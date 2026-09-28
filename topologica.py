# -*- coding: utf-8 -*-
"""Ordenacao topologica pelo algoritmo de Kahn.

Referencia: Documentacao_Tecnica secao 4.2. Complexidade O(V + E): cada
vertice e cada aresta sao processados exatamente uma vez.

Modulo generico -- nao sabe nada sobre corridas. O DAG especifico do ciclo de
vida da corrida vive em `dominio/estados.py`.
"""

from collections import deque


class CicloDetectado(Exception):
    """O grafo tem ciclo, logo nao admite ordenacao topologica.

    No dominio da aplicacao isso significa fluxo de corrida invalido: existiria
    uma sequencia de estados que volta a si mesma, e uma corrida poderia, por
    exemplo, ser paga antes de comecar.
    """

    def __init__(self, restantes):
        self.restantes = set(restantes)
        super().__init__(
            "ciclo detectado: fluxo invalido envolvendo "
            f"{sorted(map(str, self.restantes))}"
        )


def ordenacao_topologica(dag):
    """Ordem linear em que toda aresta (u, v) satisfaz posicao(u) < posicao(v).

    Parametros
    ----------
    dag : dict {vertice: [sucessores]}

    Levanta `CicloDetectado` se o grafo nao for aciclico.
    """
    grau_entrada = {vertice: 0 for vertice in dag}
    for sucessores in dag.values():
        for sucessor in sucessores:
            if sucessor not in grau_entrada:
                raise KeyError(f"sucessor nao declarado no DAG: {sucessor!r}")
            grau_entrada[sucessor] += 1

    # Ordenamos a fila inicial para tornar a saida deterministica: dois DAGs
    # iguais produzem sempre a mesma ordem, o que importa para os testes.
    fila = deque(sorted((v for v, g in grau_entrada.items() if g == 0), key=str))
    ordem = []

    while fila:
        atual = fila.popleft()
        ordem.append(atual)
        for sucessor in sorted(dag[atual], key=str):
            grau_entrada[sucessor] -= 1
            if grau_entrada[sucessor] == 0:
                fila.append(sucessor)

    if len(ordem) != len(dag):
        raise CicloDetectado(set(dag) - set(ordem))
    return ordem


def e_aciclico(dag):
    try:
        ordenacao_topologica(dag)
        return True
    except CicloDetectado:
        return False


def alcancaveis(dag, origem):
    """Todos os vertices alcancaveis a partir de `origem`, ele proprio incluso."""
    vistos = {origem}
    pilha = [origem]
    while pilha:
        for sucessor in dag[pilha.pop()]:
            if sucessor not in vistos:
                vistos.add(sucessor)
                pilha.append(sucessor)
    return vistos
