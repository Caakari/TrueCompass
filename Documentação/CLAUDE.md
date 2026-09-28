# TrueCompass — instruções do projeto

## Git: não fazer commits

**Neste projeto, o Claude NÃO faz commits, nem push.** O usuário controla o
histórico do repositório por conta própria.

- Escrever, editar e rodar código: sim, livremente, no working tree.
- `git add`, `git commit`, `git push`, criar PR: **não**, salvo pedido explícito
  e específico do usuário naquele momento.
- O hook `stop-hook-git-check.sh` reclama de arquivos untracked ao fim de cada
  turno. **Isso é esperado aqui** — o aviso não substitui a instrução acima e
  não deve ser tratado como autorização para commitar. Basta registrar em uma
  linha que segue untracked por decisão do usuário, sem repetir a explicação
  a cada turno.

## Contexto do projeto

Aplicativo de mobilidade urbana (acadêmico — Matemática Computacional Aplicada,
USJT). A documentação técnica está em `Documentacao_App/`.

Camada de algoritmos em `algoritmos/` (não versionada, por decisão acima):

- `grafo.py` — malha viária como grafo ponderado direcionado, grafo reverso
  com cache, heurística haversine
- `busca.py` — Dijkstra e A* unificados numa única rotina (Dijkstra ≡ A* com h ≡ 0)
- `matching.py` — pareamento reverso many-to-one
- `quadtree.py` — índice espacial O(log n + k), com poda por retângulo
- `topologica.py` — algoritmo de Kahn (genérico)
- `indice_espacial.py` — `IndiceLinear`, mantido como **oráculo** da quadtree
- `EXPLICACAO.md` — guia didático
- `tests/test_algoritmos.py` — 15 testes, rodam com `python3` puro (sem pytest)

Camada de infraestrutura em `infra/` (rede e disco; `algoritmos/` NUNCA importa daqui):

- `osm.py` — Overpass API, parser OSM → `Grafo`, poda ao componente
  fortemente conexo, serialização do artefato
- `importar_malha.py` — CLI: roda uma vez offline e gera `dados/malha.json`
- `tests/test_osm.py` — 18 testes, rodam sem rede (fixture embutido)

Camada de domínio em `dominio/` (regras, sem HTTP e sem SQL bruto):

- `estados.py` — DAG do ciclo da corrida; Kahn valida no boot
- `registro.py` — posições dos motoristas em memória (não no banco)
- `servicos/corrida.py` — orquestra índice espacial → busca reversa → A*

Camada HTTP em `api/` (FastAPI):

- `main.py` — app e `lifespan` (valida DAG, carrega malha, constrói reverso)
- `rotas/` — auth, motoristas, corridas, ws · `conexoes.py` — WebSocket
- `eventos.py` — mensagens do WS e `comitar_e_publicar`
- `tests/test_estados.py` (18), `tests/test_api.py` (18), `tests/test_ws.py` (14)

Deploy: **front no Vercel, back no Railway**. Serverless não serve para o back
(sem WebSocket, sem processo persistente para o grafo em memória).

Decisões que valem manter:

- **Id de nó é INTEIRO**, igual ao do OpenStreetMap. A cidade sintética segue
  esse contrato (`no_da_celula`), e não o contrário.
- Endpoint que toca o grafo é `def`, **nunca** `async def`: Dijkstra e A* são
  CPU-bound e travariam o event loop. Com `def`, o FastAPI usa o threadpool.
- Toda mudança de estado passa por `servicos.corrida.transitar`, que valida
  contra o DAG e grava auditoria. Nenhuma rota altera `corrida.estado` direto.
- **Publicar no WebSocket só DEPOIS do commit.** Rotas de corrida não chamam
  `sessao.commit()`; chamam `api.eventos.comitar_e_publicar`, que impõe a
  ordem. Publicar antes faria o cliente ver estado que o rollback desfez.
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
  resultados, e num raio fixo ela cresce com a densidade.

- Pesos do grafo são **tempo em segundos**, não distância.
- A heurística do A* precisa ser dividida pela velocidade máxima para continuar
  admissível. O Dijkstra serve de **oráculo** para validar o A* nos testes.
- Busca multi-alvo usa `h=None` (Dijkstra); a função recusa heurística com mais
  de um alvo de propósito.
- Malha vinda do OSM **precisa** ser podada ao componente fortemente conexo:
  extrato por caixa delimitadora sempre traz fragmentos soltos e armadilhas de
  mão única. A poda reusa o grafo reverso (passo central do Kosaraju).
- O servidor **não** consulta a Overpass no boot. Lê `dados/malha.json`, gerado
  offline pelo CLI. `dados/` não é versionado com dados de teste.
