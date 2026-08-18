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


def escala_fonte() -> int:
    """Delta de tamanho da fonte, em px, lido das preferências da GUI.

    Valor fora da faixa (ou de tipo errado, num arquivo editado à mão) cai no
    padrão em vez de quebrar a abertura da janela — o tema NUNCA pode ser o
    motivo de a interface não abrir.
    """
    global _escala_aplicada
    if _escala_aplicada is not None:
        return _escala_aplicada
    bruto = load_gui_prefs().get(CHAVE_ESCALA, ESCALA_PADRAO)
    if isinstance(bruto, bool) or not isinstance(bruto, (int, float)):
        logger.warning("theme_escala_invalida", valor=repr(bruto))
        bruto = ESCALA_PADRAO
    delta = int(bruto)
    if delta < 0 or delta > ESCALA_MAXIMA:
        logger.warning("theme_escala_fora_da_faixa", valor=delta)
        delta = max(0, min(ESCALA_MAXIMA, delta))
    _escala_aplicada = delta
    return delta


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


def apply_theme(window: Gtk.Window) -> None:
    """Carrega theme.css e aplica à janela principal com classe .hefesto-dualsense4unix-window.

    Registra aviso via logger se o arquivo não for encontrado; nunca levanta
    exceção para não impedir a GUI de abrir sem tema.
    """
    if not _CSS_PATH.exists():
        logger.warning("theme_css_ausente", path=str(_CSS_PATH))
        return

    settings = Gtk.Settings.get_default()

    # BUG-GUI-COSMIC-WIDGET-CONTRAST-01: camada defensiva. Em COSMIC a sessão
    # não aplica a variante escura do tema GTK por padrão, então containers/
    # widgets não cobertos pelo nosso CSS herdam o claro do sistema (causando
    # branco-sobre-branco). Pedir a variante escura faz o tema-base do sistema
    # já entregar fundos escuros onde existir; o CSS Drácula continua sendo o
    # canal principal (PRIORITY_APPLICATION sobrepõe o tema mesmo assim).
    if settings is not None:
        try:
            settings.set_property("gtk-application-prefer-dark-theme", True)
        except (TypeError, ValueError) as exc:  # propriedade ausente em algum backend
            logger.warning("theme_prefer_dark_indisponivel", erro=str(exc))

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
