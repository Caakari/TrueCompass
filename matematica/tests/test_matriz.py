"""Testes da matriz de mapa e do modelo de semaforo.

    python3 matematica/tests/test_matriz.py
"""

import os
import sys
from math import isclose

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from algoritmos.busca import busca_caminho_minimo
from algoritmos.grafo import haversine
from algoritmos.matriz_mapa import (MatrizInvalida, MatrizMapa, celula_do_no,
                                    no_da_celula)
from algoritmos.semaforo import (Semaforo, TemporizacaoInvalida, espera_media,
                                 proporcao_de_verde)

MAPA = """
AAAAA
.#.S.
>>>..
.#..A
"""


def mapa():
    return MatrizMapa.de_texto(MAPA)


def peso(grafo, a, b):
    return dict(grafo.vizinhos(a)).get(b)


# ============================================================ SEMAFORO

def test_formula_da_espera_media():
    """E[espera] = r^2 / (2c)."""
    assert espera_media(30, 60) == 30 * 30 / 120
    assert espera_media(0, 60) == 0.0          # sempre verde
    assert espera_media(60, 60) == 30.0        # sempre vermelho: espera c/2


def test_espera_cresce_com_o_quadrado_do_vermelho():
    """Dobrar o vermelho, mantido o ciclo, quadruplica a espera."""
    assert isclose(espera_media(30, 60), 4 * espera_media(15, 60), rel_tol=1e-12)


def test_proporcao_de_verde():
    assert proporcao_de_verde(15, 60) == 0.75
    assert proporcao_de_verde(60, 60) == 0.0


def test_temporizacao_invalida_e_recusada():
    for vermelho, ciclo in [(30, 0), (30, -1), (-5, 60), (90, 60)]:
        try:
            espera_media(vermelho, ciclo)
        except TemporizacaoInvalida:
            continue
        raise AssertionError(f"deveria recusar vermelho={vermelho} ciclo={ciclo}")


def test_semaforo_valida_na_construcao():
    try:
        Semaforo(90, 60)
    except TemporizacaoInvalida:
        return
    raise AssertionError("construcao com vermelho > ciclo deveria falhar")


def test_semaforo_expoe_verde_e_atraso():
    sinal = Semaforo(20, 50)
    assert sinal.verde == 30.0
    assert isclose(sinal.atraso, 400 / 100)


# ============================================================ MATRIZ

def test_identificador_de_celula_e_reversivel():
    for i, j in [(0, 0), (3, 7), (120, 4500)]:
        assert celula_do_no(no_da_celula(i, j)) == (i, j)


def test_linha_zero_fica_ao_sul():
    """O texto e escrito com o norte em cima; a linha 0 e a de baixo."""
    m = mapa()
    assert m.simbolo(0, 0) == "."          # ultima linha do texto
    assert m.simbolo(3, 0) == "A"          # primeira linha do texto
    assert m.coordenadas(0, 0)[0] < m.coordenadas(3, 0)[0]


def test_ida_e_volta_do_texto():
    assert MatrizMapa.de_texto(MAPA).para_texto() == MAPA.strip("\n")


def test_comentarios_sao_ignorados():
    m = MatrizMapa.de_texto("// um comentario\n..\n..\n")
    assert m.altura == 2 and m.largura == 2


def test_linhas_de_tamanhos_diferentes_sao_completadas():
    m = MatrizMapa.de_texto("...\n.\n")
    assert m.largura == 3
    assert not m.transponivel(0, 1)        # completado com espaco


def test_simbolo_desconhecido_e_recusado():
    try:
        MatrizMapa.de_texto("..\n.X\n")
    except MatrizInvalida:
        return
    raise AssertionError("simbolo invalido deveria falhar")


def test_matriz_vazia_e_recusada():
    try:
        MatrizMapa([])
    except MatrizInvalida:
        return
    raise AssertionError("matriz vazia deveria falhar")


# ----------------------------------------------------- topologia derivada

def test_celula_intransponivel_nao_vira_no():
    g = mapa().para_grafo()
    assert no_da_celula(2, 1) not in set(g.nos)      # '#' na linha '.#..A'
    assert no_da_celula(0, 0) in set(g.nos)


def test_mao_dupla_gera_as_duas_arestas():
    g = MatrizMapa.de_texto("..\n..").para_grafo()
    a, b = no_da_celula(0, 0), no_da_celula(0, 1)
    assert peso(g, a, b) is not None and peso(g, b, a) is not None


def test_mao_unica_leste_bloqueia_a_volta():
    g = MatrizMapa.de_texto(">>").para_grafo()
    a, b = no_da_celula(0, 0), no_da_celula(0, 1)
    assert peso(g, a, b) is not None
    assert peso(g, b, a) is None


def test_mao_unica_nao_restringe_o_eixo_perpendicular():
    """'>' limita o movimento horizontal; o vertical segue livre."""
    g = MatrizMapa.de_texto(">\n>").para_grafo()
    baixo, cima = no_da_celula(0, 0), no_da_celula(1, 0)
    assert peso(g, baixo, cima) is not None
    assert peso(g, cima, baixo) is not None


def test_sentidos_opostos_vizinhos_se_anulam():
    """'>' seguido de '<' nao permite passagem em sentido algum."""
    g = MatrizMapa.de_texto("><").para_grafo()
    a, b = no_da_celula(0, 0), no_da_celula(0, 1)
    assert peso(g, a, b) is None and peso(g, b, a) is None


def test_avenida_e_mais_rapida_que_rua():
    g = MatrizMapa.de_texto("AA\n..").para_grafo()
    assert peso(g, no_da_celula(1, 0), no_da_celula(1, 1)) < \
           peso(g, no_da_celula(0, 0), no_da_celula(0, 1))


def test_trecho_misto_usa_a_velocidade_menor():
    """Avenida ligada a rua local percorre na condicao mais restritiva."""
    misto = MatrizMapa.de_texto("A.").para_grafo()
    lento = MatrizMapa.de_texto("..").para_grafo()
    assert isclose(peso(misto, no_da_celula(0, 0), no_da_celula(0, 1)),
                   peso(lento, no_da_celula(0, 0), no_da_celula(0, 1)))


# ------------------------------------------------------------- semaforos

def test_semaforo_entra_na_aresta_que_chega():
    m = MatrizMapa.de_texto(".S")
    g = m.para_grafo()
    sem = m.para_grafo(considerar_semaforos=False)
    a, b = no_da_celula(0, 0), no_da_celula(0, 1)

    # chegando no semaforo: paga o atraso
    assert isclose(peso(g, a, b) - peso(sem, a, b), Semaforo().atraso)
    # saindo do semaforo: nao paga nada
    assert isclose(peso(g, b, a), peso(sem, b, a))


def test_semaforo_nao_altera_a_topologia():
    m = mapa()
    assert m.para_grafo().total_arestas() == \
           m.para_grafo(considerar_semaforos=False).total_arestas()


def test_temporizacao_personalizada_substitui_o_padrao():
    m = MatrizMapa.de_texto(".S")
    m.definir_semaforo(0, 1, vermelho=50, ciclo=60)
    a, b = no_da_celula(0, 0), no_da_celula(0, 1)
    atraso = peso(m.para_grafo(), a, b) - peso(m.para_grafo(considerar_semaforos=False), a, b)
    assert isclose(atraso, espera_media(50, 60))
    assert atraso > Semaforo().atraso        # vermelho mais longo, espera maior


def test_semaforo_pode_mudar_a_rota_escolhida():
    """O desvio mais longo vence quando o caminho curto esta cheio de sinal.

    Duas fileiras ligando os mesmos extremos: a de baixo e direta mas
    semaforizada; a de cima da a volta, sem sinal.

    A diferenca precisa ser decisiva. Com a temporizacao padrao (7,5s por
    sinal) o caminho direto ainda venceria por margem estreita -- 4 trechos
    mais 3 sinais contra 6 trechos limpos. Usamos sinais pesados (55s de
    vermelho em ciclo de 60s, 25,2s de espera cada) para que o desvio seja
    inequivocamente melhor.
    """
    m = MatrizMapa.de_texto("""
    .....
    .SSS.
    """.replace("    ", ""))
    for coluna in (1, 2, 3):
        m.definir_semaforo(0, coluna, vermelho=55, ciclo=60)
    origem, destino = no_da_celula(0, 0), no_da_celula(0, 4)

    com = busca_caminho_minimo(m.para_grafo(), origem, {destino})
    sem = busca_caminho_minimo(m.para_grafo(considerar_semaforos=False),
                               origem, {destino})
    assert com.custos[destino] > sem.custos[destino], "semaforo nao encareceu nada"

    def rota(resultado):
        caminho, atual = [destino], destino
        while atual != origem:
            atual = resultado.anterior[atual]
            caminho.append(atual)
        return list(reversed(caminho))

    caminho_com, caminho_sem = rota(com), rota(sem)
    assert caminho_com != caminho_sem, "a rota deveria desviar dos semaforos"
    # Sem sinal, atravessa a fileira semaforizada; com sinal, sobe e contorna.
    assert all(celula_do_no(n)[0] == 0 for n in caminho_sem), "rota limpa nao foi a direta"
    assert any(celula_do_no(n)[0] == 1 for n in caminho_com), "rota com sinal nao desviou"


def test_estatisticas_contam_os_semaforos():
    dados = mapa().estatisticas()
    assert dados["semaforos"] == 1
    assert dados["transponiveis"] < dados["celulas"]


# ---------------------------- a heuristica do A* continua valida com atraso

def test_atraso_preserva_admissibilidade_da_heuristica():
    """Somar atraso so AUMENTA o custo real; a heuristica, que nao mudou,
    continua sendo um limite inferior. A* segue devolvendo a rota otima."""
    from algoritmos.grafo import heuristica_haversine

    m = MatrizMapa.de_texto("""
    AAAAAA
    .SS.S.
    .....S
    SS.A.A
    """.replace("    ", ""))
    g = m.para_grafo()
    origem, destino = no_da_celula(0, 0), no_da_celula(3, 5)
    h = heuristica_haversine(g, destino, 50.0)

    dij = busca_caminho_minimo(g, origem, {destino})
    ast = busca_caminho_minimo(g, origem, {destino}, h=h)
    assert isclose(dij.custos[destino], ast.custos[destino], rel_tol=1e-9), \
        "com semaforo, A* divergiu do Dijkstra"


# ------------------------------------------------- o mapa que vai a producao

CAMINHO_MAPA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "mapas", "centro.mapa")


def mapa_de_producao():
    with open(CAMINHO_MAPA, encoding="utf-8") as arquivo:
        return MatrizMapa.de_texto(arquivo.read())


def test_mapa_do_centro_carrega():
    dados = mapa_de_producao().estatisticas()
    assert dados["altura"] == dados["largura"] == 36
    assert dados["transponiveis"] > 1000
    assert dados["semaforos"] > 0


def test_mapa_do_centro_e_fortemente_conexo():
    """Cruzamento inalcancavel viraria motorista invisivel ou rota inexistente.

    Verificado como no Kosaraju: o que a semente alcanca, intersectado com o
    que alcanca a semente (via grafo reverso), tem de ser a malha inteira.
    """
    g = mapa_de_producao().para_grafo()
    semente = max(g.nos, key=lambda n: len(dict(g.vizinhos(n))))
    alcanca = set(busca_caminho_minimo(g, semente, alvos=set()).distancias)
    alcancado = set(busca_caminho_minimo(g.reverso(), semente, alvos=set()).distancias)
    assert alcanca == alcancado == set(g.nos), (
        f"malha nao e fortemente conexa: {len(g.nos) - len(alcanca & alcancado)} "
        f"cruzamentos isolados"
    )


def test_mapa_do_centro_tem_rio_com_pontes():
    """O rio existe e e atravessavel -- so pelas pontes."""
    m = mapa_de_producao()
    coluna_rio = 20
    bloqueadas = sum(1 for i in range(m.altura) if not m.transponivel(i, coluna_rio))
    assert bloqueadas == m.altura - 2, "o rio deveria ter exatamente 2 pontes"


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
            print(f"  FALHA {teste.__name__}: {str(erro)[:140]}")
    print(f"\n{len(testes) - falhas}/{len(testes)} testes passaram")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
