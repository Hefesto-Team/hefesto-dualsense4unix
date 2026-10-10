"""O PCM da háptica vira bloco de rádio — HAPTICA-POR-RADIO-01, P2."""

from __future__ import annotations

import sys
from array import array
from dataclasses import dataclass, field

TAXA_DO_BLOCO = 3000
AMOSTRAS_POR_CANAL = 32
BYTES_DO_BLOCO = AMOSTRAS_POR_CANAL * 2

#: A entrada é a do endpoint do DualSense: 48 kHz, quatro canais, s16le.
TAXA_DE_ENTRADA = 48000
CANAIS_DE_ENTRADA = 4
CANAIS_DOS_MOTORES = (2, 3)

FATOR = TAXA_DE_ENTRADA // TAXA_DO_BLOCO

_PICO_INT16 = 32768
_PICO_INT8 = 127


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


def bloco_de_silencio() -> bytes:
    """64 bytes zerados: o bloco que não mexe os motores."""
    return bytes(BYTES_DO_BLOCO)


__all__ = [
    "AMOSTRAS_POR_CANAL",
    "BYTES_DO_BLOCO",
    "CANAIS_DOS_MOTORES",
    "FATOR",
    "TAXA_DO_BLOCO",
    "ConversorDeHaptica",
    "bloco_de_silencio",
]
