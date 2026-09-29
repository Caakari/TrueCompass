"""Testes da ordenacao topologica e do DAG do ciclo da corrida.

    python3 tests/test_estados.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from algoritmos.topologica import (CicloDetectado, alcancaveis, e_aciclico,
                                   ordenacao_topologica)
from dominio import estados as E


# ------------------------------------------------------- algoritmo de Kahn

def test_ordem_respeita_todas_as_arestas():
    """A propriedade que define ordenacao topologica: pos(u) < pos(v)."""
    ordem = ordenacao_topologica(E.DAG_CORRIDA)
    posicao = {estado: i for i, estado in enumerate(ordem)}
    for origem, destinos in E.DAG_CORRIDA.items():
        for destino in destinos:
            assert posicao[origem] < posicao[destino], f"{origem} -> {destino}"


def test_ordem_contem_todos_os_vertices_uma_vez():
    ordem = ordenacao_topologica(E.DAG_CORRIDA)
    assert len(ordem) == len(E.DAG_CORRIDA) == len(set(ordem))


def test_ciclo_e_detectado():
    ciclico = {"a": ["b"], "b": ["c"], "c": ["a"]}
    assert not e_aciclico(ciclico)
    try:
        ordenacao_topologica(ciclico)
    except CicloDetectado as erro:
        assert erro.restantes == {"a", "b", "c"}
        return
    raise AssertionError("deveria ter detectado o ciclo")


def test_autolaco_e_ciclo():
    assert not e_aciclico({"a": ["a"]})


def test_sucessor_nao_declarado_e_erro():
    try:
        ordenacao_topologica({"a": ["fantasma"]})
    except KeyError:
        return
    raise AssertionError("sucessor ausente do DAG deveria falhar alto")


def test_ordem_e_deterministica():
    assert ordenacao_topologica(E.DAG_CORRIDA) == ordenacao_topologica(E.DAG_CORRIDA)


def test_grafo_vazio_e_aciclico():
    assert ordenacao_topologica({}) == []


# --------------------------------------------------------- DAG da corrida

def test_dag_da_corrida_sobe_limpo():
    ordem = E.validar_dag()
    assert ordem[0] == E.PEDIDO


def test_pagamento_so_vem_de_concluida():
    """A promessa do README, verificada na estrutura do grafo."""
    entradas = [de for de, para in E.DAG_CORRIDA.items() if E.PAGA in para]
    assert entradas == [E.CONCLUIDA]


def test_nao_se_paga_corrida_que_nao_comecou():
    for estado in (E.PEDIDO, E.ALOCACAO, E.ROTA, E.EM_CURSO):
        assert not E.transicao_permitida(estado, E.PAGA)


def test_nao_se_pula_etapa():
    assert not E.transicao_permitida(E.PEDIDO, E.EM_CURSO)
    assert not E.transicao_permitida(E.ALOCACAO, E.CONCLUIDA)


def test_nao_se_volta_atras():
    assert not E.transicao_permitida(E.EM_CURSO, E.ROTA)
    assert not E.transicao_permitida(E.CONCLUIDA, E.EM_CURSO)


def test_estados_finais_nao_tem_saida():
    for estado in E.ESTADOS_FINAIS:
        assert E.DAG_CORRIDA[estado] == []
        assert E.e_final(estado)


def test_corrida_em_curso_nao_pode_ser_cancelada():
    """Cancelar e possivel ate a rota; depois que o carro anda, nao mais."""
    assert not E.transicao_permitida(E.EM_CURSO, E.CANCELADA)
    for estado in (E.PEDIDO, E.ALOCACAO, E.ROTA):
        assert E.transicao_permitida(estado, E.CANCELADA)


def test_caminho_feliz_completo():
    fluxo = [E.PEDIDO, E.ALOCACAO, E.ROTA, E.EM_CURSO, E.CONCLUIDA, E.PAGA]
    for de_estado, para_estado in zip(fluxo, fluxo[1:]):
        assert E.exigir_transicao(de_estado, para_estado) == para_estado


def test_transicao_invalida_explica_o_que_era_possivel():
    try:
        E.exigir_transicao(E.PEDIDO, E.PAGA)
    except E.TransicaoInvalida as erro:
        assert E.ALOCACAO in str(erro) and "invalida" in str(erro)
        return
    raise AssertionError("deveria ter recusado")


def test_estado_inexistente_e_recusado():
    try:
        E.exigir_transicao("estado_fantasma", E.PAGA)
    except E.TransicaoInvalida:
        return
    raise AssertionError("estado desconhecido deveria ser recusado")


def test_todo_estado_e_alcancavel_desde_o_pedido():
    """Estado inalcancavel seria codigo morto no fluxo."""
    assert alcancaveis(E.DAG_CORRIDA, E.PEDIDO) == set(E.DAG_CORRIDA)


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
