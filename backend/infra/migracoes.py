# -*- coding: utf-8 -*-
"""Migracao ADITIVA no boot: acrescenta as colunas que faltam.

POR QUE EXISTE: `Base.metadata.create_all` cria tabelas que nao existem, mas
NAO toca as que ja existem. O MySQL de producao (Railway) ja tem `usuarios`,
`corridas` etc.; sem isto, cada coluna nova no modelo quebraria o servidor no
primeiro SELECT ("Unknown column"), e a correcao exigiria entrar no banco a mao.

O QUE FAZ, E SO ISSO: compara cada tabela do modelo com a do banco e roda
`ALTER TABLE ... ADD COLUMN` para cada coluna ausente, criando tambem os
indices dela. Nunca remove, renomeia nem altera coluna -- isso exige decisao
humana (e dados), e e o territorio do Alembic.

REGRA: coluna nova em tabela existente precisa aceitar NULL (ou ter default
no servidor). As linhas antigas nao tem valor para ela; um NOT NULL sem
default faria o ALTER falhar no meio do boot. Isso e conferido ANTES de
qualquer ALTER, e o servidor nao sobe com um modelo que viole a regra.

Idempotente: rodar duas vezes nao faz nada na segunda.
"""

import logging

from sqlalchemy import inspect, text
from sqlalchemy.schema import CreateColumn

registrador = logging.getLogger("truecompass.migracoes")


def colunas_ausentes(engine, metadata):
    """[(tabela, coluna)] do modelo que o banco ainda nao tem.

    Tabelas inteiras ausentes nao entram: essas o `create_all` cria completas.
    """
    inspetor = inspect(engine)
    existentes = set(inspetor.get_table_names())
    faltando = []
    for tabela in metadata.sorted_tables:
        if tabela.name not in existentes:
            continue
        no_banco = {c["name"] for c in inspetor.get_columns(tabela.name)}
        faltando.extend((tabela, coluna) for coluna in tabela.columns
                        if coluna.name not in no_banco)
    return faltando


def migrar(engine, metadata):
    """Acrescenta as colunas ausentes. Devolve os nomes 'tabela.coluna'."""
    faltando = colunas_ausentes(engine, metadata)
    for tabela, coluna in faltando:
        if not coluna.nullable and coluna.server_default is None:
            raise RuntimeError(
                f"{tabela.name}.{coluna.name} e NOT NULL sem server_default: nao da "
                "para acrescenta-la a uma tabela com linhas. Torne-a nullable.")

    feitas = []
    with engine.begin() as conexao:
        for tabela, coluna in faltando:
            ddl = CreateColumn(coluna).compile(dialect=engine.dialect)
            conexao.execute(text(f"ALTER TABLE {tabela.name} ADD COLUMN {ddl}"))
            feitas.append(f"{tabela.name}.{coluna.name}")
        for tabela, coluna in faltando:
            for indice in tabela.indexes:
                if coluna in indice.columns.values():
                    indice.create(conexao, checkfirst=True)

    for nome in feitas:
        registrador.info("migracao: coluna %s acrescentada", nome)
    return feitas
