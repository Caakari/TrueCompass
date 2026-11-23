# -*- coding: utf-8 -*-
"""Avaliacao de 1 a 5 estrelas entre passageiro e motorista.

Regras (sem HTTP e sem SQL bruto, como o resto do dominio):

- So se avalia corrida que CHEGOU ao fim: `concluida` ou `paga`. Avaliar uma
  corrida cancelada ou em curso nao faria sentido -- e o mesmo DAG que
  impede pagar antes de concluir.
- Cada lado avalia o OUTRO: o passageiro avalia o usuario do motorista, e o
  motorista avalia o passageiro. Uma vez por corrida (restricao no banco).
- A media e calculada no banco (AVG), nunca guardada: guardar a media exigiria
  mante-la em sincronia a cada nota nova, e um erro ali nao teria volta.
"""

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from dominio import estados as E
from infra.modelos import Avaliacao, Motorista

ESTADOS_AVALIAVEIS = (E.CONCLUIDA, E.PAGA)


class AvaliacaoInvalida(Exception):
    pass


class AvaliacaoRepetida(Exception):
    pass


def avaliado_por(sessao, corrida, autor):
    """Id do usuario que `autor` avalia nesta corrida (o outro lado)."""
    if autor.id == corrida.passageiro_id:
        if corrida.motorista_id is None:
            raise AvaliacaoInvalida("corrida sem motorista")
        return sessao.get(Motorista, corrida.motorista_id).usuario_id
    motorista = sessao.query(Motorista).filter_by(usuario_id=autor.id).one_or_none()
    if motorista is not None and motorista.id == corrida.motorista_id:
        return corrida.passageiro_id
    raise AvaliacaoInvalida("so quem participou da corrida avalia")


def avaliar(sessao, corrida, autor, nota, comentario=None):
    if corrida.estado not in ESTADOS_AVALIAVEIS:
        raise AvaliacaoInvalida(f"so se avalia corrida concluida (estado: {corrida.estado})")
    if not 1 <= nota <= 5:
        raise AvaliacaoInvalida("a nota vai de 1 a 5")
    avaliacao = Avaliacao(corrida_id=corrida.id, autor_id=autor.id,
                          avaliado_id=avaliado_por(sessao, corrida, autor),
                          nota=nota, comentario=(comentario or "").strip() or None)
    sessao.add(avaliacao)
    try:
        sessao.flush()
    except IntegrityError as erro:
        sessao.rollback()
        raise AvaliacaoRepetida("voce ja avaliou esta corrida") from erro
    return avaliacao


def nota_media(sessao, usuario_id):
    """(media com 1 casa, quantidade). Media None se ninguem avaliou ainda."""
    media, total = (sessao.query(func.avg(Avaliacao.nota), func.count(Avaliacao.id))
                    .filter(Avaliacao.avaliado_id == usuario_id).one())
    return (round(float(media), 1) if total else None), int(total)


def nota_dada(sessao, corrida_id, autor_id):
    nota = (sessao.query(Avaliacao.nota)
            .filter_by(corrida_id=corrida_id, autor_id=autor_id).scalar())
    return int(nota) if nota is not None else None
