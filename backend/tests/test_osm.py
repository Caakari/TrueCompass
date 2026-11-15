"""Testes do carregador OpenStreetMap.

Roda sem rede: o fixture reproduz um extrato Overpass em miniatura, cobrindo
as convencoes que de fato aparecem no OSM -- mao unica explicita, mao unica
invertida, rotatoria, via expressa com sentido implicito, maxspeed em km/h e
em mph, etiqueta malformada, fragmento solto e armadilha de mao unica.

    python3 backend/tests/test_osm.py
"""

import json
import os
import sys
import tempfile
from math import isclose

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import matematica_no_caminho  # noqa: E402,F401  -- pacote `algoritmos`, em ../matematica

from algoritmos.grafo import haversine
from algoritmos.busca import busca_caminho_minimo
from algoritmos.contracao import contrair
from infra.osm import (AREA_MUNICIPIO_SP, SEMAFORO_OSM, VELOCIDADE_PADRAO, _sentidos, blocos,
                       juntar_extratos,
                       _velocidade_kmh, carregar_grafo, construir_grafo,
                       ler_artefato, maior_componente_fortemente_conexo,
                       montar_consulta, salvar_grafo, semaforos_do_osm)

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


# -------------------------------------------------------------- semaforos

def _com_semaforo_no(no):
    """O fixture, com o no `no` etiquetado highway=traffic_signals."""
    elementos = [dict(e) for e in FIXTURE["elements"]]
    for e in elementos:
        if e["type"] == "node" and e["id"] == no:
            e["tags"] = {"highway": "traffic_signals"}
    return {"elements": elementos}


def test_semaforo_soma_atraso_so_na_aresta_que_chega():
    """1 <-> 2 e mao dupla; o sinal esta em 2. Quem CHEGA em 2 espera, quem
    sai de 2 nao -- e ali que se para."""
    sem, com = grafo_bruto(), construir_grafo(_com_semaforo_no(2))
    assert isclose(peso(com, 1, 2), peso(sem, 1, 2) + SEMAFORO_OSM.atraso, abs_tol=1e-9)
    assert isclose(peso(com, 2, 1), peso(sem, 2, 1), abs_tol=1e-9)


def test_semaforo_none_ignora_os_sinais():
    sem = grafo_bruto()
    ignorado = construir_grafo(_com_semaforo_no(2), semaforo=None)
    assert isclose(peso(ignorado, 1, 2), peso(sem, 1, 2), abs_tol=1e-9)


def test_atraso_presumido_segue_a_formula():
    """E[espera] = r^2 / (2c), com r = 40s e c = 90s."""
    assert isclose(SEMAFORO_OSM.atraso, 40 ** 2 / (2 * 90))


def test_artefato_leva_os_semaforos_que_sobreviveram_a_poda():
    """O sinal no fragmento solto (no 6) some junto com o fragmento."""
    dados = _com_semaforo_no(2)
    for e in dados["elements"]:
        if e["type"] == "node" and e["id"] == 6:
            e["tags"] = {"highway": "traffic_signals"}
    podado = maior_componente_fortemente_conexo(construir_grafo(dados))
    with tempfile.TemporaryDirectory() as pasta:
        caminho = os.path.join(pasta, "malha.json")
        salvar_grafo(podado, caminho, semaforos=semaforos_do_osm(dados))
        _grafo, semaforos, _geo = ler_artefato(caminho)
    assert [(s["lat"], s["lon"]) for s in semaforos] == [COORD[2]]
    assert isclose(semaforos[0]["atraso_medio"], round(SEMAFORO_OSM.atraso, 2))


def test_artefato_antigo_sem_semaforos_ainda_carrega():
    with tempfile.TemporaryDirectory() as pasta:
        caminho = os.path.join(pasta, "malha.json")
        salvar_grafo(grafo_bruto(), caminho)
        grafo, semaforos, _geo = ler_artefato(caminho)
    assert semaforos == [] and len(grafo.nos) == len(grafo_bruto().nos)


# -------------------------------------------------------------------- consulta

def test_consulta_overpass_tem_caixa_e_filtro():
    consulta = montar_consulta(-23.56, -46.65, -23.54, -46.63)
    assert "-23.56,-46.65,-23.54,-46.63" in consulta
    assert "residential" in consulta and "out body" in consulta
    assert "footway" not in consulta      # pedestre nao entra na malha de carro


# ---------------------------------------------------------------------------

def test_consulta_com_area_recorta_pelo_municipio():
    consulta = montar_consulta(-23.56, -46.65, -23.54, -46.63, area=AREA_MUNICIPIO_SP)
    assert f"area(id:{AREA_MUNICIPIO_SP})->.alvo;" in consulta
    assert "(area.alvo)(-23.56,-46.65,-23.54,-46.63)" in consulta


def test_blocos_cobrem_a_caixa_sem_buraco():
    lista = blocos(-24.0, -46.8, -23.4, -46.4, 4, 3)
    assert len(lista) == 12
    assert min(b[0] for b in lista) == -24.0 and max(b[2] for b in lista) == -23.4
    assert min(b[1] for b in lista) == -46.8 and max(b[3] for b in lista) == -46.4
    area = sum((n - s_) * (l - o) for s_, o, n, l in lista)
    assert isclose(area, 0.6 * 0.4, rel_tol=1e-6)


def test_juntar_extratos_nao_duplica_rua_da_fronteira():
    a = {"elements": [{"type": "node", "id": 1, "lat": 0, "lon": 0},
                      {"type": "way", "id": 9, "nodes": [1, 2]}]}
    b = {"elements": [{"type": "node", "id": 2, "lat": 0, "lon": 1},
                      {"type": "way", "id": 9, "nodes": [1, 2]}]}
    juntos = juntar_extratos([a, b])["elements"]
    assert sorted((e["type"], e["id"]) for e in juntos) == [("node", 1), ("node", 2), ("way", 9)]


def test_artefato_comprimido_com_geometria_preserva_rotas_e_tracado():
    """Grava contraido em .gz, le de volta: mesmos custos e mesmo desenho."""
    grafo = maior_componente_fortemente_conexo(grafo_bruto())
    contraido, geometria = contrair(grafo, limite_m=10_000)
    with tempfile.TemporaryDirectory() as pasta:
        caminho = os.path.join(pasta, "malha.json.gz")
        salvar_grafo(contraido, caminho, geometria=geometria)
        with open(caminho, "rb") as bruto:
            assert bruto.read(2) == b"\x1f\x8b", "tem de sair comprimido"
        lido, _semaforos, geo_lida = ler_artefato(caminho)
    assert set(lido.nos) == set(contraido.nos)
    for u in contraido.nos:
        for v, p in contraido.vizinhos(u):
            assert isclose(peso(lido, u, v), p, abs_tol=1e-3)
            for (a, b), (c, d) in zip(geo_lida.intermediarios(u, v),
                                      geometria.intermediarios(u, v)):
                assert isclose(a, c, abs_tol=1e-6) and isclose(b, d, abs_tol=1e-6)
            assert len(geo_lida.intermediarios(u, v)) == len(geometria.intermediarios(u, v))
            assert geo_lida.mesmo_tracado(u, v) == geometria.mesmo_tracado(u, v)
    origem = next(iter(grafo.nos))
    esperado = busca_caminho_minimo(grafo, origem, alvos=set()).distancias
    obtido = busca_caminho_minimo(lido, origem, alvos=set()).distancias
    for no, custo in obtido.items():
        assert isclose(custo, esperado[no], abs_tol=1e-2)


def test_gz_e_deterministico():
    """Mesmo grafo, mesmos bytes: o git nao ve mudanca onde nao houve."""
    grafo = maior_componente_fortemente_conexo(grafo_bruto())
    with tempfile.TemporaryDirectory() as pasta:
        a, b = os.path.join(pasta, "a.json.gz"), os.path.join(pasta, "b.json.gz")
        salvar_grafo(grafo, a)
        salvar_grafo(grafo, b)
        with open(a, "rb") as x, open(b, "rb") as y:
            assert x.read() == y.read()


# ------------------------------------------------------------- extrato .pbf

def _com_osmium():
    try:
        import osmium  # noqa: F401
        import shapely  # noqa: F401
        return True
    except ImportError:
        return False      # dependencia so da importacao offline


def test_pbf_recorta_pelo_contorno_como_a_overpass():
    """Via que toca o municipio entra INTEIRA; a de fora, a calcada e a area
    nao entram; o semaforo da via aceita vem com a etiqueta."""
    if not _com_osmium():
        return
    import osmium
    from infra.pbf import extrair_vias, ler_contorno

    with tempfile.TemporaryDirectory() as pasta:
        pbf = os.path.join(pasta, "mini.osm.pbf")
        contorno = os.path.join(pasta, "contorno.geojson")
        quadrado = [[-46.70, -23.60], [-46.60, -23.60], [-46.60, -23.50], [-46.70, -23.50], [-46.70, -23.60]]
        with open(contorno, "w", encoding="utf-8") as arquivo:
            json.dump({"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {},
                       "geometry": {"type": "Polygon", "coordinates": [quadrado]}}]}, arquivo)

        pontos = {1: (-23.55, -46.65), 2: (-23.55, -46.64), 3: (-23.55, -46.55),   # 3 fora
                  4: (-23.40, -46.40), 5: (-23.40, -46.39),                         # longe
                  6: (-23.56, -46.65), 7: (-23.56, -46.64)}
        escritor = osmium.SimpleWriter(pbf)
        for no, (lat, lon) in pontos.items():
            tags = {"highway": "traffic_signals"} if no == 2 else {}
            escritor.add_node(osmium.osm.mutable.Node(id=no, location=(lon, lat), tags=tags))
        vias = [(10, [1, 2, 3], {"highway": "primary"}),          # cruza a divisa: entra inteira
                (11, [4, 5], {"highway": "residential"}),         # fora
                (12, [6, 7], {"highway": "footway"}),             # carro nao passa
                (13, [6, 7], {"highway": "service", "area": "yes"})]
        for via, nos, tags in vias:
            escritor.add_way(osmium.osm.mutable.Way(id=via, nodes=nos, tags=tags))
        escritor.close()

        dados = extrair_vias(pbf, ler_contorno(contorno))

    vias_lidas = {e["id"]: e for e in dados["elements"] if e["type"] == "way"}
    nos_lidos = {e["id"]: e for e in dados["elements"] if e["type"] == "node"}
    assert set(vias_lidas) == {10}
    assert vias_lidas[10]["nodes"] == [1, 2, 3], "a via nao pode ser cortada na divisa"
    assert set(nos_lidos) == {1, 2, 3}
    assert nos_lidos[2].get("tags") == {"highway": "traffic_signals"}
    assert isclose(nos_lidos[3]["lon"], -46.55, abs_tol=1e-7)
    # O formato e o da Overpass: o resto do pipeline aceita sem adaptacao.
    grafo = construir_grafo(dados)
    assert set(grafo.nos) == {1, 2, 3} and grafo.total_arestas() == 4


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
