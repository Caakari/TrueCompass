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
    # Perfil. Toda coluna acrescentada depois da primeira versao e NULLABLE:
    # a migracao aditiva (infra.migracoes) precisa disso nas linhas antigas.
    telefone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    cor_avatar: Mapped[str | None] = mapped_column(String(7), nullable=True)   # "#2F8A4C"

    motorista: Mapped["Motorista"] = relationship(back_populates="usuario",
                                                  uselist=False)


class Motorista(Base):
    __tablename__ = "motoristas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), unique=True)
    placa: Mapped[str] = mapped_column(String(10))
    modelo: Mapped[str] = mapped_column(String(60), default="")
    disponivel: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    cor_carro: Mapped[str | None] = mapped_column(String(30), nullable=True)

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
    # Para o historico: o que o passageiro escolheu e os enderecos como ele os
    # viu (o grafo so guarda o no; refazer a geocodificacao a cada listagem
    # seria lento e abusaria do Photon/Nominatim).
    categoria: Mapped[str | None] = mapped_column(String(12), nullable=True)
    forma_pagamento: Mapped[str | None] = mapped_column(String(12), nullable=True)
    origem_texto: Mapped[str | None] = mapped_column(String(200), nullable=True)
    destino_texto: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # Link publico de acompanhamento (None = nao compartilhada). Aleatorio,
    # nao derivado do id: quem tem o link de uma corrida nao adivinha outra.
    token_compartilhar: Mapped[str | None] = mapped_column(String(40), nullable=True,
                                                           unique=True, index=True)
    # Por que foi cancelada, quando nao foi o passageiro (ex.: ninguem aceitou).
    motivo_cancelamento: Mapped[str | None] = mapped_column(String(80), nullable=True)
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


class LocalSalvo(Base):
    """Atalho de destino: Casa, Trabalho ou um favorito com nome livre.

    Casa e Trabalho sao unicos por usuario (definir de novo substitui); os
    favoritos ('outro') podem ser varios.
    """

    __tablename__ = "locais_salvos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    tipo: Mapped[str] = mapped_column(String(10))           # casa | trabalho | outro
    rotulo: Mapped[str] = mapped_column(String(40))
    titulo: Mapped[str] = mapped_column(String(160))
    detalhe: Mapped[str] = mapped_column(String(200), default="")
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=agora)


class Avaliacao(Base):
    """Nota de 1 a 5 que um lado da corrida da ao outro.

    Uma por autor por corrida (restricao no banco, nao so no codigo: dois
    toques rapidos em "Enviar" nao podem virar duas notas).
    """

    __tablename__ = "avaliacoes"
    __table_args__ = (UniqueConstraint("corrida_id", "autor_id", name="uq_avaliacao_autor"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    corrida_id: Mapped[int] = mapped_column(ForeignKey("corridas.id"), index=True)
    autor_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    avaliado_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    nota: Mapped[int] = mapped_column(Integer)
    comentario: Mapped[str | None] = mapped_column(String(280), nullable=True)
    criada_em: Mapped[datetime] = mapped_column(DateTime, default=agora)


class CorridaParada(Base):
    """Parada no caminho, na ordem em que o passageiro a quer.

    Tabela propria (e nao colunas em `corridas`) porque sao de 0 a N. O no
    ancorado fica gravado: a rota da corrida e recalculada a partir dele.
    """

    __tablename__ = "corrida_paradas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    corrida_id: Mapped[int] = mapped_column(ForeignKey("corridas.id"), index=True)
    ordem: Mapped[int] = mapped_column(Integer)
    no: Mapped[int] = mapped_column(BigInteger)
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    texto: Mapped[str | None] = mapped_column(String(200), nullable=True)


class Mensagem(Base):
    """Mensagem do chat da corrida, entre passageiro e motorista."""

    __tablename__ = "mensagens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    corrida_id: Mapped[int] = mapped_column(ForeignKey("corridas.id"), index=True)
    autor_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    texto: Mapped[str] = mapped_column(String(500))
    criada_em: Mapped[datetime] = mapped_column(DateTime, default=agora)


class Oferta(Base):
    """Oferta de uma corrida a UM motorista, com prazo para aceitar.

    Enquanto a corrida esta em `alocacao`, ela e oferecida a um motorista por
    vez, do menor ETA para o maior. Recusar ou deixar expirar passa a oferta
    ao proximo SEM mudar o estado da corrida: um laco alocacao -> alocacao
    seria um ciclo, e o DAG validado por Kahn nao admite ciclo. Esta tabela e
    a auditoria das tentativas.

    status: pendente -> aceita | recusada | expirada | cancelada. A troca e
    sempre `UPDATE ... WHERE status = 'pendente'` com checagem de rowcount:
    se o motorista aceita no mesmo instante em que a oferta expira, so um
    dos dois vence.
    """

    __tablename__ = "ofertas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    corrida_id: Mapped[int] = mapped_column(ForeignKey("corridas.id"), index=True)
    motorista_id: Mapped[int] = mapped_column(ForeignKey("motoristas.id"), index=True)
    status: Mapped[str] = mapped_column(String(12), default="pendente", index=True)
    eta_segundos: Mapped[float | None] = mapped_column(Float, nullable=True)
    criada_em: Mapped[datetime] = mapped_column(DateTime, default=agora)
    expira_em: Mapped[datetime] = mapped_column(DateTime)
    respondida_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
