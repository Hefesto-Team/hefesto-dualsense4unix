"""COR-QUE-NAO-PINTAVA-01 (19/08/2026) — a classe de cor que o GTK ignorava.

As cinco classes de cor do `theme.css` (`status-ok`, `status-warn`,
`status-err`, `accent-purple`, `accent-pink`) nasceram SOLTAS — seletor de
especificidade (0,1,0). A regra `.hefesto-dualsense4unix-window label` do mesmo
arquivo é (0,1,1) e casa o label DIRETAMENTE, então ela vencia: a classe era
aplicada, o GTK a lia, e o texto saía na cor do tema.

A casa já tinha visto o sintoma e contornado sem achar a causa. O
`app/widgets/painel_no_jogo.py:135` diz, textual: *"a classe existe, é aplicada
e não pinta nada (a primeira foto saiu com 'no jogo agora' em branco)"*.

Quem sofria, contado em 19/08: `status-warn` em doze lugares, dois deles
rótulos do próprio `main.glade` (`:310` e `:325`).

ESTE TESTE MEDE A COR RENDERIZADA, não o texto do CSS. Um teste que lesse o
arquivo passaria com a regra solta — e foi exatamente a regra solta que não
pintou nada por semanas.
"""

from __future__ import annotations

from tests.conftest import exigir_gi_real

# `import gi` cru aceita o stub que outro arquivo planta em `sys.modules`, e com
# o stub dentro o `Gtk.init_check()` estoura e derruba a COLETA deste módulo.
exigir_gi_real("COR-QUE-NAO-PINTAVA-01 (a cor que o GTK resolvia)")

from pathlib import Path

import gi
import pytest

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gtk

RAIZ = Path(__file__).resolve().parents[2]
THEME = RAIZ / "src/hefesto_dualsense4unix/gui/theme.css"

#: classe -> a cor que o `theme.css` promete, em (r, g, b) de 0 a 255.
PROMESSAS = {
    "hefesto-dualsense4unix-status-ok": (0x50, 0xFA, 0x7B),
    "hefesto-dualsense4unix-status-warn": (0xF1, 0xFA, 0x8C),
    "hefesto-dualsense4unix-status-err": (0xFF, 0x55, 0x55),
    "hefesto-dualsense4unix-accent-purple": (0xBD, 0x93, 0xF9),
    "hefesto-dualsense4unix-accent-pink": (0xFF, 0x79, 0xC6),
}


def _gtk_pronto() -> bool:
    try:
        return bool(Gtk.init_check()[0])
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _gtk_pronto(), reason="sem GTK/display utilizável"
)


def _cor_resolvida(classe: str) -> tuple[int, int, int]:
    """A cor que o GTK REALMENTE resolve para um label dentro da janela.

    Monta a mesma hierarquia da tela — a janela com a classe do aplicativo e o
    label dentro dela —, aplica o `theme.css` no screen e pergunta ao contexto
    de estilo. É a única pergunta que a regra solta responde errado.
    """
    provider = Gtk.CssProvider()
    provider.load_from_path(str(THEME))
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(),
        provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
    )
    janela = Gtk.OffscreenWindow()
    janela.get_style_context().add_class("hefesto-dualsense4unix-window")
    caixa = Gtk.Box()
    rotulo = Gtk.Label(label="texto")
    rotulo.get_style_context().add_class(classe)
    caixa.add(rotulo)
    janela.add(caixa)
    janela.show_all()
    while Gtk.events_pending():
        Gtk.main_iteration()
    rgba = rotulo.get_style_context().get_color(Gtk.StateFlags.NORMAL)
    return (
        round(rgba.red * 255),
        round(rgba.green * 255),
        round(rgba.blue * 255),
    )


class TestAClassePinta:
    @pytest.mark.parametrize("classe,esperado", sorted(PROMESSAS.items()))
    def test_a_cor_prometida_chega_ao_label(
        self, classe: str, esperado: tuple[int, int, int]
    ) -> None:
        """A MORDIDA. Tire o escopo da window no `theme.css` e isto reprova.

        Sem o escopo, o GTK devolve a cor do tema (o `@fg` claro da janela) e
        não a cor da classe — que é o "aplicada e não pinta nada" que a casa
        registrou em `painel_no_jogo.py:135`.
        """
        obtido = _cor_resolvida(classe)
        assert obtido == esperado, (
            f"a classe `{classe}` é aplicada e o GTK resolve {obtido}, não "
            f"{esperado}: a regra perdeu a disputa de especificidade para "
            "`.hefesto-dualsense4unix-window label`, e o texto sai na cor do "
            "tema — foi assim que dois rótulos do main.glade ficaram brancos"
        )
