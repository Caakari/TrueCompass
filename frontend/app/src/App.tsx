import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useRef, useState, type MouseEvent } from 'react'
import { flushSync } from 'react-dom'
import { api, definirAoExpirar } from './api'
import { gravarSessao, lerSessao, renovar, venceEm } from './lib/sessao'
import { gravarArmazenado, lerArmazenado, movimentoReduzido } from './lib/util'
import { Acompanhar } from './telas/Acompanhar'
import { Entrada } from './telas/Entrada'
import { Motorista } from './telas/Motorista'
import { Passageiro } from './telas/Passageiro'
import type { Malha, Sessao, Tema } from './tipos'
import { Bussola } from './ui/Bussola'

const CHAVE_TEMA = 'truecompass.tema'

function temaInicial(): Tema {
  return lerArmazenado<Tema>(CHAVE_TEMA)
    ?? (window.matchMedia?.('(prefers-color-scheme: light)').matches ? 'claro' : 'escuro')
}

type DocumentoComTransicao = Document & {
  startViewTransition?: (atualizar: () => void) => { ready: Promise<void> }
}

/** Código do link público de acompanhamento (?acompanhar=...), se houver. */
function codigoDeAcompanhamento(): string | null {
  try { return new URLSearchParams(window.location.search).get('acompanhar') } catch { return null }
}

export default function App() {
  // Link compartilhado: abre direto o acompanhamento, sem login.
  const [codigo] = useState(codigoDeAcompanhamento)
  const [sessao, definirSessao] = useState<Sessao | null>(lerSessao)
  const [tema, definirTema] = useState<Tema>(temaInicial)
  const [malha, definirMalha] = useState<Malha | null>(null)
  const [falhaBackend, definirFalhaBackend] = useState<string | null>(null)
  const [iris, definirIris] = useState<{ x: number; y: number } | null>(null)

  useEffect(() => {
    document.documentElement.dataset.tema = tema
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', tema === 'escuro' ? '#0D0F11' : '#F4F4F1')
    gravarArmazenado(CHAVE_TEMA, tema)
  }, [tema])

  useEffect(() => { gravarSessao(sessao) }, [sessao])

  // Token venceu numa chamada (401): com "manter conectado", renova e segue
  // logado; sem, volta ao login.
  const sessaoRef = useRef(sessao)
  sessaoRef.current = sessao
  useEffect(() => {
    definirAoExpirar(() => {
      const atual = sessaoRef.current
      if (!atual?.renovacao) { definirSessao(null); return }
      renovar(atual).then(definirSessao).catch(() => definirSessao(null))
    })
  }, [])

  // Renova 5 min ANTES de vencer, para nenhuma chamada pegar o 401. Se já
  // venceu (app aberto depois de dias), renova na hora.
  useEffect(() => {
    if (!sessao?.renovacao) return
    const vence = venceEm(sessao.token)
    if (vence == null) return
    const espera = Math.min(Math.max(vence - Date.now() - 5 * 60_000, 0), 2 ** 31 - 1)
    const id = setTimeout(() => {
      renovar(sessao).then(definirSessao).catch((f: Error & { status?: number }) => {
        if (f.status === 401) definirSessao(null)       // sessão encerrada no servidor
      })
    }, espera)
    return () => clearTimeout(id)
  }, [sessao?.token])

  // Informações da malha: UMA vez, compartilhadas. A geometria das ruas não
  // vem inteira (a cidade toda tem centenas de milhares de trechos): o mapa
  // pede só o recorte visível.
  useEffect(() => {
    let vivo = true
    api.infoDaMalha()
      .then((info) => {
        if (!vivo) return
        definirMalha({ ...info, semaforos: [] })
        // Os semáforos da cidade inteira são milhares e só aparecem quando a
        // pessoa liga "Malha e semáforos": chegam depois, sem segurar a abertura.
        api.semaforos()
          .then(({ semaforos }) => { if (vivo) definirMalha((m) => m && { ...m, semaforos }) })
          .catch(() => { /* sem a camada de semáforos; o app segue */ })
      })
      .catch((f: Error) => { if (vivo) definirFalhaBackend(`${f.message} Suba o backend com: uvicorn api.main:app`) })
    return () => { vivo = false }
  }, [])

  /**
   * Troca de tema com REVELAÇÃO CIRCULAR a partir do ponto tocado (View
   * Transitions API): o tema novo se expande como uma gota de tinta. Onde a
   * API não existe, troca direto.
   */
  function alternarTema(e?: MouseEvent) {
    const novo: Tema = tema === 'escuro' ? 'claro' : 'escuro'
    const doc = document as DocumentoComTransicao
    if (!doc.startViewTransition || movimentoReduzido() || !e) { definirTema(novo); return }
    const x = e.clientX, y = e.clientY
    const raio = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y))
    doc.startViewTransition(() => { flushSync(() => definirTema(novo)) }).ready.then(() => {
      document.documentElement.animate(
        { clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${raio}px at ${x}px ${y}px)`] },
        { duration: 650, easing: 'cubic-bezier(.65,0,.35,1)', pseudoElement: '::view-transition-new(root)' },
      )
    })
  }

  // Entrar: a tela de login se fecha numa ÍRIS a partir do botão tocado, e o
  // mapa aparece por trás.
  function aoEntrar(nova: Sessao, de: { x: number; y: number }) {
    if (movimentoReduzido()) { definirSessao(nova); return }
    definirIris(de)
    setTimeout(() => definirSessao(nova), 520)
    setTimeout(() => definirIris(null), 1100)
  }

  const sair = () => {
    gravarArmazenado('truecompass.corrida', null)
    // Encerra a sessão deste aparelho no servidor (o token de renovação
    // deixa de valer), sem esperar a resposta.
    if (sessao?.renovacao) api.sair(sessao.renovacao).catch(() => {})
    definirSessao(null)
  }

  const tela = codigo ? 'acompanhar'
    : !sessao ? 'entrada' : !malha ? (falhaBackend ? 'entrada' : 'carregando') : sessao.tipo

  return (
    <div className="aplicativo">
      {/* Modo simultâneo, e não "wait": as telas são position:absolute e se
          cruzam sem conflito. Com "wait" a tela de entrada terminava de sumir
          mas nunca era desmontada, e a seguinte não entrava. */}
      <AnimatePresence initial={false}>
        <motion.div key={tela} className="tela" initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }} transition={{ duration: 0.3 }}>
          {tela === 'acompanhar' && codigo && <Acompanhar codigo={codigo} tema={tema} />}
          {tela === 'entrada' && <Entrada centro={malha?.centro ?? null} falhaBackend={falhaBackend} aoEntrar={aoEntrar} />}
          {tela === 'carregando' && (
            <div className="tela-carregando">
              <Bussola rumo={null} buscando tamanho={96} />
              <motion.span animate={{ opacity: [0.4, 1, 0.4] }} transition={{ duration: 1.6, repeat: Infinity }}>
                Carregando as ruas…
              </motion.span>
            </div>
          )}
          {sessao && malha && tela === 'passageiro' && (
            <Passageiro sessao={sessao} malha={malha} tema={tema} alternarTema={alternarTema} sair={sair} />
          )}
          {sessao && malha && tela === 'motorista' && (
            <Motorista sessao={sessao} malha={malha} tema={tema} alternarTema={alternarTema} sair={sair} />
          )}
        </motion.div>
      </AnimatePresence>

      <AnimatePresence>
        {iris && (
          <motion.div className="iris" aria-hidden="true"
                      initial={{ clipPath: `circle(0px at ${iris.x}px ${iris.y}px)` }}
                      animate={{ clipPath: [`circle(0px at ${iris.x}px ${iris.y}px)`, `circle(${Math.hypot(innerWidth, innerHeight)}px at ${iris.x}px ${iris.y}px)`] }}
                      exit={{ clipPath: `circle(0px at 50% 50%)`, transition: { duration: 0.55, ease: [0.65, 0, 0.35, 1] } }}
                      transition={{ duration: 0.5, ease: [0.65, 0, 0.35, 1] }}>
            <motion.div className="iris-bussola" initial={{ scale: 0.4, rotate: -90 }} animate={{ scale: 1, rotate: 0 }}
                        transition={{ type: 'spring', stiffness: 200, damping: 14 }}>
              <Bussola rumo={0} tamanho={86} letras={false} />
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
