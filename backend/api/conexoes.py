# -*- coding: utf-8 -*-
"""Gerenciador de conexoes WebSocket, por corrida.

O detalhe que exige cuidado: as rotas HTTP que mudam o estado da corrida
rodam em THREADS (sao `def`, nao `async def`), enquanto os WebSockets vivem
no event loop. Chamar `await websocket.send_json()` de uma thread nao
funciona -- e por isso `publicar` usa `run_coroutine_threadsafe`, que agenda
o envio no loop a partir de fora dele.
"""

import asyncio
import logging

registrador = logging.getLogger("truecompass.ws")


class GerenciadorConexoes:
    def __init__(self):
        self._por_corrida = {}
        self._loop = None

    def registrar_loop(self, loop):
        """Guardado no startup: e a ponte entre as threads e o event loop."""
        self._loop = loop

    async def conectar(self, corrida_id, websocket):
        await websocket.accept()
        self._por_corrida.setdefault(corrida_id, set()).add(websocket)

    def desconectar(self, corrida_id, websocket):
        conexoes = self._por_corrida.get(corrida_id)
        if conexoes:
            conexoes.discard(websocket)
            if not conexoes:
                del self._por_corrida[corrida_id]

    async def _enviar(self, corrida_id, mensagem):
        for websocket in list(self._por_corrida.get(corrida_id, ())):
            try:
                await websocket.send_json(mensagem)
            except Exception:
                # Cliente caiu no meio do envio: limpa e segue. Uma conexao
                # morta nunca pode derrubar a transicao de estado.
                self.desconectar(corrida_id, websocket)

    def publicar(self, corrida_id, mensagem):
        """Chamavel de dentro de uma rota sincrona."""
        if not self._loop or corrida_id not in self._por_corrida:
            return
        try:
            asyncio.run_coroutine_threadsafe(
                self._enviar(corrida_id, mensagem), self._loop
            )
        except RuntimeError as erro:
            registrador.warning("falha ao publicar no websocket: %s", erro)

    def total(self):
        return sum(len(c) for c in self._por_corrida.values())
