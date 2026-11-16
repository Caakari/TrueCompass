# -*- coding: utf-8 -*-
"""Envio do codigo de verificacao por e-mail.

Modos (EMAIL_MODO, ou escolhido sozinho pelo que estiver configurado):

- resend  -- API HTTP da Resend (RESEND_API_KEY). Gratis ate 100/dia. Sem
             dominio proprio verificado, so envia para o e-mail do dono da
             conta Resend; com dominio, para qualquer um.
- smtp    -- servidor SMTP (SMTP_HOST, SMTP_PORTA, SMTP_USUARIO, SMTP_SENHA),
             ex.: Gmail com "senha de app".
- log     -- nao envia: escreve o codigo no log do servidor (desenvolvimento).
- memoria -- guarda em `ENVIADOS` (testes).

Chamado em segundo plano (BackgroundTasks): a resposta da API nao espera o
e-mail sair, e o tempo de resposta nao revela se o e-mail existe.
"""

import json
import logging
import smtplib
import ssl
import urllib.request
from email.message import EmailMessage

from infra.config import obter_config

registrador = logging.getLogger("truecompass.email")
ENVIADOS = []           # modo "memoria"

_ASSUNTO = {
    "confirmar": "Seu código do TrueCompass: {codigo}",
    "recuperar": "Código para criar uma senha nova: {codigo}",
}
_FRASE = {
    "confirmar": "Use este código para confirmar seu e-mail e abrir sua conta:",
    "recuperar": "Recebemos um pedido para criar uma senha nova. Use este código:",
}


def _mascarar(email):
    nome, _, dominio = email.partition("@")
    return f"{nome[:1]}***@{dominio}"


def montar(destino, nome, codigo, finalidade):
    primeiro = (nome or "").split(" ")[0] or "Olá"
    assunto = _ASSUNTO[finalidade].format(codigo=codigo)
    texto = (f"{primeiro},\n\n{_FRASE[finalidade]}\n\n    {codigo}\n\n"
             "Ele vale por 15 minutos. Se não foi você, ignore este e-mail: "
             "sem o código, nada muda na sua conta.\n\n— TrueCompass")
    html = f"""<div style="font-family:Arial,sans-serif;max-width:440px;margin:auto;color:#171A1D">
  <h2 style="margin:0 0 4px">True<span style="color:#C5303E">Compass</span></h2>
  <p>{primeiro},</p><p>{_FRASE[finalidade]}</p>
  <p style="font-size:34px;letter-spacing:10px;font-weight:bold;background:#EEF3EF;
            border-radius:12px;padding:16px;text-align:center;color:#1F5E33">{codigo}</p>
  <p style="color:#5F6770;font-size:13px">Ele vale por 15 minutos. Se não foi você, ignore este
  e-mail: sem o código, nada muda na sua conta.</p></div>"""
    return {"para": destino, "assunto": assunto, "texto": texto, "html": html,
            "codigo": codigo, "finalidade": finalidade}


def _por_resend(config, msg):
    corpo = json.dumps({"from": config.email_remetente, "to": [msg["para"]],
                        "subject": msg["assunto"], "text": msg["texto"], "html": msg["html"]})
    requisicao = urllib.request.Request(
        "https://api.resend.com/emails", data=corpo.encode(), method="POST",
        headers={"Authorization": f"Bearer {config.resend_chave}",
                 "Content-Type": "application/json", "User-Agent": "TrueCompass/1.0"})
    with urllib.request.urlopen(requisicao, timeout=10) as resposta:
        resposta.read()


def _por_smtp(config, msg):
    mensagem = EmailMessage()
    mensagem["From"] = config.email_remetente
    mensagem["To"] = msg["para"]
    mensagem["Subject"] = msg["assunto"]
    mensagem.set_content(msg["texto"])
    mensagem.add_alternative(msg["html"], subtype="html")
    contexto = ssl.create_default_context()
    if config.smtp_porta == 465:
        servidor = smtplib.SMTP_SSL(config.smtp_host, config.smtp_porta, timeout=15, context=contexto)
    else:
        servidor = smtplib.SMTP(config.smtp_host, config.smtp_porta, timeout=15)
        servidor.starttls(context=contexto)
    with servidor:
        if config.smtp_usuario:
            servidor.login(config.smtp_usuario, config.smtp_senha)
        servidor.send_message(mensagem)


def enviar_codigo(destino, nome, codigo, finalidade):
    """Manda o codigo. Nunca levanta: roda em segundo plano, e uma falha de
    e-mail vira log (a pessoa pode pedir de novo)."""
    config = obter_config()
    msg = montar(destino, nome, codigo, finalidade)
    try:
        if config.email_modo == "memoria":
            ENVIADOS.append(msg)
        elif config.email_modo == "resend":
            _por_resend(config, msg)
        elif config.email_modo == "smtp":
            _por_smtp(config, msg)
        else:
            registrador.warning("e-mail desligado (EMAIL_MODO=log): codigo de %s para %s = %s",
                                finalidade, _mascarar(destino), codigo)
            return
        registrador.info("codigo de %s enviado para %s", finalidade, _mascarar(destino))
    except Exception as erro:                       # noqa: BLE001 -- segundo plano
        registrador.error("falha ao enviar codigo para %s: %s", _mascarar(destino), erro)
