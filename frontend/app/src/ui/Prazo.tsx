import { motion } from 'framer-motion'
import { useEffect, useState } from 'react'

/**
 * Contagem regressiva do prazo da oferta. O total vem do SERVIDOR
 * (`oferta_segundos`, já descontado o tempo que passou lá); aqui só se desconta
 * o que passa no aparelho desde que a resposta chegou. O relógio do celular
 * nunca entra na conta.
 */
export function usePrazo(segundos: number | null, chave: unknown) {
  const [restante, definirRestante] = useState(segundos ?? 0)
  useEffect(() => {
    if (segundos == null) return
    const inicio = performance.now()
    definirRestante(segundos)
    const id = setInterval(() => {
      definirRestante(Math.max(0, segundos - (performance.now() - inicio) / 1000))
    }, 200)
    return () => clearInterval(id)
  }, [segundos, chave])
  return restante
}

export function BarraPrazo({ restante, total }: { restante: number; total: number }) {
  return (
    <div className="barra-prazo" role="timer" aria-label={`${Math.ceil(restante)} segundos para responder`}>
      <motion.span initial={false} animate={{ scaleX: total > 0 ? restante / total : 0 }}
                   transition={{ duration: 0.2, ease: 'linear' }}
                   className={restante <= 5 ? 'urgente' : ''} />
    </div>
  )
}
