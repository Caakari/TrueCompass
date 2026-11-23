# -*- coding: utf-8 -*-
"""Mapa como MATRIZ de celulas, convertida em grafo ponderado direcionado.

A matriz e a representacao de AUTORIA: humana, editavel como texto, versionavel
em diff. O grafo e a representacao de EXECUCAO, derivada dela.

    ######               UM CARACTERE = UMA CELULA, sem separador.
    #.>.S#               Celulas vizinhas ortogonais viram arestas;
    #.#.A#               o sentido sai do tipo da celula.
    ######

NAO CONFUNDIR com matriz de adjacencia. Esta matriz e NxM, com uma celula por
cruzamento -- cresce com a area da cidade. A matriz de adjacencia seria VxV e,
medida na malha do projeto, ocuparia 1.067 vezes mais que a lista de
adjacencia. A matriz aqui descreve a GEOGRAFIA; a lista, a CONECTIVIDADE.

TIPOS DE CELULA

    .   rua local, mao dupla
    A   avenida, mao dupla, mais rapida
    S   cruzamento semaforizado, mao dupla
    >   mao unica para leste      (movimento vertical permanece livre)
    <   mao unica para oeste
    ^   mao unica para norte
    v   mao unica para sul
    #   intransponivel (quarteirao, agua, predio)
    ' ' espaco: tambem intransponivel. CUIDADO -- escrever "A A A" produz
        avenida / quarteirao / avenida, e nao tres avenidas seguidas. Para
        avenidas contiguas escreva "AAA".

REGRA DAS ARESTAS. Existe aresta de (i,j) para a vizinha ortogonal se ambas
sao transponiveis E ambas permitem aquele sentido de movimento. Compor a
permissao das duas pontas mantem a regra local e simetrica de escrever.
"""

from algoritmos.grafo import Grafo, haversine
from algoritmos.semaforo import Semaforo

PASSO_ID = 10_000      # mesmo esquema de `cidade_exemplo.no_da_celula`

LIVRE, LESTE, OESTE, NORTE, SUL = "livre", "leste", "oeste", "norte", "sul"

# tipo -> (velocidade km/h, restricao horizontal, restricao vertical, semaforo)
TIPOS = {
    ".": (30.0, LIVRE, LIVRE, False),
    "A": (50.0, LIVRE, LIVRE, False),
    "S": (30.0, LIVRE, LIVRE, True),
    ">": (30.0, LESTE, LIVRE, False),
    "<": (30.0, OESTE, LIVRE, False),
    "^": (30.0, LIVRE, NORTE, False),
    "v": (30.0, LIVRE, SUL, False),
}
INTRANSPONIVEIS = {"#", " "}


class MatrizInvalida(ValueError):
    pass


def no_da_celula(i, j):
    """(linha, coluna) -> identificador inteiro do cruzamento."""
    return i * PASSO_ID + j


def celula_do_no(identificador):
    return divmod(identificador, PASSO_ID)


class MatrizMapa:
    """Mapa em grade. Linha 0 e a mais ao SUL; coluna 0, a mais a OESTE."""

    def __init__(self, celulas, lat0=-23.5500, lon0=-46.6400,
                 espacamento_graus=0.0009, semaforos=None):
        if not celulas or not celulas[0]:
            raise MatrizInvalida("matriz vazia")
        largura = len(celulas[0])
        for numero, linha in enumerate(celulas):
            if len(linha) != largura:
                raise MatrizInvalida(
                    f"linha {numero} tem {len(linha)} celulas, esperado {largura}"
                )
            for coluna, simbolo in enumerate(linha):
                if simbolo not in TIPOS and simbolo not in INTRANSPONIVEIS:
                    raise MatrizInvalida(
                        f"simbolo desconhecido {simbolo!r} em ({numero}, {coluna})"
                    )
        self.celulas = [list(linha) for linha in celulas]
        self.altura = len(self.celulas)
        self.largura = largura
        self.lat0, self.lon0 = lat0, lon0
        self.espacamento = espacamento_graus
        # Temporizacao por celula; as marcadas com "S" usam o padrao.
        self.semaforos = dict(semaforos or {})

    # ------------------------------------------------------------- leitura

    @classmethod
    def de_texto(cls, texto, **kwargs):
        """Le a matriz de um bloco de texto, ignorando comentarios e vazios.

        A primeira linha do texto e a de cima no desenho, que corresponde ao
        NORTE -- invertemos para que a linha 0 fique ao sul, como manda a
        convencao geografica de latitude crescente.
        """
        linhas = [linha.rstrip("\n") for linha in texto.splitlines()
                  if linha.strip() and not linha.lstrip().startswith("//")]
        if not linhas:
            raise MatrizInvalida("texto sem nenhuma linha de mapa")
        largura = max(len(linha) for linha in linhas)
        linhas = [linha.ljust(largura) for linha in linhas]   # preenche com vazio
        return cls(list(reversed(linhas)), **kwargs)

    def para_texto(self):
        return "\n".join("".join(linha) for linha in reversed(self.celulas))

    def simbolo(self, i, j):
        return self.celulas[i][j]

    def transponivel(self, i, j):
        return (0 <= i < self.altura and 0 <= j < self.largura
                and self.celulas[i][j] not in INTRANSPONIVEIS)

    def semaforo_de(self, i, j):
        """Semaforo da celula, ou None."""
        if (i, j) in self.semaforos:
            return self.semaforos[(i, j)]
        if self.transponivel(i, j) and TIPOS[self.celulas[i][j]][3]:
            return Semaforo()
        return None

    def coordenadas(self, i, j):
        return (self.lat0 + i * self.espacamento, self.lon0 + j * self.espacamento)

    # ------------------------------------------------------------- escrita

    def definir(self, i, j, simbolo):
        if simbolo not in TIPOS and simbolo not in INTRANSPONIVEIS:
            raise MatrizInvalida(f"simbolo desconhecido: {simbolo!r}")
        self.celulas[i][j] = simbolo

    def definir_semaforo(self, i, j, vermelho, ciclo):
        self.semaforos[(i, j)] = Semaforo(vermelho, ciclo)

    # ------------------------------------------------- conversao para grafo

    def _permite(self, i, j, sentido):
        """A celula autoriza movimento neste sentido?"""
        _vel, horizontal, vertical, _sem = TIPOS[self.celulas[i][j]]
        restricao = horizontal if sentido in (LESTE, OESTE) else vertical
        return restricao in (LIVRE, sentido)

    def para_grafo(self, considerar_semaforos=True):
        """Constroi o grafo ponderado direcionado.

        Peso da aresta = tempo de percurso + atraso esperado no semaforo do
        cruzamento de CHEGADA. O atraso entra na aresta que chega porque e ali
        que o veiculo espera; sair de um cruzamento semaforizado nao custa.

        A velocidade do trecho e a MENOR das duas celulas: um trecho que liga
        avenida a rua local e percorrido na condicao mais restritiva.
        """
        grafo = Grafo()
        for i in range(self.altura):
            for j in range(self.largura):
                if self.transponivel(i, j):
                    grafo.adicionar_no(no_da_celula(i, j), *self.coordenadas(i, j))

        vizinhancas = ((0, 1, LESTE, OESTE), (1, 0, NORTE, SUL))
        for i in range(self.altura):
            for j in range(self.largura):
                if not self.transponivel(i, j):
                    continue
                for di, dj, ida, volta in vizinhancas:
                    vi, vj = i + di, j + dj
                    if not self.transponivel(vi, vj):
                        continue

                    lat1, lon1 = self.coordenadas(i, j)
                    lat2, lon2 = self.coordenadas(vi, vj)
                    metros = haversine(lat1, lon1, lat2, lon2)
                    kmh = min(TIPOS[self.celulas[i][j]][0],
                              TIPOS[self.celulas[vi][vj]][0])
                    segundos = metros / (kmh / 3.6)

                    if self._permite(i, j, ida) and self._permite(vi, vj, ida):
                        atraso = 0.0
                        if considerar_semaforos:
                            sinal = self.semaforo_de(vi, vj)
                            atraso = sinal.atraso if sinal else 0.0
                        grafo.adicionar_aresta(no_da_celula(i, j),
                                               no_da_celula(vi, vj),
                                               segundos + atraso)

                    if self._permite(i, j, volta) and self._permite(vi, vj, volta):
                        atraso = 0.0
                        if considerar_semaforos:
                            sinal = self.semaforo_de(i, j)
                            atraso = sinal.atraso if sinal else 0.0
                        grafo.adicionar_aresta(no_da_celula(vi, vj),
                                               no_da_celula(i, j),
                                               segundos + atraso)

        return grafo

    # ------------------------------------------------------------- resumo

    def estatisticas(self):
        contagem = {}
        for linha in self.celulas:
            for simbolo in linha:
                contagem[simbolo] = contagem.get(simbolo, 0) + 1
        semaforizados = sum(
            1 for i in range(self.altura) for j in range(self.largura)
            if self.semaforo_de(i, j) is not None
        )
        return {
            "altura": self.altura, "largura": self.largura,
            "celulas": self.altura * self.largura,
            "transponiveis": sum(contagem.get(s, 0) for s in TIPOS),
            "semaforos": semaforizados,
            "por_simbolo": contagem,
        }

    def __repr__(self):
        return f"MatrizMapa({self.altura}x{self.largura})"
