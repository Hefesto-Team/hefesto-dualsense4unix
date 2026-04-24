"""Testes do WlrctlBackend (BUG-COSMIC-WLR-BACKEND-01).

Cobre:
  - Binário ausente → backend disponível=False, retorna None.
  - JSON válido com 1 toplevel → WindowInfo populado (app_id, title).
  - JSON vazio (`[]`) → None.
  - Stdout vazio → None.
  - JSON inválido → None.
  - returncode != 0 → None.
  - Timeout → None.
  - FileNotFoundError em runtime (binário sumiu) → marca indisponível.
  - OSError genérico → None.
  - Aceita variante `appId` além de `app_id`.
"""
from __future__ import annotations

import subprocess
from typing import Any
from unittest.mock import MagicMock

import pytest

from hefesto.integrations.window_backends import wlr_toplevel


def _patch_which(monkeypatch: pytest.MonkeyPatch, *, available: bool) -> None:
    """Substitui `shutil.which` no módulo para simular wlrctl ausente/presente."""
    monkeypatch.setattr(
        wlr_toplevel.shutil,
        "which",
        lambda binary: "/usr/bin/wlrctl" if available else None,
    )


def _patch_run(
    monkeypatch: pytest.MonkeyPatch,
    *,
    stdout: str = "",
    stderr: str = "",
    returncode: int = 0,
    raises: Exception | None = None,
) -> MagicMock:
    """Substitui `subprocess.run` no módulo. Retorna o spy."""
    spy = MagicMock()

    def _fake_run(*args: Any, **kwargs: Any) -> Any:
        spy(*args, **kwargs)
        if raises is not None:
            raise raises
        result = MagicMock()
        result.stdout = stdout
        result.stderr = stderr
        result.returncode = returncode
        return result

    monkeypatch.setattr(wlr_toplevel.subprocess, "run", _fake_run)
    return spy


def test_wlrctl_ausente_retorna_none(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_which(monkeypatch, available=False)
    backend = wlr_toplevel.WlrctlBackend()
    assert backend._available is False
    assert backend.get_active_window_info() is None


def test_wlrctl_present_e_json_valido(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_which(monkeypatch, available=True)
    _patch_run(
        monkeypatch,
        stdout='[{"app_id": "firefox", "title": "Mozilla Firefox"}]',
    )
    backend = wlr_toplevel.WlrctlBackend()
    info = backend.get_active_window_info()
    assert info is not None
    assert info.app_id == "firefox"
    assert info.wm_class == "firefox"
    assert info.title == "Mozilla Firefox"
    assert info.pid == 0  # wlr não expõe pid


def test_wlrctl_aceita_variante_appid_camelcase(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_which(monkeypatch, available=True)
    _patch_run(
        monkeypatch,
        stdout='[{"appId": "steam", "title": "Steam"}]',
    )
    backend = wlr_toplevel.WlrctlBackend()
    info = backend.get_active_window_info()
    assert info is not None
    assert info.app_id == "steam"
    assert info.wm_class == "steam"


def test_wlrctl_json_lista_vazia_retorna_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_which(monkeypatch, available=True)
    _patch_run(monkeypatch, stdout="[]")
    backend = wlr_toplevel.WlrctlBackend()
    assert backend.get_active_window_info() is None


def test_wlrctl_stdout_vazio_retorna_none(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_which(monkeypatch, available=True)
    _patch_run(monkeypatch, stdout="")
    backend = wlr_toplevel.WlrctlBackend()
    assert backend.get_active_window_info() is None


def test_wlrctl_json_invalido_retorna_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_which(monkeypatch, available=True)
    _patch_run(monkeypatch, stdout="not json {")
    backend = wlr_toplevel.WlrctlBackend()
    assert backend.get_active_window_info() is None


def test_wlrctl_returncode_diferente_zero_retorna_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_which(monkeypatch, available=True)
    _patch_run(monkeypatch, returncode=2, stderr="protocol not supported")
    backend = wlr_toplevel.WlrctlBackend()
    assert backend.get_active_window_info() is None


def test_wlrctl_timeout_retorna_none(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_which(monkeypatch, available=True)
    _patch_run(
        monkeypatch,
        raises=subprocess.TimeoutExpired(cmd=["wlrctl"], timeout=1.0),
    )
    backend = wlr_toplevel.WlrctlBackend()
    assert backend.get_active_window_info() is None


def test_wlrctl_filenotfound_marca_indisponivel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Binário some entre o which() inicial e a chamada — backend marca
    indisponível para evitar reabrir subprocess a cada tick."""
    _patch_which(monkeypatch, available=True)
    _patch_run(monkeypatch, raises=FileNotFoundError("wlrctl not found"))
    backend = wlr_toplevel.WlrctlBackend()
    assert backend._available is True  # antes da chamada
    assert backend.get_active_window_info() is None
    assert backend._available is False  # marcou após FileNotFoundError


def test_wlrctl_oserror_retorna_none(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_which(monkeypatch, available=True)
    _patch_run(monkeypatch, raises=OSError("disk full or smt"))
    backend = wlr_toplevel.WlrctlBackend()
    assert backend.get_active_window_info() is None
    # Diferença de FileNotFoundError: OSError genérico NÃO marca indisponível
    # (pode ser transiente). Próxima chamada vai tentar de novo.
    assert backend._available is True


def test_wlrctl_toplevel_nao_dict_retorna_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Defesa: se wlrctl mudar formato e retornar string em vez de dict."""
    _patch_which(monkeypatch, available=True)
    _patch_run(monkeypatch, stdout='["just_a_string"]')
    backend = wlr_toplevel.WlrctlBackend()
    assert backend.get_active_window_info() is None


def test_wlrctl_sem_app_id_nem_title(monkeypatch: pytest.MonkeyPatch) -> None:
    """Toplevel com dict vazio → wm_class='unknown', title=''."""
    _patch_which(monkeypatch, available=True)
    _patch_run(monkeypatch, stdout="[{}]")
    backend = wlr_toplevel.WlrctlBackend()
    info = backend.get_active_window_info()
    assert info is not None
    assert info.wm_class == "unknown"
    assert info.app_id == ""
    assert info.title == ""


def test_wlrctl_chama_wlrctl_com_args_corretos(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_which(monkeypatch, available=True)
    spy = _patch_run(
        monkeypatch,
        stdout='[{"app_id": "x", "title": "y"}]',
    )
    backend = wlr_toplevel.WlrctlBackend()
    backend.get_active_window_info()
    args, kwargs = spy.call_args
    cmd = args[0]
    assert cmd[0] == "wlrctl"
    assert "toplevel" in cmd
    assert "--json" in cmd
    assert "--state" in cmd and "activated" in cmd
    assert kwargs.get("timeout") == 1.0
    assert kwargs.get("check") is False
    assert kwargs.get("text") is True
