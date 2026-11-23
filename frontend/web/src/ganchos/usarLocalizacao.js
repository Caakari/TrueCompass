import { useEffect, useState } from 'react'

/**
 * GPS do aparelho, acompanhado continuamente.
 *
 * Devolve { posicao, estado }, com estado em:
 *   'aguardando'   pedindo permissão / primeira leitura
 *   'ok'           posição disponível
 *   'negado'       a pessoa recusou a permissão
 *   'indisponivel' navegador sem GPS, ou página fora de contexto seguro
 *                  (geolocalização exige https ou localhost)
 */
export function usarLocalizacao(ativo = true) {
  const [posicao, definirPosicao] = useState(null)
  const [estado, definirEstado] = useState('aguardando')

  useEffect(() => {
    if (!ativo) return
    if (!('geolocation' in navigator) || !window.isSecureContext) {
      definirEstado('indisponivel')
      return
    }
    const id = navigator.geolocation.watchPosition(
      ({ coords }) => {
        definirPosicao({ lat: coords.latitude, lon: coords.longitude,
                         precisao: coords.accuracy })
        definirEstado('ok')
      },
      (erro) => definirEstado(erro.code === erro.PERMISSION_DENIED ? 'negado' : 'indisponivel'),
      { enableHighAccuracy: true, maximumAge: 10000, timeout: 20000 },
    )
    return () => navigator.geolocation.clearWatch(id)
  }, [ativo])

  return { posicao, estado }
}
