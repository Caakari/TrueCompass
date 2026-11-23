import {
  animate, motion, useMotionValue, useSpring, useTransform, type HTMLMotionProps,
} from 'framer-motion'
import { useEffect, useRef, useState, type CSSProperties, type PointerEvent, type ReactNode } from 'react'
import { movimentoReduzido, vibrar } from '../lib/util'

export const MOLA = { type: 'spring', stiffness: 420, damping: 32 } as const
export const MOLA_SUAVE = { type: 'spring', stiffness: 260, damping: 30 } as const

// ================================================================= Botão

type Variante = 'primario' | 'secundario' | 'fantasma' | 'perigo'

interface PropsBotao extends Omit<HTMLMotionProps<'button'>, 'children'> {
  children: ReactNode
  variante?: Variante
  carregando?: boolean
  cheio?: boolean
}

/**
 * Botão do aplicativo.
 * - Afunda com mola ao toque e solta uma ONDA do ponto exato do dedo.
 * - Com mouse, é MAGNÉTICO: inclina-se alguns pixels na direção do cursor.
 * - Um feixe de brilho atravessa o botão primário de tempos em tempos.
 * - `carregando` troca o rótulo por um giro sem mudar a largura.
 */
export function Botao({
  children, variante = 'primario', carregando = false, cheio = true, disabled,
  className = '', onClick, type = 'button', ...resto
}: PropsBotao) {
  const [ondas, definirOndas] = useState<{ id: number; x: number; y: number; t: number }[]>([])
  const x = useSpring(0, { stiffness: 300, damping: 18 })
  const y = useSpring(0, { stiffness: 300, damping: 18 })
  const inativo = disabled || carregando

  function aoMover(e: PointerEvent<HTMLButtonElement>) {
    if (e.pointerType !== 'mouse' || inativo) return
    const caixa = e.currentTarget.getBoundingClientRect()
    x.set(((e.clientX - caixa.left) / caixa.width - 0.5) * 8)
    y.set(((e.clientY - caixa.top) / caixa.height - 0.5) * 6)
  }

  function aoPressionar(e: PointerEvent<HTMLButtonElement>) {
    if (inativo) return
    const caixa = e.currentTarget.getBoundingClientRect()
    const t = Math.max(caixa.width, caixa.height) * 2.4
    const onda = { id: performance.now(), x: e.clientX - caixa.left - t / 2, y: e.clientY - caixa.top - t / 2, t }
    definirOndas((o) => [...o, onda])
    setTimeout(() => definirOndas((o) => o.filter((w) => w.id !== onda.id)), 700)
  }

  return (
    <motion.button
      type={type}
      className={`botao ${variante} ${cheio ? 'cheio' : ''} ${carregando ? 'carregando' : ''} ${className}`}
      disabled={inativo}
      style={{ x, y }}
      whileTap={inativo ? undefined : { scale: 0.955 }}
      transition={{ type: 'spring', stiffness: 520, damping: 28 }}
      onPointerMove={aoMover}
      onPointerLeave={() => { x.set(0); y.set(0) }}
      onPointerDown={aoPressionar}
      onClick={(e) => { vibrar(8); onClick?.(e) }}
      {...resto}
    >
      {ondas.map((o) => (
        <span key={o.id} className="onda" style={{ left: o.x, top: o.y, width: o.t, height: o.t }} />
      ))}
      {variante === 'primario' && !inativo && <span className="brilho" aria-hidden="true" />}
      <span className="botao-rotulo">{children}</span>
      {carregando && <span className="giro" aria-label="carregando" />}
    </motion.button>
  )
}

/** Botão redondo flutuante sobre o mapa. */
export function BotaoRedondo({ children, rotulo, ativo = false, className = '', onClick, ...resto }:
  Omit<HTMLMotionProps<'button'>, 'children'> & { children: ReactNode; rotulo: string; ativo?: boolean }) {
  return (
    <motion.button type="button" aria-label={rotulo} title={rotulo}
                   className={`botao-redondo ${ativo ? 'ativo' : ''} ${className}`}
                   whileTap={{ scale: 0.86, rotate: -6 }} whileHover={{ scale: 1.06 }}
                   transition={{ type: 'spring', stiffness: 600, damping: 24 }}
                   onClick={(e) => { vibrar(6); onClick?.(e) }} {...resto}>
      {children}
    </motion.button>
  )
}

// ============================================================== Odômetro

/**
 * Número em ODÔMETRO: cada dígito é uma coluna 0–9 que rola até o valor novo,
 * com mola e um pequeno atraso por casa — da direita para a esquerda, como um
 * contador mecânico. Separadores e símbolos ("R$", ",") ficam parados.
 */
export function Odometro({ texto, className = '' }: { texto: string; className?: string }) {
  const caracteres = [...texto]
  return (
    <span className={`odometro ${className}`} aria-label={texto}>
      {caracteres.map((c, i) => {
        const casa = caracteres.length - i            // chave estável pela direita
        if (!/\d/.test(c)) return <span key={`s${casa}`} className="odometro-fixo" aria-hidden="true">{c}</span>
        return <ColunaDigito key={`d${casa}`} digito={Number(c)} atraso={casa * 0.045} />
      })}
    </span>
  )
}

// Mesma altura de .odometro-janela no CSS: o passo da coluna é uma casa.
const ALTURA_DIGITO_EM = 1.15

function ColunaDigito({ digito, atraso }: { digito: number; atraso: number }) {
  return (
    <span className="odometro-janela" aria-hidden="true">
      <motion.span className="odometro-coluna" initial={{ y: '0em' }}
                   animate={{ y: `${-digito * ALTURA_DIGITO_EM}em` }}
                   transition={{ type: 'spring', stiffness: 140, damping: 18, delay: atraso }}>
        {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9].map((n) => <span key={n}>{n}</span>)}
      </motion.span>
    </span>
  )
}

/** Valor que desliza continuamente até o alvo (para contadores grandes). */
export function NumeroDeslizante({ valor, formatar, duracao = 1.1 }:
  { valor: number; formatar: (v: number) => string; duracao?: number }) {
  const mv = useMotionValue(0)
  const texto = useTransform(mv, formatar)
  useEffect(() => {
    const c = animate(mv, valor, { duration: movimentoReduzido() ? 0 : duracao, ease: [0.16, 1, 0.3, 1] })
    return () => c.stop()
  }, [valor])
  return <motion.span>{texto}</motion.span>
}

// ======================================================= Texto revelado

/**
 * Texto que surge letra a letra, saindo de um desfoque e subindo — usado em
 * títulos que mudam de fase. `chave` reinicia a animação.
 */
export function TextoRevelado({ texto, className = '', atraso = 0, as = 'h2' }:
  { texto: string; className?: string; atraso?: number; as?: 'h1' | 'h2' | 'span' }) {
  const Tag = motion[as]
  const palavras = texto.split(' ')
  let indice = 0
  return (
    <Tag key={texto} className={`texto-revelado ${className}`} aria-label={texto}
         initial="oculto" animate="visivel"
         variants={{ visivel: { transition: { staggerChildren: 0.022, delayChildren: atraso } } }}>
      {palavras.map((palavra, p) => (
        <span key={p} className="palavra" aria-hidden="true">
          {[...palavra].map((letra) => (
            <motion.span key={indice++} className="letra"
                         variants={{
                           oculto: { opacity: 0, y: '0.45em', filter: 'blur(6px)' },
                           // Mola só no deslocamento: no blur ela passaria de 0 e geraria
                           // blur negativo, que é inválido.
                           visivel: { opacity: 1, y: 0, filter: 'blur(0px)', transition: { y: { type: 'spring', stiffness: 380, damping: 26 }, default: { duration: 0.35, ease: 'easeOut' } } },
                         }}>
              {letra}
            </motion.span>
          ))}
          {p < palavras.length - 1 && ' '}
        </span>
      ))}
    </Tag>
  )
}

// ============================================================ Diversos

export function Esqueleto({ largura = '100%', altura = 14, raio = 7, style }:
  { largura?: number | string; altura?: number; raio?: number; style?: CSSProperties }) {
  return <span className="esqueleto" style={{ width: largura, height: altura, borderRadius: raio, ...style }} />
}

export function Reticencias() {
  return <span className="reticencias" aria-hidden="true"><span /><span /><span /></span>
}

// ============================================================== Confete

const CORES_CONFETE = ['#5FA772', '#93C9A1', '#E0525C', '#F08A92', '#B08D57', '#ECEAE5']

/**
 * Explosão de confete em canvas, a partir de um ponto (o selo de "pago").
 * Física simples: velocidade inicial em leque, gravidade, arrasto do ar e
 * rotação — 160 partículas, ~3 s, depois o canvas se apaga sozinho.
 */
export function Confete({ origem }: { origem: { x: number; y: number } | null }) {
  const ref = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = ref.current
    if (!canvas || !origem || movimentoReduzido()) return
    const ctx = canvas.getContext('2d')!
    const dpr = window.devicePixelRatio || 1
    canvas.width = window.innerWidth * dpr
    canvas.height = window.innerHeight * dpr
    ctx.scale(dpr, dpr)

    const particulas = Array.from({ length: 160 }, () => {
      const angulo = -Math.PI / 2 + (Math.random() - 0.5) * Math.PI * 1.25
      const velocidade = 7 + Math.random() * 11
      return {
        x: origem.x, y: origem.y,
        vx: Math.cos(angulo) * velocidade, vy: Math.sin(angulo) * velocidade,
        giro: Math.random() * Math.PI, vgiro: (Math.random() - 0.5) * 0.4,
        largura: 5 + Math.random() * 6, altura: 3 + Math.random() * 4,
        cor: CORES_CONFETE[Math.floor(Math.random() * CORES_CONFETE.length)],
        vida: 1,
      }
    })

    let quadro = 0
    const passo = () => {
      ctx.clearRect(0, 0, window.innerWidth, window.innerHeight)
      let vivas = 0
      for (const p of particulas) {
        if (p.vida <= 0) continue
        p.vx *= 0.985
        p.vy = p.vy * 0.985 + 0.32
        p.x += p.vx
        p.y += p.vy
        p.giro += p.vgiro
        p.vida -= 0.0065
        if (p.y > window.innerHeight + 20) p.vida = 0
        if (p.vida <= 0) continue
        vivas++
        ctx.save()
        ctx.globalAlpha = Math.min(1, p.vida * 1.6)
        ctx.translate(p.x, p.y)
        ctx.rotate(p.giro)
        ctx.scale(1, Math.cos(p.giro * 2.2))       // gira em 3D, de frente e de lado
        ctx.fillStyle = p.cor
        ctx.fillRect(-p.largura / 2, -p.altura / 2, p.largura, p.altura)
        ctx.restore()
      }
      if (vivas > 0) quadro = requestAnimationFrame(passo)
      else ctx.clearRect(0, 0, window.innerWidth, window.innerHeight)
    }
    quadro = requestAnimationFrame(passo)
    return () => cancelAnimationFrame(quadro)
  }, [origem?.x, origem?.y])

  return <canvas ref={ref} className="confete" aria-hidden="true" />
}
