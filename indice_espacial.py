# -*- coding: utf-8 -*-
"""Indice espacial: filtro geografico barato antes da busca em grafo.

Duas implementacoes da MESMA interface -- `inserir`, `remover`, `reconstruir`,
`proximos`, `mais_proximo`:

  - `Quadtree` (algoritmos/quadtree.py): a de producao, O(log n).
  - `IndiceLinear` (aqui): varredura O(n), mantida como ORACULO dos testes.

A linear nao e codigo morto: e o gabarito que prova a quadtree correta, do
mesmo jeito que o Dijkstra prova o A*. Uma implementacao obviamente correta
vale mais como referencia do que como otimizacao.

O contrato: `proximos` devolve candidatos dentro do raio, ordenados por
distancia em linha reta. E so um FILTRO. Quem decide quem chega antes e a
busca reversa no grafo, porque linha reta mente -- rio, mao unica e via
expressa nao aparecem na distancia euclidiana.
"""

from algoritmos.grafo import haversine


class IndiceLinear:
    """Varredura completa. Correta por construcao; usada como oraculo."""

    def __init__(self, pontos=None):
        self._pontos = dict(pontos or {})

    def inserir(self, identificador, lat, lon):
        self._pontos[identificador] = (lat, lon)

    def remover(self, identificador):
        self._pontos.pop(identificador, None)

    def reconstruir(self, pontos):
        self._pontos = dict(pontos)

    def proximos(self, lat, lon, raio_m, limite=None):
        """Candidatos dentro do raio, do mais perto ao mais longe."""
        encontrados = []
        for identificador, (plat, plon) in self._pontos.items():
            metros = haversine(lat, lon, plat, plon)
            if metros <= raio_m:
                encontrados.append((metros, identificador))
        encontrados.sort()
        if limite:
            encontrados = encontrados[:limite]
        return [identificador for _, identificador in encontrados]

    def mais_proximo(self, lat, lon):
        """Um unico ponto: usado para ancorar coordenada GPS ao cruzamento."""
        if not self._pontos:
            return None
        return min(
            self._pontos,
            key=lambda i: haversine(lat, lon, *self._pontos[i]),
        )

    def __len__(self):
        return len(self._pontos)


def indice_dos_nos(grafo):
    """Indice sobre os cruzamentos da malha, para ancorar coordenadas GPS.

    Numa malha real do OpenStreetMap sao dezenas de milhares de cruzamentos, e
    ancorar por varredura custaria O(V) a cada ping de GPS. Com a quadtree, a
    ancoragem fica O(log V).
    """
    from algoritmos.quadtree import Quadtree
    return Quadtree({no: grafo.coordenadas(no) for no in grafo.nos})
