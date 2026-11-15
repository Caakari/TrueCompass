import { AnimatePresence, motion } from 'framer-motion'
import { useState, type ReactNode } from 'react'
import { milhar, pontoCardinal, vibrar } from '../lib/util'
import type { Corrida, EstadoCorrida, Estimativa } from '../tipos'
import { Bussola } from '../ui/Bussola'
import { Icone } from '../ui/Icone'
import { BotaoRedondo, NumeroDeslizante } from '../ui/Movimento'

// ============================================================ barra superior

/**
 * Barra flutuante: conta à esquerda, título da fase ao centro, bússola à
 * direita. A bússola aponta o azimute inicial até o destino da vez.
 */
export function BarraTopo({ rumo, rotuloRumo, titulo, buscando = false, menu }: {
  rumo: number | null
  rotuloRumo: string
  titulo: string | null
  buscando?: boolean
  menu: (fechar: () => void) => ReactNode
}) {
  const [aberto, definirAberto] = useState(false)
  return (
    <>
      <div className="barra-topo">
        <BotaoRedondo rotulo="Conta e preferências" ativo={aberto} onClick={() => definirAberto(!aberto)}>
          <Icone nome="usuario" />
        </BotaoRedondo>
        <AnimatePresence mode="popLayout">
          {titulo && (
            <motion.div key={titulo} className="pilula-titulo"
                        initial={{ opacity: 0, y: -18, scale: 0.85, filter: 'blur(6px)' }}
                        animate={{ opacity: 1, y: 0, scale: 1, filter: 'blur(0px)' }}
                        exit={{ opacity: 0, y: -14, scale: 0.9, filter: 'blur(6px)' }}
                        transition={{ y: { type: 'spring', stiffness: 420, damping: 28 }, scale: { type: 'spring', stiffness: 420, damping: 28 }, default: { duration: 0.3 } }}>
              {titulo}
            </motion.div>
          )}
        </AnimatePresence>
        <div className="bussola-flutuante"
             title={rumo == null ? 'Sem destino' : `${rotuloRumo}: ${Math.round(rumo)}° ${pontoCardinal(rumo)}`}>
          <Bussola rumo={rumo} tamanho={48} letras={false} buscando={buscando} />
          <AnimatePresence>
            {rumo != null && (
              <motion.span className="bussola-graus mono" initial={{ opacity: 0, height: 0 }}
                           animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }}>
                {Math.round(rumo)}° {pontoCardinal(rumo)}
              </motion.span>
            )}
          </AnimatePresence>
        </div>
      </div>
      <AnimatePresence>
        {aberto && (
          <>
            <motion.div className="veu" onClick={() => definirAberto(false)}
                        initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} />
            <motion.div className="menu-conta"
                        initial={{ opacity: 0, scale: 0.6, y: -20, rotate: -4 }}
                        animate={{ opacity: 1, scale: 1, y: 0, rotate: 0 }}
                        exit={{ opacity: 0, scale: 0.8, y: -10 }}
                        transition={{ type: 'spring', stiffness: 460, damping: 26 }}
                        style={{ transformOrigin: '24px 0px' }}>
              <motion.div initial="o" animate="v" variants={{ v: { transition: { staggerChildren: 0.04, delayChildren: 0.06 } } }}>
                {menu(() => definirAberto(false))}
              </motion.div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </>
  )
}

const itemVariante = { o: { opacity: 0, x: -12 }, v: { opacity: 1, x: 0 } }

export function ItemMenu({ icone, children, onClick, perigo = false, valor }: {
  icone: string; children: ReactNode; onClick?: (e: React.MouseEvent) => void; perigo?: boolean; valor?: boolean
}) {
  return (
    <motion.button variants={itemVariante} className={`item-menu ${perigo ? 'perigo' : ''}`}
                   whileTap={{ scale: 0.97 }} onClick={(e) => { vibrar(6); onClick?.(e) }}>
      <Icone nome={icone} tamanho={19} />
      <span>{children}</span>
      {valor !== undefined && (
        <span className={`chave ${valor ? 'ligada' : ''}`}>
          <motion.i layout transition={{ type: 'spring', stiffness: 600, damping: 32 }} />
        </span>
      )}
    </motion.button>
  )
}

export function CabecaMenu({ icone, titulo, detalhe }: { icone: string; titulo: string; detalhe: string }) {
  return (
    <motion.div variants={itemVariante} className="menu-cabeca">
      <span className="avatar"><Icone nome={icone} /></span>
      <div><b>{titulo}</b><small>{detalhe}</small></div>
    </motion.div>
  )
}

/** Coluna de botões no canto direito, logo acima da folha. */
export function ControlesMapa({ base, children }: { base: number; children: ReactNode }) {
  return (
    <motion.div className="controles-mapa" initial={false} animate={{ bottom: base + 14 }}
                transition={{ type: 'spring', stiffness: 360, damping: 34 }}>
      {children}
    </motion.div>
  )
}

/**
 * Pino fixo no centro, para "escolher no mapa": quem se move é o mapa. Ele
 * levanta enquanto o mapa se mexe e pousa com um quique quando para.
 */
export function PinoCentral({ movendo, tipo, base }: { movendo: boolean; tipo: 'origem' | 'destino'; base: number }) {
  return (
    <div className="pino-central" style={{ bottom: `calc(50% - ${base / 2}px)` }}>
      <motion.div animate={{ y: movendo ? -22 : 0, scale: movendo ? 1.1 : 1 }}
                  transition={{ type: 'spring', stiffness: 520, damping: movendo ? 30 : 12 }}>
        {tipo === 'origem' ? <div className="pino-origem grande"><i /></div> : <div className="pino-destino"><span /></div>}
      </motion.div>
      <motion.span className="pino-sombra" animate={{ scale: movendo ? 0.5 : 1, opacity: movendo ? 0.25 : 0.55 }} />
    </div>
  )
}

// ======================================================== linha do DAG

/**
 * O DAG do ciclo da corrida. A ordem é a ordenação topológica que o backend
 * valida por Kahn no boot: ver a barra encher é ver o teorema funcionando —
 * nunca se pula etapa, nunca se volta atrás.
 */
export const ETAPAS: { chave: EstadoCorrida; nome: string; nota: string }[] = [
  { chave: 'pedido', nome: 'Pedido', nota: 'registrado' },
  { chave: 'alocacao', nome: 'Motorista', nota: 'busca reversa no grafo' },
  { chave: 'rota', nome: 'Rota', nota: 'A* com marcos (ALT)' },
  { chave: 'em_curso', nome: 'Viagem', nota: 'em andamento' },
  { chave: 'concluida', nome: 'Chegada', nota: 'concluída' },
  { chave: 'paga', nome: 'Pago', nota: 'só a partir de concluída' },
]

export function LinhaDeEstados({ estado }: { estado: EstadoCorrida | null }) {
  const cancelada = estado === 'cancelada'
  const indice = ETAPAS.findIndex((e) => e.chave === estado)
  const progresso = indice <= 0 ? 0 : indice / (ETAPAS.length - 1)
  const atual = ETAPAS[indice]
  return (
    <div className={`linha-estados ${cancelada ? 'cancelada' : ''}`}>
      <div className="trilho-estados">
        <motion.div className="trilho-preenchido" initial={false} animate={{ scaleX: progresso }}
                    transition={{ type: 'spring', stiffness: 90, damping: 16 }}>
          <span className="trilho-luz" />
        </motion.div>
        {ETAPAS.map((etapa, i) => {
          const feita = indice > i, agora = indice === i
          return (
            <div key={etapa.chave} className={`marco ${feita ? 'feito' : ''} ${agora ? 'agora' : ''}`}
                 style={{ left: `${(i / (ETAPAS.length - 1)) * 100}%` }}>
              <motion.span className="marco-bola" initial={false}
                           animate={{ scale: agora ? [1, 1.45, 1.25] : 1 }}
                           transition={{ duration: 0.5 }}>
                <AnimatePresence>
                  {feita && (
                    <motion.span initial={{ scale: 0, rotate: -90 }} animate={{ scale: 1, rotate: 0 }}
                                 transition={{ type: 'spring', stiffness: 600, damping: 18 }}>
                      <Icone nome="check" tamanho={10} traco={3.6} />
                    </motion.span>
                  )}
                </AnimatePresence>
              </motion.span>
            </div>
          )
        })}
      </div>
      <div className="rotulos-estados">
        {ETAPAS.map((e, i) => <span key={e.chave} className={indice >= i ? 'alcancado' : ''}>{e.nome}</span>)}
      </div>
      <div className="nota-estado mono">
        {cancelada ? 'cancelada · estado final do DAG' : atual ? `${atual.chave} · ${atual.nota}` : ''}
      </div>
    </div>
  )
}

// ============================================== como a rota foi calculada

/**
 * A* e Dijkstra rodaram sobre o MESMO par de cruzamentos no backend. O custo
 * tem de ser idêntico (o Dijkstra é o oráculo); muda quantos nós cada um
 * precisou expandir. O botão "Ver no mapa" toca as duas ondas juntas.
 */
export function DetalhesAlgoritmo({ estimativa, aoComparar }: { estimativa: Estimativa; aoComparar: () => void }) {
  const [aberto, definirAberto] = useState(false)
  const a = estimativa.algoritmo.a_estrela
  const d = estimativa.algoritmo.dijkstra
  const maior = Math.max(a.nos_expandidos, d?.nos_expandidos ?? 0, 1)
  const economia = d ? 1 - a.nos_expandidos / Math.max(d.nos_expandidos, 1) : 0

  return (
    <div className={`detalhes-alg ${aberto ? 'aberto' : ''}`}>
      <button className="detalhes-cabeca" aria-expanded={aberto} onClick={() => { vibrar(6); definirAberto(!aberto) }}>
        <Icone nome="chip" tamanho={18} />
        <span>Como esta rota foi calculada</span>
        <motion.span animate={{ rotate: aberto ? 90 : 0 }} className="detalhes-seta"><Icone nome="seta" tamanho={16} /></motion.span>
      </button>
      <AnimatePresence initial={false}>
        {aberto && (
          <motion.div className="detalhes-corpo" initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }}
                      transition={{ type: 'spring', stiffness: 300, damping: 34 }}>
            <p>
              A* sobre <b>{milhar(estimativa.algoritmo.nos_na_malha)}</b> cruzamentos reais do OpenStreetMap.
              Peso de cada rua = tempo de percurso + espera esperada nos semáforos
              (<span className="mono">r²/2c</span>).{' '}
              {estimativa.algoritmo.heuristica === 'alt'
                ? <>Heurística ALT: distâncias pré-calculadas até marcos na periferia da cidade e a
                    desigualdade triangular, <span className="mono">|d(L,t) − d(L,v)|</span> — nunca superestima,
                    e aponta o A* ao destino muito melhor que a linha reta.</>
                : <>Heurística: linha reta ÷ {estimativa.algoritmo.velocidade_max_kmh} km/h,
                    a maior velocidade medida na malha — por isso nunca superestima.</>}
            </p>
            <Barra rotulo="A*" valor={a.nos_expandidos} maior={maior} ms={a.ms} classe="a-estrela" />
            {d && <Barra rotulo="Dijkstra" valor={d.nos_expandidos} maior={maior} ms={d.ms} classe="dijkstra" atraso={0.18} />}
            {d && (
              <div className="detalhes-rodape">
                <span className={`selo ${d.mesmo_custo ? 'ok' : 'erro'}`}>
                  <Icone nome={d.mesmo_custo ? 'check' : 'aviso'} tamanho={13} traco={3} />
                  {d.mesmo_custo ? 'mesmo custo ótimo' : 'custos divergem!'}
                </span>
                {economia > 0 && <span>{Math.round(economia * 100)}% menos nós expandidos</span>}
              </div>
            )}
            {estimativa.exploracao?.dijkstra && (
              <motion.button className="botao-comparar" whileTap={{ scale: 0.96 }}
                             onClick={() => { vibrar([10, 30, 10]); aoComparar() }}>
                <Icone nome="repetir" tamanho={17} />
                Ver as duas buscas no mapa
                <span className="legenda-onda"><i className="a-estrela" />A* <i className="dijkstra" />Dijkstra</span>
              </motion.button>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

function Barra({ rotulo, valor, maior, ms, classe, atraso = 0 }:
  { rotulo: string; valor: number; maior: number; ms: number; classe: string; atraso?: number }) {
  return (
    <div className="barra-alg">
      <div className="barra-alg-rotulo">
        <span>{rotulo}</span>
        <span className="mono"><NumeroDeslizante valor={valor} formatar={(v) => milhar(Math.round(v))} /> nós · {ms.toFixed(0)} ms</span>
      </div>
      <div className="barra-alg-trilho">
        <motion.div className={`barra-alg-cheio ${classe}`} initial={{ scaleX: 0 }} animate={{ scaleX: valor / maior }}
                    transition={{ delay: 0.15 + atraso, type: 'spring', stiffness: 70, damping: 16 }} />
      </div>
    </div>
  )
}

// ========================================================= cartões diversos

export function CartaoMotorista({ corrida, categoria }: { corrida: Corrida; categoria?: string }) {
  const iniciais = (corrida.motorista_nome || 'Motorista').split(' ').map((p) => p[0]).slice(0, 2).join('').toUpperCase()
  const corridas = corrida.motorista_corridas
  return (
    <motion.div className="cartao-motorista" initial={{ opacity: 0, y: 14, rotateX: -30 }}
                animate={{ opacity: 1, y: 0, rotateX: 0 }} transition={{ type: 'spring', stiffness: 260, damping: 22, delay: 0.1 }}>
      <span className="avatar grande">{iniciais}<i className="avatar-anel" /></span>
      <div className="cartao-motorista-textos">
        <b>{corrida.motorista_nome || 'Seu motorista'}</b>
        {/* Contagem real de corridas concluídas: o protótipo não coleta notas. */}
        {corridas != null && (
          <span className="cartao-corridas">
            <Icone nome="check" tamanho={12} traco={2.6} />
            {corridas === 0 ? 'Primeira corrida' : `${milhar(corridas)} ${corridas === 1 ? 'corrida' : 'corridas'}`}
          </span>
        )}
        {categoria && <span className="etiqueta-categoria"><Icone nome="carro" tamanho={13} /> {categoria}</span>}
      </div>
      <div className="cartao-veiculo">
        {corrida.motorista_placa && (
          <motion.span className="placa" aria-label={`Placa ${corrida.motorista_placa}`}
                       initial={{ rotateY: 90 }} animate={{ rotateY: 0 }} transition={{ delay: 0.35, type: 'spring', stiffness: 200, damping: 14 }}>
            <small>BRASIL</small>{corrida.motorista_placa}
          </motion.span>
        )}
        <small>{corrida.motorista_modelo || 'Carro'}</small>
      </div>
    </motion.div>
  )
}

/** Selo de fim: círculo que se fecha e o traço do ✓ (ou ×) se desenhando. */
export function SeloFinal({ ok }: { ok: boolean }) {
  return (
    <motion.svg className={`selo-final ${ok ? 'ok' : 'cancelado'}`} viewBox="0 0 80 80" width="96" height="96"
                initial={{ scale: 0.3, rotate: -40, opacity: 0 }} animate={{ scale: 1, rotate: 0, opacity: 1 }}
                transition={{ type: 'spring', stiffness: 260, damping: 13 }}>
      <motion.circle cx="40" cy="40" r="36" initial={{ pathLength: 0 }} animate={{ pathLength: 1 }}
                     transition={{ duration: 0.6, ease: 'easeOut' }} />
      <motion.path d={ok ? 'M24 41l11 11 22-24' : 'M28 28l24 24M52 28L28 52'}
                   initial={{ pathLength: 0 }} animate={{ pathLength: 1 }}
                   transition={{ delay: 0.45, duration: 0.45, ease: 'easeOut' }} />
    </motion.svg>
  )
}

export function SeloAoVivo({ conectado }: { conectado: boolean }) {
  return (
    <span className={`selo-vivo ${conectado ? 'ativo' : ''}`}>
      <span className={`ponto ${conectado ? 'pulsando' : ''}`} /> {conectado ? 'ao vivo' : 'reconectando'}
    </span>
  )
}
