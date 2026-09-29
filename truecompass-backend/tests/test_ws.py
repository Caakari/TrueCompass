"""Testes do acompanhamento em tempo real (WebSocket).

    python3 tests/test_ws.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_BANCO = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_BANCO.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_BANCO.name}"
os.environ["JWT_SECRET"] = "segredo-de-teste"
os.environ["AMBIENTE"] = "teste"
os.environ["MALHA_ARQUIVO"] = "__inexistente__"

from fastapi.testclient import TestClient      # noqa: E402

from api.main import criar_app                 # noqa: E402
from dominio import estados as E               # noqa: E402

MOTORISTA = (-23.5320, -46.6220)
ORIGEM = (-23.5320, -46.6211)
DESTINO = (-23.5230, -46.6130)

cliente = None
aplicacao = None
_contador = iter(range(1000))


def cabecalho(token):
    return {"Authorization": f"Bearer {token}"}


def registrar(tipo):
    n = next(_contador)
    corpo = {"nome": f"Pessoa {n}", "email": f"u{n}@usjt.br",
             "senha": "senha-forte-123", "tipo": tipo}
    if tipo == "motorista":
        corpo["placa"] = f"AB{n:05d}"[:10]
    resposta = cliente.post("/auth/registro", json=corpo)
    assert resposta.status_code == 201, resposta.text
    return resposta.json()["token"]


def motorista_online():
    token = registrar("motorista")
    cliente.post("/motoristas/posicao",
                 json={"lat": MOTORISTA[0], "lon": MOTORISTA[1]},
                 headers=cabecalho(token))
    cliente.post("/motoristas/disponibilidade", json={"disponivel": True},
                 headers=cabecalho(token))
    return token


def corrida_pronta():
    """Devolve (token_passageiro, token_motorista, corrida_id)."""
    limpar_pool()
    passageiro = registrar("passageiro")
    motorista = motorista_online()
    resposta = cliente.post("/corridas", json={
        "origem_lat": ORIGEM[0], "origem_lon": ORIGEM[1],
        "destino_lat": DESTINO[0], "destino_lon": DESTINO[1],
    }, headers=cabecalho(passageiro))
    assert resposta.status_code == 201, resposta.text
    return passageiro, motorista, resposta.json()["id"]


def limpar_pool():
    from infra.banco import Sessao
    from infra.modelos import Motorista

    sessao = Sessao()
    try:
        for motorista in sessao.query(Motorista).all():
            motorista.disponivel = False
        sessao.commit()
    finally:
        sessao.close()
    registro = aplicacao.state.registro
    for identificador in list(registro.instantaneo()):
        registro.esquecer(identificador)


def abrir(corrida_id, token):
    return cliente.websocket_connect(f"/ws/corridas/{corrida_id}?token={token}")


# ------------------------------------------------------------------ conexao

def test_conexao_recebe_o_estado_atual():
    passageiro, _, cid = corrida_pronta()
    with abrir(cid, passageiro) as ws:
        primeira = ws.receive_json()
    assert primeira["evento"] == "estado"
    assert primeira["estado"] == E.ROTA
    assert primeira["corrida_id"] == cid
    assert primeira["motorista_id"] is not None


def test_motorista_tambem_acompanha():
    _, motorista, cid = corrida_pronta()
    with abrir(cid, motorista) as ws:
        assert ws.receive_json()["estado"] == E.ROTA


def test_token_invalido_e_recusado():
    passageiro, _, cid = corrida_pronta()
    try:
        with abrir(cid, "token-falso") as ws:
            ws.receive_json()
    except Exception:
        return
    raise AssertionError("conexao com token invalido deveria ser fechada")


def test_terceiro_nao_acompanha_corrida_alheia():
    _, _, cid = corrida_pronta()
    intruso = registrar("passageiro")
    try:
        with abrir(cid, intruso) as ws:
            ws.receive_json()
    except Exception:
        return
    raise AssertionError("terceiro nao pode acompanhar")


def test_corrida_inexistente_e_recusada():
    passageiro, _, _ = corrida_pronta()
    try:
        with abrir(99999, passageiro) as ws:
            ws.receive_json()
    except Exception:
        return
    raise AssertionError("corrida inexistente deveria ser recusada")


# ------------------------------------------------------------- publicacao

def test_transicao_chega_no_websocket():
    passageiro, _, cid = corrida_pronta()
    with abrir(cid, passageiro) as ws:
        ws.receive_json()                                  # estado inicial
        cliente.post(f"/corridas/{cid}/iniciar", headers=cabecalho(passageiro))
        evento = ws.receive_json()
    assert evento["evento"] == "estado" and evento["estado"] == E.EM_CURSO


def test_fluxo_inteiro_chega_em_ordem():
    passageiro, _, cid = corrida_pronta()
    with abrir(cid, passageiro) as ws:
        ws.receive_json()
        recebidos = []
        for acao in ("iniciar", "finalizar", "pagamento"):
            cliente.post(f"/corridas/{cid}/{acao}", headers=cabecalho(passageiro))
            recebidos.append(ws.receive_json()["estado"])
    assert recebidos == [E.EM_CURSO, E.CONCLUIDA, E.PAGA]


def test_motorista_ve_a_transicao_feita_pelo_passageiro():
    passageiro, motorista, cid = corrida_pronta()
    with abrir(cid, motorista) as ws:
        ws.receive_json()
        cliente.post(f"/corridas/{cid}/iniciar", headers=cabecalho(passageiro))
        assert ws.receive_json()["estado"] == E.EM_CURSO


def test_posicao_do_motorista_chega_no_mapa():
    passageiro, motorista, cid = corrida_pronta()
    with abrir(cid, passageiro) as ws:
        ws.receive_json()
        nova = {"lat": MOTORISTA[0] + 0.0005, "lon": MOTORISTA[1] + 0.0005}
        resposta = cliente.post("/motoristas/posicao", json=nova,
                                headers=cabecalho(motorista))
        assert resposta.json()["corrida_ativa"] == cid
        evento = ws.receive_json()
    assert evento["evento"] == "posicao"
    assert abs(evento["lat"] - nova["lat"]) < 1e-9


def test_posicao_sem_corrida_ativa_nao_publica():
    """Motorista ocioso nao deve gerar trafego em corrida nenhuma."""
    limpar_pool()
    token = motorista_online()
    resposta = cliente.post("/motoristas/posicao",
                            json={"lat": MOTORISTA[0], "lon": MOTORISTA[1]},
                            headers=cabecalho(token))
    assert resposta.json()["corrida_ativa"] is None


# ------------------------------- a regra: publicar so depois do commit

def test_transicao_recusada_nao_publica_nada():
    """Se o DAG recusa, nada pode chegar ao cliente.

    Verificamos sem depender de tempo: tentamos a transicao invalida e, logo
    depois, uma valida. A PRIMEIRA mensagem recebida tem de ser a da valida --
    se a recusada tivesse publicado, ela chegaria antes.
    """
    passageiro, _, cid = corrida_pronta()
    with abrir(cid, passageiro) as ws:
        ws.receive_json()

        recusada = cliente.post(f"/corridas/{cid}/pagamento",
                                headers=cabecalho(passageiro))
        assert recusada.status_code == 409

        cliente.post(f"/corridas/{cid}/iniciar", headers=cabecalho(passageiro))
        evento = ws.receive_json()

    assert evento["estado"] == E.EM_CURSO, (
        f"chegou {evento['estado']!r}: a transicao recusada vazou para o cliente"
    )


def test_cancelamento_por_falta_de_motorista_chega_como_cancelada():
    limpar_pool()
    passageiro = registrar("passageiro")
    motorista_online()
    cid = cliente.post("/corridas", json={
        "origem_lat": ORIGEM[0], "origem_lon": ORIGEM[1],
        "destino_lat": DESTINO[0], "destino_lon": DESTINO[1],
    }, headers=cabecalho(passageiro)).json()["id"]

    with abrir(cid, passageiro) as ws:
        ws.receive_json()
        cliente.post(f"/corridas/{cid}/cancelar", headers=cabecalho(passageiro))
        assert ws.receive_json()["estado"] == E.CANCELADA


# ------------------------------------------------------------- isolamento

def test_evento_nao_vaza_para_outra_corrida():
    passageiro_a, _, cid_a = corrida_pronta()
    passageiro_b, _, cid_b = corrida_pronta()

    with abrir(cid_a, passageiro_a) as ws_a:
        ws_a.receive_json()
        cliente.post(f"/corridas/{cid_b}/iniciar", headers=cabecalho(passageiro_b))
        cliente.post(f"/corridas/{cid_a}/iniciar", headers=cabecalho(passageiro_a))
        evento = ws_a.receive_json()
    assert evento["corrida_id"] == cid_a, "evento da corrida B vazou para A"


def test_desconexao_limpa_o_registro():
    passageiro, _, cid = corrida_pronta()
    with abrir(cid, passageiro) as ws:
        ws.receive_json()
        assert aplicacao.state.conexoes.total() == 1
    assert aplicacao.state.conexoes.total() == 0


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
                teste()
                print(f"  ok    {teste.__name__}")
            except AssertionError as erro:
                falhas += 1
                print(f"  FALHA {teste.__name__}: {str(erro)[:150]}")
    print(f"\n{len(testes) - falhas}/{len(testes)} testes passaram")
    # O pool do SQLAlchemy mantem o arquivo aberto; no Windows o unlink falharia.
    from infra.banco import engine
    engine.dispose()
    os.unlink(_BANCO.name)
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
