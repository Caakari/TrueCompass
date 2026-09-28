# Entendendo os algoritmos do TrueCompass

> Guia de aprendizado. A linguagem aqui é simples de propósito — a versão
> formal, com provas, está na documentação técnica do projeto.

---

## 1. O problema, em um minuto

Quando alguém pede uma corrida, o app precisa responder duas perguntas **diferentes**:

| # | Pergunta | Quem responde |
|---|---|---|
| 1 | Dos 20 motoristas por perto, **qual chega antes** até o passageiro? | Dijkstra reverso |
| 2 | Qual o **melhor caminho** do passageiro até o destino dele? | A\* |

São perguntas diferentes, e por isso pedem ferramentas diferentes. A confusão
comum é achar que "achar rota" e "achar motorista" é o mesmo problema.

---

## 2. O que o Dijkstra faz (sem matemática)

Imagine derrubar uma gota de tinta num mapa, no ponto de partida. A tinta
se espalha pelas ruas, um pouquinho por vez, sempre **pela borda mais barata
primeiro**. Quando a tinta encosta no seu destino, o caminho que ela fez até
ali é o mais rápido possível.

É literalmente isso que o Dijkstra faz:

```
1. Comece com custo 0 na origem e infinito em todo o resto.
2. Pegue o ponto mais barato que você ainda não visitou.
3. Olhe os vizinhos dele. Se dá pra chegar mais barato por aqui, atualize.
4. Repita.
```

**A garantia de ouro:** no momento em que um ponto é *retirado da fila*, o
custo dele já é o definitivo — nunca vai melhorar depois. Isso só vale porque
nenhuma rua tem custo negativo (ninguém "ganha tempo" ao dirigir). Guarde
essa frase, porque é dela que sai tudo o mais.

### Os dois desperdícios

O problema não é o Dijkstra estar errado. Ele está certo. O problema é que,
do jeito que estava especificado, ele desperdiça de duas formas:

**Desperdício 1 — ele espalha a tinta para todo lado.** Se você está no centro
e vai para a zona sul, o Dijkstra também espalha tinta para a zona norte, para
o leste, para o oeste. Ele não sabe para onde você vai.

**Desperdício 2 — ele não sabe a hora de parar.** A especificação original
calculava a distância da origem até *todos* os cruzamentos da cidade, mesmo
quando você só queria um número.

Esse segundo já se resolve com uma linha: **pare quando o destino sair da
fila**. Pela garantia de ouro, naquele instante a resposta já é final.

---

## 3. Ideia 1 — A\*: a tinta que sabe para onde ir

E se, além do custo já gasto, a tinta também considerasse **o quanto ainda
falta**? É isso o A\*.

```
Dijkstra escolhe o próximo ponto por:   g(v)
A* escolhe o próximo ponto por:         g(v) + h(v)
```

- `g(v)` = quanto **já gastei** para chegar em `v` (isso o Dijkstra já tinha)
- `h(v)` = meu **chute** de quanto ainda falta de `v` até o destino

Só isso. Mesmo laço, mesma fila, chave diferente. A tinta deixa de ser um
círculo e vira uma **gota apontada para o destino**.

### De onde vem o chute?

Do próprio mapa. Você tem as coordenadas de cada cruzamento, então:

```
h(v) = distância em linha reta de v até o destino ÷ velocidade máxima
```

A distância em linha reta ("haversine", que é a linha reta sobre a superfície
curva da Terra) é fácil de calcular e não precisa de preparo nenhum.

### A regra que não pode ser quebrada

> **O chute nunca pode ser maior que a verdade.**

Em outras palavras: `h` tem de ser **otimista**. Se ele exagerar, o A\* pode
descartar a rota boa achando que ela é ruim, e devolver um caminho pior.

A linha reta é otimista por natureza: nenhuma rua é mais curta que a linha
reta entre dois pontos. E dividir pela velocidade **máxima** garante que o
tempo estimado também seja otimista — nenhum carro anda mais rápido que isso.

Esse é o erro clássico, e vale decorar:

```python
h = haversine(v, destino)                       # ERRADO: isso é METRO
h = haversine(v, destino) / velocidade_max      # certo: isso é SEGUNDO
```

Se os pesos do grafo são segundos e o seu `h` devolve metros, o número sai
centenas de vezes maior que a verdade — o chute vira pessimista e as rotas
saem erradas. Existe um teste no projeto (`test_heuristica_inadmissivel_seria_pega`)
que reproduz exatamente esse bug de propósito.

### O Dijkstra continua vivo (e vira o seu juiz)

Repare: se `h(v) = 0` para todo mundo, "chutar zero" é o mesmo que não chutar
nada, e o A\* vira **exatamente** o Dijkstra. Ou seja, são o mesmo algoritmo
com uma configuração diferente.

Isso dá uma sacada prática ótima: como o Dijkstra é simples e comprovadamente
correto, ele serve de **gabarito**. Rode os dois no mesmo par de pontos e o
custo tem de bater. Se não bater, a sua heurística está errada. É assim que o
teste `test_astar_concorda_com_dijkstra` funciona, em 200 pares aleatórios.

---

## 4. Ideia 2 — o grafo invertido: pergunte ao contrário

Agora o matching. Você tem 20 motoristas e quer o tempo de cada um até o
passageiro.

O jeito óbvio é rodar o Dijkstra 20 vezes, uma por motorista. **20 espalhadas
de tinta pela cidade para responder um pedido de corrida.**

### A sacada

O Dijkstra é do tipo **"de um lugar para todos"**. Mas o seu problema é
**"de todos para um lugar"**. Parece que não encaixa... até você virar o mapa
do avesso.

Pegue a cidade e **inverta o sentido de todas as ruas**. Mesmas ruas, mesmos
tempos, só as setas trocadas. Nesse mapa invertido vale:

```
ir do passageiro até o motorista (mapa invertido)
        =
ir do motorista até o passageiro (mapa de verdade)
```

Então **uma única** espalhada de tinta, partindo do passageiro no mapa
invertido, alcança todos os 20 motoristas e já diz o tempo de cada um.

**De 20 buscas para 1.**

### E por que não simplesmente rodar do passageiro no mapa normal?

Porque a cidade tem **mão única**. O tempo de ir de A para B não é o mesmo de
ir de B para A.

Se você rodar a busca a partir do passageiro no mapa normal, você está
calculando *"quanto tempo o passageiro levaria para dirigir até cada motorista"* —
que é a pergunta errada. Numa região de marginais e viadutos, a resposta pode
ser bem diferente.

Inverter as setas é o que conserta isso, e **não custa nada** em tempo de
execução: o mapa invertido é construído **uma vez** quando o sistema liga, e
fica guardado.

> Cuidado prático: se você atualiza o trânsito em tempo real, precisa
> atualizar os dois mapas juntos. Esquecer disso faz o matching usar tempos
> velhos — é o bug mais chato dessa abordagem. Por isso o método
> `atualizar_peso()` mexe nos dois, e existe um teste só para garantir isso.

### Saber a hora de parar (de novo)

Você não precisa de tempo até a cidade inteira — só até os 20. Então conte:
cada vez que um motorista sai da fila, risque da lista. Quando a lista zerar,
pare.

Some um **orçamento de tempo** (`limite`): se um motorista está a mais de 15
minutos, ele não interessa. Assim, se um candidato ficou do outro lado de um
rio sem ponte, a busca não varre a cidade atrás dele — ele simplesmente sai
da lista.

### Bônus: as 20 rotas saem de graça

Enquanto espalha a tinta, o algoritmo anota "cheguei em `v` vindo de `u`".
Esse rastro forma uma **árvore** de caminhos.

Aqui vem a parte bonita: como a busca rodou no mapa invertido, seguir o rastro
a partir de um motorista, **na ordem natural de leitura**, já entrega a rota
real dele até o passageiro. Sem inverter nada no final.

```
motorista → (rastro) → (rastro) → ... → passageiro
```

Uma busca, 20 ETAs **e** as 20 rotas para desenhar no mapa.

---

## 5. Por que a quadtree não resolve isso sozinha

A quadtree ordena por **distância em linha reta**. Mas linha reta mente.

Rodando a demonstração do projeto, com o passageiro na beira do rio:

```
motorista_16    275 m em linha reta   ->   5.8 min de verdade
motorista_08    548 m em linha reta   ->   1.0 min de verdade
```

O `motorista_16` está na **metade** da distância e chega **quase 5 minutos
depois** — porque está do outro lado do rio e precisa dar a volta pela ponte.
A velocidade implícita dele é 2,9 km/h: mais lento que andar a pé.

Cada estrutura faz o que sabe fazer:

| Etapa | Papel | Ferramenta |
|---|---|---|
| Filtro | baratear: de 5.000 motoristas para 20 plausíveis | Quadtree |
| Desempate | acertar: qual dos 20 chega antes **de verdade** | Dijkstra reverso |
| Rota | melhor caminho até o destino | A\* |

E repare: para isso funcionar, os pesos do grafo têm de ser **tempo**, não
distância. Quem o passageiro quer é quem chega antes, não quem está mais perto.

---

## 6. Tudo isso é uma função só

Como Dijkstra é "A\* com chute zero", e o reverso é "o mesmo laço rodando no
mapa invertido", não existem três algoritmos. Existe **um**, com parâmetros:

```python
busca_caminho_minimo(grafo, origem, alvos, h=None, limite=inf)
```

| Uso | grafo | alvos | h |
|---|---|---|---|
| Rota da corrida | normal | `{destino}` | haversine → **A\*** |
| Matching | **invertido** | `{20 motoristas}` | `None` → **Dijkstra** |
| Gabarito dos testes | normal | `{destino}` | `None` → **Dijkstra** |

### Uma armadilha, uma guarda

Com **vários alvos ao mesmo tempo**, o chute teria de ser otimista para todos
simultaneamente — e vai ficando ruim conforme os alvos são resolvidos. Não
compensa a complicação.

Por isso a função **recusa** heurística quando há mais de um alvo, com uma
mensagem explicando. Melhor um erro claro na cara do que uma rota sutilmente
errada em produção.

---

## 7. Resultados medidos

Cidade sintetica de 3.600 cruzamentos e 8.545 trechos de rua:

**Matching (20 candidatos):**

| Abordagem | Buscas | Nós expandidos | Tempo |
|---|---|---|---|
| Um Dijkstra por motorista | 20 | 30.395 | 36,9 ms |
| **Um Dijkstra reverso** | **1** | **2.841** | **3,9 ms** |

→ **10,7× menos trabalho**, resultado idêntico.

**Rota da corrida:**

| Algoritmo | Nós expandidos | Tempo | Custo |
|---|---|---|---|
| Dijkstra | 3.302 | 4,1 ms | 6,56 min |
| **A\*** | **1.044** | **2,1 ms** | **6,56 min** |

→ **3,2× menos trabalho**, e **exatamente a mesma rota ótima**.

Esse "mesmo custo" na última coluna é o ponto todo: não é uma aproximação que
troca qualidade por velocidade. É a resposta certa, alcançada com menos busca.

> Detalhe honesto: A\* e Dijkstra têm a **mesma** complexidade de pior caso,
> `O((V + E) log V)`. O ganho é no caso médio, e por isso a métrica correta
> para o relatório é **nós expandidos**, não a notação O.

---

## 8. Como rodar

```bash
python3 -m algoritmos.demo        # comparativo com os números acima
python3 tests/test_algoritmos.py  # 15 testes, sem precisar de pytest
```

---

## 9. Glossário

| Termo | Em português claro |
|---|---|
| **Vértice / nó** | um cruzamento |
| **Aresta** | um trecho de rua entre dois cruzamentos |
| **Peso** | quanto custa percorrer aquele trecho (aqui: segundos) |
| **Grafo direcionado** | mapa onde a rua tem sentido (mão única) |
| **Lista de adjacência** | "para cada cruzamento, a lista de vizinhos" |
| **Fila de prioridade** | fila que sempre entrega o item mais barato primeiro |
| **Relaxar uma aresta** | "por aqui chega mais barato? então atualiza" |
| **Heurística `h`** | o chute de quanto falta até o destino |
| **Admissível** | o chute nunca passa da verdade (é otimista) |
| **Expandir um nó** | tirar um cruzamento da fila e olhar seus vizinhos |
| **Grafo reverso** | o mesmo mapa com todas as setas invertidas |
| **Many-to-one** | "de muitos para um": vários motoristas, um passageiro |

---

## 10. Para onde isso cresce

- **A\* bidirecional** — espalha tinta dos dois lados e encontra no meio.
- **Contraction Hierarchies** — o que o OSRM/Uber usam de verdade: cria atalhos
  num pré-processamento e responde rotas em microssegundos. Ganho enorme, mas
  o pré-processamento não gosta de trânsito mudando o tempo todo.
- **Algoritmo húngaro** — quando dois passageiros disputam o mesmo motorista,
  "cada um pega o mais perto" começa a falhar. Aí o problema vira
  *emparelhamento de custo mínimo*, e o Dijkstra reverso é justamente como
  você monta a matriz de custos barato: uma busca por passageiro, em vez de
  uma por par.
