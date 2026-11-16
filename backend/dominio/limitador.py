# -*- coding: utf-8 -*-
"""Limite de tentativas (login errado, codigo errado, reenvio de codigo).

Janela deslizante em memoria: guarda o instante de cada falha recente por
CHAVE (ex.: "login:email:ana@x.com", "login:ip:1.2.3.4"). Passou de
`maximo` falhas dentro de `janela_s`, a chave fica bloqueada por `bloqueio_s`.

Em memoria, e nao no banco, de proposito: e consultado a cada tentativa e
nao precisa sobreviver a um reinicio (o pior caso e o atacante ganhar uma
janela nova). O servidor do TrueCompass e UM processo (o grafo vive em
memoria); com varias instancias isto teria de ir para um Redis.

Puro: o relogio e injetavel, para os testes nao dormirem.
"""

import threading
import time
from collections import defaultdict, deque


class Limitador:
    def __init__(self, maximo, janela_s, bloqueio_s, relogio=time.monotonic):
        self.maximo, self.janela_s, self.bloqueio_s = maximo, janela_s, bloqueio_s
        self._relogio = relogio
        self._falhas = defaultdict(deque)
        self._bloqueado_ate = {}
        self._trava = threading.Lock()

    def espera(self, chave):
        """Segundos que faltam para a chave poder tentar de novo (0 = livre)."""
        with self._trava:
            fim = self._bloqueado_ate.get(chave)
            if fim is None:
                return 0
            resta = fim - self._relogio()
            if resta <= 0:
                del self._bloqueado_ate[chave]
                return 0
            return int(resta) + 1          # arredonda para cima: nunca libera cedo

    def falhou(self, chave):
        """Registra uma falha. Devolve a espera imposta (0 se ainda nao bloqueou)."""
        with self._trava:
            agora = self._relogio()
            falhas = self._falhas[chave]
            falhas.append(agora)
            while falhas and agora - falhas[0] > self.janela_s:
                falhas.popleft()
            if len(falhas) >= self.maximo:
                self._bloqueado_ate[chave] = agora + self.bloqueio_s
                falhas.clear()
                return int(self.bloqueio_s)
            return 0

    def limpar(self, chave):
        """Acertou: zera o historico (um erro de digitacao antigo nao conta)."""
        with self._trava:
            self._falhas.pop(chave, None)
            self._bloqueado_ate.pop(chave, None)

    def zerar(self):
        with self._trava:
            self._falhas.clear()
            self._bloqueado_ate.clear()


class Limites:
    """Os limitadores do login, num lugar so (vive em app.state)."""

    def __init__(self, relogio=time.monotonic):
        # 5 senhas erradas para o MESMO e-mail em 15 min: 5 min parado.
        self.login_email = Limitador(5, 15 * 60, 5 * 60, relogio)
        # Do MESMO IP, contra quem testa muitos e-mails: 20 em 15 min -> 15 min.
        self.login_ip = Limitador(20, 15 * 60, 15 * 60, relogio)
        # Codigo errado: 8 em 15 min por e-mail (cada codigo ainda morre em 5).
        self.codigo = Limitador(8, 15 * 60, 15 * 60, relogio)
        # Envio de codigo: no maximo 5 por hora para o mesmo e-mail...
        self.envios = Limitador(5, 60 * 60, 60 * 60, relogio)
        # ...e um intervalo minimo entre dois envios.
        self.intervalo_envio = {}
        self.intervalo_envio_s = 60
        self._relogio = relogio
        self._trava = threading.Lock()

    def espera_para_enviar(self, chave):
        """Segundos ate poder mandar outro codigo para `chave` (0 = pode)."""
        with self._trava:
            ultimo = self.intervalo_envio.get(chave)
            if ultimo is not None:
                resta = self.intervalo_envio_s - (self._relogio() - ultimo)
                if resta > 0:
                    return int(resta) + 1
        return self.envios.espera(chave)

    def registrar_envio(self, chave):
        with self._trava:
            self.intervalo_envio[chave] = self._relogio()
        self.envios.falhou(chave)        # conta como uso; o 6o na hora bloqueia

    def zerar(self):
        for limitador in (self.login_email, self.login_ip, self.codigo, self.envios):
            limitador.zerar()
        with self._trava:
            self.intervalo_envio.clear()
