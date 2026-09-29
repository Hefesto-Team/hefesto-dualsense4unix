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

UMA JANELA POR TELA, E O SEGUNDO CLIQUE A TRAZ PARA A FRENTE (28/09/2026)
--------------------------------------------------------------------------
Até aqui, clicar duas vezes no ícone abria duas janelas: o mecanismo que a
janela GTK antiga usava (``utils/single_instance.acquire_or_bring_to_front``, o
modelo *primeira vence*) ficou sem chamador quando ela saiu, em 06/09. Ele volta
aqui (``tomar_a_vez``): a janela que já está aberta recebe o pedido e vem para a
frente, e o segundo processo sai com ``rc=0`` antes de importar o GTK.

O lock é POR TELA (``nome_da_vez``): a janela que nasce num ``Xvfb`` de
instrumento nunca pede nada à janela da tela dela. E ele só vale quando a
janela vai para uma tela de verdade (``HEFESTO_NA_TELA=1``, sem ``--oculta``):
os instrumentos continuam abrindo quantas janelas escondidas quiserem.

O CACHE DE LOADERS DO GDKPIXBUF SE CONFERE AQUI, ANTES DO GTK
--------------------------------------------------------------
``app/arranque.sanear_loaders_do_gdk_pixbuf`` descarta o
``GDK_PIXBUF_MODULE_FILE`` herdado de um terminal empacotado quando os módulos
dele são de outro confinamento, o caso em que o GTK aborta o processo no
primeiro SVG. O ``run.sh`` faz a versão grossa em shell; a fina é esta, e ela
só serve antes de qualquer import de ``gi.repository``.

A INTERFACE É UM VISOR
-----------------------
Ela lê ``daemon.state_full`` do daemon que estiver no ar para mostrar a mesa
real. Este envoltório não mexe em socket, nem em config, nem em ambiente: ele
veste a identidade da JANELA e sai da frente.
"""
from __future__ import annotations

import os
import re
import runpy
import signal
import sys
from pathlib import Path
from typing import Any

# Este lançador roda o piloto no PRÓPRIO processo (`runpy`), então a janela dele
# é uma janela de verdade — e não nasce na tela dela (TELA-DELA-02). Quem quer
# VER a interface declara `HEFESTO_NA_TELA=1`.
#
# FATO ERRADO, SUBSTITUÍDO — 06/09/2026. Esta linha dizia *"o produto que ela
# usa é o lançador instalado, e não passa por aqui"*, e foi com essa premissa
# que a guarda entrou aqui em 04/09. O `.desktop` instalado aponta o `Exec=`
# para `run.sh --gui`, que chama ESTE arquivo: o atalho dela PASSA por aqui, e
# passou desviado por dois dias — ela clicou, o WebKit pintou as dez abas num
# `Xvfb` e a tela dela não recebeu nada.
#
# Quem declara o escape é o que ela clica: o `Exec=` do `.desktop` e o
# lançador de `~/.local/bin`, os dois escritos pelo `install.sh` com
# `HEFESTO_NA_TELA=1`. O `run.sh` não o declara, e a guarda FICA aqui: os
# instrumentos que chamam este script, ou o `run.sh --gui`, continuam sem tela.
# Há régua: `test_o_lancador_dela_nasce_na_tela_dela.py`.
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


def nome_da_vez() -> str:
    """O nome do lock de instância única: um por TELA.

    A tela é a do Wayland quando há uma (é nela que o GTK abre, salvo o opt-in
    do XWayland, que continua na mesma sessão), senão a do X. Um ``Xvfb`` de
    instrumento tem ``DISPLAY`` próprio e nenhum ``WAYLAND_DISPLAY``: o lock dele
    é outro, e ele nunca manda a janela dela para a frente.
    """
    tela = os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY") or "sem-tela"
    return "gui-" + re.sub(r"[^A-Za-z0-9_.-]", "_", tela)


def a_janela_vai_para_a_tela(args: list[str]) -> bool:
    """A janela deste processo nasce numa tela de verdade?

    ``HEFESTO_NA_TELA=1`` é o que o atalho e o lançador de ``~/.local/bin``
    declaram; sem ele, a guarda TELA-DELA-02 já desviou a janela para um
    ``Xvfb`` próprio. ``--oculta`` é o ``Gtk.OffscreenWindow`` das réguas, que
    não aparece em tela nenhuma. Nos dois casos não há o que trazer à frente.
    """
    return os.environ.get("HEFESTO_NA_TELA") == "1" and "--oculta" not in args


def tomar_a_vez(args: list[str]) -> str | None:
    """Toma a vez de ser A janela desta tela, no modelo *primeira vence*.

    Devolve o nome do lock quando este processo é a janela (e aí quem chama
    arma ``armar_a_volta_a_frente`` depois do GTK), ``""`` quando não há lock a
    tomar (instrumento, janela oculta), e ``None`` quando uma janela já aberta
    recebeu o pedido e veio para a frente: quem chama sai com ``rc=0``.

    O TRATADOR DO SINAL ENTRA ANTES DO LOCK, e é de propósito: a ação padrão do
    ``SIGUSR1`` é MATAR. Do instante em que o pid file traz este PID até o
    GLib armar o tratador de verdade, um segundo clique derrubaria a janela que
    está nascendo. Um tratador vazio de Python é trocado na execução de um
    filho (o WebKit), o que um ``SIG_IGN`` não seria.
    """
    if not a_janela_vai_para_a_tela(args):
        return ""
    from hefesto_dualsense4unix.utils import single_instance as si

    nome = nome_da_vez()
    signal.signal(si.SINAL_DE_VIR_A_FRENTE, lambda *_: None)
    pid = si.acquire_or_bring_to_front(nome, lambda anterior: si.pedir_a_frente(nome, anterior))
    return nome if pid is not None else None


def janelas_de_frente(janelas: list[Any]) -> list[Any]:
    """As janelas que um pedido de vir à frente apresenta.

    As de primeiro nível, visíveis e sem dona: a janela das abas. Um diálogo
    (``transient_for``) vem junto com a dona, e uma ``Gtk.OffscreenWindow`` não
    está em tela nenhuma.
    """
    from gi.repository import Gtk

    return [
        j for j in janelas
        if isinstance(j, Gtk.Window)
        and not isinstance(j, Gtk.OffscreenWindow)
        and j.get_window_type() == Gtk.WindowType.TOPLEVEL
        and j.get_visible()
        and j.get_transient_for() is None
    ]


def vir_a_frente(nome: str) -> bool:
    """O tratador do pedido: apresenta a janela, com o token de quem pediu."""
    from gi.repository import Gtk

    from hefesto_dualsense4unix.utils import single_instance as si

    token = si.ler_o_pedido_de_ativacao(nome)
    janelas = janelas_de_frente(Gtk.Window.list_toplevels())
    for janela in janelas:
        if token:
            janela.set_startup_id(token)
        janela.present()
    print(f"  a janela veio para a frente ({len(janelas)} apresentada(s)"
          f"{', com o token de quem pediu' if token else ''})")
    return True  # o GLib mantém o tratador para o próximo pedido


def armar_a_volta_a_frente(nome: str) -> None:
    """Troca o tratador vazio pelo do laço do GLib, que roda na thread da janela."""
    from gi.repository import GLib

    from hefesto_dualsense4unix.utils import single_instance as si

    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, si.SINAL_DE_VIR_A_FRENTE, vir_a_frente, nome)


#: O TETO DO DIÁRIO DA JANELA, em bytes. 1 MiB dá ~10 mil linhas de recado —
#: mais do que uma sessão dela produz, e pouco o bastante para nunca aparecer
#: numa conta de disco. Passou disso, o arquivo vira `.1` e recomeça: UMA volta
#: só, porque o que interessa é a sessão de agora e a anterior.
TETO_DO_DIARIO = 1 << 20


def diario_da_janela() -> object:
    """O arquivo onde a janela dela deixa rastro, ou ``None`` se há terminal.

    **A-TELA-SAMBA-01, 06/09/2026, e é o Passo 5 dela.** Quando ela abre a
    interface pelo atalho da dock, o ``stdout`` e o ``stderr`` do processo vão
    para lugar nenhum — o ``.desktop`` não tem terminal atrás. Tudo o que o
    piloto diz some: o ``[tique lento]``, o ``[daemon mudo]``, o ``a pintura
    falhou``, o ``ERRO DE CARGA``. **Nenhum dos quatro sintomas de "a interface
    tá sambando" tinha uma linha em lugar nenhum**, e o diagnóstico saiu de
    foto — que é o instrumento que menos enxerga este defeito.

    O DESVIO SÓ ACONTECE SEM TERMINAL, e é a metade que impede o remédio de
    virar doença: quem roda o piloto à mão, numa régua ou num ensaio, continua
    vendo tudo na tela — desviar ali esconderia a saída de quem está olhando
    para ela. ``isatty()`` é a pergunta certa, e é a mesma que o ``rich`` e o
    ``pytest`` fazem.

    O LUGAR É O MESMO ``XDG_STATE_HOME`` que a suíte já desvia para um lar de
    mentira (``tests/conftest.py``), então uma régua que chame esta função não
    escreve no ``~/.local/state`` DELA.
    """
    fluxo = sys.stderr
    try:
        if fluxo is not None and hasattr(fluxo, "isatty") and fluxo.isatty():
            return None
    except (ValueError, OSError):
        # Um fluxo já fechado responde levantando. Sem terminal, então.
        pass

    from hefesto_dualsense4unix.utils.xdg_paths import state_dir

    casa = state_dir(ensure=True)
    diario = casa / "interface.log"
    try:
        if diario.exists() and diario.stat().st_size > TETO_DO_DIARIO:
            diario.replace(casa / "interface.log.1")
        return diario.open("a", buffering=1, encoding="utf-8", errors="replace")
    except OSError as erro:
        # DISCO CHEIO NÃO IMPEDE A JANELA DE ABRIR. O diário é conforto de
        # diagnóstico; a interface é o produto.
        print(f"  sem diário da janela ({erro})", file=sys.stderr)
        return None


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)

    # ANTES DE QUALQUER `gi.repository`: depois dele o GdkPixbuf já leu o cache
    # de loaders, e a correção chegaria tarde.
    from hefesto_dualsense4unix.app.arranque import sanear_loaders_do_gdk_pixbuf

    loaders_saneados = sanear_loaders_do_gdk_pixbuf()

    diario = diario_da_janela()
    if diario is not None:
        import datetime

        # AS DUAS SAÍDAS VÃO PARA O MESMO ARQUIVO, e em ordem: o piloto imprime
        # o relato no `stdout` e os recados no `stderr`, e ler os dois em
        # arquivos separados obrigaria a próxima pessoa a costurar dois
        # relógios. `sys.stderr` também é trocado para que o `print(...,
        # file=sys.stderr)` de dentro do piloto pouse aqui.
        sys.stdout = diario  # type: ignore[assignment]
        sys.stderr = diario  # type: ignore[assignment]
        print(f"\n===== a janela abriu em "
              f"{datetime.datetime.now().isoformat(timespec='seconds')} =====")
    if loaders_saneados:
        print("  loaders do GdkPixbuf: o cache herdado não serve a este processo;"
              " vale o do sistema")

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

    # UMA JANELA POR TELA: se já há uma aberta, ela vem para a frente e este
    # processo sai aqui, sem ter importado o GTK.
    vez = tomar_a_vez(args)
    if vez is None:
        print("  já havia uma janela aberta nesta tela: ela veio para a frente")
        return 0

    # A IDENTIDADE VEM DO DONO DELA, nunca de um literal aqui: um nome digitado
    # neste arquivo põe no WM_CLASS algo que o `.desktop` não declara, e a dock
    # não acha o ícone quando os dois divergem.
    for linha in vestir_a_identidade(identidade.atual()):
        print(f"  {linha}")
    print()
    if vez:
        armar_a_volta_a_frente(vez)

    # `run_name="__main__"` para o piloto executar o próprio bloco de entrada.
    # `sys.argv[0]` passa a ser o piloto: é o que ele espera ver.
    sys.argv = [str(piloto), *args]
    runpy.run_path(str(piloto), run_name="__main__")
    return 0


if __name__ == "__main__":
    sys.exit(main())
