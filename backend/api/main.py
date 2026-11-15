# -*- coding: utf-8 -*-
"""Aplicacao FastAPI do TrueCompass."""

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from algoritmos.contracao import Geometria
from algoritmos.indice_espacial import indice_dos_nos
from api.conexoes import GerenciadorConexoes
from api.rotas import auth, corridas, lugares, malha, motoristas, publico, usuarios, viagens, ws
from api.rotas.malha import resumo_da_malha
from dominio.estados import validar_dag
from dominio.registro import RegistroMotoristas
from infra.banco import criar_tabelas
from infra.config import obter_config

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
registrador = logging.getLogger("truecompass")


def carregar_malha(config):
    """Decide a fonte do mapa, nesta ordem de preferencia.

    1. Artefato do OpenStreetMap (`dados/malha.json.gz`), gerado offline pelo
       CLI -- ruas REAIS de Sao Paulo, com mao unica e semaforos do OSM. E o
       que permite buscar um endereco de verdade e rotear ate ele.
    2. MATRIZ (`mapas/*.mapa`) -- editavel a mao, boa para experimentos
       didaticos. Para usa-la com o artefato presente: `MALHA_ARQUIVO=`.
    3. Cidade sintetica, apenas para nao travar o desenvolvimento.

    O servidor NUNCA consulta a Overpass no boot: seria lento, fragil e abuso
    de um servico publico.

    Devolve (grafo, matriz_ou_None, semaforos, geometria). Os semaforos vao a
    parte porque o grafo nao os carrega -- o atraso ja foi absorvido pelos
    pesos das arestas; a lista serve para o front desenhar. A geometria e a
    forma das ruas contraidas (vazia na matriz e na cidade sintetica, onde
    toda aresta ja e reta).
    """
    if config.arquivo_malha and os.path.exists(config.arquivo_malha):
        from infra.osm import ler_artefato
        grafo, semaforos, geometria = ler_artefato(config.arquivo_malha)
        registrador.info("malha do OpenStreetMap: %s (%d nos, %d arestas, %d semaforos, "
                         "%d arestas com tracado)",
                         config.arquivo_malha, len(grafo.nos), grafo.total_arestas(),
                         len(semaforos), len(geometria))
        return grafo, None, semaforos, geometria

    if config.arquivo_matriz and os.path.exists(config.arquivo_matriz):
        from algoritmos.matriz_mapa import MatrizMapa
        with open(config.arquivo_matriz, encoding="utf-8") as arquivo:
            matriz = MatrizMapa.de_texto(arquivo.read())
        grafo = matriz.para_grafo(considerar_semaforos=config.considerar_semaforos)
        dados = matriz.estatisticas()
        registrador.info(
            "mapa em matriz: %s (%dx%d, %d nos, %d arestas, %d semaforos%s)",
            config.arquivo_matriz, dados["altura"], dados["largura"],
            len(grafo.nos), grafo.total_arestas(), dados["semaforos"],
            "" if config.considerar_semaforos else " IGNORADOS",
        )
        return grafo, matriz, semaforos_da_matriz(matriz), Geometria()

    from algoritmos.cidade_exemplo import construir_cidade
    registrador.warning(
        "nem %s nem %s encontrados: subindo com a CIDADE SINTETICA.",
        config.arquivo_malha, config.arquivo_matriz,
    )
    return construir_cidade(lado=40), None, [], Geometria()


def semaforos_da_matriz(matriz):
    """Cruzamentos semaforizados da matriz, no formato de /malha/semaforos."""
    saida = []
    for i in range(matriz.altura):
        for j in range(matriz.largura):
            sinal = matriz.semaforo_de(i, j)
            if sinal is None:
                continue
            lat, lon = matriz.coordenadas(i, j)
            saida.append({
                "lat": round(lat, 6), "lon": round(lon, 6),
                "vermelho": sinal.vermelho, "ciclo": sinal.ciclo,
                "atraso_medio": round(sinal.atraso, 2),
            })
    return saida


def caixa_da_malha(grafo):
    """Retangulo envolvente da malha: limita a busca de lugares a area em que
    o A* tem rua para chegar."""
    latitudes = [grafo.coordenadas(no)[0] for no in grafo.nos]
    longitudes = [grafo.coordenadas(no)[1] for no in grafo.nos]
    if not latitudes:
        return None
    return {"sul": min(latitudes), "oeste": min(longitudes),
            "norte": max(latitudes), "leste": max(longitudes)}


def carregar_alt(config, grafo):
    """Marcos do ALT, se houver artefato COMPATIVEL com esta malha.

    A impressao digital e conferida de proposito: um artefato gerado para
    outro mapa daria limites de um grafo diferente, e o A* devolveria rota
    subotima sem erro algum. Preferimos cair na haversine, que e correta.
    """
    if not os.path.exists(config.arquivo_alt):
        registrador.info("sem %s: A* usara a heuristica haversine. "
                         "Gere com `python3 -m infra.preparar_alt`.",
                         config.arquivo_alt)
        return None
    try:
        from algoritmos.alt import ALT
        alt = ALT.carregar(config.arquivo_alt)
    except (ValueError, OSError, EOFError) as erro:
        registrador.warning("nao foi possivel ler %s (%s): usando haversine",
                            config.arquivo_alt, erro)
        return None

    if not alt.confere(grafo):
        registrador.warning(
            "%s foi gerado para OUTRA malha: ignorado. Regere com "
            "`python3 -m infra.preparar_alt`.", config.arquivo_alt)
        return None

    registrador.info("ALT: %d marcos, %d ativos por consulta", len(alt), alt.ativos)
    return alt


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
    (app.state.grafo, app.state.matriz, app.state.semaforos,
     app.state.geometria) = carregar_malha(config)
    app.state.grafo.reverso()
    app.state.indice_nos = indice_dos_nos(app.state.grafo)
    app.state.caixa = caixa_da_malha(app.state.grafo)
    app.state.resumo_malha = resumo_da_malha(app.state.grafo)
    # Cruzamentos semaforizados, para contar os sinais de cada rota.
    app.state.nos_semaforizados = frozenset(
        app.state.indice_nos.mais_proximo(s["lat"], s["lon"])
        for s in app.state.semaforos
    )
    registrador.info("grafo reverso e indice espacial prontos "
                     "(velocidade maxima medida: %.0f km/h)",
                     app.state.grafo.velocidade_maxima_kmh())

    # Marcos do ALT: heuristica muito mais apertada que a haversine. Opcional --
    # sem o artefato, o A* segue correto, so explorando mais.
    app.state.alt = carregar_alt(config, app.state.grafo)

    app.state.registro = RegistroMotoristas()
    app.state.conexoes = GerenciadorConexoes()
    app.state.conexoes.registrar_loop(asyncio.get_running_loop())

    criar_tabelas()
    vigia = asyncio.create_task(vigiar_ofertas(app, config))
    registrador.info("TrueCompass pronto (ambiente: %s)", config.ambiente)
    yield
    vigia.cancel()
    registrador.info("encerrando")


INTERVALO_VIGIA_S = 2.0


def expirar_ofertas_agora(app, config):
    """Uma passada: expira ofertas vencidas e publica DEPOIS do commit."""
    from api.eventos import mensagem_estado
    from dominio.servicos import corrida as servico
    from infra.banco import Sessao

    sessao = Sessao()
    try:
        mudaram = servico.expirar_ofertas(sessao, app.state.grafo, app.state.registro, config)
        sessao.commit()
        for corrida in mudaram:
            app.state.conexoes.publicar(corrida.id, mensagem_estado(corrida))
        return mudaram
    except Exception:
        sessao.rollback()
        registrador.exception("falha ao expirar ofertas")
        return []
    finally:
        sessao.close()


async def vigiar_ofertas(app, config):
    """Laco do processo: a cada 2 s, passa adiante as ofertas sem resposta.

    O trabalho (consulta, busca reversa para o proximo motorista) roda numa
    thread, para nao segurar o event loop -- a mesma regra dos endpoints que
    tocam o grafo serem `def`.
    """
    while True:
        await asyncio.sleep(INTERVALO_VIGIA_S)
        await asyncio.to_thread(expirar_ofertas_agora, app, config)


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
        allow_origin_regex=config.padrao_cors,  # e as previas dele (`*` no CORS_ORIGENS)
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    for modulo in (auth, usuarios, motoristas, corridas, malha, lugares, viagens, publico, ws):
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
