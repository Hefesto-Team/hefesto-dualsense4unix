#!/usr/bin/env python3
"""Abre a interface nova COM identidade — a logo na dock, o nome na barra.

Pedido dela, 29/08/2026: *"o nosso lançador.sh precisa ter a logo do app na
dock"*.

POR QUE ESTE ARQUIVO EXISTE, EM VEZ DE DUAS LINHAS NO PILOTO
------------------------------------------------------------
O piloto (``src/hefesto_dualsense4unix/interface/controles_vivos.py``) está sendo editado
por outra leva agora, e mora em ``layout/``, que é ``.gitignore`` e não
viaja em worktree. Este envoltório resolve os dois problemas de uma vez: a
identidade é versionada aqui, e o piloto é carregado sem uma linha de mudança.

O QUE FALTAVA, MEDIDO
---------------------
``controles_vivos.py:554`` cria ``Gtk.Window(title="Hefesto — Controles")`` sem
``prgname``, sem ``program_class`` e sem ícone. Medido em Xvfb lendo do
servidor X com ``xprop``, a janela publicava::

    WM_CLASS = ("controles_vivos.py", "Controles_vivos.py")

O cosmic-comp publica o SEGUNDO campo como ``app_id``
(``cosmic-comp/src/shell/element/surface.rs:237`` →
``smithay/src/xwayland/xwm/surface.rs:1083``). ``Controles_vivos.py`` não casa
``.desktop`` nenhum: dock com ícone genérico e nome de script.

AS TRÊS LINHAS QUE CURAM, e por que são de PROCESSO e não de janela
-------------------------------------------------------------------
``Gdk.set_program_class`` conserta TODA janela do processo, inclusive as que o
piloto ainda não abriu — enquanto ``Gtk.Window.set_wmclass`` é por janela, é
depreciado, e obrigaria a editar o piloto a cada janela nova. Medido em 29/08,
Xvfb + ``xprop``: sem ela a janela filha sai ``"Medir.py"``; com ela sai
``"Hefesto-Dualsense4Unix"`` — o nome único, desde 01/09/2026.

O ÍCONE TEM DOIS CAMINHOS, e o segundo é o que funciona SEM INSTALAR
---------------------------------------------------------------------
``set_default_icon_name`` só resolve se o ícone estiver no tema ``hicolor`` —
isto é, depois do ``install.sh``. Antes disso o nome não resolve e a janela
fica sem ícone nenhum. Por isso aqui se PERGUNTA ao tema
(``Gtk.IconTheme.has_icon``) e, se ele não tiver, carrega o PNG do disco, que
vira ``_NET_WM_ICON`` na janela e não depende de instalação alguma. Ela pode
clicar o ``interface`` num repositório recém-clonado e já ver a logo.

OS BOTÕES DA JANELA SAEM À ESQUERDA, E A CULPA NÃO É DO CÓDIGO (02/09/2026)
---------------------------------------------------------------------------
Ela fotografou fechar/maximizar/minimizar **à esquerda e fora de ordem**,
diferentes de toda outra janela da sessão dela. O código está certo: a
``JanelaDaAba`` já põe uma ``Gtk.HeaderBar`` e **não** chama
``set_decoration_layout``, logo herda o do ambiente. Medido no GTK vivo, sem
abrir janela nenhuma::

    Gtk.Settings.get_default().get_property("gtk-decoration-layout")
    → 'close,maximize,minimize:'

O que vem ANTES dos dois-pontos vai para a ESQUERDA, e a ordem é literalmente
essa. É o sintoma inteiro, e ele vale para **todo** aplicativo GTK desta
sessão. A configuração está em dois lugares dela, dizendo o mesmo::

    ~/.config/gtk-3.0/settings.ini   gtk-decoration-layout=close,maximize,minimize:
    gsettings get org.gnome.desktop.wm.preferences button-layout
                                     'close,maximize,minimize:'

As janelas nativas do COSMIC não leem essa chave — o toolkit delas é outro —,
e é por isso que só as GTK destoam.

**NÃO SE CONSERTA AQUI.** Um aplicativo que chamasse ``set_decoration_layout``
passaria a ignorar a escolha global dela, e a próxima pessoa procuraria a causa
no lugar errado. O conserto é de UMA LINHA, na máquina dela, e é decisão dela
qual lado quer: ``:minimize,maximize,close`` põe os três à direita, na ordem
usual do COSMIC.

A INTERFACE É UM VISOR
-----------------------
Ela lê ``daemon.state_full`` do daemon que estiver no ar para mostrar a mesa
real. Este envoltório não mexe em socket, nem em config, nem em ambiente: ele
veste a identidade da JANELA e sai da frente.
"""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

# Este lançador de DESENVOLVIMENTO roda o piloto no PRÓPRIO processo (`runpy`),
# então a janela dele é uma janela de verdade — e não nasce na tela dela
# (TELA-DELA-02). Quem quer VER a interface declara `HEFESTO_NA_TELA=1`; o
# produto que ela usa é o lançador instalado, e não passa por aqui.
import pathlib as _pathlib

_RAIZ_TELA = str(_pathlib.Path(__file__).resolve().parents[1] / "src")
if _RAIZ_TELA not in sys.path:
    sys.path.insert(0, _RAIZ_TELA)
from hefesto_dualsense4unix.utils.tela_de_mentira import (
    garantir_tela_de_mentira,
)

garantir_tela_de_mentira()

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent

#: O PILOTO DAS DEZ ABAS VEM PRIMEIRO — 01/09/2026. Até aqui o lançador abria o
#: `controles_vivos.py`, que é o piloto de UMA aba: a Controles ficava viva e as
#: outras nove eram o mockup ESTÁTICO, sem um dado do daemon. Clicar na tira
#: levava a uma tela bonita e morta.
#:
#: `hefesto_vivo.py` é uma janela com as dez, a navegação entre elas funcionando
#: e a pintura por página — 122 valores escritos por travessia, medidos com o
#: controle dela no cabo e os 33 perfis no disco.
#:
#: O `controles_vivos.py` FICA como segunda tentativa, e não é nostalgia: se
#: esta cópia da árvore estiver incompleta, abrir a aba Controles viva é melhor
#: que não abrir nada. A ordem é a que importa.
#:
#: TUDO SAI DESTA ÁRVORE (`RAIZ`), e é ordem dela: *"tudo tem que apontar pro
#: nosso lancher html e tudo tem que apontar pros arquivos na nossa pasta"*.
#: Havia um segundo caminho apontando para uma árvore vizinha, e é assim que a
#: interface abre a versão de anteontem sem ninguém perceber.
CANDIDATOS_DO_PILOTO = (
    RAIZ / "src" / "hefesto_dualsense4unix" / "interface" / "hefesto_vivo.py",
    RAIZ / "src" / "hefesto_dualsense4unix" / "interface" / "controles_vivos.py",
)
#: O PNG que vira `_NET_WM_ICON` quando o tema ainda não conhece o nome.
CANDIDATOS_DO_ICONE = (
    RAIZ / "assets" / "appimage" / "Hefesto-Dualsense4Unix.png",
)


def achar_o_piloto() -> Path | None:
    """O primeiro piloto que existir, na ordem dos candidatos, ou `None`."""
    return next((c for c in CANDIDATOS_DO_PILOTO if c.is_file()), None)


def achar_o_icone() -> Path | None:
    """O primeiro PNG de logo de dev que existir, ou `None`."""
    return next((c for c in CANDIDATOS_DO_ICONE if c.is_file()), None)


def vestir_a_identidade(casa: object) -> list[str]:
    """Põe nome, classe e ícone no PROCESSO, antes da primeira janela.

    Devolve a lista do que conseguiu fazer, para o lançador imprimir — sem
    isso, um ícone que não sobe some sem uma linha de aviso, que é justamente
    o defeito desta casa ("ausência de notícia é lida como sucesso").
    """
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
    from gi.repository import Gdk, GLib, Gtk

    feito: list[str] = []
    GLib.set_prgname(casa.wm_instance)  # type: ignore[attr-defined]
    GLib.set_application_name(casa.nome_longo)  # type: ignore[attr-defined]
    Gdk.set_program_class(casa.wm_class)  # type: ignore[attr-defined]
    feito.append(f"WM_CLASS = {casa.wm_instance!r}, {casa.wm_class!r}")  # type: ignore[attr-defined]

    tema = Gtk.IconTheme.get_default()
    nome_do_icone = casa.icone  # type: ignore[attr-defined]
    if tema is not None and tema.has_icon(nome_do_icone):
        Gtk.Window.set_default_icon_name(nome_do_icone)
        feito.append(f"ícone pelo tema ({nome_do_icone})")
    else:
        arquivo = achar_o_icone()
        if arquivo is not None:
            Gtk.Window.set_default_icon_from_file(str(arquivo))
            feito.append(f"ícone pelo arquivo ({arquivo.name}) — sem install")
        else:
            feito.append(
                f"SEM ÍCONE: o tema não tem {nome_do_icone!r} e o PNG não está"
                " no disco (rode scripts/gerar_icones.sh)"
            )
    return feito


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)

    piloto = achar_o_piloto()
    if piloto is None:
        print("não achei o piloto (src/hefesto_dualsense4unix/interface/controles_vivos.py)",
              file=sys.stderr)
        for c in CANDIDATOS_DO_PILOTO:
            print(f"  procurei em: {c}", file=sys.stderr)
        return 1

    # O produto tem de estar importável para a identidade sair de um dono só.
    # Numa árvore sem `pip install -e`, `src/` entra no path à mão.
    src = RAIZ / "src"
    if src.is_dir() and str(src) not in sys.path:
        sys.path.insert(0, str(src))
    from hefesto_dualsense4unix.utils import identidade

    # A IDENTIDADE VEM DO DONO DELA, nunca de um literal aqui: um nome digitado
    # neste arquivo põe no WM_CLASS algo que o `.desktop` não declara, e a dock
    # não acha o ícone quando os dois divergem.
    for linha in vestir_a_identidade(identidade.atual()):
        print(f"  {linha}")
    print()

    # `run_name="__main__"` para o piloto executar o próprio bloco de entrada.
    # `sys.argv[0]` passa a ser o piloto: é o que ele espera ver.
    sys.argv = [str(piloto), *args]
    runpy.run_path(str(piloto), run_name="__main__")
    return 0


if __name__ == "__main__":
    sys.exit(main())
