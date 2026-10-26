"""O PCM da háptica vira bloco de rádio — HAPTICA-POR-RADIO-01, P2."""

from __future__ import annotations

import sys
from array import array
from dataclasses import dataclass, field

TAXA_DO_BLOCO = 3000
AMOSTRAS_POR_CANAL = 32
BYTES_DO_BLOCO = AMOSTRAS_POR_CANAL * 2

TAXA_DE_ENTRADA = 48000
CANAIS_DE_ENTRADA = 4
CANAIS_DOS_MOTORES = (2, 3)

FATOR = TAXA_DE_ENTRADA // TAXA_DO_BLOCO

CANAIS_DA_FRENTE = (0, 1)
QUADROS_POR_BLOCO = AMOSTRAS_POR_CANAL * FATOR
QUADROS_DA_FRENTE_NO_SOM = 480

_PICO_INT16 = 32768
_PICO_INT8 = 127

_ESQUERDA_DA_FRENTE = [
    (i * QUADROS_POR_BLOCO) // QUADROS_DA_FRENTE_NO_SOM for i in range(QUADROS_DA_FRENTE_NO_SOM)
]
_DIREITA_DA_FRENTE = [min(j + 1, QUADROS_POR_BLOCO - 1) for j in _ESQUERDA_DA_FRENTE]
_PESO_DA_FRENTE = [
    ((i * QUADROS_POR_BLOCO) % QUADROS_DA_FRENTE_NO_SOM) / QUADROS_DA_FRENTE_NO_SOM
    for i in range(QUADROS_DA_FRENTE_NO_SOM)
]


def _reamostrar_um_canal(canal: array[int]) -> list[int]:
    return [
        int(canal[j] + (canal[k] - canal[j]) * w)
        for j, k, w in zip(_ESQUERDA_DA_FRENTE, _DIREITA_DA_FRENTE, _PESO_DA_FRENTE, strict=True)
    ]


def frente_reamostrada(esquerdo: array[int], direito: array[int]) -> bytes:
    """Os 512 quadros da frente a 48 kHz viram os 480 do som a 45 kHz (s16le, estéreo).

    Interpolação linear; silêncio exato devolve ``b""``, que para quem chama
    vale «nada a somar». O último quadro segura o valor, sem extrapolar além
    do bloco.
    """
    if not any(esquerdo) and not any(direito):
        return b""
    saida = array("h", bytes(QUADROS_DA_FRENTE_NO_SOM * 4))
    saida[0::2] = array("h", _reamostrar_um_canal(esquerdo))
    saida[1::2] = array("h", _reamostrar_um_canal(direito))
    if sys.byteorder == "big":
        saida.byteswap()
    return saida.tobytes()


def somar_com_saturacao(base: bytes, outro: bytes) -> bytes:
    """Soma dois PCM s16le do mesmo tamanho, amostra a amostra, saturando em int16.

    ``outro`` vazio devolve ``base`` como veio: a frente muda não custa conta.
    """
    if not outro or len(outro) != len(base):
        return base
    a = array("h")
    b = array("h")
    a.frombytes(base)
    b.frombytes(outro)
    if sys.byteorder == "big":
        a.byteswap()
        b.byteswap()
    for i, valor in enumerate(b):
        if valor:
            soma = a[i] + valor
            a[i] = 32767 if soma > 32767 else (-32768 if soma < -32768 else soma)
    if sys.byteorder == "big":
        a.byteswap()
    return a.tobytes()


def tem_sinal_na_frente(
    pcm: bytes | bytearray | memoryview, canais: int = CANAIS_DE_ENTRADA
) -> bool:
    """O PCM do endpoint tem sinal nos canais 1-2 (a frente)? Não olha os motores."""
    quadro = 2 * canais
    inteiro = len(pcm) - len(pcm) % quadro
    if canais < 3 or inteiro <= 0:
        return False
    amostras = memoryview(pcm)[:inteiro].cast("h")
    frente = amostras[0::canais].tobytes() + amostras[1::canais].tobytes()
    return frente.count(0) < len(frente)


@dataclass
class ConversorDeHaptica:
    """Recebe PCM em pedaços de qualquer tamanho e devolve blocos inteiros."""

    ganho: float = 1.0
    canais: int = CANAIS_DE_ENTRADA
    motores: tuple[int, int] = CANAIS_DOS_MOTORES
    _resto: bytearray = field(default_factory=bytearray, repr=False)
    _pendentes: bytearray = field(default_factory=bytearray, repr=False)

    def alimentar(self, pcm: bytes | bytearray | memoryview) -> list[bytes]:
        """PCM s16le entrelaçado → blocos de 64 B prontos para o report."""
        dados = bytes(self._resto) + bytes(pcm)
        largura = 2 * self.canais
        quadros = len(dados) // largura
        sobra = quadros % FATOR
        usaveis = quadros - sobra
        self._resto = bytearray(dados[usaveis * largura :])
        if usaveis:
            self._pendentes += self._dizimar(dados[: usaveis * largura], usaveis)

        blocos: list[bytes] = []
        while len(self._pendentes) >= BYTES_DO_BLOCO:
            blocos.append(bytes(self._pendentes[:BYTES_DO_BLOCO]))
            del self._pendentes[:BYTES_DO_BLOCO]
        return blocos

    def _dizimar(self, dados: bytes, quadros: int) -> bytes:
        """Média de cada janela de 16 quadros, nos dois motores.

        O PCM se lê uma vez como ``array("h")`` e cada motor sai por um
        fatiamento com passo: é o caminho quente da ponte, 93 blocos por
        segundo por controle no rádio, com jogo tocando ou não.
        """
        amostras = array("h")
        amostras.frombytes(dados[: quadros * 2 * self.canais])
        if sys.byteorder == "big":
            amostras.byteswap()
        esq, dir_ = self.motores
        canal_esq = amostras[esq :: self.canais]
        canal_dir = amostras[dir_ :: self.canais]
        para_int8 = self._para_int8
        saida = bytearray()
        for inicio in range(0, quadros, FATOR):
            fim = inicio + FATOR
            saida.append(para_int8(sum(canal_esq[inicio:fim]) / FATOR))
            saida.append(para_int8(sum(canal_dir[inicio:fim]) / FATOR))
        return bytes(saida)

    def _para_int8(self, valor: float) -> int:
        escalado = round(valor * self.ganho * _PICO_INT8 / _PICO_INT16)
        if escalado > _PICO_INT8:
            escalado = _PICO_INT8
        elif escalado < -_PICO_INT8:
            escalado = -_PICO_INT8
        return escalado & 0xFF

    def limpar(self) -> None:
        """Esquece o resto — o jogo fechou, e o próximo não herda meia amostra."""
        self._resto.clear()
        self._pendentes.clear()


@dataclass
class SeparadorDaFrente:
    """A frente (canais 1-2) do endpoint, em blocos alinhados aos da háptica.

    Corre ao lado do :class:`ConversorDeHaptica` sem entrar nele: o conversor é
    o caminho quente dos motores e tem o custo medido. ``alimentar`` recebe o
    mesmo PCM e devolve, a cada 512 quadros fechados, a frente daquele bloco
    pronta para somar ao som (480 quadros, s16le estéreo; ``b""`` = muda).
    Sem ganho nenhum: o ganho da vibração é dos motores.
    """

    canais: int = CANAIS_DE_ENTRADA
    _esq: array[int] = field(default_factory=lambda: array("h"), repr=False)
    _dir: array[int] = field(default_factory=lambda: array("h"), repr=False)
    _resto: bytearray = field(default_factory=bytearray, repr=False)

    def alimentar(self, pcm: bytes | bytearray | memoryview) -> list[bytes]:
        if self.canais < 3:
            return []
        dados = bytes(self._resto) + bytes(pcm)
        largura = 2 * self.canais
        inteiros = len(dados) // largura
        self._resto = bytearray(dados[inteiros * largura :])
        if inteiros:
            amostras = array("h")
            amostras.frombytes(dados[: inteiros * largura])
            if sys.byteorder == "big":
                amostras.byteswap()
            self._esq.extend(amostras[CANAIS_DA_FRENTE[0] :: self.canais])
            self._dir.extend(amostras[CANAIS_DA_FRENTE[1] :: self.canais])
        frentes: list[bytes] = []
        while len(self._esq) >= QUADROS_POR_BLOCO:
            frentes.append(
                frente_reamostrada(self._esq[:QUADROS_POR_BLOCO], self._dir[:QUADROS_POR_BLOCO])
            )
            del self._esq[:QUADROS_POR_BLOCO]
            del self._dir[:QUADROS_POR_BLOCO]
        return frentes

    def limpar(self) -> None:
        self._resto.clear()
        del self._esq[:]
        del self._dir[:]


def bloco_de_silencio() -> bytes:
    """64 bytes zerados: o bloco que não mexe os motores."""
    return bytes(BYTES_DO_BLOCO)


__all__ = [
    "AMOSTRAS_POR_CANAL",
    "BYTES_DO_BLOCO",
    "CANAIS_DA_FRENTE",
    "CANAIS_DOS_MOTORES",
    "FATOR",
    "QUADROS_DA_FRENTE_NO_SOM",
    "QUADROS_POR_BLOCO",
    "TAXA_DO_BLOCO",
    "ConversorDeHaptica",
    "SeparadorDaFrente",
    "bloco_de_silencio",
    "frente_reamostrada",
    "somar_com_saturacao",
    "tem_sinal_na_frente",
]
