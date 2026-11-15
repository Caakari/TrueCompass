import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { vibrar } from '../lib/util'
import type { Mensagem } from '../tipos'
import { Aviso } from '../ui/Folha'
import { Icone } from '../ui/Icone'
import { Painel } from './Perfil'

const RAPIDAS: Record<'passageiro' | 'motorista', string[]> = {
  passageiro: ['Já estou no local', 'Estou chegando', 'Pode me esperar um minuto?', 'Ok, obrigado!'],
  motorista: ['Estou chegando', 'Cheguei ao local', 'Estou em frente', 'Ok!'],
}

function hora(iso: string | null) {
  if (!iso) return ''
  const data = new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : `${iso}Z`)
  return data.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
}

/**
 * Chat da corrida. O histórico vem do backend uma vez; as mensagens novas
 * chegam pelo WebSocket da corrida (`novaMensagem`) — nada de consultar a
 * cada segundo. A própria mensagem enviada entra pela resposta do POST, e o
 * eco que volta pelo socket é descartado pelo id.
 */
export function TelaChat({ token, corridaId, euId, papel, outroNome, novaMensagem, aberto, aoFechar }: {
  token: string; corridaId: number; euId: number; papel: 'passageiro' | 'motorista'
  outroNome: string; novaMensagem: Mensagem | null; aberto: boolean; aoFechar: () => void
}) {
  const [mensagens, definirMensagens] = useState<Mensagem[]>([])
  const [texto, definirTexto] = useState('')
  const [enviando, definirEnviando] = useState(false)
  const [erro, definirErro] = useState<string | null>(null)
  const fimRef = useRef<HTMLDivElement>(null)

  const juntar = (novas: Mensagem[]) => definirMensagens((atual) => {
    const ids = new Set(atual.map((m) => m.id))
    return [...atual, ...novas.filter((m) => !ids.has(m.id))].sort((a, b) => a.id - b.id)
  })

  useEffect(() => { api.mensagens(token, corridaId).then(juntar).catch((f: Error) => definirErro(f.message)) }, [corridaId])
  useEffect(() => { if (novaMensagem) juntar([novaMensagem]) }, [novaMensagem?.id])
  useEffect(() => { fimRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }) }, [mensagens.length, aberto])

  async function enviar(conteudo: string) {
    const limpo = conteudo.trim()
    if (!limpo || enviando) return
    definirEnviando(true)
    definirErro(null)
    try {
      juntar([await api.enviarMensagem(token, corridaId, limpo)])
      definirTexto('')
      vibrar(8)
    } catch (f) {
      definirErro((f as Error).message)
    } finally {
      definirEnviando(false)
    }
  }

  return (
    <Painel titulo={outroNome} aoFechar={aoFechar}>
      <div className="chat-mensagens" role="log" aria-live="polite">
        {mensagens.length === 0 && !erro && (
          <div className="chat-vazio">
            <Icone nome="chat" tamanho={30} />
            <span>Combine o embarque com {outroNome}. As mensagens ficam só nesta corrida.</span>
          </div>
        )}
        <AnimatePresence initial={false}>
          {mensagens.map((m) => {
            const minha = m.autor_id === euId
            return (
              <motion.div key={m.id} className={`balao ${minha ? 'minha' : 'dele'}`}
                          initial={{ opacity: 0, y: 10, scale: 0.95 }} animate={{ opacity: 1, y: 0, scale: 1 }}>
                <span>{m.texto}</span>
                <small>{hora(m.criada_em)}</small>
              </motion.div>
            )
          })}
        </AnimatePresence>
        <div ref={fimRef} />
      </div>
      {erro && <Aviso tipo="erro">{erro}</Aviso>}
      <div className="chat-rapidas">
        {RAPIDAS[papel].map((r) => (
          <button key={r} className="chip" onClick={() => enviar(r)} disabled={enviando}>{r}</button>
        ))}
      </div>
      <form className="chat-entrada" onSubmit={(e) => { e.preventDefault(); enviar(texto) }}>
        <input className="campo-texto" value={texto} maxLength={500} placeholder={`Mensagem para ${outroNome}`}
               onChange={(e) => definirTexto(e.target.value)} aria-label="Mensagem" />
        <motion.button type="submit" className="botao-enviar" disabled={!texto.trim() || enviando}
                       whileTap={{ scale: 0.85 }} aria-label="Enviar">
          <Icone nome="seta" tamanho={20} />
        </motion.button>
      </form>
    </Painel>
  )
}
