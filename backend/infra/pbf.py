# -*- coding: utf-8 -*-
"""Leitura de extrato .osm.pbf, alternativa a Overpass para a cidade inteira.

POR QUE EXISTE: a Overpass recusa conexoes de varios datacenters (e o caso do
ambiente em que a malha foi gerada), e uma cidade inteira por consulta e
pesada para um servico publico. Os extratos por estado da OSM Franca sao
arquivos estaticos, atualizados diariamente:

    https://download.openstreetmap.fr/extracts/south-america/brazil/southeast/sao-paulo-latest.osm.pbf

O recorte imita a consulta da Overpass com area (`montar_consulta(area=...)`):
fica toda via TRAFEGAVEL que tem pelo menos um no dentro do contorno do
municipio, com TODOS os seus nos (inclusive os de fora, para a rua nao ser
cortada no meio). A saida tem o mesmo formato `{"elements": [...]}` da
Overpass, entao `construir_grafo`, a poda e a contracao seguem iguais.

Dependencias (`osmium`, `shapely`) so para a importacao offline, em
`requirements-importacao.txt`: o servidor no Railway nao as instala.
"""

import json
import re
import time
import urllib.parse
import urllib.request

from infra.osm import VIAS_TRAFEGAVEIS

URL_NOMINATIM = "https://nominatim.openstreetmap.org/lookup"
AGENTE = "TrueCompass/1.0 (projeto academico USJT)"
_VIA = re.compile(f"^({VIAS_TRAFEGAVEIS})$")


def baixar_contorno(relacao, caminho):
    """Contorno de uma relacao administrativa (GeoJSON), via Nominatim.

    Uma chamada so, com cache em disco: a politica do Nominatim pede uso
    moderado, e o contorno de um municipio nao muda de um dia para o outro.
    """
    parametros = urllib.parse.urlencode({
        "osm_ids": f"R{relacao}", "format": "geojson",
        "polygon_geojson": 1, "polygon_threshold": 0.0001,
    })
    requisicao = urllib.request.Request(f"{URL_NOMINATIM}?{parametros}",
                                        headers={"User-Agent": AGENTE})
    with urllib.request.urlopen(requisicao, timeout=60) as resposta:
        dados = json.loads(resposta.read().decode("utf-8"))
    if not dados.get("features"):
        raise RuntimeError(f"Nominatim nao conhece a relacao {relacao}")
    with open(caminho, "w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo)
    return dados


def ler_contorno(caminho):
    """Geometria shapely (Polygon/MultiPolygon) do primeiro feature do GeoJSON."""
    from shapely.geometry import shape
    with open(caminho, encoding="utf-8") as arquivo:
        dados = json.load(arquivo)
    feicao = dados["features"][0] if "features" in dados else dados
    return shape(feicao["geometry"])


def extrair_vias(caminho_pbf, contorno, progresso=None):
    """Vias trafegaveis que tocam o `contorno`, no formato da Overpass.

    Uma passada so pelo arquivo. `with_locations` guarda a coordenada de cada
    no ANTES do filtro por etiqueta, entao a via chega com a geometria
    completa; o filtro `highway` (em C++) evita que milhoes de nos sem
    etiqueta passem pelo Python.
    """
    import osmium
    from shapely import contains_xy, prepare

    prepare(contorno)
    oeste, sul, leste, norte = contorno.bounds

    vias, nos, sinais = [], {}, {}
    contagem = 0
    inicio = time.perf_counter()
    processador = (osmium.FileProcessor(caminho_pbf)
                   .with_locations()
                   .with_filter(osmium.filter.KeyFilter("highway")))
    for objeto in processador:
        contagem += 1
        if progresso and contagem % 500_000 == 0:
            progresso(contagem, time.perf_counter() - inicio)

        if objeto.is_node():
            # Semaforo em qualquer lugar: so entra se a via dele entrar.
            if objeto.tags.get("highway") == "traffic_signals":
                sinais[objeto.id] = (objeto.location.lat, objeto.location.lon)
            continue
        if not objeto.is_way():
            continue

        tags = objeto.tags
        if not _VIA.match(tags.get("highway", "")) or tags.get("area") == "yes":
            continue
        pontos = [(no.ref, no.location) for no in objeto.nodes if no.location.valid()]
        if len(pontos) < 2:
            continue
        lons = [loc.lon for _, loc in pontos]
        lats = [loc.lat for _, loc in pontos]
        # Pre-filtro barato pela caixa; o teste fino e o do poligono.
        if max(lons) < oeste or min(lons) > leste or max(lats) < sul or min(lats) > norte:
            continue
        if not contains_xy(contorno, lons, lats).any():
            continue

        vias.append({"type": "way", "id": objeto.id,
                     "nodes": [ref for ref, _ in pontos], "tags": dict(tags)})
        for ref, loc in pontos:
            nos[ref] = (loc.lat, loc.lon)

    elementos = []
    for ref, (lat, lon) in nos.items():
        elemento = {"type": "node", "id": ref, "lat": lat, "lon": lon}
        if ref in sinais:
            elemento["tags"] = {"highway": "traffic_signals"}
        elementos.append(elemento)
    elementos.extend(vias)
    return {"elements": elementos}
