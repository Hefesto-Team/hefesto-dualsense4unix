"""R-14 (auditoria 23/07) — "Todos" na aba Lightbar deixa de matar o automático.

Defeito medido: um clique em cor (ou num preset de player-LED) com o alvo em
"Todos" desligava ``auto_player_colors`` no draft E persistia isso no perfil.
Como aquele flag único governava também a NUMERAÇÃO dos DualSense e a dos
EXTERNOS (o tick de ``external_identity`` era gateado por ele), o efeito
colateral era a queixa "dois player 1, dois player 2" — e o congelamento
seguia salvo no ``fps.json``.

Cura: com os controles CONECTADOS conhecidos (o mapa que a aba Status mantém
do ``state_full``), "Todos" vira "cada um, por MAC" — override por-uniq no
draft e um pedido IPC por controle. O override vence a camada automática no
merge por campo do backend (D5), então a cor única aparece sem desligar nada.
Sem saber quem está conectado, o caminho degradado de sempre (D4) continua,
avisado no toast.

GUI: precisa de ``gi`` (padrão de ``test_mouse_actions_gui_sync.py``).
"""
# ruff: noqa: E402  (imports após o pin de versão do gi — padrão da casa)
from __future__ import annotations

from typing import Any

import pytest

gi = pytest.importorskip("gi")

# BUG-TEST-GDK-VERSION-PIN-01: pina Gdk/Gtk 3.0 ANTES de importar módulos da
# GUI — sem isso o gi pode carregar Gdk 4.0 e envenenar o processo inteiro.
gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")

from hefesto_dualsense4unix.app import draft_config as draft_mod
from hefesto_dualsense4unix.app.actions import lightbar_actions
from hefesto_dualsense4unix.app.actions.lightbar_actions import (
    _AVISO_D4,
    LightbarActionsMixin,
)
from hefesto_dualsense4unix.profiles.schema import (
    LedsConfig,
    MatchAny,
    Profile,
)

#: MACs forjados (faixa aa:bb:cc — teste-guarda de anonimato).
UNIQ_1 = "aabbcc000001"
UNIQ_2 = "aabbcc000002"

ROXO = (129, 61, 156)


class _FakeCheck:
    def __init__(self) -> None:
        self.active = True

    def connect(self, *_a: Any, **_kw: Any) -> None:
        return None

    def get_active(self) -> bool:
        return self.active

    def set_active(self, value: bool) -> None:
        self.active = bool(value)


class _FakeColorButton:
    def __init__(self, rgb: tuple[int, int, int]) -> None:
        self._rgb = rgb

    def get_rgba(self) -> Any:
        class _RGBA:
            red = self._rgb[0] / 255
            green = self._rgb[1] / 255
            blue = self._rgb[2] / 255

        return _RGBA()

    def set_rgba(self, _rgba: Any) -> None:
        return None


class _Host(LightbarActionsMixin):
    """Host mínimo com o mapa de conectados da aba Status (R-16/R-14)."""

    def __init__(
        self,
        draft: draft_mod.DraftConfig,
        conectados: dict[int, str | None] | None,
        uniq: str | None = None,
    ) -> None:
        self.draft = draft
        self._edit_target_uniq = uniq
        if conectados is not None:
            self._target_uniq_by_index = conectados
        self._widgets: dict[str, Any] = {"auto_player_colors_check": _FakeCheck()}
        self._toasts: list[str] = []
        self._refresh_guard = False

    def _get(self, widget_id: str) -> Any:
        return self._widgets.get(widget_id)

    def _toast_light(self, msg: str) -> None:
        self._toasts.append(msg)


def _draft(auto: bool = True) -> draft_mod.DraftConfig:
    perfil = Profile(
        name="vitoria",
        match=MatchAny(),
        priority=5,
        leds=LedsConfig(
            lightbar=ROXO,
            player_leds=[True, False, False, False, False],
            lightbar_brightness=1.0,
            auto_player_colors=auto,
        ),
    )
    return draft_mod.DraftConfig.from_profile(perfil)


def _host(auto: bool = True, com_conectados: bool = True) -> _Host:
    conectados = {1: UNIQ_1, 2: UNIQ_2} if com_conectados else None
    return _Host(_draft(auto), conectados)


# ---------------------------------------------------------------------------
# Draft: "Todos" vira override por-MAC, sem derrubar o automático
# ---------------------------------------------------------------------------


def test_cor_em_todos_nao_desliga_o_auto_e_grava_por_mac() -> None:
    """Falha-sem: o D4 desligava ``auto_player_colors`` no draft (e o "Salvar
    Perfil" levava isso ao JSON), congelando numeração e externos junto."""
    host = _host()
    host.on_lightbar_color_set(_FakeColorButton((0, 0, 255)))

    assert host.draft.leds.auto_player_colors is True, "a paleta continua viva"
    for uniq in (UNIQ_1, UNIQ_2):
        assert host.draft.effective_leds_for(uniq).lightbar_rgb == (0, 0, 255)
    assert not any(_AVISO_D4 in t for t in host._toasts)
    # O global também registra a cor única (é o que a aba exibe em "Todos").
    assert host.draft.leds.lightbar_rgb == (0, 0, 255)


def test_override_por_mac_sobrevive_ao_round_trip_do_perfil() -> None:
    """O que a GUI grava tem de chegar ao JSON: sem o override por-MAC a
    ativação seguinte devolveria a paleta automática por cima da cor única."""
    host = _host()
    host.on_lightbar_color_set(_FakeColorButton((0, 0, 255)))
    perfil = host.draft.to_profile("vitoria")
    assert perfil.leds.auto_player_colors is True
    assert perfil.controllers is not None
    for uniq in (UNIQ_1, UNIQ_2):
        assert tuple(perfil.controllers[uniq].leds.lightbar) == (0, 0, 255)


def test_player_leds_em_todos_nao_desliga_o_auto(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """U9 sem o martelo: o padrão manual vence por override por-MAC, não
    desligando a identidade automática de todo mundo."""
    enviados: list[tuple[Any, str | None]] = []
    monkeypatch.setattr(
        lightbar_actions,
        "player_leds_set",
        lambda bits, uniq=None: enviados.append((bits, uniq)) or True,
    )
    host = _host()
    host.on_player_leds_preset_p3(None)

    assert host.draft.leds.auto_player_colors is True
    assert [uniq for _bits, uniq in enviados] == [UNIQ_1, UNIQ_2]
    p3 = (True, False, True, False, True)
    for uniq in (UNIQ_1, UNIQ_2):
        assert tuple(host.draft.effective_leds_for(uniq).player_leds) == p3


def test_brilho_em_todos_continua_global() -> None:
    """Brilho ESCALA a paleta (D11) — não disputa com o automático, então
    continua sendo campo global (nada de override por-MAC)."""

    class _FakeScale:
        @staticmethod
        def get_value() -> float:
            return 40.0

    host = _host()
    host.on_lightbar_brightness_changed(_FakeScale())
    assert host.draft.leds.auto_player_colors is True
    assert host.draft.leds.lightbar_brightness == 40
    assert host.draft.source_controllers in (None, {})


def test_sem_saber_os_conectados_o_d4_antigo_permanece() -> None:
    """Caminho degradado explícito: sem alvo não há override possível, e a
    cor única só aparece desligando a paleta (com aviso)."""
    host = _host(com_conectados=False)
    host.on_lightbar_color_set(_FakeColorButton((0, 0, 255)))
    assert host.draft.leds.auto_player_colors is False
    assert any(_AVISO_D4 in t for t in host._toasts)


# ---------------------------------------------------------------------------
# IPC: "Todos" manda um pedido POR MAC (R-14 + disciplina do R-17)
# ---------------------------------------------------------------------------


def test_aplicar_em_todos_manda_led_set_por_mac(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Falha-sem: o "Aplicar" em "Todos" ia por ``apply_draft`` com o toggle
    desligado — a única forma de a cor vencer a paleta era matá-la."""
    chamadas: list[tuple[Any, Any, str | None]] = []
    monkeypatch.setattr(
        lightbar_actions,
        "led_set",
        lambda rgb, brightness=None, uniq=None: chamadas.append(
            (rgb, brightness, uniq)
        )
        or True,
    )
    monkeypatch.setattr(
        lightbar_actions.ipc_bridge,
        "apply_draft",
        lambda *_a, **_kw: pytest.fail("com conectados conhecidos é led.set por MAC"),
    )
    host = _host()
    host._current_rgb = (10, 20, 30)
    host._current_brightness = 0.5
    host.on_lightbar_apply(None)

    assert chamadas == [
        ((10, 20, 30), 0.5, UNIQ_1),
        ((10, 20, 30), 0.5, UNIQ_2),
    ]
    assert host.draft.leds.auto_player_colors is True
    assert not any(_AVISO_D4 in t for t in host._toasts)


def test_falha_em_um_controle_nao_vira_sucesso(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Um controle que não aceitou é falha visível (sem curto-circuito: os
    outros ainda recebem o pedido)."""
    vistos: list[str | None] = []

    def _led_set(rgb: Any, brightness: Any = None, uniq: str | None = None) -> bool:
        vistos.append(uniq)
        return uniq != UNIQ_1

    monkeypatch.setattr(lightbar_actions, "led_set", _led_set)
    host = _host()
    host.on_lightbar_apply(None)
    assert vistos == [UNIQ_1, UNIQ_2]
    assert any("não consegui aplicar" in t for t in host._toasts)


def _gdk_rgba_ok() -> bool:
    """A CI headless de release tem um Gdk parcial sem RGBA (o botão
    "Apagar" constrói um) — mesmo skip de ``test_lightbar_auto_colors``."""
    try:
        from gi.repository import Gdk

        return hasattr(Gdk, "RGBA")
    except Exception:
        return False


@pytest.mark.skipif(not _gdk_rgba_ok(), reason="Gdk.RGBA ausente (CI headless)")
def test_apagar_em_todos_manda_preto_por_mac(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chamadas: list[tuple[Any, Any, str | None]] = []
    monkeypatch.setattr(
        lightbar_actions,
        "led_set",
        lambda rgb, brightness=None, uniq=None: chamadas.append(
            (rgb, brightness, uniq)
        )
        or True,
    )
    monkeypatch.setattr(
        lightbar_actions.ipc_bridge,
        "apply_draft",
        lambda *_a, **_kw: pytest.fail("com conectados conhecidos é led.set por MAC"),
    )
    host = _host()
    host.on_lightbar_off(None)

    assert chamadas == [((0, 0, 0), None, UNIQ_1), ((0, 0, 0), None, UNIQ_2)]
    assert host.draft.leds.auto_player_colors is True
