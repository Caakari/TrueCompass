"""Gera uma cidade sintetica para demonstracao e testes.

Malha estilo Manhattan: ruas de mao unica com sentidos alternados,
avenidas de mao dupla mais rapidas a cada 5 quarteiroes, e um rio que
corta a cidade com apenas duas pontes.

O rio existe de proposito: ele cria o caso em que a distancia em linha
reta MENTE. Um motorista a 300 m do passageiro, mas do outro lado do rio,
pode estar a 10 minutos de carro. E isso que o Dijkstra reverso corrige
e a quadtree sozinha nao enxerga.
"""

import random

from .grafo import Grafo, haversine

VELOCIDADE_RUA_KMH = 30.0
VELOCIDADE_AVENIDA_KMH = 50.0
VELOCIDADE_MAX_KMH = VELOCIDADE_AVENIDA_KMH  # usada pela heuristica do A*


# Identificador de no e INTEIRO, igual ao do OpenStreetMap. A cidade sintetica
# obedece ao contrato da fonte de producao, e nao o contrario: assim o mesmo
# codigo (e o mesmo schema de banco) serve para as duas malhas.
PASSO_ID = 10_000


def no_da_celula(i, j):
    """(linha, coluna) -> id inteiro do cruzamento."""
    return i * PASSO_ID + j


_no = no_da_celula


def construir_cidade(lado=40, espacamento_graus=0.0009, lat0=-23.5500, lon0=-46.6400,
                     coluna_do_rio=None, linhas_das_pontes=None):
    """Monta a malha viaria. `lado` x `lado` cruzamentos."""
    if coluna_do_rio is None:
        coluna_do_rio = lado // 2
    if linhas_das_pontes is None:
        linhas_das_pontes = {lado // 6, (5 * lado) // 6}

    # As bordas sao avenidas de mao dupla (um "anel viario"): sem isso, o
    # padrao alternado deixa cruzamentos de canto sem nenhuma entrada.
    grafo = Grafo()
    for i in range(lado):
        for j in range(lado):
            grafo.adicionar_no(_no(i, j), lat0 + i * espacamento_graus,
                               lon0 + j * espacamento_graus)

    def ligar(a, b, kmh, mao_dupla):
        lat1, lon1 = grafo.coordenadas(a)
        lat2, lon2 = grafo.coordenadas(b)
        segundos = haversine(lat1, lon1, lat2, lon2) / (kmh / 3.6)
        if mao_dupla:
            grafo.adicionar_rua_mao_dupla(a, b, segundos)
        else:
            grafo.adicionar_aresta(a, b, segundos)

    for i in range(lado):
        for j in range(lado):
            # ---- ruas horizontais (variando j)
            if j + 1 < lado:
                atravessa_rio = (j + 1 == coluna_do_rio) and (i not in linhas_das_pontes)
                if not atravessa_rio:
                    if i % 5 == 0 or i == lado - 1:     # avenida: mao dupla, rapida
                        ligar(_no(i, j), _no(i, j + 1), VELOCIDADE_AVENIDA_KMH, True)
                    elif i % 2 == 0:                    # rua de mao unica: para leste
                        ligar(_no(i, j), _no(i, j + 1), VELOCIDADE_RUA_KMH, False)
                    else:                               # rua de mao unica: para oeste
                        ligar(_no(i, j + 1), _no(i, j), VELOCIDADE_RUA_KMH, False)

            # ---- ruas verticais (variando i)
            if i + 1 < lado:
                if j % 5 == 0 or j == lado - 1:
                    ligar(_no(i, j), _no(i + 1, j), VELOCIDADE_AVENIDA_KMH, True)
                elif j % 2 == 0:
                    ligar(_no(i, j), _no(i + 1, j), VELOCIDADE_RUA_KMH, False)
                else:
                    ligar(_no(i + 1, j), _no(i, j), VELOCIDADE_RUA_KMH, False)

    return grafo


def sortear_motoristas(lado, quantidade, semente=42, centro=None, raio_celulas=None):
    """Simula o que a quadtree entregaria: k candidatos perto do passageiro."""
    rng = random.Random(semente)
    motoristas = {}
    tentativas = 0
    while len(motoristas) < quantidade and tentativas < quantidade * 200:
        tentativas += 1
        if centro is None:
            i, j = rng.randrange(lado), rng.randrange(lado)
        else:
            ci, cj = centro
            i = ci + rng.randint(-raio_celulas, raio_celulas)
            j = cj + rng.randint(-raio_celulas, raio_celulas)
            if not (0 <= i < lado and 0 <= j < lado):
                continue
        motoristas[f"motorista_{len(motoristas):02d}"] = _no(i, j)
    return motoristas
