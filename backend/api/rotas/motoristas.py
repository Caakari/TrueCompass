# -*- coding: utf-8 -*-
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from api.deps import (motorista_atual, obter_conexoes, obter_indice_nos,
                      obter_registro)
from api.esquemas import DisponibilidadeEntrada, PosicaoEntrada
from api.eventos import mensagem_posicao
from dominio import estados as E
from infra.banco import obter_sessao
from infra.modelos import Corrida, Motorista, Pagamento

# Sao Paulo: UTC-3 o ano todo (o horario de verao acabou em 2019). Offset fixo
# em vez de zoneinfo para nao depender do tzdata da imagem do deploy.
FUSO_SP = timezone(timedelta(hours=-3))

# Estados em que o motorista esta comprometido com uma corrida e o passageiro
# quer ver o carro se mexendo no mapa.
ESTADOS_ATIVOS = (E.ALOCACAO, E.ROTA, E.EM_CURSO)

rotas = APIRouter(prefix="/motoristas", tags=["motoristas"])


@rotas.post("/posicao")
def atualizar_posicao(dados: PosicaoEntrada,
                      motorista: Motorista = Depends(motorista_atual),
                      registro=Depends(obter_registro),
                      indice_nos=Depends(obter_indice_nos),
                      conexoes=Depends(obter_conexoes),
                      sessao: Session = Depends(obter_sessao)):
    """Ping de GPS. Endpoint de altissima frequencia.

    A posicao vai para a MEMORIA, nao para o banco: milhares de motoristas
    pingando a cada poucos segundos derrubariam o MySQL se cada ping virasse
    um INSERT. O banco recebe a ultima posicao conhecida em lote.
    """
    no = indice_nos.mais_proximo(dados.lat, dados.lon)
    registro.atualizar(motorista.id, dados.lat, dados.lon, no)

    motorista.lat, motorista.lon, motorista.no_atual = dados.lat, dados.lon, no

    # Se ha corrida em andamento, o passageiro acompanha o carro no mapa.
    corrida = (sessao.query(Corrida)
               .filter(Corrida.motorista_id == motorista.id,
                       Corrida.estado.in_(ESTADOS_ATIVOS))
               .order_by(Corrida.id.desc()).first())
    sessao.commit()
    if corrida:
        conexoes.publicar(corrida.id, mensagem_posicao(corrida.id, motorista.id,
                                                       dados.lat, dados.lon))
    return {"no_ancorado": no, "lat": dados.lat, "lon": dados.lon,
            "corrida_ativa": corrida.id if corrida else None}


@rotas.post("/disponibilidade")
def definir_disponibilidade(dados: DisponibilidadeEntrada,
                            motorista: Motorista = Depends(motorista_atual),
                            registro=Depends(obter_registro),
                            sessao: Session = Depends(obter_sessao)):
    if dados.disponivel and not (motorista.placa or "").strip():
        # Conta criada pelo Google nao informou a placa.
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "cadastre a placa do carro no seu perfil antes de ficar online")
    motorista.disponivel = dados.disponivel
    sessao.commit()
    registro.definir_disponibilidade(motorista.id, dados.disponivel)
    return {"disponivel": dados.disponivel, "motoristas_online": len(registro)}


def inicio_do_dia_utc(agora=None):
    """Meia-noite de hoje em Sao Paulo, em UTC sem fuso (como o banco grava)."""
    agora = agora or datetime.now(timezone.utc)
    meia_noite = agora.astimezone(FUSO_SP).replace(hour=0, minute=0, second=0, microsecond=0)
    return meia_noite.astimezone(timezone.utc).replace(tzinfo=None)


@rotas.get("/resumo")
def resumo(motorista: Motorista = Depends(motorista_atual),
           sessao: Session = Depends(obter_sessao)):
    """Ganhos e corridas de HOJE, para o painel do motorista.

    Sai dos pagamentos gravados, nao de uma conta no app: o valor so entra
    depois que o passageiro paga -- a mesma regra do DAG (concluida -> paga).
    """
    inicio = inicio_do_dia_utc()
    corridas, ganhos = (sessao.query(func.count(Pagamento.id), func.coalesce(func.sum(Pagamento.valor), 0.0))
                        .join(Corrida, Corrida.id == Pagamento.corrida_id)
                        .filter(Corrida.motorista_id == motorista.id,
                                Pagamento.processado_em >= inicio)
                        .one())
    total = (sessao.query(func.count(Corrida.id))
             .filter(Corrida.motorista_id == motorista.id,
                     Corrida.estado.in_((E.CONCLUIDA, E.PAGA)))
             .scalar()) or 0
    return {"ganhos_hoje": round(float(ganhos), 2), "corridas_hoje": int(corridas),
            "corridas_total": int(total)}
