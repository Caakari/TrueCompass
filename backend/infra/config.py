# -*- coding: utf-8 -*-
"""Configuracao lida do ambiente. Nenhum segredo no codigo."""

import os
import re
from functools import lru_cache

from matematica_no_caminho import PASTA_BACKEND, PASTA_MATEMATICA


def _caminho(variavel, padrao):
    """Caminho de arquivo vindo do ambiente, resolvido a partir de backend/.

    Assim o servidor acha os dados de qualquer pasta de onde for iniciado
    (raiz do repositorio no Railway, ou backend/ no desenvolvimento).
    Valor vazio desliga a fonte (ex.: `MALHA_ARQUIVO=` para usar a matriz).
    """
    valor = os.getenv(variavel, padrao)
    if not valor or os.path.isabs(valor):
        return valor
    return os.path.join(PASTA_BACKEND, valor)


def _normalizar_url(url):
    """Railway entrega `mysql://...`; o SQLAlchemy exige o driver no esquema."""
    if url.startswith("mysql://"):
        return url.replace("mysql://", "mysql+pymysql://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    return url


def separar_origens(texto):
    """CORS_ORIGENS -> (origens exatas, expressao regular ou None).

    Aceita `*` como CURINGA dentro de uma origem, para as previas do Vercel,
    que ganham um endereco por branch e por commit:

        https://meu-app.vercel.app,https://meu-app-*-minha-equipe.vercel.app

    O `*` casa so letras minusculas, digitos e hifen -- nunca ponto nem barra.
    Assim ele nao atravessa para outro dominio: `*.vercel.app` NAO aceitaria
    `evil.com/x.vercel.app`, e `meu-app-*` nao aceita `meu-app-x.evil.com`.
    Origem com barra no fim e normalizada: o navegador nunca a envia assim.
    """
    exatas, padroes = [], []
    for origem in texto.split(","):
        origem = origem.strip().rstrip("/")
        if not origem:
            continue
        if "*" in origem:
            partes = (re.escape(p) for p in origem.split("*"))
            padroes.append("[a-z0-9-]+".join(partes))
        else:
            exatas.append(origem)
    padrao = f"^(?:{'|'.join(padroes)})$" if padroes else None
    return exatas, padrao


class Config:
    def __init__(self):
        self.url_banco = _normalizar_url(
            os.getenv("DATABASE_URL", "sqlite:///" + os.path.join(PASTA_BACKEND, "truecompass.db"))
        )
        self.segredo_jwt = os.getenv("JWT_SECRET", "")
        self.horas_token = int(os.getenv("JWT_HORAS", "12"))
        self.arquivo_malha = _caminho("MALHA_ARQUIVO", "dados/malha.json.gz")
        # Mapa em matriz: fonte preferencial, por ser editavel e versionavel.
        self.arquivo_matriz = _caminho("MAPA_MATRIZ", os.path.join(PASTA_MATEMATICA, "mapas", "centro.mapa"))
        self.considerar_semaforos = os.getenv("SEMAFOROS", "1") not in ("0", "false")
        # Marcos do ALT, gerados por `python3 -m infra.preparar_alt`.
        self.arquivo_alt = _caminho("ALT_ARQUIVO", "dados/alt.bin")
        self.origens_cors, self.padrao_cors = separar_origens(
            os.getenv("CORS_ORIGENS", "http://localhost:5173"))
        self.limite_matching_s = float(os.getenv("MATCHING_LIMITE_S", str(15 * 60)))
        self.raio_busca_m = float(os.getenv("MATCHING_RAIO_M", "3000"))
        self.max_candidatos = int(os.getenv("MATCHING_MAX_CANDIDATOS", "20"))
        # Tempo que o motorista tem para aceitar uma oferta de corrida.
        self.prazo_oferta_s = float(os.getenv("OFERTA_PRAZO_S", "20"))
        self.ambiente = os.getenv("AMBIENTE", "desenvolvimento")

    @property
    def producao(self):
        return self.ambiente == "producao"

    def validar(self):
        """Falha no boot, nao na primeira requisicao."""
        if not self.segredo_jwt:
            if self.producao:
                raise RuntimeError(
                    "JWT_SECRET obrigatorio em producao. Defina a variavel no Railway."
                )
            self.segredo_jwt = "segredo-inseguro-apenas-para-desenvolvimento"
        if self.producao and "sqlite" in self.url_banco:
            raise RuntimeError("SQLite nao serve em producao: configure DATABASE_URL")
        return self


@lru_cache(maxsize=1)
def obter_config():
    return Config().validar()
