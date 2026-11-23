# -*- coding: utf-8 -*-
"""Atraso esperado em cruzamento semaforizado.

DEDUCAO. Um veiculo chega ao cruzamento em instante uniformemente distribuido
dentro do ciclo [0, c). Sendo r a duracao do vermelho e g = c - r a do verde:

  - com probabilidade g/c a chegada cai no verde, e a espera e zero;
  - com probabilidade r/c cai no vermelho, em instante uniforme dentro de
    [0, r), e a espera e o tempo restante -- em media r/2.

Logo:

    E[espera] = (g/c)*0 + (r/c)*(r/2) = r^2 / (2c)

Note que a espera cresce com o QUADRADO do vermelho: dobrar o vermelho
mantendo o ciclo quadruplica a espera media. E por isso que onda verde importa.

HIPOTESE DE CHEGADA UNIFORME. Vale quando os semaforos nao estao coordenados
entre si, que e o caso aqui. Havendo onda verde, as chegadas deixam de ser
uniformes e a formula superestima -- o que, para roteamento, e o lado seguro
do erro (ver ESTIMATIVA_CONSERVADORA no modulo).
"""

VERMELHO_PADRAO = 30.0
CICLO_PADRAO = 60.0


class TemporizacaoInvalida(ValueError):
    pass


def espera_media(vermelho, ciclo):
    """Atraso esperado, em segundos, num cruzamento semaforizado.

    E[espera] = vermelho^2 / (2 * ciclo)
    """
    if ciclo <= 0:
        raise TemporizacaoInvalida(f"ciclo deve ser positivo: {ciclo}")
    if vermelho < 0:
        raise TemporizacaoInvalida(f"vermelho nao pode ser negativo: {vermelho}")
    if vermelho > ciclo:
        raise TemporizacaoInvalida(
            f"vermelho ({vermelho}s) nao pode exceder o ciclo ({ciclo}s)"
        )
    return (vermelho ** 2) / (2.0 * ciclo)


def espera_maxima(vermelho):
    """Pior caso: chegar no instante exato em que o sinal fecha."""
    return float(vermelho)


def proporcao_de_verde(vermelho, ciclo):
    """Fracao do ciclo em que o cruzamento esta liberado."""
    if ciclo <= 0:
        raise TemporizacaoInvalida(f"ciclo deve ser positivo: {ciclo}")
    return max(0.0, (ciclo - vermelho) / ciclo)


class Semaforo:
    """Temporizacao de um cruzamento."""

    __slots__ = ("vermelho", "ciclo")

    def __init__(self, vermelho=VERMELHO_PADRAO, ciclo=CICLO_PADRAO):
        espera_media(vermelho, ciclo)      # valida na construcao
        self.vermelho = float(vermelho)
        self.ciclo = float(ciclo)

    @property
    def verde(self):
        return self.ciclo - self.vermelho

    @property
    def atraso(self):
        return espera_media(self.vermelho, self.ciclo)

    def __repr__(self):
        return (f"Semaforo(vermelho={self.vermelho:g}s, ciclo={self.ciclo:g}s, "
                f"atraso={self.atraso:.1f}s)")

    def __eq__(self, outro):
        return (isinstance(outro, Semaforo)
                and self.vermelho == outro.vermelho and self.ciclo == outro.ciclo)
