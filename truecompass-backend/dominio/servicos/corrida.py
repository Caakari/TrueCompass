# -*- coding: utf-8 -*-
"""Regras de negocio da corrida.

Orquestra as tres pecas algoritmicas sem conhecer HTTP:
  indice espacial (filtro)  ->  busca reversa (ETA real)  ->  A* (rota)
e submete toda mudanca de estado ao DAG.
"""

from sqlalchemy import update

from algoritmos.busca import busca_caminho_minimo, reconstruir_caminho
from algoritmos.grafo import heuristica_haversine
from algoritmos.matching import motoristas_mais_proximos
from dominio import estados as E
from infra.modelos import Corrida, CorridaTransicao, Motorista, Pagamento

TARIFA_BASE = 5.00
POR_MINUTO = 0.80
POR_KM = 1.90
VELOCIDADE_MAX_KMH = 100.0     # coerente com o teto usado na malha do OSM


class SemMotoristaDisponivel(Exception):
    pass


class DestinoInalcancavel(Exception):
    pass


# --------------------------------------------------------------- transicoes

def transitar(sessao, corrida, novo_estado):
    """Ponto UNICO de mudanca de estado. Valida pelo DAG e audita.

    Nenhuma rota da API altera `corrida.estado` diretamente -- se alterasse,
    a garantia estrutural do DAG viraria apenas convencao.
    """
    anterior = corrida.estado
    E.exigir_transicao(anterior, novo_estado)     # levanta TransicaoInvalida
    corrida.estado = novo_estado
    sessao.add(CorridaTransicao(corrida_id=corrida.id, de_estado=anterior,
                                para_estado=novo_estado))
    return corrida


# ------------------------------------------------------------------- rota

def calcular_rota(grafo, no_origem, no_destino):
    """A* com heuristica haversine admissivel. Devolve (segundos, caminho)."""
    if no_origem == no_destino:
        return 0.0, [no_origem]
    heuristica = heuristica_haversine(grafo, no_destino, VELOCIDADE_MAX_KMH)
    resultado = busca_caminho_minimo(grafo, no_origem, {no_destino}, h=heuristica)
    if no_destino not in resultado.custos:
        raise DestinoInalcancavel(f"sem rota de {no_origem} ate {no_destino}")
    return (resultado.custos[no_destino],
            reconstruir_caminho(resultado.anterior, no_origem, no_destino))


def comprimento_metros(grafo, caminho):
    from algoritmos.grafo import haversine
    return sum(
        haversine(*grafo.coordenadas(a), *grafo.coordenadas(b))
        for a, b in zip(caminho, caminho[1:])
    )


def estimar_custo(segundos, metros):
    return round(TARIFA_BASE + POR_MINUTO * (segundos / 60) + POR_KM * (metros / 1000), 2)


# --------------------------------------------------------------- alocacao

def alocar_motorista(sessao, grafo, registro, corrida, config):
    """Escolhe o motorista de menor ETA REAL e o reserva.

    1. Indice espacial corta de milhares para ~20 candidatos plausiveis.
    2. UMA busca reversa da o tempo real de todos eles de uma vez.
    3. A reserva e otimista: `UPDATE ... WHERE disponivel = 1`. Se afetou
       zero linhas, outro pedido ganhou a corrida pelo mesmo motorista --
       segue para o proximo do ranking, sem travar a tabela.
    """
    lat, lon = grafo.coordenadas(corrida.no_origem)
    candidatos = registro.candidatos(lat, lon, config.raio_busca_m,
                                     config.max_candidatos)
    if not candidatos:
        raise SemMotoristaDisponivel("nenhum motorista disponivel no raio")

    ranking = motoristas_mais_proximos(
        grafo, corrida.no_origem, candidatos,
        limite_segundos=config.limite_matching_s,
    )
    if not ranking:
        raise SemMotoristaDisponivel(
            "ha motoristas por perto, mas nenhum alcanca o passageiro a tempo"
        )

    for candidato in ranking:
        afetadas = sessao.execute(
            update(Motorista)
            .where(Motorista.id == candidato.motorista_id,
                   Motorista.disponivel.is_(True))
            .values(disponivel=False)
        ).rowcount
        if afetadas == 1:
            registro.definir_disponibilidade(candidato.motorista_id, False)
            corrida.motorista_id = candidato.motorista_id
            corrida.eta_segundos = candidato.eta_segundos
            transitar(sessao, corrida, E.ALOCACAO)
            return candidato

    raise SemMotoristaDisponivel(
        "todos os candidatos foram alocados a outros pedidos neste instante"
    )


def liberar_motorista(sessao, registro, motorista_id):
    if motorista_id is None:
        return
    sessao.execute(
        update(Motorista).where(Motorista.id == motorista_id).values(disponivel=True)
    )
    registro.definir_disponibilidade(motorista_id, True)


# ----------------------------------------------------------------- fluxo

def definir_rota(sessao, grafo, corrida):
    """Calcula a rota da corrida e avanca o estado para `rota`."""
    segundos, caminho = calcular_rota(grafo, corrida.no_origem, corrida.no_destino)
    corrida.custo_estimado = estimar_custo(segundos, comprimento_metros(grafo, caminho))
    transitar(sessao, corrida, E.ROTA)
    return segundos, caminho


def registrar_pagamento(sessao, corrida):
    """So roda depois que `transitar` aceitou concluida -> paga."""
    transitar(sessao, corrida, E.PAGA)
    pagamento = Pagamento(corrida_id=corrida.id,
                          valor=corrida.custo_estimado or 0.0)
    sessao.add(pagamento)
    return pagamento
