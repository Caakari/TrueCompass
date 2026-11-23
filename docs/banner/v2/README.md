# Banner do TrueCompass — Mostra de Trabalhos A3 (Expo São Judas 2026/2)

Feito conforme o **Guia Oficial: Como Elaborar o Banner** do Prof. Raulison
Resende. Pouco texto, em tópicos, e metade do espaço em recursos visuais
(diagramas, gráfico, telas, mapa real).

| | |
|---|---|
| Arquivo para impressão | `banner_truecompass_v2.pdf` — **90 cm × 120 cm**, retrato, vetorial, fontes embutidas |
| Prévia | `previa.png` |
| Gerador | `gerar.py` (HTML) + `renderizar.js` (PDF via Playwright) |
| Acabamento (guia) | lona ou papel fosco, canaleta plástica e cordão |

## Como segue o guia

| Pedido do guia | No banner |
|---|---|
| Logotipos da universidade e do curso | logotipo oficial da São Judas (`logos/logo-usjt.svg`, baixado de usjt.br) · o curso não tem logotipo próprio: placa com o nome |
| Título, autores, orientador, curso/campus/ano | cabeçalho: nomes completos, Prof. Raulison Resende, Análise e Desenvolvimento de Sistemas, Campus Santo Amaro, 2026/2 |
| Coluna esquerda: Contexto & Problema, Objetivos | 4 tópicos + diagrama "linha reta × pelas ruas"; objetivo geral e 5 específicos |
| Coluna central: Metodologia / Arquitetura com diagrama | fluxo "do mapa ao grafo", diagrama de camadas e a corrida passo a passo |
| Coluna direita: Resultados (gráfico, prints, indicadores) | gráfico Dijkstra × A* × A*+ALT, 4 indicadores, 3 telas do app |
| Considerações finais, 2-3 referências ABNT, QR Code | rodapé; o QR leva ao repositório do squad, github.com/Caakari/TrueCompass (conferido decodificando o PDF) |
| Título 60-80 pt · seções 36-44 pt · texto 24-30 pt · nunca < 20 pt | título 80 · seções 40 · texto 24-27 · legendas e referências 21-22 (medido no documento renderizado; o texto dentro do diagrama tem 22-23 pt) |

## Gerar de novo

```bash
python3 -m pip install qrcode
python3 docs/banner/v2/gerar.py
node docs/banner/v2/renderizar.js docs/banner/v2/banner.html docs/banner/v2/banner_truecompass_v2.pdf
```

O `renderizar.js` imprime onde termina cada coluna e onde começa o rodapé (em
cm) e avisa se alguma coluna invadir o rodapé.

## De onde vêm os números

`medir_algoritmos.py` roda os três algoritmos nos MESMOS 30 pares sorteados
(semente 2026) da malha da cidade inteira (136.891 cruzamentos), com o `alt.bin`
do projeto:

| Algoritmo | Cruzamentos visitados (média) | Tempo por rota |
|---|---:|---:|
| Dijkstra | 66.015 | 167 ms (média) |
| A* (linha reta) | 45.877 | 169 ms (média) |
| A* + ALT | 6.687 | 22 ms (mediana) · 29 ms (média) |

10× menos cruzamentos visitados, e **0** rotas com custo diferente do Dijkstra
(o oráculo). Os demais: 137 mil cruzamentos e 67% de rotas que mudam com os
semáforos estão no `CLAUDE.md`; 281 é o total das suítes de teste.

Mudou alguma medida? Atualize `MEDIDAS`, no alto do `gerar.py`.

## Capturas

`capturas/` tem as telas do app atual a 3× de densidade (1170 × 2532 px), com os
créditos do mapa ocultos na captura — o crédito ao OpenStreetMap e ao
OpenFreeMap está no rodapé do banner.
