"""A entrada do produto que abre a janela: a identidade veste o processo ANTES de ela nascer.

Pedido, 29/08/2026: *"o nosso lançador.sh precisa ter a logo do app na dock"*. Em 07/10/2026 a
bancada achou a segunda porta: o console script `hefesto-dualsense4unix-gui` ia direto ao piloto, e
a janela da bandeja se anunciava `hefesto-dualsense4unix-gui`, nome que nenhum `.desktop` casa (dock
com a engrenagem). O corpo do antigo envoltório mora aqui, no pacote, porque o wheel não leva
`scripts/`; dele saem dois chamadores e nenhum terceiro: o console script (`entrada`) e o calço
`scripts/abrir_interface.py` (`abrir`), que o `run.sh --gui` continua chamando.

O QUE FALTAVA, MEDIDO
---------------------
O piloto cria a janela sem `prgname`, sem `program_class` e sem ícone. Medido em Xvfb lendo do
servidor X com `xprop`, a janela publicava `WM_CLASS = ("controles_vivos.py",
"Controles_vivos.py")`; o cosmic-comp publica o SEGUNDO campo como `app_id`. Nome de script, dock
com ícone genérico.

AS TRÊS LINHAS QUE CURAM, e por que são de PROCESSO e não de janela
-------------------------------------------------------------------
`Gdk.set_program_class` conserta TODA janela do processo, inclusive as que o piloto ainda não abriu
(`Gtk.Window.set_wmclass` é por janela e depreciado). O `GLib.set_prgname` dá o `app_id` do Wayland.

O ÍCONE TEM DOIS CAMINHOS, e o segundo é o que funciona SEM INSTALAR
---------------------------------------------------------------------
`set_default_icon_name` só resolve se o ícone estiver no tema `hicolor`, isto é, depois do
`install.sh`. Antes disso se carrega o PNG do disco, que vira `_NET_WM_ICON` na janela. Num pacote
sem a árvore o PNG não existe, e o ícone vem do tema que o pacote instala.

OS BOTÕES DA JANELA SAEM À ESQUERDA, E A CULPA NÃO É DO CÓDIGO (02/09/2026)
---------------------------------------------------------------------------
O `gtk-decoration-layout` da sessão dela é `close,maximize,minimize:` (em
`~/.config/gtk-3.0/settings.ini` e no gsettings), e vale para todo aplicativo GTK. **NÃO SE CONSERTA
AQUI**: um aplicativo que chamasse `set_decoration_layout` ignoraria a escolha global dela. O
conserto é de UMA LINHA na máquina do usuário.

UMA JANELA POR TELA, E O SEGUNDO CLIQUE A TRAZ PARA A FRENTE (28/09/2026)
--------------------------------------------------------------------------
Clicar duas vezes no ícone abria duas janelas. O modelo *primeira vence* volta aqui (`tomar_a_vez`):
a janela aberta recebe o pedido pela porta dela (um socket no runtime, NUNCA um sinal: o WebKit toma
o `SIGUSR1`), vem para a frente e responde; o segundo processo sai com `rc=0` antes de importar o
GTK. A janela que não responde não segura o clique. O lock é POR TELA (`nome_da_vez`) e só vale
quando a janela vai para uma tela de verdade (`HEFESTO_NA_TELA=1`, sem `--oculta`).

A GUARDA DA TELA RODA DENTRO DA ENTRADA, NUNCA NO IMPORT
---------------------------------------------------------
`garantir_tela_de_mentira` desvia o GTK para um Xvfb próprio quando `HEFESTO_NA_TELA` não vale `1`.
A entrada do produto (console script) põe o padrão `1` ANTES dela, porque a bandeja que abre o
painel não declara a variável; o calço da árvore (`run.sh`) não põe, e os instrumentos que o chamam
seguem na tela de mentira. Em `abrir.py` nada roda no import.

O CACHE DE LOADERS DO GDKPIXBUF SE CONFERE AQUI, ANTES DO GTK
--------------------------------------------------------------
`app/arranque.sanear_loaders_do_gdk_pixbuf` descarta o `GDK_PIXBUF_MODULE_FILE` herdado de um
terminal empacotado quando os módulos dele são de outro confinamento. Só serve antes de qualquer
`gi.repository`; por isso o piloto, que importa o Gtk no topo, NUNCA é importado aqui no topo: ele
roda por `runpy.run_module`, depois da identidade.

A INTERFACE É UM VISOR
-----------------------
Ela lê `daemon.state_full` do daemon que estiver no ar. Esta entrada não mexe em socket, nem em
config: veste a identidade da JANELA e sai da frente.
"""
from __future__ import annotations

import importlib.util
import os
import re
import runpy
import sys
from pathlib import Path
from typing import Any, TextIO

from hefesto_dualsense4unix.utils.identidade import Identidade
from hefesto_dualsense4unix.utils.tela_de_mentira import garantir_tela_de_mentira

RAIZ = Path(__file__).resolve().parents[3]

CANDIDATOS_DO_PILOTO = (
    "hefesto_dualsense4unix.interface.hefesto_vivo",
    "hefesto_dualsense4unix.interface.controles_vivos",
)
CANDIDATOS_DO_ICONE = (
    RAIZ / "assets" / "appimage" / "Hefesto-Dualsense4Unix.png",
)


def achar_o_piloto() -> str | None:
    """O nome do primeiro módulo de piloto que existir, na ordem dos candidatos, ou `None`."""
    for nome in CANDIDATOS_DO_PILOTO:
        try:
            if importlib.util.find_spec(nome) is not None:
                return nome
        except (ImportError, ValueError):
            continue
    return None


def achar_o_icone() -> Path | None:
    """O primeiro PNG de logo de dev que existir, ou `None`."""
    return next((c for c in CANDIDATOS_DO_ICONE if c.is_file()), None)


def vestir_a_identidade(casa: Identidade) -> list[str]:
    """Põe nome, classe e ícone no PROCESSO, antes da primeira janela."""
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
    from gi.repository import Gdk, GLib, Gtk

    feito: list[str] = []
    GLib.set_prgname(casa.wm_instance)
    GLib.set_application_name(casa.nome_longo)
    Gdk.set_program_class(casa.wm_class)
    feito.append(f"WM_CLASS = {casa.wm_instance!r}, {casa.wm_class!r}")

    tema = Gtk.IconTheme.get_default()
    nome_do_icone = casa.icone
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
    """O nome do lock de instância única: um por TELA."""
    tela = os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY") or "sem-tela"
    return "gui-" + re.sub(r"[^A-Za-z0-9_.-]", "_", tela)


def a_janela_vai_para_a_tela(args: list[str]) -> bool:
    """A janela deste processo nasce numa tela de verdade?"""
    return os.environ.get("HEFESTO_NA_TELA") == "1" and "--oculta" not in args


def tomar_a_vez(args: list[str]) -> str | None:
    """Toma a vez de ser A janela desta tela, no modelo *primeira vence*."""
    if not a_janela_vai_para_a_tela(args):
        return ""
    from hefesto_dualsense4unix.utils import single_instance as si

    nome = nome_da_vez()
    atendidos: list[bool] = []

    def _pedir(anterior: int) -> None:
        atendidos.append(si.pedir_a_frente(nome, anterior))

    for _volta in range(2):
        atendidos.clear()
        try:
            pid = si.acquire_or_bring_to_front(nome, _pedir)
        except (OSError, RuntimeError) as erro:
            print(f"  sem instância única nesta abertura ({erro})")
            continue
        if pid is None:
            if atendidos and atendidos[-1]:
                return None
            print("  a janela aberta nesta tela não respondeu: abro outra")
            return ""
        try:
            si.abrir_a_porta_de_frente(nome)
        except OSError as erro:
            si.release(nome)
            print(f"  sem instância única nesta abertura ({erro})")
            return ""
        return nome
    return ""


def janelas_de_frente(janelas: list[Any]) -> list[Any]:
    """As janelas que um pedido de vir à frente apresenta."""
    from gi.repository import Gtk

    return [
        j for j in janelas
        if isinstance(j, Gtk.Window)
        and not isinstance(j, Gtk.OffscreenWindow)
        and j.get_window_type() == Gtk.WindowType.TOPLEVEL
        and j.get_visible()
        and j.get_transient_for() is None
    ]


def vir_a_frente(porta: Any) -> bool:
    """Atende os pedidos da fila da porta: apresenta a janela, com o token de quem pediu."""
    from gi.repository import Gtk

    from hefesto_dualsense4unix.utils import single_instance as si

    while (token := si.ler_o_pedido(porta)) is not False:
        janelas = janelas_de_frente(Gtk.Window.list_toplevels())
        for janela in janelas:
            if token:
                janela.set_startup_id(token)
            janela.present()
        print(f"  a janela veio para a frente ({len(janelas)} apresentada(s)"
              f"{', com o token de quem pediu' if token else ''})")
    return True


def armar_a_volta_a_frente(nome: str) -> None:
    """Põe a porta da janela no laço do GLib, que roda na thread da janela."""
    from gi.repository import GLib

    from hefesto_dualsense4unix.utils import single_instance as si

    porta = si.porta_de_frente(nome)
    if porta is None:
        return
    GLib.io_add_watch(
        porta.fileno(), GLib.PRIORITY_DEFAULT, GLib.IOCondition.IN,
        lambda _fd, _condicao: vir_a_frente(porta),
    )


TETO_DO_DIARIO = 1 << 20


def diario_da_janela() -> TextIO | None:
    """O arquivo onde a janela dela deixa rastro, ou ``None`` se há terminal."""
    fluxo = sys.stderr
    try:
        if fluxo is not None and hasattr(fluxo, "isatty") and fluxo.isatty():
            return None
    except (ValueError, OSError):
        pass

    from hefesto_dualsense4unix.utils.xdg_paths import state_dir

    casa = state_dir(ensure=True)
    diario = casa / "interface.log"
    try:
        if diario.exists() and diario.stat().st_size > TETO_DO_DIARIO:
            diario.replace(casa / "interface.log.1")
        return diario.open("a", buffering=1, encoding="utf-8", errors="replace")
    except OSError as erro:
        print(f"  sem diário da janela ({erro})", file=sys.stderr)
        return None


def abrir(argv: list[str] | None = None, *, na_tela_por_padrao: bool = False) -> int:
    """Abre a janela: guarda da tela, saneamento, diário, vez, identidade e, por fim, o piloto."""
    args = list(sys.argv[1:] if argv is None else argv)

    if na_tela_por_padrao:
        os.environ.setdefault("HEFESTO_NA_TELA", "1")
    garantir_tela_de_mentira()

    from hefesto_dualsense4unix.app.arranque import sanear_loaders_do_gdk_pixbuf

    loaders_saneados = sanear_loaders_do_gdk_pixbuf()

    diario = diario_da_janela()
    if diario is not None:
        import datetime

        sys.stdout = diario
        sys.stderr = diario
        print(f"\n===== a janela abriu em "
              f"{datetime.datetime.now().isoformat(timespec='seconds')} =====")
    if loaders_saneados:
        print("  loaders do GdkPixbuf: o cache herdado não serve a este processo;"
              " vale o do sistema")

    piloto = achar_o_piloto()
    if piloto is None:
        print("não achei o piloto (hefesto_dualsense4unix.interface.hefesto_vivo)",
              file=sys.stderr)
        for c in CANDIDATOS_DO_PILOTO:
            print(f"  procurei por: {c}", file=sys.stderr)
        return 1

    from hefesto_dualsense4unix.utils import identidade

    vez = tomar_a_vez(args)
    if vez is None:
        print("  já havia uma janela aberta nesta tela: ela veio para a frente")
        return 0

    for linha in vestir_a_identidade(identidade.atual()):
        print(f"  {linha}")
    print()
    if vez:
        armar_a_volta_a_frente(vez)

    sys.argv = [piloto, *args]
    runpy.run_module(piloto, run_name="__main__")
    return 0


def entrada() -> int:
    """O console script `hefesto-dualsense4unix-gui`: a janela vai para a tela de quem pediu."""
    return abrir(na_tela_por_padrao=True)


if __name__ == "__main__":
    sys.exit(entrada())
