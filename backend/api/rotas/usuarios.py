# -*- coding: utf-8 -*-
"""Perfil da conta e locais salvos (Casa, Trabalho e favoritos)."""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from api.esquemas import LocalEntrada, LocalSaida, PerfilEntrada, PerfilSaida
from dominio import estados as E
from dominio.servicos.avaliacao import nota_media
from infra.banco import obter_sessao
from infra.modelos import Corrida, LocalSalvo, Motorista, Usuario
from api.deps import usuario_atual

rotas = APIRouter(prefix="/usuarios/eu", tags=["perfil"])

MAXIMO_FAVORITOS = 20
ROTULOS = {"casa": "Casa", "trabalho": "Trabalho"}


def _motorista_de(sessao, usuario):
    if usuario.tipo != "motorista":
        return None
    return sessao.query(Motorista).filter_by(usuario_id=usuario.id).one_or_none()


def _perfil(sessao, usuario):
    motorista = _motorista_de(sessao, usuario)
    nota, avaliacoes = nota_media(sessao, usuario.id)
    if motorista is not None:
        filtro = Corrida.motorista_id == motorista.id
    else:
        filtro = Corrida.passageiro_id == usuario.id
    corridas = (sessao.query(func.count(Corrida.id))
                .filter(filtro, Corrida.estado.in_((E.CONCLUIDA, E.PAGA))).scalar()) or 0
    return PerfilSaida(
        id=usuario.id, nome=usuario.nome, email=usuario.email, tipo=usuario.tipo,
        telefone=usuario.telefone, cor_avatar=usuario.cor_avatar, criado_em=usuario.criado_em,
        placa=motorista.placa if motorista else None,
        modelo=(motorista.modelo or None) if motorista else None,
        cor_carro=motorista.cor_carro if motorista else None,
        nota=nota, avaliacoes=avaliacoes, corridas=corridas,
    )


@rotas.get("", response_model=PerfilSaida)
def ver_perfil(usuario: Usuario = Depends(usuario_atual),
               sessao: Session = Depends(obter_sessao)):
    return _perfil(sessao, usuario)


@rotas.patch("", response_model=PerfilSaida)
def editar_perfil(dados: PerfilEntrada, usuario: Usuario = Depends(usuario_atual),
                  sessao: Session = Depends(obter_sessao)):
    """Muda so os campos enviados. String vazia apaga telefone e cor."""
    enviados = dados.model_dump(exclude_unset=True)
    if "nome" in enviados and dados.nome:
        usuario.nome = dados.nome.strip()
    for campo in ("telefone", "cor_avatar"):
        if campo in enviados:
            setattr(usuario, campo, (enviados[campo] or "").strip() or None)

    dados_carro = {k: enviados[k] for k in ("placa", "modelo", "cor_carro") if k in enviados}
    if dados_carro:
        motorista = _motorista_de(sessao, usuario)
        if motorista is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                                "placa, modelo e cor do carro sao so de motorista")
        if "placa" in dados_carro and dados_carro["placa"]:
            motorista.placa = dados_carro["placa"].strip().upper()
        if "modelo" in dados_carro:
            motorista.modelo = (dados_carro["modelo"] or "").strip()
        if "cor_carro" in dados_carro:
            motorista.cor_carro = (dados_carro["cor_carro"] or "").strip() or None
    sessao.commit()
    return _perfil(sessao, usuario)


# ------------------------------------------------------------ locais salvos

def _saida_local(local):
    return LocalSaida.model_validate(local, from_attributes=True)


@rotas.get("/locais", response_model=list[LocalSaida])
def listar_locais(usuario: Usuario = Depends(usuario_atual),
                  sessao: Session = Depends(obter_sessao)):
    """Casa e Trabalho primeiro, depois os favoritos na ordem em que foram salvos."""
    ordem = {"casa": 0, "trabalho": 1, "outro": 2}
    locais = sessao.query(LocalSalvo).filter_by(usuario_id=usuario.id).all()
    locais.sort(key=lambda l: (ordem.get(l.tipo, 3), l.id))
    return [_saida_local(l) for l in locais]


@rotas.post("/locais", response_model=LocalSaida)
def salvar_local(dados: LocalEntrada, usuario: Usuario = Depends(usuario_atual),
                 sessao: Session = Depends(obter_sessao)):
    """Casa e Trabalho sao unicos: salvar de novo SUBSTITUI o anterior."""
    if dados.tipo in ROTULOS:
        local = (sessao.query(LocalSalvo)
                 .filter_by(usuario_id=usuario.id, tipo=dados.tipo).one_or_none())
        rotulo = ROTULOS[dados.tipo]
    else:
        total = (sessao.query(func.count(LocalSalvo.id))
                 .filter_by(usuario_id=usuario.id, tipo="outro").scalar())
        if total >= MAXIMO_FAVORITOS:
            raise HTTPException(status.HTTP_409_CONFLICT,
                                f"limite de {MAXIMO_FAVORITOS} favoritos atingido")
        local = None
        rotulo = (dados.rotulo or "").strip() or dados.titulo[:40]
    if local is None:
        local = LocalSalvo(usuario_id=usuario.id, tipo=dados.tipo)
        sessao.add(local)
    local.rotulo, local.titulo, local.detalhe = rotulo, dados.titulo, dados.detalhe
    local.lat, local.lon = dados.lat, dados.lon
    sessao.commit()
    return _saida_local(local)


@rotas.delete("/locais/{local_id}", status_code=status.HTTP_204_NO_CONTENT)
def apagar_local(local_id: int, usuario: Usuario = Depends(usuario_atual),
                 sessao: Session = Depends(obter_sessao)):
    local = sessao.get(LocalSalvo, local_id)
    # Local de outra pessoa responde 404, nao 403: nao revela que o id existe.
    if local is None or local.usuario_id != usuario.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "local inexistente")
    sessao.delete(local)
    sessao.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
