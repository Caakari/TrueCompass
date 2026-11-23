# -*- coding: utf-8 -*-
"""Confere o token de acesso que o app recebeu do Google.

O app abre a janela do Google (Google Identity Services, fluxo de token) e
manda o `access_token` para ca. Antes de abrir sessao, perguntamos ao PROPRIO
Google:

1. tokeninfo: o token e valido e foi emitido para o NOSSO client id (`aud`).
   Sem esta checagem, um token emitido para outro site -- que o usuario usou
   la -- serviria para entrar aqui na conta dele (confused deputy).
2. userinfo: nome e e-mail, e se o Google confirmou o e-mail.
"""

import json
import urllib.error
import urllib.parse
import urllib.request

TOKENINFO = "https://oauth2.googleapis.com/tokeninfo"
USERINFO = "https://openidconnect.googleapis.com/v1/userinfo"


class TokenGoogleInvalido(Exception):
    pass


def _json(url, token=None):
    cabecalhos = {"Authorization": f"Bearer {token}"} if token else {}
    requisicao = urllib.request.Request(url, headers=cabecalhos)
    with urllib.request.urlopen(requisicao, timeout=8) as resposta:
        return json.loads(resposta.read().decode())


def verificar(token, client_id):
    """Devolve {"sub", "email", "nome"} ou levanta TokenGoogleInvalido."""
    try:
        info = _json(f"{TOKENINFO}?{urllib.parse.urlencode({'access_token': token})}")
        if client_id not in (info.get("aud"), info.get("azp")):
            raise TokenGoogleInvalido("token emitido para outro aplicativo")
        perfil = _json(USERINFO, token)
    except urllib.error.HTTPError as erro:
        raise TokenGoogleInvalido("token do Google invalido ou vencido") from erro
    except (urllib.error.URLError, TimeoutError, ValueError) as erro:
        raise TokenGoogleInvalido(f"Google indisponivel: {erro}") from erro
    if perfil.get("sub") != info.get("sub"):
        raise TokenGoogleInvalido("respostas do Google nao conferem")
    if not perfil.get("email") or not perfil.get("email_verified"):
        raise TokenGoogleInvalido("o Google nao confirmou este e-mail")
    return {"sub": perfil["sub"], "email": perfil["email"].lower(),
            "nome": perfil.get("name") or perfil["email"].split("@")[0]}
