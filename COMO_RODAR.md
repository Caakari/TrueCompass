# TrueCompass — como rodar

O repositório tem três partes (ver `INDICE.md`):

```
frontend/     app (React + TypeScript) e web (versão anterior)
backend/      servidor FastAPI
matematica/   algoritmos puros e o mapa em matriz
```

Todos os comandos abaixo partem da **raiz** do repositório, salvo indicação.

## Requisitos

- Python 3.11 ou superior (backend e matemática)
- Node.js 20 ou superior (front-end)

## Instalação do backend

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt    # a raiz aponta para backend/requirements.txt
```

## Rodar os testes

Não precisa de pytest, banco nem rede — cada arquivo roda sozinho:

```bash
python3 matematica/tests/test_algoritmos.py   # 19 — Dijkstra, A*, pareamento reverso
python3 matematica/tests/test_quadtree.py     # 23 — índice espacial
python3 matematica/tests/test_contracao.py    # 14 — contração da malha
python3 matematica/tests/test_matriz.py       # 29 — matriz do mapa e semáforos
python3 backend/tests/test_osm.py             # 29 — parser OpenStreetMap
python3 backend/tests/test_estados.py         # 18 — Kahn e DAG da corrida
python3 backend/tests/test_api.py             # 80 — ciclo completo via HTTP
python3 backend/tests/test_migracoes.py       # 6 — migração aditiva do banco
python3 backend/tests/test_ws.py              # 16 — tempo real
```

Todos de uma vez:

```bash
for t in algoritmos quadtree matriz; do python3 matematica/tests/test_$t.py; done
for t in osm estados api ws;        do python3 backend/tests/test_$t.py; done
```

## Ver os algoritmos comparados

```bash
cd matematica && python3 -m algoritmos.demo
```

Mede Dijkstra × A\*, pareamento ingênuo × reverso, e varredura linear × quadtree.

## Subir o servidor

```bash
export JWT_SECRET="qualquer-coisa-em-desenvolvimento"     # Windows: $env:JWT_SECRET="..."
uvicorn --app-dir backend api.main:app --reload
```

(ou, de dentro de `backend/`: `uvicorn api.main:app --reload`)

- API: http://127.0.0.1:8000
- **Documentação interativa: http://127.0.0.1:8000/docs** — dá para testar todos
  os endpoints pelo navegador, sem Postman
- Saúde: http://127.0.0.1:8000/saude

O servidor carrega, nesta ordem: a malha real (`backend/dados/malha.json.gz`), o
mapa em matriz (`matematica/mapas/centro.mapa`) ou, sem nenhum dos dois, a
cidade sintética. Os caminhos funcionam de qualquer pasta de onde ele for
iniciado. Para usar a matriz com a malha presente: `MALHA_ARQUIVO=` (vazio).

## Subir o app

Com o backend no ar:

```bash
cd frontend/app
npm install
npm run dev            # http://localhost:5180
```

O front anterior continua em `frontend/web` (`npm run dev`, porta 5173).

## Importar a malha real do OpenStreetMap

O artefato atual cobre o **município de São Paulo inteiro** e saiu de um
extrato `.osm.pbf` (a Overpass recusa conexões de vários datacenters):

```bash
cd backend
pip install -r requirements-importacao.txt
curl -o dados/osm_bruto/sao-paulo-latest.osm.pbf \
  https://download.openstreetmap.fr/extracts/south-america/brazil/southeast/sao-paulo-latest.osm.pbf
python3 -m infra.importar_malha --pbf dados/osm_bruto/sao-paulo-latest.osm.pbf
```

Leva ~1 minuto (pico de 1,5 GB de RAM). O contorno do município é baixado do
Nominatim na primeira vez. Pela Overpass, quando ela aceita a conexão:

```bash
python3 -m infra.importar_malha                # município de São Paulo, em 12 blocos
```

Roda **uma vez**, offline, e gera `backend/dados/malha.json.gz` (versionado). O
servidor lê esse arquivo no boot — nunca consulta a Overpass em produção.

A cidade é baixada em 12 blocos, cada um recortado pelo limite do município
(relação 298285 do OSM), com cache por bloco em `backend/dados/osm_bruto/`: se
um bloco falhar, rodar de novo não baixa os outros. Depois da poda ao
componente fortemente conexo, os nós de passagem são **contraídos** (ver
`matematica/algoritmos/contracao.py`).

Outras formas:

```bash
python3 -m infra.importar_malha --sul -23.56 --oeste -46.66 --norte -23.54 --leste -46.63
python3 -m infra.importar_malha --reprocessar dados/malha.json   # sem rede: só contrai
```

## Acelerar o cálculo de rota (ALT)

Depois de importar a malha, pré-calcule os marcos:

```bash
cd backend
python3 -m infra.preparar_alt --marcos 16
```

Roda uma vez (segundos, na malha contraída) e grava `backend/dados/alt.bin`.
O servidor carrega no boot e o cálculo de rota fica **14× mais rápido** —
157 ms para 16 ms por rota.

Sem o arquivo o sistema continua correto, usando a heurística haversine.
Se a malha mudar, **regere**: o artefato traz impressão digital e um arquivo
desatualizado é recusado no boot, com aviso no log.

## Variáveis de ambiente

Copie `backend/.env.exemplo` para `backend/.env`. Só `JWT_SECRET` é realmente
obrigatória em desenvolvimento; o resto tem padrão razoável. Caminhos
relativos (como `MALHA_ARQUIVO`) partem de `backend/`.

### Login: e-mail com código e "Continuar com Google"

Sem nada configurado, o login funciona como antes: o cadastro abre a conta na
hora e o "Continuar com Google" avisa que não está configurado. Em
desenvolvimento, `EMAIL_MODO=log CONFIRMAR_EMAIL=1` liga a confirmação e
escreve o código no log do servidor.

- **E-mail (código de 6 dígitos), recomendado:** Brevo. Crie a conta em brevo.com,
  confirme o e-mail remetente em *Senders* e gere a chave em *SMTP & API → API Keys*.
  No Railway: `BREVO_API_KEY` e `EMAIL_REMETENTE=TrueCompass <seu-remetente@gmail.com>`.
  Não exige domínio próprio e envia por API (funciona onde o SMTP é bloqueado).
  Em *Security → Authorised IPs*, desative o bloqueio por IP: o Railway muda de IP
  e a Brevo recusaria o envio ("unrecognised IP address" no log).
- **E-mail, alternativa:** defina `RESEND_API_KEY` no Railway (conta
  grátis em resend.com, até 100 e-mails/dia). Sem domínio próprio verificado na
  Resend, ela só entrega no e-mail do dono da conta — para testar basta; para
  todo mundo, verifique um domínio e ajuste `EMAIL_REMETENTE`. Com e-mail
  configurado, a confirmação no cadastro liga sozinha.
- **Google:** no Google Cloud Console → APIs e serviços → Credenciais → Criar
  credenciais → ID do cliente OAuth → "Aplicativo da Web". Em "Origens
  JavaScript autorizadas", ponha o domínio do Vercel (e `http://localhost:5180`
  para testar). Copie o ID para `GOOGLE_CLIENT_ID` (Railway) **e**
  `VITE_GOOGLE_CLIENT_ID` (Vercel) — é o mesmo valor, e não é segredo.

## Organização das pastas

```
matematica/algoritmos/   matemática pura — não importa FastAPI nem SQL
backend/dominio/         regras de negócio — não importa HTTP
backend/api/             camada HTTP (FastAPI)
backend/infra/           banco, rede, segredos
frontend/app/            interface (React + TypeScript)
```

A regra: **as setas de dependência apontam sempre para dentro**.
`matematica/` não conhece ninguém, e é por isso que seus testes rodam sem banco
e sem servidor. O backend encontra a pasta `matematica/` sozinho, por
`backend/matematica_no_caminho.py`.

Leia `matematica/algoritmos/EXPLICACAO.md` para entender os algoritmos em
linguagem simples, e `CLAUDE.md` para as decisões de projeto que valem manter.

## Deploy

- **Back-end → Railway**, com a **raiz** do repositório (o backend importa
  `matematica/`). `Procfile` e `railway.json` da raiz já apontam para
  `backend/`; o `requirements.txt` da raiz traz as dependências completas (o
  Railpack só enxerga ele na hora do pip). Health check em `/saude`.
  `CORS_ORIGENS` aceita `*` para as prévias do Vercel, separado por vírgula:
  `https://prototipo-truecompass-frontend.vercel.app,https://prototipo-truecompass-frontend-*-product-kauan.vercel.app`. Adicione o plugin MySQL e
  defina `JWT_SECRET` e `CORS_ORIGENS`.
- **Front-end → Vercel**, diretório raiz `frontend/app`, com `VITE_API_URL`
  apontando para o backend.

Mantenha `--workers 1`: cada worker carrega sua própria cópia do grafo em
memória, e o GIL não paraleliza a busca mesmo.
