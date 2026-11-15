import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useRef, useState } from 'react'
import { api, type AcaoCorrida } from '../api'
import { useCorridaAoVivo, useLocalizacao } from '../ganchos'
import { dentroDaCaixa, paraPonto, reais, rumoVerdadeiro, textoDuracao, vibrar } from '../lib/util'
import { Mapa, type ApiMapa } from '../mapa/Mapa'
import type { Corrida, EstadoCorrida, LatLon, Lugar, Malha, Ponto, ResumoMotorista, Rota, Semaforo, Sessao, Tema } from '../tipos'
import { Aviso, Folha, type Margens } from '../ui/Folha'
import { Icone } from '../ui/Icone'
import { Botao, BotaoRedondo, Confete, Odometro, TextoRevelado } from '../ui/Movimento'
import { Busca } from './Busca'
import {
  BarraTopo, CabecaMenu, ControlesMapa, ItemMenu, LinhaDeEstados, SeloAoVivo, SeloFinal,
} from './Comum'

const VAZIO: LatLon[] = []
const SEM_SEMAFOROS: Semaforo[] = []
const PASSOS_SIMULACAO = 90          // a simulação dura no máximo ~40 s
const INTERVALO_SIMULACAO_MS = 450
const FINAIS: EstadoCorrida[] = ['paga', 'cancelada']

interface Props {
  sessao: Sessao
  malha: Malha
  tema: Tema
  alternarTema: (e: React.MouseEvent) => void
  sair: () => void
}

export function Motorista({ sessao, malha, tema, alternarTema, sair }: Props) {
  const token = sessao.token
  const mapa = useRef<ApiMapa>(null)
  const gps = useLocalizacao()
  const caixa = malha.caixa
  const gpsNaArea = dentroDaCaixa(gps.posicao, caixa)

  const [usarGps, definirUsarGps] = useState(true)
  const [posicaoManual, definirPosicaoManual] = useState<Ponto | null>(null)
  const [posicaoSimulada, definirPosicaoSimulada] = useState<Ponto | null>(null)
  const [endereco, definirEndereco] = useState<Lugar | null>(null)
  const [online, definirOnline] = useState(false)
  const [choque, definirChoque] = useState(0)
  const [alternando, definirAlternando] = useState(false)
  const [corridaId, definirCorridaId] = useState<number | null>(null)
  const [corrida, definirCorrida] = useState<Corrida | null>(null)
  const [chegou, definirChegou] = useState(false)
  const [trajeto, definirTrajeto] = useState<Rota | null>(null)
  const [enderecos, definirEnderecos] = useState<{ origem?: Lugar; destino?: Lugar }>({})
  const [simulacao, definirSimulacao] = useState<{ passo: number; total: number } | null>(null)
  const [erro, definirErro] = useState<string | null>(null)
  const [ocupado, definirOcupado] = useState(false)
  const [busca, definirBusca] = useState(false)
  const [margens, definirMargens] = useState<Margens>({ base: 0, esquerda: 0 })
  const [mostrarMalha, definirMostrarMalha] = useState(false)
  const [semTiles, definirSemTiles] = useState(false)
  const [resumo, definirResumo] = useState<ResumoMotorista | null>(null)
  const [confete, definirConfete] = useState<{ x: number; y: number } | null>(null)
  const cronometro = useRef<ReturnType<typeof setInterval> | undefined>(undefined)
  const ultimaSimulada = useRef<Ponto | null>(null)
  const corridaIdRef = useRef<number | null>(null)
  corridaIdRef.current = corridaId

  const aoVivo = useCorridaAoVivo(corridaId, token)
  const estado: EstadoCorrida | null = aoVivo.estado ?? corrida?.estado ?? null
  const encerrada = estado != null && FINAIS.includes(estado)
  const indoAoDestino = estado === 'em_curso'

  // Ganhos do dia: atualizados ao entrar e a cada corrida que termina.
  useEffect(() => {
    api.resumoDoMotorista(token).then(definirResumo).catch(() => {})
  }, [corridaId === null, estado === 'paga'])

  const posicao: Ponto | null = posicaoSimulada ?? (usarGps && gpsNaArea ? gps.posicao : posicaoManual)
  const fase = !corridaId ? 'fila' : encerrada ? 'encerrada' : 'corrida'

  // ---- envia a posição; a resposta diz se há corrida atribuída
  async function enviarPosicao(p: Ponto) {
    try {
      const resposta = await api.enviarPosicao(token, p.lat, p.lon)
      const ativa = resposta.corrida_ativa
      if (ativa && ativa !== corridaIdRef.current) {
        definirCorridaId(ativa)
        definirChegou(true)
        vibrar([80, 60, 80, 60, 160])
        setTimeout(() => definirChegou(false), 2600)
      }
      return resposta
    } catch (falha) {
      definirErro((falha as Error).message)
      return null
    }
  }

  // Batida de GPS a cada 4 s enquanto online. Sem ela o motorista NUNCA
  // descobriria a corrida: é a resposta de /posicao que informa
  // corrida_ativa. Pausada durante a simulação, que envia a própria posição.
  useEffect(() => {
    if (!online || !posicao || simulacao) return
    enviarPosicao(posicao)
    const id = setInterval(() => enviarPosicao(posicao), 4000)
    return () => clearInterval(id)
  }, [online, posicao?.lat, posicao?.lon, Boolean(simulacao)])

  // Endereço da posição atual, com folga para não consultar a cada metro.
  useEffect(() => {
    if (!posicao || simulacao) return
    const controle = new AbortController()
    const id = setTimeout(() => {
      api.enderecoDoPonto(token, posicao.lat, posicao.lon, controle.signal)
        .then(({ lugar }) => definirEndereco(lugar)).catch(() => {})
    }, 600)
    return () => { clearTimeout(id); controle.abort() }
  }, [posicao?.lat, posicao?.lon, Boolean(simulacao)])

  const centralizado = useRef(false)
  useEffect(() => {
    if (posicao && !centralizado.current) {
      centralizado.current = true
      mapa.current?.voarPara(posicao, 16)
    }
  }, [posicao?.lat])

  // ---- corrida atribuída
  useEffect(() => {
    if (!corridaId) { definirCorrida(null); definirTrajeto(null); definirEnderecos({}); return }
    api.consultarCorrida(token, corridaId).then(definirCorrida).catch(() => {})
  }, [corridaId, aoVivo.versao])

  useEffect(() => {
    if (!corrida?.origem) return
    for (const [campo, ponto] of [['origem', corrida.origem], ['destino', corrida.destino]] as const) {
      if (!ponto) continue
      api.enderecoDoPonto(token, ponto[0], ponto[1])
        .then(({ lugar }) => definirEnderecos((e) => ({ ...e, [campo]: lugar }))).catch(() => {})
    }
  }, [corrida?.id])

  // Trajeto: até o passageiro (alocação/rota) ou até o destino (em curso).
  useEffect(() => {
    if (!corridaId || !estado || !['alocacao', 'rota', 'em_curso'].includes(estado)) { definirTrajeto(null); return }
    const pedido = indoAoDestino ? api.rotaDaCorrida : api.rotaDoMotorista
    pedido(token, corridaId).then((r) => {
      definirTrajeto(r)
      if (r.pontos.length > 1) mapa.current?.enquadrar(r.pontos)
    }).catch(() => definirTrajeto(null))
  }, [corridaId, estado])

  useEffect(() => {
    if (encerrada || estado === 'concluida') pararSimulacao()
    if (estado === 'paga') definirConfete({ x: window.innerWidth / 2, y: window.innerHeight * 0.6 })
  }, [estado])
  useEffect(() => () => clearInterval(cronometro.current), [])

  async function alternarOnline() {
    if (!posicao) { definirErro('Defina sua posição antes de ficar online.'); return }
    definirAlternando(true)
    definirErro(null)
    try {
      await enviarPosicao(posicao)
      await api.definirDisponibilidade(token, !online)
      if (!online) { definirChoque((c) => c + 1); vibrar([15, 60, 30]) } else vibrar(15)
      definirOnline(!online)
    } catch (falha) {
      definirErro((falha as Error).message)
    } finally {
      definirAlternando(false)
    }
  }

  /**
   * Simula o deslocamento: percorre o trajeto REAL, ponto a ponto da
   * geometria do OpenStreetMap, enviando GPS a cada passo. O passageiro vê o
   * carro andar pelas ruas via WebSocket — não é interpolação em linha reta.
   */
  function iniciarSimulacao() {
    const pontos = trajeto?.pontos ?? []
    if (pontos.length < 2 || simulacao) return
    const salto = Math.max(1, Math.ceil(pontos.length / PASSOS_SIMULACAO))
    const amostra = pontos.filter((_, i) => i % salto === 0)
    if (amostra[amostra.length - 1] !== pontos[pontos.length - 1]) amostra.push(pontos[pontos.length - 1])
    let i = 0
    definirSimulacao({ passo: 0, total: amostra.length })
    vibrar(12)
    cronometro.current = setInterval(async () => {
      if (i >= amostra.length) { pararSimulacao(); vibrar([30, 50, 30]); return }
      const p = paraPonto(amostra[i++])
      ultimaSimulada.current = p
      definirPosicaoSimulada(p)
      definirSimulacao({ passo: i, total: amostra.length })
      await enviarPosicao(p)
    }, INTERVALO_SIMULACAO_MS)
  }

  function pararSimulacao() {
    clearInterval(cronometro.current)
    cronometro.current = undefined
    definirSimulacao(null)
    // Fica onde a simulação parou, em vez de saltar de volta ao GPS.
    const ultima = ultimaSimulada.current
    ultimaSimulada.current = null
    if (ultima) { definirPosicaoManual(ultima); definirUsarGps(false) }
    definirPosicaoSimulada(null)
  }

  async function agir(acao: AcaoCorrida) {
    if (!corridaId) return
    definirOcupado(true)
    definirErro(null)
    try {
      definirCorrida(await api.transitar(token, corridaId, acao))
      vibrar(15)
    } catch (falha) {
      definirErro((falha as Error).message)
    } finally {
      definirOcupado(false)
    }
  }

  function definirPosicao(lugar: Lugar) {
    definirUsarGps(false)
    definirPosicaoManual({ lat: lugar.lat, lon: lugar.lon })
    definirEndereco(lugar)
    mapa.current?.voarPara(lugar, 16)
    if (online) enviarPosicao(lugar)
  }

  function aoClicarNoMapa(p: Ponto) {
    if (corridaId || simulacao) return
    if (!dentroDaCaixa(p, caixa)) { definirErro('Esse ponto está fora da área coberta pela malha.'); return }
    vibrar(10)
    definirErro(null)
    definirPosicao({ ...p, id: 'mapa', titulo: 'Ponto marcado no mapa', detalhe: '', categoria: 'endereco' })
    api.enderecoDoPonto(token, p.lat, p.lon).then(({ lugar }) => definirEndereco(lugar)).catch(() => {})
  }

  const passageiro = corrida?.origem ? paraPonto(corrida.origem) : null
  const destino = corrida?.destino ? paraPonto(corrida.destino) : null
  const alvo = indoAoDestino ? destino : passageiro
  const rumo = posicao && alvo ? rumoVerdadeiro(posicao, alvo) : null
  const titulo = fase === 'fila' ? (resumo ? `${reais(resumo.ganhos_hoje)} hoje` : null)
    : estado === 'em_curso' ? 'Em viagem' : estado === 'concluida' ? 'Aguardando pagamento'
    : fase === 'corrida' ? 'Indo buscar' : null

  return (
    <div className="tela-app">
      <Mapa ref={mapa} tema={tema} centro={malha.centro}
            motorista={posicao}
            origem={fase !== 'fila' ? passageiro : null}
            destino={fase !== 'fila' ? destino : null}
            radar={fase === 'fila' && online ? posicao : null}
            rota={indoAoDestino && trajeto ? trajeto.pontos : VAZIO}
            rotaMotorista={!indoAoDestino && trajeto ? trajeto.pontos : VAZIO}
            cometa={indoAoDestino}
            semaforos={mostrarMalha ? malha.semaforos : SEM_SEMAFOROS}
            mostrarMalha={mostrarMalha || semTiles}
            margens={margens}
            aoClicar={aoClicarNoMapa}
            aoFalharTiles={() => definirSemTiles(true)} />

      {/* Onda de choque ao ficar online: um anel que atravessa a tela. */}
      <AnimatePresence>
        {choque > 0 && online && (
          <motion.div key={choque} className="choque" initial={{ scale: 0, opacity: 0.9 }}
                      animate={{ scale: 1, opacity: 0 }} exit={{ opacity: 0 }}
                      transition={{ duration: 1.1, ease: [0.16, 1, 0.3, 1] }} />
        )}
      </AnimatePresence>

      <BarraTopo rumo={rumo} rotuloRumo={indoAoDestino ? 'Rumo ao destino' : 'Rumo ao passageiro'} titulo={titulo}
                 menu={(fechar) => (
                   <>
                     <CabecaMenu icone="carro" titulo="Motorista" detalhe={online ? 'disponível para corridas' : 'offline'} />
                     <ItemMenu icone={tema === 'escuro' ? 'sol' : 'lua'} onClick={alternarTema}>Tema {tema === 'escuro' ? 'claro' : 'escuro'}</ItemMenu>
                     <ItemMenu icone="camadas" valor={mostrarMalha} onClick={() => definirMostrarMalha(!mostrarMalha)}>Malha e semáforos</ItemMenu>
                     <ItemMenu icone="sair" perigo onClick={() => { fechar(); sair() }}>Sair</ItemMenu>
                   </>
                 )} />

      <ControlesMapa base={margens.base}>
        <BotaoRedondo rotulo="Centralizar em mim" onClick={() => posicao && mapa.current?.voarPara(posicao, 16)}>
          <Icone nome="mira" />
        </BotaoRedondo>
      </ControlesMapa>

      <Folha chave={fase} aoMedir={definirMargens}>
        {fase === 'fila' && (
          <Fila online={online} alternando={alternando} alternar={alternarOnline} posicao={posicao} endereco={endereco} resumo={resumo}
                erro={erro} gpsFora={Boolean(gps.posicao && !gpsNaArea)} gpsNaArea={gpsNaArea} usarGps={usarGps && gpsNaArea}
                ativarGps={() => { definirUsarGps(true); if (gps.posicao) mapa.current?.voarPara(gps.posicao, 16) }}
                abrirBusca={() => definirBusca(true)} />
        )}
        {fase === 'corrida' && corrida && (
          <CorridaMotorista corrida={corrida} estado={estado} enderecos={enderecos} trajeto={trajeto}
                            conectado={aoVivo.conectado} simulacao={simulacao}
                            iniciarSimulacao={iniciarSimulacao} pararSimulacao={pararSimulacao}
                            agir={agir} ocupado={ocupado} erro={erro} />
        )}
        {fase === 'encerrada' && (
          <Encerrada estado={estado} corrida={corrida}
                     voltar={() => { definirCorridaId(null); definirErro(null); definirConfete(null) }} />
        )}
      </Folha>

      {/* Chegada de corrida: o cartão invade a tela por um instante. */}
      <AnimatePresence>
        {chegou && corrida && (
          <motion.div className="chegada-corrida" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                      onClick={() => definirChegou(false)}>
            <motion.div className="chegada-cartao"
                        initial={{ y: 300, scale: 0.6, rotate: -8 }}
                        animate={{ y: 0, scale: 1, rotate: [0, 3, -3, 2, -1, 0] }}
                        exit={{ y: 120, scale: 0.8, opacity: 0 }}
                        transition={{ type: 'spring', stiffness: 260, damping: 16, rotate: { duration: 0.6, delay: 0.3 } }}>
              <span className="chegada-anel" /><span className="chegada-anel atraso" />
              <Icone nome="carro" tamanho={40} traco={1.6} />
              <TextoRevelado className="titulo-folha" texto="Nova corrida!" />
              <span className="chegada-valor"><Odometro texto={reais(corrida.custo_estimado)} /></span>
              {corrida.eta_segundos != null && (
                <span className="chegada-detalhes"><span>Embarque a <b>{textoDuracao(corrida.eta_segundos)}</b></span></span>
              )}
              <small>{corrida.passageiro_nome?.split(' ')[0] ?? 'Passageiro'} está esperando · toque para ver</small>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {busca && (
          <Busca key="busca" token={token} campoInicial="posicao" campos={['posicao']} valores={{}}
                 perto={posicao ?? gps.posicao}
                 aoEscolher={(_c, lugar) => { definirPosicao(lugar); definirBusca(false) }}
                 aoFechar={() => definirBusca(false)} />
        )}
      </AnimatePresence>

      <Confete origem={confete} />
    </div>
  )
}

function Fila({ online, alternando, alternar, posicao, endereco, resumo, erro, gpsFora, gpsNaArea, usarGps, ativarGps, abrirBusca }: {
  online: boolean; alternando: boolean; alternar: () => void; posicao: Ponto | null; endereco: Lugar | null
  resumo: ResumoMotorista | null; erro: string | null; gpsFora: boolean; gpsNaArea: boolean; usarGps: boolean
  ativarGps: () => void; abrirBusca: () => void
}) {
  return (
    <div className="conteudo">
      {/* O botão grande e redondo dos apps de motorista: um toque, e você
          entra (ou sai) da fila do pareamento. */}
      <motion.button className={`botao-go ${online ? 'ligado' : ''}`} onClick={() => { vibrar(10); alternar() }}
                     disabled={alternando || !posicao} whileTap={{ scale: 0.88 }} whileHover={{ scale: 1.04 }}
                     animate={online ? {} : { boxShadow: ['0 0 0 6px var(--verde-dim)', '0 0 0 16px transparent'] }}
                     transition={online ? {} : { boxShadow: { duration: 1.8, repeat: Infinity } }}
                     aria-label={online ? 'Ficar offline' : 'Ficar online'}>
        {alternando ? <span className="giro" /> : online ? 'Pausar' : 'Iniciar'}
      </motion.button>
      <div className={`status-motorista ${online ? 'online' : ''}`}>
        <span className={`ponto ${online ? 'pulsando' : ''}`} />
        {online ? 'Você está online' : 'Você está offline'}
      </div>
      <p className="status-motorista-apoio">
        {online ? 'Procurando viagens perto de você' : posicao ? 'Toque em Iniciar para receber corridas' : 'Defina sua posição para começar'}
      </p>

      {resumo && (
        <div className="ganhos-dia">
          <div><b>{reais(resumo.ganhos_hoje)}</b><span>ganhos hoje</span></div>
          <div><b>{resumo.corridas_hoje}</b><span>{resumo.corridas_hoje === 1 ? 'corrida hoje' : 'corridas hoje'}</span></div>
          <div><b>{resumo.corridas_total}</b><span>no total</span></div>
        </div>
      )}

      <div className="posicao-motorista">
        <span className="lugar-icone gps"><Icone nome="carro" /></span>
        <div className="linha-textos">
          <small>Sua posição {usarGps ? '· GPS' : ''}</small>
          <b>{posicao ? (endereco?.titulo ?? 'Localizando endereço…') : 'Não definida'}</b>
          <span>{posicao ? endereco?.detalhe ?? '' : 'Toque no mapa, busque um endereço ou use o GPS'}</span>
        </div>
      </div>

      <div className="chips">
        <motion.button className={`chip ${usarGps ? 'ativo' : ''}`} whileTap={{ scale: 0.92 }} disabled={!gpsNaArea}
                       onClick={() => { vibrar(8); ativarGps() }}><Icone nome="mira" tamanho={16} /> GPS</motion.button>
        <motion.button className="chip" whileTap={{ scale: 0.92 }} onClick={() => { vibrar(8); abrirBusca() }}>
          <Icone nome="busca" tamanho={16} /> Buscar endereço
        </motion.button>
        <span className="chip-dica"><Icone nome="pino" tamanho={15} /> ou toque no mapa</span>
      </div>

      <AnimatePresence>
        {gpsFora && <Aviso icone="mapa">Seu GPS está fora da cidade de São Paulo, a área coberta. Marque sua posição no mapa.</Aviso>}
        {erro && <Aviso tipo="erro">{erro}</Aviso>}
      </AnimatePresence>

      {online && (
        <p className="texto-apoio esquerda">
          Quando um passageiro pedir por perto, o pareamento reverso mede seu tempo real até ele pelas ruas — não a distância em linha reta.
        </p>
      )}
    </div>
  )
}

function CorridaMotorista({ corrida, estado, enderecos, trajeto, conectado, simulacao, iniciarSimulacao, pararSimulacao, agir, ocupado, erro }: {
  corrida: Corrida; estado: EstadoCorrida | null; enderecos: { origem?: Lugar; destino?: Lugar }; trajeto: Rota | null
  conectado: boolean; simulacao: { passo: number; total: number } | null; iniciarSimulacao: () => void
  pararSimulacao: () => void; agir: (a: AcaoCorrida) => void; ocupado: boolean; erro: string | null
}) {
  const indoAoDestino = estado === 'em_curso'
  const nome = corrida.passageiro_nome?.split(' ')[0] ?? 'passageiro'
  return (
    <div className="conteudo">
      <div className="status-corrida">
        <small>{indoAoDestino ? 'Em viagem' : estado === 'concluida' ? 'Corrida concluída' : 'Nova corrida'}</small>
        <TextoRevelado className="titulo-folha" texto={`${indoAoDestino ? 'Levando' : estado === 'concluida' ? 'Corrida de' : 'Buscar'} ${nome}`} />
        <SeloAoVivo conectado={conectado} />
      </div>

      <div className="resumo-trajeto compacto">
        <div className="busca-trilho" aria-hidden="true"><span className="trilho-origem" /><span className="trilho-linha" /><span className="trilho-destino" /></div>
        <div className="resumo-linhas">
          <div><small>Embarque</small><b>{enderecos.origem?.titulo ?? '…'}</b>{enderecos.origem?.detalhe && <span>{enderecos.origem.detalhe}</span>}</div>
          <div><small>Destino</small><b>{enderecos.destino?.titulo ?? '…'}</b>{enderecos.destino?.detalhe && <span>{enderecos.destino.detalhe}</span>}</div>
        </div>
      </div>

      <div className="estatisticas duas">
        <div className="estatistica">
          <Icone nome="relogio" tamanho={17} />
          <b>{trajeto ? textoDuracao(trajeto.segundos) : '—'}</b>
          <span>{indoAoDestino ? 'até o destino' : 'até o passageiro'}</span>
        </div>
        <div className="estatistica">
          <Icone nome="dinheiro" tamanho={17} />
          <b><Odometro texto={reais(corrida.custo_estimado)} /></b>
          <span>valor da corrida</span>
        </div>
      </div>

      <LinhaDeEstados estado={estado} />
      <AnimatePresence>{erro && <Aviso tipo="erro">{erro}</Aviso>}</AnimatePresence>

      <div className="acoes">
        {estado !== 'concluida' && (
          <Botao variante={simulacao ? 'secundario' : 'primario'} disabled={!trajeto || trajeto.pontos.length < 2}
                 onClick={simulacao ? pararSimulacao : iniciarSimulacao}>
            <Icone nome={simulacao ? 'fechar' : 'rota'} tamanho={19} />
            {simulacao ? 'Parar navegação' : indoAoDestino ? 'Navegar até o destino (GPS simulado)' : 'Navegar até o embarque (GPS simulado)'}
          </Botao>
        )}
        <AnimatePresence>
          {simulacao && (
            <motion.div className="progresso-simulacao" initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 5 }} exit={{ opacity: 0, height: 0 }}>
              <motion.span animate={{ scaleX: simulacao.passo / simulacao.total }} transition={{ duration: 0.45, ease: 'linear' }} />
            </motion.div>
          )}
        </AnimatePresence>
        {estado === 'rota' && <Botao variante="secundario" carregando={ocupado} onClick={() => agir('iniciar')}>Iniciar viagem</Botao>}
        {estado === 'em_curso' && (
          <Botao variante="secundario" carregando={ocupado} onClick={() => agir('finalizar')}><Icone nome="bandeira" tamanho={18} /> Finalizar corrida</Botao>
        )}
        {estado === 'concluida' && <p className="texto-apoio">Aguardando o pagamento do passageiro…</p>}
      </div>
    </div>
  )
}

function Encerrada({ estado, corrida, voltar }: { estado: EstadoCorrida | null; corrida: Corrida | null; voltar: () => void }) {
  const paga = estado === 'paga'
  return (
    <div className="conteudo centralizado">
      <SeloFinal ok={paga} />
      <TextoRevelado className="titulo-folha pequeno" texto={paga ? 'Corrida paga' : 'Corrida cancelada'} atraso={0.3} />
      {paga && corrida && <div className="valor-final"><Odometro texto={reais(corrida.custo_estimado)} /></div>}
      <p className="texto-apoio">{paga ? 'Você já está de volta à fila.' : 'O passageiro cancelou. Você voltou à fila.'}</p>
      <Botao onClick={voltar}>Voltar à fila</Botao>
    </div>
  )
}
