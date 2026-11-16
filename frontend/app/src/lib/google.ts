/**
 * Login com Google pelo Google Identity Services (GIS), carregado só quando a
 * pessoa toca no botão. Usa o fluxo de TOKEN em janela própria (popup): o
 * botão continua com o visual do app, e o backend confere o token direto no
 * Google (audiência = nosso client id) antes de abrir a sessão.
 *
 * Precisa de VITE_GOOGLE_CLIENT_ID (Google Cloud → Credenciais → ID do
 * cliente OAuth, tipo "Aplicativo da Web", com o domínio do Vercel em
 * "Origens JavaScript autorizadas").
 */
const CLIENT_ID: string | undefined = import.meta.env.VITE_GOOGLE_CLIENT_ID
const SCRIPT = 'https://accounts.google.com/gsi/client'

interface RespostaToken { access_token?: string; error?: string; error_description?: string }
interface ClienteToken { requestAccessToken: (opcoes?: { prompt?: string }) => void }
interface GoogleGis {
  accounts: { oauth2: { initTokenClient: (c: {
    client_id: string; scope: string; callback: (r: RespostaToken) => void
    error_callback?: (e: { type: string }) => void
  }) => ClienteToken } }
}

let carregando: Promise<GoogleGis> | null = null

function carregarGis(): Promise<GoogleGis> {
  const existente = (window as unknown as { google?: GoogleGis }).google
  if (existente?.accounts?.oauth2) return Promise.resolve(existente)
  carregando ??= new Promise((resolver, rejeitar) => {
    const tag = document.createElement('script')
    tag.src = SCRIPT; tag.async = true
    tag.onload = () => resolver((window as unknown as { google: GoogleGis }).google)
    tag.onerror = () => { carregando = null; rejeitar(new Error('Não foi possível falar com o Google. Verifique a conexão.')) }
    document.head.appendChild(tag)
  })
  return carregando
}

class Cancelado extends Error { name = 'Cancelado' }

/** Abre a janela do Google e devolve o token de acesso (só e-mail e perfil). */
export async function pedirCredencialGoogle(): Promise<string> {
  if (!CLIENT_ID) throw new Error('Entrar com Google ainda não foi configurado neste servidor.')
  const google = await carregarGis()
  return new Promise((resolver, rejeitar) => {
    const cliente = google.accounts.oauth2.initTokenClient({
      client_id: CLIENT_ID,
      scope: 'openid email profile',
      callback: (r) => {
        if (r.access_token) resolver(r.access_token)
        else rejeitar(new Error(r.error_description || 'O Google recusou o login.'))
      },
      error_callback: (e) => rejeitar(e.type === 'popup_closed' ? new Cancelado() : new Error('Janela do Google bloqueada ou fechada.')),
    })
    cliente.requestAccessToken({ prompt: 'select_account' })
  })
}
