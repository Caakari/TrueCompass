import { AnimatePresence, motion } from 'framer-motion'
import { useState } from 'react'
import { vibrar } from '../lib/util'
import { Botao } from './Movimento'

const ROTULOS = ['', 'Muito ruim', 'Ruim', 'Ok', 'Boa', 'Excelente']

function Estrela({ cheia, tamanho }: { cheia: boolean; tamanho: number }) {
  return (
    <svg viewBox="0 0 24 24" width={tamanho} height={tamanho} aria-hidden="true">
      <path d="M12 2.8l2.8 5.8 6.3.9-4.6 4.4 1.1 6.3L12 17.2 6.4 20.2l1.1-6.3L2.9 9.5l6.3-.9z"
            fill={cheia ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth={1.6} strokeLinejoin="round" />
    </svg>
  )
}

/** Escolha de 1 a 5 estrelas, com teclado (setas) e rótulo do valor. */
export function SeletorEstrelas({ valor, aoMudar, tamanho = 38 }:
  { valor: number; aoMudar: (n: number) => void; tamanho?: number }) {
  const [sobre, definirSobre] = useState(0)
  const mostrado = sobre || valor
  return (
    <div className="seletor-estrelas">
      <div className="estrelas" role="radiogroup" aria-label="Nota de 1 a 5 estrelas"
           onMouseLeave={() => definirSobre(0)}
           onKeyDown={(e) => {
             if (e.key === 'ArrowRight' || e.key === 'ArrowUp') aoMudar(Math.min(5, (valor || 0) + 1))
             if (e.key === 'ArrowLeft' || e.key === 'ArrowDown') aoMudar(Math.max(1, (valor || 2) - 1))
           }}>
        {[1, 2, 3, 4, 5].map((n) => (
          <motion.button key={n} type="button" role="radio" aria-checked={valor === n}
                         aria-label={`${n} ${n === 1 ? 'estrela' : 'estrelas'}`}
                         tabIndex={valor === n || (!valor && n === 1) ? 0 : -1}
                         className={`estrela ${n <= mostrado ? 'acesa' : ''}`}
                         onMouseEnter={() => definirSobre(n)} onClick={() => { vibrar(n * 4); aoMudar(n) }}
                         whileTap={{ scale: 0.8 }}
                         animate={n <= valor ? { scale: [1, 1.25, 1], transition: { delay: n * 0.04 } } : { scale: 1 }}>
            <Estrela cheia={n <= mostrado} tamanho={tamanho} />
          </motion.button>
        ))}
      </div>
      <AnimatePresence mode="wait">
        <motion.span key={mostrado} className="estrelas-rotulo"
                     initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }}>
          {ROTULOS[mostrado] || 'Toque para avaliar'}
        </motion.span>
      </AnimatePresence>
    </div>
  )
}

/** Nota média compacta: ★ 4,8. "Novo" quando ainda não há avaliações. */
export function NotaMedia({ nota, total }: { nota: number | null; total?: number }) {
  if (nota == null) return <span className="nota-media nova">Novo</span>
  return (
    <span className="nota-media" title={total ? `${total} ${total === 1 ? 'avaliação' : 'avaliações'}` : undefined}>
      <Estrela cheia tamanho={13} /> {nota.toFixed(1).replace('.', ',')}
    </span>
  )
}

/**
 * Bloco de avaliação do fim da corrida: estrelas, comentário opcional e
 * envio. Depois de enviado, vira um agradecimento com a nota dada.
 */
export function AvaliarCorrida({ quem, notaDada, enviar }: {
  quem: string
  notaDada: number | null
  enviar: (nota: number, comentario: string) => Promise<void>
}) {
  const [nota, definirNota] = useState(0)
  const [comentario, definirComentario] = useState('')
  const [enviando, definirEnviando] = useState(false)
  const [erro, definirErro] = useState<string | null>(null)

  if (notaDada != null) {
    return (
      <motion.div className="avaliacao-feita" initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }}>
        <div className="estrelas fixas">{[1, 2, 3, 4, 5].map((n) => <span key={n} className={`estrela ${n <= notaDada ? 'acesa' : ''}`}><Estrela cheia={n <= notaDada} tamanho={22} /></span>)}</div>
        <span>Obrigado por avaliar {quem}!</span>
      </motion.div>
    )
  }

  async function aoEnviar() {
    if (!nota) return
    definirEnviando(true)
    definirErro(null)
    try { await enviar(nota, comentario.trim()) } catch (f) { definirErro((f as Error).message) } finally { definirEnviando(false) }
  }

  return (
    <div className="avaliar-corrida">
      <span className="avaliar-titulo">Como foi com {quem}?</span>
      <SeletorEstrelas valor={nota} aoMudar={definirNota} />
      <AnimatePresence>
        {nota > 0 && (
          <motion.div className="avaliar-extra" initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }}
                      exit={{ opacity: 0, height: 0 }}>
            <textarea className="campo-texto" rows={2} maxLength={280} placeholder="Quer comentar algo? (opcional)"
                      value={comentario} onChange={(e) => definirComentario(e.target.value)} />
            {erro && <span className="avaliar-erro">{erro}</span>}
            <Botao variante="secundario" carregando={enviando} onClick={aoEnviar}>Enviar avaliação</Botao>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
