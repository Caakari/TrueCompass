# TrueCompass — índice do projeto

Mapa de onde está cada coisa. Projeto acadêmico de Matemática Computacional
Aplicada (USJT).

```
Prototipo-TrueCompass/
├── frontend/      o que roda no celular/navegador (React)
│   ├── app/            ATUAL — React + TypeScript, animações
│   ├── web/            anterior — React + JavaScript
│   └── prototipo_html/ protótipo visual original do squad
├── backend/       servidor (FastAPI): HTTP, regras de negócio, banco, rede
│   ├── api/  dominio/  infra/
│   ├── dados/          malha real de São Paulo (OpenStreetMap)
│   └── tests/
├── matematica/    os algoritmos puros: grafo, A*, quadtree, matriz do mapa
│   ├── algoritmos/
│   ├── mapas/          o mapa em matriz (texto editável)
│   └── tests/
└── docs/          documentação formal (PDF) e material da disciplina
```

As setas de dependência apontam **para dentro**: `frontend` fala com o
`backend` só por HTTP/WebSocket; o `backend` usa a `matematica`; e a
`matematica` não conhece ninguém — por isso seus testes rodam sem banco, sem
servidor e sem rede. O backend acha a pasta `matematica/` sozinho
(`backend/matematica_no_caminho.py`).

## Comece por aqui

| Arquivo | Para quê |
|---|---|
| `COMO_RODAR.md` | instalar, rodar os testes, subir o servidor e o app |
| `README.md` | visão do produto — o que o app faz, para quem usa |
| `CLAUDE.md` | decisões de projeto que valem manter (e as armadilhas) |
| `frontend/app/README.md` | o app novo: estrutura e o que cada animação representa |

## Aprendizado do squad

| Arquivo | Assunto |
|---|---|
| `matematica/algoritmos/EXPLICACAO.md` | os **algoritmos** em linguagem simples (A\*, busca reversa) |
| `matematica/algoritmos/MATEMATICA.md` | as **fórmulas**: de onde vieram e o que quebra se mexer |

## Documentação formal — `docs/`

| Arquivo | Conteúdo |
|---|---|
| `docs/Documentacao_App/TrueCompass_Documentacao_Tecnica.pdf` | doc original — seções 1 a 7 |
| `docs/Documentacao_App/TrueCompass_Secao_C_Fundamentacao_Matematica.pdf` | 9 definições, 14 proposições, 5 corolários, com demonstrações |
| `docs/Documentacao_App/TrueCompass_1a_Parcial_Relatorio_Executivo.pdf` | entrega da 1ª parcial, 8 seções |
| `docs/Documentacao_Aula/` | material da disciplina |

> A Seção C **retifica** a §6 da doc original: a consulta por raio na quadtree
> é O(log n + k), e não O(log n). Ver Proposição C.14.

## Matemática — `matematica/`

### `matematica/algoritmos/` — matemática pura

| Arquivo | O que faz |
|---|---|
| `grafo.py` | malha como grafo ponderado direcionado, grafo reverso, haversine, velocidade máxima medida |
| `busca.py` | Dijkstra e A\* na **mesma** rotina (Dijkstra ≡ A\* com h ≡ 0) |
| `matching.py` | pareamento reverso many-to-one — 1 busca em vez de k |
| `quadtree.py` | índice espacial com poda por retângulo |
| `indice_espacial.py` | varredura linear, mantida como **oráculo** dos testes |
| `topologica.py` | algoritmo de Kahn |
| `matriz_mapa.py` | mapa como matriz de células → grafo |
| `semaforo.py` | atraso esperado em cruzamento semaforizado, r²/2c |
| `contracao.py` | contração de nós de passagem; `Geometria` guarda a forma das ruas |
| `alt.py` | A\* + Landmarks + desigualdade Triangular: heurística 14× mais apertada na malha real |
| `cidade_exemplo.py` | cidade sintética (mão única, avenidas, rio com 2 pontes) |
| `demo.py` | comparativo medido — `cd matematica && python3 -m algoritmos.demo` |

### `matematica/mapas/centro.mapa` — o mapa em matriz

Matriz 36×36 editável como texto. Um caractere por célula:

| | |
|---|---|
| `.` | rua local, mão dupla |
| `A` | avenida, mais rápida |
| `S` | cruzamento semaforizado |
| `> < ^ v` | mão única |
| `#` | intransponível (quarteirão, rio, parque) |

O servidor usa a malha real do OpenStreetMap quando ela existe; para usar a
matriz, suba com `MALHA_ARQUIVO=` (vazio). O grafo é derivado dela no boot.

## Backend — `backend/`

### `backend/dominio/` — regras de negócio

| Arquivo | O que faz |
|---|---|
| `estados.py` | DAG do ciclo da corrida; Kahn valida no boot |
| `registro.py` | posições dos motoristas em memória (não no banco) |
| `servicos/corrida.py` | orquestra quadtree → busca reversa → A\*; prévia da viagem |

### `backend/api/` — camada HTTP (FastAPI)

| Arquivo | O que faz |
|---|---|
| `main.py` | app e `lifespan`: valida DAG, carrega malha, constrói reverso |
| `rotas/auth.py` | registro e login (JWT) |
| `rotas/motoristas.py` | ping de GPS, disponibilidade |
| `rotas/corridas.py` | ciclo da corrida |
| `rotas/lugares.py` | busca de endereços reais (Photon/Nominatim) |
| `rotas/viagens.py` | prévia: rota A\*, preço, ondas de busca A\* × Dijkstra |
| `rotas/malha.py` | geometria da malha e semáforos, para o mapa |
| `rotas/ws.py` | acompanhamento em tempo real |
| `conexoes.py` · `eventos.py` | WebSocket e `comitar_e_publicar` |
| `esquemas.py` · `deps.py` | contratos Pydantic e injeção de dependências |

### `backend/infra/` — banco, rede, segredos

| Arquivo | O que faz |
|---|---|
| `osm.py` | Overpass API, parser OSM, semáforos, poda ao componente fortemente conexo |
| `importar_malha.py` | CLI: gera `backend/dados/malha.json.gz` (município de SP, contraído) uma vez, offline |
| `preparar_alt.py` | CLI: gera `backend/dados/alt.bin` (marcos do ALT), derivado da malha |
| `geocodificacao.py` | busca de lugares, com cache e limite de taxa |
| `modelos.py` · `banco.py` | tabelas SQLAlchemy e sessão |
| `seguranca.py` | bcrypt e JWT |
| `config.py` | configuração via ambiente (caminhos relativos partem de `backend/`) |

## Testes — 213, sem pytest

```bash
for t in algoritmos quadtree matriz alt contracao; do python3 matematica/tests/test_$t.py; done
for t in osm estados api ws;        do python3 backend/tests/test_$t.py; done
```

| Arquivo | Qtd | Cobre |
|---|---:|---|
| `matematica/tests/test_algoritmos.py` | 19 | Dijkstra, A\*, pareamento reverso, velocidade máxima medida |
| `matematica/tests/test_quadtree.py` | 23 | índice espacial, poda, janela retangular, casos degenerados |
| `matematica/tests/test_matriz.py` | 29 | matriz do mapa, semáforos, mapa de produção |
| `matematica/tests/test_alt.py` | 23 | ALT: admissibilidade, consistência, artefato, impressão digital |
| `matematica/tests/test_contracao.py` | 14 | contração: oráculo Dijkstra, mão única, semáforo, corte de 250 m, traçado |
| `backend/tests/test_osm.py` | 28 | parser OSM, mão única, semáforos, poda, blocos, artefato .gz (sem rede) |
| `backend/tests/test_estados.py` | 18 | Kahn, DAG, transições proibidas |
| `backend/tests/test_api.py` | 45 | ciclo via HTTP, auth, concorrência, malha, prévia, categorias, lugares, resumo do motorista |
| `backend/tests/test_ws.py` | 14 | tempo real, isolamento entre corridas |

`frontend/web/e2e/fluxo.py` (Playwright) ainda usa a interface do front antigo.

## Front-end — `frontend/`

| Pasta | O que é |
|---|---|
| `frontend/app/` | **atual** — React + TypeScript. Busca real, onda do A\*, mapa OSM. Porta 5180 |
| `frontend/web/` | anterior — React + JavaScript. Porta 5173 |
| `frontend/prototipo_html/Front_End.html` | protótipo visual original do squad (a paleta veio dele) |

```bash
cd frontend/app && npm install && npm run dev      # http://localhost:5180
```

## Deploy

| Camada | Plataforma | Configuração |
|---|---|---|
| Back-end | **Railway** | raiz do repositório: `Procfile`, `railway.json`, `requirements.txt` (aponta para `backend/`) |
| Front-end | **Vercel** | diretório raiz `frontend/app`, variável `VITE_API_URL` |

O Railway precisa da RAIZ do repositório (e não só de `backend/`), porque o
backend importa `matematica/`. Serverless não serve para o backend: sem
WebSocket e sem processo persistente para manter o grafo em memória.
Mantenha `--workers 1`.

## Resultados medidos

| Substituição | Ganho | Otimalidade |
|---|---|---|
| k Dijkstras → 1 busca reversa | **10,7×** | preservada |
| Dijkstra → A\* | **3,2×** | preservada |
| Varredura linear → quadtree | **154,8×** | preservada |

Em nenhum dos três houve perda de otimalidade: a resposta é a **mesma**,
obtida com menos busca. Reproduza com `cd matematica && python3 -m algoritmos.demo`.
