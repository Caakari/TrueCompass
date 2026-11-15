# -*- coding: utf-8 -*-
"""Ciclo da corrida.

NOTA DE CONCORRENCIA: os endpoints que tocam o grafo sao declarados com `def`
e nao `async def`. Dijkstra e A* sao CPU-bound e seguram o GIL; num
`async def` eles travariam o event loop inteiro e toda outra requisicao
ficaria parada. Com `def`, o FastAPI os executa num threadpool.
"""

import secrets

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from api.deps import (config, obter_alt, obter_conexoes, obter_geometria, obter_grafo,
                      obter_indice_nos, obter_registro, usuario_atual)
from api.esquemas import (AvaliacaoEntrada, CorridaEntrada, CorridaSaida, HistoricoItem,
                          MensagemEntrada, MensagemSaida, ParadaSaida, RotaSaida)
from api.eventos import comitar_e_publicar, mensagem_chat
from dominio import estados as E
from dominio.servicos import avaliacao as avaliacoes
from dominio.servicos import corrida as servico
from infra.banco import obter_sessao
from infra.modelos import Corrida, CorridaParada, Mensagem, Motorista, Usuario

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


def paradas_da_corrida(sessao, corrida_id):
    """Paradas na ordem pedida."""
    return (sessao.query(CorridaParada).filter_by(corrida_id=corrida_id)
            .order_by(CorridaParada.ordem).all())


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
    saida.paradas = [ParadaSaida(lat=p.lat, lon=p.lon, texto=p.texto)
                     for p in paradas_da_corrida(sessao, corrida.id)]
    if corrida.estado == E.ALOCACAO:
        oferta = servico.oferta_pendente(sessao, corrida.id)
        if oferta is not None:
            saida.aguardando_aceite = True
            saida.oferta_segundos = round(servico.segundos_para_responder(oferta), 1)
    if usuario is None or usuario.id != corrida.passageiro_id:
        saida.token_compartilhar = None
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
    nos_paradas = [indice_nos.mais_proximo(p.lat, p.lon) for p in dados.paradas]
    if origem is None or destino is None or None in nos_paradas:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "coordenadas fora da area coberta pela malha")

    corrida = Corrida(passageiro_id=usuario.id, no_origem=origem, no_destino=destino,
                      estado=E.ESTADO_INICIAL, categoria=dados.categoria,
                      forma_pagamento=dados.forma_pagamento,
                      origem_texto=(dados.origem_texto or "").strip() or None,
                      destino_texto=(dados.destino_texto or "").strip() or None)
    sessao.add(corrida)
    sessao.flush()
    for ordem, (parada, no) in enumerate(zip(dados.paradas, nos_paradas)):
        sessao.add(CorridaParada(corrida_id=corrida.id, ordem=ordem, no=no,
                                 lat=parada.lat, lon=parada.lon,
                                 texto=(parada.texto or "").strip() or None))

    try:
        # Preco antes da oferta: o motorista ve o valor para decidir.
        servico.calcular_preco(grafo, corrida, alt=alt, geometria=geometria,
                               categoria=dados.categoria, paradas=nos_paradas)
        servico.oferecer(sessao, grafo, registro, corrida, cfg)
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
    """Traçado para o Leaflet desenhar: A* trecho a trecho, pelas paradas."""
    corrida = _carregar(sessao, corrida_id, usuario)
    nos = [corrida.no_origem, *(p.no for p in paradas_da_corrida(sessao, corrida.id)),
           corrida.no_destino]
    try:
        segundos, caminho = servico.rota_por_paradas(grafo, nos, alt=alt)
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
    oferta = servico.oferta_pendente(sessao, corrida.id)
    if oferta is not None:
        servico._fechar_oferta(sessao, oferta, "cancelada", servico.agora_utc())
    servico.liberar_motorista(sessao, registro, corrida.motorista_id)
    comitar_e_publicar(sessao, conexoes, corrida)
    return _saida(sessao, corrida, grafo, usuario)


# ------------------------------------------------------------------ oferta

def _motorista_da_oferta(sessao, usuario):
    motorista = (sessao.query(Motorista).filter_by(usuario_id=usuario.id).one_or_none()
                 if usuario.tipo == "motorista" else None)
    if motorista is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "so o motorista responde a oferta")
    return motorista


@rotas.post("/{corrida_id}/aceitar", response_model=CorridaSaida)
def aceitar(corrida_id: int, usuario: Usuario = Depends(usuario_atual),
            sessao: Session = Depends(obter_sessao),
            conexoes=Depends(obter_conexoes), grafo=Depends(obter_grafo)):
    """O motorista aceita a oferta aberta, dentro do prazo: alocacao -> rota."""
    motorista = _motorista_da_oferta(sessao, usuario)
    corrida = _carregar(sessao, corrida_id, usuario)
    try:
        servico.aceitar_oferta(sessao, corrida, motorista)
    except servico.OfertaInvalida as erro:
        sessao.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, str(erro))
    comitar_e_publicar(sessao, conexoes, corrida)
    return _saida(sessao, corrida, grafo, usuario)


@rotas.post("/{corrida_id}/recusar", status_code=status.HTTP_204_NO_CONTENT)
def recusar(corrida_id: int, usuario: Usuario = Depends(usuario_atual),
            sessao: Session = Depends(obter_sessao), registro=Depends(obter_registro),
            conexoes=Depends(obter_conexoes), grafo=Depends(obter_grafo), cfg=Depends(config)):
    """O motorista recusa: a corrida e oferecida ao proximo do ranking.

    204 sem corpo: quem recusou deixa de participar da corrida e nao a ve mais.
    """
    motorista = _motorista_da_oferta(sessao, usuario)
    corrida = _carregar(sessao, corrida_id, usuario)
    try:
        servico.recusar_oferta(sessao, grafo, registro, corrida, motorista, cfg)
    except servico.OfertaInvalida as erro:
        sessao.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, str(erro))
    comitar_e_publicar(sessao, conexoes, corrida)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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


# -------------------------------------------------------------------- chat

# O chat vale enquanto os dois lados ainda precisam se encontrar ou estao
# juntos; depois do fim, a conversa vira historico e fica so leitura.
ESTADOS_COM_CHAT = (E.ALOCACAO, E.ROTA, E.EM_CURSO)


@rotas.get("/{corrida_id}/mensagens", response_model=list[MensagemSaida])
def listar_mensagens(corrida_id: int, usuario: Usuario = Depends(usuario_atual),
                     sessao: Session = Depends(obter_sessao)):
    corrida = _carregar(sessao, corrida_id, usuario)
    return [MensagemSaida.model_validate(m, from_attributes=True)
            for m in sessao.query(Mensagem).filter_by(corrida_id=corrida.id)
            .order_by(Mensagem.id).limit(500)]


@rotas.post("/{corrida_id}/mensagens", response_model=MensagemSaida,
            status_code=status.HTTP_201_CREATED)
def enviar_mensagem(corrida_id: int, dados: MensagemEntrada,
                    usuario: Usuario = Depends(usuario_atual),
                    sessao: Session = Depends(obter_sessao),
                    conexoes=Depends(obter_conexoes)):
    """Grava e SO DEPOIS publica no WebSocket da corrida (mesma regra do estado)."""
    corrida = _carregar(sessao, corrida_id, usuario)
    if corrida.estado not in ESTADOS_COM_CHAT:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"o chat fecha quando a corrida termina (estado: {corrida.estado})")
    texto = dados.texto.strip()
    if not texto:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "mensagem vazia")
    mensagem = Mensagem(corrida_id=corrida.id, autor_id=usuario.id, texto=texto)
    sessao.add(mensagem)
    sessao.commit()
    saida = MensagemSaida.model_validate(mensagem, from_attributes=True)
    conexoes.publicar(corrida.id, mensagem_chat(corrida.id, saida.model_dump(mode="json")))
    return saida


# ------------------------------------------------------------ compartilhar

@rotas.post("/{corrida_id}/compartilhar", response_model=CorridaSaida)
def compartilhar(corrida_id: int, usuario: Usuario = Depends(usuario_atual),
                 sessao: Session = Depends(obter_sessao), grafo=Depends(obter_grafo)):
    """Gera (uma vez) o token do link publico. Pedir de novo devolve o mesmo.

    So o passageiro compartilha: a viagem e dele. O token e aleatorio
    (`secrets`), e nao derivado do id, para nao ser adivinhavel.
    """
    corrida = _carregar(sessao, corrida_id, usuario)
    if usuario.id != corrida.passageiro_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "so o passageiro compartilha a viagem")
    if corrida.estado in E.ESTADOS_FINAIS:
        raise HTTPException(status.HTTP_409_CONFLICT, "a corrida ja terminou")
    if corrida.token_compartilhar is None:
        corrida.token_compartilhar = secrets.token_urlsafe(16)
        sessao.commit()
    return _saida(sessao, corrida, grafo, usuario)
