import { animate, motion, useDragControls, useMotionValue } from 'framer-motion'
import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { vibrar } from '../util'

const ESPIAR_PX = 132           // altura visível quando recolhida
const MOLA = { type: 'spring', stiffness: 380, damping: 36, mass: 0.9 }

export function usarDesktop() {
  const consulta = '(min-width: 900px)'
  const [desktop, definir] = useState(() => window.matchMedia(consulta).matches)
  useEffect(() => {
    const lista = window.matchMedia(consulta)
    const aoMudar = () => definir(lista.matches)
    lista.addEventListener('change', aoMudar)
    return () => lista.removeEventListener('change', aoMudar)
  }, [])
  return desktop
}

/**
 * Folha inferior, o padrão de app de mobilidade: o mapa ocupa a tela toda e o
 * conteúdo sobe de baixo.
 *
 * - Arrastar pela alça recolhe/expande (com mola e velocidade do gesto).
 * - A ALTURA acompanha o conteúdo com animação real de layout (height), e não
 *   com escala — escala deformaria texto durante a transição.
 * - `aoMedir` informa quanto da tela a folha ocupa, para o mapa enquadrar a
 *   rota na parte que continua visível.
 * - Em tela larga (tablet deitado, desktop) vira painel lateral flutuante; o
 *   app continua o mesmo, só ganha espaço.
 */
export function Folha({ children, chave, aoMedir }) {
  const desktop = usarDesktop()
  const conteudoRef = useRef(null)
  const [alturaConteudo, definirAlturaConteudo] = useState(0)
  const [recolhida, definirRecolhida] = useState(false)
  // Começa abaixo da posição final: o primeiro animate a faz subir.
  const y = useMotionValue(120)
  const controles = useDragControls()

  useLayoutEffect(() => {
    const elemento = conteudoRef.current
    if (!elemento) return
    const observador = new ResizeObserver(() => definirAlturaConteudo(elemento.offsetHeight))
    observador.observe(elemento)
    definirAlturaConteudo(elemento.offsetHeight)
    return () => observador.disconnect()
  }, [])

  const maxima = Math.round(window.innerHeight * (desktop ? 0.9 : 0.86))
  const altura = Math.min(alturaConteudo, maxima)
  const curso = Math.max(0, altura - ESPIAR_PX)

  // Conteúdo novo (outra fase da corrida) sempre aparece expandido.
  useEffect(() => { definirRecolhida(false) }, [chave])

  useEffect(() => {
    const alvo = desktop || !recolhida ? 0 : curso
    const controle = animate(y, alvo, MOLA)
    return () => controle.stop()
  }, [recolhida, curso, desktop])

  useEffect(() => {
    if (desktop) aoMedir?.({ base: 0, esquerda: 432 })
    else aoMedir?.({ base: recolhida ? ESPIAR_PX : altura, esquerda: 0 })
  }, [altura, recolhida, desktop])

  function aoSoltar(_evento, info) {
    const posicao = (recolhida ? curso : 0) + info.offset.y
    const recolher = info.velocity.y > 350 || (posicao > curso / 2 && info.velocity.y > -350)
    if (recolher !== recolhida) vibrar(6)
    definirRecolhida(recolher)
    animate(y, recolher ? curso : 0, { ...MOLA, velocity: info.velocity.y })
  }

  return (
    <motion.section
      className={`folha ${desktop ? 'lateral' : ''}`}
      style={{ y }}
      initial={{ opacity: 0 }}
      animate={{ height: altura || 'auto', opacity: 1 }}
      transition={{ height: MOLA, opacity: { duration: 0.3 } }}
      drag={desktop ? false : 'y'}
      dragControls={controles}
      dragListener={false}
      dragConstraints={{ top: 0, bottom: curso }}
      dragElastic={{ top: 0.04, bottom: 0.25 }}
      dragMomentum={false}
      onDragEnd={aoSoltar}
    >
      <div className="folha-rolagem" style={{ maxHeight: maxima }}>
        <div ref={conteudoRef} className="folha-conteudo">
          {!desktop && (
            <div className="folha-alca"
                 onPointerDown={(e) => controles.start(e)}
                 onClick={() => { vibrar(6); definirRecolhida((r) => !r) }}
                 role="button" aria-label={recolhida ? 'Expandir painel' : 'Recolher painel'}>
              <span />
            </div>
          )}
          {children}
        </div>
      </div>
    </motion.section>
  )
}
