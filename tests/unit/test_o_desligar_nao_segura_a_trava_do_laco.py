"""O desligar de um controle (SET_FEATURE 0x08) corre fora do `_io_lock` e não prende os outros."""
from __future__ import annotations

import threading
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core import backend_pydualsense as backend_mod
from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController

_LIMITE_S = 2.0
_RADIO_1 = "AA:BB:CC:00:00:01"
_RADIO_2 = "AA:BB:CC:00:00:02"
_CABO = "AA:BB:CC:00:00:03"
_CABO2 = "AA:BB:CC:00:00:04"


def _u(chave: str) -> str:
    uniq = PyDualSenseController._key_to_uniq(chave)
    assert uniq is not None
    return uniq


class _Handle:
    connected = True

    def __init__(self, path: bytes, *, radio: bool = True) -> None:
        self._pinned_path = path
        self.conType = SimpleNamespace(name="BT" if radio else "USB")


def _mesa(**handles: _Handle) -> PyDualSenseController:
    inst = PyDualSenseController.__new__(PyDualSenseController)
    PyDualSenseController.__init__(inst, evdev_reader=SimpleNamespace())  # type: ignore[arg-type]
    inst._handles = dict(handles)
    inst._primary_key = next(iter(handles))
    return inst


class _Escrita:
    def __init__(self, preso: str | None = None) -> None:
        self.preso = preso
        self.entrou = threading.Event()
        self.solta = threading.Event()

    def __call__(self, path: str, data: bytes, opener: Any = None) -> int:
        if path == self.preso:
            self.entrou.set()
            assert self.solta.wait(_LIMITE_S * 5)
        return len(data)


def _em_fio(fn: Any) -> tuple[threading.Thread, list[Any]]:
    saida: list[Any] = []
    fio = threading.Thread(target=lambda: saida.append(fn()), daemon=True)
    fio.start()
    return fio, saida


def _responde(fn: Any) -> Any:
    fio, saida = _em_fio(fn)
    fio.join(_LIMITE_S)
    assert not fio.is_alive(), "a chamada esperou o desligar preso: a trava segurou o ioctl"
    return saida[0]


def _mesa_de_quatro(
    monkeypatch: pytest.MonkeyPatch, preso: str
) -> tuple[Any, PyDualSenseController]:
    escrita = _Escrita(preso=preso)
    monkeypatch.setattr(backend_mod, "_write_feature_via_hidraw", escrita)
    mesa = _mesa(
        **{
            _RADIO_1: _Handle(b"/dev/hidraw1"),
            _RADIO_2: _Handle(b"/dev/hidraw2"),
            _CABO: _Handle(b"/dev/hidraw3", radio=False),
            _CABO2: _Handle(b"/dev/hidraw4", radio=False),
        }
    )
    return escrita, mesa


def test_o_desligar_preso_nao_prende_os_outros(monkeypatch: pytest.MonkeyPatch) -> None:
    """D-2111-DESLIGAR-O-CONTROLE-SOLTA-A-TRAVA: um rádio preso no desligar, a mesa segue."""
    escrita, mesa = _mesa_de_quatro(monkeypatch, "/dev/hidraw1")
    preso, saida = _em_fio(lambda: mesa.desligar_o_controle(_u(_RADIO_1)))
    assert escrita.entrou.wait(_LIMITE_S)
    try:
        assert _responde(mesa.is_connected) is True
        assert _responde(mesa.alvos_conectados)
        assert _responde(lambda: mesa.desligar_o_controle(_u(_RADIO_2))) is True
        assert _responde(lambda: mesa.desligar_o_controle(_u(_CABO))) is False
        assert preso.is_alive()
    finally:
        escrita.solta.set()
        preso.join(_LIMITE_S)
    assert saida == [True]


@pytest.mark.parametrize("troca", ["outro_handle", "saiu", "foi_ao_cabo"])
def test_handle_trocado_no_meio_do_desligar_devolve_false(
    monkeypatch: pytest.MonkeyPatch, troca: str
) -> None:
    """D-2111-DESLIGAR-O-CONTROLE-SOLTA-A-TRAVA: o pedido só vale se o controle é o mesmo."""
    escrita, mesa = _mesa_de_quatro(monkeypatch, "/dev/hidraw1")
    preso, saida = _em_fio(lambda: mesa.desligar_o_controle(_u(_RADIO_1)))
    assert escrita.entrou.wait(_LIMITE_S)
    assert _responde(mesa.is_connected) is True
    with mesa._io_lock:
        if troca == "saiu":
            mesa._handles.pop(_RADIO_1)
        elif troca == "foi_ao_cabo":
            mesa._handles[_RADIO_1] = _Handle(b"/dev/hidraw7", radio=False)
        else:
            mesa._handles[_RADIO_1] = _Handle(b"/dev/hidraw1")
    escrita.solta.set()
    preso.join(_LIMITE_S)
    assert saida == [False]


def test_o_controle_que_vai_ao_cabo_e_volta_ao_radio_desliga_pelo_hidraw_novo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D-2111-DESLIGAR-O-CONTROLE-SOLTA-A-TRAVA: no cabo o verbo recusa; de volta ao rádio, o
    pedido sai no nó novo e os outros três ficam intocados."""
    escrita, mesa = _mesa_de_quatro(monkeypatch, "")
    caminhos: list[str] = []
    monkeypatch.setattr(
        backend_mod,
        "_write_feature_via_hidraw",
        lambda path, data, opener=None: caminhos.append(path) or escrita(path, data, opener),
    )
    with mesa._io_lock:
        mesa._handles[_RADIO_1] = _Handle(b"/dev/hidraw7", radio=False)
    assert mesa.desligar_o_controle(_u(_RADIO_1)) is False
    with mesa._io_lock:
        mesa._handles[_RADIO_1] = _Handle(b"/dev/hidraw8")
    assert mesa.desligar_o_controle(_u(_RADIO_1)) is True
    assert caminhos == ["/dev/hidraw8"]


def test_um_controle_so_o_desligar_segue_igual(monkeypatch: pytest.MonkeyPatch) -> None:
    """D-2111-DESLIGAR-O-CONTROLE-SOLTA-A-TRAVA: sem concorrência, o pedido sai inteiro."""
    monkeypatch.setattr(backend_mod, "_write_feature_via_hidraw", _Escrita())
    mesa = _mesa(**{_RADIO_1: _Handle(b"/dev/hidraw1")})
    assert mesa.desligar_o_controle(_u(_RADIO_1)) is True
