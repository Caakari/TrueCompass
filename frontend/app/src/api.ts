/**
 * Cliente tipado da API do TrueCompass.
 *
 * Em desenvolvimento BASE é "/api" e o proxy do Vite encaminha ao backend —
 * sem CORS e sem URL absoluta espalhada. Em produção (Vercel) VITE_API_URL
 * aponta para o backend no Railway.
 */
import type {
  Caixa, Corrida, EdicaoPerfil, Estimativa, FormaPagamento, IdCategoria, InfoMalha, ItemHistorico, Lugar,
  Acompanhamento, LocalSalvo, Mensagem, Perfil, Ponto, RespostaPosicao, ResumoMotorista, Rota, TipoLocal,
  Semaforo, Sessao, TipoUsuario, Trecho,
} from './tipos'

const BASE: string = import.meta.env.VITE_API_URL || '/api'

export class ErroApi extends Error {
  constructor(mensagem: string, readonly status: number) {
    super(mensagem)
  }
}

// Token expirado em qualquer chamada autenticada: o App volta ao login, em
// vez de cada tela tratar o 401 por conta própria.
let aoExpirar: (() => void) | null = null
export function definirAoExpirar(funcao: () => void) { aoExpirar = funcao }

interface Opcoes {
  metodo?: 'GET' | 'POST' | 'PATCH' | 'DELETE'
  corpo?: unknown
  token?: string
  sinal?: AbortSignal
}

async function pedir<T>(caminho: string, { metodo = 'GET', corpo, token, sinal }: Opcoes = {}): Promise<T> {
  const cabecalhos: Record<string, string> = {}
  if (corpo !== undefined) cabecalhos['Content-Type'] = 'application/json'
  if (token) cabecalhos.Authorization = `Bearer ${token}`

  let resposta: Response
  try {
    resposta = await fetch(`${BASE}${caminho}`, {
      method: metodo, headers: cabecalhos, signal: sinal,
      body: corpo !== undefined ? JSON.stringify(corpo) : undefined,
    })
  } catch (falha) {
    // Busca cancelada pelo próprio app (a pessoa continuou digitando).
    if ((falha as Error).name === 'AbortError') throw falha
    throw new ErroApi('Sem conexão com o servidor. Ele está rodando?', 0)
  }

  const texto = await resposta.text()
  let dados: unknown = null
  try { dados = texto ? JSON.parse(texto) : null } catch { dados = { detail: texto } }

  if (!resposta.ok) {
    if (resposta.status === 401 && token) aoExpirar?.()
    throw new ErroApi(mensagemDeErro(dados, resposta.status), resposta.status)
  }
  return dados as T
}

function mensagemDeErro(dados: unknown, status: number): string {
  const detalhe = (dados as { detail?: unknown } | null)?.detail
  // 422 do FastAPI chega como lista de erros de validação.
  if (Array.isArray(detalhe)) {
    return detalhe.map((e: { loc?: string[]; msg: string }) =>
      `${e.loc?.slice(-1)[0] ?? ''}: ${e.msg}`).join('; ')
  }
  return typeof detalhe === 'string' ? detalhe : `Erro ${status}`
}

export interface DadosRegistro {
  nome: string
  email: string
  senha: string
  tipo: TipoUsuario
  placa?: string
  modelo?: string
}

/** "Título, detalhe" do endereço, como o passageiro o viu — vai para o histórico. */
const textoDoLugar = (l: Lugar) =>
  (l.gps && l.detalhe ? l.detalhe : [l.titulo, l.detalhe].filter(Boolean).join(', ')).slice(0, 200)

const corpoViagem = (origem: Ponto, destino: Ponto) => ({
  origem_lat: origem.lat, origem_lon: origem.lon,
  destino_lat: destino.lat, destino_lon: destino.lon,
})

export const api = {
  // ---- autenticação
  registrar: (dados: DadosRegistro) =>
    pedir<Sessao>('/auth/registro', { metodo: 'POST', corpo: dados }),
  entrar: (email: string, senha: string) =>
    pedir<Sessao>('/auth/login', { metodo: 'POST', corpo: { email, senha } }),

  // ---- malha (pública: geometria de dado aberto)
  infoDaMalha: () => pedir<InfoMalha>('/malha/info'),
  semaforos: () => pedir<{ semaforos: Semaforo[]; total: number }>('/malha/semaforos'),
  trechos: (caixa: Caixa, limite = 6000, sinal?: AbortSignal) => {
    const q = new URLSearchParams({
      sul: String(caixa.sul), oeste: String(caixa.oeste),
      norte: String(caixa.norte), leste: String(caixa.leste), limite: String(limite),
    })
    return pedir<{ trechos: Trecho[]; total: number; truncado: boolean }>(`/malha/trechos?${q}`, { sinal })
  },

  // ---- lugares reais (Photon/Nominatim, pelo backend)
  buscarLugares: (token: string, texto: string,
                  { perto, completo = false, sinal }: { perto?: Ponto | null; completo?: boolean; sinal?: AbortSignal } = {}) => {
    const q = new URLSearchParams({ q: texto, completo: String(completo) })
    if (perto) { q.set('lat', String(perto.lat)); q.set('lon', String(perto.lon)) }
    return pedir<{ lugares: Lugar[]; area: Caixa | null }>(`/lugares/buscar?${q}`, { token, sinal })
  },
  enderecoDoPonto: (token: string, lat: number, lon: number, sinal?: AbortSignal) =>
    pedir<{ lugar: Lugar; dentro_da_area: boolean }>(
      `/lugares/reverso?${new URLSearchParams({ lat: String(lat), lon: String(lon) })}`, { token, sinal }),

  // ---- prévia: o mesmo A* do pedido, com a frente de onda das buscas
  estimar: (token: string, origem: Ponto, destino: Ponto, paradas: Ponto[] = [], sinal?: AbortSignal) =>
    pedir<Estimativa>('/viagens/estimativa', {
      metodo: 'POST', token, sinal,
      corpo: { ...corpoViagem(origem, destino), comparar: true, explorar: true,
               paradas: paradas.map((p) => ({ lat: p.lat, lon: p.lon })) },
    }),

  // ---- motorista
  enviarPosicao: (token: string, lat: number, lon: number) =>
    pedir<RespostaPosicao>('/motoristas/posicao', { metodo: 'POST', corpo: { lat, lon }, token }),
  resumoDoMotorista: (token: string) => pedir<ResumoMotorista>('/motoristas/resumo', { token }),
  definirDisponibilidade: (token: string, disponivel: boolean) =>
    pedir<{ disponivel: boolean; motoristas_online: number }>(
      '/motoristas/disponibilidade', { metodo: 'POST', corpo: { disponivel }, token }),

  // ---- corrida
  pedirCorrida: (token: string, origem: Lugar, destino: Lugar,
                 { categoria = 'economico', formaPagamento = 'pix', paradas = [] }:
                 { categoria?: IdCategoria; formaPagamento?: FormaPagamento; paradas?: Lugar[] } = {}) =>
    pedir<Corrida>('/corridas', {
      metodo: 'POST', token,
      corpo: {
        ...corpoViagem(origem, destino), categoria, forma_pagamento: formaPagamento,
        origem_texto: textoDoLugar(origem), destino_texto: textoDoLugar(destino),
        paradas: paradas.map((p) => ({ lat: p.lat, lon: p.lon, texto: textoDoLugar(p) })),
      },
    }),
  // Oferta: o motorista tem alguns segundos para aceitar; recusar passa ao próximo.
  aceitarOferta: (token: string, id: number) => pedir<Corrida>(`/corridas/${id}/aceitar`, { metodo: 'POST', token }),
  recusarOferta: (token: string, id: number) => pedir<null>(`/corridas/${id}/recusar`, { metodo: 'POST', token }),
  mensagens: (token: string, id: number) => pedir<Mensagem[]>(`/corridas/${id}/mensagens`, { token }),
  enviarMensagem: (token: string, id: number, texto: string) =>
    pedir<Mensagem>(`/corridas/${id}/mensagens`, { metodo: 'POST', token, corpo: { texto } }),
  compartilhar: (token: string, id: number) => pedir<Corrida>(`/corridas/${id}/compartilhar`, { metodo: 'POST', token }),
  // Público: sem token. É o link que o passageiro manda para a família.
  acompanhar: (codigo: string) => pedir<Acompanhamento>(`/publico/acompanhar/${encodeURIComponent(codigo)}`),
  historico: (token: string, antesDe?: number) =>
    pedir<ItemHistorico[]>(`/corridas?limite=20${antesDe ? `&antes_de=${antesDe}` : ''}`, { token }),
  avaliar: (token: string, id: number, nota: number, comentario?: string) =>
    pedir<Corrida>(`/corridas/${id}/avaliacao`, { metodo: 'POST', token, corpo: { nota, comentario } }),

  // ---- perfil e locais salvos
  perfil: (token: string) => pedir<Perfil>('/usuarios/eu', { token }),
  editarPerfil: (token: string, dados: EdicaoPerfil) =>
    pedir<Perfil>('/usuarios/eu', { metodo: 'PATCH', token, corpo: dados }),
  locais: (token: string) => pedir<LocalSalvo[]>('/usuarios/eu/locais', { token }),
  salvarLocal: (token: string, tipo: TipoLocal, lugar: Lugar, rotulo?: string) =>
    pedir<LocalSalvo>('/usuarios/eu/locais', {
      metodo: 'POST', token,
      corpo: { tipo, rotulo, titulo: lugar.titulo.slice(0, 160), detalhe: (lugar.detalhe ?? '').slice(0, 200), lat: lugar.lat, lon: lugar.lon },
    }),
  apagarLocal: (token: string, id: number) => pedir<null>(`/usuarios/eu/locais/${id}`, { metodo: 'DELETE', token }),
  consultarCorrida: (token: string, id: number) => pedir<Corrida>(`/corridas/${id}`, { token }),
  rotaDaCorrida: (token: string, id: number) => pedir<Rota>(`/corridas/${id}/rota`, { token }),
  rotaDoMotorista: (token: string, id: number) => pedir<Rota>(`/corridas/${id}/rota-motorista`, { token }),
  transitar: (token: string, id: number, acao: AcaoCorrida) =>
    pedir<Corrida>(`/corridas/${id}/${ROTA_DA_ACAO[acao]}`, { metodo: 'POST', token }),
}

export type AcaoCorrida = 'iniciar' | 'finalizar' | 'pagar' | 'cancelar'
const ROTA_DA_ACAO: Record<AcaoCorrida, string> = {
  iniciar: 'iniciar', finalizar: 'finalizar', pagar: 'pagamento', cancelar: 'cancelar',
}

/**
 * URL do WebSocket. O token vai na query string porque a API de WebSocket do
 * navegador não permite cabeçalho personalizado no handshake.
 */
export function urlDoWebSocket(corridaId: number, token: string): string {
  const caminho = `${BASE}/ws/corridas/${corridaId}?token=${encodeURIComponent(token)}`
  if (caminho.startsWith('http')) return caminho.replace(/^http/, 'ws')
  const protocolo = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocolo}//${window.location.host}${caminho}`
}
