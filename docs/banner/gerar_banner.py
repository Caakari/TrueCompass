# -*- coding: utf-8 -*-
"""Gera o banner do TrueCompass em PDF, no tamanho exato de impressão.

    90 cm de largura x 120 cm de altura, retrato.

Tipografia conforme a especificação da disciplina:
    título 80 pt · títulos de seção 40 pt · corpo e bullets 21 a 25 pt
    (o mínimo de 20 pt é respeitado em todo o banner, legendas inclusive).

Fontes: Montserrat, em `fontes/`; na falta dela, Liberation Sans, que é
metricamente compatível com a Arial — as duas são permitidas.

Uso:
    python3 docs/banner/gerar_banner.py              # gera banner_truecompass.pdf
    python3 docs/banner/gerar_banner.py --previa     # e exporta um PNG de prova

Os números impressos saem das medições do próprio repositório
(`matematica/algoritmos/demo.py` e `backend/infra/preparar_alt.py`). Se uma
medição mudar, atualize MEDIDAS, logo abaixo — e só ali.
"""
from __future__ import annotations

import math
import os
import sys

from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as pdfcanvas

AQUI = os.path.dirname(os.path.abspath(__file__))
CAPTURAS = os.path.join(AQUI, "capturas")
SAIDA = os.path.join(AQUI, "banner_truecompass.pdf")

LARGURA, ALTURA = 90 * cm, 120 * cm


# ----------------------------------------------------------------- tipografia
def _registrar_fontes() -> tuple[str, str, str, str]:
    pasta = os.path.join(AQUI, "fontes")
    pesos = {"400": "Banner", "600": "Banner-Semi", "700": "Banner-Bold", "800": "Banner-Black"}
    if all(os.path.exists(os.path.join(pasta, f"Montserrat-{p}.ttf")) for p in pesos):
        for peso, nome in pesos.items():
            pdfmetrics.registerFont(TTFont(nome, os.path.join(pasta, f"Montserrat-{peso}.ttf")))
        return "Banner", "Banner-Semi", "Banner-Bold", "Banner-Black"

    liberation = "/usr/share/fonts/truetype/liberation"
    if os.path.exists(os.path.join(liberation, "LiberationSans-Regular.ttf")):
        pdfmetrics.registerFont(TTFont("Banner", f"{liberation}/LiberationSans-Regular.ttf"))
        pdfmetrics.registerFont(TTFont("Banner-Bold", f"{liberation}/LiberationSans-Bold.ttf"))
        print("aviso: Montserrat ausente — usando Liberation Sans (métrica da Arial).")
        return "Banner", "Banner-Bold", "Banner-Bold", "Banner-Bold"

    print("aviso: nenhuma TTF encontrada — usando Helvetica (métrica da Arial).")
    return "Helvetica", "Helvetica-Bold", "Helvetica-Bold", "Helvetica-Bold"


REG, SEMI, BOLD, BLACK = _registrar_fontes()
MONO = "Courier-Bold"


# Caractere fora da fonte sai BRANCO no PDF, sem erro nenhum. A Montserrat do
# Google vem no subconjunto "latin", sem setas nem símbolos matemáticos — por
# isso todo texto desenhado passa por esta conferência.
def _glifos_da_fonte() -> set[int] | None:
    caminho = os.path.join(AQUI, "fontes", "Montserrat-400.ttf")
    if not os.path.exists(caminho):
        return None
    try:
        from fontTools.ttLib import TTFont as _TT
        return set(_TT(caminho).getBestCmap())
    except ImportError:
        return None


GLIFOS = _glifos_da_fonte()
SEM_GLIFO: set[str] = set()


def _conferir(txto: str) -> str:
    if GLIFOS is not None:
        SEM_GLIFO.update(ch for ch in txto if ord(ch) not in GLIFOS and ch != "\n")
    return txto


# --------------------------------------------------------------------- paleta
PAPEL = (0.965, 0.961, 0.949)
TINTA = (0.063, 0.071, 0.078)
SUAVE = (0.396, 0.420, 0.443)
FRACO = (0.580, 0.600, 0.616)
ACO = (0.169, 0.188, 0.208)
VERDE = (0.157, 0.482, 0.298)
VERDE_CLARO = (0.392, 0.675, 0.463)
VERMELHO = (0.800, 0.220, 0.267)
LATAO = (0.667, 0.510, 0.251)
ESCURO = (0.051, 0.059, 0.067)
GRAFITE = (0.110, 0.125, 0.137)
CARTAO = (1, 1, 1)
LINHA = (0.882, 0.878, 0.859)
TRILHO = (0.914, 0.910, 0.894)
SOMBRA = (0.898, 0.894, 0.875)

# ------------------------------------------------------------------- medições
MEDIDAS = {
    "nos": "118.267", "arestas": "180.424", "semaforos": "3.542",
    "dijkstra_nos": 1_703_955, "haversine_nos": 1_329_866, "alt_nos": 119_398,
    "haversine_ms": 172, "alt_ms": 14,
    "testes": 183, "e2e": 20,
}
REPO = "https://github.com/Cm-Kauan/Prototipo-TrueCompass"

# ------------------------------------------------------------------ utilidades
c = pdfcanvas.Canvas(SAIDA, pagesize=(LARGURA, ALTURA))
c.setTitle("TrueCompass — banner do projeto")
c.setAuthor("Squad TrueCompass — Universidade São Judas Tadeu")


def larg(txto: str, fonte: str, tam: float) -> float:
    return pdfmetrics.stringWidth(txto, fonte, tam)


def quebrar(txto: str, fonte: str, tam: float, largura: float) -> list[str]:
    linhas: list[str] = []
    for bloco in txto.split("\n"):
        atual = ""
        for palavra in bloco.split(" "):
            teste = palavra if not atual else f"{atual} {palavra}"
            if larg(teste, fonte, tam) <= largura or not atual:
                atual = teste
            else:
                linhas.append(atual)
                atual = palavra
        linhas.append(atual)
    return linhas


def texto(x, y, txto, fonte=REG, tam=24, cor=TINTA, alinhar="esq", espaco=0.0):
    """Escreve uma linha. `espaco` abre as letras (só o objeto de texto do
    ReportLab sabe fazer isso, e aí o alinhamento tem de considerar a abertura)."""
    txto = _conferir(txto)
    c.setFont(fonte, tam)
    c.setFillColorRGB(*cor)
    if not espaco:
        {"centro": c.drawCentredString, "dir": c.drawRightString}.get(alinhar, c.drawString)(
            x, y, txto)
        return
    l = larg(txto, fonte, tam) + espaco * max(len(txto) - 1, 0)
    x = x - l / 2 if alinhar == "centro" else x - l if alinhar == "dir" else x
    obj = c.beginText(x, y)
    obj.setFont(fonte, tam)
    obj.setFillColorRGB(*cor)
    obj.setCharSpace(espaco)
    obj.textOut(txto)
    # Tc é estado de texto do PDF: persiste depois do BT/ET e alargaria TODO o
    # resto da página. Zerar aqui, depois de mostrar o texto, é obrigatório.
    obj.setCharSpace(0)
    c.drawText(obj)


def paragrafo(x, y, txto, largura, fonte=REG, tam=24, cor=TINTA, entrelinha=1.40) -> float:
    c.setFont(fonte, tam)
    c.setFillColorRGB(*cor)
    for linha in quebrar(_conferir(txto), fonte, tam, largura):
        c.drawString(x, y, linha)
        y -= tam * entrelinha
    return y + tam * entrelinha


def alt_paragrafo(txto, largura, fonte=REG, tam=24, entrelinha=1.40) -> float:
    return len(quebrar(txto, fonte, tam, largura)) * tam * entrelinha


def cartao(x, y, l, a, fundo=CARTAO, borda=LINHA, raio=0.6 * cm, sombra=True):
    """Cartão com sombra deslocada — o bloco de base do layout."""
    if sombra:
        c.setFillColorRGB(*SOMBRA)
        c.roundRect(x + 0.16 * cm, y - a - 0.16 * cm, l, a, raio, stroke=0, fill=1)
    c.setFillColorRGB(*fundo)
    if borda:
        c.setStrokeColorRGB(*borda)
        c.setLineWidth(1.8)
    c.roundRect(x, y - a, l, a, raio, stroke=1 if borda else 0, fill=1)


def faixa_lateral(x, y, a, cor, l=0.32 * cm):
    c.setFillColorRGB(*cor)
    c.roundRect(x, y - a, l * 3, a, l, stroke=0, fill=1)
    c.setFillColorRGB(*CARTAO)
    c.rect(x + l, y - a, l * 2, a, stroke=0, fill=1)


def secao(x, y, etiqueta, titulo, cor, largura) -> float:
    """Cabeçalho de seção: ponto + etiqueta pequena, título grande, filete fino."""
    c.setFillColorRGB(*cor)
    c.circle(x + 0.3 * cm, y - 0.28 * cm, 0.3 * cm, stroke=0, fill=1)
    texto(x + 1.05 * cm, y - 0.5 * cm, etiqueta.upper(), BLACK, 21, cor, espaco=2.2)
    texto(x, y - 2.35 * cm, titulo, BLACK, 40, TINTA)
    c.setStrokeColorRGB(*LINHA)
    c.setLineWidth(2)
    c.line(x, y - 2.95 * cm, x + largura, y - 2.95 * cm)
    return y - 3.6 * cm


def seta(x1, y1, x2, y2, cor=FRACO, espessura=3.0, cabeca=0.38 * cm):
    c.setStrokeColorRGB(*cor)
    c.setLineWidth(espessura)
    c.setLineCap(1)
    c.line(x1, y1, x2, y2)
    ang = math.atan2(y2 - y1, x2 - x1)
    c.setFillColorRGB(*cor)
    p = c.beginPath()
    p.moveTo(x2, y2)
    p.lineTo(x2 - cabeca * math.cos(ang - 0.42), y2 - cabeca * math.sin(ang - 0.42))
    p.lineTo(x2 - cabeca * math.cos(ang + 0.42), y2 - cabeca * math.sin(ang + 0.42))
    p.close()
    c.drawPath(p, stroke=0, fill=1)


def bussola(cx, cy, r, aro=(1, 1, 1), norte=VERMELHO, sul=(0.70, 0.71, 0.70)):
    c.setStrokeColorRGB(*aro)
    c.setLineWidth(r * 0.075)
    c.circle(cx, cy, r, stroke=1, fill=0)
    c.setLineWidth(r * 0.045)
    for i in range(12):
        a = math.pi / 6 * i
        c.line(cx + r * 0.80 * math.sin(a), cy + r * 0.80 * math.cos(a),
               cx + r * 0.94 * math.sin(a), cy + r * 0.94 * math.cos(a))
    for alvo, cor in (((0, r * 0.72), norte), ((0, -r * 0.72), sul)):
        p = c.beginPath()
        p.moveTo(cx + alvo[0], cy + alvo[1])
        p.lineTo(cx + r * 0.19, cy)
        p.lineTo(cx - r * 0.19, cy)
        p.close()
        c.setFillColorRGB(*cor)
        c.drawPath(p, stroke=0, fill=1)


def celular(arquivo, x, y, largura) -> float:
    """Captura dentro de uma moldura de aparelho, com os cantos arredondados."""
    img = ImageReader(os.path.join(CAPTURAS, arquivo))
    pw, ph = img.getSize()
    a = largura * ph / pw
    raio = largura * 0.09
    c.saveState()
    c.setFillColorRGB(*SOMBRA)
    c.roundRect(x + 0.14 * cm, y - a - 0.14 * cm, largura, a, raio, stroke=0, fill=1)
    p = c.beginPath()
    p.roundRect(x, y - a, largura, a, raio)
    c.clipPath(p, stroke=0, fill=0)
    c.drawImage(img, x, y - a, largura, a, mask=None)
    c.restoreState()
    c.setStrokeColorRGB(*GRAFITE)
    c.setLineWidth(3.2)
    c.roundRect(x, y - a, largura, a, raio, stroke=1, fill=0)
    return y - a


# ======================================================================= fundo
c.setFillColorRGB(*PAPEL)
c.rect(0, 0, LARGURA, ALTURA, stroke=0, fill=1)

MARGEM = 4 * cm
UTIL = LARGURA - 2 * MARGEM
COL_L = 26 * cm
COLS = [MARGEM, MARGEM + 28 * cm, MARGEM + 56 * cm]

BANDA_ALT = 22.2 * cm
BANDA_BASE = ALTURA - BANDA_ALT
Y_COL = BANDA_BASE - 3.0 * cm
RODAPE_TOPO = 21.6 * cm
RODAPE_BASE = 3.8 * cm

# =================================================================== cabeçalho
c.setFillColorRGB(*ESCURO)
c.rect(0, BANDA_BASE, LARGURA, BANDA_ALT, stroke=0, fill=1)

# marca d'água: a rosa dos ventos, discreta, atrás do título
c.saveState()
# sem recorte, os arcos vazariam da faixa escura e apareceriam como riscos
# cinzentos sobre o papel claro das colunas
recorte = c.beginPath()
recorte.rect(0, BANDA_BASE, LARGURA, BANDA_ALT)
c.clipPath(recorte, stroke=0, fill=0)
c.setStrokeColorRGB(0.098, 0.110, 0.122)
for raio in (9.5 * cm, 13.5 * cm, 17.5 * cm):
    c.setLineWidth(2.4)
    c.circle(LARGURA / 2, ALTURA - 10.4 * cm, raio, stroke=1, fill=0)
for i in range(8):
    a = math.pi / 4 * i
    c.setLineWidth(2.0)
    c.line(LARGURA / 2 + 6.0 * cm * math.sin(a), ALTURA - 10.4 * cm + 6.0 * cm * math.cos(a),
           LARGURA / 2 + 17.5 * cm * math.sin(a), ALTURA - 10.4 * cm + 17.5 * cm * math.cos(a))
c.restoreState()

for i, cor in enumerate((VERDE, VERDE_CLARO, LATAO, VERMELHO)):
    c.setFillColorRGB(*cor)
    c.rect(i * LARGURA / 4, BANDA_BASE, LARGURA / 4, 0.42 * cm, stroke=0, fill=1)

for lx, rotulo in ((MARGEM, "LOGOTIPO DA UNIVERSIDADE"),
                   (LARGURA - MARGEM - 15.5 * cm, "LOGOTIPO DO CURSO")):
    c.setStrokeColorRGB(0.231, 0.251, 0.267)
    c.setLineWidth(2.0)
    c.setDash(7, 7)
    c.roundRect(lx, ALTURA - 5.8 * cm, 15.5 * cm, 3.4 * cm, 0.3 * cm, stroke=1, fill=0)
    c.setDash()
    texto(lx + 7.75 * cm, ALTURA - 4.3 * cm, rotulo, SEMI, 21, (0.376, 0.400, 0.416), "centro")

et = "APLICATIVO DE MOBILIDADE URBANA"
lw_et = larg(et, BLACK, 22) + 2.4 * len(et) + 2.6 * cm
c.setStrokeColorRGB(*VERDE_CLARO)
c.setLineWidth(2.2)
c.roundRect((LARGURA - lw_et) / 2, ALTURA - 7.9 * cm, lw_et, 1.5 * cm, 0.75 * cm, stroke=1, fill=0)
texto(LARGURA / 2, ALTURA - 7.42 * cm, et, BLACK, 22, VERDE_CLARO, "centro", espaco=2.4)

TITULO = "TrueCompass"
lt = larg(TITULO, BLACK, 80)
conjunto = 2.3 * cm * 2 + 1.4 * cm + lt
x0 = (LARGURA - conjunto) / 2
bussola(x0 + 2.3 * cm, ALTURA - 10.4 * cm, 2.3 * cm)
texto(x0 + 2.3 * cm * 2 + 1.4 * cm, ALTURA - 11.35 * cm, TITULO, BLACK, 80, (1, 1, 1))

SUB = ("Alocação ótima de motoristas e rota de menor tempo sobre a malha viária real de "
       "São Paulo, com corretude demonstrada e ganho medido")
y = ALTURA - 13.9 * cm
for linha in quebrar(SUB, SEMI, 38, 70 * cm):
    texto(LARGURA / 2, y, linha, SEMI, 38, VERDE_CLARO, "centro")
    y -= 1.55 * cm

c.setStrokeColorRGB(0.153, 0.169, 0.188)
c.setLineWidth(2)
c.line(MARGEM + 6 * cm, ALTURA - 16.4 * cm, LARGURA - MARGEM - 6 * cm, ALTURA - 16.4 * cm)

y = ALTURA - 17.7 * cm
for linha in [
    "Bianca Murcela Mascamudo · RA 8261104797      Carolina Chaves · RA 826182449      "
    "Carolina Yukari Kague · RA 8261110898",
    "Gabryela Araujo · RA 826199094      Kauan Sousa · RA 8261113181      "
    "Wildiner Lopes · RA 8261102715",
]:
    texto(LARGURA / 2, y, linha, REG, 25, (0.835, 0.843, 0.839), "centro")
    y -= 1.4 * cm

texto(LARGURA / 2, ALTURA - 20.3 * cm, "Orientador:  Prof. Raulison Resende", SEMI, 27,
      (1, 1, 1), "centro")
texto(LARGURA / 2, ALTURA - 21.2 * cm,
      "Universidade São Judas Tadeu  ·  Matemática Computacional Aplicada (0064481)  ·  "
      "Campus ____________  ·  2026/2", SEMI, 24, (0.769, 0.639, 0.420), "centro")

# ================================================================== COLUNA 1
x, y = COLS[0], Y_COL
y = secao(x, y, "o produto", "O aplicativo", VERDE, COL_L)

RECURSOS = [
    ("Pedir a corrida", "origem pelo GPS ou escolhida no mapa; destino por busca de endereço."),
    ("Achar quem chega antes", "não o mais perto em linha reta, e sim o de menor tempo real pelas ruas."),
    ("Acompanhar ao vivo", "o carro anda no mapa e o estado da corrida chega por WebSocket."),
    ("Pagar só no fim", "o pagamento só existe depois de concluída — o fluxo não deixa pular etapa."),
]
for titulo, nota in RECURSOS:
    a_i = 1.0 * cm + alt_paragrafo(nota, COL_L - 3.6 * cm, REG, 23) + 1.95 * cm
    cartao(x, y, COL_L, a_i)
    c.setFillColorRGB(*VERDE)
    c.circle(x + 1.35 * cm, y - 1.4 * cm, 0.62 * cm, stroke=0, fill=1)
    c.setStrokeColorRGB(1, 1, 1)
    c.setLineWidth(3.4)
    c.setLineCap(1)
    c.line(x + 1.05 * cm, y - 1.43 * cm, x + 1.29 * cm, y - 1.67 * cm)
    c.line(x + 1.29 * cm, y - 1.67 * cm, x + 1.71 * cm, y - 1.13 * cm)
    texto(x + 2.6 * cm, y - 1.6 * cm, titulo, BOLD, 25, TINTA)
    paragrafo(x + 2.6 * cm, y - 3.05 * cm, nota, COL_L - 3.6 * cm, REG, 23, SUAVE)
    y -= a_i + 0.6 * cm

y -= 0.9 * cm
y = secao(x, y, "por que importa", "Contexto e problema", VERMELHO, COL_L)

for titulo, corpo in [
    ("A distância em linha reta mente.",
     "No cenário medido, um motorista a 275 m do passageiro leva 5,8 min para chegar; "
     "outro, a 548 m, leva 1,0 min — o primeiro está do outro lado do rio."),
    ("k candidatos, k varreduras do grafo.",
     "A alocação ingênua roda uma busca de rota completa para cada candidato. "
     "É computação jogada fora em cada pedido."),
]:
    c.setFillColorRGB(*VERMELHO)
    c.rect(x, y - 0.95 * cm, 0.16 * cm, 1.15 * cm, stroke=0, fill=1)
    texto(x + 0.9 * cm, y - 0.55 * cm, titulo, BOLD, 25, TINTA)
    y = paragrafo(x + 0.9 * cm, y - 1.95 * cm, corpo, COL_L - 0.9 * cm, REG, 23, SUAVE)
    y -= 1.5 * cm

y -= 0.6 * cm
y = secao(x, y, "o que foi entregue", "Objetivos", LATAO, COL_L)

GERAL = ("Formalizar a malha viária como grafo ponderado direcionado G = (V, E, w), com w em "
         "segundos, e implementar a camada algorítmica que devolve o motorista de menor tempo "
         "real de chegada e a rota ótima até o destino — com corretude demonstrada e ganho "
         "medido.")
a_g = alt_paragrafo(GERAL, COL_L - 2.6 * cm, REG, 23) + 3.0 * cm
cartao(x, y, COL_L, a_g, GRAFITE, None)
texto(x + 1.3 * cm, y - 1.5 * cm, "OBJETIVO GERAL", BLACK, 22, VERDE_CLARO, espaco=2.0)
paragrafo(x + 1.3 * cm, y - 3.0 * cm, GERAL, COL_L - 2.6 * cm, REG, 23, (0.902, 0.906, 0.898))
y -= a_g + 1.4 * cm

texto(x, y, "OBJETIVOS ESPECÍFICOS — ETAPAS CONCLUÍDAS", BLACK, 22, SUAVE, espaco=1.6)
y -= 1.45 * cm
for i, item in enumerate([
    "Malha como grafo direcionado em lista de adjacência, O(V + E); ciclo da corrida como DAG.",
    "Dijkstra e A* na mesma rotina — o Dijkstra é o A* com h = 0 — com heurística provada "
    "admissível e consistente.",
"Pareamento de k motoristas com UMA busca no grafo reverso; quadtree no filtro espacial e Kahn no fluxo de estados.",
    "Heurística ALT: marcos e desigualdade triangular sobre a malha real.",
    "Aplicação web ponta a ponta: API FastAPI e app React com mapa e tempo real.",
], 1):
    c.setFillColorRGB(*LATAO)
    c.circle(x + 0.48 * cm, y - 0.24 * cm, 0.48 * cm, stroke=0, fill=1)
    texto(x + 0.48 * cm, y - 0.5 * cm, str(i), BLACK, 22, (1, 1, 1), "centro")
    y = paragrafo(x + 1.5 * cm, y, item, COL_L - 1.5 * cm, REG, 23, TINTA)
    y -= 1.25 * cm

FIM_C1 = y

# ================================================================== COLUNA 2
x, y = COLS[1], Y_COL
y = secao(x, y, "como foi construído", "Arquitetura", ACO, COL_L)

y = paragrafo(x, y, "Setas de dependência sempre apontando para dentro: a camada matemática "
                    "não importa ninguém, e por isso roda sem banco, servidor nem rede.",
              COL_L, REG, 23, SUAVE)
y -= 1.4 * cm

CAMADAS = [
    ("frontend/", "app React + TypeScript", "mapa Leaflet, bússola, folha arrastável, WebSocket", VERDE_CLARO),
    ("backend/api/", "FastAPI", "rotas HTTP e WebSocket; publica só DEPOIS do commit", ACO),
    ("backend/dominio/", "regras do negócio", "DAG da corrida, alocação otimista, tarifa", LATAO),
    ("matematica/algoritmos/", "matemática pura", "grafo · A*/Dijkstra · ALT · quadtree · Kahn · matriz", VERDE),
]
A_CAM, G_CAM = 3.9 * cm, 1.0 * cm
for i, (pasta, papel, nota, cor) in enumerate(CAMADAS):
    cy = y - i * (A_CAM + G_CAM)
    cartao(x, cy, COL_L, A_CAM)
    faixa_lateral(x, cy, A_CAM, cor)
    texto(x + 1.5 * cm, cy - 1.45 * cm, pasta, BOLD, 24, cor)
    texto(x + 1.5 * cm + larg(pasta, BOLD, 24) + 0.4 * cm, cy - 1.45 * cm, papel, REG, 23, TINTA)
    texto(x + 1.5 * cm, cy - 2.9 * cm, nota, REG, 21, SUAVE)
    if i < len(CAMADAS) - 1:
        seta(x + COL_L / 2, cy - A_CAM - 0.08 * cm, x + COL_L / 2, cy - A_CAM - G_CAM + 0.22 * cm)
y -= len(CAMADAS) * A_CAM + (len(CAMADAS) - 1) * G_CAM + 1.35 * cm
texto(x, y, "Matriz de adjacência V×V mediu 1.067× mais memória: descartada.", REG, 21, FRACO)
y -= 1.6 * cm

y = secao(x, y, "o motor", "Como uma corrida acontece", VERDE, COL_L)
PIPE = [
    ("Pedido", "o passageiro marca origem e destino", VERDE_CLARO),
    ("Quadtree", "filtra os motoristas do entorno em O(log n + k)", LATAO),
    ("Busca reversa", "UMA busca no grafo invertido mede o tempo real de todos", VERMELHO),
    ("A* com ALT", "marcos e desigualdade triangular devolvem a rota ótima", VERDE),
    ("DAG da corrida", "a transição de estado é validada antes de existir", ACO),
    ("Commit, e só então WebSocket", "o cliente nunca vê estado que o rollback desfez", VERDE_CLARO),
]
A_P, G_P = 3.5 * cm, 0.65 * cm
for i, (nome, nota, cor) in enumerate(PIPE):
    cartao(x, y, COL_L, A_P)
    c.setFillColorRGB(*cor)
    c.roundRect(x + 0.9 * cm, y - 2.3 * cm, 1.6 * cm, 1.6 * cm, 0.48 * cm, stroke=0, fill=1)
    texto(x + 1.7 * cm, y - 1.85 * cm, str(i + 1), BLACK, 27, (1, 1, 1), "centro")
    texto(x + 3.1 * cm, y - 1.4 * cm, nome, BOLD, 24, TINTA)
    paragrafo(x + 3.1 * cm, y - 2.7 * cm, nota, COL_L - 3.8 * cm, REG, 21, SUAVE, 1.25)
    y -= A_P
    if i < len(PIPE) - 1:
        seta(x + 1.7 * cm, y - 0.04 * cm, x + 1.7 * cm, y - G_P + 0.2 * cm, FRACO, 2.8)
        y -= G_P

y -= 1.6 * cm
y = secao(x, y, "o mapa", "Da matriz ao grafo", LATAO, COL_L)
A_MAT = 10.6 * cm
cartao(x, y, COL_L, A_MAT)

GRADE = [".A..", ".AS.", "#A..", ".A>."]
cel = 1.35 * cm
gx, gy = x + 1.4 * cm, y - 1.4 * cm
CORES_CEL = {".": (0.945, 0.941, 0.929), "A": (0.839, 0.898, 0.859), "S": (0.976, 0.871, 0.882),
             "#": (0.776, 0.780, 0.769), ">": (0.953, 0.914, 0.831)}
for i, linha in enumerate(GRADE):
    for j, ch in enumerate(linha):
        px, py = gx + j * cel, gy - i * cel
        c.setFillColorRGB(*CORES_CEL[ch])
        c.setStrokeColorRGB(*LINHA)
        c.setLineWidth(1.4)
        c.rect(px, py - cel, cel, cel, stroke=1, fill=1)
        texto(px + cel / 2, py - cel * 0.7, ch, MONO, 21, ACO, "centro")

seta(gx + 4 * cel + 0.7 * cm, gy - 2 * cel, gx + 4 * cel + 2.4 * cm, gy - 2 * cel, ACO, 3.8)
nx, ny = gx + 4 * cel + 3.5 * cm, gy - 0.8 * cm
PONTOS = [(0, 0), (1.8 * cm, 0.2 * cm), (0.3 * cm, -1.9 * cm), (2.2 * cm, -2.2 * cm), (1.1 * cm, -3.9 * cm)]
c.setStrokeColorRGB(*ACO)
c.setLineWidth(2.6)
for a, b in [(0, 1), (0, 2), (1, 3), (2, 3), (2, 4), (3, 4)]:
    c.line(nx + PONTOS[a][0], ny + PONTOS[a][1], nx + PONTOS[b][0], ny + PONTOS[b][1])
for k, (px, py) in enumerate(PONTOS):
    c.setFillColorRGB(*(VERMELHO if k == 3 else VERDE))
    c.circle(nx + px, ny + py, 0.4 * cm, stroke=0, fill=1)

texto(x + 1.4 * cm, y - 7.5 * cm,
      "Um caractere = uma célula.   .  rua     A  avenida     S  semáforo", REG, 21, SUAVE)
texto(x + 1.4 * cm, y - 8.6 * cm, ">  mão única     #  intransponível", REG, 21, SUAVE)
c.setFillColorRGB(0.976, 0.941, 0.945)
c.roundRect(x + 1.2 * cm, y - 10.2 * cm, COL_L - 2.4 * cm, 1.6 * cm, 0.35 * cm, stroke=0, fill=1)
texto(x + 1.7 * cm, y - 9.7 * cm,
      "E[espera] = r² / 2c  no peso da aresta que CHEGA ao cruzamento", BOLD, 22, VERMELHO)
y -= A_MAT
FIM_C2 = y

# ================================================================== COLUNA 3
x, y = COLS[2], Y_COL
y = secao(x, y, "o que foi medido", "Resultados", VERDE, COL_L)
y = paragrafo(x, y, f"Na malha real: {MEDIDAS['nos']} cruzamentos, {MEDIDAS['arestas']} trechos "
                    f"de rua e {MEDIDAS['semaforos']} semáforos. Em todos os casos a rota "
                    "devolvida é a mesma — o ganho é de busca, nunca de qualidade.",
              COL_L, REG, 23, SUAVE)
y -= 1.5 * cm

TILES = [("14,3×", "menos nós na rota", "de Dijkstra para A* com ALT", VERDE_CLARO),
         ("10,7×", "menos nós no pareamento", "de k buscas para 1 reversa", VERMELHO),
         ("154,8×", "menos comparações", "da varredura linear à quadtree", LATAO),
         ("0", "rotas subótimas", "em toda a validação", (0.60, 0.65, 0.68))]
tw, th = (COL_L - 0.9 * cm) / 2, 6.0 * cm
for i, (num, nota, det, cor) in enumerate(TILES):
    tx = x + (i % 2) * (tw + 0.9 * cm)
    ty = y - (i // 2) * (th + 0.9 * cm)
    cartao(tx, ty, tw, th, GRAFITE, None, 0.55 * cm)
    c.setFillColorRGB(*cor)
    c.roundRect(tx, ty - th, 0.3 * cm, th, 0.15 * cm, stroke=0, fill=1)
    texto(tx + tw / 2, ty - 2.6 * cm, num, BLACK, 58, cor, "centro")
    texto(tx + tw / 2, ty - 4.0 * cm, nota, SEMI, 22, (0.937, 0.937, 0.925), "centro")
    texto(tx + tw / 2, ty - 5.1 * cm, det, REG, 21, (0.631, 0.651, 0.659), "centro")
y -= 2 * th + 0.9 * cm + 1.8 * cm

texto(x, y, "NÓS EXPANDIDOS EM 25 ROTAS ORIGEM–DESTINO", BLACK, 22, SUAVE, espaco=1.6)
y -= 1.6 * cm
A_GRAF = 10.9 * cm
cartao(x, y, COL_L, A_GRAF)
BARRAS = [("Dijkstra", MEDIDAS["dijkstra_nos"], (0.42, 0.45, 0.47), ""),
          ("A* haversine", MEDIDAS["haversine_nos"], LATAO, f"{MEDIDAS['haversine_ms']} ms/rota"),
          ("A* com ALT", MEDIDAS["alt_nos"], VERDE, f"{MEDIDAS['alt_ms']} ms/rota")]
maior = max(v for _, v, _, _ in BARRAS)
bx, bw = x + 1.3 * cm, COL_L - 2.6 * cm
for i, (nome, valor, cor, nota) in enumerate(BARRAS):
    by = y - 1.8 * cm - i * 2.8 * cm
    texto(bx, by, nome, BOLD, 23, TINTA)
    texto(bx + bw, by, f"{valor:,}".replace(",", ".") + (f"   ·   {nota}" if nota else ""),
          SEMI, 22, cor, "dir")
    c.setFillColorRGB(*TRILHO)
    c.roundRect(bx, by - 1.75 * cm, bw, 1.15 * cm, 0.3 * cm, stroke=0, fill=1)
    c.setFillColorRGB(*cor)
    c.roundRect(bx, by - 1.75 * cm, bw * valor / maior, 1.15 * cm, 0.3 * cm, stroke=0, fill=1)
texto(bx, y - A_GRAF + 1.0 * cm,
      "Mesmo custo ótimo nas três — conferido rota a rota contra o Dijkstra.", REG, 21, FRACO)
y -= A_GRAF + 1.7 * cm

y = secao(x, y, "demonstração", "O app funcionando", ACO, COL_L)
lw = 8.1 * cm
base, fim = y + 0.5 * cm, y
for i, (arq, legenda) in enumerate([("algoritmo.png", "A* × Dijkstra na rota pedida"),
                                    ("alocada.png", "motorista alocado, ao vivo"),
                                    ("motorista-corrida.png", "o lado do motorista")]):
    ix = x + 0.25 * cm + i * (lw + 0.6 * cm)
    fim = celular(arq, ix, base, lw)
    for k, linha in enumerate(quebrar(legenda, REG, 21, lw + 0.5 * cm)):
        texto(ix + lw / 2, fim - 1.2 * cm - k * 1.05 * cm, linha, REG, 21, SUAVE, "centro")
y = fim - 3.9 * cm

INDS = [("Semáforos reais no peso das arestas", f"{MEDIDAS['semaforos']} · 67% das rotas mudam de traçado"),
        ("Pré-processamento do ALT", "16 marcos · 10,3 s · artefato de 29,8 MB"),
        ("Testes automatizados", f"{MEDIDAS['testes']} verdes + {MEDIDAS['e2e']} no navegador"),
        ("Estratégia de validação", "oráculo: Dijkstra confere o A*, varredura confere a quadtree")]
A_IND = len(INDS) * 2.4 * cm + 2.5 * cm
cartao(x, y, COL_L, A_IND)
texto(x + 1.3 * cm, y - 1.6 * cm, "INDICADORES DE ENTREGA", BLACK, 22, SUAVE, espaco=1.6)
for i, (chave, valor) in enumerate(INDS):
    iy = y - 3.1 * cm - i * 2.4 * cm
    c.setFillColorRGB(*VERDE)
    c.circle(x + 1.45 * cm, iy + 0.22 * cm, 0.2 * cm, stroke=0, fill=1)
    texto(x + 2.1 * cm, iy, chave, SEMI, 22, TINTA)
    texto(x + 2.1 * cm, iy - 1.15 * cm, valor, REG, 21, SUAVE)
y -= A_IND
FIM_C3 = y

# ====================================================================== rodapé
cartao(MARGEM, RODAPE_TOPO, UTIL, RODAPE_TOPO - RODAPE_BASE, GRAFITE, None, 0.7 * cm, sombra=False)
for i, cor in enumerate((VERDE, VERDE_CLARO, LATAO, VERMELHO)):
    c.setFillColorRGB(*cor)
    c.rect(MARGEM + i * UTIL / 4, RODAPE_TOPO - 0.4 * cm, UTIL / 4, 0.4 * cm, stroke=0, fill=1)

fx, fy = MARGEM + 2.4 * cm, RODAPE_TOPO - 1.9 * cm
L_CONC, L_REF, L_QR = 35 * cm, 25 * cm, 10.4 * cm

texto(fx, fy - 0.5 * cm, "CONSIDERAÇÕES FINAIS", BLACK, 22, VERDE_CLARO, espaco=2.2)
yy = paragrafo(fx, fy - 2.8 * cm,
               "O ganho veio de trocar o algoritmo, não de comprar máquina: as mesmas rotas, com "
               "uma fração da busca. O que sustenta a troca é a demonstração — admissibilidade e "
               "consistência da heurística, dualidade do grafo reverso, aciclicidade do fluxo — e "
               "não a medição isolada. O protótipo roda ponta a ponta sobre ruas reais.",
               L_CONC, REG, 23, (0.918, 0.922, 0.914))
yy -= 1.6 * cm
texto(fx, yy, "TRABALHOS FUTUROS", BLACK, 22, LATAO, espaco=2.0)
yy -= 1.4 * cm
for item in ["Semáforos dependentes do tempo (onda verde), provando antes a propriedade FIFO.",
             "Algoritmo húngaro para despacho em lote, com vários pedidos simultâneos.",
             "Publicação: front-end no Vercel, back-end no Railway com a malha em memória."]:
    c.setFillColorRGB(*LATAO)
    c.circle(fx + 0.25 * cm, yy + 0.24 * cm, 0.2 * cm, stroke=0, fill=1)
    yy = paragrafo(fx + 0.9 * cm, yy, item, L_CONC - 0.9 * cm, REG, 22, (0.800, 0.812, 0.808))
    yy -= 1.15 * cm

yy -= 0.6 * cm
c.setStrokeColorRGB(0.200, 0.216, 0.231)
c.setLineWidth(2)
c.line(fx, yy + 0.5 * cm, fx + L_CONC, yy + 0.5 * cm)
paragrafo(fx, yy - 0.9 * cm,
          "Pilha: Python 3.11 · FastAPI · SQLAlchemy · React + TypeScript · Leaflet · WebSocket. "
          "Os algoritmos são de implementação própria — nenhuma biblioteca de grafos.",
          L_CONC, REG, 21, (0.600, 0.616, 0.620))

rx = fx + L_CONC + 2.2 * cm
texto(rx, fy - 0.5 * cm, "REFERÊNCIAS", BLACK, 22, VERDE_CLARO, espaco=2.2)
yy = fy - 2.7 * cm
for ref in [
    "CORMEN, T. H. et al. Algoritmos: teoria e prática. 4. ed. Rio de Janeiro: LTC, 2024.",
    "HART, P. E.; NILSSON, N. J.; RAPHAEL, B. A formal basis for the heuristic determination of "
    "minimum cost paths. IEEE Transactions on Systems Science and Cybernetics, v. 4, n. 2, "
    "p. 100-107, 1968.",
    "GOLDBERG, A. V.; HARRELSON, C. Computing the shortest path: A* search meets graph theory. "
    "In: SODA, 16., 2005, Vancouver. Proceedings. Philadelphia: SIAM, 2005. p. 156-165.",
]:
    yy = paragrafo(rx, yy, ref, L_REF, REG, 21, (0.788, 0.800, 0.796), 1.3)
    yy -= 1.1 * cm
texto(rx, yy - 0.2 * cm, "Malha: OpenStreetMap contributors (ODbL), via Overpass API.",
      REG, 21, (0.600, 0.616, 0.620))

qx = LARGURA - MARGEM - 2.4 * cm - L_QR
qy = RODAPE_BASE + 5.2 * cm
try:
    import qrcode

    qr = qrcode.QRCode(border=1, error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(REPO)
    qr.make(fit=True)
    matriz = qr.get_matrix()
    c.setFillColorRGB(1, 1, 1)
    c.roundRect(qx - 0.6 * cm, qy - 0.6 * cm, L_QR + 1.2 * cm, L_QR + 1.2 * cm, 0.4 * cm,
                stroke=0, fill=1)
    passo = L_QR / len(matriz)
    c.setFillColorRGB(*ESCURO)
    for i, linha in enumerate(matriz):
        for j, preto in enumerate(linha):
            if preto:
                c.rect(qx + j * passo, qy + L_QR - (i + 1) * passo, passo * 1.02, passo * 1.02,
                       stroke=0, fill=1)
except ImportError:
    print("aviso: módulo qrcode ausente — QR não desenhado (pip install qrcode).")

texto(qx + L_QR / 2, qy - 1.9 * cm, "Repositório, documentação e protótipo", SEMI, 22,
      (0.937, 0.937, 0.925), "centro")
texto(qx + L_QR / 2, qy - 3.05 * cm, "github.com/Cm-Kauan/Prototipo-TrueCompass", REG, 21,
      (0.631, 0.651, 0.659), "centro")

c.showPage()
c.save()

if SEM_GLIFO:
    print("ATENÇÃO: a fonte não tem estes caracteres, que sairiam em branco: "
          + " ".join(sorted(SEM_GLIFO)))
print(f"banner: {SAIDA}  ({os.path.getsize(SAIDA) / 1e6:.1f} MB · 90 × 120 cm)")
for nome, fim in (("coluna 1", FIM_C1), ("coluna 2", FIM_C2), ("coluna 3", FIM_C3)):
    folga = (fim - RODAPE_TOPO) / cm
    print(f"  {nome}: termina em {fim / cm:5.1f} cm  ·  folga até o rodapé: {folga:5.1f} cm"
          f"{'   <<< ESTOUROU' if folga < 0 else ''}")

if "--previa" in sys.argv:
    destino = os.path.join(AQUI, "previa_banner")
    os.system(f'pdftoppm -png -r 50 -singlefile "{SAIDA}" "{destino}"')
    print(f"prévia: {destino}.png")
