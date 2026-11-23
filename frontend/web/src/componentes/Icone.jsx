/**
 * Ícones em SVG inline (traço 2px, 24×24). Inline, e não arquivo de imagem,
 * pelo mesmo motivo dos marcadores do mapa: nada depende de caminho de asset
 * que o bundler possa quebrar, e a cor herda de `currentColor`.
 */
const CAMINHOS = {
  busca: <><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></>,
  voltar: <path d="M15 18l-6-6 6-6" />,
  fechar: <path d="M18 6 6 18M6 6l12 12" />,
  mira: <><circle cx="12" cy="12" r="7" /><circle cx="12" cy="12" r="2.5" /><path d="M12 2v3M12 19v3M2 12h3M19 12h3" /></>,
  pino: <><path d="M12 21s-7-6.2-7-11.5A7 7 0 0 1 19 9.5C19 14.8 12 21 12 21z" /><circle cx="12" cy="9.5" r="2.5" /></>,
  relogio: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
  trocar: <path d="M7 4v16M7 20l-3-3M7 20l3-3M17 20V4M17 4l-3 3M17 4l3 3" />,
  carro: <><path d="M5 17h14v-4.5l-1.8-4.7A2 2 0 0 0 15.3 6.5H8.7a2 2 0 0 0-1.9 1.3L5 12.5z" /><path d="M5 12.5h14" /><circle cx="8" cy="17" r="1.6" /><circle cx="16" cy="17" r="1.6" /></>,
  semaforo: <><rect x="8" y="2.5" width="8" height="19" rx="3" /><circle cx="12" cy="7" r="1.4" /><circle cx="12" cy="12" r="1.4" /><circle cx="12" cy="17" r="1.4" /></>,
  rota: <><circle cx="6" cy="19" r="2.5" /><circle cx="18" cy="5" r="2.5" /><path d="M8.5 19H16a3.5 3.5 0 0 0 0-7H8a3.5 3.5 0 0 1 0-7h7.5" /></>,
  check: <path d="M5 12.5l4.5 4.5L19 7.5" />,
  camadas: <><path d="m12 3 9 5-9 5-9-5 9-5z" /><path d="m3 13 9 5 9-5" /></>,
  sol: <><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></>,
  lua: <path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z" />,
  sair: <><path d="M15 4h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-3" /><path d="M10 17l-5-5 5-5M5 12h11" /></>,
  usuario: <><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></>,
  energia: <><path d="M12 3v8" /><path d="M6.3 7.3a8 8 0 1 0 11.4 0" /></>,
  seta: <path d="M5 12h14M13 6l6 6-6 6" />,
  mapa: <><path d="m9 4-6 2.5v13.5l6-2.5 6 2.5 6-2.5V4l-6 2.5z" /><path d="M9 4v13.5M15 6.5V20" /></>,
  chip: <><rect x="6" y="6" width="12" height="12" rx="2" /><path d="M9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M2 15h4M18 9h4M18 15h4" /></>,
  aviso: <><path d="M12 3 2 20h20z" /><path d="M12 10v4M12 17.5v.01" /></>,
  dinheiro: <><rect x="2.5" y="6" width="19" height="12" rx="2" /><circle cx="12" cy="12" r="2.5" /></>,
  bandeira: <><path d="M5 21V4" /><path d="M5 4h11l-2 4 2 4H5" /></>,
  // categorias de lugar
  educacao: <><path d="m2 9 10-5 10 5-10 5z" /><path d="M6 11v5c3 2.5 9 2.5 12 0v-5" /></>,
  saude: <><rect x="3" y="3" width="18" height="18" rx="4" /><path d="M12 8v8M8 12h8" /></>,
  comida: <><path d="M7 3v8M5 3v5a2 2 0 0 0 4 0V3M7 11v10" /><path d="M17 21V3c-2 1.5-3 4-3 7h3" /></>,
  compras: <><path d="M5 8h14l-1 13H6z" /><path d="M9 8V6a3 3 0 0 1 6 0v2" /></>,
  cultura: <><path d="M3 10h18M5 10v8M9.5 10v8M14.5 10v8M19 10v8M3 21h18" /><path d="m12 3 9 5H3z" /></>,
  parque: <><path d="M12 3 6 12h3l-3 5h12l-3-5h3z" /><path d="M12 17v4" /></>,
  transporte: <><rect x="5" y="3" width="14" height="14" rx="3" /><path d="M5 11h14M8 21l2-4M16 21l-2-4" /><circle cx="9" cy="14" r=".6" /><circle cx="15" cy="14" r=".6" /></>,
  hospedagem: <><path d="M3 18V7M3 13h18v5M21 13a3 3 0 0 0-3-3h-7v3" /><circle cx="7" cy="10.5" r="1.8" /></>,
  servico: <><path d="M4 21V8l8-5 8 5v13" /><path d="M9 21v-6h6v6" /></>,
  religiao: <><path d="M12 2v6M9 5h6" /><path d="M5 21v-8l7-5 7 5v8z" /></>,
  esporte: <><circle cx="12" cy="12" r="9" /><path d="M3.5 9h17M3.5 15h17M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18" /></>,
  rua: <><path d="M8 3 5 21M16 3l3 18" /><path d="M12 4v3M12 10.5v3M12 17v3" /></>,
  regiao: <><path d="m9 4-6 2.5v13.5l6-2.5 6 2.5 6-2.5V4l-6 2.5z" /></>,
  endereco: <><path d="m3 11 9-7 9 7" /><path d="M5 9.5V20h14V9.5" /></>,
  lugar: <><path d="M12 21s-7-6.2-7-11.5A7 7 0 0 1 19 9.5C19 14.8 12 21 12 21z" /><circle cx="12" cy="9.5" r="2.5" /></>,
}

export function Icone({ nome, tamanho = 20, traco = 2, className, style }) {
  return (
    <svg width={tamanho} height={tamanho} viewBox="0 0 24 24" fill="none"
         stroke="currentColor" strokeWidth={traco} strokeLinecap="round"
         strokeLinejoin="round" aria-hidden="true" className={className} style={style}>
      {CAMINHOS[nome] ?? CAMINHOS.lugar}
    </svg>
  )
}
