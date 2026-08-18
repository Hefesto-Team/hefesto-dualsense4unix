"""FEAT-DSX-EVDEV-WATCHDOG-01 — watchdog HID x evdev: reabre o evdev reader
quando ele fica preso num node OBSOLETO após uma re-enumeração (storm -71 /
replug) em que o read_loop zumbi não recebe ENODEV — controle "morto" sem erro.

Cobre os três níveis:
  - EvdevReader.is_stale(): só True por TROCA real de node (idle-safe).
  - EvdevReader.request_reopen(): zera o path e SINALIZA a thread dona (HANG-01,
    2026-07-19: não fecha mais o fd de fora — ver test_evdev_reader.py).
  - PyDualSenseController.heal_evdev_if_stale(): cola os dois com cross-check.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController
from hefesto_dualsense4unix.core.evdev_reader import EvdevReader

# --- is_stale --------------------------------------------------------------


def test_is_stale_false_sem_path_aberto(monkeypatch: pytest.MonkeyPatch) -> None:
    # device_path explícito evita o scan de /dev/input no __init__ (hermético).
    r = EvdevReader(device_path=Path("/dev/input/event20"))
    r._device_path = None
    # mesmo com finder achando algo: sem device aberto, o reconnect loop cobre.
    monkeypatch.setattr(r, "_find_device", lambda: Path("/dev/input/event21"))
    assert r.is_stale() is False


def test_is_stale_false_quando_finder_none(monkeypatch: pytest.MonkeyPatch) -> None:
    r = EvdevReader(device_path=Path("/dev/input/event20"))
    monkeypatch.setattr(r, "_find_device", lambda: None)  # transitório/sem node
    assert r.is_stale() is False


def test_is_stale_false_quando_mesmo_node(monkeypatch: pytest.MonkeyPatch) -> None:
    """Idle-safe: ociosidade não muda o node canônico → nunca reabre à toa."""
    r = EvdevReader(device_path=Path("/dev/input/event20"))
    monkeypatch.setattr(r, "_find_device", lambda: Path("/dev/input/event20"))
    assert r.is_stale() is False


def test_is_stale_true_quando_node_mudou(monkeypatch: pytest.MonkeyPatch) -> None:
    r = EvdevReader(device_path=Path("/dev/input/event20"))
    monkeypatch.setattr(r, "_find_device", lambda: Path("/dev/input/event21"))
    assert r.is_stale() is True


# --- request_reopen --------------------------------------------------------


def test_request_reopen_zera_path_e_sinaliza_sem_fechar_dev() -> None:
    """HANG-01 (2026-07-19): `request_reopen()` NÃO fecha mais o `InputDevice`
    de fora (era o `dev.close()` cross-thread do HEAD 27b51d5, o mesmo padrão
    de risco do `stop()`/M4) — zera o path em cache e só SINALIZA (flag de
    reopen + wake do self-pipe); quem larga o device é sempre a THREAD DONA,
    no `finally` do `_run` (padrão GYRO-FD-01/PhysicalReportReader)."""
    r = EvdevReader(device_path=Path("/dev/input/event20"))
    closed: list[bool] = []

    class _Dev:
        def close(self) -> None:
            closed.append(True)

    r._active_dev = _Dev()
    r.request_reopen("test")
    assert r._device_path is None  # próximo ciclo re-localiza o node certo
    assert closed == []  # HANG-01: fd NÃO fechado daqui — só sinalizado
    assert r._reopen_flag.is_set()  # é a thread dona quem atende o sinal


def test_request_reopen_sem_dev_ativo_nao_quebra() -> None:
    r = EvdevReader(device_path=Path("/dev/input/event20"))
    r._active_dev = None
    r.request_reopen("test")  # não levanta
    assert r._device_path is None


# --- heal_evdev_if_stale (backend, com cross-check) ------------------------


class _FakeReader:
    def __init__(self, *, available: bool, stale: bool) -> None:
        self._available = available
        self._stale = stale
        self.reopened: list[str] = []

    def is_available(self) -> bool:
        return self._available

    def is_stale(self) -> bool:
        return self._stale

    def request_reopen(self, reason: str = "watchdog") -> None:
        self.reopened.append(reason)


def _backend_with(reader: Any) -> PyDualSenseController:
    backend = PyDualSenseController.__new__(PyDualSenseController)
    backend._evdev = reader
    return backend


def test_heal_reabre_quando_stale() -> None:
    reader = _FakeReader(available=True, stale=True)
    assert _backend_with(reader).heal_evdev_if_stale() is True
    assert len(reader.reopened) == 1


def test_heal_noop_quando_node_ok() -> None:
    reader = _FakeReader(available=True, stale=False)
    assert _backend_with(reader).heal_evdev_if_stale() is False
    assert reader.reopened == []


def test_heal_noop_quando_reader_indisponivel() -> None:
    reader = _FakeReader(available=False, stale=True)  # stale ignorado se off
    assert _backend_with(reader).heal_evdev_if_stale() is False
    assert reader.reopened == []
