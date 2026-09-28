# TrueCompass — Backend

## Requisitos

Python 3.11 ou superior.

## Instalação

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Rodar os testes

Não precisa de pytest, banco nem rede — cada arquivo roda sozinho:

```bash
python3 tests/test_algoritmos.py   # 15 — Dijkstra, A*, pareamento reverso
python3 tests/test_quadtree.py     # 20 — índice espacial
python3 tests/test_osm.py          # 18 — parser OpenStreetMap
python3 tests/test_estados.py      # 18 — Kahn e DAG da corrida
python3 tests/test_api.py          # 18 — ciclo completo via HTTP
python3 tests/test_ws.py           # 14 — tempo real
```

Todos de uma vez:

```bash
for t in algoritmos quadtree osm estados api ws; do python3 tests/test_$t.py; done
```

## Ver os algoritmos comparados

```bash
python3 -m algoritmos.demo
```

Mede Dijkstra × A\*, pareamento ingênuo × reverso, e varredura linear × quadtree.

## Subir o servidor

```bash
export JWT_SECRET="qualquer-coisa-em-desenvolvimento"
uvicorn api.main:app --reload
```

- API: http://127.0.0.1:8000
- **Documentação interativa: http://127.0.0.1:8000/docs** — dá para testar todos
  os endpoints pelo navegador, sem Postman
- Saúde: http://127.0.0.1:8000/saude

Sem `dados/malha.json`, o servidor sobe com a **cidade sintética** (1.600
cruzamentos) e avisa no log. Serve para desenvolver tudo antes de ter a malha
real.

## Importar a malha real do OpenStreetMap

```bash
python3 -m infra.importar_malha --sul -23.560 --oeste -46.600 \
                                --norte -23.540 --leste -46.570
```

Roda **uma vez**, offline, e gera `dados/malha.json`. O servidor lê esse
arquivo no boot — nunca consulta a Overpass em produção.

Comece com uma área pequena (um bairro). Caixas grandes demoram e a Overpass
pode recusar.

## Variáveis de ambiente

Copie `.env.exemplo` para `.env`. Só `JWT_SECRET` é realmente obrigatória em
desenvolvimento; o resto tem padrão razoável.

## Organização das pastas

```
algoritmos/   matemática pura — não importa FastAPI nem SQL
dominio/      regras de negócio — não importa HTTP
api/          camada HTTP (FastAPI)
infra/        banco, rede, segredos
tests/        um arquivo por camada
```

A regra: **as setas de dependência apontam sempre para dentro**. `algoritmos/`
não conhece ninguém, e é por isso que seus testes rodam sem banco e sem
servidor.

Leia `algoritmos/EXPLICACAO.md` para entender os algoritmos em linguagem
simples, e `CLAUDE.md` para as decisões de projeto que valem manter.

## Deploy

- **Back-end → Railway.** `Procfile` e `railway.json` prontos, health check em
  `/saude`. Adicione o plugin MySQL e defina `JWT_SECRET` e `CORS_ORIGENS`.
- **Front-end → Vercel.**

Mantenha `--workers 1`: cada worker carrega sua própria cópia do grafo em
memória, e o GIL não paraleliza a busca mesmo.
