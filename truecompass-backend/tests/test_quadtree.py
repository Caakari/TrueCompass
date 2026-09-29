"""Testes da quadtree.

O teste central e o ORACULO: para centenas de consultas aleatorias, a
quadtree tem de devolver EXATAMENTE o mesmo que a varredura linear. Mesma
estrategia com que o Dijkstra valida o A* -- a implementacao simples e
obviamente correta serve de gabarito para a otimizada.

    python3 tests/test_quadtree.py
"""

import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from algoritmos.grafo import haversine
from algoritmos.indice_espacial import IndiceLinear
from algoritmos.quadtree import Quadtree, Retangulo

LAT0, LON0, EXTENSAO = -23.55, -46.64, 0.05


def pontos_aleatorios(quantidade, semente=7):
    rng = random.Random(semente)
    return {i: (LAT0 + rng.random() * EXTENSAO, LON0 + rng.random() * EXTENSAO)
            for i in range(quantidade)}


# ------------------------------------------------------------------ oraculo

def test_proximos_bate_com_a_varredura_linear():
    pontos = pontos_aleatorios(1500)
    arvore, linear = Quadtree(pontos), IndiceLinear(pontos)
    rng = random.Random(99)

    for _ in range(200):
        lat = LAT0 + rng.random() * EXTENSAO
        lon = LON0 + rng.random() * EXTENSAO
        raio = rng.choice([50, 200, 800, 3000])
        assert arvore.proximos(lat, lon, raio) == linear.proximos(lat, lon, raio), (
            f"divergencia em ({lat:.5f}, {lon:.5f}) raio {raio}m"
        )


def test_mais_proximo_bate_com_a_varredura_linear():
    pontos = pontos_aleatorios(800, semente=11)
    arvore, linear = Quadtree(pontos), IndiceLinear(pontos)
    rng = random.Random(123)

    for _ in range(200):
        lat = LAT0 + rng.random() * EXTENSAO
        lon = LON0 + rng.random() * EXTENSAO
        esperado, obtido = linear.mais_proximo(lat, lon), arvore.mais_proximo(lat, lon)
        # Empate exato e possivel: comparamos a distancia, nao o identificador.
        assert abs(haversine(lat, lon, *pontos[obtido])
                   - haversine(lat, lon, *pontos[esperado])) < 1e-9


def test_consulta_fora_da_area_nao_inventa_resultado():
    pontos = pontos_aleatorios(500)
    arvore, linear = Quadtree(pontos), IndiceLinear(pontos)
    longe = (LAT0 - 5, LON0 - 5)
    assert arvore.proximos(*longe, 1000) == linear.proximos(*longe, 1000) == []


# --------------------------------------------------------------------- poda

def test_poda_visita_uma_fracao_dos_nos():
    pontos = pontos_aleatorios(3000)
    arvore = Quadtree(pontos)
    arvore.proximos(LAT0 + EXTENSAO / 2, LON0 + EXTENSAO / 2, 300)
    assert arvore.nos_visitados < arvore.total_nos() / 3, (
        f"poda fraca: visitou {arvore.nos_visitados} de {arvore.total_nos()}"
    )


def test_ramo_distante_e_descartado_inteiro():
    """Consulta fora da area deve parar na raiz."""
    arvore = Quadtree(pontos_aleatorios(2000))
    arvore.proximos(LAT0 - 1, LON0 - 1, 100)
    assert arvore.nos_visitados == 1


def test_arvore_cresce_menos_que_linearmente():
    """Altura de arvore, nao de lista: quadruplicar os pontos soma ~1 nivel."""
    baixa = Quadtree(pontos_aleatorios(500, semente=1)).altura()
    alta = Quadtree(pontos_aleatorios(8000, semente=2)).altura()
    assert alta - baixa <= 4, f"altura saltou de {baixa} para {alta}"


# ------------------------------------------------------------- subdivisao

def test_folha_subdivide_ao_estourar_a_capacidade():
    pontos = pontos_aleatorios(200)
    assert Quadtree(pontos, capacidade=4).altura() > Quadtree(pontos, capacidade=256).altura()


def test_pontos_identicos_nao_causam_recursao_infinita():
    """Sem teto de profundidade, nenhuma divisao separa pontos coincidentes."""
    iguais = {i: (LAT0, LON0) for i in range(50)}
    arvore = Quadtree(iguais, capacidade=4, profundidade_max=6)
    assert len(arvore) == 50
    assert arvore.altura() <= 7
    assert len(arvore.proximos(LAT0, LON0, 10)) == 50


def test_arvore_vazia_responde_sem_quebrar():
    vazia = Quadtree({})
    assert len(vazia) == 0
    assert vazia.proximos(LAT0, LON0, 1000) == []
    assert vazia.mais_proximo(LAT0, LON0) is None


def test_um_unico_ponto():
    arvore = Quadtree({"unico": (LAT0, LON0)})
    assert arvore.mais_proximo(LAT0, LON0) == "unico"
    assert arvore.proximos(LAT0, LON0, 1) == ["unico"]


# ----------------------------------------------------------------- escrita

def test_inserir_ponto_novo():
    arvore = Quadtree(pontos_aleatorios(100))
    arvore.inserir("novo", LAT0 + 0.01, LON0 + 0.01)
    assert "novo" in arvore and len(arvore) == 101
    assert "novo" in arvore.proximos(LAT0 + 0.01, LON0 + 0.01, 50)


def test_reinserir_move_o_ponto_sem_duplicar():
    arvore = Quadtree(pontos_aleatorios(100))
    arvore.inserir("movel", LAT0 + 0.01, LON0 + 0.01)
    arvore.inserir("movel", LAT0 + 0.04, LON0 + 0.04)

    assert len(arvore) == 101, "reinsercao duplicou o ponto"
    assert "movel" not in arvore.proximos(LAT0 + 0.01, LON0 + 0.01, 50)
    assert "movel" in arvore.proximos(LAT0 + 0.04, LON0 + 0.04, 50)


def test_inserir_fora_da_area_expande_a_arvore():
    arvore = Quadtree(pontos_aleatorios(100))
    arvore.inserir("distante", LAT0 + 10, LON0 + 10)
    assert arvore.mais_proximo(LAT0 + 10, LON0 + 10) == "distante"


def test_remover():
    pontos = pontos_aleatorios(100)
    arvore = Quadtree(pontos)
    alvo, (lat, lon) = 0, pontos[0]
    arvore.remover(alvo)
    assert alvo not in arvore and len(arvore) == 99
    assert alvo not in arvore.proximos(lat, lon, 5000)
    arvore.remover("nunca_existiu")      # nao pode quebrar


def test_reconstruir_troca_todo_o_conteudo():
    arvore = Quadtree(pontos_aleatorios(100))
    arvore.reconstruir({"a": (LAT0, LON0)})
    assert len(arvore) == 1 and arvore.mais_proximo(LAT0, LON0) == "a"


# ------------------------------------------------------------------ limites

def test_limite_devolve_os_mais_proximos():
    pontos = pontos_aleatorios(1000)
    arvore, linear = Quadtree(pontos), IndiceLinear(pontos)
    alvo = (LAT0 + 0.02, LON0 + 0.02)
    assert arvore.proximos(*alvo, 3000, limite=5) == linear.proximos(*alvo, 3000, limite=5)


def test_resultado_vem_ordenado_por_distancia():
    pontos = pontos_aleatorios(600)
    arvore = Quadtree(pontos)
    alvo = (LAT0 + 0.02, LON0 + 0.02)
    distancias = [haversine(*alvo, *pontos[i]) for i in arvore.proximos(*alvo, 2000)]
    assert distancias == sorted(distancias)


def test_raio_zero_pega_so_o_ponto_exato():
    arvore = Quadtree({"aqui": (LAT0, LON0), "la": (LAT0 + 0.01, LON0)})
    assert arvore.proximos(LAT0, LON0, 0) == ["aqui"]


# --------------------------------------------------------------- retangulo

def test_distancia_a_retangulo_e_zero_por_dentro():
    r = Retangulo(-23.56, -23.54, -46.65, -46.63)
    assert r.distancia_minima_m(-23.55, -46.64) == 0.0
    assert r.distancia_minima_m(-23.50, -46.64) > 4000


def test_quadrantes_cobrem_o_retangulo_sem_sobrepor():
    r = Retangulo(0.0, 2.0, 0.0, 2.0)
    quadrantes = r.quadrantes()
    assert len(quadrantes) == 4
    for lat, lon in ((0.5, 0.5), (0.5, 1.5), (1.5, 0.5), (1.5, 1.5)):
        assert sum(1 for q in quadrantes if q.contem(lat, lon)) == 1


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
