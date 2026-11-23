# -*- coding: utf-8 -*-
"""Pre-calcula os marcos do ALT e grava o artefato.

Roda UMA vez, offline, depois de importar a malha:

    python3 -m infra.preparar_alt
    python3 -m infra.preparar_alt --marcos 24 --saida dados/alt.bin

(de dentro de backend/)

O servidor le o arquivo no boot. Sem ele, o A* cai na heuristica haversine --
correto, porem com muito menos poda.
"""

import argparse
import os
import random
import time

from algoritmos.alt import ALT
from algoritmos.busca import busca_caminho_minimo
from algoritmos.grafo import heuristica_haversine


def carregar_grafo_do_projeto(config):
    """Mesma ordem de preferencia do servidor: artefato OSM, depois matriz.

    A ordem tem de ser identica a de `api.main.carregar_malha`: marcos gerados
    para outro mapa falham na impressao digital e o servidor os descarta.
    """
    if config.arquivo_malha and os.path.exists(config.arquivo_malha):
        from infra.osm import carregar_grafo
        return carregar_grafo(config.arquivo_malha), config.arquivo_malha
    if config.arquivo_matriz and os.path.exists(config.arquivo_matriz):
        from algoritmos.matriz_mapa import MatrizMapa
        with open(config.arquivo_matriz, encoding="utf-8") as arquivo:
            matriz = MatrizMapa.de_texto(arquivo.read())
        return (matriz.para_grafo(considerar_semaforos=config.considerar_semaforos),
                config.arquivo_matriz)
    raise SystemExit("nenhum mapa encontrado: gere a malha antes")


def medir(grafo, alt, pares=25, semente=11):
    """Compara A*+ALT com A*+haversine e com Dijkstra, nos mesmos pares."""
    rng = random.Random(semente)
    nos = sorted(grafo.nos)
    totais = {"Dijkstra": 0, "A* haversine": 0, "A* ALT": 0}
    tempos = {"A* haversine": 0.0, "A* ALT": 0.0}
    divergencias = usados = 0

    for _ in range(pares):
        origem, destino = rng.sample(nos, 2)
        base = busca_caminho_minimo(grafo, origem, {destino})
        if destino not in base.custos:
            continue
        usados += 1
        totais["Dijkstra"] += base.nos_expandidos

        inicio = time.perf_counter()
        hav = busca_caminho_minimo(grafo, origem, {destino},
                                   h=heuristica_haversine(grafo, destino))
        tempos["A* haversine"] += time.perf_counter() - inicio
        totais["A* haversine"] += hav.nos_expandidos

        inicio = time.perf_counter()
        com_alt = busca_caminho_minimo(grafo, origem, {destino},
                                       h=alt.heuristica(destino, origem=origem))
        tempos["A* ALT"] += time.perf_counter() - inicio
        totais["A* ALT"] += com_alt.nos_expandidos

        if com_alt.custos[destino] > base.custos[destino] * (1 + 1e-9):
            divergencias += 1

    return totais, tempos, divergencias, usados


def main():
    ap = argparse.ArgumentParser(description="Pre-calcula os marcos do ALT")
    ap.add_argument("--marcos", type=int, default=16,
                    help="quantidade de marcos (padrao 16)")
    ap.add_argument("--ativos", type=int, default=4,
                    help="marcos avaliados por consulta (padrao 4)")
    ap.add_argument("--saida", default=None,
                    help="arquivo de saida (padrao: onde o servidor procura)")
    ap.add_argument("--sem-medicao", action="store_true")
    args = ap.parse_args()

    from infra.config import obter_config
    config = obter_config()
    args.saida = args.saida or config.arquivo_alt
    grafo, fonte = carregar_grafo_do_projeto(config)
    print(f"mapa: {fonte} ({len(grafo.nos):,} nos, {grafo.total_arestas():,} arestas)")

    inicio = time.perf_counter()
    alt = ALT.construir(
        grafo, quantidade=args.marcos, ativos=args.ativos,
        relatar=lambda i, n, _m: print(f"  marco {i}/{n}", end="\r", flush=True),
    )
    print(f"  {len(alt)} marcos em {time.perf_counter() - inicio:.1f}s" + " " * 12)

    os.makedirs(os.path.dirname(args.saida) or ".", exist_ok=True)
    alt.salvar(args.saida)
    print(f"artefato: {args.saida} "
          f"({os.path.getsize(args.saida) / 1_048_576:.1f} MB)")

    if args.sem_medicao:
        return
    print("\nmedindo...")
    totais, tempos, divergencias, usados = medir(grafo, alt)
    base = max(totais["Dijkstra"], 1)
    print(f"\n{usados} pares origem-destino:")
    print(f"  {'':<16}{'nos expandidos':>16}{'ganho':>9}{'tempo':>11}")
    for nome, valor in totais.items():
        tempo = tempos.get(nome)
        coluna = f"{tempo * 1000:>9.0f}ms" if tempo else f"{'':>11}"
        print(f"  {nome:<16}{valor:>16,}{base / max(valor, 1):>8.1f}x{coluna}")
    print(f"\n  rotas subotimas: {divergencias} (tem de ser 0)")


if __name__ == "__main__":
    main()
