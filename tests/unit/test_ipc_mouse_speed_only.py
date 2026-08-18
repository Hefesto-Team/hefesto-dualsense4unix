"""Rota speed-only de mouse.emulation.set (BUG-MOUSE-GUI-SYNC-01 A4).

Prova que:
  - Handler sem 'enabled' chama Daemon.set_mouse_speed (nunca set_mouse_emulation).
  - Handler com 'enabled' bool preserva o contrato original (FEAT-MOUSE-01).
  - 'enabled' com tipo inválido continua rejeitado.
  - Daemon.set_mouse_speed com device vivo aplica set_speed sem start/stop.
  - Daemon.set_mouse_speed sem device NÃO cria device, NÃO liga emulação e
    NÃO persiste o flag — regressão do A4 (slider religava emulação e matava
    o gamepad virtual em pleno jogo).
  - FEAT-MOUSE-CURSOR-FEEL-01 (A5): com a emulação JÁ ligada, set_mouse_speed
    e set_mouse_emulation re-persistem o flag com as velocidades novas
    (mudança de speed com mouse ligado sobrevive a restart).
  - Velocidades são clampadas ao contrato (speed 1-12, scroll 1-5).
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.testing import FakeController

# ---------------------------------------------------------------------------
# Handler _handle_mouse_emulation_set
# ---------------------------------------------------------------------------


class _FakeConfig:
    mouse_emulation_enabled = False
    mouse_speed = 6
    mouse_scroll_speed = 1


class _FakeDaemon:
    def __init__(self, enabled: bool = False) -> None:
        self.config = _FakeConfig()
        self.config.mouse_emulation_enabled = enabled
        self.speed_calls: list[tuple[int | None, int | None]] = []
        self.emulation_calls: list[tuple[bool, int | None, int | None]] = []

    def set_mouse_speed(
        self, speed: int | None = None, scroll_speed: int | None = None
    ) -> bool:
        self.speed_calls.append((speed, scroll_speed))
        return True

    def set_mouse_emulation(
        self,
        enabled: bool,
        speed: int | None = None,
        scroll_speed: int | None = None,
    ) -> bool:
        self.emulation_calls.append((enabled, speed, scroll_speed))
        return True


class _Handlers(IpcHandlersMixin):
    def __init__(self, daemon: object) -> None:
        self.daemon = daemon  # type: ignore[assignment]


@pytest.mark.asyncio
async def test_speed_only_chama_set_mouse_speed() -> None:
    d = _FakeDaemon()
    res = await _Handlers(d)._handle_mouse_emulation_set({"speed": 9})
    assert res["status"] == "ok"
    assert d.speed_calls == [(9, None)]
    assert d.emulation_calls == []


@pytest.mark.asyncio
async def test_speed_only_reporta_enabled_corrente() -> None:
    """Sem 'enabled' no request, a resposta reflete o estado VIVO da config."""
    ligado = _FakeDaemon(enabled=True)
    res = await _Handlers(ligado)._handle_mouse_emulation_set({"speed": 3})
    assert res["enabled"] is True

    desligado = _FakeDaemon(enabled=False)
    res = await _Handlers(desligado)._handle_mouse_emulation_set({"scroll_speed": 2})
    assert res["enabled"] is False


@pytest.mark.asyncio
async def test_enabled_bool_preserva_contrato_original() -> None:
    d = _FakeDaemon()
    res = await _Handlers(d)._handle_mouse_emulation_set(
        {"enabled": True, "speed": 7, "scroll_speed": 2}
    )
    assert res == {"status": "ok", "enabled": True}
    assert d.emulation_calls == [(True, 7, 2)]
    assert d.speed_calls == []


@pytest.mark.asyncio
async def test_enabled_tipo_invalido_rejeitado() -> None:
    with pytest.raises(ValueError, match="enabled"):
        await _Handlers(_FakeDaemon())._handle_mouse_emulation_set({"enabled": "sim"})


@pytest.mark.asyncio
async def test_speed_tipo_invalido_rejeitado_na_rota_speed_only() -> None:
    with pytest.raises(ValueError, match="speed"):
        await _Handlers(_FakeDaemon())._handle_mouse_emulation_set({"speed": "9"})


@pytest.mark.asyncio
async def test_sem_daemon_erro() -> None:
    with pytest.raises(ValueError, match="daemon"):
        await _Handlers(None)._handle_mouse_emulation_set({"speed": 9})


# ---------------------------------------------------------------------------
# Daemon.set_mouse_speed (lifecycle)
# ---------------------------------------------------------------------------


def _make_daemon() -> Daemon:
    """Daemon mínimo sem IPC/UDP/autoswitch para exercitar set_mouse_speed."""
    return Daemon(
        controller=FakeController(transport="usb", states=[]),
        config=DaemonConfig(
            ipc_enabled=False,
            udp_enabled=False,
            autoswitch_enabled=False,
        ),
    )


def test_set_mouse_speed_com_device_vivo_aplica_sem_recriar() -> None:
    """Mouse LIGADO: muda velocidade ao vivo, sem destruir/recriar o device."""
    daemon = _make_daemon()
    device = MagicMock()
    daemon._mouse_device = device
    daemon.config.mouse_emulation_enabled = True

    assert daemon.set_mouse_speed(speed=9) is True

    assert daemon._mouse_device is device
    device.stop.assert_not_called()
    device.set_speed.assert_called_once_with(mouse_speed=9, scroll_speed=1)
    assert daemon.config.mouse_speed == 9


def test_set_mouse_speed_sem_device_nao_liga_nem_cria(monkeypatch) -> None:
    """Mouse DESLIGADO: atualiza config, NÃO liga emulação, NÃO cria device e
    NÃO persiste flag — regressão do A4 (slider religava a emulação)."""
    from hefesto_dualsense4unix.utils import session

    persist_calls: list[object] = []
    monkeypatch.setattr(
        session,
        "save_mouse_emulation_enabled",
        lambda enabled: persist_calls.append(enabled),
    )
    monkeypatch.setattr(
        session,
        "save_mouse_emulation",
        lambda *a, **k: persist_calls.append((a, k)),
    )

    daemon = _make_daemon()
    assert daemon._mouse_device is None

    assert daemon.set_mouse_speed(speed=9, scroll_speed=3) is True

    assert daemon._mouse_device is None
    assert daemon.config.mouse_emulation_enabled is False
    assert daemon.config.mouse_speed == 9
    assert daemon.config.mouse_scroll_speed == 3
    assert persist_calls == []


def test_set_mouse_speed_com_emulacao_ligada_re_persiste_flag(monkeypatch) -> None:
    """FEAT-MOUSE-CURSOR-FEEL-01 (A5): com a emulação LIGADA, mudar a
    velocidade re-salva o flag JSON — o speed novo sobrevive a restart."""
    from hefesto_dualsense4unix.utils import session

    saved: list[tuple[bool, int | None, int | None]] = []
    monkeypatch.setattr(
        session,
        "save_mouse_emulation",
        lambda enabled, speed=None, scroll_speed=None: saved.append(
            (enabled, speed, scroll_speed)
        ),
    )

    daemon = _make_daemon()
    daemon._mouse_device = MagicMock()
    daemon.config.mouse_emulation_enabled = True

    assert daemon.set_mouse_speed(speed=9, scroll_speed=3) is True

    assert saved == [(True, 9, 3)]


def test_set_mouse_speed_clampa_ao_contrato() -> None:
    """Contrato speed 1-12 / scroll 1-5 vale também na rota speed-only."""
    daemon = _make_daemon()
    daemon.set_mouse_speed(speed=99, scroll_speed=0)
    assert daemon.config.mouse_speed == 12
    assert daemon.config.mouse_scroll_speed == 1


def test_set_mouse_emulation_ligar_ja_ligado_re_persiste_velocidades(
    monkeypatch,
) -> None:
    """FEAT-MOUSE-CURSOR-FEEL-01 (A5): 'ligar' com device JÁ vivo (start
    retorna cedo sem salvar) re-persiste o flag com as velocidades novas."""
    from hefesto_dualsense4unix.utils import session

    saved: list[tuple[bool, int | None, int | None]] = []
    monkeypatch.setattr(
        session,
        "save_mouse_emulation",
        lambda enabled, speed=None, scroll_speed=None: saved.append(
            (enabled, speed, scroll_speed)
        ),
    )

    daemon = _make_daemon()
    device = MagicMock()
    daemon._mouse_device = device
    daemon.config.mouse_emulation_enabled = True

    assert daemon.set_mouse_emulation(True, speed=11, scroll_speed=2) is True

    device.set_speed.assert_called_once_with(mouse_speed=11, scroll_speed=2)
    assert saved == [(True, 11, 2)]
