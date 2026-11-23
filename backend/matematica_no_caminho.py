# -*- coding: utf-8 -*-
"""Poe a pasta `matematica/` no caminho de importacao do Python.

O projeto separa as camadas em pastas irmas:

    backend/      api, dominio, infra  -- HTTP, regras, rede e disco
    matematica/   algoritmos           -- grafo, A*, quadtree, matriz do mapa
    frontend/     app, web             -- React

O backend USA a matematica (`from algoritmos.busca import ...`), mas ela nao
mora dentro dele -- e de proposito: `algoritmos/` nao conhece ninguem e seus
testes rodam sem banco e sem servidor. A seta de dependencia continua
apontando para dentro, so que agora atravessa uma pasta.

Os pacotes `api`, `dominio` e `infra` importam este modulo no `__init__`,
entao basta o backend estar no caminho (uvicorn --app-dir backend, ou rodar
de dentro de backend/) para `algoritmos` ser encontrado.
"""

import os
import sys

PASTA_BACKEND = os.path.dirname(os.path.abspath(__file__))
PASTA_RAIZ = os.path.dirname(PASTA_BACKEND)
PASTA_MATEMATICA = os.path.join(PASTA_RAIZ, "matematica")

if PASTA_MATEMATICA not in sys.path:
    sys.path.insert(0, PASTA_MATEMATICA)
