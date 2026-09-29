"""Testes do carregador OpenStreetMap.

Roda sem rede: o fixture reproduz um extrato Overpass em miniatura, cobrindo
as convencoes que de fato aparecem no OSM -- mao unica explicita, mao unica
invertida, rotatoria, via expressa com sentido implicito, maxspeed em km/h e
em mph, etiqueta malformada, fragmento solto e armadilha de mao unica.

    python3 tests/test_osm.py
"""

import json
import os
import sys
import tempfile
from math import isclose

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from algoritmos.grafo import haversine
from infra.osm import (VELOCIDADE_PADRAO, _sentidos, _velocidade_kmh,
                       carregar_grafo, construir_grafo,
                       maior_componente_fortemente_conexo, montar_consulta,
                       salvar_grafo)

COORD = {
    1: (-23.5500, -46.6400), 2: (-23.5500, -46.6390),
    3: (-23.5510, -46.6390), 4: (-23.5510, -46.6400),
    5: (-23.5520, -46.6400),                      # armadilha de mao unica
    6: (-23.5600, -46.6500), 7: (-23.5600, -46.6490),  # fragmento solto
}

VIAS = [
    # ida e volta, com maxspeed malformado (deve cair no padrao residential)
    (101, [1, 2], {"highway": "residential", "maxspeed": "abc"}),
    (102, [2, 3], {"highway": "primary", "oneway": "yes", "maxspeed": "60"}),
    (103, [3, 4], {"highway": "residential", "oneway": "no"}),
    (104, [4, 1], {"highway": "residential", "maxspeed": "30 mph"}),
    (105, [4, 5], {"highway": "residential", "oneway": "yes"}),   # so entra
    (106, [6, 7], {"highway": "residential"}),                    # desconexo
    (107, [1, 3], {"highway": "motorway"}),        # mao unica implicita
    (108, [2, 4], {"highway": "residential", "oneway": "-1"}),    # invertida
]

FIXTURE = {"elements": (
    [{"type": "node", "id": i, "lat": la, "lon": lo} for i, (la, lo) in COORD.items()]
    + [{"type": "way", "id": i, "nodes": ns, "tags": t} for i, ns, t in VIAS]
)}


def grafo_bruto():
    return construir_grafo(FIXTURE)


def tem_aresta(grafo, origem, destino):
    return destino in dict(grafo.vizinhos(origem))


def peso(grafo, origem, destino):
    return dict(grafo.vizinhos(origem))[destino]


# ----------------------------------------------------------- direcionalidade

def test_mao_dupla_gera_as_duas_arestas():
    g = grafo_bruto()
    assert tem_aresta(g, 1, 2) and tem_aresta(g, 2, 1)


def test_oneway_yes_gera_so_a_ida():
    g = grafo_bruto()
    assert tem_aresta(g, 2, 3) and not tem_aresta(g, 3, 2)


def test_oneway_invertido_gera_so_a_volta():
    """oneway=-1 significa que a via corre CONTRA a ordem dos nos."""
    g = grafo_bruto()
    assert tem_aresta(g, 4, 2) and not tem_aresta(g, 2, 4)


def test_motorway_e_mao_unica_mesmo_sem_etiqueta():
    g = grafo_bruto()
    assert tem_aresta(g, 1, 3) and not tem_aresta(g, 3, 1)


def test_rotatoria_e_mao_unica():
    assert _sentidos({"highway": "residential", "junction": "roundabout"}) == (True, False)


def test_oneway_explicito_vence_o_implicito():
    assert _sentidos({"highway": "motorway", "oneway": "no"}) == (True, True)


# ------------------------------------------------------------- velocidades

def test_maxspeed_em_kmh():
    assert _velocidade_kmh({"highway": "primary", "maxspeed": "60"}) == 60.0


def test_maxspeed_em_mph_e_convertido():
    assert isclose(_velocidade_kmh({"highway": "residential", "maxspeed": "30 mph"}),
                   30 * 1.609344, rel_tol=1e-9)


def test_maxspeed_malformado_cai_no_padrao():
    assert _velocidade_kmh({"highway": "residential", "maxspeed": "abc"}) == \
        VELOCIDADE_PADRAO["residential"]


def test_maxspeed_sem_etiqueta_usa_padrao_do_tipo():
    assert _velocidade_kmh({"highway": "motorway"}) == VELOCIDADE_PADRAO["motorway"]


def test_via_desconhecida_usa_fallback():
    assert _velocidade_kmh({"highway": "service"}) == 30.0


# ------------------------------------------------------------------- pesos

def test_peso_e_tempo_em_segundos():
    """Peso = distancia / velocidade. A unidade do sistema inteiro e segundo."""
    g = grafo_bruto()
    metros = haversine(*COORD[2], *COORD[3])
    esperado = metros / (60.0 / 3.6)          # via 102: primary a 60 km/h
    assert isclose(peso(g, 2, 3), esperado, rel_tol=1e-9)


def test_via_mais_rapida_tem_peso_menor():
    g = grafo_bruto()
    assert peso(g, 1, 3) < peso(g, 1, 2)      # motorway 100 km/h x residential 30


# ------------------------------------------------- componente fortemente conexo

def test_poda_remove_fragmento_solto_e_armadilha():
    """6 e 7 estao desconectados; 5 so recebe entrada e nunca devolve saida."""
    bruto = grafo_bruto()
    assert {5, 6, 7} <= set(bruto.nos)

    podado = maior_componente_fortemente_conexo(bruto)
    assert set(podado.nos) == {1, 2, 3, 4}


def test_apos_poda_todo_par_e_mutuamente_alcancavel():
    from algoritmos.busca import busca_caminho_minimo
    podado = maior_componente_fortemente_conexo(grafo_bruto())
    for origem in podado.nos:
        alcancados = set(busca_caminho_minimo(podado, origem, alvos=set()).distancias)
        assert alcancados == set(podado.nos), f"{origem} nao alcanca toda a malha"


def test_poda_de_grafo_vazio_nao_quebra():
    assert len(maior_componente_fortemente_conexo(construir_grafo({"elements": []})).nos) == 0


# --------------------------------------------------------------- serializacao

def test_serializacao_preserva_o_grafo():
    original = maior_componente_fortemente_conexo(grafo_bruto())
    with tempfile.TemporaryDirectory() as pasta:
        caminho = os.path.join(pasta, "malha.json")
        salvar_grafo(original, caminho)
        lido = carregar_grafo(caminho)

    assert set(lido.nos) == set(original.nos)
    assert lido.total_arestas() == original.total_arestas()
    for origem in original.nos:
        assert lido.coordenadas(origem) == original.coordenadas(origem)
        for destino, p in original.vizinhos(origem):
            assert isclose(peso(lido, origem, destino), p, abs_tol=1e-3)


# -------------------------------------------------------------------- consulta

def test_consulta_overpass_tem_caixa_e_filtro():
    consulta = montar_consulta(-23.56, -46.65, -23.54, -46.63)
    assert "-23.56,-46.65,-23.54,-46.63" in consulta
    assert "residential" in consulta and "out body" in consulta
    assert "footway" not in consulta      # pedestre nao entra na malha de carro


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
            print(f"  FALHA {teste.__name__}: {erro}")
    print(f"\n{len(testes) - falhas}/{len(testes)} testes passaram")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
