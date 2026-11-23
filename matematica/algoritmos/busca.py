"""Busca de caminho minimo unificada: Dijkstra e A* sao a MESMA funcao.

    Dijkstra  = busca_caminho_minimo(..., h=None)        -> h(v) = 0
    A*        = busca_caminho_minimo(..., h=heuristica)  -> h(v) > 0

A unica diferenca entre os dois e a CHAVE usada na fila de prioridade:

    Dijkstra ordena por  g(v)           -> expande em circulo, para todo lado
    A*       ordena por  g(v) + h(v)    -> expande em gota, apontada ao destino

onde g(v) e o custo ja percorrido de s ate v, e h(v) e a estimativa otimista
do que falta de v ate o destino.
"""

import heapq
from dataclasses import dataclass, field
from math import inf


@dataclass
class Resultado:
    """Saida de uma busca."""

    custos: dict = field(default_factory=dict)
    """Alvos resolvidos -> custo definitivo (em segundos)."""

    distancias: dict = field(default_factory=dict)
    """Todo no alcancado -> melhor custo conhecido."""

    anterior: dict = field(default_factory=dict)
    """Arvore de caminhos minimos: anterior[v] = no de onde chegamos em v."""

    nos_expandidos: int = 0
    """Quantos vertices sairam da fila. E a metrica honesta de eficiencia:
    Dijkstra e A* tem a mesma complexidade de pior caso, O((V+E) log V) --
    o ganho do A* aparece aqui, no caso medio."""

    nao_alcancados: set = field(default_factory=set)
    """Alvos que ficaram fora do limite de custo ou sao inalcancaveis."""


def busca_caminho_minimo(grafo, origem, alvos, h=None, limite=inf):
    """Caminho minimo de `origem` ate `alvos`, com parada antecipada.

    Parametros
    ----------
    grafo  : objeto com .vizinhos(no) -> iteravel de (vizinho, peso).
             Passe o grafo normal para rotas; o grafo REVERSO para matching.
    origem : vertice de partida (unico).
    alvos  : conjunto de vertices procurados. A busca para assim que todos
             tiverem sido extraidos da fila -- nao varre a cidade inteira.
             Conjunto vazio = sem parada antecipada, explora tudo que o
             `limite` permitir (util para depurar ou medir o pior caso).
    h      : heuristica admissivel h(v) -> custo estimado de v ate o alvo.
             None (padrao) => Dijkstra.
    limite : orcamento maximo de custo. Nos alem disso nem entram na fila.

    Por que a parada antecipada e correta
    -------------------------------------
    Com pesos nao negativos, quando um vertice e EXTRAIDO da fila seu custo
    ja e definitivo -- e exatamente o passo indutivo da secao 5.1 da
    documentacao. Entao basta contar os alvos ja extraidos e parar no zero.
    """
    alvos = set(alvos)

    # Guarda contra a unica armadilha real desta unificacao: com varios alvos
    # a heuristica teria de ser admissivel para todos ao mesmo tempo, e ela
    # enfraquece conforme os alvos sao resolvidos. Nao compensa: use h=0.
    if h is not None and len(alvos) > 1:
        raise ValueError(
            "Heuristica so e valida com um unico alvo. Para busca multi-alvo "
            "(matching de motoristas) use h=None, ou seja, Dijkstra."
        )

    if h is None:
        def h(_no):
            return 0.0

    resultado = Resultado()
    resultado.distancias[origem] = 0.0
    faltam = set(alvos)
    explorar_tudo = not alvos
    visitados = set()

    # Cada item e (f, g, no). Guardamos g junto para nao recalcular nada.
    fila = [(h(origem), 0.0, origem)]

    while fila and (faltam or explorar_tudo):
        _f, g, u = heapq.heappop(fila)

        # "Lazy deletion": o heapq do Python nao tem DECREASE_KEY, entao
        # empurramos entradas duplicadas e descartamos as obsoletas aqui.
        # Efeito pratico identico, e sem estrutura de dados extra.
        if u in visitados:
            continue
        visitados.add(u)
        resultado.nos_expandidos += 1

        if u in faltam:
            resultado.custos[u] = g   # definitivo neste exato momento
            faltam.discard(u)
            if not faltam:
                break

        for v, peso in grafo.vizinhos(u):
            novo = g + peso
            if novo > limite:
                continue  # estourou o orcamento: nem vale entrar na fila
            if novo < resultado.distancias.get(v, inf):
                resultado.distancias[v] = novo
                resultado.anterior[v] = u
                heapq.heappush(fila, (novo + h(v), novo, v))

    resultado.nao_alcancados = faltam
    return resultado


def reconstruir_caminho(anterior, origem, destino):
    """Caminho [origem, ..., destino] no grafo em que a busca rodou.

    Use para a ROTA DA CORRIDA (busca no grafo normal).
    """
    if origem == destino:
        return [origem]
    if destino not in anterior:
        return []
    caminho = [destino]
    while caminho[-1] != origem:
        caminho.append(anterior[caminho[-1]])
    caminho.reverse()
    return caminho


def caminho_ate_origem(anterior, no, origem):
    """Caminho [no, ..., origem] SEM inverter no final.

    Use para o MATCHING (busca no grafo reverso). A sacada:
    a busca rodou de p para m no grafo reverso, mas seguir os ponteiros
    `anterior` a partir de m, na ordem natural de leitura, ja entrega a
    rota real m -> ... -> p no grafo ORIGINAL. Cada par consecutivo e uma
    aresta valida de G, porque as arestas do reverso sao as de G invertidas.

    Ou seja: UMA busca devolve as rotas de TODOS os motoristas, de graca.
    """
    if no == origem:
        return [no]
    if no not in anterior:
        return []
    caminho = [no]
    while caminho[-1] != origem:
        caminho.append(anterior[caminho[-1]])
    return caminho
