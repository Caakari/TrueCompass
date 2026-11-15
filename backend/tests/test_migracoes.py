# -*- coding: utf-8 -*-
"""Testes da migracao aditiva (infra.migracoes).

O cenario e o do MySQL de producao: tabelas criadas por uma versao anterior
do modelo, ja com linhas, e um modelo novo com colunas a mais.

    python3 backend/tests/test_migracoes.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import matematica_no_caminho  # noqa: E402,F401

from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, inspect, text  # noqa: E402

from infra.migracoes import colunas_ausentes, migrar  # noqa: E402
from infra.modelos import Base  # noqa: E402

# Esquema da primeira versao publicada, como esta no banco do Railway.
ESQUEMA_ANTIGO = """
CREATE TABLE usuarios (id INTEGER PRIMARY KEY, nome VARCHAR(120), email VARCHAR(180) UNIQUE,
    senha_hash VARCHAR(128), tipo VARCHAR(20), criado_em DATETIME);
CREATE TABLE motoristas (id INTEGER PRIMARY KEY, usuario_id INTEGER UNIQUE REFERENCES usuarios(id),
    placa VARCHAR(10), modelo VARCHAR(60), disponivel BOOLEAN, no_atual BIGINT, lat FLOAT, lon FLOAT,
    atualizado_em DATETIME);
CREATE TABLE corridas (id INTEGER PRIMARY KEY, passageiro_id INTEGER REFERENCES usuarios(id),
    motorista_id INTEGER REFERENCES motoristas(id), no_origem BIGINT, no_destino BIGINT,
    estado VARCHAR(20), eta_segundos FLOAT, custo_estimado FLOAT, criada_em DATETIME,
    atualizada_em DATETIME);
"""


def banco_antigo():
    caminho = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
    engine = create_engine(f"sqlite:///{caminho}")
    with engine.begin() as conexao:
        for comando in ESQUEMA_ANTIGO.strip().split(";"):
            if comando.strip():
                conexao.execute(text(comando))
        conexao.execute(text("INSERT INTO usuarios (id, nome, email, senha_hash, tipo) "
                             "VALUES (1, 'Ana', 'ana@usjt.br', 'x', 'passageiro')"))
        conexao.execute(text("INSERT INTO corridas (id, passageiro_id, no_origem, no_destino, "
                             "estado, custo_estimado) VALUES (7, 1, 10, 20, 'paga', 31.5)"))
    return engine, caminho


def test_acrescenta_as_colunas_novas_e_preserva_as_linhas():
    engine, caminho = banco_antigo()
    try:
        Base.metadata.create_all(engine)
        feitas = migrar(engine, Base.metadata)
        assert "usuarios.telefone" in feitas and "corridas.categoria" in feitas
        assert "motoristas.cor_carro" in feitas
        colunas = {c["name"] for c in inspect(engine).get_columns("corridas")}
        assert {"categoria", "forma_pagamento", "origem_texto", "destino_texto"} <= colunas
        with engine.connect() as conexao:
            linha = conexao.execute(text("SELECT estado, custo_estimado, categoria "
                                         "FROM corridas WHERE id = 7")).one()
        assert tuple(linha) == ("paga", 31.5, None), "a linha antiga tem de sobreviver"
    finally:
        engine.dispose()
        os.unlink(caminho)


def test_tabelas_novas_sao_criadas_pelo_create_all():
    engine, caminho = banco_antigo()
    try:
        Base.metadata.create_all(engine)
        migrar(engine, Base.metadata)
        tabelas = set(inspect(engine).get_table_names())
        assert {"locais_salvos", "avaliacoes", "corrida_paradas", "mensagens"} <= tabelas
    finally:
        engine.dispose()
        os.unlink(caminho)


def test_indice_unico_da_coluna_nova_e_criado():
    """token_compartilhar precisa do indice UNICO (busca do link publico)."""
    engine, caminho = banco_antigo()
    try:
        Base.metadata.create_all(engine)
        migrar(engine, Base.metadata)
        indices = {i["name"]: i for i in inspect(engine).get_indexes("corridas")}
        assert "ix_corridas_token_compartilhar" in indices
        assert indices["ix_corridas_token_compartilhar"]["unique"]
    finally:
        engine.dispose()
        os.unlink(caminho)


def test_e_idempotente():
    engine, caminho = banco_antigo()
    try:
        Base.metadata.create_all(engine)
        assert migrar(engine, Base.metadata)
        assert migrar(engine, Base.metadata) == [], "a segunda passada nao tem o que fazer"
        assert colunas_ausentes(engine, Base.metadata) == []
    finally:
        engine.dispose()
        os.unlink(caminho)


def test_banco_novo_nao_precisa_de_migracao():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    assert migrar(engine, Base.metadata) == []


def test_recusa_coluna_not_null_sem_default_antes_de_alterar_qualquer_coisa():
    engine = create_engine("sqlite://")
    with engine.begin() as conexao:
        conexao.execute(text("CREATE TABLE coisas (id INTEGER PRIMARY KEY)"))
    modelo = MetaData()
    Table("coisas", modelo, Column("id", Integer, primary_key=True),
          Column("boa", String(10), nullable=True),
          Column("ruim", String(10), nullable=False))
    try:
        migrar(engine, modelo)
    except RuntimeError as erro:
        assert "coisas.ruim" in str(erro)
    else:
        raise AssertionError("NOT NULL sem default deveria ser recusada")
    colunas = {c["name"] for c in inspect(engine).get_columns("coisas")}
    assert colunas == {"id"}, "nada pode ter sido alterado antes da recusa"


def main():
    testes = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    falhas = 0
    for teste in testes:
        try:
            teste()
            print(f"  ok    {teste.__name__}")
        except AssertionError as erro:
            falhas += 1
            print(f"  FALHA {teste.__name__}: {str(erro)[:160]}")
    print(f"\n{len(testes) - falhas}/{len(testes)} testes passaram")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
