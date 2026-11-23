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

import gzip
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from algoritmos.busca import busca_caminho_minimo
from algoritmos.contracao import ESCALA, Geometria
from algoritmos.grafo import Grafo, haversine
from algoritmos.semaforo import Semaforo

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

# O OSM diz ONDE ha semaforo (no com highway=traffic_signals), mas nao a
# temporizacao. Presumimos ciclo de 90s com 40s de vermelho, ordem de grandeza
# de cruzamento arterial em Sao Paulo: E[espera] = 40^2 / (2*90) ~ 8,9s.
SEMAFORO_OSM = Semaforo(vermelho=40.0, ciclo=90.0)


# --------------------------------------------------------------------- rede

# Municipio de Sao Paulo no OSM: relacao 298285. A Overpass enderecava areas
# como 3600000000 + id da relacao.
AREA_MUNICIPIO_SP = 3600000000 + 298285


def montar_consulta(sul, oeste, norte, leste, timeout_s=90, area=None):
    """Monta a consulta Overpass QL da malha trafegavel dentro da caixa.

    Com `area`, recorta TAMBEM pelo limite administrativo: a caixa de um
    bloco que encosta na divisa nao traz as ruas de Osasco ou Guarulhos.
    """
    caixa = f"{sul},{oeste},{norte},{leste}"
    filtro_area = f"(area.alvo)" if area else ""
    return (
        f"[out:json][timeout:{timeout_s}];\n"
        + (f"area(id:{area})->.alvo;\n" if area else "")
        + f'way["highway"~"^({VIAS_TRAFEGAVEIS})$"]["area"!~"yes"]{filtro_area}({caixa});\n'
        f"(._;>;);\n"
        f"out body;"
    )


def blocos(sul, oeste, norte, leste, linhas, colunas):
    """Divide a caixa numa grade. A Overpass recusa (ou estoura o tempo em)
    uma cidade inteira de uma vez; em blocos do tamanho do extrato que ja
    funcionava (~300 km2) cada consulta passa folgada."""
    altura, largura = (norte - sul) / linhas, (leste - oeste) / colunas
    return [(round(sul + i * altura, 6), round(oeste + j * largura, 6),
             round(sul + (i + 1) * altura, 6), round(oeste + (j + 1) * largura, 6))
            for i in range(linhas) for j in range(colunas)]


def juntar_extratos(extratos):
    """Uniao de varios extratos, sem repetir elementos.

    Rua que cruza a fronteira de dois blocos vem nos dois (a consulta pede
    os nos de cada via, mesmo fora da caixa): a chave (tipo, id) a mantem
    uma vez so, e os trechos se emendam pelo id de no, que e o do OSM.
    """
    vistos = {}
    for dados in extratos:
        for elemento in dados.get("elements", []):
            vistos[(elemento["type"], elemento["id"])] = elemento
    return {"elements": list(vistos.values())}


def baixar_osm(sul, oeste, norte, leste, cache=None, tentativas=3, area=None):
    """Baixa o extrato da Overpass API, com cache em disco.

    O cache nao e conforto: a Overpass e um servico publico e gratuito, e
    refazer o download a cada boot seria abuso. Em producao o grafo deve ser
    pre-processado uma vez e versionado como artefato.
    """
    if cache and os.path.exists(cache):
        with open(cache, encoding="utf-8") as arquivo:
            return json.load(arquivo)

    consulta = montar_consulta(sul, oeste, norte, leste, timeout_s=180, area=area)
    corpo = urllib.parse.urlencode({"data": consulta}).encode()
    ultimo_erro = None

    for numero in range(tentativas):
        for espelho in ESPELHOS_OVERPASS:
            try:
                requisicao = urllib.request.Request(
                    espelho, data=corpo,
                    headers={"User-Agent": "TrueCompass/1.0 (projeto academico USJT)"},
                )
                with urllib.request.urlopen(requisicao, timeout=300) as resposta:
                    dados = json.loads(resposta.read().decode("utf-8"))
                if cache:
                    os.makedirs(os.path.dirname(cache) or ".", exist_ok=True)
                    with open(cache, "w", encoding="utf-8") as arquivo:
                        json.dump(dados, arquivo)
                return dados
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError,
                    ConnectionError, json.JSONDecodeError) as erro:
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


def semaforos_do_osm(dados_osm):
    """Nos marcados como semaforo no OSM: {id: (lat, lon)}."""
    return {
        elemento["id"]: (elemento["lat"], elemento["lon"])
        for elemento in dados_osm.get("elements", [])
        if elemento.get("type") == "node"
        and (elemento.get("tags") or {}).get("highway") == "traffic_signals"
    }


def construir_grafo(dados_osm, semaforo=SEMAFORO_OSM):
    """Converte o JSON da Overpass no nosso Grafo ponderado direcionado.

    Peso da aresta = distancia haversine / velocidade, em SEGUNDOS -- coerente
    com o resto do sistema, onde o que importa e tempo, nao distancia.

    Semaforo: o atraso esperado entra na aresta que CHEGA ao no semaforizado,
    mesma regra da matriz (e ali que se espera). `semaforo=None` ignora os
    sinais. Somar atraso so aumenta custo, entao a heuristica continua
    admissivel.
    """
    coordenadas = {}
    vias = []
    for elemento in dados_osm.get("elements", []):
        if elemento.get("type") == "node":
            coordenadas[elemento["id"]] = (elemento["lat"], elemento["lon"])
        elif elemento.get("type") == "way" and elemento.get("nodes"):
            vias.append(elemento)

    sinais = semaforos_do_osm(dados_osm) if semaforo else {}
    atraso = semaforo.atraso if semaforo else 0.0

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
                grafo.adicionar_aresta(anterior, atual,
                                       segundos + (atraso if atual in sinais else 0.0))
            if vale_volta:
                grafo.adicionar_aresta(atual, anterior,
                                       segundos + (atraso if anterior in sinais else 0.0))

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

def _ler_json(caminho):
    """JSON do artefato, comprimido ou nao (decide pelo .gz no nome)."""
    if caminho.endswith(".gz"):
        with gzip.open(caminho, "rt", encoding="utf-8") as arquivo:
            return json.load(arquivo)
    with open(caminho, encoding="utf-8") as arquivo:
        return json.load(arquivo)


def _gravar_json(dados, caminho):
    """Grava o artefato. O .gz e deterministico (sem data nem nome no
    cabecalho): o mesmo grafo gera os mesmos bytes, e o git nao ve mudanca
    onde nao houve."""
    texto = json.dumps(dados, separators=(",", ":")).encode("utf-8")
    if caminho.endswith(".gz"):
        texto = gzip.compress(texto, compresslevel=9, mtime=0)
    with open(caminho, "wb") as arquivo:
        arquivo.write(texto)


def _codificar_geometria(grafo, geometria):
    """[[u, v, deltas]] e [[v, u, 0]] para o sentido que reaproveita (u, v).

    Os pontos vao em microgaus e como DIFERENCA do anterior (o primeiro, do
    no u): numeros de 1 a 3 digitos em vez de 9, e o artefato encolhe.
    """
    saida, emitidos = [], set()
    for u in grafo.nos:
        for v, _peso in grafo.vizinhos(u):
            entrada = geometria.bruto(u, v)
            if entrada is None:
                continue
            valores, invertido = entrada
            volta = geometria.bruto(v, u)
            if (v, u) in emitidos and volta and volta[0] is valores:
                saida.append([u, v, 0])
                continue
            pontos = geometria.intermediarios(u, v)
            lat0, lon0 = grafo.coordenadas(u)
            anterior = (round(lat0 * ESCALA), round(lon0 * ESCALA))
            deltas = []
            for lat, lon in pontos:
                atual = (round(lat * ESCALA), round(lon * ESCALA))
                deltas += [atual[0] - anterior[0], atual[1] - anterior[1]]
                anterior = atual
            saida.append([u, v, deltas])
            emitidos.add((u, v))
    return saida


def _decodificar_geometria(grafo, linhas):
    geometria = Geometria()
    referencias = []
    for u, v, deltas in linhas:
        if deltas == 0:
            referencias.append((u, v))
            continue
        lat0, lon0 = grafo.coordenadas(u)
        lat, lon = round(lat0 * ESCALA), round(lon0 * ESCALA)
        pontos = []
        for i in range(0, len(deltas), 2):
            lat += deltas[i]
            lon += deltas[i + 1]
            pontos.append((lat / ESCALA, lon / ESCALA))
        geometria.definir(u, v, pontos)
    for u, v in referencias:
        geometria.compartilhar(u, v, v, u)
    return geometria


def salvar_grafo(grafo, caminho, semaforos=None, semaforo=SEMAFORO_OSM,
                 geometria=None):
    """Serializa o grafo ja processado, para o servidor subir rapido.

    Reconstruir a malha a partir do OSM leva minutos; ler este arquivo leva
    segundos. O artefato e gerado uma vez, offline, e versionado.

    `semaforos` ({id: (lat, lon)}) vai junto so para o front desenhar: o
    atraso ja esta nos pesos. Guardamos apenas os que sobreviveram a poda.
    `geometria` (da contracao) guarda a forma das ruas: sem ela, cada aresta
    contraida seria desenhada e medida como linha reta.
    """
    dados = {
        "versao": 2 if geometria is not None else 1,
        "nos": [[no, *grafo.coordenadas(no)] for no in grafo.nos],
        "arestas": [[o, d, round(p, 4)]
                    for o in grafo.nos for d, p in grafo.vizinhos(o)],
    }
    if semaforos:
        nos = set(grafo.nos)
        dados["semaforo"] = {"vermelho": semaforo.vermelho, "ciclo": semaforo.ciclo}
        dados["semaforos"] = [[no, lat, lon] for no, (lat, lon) in semaforos.items()
                              if no in nos]
    if geometria is not None:
        dados["geometria"] = _codificar_geometria(grafo, geometria)
    _gravar_json(dados, caminho)


def ler_artefato(caminho):
    """Le o artefato: devolve (grafo, semaforos, geometria).

    `semaforos` ja vem no formato de /malha/semaforos (lista de dicts); vazia
    em artefato antigo, gerado antes de os sinais serem importados.
    `geometria` e vazia em artefato sem contracao (versao 1): toda aresta e
    reta, que e exatamente o que ela era.
    """
    dados = _ler_json(caminho)
    grafo = Grafo()
    for no, lat, lon in dados["nos"]:
        grafo.adicionar_no(no, lat, lon)
    for origem, destino, peso in dados["arestas"]:
        grafo.adicionar_aresta(origem, destino, peso)

    temporizacao = dados.get("semaforo") or {}
    sinal = Semaforo(temporizacao.get("vermelho", SEMAFORO_OSM.vermelho),
                     temporizacao.get("ciclo", SEMAFORO_OSM.ciclo))
    semaforos = [
        {"lat": round(lat, 6), "lon": round(lon, 6), "vermelho": sinal.vermelho,
         "ciclo": sinal.ciclo, "atraso_medio": round(sinal.atraso, 2)}
        for _no, lat, lon in dados.get("semaforos", [])
    ]
    geometria = _decodificar_geometria(grafo, dados.get("geometria", []))
    return grafo, semaforos, geometria


def ids_dos_semaforos(caminho):
    """Ids dos nos semaforizados de um artefato (para preserva-los ao contrair)."""
    return {no for no, _lat, _lon in _ler_json(caminho).get("semaforos", [])}


def carregar_grafo(caminho):
    return ler_artefato(caminho)[0]
