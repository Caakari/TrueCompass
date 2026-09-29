# -*- coding: utf-8 -*-
"""Quadtree para indexacao espacial.

Referencia: Documentacao_Tecnica secao 3. Cada no interno tem exatamente
quatro filhos (NE, NO, SE, SO); cada folha guarda ate `capacidade` pontos e
se subdivide ao estourar.

O ganho vem da PODA: um ramo cujo retangulo nao intersecta o circulo de busca
e descartado inteiro, sem olhar um unico ponto la dentro. Busca linear compara
com todos os n motoristas; a quadtree visita O(log n) nos em distribuicao
uniforme -- a recorrencia T(n) = T(n/4) + O(1) da secao 6 da documentacao.

Implementa a mesma interface de `IndiceLinear`, que permanece no projeto como
ORACULO: os testes conferem, ponto a ponto, que as duas devolvem o mesmo
conjunto. Mesma estrategia com que o Dijkstra valida o A*.
"""

import heapq
from math import cos, radians

from algoritmos.grafo import haversine

# Extensao de um grau de latitude, em metros. Praticamente constante.
METROS_POR_GRAU_LAT = 111_320.0

# O ponto do retangulo mais proximo em GRAUS e, para extensoes urbanas, o mais
# proximo em METROS. A rigor cos(latitude) varia dentro do retangulo, entao
# usamos uma folga ao podar: melhor visitar um ramo a mais do que descartar um
# ramo que continha resultado.
FOLGA_PODA = 1.01


class Retangulo:
    """Regiao retangular em coordenadas geograficas."""

    __slots__ = ("lat_min", "lat_max", "lon_min", "lon_max")

    def __init__(self, lat_min, lat_max, lon_min, lon_max):
        self.lat_min, self.lat_max = lat_min, lat_max
        self.lon_min, self.lon_max = lon_min, lon_max

    def contem(self, lat, lon):
        return (self.lat_min <= lat <= self.lat_max
                and self.lon_min <= lon <= self.lon_max)

    def quadrantes(self):
        """Subdivide em NO, NE, SO, SE."""
        lat_meio = (self.lat_min + self.lat_max) / 2
        lon_meio = (self.lon_min + self.lon_max) / 2
        return (
            Retangulo(lat_meio, self.lat_max, self.lon_min, lon_meio),   # NO
            Retangulo(lat_meio, self.lat_max, lon_meio, self.lon_max),   # NE
            Retangulo(self.lat_min, lat_meio, self.lon_min, lon_meio),   # SO
            Retangulo(self.lat_min, lat_meio, lon_meio, self.lon_max),   # SE
        )

    def distancia_minima_m(self, lat, lon):
        """Distancia, em metros, ate o ponto mais proximo deste retangulo.

        Zero se o ponto esta dentro. E o limite inferior que autoriza a poda:
        se ele ja excede o raio, nenhum ponto aqui dentro pode servir.
        """
        lat_proxima = min(max(lat, self.lat_min), self.lat_max)
        lon_proxima = min(max(lon, self.lon_min), self.lon_max)
        return haversine(lat, lon, lat_proxima, lon_proxima)

    def __repr__(self):
        return (f"Retangulo({self.lat_min:.5f}..{self.lat_max:.5f}, "
                f"{self.lon_min:.5f}..{self.lon_max:.5f})")


def _envolver(pontos, folga_graus=1e-4):
    """Retangulo que contem todos os pontos, com uma folga nas bordas."""
    if not pontos:
        return Retangulo(-1e-3, 1e-3, -1e-3, 1e-3)
    lats = [lat for lat, _ in pontos.values()]
    lons = [lon for _, lon in pontos.values()]
    return Retangulo(min(lats) - folga_graus, max(lats) + folga_graus,
                     min(lons) - folga_graus, max(lons) + folga_graus)


class _No:
    """No da arvore: folha com pontos, ou interno com quatro filhos."""

    __slots__ = ("retangulo", "pontos", "filhos", "profundidade")

    def __init__(self, retangulo, profundidade=0):
        self.retangulo = retangulo
        self.pontos = {}        # identificador -> (lat, lon)
        self.filhos = None
        self.profundidade = profundidade

    @property
    def e_folha(self):
        return self.filhos is None

    def inserir(self, identificador, lat, lon, capacidade, profundidade_max):
        if not self.e_folha:
            self._filho_de(lat, lon).inserir(identificador, lat, lon,
                                             capacidade, profundidade_max)
            return

        self.pontos[identificador] = (lat, lon)

        # Subdivide ao estourar -- desde que ainda faca sentido. Sem o teto de
        # profundidade, um punhado de pontos na MESMA coordenada subdividiria
        # para sempre, porque nenhuma divisao os separa.
        if len(self.pontos) > capacidade and self.profundidade < profundidade_max:
            self._subdividir(capacidade, profundidade_max)

    def _subdividir(self, capacidade, profundidade_max):
        self.filhos = [_No(r, self.profundidade + 1)
                       for r in self.retangulo.quadrantes()]
        pendentes, self.pontos = self.pontos, {}
        for identificador, (lat, lon) in pendentes.items():
            self._filho_de(lat, lon).inserir(identificador, lat, lon,
                                             capacidade, profundidade_max)

    def _filho_de(self, lat, lon):
        """Quadrante que abriga a coordenada.

        A borda entre quadrantes e resolvida por `contem`, que e inclusiva; o
        ultimo filho serve de rede para erro de arredondamento na fronteira.
        """
        for filho in self.filhos:
            if filho.retangulo.contem(lat, lon):
                return filho
        return self.filhos[-1]


class Quadtree:
    """Indice espacial com a mesma interface de `IndiceLinear`."""

    def __init__(self, pontos=None, capacidade=8, profundidade_max=24):
        self.capacidade = capacidade
        self.profundidade_max = profundidade_max
        self._todos = {}
        self._raiz = None
        self.nos_visitados = 0      # instrumentacao para os benchmarks
        self.reconstruir(dict(pontos or {}))

    # ------------------------------------------------------------- escrita

    def reconstruir(self, pontos):
        """Recria a arvore do zero, em O(n log n).

        E a operacao preferida sobre atualizacao incremental: com motoristas
        se movendo o tempo todo, reconstruir periodicamente e mais simples e,
        para alguns milhares de pontos, barato.
        """
        self._todos = dict(pontos)
        self._raiz = _No(_envolver(self._todos))
        for identificador, (lat, lon) in self._todos.items():
            self._raiz.inserir(identificador, lat, lon,
                               self.capacidade, self.profundidade_max)

    def inserir(self, identificador, lat, lon):
        ja_conhecido = identificador in self._todos
        self._todos[identificador] = (lat, lon)

        # Reinsercao ou ponto fora da area coberta exigem reconstruir: a
        # arvore nao cresce alem da raiz, e um ponto antigo ficaria duplicado.
        if ja_conhecido or not self._raiz.retangulo.contem(lat, lon):
            self.reconstruir(self._todos)
        else:
            self._raiz.inserir(identificador, lat, lon,
                               self.capacidade, self.profundidade_max)

    def remover(self, identificador):
        if self._todos.pop(identificador, None) is not None:
            self.reconstruir(self._todos)

    # ------------------------------------------------------------- consulta

    def proximos(self, lat, lon, raio_m, limite=None):
        """Pontos dentro do raio, do mais proximo ao mais distante."""
        self.nos_visitados = 0
        encontrados = []
        pilha = [self._raiz]
        limite_poda = raio_m * FOLGA_PODA

        while pilha:
            no = pilha.pop()
            self.nos_visitados += 1

            # A PODA: ramo inteiro descartado sem olhar ponto nenhum.
            if no.retangulo.distancia_minima_m(lat, lon) > limite_poda:
                continue

            if no.e_folha:
                for identificador, (plat, plon) in no.pontos.items():
                    metros = haversine(lat, lon, plat, plon)
                    if metros <= raio_m:
                        encontrados.append((metros, identificador))
            else:
                pilha.extend(no.filhos)

        encontrados.sort()
        if limite:
            encontrados = encontrados[:limite]
        return [identificador for _, identificador in encontrados]

    def mais_proximo(self, lat, lon):
        """Vizinho mais proximo, por busca best-first com poda.

        A fila entrega sempre o ramo cujo retangulo esta mais perto. Quando o
        topo da fila for um PONTO, e nao um ramo, ele e o mais proximo: nenhum
        ramo ainda na fila pode conter algo melhor.
        """
        self.nos_visitados = 0
        if not self._todos:
            return None

        contador = 0
        fila = [(self._raiz.retangulo.distancia_minima_m(lat, lon), 0,
                 contador, self._raiz)]

        while fila:
            _distancia, tipo, _ordem, item = heapq.heappop(fila)
            if tipo == 1:               # e um ponto: resposta final
                return item
            self.nos_visitados += 1

            if item.e_folha:
                for identificador, (plat, plon) in item.pontos.items():
                    contador += 1
                    heapq.heappush(fila, (haversine(lat, lon, plat, plon), 1,
                                          contador, identificador))
            else:
                for filho in item.filhos:
                    contador += 1
                    heapq.heappush(
                        fila,
                        (filho.retangulo.distancia_minima_m(lat, lon), 0,
                         contador, filho),
                    )
        return None

    # ----------------------------------------------------------- inspecao

    def altura(self):
        def medir(no):
            return 1 if no.e_folha else 1 + max(medir(f) for f in no.filhos)
        return medir(self._raiz)

    def total_nos(self):
        def contar(no):
            return 1 if no.e_folha else 1 + sum(contar(f) for f in no.filhos)
        return contar(self._raiz)

    def __len__(self):
        return len(self._todos)

    def __contains__(self, identificador):
        return identificador in self._todos


def raio_para_graus(raio_m, lat):
    """Conversao auxiliar metros -> graus, util para montar caixas de busca."""
    delta_lat = raio_m / METROS_POR_GRAU_LAT
    delta_lon = raio_m / (METROS_POR_GRAU_LAT * max(cos(radians(lat)), 1e-6))
    return delta_lat, delta_lon
