# -*- coding: utf-8 -*-
"""Acompanhamento PUBLICO de uma corrida, pelo link que o passageiro compartilha.

Sem login, de proposito: quem recebe o link (familia, amigo) nao tem conta.
A protecao e o token aleatorio da corrida, e o que sai daqui e o MINIMO
(`AcompanhamentoSaida`): primeiro nome, carro, placa, posicao e trajeto.

`def`, e nao `async def`: calcula rota (A*), que e CPU-bound.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.deps import obter_alt, obter_geometria, obter_grafo
from api.esquemas import AcompanhamentoSaida, ParadaSaida
from api.rotas.corridas import paradas_da_corrida
from dominio import estados as E
from dominio.servicos import corrida as servico
from infra.banco import obter_sessao
from infra.modelos import Corrida, Motorista, Usuario

rotas = APIRouter(prefix="/publico", tags=["publico"])

ESTADOS_ATIVOS = (E.ALOCACAO, E.ROTA, E.EM_CURSO)


def _primeiro_nome(nome):
    return nome.split()[0] if nome else None


@rotas.get("/acompanhar/{token}", response_model=AcompanhamentoSaida)
def acompanhar(token: str, sessao: Session = Depends(obter_sessao),
               grafo=Depends(obter_grafo), alt=Depends(obter_alt),
               geometria=Depends(obter_geometria)):
    corrida = (sessao.query(Corrida).filter_by(token_compartilhar=token).one_or_none()
               if len(token) >= 16 else None)
    if corrida is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "link de acompanhamento invalido")

    ativa = corrida.estado in ESTADOS_ATIVOS
    passageiro = sessao.get(Usuario, corrida.passageiro_id)
    motorista = sessao.get(Motorista, corrida.motorista_id) if corrida.motorista_id else None
    saida = AcompanhamentoSaida(
        estado=corrida.estado, ativa=ativa,
        passageiro=_primeiro_nome(passageiro.nome if passageiro else None),
        destino_texto=corrida.destino_texto,
        origem=grafo.coordenadas(corrida.no_origem) if corrida.no_origem in grafo.nos else None,
        destino=grafo.coordenadas(corrida.no_destino) if corrida.no_destino in grafo.nos else None,
    )
    paradas = paradas_da_corrida(sessao, corrida.id)
    saida.paradas = [ParadaSaida(lat=p.lat, lon=p.lon, texto=p.texto) for p in paradas]
    if motorista is not None:
        saida.motorista = _primeiro_nome(motorista.usuario.nome if motorista.usuario else None)
        saida.carro = " ".join(filter(None, [motorista.modelo, motorista.cor_carro])) or None
        saida.placa = motorista.placa

    # Corrida encerrada: o link continua valido, mas para de mostrar posicao.
    if not ativa:
        return saida

    if motorista is not None and motorista.lat is not None:
        saida.posicao_motorista = (motorista.lat, motorista.lon)
    em_viagem = (corrida.estado == E.EM_CURSO and motorista is not None
                 and motorista.no_atual in grafo.nos)
    try:
        if em_viagem and not paradas:
            # Em viagem, sem paradas: o que FALTA, da posicao atual ao destino.
            segundos, caminho = servico.rota_por_paradas(
                grafo, [motorista.no_atual, corrida.no_destino], alt=alt)
            saida.segundos_restantes = segundos
        else:
            # Com paradas, o servidor nao sabe quais ja foram visitadas: mostra
            # o trajeto planejado e NAO inventa um tempo restante.
            nos = [corrida.no_origem, *(p.no for p in paradas), corrida.no_destino]
            _segundos, caminho = servico.rota_por_paradas(grafo, nos, alt=alt)
        saida.pontos = servico.tracado(grafo, caminho, geometria)
    except servico.DestinoInalcancavel:
        pass
    return saida
