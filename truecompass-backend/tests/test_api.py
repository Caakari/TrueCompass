"""Teste de integracao da API: o ciclo completo de uma corrida.

Sobe a aplicacao de verdade (FastAPI + SQLAlchemy sobre SQLite temporario) e
percorre o fluxo inteiro, inclusive as tentativas que o DAG deve recusar.

    python3 tests/test_api.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# O engine e criado no import de infra.banco: o ambiente tem de estar pronto antes.
_BANCO = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_BANCO.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_BANCO.name}"
os.environ["JWT_SECRET"] = "segredo-de-teste"
os.environ["AMBIENTE"] = "teste"
os.environ["MALHA_ARQUIVO"] = "__inexistente__"   # forca a cidade sintetica

from fastapi.testclient import TestClient      # noqa: E402

from api.main import criar_app                 # noqa: E402
from dominio import estados as E               # noqa: E402

# Coordenadas dentro da cidade sintetica (lado 40, a partir de -23.55/-46.64).
MOTORISTA = (-23.5320, -46.6220)
ORIGEM = (-23.5320, -46.6211)
DESTINO = (-23.5230, -46.6130)

# Atribuido em main(): o lifespan (que cria as tabelas e carrega o grafo) so
# roda quando o TestClient e usado como gerenciador de contexto.
cliente = None
aplicacao = None
_contador = iter(range(1000))


def limpar_estado():
    """Zera o pool de motoristas entre testes.

    Sem isso a suite depende da ordem: motoristas deixados disponiveis por um
    teste anterior sao encontrados pelo pareamento do teste seguinte. O estado
    vive em dois lugares -- o banco e o registro em memoria -- e os dois
    precisam ser limpos.
    """
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
    for motorista_id in list(registro.instantaneo()):
        registro.esquecer(motorista_id)


def cabecalho(token):
    return {"Authorization": f"Bearer {token}"}


def novo_passageiro():
    n = next(_contador)
    r = cliente.post("/auth/registro", json={
        "nome": f"Passageiro {n}", "email": f"p{n}@usjt.br",
        "senha": "senha-forte-123", "tipo": "passageiro"})
    assert r.status_code == 201, r.text
    return r.json()["token"]


def novo_motorista(lat=MOTORISTA[0], lon=MOTORISTA[1], disponivel=True):
    n = next(_contador)
    r = cliente.post("/auth/registro", json={
        "nome": f"Motorista {n}", "email": f"m{n}@usjt.br",
        "senha": "senha-forte-123", "tipo": "motorista",
        "placa": f"ABC{n:04d}"[:10], "modelo": "Onix"})
    assert r.status_code == 201, r.text
    token = r.json()["token"]
    assert cliente.post("/motoristas/posicao", json={"lat": lat, "lon": lon},
                        headers=cabecalho(token)).status_code == 200
    if disponivel:
        assert cliente.post("/motoristas/disponibilidade", json={"disponivel": True},
                            headers=cabecalho(token)).status_code == 200
    return token


def pedir_corrida(token_passageiro):
    return cliente.post("/corridas", json={
        "origem_lat": ORIGEM[0], "origem_lon": ORIGEM[1],
        "destino_lat": DESTINO[0], "destino_lon": DESTINO[1],
    }, headers=cabecalho(token_passageiro))


# ------------------------------------------------------------------ basico

def test_saude_responde():
    dados = cliente.get("/saude").json()
    assert dados["status"] == "ok" and dados["nos_na_malha"] == 1600


def test_email_duplicado_e_recusado():
    corpo = {"nome": "Repetida", "email": "duplicado@usjt.br",
             "senha": "senha-forte-123", "tipo": "passageiro"}
    assert cliente.post("/auth/registro", json=corpo).status_code == 201
    assert cliente.post("/auth/registro", json=corpo).status_code == 409


def test_motorista_sem_placa_e_recusado():
    r = cliente.post("/auth/registro", json={
        "nome": "Sem Placa", "email": "semplaca@usjt.br",
        "senha": "senha-forte-123", "tipo": "motorista"})
    assert r.status_code == 422


def test_login_errado_nao_revela_se_o_email_existe():
    cliente.post("/auth/registro", json={
        "nome": "Alguem", "email": "existe@usjt.br",
        "senha": "senha-forte-123", "tipo": "passageiro"})
    a = cliente.post("/auth/login", json={"email": "existe@usjt.br", "senha": "errada"})
    b = cliente.post("/auth/login", json={"email": "naoexiste@usjt.br", "senha": "errada"})
    assert a.status_code == b.status_code == 401
    assert a.json()["detail"] == b.json()["detail"]


def test_rota_protegida_exige_token():
    assert cliente.get("/corridas/1").status_code == 401
    assert cliente.get("/corridas/1", headers=cabecalho("lixo")).status_code == 401


# --------------------------------------------------------- ciclo da corrida

def test_ciclo_completo_da_corrida():
    passageiro = novo_passageiro()
    novo_motorista()

    resposta = pedir_corrida(passageiro)
    assert resposta.status_code == 201, resposta.text
    corrida = resposta.json()
    assert corrida["estado"] == E.ROTA          # pedido -> alocacao -> rota
    assert corrida["motorista_id"] is not None
    assert corrida["eta_segundos"] > 0
    assert corrida["custo_estimado"] > 0

    cid = corrida["id"]
    for acao, esperado in (("iniciar", E.EM_CURSO),
                           ("finalizar", E.CONCLUIDA),
                           ("pagamento", E.PAGA)):
        r = cliente.post(f"/corridas/{cid}/{acao}", headers=cabecalho(passageiro))
        assert r.status_code == 200, r.text
        assert r.json()["estado"] == esperado


def test_rota_devolve_tracado_para_o_mapa():
    passageiro = novo_passageiro()
    novo_motorista()
    cid = pedir_corrida(passageiro).json()["id"]

    rota = cliente.get(f"/corridas/{cid}/rota", headers=cabecalho(passageiro)).json()
    assert rota["segundos"] > 0 and rota["metros"] > 0
    assert len(rota["pontos"]) >= 2
    assert all(len(p) == 2 for p in rota["pontos"])


# -------------------------------------------- o DAG barrando o que deve barrar

def test_nao_se_paga_corrida_que_nao_terminou():
    """A promessa do README, verificada via HTTP."""
    passageiro = novo_passageiro()
    novo_motorista()
    cid = pedir_corrida(passageiro).json()["id"]

    r = cliente.post(f"/corridas/{cid}/pagamento", headers=cabecalho(passageiro))
    assert r.status_code == 409
    assert "invalida" in r.json()["detail"]


def test_nao_se_finaliza_corrida_que_nao_comecou():
    passageiro = novo_passageiro()
    novo_motorista()
    cid = pedir_corrida(passageiro).json()["id"]
    assert cliente.post(f"/corridas/{cid}/finalizar",
                        headers=cabecalho(passageiro)).status_code == 409


def test_nao_se_inicia_duas_vezes():
    passageiro = novo_passageiro()
    novo_motorista()
    cid = pedir_corrida(passageiro).json()["id"]
    assert cliente.post(f"/corridas/{cid}/iniciar",
                        headers=cabecalho(passageiro)).status_code == 200
    assert cliente.post(f"/corridas/{cid}/iniciar",
                        headers=cabecalho(passageiro)).status_code == 409


def test_corrida_em_curso_nao_pode_ser_cancelada():
    passageiro = novo_passageiro()
    novo_motorista()
    cid = pedir_corrida(passageiro).json()["id"]
    cliente.post(f"/corridas/{cid}/iniciar", headers=cabecalho(passageiro))
    assert cliente.post(f"/corridas/{cid}/cancelar",
                        headers=cabecalho(passageiro)).status_code == 409


# ------------------------------------------------------------- pareamento

def test_sem_motorista_disponivel_devolve_503():
    passageiro = novo_passageiro()
    novo_motorista(disponivel=False)
    r = pedir_corrida(passageiro)
    assert r.status_code == 503
    assert "disponivel" in r.json()["detail"]


def test_motorista_alocado_sai_do_pool():
    """Dois pedidos, um motorista: o segundo nao pode pegar o mesmo carro."""
    novo_motorista()
    primeiro = pedir_corrida(novo_passageiro())
    assert primeiro.status_code == 201

    segundo = pedir_corrida(novo_passageiro())
    assert segundo.status_code == 503, "o mesmo motorista foi alocado duas vezes"


def test_motorista_volta_ao_pool_apos_finalizar():
    passageiro = novo_passageiro()
    novo_motorista()
    cid = pedir_corrida(passageiro).json()["id"]
    cliente.post(f"/corridas/{cid}/iniciar", headers=cabecalho(passageiro))
    cliente.post(f"/corridas/{cid}/finalizar", headers=cabecalho(passageiro))

    assert pedir_corrida(novo_passageiro()).status_code == 201


def test_escolhe_o_motorista_de_menor_eta():
    """Com dois candidatos, o pareamento tem de pegar o de menor ETA REAL."""
    novo_motorista(-23.5320, -46.6100)          # bem mais longe da origem
    novo_motorista()                            # colado na origem

    corrida = pedir_corrida(novo_passageiro()).json()
    assert corrida["eta_segundos"] < 120, corrida["eta_segundos"]

    # E o de longe continua no pool, porque nao foi ele o escolhido.
    segunda = pedir_corrida(novo_passageiro())
    assert segunda.status_code == 201
    assert segunda.json()["eta_segundos"] > corrida["eta_segundos"]


# ------------------------------------------------------------- isolamento

def test_nao_se_ve_corrida_alheia():
    passageiro = novo_passageiro()
    novo_motorista()
    cid = pedir_corrida(passageiro).json()["id"]
    assert cliente.get(f"/corridas/{cid}",
                       headers=cabecalho(novo_passageiro())).status_code == 403


def test_passageiro_nao_atualiza_posicao_de_motorista():
    assert cliente.post("/motoristas/posicao", json={"lat": 0.0, "lon": 0.0},
                        headers=cabecalho(novo_passageiro())).status_code == 403


def test_auditoria_registra_todas_as_transicoes():
    """A tabela de transicoes e a prova empirica da ordem topologica."""
    from infra.banco import Sessao
    from infra.modelos import CorridaTransicao

    passageiro = novo_passageiro()
    novo_motorista()
    cid = pedir_corrida(passageiro).json()["id"]
    for acao in ("iniciar", "finalizar", "pagamento"):
        cliente.post(f"/corridas/{cid}/{acao}", headers=cabecalho(passageiro))

    sessao = Sessao()
    try:
        linhas = (sessao.query(CorridaTransicao)
                  .filter_by(corrida_id=cid).order_by(CorridaTransicao.id).all())
    finally:
        sessao.close()

    percurso = [(t.de_estado, t.para_estado) for t in linhas]
    assert percurso == [
        (E.PEDIDO, E.ALOCACAO), (E.ALOCACAO, E.ROTA), (E.ROTA, E.EM_CURSO),
        (E.EM_CURSO, E.CONCLUIDA), (E.CONCLUIDA, E.PAGA),
    ], percurso


# ---------------------------------------------------------------------------

def main():
    global cliente
    testes = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    falhas = 0
    global aplicacao
    aplicacao = criar_app()
    with TestClient(aplicacao) as conectado:
        cliente = conectado
        for teste in testes:
            try:
                limpar_estado()
                teste()
                print(f"  ok    {teste.__name__}")
            except AssertionError as erro:
                falhas += 1
                print(f"  FALHA {teste.__name__}: {str(erro)[:160]}")
    print(f"\n{len(testes) - falhas}/{len(testes)} testes passaram")
    # O pool do SQLAlchemy mantem o arquivo aberto; no Windows o unlink falharia.
    from infra.banco import engine
    engine.dispose()
    os.unlink(_BANCO.name)
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
