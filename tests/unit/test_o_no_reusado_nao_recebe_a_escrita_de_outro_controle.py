"""O nó hidraw que outro controle herdou não recebe a escrita nem a leitura do primeiro
(O-NO-HIDRAW-REUSADO-NAO-RECEBE-A-ESCRITA-DE-OUTRO-CONTROLE-01).

Decisão a validar: D-2211-O-DESLIGAR-SO-ESCREVE-NO-NO-CONFERIDO. O desligar e a leitura da feature
abrem o nó por caminho, num fd efêmero; antes de escrever ou ler, o endereço do fd aberto
(`HIDIOCGRAWUNIQ`, ou o uevent do hidraw quando o kernel não conhece o ioctl) tem de ser o do
controle pedido. Se não for, nada sai e o diário diz o motivo. O retorno do desligar segue
«escrito inteiro no nó do próprio controle e o handle não trocou»; o único chamador o ignora.

O dublê fica no fundo: o `fcntl.ioctl` responde por «quem ocupa o nó» no instante da abertura
(endereço, SET e GET de feature), e o opener abre o `/dev/null`. Quatro controles, dois no cabo e
dois no rádio, em faixa forjada; nenhum nó é de verdade.
"""

from __future__ import annotations

import errno
import fcntl
import itertools
import os
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import structlog.testing

from hefesto_dualsense4unix.core import backend_pydualsense as backend_mod
from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController
from hefesto_dualsense4unix.core.ds_output_report import BT_FEATURE_CRC_SEED, bt_crc32

CABO_1 = "AA:BB:CC:00:00:01"
CABO_2 = "AA:BB:CC:00:00:02"
RADIO_1 = "AA:BB:CC:00:00:03"
RADIO_2 = "AA:BB:CC:00:00:04"
INTRUSO = "AA:BB:CC:00:00:09"

_NOS = {
    CABO_1: "/dev/hidraw3",
    CABO_2: "/dev/hidraw4",
    RADIO_1: "/dev/hidraw5",
    RADIO_2: "/dev/hidraw6",
}
_NO_CABO = (CABO_1, CABO_2)
_NO_RADIO = (RADIO_1, RADIO_2)


def _pagina_de(ocupante: str, report_id: int, tamanho: int) -> bytes:
    """A feature que `ocupante` serve; no rádio, fechada com o CRC-32 da leitura."""
    if ocupante in _NO_RADIO:
        corpo = bytes([report_id]) + (ocupante.encode() * tamanho)[: tamanho - 5]
        crc = bt_crc32(corpo, seed=BT_FEATURE_CRC_SEED)
        return corpo + crc.to_bytes(4, "little")
    return bytes([report_id]) + (ocupante.encode() * tamanho)[: tamanho - 1]


class _Mundo:
    """Quem ocupa cada nó AGORA; o fd guarda o ocupante do instante em que foi aberto."""

    def __init__(self) -> None:
        self.ocupante: dict[str, str] = dict(((no, uniq) for uniq, no in _NOS.items()))
        self._do_fd: dict[int, str] = {}
        self.escritas: list[tuple[str, bytes]] = []
        self.aberturas: list[str] = []
        self.antes_de_abrir: Callable[[str], None] | None = None
        self.kernel_sem_uniq = False

    def trocar(self, uniq_que_sai: str, por: str = INTRUSO) -> None:
        self.ocupante[_NOS[uniq_que_sai]] = por

    def abrir(self, caminho: str) -> int:
        if self.antes_de_abrir is not None:
            self.antes_de_abrir(caminho)
        fd = os.open(os.devnull, os.O_RDONLY)
        self._do_fd[fd] = self.ocupante[caminho]
        self.aberturas.append(caminho)
        return fd

    def ioctl(self, fd: int, pedido: int, buf: Any, mutavel: bool = False) -> int:
        ocupante = self._do_fd[fd]
        numero, direcao = pedido & 0xFF, pedido >> 30
        if numero == 0x08 and direcao == 2:
            if self.kernel_sem_uniq:
                raise OSError(errno.ENOTTY, "Inappropriate ioctl for device")
            nome = ocupante.lower().encode() + b"\0"
            buf[: len(nome)] = nome
            return len(nome)
        if numero == 0x06:
            self.escritas.append((ocupante, bytes(buf)))
            return len(buf)
        if numero == 0x07:
            buf[:] = _pagina_de(ocupante, buf[0], len(buf))
            return len(buf)
        raise AssertionError(f"ioctl inesperado: {pedido:#x}")


class _Handle:
    def __init__(self, path: bytes, *, radio: bool) -> None:
        self._pinned_path = path
        self.conType = SimpleNamespace(name="BT" if radio else "USB")


@pytest.fixture()
def mundo(monkeypatch: pytest.MonkeyPatch) -> _Mundo:
    dubl = _Mundo()
    monkeypatch.setattr(fcntl, "ioctl", dubl.ioctl)
    return dubl


def _uniq(key: str) -> str:
    uniq = PyDualSenseController._key_to_uniq(key)
    assert uniq is not None
    return str(uniq)


def _mesa(mundo: _Mundo, ordem: tuple[str, ...] = (CABO_1, CABO_2, RADIO_1, RADIO_2)) -> Any:
    from hefesto_dualsense4unix.core.evdev_reader import EvdevReader

    reader = EvdevReader(device_path=None)
    reader._device_path = None
    inst = PyDualSenseController(evdev_reader=reader)
    inst._handles = {
        key: _Handle(_NOS[key].encode(), radio=key in _NO_RADIO) for key in ordem
    }
    inst._primary_key = ordem[0]
    inst.set_feature_opener(mundo.abrir)
    return inst


def _calibracao(inst: Any, key: str) -> bytes | None:
    return inst.read_calibration(_uniq(key))


@pytest.mark.parametrize("ordem", list(itertools.permutations((CABO_1, CABO_2, RADIO_1, RADIO_2))))
def test_sem_troca_de_numero_cada_controle_recebe_so_o_dele(
    mundo: _Mundo, ordem: tuple[str, ...]
) -> None:
    """Os quatro, em qualquer ordem de ligar: o controle certo continua recebendo a escrita e a
    leitura, e nenhum outro as vê."""
    inst = _mesa(mundo, ordem)

    for key in _NO_RADIO:
        assert inst.desligar_o_controle(_uniq(key)) is True
    for key in _NOS:
        assert _calibracao(inst, key) == _pagina_de(key, 0x05, 41), key

    assert sorted(ocupante for ocupante, _ in mundo.escritas) == sorted(_NO_RADIO), (
        "o desligar de cada rádio escreveu no nó dele e em nenhum outro"
    )


@pytest.mark.parametrize("que_sai", _NO_RADIO)
def test_o_desligar_nao_escreve_no_no_herdado_por_outro_controle(
    mundo: _Mundo, que_sai: str
) -> None:
    """D-2211-O-DESLIGAR-SO-ESCREVE-NO-NO-CONFERIDO.

    **A MORDIDA.** O controle saiu, o intruso herdou o número e o backend ainda não soube:
    o desligar do que saiu não escreve no intruso.

    MORDIDA: a conferência do endereço arrancada reprova aqui pela frase do assert.
    """
    inst = _mesa(mundo)
    mundo.trocar(que_sai)

    assert inst.desligar_o_controle(_uniq(que_sai)) is False

    assert mundo.escritas == [], (
        f"o SET_FEATURE do desligar saiu para o nó herdado: {mundo.escritas}"
    )
    outro = next(k for k in _NO_RADIO if k != que_sai)
    assert inst.desligar_o_controle(_uniq(outro)) is True
    assert [ocupante for ocupante, _ in mundo.escritas] == [outro]


@pytest.mark.parametrize("que_sai", list(_NOS))
def test_a_troca_entre_a_copia_do_caminho_e_a_abertura_tambem_nao_alcanca(
    mundo: _Mundo, que_sai: str
) -> None:
    """A janela de verdade: o caminho foi copiado sob a trava, o número troca de dono antes do
    `open`. Vale para o desligar (rádio) e para a leitura da feature (cabo e rádio)."""
    inst = _mesa(mundo)
    caminho = _NOS[que_sai]

    def _troca(aberto: str) -> None:
        if aberto == caminho:
            mundo.ocupante[caminho] = INTRUSO

    mundo.antes_de_abrir = _troca

    if que_sai in _NO_RADIO:
        assert inst.desligar_o_controle(_uniq(que_sai)) is False
        assert mundo.escritas == [], f"escreveu no nó herdado: {mundo.escritas}"
    leitura = _calibracao(inst, que_sai)
    assert leitura is None, f"a leitura devolveu o dado do outro controle: {leitura!r}"


def test_a_leitura_do_firmware_nao_devolve_a_versao_do_outro(mundo: _Mundo) -> None:
    inst = _mesa(mundo)
    mundo.trocar(CABO_2)

    assert inst.read_update_version(_uniq(CABO_2)) is None
    assert inst.read_update_version(_uniq(CABO_1)) is not None


def test_o_diario_diz_o_motivo_da_recusa(mundo: _Mundo) -> None:
    inst = _mesa(mundo)
    mundo.trocar(RADIO_1)
    mundo.trocar(CABO_1)

    with structlog.testing.capture_logs() as registros:
        inst.desligar_o_controle(_uniq(RADIO_1))
        _calibracao(inst, CABO_1)

    eventos = {(r["event"], r.get("motivo")) for r in registros}
    assert ("controle_desligar_recusado", "no_de_outro_controle") in eventos, eventos
    assert "calibration_no_de_outro_controle" in {r["event"] for r in registros}, eventos
    assert INTRUSO.lower() not in str(registros).lower()


def _uevent_do_no(raiz: Path, no: str, uniq: str | None) -> None:
    pasta = raiz / no / "device"
    pasta.mkdir(parents=True)
    linhas = ["DRIVER=playstation", "HID_ID=0005:0000054C:00000CE6"]
    if uniq is not None:
        linhas.append(f"HID_UNIQ={uniq.lower()}")
    (pasta / "uevent").write_text("\n".join(linhas) + "\n", encoding="utf-8")


def test_kernel_sem_o_ioctl_do_endereco_confere_pelo_uevent_do_no(
    mundo: _Mundo, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Sem `HIDIOCGRAWUNIQ` (kernel antigo), o uevent do hidraw aberto diz de quem é o nó, e o
    controle certo continua recebendo."""
    mundo.kernel_sem_uniq = True
    monkeypatch.setattr(backend_mod, "RAIZ_CLASS_HIDRAW", str(tmp_path))
    _uevent_do_no(tmp_path, "hidraw5", RADIO_1)
    _uevent_do_no(tmp_path, "hidraw6", INTRUSO)
    inst = _mesa(mundo)

    assert inst.desligar_o_controle(_uniq(RADIO_1)) is True
    assert inst.desligar_o_controle(_uniq(RADIO_2)) is False
    assert [ocupante for ocupante, _ in mundo.escritas] == [RADIO_1]


def test_sem_endereco_legivel_nenhum_dos_dois_alcanca_o_no(
    mundo: _Mundo, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Sem o ioctl e sem uevent, não se sabe de quem é o nó: a escrita não sai e a leitura
    devolve `None` (a calibração canônica do chamador cobre)."""
    mundo.kernel_sem_uniq = True
    monkeypatch.setattr(backend_mod, "RAIZ_CLASS_HIDRAW", str(tmp_path))
    inst = _mesa(mundo)

    assert inst.desligar_o_controle(_uniq(RADIO_1)) is False
    assert mundo.escritas == []
    assert _calibracao(inst, CABO_1) is None


def test_o_fd_da_abertura_recusada_nao_vaza(mundo: _Mundo) -> None:
    inst = _mesa(mundo)
    mundo.trocar(RADIO_1)
    antes = len(os.listdir("/proc/self/fd"))

    for _ in range(20):
        inst.desligar_o_controle(_uniq(RADIO_1))
        _calibracao(inst, RADIO_1)

    assert len(os.listdir("/proc/self/fd")) == antes, "o fd do nó recusado ficou aberto"
