# -*- coding: utf-8 -*-
"""Banner do TrueCompass (90 x 120 cm) em HTML -> PDF vetorial.

Pouco texto, tópicos e números. O fundo do topo é a malha REAL de São Paulo
(ruas do OpenStreetMap que o app usa), com a rota verde e os semáforos.

    python3 docs/banner/v2/gerar.py            # gera banner.html (ao lado deste arquivo)
    node docs/banner/v2/renderizar.js docs/banner/v2/banner.html docs/banner/v2/banner_truecompass_v2.pdf

Dependências: `pip install qrcode` e o Playwright (já instalado no ambiente).
"""
import base64
import io
import json
import math

import qrcode
import qrcode.image.svg

import os

AQUI = os.path.dirname(os.path.abspath(__file__))
# mapa_heroi.json: ruas, semáforos e a rota USJT Mooca -> Praça da Sé, tirados da
# malha real pela API do app (/malha/trechos, /malha/semaforos, /viagens/estimativa).
DADOS = os.path.join(AQUI, "mapa_heroi.json")
CAPTURAS = os.path.join(AQUI, "capturas")
FONTES = os.path.join(AQUI, "..", "fontes")
SAIDA = os.path.join(AQUI, "banner.html")
REPO = "https://github.com/Cm-Kauan/Prototipo-TrueCompass"

# ------------------------------------------------------------ mapa do topo
# Área do topo, em cm (o SVG usa cm como unidade de usuário).
HERO_W, HERO_H = 90.0, 46.0
d = json.load(open(DADOS))
rota = d["rota"]


def merc(lat, lon):
    s = math.sin(math.radians(lat))
    return (lon + 180) / 360, 0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)


xs = [merc(a, b)[0] for a, b in rota]
ys = [merc(a, b)[1] for a, b in rota]
# A rota ocupa ~58% da largura, na faixa de baixo do topo (o texto fica em cima).
escala = HERO_W * 0.58 / (max(xs) - min(xs))
cx = (min(xs) + max(xs)) / 2
cy = (min(ys) + max(ys)) / 2
ALVO_X, ALVO_Y = HERO_W * 0.37, HERO_H * 0.68


def P(lat, lon):
    x, y = merc(lat, lon)
    return (x - cx) * escala + ALVO_X, (y - cy) * escala + ALVO_Y


def dentro(p, folga=2):
    return -folga < p[0] < HERO_W + folga and -folga < p[1] < HERO_H + folga


ruas = []
for t in d["trechos"]:
    a, b = P(t[0], t[1]), P(t[2], t[3])
    if dentro(a) or dentro(b):
        ruas.append(f"M{a[0]:.2f} {a[1]:.2f}L{b[0]:.2f} {b[1]:.2f}")
caminho_rota = "M" + "L".join(f"{x:.2f} {y:.2f}" for x, y in (P(a, b) for a, b in rota))


# Semáforos da rota: a até 15 m do traçado, um por cruzamento (agrupados em 50 m).
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
        if all(metros(pt, o) > 120 for o in na_rota):
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


sinais = "".join(semaforo(*P(*pt), k=1.05) for pt in na_rota)
o, f = P(*rota[0]), P(*rota[-1])
pinos = (f'<circle cx="{o[0]:.2f}" cy="{o[1]:.2f}" r="0.75" fill="#3DDC84" stroke="#0E1215" stroke-width="0.3"/>'
         f'<rect x="{f[0] - 0.75:.2f}" y="{f[1] - 0.75:.2f}" width="1.5" height="1.5" rx="0.25" fill="#E0525C" stroke="#0E1215" stroke-width="0.3"/>')

MAPA = f"""<svg class="mapa" viewBox="0 0 {HERO_W} {HERO_H}" preserveAspectRatio="xMidYMid slice">
  <defs>
    <filter id="brilho" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="0.55"/></filter>
    <linearGradient id="vela" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#0E1215" stop-opacity=".88"/>
      <stop offset=".4" stop-color="#0E1215" stop-opacity=".35"/>
      <stop offset="1" stop-color="#0E1215" stop-opacity=".1"/>
    </linearGradient>
  </defs>
  <path d="{''.join(ruas)}" stroke="#3A4854" stroke-width="0.11" fill="none" stroke-linecap="round"/>
  <rect width="{HERO_W}" height="{HERO_H}" fill="url(#vela)"/>
  <path d="{caminho_rota}" stroke="#3DDC84" stroke-width="1.1" fill="none" opacity=".45" filter="url(#brilho)" stroke-linejoin="round" stroke-linecap="round"/>
  <path d="{caminho_rota}" stroke="#3DDC84" stroke-width="0.42" fill="none" stroke-linejoin="round" stroke-linecap="round"/>
  {sinais}
  {pinos}
</svg>"""

# ------------------------------------------------------------------- QR
img = qrcode.make(REPO, image_factory=qrcode.image.svg.SvgPathImage, box_size=10, border=0)
buf = io.BytesIO()
img.save(buf)
QR = buf.getvalue().decode()
QR = QR[QR.index("<svg"):]


def foto(nome):
    return "data:image/png;base64," + base64.b64encode(open(f"{CAPTURAS}/{nome}", "rb").read()).decode()


def fonte(peso):
    return f"""@font-face {{ font-family: 'Montserrat'; font-weight: {peso};
      src: url('file://{FONTES}/Montserrat-{peso}.ttf') format('truetype'); }}"""


# ---------------------------------------------------------- ícones (traço)
ICONES = {
    "mapa": '<path d="m9 4-6 2.5v13.5l6-2.5 6 2.5 6-2.5V4l-6 2.5z"/><path d="M9 4v13.5M15 6.5V20"/>',
    "rota": '<circle cx="6" cy="19" r="2.5"/><circle cx="18" cy="5" r="2.5"/><path d="M8.5 19H16a3.5 3.5 0 0 0 0-7H8a3.5 3.5 0 0 1 0-7h7.5"/>',
    "semaforo": '<rect x="8" y="2.5" width="8" height="19" rx="3"/><circle cx="12" cy="7" r="1.4"/><circle cx="12" cy="12" r="1.4"/><circle cx="12" cy="17" r="1.4"/>',
    "carro": '<path d="M5 17h14v-4.5l-1.8-4.7A2 2 0 0 0 15.3 6.5H8.7a2 2 0 0 0-1.9 1.3L5 12.5z"/><path d="M5 12.5h14"/><circle cx="8" cy="17" r="1.6"/><circle cx="16" cy="17" r="1.6"/>',
    "grade": '<rect x="3.5" y="3.5" width="17" height="17" rx="2"/><path d="M12 3.5v17M3.5 12h17M12 7.75h8.5M16.25 3.5V12"/>',
    "escudo": '<path d="M12 3 4.5 6v5.5c0 4.6 3.2 8.4 7.5 9.5 4.3-1.1 7.5-4.9 7.5-9.5V6z"/><path d="m9 12 2.2 2.2L15.5 10"/>',
}


def icone(nome):
    return (f'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
            f'stroke-linecap="round" stroke-linejoin="round">{ICONES[nome]}</svg>')


LOGO = """<svg viewBox="0 0 512 512"><circle cx="256" cy="256" r="236" fill="#1C2024" stroke="#3C444B" stroke-width="12"/>
<circle cx="256" cy="256" r="190" fill="none" stroke="#2D3338" stroke-width="5"/>
<g stroke="#5A646D" stroke-width="7">""" + "".join(
    f'<line x1="256" y1="40" x2="256" y2="{70 if i % 2 == 0 else 58}" transform="rotate({i * 45} 256 256)"/>' for i in range(8)
) + """</g><g transform="rotate(32 256 256)">
<polygon points="256,86 286,256 256,232 226,256" fill="#E0525C"/>
<polygon points="256,426 226,256 256,280 286,256" fill="#3C444B"/></g>
<circle cx="256" cy="256" r="19" fill="#B08D57"/></svg>"""

TOPICOS = [
    ("mapa", "Mapa real de São Paulo", "As ruas do OpenStreetMap: a cidade inteira, com 6,8 mil semáforos."),
    ("rota", "Rota mais rápida", "A* com marcos (ALT). O Dijkstra confere que a rota é a ótima."),
    ("semaforo", "Semáforo no cálculo", "Espera média r²/2c somada a cada rua que chega ao cruzamento."),
    ("carro", "Motorista que chega antes", "Busca reversa no grafo: tempo real pelas ruas, não linha reta."),
    ("grade", "Busca espacial rápida", "Quadtree encontra os motoristas próximos em O(log n + k)."),
    ("escudo", "Corrida sem atalhos", "Os estados da corrida formam um grafo acíclico, validado por Kahn."),
]
NUMEROS = [
    ("137 mil", "cruzamentos reais de São Paulo"),
    ("11×", "mais rápido que o Dijkstra"),
    ("19 ms", "para calcular uma rota"),
    ("67%", "das rotas mudam com os semáforos"),
]
EQUIPE = [("Bianca Murcela Mascamudo", "8261104797"), ("Carolina Chaves", "826182449"),
          ("Carolina Yukari Kague", "8261110898"), ("Gabryela Araujo", "826199094"),
          ("Kauan Sousa", "8261113181"), ("Wildiner Lopes", "8261102715")]
TECNOLOGIAS = ["React", "TypeScript", "Python · FastAPI", "MySQL", "OpenStreetMap", "Railway · Vercel"]

topicos = "".join(f"""<div class="topico"><span class="topico-icone">{icone(i)}</span>
  <div><h3>{t}</h3><p>{x}</p></div></div>""" for i, t, x in TOPICOS)
numeros = "".join(f'<div class="numero"><b>{n}</b><span>{r}</span></div>' for n, r in NUMEROS)
equipe = "".join(f"<li>{n} <small>RA {ra}</small></li>" for n, ra in EQUIPE)
tecnologias = "".join(f"<span>{t}</span>" for t in TECNOLOGIAS)

HTML = f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>Banner TrueCompass</title>
<style>
{fonte(400)} {fonte(600)} {fonte(700)} {fonte(800)}
@page {{ size: 90cm 120cm; margin: 0; }}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
html, body {{ width: 90cm; height: 120cm; }}
body {{ font-family: 'Montserrat', 'Liberation Sans', Arial, sans-serif; color: #15191C; background: #F3F2EE;
        -webkit-print-color-adjust: exact; print-color-adjust: exact; overflow: hidden; position: relative; }}

/* ---------------- topo escuro, com o mapa real ao fundo */
.heroi {{ position: absolute; inset: 0 0 auto 0; height: {HERO_H}cm; background: #0E1215; color: #fff; overflow: hidden; }}
.mapa {{ position: absolute; inset: 0; width: 100%; height: 100%; }}
.faixa {{ position: absolute; top: 0; left: 0; right: 0; height: 0.6cm;
          background: linear-gradient(90deg, #E0525C 0 25%, #3DDC84 25% 50%, #B08D57 50% 75%, #5A646D 75%); }}
.instituicao {{ position: absolute; top: 2.6cm; left: 5cm; right: 5cm; display: flex; justify-content: space-between;
                font: 600 24pt Montserrat; letter-spacing: .12em; text-transform: uppercase; color: #9AA6B0; }}
.marca {{ position: absolute; top: 7.4cm; left: 5cm; display: flex; align-items: center; gap: 2.4cm; }}
.marca .logo {{ width: 14cm; height: 14cm; filter: drop-shadow(0 .6cm 1.2cm rgba(0,0,0,.55)); }}
.marca h1 {{ font: 800 80pt Montserrat; letter-spacing: -.02em; line-height: 1; }}
.marca h1 span {{ color: #E0525C; }}
.marca .lema {{ margin-top: .9cm; font: 600 40pt Montserrat; color: #3DDC84; }}
.marca .resumo {{ margin-top: 1.1cm; max-width: 40cm; font: 400 25pt/1.45 Montserrat; color: #D6DCE0; }}

.celular {{ position: absolute; right: 6.5cm; top: 5.6cm; width: 15.5cm; border-radius: 2.6cm; padding: .55cm;
            background: #050607; box-shadow: 0 1.6cm 3cm rgba(0,0,0,.6), 0 0 0 .12cm #2A3138; transform: rotate(3deg); }}
.celular img {{ display: block; width: 100%; border-radius: 2.05cm; }}

/* ---------------- números grandes, sobrepostos à borda do topo */
.numeros {{ position: absolute; top: {HERO_H - 5}cm; left: 5cm; right: 5cm; display: grid; grid-template-columns: repeat(4, 1fr);
            gap: 1.4cm; }}
.numero {{ background: #fff; border-radius: 1cm; padding: 1.5cm 1.4cm 1.4cm; box-shadow: 0 .5cm 1.4cm rgba(16,22,26,.16);
           border-top: .35cm solid #2F8A4C; }}
.numero:nth-child(2) {{ border-top-color: #E0525C; }} .numero:nth-child(3) {{ border-top-color: #B08D57; }}
.numero:nth-child(4) {{ border-top-color: #3C444B; }}
.numero b {{ display: block; font: 800 72pt Montserrat; letter-spacing: -.02em; line-height: 1; color: #15191C; }}
.numero span {{ display: block; margin-top: .6cm; font: 600 24pt/1.3 Montserrat; color: #5F6770; }}

/* ---------------- tópicos */
.conteudo {{ position: absolute; left: 5cm; right: 5cm; top: {HERO_H + 8.8}cm; }}
#app {{ margin-top: 2.2cm; }}
.secao h2 {{ font: 800 40pt Montserrat; letter-spacing: -.01em; display: flex; align-items: center; gap: .9cm; }}
.secao h2::before {{ content: ''; width: 2.2cm; height: .45cm; border-radius: .3cm; background: #2F8A4C; }}
.topicos {{ margin-top: 1.3cm; display: grid; grid-template-columns: 1fr 1fr; gap: 1cm 1.6cm; }}
.topico {{ display: flex; gap: 1.2cm; align-items: center; background: #fff; border-radius: 1cm; padding: 1.1cm 1.5cm;
           box-shadow: 0 .3cm .9cm rgba(16,22,26,.08); }}
.topico-icone {{ flex: none; width: 3.4cm; height: 3.4cm; border-radius: .9cm; background: #E4F1E8; color: #2F8A4C;
                 display: grid; place-items: center; }}
.topico:nth-child(3) .topico-icone, .topico:nth-child(6) .topico-icone {{ background: #F9E3E5; color: #C5303E; }}
.topico-icone svg {{ width: 1.9cm; height: 1.9cm; }}
.topico h3 {{ font: 700 32pt Montserrat; letter-spacing: -.01em; }}
.topico p {{ margin-top: .35cm; font: 400 24pt/1.4 Montserrat; color: #4A535B; }}

/* ---------------- o app */
.telas {{ margin-top: 1.3cm; display: grid; grid-template-columns: repeat(3, 1fr); gap: 2.4cm; align-items: start; }}
.tela {{ text-align: center; }}
.tela .moldura {{ margin: 0 auto; width: 11.2cm; border-radius: 2.2cm; padding: .45cm; background: #0B0D0F;
                 box-shadow: 0 .8cm 1.8cm rgba(16,22,26,.25); }}
.tela .moldura img {{ display: block; width: 100%; border-radius: 1.8cm; aspect-ratio: 1170 / 2100; object-fit: cover; object-position: top; }}
.tela span {{ display: block; margin-top: .7cm; font: 600 24pt Montserrat; color: #3B434A; }}

/* ---------------- rodapé */
.rodape {{ position: absolute; left: 0; right: 0; bottom: 0; height: 16cm; background: #0E1215; color: #fff;
           padding: 2.2cm 5cm 0; display: grid; grid-template-columns: 1.55fr 1fr auto; gap: 3cm; }}
.rodape h4 {{ font: 700 24pt Montserrat; letter-spacing: .14em; text-transform: uppercase; color: #3DDC84; margin-bottom: .9cm; }}
.rodape ul {{ list-style: none; columns: 2; column-gap: 1.6cm; }}
.rodape li {{ font: 600 24pt/1.75 Montserrat; color: #E8ECEF; break-inside: avoid; }}
.rodape li small {{ font: 400 21pt Montserrat; color: #8C99A4; margin-left: .3cm; }}
.rodape .orientador {{ margin-top: 1cm; font: 600 25pt Montserrat; color: #fff; }}
.rodape .orientador small {{ display: block; margin-top: .35cm; font: 400 22pt Montserrat; color: #8C99A4; }}
.chips {{ display: flex; flex-wrap: wrap; gap: .55cm; }}
.chips span {{ font: 600 22pt Montserrat; padding: .45cm .9cm; border-radius: 1cm; background: #1C2329; color: #D6DCE0;
               border: .06cm solid #2E3943; }}
.creditos {{ margin-top: 1.2cm; font: 400 21pt/1.45 Montserrat; color: #8C99A4; }}
.qr {{ text-align: center; }}
.qr .quadro {{ width: 10.5cm; height: 10.5cm; background: #fff; border-radius: .8cm; padding: .8cm; }}
.qr .quadro svg {{ width: 100%; height: 100%; }}
.qr span {{ display: block; margin-top: .7cm; font: 600 22pt Montserrat; color: #D6DCE0; }}
</style></head><body>

<section class="heroi">
  {MAPA}
  <div class="faixa"></div>
  <div class="instituicao"><span>Universidade São Judas Tadeu</span><span>Matemática Computacional Aplicada · 2026/2</span></div>
  <div class="marca">
    <div class="logo">{LOGO}</div>
    <div>
      <h1>True<span>Compass</span></h1>
      <div class="lema">Sua corrida, no caminho certo.</div>
      <p class="resumo">App de mobilidade urbana que encontra a rota mais rápida e o motorista que chega antes, no mapa real de São Paulo.</p>
    </div>
  </div>
  <div class="celular"><img src="{foto('cap_previa.png')}" alt=""></div>
</section>

<div class="numeros">{numeros}</div>

<div class="conteudo">
<section class="secao" id="como"><h2>Como funciona</h2>
  <div class="topicos">{topicos}</div>
</section>

<section class="secao" id="app"><h2>O app</h2>
  <div class="telas">
    <div class="tela"><div class="moldura"><img src="{foto('cap_login.png')}" alt=""></div><span>Login seguro</span></div>
    <div class="tela"><div class="moldura"><img src="{foto('cap_oferta.png')}" alt=""></div><span>Motorista aceita ou recusa</span></div>
    <div class="tela"><div class="moldura"><img src="{foto('cap_inicio_escuro.png')}" alt=""></div><span>Mapa real, tema escuro</span></div>
  </div>
</section>
</div>

<footer class="rodape">
  <div>
    <h4>Equipe</h4>
    <ul>{equipe}</ul>
    <p class="orientador">Orientador: Prof. Raulison Resende<small>Matemática Computacional Aplicada (0064481)</small></p>
  </div>
  <div>
    <h4>Tecnologias</h4>
    <div class="chips">{tecnologias}</div>
    <p class="creditos">Dados de mapa: © OpenStreetMap, OpenMapTiles e OpenFreeMap.</p>
  </div>
  <div class="qr"><div class="quadro">{QR}</div><span>Código no GitHub</span></div>
</footer>
</body></html>"""

open(SAIDA, "w").write(HTML)
print("ruas:", len(ruas), "| semáforos na rota:", len(na_rota), "| html:", round(len(HTML) / 1e6, 1), "MB")
