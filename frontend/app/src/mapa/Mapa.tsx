import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react'
import { api } from '../api'
import { rumoVerdadeiro } from '../lib/util'
import type { LatLon, Ponto, Semaforo, Tema } from '../tipos'
import { CamadaOnda, type Onda } from './onda'

/**
 * Mapa em tela cheia (Leaflet) com a camada de animação do algoritmo.
 *
 * Decisões que evitam armadilhas conhecidas:
 *
 * 1. MARCADORES SEM IMAGEM. Os ícones padrão do Leaflet quebram sob bundler
 *    (as imagens são resolvidas por caminho relativo ao CSS). Usamos
 *    `circleMarker` (SVG) e `divIcon` (HTML/CSS puro) — nenhum asset.
 * 2. O FUNDO É OPCIONAL. Quem roteia é o nosso grafo; o fundo só dá contexto
 *    (e os nomes das ruas). Padrão: mapa VETORIAL do OpenFreeMap, desenhado
 *    pelo MapLibre — Positron no claro e Dark no escuro, um tema escuro de
 *    verdade, não uma inversão de cores. Grátis e sem chave. Se o WebGL ou o
 *    estilo falharem, cai nos tiles raster do OpenStreetMap (filtro cinza);
 *    se esses também falharem 8 vezes seguidas, a malha do algoritmo assume
 *    o desenho das ruas (`aoFalharTiles`).
 * 3. MILHARES DE ELEMENTOS EM CANVAS. Semáforos e malha usam o renderizador
 *    canvas, e a malha vai em DUAS camadas multi-segmento (nunca uma por
 *    rua). A rota fica em SVG porque o desenho animado usa stroke-dashoffset.
 * 4. A ONDA DA BUSCA é um <canvas> próprio sobre o mapa (ver onda.ts): são
 *    milhares de pontos redesenhados a cada quadro, inviável como camadas.
 */

const TILES = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
const ATRIBUICAO = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
const ESTILO_VETORIAL: Record<Tema, string> = {
  claro: 'https://tiles.openfreemap.org/styles/positron',
  escuro: 'https://tiles.openfreemap.org/styles/dark',
}
const ATRIBUICAO_VETORIAL = '<a href="https://openfreemap.org">OpenFreeMap</a> &copy; <a href="https://www.openmaptiles.org/">OpenMapTiles</a> '
  + ATRIBUICAO
/** Sem carregar o estilo nesse prazo, desiste do vetorial e usa os tiles raster. */
const PRAZO_VETORIAL_MS = 15000

/**
 * Rótulos em português: os estilos do OpenMapTiles preferem `name_en`/latim
 * ("Sao Paulo"). Troca o texto de toda camada que mostra NOME por
 * name:pt → name. Camadas de número de casa e afins ficam como estão.
 */
function rotulosEmPortugues(gl: import('maplibre-gl').Map) {
  for (const camada of gl.getStyle().layers ?? []) {
    if (camada.type !== 'symbol') continue
    const texto = gl.getLayoutProperty(camada.id, 'text-field')
    if (texto && JSON.stringify(texto).includes('name')) {
      gl.setLayoutProperty(camada.id, 'text-field', ['coalesce', ['get', 'name:pt'], ['get', 'name']])
    }
  }
}
const ZOOM_SEMAFOROS = 15
const ZOOM_MALHA = 14

export interface Margens { topo?: number; base: number; esquerda: number }

export interface ApiMapa {
  voarPara(p: Ponto, zoom?: number): void
  enquadrar(pontos: Array<Ponto | LatLon>): void
  centro(): Ponto | null
  naTela(p: Ponto): { x: number; y: number } | null
}

interface Props {
  tema: Tema
  centro?: Ponto
  usuario?: Ponto | null
  origem?: Ponto | null
  destino?: Ponto | null
  /** Paradas no caminho, na ordem (marcadores numerados). */
  paradas?: Ponto[]
  motorista?: Ponto | null
  radar?: Ponto | null
  rota?: LatLon[]
  rotaMotorista?: LatLon[]
  conectores?: LatLon[][]
  semaforos?: Semaforo[]
  /** Semáforos da rota exibida: desenhados com o ícone de semáforo. */
  sinaisRota?: LatLon[]
  onda?: Onda | null
  cometa?: boolean
  mostrarMalha?: boolean
  margens: Margens
  aoClicar?: (p: Ponto) => void
  aoMoverCentro?: (p: Ponto) => void
  aoIniciarMovimento?: () => void
  aoFalharTiles?: () => void
}

const VAZIO: LatLon[] = []
const SEM_PARADAS: Ponto[] = []
const MAXIMO_PARADAS = 3

function cor(nome: string, alternativa: string) {
  return getComputedStyle(document.documentElement).getPropertyValue(nome).trim() || alternativa
}

const icone = (html: string, tamanho: [number, number], ancora: [number, number], classe = '') =>
  L.divIcon({ className: `marcador ${classe}`, html, iconSize: tamanho, iconAnchor: ancora })

const ICONES = {
  origem: () => icone('<div class="pino-origem"><i></i></div>', [24, 24], [12, 12]),
  destino: () => icone('<div class="pino-destino"><span></span></div>', [30, 40], [15, 38]),
  parada: (n: number) => icone(`<div class="pino-parada">${n}</div>`, [24, 24], [12, 12]),
  usuario: () => icone('<div class="ponto-usuario"></div>', [20, 20], [10, 10]),
  // Semáforo de pé, com as três luzes e o vermelho aceso; a ponta embaixo
  // marca o cruzamento. Sem gradiente com id: o mesmo SVG se repete em
  // vários marcadores, e um id duplicado quebra quando o primeiro sai.
  sinal: () => icone(`<div class="sinal-rota"><svg viewBox="-10 -36 20 38" width="18" height="34" aria-hidden="true">
      <path d="M0 0 L-3.2 -6.2 L3.2 -6.2 Z" class="sinal-ponta"/>
      <rect x="-7.5" y="-34.5" width="15" height="29.5" rx="5.6" class="sinal-caixa"/>
      <circle cy="-27.6" r="5.4" class="sinal-halo"/>
      <circle cy="-27.6" r="3.3" class="sinal-vermelho"/>
      <circle cy="-19.6" r="3.3" class="sinal-amarelo"/>
      <circle cy="-11.6" r="3.3" class="sinal-verde"/>
      <path d="M-4.2 -30.2 Q0 -33.2 4.2 -30.2 M-4.2 -22.2 Q0 -25.2 4.2 -22.2 M-4.2 -14.2 Q0 -17.2 4.2 -14.2" class="sinal-viseira"/>
      <circle cx="-1.1" cy="-28.9" r=".95" class="sinal-reflexo"/>
    </svg></div>`, [18, 34], [9, 32], 'marcador-sinal'),
  radar: () => icone('<div class="radar"><b></b><i></i><i></i><i></i></div>', [280, 280], [140, 140], 'marcador-radar'),
  carro: () => icone(`<div class="carro"><svg viewBox="0 0 40 40" width="40" height="40">
      <ellipse cx="20" cy="21" rx="10" ry="16" class="carro-sombra"/>
      <rect x="12" y="5" width="16" height="30" rx="6.5" class="carro-corpo"/>
      <rect x="14.3" y="10.5" width="11.4" height="6.5" rx="2" class="carro-vidro"/>
      <rect x="14.3" y="24.5" width="11.4" height="4.6" rx="1.6" class="carro-vidro"/>
      <rect x="13" y="5.6" width="3.2" height="1.8" rx=".9" class="carro-farol"/>
      <rect x="23.8" y="5.6" width="3.2" height="1.8" rx=".9" class="carro-farol"/>
    </svg></div>`, [40, 40], [20, 20]),
}

export const Mapa = forwardRef<ApiMapa, Props>(function Mapa(props, ref) {
  const {
    tema, centro, usuario, origem, destino, paradas = SEM_PARADAS, motorista, radar,
    rota = VAZIO, rotaMotorista = VAZIO, conectores, semaforos = [], sinaisRota = VAZIO,
    onda = null, cometa = false, mostrarMalha = false,
  } = props
  const divRef = useRef<HTMLDivElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const mapaRef = useRef<L.Map | null>(null)
  const ondaRef = useRef<CamadaOnda | null>(null)
  const camadasRef = useRef<Record<string, L.Polyline | L.LayerGroup | L.Canvas>>({})
  const marcadoresRef = useRef<Record<string, L.Marker>>({})
  const propsRef = useRef(props)
  propsRef.current = props
  const [zoom, definirZoom] = useState(15)

  const linha = (nome: string) => camadasRef.current[nome] as L.Polyline

  function opcoesEnquadramento(): L.FitBoundsOptions {
    const m = propsRef.current.margens
    return {
      paddingTopLeft: [(m.esquerda || 0) + 30, (m.topo || 0) + 92],
      paddingBottomRight: [30, (m.base || 0) + 30],
      maxZoom: 17,
    }
  }

  useImperativeHandle(ref, () => ({
    voarPara(p, nivel = 16) { mapaRef.current?.flyTo([p.lat, p.lon], nivel, { duration: 0.9 }) },
    enquadrar(pontos) {
      const mapa = mapaRef.current
      const validos = pontos.filter(Boolean)
        .map((p) => (Array.isArray(p) ? p : [p.lat, p.lon]) as L.LatLngTuple)
      if (!mapa || validos.length === 0) return
      if (validos.length === 1) { mapa.flyTo(validos[0], 16, { duration: 0.8 }); return }
      mapa.flyToBounds(L.latLngBounds(validos), { ...opcoesEnquadramento(), duration: 0.9 })
    },
    centro() {
      const c = mapaRef.current?.getCenter()
      return c ? { lat: c.lat, lon: c.lng } : null
    },
    naTela(p) {
      const mapa = mapaRef.current
      if (!mapa || !divRef.current) return null
      const ponto = mapa.latLngToContainerPoint([p.lat, p.lon])
      const caixa = divRef.current.getBoundingClientRect()
      return { x: caixa.left + ponto.x, y: caixa.top + ponto.y }
    },
  }))

  // ---------------------------------------------------- criação (uma vez)
  useEffect(() => {
    if (mapaRef.current || !divRef.current) return
    const mapa = L.map(divRef.current, {
      center: centro ? [centro.lat, centro.lon] : [-23.5505, -46.6333],
      zoom: 14, zoomControl: false, attributionControl: false,
      zoomSnap: 0.25, wheelPxPerZoomLevel: 90,
    })
    L.control.attribution({ position: 'topright', prefix: false }).addTo(mapa)

    const canvas = L.canvas({ padding: 0.4 })
    const semInteracao = { interactive: false }
    camadasRef.current = {
      canvas,
      malhaDupla: L.polyline([], { renderer: canvas, weight: 1.5, ...semInteracao }),
      malhaUnica: L.polyline([], { renderer: canvas, weight: 1.5, dashArray: '4,4', ...semInteracao }),
      semaforos: L.layerGroup(),
      sinaisRota: L.layerGroup().addTo(mapa),
      conectores: L.polyline([], { weight: 3, dashArray: '1,7', lineCap: 'round', className: 'conector', ...semInteracao }).addTo(mapa),
      rastro: L.polyline([], { weight: 6, lineCap: 'round', className: 'rastro', ...semInteracao }).addTo(mapa),
      rotaMotoristaContorno: L.polyline([], { weight: 8, className: 'rota-motorista-contorno', ...semInteracao }).addTo(mapa),
      rotaMotorista: L.polyline([], { weight: 4, dashArray: '2,9', lineCap: 'round', className: 'rota-motorista', ...semInteracao }).addTo(mapa),
      rotaBrilho: L.polyline([], { weight: 16, className: 'rota-brilho', ...semInteracao }).addTo(mapa),
      rotaContorno: L.polyline([], { weight: 10, className: 'rota-contorno', ...semInteracao }).addTo(mapa),
      rota: L.polyline([], { weight: 5.5, className: 'rota-linha', ...semInteracao }).addTo(mapa),
    }

    mapa.on('click', (e) => propsRef.current.aoClicar?.({ lat: e.latlng.lat, lon: e.latlng.lng }))
    mapa.on('movestart', () => propsRef.current.aoIniciarMovimento?.())
    mapa.on('moveend', () => {
      const c = mapa.getCenter()
      propsRef.current.aoMoverCentro?.({ lat: c.lat, lon: c.lng })
    })
    mapa.on('zoomend', () => definirZoom(mapa.getZoom()))

    ondaRef.current = new CamadaOnda(mapa, canvasRef.current!)
    mapaRef.current = mapa
    // O contêiner é medido antes do layout final; sem isto o mapa sai cortado.
    setTimeout(() => mapa.invalidateSize(), 80)
    const aoRedimensionar = () => mapa.invalidateSize()
    window.addEventListener('resize', aoRedimensionar)
    return () => {
      window.removeEventListener('resize', aoRedimensionar)
      ondaRef.current?.destruir()
      mapa.remove()
      mapaRef.current = null
    }
  }, [])

  // ------------------------------------------- fundo do mapa, trocado com o tema
  useEffect(() => {
    const mapa = mapaRef.current
    if (!mapa) return
    let vivo = true
    let camada: L.Layer | null = null
    let prazo: ReturnType<typeof setTimeout> | undefined

    // Plano B: tiles raster do OSM (o fundo anterior), com o filtro cinza.
    function usarRaster() {
      if (!vivo || !mapa) return
      if (camada) mapa.removeLayer(camada)
      const tiles = L.tileLayer(TILES, { maxZoom: 19, attribution: ATRIBUICAO, className: 'tiles-osm' })
      let falhas = 0
      tiles.on('tileload', () => { falhas = 0 })
      tiles.on('tileerror', () => {
        if (++falhas === 8 && mapa.hasLayer(tiles)) {
          mapa.removeLayer(tiles)
          propsRef.current.aoFalharTiles?.()
        }
      })
      camada = tiles.addTo(mapa)
      tiles.bringToBack()
    }

    // Padrão: vetorial. Carregado sob demanda (o MapLibre é grande e só o
    // mapa precisa dele); qualquer falha antes do 'load' cai no raster.
    Promise.all([import('maplibre-gl'), import('@maplibre/maplibre-gl-leaflet'),
                 import('maplibre-gl/dist/maplibre-gl.css'), import('maplibre-gl/dist/maplibre-gl-worker.mjs?url')])
      .then(([maplibre, { maplibreGL }, , { default: urlDoWorker }]) => {
        if (!vivo) return
        // O MapLibre procura o worker AO LADO do próprio arquivo, e nem o
        // build nem o servidor de desenvolvimento do Vite o copiam para lá:
        // sem isto o vetorial falhava SEMPRE ("Worker failed to load") e o
        // mapa caía no raster. Com `?url`, o Vite publica o worker e dá o endereço.
        maplibre.setWorkerUrl(urlDoWorker)
        const vetorial = maplibreGL({ style: ESTILO_VETORIAL[tema], attributionControl: { customAttribution: ATRIBUICAO_VETORIAL }, interactive: false })
        camada = vetorial.addTo(mapa)
        const gl = vetorial.getMaplibreMap()
        let carregou = false
        const desistir = (motivo: unknown) => {
          if (carregou) return
          clearTimeout(prazo)
          console.warn('[mapa] fundo vetorial indisponível, usando tiles raster:', motivo)
          usarRaster()
        }
        prazo = setTimeout(() => desistir('prazo esgotado'), PRAZO_VETORIAL_MS)
        gl.on('load', () => { carregou = true; clearTimeout(prazo); rotulosEmPortugues(gl) })
        gl.on('error', (e) => desistir(e.error?.message ?? e))
      })
      .catch((e) => { if (vivo) { console.warn('[mapa] MapLibre não carregou:', e); usarRaster() } })

    const rua = cor('--mapa-rua', '#6B7680')
    linha('malhaDupla').setStyle({ color: rua })
    linha('malhaUnica').setStyle({ color: rua })
    ondaRef.current?.atualizarCores()
    return () => { vivo = false; clearTimeout(prazo); if (camada) mapa.removeLayer(camada) }
  }, [tema])

  useEffect(() => {
    if (mapaRef.current && centro && !origem && !usuario) mapaRef.current.setView([centro.lat, centro.lon], 14)
  }, [centro?.lat, centro?.lon])

  // ------------------------------------------ malha do algoritmo (opcional)
  useEffect(() => {
    const mapa = mapaRef.current
    if (!mapa) return
    const dupla = linha('malhaDupla'), unica = linha('malhaUnica')
    if (!mostrarMalha) { mapa.removeLayer(dupla); mapa.removeLayer(unica); return }
    dupla.addTo(mapa); unica.addTo(mapa)
    let controle: AbortController | null = null
    let espera: ReturnType<typeof setTimeout> | undefined

    async function carregar() {
      if (mapa!.getZoom() < ZOOM_MALHA) { dupla.setLatLngs([]); unica.setLatLngs([]); return }
      controle?.abort()
      controle = new AbortController()
      const b = mapa!.getBounds().pad(0.25)
      try {
        const { trechos } = await api.trechos(
          { sul: b.getSouth(), norte: b.getNorth(), oeste: b.getWest(), leste: b.getEast() }, 12000, controle.signal)
        const duplas: L.LatLngTuple[][] = [], unicas: L.LatLngTuple[][] = []
        for (const [la1, lo1, la2, lo2, mao] of trechos) (mao ? unicas : duplas).push([[la1, lo1], [la2, lo2]])
        dupla.setLatLngs(duplas)
        unica.setLatLngs(unicas)
      } catch { /* cancelada ou offline: mantém o desenho anterior */ }
    }
    const agendar = () => { clearTimeout(espera); espera = setTimeout(carregar, 250) }
    carregar()
    mapa.on('moveend', agendar)
    return () => { mapa.off('moveend', agendar); clearTimeout(espera); controle?.abort() }
  }, [mostrarMalha])

  // ------------------------------------------------ semáforos (só de perto)
  useEffect(() => {
    const grupo = camadasRef.current.semaforos as L.LayerGroup
    if (!grupo) return
    grupo.clearLayers()
    const vermelho = cor('--vermelho', '#E0525C')
    for (const s of semaforos) {
      L.circleMarker([s.lat, s.lon], {
        renderer: camadasRef.current.canvas as L.Canvas, radius: 2.6, weight: 1,
        color: vermelho, fillColor: vermelho, fillOpacity: 0.4, opacity: 0.7,
      }).bindTooltip(
        `Semáforo · espera média ${s.atraso_medio.toFixed(1).replace('.', ',')} s`
        + `<br/><small>vermelho ${s.vermelho}s em ciclo de ${s.ciclo}s → r²/2c</small>`,
        { direction: 'top', offset: [0, -4] },
      ).addTo(grupo)
    }
  }, [semaforos])

  useEffect(() => {
    const mapa = mapaRef.current, grupo = camadasRef.current.semaforos as L.LayerGroup
    if (!mapa || !grupo) return
    if (zoom >= ZOOM_SEMAFOROS) grupo.addTo(mapa)
    else mapa.removeLayer(grupo)
  }, [zoom])

  // ------------------------------- semáforos da rota (o ícone, sempre visível)
  // Só os do caminho: o mapa continua limpo. De longe, sinais a menos de
  // 20 px um do outro viram UM ícone, senão a avenida vira uma pilha.
  useEffect(() => {
    const mapa = mapaRef.current, grupo = camadasRef.current.sinaisRota as L.LayerGroup
    if (!mapa || !grupo) return
    grupo.clearLayers()
    const z = mapa.getZoom(), postos: L.Point[] = []
    for (const p of sinaisRota) {
      const px = mapa.project(p, z)
      if (postos.some((q) => q.distanceTo(px) < 20)) continue
      postos.push(px)
      L.marker(p, { icon: ICONES.sinal(), interactive: false, keyboard: false, zIndexOffset: -200 }).addTo(grupo)
    }
  }, [sinaisRota, zoom])

  // --------------------------------------------- rota: enquadra, onda, traço
  const ondaAtualRef = useRef<string | null>(null)
  const baseEnquadrada = useRef(props.margens.base)

  function desenharRota() {
    const caminho = linha('rota').getElement() as SVGPathElement | undefined
    for (const nome of ['rota', 'rotaContorno', 'rotaBrilho']) {
      (linha(nome).getElement() as SVGElement | undefined)?.classList.remove('oculta')
    }
    if (!caminho?.getTotalLength) return
    // O traço se desenha do início ao fim, na ordem em que o A* o percorreu.
    const total = caminho.getTotalLength()
    const contorno = linha('rotaContorno').getElement() as SVGPathElement | undefined
    for (const el of [caminho, contorno]) {
      if (!el) continue
      el.style.transition = 'none'
      el.style.strokeDasharray = `${total} ${total}`
      el.style.strokeDashoffset = `${total}`
      void el.getBoundingClientRect()
      el.style.transition = 'stroke-dashoffset 1.15s cubic-bezier(.65,0,.35,1)'
      el.style.strokeDashoffset = '0'
      el.addEventListener('transitionend', () => {
        el.style.transition = ''; el.style.strokeDasharray = ''; el.style.strokeDashoffset = ''
      }, { once: true })
    }
  }

  function ocultarRota() {
    for (const nome of ['rota', 'rotaContorno', 'rotaBrilho']) {
      (linha(nome).getElement() as SVGElement | undefined)?.classList.add('oculta')
    }
  }

  useEffect(() => {
    const mapa = mapaRef.current
    if (!mapa) return
    for (const nome of ['rota', 'rotaContorno', 'rotaBrilho']) linha(nome).setLatLngs(rota)
    ondaRef.current?.definirRota(rota)
    if (rota.length < 2) { ondaRef.current?.parar(); return }

    const temOnda = Boolean(onda && onda.a_estrela.length)
    if (temOnda) ocultarRota()
    baseEnquadrada.current = propsRef.current.margens.base
    mapa.flyToBounds(L.latLngBounds(rota as L.LatLngTuple[]), { ...opcoesEnquadramento(), duration: 0.85 })

    // Espera o enquadramento terminar: o Leaflet recalcula o <path> a cada
    // zoom, e um comprimento medido antes ficaria errado depois.
    let feito = false
    const seguir = () => {
      if (feito) return
      feito = true
      if (temOnda && onda) {
        ondaAtualRef.current = onda.chave
        ondaRef.current?.tocar(onda, desenharRota)
      } else {
        desenharRota()
      }
    }
    mapa.once('moveend', seguir)
    const reserva = setTimeout(seguir, 1000)
    return () => { clearTimeout(reserva); mapa.off('moveend', seguir) }
  }, [rota])

  // A folha mudou de altura (a prévia carregou, ou foi recolhida): a rota
  // enquadrada antes ficaria escondida atrás dela. Re-enquadra, sem tocar a
  // onda de novo.
  useEffect(() => {
    const mapa = mapaRef.current
    if (!mapa || rota.length < 2) { baseEnquadrada.current = props.margens.base; return }
    if (Math.abs(props.margens.base - baseEnquadrada.current) < 40) return
    const id = setTimeout(() => {
      baseEnquadrada.current = props.margens.base
      mapa.flyToBounds(L.latLngBounds(rota as L.LatLngTuple[]), { ...opcoesEnquadramento(), duration: 0.6 })
    }, 120)
    return () => clearTimeout(id)
  }, [props.margens.base, props.margens.esquerda])

  // Replay da onda (ex.: "comparar com Dijkstra") sem mudar a rota.
  useEffect(() => {
    if (!onda || rota.length < 2 || ondaAtualRef.current === onda.chave) return
    if (ondaAtualRef.current === null) return       // a primeira toca no efeito da rota
    ondaAtualRef.current = onda.chave
    ocultarRota()
    ondaRef.current?.tocar(onda, desenharRota)
  }, [onda?.chave])

  useEffect(() => { ondaRef.current?.definirCometa(cometa) }, [cometa])

  useEffect(() => {
    linha('rotaMotorista').setLatLngs(rotaMotorista)
    linha('rotaMotoristaContorno').setLatLngs(rotaMotorista)
  }, [rotaMotorista])

  useEffect(() => { linha('conectores').setLatLngs(conectores ?? []) }, [conectores])

  // ------------------------------- marcadores: criados uma vez, depois movidos
  function marcador(chave: string, ponto: Ponto | null | undefined,
                    fabrica: () => L.DivIcon, z = 0): L.Marker | null {
    const mapa = mapaRef.current
    if (!mapa) return null
    const atual = marcadoresRef.current[chave]
    if (!ponto) {
      if (atual) { mapa.removeLayer(atual); delete marcadoresRef.current[chave] }
      return null
    }
    if (atual) { atual.setLatLng([ponto.lat, ponto.lon]); return atual }
    const novo = L.marker([ponto.lat, ponto.lon], { icon: fabrica(), keyboard: false, interactive: false, zIndexOffset: z }).addTo(mapa)
    marcadoresRef.current[chave] = novo
    return novo
  }

  useEffect(() => { marcador('usuario', usuario, ICONES.usuario, -100) }, [usuario?.lat, usuario?.lon])
  useEffect(() => { marcador('origem', origem, ICONES.origem, 200) }, [origem?.lat, origem?.lon])
  useEffect(() => { marcador('destino', destino, ICONES.destino, 300) }, [destino?.lat, destino?.lon])
  useEffect(() => {
    for (let i = 0; i < MAXIMO_PARADAS; i++) marcador(`parada${i}`, paradas[i] ?? null, () => ICONES.parada(i + 1), 250)
  }, [paradas.map((p) => `${p.lat},${p.lon}`).join(';')])
  useEffect(() => { marcador('radar', radar, ICONES.radar, -200) }, [radar?.lat, radar?.lon])

  // ------------------------------------------------ carro, interpolado
  //
  // O GPS chega em saltos; mover de uma vez seria teleporte. Interpolamos
  // quadro a quadro e o carro desliza; a frente aponta o rumo verdadeiro
  // entre a posição anterior e a nova (giro sempre pelo caminho curto), e um
  // rastro curto mostra por onde ele acabou de passar.
  const anteriorRef = useRef<Ponto | null>(null)
  const quadroRef = useRef(0)
  const rumoRef = useRef(0)
  const rastroRef = useRef<L.LatLngTuple[]>([])

  useEffect(() => {
    if (!motorista) {
      anteriorRef.current = null
      rastroRef.current = []
      linha('rastro').setLatLngs([])
      marcador('motorista', null, ICONES.carro)
      return
    }
    const de = anteriorRef.current
    const carro = marcador('motorista', de ?? motorista, ICONES.carro, 400)
    if (!de) { anteriorRef.current = motorista; return }

    if (de.lat !== motorista.lat || de.lon !== motorista.lon) {
      const novo = rumoVerdadeiro(de, motorista)
      rumoRef.current += ((((novo - rumoRef.current) % 360) + 540) % 360) - 180
      const el = carro?.getElement()?.querySelector('.carro') as HTMLElement | null
      if (el) el.style.transform = `rotate(${rumoRef.current}deg)`
      rastroRef.current = [...rastroRef.current, [de.lat, de.lon] as L.LatLngTuple].slice(-10)
    }

    const inicio = performance.now()
    cancelAnimationFrame(quadroRef.current)
    const passo = (agora: number) => {
      const t = Math.min(1, (agora - inicio) / 550)
      const s = t * (2 - t)
      const atual: L.LatLngTuple = [de.lat + (motorista.lat - de.lat) * s, de.lon + (motorista.lon - de.lon) * s]
      carro?.setLatLng(atual)
      linha('rastro').setLatLngs([...rastroRef.current, atual])
      if (t < 1) quadroRef.current = requestAnimationFrame(passo)
    }
    quadroRef.current = requestAnimationFrame(passo)
    anteriorRef.current = motorista
    return () => cancelAnimationFrame(quadroRef.current)
  }, [motorista?.lat, motorista?.lon])

  return (
    <div className="mapa-palco">
      <div ref={divRef} className="mapa" />
      <canvas ref={canvasRef} className="camada-onda" aria-hidden="true" />
    </div>
  )
})

export type { Onda }
