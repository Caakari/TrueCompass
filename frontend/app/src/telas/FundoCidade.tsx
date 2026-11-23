import { useEffect, useRef } from 'react'
import { api } from '../api'
import { movimentoReduzido } from '../lib/util'
import type { Ponto, Trecho } from '../tipos'

/**
 * Fundo vivo da tela de entrada, feito das RUAS REAIS da malha.
 *
 * 1. Busca no backend os trechos ao redor do centro da área coberta
 *    (endpoint público, não exige login).
 * 2. A cidade se revela do centro para fora, em anel — a mesma forma de uma
 *    busca de Dijkstra se espalhando.
 * 3. Depois, pulsos de luz percorrem trechos ao acaso, como carros.
 *
 * Sem backend no ar, cai num traçado de grade sintético: a tela de entrada
 * não pode depender da rede para existir.
 */

const RAIO_GRAUS = 0.016
const REVELAR_MS = 2600
const PULSOS = 46

interface Segmento { x1: number; y1: number; x2: number; y2: number; d: number; unica: boolean }

function grade(): Trecho[] {
  const saida: Trecho[] = []
  const passo = 0.0012
  for (let i = -14; i <= 14; i++) {
    for (let j = -14; j <= 14; j++) {
      const la = i * passo, lo = j * passo * 1.1
      if (Math.random() > 0.12) saida.push([la, lo, la, lo + passo * 1.1, 0])
      if (Math.random() > 0.12) saida.push([la, lo, la + passo, lo, 0])
    }
  }
  return saida
}

export function FundoCidade({ centro }: { centro: Ponto | null }) {
  const ref = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = ref.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')!
    let vivo = true
    let quadro = 0
    let segmentos: Segmento[] = []
    let estatico: HTMLCanvasElement | null = null
    let inicio = 0
    const reduzido = movimentoReduzido()

    const css = getComputedStyle(document.documentElement)
    const corRua = css.getPropertyValue('--cidade-rua').trim() || 'rgba(160,170,180,.28)'
    const corPulso = css.getPropertyValue('--verde').trim() || '#5FA772'
    const corPulso2 = css.getPropertyValue('--vermelho').trim() || '#E0525C'

    let largura = 0, altura = 0
    const dpr = Math.min(2, window.devicePixelRatio || 1)

    function dimensionar() {
      largura = canvas!.clientWidth
      altura = canvas!.clientHeight
      canvas!.width = largura * dpr
      canvas!.height = altura * dpr
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    }

    function projetar(trechos: Trecho[], c: Ponto) {
      // Equirretangular local: 1° de longitude encolhe por cos(latitude).
      const kx = Math.cos((c.lat * Math.PI) / 180)
      const escala = (Math.max(largura, altura) * 0.62) / RAIO_GRAUS
      const cx = largura / 2, cy = altura * 0.42
      segmentos = trechos.map(([la1, lo1, la2, lo2, unica]) => {
        const x1 = cx + (lo1 - c.lon) * kx * escala, y1 = cy - (la1 - c.lat) * escala
        const x2 = cx + (lo2 - c.lon) * kx * escala, y2 = cy - (la2 - c.lat) * escala
        const mx = (x1 + x2) / 2 - cx, my = (y1 + y2) / 2 - cy
        return { x1, y1, x2, y2, d: Math.hypot(mx, my), unica: unica === 1 }
      }).sort((a, b) => a.d - b.d)
    }

    function preRenderizar() {
      estatico = document.createElement('canvas')
      estatico.width = largura * dpr
      estatico.height = altura * dpr
      const e = estatico.getContext('2d')!
      e.setTransform(dpr, 0, 0, dpr, 0, 0)
      e.strokeStyle = corRua
      e.lineWidth = 1
      e.beginPath()
      for (const s of segmentos) { e.moveTo(s.x1, s.y1); e.lineTo(s.x2, s.y2) }
      e.stroke()
    }

    // Pulsos: cada um percorre um trecho e salta para outro.
    const pulsos = Array.from({ length: PULSOS }, () => ({ s: 0, t: Math.random(), v: 0.006 + Math.random() * 0.012, vermelho: Math.random() < 0.18 }))
    const sortear = () => Math.floor(Math.random() * Math.max(1, segmentos.length * 0.7))

    function desenhar(agora: number) {
      if (!vivo) return
      ctx.clearRect(0, 0, largura, altura)
      const decorrido = agora - inicio
      const maxD = segmentos.length ? segmentos[segmentos.length - 1].d : 1
      const raio = reduzido ? Infinity : (decorrido / REVELAR_MS) * maxD

      if (raio < maxD) {
        // Revelação em anel, com a frente mais clara.
        ctx.lineWidth = 1
        ctx.strokeStyle = corRua
        ctx.beginPath()
        let i = 0
        for (; i < segmentos.length && segmentos[i].d < raio - 60; i++) {
          const s = segmentos[i]
          ctx.moveTo(s.x1, s.y1); ctx.lineTo(s.x2, s.y2)
        }
        ctx.stroke()
        ctx.strokeStyle = corPulso
        ctx.globalAlpha = 0.85
        ctx.lineWidth = 1.6
        ctx.beginPath()
        for (; i < segmentos.length && segmentos[i].d < raio; i++) {
          const s = segmentos[i]
          ctx.moveTo(s.x1, s.y1); ctx.lineTo(s.x2, s.y2)
        }
        ctx.stroke()
        ctx.globalAlpha = 1
      } else {
        if (!estatico) preRenderizar()
        ctx.drawImage(estatico!, 0, 0, largura, altura)

        if (!reduzido && segmentos.length) {
          ctx.globalCompositeOperation = 'lighter'
          for (const p of pulsos) {
            p.t += p.v
            if (p.t >= 1 || p.s === 0) { p.s = sortear(); p.t = 0 }
            const s = segmentos[p.s]
            const x = s.x1 + (s.x2 - s.x1) * p.t, y = s.y1 + (s.y2 - s.y1) * p.t
            const g = ctx.createRadialGradient(x, y, 0, x, y, 7)
            g.addColorStop(0, p.vermelho ? corPulso2 : corPulso)
            g.addColorStop(1, 'transparent')
            ctx.fillStyle = g
            ctx.fillRect(x - 7, y - 7, 14, 14)
          }
          ctx.globalCompositeOperation = 'source-over'
        }
      }
      if (!reduzido || raio < maxD) quadro = requestAnimationFrame(desenhar)
    }

    async function iniciar() {
      dimensionar()
      let trechos: Trecho[] = []
      let c = centro ?? { lat: 0, lon: 0 }
      if (centro) {
        try {
          const r = await api.trechos({
            sul: centro.lat - RAIO_GRAUS, norte: centro.lat + RAIO_GRAUS,
            oeste: centro.lon - RAIO_GRAUS * 1.3, leste: centro.lon + RAIO_GRAUS * 1.3,
          }, 9000)
          trechos = r.trechos
        } catch { /* offline: grade */ }
      }
      if (!vivo) return
      if (trechos.length < 50) { trechos = grade(); c = { lat: 0, lon: 0 } }
      projetar(trechos, c)
      inicio = performance.now()
      quadro = requestAnimationFrame(desenhar)
    }
    iniciar()

    const aoRedimensionar = () => {
      cancelAnimationFrame(quadro)
      estatico = null
      iniciar()
    }
    window.addEventListener('resize', aoRedimensionar)
    return () => {
      vivo = false
      cancelAnimationFrame(quadro)
      window.removeEventListener('resize', aoRedimensionar)
    }
  }, [centro?.lat, centro?.lon])

  return <canvas ref={ref} className="fundo-cidade" aria-hidden="true" />
}
