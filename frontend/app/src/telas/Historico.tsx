import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useState } from 'react'
import { api } from '../api'
import { reais, vibrar } from '../lib/util'
import type { EstadoCorrida, FormaPagamento, IdCategoria, ItemHistorico, TipoUsuario } from '../tipos'
import { AvaliarCorrida } from '../ui/Estrelas'
import { Aviso } from '../ui/Folha'
import { Icone } from '../ui/Icone'
import { Botao, Esqueleto } from '../ui/Movimento'
import { Painel } from './Perfil'

export const NOME_CATEGORIA: Record<IdCategoria, string> = { economico: 'Econômico', conforto: 'Conforto', grande: 'Grande' }
export const PAGAMENTOS: { id: FormaPagamento; nome: string; icone: string }[] = [
  { id: 'pix', nome: 'Pix', icone: 'raio' },
  { id: 'cartao', nome: 'Cartão', icone: 'chip' },
  { id: 'dinheiro', nome: 'Dinheiro', icone: 'dinheiro' },
]
const NOME_PAGAMENTO = Object.fromEntries(PAGAMENTOS.map((p) => [p.id, p.nome])) as Record<FormaPagamento, string>

const ESTADO: Partial<Record<EstadoCorrida, { rotulo: string; classe: string }>> = {
  paga: { rotulo: 'Paga', classe: 'ok' },
  concluida: { rotulo: 'Aguardando pagamento', classe: 'pendente' },
  cancelada: { rotulo: 'Cancelada', classe: 'cancelada' },
  em_curso: { rotulo: 'Em andamento', classe: 'andamento' },
  rota: { rotulo: 'Em andamento', classe: 'andamento' },
  alocacao: { rotulo: 'Em andamento', classe: 'andamento' },
}

function dataCurta(iso: string | null) {
  if (!iso) return ''
  // O banco grava UTC sem fuso: o "Z" faz o navegador converter para o local.
  const data = new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : `${iso}Z`)
  return data.toLocaleString('pt-BR', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })
}

export function TelaHistorico({ token, tipo, aoFechar }: { token: string; tipo: TipoUsuario; aoFechar: () => void }) {
  const [itens, definirItens] = useState<ItemHistorico[] | null>(null)
  const [fim, definirFim] = useState(false)
  const [carregando, definirCarregando] = useState(false)
  const [erro, definirErro] = useState<string | null>(null)
  const [aberto, definirAberto] = useState<number | null>(null)

  async function carregar(antesDe?: number) {
    definirCarregando(true)
    try {
      const pagina = await api.historico(token, antesDe)
      definirItens((atual) => [...(antesDe ? atual ?? [] : []), ...pagina])
      definirFim(pagina.length < 20)
    } catch (f) {
      definirErro((f as Error).message)
    } finally {
      definirCarregando(false)
    }
  }
  useEffect(() => { carregar() }, [token])

  const pagas = (itens ?? []).filter((i) => i.estado === 'paga')
  const total = pagas.reduce((s, i) => s + (i.custo_estimado ?? 0), 0)

  return (
    <Painel titulo={tipo === 'motorista' ? 'Suas corridas' : 'Suas viagens'} aoFechar={aoFechar}>
      {itens && itens.length > 0 && (
        <div className="historico-resumo">
          <div><b>{pagas.length}</b><span>{pagas.length === 1 ? 'corrida paga' : 'corridas pagas'}</span></div>
          <div><b>{reais(total)}</b><span>{tipo === 'motorista' ? 'recebidos' : 'gastos'} {fim ? 'no total' : 'nestas'}</span></div>
        </div>
      )}
      {erro && <Aviso tipo="erro">{erro}</Aviso>}
      {!itens && !erro && [0, 1, 2].map((i) => (
        <div key={i} className="item-historico"><Esqueleto largura="45%" altura={12} /><Esqueleto largura="85%" altura={16} style={{ marginTop: 10 }} /><Esqueleto largura="60%" altura={12} style={{ marginTop: 8 }} /></div>
      ))}
      {itens && itens.length === 0 && (
        <div className="historico-vazio">
          <Icone nome="rota" tamanho={34} />
          <b>{tipo === 'motorista' ? 'Nenhuma corrida ainda' : 'Nenhuma viagem ainda'}</b>
          <span>{tipo === 'motorista' ? 'Fique online para receber a primeira.' : 'Suas corridas aparecem aqui.'}</span>
        </div>
      )}
      <motion.ul className="lista-historico" initial="o" animate="v" variants={{ v: { transition: { staggerChildren: 0.05 } } }}>
        {(itens ?? []).map((item) => {
          const estado = ESTADO[item.estado] ?? { rotulo: item.estado, classe: '' }
          const avaliavel = (item.estado === 'concluida' || item.estado === 'paga') && item.minha_avaliacao == null && item.outro_nome
          return (
            <motion.li key={item.id} className="item-historico" variants={{ o: { opacity: 0, y: 12 }, v: { opacity: 1, y: 0 } }}>
              <div className="item-historico-topo">
                <span>{dataCurta(item.criada_em)}</span>
                <span className={`selo-estado ${estado.classe}`}>{estado.rotulo}</span>
              </div>
              <div className="item-historico-trajeto">
                <span className="trilho-mini" aria-hidden="true"><i className="o" /><i className="l" /><i className="d" /></span>
                <div>
                  <b>{item.origem_texto ?? 'Partida'}</b>
                  <b>{item.destino_texto ?? 'Destino'}</b>
                </div>
              </div>
              <div className="item-historico-rodape">
                <span>
                  {item.categoria && <>{NOME_CATEGORIA[item.categoria]} · </>}
                  {item.forma_pagamento && <>{NOME_PAGAMENTO[item.forma_pagamento]} · </>}
                  {item.outro_nome ?? 'sem motorista'}
                </span>
                <b>{item.estado === 'cancelada' ? '—' : reais(item.custo_estimado)}</b>
              </div>
              {item.minha_avaliacao != null && (
                <span className="item-historico-nota">Você deu {'★'.repeat(item.minha_avaliacao)}{'☆'.repeat(5 - item.minha_avaliacao)}</span>
              )}
              {avaliavel && (
                aberto === item.id ? (
                  <AvaliarCorrida quem={item.outro_nome!.split(' ')[0]} notaDada={null}
                                  enviar={async (nota, comentario) => {
                                    await api.avaliar(token, item.id, nota, comentario)
                                    vibrar([10, 40, 10])
                                    definirItens((l) => l && l.map((i) => i.id === item.id ? { ...i, minha_avaliacao: nota } : i))
                                    definirAberto(null)
                                  }} />
                ) : (
                  <button className="link-avaliar" onClick={() => { vibrar(6); definirAberto(item.id) }}>
                    Avaliar {item.outro_nome!.split(' ')[0]}
                  </button>
                )
              )}
            </motion.li>
          )
        })}
      </motion.ul>
      <AnimatePresence>
        {itens && !fim && itens.length > 0 && (
          <Botao variante="secundario" carregando={carregando} onClick={() => carregar(itens[itens.length - 1].id)}>Carregar mais</Botao>
        )}
      </AnimatePresence>
    </Painel>
  )
}
