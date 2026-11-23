import { animate, motion, useMotionValue, useSpring, useTransform } from 'framer-motion'
import { useEffect, useRef, type PointerEvent } from 'react'

/**
 * Bússola com rumo verdadeiro.
 *
 * A agulha não é enfeite: aponta o AZIMUTE INICIAL entre dois pontos sobre a
 * esfera (ver rumoVerdadeiro em lib/util.ts) — a mesma geometria do
 * haversine que o backend usa para pesar as arestas.
 *
 * Três modos:
 *  - rumo numérico: a agulha vai até ele com MOLA (oscila e assenta, como uma
 *    agulha magnética de verdade), sempre pelo caminho curto — de 350° para
 *    10° são +20°, não −340°;
 *  - `buscando`: gira rápido, procurando; ao receber um rumo, trava nele;
 *  - sem rumo: deriva devagar.
 */

const RAD = Math.PI / 180
const MARCAS = Array.from({ length: 72 }, (_, i) => {
  const cardeal = i % 9 === 0
  const comprimento = cardeal ? 7 : i % 3 === 0 ? 4.5 : 2.5
  const a = i * 5 * RAD
  return {
    x1: 50 + Math.sin(a) * 44, y1: 50 - Math.cos(a) * 44,
    x2: 50 + Math.sin(a) * (44 - comprimento), y2: 50 - Math.cos(a) * (44 - comprimento),
    cardeal,
  }
})
const LETRAS = [['N', 0], ['L', 90], ['S', 180], ['O', 270]] as const

interface Props {
  rumo: number | null
  tamanho?: number
  letras?: boolean
  buscando?: boolean
  inclinar?: boolean
}

export function Bussola({ rumo, tamanho = 110, letras = true, buscando = false, inclinar = false }: Props) {
  const giro = useMotionValue(0)
  const molaGiro = useSpring(giro, { stiffness: 70, damping: 9, mass: 1.1 })
  const acumulado = useRef(0)

  // Inclinação 3D que acompanha o cursor (só com mouse).
  const rx = useSpring(0, { stiffness: 180, damping: 18 })
  const ry = useSpring(0, { stiffness: 180, damping: 18 })
  const brilhoX = useTransform(ry, [-18, 18], ['20%', '80%'])
  const brilhoY = useTransform(rx, [-18, 18], ['80%', '20%'])
  const reflexo = useTransform([brilhoX, brilhoY], ([x, y]) =>
    `radial-gradient(circle at ${x} ${y}, rgba(255,255,255,.22), transparent 55%)`)

  useEffect(() => {
    if (buscando && rumo == null) {
      // Gira rápido e sem parar enquanto procura.
      const controle = animate(giro, giro.get() + 3600, { duration: 9, ease: 'linear', repeat: Infinity })
      return () => controle.stop()
    }
    if (rumo == null) {
      const controle = animate(giro, giro.get() + 360, { duration: 26, ease: 'linear', repeat: Infinity })
      return () => controle.stop()
    }
    const atual = giro.get()
    acumulado.current = atual + ((((rumo - atual) % 360) + 540) % 360) - 180
    giro.set(acumulado.current)
  }, [rumo, buscando])

  function aoMover(e: PointerEvent<HTMLDivElement>) {
    if (!inclinar || e.pointerType !== 'mouse') return
    const caixa = e.currentTarget.getBoundingClientRect()
    ry.set(((e.clientX - caixa.left) / caixa.width - 0.5) * 36)
    rx.set(-((e.clientY - caixa.top) / caixa.height - 0.5) * 36)
  }

  const rotulo = rumo == null ? 'Bússola sem destino definido' : `Rumo ${Math.round(rumo)} graus`

  return (
    <motion.div className="bussola-palco" style={{ width: tamanho, height: tamanho, rotateX: rx, rotateY: ry }}
                onPointerMove={aoMover} onPointerLeave={() => { rx.set(0); ry.set(0) }}>
      <svg className="bussola" viewBox="0 0 100 100" width={tamanho} height={tamanho} role="img" aria-label={rotulo}>
        <defs>
          <radialGradient id="bussola-fundo" cx="50%" cy="38%" r="70%">
            <stop offset="0%" stopColor="var(--cartao-alto)" />
            <stop offset="100%" stopColor="var(--cartao)" />
          </radialGradient>
        </defs>
        <circle className="bussola-aro" cx="50" cy="50" r="47" fill="url(#bussola-fundo)" />
        <circle className="bussola-aro-interno" cx="50" cy="50" r="38" />
        {MARCAS.map((m, i) => (
          <line key={i} x1={m.x1} y1={m.y1} x2={m.x2} y2={m.y2}
                className={m.cardeal ? 'bussola-marca-cardeal' : 'bussola-marca'} />
        ))}
        {letras && LETRAS.map(([letra, angulo]) => (
          <text key={letra} className={`bussola-letra ${letra === 'N' ? 'norte' : ''}`}
                x={50 + Math.sin(angulo * RAD) * 30} y={50 - Math.cos(angulo * RAD) * 30 + 3.2}>
            {letra}
          </text>
        ))}
        <motion.g style={{ rotate: molaGiro }}>
          <polygon className="bussola-agulha-n" points="50,13 55.5,50 50,46 44.5,50" />
          <polygon className="bussola-agulha-s" points="50,87 44.5,50 50,54 55.5,50" />
        </motion.g>
        <circle className="bussola-centro" cx="50" cy="50" r="3.6" />
      </svg>
      {inclinar && (
        <motion.span className="bussola-reflexo" aria-hidden="true"
                     style={{ background: reflexo }} />
      )}
    </motion.div>
  )
}
