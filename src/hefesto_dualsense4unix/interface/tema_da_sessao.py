"""O tema e a barra da sessão, adotados pela janela da interface (`interface/janela.py`)."""
# ruff: noqa: E402
from __future__ import annotations

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)


_CHAVE_DO_TEMA = ("org.gnome.desktop.interface", "gtk-theme")

_CHAVE_DOS_BOTOES = ("org.gnome.desktop.wm.preferences", "button-layout")

LADO_DO_COSMIC = ":minimize,maximize,close"

#: De que lado da barra os botões desta casa ficam. O produto segue o do sistema; uma extensão de
#: tema pode escolher o outro (22/10/2026, O-TEMA-DA-EXTENSAO-ESCOLHE-O-LADO-DOS-BOTOES).
ESQUERDA = "esquerda"
DIREITA = "direita"


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


def lado_do_sistema() -> str:
    """De que lado o sistema põe os botões das janelas: ``esquerda`` ou ``direita``.

    No COSMIC é a direita, e a sessão não é consultada (o ``button-layout`` dela mente, como o
    teste de 21/10 mede). Fora dele vale o que o ``button-layout`` diz antes dos dois pontos; sem
    resposta legível, ou sem os dois pontos, a direita.
    """
    if sessao_e_cosmic():
        return DIREITA
    layout = lado_dos_botoes_na_sessao()
    if ":" not in layout:
        return DIREITA
    antes = layout.split(":", 1)[0]
    return ESQUERDA if "close" in [p.strip() for p in antes.split(",")] else DIREITA


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
    """Faz o processo usar o tema que O usuário escolheu. Devolve o nome adotado, ou ``""``."""
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

    Em COSMIC a sessão não aplica a variante escura sozinha, e o popup de um ``<select>`` do
    WebKit, desenhado fora da página, nasce branco no meio da interface escura. O porquê, com a
    medida de 04/09/2026, está em ``docs/research/o-porque-dos-modulos.md``.
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


