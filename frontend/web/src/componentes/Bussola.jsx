import { useEffect, useRef, useState } from 'react'

/**
 * Bússola com rumo verdadeiro.
 *
 * A agulha não é enfeite: ela aponta o AZIMUTE INICIAL entre dois pontos sobre
 * a esfera — a direção em que se deve partir para seguir o grande círculo até
 * o destino.
 *
 *   θ = atan2( sen Δλ · cos φ₂ ,
 *              cos φ₁ · sen φ₂ − sen φ₁ · cos φ₂ · cos Δλ )
 *
 * É a mesma geometria esférica do haversine que o backend usa para pesar as
 * arestas; aqui ela vira direção em vez de distância.
 */

const paraRad = (graus) => (graus * Math.PI) / 180
const paraGraus = (rad) => (rad * 180) / Math.PI

export function rumoVerdadeiro(lat1, lon1, lat2, lon2) {
  const f1 = paraRad(lat1)
  const f2 = paraRad(lat2)
  const dl = paraRad(lon2 - lon1)
  const y = Math.sin(dl) * Math.cos(f2)
  const x = Math.cos(f1) * Math.sin(f2) - Math.sin(f1) * Math.cos(f2) * Math.cos(dl)
  return (paraGraus(Math.atan2(y, x)) + 360) % 360
}

const PONTOS = ['N', 'NE', 'L', 'SE', 'S', 'SO', 'O', 'NO']

export function pontoCardinal(graus) {
  return PONTOS[Math.round(((graus % 360) + 360) % 360 / 45) % 8]
}

/** Marcas do limbo: 72 traços, os de 45° mais longos. */
function marcas() {
  const saida = []
  for (let i = 0; i < 72; i += 1) {
    const cardeal = i % 9 === 0
    const comprimento = cardeal ? 7 : i % 3 === 0 ? 4.5 : 2.5
    const angulo = paraRad(i * 5)
    const externo = 44
    saida.push({
      x1: 50 + Math.sin(angulo) * externo,
      y1: 50 - Math.cos(angulo) * externo,
      x2: 50 + Math.sin(angulo) * (externo - comprimento),
      y2: 50 - Math.cos(angulo) * (externo - comprimento),
      cardeal,
      chave: i,
    })
  }
  return saida
}

const MARCAS = marcas()
const LETRAS = [
  { letra: 'N', angulo: 0 }, { letra: 'L', angulo: 90 },
  { letra: 'S', angulo: 180 }, { letra: 'O', angulo: 270 },
]

export function Bussola({ rumo = null, tamanho = 112, mostrarLetras = true }) {
  const acumuladoRef = useRef(0)
  const anteriorRef = useRef(null)
  const [giro, definirGiro] = useState(0)

  // Rotação acumulada: sem isto, ir de 350° para 10° faria a agulha voltar
  // 340° pelo caminho longo. Normalizamos a diferença em [-180, 180] e
  // somamos ao total, então a agulha sempre toma o caminho curto.
  useEffect(() => {
    if (rumo == null) return
    const anterior = anteriorRef.current
    if (anterior == null) {
      acumuladoRef.current = rumo
    } else {
      let delta = ((rumo - anterior + 540) % 360) - 180
      acumuladoRef.current += delta
    }
    anteriorRef.current = rumo
    definirGiro(acumuladoRef.current)
  }, [rumo])

  const semRumo = rumo == null

  return (
    <svg className="bussola" width={tamanho} height={tamanho} viewBox="0 0 100 100"
         role="img" aria-label={semRumo ? 'Bússola sem destino definido'
                                        : `Rumo ${Math.round(rumo)} graus, ${pontoCardinal(rumo)}`}>
      <circle className="bussola-aro" cx="50" cy="50" r="47" />
      <circle className="bussola-aro-interno" cx="50" cy="50" r="38" />

      {MARCAS.map((m) => (
        <line key={m.chave} x1={m.x1} y1={m.y1} x2={m.x2} y2={m.y2}
              className={m.cardeal ? 'bussola-marca-cardeal' : 'bussola-marca'} />
      ))}

      {mostrarLetras && LETRAS.map(({ letra, angulo }) => {
        const r = paraRad(angulo)
        return (
          <text key={letra} className={`bussola-letra ${letra === 'N' ? 'norte' : ''}`}
                x={50 + Math.sin(r) * 30} y={50 - Math.cos(r) * 30 + 3.2}>
            {letra}
          </text>
        )
      })}

      <g className={`bussola-giro ${semRumo ? 'livre' : ''}`}
         style={semRumo ? undefined : { transform: `rotate(${giro}deg)` }}>
        {/* Agulha norte, vermelha — aponta o rumo. */}
        <polygon className="bussola-agulha-n" points="50,13 55,50 50,46 45,50" />
        {/* Cauda, cinza. */}
        <polygon className="bussola-agulha-s" points="50,87 45,50 50,54 55,50" />
      </g>
      <circle className="bussola-centro" cx="50" cy="50" r="3.4" />
    </svg>
  )
}

/** Cartão com a bússola e a leitura numérica do rumo. */
export function CartaoBussola({ origem, destino, rotulo = 'Rumo ao destino' }) {
  const rumo = origem && destino
    ? rumoVerdadeiro(origem.lat, origem.lon, destino.lat, destino.lon)
    : null

  return (
    <div className="cartao cartao-bussola entra entra-1">
      <Bussola rumo={rumo} tamanho={96} />
      <div className="bussola-dados">
        <div className="cartao-titulo" style={{ marginBottom: 6 }}>{rotulo}</div>
        {rumo == null ? (
          <>
            <div className="bussola-rumo" style={{ fontSize: 17, color: 'var(--texto-fraco)' }}>
              sem destino
            </div>
            <div className="bussola-legenda">marque origem e destino no mapa</div>
          </>
        ) : (
          <>
            <div className="bussola-rumo">
              {Math.round(rumo)}° <small>{pontoCardinal(rumo)}</small>
            </div>
            <div className="bussola-legenda">azimute inicial sobre a esfera</div>
          </>
        )}
      </div>
    </div>
  )
}
