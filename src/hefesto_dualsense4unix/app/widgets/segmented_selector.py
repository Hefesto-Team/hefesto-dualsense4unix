"""segmented_selector.py — botões segmentados sempre visíveis (sem popup).

FEAT-DSX-COMBO-TO-SEGMENTED-01: substitui ``GtkComboBox``/``GtkComboBoxText`` na
COSMIC, onde o cosmic-comp rouba o foco no clique e FECHA o popup do combo na
hora (bug do compositor — cosmic-epoch#2497 / pop#3660). Botões sempre visíveis
(sem popup/grab GTK) são imunes: a usuária consegue escolher.

O widget espelha o subconjunto da API por-ID do ``GtkComboBoxText`` usado pelo
app, para os call sites trocarem o combo por ele sem mudar a lógica:

  - ``set_items(items)``    — lista de ``(id, label)``; reconstrói os botões,
    preservando o id ativo se ele ainda existir. Idempotente: não reconstrói se
    os itens forem idênticos aos atuais.
  - ``get_active_id() -> str | None``
  - ``set_active_id(id)``   — ativa o botão do id e EMITE ``"changed"`` (igual ao
    ``GtkComboBox.set_active_id``); só emite quando o id realmente muda. Um guard
    interno evita loop ao marcar/desmarcar os outros botões do grupo.
  - ``connect("changed", cb)`` — sinal GObject nativo; ``cb`` recebe o widget
    como 1º argumento (como o handler de ``GtkComboBox::changed``).

A lógica por-ID vive em ``_SegmentedLogic`` (puro Python, sem GTK — testável sem
display). A classe concreta apenas implementa os 3 hooks que tocam o toolkit
(criar botões, ativar um botão, emitir o sinal). Como ``button_glyph`` e
``stick_preview_gtk``, há uma variante real (subclasse de ``Gtk.Box``) quando o
GTK está disponível e um stub puro caso contrário (testes/CI sem PyGObject).
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any, ClassVar


class _SegmentedLogic:
    """Lógica por-ID compartilhada (sem GTK).

    Mantém ``_items`` e ``_active_id`` e implementa a semântica do combo
    (set_items idempotente + preserva ativo; set_active_id só emite na mudança).
    Subclasses fornecem os hooks ``_create_buttons``/``_activate_button``/
    ``_emit_changed`` que tocam o toolkit.
    """

    _wrap: bool
    _items: list[tuple[str, str]]
    _active_id: str | None
    _updating: bool

    def _init_logic(self, wrap: bool) -> None:
        self._wrap = wrap
        self._items = []
        self._active_id = None
        # Guard: True enquanto marcamos botões programaticamente, para o handler
        # "toggled" não reemitir "changed" nem entrar em loop.
        self._updating = False

    # ---- API por-ID (espelha o GtkComboBoxText) ----

    def set_items(self, items: list[tuple[str, str]]) -> None:
        """Reconstrói os botões a partir de ``[(id, label), ...]``.

        Idempotente: se ``items`` for igual aos itens atuais, não faz nada. O id
        ativo é preservado se ainda existir na nova lista; caso contrário fica
        ``None``. NÃO emite "changed" (espelha o append/remove do combo, que só
        emite no ``set_active_id``).
        """
        items = list(items)
        if items == self._items:
            return
        prev_active = self._active_id
        self._items = items
        self._create_buttons(items)
        keep = prev_active if self._index_of(items, prev_active) is not None else None
        self._active_id = None
        if keep is not None:
            idx = self._index_of(items, keep)
            if idx is not None:
                self._activate_button(idx)
                self._active_id = keep

    def get_active_id(self) -> str | None:
        """Id do item ativo, ou ``None`` (espelha ``GtkComboBox.get_active_id``)."""
        return self._active_id

    def set_active_id(self, the_id: str) -> None:
        """Ativa o botão do id e EMITE "changed" (igual ao ``GtkComboBox``).

        Só emite quando o id efetivamente muda — ids inexistentes ou iguais ao
        ativo são no-op (mesma semântica do combo).
        """
        idx = self._index_of(self._items, the_id)
        if idx is None:
            return
        if the_id == self._active_id:
            return
        self._activate_button(idx)
        self._active_id = the_id
        self._emit_changed()

    @staticmethod
    def _index_of(items: list[tuple[str, str]], the_id: str | None) -> int | None:
        """Índice do id na lista de itens, ou ``None`` se ausente."""
        if the_id is None:
            return None
        for i, (iid, _label) in enumerate(items):
            if iid == the_id:
                return i
        return None

    # ---- hooks (implementados pela classe concreta) ----

    def _create_buttons(self, items: list[tuple[str, str]]) -> None:
        raise NotImplementedError

    def _activate_button(self, idx: int) -> None:
        raise NotImplementedError

    def _emit_changed(self) -> None:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Resolução condicional de GTK (mesmo padrão de stick_preview_gtk/button_glyph)
# ---------------------------------------------------------------------------

try:
    import gi

    gi.require_version("Gtk", "3.0")
    from gi.repository import GObject, Gtk

    _GTK_DISPONIVEL = True
except (ImportError, ValueError):
    _GTK_DISPONIVEL = False


if _GTK_DISPONIVEL:
    # RUN_FIRST tem valor 1; o getattr tolera um GObject stubado sem SignalFlags.
    _RUN_FIRST = getattr(getattr(GObject, "SignalFlags", None), "RUN_FIRST", 1)

    class SegmentedSelector(_SegmentedLogic, Gtk.Box):  # type: ignore[misc]
        """Grupo de ``GtkRadioButton`` em modo toggle, com a API por-ID do combo."""

        # Espelha GtkComboBox::changed: sem argumentos; o handler lê
        # get_active_id() para descobrir o novo valor.
        __gsignals__: ClassVar[dict[str, tuple[Any, ...]]] = {
            "changed": (_RUN_FIRST, None, ()),
        }

        def __init__(self, wrap: bool = False) -> None:
            Gtk.Box.__init__(
                self, orientation=Gtk.Orientation.VERTICAL, spacing=0
            )
            self._init_logic(wrap)
            self._buttons: list[Gtk.RadioButton] = []
            # Founder OCULTO do grupo de rádio (ver _create_buttons): permite que
            # TODOS os botões visíveis fiquem inativos ao mesmo tempo (estado
            # _active_id=None visualmente fiel ao GtkComboBox com active=-1).
            self._group_founder: Gtk.RadioButton | None = None
            self.set_valign(Gtk.Align.CENTER)
            if wrap:
                flow = Gtk.FlowBox()
                flow.set_selection_mode(Gtk.SelectionMode.NONE)
                # UX-TRIGGERS-COMPACT-01: teto de 3 por linha + botões compactos
                # (classe CSS) — os 19 modos viravam um paredão de 2 colunas de
                # botões ENORMES que engolia a aba inteira e empurrava sliders/
                # Aplicar para fora da dobra (visto ao vivo 2026-07-13). Com 3
                # colunas compactas a grade cabe em ~7 linhas curtas.
                flow.set_max_children_per_line(3)
                flow.set_min_children_per_line(1)
                flow.set_homogeneous(True)
                flow.set_row_spacing(2)
                flow.set_column_spacing(2)
                self.get_style_context().add_class("hefesto-segmented-compact")
                # M2: com min_children_per_line=1 e 19 botões de rótulo largo, o
                # FlowBox exige a largura do botão mais largo como mínimo; sob o
                # scroller-pai da aba Gatilhos (hscroll=NEVER) isso estoura em
                # `Gtk-WARNING: Negative content width` + coluna larga. Envolver o
                # FlowBox num ScrolledWindow (h=AUTOMATIC, v=NEVER) dá a largura de
                # referência: o ScrolledWindow reporta mínimo pequeno, então o
                # FlowBox NUNCA é alocado com largura negativa (rola em vez disso).
                # propagate_natural_height mantém a altura natural (sem cortar).
                scroller = Gtk.ScrolledWindow()
                scroller.set_policy(
                    Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER
                )
                scroller.set_propagate_natural_height(True)
                scroller.add(flow)
                self._container: Any = flow
                self.pack_start(scroller, True, True, 0)
            else:
                self.get_style_context().add_class("linked")
                self._container = self

        # ---- hooks GTK ----

        def _create_buttons(self, items: list[tuple[str, str]]) -> None:
            """Destrói os botões atuais e cria um GtkRadioButton por item.

            Usa um founder OCULTO do grupo (nunca empacotado no container): sem
            ele, ``new_with_label_from_widget`` faria o PRIMEIRO botão visível
            nascer ATIVO, divergindo de ``_active_id=None`` e tornando o item
            default inalcançável por clique (clicar um rádio já-ativo não dispara
            "toggled"). Com o founder oculto segurando o estado ativo inicial,
            TODOS os botões visíveis começam inativos — visual fiel ao combo.
            """
            for child in list(self._container.get_children()):
                self._container.remove(child)
                child.destroy()
            old_founder = self._group_founder
            if old_founder is not None:
                old_founder.destroy()
            self._buttons = []
            # group=None → este botão funda o grupo; não é empacotado → invisível.
            self._group_founder = Gtk.RadioButton()
            for the_id, label in items:
                btn = Gtk.RadioButton.new_with_label_from_widget(
                    self._group_founder, label
                )
                btn.set_mode(False)  # toggle button (sem a bolinha de radio)
                btn.connect("toggled", self._on_button_toggled, the_id)
                if self._wrap:
                    self._container.add(btn)
                else:
                    self._container.pack_start(btn, False, False, 0)
                self._buttons.append(btn)
            self._container.show_all()

        def _activate_button(self, idx: int) -> None:
            """Marca o botão idx como ativo, sob guard (sem reemitir "changed")."""
            self._updating = True
            try:
                self._buttons[idx].set_active(True)
            finally:
                self._updating = False

        def _emit_changed(self) -> None:
            self.emit("changed")

        def _on_button_toggled(
            self, button: Gtk.RadioButton, the_id: str
        ) -> None:
            """Reage ao clique do usuário no botão que ficou ATIVO."""
            if self._updating:
                return
            if not button.get_active():
                return  # ignora o botão do grupo que foi desmarcado
            if the_id == self._active_id:
                return
            self._active_id = the_id
            self.emit("changed")

else:

    class SegmentedSelector(_SegmentedLogic):  # type: ignore[no-redef]
        """Stub puro para ambientes sem GTK3 (testes, CI sem PyGObject).

        Implementa a MESMA API por-ID (a lógica vive em ``_SegmentedLogic``);
        os hooks de toolkit viram no-ops e o "changed" chama os callbacks
        registrados via ``connect``.
        """

        def __init__(self, wrap: bool = False) -> None:
            self._init_logic(wrap)
            self._handlers: list[Callable[[Any], None]] = []

        def connect(self, signal: str, callback: Callable[[Any], None]) -> None:
            if signal == "changed":
                self._handlers.append(callback)

        def show_all(self) -> None:
            pass

        def show(self) -> None:
            pass

        def set_tooltip_text(self, _text: str) -> None:
            pass

        # ---- hooks (no-ops; o estado é só self._active_id) ----

        def _create_buttons(self, items: list[tuple[str, str]]) -> None:
            pass

        def _activate_button(self, idx: int) -> None:
            pass

        def _emit_changed(self) -> None:
            for cb in list(self._handlers):
                cb(self)


__all__ = ["SegmentedSelector"]
