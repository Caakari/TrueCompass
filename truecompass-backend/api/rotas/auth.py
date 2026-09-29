# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.esquemas import LoginEntrada, RegistroEntrada, TokenSaida
from infra.banco import obter_sessao
from infra.modelos import Motorista, Usuario
from infra.seguranca import cifrar_senha, conferir_senha, emitir_token

rotas = APIRouter(prefix="/auth", tags=["auth"])


@rotas.post("/registro", response_model=TokenSaida,
            status_code=status.HTTP_201_CREATED)
def registrar(dados: RegistroEntrada, sessao: Session = Depends(obter_sessao)):
    if dados.tipo == "motorista" and not dados.placa:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "motorista exige placa")

    usuario = Usuario(nome=dados.nome, email=dados.email.lower(),
                      senha_hash=cifrar_senha(dados.senha), tipo=dados.tipo)
    sessao.add(usuario)
    try:
        sessao.flush()
        if dados.tipo == "motorista":
            sessao.add(Motorista(usuario_id=usuario.id, placa=dados.placa,
                                 modelo=dados.modelo or ""))
        sessao.commit()
    except IntegrityError:
        sessao.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "email ja cadastrado")

    return TokenSaida(token=emitir_token(usuario.id, usuario.tipo),
                      usuario_id=usuario.id, tipo=usuario.tipo)


@rotas.post("/login", response_model=TokenSaida)
def login(dados: LoginEntrada, sessao: Session = Depends(obter_sessao)):
    usuario = sessao.query(Usuario).filter_by(email=dados.email.lower()).one_or_none()
    # Mensagem unica para email inexistente e senha errada: nao entregamos
    # ao atacante a informacao de quais emails estao cadastrados.
    if not usuario or not conferir_senha(dados.senha, usuario.senha_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "credenciais invalidas")
    return TokenSaida(token=emitir_token(usuario.id, usuario.tipo),
                      usuario_id=usuario.id, tipo=usuario.tipo)
