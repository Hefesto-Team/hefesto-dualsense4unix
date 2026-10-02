"""Testes unitários para FEAT-RUMBLE-POLICY-01 — política de intensidade de rumble.

Cobre:
- Cada preset retorna mult correto.
- Modo Auto respeita battery thresholds (mock battery_pct 80/40/10).
- Debounce 5s evita flapping em modo auto.
- rumble.set(100, 200) com policy "economia" aplica (30, 60), pelo funil VIVO
  (`daemon.ipc_rumble_policy.apply_rumble_policy`).
- _handle_rumble_policy_set e _handle_rumble_policy_custom do IPC.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.core.rumble import _effective_mult
from hefesto_dualsense4unix.daemon.ipc_rumble_policy import apply_rumble_policy
from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.daemon.subsystems.rumble import RUMBLE_POLICY_MULT


_effective_mult_inline = _effective_mult


def _config(policy: str, custom_mult: float = 0.7) -> DaemonConfig:
    cfg = DaemonConfig()
    cfg.rumble_policy = policy  # type: ignore[assignment]
    cfg.rumble_policy_custom_mult = custom_mult
    return cfg


class TestPresets:
    """Cada preset retorna o multiplicador esperado."""

    def test_economia(self) -> None:
        cfg = _config("economia")
        mult, _, _ = _effective_mult_inline(cfg, 100, 1.0, 0.7, 0.0)
        assert mult == pytest.approx(0.3)

    def test_balanceado(self) -> None:
        cfg = _config("balanceado")
        mult, _, _ = _effective_mult_inline(cfg, 100, 1.0, 0.7, 0.0)
        assert mult == pytest.approx(RUMBLE_POLICY_MULT["balanceado"])

    def test_max(self) -> None:
        cfg = _config("max")
        mult, _, _ = _effective_mult_inline(cfg, 100, 1.0, 0.7, 0.0)
        assert mult == pytest.approx(RUMBLE_POLICY_MULT["max"])

    def test_custom(self) -> None:
        cfg = _config("custom", custom_mult=0.45)
        mult, _, _ = _effective_mult_inline(cfg, 100, 1.0, 0.7, 0.0)
        assert mult == pytest.approx(0.45)

    def test_custom_via_rumble_py(self) -> None:
        """Garante que a _effective_mult em rumble.py retorna igual."""
        cfg = _config("custom", custom_mult=0.55)
        mult, _, _ = _effective_mult(cfg, 80, 1.0, 0.7, 0.0)
        assert mult == pytest.approx(0.55)


# do state_full). Políticas fixas o deixavam INTOCADO, preso no default 0.7:


class TestMultEfetivoObservavel:
    """Toda política sincroniza o estado observável com o mult efetivo."""

    def test_max_sincroniza_estado_observavel(self) -> None:
        """O cenário do journal: policy=max com estado herdado 0.7 tem que
        devolver o mult DO MÁXIMO — não deixar o 0.7 fantasma para o
        state_full."""
        cfg = _config("max")
        mult, new_last, _ = _effective_mult(cfg, 100, 1.0, 0.7, 0.0)
        assert mult == pytest.approx(RUMBLE_POLICY_MULT["max"])
        assert new_last == pytest.approx(RUMBLE_POLICY_MULT["max"])

    def test_economia_sincroniza_estado_observavel(self) -> None:
        cfg = _config("economia")
        mult, new_last, _ = _effective_mult(cfg, 100, 1.0, 0.7, 0.0)
        assert mult == pytest.approx(0.3)
        assert new_last == pytest.approx(0.3)

    def test_custom_sincroniza_estado_observavel(self) -> None:
        cfg = _config("custom", custom_mult=0.45)
        mult, new_last, _ = _effective_mult(cfg, 100, 1.0, 0.7, 0.0)
        assert mult == pytest.approx(0.45)
        assert new_last == pytest.approx(0.45)

    def test_politica_desconhecida_sincroniza_fallback(self) -> None:
        cfg = _config("turbo")
        mult, new_last, _ = _effective_mult(cfg, 100, 1.0, 0.3, 0.0)
        assert mult == pytest.approx(RUMBLE_POLICY_MULT["balanceado"])
        assert new_last == pytest.approx(RUMBLE_POLICY_MULT["balanceado"])

    def test_politica_fixa_preserva_relogio_do_debounce_auto(self) -> None:
        """Política fixa não mexe no timestamp do debounce do auto — só no"""
        cfg = _config("max")
        _, _, new_at = _effective_mult(cfg, 100, 500.0, 0.7, 123.0)
        assert new_at == pytest.approx(123.0)


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


class TestAutoDebounce:
    """Debounce de 5s evita flapping no modo auto."""

    def test_sem_debounce_muda(self) -> None:
        """Primeira mudança (last_change_at == 0.0) ocorre imediatamente."""
        cfg = _config("auto")
        mult, new_last, new_at = _effective_mult_inline(cfg, 10, 100.0, 0.7, 0.0)
        assert mult == pytest.approx(0.3)
        assert new_last == pytest.approx(0.3)
        assert new_at == pytest.approx(100.0)

    def test_dentro_debounce_nao_muda(self) -> None:
        """Mudança dentro de 5s mantém mult anterior."""
        cfg = _config("auto")
        mult, new_last, new_at = _effective_mult_inline(
            cfg, 10, 102.0, 0.7, 100.0
        )
        assert mult == pytest.approx(0.7)
        assert new_last == pytest.approx(0.7)
        assert new_at == pytest.approx(100.0)

    def test_apos_debounce_muda(self) -> None:
        """Mudança após 5s+ é aplicada."""
        cfg = _config("auto")
        mult, new_last, new_at = _effective_mult_inline(
            cfg, 10, 106.0, 0.7, 100.0
        )
        assert mult == pytest.approx(0.3)
        assert new_last == pytest.approx(0.3)
        assert new_at == pytest.approx(106.0)

    def test_sem_mudanca_mantem(self) -> None:
        """Se target == last_auto_mult, retorna estável sem debounce."""
        cfg = _config("auto")
        mult, new_last, new_at = _effective_mult_inline(
            cfg, 80, 200.0, 1.0, 100.0
        )
        assert mult == pytest.approx(1.0)
        assert new_last == pytest.approx(1.0)
        assert new_at == pytest.approx(100.0)


class TestRumbleSetComPolitica:
    """rumble.set(100, 200) com policy 'economia' aplica (30, 60)."""

    @staticmethod
    def _daemon(cfg: DaemonConfig | None, bateria: int | None = None) -> SimpleNamespace:
        store = StateStore()
        if bateria is not None:
            store.update_controller_state(
                ControllerState(
                    battery_pct=bateria, l2_raw=0, r2_raw=0, connected=True,
                    transport="usb",
                )
            )
        return SimpleNamespace(config=cfg, store=store)

    def test_economia_aplica_mult_30(self) -> None:
        daemon = self._daemon(_config("economia"))
        assert apply_rumble_policy(daemon, 100, 200) == (30, 60)

    def test_balanceado_entrega_o_que_o_jogo_pediu(self) -> None:
        """Era `test_balanceado_aplica_mult_70`, com o 0.7 no NOME."""
        daemon = self._daemon(_config("balanceado"))
        esperado = round(100 * RUMBLE_POLICY_MULT["balanceado"])
        assert apply_rumble_policy(daemon, 100, 100) == (esperado, esperado)

    def test_max_amplifica(self) -> None:
        """Era `test_max_sem_alteracao`, e o nome contava a história certa"""
        daemon = self._daemon(_config("max"))
        mult = RUMBLE_POLICY_MULT["max"]
        assert apply_rumble_policy(daemon, 100, 200) == (
            min(255, round(100 * mult)), min(255, round(200 * mult))
        )
        assert mult > 1.0, 'um botão chamado "Máximo" tem de aumentar'

    def test_clamp_resultado(self) -> None:
        """Resultado é recortado em [0, 255]."""
        daemon = self._daemon(_config("max"))
        assert apply_rumble_policy(daemon, 255, 255) == (255, 255)

    def test_sem_config_entrega_o_pedido_intocado(self) -> None:
        """Daemon sem config: o funil devolve o que o jogo pediu."""
        assert apply_rumble_policy(self._daemon(None), 100, 200) == (100, 200)

    def test_auto_com_bateria_baixa(self) -> None:
        """Modo auto + battery 10% -> mult 0.3, e a memória do debounce anda."""
        daemon = self._daemon(_config("auto"), bateria=10)
        daemon._last_auto_change_at = 0.0
        daemon._last_auto_mult = 0.7

        assert apply_rumble_policy(daemon, 100, 200) == (30, 60)
        assert daemon._last_auto_mult == pytest.approx(0.3)


class TestIpcHandlers:
    """_handle_rumble_policy_set e _handle_rumble_policy_custom."""

    def _make_server(self) -> object:
        """Cria IpcServer com config de daemon mockado."""
        from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
        from hefesto_dualsense4unix.daemon.state_store import StateStore

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
        """HARM-19: o teto é o do esquema (2.0), não 1.0."""
        server, _cfg = self._make_server()
        with pytest.raises(ValueError, match="fora de"):
            asyncio.run(server._handle_rumble_policy_custom({"mult": 2.5}))

    def test_policy_custom_no_teto_e_aceito(self) -> None:
        """O TOPO do slider é aceito pelo daemon — a invariante é essa.

        SATURA-01 (11/08/2026): o teste chamava-se "amplificado" e travava o
        1.5 como número literal, porque o slider ia a 200%. O teto voltou a
        100% (medido: acima disso metade da faixa do jogo satura em 255 e a
        vibração perde a variação), e o valor passou a sair do dono único —
        `RUMBLE_CUSTOM_MULT_MAX` no esquema. Assim o teste continua provando o
        que importa, "o que a UI oferece, o daemon aceita", e não precisa ser
        reescrito na próxima vez que o teto mudar.
        """
        from hefesto_dualsense4unix.profiles.schema import RUMBLE_CUSTOM_MULT_MAX

        server, cfg = self._make_server()

        result = asyncio.run(
            server._handle_rumble_policy_custom({"mult": RUMBLE_CUSTOM_MULT_MAX})
        )

        assert result["mult"] == RUMBLE_CUSTOM_MULT_MAX
        assert cfg.rumble_policy_custom_mult == RUMBLE_CUSTOM_MULT_MAX

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

        server.daemon._last_auto_mult = 0.3

        result = asyncio.run(server._handle_daemon_state_full({}))
        assert "rumble_policy" in result
        assert result["rumble_policy"] == "balanceado"
        assert "rumble_policy_custom_mult" in result
        assert "rumble_mult_applied" in result
        assert result["rumble_mult_applied"] == pytest.approx(0.3)
