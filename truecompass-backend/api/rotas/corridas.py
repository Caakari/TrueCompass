# -*- coding: utf-8 -*-
"""Ciclo da corrida.

NOTA DE CONCORRENCIA: os endpoints que tocam o grafo sao declarados com `def`
e nao `async def`. Dijkstra e A* sao CPU-bound e seguram o GIL; num
`async def` eles travariam o event loop inteiro e toda outra requisicao
ficaria parada. Com `def`, o FastAPI os executa num threadpool.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.deps import (config, obter_conexoes, obter_grafo, obter_indice_nos,
                      obter_registro, usuario_atual)
from api.esquemas import CorridaEntrada, CorridaSaida, RotaSaida
from api.eventos import comitar_e_publicar
from dominio import estados as E
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
                      estado=E.ESTADO_INICIAL)
    sessao.add(corrida)
    sessao.flush()

    try:
        servico.alocar_motorista(sessao, grafo, registro, corrida, cfg)
        servico.definir_rota(sessao, grafo, corrida)
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
    return CorridaSaida.model_validate(corrida, from_attributes=True)


@rotas.get("/{corrida_id}", response_model=CorridaSaida)
def consultar(corrida_id: int, usuario: Usuario = Depends(usuario_atual),
              sessao: Session = Depends(obter_sessao)):
    return CorridaSaida.model_validate(_carregar(sessao, corrida_id, usuario),
                                       from_attributes=True)


@rotas.get("/{corrida_id}/rota", response_model=RotaSaida)
def obter_rota(corrida_id: int, usuario: Usuario = Depends(usuario_atual),
               sessao: Session = Depends(obter_sessao), grafo=Depends(obter_grafo)):
    """Traçado para o Leaflet desenhar. A* com heuristica haversine."""
    corrida = _carregar(sessao, corrida_id, usuario)
    try:
        segundos, caminho = servico.calcular_rota(grafo, corrida.no_origem,
                                                  corrida.no_destino)
    except servico.DestinoInalcancavel as erro:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(erro))
    return RotaSaida(segundos=segundos,
                     metros=servico.comprimento_metros(grafo, caminho),
                     pontos=[grafo.coordenadas(no) for no in caminho])


@rotas.post("/{corrida_id}/iniciar", response_model=CorridaSaida)
def iniciar(corrida_id: int, usuario: Usuario = Depends(usuario_atual),
            sessao: Session = Depends(obter_sessao),
            conexoes=Depends(obter_conexoes)):
    corrida = _carregar(sessao, corrida_id, usuario)
    _transitar_ou_409(sessao, corrida, E.EM_CURSO)
    comitar_e_publicar(sessao, conexoes, corrida)
    return CorridaSaida.model_validate(corrida, from_attributes=True)


@rotas.post("/{corrida_id}/finalizar", response_model=CorridaSaida)
def finalizar(corrida_id: int, usuario: Usuario = Depends(usuario_atual),
              sessao: Session = Depends(obter_sessao),
              registro=Depends(obter_registro),
              conexoes=Depends(obter_conexoes)):
    corrida = _carregar(sessao, corrida_id, usuario)
    _transitar_ou_409(sessao, corrida, E.CONCLUIDA)
    servico.liberar_motorista(sessao, registro, corrida.motorista_id)
    comitar_e_publicar(sessao, conexoes, corrida)
    return CorridaSaida.model_validate(corrida, from_attributes=True)


@rotas.post("/{corrida_id}/pagamento", response_model=CorridaSaida)
def pagar(corrida_id: int, usuario: Usuario = Depends(usuario_atual),
          sessao: Session = Depends(obter_sessao),
          conexoes=Depends(obter_conexoes)):
    """Só alcancavel a partir de `concluida` -- garantido pelo DAG, nao por `if`."""
    corrida = _carregar(sessao, corrida_id, usuario)
    try:
        servico.registrar_pagamento(sessao, corrida)
    except E.TransicaoInvalida as erro:
        raise HTTPException(status.HTTP_409_CONFLICT, str(erro))
    comitar_e_publicar(sessao, conexoes, corrida)
    return CorridaSaida.model_validate(corrida, from_attributes=True)


@rotas.post("/{corrida_id}/cancelar", response_model=CorridaSaida)
def cancelar(corrida_id: int, usuario: Usuario = Depends(usuario_atual),
             sessao: Session = Depends(obter_sessao),
             registro=Depends(obter_registro),
             conexoes=Depends(obter_conexoes)):
    corrida = _carregar(sessao, corrida_id, usuario)
    _transitar_ou_409(sessao, corrida, E.CANCELADA)
    servico.liberar_motorista(sessao, registro, corrida.motorista_id)
    comitar_e_publicar(sessao, conexoes, corrida)
    return CorridaSaida.model_validate(corrida, from_attributes=True)
