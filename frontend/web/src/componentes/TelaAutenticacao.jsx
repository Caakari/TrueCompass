import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useState } from 'react'
import { api } from '../api'
import { vibrar } from '../util'
import { Botao } from './Basicos'
import { Bussola } from './Bussola'
import { Aviso } from './Sobreposicoes'
import { Icone } from './Icone'

function Campo({ id, rotulo, ...props }) {
  return (
    <motion.div className="campo" layout="position"
                initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }} transition={{ type: 'spring', stiffness: 380, damping: 34 }}>
      <input id={id} placeholder=" " {...props} />
      <label htmlFor={id}>{rotulo}</label>
    </motion.div>
  )
}

export function TelaAutenticacao({ aoEntrar, falhaBackend }) {
  const [modo, definirModo] = useState('entrar')
  const [tipo, definirTipo] = useState('passageiro')
  const [nome, definirNome] = useState('')
  const [email, definirEmail] = useState('')
  const [senha, definirSenha] = useState('')
  const [placa, definirPlaca] = useState('')
  const [modelo, definirModelo] = useState('')
  const [erro, definirErro] = useState(null)
  const [enviando, definirEnviando] = useState(false)
  // A agulha gira até "achar o norte" quando a tela abre.
  const [rumo, definirRumo] = useState(null)
  useEffect(() => {
    const ids = [setTimeout(() => definirRumo(250), 350), setTimeout(() => definirRumo(0), 1100)]
    return () => ids.forEach(clearTimeout)
  }, [])

  const registrando = modo === 'registrar'

  async function enviar(evento) {
    evento.preventDefault()
    definirErro(null)
    definirEnviando(true)
    try {
      const sessao = registrando
        ? await api.registrar({
            nome, email, senha, tipo,
            placa: tipo === 'motorista' ? placa : undefined,
            modelo: tipo === 'motorista' ? modelo : undefined,
          })
        : await api.entrar(email, senha)
      vibrar([15, 40, 15])
      aoEntrar(sessao)
    } catch (falha) {
      vibrar([40, 30, 40])
      definirErro(falha.message)
    } finally {
      definirEnviando(false)
    }
  }

  return (
    <div className="tela-entrada">
      <motion.div className="entrada-heroi" initial={{ opacity: 0, y: -16 }} animate={{ opacity: 1, y: 0 }}
                  transition={{ type: 'spring', stiffness: 200, damping: 22 }}>
        <Bussola rumo={rumo} tamanho={104} />
        <div className="marca"><b>True</b><i>Compass</i></div>
        <div className="subtitulo">Sua corrida, no caminho certo.</div>
      </motion.div>

      <motion.form className="entrada-form" onSubmit={enviar}
                   initial={{ opacity: 0, y: 40 }} animate={{ opacity: 1, y: 0 }}
                   transition={{ delay: 0.12, type: 'spring', stiffness: 220, damping: 26 }}>
        <div className="segmentado" role="tablist">
          {[['entrar', 'Entrar'], ['registrar', 'Criar conta']].map(([chave, rotulo]) => (
            <button key={chave} type="button" role="tab" aria-selected={modo === chave}
                    className={modo === chave ? 'ativo' : ''}
                    onClick={() => { vibrar(6); definirModo(chave); definirErro(null) }}>
              {modo === chave && <motion.span layoutId="segmento" className="segmento-fundo"
                                              transition={{ type: 'spring', stiffness: 500, damping: 36 }} />}
              <span>{rotulo}</span>
            </button>
          ))}
        </div>

        {falhaBackend && <Aviso tipo="erro">{falhaBackend}</Aviso>}

        <AnimatePresence initial={false}>
          {registrando && (
            <motion.div key="perfil" className="perfis"
                        initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }}
                        exit={{ opacity: 0, height: 0 }}>
              {[['passageiro', 'usuario', 'Passageiro', 'Peço corridas'],
                ['motorista', 'carro', 'Motorista', 'Faço corridas']].map(([chave, icone, titulo, nota]) => (
                <motion.button key={chave} type="button" whileTap={{ scale: 0.96 }}
                               className={`perfil ${tipo === chave ? 'ativo' : ''}`}
                               onClick={() => { vibrar(6); definirTipo(chave) }}>
                  <Icone nome={icone} tamanho={24} />
                  <b>{titulo}</b><small>{nota}</small>
                  {tipo === chave && (
                    <motion.span className="perfil-check" layoutId="perfil-check">
                      <Icone nome="check" tamanho={12} traco={3.4} />
                    </motion.span>
                  )}
                </motion.button>
              ))}
            </motion.div>
          )}
        </AnimatePresence>

        <AnimatePresence initial={false}>
          {registrando && (
            <Campo key="nome" id="nome" rotulo="Nome" value={nome} required minLength={2}
                   autoComplete="name" onChange={(e) => definirNome(e.target.value)} />
          )}
          <Campo key="email" id="email" rotulo="E-mail" type="email" value={email} required
                 autoComplete="username" inputMode="email"
                 onChange={(e) => definirEmail(e.target.value)} />
          <Campo key="senha" id="senha" rotulo="Senha" type="password" value={senha} required minLength={8}
                 autoComplete={registrando ? 'new-password' : 'current-password'}
                 onChange={(e) => definirSenha(e.target.value)} />
          {registrando && tipo === 'motorista' && (
            <Campo key="placa" id="placa" rotulo="Placa" value={placa} required maxLength={10}
                   autoCapitalize="characters" onChange={(e) => definirPlaca(e.target.value.toUpperCase())} />
          )}
          {registrando && tipo === 'motorista' && (
            <Campo key="modelo" id="modelo" rotulo="Modelo do carro" value={modelo} maxLength={60}
                   onChange={(e) => definirModelo(e.target.value)} />
          )}
        </AnimatePresence>

        <AnimatePresence>{erro && <Aviso tipo="erro">{erro}</Aviso>}</AnimatePresence>

        <Botao type="submit" carregando={enviando} onClick={undefined}>
          {registrando ? 'Criar conta' : 'Entrar'}
        </Botao>

        {registrando && (
          <p className="texto-apoio">
            Mínimo de 8 caracteres. A senha é guardada com bcrypt — o servidor nunca a armazena em texto.
          </p>
        )}
      </motion.form>
    </div>
  )
}
