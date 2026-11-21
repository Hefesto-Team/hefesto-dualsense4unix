"""A volta não espera o som do cabo soltar o aparelho USB.

Medido em 20/11/2026, em três ligações do cabo: o kernel registrou o controle em 2,6 s, e o
`connect` da volta só voltou 0,3 s depois de o `snd-usb-audio` terminar a probe do som do
mesmo aparelho, cerca de 10 s mais tarde (`volta_demorou connect_ms=9911`, 10033 e 10233). O
`hidapi.enumerate` lia as strings `manufacturer` e `product` do aparelho USB, que o kernel serve
sob a trava que a probe segura; enquanto isso, nenhum controle abria, em nenhum transporte.

A árvore de mentira tem as strings do aparelho USB como FIFO sem escritor: quem as abre fica
preso, como ficava o `hidapi` atrás da trava. O dublê do `hidapi` faz o que o `linux/hid.c`
faz na enumeração (filtra pelo `HID_ID` do uevent e lê as duas strings do pai USB), para a
mordida mostrar a volta presa. MORDIDA: devolver `hidapi.enumerate` ao `_enumerate_device_keys`.
"""
from __future__ import annotations

import contextlib
import os
import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core import backend_pydualsense as backend_mod
from hefesto_dualsense4unix.core import evdev_reader
from hefesto_dualsense4unix.core import relogio_da_conexao as rel
from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController

PRAZO_S = 2.0
MESA = (
    ("usb", "0CE6", "aa:bb:cc:00:00:01"),
    ("bt", "0CE6", "aa:bb:cc:00:00:02"),
    ("usb", "0DF2", "aa:bb:cc:00:00:03"),
    ("bt", "0DF2", "aa:bb:cc:00:00:04"),
)
BARRAMENTO = {"usb": "0003", "bt": "0005"}


class _Arvore:
    """Um `/sys` de mentira: a classe hidraw e, no cabo, o aparelho USB com as strings."""

    def __init__(self, raiz: Path) -> None:
        self.classe = raiz / "class" / "hidraw"
        self.classe.mkdir(parents=True)
        self.devices = raiz / "devices"
        self.presas: list[Path] = []

    def controle(self, numero: int, transporte: str, pid: str, uniq: str, *, preso: bool) -> None:
        nome = f"hidraw{numero}"
        hid_nome = f"{BARRAMENTO[transporte]}:054C:{pid}.{numero:04X}"
        if transporte == "usb":
            aparelho = self.devices / "pci0000:00" / "usb3" / f"3-{numero}"
            pai = aparelho / f"3-{numero}:1.3" / hid_nome
            pai.mkdir(parents=True)
            (aparelho / "idVendor").write_text("054c\n", encoding="utf-8")
            for string in ("manufacturer", "product"):
                if preso:
                    os.mkfifo(aparelho / string)
                    self.presas.append(aparelho / string)
                else:
                    (aparelho / string).write_text("Sony\n", encoding="utf-8")
        else:
            pai = self.devices / "virtual" / "misc" / "uhid" / hid_nome
            pai.mkdir(parents=True)
        (pai / "uevent").write_text(
            f"HID_ID={BARRAMENTO[transporte]}:0000054C:0000{pid}\n"
            f"HID_NAME=Wireless Controller\nHID_UNIQ={uniq}\n",
            encoding="utf-8",
        )
        (self.classe / nome).mkdir()
        os.symlink(pai, self.classe / nome / "device")

    def soltar(self) -> None:
        for fifo in self.presas:
            with contextlib.suppress(OSError):
                os.close(os.open(fifo, os.O_WRONLY | os.O_NONBLOCK))


def _hidapi_como_o_linux(classe: Path) -> SimpleNamespace:
    """O `hid_enumerate` do `linux/hid.c`: o `HID_ID` filtra, e o cabo lê as strings do pai USB."""

    def enumerate(vendor_id: int = 0, product_id: int = 0) -> list[SimpleNamespace]:
        del product_id
        achados = []
        for no in sorted(os.listdir(classe)):
            campos = dict(
                linha.split("=", 1)
                for linha in (classe / no / "device" / "uevent").read_text("utf-8").splitlines()
            )
            _bus, vid, pid = campos["HID_ID"].split(":")
            if vendor_id and int(vid, 16) != vendor_id:
                continue
            for pasta in Path(os.path.realpath(classe / no / "device")).parents:
                if (pasta / "idVendor").is_file():
                    (pasta / "manufacturer").read_text("utf-8")
                    (pasta / "product").read_text("utf-8")
                    break
            achados.append(SimpleNamespace(
                product_id=int(pid, 16), path=f"/dev/{no}".encode(),
                serial_number=campos["HID_UNIQ"]))
        return achados

    return SimpleNamespace(enumerate=enumerate)


@pytest.fixture
def arvore(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Any:
    sysfs = _Arvore(tmp_path / "sys")
    monkeypatch.setattr(backend_mod, "RAIZ_CLASS_HIDRAW", str(sysfs.classe))
    monkeypatch.setitem(sys.modules, "hidapi", _hidapi_como_o_linux(sysfs.classe))
    yield sysfs
    sysfs.soltar()


def _no_prazo(funcao: Any) -> tuple[bool, list[Any]]:
    saida: list[Any] = []
    fio = threading.Thread(target=lambda: saida.append(funcao()), daemon=True)
    fio.start()
    fio.join(PRAZO_S)
    return not fio.is_alive(), saida


def _montar(
    arvore: _Arvore, presa: int
) -> tuple[list[tuple[str, bytes, bool]], dict[bytes, str]]:
    """A mesa mista, com o controle da posição ``presa`` no cabo e o som dele em probe."""
    esperado = []
    transportes = {}
    for posicao, (transporte, pid, uniq) in enumerate(MESA):
        numero = 4 + posicao
        no_cabo = "usb" if posicao == presa else transporte
        arvore.controle(numero, no_cabo, pid, uniq, preso=posicao == presa)
        path = f"/dev/hidraw{numero}".encode()
        esperado.append((uniq, path, pid == "0DF2"))
        transportes[path] = no_cabo
    return esperado, transportes


@pytest.mark.parametrize("presa", range(len(MESA)), ids=[f"P{n + 1}" for n in range(len(MESA))])
def test_a_enumeracao_nao_espera_as_strings_do_aparelho_usb(arvore: _Arvore, presa: int) -> None:
    """De P1 a P4, cabo e rádio, DualSense e Edge: a lista sai com o aparelho USB travado."""
    esperado, _transportes = _montar(arvore, presa)
    assert len(arvore.presas) == 2

    terminou, saida = _no_prazo(PyDualSenseController._enumerate_device_keys)

    assert terminou, (
        f"a enumeração esperou as strings do aparelho USB travado ({PRAZO_S:g} s)"
    )
    assert saida == [esperado]


class _Handle:
    def __init__(self, path: bytes, transporte: str) -> None:
        self._pinned_path = path
        self.conType = SimpleNamespace(name=transporte.upper())
        self.state = SimpleNamespace()
        self.connected = True

    def close(self) -> None:
        pass


@pytest.mark.parametrize("presa", range(len(MESA)), ids=[f"P{n + 1}" for n in range(len(MESA))])
def test_a_volta_abre_a_mesa_inteira_com_o_som_do_cabo_preso(
    arvore: _Arvore, monkeypatch: pytest.MonkeyPatch, presa: int
) -> None:
    """O `connect` da volta abre os quatro enquanto a probe do som segura o aparelho USB."""
    monkeypatch.setattr(evdev_reader, "discover_gamepads", lambda **_k: [])
    monkeypatch.setattr(backend_mod, "TETO_DA_ABERTURA_NA_VOLTA_SEC", 0.1)
    esperado, transportes = _montar(arvore, presa)
    ctl = PyDualSenseController()

    def abrir(path: bytes, *, is_edge: bool) -> _Handle:
        del is_edge
        return _Handle(path, transportes[path])

    ctl._open_one = abrir  # type: ignore[method-assign]
    rel.RELOGIO.limpar()
    try:
        terminou, _ = _no_prazo(ctl.connect)
    finally:
        rel.RELOGIO.limpar()

    assert terminou, f"o connect da volta esperou o aparelho USB travado ({PRAZO_S:g} s)"
    assert set(ctl._handles) == {uniq for uniq, _p, _e in esperado}
