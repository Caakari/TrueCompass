# -*- coding: utf-8 -*-
"""Importa uma area real do OpenStreetMap e gera o artefato da malha.

    # Municipio de Sao Paulo inteiro (padrao), baixado em blocos:
    python3 -m infra.importar_malha --municipio-sp

    # Uma caixa qualquer:
    python3 -m infra.importar_malha --sul -23.560 --oeste -46.600 \
                                    --norte -23.540 --leste -46.570

    # Sem rede: so contrai um artefato antigo (versao 1):
    python3 -m infra.importar_malha --reprocessar dados/malha.json

    # De um extrato .osm.pbf (quando a Overpass recusa o datacenter), com o
    # contorno do municipio baixado do Nominatim na primeira vez:
    pip install -r requirements-importacao.txt
    python3 -m infra.importar_malha --pbf dados/osm_bruto/sao-paulo-latest.osm.pbf

Roda UMA vez, offline, e versiona a saida. O servidor nunca consulta a
Overpass no boot: ele le o arquivo gerado aqui.

Etapas: download (em blocos) -> grafo -> poda ao componente fortemente
conexo -> CONTRACAO dos nos de passagem -> artefato comprimido.
"""

import argparse
import os
import time

from matematica_no_caminho import PASTA_BACKEND  # antes de `algoritmos`
from algoritmos.busca import busca_caminho_minimo
from algoritmos.contracao import LIMITE_PADRAO_M, contrair
from infra.osm import (AREA_MUNICIPIO_SP, SEMAFORO_OSM, baixar_osm, blocos,
                       construir_grafo, ids_dos_semaforos, juntar_extratos,
                       ler_artefato, maior_componente_fortemente_conexo,
                       salvar_grafo, semaforos_do_osm)

# Caixa envolvente do municipio de Sao Paulo (de Perus a Marsilac). O recorte
# fino e o da AREA administrativa; a caixa so organiza os blocos.
CAIXA_MUNICIPIO_SP = (-24.010, -46.830, -23.355, -46.360)
GRADE_MUNICIPIO_SP = (4, 3)    # blocos de ~18 x 16 km


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


def baixar_em_blocos(caixa, grade, pasta_cache, area=None):
    """Um extrato por bloco, cada um com cache proprio: se o 9o bloco falhar,
    rodar de novo nao baixa os 8 primeiros outra vez."""
    os.makedirs(pasta_cache, exist_ok=True)
    extratos = []
    lista = blocos(*caixa, *grade)
    for numero, (sul, oeste, norte, leste) in enumerate(lista, 1):
        cache = os.path.join(pasta_cache, f"bloco_{numero:02d}.json")
        inicio = time.perf_counter()
        dados = baixar_osm(sul, oeste, norte, leste, cache=cache, area=area)
        print(f"  bloco {numero:2d}/{len(lista)}: {len(dados.get('elements', [])):>9,} "
              f"elementos ({time.perf_counter() - inicio:5.1f}s)")
        extratos.append(dados)
    return juntar_extratos(extratos)


def contrair_e_relatar(grafo, sinais, limite_m):
    inicio = time.perf_counter()
    contraido, geometria = contrair(grafo, preservar=sinais, limite_m=limite_m)
    print(f"Contracao:    {len(contraido.nos):,} nos, {contraido.total_arestas():,} arestas "
          f"({100 * len(contraido.nos) / len(grafo.nos):.0f}% dos nos; "
          f"cadeias de ate {limite_m:.0f} m; {time.perf_counter() - inicio:.1f}s)")
    return contraido, geometria


def conferir_contracao(bruto, contraido, amostras=2, semente=7):
    """Oraculo no proprio artefato: Dijkstra completo nos dois grafos, a
    partir de algumas origens, tem de dar o MESMO custo para todo no mantido.
    Se a contracao errasse, o artefato nem seria gravado."""
    import random
    from math import isclose
    origens = random.Random(semente).sample(sorted(contraido.nos), amostras)
    inicio = time.perf_counter()
    for origem in origens:
        esperado = busca_caminho_minimo(bruto, origem, alvos=set()).distancias
        obtido = busca_caminho_minimo(contraido, origem, alvos=set()).distancias
        for no, custo in obtido.items():
            assert isclose(custo, esperado[no], abs_tol=1e-6), (
                f"contracao alterou o custo {origem}->{no}: {esperado[no]} != {custo}")
        assert len(obtido) == len(contraido.nos)
    print(f"  oraculo:    {amostras} origens x {len(contraido.nos):,} destinos, custos "
          f"identicos ao grafo sem contracao ({time.perf_counter() - inicio:.0f}s)")


def verificar_conexo(grafo):
    """Sanidade: a malha tem de ser fortemente conexa de verdade."""
    semente = next(iter(grafo.nos))
    ida = len(busca_caminho_minimo(grafo, semente, alvos=set()).distancias)
    volta = len(busca_caminho_minimo(grafo.reverso(), semente, alvos=set()).distancias)
    assert ida == volta == len(grafo.nos), (
        f"malha nao e fortemente conexa: {semente} alcanca {ida} e e alcancado "
        f"por {volta} de {len(grafo.nos)} nos")
    print("  verificado: malha fortemente conexa")


def main():
    ap = argparse.ArgumentParser(description="Importa malha viaria do OpenStreetMap")
    fonte = ap.add_mutually_exclusive_group()
    fonte.add_argument("--municipio-sp", action="store_true",
                       help="municipio de Sao Paulo inteiro, em blocos (padrao)")
    fonte.add_argument("--reprocessar", metavar="ARTEFATO",
                       help="nao baixa nada: so contrai um artefato existente")
    fonte.add_argument("--pbf", metavar="EXTRATO",
                       help="le um extrato .osm.pbf em vez de consultar a Overpass")
    ap.add_argument("--contorno", default=os.path.join(PASTA_BACKEND, "dados", "osm_bruto",
                                                       "municipio_sp.geojson"),
                    help="GeoJSON do municipio (com --pbf); baixado do Nominatim se faltar")
    ap.add_argument("--sul", type=float)
    ap.add_argument("--oeste", type=float)
    ap.add_argument("--norte", type=float)
    ap.add_argument("--leste", type=float)
    ap.add_argument("--cache", default=os.path.join(PASTA_BACKEND, "dados", "osm_bruto"),
                    help="pasta dos extratos crus da Overpass (um arquivo por bloco)")
    ap.add_argument("--saida", default=os.path.join(PASTA_BACKEND, "dados", "malha.json.gz"),
                    help="artefato final, lido pelo servidor no boot")
    ap.add_argument("--limite-m", type=float, default=LIMITE_PADRAO_M,
                    help="comprimento maximo de uma cadeia contraida")
    ap.add_argument("--sem-contrair", action="store_true",
                    help="mantem todos os nos (artefato muito maior)")
    args = ap.parse_args()

    os.makedirs(os.path.dirname(args.saida) or ".", exist_ok=True)

    if args.reprocessar:
        grafo, _semaforos, _geo = ler_artefato(args.reprocessar)
        ids = ids_dos_semaforos(args.reprocessar)
        print(f"Artefato:     {len(grafo.nos):,} nos, {grafo.total_arestas():,} arestas")
        contraido, geometria = contrair_e_relatar(grafo, ids, args.limite_m)
        conferir_contracao(grafo, contraido)
        verificar_conexo(contraido)
        sinais = {no: grafo.coordenadas(no) for no in ids if no in grafo.nos}
        salvar_grafo(contraido, args.saida, semaforos=sinais, geometria=geometria)
        print(f"Artefato: {args.saida} ({os.path.getsize(args.saida) / 1_048_576:.1f} MB)")
        return

    caixa_dada = None not in (args.sul, args.oeste, args.norte, args.leste)
    if args.pbf:
        from infra.pbf import baixar_contorno, extrair_vias, ler_contorno
        if not os.path.exists(args.contorno):
            os.makedirs(os.path.dirname(args.contorno) or ".", exist_ok=True)
            baixar_contorno(AREA_MUNICIPIO_SP - 3600000000, args.contorno)
            print(f"Contorno do municipio baixado do Nominatim: {args.contorno}")
        contorno = ler_contorno(args.contorno)
        print(f"Lendo {args.pbf} (recorte pelo contorno do municipio)")
        inicio = time.perf_counter()
        dados = extrair_vias(args.pbf, contorno, progresso=lambda n, s: print(
            f"  {n:>11,} objetos com highway lidos ({s:.0f}s)"))
        print(f"  {len(dados['elements']):,} elementos em {time.perf_counter() - inicio:.1f}s")
    elif caixa_dada:
        if args.sul >= args.norte or args.oeste >= args.leste:
            ap.error("caixa invalida: exige sul < norte e oeste < leste")
        caixa, grade, area = (args.sul, args.oeste, args.norte, args.leste), (1, 1), None
        print(f"Baixando ({args.sul}, {args.oeste}) .. ({args.norte}, {args.leste})")
    else:
        caixa, grade, area = CAIXA_MUNICIPIO_SP, GRADE_MUNICIPIO_SP, AREA_MUNICIPIO_SP
        print(f"Baixando o municipio de Sao Paulo em {grade[0] * grade[1]} blocos")

    if not args.pbf:
        inicio = time.perf_counter()
        dados = baixar_em_blocos(caixa, grade, args.cache, area=area)
        print(f"  {len(dados['elements']):,} elementos em {time.perf_counter() - inicio:.1f}s")

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

    sinais = semaforos_do_osm(dados)
    nos_podados = set(podado.nos)
    sinais = {no: coord for no, coord in sinais.items() if no in nos_podados}
    print(f"  semaforos:  {len(sinais):,} na malha "
          f"(+{SEMAFORO_OSM.atraso:.1f}s esperados em cada aresta que chega)")

    if args.sem_contrair:
        final, geometria = podado, None
    else:
        final, geometria = contrair_e_relatar(podado, set(sinais), args.limite_m)
        conferir_contracao(podado, final)
    verificar_conexo(final)

    salvar_grafo(final, args.saida, semaforos=sinais, geometria=geometria)
    print(f"Artefato: {args.saida} "
          f"({os.path.getsize(args.saida) / 1_048_576:.1f} MB)")


if __name__ == "__main__":
    main()
