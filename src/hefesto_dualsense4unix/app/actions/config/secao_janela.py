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
   que a casa já pagou uma vez. **E desde 25/08/2026 o espelho é só espelho:**
   o botão "Abrir a aba Sistema" saiu (LEX-4, pedido dela), e quem diz onde se
   muda é a dica do rótulo de estado.

A QUARTA, de 25/08/2026, é a que muda o que se vê: **esta seção responde ao
CLIQUE.** As três frases de apoio que ocupavam a página viraram dica dos rótulos
que elas explicam, e no lugar delas nasceu o RECIBO — um rótulo vazio no fim da
fileira que ganha "Guardado." em verde no instante do gesto. O sintoma que isso
cura é o dela: *"janela ok, muito bom mas os botões não funcionam"*. Os handlers
sempre estiveram lá; o que faltava era a tela dizer que o gesto chegou.

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
    RECIBO_GUARDADO,
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

#: VERDE é a cor de confirmação desta casa, da mesma linha do `theme.css:13` e
#: do mesmo `@green` (`theme.css:26`) que `daemon_actions.py:157` e
#: `emulation_actions.py:451` já escrevem em hexa pelo mesmo motivo.
_COR_DE_CONFIRMACAO = "#50fa7b"

#: A frase que explica QUANDO o tamanho novo aparece. Ela era o primeiro
#: parágrafo de apoio da seção (`:111` até 25/08/2026) e virou dica do rótulo
#: "Tamanho do texto:" pela regra do léxico da LEX-2: *fica na página o que
#: MUDA, vai para o hover o que EXPLICA*. Esta frase diria a mesma coisa com a
#: janela recém-aberta e com a janela toda mexida — logo, explica.
#:
#: Ela NÃO é o recibo e não o substitui: responde "quando o tema é aplicado", e
#: a decisão 1 do topo (o `apply_theme` que COMPÕE) é o que a torna verdadeira.
#: Quem responde "isto ficou guardado?" é o `RECIBO_GUARDADO`.
_QUANDO_O_TAMANHO_APARECE = "O tamanho novo vale na próxima vez que você abrir o Hefesto."

#: A dica do rótulo de estado do espelho de autostart. Ela nasceu junto com a
#: SAÍDA do botão "Abrir a aba Sistema" (LEX-4, pedido literal dela: *"não
#: deveriam ter o botão de abrir aba sistema"*): sem o botão, a fileira precisa
#: dizer por outro caminho onde o interruptor de verdade mora — senão o espelho
#: vira um estado que ninguém sabe mudar.
#:
#: PROVISÓRIO — decisão dela (PROVA-DE-TELA-01).
_ONDE_SE_LIGA_JUNTO = (
    "Este valor é um espelho. Quem liga e desliga é o interruptor da aba "
    "Sistema."
)

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
    # A LISTA DOS RECIBOS nasce aqui, e nasce VAZIA a cada montagem: a aba pode
    # ser remontada, e um rótulo de uma montagem morta na lista faria o próximo
    # clique tentar apagar um widget destruído.
    host._config_recibos = []

    caixa.pack_start(_fileira_do_tamanho(host), False, False, 0)
    caixa.pack_start(_fileira_do_ambiente(host), False, False, 0)
    # ESTADO, e por isso FICA na página: esta frase muda com a máquina — ela diz
    # qual ambiente foi detectado, e é o único jeito de a pessoa saber que há
    # algo a corrigir ali.
    caixa.pack_start(rotulo_de_apoio(frase_do_detectado(ambiente_lido())), False, False, 0)

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
    linha, _rotulo = _fileira(
        "Tamanho do texto:",
        # As duas frases que saíram da página na LEX-2, juntas na dica do rótulo
        # que elas explicam: quando o tamanho novo aparece, e que a escolha já
        # está guardada. A marca visual do "tenho dica" quem dá é
        # `moldura.marcar_afordancias`, que varre a seção montada.
        dica=f"{_QUANDO_O_TAMANHO_APARECE} {VALE_JA}",
    )
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
    seletor.connect("changed", lambda sel: _ao_trocar_o_tamanho(host, sel))
    host._config_escala_seletor = seletor
    linha.pack_start(seletor, False, False, 0)
    host._config_recibo_do_tamanho = _recibo(host, linha)
    return linha


def _ao_trocar_o_tamanho(host: Any, seletor: Any) -> None:
    """Grava o degrau escolhido e ESCREVE O RECIBO.

    NÃO reaplica o tema — ver a decisão 1 do topo. E é justamente por isso que
    o recibo existe: sem ele, um clique aqui não muda um pixel da janela, e o
    gesto fica indistinguível de um gesto que não aconteceu.
    """
    nome = seletor.get_active_id()
    valor = DEGRAUS_DE_ESCALA.get(nome) if nome is not None else None
    if valor is None:
        return
    set_pref(CHAVE_ESCALA, valor)
    logger.info("config_escala_gravada", degrau=nome, delta=valor)
    _escrever_o_recibo(host, getattr(host, "_config_recibo_do_tamanho", None))


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
            "sozinho; no GNOME precisa de uma extensão instalada. "
            # A `VALE_JA` ANEXA aqui, e não substitui: as duas explicam coisas
            # diferentes sobre a mesma fileira. Anexar é o mesmo desenho da
            # LEX-2 para `_NOME_VALE_JA` em `secao_mesa`.
            + VALE_JA
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
    host._config_recibo_do_ambiente = _recibo(host, linha)
    return linha


def _ao_corrigir_o_ambiente(host: Any, seletor: Any) -> None:
    """Grava a correção, escreve o RECIBO e repinta a mensagem da bandeja.

    Repintar é a entrega da correção em si: o ambiente não muda uma linha do
    que o produto faz, muda o que a seção sabe recomendar quando o ícone não
    sobe. É também o que torna o aceite "num GNOME sem a extensão, a seção
    mostra a instrução" verificável numa bancada que não tem GNOME.

    O RECIBO É INDEPENDENTE DO REPINTAR, e é essa separação que resolve o
    sintoma dela. `ambiente.mensagem_da_bandeja` devolve a MESMA frase para os
    três ambientes quando o ícone sobe (`ambiente.py:143-144`) — que é o caso
    da máquina dela, provado pela foto da aba ("A barra do sistema desta sessão
    recebe o ícone do Hefesto"). Trocar COSMIC → GNOME → Outro ali não mudava um
    pixel, e o clique lia como botão quebrado. O recibo responde ao GESTO; a
    bandeja responde ao FATO, e os dois deixam de ser a mesma coisa.
    """
    escolha = seletor.get_active_id()
    if escolha is None:
        return
    gravar_correcao_de_ambiente(escolha)
    logger.info("config_ambiente_corrigido", escolha=escolha)
    _escrever_o_recibo(host, getattr(host, "_config_recibo_do_ambiente", None))
    _pintar_a_bandeja(host)


# ---------------------------------------------------------------------------
# O recibo — a resposta ao clique, na fileira que o recebeu
# ---------------------------------------------------------------------------


def _recibo(host: Any, linha: Any) -> Any:
    """Um rótulo VAZIO no fim da fileira, e o registro dele na lista do host.

    Nasce vazio de propósito, e essa é a diferença inteira em relação ao
    parágrafo que ele substitui: a `VALE_JA` estava na página ANTES do clique,
    então não distinguia "cliquei" de "não cliquei". Um rótulo que só ganha
    texto depois do gesto responde à pergunta que a pessoa faz — *isto ficou
    guardado?* — no instante em que ela a faz.
    """
    from gi.repository import Gtk

    rotulo = Gtk.Label(label="")
    rotulo.set_xalign(0.0)
    linha.pack_start(rotulo, False, False, 0)
    with contextlib.suppress(Exception):
        host._config_recibos.append(rotulo)
    return rotulo


def _escrever_o_recibo(host: Any, rotulo: Any) -> None:
    """Escreve o recibo NESTA fileira e apaga o das outras.

    Apagar os outros é o que impede a seção de acumular confirmações antigas:
    dois recibos verdes ao mesmo tempo diriam que dois gestos acabaram de
    acontecer, quando só um aconteceu.

    Tudo sob `suppress` porque isto roda de dentro de um handler de sinal do
    GTK, onde uma exceção não tem quem a pegue — vira traço na saída de erro com
    a janela já de pé. E `html.escape` pela mesma razão medida de
    `_pintar_a_bandeja`: a frase é texto de tela e pode ganhar um "&" na próxima
    revisão de redação, que derrubaria a análise do Pango e deixaria o rótulo em
    branco.
    """
    if rotulo is None:
        return
    with contextlib.suppress(Exception):
        for outro in getattr(host, "_config_recibos", ()):
            if outro is not rotulo:
                outro.set_text("")
    with contextlib.suppress(Exception):
        rotulo.set_markup(
            f'<span foreground="{_COR_DE_CONFIRMACAO}">'
            f"{html.escape(_(RECIBO_GUARDADO), quote=False)}</span>"
        )


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
    """O espelho do interruptor da aba Sistema. Só o espelho, desde a LEX-4.

    Devolve `None` quando o interruptor de origem não existe (dublê de teste,
    glade antigo): espelho sem original é um rótulo que nunca fica certo, e
    isso é pior do que a linha não existir.

    O estado acompanha o original por `notify::active`, e não por uma segunda
    consulta ao sistema: a aba Sistema já pergunta em thread e reconcilia o
    interruptor sob `_daemon_autostart_guard` (`daemon_actions.py:1955-1961`).
    Perguntar de novo aqui criaria uma segunda resposta para a mesma pergunta —
    e duas respostas divergem no dia em que uma das duas atrasar.
    """
    interruptor = host._get("daemon_autostart_switch")
    if interruptor is None:
        return None

    linha, _rotulo = _fileira("Ligar junto com o computador")
    estado = _rotulo_simples("")
    # LEX-4 (25/08/2026): o botão "Abrir a aba Sistema" SAIU daqui, a pedido
    # literal dela — *"não deveriam ter o botão de abrir aba sistema"*. Ele
    # funcionava (a busca era por id, nunca por índice); o problema era outro:
    # numa fileira que já é espelho, um botão de navegação é o único elemento
    # clicável, e ele parece o controle que muda o estado ao lado.
    #
    # A dica no rótulo de estado é o que sobra no lugar, e ela entrega o que o
    # botão entregava de fato: dizer ONDE se muda. O espelho continua espelho.
    with contextlib.suppress(Exception):
        estado.set_tooltip_text(_(_ONDE_SE_LIGA_JUNTO))
    host._config_autostart_estado = estado
    linha.pack_start(estado, False, False, 0)

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


# `_abrir_a_aba_sistema` VIVEU AQUI e saiu com o botão dela (LEX-4, 25/08/2026).
# Ela procurava a página `daemon_box` pelo ID do Glade, nunca por índice, e o
# `id_da_pagina` que ela usava CONTINUA vivo e público em `home_actions` — ele
# tem outros oito chamadores (`app.py`, `status_actions.py`, e a EST-10 depende
# dele). Não o apague junto: o que morreu foi o botão, não o desembrulho.


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
