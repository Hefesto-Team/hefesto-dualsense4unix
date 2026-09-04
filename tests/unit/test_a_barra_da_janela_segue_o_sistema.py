#!/usr/bin/env python3
"""OS BOTÕES DA JANELA DO LADO DO SISTEMA — queixa 2 dela, e a premissa que caiu.

> **Ela, 04/09/2026:** *"a barra de navegação fechar, maximizar diminuir não é a
> mesma do sistema"*. Era a única das quinze queixas que tinha ficado aberta.

**DECIDIDA no mesmo dia — opção ``1-a``, só a janela do Hefesto.** Nenhuma linha
na configuração dela: o produto pede ao GTK, dentro do próprio processo, ao lado
de onde ele já pede o tema.

A PREMISSA DA SPRINT CAIU NA MEDIÇÃO, e esta régua existe em parte para que ela
não volte. A ``BARRA-DA-JANELA-01`` mandava *"ler
``org.gnome.desktop.wm.preferences button-layout``; se a sessão não disser, cair
em ``:minimize,maximize,close``"* — supondo que só o ``settings.ini`` dela
carregasse o valor errado. Medido na máquina dela em 04/09/2026:

    $ cat ~/.config/gtk-3.0/settings.ini
    gtk-decoration-layout=close,maximize,minimize:
    $ gsettings get org.gnome.desktop.wm.preferences button-layout
    'close,maximize,minimize:'

**As duas fontes dizem ESQUERDA**, que é exatamente a queixa. Uma cura que
"pergunta à sessão" devolveria a resposta que produziu o defeito, passaria no
teste com um dublê mudo e deixaria a janela dela igual — o verde sobre defeito
vivo que esta casa pagou quatro vezes numa madrugada. **Quando o instrumento e o
aparelho discordam, o aparelho ganha.**

Quem decide o lado no COSMIC é o compositor, e ele não tem chave: ``~/.config/
cosmic/`` inteiro não guarda uma linha sobre lado de botão. Por isso o produto
usa a constante do compositor, **e só sob COSMIC** — fora dele o GTK já está
certo e mexer seria o aplicativo passando por cima de uma escolha que ninguém
contestou.

POR QUE A RÉGUA É A PROPRIEDADE E NÃO O PIXEL DO BOTÃO. Medido nesta máquina em
04/09/2026, montando uma ``Gtk.HeaderBar`` com ``set_show_close_button(True)``
dentro de uma ``Gtk.OffscreenWindow``:

===================================  ==================================
como                                 quantos botões nascem
===================================  ==================================
``set_titlebar(barra)``              zero — e a barra aloca **1 px**
``pack_start`` num ``Gtk.Box``       zero — a barra aloca 600 px
===================================  ==================================

Os botões de decoração só existem quando a barra É a titlebar de uma janela
decorada, e offscreen não há gerenciador de janelas — é a armadilha que o
``COMO-OLHAR-A-TELA`` já lista. **Medir o pixel exigiria pôr uma janela na tela
dela, e ela tem UMA tela.** ``gtk-decoration-layout`` é o canal por onde o GTK
decide, e é onde a cura escreve: medir ali é medir o que o produto faz.

A MORDIDA: comente a chamada de ``adotar_a_barra_da_sessao`` no
``gui/ponte_da_tela.JanelaDaAba.__init__`` — ou o ``set_property`` dentro dela —
e ``test_a_barra_da_janela_fica_do_lado_do_sistema`` reprova mostrando o
``close,maximize,minimize:`` que a sessão dela manda.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

#: O QUE A SESSÃO DELA DIZ, e é o valor que a cura NÃO pode seguir. Escrito aqui
#: à mão de propósito: importar a leitura dos dois lados faria os dois errarem
#: juntos em silêncio.
O_QUE_A_SESSAO_DELA_DIZ = "close,maximize,minimize:"

#: O LADO DO COSMIC — os três botões DEPOIS dos dois-pontos, isto é, à direita.
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
    # O `Gtk.Settings` É GLOBAL DO PROCESSO, e qualquer vizinho que abra uma
    # janela desta casa já o terá escrito. Sem guardar e devolver, esta régua
    # mediria o rastro do vizinho — e a mordida deixaria de morder, porque a
    # propriedade já estaria do lado certo antes de a cura correr.
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


# --------------------------------------------------------------------------
# 1. a cura, pelo caminho do produto
# --------------------------------------------------------------------------
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
    """A cura corre onde a JANELA nasce, e não só quando alguém a chama.

    É a diferença entre a cura existir e a cura estar LIGADA — o padrão que esta
    casa chama de *a casa sabe e o produto não faz*, e que já custou uma frase
    de recusa indo para o terminal em vez da tela.
    """
    fonte = (RAIZ / "src/hefesto_dualsense4unix/gui/ponte_da_tela.py").read_text(
        encoding="utf-8")
    assert "tema.adotar_a_barra_da_sessao()" in fonte, (
        "a `JanelaDaAba` não chama a cura da barra. Uma cura que ninguém liga "
        "é a dívida que esta casa persegue com um portão próprio.")


# --------------------------------------------------------------------------
# 2. o que ela NÃO faz — e é metade da decisão dela
# --------------------------------------------------------------------------
def test_fora_do_cosmic_o_produto_nao_mexe(gtk, sessao) -> None:
    """Em GNOME/KDE o GTK já põe os botões onde o sistema os põe.

    Mexer ali seria o aplicativo passando por cima de uma escolha que ninguém
    contestou — e a decisão dela é ``1-a``, *só a janela do Hefesto*, num
    ambiente em que ela está errada.
    """
    from hefesto_dualsense4unix.app import theme

    sessao("GNOME")
    gtk.set_property("gtk-decoration-layout", O_QUE_A_SESSAO_DELA_DIZ)
    assert theme.adotar_a_barra_da_sessao() == ""
    assert gtk.get_property("gtk-decoration-layout") == O_QUE_A_SESSAO_DELA_DIZ, (
        "o produto reescreveu a decoração numa sessão que não é COSMIC")


def test_nada_e_escrito_na_configuracao_dela(gtk, sessao) -> None:
    """A decisão ``1-a`` em uma linha: **nenhuma** linha no disco dela.

    A cura inteira vive em `Gtk.Settings` — memória deste processo. Um `open(...,
    "w")` sobre o `settings.ini` mudaria programas que não são este, e é
    exatamente o que ela recusou.
    """
    import ast

    fonte = (RAIZ / "src/hefesto_dualsense4unix/app/theme.py").read_text(
        encoding="utf-8")
    arvore = ast.parse(fonte)
    # POR AST, E NÃO POR `in` NA LINHA. A primeira versão desta régua procurava
    # `"settings.ini"` no TEXTO do arquivo e reprovava a própria MEDIÇÃO — o
    # docstring que explica por que a cura não lê aquele arquivo cita o nome
    # dele. É a família de defeito que o `validar-palavra-de-tela` já nomeia:
    # *régua que casa um token em qualquer lugar do texto, em vez do campo que o
    # significa*. Docstring é prosa; o que se cobra é CÓDIGO.
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
            corpo = corpo[1:]  # o docstring sai: ele explica, não executa
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
    """Já está do lado certo? Não há o que fazer — e a função diz isso.

    Cada janela desta casa chama a cura ao nascer. Reescrever a mesma
    propriedade a cada janela não quebra nada, mas o retorno vazio é o que
    separa *"eu adotei agora"* de *"já estava"* no log e no relato.
    """
    from hefesto_dualsense4unix.app import theme

    sessao("COSMIC")
    gtk.set_property("gtk-decoration-layout", A_DIREITA)
    assert theme.adotar_a_barra_da_sessao() == ""
    assert gtk.get_property("gtk-decoration-layout") == A_DIREITA


# --------------------------------------------------------------------------
# 3. a premissa que caiu fica MEDIDA, para ninguém remedir
# --------------------------------------------------------------------------
def test_perguntar_a_sessao_devolve_a_resposta_errada(gtk) -> None:
    """A leitura do dconf continua existindo — e continua sem servir de cura.

    Ela é o que o relato imprime e o que a mordida arranca. Nesta máquina ela
    responde ``close,maximize,minimize:``; noutra pode responder outra coisa, e
    por isso a régua cobra a FORMA, não o valor: se a sessão disser algo, e esse
    algo puser botão à esquerda, seguir a sessão reabriria a queixa.
    """
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
