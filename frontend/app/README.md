# TrueCompass — app (React + TypeScript)

Front-end mobile do TrueCompass, ligado ao backend FastAPI deste repositório.
Não é uma página imitando um celular: o mapa ocupa a tela inteira e o conteúdo
sobe numa folha arrastável. Em tela larga a folha vira painel lateral.

## Rodar

Com o backend no ar em `http://127.0.0.1:8000` (ver `COMO_RODAR.md` na raiz):

```bash
npm install
npm run dev          # http://localhost:5180
```

O app chama `/api/...` e o proxy do Vite encaminha ao backend, inclusive o
WebSocket. Para outro backend: `VITE_BACKEND=http://192.168.0.10:8000 npm run dev`.

A porta é **5180** (e não 5173) para o front anterior, em `frontend/web/`, poder rodar ao lado.

Geolocalização só funciona em `https` ou `localhost`. Pelo IP da rede local, o
app segue funcionando, mas a partida é escolhida pela busca ou no mapa.

```bash
npm run tipos        # TypeScript estrito, sem emitir
npm run build        # tipos + build de produção em dist/
```

Deploy no Vercel: diretório raiz `frontend/app`, variável `VITE_API_URL` apontando para
o backend no Railway (que precisa de `CORS_ORIGENS` com o domínio do Vercel).

## Organização

```
src/
├── tipos.ts              contratos do backend, espelhados em TypeScript
├── api.ts                cliente tipado + URL do WebSocket
├── ganchos.ts            GPS, busca de lugares, corrida ao vivo, tela larga
├── lib/util.ts           haversine, rumo verdadeiro, formatos, armazenamento
├── mapa/
│   ├── Mapa.tsx          Leaflet: tiles OSM, rota, marcadores, carro
│   └── onda.ts           canvas da ONDA da busca e do cometa sobre a rota
├── ui/                   Bússola, Folha, Botão, Odômetro, Confete, ícones
├── telas/                Entrada, Busca, Passageiro, Motorista, Comum
└── estilos/              base, mapa, folha, telas (tema claro e escuro)
```

## O fluxo, no padrão dos apps de corrida

| Tela | O que tem |
|---|---|
| Início | "Para onde?", recentes e a partida (GPS). Mapa em cinza, sem semáforos |
| Escolha da viagem | Três categorias com preço e chegada; botão fixo; a rota visível no mapa |
| Corrida | "Chega em N min", cartão do motorista (corridas concluídas, categoria, placa, carro) |
| Motorista | Botão Iniciar/Pausar, ganhos e corridas de hoje, chegada de corrida |

## As animações, e o que cada uma representa

| Animação | O que é de verdade |
|---|---|
| Cidade se revelando na entrada | Trechos reais da malha (`/malha/trechos`), revelados do centro para fora |
| Onda verde antes da rota | Nós que o **A\*** alcançou, na ordem real de descoberta (`exploracao` da estimativa) |
| "Ver as duas buscas no mapa" | A\* e **Dijkstra** na mesma velocidade: o A\* termina antes porque descobre menos nós |
| Rota se desenhando + cometa | O caminho que o A\* devolveu, do embarque ao destino |
| Radar na partida | O pareamento: busca reversa até os motoristas |
| Agulha da bússola | Azimute inicial (grande círculo) até o destino; procurando, gira e trava no motorista |
| Carro girando | Rumo verdadeiro entre dois pings de GPS |
| Barra do fluxo | O DAG da corrida, na ordem topológica validada por Kahn |

Com `prefers-reduced-motion`, as ondas, o cometa e o confete são desligados.

## Armadilhas já resolvidas (não reintroduzir)

- **`AnimatePresence mode="wait"` na troca de telas trava**: a tela de saída
  termina a animação e nunca é desmontada. As telas são `position: absolute`
  e trocam em modo simultâneo.
- **Mola em `filter: blur()`** passa de zero e gera blur negativo (inválido).
  Mola só em deslocamento/escala; blur sempre com curva.
- **Carimbo do `requestAnimationFrame`** é o início do quadro e pode ser
  anterior ao `performance.now()` lido ao iniciar a onda: o tempo decorrido
  é preso em zero, senão o índice sai negativo.
- **Tiles da CARTO passaram a exigir chave de API.** Usamos os tiles padrão do
  OpenStreetMap; no tema escuro um filtro CSS os inverte.
- A ordem de descoberta das duas buscas é amostrada com o **mesmo passo**
  (`passo_comum` no backend). Amostrar cada uma para o mesmo tamanho apagaria
  a diferença entre A\* e Dijkstra.
