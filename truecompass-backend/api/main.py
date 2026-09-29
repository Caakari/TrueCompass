# -*- coding: utf-8 -*-
"""Aplicacao FastAPI do TrueCompass."""

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from algoritmos.indice_espacial import indice_dos_nos
from api.conexoes import GerenciadorConexoes
from api.rotas import auth, corridas, motoristas, ws
from dominio.estados import validar_dag
from dominio.registro import RegistroMotoristas
from infra.banco import criar_tabelas
from infra.config import obter_config

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
registrador = logging.getLogger("truecompass")


def carregar_malha(config):
    """Le o artefato gerado offline. Se nao existir, cai na cidade sintetica.

    O servidor NUNCA consulta a Overpass no boot: seria lento, fragil e abuso
    de um servico publico. O artefato e gerado uma vez por
    `python3 -m infra.importar_malha` e versionado.
    """
    if os.path.exists(config.arquivo_malha):
        from infra.osm import carregar_grafo
        grafo = carregar_grafo(config.arquivo_malha)
        registrador.info("malha do OpenStreetMap: %s (%d nos, %d arestas)",
                         config.arquivo_malha, len(grafo.nos), grafo.total_arestas())
        return grafo

    from algoritmos.cidade_exemplo import construir_cidade
    registrador.warning(
        "%s nao encontrado: subindo com a CIDADE SINTETICA. "
        "Gere o artefato real com `python3 -m infra.importar_malha`.",
        config.arquivo_malha,
    )
    return construir_cidade(lado=40)


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    config = obter_config()

    # 1. O DAG do fluxo e validado por Kahn ANTES de qualquer requisicao.
    #    Havendo ciclo, o servidor nao sobe -- a prova da secao 5.2 da
    #    documentacao vira garantia de execucao.
    ordem = validar_dag()
    registrador.info("fluxo da corrida validado: %s", " -> ".join(ordem))

    # 2. A malha e o grafo reverso sao construidos UMA vez e ficam em memoria
    #    pelo tempo de vida do processo. Reconstruir por requisicao seria
    #    inviavel -- e e por isso que este backend precisa de processo
    #    persistente (Railway), e nao de funcoes serverless.
    app.state.grafo = carregar_malha(config)
    app.state.grafo.reverso()
    app.state.indice_nos = indice_dos_nos(app.state.grafo)
    registrador.info("grafo reverso e indice espacial prontos")

    app.state.registro = RegistroMotoristas()
    app.state.conexoes = GerenciadorConexoes()
    app.state.conexoes.registrar_loop(asyncio.get_running_loop())

    criar_tabelas()
    registrador.info("TrueCompass pronto (ambiente: %s)", config.ambiente)
    yield
    registrador.info("encerrando")


def criar_app():
    config = obter_config()
    app = FastAPI(
        title="TrueCompass API",
        description="Mobilidade urbana com roteamento por A* e pareamento "
                    "reverso many-to-one sobre malha do OpenStreetMap.",
        version="0.1.0",
        lifespan=ciclo_de_vida,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.origens_cors,      # o dominio do front no Vercel
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    for modulo in (auth, motoristas, corridas, ws):
        app.include_router(modulo.rotas)

    @app.get("/saude", tags=["infra"])
    def saude():
        """Health check do Railway."""
        return {
            "status": "ok",
            "nos_na_malha": len(app.state.grafo.nos),
            "motoristas_online": len(app.state.registro),
            "websockets_abertos": app.state.conexoes.total(),
        }

    return app


app = criar_app()
