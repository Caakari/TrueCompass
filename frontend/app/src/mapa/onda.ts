import type L from 'leaflet'
import { movimentoReduzido } from '../lib/util'
import type { LatLon } from '../tipos'

/**
 * A ONDA DA BUSCA, desenhada sobre o mapa.
 *
 * O backend devolve, para cada busca, as coordenadas dos nós na ORDEM em que
 * foram alcançados (ver `ordem_de_descoberta` em dominio/servicos/corrida.py).
 * Aqui essa sequência vira animação: os pontos acendem um a um, a frente de
 * onda brilha e o rastro esfria.
 *
 * As duas buscas andam na MESMA velocidade (pontos por segundo). Por isso o
 * A* termina antes: ele tem menos nós para descobrir. E a forma conta a
 * história da documentação — o Dijkstra se espalha em círculo, para todo
 * lado; o A* escorre em gota, apontado ao destino pela heurística.
 *
 * Quando a última onda chega, a rota se desenha (callback) e um COMETA de luz
 * passa a percorrê-la em laço, do embarque ao destino.
 *
 * Tudo num único <canvas> redesenhado por requestAnimationFrame: milhares de
 * pontos como camadas do Leaflet travariam o navegador.
 */

export interface Onda {
  /** Muda a cada replay: é o que dispara a animação de novo. */
  chave: string
  a_estrela: LatLon[]
  dijkstra?: LatLon[]
  /** Toca as duas ondas juntas (comparação) ou só a do A*. */
  comparar: boolean
}

interface Faixa {
  pontos: LatLon[]
  cor: string
  duracao: number
}

const VELOCIDADE_PONTOS_S = 1200       // mesma para as duas buscas
const FRENTE = 90                      // quantos pontos formam a frente brilhante
const ESMAECER_MS = 900
const VOLTA_COMETA_MS = 3200

export class CamadaOnda {
  private ctx: CanvasRenderingContext2D
  private faixas: Faixa[] = []
  private inicio = 0
  private fimOnda = 0
  private aoChegar: (() => void) | null = null
  private rota: LatLon[] = []
  private cometa = false
  private quadro = 0
  private largura = 0
  private altura = 0
  private emZoom = false
  private cores = { aEstrela: '#5FA772', dijkstra: '#B08D57', cometa: '#F3F1E7' }

  constructor(private mapa: L.Map, private canvas: HTMLCanvasElement) {
    this.ctx = canvas.getContext('2d')!
    this.atualizarCores()
    // Durante o zoom animado o Leaflet move os panes com transform CSS; a
    // projeção só fica certa no fim. Some com o canvas nesse intervalo.
    mapa.on('zoomstart', this.aoIniciarZoom)
    mapa.on('zoomend', this.aoTerminarZoom)
    mapa.on('move resize', this.aoMover)
  }

  private aoIniciarZoom = () => { this.emZoom = true; this.canvas.style.opacity = '0' }
  private aoTerminarZoom = () => { this.emZoom = false; this.canvas.style.opacity = '1'; this.agendar() }
  private aoMover = () => this.agendar()

  atualizarCores() {
    const css = getComputedStyle(document.documentElement)
    const ler = (nome: string, alt: string) => css.getPropertyValue(nome).trim() || alt
    this.cores = {
      aEstrela: ler('--onda-a-estrela', '#5FA772'),
      dijkstra: ler('--onda-dijkstra', '#B08D57'),
      cometa: ler('--cometa', '#F3F1E7'),
    }
    this.agendar()
  }

  definirRota(rota: LatLon[]) {
    this.rota = rota
    if (rota.length < 2) this.faixas = []
    this.agendar()
  }

  definirCometa(ligado: boolean) {
    this.cometa = ligado && !movimentoReduzido()
    this.agendar()
  }

  /** Toca a(s) onda(s); `aoChegar` roda quando a última termina. */
  tocar(onda: Onda, aoChegar: () => void) {
    if (movimentoReduzido()) { this.faixas = []; aoChegar(); return }
    const duracao = (n: number) => Math.max(650, (n / VELOCIDADE_PONTOS_S) * 1000)
    this.faixas = []
    if (onda.comparar && onda.dijkstra?.length) {
      this.faixas.push({ pontos: onda.dijkstra, cor: this.cores.dijkstra, duracao: duracao(onda.dijkstra.length) })
    }
    this.faixas.push({ pontos: onda.a_estrela, cor: this.cores.aEstrela, duracao: duracao(onda.a_estrela.length) })
    this.inicio = performance.now()
    this.fimOnda = this.inicio + Math.max(...this.faixas.map((f) => f.duracao))
    this.aoChegar = aoChegar
    this.agendar()
  }

  parar() {
    this.faixas = []
    this.aoChegar = null
    this.agendar()
  }

  destruir() {
    cancelAnimationFrame(this.quadro)
    this.mapa.off('zoomstart', this.aoIniciarZoom)
    this.mapa.off('zoomend', this.aoTerminarZoom)
    this.mapa.off('move resize', this.aoMover)
  }

  // ------------------------------------------------------------- desenho

  private agendar() {
    cancelAnimationFrame(this.quadro)
    this.quadro = requestAnimationFrame(this.desenhar)
  }

  private ajustarTamanho() {
    const dpr = window.devicePixelRatio || 1
    const { clientWidth: l, clientHeight: a } = this.canvas
    if (l !== this.largura || a !== this.altura) {
      this.largura = l
      this.altura = a
      this.canvas.width = Math.round(l * dpr)
      this.canvas.height = Math.round(a * dpr)
    }
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  }

  private projetar(p: LatLon) {
    return this.mapa.latLngToContainerPoint(p)
  }

  private desenhar = (agora: number) => {
    this.ajustarTamanho()
    const ctx = this.ctx
    ctx.clearRect(0, 0, this.largura, this.altura)
    if (this.emZoom) return
    let continuar = false

    // ---- ondas
    if (this.faixas.length) {
      // O carimbo do rAF é o INÍCIO do quadro e pode ser anterior ao
      // performance.now() lido em tocar(): sem o max, o primeiro quadro tem
      // tempo negativo, índice negativo e lê pontos[-n].
      const decorrido = Math.max(0, agora - this.inicio)
      const posFim = agora - this.fimOnda
      const alfaGeral = posFim <= 0 ? 1 : Math.max(0, 1 - posFim / ESMAECER_MS)
      if (posFim >= 0 && this.aoChegar) {
        const chegar = this.aoChegar
        this.aoChegar = null
        chegar()
      }
      if (alfaGeral > 0) {
        for (const faixa of this.faixas) this.desenharFaixa(faixa, decorrido, alfaGeral)
        continuar = true
      } else {
        this.faixas = []
      }
    }

    // ---- cometa percorrendo a rota
    if (this.cometa && this.rota.length > 1 && !this.aoChegar && this.faixas.length === 0) {
      this.desenharCometa(agora)
      continuar = true
    }

    if (continuar) this.quadro = requestAnimationFrame(this.desenhar)
  }

  private desenharFaixa(faixa: Faixa, decorrido: number, alfaGeral: number) {
    const ctx = this.ctx
    const n = faixa.pontos.length
    const k = Math.max(0, Math.min(n, Math.floor(n * Math.min(1, decorrido / faixa.duracao))))
    if (k === 0) return

    // Rastro: o que já foi descoberto, frio e discreto.
    ctx.globalCompositeOperation = 'source-over'
    ctx.fillStyle = faixa.cor
    ctx.globalAlpha = 0.5 * alfaGeral
    const inicioFrente = Math.max(0, k - FRENTE)
    for (let i = 0; i < inicioFrente; i++) {
      const p = this.projetar(faixa.pontos[i])
      ctx.fillRect(p.x - 1.4, p.y - 1.4, 2.8, 2.8)
    }

    // Frente de onda: brilhante, maior, somando luz ('lighter').
    ctx.globalCompositeOperation = 'lighter'
    for (let i = inicioFrente; i < k; i++) {
      const calor = (i - inicioFrente + 1) / FRENTE       // 0 → 1, mais novo = mais quente
      const p = this.projetar(faixa.pontos[i])
      ctx.globalAlpha = (0.15 + 0.55 * calor) * alfaGeral
      ctx.beginPath()
      ctx.arc(p.x, p.y, 1.5 + 3.5 * calor, 0, Math.PI * 2)
      ctx.fill()
    }

    // Ponta da onda: um clarão no nó mais recente.
    if (k < n) {
      const p = this.projetar(faixa.pontos[k - 1])
      const g = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, 26)
      g.addColorStop(0, faixa.cor)
      g.addColorStop(1, 'transparent')
      ctx.globalAlpha = 0.9 * alfaGeral
      ctx.fillStyle = g
      ctx.fillRect(p.x - 26, p.y - 26, 52, 52)
    }
    ctx.globalAlpha = 1
    ctx.globalCompositeOperation = 'source-over'
  }

  private desenharCometa(agora: number) {
    const ctx = this.ctx
    const pts = this.rota.map((p) => this.projetar(p))
    const acumulado = [0]
    for (let i = 1; i < pts.length; i++) {
      acumulado.push(acumulado[i - 1] + Math.hypot(pts[i].x - pts[i - 1].x, pts[i].y - pts[i - 1].y))
    }
    const total = acumulado[acumulado.length - 1]
    if (total < 4) return

    const u = (agora % VOLTA_COMETA_MS) / VOLTA_COMETA_MS
    const cabeca = u * total
    const cauda = Math.max(0, cabeca - Math.min(160, total * 0.22))

    const pontoEm = (d: number) => {
      let i = 1
      while (i < acumulado.length - 1 && acumulado[i] < d) i++
      const t = (d - acumulado[i - 1]) / Math.max(1e-6, acumulado[i] - acumulado[i - 1])
      return { x: pts[i - 1].x + (pts[i].x - pts[i - 1].x) * t, y: pts[i - 1].y + (pts[i].y - pts[i - 1].y) * t }
    }

    // Cauda: segmentos com alfa crescente até a cabeça.
    const passos = 24
    ctx.lineCap = 'round'
    ctx.globalCompositeOperation = 'lighter'
    let anterior = pontoEm(cauda)
    for (let s = 1; s <= passos; s++) {
      const d = cauda + ((cabeca - cauda) * s) / passos
      const atual = pontoEm(d)
      ctx.strokeStyle = this.cores.cometa
      ctx.globalAlpha = (s / passos) ** 2 * 0.85
      ctx.lineWidth = 1.5 + 3.5 * (s / passos)
      ctx.beginPath()
      ctx.moveTo(anterior.x, anterior.y)
      ctx.lineTo(atual.x, atual.y)
      ctx.stroke()
      anterior = atual
    }
    const p = pontoEm(cabeca)
    const g = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, 14)
    g.addColorStop(0, this.cores.cometa)
    g.addColorStop(1, 'transparent')
    ctx.globalAlpha = 1
    ctx.fillStyle = g
    ctx.fillRect(p.x - 14, p.y - 14, 28, 28)
    ctx.globalCompositeOperation = 'source-over'
  }
}
