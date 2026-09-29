# -*- coding: utf-8 -*-
"""Engine e sessao do banco."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from infra.config import obter_config
from infra.modelos import Base

_config = obter_config()

_argumentos = {"pool_pre_ping": True}
if _config.url_banco.startswith("sqlite"):
    # SQLite so aparece em teste e desenvolvimento.
    _argumentos = {"connect_args": {"check_same_thread": False}}

engine = create_engine(_config.url_banco, **_argumentos)
Sessao = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def criar_tabelas():
    """Suficiente para o escopo academico. Em evolucao real, use Alembic."""
    Base.metadata.create_all(engine)


def obter_sessao():
    """Dependencia do FastAPI: abre e fecha a sessao por requisicao."""
    sessao = Sessao()
    try:
        yield sessao
    finally:
        sessao.close()
