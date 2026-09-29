"""Testes da camada de algoritmos.

Roda sem pytest:  python3 tests/test_algoritmos.py
Com pytest:       pytest tests/

A ideia central destes testes e o ORACULO: o Dijkstra, por ser simples e
comprovadamente correto (prova por inducao, secao 5.1 da documentacao),
serve de gabarito para validar o A* e a busca reversa. Se a heuristica do
A* estiver errada, os custos divergem e o teste quebra.
"""

import os
import random
import sys
from math import inf, isclose

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from algoritmos.busca import (busca_caminho_minimo, caminho_ate_origem,
                              reconstruir_caminho)
from algoritmos.cidade_exemplo import (VELOCIDADE_MAX_KMH, construir_cidade,
                                       no_da_celula, sortear_motoristas)
from algoritmos.grafo import Grafo, heuristica_haversine
from algoritmos.matching import (motoristas_mais_proximos,
                                 motoristas_mais_proximos_ingenuo)

LADO = 30
CIDADE = construir_cidade(lado=LADO)


def custo_do_caminho(grafo, caminho):
    """Soma os pesos ao longo do caminho, validando cada aresta."""
    total = 0.0
    for a, b in zip(caminho, caminho[1:]):
        pesos = dict(grafo.vizinhos(a))
        assert b in pesos, f"aresta inexistente no grafo: {a} -> {b}"
        total += pesos[b]
    return total


# --------------------------------------------------------------------------
# 1. O oraculo: A* tem de devolver exatamente o mesmo custo que o Dijkstra
# --------------------------------------------------------------------------

def test_astar_concorda_com_dijkstra():
    rng = random.Random(7)
    nos = sorted(CIDADE.nos)
    for _ in range(200):
        origem, destino = rng.sample(nos, 2)
        h = heuristica_haversine(CIDADE, destino, VELOCIDADE_MAX_KMH)

        dij = busca_caminho_minimo(CIDADE, origem, {destino}, h=None)
        ast = busca_caminho_minimo(CIDADE, origem, {destino}, h=h)

        assert isclose(dij.custos[destino], ast.custos[destino], rel_tol=1e-9), (
            f"A* divergiu do Dijkstra em {origem} -> {destino}: "
            f"{ast.custos[destino]} != {dij.custos[destino]}"
        )


def test_astar_expande_menos_nos():
    """Mesma complexidade de pior caso, ganho no caso medio."""
    rng = random.Random(11)
    nos = sorted(CIDADE.nos)
    dij_total = ast_total = 0
    for _ in range(50):
        origem, destino = rng.sample(nos, 2)
        h = heuristica_haversine(CIDADE, destino, VELOCIDADE_MAX_KMH)
        dij_total += busca_caminho_minimo(CIDADE, origem, {destino}).nos_expandidos
        ast_total += busca_caminho_minimo(CIDADE, origem, {destino}, h=h).nos_expandidos
    assert ast_total < dij_total, "A* deveria expandir menos nos que o Dijkstra"


def test_heuristica_inadmissivel_seria_pega():
    """Se alguem esquecer de dividir pela velocidade, h vira metros enquanto
    os pesos sao segundos: superestima, perde a admissibilidade e o A* erra.
    Este teste documenta o bug, provando que ele e detectavel."""
    origem, destino = no_da_celula(2, 2), no_da_celula(LADO - 3, LADO - 3)
    correto = busca_caminho_minimo(CIDADE, origem, {destino}).custos[destino]

    from algoritmos.grafo import haversine
    lat_d, lon_d = CIDADE.coordenadas(destino)

    def h_errada(no):                       # <- falta dividir por v_max
        lat, lon = CIDADE.coordenadas(no)
        return haversine(lat, lon, lat_d, lon_d)

    ruim = busca_caminho_minimo(CIDADE, origem, {destino}, h=h_errada).custos[destino]
    assert ruim > correto, "heuristica inadmissivel deveria degradar a rota"


# --------------------------------------------------------------------------
# 2. A identidade que sustenta o matching reverso
# --------------------------------------------------------------------------

def test_identidade_do_grafo_reverso():
    """dist_{G_reverso}(p, m) == dist_G(m, p), para todo par."""
    rng = random.Random(13)
    nos = sorted(CIDADE.nos)
    reverso = CIDADE.reverso()
    for _ in range(100):
        p, m = rng.sample(nos, 2)
        ida = busca_caminho_minimo(CIDADE, m, {p}).custos[p]
        volta = busca_caminho_minimo(reverso, p, {m}).custos[m]
        assert isclose(ida, volta, rel_tol=1e-9)


def test_grafo_e_mesmo_direcionado():
    """Prova que inverter o grafo NAO e detalhe: existem pares onde ir e
    voltar custam coisas diferentes (mao unica). Se a malha fosse simetrica,
    bastaria rodar Dijkstra a partir do passageiro."""
    rng = random.Random(17)
    nos = sorted(CIDADE.nos)
    assimetricos = 0
    for _ in range(100):
        a, b = rng.sample(nos, 2)
        ida = busca_caminho_minimo(CIDADE, a, {b}).custos[b]
        volta = busca_caminho_minimo(CIDADE, b, {a}).custos[a]
        if not isclose(ida, volta, rel_tol=1e-6):
            assimetricos += 1
    assert assimetricos > 0, "malha simetrica: o exemplo perdeu o sentido"


# --------------------------------------------------------------------------
# 3. Matching reverso many-to-one x versao ingenua (k buscas)
# --------------------------------------------------------------------------

def test_matching_reverso_igual_ao_ingenuo():
    passageiro = no_da_celula(LADO // 2, LADO // 2)
    motoristas = sortear_motoristas(LADO, 20, semente=3)

    rapido = motoristas_mais_proximos(CIDADE, passageiro, motoristas)
    lento, _ = motoristas_mais_proximos_ingenuo(CIDADE, passageiro, motoristas)

    assert len(rapido) == len(lento)
    for a, b in zip(rapido, lento):
        assert a.motorista_id == b.motorista_id
        assert isclose(a.eta_segundos, b.eta_segundos, rel_tol=1e-9)


def test_matching_gasta_menos_que_k_buscas():
    passageiro = no_da_celula(LADO // 2, LADO // 2)
    motoristas = sortear_motoristas(LADO, 20, semente=5)

    reverso = CIDADE.reverso()
    uma_busca = busca_caminho_minimo(reverso, passageiro, set(motoristas.values()))
    _, expandidos_ingenuo = motoristas_mais_proximos_ingenuo(CIDADE, passageiro, motoristas)

    assert uma_busca.nos_expandidos < expandidos_ingenuo


def test_rotas_do_matching_sao_validas_no_grafo_original():
    """A rota lida do grafo reverso tem de ser uma sequencia de arestas
    REAIS do grafo original, e somar exatamente o ETA informado."""
    passageiro = no_da_celula(LADO // 2, LADO // 2)
    motoristas = sortear_motoristas(LADO, 15, semente=9)

    for candidato in motoristas_mais_proximos(CIDADE, passageiro, motoristas):
        assert candidato.rota[0] == candidato.no, "rota deve comecar no motorista"
        assert candidato.rota[-1] == passageiro, "rota deve terminar no passageiro"
        total = custo_do_caminho(CIDADE, candidato.rota)
        assert isclose(total, candidato.eta_segundos, rel_tol=1e-9)


def test_limite_de_tempo_descarta_distantes():
    passageiro = no_da_celula(0, 0)
    motoristas = sortear_motoristas(LADO, 25, semente=21)
    todos = motoristas_mais_proximos(CIDADE, passageiro, motoristas)
    limitado = motoristas_mais_proximos(CIDADE, passageiro, motoristas, limite_segundos=120)

    assert len(limitado) < len(todos)
    assert all(c.eta_segundos <= 120 for c in limitado)


# --------------------------------------------------------------------------
# 4. Rota da corrida e reconstrucao de caminho
# --------------------------------------------------------------------------

def test_rota_da_corrida_e_valida():
    origem, destino = no_da_celula(3, 3), no_da_celula(LADO - 4, LADO - 4)
    h = heuristica_haversine(CIDADE, destino, VELOCIDADE_MAX_KMH)
    resultado = busca_caminho_minimo(CIDADE, origem, {destino}, h=h)
    rota = reconstruir_caminho(resultado.anterior, origem, destino)

    assert rota[0] == origem and rota[-1] == destino
    assert isclose(custo_do_caminho(CIDADE, rota), resultado.custos[destino], rel_tol=1e-9)


def test_caminho_trivial_e_inexistente():
    meio = no_da_celula(5, 5)
    r = busca_caminho_minimo(CIDADE, meio, {meio})
    assert r.custos[meio] == 0.0
    assert reconstruir_caminho(r.anterior, meio, meio) == [meio]
    assert caminho_ate_origem({}, no_da_celula(9, 9), meio) == []


# --------------------------------------------------------------------------
# 5. Guardas e invariantes
# --------------------------------------------------------------------------

def test_heuristica_com_varios_alvos_e_rejeitada():
    h = heuristica_haversine(CIDADE, no_da_celula(1, 1), VELOCIDADE_MAX_KMH)
    try:
        busca_caminho_minimo(CIDADE, no_da_celula(0, 0),
                             {no_da_celula(1, 1), no_da_celula(2, 2)}, h=h)
    except ValueError:
        return
    raise AssertionError("deveria recusar heuristica com multiplos alvos")


def test_peso_negativo_e_rejeitado():
    g = Grafo()
    g.adicionar_no("a", 0.0, 0.0)
    g.adicionar_no("b", 0.0, 0.1)
    try:
        g.adicionar_aresta("a", "b", -1.0)
    except ValueError:
        return
    raise AssertionError("peso negativo quebraria a prova de corretude")


def test_atualizar_peso_mantem_reverso_sincronizado():
    g = construir_cidade(lado=8)
    reverso = g.reverso()
    origem = no_da_celula(0, 0)
    destino, peso_antigo = next(iter(g.vizinhos(origem)))

    g.atualizar_peso(origem, destino, peso_antigo * 10)   # engarrafamento

    assert dict(reverso.vizinhos(destino))[origem] == peso_antigo * 10, (
        "grafo reverso ficou com o peso antigo: o matching usaria tempos velhos"
    )


def test_alvo_inalcancavel_e_reportado():
    g = Grafo()
    g.adicionar_no("a", 0.0, 0.0)
    g.adicionar_no("ilha", 1.0, 1.0)
    r = busca_caminho_minimo(g, "a", {"ilha"})
    assert r.nao_alcancados == {"ilha"} and "ilha" not in r.custos


# --------------------------------------------------------------------------

def main():
    testes = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    falhas = 0
    for teste in testes:
        try:
            teste()
            print(f"  ok    {teste.__name__}")
        except AssertionError as erro:
            falhas += 1
            print(f"  FALHA {teste.__name__}: {erro}")
    print(f"\n{len(testes) - falhas}/{len(testes)} testes passaram")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
