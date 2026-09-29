# -*- coding: utf-8 -*-
"""Publicacao de eventos da corrida no WebSocket.

REGRA CENTRAL: publicar SEMPRE depois do commit, nunca antes.

Se o evento sair junto com a transicao e a transacao rolar atras depois, o
cliente recebe uma mudanca de estado que nunca aconteceu -- o passageiro ve
"motorista a caminho" sem motorista algum alocado. Estado no banco e estado na
tela divergem, e nada no sistema volta a corrigir isso.

Por isso `comitar_e_publicar` existe: ela impoe a ordem. Nenhuma rota de
corrida chama `sessao.commit()` diretamente.
"""

from datetime import datetime, timezone


def _agora():
    return datetime.now(timezone.utc).isoformat()


def mensagem_estado(corrida):
    return {
        "evento": "estado",
        "corrida_id": corrida.id,
        "estado": corrida.estado,
        "motorista_id": corrida.motorista_id,
        "eta_segundos": corrida.eta_segundos,
        "custo_estimado": corrida.custo_estimado,
        "em": _agora(),
    }


def mensagem_posicao(corrida_id, motorista_id, lat, lon):
    return {
        "evento": "posicao",
        "corrida_id": corrida_id,
        "motorista_id": motorista_id,
        "lat": lat,
        "lon": lon,
        "em": _agora(),
    }


def comitar_e_publicar(sessao, conexoes, corrida):
    """Confirma a transacao e so entao avisa quem acompanha.

    Se o commit levantar, nada e publicado -- que e exatamente o desejado.
    """
    sessao.commit()
    conexoes.publicar(corrida.id, mensagem_estado(corrida))
    return corrida
