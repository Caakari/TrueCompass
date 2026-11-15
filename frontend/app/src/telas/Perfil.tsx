import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useState } from 'react'
import { api } from '../api'
import { milhar, vibrar } from '../lib/util'
import type { EdicaoPerfil, LocalSalvo, Lugar, Perfil, Ponto, TipoLocal } from '../tipos'
import { NotaMedia } from '../ui/Estrelas'
import { Aviso } from '../ui/Folha'
import { Icone } from '../ui/Icone'
import { Botao, Esqueleto } from '../ui/Movimento'
import { Busca } from './Busca'

export const CORES_AVATAR = ['#2F8A4C', '#C5303E', '#1D4FB0', '#8F6E38', '#6B4FA0', '#D08F3E', '#2A8C8C', '#4A5560']
export const ICONE_LOCAL: Record<TipoLocal, string> = { casa: 'endereco', trabalho: 'servico', outro: 'pino' }

export function iniciais(nome: string | null | undefined) {
  return (nome || '?').split(' ').filter(Boolean).map((p) => p[0]).slice(0, 2).join('').toUpperCase()
}

/** Painel em tela cheia, com a mesma entrada circular da busca. */
export function Painel({ titulo, aoFechar, children }: { titulo: string; aoFechar: () => void; children: React.ReactNode }) {
  return (
    <motion.div className="tela-busca tela-painel" initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                exit={{ opacity: 0, transition: { delay: 0.1 } }}>
      <motion.div className="busca-fundo" initial={{ clipPath: 'circle(0% at 8% 4%)' }}
                  animate={{ clipPath: 'circle(150% at 8% 4%)' }} exit={{ clipPath: 'circle(0% at 8% 4%)' }}
                  transition={{ duration: 0.5, ease: [0.65, 0, 0.35, 1] }} />
      <div className="busca-topo">
        <motion.button className="botao-icone" onClick={aoFechar} whileTap={{ scale: 0.8, rotate: -20 }} aria-label="Voltar"
                       initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0, transition: { delay: 0.15 } }}>
          <Icone nome="voltar" tamanho={24} />
        </motion.button>
        <motion.div className="busca-titulo" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0, transition: { delay: 0.18 } }}>
          {titulo}
        </motion.div>
      </div>
      <motion.div className="painel-conteudo" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0, transition: { delay: 0.22 } }}>
        {children}
      </motion.div>
    </motion.div>
  )
}

function CampoTexto({ id, rotulo, valor, aoMudar, ...resto }: {
  id: string; rotulo: string; valor: string; aoMudar: (v: string) => void
} & Omit<React.InputHTMLAttributes<HTMLInputElement>, 'value' | 'onChange'>) {
  return (
    <div className="campo">
      <input id={id} placeholder=" " value={valor} onChange={(e) => aoMudar(e.target.value)} {...resto} />
      <label htmlFor={id}>{rotulo}</label>
      <span className="campo-linha" />
    </div>
  )
}

/** Estado do formulário: sempre string (vazia = sem valor), nunca null. */
type Formulario = Record<'nome' | 'telefone' | 'cor_avatar' | 'placa' | 'modelo' | 'cor_carro', string>

interface Props {
  token: string
  perto: Ponto | null
  aoFechar: () => void
  /** Avisa a tela de trás que o perfil/os locais mudaram (atalhos, avatar). */
  aoMudar?: (perfil: Perfil | null, locais: LocalSalvo[]) => void
}

export function TelaPerfil({ token, perto, aoFechar, aoMudar }: Props) {
  const [perfil, definirPerfil] = useState<Perfil | null>(null)
  const [locais, definirLocais] = useState<LocalSalvo[]>([])
  const [edicao, definirEdicao] = useState<Formulario>({ nome: '', telefone: '', cor_avatar: '', placa: '', modelo: '', cor_carro: '' })
  const [salvando, definirSalvando] = useState(false)
  const [mensagem, definirMensagem] = useState<{ tipo: 'ok' | 'erro'; texto: string } | null>(null)
  const [definindo, definirDefinindo] = useState<{ tipo: TipoLocal; rotulo?: string } | null>(null)
  const [nomeFavorito, definirNomeFavorito] = useState('')

  useEffect(() => {
    Promise.all([api.perfil(token), api.locais(token)]).then(([p, l]) => {
      definirPerfil(p); definirLocais(l)
      definirEdicao({ nome: p.nome, telefone: p.telefone ?? '', cor_avatar: p.cor_avatar ?? '', placa: p.placa ?? '', modelo: p.modelo ?? '', cor_carro: p.cor_carro ?? '' })
    }).catch((f: Error) => definirMensagem({ tipo: 'erro', texto: f.message }))
  }, [token])

  const motorista = perfil?.tipo === 'motorista'
  const mudou = perfil != null && (
    edicao.nome !== perfil.nome || edicao.telefone !== (perfil.telefone ?? '') || edicao.cor_avatar !== (perfil.cor_avatar ?? '')
    || (motorista && (edicao.placa !== (perfil.placa ?? '') || edicao.modelo !== (perfil.modelo ?? '') || edicao.cor_carro !== (perfil.cor_carro ?? ''))))

  async function salvar() {
    if (!perfil) return
    definirSalvando(true)
    definirMensagem(null)
    const dados: EdicaoPerfil = { nome: edicao.nome.trim(), telefone: edicao.telefone.trim(), cor_avatar: edicao.cor_avatar }
    if (motorista) Object.assign(dados, { placa: edicao.placa.trim(), modelo: edicao.modelo.trim(), cor_carro: edicao.cor_carro.trim() })
    try {
      const novo = await api.editarPerfil(token, dados)
      definirPerfil(novo)
      aoMudar?.(novo, locais)
      vibrar([10, 40, 10])
      definirMensagem({ tipo: 'ok', texto: 'Perfil atualizado.' })
    } catch (f) {
      definirMensagem({ tipo: 'erro', texto: (f as Error).message })
    } finally {
      definirSalvando(false)
    }
  }

  async function guardarLocal(lugar: Lugar) {
    if (!definindo) return
    try {
      await api.salvarLocal(token, definindo.tipo, lugar, definindo.rotulo)
      const lista = await api.locais(token)
      definirLocais(lista)
      aoMudar?.(perfil, lista)
      vibrar(12)
    } catch (f) {
      definirMensagem({ tipo: 'erro', texto: (f as Error).message })
    }
    definirDefinindo(null)
    definirNomeFavorito('')
  }

  async function apagar(local: LocalSalvo) {
    vibrar(8)
    const lista = locais.filter((l) => l.id !== local.id)
    definirLocais(lista)
    aoMudar?.(perfil, lista)
    try { await api.apagarLocal(token, local.id) } catch { definirLocais(locais) }
  }

  const casa = locais.find((l) => l.tipo === 'casa')
  const trabalho = locais.find((l) => l.tipo === 'trabalho')
  const favoritos = locais.filter((l) => l.tipo === 'outro')

  return (
    <Painel titulo="Seu perfil" aoFechar={aoFechar}>
      {!perfil && !mensagem && (
        <div className="perfil-cabeca"><Esqueleto largura={84} altura={84} raio={42} /><div style={{ flex: 1 }}><Esqueleto largura="60%" altura={18} /><Esqueleto largura="40%" altura={12} style={{ marginTop: 8 }} /></div></div>
      )}
      {perfil && (
        <>
          <div className="perfil-cabeca">
            <motion.span className="avatar enorme" style={{ background: edicao.cor_avatar || undefined }}
                         key={edicao.cor_avatar} initial={{ scale: 0.85 }} animate={{ scale: 1 }}>
              {iniciais(edicao.nome)}
            </motion.span>
            <div className="perfil-identidade">
              <b>{perfil.nome}</b>
              <span>{perfil.email}</span>
              <span className="perfil-reputacao">
                <NotaMedia nota={perfil.nota} total={perfil.avaliacoes} />
                <span>· {milhar(perfil.corridas)} {perfil.corridas === 1 ? 'corrida' : 'corridas'}</span>
                {perfil.avaliacoes > 0 && <span>· {perfil.avaliacoes} {perfil.avaliacoes === 1 ? 'avaliação' : 'avaliações'}</span>}
              </span>
            </div>
          </div>

          <div className="cores-avatar" role="radiogroup" aria-label="Cor do avatar">
            {CORES_AVATAR.map((cor) => (
              <motion.button key={cor} role="radio" aria-checked={edicao.cor_avatar === cor} aria-label={`Cor ${cor}`}
                             className={`cor ${edicao.cor_avatar === cor ? 'escolhida' : ''}`} style={{ background: cor }}
                             whileTap={{ scale: 0.85 }} onClick={() => { vibrar(6); definirEdicao((e) => ({ ...e, cor_avatar: cor })) }} />
            ))}
          </div>

          <div className="perfil-campos">
            <CampoTexto id="perfil-nome" rotulo="Nome" valor={edicao.nome} maxLength={120} autoComplete="name"
                        aoMudar={(v) => definirEdicao((e) => ({ ...e, nome: v }))} />
            <CampoTexto id="perfil-telefone" rotulo="Telefone (opcional)" valor={edicao.telefone} inputMode="tel" maxLength={20}
                        autoComplete="tel" aoMudar={(v) => definirEdicao((e) => ({ ...e, telefone: v }))} />
            {motorista && (
              <>
                <CampoTexto id="perfil-modelo" rotulo="Modelo do carro" valor={edicao.modelo} maxLength={60}
                            aoMudar={(v) => definirEdicao((e) => ({ ...e, modelo: v }))} />
                <div className="perfil-linha-dupla">
                  <CampoTexto id="perfil-cor" rotulo="Cor do carro" valor={edicao.cor_carro} maxLength={30}
                              aoMudar={(v) => definirEdicao((e) => ({ ...e, cor_carro: v }))} />
                  <CampoTexto id="perfil-placa" rotulo="Placa" valor={edicao.placa} maxLength={10}
                              aoMudar={(v) => definirEdicao((e) => ({ ...e, placa: v.toUpperCase() }))} />
                </div>
              </>
            )}
          </div>

          <AnimatePresence>
            {mensagem && <Aviso tipo={mensagem.tipo === 'erro' ? 'erro' : undefined} icone={mensagem.tipo === 'ok' ? 'check' : undefined}>{mensagem.texto}</Aviso>}
          </AnimatePresence>
          <Botao onClick={salvar} carregando={salvando} disabled={!mudou || edicao.nome.trim().length < 2}>Salvar alterações</Botao>

          <section className="perfil-secao">
            <h3>Locais salvos</h3>
            <p className="texto-apoio esquerda">Aparecem como atalho em "Para onde?".</p>
            {(['casa', 'trabalho'] as const).map((tipo) => {
              const local = tipo === 'casa' ? casa : trabalho
              return (
                <LinhaLocal key={tipo} icone={ICONE_LOCAL[tipo]} rotulo={tipo === 'casa' ? 'Casa' : 'Trabalho'} local={local}
                            definir={() => definirDefinindo({ tipo })} apagar={local ? () => apagar(local) : undefined} />
              )
            })}
            {favoritos.map((local) => (
              <LinhaLocal key={local.id} icone={ICONE_LOCAL.outro} rotulo={local.rotulo} local={local}
                          apagar={() => apagar(local)} />
            ))}
            <div className="novo-favorito">
              <input className="campo-texto" placeholder="Nome do favorito (ex.: Academia)" maxLength={40}
                     value={nomeFavorito} onChange={(e) => definirNomeFavorito(e.target.value)} />
              <Botao variante="secundario" cheio={false} disabled={!nomeFavorito.trim()}
                     onClick={() => definirDefinindo({ tipo: 'outro', rotulo: nomeFavorito.trim() })}>
                <Icone nome="pino" tamanho={16} /> Adicionar
              </Botao>
            </div>
          </section>
        </>
      )}
      {!perfil && mensagem && <Aviso tipo="erro">{mensagem.texto}</Aviso>}

      <AnimatePresence>
        {definindo && (
          <Busca key="busca-local" token={token} campoInicial="posicao" campos={['posicao']} valores={{}} perto={perto}
                 titulo={definindo.tipo === 'casa' ? 'Endereço de casa' : definindo.tipo === 'trabalho' ? 'Endereço do trabalho' : definindo.rotulo}
                 rotulo="Busque o endereço"
                 aoEscolher={(_c, lugar) => { guardarLocal(lugar) }}
                 aoFechar={() => definirDefinindo(null)} />
        )}
      </AnimatePresence>
    </Painel>
  )
}

function LinhaLocal({ icone, rotulo, local, definir, apagar }: {
  icone: string; rotulo: string; local?: LocalSalvo; definir?: () => void; apagar?: () => void
}) {
  return (
    <motion.div className="linha-local" layout initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }}>
      <button className="lugar" onClick={definir} disabled={!definir}>
        <span className="lugar-icone"><Icone nome={icone} /></span>
        <span className="lugar-textos">
          <span className="lugar-titulo">{rotulo}</span>
          <span className="lugar-detalhe">{local ? local.titulo : 'Toque para definir'}</span>
        </span>
        {definir && <Icone nome="seta" tamanho={16} />}
      </button>
      {apagar && (
        <motion.button className="botao-icone" whileTap={{ scale: 0.8 }} onClick={apagar} aria-label={`Remover ${rotulo}`}>
          <Icone nome="fechar" tamanho={18} />
        </motion.button>
      )}
    </motion.div>
  )
}
