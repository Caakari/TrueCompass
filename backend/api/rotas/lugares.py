# -*- coding: utf-8 -*-
"""Busca de lugares reais (enderecos, estabelecimentos, pontos de interesse).

Encaminha ao Photon/Nominatim pela camada `infra.geocodificacao`, recortando
o resultado a area coberta pela malha. Exige login: sem isso o endpoint
viraria um proxy aberto para servicos publicos que tem limite de uso.

Endpoints `def`, nao `async def`: a chamada de rede e bloqueante (urllib) e,
no threadpool, nao segura o event loop.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.deps import obter_caixa, usuario_atual
from infra import geocodificacao as geo

rotas = APIRouter(prefix="/lugares", tags=["lugares"])


def _fora_do_ar(erro):
    return HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                         f"busca de lugares indisponivel: {erro}")


@rotas.get("/buscar")
def buscar(q: str = Query(min_length=1, max_length=120),
           lat: float | None = Query(default=None, ge=-90, le=90),
           lon: float | None = Query(default=None, ge=-180, le=180),
           completo: bool = Query(default=False,
                                  description="Enter confirmado: inclui Nominatim"),
           limite: int = Query(default=8, ge=1, le=15),
           caixa=Depends(obter_caixa),
           _usuario=Depends(usuario_atual)):
    """Lugares que casam com `q`, dentro da area da malha.

    `lat`/`lon` (opcionais) puxam o ranking para perto de quem busca.
    """
    if caixa is None:
        return {"lugares": [], "area": None}
    perto = (lat, lon) if lat is not None and lon is not None else None
    try:
        lugares = geo.buscar_lugares(q, caixa, perto=perto, limite=limite,
                                     completo=completo)
    except geo.GeocodificacaoIndisponivel as erro:
        raise _fora_do_ar(erro)
    return {"lugares": lugares, "area": caixa}


@rotas.get("/reverso")
def reverso(lat: float = Query(ge=-90, le=90), lon: float = Query(ge=-180, le=180),
            caixa=Depends(obter_caixa),
            _usuario=Depends(usuario_atual)):
    """Endereco do ponto (GPS do aparelho, ou pino arrastado no mapa)."""
    dentro = bool(caixa) and (caixa["sul"] <= lat <= caixa["norte"]
                              and caixa["oeste"] <= lon <= caixa["leste"])
    try:
        lugar = geo.endereco_do_ponto(lat, lon)
    except geo.GeocodificacaoIndisponivel as erro:
        raise _fora_do_ar(erro)
    if lugar is None:
        lugar = {"id": f"ponto:{lat:.5f},{lon:.5f}", "titulo": "Local marcado",
                 "detalhe": f"{lat:.5f}, {lon:.5f}", "categoria": "endereco",
                 "lat": lat, "lon": lon}
    return {"lugar": lugar, "dentro_da_area": dentro}
