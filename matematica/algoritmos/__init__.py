"""Camada de algoritmos do TrueCompass.

Tres modulos, conforme a secao 7 da documentacao tecnica:
  - grafo.py     : malha viaria, grafo reverso, heuristica haversine
  - busca.py     : Dijkstra e A* unificados numa unica rotina
  - matching.py  : busca reversa many-to-one para achar o motorista
"""

from .busca import Resultado, busca_caminho_minimo, caminho_ate_origem, reconstruir_caminho
from .grafo import Grafo, haversine, heuristica_haversine
from .matching import Candidato, motoristas_mais_proximos, motoristas_mais_proximos_ingenuo

__all__ = [
    "Grafo", "haversine", "heuristica_haversine",
    "busca_caminho_minimo", "reconstruir_caminho", "caminho_ate_origem", "Resultado",
    "motoristas_mais_proximos", "motoristas_mais_proximos_ingenuo", "Candidato",
]
