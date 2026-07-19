"""GUI-05 (P4/P5) — tema dos diálogos + segmentado read-only da ficha.

P5 (estudo 2026-07-18): `_build_wrapper_dialog` criava `Gtk.MessageDialog` SEM
a classe `.hefesto-dualsense4unix-window` — TODO o CSS Drácula é escopado a
ela, e sob XWayland no COSMIC o diálogo herdava Adwaita CLARO. A cura tem duas
camadas (as duas testadas aqui):

1. VARREDURA: todo `Gtk.MessageDialog`/`Gtk.Dialog` do app aplica a classe
   (helper `gui_dialogs._apply_app_theme` ou o `add_class` literal);
2. estrutural: bloco top-level `messagedialog` no theme.css (test_theme_css).

P4: a ficha do controle externo ganha um seletor SEGMENTADO READ-ONLY
(Nintendo | Xbox) marcando o modo DETECTADO — sem popup (veto 8BIT-02). A
camada pura vive em test_external_controllers; aqui ficam a montagem GTK real
(guardada por display) e os espelhos por fonte que rodam headless.
"""
from __future__ import annotations

import contextlib
import inspect
import re
from pathlib import Path

import pytest

_APP_DIR = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "hefesto_dualsense4unix"
    / "app"
)

#: Como um diálogo pode receber a classe de tema: pelo helper canônico ou pelo
#: add_class literal (módulos que não importam gui_dialogs).
_THEME_MARKS = (
    "_apply_app_theme(",
    'add_class("hefesto-dualsense4unix-window")',
)


def _tem_tema(src: str) -> bool:
    # Compacta o whitespace antes de casar: o `add_class(` quebrado em duas
    # linhas pelo limite de coluna (daemon_actions) continua contando.
    compacto = re.sub(r"\s+", "", src)
    return any(mark in compacto for mark in _THEME_MARKS)


# ---------------------------------------------------------------------------
# Varredura: cada construtor de diálogo conhecido aplica a classe de tema
# ---------------------------------------------------------------------------


def _funcoes_com_dialogo() -> list[tuple[str, str]]:
    """(nome, fonte) de cada função/método do app que constrói um diálogo."""
    from hefesto_dualsense4unix.app import gui_dialogs
    from hefesto_dualsense4unix.app.actions.daemon_actions import (
        DaemonActionsMixin,
    )
    from hefesto_dualsense4unix.app.actions.home_actions import HomeActionsMixin
    from hefesto_dualsense4unix.app.actions.launch_wrapper_dialog import (
        LaunchWrapperDialogMixin,
    )

    alvos = [
        gui_dialogs.prompt_profile_name,
        gui_dialogs.prompt_overwrite_existing,
        gui_dialogs.confirm_downgrade_match_to_any,
        gui_dialogs.prompt_import_conflict,
        gui_dialogs.confirm_restore_default,
        gui_dialogs.confirm_delete_profile,
        gui_dialogs.show_external_controller,
        LaunchWrapperDialogMixin._build_wrapper_dialog,
        HomeActionsMixin._on_home_shutdown_clicked,
        DaemonActionsMixin._show_restart_error,
        DaemonActionsMixin._build_steam_apply_confirm_dialog,
    ]
    return [(fn.__qualname__, inspect.getsource(fn)) for fn in alvos]


@pytest.mark.parametrize(
    ("nome", "src"),
    _funcoes_com_dialogo(),
    ids=[nome for nome, _ in _funcoes_com_dialogo()],
)
def test_cada_dialogo_conhecido_aplica_a_classe_de_tema(
    nome: str, src: str
) -> None:
    assert _tem_tema(src), (
        f"{nome} constrói um diálogo sem a classe de tema "
        "(.hefesto-dualsense4unix-window) — ele abriria CLARO no COSMIC"
    )


def test_varredura_nenhum_modulo_do_app_cria_dialogo_sem_tema() -> None:
    """Guarda de regressão: módulo do app/ que constrói Gtk.MessageDialog ou
    Gtk.Dialog precisa aplicar a classe de tema em algum lugar do arquivo.

    Granularidade por ARQUIVO (a por-função vive no teste parametrizado
    acima): pega o esquecimento clássico — um diálogo novo num módulo que
    nunca tematizou nada.
    """
    padrao = re.compile(r"Gtk\.(MessageDialog|Dialog)\(")
    problemas: list[str] = []
    for arquivo in sorted(_APP_DIR.rglob("*.py")):
        texto = arquivo.read_text(encoding="utf-8")
        if padrao.search(texto) and not _tem_tema(texto):
            problemas.append(str(arquivo.relative_to(_APP_DIR)))
    assert problemas == [], (
        "Módulos com diálogo GTK sem a classe de tema: "
        f"{problemas} — use gui_dialogs._apply_app_theme"
    )


def test_helper_do_tema_aplica_a_classe_canonica() -> None:
    """Espelho stub-level do helper: um fake de diálogo recebe a classe."""
    from hefesto_dualsense4unix.app.gui_dialogs import _apply_app_theme

    class _Ctx:
        def __init__(self) -> None:
            self.classes: list[str] = []

        def add_class(self, name: str) -> None:
            self.classes.append(name)

    class _FakeDialog:
        def __init__(self) -> None:
            self.ctx = _Ctx()

        def get_style_context(self) -> _Ctx:
            return self.ctx

    dlg = _FakeDialog()
    _apply_app_theme(dlg)
    assert dlg.ctx.classes == ["hefesto-dualsense4unix-window"]


def test_helper_do_tema_nao_propaga_excecao_de_stub() -> None:
    """Style context quebrado (stub de teste) não pode derrubar o diálogo."""
    from hefesto_dualsense4unix.app.gui_dialogs import _apply_app_theme

    class _SemStyle:
        pass

    _apply_app_theme(_SemStyle())  # não levanta


# ---------------------------------------------------------------------------
# P4 — segmentado read-only da ficha do externo
# ---------------------------------------------------------------------------

_NINTENDO_USB = {
    "name": "Nintendo Co., Ltd. Pro Controller",
    "vid": "057e",
    "pid": "2009",
    "bus": "usb",
    "driver": "nintendo",
}
_DESCONHECIDO = {"name": "Marca Xpto Pad", "vid": "abcd", "pid": "0001", "bus": "usb"}


def test_ficha_monta_o_segmentado_e_o_subtitulo() -> None:
    """Espelho por fonte (headless): a ficha empacota a linha do segmentado
    (`_external_mode_row`) e o subtítulo, mantendo o texto de orientação
    existente (`mode_guidance`)."""
    from hefesto_dualsense4unix.app import gui_dialogs

    src = inspect.getsource(gui_dialogs.show_external_controller)
    assert "_external_mode_row(" in src
    assert "mode_guidance(" in src  # a orientação existente continua lá


def test_external_mode_row_e_read_only_por_construcao() -> None:
    """Espelho por fonte (headless): insensitive + tooltip + sem popup."""
    from hefesto_dualsense4unix.app import gui_dialogs

    src = inspect.getsource(gui_dialogs._external_mode_row)
    assert "SegmentedSelector" in src  # padrão da casa, nunca combo/popup
    assert "ComboBox" not in src
    assert "set_sensitive(False)" in src
    assert "MODE_SELECTOR_TOOLTIP" in src
    assert "MODE_SELECTOR_SUBTITLE" in src


_DISPLAY_OK = False
with contextlib.suppress(Exception):
    import gi as _gi

    _gi.require_version("Gtk", "3.0")
    from gi.repository import Gdk as _Gdk

    _DISPLAY_OK = _Gdk.Display.get_default() is not None


@pytest.mark.skipif(
    not _DISPLAY_OK, reason="sem display GTK — montagem real do segmentado"
)
class TestFichaGtkReal:
    def test_segmentado_marca_o_modo_e_nao_e_clicavel(self) -> None:
        from hefesto_dualsense4unix.app.actions.external_controllers import (
            MODE_SELECTOR_SUBTITLE,
            MODE_SELECTOR_TOOLTIP,
        )
        from hefesto_dualsense4unix.app.gui_dialogs import _external_mode_row

        montado = _external_mode_row(_NINTENDO_USB)
        assert montado is not None
        row, sub = montado
        # a linha tem o rótulo + o seletor
        chave, seletor = row.get_children()
        assert "O jogo vê como" in chave.get_text()
        assert seletor.get_active_id() == "nintendo"
        assert seletor.get_sensitive() is False  # read-only de verdade
        assert seletor.get_tooltip_text() == MODE_SELECTOR_TOOLTIP
        assert sub.get_text() == MODE_SELECTOR_SUBTITLE

    def test_controle_sem_dois_modos_nao_monta_nada(self) -> None:
        from hefesto_dualsense4unix.app.gui_dialogs import _external_mode_row

        assert _external_mode_row(_DESCONHECIDO) is None
