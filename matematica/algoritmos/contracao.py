"""Contracao de nos de passagem: a malha guarda so o que decide rota.

Um extrato do OpenStreetMap traz um no a cada curva da rua. Na malha real de
Sao Paulo, MEDIDO, 79% dos nos tem exatamente dois vizinhos e nenhum
semaforo: nao sao cruzamentos, so desenham a curva. Para o Dijkstra/A* eles
sao puro custo -- cada um entra na fila de prioridade e e expandido sem que
exista escolha nenhuma a fazer ali.

A contracao troca cada cadeia sem bifurcacao

    cruzamento -> a -> b -> c -> cruzamento

por UMA aresta, de peso igual a soma dos pesos da cadeia.

POR QUE O CAMINHO MINIMO NAO MUDA. Um caminho que entra numa cadeia sem
bifurcacao so pode atravessa-la inteira ou voltar por onde entrou; voltar e
um desvio de custo positivo, que nenhum caminho minimo faz (pesos nao
negativos, secao 5.1). Logo todo caminho minimo entre dois nos MANTIDOS
percorre cadeias inteiras, e a soma dos pesos e preservada exatamente.
O teste-oraculo confere: Dijkstra no grafo original e no contraido devolvem
o mesmo custo para todo par de nos mantidos.

A HEURISTICA CONTINUA ADMISSIVEL. `velocidade_maxima_kmh` passa a medir a
linha reta entre as pontas da cadeia, que e <= ao comprimento da cadeia --
cada aresta contraida parece mais LENTA que a rua real, nunca mais rapida.
E vale para todo caminho: linha_reta(v, t) <= soma das linhas retas das
arestas <= v_max * soma dos pesos. Admissivel e consistente, como antes.

DOIS LIMITES DELIBERADOS:

- Nos em `preservar` (semaforos) nunca somem. O atraso do sinal ja esta no
  peso da aresta que chega, entao contrair tambem seria exato; preservamos
  porque o front e a contagem de sinais por rota se ancoram nesses nos.
- Cadeia mais longa que `limite_m` e partida. Sem isso, quem pede corrida no
  meio de um viaduto de 1 km seria ancorado a um cruzamento a 500 m: a quadtree
  so enxerga nos. Com 250 m, na malha atual, sobram 22% dos nos.

A forma da rua nao se perde: os pontos intermediarios ficam em `Geometria`,
usada so para DESENHAR e para MEDIR metros -- nunca pela busca.
"""

from array import array

from .grafo import Grafo, haversine

LIMITE_PADRAO_M = 250.0
ESCALA = 1_000_000          # microgaus: inteiro de 32 bits, ~0,1 m de resolucao


class Geometria:
    """Tracado real das arestas contraidas.

    Para cada aresta (u, v) que substituiu uma cadeia, guarda os pontos
    INTERMEDIARIOS (sem as pontas, que ja sao nos do grafo) em microgaus,
    num `array('i')` -- 8 bytes por ponto, contra ~100 de uma tupla de floats.
    Numa rua de mao dupla os dois sentidos compartilham o MESMO array, lido
    de tras para frente num deles.

    Aresta sem entrada aqui e um segmento reto entre as pontas: e o caso de
    toda aresta do grafo nao contraido, entao `Geometria()` vazia e neutra.
    """

    def __init__(self):
        self._meio = {}         # (u, v) -> (array('i') lat,lon,lat,lon..., invertido)

    def __len__(self):
        return len(self._meio)

    def definir(self, u, v, pontos, invertido=False):
        """`pontos`: [(lat, lon), ...] intermediarios, na ordem de u para v."""
        if isinstance(pontos, array):
            valores = pontos
        else:
            valores = array("i")
            for lat, lon in pontos:
                valores.append(round(lat * ESCALA))
                valores.append(round(lon * ESCALA))
        if valores:
            self._meio[(u, v)] = (valores, invertido)

    def compartilhar(self, u, v, de_u, de_v):
        """(u, v) usa o tracado de (de_u, de_v) percorrido ao contrario."""
        valores, invertido = self._meio[(de_u, de_v)]
        self._meio[(u, v)] = (valores, not invertido)

    def bruto(self, u, v):
        """(array, invertido) ou None. Para serializar sem copiar."""
        return self._meio.get((u, v))

    def mesmo_tracado(self, u, v):
        """(u, v) e (v, u) sao a mesma rua percorrida nos dois sentidos?

        Falso quando duas ruas distintas ligam o par (uma em cada sentido,
        como as duas pistas de uma avenida): ai as duas tem de ser desenhadas.
        """
        ida, volta = self._meio.get((u, v)), self._meio.get((v, u))
        if ida is None or volta is None:
            return ida is None and volta is None
        return ida[0] is volta[0]

    def intermediarios(self, u, v):
        """Pontos entre u e v, na ordem de u para v ([] se a aresta e reta)."""
        entrada = self._meio.get((u, v))
        if entrada is None:
            return []
        valores, invertido = entrada
        pontos = [(valores[i] / ESCALA, valores[i + 1] / ESCALA)
                  for i in range(0, len(valores), 2)]
        if invertido:
            pontos.reverse()
        return pontos

    def tracado(self, grafo, caminho):
        """Polilinha completa do caminho: nos e pontos intermediarios."""
        if not caminho:
            return []
        pontos = [grafo.coordenadas(caminho[0])]
        for u, v in zip(caminho, caminho[1:]):
            pontos.extend(self.intermediarios(u, v))
            pontos.append(grafo.coordenadas(v))
        return pontos

    def comprimento_m(self, grafo, caminho):
        """Metros pela rua, e nao pela corda entre cruzamentos.

        Sem a geometria uma curva contraida viraria linha reta e o preco da
        corrida (que cobra por km) sairia mais barato que o trajeto real.
        """
        pontos = self.tracado(grafo, caminho)
        return sum(haversine(*a, *b) for a, b in zip(pontos, pontos[1:]))


def _vizinhanca(grafo):
    """Vizinhos SEM direcao: quem liga a quem, em qualquer sentido."""
    vizinhos = {no: set() for no in grafo.nos}
    for origem in grafo.nos:
        for destino, _peso in grafo.vizinhos(origem):
            if destino != origem:
                vizinhos[origem].add(destino)
                vizinhos[destino].add(origem)
    return vizinhos


def nos_de_passagem(grafo, preservar=()):
    """Nos que so desenham a rua: dois vizinhos, atravessaveis, sem sinal.

    "Atravessavel" exige poder entrar por um lado e sair pelo outro em pelo
    menos um sentido. Um no com dois vizinhos que so RECEBE (p -> a <- q) e
    um beco: contrai-lo apagaria um destino, entao fica.
    """
    preservar = set(preservar)
    vizinhos = _vizinhanca(grafo)
    passagem = set()
    for no, lados in vizinhos.items():
        if len(lados) != 2 or no in preservar:
            continue
        p, q = lados
        saidas = dict(grafo.vizinhos(no))
        entra_p = no in dict(grafo.vizinhos(p))
        entra_q = no in dict(grafo.vizinhos(q))
        if (entra_p and q in saidas) or (entra_q and p in saidas):
            passagem.add(no)
    return passagem, vizinhos


def _nos_mantidos(grafo, passagem, vizinhos, limite_m):
    """Fase 1: decide quem fica. Inclui os cortes que limitam o comprimento.

    Percorre cada cadeia uma vez, sem direcao, a partir de um no mantido.
    Ciclos feitos so de nos de passagem (raros: uma rotatoria isolada) nao
    tem ponta mantida; o primeiro no do ciclo vira ancora.
    """
    mantidos = set(grafo.nos) - passagem
    visitados = set()

    def percorrer(inicio):
        for vizinho in sorted(vizinhos[inicio]):
            if vizinho in mantidos or vizinho in visitados:
                continue
            anterior, atual = inicio, vizinho
            acumulado = haversine(*grafo.coordenadas(inicio), *grafo.coordenadas(atual))
            while atual in passagem and atual not in visitados:
                visitados.add(atual)
                proximo = next(x for x in vizinhos[atual] if x != anterior)
                trecho = haversine(*grafo.coordenadas(atual), *grafo.coordenadas(proximo))
                if acumulado + trecho > limite_m:
                    mantidos.add(atual)      # corte: a cadeia segue a partir daqui
                    acumulado = 0.0
                acumulado += trecho
                anterior, atual = atual, proximo

    for no in sorted(mantidos):
        percorrer(no)
    for no in sorted(passagem):
        if no not in visitados and no not in mantidos:
            mantidos.add(no)                 # ancora de um ciclo isolado
            percorrer(no)
    return mantidos


def contrair(grafo, preservar=(), limite_m=LIMITE_PADRAO_M):
    """Grafo so com cruzamentos (e cortes), mais o tracado do que sumiu.

    Devolve (grafo_contraido, geometria). Fase 2 caminha DIRECIONADA a
    partir de cada no mantido: segue a aresta de saida, atravessa os nos de
    passagem somando pesos e para no proximo no mantido. Se no meio a rua
    deixa de ir naquele sentido, nao ha aresta -- a cadeia so e percorrida
    no outro.

    Duas cadeias distintas ligando o mesmo par (duas ruas paralelas entre os
    mesmos cruzamentos) colapsam numa aresta: fica a de menor peso, com o
    tracado dela. Para caminho minimo, a outra nunca seria escolhida.
    """
    passagem, vizinhos = nos_de_passagem(grafo, preservar)
    mantidos = _nos_mantidos(grafo, passagem, vizinhos, limite_m)

    contraido = Grafo()
    for no in grafo.nos:
        if no in mantidos:
            contraido.adicionar_no(no, *grafo.coordenadas(no))

    melhores = {}           # (u, v) -> (peso, nos intermediarios)
    for inicio in mantidos:
        for primeiro, peso in grafo.vizinhos(inicio):
            anterior, atual, total, meio = inicio, primeiro, peso, []
            while atual not in mantidos:
                meio.append(atual)
                proximo = next(x for x in vizinhos[atual] if x != anterior)
                saidas = dict(grafo.vizinhos(atual))
                if proximo not in saidas:
                    break                    # contramao no meio da cadeia
                total += saidas[proximo]
                anterior, atual = atual, proximo
            else:
                if atual != inicio:          # laco de volta ao mesmo no: inutil
                    chave = (inicio, atual)
                    if chave not in melhores or total < melhores[chave][0]:
                        melhores[chave] = (total, tuple(meio))

    geometria = Geometria()
    for (u, v), (peso, meio) in melhores.items():
        contraido.adicionar_aresta(u, v, peso)
    for (u, v), (_peso, meio) in melhores.items():
        if not meio or (u, v) in geometria._meio:
            continue
        geometria.definir(u, v, [grafo.coordenadas(no) for no in meio])
        volta = melhores.get((v, u))
        if volta and volta[1] == meio[::-1]:
            geometria.compartilhar(v, u, u, v)
    return contraido, geometria
