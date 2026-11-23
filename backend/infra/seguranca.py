# -*- coding: utf-8 -*-
"""Hash de senha (bcrypt) e token de acesso (JWT HS256)."""

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from infra.config import obter_config

ALGORITMO = "HS256"


def cifrar_senha(senha):
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def conferir_senha(senha, senha_hash):
    try:
        return bcrypt.checkpw(senha.encode("utf-8"), senha_hash.encode("utf-8"))
    except ValueError:
        return False    # hash corrompido no banco: nega, nao explode


def emitir_token(usuario_id, tipo):
    config = obter_config()
    agora = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(usuario_id),
            "tipo": tipo,
            "iat": agora,
            "exp": agora + timedelta(hours=config.horas_token),
        },
        config.segredo_jwt,
        algorithm=ALGORITMO,
    )


def ler_token(token):
    """Devolve o conteudo do token, ou None se invalido/expirado."""
    try:
        return jwt.decode(token, obter_config().segredo_jwt, algorithms=[ALGORITMO])
    except jwt.PyJWTError:
        return None
