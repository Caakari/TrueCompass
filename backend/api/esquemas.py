# -*- coding: utf-8 -*-
"""Contratos de entrada e saida da API (Pydantic)."""

from datetime import datetime
from typing import Literal

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
    senha: str = Field(max_length=200)
    manter_conectado: bool = False


class TokenSaida(BaseModel):
    token: str
    tipo_token: str = "bearer"
    usuario_id: int
    tipo: str
    # So com "manter conectado": troca-se por um token novo em /auth/renovar.
    renovacao: str | None = None


class PendenteSaida(BaseModel):
    confirmacao_pendente: bool = True
    email: str


class ConfirmarEmailEntrada(BaseModel):
    email: EmailStr
    codigo: str = Field(min_length=1, max_length=12)
    manter_conectado: bool = True


class EnviarCodigoEntrada(BaseModel):
    email: EmailStr
    finalidade: Literal["confirmar", "recuperar"] = "recuperar"


class RecuperarEntrada(BaseModel):
    email: EmailStr


class RedefinirEntrada(BaseModel):
    email: EmailStr
    codigo: str = Field(min_length=1, max_length=12)
    senha: str = Field(min_length=8, max_length=72)
    manter_conectado: bool = True


class GoogleEntrada(BaseModel):
    credencial: str = Field(min_length=10, max_length=4096)
    tipo: Literal["passageiro", "motorista"] | None = None
    manter_conectado: bool = True


class RenovarEntrada(BaseModel):
    renovacao: str = Field(min_length=10, max_length=200)


class PosicaoEntrada(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class DisponibilidadeEntrada(BaseModel):
    disponivel: bool


class ParadaEntrada(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    texto: str | None = Field(default=None, max_length=200)


class ParadaSaida(BaseModel):
    lat: float
    lon: float
    texto: str | None = None


class CorridaEntrada(BaseModel):
    origem_lat: float = Field(ge=-90, le=90)
    origem_lon: float = Field(ge=-180, le=180)
    destino_lat: float = Field(ge=-90, le=90)
    destino_lon: float = Field(ge=-180, le=180)
    # Ver dominio.servicos.corrida.CATEGORIAS. Opcional: cliente antigo segue
    # pedindo o Economico.
    categoria: Literal["economico", "conforto", "grande"] = "economico"
    # Simulado: nenhum pagamento real e processado. Fica registrado na corrida.
    forma_pagamento: Literal["pix", "cartao", "dinheiro"] = "pix"
    # Enderecos como o passageiro os viu, para o historico.
    origem_texto: str | None = Field(default=None, max_length=200)
    destino_texto: str | None = Field(default=None, max_length=200)
    # Paradas no caminho, NA ORDEM. Teto de 3, como nos apps de corrida.
    paradas: list[ParadaEntrada] = Field(default_factory=list, max_length=3)


class CorridaSaida(BaseModel):
    id: int
    estado: str
    motorista_id: int | None = None
    eta_segundos: float | None = None
    custo_estimado: float | None = None
    no_origem: int
    no_destino: int
    # Para o card da corrida no app: quem vem buscar, e onde.
    motorista_nome: str | None = None
    motorista_placa: str | None = None
    motorista_modelo: str | None = None
    # Corridas que o motorista ja concluiu, e a media das notas que recebeu
    # (None enquanto ninguem o avaliou: "novo", e nao "nota zero").
    motorista_corridas: int | None = None
    motorista_cor_carro: str | None = None
    motorista_nota: float | None = None
    motorista_avaliacoes: int = 0
    passageiro_nome: str | None = None
    passageiro_nota: float | None = None
    categoria: str | None = None
    forma_pagamento: str | None = None
    origem_texto: str | None = None
    destino_texto: str | None = None
    # A nota que QUEM PERGUNTA deu nesta corrida (None = ainda nao avaliou).
    minha_avaliacao: int | None = None
    paradas: list[ParadaSaida] = []
    # So o passageiro ve o token: e ele quem decide com quem compartilhar.
    token_compartilhar: str | None = None
    # Em `alocacao`: oferta aberta a um motorista, esperando o aceite.
    aguardando_aceite: bool = False
    oferta_segundos: float | None = None      # prazo restante, medido no servidor
    motivo_cancelamento: str | None = None
    origem: tuple[float, float] | None = None       # cruzamento de embarque
    destino: tuple[float, float] | None = None


class RotaSaida(BaseModel):
    segundos: float
    metros: float
    pontos: list[tuple[float, float]]      # [lat, lon] para o Leaflet desenhar
    semaforos: list[tuple[float, float]] = []   # sinais do caminho, na ordem


# ------------------------------------------------------------------ perfil

class PerfilSaida(BaseModel):
    id: int
    nome: str
    email: str
    tipo: str
    telefone: str | None = None
    cor_avatar: str | None = None
    criado_em: datetime | None = None
    # So de motorista.
    placa: str | None = None
    modelo: str | None = None
    cor_carro: str | None = None
    # Reputacao: media das notas recebidas e corridas levadas ate o fim.
    nota: float | None = None
    avaliacoes: int = 0
    corridas: int = 0


class PerfilEntrada(BaseModel):
    """Tudo opcional: so muda o que vier. String vazia apaga o campo opcional."""
    nome: str | None = Field(default=None, min_length=2, max_length=120)
    telefone: str | None = Field(default=None, pattern=r"^$|^\+?[0-9 ()-]{8,20}$")
    cor_avatar: str | None = Field(default=None, pattern=r"^$|^#[0-9A-Fa-f]{6}$")
    placa: str | None = Field(default=None, min_length=7, max_length=10)
    modelo: str | None = Field(default=None, max_length=60)
    cor_carro: str | None = Field(default=None, max_length=30)


# ---------------------------------------------------------- locais salvos

class LocalEntrada(BaseModel):
    tipo: Literal["casa", "trabalho", "outro"]
    rotulo: str | None = Field(default=None, max_length=40)   # nome do favorito
    titulo: str = Field(min_length=1, max_length=160)
    detalhe: str = Field(default="", max_length=200)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class LocalSaida(BaseModel):
    id: int
    tipo: str
    rotulo: str
    titulo: str
    detalhe: str
    lat: float
    lon: float


# ------------------------------------------------------ historico e notas

class HistoricoItem(BaseModel):
    id: int
    estado: str
    criada_em: datetime | None = None
    categoria: str | None = None
    forma_pagamento: str | None = None
    custo_estimado: float | None = None
    origem_texto: str | None = None
    destino_texto: str | None = None
    # O outro lado: o motorista para o passageiro, e vice-versa.
    outro_nome: str | None = None
    minha_avaliacao: int | None = None


class AvaliacaoEntrada(BaseModel):
    nota: int = Field(ge=1, le=5)
    comentario: str | None = Field(default=None, max_length=280)


# -------------------------------------------------------------------- chat

class MensagemEntrada(BaseModel):
    texto: str = Field(min_length=1, max_length=500)


class MensagemSaida(BaseModel):
    id: int
    autor_id: int
    texto: str
    criada_em: datetime | None = None


# ------------------------------------------------- acompanhamento publico

class AcompanhamentoSaida(BaseModel):
    """O que um link compartilhado mostra, sem login.

    De proposito, o MINIMO para quem acompanha: primeiro nome, carro, placa,
    posicao e trajeto. Nada de email, telefone, sobrenome ou historico.
    """
    estado: str
    ativa: bool
    passageiro: str | None = None           # primeiro nome
    motorista: str | None = None            # primeiro nome
    carro: str | None = None
    placa: str | None = None
    posicao_motorista: tuple[float, float] | None = None
    origem: tuple[float, float] | None = None
    destino: tuple[float, float] | None = None
    destino_texto: str | None = None
    paradas: list[ParadaSaida] = []
    pontos: list[tuple[float, float]] = []
    segundos_restantes: float | None = None
