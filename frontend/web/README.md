# TrueCompass — front-end

Aplicativo web em **React + Vite** consumindo a API do TrueCompass.

## Rodar

Com o backend no ar em `http://127.0.0.1:8000`:

```bash
npm install
npm run dev -- --strictPort     # http://127.0.0.1:5173
```

`--strictPort` faz o Vite falhar se a porta estiver ocupada, em vez de
escorregar para 5174 — o que deixaria o proxy apontando para o lugar errado.

Em desenvolvimento o front chama `/api/...` e o **proxy do Vite** encaminha ao
backend — sem CORS e sem URL absoluta espalhada pelo código. O proxy também
encaminha o WebSocket (`ws: true` no `vite.config.js`).

Para apontar a outro backend:

```bash
VITE_BACKEND=http://192.168.0.10:8000 npm run dev
```

## Build e deploy

```bash
npm run build        # gera dist/
npm run preview      # confere o build localmente
```

No **Vercel**: importe o repositório, defina `frontend/web` como diretório raiz e
configure a variável `VITE_API_URL` apontando para o backend no Railway.
O `vercel.json` já traz o rewrite de SPA.

## Como está organizado

```
src/
├── api.js                    cliente HTTP + URL do WebSocket
├── App.jsx                   sessão, tema, carga da malha
├── estilos.css               paleta herdada do protótipo do squad
├── ganchos/
│   └── usarCorridaAoVivo.js  assina o WebSocket da corrida
└── componentes/
    ├── TelaAutenticacao.jsx  registro e login
    ├── Mapa.jsx              Leaflet: malha, rotas, marcadores
    ├── LinhaDeEstados.jsx    o DAG da corrida, visualmente
    ├── PainelPassageiro.jsx  pedir corrida e acompanhar
    └── PainelMotorista.jsx   ficar online, receber, deslocar
```

## O visual

Paleta de **instrumento**, não de painel de software: corpo de aço escovado
(cinzas), agulha norte (vermelho), vegetação e patina (verde natureza). A
referência é uma bússola de campo.

Tudo que anima representa algo real:

| Animação | O que representa |
|---|---|
| Agulha da bússola | o **azimute inicial** até o destino, calculado na hora |
| Traçado da rota | a ordem em que o A\* percorreu o caminho |
| Pulso de radar | o raio em que o pareamento está procurando motorista |
| Marcador do motorista | interpolação entre pings de GPS, para não teleportar |

`prefers-reduced-motion` desliga tudo, para quem precisa.

## Três decisões que vale conhecer

**O mapa desenha a malha da nossa API, não só tiles.** Os tiles do
OpenStreetMap são pano de fundo opcional — se a internet falhar, a camada é
removida após algumas tentativas e o mapa continua útil, porque as ruas vêm de
`/malha/trechos`. Você vê o grafo que o algoritmo realmente percorre: mão
única tracejada, mão dupla sólida.

**Marcadores são círculos SVG, não ícones.** Os ícones padrão do Leaflet
quebram sob bundler porque as imagens são resolvidas por caminho relativo ao
CSS. `circleMarker` não depende de asset algum.

**A agulha gira pelo caminho curto.** A rotação é acumulada: ir de 350° para
10° soma +20°, não −340°. Sem isso a agulha daria quase uma volta inteira ao
cruzar o norte.

**A malha inteira sai em duas camadas, não uma por rua.** `L.polyline` aceita
array de arrays e desenha milhares de segmentos como **uma** camada. Criar uma
camada por rua trava o navegador. No teste, o maior `<path>` tem 37 mil
caracteres — é a malha inteira num elemento só.

## Fluxo da demonstração

Abra **duas janelas** (uma anônima, para sessões separadas):

1. **Motorista** — cadastre-se como motorista, clique no mapa para marcar sua
   posição, clique em *Ficar online*.
2. **Passageiro** — cadastre-se, clique na origem, clique no destino, peça a
   corrida. O motorista aparece com ETA e valor.
3. **Motorista** — a corrida aparece sozinha (a batida de GPS roda a cada 4s).
   Clique em *Simular deslocamento*: o carro percorre as ruas de verdade.
4. **Passageiro** — veja os pings de GPS chegando no cartão *Tempo real* e
   percorra o fluxo: Embarquei → Cheguei → Pagar.

Repare que **Pagar só aparece depois de concluída** — não é regra da interface,
é o DAG do backend recusando a transição.

## Teste ponta a ponta

```bash
pip install playwright && playwright install chromium
python3 e2e/fluxo.py
```

Sobe dois navegadores, percorre o ciclo inteiro e grava capturas em
`e2e/capturas/`. Use **banco limpo**: motoristas online de execuções anteriores
competem no pareamento e deixam o teste instável.
