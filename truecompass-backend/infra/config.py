# -*- coding: utf-8 -*-
"""Configuracao lida do ambiente. Nenhum segredo no codigo."""

import os
from functools import lru_cache


def _normalizar_url(url):
    """Railway entrega `mysql://...`; o SQLAlchemy exige o driver no esquema."""
    if url.startswith("mysql://"):
        return url.replace("mysql://", "mysql+pymysql://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    return url


class Config:
    def __init__(self):
        self.url_banco = _normalizar_url(
            os.getenv("DATABASE_URL", "sqlite:///./truecompass.db")
        )
        self.segredo_jwt = os.getenv("JWT_SECRET", "")
        self.horas_token = int(os.getenv("JWT_HORAS", "12"))
        self.arquivo_malha = os.getenv("MALHA_ARQUIVO", "dados/malha.json")
        self.origens_cors = [
            o.strip() for o in os.getenv("CORS_ORIGENS", "http://localhost:5173").split(",")
            if o.strip()
        ]
        self.limite_matching_s = float(os.getenv("MATCHING_LIMITE_S", str(15 * 60)))
        self.raio_busca_m = float(os.getenv("MATCHING_RAIO_M", "3000"))
        self.max_candidatos = int(os.getenv("MATCHING_MAX_CANDIDATOS", "20"))
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
