# -*- coding: utf-8 -*-
"""Teste ponta a ponta do front-end contra o backend real.

Dois navegadores simultaneos -- um motorista e um passageiro -- percorrendo o
ciclo completo da corrida pela interface, com capturas de tela a cada etapa.

PRE-REQUISITOS
    pip install playwright && playwright install chromium

    Backend e front no ar, com banco LIMPO:
        rm -f e2e.db
        JWT_SECRET=teste MALHA_ARQUIVO=__x__ DATABASE_URL=sqlite:///./e2e.db \
            uvicorn --app-dir backend api.main:app --port 8000
        cd frontend/web && npm run dev

    O banco limpo nao e detalhe: motoristas online de execucoes anteriores
    competem no pareamento, e o teste fica instavel.

USO
    python3 frontend/web/e2e/fluxo.py

    E2E_BASE     URL do front (padrao http://127.0.0.1:5173)
    E2E_SAIDA    pasta das capturas (padrao frontend/web/e2e/capturas)
    CHROMIUM     caminho do executavel, se nao usar o do Playwright
"""
import os, sys, time
from playwright.sync_api import sync_playwright

BASE = os.environ.get("E2E_BASE", "http://127.0.0.1:5173")
SAIDA = os.environ.get("E2E_SAIDA", os.path.join(os.path.dirname(__file__), "capturas"))
os.makedirs(SAIDA, exist_ok=True)
SELO = int(time.time())
falhas = []


def checar(condicao, descricao):
    print(f"  {'ok   ' if condicao else 'FALHA'} {descricao}")
    if not condicao:
        falhas.append(descricao)


def registrar(pagina, tipo, nome, email, placa=None):
    pagina.goto(BASE, wait_until="networkidle")
    pagina.get_by_role("button", name="Criar agora").click()
    pagina.select_option("#tipo", tipo)
    pagina.fill("#nome", nome)
    pagina.fill("#email", email)
    pagina.fill("#senha", "senha-forte-123")
    if placa:
        pagina.fill("#placa", placa)
    pagina.get_by_role("button", name="Criar conta").click()
    pagina.wait_for_selector(".barra-topo", timeout=15000)


def clicar_mapa(pagina, dx=0, dy=0):
    """Clica no mapa, deslocado do centro em pixels."""
    caixa = pagina.locator(".leaflet-container").bounding_box()
    pagina.mouse.click(caixa["x"] + caixa["width"] / 2 + dx,
                       caixa["y"] + caixa["height"] / 2 + dy)
    pagina.wait_for_timeout(500)


with sync_playwright() as pw:
    # CHROMIUM opcional: use quando o navegador ja estiver instalado em outro
    # caminho. Sem a variavel, o Playwright usa o proprio.
    executavel = os.environ.get("CHROMIUM")
    navegador = pw.chromium.launch(
        **({"executable_path": executavel} if executavel else {}),
        args=["--no-sandbox", "--disable-dev-shm-usage"])
    erros_js = []

    ctx_m = navegador.new_context(viewport={"width": 1280, "height": 800})
    ctx_p = navegador.new_context(viewport={"width": 1280, "height": 800})
    motorista = ctx_m.new_page()
    passageiro = ctx_p.new_page()
    for pg in (motorista, passageiro):
        pg.on("pageerror", lambda e: erros_js.append(str(e)))

    print("\n== 1. tela de autenticacao ==")
    passageiro.goto(BASE, wait_until="networkidle")
    checar(passageiro.locator(".marca").first.is_visible(), "marca TrueCompass visivel")
    checar("caminho certo" in passageiro.content(), "subtitulo do produto presente")
    checar(passageiro.locator("svg.bussola").count() > 0, "bussola desenhada na entrada")
    passageiro.screenshot(path=f"{SAIDA}/01-login.png")

    print("\n== 2. motorista entra, marca posicao e fica online ==")
    registrar(motorista, "motorista", "Motorista Teste",
              f"m{SELO}@usjt.br", placa="ABC1D23")
    checar(motorista.locator(".leaflet-container").is_visible(), "mapa carregou")
    motorista.wait_for_timeout(1500)
    # A malha inteira sai em DUAS camadas multi-segmento, nao uma por rua --
    # entao conta-se o tamanho do atributo "d", e nao o numero de <path>.
    tamanhos = motorista.eval_on_selector_all(
        ".leaflet-overlay-pane path",
        "els => els.map(e => (e.getAttribute('d')||'').length)")
    checar(max(tamanhos or [0]) > 2000,
           f"malha viaria desenhada a partir da API (maior path: {max(tamanhos or [0])} chars)")
    clicar_mapa(motorista, 0, 0)
    checar("offline" in motorista.locator(".selo").last.inner_text().lower(),
           "motorista comeca offline")
    motorista.get_by_role("button", name="Ficar online").click()
    motorista.wait_for_timeout(800)
    checar("disponível" in motorista.content(), "motorista ficou disponivel")
    motorista.screenshot(path=f"{SAIDA}/02-motorista-online.png")

    print("\n== 3. passageiro pede corrida ==")
    registrar(passageiro, "passageiro", "Passageiro Teste", f"p{SELO}@usjt.br")
    passageiro.wait_for_timeout(1500)
    checar("ORIGEM" in passageiro.locator(".dica-mapa").inner_text(),
           "dica pede para marcar origem")
    clicar_mapa(passageiro, 12, 12)
    checar("DESTINO" in passageiro.locator(".dica-mapa").inner_text(),
           "dica passa a pedir destino")
    clicar_mapa(passageiro, 170, -140)
    # A bussola calcula o azimute inicial entre origem e destino. Com os dois
    # pontos marcados ela precisa sair de "sem destino" e mostrar um rumo.
    import re as _re
    leitura = passageiro.locator(".bussola-rumo").inner_text()
    casa = _re.match(r"^(\d{1,3})°\s*(N|NE|L|SE|S|SO|O|NO)$", leitura.strip())
    checar(casa is not None, f"bussola mostra rumo e ponto cardinal ({leitura!r})")
    if casa:
        graus = int(casa.group(1))
        checar(0 <= graus <= 360, f"rumo dentro da faixa valida ({graus}°)")
    passageiro.screenshot(path=f"{SAIDA}/03-origem-destino.png")

    passageiro.get_by_role("button", name="Pedir corrida").click()
    passageiro.wait_for_selector(".linha-estados", timeout=20000)
    passageiro.wait_for_timeout(2000)

    conteudo = passageiro.content()
    checar("Motorista chega em" in conteudo, "ETA exibido")
    checar("Valor estimado" in conteudo, "valor estimado exibido")
    checar(passageiro.locator(".etapa.atual .etapa-nome").inner_text() == "Rota calculada",
           "linha de estados aponta 'Rota calculada'")
    # inner_text() respeita text-transform: uppercase, entao compara-se sem caixa.
    checar("conectado" in passageiro.locator(".selo.ativo").last.inner_text().lower(),
           "WebSocket conectado")
    tamanhos_p = passageiro.eval_on_selector_all(
        ".leaflet-overlay-pane path",
        "els => els.map(e => (e.getAttribute('d')||'').length)")
    checar(len([t for t in tamanhos_p if t > 30]) >= 3,
           "rota e marcadores desenhados sobre a malha")
    passageiro.screenshot(path=f"{SAIDA}/04-corrida-alocada.png")

    print("\n== 4. motorista se desloca; passageiro ve pelo WebSocket ==")
    # A batida de GPS roda a cada 4s: e por ela que o motorista descobre a corrida.
    try:
        motorista.wait_for_selector("text=Corrida #", timeout=15000)
    except Exception:
        print("\n  !! O motorista deste teste nao recebeu a corrida.")
        print("     Causa quase certa: o BANCO NAO ESTAVA LIMPO. Motoristas")
        print("     online de execucoes anteriores competem no pareamento e,")
        print("     estando mais perto, vencem -- comportamento correto do app.")
        print("     Pare o servidor, apague o banco e suba de novo:")
        print("         rm -f e2e.db && uvicorn api.main:app --port 8000\n")
        falhas.append("motorista recebeu a corrida (banco sujo?)")
        navegador.close()
        sys.exit(1)
    checar("Corrida #" in motorista.content(), "motorista recebeu a corrida")
    motorista.get_by_role("button", name="Simular deslocamento").click()
    motorista.wait_for_timeout(4000)
    registro = passageiro.locator(".registro-eventos").inner_text()
    checar("gps" in registro.lower(),
           f"passageiro recebeu pings de GPS em tempo real ({registro.splitlines()[:1]})")
    motorista.screenshot(path=f"{SAIDA}/05-motorista-deslocando.png")
    passageiro.screenshot(path=f"{SAIDA}/06-passageiro-gps-ao-vivo.png")
    # A simulacao pode ter TERMINADO sozinha: num trajeto curto os passos
    # acabam antes da espera acima, e o botao volta a "Simular deslocamento".
    parar = motorista.get_by_role("button", name="Parar deslocamento")
    if parar.count() > 0:
        parar.click()
    else:
        print("       (simulacao concluiu sozinha -- trajeto curto)")

    print("\n== 5. ciclo completo pela interface ==")
    passageiro.get_by_role("button", name="Embarquei").click()
    passageiro.wait_for_timeout(1200)
    checar(passageiro.locator(".etapa.atual .etapa-nome").inner_text()
           == "Corrida em andamento", "estado avancou para em_curso")

    passageiro.get_by_role("button", name="Cheguei ao destino").click()
    passageiro.wait_for_timeout(1200)
    checar(passageiro.locator(".etapa.atual .etapa-nome").inner_text()
           == "Corrida concluída", "estado avancou para concluida")
    passageiro.screenshot(path=f"{SAIDA}/07-concluida.png")

    passageiro.get_by_role("button", name="Pagar").click()
    passageiro.wait_for_timeout(1500)
    checar(passageiro.locator(".etapa.atual .etapa-nome").inner_text()
           == "Pagamento liberado", "pagamento processado")
    checar("Começar outra corrida" in passageiro.content(),
           "oferece nova corrida apos encerrar")
    passageiro.screenshot(path=f"{SAIDA}/08-paga.png")

    print("\n== 6. tema claro ==")
    passageiro.locator(".interruptor-tema").first.click()
    passageiro.wait_for_timeout(700)
    checar(passageiro.evaluate("document.documentElement.dataset.tema") == "claro",
           "tema claro aplicado")
    passageiro.screenshot(path=f"{SAIDA}/09-tema-claro.png")

    print("\n== 7. sem erro de javascript ==")
    checar(not erros_js, f"nenhum erro no console (vistos: {erros_js[:2]})")

    navegador.close()

print(f"\n{'='*52}")
if falhas:
    print(f"{len(falhas)} FALHA(S):")
    for f in falhas:
        print(f"  - {f}")
    sys.exit(1)
print("todas as verificacoes passaram")
