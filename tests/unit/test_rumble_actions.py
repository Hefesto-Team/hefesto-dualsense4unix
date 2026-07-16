"""Testes unitários de RumbleActionsMixin (AUDIT-FINDING-COVERAGE-ACTIONS-ZERO-01).

Cobrem a lógica pura de:
  - Seleção de política via toggles (economia/balanceado/max/auto).
  - Sincronização slider de intensidade <-> política.
  - Aplicar/parar rumble persistindo valores no draft e chamando IPC.
  - Refresh do draft para widgets.

Usa padrão `_FakeMixin` (descriptor protocol `__get__`) e stubs de
`gi.repository.{Gtk,GLib}` para rodar sem PyGObject instalado no venv
(armadilha A-12). Mesmo cenário de `test_status_actions_reconnect.py`.
"""
from __future__ import annotations

import sys
import types
from typing import Any

import pytest


def _install_gi_stubs() -> None:
    # GATE-SKIP-MASK-01: com o PyGObject real disponível, NÃO instala stubs —
    # o merge abaixo mutaria o gi REAL (sobrescreve GLib.idle_add e
    # require_version) e fazia testes de GUI pularem como "ambiente sem GTK".
    existente = sys.modules.get("gi")
    if existente is None or getattr(existente, "__spec__", None) is not None:
        try:
            import gi

            gi.require_version("Gtk", "3.0")
            from gi.repository import Gtk  # noqa: F401

            return
        except Exception:  # pragma: no cover — ambientes sem GTK
            pass

    # Reutiliza módulos stub existentes (se outros testes já injetaram) para
    # merge de atributos — caso contrário cria do zero.
    gi_mod = sys.modules.get("gi") or types.ModuleType("gi")
    gi_mod.require_version = lambda _n, _v: None  # type: ignore[attr-defined]
    repo_mod = sys.modules.get("gi.repository") or types.ModuleType(
        "gi.repository"
    )
    gtk_mod = sys.modules.get("gi.repository.Gtk") or types.ModuleType(
        "gi.repository.Gtk"
    )
    glib_mod = sys.modules.get("gi.repository.GLib") or types.ModuleType(
        "gi.repository.GLib"
    )

    # Classes mínimas (idempotente).
    for cls_name in (
        "Builder", "Window", "Button", "ToggleButton", "ComboBoxText",
        "Switch", "TextView", "TextBuffer", "Scale", "Label", "Box",
    ):
        if not hasattr(gtk_mod, cls_name):
            setattr(gtk_mod, cls_name, type(cls_name, (), {}))

    glib_mod.timeout_add = lambda *_a, **_kw: 0  # type: ignore[attr-defined]
    glib_mod.timeout_add_seconds = lambda *_a, **_kw: 0  # type: ignore[attr-defined]
    glib_mod.source_remove = lambda *_a, **_kw: None  # type: ignore[attr-defined]
    glib_mod.idle_add = lambda fn, *a, **kw: fn(*a, **kw)  # type: ignore[attr-defined]
    repo_mod.Gtk = gtk_mod  # type: ignore[attr-defined]
    repo_mod.GLib = glib_mod  # type: ignore[attr-defined]

    sys.modules["gi"] = gi_mod
    sys.modules["gi.repository"] = repo_mod
    sys.modules["gi.repository.Gtk"] = gtk_mod
    sys.modules["gi.repository.GLib"] = glib_mod


_install_gi_stubs()

from hefesto_dualsense4unix.app.actions import rumble_actions  # noqa: E402

# --- Fakes de widgets GTK ---------------------------------------------


class _FakeScale:
    def __init__(self, value: float = 0.0) -> None:
        self._value = float(value)

    def get_value(self) -> float:
        return self._value

    def set_value(self, v: float) -> None:
        self._value = float(v)


class _FakeToggleButton:
    def __init__(self, active: bool = False) -> None:
        self._active = active

    def get_active(self) -> bool:
        return self._active

    def set_active(self, v: bool) -> None:
        self._active = bool(v)


class _FakeLabel:
    def __init__(self) -> None:
        self._visible = False
        self._text = ""

    def set_visible(self, v: bool) -> None:
        self._visible = bool(v)

    def get_visible(self) -> bool:
        return self._visible

    def set_text(self, t: str) -> None:
        self._text = t

    def set_markup(self, t: str) -> None:
        self._text = t


class _FakeStatusBar:
    def __init__(self) -> None:
        self.pushed: list[tuple[int, str]] = []
        self._ctx_counter = 0

    def get_context_id(self, key: str) -> int:
        self._ctx_counter += 1
        return self._ctx_counter

    def pop(self, ctx_id: int) -> None:
        # _status_toast faz pop antes do push (no máx 1 msg por contexto).
        if self.pushed:
            self.pushed.pop()

    def push(self, ctx_id: int, msg: str) -> None:
        self.pushed.append((ctx_id, msg))


# --- FakeMixin ---------------------------------------------------------


class _FakeRumbleMixin:
    """Composição mínima pra rodar RumbleActionsMixin sem GTK real."""

    def __init__(self) -> None:
        from hefesto_dualsense4unix.app.draft_config import DraftConfig

        self.draft = DraftConfig.default()
        # M1: guard renomeado por mixin (era _guard_refresh compartilhado).
        self._rumble_guard_refresh = False
        self._rumble_policy = "balanceado"
        # M6: id do timer do teste de 500ms (atributo de classe no mixin real).
        self._rumble_test_source: int | None = None

        self._widgets: dict[str, Any] = {
            "rumble_policy_economia": _FakeToggleButton(),
            "rumble_policy_balanceado": _FakeToggleButton(active=True),
            "rumble_policy_max": _FakeToggleButton(),
            "rumble_policy_auto": _FakeToggleButton(),
            "rumble_policy_slider": _FakeScale(70.0),
            "rumble_policy_auto_label": _FakeLabel(),
            "rumble_weak_scale": _FakeScale(0.0),
            "rumble_strong_scale": _FakeScale(0.0),
            "rumble_state_label": _FakeLabel(),
            "status_bar": _FakeStatusBar(),
        }

    def _get(self, key: str) -> Any:
        return self._widgets.get(key)


def _build_mixin(monkeypatch: pytest.MonkeyPatch) -> _FakeRumbleMixin:
    """Instancia o mixin via composição + neutraliza IPC real."""
    calls: dict[str, list[Any]] = {
        "rumble_set": [],
        "rumble_stop": [],
        "rumble_passthrough": [],
        "rumble_policy_set": [],
        "rumble_policy_custom": [],
        "call_async": [],
        # Folga de timeout pedida em cada rota (HARM-15/HARM-19): sem ela a aba
        # declarava o daemon morto/desconhecido com ele VIVO.
        "call_async_timeout": [],
        "rumble_policy_set_timeout": [],
    }
    # HARM-19: a aba usa a rota "checked" — `(ok, motivo)`. Mutável para o teste
    # escolher entre daemon que RECUSA (vivo) e daemon que não responde.
    resultado_policy: list[tuple[bool, str | None]] = [(True, None)]

    def fake_rumble_set(weak: int, strong: int) -> bool:
        calls["rumble_set"].append((weak, strong))
        return True

    def fake_rumble_stop() -> bool:
        calls["rumble_stop"].append(True)
        return True

    def fake_rumble_passthrough(enabled: bool = True) -> bool:
        calls["rumble_passthrough"].append(enabled)
        return True

    def fake_rumble_policy_set_checked(
        policy: str, *, timeout: float | None = None
    ) -> tuple[bool, str | None]:
        calls["rumble_policy_set"].append(policy)
        calls["rumble_policy_set_timeout"].append(timeout)
        return resultado_policy[0]

    def fake_rumble_policy_custom(mult: float) -> bool:
        calls["rumble_policy_custom"].append(mult)
        return True

    def fake_call_async(
        method: str,
        params: dict,
        on_success: Any = None,
        on_failure: Any = None,
        **kwargs: Any,
    ) -> None:
        calls["call_async"].append((method, params))
        calls["call_async_timeout"].append(kwargs.get("timeout_s"))

    monkeypatch.setattr(rumble_actions, "rumble_set", fake_rumble_set)
    monkeypatch.setattr(rumble_actions, "rumble_stop", fake_rumble_stop)
    monkeypatch.setattr(
        rumble_actions, "rumble_passthrough", fake_rumble_passthrough
    )
    monkeypatch.setattr(
        rumble_actions, "rumble_policy_set_checked", fake_rumble_policy_set_checked
    )
    monkeypatch.setattr(
        rumble_actions, "rumble_policy_custom", fake_rumble_policy_custom
    )
    monkeypatch.setattr(rumble_actions, "call_async", fake_call_async)

    instance = _FakeRumbleMixin()
    instance._ipc_calls = calls  # type: ignore[attr-defined]
    instance._policy_result = resultado_policy  # type: ignore[attr-defined]

    for name in (
        "install_rumble_tab",
        "_sync_policy_from_state",
        "_apply_policy_to_widgets",
        "on_rumble_policy_economia",
        "on_rumble_policy_balanceado",
        "on_rumble_policy_max",
        "on_rumble_policy_auto",
        "_set_policy",
        "on_rumble_policy_slider_changed",
        "_activate_policy_toggle",
        "on_rumble_apply",
        "on_rumble_test_500ms",
        "on_rumble_stop",
        "on_rumble_passthrough",
        "_refresh_rumble_from_draft",
        "_refresh_rumble_state_label_async",
        "_cancel_rumble_test_timer",
        "_update_rumble_state_label",
        "_read_scales",
        "_set_scales",
        "_rumble_test_stop",
        "_toast_rumble",
    ):
        setattr(
            instance,
            name,
            rumble_actions.RumbleActionsMixin.__dict__[name].__get__(
                instance, type(instance)
            ),
        )
    # _toast_rumble delega ao helper compartilhado _status_toast (base.py); como o
    # fake usa composição (não herda WidgetAccessMixin), ligamos o helper à mão.
    instance._status_toast = (  # type: ignore[attr-defined]
        rumble_actions.RumbleActionsMixin._status_toast.__get__(
            instance, type(instance)
        )
    )
    return instance


# --- Testes: política (toggles) ---------------------------------------


def test_on_rumble_policy_economia_ativa_preset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mixin = _build_mixin(monkeypatch)
    btn = mixin._widgets["rumble_policy_economia"]
    btn.set_active(True)
    mixin.on_rumble_policy_economia(btn)

    assert mixin._rumble_policy == "economia"
    assert mixin._ipc_calls["rumble_policy_set"] == ["economia"]
    # Slider move para 30% (0.3 mult).
    assert mixin._widgets["rumble_policy_slider"].get_value() == pytest.approx(30.0)


def test_on_rumble_policy_balanceado_ativa_preset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mixin = _build_mixin(monkeypatch)
    btn = mixin._widgets["rumble_policy_balanceado"]
    btn.set_active(True)
    mixin.on_rumble_policy_balanceado(btn)

    assert mixin._rumble_policy == "balanceado"
    assert "balanceado" in mixin._ipc_calls["rumble_policy_set"]


def test_on_rumble_policy_auto_mostra_label(monkeypatch: pytest.MonkeyPatch) -> None:
    mixin = _build_mixin(monkeypatch)
    btn = mixin._widgets["rumble_policy_auto"]
    btn.set_active(True)
    mixin.on_rumble_policy_auto(btn)

    assert mixin._rumble_policy == "auto"
    assert mixin._widgets["rumble_policy_auto_label"].get_visible() is True


def test_on_rumble_policy_reafirma_e_reenvia_ipc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A1: clicar num toggle já-ativo o desmarca (get_active=False); o handler
    re-afirma o botão e REENVIA o IPC (sem clique morto). Sempre 1 afundado."""
    mixin = _build_mixin(monkeypatch)
    btn = mixin._widgets["rumble_policy_max"]
    btn.set_active(False)  # simula o clique num já-ativo que o desmarcou
    mixin.on_rumble_policy_max(btn)

    # IPC reenviado mesmo com get_active()==False no clique.
    assert mixin._ipc_calls["rumble_policy_set"] == ["max"]
    # Exclusão mútua: exatamente 1 política afundada (max re-afirmado).
    assert mixin._widgets["rumble_policy_max"].get_active() is True
    assert mixin._widgets["rumble_policy_economia"].get_active() is False
    assert mixin._widgets["rumble_policy_balanceado"].get_active() is False
    assert mixin._widgets["rumble_policy_auto"].get_active() is False


def test_on_rumble_policy_guard_refresh_noop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Com o guard ativo, handler não dispara IPC."""
    mixin = _build_mixin(monkeypatch)
    mixin._rumble_guard_refresh = True
    btn = mixin._widgets["rumble_policy_max"]
    btn.set_active(True)
    mixin.on_rumble_policy_max(btn)

    assert mixin._ipc_calls["rumble_policy_set"] == []


# --- Testes: slider de intensidade ------------------------------------


def test_on_rumble_policy_slider_changed_preset_balanceado(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Slider em 70% casa mult canônico de balanceado (0.7)."""
    mixin = _build_mixin(monkeypatch)
    mixin._rumble_policy = "economia"
    slider = mixin._widgets["rumble_policy_slider"]
    slider.set_value(70.0)
    mixin.on_rumble_policy_slider_changed(slider)

    assert mixin._rumble_policy == "balanceado"
    assert "balanceado" in mixin._ipc_calls["rumble_policy_set"]


def test_on_rumble_policy_slider_changed_custom(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Slider em valor não-canônico (ex.: 55%) vira política custom."""
    mixin = _build_mixin(monkeypatch)
    slider = mixin._widgets["rumble_policy_slider"]
    slider.set_value(55.0)
    mixin.on_rumble_policy_slider_changed(slider)

    assert mixin._rumble_policy == "custom"
    assert mixin._ipc_calls["rumble_policy_custom"] == [pytest.approx(0.55)]
    for pid in (
        "rumble_policy_economia",
        "rumble_policy_balanceado",
        "rumble_policy_max",
        "rumble_policy_auto",
    ):
        assert mixin._widgets[pid].get_active() is False


# --- Testes: política persiste no draft (FEAT-RUMBLE-POLICY-PROFILE-01) --


def test_set_policy_grava_no_draft(monkeypatch: pytest.MonkeyPatch) -> None:
    """Escolher um preset persiste a política no draft (rodapé salva o que ela vê)."""
    mixin = _build_mixin(monkeypatch)
    btn = mixin._widgets["rumble_policy_max"]
    btn.set_active(True)
    mixin.on_rumble_policy_max(btn)

    assert mixin.draft.rumble.policy == "max"
    assert mixin.draft.rumble.custom_mult is None


def test_slider_custom_grava_mult_no_draft(monkeypatch: pytest.MonkeyPatch) -> None:
    """Slider em valor não-canônico persiste policy=custom + mult no draft."""
    mixin = _build_mixin(monkeypatch)
    slider = mixin._widgets["rumble_policy_slider"]
    slider.set_value(55.0)
    mixin.on_rumble_policy_slider_changed(slider)

    assert mixin.draft.rumble.policy == "custom"
    assert mixin.draft.rumble.custom_mult == pytest.approx(0.55)


def test_preset_apos_custom_zera_custom_mult(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Voltar a um preset limpa custom_mult (schema rejeita mult fora de custom)."""
    mixin = _build_mixin(monkeypatch)
    slider = mixin._widgets["rumble_policy_slider"]
    slider.set_value(55.0)
    mixin.on_rumble_policy_slider_changed(slider)
    mixin._set_policy("economia")

    assert mixin.draft.rumble.policy == "economia"
    assert mixin.draft.rumble.custom_mult is None
    # E o draft com política vira um perfil válido (round-trip do rodapé).
    profile = mixin.draft.to_profile("perfil_rumble", priority=5)
    assert profile.rumble.policy == "economia"


# --- Testes: apply / test / stop --------------------------------------


def test_on_rumble_apply_persiste_draft_e_chama_ipc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mixin = _build_mixin(monkeypatch)
    mixin._widgets["rumble_weak_scale"].set_value(120)
    mixin._widgets["rumble_strong_scale"].set_value(200)

    mixin.on_rumble_apply(None)

    assert mixin.draft.rumble.weak == 120
    assert mixin.draft.rumble.strong == 200
    assert mixin._ipc_calls["rumble_set"] == [(120, 200)]


def test_on_rumble_stop_zera_scales_e_chama_ipc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mixin = _build_mixin(monkeypatch)
    mixin._widgets["rumble_weak_scale"].set_value(160)
    mixin._widgets["rumble_strong_scale"].set_value(220)

    mixin.on_rumble_stop(None)

    assert mixin._widgets["rumble_weak_scale"].get_value() == 0
    assert mixin._widgets["rumble_strong_scale"].get_value() == 0
    assert mixin._ipc_calls["rumble_stop"] == [True]


def test_on_rumble_passthrough_devolve_rumble_ao_jogo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FEAT-RUMBLE-PASSTHROUGH-GUI-01: o botão chama rumble.passthrough(True) e
    zera os sliders — antídoto do 'Parar'."""
    mixin = _build_mixin(monkeypatch)
    mixin._widgets["rumble_weak_scale"].set_value(120)

    mixin.on_rumble_passthrough(None)

    assert mixin._widgets["rumble_weak_scale"].get_value() == 0
    assert mixin._ipc_calls["rumble_passthrough"] == [True]


def test_on_rumble_test_500ms_aplica_defaults_quando_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Teste com sliders em 0 dispara valor default (weak=160, strong=220)."""
    mixin = _build_mixin(monkeypatch)
    monkeypatch.setattr(
        rumble_actions.GLib, "timeout_add", lambda _ms, _fn: 1
    )

    mixin.on_rumble_test_500ms(None)

    assert mixin._ipc_calls["rumble_set"] == [(160, 220)]
    assert mixin._widgets["rumble_weak_scale"].get_value() == 160
    assert mixin._widgets["rumble_strong_scale"].get_value() == 220


# --- Testes: _apply_policy_to_widgets + refresh ----------------------


def test_apply_policy_to_widgets_ativa_toggle_correto(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mixin = _build_mixin(monkeypatch)
    mixin._apply_policy_to_widgets("max", 1.0)

    assert mixin._widgets["rumble_policy_max"].get_active() is True
    assert mixin._widgets["rumble_policy_economia"].get_active() is False
    assert mixin._widgets["rumble_policy_slider"].get_value() == pytest.approx(100.0)


def test_apply_policy_to_widgets_custom_usa_custom_mult(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Policy=custom move slider para custom_mult*100."""
    mixin = _build_mixin(monkeypatch)
    mixin._apply_policy_to_widgets("custom", 0.42)

    assert mixin._widgets["rumble_policy_slider"].get_value() == pytest.approx(42.0)
    assert mixin._widgets["rumble_policy_auto_label"].get_visible() is False


def test_refresh_rumble_from_draft_popula_scales(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mixin = _build_mixin(monkeypatch)
    new_rumble = mixin.draft.rumble.model_copy(update={"weak": 88, "strong": 177})
    mixin.draft = mixin.draft.model_copy(update={"rumble": new_rumble})

    mixin._refresh_rumble_from_draft()

    assert mixin._widgets["rumble_weak_scale"].get_value() == 88.0
    assert mixin._widgets["rumble_strong_scale"].get_value() == 177.0


def test_install_rumble_tab_chama_state_full(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mixin = _build_mixin(monkeypatch)
    mixin.install_rumble_tab()
    assert any(c[0] == "daemon.state_full" for c in mixin._ipc_calls["call_async"])


# --- Testes: BUG-RUMBLE-POLICY-DRAFT-DIVERGE-01 -----------------------


def test_refresh_com_opiniao_no_draft_reflete_draft_nao_daemon(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Perfil com opinião: widgets refletem o DRAFT (o que o rodapé salva),
    sem consultar o estado vivo do daemon."""
    mixin = _build_mixin(monkeypatch)
    new_rumble = mixin.draft.rumble.model_copy(update={"policy": "economia"})
    mixin.draft = mixin.draft.model_copy(update={"rumble": new_rumble})

    mixin._refresh_rumble_from_draft()

    assert mixin._widgets["rumble_policy_economia"].get_active() is True
    assert mixin._widgets["rumble_policy_max"].get_active() is False
    assert mixin._widgets["rumble_policy_slider"].get_value() == pytest.approx(30.0)
    # A POLÍTICA veio do draft (não do daemon) — BUG-RUMBLE-POLICY-DRAFT-DIVERGE-01.
    # Feature #4: há UMA leitura de state_full APENAS para o indicador de estado da
    # vibração (FF/passthrough — dado vivo que não existe no draft); ela NÃO lê a
    # política do daemon, então o bug do policy-diverge não retorna.
    assert mixin._ipc_calls["call_async"] == [("daemon.state_full", {})]
    # E o draft segue intocado (economia).
    assert mixin.draft.rumble.policy == "economia"


def test_refresh_sem_opiniao_exibe_daemon_sem_gravar_draft(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Perfil SEM opinião: widgets exibem o estado do daemon com indicação na
    statusbar, mas o draft NÃO ganha opinião (senão todo perfil ganharia
    política só de abrir a aba)."""
    mixin = _build_mixin(monkeypatch)

    def call_async_entrega_max(
        method: str,
        params: dict,
        on_success: Any = None,
        on_failure: Any = None,
        **_kw: Any,
    ) -> None:
        assert method == "daemon.state_full"
        if on_success is not None:
            on_success({"rumble_policy": "max", "rumble_policy_custom_mult": 0.7})

    monkeypatch.setattr(rumble_actions, "call_async", call_async_entrega_max)
    assert mixin.draft.rumble.policy is None  # default: sem opinião

    mixin._refresh_rumble_from_draft()

    # Widgets refletem o estado vivo do daemon (referência).
    assert mixin._widgets["rumble_policy_max"].get_active() is True
    # Mas o draft continua sem opinião — o rodapé não salvará política.
    assert mixin.draft.rumble.policy is None
    assert mixin.draft.rumble.custom_mult is None
    # Indicação de "sem opinião no perfil" na statusbar.
    mensagens = [msg for _ctx, msg in mixin._widgets["status_bar"].pushed]
    assert any("não" in m and "opinião" in m for m in mensagens)


def test_toggle_apos_refresh_sem_opiniao_grava_draft(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Clicar num toggle depois do refresh continua gravando no draft."""
    mixin = _build_mixin(monkeypatch)
    mixin._refresh_rumble_from_draft()

    btn = mixin._widgets["rumble_policy_auto"]
    btn.set_active(True)
    mixin.on_rumble_policy_auto(btn)

    assert mixin.draft.rumble.policy == "auto"


# --- Testes: HARM-19 (a faixa do slider = a faixa que o daemon aceita) ----


def test_custom_mult_round_trip(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ida e volta valor/100 no slider, inclusive no round-trip de perfil."""
    mixin = _build_mixin(monkeypatch)
    slider = mixin._widgets["rumble_policy_slider"]
    slider.set_value(100.0)
    mixin.on_rumble_policy_slider_changed(slider)

    # 100% coincide com o preset "max" — a aba afunda o preset em vez de custom.
    assert mixin._rumble_policy == "max"
    assert mixin.draft.rumble.policy == "max"

    slider.set_value(95.0)
    mixin.on_rumble_policy_slider_changed(slider)
    assert mixin._rumble_policy == "custom"
    assert mixin.draft.rumble.custom_mult == pytest.approx(0.95)
    assert mixin._ipc_calls["rumble_policy_custom"] == [pytest.approx(0.95)]

    mixin._apply_policy_to_widgets("custom", 0.95)
    assert slider.get_value() == pytest.approx(95.0)

    profile = mixin.draft.to_profile("perfil_custom_95", priority=5)
    assert profile.rumble.policy == "custom"
    assert profile.rumble.custom_mult == pytest.approx(0.95)


def test_glade_rumble_policy_adj_vai_ate_o_teto_do_schema() -> None:
    """O slider oferece a faixa INTEIRA que o schema aceita (`mult * 100`).

    HARM-19: a faixa teve três donos (2.0 no schema, 1.0 no handler, 200% aqui) e
    de 101% em diante a usuária levava erro de validação. A cura foi alinhar o
    HANDLER ao schema — truncar o slider em 100% mataria o que o
    BUG-RUMBLE-CUSTOM-MULT-CAP-01 entregou de propósito: acima de 100% o
    multiplicador AMPLIFICA o que o jogo pediu.
    """
    import xml.etree.ElementTree as ET
    from pathlib import Path

    from hefesto_dualsense4unix.profiles.schema import RUMBLE_CUSTOM_MULT_MAX

    glade = (
        Path(__file__).resolve().parents[2]
        / "src" / "hefesto_dualsense4unix" / "gui" / "main.glade"
    )
    tree = ET.parse(glade)  # também valida que o XML segue bem formado
    adj = next(
        (obj for obj in tree.iter("object") if obj.get("id") == "rumble_policy_adj"),
        None,
    )
    assert adj is not None, "adjustment rumble_policy_adj não encontrado"
    props = {p.get("name"): (p.text or "") for p in adj.findall("property")}
    assert float(props["upper"]) == RUMBLE_CUSTOM_MULT_MAX * 100
    assert float(props["lower"]) == 0.0


def test_faixa_do_slider_cabe_no_que_o_handler_do_daemon_aceita() -> None:
    """A faixa da UI é subconjunto da faixa aceita por `rumble.policy_custom`.

    Prova de coexistência (o par que estava divergente): o topo do adjustment
    (upper/100) tem de passar pela validação do handler REAL do daemon.
    """
    import asyncio
    import xml.etree.ElementTree as ET
    from pathlib import Path
    from types import SimpleNamespace

    from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin

    glade = (
        Path(__file__).resolve().parents[2]
        / "src" / "hefesto_dualsense4unix" / "gui" / "main.glade"
    )
    tree = ET.parse(glade)
    adj = next(
        obj for obj in tree.iter("object") if obj.get("id") == "rumble_policy_adj"
    )
    props = {p.get("name"): (p.text or "") for p in adj.findall("property")}
    topo = float(props["upper"]) / 100.0

    class _Handlers(IpcHandlersMixin):
        def __init__(self) -> None:
            self.daemon = SimpleNamespace(
                config=SimpleNamespace(
                    rumble_policy="balanceado", rumble_policy_custom_mult=0.7
                )
            )

        def _mark_rumble_policy_manual(self) -> None:
            pass

    handlers = _Handlers()
    result = asyncio.run(handlers._handle_rumble_policy_custom({"mult": topo}))
    assert result["status"] == "ok"
    assert handlers.daemon.config.rumble_policy_custom_mult == pytest.approx(topo)


# ---------------------------------------------------------------------------
# HARM-15/HARM-19 — a aba Rumble para de mentir sobre o daemon
# ---------------------------------------------------------------------------


def test_sem_resposta_a_aba_nao_chuta_uma_politica(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sem resposta, a aba NÃO SABE a política — e afirmar uma é mentir.

    Repro: o daemon está em "max"; a usuária abre a aba durante um hotplug; o
    state_full passa do timeout. O `_on_err` afirmava "Balanceado / 70%" POR CIMA
    da política real, e o controle passava a fazer o oposto do que a tela dizia.
    """
    mixin = _build_mixin(monkeypatch)
    # A tela como o daemon a deixou: "Máximo" afundado, slider em 100%.
    mixin._widgets["rumble_policy_balanceado"].set_active(False)
    mixin._widgets["rumble_policy_max"].set_active(True)
    mixin._widgets["rumble_policy_slider"].set_value(100.0)

    def call_async_falha(
        _method: str,
        _params: dict,
        on_success: Any = None,
        on_failure: Any = None,
        **_kw: Any,
    ) -> None:
        if on_failure is not None:
            on_failure(RuntimeError("conexão timeout"))

    monkeypatch.setattr(rumble_actions, "call_async", call_async_falha)

    mixin._sync_policy_from_state()

    # Os widgets ficam como estavam — nada de "Balanceado / 70%" inventado.
    assert mixin._widgets["rumble_policy_max"].get_active() is True
    assert mixin._widgets["rumble_policy_balanceado"].get_active() is False
    assert mixin._widgets["rumble_policy_slider"].get_value() == 100.0


def test_leitura_da_politica_da_folga_de_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HARM-15: o state_full não cabe nos 0.25s default sob carga."""
    mixin = _build_mixin(monkeypatch)

    mixin._sync_policy_from_state()
    mixin._refresh_rumble_state_label_async()

    assert mixin._ipc_calls["call_async_timeout"] == [1.0, 1.0]


def test_recusa_do_daemon_vivo_mostra_o_motivo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`_safe_call` devolve (False, None) também para erro JSON-RPC do servidor —
    daemon VIVO que recusou. O toast acusava categoricamente "não está rodando"."""
    mixin = _build_mixin(monkeypatch)
    mixin._policy_result[0] = (False, "mult fora da faixa")  # type: ignore[attr-defined]

    mixin._set_policy("max")

    msg = [m for _ctx, m in mixin._widgets["status_bar"].pushed][-1]
    assert "mult fora da faixa" in msg
    assert "não está rodando" not in msg


def test_daemon_offline_continua_dizendo_que_esta_offline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sem motivo = não respondeu: aí sim o diagnóstico é o daemon."""
    mixin = _build_mixin(monkeypatch)
    mixin._policy_result[0] = (False, None)  # type: ignore[attr-defined]

    mixin._set_policy("max")

    msg = [m for _ctx, m in mixin._widgets["status_bar"].pushed][-1]
    assert "não está rodando" in msg


def test_troca_de_politica_da_folga_de_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mixin = _build_mixin(monkeypatch)

    mixin._set_policy("economia")

    assert mixin._ipc_calls["rumble_policy_set_timeout"] == [1.0]
