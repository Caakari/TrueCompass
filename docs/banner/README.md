# Banner do TrueCompass

Banner do projeto para a Matemática Computacional Aplicada, no tamanho exato
pedido pela disciplina.

| | |
|---|---|
| Arquivo pronto para impressão | `banner_truecompass.pdf` |
| Dimensão | **90 cm × 120 cm**, retrato (2551,18 × 3401,58 pt — conferido com `pdfinfo`) |
| Prévia em imagem | `previa_banner.png` — não versionada; sai do `--previa` |
| Gerador | `gerar_banner.py` |
| Acabamento sugerido | lona ou papel fosco, bastão plástico e cordão |

## Antes de mandar imprimir — duas coisas faltam

1. **Os dois logotipos.** O topo tem dois retângulos pontilhados marcados
   `LOGOTIPO DA UNIVERSIDADE` e `LOGOTIPO DO CURSO`. Nenhum logotipo oficial
   está no repositório, então ficaram como espaço reservado: cole as imagens
   por cima (Canva, Figma, Illustrator ou o próprio PowerPoint, importando o
   PDF) ou aponte os caminhos no `gerar_banner.py`.
2. **O campus.** O cabeçalho traz `Campus ____________`. O campus não aparece
   em nenhum documento do projeto nem no plano de ensino — preencha a lacuna.

## Como está organizado

```
cabeçalho (faixa escura, largura inteira, rosa dos ventos de marca d'água)
    logotipos · etiqueta · TrueCompass · subtítulo · integrantes e RAs
    orientador · universidade · unidade curricular · campus · período letivo

coluna 1                  coluna 2                    coluna 3
O APLICATIVO              ARQUITETURA                 RESULTADOS
  o que o app faz           as 4 camadas                números medidos
CONTEXTO E PROBLEMA       COMO UMA CORRIDA ACONTECE   gráfico de nós expandidos
OBJETIVOS                   os 6 passos               O APP FUNCIONANDO
  geral e específicos     DA MATRIZ AO GRAFO            3 telas reais
                                                      INDICADORES DE ENTREGA

rodapé (cartão escuro, largura inteira)
    CONSIDERAÇÕES FINAIS e trabalhos futuros · REFERÊNCIAS · QR do repositório
```

A leitura corre da esquerda para a direita e de cima para baixo, como pede a
especificação. O QR do rodapé aponta para
`https://github.com/Cm-Kauan/Prototipo-TrueCompass` — conferido decodificando o
PDF já renderizado, não só o dado de entrada.

## Tipografia

Montserrat, nos corpos exigidos:

| Elemento | Tamanho |
|---|---|
| Título | 80 pt |
| Títulos de seção | 36 a 40 pt |
| Corpo e bullets | 21 a 25 pt |
| Legendas, etiquetas e notas | 21 a 22 pt |

Nada abaixo de 20 pt, inclusive nas legendas das capturas.

## Gerar de novo

```bash
python3 -m pip install reportlab qrcode pillow fonttools
python3 docs/banner/gerar_banner.py --previa
```

O script imprime, no fim, onde cada coluna termina e quanta folga sobrou até o
rodapé — se alguma estourar, ele avisa com `<<< ESTOUROU`.

### A conferência de glifos

A Montserrat distribuída pelo Google vem no subconjunto **latin**, que **não
tem** `→`, `≡`, `≥` nem sobrescritos como `ᴿ`. Caractere ausente não dá erro:
sai **em branco** no PDF, e só se descobre olhando a prova impressa. Por isso
todo texto desenhado passa por `_conferir()`, e o script lista no fim qualquer
caractere que a fonte não tenha. Se aparecer essa lista, troque o caractere —
não ignore.

Sem as fontes em `fontes/`, o script cai para a Liberation Sans, que é
metricamente compatível com a Arial (as duas são permitidas pela
especificação).

## De onde vêm os números

Todos saem de medições do próprio repositório, não de estimativa:

| Número | Origem |
|---|---|
| 118.267 nós · 180.424 arestas · 3.542 semáforos | log de subida do servidor com `backend/dados/malha.json` |
| 14,3× (Dijkstra → A\* com ALT), 1.703.955 → 119.398 nós | `python3 -m infra.preparar_alt`, 25 pares origem-destino |
| 10,7× no pareamento e 154,8× na quadtree | `cd matematica && python3 -m algoritmos.demo` |
| 67% das rotas mudam com semáforo | mesma rotina, seção 5 |
| 183 testes verdes | as sete suítes de `matematica/tests/` e `backend/tests/` |

Mudou alguma medição? Atualize o dicionário `MEDIDAS`, no alto do
`gerar_banner.py` — e só ele.

## Capturas

`capturas/` tem as telas do app em `frontend/app`, geradas com Playwright a
3× de densidade (1320 × 2700 px) contra o backend rodando com a malha real.
Três entram no banner; as outras ficam à disposição para slides e relatório.
