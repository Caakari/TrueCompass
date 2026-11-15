"""Teste de integracao da API: o ciclo completo de uma corrida.

Sobe a aplicacao de verdade (FastAPI + SQLAlchemy sobre SQLite temporario) e
percorre o fluxo inteiro, inclusive as tentativas que o DAG deve recusar.

    python3 backend/tests/test_api.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import matematica_no_caminho  # noqa: E402,F401  -- pacote `algoritmos`, em ../matematica

# O engine e criado no import de infra.banco: o ambiente tem de estar pronto antes.
_BANCO = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_BANCO.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_BANCO.name}"
os.environ["JWT_SECRET"] = "segredo-de-teste"
os.environ["AMBIENTE"] = "teste"
# Fixa a cidade sintetica: estes testes verificam a API, nao qual mapa e o
# padrao do servidor. Sem isto, trocar o mapa de producao quebra a suite toda.
os.environ["MALHA_ARQUIVO"] = "__inexistente__"
os.environ["MAPA_MATRIZ"] = "__inexistente__"
# Origem exata (com a barra no fim que ja enganou o deploy uma vez) e um
# padrao com curinga, como as previas do Vercel.
os.environ["CORS_ORIGENS"] = ("https://app-teste.vercel.app/,"
                              "https://app-teste-*-equipe.vercel.app")

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


def pedir_corrida(token_passageiro, **extra):
    return cliente.post("/corridas", json={
        "origem_lat": ORIGEM[0], "origem_lon": ORIGEM[1],
        "destino_lat": DESTINO[0], "destino_lon": DESTINO[1], **extra,
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


def test_rota_do_motorista_ate_o_passageiro():
    passageiro = novo_passageiro()
    novo_motorista()
    cid = pedir_corrida(passageiro).json()["id"]

    rota = cliente.get(f"/corridas/{cid}/rota-motorista",
                       headers=cabecalho(passageiro))
    assert rota.status_code == 200, rota.text
    dados = rota.json()
    assert dados["segundos"] > 0 and len(dados["pontos"]) >= 2


def test_rota_do_motorista_exige_alocacao():
    """Corrida cancelada por falta de motorista nao tem trajeto a exibir."""
    passageiro = novo_passageiro()
    novo_motorista(disponivel=False)
    assert pedir_corrida(passageiro).status_code == 503
    from infra.banco import Sessao
    from infra.modelos import Corrida
    sessao = Sessao()
    try:
        cid = sessao.query(Corrida).order_by(Corrida.id.desc()).first().id
    finally:
        sessao.close()
    resposta = cliente.get(f"/corridas/{cid}/rota-motorista",
                           headers=cabecalho(passageiro))
    assert resposta.status_code == 409


# ------------------------------------------------------ geometria da malha

def test_info_da_malha_traz_caixa_e_centro():
    dados = cliente.get("/malha/info").json()
    assert dados["nos"] == 1600 and dados["arestas"] > 0
    caixa = dados["caixa"]
    assert caixa["sul"] < caixa["norte"] and caixa["oeste"] < caixa["leste"]
    assert caixa["sul"] <= dados["centro"]["lat"] <= caixa["norte"]


def test_trechos_vem_no_formato_compacto():
    trechos = cliente.get("/malha/trechos").json()["trechos"]
    assert trechos
    for lat1, lon1, lat2, lon2, mao_unica in trechos[:50]:
        assert mao_unica in (0, 1)
        assert (lat1, lon1) != (lat2, lon2)


def test_mao_dupla_nao_e_desenhada_duas_vezes():
    """Emitir os dois sentidos sobreporia a mesma rua no mapa."""
    trechos = cliente.get("/malha/trechos").json()["trechos"]
    vistos = set()
    for lat1, lon1, lat2, lon2, _ in trechos:
        par = frozenset({(lat1, lon1), (lat2, lon2)})
        assert par not in vistos, "trecho repetido em sentido oposto"
        vistos.add(par)


def test_caixa_menor_devolve_menos_trechos():
    todos = cliente.get("/malha/trechos").json()["total"]
    recorte = cliente.get("/malha/trechos", params={
        "sul": -23.54, "norte": -23.53, "oeste": -46.63, "leste": -46.62,
    }).json()["total"]
    assert 0 < recorte < todos


def test_limite_marca_truncado():
    dados = cliente.get("/malha/trechos", params={"limite": 10}).json()
    assert dados["total"] == 10 and dados["truncado"] is True


def test_caixa_vazia_devolve_lista_vazia():
    dados = cliente.get("/malha/trechos", params={
        "sul": 10, "norte": 11, "oeste": 10, "leste": 11,
    }).json()
    assert dados["trechos"] == [] and dados["truncado"] is False



# ------------------------------------------------------ previa da viagem

def estimar(token, comparar=False, origem=ORIGEM, destino=DESTINO):
    return cliente.post("/viagens/estimativa", json={
        "origem_lat": origem[0], "origem_lon": origem[1],
        "destino_lat": destino[0], "destino_lon": destino[1], "comparar": comparar,
    }, headers=cabecalho(token))


def test_estimativa_exige_login():
    assert cliente.post("/viagens/estimativa", json={
        "origem_lat": ORIGEM[0], "origem_lon": ORIGEM[1],
        "destino_lat": DESTINO[0], "destino_lon": DESTINO[1]}).status_code == 401


def test_estimativa_traz_rota_preco_e_oraculo():
    resposta = estimar(novo_passageiro(), comparar=True)
    assert resposta.status_code == 200, resposta.text
    dados = resposta.json()
    assert len(dados["pontos"]) > 2 and dados["segundos"] > 0 and dados["metros"] > 0
    assert dados["custo_estimado"] > 5.0                     # acima da tarifa base
    algoritmo = dados["algoritmo"]
    assert algoritmo["dijkstra"]["mesmo_custo"] is True
    assert (algoritmo["a_estrela"]["nos_expandidos"]
            <= algoritmo["dijkstra"]["nos_expandidos"])


def test_exploracao_traz_a_frente_de_onda_das_duas_buscas():
    """A* descobre menos nos que o Dijkstra, e ambas as ondas partem da
    origem: o primeiro ponto e o cruzamento onde a rota comeca."""
    passageiro = novo_passageiro()
    dados = cliente.post("/viagens/estimativa", json={
        "origem_lat": ORIGEM[0], "origem_lon": ORIGEM[1],
        "destino_lat": DESTINO[0], "destino_lon": DESTINO[1],
        "comparar": True, "explorar": True,
    }, headers=cabecalho(passageiro)).json()
    onda = dados["exploracao"]
    assert 0 < len(onda["a_estrela"]) <= len(onda["dijkstra"])
    inicio = [round(c, 5) for c in dados["pontos"][0]]
    assert onda["a_estrela"][0] == inicio and onda["dijkstra"][0] == inicio


def test_amostragem_comum_preserva_a_proporcao_entre_as_buscas():
    """Amostrar cada onda para o mesmo tamanho apagaria a diferenca entre
    A* e Dijkstra. Com o passo comum, a razao entre elas se mantem."""
    from types import SimpleNamespace

    from dominio.servicos.corrida import passo_comum

    a_estrela = SimpleNamespace(distancias=dict.fromkeys(range(2_000)))
    dijkstra = SimpleNamespace(distancias=dict.fromkeys(range(10_000)))
    passo = passo_comum(a_estrela, dijkstra, maximo=1_000)
    assert passo == 10
    assert len(range(2_000)[::passo]) * 5 == len(range(10_000)[::passo])


def test_exploracao_e_opcional():
    assert "exploracao" not in estimar(novo_passageiro()).json()


def test_estimativa_e_a_mesma_rota_do_pedido():
    """A previa nao pode prometer um preco e o pedido cobrar outro."""
    passageiro = novo_passageiro()
    novo_motorista()
    previa = estimar(passageiro).json()
    corrida = pedir_corrida(passageiro).json()
    assert corrida["custo_estimado"] == previa["custo_estimado"]


def test_estimativa_mostra_motorista_mais_proximo():
    passageiro = novo_passageiro()
    assert estimar(passageiro).json()["motoristas"]["proximos"] == 0
    novo_motorista()
    motoristas = estimar(passageiro).json()["motoristas"]
    assert motoristas["proximos"] == 1 and motoristas["eta_mais_proximo_s"] > 0


def test_ponto_longe_vem_com_distancia_de_ancoragem():
    """Ponto longe e ancorado ao cruzamento mais proximo; a distancia de
    ancoragem vem na resposta para o front avisar."""
    dados = estimar(novo_passageiro(), destino=(-23.60, -46.70)).json()
    assert dados["ancoragem_m"]["destino"] > 1000


# ------------------------------------------------------ busca de lugares

def _geocodificador_falso(lugares):
    """Substitui o Photon: testa recorte e formato sem tocar a rede."""
    from infra import geocodificacao as geo
    original = geo._photon
    geo._photon = lambda texto, caixa, perto, limite: [dict(l) for l in lugares]
    geo._cache = geo._CacheLRU()
    return lambda: setattr(geo, "_photon", original)


def test_busca_de_lugares_exige_login():
    assert cliente.get("/lugares/buscar", params={"q": "masp"}).status_code == 401


def test_busca_descarta_lugar_fora_da_malha():
    dentro = {"id": "N1", "titulo": "Dentro", "detalhe": "", "categoria": "lugar",
              "lat": ORIGEM[0], "lon": ORIGEM[1]}
    fora = dict(dentro, id="N2", titulo="Fora", lat=-22.9, lon=-43.2)   # Rio
    restaurar = _geocodificador_falso([dentro, fora])
    try:
        resposta = cliente.get("/lugares/buscar", params={"q": "lugar"},
                               headers=cabecalho(novo_passageiro()))
    finally:
        restaurar()
    assert resposta.status_code == 200, resposta.text
    assert [l["titulo"] for l in resposta.json()["lugares"]] == ["Dentro"]


def test_busca_fora_do_ar_devolve_503():
    from infra import geocodificacao as geo
    original = geo._photon

    def quebrado(*_args):
        raise OSError("sem rede")

    geo._photon = quebrado
    geo._cache = geo._CacheLRU()
    try:
        resposta = cliente.get("/lugares/buscar", params={"q": "qualquer"},
                               headers=cabecalho(novo_passageiro()))
    finally:
        geo._photon = original
    assert resposta.status_code == 503

# ---------------------------------------------------------------------------

# -------------------------------------------------------------- categorias

def test_estimativa_traz_as_tres_categorias_em_ordem_de_preco():
    dados = estimar(novo_passageiro()).json()
    categorias = dados["categorias"]
    assert [c["id"] for c in categorias] == ["economico", "conforto", "grande"]
    precos = [c["custo"] for c in categorias]
    assert precos == sorted(precos) and precos[0] < precos[-1]
    assert precos[0] == dados["custo_estimado"]          # Economico e o padrao
    assert categorias[2]["lugares"] == 6


def test_corrida_cobra_o_preco_da_categoria_escolhida():
    passageiro = novo_passageiro()
    novo_motorista()
    previa = {c["id"]: c["custo"] for c in estimar(passageiro).json()["categorias"]}
    corrida = pedir_corrida(passageiro, categoria="conforto").json()
    assert abs(corrida["custo_estimado"] - previa["conforto"]) < 0.02, (corrida, previa)


def test_corrida_sem_categoria_cobra_o_economico():
    passageiro = novo_passageiro()
    novo_motorista()
    previa = estimar(passageiro).json()["custo_estimado"]
    corrida = pedir_corrida(passageiro).json()
    assert abs(corrida["custo_estimado"] - previa) < 0.02


def test_categoria_desconhecida_e_recusada():
    passageiro = novo_passageiro()
    novo_motorista()
    assert pedir_corrida(passageiro, categoria="limusine").status_code == 422


def test_cartao_traz_corridas_concluidas_do_motorista():
    passageiro = novo_passageiro()
    novo_motorista()
    primeira = pedir_corrida(passageiro).json()
    assert primeira["motorista_corridas"] == 0
    for acao in ("iniciar", "finalizar"):
        cliente.post(f"/corridas/{primeira['id']}/{acao}", headers=cabecalho(passageiro))
    depois = cliente.get(f"/corridas/{primeira['id']}", headers=cabecalho(passageiro)).json()
    assert depois["motorista_corridas"] == 1


def test_resumo_do_motorista_soma_so_o_que_foi_pago_hoje():
    passageiro = novo_passageiro()
    motorista = novo_motorista()
    assert cliente.get("/motoristas/resumo", headers=cabecalho(motorista)).json() == {
        "ganhos_hoje": 0.0, "corridas_hoje": 0, "corridas_total": 0}
    corrida = pedir_corrida(passageiro).json()
    for acao in ("iniciar", "finalizar"):
        cliente.post(f"/corridas/{corrida['id']}/{acao}", headers=cabecalho(passageiro))
    concluida = cliente.get("/motoristas/resumo", headers=cabecalho(motorista)).json()
    assert concluida["ganhos_hoje"] == 0.0 and concluida["corridas_total"] == 1
    cliente.post(f"/corridas/{corrida['id']}/pagamento", headers=cabecalho(passageiro))
    paga = cliente.get("/motoristas/resumo", headers=cabecalho(motorista)).json()
    assert paga["corridas_hoje"] == 1
    assert abs(paga["ganhos_hoje"] - corrida["custo_estimado"]) < 0.01


def test_resumo_e_exclusivo_de_motorista():
    assert cliente.get("/motoristas/resumo",
                       headers=cabecalho(novo_passageiro())).status_code == 403


def test_inicio_do_dia_segue_o_fuso_de_sao_paulo():
    from datetime import datetime, timezone
    from api.rotas.motoristas import inicio_do_dia_utc
    # 01:30 UTC de 16/11 ainda e 15/11 em Sao Paulo (22:30): o dia comecou
    # as 03:00 UTC de 15/11.
    agora = datetime(2026, 11, 16, 1, 30, tzinfo=timezone.utc)
    assert inicio_do_dia_utc(agora) == datetime(2026, 11, 15, 3, 0)


# -------------------------------------------------------------------- CORS

def _preflight(origem):
    return cliente.options("/auth/login", headers={
        "Origin": origem, "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type"})


def test_cors_aceita_a_origem_exata_mesmo_configurada_com_barra():
    r = _preflight("https://app-teste.vercel.app")
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") == "https://app-teste.vercel.app"


def test_cors_aceita_as_previas_pelo_curinga():
    for origem in ("https://app-teste-git-main-equipe.vercel.app",
                   "https://app-teste-k3j9x2abc-equipe.vercel.app"):
        r = _preflight(origem)
        assert r.status_code == 200, origem
        assert r.headers.get("access-control-allow-origin") == origem


def test_cors_recusa_quem_so_parece_com_o_padrao():
    for origem in ("https://evil.com",
                   "https://app-teste-x-equipe.vercel.app.evil.com",   # sufixo forjado
                   "https://app-teste-x.evil-equipe.vercel.app",       # ponto no curinga
                   "http://app-teste-git-main-equipe.vercel.app",      # sem https
                   "https://outro-app-git-main-equipe.vercel.app"):
        r = _preflight(origem)
        assert "access-control-allow-origin" not in r.headers, origem


def test_separar_origens():
    from infra.config import separar_origens
    exatas, padrao = separar_origens(" https://a.app/ , https://a-*-eq.app ,, ")
    assert exatas == ["https://a.app"]
    assert padrao == r"^(?:https://a\-[a-z0-9-]+\-eq\.app)$"
    assert separar_origens("https://a.app") == (["https://a.app"], None)


# ------------------------------------------------------------------ perfil

def _corrida_concluida(passageiro, motorista_token=None, **extra):
    """Pede e leva uma corrida ate `concluida`. Devolve o json da corrida."""
    if motorista_token is None:
        novo_motorista()
    corrida = pedir_corrida(passageiro, **extra).json()
    for acao in ("iniciar", "finalizar"):
        cliente.post(f"/corridas/{corrida['id']}/{acao}", headers=cabecalho(passageiro))
    return corrida


def test_perfil_comeca_sem_nota_e_aceita_edicao_parcial():
    token = novo_passageiro()
    perfil = cliente.get("/usuarios/eu", headers=cabecalho(token)).json()
    assert perfil["nota"] is None and perfil["avaliacoes"] == 0 and perfil["corridas"] == 0
    r = cliente.patch("/usuarios/eu", json={"telefone": "(11) 98765-4321", "cor_avatar": "#2F8A4C"},
                      headers=cabecalho(token))
    assert r.status_code == 200, r.text
    assert r.json()["telefone"] == "(11) 98765-4321" and r.json()["nome"] == perfil["nome"]
    apagado = cliente.patch("/usuarios/eu", json={"telefone": ""}, headers=cabecalho(token)).json()
    assert apagado["telefone"] is None and apagado["cor_avatar"] == "#2F8A4C"


def test_perfil_recusa_cor_e_telefone_malformados():
    token = novo_passageiro()
    for corpo in ({"cor_avatar": "verde"}, {"cor_avatar": "xx#123456"}, {"telefone": "abc"}):
        assert cliente.patch("/usuarios/eu", json=corpo, headers=cabecalho(token)).status_code == 422


def test_dados_do_carro_sao_so_de_motorista():
    passageiro = novo_passageiro()
    assert cliente.patch("/usuarios/eu", json={"cor_carro": "Prata"},
                         headers=cabecalho(passageiro)).status_code == 422
    motorista = novo_motorista(disponivel=False)
    r = cliente.patch("/usuarios/eu", json={"cor_carro": "Prata", "placa": "abc1d23"},
                      headers=cabecalho(motorista)).json()
    assert r["cor_carro"] == "Prata" and r["placa"] == "ABC1D23"


# ----------------------------------------------------------- locais salvos

def _local(token, **campos):
    corpo = {"tipo": "outro", "titulo": "Lugar", "lat": ORIGEM[0], "lon": ORIGEM[1], **campos}
    return cliente.post("/usuarios/eu/locais", json=corpo, headers=cabecalho(token))


def test_casa_e_unica_e_e_substituida():
    token = novo_passageiro()
    primeira = _local(token, tipo="casa", titulo="Rua A, 1").json()
    segunda = _local(token, tipo="casa", titulo="Rua B, 2").json()
    assert primeira["id"] == segunda["id"] and segunda["rotulo"] == "Casa"
    locais = cliente.get("/usuarios/eu/locais", headers=cabecalho(token)).json()
    assert [l["titulo"] for l in locais] == ["Rua B, 2"]


def test_lista_poe_casa_e_trabalho_antes_dos_favoritos():
    token = novo_passageiro()
    _local(token, titulo="Academia", rotulo="Academia")
    _local(token, tipo="trabalho", titulo="USJT")
    _local(token, tipo="casa", titulo="Casa")
    assert [l["tipo"] for l in cliente.get("/usuarios/eu/locais", headers=cabecalho(token)).json()] \
        == ["casa", "trabalho", "outro"]


def test_nao_se_apaga_local_alheio():
    dono, intruso = novo_passageiro(), novo_passageiro()
    local = _local(dono, titulo="Meu").json()
    assert cliente.delete(f"/usuarios/eu/locais/{local['id']}",
                          headers=cabecalho(intruso)).status_code == 404
    assert cliente.delete(f"/usuarios/eu/locais/{local['id']}",
                          headers=cabecalho(dono)).status_code == 204
    assert cliente.get("/usuarios/eu/locais", headers=cabecalho(dono)).json() == []


# ------------------------------------------------------ pagamento e historico

def test_forma_de_pagamento_e_enderecos_ficam_na_corrida():
    passageiro = novo_passageiro()
    novo_motorista()
    corrida = pedir_corrida(passageiro, forma_pagamento="dinheiro", categoria="grande",
                            origem_texto="Av. Paulista, 1000", destino_texto="Praça da Sé").json()
    assert corrida["forma_pagamento"] == "dinheiro" and corrida["categoria"] == "grande"
    assert corrida["origem_texto"] == "Av. Paulista, 1000"


def test_forma_de_pagamento_desconhecida_e_recusada():
    passageiro = novo_passageiro()
    novo_motorista()
    assert pedir_corrida(passageiro, forma_pagamento="cheque").status_code == 422


def test_historico_traz_so_as_minhas_da_mais_nova_para_a_mais_velha():
    passageiro, outro = novo_passageiro(), novo_passageiro()
    novo_motorista()
    primeira = _corrida_concluida(passageiro, destino_texto="Primeira")
    cliente.post(f"/corridas/{primeira['id']}/pagamento", headers=cabecalho(passageiro))
    _corrida_concluida(outro)
    segunda = _corrida_concluida(passageiro, destino_texto="Segunda")
    itens = cliente.get("/corridas", headers=cabecalho(passageiro)).json()
    assert [i["id"] for i in itens] == [segunda["id"], primeira["id"]]
    assert itens[0]["destino_texto"] == "Segunda" and itens[0]["outro_nome"].startswith("Motorista")
    pagina = cliente.get(f"/corridas?antes_de={segunda['id']}", headers=cabecalho(passageiro)).json()
    assert [i["id"] for i in pagina] == [primeira["id"]], "cursor: so as anteriores"


def test_historico_do_motorista_mostra_o_passageiro():
    passageiro = novo_passageiro()
    motorista = novo_motorista()
    corrida = _corrida_concluida(passageiro, motorista_token=motorista)
    itens = cliente.get("/corridas", headers=cabecalho(motorista)).json()
    assert itens[0]["id"] == corrida["id"] and itens[0]["outro_nome"].startswith("Passageiro")


# ------------------------------------------------------------- avaliacoes

def test_nao_se_avalia_corrida_que_nao_terminou():
    passageiro = novo_passageiro()
    novo_motorista()
    corrida = pedir_corrida(passageiro).json()
    r = cliente.post(f"/corridas/{corrida['id']}/avaliacao", json={"nota": 5},
                     headers=cabecalho(passageiro))
    assert r.status_code == 409


def test_avaliacao_entra_na_media_do_motorista_e_nao_se_repete():
    motorista = novo_motorista()
    notas = []
    for nota in (5, 4):
        passageiro = novo_passageiro()
        corrida = _corrida_concluida(passageiro, motorista_token=motorista)
        r = cliente.post(f"/corridas/{corrida['id']}/avaliacao", json={"nota": nota, "comentario": "ok"},
                         headers=cabecalho(passageiro))
        assert r.status_code == 200, r.text
        assert r.json()["minha_avaliacao"] == nota
        notas.append((passageiro, corrida))
        cliente.post(f"/motoristas/disponibilidade", json={"disponivel": True}, headers=cabecalho(motorista))
    passageiro, corrida = notas[-1]
    repetida = cliente.post(f"/corridas/{corrida['id']}/avaliacao", json={"nota": 1},
                            headers=cabecalho(passageiro))
    assert repetida.status_code == 409
    cartao = cliente.get(f"/corridas/{corrida['id']}", headers=cabecalho(passageiro)).json()
    assert cartao["motorista_nota"] == 4.5 and cartao["motorista_avaliacoes"] == 2


def test_motorista_avalia_o_passageiro():
    passageiro = novo_passageiro()
    motorista = novo_motorista()
    corrida = _corrida_concluida(passageiro, motorista_token=motorista)
    r = cliente.post(f"/corridas/{corrida['id']}/avaliacao", json={"nota": 3},
                     headers=cabecalho(motorista))
    assert r.status_code == 200 and r.json()["passageiro_nota"] == 3.0
    assert cliente.get("/usuarios/eu", headers=cabecalho(passageiro)).json()["nota"] == 3.0


def test_nota_fora_de_1_a_5_e_recusada():
    passageiro = novo_passageiro()
    corrida = _corrida_concluida(passageiro)
    for nota in (0, 6):
        assert cliente.post(f"/corridas/{corrida['id']}/avaliacao", json={"nota": nota},
                            headers=cabecalho(passageiro)).status_code == 422


# ----------------------------------------------------------------- paradas

PARADA_1 = (-23.5290, -46.6190)
PARADA_2 = (-23.5260, -46.6150)


def _estimar_com(token, paradas=(), origem=ORIGEM, destino=DESTINO):
    return cliente.post("/viagens/estimativa", json={
        "origem_lat": origem[0], "origem_lon": origem[1],
        "destino_lat": destino[0], "destino_lon": destino[1], "comparar": True,
        "paradas": [{"lat": lat, "lon": lon} for lat, lon in paradas],
    }, headers=cabecalho(token))


def test_rota_com_paradas_e_a_soma_dos_trechos():
    """Com ordem fixa, o minimo e a soma dos minimos de cada trecho."""
    token = novo_passageiro()
    total = _estimar_com(token, [PARADA_1, PARADA_2]).json()
    trechos = [_estimar_com(token, origem=a, destino=b).json()["segundos"]
               for a, b in ((ORIGEM, PARADA_1), (PARADA_1, PARADA_2), (PARADA_2, DESTINO))]
    assert abs(total["segundos"] - sum(trechos)) < 1e-6
    assert total["algoritmo"]["trechos"] == 3 and len(total["paradas"]) == 2
    assert total["algoritmo"]["dijkstra"]["mesmo_custo"] is True, "o oraculo confere cada trecho"
    direto = _estimar_com(token).json()
    assert total["segundos"] >= direto["segundos"] - 1e-6, "parada nunca encurta a viagem"


def test_no_maximo_tres_paradas():
    token = novo_passageiro()
    assert _estimar_com(token, [PARADA_1] * 4).status_code == 422


def test_corrida_com_paradas_guarda_a_ordem_e_passa_por_elas():
    passageiro = novo_passageiro()
    novo_motorista()
    sem = pedir_corrida(passageiro).json()
    cliente.post(f"/corridas/{sem['id']}/cancelar", headers=cabecalho(passageiro))
    novo_motorista()
    corrida = pedir_corrida(passageiro, paradas=[
        {"lat": PARADA_2[0], "lon": PARADA_2[1], "texto": "Padaria"},
        {"lat": PARADA_1[0], "lon": PARADA_1[1], "texto": "Farmácia"}]).json()
    assert [p["texto"] for p in corrida["paradas"]] == ["Padaria", "Farmácia"]
    assert corrida["custo_estimado"] > sem["custo_estimado"]
    rota = cliente.get(f"/corridas/{corrida['id']}/rota", headers=cabecalho(passageiro)).json()
    estimativa = _estimar_com(passageiro, [PARADA_2, PARADA_1]).json()
    assert abs(rota["segundos"] - estimativa["segundos"]) < 1e-6, "rota e previa sao o mesmo calculo"


# -------------------------------------------------------------------- chat

def test_chat_entre_passageiro_e_motorista():
    passageiro = novo_passageiro()
    motorista = novo_motorista()
    corrida = pedir_corrida(passageiro).json()
    for token, texto in ((passageiro, "Estou de camiseta azul"), (motorista, "Chego em 2 min")):
        r = cliente.post(f"/corridas/{corrida['id']}/mensagens", json={"texto": texto}, headers=cabecalho(token))
        assert r.status_code == 201, r.text
    lidas = cliente.get(f"/corridas/{corrida['id']}/mensagens", headers=cabecalho(motorista)).json()
    assert [m["texto"] for m in lidas] == ["Estou de camiseta azul", "Chego em 2 min"]


def test_chat_e_so_de_quem_esta_na_corrida():
    passageiro, intruso = novo_passageiro(), novo_passageiro()
    novo_motorista()
    corrida = pedir_corrida(passageiro).json()
    r = cliente.post(f"/corridas/{corrida['id']}/mensagens", json={"texto": "oi"}, headers=cabecalho(intruso))
    assert r.status_code == 403
    assert cliente.get(f"/corridas/{corrida['id']}/mensagens", headers=cabecalho(intruso)).status_code == 403


def test_chat_fecha_quando_a_corrida_termina_e_recusa_vazio():
    passageiro = novo_passageiro()
    corrida = _corrida_concluida(passageiro)
    assert cliente.post(f"/corridas/{corrida['id']}/mensagens", json={"texto": "oi"},
                        headers=cabecalho(passageiro)).status_code == 409
    passageiro2 = novo_passageiro()
    novo_motorista()
    outra = pedir_corrida(passageiro2).json()
    assert cliente.post(f"/corridas/{outra['id']}/mensagens", json={"texto": "   "},
                        headers=cabecalho(passageiro2)).status_code == 422


# ------------------------------------------------------------ compartilhar

def test_link_publico_mostra_so_o_minimo_e_sem_login():
    passageiro = novo_passageiro()
    novo_motorista()
    corrida = pedir_corrida(passageiro, destino_texto="Praça da Sé").json()
    assert corrida["token_compartilhar"] is None
    token = cliente.post(f"/corridas/{corrida['id']}/compartilhar",
                         headers=cabecalho(passageiro)).json()["token_compartilhar"]
    de_novo = cliente.post(f"/corridas/{corrida['id']}/compartilhar",
                           headers=cabecalho(passageiro)).json()["token_compartilhar"]
    assert token and len(token) >= 16 and token == de_novo, "compartilhar duas vezes da o mesmo link"
    publico = cliente.get(f"/publico/acompanhar/{token}")          # sem cabecalho de login
    assert publico.status_code == 200, publico.text
    dados = publico.json()
    assert dados["ativa"] and dados["destino_texto"] == "Praça da Sé"
    assert dados["passageiro"] == "Passageiro", "so o primeiro nome"
    assert dados["posicao_motorista"] is not None and len(dados["pontos"]) > 1
    assert "@" not in publico.text, "nenhum email pode vazar no link publico"


def test_link_encerrado_para_de_mostrar_posicao():
    passageiro = novo_passageiro()
    novo_motorista()
    corrida = pedir_corrida(passageiro).json()
    token = cliente.post(f"/corridas/{corrida['id']}/compartilhar",
                         headers=cabecalho(passageiro)).json()["token_compartilhar"]
    for acao in ("iniciar", "finalizar", "pagamento"):
        cliente.post(f"/corridas/{corrida['id']}/{acao}", headers=cabecalho(passageiro))
    dados = cliente.get(f"/publico/acompanhar/{token}").json()
    assert dados["estado"] == "paga" and not dados["ativa"]
    assert dados["posicao_motorista"] is None and dados["pontos"] == []


def test_so_o_passageiro_compartilha_e_token_falso_da_404():
    passageiro = novo_passageiro()
    motorista = novo_motorista()
    corrida = pedir_corrida(passageiro).json()
    assert cliente.post(f"/corridas/{corrida['id']}/compartilhar",
                        headers=cabecalho(motorista)).status_code == 403
    cliente.post(f"/corridas/{corrida['id']}/compartilhar", headers=cabecalho(passageiro))
    visto_pelo_motorista = cliente.get(f"/corridas/{corrida['id']}", headers=cabecalho(motorista)).json()
    assert visto_pelo_motorista["token_compartilhar"] is None
    for falso in ("abc", "x" * 22):
        assert cliente.get(f"/publico/acompanhar/{falso}").status_code == 404


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
    # No Windows o arquivo segue aberto enquanto o pool do engine existir.
    from infra.banco import engine
    engine.dispose()
    os.unlink(_BANCO.name)
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
