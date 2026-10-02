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

BOTOES_JA_DO_MOUSE: frozenset[str] = frozenset(
    {*_MOUSE_BOTOES, *_MOUSE_DPAD, *_MOUSE_TECLAS_TAP, "l2", "r2"}
)


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
)


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
    # O ALTERNADOR é o preset do L3 desde 02/09/2026 (decisão dela). Sem esta
    "__TOGGLE_OSK__": "Abrir e fechar teclado na tela",
    "__OPEN_OSK__": "Abrir teclado na tela",
    "__CLOSE_OSK__": "Fechar teclado na tela",
}

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
            saida.append(tok[4:])
        else:
            saida.append(tok)
    return " + ".join(saida)


def _e_nome_de_tecla(tok: str) -> bool:
    """`True` quando `KEY_<TOK>` existe no vocabulário do `evdev`."""
    if not tok or not tok.replace("_", "").isalnum():
        return False
    try:
        from evdev import ecodes
    except Exception:
        return False
    return f"KEY_{tok.upper()}" in getattr(ecodes, "ecodes", {})


def dehumanize_binding(friendly: str) -> str:
    """Inverso de `humanize_binding` — 'Alt + Tab' → 'KEY_LEFTALT+KEY_TAB'."""
    partes = [tok.strip() for tok in friendly.split("+") if tok.strip()]
    saida = []
    for tok in partes:
        chave = tok.lower()
        if chave in _REV_KEY:
            saida.append(_REV_KEY[chave])
        elif tok.startswith("KEY_") or tok.startswith("__"):
            saida.append(tok)
        elif (len(tok) == 1 and tok.isalnum()) or _e_nome_de_tecla(tok):
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
        return (
            "<b>Sem tecla:</b> nenhum botão digita nada agora — a lista está "
            "vazia porque todos os atalhos foram removidos. Clique em “Voltar "
            "ao padrão” para devolver os de fábrica."
        )
    nomes = ", ".join(humanize_button(botao) for botao in orfaos)
    frase = f"<b>Sem tecla (não digitam nada):</b> {nomes}."
    do_mouse = [botao for botao in orfaos if botao in BOTOES_JA_DO_MOUSE]
    if do_mouse:
        quantos = (
            "Um deles já é" if len(do_mouse) == 1 else f"{len(do_mouse)} deles já são"
        )
        frase += (
            f" {quantos} do mouse quando “Emular mouse” está ligado (clique, "
            "rolagem, setas): dar uma tecla a esses faz o botão fazer as duas "
            "coisas ao mesmo tempo."
        )
    return frase


def frase_do_teclado_na_tela(osk_disponivel: bool | None) -> str:
    """O que ESTA máquina tem, sobre o teclado na tela (N12).

    TECLADO-NA-TELA-QUE-A-JANELA-NAO-LE-01. `BINDINGS_LEGEND` diz o que o L3
    PRECISA (`onboard` ou `wvkbd-mobintl` instalados) e nunca disse se algum
    está — e a resposta viaja no fio desde 10/08, no `osk_disponivel` do bloco
    `keyboard_emulation`. Como nenhum atalho de fábrica digita letra, esta é a
    frase que decide se existe ALGUM caminho para escrever texto com o
    controle.

    Aditiva, e não uma reescrita da legenda: com `None` devolve `""` e a tela
    fica exatamente como estava. "Não sei" já está dito no texto fixo, e
    substituí-lo por "não tem" porque ninguém respondeu mandaria ela instalar um
    pacote que talvez já esteja lá.

    Os dois nomes saem com o ambiente ao lado porque a ORDEM importa e a janela
    não a conhece: o `onboard` digita por XTEST e não alcança cliente Wayland
    nativo; o daemon já escolhe pela sessão viva (`_osk_candidatos`), mas quem
    lê a legenda está prestes a instalar à mão.
    """
    if osk_disponivel is None:
        return ""
    if osk_disponivel:
        return (
            "<b>Neste computador:</b> o teclado na tela está instalado — o L3 "
            "abre."
        )
    return (
        "<b>Neste computador:</b> não há teclado na tela instalado, então o L3 "
        "não vai abrir nada — e, como nenhum atalho de fábrica digita letra, "
        "hoje não há como escrever texto com o controle. Instale um: "
        "<tt>wvkbd-mobintl</tt> (Wayland) ou <tt>onboard</tt> (X11)."
    )


#: 09/08 (TOUCHPAD-DO-SISTEMA-01) e continua em `DEFAULT_BUTTON_BINDINGS`.
REGIOES_DO_TOUCHPAD: frozenset[str] = frozenset(
    {"touchpad_left_press", "touchpad_middle_press", "touchpad_right_press"}
)


def frase_dos_atalhos_fora_da_lista(bindings: dict[str, tuple[str, ...]]) -> str:
    """Nomeia os atalhos que o perfil GUARDA e a lista da aba não mostra."""
    fora = [botao for botao in bindings if botao not in CANONICAL_BUTTONS]
    if not fora:
        return ""
    nomes = ", ".join(humanize_button(botao) for botao in fora)
    frase = f"<b>Guardados, sem linha na lista:</b> {nomes}."
    if all(botao in REGIOES_DO_TOUCHPAD for botao in fora):
        frase += (
            " O touchpad voltou a ser o mouse do computador, então esta versão "
            "não dispara esses atalhos."
        )
    else:
        frase += " Esta versão não dispara esses atalhos."
    frase += (
        " O perfil continua guardando o que você escolheu — nada nesta aba os "
        "apaga."
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


    def _install_key_bindings_treeview(self) -> None:
        """Cria/configura colunas do `key_bindings_treeview`. Idempotente."""
        tree: Gtk.TreeView | None = self._get("key_bindings_treeview")
        if tree is None:
            return
        if tree.get_model() is not None:
            self._key_bindings_store = tree.get_model()
            return
        store = Gtk.ListStore(
            GObject.TYPE_STRING,
            GObject.TYPE_STRING,
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
        self._atualizar_legenda(bindings)

    def _atualizar_legenda(self, bindings: dict[str, tuple[str, ...]]) -> None:
        """Pinta a legenda fixa + as duas frases variáveis. Tolera glade sem ela."""
        legend = self._get("key_bindings_legend")
        if legend is None:
            return
        partes = [BINDINGS_LEGEND]
        partes += [
            frase
            for frase in (
                frase_do_teclado_na_tela(getattr(self, "_osk_disponivel", None)),
                frase_dos_botoes_sem_tecla(bindings),
                frase_dos_atalhos_fora_da_lista(bindings),
            )
            if frase
        ]
        legend.set_markup("\n".join(partes))

    def _repintar_legenda_do_teclado(self) -> None:
        """Gancho do `_anotar_teclado_na_tela` (N12): repinta SÓ a legenda."""
        self._atualizar_legenda(self._resolve_effective_bindings())

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
        """FUNDE o store com o rascunho e grava em `draft.key_bindings`.

        Store vazia → None (herda defaults). Dict não vazio → override
        explícito (consumido por `DraftConfig.to_profile`).

        ATALHO-FORA-DA-LISTA-01 (25/08/2026) — por que FUNDIR e não substituir.
        Esta função escrevia a lista da TELA por cima de `draft.key_bindings`, e
        a lista da tela só tem linha para botão de `CANONICAL_BUTTONS`
        (`_refresh_key_bindings_from_draft`). Existe chave FORA dessa lista, e
        não por acidente: as três regiões do touchpad saíram da aba em 09/08
        (TOUCHPAD-DO-SISTEMA-01, decisão dela — ver o comentário longo em
        `CANONICAL_BUTTONS`) e continuam em `DEFAULT_BUTTON_BINDINGS` e nos
        perfis que ela já gravou. O resultado medido: o perfil
        `point_and_click.json` dela guarda sete atalhos, a tela mostra quatro, e
        o PRIMEIRO gesto na aba — editar uma célula, "Adicionar", "Remover" —
        apagava os três do touchpad sem uma palavra. O rodapé "Salvar Perfil"
        emite `key_bindings=self.key_bindings` (`app/draft_config.py:541`): o
        rascunho podado virava o arquivo podado.

        A regra da fusão, em três linhas:

        - o que TEM linha na tela vence — é o que ela está vendo e mexendo;
        - botão canônico SEM linha continua fora (removê-lo é gesto legítimo, e
          fundir de volta desfaria o "Remover" dela);
        - chave sem linha e fora de `CANONICAL_BUTTONS` é preservada — a tela
          nunca a ofereceu, então nada do que ela fez aqui pediu para apagá-la.
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
        for button, guardados in self._resolve_effective_bindings().items():
            if button in CANONICAL_BUTTONS or button in new_bindings:
                continue
            new_bindings[button] = list(guardados)
        self.draft = draft.model_copy(
            update={"key_bindings": new_bindings or None}
        )


    def _toast_input(self, msg: str) -> None:
        """Toast em `status_bar`. Reusa ctx id "input" pra não brigar com mouse."""
        self._status_toast("input", msg)


__all__ = [
    "BINDINGS_LEGEND",
    "CANONICAL_BUTTONS",
    "REGIOES_DO_TOUCHPAD",
    "InputActionsMixin",
    "frase_do_teclado_na_tela",
    "frase_dos_atalhos_fora_da_lista",
]
