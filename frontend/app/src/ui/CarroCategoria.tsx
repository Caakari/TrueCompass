import { useId } from 'react'
import type { IdCategoria } from '../tipos'

/**
 * Ilustração de perfil de cada categoria, no lugar do mesmo ícone repetido.
 * A escala sobe com o preço: Essencial é um hatch compacto e simples,
 * Conforto um sedã grafite com friso cromado e rodas de liga, Premium um SUV
 * alto, de três janelas e rack no teto. Todos no MESMO viewBox, então o
 * tamanho relativo entre eles é real (o hatch ocupa menos largura).
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
          {categoria === 'conforto' && <><stop offset="0" stopColor="#4A525C" /><stop offset=".45" stopColor="#262B31" /><stop offset="1" stopColor="#15181C" /></>}
          {categoria === 'grande' && <><stop offset="0" stopColor="#4F6E8E" /><stop offset=".5" stopColor="#2E4A66" /><stop offset="1" stopColor="#1C2F43" /></>}
        </linearGradient>
      </defs>
      <ellipse cx="50" cy="45" rx={categoria === 'economico' ? 34 : 42} ry="2.6" fill="#000" opacity=".18" />
      {categoria === 'economico' && <Hatch id={id} />}
      {categoria === 'conforto' && <Seda id={id} />}
      {categoria === 'grande' && <Suv id={id} />}
    </svg>
  )
}

const CONTORNO = { stroke: 'rgba(120,128,138,.55)', strokeWidth: 0.7, strokeLinejoin: 'round' as const }

function Roda({ x, y, r, liga }: { x: number; y: number; r: number; liga: boolean }) {
  const raios = liga ? 5 : 0
  return (
    <g>
      <circle cx={x} cy={y} r={r + 1.4} fill="#14171a" />
      <circle cx={x} cy={y} r={r} fill="#1e2226" />
      <circle cx={x} cy={y} r={r * 0.6} fill={liga ? '#C9CED4' : '#8E959D'} />
      {Array.from({ length: raios }, (_, i) => {
        const a = (i / raios) * Math.PI * 2 - Math.PI / 2
        return <line key={i} x1={x} y1={y} x2={x + Math.cos(a) * r * 0.58} y2={y + Math.sin(a) * r * 0.58}
                     stroke="#6f777f" strokeWidth={0.9} strokeLinecap="round" />
      })}
      <circle cx={x} cy={y} r={r * 0.16} fill="#5b636b" />
    </g>
  )
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
      <Roda x={30} y={37} r={5.8} liga={false} />
      <Roda x={71} y={37} r={5.8} liga={false} />
    </g>
  )
}

/** Conforto: sedã grafite, friso cromado, rodas de liga, faróis de LED. */
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
      <line x1="50.4" y1="24.5" x2="50.4" y2="33" stroke="rgba(255,255,255,.12)" strokeWidth=".6" />
      {/* reflexo no capô */}
      <path d="M74 24.6 Q82 25.2 88 27" stroke="rgba(255,255,255,.28)" strokeWidth=".8" fill="none" strokeLinecap="round" />
      <path d="M87.5 27.3 L92 28.4" stroke="#EAF6FF" strokeWidth="1.6" strokeLinecap="round" />
      <path d="M9.8 27.6 L13 27.2" stroke="#E0453C" strokeWidth="1.8" strokeLinecap="round" />
      <Roda x={24} y={36} r={6.6} liga />
      <Roda x={77} y={36} r={6.6} liga />
    </g>
  )
}

/** Premium: SUV alto, três janelas, rack no teto, rodas maiores. */
function Suv({ id }: { id: string }) {
  return (
    <g>
      <rect x="15" y="6" width="46" height="1.6" rx=".8" fill="#AEB6BE" />
      <rect x="20" y="7" width="1.4" height="2.2" fill="#AEB6BE" />
      <rect x="55" y="7" width="1.4" height="2.2" fill="#AEB6BE" />
      <path d="M7.5 35.5 L7.5 15 Q7.5 8.8 13.5 8.6 L62 8.2 Q66 8.2 68.8 11 L77 20 L89 22.4 Q94 23.4 94 28 L94 33.5 Q94 35.5 91.5 35.5 Z"
            fill={`url(#lata${id})`} {...CONTORNO} />
      <path d="M12 19.5 L12 12.6 Q12 11.4 13.4 11.4 L29.5 11.4 L29.5 19.5 Z" fill={`url(#vidro${id})`} />
      <path d="M32.2 19.5 L32.2 11.4 L49.5 11.4 L49.5 19.5 Z" fill={`url(#vidro${id})`} />
      <path d="M52.2 19.5 L52.2 11.4 L62.4 11.4 Q65 11.4 67 13.4 L72.6 19.5 Z" fill={`url(#vidro${id})`} />
      {/* proteção plástica na base, típica de SUV */}
      <path d="M7.5 31.5 L94 31.5 L94 33.5 Q94 35.5 91.5 35.5 L7.5 35.5 Z" fill="#1A2633" opacity=".85" />
      <path d="M14 21.2 L73 21.2" stroke="#D8DDE2" strokeWidth=".7" strokeLinecap="round" opacity=".7" />
      <line x1="31" y1="21.5" x2="31" y2="31" stroke="rgba(255,255,255,.1)" strokeWidth=".6" />
      <line x1="51" y1="21.5" x2="51" y2="31" stroke="rgba(255,255,255,.1)" strokeWidth=".6" />
      <path d="M88.8 25.6 L93.4 26.8" stroke="#EAF6FF" strokeWidth="1.8" strokeLinecap="round" />
      <path d="M7.8 17 L7.8 22" stroke="#E0453C" strokeWidth="1.6" strokeLinecap="round" />
      <Roda x={23} y={36} r={7.4} liga />
      <Roda x={78} y={36} r={7.4} liga />
    </g>
  )
}
