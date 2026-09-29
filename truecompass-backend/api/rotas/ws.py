# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from api.deps import obter_conexoes
from api.eventos import mensagem_estado
from infra.banco import Sessao
from infra.modelos import Corrida, Motorista
from infra.seguranca import ler_token

rotas = APIRouter(tags=["tempo real"])


@rotas.websocket("/ws/corridas/{corrida_id}")
async def acompanhar(websocket: WebSocket, corrida_id: int, token: str = "",
                     conexoes=Depends(obter_conexoes)):
    """Acompanhamento em tempo real de uma corrida.

    O token vem na query string porque a API de WebSocket do navegador nao
    permite cabecalhos personalizados no handshake.
    """
    dados = ler_token(token)
    if not dados:
        await websocket.close(code=4401, reason="token invalido")
        return

    usuario_id = int(dados["sub"])
    sessao = Sessao()
    try:
        corrida = sessao.get(Corrida, corrida_id)
        if not corrida:
            await websocket.close(code=4404, reason="corrida inexistente")
            return

        # Os dois lados acompanham: o passageiro ve o carro chegando, e o
        # motorista ve a corrida mudar de estado pela mao do passageiro.
        motorista = (sessao.query(Motorista).filter_by(usuario_id=usuario_id)
                     .one_or_none())
        envolvido = (corrida.passageiro_id == usuario_id
                     or (motorista and corrida.motorista_id == motorista.id))
        if not envolvido:
            await websocket.close(code=4403, reason="corrida de outra pessoa")
            return
        estado_inicial = mensagem_estado(corrida)
    finally:
        sessao.close()

    await conexoes.conectar(corrida_id, websocket)
    await websocket.send_json(estado_inicial)
    try:
        while True:
            await websocket.receive_text()      # mantem a conexao viva
    except WebSocketDisconnect:
        pass
    finally:
        conexoes.desconectar(corrida_id, websocket)
