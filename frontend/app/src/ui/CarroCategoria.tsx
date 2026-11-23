import { useId } from 'react'
import type { IdCategoria } from '../tipos'

/**
 * Ilustração de perfil de cada categoria, no lugar do mesmo ícone repetido.
 * O carro segue a categoria: Essencial é um hatch compacto branco, de calota
 * simples; Conforto, um sedã moderno prata-azulado com rodas de liga e friso
 * cromado; Premium, um SUV de luxo preto brilhante, com moldura cromada nas
 * janelas, rodas grandes de dez raios e luzes de LED. Todos no MESMO viewBox,
 * então o tamanho relativo entre eles é real (o hatch ocupa menos largura).
 *
 * Cores fixas (não seguem o tema): são a pintura do carro. Um contorno
 * sutil garante leitura no cartão claro e no escuro.
 */
export function CarroCategoria({ categoria, largura = 76 }: { categoria: IdCategoria; largura?: number }) {
  const id = useId().replace(/:/g, '')
  return (
    <svg viewBox="0 0 100 50" width={largura} height={largura / 2} aria-hidden="true" className={`carro-${categoria}`}>
      <defs>
        <linearGradient id={`vidro${id}`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#5d6b7a" />
          <stop offset=".55" stopColor="#1c242d" />
          <stop offset="1" stopColor="#10151b" />
        </linearGradient>
        <linearGradient id={`lata${id}`} x1="0" y1="0" x2="0" y2="1">
          {categoria === 'economico' && <><stop offset="0" stopColor="#F2F4F6" /><stop offset="1" stopColor="#B9C0C8" /></>}
          {categoria === 'conforto' && <><stop offset="0" stopColor="#C3CFDB" /><stop offset=".5" stopColor="#7E92A6" /><stop offset="1" stopColor="#53647A" /></>}
          {categoria === 'grande' && <><stop offset="0" stopColor="#6A727C" /><stop offset=".3" stopColor="#23272D" /><stop offset=".7" stopColor="#101215" /><stop offset="1" stopColor="#07080A" /></>}
        </linearGradient>
      </defs>
      <ellipse cx="50" cy="45" rx={categoria === 'economico' ? 34 : 42} ry="2.6" fill="#000" opacity=".18" />
      {categoria === 'economico' && <Hatch id={id} />}
      {categoria === 'conforto' && <Seda id={id} />}
      {categoria === 'grande' && <SuvLuxo id={id} />}
    </svg>
  )
}

const CONTORNO = { stroke: 'rgba(120,128,138,.55)', strokeWidth: 0.7, strokeLinejoin: 'round' as const }

/** Calota simples (Essencial), liga de 5 raios (Conforto), liga de 10 raios bicolor (Premium). */
function Roda({ x, y, r, acabamento }: { x: number; y: number; r: number; acabamento: 'calota' | 'liga' | 'premium' }) {
  const raios = acabamento === 'premium' ? 10 : acabamento === 'liga' ? 5 : 0
  const aro = acabamento === 'premium' ? 0.68 : 0.6
  return (
    <g>
      <circle cx={x} cy={y} r={r + 1.4} fill="#14171a" />
      <circle cx={x} cy={y} r={r} fill="#1e2226" />
      <circle cx={x} cy={y} r={r * aro} fill={acabamento === 'calota' ? '#8E959D' : acabamento === 'premium' ? '#2a2e33' : '#C9CED4'} />
      {acabamento === 'premium' && <circle cx={x} cy={y} r={r * aro} fill="none" stroke="#DADFE4" strokeWidth=".6" />}
      {Array.from({ length: raios }, (_, i) => {
        const a = (i / raios) * Math.PI * 2 - Math.PI / 2
        return <line key={i} x1={x} y1={y} x2={x + Math.cos(a) * r * (aro - 0.03)} y2={y + Math.sin(a) * r * (aro - 0.03)}
                     stroke={acabamento === 'premium' ? '#D5DAE0' : '#6f777f'} strokeWidth={acabamento === 'premium' ? 0.55 : 0.9} strokeLinecap="round" />
      })}
      <circle cx={x} cy={y} r={r * 0.16} fill={acabamento === 'premium' ? '#9AA2AA' : '#5b636b'} />
    </g>
  )
}

/** Retrovisor na base do para-brisa. */
function Retrovisor({ x, y, cor }: { x: number; y: number; cor: string }) {
  return <path d={`M${x} ${y} l2.2 -.4 q.9 0 .9 .9 l0 1.1 q0 .7 -.8 .7 l-2.3 0 Z`} fill={cor} />
}

/** Essencial: hatch compacto, prata claro, calota simples. */
function Hatch({ id }: { id: string }) {
  return (
    <g>
      <path d="M19 37 L18.5 27.5 Q18.5 24 20.5 21.5 L27.5 14 Q29 12.6 31.5 12.6 L51 12 Q55.5 12 58.5 15 L65.5 21.8 L78.5 23.6 Q83 24.5 83 28.5 L83 34.5 Q83 37 80.5 37 Z"
            fill={`url(#lata${id})`} {...CONTORNO} />
      <path d="M24.5 21.6 L29.8 16 Q30.8 14.9 32.4 14.9 L40.5 14.9 L40.5 21.6 Z" fill={`url(#vidro${id})`} />
      <path d="M43.5 21.6 L43.5 14.9 L51.5 14.7 Q54 14.7 56 16.7 L61 21.6 Z" fill={`url(#vidro${id})`} />
      <line x1="42" y1="23" x2="42" y2="34" stroke="rgba(0,0,0,.18)" strokeWidth=".6" />
      <rect x="80.2" y="25.2" width="2.6" height="2.2" rx=".8" fill="#FFF3C4" />
      <rect x="18.7" y="24.5" width="1.6" height="3" rx=".6" fill="#D2463F" />
      <Retrovisor x={60.5} y={21} cor="#C9CFD6" />
      <Roda x={30} y={37} r={5.8} acabamento="calota" />
      <Roda x={71} y={37} r={5.8} acabamento="calota" />
    </g>
  )
}

/** Conforto: sedã moderno prata-azulado, friso cromado, rodas de liga, faróis de LED. */
function Seda({ id }: { id: string }) {
  return (
    <g>
      <path d="M9.5 36 L9.5 29 Q9.5 25.8 13.5 25 L26 23 L35.5 14.2 Q37.4 12.6 40.5 12.6 L60 12.6 Q63.4 12.6 66 15.2 L73 22.3 L87 24.4 Q92.5 25.4 92.5 30 L92.5 33.6 Q92.5 36 90 36 Z"
            fill={`url(#lata${id})`} {...CONTORNO} />
      <path d="M30.5 22.6 L37.6 15.8 Q39 14.6 41.2 14.6 L49 14.6 L49 22.6 Z" fill={`url(#vidro${id})`} />
      <path d="M51.8 22.6 L51.8 14.6 L59.6 14.6 Q62.2 14.6 64 16.6 L69.6 22.6 Z" fill={`url(#vidro${id})`} />
      {/* friso cromado da linha de cintura e da soleira */}
      <path d="M27 23.9 L72.5 23.4" stroke="#D8DDE2" strokeWidth=".8" strokeLinecap="round" />
      <path d="M31 33.2 L68 33.2" stroke="#9AA2AA" strokeWidth=".7" strokeLinecap="round" opacity=".8" />
      <line x1="50.4" y1="24.5" x2="50.4" y2="33" stroke="rgba(0,0,0,.16)" strokeWidth=".6" />
      <path d="M41 25.6 L44 25.6 M59 25.4 L62 25.4" stroke="#E6EAEE" strokeWidth=".7" strokeLinecap="round" />
      {/* reflexo no capô */}
      <path d="M74 24.6 Q82 25.2 88 27" stroke="rgba(255,255,255,.45)" strokeWidth=".8" fill="none" strokeLinecap="round" />
      <Retrovisor x={69} y={21.8} cor="#6E8296" />
      <path d="M87.5 27.3 L92 28.4" stroke="#EAF6FF" strokeWidth="1.6" strokeLinecap="round" />
      <path d="M9.8 27.6 L13 27.2" stroke="#E0453C" strokeWidth="1.8" strokeLinecap="round" />
      <Roda x={24} y={36} r={6.6} acabamento="liga" />
      <Roda x={77} y={36} r={6.6} acabamento="liga" />
    </g>
  )
}

/**
 * Premium: SUV de luxo, preto brilhante. Alto do chão, cintura alta (vidros
 * baixos) com moldura cromada, caixas de roda recortadas, rodas de dez raios,
 * LED fino na frente e lanterna vertical atrás. Sem rack nem plástico: é o
 * carro de luxo, não o utilitário.
 */
function SuvLuxo({ id }: { id: string }) {
  // Caixas de roda recortadas na lataria: o SUV fica alto do chão, e a roda
  // aparece inteira dentro do arco (raio 9,3 em volta do centro da roda).
  return (
    <g>
      <path d="M10 33.5 L10 21 Q10 17.5 12 15.5 L17 10.5 Q18.6 9 21.5 9 L58 8.6 Q62 8.6 64.6 11 L72 18.4 Q73.4 19.6 75.5 19.9 L88.5 21.6 Q93 22.3 93 27 L93 32 Q93 33.5 91.5 33.5 L86.06 33.5 A9.3 9.3 0 0 0 67.94 33.5 L33.06 33.5 A9.3 9.3 0 0 0 14.94 33.5 Z"
            fill={`url(#lata${id})`} {...CONTORNO} />
      {/* vidros baixos (cintura alta) com moldura cromada; colunas na cor do carro */}
      <path d="M15.6 18.6 L19.6 13 Q20.8 11.5 23 11.5 L57.5 11.3 Q60.6 11.3 62.6 13.3 L68 18.6 Z"
            fill={`url(#vidro${id})`} stroke="#E3E7EB" strokeWidth=".8" strokeLinejoin="round" />
      <rect x="34" y="11.2" width="2.2" height="7.6" fill="#0d0f12" />
      <rect x="50.4" y="11.2" width="2" height="7.6" fill="#0d0f12" />
      {/* reflexo do ombro e do capô: o preto brilhante precisa de luz para ler */}
      <path d="M12.5 21.8 Q50 20.4 87.5 22.6" stroke="rgba(255,255,255,.4)" strokeWidth=".7" fill="none" strokeLinecap="round" />
      <path d="M74 20.6 Q82 21.4 89 22.8" stroke="rgba(255,255,255,.3)" strokeWidth=".6" fill="none" strokeLinecap="round" />
      <path d="M39.6 23.8 L43 23.8 M56 23.6 L59.4 23.6" stroke="#E6EAEE" strokeWidth=".7" strokeLinecap="round" />
      <path d="M34.5 31.6 L66.5 31.6" stroke="#C9CED4" strokeWidth=".7" strokeLinecap="round" />
      <line x1="35.1" y1="20" x2="35.1" y2="30.8" stroke="rgba(255,255,255,.09)" strokeWidth=".6" />
      <line x1="51.4" y1="20" x2="51.4" y2="30.8" stroke="rgba(255,255,255,.09)" strokeWidth=".6" />
      <Retrovisor x={68.6} y={18.2} cor="#16191d" />
      <path d="M87.4 23.4 L92.8 24.6" stroke="#EAF6FF" strokeWidth="1.3" strokeLinecap="round" />
      <path d="M88 23.6 L92.2 24.6" stroke="#9FD8FF" strokeWidth=".4" strokeLinecap="round" opacity=".9" />
      <path d="M10.3 17.4 L10.3 22.6" stroke="#E0453C" strokeWidth="1.5" strokeLinecap="round" />
      <Roda x={24} y={35.6} r={7.8} acabamento="premium" />
      <Roda x={77} y={35.6} r={7.8} acabamento="premium" />
    </g>
  )
}
