import { motion } from 'framer-motion'
import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { horarioDaqui, paraPonto, textoDuracao } from '../lib/util'
import { Mapa, type ApiMapa } from '../mapa/Mapa'
import type { Acompanhamento, LatLon, Tema } from '../tipos'
import { Bussola } from '../ui/Bussola'
import { Aviso, Folha, type Margens } from '../ui/Folha'
import { Icone } from '../ui/Icone'
import { SeloFinal } from './Comum'

const INTERVALO_MS = 5000
const VAZIO: LatLon[] = []

const FRASE: Record<string, string> = {
  alocacao: 'O motorista está indo buscar', rota: 'O motorista está indo buscar',
  em_curso: 'Em viagem', concluida: 'Chegou ao destino', paga: 'Viagem concluída', cancelada: 'Corrida cancelada',
}

/**
 * Acompanhamento público, pelo link que o passageiro compartilhou. Sem
 * login: quem recebe (família, amigos) não tem conta. Consulta o backend a
 * cada 5 s — o WebSocket da corrida exige token de quem está nela.
 */
export function Acompanhar({ codigo, tema }: { codigo: string; tema: Tema }) {
  const mapa = useRef<ApiMapa>(null)
  const [dados, definirDados] = useState<Acompanhamento | null>(null)
  const [erro, definirErro] = useState<string | null>(null)
  const [margens, definirMargens] = useState<Margens>({ base: 0, esquerda: 0 })
  const enquadrado = useRef(false)

  useEffect(() => {
    let vivo = true
    let id: ReturnType<typeof setTimeout> | undefined
    const consultar = async () => {
      try {
        const novo = await api.acompanhar(codigo)
        if (!vivo) return
        definirDados(novo)
        definirErro(null)
        if (!enquadrado.current && novo.pontos.length > 1) {
          enquadrado.current = true
          setTimeout(() => mapa.current?.enquadrar(novo.pontos), 300)
        }
        if (novo.ativa) id = setTimeout(consultar, INTERVALO_MS)   // encerrada: para de consultar
      } catch (f) {
        if (!vivo) return
        definirErro((f as Error & { status?: number }).status === 404
          ? 'Este link de acompanhamento não existe ou expirou.' : (f as Error).message)
        id = setTimeout(consultar, INTERVALO_MS * 2)
      }
    }
    consultar()
    return () => { vivo = false; clearTimeout(id) }
  }, [codigo])

  const motorista = dados?.posicao_motorista ? paraPonto(dados.posicao_motorista) : null
  const quem = dados?.passageiro ?? 'O passageiro'
  return (
    <div className="tela-app">
      <Mapa ref={mapa} tema={tema} margens={margens}
            origem={dados?.origem ? paraPonto(dados.origem) : null}
            destino={dados?.destino ? paraPonto(dados.destino) : null}
            paradas={dados?.paradas ?? []}
            motorista={dados?.ativa ? motorista : null}
            rota={dados?.ativa ? dados.pontos : VAZIO}
            cometa={dados?.estado === 'em_curso'} />
      <div className="barra-topo acompanhar-topo">
        <span className="marca-acompanhar"><Bussola rumo={0} tamanho={30} letras={false} /> <span>True<b>Compass</b></span></span>
      </div>
      <Folha chave={dados ? `${dados.ativa}-${dados.estado}` : erro ? 'erro' : 'carregando'} aoMedir={definirMargens}>
        <div className="conteudo">
          {!dados && !erro && <p className="texto-apoio">Carregando a viagem…</p>}
          {erro && <Aviso tipo="erro">{erro}</Aviso>}
          {dados && !dados.ativa && (
            <div className="conteudo centralizado">
              <SeloFinal ok={dados.estado !== 'cancelada'} />
              <b className="titulo-folha pequeno">{FRASE[dados.estado] ?? dados.estado}</b>
              <p className="texto-apoio">{dados.estado === 'cancelada' ? 'A corrida foi cancelada.' : `${quem} chegou${dados.destino_texto ? ` em ${dados.destino_texto}` : ''}.`}</p>
            </div>
          )}
          {dados?.ativa && (
            <>
              <div className="status-corrida">
                <small>Você está acompanhando a viagem de {quem}</small>
                <h2 className="titulo-folha">{FRASE[dados.estado] ?? dados.estado}</h2>
              </div>
              {dados.segundos_restantes != null && (
                <motion.div className="linha-motoristas ok" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                  <span className="ponto pulsando" />
                  <span>Chegada prevista às <b>{horarioDaqui(dados.segundos_restantes)}</b> · faltam {textoDuracao(dados.segundos_restantes)}</span>
                </motion.div>
              )}
              {dados.destino_texto && (
                <div className="acompanhar-destino"><Icone nome="bandeira" tamanho={16} /> {dados.destino_texto}</div>
              )}
              {dados.motorista && (
                <div className="cartao-motorista">
                  <span className="avatar grande">{dados.motorista[0]}</span>
                  <div className="cartao-motorista-textos"><b>{dados.motorista}</b><span>{dados.carro ?? 'Carro'}</span></div>
                  {dados.placa && <span className="placa"><small>BRASIL</small>{dados.placa}</span>}
                </div>
              )}
              <p className="nota-categorias"><small>A posição é atualizada a cada 5 segundos. Este link mostra só esta viagem.</small></p>
            </>
          )}
        </div>
      </Folha>
    </div>
  )
}
