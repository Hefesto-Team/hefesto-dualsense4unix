"""O gatilho diz quando disparou (O-GATILHO-DIZ-QUANDO-DISPAROU-01, 08/10/2026).

O nibble ALTO do status de cada gatilho, no relatório de entrada, diz o que o
gatilho sente: com a arma oficial, 0 antes do início, 1 dentro e 2 depois
(disparou). O leitor físico passou a ler os dois, no cabo (`0x01`, base 1:
report[42] e [43]) e no rádio (`0x31`, base 2: report[43] e [44]), pelo mesmo
`_struct_base` dos outros bytes, ou seja, com o CRC e o filtro do áudio.

Os relatórios são sintéticos (nenhum aparelho é tocado): o que sustenta o
deslocamento no controle de verdade é a bancada, e a referência canônica diz
isso. Nenhum endereço de rádio aparece aqui.
"""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Callable

import pytest

from hefesto_dualsense4unix.core import physical_report_reader as prr
from hefesto_dualsense4unix.core.ds_output_report import BT_INPUT_CRC_SEED, bt_crc32
from hefesto_dualsense4unix.core.physical_report_reader import (
    INPUT_REPORT_BT_SIZE,
    TRIGGER_ESTADO_DISPAROU,
    PhysicalReportReader,
    extract_estado_do_gatilho,
)

_USB_L2, _USB_R2 = 43, 42
_BT_L2, _BT_R2 = 44, 43


def _usb(l2: int = 0, r2: int = 0, *, baixo_l2: int = 0, baixo_r2: int = 0) -> bytes:
    """Report `0x01` de 64 B com o nibble alto de cada gatilho."""
    raw = bytearray(64)
    raw[0] = 0x01
    raw[_USB_L2] = (l2 << 4) | baixo_l2
    raw[_USB_R2] = (r2 << 4) | baixo_r2
    return bytes(raw)


def _bt(
    l2: int = 0,
    r2: int = 0,
    *,
    baixo_l2: int = 0,
    baixo_r2: int = 0,
    corrompido: bool = False,
    audio: bool = False,
) -> bytes:
    """Report `0x31` de 78 B com CRC de INPUT (semente 0xA1) válido."""
    raw = bytearray(INPUT_REPORT_BT_SIZE)
    raw[0] = 0x31
    raw[1] = 0x02 if audio else 0x01
    raw[_BT_L2] = (l2 << 4) | baixo_l2
    raw[_BT_R2] = (r2 << 4) | baixo_r2
    raw[-4:] = bt_crc32(raw[:-4], seed=BT_INPUT_CRC_SEED).to_bytes(4, "little")
    if corrompido:
        raw[_BT_R2] ^= 0xF0
    return bytes(raw)


class _Relogio:
    def __init__(self) -> None:
        self.t = 100.0

    def __call__(self) -> float:
        return self.t


class _Vpad:
    """Dublê mínimo: o gatilho não é encaminhado a ninguém, só lido."""

    def set_motion_streaming(self, _ligado: bool) -> None:
        return None

    def forward_motion(self, _janela: bytes) -> None:
        return None


def _leitor() -> tuple[PhysicalReportReader, _Relogio, list[tuple[str, int, int, float]]]:
    relogio = _Relogio()
    leitor = PhysicalReportReader(
        path_provider=lambda: None, vpad=_Vpad(), time_fn=relogio
    )
    eventos: list[tuple[str, int, int, float]] = []
    leitor.ouvir_gatilho(lambda *a: eventos.append(a))
    return leitor, relogio, eventos


def _como_o_laco(leitor: PhysicalReportReader, report: bytes) -> None:
    """O que o laço vivo faz com cada report: resolve a base e observa."""
    base = prr._struct_base(report)
    if base is not None:
        leitor._observe_gatilho(report, base)


@pytest.mark.parametrize("monta", [_usb, _bt], ids=["cabo", "radio"])
def test_o_extrator_le_o_nibble_alto_de_cada_lado(
    monta: Callable[..., bytes],
) -> None:
    assert extract_estado_do_gatilho(monta(l2=1, r2=2)) == (1, 2)
    assert extract_estado_do_gatilho(monta(l2=2, r2=0)) == (2, 0)
    assert extract_estado_do_gatilho(monta()) == (0, 0)


@pytest.mark.parametrize("monta", [_usb, _bt], ids=["cabo", "radio"])
def test_o_nibble_baixo_nao_entra_na_conta(monta: Callable[..., bytes]) -> None:
    """Mordida: ler `& 0x0F` em vez do nibble alto reprova."""
    assert extract_estado_do_gatilho(monta(l2=0, r2=1, baixo_l2=0xF, baixo_r2=0x7)) == (
        0,
        1,
    )


def test_o_lado_esquerdo_e_o_direito_nao_se_trocam() -> None:
    """Mordida: trocar os dois deslocamentos reprova (R2 é o 41, L2 o 42)."""
    assert extract_estado_do_gatilho(_usb(l2=2, r2=0)) == (2, 0)
    assert extract_estado_do_gatilho(_bt(l2=0, r2=2)) == (0, 2)
    assert prr.TRIGGER_R2_STATUS_OFFSET + 1 == prr.TRIGGER_L2_STATUS_OFFSET


def test_cabo_e_radio_apontam_para_o_mesmo_campo_do_struct() -> None:
    """A base muda (1 e 2), o campo do struct é o mesmo."""
    assert _USB_R2 == 1 + prr.TRIGGER_R2_STATUS_OFFSET
    assert _BT_R2 == 2 + prr.TRIGGER_R2_STATUS_OFFSET
    assert _USB_L2 == 1 + prr.TRIGGER_L2_STATUS_OFFSET
    assert _BT_L2 == 2 + prr.TRIGGER_L2_STATUS_OFFSET


def test_radio_com_crc_corrompido_nao_vira_estado() -> None:
    """Mordida: ignorar o CRC do `0x31` reprova."""
    assert extract_estado_do_gatilho(_bt(r2=2, corrompido=True)) is None


def test_radio_com_audio_nao_vira_estado() -> None:
    """O Opus do microfone tem o mesmo id, o mesmo tamanho e CRC válido."""
    assert extract_estado_do_gatilho(_bt(r2=2, audio=True)) is None


def test_report_curto_ou_de_outro_id_da_none() -> None:
    assert extract_estado_do_gatilho(b"") is None
    assert extract_estado_do_gatilho(_usb()[:40]) is None
    assert extract_estado_do_gatilho(bytes([0x05]) + bytes(63)) is None


@pytest.mark.parametrize("monta", [_usb, _bt], ids=["cabo", "radio"])
def test_a_arma_que_dispara_conta_uma_vez_e_diz_quando(
    monta: Callable[..., bytes],
) -> None:
    leitor, relogio, eventos = _leitor()
    _como_o_laco(leitor, monta(r2=0))
    assert leitor.estado_do_gatilho == (0, 0)
    assert leitor.disparos_do_gatilho == {"L2": 0, "R2": 0}

    relogio.t = 101.0
    _como_o_laco(leitor, monta(r2=1))
    relogio.t = 101.5
    for _ in range(5):
        _como_o_laco(leitor, monta(r2=2))

    assert leitor.estado_do_gatilho == (0, 2)
    assert leitor.disparos_do_gatilho == {"L2": 0, "R2": 1}
    assert leitor.disparou_em == {"R2": 101.5}
    assert leitor.gatilho_desde == 101.5
    assert eventos == [("R2", 0, 1, 101.0), ("R2", 1, 2, 101.5)]


def test_o_dedo_volta_e_a_arma_dispara_de_novo() -> None:
    leitor, relogio, _eventos = _leitor()
    for t, r2 in ((1.0, 0), (2.0, 1), (3.0, 2), (4.0, 0), (5.0, 1), (6.0, 2)):
        relogio.t = t
        _como_o_laco(leitor, _usb(r2=r2))
    assert leitor.disparos_do_gatilho["R2"] == 2
    assert leitor.disparou_em["R2"] == 6.0


def test_cada_gatilho_conta_o_seu() -> None:
    leitor, relogio, _eventos = _leitor()
    _como_o_laco(leitor, _usb(l2=0, r2=0))
    relogio.t = 101.0
    _como_o_laco(leitor, _usb(l2=2, r2=0))
    relogio.t = 102.0
    _como_o_laco(leitor, _usb(l2=2, r2=2))
    assert leitor.disparos_do_gatilho == {"L2": 1, "R2": 1}
    assert leitor.disparou_em == {"L2": 101.0, "R2": 102.0}


def test_o_primeiro_relatorio_nao_e_um_disparo() -> None:
    """O leitor abre com o gatilho já no estado 2 (dedo no fundo): não houve
    borda nenhuma para contar."""
    leitor, _relogio, eventos = _leitor()
    _como_o_laco(leitor, _usb(r2=TRIGGER_ESTADO_DISPAROU))
    assert leitor.disparos_do_gatilho == {"L2": 0, "R2": 0}
    assert eventos == []
    assert leitor.estado_do_gatilho == (0, 2)


def test_relatorio_corrompido_nao_move_o_estado() -> None:
    leitor, _relogio, _eventos = _leitor()
    _como_o_laco(leitor, _bt(r2=1))
    _como_o_laco(leitor, _bt(r2=2, corrompido=True))
    assert leitor.estado_do_gatilho == (0, 1)
    assert leitor.disparos_do_gatilho["R2"] == 0


def test_perder_o_controle_esquece_o_estado_e_guarda_a_conta() -> None:
    leitor, relogio, _eventos = _leitor()
    _como_o_laco(leitor, _usb(r2=1))
    relogio.t = 101.0
    _como_o_laco(leitor, _usb(r2=2))
    leitor._reset_gatilho()
    assert leitor.estado_do_gatilho is None
    assert leitor.disparos_do_gatilho["R2"] == 1
    _como_o_laco(leitor, _usb(r2=2))
    assert leitor.disparos_do_gatilho["R2"] == 1


def test_ouvinte_que_quebra_nao_derruba_o_leitor() -> None:
    leitor, _relogio, _eventos = _leitor()

    def _quebra(*_a: object) -> None:
        raise RuntimeError("ouvinte ruim")

    leitor.ouvir_gatilho(_quebra)
    _como_o_laco(leitor, _usb(r2=0))
    _como_o_laco(leitor, _usb(r2=2))
    assert leitor.disparos_do_gatilho["R2"] == 1


def test_o_dado_e_so_de_leitura() -> None:
    """Nada vai ao controle nem ao vpad por causa do estado: o leitor não toca
    em nenhum método do vpad ao observar o gatilho."""
    tocados: list[str] = []

    class _VpadQueDenuncia:
        def __getattr__(self, nome: str) -> object:
            tocados.append(nome)
            return lambda *_a, **_k: None

    leitor = PhysicalReportReader(
        path_provider=lambda: None, vpad=_VpadQueDenuncia(), time_fn=_Relogio()
    )
    for r2 in (0, 1, 2, 0):
        _como_o_laco(leitor, _usb(r2=r2))
    assert tocados == []


def _esperar(cond: Callable[[], bool], limite_s: float = 3.0) -> bool:
    fim = time.monotonic() + limite_s
    while time.monotonic() < fim:
        if cond():
            return True
        time.sleep(0.01)
    return cond()


def _esperar_o_estado(leitor: PhysicalReportReader, esperado: tuple[int, int]) -> bool:
    return _esperar(lambda: leitor.estado_do_gatilho == esperado)


@pytest.mark.parametrize("monta", [_usb, _bt], ids=["cabo", "radio"])
def test_pelo_laco_da_thread_o_disparo_chega_ao_ouvinte(
    monkeypatch: pytest.MonkeyPatch, monta: Callable[..., bytes]
) -> None:
    lido, escrita = os.pipe()
    monkeypatch.setattr(prr.os, "open", lambda *_a: os.dup(lido))
    leitor = PhysicalReportReader(path_provider=lambda: "/dev/hidraw-fake", vpad=_Vpad())
    eventos: list[tuple[str, int, int, float]] = []
    trava = threading.Lock()

    def _ouve(*a: object) -> None:
        with trava:
            eventos.append(a)  # type: ignore[arg-type]

    leitor.ouvir_gatilho(_ouve)
    try:
        assert leitor.start() is True
        for r2 in (0, 1, 2):
            os.write(escrita, monta(r2=r2))
            assert _esperar_o_estado(leitor, (0, r2))
        assert leitor.disparos_do_gatilho["R2"] == 1
        assert [(e[0], e[1], e[2]) for e in eventos] == [("R2", 0, 1), ("R2", 1, 2)]
    finally:
        leitor.stop()
        os.close(escrita)
        os.close(lido)
