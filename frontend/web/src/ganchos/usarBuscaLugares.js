import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api'

const ESPERA_DIGITACAO_MS = 280

/**
 * Autocompletar de lugares reais.
 *
 * - Espera a pessoa parar de digitar (debounce) antes de consultar.
 * - Cancela a requisição anterior quando chega uma letra nova: sem isso, uma
 *   resposta lenta de "pau" poderia sobrescrever a de "paulista".
 * - `buscarCompleto()` é o Enter: consulta também o Nominatim, que acerta
 *   melhor nomes populares mas não pode ser usado a cada tecla.
 */
export function usarBuscaLugares(token, texto, perto) {
  const [resultados, definirResultados] = useState([])
  const [carregando, definirCarregando] = useState(false)
  const [completo, definirCompleto] = useState(false)
  const [erro, definirErro] = useState(null)
  const controleRef = useRef(null)
  const pertoRef = useRef(perto)
  pertoRef.current = perto

  const consultar = useCallback(async (consulta, modoCompleto) => {
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
      if (falha.name === 'AbortError') return
      definirErro(falha.message)
      definirResultados([])
    } finally {
      if (!controle.signal.aborted) definirCarregando(false)
    }
  }, [token])

  useEffect(() => {
    const consulta = texto.trim()
    if (consulta.length < 2) {
      controleRef.current?.abort()
      definirResultados([])
      definirCarregando(false)
      definirCompleto(false)
      definirErro(null)
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
