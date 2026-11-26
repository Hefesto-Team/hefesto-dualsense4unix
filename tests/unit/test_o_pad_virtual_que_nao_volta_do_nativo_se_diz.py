"""O pad virtual (ou o mouse) que não volta do Modo Nativo se diz no diário e no contador."""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from structlog.testing import capture_logs

from hefesto_dualsense4unix.daemon.lifecycle import Daemon
from hefesto_dualsense4unix.testing import FakeController


@pytest.fixture
def daemon(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> Daemon:
    from hefesto_dualsense4unix.utils import session as session_mod

    monkeypatch.setattr(session_mod, "config_dir", lambda ensure=False: tmp_path)
    d = Daemon(controller=FakeController())
    monkeypatch.setattr(d, "_reapply_last_profile", lambda: None)
    return d


def _sair_do_nativo_com(daemon: Daemon, stash: dict[str, Any]) -> list[dict[str, Any]]:
    daemon._native_mode = True
    daemon._native_emu_stash = stash
    with capture_logs() as diario:
        daemon.set_native_mode(False, origin="manual")
    return [e for e in diario if e.get("log_level") == "warning"]


@pytest.mark.parametrize("desfecho", ["falhou", "recusado_steam_input"])
def test_o_pad_que_nao_volta_deixa_o_aviso_e_o_contador(daemon: Daemon, desfecho: str) -> None:
    """O desfecho dublado em falha: a saída do Nativo deixa um ``warning`` e o contador em 1."""
    daemon.set_gamepad_emulation_desfecho = MagicMock(  # type: ignore[method-assign]
        return_value=desfecho)
    avisos = _sair_do_nativo_com(daemon, {"gamepad": [True, "xbox"]})
    assert [a.get("desfecho") for a in avisos] == [desfecho]
    assert avisos[0]["o_que"] == "pad"
    assert daemon.store.counter(f"nativo.volta_falhou.{desfecho}") == 1


def test_o_pad_que_levanta_na_volta_deixa_o_aviso_e_o_contador(daemon: Daemon) -> None:
    """O desfecho que levanta: o aviso sai pelo dono dos passos, com o contador em 1."""
    daemon.set_gamepad_emulation_desfecho = MagicMock(  # type: ignore[method-assign]
        side_effect=OSError("uinput sumiu"))
    avisos = _sair_do_nativo_com(daemon, {"gamepad": [True, "dualsense"]})
    assert [(a.get("laco"), a.get("passo")) for a in avisos] == [("nativo", "volta_do_pad")]
    assert daemon.store.counter("nativo.volta_falhou.excecao") == 1


def test_o_mouse_que_nao_volta_se_diz(daemon: Daemon) -> None:
    daemon.set_mouse_emulation = MagicMock(return_value=False)  # type: ignore[method-assign]
    avisos = _sair_do_nativo_com(daemon, {"mouse": [True, 6, 1]})
    assert [(a.get("o_que"), a.get("desfecho")) for a in avisos] == [("mouse", "falhou")]
    assert daemon.store.counter("nativo.volta_falhou.falhou") == 1


@pytest.mark.parametrize("desfecho", ["aplicado", "ja_estava", "bloqueado_por_jogo"])
def test_o_pad_que_volta_nao_avisa(daemon: Daemon, desfecho: str) -> None:
    daemon.set_gamepad_emulation_desfecho = MagicMock(  # type: ignore[method-assign]
        return_value=desfecho)
    assert _sair_do_nativo_com(daemon, {"gamepad": [True, "xbox"]}) == []
    assert not [k for k in daemon.store.snapshot().counters if k.startswith("nativo.")]
