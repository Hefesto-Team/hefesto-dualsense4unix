"""Testes unitários de TriggersActionsMixin (AUDIT-FINDING-COVERAGE-ACTIONS-ZERO-01).

Cobrem:
  - Seleção de preset via dropdown de modo (Off, Rigid, Pulse, MultiPos*).
  - Aplicar trigger persistindo no draft e chamando IPC.
  - Reset para Off.
  - Mudança de preset posicional (MultiPositionFeedback/Vibration).
  - Collect de valores de sliders para payload IPC.

Padrão `_FakeMixin` + stubs de `gi` (armadilha A-12).
"""
from __future__ import annotations

import sys
import types
from typing import Any

import pytest

# --- Fakes headless de widgets Gtk usados pela aba Triggers ------------
# Módulo-level para servirem tanto ao stub de CI (_install_gi_stubs)
# quanto ao patch hermético dos bindings do módulo em _build_mixin.


class _Orientation:
    HORIZONTAL = 0
    VERTICAL = 1


class _PositionType:
    LEFT = 0
    RIGHT = 1


class _Adjustment:
    def __init__(
        self,
        value: float = 0,
        lower: float = 0,
        upper: float = 100,
        step_increment: float = 1,
        page_increment: float = 10,
    ) -> None:
        self.value = value


class _StyleContext:
    """Guarda as classes CSS aplicadas, para os testes poderem afirmá-las."""

    def __init__(self) -> None:
        self.classes: set[str] = set()

    def add_class(self, nome: str) -> None:
        self.classes.add(nome)


class _Box:
    def __init__(self, *_a: Any, **_kw: Any) -> None:
        self._children: list[Any] = []
        self._style = _StyleContext()

    def pack_start(self, child: Any, *_a: Any, **_kw: Any) -> None:
        self._children.append(child)

    def get_children(self) -> list[Any]:
        return list(self._children)

    def remove(self, child: Any) -> None:
        self._children.remove(child)

    def show_all(self) -> None:
        pass

    def set_homogeneous(self, _v: bool) -> None:
        pass

    def get_style_context(self) -> _StyleContext:
        return self._style

    def set_visible(self, _v: bool) -> None:
        pass


class _Scale:
    def __init__(self, *_a: Any, **kw: Any) -> None:
        adjust = kw.get("adjustment")
        self._value: float = float(adjust.value) if adjust else 0.0

    def set_digits(self, _n: int) -> None:
        pass

    def set_value_pos(self, _p: int) -> None:
        pass

    def set_hexpand(self, _v: bool) -> None:
        pass

    def set_value(self, v: float) -> None:
        self._value = float(v)

    def get_value(self) -> float:
        return self._value

    def queue_draw(self) -> None:
        pass

    def connect(self, _signal: str, _cb: Any) -> None:
        pass


class _Label:
    def __init__(self, *_a: Any, **kw: Any) -> None:
        self._text = kw.get("label", "")
        # Espelham o que `_build_param_row` configura no rótulo do slider: uma
        # linha só, com reticências se não couber (S3 — a coluna encolheu para
        # 150px e "Intensidade início (1-8)" não pode voltar a quebrar linha).
        self.line_wrap: bool | None = None
        self.ellipsize: Any = None
        self.tooltip: str | None = None

    def set_xalign(self, _x: float) -> None:
        pass

    def set_size_request(self, _w: int, _h: int) -> None:
        pass

    def set_line_wrap(self, wrap: bool) -> None:
        self.line_wrap = wrap

    def set_ellipsize(self, mode: Any) -> None:
        self.ellipsize = mode

    def set_tooltip_text(self, texto: str) -> None:
        self.tooltip = texto

    def set_text(self, t: str) -> None:
        self._text = t

    def set_markup(self, m: str) -> None:
        self._text = m


def _install_gi_stubs() -> None:
    # Se PyGObject real está disponível, não fazemos nada (integração real).
    # GATE-SKIP-MASK-01: a checagem antiga só valia se "gi" JÁ estivesse em
    # sys.modules — na coleta a fio frio o stub entrava mesmo com GTK real
    # instalado e envenenava o processo inteiro.
    existente = sys.modules.get("gi")
    if existente is None or getattr(existente, "__spec__", None) is not None:
        try:
            import gi

            gi.require_version("Gtk", "3.0")
            # CI-TYPELIB-PARCIAL-01: checar só o Gtk deixava passar um `gi`
            # PELA METADE. No runner do GitHub o Gtk importa e o Pango não
            # ("unknown location"), então este early-return dispensava os
            # stubs e o import de `triggers_actions` — que usa Pango —
            # estourava na COLETA, derrubando a suíte e reprovando o release.
            # A pergunta certa não é "existe gi?", é "existe TUDO o que o
            # módulo sob teste importa?".
            from gi.repository import GLib, Gtk, Pango  # noqa: F401

            return
        except Exception:  # pragma: no cover — ambientes sem GTK
            pass

    # Reutiliza módulos stub se já criados por testes anteriores (merge de atributos).
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

    # Registrar classes mínimas adicionais (idempotente: só adiciona se ausente).
    for cls_name in (
        "Builder", "Window", "Button", "ToggleButton", "ComboBoxText",
        "Switch", "TextView", "TextBuffer",
    ):
        if not hasattr(gtk_mod, cls_name):
            setattr(gtk_mod, cls_name, type(cls_name, (), {}))
    # Sempre sobrescrevemos estes com as fakes funcionais desta suite (não são placeholders).
    gtk_mod.Orientation = _Orientation  # type: ignore[attr-defined]
    gtk_mod.PositionType = _PositionType  # type: ignore[attr-defined]
    gtk_mod.Adjustment = _Adjustment  # type: ignore[attr-defined]
    gtk_mod.Box = _Box  # type: ignore[attr-defined]
    gtk_mod.Scale = _Scale  # type: ignore[attr-defined]
    gtk_mod.Label = _Label  # type: ignore[attr-defined]

    glib_mod.timeout_add = lambda *_a, **_kw: 0  # type: ignore[attr-defined]
    glib_mod.idle_add = lambda fn, *a, **kw: fn(*a, **kw)  # type: ignore[attr-defined]
    glib_mod.source_remove = lambda *_a, **_kw: None  # type: ignore[attr-defined]

    # `triggers_actions` importa Pango junto de Gtk/GLib; sem o stub o import
    # do módulo sob teste falha mesmo com os outros dois no lugar.
    pango_mod = sys.modules.get("gi.repository.Pango") or types.ModuleType(
        "gi.repository.Pango"
    )
    if not hasattr(pango_mod, "EllipsizeMode"):
        pango_mod.EllipsizeMode = type(  # type: ignore[attr-defined]
            "EllipsizeMode", (), {"NONE": 0, "START": 1, "MIDDLE": 2, "END": 3}
        )

    repo_mod.Gtk = gtk_mod  # type: ignore[attr-defined]
    repo_mod.GLib = glib_mod  # type: ignore[attr-defined]
    repo_mod.Pango = pango_mod  # type: ignore[attr-defined]

    sys.modules["gi"] = gi_mod
    sys.modules["gi.repository"] = repo_mod
    sys.modules["gi.repository.Gtk"] = gtk_mod
    sys.modules["gi.repository.GLib"] = glib_mod
    sys.modules["gi.repository.Pango"] = pango_mod


_install_gi_stubs()

from hefesto_dualsense4unix.app.actions import triggers_actions

# --- Fakes de widgets GTK ---------------------------------------------


class _FakeComboBox:
    def __init__(self, active_id: str | None = None) -> None:
        self._entries: list[tuple[str, str]] = []
        self._active_id: str | None = active_id
        self._visible = True

    def remove_all(self) -> None:
        self._entries.clear()

    def append(self, id_: str, label: str) -> None:
        self._entries.append((id_, label))

    def set_active_id(self, id_: str) -> None:
        self._active_id = id_

    def get_active_id(self) -> str | None:
        return self._active_id

    def get_visible(self) -> bool:
        return self._visible

    def set_visible(self, v: bool) -> None:
        self._visible = bool(v)


class _FakeSegmentedSelector:
    """Stub do SegmentedSelector (FEAT-DSX-COMBO-TO-SEGMENTED-01).

    Espelha o subconjunto da API por-ID usado pela aba Triggers — **inclusive
    a EMISSÃO** de "changed" em ``set_active_id``, que é a semântica do widget
    real (``app/widgets/segmented_selector.set_active_id``: emite quando o id
    muda, no-op quando não muda).

    MESA-CHEIA-08 (13/08): o corpo deste método era ``self._active_id = the_id``
    e nada mais. Com ele mudo, o teste do "Desligar" logo abaixo passava com o
    defeito de pé — o primeiro degrau da cadeia (o "changed" que agenda o
    live-preview de 300 ms) simplesmente não existia no dublê. **Um teste que
    passa com a cura arrancada não testa nada**, e este arquivo era o exemplo
    dessa regra.
    """

    def __init__(self, wrap: bool = False) -> None:
        self.wrap = wrap
        self._items: list[tuple[str, str]] = []
        self._active_id: str | None = None
        self._visible = True
        self.handlers: list[tuple[str, Any]] = []

    def set_items(self, items: list[tuple[str, str]]) -> None:
        self._items = list(items)

    def get_active_id(self) -> str | None:
        return self._active_id

    def set_active_id(self, the_id: str) -> None:
        if the_id == self._active_id:
            return  # no-op: o widget real só emite quando o id MUDA
        if all(iid != the_id for iid, _label in self._items):
            return  # id inexistente é no-op no widget real
        self._active_id = the_id
        for sinal, cb in list(self.handlers):
            if sinal == "changed":
                cb(self)

    def connect(self, signal: str, cb: Any) -> None:
        self.handlers.append((signal, cb))

    def show_all(self) -> None:
        pass

    def get_visible(self) -> bool:
        return self._visible

    def set_visible(self, v: bool) -> None:
        self._visible = bool(v)


class _Relogio:
    """O ``GLib.timeout_add`` que GUARDA o callback em vez de engoli-lo.

    MESA-CHEIA-08, mordida 2: o dublê era ``lambda *_a, **_kw: 0``, e o
    defeito do "Desligar" é TEMPORAL — acontece 300 ms depois do gesto, nunca
    na chamada. Com o relógio engolido, o teste olhava só o instante
    em que nada de errado acontece.

    ``source_remove`` tira o pendente do mapa: é assim que se distingue
    "cancelou o preview" de "o preview vai disparar e ninguém viu".
    """

    def __init__(self) -> None:
        self.pendentes: dict[int, tuple[Any, tuple[Any, ...]]] = {}
        self._ultimo = 0

    def timeout_add(self, _ms: int, cb: Any, *args: Any) -> int:
        self._ultimo += 1
        self.pendentes[self._ultimo] = (cb, args)
        return self._ultimo

    def source_remove(self, ident: int) -> None:
        self.pendentes.pop(ident, None)

    def disparar_pendentes(self) -> int:
        """Faz o tempo passar. Devolve quantos callbacks dispararam."""
        pendentes = list(self.pendentes.items())
        self.pendentes.clear()
        for _ident, (cb, args) in pendentes:
            cb(*args)
        return len(pendentes)


class _FakeStatusBar:
    def __init__(self) -> None:
        self.pushed: list[tuple[int, str]] = []
        self._ctr = 0

    def get_context_id(self, _k: str) -> int:
        self._ctr += 1
        return self._ctr

    def push(self, ctx: int, msg: str) -> None:
        self.pushed.append((ctx, msg))


def _mk_widgets() -> dict[str, Any]:
    # GATE-SKIP-MASK-01: fakes headless direto (nada de gi/sys.modules) —
    # um Gtk.Box REAL rejeitaria o _FakeSegmentedSelector no pack_start.
    widgets: dict[str, Any] = {}
    for side in ("left", "right"):
        # FEAT-DSX-COMBO-TO-SEGMENTED-01: o combo de modo virou um slot (GtkBox)
        # onde install_triggers_tab empacota o SegmentedSelector.
        widgets[f"trigger_{side}_mode_slot"] = _Box()
        widgets[f"trigger_{side}_desc"] = _Label()
        widgets[f"trigger_{side}_params_box"] = _Box()
        widgets[f"trigger_{side}_preset_combo"] = _FakeComboBox()
        widgets[f"trigger_{side}_preset_row"] = _Box()
    widgets["status_bar"] = _FakeStatusBar()
    return widgets


class _FakeTriggersMixin:
    # Herdado do mixin real (atributo de classe frozenset).
    _MODES_COM_PRESET = triggers_actions.TriggersActionsMixin._MODES_COM_PRESET

    def __init__(self) -> None:
        from hefesto_dualsense4unix.app.draft_config import DraftConfig

        self.draft = DraftConfig.default()
        # M1: guard renomeado por mixin (era _guard_refresh compartilhado).
        self._triggers_guard_refresh = False
        self._trigger_preset_applying = False
        self._trigger_param_widgets = {"left": {}, "right": {}}
        self._widgets = _mk_widgets()

    def _get(self, key: str) -> Any:
        return self._widgets.get(key)


def _build_mixin(monkeypatch: pytest.MonkeyPatch) -> _FakeTriggersMixin:
    calls: list[tuple[str, str, list[int]]] = []

    def fake_trigger_set(
        side: str, mode: str, params: list[int], uniq: str | None = None
    ) -> tuple[bool, str | None]:
        calls.append((side, mode, list(params)))
        return True, None

    monkeypatch.setattr(triggers_actions, "trigger_set_checked", fake_trigger_set)

    # R-19: o botão "Desligar" passou a usar `trigger.reset` (LIBERA a trava)
    # em vez de mandar outro `trigger.set` (que a RE-ARMAVA).
    # ABAS-06: o "Desligar" passou a levar o `uniq` do alvo, como o "Aplicar".
    resets: list[tuple[str | None, str | None]] = []

    def fake_trigger_reset(
        side: str | None = None, uniq: str | None = None
    ) -> tuple[bool, str | None]:
        resets.append((side, uniq))
        return True, None

    monkeypatch.setattr(triggers_actions, "trigger_reset", fake_trigger_reset)
    # FEAT-DSX-COMBO-TO-SEGMENTED-01: install_triggers_tab instancia o
    # SegmentedSelector real (precisa de display). Troca pelo stub headless.
    monkeypatch.setattr(
        triggers_actions, "SegmentedSelector", _FakeSegmentedSelector
    )
    # GATE-SKIP-MASK-01: em vez de envenenar sys.modules["gi"], trocamos os
    # bindings Gtk/GLib DO MÓDULO em teste pelos fakes headless. O
    # monkeypatch desfaz tudo no teardown — os demais testes do processo
    # seguem vendo o PyGObject real.
    monkeypatch.setattr(
        triggers_actions,
        "Gtk",
        types.SimpleNamespace(
            Orientation=_Orientation,
            PositionType=_PositionType,
            Adjustment=_Adjustment,
            Box=_Box,
            Scale=_Scale,
            Label=_Label,
        ),
    )
    relogio = _Relogio()
    monkeypatch.setattr(
        triggers_actions,
        "GLib",
        types.SimpleNamespace(
            timeout_add=relogio.timeout_add,
            idle_add=lambda fn, *a, **kw: fn(*a, **kw),
            source_remove=relogio.source_remove,
        ),
    )

    inst = _FakeTriggersMixin()
    inst._relogio = relogio  # type: ignore[attr-defined]
    inst._trigger_set_calls = calls  # type: ignore[attr-defined]
    inst._trigger_reset_calls = resets  # type: ignore[attr-defined]

    # Esta tupla é uma lista de nomes A MANTER À MÃO: o dublê copia UM A UM os
    # métodos reais do mixin. Esquecer um nome aqui, ou renomear o método no
    # fonte sem mexer aqui, quebra a suíte — e o modo de falha de cada descuido
    # é DIFERENTE. Medido nesta árvore em 14/08/2026, porque três agentes já
    # descreveram esta linha de três jeitos incompatíveis, cada um tendo rodado
    # um experimento diferente sem saber do outro:
    #
    #   nome FORA da tupla, método no fonte -> AttributeError no primeiro uso,
    #       dentro do código de produção (`triggers_actions.py`, no
    #       `_reset_trigger`). `_FakeTriggersMixin` não tem `__getattr__` e
    #       `_reset_trigger` não engole exceção: 6 failed, 26 passed.
    #   método FORA do fonte, nome na tupla -> KeyError aqui embaixo, no
    #       `__dict__[name]`, ainda na MONTAGEM do dublê — então cai todo teste
    #       que chama `_build_mixin`: 29 failed, 3 passed.
    #
    # Nenhum dos dois é silencioso, e é por isso que esta tupla não precisa de
    # portão próprio. A afirmação de que um descuido aqui "passaria por
    # AttributeError silencioso" foi medida e é FALSA — fica escrito para a
    # próxima pessoa não pagar a medição pela quarta vez.
    for name in (
        "install_triggers_tab",
        "_refresh_triggers_from_draft",
        "on_trigger_left_mode_changed",
        "on_trigger_right_mode_changed",
        "on_trigger_left_preset_changed",
        "on_trigger_right_preset_changed",
        "on_trigger_left_apply",
        "on_trigger_right_apply",
        "on_trigger_left_reset",
        "on_trigger_right_reset",
        "_on_mode_changed",
        "_on_preset_changed",
        "_update_preset_row_visibility",
        "_populate_preset_combo",
        "_on_param_slider_changed",
        "_update_preset_to_custom",
        "_persist_params_to_draft",
        "_rebuild_params",
        "_build_param_row",
        "_collect_values",
        "_apply_trigger",
        "_send_trigger_named",
        "_reset_trigger",
        "_toast_trigger",
        "_schedule_live_preview",
        "_cancelar_live_preview",
        "_adiantar_live_preview",
        "_fire_live_preview",
    ):
        setattr(
            inst,
            name,
            triggers_actions.TriggersActionsMixin.__dict__[name].__get__(
                inst, type(inst)
            ),
        )
    return inst


# --- Testes -----------------------------------------------------------


def test_install_triggers_tab_popula_combo_de_modos(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from hefesto_dualsense4unix.app.actions.trigger_specs import PRESETS

    mixin = _build_mixin(monkeypatch)
    mixin.install_triggers_tab()

    combo_left = mixin._trigger_mode["left"]
    assert combo_left.get_active_id() == "Off"
    assert len(combo_left._items) == len(PRESETS)
    # O handler "changed" foi conectado no código (não mais via Glade).
    assert any(sig == "changed" for sig, _cb in combo_left.handlers)


def test_on_trigger_mode_changed_atualiza_draft(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mixin = _build_mixin(monkeypatch)
    mixin.install_triggers_tab()
    combo = mixin._trigger_mode["left"]
    combo.set_active_id("Rigid")

    mixin.on_trigger_left_mode_changed(combo)

    assert mixin.draft.triggers.left.mode == "Rigid"
    # BUG-TRIGGERS-DRAFT-STALE-01: o draft já nasce com os defaults dos
    # sliders (antes gravava () — "Salvar Perfil" antes do live-preview
    # persistia o gatilho zerado). Rigid: position=5, force=200.
    assert mixin.draft.triggers.left.params == (5, 200)


def test_on_trigger_mode_changed_guard_refresh_noop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mixin = _build_mixin(monkeypatch)
    mixin.install_triggers_tab()
    mixin._triggers_guard_refresh = True
    combo = mixin._trigger_mode["left"]
    combo.set_active_id("Pulse")

    mixin.on_trigger_left_mode_changed(combo)

    # Draft não mudou porque guard estava ativo.
    assert mixin.draft.triggers.left.mode == "Off"


def test_apply_trigger_rigid_persiste_draft_e_chama_ipc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mixin = _build_mixin(monkeypatch)
    mixin.install_triggers_tab()
    combo = mixin._trigger_mode["left"]
    combo.set_active_id("Rigid")
    mixin.on_trigger_left_mode_changed(combo)

    # Forçar valores de sliders via _trigger_param_widgets.
    widgets = mixin._trigger_param_widgets["left"]
    widgets["position"].set_value(5)
    widgets["force"].set_value(200)

    mixin.on_trigger_left_apply(None)

    assert mixin._trigger_set_calls == [("left", "Rigid", [5, 200])]
    assert mixin.draft.triggers.left.mode == "Rigid"
    assert mixin.draft.triggers.left.params == (5, 200)


def test_apply_trigger_multi_position_feedback_envia_strengths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mixin = _build_mixin(monkeypatch)
    mixin.install_triggers_tab()
    combo = mixin._trigger_mode["right"]
    combo.set_active_id("MultiPositionFeedback")
    mixin.on_trigger_right_mode_changed(combo)

    widgets = mixin._trigger_param_widgets["right"]
    for i in range(10):
        widgets[f"pos_{i}"].set_value(i)

    mixin.on_trigger_right_apply(None)

    assert len(mixin._trigger_set_calls) == 1
    side, mode, params = mixin._trigger_set_calls[0]
    assert side == "right"
    assert mode == "MultiPositionFeedback"
    # Envia lista de 10 strengths (pos_0..pos_9).
    assert params == [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
    # BUG-TRIGGER-FLAT-MULTIPOS-01: o draft TAMBÉM precisa guardar a lista plana
    # (antes gravava () -> perda silenciosa ao salvar/aplicar perfil).
    assert mixin.draft.triggers.right.mode == "MultiPositionFeedback"
    assert mixin.draft.triggers.right.params == (0, 1, 2, 3, 4, 5, 6, 7, 8, 9)


def test_reset_trigger_envia_off(monkeypatch: pytest.MonkeyPatch) -> None:
    mixin = _build_mixin(monkeypatch)
    mixin.install_triggers_tab()
    combo = mixin._trigger_mode["left"]
    combo.set_active_id("Rigid")

    mixin.on_trigger_left_reset(None)

    assert combo.get_active_id() == "Off"
    # R-19: o "Desligar" tem de LIBERAR a trava manual, não re-armá-la. Antes
    # ele mandava `trigger.set` modo "Off", e `trigger.set` arma
    # `mark_manual_trigger_active` — o botão de "voltar ao normal" era mais um
    # jeito de PAUSAR a troca automática de perfil, sem nada dizendo isso.
    assert mixin._trigger_reset_calls == [("left", None)]
    assert mixin._trigger_set_calls == [], (
        "trigger.set aqui re-armaria a trava que o botão deveria soltar"
    )


def test_o_desligar_nao_re_arma_a_trava_300ms_depois(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MESA-CHEIA-08 (13/08) — a R-19 estava DESFEITA, e por um caminho novo.

    O "Desligar" solta a trava (`trigger.reset`) e, 300 ms depois, o
    live-preview que o próprio gesto agendou mandava um `trigger.set` que a
    RE-ARMAVA. Ela sente isso como *"a config que eu deixo não fica"*: o
    perfil não volta a trocar sozinho depois do botão que promete "voltar ao
    normal", e nada na tela diz por quê.

    A cadeia inteira, com os dois degraus que o dublê antigo apagava:
    `set_active_id("Off")` EMITE "changed" -> `_on_mode_changed` agenda
    `_fire_live_preview` -> 300 ms -> `trigger.set`.
    """
    mixin = _build_mixin(monkeypatch)
    mixin.install_triggers_tab()
    combo = mixin._trigger_mode["left"]

    # O caso que dói é o normal: aplicar "Rígido" e depois "Desligar".
    combo.set_active_id("Rigid")
    mixin._relogio.disparar_pendentes()  # o preview do "Rígido" aplica
    assert mixin._trigger_set_calls, "o live-preview é feature pedida"
    mixin._trigger_set_calls.clear()

    mixin.on_trigger_left_reset(None)
    assert mixin._trigger_reset_calls == [("left", None)]
    # O tempo passa. É AQUI que o defeito acontecia.
    disparados = mixin._relogio.disparar_pendentes()

    assert disparados == 0, (
        "o «Desligar» deixou um live-preview pendente — ele vira um "
        "trigger.set 300 ms depois"
    )
    assert mixin._trigger_set_calls == [], (
        "trigger.set depois do trigger.reset RE-ARMA a trava manual que o "
        "botão existe para soltar"
    )


def test_trocar_de_modo_pelo_gesto_normal_continua_aplicando(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MORDIDA 3 — o caso que NÃO deve mudar.

    Matar o live-preview inteiro "resolveria" o defeito acima e quebraria a
    feature: hipótese tem de explicar o que JÁ funcionava.
    """
    mixin = _build_mixin(monkeypatch)
    mixin.install_triggers_tab()
    combo = mixin._trigger_mode["right"]

    combo.set_active_id("Rigid")
    assert mixin._relogio.disparar_pendentes() == 1
    assert [modo for _lado, modo, _p in mixin._trigger_set_calls] == ["Rigid"]


def _espiar_ordem(
    monkeypatch: pytest.MonkeyPatch,
) -> list[str]:
    """Registra a ORDEM real entre `trigger.set` e `trigger.reset`.

    As duas listas do `_build_mixin` são separadas, então "quem saiu antes"
    não dá para ler nelas. Aqui embrulhamos os dois dublês já instalados —
    o que se mede é a sequência que o daemon veria no socket.
    """
    ordem: list[str] = []
    set_instalado = triggers_actions.trigger_set_checked
    reset_instalado = triggers_actions.trigger_reset

    def espia_set(*a: Any, **kw: Any) -> Any:
        ordem.append("set")
        return set_instalado(*a, **kw)

    def espia_reset(*a: Any, **kw: Any) -> Any:
        ordem.append("reset")
        return reset_instalado(*a, **kw)

    monkeypatch.setattr(triggers_actions, "trigger_set_checked", espia_set)
    monkeypatch.setattr(triggers_actions, "trigger_reset", espia_reset)
    return ordem


def test_o_desligar_de_um_lado_nao_deixa_o_outro_re_armar_a_trava(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FURO RESIDUAL da MESA-CHEIA-08, medido no ceticismo e curado em 14/08.

    `_cancelar_live_preview` mata só o lado do botão, mas a trava manual **não
    tem lado**: `daemon/state_store.mark_manual_trigger_active` recebe uma
    categoria só ("trigger") para os dois gatilhos. Então mexer no modo do
    gatilho DIREITO e, dentro de 300 ms, clicar "Desligar" no ESQUERDO deixava
    o `trigger.set` da direita cair DEPOIS do `trigger.reset` da esquerda — e
    re-armar a trava que o botão existe para soltar. Medido antes da cura::

        disparados: 1  trigger.set: [('right', 'Rigid', [5, 200])]

    É o mesmo dano da sprint por uma janela mais estreita: dois gestos em
    lados diferentes dentro dos 300 ms.

    A cura ADIANTA o preview do outro lado em vez de cancelá-lo — o que este
    teste mede é a ORDEM: o `set` da direita sai ANTES do `reset` da esquerda,
    e nada sobra pendente para depois.
    """
    mixin = _build_mixin(monkeypatch)
    mixin.install_triggers_tab()
    ordem = _espiar_ordem(monkeypatch)

    # A usuária mexe no gatilho DIREITO...
    mixin._trigger_mode["right"].set_active_id("Rigid")
    # ...e, antes dos 300 ms, clica "Desligar" no ESQUERDO.
    mixin.on_trigger_left_reset(None)

    assert mixin._trigger_reset_calls == [("left", None)]
    assert ordem == ["set", "reset"], (
        "o trigger.set do outro gatilho caiu DEPOIS do trigger.reset e "
        "re-armou a trava manual, que é uma só para os dois lados"
    )
    assert mixin._relogio.disparar_pendentes() == 0, (
        "sobrou live-preview pendente depois do «Desligar»"
    )


def test_o_desligar_de_um_lado_nao_engole_o_preview_do_outro(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O caso que NÃO deve mudar, do furo do outro lado (14/08).

    Cancelar o preview do gatilho oposto "resolveria" o furo acima matando uma
    aplicação que ela pediu, num gatilho que ela não mandou desligar — o mesmo
    contorno que a mordida 3 da sprint já proíbe para o próprio lado. O
    `trigger.set` da direita tem de acontecer, com os bytes que ela escolheu.
    """
    mixin = _build_mixin(monkeypatch)
    mixin.install_triggers_tab()

    mixin._trigger_mode["right"].set_active_id("Rigid")
    mixin.on_trigger_left_reset(None)

    assert [(lado, modo) for lado, modo, _p in mixin._trigger_set_calls] == [
        ("right", "Rigid")
    ], "o preview do gatilho que ela NÃO desligou foi engolido"
    assert mixin._trigger_set_calls[0][2], (
        "o preview adiantado tem de levar os mesmos params do preview atrasado"
    )


def test_o_desligado_do_seletor_ainda_manda_trigger_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RETRATO, não cura — o furo B da MESA-CHEIA-08, aberto para ela decidir.

    A aba tem DOIS gestos que apagam o gatilho e parecem o mesmo: o botão
    «Desligar» (`trigger.reset`, SOLTA a trava) e o botão «Desligado» do
    seletor de modos (`app/actions/trigger_specs.py:83` — id "Off", rótulo
    "Desligado"), que passa pelo live-preview e manda `trigger.set` "Off" —
    e `trigger.set` ARMA a trava (`daemon/ipc_handlers._handle_trigger_set`).
    Medido nesta árvore::

        disparados: 1  trigger.set: [('left', 'Off', [])]  trigger.reset: []

    **Isto não é bug declarado.** "Desligado" é um modo como os outros, e a
    trava armada é coerente com "ela escolheu isto à mão"; o botão «Desligar»
    é que existe para soltar (R-19). Mas os dois rótulos prometem a mesma
    coisa na tela, e qual dos dois deve soltar a trava é decisão dela.

    Registrado em `docs/process/sprints/2026-08-13-MESA-CHEIA-08-...md`,
    seção 6. Este teste **não morde** — não há cura a arrancar. Ele fixa o
    comportamento de hoje para que a mudança, quando ela decidir, seja
    deliberada e não um efeito colateral.
    """
    mixin = _build_mixin(monkeypatch)
    mixin.install_triggers_tab()
    combo = mixin._trigger_mode["left"]

    combo.set_active_id("Rigid")
    mixin._relogio.disparar_pendentes()
    mixin._trigger_set_calls.clear()

    combo.set_active_id("Off")  # o botão «Desligado» do seletor segmentado

    assert mixin._relogio.disparar_pendentes() == 1
    assert mixin._trigger_set_calls == [("left", "Off", [])]
    assert mixin._trigger_reset_calls == [], (
        "o «Desligado» do seletor não passa pelo trigger.reset — é o furo B"
    )


def test_desligar_com_o_modo_ja_em_off_nao_muda_nada(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MORDIDA 4 — a ressalva honesta, registrada para ninguém "consertá-la".

    Com o modo já em "Off" o `set_active_id` é no-op (o widget real só emite
    quando o id MUDA), então não há "changed", não há timer e não havia
    re-arme nem antes nem depois.
    """
    mixin = _build_mixin(monkeypatch)
    mixin.install_triggers_tab()
    combo = mixin._trigger_mode["left"]
    assert combo.get_active_id() == "Off"

    mixin.on_trigger_left_reset(None)

    assert mixin._relogio.disparar_pendentes() == 0
    assert mixin._trigger_set_calls == []
    assert mixin._trigger_reset_calls == [("left", None)]


def test_reset_trigger_leva_o_controle_escolhido(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ABAS-06 (25/07) — "Desligar" era o último comando da janela em broadcast.

    Com "Controle 2" selecionado no seletor do banner, o "Aplicar" ao lado
    mandava o MAC (PERFIL-05) e o "Desligar" não — então ele zerava o gatilho
    dos QUATRO controles. O mesmo defeito já tinha sido corrigido no "Apagar"
    da aba Lightbar (R-17) e não fora replicado aqui.
    """
    mixin = _build_mixin(monkeypatch)
    mixin.install_triggers_tab()
    # É o que o seletor do banner mantém (StatusActionsMixin._edit_target_uniq,
    # lido pelo `_edit_uniq` que os dois botões da aba consultam).
    mixin._edit_target_uniq = "aabbcc000002"  # type: ignore[attr-defined]
    mixin._edit_uniq = lambda: mixin._edit_target_uniq  # type: ignore[attr-defined]

    mixin.on_trigger_right_reset(None)

    assert mixin._trigger_reset_calls == [("right", "aabbcc000002")], (
        "sem o MAC, desligar o gatilho de UM controle desligava o dos quatro"
    )


def test_on_preset_changed_feedback_popula_sliders(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Seleção de preset posicional preenche sliders com valores do preset."""
    mixin = _build_mixin(monkeypatch)
    mixin.install_triggers_tab()

    mode_combo = mixin._trigger_mode["left"]
    mode_combo.set_active_id("MultiPositionFeedback")
    mixin.on_trigger_left_mode_changed(mode_combo)

    preset_combo = mixin._widgets["trigger_left_preset_combo"]
    preset_combo.set_active_id("rampa_crescente")

    mixin.on_trigger_left_preset_changed(preset_combo)

    # Pelo menos um slider foi alterado (valor != 0 em pos_0).
    widgets = mixin._trigger_param_widgets["left"]
    assert any(widgets[f"pos_{i}"].get_value() > 0 for i in range(10))


def test_on_preset_changed_custom_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    """Preset 'custom' não altera sliders."""
    mixin = _build_mixin(monkeypatch)
    mixin.install_triggers_tab()
    mode_combo = mixin._trigger_mode["left"]
    mode_combo.set_active_id("MultiPositionFeedback")
    mixin.on_trigger_left_mode_changed(mode_combo)

    widgets = mixin._trigger_param_widgets["left"]
    for i in range(10):
        widgets[f"pos_{i}"].set_value(0)

    preset_combo = mixin._widgets["trigger_left_preset_combo"]
    preset_combo.set_active_id("custom")
    mixin.on_trigger_left_preset_changed(preset_combo)

    # Todos continuam 0.
    for i in range(10):
        assert widgets[f"pos_{i}"].get_value() == 0


def test_collect_values_extrai_dict_de_sliders(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mixin = _build_mixin(monkeypatch)
    mixin.install_triggers_tab()
    mode_combo = mixin._trigger_mode["left"]
    mode_combo.set_active_id("Rigid")
    mixin.on_trigger_left_mode_changed(mode_combo)

    widgets = mixin._trigger_param_widgets["left"]
    widgets["position"].set_value(3)
    widgets["force"].set_value(150)

    result = mixin._collect_values("left")
    assert result == {"position": 3, "force": 150}


def test_refresh_triggers_from_draft_sincroniza_widgets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Draft contendo modo Rigid propaga para combo + rebuild sliders."""
    mixin = _build_mixin(monkeypatch)
    mixin.install_triggers_tab()

    from hefesto_dualsense4unix.app.draft_config import TriggerDraft, TriggersDraft
    new_triggers = TriggersDraft(
        left=TriggerDraft(mode="Rigid", params=(4, 180)),
    )
    mixin.draft = mixin.draft.model_copy(update={"triggers": new_triggers})

    mixin._refresh_triggers_from_draft()

    combo = mixin._trigger_mode["left"]
    assert combo.get_active_id() == "Rigid"
    widgets = mixin._trigger_param_widgets["left"]
    assert widgets["position"].get_value() == 4
    assert widgets["force"].get_value() == 180


def test_apply_trigger_custom_envia_mode_e_forces(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mixin = _build_mixin(monkeypatch)
    mixin.install_triggers_tab()
    combo = mixin._trigger_mode["right"]
    combo.set_active_id("Custom")
    mixin.on_trigger_right_mode_changed(combo)

    widgets = mixin._trigger_param_widgets["right"]
    widgets["mode"].set_value(2)
    for i in range(7):
        widgets[f"force_{i}"].set_value(10 + i)

    mixin.on_trigger_right_apply(None)

    assert len(mixin._trigger_set_calls) == 1
    side, mode, params = mixin._trigger_set_calls[0]
    assert side == "right"
    assert mode == "Custom"
    # [mode, force_0..force_6] = [2, 10, 11, 12, 13, 14, 15, 16]
    assert params == [2, 10, 11, 12, 13, 14, 15, 16]


# ---------------------------------------------------------------------------
# UI-TRIGGERS-LIVE-PREVIEW-01 — debounce + apply imediato no combobox change
# ---------------------------------------------------------------------------


def test_on_mode_changed_agenda_live_preview(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Trocar o combobox de modo agenda `_apply_trigger` via debounce 300ms."""
    mixin = _build_mixin(monkeypatch)
    mixin.install_triggers_tab()

    agendados: list[tuple[int, Any, str]] = []

    def fake_timeout_add(
        interval: int, fn: Any, *args: Any, **_kw: Any
    ) -> int:
        agendados.append((interval, fn, args[0] if args else ""))
        return 42  # handle fictício

    monkeypatch.setattr(triggers_actions.GLib, "timeout_add", fake_timeout_add)

    combo = mixin._trigger_mode["left"]
    combo.set_active_id("Pulse")
    mixin.on_trigger_left_mode_changed(combo)

    assert agendados, "live preview não agendou GLib.timeout_add"
    interval, fn, side = agendados[0]
    assert interval == 300
    assert side == "left"
    assert callable(fn)


def test_schedule_live_preview_cancela_pendente(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Trocas rápidas devem cancelar o timer anterior antes de agendar novo."""
    mixin = _build_mixin(monkeypatch)
    mixin.install_triggers_tab()
    removidos: list[int] = []

    def fake_remove(handle: int) -> None:
        removidos.append(handle)

    monkeypatch.setattr(triggers_actions.GLib, "source_remove", fake_remove)
    monkeypatch.setattr(
        triggers_actions.GLib,
        "timeout_add",
        lambda *_a, **_kw: 99,
    )

    # Primeira agendagem grava handle 99.
    mixin._schedule_live_preview("left")
    assert mixin._trigger_live_preview_timer["left"] == 99
    # Segunda agendagem deve cancelar o handle anterior (99).
    mixin._schedule_live_preview("left")
    assert 99 in removidos


def test_fire_live_preview_aplica_e_zera_timer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`_fire_live_preview` chama `_apply_trigger` e zera o handle."""
    mixin = _build_mixin(monkeypatch)
    mixin.install_triggers_tab()
    mixin._trigger_live_preview_timer["right"] = 77

    combo = mixin._trigger_mode["right"]
    combo.set_active_id("Rigid")
    mixin.on_trigger_right_mode_changed(combo)
    # _on_mode_changed dispara _schedule_live_preview que zera handle local
    # ao agendar; o teste foca o _fire_live_preview standalone.
    mixin._trigger_live_preview_timer["right"] = 77
    mixin._fire_live_preview("right")

    assert mixin._trigger_live_preview_timer["right"] == 0
    assert any(call[0] == "right" for call in mixin._trigger_set_calls)


# ---------------------------------------------------------------------------
# BUG-TRIGGERS-PRESET-DUP-01 — seletor de preset sem "Personalizar" duplicado
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("mode_id", ["MultiPositionFeedback", "MultiPositionVibration"])
def test_populate_preset_combo_sem_duplicar_personalizar(
    monkeypatch: pytest.MonkeyPatch, mode_id: str
) -> None:
    """Os dicts de labels JÁ trazem "custom"; o combo não pode duplicá-lo."""
    from hefesto_dualsense4unix.profiles.trigger_presets import (
        FEEDBACK_POSITION_LABELS,
        VIBRATION_POSITION_LABELS,
    )

    labels = (
        FEEDBACK_POSITION_LABELS
        if mode_id == "MultiPositionFeedback"
        else VIBRATION_POSITION_LABELS
    )
    mixin = _build_mixin(monkeypatch)
    mixin.install_triggers_tab()

    mixin._populate_preset_combo("left", mode_id)

    items = mixin._trigger_preset["left"]._items
    ids = [key for key, _label in items]
    # Exatamente uma entrada "custom", sempre por último (UX: Personalizar no fim).
    assert ids.count("custom") == 1
    assert ids[-1] == "custom"
    assert len(items) == len(labels)


# ---------------------------------------------------------------------------
# BUG-TRIGGERS-DRAFT-STALE-01 — slider/preset atualizam o draft (rodapé salva
# o que a usuária vê/sente) + agendam o live-preview
# ---------------------------------------------------------------------------


def test_slider_atualiza_draft_e_agenda_live_preview(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mexer num slider grava os params correntes no draft e agenda o preview."""
    mixin = _build_mixin(monkeypatch)
    mixin.install_triggers_tab()

    agendados: list[tuple[int, str]] = []
    monkeypatch.setattr(
        triggers_actions.GLib,
        "timeout_add",
        lambda interval, _fn, *args, **_kw: (
            agendados.append((interval, args[0] if args else "")) or 7
        ),
    )

    combo = mixin._trigger_mode["left"]
    combo.set_active_id("Rigid")
    mixin.on_trigger_left_mode_changed(combo)
    agendados.clear()  # descarta o preview do mode-changed; foco é o do slider

    widgets = mixin._trigger_param_widgets["left"]
    widgets["position"].set_value(7)
    # O stub de Gtk.Scale não emite "value-changed"; invoca o handler à mão
    # (é o que o sinal real dispara via _rebuild_params).
    mixin._on_param_slider_changed("left")

    assert mixin.draft.triggers.left.mode == "Rigid"
    assert mixin.draft.triggers.left.params == (7, 200)
    assert agendados == [(300, "left")]


def test_slider_durante_refresh_nao_grava_draft(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Refresh programático (guard ativo) não pode reescrever o draft."""
    mixin = _build_mixin(monkeypatch)
    mixin.install_triggers_tab()

    combo = mixin._trigger_mode["left"]
    combo.set_active_id("Rigid")
    mixin.on_trigger_left_mode_changed(combo)
    draft_antes = mixin.draft

    mixin._triggers_guard_refresh = True
    try:
        mixin._trigger_param_widgets["left"]["position"].set_value(9)
        mixin._on_param_slider_changed("left")
    finally:
        mixin._triggers_guard_refresh = False

    assert mixin.draft is draft_antes


def test_preset_changed_atualiza_draft_e_agenda_preview(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Escolher um preset posicional persiste os valores no draft + preview."""
    from hefesto_dualsense4unix.profiles.trigger_presets import (
        FEEDBACK_POSITION_PRESETS,
    )

    mixin = _build_mixin(monkeypatch)
    mixin.install_triggers_tab()

    agendados: list[tuple[int, str]] = []
    monkeypatch.setattr(
        triggers_actions.GLib,
        "timeout_add",
        lambda interval, _fn, *args, **_kw: (
            agendados.append((interval, args[0] if args else "")) or 7
        ),
    )

    mode_combo = mixin._trigger_mode["left"]
    mode_combo.set_active_id("MultiPositionFeedback")
    mixin.on_trigger_left_mode_changed(mode_combo)
    agendados.clear()

    preset_combo = mixin._widgets["trigger_left_preset_combo"]
    preset_combo.set_active_id("rampa_crescente")
    mixin.on_trigger_left_preset_changed(preset_combo)

    esperado = tuple(FEEDBACK_POSITION_PRESETS["rampa_crescente"])
    assert mixin.draft.triggers.left.mode == "MultiPositionFeedback"
    assert mixin.draft.triggers.left.params == esperado
    assert (300, "left") in agendados


# --- HARM-19: erro de validação explica o erro, não acusa o daemon ------


def _mensagem_real_do_daemon(mode: str, params: list[int]) -> str:
    """Mensagem que o daemon devolve ao recusar `params` (CODE_INVALID_PARAMS).

    Vem do `build_from_name` de verdade — é o que o `_handle_trigger_set` chama
    e o `ipc_server` converte em erro JSON-RPC. Assim o teste prova a
    COEXISTÊNCIA (o texto do daemon casa com o tradutor da aba), não a fantasia
    do teste sobre esse texto.
    """
    from hefesto_dualsense4unix.core.trigger_effects import build_from_name

    with pytest.raises(ValueError) as exc:
        build_from_name(mode, params)
    return str(exc.value)


def test_humanizar_erro_de_ordem_usa_os_rotulos_dos_sliders() -> None:
    from hefesto_dualsense4unix.app.actions.trigger_specs import get_spec

    motivo = _mensagem_real_do_daemon("Bow", [5, 3, 4, 4])
    texto = triggers_actions.humanizar_erro_gatilho(motivo, get_spec("Bow"))

    assert texto == "Fim (3) precisa ser maior que Início (5)"


def test_humanizar_erro_de_faixa_usa_os_rotulos_dos_sliders() -> None:
    from hefesto_dualsense4unix.app.actions.trigger_specs import get_spec

    motivo = _mensagem_real_do_daemon("Rigid", [5, 300])
    texto = triggers_actions.humanizar_erro_gatilho(motivo, get_spec("Rigid"))

    assert texto == "Força precisa estar entre 0 e 255 (você pediu 300)"


def test_humanizar_mensagem_desconhecida_devolve_none() -> None:
    assert triggers_actions.humanizar_erro_gatilho("pane geral", None) is None


def test_toast_de_validacao_explica_e_nao_culpa_o_daemon(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HARM-19: com o daemon VIVO recusando (Fim <= Início), o toast dizia
    "falhou (daemon offline?)" — mandava a usuária caçar o problema no lugar
    errado."""
    mixin = _build_mixin(monkeypatch)
    motivo = _mensagem_real_do_daemon("Bow", [5, 3, 4, 4])
    monkeypatch.setattr(
        triggers_actions,
        "trigger_set_checked",
        lambda *_a, **_kw: (False, motivo),
    )
    mixin.install_triggers_tab()
    combo = mixin._trigger_mode["left"]
    combo.set_active_id("Bow")
    mixin.on_trigger_left_mode_changed(combo)
    widgets = mixin._trigger_param_widgets["left"]
    widgets["start"].set_value(5)
    widgets["end"].set_value(3)

    mixin.on_trigger_left_apply(None)

    _ctx, msg = mixin._widgets["status_bar"].pushed[-1]
    assert msg == (
        "Gatilho esquerdo (L2): Bow não aplicado — "
        "Fim (3) precisa ser maior que Início (5)"
    )
    assert "daemon" not in msg


def test_toast_de_daemon_offline_aponta_para_a_aba_sistema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sem motivo = ninguém respondeu; JARG-01: em vez de "daemon offline?",
    o leigo é mandado ligar o Hefesto na aba Sistema."""
    mixin = _build_mixin(monkeypatch)
    monkeypatch.setattr(
        triggers_actions, "trigger_set_checked", lambda *_a, **_kw: (False, None)
    )
    mixin.install_triggers_tab()
    combo = mixin._trigger_mode["left"]
    combo.set_active_id("Rigid")
    mixin.on_trigger_left_mode_changed(combo)

    mixin.on_trigger_left_apply(None)

    _ctx, msg = mixin._widgets["status_bar"].pushed[-1]
    assert msg == (
        "Gatilho esquerdo (L2): não consegui aplicar Rigid — o Hefesto pode "
        "estar desligado (ligue na aba Sistema)"
    )


def test_toast_de_motivo_desconhecido_mostra_o_texto_cru(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Texto cru do daemon ainda diz mais que "offline?" — nunca cair no ramo
    errado por não reconhecer o formato."""
    mixin = _build_mixin(monkeypatch)
    monkeypatch.setattr(
        triggers_actions,
        "trigger_set_checked",
        lambda *_a, **_kw: (False, "formato novo de recusa"),
    )
    mixin.install_triggers_tab()
    combo = mixin._trigger_mode["left"]
    combo.set_active_id("Rigid")
    mixin.on_trigger_left_mode_changed(combo)

    mixin.on_trigger_left_apply(None)

    _ctx, msg = mixin._widgets["status_bar"].pushed[-1]
    assert msg == "Gatilho esquerdo (L2): Rigid não aplicado — formato novo de recusa"
