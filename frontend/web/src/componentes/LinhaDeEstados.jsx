import { motion } from 'framer-motion'
import { Icone } from './Icone'

/**
 * Visualiza o DAG do ciclo da corrida.
 *
 * A ordem exibida é exatamente a ordenação topológica que o backend valida por
 * Kahn na inicialização. Ver a barra andar é ver o teorema funcionando: nunca
 * se pula etapa, nunca se volta atrás.
 */
export const ETAPAS = [
  { chave: 'pedido', nome: 'Pedido', nota: 'registrado' },
  { chave: 'alocacao', nome: 'Motorista', nota: 'busca reversa no grafo' },
  { chave: 'rota', nome: 'Rota', nota: 'A* com heurística haversine' },
  { chave: 'em_curso', nome: 'Viagem', nota: 'em andamento' },
  { chave: 'concluida', nome: 'Chegada', nota: 'concluída' },
  { chave: 'paga', nome: 'Pago', nota: 'só a partir de concluída' },
]

export function LinhaDeEstados({ estadoAtual }) {
  const cancelada = estadoAtual === 'cancelada'
  const indice = ETAPAS.findIndex((e) => e.chave === estadoAtual)
  const progresso = indice <= 0 ? 0 : indice / (ETAPAS.length - 1)
  const atual = ETAPAS[indice]

  return (
    <div className={`linha-estados ${cancelada ? 'cancelada' : ''}`}
         aria-label={cancelada ? 'Corrida cancelada' : `Etapa: ${atual?.nome ?? ''}`}>
      <div className="trilho-estados">
        <motion.div className="trilho-preenchido"
                    initial={false} animate={{ scaleX: progresso }}
                    transition={{ type: 'spring', stiffness: 120, damping: 22 }} />
        {ETAPAS.map((etapa, i) => {
          const feita = indice > i
          const agora = indice === i
          return (
            <div key={etapa.chave}
                 className={`marco ${feita ? 'feito' : ''} ${agora ? 'agora' : ''}`}
                 style={{ left: `${(i / (ETAPAS.length - 1)) * 100}%` }}>
              <motion.span className="marco-bola" initial={false}
                           animate={{ scale: agora ? 1.25 : 1 }}
                           transition={{ type: 'spring', stiffness: 500, damping: 20 }}>
                {feita && <Icone nome="check" tamanho={10} traco={3.4} />}
              </motion.span>
            </div>
          )
        })}
      </div>
      <div className="rotulos-estados">
        {ETAPAS.map((etapa, i) => (
          <span key={etapa.chave} className={indice >= i ? 'alcancado' : ''}>{etapa.nome}</span>
        ))}
      </div>
      {atual && !cancelada && <div className="nota-estado mono">{atual.chave} · {atual.nota}</div>}
      {cancelada && <div className="nota-estado mono">cancelada · estado final do DAG</div>}
    </div>
  )
}
