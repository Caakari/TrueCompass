import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useMemo, useRef, useState, type ClipboardEvent, type FormEvent, type KeyboardEvent, type ReactNode } from 'react'
import { api, ErroApi } from '../api'
import { vibrar } from '../lib/util'
import type { Ponto, Sessao, TipoUsuario } from '../tipos'
import { Bussola } from '../ui/Bussola'
import { Aviso } from '../ui/Folha'
import { Icone } from '../ui/Icone'
import { Botao } from '../ui/Movimento'
import { FundoCidade } from './FundoCidade'

// ================================================================= campos

function Campo({ id, rotulo, acessorio, ...props }:
  { id: string; rotulo: string; acessorio?: ReactNode } & React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <motion.div className={`campo ${acessorio ? 'com-acessorio' : ''}`} layout="position"
                initial={{ opacity: 0, height: 0, y: -8 }} animate={{ opacity: 1, height: 'auto', y: 0 }}
                exit={{ opacity: 0, height: 0, y: -8 }} transition={{ type: 'spring', stiffness: 380, damping: 32 }}>
      <input id={id} placeholder=" " {...props} />
      <label htmlFor={id}>{rotulo}</label>
      <span className="campo-linha" />
      {acessorio}
    </motion.div>
  )
}

/** Senha com o olho para mostrar/ocultar (no celular, digitar às cegas erra muito). */
function CampoSenha({ id, rotulo, valor, definir, nova }:
  { id: string; rotulo: string; valor: string; definir: (v: string) => void; nova: boolean }) {
  const [visivel, definirVisivel] = useState(false)
  return (
    <Campo id={id} rotulo={rotulo} type={visivel ? 'text' : 'password'} value={valor} required minLength={8}
           autoComplete={nova ? 'new-password' : 'current-password'} onChange={(e) => definir(e.target.value)}
           acessorio={
             <button type="button" className="campo-olho" aria-label={visivel ? 'Ocultar senha' : 'Mostrar senha'}
                     onClick={() => { vibrar(6); definirVisivel(!visivel) }}>
               <Icone nome={visivel ? 'olhoFechado' : 'olho'} tamanho={20} />
             </button>
           } />
  )
}

// ======================================================== força da senha

// As mais usadas no Brasil (listas públicas de vazamentos). O servidor
// confere a MESMA regra; aqui é só para avisar antes de enviar.
const SENHAS_COMUNS = new Set([
  '12345678', '123456789', '1234567890', 'senha123', 'senha1234', 'password', 'password1', 'qwerty123',
  'abc12345', 'abcd1234', '11111111', '00000000', '87654321', 'brasil123', 'iloveyou', 'admin123',
  'mudar123', 'trocar123', 'flamengo', 'corinthians', 'palmeiras', 'saopaulo', 'santos123', 'gabriel1',
])

export function avaliarSenha(senha: string, email = '') {
  const minuscula = senha.toLowerCase()
  const usuario = email.split('@')[0]?.toLowerCase() ?? ''
  const comum = SENHAS_COMUNS.has(minuscula) || /^(.)\1+$/.test(senha)
    || (usuario.length >= 4 && minuscula.includes(usuario))
  const regras = [
    { ok: senha.length >= 8, texto: 'Pelo menos 8 caracteres' },
    { ok: /[a-zA-Z]/.test(senha) && /\d/.test(senha), texto: 'Letras e números' },
    { ok: senha.length > 0 && !comum, texto: 'Não é óbvia (nem o seu e-mail)' },
  ]
  let pontos = 0
  if (senha.length >= 8) pontos++
  if (senha.length >= 12) pontos++
  if (/[a-z]/.test(senha) && /[A-Z]/.test(senha)) pontos++
  if (/[a-zA-Z]/.test(senha) && /\d/.test(senha)) pontos++
  if (/[^a-zA-Z0-9]/.test(senha)) pontos++
  const forca = comum || senha.length < 8 ? Math.min(pontos, 1) : Math.min(pontos, 4)
  return { regras, forca, valida: regras.every((r) => r.ok) }
}

const NIVEIS = ['Muito fraca', 'Fraca', 'Razoável', 'Boa', 'Forte']

function MedidorSenha({ senha, email }: { senha: string; email: string }) {
  const { regras, forca } = useMemo(() => avaliarSenha(senha, email), [senha, email])
  if (!senha) return null
  return (
    <motion.div className="medidor" initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}>
      <div className="medidor-topo">
        <div className={`medidor-barras nivel-${forca}`} aria-hidden="true">
          {[1, 2, 3, 4].map((n) => <span key={n} className={n <= forca ? 'cheia' : ''} />)}
        </div>
        <span className={`medidor-rotulo nivel-${forca}`}>{NIVEIS[forca]}</span>
      </div>
      <ul className="medidor-regras">
        {regras.map((r) => (
          <li key={r.texto} className={r.ok ? 'ok' : ''}>
            <span className="medidor-marca"><Icone nome={r.ok ? 'check' : 'fechar'} tamanho={11} traco={3.2} /></span>
            {r.texto}
          </li>
        ))}
      </ul>
    </motion.div>
  )
}

// ==================================================== código de 6 dígitos

const DIGITOS = 6

/** Seis caixas: avança sozinho, volta no apagar, aceita colar o código inteiro. */
function CodigoVerificacao({ valor, definir, erro }: { valor: string; definir: (v: string) => void; erro: boolean }) {
  const caixas = useRef<(HTMLInputElement | null)[]>([])
  useEffect(() => { setTimeout(() => caixas.current[0]?.focus(), 350) }, [])

  function digitar(i: number, texto: string) {
    const so = texto.replace(/\D/g, '')
    if (!so) return
    const novo = (valor.slice(0, i) + so + valor.slice(i + so.length)).slice(0, DIGITOS)
    definir(novo)
    caixas.current[Math.min(i + so.length, DIGITOS - 1)]?.focus()
  }
  function tecla(i: number, e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Backspace') {
      e.preventDefault()
      if (valor[i]) definir(valor.slice(0, i) + valor.slice(i + 1))
      else if (i > 0) { definir(valor.slice(0, i - 1) + valor.slice(i)); caixas.current[i - 1]?.focus() }
    } else if (e.key === 'ArrowLeft' && i > 0) caixas.current[i - 1]?.focus()
    else if (e.key === 'ArrowRight' && i < DIGITOS - 1) caixas.current[i + 1]?.focus()
  }
  function colar(e: ClipboardEvent<HTMLInputElement>) {
    e.preventDefault()
    digitar(0, e.clipboardData.getData('text').slice(0, DIGITOS))
  }
  return (
    <motion.div className={`codigo ${erro ? 'erro' : ''}`} animate={erro ? { x: [0, -10, 9, -6, 4, 0] } : {}}
                transition={{ duration: 0.45 }}>
      {Array.from({ length: DIGITOS }, (_, i) => (
        <motion.input key={i} ref={(el) => { caixas.current[i] = el }} value={valor[i] ?? ''}
                      inputMode="numeric" autoComplete={i === 0 ? 'one-time-code' : 'off'} maxLength={DIGITOS}
                      aria-label={`Dígito ${i + 1}`} className={valor[i] ? 'cheia' : ''}
                      initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: 0.05 * i, type: 'spring', stiffness: 420, damping: 26 }}
                      onChange={(e) => digitar(i, e.target.value)} onKeyDown={(e) => tecla(i, e)} onPaste={colar}
                      onFocus={(e) => e.target.select()} />
      ))}
    </motion.div>
  )
}

/** "a***@gmail.com": confirma o destino do código sem expor o endereço inteiro. */
function emailMascarado(email: string) {
  const [nome, dominio] = email.split('@')
  if (!dominio) return email
  return `${nome.slice(0, 1)}${'•'.repeat(Math.max(2, Math.min(nome.length - 1, 6)))}@${dominio}`
}

// ===================================================== botão do Google

function LogoGoogle() {
  return (
    <svg width="20" height="20" viewBox="0 0 48 48" aria-hidden="true">
      <path fill="#FFC107" d="M43.6 20.1H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.6-.4-3.9z" />
      <path fill="#FF3D00" d="m6.3 14.7 6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z" />
      <path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-7.9l-6.5 5C9.5 39.6 16.2 44 24 44z" />
      <path fill="#1976D2" d="M43.6 20.1H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.6-.4-3.9z" />
    </svg>
  )
}

function BotaoGoogle({ texto, onClick, carregando }: { texto: string; onClick: () => void; carregando: boolean }) {
  return (
    <motion.button type="button" className="botao-google" onClick={onClick} disabled={carregando}
                   whileTap={{ scale: 0.97 }} whileHover={{ y: -1 }}>
      {carregando ? <span className="giro pequeno" /> : <LogoGoogle />}
      <span>{texto}</span>
    </motion.button>
  )
}

// ========================================================== tela inteira

type Etapa = 'entrar' | 'registrar' | 'confirmar' | 'recuperar' | 'redefinir'

const MARCA = [...'TrueCompass']
const REENVIO_S = 60

function relogio(segundos: number) {
  return `${Math.floor(segundos / 60)}:${String(segundos % 60).padStart(2, '0')}`
}

/** Contagem regressiva em segundos; `iniciar(n)` recomeça. */
function useContagem() {
  const [resta, definirResta] = useState(0)
  useEffect(() => {
    if (resta <= 0) return
    const id = setTimeout(() => definirResta((r) => r - 1), 1000)
    return () => clearTimeout(id)
  }, [resta])
  return [resta, definirResta] as const
}

export function Entrada({ centro, falhaBackend, aoEntrar }:
  { centro: Ponto | null; falhaBackend: string | null; aoEntrar: (s: Sessao, de: { x: number; y: number }) => void }) {
  const [etapa, definirEtapa] = useState<Etapa>('entrar')
  const [tipo, definirTipo] = useState<TipoUsuario>('passageiro')
  const [nome, definirNome] = useState('')
  const [email, definirEmail] = useState('')
  const [senha, definirSenha] = useState('')
  const [placa, definirPlaca] = useState('')
  const [modelo, definirModelo] = useState('')
  const [codigo, definirCodigo] = useState('')
  const [manter, definirManter] = useState(true)
  const [erro, definirErro] = useState<string | null>(null)
  const [aviso, definirAviso] = useState<string | null>(null)
  const [enviando, definirEnviando] = useState(false)
  const [comGoogle, definirComGoogle] = useState(false)
  const [contagemBloqueio, definirBloqueio] = useContagem()
  // O bloqueio vale para a etapa que o causou: o login bloqueado não pode
  // travar o "Esqueci minha senha", que é justamente a saída.
  const [etapaBloqueada, definirEtapaBloqueada] = useState<Etapa | null>(null)
  const [reenvio, definirReenvio] = useContagem()
  const botaoRef = useRef<HTMLDivElement>(null)
  // A agulha gira procurando e "acha o norte" quando a tela abre.
  const [rumo, definirRumo] = useState<number | null>(null)
  useEffect(() => {
    const ids = [setTimeout(() => definirRumo(220), 500), setTimeout(() => definirRumo(0), 1300)]
    return () => ids.forEach(clearTimeout)
  }, [])

  const registrando = etapa === 'registrar'
  const bloqueio = etapa === etapaBloqueada ? contagemBloqueio : 0
  const principal = etapa === 'entrar' || etapa === 'registrar'
  // Marca grande só no "Entrar"; nas outras etapas o formulário é longo e a
  // bússola encolhe para ele caber sem rolar.
  const heroiCheio = etapa === 'entrar'
  const forcaOk = avaliarSenha(senha, email).valida

  function irPara(nova: Etapa) {
    vibrar(6); definirErro(null); definirAviso(null); definirCodigo('')
    definirEtapa(nova)
  }

  function entrou(sessao: Sessao) {
    vibrar([15, 40, 15])
    const caixa = botaoRef.current?.getBoundingClientRect()
    aoEntrar(sessao, caixa ? { x: caixa.left + caixa.width / 2, y: caixa.top + caixa.height / 2 }
                           : { x: window.innerWidth / 2, y: window.innerHeight / 2 })
  }

  function falhou(falha: unknown) {
    vibrar([40, 30, 40])
    const e = falha as ErroApi
    if (e.status === 429 && e.esperarSegundos) {
      definirBloqueio(e.esperarSegundos)
      definirEtapaBloqueada(etapa)
      definirErro(null)
      return
    }
    definirErro(e.message)
  }

  async function executar(acao: () => Promise<void>) {
    definirErro(null)
    definirEnviando(true)
    try { await acao() } catch (falha) { falhou(falha) } finally { definirEnviando(false) }
  }

  function enviar(e: FormEvent) {
    e.preventDefault()
    if (bloqueio > 0) return
    if (etapa === 'entrar') {
      executar(async () => {
        try {
          entrou(await api.entrar(email, senha, manter))
        } catch (falha) {
          // Conta criada mas e-mail ainda não confirmado: vai direto ao código.
          if ((falha as ErroApi).status === 403) {
            definirAviso('Falta confirmar seu e-mail. Enviamos um código novo.')
            api.reenviarCodigo(email, 'confirmar').catch(() => {})
            definirReenvio(REENVIO_S); definirCodigo(''); definirEtapa('confirmar')
            return
          }
          throw falha
        }
      })
    } else if (etapa === 'registrar') {
      if (!forcaOk) { definirErro('Escolha uma senha mais forte (veja as regras abaixo do campo).'); vibrar([40, 30, 40]); return }
      executar(async () => {
        const r = await api.registrar({ nome, email, senha, tipo, ...(tipo === 'motorista' ? { placa, modelo } : {}) })
        if ('confirmacao_pendente' in r) { definirReenvio(REENVIO_S); definirCodigo(''); definirEtapa('confirmar') }
        else entrou(r)
      })
    } else if (etapa === 'confirmar') {
      executar(async () => entrou(await api.confirmarEmail(email, codigo, manter)))
    } else if (etapa === 'recuperar') {
      executar(async () => {
        await api.recuperarSenha(email)
        definirReenvio(REENVIO_S); definirCodigo(''); definirSenha(''); definirEtapa('redefinir')
      })
    } else if (etapa === 'redefinir') {
      if (!forcaOk) { definirErro('Escolha uma senha mais forte.'); vibrar([40, 30, 40]); return }
      executar(async () => entrou(await api.redefinirSenha(email, codigo, senha, manter)))
    }
  }

  function reenviar() {
    if (reenvio > 0) return
    vibrar(8)
    definirReenvio(REENVIO_S)
    api.reenviarCodigo(email, etapa === 'confirmar' ? 'confirmar' : 'recuperar')
      .then(() => definirAviso('Código reenviado.')).catch(falhou)
  }

  async function google() {
    definirComGoogle(true)
    definirErro(null)
    try {
      const { pedirCredencialGoogle } = await import('../lib/google')
      const credencial = await pedirCredencialGoogle()
      entrou(await api.entrarComGoogle(credencial, registrando ? tipo : undefined, manter))
    } catch (falha) {
      if ((falha as Error).name !== 'Cancelado') falhou(falha)
    } finally {
      definirComGoogle(false)
    }
  }

  const textoBotao: Record<Etapa, string> = {
    entrar: 'Entrar', registrar: 'Criar conta', confirmar: 'Confirmar e-mail',
    recuperar: 'Enviar código', redefinir: 'Salvar nova senha',
  }
  const codigoCompleto = codigo.length === DIGITOS

  return (
    <div className="tela-entrada">
      <FundoCidade centro={centro} />
      <div className="entrada-vinheta" />

      <motion.div className={`entrada-heroi ${heroiCheio ? '' : 'compacto'}`} layout
                  transition={{ type: 'spring', stiffness: 260, damping: 30 }}>
        <motion.div initial={{ scale: 0.2, rotate: -180, opacity: 0 }} animate={{ scale: heroiCheio ? 1 : 0.62, rotate: 0, opacity: 1 }}
                    transition={{ type: 'spring', stiffness: 120, damping: 14 }}>
          <Bussola rumo={rumo} tamanho={112} inclinar />
        </motion.div>
        <h1 className="marca" aria-label="TrueCompass">
          {MARCA.map((letra, i) => (
            <motion.span key={i} className={i >= 4 ? 'marca-b' : ''} aria-hidden="true"
                         initial={{ opacity: 0, y: 30, rotateX: -90, filter: 'blur(8px)' }}
                         animate={{ opacity: 1, y: 0, rotateX: 0, filter: 'blur(0px)' }}
                         transition={{ delay: 0.35 + i * 0.045, type: 'spring', stiffness: 260, damping: 18,
                                       filter: { delay: 0.35 + i * 0.045, duration: 0.4 }, opacity: { delay: 0.35 + i * 0.045, duration: 0.3 } }}>
              {letra}
            </motion.span>
          ))}
        </h1>
        {heroiCheio && (
          <motion.div className="subtitulo" initial={{ opacity: 0, letterSpacing: '0.4em' }}
                      animate={{ opacity: 1, letterSpacing: '0.02em' }} transition={{ delay: 0.9, duration: 0.9, ease: [0.16, 1, 0.3, 1] }}>
            Sua corrida, no caminho certo.
          </motion.div>
        )}
      </motion.div>

      <motion.form className="entrada-form" onSubmit={enviar} noValidate={etapa === 'confirmar' || etapa === 'redefinir'}
                   initial={{ opacity: 0, y: 120 }} animate={{ opacity: 1, y: 0 }}
                   transition={{ delay: 0.5, type: 'spring', stiffness: 160, damping: 22 }}>
        {/* NENHUM layoutId nesta tela (o destaque das abas e o check do perfil
            são CSS). layoutId desmontado ou trocado de lugar aqui dentro deixava
            a saída da tela pendurada: depois de trocar de aba e entrar, a tela de
            login ficava montada, invisível, por trás do mapa — com o fundo
            animado gastando bateria — e voltava com o estado antigo ao sair. */}
          <motion.div key={principal ? 'principal' : etapa} className="entrada-etapa"
                      initial={{ opacity: 0, x: principal ? -30 : 30 }} animate={{ opacity: 1, x: 0 }}
                      transition={{ duration: 0.25 }}>

            {principal && (
              <>
                <div className={`segmentado ${registrando ? 'na-direita' : ''}`} role="tablist">
                  <span className="segmento-fundo deslizante" aria-hidden="true" />
                  {(['entrar', 'registrar'] as const).map((chave) => (
                    <button key={chave} type="button" role="tab" aria-selected={etapa === chave}
                            className={etapa === chave ? 'ativo' : ''} onClick={() => irPara(chave)}>
                      <span>{chave === 'entrar' ? 'Entrar' : 'Criar conta'}</span>
                    </button>
                  ))}
                </div>

                <AnimatePresence>{falhaBackend && <Aviso tipo="erro">{falhaBackend}</Aviso>}</AnimatePresence>

                <AnimatePresence initial={false}>
                  {registrando && (
                    <motion.div key="perfis" className="perfis" initial={{ opacity: 0, height: 0 }}
                                animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }}>
                      {([['passageiro', 'usuario', 'Passageiro', 'Peço corridas'], ['motorista', 'carro', 'Motorista', 'Faço corridas']] as const)
                        .map(([chave, icone, titulo, nota]) => (
                          <motion.button key={chave} type="button" whileTap={{ scale: 0.94 }} whileHover={{ y: -3 }}
                                         className={`perfil ${tipo === chave ? 'ativo' : ''}`}
                                         onClick={() => { vibrar(6); definirTipo(chave) }}>
                            <motion.span animate={tipo === chave ? { rotate: [0, -14, 10, 0], scale: [1, 1.2, 1] } : {}}
                                         transition={{ duration: 0.5 }}>
                              <Icone nome={icone} tamanho={26} />
                            </motion.span>
                            <b>{titulo}</b><small>{nota}</small>
                            {tipo === chave && (
                              <motion.span className="perfil-check" initial={{ scale: 0 }} animate={{ scale: 1 }}
                                           transition={{ type: 'spring', stiffness: 500, damping: 26 }}>
                                <Icone nome="check" tamanho={12} traco={3.4} />
                              </motion.span>
                            )}
                          </motion.button>
                        ))}
                    </motion.div>
                  )}
                </AnimatePresence>

                <BotaoGoogle texto={registrando ? 'Criar conta com Google' : 'Continuar com Google'}
                             onClick={google} carregando={comGoogle} />
                <div className="divisor"><span>ou com e-mail</span></div>

                <AnimatePresence initial={false}>
                  {registrando && (
                    <Campo key="nome" id="nome" rotulo="Nome" value={nome} required minLength={2} autoComplete="name"
                           onChange={(e) => definirNome(e.target.value)} />
                  )}
                  <Campo key="email" id="email" rotulo="E-mail" type="email" value={email} required autoComplete="username"
                         inputMode="email" onChange={(e) => definirEmail(e.target.value)} />
                  <CampoSenha key="senha" id="senha" rotulo="Senha" valor={senha} definir={definirSenha} nova={registrando} />
                  {registrando && <MedidorSenha key="medidor" senha={senha} email={email} />}
                  {registrando && tipo === 'motorista' && (
                    <Campo key="placa" id="placa" rotulo="Placa" value={placa} required maxLength={10} autoCapitalize="characters"
                           onChange={(e) => definirPlaca(e.target.value.toUpperCase())} />
                  )}
                  {registrando && tipo === 'motorista' && (
                    <Campo key="modelo" id="modelo" rotulo="Modelo do carro" value={modelo} maxLength={60}
                           onChange={(e) => definirModelo(e.target.value)} />
                  )}
                </AnimatePresence>

                <div className="entrada-opcoes">
                  <label className="manter">
                    <input type="checkbox" checked={manter} onChange={(e) => { vibrar(6); definirManter(e.target.checked) }} />
                    <span className="manter-caixa"><Icone nome="check" tamanho={12} traco={3.4} /></span>
                    Manter conectado
                  </label>
                  {!registrando && (
                    <button type="button" className="link" onClick={() => irPara('recuperar')}>Esqueci minha senha</button>
                  )}
                </div>
              </>
            )}

            {etapa === 'confirmar' && (
              <div className="etapa-cabeca">
                <button type="button" className="botao-icone" aria-label="Voltar" onClick={() => irPara('registrar')}>
                  <Icone nome="voltar" tamanho={22} />
                </button>
                <span className="etapa-selo"><Icone nome="envelope" tamanho={26} /></span>
                <h2>Confirme seu e-mail</h2>
                <p>Enviamos um código de 6 dígitos para <b>{emailMascarado(email)}</b>. Ele vale por 15 minutos.</p>
                <CodigoVerificacao valor={codigo} definir={definirCodigo} erro={Boolean(erro)} />
              </div>
            )}

            {etapa === 'recuperar' && (
              <div className="etapa-cabeca">
                <button type="button" className="botao-icone" aria-label="Voltar" onClick={() => irPara('entrar')}>
                  <Icone nome="voltar" tamanho={22} />
                </button>
                <span className="etapa-selo"><Icone nome="cadeado" tamanho={26} /></span>
                <h2>Esqueceu a senha?</h2>
                <p>Digite o e-mail da sua conta. Enviaremos um código para você criar uma senha nova.</p>
                <AnimatePresence initial={false}>
                  <Campo id="email-recuperar" rotulo="E-mail" type="email" value={email} required autoComplete="username"
                         inputMode="email" onChange={(e) => definirEmail(e.target.value)} />
                </AnimatePresence>
              </div>
            )}

            {etapa === 'redefinir' && (
              <div className="etapa-cabeca">
                <button type="button" className="botao-icone" aria-label="Voltar" onClick={() => irPara('recuperar')}>
                  <Icone nome="voltar" tamanho={22} />
                </button>
                <span className="etapa-selo"><Icone nome="escudo" tamanho={26} /></span>
                <h2>Crie uma senha nova</h2>
                <p>Digite o código que enviamos para <b>{emailMascarado(email)}</b> e a senha nova.</p>
                <CodigoVerificacao valor={codigo} definir={definirCodigo} erro={Boolean(erro)} />
                {/* Campos com `exit` SEMPRE dentro de um AnimatePresence próprio:
                    solto, o campo se registra no AnimatePresence do App, e a
                    tela de login nunca terminava de sair depois de entrar. */}
                <AnimatePresence initial={false}>
                  <CampoSenha key="nova-senha" id="nova-senha" rotulo="Senha nova" valor={senha} definir={definirSenha} nova />
                  <MedidorSenha key="medidor" senha={senha} email={email} />
                </AnimatePresence>
              </div>
            )}
          </motion.div>

        <AnimatePresence>
          {bloqueio > 0 && (
            <Aviso key="bloqueio" tipo="erro">
              Muitas tentativas seguidas. Por segurança, tente de novo em <b className="mono">{relogio(bloqueio)}</b>.
            </Aviso>
          )}
          {erro && bloqueio <= 0 && <Aviso key="erro" tipo="erro">{erro}</Aviso>}
          {aviso && !erro && <Aviso key="aviso" tipo="ok">{aviso}</Aviso>}
        </AnimatePresence>

        <div ref={botaoRef}>
          <Botao type="submit" carregando={enviando}
                 disabled={bloqueio > 0 || ((etapa === 'confirmar' || etapa === 'redefinir') && !codigoCompleto)}>
            {textoBotao[etapa]} <Icone nome="seta" tamanho={18} />
          </Botao>
        </div>

        {(etapa === 'confirmar' || etapa === 'redefinir') && (
          <p className="texto-apoio centro">
            Não chegou? Olhe o spam ou{' '}
            <button type="button" className="link" disabled={reenvio > 0} onClick={reenviar}>
              {reenvio > 0 ? `reenvie em ${relogio(reenvio)}` : 'reenvie o código'}
            </button>
          </p>
        )}
        {registrando && (
          <p className="texto-apoio centro pequeno">
            A senha é guardada com bcrypt: o servidor nunca a armazena em texto.
          </p>
        )}
      </motion.form>
    </div>
  )
}
