"""O-NATIVO-PELO-RADIO-NAO-APAGA-O-MOTOR-QUE-O-JOGO-ACENDE-01: a ponte só diz o estado que tem.

**A causa, medida em 31/10/2026** (a bomba como a ponte a monta, 50 quadros só de som com
sinal): 50 de 50 relatórios ``0x36`` levavam o bloco ``0x10`` com os flags a 0, e cada um é
uma soltura do motor (medido no aparelho em 26/10). Com o som do jogo no alto-falante pelo
rádio, o motor que o ``0x31`` do jogo acendia não durava um quadro.

**A cura:** o ``0x10`` neutro vai só junto do bloco ``0x12`` (sem ele a háptica não toca,
ensaio de 03/10); o quadro só de som sai sem o ``0x10`` (o som toca sem ele, mesmo ensaio),
e a cadeia sobe sem buraco. O ``common`` dado por quem chama vai em todo quadro.

Sem aparelho: o PCM é de mentira, o hidraw é um cano. Endereços da faixa forjada ``02:fe``.
"""

from __future__ import annotations

import os
import struct
import time
from collections.abc import Callable

import pytest

from hefesto_dualsense4unix.core import ds_output_report as rep
from hefesto_dualsense4unix.integrations import alto_falante_bt as af
from hefesto_dualsense4unix.integrations import dualsense_bt_audio as bta
from hefesto_dualsense4unix.integrations import haptica_bt as hb

TAG_ESTADO = af.tag_tlv(bta.BLOCO_SET_STATE)
TAG_HAPTICA = af.tag_tlv(bta.BLOCO_HAPTICS)
TAG_CONTROLE = af.tag_tlv(bta.BLOCO_AUDIO_CONTROL)
TAG_SOM = af.tag_tlv(bta.BLOCO_SPEAKER)
FLAGS_DO_MOTOR = rep.VALID_FLAG0_COMPATIBLE_VIBRATION | rep.VALID_FLAG0_HAPTICS_SELECT

SOM = struct.pack("<2h", 9000, -9000) * (af.BYTES_DE_PCM_POR_QUADRO // 4)
MUDO = bytes(af.BYTES_DE_PCM_POR_QUADRO)
MOTORES = struct.pack("<4h", 0, 0, 20000, -20000) * af.QUADROS_POR_BLOCO_HAPTICO
MOTORES_QUIETOS = bytes(len(MOTORES))
JOGADORES = tuple(f"02fe0000001{n}" for n in range(1, 5))


class _Opus:
    def codificar(self, _pcm: bytes) -> bytes:
        return b"\x01" * af.BYTES_POR_QUADRO_OPUS


def _fonte(blocos: list[bytes]) -> Callable[[int], bytes]:
    fila = list(blocos)

    def _ler(_quantos: int) -> bytes:
        return fila.pop(0) if fila else b""

    return _ler


def _blocos(report: bytes) -> list[tuple[int, bytes]]:
    """A cadeia TLV do ``0x36``, do ``[2]`` até o primeiro byte vazio."""
    blocos: list[tuple[int, bytes]] = []
    pos = af.POS_TAG_CONTROLE_COMBINADO
    fim = len(report) - af.CRC_BYTES
    while pos < fim and report[pos]:
        tamanho = report[pos + 1]
        blocos.append((report[pos], bytes(report[pos + 2 : pos + 2 + tamanho])))
        pos += 2 + tamanho
    return blocos


def _estado(report: bytes) -> bytes | None:
    return next((dados for tag, dados in _blocos(report) if tag == TAG_ESTADO), None)


def _solta_o_motor(report: bytes) -> bool:
    estado = _estado(report)
    return estado is not None and not estado[0] & FLAGS_DO_MOTOR


def _relatorios(bomba: af.BombaDeSomPeloRadio) -> list[bytes]:
    saida: list[bytes] = []
    while (report := bomba.um_report()) is not None:
        if report:
            saida.append(report)
    return saida


def _bomba(
    som: list[bytes], haptica: list[bytes] | None = None, *, common: bytes | None = None
) -> af.BombaDeSomPeloRadio:
    return af.BombaDeSomPeloRadio(
        fonte=_fonte(som),
        fonte_haptica=None if haptica is None else _fonte(haptica),
        codificador=_Opus(),
        so_com_sinal=True,
        common=common,
    )


def test_o_quadro_so_de_som_nao_solta_o_motor_do_jogo() -> None:
    """MORDIDA: devolva ``common=self.common`` neutro em todo quadro e veja 20 solturas."""
    relatorios = _relatorios(_bomba([SOM] * 20))
    assert len(relatorios) == 20
    assert [r for r in relatorios if _solta_o_motor(r)] == []
    for report in relatorios:
        assert [tag for tag, _ in _blocos(report)] == [TAG_CONTROLE, TAG_SOM]
        assert report[af.POS_TAG_ESTADO_COMBINADO] == TAG_SOM, "a cadeia sobe sem buraco"
        assert report[-4:] == rep.bt_crc32(report[:-4], seed=rep.BT_CRC_SEED).to_bytes(4, "little")


def test_a_haptica_leva_o_0x10_neutro_sem_dizer_mais_nada() -> None:
    """O ensaio de 03/10: sem o ``0x10`` a háptica não toca. O neutro não diz luz nem gatilho."""
    relatorios = _relatorios(_bomba([SOM] * 5, [MOTORES] * 5))
    assert len(relatorios) == 5
    for report in relatorios:
        assert [tag for tag, _ in _blocos(report)] == [
            TAG_CONTROLE, TAG_ESTADO, TAG_HAPTICA, TAG_SOM,
        ]
        assert _estado(report) == bytes(af.LEN_ESTADO_COMBINADO)


def test_o_silencio_que_fecha_a_haptica_leva_o_0x10_e_depois_ele_sai() -> None:
    relatorios = _relatorios(
        _bomba([SOM] * 6, [MOTORES, MOTORES, MOTORES_QUIETOS, MOTORES_QUIETOS,
                           MOTORES_QUIETOS, MOTORES_QUIETOS])
    )
    com_estado = [_estado(r) is not None for r in relatorios]
    assert com_estado == [True, True, True, False, False, False]
    silencio = dict(_blocos(relatorios[2]))[TAG_HAPTICA]
    assert silencio == hb.bloco_de_silencio()


def test_o_common_dado_vai_em_todo_quadro() -> None:
    dado = af.common_de_audio()
    relatorios = _relatorios(_bomba([SOM] * 3, common=dado))
    assert [(_estado(r) or b"")[: rep.COMMON_LEN] for r in relatorios] == [dado] * 3


def test_o_silencio_inteiro_nao_vai_ao_fio() -> None:
    assert _relatorios(_bomba([MUDO] * 4, [MOTORES_QUIETOS] * 4)) == []


@pytest.mark.parametrize("uniq", JOGADORES)
def test_a_ponte_de_cada_jogador_escreve_o_som_sem_soltar_o_motor(uniq: str) -> None:
    """A ponte como o daemon a sobe (sem ``common``), de P1 a P4, lida no cano."""
    leitura, escrita = os.pipe()
    try:
        ponte = af.PonteDeSomPorRadio(
            uniq=uniq,
            abrir_hidraw=lambda: escrita,
            fonte_de_pcm=_fonte([SOM] * 8),
        )
        assert ponte.subir() is True, ponte.motivo
        prazo = time.monotonic() + 5.0
        while not ponte.terminou_sozinha() and time.monotonic() < prazo:
            time.sleep(0.01)
        assert ponte.terminou_sozinha(), "a fonte secou e a ponte não desceu"
        ponte.descer()
        os.set_blocking(leitura, False)
        cru = b""
        while True:
            try:
                pedaco = os.read(leitura, 65536)
            except BlockingIOError:
                break
            if not pedaco:
                break
            cru += pedaco
    finally:
        os.close(leitura)
    tamanho = af.TAMANHO_DO_DEGRAU[af.DEGRAU_COMBINADO]
    relatorios = [cru[i : i + tamanho] for i in range(0, len(cru), tamanho)]
    assert len(relatorios) == 8
    assert all(r[0] == af.DEGRAU_COMBINADO for r in relatorios)
    assert [r for r in relatorios if _estado(r) is not None] == []
