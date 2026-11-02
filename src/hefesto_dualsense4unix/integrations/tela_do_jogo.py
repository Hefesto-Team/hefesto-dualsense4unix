"""A tela do jogo em cinco números: o dano, o clarão, o escuro, o tremor e a saturação.

Cada quadro que a fonte entrega (o portal de captura do sistema) vira uma grade de 32 por 18
cores médias, e da grade e da anterior saem os cinco sinais de ``jogo.tela``, de 0 a 1.
Nenhum pixel sai daqui: uma região declarada pela receita (a barra de vida) publica só a fração
da cor declarada. Sem assinante a fonte não abre; sem fonte, ou com a fonte caída, o tópico publica
os cinco como ``None`` (ausente), nunca zero, e tenta de novo sozinho.
"""
from __future__ import annotations

import math
import re
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

GRADE_X = 32
GRADE_Y = 18
HZ_DA_TELA = 15
TOPICO_DA_TELA = "jogo.tela"
SINAIS = ("dano", "flash", "escuro", "tremor", "saturacao")
REGIOES_POR_RECEITA = 8
AMOSTRAS_DA_REGIAO = 64
ALCANCE_DO_TREMOR = 2
GANHO_DO_DANO = 3.0
GANHO_DO_FLASH = 2.0
NOME_DA_REGIAO = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
CANAIS: Mapping[str, tuple[int, int, int, int]] = {
    "BGRx": (2, 1, 0, 4),
    "BGRA": (2, 1, 0, 4),
    "RGBx": (0, 1, 2, 4),
    "RGBA": (0, 1, 2, 4),
    "RGB": (0, 1, 2, 3),
    "BGR": (2, 1, 0, 3),
}

Cor = tuple[float, float, float]
Grade = tuple[Cor, ...]


class TelaRecusadaError(Exception):
    """A receita ou o quadro fora da forma; ``frase`` diz o porquê."""

    def __init__(self, frase: str) -> None:
        super().__init__(frase)
        self.frase = frase


@dataclass(frozen=True)
class Quadro:
    """Um quadro cru: ``passo`` bytes por linha, no formato de ``CANAIS``."""

    largura: int
    altura: int
    passo: int
    formato: str
    dados: bytes

    def __post_init__(self) -> None:
        if self.formato not in CANAIS:
            raise TelaRecusadaError(f"O formato «{self.formato}» não é um dos conhecidos.")
        bpp = CANAIS[self.formato][3]
        if self.largura < 1 or self.altura < 1 or self.passo < self.largura * bpp:
            raise TelaRecusadaError("O quadro não tem a forma que declara.")
        if len(self.dados) < self.passo * (self.altura - 1) + self.largura * bpp:
            raise TelaRecusadaError("O quadro veio menor do que declara.")

    def cor(self, x: int, y: int) -> Cor:
        r, g, b, bpp = CANAIS[self.formato]
        i = y * self.passo + x * bpp
        d = self.dados
        return d[i + r] / 255.0, d[i + g] / 255.0, d[i + b] / 255.0


def reduzir(quadro: Quadro) -> Grade:
    """A grade 32 por 18, por linhas: em cada célula, a média de quatro amostras espalhadas."""
    celulas: list[Cor] = []
    for gy in range(GRADE_Y):
        ys = [min(quadro.altura - 1, int((gy + f) * quadro.altura / GRADE_Y))
              for f in (0.25, 0.75)]
        for gx in range(GRADE_X):
            xs = [min(quadro.largura - 1, int((gx + f) * quadro.largura / GRADE_X))
                  for f in (0.25, 0.75)]
            soma_r = soma_g = soma_b = 0.0
            for y in ys:
                for x in xs:
                    r, g, b = quadro.cor(x, y)
                    soma_r += r
                    soma_g += g
                    soma_b += b
            celulas.append((soma_r / 4, soma_g / 4, soma_b / 4))
    return tuple(celulas)


def _luma(c: Cor) -> float:
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def _vermelho(c: Cor) -> float:
    return max(0.0, c[0] - max(c[1], c[2]))


def _na_borda(i: int) -> bool:
    x, y = i % GRADE_X, i // GRADE_X
    return x < 3 or x >= GRADE_X - 3 or y < 2 or y >= GRADE_Y - 2


def _limitar(valor: float) -> float:
    return min(1.0, max(0.0, valor))


def deslocamento(antes: Sequence[float], agora: Sequence[float],
                 alcance: int = ALCANCE_DO_TREMOR) -> tuple[int, int]:
    """O deslocamento global (em células) que melhor leva ``antes`` a ``agora``; ``(0, 0)``
    quando nenhum outro é claramente melhor."""
    def erro(dx: int, dy: int) -> float:
        soma, n = 0.0, 0
        for y in range(alcance, GRADE_Y - alcance):
            for x in range(alcance, GRADE_X - alcance):
                soma += abs(agora[y * GRADE_X + x] - antes[(y - dy) * GRADE_X + (x - dx)])
                n += 1
        return soma / n

    parado = erro(0, 0)
    melhor, onde = parado, (0, 0)
    for dy in range(-alcance, alcance + 1):
        for dx in range(-alcance, alcance + 1):
            if (dx, dy) != (0, 0) and (e := erro(dx, dy)) < melhor:
                melhor, onde = e, (dx, dy)
    if parado < 0.02 or melhor > parado * 0.5:
        return 0, 0
    return onde


def sinais(antes: Grade | None, agora: Grade) -> dict[str, float]:
    """Os cinco sinais, de 0 a 1. Sem quadro anterior, o que depende de mudança é 0."""
    luma = [_luma(c) for c in agora]
    media = sum(luma) / len(luma)
    saturacao = sum((max(c) - min(c)) / max(c) if max(c) > 0 else 0.0
                    for c in agora) / len(agora)
    borda = [i for i in range(len(agora)) if _na_borda(i)]
    vermelho = sum(_vermelho(agora[i]) for i in borda) / len(borda)
    dano = flash = tremor = 0.0
    if antes is not None:
        luma_antes = [_luma(c) for c in antes]
        flash = _limitar(GANHO_DO_FLASH * (media - sum(luma_antes) / len(luma_antes)))
        vermelho_antes = sum(_vermelho(antes[i]) for i in borda) / len(borda)
        dano = _limitar(GANHO_DO_DANO * (vermelho - vermelho_antes))
        dx, dy = deslocamento(luma_antes, luma)
        tremor = _limitar(math.hypot(dx, dy) / math.hypot(ALCANCE_DO_TREMOR, ALCANCE_DO_TREMOR))
    return {"dano": dano, "flash": flash, "escuro": _limitar(1.0 - media),
            "tremor": tremor, "saturacao": _limitar(saturacao)}


@dataclass(frozen=True)
class Regiao:
    """Uma região da tela que a receita declara (frações da tela) e a cor que a enche."""

    nome: str
    x: float
    y: float
    largura: float
    altura: float
    cor: tuple[int, int, int]
    tolerancia: int = 48


def regioes_da_receita(lista: Sequence[Mapping[str, Any]]) -> tuple[Regiao, ...]:
    """Valida as regiões declaradas; recusa com :class:`TelaRecusadaError`."""
    if len(lista) > REGIOES_POR_RECEITA:
        raise TelaRecusadaError(f"A receita declara até {REGIOES_POR_RECEITA} regiões.")
    regioes: list[Regiao] = []
    for linha in lista:
        try:
            nome = str(linha["nome"])
            x, y = float(linha["x"]), float(linha["y"])
            largura, altura = float(linha["largura"]), float(linha["altura"])
            cor = tuple(int(v) for v in linha["cor"])
            tolerancia = int(linha.get("tolerancia", 48))
        except (KeyError, TypeError, ValueError) as exc:
            raise TelaRecusadaError("Uma região da receita não tem a forma declarada.") from exc
        if not NOME_DA_REGIAO.match(nome):
            raise TelaRecusadaError(f"O nome «{nome}» não serve para uma região.")
        if (len(cor) != 3 or any(not 0 <= v <= 255 for v in cor)
                or not 0 <= tolerancia <= 255):
            raise TelaRecusadaError(f"A cor de «{nome}» precisa de três valores de 0 a 255.")
        if (min(x, y) < 0 or largura <= 0 or altura <= 0
                or x + largura > 1 or y + altura > 1):
            raise TelaRecusadaError(f"«{nome}» sai da tela.")
        regioes.append(Regiao(nome, x, y, largura, altura, (cor[0], cor[1], cor[2]), tolerancia))
    if len({r.nome for r in regioes}) != len(regioes):
        raise TelaRecusadaError("A receita repete o nome de uma região.")
    return tuple(regioes)


def fracao(quadro: Quadro, regiao: Regiao, amostras: int = AMOSTRAS_DA_REGIAO) -> float:
    """A fração de 0 a 1 da linha do meio da região que tem a cor declarada."""
    y = min(quadro.altura - 1, int((regiao.y + regiao.altura / 2) * quadro.altura))
    alvo = [v / 255.0 for v in regiao.cor]
    limite = regiao.tolerancia / 255.0
    cheias = 0
    for i in range(amostras):
        x = min(quadro.largura - 1,
                int((regiao.x + regiao.largura * (i + 0.5) / amostras) * quadro.largura))
        if all(abs(a - b) <= limite for a, b in zip(quadro.cor(x, y), alvo, strict=True)):
            cheias += 1
    return cheias / amostras


class TelaDoJogo:
    """Guarda a grade anterior e transforma cada quadro na carga de ``jogo.tela``."""

    def __init__(self, regioes: Sequence[Regiao] = (),
                 relogio: Callable[[], float] = time.monotonic) -> None:
        self.regioes = tuple(regioes)
        self._relogio = relogio
        self._antes: Grade | None = None

    def medir(self, quadro: Quadro) -> dict[str, Any]:
        grade = reduzir(quadro)
        carga: dict[str, Any] = {"t": self._relogio(), **sinais(self._antes, grade)}
        self._antes = grade
        if self.regioes:
            carga["regioes"] = {r.nome: fracao(quadro, r) for r in self.regioes}
        return carga

    def ausente(self) -> dict[str, Any]:
        self._antes = None
        carga: dict[str, Any] = {"t": self._relogio(), **dict.fromkeys(SINAIS)}
        if self.regioes:
            carga["regioes"] = {r.nome: None for r in self.regioes}
        return carga


class FonteDaTela(Protocol):
    """A fonte dos quadros (o portal de captura). ``abrir`` devolve se abriu; ``quadro``
    devolve ``None`` quando a fonte caiu."""

    def abrir(self) -> bool: ...

    def quadro(self) -> Quadro | None: ...

    def fechar(self) -> None: ...


class Captura:
    """Abre a fonte só com assinante e publica um quadro por passo; a fonte que falta ou cai
    vira ``jogo.tela`` ausente uma vez, e a próxima tentativa sai depois de ``espera``."""

    def __init__(self, fonte: FonteDaTela, tela: TelaDoJogo, *,
                 publicar: Callable[[dict[str, Any]], None],
                 assinantes: Callable[[], int], espera: float = 2.0,
                 relogio: Callable[[], float] = time.monotonic) -> None:
        self.fonte = fonte
        self.tela = tela
        self._publicar = publicar
        self._assinantes = assinantes
        self._espera = espera
        self._relogio = relogio
        self.aberta = False
        self._proxima = 0.0
        self._ausente_dito = False

    def _cair(self) -> None:
        if self.aberta:
            self.fonte.fechar()
        self.aberta = False
        self._proxima = self._relogio() + self._espera
        if not self._ausente_dito:
            self._ausente_dito = True
            self._publicar(self.tela.ausente())

    def passo(self) -> None:
        if self._assinantes() <= 0:
            if self.aberta:
                self.fonte.fechar()
                self.aberta = False
            self._ausente_dito = False
            return
        if not self.aberta:
            if self._relogio() < self._proxima:
                return
            try:
                self.aberta = self.fonte.abrir()
            except (OSError, RuntimeError):
                self.aberta = False
            if not self.aberta:
                self._cair()
                return
        try:
            quadro = self.fonte.quadro()
        except (OSError, RuntimeError, TelaRecusadaError):
            quadro = None
        if quadro is None:
            self._cair()
            return
        self._ausente_dito = False
        self._publicar(self.tela.medir(quadro))


__all__ = [
    "GRADE_X",
    "GRADE_Y",
    "HZ_DA_TELA",
    "SINAIS",
    "TOPICO_DA_TELA",
    "Captura",
    "FonteDaTela",
    "Quadro",
    "Regiao",
    "TelaDoJogo",
    "TelaRecusadaError",
    "deslocamento",
    "fracao",
    "reduzir",
    "regioes_da_receita",
    "sinais",
]
