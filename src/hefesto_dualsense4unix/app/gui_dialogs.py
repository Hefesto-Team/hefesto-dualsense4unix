"""Helpers de diálogo GTK reutilizáveis para a GUI do Hefesto - Dualsense4Unix.

Todos os diálogos são modais e bloqueantes (run/destroy), adequados para
uso na thread principal GTK. Nenhum acessa IPC diretamente.
"""
from __future__ import annotations

from typing import cast

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402


def prompt_profile_name(
    parent: Gtk.Window,
    default_name: str = "",
) -> str | None:
    """Exibe diálogo modal para entrada de nome de perfil.

    Retorna o nome digitado (stripped) ou None se o usuário cancelou.
    Campo pré-preenchido com ``default_name``.
    """
    dialog = Gtk.Dialog(
        title="Salvar Perfil",
        parent=parent,
        modal=True,
        destroy_with_parent=True,
    )
    dialog.add_button("Cancelar", Gtk.ResponseType.CANCEL)
    dialog.add_button("Salvar", Gtk.ResponseType.OK)
    dialog.set_default_response(Gtk.ResponseType.OK)

    content = dialog.get_content_area()
    content.set_spacing(8)
    content.set_margin_top(12)
    content.set_margin_bottom(12)
    content.set_margin_start(16)
    content.set_margin_end(16)

    label = Gtk.Label(label="Nome do perfil:")
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
        text=f"Perfil '{name}' já existe.",
    )
    dialog.format_secondary_text("Deseja sobrescrever o perfil existente?")
    dialog.add_button("Cancelar", Gtk.ResponseType.CANCEL)
    dialog.add_button("Sobrescrever", Gtk.ResponseType.OK)
    dialog.set_default_response(Gtk.ResponseType.OK)

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
        text=f"Perfil '{name}' já existe.",
    )
    dialog.format_secondary_text(
        "Escolha o que fazer com o perfil importado:"
    )
    dialog.add_button("Cancelar", Gtk.ResponseType.CANCEL)
    dialog.add_button("Renomear", Gtk.ResponseType.REJECT)
    dialog.add_button("Sobrescrever", Gtk.ResponseType.OK)
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
        text="Restaurar perfil original?",
    )
    dialog.format_secondary_text(
        "Isso vai restaurar o 'meu_perfil' para a cópia original (Navegação). "
        "As suas alterações serão perdidas. Continuar?"
    )
    dialog.add_button("Cancelar", Gtk.ResponseType.CANCEL)
    dialog.add_button("Restaurar", Gtk.ResponseType.OK)
    dialog.set_default_response(Gtk.ResponseType.CANCEL)

    response = dialog.run()
    dialog.destroy()
    return bool(response == Gtk.ResponseType.OK)


__all__ = [
    "confirm_restore_default",
    "prompt_import_conflict",
    "prompt_overwrite_existing",
    "prompt_profile_name",
]
