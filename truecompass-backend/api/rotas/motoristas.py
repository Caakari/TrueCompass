# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.deps import (motorista_atual, obter_conexoes, obter_indice_nos,
                      obter_registro)
from api.esquemas import DisponibilidadeEntrada, PosicaoEntrada
from api.eventos import mensagem_posicao
from dominio import estados as E
from infra.banco import obter_sessao
from infra.modelos import Corrida, Motorista

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
    motorista.disponivel = dados.disponivel
    sessao.commit()
    registro.definir_disponibilidade(motorista.id, dados.disponivel)
    return {"disponivel": dados.disponivel, "motoristas_online": len(registro)}
