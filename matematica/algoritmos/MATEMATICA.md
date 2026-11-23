# A matemática do TrueCompass, sem susto

> Companheiro do `EXPLICACAO.md`. Lá o assunto são os **algoritmos** (A\* e
> Dijkstra reverso); aqui são as **fórmulas** — de onde vieram, por que existem
> e o que quebra se você mexer nelas.
>
> A versão formal, com proposições e demonstrações, está na documentação
> técnica. Aqui a linguagem é de conversa.

---

## 1. Por que não dá para usar Pitágoras

Você tem duas coordenadas e quer a distância. O reflexo é Pitágoras:

```python
distancia = sqrt((lat2-lat1)**2 + (lon2-lon1)**2)   # ERRADO
```

O problema: **grau de latitude e grau de longitude não medem a mesma coisa.**

A Terra é aproximadamente uma esfera. As linhas de latitude (horizontais) são
paralelas e igualmente espaçadas. Mas as linhas de longitude (verticais) se
encontram nos polos — então elas vão se **aproximando** conforme você sai do
equador.

Resultado, medido em São Paulo (latitude −23,5°):

| | 1 grau vale |
|---|---|
| Latitude | 111,2 km |
| Longitude | **102,0 km** |

Usar Pitágoras em graus crus erra **8,3%** no eixo leste-oeste. Num raio de
busca de 3 km, são 250 metros de erro — o bastante para escolher o motorista
errado.

### A fórmula que resolve: haversine

```python
a = sin²(Δlat/2) + cos(lat1) · cos(lat2) · sin²(Δlon/2)
distancia = 2 · R · arcsin(√a)
```

com `R = 6.371.000 m` (raio médio da Terra).

Não precisa decorar. Precisa entender **um pedaço**: o
`cos(lat1) · cos(lat2)` no meio. É exatamente ele que encolhe a contribuição
da longitude conforme você se afasta do equador. É a correção que o Pitágoras
não tem.

> **Onde isso é usado:** em quatro lugares — peso da aresta, heurística do A\*,
> poda da quadtree e ordenação por distância. É a função mais chamada do
> sistema inteiro.

---

## 2. A conta de uma linha que define o projeto

```python
peso_da_aresta = haversine(a, b) / (velocidade_kmh / 3.6)
```

O `/3.6` é só conversão de unidade: 1 km/h = 1000 m ÷ 3600 s = 1/3,6 m/s.

Faça a análise dimensional:

```
metros ÷ (metros/segundo) = segundos
```

**O peso é TEMPO, não distância.** Essa é a decisão mais importante de todo o
backend, e ela cabe numa divisão.

Por quê: o passageiro não quer quem está mais perto, quer **quem chega antes**.
Uma avenida de 50 km/h vence uma rua de 30 km/h mesmo sendo mais comprida. Se o
peso fosse distância, o sistema escolheria sempre errado em cidade com vias de
velocidades diferentes.

> **Cuidado ao mexer:** se alguém mudar o peso para metros, **tudo** desanda em
> silêncio — a heurística do A\* deixa de ser válida, a tarifa dobra de conta, e
> o ranking de motoristas inverte. O código não vai reclamar. Os testes vão.

---

## 3. Por que lista e não matriz

Duas formas de guardar um grafo:

- **Matriz de adjacência:** uma tabela V×V onde `M[i][j]` é o peso de i para j.
- **Lista de adjacência:** para cada cruzamento, a lista dos vizinhos dele.

Medido na nossa malha de 3.600 cruzamentos:

| | Entradas |
|---|---|
| Lista | ~12 mil |
| Matriz | ~13 **milhões** |

**1.067× menor.** O motivo tem nome: malha viária é um grafo **esparso**. O
grau médio medido é **2,37** — cada cruzamento liga a pouquíssimas ruas. Um
cruzamento não se conecta a outros 3.599; conecta a dois ou três.

A matriz reserva espaço para todas as ligações que **poderiam** existir. A
lista guarda só as que existem.

---

## 4. A frase que faz o Dijkstra funcionar

Decore esta:

> **No instante em que um vértice sai da fila de prioridade, o custo dele já é
> o definitivo.**

Não vai melhorar depois. Nunca. E é por isso que dá para parar a busca assim que
o destino sai da fila, em vez de calcular a cidade inteira.

### Por que isso é verdade

Suponha que `u` acabou de sair da fila, e que existia um caminho melhor até `u`
passando por algum `x` que ainda está na fila.

Esse caminho custaria `custo(x) + (o trecho de x até u)`. Mas:

1. O trecho de `x` até `u` custa **zero ou mais** — nenhuma rua devolve tempo.
2. `custo(x) ≥ custo(u)`, porque `u` foi escolhido como o **mínimo** da fila.

Logo o caminho alternativo custa pelo menos `custo(u)`. Não é melhor.
Contradição. ∎

### O que quebra a garantia

O passo 1. Se algum peso fosse **negativo**, o trecho de `x` até `u` poderia
reduzir o total, e o "definitivo" deixaria de ser definitivo.

É por isso que `adicionar_aresta` **recusa peso negativo** com mensagem
explícita. Não é paranoia: é a única hipótese da prova, protegida em código.

---

## 5. O A\* precisa de um chute honesto

O A\* é o Dijkstra com uma linha diferente: a chave da fila.

```
Dijkstra escolhe por:  g(v)
A*       escolhe por:  g(v) + h(v)
```

`g` = quanto já gastei. `h` = meu chute de quanto falta.

Nosso chute:

```python
h(v) = haversine(v, destino) / velocidade_maxima
```

### Duas propriedades, dois nomes

**Admissível** = o chute nunca passa da verdade. Ele é otimista.

Por que o nosso é: a linha reta é o menor percurso fisicamente possível, e
nenhum carro anda mais rápido que a velocidade máxima. Então o tempo real é
sempre **maior ou igual** ao chute.

**Consistente** = o chute respeita a desigualdade triangular:
`h(u) ≤ peso(u,v) + h(v)`. Em português: dar um passo e chutar de novo não pode
resultar num chute *menor* que o chute original.

### O que cada uma garante

| Propriedade | Se faltar |
|---|---|
| Admissível | o A\* devolve rota **pior** que a ótima |
| Consistente | o A\* reexpande nós e fica mais lento |

### O erro que quase todo mundo comete

```python
h = haversine(v, destino)                       # ERRADO — isso é METRO
h = haversine(v, destino) / velocidade_maxima   # certo  — isso é SEGUNDO
```

Se os pesos são segundos e o `h` devolve metros, o chute sai **centenas de vezes
maior** que a verdade. Deixa de ser otimista, perde a admissibilidade, e as
rotas saem erradas — sem erro nenhum na tela.

Existe um teste que reproduz esse bug de propósito:
`test_heuristica_inadmissivel_seria_pega`.

### O detalhe elegante

Se `h(v) = 0` para todos, "chutar zero" é não chutar nada — e o A\* **vira** o
Dijkstra. Zero é trivialmente admissível e consistente. Por isso os dois são a
mesma função no nosso código, com um parâmetro de diferença.

---

## 6. Virar o mapa do avesso

A identidade:

```
distância de p até m no mapa invertido  =  distância de m até p no mapa real
```

### Por que é verdade

Pegue qualquer caminho de `m` até `p` no mapa real:

```
m → a → b → p
```

No mapa invertido, cada uma dessas setas existe ao contrário, **com o mesmo
peso**. Então existe o caminho:

```
p → b → a → m
```

e ele custa exatamente o mesmo, porque é a mesma soma de pesos numa ordem
diferente.

Todo caminho de um lado tem um par do outro lado, com custo igual. Se os
conjuntos de caminhos se correspondem um a um e os custos batem, **o menor de um
é o menor do outro**. ∎

### O que isso economiza

Para saber o tempo de 20 motoristas até um passageiro:

- Sem a identidade: 20 buscas, uma por motorista.
- Com a identidade: **1 busca**, partindo do passageiro no mapa invertido.

Medido: **10,7× menos trabalho**.

> **Por que precisa inverter, e não só rodar do passageiro:** porque a cidade tem
> mão única. Ir de A para B não custa o mesmo que ir de B para A. Rodar do
> passageiro no mapa **normal** responderia "quanto tempo o passageiro levaria
> para dirigir até cada motorista" — a pergunta errada.

---

## 7. O mesmo mapa invertido serve para mais uma coisa

Extrato do OpenStreetMap recortado por caixa **sempre** vem com sujeira: ruas
cortadas na borda, pedaços isolados, e trechos em que se entra e não se sai
("armadilha de mão única"). Se um motorista para num desses, o pareamento não o
encontra — ou encontra e a rota não existe.

A limpeza:

```
região boa = (quem eu alcanço no mapa normal) ∩ (quem me alcança, via mapa invertido)
```

Um cruzamento só serve se você consegue **ir** até ele **e voltar**. Interseção
dos dois conjuntos.

Isso tem nome — é o passo central do **algoritmo de Kosaraju** — e reaproveita o
mapa invertido que já existia para o pareamento. Duas finalidades completamente
diferentes, uma estrutura.

No nosso fixture de teste, a poda descarta **42,9%** dos nós.

---

## 8. Ordenar o que depende de quê

O ciclo da corrida é um grafo de dependências:

```
pedido → alocação → rota → em curso → concluída → paga
```

Cada seta é "isto precisa acontecer antes daquilo". O algoritmo de **Kahn**
ordena esse tipo de grafo:

1. Conte, para cada estado, quantas setas **chegam** nele (grau de entrada).
2. Quem tem zero pode ir primeiro.
3. Ao usar um estado, tire uma seta de cada sucessor dele.
4. Quem chegou a zero entra na fila.

### O subproduto que vale mais que a ordem

Se ao final sobrou alguém sem processar, **existe ciclo** — uma dependência
circular. No nosso caso, isso significaria um fluxo em que a corrida poderia
voltar a um estado anterior e, por exemplo, ser paga duas vezes.

Rodamos Kahn **no boot do servidor**. Havendo ciclo, o servidor não sobe.

### Por que isso importa mais do que parece

A promessa do README — *"o pagamento só é processado depois que a corrida é
confirmada como concluída"* — não está garantida por um `if` em algum lugar.
Está garantida pela **estrutura do grafo**: `paga` tem exatamente uma seta
chegando, vinda de `concluída`.

Mudar a regra = mudar o grafo. Não existe outro lugar onde ela possa vazar.

---

## 9. A árvore que descarta bairros inteiros

A quadtree divide o mapa em 4 quadrantes; cada quadrante que fica cheio se
divide em 4 de novo. Cada nó da árvore "sabe" qual retângulo do mapa ele cobre.

**A sacada** não é a divisão, é a **poda**: se o retângulo de um nó está inteiro
fora do seu raio de busca, você descarta aquele ramo **sem olhar um único ponto
lá dentro**.

### A conta que autoriza podar

Você precisa da menor distância possível entre o ponto de consulta e **qualquer**
ponto daquele retângulo. Isso sai grudando a consulta na borda do retângulo:

```python
lat_mais_proxima = min(max(lat, lat_min), lat_max)   # "clamp"
lon_mais_proxima = min(max(lon, lon_min), lon_max)
limite = haversine(lat, lon, lat_mais_proxima, lon_mais_proxima)
```

Se `limite > raio`, nada naquele retângulo pode servir. Descarta.

### A recorrência

Descer a árvore até uma folha:

```
T(n) = T(n/4) + O(1)
```

Leia assim: "resolver para n pontos custa resolver para um quarto deles, mais
trabalho constante". Pelo **Teorema Mestre** (caso 2), isso dá **O(log n)**.

### Mas cuidado com essa afirmação

Medimos, e o número **não** cresce como log puro:

| Motoristas | Nós visitados | Ganho |
|---:|---:|---:|
| 500 | 21,2 | 23,6× |
| 2.000 | 41,6 | 48,1× |
| 8.000 | 85,0 | 94,1× |
| 32.000 | 206,7 | 154,8× |

64× mais motoristas → ~10× mais nós visitados.

O motivo: a consulta por raio é **O(log n + k)**, onde `k` é a quantidade de
**resultados**. Num raio fixo, adensar a cidade aumenta quem cabe dentro dele —
`k` cresceu de ~5 para ~320. Esses pontos precisam ser lidos de todo jeito, por
qualquer estrutura.

O `O(log n)` do Teorema Mestre descreve a **descida**. A coleta acrescenta o
`k`.

**A vantagem real da quadtree:** a varredura linear paga `n` **mesmo quando
k = 0**. Consulta numa região vazia da cidade: a linear compara com os 32.000
motoristas; a quadtree para na raiz, **1 nó visitado**.

---

## 10. A única fórmula que é decisão, não teorema

```python
custo = 5,00 + 0,80 × (segundos/60) + 1,90 × (metros/1000)
```

Tarifa base, mais preço por minuto, mais preço por quilômetro. Função afim,
cresce com tempo e com distância.

Todas as outras fórmulas deste documento saem de geometria ou de teoria dos
grafos — não há escolha. Os três números aqui são arbitrários: vêm de decisão de
negócio, e vocês podem mudá-los sem quebrar nada.

---

## 11. Um detalhe que só aparece na prática

Soma em ponto flutuante **não é associativa**: `(a+b)+c` pode não dar
exatamente `a+(b+c)`.

Encontramos isso de verdade. O pareamento ingênuo e o reverso somam **os mesmos
pesos**, mas em **ordem diferente** — e divergiram em **1,1 × 10⁻¹³ segundos**
sobre valores de ~350 segundos.

É ruído de arredondamento, não erro de algoritmo. Mas basta para quebrar um
`==`. Por isso toda comparação de custo no projeto usa **tolerância relativa**:

```python
assert custo_a == custo_b                              # frágil
assert isclose(custo_a, custo_b, rel_tol=1e-9)         # correto
```

---

## 12. O método: use o simples para provar o complexo

Este é o princípio que organiza os testes, e vale levar para qualquer projeto.

| Implementação simples | Valida | Como |
|---|---|---|
| Dijkstra (`h = 0`) | A\* | 200 pares aleatórios, custo idêntico |
| `IndiceLinear` (varredura) | Quadtree | 200 consultas, mesmo conjunto e mesma ordem |
| Pareamento ingênuo (k buscas) | Pareamento reverso | mesmos ETAs |

Nenhuma dessas implementações simples é código morto. Elas são o **gabarito**.

Uma versão obviamente correta vale mais como referência do que como otimização —
porque se a otimizada divergir dela em qualquer entrada, você sabe na hora, e
sabe exatamente qual das duas está errada.

---

## Cola rápida

| Fórmula | Onde | Para quê |
|---|---|---|
| `2R·arcsin(√a)` | `grafo.py` | distância sobre a esfera |
| `d / (kmh/3.6)` | `grafo.py` | peso da aresta, em segundos |
| `f = g + h` | `busca.py` | chave da fila do A\* |
| `h = d/v_max` | `grafo.py` | chute otimista |
| `dist_inv(p,m) = dist(m,p)` | `matching.py` | 1 busca em vez de k |
| `R⁺ ∩ R⁻` | `osm.py` | poda ao componente conexo |
| grau de entrada | `topologica.py` | ordem e detecção de ciclo |
| clamp + haversine | `quadtree.py` | limite que autoriza a poda |
| `T(n)=T(n/4)+O(1)` | `quadtree.py` | recorrência da descida |
| `base + min + km` | `corrida.py` | tarifa |
