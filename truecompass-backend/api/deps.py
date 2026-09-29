# -*- coding: utf-8 -*-
"""Dependencias injetadas nas rotas."""

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session
from starlette.requests import HTTPConnection

from infra.banco import obter_sessao
from infra.config import obter_config
from infra.modelos import Motorista, Usuario
from infra.seguranca import ler_token


# `HTTPConnection` e a classe-base comum de `Request` e `WebSocket`. Anotar com
# `Request` quebraria estas dependencias nas rotas WebSocket, onde o FastAPI
# injeta um `WebSocket` -- e o erro so apareceria em producao, no primeiro
# cliente que tentasse acompanhar uma corrida.
def obter_grafo(conexao: HTTPConnection):
    """A malha viaria, carregada uma unica vez no boot."""
    return conexao.app.state.grafo


def obter_indice_nos(conexao: HTTPConnection):
    return conexao.app.state.indice_nos


def obter_registro(conexao: HTTPConnection):
    return conexao.app.state.registro


def obter_conexoes(conexao: HTTPConnection):
    return conexao.app.state.conexoes


def usuario_atual(authorization: str = Header(default=""),
                  sessao: Session = Depends(obter_sessao)):
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token ausente")
    dados = ler_token(authorization.split(None, 1)[1])
    if not dados:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token invalido ou expirado")
    usuario = sessao.get(Usuario, int(dados["sub"]))
    if not usuario:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "usuario inexistente")
    return usuario


def motorista_atual(usuario: Usuario = Depends(usuario_atual),
                    sessao: Session = Depends(obter_sessao)):
    motorista = sessao.query(Motorista).filter_by(usuario_id=usuario.id).one_or_none()
    if not motorista:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "rota exclusiva de motorista")
    return motorista


def config():
    return obter_config()
