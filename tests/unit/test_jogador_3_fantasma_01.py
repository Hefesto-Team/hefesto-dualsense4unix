"""Nunca existe um estado em que o jogo vê o físico E o virtual."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp


class _DaemonFalso:
    """O mínimo que os dois caminhos leem."""

    def __init__(self, *, excecao: bool, appid: int | None) -> None:
        self._steam_input_excecao = excecao
        self._steam_input_vpad_suspenso = excecao
        self._steam_input_flavor_suspenso = "dualsense" if excecao else None
        self._steam_input_coop_derrubados = 1 if excecao else 0
        self._steam_input_excecao_dispensada_appid: int | None = None
        self._appid_visivel = appid
        self._gamepad_device = None
        self.config = SimpleNamespace(
            gamepad_emulation_enabled=False, gamepad_flavor="dualsense"
        )

    def is_native_mode(self) -> bool:
        return False


APPID = 1599660


@pytest.fixture()
def daemon_com_jogo_marcado(monkeypatch: pytest.MonkeyPatch) -> _DaemonFalso:
    """Jogo da allowlist na frente, exceção ativa, vpads suspensos."""
    d = _DaemonFalso(excecao=True, appid=APPID)

    def _appid(daemon: Any, **_kw: Any) -> int | None:
        if getattr(daemon, "_steam_input_excecao_dispensada_appid", None) == APPID:
            return None
        return getattr(daemon, "_appid_visivel", None)

    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.launch_env.steam_input_exception_appid", _appid
    )
    return d


def test_o_gesto_manual_dispensa_a_excecao(daemon_com_jogo_marcado: _DaemonFalso) -> None:
    """Pedir o gamepad na mão tira a exceção do caminho — o gesto ganha inteiro."""
    d = daemon_com_jogo_marcado
    assert gp.steam_input_excecao_ativa(d) is True, "o cenário nasceu errado"

    gp.sync_steam_input_exception(d)
    d._steam_input_excecao_dispensada_appid = APPID
    d._steam_input_excecao = False

    assert gp.sync_steam_input_exception(d) is False, (
        "com a exceção dispensada por gesto, `sync` não pode religá-la — senão o "
        "grab volta a ser pulado no tique seguinte e o duplicado renasce."
    )
    assert gp.steam_input_excecao_ativa(d) is False

def test_a_dispensa_e_por_appid_e_nao_global(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dispensar um jogo não pode dispensar os outros da lista."""
    outro = 3357650
    d = _DaemonFalso(excecao=True, appid=outro)
    d._steam_input_excecao_dispensada_appid = APPID

    def _appid(daemon: Any, **_kw: Any) -> int | None:
        if getattr(daemon, "_steam_input_excecao_dispensada_appid", None) == getattr(
            daemon, "_appid_visivel", None
        ):
            return None
        return getattr(daemon, "_appid_visivel", None)

    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.launch_env.steam_input_exception_appid", _appid
    )

    assert gp.sync_steam_input_exception(d) is True, (
        "a dispensa de um appid vazou para outro — a marca do outro jogo dela "
        "parou de valer sem ninguém pedir."
    )


def test_sem_dispensa_a_excecao_continua_valendo(monkeypatch: pytest.MonkeyPatch) -> None:
    """O caminho normal não muda: jogo marcado na frente ⇒ exceção ativa."""
    d = _DaemonFalso(excecao=False, appid=APPID)

    def _appid(daemon: Any, **_kw: Any) -> int | None:
        if getattr(daemon, "_steam_input_excecao_dispensada_appid", None) == APPID:
            return None
        return getattr(daemon, "_appid_visivel", None)

    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.launch_env.steam_input_exception_appid", _appid
    )
    monkeypatch.setattr(gp, "_set_evdev_grab", lambda *_a, **_k: None)

    assert gp.sync_steam_input_exception(d) is True, (
        "jogo marcado na frente deixou de ligar a exceção — o controle dobrado "
        "que a marca existe para acabar voltaria."
    )
