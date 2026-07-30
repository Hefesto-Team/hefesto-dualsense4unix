"""LARGURA-01/E1 — as barras da aba Rumble param de atravessar a janela.

A queixa dela, sobre a janela maximizada: as barras de vibração vão de ponta a
ponta da tela para dizer um número de 0 a 100. Medido numa
`Gtk.OffscreenWindow` de 1920px com o tema na escala que de fato sai:
`rumble_weak_scale` e `rumble_strong_scale` recebiam **1731px cada** para 58px
de natural, e o `rumble_policy_slider` 837px. É o mesmo defeito que ela já
apontou nas barras de L2/R2 DENTRO do card, aqui fora dele.

Este portão mede a ALOCAÇÃO, não o pedido: widget sem janela devolve 1x1 em
tudo, e um teste de geometria sobre ele passa com qualquer layout (nota que a
SOM-01 deixou). Por isso a janela é montada, mostrada e o laço rodado antes de
ler `get_allocation`.

A mordida está escrita no aceite: arrancar o par
`halign=start` + `width-request` de uma das três faz a barra voltar aos 1731px
(ou 837px) e este arquivo reprova apontando qual.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: antes de qualquer import de `gi`. `importorskip("gi")`
# aceitaria o stub que outro arquivo planta em sys.modules; sem guarda nenhuma
# este módulo derrubaria a COLETA no CI headless em vez de pular.
exigir_gi_real("largura das barras de vibracao")

from collections.abc import Iterator

import pytest

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")
_gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gtk

from hefesto_dualsense4unix.app.constants import GUI_DIR, MAIN_GLADE
from hefesto_dualsense4unix.app.theme import (
    escala_fonte,
    escalar_css,
    escalar_nome_da_fonte,
)

#: A tela dela, maximizada. É onde o esticão aparece.
LARGURA_DA_TELA_DELA = 1920

#: Teto aceito para barra/entrada em qualquer aba. O número vem da receita já no
#: ar dentro do card (`LARGURA_BARRA_GATILHO_UNICO = 400`,
#: `LARGURA_GYRO_UNICO = 420`, `app/widgets/controller_card.py:337-339`) — a
#: folga de 20px cobre a borda/foco que o tema desenha em volta.
TETO_DA_BARRA = 420

#: As barras que ESTA leva cobriu, com a largura que cada uma recebia antes.
#: A aba Rumble entrou sozinha por ter a maior folga de largura mínima medida
#: (473px de 1180). As outras seis da lista da LARGURA-01 seguem esticadas de
#: propósito, e a razão de cada uma está no relatório da sprint.
BARRAS_COM_TETO: dict[str, int] = {
    "rumble_weak_scale": 1731,
    "rumble_strong_scale": 1731,
    "rumble_policy_slider": 837,
}


def _gtk_pronto() -> bool:
    try:
        return bool(Gtk.init_check()[0])
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _gtk_pronto(), reason="sem GTK/display utilizável"
)


@pytest.fixture(scope="module")
def alocacoes() -> Iterator[dict[str, int]]:
    """Monta a janela inteira offscreen em 1920 e devolve o que cada barra recebeu.

    O tema entra pelos DOIS canais de `app.theme.apply_theme` (o CSS com os
    `font-size` reescritos e o `gtk-font-name`): sem o segundo, quase toda a
    janela mediria a fonte padrão do Pango e o número não seria o da tela dela.
    """
    delta = escala_fonte()
    tela = Gdk.Screen.get_default()
    provider = Gtk.CssProvider()
    bruto = (GUI_DIR / "theme.css").read_text(encoding="utf-8")
    provider.load_from_data(escalar_css(bruto, delta).encode("utf-8"))
    if tela is not None:
        Gtk.StyleContext.add_provider_for_screen(
            tela, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
    settings = Gtk.Settings.get_default()
    anterior = None
    if settings is not None and delta:
        anterior = settings.get_property("gtk-font-name")
        settings.set_property(
            "gtk-font-name", escalar_nome_da_fonte(anterior or "", delta)
        )

    builder = Gtk.Builder()
    builder.add_from_file(str(MAIN_GLADE))
    root = builder.get_object("root_box")
    pai = root.get_parent()
    if pai is not None:
        pai.remove(root)
    win = Gtk.OffscreenWindow()
    win.get_style_context().add_class("hefesto-dualsense4unix-window")
    win.add(root)
    win.set_size_request(LARGURA_DA_TELA_DELA, 1080)
    win.show_all()
    # O GtkNotebook só ALOCA a página visível — sem passar por todas, a aba
    # Rumble devolveria 1x1 e o teste passaria sem medir nada.
    notebook = builder.get_object("main_notebook")
    for indice in range(notebook.get_n_pages()):
        notebook.set_current_page(indice)
        for _ in range(400):
            if not Gtk.events_pending():
                break
            Gtk.main_iteration()

    medidas = {}
    for nome in BARRAS_COM_TETO:
        widget = builder.get_object(nome)
        assert widget is not None, f"{nome} saiu do main.glade"
        medidas[nome] = widget.get_allocation().width

    yield medidas

    if settings is not None and anterior is not None:
        settings.set_property("gtk-font-name", anterior)
    if tela is not None:
        Gtk.StyleContext.remove_provider_for_screen(tela, provider)


@pytest.mark.parametrize("nome", sorted(BARRAS_COM_TETO))
def test_a_barra_nao_atravessa_mais_a_janela(
    nome: str, alocacoes: dict[str, int]
) -> None:
    recebido = alocacoes[nome]
    assert recebido <= TETO_DA_BARRA, (
        f"{nome} recebeu {recebido}px numa janela de {LARGURA_DA_TELA_DELA} "
        f"(teto {TETO_DA_BARRA}; antes desta leva eram "
        f"{BARRAS_COM_TETO[nome]}px). Provavelmente alguém tirou o par "
        "`halign=start` + `width-request` do glade. Lembre que `width-request` "
        "SOZINHO não resolve: no GTK3 pedido de tamanho é MÍNIMO, e o `hexpand` "
        "continua esticando a barra."
    )


def test_a_barra_continua_util_e_nao_virou_um_toco(
    alocacoes: dict[str, int]
) -> None:
    """O outro lado do teto: 400px de barra ainda se arrasta com o mouse.

    Um `width-request` errado (ou um `halign` sem ele) deixaria a barra no
    natural de 58px — teto cumprido e controle inutilizável.
    """
    curtas = {
        nome: valor for nome, valor in alocacoes.items() if valor < 200
    }
    assert not curtas, (
        f"barra encolhida demais para ser arrastada: {curtas}. O teto é para "
        "devolver espaço, não para transformar o controle num toco."
    )
