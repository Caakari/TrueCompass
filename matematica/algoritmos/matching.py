"""Matching de motoristas: qual deles chega antes no passageiro?

Implementa a busca reversa many-to-one, e tambem a versao ingenua
(uma busca por motorista) para servir de comparacao nos benchmarks.
"""

from dataclasses import dataclass
from math import inf

from .busca import busca_caminho_minimo, caminho_ate_origem


@dataclass
class Candidato:
    motorista_id: str
    no: str
    eta_segundos: float
    rota: list

    @property
    def eta_minutos(self):
        return self.eta_segundos / 60.0


def motoristas_mais_proximos(grafo, no_passageiro, motoristas, limite_segundos=inf, top_n=None):
    """UMA busca no grafo reverso devolve o ETA de todos os motoristas.

    Parametros
    ----------
    grafo          : o grafo NORMAL da cidade (o reverso sai daqui).
    no_passageiro  : vertice onde o passageiro esta.
    motoristas     : dict {motorista_id: no_onde_ele_esta}.
                     Tipicamente os ~20 candidatos que a quadtree filtrou.
    limite_segundos: orcamento de tempo. Quem estiver alem disso e descartado
                     em vez de fazer a busca varrer a cidade atras dele.
    top_n          : quantos devolver (None = todos os alcancados).

    Devolve lista de Candidato ordenada por ETA crescente.

    Custo: 1 busca limitada por raio, em vez de k buscas completas.
    """
    if not motoristas:
        return []

    # Varios motoristas podem estar no mesmo cruzamento: agrupamos por no
    # para nao procurar o mesmo alvo duas vezes.
    por_no = {}
    for motorista_id, no in motoristas.items():
        por_no.setdefault(no, []).append(motorista_id)

    grafo_reverso = grafo.reverso()
    resultado = busca_caminho_minimo(
        grafo_reverso,
        origem=no_passageiro,
        alvos=set(por_no),
        h=None,                  # multi-alvo => Dijkstra, sem heuristica
        limite=limite_segundos,
    )

    candidatos = []
    for no, eta in resultado.custos.items():
        # anterior[] vem do grafo reverso, mas lido na ordem natural ja e a
        # rota real motorista -> passageiro no grafo original.
        rota = caminho_ate_origem(resultado.anterior, no, no_passageiro)
        for motorista_id in por_no[no]:
            candidatos.append(Candidato(motorista_id, no, eta, rota))

    candidatos.sort(key=lambda c: c.eta_segundos)
    return candidatos[:top_n] if top_n else candidatos


def motoristas_mais_proximos_ingenuo(grafo, no_passageiro, motoristas, limite_segundos=inf):
    """Versao ingenua: uma busca separada por motorista. So para comparar.

    Da o MESMO resultado da versao reversa -- e e por isso que ela serve de
    oraculo nos testes -- mas custa k buscas em vez de 1.
    """
    candidatos = []
    total_expandidos = 0
    for motorista_id, no in motoristas.items():
        resultado = busca_caminho_minimo(
            grafo, origem=no, alvos={no_passageiro}, h=None, limite=limite_segundos
        )
        total_expandidos += resultado.nos_expandidos
        if no_passageiro in resultado.custos:
            candidatos.append(
                Candidato(
                    motorista_id,
                    no,
                    resultado.custos[no_passageiro],
                    [],  # rota omitida: aqui so nos interessa o custo
                )
            )
    candidatos.sort(key=lambda c: c.eta_segundos)
    return candidatos, total_expandidos
