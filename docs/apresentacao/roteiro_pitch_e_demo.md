# TrueCompass — roteiro da apresentação (Mostra A3, 30/11)

Guia do professor: ficar **ao lado** do banner, nunca na frente; pitch de **90 s**;
sistema aberto na bancada para a demonstração ao vivo.

---

## 1. Pitch de 90 segundos

Aponte para o banner enquanto fala. Entre colchetes, a parte do banner.

### Quem somos e o problema (20 s) — [cabeçalho → coluna 1]

> "Somos o grupo do **TrueCompass**, de Análise e Desenvolvimento de Sistemas.
> Os apps de corrida costumam chamar o motorista **mais perto em linha reta**.
> Mas, numa cidade como São Paulo, com mão única, vias expressas e semáforos, o
> mais perto nem sempre é **o que chega antes**. [aponta o desenho A × B]
> Aqui, o motorista A está a 300 metros, mas leva 7 minutos; o B, a 900, chega em 3."

### Como funciona (40 s) — [coluna 2]

> "Transformamos o mapa real da cidade, do OpenStreetMap, num **grafo**: cada
> cruzamento é um vértice, cada rua uma aresta, e o peso é o **tempo** — incluindo
> a espera média no semáforo. [aponta 'Do mapa ao grafo']
> São 137 mil cruzamentos. Para achar a rota usamos o **A\* com marcos (ALT)**, e o
> **Dijkstra** confere que a rota é mesmo a ótima.
> Para achar o motorista, fazemos **uma busca reversa**: partimos do passageiro e
> medimos o tempo real de todos os motoristas de uma vez. [aponta 'passo a passo']
> O motorista recebe a oferta e tem 20 segundos para aceitar."

### Resultados e próximos passos (30 s) — [coluna 3 → rodapé]

> "Medimos na cidade inteira: o A\* com ALT visita **10 vezes menos cruzamentos**
> que o Dijkstra e calcula a rota em **22 milissegundos**, sempre com a rota ótima.
> [aponta o gráfico] São 281 testes automatizados, e o app está **no ar**.
> Os próximos passos são trânsito e tempo de semáforo em tempo real.
> Querem ver funcionando?" [vira o notebook]

**Dica:** cronometre. Se passar de 90 s, corte exemplos, não os números.

---

## 2. Demonstração ao vivo (2 a 3 min)

### Preparação (na véspera)

- [ ] **Duas contas já criadas e testadas** (não crie na hora):
  - **passageiro** — no **notebook**, com "Manter conectado" marcado;
  - **motorista** — no **celular**, com placa preenchida em *Perfil e carro*.
- [ ] Na conta do passageiro, salve o **Trabalho** (ex.: *Avenida Paulista, 1578*):
  vira um atalho de um toque na tela inicial.
- [ ] Teste o fluxo inteiro uma vez em casa, com os dois aparelhos.
- [ ] Celular e notebook **carregados** + carregador e um **roteador do celular**
  (internet da feira costuma falhar).
- [ ] Deixe gravado um **vídeo de tela** do fluxo completo (plano B).

### No dia, antes de abrir a bancada

- [ ] Abra o app nos dois aparelhos e permita a **localização**.
- [ ] Os dois aparelhos ficam juntos na bancada: o motorista está "perto" do
  passageiro, então a oferta chega a ele.
- [ ] No celular (motorista), toque em **Iniciar** e deixe a tela aberta.

### Passo a passo (quem fala aponta, quem opera toca)

| # | Aparelho | Toque em | Fale |
|---|---|---|---|
| 1 | Notebook | atalho **Trabalho** | "A rota verde é a do A\*. Esses ícones são os semáforos do caminho." |
| 2 | Notebook | **Como esta rota foi calculada** → **Ver as duas buscas no mapa** | "Aqui as duas buscas correm juntas: veja quanto o Dijkstra explora a mais." *(o momento mais forte para a banca de Matemática)* |
| 3 | Notebook | escolha **Conforto** → **Confirmar** | "Três categorias; o preço muda, a rota é a mesma." |
| 4 | Celular | **Aceitar** (na oferta) | "O motorista vê o valor e tem 20 s para aceitar." |
| 5 | Celular | **Mensagem para …** → **Estou chegando** | "Chat da corrida, em tempo real." |
| 6 | Notebook | **Compartilhar** | "O link mostra a viagem para a família, sem login." |
| 7 | Celular | **Navegar até o embarque (GPS simulado)** | "O carro anda no mapa do passageiro ao vivo." |
| 8 | Celular | **Iniciar viagem** → **Navegar até o destino** → **Finalizar corrida** | — |
| 9 | Notebook | **Pagar** → avaliar com estrelas | "Pagamento simulado; nenhuma cobrança real." |

Extra, se perguntarem pelo grafo: no menu da conta, ligue **Malha e semáforos** —
o mapa mostra a malha que o algoritmo usa.

### Plano B

| Se… | Faça |
|---|---|
| A oferta não chega ao motorista | Confira se ele tocou em **Iniciar** e se a localização está ligada; espere a próxima batida de GPS (4 s). |
| "Sem conexão com o servidor" | Troque para o roteador do celular. Se persistir, mostre o **vídeo** gravado. |
| O mapa não carrega | O app cai sozinho num mapa mais simples; a rota e os semáforos continuam. |
| Tudo falhou | Banner + vídeo. Não tente consertar na frente do visitante. |

---

## 3. Perguntas prováveis da banca

**Por que A\* e não só Dijkstra?**
O Dijkstra explora em todas as direções; o A\* usa uma estimativa de quanto falta
e vai direto ao destino. Na cidade inteira, visitou 10× menos cruzamentos.

**O que é o ALT?**
"A\*, Landmarks e desigualdade Triangular": guardamos de antemão a distância de
todos os cruzamentos até alguns pontos da periferia (marcos). Pela desigualdade
triangular, isso dá um limite inferior muito mais justo que a linha reta.

**Como vocês garantem que a rota é a melhor?**
A estimativa nunca passa do custo real (heurística **admissível**), então o A\*
devolve a ótima. E testamos: o Dijkstra serve de **oráculo**; nas 30 rotas
medidas, o custo foi idêntico.

**De onde vem o r²/2c do semáforo?**
Se o vermelho dura *r* segundos num ciclo de *c*, quem chega num momento
aleatório espera em média r²/(2c). Essa espera entra no peso da rua que chega ao
cruzamento. Com ela, 67% das rotas mudam de traçado.

**Os tempos de semáforo são reais?**
Não: o OpenStreetMap diz **onde** há semáforo, não o tempo. Presumimos 40 s de
vermelho num ciclo de 90 s. Dados reais são um próximo passo.

**Como acham o motorista tão rápido?**
Uma **quadtree** filtra os motoristas próximos em O(log n + k); depois **uma só**
busca no grafo reverso, a partir do passageiro, mede o tempo real de todos.

**Por que o estado da corrida é um grafo?**
Os estados (pedida → alocada → em curso → paga…) formam um grafo acíclico; o
algoritmo de **Kahn** valida no início que não há ciclo nem atalho (não dá para
pagar sem concluir).

**E se der muitos usuários?**
O grafo fica na memória do servidor e cada rota leva ~22 ms. Para escalar,
várias instâncias com o limite de tentativas num Redis.

**É seguro?**
Senhas com bcrypt, bloqueio após tentativas erradas, código por e-mail para
recuperar a senha e sessão que se renova sozinha.

---

## 4. Divisão sugerida (6 pessoas)

| Papel | Quem |
|---|---|
| Pitch — problema | |
| Pitch — como funciona | |
| Pitch — resultados | |
| Demo — notebook (passageiro) | |
| Demo — celular (motorista) | |
| Perguntas técnicas (seção 3) | |

Revezem nos horários da feira; todos devem saber o pitch inteiro.
