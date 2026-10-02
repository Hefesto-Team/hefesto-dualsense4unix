#!/usr/bin/env python3
"""OS BOTÕES DA JANELA DO LADO DO SISTEMA — queixa 2 dela, e a premissa que caiu."""
from __future__ import annotations

import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

O_QUE_A_SESSAO_DELA_DIZ = "close,maximize,minimize:"

A_DIREITA = ":minimize,maximize,close"


@pytest.fixture
def gtk():
    """O GTK desta máquina, ou um `skip` honesto. Restaura o que tocar."""
    gi = pytest.importorskip("gi", reason="a GUI precisa do PyGObject do sistema")
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o GTK não abre")
    settings = Gtk.Settings.get_default()
    if settings is None:
        pytest.skip("sem Gtk.Settings — não há onde escrever a decoração")
    guardado = settings.get_property("gtk-decoration-layout")
    yield settings
    settings.set_property("gtk-decoration-layout", guardado)


@pytest.fixture
def sessao(monkeypatch):
    """Diz de que sessão estamos falando, sem depender da máquina que roda."""

    def por(nome: str) -> None:
        for chave in ("XDG_CURRENT_DESKTOP", "XDG_SESSION_DESKTOP",
                      "DESKTOP_SESSION"):
            monkeypatch.delenv(chave, raising=False)
        if nome:
            monkeypatch.setenv("XDG_CURRENT_DESKTOP", nome)

    return por


def test_a_barra_da_janela_fica_do_lado_do_sistema(gtk, sessao) -> None:
    """A queixa dela, fechada: sob COSMIC os três botões vão para a direita."""
    from hefesto_dualsense4unix.app import theme

    sessao("COSMIC")
    gtk.set_property("gtk-decoration-layout", O_QUE_A_SESSAO_DELA_DIZ)
    assert theme.adotar_a_barra_da_sessao() == A_DIREITA
    agora = gtk.get_property("gtk-decoration-layout")
    assert agora == A_DIREITA, (
        f"a janela continuaria com os botões à esquerda ({agora!r}) — que é a "
        f"queixa 2 dela, palavra por palavra: 'a barra de navegação fechar, "
        f"maximizar diminuir não é a mesma do sistema'.")


def test_a_janela_do_produto_ja_nasce_com_a_barra_certa(gtk, sessao) -> None:
    """A cura corre onde a JANELA nasce, e não só quando alguém a chama."""
    fonte = (RAIZ / "src/hefesto_dualsense4unix/gui/ponte_da_tela.py").read_text(
        encoding="utf-8")
    assert "tema.adotar_a_barra_da_sessao()" in fonte, (
        "a `JanelaDaAba` não chama a cura da barra. Uma cura que ninguém liga "
        "é a dívida que esta casa persegue com um portão próprio.")


def test_fora_do_cosmic_o_produto_nao_mexe(gtk, sessao) -> None:
    """Em GNOME/KDE o GTK já põe os botões onde o sistema os põe."""
    from hefesto_dualsense4unix.app import theme

    sessao("GNOME")
    gtk.set_property("gtk-decoration-layout", O_QUE_A_SESSAO_DELA_DIZ)
    assert theme.adotar_a_barra_da_sessao() == ""
    assert gtk.get_property("gtk-decoration-layout") == O_QUE_A_SESSAO_DELA_DIZ, (
        "o produto reescreveu a decoração numa sessão que não é COSMIC")


def test_nada_e_escrito_na_configuracao_dela(gtk, sessao) -> None:
    """A decisão ``1-a`` em uma linha: **nenhuma** linha no disco dela."""
    import ast

    fonte = (RAIZ / "src/hefesto_dualsense4unix/app/theme.py").read_text(
        encoding="utf-8")
    arvore = ast.parse(fonte)
    daqui = {"sessao_e_cosmic", "lado_dos_botoes_na_sessao",
             "barra_que_o_sistema_usa", "adotar_a_barra_da_sessao"}
    achadas = {n.name for n in ast.walk(arvore)
               if isinstance(n, ast.FunctionDef) and n.name in daqui}
    assert achadas == daqui, f"faltam funções da cura da barra: {daqui - achadas}"
    for no in ast.walk(arvore):
        if not (isinstance(no, ast.FunctionDef) and no.name in daqui):
            continue
        corpo = list(no.body)
        if (corpo and isinstance(corpo[0], ast.Expr)
                and isinstance(corpo[0].value, ast.Constant)):
            corpo = corpo[1:]
        for dentro in [d for c in corpo for d in ast.walk(c)]:
            if isinstance(dentro, ast.Constant) and isinstance(dentro.value, str):
                assert "settings.ini" not in dentro.value, (
                    f"{no.name} carrega o caminho do `settings.ini` dela")
            if isinstance(dentro, ast.Call):
                alvo = getattr(dentro.func, "id", None) or getattr(
                    dentro.func, "attr", "")
                assert alvo not in ("open", "write_text", "write_bytes"), (
                    f"{no.name} escreve em arquivo ({alvo}) — a decisão dela é "
                    f"`1-a`, e ela diz com todas as letras: nenhuma linha na "
                    f"configuração dela.")


def test_a_segunda_chamada_nao_reescreve(gtk, sessao) -> None:
    """Já está do lado certo? Não há o que fazer — e a função diz isso."""
    from hefesto_dualsense4unix.app import theme

    sessao("COSMIC")
    gtk.set_property("gtk-decoration-layout", A_DIREITA)
    assert theme.adotar_a_barra_da_sessao() == ""
    assert gtk.get_property("gtk-decoration-layout") == A_DIREITA


def test_perguntar_a_sessao_devolve_a_resposta_errada(gtk) -> None:
    """A leitura do dconf continua existindo — e continua sem servir de cura."""
    from hefesto_dualsense4unix.app import theme

    dito = theme.lado_dos_botoes_na_sessao()
    if not dito:
        pytest.skip("esta máquina não tem o esquema `wm.preferences` instalado")
    antes_dos_dois_pontos = dito.split(":")[0]
    if not antes_dos_dois_pontos:
        pytest.skip(f"nesta máquina a sessão já manda os botões para a direita "
                    f"({dito!r}) — não há divergência a registrar")
    assert theme.barra_que_o_sistema_usa() != dito, (
        f"o produto passou a SEGUIR a sessão, e a sessão diz {dito!r} — botões "
        f"à esquerda. É a queixa 2 dela reaberta pela cura que devia fechá-la.")
