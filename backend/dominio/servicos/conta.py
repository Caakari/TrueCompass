# -*- coding: utf-8 -*-
"""Regras da conta: forca da senha, codigos por e-mail e sessoes renovaveis.

Sem HTTP. O envio do e-mail e o Google ficam em `infra/`; aqui so a regra.
"""

import hashlib
import hmac
import secrets
from datetime import timedelta

from dominio.servicos.corrida import agora_utc
from infra.modelos import CodigoVerificacao, SessaoRenovacao

# ------------------------------------------------------------ forca da senha

# As mais usadas no Brasil (listas publicas de vazamentos). O app confere a
# MESMA lista antes de enviar; aqui e a regra que vale.
SENHAS_COMUNS = frozenset({
    "12345678", "123456789", "1234567890", "senha123", "senha1234", "password", "password1",
    "qwerty123", "abc12345", "abcd1234", "11111111", "00000000", "87654321", "brasil123",
    "iloveyou", "admin123", "mudar123", "trocar123", "flamengo", "corinthians", "palmeiras",
    "saopaulo", "santos123", "gabriel1",
})


def problemas_da_senha(senha, email=""):
    """Lista do que falta na senha (vazia = aceita). Mesmas regras do app:
    8+ caracteres, letras E numeros, nao ser obvia nem conter o e-mail."""
    problemas = []
    if len(senha) < 8:
        problemas.append("pelo menos 8 caracteres")
    if not (any(c.isalpha() for c in senha) and any(c.isdigit() for c in senha)):
        problemas.append("letras e numeros")
    minuscula = senha.lower()
    usuario = (email or "").split("@")[0].lower()
    if (minuscula in SENHAS_COMUNS or len(set(senha)) == 1
            or (len(usuario) >= 4 and usuario in minuscula)):
        problemas.append("nao ser obvia nem conter o seu e-mail")
    return problemas


# ------------------------------------------------------------------- codigos

DIGITOS = 6
VALIDADE_CODIGO = timedelta(minutes=15)
TENTATIVAS_POR_CODIGO = 5


class CodigoInvalido(Exception):
    """Errado, vencido, ja usado ou esgotado -- a pessoa ve a mesma coisa."""


def _hash_codigo(segredo, usuario_id, finalidade, codigo):
    # HMAC com o segredo do servidor: 10^6 codigos possiveis se quebrariam
    # por forca bruta num SHA puro; sem o segredo, o hash nao serve de nada.
    mensagem = f"{usuario_id}:{finalidade}:{codigo}".encode()
    return hmac.new(segredo.encode(), mensagem, hashlib.sha256).hexdigest()


def gerar_codigo(sessao, usuario, finalidade, segredo):
    """Cria um codigo novo e INVALIDA os anteriores da mesma finalidade (so o
    ultimo e-mail vale). Devolve o codigo em texto, para mandar por e-mail."""
    agora = agora_utc()
    (sessao.query(CodigoVerificacao)
     .filter_by(usuario_id=usuario.id, finalidade=finalidade, usado_em=None)
     .update({"usado_em": agora}))
    codigo = f"{secrets.randbelow(10 ** DIGITOS):0{DIGITOS}d}"
    sessao.add(CodigoVerificacao(usuario_id=usuario.id, finalidade=finalidade,
                                 codigo_hash=_hash_codigo(segredo, usuario.id, finalidade, codigo),
                                 criado_em=agora, expira_em=agora + VALIDADE_CODIGO))
    return codigo


def usar_codigo(sessao, usuario, finalidade, codigo, segredo):
    """Confere e CONSOME o codigo. Cada erro gasta uma tentativa; na quinta o
    codigo morre e e preciso pedir outro. Levanta CodigoInvalido."""
    agora = agora_utc()
    atual = (sessao.query(CodigoVerificacao)
             .filter_by(usuario_id=usuario.id, finalidade=finalidade, usado_em=None)
             .order_by(CodigoVerificacao.id.desc()).first())
    if atual is None or atual.expira_em <= agora or atual.tentativas >= TENTATIVAS_POR_CODIGO:
        raise CodigoInvalido("codigo invalido ou expirado; peca um novo")
    esperado = _hash_codigo(segredo, usuario.id, finalidade, (codigo or "").strip())
    if not hmac.compare_digest(esperado, atual.codigo_hash):
        atual.tentativas += 1
        if atual.tentativas >= TENTATIVAS_POR_CODIGO:
            atual.usado_em = agora
        sessao.commit()          # a tentativa gasta vale mesmo com o 400 a seguir
        raise CodigoInvalido("codigo incorreto")
    atual.usado_em = agora


# ------------------------------------------------- sessoes de renovacao

class RenovacaoInvalida(Exception):
    pass


def _hash_token(token):
    return hashlib.sha256(token.encode()).hexdigest()


def abrir_renovacao(sessao, usuario, dias):
    token = secrets.token_urlsafe(32)
    agora = agora_utc()
    sessao.add(SessaoRenovacao(usuario_id=usuario.id, token_hash=_hash_token(token),
                               criada_em=agora, expira_em=agora + timedelta(days=dias)))
    return token


def revogar_todas(sessao, usuario_id):
    (sessao.query(SessaoRenovacao)
     .filter_by(usuario_id=usuario_id, revogada_em=None)
     .update({"revogada_em": agora_utc()}))


def renovar(sessao, token, dias):
    """Troca o token de renovacao por um NOVO (rotacao) e devolve
    (usuario_id, token_novo). Token ja trocado usado de novo = vazou: derruba
    todas as sessoes da conta antes de recusar."""
    registro = (sessao.query(SessaoRenovacao)
                .filter_by(token_hash=_hash_token(token or "")).one_or_none())
    if registro is None:
        raise RenovacaoInvalida("sessao desconhecida")
    agora = agora_utc()
    if registro.revogada_em is not None:
        revogar_todas(sessao, registro.usuario_id)
        sessao.commit()
        raise RenovacaoInvalida("sessao encerrada; entre de novo")
    if registro.expira_em <= agora:
        raise RenovacaoInvalida("sessao vencida; entre de novo")
    registro.revogada_em = agora
    novo = secrets.token_urlsafe(32)
    sessao.add(SessaoRenovacao(usuario_id=registro.usuario_id, token_hash=_hash_token(novo),
                               criada_em=agora, expira_em=agora + timedelta(days=dias)))
    return registro.usuario_id, novo


def revogar(sessao, token):
    (sessao.query(SessaoRenovacao)
     .filter_by(token_hash=_hash_token(token or ""), revogada_em=None)
     .update({"revogada_em": agora_utc()}))
