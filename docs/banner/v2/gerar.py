# -*- coding: utf-8 -*-
"""Banner do TrueCompass para a Mostra de Trabalhos A3 (Expo São Judas 2026/2).

Segue o "Guia Oficial: Como Elaborar o Banner" do Prof. Raulison Resende:

- 90 cm x 120 cm, retrato; Montserrat;
- título 80 pt, títulos de seção 40 pt, texto 24 a 30 pt (nada abaixo de 20 pt);
- cabeçalho com logotipos, título, autores, orientador e curso/campus/ano;
- três colunas: Contexto e Objetivos | Metodologia e Arquitetura (diagramas) |
  Resultados (gráfico, indicadores, telas);
- rodapé com Considerações finais, Referências (ABNT) e QR Code do GitHub;
- metade visual, metade texto curto em tópicos.

    python3 docs/banner/v2/gerar.py
    node docs/banner/v2/renderizar.js docs/banner/v2/banner.html docs/banner/v2/banner_truecompass_v2.pdf

Dependências: `pip install qrcode` e o Playwright (já instalado no ambiente).
"""
import base64
import io
import json
import math
import os

import qrcode
import qrcode.image.svg

AQUI = os.path.dirname(os.path.abspath(__file__))
# mapa_heroi.json: ruas, semáforos e a rota USJT Mooca -> Praça da Sé, tirados da
# malha real pela API do app (/malha/trechos, /malha/semaforos, /viagens/estimativa).
DADOS = os.path.join(AQUI, "mapa_heroi.json")
CAPTURAS = os.path.join(AQUI, "capturas")
FONTES = os.path.join(AQUI, "..", "fontes")
SAIDA = os.path.join(AQUI, "banner.html")
REPO = "https://github.com/Cm-Kauan/Prototipo-TrueCompass"

# ------------------------------------------------------------ medições
# Medidas na malha da cidade inteira (136.891 cruzamentos), 30 rotas sorteadas
# (semente 2026), nos mesmos pares para os três algoritmos. Ver README.md.
MEDIDAS = {
    "dijkstra_nos": 66_015, "haversine_nos": 45_877, "alt_nos": 6_687,
    "dijkstra_ms": 167, "haversine_ms": 169, "alt_ms_mediana": 22,
    "rotas": 30, "divergencias": 0, "testes": 281,
}

# ------------------------------------------------------------ mapa do cabeçalho
CAB_W, CAB_H = 90.0, 30.0
d = json.load(open(DADOS))
rota = d["rota"]


def merc(lat, lon):
    s = math.sin(math.radians(lat))
    return (lon + 180) / 360, 0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)


xs = [merc(a, b)[0] for a, b in rota]
ys = [merc(a, b)[1] for a, b in rota]
# A rota fica à direita do cabeçalho, abaixo da placa do curso; o texto, à esquerda.
escala = 30.0 / (max(xs) - min(xs))
cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
ALVO_X, ALVO_Y = 70.0, 21.5


def P(lat, lon):
    x, y = merc(lat, lon)
    return (x - cx) * escala + ALVO_X, (y - cy) * escala + ALVO_Y


ruas = []
for t in d["trechos"]:
    a, b = P(t[0], t[1]), P(t[2], t[3])
    if (-2 < a[0] < CAB_W + 2 and -2 < a[1] < CAB_H + 2) or (-2 < b[0] < CAB_W + 2 and -2 < b[1] < CAB_H + 2):
        ruas.append(f"M{a[0]:.2f} {a[1]:.2f}L{b[0]:.2f} {b[1]:.2f}")
caminho_rota = "M" + "L".join(f"{x:.2f} {y:.2f}" for x, y in (P(a, b) for a, b in rota))


def metros(a, b):
    return math.hypot((a[1] - b[1]) * 102000, (a[0] - b[0]) * 111000)


def dist_seg(p, a, b):
    P0 = ((p[1] - a[1]) * 102000, (p[0] - a[0]) * 111000)
    B = ((b[1] - a[1]) * 102000, (b[0] - a[0]) * 111000)
    L = B[0] ** 2 + B[1] ** 2
    t = max(0, min(1, (P0[0] * B[0] + P0[1] * B[1]) / L)) if L else 0
    return math.hypot(P0[0] - t * B[0], P0[1] - t * B[1])


na_rota = []
for s in d["semaforos"]:
    pt = (s["lat"], s["lon"])
    if any(dist_seg(pt, rota[i - 1], rota[i]) < 15 for i in range(1, len(rota))):
        if all(metros(pt, o) > 160 for o in na_rota):
            na_rota.append(pt)


def semaforo(x, y, k=1.0):
    """O ícone do app: semáforo de pé, vermelho aceso, ponta no cruzamento."""
    return f"""<g transform="translate({x:.2f} {y:.2f}) scale({k})">
  <path d="M0 0 L-0.32 -0.62 L0.32 -0.62 Z" fill="#E8ECEF"/>
  <rect x="-0.75" y="-3.45" width="1.5" height="2.95" rx="0.56" fill="#262B31" stroke="#fff" stroke-width="0.17"/>
  <circle cy="-2.76" r="0.6" fill="#FF3B3B" opacity=".45"/>
  <circle cy="-2.76" r="0.33" fill="#FF3D3D"/>
  <circle cy="-1.96" r="0.33" fill="#4E421F"/>
  <circle cy="-1.16" r="0.33" fill="#1B4430"/>
</g>"""


o, f = P(*rota[0]), P(*rota[-1])
MAPA = f"""<svg class="mapa" viewBox="0 0 {CAB_W} {CAB_H}" preserveAspectRatio="xMidYMid slice">
  <defs>
    <filter id="brilho" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="0.4"/></filter>
    <linearGradient id="vela" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#0E1215" stop-opacity=".93"/>
      <stop offset=".5" stop-color="#0E1215" stop-opacity=".78"/>
      <stop offset="1" stop-color="#0E1215" stop-opacity=".2"/>
    </linearGradient>
  </defs>
  <path d="{''.join(ruas)}" stroke="#3A4854" stroke-width="0.08" fill="none" stroke-linecap="round"/>
  <rect width="{CAB_W}" height="{CAB_H}" fill="url(#vela)"/>
  <path d="{caminho_rota}" stroke="#3DDC84" stroke-width="0.8" fill="none" opacity=".45" filter="url(#brilho)" stroke-linejoin="round" stroke-linecap="round"/>
  <path d="{caminho_rota}" stroke="#3DDC84" stroke-width="0.3" fill="none" stroke-linejoin="round" stroke-linecap="round"/>
  {''.join(semaforo(*P(*pt), k=0.72) for pt in na_rota)}
  <circle cx="{o[0]:.2f}" cy="{o[1]:.2f}" r="0.55" fill="#3DDC84" stroke="#0E1215" stroke-width="0.22"/>
  <rect x="{f[0] - 0.55:.2f}" y="{f[1] - 0.55:.2f}" width="1.1" height="1.1" rx="0.2" fill="#E0525C" stroke="#0E1215" stroke-width="0.22"/>
</svg>"""

# ------------------------------------------------------------------- QR
img = qrcode.make(REPO, image_factory=qrcode.image.svg.SvgPathImage, box_size=10, border=0)
buf = io.BytesIO()
img.save(buf)
QR = buf.getvalue().decode()
QR = QR[QR.index("<svg"):]


def dado(caminho, tipo):
    return f"data:{tipo};base64," + base64.b64encode(open(caminho, "rb").read()).decode()


def foto(nome):
    return dado(os.path.join(CAPTURAS, nome), "image/png")


# Logotipo oficial, baixado de https://www.usjt.br/assets/img/logo-usjt.svg.
# Entra como <img> (data URI), nunca como SVG embutido: nada do arquivo executa.
LOGO_USJT = dado(os.path.join(AQUI, "logos", "logo-usjt.svg"), "image/svg+xml")


def fonte(peso):
    return f"""@font-face {{ font-family: 'Montserrat'; font-weight: {peso};
      src: url('file://{os.path.abspath(FONTES)}/Montserrat-{peso}.ttf') format('truetype'); }}"""


# ---------------------------------------------------------- ícones (traço)
ICONES = {
    "mapa": '<path d="m9 4-6 2.5v13.5l6-2.5 6 2.5 6-2.5V4l-6 2.5z"/><path d="M9 4v13.5M15 6.5V20"/>',
    "poda": '<circle cx="6" cy="6" r="2.2"/><circle cx="18" cy="6" r="2.2"/><circle cx="12" cy="18" r="2.2"/><path d="M8 7l8 0M7 8l4 8M17 8l-4 8"/>',
    "contrai": '<path d="M4 12h16"/><circle cx="4" cy="12" r="2"/><circle cx="20" cy="12" r="2"/><path d="M9 8l3 4-3 4M15 8l-3 4 3 4"/>',
    "semaforo": '<rect x="8" y="2.5" width="8" height="19" rx="3"/><circle cx="12" cy="7" r="1.4"/><circle cx="12" cy="12" r="1.4"/><circle cx="12" cy="17" r="1.4"/>',
    "check": '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    "seta": '<path d="M12 4v16M6 14l6 6 6-6"/>',
}


def icone(nome, classe="ic"):
    return (f'<svg class="{classe}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" '
            f'stroke-linecap="round" stroke-linejoin="round">{ICONES[nome]}</svg>')


SETA = f'<div class="seta">{icone("seta")}</div>'

LOGO = """<svg viewBox="0 0 512 512"><circle cx="256" cy="256" r="236" fill="#1C2024" stroke="#3C444B" stroke-width="12"/>
<circle cx="256" cy="256" r="190" fill="none" stroke="#2D3338" stroke-width="5"/>
<g stroke="#5A646D" stroke-width="7">""" + "".join(
    f'<line x1="256" y1="40" x2="256" y2="{70 if i % 2 == 0 else 58}" transform="rotate({i * 45} 256 256)"/>' for i in range(8)
) + """</g><g transform="rotate(32 256 256)">
<polygon points="256,86 286,256 256,232 226,256" fill="#E0525C"/>
<polygon points="256,426 226,256 256,280 286,256" fill="#3C444B"/></g>
<circle cx="256" cy="256" r="19" fill="#B08D57"/></svg>"""

# Diagrama do problema: o motorista "mais perto" em linha reta está do outro
# lado de uma via sem travessia; o mais longe chega antes pelas ruas.
PROBLEMA = """<svg class="diagrama" viewBox="0 0 26 13.5">
  <rect width="26" height="13.5" rx="0.6" fill="#E9ECE7"/>
  <g stroke="#FFFFFF" stroke-width="0.55">
    <path d="M0 3.6H26M0 7H26M0 10.4H26M4 0V13.5M9 0V13.5M17 0V13.5M22 0V13.5"/>
  </g>
  <path d="M0 5.3H26" stroke="#9FB4C7" stroke-width="1.6"/>
  <text x="0.6" y="5.6" font-size="0.8" fill="#3E5568" font-weight="700" font-family="Montserrat">via expressa, sem travessia</text>
  <path d="M13 7 L13 3.6" stroke="#C5303E" stroke-width="0.2" stroke-dasharray="0.35 0.3"/>
  <path d="M13 3.6 H22 V10.4 H13 V7" stroke="#C5303E" stroke-width="0.34" fill="none" stroke-linejoin="round" opacity=".85"/>
  <path d="M4 10.4 H13 V7" stroke="#2F8A4C" stroke-width="0.45" fill="none" stroke-linejoin="round"/>
  <circle cx="13" cy="7" r="0.65" fill="#2F8A4C" stroke="#fff" stroke-width="0.2"/>
  <g transform="translate(13 3.6)"><rect x="-0.75" y="-0.55" width="1.5" height="1.1" rx="0.3" fill="#C5303E"/></g>
  <g transform="translate(4 10.4)"><rect x="-0.75" y="-0.55" width="1.5" height="1.1" rx="0.3" fill="#2F8A4C"/></g>
  <text x="0.6" y="2.6" font-size="0.82" fill="#C5303E" font-weight="800" font-family="Montserrat">A: 300 m em linha reta, 7 min</text>
  <text x="0.6" y="12.6" font-size="0.82" fill="#1F5E33" font-weight="800" font-family="Montserrat">B: 900 m em linha reta, 3 min</text>
  <text x="14" y="8.4" font-size="0.8" fill="#15191C" font-weight="800" font-family="Montserrat">passageiro</text>
</svg>"""

PIPELINE = [
    ("mapa", "OpenStreetMap", "650 mil nós da cidade de São Paulo"),
    ("poda", "Poda do grafo", "fica só o componente fortemente conexo"),
    ("contrai", "Contração", "137 mil cruzamentos: 79% a menos, mesmas rotas"),
    ("semaforo", "Peso = tempo", "trecho da rua + espera do semáforo, r²/2c"),
]
CAMADAS = [
    ("App", "React + TypeScript · mapa MapLibre", "Vercel", "#2F8A4C"),
    ("API", "FastAPI · WebSocket · login seguro", "Railway", "#1D4FB0"),
    ("Domínio", "corrida como grafo acíclico (Kahn)", "", "#B08D57"),
    ("Algoritmos", "A* · ALT · Dijkstra · Quadtree", "", "#C5303E"),
    ("Banco", "MySQL", "Railway", "#4A5560"),
]
PASSOS = [
    "Pedido: A* calcula rota e preço",
    "Quadtree acha os motoristas perto",
    "Busca reversa: quem chega antes",
    "Oferta: 20 s para aceitar",
    "Corrida ao vivo no mapa",
]
INDICADORES = [
    ("0", f"rotas diferentes do Dijkstra em {MEDIDAS['rotas']} testes"),
    ("67%", "das rotas mudam com os semáforos"),
    ("137 mil", "cruzamentos reais no grafo"),
    (str(MEDIDAS["testes"]), "testes automatizados"),
]
EQUIPE = ["Bianca Murcela Mascamudo", "Carolina Chaves", "Carolina Yukari Kague",
          "Gabryela Araujo", "Kauan Sousa", "Wildiner Lopes"]
REFERENCIAS = [
    "DIJKSTRA, E. W. A note on two problems in connexion with graphs. <i>Numerische Mathematik</i>, v. 1, p. 269-271, 1959.",
    "HART, P. E.; NILSSON, N. J.; RAPHAEL, B. A formal basis for the heuristic determination of minimum cost paths. <i>IEEE Trans. SSC</i>, v. 4, n. 2, p. 100-107, 1968.",
    "GOLDBERG, A. V.; HARRELSON, C. Computing the shortest path: A* search meets graph theory. In: <i>ACM-SIAM SODA</i>, 2005. p. 156-165.",
]

# ------------------------------------------------------------- gráfico
BARRAS = [("Dijkstra", MEDIDAS["dijkstra_nos"], f"{MEDIDAS['dijkstra_ms']} ms", "#7A848C"),
          ("A* (linha reta)", MEDIDAS["haversine_nos"], f"{MEDIDAS['haversine_ms']} ms", "#B08D57"),
          ("A* + ALT", MEDIDAS["alt_nos"], f"{MEDIDAS['alt_ms_mediana']} ms", "#2F8A4C")]
maior = max(v for _, v, _, _ in BARRAS)
grafico = "".join(
    f"""<div class="barra"><span class="barra-nome">{n}</span>
  <div class="barra-trilho"><div class="barra-cheia" style="width:{max(v / maior * 100, 4):.1f}%;background:{c}"></div>
  <b>{v:,}</b></div><span class="barra-ms">{ms}</span></div>""".replace(",", ".")
    for n, v, ms, c in BARRAS)
reducao = round(MEDIDAS["dijkstra_nos"] / MEDIDAS["alt_nos"])


def ul(itens, classe="topicos"):
    return f'<ul class="{classe}">' + "".join(f"<li>{i}</li>" for i in itens) + "</ul>"


HTML = f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>Banner TrueCompass</title>
<style>
{fonte(400)} {fonte(600)} {fonte(700)} {fonte(800)}
@page {{ size: 90cm 120cm; margin: 0; }}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
html, body {{ width: 90cm; height: 120cm; }}
body {{ font-family: 'Montserrat', Arial, sans-serif; color: #15191C; background: #F3F2EE; position: relative; overflow: hidden;
        -webkit-print-color-adjust: exact; print-color-adjust: exact; }}

/* ================= cabeçalho */
.cab {{ position: absolute; inset: 0 0 auto 0; height: {CAB_H}cm; background: #0E1215; color: #fff; overflow: hidden; }}
.mapa {{ position: absolute; inset: 0; width: 100%; height: 100%; }}
.faixa {{ position: absolute; top: 0; left: 0; right: 0; height: .55cm;
          background: linear-gradient(90deg, #E0525C 0 25%, #3DDC84 25% 50%, #B08D57 50% 75%, #5A646D 75%); }}
.placa {{ position: absolute; top: 2.2cm; background: #fff; border-radius: .7cm; display: flex; align-items: center;
          box-shadow: 0 .4cm 1cm rgba(0,0,0,.35); }}
.placa.usjt {{ left: 3.5cm; height: 4.6cm; padding: 0 1.4cm; }}
.placa.usjt img {{ height: 2.4cm; }}
.placa.curso {{ right: 3.5cm; height: 4.6cm; padding: 0 1.4cm; flex-direction: column; align-items: flex-start; justify-content: center; }}
.placa.curso small {{ font: 700 21pt Montserrat; letter-spacing: .14em; color: #7A848C; }}
.placa.curso b {{ font: 800 28pt/1.15 Montserrat; color: #293189; }}
.evento {{ position: absolute; top: 3.75cm; left: 0; right: 0; text-align: center; font: 700 24pt Montserrat;
           letter-spacing: .16em; color: #3DDC84; }}
.titulo {{ position: absolute; top: 8.6cm; left: 3.5cm; display: flex; align-items: center; gap: 1.8cm; }}
.titulo .logo {{ width: 10cm; height: 10cm; flex: none; filter: drop-shadow(0 .4cm .9cm rgba(0,0,0,.5)); }}
.titulo h1 {{ font: 800 80pt Montserrat; letter-spacing: -.02em; line-height: 1; }}
.titulo h1 span {{ color: #E0525C; }}
.titulo .sub {{ margin-top: .6cm; font: 600 36pt/1.2 Montserrat; color: #3DDC84; max-width: 38cm; }}
.autores {{ position: absolute; top: 20.6cm; left: 3.5cm; right: 36cm; }}
.autores .nomes {{ font: 600 25pt/1.5 Montserrat; color: #F1F4F6; }}
.autores .nomes span:not(:nth-child(3n))::after {{ content: '  ·  '; color: #5A646D; }}
.autores .nomes span:nth-child(3)::after {{ content: ''; display: block; }}
.autores .prof {{ margin-top: .45cm; font: 700 25pt Montserrat; color: #fff; }}
.autores .curso {{ margin-top: .3cm; font: 600 24pt Montserrat; color: #C9A86A; }}

/* ================= colunas */
.colunas {{ position: absolute; top: {CAB_H + 2.2}cm; left: 3.5cm; right: 3.5cm; display: grid;
            grid-template-columns: repeat(3, 1fr); gap: 1.8cm; }}
.col {{ display: flex; flex-direction: column; gap: 1.6cm; justify-content: space-between; height: {101 - 2.2 - CAB_H - 2.2}cm; }}
.secao h2 {{ font: 800 40pt Montserrat; letter-spacing: -.01em; display: flex; align-items: center; gap: .7cm; margin-bottom: .9cm; }}
.secao h2 i {{ font-style: normal; flex: none; width: 1.7cm; height: 1.7cm; border-radius: 50%; display: grid; place-items: center;
               background: #15191C; color: #fff; font: 800 26pt Montserrat; }}
.cartao {{ background: #fff; border-radius: .9cm; padding: 1.5cm 1.5cm; box-shadow: 0 .3cm .9cm rgba(16,22,26,.08); }}
h3 {{ font: 700 28pt Montserrat; margin-bottom: .6cm; }}
.topicos {{ list-style: none; display: flex; flex-direction: column; gap: .5cm; }}
.topicos li {{ position: relative; padding-left: 1.1cm; font: 400 25pt/1.38 Montserrat; color: #2B3238; }}
.topicos li::before {{ content: ''; position: absolute; left: .1cm; top: .45cm; width: .45cm; height: .45cm; border-radius: 50%; background: #C5303E; }}
.topicos.verde li::before {{ background: #2F8A4C; }}
.topicos b {{ color: #15191C; }}
.diagrama {{ display: block; width: 100%; margin-top: 1.2cm; border-radius: .6cm; }}
.col:first-child .topicos li {{ font-size: 27pt; }}
.col:first-child .topicos {{ gap: .7cm; }}
.legenda {{ margin-top: .5cm; font: 600 22pt Montserrat; color: #5F6770; }}
.geral {{ border-left: .4cm solid #2F8A4C; padding: 1cm 1.1cm; background: #EAF3EC; border-radius: .5cm;
          font: 600 27pt/1.4 Montserrat; color: #1F3A28; margin-bottom: .9cm; }}
.geral small {{ display: block; font: 800 21pt Montserrat; letter-spacing: .12em; color: #2F8A4C; margin-bottom: .3cm; }}
.especificos-titulo {{ font: 800 21pt Montserrat; letter-spacing: .12em; color: #7A848C; margin-bottom: .5cm; }}

/* pipeline do mapa ao grafo */
.pipe {{ display: flex; flex-direction: column; align-items: stretch; }}
.etapa {{ display: flex; align-items: center; gap: 1cm; background: #F6F7F4; border: .07cm solid #E1E4DE; border-radius: .7cm; padding: .75cm 1cm; }}
.etapa .ic {{ flex: none; width: 1.7cm; height: 1.7cm; color: #2F8A4C; }}
.etapa b {{ display: block; font: 700 25pt Montserrat; }}
.etapa span {{ display: block; font: 400 22pt/1.3 Montserrat; color: #4A535B; }}
.seta {{ display: grid; place-items: center; height: 1.1cm; color: #9AA2A9; }}
.seta svg {{ width: 1cm; height: 1cm; }}
/* camadas */
.camada {{ display: grid; grid-template-columns: 6.2cm 1fr auto; align-items: center; gap: .7cm; padding: .55cm .8cm;
           border-radius: .55cm; background: #F6F7F4; }}
.camada + .camada {{ margin-top: .35cm; }}
.camada b {{ color: #fff; font: 800 22pt Montserrat; text-align: center; padding: .35cm 0; border-radius: .4cm; }}
.camada span {{ font: 400 22pt/1.3 Montserrat; color: #2B3238; }}
.camada em {{ font: 700 21pt Montserrat; font-style: normal; color: #7A848C; }}
/* passos */
.passos {{ list-style: none; counter-reset: p; display: flex; flex-direction: column; gap: .45cm; }}
.passos li {{ counter-increment: p; display: flex; align-items: center; gap: .8cm; font: 600 24pt Montserrat; color: #2B3238; }}
.passos li::before {{ content: counter(p); flex: none; width: 1.45cm; height: 1.45cm; border-radius: 50%; background: #2F8A4C; color: #fff;
                      display: grid; place-items: center; font: 800 22pt Montserrat; }}

/* resultados */
.destaque {{ display: flex; align-items: baseline; gap: .8cm; margin-bottom: .8cm; }}
.destaque b {{ font: 800 72pt Montserrat; color: #2F8A4C; letter-spacing: -.02em; line-height: 1; }}
.destaque span {{ font: 600 25pt/1.3 Montserrat; color: #2B3238; }}
.barra {{ display: grid; grid-template-columns: 7.3cm 1fr 3.6cm; align-items: center; gap: .6cm; }}
.barra + .barra {{ margin-top: .7cm; }}
.barra-nome {{ font: 700 22pt Montserrat; color: #2B3238; }}
.barra-trilho {{ position: relative; height: 1.9cm; background: #EEF0EC; border-radius: .4cm; }}
.barra-cheia {{ height: 100%; border-radius: .4cm; }}
.barra-trilho b {{ position: absolute; right: .4cm; top: 50%; transform: translateY(-50%); font: 800 22pt Montserrat; color: #15191C; }}
.barra-ms {{ font: 700 22pt Montserrat; color: #5F6770; text-align: right; }}
.indicadores {{ display: grid; grid-template-columns: 1fr 1fr; gap: .8cm; }}
.ind {{ background: #fff; border-radius: .8cm; padding: 1cm 1.1cm; box-shadow: 0 .3cm .9cm rgba(16,22,26,.08); border-top: .3cm solid #2F8A4C; }}
.ind:nth-child(2) {{ border-top-color: #C5303E; }} .ind:nth-child(3) {{ border-top-color: #B08D57; }} .ind:nth-child(4) {{ border-top-color: #1D4FB0; }}
.ind b {{ display: block; font: 800 50pt Montserrat; letter-spacing: -.02em; line-height: 1; }}
.ind span {{ display: block; margin-top: .4cm; font: 600 22pt/1.3 Montserrat; color: #4A535B; }}
.telas {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: .6cm; }}
.tela {{ text-align: center; }}
.tela .moldura {{ border-radius: 1.3cm; padding: .28cm; background: #0B0D0F; box-shadow: 0 .45cm 1cm rgba(16,22,26,.25); }}
.tela .moldura img {{ display: block; width: 100%; border-radius: 1.05cm; aspect-ratio: 1170 / 2532; object-fit: cover; object-position: top; }}
.tela span {{ display: block; margin-top: .5cm; font: 600 21pt Montserrat; color: #3B434A; }}

/* ================= rodapé */
.rodape {{ position: absolute; left: 0; right: 0; bottom: 0; height: 19cm; background: #0E1215; color: #fff;
           padding: 2.2cm 3.5cm 0; display: grid; grid-template-columns: 1.05fr 1.25fr auto; gap: 2.6cm; }}
.rodape h2 {{ font: 800 36pt Montserrat; color: #3DDC84; margin-bottom: .9cm; }}
.rodape .topicos li {{ color: #E3E8EC; font-size: 24pt; }}
.rodape .topicos li::before {{ background: #3DDC84; }}
.rodape .topicos b {{ color: #fff; }}
.rodape .futuro {{ margin-top: .9cm; font: 800 21pt Montserrat; letter-spacing: .12em; color: #C9A86A; margin-bottom: .5cm; }}
.refs {{ list-style: none; display: flex; flex-direction: column; gap: .7cm; }}
.refs li {{ font: 400 21pt/1.4 Montserrat; color: #C5CDD3; }}
.refs i {{ font-style: italic; }}
.qr {{ text-align: center; }}
.qr .quadro {{ width: 11cm; height: 11cm; background: #fff; border-radius: .8cm; padding: .8cm; }}
.qr .quadro svg {{ width: 100%; height: 100%; }}
.qr b {{ display: block; margin-top: .7cm; font: 700 24pt Montserrat; }}
.qr span {{ display: block; margin-top: .3cm; font: 400 21pt Montserrat; color: #8C99A4; }}
</style></head><body>

<header class="cab">
  {MAPA}
  <div class="faixa"></div>
  <div class="placa usjt"><img src="{LOGO_USJT}" alt="Universidade São Judas Tadeu"></div>
  <div class="evento">MOSTRA DE TRABALHOS A3 · EXPO SÃO JUDAS 2026/2</div>
  <div class="placa curso"><small>CURSO</small><b>Análise e Desenvolvimento<br>de Sistemas</b></div>
  <div class="titulo">
    <div class="logo">{LOGO}</div>
    <div>
      <h1>True<span>Compass</span></h1>
      <div class="sub">Rota mais rápida e o motorista que chega antes, no mapa real de São Paulo</div>
    </div>
  </div>
  <div class="autores">
    <div class="nomes">{''.join(f'<span>{n}</span>' for n in EQUIPE)}</div>
    <div class="prof">Orientador: Prof. Raulison Resende</div>
    <div class="curso">Matemática Computacional Aplicada · Campus Santo Amaro · 2026/2</div>
  </div>
</header>

<main class="colunas">
  <!-- ============ esquerda: a base do projeto -->
  <div class="col">
    <section class="secao cartao"><h2><i>1</i>Contexto &amp; Problema</h2>
      {ul([
        "Apps de corrida costumam escolher o motorista <b>mais perto em linha reta</b>, e não o que <b>chega antes</b> pelas ruas.",
        "Mão única, vias expressas e <b>semáforos</b> mudam o tempo real.",
        "São Paulo tem <b>137 mil cruzamentos</b>: testar todos os caminhos não cabe em segundos.",
        "A resposta tem de sair <b>na hora</b>: o passageiro espera segundos, não minutos.",
      ])}
      {PROBLEMA}
      <p class="legenda">O motorista A parece mais perto, mas o B chega 4 min antes.</p>
    </section>
    <section class="secao cartao"><h2><i>2</i>Objetivos</h2>
      <div class="geral"><small>OBJETIVO GERAL</small>Construir um app de mobilidade que acha, com garantia matemática, a rota de menor tempo e o motorista que chega antes.</div>
      <div class="especificos-titulo">OBJETIVOS ESPECÍFICOS</div>
      {ul([
        "Modelar a cidade como <b>grafo ponderado</b> pelo tempo",
        "Rotas com <b>A* + ALT</b>, conferidas pelo Dijkstra",
        "Semáforos no peso das ruas",
        "Pareamento por <b>busca reversa</b> e quadtree",
        "App completo no ar: login, corrida e pagamento",
      ], "topicos verde")}
    </section>
  </div>

  <!-- ============ centro: a solução técnica -->
  <div class="col">
    <section class="secao cartao"><h2><i>3</i>Metodologia</h2>
      <h3>Do mapa ao grafo</h3>
      <div class="pipe">
        {SETA.join(f'<div class="etapa">{icone(i)}<div><b>{t}</b><span>{x}</span></div></div>' for i, t, x in PIPELINE)}
      </div>
    </section>
    <section class="secao cartao"><h2><i>4</i>Arquitetura</h2>
      {''.join(f'<div class="camada"><b style="background:{c}">{n}</b><span>{x}</span><em>{dep}</em></div>' for n, x, dep, c in CAMADAS)}
      <h3 style="margin-top:1.2cm">Uma corrida, passo a passo</h3>
      <ol class="passos">{''.join(f'<li>{p}</li>' for p in PASSOS)}</ol>
    </section>
  </div>

  <!-- ============ direita: resultados -->
  <div class="col">
    <section class="secao cartao"><h2><i>5</i>Resultados</h2>
      <div class="destaque"><b>{reducao}×</b><span>menos cruzamentos visitados com A* + ALT, e a mesma rota ótima</span></div>
      <h3 style="font-size:24pt;color:#5F6770">Cruzamentos visitados e tempo por rota</h3>
      {grafico}
      <p class="legenda">Média de {MEDIDAS['rotas']} rotas sorteadas na cidade inteira (tempo do ALT: mediana).</p>
    </section>
    <div class="indicadores">{''.join(f'<div class="ind"><b>{n}</b><span>{t}</span></div>' for n, t in INDICADORES)}</div>
    <section class="secao cartao">
      <div class="telas">
        <div class="tela"><div class="moldura"><img src="{foto('cap_previa.png')}" alt=""></div><span>Rota e semáforos</span></div>
        <div class="tela"><div class="moldura"><img src="{foto('cap_oferta.png')}" alt=""></div><span>Oferta ao motorista</span></div>
        <div class="tela"><div class="moldura"><img src="{foto('cap_login.png')}" alt=""></div><span>Login seguro</span></div>
      </div>
    </section>
  </div>
</main>

<footer class="rodape">
  <div>
    <h2>Considerações finais</h2>
    {ul([
      "Teoria dos grafos resolvendo um problema real, com <b>prova e medição</b>.",
      "App funcionando de ponta a ponta, publicado na nuvem.",
    ])}
    <div class="futuro">PRÓXIMOS PASSOS</div>
    {ul(["Trânsito e tempo de semáforo em tempo real", "App nativo com notificações"])}
  </div>
  <div>
    <h2>Referências</h2>
    <ol class="refs">{''.join(f'<li>{r}</li>' for r in REFERENCIAS)}</ol>
  </div>
  <div class="qr"><div class="quadro">{QR}</div><b>Código no GitHub</b><span>Mapas: © OpenStreetMap, OpenFreeMap</span></div>
</footer>
</body></html>"""

open(SAIDA, "w").write(HTML)
print("ruas:", len(ruas), "| semáforos na rota:", len(na_rota), "| html:", round(len(HTML) / 1e6, 1), "MB")
