# -*- coding: utf-8 -*-
"""Previa da viagem: a rota real entre dois enderecos, antes de pedir.

E o que o app mostra quando a pessoa escolhe o destino -- tracado, tempo,
distancia e preco -- calculado pelo MESMO A* que o pedido usara depois.

`def`, nunca `async def`: o A* e CPU-bound e travaria o event loop.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from api.esquemas import ParadaEntrada

from api.deps import (config, obter_alt, obter_geometria, obter_grafo, obter_indice_nos,
                      obter_nos_semaforizados, obter_registro, usuario_atual)
from dominio.servicos import corrida as servico

rotas = APIRouter(prefix="/viagens", tags=["viagens"])


class EstimativaEntrada(BaseModel):
    origem_lat: float = Field(ge=-90, le=90)
    origem_lon: float = Field(ge=-180, le=180)
    destino_lat: float = Field(ge=-90, le=90)
    destino_lon: float = Field(ge=-180, le=180)
    comparar: bool = Field(default=False,
                           description="roda tambem o Dijkstra, como oraculo")
    explorar: bool = Field(default=False,
                           description="devolve a frente de onda de cada busca")
    paradas: list[ParadaEntrada] = Field(default_factory=list, max_length=3)


@rotas.post("/estimativa")
def estimativa(dados: EstimativaEntrada,
               _usuario=Depends(usuario_atual),
               grafo=Depends(obter_grafo),
               indice_nos=Depends(obter_indice_nos),
               registro=Depends(obter_registro),
               semaforos=Depends(obter_nos_semaforizados),
               geometria=Depends(obter_geometria),
               alt=Depends(obter_alt),
               cfg=Depends(config)):
    try:
        return servico.estimar_viagem(
            grafo, indice_nos,
            (dados.origem_lat, dados.origem_lon),
            (dados.destino_lat, dados.destino_lon),
            paradas=[(p.lat, p.lon) for p in dados.paradas],
            registro=registro, config=cfg, semaforos=semaforos,
            comparar=dados.comparar, explorar=dados.explorar,
            geometria=geometria, alt=alt,
        )
    except servico.DestinoInalcancavel as erro:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(erro))
