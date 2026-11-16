# -*- coding: utf-8 -*-
"""Regras de negocio da corrida.

Orquestra as tres pecas algoritmicas sem conhecer HTTP:
  indice espacial (filtro)  ->  busca reversa (ETA real)  ->  A* (rota)
e submete toda mudanca de estado ao DAG.
"""

import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import update

from algoritmos.busca import busca_caminho_minimo, reconstruir_caminho
from algoritmos.contracao import Geometria
from algoritmos.grafo import haversine, heuristica_haversine
from algoritmos.matching import motoristas_mais_proximos
from dominio import estados as E
from infra.modelos import Corrida, CorridaTransicao, Motorista, Oferta, Pagamento

TARIFA_BASE = 5.00
POR_MINUTO = 0.80
POR_KM = 1.90

# Categorias de viagem. O multiplicador incide sobre a tarifa INTEIRA (base,
# tempo e distancia): a rota e a mesma, so muda o carro. No prototipo todo
# motorista atende todas as categorias -- por isso o tempo de chegada do
# motorista e o mesmo nos tres cartoes, e isso e dito, nao escondido.
CATEGORIA_PADRAO = "economico"
# Os nomes sobem com o conforto (Essencial < Conforto < Premium). As CHAVES
# ficam como estavam: sao elas que estao gravadas em corridas.categoria, e
# trocar a chave apagaria a categoria das corridas antigas no historico.
CATEGORIAS = {
    "economico": {"nome": "Essencial", "lugares": 4, "fator": 1.00,
                  "descricao": "Viagens do dia a dia, preço justo"},
    "conforto": {"nome": "Conforto", "lugares": 4, "fator": 1.35,
                 "descricao": "Carros mais novos, ar e espaço extra"},
    "grande": {"nome": "Premium", "lugares": 6, "fator": 1.60,
               "descricao": "O mais confortável, até 6 pessoas"},
}


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

def calcular_rota(grafo, no_origem, no_destino, alt=None):
    """A* ate o destino. Devolve (segundos, caminho).

    Com `alt`, usa a heuristica de marcos (ALT), muito mais apertada; sem ela,
    cai na haversine. As duas sao admissiveis, logo a rota devolvida e a mesma
    -- muda so quanto do grafo precisa ser explorado para encontra-la.

    O divisor da haversine e a velocidade maxima MEDIDA no proprio grafo, e
    nao um teto fixo: a malha real de Sao Paulo tem trecho a 110 km/h, e um
    teto de 100 faria h superestimar ali.
    """
    if no_origem == no_destino:
        return 0.0, [no_origem]
    heuristica = (alt.heuristica(no_destino, origem=no_origem) if alt
                  else heuristica_haversine(grafo, no_destino))
    resultado = busca_caminho_minimo(grafo, no_origem, {no_destino}, h=heuristica)
    if no_destino not in resultado.custos:
        raise DestinoInalcancavel(f"sem rota de {no_origem} ate {no_destino}")
    return (resultado.custos[no_destino],
            reconstruir_caminho(resultado.anterior, no_origem, no_destino))


SEM_GEOMETRIA = Geometria()


def tracado(grafo, caminho, geometria=None):
    """Polilinha para o mapa: cruzamentos E a forma das ruas entre eles.

    A malha e contraida (so cruzamentos viram nos); sem a geometria, a rota
    seria desenhada cortando quarteiroes em linha reta a cada curva.
    """
    return (geometria or SEM_GEOMETRIA).tracado(grafo, caminho)


def comprimento_metros(grafo, caminho, geometria=None):
    """Metros pelo tracado real -- e o que a tarifa por km cobra."""
    return (geometria or SEM_GEOMETRIA).comprimento_m(grafo, caminho)


def estimar_custo(segundos, metros, categoria=CATEGORIA_PADRAO):
    """Tarifa = (base + por minuto + por km) x fator da categoria."""
    base = TARIFA_BASE + POR_MINUTO * (segundos / 60) + POR_KM * (metros / 1000)
    return round(base * CATEGORIAS[categoria]["fator"], 2)


def opcoes_de_viagem(segundos, metros):
    """Os cartoes de categoria da previa, do mais barato ao mais caro."""
    return [{"id": chave, "nome": c["nome"], "lugares": c["lugares"],
             "descricao": c["descricao"], "custo": estimar_custo(segundos, metros, chave)}
            for chave, c in CATEGORIAS.items()]


MAXIMO_PONTOS_EXPLORACAO = 2500


def ordem_de_descoberta(grafo, resultado, passo=1):
    """Coordenadas dos nos que a busca alcancou, NA ORDEM em que os alcancou.

    `resultado.distancias` e um dict, e dict do Python preserva a ordem de
    insercao: a chave entra quando o no e alcancado pela primeira vez (entra
    na fila), e relaxamentos posteriores so atualizam o valor. Entao a
    sequencia das chaves e a frente de onda da busca, de graca -- sem tocar
    no laco do algoritmo.

    E isso que o front anima: o Dijkstra se espalha em circulo, o A* em gota
    apontada ao destino. Amostrada com `passo` fixo, preservando a ordem (a
    forma da onda nao muda).
    """
    nos = list(resultado.distancias)
    return [[round(c, 5) for c in grafo.coordenadas(no)] for no in nos[::passo]]


def passo_comum(*resultados, maximo=MAXIMO_PONTOS_EXPLORACAO):
    """Um UNICO passo de amostragem para todas as buscas comparadas.

    Amostrar cada uma para `maximo` pontos apagaria a diferenca que se quer
    mostrar: Dijkstra e A* sairiam do mesmo tamanho. Com o mesmo passo, a
    proporcao de nos descobertos se preserva -- e o A* termina antes.
    """
    maior = max(len(r.distancias) for r in resultados)
    return max(1, -(-maior // maximo))             # teto da divisao


MAXIMO_PARADAS = 3


def rota_por_paradas(grafo, nos, alt=None):
    """Caminho minimo que passa pelos `nos` NA ORDEM dada: (segundos, caminho).

    Com a ordem fixa, o caminho minimo e exatamente a concatenacao dos
    minimos de cada trecho: qualquer caminho valido se decompoe nos mesmos
    trechos, e trocar um trecho pelo minimo dele so diminui o total. Por
    isso basta um A* por trecho (com a heuristica apontando para o fim
    DAQUELE trecho). O teste-oraculo confere contra o Dijkstra.
    """
    total, caminho = 0.0, [nos[0]]
    for a, b in zip(nos, nos[1:]):
        if a == b:
            continue                     # parada no mesmo cruzamento: trecho vazio
        segundos, trecho = calcular_rota(grafo, a, b, alt=alt)
        total += segundos
        caminho.extend(trecho[1:])
    return total, caminho


def _passo_da_soma(totais, maximo=MAXIMO_PONTOS_EXPLORACAO):
    """Passo comum quando cada busca e a SOMA de varios trechos."""
    maior = max(totais) if totais else 0
    return max(1, -(-maior // maximo))


def estimar_viagem(grafo, indice_nos, origem, destino, *, paradas=(), registro=None,
                   config=None, semaforos=frozenset(), comparar=False,
                   explorar=False, geometria=None, alt=None):
    """Previa da viagem, ANTES de pedir: rota, tempo, distancia e preco.

    `origem`/`destino` (e cada uma das `paradas`) sao (lat, lon) do endereco
    escolhido. Cada ponto e ancorado ao cruzamento mais proximo pela
    quadtree, e um A* roda por TRECHO (origem -> parada 1 -> ... -> destino)
    -- exatamente o calculo que o pedido de corrida fara depois.

    Com `registro`, mede tambem o ETA REAL do motorista mais proximo (busca
    reversa, a mesma do pareamento). Com `comparar`, roda o Dijkstra sobre os
    mesmos trechos e devolve os dois contadores de nos expandidos: o custo tem
    de ser identico (o Dijkstra e o oraculo), so o esforco muda.

    Com `explorar`, devolve tambem a frente de onda de cada busca (ver
    `ordem_de_descoberta`), trecho apos trecho, para o front desenhar o
    algoritmo trabalhando.
    """
    if len(paradas) > MAXIMO_PARADAS:
        raise DestinoInalcancavel(f"no maximo {MAXIMO_PARADAS} paradas")
    pontos_viagem = [origem, *paradas, destino]
    nos = [indice_nos.mais_proximo(*p) for p in pontos_viagem]
    if any(no is None for no in nos):
        raise DestinoInalcancavel("coordenadas fora da area coberta pela malha")

    trechos = [(a, b) for a, b in zip(nos, nos[1:]) if a != b]
    segundos, caminho, expandidos, buscas = 0.0, [nos[0]], 0, []
    inicio = time.perf_counter()
    for a, b in trechos:
        heuristica = (alt.heuristica(b, origem=a) if alt else heuristica_haversine(grafo, b))
        resultado = busca_caminho_minimo(grafo, a, {b}, h=heuristica)
        if b not in resultado.custos:
            raise DestinoInalcancavel(f"sem rota de {a} ate {b}")
        segundos += resultado.custos[b]
        caminho.extend(reconstruir_caminho(resultado.anterior, a, b)[1:])
        expandidos += resultado.nos_expandidos
        buscas.append(resultado)
    ms_a_estrela = (time.perf_counter() - inicio) * 1000

    metros = comprimento_metros(grafo, caminho, geometria)
    pontos = tracado(grafo, caminho, geometria)
    saida = {
        "segundos": segundos,
        "metros": metros,
        "custo_estimado": estimar_custo(segundos, metros),
        "categorias": opcoes_de_viagem(segundos, metros),
        "pontos": pontos,
        "semaforos_no_caminho": sum(1 for no in caminho if no in semaforos),
        # Quanto o endereco esta do cruzamento onde a rota comeca/termina:
        # o front desenha esse trecho a pe, tracejado.
        "ancoragem_m": {
            "origem": haversine(*origem, *pontos[0]),
            "destino": haversine(*destino, *pontos[-1]),
        },
        "paradas": [{"lat": lat, "lon": lon} for lat, lon in
                    (grafo.coordenadas(no) for no in nos[1:-1])],
        "algoritmo": {
            "a_estrela": {"nos_expandidos": expandidos, "ms": round(ms_a_estrela, 1)},
            "heuristica": "alt" if alt else "haversine",
            "velocidade_max_kmh": round(grafo.velocidade_maxima_kmh(), 1),
            "nos_na_malha": len(grafo.nos),
            "trechos": len(trechos),
        },
        "motoristas": None,
    }
    oraculos = []
    if comparar and trechos:
        inicio = time.perf_counter()
        custo_oraculo = 0.0
        for a, b in trechos:
            oraculo = busca_caminho_minimo(grafo, a, {b})
            custo_oraculo += oraculo.custos[b]
            oraculos.append(oraculo)
        saida["algoritmo"]["dijkstra"] = {
            "nos_expandidos": sum(o.nos_expandidos for o in oraculos),
            "ms": round((time.perf_counter() - inicio) * 1000, 1),
            "mesmo_custo": abs(custo_oraculo - segundos) < 1e-6,
        }

    if explorar:
        totais = [sum(len(b.distancias) for b in grupo) for grupo in (buscas, oraculos) if grupo]
        passo = _passo_da_soma(totais) if totais else 1
        saida["exploracao"] = {
            "a_estrela": [p for b in buscas for p in ordem_de_descoberta(grafo, b, passo)],
        }
        if oraculos:
            saida["exploracao"]["dijkstra"] = [p for b in oraculos for p in ordem_de_descoberta(grafo, b, passo)]

    if registro is not None and config is not None:
        lat, lon = grafo.coordenadas(nos[0])
        candidatos = registro.candidatos(lat, lon, config.raio_busca_m,
                                         config.max_candidatos)
        ranking = motoristas_mais_proximos(
            grafo, nos[0], candidatos, limite_segundos=config.limite_matching_s,
        ) if candidatos else []
        saida["motoristas"] = {
            "proximos": len(candidatos),
            "eta_mais_proximo_s": ranking[0].eta_segundos if ranking else None,
        }
    return saida


# --------------------------------------------------------------- alocacao

class OfertaInvalida(Exception):
    pass


def agora_utc():
    """Agora em UTC SEM fuso: e como o banco grava e devolve as datas."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def oferta_pendente(sessao, corrida_id):
    return (sessao.query(Oferta)
            .filter_by(corrida_id=corrida_id, status="pendente")
            .order_by(Oferta.id.desc()).first())


def oferecer(sessao, grafo, registro, corrida, config, agora=None):
    """Oferece a corrida ao motorista de menor ETA REAL que ainda nao a recebeu.

    1. Indice espacial corta de milhares para ~20 candidatos plausiveis.
    2. UMA busca reversa da o tempo real de todos eles de uma vez.
    3. Quem ja recebeu esta corrida (recusou ou deixou expirar) sai da lista.
    4. A reserva e otimista: `UPDATE ... WHERE disponivel = 1`. Se afetou
       zero linhas, outro pedido ganhou o motorista -- segue para o proximo,
       sem travar a tabela.

    O motorista fica reservado (indisponivel) enquanto a oferta esta aberta:
    sem isso, ele receberia duas ofertas ao mesmo tempo.
    """
    agora = agora or agora_utc()
    lat, lon = grafo.coordenadas(corrida.no_origem)
    candidatos = registro.candidatos(lat, lon, config.raio_busca_m,
                                     config.max_candidatos)
    if not candidatos:
        raise SemMotoristaDisponivel("nenhum motorista disponivel no raio")

    ranking = motoristas_mais_proximos(
        grafo, corrida.no_origem, candidatos,
        limite_segundos=config.limite_matching_s,
    )
    ja_ofertados = {m for (m,) in sessao.query(Oferta.motorista_id)
                    .filter(Oferta.corrida_id == corrida.id)}
    ranking = [c for c in ranking if c.motorista_id not in ja_ofertados]
    if not ranking:
        raise SemMotoristaDisponivel(
            "ha motoristas por perto, mas nenhum alcanca o passageiro a tempo"
            if not ja_ofertados else "nenhum motorista aceitou a corrida")

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
            sessao.add(Oferta(corrida_id=corrida.id, motorista_id=candidato.motorista_id,
                              eta_segundos=candidato.eta_segundos,
                              expira_em=agora + timedelta(seconds=config.prazo_oferta_s)))
            if corrida.estado == E.PEDIDO:
                transitar(sessao, corrida, E.ALOCACAO)
            return candidato

    raise SemMotoristaDisponivel(
        "todos os candidatos foram alocados a outros pedidos neste instante"
    )


# Nome antigo, mantido: "alocar" hoje e "oferecer ao primeiro do ranking".
alocar_motorista = oferecer


def _fechar_oferta(sessao, oferta, novo_status, agora, exigir_prazo=False):
    """pendente -> novo_status, de forma otimista. True se ESTA chamada fechou.

    `exigir_prazo`: so fecha se a oferta ainda nao venceu (usado no aceite).
    """
    consulta = (update(Oferta)
                .where(Oferta.id == oferta.id, Oferta.status == "pendente")
                .values(status=novo_status, respondida_em=agora))
    if exigir_prazo:
        consulta = consulta.where(Oferta.expira_em > agora)
    fechou = sessao.execute(consulta).rowcount == 1
    if fechou:
        oferta.status = novo_status
    return fechou


def _passar_adiante(sessao, grafo, registro, corrida, config, agora):
    """Libera o motorista atual e oferece ao proximo; sem proximo, cancela."""
    liberar_motorista(sessao, registro, corrida.motorista_id)
    corrida.motorista_id = None
    corrida.eta_segundos = None
    try:
        oferecer(sessao, grafo, registro, corrida, config, agora)
    except SemMotoristaDisponivel:
        corrida.motivo_cancelamento = "nenhum motorista aceitou"
        transitar(sessao, corrida, E.CANCELADA)


def aceitar_oferta(sessao, corrida, motorista, agora=None):
    """O motorista da oferta aberta aceita dentro do prazo: alocacao -> rota."""
    agora = agora or agora_utc()
    oferta = oferta_pendente(sessao, corrida.id)
    if corrida.estado != E.ALOCACAO or oferta is None or oferta.motorista_id != motorista.id:
        raise OfertaInvalida("nao ha oferta aberta desta corrida para voce")
    if not _fechar_oferta(sessao, oferta, "aceita", agora, exigir_prazo=True):
        raise OfertaInvalida("a oferta expirou")
    transitar(sessao, corrida, E.ROTA)
    return oferta


def recusar_oferta(sessao, grafo, registro, corrida, motorista, config, agora=None):
    """O motorista recusa: a oferta vai para o proximo do ranking."""
    agora = agora or agora_utc()
    oferta = oferta_pendente(sessao, corrida.id)
    if corrida.estado != E.ALOCACAO or oferta is None or oferta.motorista_id != motorista.id:
        raise OfertaInvalida("nao ha oferta aberta desta corrida para voce")
    if _fechar_oferta(sessao, oferta, "recusada", agora):
        _passar_adiante(sessao, grafo, registro, corrida, config, agora)
    return oferta


def expirar_ofertas(sessao, grafo, registro, config, agora=None):
    """Ofertas vencidas sem resposta: passa cada corrida adiante.

    Chamada periodicamente pelo servidor (laco no `lifespan`). Devolve as
    corridas que mudaram, para quem chamou publicar DEPOIS do commit.
    """
    agora = agora or agora_utc()
    vencidas = (sessao.query(Oferta)
                .filter(Oferta.status == "pendente", Oferta.expira_em <= agora).all())
    mudaram = []
    for oferta in vencidas:
        corrida = sessao.get(Corrida, oferta.corrida_id)
        if corrida is None or corrida.estado != E.ALOCACAO:
            _fechar_oferta(sessao, oferta, "cancelada", agora)
            continue
        if _fechar_oferta(sessao, oferta, "expirada", agora):
            _passar_adiante(sessao, grafo, registro, corrida, config, agora)
            mudaram.append(corrida)
    return mudaram


def segundos_para_responder(oferta, agora=None):
    """Prazo restante, calculado no servidor (relogio do celular nao e confiavel)."""
    agora = agora or agora_utc()
    return max(0.0, (oferta.expira_em - agora).total_seconds())


def liberar_motorista(sessao, registro, motorista_id):
    if motorista_id is None:
        return
    sessao.execute(
        update(Motorista).where(Motorista.id == motorista_id).values(disponivel=True)
    )
    registro.definir_disponibilidade(motorista_id, True)


# ----------------------------------------------------------------- fluxo

def calcular_preco(grafo, corrida, alt=None, geometria=None,
                   categoria=CATEGORIA_PADRAO, paradas=()):
    """Rota da corrida (pelas paradas) e o preco, gravado em `custo_estimado`.

    Os metros saem do TRACADO (`geometria`), exatamente como na previa: sem
    ela, numa malha contraida, cada curva viraria corda e a corrida cobraria
    menos do que o passageiro viu antes de confirmar.

    Calculado no PEDIDO, antes do aceite: o motorista ve o valor na oferta.
    """
    nos = [corrida.no_origem, *paradas, corrida.no_destino]
    segundos, caminho = rota_por_paradas(grafo, nos, alt=alt)
    corrida.custo_estimado = estimar_custo(
        segundos, comprimento_metros(grafo, caminho, geometria), categoria)
    return segundos, caminho


def definir_rota(sessao, grafo, corrida, alt=None, geometria=None,
                 categoria=CATEGORIA_PADRAO, paradas=()):
    """Preco e rota, e avanca para `rota` (fluxo sem aceite, usado em testes)."""
    resultado = calcular_preco(grafo, corrida, alt, geometria, categoria, paradas)
    transitar(sessao, corrida, E.ROTA)
    return resultado


def registrar_pagamento(sessao, corrida):
    """So roda depois que `transitar` aceitou concluida -> paga."""
    transitar(sessao, corrida, E.PAGA)
    pagamento = Pagamento(corrida_id=corrida.id,
                          valor=corrida.custo_estimado or 0.0)
    sessao.add(pagamento)
    return pagamento
