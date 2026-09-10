"""A folha lê o tema que o sistema PINTA, não o sinalizador que ninguém liga.

O DEFEITO, medido em 10/09/2026 com ela na bancada e as duas folhas na tela:
*"fora que nao deu pra ler nada nos botoes"*.  # noqa-acento: citação literal dela

As três folhas de ensaio decidiam claro-ou-escuro por
``gtk-application-prefer-dark-theme``. Na máquina dela esse sinalizador é
**False** e o tema é **`adw-gtk3-dark`** — escuro. As folhas pintavam a janela de
CLARO e o GTK seguia pintando ``button`` e ``entry`` pelo tema ESCURO, com a
letra BRANCA. Branco sobre claro é o que ela não conseguiu ler — e o rótulo do
botão era justamente o que dizia o que fazer.

``prefer-dark`` é um PEDIDO do aplicativo ao tema, não uma descrição do tema. O
produto o liga por conta própria (``app/theme.py``) e por isso nunca viu este
defeito; um instrumento que não o liga lê ``False`` num desktop escuro.

ESTA RÉGUA MORDE EM TRÊS LUGARES, e os três já erraram:

1. a detecção não pode depender só do sinalizador — com ele em False e um tema
   escuro, a resposta ainda tem de ser «escuro»;
2. o CSS tem de pintar ``button``, ``entry`` e ``combobox``. Pintar só
   ``window``/``frame``/``scrolledwindow`` é o que deixou o rótulo sumir dentro
   do próprio botão;
3. as três folhas têm de usar o DONO. Uma cura em uma folha só deixaria as
   outras duas com o defeito — e a que ela usou de manhã é a terceira.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
ENSAIOS = RAIZ / "scripts" / "ensaios"
if str(ENSAIOS) not in sys.path:
    sys.path.insert(0, str(ENSAIOS))

#: AS TRÊS FOLHAS DA BANCADA DELA. A do som e a do microfone nasceram em 09/09;
#: a dos ensaios é a que ela usou na manhã de 09/09, e é por ela que a cura tem
#: de passar também.
FOLHAS = (
    "a_folha_do_som_por_controle.py",
    "a_folha_do_microfone_por_controle.py",
    "a_folha_dos_ensaios.py",
)


def test_o_dono_existe_e_e_um_so() -> None:
    """A detecção e o CSS moram em `comum`, e não copiados em cada folha."""
    import comum

    assert callable(comum.o_tema_e_escuro)
    assert callable(comum.pintar_fundo_solido)


def test_a_deteccao_nao_acredita_so_no_sinalizador(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tema escuro + `prefer-dark` False = escuro. É o caso EXATO da máquina dela.

    A MORDIDA: devolver a detecção para `prefer-dark` sozinho faz este teste
    reprovar, que é o defeito de 10/09 voltando.
    """
    import comum

    gi = pytest.importorskip("gi")
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk

    ajustes = Gtk.Settings.get_default()
    if ajustes is None:  # pragma: no cover — sem tela nem Xvfb não há Settings
        pytest.skip("sem Gtk.Settings nesta máquina")

    monkeypatch.setattr(
        type(ajustes), "get_property",
        lambda self, nome: (
            False if nome == "gtk-application-prefer-dark-theme"
            else "adw-gtk3-dark" if nome == "gtk-theme-name"
            else ""
        ),
    )
    assert comum.o_tema_e_escuro() is True, (
        "com o tema `adw-gtk3-dark` e `prefer-dark` False — o caso medido na "
        "máquina dela — a folha tem de se pintar de ESCURO"
    )


def test_o_css_pinta_o_botao_o_campo_e_a_lista(monkeypatch: pytest.MonkeyPatch) -> None:
    """O CSS cobre `button`, `entry` e `combobox` — os três que sumiram.

    A MORDIDA: apagar qualquer um dos três seletores reprova aqui.
    """
    import comum

    pytest.importorskip("gi")
    css_visto: list[str] = []

    class _ProvedorDeMentira:
        def load_from_data(self, dados: bytes) -> None:
            css_visto.append(dados.decode("utf-8"))

    class _JanelaDeMentira:
        def set_app_paintable(self, _v: bool) -> None:
            return None

    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
    from gi.repository import Gdk, Gtk

    monkeypatch.setattr(Gtk, "CssProvider", _ProvedorDeMentira)
    monkeypatch.setattr(Gtk.StyleContext, "add_provider_for_screen",
                        staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(Gdk.Screen, "get_default", staticmethod(lambda: None))

    comum.pintar_fundo_solido(_JanelaDeMentira())
    assert css_visto, "o CSS não foi carregado"
    css = css_visto[0]

    # OS SELETORES, LIDOS — e não a substring procurada no texto todo. A
    # primeira versão desta régua fazia `"button" in css` e PASSOU com a cura
    # arrancada: a palavra sobrevivia dentro de `combobox button`. É a armadilha
    # que esta casa já nomeia — *régua que casa um token em QUALQUER lugar do
    # texto, em vez do campo que o significa* — e ela pegou a própria régua.
    seletores = set()
    for regra in css.split("}"):
        if "{" in regra:
            seletores.update(s.strip() for s in regra.split("{")[0].split(","))

    for seletor in ("button", "entry", "combobox button"):
        assert seletor in seletores, (
            f"o CSS da folha não pinta `{seletor}` — foi assim que o rótulo do "
            f"botão sumiu dentro do próprio botão em 10/09/2026. "
            f"seletores declarados: {sorted(seletores)}"
        )


@pytest.mark.parametrize("folha", FOLHAS)
def test_toda_folha_usa_o_dono_e_nenhuma_decide_sozinha(folha: str) -> None:
    """Nenhuma folha lê o sinalizador por conta própria.

    A MORDIDA: devolver o bloco antigo a QUALQUER uma das três reprova aqui —
    inclusive à que ninguém abriu hoje.
    """
    fonte = (ENSAIOS / folha).read_text(encoding="utf-8")
    assert "pintar_fundo_solido" in fonte, f"{folha} não usa o dono do fundo"
    assert "gtk-application-prefer-dark-theme" not in fonte, (
        f"{folha} voltou a decidir o tema pelo sinalizador — é o defeito de "
        f"10/09/2026, e ele deixa o rótulo do botão ilegível na máquina dela"
    )
