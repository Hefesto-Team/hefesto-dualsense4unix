"""Testes da aba Mouse sincronizada com o daemon (BUG-MOUSE-GUI-SYNC-01)."""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("mouse actions gui sync")

from typing import Any

import pytest

pytest.importorskip("gi")

from hefesto_dualsense4unix.app import ipc_bridge
from hefesto_dualsense4unix.app.actions.footer_actions import FROZEN_WIDGET_IDS
from hefesto_dualsense4unix.app.actions.mouse_actions import MouseActionsMixin
from hefesto_dualsense4unix.app.draft_config import DraftConfig


class _FakeSwitch:
    """Stub de Gtk.Switch que REEMITE state-set em todo set_active."""

    def __init__(self, owner: Any) -> None:
        self._owner = owner
        self._active = False
        self.set_active_calls = 0
        self.sensitive = True

    def get_active(self) -> bool:
        return self._active

    def set_active(self, value: bool) -> None:
        self.set_active_calls += 1
        self._active = bool(value)
        self._owner.on_mouse_toggle_set(self, bool(value))

    def set_sensitive(self, value: bool) -> None:
        self.sensitive = bool(value)


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

    switch.set_active(True)

    assert len(calls) == 1, "exatamente 1 tentativa de IPC"
    assert switch.set_active_calls == 2
    assert switch.get_active() is False, "switch revertido ao estado anterior"
    from hefesto_dualsense4unix.app.actions.mouse_actions import (
        SEM_RESPOSTA_DO_HEFESTO,
    )

    assert harness.toasts == [SEM_RESPOSTA_DO_HEFESTO]
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


def test_toggle_sucesso_atualiza_draft_sem_deixar_pendencia(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HARM-05: o sucesso do toggle NÃO deixa a seção suja.

    O `dirty` significa "há algo pendente para o Aplicar enviar". Marcá-lo aqui,
    DEPOIS de o daemon já ter aplicado o `mouse.emulation.set` com sucesso, era
    uma contradição — e cara: a seção ficava suja pelo resto da sessão, e o
    primeiro "Aplicar" do rodapé re-enviava mouse.emulation.set, religando o
    mouse e MATANDO o vpad no meio do jogo.

    O `in_profile=True` no lugar preserva a outra função do dirty: o `to_profile`
    inclui a seção quando `dirty` OU `in_profile`, então o "Salvar Perfil"
    continua levando o mouse junto.
    """
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
        (
            "mouse.emulation.set",
            {"enabled": True, "speed": 9, "scroll_speed": 2, "origin": "manual"},
        )
    ]
    assert harness.draft.mouse.enabled is True
    assert harness.draft.mouse.speed == 9
    assert harness.draft.mouse.scroll_speed == 2
    assert harness.draft.mouse.dirty is False, (
        "o daemon já aplicou — não há pendência; dirty aqui fazia o Aplicar "
        "seguinte religar o mouse e matar o vpad"
    )
    assert harness.draft.mouse.in_profile is True, (
        "sem isto o Salvar Perfil perderia a seção mouse"
    )
    assert switch.get_active() is True


def test_slider_envia_payload_sem_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Toggle stale-ON: o payload NUNCA inclui 'enabled' — religar é impossível."""
    harness, switch = _make_harness()
    assert switch is not None
    switch._active = True
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

    assert calls == [("mouse.emulation.set", {"speed": 9, "origin": "manual"})]
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

    assert calls == [("mouse.emulation.set", {"scroll_speed": 3, "origin": "manual"})]


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
    assert held[0][0] == {"speed": 7, "origin": "manual"}

    held[0][1]({"status": "ok"})

    assert len(held) == 2, "pendente reenviado ao terminar"
    assert held[1][0] == {"speed": 9, "origin": "manual"}, "só o último valor sobrevive"

    held[1][1]({"status": "ok"})
    assert len(held) == 2, "sem eco infinito"


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


def test_frozen_widget_ids_incluem_sliders_de_mouse() -> None:
    assert "mouse_speed_scale" in FROZEN_WIDGET_IDS
    assert "mouse_scroll_speed_scale" in FROZEN_WIDGET_IDS
    assert "mouse_emulation_toggle" in FROZEN_WIDGET_IDS
