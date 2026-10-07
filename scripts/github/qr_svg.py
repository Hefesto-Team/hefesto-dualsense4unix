"""QR code em SVG, sem dependência: modo byte, correção M, versões 1 a 15.

A página do produto mostra o QR do PIX a partir da chave que está no `.github/FUNDING.yml`; o Pages só instala
o `markdown-it-py`, então o código mora aqui em vez de pedir um pacote a mais. O desenho segue a norma ISO/IEC
18004 (finders, alinhamento, tempo, informação de formato e de versão, máscara de menor penalidade).

  svg_do_qr("https://exemplo.org/doar")  ->  '<svg ...>...</svg>'
  matriz("texto")                         ->  lista de linhas de bool (True = módulo escuro)
"""
from __future__ import annotations

from itertools import pairwise

# Nível M: (codewords de correção por bloco, [(blocos, codewords de dado por bloco), ...]).
_NIVEL_M: dict[int, tuple[int, list[tuple[int, int]]]] = {
    1: (10, [(1, 16)]),
    2: (16, [(1, 28)]),
    3: (26, [(1, 44)]),
    4: (18, [(2, 32)]),
    5: (24, [(2, 43)]),
    6: (16, [(4, 27)]),
    7: (18, [(4, 31)]),
    8: (22, [(2, 38), (2, 39)]),
    9: (22, [(3, 36), (2, 37)]),
    10: (26, [(4, 43), (1, 44)]),
    11: (30, [(1, 50), (4, 51)]),
    12: (22, [(6, 36), (2, 37)]),
    13: (22, [(8, 37), (1, 38)]),
    14: (24, [(4, 40), (5, 41)]),
    15: (24, [(5, 41), (5, 42)]),
}
_ALINHAMENTO: dict[int, list[int]] = {
    1: [], 2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30], 6: [6, 34], 7: [6, 22, 38], 8: [6, 24, 42],
    9: [6, 26, 46], 10: [6, 28, 50], 11: [6, 30, 54], 12: [6, 32, 58], 13: [6, 34, 62], 14: [6, 26, 46, 66],
    15: [6, 26, 48, 70],
}
VERSAO_MAXIMA = 15


def capacidade() -> int:
    """O maior texto, em bytes, que cabe (versão 15, nível M)."""
    return (_dados_da_versao(VERSAO_MAXIMA) * 8 - 4 - 16) // 8


def _dados_da_versao(versao: int) -> int:
    return sum(n * d for n, d in _NIVEL_M[versao][1])


def _tabelas_gf() -> tuple[list[int], list[int]]:
    exp = [0] * 512
    log = [0] * 256
    x = 1
    for i in range(255):
        exp[i] = x
        log[x] = i
        x <<= 1
        if x & 0x100:
            x ^= 0x11D
    for i in range(255, 512):
        exp[i] = exp[i - 255]
    return exp, log


_EXP, _LOG = _tabelas_gf()


def _mul(a: int, b: int) -> int:
    return 0 if a == 0 or b == 0 else _EXP[_LOG[a] + _LOG[b]]


def _resto_reed_solomon(dados: list[int], n: int) -> list[int]:
    gerador = [1]
    for i in range(n):
        proximo = [0] * (len(gerador) + 1)
        for j, c in enumerate(gerador):
            proximo[j] ^= c
            proximo[j + 1] ^= _mul(c, _EXP[i])
        gerador = proximo
    resto = [0] * n
    for byte in dados:
        fator = byte ^ resto[0]
        resto = [*resto[1:], 0]
        for i in range(n):
            resto[i] ^= _mul(gerador[i + 1], fator)
    return resto


def _codewords(dados: bytes, versao: int) -> list[int]:
    """Os dados em modo byte, completados e intercalados com a correção de erro."""
    bits: list[int] = []

    def junta(valor: int, quantos: int) -> None:
        bits.extend((valor >> (quantos - 1 - i)) & 1 for i in range(quantos))

    junta(0b0100, 4)
    junta(len(dados), 8 if versao < 10 else 16)
    for b in dados:
        junta(b, 8)
    total = _dados_da_versao(versao) * 8
    junta(0, min(4, total - len(bits)))
    junta(0, -len(bits) % 8)
    palavras = [int("".join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits), 8)]
    enchimento = (0xEC, 0x11)
    while len(palavras) < total // 8:
        palavras.append(enchimento[(len(palavras) - len(bits) // 8) % 2])
    ec, grupos = _NIVEL_M[versao]
    blocos: list[list[int]] = []
    inicio = 0
    for n, d in grupos:
        for _ in range(n):
            blocos.append(palavras[inicio:inicio + d])
            inicio += d
    correcoes = [_resto_reed_solomon(b, ec) for b in blocos]
    saida: list[int] = []
    for i in range(max(len(b) for b in blocos)):
        saida += [b[i] for b in blocos if i < len(b)]
    for i in range(ec):
        saida += [c[i] for c in correcoes]
    return saida


def _bit(valor: int, i: int) -> bool:
    return bool((valor >> i) & 1)


class _Desenho:
    def __init__(self, versao: int) -> None:
        self.n = 17 + 4 * versao
        self.versao = versao
        self.mod = [[False] * self.n for _ in range(self.n)]
        self.funcao = [[False] * self.n for _ in range(self.n)]
        self._funcoes()

    def _p(self, x: int, y: int, escuro: bool) -> None:
        self.mod[y][x] = escuro
        self.funcao[y][x] = True

    def _finder(self, cx: int, cy: int) -> None:
        for dy in range(-4, 5):
            for dx in range(-4, 5):
                x, y = cx + dx, cy + dy
                if 0 <= x < self.n and 0 <= y < self.n:
                    self._p(x, y, max(abs(dx), abs(dy)) not in (2, 4))

    def _alinhamento(self, cx: int, cy: int) -> None:
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                self._p(cx + dx, cy + dy, max(abs(dx), abs(dy)) != 1)

    def _funcoes(self) -> None:
        n = self.n
        for i in range(n):
            self._p(6, i, i % 2 == 0)
            self._p(i, 6, i % 2 == 0)
        self._finder(3, 3)
        self._finder(n - 4, 3)
        self._finder(3, n - 4)
        pos = _ALINHAMENTO[self.versao]
        for i, cy in enumerate(pos):
            for j, cx in enumerate(pos):
                if not ((i == 0 and j == 0) or (i == 0 and j == len(pos) - 1) or (i == len(pos) - 1 and j == 0)):
                    self._alinhamento(cx, cy)
        self.formato(0)
        self._versao()

    def formato(self, mascara: int) -> None:
        n = self.n
        dado = (0 << 3) | mascara  # nível M = 00
        resto = dado
        for _ in range(10):
            resto = (resto << 1) ^ ((resto >> 9) * 0x537)
        bits = ((dado << 10) | resto) ^ 0x5412
        for i in range(6):
            self._p(8, i, _bit(bits, i))
        self._p(8, 7, _bit(bits, 6))
        self._p(8, 8, _bit(bits, 7))
        self._p(7, 8, _bit(bits, 8))
        for i in range(9, 15):
            self._p(14 - i, 8, _bit(bits, i))
        for i in range(8):
            self._p(n - 1 - i, 8, _bit(bits, i))
        for i in range(8, 15):
            self._p(8, n - 15 + i, _bit(bits, i))
        self._p(8, n - 8, True)

    def _versao(self) -> None:
        if self.versao < 7:
            return
        resto = self.versao
        for _ in range(12):
            resto = (resto << 1) ^ ((resto >> 11) * 0x1F25)
        bits = (self.versao << 12) | resto
        for i in range(18):
            a, b = self.n - 11 + i % 3, i // 3
            self._p(a, b, _bit(bits, i))
            self._p(b, a, _bit(bits, i))

    def dados(self, palavras: list[int]) -> None:
        n = self.n
        i = 0
        direita = n - 1
        while direita >= 1:
            if direita == 6:  # a coluna de tempo não leva dado
                direita = 5
            for vert in range(n):
                for j in range(2):
                    x = direita - j
                    y = n - 1 - vert if ((direita + 1) & 2) == 0 else vert
                    if not self.funcao[y][x] and i < len(palavras) * 8:
                        self.mod[y][x] = _bit(palavras[i >> 3], 7 - (i & 7))
                        i += 1
            direita -= 2

    def mascara(self, qual: int) -> None:
        for y in range(self.n):
            for x in range(self.n):
                if self.funcao[y][x]:
                    continue
                inverte = (
                    (x + y) % 2 == 0, y % 2 == 0, x % 3 == 0, (x + y) % 3 == 0,
                    (x // 3 + y // 2) % 2 == 0, x * y % 2 + x * y % 3 == 0,
                    (x * y % 2 + x * y % 3) % 2 == 0, ((x + y) % 2 + x * y % 3) % 2 == 0,
                )[qual]
                if inverte:
                    self.mod[y][x] = not self.mod[y][x]

    def penalidade(self) -> int:
        n = self.n
        linhas = ["".join("1" if c else "0" for c in lin) for lin in self.mod]
        colunas = ["".join(linhas[y][x] for y in range(n)) for x in range(n)]
        total = 0
        for texto in linhas + colunas:
            corrida = 1
            for a, b in pairwise(texto):
                if a == b:
                    corrida += 1
                    continue
                total += corrida - 2 if corrida >= 5 else 0
                corrida = 1
            total += corrida - 2 if corrida >= 5 else 0
            enquadrado = "0000" + texto + "0000"
            total += 40 * (enquadrado.count("00001011101") + enquadrado.count("10111010000"))
        for y in range(n - 1):
            for x in range(n - 1):
                if linhas[y][x] == linhas[y][x + 1] == linhas[y + 1][x] == linhas[y + 1][x + 1]:
                    total += 3
        escuros = sum(lin.count("1") for lin in linhas)
        quantos = n * n
        total += 10 * (-(-abs(escuros * 20 - quantos * 10) // quantos) - 1)
        return total


def _versao_para(dados: bytes) -> int:
    for versao in range(1, VERSAO_MAXIMA + 1):
        cabecalho = 4 + (8 if versao < 10 else 16)
        if cabecalho + 8 * len(dados) <= _dados_da_versao(versao) * 8:
            return versao
    raise ValueError(f"texto grande demais para o QR ({len(dados)} bytes, o máximo é {capacidade()})")


def matriz(texto: str, mascara: int | None = None) -> list[list[bool]]:
    """Os módulos do QR (True = escuro); `mascara` força uma máscara (os testes), senão sai a de menor penalidade."""
    dados = texto.encode("utf-8")
    versao = _versao_para(dados)
    palavras = _codewords(dados, versao)
    melhor: _Desenho | None = None
    menor = 0
    for qual in range(8) if mascara is None else (mascara,):
        d = _Desenho(versao)
        d.dados(palavras)
        d.mascara(qual)
        d.formato(qual)
        pena = d.penalidade()
        if melhor is None or pena < menor:
            melhor, menor = d, pena
    assert melhor is not None
    return melhor.mod


def svg_do_qr(texto: str, rotulo: str = "QR code", borda: int = 4) -> str:
    """O QR em SVG de uma peça só: fundo branco, módulos pretos e a zona de silêncio de `borda` módulos."""
    mod = matriz(texto)
    n = len(mod)
    lado = n + 2 * borda
    tracos = []
    for y, linha in enumerate(mod):
        x = 0
        while x < n:
            if not linha[x]:
                x += 1
                continue
            ini = x
            while x < n and linha[x]:
                x += 1
            tracos.append(f"M{ini + borda} {y + borda}h{x - ini}v1h-{x - ini}z")
    rotulo = rotulo.replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {lado} {lado}" width="{lado * 6}" '
        f'height="{lado * 6}" role="img" aria-label="{rotulo}" shape-rendering="crispEdges">'
        f'<rect width="{lado}" height="{lado}" fill="#fff"/><path d="{"".join(tracos)}" fill="#000"/></svg>'
    )
