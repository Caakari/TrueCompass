# -*- coding: utf-8 -*-
"""Conta e login: e-mail e senha, Google, codigo por e-mail e sessao renovavel.

Regras que valem para todas as rotas daqui:

- Nada revela se um e-mail esta cadastrado (exceto o 409 do cadastro, que e
  inevitavel): recuperar senha e reenviar codigo respondem 204 sempre, e o
  login errado gasta o mesmo bcrypt com ou sem conta.
- Muitas tentativas -> 429 com Retry-After, que o app transforma em contagem.
- O e-mail sai em segundo plano: a resposta nao espera o envio.
"""

import secrets

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.deps import ip_de, obter_limites
from api.esquemas import (ConfirmarEmailEntrada, EnviarCodigoEntrada, GoogleEntrada,
                          LoginEntrada, PendenteSaida, RecuperarEntrada, RedefinirEntrada,
                          RegistroEntrada, RenovarEntrada, TokenSaida)
from dominio.servicos import conta
from infra import email as correio
from infra import google
from infra.banco import obter_sessao
from infra.config import obter_config
from infra.modelos import Motorista, Usuario
from infra.seguranca import cifrar_senha, conferir_senha, emitir_token
from starlette.requests import HTTPConnection

rotas = APIRouter(prefix="/auth", tags=["auth"])

# Hash de uma senha qualquer: login com e-mail inexistente confere contra ele,
# para levar o MESMO tempo que um login com senha errada.
_HASH_FALSO = cifrar_senha("nenhuma-conta-tem-esta-senha-1")


def _muitas(segundos, motivo="muitas tentativas; espere e tente de novo"):
    return HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, motivo,
                         headers={"Retry-After": str(max(1, int(segundos)))})


def _sessao_de(sessao, usuario, manter):
    config = obter_config()
    renovacao = conta.abrir_renovacao(sessao, usuario, config.dias_renovacao) if manter else None
    sessao.commit()
    return TokenSaida(token=emitir_token(usuario.id, usuario.tipo), usuario_id=usuario.id,
                      tipo=usuario.tipo, renovacao=renovacao)


def _exigir_senha_forte(senha, email):
    problemas = conta.problemas_da_senha(senha, email)
    if problemas:
        raise HTTPException(422,
                            "senha fraca: precisa de " + ", ".join(problemas))


def _enviar(sessao, tarefas, limites, usuario, finalidade):
    """Gera o codigo e agenda o e-mail, respeitando o intervalo entre envios."""
    chave = f"envio:{finalidade}:{usuario.email}"
    espera = limites.espera_para_enviar(chave)
    if espera:
        raise _muitas(espera, "aguarde para pedir outro codigo")
    codigo = conta.gerar_codigo(sessao, usuario, finalidade, obter_config().segredo_jwt)
    sessao.commit()
    limites.registrar_envio(chave)
    tarefas.add_task(correio.enviar_codigo, usuario.email, usuario.nome, codigo, finalidade)


def _por_email(sessao, email):
    return sessao.query(Usuario).filter_by(email=email.lower()).one_or_none()


# ------------------------------------------------------------------ recursos

@rotas.get("/recursos")
def recursos():
    """O que está configurado neste servidor, para o app não mostrar botão que
    não funciona: sem e-mail, "Esqueci minha senha" não enviaria código; sem
    client id, "Continuar com Google" só daria erro. Público e sem segredo."""
    config = obter_config()
    return {
        "email": config.email_modo in ("brevo", "resend", "smtp", "memoria"),
        "confirmar_email": config.confirmar_email,
        "google": bool(config.google_client_id),
    }


# ------------------------------------------------------------------- cadastro

@rotas.post("/registro", response_model=TokenSaida | PendenteSaida,
            status_code=status.HTTP_201_CREATED)
def registrar(dados: RegistroEntrada, tarefas: BackgroundTasks,
              sessao: Session = Depends(obter_sessao), limites=Depends(obter_limites)):
    if dados.tipo == "motorista" and not dados.placa:
        raise HTTPException(422, "motorista exige placa")
    _exigir_senha_forte(dados.senha, dados.email)
    confirmar = obter_config().confirmar_email

    usuario = Usuario(nome=dados.nome, email=dados.email.lower(),
                      senha_hash=cifrar_senha(dados.senha), tipo=dados.tipo,
                      email_confirmado=not confirmar)
    sessao.add(usuario)
    try:
        sessao.flush()
        if dados.tipo == "motorista":
            sessao.add(Motorista(usuario_id=usuario.id, placa=dados.placa,
                                 modelo=dados.modelo or ""))
        sessao.commit()
    except IntegrityError:
        sessao.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "email ja cadastrado")

    if confirmar:
        # A conta so abre com o codigo: assim ninguem cadastra o e-mail alheio.
        _enviar(sessao, tarefas, limites, usuario, "confirmar")
        return PendenteSaida(email=usuario.email)
    return _sessao_de(sessao, usuario, manter=False)


@rotas.post("/confirmar-email", response_model=TokenSaida)
def confirmar_email(dados: ConfirmarEmailEntrada, sessao: Session = Depends(obter_sessao),
                    limites=Depends(obter_limites)):
    chave = f"codigo:{dados.email.lower()}"
    if espera := limites.codigo.espera(chave):
        raise _muitas(espera)
    usuario = _por_email(sessao, dados.email)
    try:
        if usuario is None or usuario.email_confirmado is not False:
            raise conta.CodigoInvalido("codigo invalido ou expirado")
        conta.usar_codigo(sessao, usuario, "confirmar", dados.codigo, obter_config().segredo_jwt)
    except conta.CodigoInvalido as erro:
        limites.codigo.falhou(chave)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(erro))
    limites.codigo.limpar(chave)
    usuario.email_confirmado = True
    return _sessao_de(sessao, usuario, dados.manter_conectado)


@rotas.post("/reenviar-codigo", status_code=status.HTTP_204_NO_CONTENT)
def reenviar_codigo(dados: EnviarCodigoEntrada, tarefas: BackgroundTasks,
                    sessao: Session = Depends(obter_sessao), limites=Depends(obter_limites)):
    """204 sempre (exceto o 429 do intervalo): nao revela se a conta existe."""
    usuario = _por_email(sessao, dados.email)
    precisa = usuario is not None and (
        dados.finalidade == "recuperar" or usuario.email_confirmado is False)
    if precisa:
        _enviar(sessao, tarefas, limites, usuario, dados.finalidade)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------- login

@rotas.post("/login", response_model=TokenSaida)
def login(dados: LoginEntrada, conexao: HTTPConnection,
          sessao: Session = Depends(obter_sessao), limites=Depends(obter_limites)):
    email = dados.email.lower()
    chave_email, chave_ip = f"login:{email}", f"login-ip:{ip_de(conexao)}"
    espera = max(limites.login_email.espera(chave_email), limites.login_ip.espera(chave_ip))
    if espera:
        raise _muitas(espera)

    usuario = _por_email(sessao, email)
    # Mensagem unica para email inexistente e senha errada, e o MESMO custo
    # de bcrypt nos dois casos: nem a resposta nem o tempo dizem quem existe.
    certa = conferir_senha(dados.senha, usuario.senha_hash if usuario else _HASH_FALSO)
    if not usuario or not certa:
        espera = max(limites.login_email.falhou(chave_email), limites.login_ip.falhou(chave_ip))
        if espera:
            raise _muitas(espera)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "e-mail ou senha incorretos")
    limites.login_email.limpar(chave_email)
    if usuario.email_confirmado is False:
        # A senha estava certa: so falta o codigo. O app manda para a tela dele.
        raise HTTPException(status.HTTP_403_FORBIDDEN, "email_nao_confirmado")
    return _sessao_de(sessao, usuario, dados.manter_conectado)


# --------------------------------------------------------- recuperar senha

@rotas.post("/recuperar-senha", status_code=status.HTTP_204_NO_CONTENT)
def recuperar_senha(dados: RecuperarEntrada, tarefas: BackgroundTasks,
                    sessao: Session = Depends(obter_sessao), limites=Depends(obter_limites)):
    """Manda o codigo, se a conta existir. Responde igual nos dois casos."""
    usuario = _por_email(sessao, dados.email)
    if usuario is not None:
        _enviar(sessao, tarefas, limites, usuario, "recuperar")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@rotas.post("/redefinir-senha", response_model=TokenSaida)
def redefinir_senha(dados: RedefinirEntrada, sessao: Session = Depends(obter_sessao),
                    limites=Depends(obter_limites)):
    chave = f"codigo:{dados.email.lower()}"
    if espera := limites.codigo.espera(chave):
        raise _muitas(espera)
    _exigir_senha_forte(dados.senha, dados.email)
    usuario = _por_email(sessao, dados.email)
    try:
        if usuario is None:
            raise conta.CodigoInvalido("codigo invalido ou expirado")
        conta.usar_codigo(sessao, usuario, "recuperar", dados.codigo, obter_config().segredo_jwt)
    except conta.CodigoInvalido as erro:
        limites.codigo.falhou(chave)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(erro))
    limites.codigo.limpar(chave)
    limites.login_email.limpar(f"login:{usuario.email}")
    usuario.senha_hash = cifrar_senha(dados.senha)
    # Quem recebeu o codigo provou ser dono do e-mail.
    usuario.email_confirmado = True
    # Senha trocada derruba as sessoes "manter conectado" de outros aparelhos:
    # se a troca foi por suspeita de invasao, o invasor sai.
    conta.revogar_todas(sessao, usuario.id)
    return _sessao_de(sessao, usuario, dados.manter_conectado)


# ------------------------------------------------------------------- google

@rotas.post("/google", response_model=TokenSaida)
def entrar_com_google(dados: GoogleEntrada, sessao: Session = Depends(obter_sessao)):
    client_id = obter_config().google_client_id
    if not client_id:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "entrar com Google ainda nao foi configurado neste servidor")
    try:
        perfil = google.verificar(dados.credencial, client_id)
    except google.TokenGoogleInvalido as erro:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(erro))

    usuario = sessao.query(Usuario).filter_by(google_sub=perfil["sub"]).one_or_none()
    if usuario is None:
        usuario = _por_email(sessao, perfil["email"])
        if usuario is not None:
            # Conta de e-mail e senha ja existia: o Google confirmou que o
            # e-mail e desta pessoa, entao liga as duas formas de entrar.
            usuario.google_sub = perfil["sub"]
            usuario.email_confirmado = True
    if usuario is None:
        tipo = dados.tipo or "passageiro"
        # Sem senha propria: um hash aleatorio que nenhuma senha confere. Se a
        # pessoa quiser senha, usa "esqueci minha senha".
        usuario = Usuario(nome=perfil["nome"][:120], email=perfil["email"], tipo=tipo,
                          senha_hash=cifrar_senha(secrets.token_urlsafe(24)),
                          email_confirmado=True, google_sub=perfil["sub"])
        sessao.add(usuario)
        sessao.flush()
        if tipo == "motorista":
            # A placa vem depois, no perfil; sem ela o motorista nao fica online.
            sessao.add(Motorista(usuario_id=usuario.id, placa="", modelo=""))
    return _sessao_de(sessao, usuario, dados.manter_conectado)


# -------------------------------------------------- sessao renovavel

@rotas.post("/renovar", response_model=TokenSaida)
def renovar(dados: RenovarEntrada, sessao: Session = Depends(obter_sessao)):
    """Troca o token de renovacao por um token de acesso novo E um token de
    renovacao novo (o anterior deixa de valer)."""
    config = obter_config()
    try:
        usuario_id, novo = conta.renovar(sessao, dados.renovacao, config.dias_renovacao)
    except conta.RenovacaoInvalida as erro:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(erro))
    usuario = sessao.get(Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "usuario inexistente")
    sessao.commit()
    return TokenSaida(token=emitir_token(usuario.id, usuario.tipo), usuario_id=usuario.id,
                      tipo=usuario.tipo, renovacao=novo)


@rotas.post("/sair", status_code=status.HTTP_204_NO_CONTENT)
def sair(dados: RenovarEntrada, sessao: Session = Depends(obter_sessao)):
    """Encerra a sessao deste aparelho (o token de renovacao deixa de valer)."""
    conta.revogar(sessao, dados.renovacao)
    sessao.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
