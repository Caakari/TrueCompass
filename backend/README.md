# backend/

Servidor FastAPI: corridas, motoristas, pagamentos, busca de lugares e tempo
real. Usa os algoritmos de `../matematica/` (ligação em `matematica_no_caminho.py`).

| Pasta | Camada |
|---|---|
| `api/` | HTTP e WebSocket |
| `dominio/` | regras de negócio: DAG da corrida, pareamento, prévia da viagem |
| `infra/` | banco, OpenStreetMap, busca de lugares, segredos |
| `dados/` | `malha.json.gz` — ruas reais de São Paulo (contraídas), lidas no boot |
| `tests/` | 92 testes, sem pytest |

Da raiz do repositório:

```bash
uvicorn --app-dir backend api.main:app --reload
for t in osm estados api ws; do python3 backend/tests/test_$t.py; done
```
