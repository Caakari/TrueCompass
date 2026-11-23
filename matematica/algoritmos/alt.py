# -*- coding: utf-8 -*-
"""ALT: A* + Landmarks + desigualdade Triangular.

PROBLEMA. A heuristica haversine divide a distancia em linha reta pela maior
velocidade da malha. Na malha real de Sao Paulo esse teto e 110 km/h, imposto
por um punhado de arestas de marginal, enquanto a rua mediana tem 30 km/h. A
estimativa fica frouxa por um fator de ~3,7 e o A* quase degenera em Dijkstra.

IDEIA. Escolher alguns MARCOS e pre-calcular, para cada vertice, a distancia
ate eles e a partir deles. A desigualdade triangular (Proposicao C.1 da
documentacao) entrega entao dois limites inferiores para d(v, t):

    marco como ORIGEM   d(L,t) <= d(L,v) + d(v,t)  =>  d(v,t) >= d(L,t) - d(L,v)
    marco como DESTINO  d(v,L) <= d(v,t) + d(t,L)  =>  d(v,t) >= d(v,L) - d(t,L)

Tomamos o MAIOR dos limites sobre os marcos escolhidos. Cada termo e um limite
inferior legitimo, logo o maximo tambem e -- e a heuristica permanece
ADMISSIVEL. Permanece CONSISTENTE porque cada termo e uma diferenca de
potenciais: para o primeiro,

    h(u) - h(v) = d(L,v) - d(L,u) <= w(u,v),

pois d(L,v) <= d(L,u) + w(u,v); o segundo e simetrico, e o maximo de funcoes
consistentes e consistente.

DIRECIONADO. Num grafo dirigido os dois limites exigem dados distintos:
d(L,.) sai de uma busca no grafo normal, d(.,L) de uma busca no grafo REVERSO
-- exatamente a dualidade da Proposicao C.7, que ja usamos no pareamento.

PRECISAO. As tabelas sao float64, nao float32. Medido: com float32 o limite
chega a superar o custo real em 2e-6 RELATIVO -- a admissibilidade depende de
uma SUBTRACAO entre duas distancias, e a diferenca herda o arredondamento das
duas pontas. Com 16 marcos na malha de Sao Paulo isso custa 29 MB em vez de
14 MB, preco baixo por nao ter de justificar rota subotima.

MARCOS ATIVOS. Avaliar 16 marcos a cada chamada de h custa caro em Python e
pode anular o ganho. Na consulta escolhemos os poucos marcos que dao o melhor
limite para aquele par origem-destino e usamos so eles. E a pratica padrao do
ALT, e o que mantem o custo por chamada baixo.
"""

import hashlib
import struct
from array import array
from math import inf, isfinite

from algoritmos.busca import busca_caminho_minimo

QUANTIDADE_PADRAO = 16
ATIVOS_PADRAO = 4
ASSINATURA = b"TCALT4\x00\x00"


class ALT:
    """Marcos e tabelas de distancia, com a heuristica derivada deles."""

    __slots__ = ("marcos", "indice", "de_marco", "para_marco", "ativos")

    def __init__(self, marcos, indice, de_marco, para_marco, ativos=ATIVOS_PADRAO):
        self.marcos = list(marcos)
        self.indice = indice                # no -> posicao nas tabelas
        self.de_marco = de_marco            # por marco: array d (float64), d(L, v)
        self.para_marco = para_marco        # por marco: array d (float64), d(v, L)
        self.ativos = ativos

    def __len__(self):
        return len(self.marcos)

    # ------------------------------------------------------ impressao digital

    @staticmethod
    def impressao_de(nos):
        """Resumo do conjunto de vertices, para detectar artefato desatualizado.

        Sem isto, um `alt.bin` gerado para outra malha seria usado em silencio:
        os ids coincidiriam em parte, os limites viriam de outro grafo e o A*
        devolveria rota subotima sem erro algum. Preferivel recusar.
        """
        resumo = hashlib.blake2b(digest_size=16)
        resumo.update(struct.pack("<Q", len(nos)))
        for no in nos:
            resumo.update(struct.pack("<q", no))
        return resumo.digest()

    @property
    def impressao(self):
        return self.impressao_de(sorted(self.indice, key=self.indice.get))

    def confere(self, grafo):
        """True se este ALT foi construido para exatamente este grafo."""
        return self.impressao == self.impressao_de(sorted(grafo.nos))

    # ------------------------------------------------------------ construcao

    @classmethod
    def construir(cls, grafo, quantidade=QUANTIDADE_PADRAO, ativos=ATIVOS_PADRAO,
                  relatar=None):
        """Escolhe os marcos e calcula as tabelas. O(quantidade * (V+E) log V).

        Selecao por PONTO MAIS DISTANTE: o primeiro marco e o vertice mais
        longe de uma semente arbitraria; cada seguinte e o que esta mais longe
        do conjunto ja escolhido. Marcos espalhados pela periferia dao limites
        melhores que marcos no centro -- um marco no meio da cidade fica
        "entre" origem e destino e seu limite vira quase zero.
        """
        nos = sorted(grafo.nos)
        if not nos:
            raise ValueError("grafo vazio")
        indice = {no: i for i, no in enumerate(nos)}
        total = len(nos)
        reverso = grafo.reverso()

        def varrer(alvo_grafo, origem):
            """Distancias de `origem` a todos, como array de float32."""
            distancias = busca_caminho_minimo(alvo_grafo, origem, alvos=set()).distancias
            tabela = array("d", [inf]) * total
            for no, valor in distancias.items():
                tabela[indice[no]] = valor
            return tabela

        # Semente: o vertice mais distante de um no qualquer.
        inicial = busca_caminho_minimo(grafo, nos[0], alvos=set()).distancias
        primeiro = max(inicial, key=inicial.get)

        marcos, de_marco, para_marco = [], [], []
        # Distancia de cada vertice ao conjunto de marcos ja escolhido.
        cobertura = array("d", [inf]) * total

        candidato = primeiro
        for passo in range(min(quantidade, total)):
            marcos.append(candidato)
            de = varrer(grafo, candidato)
            para = varrer(reverso, candidato)     # d(v, L), pela dualidade
            de_marco.append(de)
            para_marco.append(para)

            for i in range(total):
                if de[i] < cobertura[i]:
                    cobertura[i] = de[i]

            if relatar:
                relatar(passo + 1, min(quantidade, total), candidato)

            if passo + 1 < quantidade:
                # Proximo marco: o mais distante de tudo que ja temos.
                melhor, melhor_valor = None, -1.0
                for i in range(total):
                    valor = cobertura[i]
                    if isfinite(valor) and valor > melhor_valor:
                        melhor, melhor_valor = i, valor
                if melhor is None:
                    break
                candidato = nos[melhor]

        return cls(marcos, indice, de_marco, para_marco, ativos)

    # ------------------------------------------------------------ heuristica

    def heuristica(self, destino, origem=None):
        """h(v) admissivel e consistente para o A* ate `destino`.

        Com `origem`, seleciona os marcos ATIVOS: aqueles cujo limite ja e
        maior na propria origem. Sem ela, usa todos -- correto, porem mais
        caro por chamada.
        """
        j = self.indice.get(destino)
        if j is None:
            return lambda _no: 0.0

        # Pares (d(L,t), d(t,L)) por marco, lidos uma vez so.
        candidatos = []
        for k in range(len(self.marcos)):
            de_t = self.de_marco[k][j]
            para_t = self.para_marco[k][j]
            if isfinite(de_t) or isfinite(para_t):
                candidatos.append((k, de_t, para_t))

        if origem is not None and len(candidatos) > self.ativos:
            i0 = self.indice.get(origem)
            if i0 is not None:
                def forca(item):
                    k, de_t, para_t = item
                    a = de_t - self.de_marco[k][i0]
                    b = self.para_marco[k][i0] - para_t
                    melhor = max(a if isfinite(a) else 0.0,
                                 b if isfinite(b) else 0.0)
                    return melhor
                candidatos.sort(key=forca, reverse=True)
                candidatos = candidatos[:self.ativos]

        # Materializa em listas simples: indexacao de lista e mais rapida que
        # atributo + array dentro do laco quente.
        tabelas = [(self.de_marco[k], de_t, self.para_marco[k], para_t)
                   for k, de_t, para_t in candidatos]
        indice = self.indice

        def h(no):
            i = indice[no]
            melhor = 0.0
            for de, de_t, para, para_t in tabelas:
                a = de_t - de[i]
                if a > melhor and a != inf:
                    melhor = a
                b = para[i] - para_t
                if b > melhor and b != inf:
                    melhor = b
            return melhor

        return h

    # ---------------------------------------------------------- persistencia

    def salvar(self, caminho):
        """Formato binario compacto: cabecalho, ids dos nos, depois as tabelas."""
        nos_ordenados = sorted(self.indice, key=self.indice.get)
        with open(caminho, "wb") as arquivo:
            arquivo.write(ASSINATURA)
            arquivo.write(struct.pack("<QQQ", len(nos_ordenados),
                                      len(self.marcos), self.ativos))
            arquivo.write(self.impressao_de(nos_ordenados))
            array("q", nos_ordenados).tofile(arquivo)
            array("q", self.marcos).tofile(arquivo)
            for tabela in self.de_marco:
                tabela.tofile(arquivo)
            for tabela in self.para_marco:
                tabela.tofile(arquivo)

    @classmethod
    def carregar(cls, caminho):
        with open(caminho, "rb") as arquivo:
            if arquivo.read(len(ASSINATURA)) != ASSINATURA:
                raise ValueError(f"{caminho} nao e um arquivo ALT desta versao")
            total, quantidade, ativos = struct.unpack("<QQQ", arquivo.read(24))
            gravada = arquivo.read(16)

            ids = array("q"); ids.fromfile(arquivo, total)
            marcos = array("q"); marcos.fromfile(arquivo, quantidade)

            de_marco, para_marco = [], []
            for _ in range(quantidade):
                tabela = array("d"); tabela.fromfile(arquivo, total)
                de_marco.append(tabela)
            for _ in range(quantidade):
                tabela = array("d"); tabela.fromfile(arquivo, total)
                para_marco.append(tabela)

        indice = {no: i for i, no in enumerate(ids)}
        if cls.impressao_de(list(ids)) != gravada:
            raise ValueError(f"{caminho} esta corrompido: impressao nao confere")
        return cls(list(marcos), indice, de_marco, para_marco, ativos)
