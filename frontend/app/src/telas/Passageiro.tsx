import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useMemo, useRef, useState } from 'react'
import { api, type AcaoCorrida } from '../api'
import { useCorridaAoVivo, useLocalizacao } from '../ganchos'
import {
  dentroDaCaixa, esperar, gravarArmazenado, horarioDaqui, lerArmazenado, paraPonto, reais,
  rumoVerdadeiro, saudacao, textoDistancia, textoDuracao, vibrar,
} from '../lib/util'
import { Mapa, type ApiMapa, type Onda } from '../mapa/Mapa'
import type {
  Corrida, EstadoCorrida, Estimativa, FormaPagamento, IdCategoria, LatLon, LocalSalvo, Lugar, Malha, OpcaoViagem, Ponto,
  Rota, Semaforo, Sessao, Tema, TipoLocal,
} from '../tipos'
import { Bussola } from '../ui/Bussola'
import { Aviso, Folha, type Margens } from '../ui/Folha'
import { Icone } from '../ui/Icone'
import { Botao, BotaoRedondo, Confete, Esqueleto, Odometro, Reticencias, TextoRevelado } from '../ui/Movimento'
import { AvaliarCorrida } from '../ui/Estrelas'
import { BarraPrazo, usePrazo } from '../ui/Prazo'
import { TelaChat } from './Chat'
import { Busca, guardarRecente, lerRecentes, type Campo } from './Busca'
import { NOME_CATEGORIA, PAGAMENTOS, TelaHistorico } from './Historico'
import { ICONE_LOCAL, TelaPerfil } from './Perfil'
import {
  BarraTopo, CabecaMenu, CartaoMotorista, ControlesMapa, DetalhesAlgoritmo, ItemMenu,
  LinhaDeEstados, PinoCentral, SeloAoVivo, SeloFinal,
} from './Comum'

const CHAVE_CORRIDA = 'truecompass.corrida'
const CHAVE_PAGAMENTO = 'truecompass.pagamento'
const FINAIS: EstadoCorrida[] = ['paga', 'cancelada']
const VAZIO: LatLon[] = []
const SEM_SEMAFOROS: Semaforo[] = []
const SEM_LUGARES: Lugar[] = []
const MAXIMO_PARADAS = 3

type Fase = 'inicio' | 'previa' | 'procurando' | 'sem_motorista' | 'corrida' | 'fim' | 'escolha'

interface Escolha { campo: 'origem' | 'destino'; lugar: Lugar | null; carregando: boolean; fora: boolean; movendo: boolean }

interface Props {
  sessao: Sessao
  malha: Malha
  tema: Tema
  alternarTema: (e: React.MouseEvent) => void
  sair: () => void
}

export function Passageiro({ sessao, malha, tema, alternarTema, sair }: Props) {
  const token = sessao.token
  const mapa = useRef<ApiMapa>(null)
  const gps = useLocalizacao()
  const caixa = malha.caixa
  const gpsNaArea = dentroDaCaixa(gps.posicao, caixa)

  const salvo = useMemo(() => lerArmazenado<{ corridaId: number; origem: Lugar; destino: Lugar; categoria?: IdCategoria; paradas?: Lugar[] }>(CHAVE_CORRIDA), [])
  const [origem, definirOrigem] = useState<Lugar | null>(salvo?.origem ?? null)
  const [destino, definirDestino] = useState<Lugar | null>(salvo?.destino ?? null)
  const [busca, definirBusca] = useState<Campo | null>(null)
  const [escolha, definirEscolha] = useState<Escolha | null>(null)
  const [estimativa, definirEstimativa] = useState<Estimativa | null>(null)
  const [calculando, definirCalculando] = useState(false)
  const [onda, definirOnda] = useState<Onda | null>(null)
  const [corrida, definirCorrida] = useState<Corrida | null>(null)
  const [procurando, definirProcurando] = useState(false)
  const [semMotorista, definirSemMotorista] = useState(false)
  const [rotaCorrida, definirRotaCorrida] = useState<LatLon[]>(VAZIO)
  const [rotaMotorista, definirRotaMotorista] = useState<Rota | null>(null)
  const [erro, definirErro] = useState<string | null>(null)
  const [ocupado, definirOcupado] = useState(false)
  const [margens, definirMargens] = useState<Margens>({ base: 0, esquerda: 0 })
  // A malha e os semáforos só aparecem quando a pessoa pede (menu): o mapa
  // fica limpo, e a única coisa em destaque é a rota. Sem tiles (offline),
  // a malha volta como fundo, mas sem os semáforos.
  const [mostrarMalha, definirMostrarMalha] = useState(false)
  const [semTiles, definirSemTiles] = useState(false)
  const [categoria, definirCategoria] = useState<IdCategoria>(salvo?.categoria ?? 'economico')
  // Preferência do aparelho: quem paga com Pix costuma pagar sempre com Pix.
  const [formaPagamento, definirFormaPagamento] = useState<FormaPagamento>(
    () => lerArmazenado<FormaPagamento>(CHAVE_PAGAMENTO) ?? 'pix')
  const [painel, definirPainel] = useState<'perfil' | 'historico' | 'chat' | null>(null)
  // Paradas no caminho, na ordem (até 3).
  const [paradas, definirParadas] = useState<Lugar[]>(salvo?.paradas ?? [])
  const [definindoParada, definirDefinindoParada] = useState(false)
  const [naoLidas, definirNaoLidas] = useState(0)
  const [avisoLink, definirAvisoLink] = useState<string | null>(null)
  const [locais, definirLocais] = useState<LocalSalvo[]>([])
  const [definindoLocal, definirDefinindoLocal] = useState<TipoLocal | null>(null)

  useEffect(() => { api.locais(token).then(definirLocais).catch(() => {}) }, [token])
  useEffect(() => { gravarArmazenado(CHAVE_PAGAMENTO, formaPagamento) }, [formaPagamento])

  function irParaLocal(local: LocalSalvo) {
    vibrar(8)
    aplicar('destino', { id: `local:${local.id}`, titulo: local.titulo, detalhe: local.detalhe || local.rotulo,
                         categoria: 'endereco', lat: local.lat, lon: local.lon })
  }
  const [confete, definirConfete] = useState<{ x: number; y: number } | null>(null)
  const recentes = useMemo(lerRecentes, [busca, corrida?.id])

  const aoVivo = useCorridaAoVivo(corrida?.id ?? null, token)

  // Mensagem nova do motorista com o chat fechado: conta como não lida.
  useEffect(() => {
    const m = aoVivo.mensagem
    if (!m || m.autor_id === sessao.usuario_id) return
    if (painel !== 'chat') { definirNaoLidas((n) => n + 1); vibrar([20, 40, 20]) }
  }, [aoVivo.mensagem?.id])

  async function compartilharViagem() {
    if (!corrida) return
    try {
      const atual = await api.compartilhar(token, corrida.id)
      definirCorrida(atual)
      const url = `${window.location.origin}${window.location.pathname}?acompanhar=${atual.token_compartilhar}`
      const texto = `Acompanhe minha viagem no TrueCompass${destino ? ` até ${destino.titulo}` : ''}`
      if (navigator.share) {
        await navigator.share({ title: 'TrueCompass', text: texto, url })
      } else {
        await navigator.clipboard.writeText(url)
        definirAvisoLink('Link copiado. Quem abrir vê o carro no mapa até você chegar.')
        setTimeout(() => definirAvisoLink(null), 4000)
      }
    } catch (f) {
      if ((f as Error).name !== 'AbortError') definirErro((f as Error).message)
    }
  }
  const estado: EstadoCorrida | null = aoVivo.estado ?? corrida?.estado ?? null

  const fase: Fase = escolha ? 'escolha'
    : corrida ? (estado && FINAIS.includes(estado) ? 'fim' : 'corrida')
    : procurando ? 'procurando'
    : semMotorista ? 'sem_motorista'
    : origem && destino ? 'previa'
    : 'inicio'

  // ---- retoma a corrida se o app foi fechado no meio
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
    else gravarArmazenado(CHAVE_CORRIDA, { corridaId: corrida.id, origem, destino, categoria, paradas })
  }, [corrida?.id, estado])

  // ---- partida padrão: o GPS, se estiver dentro da área coberta
  const gpsAplicado = useRef(false)
  useEffect(() => {
    if (gpsAplicado.current || !gpsNaArea || !gps.posicao) return
    gpsAplicado.current = true
    if (!origem) usarGpsComo('origem')
    if (!corrida) mapa.current?.voarPara(gps.posicao, 16)
  }, [gpsNaArea])

  function aplicar(campo: 'origem' | 'destino', lugar: Lugar) {
    if (campo === 'origem') definirOrigem(lugar)
    else definirDestino(lugar)
    definirSemMotorista(false)
  }

  async function usarGpsComo(campo: 'origem' | 'destino') {
    if (!gps.posicao) return
    const { lat, lon } = gps.posicao
    const base: Lugar = { id: 'gps', gps: true, titulo: 'Sua localização', detalhe: 'GPS do aparelho', categoria: 'endereco', lat, lon }
    aplicar(campo, base)
    try {
      const { lugar } = await api.enderecoDoPonto(token, lat, lon)
      aplicar(campo, { ...base, detalhe: lugar.titulo })
    } catch { /* fica o rótulo genérico */ }
  }

  // ---- prévia: o MESMO A* do pedido, com as ondas das duas buscas
  useEffect(() => {
    if (corrida || !origem || !destino) { definirEstimativa(null); definirOnda(null); return }
    const controle = new AbortController()
    definirCalculando(true)
    definirErro(null)
    const inicio = performance.now()
    api.estimar(token, origem, destino, paradas, controle.signal)
      .then(async (e) => {
        const resta = 500 - (performance.now() - inicio)
        if (resta > 0) await esperar(resta)
        if (controle.signal.aborted) return
        definirOnda(e.exploracao ? { chave: `a${performance.now()}`, a_estrela: e.exploracao.a_estrela, dijkstra: e.exploracao.dijkstra, comparar: false } : null)
        definirEstimativa(e)
        vibrar(8)
      })
      .catch((f: Error) => { if (f.name !== 'AbortError') definirErro(f.message) })
      .finally(() => { if (!controle.signal.aborted) definirCalculando(false) })
    return () => controle.abort()
  }, [origem?.lat, origem?.lon, destino?.lat, destino?.lon, corrida?.id, paradas.map((p) => p.id).join('|')])

  // A comparação acontece NO MAPA: recolhe a folha, espera o mapa
  // re-enquadrar a rota na área liberada, e só então solta as duas ondas.
  const [recolherFolha, definirRecolherFolha] = useState(0)
  function compararBuscas() {
    const exploracao = estimativa?.exploracao
    if (!exploracao) return
    definirRecolherFolha((n) => n + 1)
    setTimeout(() => definirOnda({
      chave: `c${performance.now()}`, a_estrela: exploracao.a_estrela, dijkstra: exploracao.dijkstra, comparar: true,
    }), 750)
  }

  // ---- corrida ao vivo: o WebSocket empurra; o backend é a verdade
  useEffect(() => {
    if (!aoVivo.versao || !corrida) return
    vibrar([15, 50, 15])
    api.consultarCorrida(token, corrida.id).then(definirCorrida).catch(() => {})
  }, [aoVivo.versao])

  useEffect(() => {
    if (estado === 'paga') definirConfete({ x: window.innerWidth / 2, y: window.innerHeight * 0.62 })
  }, [estado])

  // Trajeto do motorista até você: recalculado a cada ping de GPS dele.
  const enquadrado = useRef<number | null>(null)
  useEffect(() => {
    if (!corrida || !estado || !['alocacao', 'rota'].includes(estado)) { definirRotaMotorista(null); return }
    api.rotaDoMotorista(token, corrida.id).then((r) => {
      definirRotaMotorista(r)
      if (enquadrado.current !== corrida.id && r.pontos.length > 1) {
        enquadrado.current = corrida.id
        mapa.current?.enquadrar([...r.pontos, ...(origem ? [origem] : [])])
      }
    }).catch(() => definirRotaMotorista(null))
  }, [corrida?.id, estado, aoVivo.posicaoMotorista?.lat, aoVivo.posicaoMotorista?.lon])

  async function confirmar() {
    if (!origem || !destino) return
    definirProcurando(true)
    definirSemMotorista(false)
    definirErro(null)
    vibrar([12, 40, 12])
    const inicio = performance.now()
    try {
      const nova = await api.pedirCorrida(token, origem, destino, { categoria, formaPagamento, paradas })
      // O pareamento é rápido; o radar fica um instante para ser percebido.
      const resta = 1900 - (performance.now() - inicio)
      if (resta > 0) await esperar(resta)
      guardarRecente(destino)
      definirRotaCorrida(estimativa?.pontos ?? VAZIO)
      definirCorrida(nova)
      vibrar([20, 60, 20, 60, 40])
    } catch (falha) {
      const f = falha as Error & { status?: number }
      if (f.status === 503) definirSemMotorista(true)
      else definirErro(f.message)
    } finally {
      definirProcurando(false)
    }
  }

  async function agir(acao: AcaoCorrida) {
    if (!corrida) return
    definirOcupado(true)
    definirErro(null)
    try {
      definirCorrida(await api.transitar(token, corrida.id, acao))
      vibrar(15)
    } catch (falha) {
      definirErro((falha as Error).message)
    } finally {
      definirOcupado(false)
    }
  }

  function novaCorrida() {
    definirParadas([]); definirNaoLidas(0)
    definirCategoria('economico')
    definirCorrida(null); definirDestino(null); definirEstimativa(null); definirOnda(null)
    definirRotaCorrida(VAZIO); definirRotaMotorista(null); definirErro(null); definirConfete(null)
    gravarArmazenado(CHAVE_CORRIDA, null)
    if (gpsNaArea) usarGpsComo('origem')
  }

  function trocar() {
    vibrar(10)
    definirOrigem(destino)
    definirDestino(origem)
  }

  // ---- escolher no mapa: o pino fica parado, o mapa se move
  const pedidoPonto = useRef(0)
  function iniciarEscolha(campo: Campo) {
    if (campo === 'posicao') return
    definirBusca(null)
    const alvo = (campo === 'origem' ? origem : destino) ?? (gpsNaArea ? gps.posicao : null)
    definirEscolha({ campo, lugar: null, carregando: true, fora: false, movendo: false })
    setTimeout(() => {
      if (alvo) mapa.current?.voarPara(alvo, 17)
      setTimeout(() => { const c = mapa.current?.centro(); if (c) consultarPonto(c) }, alvo ? 1000 : 60)
    }, 60)
  }

  function consultarPonto(p: Ponto) {
    const id = ++pedidoPonto.current
    if (!dentroDaCaixa(p, caixa)) {
      definirEscolha((e) => e && { ...e, movendo: false, carregando: false, lugar: null, fora: true })
      return
    }
    definirEscolha((e) => e && { ...e, movendo: false, carregando: true, fora: false })
    api.enderecoDoPonto(token, p.lat, p.lon)
      .then(({ lugar }) => {
        if (id === pedidoPonto.current) definirEscolha((e) => e && { ...e, carregando: false, lugar: { ...lugar, ...p } })
      })
      .catch(() => {
        if (id !== pedidoPonto.current) return
        definirEscolha((e) => e && {
          ...e, carregando: false,
          lugar: { id: `ponto:${p.lat.toFixed(5)},${p.lon.toFixed(5)}`, titulo: 'Ponto marcado no mapa',
                   detalhe: `${p.lat.toFixed(5)}, ${p.lon.toFixed(5)}`, categoria: 'endereco', ...p },
        })
      })
  }

  function confirmarEscolha() {
    if (!escolha?.lugar) return
    vibrar(12)
    guardarRecente(escolha.lugar)
    aplicar(escolha.campo, escolha.lugar)
    const precisaDestino = escolha.campo === 'origem' && !destino
    definirEscolha(null)
    if (precisaDestino) definirBusca('destino')
  }

  function aoEscolherNaBusca(campo: Campo, lugar: Lugar): Campo | void {
    if (campo === 'posicao') return
    aplicar(campo, lugar)
    if (campo === 'origem' && !destino) return 'destino'
    if (campo === 'destino' && !origem) return 'origem'
    definirBusca(null)
  }

  // ---- o que o mapa mostra em cada fase
  const rotaExibida = corrida ? rotaCorrida : fase === 'previa' && estimativa ? estimativa.pontos : VAZIO
  const conectores = useMemo(() => {
    // Trecho a pé entre o endereço e o cruzamento onde a rota começa/termina.
    if (rotaExibida.length < 2 || !origem || !destino) return undefined
    return [[[origem.lat, origem.lon], rotaExibida[0]], [rotaExibida[rotaExibida.length - 1], [destino.lat, destino.lon]]] as LatLon[][]
  }, [rotaExibida, origem?.lat, destino?.lat])

  // A bússola: rumo ao destino; procurando motorista, gira; achado, trava
  // na direção de onde ele vem.
  const motoristaEm = rotaMotorista?.pontos[0] ? paraPonto(rotaMotorista.pontos[0]) : null
  const de = origem ?? (gpsNaArea ? gps.posicao : null)
  const rumo = fase === 'escolha' || !de ? null
    : fase === 'corrida' && motoristaEm && estado !== 'em_curso' ? rumoVerdadeiro(de, motoristaEm)
    : destino ? rumoVerdadeiro(de, destino) : null

  const titulos: Partial<Record<string, string>> = {
    procurando: 'Procurando motorista', alocacao: 'Aguardando confirmação', rota: 'Motorista a caminho',
    em_curso: 'Em viagem', concluida: 'Você chegou',
  }
  const titulo = fase === 'procurando' ? titulos.procurando! : fase === 'corrida' && estado ? titulos[estado] ?? null : null

  return (
    <div className="tela-app">
      <Mapa ref={mapa} tema={tema} centro={malha.centro}
            usuario={gps.posicao}
            origem={fase === 'escolha' && escolha?.campo === 'origem' ? null : origem}
            destino={fase === 'escolha' && escolha?.campo === 'destino' ? null : destino}
            paradas={fase === 'previa' || fase === 'corrida' ? paradas : SEM_LUGARES}
            motorista={fase === 'corrida' ? aoVivo.posicaoMotorista ?? motoristaEm : null}
            radar={fase === 'procurando' ? origem : null}
            rota={rotaExibida}
            rotaMotorista={fase === 'corrida' && rotaMotorista ? rotaMotorista.pontos : VAZIO}
            conectores={conectores}
            semaforos={mostrarMalha ? malha.semaforos : SEM_SEMAFOROS}
            onda={fase === 'previa' ? onda : null}
            cometa={(fase === 'previa' && Boolean(estimativa)) || (fase === 'corrida' && estado === 'em_curso')}
            mostrarMalha={mostrarMalha || semTiles}
            margens={margens}
            aoMoverCentro={escolha ? consultarPonto : undefined}
            aoIniciarMovimento={escolha ? () => definirEscolha((e) => e && { ...e, movendo: true }) : undefined}
            aoFalharTiles={() => definirSemTiles(true)} />

      {fase === 'escolha' && escolha && <PinoCentral movendo={escolha.movendo} tipo={escolha.campo} base={margens.base} />}

      <BarraTopo rumo={rumo} rotuloRumo={fase === 'corrida' ? 'Rumo ao motorista' : 'Rumo ao destino'}
                 titulo={titulo} buscando={fase === 'procurando'}
                 menu={(fechar) => (
                   <>
                     <CabecaMenu icone="usuario" titulo="Passageiro" detalhe={`${malha.nos.toLocaleString('pt-BR')} cruzamentos reais`} />
                     <ItemMenu icone="usuario" onClick={() => { fechar(); definirPainel('perfil') }}>Perfil e locais salvos</ItemMenu>
                     <ItemMenu icone="relogio" onClick={() => { fechar(); definirPainel('historico') }}>Suas viagens</ItemMenu>
                     <ItemMenu icone={tema === 'escuro' ? 'sol' : 'lua'} onClick={alternarTema}>Tema {tema === 'escuro' ? 'claro' : 'escuro'}</ItemMenu>
                     <ItemMenu icone="camadas" valor={mostrarMalha} onClick={() => definirMostrarMalha(!mostrarMalha)}>Malha e semáforos</ItemMenu>
                     <ItemMenu icone="sair" perigo onClick={() => { fechar(); sair() }}>Sair</ItemMenu>
                   </>
                 )} />

      <ControlesMapa base={margens.base}>
        <BotaoRedondo rotulo="Minha localização" onClick={() => {
          if (gps.posicao) mapa.current?.voarPara(gps.posicao, 16)
          else if (malha.centro) mapa.current?.voarPara(malha.centro, 13)
        }}>
          <Icone nome="mira" />
        </BotaoRedondo>
      </ControlesMapa>

      <Folha chave={fase === 'corrida' ? `corrida-${estado}` : fase} aoMedir={definirMargens} recolher={recolherFolha}
             fracaoMaxima={fase === 'previa' ? 0.68 : undefined}>
        {fase === 'inicio' && (
          <Inicio origem={origem} gps={gps} gpsNaArea={gpsNaArea} recentes={recentes} locais={locais}
                  abrirBusca={definirBusca} aoEscolherRecente={(l) => aplicar('destino', l)}
                  irParaLocal={irParaLocal} definirLocal={definirDefinindoLocal} />
        )}
        {fase === 'previa' && origem && destino && (
          <Previa origem={origem} destino={destino} estimativa={calculando ? null : estimativa} erro={erro}
                  categoria={categoria} escolherCategoria={(c) => { vibrar(8); definirCategoria(c) }}
                  formaPagamento={formaPagamento} escolherPagamento={(f) => { vibrar(6); definirFormaPagamento(f) }}
                  paradas={paradas} adicionarParada={() => definirDefinindoParada(true)}
                  removerParada={(i) => { vibrar(8); definirParadas((l) => l.filter((_, j) => j !== i)) }}
                  trocar={trocar} abrirBusca={definirBusca} voltar={() => { definirDestino(null); definirErro(null) }}
                  confirmar={confirmar} comparar={compararBuscas} />
        )}
        {fase === 'procurando' && <Procurando />}
        {fase === 'sem_motorista' && <SemMotorista tentar={confirmar} voltar={() => definirSemMotorista(false)} />}
        {fase === 'corrida' && corrida && (
          <EmCorrida corrida={corrida} estado={estado} destino={destino} rotaMotorista={rotaMotorista} categoria={categoria}
                     conectado={aoVivo.conectado} ocupado={ocupado} erro={erro} agir={agir}
                     naoLidas={naoLidas} abrirChat={() => { definirNaoLidas(0); definirPainel('chat') }}
                     compartilhar={compartilharViagem} avisoLink={avisoLink} />
        )}
        {fase === 'fim' && corrida && (
          <Fim estado={estado} corrida={corrida} destino={destino} novaCorrida={novaCorrida}
               avaliar={async (nota, comentario) => { definirCorrida(await api.avaliar(token, corrida.id, nota, comentario)); vibrar([10, 40, 10]) }} />
        )}
        {fase === 'escolha' && escolha && (
          <EscolhaNoMapa escolha={escolha} confirmar={confirmarEscolha} cancelar={() => definirEscolha(null)} />
        )}
      </Folha>

      <AnimatePresence>
        {busca && (
          <Busca key="busca" token={token} campoInicial={busca} campos={['origem', 'destino']}
                 valores={{ origem, destino }} perto={gps.posicao} gpsDisponivel={gpsNaArea}
                 aoEscolher={aoEscolherNaBusca}
                 aoUsarLocalizacao={(campo) => {
                   if (campo === 'posicao') return
                   usarGpsComo(campo)
                   const outro = campo === 'origem' ? destino : origem
                   if (!outro) return campo === 'origem' ? 'destino' : 'origem'
                   definirBusca(null)
                 }}
                 aoEscolherNoMapa={iniciarEscolha}
                 aoFechar={() => definirBusca(null)} />
        )}
        {definindoLocal && (
          <Busca key="definir-local" token={token} campoInicial="posicao" campos={['posicao']} valores={{}} perto={gps.posicao}
                 titulo={definindoLocal === 'casa' ? 'Endereço de casa' : 'Endereço do trabalho'} rotulo="Busque o endereço"
                 aoEscolher={(_c, lugar) => {
                   api.salvarLocal(token, definindoLocal, lugar)
                     .then(() => api.locais(token)).then(definirLocais).catch((f: Error) => definirErro(f.message))
                   definirDefinindoLocal(null)
                 }}
                 aoFechar={() => definirDefinindoLocal(null)} />
        )}
        {painel === 'perfil' && (
          <TelaPerfil key="perfil" token={token} perto={gps.posicao} aoFechar={() => definirPainel(null)}
                      aoMudar={(_p, lista) => definirLocais(lista)} />
        )}
        {painel === 'historico' && <TelaHistorico key="historico" token={token} tipo="passageiro" aoFechar={() => definirPainel(null)} />}
        {definindoParada && (
          <Busca key="definir-parada" token={token} campoInicial="posicao" campos={['posicao']} valores={{}} perto={origem ?? gps.posicao}
                 titulo={`Parada ${paradas.length + 1}`} rotulo="Onde você quer parar?"
                 aoEscolher={(_c, lugar) => {
                   definirParadas((l) => l.length < MAXIMO_PARADAS ? [...l, { ...lugar, id: `${lugar.id}#${l.length}` }] : l)
                   definirDefinindoParada(false)
                 }}
                 aoFechar={() => definirDefinindoParada(false)} />
        )}
        {painel === 'chat' && corrida && (
          <TelaChat key="chat" token={token} corridaId={corrida.id} euId={sessao.usuario_id} papel="passageiro"
                    outroNome={corrida.motorista_nome?.split(' ')[0] ?? 'Motorista'} novaMensagem={aoVivo.mensagem}
                    aberto aoFechar={() => definirPainel(null)} />
        )}
      </AnimatePresence>

      <Confete origem={confete} />
    </div>
  )
}

// ================================================================== fases

function Inicio({ origem, gps, gpsNaArea, recentes, locais, abrirBusca, aoEscolherRecente, irParaLocal, definirLocal }: {
  origem: Lugar | null; gps: ReturnType<typeof useLocalizacao>; gpsNaArea: boolean; recentes: Lugar[]
  locais: LocalSalvo[]; abrirBusca: (c: Campo) => void; aoEscolherRecente: (l: Lugar) => void
  irParaLocal: (l: LocalSalvo) => void; definirLocal: (t: TipoLocal) => void
}) {
  const casa = locais.find((l) => l.tipo === 'casa')
  const trabalho = locais.find((l) => l.tipo === 'trabalho')
  const favoritos = locais.filter((l) => l.tipo === 'outro')
  const detalhe = origem?.detalhe ?? (
    gps.estado === 'aguardando' ? 'Procurando seu GPS…'
      : gps.estado === 'negado' ? 'Permissão de localização negada'
      : gps.posicao && !gpsNaArea ? 'Seu GPS está fora da área coberta'
      : 'Toque para buscar um endereço')
  return (
    <div className="conteudo">
      <motion.div className="saudacao" initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }}>{saudacao()}</motion.div>
      {/* Como nos apps de corrida: a tela inicial é UMA pergunta. */}
      <motion.button layoutId="caixa-busca" className="campo-busca" whileTap={{ scale: 0.97 }}
                     transition={{ type: 'spring', stiffness: 380, damping: 34 }}
                     onClick={() => { vibrar(8); abrirBusca('destino') }}>
        <Icone nome="busca" tamanho={21} />
        <span>Para onde?</span>
        <span className="campo-busca-atalho"><Icone nome="relogio" tamanho={15} /> Agora</span>
      </motion.button>

      {/* Atalhos: Casa e Trabalho sempre aparecem (definir ou ir), depois os favoritos. */}
      <div className="atalhos-locais">
        {([['casa', casa], ['trabalho', trabalho]] as const).map(([tipo, local]) => (
          <motion.button key={tipo} className={`atalho-local ${local ? '' : 'vazio'}`} whileTap={{ scale: 0.94 }}
                         onClick={() => local ? irParaLocal(local) : definirLocal(tipo)}>
            <Icone nome={ICONE_LOCAL[tipo]} tamanho={16} />
            <span>{local ? (tipo === 'casa' ? 'Casa' : 'Trabalho') : (tipo === 'casa' ? 'Definir casa' : 'Definir trabalho')}</span>
          </motion.button>
        ))}
        {favoritos.map((local) => (
          <motion.button key={local.id} className="atalho-local" whileTap={{ scale: 0.94 }} onClick={() => irParaLocal(local)}>
            <Icone nome={ICONE_LOCAL.outro} tamanho={16} /><span>{local.rotulo}</span>
          </motion.button>
        ))}
      </div>

      {recentes.length > 0 && (
        <motion.ul className="lista-rapida" initial="o" animate="v"
                   variants={{ v: { transition: { staggerChildren: 0.06, delayChildren: 0.15 } } }}>
          {recentes.slice(0, 3).map((lugar) => (
            <motion.li key={lugar.id} variants={{ o: { opacity: 0, x: -16 }, v: { opacity: 1, x: 0 } }}>
              <motion.button className="lugar" whileTap={{ scale: 0.97 }} whileHover={{ x: 4 }}
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

      <motion.button className="linha-partida" onClick={() => abrirBusca('origem')} whileTap={{ scale: 0.98 }}
                     initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0, transition: { delay: 0.15 } }}>
        <span className={`ponto-partida ${origem ? '' : 'vazio'}`} />
        <span className="linha-textos">
          <small>Partida</small>
          <b>{origem?.titulo ?? 'Escolha o ponto de partida'}</b>
          <span>{detalhe}</span>
        </span>
        <Icone nome="seta" tamanho={17} />
      </motion.button>

      <AnimatePresence>
        {gps.posicao && !gpsNaArea && !origem && (
          <Aviso icone="mapa">
            A cobertura é a cidade de São Paulo (ruas reais do OpenStreetMap). Escolha a partida pela busca ou no mapa.
          </Aviso>
        )}
      </AnimatePresence>
    </div>
  )
}

function ResumoTrajeto({ origem, destino, abrirBusca, trocar }:
  { origem: Lugar; destino: Lugar; abrirBusca: (c: Campo) => void; trocar: () => void }) {
  return (
    <motion.div layoutId="caixa-busca" className="resumo-trajeto" transition={{ type: 'spring', stiffness: 380, damping: 34 }}>
      <div className="busca-trilho" aria-hidden="true">
        <span className="trilho-origem" /><span className="trilho-linha" /><span className="trilho-destino" />
      </div>
      <div className="resumo-linhas">
        <button onClick={() => abrirBusca('origem')}><b>{origem.titulo}</b>{origem.detalhe && <span>{origem.detalhe}</span>}</button>
        <button onClick={() => abrirBusca('destino')}><b>{destino.titulo}</b>{destino.detalhe && <span>{destino.detalhe}</span>}</button>
      </div>
      <motion.button className="botao-icone trocar" onClick={trocar} aria-label="Inverter partida e destino"
                     whileTap={{ rotate: 180, scale: 0.85 }} transition={{ type: 'spring', stiffness: 400, damping: 15 }}>
        <Icone nome="trocar" tamanho={20} />
      </motion.button>
    </motion.div>
  )
}

function Previa({ origem, destino, estimativa, erro, categoria, escolherCategoria, formaPagamento, escolherPagamento,
                  paradas, adicionarParada, removerParada, trocar, abrirBusca, voltar, confirmar, comparar }: {
  paradas: Lugar[]; adicionarParada: () => void; removerParada: (i: number) => void
  origem: Lugar; destino: Lugar; estimativa: Estimativa | null; erro: string | null
  categoria: IdCategoria; escolherCategoria: (c: IdCategoria) => void
  formaPagamento: FormaPagamento; escolherPagamento: (f: FormaPagamento) => void; trocar: () => void
  abrirBusca: (c: Campo) => void; voltar: () => void; confirmar: () => void; comparar: () => void
}) {
  const eta = estimativa?.motoristas?.eta_mais_proximo_s ?? null
  const longe = estimativa ? Math.max(estimativa.ancoragem_m.origem, estimativa.ancoragem_m.destino) : 0
  const opcoes = estimativa?.categorias ?? []
  const escolhida = opcoes.find((o) => o.id === categoria) ?? opcoes[0]

  return (
    <div className="conteudo">
      <div className="linha-cabeca">
        <motion.button className="botao-icone" onClick={voltar} whileTap={{ scale: 0.8 }} aria-label="Voltar"><Icone nome="voltar" tamanho={22} /></motion.button>
        <span className="cabeca-titulo">Escolha uma viagem</span>
      </div>
      <ResumoTrajeto origem={origem} destino={destino} abrirBusca={abrirBusca} trocar={trocar} />
      {/* Paradas entre a partida e o destino: a rota passa por elas, na ordem. */}
      <div className="paradas-trajeto">
        <AnimatePresence initial={false}>
          {paradas.map((p, i) => (
            <motion.div key={p.id} className="linha-parada" initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }}>
              <span className="numero-parada">{i + 1}</span>
              <b>{p.titulo}</b>
              <motion.button className="botao-icone" whileTap={{ scale: 0.8 }} onClick={() => removerParada(i)} aria-label={`Remover parada ${i + 1}`}>
                <Icone nome="fechar" tamanho={16} />
              </motion.button>
            </motion.div>
          ))}
        </AnimatePresence>
        {paradas.length < MAXIMO_PARADAS && (
          <button className="adicionar-parada" onClick={adicionarParada}>
            <Icone nome="mais" tamanho={16} /> {paradas.length ? 'Adicionar outra parada' : 'Adicionar parada'}
          </button>
        )}
      </div>

      <AnimatePresence>{erro && <Aviso tipo="erro">{erro}</Aviso>}</AnimatePresence>

      {!estimativa && !erro && (
        <div className="calculando">
          <div className="calculando-texto"><Icone nome="rota" tamanho={18} /> Calculando a rota mais rápida pelas ruas<Reticencias /></div>
          <div className="barra-indeterminada"><span /></div>
          {[0, 1, 2].map((i) => (
            <div key={i} className="categoria">
              <Esqueleto largura={58} altura={38} raio={10} />
              <div style={{ flex: 1 }}><Esqueleto largura="40%" altura={15} /><Esqueleto largura="65%" altura={11} style={{ marginTop: 8 }} /></div>
              <Esqueleto largura={58} altura={18} />
            </div>
          ))}
        </div>
      )}

      {estimativa && escolhida && (
        <>
          <motion.div className="lista-categorias" role="radiogroup" aria-label="Categoria da viagem"
                      initial="o" animate="v" variants={{ v: { transition: { staggerChildren: 0.07 } } }}>
            {opcoes.map((opcao) => (
              <CartaoCategoria key={opcao.id} opcao={opcao} selecionada={opcao.id === escolhida.id}
                               segundos={estimativa.segundos} eta={eta} escolher={() => escolherCategoria(opcao.id)} />
            ))}
          </motion.div>
          <div className="nota-categorias">
            <span><Icone nome="rota" tamanho={14} /> <b>{textoDistancia(estimativa.metros)}</b> pelas ruas · <b>{textoDuracao(estimativa.segundos)}</b> de viagem · <b>{estimativa.semaforos_no_caminho}</b> semáforos</span>
            <span className={eta != null ? 'ok' : 'nenhum'}>
              <span className={`ponto ${eta != null ? 'pulsando' : ''}`} />
              {eta != null ? <>Motorista mais próximo a <b>{textoDuracao(eta)}</b> pelas ruas</> : 'Nenhum motorista online por perto agora'}
            </span>
            <small>No protótipo, os mesmos motoristas atendem as três categorias.</small>
          </div>

          {longe > 150 && (
            <Aviso icone="pino">O endereço fica a {textoDistancia(longe)} da rua mais próxima da malha (trecho tracejado).</Aviso>
          )}

          <DetalhesAlgoritmo estimativa={estimativa} aoComparar={comparar} />

          {/* Fixo na base da folha: a ação nunca some abaixo da dobra. */}
          <div className="acao-fixa">
            <div className="pagamentos" role="radiogroup" aria-label="Forma de pagamento">
              {PAGAMENTOS.map((p) => (
                <button key={p.id} role="radio" aria-checked={formaPagamento === p.id}
                        className={`pagamento ${formaPagamento === p.id ? 'escolhido' : ''}`} onClick={() => escolherPagamento(p.id)}>
                  {/* Destaque em CSS, e NÃO com layoutId: um elemento de layout
                      compartilhado dentro da folha prende a saída do
                      AnimatePresence mode="wait", e a fase seguinte nunca entra. */}
                  <Icone nome={p.icone} tamanho={15} /> {p.nome}
                </button>
              ))}
            </div>
            <Botao onClick={confirmar} className="botao-confirmar">
              Confirmar {escolhida.nome} · {reais(escolhida.custo)}
            </Botao>
          </div>
        </>
      )}
    </div>
  )
}

/**
 * Um cartão por categoria: carro, lugares, chegada e preço.
 *
 * SEM a prop `layout`, de propósito: a lista remonta a cada nova estimativa
 * (parada adicionada, origem e destino trocados), e um componente `layout`
 * remontado prende a saída do AnimatePresence mode="wait" da Folha — a
 * corrida confirmada abria uma folha vazia.
 */
function CartaoCategoria({ opcao, selecionada, segundos, eta, escolher }: {
  opcao: OpcaoViagem; selecionada: boolean; segundos: number; eta: number | null; escolher: () => void
}) {
  return (
    <motion.button role="radio" aria-checked={selecionada} className={`categoria ${selecionada ? 'selecionada' : ''}`}
                   onClick={escolher} whileTap={{ scale: 0.98 }}
                   variants={{ o: { opacity: 0, y: 14 }, v: { opacity: 1, y: 0 } }}>
      <span className="categoria-carro" aria-hidden="true">
        {opcao.lugares > 4 && <span className="carro-extra"><Icone nome="carro" tamanho={34} traco={1.6} /></span>}
        <motion.span animate={{ scale: selecionada ? 1.12 : 1 }} transition={{ type: 'spring', stiffness: 400, damping: 18 }}>
          <Icone nome="carro" tamanho={38} traco={opcao.id === 'conforto' ? 2 : 1.6} />
        </motion.span>
      </span>
      <span className="categoria-textos">
        <span className="categoria-nome">
          {opcao.nome}
          <span className="categoria-lugares"><Icone nome="usuario" tamanho={13} /> {opcao.lugares}</span>
        </span>
        <span className="categoria-chegada">
          Chegada {horarioDaqui(segundos + (eta ?? 0))}{eta != null && <> · a {Math.max(1, Math.round(eta / 60))} min</>}
        </span>
        <AnimatePresence initial={false}>
          {selecionada && (
            <motion.span className="categoria-descricao" initial={{ opacity: 0, height: 0 }}
                         animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }}>
              {opcao.descricao}
            </motion.span>
          )}
        </AnimatePresence>
      </span>
      <span className="categoria-preco">{selecionada ? <Odometro texto={reais(opcao.custo)} /> : reais(opcao.custo)}</span>
    </motion.button>
  )
}

function Procurando() {
  return (
    <div className="conteudo centralizado">
      <div className="procurando-bussola">
        <span className="varredura" />
        <Bussola rumo={null} buscando tamanho={92} />
        <span className="anel" /><span className="anel atraso" /><span className="anel atraso2" />
      </div>
      <TextoRevelado className="titulo-folha pequeno" texto="Procurando motorista" />
      <p className="texto-apoio">
        Uma única busca no grafo <b>reverso</b> mede o tempo real, pelas ruas, de cada motorista até você — e o de menor tempo é reservado.
      </p>
      <div className="barra-indeterminada"><span /></div>
    </div>
  )
}

function SemMotorista({ tentar, voltar }: { tentar: () => void; voltar: () => void }) {
  return (
    <div className="conteudo centralizado">
      <motion.div className="icone-grande alerta" initial={{ scale: 0.4, rotate: -30 }} animate={{ scale: 1, rotate: [0, -10, 8, -4, 0] }}
                  transition={{ type: 'spring', stiffness: 380, damping: 12 }}>
        <Icone nome="carro" tamanho={34} />
      </motion.div>
      <TextoRevelado className="titulo-folha pequeno" texto="Nenhum motorista disponível" />
      <p className="texto-apoio">Não há motorista online que alcance você a tempo pelas ruas. Tente de novo em instantes.</p>
      <Botao onClick={tentar}><Icone nome="repetir" tamanho={18} /> Tentar novamente</Botao>
      <Botao variante="secundario" onClick={voltar}>Voltar</Botao>
    </div>
  )
}

function EmCorrida({ corrida, estado, destino, rotaMotorista, categoria, conectado, ocupado, erro, agir,
                     naoLidas, abrirChat, compartilhar, avisoLink }: {
  corrida: Corrida; estado: EstadoCorrida | null; destino: Lugar | null; rotaMotorista: Rota | null; categoria: IdCategoria
  conectado: boolean; ocupado: boolean; erro: string | null; agir: (a: AcaoCorrida) => void
  naoLidas: number; abrirChat: () => void; compartilhar: () => void; avisoLink: string | null
}) {
  const eta = rotaMotorista?.segundos ?? corrida.eta_segundos
  const minutos = eta != null ? Math.max(1, Math.round(eta / 60)) : null
  const aCaminho = estado === 'alocacao' || estado === 'rota'
  // Oferta aberta: o motorista ainda não aceitou. Ao recusar ou deixar
  // vencer, o backend oferece ao próximo e o estado chega pelo WebSocket.
  const aguardando = estado === 'alocacao' && corrida.aguardando_aceite
  const restante = usePrazo(aguardando ? corrida.oferta_segundos : null, corrida.motorista_id)
  if (aguardando) {
    return (
      <div className="conteudo">
        <div className="status-corrida">
          <small>Corrida oferecida a {corrida.motorista_nome?.split(' ')[0] ?? 'um motorista'}{minutos != null ? `, a ${minutos} min` : ''}</small>
          <h2 className="titulo-folha">Aguardando confirmação<Reticencias /></h2>
          <SeloAoVivo conectado={conectado} />
        </div>
        <BarraPrazo restante={restante} total={Math.max(20, corrida.oferta_segundos ?? 0)} />
        <p className="texto-apoio esquerda">
          O motorista mais próximo pelas ruas tem alguns segundos para aceitar. Se ele recusar, a corrida vai
          para o próximo — sem você precisar pedir de novo.
        </p>
        <AnimatePresence>{erro && <Aviso tipo="erro">{erro}</Aviso>}</AnimatePresence>
        <div className="acoes">
          <Botao variante="perigo" carregando={ocupado} onClick={() => agir('cancelar')}>Cancelar pedido</Botao>
        </div>
      </div>
    )
  }
  return (
    <div className="conteudo">
      <div className="status-corrida">
        {aCaminho && (
          <>
            <small>Encontre seu motorista no embarque</small>
            <h2 className="titulo-folha">{minutos != null ? <>Chega em <Odometro texto={String(minutos)} /> min</> : 'Chegando'}</h2>
          </>
        )}
        {estado === 'em_curso' && <><small>A caminho do destino</small><TextoRevelado className="titulo-folha" texto={destino?.titulo ?? 'Em viagem'} /></>}
        {estado === 'concluida' && <><small>Corrida concluída</small><TextoRevelado className="titulo-folha" texto="Você chegou!" /></>}
        <SeloAoVivo conectado={conectado} />
      </div>

      <CartaoMotorista corrida={corrida} categoria={NOME_CATEGORIA[categoria]} />
      {estado !== 'concluida' && (
        <div className="acoes-corrida">
          <motion.button className="acao-corrida" whileTap={{ scale: 0.95 }} onClick={abrirChat}>
            <Icone nome="chat" tamanho={17} /> Mensagem
            <AnimatePresence>
              {naoLidas > 0 && <motion.span className="contador" initial={{ scale: 0 }} animate={{ scale: 1 }} exit={{ scale: 0 }}>{naoLidas}</motion.span>}
            </AnimatePresence>
          </motion.button>
          <motion.button className="acao-corrida" whileTap={{ scale: 0.95 }} onClick={compartilhar}>
            <Icone nome="compartilhar" tamanho={17} /> Compartilhar
          </motion.button>
        </div>
      )}
      <AnimatePresence>{avisoLink && <Aviso icone="check">{avisoLink}</Aviso>}</AnimatePresence>
      <LinhaDeEstados estado={estado} />
      <AnimatePresence>{erro && <Aviso tipo="erro">{erro}</Aviso>}</AnimatePresence>

      <div className="acoes">
        {estado === 'rota' && <Botao carregando={ocupado} onClick={() => agir('iniciar')}>Já embarquei</Botao>}
        {estado === 'em_curso' && <Botao carregando={ocupado} onClick={() => agir('finalizar')}><Icone nome="bandeira" tamanho={18} /> Cheguei ao destino</Botao>}
        {estado === 'concluida' && (
          <Botao carregando={ocupado} onClick={() => agir('pagar')}><Icone nome="dinheiro" tamanho={19} /> Pagar {reais(corrida.custo_estimado)}</Botao>
        )}
        {aCaminho && <Botao variante="perigo" carregando={ocupado} onClick={() => agir('cancelar')}>Cancelar corrida</Botao>}
      </div>
    </div>
  )
}

function Fim({ estado, corrida, destino, novaCorrida, avaliar }: {
  estado: EstadoCorrida | null; corrida: Corrida; destino: Lugar | null; novaCorrida: () => void
  avaliar: (nota: number, comentario: string) => Promise<void>
}) {
  const paga = estado === 'paga'
  return (
    <div className="conteudo centralizado">
      <SeloFinal ok={paga} />
      <TextoRevelado className="titulo-folha pequeno" texto={paga ? 'Pagamento confirmado' : 'Corrida cancelada'} atraso={0.3} />
      {paga && (
        <>
          <div className="valor-final"><Odometro texto={reais(corrida.custo_estimado)} /></div>
          <p className="texto-apoio">Obrigado por viajar com a TrueCompass{destino ? ` até ${destino.titulo}` : ''}.</p>
          {corrida.motorista_nome && (
            <AvaliarCorrida quem={corrida.motorista_nome.split(' ')[0]} notaDada={corrida.minha_avaliacao} enviar={avaliar} />
          )}
        </>
      )}
      {!paga && (
        <p className="texto-apoio">
          {corrida.motivo_cancelamento === 'nenhum motorista aceitou'
            ? 'Nenhum motorista por perto aceitou a corrida a tempo. Nenhum valor foi cobrado — tente de novo em instantes.'
            : 'Nenhum valor foi cobrado.'}
        </p>
      )}
      <Botao onClick={novaCorrida}>Nova corrida</Botao>
    </div>
  )
}

function EscolhaNoMapa({ escolha, confirmar, cancelar }: { escolha: Escolha; confirmar: () => void; cancelar: () => void }) {
  const { campo, lugar, carregando, fora } = escolha
  return (
    <div className="conteudo">
      <div className="linha-cabeca">
        <motion.button className="botao-icone" onClick={cancelar} whileTap={{ scale: 0.8 }} aria-label="Cancelar"><Icone nome="voltar" tamanho={22} /></motion.button>
        <span className="cabeca-titulo">{campo === 'origem' ? 'Ponto de partida' : 'Destino'}</span>
      </div>
      <p className="texto-apoio esquerda">Arraste o mapa para posicionar o pino.</p>
      <div className="endereco-escolhido">
        <span className={`lugar-icone ${campo === 'origem' ? 'gps' : 'destino'}`}><Icone nome="pino" /></span>
        <AnimatePresence mode="wait">
          <motion.div key={carregando ? 'c' : fora ? 'f' : lugar?.id ?? 'v'}
                      initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }}>
            {carregando && <><Esqueleto largura="62%" altura={15} /><Esqueleto largura="42%" altura={11} style={{ marginTop: 8 }} /></>}
            {!carregando && fora && <><b>Fora da área coberta</b><span>Só há ruas carregadas dentro da cidade de São Paulo.</span></>}
            {!carregando && !fora && lugar && <><b>{lugar.titulo}</b><span>{lugar.detalhe}</span></>}
          </motion.div>
        </AnimatePresence>
      </div>
      <Botao onClick={confirmar} disabled={carregando || fora || !lugar}>Confirmar {campo === 'origem' ? 'partida' : 'destino'}</Botao>
    </div>
  )
}
