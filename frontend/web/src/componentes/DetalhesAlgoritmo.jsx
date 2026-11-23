import { AnimatePresence, motion } from 'framer-motion'
import { useState } from 'react'
import { vibrar } from '../util'
import { Icone } from './Icone'

const milhar = (n) => n.toLocaleString('pt-BR')

/**
 * "Como esta rota foi calculada": o A* e o Dijkstra rodaram sobre o MESMO
 * par de cruzamentos no backend. O custo tem de ser idêntico (o Dijkstra é o
 * oráculo); o que muda é quantos nós cada um precisou expandir.
 */
export function DetalhesAlgoritmo({ estimativa }) {
  const [aberto, definirAberto] = useState(false)
  const alg = estimativa?.algoritmo
  if (!alg) return null
  const a = alg.a_estrela
  const d = alg.dijkstra
  const maior = Math.max(a.nos_expandidos, d?.nos_expandidos ?? 0, 1)
  const economia = d ? 1 - a.nos_expandidos / Math.max(d.nos_expandidos, 1) : null

  return (
    <div className={`detalhes-alg ${aberto ? 'aberto' : ''}`}>
      <button className="detalhes-cabeca" onClick={() => { vibrar(6); definirAberto(!aberto) }}
              aria-expanded={aberto}>
        <Icone nome="chip" tamanho={18} />
        <span>Como esta rota foi calculada</span>
        <motion.span animate={{ rotate: aberto ? 90 : 0 }} className="detalhes-seta">
          <Icone nome="seta" tamanho={16} />
        </motion.span>
      </button>
      <AnimatePresence initial={false}>
        {aberto && (
          <motion.div className="detalhes-corpo"
                      initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ type: 'spring', stiffness: 300, damping: 34 }}>
            <p>
              A* sobre <b>{milhar(alg.nos_na_malha)}</b> cruzamentos reais do OpenStreetMap.
              Peso de cada rua = tempo de percurso + espera esperada nos semáforos
              (<span className="mono">r²/2c</span>). Heurística: linha reta ÷ {alg.velocidade_max_kmh} km/h,
              a maior velocidade medida na malha — por isso nunca superestima.
            </p>
            <Barra rotulo="A*" valor={a.nos_expandidos} maior={maior} ms={a.ms} classe="a-estrela" />
            {d && <Barra rotulo="Dijkstra" valor={d.nos_expandidos} maior={maior} ms={d.ms} classe="dijkstra" atraso={0.15} />}
            {d && (
              <div className="detalhes-rodape">
                <span className={`selo ${d.mesmo_custo ? 'ok' : 'erro'}`}>
                  <Icone nome={d.mesmo_custo ? 'check' : 'aviso'} tamanho={13} traco={3} />
                  {d.mesmo_custo ? 'mesmo custo ótimo' : 'custos divergem!'}
                </span>
                {economia > 0 && <span>{Math.round(economia * 100)}% menos nós expandidos</span>}
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

function Barra({ rotulo, valor, maior, ms, classe, atraso = 0 }) {
  return (
    <div className="barra-alg">
      <div className="barra-alg-rotulo">
        <span>{rotulo}</span>
        <span className="mono">{milhar(valor)} nós · {ms.toFixed(0)} ms</span>
      </div>
      <div className="barra-alg-trilho">
        <motion.div className={`barra-alg-cheio ${classe}`}
                    initial={{ scaleX: 0 }} animate={{ scaleX: valor / maior }}
                    transition={{ delay: 0.15 + atraso, type: 'spring', stiffness: 90, damping: 18 }} />
      </div>
    </div>
  )
}
