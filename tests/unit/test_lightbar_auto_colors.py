"""COR-04 — GUI da aba Lightbar: toggle "Cores automáticas por controle"."""

from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("lightbar auto colors")

from typing import Any
from unittest.mock import MagicMock

import gi
import pytest

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")

from hefesto_dualsense4unix.app.actions.lightbar_actions import LightbarActionsMixin
from hefesto_dualsense4unix.app.draft_config import DraftConfig
from hefesto_dualsense4unix.daemon.ipc_draft_applier import DraftApplier
from hefesto_dualsense4unix.daemon.subsystems import identity
from hefesto_dualsense4unix.profiles.schema import (

    ControllerOverrides,
    LedsConfig,
    MatchAny,
    Profile,
)

UNIQ_1 = "aabbcc000001"
UNIQ_2 = "aabbcc000002"


class _FakeCheck:
    """Stub de GtkCheckButton: emite "toggled" só quando o estado MUDA."""

    def __init__(self) -> None:
        self.active = False
        self._handlers: list[Any] = []

    def connect(self, _signal: str, handler: Any) -> None:
        self._handlers.append(handler)

    def set_active(self, value: bool) -> None:
        value = bool(value)
        if self.active == value:
            return
        self.active = value
        for handler in list(self._handlers):
            handler(self)

    def get_active(self) -> bool:
        return self.active


class _FakeRGBA:
    def __init__(self, r: float, g: float, b: float) -> None:
        self.red = r
        self.green = g
        self.blue = b
        self.alpha = 1.0


class _FakeColorButton:
    def __init__(self, rgb: tuple[int, int, int]) -> None:
        self._rgba = _FakeRGBA(rgb[0] / 255, rgb[1] / 255, rgb[2] / 255)

    def get_rgba(self) -> _FakeRGBA:
        return self._rgba


class _Host(LightbarActionsMixin):
    """Hospedeiro mínimo: draft + alvo + widgets fakes + toast espião."""

    def __init__(
        self,
        draft: DraftConfig,
        uniq: str | None = None,
        widgets: dict[str, Any] | None = None,
    ) -> None:
        self.draft = draft
        self._edit_target_uniq = uniq
        self._widgets = widgets or {}
        self._toasts: list[str] = []
        self._refresh_guard = False

    def _get(self, widget_id: str) -> Any:
        return self._widgets.get(widget_id)

    def _toast_light(self, msg: str) -> None:
        self._toasts.append(msg)


def _aceitou(uniq: str | None) -> dict[str, Any]:
    """Corpo de um ``led.set``/``led.player_set`` que ESCREVEU em ``uniq``."""
    return {
        "status": "ok",
        "aplicado_em": [uniq] if uniq else [],
        "guardado_em": [],
    }


def _perfil(
    auto: bool | None = None,
    controllers: dict[str, Any] | None = None,
) -> Profile:
    """Perfil roxo da casa; ``auto=None`` = perfil ANTIGO (campo ausente)."""
    leds_kwargs: dict[str, Any] = {
        "lightbar": (129, 61, 156),
        "player_leds": [True, False, False, False, False],
        "lightbar_brightness": 1.0,
    }
    if auto is not None:
        leds_kwargs["auto_player_colors"] = auto
    return Profile(
        name="vitoria",
        match=MatchAny(),
        priority=5,
        leds=LedsConfig(**leds_kwargs),
        controllers=controllers,
    )


def _override_verde_completo() -> ControllerOverrides:
    """Override com cor + player-LEDs + gatilho próprios (parcial-explícito)."""
    return ControllerOverrides.model_validate(
        {
            "leds": {
                "lightbar": [0, 255, 0],
                "lightbar_brightness": 0.5,
                "player_leds": [False, True, False, True, False],
            },
            "triggers": {"right": {"mode": "Rigid", "params": [5, 200]}},
        }
    )


def test_round_trip_preserva_auto_false_e_mapa_controllers() -> None:
    """from_profile(auto=False + override) → to_profile: nada se perde."""
    perfil = _perfil(auto=False, controllers={UNIQ_2: _override_verde_completo()})
    draft = DraftConfig.from_profile(perfil)

    salvo = draft.to_profile("vitoria")
    assert salvo.leds.auto_player_colors is False
    assert salvo.controllers is not None
    override = salvo.controllers[UNIQ_2]
    assert tuple(override.leds.lightbar) == (0, 255, 0)
    assert override.triggers.right.mode == "Rigid"
    assert "auto_player_colors" not in override.leds.model_fields_set


def _gdk_rgba_ok() -> bool:
    """Gdk.RGBA existe? A CI headless de release tem um Gdk parcial sem RGBA;"""
    try:
        import gi

        gi.require_version("Gdk", "3.0")
        from gi.repository import Gdk

        return hasattr(Gdk, "RGBA")
    except Exception:
        return False


class TestApplierAutoColors:
    @pytest.fixture(autouse=True)
    def _singleton_limpo(self) -> Any:
        identity.reset_identity_registry()
        yield
        identity.reset_identity_registry()

    @staticmethod
    def _applier() -> tuple[DraftApplier, MagicMock]:
        controller = MagicMock()
        return (
            DraftApplier(controller=controller, store=MagicMock(), daemon=None),
            controller,
        )

    def test_secao_leds_configura_o_registro(self) -> None:
        applier, controller = self._applier()
        applied = applier.apply(
            {
                "leds": {
                    "lightbar_rgb": [10, 20, 30],
                    "lightbar_brightness": 0.4,
                    "player_leds": [True, False, False, False, False],
                    "auto_player_colors": False,
                }
            }
        )
        assert applied == ["leds"]
        registry = identity.get_identity_registry()
        assert registry.auto_enabled is False
        assert registry.auto_brightness == pytest.approx(0.4)
        controller.apply_output_defaults.assert_called_once()

    def test_toggle_sozinho_configura_sem_broadcast(self) -> None:
        """Payload parcial (só o toggle) — o caminho do botão da aba."""
        applier, controller = self._applier()
        registry = identity.get_identity_registry()
        registry.configure(enabled=False)
        applied = applier.apply({"leds": {"auto_player_colors": True}})
        assert applied == ["leds"]
        assert registry.auto_enabled is True
        controller.apply_output_defaults.assert_not_called()

    def test_payload_sem_a_chave_nao_mexe_no_registro(self) -> None:
        """GUI antiga (sem o campo) = sem opinião: o vigente fica."""
        applier, _controller = self._applier()
        registry = identity.get_identity_registry()
        registry.configure(enabled=False, brightness=0.2)
        applier.apply({"leds": {"lightbar_rgb": [1, 2, 3]}})
        assert registry.auto_enabled is False
        assert registry.auto_brightness == pytest.approx(0.2)

    def test_toggle_invalido_recusa_a_secao(self) -> None:
        applier, controller = self._applier()
        applied = applier.apply({"leds": {"auto_player_colors": "sim"}})
        assert applied == []
        assert identity.get_identity_registry().auto_enabled is True
        controller.apply_output_defaults.assert_not_called()


