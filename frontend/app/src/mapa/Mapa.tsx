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
 * 2. TILES SÃO PANO DE FUNDO OPCIONAL. Quem roteia é o nosso grafo; os tiles
 *    só dão contexto. Após 8 falhas seguidas a camada sai e a malha do
 *    algoritmo assume o desenho das ruas (`aoFalharTiles`). São os tiles
 *    padrão do OpenStreetMap, sem chave de API (os da CARTO passaram a
 *    exigir uma); no tema escuro um filtro CSS os inverte (ver mapa.css).
 * 3. MILHARES DE ELEMENTOS EM CANVAS. Semáforos e malha usam o renderizador
 *    canvas, e a malha vai em DUAS camadas multi-segmento (nunca uma por
 *    rua). A rota fica em SVG porque o desenho animado usa stroke-dashoffset.
 * 4. A ONDA DA BUSCA é um <canvas> próprio sobre o mapa (ver onda.ts): são
 *    milhares de pontos redesenhados a cada quadro, inviável como camadas.
 */

const TILES = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
const ATRIBUICAO = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
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
    rota = VAZIO, rotaMotorista = VAZIO, conectores, semaforos = [],
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

  // ------------------------------------------------- tiles, trocados com o tema
  useEffect(() => {
    const mapa = mapaRef.current
    if (!mapa) return
    const tiles = L.tileLayer(TILES, { maxZoom: 19, attribution: ATRIBUICAO, className: 'tiles-osm' })
    let falhas = 0
    tiles.on('tileload', () => { falhas = 0 })
    tiles.on('tileerror', () => {
      if (++falhas === 8 && mapa.hasLayer(tiles)) {
        mapa.removeLayer(tiles)
        propsRef.current.aoFalharTiles?.()
      }
    })
    tiles.addTo(mapa).bringToBack()
    const rua = cor('--mapa-rua', '#6B7680')
    linha('malhaDupla').setStyle({ color: rua })
    linha('malhaUnica').setStyle({ color: rua })
    ondaRef.current?.atualizarCores()
    return () => { mapa.removeLayer(tiles) }
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
