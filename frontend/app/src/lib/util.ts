import type { Caixa, Ponto } from '../tipos'

// ------------------------------------------------------------- geometria

const RAD = Math.PI / 180

/** Distância em metros sobre a esfera — a mesma fórmula do backend. */
export function haversine(a: Ponto, b: Ponto): number {
  const dlat = (b.lat - a.lat) * RAD
  const dlon = (b.lon - a.lon) * RAD
  const h = Math.sin(dlat / 2) ** 2
    + Math.cos(a.lat * RAD) * Math.cos(b.lat * RAD) * Math.sin(dlon / 2) ** 2
  return 2 * 6_371_000 * Math.asin(Math.sqrt(h))
}

/**
 * Azimute inicial (rumo verdadeiro) de `a` para `b`, em graus de 0 a 360.
 *
 *   θ = atan2( sen Δλ · cos φ₂ , cos φ₁ · sen φ₂ − sen φ₁ · cos φ₂ · cos Δλ )
 *
 * É a direção em que se parte para seguir o grande círculo — de (0,0) a
 * (10,10) são 44,56°, e não 45°.
 */
export function rumoVerdadeiro(a: Ponto, b: Ponto): number {
  const f1 = a.lat * RAD
  const f2 = b.lat * RAD
  const dl = (b.lon - a.lon) * RAD
  const y = Math.sin(dl) * Math.cos(f2)
  const x = Math.cos(f1) * Math.sin(f2) - Math.sin(f1) * Math.cos(f2) * Math.cos(dl)
  return ((Math.atan2(y, x) / RAD) + 360) % 360
}

const CARDEAIS = ['N', 'NE', 'L', 'SE', 'S', 'SO', 'O', 'NO']
export function pontoCardinal(graus: number): string {
  return CARDEAIS[Math.round((((graus % 360) + 360) % 360) / 45) % 8]
}

export function dentroDaCaixa(ponto: Ponto | null | undefined, caixa: Caixa | null | undefined): boolean {
  return Boolean(ponto && caixa)
    && ponto!.lat >= caixa!.sul && ponto!.lat <= caixa!.norte
    && ponto!.lon >= caixa!.oeste && ponto!.lon <= caixa!.leste
}

export const paraPonto = ([lat, lon]: [number, number]): Ponto => ({ lat, lon })

// -------------------------------------------------------------- formatos

export function textoDuracao(segundos: number | null | undefined): string {
  if (segundos == null) return '—'
  const minutos = Math.max(1, Math.round(segundos / 60))
  if (minutos < 60) return `${minutos} min`
  return `${Math.floor(minutos / 60)} h ${String(minutos % 60).padStart(2, '0')}`
}

export function textoDistancia(metros: number | null | undefined): string {
  if (metros == null) return '—'
  if (metros < 1000) return `${Math.max(10, Math.round(metros / 10) * 10)} m`
  return `${(metros / 1000).toFixed(1).replace('.', ',')} km`
}

export function reais(valor: number | null | undefined): string {
  if (valor == null) return '—'
  return valor.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
}

export const milhar = (n: number) => n.toLocaleString('pt-BR')

export function horarioDaqui(segundos: number): string {
  return new Date(Date.now() + segundos * 1000)
    .toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
}

export function saudacao(): string {
  const hora = new Date().getHours()
  if (hora < 5 || hora >= 18) return 'Boa noite'
  return hora < 12 ? 'Bom dia' : 'Boa tarde'
}

export const esperar = (ms: number) => new Promise<void>((r) => setTimeout(r, ms))

// -------------------------------------------------------------- aparelho

/** Toque háptico (Android). Silencioso onde não existe. */
export function vibrar(padrao: number | number[] = 10) {
  try { navigator.vibrate?.(padrao) } catch { /* sem vibração */ }
}

// localStorage pode lançar (navegação privada, cookies bloqueados): todo
// acesso passa por aqui, e o app segue funcionando sem persistir.
export function lerArmazenado<T>(chave: string): T | null {
  try { return JSON.parse(localStorage.getItem(chave) ?? 'null') as T | null } catch { return null }
}
export function gravarArmazenado(chave: string, valor: unknown) {
  try {
    if (valor == null) localStorage.removeItem(chave)
    else localStorage.setItem(chave, JSON.stringify(valor))
  } catch { /* segue sem persistir */ }
}

export function movimentoReduzido(): boolean {
  return window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
}
