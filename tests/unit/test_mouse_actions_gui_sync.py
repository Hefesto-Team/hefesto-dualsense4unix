"""Testes da aba Mouse sincronizada com o daemon (BUG-MOUSE-GUI-SYNC-01).

Cobre os quatro achados do diagnóstico 2026-07-03:
  - A1: bootstrap e refresh da aba sobrepõem o bloco vivo ``mouse_emulation``.
  - A2: seção mouse intocada NÃO é enviada no Aplicar (ver test_draft_config).
  - A3: revert do toggle com daemon offline não reentra no handler (guard).
  - A4: sliders enviam payload speed-only (sem ``enabled``) — religar por
    slider é impossível; com toggle OFF nem IPC sai.

Não exercita GTK real: widgets são stubs com a API mínima; o ``call_async``
do ipc_bridge é monkeypatchado para invocar os callbacks sincronamente
(o real re-posta via GLib.idle_add — mesma semântica para a lógica testada).
"""
from __future__ import annotations

from typing import Any

import pytest

pytest.importorskip("gi")

from hefesto_dualsense4unix.app import ipc_bridge
from hefesto_dualsense4unix.app.actions.footer_actions import FROZEN_WIDGET_IDS
from hefesto_dualsense4unix.app.actions.mouse_actions import MouseActionsMixin
from hefesto_dualsense4unix.app.draft_config import DraftConfig

# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------


class _FakeSwitch:
    """Stub de Gtk.Switch que REEMITE state-set em todo set_active.

    Reproduz o comportamento GTK3 do repro real do A3: ``set_active`` chama o
    handler ``state-set`` SINCRONAMENTE — sem o guard, o revert do caminho de
    falha reentra no handler (999 reentradas + RecursionError).
    """

    def __init__(self, owner: Any) -> None:
        self._owner = owner
        self._active = False
        self.set_active_calls = 0

    def get_active(self) -> bool:
        return self._active

    def set_active(self, value: bool) -> None:
        self.set_active_calls += 1
        self._active = bool(value)
        self._owner.on_mouse_toggle_set(self, bool(value))


class _FakeScale:
    def __init__(self, value: float = 6.0) -> None:
        self._value = value

    def get_value(self) -> float:
        return self._value

    def set_value(self, value: float) -> None:
        self._value = float(value)


class _Harness(MouseActionsMixin):
    """MouseActionsMixin com builder substituído por dict de widgets."""

    def __init__(self) -> None:
        self.draft = DraftConfig.default()
        self.widgets: dict[str, Any] = {}
        self.toasts: list[str] = []

    def _get(self, widget_id: str) -> Any:
        return self.widgets.get(widget_id)

    def _toast_mouse(self, msg: str) -> None:
        self.toasts.append(msg)


def _make_harness(with_switch: bool = True) -> tuple[_Harness, _FakeSwitch | None]:
    harness = _Harness()
    switch: _FakeSwitch | None = None
    if with_switch:
        switch = _FakeSwitch(harness)
        harness.widgets["mouse_emulation_toggle"] = switch
    return harness, switch


# ---------------------------------------------------------------------------
# A3 — toggle com daemon offline: 1 IPC + 1 revert, sem reentrada
# ---------------------------------------------------------------------------


def test_toggle_offline_um_ipc_um_revert_sem_reentrada(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness, switch = _make_harness()
    assert switch is not None
    calls: list[tuple[str, dict[str, Any]]] = []

    def fake_call_async(
        method: str,
        params: dict[str, Any] | None,
        on_success: Any,
        on_failure: Any = None,
        timeout_s: float = 0.25,
    ) -> None:
        calls.append((method, dict(params or {})))
        on_failure(ConnectionError("daemon offline"))

    monkeypatch.setattr(ipc_bridge, "call_async", fake_call_async)

    # Usuária liga o switch: GTK seta active e emite state-set.
    switch.set_active(True)

    assert len(calls) == 1, "exatamente 1 tentativa de IPC"
    # 2 set_active no total: 1 do gesto da usuária + 1 do revert (sem cascata).
    assert switch.set_active_calls == 2
    assert switch.get_active() is False, "switch revertido ao estado anterior"
    assert any("Falha" in t for t in harness.toasts)
    # Draft intocado (nada aplicado) e seção mouse continua limpa.
    assert harness.draft.mouse.enabled is False
    assert harness.draft.mouse.dirty is False


def test_toggle_status_failed_tambem_reverte(monkeypatch: pytest.MonkeyPatch) -> None:
    """Resposta {status: failed} (ex.: uinput indisponível) reverte o switch."""
    harness, switch = _make_harness()
    assert switch is not None

    def fake_call_async(
        method: str,
        params: dict[str, Any] | None,
        on_success: Any,
        on_failure: Any = None,
        timeout_s: float = 0.25,
    ) -> None:
        on_success({"status": "failed", "enabled": False})

    monkeypatch.setattr(ipc_bridge, "call_async", fake_call_async)

    switch.set_active(True)

    assert switch.get_active() is False
    assert harness.draft.mouse.dirty is False


def test_toggle_sucesso_atualiza_draft_e_marca_dirty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness, switch = _make_harness()
    assert switch is not None
    harness.widgets["mouse_speed_scale"] = _FakeScale(9.0)
    harness.widgets["mouse_scroll_speed_scale"] = _FakeScale(2.0)
    calls: list[tuple[str, dict[str, Any]]] = []

    def fake_call_async(
        method: str,
        params: dict[str, Any] | None,
        on_success: Any,
        on_failure: Any = None,
        timeout_s: float = 0.25,
    ) -> None:
        calls.append((method, dict(params or {})))
        on_success({"status": "ok", "enabled": True})

    monkeypatch.setattr(ipc_bridge, "call_async", fake_call_async)

    switch.set_active(True)

    assert calls == [
        ("mouse.emulation.set", {"enabled": True, "speed": 9, "scroll_speed": 2})
    ]
    assert harness.draft.mouse.enabled is True
    assert harness.draft.mouse.speed == 9
    assert harness.draft.mouse.scroll_speed == 2
    assert harness.draft.mouse.dirty is True
    assert switch.get_active() is True


# ---------------------------------------------------------------------------
# A4 — sliders enviam speed-only (sem 'enabled')
# ---------------------------------------------------------------------------


def test_slider_envia_payload_sem_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Toggle stale-ON: o payload NUNCA inclui 'enabled' — religar é impossível."""
    harness, switch = _make_harness()
    assert switch is not None
    switch._active = True  # stale-ON (daemon pode ter desligado via CLI)
    scale = _FakeScale(9.0)
    harness.widgets["mouse_speed_scale"] = scale
    calls: list[tuple[str, dict[str, Any]]] = []

    def fake_call_async(
        method: str,
        params: dict[str, Any] | None,
        on_success: Any,
        on_failure: Any = None,
        timeout_s: float = 0.25,
    ) -> None:
        calls.append((method, dict(params or {})))
        on_success({"status": "ok", "enabled": False})

    monkeypatch.setattr(ipc_bridge, "call_async", fake_call_async)

    harness.on_mouse_speed_changed(scale)

    assert calls == [("mouse.emulation.set", {"speed": 9})]
    assert "enabled" not in calls[0][1]
    assert harness.draft.mouse.dirty is True


def test_slider_scroll_envia_payload_sem_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness, switch = _make_harness()
    assert switch is not None
    switch._active = True
    scale = _FakeScale(3.0)
    harness.widgets["mouse_scroll_speed_scale"] = scale
    calls: list[tuple[str, dict[str, Any]]] = []

    def fake_call_async(
        method: str,
        params: dict[str, Any] | None,
        on_success: Any,
        on_failure: Any = None,
        timeout_s: float = 0.25,
    ) -> None:
        calls.append((method, dict(params or {})))
        on_success({"status": "ok", "enabled": False})

    monkeypatch.setattr(ipc_bridge, "call_async", fake_call_async)

    harness.on_mouse_scroll_speed_changed(scale)

    assert calls == [("mouse.emulation.set", {"scroll_speed": 3})]


def test_slider_com_toggle_off_nao_faz_ipc(monkeypatch: pytest.MonkeyPatch) -> None:
    """Toggle OFF: slider só atualiza o draft (preferência), sem IPC."""
    harness, switch = _make_harness()
    assert switch is not None
    scale = _FakeScale(9.0)
    harness.widgets["mouse_speed_scale"] = scale
    calls: list[Any] = []
    monkeypatch.setattr(
        ipc_bridge, "call_async", lambda *a, **kw: calls.append(a)
    )

    harness.on_mouse_speed_changed(scale)

    assert calls == []
    assert harness.draft.mouse.speed == 9
    assert harness.draft.mouse.dirty is True


def test_slider_coalescing_um_rpc_em_voo_aplica_ultimo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Durante um RPC em voo, só o ÚLTIMO valor pendente é reenviado ao final."""
    harness, switch = _make_harness()
    assert switch is not None
    switch._active = True
    scale = _FakeScale(7.0)
    harness.widgets["mouse_speed_scale"] = scale
    held: list[tuple[dict[str, Any], Any]] = []

    def fake_call_async(
        method: str,
        params: dict[str, Any] | None,
        on_success: Any,
        on_failure: Any = None,
        timeout_s: float = 0.25,
    ) -> None:
        held.append((dict(params or {}), on_success))

    monkeypatch.setattr(ipc_bridge, "call_async", fake_call_async)

    harness.on_mouse_speed_changed(scale)
    scale.set_value(8.0)
    harness.on_mouse_speed_changed(scale)
    scale.set_value(9.0)
    harness.on_mouse_speed_changed(scale)

    assert len(held) == 1, "um RPC em voo por vez"
    assert held[0][0] == {"speed": 7}

    held[0][1]({"status": "ok"})  # completa o primeiro

    assert len(held) == 2, "pendente reenviado ao terminar"
    assert held[1][0] == {"speed": 9}, "só o último valor sobrevive"

    held[1][1]({"status": "ok"})
    assert len(held) == 2, "sem eco infinito"


# ---------------------------------------------------------------------------
# A1 — refresh assíncrono da aba com o bloco vivo do daemon
# ---------------------------------------------------------------------------


def test_refresh_da_aba_sincroniza_com_estado_vivo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness, switch = _make_harness()
    assert switch is not None
    speed_scale = _FakeScale(6.0)
    scroll_scale = _FakeScale(1.0)
    harness.widgets["mouse_speed_scale"] = speed_scale
    harness.widgets["mouse_scroll_speed_scale"] = scroll_scale

    def fake_call_async(
        method: str,
        params: dict[str, Any] | None,
        on_success: Any,
        on_failure: Any = None,
        timeout_s: float = 0.25,
    ) -> None:
        assert method == "daemon.state_full"
        on_success(
            {
                "active_profile": "vitoria",
                "mouse_emulation": {"enabled": True, "speed": 9, "scroll_speed": 2},
            }
        )

    monkeypatch.setattr(ipc_bridge, "call_async", fake_call_async)

    harness._refresh_mouse_from_daemon_async()

    assert harness.draft.mouse.enabled is True
    assert harness.draft.mouse.speed == 9
    assert harness.draft.mouse.scroll_speed == 2
    assert harness.draft.mouse.dirty is False, "sync programático não marca dirty"
    assert switch.get_active() is True
    assert speed_scale.get_value() == 9.0
    assert scroll_scale.get_value() == 2.0


def test_refresh_da_aba_daemon_offline_mantem_draft(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness, _switch = _make_harness()
    antes = harness.draft

    def fake_call_async(
        method: str,
        params: dict[str, Any] | None,
        on_success: Any,
        on_failure: Any = None,
        timeout_s: float = 0.25,
    ) -> None:
        on_failure(ConnectionError("daemon offline"))

    monkeypatch.setattr(ipc_bridge, "call_async", fake_call_async)

    harness._refresh_mouse_from_daemon_async()

    assert harness.draft is antes


def test_refresh_mouse_tab_combina_draft_e_estado_vivo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_refresh_mouse_tab (switch-page da página 7) roda draft + async."""
    harness, switch = _make_harness()
    assert switch is not None

    def fake_call_async(
        method: str,
        params: dict[str, Any] | None,
        on_success: Any,
        on_failure: Any = None,
        timeout_s: float = 0.25,
    ) -> None:
        on_success({"mouse_emulation": {"enabled": True, "speed": 4, "scroll_speed": 1}})

    monkeypatch.setattr(ipc_bridge, "call_async", fake_call_async)

    harness._refresh_mouse_tab()

    assert harness.draft.mouse.enabled is True
    assert harness.draft.mouse.speed == 4


# ---------------------------------------------------------------------------
# A1 — overlay do bloco vivo no bootstrap do draft
# ---------------------------------------------------------------------------


def _load_app_module() -> Any:
    """Importa app.app lazy — o módulo puxa gi.repository.GdkPixbuf, ausente
    nos stubs de gi instalados por outros testes da suíte (padrão do repo,
    ver test_quit_app_stops_daemon.py). Quando indisponível, pula o teste."""
    try:
        import hefesto_dualsense4unix.app.app as app_mod
    except ImportError as exc:
        pytest.skip(f"gi/GdkPixbuf indisponível: {exc}")
    return app_mod


def _perfil_minimo(name: str = "vitoria") -> Any:
    from hefesto_dualsense4unix.profiles.schema import (
        LedsConfig,
        MatchAny,
        Profile,
        RumbleConfig,
        TriggerConfig,
        TriggersConfig,
    )

    return Profile(
        name=name,
        match=MatchAny(),
        triggers=TriggersConfig(
            left=TriggerConfig(mode="Off", params=[]),
            right=TriggerConfig(mode="Off", params=[]),
        ),
        leds=LedsConfig(
            lightbar=(255, 128, 0),
            lightbar_brightness=1.0,
            player_leds=[True, False, False, False, False],
        ),
        rumble=RumbleConfig(),
    )


def test_bootstrap_sobrepoe_bloco_mouse_vivo(monkeypatch: pytest.MonkeyPatch) -> None:
    """GUI aberta com daemon em modo mouse: draft nasce com o estado VIVO."""
    app_mod = _load_app_module()
    from hefesto_dualsense4unix.profiles import loader

    state = {
        "active_profile": "vitoria",
        "mouse_emulation": {"enabled": True, "speed": 9, "scroll_speed": 2},
    }
    monkeypatch.setattr(ipc_bridge, "daemon_state_full", lambda: state)
    monkeypatch.setattr(loader, "load_all_profiles", lambda: [_perfil_minimo()])

    draft, active_name = app_mod.HefestoApp._compute_draft_from_active_profile(object())

    assert active_name == "vitoria"
    assert draft is not None
    assert draft.mouse.enabled is True
    assert draft.mouse.speed == 9
    assert draft.mouse.scroll_speed == 2
    assert draft.mouse.dirty is False, "overlay programático não marca dirty"
    # Perfil segue mandando nas demais seções.
    assert draft.leds.player_leds == (True, False, False, False, False)


def _perfil_com_mouse(name: str = "pnc", speed: int = 8, scroll: int = 2) -> Any:
    from hefesto_dualsense4unix.profiles.schema import (
        LedsConfig,
        MatchAny,
        Profile,
        ProfileMouseConfig,
        RumbleConfig,
        TriggerConfig,
        TriggersConfig,
    )

    return Profile(
        name=name,
        match=MatchAny(),
        triggers=TriggersConfig(
            left=TriggerConfig(mode="Off", params=[]),
            right=TriggerConfig(mode="Off", params=[]),
        ),
        leds=LedsConfig(
            lightbar=(255, 170, 0),
            lightbar_brightness=0.6,
            player_leds=[False, False, True, False, False],
        ),
        rumble=RumbleConfig(),
        mouse=ProfileMouseConfig(enabled=True, speed=speed, scroll_speed=scroll),
    )


def test_bootstrap_perfil_com_mouse_nao_clobbera_com_vivo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """BUG-MOUSE-OVERLAY-CLOBBERS-SECTION-01: perfil COM seção mouse
    (point_and_click) + estado vivo DIVERGENTE (o lock manual bloqueou a ativação
    → mouse off/6) — o overlay NÃO sobrepõe: a aba mostra o valor do PERFIL (=o que
    será salvo), e Salvar Perfil preserva a seção intacta em vez de gravar o vivo."""
    app_mod = _load_app_module()
    from hefesto_dualsense4unix.profiles import loader

    # Daemon vivo com mouse OFF/6 (lock bloqueou); perfil ativo = pnc (on/8/2).
    state = {
        "active_profile": "pnc",
        "mouse_emulation": {"enabled": False, "speed": 6, "scroll_speed": 1},
    }
    monkeypatch.setattr(ipc_bridge, "daemon_state_full", lambda: state)
    monkeypatch.setattr(
        loader, "load_all_profiles", lambda: [_perfil_com_mouse("pnc", 8, 2)]
    )

    draft, active_name = app_mod.HefestoApp._compute_draft_from_active_profile(object())

    assert active_name == "pnc"
    assert draft is not None
    # A aba mostra o valor do PERFIL (não o vivo divergente).
    assert (draft.mouse.enabled, draft.mouse.speed, draft.mouse.scroll_speed) == (
        True,
        8,
        2,
    )
    assert draft.mouse.in_profile is True
    assert draft.mouse.dirty is False
    # E Salvar Perfil (sem tocar a aba) preserva a seção do perfil — não clobbera.
    salvo = draft.to_profile("pnc")
    assert salvo.mouse is not None
    assert (salvo.mouse.enabled, salvo.mouse.speed, salvo.mouse.scroll_speed) == (
        True,
        8,
        2,
    )


def test_bootstrap_sem_bloco_mouse_usa_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Daemon antigo (sem bloco mouse_emulation): draft mantém defaults."""
    app_mod = _load_app_module()
    from hefesto_dualsense4unix.profiles import loader

    monkeypatch.setattr(
        ipc_bridge, "daemon_state_full", lambda: {"active_profile": "vitoria"}
    )
    monkeypatch.setattr(loader, "load_all_profiles", lambda: [_perfil_minimo()])

    draft, active_name = app_mod.HefestoApp._compute_draft_from_active_profile(object())

    assert active_name == "vitoria"
    assert draft is not None
    assert draft.mouse.enabled is False
    assert draft.mouse.dirty is False


# ---------------------------------------------------------------------------
# Freeze do Aplicar cobre os sliders da aba Mouse
# ---------------------------------------------------------------------------


def test_frozen_widget_ids_incluem_sliders_de_mouse() -> None:
    assert "mouse_speed_scale" in FROZEN_WIDGET_IDS
    assert "mouse_scroll_speed_scale" in FROZEN_WIDGET_IDS
    assert "mouse_emulation_toggle" in FROZEN_WIDGET_IDS


# ---------------------------------------------------------------------------
# Glyphs do card Mapeamento (fix cosmético, ADR-011)
# ---------------------------------------------------------------------------


def test_glade_card_mapeamento_glyphs_via_ncr() -> None:
    """Triângulo/Círculo usam NCR (sobrevive ao sanitizer); Quadrado é literal."""
    from pathlib import Path

    from hefesto_dualsense4unix.app.constants import MAIN_GLADE

    conteúdo = Path(MAIN_GLADE).read_text(encoding="utf-8")
    assert "Triângulo (&#9651;) ou R2" in conteúdo
    assert "Círculo (&#9675;)" in conteúdo
    assert "Quadrado (□)" in conteúdo
    assert "Triângulo () ou R2" not in conteúdo, "parênteses vazios (glyph strippado)"
    assert "Círculo ()" not in conteúdo
