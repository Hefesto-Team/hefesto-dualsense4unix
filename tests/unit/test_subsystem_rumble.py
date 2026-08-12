"""Testes unitários do subsystem Rumble (isolamento).

Prova que:
  - _effective_mult_inline retorna multiplicadores corretos por política.
  - reassert_rumble chama controller.set_rumble com valores escalados.
  - reassert_rumble é noop quando rumble_active is None.
  - reassert_rumble aplica clamp [0, 255].
  - RumbleSubsystem.is_enabled é sempre True.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.core.rumble import _effective_mult
from hefesto_dualsense4unix.daemon.subsystems.rumble import (
    RUMBLE_POLICY_MULT,
    RumbleSubsystem,
    reassert_rumble,
)

# 11/08/2026: os degraus eram literais aqui (0.7 / 1.0). Quando a escada
# mudou para 30/100/150 por decisão dela, estes testes reprovaram sem que
# nada do produto estivesse errado — fixavam o VALOR em vez da REGRA.
# Derivando do dono único, provam o que devem: que a política escolhida é a
# que chega ao motor.

# AUDIT-FINDING-RUMBLE-POLICY-DEDUP-01: _effective_mult_inline deletado;
# alias local para preservar leitura dos asserts sem mudar semântica.
_effective_mult_inline = _effective_mult


def _cfg(policy: str, custom_mult: float = 0.7) -> MagicMock:
    cfg = MagicMock()
    cfg.rumble_policy = policy
    cfg.rumble_policy_custom_mult = custom_mult
    return cfg


class TestEffectiveMultInline:
    def test_economia(self) -> None:
        mult, _, _ = _effective_mult_inline(_cfg("economia"), 80, 1.0, 0.7, 0.0)
        assert mult == pytest.approx(0.3)

    def test_balanceado(self) -> None:
        mult, _, _ = _effective_mult_inline(_cfg("balanceado"), 80, 1.0, 0.7, 0.0)
        assert mult == pytest.approx(RUMBLE_POLICY_MULT["balanceado"])

    def test_max(self) -> None:
        mult, _, _ = _effective_mult_inline(_cfg("max"), 80, 1.0, 0.7, 0.0)
        assert mult == pytest.approx(RUMBLE_POLICY_MULT["max"])

    def test_custom(self) -> None:
        mult, _, _ = _effective_mult_inline(_cfg("custom", 0.5), 80, 1.0, 0.7, 0.0)
        assert mult == pytest.approx(0.5)

    def test_auto_bateria_alta(self) -> None:
        mult, _, _ = _effective_mult_inline(_cfg("auto"), 80, 1.0, 0.7, 0.0)
        assert mult == pytest.approx(1.0)

    def test_auto_bateria_baixa(self) -> None:
        mult, _, _ = _effective_mult_inline(_cfg("auto"), 10, 1.0, 0.7, 0.0)
        assert mult == pytest.approx(0.3)

    def test_fallback_desconhecido(self) -> None:
        mult, _, _ = _effective_mult_inline(_cfg("desconhecido"), 50, 1.0, 0.7, 0.0)
        # Política que não existe cai no BALANCEADO — a regra, não o número.
        assert mult == pytest.approx(RUMBLE_POLICY_MULT["balanceado"])


class TestReassertRumble:
    def _make_daemon(
        self,
        rumble_active: tuple[int, int] | None,
        policy: str = "max",
    ) -> MagicMock:
        daemon = MagicMock()
        daemon.config = MagicMock()
        daemon.config.rumble_active = rumble_active
        daemon.config.rumble_policy = policy
        daemon.config.rumble_policy_custom_mult = 0.7
        daemon._last_auto_mult = 0.7
        daemon._last_auto_change_at = 0.0

        snap = MagicMock()
        snap.controller = MagicMock()
        snap.controller.battery_pct = 80
        daemon.store.snapshot.return_value = snap
        return daemon

    def test_noop_se_rumble_active_none(self) -> None:
        daemon = self._make_daemon(rumble_active=None)
        reassert_rumble(daemon, 1.0)
        daemon.controller.set_rumble.assert_not_called()

    def test_chama_set_rumble_com_valores_escalados(self) -> None:
        """No "Máximo" o rumble FIXADO também é amplificado — e saturado.

        Enquanto o máximo valia 1,0 este teste passava com (100, 200)
        intactos, e não distinguia escalar de não escalar. Com 1,5 ele
        finalmente morde os dois lados: a conta e o recorte em 255."""
        daemon = self._make_daemon(rumble_active=(100, 200), policy="max")
        reassert_rumble(daemon, 1.0)
        mult = RUMBLE_POLICY_MULT["max"]
        daemon.controller.set_rumble.assert_called_once_with(
            weak=min(255, round(100 * mult)), strong=min(255, round(200 * mult))
        )

    def test_aplica_politica_economia(self) -> None:
        daemon = self._make_daemon(rumble_active=(100, 200), policy="economia")
        reassert_rumble(daemon, 1.0)
        # 100 * 0.3 = 30, 200 * 0.3 = 60
        daemon.controller.set_rumble.assert_called_once_with(weak=30, strong=60)

    def test_clamp_resultado(self) -> None:
        daemon = self._make_daemon(rumble_active=(255, 255), policy="max")
        reassert_rumble(daemon, 1.0)
        daemon.controller.set_rumble.assert_called_once_with(weak=255, strong=255)

    def test_excecao_nao_lanca(self) -> None:
        daemon = self._make_daemon(rumble_active=(100, 200), policy="max")
        daemon.controller.set_rumble.side_effect = RuntimeError("falha HID")
        reassert_rumble(daemon, 1.0)  # não deve lançar


class TestRumbleSubsystem:
    def test_is_enabled_sempre_true(self) -> None:
        subsystem = RumbleSubsystem()
        assert subsystem.is_enabled(MagicMock()) is True

    @pytest.mark.asyncio
    async def test_start_noop(self) -> None:
        subsystem = RumbleSubsystem()
        await subsystem.start(MagicMock())  # não lança

    @pytest.mark.asyncio
    async def test_stop_noop(self) -> None:
        subsystem = RumbleSubsystem()
        await subsystem.stop()  # não lança
