# -*- coding: utf-8 -*-
"""Posicoes dos motoristas, em memoria.

POR QUE NAO NO BANCO: um ping de GPS a cada 3-5s vezes milhares de motoristas
e uma carga de escrita que o MySQL nao deve absorver linha a linha. A posicao
corrente vive aqui; o banco guarda a ultima conhecida, persistida em lote.
"""

import threading

from algoritmos.quadtree import Quadtree


class RegistroMotoristas:
    """Estado vivo do processo. Protegido por lock: o FastAPI atende
    requisicoes em threads, e o dicionario e compartilhado."""

    def __init__(self):
        self._posicoes = {}      # motorista_id -> (lat, lon, no)
        self._disponiveis = set()
        self._indice = Quadtree()
        self._trava = threading.Lock()
        self._sujo = False

    def atualizar(self, motorista_id, lat, lon, no):
        with self._trava:
            self._posicoes[motorista_id] = (lat, lon, no)
            self._sujo = True

    def definir_disponibilidade(self, motorista_id, disponivel):
        with self._trava:
            if disponivel:
                self._disponiveis.add(motorista_id)
            else:
                self._disponiveis.discard(motorista_id)
            self._sujo = True

    def esquecer(self, motorista_id):
        with self._trava:
            self._posicoes.pop(motorista_id, None)
            self._disponiveis.discard(motorista_id)
            self._sujo = True

    def _reconstruir_se_preciso(self):
        if self._sujo:
            self._indice.reconstruir({
                mid: (lat, lon)
                for mid, (lat, lon, _) in self._posicoes.items()
                if mid in self._disponiveis
            })
            self._sujo = False

    def candidatos(self, lat, lon, raio_m, limite):
        """Motoristas disponiveis por perto -- em linha reta, ainda um chute.

        Devolve {motorista_id: no_da_malha}, que e exatamente o formato que
        `motoristas_mais_proximos` consome.
        """
        with self._trava:
            self._reconstruir_se_preciso()
            ids = self._indice.proximos(lat, lon, raio_m, limite)
            return {mid: self._posicoes[mid][2] for mid in ids
                    if self._posicoes[mid][2] is not None}

    def posicao(self, motorista_id):
        with self._trava:
            return self._posicoes.get(motorista_id)

    def instantaneo(self):
        """Copia para persistencia em lote."""
        with self._trava:
            return dict(self._posicoes)

    def __len__(self):
        with self._trava:
            return len(self._disponiveis)
