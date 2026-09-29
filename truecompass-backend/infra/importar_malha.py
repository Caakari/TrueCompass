# -*- coding: utf-8 -*-
"""Importa uma area real do OpenStreetMap e gera o artefato da malha.

    python3 -m infra.importar_malha --sul -23.560 --oeste -46.600 \
                                    --norte -23.540 --leste -46.570

Roda UMA vez, offline, e versiona a saida. O servidor nunca consulta a
Overpass no boot: ele le o JSON gerado aqui, que sobe em fracoes de segundo.
"""

import argparse
import os
import time

from algoritmos.busca import busca_caminho_minimo
from infra.osm import (baixar_osm, construir_grafo,
                       maior_componente_fortemente_conexo, salvar_grafo)


def estatisticas(grafo):
    """Numeros para o relatorio: tamanho, direcionalidade e conectividade."""
    total_nos = len(grafo.nos)
    total_arestas = grafo.total_arestas()
    mao_unica = sum(
        1 for o in grafo.nos for d, _ in grafo.vizinhos(o)
        if o not in dict(grafo.vizinhos(d))
    )
    graus = [len(dict(grafo.vizinhos(no))) for no in grafo.nos]
    return {
        "nos": total_nos,
        "arestas": total_arestas,
        "arestas_mao_unica": mao_unica,
        "percentual_mao_unica": 100.0 * mao_unica / total_arestas if total_arestas else 0.0,
        "grau_medio": sum(graus) / total_nos if total_nos else 0.0,
    }


def main():
    ap = argparse.ArgumentParser(description="Importa malha viaria do OpenStreetMap")
    ap.add_argument("--sul", type=float, required=True)
    ap.add_argument("--oeste", type=float, required=True)
    ap.add_argument("--norte", type=float, required=True)
    ap.add_argument("--leste", type=float, required=True)
    ap.add_argument("--cache", default="dados/osm_bruto.json",
                    help="onde guardar o extrato cru da Overpass")
    ap.add_argument("--saida", default="dados/malha.json",
                    help="artefato final, lido pelo servidor no boot")
    args = ap.parse_args()

    if args.sul >= args.norte or args.oeste >= args.leste:
        ap.error("caixa invalida: exige sul < norte e oeste < leste")

    os.makedirs(os.path.dirname(args.saida) or ".", exist_ok=True)

    print(f"Baixando ({args.sul}, {args.oeste}) .. ({args.norte}, {args.leste})")
    inicio = time.perf_counter()
    dados = baixar_osm(args.sul, args.oeste, args.norte, args.leste, cache=args.cache)
    print(f"  {len(dados.get('elements', [])):,} elementos "
          f"em {time.perf_counter() - inicio:.1f}s")

    bruto = construir_grafo(dados)
    antes = estatisticas(bruto)
    print(f"Grafo bruto:  {antes['nos']:,} nos, {antes['arestas']:,} arestas")

    podado = maior_componente_fortemente_conexo(bruto)
    depois = estatisticas(podado)
    descartados = antes["nos"] - depois["nos"]
    print(f"Apos a poda:  {depois['nos']:,} nos, {depois['arestas']:,} arestas "
          f"({descartados:,} nos descartados, "
          f"{100.0 * descartados / antes['nos']:.1f}%)")
    print(f"  mao unica:  {depois['percentual_mao_unica']:.1f}% das arestas")
    print(f"  grau medio: {depois['grau_medio']:.2f}")

    # Sanidade: a malha podada tem de ser fortemente conexa de verdade.
    semente = next(iter(podado.nos))
    alcancados = len(busca_caminho_minimo(podado, semente, alvos=set()).distancias)
    assert alcancados == len(podado.nos), (
        f"poda falhou: {semente} alcanca {alcancados} de {len(podado.nos)} nos"
    )
    print("  verificado: malha fortemente conexa")

    salvar_grafo(podado, args.saida)
    print(f"Artefato: {args.saida} "
          f"({os.path.getsize(args.saida) / 1_048_576:.1f} MB)")


if __name__ == "__main__":
    main()
