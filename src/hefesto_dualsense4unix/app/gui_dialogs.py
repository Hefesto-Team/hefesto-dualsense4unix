"""Helpers de diálogo GTK reutilizáveis para a GUI do Hefesto - Dualsense4Unix.

Todos os diálogos são modais e bloqueantes (run/destroy), adequados para
uso na thread principal GTK. Nenhum acessa IPC diretamente.
"""
from __future__ import annotations

import contextlib
from typing import Any, cast

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402

from hefesto_dualsense4unix.utils.i18n import _  # noqa: E402


def _apply_app_theme(dialog: Any) -> None:
    """Aplica a classe de tema do app ao toplevel do diálogo (GUI-05/P5).

    TODO o CSS Drácula é escopado a ``.hefesto-dualsense4unix-window`` — um
    diálogo sem a classe herda o tema do sistema, que sob XWayland no COSMIC
    (XSettings apontando um gtk-theme nem instalado) degrada para Adwaita
    CLARO, ilegível ao lado do corpo escuro do app. Best-effort: um style
    context stubado nos testes não pode derrubar o fluxo do diálogo.
    """
    with contextlib.suppress(Exception):
        dialog.get_style_context().add_class("hefesto-dualsense4unix-window")


def prompt_profile_name(
    parent: Gtk.Window,
    default_name: str = "",
) -> str | None:
    """Exibe diálogo modal para entrada de nome de perfil.

    Retorna o nome digitado (stripped) ou None se o usuário cancelou.
    Campo pré-preenchido com ``default_name``.
    """
    dialog = Gtk.Dialog(
        title=_("Salvar Perfil"),
        parent=parent,
        modal=True,
        destroy_with_parent=True,
    )
    _apply_app_theme(dialog)
    dialog.add_button(_("Cancelar"), Gtk.ResponseType.CANCEL)
    dialog.add_button(_("Salvar"), Gtk.ResponseType.OK)
    dialog.set_default_response(Gtk.ResponseType.OK)

    content = dialog.get_content_area()
    content.set_spacing(8)
    content.set_margin_top(12)
    content.set_margin_bottom(12)
    content.set_margin_start(16)
    content.set_margin_end(16)

    label = Gtk.Label(label=_("Nome do perfil:"))
    label.set_xalign(0.0)
    content.add(label)

    entry = Gtk.Entry()
    entry.set_text(default_name)
    entry.set_activates_default(True)
    content.add(entry)

    content.show_all()
    response = dialog.run()
    name = entry.get_text().strip()
    dialog.destroy()

    if response == Gtk.ResponseType.OK and name:
        return cast(str, name)
    return None


def prompt_overwrite_existing(
    parent: Gtk.Window,
    name: str,
) -> bool:
    """Pergunta se o usuário deseja sobrescrever um perfil de mesmo nome.

    Retorna True se confirmou sobrescrever, False se cancelou.
    """
    dialog = Gtk.MessageDialog(
        parent=parent,
        modal=True,
        destroy_with_parent=True,
        message_type=Gtk.MessageType.QUESTION,
        buttons=Gtk.ButtonsType.NONE,
        text=_("Perfil '%s' já existe.") % name,
    )
    _apply_app_theme(dialog)
    dialog.format_secondary_text(_("Deseja sobrescrever o perfil existente?"))
    dialog.add_button(_("Cancelar"), Gtk.ResponseType.CANCEL)
    dialog.add_button(_("Sobrescrever"), Gtk.ResponseType.OK)
    dialog.set_default_response(Gtk.ResponseType.OK)

    response = dialog.run()
    dialog.destroy()
    return bool(response == Gtk.ResponseType.OK)


def confirm_downgrade_match_to_any(
    parent: Gtk.Window,
    name: str,
) -> bool:
    """Confirma transformar um perfil de programa específico em "Sempre".

    COR-A: desligar "Modo avançado" num perfil de jogo e Salvar trocava o alvo
    (window_class/título) por MatchAny em SILÊNCIO — o perfil que valia só num
    jogo passava a valer para TUDO, sem aviso e com o toast "Perfil salvo".
    Retorna True se o usuário confirmou a mudança, False se cancelou.
    """
    dialog = Gtk.MessageDialog(
        parent=parent,
        modal=True,
        destroy_with_parent=True,
        message_type=Gtk.MessageType.WARNING,
        buttons=Gtk.ButtonsType.NONE,
        text=_("O perfil '%s' vale só em programas específicos.") % name,
    )
    _apply_app_theme(dialog)
    dialog.format_secondary_text(
        _(
            "Salvar assim faz ele valer para TUDO (Quando usar: Sempre) e apaga "
            "os programas em que ele valia. Tem certeza?"
        )
    )
    dialog.add_button(_("Cancelar"), Gtk.ResponseType.CANCEL)
    dialog.add_button(_("Valer para tudo"), Gtk.ResponseType.OK)
    dialog.set_default_response(Gtk.ResponseType.CANCEL)

    response = dialog.run()
    dialog.destroy()
    return bool(response == Gtk.ResponseType.OK)


def prompt_import_conflict(
    parent: Gtk.Window,
    name: str,
) -> str | None:
    """Exibe diálogo de conflito ao importar perfil com nome já existente.

    Retorna uma das strings: "sobrescrever", "renomear", ou None (cancelado).
    O chamador deve tratar "renomear" pedindo novo nome via prompt_profile_name.
    """
    dialog = Gtk.MessageDialog(
        parent=parent,
        modal=True,
        destroy_with_parent=True,
        message_type=Gtk.MessageType.QUESTION,
        buttons=Gtk.ButtonsType.NONE,
        text=_("Perfil '%s' já existe.") % name,
    )
    _apply_app_theme(dialog)
    dialog.format_secondary_text(
        _("Escolha o que fazer com o perfil importado:")
    )
    dialog.add_button(_("Cancelar"), Gtk.ResponseType.CANCEL)
    dialog.add_button(_("Renomear"), Gtk.ResponseType.REJECT)
    dialog.add_button(_("Sobrescrever"), Gtk.ResponseType.OK)
    dialog.set_default_response(Gtk.ResponseType.OK)

    response = dialog.run()
    dialog.destroy()

    if response == Gtk.ResponseType.OK:
        return "sobrescrever"
    if response == Gtk.ResponseType.REJECT:
        return "renomear"
    return None


def confirm_restore_default(parent: Gtk.Window) -> bool:
    """Pede confirmação antes de restaurar meu_perfil ao estado original.

    Retorna True se o usuário confirmou, False se cancelou.
    """
    dialog = Gtk.MessageDialog(
        parent=parent,
        modal=True,
        destroy_with_parent=True,
        message_type=Gtk.MessageType.WARNING,
        buttons=Gtk.ButtonsType.NONE,
        text=_("Restaurar perfil original?"),
    )
    _apply_app_theme(dialog)
    dialog.format_secondary_text(
        # BUG-RESTORE-DIALOG-WRONG-PROFILE-01: citava 'Navegação' (outro asset,
        # navegacao.json); o restore aplica o asset 'meu_perfil' (match: any).
        _(
            "Isso vai restaurar o 'meu_perfil' para a configuração padrão de "
            "fábrica (aplica-se a todos os apps). As suas alterações serão "
            "perdidas. Continuar?"
        )
    )
    dialog.add_button(_("Cancelar"), Gtk.ResponseType.CANCEL)
    dialog.add_button(_("Restaurar"), Gtk.ResponseType.OK)
    dialog.set_default_response(Gtk.ResponseType.CANCEL)

    response = dialog.run()
    dialog.destroy()
    return bool(response == Gtk.ResponseType.OK)


def confirm_delete_profile(parent: Gtk.Window, name: str) -> bool:
    """Pede confirmação antes de remover PERMANENTEMENTE um perfil.

    Retorna True se o usuário confirmou a remoção, False se cancelou.
    BUG-DELETE-NO-CONFIRM-01: antes a remoção era 1-clique sem aviso.
    """
    dialog = Gtk.MessageDialog(
        parent=parent,
        modal=True,
        destroy_with_parent=True,
        message_type=Gtk.MessageType.WARNING,
        buttons=Gtk.ButtonsType.NONE,
        text=_("Remover o perfil '%s'?") % name,
    )
    _apply_app_theme(dialog)
    dialog.format_secondary_text(
        _("Esta ação é permanente e não pode ser desfeita.")
    )
    dialog.add_button(_("Cancelar"), Gtk.ResponseType.CANCEL)
    dialog.add_button(_("Remover"), Gtk.ResponseType.OK)
    dialog.set_default_response(Gtk.ResponseType.CANCEL)

    response = dialog.run()
    dialog.destroy()
    return bool(response == Gtk.ResponseType.OK)


def _escape_markup(text: str) -> str:
    """Escapa `&`/`<`/`>` para markup Pango (sem depender de GLib no import)."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _external_mode_row(entry: dict[str, Any]) -> tuple[Any, Any] | None:
    """(linha com o segmentado read-only do modo, subtítulo) — ou ``None``.

    GUI-05/P4: o modo detectado ("O jogo vê como") deixou de ser só uma linha
    de texto na grade e virou um seletor SEGMENTADO do padrão da casa
    (``Nintendo | Xbox``) — READ-ONLY, porque o modo é troca de HARDWARE
    (combo no próprio controle), nunca um toggle de software. Sem popup nem
    dropdown (veto do 8BIT-02: cosmic-comp fecha qualquer popup). Separado do
    diálogo modal para os testes montarem a linha sem ``run()``.
    """
    from hefesto_dualsense4unix.app.actions.external_controllers import (
        MODE_SELECTOR_SUBTITLE,
        MODE_SELECTOR_TOOLTIP,
        mode_selector_state,
    )
    from hefesto_dualsense4unix.app.widgets.segmented_selector import (
        SegmentedSelector,
    )

    estado = mode_selector_state(entry)
    if estado is None:
        return None
    itens, ativo = estado

    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    chave = Gtk.Label(label=_("O jogo vê como") + ":")
    chave.set_xalign(0.0)
    chave.get_style_context().add_class("dim-label")
    row.pack_start(chave, False, False, 0)

    seletor = SegmentedSelector()
    seletor.set_items(itens)
    seletor.set_active_id(ativo)
    # Insensitive de propósito: visual idêntico aos segmentados do app, mas
    # não-clicável — não existe troca por software para oferecer.
    with contextlib.suppress(Exception):
        seletor.set_sensitive(False)
    seletor.set_tooltip_text(MODE_SELECTOR_TOOLTIP)
    row.pack_start(seletor, False, False, 0)

    sub = Gtk.Label(label=MODE_SELECTOR_SUBTITLE)
    sub.set_line_wrap(True)
    sub.set_xalign(0.0)
    sub.set_max_width_chars(52)
    sub.get_style_context().add_class("dim-label")
    return row, sub


def show_external_controller(
    parent: Gtk.Window, entry: dict[str, Any], slot: int | None = None
) -> None:
    """Ficha READ-ONLY de um controle externo (8BIT-02) — a "aba secreta".

    Abre só para o controle clicado no seletor do topo. Mostra identidade
    honesta (tipo, como conectou, driver) + o aviso do Nintendo/8BitDo por
    Bluetooth. ``slot`` = número GLOBAL de co-op (o MESMO do LED de player), pra
    GUI e LED não discordarem. NÃO controla nada: o Hefesto não mexe nesses
    controles — eles funcionam pelo driver do Linux + Steam. Modal, run/destroy.
    """
    from hefesto_dualsense4unix.app.actions.external_controllers import (
        detail_rows,
        friendly_type,
        mode_guidance,
        nintendo_bt_warning,
    )

    dialog = Gtk.Dialog(
        title=friendly_type(entry),
        parent=parent,
        modal=True,
        destroy_with_parent=True,
    )
    # Popup NÃO-INTERATIVO com o visual da GUI (Drácula): a classe da janela faz
    # o CSS screen-wide (theme.css) pintar fundo/labels/botão como no resto do
    # app — sem isso o diálogo herdava o tema claro do sistema (branco no COSMIC).
    _apply_app_theme(dialog)
    dialog.add_button(_("Fechar"), Gtk.ResponseType.CLOSE)
    dialog.set_default_response(Gtk.ResponseType.CLOSE)
    content = dialog.get_content_area()
    content.set_spacing(10)
    content.set_border_width(16)

    # Número GLOBAL de co-op — o MESMO que o LED de player do controle mostra,
    # para GUI e LED nunca discordarem (o 1º externo continua a contagem dos
    # DualSense: com 2 DualSense, este é o Controle 3).
    if slot is not None:
        slot_lbl = Gtk.Label()
        slot_lbl.set_markup(
            f'<span size="x-large" weight="bold">{_("Controle")} {slot}</span>'
        )
        slot_lbl.set_xalign(0.0)
        content.pack_start(slot_lbl, False, False, 0)

    intro = Gtk.Label()
    intro.set_markup(
        _(
            "<b>Este controle funciona</b> — pelo Linux e pela Steam. O Hefesto "
            "só o mostra aqui; não mexe nele (nada de cor, gatilho ou co-op "
            "virtual: isso é exclusivo do DualSense)."
        )
    )
    intro.set_line_wrap(True)
    intro.set_xalign(0.0)
    intro.set_max_width_chars(52)
    content.pack_start(intro, False, False, 0)

    grid = Gtk.Grid()
    grid.set_row_spacing(6)
    grid.set_column_spacing(14)
    for row, (rotulo, valor) in enumerate(detail_rows(entry)):
        chave = Gtk.Label(label=str(rotulo) + ":")
        chave.set_xalign(1.0)
        chave.get_style_context().add_class("dim-label")
        val = Gtk.Label(label=str(valor))
        val.set_xalign(0.0)
        val.set_line_wrap(True)
        grid.attach(chave, 0, row, 1, 1)
        grid.attach(val, 1, row, 1, 1)
    content.pack_start(grid, False, False, 0)

    # Xbox/Nintendo (como o jogo o enxerga): é modo de HARDWARE do controle, não
    # um toggle de software — a ficha DETECTA o modo atual e ORIENTA a troca +
    # o trade-off (X-input/Xbox = à prova de travas por foge do hid-nintendo;
    # Switch/Nintendo = gyro, mas instável por Bluetooth). GUI-05/P4: o modo
    # detectado aparece num segmentado READ-ONLY (Nintendo | Xbox) do padrão da
    # casa — a linha de texto da grade virou este widget (fonte única).
    modo_widgets = _external_mode_row(entry)
    if modo_widgets is not None:
        modo_row, modo_sub = modo_widgets
        content.pack_start(modo_row, False, False, 0)
        content.pack_start(modo_sub, False, False, 0)

    guia = mode_guidance(entry)
    if guia is not None:
        _atual, orient = guia
        modo_lbl = Gtk.Label(label=orient)
        modo_lbl.set_line_wrap(True)
        modo_lbl.set_xalign(0.0)
        modo_lbl.set_max_width_chars(52)
        modo_lbl.get_style_context().add_class("dim-label")
        content.pack_start(modo_lbl, False, False, 0)

    aviso = nintendo_bt_warning(entry)
    if aviso:
        warn = Gtk.Label()
        # &#9888; (WARNING SIGN) via NCR — sobrevive ao sanitizer de emojis.
        warn.set_markup(
            f'<span foreground="#e0a020">&#9888; {_escape_markup(aviso)}</span>'
        )
        warn.set_line_wrap(True)
        warn.set_xalign(0.0)
        warn.set_max_width_chars(52)
        content.pack_start(warn, False, False, 0)

    dialog.show_all()
    dialog.run()
    dialog.destroy()


__all__ = [
    "confirm_delete_profile",
    "confirm_downgrade_match_to_any",
    "confirm_restore_default",
    "prompt_import_conflict",
    "prompt_overwrite_existing",
    "prompt_profile_name",
    "show_external_controller",
]
