"""A háptica do rádio se converte sem pesar na ponte.

Com a fonte háptica ligada, a ponte do rádio converte PCM a cada relatório,
93 blocos por segundo por controle, com jogo tocando ou não. A conversão
andava amostra a amostra em Python e custava de 36 a 46 ms de CPU por
segundo, por controle, segurando o GIL que o laço do report e o do daemon
disputam.

Duas coisas se cobram aqui:

1. a saída não muda: a cópia literal do ``_dizimar`` antigo é a referência,
   e os blocos das duas se comparam byte a byte, com pedaços de tamanho
   ímpar, os extremos de ``int16`` e os ganhos 1,0 e 2,5;
2. o custo cai: no mesmo processo, sobre o mesmo segundo de PCM, o melhor de
   três da conversão nova é no máximo um terço do melhor de três da
   referência.
"""

from __future__ import annotations

import random
import struct
import time
from collections.abc import Callable

import pytest

from hefesto_dualsense4unix.integrations.haptica_bt import (
    BYTES_DO_BLOCO,
    CANAIS_DE_ENTRADA,
    FATOR,
    TAXA_DE_ENTRADA,
    ConversorDeHaptica,
)

LARGURA = 2 * CANAIS_DE_ENTRADA


class ConversorDeReferencia(ConversorDeHaptica):
    """O ``_dizimar`` de antes desta sprint, copiado literalmente."""

    def _dizimar(self, dados: bytes, quadros: int) -> bytes:
        largura = 2 * self.canais
        esq, dir_ = self.motores
        saida = bytearray()
        for inicio in range(0, quadros, FATOR):
            somas = [0, 0]
            for q in range(inicio, inicio + FATOR):
                base = q * largura
                for lado, canal in enumerate((esq, dir_)):
                    off = base + 2 * canal
                    somas[lado] += int.from_bytes(dados[off : off + 2], "little", signed=True)
            for soma in somas:
                saida.append(self._para_int8(soma / FATOR))
        return bytes(saida)


def _pcm(quadros: int, semente: int) -> bytes:
    """PCM s16le de quatro canais, aleatório, com os extremos de int16 semeados."""
    sorteio = random.Random(semente)
    amostras = [sorteio.randint(-32768, 32767) for _ in range(quadros * CANAIS_DE_ENTRADA)]
    for indice in range(0, len(amostras), 97):
        amostras[indice] = -32768
    for indice in range(5, len(amostras), 89):
        amostras[indice] = 32767
    for indice in range(2, min(len(amostras), FATOR * CANAIS_DE_ENTRADA * 4), CANAIS_DE_ENTRADA):
        amostras[indice] = 32767
    return struct.pack(f"<{len(amostras)}h", *amostras)


def _pedacos(pcm: bytes, semente: int) -> list[bytes]:
    """Pedaços de tamanho ímpar, para o resto atravessar a fronteira do quadro."""
    sorteio = random.Random(semente)
    pedacos: list[bytes] = []
    posicao = 0
    while posicao < len(pcm):
        tamanho = sorteio.randrange(1, 4097) | 1
        pedacos.append(pcm[posicao : posicao + tamanho])
        posicao += tamanho
    return pedacos


def _blocos(conversor: ConversorDeHaptica, pedacos: list[bytes]) -> list[bytes]:
    saida: list[bytes] = []
    for pedaco in pedacos:
        saida.extend(conversor.alimentar(pedaco))
    return saida


@pytest.mark.parametrize("ganho", [1.0, 2.5])
@pytest.mark.parametrize("semente", [7, 2026])
def test_a_saida_e_byte_a_byte_a_de_antes(ganho: float, semente: int) -> None:
    pcm = _pcm(TAXA_DE_ENTRADA // 2, semente)
    pedacos = _pedacos(pcm, semente + 1)
    assert any(len(pedaco) % LARGURA for pedaco in pedacos)
    novos = _blocos(ConversorDeHaptica(ganho=ganho), pedacos)
    antigos = _blocos(ConversorDeReferencia(ganho=ganho), pedacos)
    assert len(novos) == len(antigos) > 0
    assert all(len(bloco) == BYTES_DO_BLOCO for bloco in novos)
    assert novos == antigos


def test_os_extremos_de_int16_saturam_igual() -> None:
    quadro_max = struct.pack("<4h", 0, 0, 32767, -32768)
    quadro_min = struct.pack("<4h", 0, 0, -32768, 32767)
    pcm = (quadro_max * FATOR + quadro_min * FATOR) * (BYTES_DO_BLOCO // 4)
    for ganho in (1.0, 2.5):
        novos = _blocos(ConversorDeHaptica(ganho=ganho), [pcm])
        antigos = _blocos(ConversorDeReferencia(ganho=ganho), [pcm])
        assert novos == antigos and novos


def test_os_motores_trocados_saem_trocados() -> None:
    pcm = _pcm(FATOR * 64, 3)
    motores = (3, 2)
    novos = _blocos(ConversorDeHaptica(motores=motores), [pcm])
    antigos = _blocos(ConversorDeReferencia(motores=motores), [pcm])
    assert novos == antigos


def _melhor_de_tres(fabrica: Callable[[], ConversorDeHaptica], pedacos: list[bytes]) -> float:
    tempos: list[float] = []
    for _ in range(3):
        conversor = fabrica()
        comeco = time.process_time()
        _blocos(conversor, pedacos)
        tempos.append(time.process_time() - comeco)
    return min(tempos)


def test_o_custo_cai_para_um_terco_ou_menos() -> None:
    pcm = _pcm(TAXA_DE_ENTRADA, 11)
    pedacos = [pcm[i : i + 4096] for i in range(0, len(pcm), 4096)]
    referencia = _melhor_de_tres(ConversorDeReferencia, pedacos)
    nova = _melhor_de_tres(ConversorDeHaptica, pedacos)
    assert nova * 3 <= referencia, (
        f"a conversão nova custou {nova * 1000:.1f} ms contra {referencia * 1000:.1f} ms"
    )

