# -*- coding: utf-8 -*-
"""Contratos de entrada e saida da API (Pydantic)."""

from pydantic import BaseModel, EmailStr, Field


class RegistroEntrada(BaseModel):
    nome: str = Field(min_length=2, max_length=120)
    email: EmailStr
    senha: str = Field(min_length=8, max_length=72)   # 72 = teto do bcrypt
    tipo: str = Field(pattern="^(passageiro|motorista)$")
    placa: str | None = Field(default=None, max_length=10)
    modelo: str | None = Field(default=None, max_length=60)


class LoginEntrada(BaseModel):
    email: EmailStr
    senha: str


class TokenSaida(BaseModel):
    token: str
    tipo_token: str = "bearer"
    usuario_id: int
    tipo: str


class PosicaoEntrada(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class DisponibilidadeEntrada(BaseModel):
    disponivel: bool


class CorridaEntrada(BaseModel):
    origem_lat: float = Field(ge=-90, le=90)
    origem_lon: float = Field(ge=-180, le=180)
    destino_lat: float = Field(ge=-90, le=90)
    destino_lon: float = Field(ge=-180, le=180)


class CorridaSaida(BaseModel):
    id: int
    estado: str
    motorista_id: int | None = None
    eta_segundos: float | None = None
    custo_estimado: float | None = None
    no_origem: int
    no_destino: int


class RotaSaida(BaseModel):
    segundos: float
    metros: float
    pontos: list[tuple[float, float]]      # [lat, lon] para o Leaflet desenhar
