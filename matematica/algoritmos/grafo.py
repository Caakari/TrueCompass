"""Modelagem da malha viaria como grafo ponderado direcionado.

Referencia: Documentacao_Tecnica secao 2.1 -- G = (V, E, w), com w: E -> R+.
A representacao e lista de adjacencia, custo de espaco O(V + E).
"""

from math import asin, cos, inf, radians, sin, sqrt

RAIO_TERRA_M = 6_371_000.0


def haversine(lat1, lon1, lat2, lon2):
    """Distancia em metros sobre a superficie da Terra (grande circulo).

    E o menor caminho fisicamente possivel entre dois pontos, logo nunca
    superestima a distancia real por ruas. Essa propriedade e o que torna
    a heuristica do A* admissivel.
    """
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * RAIO_TERRA_M * asin(sqrt(a))


class Grafo:
    """Grafo direcionado com pesos e coordenadas geograficas por vertice.

    Os pesos representam TEMPO DE VIAGEM em segundos (e nao distancia):
    o que interessa ao passageiro e quem chega antes, nao quem esta mais perto.
    """

    def __init__(self):
        self._adjacencia = {}   # no -> {vizinho: peso}
        self._coordenadas = {}  # no -> (lat, lon)
        self._cache_reverso = None
        self._cache_vmax = None

    # ---------------------------------------------------------------- escrita

    def adicionar_no(self, no, lat, lon):
        self._adjacencia.setdefault(no, {})
        self._coordenadas[no] = (lat, lon)
        self._cache_reverso = None
        self._cache_vmax = None

    def adicionar_aresta(self, origem, destino, peso):
        """Adiciona uma rua de mao unica (origem -> destino)."""
        if peso < 0:
            raise ValueError(
                "Dijkstra/A* exigem pesos nao negativos: a prova de corretude "
                "por inducao depende disso (secao 5.1 da documentacao)."
            )
        self._adjacencia.setdefault(origem, {})[destino] = peso
        self._adjacencia.setdefault(destino, {})
        self._cache_reverso = None
        self._cache_vmax = None

    def adicionar_rua_mao_dupla(self, a, b, peso):
        self.adicionar_aresta(a, b, peso)
        self.adicionar_aresta(b, a, peso)

    def atualizar_peso(self, origem, destino, novo_peso):
        """Atualiza o custo de uma rua (ex.: transito em tempo real).

        Mantem o grafo reverso em sincronia, se ele ja tiver sido construido.
        Esquecer isso e o bug classico: o matching passa a usar tempos antigos.
        """
        if destino not in self._adjacencia.get(origem, {}):
            raise KeyError(f"aresta {origem} -> {destino} nao existe")
        self._adjacencia[origem][destino] = novo_peso
        if self._cache_reverso is not None:
            self._cache_reverso._adjacencia[destino][origem] = novo_peso
        # Peso menor pode elevar a velocidade maxima -- e com ela o divisor da
        # heuristica. Manter o valor antigo deixaria h superestimar.
        self._cache_vmax = None

    # ---------------------------------------------------------------- leitura

    def vizinhos(self, no):
        """Devolve pares (vizinho, peso). Usado pelo laco de relaxamento."""
        return self._adjacencia.get(no, {}).items()

    def coordenadas(self, no):
        return self._coordenadas[no]

    @property
    def nos(self):
        return self._adjacencia.keys()

    def total_arestas(self):
        return sum(len(v) for v in self._adjacencia.values())

    def velocidade_maxima_kmh(self):
        """Maior velocidade efetiva entre todas as arestas: distancia / peso.

        E o divisor MAIS APERTADO que ainda deixa a heuristica admissivel: se
        nenhuma aresta e percorrida mais rapido que v_max, nenhum caminho o e,
        e linha_reta / v_max nunca superestima. Um teto fixo arriscaria os
        dois erros: baixo demais (a malha real de SP tem marginal a 110 km/h,
        acima dos 100 que estavam fixos) quebra a admissibilidade; alto demais
        enfraquece h e o A* degenera em Dijkstra.

        O(E), calculado uma vez e mantido em cache ate a proxima escrita.
        Aresta de peso zero e comprimento positivo daria velocidade infinita:
        devolve inf, e h vira 0 -- o A* recai com seguranca no Dijkstra.
        """
        if self._cache_vmax is None:
            maxima = 0.0
            for origem, saidas in self._adjacencia.items():
                lat1, lon1 = self._coordenadas[origem]
                for destino, peso in saidas.items():
                    metros = haversine(lat1, lon1, *self._coordenadas[destino])
                    if peso > 0:
                        maxima = max(maxima, metros / peso)
                    elif metros > 0:
                        maxima = inf
            self._cache_vmax = maxima * 3.6
        return self._cache_vmax

    # ---------------------------------------------------------------- reverso

    def subgrafo(self, nos):
        """Novo grafo contendo apenas `nos` e as arestas entre eles.

        Usado para podar a malha ao maior componente fortemente conexo: um
        extrato do OpenStreetMap recortado por caixa delimitadora sempre traz
        fragmentos soltos e armadilhas de mao unica que nunca voltam.
        """
        nos = set(nos)
        recorte = Grafo()
        for no in nos:
            lat, lon = self._coordenadas[no]
            recorte.adicionar_no(no, lat, lon)
        for origem in nos:
            for destino, peso in self._adjacencia.get(origem, {}).items():
                if destino in nos:
                    recorte.adicionar_aresta(origem, destino, peso)
        return recorte

    def reverso(self):
        """Grafo com todas as setas invertidas, mesmos pesos.

        Vale a identidade que sustenta o matching many-to-one:

            dist_{G_reverso}(p, m) == dist_G(m, p)

        Ou seja: UMA busca partindo do passageiro no grafo reverso devolve
        o tempo de TODOS os motoristas ate ele. Construido uma unica vez e
        mantido em cache -- nunca por requisicao.
        """
        if self._cache_reverso is not None:
            return self._cache_reverso

        reverso = Grafo()
        reverso._coordenadas = self._coordenadas
        reverso._adjacencia = {no: {} for no in self._adjacencia}
        for origem, saidas in self._adjacencia.items():
            for destino, peso in saidas.items():
                reverso._adjacencia[destino][origem] = peso

        reverso._cache_reverso = self
        reverso._cache_vmax = self._cache_vmax
        self._cache_reverso = reverso
        return reverso


def heuristica_haversine(grafo, destino, velocidade_max_kmh=None):
    """Constroi h(v) para o A*, em segundos.

    h(v) = distancia_em_linha_reta(v, destino) / velocidade_maxima

    ADMISSIVEL: a linha reta nunca e maior que o caminho por ruas, e nenhum
    carro anda mais rapido que a velocidade maxima -- logo h nunca superestima.
    CONSISTENTE: vale a desigualdade triangular h(u) <= w(u,v) + h(v).

    Se voce esquecer de dividir pela velocidade, h vira "metros" enquanto os
    pesos sao "segundos": a heuristica superestima, deixa de ser admissivel
    e o A* passa a devolver rotas erradas. O teste-oraculo pega isso.

    Sem `velocidade_max_kmh`, usa a velocidade maxima medida no proprio grafo
    (ver Grafo.velocidade_maxima_kmh) -- o teto mais apertado e admissivel.
    """
    if velocidade_max_kmh is None:
        velocidade_max_kmh = grafo.velocidade_maxima_kmh()
    if velocidade_max_kmh in (0, inf):
        return lambda _no: 0.0
    velocidade_max_ms = velocidade_max_kmh / 3.6
    lat_d, lon_d = grafo.coordenadas(destino)

    def h(no):
        lat, lon = grafo.coordenadas(no)
        return haversine(lat, lon, lat_d, lon_d) / velocidade_max_ms

    return h
