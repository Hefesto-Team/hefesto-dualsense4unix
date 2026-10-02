"""FEAT-AUTOSWITCH-LOCK-01 → O-FREESTYLE-E-UMA-CAMADA-SO-01 — o Modo Freestyle."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.autoswitch import AutoSwitcher
from hefesto_dualsense4unix.profiles.loader import save_profile
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import (
    MatchAny,
    MatchCriteria,
    Profile,
)
from hefesto_dualsense4unix.testing import FakeController

APPID_MMJ = 2111190
WM_MMJ = f"steam_app_{APPID_MMJ}"


@pytest.fixture
def isolated_profiles_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    target = tmp_path / "profiles"
    target.mkdir()

    def fake_profiles_dir(ensure: bool = False) -> Path:
        if ensure:
            target.mkdir(parents=True, exist_ok=True)
        return target

    monkeypatch.setattr(loader_module, "profiles_dir", fake_profiles_dir)
    return target


def _switcher(store: StateStore) -> tuple[AutoSwitcher, MagicMock]:
    manager = MagicMock(spec=ProfileManager)
    sw = AutoSwitcher(manager=manager, window_reader=lambda: {}, store=store)
    return sw, manager


def _switcher_real(store: StateStore) -> AutoSwitcher:
    """AutoSwitcher com ProfileManager REAL — o `select_for_window` de verdade"""
    fc = FakeController()
    fc.connect()
    return AutoSwitcher(
        manager=ProfileManager(controller=fc, store=store),
        window_reader=lambda: {},
        store=store,
    )


def _perfil_do_jogo() -> Profile:
    return Profile(
        name="madjack",
        match=MatchCriteria(window_class=[WM_MMJ]),
        priority=0,
    )


def _navegacao() -> Profile:
    return Profile(
        name="Navegação",
        match=MatchCriteria(window_class=["steam"]),
        priority=50,
    )


class TestStore:
    def test_default_desligado(self) -> None:
        assert StateStore().freestyle_ligado is False

    def test_liga_e_desliga(self) -> None:
        s = StateStore()
        s.set_freestyle_ligado(True)
        assert s.freestyle_ligado is True
        s.set_freestyle_ligado(False)
        assert s.freestyle_ligado is False


class TestAutoswitchRespeitaOFreestyle:
    def test_ligado_nao_troca_por_janela_comum(
        self, isolated_profiles_dir: Path
    ) -> None:
        """Nenhuma janela de desktop troca o perfil."""
        save_profile(_navegacao())
        store = StateStore()
        store.set_freestyle_ligado(True)
        sw = _switcher_real(store)

        for t in (0.0, 0.6, 30.0, 300.0):
            sw._tick({"wm_class": "steam", "wm_name": "Steam"}, t)

        assert sw._current_profile is None
        assert store.active_profile is None

    def test_ligado_nem_a_regra_propria_do_jogo_entra(
        self, isolated_profiles_dir: Path
    ) -> None:
        """A LOCK-CEDE-01 revogada: o jogo com perfil PRÓPRIO não entra."""
        save_profile(_perfil_do_jogo())
        save_profile(Profile(name="vitoria", match=MatchAny(), priority=5))
        store = StateStore()
        store.set_freestyle_ligado(True)
        sw = _switcher_real(store)

        for t in (0.0, 0.6, 60.0):
            sw._tick({"wm_class": WM_MMJ, "wm_name": "Mullet Mad Jack"}, t)

        assert sw._current_profile is None
        assert store.active_profile is None

    def test_desligado_volta_a_decidir(self) -> None:
        store = StateStore()
        store.set_freestyle_ligado(False)
        sw, manager = _switcher(store)
        manager.select_for_window.return_value = None
        sw._tick({"wm_class": "firefox", "wm_name": "Mozilla"}, 999.0)
        manager.select_for_window.assert_called()

    def test_o_metodo_publico_e_o_store_concordam(self) -> None:
        store = StateStore()
        sw, _ = _switcher(store)
        assert sw.freestyle_ligado() is False
        store.set_freestyle_ligado(True)
        assert sw.freestyle_ligado() is True

    def test_sem_store_nunca_ligado(self) -> None:
        sw = AutoSwitcher(manager=MagicMock(), window_reader=lambda: {})
        assert sw.freestyle_ligado() is False

    def test_log_da_parada_uma_vez_por_episodio(
        self, isolated_profiles_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A pergunta é feita a 2 Hz e o Freestyle fica ligado por horas —"""
        from hefesto_dualsense4unix.profiles import autoswitch as autoswitch_mod

        spy = MagicMock()
        monkeypatch.setattr(autoswitch_mod, "logger", spy)

        save_profile(_navegacao())
        store = StateStore()
        store.set_freestyle_ligado(True)
        sw = _switcher_real(store)

        for t in (0.0, 0.5, 1.0, 1.5, 2.0):
            sw._tick({"wm_class": "steam"}, t)

        eventos = [
            c
            for c in spy.info.call_args_list
            if c[0][0] == "autoswitch_parado_pelo_freestyle"
        ]
        assert len(eventos) == 1


class TestFreestyleNoRunLoop:
    """O `run()` REAL — a auditoria apontou que a cobertura parava no `_tick`"""

    @pytest.mark.asyncio
    async def test_run_ligado_nao_troca_por_janela_comum(
        self, isolated_profiles_dir: Path
    ) -> None:
        save_profile(_navegacao())
        store = StateStore()
        store.set_freestyle_ligado(True)
        fc = FakeController()
        fc.connect()
        manager = ProfileManager(controller=fc, store=store)
        sw = AutoSwitcher(
            manager=manager,
            window_reader=lambda: {"wm_class": "steam"},
            poll_interval_sec=0.02,
            debounce_sec=0.02,
            store=store,
        )
        sw.start()
        await asyncio.sleep(0.2)
        sw.stop()
        await sw._task  # type: ignore[union-attr]

        assert sw._current_profile is None
        assert manager.store.counter("profile.activated") == 0

    @pytest.mark.asyncio
    async def test_run_ligado_nao_cede_ao_perfil_do_jogo(
        self, isolated_profiles_dir: Path
    ) -> None:
        save_profile(_perfil_do_jogo())
        store = StateStore()
        store.set_freestyle_ligado(True)
        fc = FakeController()
        fc.connect()
        manager = ProfileManager(controller=fc, store=store)
        sw = AutoSwitcher(
            manager=manager,
            window_reader=lambda: {"wm_class": WM_MMJ},
            poll_interval_sec=0.02,
            debounce_sec=0.02,
            store=store,
        )
        sw.start()
        await asyncio.sleep(0.2)
        sw.stop()
        await sw._task  # type: ignore[union-attr]

        assert sw._current_profile is None
        assert manager.store.counter("profile.activated") == 0

    @pytest.mark.asyncio
    async def test_ligar_em_runtime_para_no_tique_seguinte(
        self, isolated_profiles_dir: Path
    ) -> None:
        """Ligar vale na hora (o `_tick` relê o store) — sem reiniciar o daemon"""
        save_profile(_navegacao())
        save_profile(
            Profile(
                name="leitura",
                match=MatchCriteria(window_class=["firefox"]),
                priority=50,
            )
        )
        store = StateStore()
        fc = FakeController()
        fc.connect()
        manager = ProfileManager(controller=fc, store=store)
        janela = {"wm_class": "steam"}
        sw = AutoSwitcher(
            manager=manager,
            window_reader=lambda: dict(janela),
            poll_interval_sec=0.02,
            debounce_sec=0.02,
            store=store,
        )
        sw.start()
        await asyncio.sleep(0.15)
        assert sw._current_profile == "Navegação"

        store.set_freestyle_ligado(True)
        janela["wm_class"] = "firefox"
        await asyncio.sleep(0.2)
        sw.stop()
        await sw._task  # type: ignore[union-attr]

        assert sw._current_profile == "Navegação"


class TestPersistencia:
    def test_flag_roundtrip(self, tmp_path: Any, monkeypatch: Any) -> None:
        from hefesto_dualsense4unix.utils import session as sess

        monkeypatch.setattr(sess, "config_dir", lambda ensure=False: tmp_path)
        assert sess.load_freestyle_ligado() is False
        sess.save_freestyle_ligado(True)
        assert sess.load_freestyle_ligado() is True
        sess.save_freestyle_ligado(False)
        assert sess.load_freestyle_ligado() is False

    @pytest.mark.asyncio
    async def test_boot_retoma_o_freestyle_da_sessao_anterior(
        self, isolated_profiles_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`lifecycle.run` carrega a flag no boot — a escolha dela atravessa"""
        from hefesto_dualsense4unix.core.controller import ControllerState
        from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig

        save_profile(
            Profile(name=loader_module.NOME_DO_PADRAO, match=MatchAny(), priority=0)
        )

        monkeypatch.setattr(
            "hefesto_dualsense4unix.daemon.lifecycle.INPUT_GRACE_SEC", 0.02
        )
        monkeypatch.setattr(
            "hefesto_dualsense4unix.utils.session.load_paused_state", lambda: False
        )
        monkeypatch.setattr(
            "hefesto_dualsense4unix.utils.session.save_paused_state", lambda _p: None
        )
        monkeypatch.setattr(
            "hefesto_dualsense4unix.utils.session.load_freestyle_ligado",
            lambda: True,
        )

        estado = ControllerState(
            battery_pct=80,
            l2_raw=0,
            r2_raw=0,
            connected=True,
            transport="usb",
            buttons_pressed=frozenset(),
        )
        config = DaemonConfig(
            poll_hz=200,
            auto_reconnect=False,
            ipc_enabled=False,
            udp_enabled=False,
            autoswitch_enabled=False,
            mouse_emulation_enabled=False,
            keyboard_emulation_enabled=False,
            ps_button_action="none",
            mic_button_toggles_system=False,
        )
        daemon = Daemon(
            controller=FakeController(transport="usb", states=[estado]),
            config=config,
        )
        task = asyncio.create_task(daemon.run())
        for _ in range(200):
            if daemon.store.active_profile == loader_module.NOME_DO_PADRAO:
                break
            await asyncio.sleep(0.01)
        try:
            assert daemon.store.freestyle_ligado is True
            assert daemon.store.active_profile == loader_module.NOME_DO_PADRAO
        finally:
            daemon.stop()
            await task


class TestRotasQueNaoConsultamOFreestyle:
    """Duas rotas que NÃO consultam o `freestyle_ligado`, de propósito."""

    def test_ciclo_por_hotkey_nao_consulta_o_freestyle(self) -> None:
        import inspect

        from hefesto_dualsense4unix.daemon.subsystems import hotkey as hotkey_mod

        fonte = inspect.getsource(hotkey_mod)
        assert "freestyle_ligado" not in fonte

    def test_dreno_de_modo_pendente_nao_consulta_o_freestyle(self) -> None:
        import inspect

        from hefesto_dualsense4unix.daemon.lifecycle import Daemon

        fonte = inspect.getsource(Daemon._drenar_modo_pendente)
        assert "freestyle_ligado" not in fonte
