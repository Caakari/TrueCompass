/**
 * Onde a sessão mora e como ela se renova.
 *
 * - "Manter conectado" (há token de renovação): localStorage — sobrevive a
 *   fechar o app. Sem ele: sessionStorage — a sessão acaba com a aba.
 * - O token de acesso dura algumas horas. Antes de vencer (e se uma chamada
 *   voltar 401), trocamos o de renovação por um par novo.
 * - Cada token de renovação é trocado UMA vez: o servidor troca o token a
 *   cada uso e trata o uso repetido do antigo como roubo (derruba tudo).
 */
import { api } from '../api'
import type { Sessao } from '../tipos'

const CHAVE = 'truecompass.sessao'

function ler(armazem: Storage | undefined): Sessao | null {
  try { return JSON.parse(armazem?.getItem(CHAVE) ?? 'null') as Sessao | null } catch { return null }
}

export function lerSessao(): Sessao | null {
  return ler(globalThis.localStorage) ?? ler(globalThis.sessionStorage)
}

export function gravarSessao(sessao: Sessao | null) {
  try {
    localStorage.removeItem(CHAVE)
    sessionStorage.removeItem(CHAVE)
    if (!sessao) return
    const destino = sessao.renovacao ? localStorage : sessionStorage
    destino.setItem(CHAVE, JSON.stringify(sessao))
  } catch { /* navegador sem armazenamento: a sessão vive só na memória */ }
}

/** Instante (ms) em que o token de acesso vence, lido do próprio JWT. */
export function venceEm(token: string): number | null {
  try {
    const carga = JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')))
    return typeof carga.exp === 'number' ? carga.exp * 1000 : null
  } catch { return null }
}

// Token de renovação JÁ trocado -> a troca (promessa) que ele gerou. Não basta
// "uma renovação por vez": quando a troca termina, outro 401 da mesma leva
// pode chegar antes de o React gravar a sessão nova, e pediria a troca de
// novo com o token velho — que o servidor trata como roubo e derruba tudo.
// Com o mapa, o mesmo token velho recebe a MESMA sessão nova, sem ir ao servidor.
const trocas = new Map<string, Promise<Sessao>>()

/** Troca o token de renovação por uma sessão nova (cada token, uma vez só). */
export function renovar(sessao: Sessao): Promise<Sessao> {
  const token = sessao.renovacao
  if (!token) return Promise.reject(new Error('sem renovação'))
  let troca = trocas.get(token)
  if (!troca) {
    troca = api.renovarSessao(token)
    trocas.set(token, troca)
    if (trocas.size > 8) trocas.delete(trocas.keys().next().value as string)
  }
  return troca
}
