# -*- coding: utf-8 -*-
"""Ciclo de vida da corrida modelado como DAG.

A regra central do sistema -- "pagamento so depois da corrida concluida" --
nao e imposta por `if` espalhado pelo codigo. Ela e consequencia da ESTRUTURA
deste grafo: `paga` so tem uma aresta de entrada, vinda de `concluida`.

Mudar a regra = mudar o grafo. Nao existe outro lugar onde ela possa vazar.
"""

from algoritmos.topologica import (CicloDetectado, alcancaveis,
                                   ordenacao_topologica)

PEDIDO = "pedido"
ALOCACAO = "alocacao"
ROTA = "rota"
EM_CURSO = "em_curso"
CONCLUIDA = "concluida"
PAGA = "paga"
CANCELADA = "cancelada"

DAG_CORRIDA = {
    PEDIDO:    [ALOCACAO, CANCELADA],
    ALOCACAO:  [ROTA, CANCELADA],
    ROTA:      [EM_CURSO, CANCELADA],
    EM_CURSO:  [CONCLUIDA],
    CONCLUIDA: [PAGA],
    PAGA:      [],
    CANCELADA: [],
}

ESTADO_INICIAL = PEDIDO
ESTADOS_FINAIS = frozenset({PAGA, CANCELADA})


class TransicaoInvalida(Exception):
    """Transicao que o DAG nao autoriza."""

    def __init__(self, de_estado, para_estado):
        self.de_estado = de_estado
        self.para_estado = para_estado
        permitidas = DAG_CORRIDA.get(de_estado, [])
        super().__init__(
            f"transicao invalida: {de_estado!r} -> {para_estado!r}. "
            f"A partir de {de_estado!r} so se admite: {sorted(permitidas) or 'nada'}"
        )


def validar_dag():
    """Chamado no boot da aplicacao. Se houver ciclo, o servidor NAO sobe.

    E uma checagem barata (O(V+E) sobre 7 vertices) que transforma a prova da
    secao 5.2 da documentacao em garantia de execucao: nenhuma versao do
    sistema chega a atender requisicao com fluxo de estados inconsistente.
    """
    ordem = ordenacao_topologica(DAG_CORRIDA)

    if ordem[0] != ESTADO_INICIAL:
        raise ValueError(
            f"o primeiro estado da ordem topologica deveria ser {ESTADO_INICIAL!r}, "
            f"mas e {ordem[0]!r} -- ha estado sem predecessor indevidamente"
        )

    # A regra de negocio critica, verificada e nao apenas comentada.
    if alcancaveis(DAG_CORRIDA, PEDIDO) >= {PAGA} and PAGA in DAG_CORRIDA[CONCLUIDA]:
        entradas_em_paga = [
            estado for estado, saidas in DAG_CORRIDA.items() if PAGA in saidas
        ]
        if entradas_em_paga != [CONCLUIDA]:
            raise ValueError(
                f"{PAGA!r} deve ser alcancavel exclusivamente a partir de "
                f"{CONCLUIDA!r}, mas tambem vem de {entradas_em_paga}"
            )
    return ordem


def transicao_permitida(de_estado, para_estado):
    return para_estado in DAG_CORRIDA.get(de_estado, ())


def exigir_transicao(de_estado, para_estado):
    """Valida ou levanta. Ponto unico por onde toda mudanca de estado passa."""
    if de_estado not in DAG_CORRIDA:
        raise TransicaoInvalida(de_estado, para_estado)
    if not transicao_permitida(de_estado, para_estado):
        raise TransicaoInvalida(de_estado, para_estado)
    return para_estado


def e_final(estado):
    return estado in ESTADOS_FINAIS


__all__ = [
    "DAG_CORRIDA", "ESTADO_INICIAL", "ESTADOS_FINAIS", "TransicaoInvalida",
    "CicloDetectado", "validar_dag", "transicao_permitida", "exigir_transicao",
    "e_final", "PEDIDO", "ALOCACAO", "ROTA", "EM_CURSO", "CONCLUIDA", "PAGA",
    "CANCELADA",
]
