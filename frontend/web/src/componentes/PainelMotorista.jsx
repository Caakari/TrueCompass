import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../api'
import { usarCorridaAoVivo } from '../ganchos/usarCorridaAoVivo'
import { usarLocalizacao } from '../ganchos/usarLocalizacao'
import { dentroDaCaixa, reais, textoDuracao, vibrar } from '../util'
import { Botao, BotaoRedondo, NumeroAnimado } from './Basicos'
import { rumoVerdadeiro } from './Bussola'
import { Folha } from './Folha'
import { Icone } from './Icone'
import { LinhaDeEstados } from './LinhaDeEstados'
import { Mapa } from './Mapa'
import { Aviso, BarraTopo, ControlesMapa, ItemMenu } from './Sobreposicoes'
import { TelaBusca } from './TelaBusca'

const VAZIO = []
const PASSOS_SIMULACAO = 90       // a simulação dura no máximo ~40 s
const INTERVALO_SIMULACAO_MS = 450

const transicaoConteudo = {
  initial: { opacity: 0, y: 18 },
  animate: { opacity: 1, y: 0, transition: { type: 'spring', stiffness: 380, damping: 34 } },
  exit: { opacity: 0, y: -10, transition: { duration: 0.14 } },
}

export function PainelMotorista({ sessao, malha, tema, alternarTema, sair }) {
  const token = sessao.token
  const mapaRef = useRef(null)
  const gps = usarLocalizacao()
  const caixa = malha?.caixa
  const gpsNaArea = Boolean(gps.posicao && dentroDaCaixa(gps.posicao, caixa))

  const [usarGps, definirUsarGps] = useState(true)
  const [posicaoManual, definirPosicaoManual] = useState(null)
  const [posicaoSimulada, definirPosicaoSimulada] = useState(null)
  const [endereco, definirEndereco] = useState(null)
  const [online, definirOnline] = useState(false)
  const [alternando, definirAlternando] = useState(false)
  const [corridaId, definirCorridaId] = useState(null)
  const [corrida, definirCorrida] = useState(null)
  const [trajeto, definirTrajeto] = useState(null)
  const [enderecos, definirEnderecos] = useState({})
  const [simulacao, definirSimulacao] = useState(null)       // { passo, total }
  const [erro, definirErro] = useState(null)
  const [ocupado, definirOcupado] = useState(false)
  const [busca, definirBusca] = useState(false)
  const [margens, definirMargens] = useState({ base: 0, esquerda: 0 })
  const [mostrarMalha, definirMostrarMalha] = useState(false)
  const cronometroRef = useRef(null)
  const ultimaSimuladaRef = useRef(null)
  const corridaIdRef = useRef(null)
  corridaIdRef.current = corridaId

  const aoVivo = usarCorridaAoVivo(corridaId, token)
  const estado = aoVivo.estado?.estado ?? corrida?.estado ?? null
  const encerrada = ['paga', 'cancelada'].includes(estado)

  const posicao = posicaoSimulada
    ?? (usarGps && gpsNaArea ? gps.posicao : posicaoManual)

  const fase = !corridaId ? 'fila' : encerrada ? 'encerrada' : 'corrida'

  // ---- envia a posição; a resposta diz se há corrida atribuída
  async function enviarPosicao(lat, lon) {
    try {
      const resposta = await api.enviarPosicao(token, lat, lon)
      const ativa = resposta.corrida_ativa
      if (ativa && ativa !== corridaIdRef.current) {
        definirCorridaId(ativa)
        vibrar([60, 80, 60, 80, 60])
      }
      return resposta
    } catch (falha) {
      definirErro(falha.message)
      return null
    }
  }

  // Batida de GPS a cada 4 s enquanto online. Sem ela o motorista NUNCA
  // descobriria a corrida: é a resposta de /posicao que informa corrida_ativa.
  // Pausada durante a simulação, que já envia a própria posição.
  useEffect(() => {
    if (!online || !posicao || simulacao) return
    enviarPosicao(posicao.lat, posicao.lon)
    const id = setInterval(() => enviarPosicao(posicao.lat, posicao.lon), 4000)
    return () => clearInterval(id)
  }, [online, posicao?.lat, posicao?.lon, Boolean(simulacao)])

  // Endereço da posição atual (com folga, para não consultar a cada metro).
  useEffect(() => {
    if (!posicao || simulacao) return
    const controle = new AbortController()
    const id = setTimeout(() => {
      api.enderecoDoPonto(token, posicao.lat, posicao.lon, controle.signal)
        .then(({ lugar }) => definirEndereco(lugar)).catch(() => {})
    }, 600)
    return () => { clearTimeout(id); controle.abort() }
  }, [posicao?.lat, posicao?.lon, Boolean(simulacao)])

  // Centraliza no motorista quando a posição é definida pela primeira vez.
  const centralizadoRef = useRef(false)
  useEffect(() => {
    if (posicao && !centralizadoRef.current) {
      centralizadoRef.current = true
      mapaRef.current?.voarPara(posicao.lat, posicao.lon, 16)
    }
  }, [posicao?.lat])

  // ---- corrida atribuída
  useEffect(() => {
    if (!corridaId) { definirCorrida(null); definirTrajeto(null); definirEnderecos({}); return }
    api.consultarCorrida(token, corridaId).then(definirCorrida).catch(() => {})
  }, [corridaId, aoVivo.estado?.estado])

  useEffect(() => {
    if (!corrida?.origem) return
    const pedidos = [['origem', corrida.origem], ['destino', corrida.destino]]
    for (const [campo, ponto] of pedidos) {
      if (!ponto) continue
      api.enderecoDoPonto(token, ponto[0], ponto[1])
        .then(({ lugar }) => definirEnderecos((e) => ({ ...e, [campo]: lugar })))
        .catch(() => {})
    }
  }, [corrida?.id])

  // Trajeto: até o passageiro (alocação/rota) ou até o destino (em curso).
  const indoAoDestino = estado === 'em_curso'
  useEffect(() => {
    if (!corridaId || !['alocacao', 'rota', 'em_curso'].includes(estado)) { definirTrajeto(null); return }
    const pedido = indoAoDestino ? api.rotaDaCorrida : api.rotaDoMotorista
    pedido(token, corridaId).then((r) => {
      definirTrajeto(r)
      if (r.pontos.length > 1) mapaRef.current?.enquadrar(r.pontos)
    }).catch(() => definirTrajeto(null))
  }, [corridaId, estado])

  useEffect(() => { if (encerrada || estado === 'concluida') pararSimulacao() }, [estado])
  useEffect(() => () => clearInterval(cronometroRef.current), [])

  async function alternarOnline() {
    if (!posicao) {
      definirErro('Defina sua posição antes de ficar online.')
      return
    }
    definirAlternando(true)
    definirErro(null)
    try {
      await enviarPosicao(posicao.lat, posicao.lon)
      await api.definirDisponibilidade(token, !online)
      definirOnline(!online)
      vibrar(online ? 15 : [15, 60, 25])
    } catch (falha) {
      definirErro(falha.message)
    } finally {
      definirAlternando(false)
    }
  }

  /**
   * Simula o deslocamento: percorre o trajeto REAL, ponto a ponto da geometria
   * do OpenStreetMap, enviando GPS a cada passo. O passageiro vê o carro
   * andar pelas ruas via WebSocket — não é interpolação em linha reta.
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
    cronometroRef.current = setInterval(async () => {
      if (i >= amostra.length) { pararSimulacao(); vibrar([30, 50, 30]); return }
      const [lat, lon] = amostra[i]
      i += 1
      ultimaSimuladaRef.current = { lat, lon }
      definirPosicaoSimulada({ lat, lon })
      definirSimulacao({ passo: i, total: amostra.length })
      await enviarPosicao(lat, lon)
    }, INTERVALO_SIMULACAO_MS)
  }

  function pararSimulacao() {
    clearInterval(cronometroRef.current)
    cronometroRef.current = null
    definirSimulacao(null)
    // Fica onde a simulação parou, em vez de saltar de volta ao GPS.
    const ultima = ultimaSimuladaRef.current
    ultimaSimuladaRef.current = null
    if (ultima) { definirPosicaoManual(ultima); definirUsarGps(false) }
    definirPosicaoSimulada(null)
  }

  async function agir(acao) {
    definirOcupado(true)
    definirErro(null)
    try {
      definirCorrida(await api[acao](token, corridaId))
      vibrar(15)
    } catch (falha) {
      definirErro(falha.message)
    } finally {
      definirOcupado(false)
    }
  }

  function definirPosicao(lugar) {
    definirUsarGps(false)
    definirPosicaoManual({ lat: lugar.lat, lon: lugar.lon })
    definirEndereco(lugar)
    mapaRef.current?.voarPara(lugar.lat, lugar.lon, 16)
    if (online) enviarPosicao(lugar.lat, lugar.lon)
  }

  function aoClicarNoMapa(lat, lon) {
    if (corridaId || simulacao) return
    if (!dentroDaCaixa({ lat, lon }, caixa)) {
      definirErro('Esse ponto está fora da área coberta pela malha.')
      return
    }
    vibrar(10)
    definirErro(null)
    definirPosicao({ lat, lon, titulo: 'Ponto marcado no mapa', detalhe: '' })
    api.enderecoDoPonto(token, lat, lon).then(({ lugar }) => definirEndereco(lugar)).catch(() => {})
  }

  const passageiro = corrida?.origem ? { lat: corrida.origem[0], lon: corrida.origem[1] } : null
  const destino = corrida?.destino ? { lat: corrida.destino[0], lon: corrida.destino[1] } : null
  const alvo = indoAoDestino ? destino : passageiro
  const rumo = posicao && alvo ? rumoVerdadeiro(posicao.lat, posicao.lon, alvo.lat, alvo.lon) : null

  const titulo = fase === 'fila' ? (online ? 'Online' : 'Offline')
    : estado === 'em_curso' ? 'Em viagem'
    : estado === 'concluida' ? 'Aguardando pagamento'
    : fase === 'corrida' ? 'Indo buscar' : null

  return (
    <div className="tela-app">
      <Mapa
        ref={mapaRef} tema={tema} centro={malha?.centro}
        motorista={posicao}
        origem={fase !== 'fila' ? passageiro : null}
        destino={fase !== 'fila' ? destino : null}
        radar={fase === 'fila' && online ? posicao : null}
        rota={indoAoDestino && trajeto ? trajeto.pontos : VAZIO}
        rotaMotorista={!indoAoDestino && trajeto ? trajeto.pontos : VAZIO}
        semaforos={malha?.semaforos ?? VAZIO}
        mostrarMalha={mostrarMalha}
        margens={{ topo: 0, ...margens }}
        aoClicar={aoClicarNoMapa}
        aoFalharTiles={() => definirMostrarMalha(true)}
      />

      <BarraTopo
        rumo={rumo} rotuloRumo={indoAoDestino ? 'Rumo ao destino' : 'Rumo ao passageiro'}
        titulo={titulo}
        menu={(fechar) => (
          <>
            <div className="menu-cabeca">
              <span className="avatar"><Icone nome="carro" /></span>
              <div><b>Motorista</b><small>{online ? 'disponível para corridas' : 'offline'}</small></div>
            </div>
            <ItemMenu icone={tema === 'escuro' ? 'sol' : 'lua'} onClick={alternarTema}>
              Tema {tema === 'escuro' ? 'claro' : 'escuro'}
            </ItemMenu>
            <ItemMenu icone="camadas" valor={mostrarMalha} onClick={() => definirMostrarMalha(!mostrarMalha)}>
              Malha do algoritmo
            </ItemMenu>
            <ItemMenu icone="sair" perigo onClick={() => { fechar(); sair() }}>Sair</ItemMenu>
          </>
        )}
      />

      <ControlesMapa base={margens.base}>
        <BotaoRedondo rotulo="Mostrar a malha do algoritmo" ativo={mostrarMalha}
                      onClick={() => definirMostrarMalha(!mostrarMalha)}>
          <Icone nome="camadas" />
        </BotaoRedondo>
        <BotaoRedondo rotulo="Centralizar em mim"
                      onClick={() => posicao && mapaRef.current?.voarPara(posicao.lat, posicao.lon, 16)}>
          <Icone nome="mira" />
        </BotaoRedondo>
      </ControlesMapa>

      <Folha chave={fase} aoMedir={definirMargens}>
        <AnimatePresence mode="wait" initial={false}>
          <motion.div key={fase} {...transicaoConteudo}>
            {fase === 'fila' && (
              <ConteudoFila
                online={online} alternando={alternando} alternar={alternarOnline}
                posicao={posicao} endereco={endereco} erro={erro}
                gps={gps} gpsNaArea={gpsNaArea} usarGps={usarGps && gpsNaArea}
                ativarGps={() => {
                  definirUsarGps(true)
                  if (gps.posicao) mapaRef.current?.voarPara(gps.posicao.lat, gps.posicao.lon, 16)
                }}
                abrirBusca={() => definirBusca(true)}
              />
            )}
            {fase === 'corrida' && corrida && (
              <ConteudoCorridaMotorista
                corrida={corrida} estado={estado} enderecos={enderecos} trajeto={trajeto}
                simulacao={simulacao} iniciarSimulacao={iniciarSimulacao}
                pararSimulacao={pararSimulacao} agir={agir} ocupado={ocupado} erro={erro}
              />
            )}
            {fase === 'encerrada' && (
              <ConteudoEncerrada estado={estado} corrida={corrida}
                                 voltar={() => { definirCorridaId(null); definirErro(null) }} />
            )}
          </motion.div>
        </AnimatePresence>
      </Folha>

      <AnimatePresence>
        {busca && (
          <TelaBusca
            key="busca" token={token} campoInicial="posicao" campos={['posicao']}
            valores={{}} perto={posicao ?? gps.posicao}
            aoEscolher={(_campo, lugar) => { definirPosicao(lugar); definirBusca(false) }}
            aoFechar={() => definirBusca(false)}
          />
        )}
      </AnimatePresence>
    </div>
  )
}

function ConteudoFila({ online, alternando, alternar, posicao, endereco, erro, gps, gpsNaArea, usarGps, ativarGps, abrirBusca }) {
  return (
    <div className="conteudo">
      <div className="fila-cabeca">
        <div>
          <div className="saudacao">{online ? 'Você está na fila' : 'Você está offline'}</div>
          <h1 className="titulo-folha">{online ? 'Procurando passageiros' : 'Pronto para dirigir?'}</h1>
        </div>
        <motion.button className={`botao-energia ${online ? 'ligado' : ''}`}
                       onClick={() => { vibrar(10); alternar() }}
                       disabled={alternando || !posicao}
                       whileTap={{ scale: 0.9 }}
                       aria-label={online ? 'Ficar offline' : 'Ficar online'}>
          {online && <><span className="anel" /><span className="anel atraso" /></>}
          {alternando ? <span className="giro" /> : <Icone nome="energia" tamanho={30} traco={2.4} />}
        </motion.button>
      </div>

      <div className="posicao-motorista">
        <span className="lugar-icone gps"><Icone nome="carro" /></span>
        <div className="linha-partida-textos">
          <small>Sua posição {usarGps ? '· GPS' : ''}</small>
          <b>{posicao ? (endereco?.titulo ?? 'Localizando endereço…') : 'Não definida'}</b>
          {posicao && endereco?.detalhe && <span>{endereco.detalhe}</span>}
          {!posicao && <span>Toque no mapa, busque um endereço ou use o GPS</span>}
        </div>
      </div>

      <div className="chips">
        <motion.button className={`chip ${usarGps ? 'ativo' : ''}`} whileTap={{ scale: 0.94 }}
                       disabled={!gpsNaArea} onClick={() => { vibrar(8); ativarGps() }}>
          <Icone nome="mira" tamanho={16} /> GPS
        </motion.button>
        <motion.button className="chip" whileTap={{ scale: 0.94 }} onClick={() => { vibrar(8); abrirBusca() }}>
          <Icone nome="busca" tamanho={16} /> Buscar endereço
        </motion.button>
        <span className="chip-dica"><Icone nome="pino" tamanho={15} /> ou toque no mapa</span>
      </div>

      <AnimatePresence>
        {gps.posicao && !gpsNaArea && (
          <Aviso icone="mapa">
            Seu GPS está fora da área coberta (centro expandido de SP). Marque sua posição no mapa.
          </Aviso>
        )}
        {erro && <Aviso tipo="erro">{erro}</Aviso>}
      </AnimatePresence>

      <p className="texto-apoio esquerda">
        {online
          ? 'Quando um passageiro pedir por perto, o pareamento reverso mede seu tempo real até ele pelas ruas — não a distância em linha reta.'
          : 'Fique online para entrar na fila. Sua posição é enviada a cada 4 segundos.'}
      </p>
    </div>
  )
}

function ConteudoCorridaMotorista({ corrida, estado, enderecos, trajeto, simulacao, iniciarSimulacao, pararSimulacao, agir, ocupado, erro }) {
  const indoAoDestino = estado === 'em_curso'
  const nova = ['alocacao', 'rota'].includes(estado)
  return (
    <div className="conteudo">
      {nova && (
        <motion.div className="selo-nova" initial={{ scale: 0.6, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }} transition={{ type: 'spring', stiffness: 500, damping: 15 }}>
          <span className="ponto pulsando" /> Nova corrida
        </motion.div>
      )}
      <h2 className="titulo-folha">
        {indoAoDestino ? 'Levando ' : estado === 'concluida' ? 'Corrida de ' : 'Buscar '}
        {corrida.passageiro_nome?.split(' ')[0] ?? 'passageiro'}
      </h2>

      <div className="resumo-trajeto compacto">
        <div className="busca-trilho" aria-hidden="true">
          <span className="trilho-origem" /><span className="trilho-linha" /><span className="trilho-destino" />
        </div>
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
          <b><NumeroAnimado valor={corrida.custo_estimado} formatar={reais} /></b>
          <span>valor da corrida</span>
        </div>
      </div>

      <LinhaDeEstados estadoAtual={estado} />
      {erro && <Aviso tipo="erro">{erro}</Aviso>}

      <div className="acoes">
        {estado !== 'concluida' && (
          <Botao variante={simulacao ? 'secundario' : 'primario'}
                 disabled={!trajeto || trajeto.pontos.length < 2}
                 onClick={simulacao ? pararSimulacao : iniciarSimulacao}>
            <Icone nome={simulacao ? 'fechar' : 'rota'} tamanho={19} />
            {simulacao ? 'Parar simulação'
              : indoAoDestino ? 'Seguir até o destino (simular GPS)' : 'Ir até o passageiro (simular GPS)'}
          </Botao>
        )}
        {simulacao && (
          <div className="progresso-simulacao">
            <motion.span animate={{ scaleX: simulacao.passo / simulacao.total }}
                         transition={{ duration: 0.4, ease: 'linear' }} />
          </div>
        )}
        {estado === 'rota' && (
          <Botao variante="secundario" carregando={ocupado} onClick={() => agir('iniciar')}>
            Passageiro embarcou
          </Botao>
        )}
        {estado === 'em_curso' && (
          <Botao variante="secundario" carregando={ocupado} onClick={() => agir('finalizar')}>
            <Icone nome="bandeira" tamanho={18} /> Finalizar corrida
          </Botao>
        )}
        {estado === 'concluida' && (
          <p className="texto-apoio">Aguardando o pagamento do passageiro…</p>
        )}
      </div>
    </div>
  )
}

function ConteudoEncerrada({ estado, corrida, voltar }) {
  const paga = estado === 'paga'
  return (
    <div className="conteudo centralizado">
      <motion.svg className={`selo-final ${paga ? 'ok' : 'cancelado'}`} viewBox="0 0 80 80" width="84" height="84"
                  initial={{ scale: 0.5, opacity: 0 }} animate={{ scale: 1, opacity: 1 }}
                  transition={{ type: 'spring', stiffness: 300, damping: 16 }}>
        <circle cx="40" cy="40" r="36" />
        <motion.path d={paga ? 'M24 41l11 11 22-24' : 'M28 28l24 24M52 28L28 52'}
                     initial={{ pathLength: 0 }} animate={{ pathLength: 1 }}
                     transition={{ delay: 0.25, duration: 0.5 }} />
      </motion.svg>
      <h2 className="titulo-folha pequeno">{paga ? 'Corrida paga' : 'Corrida cancelada'}</h2>
      {paga && corrida && (
        <div className="valor-final"><NumeroAnimado valor={corrida.custo_estimado} formatar={reais} /></div>
      )}
      <p className="texto-apoio">{paga ? 'Você já está de volta à fila.' : 'O passageiro cancelou. Você voltou à fila.'}</p>
      <Botao onClick={voltar}>Voltar à fila</Botao>
    </div>
  )
}
