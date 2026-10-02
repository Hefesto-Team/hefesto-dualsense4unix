"""segmented_selector.py — botões segmentados sempre visíveis (sem popup)."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any, ClassVar

#: Colunas da grade no modo ``wrap`` (19 modos de gatilho → 7 linhas).
_WRAP_COLUNAS = 3
_WRAP_MAX_CHARS = 16


class _SegmentedLogic:
    """Lógica por-ID compartilhada (sem GTK)."""

    _wrap: bool
    _items: list[tuple[str, str]]
    _active_id: str | None
    _updating: bool

    def _init_logic(self, wrap: bool) -> None:
        self._wrap = wrap
        self._items = []
        self._active_id = None
        self._dicas: dict[str, str] = {}
        self._updating = False


    def set_items(self, items: list[tuple[str, str]]) -> None:
        """Reconstrói os botões a partir de ``[(id, label), ...]``."""
        items = list(items)
        if items == self._items:
            return
        prev_active = self._active_id
        self._items = items
        self._create_buttons(items)
        self._aplicar_dicas()
        keep = prev_active if self._index_of(items, prev_active) is not None else None
        self._active_id = None
        if keep is not None:
            idx = self._index_of(items, keep)
            if idx is not None:
                self._activate_button(idx)
                self._active_id = keep

    def set_tooltips(self, dicas: dict[str, str]) -> None:
        """Dica por BOTÃO — `{id: texto}`. Id ausente fica sem dica."""
        self._dicas = dict(dicas)
        self._aplicar_dicas()

    def _aplicar_dicas(self) -> None:
        """Hook: escreve as dicas nos botões (no-op sem toolkit)."""

    def limpar_ativo(self) -> None:
        """Deixa o seletor SEM nenhum botão marcado, sem emitir "changed"."""
        if self._active_id is None:
            return
        self._active_id = None
        self._desmarcar_todos()

    def _desmarcar_todos(self) -> None:
        """Hook: tira a marca de todos os botões (no-op sem toolkit)."""

    def get_active_id(self) -> str | None:
        """Id do item ativo, ou ``None`` (espelha ``GtkComboBox.get_active_id``)."""
        return self._active_id

    def set_active_id(self, the_id: str) -> None:
        """Ativa o botão do id e EMITE "changed" (igual ao ``GtkComboBox``)."""
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
    _RUN_FIRST = getattr(getattr(GObject, "SignalFlags", None), "RUN_FIRST", 1)

    class SegmentedSelector(_SegmentedLogic, Gtk.Box):  # type: ignore[misc]
        """Grupo de ``GtkRadioButton`` em modo toggle, com a API por-ID do combo."""

        __gsignals__: ClassVar[dict[str, tuple[Any, ...]]] = {
            "changed": (_RUN_FIRST, None, ()),
        }

        def __init__(self, wrap: bool = False) -> None:
            Gtk.Box.__init__(
                self, orientation=Gtk.Orientation.VERTICAL, spacing=0
            )
            self._init_logic(wrap)
            self._buttons: list[Gtk.RadioButton] = []
            self._group_founder: Gtk.RadioButton | None = None
            self.set_valign(Gtk.Align.CENTER)
            if wrap:
                # UX-TRIGGERS-COMPACT-01 / S3: grade de 3 colunas FIXAS.
                #
                # Aqui havia um GtkFlowBox (max 3 por linha, min 1) dentro de um
                # GtkScrolledWindow. O FlowBox decide quantas colunas usar a
                # partir da largura que RECEBE, e o ScrolledWindow lhe oferece a
                # largura mínima — a de UM botão. Resultado: ele reportava a
                # altura de 19 botões EMPILHADOS, 606px, e o mesmo 606px para
                # qualquer largura de janela. Como o GtkNotebook adota o maior
                # mínimo entre as páginas, esse número virava o piso da aba
                # inteira e a barra de rolagem era inevitável.
                #
                # Um GtkGrid não negocia: 19 itens em 3 colunas são sempre 7
                # linhas (~190px). O `column_homogeneous` mantém as colunas do
                # mesmo tamanho e o label com `wrap` deixa "Feedback em rampa"
                # ocupar duas linhas dentro do botão em vez de esticá-lo.
                grid = Gtk.Grid()
                grid.set_column_homogeneous(True)
                grid.set_row_spacing(2)
                grid.set_column_spacing(2)
                self.get_style_context().add_class("hefesto-segmented-compact")
                self._container: Any = grid
                self.pack_start(grid, True, True, 0)
            else:
                self.get_style_context().add_class("linked")
                self._container = self


        def _create_buttons(self, items: list[tuple[str, str]]) -> None:
            """Destrói os botões atuais e cria um GtkRadioButton por item."""
            for child in list(self._container.get_children()):
                self._container.remove(child)
                child.destroy()
            old_founder = self._group_founder
            if old_founder is not None:
                old_founder.destroy()
            self._buttons = []
            self._group_founder = Gtk.RadioButton()
            for indice, (the_id, label) in enumerate(items):
                btn = Gtk.RadioButton.new_with_label_from_widget(
                    self._group_founder, label
                )
                btn.set_mode(False)
                btn.connect("toggled", self._on_button_toggled, the_id)
                if self._wrap:
                    filho = btn.get_child()
                    if isinstance(filho, Gtk.Label):
                        filho.set_line_wrap(True)
                        filho.set_justify(Gtk.Justification.CENTER)
                        filho.set_max_width_chars(_WRAP_MAX_CHARS)
                    btn.set_hexpand(True)
                    self._container.attach(
                        btn, indice % _WRAP_COLUNAS, indice // _WRAP_COLUNAS, 1, 1
                    )
                else:
                    self._container.pack_start(btn, False, False, 0)
                self._buttons.append(btn)
            self._container.show_all()

        def _desmarcar_todos(self) -> None:
            """Devolve o estado ativo ao founder OCULTO do grupo."""
            if self._group_founder is None:
                return
            self._updating = True
            try:
                self._group_founder.set_active(True)
            finally:
                self._updating = False

        def _aplicar_dicas(self) -> None:
            """Escreve a dica de cada id no botão correspondente."""
            for (the_id, _label), btn in zip(
                self._items, self._buttons, strict=False
            ):
                dica = self._dicas.get(the_id)
                if dica:
                    btn.set_tooltip_text(dica)

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
                return
            if the_id == self._active_id:
                return
            self._active_id = the_id
            self.emit("changed")

else:

    class SegmentedSelector(_SegmentedLogic):  # type: ignore[no-redef]
        """Stub puro para ambientes sem GTK3 (testes, CI sem PyGObject)."""

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


        def _create_buttons(self, items: list[tuple[str, str]]) -> None:
            pass

        def _activate_button(self, idx: int) -> None:
            pass

        def _emit_changed(self) -> None:
            for cb in list(self._handlers):
                cb(self)


__all__ = ["SegmentedSelector"]
