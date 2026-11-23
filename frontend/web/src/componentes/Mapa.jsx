import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react'
import { api } from '../api'
import { rumoVerdadeiro } from './Bussola'

/**
 * Mapa em tela cheia (Leaflet).
 *
 * Decisões que evitam armadilhas conhecidas:
 *
 * 1. MARCADORES SEM IMAGEM. Os ícones padrão do Leaflet quebram sob bundler
 *    (as imagens são resolvidas por caminho relativo ao CSS). Usamos
 *    `circleMarker` (SVG) e `divIcon` (HTML/CSS puro) — nenhum asset.
 *
 * 2. TILES SÃO PANO DE FUNDO OPCIONAL. Quem roteia é o nosso grafo; os tiles
 *    (CARTO sobre dados do OpenStreetMap) só dão contexto visual. Após 8
 *    falhas seguidas a camada é removida e a malha do algoritmo assume o
 *    desenho das ruas (`aoFalharTiles`).
 *
 * 3. MILHARES DE ELEMENTOS EM CANVAS. Semáforos (3,5 mil) e a malha (milhares
 *    de trechos, em DUAS camadas multi-segmento, nunca uma por rua) usam o
 *    renderizador canvas. A rota fica em SVG, porque o desenho animado
 *    depende de stroke-dashoffset.
 */

const TILES = {
  claro: 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png',
  escuro: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
}
const ATRIBUICAO = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>'
const ZOOM_SEMAFOROS = 15
const ZOOM_MALHA = 14

function cor(nome, alternativa) {
  const valor = getComputedStyle(document.documentElement).getPropertyValue(nome).trim()
  return valor || alternativa
}

const iconeOrigem = () => L.divIcon({
  className: 'marcador', iconSize: [22, 22], iconAnchor: [11, 11],
  html: '<div class="pino-origem"></div>',
})
const iconeDestino = () => L.divIcon({
  className: 'marcador', iconSize: [28, 38], iconAnchor: [14, 36],
  html: '<div class="pino-destino"><span></span></div>',
})
const iconeUsuario = () => L.divIcon({
  className: 'marcador', iconSize: [20, 20], iconAnchor: [10, 10],
  html: '<div class="ponto-usuario"></div>',
})
const iconeRadar = () => L.divIcon({
  className: 'marcador marcador-radar', iconSize: [240, 240], iconAnchor: [120, 120],
  html: '<div class="radar"><i></i><i></i><i></i></div>',
})
const iconeCarro = () => L.divIcon({
  className: 'marcador', iconSize: [40, 40], iconAnchor: [20, 20],
  html: `<div class="carro"><svg viewBox="0 0 40 40" width="40" height="40">
    <rect x="12" y="6" width="16" height="28" rx="6" class="carro-corpo"/>
    <rect x="14.5" y="11" width="11" height="6" rx="2" class="carro-vidro"/>
    <rect x="14.5" y="24" width="11" height="4.5" rx="1.6" class="carro-vidro"/>
  </svg></div>`,
})

export const Mapa = forwardRef(function Mapa({
  tema = 'escuro', centro, usuario, origem, destino, motorista, radar,
  rota = [], rotaMotorista = [], conectores = [], semaforos = [],
  mostrarMalha = false, margens = { topo: 0, base: 0, esquerda: 0 },
  aoClicar, aoMoverCentro, aoIniciarMovimento, aoFalharTiles,
}, ref) {
  const divRef = useRef(null)
  const mapaRef = useRef(null)
  const camadasRef = useRef({})
  const marcadoresRef = useRef({})
  const callbacksRef = useRef({})
  const margensRef = useRef(margens)
  const [zoom, definirZoom] = useState(15)

  callbacksRef.current = { aoClicar, aoMoverCentro, aoIniciarMovimento, aoFalharTiles }
  margensRef.current = margens

  function opcoesDeEnquadramento() {
    const m = margensRef.current
    return {
      paddingTopLeft: [(m.esquerda || 0) + 28, (m.topo || 0) + 84],
      paddingBottomRight: [28, (m.base || 0) + 28],
      maxZoom: 17,
    }
  }

  useImperativeHandle(ref, () => ({
    voarPara(lat, lon, nivel = 16) {
      mapaRef.current?.flyTo([lat, lon], nivel, { duration: 0.9 })
    },
    enquadrar(pontos) {
      const validos = pontos.filter(Boolean).map((p) => (Array.isArray(p) ? p : [p.lat, p.lon]))
      if (!mapaRef.current || validos.length === 0) return
      if (validos.length === 1) {
        mapaRef.current.flyTo(validos[0], 16, { duration: 0.8 })
        return
      }
      mapaRef.current.flyToBounds(L.latLngBounds(validos), { ...opcoesDeEnquadramento(), duration: 0.9 })
    },
    centro() {
      const c = mapaRef.current?.getCenter()
      return c ? { lat: c.lat, lon: c.lng } : null
    },
  }))

  // ---- criação do mapa (uma vez)
  useEffect(() => {
    if (mapaRef.current || !divRef.current) return
    const mapa = L.map(divRef.current, {
      center: centro ? [centro.lat, centro.lon] : [-23.5505, -46.6333],
      zoom: 15, zoomControl: false, attributionControl: false,
      zoomSnap: 0.25, wheelPxPerZoomLevel: 90, tapTolerance: 12,
    })
    L.control.attribution({ position: 'topright', prefix: false }).addTo(mapa)

    const canvas = L.canvas({ padding: 0.4 })
    camadasRef.current = {
      canvas,
      malhaDupla: L.polyline([], { renderer: canvas, weight: 1.6, interactive: false }),
      malhaUnica: L.polyline([], { renderer: canvas, weight: 1.6, dashArray: '4,4', interactive: false }),
      semaforos: L.layerGroup(),
      conectores: L.polyline([], {
        weight: 3, dashArray: '1,7', lineCap: 'round', className: 'conector', interactive: false,
      }).addTo(mapa),
      rotaMotoristaContorno: L.polyline([], { weight: 8, className: 'rota-motorista-contorno', interactive: false }).addTo(mapa),
      rotaMotorista: L.polyline([], { weight: 4, dashArray: '2,9', lineCap: 'round', className: 'rota-motorista', interactive: false }).addTo(mapa),
      rotaContorno: L.polyline([], { weight: 10, className: 'rota-contorno', interactive: false }).addTo(mapa),
      rota: L.polyline([], { weight: 5.5, className: 'rota-linha', interactive: false }).addTo(mapa),
    }

    mapa.on('click', (e) => callbacksRef.current.aoClicar?.(e.latlng.lat, e.latlng.lng))
    mapa.on('movestart', () => callbacksRef.current.aoIniciarMovimento?.())
    mapa.on('moveend', () => {
      const c = mapa.getCenter()
      callbacksRef.current.aoMoverCentro?.(c.lat, c.lng)
    })
    mapa.on('zoomend', () => definirZoom(mapa.getZoom()))

    mapaRef.current = mapa
    // O contêiner é medido antes do layout final; sem isto o mapa sai cortado.
    setTimeout(() => mapa.invalidateSize(), 80)
    const aoRedimensionar = () => mapa.invalidateSize()
    window.addEventListener('resize', aoRedimensionar)
    return () => {
      window.removeEventListener('resize', aoRedimensionar)
      mapa.remove()
      mapaRef.current = null
    }
  }, [])

  // ---- tiles, trocados com o tema
  useEffect(() => {
    const mapa = mapaRef.current
    if (!mapa) return
    const tiles = L.tileLayer(TILES[tema] ?? TILES.escuro, {
      maxZoom: 20, subdomains: 'abcd', attribution: ATRIBUICAO, detectRetina: true,
    })
    let falhas = 0
    tiles.on('tileload', () => { falhas = 0 })
    tiles.on('tileerror', () => {
      falhas += 1
      if (falhas === 8 && mapa.hasLayer(tiles)) {
        mapa.removeLayer(tiles)
        callbacksRef.current.aoFalharTiles?.()
      }
    })
    tiles.addTo(mapa)
    tiles.bringToBack()

    // Cores das camadas vêm das variáveis CSS do tema.
    const c = camadasRef.current
    const rua = cor('--mapa-rua', '#596470')
    c.malhaDupla.setStyle({ color: rua })
    c.malhaUnica.setStyle({ color: rua })
    return () => { mapa.removeLayer(tiles) }
  }, [tema])

  useEffect(() => {
    if (mapaRef.current && centro && !origem && !usuario) {
      mapaRef.current.setView([centro.lat, centro.lon], 14)
    }
  }, [centro?.lat, centro?.lon])

  // ---- malha do algoritmo (opcional): só o recorte visível
  useEffect(() => {
    const mapa = mapaRef.current
    const c = camadasRef.current
    if (!mapa) return
    if (!mostrarMalha) {
      mapa.removeLayer(c.malhaDupla)
      mapa.removeLayer(c.malhaUnica)
      return
    }
    c.malhaDupla.addTo(mapa)
    c.malhaUnica.addTo(mapa)
    let controle = null
    let espera = null

    async function carregar() {
      if (mapa.getZoom() < ZOOM_MALHA) {
        c.malhaDupla.setLatLngs([]); c.malhaUnica.setLatLngs([])
        return
      }
      controle?.abort()
      controle = new AbortController()
      const b = mapa.getBounds().pad(0.25)
      try {
        const { trechos } = await api.trechos({
          sul: b.getSouth(), norte: b.getNorth(), oeste: b.getWest(), leste: b.getEast(),
        }, 12000, controle.signal)
        const duplas = [], unicas = []
        for (const [lat1, lon1, lat2, lon2, maoUnica] of trechos) {
          (maoUnica ? unicas : duplas).push([[lat1, lon1], [lat2, lon2]])
        }
        c.malhaDupla.setLatLngs(duplas)
        c.malhaUnica.setLatLngs(unicas)
      } catch { /* cancelada ou offline: mantém o que já está desenhado */ }
    }
    const agendar = () => { clearTimeout(espera); espera = setTimeout(carregar, 250) }
    carregar()
    mapa.on('moveend', agendar)
    return () => { mapa.off('moveend', agendar); clearTimeout(espera); controle?.abort() }
  }, [mostrarMalha])

  // ---- semáforos reais: só de perto, senão viram poeira vermelha
  useEffect(() => {
    const grupo = camadasRef.current.semaforos
    if (!grupo) return
    grupo.clearLayers()
    const vermelho = cor('--vermelho', '#D64550')
    for (const sinal of semaforos) {
      L.circleMarker([sinal.lat, sinal.lon], {
        renderer: camadasRef.current.canvas, radius: 3.4, weight: 1.2,
        color: vermelho, fillColor: vermelho, fillOpacity: 0.55,
      }).bindTooltip(
        `Semáforo · espera média ${sinal.atraso_medio.toFixed(1).replace('.', ',')} s`
        + `<br/><small>vermelho ${sinal.vermelho}s em ciclo de ${sinal.ciclo}s → r²/2c</small>`,
        { direction: 'top', offset: [0, -4] },
      ).addTo(grupo)
    }
  }, [semaforos])

  useEffect(() => {
    const mapa = mapaRef.current
    const grupo = camadasRef.current.semaforos
    if (!mapa || !grupo) return
    if (zoom >= ZOOM_SEMAFOROS) grupo.addTo(mapa)
    else mapa.removeLayer(grupo)
  }, [zoom])

  // ---- rota da corrida: enquadra, e só então se desenha
  useEffect(() => {
    const mapa = mapaRef.current
    const { rota: linha, rotaContorno } = camadasRef.current
    if (!mapa || !linha) return
    linha.setLatLngs(rota)
    rotaContorno.setLatLngs(rota)
    if (rota.length < 2) return

    mapa.flyToBounds(L.latLngBounds(rota), { ...opcoesDeEnquadramento(), duration: 0.85 })
    // O traço se desenha do início ao fim, na ordem em que o A* o percorreu.
    // Espera o enquadramento terminar: o Leaflet recalcula o <path> a cada
    // zoom, e um comprimento medido antes ficaria errado depois.
    let feito = false
    const desenhar = () => {
      if (feito) return
      feito = true
      const caminho = linha.getElement?.()
      if (!caminho?.getTotalLength) return
      const total = caminho.getTotalLength()
      caminho.style.transition = 'none'
      caminho.style.strokeDasharray = `${total} ${total}`
      caminho.style.strokeDashoffset = `${total}`
      void caminho.getBoundingClientRect()
      caminho.style.transition = 'stroke-dashoffset 1.2s cubic-bezier(.4,0,.2,1)'
      caminho.style.strokeDashoffset = '0'
      const limpar = () => {
        caminho.style.transition = ''
        caminho.style.strokeDasharray = ''
        caminho.style.strokeDashoffset = ''
      }
      caminho.addEventListener('transitionend', limpar, { once: true })
    }
    mapa.once('moveend', desenhar)
    const reserva = setTimeout(desenhar, 1000)
    return () => { clearTimeout(reserva); mapa.off('moveend', desenhar) }
  }, [rota])

  useEffect(() => {
    const c = camadasRef.current
    c.rotaMotorista?.setLatLngs(rotaMotorista)
    c.rotaMotoristaContorno?.setLatLngs(rotaMotorista)
  }, [rotaMotorista])

  useEffect(() => {
    camadasRef.current.conectores?.setLatLngs(conectores)
  }, [conectores])

  // ---- marcadores: criados uma vez, movidos com setLatLng
  function marcador(chave, ponto, fabricaIcone, opcoes = {}) {
    const mapa = mapaRef.current
    if (!mapa) return null
    const atual = marcadoresRef.current[chave]
    if (!ponto) {
      if (atual) { mapa.removeLayer(atual); delete marcadoresRef.current[chave] }
      return null
    }
    if (atual) { atual.setLatLng([ponto.lat, ponto.lon]); return atual }
    const novo = L.marker([ponto.lat, ponto.lon], {
      icon: fabricaIcone(), keyboard: false, interactive: false, ...opcoes,
    }).addTo(mapa)
    marcadoresRef.current[chave] = novo
    return novo
  }

  useEffect(() => { marcador('usuario', usuario, iconeUsuario, { zIndexOffset: -100 }) }, [usuario?.lat, usuario?.lon])
  useEffect(() => { marcador('origem', origem, iconeOrigem, { zIndexOffset: 200 }) }, [origem?.lat, origem?.lon])
  useEffect(() => { marcador('destino', destino, iconeDestino, { zIndexOffset: 300 }) }, [destino?.lat, destino?.lon])
  useEffect(() => { marcador('radar', radar, iconeRadar, { zIndexOffset: -200 }) }, [radar?.lat, radar?.lon])

  // ---- carro do motorista, interpolado e virado no sentido do movimento
  //
  // O GPS chega em saltos. Mover o marcador de uma vez seria teleporte:
  // interpolamos quadro a quadro, e o carro desliza pela rua. A frente do
  // carro aponta o rumo verdadeiro entre a posição anterior e a nova — a
  // mesma conta da bússola.
  const anteriorRef = useRef(null)
  const quadroRef = useRef(null)
  const rumoRef = useRef(0)

  useEffect(() => {
    if (!motorista) {
      anteriorRef.current = null
      marcador('motorista', null)
      return
    }
    const de = anteriorRef.current
    const carro = marcador('motorista', de ?? motorista, iconeCarro, { zIndexOffset: 400 })
    if (!de) { anteriorRef.current = motorista; return }

    if (de.lat !== motorista.lat || de.lon !== motorista.lon) {
      const novo = rumoVerdadeiro(de.lat, de.lon, motorista.lat, motorista.lon)
      // Giro pelo caminho curto (de 350° para 10° são +20°, não −340°).
      rumoRef.current += ((novo - (rumoRef.current % 360) + 540) % 360) - 180
      const elemento = carro?.getElement()?.querySelector('.carro')
      if (elemento) elemento.style.transform = `rotate(${rumoRef.current}deg)`
    }

    const inicio = performance.now()
    const duracao = 600
    cancelAnimationFrame(quadroRef.current)
    const passo = (agora) => {
      const t = Math.min(1, (agora - inicio) / duracao)
      const suave = t * (2 - t)
      carro?.setLatLng([
        de.lat + (motorista.lat - de.lat) * suave,
        de.lon + (motorista.lon - de.lon) * suave,
      ])
      if (t < 1) quadroRef.current = requestAnimationFrame(passo)
    }
    quadroRef.current = requestAnimationFrame(passo)
    anteriorRef.current = motorista
    return () => cancelAnimationFrame(quadroRef.current)
  }, [motorista?.lat, motorista?.lon])

  return <div ref={divRef} className="mapa" />
})
