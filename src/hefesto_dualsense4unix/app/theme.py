"""Aplicação do tema Drácula ao Hefesto - DualSense4Unix via Gtk.CssProvider.

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
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

_CSS_PATH = GUI_DIR / "theme.css"

from hefesto_dualsense4unix.app.escala import (  # noqa: F401 — reexportados
    CHAVE_ESCALA,
    DEGRAUS_DE_ESCALA,
    ESCALA_MAXIMA,
    ESCALA_PADRAO,
    degrau_da_escala,
    escala_gravada,
)

_PONTOS_POR_PIXEL = 0.75

_PONTOS_PADRAO_PANGO = 10.0

_REGRA_TAMANHO = re.compile(r"(font-size\s*:\s*)([0-9]+(?:\.[0-9]+)?)px")
_NOME_COM_TAMANHO = re.compile(r"^(.*?)\s+([0-9]+(?:\.[0-9]+)?)$")

_escala_aplicada: int | None = None


def escala_fonte() -> int:
    """Delta de tamanho da fonte, em px, APLICADO nesta sessão."""
    global _escala_aplicada
    if _escala_aplicada is not None:
        return _escala_aplicada
    _escala_aplicada = escala_gravada()
    return _escala_aplicada


def escalar_css(texto: str, delta: int) -> str:
    """Soma ``delta`` px a cada ``font-size: Npx`` do CSS."""
    if not delta:
        return texto

    def _somar(m: re.Match[str]) -> str:
        return f"{m.group(1)}{float(m.group(2)) + delta:g}px"

    return _REGRA_TAMANHO.sub(_somar, texto)


def escalar_nome_da_fonte(nome: str, delta: int) -> str:
    """Soma ``delta`` px (convertidos em pontos) ao nome de fonte do GTK."""
    if not delta:
        return nome
    casado = _NOME_COM_TAMANHO.match(nome.strip())
    if casado is not None:
        familia, pontos = casado.group(1), float(casado.group(2))
    else:
        familia, pontos = nome.strip(), _PONTOS_PADRAO_PANGO
    return f"{familia} {pontos + delta * _PONTOS_POR_PIXEL:g}"


_CHAVE_DO_TEMA = ("org.gnome.desktop.interface", "gtk-theme")

_CHAVE_DOS_BOTOES = ("org.gnome.desktop.wm.preferences", "button-layout")

LADO_DO_COSMIC = ":minimize,maximize,close"


def sessao_e_cosmic() -> bool:
    """Esta sessão é COSMIC? Lê o ambiente a cada chamada, nunca na importação."""
    import os

    for chave in ("XDG_CURRENT_DESKTOP", "XDG_SESSION_DESKTOP", "DESKTOP_SESSION"):
        if "cosmic" in (os.environ.get(chave) or "").lower():
            return True
    return False


def lado_dos_botoes_na_sessao() -> str:
    """O que o ``button-layout`` do dconf responde, ou ``""`` se não der para saber."""
    try:
        from gi.repository import Gio
    except ImportError:  # pragma: no cover — gi sem Gio não existe na prática
        return ""
    esquema, chave = _CHAVE_DOS_BOTOES
    try:
        fonte = Gio.SettingsSchemaSource.get_default()
        if fonte is None or fonte.lookup(esquema, True) is None:
            return ""
        return str(Gio.Settings.new(esquema).get_string(chave) or "")
    except Exception as exc:
        logger.warning("botoes_da_sessao_indisponiveis", erro=str(exc))
        return ""


def barra_que_o_sistema_usa() -> str:
    """De que lado ESTA sessão põe fechar/maximizar/minimizar. ``""`` = não mexer."""
    if not sessao_e_cosmic():
        return ""
    return LADO_DO_COSMIC


def adotar_a_barra_da_sessao() -> str:
    """Põe os botões da janela do lado do sistema. Devolve o layout adotado, ou ``""``."""
    layout = barra_que_o_sistema_usa()
    if not layout:
        return ""
    settings = Gtk.Settings.get_default()
    if settings is None:
        return ""
    try:
        if (settings.get_property("gtk-decoration-layout") or "") == layout:
            return ""
        settings.set_property("gtk-decoration-layout", layout)
    except (TypeError, ValueError) as exc:
        logger.warning("barra_da_sessao_nao_aplicavel", layout=layout, erro=str(exc))
        return ""
    logger.info("barra_da_sessao_adotada", layout=layout,
                sessao_dizia=lado_dos_botoes_na_sessao())
    return layout


def tema_escolhido_na_sessao() -> str:
    """O nome do tema GTK que a sessão escolheu, ou ``""`` se não der para saber."""
    try:
        from gi.repository import Gio
    except ImportError:  # pragma: no cover — gi sem Gio não existe na prática
        return ""
    esquema, chave = _CHAVE_DO_TEMA
    try:
        fonte = Gio.SettingsSchemaSource.get_default()
        if fonte is None or fonte.lookup(esquema, True) is None:
            return ""
        return str(Gio.Settings.new(esquema).get_string(chave) or "")
    except Exception as exc:
        logger.warning("tema_da_sessao_indisponivel", erro=str(exc))
        return ""


def adotar_o_tema_da_sessao() -> str:
    """Faz o processo usar o tema que ELA escolheu. Devolve o nome adotado, ou ``""``."""
    escolhido = tema_escolhido_na_sessao()
    if not escolhido:
        return ""
    settings = Gtk.Settings.get_default()
    if settings is None:
        return ""
    try:
        if (settings.get_property("gtk-theme-name") or "") == escolhido:
            return ""
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
    except (TypeError, ValueError) as exc:
        logger.warning("theme_prefer_dark_indisponivel", erro=str(exc))
        return False
    return True


def apply_theme(window: Gtk.Window) -> None:
    """Carrega theme.css e aplica à janela principal com classe .hefesto-dualsense4unix-window."""
    if not _CSS_PATH.exists():
        logger.warning("theme_css_ausente", path=str(_CSS_PATH))
        return

    settings = Gtk.Settings.get_default()

    pedir_a_variante_escura()

    delta = escala_fonte()

    if settings is not None and delta:
        try:
            atual = settings.get_property("gtk-font-name") or ""
            settings.set_property(
                "gtk-font-name", escalar_nome_da_fonte(atual, delta)
            )
        except (TypeError, ValueError) as exc:
            logger.warning("theme_font_name_indisponivel", erro=str(exc))

    provider = Gtk.CssProvider()
    try:
        bruto = _CSS_PATH.read_text(encoding="utf-8")
        provider.load_from_data(escalar_css(bruto, delta).encode("utf-8"))
    except Exception as exc:
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

    # classe de override. GTK3 não tem @media (prefers-contrast: more) — noqa-acento
    if settings is not None:
        theme_name = settings.get_property("gtk-theme-name") or ""
        if "highcontrast" in theme_name.lower():
            window.get_style_context().add_class(
                "hefesto-dualsense4unix-high-contrast"
            )
            logger.info("theme_high_contrast_aplicado", system_theme=theme_name)

    logger.info("theme_aplicado", css=str(_CSS_PATH), escala=delta)
