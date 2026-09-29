# -*- coding: utf-8 -*-
"""Tabelas do banco (SQLAlchemy 2.0)."""

from datetime import datetime, timezone

from sqlalchemy import (BigInteger, Boolean, DateTime, Float, ForeignKey,
                        Integer, String, UniqueConstraint)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from dominio.estados import ESTADO_INICIAL


def agora():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    senha_hash: Mapped[str] = mapped_column(String(128))
    tipo: Mapped[str] = mapped_column(String(20))          # passageiro | motorista
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=agora)

    motorista: Mapped["Motorista"] = relationship(back_populates="usuario",
                                                  uselist=False)


class Motorista(Base):
    __tablename__ = "motoristas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), unique=True)
    placa: Mapped[str] = mapped_column(String(10))
    modelo: Mapped[str] = mapped_column(String(60), default="")
    disponivel: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    # Id de no do OpenStreetMap: passa de 2^31, exige BigInteger.
    no_atual: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime, default=agora,
                                                    onupdate=agora)

    usuario: Mapped[Usuario] = relationship(back_populates="motorista")


class Corrida(Base):
    __tablename__ = "corridas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    passageiro_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    motorista_id: Mapped[int | None] = mapped_column(ForeignKey("motoristas.id"),
                                                     nullable=True, index=True)
    no_origem: Mapped[int] = mapped_column(BigInteger)
    no_destino: Mapped[int] = mapped_column(BigInteger)
    estado: Mapped[str] = mapped_column(String(20), default=ESTADO_INICIAL, index=True)
    eta_segundos: Mapped[float | None] = mapped_column(Float, nullable=True)
    custo_estimado: Mapped[float | None] = mapped_column(Float, nullable=True)
    criada_em: Mapped[datetime] = mapped_column(DateTime, default=agora)
    atualizada_em: Mapped[datetime] = mapped_column(DateTime, default=agora,
                                                    onupdate=agora)


class CorridaTransicao(Base):
    """Log de auditoria: a evidencia de que a ordem topologica foi respeitada.

    Cada linha e uma aresta percorrida no DAG. Com esta tabela da para provar,
    com dados reais, que nenhuma corrida foi paga sem ter sido concluida --
    material direto para o relatorio da 2a parcial.
    """

    __tablename__ = "corrida_transicoes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    corrida_id: Mapped[int] = mapped_column(ForeignKey("corridas.id"), index=True)
    de_estado: Mapped[str] = mapped_column(String(20))
    para_estado: Mapped[str] = mapped_column(String(20))
    em: Mapped[datetime] = mapped_column(DateTime, default=agora)


class Pagamento(Base):
    __tablename__ = "pagamentos"
    __table_args__ = (UniqueConstraint("corrida_id", name="uq_pagamento_corrida"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    corrida_id: Mapped[int] = mapped_column(ForeignKey("corridas.id"))
    valor: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20), default="processado")
    processado_em: Mapped[datetime] = mapped_column(DateTime, default=agora)
