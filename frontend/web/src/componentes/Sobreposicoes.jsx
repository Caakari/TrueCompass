import { AnimatePresence, motion } from 'framer-motion'
import { useState } from 'react'
import { vibrar } from '../util'
import { BotaoRedondo } from './Basicos'
import { Bussola, pontoCardinal } from './Bussola'
import { Icone } from './Icone'

/**
 * Barra superior flutuante: conta à esquerda, bússola à direita.
 *
 * A bússola não é enfeite: aponta o azimute inicial (grande círculo) até o
 * destino da vez — a mesma geometria esférica do haversine do backend.
 */
export function BarraTopo({ rumo, rotuloRumo, menu, titulo }) {
  const [menuAberto, definirMenuAberto] = useState(false)
  return (
    <>
      <div className="barra-topo">
        <BotaoRedondo rotulo="Conta e preferências" onClick={() => definirMenuAberto(!menuAberto)}
                      ativo={menuAberto}>
          <Icone nome="usuario" />
        </BotaoRedondo>
        <AnimatePresence mode="popLayout">
          {titulo && (
            <motion.div key={titulo} className="pilula-titulo"
                        initial={{ opacity: 0, y: -12, scale: 0.95 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        exit={{ opacity: 0, y: -12, scale: 0.95 }}
                        transition={{ type: 'spring', stiffness: 420, damping: 30 }}>
              {titulo}
            </motion.div>
          )}
        </AnimatePresence>
        <div className={`bussola-flutuante ${rumo == null ? 'sem-rumo' : ''}`}
             title={rumo == null ? 'Sem destino' : `${rotuloRumo}: ${Math.round(rumo)}° ${pontoCardinal(rumo)}`}>
          <Bussola rumo={rumo} tamanho={46} mostrarLetras={false} />
          <AnimatePresence>
            {rumo != null && (
              <motion.span className="bussola-graus mono"
                           initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }}
                           exit={{ opacity: 0 }}>
                {Math.round(rumo)}° {pontoCardinal(rumo)}
              </motion.span>
            )}
          </AnimatePresence>
        </div>
      </div>
      <AnimatePresence>
        {menuAberto && (
          <>
            <motion.div className="veu" onClick={() => definirMenuAberto(false)}
                        initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} />
            <motion.div className="menu-conta"
                        initial={{ opacity: 0, scale: 0.9, y: -8 }}
                        animate={{ opacity: 1, scale: 1, y: 0 }}
                        exit={{ opacity: 0, scale: 0.92, y: -6 }}
                        transition={{ type: 'spring', stiffness: 460, damping: 32 }}
                        style={{ transformOrigin: 'top left' }}>
              {menu(() => definirMenuAberto(false))}
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </>
  )
}

export function ItemMenu({ icone, children, onClick, perigo = false, valor }) {
  return (
    <motion.button className={`item-menu ${perigo ? 'perigo' : ''}`} whileTap={{ scale: 0.97 }}
                   onClick={() => { vibrar(6); onClick?.() }}>
      <Icone nome={icone} tamanho={19} />
      <span>{children}</span>
      {valor !== undefined && <span className={`chave ${valor ? 'ligada' : ''}`}><i /></span>}
    </motion.button>
  )
}

/** Coluna de botões do lado direito, logo acima da folha. */
export function ControlesMapa({ base = 0, children }) {
  return (
    <motion.div className="controles-mapa" initial={false}
                animate={{ bottom: base + 14 }}
                transition={{ type: 'spring', stiffness: 380, damping: 36 }}>
      {children}
    </motion.div>
  )
}

/**
 * Pino fixo no centro da tela, para "escolher no mapa": quem se move é o mapa.
 * Ele levanta enquanto o mapa se mexe e pousa quando para — e o endereço do
 * ponto exato é consultado ao pousar.
 */
export function PinoCentral({ movendo, tipo = 'destino', base = 0 }) {
  return (
    <div className="pino-central" style={{ bottom: `calc(50% - ${base / 2}px)` }}>
      <motion.div animate={{ y: movendo ? -14 : 0 }}
                  transition={{ type: 'spring', stiffness: 500, damping: 22 }}>
        {tipo === 'origem'
          ? <div className="pino-origem grande" />
          : <div className="pino-destino"><span /></div>}
      </motion.div>
      <motion.span className="pino-sombra" animate={{ scale: movendo ? 0.55 : 1, opacity: movendo ? 0.3 : 0.6 }} />
    </div>
  )
}

export function Aviso({ tipo = 'neutro', icone = 'aviso', children }) {
  return (
    <motion.div className={`aviso ${tipo}`} role={tipo === 'erro' ? 'alert' : undefined}
                initial={{ opacity: 0, y: -6, height: 0 }} animate={{ opacity: 1, y: 0, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}>
      <Icone nome={icone} tamanho={17} />
      <div>{children}</div>
    </motion.div>
  )
}
