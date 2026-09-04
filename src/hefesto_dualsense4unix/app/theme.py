"""Aplicação do tema Drácula ao Hefesto - Dualsense4Unix via Gtk.CssProvider.

Prioridade GTK_STYLE_PROVIDER_PRIORITY_APPLICATION (600) sobrepõe o tema
do sistema (PRIORITY_THEME = 200) sem vazar para outras janelas GTK.

Este módulo é o DONO ÚNICO do tamanho da fonte da interface (LEGIBILIDADE-01).
A escala global tem dois canais, e são necessários os dois:

* ``Gtk.Settings.gtk-font-name`` move a base HERDADA — os ~90% da janela que
  não têm regra de tamanho nenhuma e caem no padrão do Pango (13,33px a 96
  dpi). Sozinho ele não alcança as regras que declaram ``font-size`` em px.
* O CSS é carregado por ``load_from_data`` depois de ter os ``font-size: Npx``
  reescritos em memória. Sozinho ele não alcança o que não tem regra.

Não existe terceira via: o GTK3 não tem variável de CSS (``@define-color`` só
declara COR), não tem ``calc()``, e um token desconhecido não é ignorado — ele
DERRUBA A CARGA DO ARQUIVO INTEIRO, deixando a janela com o tema claro do
sistema e uma linha de log que não diz onde foi. O projeto já tropeçou nisso
duas vezes com at-rules (``theme.css:105`` e ``:805``).
"""
# ruff: noqa: E402
from __future__ import annotations

import re

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, Gtk

from hefesto_dualsense4unix.app.constants import GUI_DIR
from hefesto_dualsense4unix.app.gui_prefs import load_gui_prefs
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

_CSS_PATH = GUI_DIR / "theme.css"

#: Chave da preferência (``~/.config/hefesto-dualsense4unix/gui_preferences.json``).
CHAVE_ESCALA = "escala_fonte"

#: Quanto a interface cresce, em PIXELS, por cima de cada tamanho declarado.
#: 3 é o pedido da mantenedora ("não seria interessante aumentarmos em 3 o
#: tamanho delas?"), medido e aprovado no orçamento de largura e altura depois
#: da realocação — ver `tests/unit/test_layout_orcamento_altura.py`.
ESCALA_PADRAO = 3

#: Teto de segurança. Acima disso o conteúdo passa a exigir mais largura do que
#: uma tela 1080p oferece, e a janela deixa de caber em vez de ficar legível.
ESCALA_MAXIMA = 8

#: Os três degraus que a aba Configurações oferece, e o delta de cada um.
#:
#: A escala aceita 0 a 8, mas nove degraus numa fileira de botões é uma régua,
#: não uma escolha — e a pergunta que a pessoa faz é "está pequeno demais?",
#: que tem três respostas. "Normal" é o `ESCALA_PADRAO` por definição: o degrau
#: do meio não pode divergir do padrão da casa no dia em que ele mudar.
#:
#: "Grande" é 6 e não `ESCALA_MAXIMA`: 8 é o teto de SEGURANÇA (acima dele a
#: janela deixa de caber numa tela 1080p), e um degrau colado no teto não tem
#: folga para o dia em que uma tela nova pedir mais um pixel.
DEGRAUS_DE_ESCALA: dict[str, int] = {
    "compacto": 0,
    "normal": ESCALA_PADRAO,
    "grande": 6,
}

#: 96 dpi: 1 ponto tipográfico = 4/3 de pixel. `gtk-font-name` fala em PONTOS;
#: o CSS, em pixels. Sem esta conversão os dois canais cresceriam desigual e a
#: interface ficaria com dois tamanhos de "corpo".
_PONTOS_POR_PIXEL = 0.75

#: Tamanho que o Pango usa quando `gtk-font-name` vem SEM número — que é
#: exatamente o caso desta máquina ("Fira Sans", sem tamanho).
_PONTOS_PADRAO_PANGO = 10.0

_REGRA_TAMANHO = re.compile(r"(font-size\s*:\s*)([0-9]+(?:\.[0-9]+)?)px")
_NOME_COM_TAMANHO = re.compile(r"^(.*?)\s+([0-9]+(?:\.[0-9]+)?)$")

#: Delta efetivamente aplicado nesta sessão. O desenho em Cairo (as barras do
#: giroscópio) não passa nem pelo CSS nem pelo Pango e precisa consultar isto.
_escala_aplicada: int | None = None


def escala_gravada() -> int:
    """Delta de tamanho da fonte que está NO DISCO agora, sem cache.

    Valor fora da faixa (ou de tipo errado, num arquivo editado à mão) cai no
    padrão em vez de quebrar a abertura da janela — o tema NUNCA pode ser o
    motivo de a interface não abrir.

    Existe separada de `escala_fonte` por causa da aba Configurações: a fileira
    de degraus tem de nascer marcando o que VALE NA PRÓXIMA ABERTURA, e
    `escala_fonte` devolve o cache `_escala_aplicada` da sessão — depois da
    primeira leitura ela mente sobre o disco, que é justamente onde a gravação
    de agora foi parar.
    """
    bruto = load_gui_prefs().get(CHAVE_ESCALA, ESCALA_PADRAO)
    if isinstance(bruto, bool) or not isinstance(bruto, (int, float)):
        logger.warning("theme_escala_invalida", valor=repr(bruto))
        bruto = ESCALA_PADRAO
    delta = int(bruto)
    if delta < 0 or delta > ESCALA_MAXIMA:
        logger.warning("theme_escala_fora_da_faixa", valor=delta)
        delta = max(0, min(ESCALA_MAXIMA, delta))
    return delta


def degrau_da_escala(delta: int) -> str:
    """O degrau de `DEGRAUS_DE_ESCALA` mais perto de `delta`.

    Nunca devolve "nenhum": um arquivo com `escala_fonte: 5` (alcançável
    editando o JSON à mão, e foi o único caminho até esta tela existir) tem de
    marcar um botão, senão a fileira nasce em branco e a pessoa não descobre
    qual tamanho está valendo. Empate não existe entre inteiros — os degraus
    são 0, 3 e 6, e as fronteiras caem em 1,5 e 4,5.
    """
    return min(DEGRAUS_DE_ESCALA, key=lambda nome: abs(DEGRAUS_DE_ESCALA[nome] - delta))


def escala_fonte() -> int:
    """Delta de tamanho da fonte, em px, APLICADO nesta sessão.

    Cacheia de propósito: o tema é composto uma vez por processo, e o desenho
    em Cairo consulta este valor a cada quadro. Quem quer saber o que está
    gravado — e não o que está na tela — chama `escala_gravada`.
    """
    global _escala_aplicada
    if _escala_aplicada is not None:
        return _escala_aplicada
    _escala_aplicada = escala_gravada()
    return _escala_aplicada


def escalar_css(texto: str, delta: int) -> str:
    """Soma ``delta`` px a cada ``font-size: Npx`` do CSS.

    Só o que está em PIXEL entra: um ``font-size`` relativo (``92%``,
    ``smaller``) não pode ser somado a um valor absoluto, e o projeto não tem
    nenhum — a escala tipográfica é toda em px justamente por isso.
    """
    if not delta:
        return texto

    def _somar(m: re.Match[str]) -> str:
        return f"{m.group(1)}{float(m.group(2)) + delta:g}px"

    return _REGRA_TAMANHO.sub(_somar, texto)


def escalar_nome_da_fonte(nome: str, delta: int) -> str:
    """Soma ``delta`` px (convertidos em pontos) ao nome de fonte do GTK.

    ``"Fira Sans"`` (sem número) é o caso comum: o Pango entrega 10pt e o nome
    passa a declarar o tamanho explicitamente, para a base herdada crescer
    junto com as regras em px.
    """
    if not delta:
        return nome
    casado = _NOME_COM_TAMANHO.match(nome.strip())
    if casado is not None:
        familia, pontos = casado.group(1), float(casado.group(2))
    else:
        familia, pontos = nome.strip(), _PONTOS_PADRAO_PANGO
    return f"{familia} {pontos + delta * _PONTOS_POR_PIXEL:g}"


#: O tema que a sessão dela escolheu, perguntado ao dono da escolha.
#:
#: ``org.gnome.desktop.interface gtk-theme`` é o mesmo lugar que o portal lê. Ele
#: mora no dconf, e por isso responde **igual sob Wayland e sob XWayland** — que
#: é o ponto inteiro desta peça.
_CHAVE_DO_TEMA = ("org.gnome.desktop.interface", "gtk-theme")

#: Onde o GTK guarda de que lado ficam fechar/maximizar/minimizar.
#:
#: O que vem ANTES dos dois-pontos vai para a esquerda; o que vem depois, para a
#: direita. ``:minimize,maximize,close`` é o lado direito, e é o que o COSMIC faz
#: nas janelas dele.
_CHAVE_DOS_BOTOES = ("org.gnome.desktop.wm.preferences", "button-layout")

#: DE QUE LADO O COSMIC PÕE OS BOTÕES, e ele não tem chave a perguntar.
#:
#: Medido na máquina dela em 04/09/2026: o compositor decora as janelas dele com
#: os três botões à DIREITA e não expõe nenhuma configuração para o lado —
#: ``~/.config/cosmic/`` inteiro não tem uma linha com ``minimize``.
LADO_DO_COSMIC = ":minimize,maximize,close"


def sessao_e_cosmic() -> bool:
    """Esta sessão é COSMIC? Lê o ambiente a cada chamada, nunca na importação.

    Um teste que troca a variável no meio da sessão precisa ser obedecido.
    """
    import os

    for chave in ("XDG_CURRENT_DESKTOP", "XDG_SESSION_DESKTOP", "DESKTOP_SESSION"):
        if "cosmic" in (os.environ.get(chave) or "").lower():
            return True
    return False


def lado_dos_botoes_na_sessao() -> str:
    """O que o ``button-layout`` do dconf responde, ou ``""`` se não der para saber.

    Ela existe para o RELATO e para a mordida: é a resposta que a sessão dá, e
    que — medida — **não serve** para curar a queixa. Ver
    :func:`barra_que_o_sistema_usa`.
    """
    try:
        from gi.repository import Gio
    except ImportError:  # pragma: no cover — gi sem Gio não existe na prática
        return ""
    esquema, chave = _CHAVE_DOS_BOTOES
    try:
        fonte = Gio.SettingsSchemaSource.get_default()
        if fonte is None or fonte.lookup(esquema, True) is None:
            return ""  # o esquema não está instalado — não há o que perguntar
        return str(Gio.Settings.new(esquema).get_string(chave) or "")
    except Exception as exc:  # amplo de propósito: nunca impedir a janela de abrir
        logger.warning("botoes_da_sessao_indisponiveis", erro=str(exc))
        return ""


def barra_que_o_sistema_usa() -> str:
    """De que lado ESTA sessão põe fechar/maximizar/minimizar. ``""`` = não mexer.

    **A QUEIXA 2 DELA, 04/09/2026:** *"a barra de navegação fechar, maximizar
    diminuir não é a mesma do sistema"*. Decidida no mesmo dia — opção ``1-a``,
    **só a janela do Hefesto**: nenhuma linha na configuração dela.

    A PREMISSA DA SPRINT CAIU NA MEDIÇÃO, e o número está aqui porque quem vier
    depois vai querer refazê-lo. A `BARRA-DA-JANELA-01` mandava *"ler
    ``org.gnome.desktop.wm.preferences button-layout``; se a sessão não disser,
    cair em ``:minimize,maximize,close``"* — supondo que só o ``settings.ini``
    dela carregasse o valor errado e o dconf estivesse mudo. Medido na máquina
    dela em 04/09/2026:

    ==========================================  ================================
    a fonte                                     o que ela responde
    ==========================================  ================================
    ``~/.config/gtk-3.0/settings.ini``          ``close,maximize,minimize:``
    ``gsettings … wm.preferences button-layout``  ``'close,maximize,minimize:'``
    as janelas do COSMIC, na tela               os três botões à **direita**
    ==========================================  ================================

    **As duas fontes dizem a mesma coisa, e as duas dizem ESQUERDA** — que é
    exatamente a queixa. Perguntar à sessão devolve a resposta que produziu o
    defeito: a cura escrita como a sprint mandava passaria no teste com um dublê
    mudo e deixaria a janela dela igual. É o padrão que esta casa nomeou em
    04/09 — *quando o instrumento e o aparelho discordam, o aparelho ganha*.

    **QUEM É O DONO DA RESPOSTA CERTA É O COMPOSITOR**, e ele não tem chave: o
    COSMIC crava os botões à direita e ``~/.config/cosmic/`` não guarda nada
    sobre lado. Então o produto usa a constante do compositor **e só sob COSMIC**
    — fora dele o GTK já está certo, e mexer seria o aplicativo passando por cima
    de uma escolha que ninguém contestou.

    O ``lado_dos_botoes_na_sessao`` continua existindo e continua sendo lido:
    ele é o que a mordida arranca, e o que o relato imprime.
    """
    if not sessao_e_cosmic():
        return ""
    return LADO_DO_COSMIC


def adotar_a_barra_da_sessao() -> str:
    """Põe os botões da janela do lado do sistema. Devolve o layout adotado, ou ``""``.

    Escreve ``gtk-decoration-layout`` **dentro deste processo**, ao lado de onde
    o :func:`adotar_o_tema_da_sessao` já pergunta a sessão pelo tema. Nenhum
    outro GTK muda, e a configuração dela não é tocada — é a decisão ``1-a``.
    """
    layout = barra_que_o_sistema_usa()
    if not layout:
        return ""
    settings = Gtk.Settings.get_default()
    if settings is None:
        return ""
    try:
        if (settings.get_property("gtk-decoration-layout") or "") == layout:
            return ""  # já está do lado certo — nada a fazer
        settings.set_property("gtk-decoration-layout", layout)
    except (TypeError, ValueError) as exc:
        logger.warning("barra_da_sessao_nao_aplicavel", layout=layout, erro=str(exc))
        return ""
    logger.info("barra_da_sessao_adotada", layout=layout,
                sessao_dizia=lado_dos_botoes_na_sessao())
    return layout


def tema_escolhido_na_sessao() -> str:
    """O nome do tema GTK que a sessão escolheu, ou ``""`` se não der para saber.

    Pergunta ao ``Gio.Settings``, que lê o dconf direto — sem depender do backend
    gráfico nem do portal.
    """
    try:
        from gi.repository import Gio
    except ImportError:  # pragma: no cover — gi sem Gio não existe na prática
        return ""
    esquema, chave = _CHAVE_DO_TEMA
    try:
        fonte = Gio.SettingsSchemaSource.get_default()
        if fonte is None or fonte.lookup(esquema, True) is None:
            return ""  # o esquema não está instalado — não há o que perguntar
        return str(Gio.Settings.new(esquema).get_string(chave) or "")
    except Exception as exc:  # amplo de propósito: nunca impedir a janela de abrir
        logger.warning("tema_da_sessao_indisponivel", erro=str(exc))
        return ""


def adotar_o_tema_da_sessao() -> str:
    """Faz o processo usar o tema que ELA escolheu. Devolve o nome adotado, ou ``""``.

    O DEFEITO QUE ISTO CURA, fotografado por ela em 04/09/2026: ela abre a aba
    Gatilhos, clica num efeito pronto, e o menu nasce **branco, com a linha
    selecionada em azul**, no meio de uma interface escura.

    A CORRENTE, medida inteira:

    1. O ``.desktop`` instalado lança com ``env GDK_BACKEND=x11``
       (``install.sh:2806``), e o ``app/main._force_xwayland_on_cosmic`` faz o
       mesmo no arranque. A razão está escrita lá e é boa: no cosmic-comp
       nativo os popups de ``GtkComboBox``/``GtkMenu`` abrem **com fundo claro**,
       mal posicionados e com o grab quebrado.
    2. Sob XWayland, porém, o GTK3 **não lê o tema do portal** — ele espera um
       daemon XSettings, que o COSMIC não tem, e cai no ``settings.ini``.
    3. O ``~/.config/gtk-3.0/settings.ini`` dela declara **só**
       ``gtk-decoration-layout``. Não há ``gtk-theme-name``.
    4. Logo o processo cai no padrão do GTK — ``Adwaita``, **claro** — e todo
       widget que o CSS do autor não alcança nasce claro.

    O popup do ``<select>`` é exatamente esse caso: o WebKit o desenha **fora**
    da página, então nem o CSS de autor nem ``color-scheme: dark`` o alcançam.
    Medido no WebKitGTK 2.52.6, sob XWayland, com o cenário dela reproduzido:

    ======================================  ==================================
    o que se tentou                         o popup
    ======================================  ==================================
    nada (o estado de hoje)                 **BRANCO, com a linha azul**
    ``color-scheme: dark`` na página        branco — as fotos saem idênticas
    ``gtk-application-prefer-dark-theme``   branco — as fotos saem idênticas
    ``gtk-theme-name`` = o tema DELA        **escuro**
    ======================================  ==================================

    É por isso que esta função existe e a ``pedir_a_variante_escura`` não basta.

    E ELA NÃO ESCOLHE O TEMA — ela **pergunta qual ele é**. A escolha continua
    dela, no lugar onde ela a fez; o que se conserta é o processo ter perdido a
    resposta ao ser empurrado para o XWayland. Um aplicativo que cravasse
    ``adw-gtk3-dark`` passaria a ignorar a próxima troca de tema dela.
    """
    escolhido = tema_escolhido_na_sessao()
    if not escolhido:
        return ""
    settings = Gtk.Settings.get_default()
    if settings is None:
        return ""
    try:
        if (settings.get_property("gtk-theme-name") or "") == escolhido:
            return ""  # já é o dela — o portal entregou, nada a fazer
        settings.set_property("gtk-theme-name", escolhido)
    except (TypeError, ValueError) as exc:
        logger.warning("tema_da_sessao_nao_aplicavel", tema=escolhido, erro=str(exc))
        return ""
    logger.info("tema_da_sessao_adotado", tema=escolhido)
    return escolhido


def pedir_a_variante_escura() -> bool:
    """Pede ao GTK a variante ESCURA do tema do sistema. Devolve se conseguiu.

    BUG-GUI-COSMIC-WIDGET-CONTRAST-01: em COSMIC a sessão **não** aplica a
    variante escura do tema GTK por padrão — medido na máquina dela em
    04/09/2026, com a sessão inteira em escuro:

        gsettings org.gnome.desktop.interface color-scheme = 'prefer-dark'
        Gtk.Settings gtk-application-prefer-dark-theme     = False   ← aqui

    Sem este pedido, todo widget que o CSS do aplicativo **não alcança** herda o
    claro do sistema. Na janela GTK isso dava branco-sobre-branco em containers;
    na janela do WebKit dá o defeito que ela fotografou em 04/09: o popup de um
    ``<select>`` aberto nasce **branco, com a linha azul do sistema**, no meio de
    uma interface escura. O popup é desenhado pelo WebKit fora da página — CSS de
    autor não o alcança, e ``color-scheme: dark`` também não (medido nos dois, no
    WebKitGTK 2.52.6: as duas fotos saíram idênticas, brancas).

    ESTA FUNÇÃO TEM DOIS CHAMADORES, e é por isso que ela existe separada: a
    regra morava dentro do ``apply_theme``, que também carrega o CSS Drácula da
    janela antiga. A janela do WebKit não quer esse CSS — ela é HTML — mas quer
    exatamente esta linha, e nasceu sem ela. É o padrão que esta casa persegue:
    *a casa sabe e o produto não faz*.
    """
    settings = Gtk.Settings.get_default()
    if settings is None:
        return False
    try:
        settings.set_property("gtk-application-prefer-dark-theme", True)
    except (TypeError, ValueError) as exc:  # propriedade ausente em algum backend
        logger.warning("theme_prefer_dark_indisponivel", erro=str(exc))
        return False
    return True


def apply_theme(window: Gtk.Window) -> None:
    """Carrega theme.css e aplica à janela principal com classe .hefesto-dualsense4unix-window.

    Registra aviso via logger se o arquivo não for encontrado; nunca levanta
    exceção para não impedir a GUI de abrir sem tema.
    """
    if not _CSS_PATH.exists():
        logger.warning("theme_css_ausente", path=str(_CSS_PATH))
        return

    settings = Gtk.Settings.get_default()

    # A variante escura tem dono próprio — as duas janelas a pedem.
    pedir_a_variante_escura()

    delta = escala_fonte()

    # Canal 1 — a base HERDADA. Sem ele, só as regras em px cresceriam e a
    # interface ficaria com dois corpos de texto diferentes.
    if settings is not None and delta:
        try:
            atual = settings.get_property("gtk-font-name") or ""
            settings.set_property(
                "gtk-font-name", escalar_nome_da_fonte(atual, delta)
            )
        except (TypeError, ValueError) as exc:
            logger.warning("theme_font_name_indisponivel", erro=str(exc))

    # Canal 2 — as regras em px, reescritas EM MEMÓRIA. É por isso que a carga
    # é `load_from_data` e não `load_from_path`: o arquivo em disco continua
    # sendo a fonte da verdade dos degraus, e o delta não é persistido nele.
    provider = Gtk.CssProvider()
    try:
        bruto = _CSS_PATH.read_text(encoding="utf-8")
        provider.load_from_data(escalar_css(bruto, delta).encode("utf-8"))
    except Exception as exc:  # GLib.Error, OSError
        logger.warning("theme_css_falha_carga", erro=str(exc))
        return

    screen = Gdk.Screen.get_default()
    if screen is None:
        logger.warning("theme_sem_display_disponivel")
        return

    Gtk.StyleContext.add_provider_for_screen(
        screen,
        provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
    )
    window.get_style_context().add_class("hefesto-dualsense4unix-window")

    # FEAT-A11Y-HIGH-CONTRAST-01 (v3.4.0): detecta tema HighContrast do
    # sistema (GNOME/COSMIC Accessibility > Contraste alto) e aplica nossa
    # classe de override. GTK3 não tem @media (prefers-contrast: more) — noqa-acento
    # nativo — o canal real e essa classe.
    if settings is not None:
        theme_name = settings.get_property("gtk-theme-name") or ""
        if "highcontrast" in theme_name.lower():
            window.get_style_context().add_class(
                "hefesto-dualsense4unix-high-contrast"
            )
            logger.info("theme_high_contrast_aplicado", system_theme=theme_name)

    logger.info("theme_aplicado", css=str(_CSS_PATH), escala=delta)
