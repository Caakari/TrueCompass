import { useEffect, useRef, useState } from 'react'
import { urlDoWebSocket } from '../api'

/**
 * Acompanha uma corrida pelo WebSocket.
 *
 * Devolve { estado, posicaoMotorista, conectado, eventos }. O backend publica
 * dois tipos de evento: "estado" (transição no DAG) e "posicao" (ping de GPS
 * do motorista durante a corrida).
 */
export function usarCorridaAoVivo(corridaId, token) {
  const [estado, definirEstado] = useState(null)
  const [posicaoMotorista, definirPosicao] = useState(null)
  const [conectado, definirConectado] = useState(false)
  const [eventos, definirEventos] = useState([])
  const socketRef = useRef(null)

  useEffect(() => {
    if (!corridaId || !token) return

    const socket = new WebSocket(urlDoWebSocket(corridaId, token))
    socketRef.current = socket
    let vivo = true

    socket.onopen = () => vivo && definirConectado(true)
    socket.onclose = () => vivo && definirConectado(false)
    socket.onerror = () => vivo && definirConectado(false)

    socket.onmessage = (evento) => {
      if (!vivo) return
      let dados
      try { dados = JSON.parse(evento.data) } catch { return }

      if (dados.evento === 'estado') definirEstado(dados)
      if (dados.evento === 'posicao') definirPosicao({ lat: dados.lat, lon: dados.lon })
      // Mantém apenas os últimos eventos: o histórico completo cresceria sem
      // limite numa corrida longa, com um ping de GPS a cada poucos segundos.
      definirEventos((antes) => [...antes.slice(-24), dados])
    }

    // Ping periódico: o endpoint aguarda mensagens do cliente para manter a
    // conexão, e proxies intermediários encerram conexões ociosas.
    const batida = setInterval(() => {
      if (socket.readyState === WebSocket.OPEN) socket.send('ping')
    }, 25000)

    return () => {
      vivo = false
      clearInterval(batida)
      socket.close()
    }
  }, [corridaId, token])

  return { estado, posicaoMotorista, conectado, eventos }
}
