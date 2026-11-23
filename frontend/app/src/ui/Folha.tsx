import { AnimatePresence, animate, motion, useDragControls, useMotionValue, type PanInfo } from 'framer-motion'
import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react'
import { useTelaLarga } from '../ganchos'
import { vibrar } from '../lib/util'
import { Icone } from './Icone'

const ESPIAR_PX = 128
const MOLA = { type: 'spring', stiffness: 360, damping: 34, mass: 0.9 } as const

export interface Margens { base: number; esquerda: number }

/**
 * Folha inferior, o padrão de app de mobilidade: o mapa ocupa a tela toda e
 * o conteúdo sobe de baixo.
 *
 * - Arrastar pela alça recolhe/expande, com mola e a VELOCIDADE do gesto.
 * - A ALTURA acompanha o conteúdo com animação de layout real (height), não
 *   com escala — escala deformaria o texto no meio da transição.
 * - `aoMedir` informa quanto da tela a folha cobre, para o mapa enquadrar a
 *   rota só na parte visível.
 * - Em tela larga vira painel lateral flutuante: o mesmo app, com espaço.
 */
export function Folha({ children, chave, aoMedir, recolher = 0, fracaoMaxima }: {
  children: ReactNode; chave: string; aoMedir: (m: Margens) => void
  /** Cada incremento recolhe a folha (ex.: para mostrar algo no mapa). */
  recolher?: number
  /** Teto da altura (fração da tela) no celular. Na escolha da viagem a
   *  folha para em ~2/3 e o resto rola: a rota precisa caber no mapa. */
  fracaoMaxima?: number
}) {
  const larga = useTelaLarga()
  const conteudoRef = useRef<HTMLDivElement>(null)
  const [alturaConteudo, definirAlturaConteudo] = useState(0)
  const [recolhida, definirRecolhida] = useState(false)
  const [alturaJanela, definirAlturaJanela] = useState(window.innerHeight)
  // Começa abaixo da posição final: o primeiro animate a faz subir.
  const y = useMotionValue(220)
  const controles = useDragControls()

  useLayoutEffect(() => {
    const elemento = conteudoRef.current
    if (!elemento) return
    const observador = new ResizeObserver(() => definirAlturaConteudo(elemento.offsetHeight))
    observador.observe(elemento)
    return () => observador.disconnect()
  }, [])

  useEffect(() => {
    const aoRedimensionar = () => definirAlturaJanela(window.innerHeight)
    window.addEventListener('resize', aoRedimensionar)
    return () => window.removeEventListener('resize', aoRedimensionar)
  }, [])

  const maxima = Math.round(alturaJanela * (larga ? 0.88 : fracaoMaxima ?? 0.84))
  const altura = Math.min(alturaConteudo, maxima)
  const curso = Math.max(0, altura - ESPIAR_PX)

  // Conteúdo novo (outra fase) sempre aparece expandido.
  useEffect(() => { definirRecolhida(false) }, [chave])
  useEffect(() => { if (recolher > 0) definirRecolhida(true) }, [recolher])

  useEffect(() => {
    const controle = animate(y, larga || !recolhida ? 0 : curso, MOLA)
    return () => controle.stop()
  }, [recolhida, curso, larga])

  useEffect(() => {
    if (larga) aoMedir({ base: 0, esquerda: 436 })
    else aoMedir({ base: recolhida ? ESPIAR_PX : altura, esquerda: 0 })
  }, [altura, recolhida, larga])

  function aoSoltar(_e: unknown, info: PanInfo) {
    const posicao = (recolhida ? curso : 0) + info.offset.y
    const recolher = info.velocity.y > 350 || (posicao > curso / 2 && info.velocity.y > -350)
    if (recolher !== recolhida) vibrar(6)
    definirRecolhida(recolher)
    animate(y, recolher ? curso : 0, { ...MOLA, velocity: info.velocity.y })
  }

  return (
    <motion.section
      className={`folha ${larga ? 'lateral' : ''}`}
      style={{ y }}
      animate={{ height: altura || 'auto' }}
      transition={{ height: MOLA }}
      drag={larga ? false : 'y'}
      dragControls={controles}
      dragListener={false}
      dragConstraints={{ top: 0, bottom: curso }}
      dragElastic={{ top: 0.05, bottom: 0.3 }}
      dragMomentum={false}
      onDragEnd={aoSoltar}
    >
      <div className="folha-rolagem" style={{ maxHeight: maxima }}>
        <div ref={conteudoRef} className="folha-conteudo">
          {!larga && (
            <div className="folha-alca" onPointerDown={(e) => controles.start(e)}
                 onClick={() => { vibrar(6); definirRecolhida((r) => !r) }}
                 role="button" aria-label={recolhida ? 'Expandir painel' : 'Recolher painel'}>
              <span />
            </div>
          )}
          <AnimatePresence mode="wait" initial={false}>
            <motion.div key={chave}
                        initial={{ opacity: 0, y: 22, filter: 'blur(4px)' }}
                        animate={{ opacity: 1, y: 0, filter: 'blur(0px)', transition: { y: { type: 'spring', stiffness: 360, damping: 32 }, default: { duration: 0.3, ease: 'easeOut' } } }}
                        exit={{ opacity: 0, y: -12, filter: 'blur(4px)', transition: { duration: 0.14 } }}>
              {children}
            </motion.div>
          </AnimatePresence>
        </div>
      </div>
    </motion.section>
  )
}

export function Aviso({ tipo = 'neutro', icone = 'aviso', children }:
  { tipo?: 'neutro' | 'erro' | 'ok'; icone?: string; children: ReactNode }) {
  return (
    <motion.div className={`aviso ${tipo}`} role={tipo === 'erro' ? 'alert' : undefined}
                initial={{ opacity: 0, height: 0, scale: 0.96 }}
                animate={{ opacity: 1, height: 'auto', scale: 1, x: tipo === 'erro' ? [0, -7, 6, -4, 3, 0] : 0 }}
                exit={{ opacity: 0, height: 0 }}
                transition={{ x: { duration: 0.42 }, default: { type: 'spring', stiffness: 360, damping: 30 } }}>
      <Icone nome={tipo === 'ok' && icone === 'aviso' ? 'check' : icone} tamanho={17} />
      <div>{children}</div>
    </motion.div>
  )
}
