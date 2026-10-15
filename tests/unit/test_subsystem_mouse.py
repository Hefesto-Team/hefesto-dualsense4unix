"""Testes unitários do subsystem Mouse (isolamento)."""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any, ClassVar
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.daemon.subsystems.mouse import (
    MouseSubsystem,
    dispatch_mouse,
    start_mouse_emulation,
    stop_mouse_emulation,
)


class _NoDeMentira:
    """Um `UinputMouseDevice` de mentira que conta quantos nasceram."""

    nascidos: ClassVar[list[_NoDeMentira]] = []

    def __init__(self, **_: Any) -> None:
        self.parou = 0
        _NoDeMentira.nascidos.append(self)

    def start(self) -> bool:
        return True

    def stop(self) -> None:
        self.parou += 1


@pytest.fixture
def no_de_mentira(monkeypatch: pytest.MonkeyPatch) -> type[_NoDeMentira]:
    _NoDeMentira.nascidos = []
    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.uinput_mouse.UinputMouseDevice", _NoDeMentira)
    monkeypatch.setattr(
        "hefesto_dualsense4unix.utils.session.save_mouse_emulation", lambda *a, **k: None)
    return _NoDeMentira


def _ctx(enabled: bool) -> SimpleNamespace:
    daemon = SimpleNamespace(
        _mouse_device=None,
        config=SimpleNamespace(
            mouse_emulation_enabled=enabled, mouse_speed=6, mouse_scroll_speed=1, poll_hz=60),
    )
    return SimpleNamespace(config=daemon.config, daemon=daemon)


class TestMouseSubsystem:
    def _make_config(self, enabled: bool) -> MagicMock:
        cfg = MagicMock()
        cfg.mouse_emulation_enabled = enabled
        return cfg

    def test_is_enabled_true(self) -> None:
        subsystem = MouseSubsystem()
        assert subsystem.is_enabled(self._make_config(enabled=True)) is True

    def test_is_enabled_false(self) -> None:
        subsystem = MouseSubsystem()
        assert subsystem.is_enabled(self._make_config(enabled=False)) is False

    @pytest.mark.asyncio
    async def test_stop_idempotente_sem_device(self) -> None:
        subsystem = MouseSubsystem()
        await subsystem.stop()

    @pytest.mark.asyncio
    async def test_start_deixa_o_no_no_daemon(self, no_de_mentira: type[_NoDeMentira]) -> None:
        ctx = _ctx(enabled=True)
        await MouseSubsystem().start(ctx)
        assert ctx.daemon._mouse_device is no_de_mentira.nascidos[0]
        assert len(no_de_mentira.nascidos) == 1

    @pytest.mark.asyncio
    async def test_a_classe_nao_guarda_no_proprio(self, no_de_mentira: type[_NoDeMentira]) -> None:
        subsystem = MouseSubsystem()
        await subsystem.start(_ctx(enabled=True))
        assert getattr(subsystem, "_device", None) is None

    @pytest.mark.asyncio
    async def test_start_desligado_nao_cria_no(self, no_de_mentira: type[_NoDeMentira]) -> None:
        ctx = _ctx(enabled=False)
        await MouseSubsystem().start(ctx)
        assert ctx.daemon._mouse_device is None
        assert no_de_mentira.nascidos == []

    @pytest.mark.asyncio
    async def test_dois_starts_e_a_funcao_nao_criam_segundo_no(
        self, no_de_mentira: type[_NoDeMentira]
    ) -> None:
        ctx = _ctx(enabled=True)
        subsystem = MouseSubsystem()
        await subsystem.start(ctx)
        await subsystem.start(ctx)
        assert start_mouse_emulation(ctx.daemon) is True
        assert len(no_de_mentira.nascidos) == 1

    @pytest.mark.asyncio
    async def test_stop_zera_o_no_do_daemon(self, no_de_mentira: type[_NoDeMentira]) -> None:
        ctx = _ctx(enabled=True)
        subsystem = MouseSubsystem()
        await subsystem.start(ctx)
        no = ctx.daemon._mouse_device
        await subsystem.stop()
        assert no.parou == 1
        assert ctx.daemon._mouse_device is None
        await subsystem.stop()
        assert no.parou == 1


class TestTabelaNoJogoFechaOsDois:
    def test_o_stop_do_teclado_roda_mesmo_se_o_do_mouse_levanta(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from hefesto_dualsense4unix.daemon.subsystems.mouse import TabelaNoJogo

        eventos: list[str] = []

        class Mouse:
            def __init__(self, **_: Any) -> None: ...
            def start(self) -> bool:
                return True
            def stop(self) -> None:
                eventos.append("mouse")
                raise RuntimeError("falha")

        class Teclado:
            virtual_token_callback = None
            def start(self) -> bool:
                return False
            def stop(self) -> None:
                eventos.append("teclado")

        monkeypatch.setattr(
            "hefesto_dualsense4unix.integrations.uinput_mouse.UinputMouseDevice", Mouse)
        monkeypatch.setattr(
            "hefesto_dualsense4unix.integrations.uinput_keyboard.UinputKeyboardDevice", Teclado)
        daemon = SimpleNamespace(
            config=SimpleNamespace(mouse_speed=6, mouse_scroll_speed=1, poll_hz=60))
        tabela = TabelaNoJogo({}, {}, ligada=True)
        assert tabela._abrir(daemon) is False
        assert eventos == ["mouse", "teclado"]


class TestStopMouseEmulation:
    def _make_daemon(self) -> MagicMock:
        daemon = MagicMock()
        daemon._mouse_device = None
        daemon.config = MagicMock()
        daemon.config.mouse_emulation_enabled = True
        return daemon

    def test_stop_descarta_device(self) -> None:
        daemon = self._make_daemon()
        mock_dev = MagicMock()
        daemon._mouse_device = mock_dev

        stop_mouse_emulation(daemon)

        mock_dev.stop.assert_called_once()
        assert daemon._mouse_device is None
        assert daemon.config.mouse_emulation_enabled is False

    def test_stop_noop_sem_device(self) -> None:
        daemon = self._make_daemon()
        daemon._mouse_device = None
        stop_mouse_emulation(daemon)


class TestDispatchMouse:
    def _make_state(self) -> MagicMock:
        state = MagicMock()
        state.raw_lx = 128
        state.raw_ly = 128
        state.raw_rx = 128
        state.raw_ry = 128
        state.l2_raw = 0
        state.r2_raw = 0
        return state

    def test_dispatch_chama_device_com_parametros_corretos(self) -> None:
        daemon = MagicMock()
        mock_dev = MagicMock()
        daemon._mouse_device = mock_dev
        state = self._make_state()
        buttons = frozenset({"cross"})

        dispatch_mouse(daemon, state, buttons)

        mock_dev.dispatch.assert_called_once_with(
            lx=128, ly=128, rx=128, ry=128, l2=0, r2=0, buttons=buttons
        )

    def test_dispatch_noop_sem_device(self) -> None:
        daemon = MagicMock()
        daemon._mouse_device = None
        state = self._make_state()
        dispatch_mouse(daemon, state, frozenset())

    def test_dispatch_trata_excecao(self) -> None:
        daemon = MagicMock()
        mock_dev = MagicMock()
        mock_dev.dispatch.side_effect = RuntimeError("falha dispatch")
        daemon._mouse_device = mock_dev
        state = self._make_state()

        dispatch_mouse(daemon, state, frozenset())
