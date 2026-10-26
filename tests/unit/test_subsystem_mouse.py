"""Testes unitários do subsystem Mouse (isolamento)."""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any, ClassVar
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.daemon.subsystems import SUBSYSTEM_REGISTRY
from hefesto_dualsense4unix.daemon.subsystems.mouse import (
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


class TestPartidaEParadaDoMouse:
    """A partida é `start_mouse_emulation`; a parada mora na lista (`SUBSYSTEM_REGISTRY`)."""

    def test_start_deixa_o_no_no_daemon(self, no_de_mentira: type[_NoDeMentira]) -> None:
        daemon = _ctx(enabled=True).daemon
        assert start_mouse_emulation(daemon) is True
        assert daemon._mouse_device is no_de_mentira.nascidos[0]
        assert len(no_de_mentira.nascidos) == 1

    def test_dois_starts_nao_criam_segundo_no(self, no_de_mentira: type[_NoDeMentira]) -> None:
        daemon = _ctx(enabled=True).daemon
        assert start_mouse_emulation(daemon) is True
        assert start_mouse_emulation(daemon) is True
        assert len(no_de_mentira.nascidos) == 1

    def test_o_gate_da_lista_pergunta_a_config(self) -> None:
        passo = next(p for p in SUBSYSTEM_REGISTRY if p.nome == "mouse")
        assert passo.quando is not None
        assert passo.quando(_ctx(enabled=True).config) is True
        assert passo.quando(_ctx(enabled=False).config) is False

    @pytest.mark.asyncio
    async def test_a_parada_da_lista_sem_no_e_idempotente(self) -> None:
        passo = next(p for p in SUBSYSTEM_REGISTRY if p.nome == "mouse")
        assert passo.parada is not None
        await passo.parada(_ctx(enabled=True).daemon)

    @pytest.mark.asyncio
    async def test_a_parada_da_lista_zera_o_no_do_daemon(
        self, no_de_mentira: type[_NoDeMentira]
    ) -> None:
        passo = next(p for p in SUBSYSTEM_REGISTRY if p.nome == "mouse")
        assert passo.parada is not None
        daemon = _ctx(enabled=True).daemon
        start_mouse_emulation(daemon)
        no = daemon._mouse_device
        await passo.parada(daemon)
        assert no.parou == 1
        assert daemon._mouse_device is None
        await passo.parada(daemon)
        assert no.parou == 1

    @pytest.mark.asyncio
    async def test_o_stop_do_subsystem_nao_esquece_a_preferencia_salva(
        self, no_de_mentira: type[_NoDeMentira], monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Desligar o daemon desce o nó, mas o mouse ligado volta ligado no próximo início.

        MORDIDA: trocar a parada por `stop_mouse_emulation(daemon)` sem `persist=False`
        grava o desligado.

        Prova da D-1510-O-STOP-DO-MOUSE-NAO-ESQUECE-A-PREFERENCIA.
        """
        gravados: list[bool] = []
        monkeypatch.setattr("hefesto_dualsense4unix.utils.session.save_mouse_emulation",
                            lambda ligado, *a, **k: gravados.append(ligado))
        passo = next(p for p in SUBSYSTEM_REGISTRY if p.nome == "mouse")
        assert passo.parada is not None
        daemon = _ctx(enabled=True).daemon
        start_mouse_emulation(daemon)
        await passo.parada(daemon)
        assert daemon._mouse_device is None
        assert gravados == [True], "a parada da lista gravou o mouse desligado na sessão"


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
