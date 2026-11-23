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
    """Tabelas novas (create_all) e colunas novas em tabelas existentes.

    A segunda parte e a migracao aditiva de `infra.migracoes`: sem ela, cada
    coluna nova no modelo quebraria o MySQL de producao, que ja tem as tabelas.
    Para remover ou alterar coluna, use Alembic.
    """
    from infra.migracoes import migrar
    Base.metadata.create_all(engine)
    return migrar(engine, Base.metadata)


def obter_sessao():
    """Dependencia do FastAPI: abre e fecha a sessao por requisicao."""
    sessao = Sessao()
    try:
        yield sessao
    finally:
        sessao.close()
