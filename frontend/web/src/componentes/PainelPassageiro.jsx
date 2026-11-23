import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../api'
import { usarCorridaAoVivo } from '../ganchos/usarCorridaAoVivo'
import { usarLocalizacao } from '../ganchos/usarLocalizacao'
import {
  dentroDaCaixa, gravarArmazenado, horarioDaqui, lerArmazenado, reais, saudacao,
  textoDistancia, textoDuracao, vibrar,
} from '../util'
import { Botao, BotaoRedondo, Esqueleto, NumeroAnimado, Reticencias } from './Basicos'
import { Bussola, rumoVerdadeiro } from './Bussola'
import { DetalhesAlgoritmo } from './DetalhesAlgoritmo'
import { Folha } from './Folha'
import { Icone } from './Icone'
import { LinhaDeEstados } from './LinhaDeEstados'
import { Mapa } from './Mapa'
import { Aviso, BarraTopo, ControlesMapa, ItemMenu, PinoCentral } from './Sobreposicoes'
import { TelaBusca, guardarRecente, lerRecentes } from './TelaBusca'

const CHAVE_CORRIDA = 'truecompass.corrida'
const FINAIS = ['paga', 'cancelada']
const VAZIO = []
const esperar = (ms) => new Promise((r) => setTimeout(r, ms))

const transicaoConteudo = {
  initial: { opacity: 0, y: 18 },
  animate: { opacity: 1, y: 0, transition: { type: 'spring', stiffness: 380, damping: 34 } },
  exit: { opacity: 0, y: -10, transition: { duration: 0.14 } },
}

export function PainelPassageiro({ sessao, malha, tema, alternarTema, sair }) {
  const token = sessao.token
  const mapaRef = useRef(null)
  const gps = usarLocalizacao()
  const caixa = malha?.caixa
  const gpsNaArea = Boolean(gps.posicao && dentroDaCaixa(gps.posicao, caixa))

  const salvo = useMemo(() => lerArmazenado(CHAVE_CORRIDA), [])
  const [origem, definirOrigem] = useState(salvo?.origem ?? null)
  const [destino, definirDestino] = useState(salvo?.destino ?? null)
  const [busca, definirBusca] = useState(null)
  const [escolha, definirEscolha] = useState(null)
  const [estimativa, definirEstimativa] = useState(null)
  const [calculando, definirCalculando] = useState(false)
  const [corrida, definirCorrida] = useState(null)
  const [procurando, definirProcurando] = useState(false)
  const [semMotorista, definirSemMotorista] = useState(false)
  const [rotaCorrida, definirRotaCorrida] = useState(VAZIO)
  const [rotaMotorista, definirRotaMotorista] = useState(null)
  const [erro, definirErro] = useState(null)
  const [ocupado, definirOcupado] = useState(false)
  const [margens, definirMargens] = useState({ base: 0, esquerda: 0 })
  const [mostrarMalha, definirMostrarMalha] = useState(false)
  const recentes = useMemo(lerRecentes, [busca, corrida?.id])

  const aoVivo = usarCorridaAoVivo(corrida?.id, token)
  const estado = aoVivo.estado?.estado ?? corrida?.estado ?? null

  const fase = escolha ? 'escolha'
    : corrida ? (FINAIS.includes(estado) ? 'fim' : 'corrida')
    : procurando ? 'procurando'
    : semMotorista ? 'sem_motorista'
    : origem && destino ? 'previa'
    : 'inicio'

  // ---- retoma a corrida em andamento se o app foi fechado/recarregado
  useEffect(() => {
    if (!salvo?.corridaId) return
    api.consultarCorrida(token, salvo.corridaId).then((c) => {
      if (FINAIS.includes(c.estado)) { gravarArmazenado(CHAVE_CORRIDA, null); return }
      definirCorrida(c)
      api.rotaDaCorrida(token, c.id).then((r) => definirRotaCorrida(r.pontos)).catch(() => {})
    }).catch(() => gravarArmazenado(CHAVE_CORRIDA, null))
  }, [])

  useEffect(() => {
    if (!corrida) return
    if (estado && FINAIS.includes(estado)) gravarArmazenado(CHAVE_CORRIDA, null)
    else gravarArmazenado(CHAVE_CORRIDA, { corridaId: corrida.id, origem, destino })
  }, [corrida?.id, estado])

  // ---- partida padrão: o GPS, se a pessoa estiver dentro da área coberta
  const gpsAplicadoRef = useRef(false)
  useEffect(() => {
    if (gpsAplicadoRef.current || !gpsNaArea) return
    gpsAplicadoRef.current = true
    if (!origem) usarGpsComo('origem')
    if (!corrida) mapaRef.current?.voarPara(gps.posicao.lat, gps.posicao.lon, 16)
  }, [gpsNaArea])

  function aplicar(campo, lugar) {
    if (campo === 'origem') definirOrigem(lugar)
    else definirDestino(lugar)
    definirSemMotorista(false)
  }

  async function usarGpsComo(campo) {
    if (!gps.posicao) return
    const { lat, lon } = gps.posicao
    const base = { id: 'gps', gps: true, titulo: 'Sua localização', detalhe: 'GPS do aparelho',
                   categoria: 'endereco', lat, lon }
    aplicar(campo, base)
    try {
      const { lugar } = await api.enderecoDoPonto(token, lat, lon)
      aplicar(campo, { ...base, detalhe: lugar.titulo })
    } catch { /* fica com o rótulo genérico */ }
  }

  // ---- prévia: o MESMO A* do pedido, rodado assim que há partida e destino
  useEffect(() => {
    if (corrida || !origem || !destino) { definirEstimativa(null); return }
    const controle = new AbortController()
    definirCalculando(true)
    definirErro(null)
    const inicio = performance.now()
    api.estimar(token, origem, destino, controle.signal)
      .then(async (resultado) => {
        // Tempo mínimo para a transição "calculando → rota" ser legível.
        const resta = 450 - (performance.now() - inicio)
        if (resta > 0) await esperar(resta)
        if (!controle.signal.aborted) definirEstimativa(resultado)
      })
      .catch((falha) => { if (falha.name !== 'AbortError') definirErro(falha.message) })
      .finally(() => { if (!controle.signal.aborted) definirCalculando(false) })
    return () => controle.abort()
  }, [origem?.lat, origem?.lon, destino?.lat, destino?.lon, corrida?.id])

  // ---- corrida ao vivo: o WebSocket empurra a mudança; o backend é a verdade
  useEffect(() => {
    if (!aoVivo.estado || !corrida) return
    vibrar([15, 50, 15])
    api.consultarCorrida(token, corrida.id).then(definirCorrida).catch(() => {})
  }, [aoVivo.estado?.estado])

  // Trajeto do motorista até você: recalculado a cada ping de GPS dele.
  const enquadradoRef = useRef(null)
  useEffect(() => {
    if (!corrida || !['alocacao', 'rota'].includes(estado)) { definirRotaMotorista(null); return }
    api.rotaDoMotorista(token, corrida.id).then((r) => {
      definirRotaMotorista(r)
      if (enquadradoRef.current !== corrida.id && r.pontos.length > 1) {
        enquadradoRef.current = corrida.id
        mapaRef.current?.enquadrar([...r.pontos, origem])
      }
    }).catch(() => definirRotaMotorista(null))
  }, [corrida?.id, estado, aoVivo.posicaoMotorista?.lat, aoVivo.posicaoMotorista?.lon])

  async function confirmar() {
    definirProcurando(true)
    definirSemMotorista(false)
    definirErro(null)
    vibrar([12, 40, 12])
    const inicio = performance.now()
    try {
      const nova = await api.pedirCorrida(token, origem, destino)
      // O pareamento é rápido; o radar fica um instante para ser percebido.
      const resta = 1500 - (performance.now() - inicio)
      if (resta > 0) await esperar(resta)
      guardarRecente(destino)
      definirRotaCorrida(estimativa?.pontos ?? VAZIO)
      definirCorrida(nova)
      vibrar([20, 60, 20])
    } catch (falha) {
      if (falha.status === 503) definirSemMotorista(true)
      else definirErro(falha.message)
    } finally {
      definirProcurando(false)
    }
  }

  async function agir(chamada) {
    definirOcupado(true)
    definirErro(null)
    try {
      definirCorrida(await chamada())
      vibrar(15)
    } catch (falha) {
      definirErro(falha.message)
    } finally {
      definirOcupado(false)
    }
  }

  function novaCorrida() {
    definirCorrida(null)
    definirDestino(null)
    definirEstimativa(null)
    definirRotaCorrida(VAZIO)
    definirRotaMotorista(null)
    definirErro(null)
    gravarArmazenado(CHAVE_CORRIDA, null)
    if (gpsNaArea) usarGpsComo('origem')
  }

  function trocar() {
    vibrar(10)
    definirOrigem(destino)
    definirDestino(origem)
  }

  // ---- escolher no mapa: o pino fica parado, o mapa se move
  const pedidoPontoRef = useRef(0)
  function iniciarEscolha(campo) {
    definirBusca(null)
    const alvo = (campo === 'origem' ? origem : destino) ?? (gpsNaArea ? gps.posicao : null)
    definirEscolha({ campo, lugar: null, carregando: true, fora: false, movendo: false })
    setTimeout(() => {
      if (alvo) mapaRef.current?.voarPara(alvo.lat, alvo.lon, 17)
      setTimeout(() => {
        const c = mapaRef.current?.centro()
        if (c) consultarPonto(c.lat, c.lon)
      }, alvo ? 1000 : 50)
    }, 60)
  }

  function consultarPonto(lat, lon) {
    const id = ++pedidoPontoRef.current
    const ponto = { lat, lon }
    if (!dentroDaCaixa(ponto, caixa)) {
      definirEscolha((e) => e && { ...e, movendo: false, carregando: false, lugar: null, fora: true })
      return
    }
    definirEscolha((e) => e && { ...e, movendo: false, carregando: true, fora: false })
    api.enderecoDoPonto(token, lat, lon)
      .then(({ lugar }) => {
        if (id === pedidoPontoRef.current) {
          definirEscolha((e) => e && { ...e, carregando: false, lugar: { ...lugar, lat, lon } })
        }
      })
      .catch(() => {
        if (id !== pedidoPontoRef.current) return
        definirEscolha((e) => e && {
          ...e, carregando: false,
          lugar: { id: `ponto:${lat.toFixed(5)},${lon.toFixed(5)}`, titulo: 'Ponto marcado no mapa',
                   detalhe: `${lat.toFixed(5)}, ${lon.toFixed(5)}`, categoria: 'endereco', lat, lon },
        })
      })
  }

  function confirmarEscolha() {
    const { campo, lugar } = escolha
    vibrar(12)
    guardarRecente(lugar)
    aplicar(campo, lugar)
    definirEscolha(null)
    if (campo === 'origem' && !destino) definirBusca({ campo: 'destino' })
  }

  function aoEscolherNaBusca(campo, lugar) {
    aplicar(campo, lugar)
    if (campo === 'origem' && !destino) return 'destino'
    if (campo === 'destino' && !origem) return 'origem'
    definirBusca(null)
    return undefined
  }

  // ---- o que o mapa mostra em cada fase
  const rotaExibida = corrida ? rotaCorrida
    : fase === 'previa' && estimativa ? estimativa.pontos : VAZIO

  const conectores = useMemo(() => {
    // Trecho a pé entre o endereço e o cruzamento onde a rota começa/termina.
    if (rotaExibida.length < 2 || !origem || !destino) return VAZIO
    return [
      [[origem.lat, origem.lon], rotaExibida[0]],
      [rotaExibida[rotaExibida.length - 1], [destino.lat, destino.lon]],
    ]
  }, [rotaExibida, origem?.lat, destino?.lat])

  const de = origem ?? (gpsNaArea ? gps.posicao : null)
  const rumo = de && destino && fase !== 'escolha'
    ? rumoVerdadeiro(de.lat, de.lon, destino.lat, destino.lon) : null

  const titulos = {
    procurando: 'Procurando motorista',
    alocacao: 'Motorista a caminho', rota: 'Motorista a caminho',
    em_curso: 'Em viagem', concluida: 'Você chegou',
  }
  const titulo = fase === 'procurando' ? titulos.procurando
    : fase === 'corrida' ? titulos[estado] : null

  const escondeOrigem = fase === 'escolha' && escolha.campo === 'origem'
  const escondeDestino = fase === 'escolha' && escolha.campo === 'destino'

  return (
    <div className="tela-app">
      <Mapa
        ref={mapaRef} tema={tema} centro={malha?.centro}
        usuario={gps.posicao}
        origem={escondeOrigem ? null : origem}
        destino={escondeDestino ? null : destino}
        motorista={fase === 'corrida' ? aoVivo.posicaoMotorista : null}
        radar={fase === 'procurando' ? origem : null}
        rota={rotaExibida}
        rotaMotorista={fase === 'corrida' && rotaMotorista ? rotaMotorista.pontos : VAZIO}
        conectores={conectores}
        semaforos={malha?.semaforos ?? VAZIO}
        mostrarMalha={mostrarMalha}
        margens={{ topo: 0, ...margens }}
        aoMoverCentro={escolha ? consultarPonto : undefined}
        aoIniciarMovimento={escolha ? () => definirEscolha((e) => e && { ...e, movendo: true }) : undefined}
        aoFalharTiles={() => definirMostrarMalha(true)}
      />

      {fase === 'escolha' && (
        <PinoCentral movendo={escolha.movendo} tipo={escolha.campo} base={margens.base} />
      )}

      <BarraTopo
        rumo={rumo} rotuloRumo="Rumo ao destino" titulo={titulo}
        menu={(fechar) => (
          <>
            <div className="menu-cabeca">
              <span className="avatar"><Icone nome="usuario" /></span>
              <div><b>Passageiro</b><small>{malha ? `${malha.nos.toLocaleString('pt-BR')} cruzamentos reais` : 'carregando malha…'}</small></div>
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
        <BotaoRedondo rotulo="Minha localização"
                      onClick={() => {
                        if (gps.posicao) mapaRef.current?.voarPara(gps.posicao.lat, gps.posicao.lon, 16)
                        else if (malha?.centro) mapaRef.current?.voarPara(malha.centro.lat, malha.centro.lon, 13)
                      }}>
          <Icone nome="mira" />
        </BotaoRedondo>
      </ControlesMapa>

      <Folha chave={fase} aoMedir={definirMargens}>
        <AnimatePresence mode="wait" initial={false}>
          <motion.div key={fase === 'corrida' ? `corrida-${estado}` : fase} {...transicaoConteudo}>
            {fase === 'inicio' && (
              <ConteudoInicio origem={origem} gps={gps} gpsNaArea={gpsNaArea} recentes={recentes}
                              malha={malha} abrirBusca={(campo) => definirBusca({ campo })}
                              aoEscolherRecente={(lugar) => aplicar('destino', lugar)} />
            )}
            {fase === 'previa' && (
              <ConteudoPrevia origem={origem} destino={destino} estimativa={estimativa}
                              calculando={calculando} erro={erro} trocar={trocar}
                              abrirBusca={(campo) => definirBusca({ campo })}
                              voltar={() => { definirDestino(null); definirErro(null) }}
                              confirmar={confirmar} />
            )}
            {fase === 'procurando' && <ConteudoProcurando />}
            {fase === 'sem_motorista' && (
              <ConteudoSemMotorista tentar={confirmar}
                                    voltar={() => definirSemMotorista(false)} />
            )}
            {fase === 'corrida' && (
              <ConteudoCorrida corrida={corrida} estado={estado} destino={destino}
                               rotaMotorista={rotaMotorista} conectado={aoVivo.conectado}
                               ocupado={ocupado} erro={erro}
                               agir={(acao) => agir(() => api[acao](token, corrida.id))} />
            )}
            {fase === 'fim' && (
              <ConteudoFim estado={estado} corrida={corrida} destino={destino} novaCorrida={novaCorrida} />
            )}
            {fase === 'escolha' && (
              <ConteudoEscolha escolha={escolha} confirmar={confirmarEscolha}
                               cancelar={() => definirEscolha(null)} />
            )}
          </motion.div>
        </AnimatePresence>
      </Folha>

      <AnimatePresence>
        {busca && (
          <TelaBusca
            key="busca" token={token} campoInicial={busca.campo}
            valores={{ origem, destino }} perto={gps.posicao}
            gpsDisponivel={gpsNaArea}
            aoEscolher={aoEscolherNaBusca}
            aoUsarLocalizacao={(campo) => {
              usarGpsComo(campo)
              const outro = campo === 'origem' ? destino : origem
              if (!outro) return campo === 'origem' ? 'destino' : 'origem'
              definirBusca(null)
              return undefined
            }}
            aoEscolherNoMapa={iniciarEscolha}
            aoFechar={() => definirBusca(null)}
          />
        )}
      </AnimatePresence>
    </div>
  )
}

// ============================================================ fases da folha

function ConteudoInicio({ origem, gps, gpsNaArea, recentes, malha, abrirBusca, aoEscolherRecente }) {
  let partida = origem?.titulo
  let detalhePartida = origem?.detalhe
  if (!origem) {
    partida = 'Escolha o ponto de partida'
    detalhePartida = gps.estado === 'aguardando' ? 'Procurando seu GPS…'
      : gps.estado === 'negado' ? 'Permissão de localização negada'
      : gps.posicao && !gpsNaArea ? 'Seu GPS está fora da área coberta'
      : 'Toque para buscar um endereço'
  }
  return (
    <div className="conteudo">
      <div className="saudacao">{saudacao()}</div>
      <h1 className="titulo-folha">Para onde vamos?</h1>
      <motion.button className="campo-busca" whileTap={{ scale: 0.98 }}
                     onClick={() => { vibrar(8); abrirBusca('destino') }}>
        <Icone nome="busca" tamanho={21} />
        <span>Buscar destino</span>
        <span className="campo-busca-atalho"><Icone nome="relogio" tamanho={15} /> Agora</span>
      </motion.button>

      <button className="linha-partida" onClick={() => abrirBusca('origem')}>
        <span className={`ponto-partida ${origem ? '' : 'vazio'}`} />
        <span className="linha-partida-textos">
          <small>Partida</small>
          <b>{partida}</b>
          {detalhePartida && <span>{detalhePartida}</span>}
        </span>
        <Icone nome="seta" tamanho={17} />
      </button>

      {gps.posicao && !gpsNaArea && !origem && (
        <Aviso icone="mapa">
          A cobertura é o centro expandido de São Paulo (ruas reais do OpenStreetMap).
          Escolha a partida pela busca ou no mapa.
        </Aviso>
      )}

      {recentes.length > 0 && (
        <motion.ul className="lista-rapida" initial="oculto" animate="visivel"
                   variants={{ visivel: { transition: { staggerChildren: 0.05, delayChildren: 0.1 } } }}>
          {recentes.slice(0, 3).map((lugar) => (
            <motion.li key={lugar.id}
                       variants={{ oculto: { opacity: 0, x: -10 }, visivel: { opacity: 1, x: 0 } }}>
              <motion.button className="lugar" whileTap={{ scale: 0.98 }}
                             onClick={() => { vibrar(8); aoEscolherRecente(lugar) }}>
                <span className="lugar-icone"><Icone nome="relogio" /></span>
                <span className="lugar-textos">
                  <span className="lugar-titulo">{lugar.titulo}</span>
                  {lugar.detalhe && <span className="lugar-detalhe">{lugar.detalhe}</span>}
                </span>
              </motion.button>
            </motion.li>
          ))}
        </motion.ul>
      )}

      {malha && (
        <div className="rodape-area">
          <Icone nome="mapa" tamanho={13} />
          {malha.nos.toLocaleString('pt-BR')} cruzamentos · {(malha.semaforos?.length ?? 0).toLocaleString('pt-BR')} semáforos reais · OpenStreetMap
        </div>
      )}
    </div>
  )
}

function ResumoTrajeto({ origem, destino, abrirBusca, trocar }) {
  return (
    <div className="resumo-trajeto">
      <div className="busca-trilho" aria-hidden="true">
        <span className="trilho-origem" /><span className="trilho-linha" /><span className="trilho-destino" />
      </div>
      <div className="resumo-linhas">
        <button onClick={() => abrirBusca('origem')}>
          <b>{origem.titulo}</b>{origem.detalhe && <span>{origem.detalhe}</span>}
        </button>
        <button onClick={() => abrirBusca('destino')}>
          <b>{destino.titulo}</b>{destino.detalhe && <span>{destino.detalhe}</span>}
        </button>
      </div>
      {trocar && (
        <motion.button className="botao-icone trocar" onClick={trocar} aria-label="Inverter partida e destino"
                       whileTap={{ rotate: 180, scale: 0.9 }}>
          <Icone nome="trocar" tamanho={20} />
        </motion.button>
      )}
    </div>
  )
}

function ConteudoPrevia({ origem, destino, estimativa, calculando, erro, trocar, abrirBusca, voltar, confirmar }) {
  const pronta = estimativa && !calculando
  const eta = estimativa?.motoristas?.eta_mais_proximo_s
  const chegada = estimativa ? horarioDaqui(estimativa.segundos + (eta ?? 0)) : null
  const longe = estimativa && Math.max(estimativa.ancoragem_m.origem, estimativa.ancoragem_m.destino) > 150

  return (
    <div className="conteudo">
      <div className="linha-cabeca">
        <motion.button className="botao-icone" onClick={voltar} whileTap={{ scale: 0.85 }} aria-label="Voltar">
          <Icone nome="voltar" tamanho={22} />
        </motion.button>
        <span className="cabeca-titulo">Escolha a viagem</span>
      </div>
      <ResumoTrajeto origem={origem} destino={destino} abrirBusca={abrirBusca} trocar={trocar} />

      {erro && <Aviso tipo="erro">{erro}</Aviso>}

      {!pronta && !erro && (
        <div className="calculando">
          <div className="calculando-texto">
            <Icone nome="rota" tamanho={18} /> Calculando a rota mais rápida pelas ruas<Reticencias />
          </div>
          <div className="barra-indeterminada"><span /></div>
          <div className="opcao-corrida esqueleto-opcao">
            <Esqueleto largura={52} altura={52} raio={14} />
            <div style={{ flex: 1 }}>
              <Esqueleto largura="45%" altura={15} />
              <Esqueleto largura="70%" altura={11} style={{ marginTop: 8 }} />
            </div>
            <Esqueleto largura={64} altura={20} />
          </div>
        </div>
      )}

      {pronta && (
        <>
          <motion.div className="opcao-corrida selecionada"
                      initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }}
                      transition={{ type: 'spring', stiffness: 380, damping: 26 }}>
            <div className="opcao-icone"><Icone nome="carro" tamanho={30} traco={1.7} /></div>
            <div className="opcao-textos">
              <b>TrueCompass</b>
              <span>Chegada às {chegada} · {textoDuracao(estimativa.segundos)}</span>
            </div>
            <div className="opcao-preco">
              <NumeroAnimado valor={estimativa.custo_estimado} formatar={reais} />
            </div>
          </motion.div>

          <motion.div className="estatisticas" initial="oculto" animate="visivel"
                      variants={{ visivel: { transition: { staggerChildren: 0.06, delayChildren: 0.12 } } }}>
            {[
              { icone: 'rota', valor: textoDistancia(estimativa.metros), rotulo: 'pelas ruas' },
              { icone: 'relogio', valor: textoDuracao(estimativa.segundos), rotulo: 'de viagem' },
              { icone: 'semaforo', valor: estimativa.semaforos_no_caminho, rotulo: 'semáforos' },
            ].map((e) => (
              <motion.div key={e.rotulo} className="estatistica"
                          variants={{ oculto: { opacity: 0, y: 8 }, visivel: { opacity: 1, y: 0 } }}>
                <Icone nome={e.icone} tamanho={17} />
                <b>{e.valor}</b>
                <span>{e.rotulo}</span>
              </motion.div>
            ))}
          </motion.div>

          <div className={`linha-motoristas ${eta != null ? 'ok' : 'nenhum'}`}>
            <span className={`ponto ${eta != null ? 'pulsando' : ''}`} />
            {eta != null
              ? <>Motorista mais próximo a <b>{textoDuracao(eta)}</b> pelas ruas</>
              : 'Nenhum motorista online por perto agora'}
          </div>

          {longe && (
            <Aviso icone="pino">
              O endereço fica a {textoDistancia(Math.max(estimativa.ancoragem_m.origem, estimativa.ancoragem_m.destino))} da
              rua mais próxima da malha (trecho tracejado).
            </Aviso>
          )}

          <DetalhesAlgoritmo estimativa={estimativa} />

          <Botao onClick={confirmar} className="botao-confirmar">
            Confirmar TrueCompass
          </Botao>
        </>
      )}
    </div>
  )
}

function ConteudoProcurando() {
  return (
    <div className="conteudo centralizado">
      <div className="procurando-bussola">
        <Bussola rumo={null} tamanho={84} />
        <span className="anel" /><span className="anel atraso" />
      </div>
      <h2 className="titulo-folha pequeno">Procurando motorista<Reticencias /></h2>
      <p className="texto-apoio">
        Uma única busca no grafo <b>reverso</b> mede o tempo real, pelas ruas, de cada
        motorista até você — e o de menor tempo é reservado.
      </p>
      <div className="barra-indeterminada"><span /></div>
    </div>
  )
}

function ConteudoSemMotorista({ tentar, voltar }) {
  return (
    <div className="conteudo centralizado">
      <motion.div className="icone-grande alerta" initial={{ scale: 0.6, rotate: -12 }}
                  animate={{ scale: 1, rotate: 0 }} transition={{ type: 'spring', stiffness: 380, damping: 14 }}>
        <Icone nome="carro" tamanho={34} />
      </motion.div>
      <h2 className="titulo-folha pequeno">Nenhum motorista disponível</h2>
      <p className="texto-apoio">
        Não há motorista online que alcance você a tempo pelas ruas. Tente de novo em instantes.
      </p>
      <Botao onClick={tentar}>Tentar novamente</Botao>
      <Botao variante="secundario" onClick={voltar}>Voltar</Botao>
    </div>
  )
}

function CartaoMotorista({ corrida }) {
  const iniciais = (corrida.motorista_nome || 'Motorista')
    .split(' ').map((p) => p[0]).slice(0, 2).join('').toUpperCase()
  return (
    <motion.div className="cartao-motorista" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.08 }}>
      <span className="avatar grande">{iniciais}</span>
      <div className="cartao-motorista-textos">
        <b>{corrida.motorista_nome || 'Seu motorista'}</b>
        <span>{corrida.motorista_modelo || 'Carro'} </span>
      </div>
      {corrida.motorista_placa && (
        <span className="placa" aria-label={`Placa ${corrida.motorista_placa}`}>
          <small>BRASIL</small>{corrida.motorista_placa}
        </span>
      )}
    </motion.div>
  )
}

function ConteudoCorrida({ corrida, estado, destino, rotaMotorista, conectado, ocupado, erro, agir }) {
  const eta = rotaMotorista?.segundos ?? corrida.eta_segundos
  const minutos = eta != null ? Math.max(1, Math.round(eta / 60)) : null
  return (
    <div className="conteudo">
      <div className="status-corrida">
        {['alocacao', 'rota'].includes(estado) && (
          <>
            <small>Motorista a caminho</small>
            <h2 className="titulo-folha">
              {minutos != null
                ? <>Chega em <NumeroAnimado valor={minutos} formatar={(v) => Math.round(v)} /> min</>
                : 'Chegando'}
            </h2>
          </>
        )}
        {estado === 'em_curso' && (
          <>
            <small>Em viagem</small>
            <h2 className="titulo-folha">{destino?.titulo ?? 'A caminho do destino'}</h2>
          </>
        )}
        {estado === 'concluida' && (
          <>
            <small>Corrida concluída</small>
            <h2 className="titulo-folha">Você chegou!</h2>
          </>
        )}
        <span className={`selo-vivo ${conectado ? 'ativo' : ''}`}>
          <span className={`ponto ${conectado ? 'pulsando' : ''}`} /> {conectado ? 'ao vivo' : 'offline'}
        </span>
      </div>

      <CartaoMotorista corrida={corrida} />
      <LinhaDeEstados estadoAtual={estado} />

      {erro && <Aviso tipo="erro">{erro}</Aviso>}

      <div className="acoes">
        {estado === 'rota' && (
          <Botao carregando={ocupado} onClick={() => agir('iniciar')}>Já embarquei</Botao>
        )}
        {estado === 'em_curso' && (
          <Botao carregando={ocupado} onClick={() => agir('finalizar')}>Cheguei ao destino</Botao>
        )}
        {estado === 'concluida' && (
          <Botao carregando={ocupado} onClick={() => agir('pagar')}>
            <Icone nome="dinheiro" tamanho={19} /> Pagar {reais(corrida.custo_estimado)}
          </Botao>
        )}
        {['alocacao', 'rota'].includes(estado) && (
          <Botao variante="perigo-suave" carregando={ocupado} onClick={() => agir('cancelar')}>
            Cancelar corrida
          </Botao>
        )}
      </div>
    </div>
  )
}

function ConteudoFim({ estado, corrida, destino, novaCorrida }) {
  const paga = estado === 'paga'
  return (
    <div className="conteudo centralizado">
      <motion.svg className={`selo-final ${paga ? 'ok' : 'cancelado'}`} viewBox="0 0 80 80" width="88" height="88"
                  initial={{ scale: 0.5, opacity: 0 }} animate={{ scale: 1, opacity: 1 }}
                  transition={{ type: 'spring', stiffness: 300, damping: 16 }}>
        <circle cx="40" cy="40" r="36" />
        <motion.path d={paga ? 'M24 41l11 11 22-24' : 'M28 28l24 24M52 28L28 52'}
                     initial={{ pathLength: 0 }} animate={{ pathLength: 1 }}
                     transition={{ delay: 0.25, duration: 0.5, ease: 'easeOut' }} />
      </motion.svg>
      <h2 className="titulo-folha pequeno">{paga ? 'Pagamento confirmado' : 'Corrida cancelada'}</h2>
      {paga && (
        <>
          <div className="valor-final"><NumeroAnimado valor={corrida.custo_estimado} formatar={reais} /></div>
          <p className="texto-apoio">Obrigado por viajar com a TrueCompass{destino ? ` até ${destino.titulo}` : ''}.</p>
        </>
      )}
      {!paga && <p className="texto-apoio">Nenhum valor foi cobrado.</p>}
      <Botao onClick={novaCorrida}>Nova corrida</Botao>
    </div>
  )
}

function ConteudoEscolha({ escolha, confirmar, cancelar }) {
  const { campo, lugar, carregando, fora } = escolha
  return (
    <div className="conteudo">
      <div className="linha-cabeca">
        <motion.button className="botao-icone" onClick={cancelar} whileTap={{ scale: 0.85 }} aria-label="Cancelar">
          <Icone nome="voltar" tamanho={22} />
        </motion.button>
        <span className="cabeca-titulo">{campo === 'origem' ? 'Ponto de partida' : 'Destino'}</span>
      </div>
      <p className="texto-apoio esquerda">Arraste o mapa para posicionar o pino.</p>
      <div className="endereco-escolhido">
        <span className={`lugar-icone ${campo === 'origem' ? 'gps' : 'destino'}`}><Icone nome="pino" /></span>
        <div>
          {carregando && <><Esqueleto largura="62%" altura={15} /><Esqueleto largura="42%" altura={11} style={{ marginTop: 8 }} /></>}
          {!carregando && fora && <><b>Fora da área coberta</b><span>Só há ruas reais carregadas no centro expandido de SP.</span></>}
          {!carregando && !fora && lugar && <><b>{lugar.titulo}</b><span>{lugar.detalhe}</span></>}
        </div>
      </div>
      <Botao onClick={confirmar} disabled={carregando || fora || !lugar}>
        Confirmar {campo === 'origem' ? 'partida' : 'destino'}
      </Botao>
    </div>
  )
}
