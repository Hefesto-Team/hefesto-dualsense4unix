"""Aba "Mouse e Teclado" — handlers CRUD de key_bindings por perfil.

FEAT-KEYBOARD-UI-01 (sprint 59.3). Herda `MouseActionsMixin` para reaproveitar
os handlers de mouse existentes e estende com:

- `install_input_tab()` — popula o TreeView com bindings efetivos do perfil
  ativo (DEFAULT_BUTTON_BINDINGS mesclado com `draft.profile.key_bindings`).
- Handlers `on_key_binding_add`, `on_key_binding_remove`,
  `on_key_binding_restore_defaults` — CRUD sobre o ListStore, delegando
  persistência ao `profile.save` via footer.

Rename físico para `input_actions.py` segue o spec, mas `mouse_actions.py`
permanece como submódulo compatibilidade (classe `MouseActionsMixin` não é
removida) para evitar ripple em callers externos e em `main.glade` onde os
handlers de mouse continuam amarrados pelos IDs originais.
"""
# ruff: noqa: E402
from __future__ import annotations

from typing import Any

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GObject, Gtk

from hefesto_dualsense4unix.app.actions.mouse_actions import MouseActionsMixin
from hefesto_dualsense4unix.core.keyboard_mappings import (
    DEFAULT_BUTTON_BINDINGS,
    format_binding,
    parse_binding,
)
from hefesto_dualsense4unix.integrations.uinput_mouse import (
    BUTTON_TO_UINPUT as _MOUSE_BOTOES,
)
from hefesto_dualsense4unix.integrations.uinput_mouse import (
    DPAD_TO_KEY as _MOUSE_DPAD,
)
from hefesto_dualsense4unix.integrations.uinput_mouse import (
    EDGE_KEY_MAP as _MOUSE_TECLAS_TAP,
)

# Legenda do layout de bindings — exibida acima do TreeView como referência
# rápida dos tokens aceitos. Tokens `__*__` são virtuais (OSK); demais são
# KEY_* canônicos do evdev.ecodes.
#
# TECLADO-QUE-NAO-DIGITA-01 (09/08/2026): a legenda abria com *"cada botão do
# controle pode digitar uma tecla do teclado"* e a lista abaixo dela mostrava
# SÓ os botões que já tinham tecla — os outros onze simplesmente não existiam
# na tela. Quem ligava "Emular teclado" via seis linhas, apertava X, Círculo,
# Quadrado, direcional, e concluía, com razão, que "o teclado não funciona":
# nada na tela dizia que aqueles botões não digitam nada, e nada dizia que
# NENHUM atalho de fábrica digita LETRA. As duas linhas novas abaixo (e a
# `frase_dos_botoes_sem_tecla`, montada a cada refresh) são o que faltava.
BINDINGS_LEGEND = (
    "<b>Como funciona:</b> cada botão do controle pode digitar uma tecla do "
    "teclado. Clique duas vezes na coluna “Tecla do teclado” para trocar.\n"
    "<b>Combinações:</b> junte teclas com “+” (ex.: Alt + Tab).\n"
    "<b>Teclado na tela:</b> escreva “Abrir teclado na tela” ou "
    "“Fechar teclado na tela”.\n"
    "<b>Para ESCREVER texto:</b> nenhum atalho de fábrica digita letra — os de "
    "fábrica são atalhos (Alt + Tab, Super, PrintScreen, Enter, Delete, "
    "Backspace). Para escrever, abra o teclado na tela com L3; ele precisa do "
    "programa <tt>onboard</tt> ou <tt>wvkbd-mobintl</tt> instalado no "
    "computador."
)

#: Botões que o MOUSE emulado já usa quando "Emular mouse" está ligado. Vem dos
#: mapas do próprio `integrations/uinput_mouse.py` (fonte única — lista copiada
#: à mão envelhece calada), mais L2/R2, que aquele device injeta como
#: cross/triangle acima do limiar analógico (`_resolve_emulated_set`).
#:
#: Dar uma tecla a um deles NÃO substitui o mouse: o botão passa a fazer as DUAS
#: coisas ao mesmo tempo, cada uma pelo SEU dispositivo virtual — são dois donos
#: do mesmo botão, e a lista oferecia os vinte botões sem dizer isso.
BOTOES_JA_DO_MOUSE: frozenset[str] = frozenset(
    {*_MOUSE_BOTOES, *_MOUSE_DPAD, *_MOUSE_TECLAS_TAP, "l2", "r2"}
)


# Ordem canônica de exibição dos botões no TreeView. Corresponde aos 17 botões
# canônicos do DualSense mais as 3 regiões de touchpad.
CANONICAL_BUTTONS: tuple[str, ...] = (
    "cross",
    "circle",
    "triangle",
    "square",
    "dpad_up",
    "dpad_down",
    "dpad_left",
    "dpad_right",
    "l1",
    "r1",
    "l2",
    "r2",
    "l3",
    "r3",
    "options",
    "create",
    "ps",
    # TOUCHPAD-DO-SISTEMA-01 (09/08/2026) — decisão dela: as três regiões do
    # touchpad SAÍRAM da aba, e a razão é que o produto não pode oferecer duas
    # coisas que se atropelam no mesmo dedo.
    #
    # O touchpad voltou a ser touchpad do SISTEMA, como era antes do Hefesto
    # (pedido dela: *"a ideia do touchpad é ele voltar a funcionar assim, seja
    # no modo nativo ou dualsense"*). Com isso, o clique dele já vira clique de
    # mouse pelo libinput. Manter as regiões mapeadas somaria uma TECLA ao
    # mesmo gesto — e o padrão de fábrica era `KEY_BACKSPACE`, ou seja: um
    # clique apagaria texto sem ela pedir.
    #
    # Listar aqui um botão que o produto não dispara mais é a janela mentindo,
    # que é o defeito que esta casa mais persegue. O runtime já se cala
    # (`daemon/subsystems/keyboard.py`, o gate `_combine_with_touchpad`); a aba
    # para de oferecer.
    #
    # PARA VOLTAR: é a mesma decisão, do outro lado — o touchpad passaria a ser
    # do Hefesto de novo (a reversão da regra está escrita no cabeçalho de
    # `assets/76-dualsense-touchpad-libinput-ignore.rules`), e estas três linhas
    # voltam junto. Uma coisa não vai sem a outra.
)


# KBD-01: a aba Teclado era 100% jargão de programador — ids internos em inglês
# (l1, create, touchpad_left_press) e tokens crus do evdev (KEY_LEFTALT,
# KEY_SYSRQ, __OPEN_OSK__). Estes mapas humanizam a EXIBIÇÃO (o modelo segue
# guardando id/binding crus para a persistência); a edição converte de volta na
# fronteira (`_dehumanize_binding`). Nomes na língua da usuária, não do kernel.
_BUTTON_LABELS: dict[str, str] = {
    "cross": "X (Cruz)",
    "circle": "Círculo",
    "triangle": "Triângulo",
    "square": "Quadrado",
    "dpad_up": "Direcional ↑",
    "dpad_down": "Direcional ↓",
    "dpad_left": "Direcional ←",
    "dpad_right": "Direcional →",
    "l1": "L1",
    "r1": "R1",
    "l2": "L2 (gatilho esquerdo)",
    "r2": "R2 (gatilho direito)",
    "l3": "L3 (clicar analógico esquerdo)",
    "r3": "R3 (clicar analógico direito)",
    "options": "Options",
    "create": "Share / Create",
    "ps": "Botão PS",
    "touchpad_left_press": "Touchpad — lado esquerdo",
    "touchpad_middle_press": "Touchpad — meio",
    "touchpad_right_press": "Touchpad — lado direito",
}

#: Tokens de tecla crus → nome que a pessoa reconhece. Fora deste mapa, um
#: `KEY_X` vira só "X" (letras/números). Round-trip garantido por `_REV_KEY`.
_KEY_LABELS: dict[str, str] = {
    "KEY_LEFTALT": "Alt",
    "KEY_RIGHTALT": "Alt direito",
    "KEY_LEFTSHIFT": "Shift",
    "KEY_RIGHTSHIFT": "Shift direito",
    "KEY_LEFTCTRL": "Ctrl",
    "KEY_RIGHTCTRL": "Ctrl direito",
    "KEY_LEFTMETA": "Super (tecla Windows)",
    "KEY_TAB": "Tab",
    "KEY_ENTER": "Enter",
    "KEY_ESC": "Esc",
    "KEY_SPACE": "Espaço",
    "KEY_BACKSPACE": "Backspace",
    "KEY_DELETE": "Delete",
    "KEY_SYSRQ": "PrintScreen",
    "KEY_UP": "Seta ↑",
    "KEY_DOWN": "Seta ↓",
    "KEY_LEFT": "Seta ←",
    "KEY_RIGHT": "Seta →",
    "__OPEN_OSK__": "Abrir teclado na tela",
    "__CLOSE_OSK__": "Fechar teclado na tela",
}

#: Mapa reverso (rótulo minúsculo → token cru) para a edição amigável.
_REV_KEY: dict[str, str] = {label.lower(): raw for raw, label in _KEY_LABELS.items()}


def humanize_button(button_id: str) -> str:
    """Rótulo amigável de um botão do controle (fallback: o próprio id)."""
    return _BUTTON_LABELS.get(button_id, button_id)


def humanize_binding(serialized: str) -> str:
    """'KEY_LEFTALT+KEY_TAB' → 'Alt + Tab'; '__OPEN_OSK__' → 'Abrir teclado…'."""
    partes = [tok.strip() for tok in serialized.split("+") if tok.strip()]
    saida = []
    for tok in partes:
        if tok in _KEY_LABELS:
            saida.append(_KEY_LABELS[tok])
        elif tok.startswith("KEY_"):
            saida.append(tok[4:])  # KEY_C -> C
        else:
            saida.append(tok)
    return " + ".join(saida)


def dehumanize_binding(friendly: str) -> str:
    """Inverso de `humanize_binding` — 'Alt + Tab' → 'KEY_LEFTALT+KEY_TAB'.

    Aceita também tokens já crus (idempotente sobre a saída do daemon) para
    quem preferir digitar `KEY_*`. Token desconhecido segue como está — o
    `parse_binding` valida e rejeita com um toast na fronteira.
    """
    partes = [tok.strip() for tok in friendly.split("+") if tok.strip()]
    saida = []
    for tok in partes:
        chave = tok.lower()
        if chave in _REV_KEY:
            saida.append(_REV_KEY[chave])
        elif tok.startswith("KEY_") or tok.startswith("__"):
            saida.append(tok)
        elif len(tok) == 1 and tok.isalnum():
            saida.append(f"KEY_{tok.upper()}")
        else:
            saida.append(tok)
    return "+".join(saida)


def frase_dos_botoes_sem_tecla(bindings: dict[str, tuple[str, ...]]) -> str:
    """Nomeia, em português, os botões do controle que NÃO digitam nada.

    TECLADO-QUE-NAO-DIGITA-01. A lista da aba só cria linha para botão COM
    tecla (`_refresh_key_bindings_from_draft`), então o botão sem tecla não
    aparece "vazio": ele some. Para quem olha, a lista parece completa — e
    apertar X, Círculo ou o direcional esperando que o teclado emulado digite
    algo é a conclusão natural, e errada, que ela teve em 09/08/2026.

    Pura de propósito: é o miolo do que ela lê, e precisa de teste sem montar
    janela (mesma disciplina do `descrever_teclado_emulado`). Devolve `""`
    quando todos os botões têm tecla — nada a dizer é melhor que uma linha
    vazia na tela.
    """
    orfaos = [botao for botao in CANONICAL_BUTTONS if not bindings.get(botao)]
    if not orfaos:
        return ""
    if len(orfaos) == len(CANONICAL_BUTTONS):
        # `key_bindings == {}` é uma escolha legítima ("teclado silencioso"),
        # mas na tela ela era indistinguível de defeito: lista vazia, sem uma
        # palavra. Agora diz o que é e como sair.
        return (
            "<b>Sem tecla:</b> nenhum botão digita nada agora — a lista está "
            "vazia porque todos os atalhos foram removidos. Clique em “Voltar "
            "ao padrão” para devolver os de fábrica."
        )
    nomes = ", ".join(humanize_button(botao) for botao in orfaos)
    frase = f"<b>Sem tecla (não digitam nada):</b> {nomes}."
    do_mouse = [botao for botao in orfaos if botao in BOTOES_JA_DO_MOUSE]
    if do_mouse:
        # Sem repetir os nomes: a lista acima já os deu, e repeti-la fazia a
        # frase dobrar de tamanho na tela dela.
        quantos = (
            "Um deles já é" if len(do_mouse) == 1 else f"{len(do_mouse)} deles já são"
        )
        frase += (
            f" {quantos} do mouse quando “Emular mouse” está ligado (clique, "
            "rolagem, setas): dar uma tecla a esses faz o botão fazer as duas "
            "coisas ao mesmo tempo."
        )
    return frase


class InputActionsMixin(MouseActionsMixin):
    """Mixin da aba "Mouse e Teclado": mouse handlers + key_bindings CRUD."""

    _key_bindings_store: Any = None

    def install_input_tab(self) -> None:
        """Setup inicial da aba. Reusa `install_mouse_tab` + popula TreeView."""
        self.install_mouse_tab()
        self._install_key_bindings_treeview()
        self._refresh_key_bindings_from_draft()

    # ------------------------------------------------------------------
    # TreeView setup + refresh
    # ------------------------------------------------------------------

    def _install_key_bindings_treeview(self) -> None:
        """Cria/configura colunas do `key_bindings_treeview`. Idempotente."""
        tree: Gtk.TreeView | None = self._get("key_bindings_treeview")
        if tree is None:
            return
        if tree.get_model() is not None:
            self._key_bindings_store = tree.get_model()
            return
        store = Gtk.ListStore(
            GObject.TYPE_STRING,  # botão canônico
            GObject.TYPE_STRING,  # binding serializado (KEY_A+KEY_B)
        )
        tree.set_model(store)
        self._key_bindings_store = store
        for idx, title in ((0, "Botão do controle"), (1, "Tecla do teclado")):
            renderer = Gtk.CellRendererText()
            if idx == 1:
                renderer.set_property("editable", True)
                renderer.connect(
                    "edited", self._on_key_binding_cell_edited
                )
            # KBD-01: exibe amigável (o modelo guarda id/binding CRUS p/ a
            # persistência); a edição converte de volta em `_on_..._edited`.
            column = Gtk.TreeViewColumn(title, renderer)
            column.set_cell_data_func(renderer, self._render_binding_cell, idx)
            tree.append_column(column)
        legend: Gtk.Label | None = self._get("key_bindings_legend")
        if legend is not None:
            legend.set_markup(BINDINGS_LEGEND)

    @staticmethod
    def _render_binding_cell(
        _column: Gtk.TreeViewColumn,
        cell: Gtk.CellRendererText,
        model: Gtk.TreeModel,
        treeiter: Gtk.TreeIter,
        col_idx: int,
    ) -> None:
        """Exibe amigável (KBD-01) sem tocar no valor CRU do modelo."""
        raw = model.get_value(treeiter, col_idx)
        if col_idx == 0:
            cell.set_property("text", humanize_button(raw))
        else:
            cell.set_property("text", humanize_binding(raw))

    def _refresh_key_bindings_from_draft(self) -> None:
        """Popula o store com as bindings efetivas do draft central.

        Efetiva = DEFAULT_BUTTON_BINDINGS quando `draft.key_bindings is None`
        (herda); `{}` = vazio (teclado silencioso); dict parcial = override
        explícito.
        """
        store = self._key_bindings_store
        if store is None:
            return
        store.clear()
        bindings = self._resolve_effective_bindings()
        for button in CANONICAL_BUTTONS:
            binding = bindings.get(button)
            if binding is None:
                continue
            store.append([button, format_binding(binding)])
        # TECLADO-QUE-NAO-DIGITA-01: a legenda é recalculada A CADA refresh
        # porque a lista de "sem tecla" muda com o rascunho (adicionar, remover,
        # voltar ao padrão, trocar de perfil). Pintá-la só na instalação do
        # TreeView, como era, deixaria a frase mentindo no primeiro Adicionar.
        self._atualizar_legenda(bindings)

    def _atualizar_legenda(self, bindings: dict[str, tuple[str, ...]]) -> None:
        """Pinta a legenda fixa + a frase dos botões sem tecla. Tolera glade sem ela."""
        legend = self._get("key_bindings_legend")
        if legend is None:
            return
        frase = frase_dos_botoes_sem_tecla(bindings)
        texto = BINDINGS_LEGEND + (f"\n{frase}" if frase else "")
        legend.set_markup(texto)

    def _resolve_effective_bindings(self) -> dict[str, tuple[str, ...]]:
        """Resolve o draft atual em mapping de botões → tupla de tokens."""
        draft = getattr(self, "draft", None)
        if draft is None:
            return dict(DEFAULT_BUTTON_BINDINGS)
        raw = draft.key_bindings
        if raw is None:
            return dict(DEFAULT_BUTTON_BINDINGS)
        if not raw:
            return {}
        return {k: tuple(v) for k, v in raw.items()}

    # ------------------------------------------------------------------
    # CRUD handlers
    # ------------------------------------------------------------------

    def on_key_binding_add(self, _button: Any) -> None:
        """Adiciona row vazia para o primeiro botão canônico ainda sem row."""
        store = self._key_bindings_store
        if store is None:
            return
        existing = {row[0] for row in store}
        for candidate in CANONICAL_BUTTONS:
            if candidate not in existing:
                store.append([candidate, "KEY_SPACE"])
                self._persist_key_bindings_to_draft()
                # KBD-02: antes, "Adicionar" escolhia um botão sozinho e já o
                # mapeava para uma tecla sem avisar. Agora explicamos, com o
                # nome humano do botão, o que aconteceu e para onde ir p/ trocar.
                self._toast_input(
                    "Adicionei uma linha para o botão "
                    f"“{humanize_button(candidate)}”, começando na tecla "
                    "“Espaço”. Clique duas vezes na coluna “Tecla do teclado” "
                    "para escolher outra, ou remova a linha se não quiser."
                )
                return
        self._toast_input("Todos os botões já têm binding — edite os existentes.")

    def on_key_binding_remove(self, _button: Any) -> None:
        """Remove a row selecionada no TreeView."""
        tree: Gtk.TreeView | None = self._get("key_bindings_treeview")
        store = self._key_bindings_store
        if tree is None or store is None:
            return
        selection = tree.get_selection()
        _, treeiter = selection.get_selected()
        if treeiter is None:
            self._toast_input("Selecione uma linha para remover.")
            return
        store.remove(treeiter)
        self._persist_key_bindings_to_draft()

    def on_key_binding_restore_defaults(self, _button: Any) -> None:
        """Restaura DEFAULT_BUTTON_BINDINGS (draft.key_bindings = None)."""
        draft = getattr(self, "draft", None)
        if draft is None:
            return
        self.draft = draft.model_copy(update={"key_bindings": None})
        self._refresh_key_bindings_from_draft()
        self._toast_input("Bindings do teclado restaurados para o default.")

    def _on_key_binding_cell_edited(
        self,
        _renderer: Gtk.CellRendererText,
        path: str,
        new_text: str,
    ) -> None:
        """Editor inline da coluna 'Tecla(s)' — valida e persiste."""
        store = self._key_bindings_store
        if store is None:
            return
        text = new_text.strip()
        if not text:
            return
        # KBD-01: a pessoa edita nomes amigáveis ("Alt + Tab"); convertemos de
        # volta para os tokens crus que o daemon entende antes de validar/gravar.
        raw = dehumanize_binding(text)
        try:
            parse_binding(raw)
        except ValueError as exc:
            self._toast_input(f"Não reconheci essa tecla: {exc}")
            return
        treeiter = store.get_iter(path)
        store.set_value(treeiter, 1, raw)
        self._persist_key_bindings_to_draft()

    def _persist_key_bindings_to_draft(self) -> None:
        """Serializa o store em dict e grava em `draft.key_bindings`.

        Store vazia → None (herda defaults). Dict não vazio → override
        explícito (consumido por `DraftConfig.to_profile`).
        """
        draft = getattr(self, "draft", None)
        if draft is None:
            return
        store = self._key_bindings_store
        if store is None:
            return
        new_bindings: dict[str, list[str]] = {}
        for row in store:
            button = row[0]
            try:
                tokens = list(parse_binding(row[1]))
            except ValueError:
                continue
            new_bindings[button] = tokens
        self.draft = draft.model_copy(
            update={"key_bindings": new_bindings or None}
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _toast_input(self, msg: str) -> None:
        """Toast em `status_bar`. Reusa ctx id "input" pra não brigar com mouse."""
        self._status_toast("input", msg)


__all__ = [
    "BINDINGS_LEGEND",
    "CANONICAL_BUTTONS",
    "InputActionsMixin",
]
