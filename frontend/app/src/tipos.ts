/**
 * Contratos do backend (FastAPI), espelhados em TypeScript.
 *
 * Fonte da verdade: api/esquemas.py, api/rotas/*.py e
 * dominio/servicos/corrida.py. Se um campo mudar lá, muda aqui — o
 * compilador aponta cada tela que dependia dele.
 */

/** [lat, lon] — o formato compacto que o backend usa em listas de pontos. */
export type LatLon = [number, number]

export interface Ponto { lat: number; lon: number }

export type TipoUsuario = 'passageiro' | 'motorista'

export interface Sessao {
  token: string
  tipo_token: string
  usuario_id: number
  tipo: TipoUsuario
}

export interface Caixa { sul: number; oeste: number; norte: number; leste: number }

export interface InfoMalha {
  nos: number
  arestas: number
  caixa: Caixa | null
  centro?: Ponto
}

export interface Semaforo {
  lat: number
  lon: number
  vermelho: number
  ciclo: number
  atraso_medio: number
}

export interface Malha extends InfoMalha { semaforos: Semaforo[] }

/** Trecho compacto: [lat1, lon1, lat2, lon2, mao_unica(0|1)]. */
export type Trecho = [number, number, number, number, 0 | 1]

export type CategoriaLugar =
  | 'educacao' | 'saude' | 'comida' | 'compras' | 'cultura' | 'parque'
  | 'transporte' | 'hospedagem' | 'servico' | 'religiao' | 'esporte'
  | 'rua' | 'regiao' | 'endereco' | 'lugar'

export interface Lugar extends Ponto {
  id: string
  titulo: string
  detalhe: string
  categoria: CategoriaLugar
  /** Marcado pelo app quando o lugar é o GPS do aparelho. */
  gps?: boolean
}

export interface ResultadoAlgoritmo { nos_expandidos: number; ms: number }

/** Categorias de viagem (dominio/servicos/corrida.py, CATEGORIAS). */
export type IdCategoria = 'economico' | 'conforto' | 'grande'

export interface OpcaoViagem {
  id: IdCategoria
  nome: string
  lugares: number
  descricao: string
  custo: number
}

export interface Estimativa {
  segundos: number
  metros: number
  custo_estimado: number
  /** Do mais barato ao mais caro; a rota é a mesma, muda o carro. */
  categorias: OpcaoViagem[]
  /** Cruzamentos onde cada parada foi ancorada, na ordem. */
  paradas: Ponto[]
  pontos: LatLon[]
  semaforos_no_caminho: number
  /** Posição de cada semáforo do caminho, na ordem do trajeto. */
  semaforos_rota?: LatLon[]
  ancoragem_m: { origem: number; destino: number }
  algoritmo: {
    a_estrela: ResultadoAlgoritmo
    dijkstra?: ResultadoAlgoritmo & { mesmo_custo: boolean }
    /** 'alt' quando o backend tem os marcos pré-calculados; senão, linha reta. */
    heuristica?: 'alt' | 'haversine'
    velocidade_max_kmh: number
    nos_na_malha: number
    /** Uma busca por trecho: origem → paradas → destino. */
    trechos?: number
  }
  motoristas: { proximos: number; eta_mais_proximo_s: number | null } | null
  /** Frente de onda de cada busca, na ordem em que os nós foram alcançados. */
  exploracao?: { a_estrela: LatLon[]; dijkstra?: LatLon[] }
}

/** Estados do DAG da corrida (dominio/estados.py). */
export type EstadoCorrida =
  | 'pedido' | 'alocacao' | 'rota' | 'em_curso' | 'concluida' | 'paga' | 'cancelada'

export interface Corrida {
  id: number
  estado: EstadoCorrida
  motorista_id: number | null
  eta_segundos: number | null
  custo_estimado: number | null
  no_origem: number
  no_destino: number
  motorista_nome: string | null
  motorista_placa: string | null
  motorista_modelo: string | null
  /** Corridas que o motorista já concluiu. */
  motorista_corridas: number | null
  motorista_cor_carro: string | null
  /** Média das notas recebidas; null enquanto ninguém avaliou ("novo"). */
  motorista_nota: number | null
  motorista_avaliacoes: number
  passageiro_nota: number | null
  categoria: IdCategoria | null
  forma_pagamento: FormaPagamento | null
  origem_texto: string | null
  destino_texto: string | null
  /** Nota que QUEM PERGUNTA deu nesta corrida; null = ainda não avaliou. */
  minha_avaliacao: number | null
  paradas: Parada[]
  /** Só o passageiro recebe; null = ainda não compartilhada. */
  token_compartilhar: string | null
  /** Em `alocacao`: a corrida foi OFERECIDA e espera o motorista aceitar. */
  aguardando_aceite: boolean
  /** Prazo restante da oferta, medido no servidor. */
  oferta_segundos: number | null
  motivo_cancelamento: string | null
  passageiro_nome: string | null
  origem: LatLon | null
  destino: LatLon | null
}

export interface Rota { segundos: number; metros: number; pontos: LatLon[]; semaforos?: LatLon[] }

export interface Parada extends Ponto { texto: string | null }

export interface Mensagem { id: number; autor_id: number; texto: string; criada_em: string | null }

/** /publico/acompanhar/{token}: o mínimo, para quem recebeu o link. */
export interface Acompanhamento {
  estado: EstadoCorrida
  ativa: boolean
  passageiro: string | null
  motorista: string | null
  carro: string | null
  placa: string | null
  posicao_motorista: LatLon | null
  origem: LatLon | null
  destino: LatLon | null
  destino_texto: string | null
  paradas: Parada[]
  pontos: LatLon[]
  segundos_restantes: number | null
}

/** Simulado: nenhum pagamento real é processado. */
export type FormaPagamento = 'pix' | 'cartao' | 'dinheiro'

export interface Perfil {
  id: number
  nome: string
  email: string
  tipo: TipoUsuario
  telefone: string | null
  cor_avatar: string | null
  criado_em: string | null
  placa: string | null
  modelo: string | null
  cor_carro: string | null
  nota: number | null
  avaliacoes: number
  corridas: number
}

export type EdicaoPerfil = Partial<Pick<Perfil, 'nome' | 'telefone' | 'cor_avatar' | 'placa' | 'modelo' | 'cor_carro'>>

export type TipoLocal = 'casa' | 'trabalho' | 'outro'

export interface LocalSalvo {
  id: number
  tipo: TipoLocal
  rotulo: string
  titulo: string
  detalhe: string
  lat: number
  lon: number
}

export interface ItemHistorico {
  id: number
  estado: EstadoCorrida
  criada_em: string | null
  categoria: IdCategoria | null
  forma_pagamento: FormaPagamento | null
  custo_estimado: number | null
  origem_texto: string | null
  destino_texto: string | null
  /** O motorista, para o passageiro; o passageiro, para o motorista. */
  outro_nome: string | null
  minha_avaliacao: number | null
}

/** /motoristas/resumo: só entra dinheiro depois do pagamento. */
export interface ResumoMotorista { ganhos_hoje: number; corridas_hoje: number; corridas_total: number }

export interface RespostaPosicao {
  no_ancorado: number
  lat: number
  lon: number
  corrida_ativa: number | null
}

/** Mensagens do WebSocket (api/eventos.py). */
export type EventoAoVivo =
  | { evento: 'estado'; corrida_id: number; estado: EstadoCorrida }
  | { evento: 'posicao'; corrida_id: number; motorista_id: number; lat: number; lon: number }
  | { evento: 'mensagem'; corrida_id: number; mensagem: Mensagem }

export type Tema = 'escuro' | 'claro'
