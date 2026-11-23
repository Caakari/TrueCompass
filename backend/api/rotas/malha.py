# -*- coding: utf-8 -*-
"""Geometria da malha viaria, para o front-end desenhar.

Sem este endpoint o mapa dependeria de tiles externos (tile.openstreetmap.org)
e nao mostraria nada do grafo que realmente usamos. Servindo os trechos daqui,
o front desenha a MALHA DE VERDADE -- da para ver mao unica, o rio e as pontes,
e a rota calculada sobre as ruas que o algoritmo enxerga.

Nao exige autenticacao: e geometria derivada de dado publico do OpenStreetMap,
sem qualquer informacao de usuario.
"""

import statistics

from fastapi import APIRouter, Depends, Query
from starlette.requests import HTTPConnection

from algoritmos.contracao import Geometria
from api.deps import obter_geometria, obter_grafo, obter_indice_nos, obter_matriz

rotas = APIRouter(prefix="/malha", tags=["malha"])

LIMITE_MAXIMO = 20_000
_SEM_GEOMETRIA = Geometria()


def resumo_da_malha(grafo):
    """Caixa envolvente, centro e tamanho. O(V): calculado UMA vez no boot."""
    latitudes, longitudes = [], []
    for no in grafo.nos:
        lat, lon = grafo.coordenadas(no)
        latitudes.append(lat)
        longitudes.append(lon)
    if not latitudes:
        return {"nos": 0, "arestas": 0, "caixa": None}
    return {
        "nos": len(latitudes),
        "arestas": grafo.total_arestas(),
        "caixa": {"sul": min(latitudes), "norte": max(latitudes),
                  "oeste": min(longitudes), "leste": max(longitudes)},
        # MEDIANA dos nos, e nao o meio da caixa: na cidade inteira o meio da
        # caixa cai na zona sul (a cidade se estende ate Marsilac), enquanto a
        # mediana fica onde esta a maior parte das ruas.
        "centro": {"lat": statistics.median(latitudes),
                   "lon": statistics.median(longitudes)},
    }


@rotas.get("/info")
def info(conexao: HTTPConnection, grafo=Depends(obter_grafo)):
    """Caixa envolvente e tamanho da malha: o front centraliza o mapa com isso."""
    resumo = getattr(conexao.app.state, "resumo_malha", None)
    return resumo if resumo is not None else resumo_da_malha(grafo)


@rotas.get("/semaforos")
def semaforos(conexao: HTTPConnection):
    """Cruzamentos semaforizados, para o front desenhar.

    Lista montada no boot: da matriz, ou dos nos `highway=traffic_signals` do
    OpenStreetMap. Nao sai do grafo porque o atraso ja foi absorvido pelos
    pesos das arestas e nao e mais recuperavel a partir deles.
    """
    lista = getattr(conexao.app.state, "semaforos", [])
    fonte = "matriz" if obter_matriz(conexao) is not None else "openstreetmap"
    return {"semaforos": lista, "total": len(lista), "fonte": fonte}


@rotas.get("/trechos")
def trechos(sul: float = Query(-90), oeste: float = Query(-180),
            norte: float = Query(90), leste: float = Query(180),
            limite: int = Query(6000, ge=1, le=LIMITE_MAXIMO),
            grafo=Depends(obter_grafo),
            indice_nos=Depends(obter_indice_nos),
            geometria=Depends(obter_geometria)):
    """Trechos de rua dentro da caixa, em formato compacto.

    Cada trecho e [lat1, lon1, lat2, lon2, mao_unica], com mao_unica em 0 ou 1.
    Lista, e nao objeto, para reduzir o tamanho da resposta -- numa malha real
    sao milhares de segmentos, e nome de campo repetido dominaria o payload.

    Os nos da janela vem da QUADTREE, e nao de uma varredura da malha: na
    cidade inteira, varrer todos os nos a cada arrastar do mapa custaria O(V)
    por requisicao. A aresta contraida e expandida no tracado real da rua,
    entao o desenho mostra as curvas, e nao a corda entre cruzamentos.

    Trechos de mao dupla sao emitidos UMA vez, evitando desenhar a mesma rua
    duas vezes sobrepostas. Aresta que sai da janela e desenhada a partir da
    ponta de dentro, para a rua nao sumir na borda.
    """
    geometria = geometria or _SEM_GEOMETRIA
    dentro = set(indice_nos.no_retangulo(sul, oeste, norte, leste))

    saida = []
    truncado = False
    for origem in dentro:
        for destino, _peso in grafo.vizinhos(origem):
            volta_existe = origem in dict(grafo.vizinhos(destino))
            mesma_rua = volta_existe and geometria.mesmo_tracado(origem, destino)
            # Mao dupla: emite so um sentido, para nao sobrepor a linha.
            if mesma_rua and destino in dentro and not (origem < destino):
                continue
            pontos = geometria.tracado(grafo, [origem, destino])
            if len(saida) + len(pontos) - 1 > limite:
                truncado = True
                break
            mao = 0 if mesma_rua else 1
            for (lat1, lon1), (lat2, lon2) in zip(pontos, pontos[1:]):
                saida.append([round(lat1, 6), round(lon1, 6),
                              round(lat2, 6), round(lon2, 6), mao])
        if truncado:
            break

    return {"trechos": saida, "total": len(saida), "truncado": truncado}
