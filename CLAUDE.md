# TrueCompass — instruções do projeto

## Git: commitar apenas no Prototipo-TrueCompass

**Commits e push são autorizados**, e apenas para este repositório:

```
https://github.com/Cm-Kauan/Prototipo-TrueCompass.git
```

Nenhum outro. `Caakari/TrueCompass` é o repositório antigo do squad, preservado
somente leitura na prática — **nunca** empurre nada para lá.

### Confira o remote antes de todo push

O container reconfigura `origin` para `Caakari/TrueCompass` a cada reinício.
Isso já aconteceu duas vezes. Antes de empurrar:

```bash
git remote get-url origin        # tem de ser Cm-Kauan/Prototipo-TrueCompass
git remote set-url origin https://github.com/Cm-Kauan/Prototipo-TrueCompass.git
```

Sem essa conferência, o commit vai para o repositório errado em silêncio.

### Disciplina de commit

- **Rode a suíte inteira antes de commitar.** Nada de commit com teste vermelho.
- `git fetch origin main` antes: o Kauan e o squad também empurram aqui.
  Divergiu, faça merge — **nunca** rebase nem force-push em branch compartilhada.
- Branch de trabalho: `main`.
- **Não commite artefato derivado.** `backend/dados/alt.bin` sai de
  `backend/dados/malha.json.gz` em segundos e está no `.gitignore`. `malha.json.gz`
  fica versionado porque regerá-lo exige a Overpass. Os extratos crus
  (`backend/dados/osm_bruto/`) também ficam fora.
- Mensagem em português, descrevendo a decisão e o porquê — não só o quê.
- **Não abra Pull Request** sem pedido explícito.
- Apagar repositório, branch alheia ou reescrever histórico: **nunca**.

### Sobre o hook

`stop-hook-git-check.sh` avisa quando sobra coisa sem commitar. Agora isso é
sinal legítimo: termine o trabalho e commite. Se houver motivo para deixar algo
fora (artefato derivado, experimento), diga em uma linha por quê.

## Contexto do projeto

Aplicativo de mobilidade urbana (acadêmico — Matemática Computacional Aplicada,
USJT). A documentação técnica está em `docs/Documentacao_App/`.

O repositório é separado em quatro pastas (mapa completo em `INDICE.md`):

```
frontend/    app/ (atual, React+TS) · web/ (anterior) · prototipo_html/
backend/     api/ · dominio/ · infra/ · dados/ · tests/
matematica/  algoritmos/ · mapas/ · tests/
docs/        Documentacao_App/ · Documentacao_Aula/
```

- O backend importa `algoritmos` de `matematica/` via
  `backend/matematica_no_caminho.py`, chamado no `__init__` de `api`, `dominio`
  e `infra`. Testes do backend importam esse módulo logo após o `sys.path`.
  **Não** mover `algoritmos/` para dentro do backend: ele não conhece ninguém.
- Caminhos de dados em `infra/config.py` são resolvidos a partir de `backend/`
  (a matriz, em `matematica/mapas/`): o servidor sobe de qualquer pasta.
- Servidor: `uvicorn --app-dir backend api.main:app` na raiz (é assim no
  Railway, que precisa da RAIZ do repositório por causa de `matematica/`).
  As dependências ficam no `requirements.txt` da **raiz**, autocontido, e
  `backend/requirements.txt` só faz `-r ../requirements.txt`. **Nunca** o
  contrário: o Railpack (construtor atual do Railway) copia só o arquivo da
  raiz para rodar o pip, e um `-r backend/...` ali quebra o build.

Camada de algoritmos em `matematica/algoritmos/` (matemática pura, sem FastAPI nem SQL):

- `grafo.py` — malha viária como grafo ponderado direcionado, grafo reverso
  com cache, heurística haversine
- `busca.py` — Dijkstra e A* unificados numa única rotina (Dijkstra ≡ A* com h ≡ 0)
- `matching.py` — pareamento reverso many-to-one
- `quadtree.py` — índice espacial O(log n + k), com poda por retângulo
- `topologica.py` — algoritmo de Kahn (genérico)
- `matriz_mapa.py` — mapa como **matriz de células** → grafo; fonte de autoria
- `semaforo.py` — atraso esperado `E[espera] = r²/(2c)`
- `contracao.py` — contrai nós de passagem (79% da malha OSM); `Geometria`
  guarda a forma das ruas para desenhar e medir metros
- `alt.py` — A* + Landmarks + desigualdade Triangular; heurística 14× mais
  apertada que a haversine na malha real
- `indice_espacial.py` — `IndiceLinear`, mantido como **oráculo** da quadtree
- `EXPLICACAO.md` — guia didático dos algoritmos
- `MATEMATICA.md` — guia didático das fórmulas (companheiro do acima)
- `matematica/tests/test_algoritmos.py` — 19 testes, rodam com `python3` puro (sem pytest)

Camada de infraestrutura em `backend/infra/` (rede e disco; `algoritmos/` NUNCA importa daqui):

- `osm.py` — Overpass API, parser OSM → `Grafo`, poda ao componente
  fortemente conexo, serialização do artefato
- `importar_malha.py` — CLI: roda uma vez offline e gera `backend/dados/malha.json.gz`
  (versionado, contraído): **município de São Paulo inteiro**, 137 mil nós,
  6,8 mil semáforos, 7,6 MB. Fontes: `--pbf` (extrato, o que gerou o atual),
  Overpass em 12 blocos (padrão), `--reprocessar` (só contrai, sem rede)
- `pbf.py` — lê extrato `.osm.pbf` (pyosmium) e recorta pelo contorno do
  município (Nominatim), devolvendo o MESMO formato da Overpass. Dependências só
  da importação: `backend/requirements-importacao.txt`
- `preparar_alt.py` — CLI: gera `backend/dados/alt.bin` com os marcos do ALT
- `geocodificacao.py` — busca de lugares: Photon ao digitar, Nominatim só no Enter
- `migracoes.py` — migração ADITIVA no boot: acrescenta colunas que faltam
- `backend/tests/test_osm.py` — 29 testes, rodam sem rede (fixture embutido)

Camada de domínio em `backend/dominio/` (regras, sem HTTP e sem SQL bruto):

- `estados.py` — DAG do ciclo da corrida; Kahn valida no boot
- `registro.py` — posições dos motoristas em memória (não no banco)
- `servicos/avaliacao.py` — notas de 1 a 5 entre passageiro e motorista
- `servicos/corrida.py` — orquestra índice espacial → busca reversa → A*

Camada HTTP em `backend/api/` (FastAPI):

- `main.py` — app e `lifespan` (valida DAG, carrega malha, constrói reverso)
- `rotas/` — auth, motoristas, corridas, malha, lugares, viagens, ws · `conexoes.py` — WebSocket
- `eventos.py` — mensagens do WS e `comitar_e_publicar`
- `rotas/usuarios.py` — perfil (`/usuarios/eu`) e locais salvos (`/usuarios/eu/locais`)
- `rotas/publico.py` — acompanhamento sem login pelo link compartilhado (`/publico/acompanhar/{token}`)
- `backend/tests/`: `test_estados.py` (18), `test_api.py` (72), `test_ws.py` (15), `test_migracoes.py` (6)
- `matematica/tests/`: `test_matriz.py` (29) — matriz e semáforos; `test_quadtree.py` (23); `test_alt.py` (23); `test_contracao.py` (14)

Front-end ATUAL em `frontend/app/` (React + TypeScript + Vite, porta 5180) — ver `frontend/app/README.md`:

- `src/tipos.ts` espelha os contratos do backend; `src/api.ts` é o cliente tipado
- `src/mapa/onda.ts` — canvas que anima a ONDA da busca (A* e Dijkstra) e o cometa
- `src/telas/` — Entrada, Busca, Passageiro, Motorista · `src/ui/` — Bússola, Folha, Odômetro

Front-end ANTIGO em `frontend/web/` (React + Vite, JS, porta 5173), mantido até decisão do usuário:

- `src/api.js` — cliente HTTP e URL do WebSocket
- `src/componentes/` — Mapa (Leaflet), Bussola (rumo verdadeiro), painéis de
  passageiro e motorista, LinhaDeEstados (o DAG visualmente), TelaAutenticacao
- `src/estilos.css` — paleta de instrumento: cinza (aço), vermelho (agulha
  norte), verde natureza. Tema claro e escuro.
- `src/ganchos/usarCorridaAoVivo.js` — assina o WebSocket da corrida
- `e2e/fluxo.py` — teste ponta a ponta com Playwright, 20 verificações

Deploy: **front no Vercel, back no Railway**. Serverless não serve para o back
(sem WebSocket, sem processo persistente para o grafo em memória).

Mapa em `matematica/mapas/*.mapa` — matriz editável como texto, um caractere por célula:
`.` rua · `A` avenida · `S` semáforo · `> < ^ v` mão única · `#` intransponível.

Decisões que valem manter:

- A matriz descreve a **geografia** (NxM, uma célula por cruzamento); a lista de
  adjacência descreve a **conectividade**. Não confundir com matriz de
  adjacência (VxV), que mediu 1.067× mais memória e foi descartada.
- **Um caractere = uma célula, sem separador.** `"A A A"` produz avenida /
  quarteirão / avenida, não três avenidas. Para contíguas, `"AAA"`.
- O atraso do semáforo entra na aresta que **chega** ao cruzamento (é ali que
  se espera), nunca na que sai.
- Somar atraso só **aumenta** o custo real, então a heurística do A* continua
  admissível e consistente sem alteração. Testado.
- O atraso tem de estar no **peso da aresta**, não somado ao final: medido,
  **67%** das rotas mudam de traçado quando os semáforos entram no cálculo.
- Ordem de carga do mapa: artefato OSM → matriz → cidade sintética. Para usar
  a matriz com o artefato presente: `MALHA_ARQUIVO=` (vazio).
- O divisor da heurística é a velocidade máxima MEDIDA no grafo
  (`Grafo.velocidade_maxima_kmh`), não um teto fixo: a malha real tem marginal
  a 110 km/h, e o teto antigo de 100 tornava o A* inadmissível.
- `/viagens/estimativa` com `explorar` devolve a ordem de descoberta de cada
  busca (ordem de inserção de `distancias`). A* e Dijkstra são amostrados com o
  MESMO passo (`passo_comum`), senão a comparação visual mentiria.
- `tests/test_api.py` e `test_ws.py` **fixam** `MAPA_MATRIZ=__inexistente__`:
  testam a API, não qual mapa é o padrão do servidor.
- **Id de nó é INTEIRO**, igual ao do OpenStreetMap. A cidade sintética segue
  esse contrato (`no_da_celula`), e não o contrário.
- Endpoint que toca o grafo é `def`, **nunca** `async def`: Dijkstra e A* são
  CPU-bound e travariam o event loop. Com `def`, o FastAPI usa o threadpool.
- Toda mudança de estado passa por `servicos.corrida.transitar`, que valida
  contra o DAG e grava auditoria. Nenhuma rota altera `corrida.estado` direto.
- **Publicar no WebSocket só DEPOIS do commit.** Rotas de corrida não chamam
  `sessao.commit()`; chamam `api.eventos.comitar_e_publicar`, que impõe a
  ordem. Publicar antes faria o cliente ver estado que o rollback desfez.
- `CORS_ORIGENS` aceita `*` como curinga, para as prévias do Vercel (um
  endereço por branch e por commit): `https://app.vercel.app,https://app-*-equipe.vercel.app`.
  O `*` casa só `[a-z0-9-]+` — nunca ponto nem barra —, então não atravessa
  para outro domínio. Barra no fim de uma origem é ignorada (o navegador nunca
  a envia; já quebrou o deploy uma vez).
- Dependências que leem `app.state` usam `HTTPConnection`, **nunca** `Request`:
  em rota WebSocket o FastAPI injeta `WebSocket`, e anotar `Request` quebra só
  em tempo de execução, no primeiro cliente que tentar acompanhar.
- Alocação de motorista é otimista: `UPDATE ... WHERE disponivel = 1` e
  checagem de `rowcount`. Se deu zero, outro pedido levou — tenta o próximo.
- A quadtree é a implementação de produção; `IndiceLinear` permanece como
  **oráculo** nos testes (mesma estratégia do Dijkstra validando o A*).
- Quadtree exige **teto de profundidade**: pontos em coordenada idêntica
  subdividiriam para sempre, porque nenhuma divisão os separa.
- A poda por retângulo usa folga de 1% (`FOLGA_PODA`): o ponto mais próximo em
  graus é o mais próximo em metros só a menos da variação de cos(latitude)
  dentro do retângulo. Melhor visitar um ramo a mais que perder resultado.
- Consulta por raio é **O(log n + k)**, não O(log n) puro — k é a quantidade de
  resultados, e num raio fixo ela cresce com a densidade. A §6 da documentação
  técnica diz O(log n) e está **retificada** na Seção C (Proposição C.14).

Banco e migração:

- `create_all` cria tabelas novas, mas **não** acrescenta coluna a tabela que já
  existe. `infra/migracoes.py` roda no boot (em `criar_tabelas`) e faz
  `ALTER TABLE ... ADD COLUMN` só do que falta, com os índices. Nunca remove nem
  altera coluna: isso é Alembic. Idempotente; testado contra o esquema antigo.
- **Toda coluna nova em tabela existente tem de ser `nullable`** (ou ter
  `server_default`): as linhas antigas não têm valor. A migração recusa antes de
  alterar qualquer coisa, e o servidor não sobe.
- Média de notas é calculada com `AVG` na consulta, nunca guardada: guardar
  exigiria sincronizar a cada avaliação nova. Sem avaliação, a nota é `None`
  ("Novo"), não zero. Uma avaliação por autor por corrida (restrição no banco).
- Histórico pagina por **cursor** (`antes_de` = menor id recebido), não por
  offset: corrida nova no meio da rolagem não desloca nem repete itens.
- Pagamento (Pix, cartão, dinheiro) é **simulado**: fica gravado na corrida,
  nenhuma cobrança real acontece.

Paradas, chat e compartilhamento:

- Até **3 paradas**, em `corrida_paradas` (tabela própria, com o nó ancorado).
  Com a ordem fixa, o caminho mínimo é **exatamente** a concatenação dos mínimos
  de cada trecho (`rota_por_paradas`): um A* por trecho, cada um com a
  heurística apontando para o fim DAQUELE trecho. Teste: total = soma dos
  trechos; o Dijkstra confere cada um. Prévia, pedido e `/rota` usam a mesma
  função.
- Chat só em `alocacao`, `rota` e `em_curso`; depois vira histórico (só
  leitura). A mensagem é gravada e SÓ DEPOIS publicada no WebSocket da corrida
  (evento `mensagem`), a mesma regra das transições.
- Link de acompanhamento: token **aleatório** (`secrets.token_urlsafe(16)`, com
  índice único), não derivado do id. Só o passageiro gera e vê. A página pública
  mostra o mínimo (primeiro nome, carro, placa, posição, trajeto) e consulta a
  cada 5 s — o WebSocket exige token de quem está na corrida. Encerrada, para de
  mostrar posição.
- Com paradas, o servidor não sabe quais já foram visitadas: o link mostra o
  trajeto planejado e **não** inventa tempo restante.

Decisões do front-end:

- **`layoutId` dentro da folha prende a troca de fase.** A `Folha` usa
  `AnimatePresence mode="wait"`; um elemento de layout compartilhado
  (`layoutId`) no conteúdo que sai faz a saída nunca terminar, e a fase seguinte
  não entra (a folha fica vazia). Foi o destaque do seletor de pagamento:
  destaque em CSS. O `layoutId="caixa-busca"` é a exceção que funciona, porque
  tem par na tela de busca — e só na busca da VIAGEM (dois campos).
- Pelo mesmo motivo, os cartões de categoria **não** têm a prop `layout`: a
  lista remonta a cada nova estimativa (parada nova, origem e destino trocados),
  e um componente `layout` remontado prendia a saída da folha. Esse defeito
  existia antes das paradas: trocar origem e destino e confirmar abria uma folha
  vazia. Teste no navegador antes de pôr `layout`/`layoutId` dentro da `Folha`.

- O fluxo segue o dos apps de corrida (estilo Uber), com a identidade do
  TrueCompass: tela inicial é UMA pergunta ("Para onde?") + recentes; a prévia
  é a escolha de **categoria** (Econômico ×1,00 · Conforto ×1,35 · Grande ×1,60,
  em `dominio/servicos/corrida.py`, `CATEGORIAS`) com botão fixo na base e a
  folha limitada a 68% da tela para a rota caber no mapa.
- O multiplicador da categoria incide sobre a tarifa inteira; a rota é a mesma.
  No protótipo todo motorista atende as três categorias — por isso o tempo de
  chegada é igual nos três cartões, e a tela diz isso.
- A categoria entra no cálculo de `custo_estimado` no pedido e é gravada em
  `corridas.categoria` (junto com `forma_pagamento` e os endereços em texto),
  para o histórico. As colunas entram pela migração aditiva.
- Mapa limpo: tiles em **tons de cinza**, sem semáforos e sem malha por padrão
  (opção "Malha e semáforos" no menu). A única coisa colorida é a rota. Se os
  tiles falharem, a malha volta como fundo, mas sem os semáforos.
- Cartão do motorista mostra **corridas concluídas** (`motorista_corridas`), dado
  real, no lugar de uma nota que o protótipo não coleta.
- Painel do motorista: botão redondo Iniciar/Pausar e ganhos do dia
  (`/motoristas/resumo`), que somam **só pagamentos** — o dinheiro entra depois
  de `concluida → paga`, a mesma regra do DAG. "Hoje" é no fuso de SP (UTC−3
  fixo, sem depender do tzdata da imagem).

- O mapa desenha a malha vinda de `/malha/trechos`; os tiles do OSM são pano
  de fundo **opcional** e a camada é removida após 8 falhas seguidas.
- Marcadores são `circleMarker` (SVG) ou `divIcon` (HTML/CSS), **nunca** os
  ícones padrão do Leaflet: eles quebram sob bundler por causa do caminho
  relativo das imagens.
- Tiles: os da **CARTO passaram a exigir chave de API** (aparecem com marca
  d'água). Use os tiles padrão do OpenStreetMap; tema escuro = filtro CSS de
  inversão sobre eles. O front antigo (`frontend/web/`) ainda aponta para a CARTO.
- **`AnimatePresence mode="wait"` na troca de telas do App trava**: a tela de
  saída anima até opacidade 0 e nunca é desmontada. Use modo simultâneo com
  telas `position: absolute`. O `frontend/web/src/App.jsx` antigo ainda tem esse defeito
  (é por isso que o painel do motorista não abria lá).
- Mola (spring) em `filter: blur()` passa de zero → blur negativo inválido.
- O carimbo do `requestAnimationFrame` pode ser ANTERIOR ao `performance.now()`
  lido ao iniciar uma animação: prenda o tempo decorrido em zero.
- A malha sai em **duas** camadas `L.polyline` multi-segmento (mão única e mão
  dupla), não uma por rua — uma camada por rua trava o navegador.
- O painel do motorista envia **batida de GPS a cada 4s** enquanto online. Sem
  isso ele nunca descobre a corrida, porque é a resposta de `/motoristas/posicao`
  que informa `corrida_ativa`.
- Em desenvolvimento o front chama `/api/...` e o proxy do Vite encaminha
  (inclusive WebSocket, com `ws: true`). Sem CORS, sem URL absoluta no código.
- O teste E2E exige **banco limpo**: motoristas online de execuções anteriores
  competem no pareamento e deixam o teste instável. O script detecta e explica.
- **`ss -lptn` não enxerga os PIDs neste ambiente** — matar servidor "por
  porta" falha em silêncio e deixa instâncias duplicadas do Vite. Use
  `ps -eo pid,args` e mate pelo PID. Suba o Vite com `--strictPort` para ele
  falhar em vez de escorregar para 5174.
- Padrão de `pkill -f` amplo (ex.: `"vite"`) casa com o **próprio comando do
  shell** e mata a sessão. Use padrões que não possam se auto-casar.
- A agulha da bússola mostra o **azimute inicial** (grande círculo), não o rumo
  constante: de (0,0) a (10,10) são 44,56°, e não 45°. Mesma geometria esférica
  do haversine.
- A rotação da agulha é **acumulada**: de 350° para 10° ela gira +20°, não
  −340°. Sem isso a animação volta pelo caminho longo.

Decisões do ALT:

- Na malha real de SP o A* com haversine ganha só **1,37×** do Dijkstra: o
  `v_max` de 110 km/h é imposto por 8 arestas de marginal, e a rua mediana tem
  30 km/h. Com ALT o ganho vai a **14,3×** (157 ms → 16 ms por rota).
- As tabelas são **float64, nunca float32**. Medido: com float32 o limite supera
  o custo real em 2e-6 relativo, porque a admissibilidade depende de uma
  SUBTRAÇÃO e a diferença herda o arredondamento das duas pontas.
- `d(v, L)` vem de busca no grafo **reverso** — a dualidade da Proposição C.7,
  a mesma já usada no pareamento.
- Marcos na **periferia**, por seleção do ponto mais distante. Marco no centro
  fica "entre" origem e destino e seu limite vira quase zero.
- **Marcos ativos**: avaliar 16 marcos por chamada de `h` custa caro em Python
  e anularia o ganho. Na consulta escolhemos os 4 melhores para aquele par.
- O artefato carrega **impressão digital** do conjunto de vértices, conferida
  no boot. Sem ela, um `alt.bin` de outra malha seria usado em silêncio e o A*
  devolveria rota subótima sem erro algum.
- Sem `backend/dados/alt.bin` o sistema **continua correto**, caindo na haversine.

- Pesos do grafo são **tempo em segundos**, não distância.
- A heurística do A* precisa ser dividida pela velocidade máxima para continuar
  admissível. O Dijkstra serve de **oráculo** para validar o A* nos testes.
- Busca multi-alvo usa `h=None` (Dijkstra); a função recusa heurística com mais
  de um alvo de propósito.
- Malha vinda do OSM **precisa** ser podada ao componente fortemente conexo:
  extrato por caixa delimitadora sempre traz fragmentos soltos e armadilhas de
  mão única. A poda reusa o grafo reverso (passo central do Kosaraju).
- O servidor **não** consulta a Overpass no boot. Lê `backend/dados/malha.json.gz`, gerado
  offline pelo CLI. `dados/` não é versionado com dados de teste.

Decisões da contração (malha da cidade inteira):

- **79%** dos nós do OSM são de passagem (2 vizinhos, sem semáforo): só desenham a
  curva. Cada cadeia vira UMA aresta com o peso somado — o caminho mínimo entre
  nós mantidos é **exatamente** o mesmo (oráculo Dijkstra nos testes, inclusive na
  malha real). Medido na malha central: 118 mil → 26,6 mil nós; estimativa de
  rota de 620 ms → 128 ms (haversine) e ~1 ms com ALT.
- Cadeias são partidas a cada **250 m**: a quadtree só enxerga nós, e sem o corte
  quem pede corrida no meio de um viaduto seria ancorado a um cruzamento longe.
- Semáforos **nunca** são contraídos: a contagem de sinais por rota e o desenho
  se ancoram neles.
- A heurística continua admissível sem mudança: a corda entre as pontas de uma
  cadeia é ≤ ao comprimento dela, então nenhuma aresta contraída parece mais
  rápida que a rua real.
- A forma da rua fica em `Geometria` (microgaus em `array('i')`, mão dupla
  compartilha o mesmo array). É usada para **desenhar** a rota e os trechos e
  para **medir metros** (a tarifa cobra por km) — nunca pela busca.
- `/malha/trechos` consulta a **quadtree** (`no_retangulo`), não varre a malha:
  com a cidade inteira, O(V) por arrastar de mapa travaria o servidor.
  `/malha/info` é calculado uma vez no boot.
- O artefato `.gz` é **determinístico** (`gzip.compress(mtime=0)`): o mesmo grafo
  gera os mesmos bytes e o git não acusa mudança à toa.

Decisões da malha da cidade inteira:

- A Overpass (e a Geofabrik) **derrubam a conexão** vinda do datacenter onde a
  malha é gerada. A fonte passou a ser o extrato `.osm.pbf` do estado na OSM
  França (`download.openstreetmap.fr/extracts/south-america/brazil/southeast/`),
  lido com pyosmium em ~25 s. A BBBike não tem São Paulo.
- O recorte imita a Overpass com área: entra toda via trafegável que tem **pelo
  menos um nó** dentro do contorno do município (relação 298285, via Nominatim),
  com TODOS os nós — a rua não é cortada na divisa.
- Medido em SP inteira: 650 mil nós → poda 644 mil → contração **137 mil**
  (21%). Oráculo: custos idênticos para 2 × 137 mil destinos. Importação em 57 s
  com pico de 1,5 GB (offline).
- No servidor: boot ~3 s, ~400 MB de RAM. ALT 11,1× sobre o Dijkstra, ~19 ms
  por rota (haversine: ~148 ms), 0 rotas subótimas. `alt.bin` de 36 MB, gerado
  no build.
- `/malha/info` devolve como centro a **mediana** dos nós, não o meio da caixa:
  a cidade vai até Marsilac, e o meio da caixa cairia na zona sul.
- Os semáforos (6,8 mil) chegam **depois** da informação da malha, sem segurar
  a abertura do app — só aparecem com "Malha e semáforos" ligado.
