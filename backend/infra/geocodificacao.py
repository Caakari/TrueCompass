# -*- coding: utf-8 -*-
"""Busca de lugares (geocodificacao) sobre servicos abertos do OpenStreetMap.

Camada de INFRAESTRUTURA: faz rede. `algoritmos/` e `dominio/` nao importam
daqui.

Dois servicos, cada um no papel que sua politica de uso permite:

- PHOTON (komoot) para o AUTOCOMPLETAR, enquanto a pessoa digita. Foi feito
  para isso: busca por prefixo, tolerante a erro de digitacao.
- NOMINATIM (OSMF) so quando a pessoa CONFIRMA a busca (Enter). A politica do
  Nominatim proibe autocompletar, mas ele acerta melhor nomes populares
  ("masp" -> Museu de Arte de Sao Paulo, onde o Photon devolve um cafe).

Por que pelo backend, e nao direto do navegador:

1. O Nominatim exige User-Agent identificando a aplicacao, e o navegador nao
   deixa o JavaScript definir User-Agent.
2. Cache e limite de taxa ficam num lugar so, para todos os usuarios.
3. O resultado ja sai recortado a area coberta pela malha: nao adianta
   oferecer um lugar onde o A* nao tem rua para chegar.
"""

import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import OrderedDict

URL_PHOTON = "https://photon.komoot.io"
URL_NOMINATIM = "https://nominatim.openstreetmap.org"
AGENTE = "TrueCompass/1.0 (projeto academico USJT; mobilidade urbana)"
TEMPO_LIMITE_S = 6.0


class GeocodificacaoIndisponivel(Exception):
    """Nenhum dos servicos respondeu."""


# ------------------------------------------------------------------ cache

class _CacheLRU:
    """Cache LRU com validade. Buscas se repetem muito (cada letra digitada
    gera um prefixo que outra pessoa ja digitou), e o servico e publico."""

    def __init__(self, capacidade=2048, validade_s=6 * 3600):
        self._itens = OrderedDict()
        self._capacidade = capacidade
        self._validade = validade_s
        self._trava = threading.Lock()

    def obter(self, chave):
        with self._trava:
            item = self._itens.get(chave)
            if item is None:
                return None
            instante, valor = item
            if time.monotonic() - instante > self._validade:
                del self._itens[chave]
                return None
            self._itens.move_to_end(chave)
            return valor

    def guardar(self, chave, valor):
        with self._trava:
            self._itens[chave] = (time.monotonic(), valor)
            self._itens.move_to_end(chave)
            while len(self._itens) > self._capacidade:
                self._itens.popitem(last=False)


_cache = _CacheLRU()

# Nominatim: no maximo 1 requisicao por segundo (politica de uso).
_trava_nominatim = threading.Lock()
_ultima_nominatim = [0.0]


def _baixar_json(url):
    requisicao = urllib.request.Request(url, headers={
        "User-Agent": AGENTE, "Accept-Language": "pt-BR,pt;q=0.9",
    })
    with urllib.request.urlopen(requisicao, timeout=TEMPO_LIMITE_S) as resposta:
        return json.loads(resposta.read().decode("utf-8"))


# ------------------------------------------------------------ normalizacao

# osm_key/osm_value -> categoria que o front transforma em icone.
_CATEGORIAS = {
    "university": "educacao", "college": "educacao", "school": "educacao",
    "kindergarten": "educacao", "library": "educacao",
    "hospital": "saude", "clinic": "saude", "pharmacy": "saude", "doctors": "saude",
    "restaurant": "comida", "cafe": "comida", "fast_food": "comida", "bar": "comida",
    "pub": "comida", "bakery": "comida", "ice_cream": "comida",
    "mall": "compras", "supermarket": "compras", "marketplace": "compras",
    "department_store": "compras", "convenience": "compras",
    "museum": "cultura", "theatre": "cultura", "cinema": "cultura",
    "arts_centre": "cultura", "attraction": "cultura", "gallery": "cultura",
    "park": "parque", "garden": "parque", "playground": "parque",
    "station": "transporte", "subway_entrance": "transporte", "bus_station": "transporte",
    "bus_stop": "transporte", "halt": "transporte", "platform": "transporte",
    "hotel": "hospedagem", "hostel": "hospedagem",
    "bank": "servico", "atm": "servico", "post_office": "servico",
    "police": "servico", "townhall": "servico", "place_of_worship": "religiao",
    "stadium": "esporte", "sports_centre": "esporte", "fitness_centre": "esporte",
}
_VIAS = {"primary", "secondary", "tertiary", "residential", "trunk", "motorway",
         "unclassified", "living_street", "pedestrian", "service"}
_REGIOES = {"suburb", "neighbourhood", "quarter", "city_district", "district",
            "city", "town", "village", "locality"}


def _categoria(chave, valor):
    if valor in _CATEGORIAS:
        return _CATEGORIAS[valor]
    if chave == "highway" and valor in _VIAS:
        return "rua"
    if chave in ("place", "boundary") or valor in _REGIOES:
        return "regiao"
    if chave == "railway":
        return "transporte"
    if valor in ("house", "house_number", "building", "yes", "residential"):
        return "endereco"
    return "lugar"


def _juntar(*partes):
    vistos, saida = set(), []
    for parte in partes:
        if parte and parte not in vistos:
            vistos.add(parte)
            saida.append(parte)
    return ", ".join(saida)


def _de_photon(feicao):
    p = feicao.get("properties", {})
    lon, lat = feicao["geometry"]["coordinates"][:2]
    rua = _juntar(p.get("street"), p.get("housenumber"))
    if p.get("name"):
        titulo = p["name"]
        detalhe = _juntar(rua, p.get("district") or p.get("locality"), p.get("city"))
    else:
        titulo = rua or p.get("district") or p.get("city") or "Local sem nome"
        detalhe = _juntar(p.get("locality"), p.get("district"), p.get("city"))
    categoria = _categoria(p.get("osm_key"), p.get("osm_value"))
    if not p.get("name") and p.get("housenumber"):
        categoria = "endereco"
    return {
        "id": f"{p.get('osm_type', '?')}{p.get('osm_id', '')}",
        "titulo": titulo,
        "detalhe": detalhe,
        "categoria": categoria,
        "lat": round(lat, 7), "lon": round(lon, 7),
    }


def _de_nominatim(item):
    endereco = item.get("address", {})
    rua = _juntar(endereco.get("road"), endereco.get("house_number"))
    nome = item.get("name")
    bairro = endereco.get("suburb") or endereco.get("neighbourhood") or endereco.get("quarter")
    cidade = endereco.get("city") or endereco.get("town") or endereco.get("municipality")
    tipo_osm = (item.get("osm_type") or "?")[:1].upper()
    return {
        "id": f"{tipo_osm}{item.get('osm_id', '')}",
        "titulo": nome or rua or bairro or "Local sem nome",
        "detalhe": _juntar(rua if nome else None, bairro, cidade),
        "categoria": _categoria(item.get("category"), item.get("type")),
        "lat": round(float(item["lat"]), 7), "lon": round(float(item["lon"]), 7),
    }


def _dentro(lugar, caixa):
    return (caixa["sul"] <= lugar["lat"] <= caixa["norte"]
            and caixa["oeste"] <= lugar["lon"] <= caixa["leste"])


def _sem_repetidos(lugares):
    """O OSM tem o mesmo lugar como no E como area: mesmo titulo a menos de
    ~50 m conta como repetido. Rua e mais agressivo -- cada quarteirao e um
    `way` separado, e "Rua Augusta" viria oito vezes; ate ~2 km e a mesma."""
    saida = []
    for lugar in lugares:
        raio = 0.02 if lugar["categoria"] == "rua" else 5e-4
        repetido = any(
            lugar["titulo"] == outro["titulo"]
            and abs(lugar["lat"] - outro["lat"]) < raio
            and abs(lugar["lon"] - outro["lon"]) < raio
            for outro in saida
        )
        if not repetido:
            saida.append(lugar)
    return saida


# ------------------------------------------------------------------ buscas

def _photon(texto, caixa, perto, limite):
    parametros = {
        "q": texto, "limit": limite * 2,
        "bbox": f"{caixa['oeste']},{caixa['sul']},{caixa['leste']},{caixa['norte']}",
    }
    if perto:
        # Vies de proximidade: "padaria" deve trazer a padaria perto de voce.
        parametros["lat"], parametros["lon"] = perto
    dados = _baixar_json(f"{URL_PHOTON}/api/?{urllib.parse.urlencode(parametros)}")
    return [_de_photon(f) for f in dados.get("features", [])]


def _nominatim(texto, caixa, limite):
    parametros = {
        "q": texto, "format": "jsonv2", "addressdetails": 1, "limit": limite,
        "viewbox": f"{caixa['oeste']},{caixa['norte']},{caixa['leste']},{caixa['sul']}",
        "bounded": 1, "countrycodes": "br", "accept-language": "pt-BR",
    }
    with _trava_nominatim:
        espera = 1.0 - (time.monotonic() - _ultima_nominatim[0])
        if espera > 0:
            time.sleep(espera)
        try:
            return [_de_nominatim(i) for i in _baixar_json(
                f"{URL_NOMINATIM}/search?{urllib.parse.urlencode(parametros)}")]
        finally:
            _ultima_nominatim[0] = time.monotonic()


def buscar_lugares(texto, caixa, perto=None, limite=8, completo=False):
    """Lugares cujo nome/endereco casa com `texto`, dentro de `caixa`.

    completo=False -> so Photon (autocompletar, a cada tecla).
    completo=True  -> Nominatim primeiro, completado pelo Photon (busca
                      confirmada com Enter).
    """
    texto = " ".join(texto.split())
    if len(texto) < 2:
        return []

    # A posicao entra arredondada (~1 km) na chave: muda pouco o resultado e
    # deixa o cache servir a quem esta no mesmo bairro.
    perto_chave = (round(perto[0], 2), round(perto[1], 2)) if perto else None
    chave = ("busca", texto.lower(), completo, perto_chave, limite,
             tuple(round(v, 4) for v in caixa.values()))
    guardado = _cache.obter(chave)
    if guardado is not None:
        return guardado

    resultados, falhas = [], 0
    fontes = [lambda: _nominatim(texto, caixa, limite)] if completo else []
    fontes.append(lambda: _photon(texto, caixa, perto, limite))
    for fonte in fontes:
        try:
            resultados.extend(fonte())
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError, OSError):
            falhas += 1
    if falhas == len(fontes):
        raise GeocodificacaoIndisponivel("servico de busca de lugares fora do ar")

    saida = _sem_repetidos([r for r in resultados if _dentro(r, caixa)])[:limite]
    _cache.guardar(chave, saida)
    return saida


def endereco_do_ponto(lat, lon):
    """Geocodificacao reversa: o endereco mais proximo de (lat, lon), ou None."""
    chave = ("reverso", round(lat, 5), round(lon, 5))
    guardado = _cache.obter(chave)
    if guardado is not None:
        return guardado or None

    parametros = urllib.parse.urlencode({"lat": lat, "lon": lon, "limit": 1})
    try:
        feicoes = _baixar_json(f"{URL_PHOTON}/reverse?{parametros}").get("features", [])
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as erro:
        raise GeocodificacaoIndisponivel(str(erro)) from erro
    lugar = _de_photon(feicoes[0]) if feicoes else {}
    if lugar:
        # O ponto e o que a pessoa marcou, nao o do endereco achado.
        lugar["lat"], lugar["lon"] = round(lat, 7), round(lon, 7)
    _cache.guardar(chave, lugar)
    return lugar or None
