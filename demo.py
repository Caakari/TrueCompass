"""Demonstracao comparativa: rode com  python3 -m algoritmos.demo

Mede as duas trocas propostas, no mesmo cenario:
  1. matching : k buscas completas  x  1 busca reversa many-to-one
  2. rota     : Dijkstra            x  A* com heuristica haversine
"""

import time
from math import inf, isclose

from .busca import busca_caminho_minimo, reconstruir_caminho
from .cidade_exemplo import (VELOCIDADE_MAX_KMH, construir_cidade,
                             no_da_celula, sortear_motoristas)
from .grafo import haversine, heuristica_haversine
from .indice_espacial import IndiceLinear
from .quadtree import Quadtree

LADO = 60
LIMITE_MATCHING_SEGUNDOS = 15 * 60


def cronometrar(funcao):
    inicio = time.perf_counter()
    valor = funcao()
    return valor, (time.perf_counter() - inicio) * 1000


def titulo(texto):
    print(f"\n{texto}\n" + "-" * len(texto))


def main():
    cidade = construir_cidade(lado=LADO)
    reverso = cidade.reverso()
    print(f"Cidade sintetica: {len(cidade.nos)} cruzamentos, "
          f"{cidade.total_arestas()} trechos de rua direcionados")

    # Passageiro encostado no rio (coluna LADO//2), do lado leste. Assim alguns
    # candidatos ficam a poucos metros em linha reta, mas do lado ERRADO da agua:
    # para chegar ate ele precisam dar a volta por uma das duas pontes.
    passageiro = no_da_celula(LADO // 2, LADO // 2 + 1)
    motoristas = sortear_motoristas(LADO, 20, semente=42,
                                    centro=(LADO // 2, LADO // 2), raio_celulas=10)

    # ---------------------------------------------------------- 1. matching
    titulo("1. MATCHING -- qual motorista chega antes?")

    def ingenuo():
        expandidos = 0
        etas = {}
        for mid, no in motoristas.items():
            r = busca_caminho_minimo(cidade, no, {passageiro},
                                     limite=LIMITE_MATCHING_SEGUNDOS)
            expandidos += r.nos_expandidos
            if passageiro in r.custos:
                etas[mid] = r.custos[passageiro]
        return etas, expandidos

    def reverso_many_to_one():
        r = busca_caminho_minimo(reverso, passageiro, set(motoristas.values()),
                                 limite=LIMITE_MATCHING_SEGUNDOS)
        etas = {mid: r.custos[no] for mid, no in motoristas.items() if no in r.custos}
        return etas, r.nos_expandidos

    (etas_a, exp_a), ms_a = cronometrar(ingenuo)
    (etas_b, exp_b), ms_b = cronometrar(reverso_many_to_one)

    # Comparacao por tolerancia, nao por igualdade exata: as duas buscas somam
    # os mesmos pesos em ORDEM diferente, e ponto flutuante nao e associativo.
    # A divergencia observada fica na casa de 1e-13 s -- ruido de arredondamento,
    # nao diferenca de algoritmo.
    assert set(etas_a) == set(etas_b), "os dois devem achar os mesmos motoristas"
    assert all(isclose(etas_a[k], etas_b[k], rel_tol=1e-9) for k in etas_a), \
        "as duas abordagens devem dar o MESMO resultado"

    print(f"  {len(motoristas)} motoristas candidatos (o que a quadtree entregaria)\n")
    print(f"  {'abordagem':<34}{'buscas':>8}{'nos expandidos':>17}{'tempo':>11}")
    print(f"  {'k Dijkstras (uma por motorista)':<34}{len(motoristas):>8}"
          f"{exp_a:>17,}{ms_a:>9.1f}ms")
    print(f"  {'1 Dijkstra reverso many-to-one':<34}{1:>8}"
          f"{exp_b:>17,}{ms_b:>9.1f}ms")
    print(f"\n  ganho: {exp_a / exp_b:.1f}x menos nos expandidos, "
          f"{ms_a / ms_b:.1f}x mais rapido -- resultado identico")

    # ------------------------------------ a distancia em linha reta mente
    titulo("2. Por que a quadtree sozinha nao basta")
    lat_p, lon_p = cidade.coordenadas(passageiro)

    def metros_em_linha_reta(mid):
        return haversine(*cidade.coordenadas(motoristas[mid]), lat_p, lon_p)

    ranking_eta = sorted(etas_b, key=lambda mid: etas_b[mid])
    ranking_reta = sorted(etas_b, key=metros_em_linha_reta)

    print(f"  {'motorista':<14}{'linha reta':>12}{'ETA real':>11}"
          f"{'velocidade implicita':>23}")
    for mid in ranking_reta[:6]:
        metros = metros_em_linha_reta(mid)
        kmh = (metros / 1000) / (etas_b[mid] / 3600)
        print(f"  {mid:<14}{metros:>9.0f} m{etas_b[mid] / 60:>9.1f} min{kmh:>20.1f} km/h")

    # A pior inversao: alguem mais perto em linha reta que chega MUITO depois.
    pior = None
    for x in etas_b:
        for y in etas_b:
            if metros_em_linha_reta(x) < metros_em_linha_reta(y):
                atraso = etas_b[x] - etas_b[y]
                if pior is None or atraso > pior[2]:
                    pior = (x, y, atraso)

    escolha_ingenua = ranking_reta[0]
    escolha_correta = ranking_eta[0]
    print(f"\n  Escolha pela quadtree (mais perto em linha reta): {escolha_ingenua}"
          f"  ->  {etas_b[escolha_ingenua] / 60:.1f} min")
    print(f"  Escolha pelo Dijkstra reverso (menor ETA real)  : {escolha_correta}"
          f"  ->  {etas_b[escolha_correta] / 60:.1f} min")

    if pior and pior[2] > 0:
        x, y, atraso = pior
        print(f"\n  Pior inversao: {x} esta a {metros_em_linha_reta(x):.0f} m e "
              f"{y} a {metros_em_linha_reta(y):.0f} m,")
        print(f"  mas {x} chega {atraso / 60:.1f} min DEPOIS -- esta do outro lado "
              f"do rio e precisa dar a volta pela ponte.")
        print("  A distancia euclidiana nao enxerga a agua; o tempo por ruas sim.")

    # ------------------------------------------------------------- 3. rota
    titulo("3. ROTA DA CORRIDA -- Dijkstra x A*")
    destino = no_da_celula(LADO - 3, LADO - 3)
    h = heuristica_haversine(cidade, destino, VELOCIDADE_MAX_KMH)

    r_dij, ms_dij = cronometrar(
        lambda: busca_caminho_minimo(cidade, passageiro, {destino}))
    r_ast, ms_ast = cronometrar(
        lambda: busca_caminho_minimo(cidade, passageiro, {destino}, h=h))

    custo_dij = r_dij.custos[destino]
    custo_ast = r_ast.custos[destino]
    assert isclose(custo_dij, custo_ast, rel_tol=1e-9), "A* precisa dar a MESMA rota otima"

    print(f"  {'algoritmo':<34}{'nos expandidos':>17}{'tempo':>11}{'custo':>12}")
    print(f"  {'Dijkstra (h = 0)':<34}{r_dij.nos_expandidos:>17,}"
          f"{ms_dij:>9.1f}ms{custo_dij / 60:>9.2f} min")
    print(f"  {'A* (h = haversine / v_max)':<34}{r_ast.nos_expandidos:>17,}"
          f"{ms_ast:>9.1f}ms{custo_ast / 60:>9.2f} min")
    print(f"\n  ganho: {r_dij.nos_expandidos / r_ast.nos_expandidos:.1f}x menos nos "
          f"expandidos -- e a MESMA rota otima (custo identico)")

    rota = reconstruir_caminho(r_ast.anterior, passageiro, destino)
    print(f"  rota com {len(rota)} cruzamentos: "
          f"{' -> '.join(map(str, rota[:3]))} -> ... -> {' -> '.join(map(str, rota[-2:]))}")

    # ------------------------------------------------ 4. quadtree x varredura
    titulo("4. INDICE ESPACIAL -- varredura linear x quadtree")
    print("  Busca de motoristas num raio de 300 m, 200 consultas por tamanho.\n")
    print(f"  {'motoristas':>11}{'linear (comparacoes)':>23}{'quadtree (nos)':>17}"
          f"{'ganho':>9}{'altura':>9}")

    import random as _random
    for quantidade in (500, 2000, 8000, 32000):
        rng = _random.Random(4)
        pontos = {i: (-23.55 + rng.random() * 0.05, -46.64 + rng.random() * 0.05)
                  for i in range(quantidade)}
        arvore = Quadtree(pontos)
        linear = IndiceLinear(pontos)

        visitados = 0
        consultas = [(-23.55 + rng.random() * 0.05, -46.64 + rng.random() * 0.05)
                     for _ in range(200)]
        for lat, lon in consultas:
            resultado_arvore = arvore.proximos(lat, lon, 300)
            visitados += arvore.nos_visitados
            assert resultado_arvore == linear.proximos(lat, lon, 300), \
                "quadtree divergiu da varredura linear"

        media_arvore = visitados / len(consultas)
        print(f"  {quantidade:>11,}{quantidade:>23,}{media_arvore:>17.1f}"
              f"{quantidade / media_arvore:>8.1f}x{arvore.altura():>9}")

    print("\n  Em toda consulta o resultado foi IDENTICO ao da varredura linear.")
    print("\n  Leitura correta dos numeros: 64x mais motoristas custaram so ~10x")
    print("  mais nos visitados. Nao e O(log n) puro, e sim O(log n + k), com k =")
    print("  quantidade de RESULTADOS -- num raio fixo, adensar a cidade aumenta")
    print("  quem cabe dentro dele. O T(n) = T(n/4) + O(1) = O(log n) da secao 6")
    print("  da documentacao descreve a DESCIDA ate a folha; a coleta acrescenta")
    print("  o termo k, que nenhuma estrutura elimina: os k pontos precisam ser")
    print("  lidos de todo jeito. A varredura linear paga n mesmo quando k = 0.")


if __name__ == "__main__":
    main()
