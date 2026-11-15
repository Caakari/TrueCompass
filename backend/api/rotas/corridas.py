# -*- coding: utf-8 -*-
"""Ciclo da corrida.

NOTA DE CONCORRENCIA: os endpoints que tocam o grafo sao declarados com `def`
e nao `async def`. Dijkstra e A* sao CPU-bound e seguram o GIL; num
`async def` eles travariam o event loop inteiro e toda outra requisicao
ficaria parada. Com `def`, o FastAPI os executa num threadpool.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from api.deps import (config, obter_alt, obter_conexoes, obter_geometria, obter_grafo,
                      obter_indice_nos, obter_registro, usuario_atual)
from api.esquemas import (AvaliacaoEntrada, CorridaEntrada, CorridaSaida, HistoricoItem,
                          RotaSaida)
from api.eventos import comitar_e_publicar
from dominio import estados as E
from dominio.servicos import avaliacao as avaliacoes
from dominio.servicos import corrida as servico
from infra.banco import obter_sessao
from infra.modelos import Corrida, Motorista, Usuario

rotas = APIRouter(prefix="/corridas", tags=["corridas"])


def _carregar(sessao, corrida_id, usuario):
    corrida = sessao.get(Corrida, corrida_id)
    if not corrida:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "corrida inexistente")
    motorista = (sessao.query(Motorista).filter_by(usuario_id=usuario.id).one_or_none()
                 if usuario.tipo == "motorista" else None)
    envolvido = (corrida.passageiro_id == usuario.id
                 or (motorista and corrida.motorista_id == motorista.id))
    if not envolvido:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "corrida de outra pessoa")
    return corrida


def corridas_concluidas(sessao, motorista_id):
    """Corridas que o motorista levou ate o fim (concluidas ou ja pagas)."""
    return (sessao.query(func.count(Corrida.id))
            .filter(Corrida.motorista_id == motorista_id,
                    Corrida.estado.in_((E.CONCLUIDA, E.PAGA)))
            .scalar()) or 0


def _saida(sessao, corrida, grafo, usuario=None):
    """CorridaSaida com o que o app mostra no card: nomes, placa, notas, pontos.

    `usuario` (quem pergunta) preenche `minha_avaliacao`.
    """
    saida = CorridaSaida.model_validate(corrida, from_attributes=True)
    passageiro = sessao.get(Usuario, corrida.passageiro_id)
    saida.passageiro_nome = passageiro.nome if passageiro else None
    saida.passageiro_nota = avaliacoes.nota_media(sessao, corrida.passageiro_id)[0]
    if corrida.motorista_id is not None:
        motorista = sessao.get(Motorista, corrida.motorista_id)
        if motorista is not None:
            saida.motorista_placa = motorista.placa
            saida.motorista_modelo = motorista.modelo or None
            saida.motorista_cor_carro = motorista.cor_carro
            saida.motorista_nome = motorista.usuario.nome if motorista.usuario else None
            saida.motorista_corridas = corridas_concluidas(sessao, motorista.id)
            saida.motorista_nota, saida.motorista_avaliacoes = avaliacoes.nota_media(
                sessao, motorista.usuario_id)
    if usuario is not None:
        saida.minha_avaliacao = avaliacoes.nota_dada(sessao, corrida.id, usuario.id)
    for campo, no in (("origem", corrida.no_origem), ("destino", corrida.no_destino)):
        if no in grafo.nos:
            setattr(saida, campo, grafo.coordenadas(no))
    return saida


def _transitar_ou_409(sessao, corrida, novo_estado):
    """Traduz a recusa do DAG em resposta HTTP.

    409 Conflict e o codigo certo: o pedido e valido, mas conflita com o
    estado atual do recurso.
    """
    try:
        servico.transitar(sessao, corrida, novo_estado)
    except E.TransicaoInvalida as erro:
        raise HTTPException(status.HTTP_409_CONFLICT, str(erro))


@rotas.post("", response_model=CorridaSaida, status_code=status.HTTP_201_CREATED)
def pedir_corrida(dados: CorridaEntrada,
                  usuario: Usuario = Depends(usuario_atual),
                  sessao: Session = Depends(obter_sessao),
                  grafo=Depends(obter_grafo),
                  alt=Depends(obter_alt),
                  geometria=Depends(obter_geometria),
                  indice_nos=Depends(obter_indice_nos),
                  registro=Depends(obter_registro),
                  conexoes=Depends(obter_conexoes),
                  cfg=Depends(config)):
    """Pedido de corrida: ancora, pareia e roteia numa transacao."""
    if usuario.tipo != "passageiro":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "apenas passageiros pedem corrida")

    origem = indice_nos.mais_proximo(dados.origem_lat, dados.origem_lon)
    destino = indice_nos.mais_proximo(dados.destino_lat, dados.destino_lon)
    if origem is None or destino is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "coordenadas fora da area coberta pela malha")

    corrida = Corrida(passageiro_id=usuario.id, no_origem=origem, no_destino=destino,
                      estado=E.ESTADO_INICIAL, categoria=dados.categoria,
                      forma_pagamento=dados.forma_pagamento,
                      origem_texto=(dados.origem_texto or "").strip() or None,
                      destino_texto=(dados.destino_texto or "").strip() or None)
    sessao.add(corrida)
    sessao.flush()

    try:
        servico.alocar_motorista(sessao, grafo, registro, corrida, cfg)
        servico.definir_rota(sessao, grafo, corrida, alt=alt, geometria=geometria,
                             categoria=dados.categoria)
    except servico.SemMotoristaDisponivel as erro:
        _transitar_ou_409(sessao, corrida, E.CANCELADA)
        comitar_e_publicar(sessao, conexoes, corrida)
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(erro))
    except servico.DestinoInalcancavel as erro:
        servico.liberar_motorista(sessao, registro, corrida.motorista_id)
        _transitar_ou_409(sessao, corrida, E.CANCELADA)
        comitar_e_publicar(sessao, conexoes, corrida)
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(erro))

    comitar_e_publicar(sessao, conexoes, corrida)
    return _saida(sessao, corrida, grafo, usuario)


@rotas.get("/{corrida_id}", response_model=CorridaSaida)
def consultar(corrida_id: int, usuario: Usuario = Depends(usuario_atual),
              sessao: Session = Depends(obter_sessao),
              grafo=Depends(obter_grafo)):
    return _saida(sessao, _carregar(sessao, corrida_id, usuario), grafo, usuario)


@rotas.get("/{corrida_id}/rota", response_model=RotaSaida)
def obter_rota(corrida_id: int, usuario: Usuario = Depends(usuario_atual),
               sessao: Session = Depends(obter_sessao), grafo=Depends(obter_grafo),
               alt=Depends(obter_alt), geometria=Depends(obter_geometria)):
    """Traçado para o Leaflet desenhar. A* com heuristica haversine."""
    corrida = _carregar(sessao, corrida_id, usuario)
    try:
        segundos, caminho = servico.calcular_rota(grafo, corrida.no_origem,
                                                  corrida.no_destino, alt=alt)
    except servico.DestinoInalcancavel as erro:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(erro))
    return RotaSaida(segundos=segundos,
                     metros=servico.comprimento_metros(grafo, caminho, geometria),
                     pontos=servico.tracado(grafo, caminho, geometria))


@rotas.get("/{corrida_id}/rota-motorista", response_model=RotaSaida)
def obter_rota_do_motorista(corrida_id: int,
                            usuario: Usuario = Depends(usuario_atual),
                            sessao: Session = Depends(obter_sessao),
                            grafo=Depends(obter_grafo),
                            alt=Depends(obter_alt),
                            geometria=Depends(obter_geometria)):
    """Trajeto do motorista ate o passageiro, sobre as ruas.

    Alvo unico, portanto A* com heuristica. Calculado sob demanda a partir da
    posicao ATUAL do motorista, e nao a do momento da alocacao -- ele ja andou
    desde entao.
    """
    corrida = _carregar(sessao, corrida_id, usuario)
    if corrida.motorista_id is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "corrida sem motorista alocado")

    motorista = sessao.get(Motorista, corrida.motorista_id)
    if motorista is None or motorista.no_atual is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "motorista sem posicao conhecida")

    try:
        segundos, caminho = servico.calcular_rota(grafo, motorista.no_atual,
                                                 corrida.no_origem, alt=alt)
    except servico.DestinoInalcancavel as erro:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(erro))

    return RotaSaida(segundos=segundos,
                     metros=servico.comprimento_metros(grafo, caminho, geometria),
                     pontos=servico.tracado(grafo, caminho, geometria))


@rotas.post("/{corrida_id}/iniciar", response_model=CorridaSaida)
def iniciar(corrida_id: int, usuario: Usuario = Depends(usuario_atual),
            sessao: Session = Depends(obter_sessao),
            conexoes=Depends(obter_conexoes),
            grafo=Depends(obter_grafo)):
    corrida = _carregar(sessao, corrida_id, usuario)
    _transitar_ou_409(sessao, corrida, E.EM_CURSO)
    comitar_e_publicar(sessao, conexoes, corrida)
    return _saida(sessao, corrida, grafo, usuario)


@rotas.post("/{corrida_id}/finalizar", response_model=CorridaSaida)
def finalizar(corrida_id: int, usuario: Usuario = Depends(usuario_atual),
              sessao: Session = Depends(obter_sessao),
              registro=Depends(obter_registro),
              conexoes=Depends(obter_conexoes),
              grafo=Depends(obter_grafo)):
    corrida = _carregar(sessao, corrida_id, usuario)
    _transitar_ou_409(sessao, corrida, E.CONCLUIDA)
    servico.liberar_motorista(sessao, registro, corrida.motorista_id)
    comitar_e_publicar(sessao, conexoes, corrida)
    return _saida(sessao, corrida, grafo, usuario)


@rotas.post("/{corrida_id}/pagamento", response_model=CorridaSaida)
def pagar(corrida_id: int, usuario: Usuario = Depends(usuario_atual),
          sessao: Session = Depends(obter_sessao),
          conexoes=Depends(obter_conexoes),
          grafo=Depends(obter_grafo)):
    """Só alcancavel a partir de `concluida` -- garantido pelo DAG, nao por `if`."""
    corrida = _carregar(sessao, corrida_id, usuario)
    try:
        servico.registrar_pagamento(sessao, corrida)
    except E.TransicaoInvalida as erro:
        raise HTTPException(status.HTTP_409_CONFLICT, str(erro))
    comitar_e_publicar(sessao, conexoes, corrida)
    return _saida(sessao, corrida, grafo, usuario)


@rotas.post("/{corrida_id}/cancelar", response_model=CorridaSaida)
def cancelar(corrida_id: int, usuario: Usuario = Depends(usuario_atual),
             sessao: Session = Depends(obter_sessao),
             registro=Depends(obter_registro),
             conexoes=Depends(obter_conexoes),
             grafo=Depends(obter_grafo)):
    corrida = _carregar(sessao, corrida_id, usuario)
    _transitar_ou_409(sessao, corrida, E.CANCELADA)
    servico.liberar_motorista(sessao, registro, corrida.motorista_id)
    comitar_e_publicar(sessao, conexoes, corrida)
    return _saida(sessao, corrida, grafo, usuario)


# ------------------------------------------------------- historico e notas

@rotas.get("", response_model=list[HistoricoItem])
def historico(limite: int = 20, antes_de: int | None = None,
              usuario: Usuario = Depends(usuario_atual),
              sessao: Session = Depends(obter_sessao)):
    """Corridas de quem pergunta, da mais recente para a mais antiga.

    Paginacao por CURSOR (`antes_de` = menor id ja recebido), nao por offset:
    corrida nova chegando no meio da rolagem nao desloca a lista nem repete itens.
    """
    limite = max(1, min(limite, 50))
    motorista = (sessao.query(Motorista).filter_by(usuario_id=usuario.id).one_or_none()
                 if usuario.tipo == "motorista" else None)
    consulta = sessao.query(Corrida)
    if motorista is not None:
        consulta = consulta.filter(Corrida.motorista_id == motorista.id)
    else:
        consulta = consulta.filter(Corrida.passageiro_id == usuario.id)
    if antes_de is not None:
        consulta = consulta.filter(Corrida.id < antes_de)
    itens = []
    for corrida in consulta.order_by(Corrida.id.desc()).limit(limite):
        if motorista is not None:
            outro = sessao.get(Usuario, corrida.passageiro_id)
        elif corrida.motorista_id is not None:
            outro = sessao.get(Motorista, corrida.motorista_id).usuario
        else:
            outro = None
        item = HistoricoItem.model_validate(corrida, from_attributes=True)
        item.outro_nome = outro.nome if outro else None
        item.minha_avaliacao = avaliacoes.nota_dada(sessao, corrida.id, usuario.id)
        itens.append(item)
    return itens


@rotas.post("/{corrida_id}/avaliacao", response_model=CorridaSaida)
def avaliar(corrida_id: int, dados: AvaliacaoEntrada,
            usuario: Usuario = Depends(usuario_atual),
            sessao: Session = Depends(obter_sessao),
            grafo=Depends(obter_grafo)):
    """Nota de 1 a 5 ao outro lado, depois que a corrida chegou ao fim."""
    corrida = _carregar(sessao, corrida_id, usuario)
    try:
        avaliacoes.avaliar(sessao, corrida, usuario, dados.nota, dados.comentario)
    except avaliacoes.AvaliacaoRepetida as erro:
        raise HTTPException(status.HTTP_409_CONFLICT, str(erro))
    except avaliacoes.AvaliacaoInvalida as erro:
        raise HTTPException(status.HTTP_409_CONFLICT, str(erro))
    sessao.commit()
    return _saida(sessao, corrida, grafo, usuario)
