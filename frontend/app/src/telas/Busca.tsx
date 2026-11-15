import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useBuscaLugares } from '../ganchos'
import { gravarArmazenado, haversine, lerArmazenado, textoDistancia, vibrar } from '../lib/util'
import type { Lugar, Ponto } from '../tipos'
import { Icone } from '../ui/Icone'
import { Esqueleto } from '../ui/Movimento'

const CHAVE_RECENTES = 'truecompass.recentes'

export function lerRecentes(): Lugar[] {
  const lista = lerArmazenado<Lugar[]>(CHAVE_RECENTES)
  return Array.isArray(lista) ? lista : []
}

export function guardarRecente(lugar: Lugar | null) {
  if (!lugar || lugar.gps) return
  gravarArmazenado(CHAVE_RECENTES, [lugar, ...lerRecentes().filter((l) => l.id !== lugar.id)].slice(0, 8))
}

export type Campo = 'origem' | 'destino' | 'posicao'

const ROTULOS: Record<Campo, string> = {
  origem: 'De onde você sai?', destino: 'Para onde vamos?', posicao: 'Onde você está?',
}

/** Destaca no título o trecho que casa com o que foi digitado (sem acento). */
function Destaque({ texto, termo }: { texto: string; termo: string }) {
  const normal = (s: string) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
  const t = normal(termo.trim())
  const i = t ? normal(texto).indexOf(t) : -1
  if (i < 0) return <>{texto}</>
  return <>{texto.slice(0, i)}<mark>{texto.slice(i, i + t.length)}</mark>{texto.slice(i + t.length)}</>
}

const lista = { o: {}, v: { transition: { staggerChildren: 0.04 } } }
const item = {
  o: { opacity: 0, y: 18, scale: 0.96 },
  v: { opacity: 1, y: 0, scale: 1, transition: { type: 'spring', stiffness: 460, damping: 30 } },
}

interface Props {
  token: string
  campoInicial: Campo
  campos: Campo[]
  valores: Partial<Record<Campo, Lugar | null>>
  perto: Ponto | null
  gpsDisponivel?: boolean
  /** Devolve o próximo campo a focar, ou nada para fechar. */
  aoEscolher: (campo: Campo, lugar: Lugar) => Campo | void
  aoUsarLocalizacao?: (campo: Campo) => Campo | void
  aoEscolherNoMapa?: (campo: Campo) => void
  aoFechar: () => void
  /** Título da tela e texto do campo, quando a busca serve a outra coisa
   *  (ex.: definir o endereço de Casa). */
  titulo?: string
  rotulo?: string
}

/**
 * Busca de lugares em tela cheia: dois campos ligados por um trilho (partida
 * e destino) e resultados reais do OpenStreetMap enquanto se digita.
 */
export function Busca({
  token, campoInicial, campos, valores, perto, gpsDisponivel = false,
  aoEscolher, aoUsarLocalizacao, aoEscolherNoMapa, aoFechar, titulo, rotulo,
}: Props) {
  const [campo, definirCampo] = useState<Campo>(campoInicial)
  const [textos, definirTextos] = useState<Partial<Record<Campo, string>>>({})
  const entradas = useRef<Partial<Record<Campo, HTMLInputElement | null>>>({})
  const texto = textos[campo] ?? ''
  const referencia = valores.origem ?? perto
  const { resultados, carregando, completo, erro, buscarCompleto } = useBuscaLugares(token, texto, referencia ?? null)
  const recentes = useMemo(lerRecentes, [])
  const digitando = texto.trim().length >= 2

  useEffect(() => {
    const id = setTimeout(() => entradas.current[campo]?.focus(), 320)
    return () => clearTimeout(id)
  }, [campo])

  function escolher(lugar: Lugar) {
    vibrar(10)
    guardarRecente(lugar)
    definirTextos((t) => ({ ...t, [campo]: '' }))
    const proximo = aoEscolher(campo, lugar)
    if (proximo) definirCampo(proximo)
  }

  return (
    <motion.div className="tela-busca" initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                exit={{ opacity: 0, transition: { delay: 0.1 } }}>
      <motion.div className="busca-fundo" initial={{ clipPath: 'circle(0% at 50% 85%)' }}
                  animate={{ clipPath: 'circle(150% at 50% 85%)' }}
                  exit={{ clipPath: 'circle(0% at 50% 85%)' }}
                  transition={{ duration: 0.55, ease: [0.65, 0, 0.35, 1] }} />
      <div className="busca-topo">
        <motion.button className="botao-icone" onClick={aoFechar} whileTap={{ scale: 0.8, rotate: -20 }}
                       aria-label="Voltar" initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0, transition: { delay: 0.15 } }}>
          <Icone nome="voltar" tamanho={24} />
        </motion.button>
        <motion.div className="busca-titulo" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0, transition: { delay: 0.18 } }}>
          {titulo ?? (campos.length > 1 ? 'Sua viagem' : 'Sua posição')}
        </motion.div>
      </div>

      <motion.div layoutId="caixa-busca" className={`busca-campos ${campos.length > 1 ? 'duplos' : ''}`}
                  transition={{ type: 'spring', stiffness: 380, damping: 34 }}>
        {campos.length > 1 && (
          <div className="busca-trilho" aria-hidden="true">
            <span className="trilho-origem" /><span className="trilho-linha" /><span className="trilho-destino" />
          </div>
        )}
        <div className="busca-entradas">
          {campos.map((nome) => {
            const valor = valores[nome]
            const ativo = campo === nome
            return (
              <label key={nome} className={`busca-entrada ${ativo ? 'ativa' : ''}`}>
                {ativo && <motion.span layoutId="foco-busca" className="busca-foco"
                                       transition={{ type: 'spring', stiffness: 500, damping: 36 }} />}
                <input ref={(el) => { entradas.current[nome] = el }}
                       value={textos[nome] ?? ''}
                       placeholder={valor ? valor.titulo : (rotulo ?? ROTULOS[nome])}
                       className={valor ? 'tem-valor' : ''}
                       aria-label={ROTULOS[nome]}
                       onFocus={() => definirCampo(nome)}
                       onChange={(e) => definirTextos((t) => ({ ...t, [nome]: e.target.value }))}
                       onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); buscarCompleto() } }}
                       enterKeyHint="search" autoComplete="off" autoCorrect="off" spellCheck={false} />
                <AnimatePresence>
                  {ativo && carregando && (
                    <motion.span key="g" className="giro pequeno" initial={{ opacity: 0, scale: 0 }}
                                 animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0 }} />
                  )}
                  {ativo && !carregando && (textos[nome] ?? '') && (
                    <motion.button key="l" className="limpar" aria-label="Limpar"
                                   initial={{ scale: 0, rotate: -90 }} animate={{ scale: 1, rotate: 0 }} exit={{ scale: 0 }}
                                   onClick={(e) => { e.preventDefault(); definirTextos((t) => ({ ...t, [nome]: '' })) }}>
                      <Icone nome="fechar" tamanho={13} traco={2.8} />
                    </motion.button>
                  )}
                </AnimatePresence>
              </label>
            )
          })}
        </div>
      </motion.div>

      <div className="busca-resultados">
        <AnimatePresence mode="wait">
          {!digitando && (
            <motion.ul key="atalhos" className="lista-lugares" variants={lista} initial="o" animate="v" exit={{ opacity: 0 }}>
              {gpsDisponivel && aoUsarLocalizacao && (
                <motion.li variants={item}>
                  <button className="lugar destaque" onClick={() => {
                    vibrar(10)
                    const proximo = aoUsarLocalizacao(campo)
                    if (proximo) definirCampo(proximo)
                  }}>
                    <span className="lugar-icone gps"><Icone nome="mira" /></span>
                    <span className="lugar-textos"><span className="lugar-titulo">Usar minha localização</span>
                      <span className="lugar-detalhe">GPS do aparelho</span></span>
                  </button>
                </motion.li>
              )}
              {aoEscolherNoMapa && (
                <motion.li variants={item}>
                  <button className="lugar destaque" onClick={() => { vibrar(10); aoEscolherNoMapa(campo) }}>
                    <span className="lugar-icone"><Icone nome="mapa" /></span>
                    <span className="lugar-textos"><span className="lugar-titulo">Escolher no mapa</span>
                      <span className="lugar-detalhe">Arraste o mapa até o ponto exato</span></span>
                  </button>
                </motion.li>
              )}
              {recentes.length > 0 && <motion.li variants={item} className="lista-secao">Recentes</motion.li>}
              {recentes.map((lugar) => (
                <motion.li key={lugar.id} variants={item}>
                  <ItemLugar lugar={lugar} icone="relogio" referencia={referencia ?? null} aoTocar={() => escolher(lugar)} />
                </motion.li>
              ))}
            </motion.ul>
          )}

          {digitando && carregando && resultados.length === 0 && (
            <motion.ul key="esqueleto" className="lista-lugares" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
              {[0, 1, 2, 3, 4].map((i) => (
                <li key={i} className="lugar" style={{ opacity: 1 - i * 0.16 }}>
                  <span className="lugar-icone"><Esqueleto largura={20} altura={20} raio={6} /></span>
                  <span className="lugar-textos">
                    <Esqueleto largura={`${70 - i * 7}%`} altura={13} />
                    <Esqueleto largura={`${48 - i * 4}%`} altura={10} style={{ marginTop: 7 }} />
                  </span>
                </li>
              ))}
            </motion.ul>
          )}

          {digitando && resultados.length > 0 && (
            <motion.ul key={resultados.map((r) => r.id).join()} className="lista-lugares"
                       variants={lista} initial="o" animate="v" exit={{ opacity: 0, transition: { duration: 0.1 } }}>
              {resultados.map((lugar) => (
                <motion.li key={lugar.id} variants={item}>
                  <ItemLugar lugar={lugar} termo={texto} referencia={referencia ?? null} aoTocar={() => escolher(lugar)} />
                </motion.li>
              ))}
              {!completo && (
                <motion.li variants={item}>
                  <button className="buscar-mais" onClick={buscarCompleto}>
                    <Icone nome="busca" tamanho={16} /> Não achou? Buscar em mais fontes
                  </button>
                </motion.li>
              )}
            </motion.ul>
          )}

          {digitando && !carregando && resultados.length === 0 && (
            <motion.div key="vazio" className="vazio" initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
              <motion.span animate={{ rotate: [0, -12, 10, -6, 0] }} transition={{ duration: 0.7 }}>
                <Icone nome={erro ? 'aviso' : 'busca'} tamanho={32} />
              </motion.span>
              <strong>{erro ? 'Busca indisponível' : 'Nada encontrado aqui'}</strong>
              <span>{erro || 'A cobertura é a cidade de São Paulo inteira: as ruas reais do OpenStreetMap estão no grafo.'}</span>
              {!erro && !completo && (
                <button className="buscar-mais" onClick={buscarCompleto}><Icone nome="busca" tamanho={16} /> Buscar em mais fontes</button>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  )
}

function ItemLugar({ lugar, termo = '', icone, referencia, aoTocar }:
  { lugar: Lugar; termo?: string; icone?: string; referencia: Ponto | null; aoTocar: () => void }) {
  const distancia = referencia ? haversine(referencia, lugar) : null
  return (
    <motion.button className="lugar" onClick={aoTocar} whileTap={{ scale: 0.97 }} whileHover={{ x: 4 }}>
      <span className={`lugar-icone cat-${lugar.categoria}`}><Icone nome={icone ?? lugar.categoria} /></span>
      <span className="lugar-textos">
        <span className="lugar-titulo"><Destaque texto={lugar.titulo} termo={termo} /></span>
        {lugar.detalhe && <span className="lugar-detalhe">{lugar.detalhe}</span>}
      </span>
      {distancia != null && <span className="lugar-distancia">{textoDistancia(distancia)}</span>}
    </motion.button>
  )
}
