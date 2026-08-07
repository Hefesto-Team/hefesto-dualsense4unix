"""Helpers de diálogo GTK reutilizáveis para a GUI do Hefesto - Dualsense4Unix.

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


# ---------------------------------------------------------------------------
# DIÁLOGO-QUE-MATA-A-JANELA-01 — o envelope que impede o estrangulamento
# ---------------------------------------------------------------------------

#: Prazo (ms) entre abrir o diálogo e a primeira tentativa de SOCORRO.
#:
#: Folgado de propósito: 1,5 s é muito mais do que qualquer compositor leva
#: para mapear e focar um diálogo que ele VAI mostrar, e curto o bastante para
#: ela não chegar a achar que a janela morreu.
PRAZO_ATE_O_SOCORRO_MS = 1500

#: Prazo (ms) entre o socorro e a DESISTÊNCIA (responder por ela e sair).
PRAZO_ATE_DESISTIR_MS = 2000

#: Nome do último diálogo que a casa teve de cancelar por não conseguir
#: aparecer. Lido por quem chama, para o aviso na barra ser honesto em vez de
#: um "Operação cancelada." que ela não pediu. Ver ``ultimo_socorro``.
_ULTIMO_SOCORRO: str | None = None

#: Diálogos com laço em curso — a lista que o ``presentar_dialogos_em_curso``
#: usa como saída de emergência externa (SIGUSR1). Nunca mais de um elemento na
#: prática (todos são modais), mas é lista para não mentir sobre aninhamento.
_EM_CURSO: list[Any] = []


def ultimo_socorro() -> str | None:
    """Nome do diálogo cancelado pelo socorro, ou ``None``.

    Zerado a cada ``executar_dialogo``, então só é verdadeiro sobre o diálogo
    que acabou de fechar. Existe para o chamador poder dizer a ela *"o aviso
    não conseguiu aparecer; nada foi alterado"* em vez do genérico
    *"Operação cancelada."*, que a faria procurar um clique que ela não deu.
    """
    return _ULTIMO_SOCORRO


def dialogo_na_tela(dialog: Any) -> bool:
    """O diálogo existe no servidor gráfico neste instante?

    MEDIDO em 06/08/2026 (Xvfb, GTK 3.24, PyGObject 3.48): as perguntas óbvias
    MENTEM. Com o ``GdkWindow`` do diálogo retirado do servidor
    (``WITHDRAWN`` — o mais próximo que se reproduz em bancada do "ela não vê
    nada"), o GTK continua respondendo::

        get_mapped()  -> True     (mente)
        get_visible() -> True     (mente)
        get_window().is_visible() -> False   (a verdade)
        is_active()   -> False    (a verdade)

    Daí a pergunta ser feita ao ``GdkWindow``, e não ao widget. Em falha de
    medição devolve ``True``: "não sei medir" nunca pode virar um cancelamento
    que ela não pediu.
    """
    try:
        janela = dialog.get_window()
        return bool(janela is not None and janela.is_visible())
    except Exception:
        return True


def dialogo_alcancavel(dialog: Any) -> bool:
    """Ela consegue RESPONDER este diálogo agora? Na tela **e** com o foco.

    O segundo termo é **foco de teclado**, não pixels — e isso é uma escolha,
    não uma aproximação. Um diálogo que o compositor apresentou recebe o foco;
    com o foco ela tem, no mínimo, o ``Esc``, que é a saída padrão de todo
    ``GtkDialog``. Sem foco, o diálogo é **inalcançável por definição**: não há
    clique nem tecla que chegue nele, e é esse o estado em que a janela dela
    morreu em 06/08/2026.
    """
    if not dialogo_na_tela(dialog):
        return False
    try:
        return bool(dialog.is_active())
    except Exception:
        return True


def presentar_dialogos_em_curso() -> int:
    """Traz para a frente todo diálogo à espera de resposta; devolve quantos.

    A SEGUNDA saída de emergência, e a única que não depende de o produto
    concordar com o diagnóstico: o app já instala ``SIGUSR1 -> show_window``
    (``app.py``), e está MEDIDO (06/08/2026) que ``GLib.idle_add`` **roda
    dentro do laço aninhado do ``dialog.run()``** — ou seja, um
    ``kill -USR1 <pid>`` de fora alcança a janela mesmo com um diálogo
    bloqueante aberto. Sem esta função o sinal só levantava a janela
    principal, que é justamente a que está sob o grab modal; com ela, levanta
    quem está segurando o grab.
    """
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
    """Mostra um diálogo que responde por sinal, com a MESMA rede do bloqueante.

    O irmão assíncrono de :func:`executar_dialogo`, e ele existe por um achado
    de 06/08/2026 que a primeira cura deixou passar.

    O QUE A PRIMEIRA CURA ERROU
    ---------------------------
    A docstring de ``executar_dialogo`` já escrevia a frase certa — *"um diálogo
    modal invisível e não-bloqueante estrangula a janela do mesmo jeito"* — e
    mesmo assim o envelope só cobriu quem chama ``run()``. Ficou de fora o
    ``_on_home_shutdown_clicked`` da aba Início ("Desligar o Hefesto?"), que usa
    ``modal=True`` + ``connect("response")`` + ``show()``.

    **MEDIDO por verificação adversarial:** o ``show()`` de um diálogo modal já
    instala o grab do GTK. Com o ``GdkWindow`` fora do servidor — o estado dela
    — a janela principal perde os TRÊS canais: clique, tecla e o "X" do
    gerenciador (0/0/0, contra 2/1/1 no controle). E nenhuma das duas saídas
    alcançava: o vigia não roda (não passa pelo envelope) e
    ``presentar_dialogos_em_curso`` devolve zero, porque ``_EM_CURSO`` não o
    conhece.

    Ou seja: a cura fechava a porta que ela atravessou e deixava a do lado
    aberta — com um portão por AST que jurava não haver mais nenhuma. Por isso
    o portão passou a olhar ``modal=True`` + ``show()``, e não só ``run()``.

    COMO USAR
    ---------
    No lugar de ``dialog.show()``, depois de ligar o seu ``connect("response")``.
    O diálogo sai de ``_EM_CURSO`` sozinho quando a resposta chega — inclusive a
    resposta de socorro, que aqui **também** dispara o ``response`` do chamador,
    então a transação dele fecha pelo caminho normal.
    """
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
    """Mostra de verdade e arma o vigia; devolve o `desarmar()`.

    O miolo compartilhado por :func:`executar_dialogo` e
    :func:`mostrar_dialogo_assincrono`. Está separado de propósito: os dois
    caminhos precisam da MESMA rede, e duas cópias dela seriam a próxima
    divergência a custar uma sessão dela.
    """
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
        """A trava do "já foi visto" vale para o FOCO, nunca para a TELA.

        Dois estados diferentes se parecem, e tratá-los igual quebra um dos
        dois:

        * **sumiu da tela** (``GdkWindow`` fora do servidor): estrangulamento,
          e nenhum histórico salva — mesmo que ela tenha visto o diálogo um
          segundo antes, agora não há o que clicar. Sem latch;
        * **está na tela, sem foco**: pode ser só um Alt+Tab dela. Aqui a trava
          vale: um diálogo que ela JÁ alcançou uma vez nunca mais é cancelado
          pelo vigia — o remédio não pode repetir a doença.
        """
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
        # Solta o grab ANTES de responder: mesmo que o `response` falhe, a
        # janela dela já voltou a aceitar clique.
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
    # `run()` só faria `gtk_widget_show`; o `present` é o pedido de LEVANTAR e
    # FOCAR que faltava, e é a cura da causa (1) descrita acima.
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

    response = executar_dialogo(dialog, nome="sobrescrever_perfil")
    dialog.destroy()
    return bool(response == Gtk.ResponseType.OK)


def confirm_downgrade_match_to_any(
    parent: Gtk.Window,
    name: str,
    regra_atual: str | None = None,
) -> bool:
    """Confirma transformar um perfil de programa específico em "Sempre".

    COR-A: desligar "Modo avançado" num perfil de jogo e Salvar trocava o alvo
    (window_class/título) por MatchAny em SILÊNCIO — o perfil que valia só num
    jogo passava a valer para TUDO, sem aviso e com o toast "Perfil salvo".
    Retorna True se o usuário confirmou a mudança, False se cancelou.

    SALVAR-NAO-REBAIXA-02 (leva 2, 05/08): ``regra_atual`` é o rótulo do que o
    perfil É HOJE, na língua da lista ("Quando usar"). Sem ele o diálogo
    continua dizendo a frase da COR-A, que só é verdade para o perfil de
    programa específico — e o chamador passou a avisar também no perfil
    *"Só manual (nunca ativa sozinho)"*, onde afirmar "vale só em programas
    específicos" seria o aviso mentindo sobre o que ela está prestes a perder.
    """
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


def confirm_downgrade_priority(
    parent: Gtk.Window,
    name: str,
    de: int,
    para: int,
) -> bool:
    """Confirma REBAIXAR a prioridade de um perfil que já existe em disco.

    SALVAR-NAO-REBAIXA-02 (leva 2, 05/08). O aviso de rebaixamento que esta
    casa tinha (``confirm_downgrade_match_to_any``) só dispara quando o match
    ORIGINAL é específico — e os perfis dela JÁ ESTÃO em ``MatchAny``, rebaixados
    por defeito anterior. Para esses perfis a janela não tinha uma única palavra
    a dizer: o que ainda podia sumir calado era a PRIORIDADE, que é justamente o
    que decide qual dos "Sempre" vence (ver `explicacao_da_disputa`). Medido:
    salvar por cima levava ``prio=200`` para ``prio=0``.

    Retorna True se ela confirmou a queda, False se cancelou.
    """
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
    """Ativar um perfil com edição não salva na tela: descartar o que está lá?

    ATIVAR-NAO-MENTE-01 (leva 2, 05/08). Ativar um perfil passou a refazer as
    abas na hora — era a queixa literal dela, *"o perfil que eu ativei não
    aplica imediatamente as features das abas"*. Só que refazer as abas
    RECARREGA o rascunho do disco, e com edição pendente isso apaga o que ela
    ajustou e ainda não salvou. Ignorar em silêncio (o que o tique de 2 Hz faz)
    deixaria as abas mentindo; recarregar em silêncio perderia trabalho dela.
    A decisão é DELA, então é uma pergunta.

    Retorna True para descartar e mostrar o perfil ativado, False para manter
    o que está na tela. O default é MANTER: um Enter distraído nunca pode
    custar edição não salva.
    """
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

    response = executar_dialogo(dialog, nome="conflito_ao_importar")
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

    response = executar_dialogo(dialog, nome="restaurar_perfil_original")
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

    response = executar_dialogo(dialog, nome="remover_perfil")
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
    GUI e LED não discordarem. NUMA-05: ``slot=None`` (registry ainda sem
    opinião) exibe "—" honesto em vez de omitir a linha ou inventar posição.
    NÃO controla nada: o Hefesto não mexe nesses controles — eles funcionam
    pelo driver do Linux + Steam. Modal, run/destroy.
    """
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
    # DualSense: com 2 DualSense, este é o Controle 3). NUMA-05: sempre exibe
    # a linha — sem opinião do registry ainda (`slot=None`), mostra "Controle
    # —" em vez de sumir com a linha inteira (null honesto > omissão muda).
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
