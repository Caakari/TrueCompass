"""Mede Dijkstra x A* (haversine) x A* (ALT) na malha da cidade inteira:
nós expandidos e tempo por rota, nos mesmos pares, e se o custo bate."""
import os, random, statistics, sys, time
RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(RAIZ, "backend"))
import matematica_no_caminho  # noqa
from algoritmos.alt import ALT
from algoritmos.busca import busca_caminho_minimo
from algoritmos.grafo import heuristica_haversine
from infra.osm import carregar_grafo

grafo = carregar_grafo(os.path.join(RAIZ, "backend", "dados", "malha.json.gz"))
grafo.reverso()
alt = ALT.carregar(os.path.join(RAIZ, "backend", "dados", "alt.bin"))
assert alt.confere(grafo), "alt.bin de outra malha"
rng = random.Random(2026)
nos = sorted(grafo.nos)
res = {k: {"nos": [], "ms": []} for k in ("Dijkstra", "A* haversine", "A* ALT")}
diverg = usados = 0
while usados < 30:
    o, d = rng.sample(nos, 2)
    t = time.perf_counter(); base = busca_caminho_minimo(grafo, o, {d}); tb = time.perf_counter() - t
    if d not in base.custos:
        continue
    usados += 1
    res["Dijkstra"]["nos"].append(base.nos_expandidos); res["Dijkstra"]["ms"].append(tb * 1000)
    for nome, h in (("A* haversine", heuristica_haversine(grafo, d)), ("A* ALT", alt.heuristica(d, origem=o))):
        t = time.perf_counter(); r = busca_caminho_minimo(grafo, o, {d}, h=h); dt = time.perf_counter() - t
        res[nome]["nos"].append(r.nos_expandidos); res[nome]["ms"].append(dt * 1000)
        if abs(r.custos[d] - base.custos[d]) > 1e-6 * base.custos[d]:
            diverg += 1
print("nós no grafo:", len(grafo.nos), "| pares:", usados, "| rotas com custo diferente do Dijkstra:", diverg)
for k, v in res.items():
    print(f"{k:13s} nós médios {statistics.mean(v['nos']):>10.0f}  ms médio {statistics.mean(v['ms']):7.1f}  ms mediana {statistics.median(v['ms']):7.1f}")
dj, al = statistics.mean(res["Dijkstra"]["nos"]), statistics.mean(res["A* ALT"]["nos"])
print("redução de nós ALT/Dijkstra:", round(dj / al, 1), "| tempo:", round(statistics.mean(res["Dijkstra"]["ms"]) / statistics.mean(res["A* ALT"]["ms"]), 1))
