import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useMemo, useRef, useState } from 'react'
import { usarBuscaLugares } from '../ganchos/usarBuscaLugares'
import { gravarArmazenado, haversine, lerArmazenado, textoDistancia, vibrar } from '../util'
import { Esqueleto } from './Basicos'
import { Icone } from './Icone'

const CHAVE_RECENTES = 'truecompass.recentes'

export function lerRecentes() {
  const lista = lerArmazenado(CHAVE_RECENTES)
  return Array.isArray(lista) ? lista : []
}

export function guardarRecente(lugar) {
  if (!lugar || lugar.gps) return
  const lista = [lugar, ...lerRecentes().filter((l) => l.id !== lugar.id)].slice(0, 8)
  gravarArmazenado(CHAVE_RECENTES, lista)
}

/** Destaca no título o trecho que casa com o que foi digitado. */
function Destaque({ texto, termo }) {
  const normalizar = (s) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
  const t = normalizar(termo.trim())
  const i = t ? normalizar(texto).indexOf(t) : -1
  if (i < 0) return texto
  return <>{texto.slice(0, i)}<mark>{texto.slice(i, i + t.length)}</mark>{texto.slice(i + t.length)}</>
}

const lista = {
  oculto: {},
  visivel: { transition: { staggerChildren: 0.035 } },
}
const item = {
  oculto: { opacity: 0, y: 10 },
  visivel: { opacity: 1, y: 0, transition: { type: 'spring', stiffness: 420, damping: 32 } },
}

/**
 * Busca de lugares em tela cheia, à moda dos apps de corrida: dois campos
 * (partida e destino) ligados por uma linha, e resultados reais vindos do
 * OpenStreetMap enquanto se digita.
 *
 * `campos` = ['origem', 'destino'] para o passageiro; ['posicao'] para o
 * motorista definir onde está.
 */
export function TelaBusca({
  token, campoInicial = 'destino', campos = ['origem', 'destino'],
  valores = {}, perto, gpsDisponivel = false,
  aoEscolher, aoUsarLocalizacao, aoEscolherNoMapa, aoFechar,
}) {
  const [campo, definirCampo] = useState(campoInicial)
  const [textos, definirTextos] = useState({})
  const entradasRef = useRef({})
  const texto = textos[campo] ?? ''
  const referencia = valores.origem ?? perto
  const { resultados, carregando, completo, erro, buscarCompleto } =
    usarBuscaLugares(token, texto, referencia)
  const recentes = useMemo(lerRecentes, [])

  useEffect(() => {
    const id = setTimeout(() => entradasRef.current[campo]?.focus(), 260)
    return () => clearTimeout(id)
  }, [campo])

  function escolher(lugar) {
    vibrar(10)
    guardarRecente(lugar)
    definirTextos((t) => ({ ...t, [campo]: '' }))
    const proximo = aoEscolher(campo, lugar)
    if (proximo) definirCampo(proximo)
  }

  const rotulos = {
    origem: 'De onde você sai?', destino: 'Para onde vamos?', posicao: 'Onde você está?',
  }
  const digitando = texto.trim().length >= 2

  return (
    <motion.div className="tela-busca"
                initial={{ y: '100%' }} animate={{ y: 0 }} exit={{ y: '100%' }}
                transition={{ type: 'spring', stiffness: 340, damping: 36 }}>
      <div className="busca-topo">
        <motion.button className="botao-icone" onClick={aoFechar} whileTap={{ scale: 0.85 }}
                       aria-label="Voltar">
          <Icone nome="voltar" tamanho={24} />
        </motion.button>
        <div className="busca-titulo">{campos.length > 1 ? 'Sua viagem' : 'Sua posição'}</div>
      </div>

      <div className={`busca-campos ${campos.length > 1 ? 'duplos' : ''}`}>
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
                <input
                  ref={(el) => { entradasRef.current[nome] = el }}
                  value={textos[nome] ?? ''}
                  placeholder={valor ? valor.titulo : rotulos[nome]}
                  className={valor ? 'tem-valor' : ''}
                  onFocus={() => definirCampo(nome)}
                  onChange={(e) => definirTextos((t) => ({ ...t, [nome]: e.target.value }))}
                  onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); buscarCompleto() } }}
                  enterKeyHint="search" autoComplete="off" autoCorrect="off" spellCheck={false}
                  aria-label={rotulos[nome]}
                />
                <AnimatePresence>
                  {ativo && carregando && (
                    <motion.span className="giro pequeno" initial={{ opacity: 0 }}
                                 animate={{ opacity: 1 }} exit={{ opacity: 0 }} />
                  )}
                  {ativo && !carregando && (textos[nome] ?? '') && (
                    <motion.button className="limpar" aria-label="Limpar"
                                   initial={{ scale: 0 }} animate={{ scale: 1 }} exit={{ scale: 0 }}
                                   onClick={(e) => { e.preventDefault(); definirTextos((t) => ({ ...t, [nome]: '' })) }}>
                      <Icone nome="fechar" tamanho={14} traco={2.6} />
                    </motion.button>
                  )}
                </AnimatePresence>
              </label>
            )
          })}
        </div>
      </div>

      <div className="busca-resultados">
        {!digitando && (
          <motion.ul className="lista-lugares" variants={lista} initial="oculto" animate="visivel">
            {gpsDisponivel && aoUsarLocalizacao && (
              <motion.li variants={item}>
                <button className="lugar destaque" onClick={() => {
                  vibrar(10)
                  const proximo = aoUsarLocalizacao(campo)
                  if (proximo) definirCampo(proximo)
                }}>
                  <span className="lugar-icone gps"><Icone nome="mira" /></span>
                  <span className="lugar-textos">
                    <span className="lugar-titulo">Usar minha localização</span>
                    <span className="lugar-detalhe">GPS do aparelho</span>
                  </span>
                </button>
              </motion.li>
            )}
            {aoEscolherNoMapa && (
              <motion.li variants={item}>
                <button className="lugar destaque" onClick={() => { vibrar(10); aoEscolherNoMapa(campo) }}>
                  <span className="lugar-icone"><Icone nome="mapa" /></span>
                  <span className="lugar-textos">
                    <span className="lugar-titulo">Escolher no mapa</span>
                    <span className="lugar-detalhe">Arraste o mapa até o ponto exato</span>
                  </span>
                </button>
              </motion.li>
            )}
            {recentes.length > 0 && <motion.li variants={item} className="lista-secao">Recentes</motion.li>}
            {recentes.map((lugar) => (
              <motion.li key={lugar.id} variants={item}>
                <ItemLugar lugar={lugar} icone="relogio" referencia={referencia}
                           aoTocar={() => escolher(lugar)} />
              </motion.li>
            ))}
          </motion.ul>
        )}

        {digitando && carregando && resultados.length === 0 && (
          <ul className="lista-lugares">
            {[0, 1, 2, 3, 4].map((i) => (
              <li key={i} className="lugar esqueleto-linha" style={{ opacity: 1 - i * 0.16 }}>
                <span className="lugar-icone"><Esqueleto largura={20} altura={20} raio={6} /></span>
                <span className="lugar-textos">
                  <Esqueleto largura={`${70 - i * 7}%`} altura={13} />
                  <Esqueleto largura={`${48 - i * 4}%`} altura={10} style={{ marginTop: 7 }} />
                </span>
              </li>
            ))}
          </ul>
        )}

        {digitando && resultados.length > 0 && (
          <motion.ul key={resultados.map((r) => r.id).join()} className="lista-lugares"
                     variants={lista} initial="oculto" animate="visivel">
            {resultados.map((lugar) => (
              <motion.li key={lugar.id} variants={item}>
                <ItemLugar lugar={lugar} termo={texto} referencia={referencia}
                           aoTocar={() => escolher(lugar)} />
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
          <motion.div className="vazio" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
            <Icone nome={erro ? 'aviso' : 'busca'} tamanho={30} />
            <strong>{erro ? 'Busca indisponível' : 'Nada encontrado aqui'}</strong>
            <span>
              {erro || 'A cobertura é o centro expandido de São Paulo, onde temos as ruas reais carregadas no grafo.'}
            </span>
            {!erro && !completo && (
              <button className="buscar-mais" onClick={buscarCompleto}>
                <Icone nome="busca" tamanho={16} /> Buscar em mais fontes
              </button>
            )}
          </motion.div>
        )}
      </div>
    </motion.div>
  )
}

function ItemLugar({ lugar, termo = '', icone, referencia, aoTocar }) {
  const distancia = referencia ? haversine(referencia, lugar) : null
  return (
    <button className="lugar" onClick={aoTocar}>
      <span className={`lugar-icone cat-${lugar.categoria}`}>
        <Icone nome={icone ?? lugar.categoria} />
      </span>
      <span className="lugar-textos">
        <span className="lugar-titulo"><Destaque texto={lugar.titulo} termo={termo} /></span>
        {lugar.detalhe && <span className="lugar-detalhe">{lugar.detalhe}</span>}
      </span>
      {distancia != null && <span className="lugar-distancia">{textoDistancia(distancia)}</span>}
    </button>
  )
}
