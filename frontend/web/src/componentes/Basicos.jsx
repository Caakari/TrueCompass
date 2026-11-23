import { animate, motion, useMotionValue, useTransform } from 'framer-motion'
import { useEffect, useRef, useState } from 'react'
import { vibrar } from '../util'

/**
 * Botão do aplicativo: afunda ao toque (mola) e solta uma ondulação a partir
 * do ponto exato onde o dedo encostou. `carregando` troca o rótulo por um
 * indicador sem mudar a largura do botão.
 */
export function Botao({
  children, variante = 'primario', carregando = false, disabled, onClick,
  className = '', largura = 'cheia', ...resto
}) {
  const [ondas, definirOndas] = useState([])

  function aoPressionar(evento) {
    const caixa = evento.currentTarget.getBoundingClientRect()
    const tamanho = Math.max(caixa.width, caixa.height) * 2.2
    const onda = {
      id: performance.now(),
      x: evento.clientX - caixa.left - tamanho / 2,
      y: evento.clientY - caixa.top - tamanho / 2,
      tamanho,
    }
    definirOndas((antes) => [...antes, onda])
    setTimeout(() => definirOndas((antes) => antes.filter((o) => o.id !== onda.id)), 650)
  }

  return (
    <motion.button
      type="button"
      className={`botao ${variante} ${largura === 'cheia' ? 'cheio' : ''} ${carregando ? 'carregando' : ''} ${className}`}
      disabled={disabled || carregando}
      whileTap={disabled || carregando ? undefined : { scale: 0.965 }}
      transition={{ type: 'spring', stiffness: 520, damping: 30 }}
      onPointerDown={disabled || carregando ? undefined : aoPressionar}
      onClick={(evento) => { vibrar(8); onClick?.(evento) }}
      {...resto}
    >
      {ondas.map((o) => (
        <span key={o.id} className="onda"
              style={{ left: o.x, top: o.y, width: o.tamanho, height: o.tamanho }} />
      ))}
      <span className="botao-rotulo">{children}</span>
      {carregando && <span className="giro" aria-label="carregando" />}
    </motion.button>
  )
}

/** Botão redondo flutuante sobre o mapa. */
export function BotaoRedondo({ children, rotulo, ativo = false, onClick, className = '', ...resto }) {
  return (
    <motion.button type="button" aria-label={rotulo} title={rotulo}
                   className={`botao-redondo ${ativo ? 'ativo' : ''} ${className}`}
                   whileTap={{ scale: 0.88 }}
                   transition={{ type: 'spring', stiffness: 600, damping: 28 }}
                   onClick={(e) => { vibrar(6); onClick?.(e) }} {...resto}>
      {children}
    </motion.button>
  )
}

/** Número que desliza até o valor novo, em vez de trocar de repente. */
export function NumeroAnimado({ valor, formatar = (v) => v.toFixed(0), duracao = 0.7 }) {
  const movimento = useMotionValue(valor ?? 0)
  const texto = useTransform(movimento, (v) => formatar(v))
  const primeiro = useRef(true)

  useEffect(() => {
    if (valor == null) return
    if (primeiro.current) {
      primeiro.current = false
      movimento.set(0)
    }
    const controle = animate(movimento, valor, { duration: duracao, ease: [0.22, 0.61, 0.36, 1] })
    return () => controle.stop()
  }, [valor])

  return <motion.span>{texto}</motion.span>
}

/** Linha de esqueleto com brilho passando, enquanto o conteúdo carrega. */
export function Esqueleto({ largura = '100%', altura = 14, raio = 7, style }) {
  return <span className="esqueleto" style={{ width: largura, height: altura, borderRadius: raio, ...style }} />
}

/** Três pontos pulsando, para "procurando…", "calculando…". */
export function Reticencias() {
  return (
    <span className="reticencias" aria-hidden="true">
      <span /><span /><span />
    </span>
  )
}
