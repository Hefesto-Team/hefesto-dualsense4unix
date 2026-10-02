"""Helpers de diálogo GTK reutilizáveis para a GUI do Hefesto - DualSense4Unix.

Todos os diálogos são modais e síncronos, adequados para uso na thread
principal GTK. Nenhum acessa IPC diretamente.

DIÁLOGO-QUE-MATA-A-JANELA-01 (06/08/2026): nenhum deles chama ``dialog.run()``
direto — TODOS passam por ``executar_dialogo``, o envelope da casa, que MOSTRA
o diálogo de verdade e garante que ele nunca segure a janela dela refém.
Ver a docstring de ``executar_dialogo`` para o porquê de cada camada.
"""
from __future__ import annotations

import contextlib
from typing import Any, cast

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402

from hefesto_dualsense4unix.utils.i18n import _  # noqa: E402
from hefesto_dualsense4unix.utils.logging_config import get_logger  # noqa: E402

logger = get_logger(__name__)


PRAZO_ATE_O_SOCORRO_MS = 1500

PRAZO_ATE_DESISTIR_MS = 2000

_ULTIMO_SOCORRO: str | None = None

_EM_CURSO: list[Any] = []


def ultimo_socorro() -> str | None:
    """Nome do diálogo cancelado pelo socorro, ou ``None``."""
    return _ULTIMO_SOCORRO


def dialogo_na_tela(dialog: Any) -> bool:
    """O diálogo existe no servidor gráfico neste instante?"""
    try:
        janela = dialog.get_window()
        return bool(janela is not None and janela.is_visible())
    except Exception:
        return True


def dialogo_alcancavel(dialog: Any) -> bool:
    """Ela consegue RESPONDER este diálogo agora? Na tela **e** com o foco."""
    if not dialogo_na_tela(dialog):
        return False
    try:
        return bool(dialog.is_active())
    except Exception:
        return True


def presentar_dialogos_em_curso() -> int:
    """Traz para a frente todo diálogo à espera de resposta; devolve quantos."""
    trazidos = 0
    for dialog in list(_EM_CURSO):
        with contextlib.suppress(Exception):
            dialog.set_keep_above(True)
            dialog.deiconify()
            dialog.show_all()
            dialog.present()
            trazidos += 1
    return trazidos


def executar_dialogo(
    dialog: Any,
    *,
    nome: str,
    resposta_de_socorro: int | None = None,
) -> int:
    """MOSTRA o diálogo, espera a resposta dela — e nunca estrangula a janela.

    O ÚNICO ``dialog.run()`` autorizado em ``app/`` (há portão por AST em
    ``tests/unit/test_dialogo_nao_mata_a_janela.py``). Devolve o ``ResponseType``.

    O DEFEITO QUE ISTO CURA (medido em 06/08/2026, 20h22)
    -----------------------------------------------------
    Ela baixou a prioridade do perfil "Vitória" de 78 para 0 e a janela morreu:
    *"interface travou legal aqui. nem consigo fazer nada nem fechar"*. O
    ``py-spy`` pegou a thread principal parada em ``dialog.run()`` dentro do
    ``confirm_downgrade_priority`` — e a foto da tela dela não tinha diálogo
    nenhum. O processo estava vivo (1,4% de CPU, laço do GTK em ``poll``),
    esperando uma resposta que ela não tinha como dar.

    São DUAS coisas somadas, e é por isso que o remédio tem duas camadas:

    1. ``gtk_dialog_run()`` só faz ``gtk_widget_show()`` no diálogo. Ele
       **não** chama ``gtk_window_present()`` — não pede levantamento nem foco
       ao compositor. Num gerenciador maduro o diálogo transiente é levantado
       e focado de graça; no ``cosmic-comp`` sobre XWayland, um diálogo apenas
       mostrado pode ficar sem foco (e, ao que a foto dela indica, sem aparecer).
       **Grau: SUSPEITA COM MECANISMO** — o mecanismo está lido no fonte do
       GTK e o sintoma bate, mas não reproduzi o COSMIC em bancada;
    2. ``modal=True`` + laço aninhado = a janela inteira presa a um diálogo que
       ela não vê. Cada clique é engolido pelo grab, e nem o "fechar" responde.
       **Grau: MEDIDO** (a pilha do ``py-spy``).

    AS CAMADAS, E POR QUE ESTAS
    ---------------------------
    * **Mostrar de verdade** (``show_all`` + ``present``) antes do laço: ataca
      a causa (1) com a API que o GTK oferece para exatamente isto;
    * **Vigia com socorro e desistência**: aos ``PRAZO_ATE_O_SOCORRO_MS``, se o
      diálogo está inalcançável (ver ``dialogo_alcancavel``), tenta o resgate
      (``deiconify`` + ``show_all`` + ``present`` + ``keep_above``); aos
      ``PRAZO_ATE_DESISTIR_MS`` seguintes, se ele continua inalcançável, SOLTA
      A MODALIDADE e responde por ela com ``resposta_de_socorro``. MEDIDO em
      06/08/2026: ``GLib.timeout_add`` e ``GLib.idle_add`` **rodam** dentro do
      laço aninhado do ``run()``, e ``dialog.response(...)`` de dentro de um
      deles faz o ``run()`` retornar — é o que torna esta camada possível;
    * **A trava do "já foi visto"**, que vale para o FOCO e nunca para a TELA
      (ver ``_precisa_de_socorro``): um Alt+Tab dela não pode virar
      cancelamento, mas um diálogo que SUMIU do servidor estrangula a janela
      mesmo tendo aparecido um segundo antes — e aí nenhum histórico salva;
    * **O vigia julga UMA vez, nos primeiros ~3,5 s**, e depois se cala para
      sempre. É escolha, e o motivo é concreto: sob X11 trocar de área de
      trabalho DESMAPEIA a janela, e um vigia permanente leria isso como
      estrangulamento e cancelaria o diálogo pelas costas dela. Nos primeiros
      segundos o compositor ou mostra a janela ou não mostra — depois disso,
      sumiço é gesto dela. O preço declarado: um diálogo que aparece e some
      DEPOIS do julgamento volta a prender a janela, e para esse caso resta a
      saída externa (``presentar_dialogos_em_curso``, via ``SIGUSR1``);
    * **Resposta de socorro = CANCELAR**: em todos os diálogos desta casa o
      cancelar é o lado que **não muda nada**. O aviso continua existindo (é
      VETO: baixar prioridade em silêncio já custou configuração dela); o que
      muda é que um aviso invisível deixa de custar a sessão inteira. Ela
      reclica "Salvar" e nada foi perdido.

    POR QUE NÃO O ÓBVIO — TROCAR TUDO POR ``connect("response")``
    -------------------------------------------------------------
    É o padrão que ``daemon_actions._show_restart_error`` já usa, e ele **não
    resolveria este defeito**: o que prende a janela é o ``modal=True`` (o grab
    do GTK), não o laço. Um diálogo modal invisível e não-bloqueante estrangula
    a janela do mesmo jeito. E o custo seria alto no lugar errado: os três
    avisos vivem no meio de ``on_profile_save``, uma transação com seis saídas
    antecipadas (sobrescrita, rename, delete do antigo, migração do marker do
    daemon) — parti-la em continuações para curar um defeito de JANELA é
    convidar um defeito de DADO. O envelope cura os dez diálogos de uma vez,
    sem tocar em nenhuma transação.
    """
    desarmar = _mostrar_e_vigiar(dialog, nome=nome, resposta_de_socorro=resposta_de_socorro)
    _EM_CURSO.append(dialog)
    try:
        resposta = dialog.run()
    finally:
        with contextlib.suppress(ValueError):
            _EM_CURSO.remove(dialog)
        desarmar()
    return cast(int, resposta)


def mostrar_dialogo_assincrono(
    dialog: Any,
    *,
    nome: str,
    resposta_de_socorro: int | None = None,
) -> None:
    """Mostra um diálogo que responde por sinal, com a MESMA rede do bloqueante."""
    desarmar = _mostrar_e_vigiar(dialog, nome=nome, resposta_de_socorro=resposta_de_socorro)
    _EM_CURSO.append(dialog)

    def _ao_responder(*_args: Any) -> None:
        with contextlib.suppress(ValueError):
            _EM_CURSO.remove(dialog)
        desarmar()

    with contextlib.suppress(Exception):
        dialog.connect("response", _ao_responder)


def _mostrar_e_vigiar(
    dialog: Any,
    *,
    nome: str,
    resposta_de_socorro: int | None = None,
) -> Any:
    """Mostra de verdade e arma o vigia; devolve o `desarmar()`."""
    global _ULTIMO_SOCORRO
    _ULTIMO_SOCORRO = None
    socorro = (
        Gtk.ResponseType.CANCEL if resposta_de_socorro is None else resposta_de_socorro
    )
    estado: dict[str, Any] = {"visto": False, "vigias": []}

    def _agendar(prazo_ms: int, callback: Any) -> None:
        try:
            from gi.repository import GLib
        except Exception:  # pragma: no cover — ambiente sem GLib
            return
        with contextlib.suppress(Exception):
            estado["vigias"].append(GLib.timeout_add(prazo_ms, callback))

    def _latch(*_args: Any) -> None:
        if dialogo_alcancavel(dialog):
            estado["visto"] = True

    def _precisa_de_socorro() -> bool:
        """A trava do "já foi visto" vale para o FOCO, nunca para a TELA."""
        if not dialogo_na_tela(dialog):
            return True
        if estado["visto"]:
            return False
        return not dialogo_alcancavel(dialog)

    def _desistir() -> bool:
        global _ULTIMO_SOCORRO
        if not _precisa_de_socorro():
            return False
        logger.error("dialogo_invisivel_desistindo", dialogo=nome)
        _ULTIMO_SOCORRO = nome
        with contextlib.suppress(Exception):
            dialog.set_modal(False)
        with contextlib.suppress(Exception):
            dialog.response(socorro)
        return False

    def _socorrer() -> bool:
        if not _precisa_de_socorro():
            return False
        logger.warning("dialogo_sem_foco_socorro", dialogo=nome)
        with contextlib.suppress(Exception):
            dialog.set_keep_above(True)
        for gesto in ("deiconify", "show_all", "present"):
            with contextlib.suppress(Exception):
                getattr(dialog, gesto)()
        _agendar(PRAZO_ATE_DESISTIR_MS, _desistir)
        return False

    handler: Any = None
    with contextlib.suppress(Exception):
        handler = dialog.connect("notify::is-active", _latch)
    with contextlib.suppress(Exception):
        dialog.set_position(
            Gtk.WindowPosition.CENTER_ON_PARENT
            if dialog.get_transient_for() is not None
            else Gtk.WindowPosition.CENTER
        )
    with contextlib.suppress(Exception):
        dialog.show_all()
    with contextlib.suppress(Exception):
        dialog.present()

    _agendar(PRAZO_ATE_O_SOCORRO_MS, _socorrer)

    def _desarmar() -> None:
        for fonte in estado["vigias"]:
            with contextlib.suppress(Exception):
                from gi.repository import GLib

                GLib.source_remove(fonte)
        estado["vigias"] = []
        if handler is not None:
            with contextlib.suppress(Exception):
                dialog.disconnect(handler)

    return _desarmar


def _apply_app_theme(dialog: Any) -> None:
    """Aplica a classe de tema do app ao toplevel do diálogo (GUI-05/P5)."""
    with contextlib.suppress(Exception):
        dialog.get_style_context().add_class("hefesto-dualsense4unix-window")


def prompt_profile_name(
    parent: Gtk.Window,
    default_name: str = "",
) -> str | None:
    """Exibe diálogo modal para entrada de nome de perfil."""
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
    response = executar_dialogo(dialog, nome="salvar_perfil_nome")
    name = entry.get_text().strip()
    dialog.destroy()

    if response == Gtk.ResponseType.OK and name:
        return cast(str, name)
    return None


def prompt_overwrite_existing(
    parent: Gtk.Window,
    name: str,
) -> bool:
    """Pergunta se o usuário deseja sobrescrever um perfil de mesmo nome."""
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

    response = executar_dialogo(dialog, nome="sobrescrever_perfil")
    dialog.destroy()
    return bool(response == Gtk.ResponseType.OK)


def confirm_downgrade_match_to_any(
    parent: Gtk.Window,
    name: str,
    regra_atual: str | None = None,
) -> bool:
    """Confirma transformar um perfil de programa específico em "Sempre"."""
    titulo = (
        _("O perfil '%s' vale só em programas específicos.") % name
        if regra_atual is None
        else _("O perfil '%s' não vale para tudo hoje — hoje ele é: %s.")
        % (name, regra_atual)
    )
    dialog = Gtk.MessageDialog(
        parent=parent,
        modal=True,
        destroy_with_parent=True,
        message_type=Gtk.MessageType.WARNING,
        buttons=Gtk.ButtonsType.NONE,
        text=titulo,
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

    response = executar_dialogo(dialog, nome="rebaixar_regra_para_sempre")
    dialog.destroy()
    return bool(response == Gtk.ResponseType.OK)


def confirm_downgrade_match_to_manual(
    parent: Gtk.Window,
    name: str,
    regra_atual: str | None = None,
) -> bool:
    """Confirma tirar o alvo de um perfil, deixando-o só-manual."""
    titulo = (
        _("O perfil '%s' vai deixar de entrar sozinho.") % name
        if regra_atual is None
        else _("O perfil '%s' vai deixar de entrar sozinho — hoje ele é: %s.")
        % (name, regra_atual)
    )
    dialog = Gtk.MessageDialog(
        parent=parent,
        modal=True,
        destroy_with_parent=True,
        message_type=Gtk.MessageType.WARNING,
        buttons=Gtk.ButtonsType.NONE,
        text=titulo,
    )
    _apply_app_theme(dialog)
    dialog.format_secondary_text(
        _(
            "Com os três campos do Modo avançado em branco, o perfil fica "
            "\"Só manual (nunca ativa sozinho)\": ele só entra quando você o "
            "escolher na lista, e apaga os programas em que ele valia. "
            "Tem certeza?"
        )
    )
    dialog.add_button(_("Cancelar"), Gtk.ResponseType.CANCEL)
    dialog.add_button(_("Deixar só na mão"), Gtk.ResponseType.OK)
    dialog.set_default_response(Gtk.ResponseType.CANCEL)

    response = executar_dialogo(dialog, nome="rebaixar_regra_para_so_manual")
    dialog.destroy()
    return bool(response == Gtk.ResponseType.OK)


def confirm_downgrade_priority(
    parent: Gtk.Window,
    name: str,
    de: int,
    para: int,
) -> bool:
    """Confirma REBAIXAR a prioridade de um perfil que já existe em disco."""
    dialog = Gtk.MessageDialog(
        parent=parent,
        modal=True,
        destroy_with_parent=True,
        message_type=Gtk.MessageType.WARNING,
        buttons=Gtk.ButtonsType.NONE,
        text=_("O perfil '%s' vai perder prioridade: de %d para %d.")
        % (name, de, para),
    )
    _apply_app_theme(dialog)
    dialog.format_secondary_text(
        _(
            "Quem tem prioridade maior vence a disputa por uma janela. Com a "
            "prioridade menor, este perfil pode deixar de entrar onde entrava. "
            "Tem certeza?"
        )
    )
    dialog.add_button(_("Cancelar"), Gtk.ResponseType.CANCEL)
    dialog.add_button(_("Baixar a prioridade"), Gtk.ResponseType.OK)
    dialog.set_default_response(Gtk.ResponseType.OK)

    response = executar_dialogo(dialog, nome="rebaixar_prioridade")
    dialog.destroy()
    return bool(response == Gtk.ResponseType.OK)


def confirm_discard_pending_edits(
    parent: Gtk.Window,
    ativado: str,
    editando: str | None = None,
) -> bool:
    """Ativar um perfil com edição não salva na tela: descartar o que está lá?"""
    dialog = Gtk.MessageDialog(
        parent=parent,
        modal=True,
        destroy_with_parent=True,
        message_type=Gtk.MessageType.QUESTION,
        buttons=Gtk.ButtonsType.NONE,
        text=_("Perfil ativado: '%s'. E as suas alterações não salvas?")
        % ativado,
    )
    _apply_app_theme(dialog)
    dialog.format_secondary_text(
        _(
            "As abas mostram alterações de '%s' que você ainda não salvou. "
            "Mostrar o perfil ativado descarta essas alterações."
        )
        % (editando or "—")
    )
    dialog.add_button(_("Manter minhas alterações"), Gtk.ResponseType.CANCEL)
    dialog.add_button(_("Descartar e mostrar o ativado"), Gtk.ResponseType.OK)
    dialog.set_default_response(Gtk.ResponseType.CANCEL)

    response = executar_dialogo(dialog, nome="descartar_edicao_pendente")
    dialog.destroy()
    return bool(response == Gtk.ResponseType.OK)


def prompt_import_conflict(
    parent: Gtk.Window,
    name: str,
) -> str | None:
    """Exibe diálogo de conflito ao importar perfil com nome já existente."""
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

    response = executar_dialogo(dialog, nome="conflito_ao_importar")
    dialog.destroy()

    if response == Gtk.ResponseType.OK:
        return "sobrescrever"
    if response == Gtk.ResponseType.REJECT:
        return "renomear"
    return None


def confirm_restore_default(parent: Gtk.Window) -> bool:
    """Pede confirmação antes de restaurar o perfil padrão ao original."""
    dialog = Gtk.MessageDialog(
        parent=parent,
        modal=True,
        destroy_with_parent=True,
        message_type=Gtk.MessageType.WARNING,
        buttons=Gtk.ButtonsType.NONE,
        text=_("Restaurar perfil original?"),
    )
    _apply_app_theme(dialog)
    from hefesto_dualsense4unix.profiles.loader import NOME_DO_PADRAO

    dialog.format_secondary_text(
        _(
            "Isso vai restaurar o '{nome}' para a configuração padrão "
            "de fábrica (aplica-se a todos os apps). As suas alterações serão "
            "perdidas. Continuar?"
        ).format(nome=NOME_DO_PADRAO)
    )
    dialog.add_button(_("Cancelar"), Gtk.ResponseType.CANCEL)
    dialog.add_button(_("Restaurar"), Gtk.ResponseType.OK)
    dialog.set_default_response(Gtk.ResponseType.CANCEL)

    response = executar_dialogo(dialog, nome="restaurar_perfil_original")
    dialog.destroy()
    return bool(response == Gtk.ResponseType.OK)


def confirm_delete_profile(
    parent: Gtk.Window, name: str, aviso: str | None = None
) -> bool:
    """Pede confirmação antes de remover PERMANENTEMENTE um perfil."""
    dialog = Gtk.MessageDialog(
        parent=parent,
        modal=True,
        destroy_with_parent=True,
        message_type=Gtk.MessageType.WARNING,
        buttons=Gtk.ButtonsType.NONE,
        text=_("Remover o perfil '%s'?") % name,
    )
    _apply_app_theme(dialog)
    permanente = _("Esta ação é permanente e não pode ser desfeita.")
    dialog.format_secondary_text(
        f"{aviso}\n\n{permanente}" if aviso else permanente
    )
    dialog.add_button(_("Cancelar"), Gtk.ResponseType.CANCEL)
    dialog.add_button(_("Remover"), Gtk.ResponseType.OK)
    dialog.set_default_response(Gtk.ResponseType.CANCEL)

    response = executar_dialogo(dialog, nome="remover_perfil")
    dialog.destroy()
    return bool(response == Gtk.ResponseType.OK)


def _escape_markup(text: str) -> str:
    """Escapa `&`/`<`/`>` para markup Pango (sem depender de GLib no import)."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _external_mode_row(entry: dict[str, Any]) -> tuple[Any, Any] | None:
    """(linha com o segmentado read-only do modo, subtítulo) — ou ``None``."""
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
    """Ficha READ-ONLY de um controle externo (8BIT-02) — a "aba secreta"."""
    from hefesto_dualsense4unix.app.actions.external_controllers import (
        detail_rows,
        friendly_type,
        mode_guidance,
        nintendo_bt_warning,
        slot_label,
    )

    dialog = Gtk.Dialog(
        title=friendly_type(entry),
        parent=parent,
        modal=True,
        destroy_with_parent=True,
    )
    _apply_app_theme(dialog)
    dialog.add_button(_("Fechar"), Gtk.ResponseType.CLOSE)
    dialog.set_default_response(Gtk.ResponseType.CLOSE)
    content = dialog.get_content_area()
    content.set_spacing(10)
    content.set_border_width(16)

    # DualSense: com 2 DualSense, este é o Controle 3). NUMA-05: sempre exibe
    slot_lbl = Gtk.Label()
    slot_lbl.set_markup(
        f'<span size="x-large" weight="bold">{_("Controle")} '
        f"{slot_label(slot)}</span>"
    )
    slot_lbl.set_xalign(0.0)
    content.pack_start(slot_lbl, False, False, 0)

    intro = Gtk.Label()
    intro.set_markup(
        _(
            "<b>Este controle funciona</b> — gerenciado pelo Linux e pela "
            "Steam; o Hefesto não mexe nele."
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
        warn.set_markup(
            f'<span foreground="#ffb86c">&#9888; {_escape_markup(aviso)}</span>'
        )
        warn.set_line_wrap(True)
        warn.set_xalign(0.0)
        warn.set_max_width_chars(52)
        content.pack_start(warn, False, False, 0)

    dialog.show_all()
    executar_dialogo(
        dialog,
        nome="ficha_controle_externo",
        resposta_de_socorro=Gtk.ResponseType.CLOSE,
    )
    dialog.destroy()


__all__ = [
    "PRAZO_ATE_DESISTIR_MS",
    "PRAZO_ATE_O_SOCORRO_MS",
    "confirm_delete_profile",
    "confirm_discard_pending_edits",
    "confirm_downgrade_match_to_any",
    "confirm_downgrade_match_to_manual",
    "confirm_downgrade_priority",
    "confirm_restore_default",
    "dialogo_alcancavel",
    "dialogo_na_tela",
    "executar_dialogo",
    "presentar_dialogos_em_curso",
    "prompt_import_conflict",
    "prompt_overwrite_existing",
    "prompt_profile_name",
    "show_external_controller",
    "ultimo_socorro",
]
