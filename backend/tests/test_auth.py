"""Testes da conta e do login: senha forte, codigo por e-mail, bloqueio por
tentativas, recuperar senha, sessao renovavel e Google.

    python3 backend/tests/test_auth.py
"""

import os
import sys
import tempfile
from contextlib import contextmanager

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import matematica_no_caminho  # noqa: E402,F401  -- pacote `algoritmos`, em ../matematica

_BANCO = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_BANCO.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_BANCO.name}"
os.environ["JWT_SECRET"] = "segredo-de-teste"
os.environ["AMBIENTE"] = "teste"
os.environ["MALHA_ARQUIVO"] = "__inexistente__"
os.environ["MAPA_MATRIZ"] = "__inexistente__"
os.environ["CORS_ORIGENS"] = "https://app-teste.vercel.app"
# E-mails ficam numa lista em memoria; nenhum sai de verdade.
os.environ["EMAIL_MODO"] = "memoria"

from fastapi.testclient import TestClient      # noqa: E402

from api.main import criar_app                 # noqa: E402
from dominio.limitador import Limitador        # noqa: E402
from dominio.servicos.conta import problemas_da_senha  # noqa: E402
from infra import email as correio             # noqa: E402
from infra import google                       # noqa: E402
from infra.config import obter_config          # noqa: E402

cliente = None
aplicacao = None
_contador = iter(range(10_000))
SENHA = "senha-forte-123"


def novo_email():
    return f"pessoa{next(_contador)}@usjt.br"


def limpar():
    aplicacao.state.limites.zerar()
    correio.ENVIADOS.clear()


@contextmanager
def configurado(**valores):
    """Muda a configuracao so durante o bloco (ex.: confirmar_email=True)."""
    config = obter_config()
    antes = {k: getattr(config, k) for k in valores}
    for chave, valor in valores.items():
        setattr(config, chave, valor)
    try:
        yield
    finally:
        for chave, valor in antes.items():
            setattr(config, chave, valor)


def registrar(email, senha=SENHA, tipo="passageiro", **extra):
    corpo = {"nome": "Ana Souza", "email": email, "senha": senha, "tipo": tipo, **extra}
    return cliente.post("/auth/registro", json=corpo)


def entrar(email, senha=SENHA, manter=False):
    return cliente.post("/auth/login", json={"email": email, "senha": senha, "manter_conectado": manter})


def ultimo_codigo(email, finalidade):
    enviados = [m for m in correio.ENVIADOS if m["para"] == email and m["finalidade"] == finalidade]
    assert enviados, f"nenhum codigo de {finalidade} para {email}"
    return enviados[-1]["codigo"]


def liberar_reenvio():
    aplicacao.state.limites.intervalo_envio.clear()


# ------------------------------------------------------------- forca da senha

def test_regras_da_senha_sao_as_mesmas_do_app():
    assert problemas_da_senha("Mooca2026!rota") == []
    assert "pelo menos 8 caracteres" in problemas_da_senha("ab1")
    assert "letras e numeros" in problemas_da_senha("somenteletras")
    assert "letras e numeros" in problemas_da_senha("1234567890")
    assert problemas_da_senha("senha123"), "senha da lista de comuns"
    assert problemas_da_senha("aaaaaaaa1") == [], "repeticao so recusa quando e um caractere so"
    assert problemas_da_senha("anasouza2026", "anasouza@gmail.com"), "contem o e-mail"


def test_cadastro_recusa_senha_fraca():
    resposta = registrar(novo_email(), senha="senha123")
    assert resposta.status_code == 422
    assert "senha fraca" in resposta.json()["detail"]


# ---------------------------------------------------- cadastro e confirmacao

def test_sem_email_configurado_o_cadastro_abre_a_sessao_na_hora():
    """Sem servico de e-mail o codigo nao chegaria a ninguem: a confirmacao
    fica desligada e o cadastro funciona como antes."""
    resposta = registrar(novo_email())
    assert resposta.status_code == 201, resposta.text
    dados = resposta.json()
    assert dados["token"] and dados["renovacao"] is None
    assert not correio.ENVIADOS


def test_cadastro_com_confirmacao_so_abre_a_conta_com_o_codigo():
    email = novo_email()
    with configurado(confirmar_email=True):
        resposta = registrar(email)
        assert resposta.status_code == 201, resposta.text
        assert resposta.json() == {"confirmacao_pendente": True, "email": email}
        codigo = ultimo_codigo(email, "confirmar")
        assert len(codigo) == 6 and codigo.isdigit()

        negado = entrar(email)
        assert negado.status_code == 403 and negado.json()["detail"] == "email_nao_confirmado"

        errado = "000000" if codigo != "000000" else "111111"
        assert cliente.post("/auth/confirmar-email", json={"email": email, "codigo": errado}).status_code == 400
        certo = cliente.post("/auth/confirmar-email", json={"email": email, "codigo": codigo})
        assert certo.status_code == 200, certo.text
        assert certo.json()["token"] and certo.json()["renovacao"], "confirmar ja deixa conectado"
        # O codigo e de uso unico.
        assert cliente.post("/auth/confirmar-email", json={"email": email, "codigo": codigo}).status_code == 400
        assert entrar(email).status_code == 200


def test_codigo_morre_depois_de_cinco_erros():
    email = novo_email()
    with configurado(confirmar_email=True):
        registrar(email)
        codigo = ultimo_codigo(email, "confirmar")
        errado = "000000" if codigo != "000000" else "111111"
        for _ in range(5):
            assert cliente.post("/auth/confirmar-email", json={"email": email, "codigo": errado}).status_code == 400
        resposta = cliente.post("/auth/confirmar-email", json={"email": email, "codigo": codigo})
        assert resposta.status_code == 400, "o codigo certo ja nao vale: pede-se outro"


def test_codigo_novo_invalida_o_anterior():
    email = novo_email()
    with configurado(confirmar_email=True):
        registrar(email)
        antigo = ultimo_codigo(email, "confirmar")
        liberar_reenvio()
        assert cliente.post("/auth/reenviar-codigo", json={"email": email, "finalidade": "confirmar"}).status_code == 204
        novo = ultimo_codigo(email, "confirmar")
        if antigo != novo:
            assert cliente.post("/auth/confirmar-email", json={"email": email, "codigo": antigo}).status_code == 400
        assert cliente.post("/auth/confirmar-email", json={"email": email, "codigo": novo}).status_code == 200


def test_reenvio_respeita_o_intervalo_com_retry_after():
    email = novo_email()
    with configurado(confirmar_email=True):
        registrar(email)                         # o cadastro ja mandou um
        resposta = cliente.post("/auth/reenviar-codigo", json={"email": email, "finalidade": "confirmar"})
    assert resposta.status_code == 429
    assert 0 < int(resposta.headers["Retry-After"]) <= 61


# ----------------------------------------------------------- recuperar senha

def test_recuperar_responde_igual_com_ou_sem_conta():
    email = novo_email()
    registrar(email)
    sem = cliente.post("/auth/recuperar-senha", json={"email": "ninguem@usjt.br"})
    com = cliente.post("/auth/recuperar-senha", json={"email": email})
    assert sem.status_code == com.status_code == 204
    assert [m["para"] for m in correio.ENVIADOS] == [email], "so a conta que existe recebe"


def test_redefinir_troca_a_senha_e_derruba_as_outras_sessoes():
    email = novo_email()
    registrar(email)
    outra_sessao = entrar(email, manter=True).json()["renovacao"]
    cliente.post("/auth/recuperar-senha", json={"email": email})
    codigo = ultimo_codigo(email, "recuperar")

    fraca = cliente.post("/auth/redefinir-senha", json={"email": email, "codigo": codigo, "senha": "12345678"})
    assert fraca.status_code == 422
    resposta = cliente.post("/auth/redefinir-senha",
                            json={"email": email, "codigo": codigo, "senha": "NovaRota#2026"})
    assert resposta.status_code == 200, resposta.text
    assert entrar(email).status_code == 401, "a senha antiga nao vale mais"
    assert entrar(email, "NovaRota#2026").status_code == 200
    assert cliente.post("/auth/renovar", json={"renovacao": outra_sessao}).status_code == 401


# ------------------------------------------------------- bloqueio por tentativas

def test_login_bloqueia_depois_de_cinco_senhas_erradas():
    email = novo_email()
    registrar(email)
    respostas = [entrar(email, "errada-123") for _ in range(5)]
    assert [r.status_code for r in respostas[:4]] == [401] * 4
    assert respostas[4].status_code == 429
    assert 200 < int(respostas[4].headers["Retry-After"]) <= 301
    assert entrar(email).status_code == 429, "nem a senha certa entra durante o bloqueio"
    outro = novo_email()
    registrar(outro)
    assert entrar(outro).status_code == 200, "o bloqueio e por e-mail, nao geral"


def test_login_nao_revela_quais_emails_existem():
    email = novo_email()
    registrar(email)
    a = entrar(email, "errada-123")
    b = entrar("nao-existe@usjt.br", "errada-123")
    assert a.status_code == b.status_code == 401
    assert a.json() == b.json()


def test_limitador_libera_depois_do_bloqueio():
    agora = [0.0]
    limitador = Limitador(3, janela_s=60, bloqueio_s=300, relogio=lambda: agora[0])
    assert limitador.falhou("x") == 0 and limitador.falhou("x") == 0
    assert limitador.falhou("x") == 300
    agora[0] = 299
    assert limitador.espera("x") == 2
    agora[0] = 301
    assert limitador.espera("x") == 0
    # Falhas espalhadas alem da janela nao se somam.
    for t in (400, 470, 540):
        agora[0] = t
        assert limitador.falhou("y") == 0


def test_cors_expoe_o_retry_after_ao_app():
    resposta = cliente.post("/auth/login", json={"email": "a@b.com", "senha": "x"},
                            headers={"Origin": "https://app-teste.vercel.app"})
    assert "retry-after" in resposta.headers.get("access-control-expose-headers", "").lower()


# ------------------------------------------------------- manter conectado

def test_sem_manter_conectado_nao_ha_renovacao():
    email = novo_email()
    registrar(email)
    assert entrar(email).json()["renovacao"] is None


def test_renovacao_troca_o_token_e_detecta_reuso():
    email = novo_email()
    registrar(email)
    primeira = entrar(email, manter=True).json()["renovacao"]
    renovada = cliente.post("/auth/renovar", json={"renovacao": primeira})
    assert renovada.status_code == 200, renovada.text
    segunda = renovada.json()["renovacao"]
    assert segunda and segunda != primeira and renovada.json()["token"]
    perfil = cliente.get("/usuarios/eu", headers={"Authorization": f"Bearer {renovada.json()['token']}"})
    assert perfil.status_code == 200
    # O token velho usado de novo = vazou: derruba tambem o novo.
    assert cliente.post("/auth/renovar", json={"renovacao": primeira}).status_code == 401
    assert cliente.post("/auth/renovar", json={"renovacao": segunda}).status_code == 401


def test_sair_encerra_a_sessao_do_aparelho():
    email = novo_email()
    registrar(email)
    renovacao = entrar(email, manter=True).json()["renovacao"]
    assert cliente.post("/auth/sair", json={"renovacao": renovacao}).status_code == 204
    assert cliente.post("/auth/renovar", json={"renovacao": renovacao}).status_code == 401


# ------------------------------------------------------------------ recursos

def test_recursos_dizem_o_que_esta_configurado():
    """O app esconde "Esqueci minha senha" e "Continuar com Google" quando o
    servidor não tem e-mail ou client id: botão que só dá erro, na frente da
    banca, é pior que botão nenhum."""
    with configurado(email_modo="log", google_client_id=""):
        assert cliente.get("/auth/recursos").json() == {"email": False, "confirmar_email": False, "google": False}
    with configurado(email_modo="brevo", confirmar_email=True, google_client_id="id.apps.googleusercontent.com"):
        assert cliente.get("/auth/recursos").json() == {"email": True, "confirmar_email": True, "google": True}


# --------------------------------------------------------------- e-mail (Brevo)

class _RespostaFalsa:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return b'{"messageId":"<1@brevo>"}'


def test_brevo_monta_a_requisicao_certa_sem_enviar_nada():
    import json as _json
    import urllib.request as _req
    enviadas, original = [], _req.urlopen
    _req.urlopen = lambda requisicao, timeout=None: enviadas.append(requisicao) or _RespostaFalsa()
    try:
        with configurado(email_modo="brevo", brevo_chave="xkeysib-teste",
                         email_remetente="TrueCompass <truecompass.app@gmail.com>"):
            correio.enviar_codigo("ana@usjt.br", "Ana Souza", "123456", "recuperar")
    finally:
        _req.urlopen = original
    assert len(enviadas) == 1
    req = enviadas[0]
    assert req.full_url == "https://api.brevo.com/v3/smtp/email"
    assert req.get_header("Api-key") == "xkeysib-teste"
    corpo = _json.loads(req.data)
    assert corpo["sender"] == {"name": "TrueCompass", "email": "truecompass.app@gmail.com"}
    assert corpo["to"] == [{"email": "ana@usjt.br"}]
    assert "123456" in corpo["subject"] and "123456" in corpo["htmlContent"]


def test_recusa_do_brevo_vira_log_e_nao_derruba_nada():
    import io as _io
    import urllib.error as _erro
    import urllib.request as _req

    def recusa(requisicao, timeout=None):
        raise _erro.HTTPError(requisicao.full_url, 401, "Unauthorized", {},
                              _io.BytesIO(b'{"message":"unrecognised IP address"}'))

    original = _req.urlopen
    _req.urlopen = recusa
    try:
        with configurado(email_modo="brevo", brevo_chave="xkeysib-teste"):
            correio.enviar_codigo("ana@usjt.br", "Ana", "123456", "confirmar")   # nao levanta
    finally:
        _req.urlopen = original


def test_chave_do_brevo_escolhe_o_modo_e_liga_a_confirmacao():
    from infra.config import Config
    antes = {k: os.environ.get(k) for k in ("EMAIL_MODO", "BREVO_API_KEY", "CONFIRMAR_EMAIL")}
    os.environ.pop("EMAIL_MODO", None)
    os.environ.pop("CONFIRMAR_EMAIL", None)
    os.environ["BREVO_API_KEY"] = "xkeysib-teste"
    try:
        config = Config()
        assert config.email_modo == "brevo" and config.confirmar_email is True
        os.environ["CONFIRMAR_EMAIL"] = "0"
        assert Config().confirmar_email is False, "CONFIRMAR_EMAIL=0 segura a confirmacao"
    finally:
        for chave, valor in antes.items():
            if valor is None:
                os.environ.pop(chave, None)
            else:
                os.environ[chave] = valor


def test_remetente_com_ou_sem_nome():
    assert correio.separar_remetente("TrueCompass <app@gmail.com>") == ("TrueCompass", "app@gmail.com")
    assert correio.separar_remetente("app@gmail.com") == ("TrueCompass", "app@gmail.com")


# ------------------------------------------------------------------ google

@contextmanager
def google_falso(perfis):
    """`perfis`: token -> perfil. Token desconhecido = invalido."""
    original = google.verificar

    def verificar(token, client_id):
        assert client_id == "cliente-teste.apps.googleusercontent.com"
        if token not in perfis:
            raise google.TokenGoogleInvalido("token do Google invalido ou vencido")
        return perfis[token]

    google.verificar = verificar
    try:
        with configurado(google_client_id="cliente-teste.apps.googleusercontent.com"):
            yield
    finally:
        google.verificar = original


def test_google_sem_configuracao_responde_503():
    with configurado(google_client_id=""):
        resposta = cliente.post("/auth/google", json={"credencial": "qualquer-token-123"})
    assert resposta.status_code == 503


def test_google_cria_a_conta_e_depois_entra_na_mesma():
    email = novo_email()
    perfil = {"sub": f"g-{email}", "email": email, "nome": "Bruno Lima"}
    with google_falso({"token-bruno-1": perfil}):
        primeira = cliente.post("/auth/google", json={"credencial": "token-bruno-1"})
        segunda = cliente.post("/auth/google", json={"credencial": "token-bruno-1"})
        recusada = cliente.post("/auth/google", json={"credencial": "token-de-outro-app"})
    assert primeira.status_code == 200, primeira.text
    assert primeira.json()["usuario_id"] == segunda.json()["usuario_id"]
    assert primeira.json()["tipo"] == "passageiro" and primeira.json()["renovacao"]
    assert recusada.status_code == 401
    eu = cliente.get("/usuarios/eu", headers={"Authorization": f"Bearer {primeira.json()['token']}"}).json()
    assert eu["nome"] == "Bruno Lima" and eu["email"] == email


def test_google_liga_a_conta_de_email_que_ja_existia():
    email = novo_email()
    usuario_id = registrar(email).json()["usuario_id"]
    with google_falso({"token-ana-1": {"sub": f"g-{email}", "email": email, "nome": "Ana"}}):
        resposta = cliente.post("/auth/google", json={"credencial": "token-ana-1"})
    assert resposta.json()["usuario_id"] == usuario_id
    assert entrar(email).status_code == 200, "a senha continua valendo"


def test_motorista_pelo_google_precisa_da_placa_para_ficar_online():
    email = novo_email()
    with google_falso({"token-carlos-1": {"sub": f"g-{email}", "email": email, "nome": "Carlos"}}):
        resposta = cliente.post("/auth/google", json={"credencial": "token-carlos-1", "tipo": "motorista"})
    token = resposta.json()["token"]
    cabecalho = {"Authorization": f"Bearer {token}"}
    online = cliente.post("/motoristas/disponibilidade", json={"disponivel": True}, headers=cabecalho)
    assert online.status_code == 409 and "placa" in online.json()["detail"]
    assert cliente.patch("/usuarios/eu", json={"placa": "FTC1A23"}, headers=cabecalho).status_code == 200
    assert cliente.post("/motoristas/disponibilidade", json={"disponivel": True}, headers=cabecalho).status_code == 200


# ---------------------------------------------------------------------------

def main():
    global cliente, aplicacao
    testes = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    falhas = 0
    aplicacao = criar_app()
    with TestClient(aplicacao) as conectado:
        cliente = conectado
        for teste in testes:
            try:
                limpar()
                teste()
                print(f"  ok    {teste.__name__}")
            except AssertionError as erro:
                falhas += 1
                print(f"  FALHA {teste.__name__}: {str(erro)[:160]}")
    print(f"\n{len(testes) - falhas}/{len(testes)} testes passaram")
    from infra.banco import engine
    engine.dispose()
    os.unlink(_BANCO.name)
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
