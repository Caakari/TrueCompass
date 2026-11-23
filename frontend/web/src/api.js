/**
 * Cliente da API do TrueCompass.
 *
 * Em desenvolvimento, BASE fica vazio e o caminho sai como "/api/...", que o
 * proxy do Vite encaminha ao backend — sem CORS e sem URL absoluta espalhada
 * pelo código. Em produção (Vercel), VITE_API_URL aponta para o Railway.
 */

const BASE = import.meta.env.VITE_API_URL || '/api'

export class ErroApi extends Error {
  constructor(mensagem, status) {
    super(mensagem)
    this.status = status
  }
}

// Chamado quando uma requisição autenticada volta 401: token expirou e o app
// precisa voltar ao login, em vez de cada tela tratar isso por conta própria.
let aoExpirar = null
export function definirAoExpirar(funcao) { aoExpirar = funcao }

async function pedir(caminho, { metodo = 'GET', corpo, token, sinal } = {}) {
  const cabecalhos = {}
  if (corpo) cabecalhos['Content-Type'] = 'application/json'
  if (token) cabecalhos.Authorization = `Bearer ${token}`

  let resposta
  try {
    resposta = await fetch(`${BASE}${caminho}`, {
      method: metodo,
      headers: cabecalhos,
      body: corpo ? JSON.stringify(corpo) : undefined,
      signal: sinal,
    })
  } catch (falha) {
    // Busca cancelada pelo próprio app (a pessoa continuou digitando).
    if (falha.name === 'AbortError') throw falha
    // Falha de rede não tem status HTTP: o backend provavelmente não subiu.
    throw new ErroApi('Sem conexão com o servidor. Ele está rodando?', 0)
  }

  if (resposta.status === 204) return null

  const texto = await resposta.text()
  let dados = null
  try { dados = texto ? JSON.parse(texto) : null } catch { dados = { detail: texto } }

  if (!resposta.ok) {
    if (resposta.status === 401 && token) aoExpirar?.()
    throw new ErroApi(mensagemDeErro(dados, resposta.status), resposta.status)
  }
  return dados
}

function mensagemDeErro(dados, status) {
  if (!dados) return `Erro ${status}`
  // 422 do FastAPI vem como lista de erros de validação.
  if (Array.isArray(dados.detail)) {
    return dados.detail.map((e) => `${e.loc?.slice(-1)[0] ?? ''}: ${e.msg}`).join('; ')
  }
  return dados.detail || `Erro ${status}`
}

export const api = {
  // ---- autenticação
  registrar: (dados) => pedir('/auth/registro', { metodo: 'POST', corpo: dados }),
  entrar: (email, senha) =>
    pedir('/auth/login', { metodo: 'POST', corpo: { email, senha } }),

  // ---- malha viária (público: geometria derivada de dado aberto)
  infoDaMalha: () => pedir('/malha/info'),
  semaforos: () => pedir('/malha/semaforos'),
  trechos: (caixa, limite = 6000, sinal) => {
    const q = new URLSearchParams({ ...caixa, limite })
    return pedir(`/malha/trechos?${q}`, { sinal })
  },

  // ---- lugares reais (Photon / Nominatim, via backend)
  buscarLugares: (token, texto, { perto, completo = false, sinal } = {}) => {
    const q = new URLSearchParams({ q: texto, completo })
    if (perto) { q.set('lat', perto.lat); q.set('lon', perto.lon) }
    return pedir(`/lugares/buscar?${q}`, { token, sinal })
  },
  enderecoDoPonto: (token, lat, lon, sinal) =>
    pedir(`/lugares/reverso?${new URLSearchParams({ lat, lon })}`, { token, sinal }),

  // ---- prévia da viagem: A* real entre os dois endereços
  estimar: (token, origem, destino, sinal) =>
    pedir('/viagens/estimativa', {
      metodo: 'POST', token, sinal,
      corpo: {
        origem_lat: origem.lat, origem_lon: origem.lon,
        destino_lat: destino.lat, destino_lon: destino.lon,
        comparar: true,
      },
    }),

  // ---- motorista
  enviarPosicao: (token, lat, lon) =>
    pedir('/motoristas/posicao', { metodo: 'POST', corpo: { lat, lon }, token }),
  definirDisponibilidade: (token, disponivel) =>
    pedir('/motoristas/disponibilidade', { metodo: 'POST', corpo: { disponivel }, token }),

  // ---- corrida
  pedirCorrida: (token, origem, destino) =>
    pedir('/corridas', {
      metodo: 'POST', token,
      corpo: {
        origem_lat: origem.lat, origem_lon: origem.lon,
        destino_lat: destino.lat, destino_lon: destino.lon,
      },
    }),
  consultarCorrida: (token, id) => pedir(`/corridas/${id}`, { token }),
  rotaDaCorrida: (token, id) => pedir(`/corridas/${id}/rota`, { token }),
  rotaDoMotorista: (token, id) => pedir(`/corridas/${id}/rota-motorista`, { token }),
  iniciar: (token, id) => pedir(`/corridas/${id}/iniciar`, { metodo: 'POST', token }),
  finalizar: (token, id) => pedir(`/corridas/${id}/finalizar`, { metodo: 'POST', token }),
  pagar: (token, id) => pedir(`/corridas/${id}/pagamento`, { metodo: 'POST', token }),
  cancelar: (token, id) => pedir(`/corridas/${id}/cancelar`, { metodo: 'POST', token }),

  saude: () => pedir('/saude'),
}

/**
 * URL do WebSocket. O token vai na query string porque a API de WebSocket do
 * navegador não permite cabeçalhos personalizados no handshake.
 */
export function urlDoWebSocket(corridaId, token) {
  const caminho = `${BASE}/ws/corridas/${corridaId}?token=${encodeURIComponent(token)}`
  if (caminho.startsWith('http')) return caminho.replace(/^http/, 'ws')
  const protocolo = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocolo}//${window.location.host}${caminho}`
}
