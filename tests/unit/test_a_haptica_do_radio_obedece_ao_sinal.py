"""A-HAPTICA-DO-RADIO-OBEDECE-AO-SINAL-DO-JOGO-01 — o rádio só leva o que tem sinal.

**A causa, medida em 27/09/2026** (PRAGMATA no menu, os quatro no rádio): o
jogo abre um fluxo de quatro canais em cada um dos quatro endpoints e manda
SILÊNCIO EXATO por eles (RMS e pico 0). Para o daemon, «tocando» era «o fluxo
existe», e não «há sinal»: a ponte de pé em silêncio a 93,75 reports por
segundo foi o que afogou o rádio em 22/09, e o portão por evdev (20/09) e o
``quem_mexe`` (26/09) nasceram para não subir quatro pontes mudas.

**A cura:** a ponte escuta o monitor o tempo todo (ler é local) e só escreve o
bloco que tem sinal nos canais que o arranjo leva — 3-4 na háptica, 1-2 no
som —, com UM silêncio depois do último sinal. A partida é o dono do fluxo no
endpoint (o cliente do servidor de som), e não quem tem
``STEAM_COMPAT_DATA_PATH`` no ambiente; e a volta acorda pelo fluxo que nasce,
avisado pelo retrato do som, sem vigia de 0,4 s.

O mundo destas réguas é de mentira e publica o que o real publica: PCM s16le
entrelaçado de quatro canais a 48 kHz (o que o ``pw-record`` entrega do monitor
do endpoint), um fd de escrita por controle no lugar do hidraw, e a linha curta
do ``pactl`` com o índice do cliente dono de cada fluxo. Nenhum aparelho,
nenhum servidor de som. Endereços da faixa forjada ``aa:bb:cc``.
"""

from __future__ import annotations

import os
import struct
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import alto_falante_bt as af
from hefesto_dualsense4unix.integrations import haptica_bt

#: O tamanho do report da háptica pelo rádio (o ``0x32``) e onde o bloco mora.
TAMANHO_032 = af.TAMANHO_DO_DEGRAU[0x32]
BLOCO_032 = slice(13, 13 + af.BYTES_DO_BLOCO_HAPTICO)


def _bloco_de_pcm(*, canais_com_sinal: tuple[int, ...] = (), amplitude: int = 20000) -> bytes:
    """512 quadros de quatro canais s16le: o que um bloco háptico consome.

    ``canais_com_sinal`` usa a numeração da sprint, de 1 a 4 (1-2 a voz, 3-4
    os motores). Sem canal nenhum, é o silêncio exato que o PRAGMATA manda no
    menu.
    """
    quadro = [0, 0, 0, 0]
    for canal in canais_com_sinal:
        quadro[canal - 1] = amplitude
    return struct.pack("<4h", *quadro) * af.QUADROS_POR_BLOCO_HAPTICO


SILENCIO = _bloco_de_pcm()
MOTOR = _bloco_de_pcm(canais_com_sinal=(3, 4))


def _fonte(blocos: list[bytes]) -> Any:
    """A fonte do monitor: um bloco por leitura, e ``b""`` quando o jogo fecha."""
    fila = list(blocos)

    def _ler(_quantos: int) -> bytes:
        return fila.pop(0) if fila else b""

    return _ler


def _bomba_da_haptica(blocos: list[bytes], *, so_com_sinal: bool = True) -> tuple[Any, list[bytes]]:
    escritas: list[bytes] = []

    def _escritor(report: bytes) -> int:
        escritas.append(report)
        return len(report)

    bomba = af.BombaDeSomPeloRadio(
        arranjo=af.ARRANJO_HAPTICA_032,
        fonte=lambda _n: b"",
        fonte_haptica=_fonte(blocos),
        escritor=_escritor,
        seco=False,
        so_com_sinal=so_com_sinal,
    )
    return bomba, escritas


# ---------------------------------------------------------------------------
# 1. A bomba: silêncio não vai, sinal vai, e um silêncio fecha
# ---------------------------------------------------------------------------


class TestORadioSoLevaOQueTemSinal:
    def test_o_silencio_exato_do_jogo_nao_manda_nada(self) -> None:
        """O menu do PRAGMATA: o fluxo existe, e o rádio fica livre.

        MORDIDA: troque o critério por «o fluxo existe» (faça ``_vale_mandar``
        devolver ``True``) — o silêncio passa a mandar 93,75 reports por
        segundo, o afogamento de 22/09.
        """
        bomba, escritas = _bomba_da_haptica([SILENCIO] * 8)
        bomba.rodar(segundos=10)
        assert escritas == [], f"o silêncio foi ao rádio: {len(escritas)} reports"
        assert bomba.contagem.reports_calados == 8
        assert bomba.contagem.reports_montados == 0

    def test_o_sinal_vai_no_bloco_dele_e_um_silencio_fecha(self) -> None:
        """Dois blocos com motor no meio de silêncio: vão os dois e UM silêncio.

        O silêncio depois do último sinal é o que faz o motor parar no zero em
        vez de ficar no último valor. MORDIDA: tire o ramo ``_mandou_sinal`` de
        ``_vale_mandar`` — saem dois reports, e o motor fica no último valor.
        """
        bomba, escritas = _bomba_da_haptica(
            [SILENCIO, SILENCIO, MOTOR, MOTOR, SILENCIO, SILENCIO, SILENCIO]
        )
        bomba.rodar(segundos=10)
        assert len(escritas) == 3, f"eram 2 com sinal e 1 silêncio: {len(escritas)}"
        assert all(len(r) == TAMANHO_032 for r in escritas)
        assert escritas[0][BLOCO_032] != bytes(64), "o primeiro bloco com sinal saiu mudo"
        assert escritas[1][BLOCO_032] != bytes(64)
        assert escritas[2][BLOCO_032] == haptica_bt.bloco_de_silencio(), (
            "depois do último sinal tem de ir o bloco de silêncio"
        )
        assert bomba.contagem.reports_calados == 4

    def test_a_sequencia_so_anda_com_o_que_foi(self) -> None:
        """Para o firmware, o fluxo PAUSOU: o nibble e o contador seguem de onde pararam."""
        bomba, escritas = _bomba_da_haptica(
            [MOTOR, SILENCIO, SILENCIO, SILENCIO, SILENCIO, MOTOR, SILENCIO]
        )
        bomba.rodar(segundos=10)
        assert [r[1] >> 4 for r in escritas] == [0, 1, 2, 3]
        assert [r[10] for r in escritas] == [0, 1, 2, 3], "o contador de quadros pulou"

    def test_o_ensaio_de_bancada_segue_mandando_o_que_pediu(self) -> None:
        """A bomba nasce sem o critério: o ensaio manda silêncio de propósito."""
        bomba, escritas = _bomba_da_haptica([SILENCIO] * 3, so_com_sinal=False)
        bomba.rodar(segundos=10)
        assert len(escritas) == 3


class TestOCriterioEDoArranjo:
    """Canais 3-4 na háptica, 1-2 no som — nunca um canal fixo."""

    def _bomba_do_som(self, pcm: list[bytes]) -> tuple[Any, list[bytes]]:
        escritas: list[bytes] = []

        class _Codificador:
            def codificar(self, _pcm: bytes) -> bytes:
                return b"\x01" * af.BYTES_POR_QUADRO_OPUS

        def _escritor(report: bytes) -> int:
            escritas.append(report)
            return len(report)

        bomba = af.BombaDeSomPeloRadio(
            arranjo=af.ARRANJO_035,
            fonte=_fonte(pcm),
            escritor=_escritor,
            seco=False,
            codificador=_Codificador(),
            so_com_sinal=True,
        )
        return bomba, escritas

    def test_o_alto_falante_com_som_nos_canais_1_e_2_manda(self) -> None:
        """O nó de som tem dois canais — os 1-2 da sprint —, e é o que o 0x35 leva.

        MORDIDA: fixe o critério nos motores (``_vale_mandar`` olhando só o
        ``haptico``) — o controle em modo som fica mudo.
        """
        voz = struct.pack("<2h", 12000, -12000) * af.AMOSTRAS_POR_QUADRO
        mudo = bytes(af.BYTES_DE_PCM_POR_QUADRO)
        bomba, escritas = self._bomba_do_som([mudo, voz, voz, mudo, mudo])
        bomba.rodar(segundos=10)
        assert len(escritas) == 3, f"eram 2 com som e 1 silêncio: {len(escritas)}"
        assert all(r[0] == 0x35 for r in escritas)

    def test_o_alto_falante_mudo_nao_manda(self) -> None:
        mudo = bytes(af.BYTES_DE_PCM_POR_QUADRO)
        bomba, escritas = self._bomba_do_som([mudo] * 5)
        bomba.rodar(segundos=10)
        assert escritas == []

    def test_a_voz_do_jogo_nao_liga_os_motores(self) -> None:
        """Na háptica, sinal só nos canais 1-2 do endpoint é a voz: o motor não vai.

        É a conta de :mod:`haptica_bt` (só os canais 3-4 viram bloco), e o
        critério lê o bloco — por isso ele é o do arranjo.
        """
        voz = _bloco_de_pcm(canais_com_sinal=(1, 2))
        bomba, escritas = _bomba_da_haptica([voz] * 4)
        bomba.rodar(segundos=10)
        assert escritas == []


# ---------------------------------------------------------------------------
# 2. A ponte do produto liga o critério
# ---------------------------------------------------------------------------


def _ler_tudo(fd: int) -> bytes:
    pedacos = []
    os.set_blocking(fd, False)
    while True:
        try:
            pedaco = os.read(fd, 65536)
        except BlockingIOError:
            break
        if not pedaco:
            break
        pedacos.append(pedaco)
    return b"".join(pedacos)


def _esperar_a_corrida(ponte: Any, prazo_s: float = 10.0) -> None:
    import time

    fim = time.monotonic() + prazo_s
    while ponte._corrida_viva() and time.monotonic() < fim:
        time.sleep(0.01)
    assert not ponte._corrida_viva(), "a fonte secou e a ponte não terminou"


def test_a_ponte_do_produto_so_escreve_o_que_tem_sinal(monkeypatch: pytest.MonkeyPatch) -> None:
    """A ponte de verdade, com o laço de verdade, num fd de mentira no lugar do hidraw.

    MORDIDA: mude o padrão de ``so_com_sinal`` da ``PonteDeSomPorRadio`` para
    ``False`` — o silêncio do menu vai ao fd, report a report.
    """
    monkeypatch.setattr(af, "a_ponte_do_radio_pode_subir", lambda: (True, ""))
    leitura, escrita = os.pipe()
    try:
        ponte = af.PonteDeSomPorRadio(
            uniq="aa:bb:cc:00:00:03",
            abrir_hidraw=lambda: escrita,
            fonte_de_pcm=lambda _n: b"",
            arranjo=af.ARRANJO_HAPTICA_032,
            fonte_de_haptica=_fonte([SILENCIO] * 5 + [MOTOR] + [SILENCIO] * 5),
        )
        assert ponte.subir() is True, ponte.motivo
        _esperar_a_corrida(ponte)
        escrito = _ler_tudo(leitura)
    finally:
        os.close(leitura)
    assert len(escrito) == 2 * TAMANHO_032, (
        f"eram o sinal e um silêncio; foram {len(escrito) / TAMANHO_032:.1f} reports"
    )
    assert ponte.contagem is not None and ponte.contagem.reports_calados == 9
