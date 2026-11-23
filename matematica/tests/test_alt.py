"""Testes do ALT (A* + Landmarks + desigualdade Triangular).

As duas propriedades que importam sao verificadas diretamente, e nao
assumidas: ADMISSIBILIDADE (h nunca passa do custo real) e CONSISTENCIA
(h(u) <= w(u,v) + h(v)). Sem a primeira o A* devolve rota subotima; sem a
segunda ele reexpande vertices.

    python3 matematica/tests/test_alt.py
"""

import os
import random
import sys
import tempfile
from math import inf, isfinite

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from algoritmos.alt import ALT
from algoritmos.busca import busca_caminho_minimo
from algoritmos.grafo import Grafo, heuristica_haversine
from algoritmos.matriz_mapa import MatrizMapa

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def mapa():
    with open(os.path.join(RAIZ, "mapas", "centro.mapa"), encoding="utf-8") as a:
        return MatrizMapa.de_texto(a.read())


GRAFO = mapa().para_grafo()
ALTT = ALT.construir(GRAFO, quantidade=8)
NOS = sorted(GRAFO.nos)


def custo_real(origem, destino):
    return busca_caminho_minimo(GRAFO, origem, {destino}).custos.get(destino)


# =============================================================== construcao

def test_constroi_a_quantidade_pedida():
    assert len(ALTT) == 8
    assert len(set(ALTT.marcos)) == 8, "marcos repetidos"


def test_marcos_sao_nos_do_grafo():
    assert all(marco in set(NOS) for marco in ALTT.marcos)


def test_tabelas_tem_uma_entrada_por_no():
    for tabela in ALTT.de_marco + ALTT.para_marco:
        assert len(tabela) == len(NOS)


def test_distancia_do_marco_a_si_mesmo_e_zero():
    for k, marco in enumerate(ALTT.marcos):
        i = ALTT.indice[marco]
        assert ALTT.de_marco[k][i] == 0.0
        assert ALTT.para_marco[k][i] == 0.0


def test_tabela_de_ida_bate_com_dijkstra():
    """d(L, v) tabelado tem de ser o custo real de L ate v."""
    rng = random.Random(3)
    marco = ALTT.marcos[0]
    real = busca_caminho_minimo(GRAFO, marco, alvos=set()).distancias
    tabela = ALTT.de_marco[0]
    for no in rng.sample(NOS, 60):
        assert abs(tabela[ALTT.indice[no]] - real[no]) < 0.01, f"divergiu em {no}"


def test_tabela_de_volta_usa_o_grafo_reverso():
    """d(v, L) tabelado tem de ser o custo real de v ate L.

    E a dualidade da Proposicao C.7: a busca partiu do marco no grafo
    REVERSO, e o resultado e a distancia ATE o marco no grafo normal.
    """
    rng = random.Random(5)
    marco = ALTT.marcos[0]
    tabela = ALTT.para_marco[0]
    for no in rng.sample(NOS, 25):
        real = busca_caminho_minimo(GRAFO, no, {marco}).custos.get(marco)
        if real is None:
            continue
        assert abs(tabela[ALTT.indice[no]] - real) < 0.01, f"divergiu em {no}"


def test_grafo_vazio_e_recusado():
    try:
        ALT.construir(Grafo())
    except ValueError:
        return
    raise AssertionError("grafo vazio deveria falhar")


def test_quantidade_maior_que_o_grafo_e_limitada():
    pequeno = MatrizMapa.de_texto("..\n..").para_grafo()
    assert len(ALT.construir(pequeno, quantidade=50)) <= 4


# ============================================== as duas propriedades centrais

def test_heuristica_e_admissivel():
    """h(v) <= custo real de v ate o destino, para todo v."""
    rng = random.Random(7)
    for _ in range(12):
        destino = rng.choice(NOS)
        h = ALTT.heuristica(destino)
        reais = busca_caminho_minimo(GRAFO.reverso(), destino, alvos=set()).distancias
        for no in rng.sample(NOS, 40):
            real = reais.get(no)
            if real is None:
                continue
            # Tolerancia RELATIVA: as duas pontas vem de somas em ordens
            # diferentes, e ponto flutuante nao e associativo.
            assert h(no) <= real * (1 + 1e-9) + 1e-9, (
                f"h({no})={h(no):.3f} > custo real {real:.3f} ate {destino}"
            )


def test_heuristica_e_consistente():
    """h(u) <= w(u,v) + h(v) em toda aresta."""
    rng = random.Random(9)
    for _ in range(8):
        destino = rng.choice(NOS)
        h = ALTT.heuristica(destino)
        for origem in rng.sample(NOS, 50):
            hu = h(origem)
            for vizinho, peso in GRAFO.vizinhos(origem):
                assert hu <= (peso + h(vizinho)) * (1 + 1e-9) + 1e-9, (
                    f"inconsistente em {origem}->{vizinho}"
                )


def test_heuristica_no_destino_e_zero():
    rng = random.Random(13)
    for destino in rng.sample(NOS, 20):
        assert ALTT.heuristica(destino)(destino) == 0.0


def test_heuristica_nunca_e_negativa():
    rng = random.Random(17)
    destino = rng.choice(NOS)
    h = ALTT.heuristica(destino)
    assert all(h(no) >= 0.0 for no in rng.sample(NOS, 150))


def test_destino_fora_do_grafo_degrada_para_dijkstra():
    h = ALTT.heuristica(-999)
    assert h(NOS[0]) == 0.0


# ======================================================= oraculo e beneficio

def test_alt_concorda_com_dijkstra():
    """O teste decisivo: mesma rota otima, com menos busca."""
    rng = random.Random(19)
    for _ in range(40):
        origem, destino = rng.sample(NOS, 2)
        otimo = custo_real(origem, destino)
        if otimo is None:
            continue
        obtido = busca_caminho_minimo(
            GRAFO, origem, {destino}, h=ALTT.heuristica(destino, origem)
        ).custos.get(destino)
        assert obtido is not None and abs(obtido - otimo) < 1e-9, (
            f"ALT divergiu em {origem}->{destino}: {obtido} != {otimo}"
        )


def test_alt_expande_menos_que_dijkstra():
    rng = random.Random(23)
    dij = alt = 0
    for _ in range(25):
        origem, destino = rng.sample(NOS, 2)
        if custo_real(origem, destino) is None:
            continue
        dij += busca_caminho_minimo(GRAFO, origem, {destino}).nos_expandidos
        alt += busca_caminho_minimo(
            GRAFO, origem, {destino}, h=ALTT.heuristica(destino, origem)
        ).nos_expandidos
    assert alt < dij, f"ALT expandiu {alt}, Dijkstra {dij}"


def test_alt_e_mais_apertado_que_a_haversine():
    """O motivo de existir: limite maior, logo poda melhor."""
    rng = random.Random(29)
    vitorias = 0
    for _ in range(30):
        origem, destino = rng.sample(NOS, 2)
        if custo_real(origem, destino) is None:
            continue
        if ALTT.heuristica(destino, origem)(origem) >= heuristica_haversine(GRAFO, destino)(origem):
            vitorias += 1
    assert vitorias >= 25, f"ALT so superou a haversine em {vitorias} de 30"


def test_marcos_ativos_preservam_a_otimalidade():
    """Usar so os melhores marcos nao pode mudar a resposta."""
    rng = random.Random(31)
    for _ in range(20):
        origem, destino = rng.sample(NOS, 2)
        otimo = custo_real(origem, destino)
        if otimo is None:
            continue
        reduzido = ALT(ALTT.marcos, ALTT.indice, ALTT.de_marco, ALTT.para_marco, ativos=2)
        obtido = busca_caminho_minimo(
            GRAFO, origem, {destino}, h=reduzido.heuristica(destino, origem)
        ).custos.get(destino)
        assert abs(obtido - otimo) < 1e-9


# ============================================================= persistencia

def test_ida_e_volta_do_arquivo():
    with tempfile.TemporaryDirectory() as pasta:
        caminho = os.path.join(pasta, "alt.bin")
        ALTT.salvar(caminho)
        lido = ALT.carregar(caminho)

    assert lido.marcos == ALTT.marcos
    assert lido.ativos == ALTT.ativos
    assert len(lido.indice) == len(ALTT.indice)
    for a, b in zip(lido.de_marco, ALTT.de_marco):
        assert list(a) == list(b)
    for a, b in zip(lido.para_marco, ALTT.para_marco):
        assert list(a) == list(b)


def test_arquivo_de_outra_versao_e_recusado():
    with tempfile.TemporaryDirectory() as pasta:
        caminho = os.path.join(pasta, "ruim.bin")
        with open(caminho, "wb") as arquivo:
            arquivo.write(b"OUTRACOISA" + b"\x00" * 64)
        try:
            ALT.carregar(caminho)
        except ValueError:
            return
    raise AssertionError("assinatura invalida deveria falhar")


def test_heuristica_do_arquivo_e_identica():
    rng = random.Random(37)
    with tempfile.TemporaryDirectory() as pasta:
        caminho = os.path.join(pasta, "alt.bin")
        ALTT.salvar(caminho)
        lido = ALT.carregar(caminho)
    destino = rng.choice(NOS)
    original, recarregado = ALTT.heuristica(destino), lido.heuristica(destino)
    assert all(original(no) == recarregado(no) for no in rng.sample(NOS, 80))


def test_impressao_detecta_grafo_diferente():
    """Artefato gerado para outra malha tem de ser recusado, nao usado."""
    assert ALTT.confere(GRAFO)
    outro = MatrizMapa.de_texto("...\n...\n...").para_grafo()
    assert not ALTT.confere(outro)


def test_impressao_sobrevive_ao_arquivo():
    with tempfile.TemporaryDirectory() as pasta:
        caminho = os.path.join(pasta, "alt.bin")
        ALTT.salvar(caminho)
        assert ALT.carregar(caminho).confere(GRAFO)


def test_arquivo_corrompido_e_recusado():
    with tempfile.TemporaryDirectory() as pasta:
        caminho = os.path.join(pasta, "alt.bin")
        ALTT.salvar(caminho)
        with open(caminho, "r+b") as arquivo:          # estraga um id de no
            arquivo.seek(len(b"TCALT4\x00\x00") + 24 + 16)
            arquivo.write(b"\xff" * 8)
        try:
            ALT.carregar(caminho)
        except ValueError:
            return
    raise AssertionError("arquivo corrompido deveria ser recusado")


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
            print(f"  FALHA {teste.__name__}: {str(erro)[:150]}")
    print(f"\n{len(testes) - falhas}/{len(testes)} testes passaram")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
