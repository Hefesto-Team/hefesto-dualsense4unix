"""VPAD-NA-JANELA-DA-STEAM-01 (17/08/2026) — o alt-tab que matava o controle."""

from __future__ import annotations

import pytest

from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.profiles.steam_app import (
    e_janela_do_cliente_steam,
    steam_appid_from_wm_class,
)
from hefesto_dualsense4unix.testing.fake_controller import FakeController


@pytest.fixture
def daemon() -> Daemon:
    """O mesmo daemon de bancada do `test_profile_mode.py`."""
    return Daemon(controller=FakeController(), config=DaemonConfig())


class TestOPredicado:
    """`e_janela_do_cliente_steam` — a pergunta que faltava, isolada."""

    @pytest.mark.parametrize(
        "wm_class",
        ["steam", "Steam", "  Steam  ", "STEAM", "steamwebhelper", "SteamWebHelper"],
    )
    def test_o_cliente_steam_e_reconhecido(self, wm_class: str) -> None:
        """Insensível a caixa e tolerante a espaço — contrato do módulo."""
        assert e_janela_do_cliente_steam(wm_class) is True

    @pytest.mark.parametrize(
        "wm_class",
        ["firefox", "gnome-terminal", "steam_app_2497900", "", "steamy", "n"],
    )
    def test_o_que_nao_e_o_cliente_fica_de_fora(self, wm_class: str) -> None:
        assert e_janela_do_cliente_steam(wm_class) is False

    def test_nao_engole_none_nem_tipo_errado(self) -> None:
        assert e_janela_do_cliente_steam(None) is False
        assert e_janela_do_cliente_steam(123) is False  # type: ignore[arg-type]

    def test_as_duas_perguntas_sao_disjuntas_e_complementares(self) -> None:
        """Jogo tem appid; cliente não tem. Nenhuma wm_class é as duas coisas."""
        assert steam_appid_from_wm_class("steam_app_2497900") == 2497900
        assert e_janela_do_cliente_steam("steam_app_2497900") is False

        assert steam_appid_from_wm_class("steam") is None
        assert e_janela_do_cliente_steam("steam") is True


class TestAGuardaNoDaemon:
    """`_janela_de_jogo_em_foco` — a guarda que protege a partida."""

    def test_a_janela_da_steam_protege_a_partida(self, daemon: Daemon) -> None:
        """A MORDIDA. Arranque o `e_janela_do_cliente_steam` da guarda e este"""
        daemon.store.record_window_detect_read("teste", "steam")
        assert daemon._janela_de_jogo_em_foco() is True, (
            "a guarda não reconheceu a janela do cliente Steam — alternar para "
            "a Steam no meio do jogo volta a destruir o vpad"
        )

    def test_a_janela_do_jogo_continua_protegida(self, daemon: Daemon) -> None:
        """O caso de 23/07 não pode ter sido trocado pelo novo."""
        daemon.store.record_window_detect_read("teste", "steam_app_2497900")
        assert daemon._janela_de_jogo_em_foco() is True

    def test_o_desktop_de_verdade_continua_desprotegido(self, daemon: Daemon) -> None:
        """A reversão legítima continua existindo — senão o perfil GRUDA."""
        for wm_class in ("firefox", "gnome-terminal", "brave-browser", ""):
            daemon.store.record_window_detect_read("teste", wm_class)
            assert daemon._janela_de_jogo_em_foco() is False, wm_class
