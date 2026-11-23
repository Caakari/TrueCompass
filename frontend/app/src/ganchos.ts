import { useCallback, useEffect, useRef, useState } from 'react'
import { api, urlDoWebSocket } from './api'
import type { EstadoCorrida, EventoAoVivo, Lugar, Mensagem, Ponto } from './tipos'

// ===================================================================== GPS

export type EstadoGps = 'aguardando' | 'ok' | 'negado' | 'indisponivel'

/**
 * GPS do aparelho, acompanhado continuamente. Geolocalização exige contexto
 * seguro (https ou localhost); fora dele o estado é 'indisponivel'.
 */
export function useLocalizacao() {
  const [posicao, definirPosicao] = useState<(Ponto & { precisao: number }) | null>(null)
  const [estado, definirEstado] = useState<EstadoGps>('aguardando')

  useEffect(() => {
    if (!('geolocation' in navigator) || !window.isSecureContext) {
      definirEstado('indisponivel')
      return
    }
    const id = navigator.geolocation.watchPosition(
      ({ coords }) => {
        definirPosicao({ lat: coords.latitude, lon: coords.longitude, precisao: coords.accuracy })
        definirEstado('ok')
      },
      (erro) => definirEstado(erro.code === erro.PERMISSION_DENIED ? 'negado' : 'indisponivel'),
      { enableHighAccuracy: true, maximumAge: 10_000, timeout: 20_000 },
    )
    return () => navigator.geolocation.clearWatch(id)
  }, [])

  return { posicao, estado }
}

// ===================================================== busca de lugares

const ESPERA_DIGITACAO_MS = 260

/**
 * Autocompletar de lugares reais.
 * - Espera a pessoa parar de digitar antes de consultar (debounce).
 * - Cancela a requisição anterior a cada letra: sem isso, a resposta lenta
 *   de "pau" poderia sobrescrever a de "paulista".
 * - `buscarCompleto()` é o Enter: inclui o Nominatim, que acerta melhor nomes
 *   populares mas, pela política de uso dele, não pode rodar a cada tecla.
 */
export function useBuscaLugares(token: string, texto: string, perto: Ponto | null) {
  const [resultados, definirResultados] = useState<Lugar[]>([])
  const [carregando, definirCarregando] = useState(false)
  const [completo, definirCompleto] = useState(false)
  const [erro, definirErro] = useState<string | null>(null)
  const controleRef = useRef<AbortController | null>(null)
  const pertoRef = useRef(perto)
  pertoRef.current = perto

  const consultar = useCallback(async (consulta: string, modoCompleto: boolean) => {
    controleRef.current?.abort()
    const controle = new AbortController()
    controleRef.current = controle
    definirCarregando(true)
    definirErro(null)
    try {
      const { lugares } = await api.buscarLugares(token, consulta, {
        perto: pertoRef.current, completo: modoCompleto, sinal: controle.signal,
      })
      if (controle.signal.aborted) return
      definirResultados(lugares)
      definirCompleto(modoCompleto)
    } catch (falha) {
      if ((falha as Error).name === 'AbortError') return
      definirErro((falha as Error).message)
      definirResultados([])
    } finally {
      if (!controle.signal.aborted) definirCarregando(false)
    }
  }, [token])

  useEffect(() => {
    const consulta = texto.trim()
    if (consulta.length < 2) {
      controleRef.current?.abort()
      definirResultados([]); definirCarregando(false); definirCompleto(false); definirErro(null)
      return
    }
    definirCarregando(true)
    const id = setTimeout(() => consultar(consulta, false), ESPERA_DIGITACAO_MS)
    return () => clearTimeout(id)
  }, [texto, consultar])

  useEffect(() => () => controleRef.current?.abort(), [])

  const buscarCompleto = useCallback(() => {
    const consulta = texto.trim()
    if (consulta.length >= 2) consultar(consulta, true)
  }, [texto, consultar])

  return { resultados, carregando, completo, erro, buscarCompleto }
}

// ===================================================== corrida ao vivo

/**
 * Acompanha uma corrida pelo WebSocket: transições do DAG ("estado") e GPS do
 * motorista ("posicao"). Reconecta sozinho se a conexão cair — no celular,
 * trocar de rede ou bloquear a tela derruba o socket.
 */
export function useCorridaAoVivo(corridaId: number | null, token: string) {
  const [estado, definirEstado] = useState<EstadoCorrida | null>(null)
  const [versao, definirVersao] = useState(0)
  const [posicaoMotorista, definirPosicao] = useState<Ponto | null>(null)
  const [conectado, definirConectado] = useState(false)
  // Última mensagem do chat que chegou pelo socket (o chat e o contador de
  // não lidas reagem a ela).
  const [mensagem, definirMensagem] = useState<Mensagem | null>(null)

  useEffect(() => {
    definirEstado(null)
    definirPosicao(null)
    definirMensagem(null)
    if (!corridaId || !token) return
    let vivo = true
    let socket: WebSocket | null = null
    let religar: ReturnType<typeof setTimeout> | undefined
    let tentativas = 0

    const abrir = () => {
      socket = new WebSocket(urlDoWebSocket(corridaId, token))
      socket.onopen = () => { tentativas = 0; if (vivo) definirConectado(true) }
      socket.onclose = () => {
        if (!vivo) return
        definirConectado(false)
        // Recuo exponencial, até 15 s.
        religar = setTimeout(abrir, Math.min(15_000, 800 * 2 ** tentativas++))
      }
      socket.onmessage = (evento) => {
        if (!vivo) return
        let dados: EventoAoVivo
        try { dados = JSON.parse(evento.data) } catch { return }
        if (dados.evento === 'estado') { definirEstado(dados.estado); definirVersao((v) => v + 1) }
        if (dados.evento === 'posicao') definirPosicao({ lat: dados.lat, lon: dados.lon })
        if (dados.evento === 'mensagem') definirMensagem(dados.mensagem)
      }
    }
    abrir()

    // Ping periódico: o endpoint espera mensagens do cliente, e proxies
    // intermediários encerram conexões ociosas.
    const batida = setInterval(() => {
      if (socket?.readyState === WebSocket.OPEN) socket.send('ping')
    }, 25_000)

    return () => {
      vivo = false
      clearInterval(batida)
      clearTimeout(religar)
      socket?.close()
    }
  }, [corridaId, token])

  return { estado, versao, posicaoMotorista, conectado, mensagem }
}

// ============================================================ layout

export function useTelaLarga() {
  const consulta = '(min-width: 900px)'
  const [larga, definir] = useState(() => window.matchMedia(consulta).matches)
  useEffect(() => {
    const lista = window.matchMedia(consulta)
    const aoMudar = () => definir(lista.matches)
    lista.addEventListener('change', aoMudar)
    return () => lista.removeEventListener('change', aoMudar)
  }, [])
  return larga
}
