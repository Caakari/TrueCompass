import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useState } from 'react'
import { api, definirAoExpirar } from './api'
import { Bussola } from './componentes/Bussola'
import { PainelMotorista } from './componentes/PainelMotorista'
import { PainelPassageiro } from './componentes/PainelPassageiro'
import { TelaAutenticacao } from './componentes/TelaAutenticacao'
import { gravarArmazenado, lerArmazenado } from './util'

const CHAVE_SESSAO = 'truecompass.sessao'
const CHAVE_TEMA = 'truecompass.tema'

function temaInicial() {
  const guardado = lerArmazenado(CHAVE_TEMA)
  if (guardado) return guardado
  return window.matchMedia?.('(prefers-color-scheme: light)').matches ? 'claro' : 'escuro'
}

export default function App() {
  const [sessao, definirSessao] = useState(() => lerArmazenado(CHAVE_SESSAO))
  const [tema, definirTema] = useState(temaInicial)
  const [malha, definirMalha] = useState(null)
  const [falhaBackend, definirFalhaBackend] = useState(null)

  useEffect(() => {
    document.documentElement.setAttribute('data-tema', tema)
    document.querySelector('meta[name="theme-color"]')
      ?.setAttribute('content', tema === 'escuro' ? '#111315' : '#F4F4F1')
    gravarArmazenado(CHAVE_TEMA, tema)
  }, [tema])

  useEffect(() => { gravarArmazenado(CHAVE_SESSAO, sessao) }, [sessao])

  // Token expirado em qualquer chamada: volta ao login.
  useEffect(() => { definirAoExpirar(() => definirSessao(null)) }, [])

  // Informações da malha: carregadas UMA vez e compartilhadas. A geometria das
  // ruas não vem mais inteira (são 118 mil cruzamentos reais): o mapa pede só
  // o recorte visível quando a camada da malha é ligada.
  useEffect(() => {
    let vivo = true
    ;(async () => {
      try {
        const [info, { semaforos }] = await Promise.all([api.infoDaMalha(), api.semaforos()])
        if (vivo) definirMalha({ ...info, semaforos })
      } catch (falha) {
        if (vivo) definirFalhaBackend(`${falha.message} Suba o backend com uvicorn api.main:app`)
      }
    })()
    return () => { vivo = false }
  }, [])

  const alternarTema = () => definirTema((t) => (t === 'escuro' ? 'claro' : 'escuro'))
  const sair = () => {
    gravarArmazenado('truecompass.corrida', null)
    definirSessao(null)
  }

  const Painel = sessao?.tipo === 'motorista' ? PainelMotorista : PainelPassageiro
  const tela = !sessao ? 'entrada' : !malha && !falhaBackend ? 'carregando' : sessao.tipo

  return (
    <AnimatePresence mode="wait">
      <motion.div key={tela} className="aplicativo"
                  initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                  transition={{ duration: 0.25 }}>
        {tela === 'entrada' && <TelaAutenticacao aoEntrar={definirSessao} falhaBackend={falhaBackend} />}
        {tela === 'carregando' && (
          <div className="tela-carregando">
            <Bussola rumo={null} tamanho={92} />
            <span>Carregando as ruas…</span>
          </div>
        )}
        {sessao && tela !== 'carregando' && (
          <Painel sessao={sessao} malha={malha} tema={tema} alternarTema={alternarTema} sair={sair} />
        )}
      </motion.div>
    </AnimatePresence>
  )
}
