"""Testes da contracao de nos de passagem.

A propriedade que importa e verificada contra o ORACULO, e nao assumida:
o Dijkstra no grafo original e no contraido devolve o mesmo custo para todo
par de nos mantidos. Se a contracao somasse errado, perdesse um sentido de
mao unica ou ligasse o que nao estava ligado, o teste pega.

    python3 matematica/tests/test_contracao.py
"""

import json
import os
import random
import sys
from math import isclose

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from algoritmos.busca import busca_caminho_minimo, reconstruir_caminho
from algoritmos.contracao import Geometria, contrair, nos_de_passagem
from algoritmos.grafo import Grafo, haversine, heuristica_haversine
from algoritmos.matriz_mapa import MatrizMapa

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MALHA_REAL = os.path.join(os.path.dirname(RAIZ), "backend", "dados", "malha.json")

# ~111 m por 0,001 grau de latitude: coordenadas de brinquedo em Sao Paulo.
LAT0, LON0, PASSO = -23.55, -46.63, 0.001


def ponto(i, j=0):
    return LAT0 + i * PASSO, LON0 + j * PASSO


def linha(ids, mao_dupla=True, peso=10.0, coluna=0):
    """Grafo com os `ids` enfileirados numa rua reta."""
    g = Grafo()
    for k, no in enumerate(ids):
        g.adicionar_no(no, *ponto(k, coluna))
    for a, b in zip(ids, ids[1:]):
        if mao_dupla:
            g.adicionar_rua_mao_dupla(a, b, peso)
        else:
            g.adicionar_aresta(a, b, peso)
    return g


def custos_de(grafo, origem):
    return busca_caminho_minimo(grafo, origem, alvos=set()).distancias


def confere_oraculo(original, contraido, origens):
    for origem in origens:
        esperado = custos_de(original, origem)
        obtido = custos_de(contraido, origem)
        # Sem esta trava, um oraculo que compara dicionarios vazios passaria.
        assert len(obtido) > 1, "busca nao alcancou ninguem: oraculo vazio"
        for destino in contraido.nos:
            assert (destino in esperado) == (destino in obtido), \
                f"{origem}->{destino}: alcancabilidade mudou"
            if destino in esperado:
                assert isclose(esperado[destino], obtido[destino], abs_tol=1e-6), \
                    f"{origem}->{destino}: {esperado[destino]} != {obtido[destino]}"


def subdividida(grafo, pedacos=4, semente=3):
    """Cada aresta da malha vira uma cadeia de `pedacos`, com uma curva.

    E o formato que o OSM entrega: um no a cada inflexao da rua. Os pesos
    somam o original, entao o caminho minimo entre cruzamentos nao muda.
    """
    aleatorio = random.Random(semente)
    g = Grafo()
    for no in grafo.nos:
        g.adicionar_no(no, *grafo.coordenadas(no))
    proximo_id = 10 ** 9
    feitas = set()
    for a in grafo.nos:
        for b, peso in grafo.vizinhos(a):
            if (b, a) in feitas:
                continue
            feitas.add((a, b))
            volta = dict(grafo.vizinhos(b)).get(a)
            (la, oa), (lb, ob) = grafo.coordenadas(a), grafo.coordenadas(b)
            cadeia = [a]
            for k in range(1, pedacos):
                t = k / pedacos
                desvio = aleatorio.uniform(-2e-5, 2e-5)
                g.adicionar_no(proximo_id, la + t * (lb - la) + desvio, oa + t * (ob - oa))
                cadeia.append(proximo_id)
                proximo_id += 1
            cadeia.append(b)
            for x, y in zip(cadeia, cadeia[1:]):
                g.adicionar_aresta(x, y, peso / pedacos)
                if volta is not None:
                    g.adicionar_aresta(y, x, volta / pedacos)
    return g


# ------------------------------------------------------------------ casos

def test_cadeia_de_mao_dupla_vira_uma_aresta_com_peso_somado():
    g = linha([1, 2, 3, 4, 5])
    c, geo = contrair(g, limite_m=10_000)
    assert set(c.nos) == {1, 5}
    assert dict(c.vizinhos(1)) == {5: 40.0}
    assert dict(c.vizinhos(5)) == {1: 40.0}
    assert len(geo.intermediarios(1, 5)) == 3
    assert geo.intermediarios(5, 1) == geo.intermediarios(1, 5)[::-1]


def test_mao_unica_so_gera_o_sentido_permitido():
    c, _ = contrair(linha([1, 2, 3, 4], mao_dupla=False), limite_m=10_000)
    assert dict(c.vizinhos(1)) == {4: 30.0}
    assert dict(c.vizinhos(4)) == {}


def test_contramao_no_meio_da_cadeia_corta_aquele_sentido():
    g = linha([1, 2, 3, 4])
    del g._adjacencia[3][2]            # 2 -> 3 so de ida
    c, _ = contrair(g, limite_m=10_000)
    assert 4 in dict(c.vizinhos(1))
    assert 1 not in dict(c.vizinhos(4)), "volta atravessaria a contramao"


def test_semaforo_nunca_e_contraido():
    c, _ = contrair(linha([1, 2, 3, 4, 5]), preservar={3}, limite_m=10_000)
    assert set(c.nos) == {1, 3, 5}


def test_beco_que_so_recebe_nao_some():
    g = Grafo()
    for k, no in enumerate((1, 2, 3)):
        g.adicionar_no(no, *ponto(k))
    g.adicionar_aresta(1, 2, 5.0)
    g.adicionar_aresta(3, 2, 5.0)      # 2 so recebe: e destino, nao passagem
    passagem, _ = nos_de_passagem(g)
    assert 2 not in passagem


def test_ruas_paralelas_entre_os_mesmos_cruzamentos_fica_a_mais_rapida():
    g = Grafo()
    g.adicionar_no(1, *ponto(0)); g.adicionar_no(9, *ponto(4))
    g.adicionar_no(2, *ponto(2, -1)); g.adicionar_no(3, *ponto(2, 1))
    g.adicionar_rua_mao_dupla(1, 2, 30.0); g.adicionar_rua_mao_dupla(2, 9, 30.0)
    g.adicionar_rua_mao_dupla(1, 3, 10.0); g.adicionar_rua_mao_dupla(3, 9, 10.0)
    # Ruas saindo de 1 e de 9: sem elas o par seria um anel, nao cruzamentos.
    g.adicionar_no(0, *ponto(-1)); g.adicionar_no(10, *ponto(5))
    g.adicionar_rua_mao_dupla(0, 1, 5.0); g.adicionar_rua_mao_dupla(9, 10, 5.0)
    c, geo = contrair(g, limite_m=10_000)
    assert set(c.nos) == {0, 1, 9, 10}
    assert dict(c.vizinhos(1))[9] == 20.0
    [(lat, lon)] = geo.intermediarios(1, 9)
    assert isclose(lat, ponto(2, 1)[0], abs_tol=1e-6) and isclose(lon, ponto(2, 1)[1], abs_tol=1e-6), \
        "tracado tem de ser o da rua vencedora"


def test_cadeia_longa_e_partida_pelo_limite():
    ids = list(range(1, 31))           # 29 trechos de ~111 m
    c, geo = contrair(linha(ids), limite_m=250)
    assert len(c.nos) > 2, "3,2 km numa aresta so ancoraria longe demais"
    for u in c.nos:
        for v, _ in c.vizinhos(u):
            assert geo.comprimento_m(c, [u, v]) <= 250 + 112


def test_ciclo_isolado_nao_trava_e_preserva_distancias():
    g = Grafo()
    ids = list(range(1, 7))
    for k, no in enumerate(ids):
        g.adicionar_no(no, *ponto(k % 3, k // 3))
    for a, b in zip(ids, ids[1:] + ids[:1]):
        g.adicionar_rua_mao_dupla(a, b, 7.0)
    # Anel de ~670 m so de nos de passagem: vira uma ancora mais os cortes
    # de 250 m, e as distancias entre eles nao mudam.
    c, _ = contrair(g, limite_m=250)
    assert 2 <= len(c.nos) < len(ids)
    confere_oraculo(g, c, list(c.nos))
    sozinho, _ = contrair(g, limite_m=10_000)
    assert len(sozinho.nos) == 1, "sem corte, o anel colapsa na sua ancora"


def test_geometria_vazia_e_neutra():
    g = linha([1, 2, 3])
    assert Geometria().tracado(g, [1, 2, 3]) == [g.coordenadas(n) for n in (1, 2, 3)]
    assert isclose(Geometria().comprimento_m(g, [1, 2]),
                   haversine(*g.coordenadas(1), *g.coordenadas(2)))


# ------------------------------------------------------ oraculo na malha

def _matriz_subdividida():
    with open(os.path.join(RAIZ, "mapas", "centro.mapa"), encoding="utf-8") as a:
        base = MatrizMapa.de_texto(a.read()).para_grafo()
    return base, subdividida(base)


BASE, SUBDIVIDIDA = _matriz_subdividida()
CONTRAIDA, GEO = contrair(SUBDIVIDIDA, limite_m=10_000)


def test_contracao_desfaz_a_subdivisao():
    assert len(SUBDIVIDIDA.nos) > 2 * len(BASE.nos)
    assert set(CONTRAIDA.nos) <= set(BASE.nos)


def test_oraculo_dijkstra_no_original_e_no_contraido():
    origens = random.Random(5).sample(sorted(CONTRAIDA.nos), 12)
    confere_oraculo(SUBDIVIDIDA, CONTRAIDA, origens)


def test_a_estrela_continua_exato_no_grafo_contraido():
    aleatorio = random.Random(8)
    nos = sorted(CONTRAIDA.nos)
    for _ in range(40):
        o, d = aleatorio.sample(nos, 2)
        dijkstra = busca_caminho_minimo(CONTRAIDA, o, {d}).custos.get(d)
        a_estrela = busca_caminho_minimo(CONTRAIDA, o, {d},
                                         h=heuristica_haversine(CONTRAIDA, d)).custos.get(d)
        assert (dijkstra is None) == (a_estrela is None)
        if dijkstra is not None:
            assert isclose(dijkstra, a_estrela, abs_tol=1e-6), f"{o}->{d}"


def test_metros_pelo_tracado_iguais_aos_do_grafo_original():
    aleatorio = random.Random(13)
    nos = sorted(CONTRAIDA.nos)
    for _ in range(20):
        o, d = aleatorio.sample(nos, 2)
        r = busca_caminho_minimo(CONTRAIDA, o, {d})
        if d not in r.custos:
            continue
        caminho = reconstruir_caminho(r.anterior, o, d)
        pontos = GEO.tracado(CONTRAIDA, caminho)
        assert pontos[0] == CONTRAIDA.coordenadas(o) and pontos[-1] == CONTRAIDA.coordenadas(d)
        r0 = busca_caminho_minimo(SUBDIVIDIDA, o, {d})
        original = reconstruir_caminho(r0.anterior, o, d)
        metros0 = sum(haversine(*SUBDIVIDIDA.coordenadas(a), *SUBDIVIDIDA.coordenadas(b))
                      for a, b in zip(original, original[1:]))
        # Empate de custo pode escolher outra rua; so compara quando o
        # traçado tem o mesmo numero de pontos (mesma sequencia de cadeias).
        if len(pontos) == len(original):
            # Microgaus arredondam ~0,1 m por ponto: o erro e de centimetros.
            assert isclose(GEO.comprimento_m(CONTRAIDA, caminho), metros0,
                           abs_tol=0.1 * len(pontos))


def test_oraculo_na_malha_real_de_sao_paulo():
    """Na malha OSM versionada, se ela existir no formato sem geometria."""
    if not os.path.exists(MALHA_REAL):
        return
    with open(MALHA_REAL, encoding="utf-8") as a:
        dados = json.load(a)
    if "geometria" in dados:
        return                         # ja contraida: nada a comparar
    g = Grafo()
    for no, lat, lon in dados["nos"]:
        g.adicionar_no(no, lat, lon)
    for o, d, p in dados["arestas"]:
        g.adicionar_aresta(o, d, p)
    sinais = {s[0] for s in dados.get("semaforos", [])}
    c, _ = contrair(g, preservar=sinais)
    assert len(c.nos) < 0.3 * len(g.nos), f"so caiu para {len(c.nos)} de {len(g.nos)}"
    assert sinais & set(g.nos) <= set(c.nos)
    confere_oraculo(g, c, random.Random(2).sample(sorted(c.nos), 3))


# ---------------------------------------------------------------------------

def main():
    testes = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    falhas = 0
    for teste in testes:
        try:
            teste()
            print(f"  ok    {teste.__name__}")
        except AssertionError as erro:
            falhas += 1
            print(f"  FALHA {teste.__name__}: {str(erro)[:150]}")
    print(f"\n{len(testes) - falhas}/{len(testes)} testes passaram")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
