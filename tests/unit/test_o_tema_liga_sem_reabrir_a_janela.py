"""O tema liga sem reabrir a janela, e o GTK segue o tema
(O-TEMA-LIGA-SEM-REABRIR-A-JANELA-E-O-GTK-SEGUE-O-TEMA-01).

Medido em 20/10/2026: a `PonteDaTela` lia o tema uma vez, na abertura, e a chave da Experimental
só gravava o registro; as cores mudavam depois de fechar e abrir a interface. E a variante escura
do GTK era pedida com qualquer tema: com o tema claro, a lista aberta de um `<select>` nascia
escura. Agora a janela vigia o registro e troca as folhas de usuário sem recarregar a página
(`PonteDaTela.trocar_o_tema`), a variante segue o fundo que vale (`mods.tema.e_escuro`) e a barra
pinta o `--panel` e o `--fg` do tema.

A sonda abre uma `PonteDaTela` de verdade num `Gtk.OffscreenWindow`, sob a tela de mentira, e lê o
fundo que a página pinta depois de cada troca; a marca posta pela página na carga prova que ela
não recarregou.

MORDIDA (executada em 21/10/2026): sem o `remove_all_style_sheets` no `trocar_o_tema`, o tema
velho fica no `UserContentManager`, desligar não volta à casa, e
`test_a_troca_repinta_sem_recarregar_e_desligar_volta_a_casa` reprova.
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
from types import SimpleNamespace

import pytest

from hefesto_dualsense4unix.interface import janela
from hefesto_dualsense4unix.mods import tema

RAIZ = pathlib.Path(__file__).resolve().parents[2]
CASA = tema.tokens_do_root((RAIZ / "mockup" / "01-jogar.html").read_text(encoding="utf-8"))
CLARO = (":root{--app-bg:#eef0f5 !important;--panel:#ffffff !important;"
         "--fg:#1c1e29 !important;}")

_SONDA = r"""
import json
from hefesto_dualsense4unix.utils.tela_de_mentira import garantir_tela_de_mentira
garantir_tela_de_mentira(anunciar=False)
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk
from hefesto_dualsense4unix.interface.janela import PonteDaTela

A = ":root{--app-bg:#102030 !important;}"
B = ":root{--app-bg:#eef0f5 !important;}"
PAGINA = ("<html><head><style>:root{--app-bg:#21222c}body{background:var(--app-bg)}</style>"
          "</head><body><script>window.__marca = Math.random();</script>x</body></html>")
ponte = PonteDaTela(folha=None, tema_de_cores=A)
janela = Gtk.OffscreenWindow()
janela.set_default_size(300, 200)
janela.add(ponte.view)
janela.show_all()
ponte.view.load_html(PAGINA, "file:///sonda/")

def girar(segundos):
    fim = GLib.get_monotonic_time() + int(segundos * 1e6)
    while GLib.get_monotonic_time() < fim:
        Gtk.main_iteration_do(False)

def ler():
    caixa = {}
    ponte.perguntar(
        "JSON.stringify([getComputedStyle(document.body).backgroundColor, window.__marca])",
        lambda valor, erro: caixa.update(valor=valor, erro=repr(erro) if erro else ""))
    fim = GLib.get_monotonic_time() + 5_000_000
    while "valor" not in caixa and GLib.get_monotonic_time() < fim:
        Gtk.main_iteration_do(False)
    return json.loads(caixa.get("valor") or "[null, null]")

def esperar(cor):
    for _ in range(40):
        lido = ler()
        if lido[0] == cor:
            return lido
        girar(0.05)
    return lido

girar(1.0)
saida = {"A": esperar("rgb(16, 32, 48)")}
ponte.trocar_o_tema(B)
saida["B"] = esperar("rgb(238, 240, 245)")
ponte.trocar_o_tema("")
saida["sem"] = esperar("rgb(33, 34, 44)")
from hefesto_dualsense4unix.interface.janela import pedir_a_variante
ajustes = Gtk.Settings.get_default()
saida["variante"] = []
for folha in (B, ""):
    saida["variante"].append([pedir_a_variante(folha),
                              ajustes.get_property("gtk-application-prefer-dark-theme")])
print(json.dumps(saida))
"""


@pytest.fixture(scope="module")
def trocas() -> dict[str, list[object]]:
    ambiente = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    filho = subprocess.run([sys.executable, "-c", _SONDA], env=ambiente,
                           capture_output=True, text=True, timeout=180)
    if filho.returncode != 0:
        pytest.skip(f"o WebKit não subiu na tela de mentira: {filho.stderr.strip()[-300:]}")
    return dict(json.loads(filho.stdout.strip().splitlines()[-1]))


def test_a_troca_repinta_sem_recarregar_e_desligar_volta_a_casa(
        trocas: dict[str, list[object]]) -> None:
    assert trocas["A"][0] == "rgb(16, 32, 48)", trocas
    assert trocas["B"][0] == "rgb(238, 240, 245)", trocas
    assert trocas["sem"][0] == "rgb(33, 34, 44)", trocas
    marcas = {trocas[k][1] for k in ("A", "B", "sem")}
    assert len(marcas) == 1 and None not in marcas, f"a página recarregou: {trocas}"


def test_a_variante_do_gtk_segue_o_tema(trocas: dict[str, list[object]]) -> None:
    assert trocas["variante"] == [[False, False], [True, True]], trocas


def test_e_escuro_diz_escuro_para_a_casa_e_claro_para_o_tema_claro() -> None:
    assert tema.e_escuro({}, CASA)
    assert not tema.e_escuro(tema.tokens_da_folha(CLARO), CASA)
    # o tema que não diz o fundo fica com o da casa
    assert tema.e_escuro({"--fg": "#1c1e29"}, CASA)


def test_a_barra_pinta_as_cores_do_tema_so_com_tema() -> None:
    assert janela.css_da_cor_da_barra("") == ""
    css = janela.css_da_cor_da_barra(CLARO)
    assert "headerbar { background: #ffffff; color: #1c1e29; }" in css
    assert "button { color: #1c1e29; }" in css


def test_o_registro_que_muda_troca_o_tema_so_quando_a_folha_muda(
        monkeypatch: pytest.MonkeyPatch) -> None:
    trocadas: list[str] = []
    quem = SimpleNamespace(ponte=SimpleNamespace(tema_de_cores=""),
                           trocar_o_tema=trocadas.append)
    monkeypatch.setattr(janela, "folha_do_tema", lambda: "")
    janela.JanelaDaAba._o_registro_das_extensoes_mudou(quem)  # type: ignore[arg-type]
    monkeypatch.setattr(janela, "folha_do_tema", lambda: CLARO)
    janela.JanelaDaAba._o_registro_das_extensoes_mudou(quem)  # type: ignore[arg-type]
    assert trocadas == [CLARO]


_SONDA_DO_PAR = r"""
import json, pathlib, sys
from hefesto_dualsense4unix.utils.tela_de_mentira import garantir_tela_de_mentira
garantir_tela_de_mentira(anunciar=False)
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from hefesto_dualsense4unix.interface.janela import pedir_a_variante

CLARO = sys.argv[1]
ajustes = Gtk.Settings.get_default()
ajustes.set_property("gtk-theme-name", "casa-de-mentira-dark")

def fundo_da_lista():
    janela = Gtk.OffscreenWindow()
    janela.add(Gtk.TreeView())
    janela.set_default_size(40, 40)
    janela.show_all()
    while Gtk.events_pending():
        Gtk.main_iteration()
    foto = janela.get_pixbuf()
    i = 20 * foto.get_rowstride() + 20 * foto.get_n_channels()
    cor = "#%02x%02x%02x" % tuple(foto.get_pixels()[i:i + 3])
    janela.destroy()
    return cor

saida = []
for folha in (CLARO, "", CLARO):
    pedir_a_variante(folha)
    saida.append([ajustes.get_property("gtk-theme-name"), fundo_da_lista()])
print(json.dumps(saida))
"""


def test_o_tema_claro_troca_o_tema_da_sessao_que_so_existe_escuro(tmp_path: pathlib.Path) -> None:
    """O COSMIC grava na sessão o nome do tema escuro (`adw-gtk3-dark`), e nele o pedido da
    variante clara não muda nada: a lista do popup do `<select>` saía escura no meio da tela clara.
    O tema claro troca o tema pelo par claro dele, e a casa escura volta ao da sessão.
    A prova da D-2110-O-TEMA-CLARO-TROCA-O-TEMA-GTK-PELO-PAR-CLARO.

    MORDIDA (executada em 21/10/2026): com `o_par_claro` devolvendo vazio, a lista do tema claro
    sai `#1e1e1e` e reprova."""
    for nome, fundo in (("casa-de-mentira", "#ffffff"), ("casa-de-mentira-dark", "#1e1e1e")):
        pasta = tmp_path / "themes" / nome / "gtk-3.0"
        pasta.mkdir(parents=True)
        (pasta / "gtk.css").write_text(f"treeview.view {{ background-color: {fundo}; }}\n",
                                       encoding="utf-8")
    ambiente = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", XDG_DATA_HOME=str(tmp_path))
    filho = subprocess.run([sys.executable, "-c", _SONDA_DO_PAR, CLARO], env=ambiente,
                           capture_output=True, text=True, timeout=120)
    assert filho.returncode == 0, filho.stderr[-600:]
    lido = json.loads(filho.stdout.strip().splitlines()[-1])
    assert lido == [["casa-de-mentira", "#ffffff"], ["casa-de-mentira-dark", "#1e1e1e"],
                    ["casa-de-mentira", "#ffffff"]], lido


@pytest.mark.parametrize(("nome", "par"), [
    ("adw-gtk3", ""), ("Adwaita-dark", "Adwaita"), ("um-tema-que-nao-existe-dark", "")])
def test_o_par_claro_so_existe_quando_o_claro_existe(nome: str, par: str) -> None:
    assert janela.o_par_claro(nome) == par
