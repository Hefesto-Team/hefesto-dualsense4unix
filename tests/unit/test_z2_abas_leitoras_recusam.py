"""Z2-1/Z2-2 — as três abas leitoras perguntam ao dono, e a recusa chega à tela."""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("z2 abas leitoras recusam")

from typing import Any

from hefesto_dualsense4unix.app import draft_config as draft_mod
from hefesto_dualsense4unix.app.actions import lightbar_actions
from hefesto_dualsense4unix.app.actions.config.secao_controles import (
    _PainelDosControles,
)
from hefesto_dualsense4unix.app.actions.lightbar_actions import LightbarActionsMixin
from hefesto_dualsense4unix.app.actions.rumble_actions import RumbleActionsMixin
from hefesto_dualsense4unix.app.alvo_de_edicao import (
    MOTIVO_SEM_ESTADO,
    definir_alvo,
)
from hefesto_dualsense4unix.profiles.schema import LedsConfig, MatchAny, Profile
from tests.unit.test_triggers_actions import _build_mixin as _build_triggers_mixin

UNIQ_1 = "aabbcc000001"
UNIQ_2 = "aabbcc000002"


def _draft_leds() -> draft_mod.DraftConfig:
    perfil = Profile(
        name="vitoria",
        match=MatchAny(),
        priority=5,
        leds=LedsConfig(lightbar=(10, 20, 30), auto_player_colors=True),
    )
    return draft_mod.DraftConfig.from_profile(perfil)


# Lightbar (L1) — _persist_leds_update e _aplicar_cor_no_controle


class _HostLuzes(LightbarActionsMixin):
    """Host virgem: nenhum atributo de alvo — nem canônico, nem legado."""

    def __init__(self) -> None:
        self.draft = _draft_leds()
        self._target_uniq_by_index: dict[int, str | None] = {1: UNIQ_1}
        self._widgets: dict[str, Any] = {}
        self._toasts: list[str] = []
        self._refresh_guard = False
        self._current_rgb = (0, 255, 0)
        self._current_brightness = 0.5

    def _get(self, widget_id: str) -> Any:
        return self._widgets.get(widget_id)

    def _toast_light(self, msg: str) -> None:
        self._toasts.append(msg)


def test_lightbar_desconhecido_nao_escreve_no_rascunho() -> None:
    """A MORDIDA: sem alvo, zero byte no rascunho — nunca cai em 'Todos'."""
    host = _HostLuzes()
    antes = host.draft
    resultado = host._persist_leds_update({"lightbar_rgb": (1, 2, 3)})
    assert resultado is False
    assert host.draft is antes, "escreveu no rascunho sem saber o alvo (P3)"


def test_lightbar_definido_em_todos_continua_escrevendo_igual() -> None:
    """A2 — o dublê também sabe ACEITAR: 'Todos' é escolha dela, não recusa."""
    host = _HostLuzes()
    definir_alvo(host, None, None)
    resultado = host._persist_leds_update({"lightbar_rgb": (1, 2, 3)})
    assert resultado is False
    assert host.draft.leds.lightbar_rgb == (1, 2, 3)


def test_lightbar_desconhecido_aplicar_recusa_com_motivo_e_zero_ipc(
    monkeypatch: Any,
) -> None:
    """Z2-2: a recusa de `alvo_de_edicao` chega à tela — zero IPC no meio."""
    host = _HostLuzes()
    monkeypatch.setattr(
        lightbar_actions,
        "led_set_detalhado",
        lambda *a, **kw: (_ for _ in ()).throw(
            AssertionError("IPC chamado com o alvo DESCONHECIDO")
        ),
    )
    ok = host._aplicar_cor_no_controle()
    assert ok is False
    assert host._toasts, "a recusa não chegou à tela (Z2-2)"
    assert MOTIVO_SEM_ESTADO in host._toasts[-1]
    assert "Nada foi alterado" in host._toasts[-1]


def test_lightbar_off_desconhecido_tambem_recusa(monkeypatch: Any) -> None:
    """`on_lightbar_off` duplica a rota do 'Aplicar' — mesma recusa."""
    host = _HostLuzes()
    monkeypatch.setattr(
        lightbar_actions,
        "led_set_detalhado",
        lambda *a, **kw: (_ for _ in ()).throw(AssertionError("IPC chamado")),
    )
    host.on_lightbar_off(None)  # type: ignore[arg-type]
    assert host._toasts
    assert MOTIVO_SEM_ESTADO in host._toasts[-1]
    assert host._current_rgb == (0, 255, 0)


class _HostRumble(RumbleActionsMixin):
    """Host virgem, mesmo molde do de Luzes."""

    def __init__(self) -> None:
        self.draft = draft_mod.DraftConfig.default()

    def _get(self, widget_id: str) -> Any:
        return None


def test_rumble_desconhecido_nao_escreve_no_rascunho() -> None:
    """A MORDIDA: intensidade mudada sem alvo não toca o rascunho."""
    host = _HostRumble()
    antes = host.draft
    host._gravar_intensidade_no_rascunho("max", None)
    assert host.draft is antes, "escreveu no rascunho sem saber o alvo (P3)"


def test_rumble_definido_em_todos_continua_gravando_igual() -> None:
    """A2 — 'Todos' (escolha dela) segue gravando byte-idêntico a antes."""
    host = _HostRumble()
    definir_alvo(host, None, None)
    host._gravar_intensidade_no_rascunho("max", None)
    assert host.draft.rumble.policy == "max"


def test_gatilhos_desconhecido_nao_escreve_no_rascunho(monkeypatch: Any) -> None:
    """A MORDIDA: preset escolhido sem alvo não grava — e não limpa overrides"""
    mixin = _build_triggers_mixin(monkeypatch)
    mixin.install_triggers_tab()
    del mixin._edit_target_uniq
    assert not hasattr(mixin, "_edit_target_uniq")
    combo = mixin._trigger_mode["left"]
    combo.set_active_id("Rigid")

    mixin.on_trigger_left_mode_changed(combo)

    assert mixin.draft.triggers.left.mode == "Off", (
        "gravou no rascunho sem saber o alvo — a mesma família do P3"
    )


def test_gatilhos_desconhecido_aplicar_recusa_com_motivo_e_zero_ipc(
    monkeypatch: Any,
) -> None:
    """Z2-2: `_apply_trigger` recusa com a frase pronta, e `trigger.set` nunca"""
    mixin = _build_triggers_mixin(monkeypatch)
    mixin.install_triggers_tab()
    combo = mixin._trigger_mode["left"]
    combo.set_active_id("Rigid")
    mixin.on_trigger_left_mode_changed(combo)
    widgets = mixin._trigger_param_widgets["left"]
    widgets["position"].set_value(5)
    widgets["force"].set_value(200)
    del mixin._edit_target_uniq
    assert not hasattr(mixin, "_edit_target_uniq")

    mixin.on_trigger_left_apply(None)

    assert mixin._trigger_set_calls == [], "IPC saiu com o alvo DESCONHECIDO"
    _ctx, msg = mixin._widgets["status_bar"].pushed[-1]
    assert MOTIVO_SEM_ESTADO in msg
    assert "Nada foi alterado" in msg


class _HostConfig:
    """Host virgem: nenhum atributo de alvo."""


def _entrada(uniq: str, slot: int) -> dict[str, Any]:
    return {
        "uniq": uniq,
        "transport": "bt",
        "connected": True,
        "player_slot": slot,
        "name": "Sony Interactive Entertainment Wireless Controller",
        "vid": "054c",
        "pid": "0ce6",
    }


def test_config_desconhecido_nenhum_card_marcado() -> None:
    """A MORDIDA: sem saber o alvo, nenhum card nasce com a marca de alvo."""
    host = _HostConfig()
    painel = _PainelDosControles(host)
    cards = painel._cards_da_mesa(
        [_entrada(UNIQ_1, 1), _entrada(UNIQ_2, 2)], []
    )
    assert not any(c.selecionado for c in cards)


def test_config_alvo_definido_marca_so_o_card_certo() -> None:
    """A2 — com um controle escolhido, só o card dele acende a marca."""
    host = _HostConfig()
    definir_alvo(host, UNIQ_1, "Controle 1 (BT)")
    painel = _PainelDosControles(host)
    cards = painel._cards_da_mesa(
        [_entrada(UNIQ_1, 1), _entrada(UNIQ_2, 2)], []
    )
    marcados = [c.uniq for c in cards if c.selecionado]
    assert marcados == [UNIQ_1]
