"""Seção 4 da aba Configurações — ajustes do programa, não dos controles.

Tamanho do texto, ambiente da área de trabalho, ícone na barra do sistema e o
espelho de "Ligar junto com o computador", que mora na aba Sistema.

O ambiente detectado informa a MENSAGEM DE AJUDA, nunca o comportamento:
`XDG_CURRENT_DESKTOP` pode vir vazia ou composta, e a aba abre igual nos três
casos.

As três decisões que moldaram esta seção, todas de 22/08/2026 e todas com o
preço medido do outro lado:

1. **O tamanho do texto GRAVA e vale ao reabrir**, e a tela diz isso. Reaplicar
   na hora exigiria desfazer o tema, e `theme.apply_theme` COMPÕE: quatro
   chamadas no mesmo processo levaram a fonte de 12,25 a 19 pontos (medido em
   `tests/unit/test_gatilho_palavra_rotulos.py:48-52`), porque ele soma ao
   `gtk-font-name` já posto e empilha provider sem nunca chamar
   `remove_provider_for_screen`. Um clique aqui NÃO chama `apply_theme`.
2. **Não existe caixa de ligar/desligar o ícone da barra.** Não há o que ela
   ligaria: a `AppTray` é sempre construída (`app.py:1416`) e nenhuma chave a
   desliga. A caixa seria decoração — e desligar a bandeja sem ensinar
   `_has_persistent_access` esconderia a janela sem caminho de volta. O que a
   seção entrega no lugar é o ESTADO e, quando o ícone não sobe, a instrução
   que hoje falta.
3. **"Ligar junto com o computador" é espelho, não um segundo dono.** O
   interruptor de verdade vive na aba Sistema, sob `_daemon_autostart_guard`;
   um segundo widget editável seria dono duplo do mesmo gesto, que é a cicatriz
   que a casa já pagou uma vez.

TERRITÓRIO DE CONFIG-07. Quem trabalha nesta seção escreve AQUI — o título, a
dica e todo widget dela. O montador da aba (`mixin.py`) só cria a moldura e
chama `montar`; ele não sabe o que há dentro, e é assim que cinco seções
crescem sem se pisarem.
"""
from __future__ import annotations

import contextlib
import html
from typing import Any

from hefesto_dualsense4unix.app.actions.config.moldura import (
    VALE_JA,
    rotulo_de_apoio,
)
from hefesto_dualsense4unix.app.ambiente import (
    AMBIENTES,
    ambiente_efetivo,
    ambiente_lido,
    frase_do_detectado,
    gravar_correcao_de_ambiente,
    mensagem_da_bandeja,
)
from hefesto_dualsense4unix.app.gui_prefs import set_pref
from hefesto_dualsense4unix.app.ipc_bridge import run_in_thread
from hefesto_dualsense4unix.app.theme import (
    CHAVE_ESCALA,
    DEGRAUS_DE_ESCALA,
    degrau_da_escala,
    escala_gravada,
)
from hefesto_dualsense4unix.app.widgets.segmented_selector import SegmentedSelector
from hefesto_dualsense4unix.integrations.desktop_notifications import (
    statusnotifierwatcher_available,
)
from hefesto_dualsense4unix.utils.i18n import _
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

#: O título como ela o lê na tela.
TITULO = "A janela"

#: Sem dica, e de propósito: no desenho aprovado esta seção também não tem.
#: Os rótulos dela se explicam sozinhos, e inventar uma explicação aqui seria
#: pôr na tela uma frase que ninguém aprovou.
DICA: str | None = None

#: Espaçamento entre o rótulo de uma fileira e o controle dela.
_ESPACAMENTO_DA_FILEIRA = 8

#: LARANJA é a cor de atenção desta casa (`theme.css:13`: "VERDE confirma,
#: LARANJA alerta"). Vem em hexa porque `set_markup` não enxerga os tokens
#: `@define-color` do CSS — é a mesma costura de `home_actions.py:751` e
#: `rumble_actions.py:868`.
_COR_DE_ATENCAO = "#ffb86c"

#: Rótulo de tela de cada degrau. O que existe e em que ordem é de `theme.py`
#: (dono único da escala); aqui mora só como cada um se chama na tela. Degrau
#: sem rótulo cai no id com inicial maiúscula, em vez de sumir da fileira.
_ROTULOS_DE_DEGRAU = {
    "compacto": "Compacto",
    "normal": "Normal",
    "grande": "Grande",
}


def montar(host: Any, caixa: Any) -> None:
    """Monta a seção dentro de `caixa` — a caixa interna da moldura.

    `host` é o `HefestoApp`: dele vêm `_get` (widgets do Glade) e o que os
    outros mixins já penduraram. `caixa` é um `Gtk.Box` vertical, com as
    margens da casa já aplicadas.

    Contrato, e ele vale para as cinco: **nunca levantar**. Uma seção que
    falha ao montar não pode derrubar a aba, e uma aba que falha não pode
    derrubar a janela. Quem chama já embrulha em `contextlib.suppress`, mas a
    tolerância começa aqui.
    """
    caixa.pack_start(_fileira_do_tamanho(host), False, False, 0)
    caixa.pack_start(
        rotulo_de_apoio("O tamanho novo vale na próxima vez que você abrir o Hefesto."),
        False,
        False,
        0,
    )
    caixa.pack_start(_fileira_do_ambiente(host), False, False, 0)
    caixa.pack_start(rotulo_de_apoio(frase_do_detectado(ambiente_lido())), False, False, 0)
    # A ÚNICA seção da aba que grava NA HORA, e por isso a única que precisa
    # dizer o contrário das outras. As duas escolhas acima vão ao disco no
    # próprio clique (`set_pref` e `gravar_correcao_de_ambiente`) — o "Aplicar"
    # do rodapé não tem nada a ver com elas. Sem esta linha, "A janela" era a
    # única seção sem resposta para "isto ficou guardado?": a frase que existia
    # ali fala de QUANDO o tema é aplicado, não de se a escolha foi guardada.
    caixa.pack_start(rotulo_de_apoio(VALE_JA), False, False, 0)

    bandeja = rotulo_de_apoio("Conferindo o ícone na barra do sistema.")
    host._config_bandeja_rotulo = bandeja
    host._config_bandeja_watcher = None
    caixa.pack_start(bandeja, False, False, 0)
    _sondar_a_bandeja(host)

    espelho = _fileira_do_autostart(host)
    if espelho is not None:
        caixa.pack_start(espelho, False, False, 0)


# ---------------------------------------------------------------------------
# Tamanho do texto
# ---------------------------------------------------------------------------


def _fileira_do_tamanho(host: Any) -> Any:
    """A fileira do tamanho: rótulo, três degraus, e o que está gravado marcado.

    Lê `escala_gravada()` e não `escala_fonte()`: a segunda devolve o cache da
    SESSÃO, e depois de uma gravação nesta mesma tela ela apontaria para o
    degrau antigo — a fileira mentiria sobre a própria escolha da pessoa.
    """
    linha, _rotulo = _fileira("Tamanho do texto:")
    # `wrap=True` com TRÊS itens é o jeito de ter a fileira DEITADA, e a
    # descoberta é medida: sem ele, o `SegmentedSelector` é um `Gtk.Box`
    # VERTICAL (`segmented_selector.py:206`) e empilha as opções uma sobre a
    # outra — é assim que "Sons do jogo / Todo o som do PC" aparece hoje em
    # `docs/usage/assets/readme_status.png`. Com `wrap`, o widget vira grade de
    # três colunas fixas, e três opções cabem numa linha só, como no desenho.
    # As duas fileiras desta seção têm exatamente três opções, e não por acaso.
    seletor = SegmentedSelector(wrap=True)
    seletor.set_items(
        [
            (nome, _ROTULOS_DE_DEGRAU.get(nome, nome.capitalize()))
            for nome in DEGRAUS_DE_ESCALA
        ]
    )
    # A marcação inicial vem ANTES do `connect`, e a ordem é a cura: o
    # `set_active_id` do `SegmentedSelector` EMITE "changed" (espelha o
    # `GtkComboBox`), e com o handler já ligado a abertura da janela gravaria
    # sozinha o que ninguém escolheu.
    with contextlib.suppress(Exception):
        seletor.set_active_id(degrau_da_escala(escala_gravada()))
    # O seletor NÃO empurra a fileira, e a linha abaixo é o que garante isso.
    # Medido em 22/08: sem ela o rótulo ficava em x=25 e os botões em x=895 —
    # 757px de vão no meio da fileira. A causa é o próprio widget: com
    # `wrap=True` ele empacota o `Gtk.Grid` interno com `expand=True`
    # (`segmented_selector.py:236`), e o GTK3 PROPAGA esse `hexpand` para cima,
    # então o `Gtk.Box` da fileira lhe entrega toda a folga da linha mesmo com
    # `pack_start(..., False, False)`. Curar no widget quebraria a aba Início,
    # que depende dessa expansão para os três botões ocuparem a largura
    # (`home_actions.py:1523`, empacotado com `False, False` e assim mesmo
    # cheio). Aqui o desenho pede o contrário: rótulo e opções lado a lado.
    seletor.set_hexpand(False)
    seletor.connect("changed", _ao_trocar_o_tamanho)
    host._config_escala_seletor = seletor
    linha.pack_start(seletor, False, False, 0)
    return linha


def _ao_trocar_o_tamanho(seletor: Any) -> None:
    """Grava o degrau escolhido. NÃO reaplica o tema — ver a decisão 1 do topo."""
    nome = seletor.get_active_id()
    valor = DEGRAUS_DE_ESCALA.get(nome) if nome is not None else None
    if valor is None:
        return
    set_pref(CHAVE_ESCALA, valor)
    logger.info("config_escala_gravada", degrau=nome, delta=valor)


# ---------------------------------------------------------------------------
# Ambiente da área de trabalho
# ---------------------------------------------------------------------------


def _fileira_do_ambiente(host: Any) -> Any:
    """A fileira do ambiente: rótulo com a dica do desenho, e os três nomes.

    A dica é a literal do desenho aprovado (`TOOLTIPS.md`), e ela pousa no
    RÓTULO — nunca na fileira inteira, que dispararia por cima dos botões.
    """
    linha, _rotulo = _fileira(
        "Ambiente:",
        dica=(
            "O ícone na barra do sistema depende do ambiente. No COSMIC aparece "
            "sozinho; no GNOME precisa de uma extensão instalada."
        ),
    )
    # `wrap=True` pelo mesmo motivo medido de `_fileira_do_tamanho`.
    seletor = SegmentedSelector(wrap=True)
    seletor.set_items(list(AMBIENTES))
    with contextlib.suppress(Exception):
        seletor.set_active_id(ambiente_efetivo())
    # Mesma cura da fileira acima: o `hexpand` do grid interno não sobe.
    seletor.set_hexpand(False)
    seletor.connect("changed", lambda sel: _ao_corrigir_o_ambiente(host, sel))
    host._config_ambiente_seletor = seletor
    linha.pack_start(seletor, False, False, 0)
    return linha


def _ao_corrigir_o_ambiente(host: Any, seletor: Any) -> None:
    """Grava a correção e REPINTA a mensagem da bandeja — e nada mais.

    Repintar é a entrega inteira desta correção: o ambiente não muda uma linha
    do que o produto faz, muda o que a seção sabe recomendar quando o ícone não
    sobe. É também o que torna o aceite "num GNOME sem a extensão, a seção
    mostra a instrução" verificável numa bancada que não tem GNOME.
    """
    escolha = seletor.get_active_id()
    if escolha is None:
        return
    gravar_correcao_de_ambiente(escolha)
    logger.info("config_ambiente_corrigido", escolha=escolha)
    _pintar_a_bandeja(host)


# ---------------------------------------------------------------------------
# O ícone na barra do sistema
# ---------------------------------------------------------------------------


def _sondar_a_bandeja(host: Any) -> None:
    """Pergunta, FORA da thread do GTK, se a barra do sistema recebe o ícone.

    `statusnotifierwatcher_available` é síncrona e fala D-Bus com
    `_DBUS_TIMEOUT_SECONDS = 2.0` (`desktop_notifications.py:33`): chamada aqui,
    ela congela a janela por até dois segundos na abertura. Vai por
    `run_in_thread`, cujos callbacks voltam pela thread do GTK via
    `GLib.idle_add` — e por isso DEVEM devolver `False`, senão o GLib reagenda
    o mesmo callback para sempre.
    """

    def _pousou(presente: Any) -> bool:
        host._config_bandeja_watcher = bool(presente)
        _pintar_a_bandeja(host)
        return False

    def _falhou(exc: Exception) -> bool:
        # Sonda que não respondeu é ícone que não aparece, do ponto de vista de
        # quem olha a barra. O que não pode acontecer é o rótulo ficar preso em
        # "Conferindo" para sempre.
        logger.debug("config_bandeja_sonda_falhou", erro=str(exc))
        host._config_bandeja_watcher = False
        _pintar_a_bandeja(host)
        return False

    run_in_thread(statusnotifierwatcher_available, _pousou, _falhou)


def _pintar_a_bandeja(host: Any) -> None:
    """Escreve no rótulo o estado do ícone — e a instrução quando ele não sobe.

    Enquanto a sonda não respondeu, o rótulo fica como nasceu: afirmar que o
    ícone está lá antes de perguntar seria a tela adivinhando.

    Laranja quando falta alguma coisa. Não vermelho: nada foi destruído e a
    janela continua inteira — é alerta, e alerta nesta casa é `@orange`.
    """
    rotulo = getattr(host, "_config_bandeja_rotulo", None)
    presente = getattr(host, "_config_bandeja_watcher", None)
    if rotulo is None or presente is None:
        return
    # Tudo dentro do `suppress`, leitura de disco inclusive: esta função é
    # chamada de dentro de um callback de `GLib.idle_add`, e exceção ali não
    # tem quem a pegue — vira traço na saída de erro com a janela já de pé.
    with contextlib.suppress(Exception):
        texto = _(mensagem_da_bandeja(ambiente_efetivo(), presente))
        if presente:
            rotulo.set_text(texto)
            return
        # `html.escape` porque a frase é texto de tela e pode ganhar um "&" ou
        # um "<" na próxima revisão de redação. Medido em 22/08/2026: o ">" de
        # "Configurações > Painel" passa cru pelo Pango, mas "&" e "<" NÃO —
        # eles derrubam a análise e o rótulo fica EM BRANCO, com o erro só no
        # log. `quote=False` porque aspas simples são válidas no texto e a
        # frase do COSMIC tem duas.
        rotulo.set_markup(
            f'<span foreground="{_COR_DE_ATENCAO}">'
            f"{html.escape(texto, quote=False)}</span>"
        )


# ---------------------------------------------------------------------------
# O espelho de "Ligar junto com o computador"
# ---------------------------------------------------------------------------


def _fileira_do_autostart(host: Any) -> Any:
    """O espelho do interruptor da aba Sistema, mais o atalho para lá.

    Devolve `None` quando o interruptor de origem não existe (dublê de teste,
    glade antigo): espelho sem original é um rótulo que nunca fica certo, e
    isso é pior do que a linha não existir.

    O estado acompanha o original por `notify::active`, e não por uma segunda
    consulta ao sistema: a aba Sistema já pergunta em thread e reconcilia o
    interruptor sob `_daemon_autostart_guard` (`daemon_actions.py:1573-1579`).
    Perguntar de novo aqui criaria uma segunda resposta para a mesma pergunta —
    e duas respostas divergem no dia em que uma das duas atrasar.
    """
    interruptor = host._get("daemon_autostart_switch")
    if interruptor is None:
        return None

    linha, _rotulo = _fileira("Ligar junto com o computador")
    estado = _rotulo_simples("")
    host._config_autostart_estado = estado
    linha.pack_start(estado, False, False, 0)

    from gi.repository import Gtk

    botao = Gtk.Button(label=_("Abrir a aba Sistema"))
    botao.connect("clicked", lambda _b: _abrir_a_aba_sistema(host))
    linha.pack_start(botao, False, False, 0)

    _espelhar_o_autostart(estado, interruptor)
    interruptor.connect(
        "notify::active", lambda widget, _pspec: _espelhar_o_autostart(estado, widget)
    )
    return linha


def _espelhar_o_autostart(estado: Any, interruptor: Any) -> None:
    """Copia o estado do interruptor para o rótulo. Uma direção só.

    Uma direção só é o desenho, não uma limitação: quem escreve é a aba
    Sistema, e este rótulo não tem como ser clicado de volta.
    """
    with contextlib.suppress(Exception):
        estado.set_text(_("Ligado") if interruptor.get_active() else _("Desligado"))


def _abrir_a_aba_sistema(host: Any) -> None:
    """Leva a janela para a aba Sistema, procurando a página pelo ID do Glade.

    Nunca por índice (EST-10): acrescentar uma aba renumera todas, e um atalho
    por número passaria a abrir a aba errada em silêncio. `id_da_pagina`
    desembrulha o rolador que `_wrap_notebook_pages_in_scroll` pôs em volta das
    páginas, e é o dono único desse desembrulho.
    """
    from hefesto_dualsense4unix.app.actions.home_actions import id_da_pagina

    notebook = host._get("main_notebook")
    if notebook is None:
        return
    with contextlib.suppress(Exception):
        for pagina in notebook.get_children():
            if id_da_pagina(pagina) != "daemon_box":
                continue
            indice = notebook.page_num(pagina)
            if isinstance(indice, int) and indice >= 0:
                notebook.set_current_page(indice)
            return


# ---------------------------------------------------------------------------
# Molde das fileiras
# ---------------------------------------------------------------------------


def _fileira(titulo: str, *, dica: str | None = None) -> tuple[Any, Any]:
    """Uma fileira "rótulo + controle", devolvida como `(caixa, rótulo)`.

    SEM `set_homogeneous(True)`, e o motivo está medido no próprio Glade
    (`main.glade:1644-1650`): uma fileira homogênea deu a "Auto" (quatro
    letras) os mesmos 459px de uma frase inteira e levou a largura mínima da
    JANELA a 1004px. A janela abre com 1180 e não tem rolagem horizontal.
    """
    from gi.repository import Gtk

    caixa = Gtk.Box(
        orientation=Gtk.Orientation.HORIZONTAL, spacing=_ESPACAMENTO_DA_FILEIRA
    )
    rotulo = _rotulo_simples(titulo)
    if dica is not None:
        rotulo.set_tooltip_text(_(dica))
    caixa.pack_start(rotulo, False, False, 0)
    return caixa, rotulo


def _rotulo_simples(texto: str) -> Any:
    """Rótulo curto de fileira: alinhado à esquerda, sem quebra.

    Não usa `rotulo_de_apoio`: aquele é para frase explicativa (esmaecida e com
    quebra em 92 caracteres). Rótulo de fileira é nome de campo, e um nome de
    campo esmaecido some ao lado do controle que ele nomeia.
    """
    from gi.repository import Gtk

    rotulo = Gtk.Label(label=_(texto))
    rotulo.set_xalign(0.0)
    return rotulo
