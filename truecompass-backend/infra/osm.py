# -*- coding: utf-8 -*-
"""Carga da malha viaria real a partir do OpenStreetMap.

Camada de INFRAESTRUTURA: faz rede e disco. O pacote `algoritmos/` permanece
puro e nao importa nada daqui -- a seta de dependencia aponta sempre para
dentro.

Optamos por consultar a Overpass API diretamente e montar o nosso `Grafo` em
vez de usar OSMnx. Duas razoes: a disciplina exige implementacao propria das
estruturas, e OSMnx arrastaria geopandas/shapely/networkx, pesados demais para
o deploy.
"""

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from algoritmos.busca import busca_caminho_minimo
from algoritmos.grafo import Grafo, haversine

ESPELHOS_OVERPASS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.osm.ch/api/interpreter",
)

# Vias trafegaveis por automovel. Deliberadamente fora: footway, cycleway,
# path, steps, pedestrian e track -- carro nao passa.
VIAS_TRAFEGAVEIS = (
    "motorway|trunk|primary|secondary|tertiary|unclassified|residential|"
    "living_street|motorway_link|trunk_link|primary_link|secondary_link|"
    "tertiary_link"
)

# Velocidades padrao (km/h) para quando a via nao declara maxspeed.
# Calibradas para contexto urbano brasileiro.
VELOCIDADE_PADRAO = {
    "motorway": 100.0, "motorway_link": 60.0,
    "trunk": 80.0, "trunk_link": 50.0,
    "primary": 60.0, "primary_link": 40.0,
    "secondary": 50.0, "secondary_link": 40.0,
    "tertiary": 40.0, "tertiary_link": 30.0,
    "unclassified": 30.0,
    "residential": 30.0,
    "living_street": 20.0,
}
VELOCIDADE_FALLBACK = 30.0


# --------------------------------------------------------------------- rede

def montar_consulta(sul, oeste, norte, leste, timeout_s=90):
    """Monta a consulta Overpass QL da malha trafegavel dentro da caixa."""
    caixa = f"{sul},{oeste},{norte},{leste}"
    return (
        f"[out:json][timeout:{timeout_s}];\n"
        f'way["highway"~"^({VIAS_TRAFEGAVEIS})$"]["area"!~"yes"]({caixa});\n'
        f"(._;>;);\n"
        f"out body;"
    )


def baixar_osm(sul, oeste, norte, leste, cache=None, tentativas=3):
    """Baixa o extrato da Overpass API, com cache em disco.

    O cache nao e conforto: a Overpass e um servico publico e gratuito, e
    refazer o download a cada boot seria abuso. Em producao o grafo deve ser
    pre-processado uma vez e versionado como artefato.
    """
    if cache and os.path.exists(cache):
        with open(cache, encoding="utf-8") as arquivo:
            return json.load(arquivo)

    consulta = montar_consulta(sul, oeste, norte, leste)
    corpo = urllib.parse.urlencode({"data": consulta}).encode()
    ultimo_erro = None

    for numero in range(tentativas):
        for espelho in ESPELHOS_OVERPASS:
            try:
                requisicao = urllib.request.Request(
                    espelho, data=corpo,
                    headers={"User-Agent": "TrueCompass/1.0 (projeto academico USJT)"},
                )
                with urllib.request.urlopen(requisicao, timeout=180) as resposta:
                    dados = json.loads(resposta.read().decode("utf-8"))
                if cache:
                    os.makedirs(os.path.dirname(cache) or ".", exist_ok=True)
                    with open(cache, "w", encoding="utf-8") as arquivo:
                        json.dump(dados, arquivo)
                return dados
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as erro:
                ultimo_erro = erro
        if numero < tentativas - 1:
            time.sleep(2 ** numero)  # recuo exponencial entre rodadas

    raise RuntimeError(
        f"nao foi possivel baixar o extrato do OpenStreetMap: {ultimo_erro}"
    )


# ------------------------------------------------------------------ parsing

def _velocidade_kmh(tags):
    """Le maxspeed; se ausente ou ilegivel, usa o padrao do tipo de via."""
    bruto = (tags.get("maxspeed") or "").strip().lower()
    if bruto and bruto not in ("none", "signals", "variable", "walk"):
        try:
            if "mph" in bruto:
                return float(bruto.replace("mph", "").strip()) * 1.609344
            return float(bruto.split()[0])
        except (ValueError, IndexError):
            pass  # etiqueta malformada: cai no padrao
    return VELOCIDADE_PADRAO.get(tags.get("highway", ""), VELOCIDADE_FALLBACK)


def _sentidos(tags):
    """Decide a direcionalidade da via: (vale_ida, vale_volta).

    Trata as tres convencoes do OSM: a etiqueta `oneway` explicita, rotatoria
    (`junction`), e a regra implicita de que rodovia expressa (`motorway`) e
    de mao unica mesmo sem etiqueta.
    """
    oneway = (tags.get("oneway") or "").strip().lower()
    if oneway in ("yes", "true", "1"):
        return True, False
    if oneway in ("-1", "reverse"):
        return False, True
    if oneway in ("no", "false", "0"):
        return True, True

    if (tags.get("junction") or "").lower() in ("roundabout", "circular"):
        return True, False
    if tags.get("highway") in ("motorway", "motorway_link"):
        return True, False
    return True, True


def construir_grafo(dados_osm):
    """Converte o JSON da Overpass no nosso Grafo ponderado direcionado.

    Peso da aresta = distancia haversine / velocidade, em SEGUNDOS -- coerente
    com o resto do sistema, onde o que importa e tempo, nao distancia.
    """
    coordenadas = {}
    vias = []
    for elemento in dados_osm.get("elements", []):
        if elemento.get("type") == "node":
            coordenadas[elemento["id"]] = (elemento["lat"], elemento["lon"])
        elif elemento.get("type") == "way" and elemento.get("nodes"):
            vias.append(elemento)

    grafo = Grafo()
    usados = set()

    for via in vias:
        tags = via.get("tags", {})
        if "highway" not in tags:
            continue
        metros_por_s = _velocidade_kmh(tags) / 3.6
        vale_ida, vale_volta = _sentidos(tags)
        sequencia = [n for n in via["nodes"] if n in coordenadas]

        for anterior, atual in zip(sequencia, sequencia[1:]):
            if anterior == atual:
                continue
            for no in (anterior, atual):
                if no not in usados:
                    grafo.adicionar_no(no, *coordenadas[no])
                    usados.add(no)
            lat1, lon1 = coordenadas[anterior]
            lat2, lon2 = coordenadas[atual]
            segundos = haversine(lat1, lon1, lat2, lon2) / metros_por_s
            if segundos <= 0:
                continue  # nos duplicados na mesma coordenada
            if vale_ida:
                grafo.adicionar_aresta(anterior, atual, segundos)
            if vale_volta:
                grafo.adicionar_aresta(atual, anterior, segundos)

    return grafo


# ------------------------------------------------------- componente conexo

def maior_componente_fortemente_conexo(grafo):
    """Poda a malha ao componente fortemente conexo do no mais conectado.

    POR QUE ISSO E OBRIGATORIO: um extrato recortado por caixa delimitadora
    corta vias na borda. O resultado tem fragmentos isolados e armadilhas de
    mao unica -- trechos em que se entra e dos quais nao se sai. Se um
    motorista parar num desses, o pareamento nunca o encontra, ou pior,
    encontra e a rota nao existe.

    O metodo e o passo central do algoritmo de Kosaraju, e reaproveita o grafo
    reverso que ja construimos: o componente fortemente conexo que contem a
    semente e exatamente a intersecao entre o que ela ALCANCA (no grafo
    normal) e o que ALCANCA ela (no grafo reverso).

    Ressalva honesta: isso devolve o componente da semente, nao o
    comprovadamente maior. Para malha viaria, com a semente escolhida pelo
    maior grau, e na pratica o componente gigante.
    """
    if not grafo.nos:
        return grafo

    semente = max(grafo.nos, key=lambda no: len(dict(grafo.vizinhos(no))))
    alcanca = set(busca_caminho_minimo(grafo, semente, alvos=set()).distancias)
    alcancado_por = set(
        busca_caminho_minimo(grafo.reverso(), semente, alvos=set()).distancias
    )
    return grafo.subgrafo(alcanca & alcancado_por)


# -------------------------------------------------------------- orquestracao

def carregar_malha(sul, oeste, norte, leste, cache=None, podar=True):
    """Ponto de entrada: caixa delimitadora -> Grafo pronto para uso."""
    grafo = construir_grafo(baixar_osm(sul, oeste, norte, leste, cache=cache))
    return maior_componente_fortemente_conexo(grafo) if podar else grafo


# ------------------------------------------------- serializacao para o boot

def salvar_grafo(grafo, caminho):
    """Serializa o grafo ja processado, para o servidor subir rapido.

    Reconstruir a malha a partir do OSM leva dezenas de segundos; ler este
    arquivo leva fracoes. O artefato e gerado uma vez, offline, e versionado.
    """
    dados = {
        "nos": [[no, *grafo.coordenadas(no)] for no in grafo.nos],
        "arestas": [[o, d, round(p, 4)]
                    for o in grafo.nos for d, p in grafo.vizinhos(o)],
    }
    with open(caminho, "w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, separators=(",", ":"))


def carregar_grafo(caminho):
    with open(caminho, encoding="utf-8") as arquivo:
        dados = json.load(arquivo)
    grafo = Grafo()
    for no, lat, lon in dados["nos"]:
        grafo.adicionar_no(no, lat, lon)
    for origem, destino, peso in dados["arestas"]:
        grafo.adicionar_aresta(origem, destino, peso)
    return grafo
