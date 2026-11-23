# matematica/

O cérebro do TrueCompass, em Python puro: não importa FastAPI, banco nem rede —
por isso os testes rodam sozinhos, em segundos.

| Pasta | O que é |
|---|---|
| `algoritmos/` | grafo, Dijkstra e A\*, pareamento reverso, quadtree, Kahn, matriz do mapa, semáforos |
| `algoritmos/EXPLICACAO.md` | os algoritmos em linguagem simples |
| `algoritmos/MATEMATICA.md` | as fórmulas: de onde vieram e o que quebra se mexer |
| `mapas/centro.mapa` | o mapa em matriz, editável como texto (um caractere por célula) |
| `tests/` | 68 testes, sem pytest |

Da raiz do repositório:

```bash
for t in algoritmos quadtree matriz; do python3 matematica/tests/test_$t.py; done
cd matematica && python3 -m algoritmos.demo      # comparativo medido
```
