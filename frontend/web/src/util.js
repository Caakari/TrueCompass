/** Formatação e pequenas utilidades compartilhadas pelas telas. */

export function textoDuracao(segundos) {
  if (segundos == null) return '—'
  const minutos = Math.max(1, Math.round(segundos / 60))
  if (minutos < 60) return `${minutos} min`
  return `${Math.floor(minutos / 60)} h ${String(minutos % 60).padStart(2, '0')}`
}

export function textoDistancia(metros) {
  if (metros == null) return '—'
  if (metros < 1000) return `${Math.max(10, Math.round(metros / 10) * 10)} m`
  return `${(metros / 1000).toFixed(1).replace('.', ',')} km`
}

export function reais(valor) {
  if (valor == null) return '—'
  return valor.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
}

export function horarioDaqui(segundos) {
  return new Date(Date.now() + segundos * 1000)
    .toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
}

export function haversine(a, b) {
  const rad = Math.PI / 180
  const dlat = (b.lat - a.lat) * rad
  const dlon = (b.lon - a.lon) * rad
  const h = Math.sin(dlat / 2) ** 2
    + Math.cos(a.lat * rad) * Math.cos(b.lat * rad) * Math.sin(dlon / 2) ** 2
  return 2 * 6371000 * Math.asin(Math.sqrt(h))
}

export function dentroDaCaixa(ponto, caixa) {
  return Boolean(ponto && caixa)
    && ponto.lat >= caixa.sul && ponto.lat <= caixa.norte
    && ponto.lon >= caixa.oeste && ponto.lon <= caixa.leste
}

/** Toque háptico curto (Android). Silencioso onde não existe. */
export function vibrar(padrao = 10) {
  try { navigator.vibrate?.(padrao) } catch { /* sem vibração */ }
}

export function saudacao() {
  const hora = new Date().getHours()
  if (hora < 5) return 'Boa noite'
  if (hora < 12) return 'Bom dia'
  if (hora < 18) return 'Boa tarde'
  return 'Boa noite'
}

// localStorage pode lançar (navegação privada, cookies bloqueados): todo
// acesso passa por aqui e o app segue funcionando sem persistir.
export function lerArmazenado(chave) {
  try { return JSON.parse(localStorage.getItem(chave)) } catch { return null }
}
export function gravarArmazenado(chave, valor) {
  try {
    if (valor == null) localStorage.removeItem(chave)
    else localStorage.setItem(chave, JSON.stringify(valor))
  } catch { /* segue sem persistir */ }
}
