"""Testes unitários para FEAT-RUMBLE-POLICY-01 — política de intensidade de rumble.

Cobre:
- Cada preset retorna mult correto.
- Modo Auto respeita battery thresholds (mock battery_pct 80/40/10).
- Debounce 5s evita flapping em modo auto.
- rumble.set(100, 200) com policy "economia" aplica (30, 60).
- RumbleEngine aplica mult via _apply_with_policy.
- _handle_rumble_policy_set e _handle_rumble_policy_custom do IPC.
"""
from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from hefesto.core.rumble import RumbleEngine, _effective_mult
from hefesto.daemon.lifecycle import (
    DaemonConfig,
    _effective_mult_inline,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _config(policy: str, custom_mult: float = 0.7) -> DaemonConfig:
    cfg = DaemonConfig()
    cfg.rumble_policy = policy  # type: ignore[assignment]
    cfg.rumble_policy_custom_mult = custom_mult
    return cfg


# ---------------------------------------------------------------------------
# Presets
# ---------------------------------------------------------------------------

class TestPresets:
    """Cada preset retorna o multiplicador esperado."""

    def test_economia(self) -> None:
        cfg = _config("economia")
        mult, _, _ = _effective_mult_inline(cfg, 100, 1.0, 0.7, 0.0)
        assert mult == pytest.approx(0.3)

    def test_balanceado(self) -> None:
        cfg = _config("balanceado")
        mult, _, _ = _effective_mult_inline(cfg, 100, 1.0, 0.7, 0.0)
        assert mult == pytest.approx(0.7)

    def test_max(self) -> None:
        cfg = _config("max")
        mult, _, _ = _effective_mult_inline(cfg, 100, 1.0, 0.7, 0.0)
        assert mult == pytest.approx(1.0)

    def test_custom(self) -> None:
        cfg = _config("custom", custom_mult=0.45)
        mult, _, _ = _effective_mult_inline(cfg, 100, 1.0, 0.7, 0.0)
        assert mult == pytest.approx(0.45)

    def test_custom_via_rumble_py(self) -> None:
        """Garante que a _effective_mult em rumble.py retorna igual."""
        cfg = _config("custom", custom_mult=0.55)
        mult, _, _ = _effective_mult(cfg, 80, 1.0, 0.7, 0.0)
        assert mult == pytest.approx(0.55)


# ---------------------------------------------------------------------------
# Modo Auto — thresholds de bateria
# ---------------------------------------------------------------------------

class TestAutoMode:
    """Modo auto respeita thresholds de bateria."""

    def test_bateria_alta(self) -> None:
        cfg = _config("auto")
        mult, new_last, _new_at = _effective_mult_inline(cfg, 80, 1.0, 0.7, 0.0)
        assert mult == pytest.approx(1.0)
        assert new_last == pytest.approx(1.0)

    def test_bateria_media(self) -> None:
        cfg = _config("auto")
        mult, _, _ = _effective_mult_inline(cfg, 40, 1.0, 1.0, 0.0)
        assert mult == pytest.approx(0.7)

    def test_bateria_baixa(self) -> None:
        cfg = _config("auto")
        mult, _, _ = _effective_mult_inline(cfg, 10, 1.0, 1.0, 0.0)
        assert mult == pytest.approx(0.3)

    def test_limiar_exato_50(self) -> None:
        """battery_pct == 50 deve retornar 0.7 (>50 para 1.0)."""
        cfg = _config("auto")
        mult, _, _ = _effective_mult_inline(cfg, 50, 1.0, 1.0, 0.0)
        assert mult == pytest.approx(0.7)

    def test_limiar_exato_51(self) -> None:
        cfg = _config("auto")
        mult, _, _ = _effective_mult_inline(cfg, 51, 1.0, 0.7, 0.0)
        assert mult == pytest.approx(1.0)

    def test_limiar_exato_20(self) -> None:
        """battery_pct == 20 deve retornar 0.7 (>=20 para 0.7)."""
        cfg = _config("auto")
        mult, _, _ = _effective_mult_inline(cfg, 20, 1.0, 1.0, 0.0)
        assert mult == pytest.approx(0.7)

    def test_limiar_exato_19(self) -> None:
        cfg = _config("auto")
        mult, _, _ = _effective_mult_inline(cfg, 19, 1.0, 1.0, 0.0)
        assert mult == pytest.approx(0.3)


# ---------------------------------------------------------------------------
# Debounce do modo auto
# ---------------------------------------------------------------------------

class TestAutoDebounce:
    """Debounce de 5s evita flapping no modo auto."""

    def test_sem_debounce_muda(self) -> None:
        """Primeira mudança (last_change_at == 0.0) ocorre imediatamente."""
        cfg = _config("auto")
        # Começa sem debounce registrado (0.0).
        mult, new_last, new_at = _effective_mult_inline(cfg, 10, 100.0, 0.7, 0.0)
        assert mult == pytest.approx(0.3)
        assert new_last == pytest.approx(0.3)
        assert new_at == pytest.approx(100.0)

    def test_dentro_debounce_nao_muda(self) -> None:
        """Mudança dentro de 5s mantém mult anterior."""
        cfg = _config("auto")
        # bateria 10% -> mult alvo 0.3; mas debounce: last_change_at=100.0, now=102.0 (<5s).
        mult, new_last, new_at = _effective_mult_inline(
            cfg, 10, 102.0, 0.7, 100.0  # 2s desde mudança
        )
        assert mult == pytest.approx(0.7)  # mantém anterior
        assert new_last == pytest.approx(0.7)
        assert new_at == pytest.approx(100.0)  # timestamp não muda

    def test_apos_debounce_muda(self) -> None:
        """Mudança após 5s+ é aplicada."""
        cfg = _config("auto")
        mult, new_last, new_at = _effective_mult_inline(
            cfg, 10, 106.0, 0.7, 100.0  # 6s desde mudança
        )
        assert mult == pytest.approx(0.3)
        assert new_last == pytest.approx(0.3)
        assert new_at == pytest.approx(106.0)

    def test_sem_mudanca_mantem(self) -> None:
        """Se target == last_auto_mult, retorna estável sem debounce."""
        cfg = _config("auto")
        mult, new_last, new_at = _effective_mult_inline(
            cfg, 80, 200.0, 1.0, 100.0  # bateria 80% -> alvo 1.0 = current
        )
        assert mult == pytest.approx(1.0)
        assert new_last == pytest.approx(1.0)
        assert new_at == pytest.approx(100.0)  # timestamp não muda


# ---------------------------------------------------------------------------
# Integração: rumble.set com política
# ---------------------------------------------------------------------------

class TestRumbleSetComPolitica:
    """rumble.set(100, 200) com policy 'economia' aplica (30, 60)."""

    def test_economia_aplica_mult_30(self) -> None:
        controller = MagicMock()
        engine = RumbleEngine(controller, time_fn=lambda: 1.0)
        cfg = _config("economia")

        # Injeta referência ao config (sem state_ref — fallback para battery 50).
        engine.link(cfg, None)

        engine.set(100, 200)
        applied = engine.tick()

        assert applied is not None
        # 100 * 0.3 = 30, 200 * 0.3 = 60
        controller.set_rumble.assert_called_once_with(weak=30, strong=60)

    def test_balanceado_aplica_mult_70(self) -> None:
        controller = MagicMock()
        engine = RumbleEngine(controller, time_fn=lambda: 1.0)
        cfg = _config("balanceado")
        engine.link(cfg, None)

        engine.set(100, 100)
        engine.tick()

        # 100 * 0.7 = 70
        controller.set_rumble.assert_called_once_with(weak=70, strong=70)

    def test_max_sem_alteracao(self) -> None:
        controller = MagicMock()
        engine = RumbleEngine(controller, time_fn=lambda: 1.0)
        cfg = _config("max")
        engine.link(cfg, None)

        engine.set(100, 200)
        engine.tick()

        # 100 * 1.0 = 100, 200 * 1.0 = 200
        controller.set_rumble.assert_called_once_with(weak=100, strong=200)

    def test_clamp_resultado(self) -> None:
        """Resultado é clampado em [0, 255]."""
        controller = MagicMock()
        engine = RumbleEngine(controller, time_fn=lambda: 1.0)
        cfg = _config("max")
        engine.link(cfg, None)

        engine.set(255, 255)
        engine.tick()

        controller.set_rumble.assert_called_once_with(weak=255, strong=255)

    def test_sem_link_usa_mult_1(self) -> None:
        """Sem link(), engine aplica mult 1.0 (modo legacy)."""
        controller = MagicMock()
        engine = RumbleEngine(controller, time_fn=lambda: 1.0)

        engine.set(100, 200)
        engine.tick()

        controller.set_rumble.assert_called_once_with(weak=100, strong=200)

    def test_auto_com_bateria_baixa(self) -> None:
        """Modo auto + battery 10% -> mult 0.3."""
        controller = MagicMock()
        engine = RumbleEngine(controller, time_fn=lambda: 1.0)
        cfg = _config("auto")

        state_ref = MagicMock()
        state_ref.battery_pct = 10
        engine.link(cfg, state_ref)
        # Inicializa debounce como primeira mudança (last_change_at == 0.0).
        engine._last_auto_change_at = 0.0
        engine._last_auto_mult = 0.7

        engine.set(100, 200)
        engine.tick()

        # 100 * 0.3 = 30, 200 * 0.3 = 60
        controller.set_rumble.assert_called_once_with(weak=30, strong=60)


# ---------------------------------------------------------------------------
# IPC handlers
# ---------------------------------------------------------------------------

class TestIpcHandlers:
    """_handle_rumble_policy_set e _handle_rumble_policy_custom."""

    def _make_server(self) -> object:
        """Cria IpcServer com config de daemon mockado."""
        from hefesto.daemon.ipc_server import IpcServer
        from hefesto.daemon.state_store import StateStore

        ctrl = MagicMock()
        store = StateStore()
        store.update_controller_state(MagicMock(battery_pct=80))
        pm = MagicMock()

        daemon_cfg = DaemonConfig()
        daemon = MagicMock()
        daemon.config = daemon_cfg
        daemon.store = store

        server = IpcServer(
            controller=ctrl,
            store=store,
            profile_manager=pm,
            daemon=daemon,
        )
        return server, daemon_cfg

    def test_policy_set_valida(self) -> None:
        server, cfg = self._make_server()
        result = asyncio.run(server._handle_rumble_policy_set({"policy": "economia"}))
        assert result == {"status": "ok", "policy": "economia"}
        assert cfg.rumble_policy == "economia"

    def test_policy_set_invalida(self) -> None:
        server, _cfg = self._make_server()
        with pytest.raises(ValueError, match="deve ser um de"):
            asyncio.run(server._handle_rumble_policy_set({"policy": "turbinado"}))

    def test_policy_custom(self) -> None:
        server, cfg = self._make_server()
        result = asyncio.run(server._handle_rumble_policy_custom({"mult": 0.45}))
        assert result == {"status": "ok", "mult": pytest.approx(0.45)}
        assert cfg.rumble_policy == "custom"
        assert cfg.rumble_policy_custom_mult == pytest.approx(0.45)

    def test_policy_custom_fora_de_range(self) -> None:
        server, _cfg = self._make_server()
        with pytest.raises(ValueError, match="fora de"):
            asyncio.run(server._handle_rumble_policy_custom({"mult": 1.5}))

    def test_policy_auto(self) -> None:
        server, cfg = self._make_server()
        result = asyncio.run(server._handle_rumble_policy_set({"policy": "auto"}))
        assert result["policy"] == "auto"
        assert cfg.rumble_policy == "auto"

    def test_state_full_inclui_rumble_policy(self) -> None:
        """daemon.state_full retorna rumble_policy no payload."""
        server, _cfg = self._make_server()

        snap_ctrl = MagicMock()
        snap_ctrl.connected = True
        snap_ctrl.transport = "usb"
        snap_ctrl.battery_pct = 80
        snap_ctrl.l2_raw = 0
        snap_ctrl.r2_raw = 0
        snap_ctrl.raw_lx = 128
        snap_ctrl.raw_ly = 128
        snap_ctrl.raw_rx = 128
        snap_ctrl.raw_ry = 128

        snap = MagicMock()
        snap.controller = snap_ctrl
        snap.active_profile = "default"
        snap.counters = {}

        server.store = MagicMock()
        server.store.snapshot.return_value = snap

        result = asyncio.run(server._handle_daemon_state_full({}))
        assert "rumble_policy" in result
        assert result["rumble_policy"] == "balanceado"
        assert "rumble_policy_custom_mult" in result
        assert "rumble_mult_applied" in result
