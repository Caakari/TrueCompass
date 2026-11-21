# Banner do TrueCompass — versão 2 (enxuta)

Versão com **pouco texto**: tópicos curtos, números grandes e o mapa real de São
Paulo ao fundo (as ruas da malha do app, com a rota USJT Mooca → Praça da Sé e os
semáforos do caminho). A versão completa, com contexto, objetivos e referências,
continua em `../banner_truecompass.pdf`.

| | |
|---|---|
| Arquivo para impressão | `banner_truecompass_v2.pdf` — **90 cm × 120 cm**, retrato, vetorial |
| Prévia | `previa.png` |
| Gerador | `gerar.py` (HTML) + `renderizar.js` (PDF via Playwright) |

Segue a mesma especificação da disciplina da versão 1: Montserrat, título em
80 pt, títulos de seção em 40 pt, texto entre 21 e 25 pt — nada abaixo de 20 pt
(medido no documento renderizado). O QR do rodapé leva ao repositório no GitHub,
conferido decodificando o PDF já gerado.

## Gerar de novo

```bash
python3 -m pip install qrcode
python3 docs/banner/v2/gerar.py
node docs/banner/v2/renderizar.js docs/banner/v2/banner.html docs/banner/v2/banner_truecompass_v2.pdf
```

O `renderizar.js` imprime onde cada bloco termina, em cm: `conteudo_fim` tem de
ficar abaixo de `rodape_inicio`, senão os celulares invadem o rodapé.

## De onde vêm os números

| Número | Origem (`CLAUDE.md`) |
|---|---|
| 137 mil cruzamentos | malha do município inteiro, depois da contração |
| 11× mais rápido | A* com ALT sobre o Dijkstra, na malha real |
| 19 ms por rota | tempo médio do A* com ALT no servidor |
| 67% das rotas mudam | rotas que trocam de traçado quando os semáforos entram no peso |
| 6,8 mil semáforos | semáforos do OpenStreetMap na malha |

As capturas em `capturas/` são do app atual (mapa vetorial, login novo, oferta
ao motorista), a 3× de densidade, com os créditos do mapa ocultos — o crédito ao
OpenStreetMap, OpenMapTiles e OpenFreeMap está no rodapé do banner.
