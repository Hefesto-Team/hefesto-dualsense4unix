"""BORDA-DE-QUEDA-01 / E2 — parar o Jogador 1 não desnuda os outros três."""
from __future__ import annotations

import contextlib
import os
import socket
import tempfile
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.broker.hidraw_broker import Broker, BrokerState
from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.integrations import hidraw_broker_client as hbc
from hefesto_dualsense4unix.utils import session

NO_P1 = "/dev/hidraw3"
SECUNDARIOS: dict[str, str] = {
    "aa:bb:cc:00:00:d2": "/dev/hidraw4",
    "e8:47:3a:00:00:9c": "/dev/hidraw5",
    "02:fe:00:00:00:71": "/dev/hidraw6",
}
TODOS_OS_NOS = [NO_P1, *SECUNDARIOS.values()]


class FakeOps:
    """Dublê de fs com as assinaturas REAIS do FsAclOps — nada de /dev."""

    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []

    def hide(self, node: str, base: str) -> None:
        self.calls.append(("hide", node))

    def restore(self, node: str, base: str, uid: int) -> None:
        self.calls.append(("restore", node))

    def is_exposed_to(self, node: str, uid: int) -> bool:
        return True

    def open_node(self, node: str, base: str) -> int:  # pragma: no cover
        raise AssertionError("esta régua nunca abre nó")

    @property
    def restaurados(self) -> list[str]:
        return [c[1] for c in self.calls if c[0] == "restore"]


def _validator(node: str) -> str | None:
    """Só os quatro nós da mesa são "físicos" para este broker."""
    base = node.rsplit("/", 1)[-1]
    return base if f"/dev/{base}" in TODOS_OS_NOS else None


def _short_socket_dir(tmp_path: Path) -> str:
    """`sun_path` tem limite de ~108 bytes; o tmp_path do pytest pode passar."""
    candidato = tmp_path / "bk"
    if len(str(candidato / "broker.sock")) <= 90:
        candidato.mkdir(exist_ok=True)
        return str(candidato)
    return tempfile.mkdtemp(prefix="hefesto-bq-", dir="/tmp")


def _espera(cond: Callable[[], bool], timeout: float = 2.0) -> bool:
    fim = time.monotonic() + timeout
    while time.monotonic() < fim:
        if cond():
            return True
        time.sleep(0.01)
    return False


class _VpadFalso:
    def __init__(self) -> None:
        self.flavor = "dualsense"
        self.backend = "uhid"

    def stop(self) -> None: ...


class _ControllerFalso:
    """Backend com `hidraw_path(uniq)` — o gate que o smoke não passa."""

    def __init__(self) -> None:
        self._evdev = SimpleNamespace(set_grab=lambda _g: True, grab_state="held")
        self.nodes: dict[str | None, str | None] = {None: NO_P1, **SECUNDARIOS}

    def hidraw_path(self, uniq: str | None = None) -> str | None:
        return self.nodes.get(uniq)

    def set_rumble(self, weak: int = 0, strong: int = 0) -> None: ...


class _DaemonComLeaseReal:
    """Daemon mínimo cujo cliente do broker é o HidrawBrokerClient de verdade."""

    def __init__(self, socket_path: str) -> None:
        self._gamepad_device: Any = _VpadFalso()
        self._motion_reader = None
        self._coop_manager = None
        self._hidraw_broker_client = hbc.HidrawBrokerClient(socket_path)
        self.config = DaemonConfig()
        self.config.gamepad_emulation_enabled = True
        self.controller = _ControllerFalso()

    def is_native_mode(self) -> bool:
        return False


@pytest.fixture()
def mesa(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    """Broker real + lease real + os quatro nós JÁ escondidos."""
    monkeypatch.setattr(session, "save_gamepad_emulation", lambda *a, **k: None)
    monkeypatch.setattr(gp, "_materialize_launch_env", lambda _d: None)
    monkeypatch.setattr(gp, "stop_motion_reader", lambda _d: None)

    sockdir = _short_socket_dir(tmp_path)
    path = os.path.join(sockdir, "broker.sock")
    listen = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listen.bind(path)
    listen.listen(4)
    ops = FakeOps()
    state = BrokerState(
        allowed_uid=os.getuid(), ops=ops, validator=_validator, log=lambda *a, **k: None
    )
    broker = Broker(state, listen, log=lambda *a, **k: None)
    thread = threading.Thread(target=broker.run, daemon=True)
    thread.start()

    daemon = _DaemonComLeaseReal(path)
    for no in TODOS_OS_NOS:
        assert daemon._hidraw_broker_client.hide(no) is True
    assert sorted(state.hidden) == sorted(TODOS_OS_NOS), "a mesa nasce escondida"
    ops.calls.clear()
    try:
        yield SimpleNamespace(daemon=daemon, state=state, ops=ops, path=path)
    finally:
        with contextlib.suppress(Exception):
            daemon._hidraw_broker_client.close()
        broker.stopping = True
        with (
            socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as poke,
            contextlib.suppress(OSError),
        ):
            poke.connect(path)
        thread.join(timeout=3.0)
        listen.close()
        if os.path.exists(path):
            os.unlink(path)
        if sockdir.startswith("/tmp/hefesto-bq-"):
            os.rmdir(sockdir)


def test_o_stop_do_p1_restaura_so_o_no_do_p1(mesa: Any) -> None:
    """O aceite da E2, dito pelo SERVIDOR: os três secundários seguem escondidos."""
    gp.stop_gamepad_emulation(mesa.daemon)

    assert _espera(lambda: NO_P1 not in mesa.state.hidden), (
        "o nó do P1 tinha de voltar à vista — o release do grab é dele"
    )
    assert sorted(mesa.state.hidden) == sorted(SECUNDARIOS.values()), (
        "parar o Jogador 1 desnudou o hidraw de quem não é ele: "
        f"escondidos={sorted(mesa.state.hidden)}"
    )
    assert mesa.ops.restaurados == [NO_P1], (
        f"o fs restaurou nó que não era do P1: {mesa.ops.restaurados}"
    )


def test_o_ramo_do_ungrab_pede_restore_de_um_no_so(mesa: Any) -> None:
    """A unidade, sem passar pelo `stop`: `_broker_sync_grab(daemon, False)`."""
    gp._broker_sync_grab(mesa.daemon, False)

    assert mesa.ops.restaurados == [NO_P1]
    assert sorted(mesa.state.hidden) == sorted(SECUNDARIOS.values())


def test_com_um_controle_so_o_efeito_e_o_mesmo_de_antes(
    mesa: Any,
) -> None:
    """A prova de que nada regrediu no caso de UM controle."""
    for no in SECUNDARIOS.values():
        assert mesa.daemon._hidraw_broker_client.restore(no) is True
    mesa.ops.calls.clear()
    assert list(mesa.state.hidden) == [NO_P1]

    gp.stop_gamepad_emulation(mesa.daemon)

    assert mesa.state.hidden == {}, "com um controle só, a mesa fica limpa"
    assert mesa.ops.restaurados == [NO_P1]


def test_o_restore_do_p1_continua_sem_gate_de_modo_nativo(mesa: Any) -> None:
    """"Expor nunca é errado" (`gamepad.py`, doutrina duplicado > zero)."""
    mesa.daemon.is_native_mode = lambda: True  # type: ignore[method-assign]

    gp._broker_sync_grab(mesa.daemon, False)

    assert mesa.ops.restaurados == [NO_P1], (
        "em Modo Nativo o release do P1 continua expondo o nó dele"
    )


def test_o_eof_da_lease_continua_restaurando_a_mesa_inteira(mesa: Any) -> None:
    """O `restore_all` do EOF é o certo, e a E2 não podia desfazê-lo."""
    mesa.daemon._hidraw_broker_client.close()

    assert _espera(lambda: mesa.state.hidden == {}), (
        "o EOF da lease tem de restaurar TUDO — é a rede da morte suja"
    )
    assert sorted(mesa.ops.restaurados) == sorted(TODOS_OS_NOS)


def test_sem_no_resolvivel_ninguem_e_desnudado(mesa: Any) -> None:
    """Controle arrancado da mesa: `hidraw_path()` devolve None."""
    mesa.daemon.controller.nodes[None] = None

    gp._broker_sync_grab(mesa.daemon, False)

    assert mesa.ops.restaurados == []
    assert sorted(mesa.state.hidden) == sorted(TODOS_OS_NOS)
