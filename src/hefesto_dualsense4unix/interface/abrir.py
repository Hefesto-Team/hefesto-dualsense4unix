"""A entrada do produto que abre a janela: a identidade veste o processo ANTES de ela nascer.

Dois chamadores: o console script (`entrada`) e o calço `scripts/abrir_interface.py` (`abrir`).
Nada roda no import; o piloto roda por `runpy.run_module`, depois da identidade e da guarda da
tela. Uma janela por tela (`tomar_a_vez`); o serviço parado volta com a janela
(`trazer_o_servico`), salvo o Parar da aba Sistema (`MARCA_DO_PARAR`). O porquê de cada parte está
em `docs/research/o-porque-dos-modulos.md`, seção `abrir`.
"""
from __future__ import annotations

import contextlib
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
    return next(
        (nome for nome in CANDIDATOS_DO_PILOTO if importlib.util.find_spec(nome) is not None),
        None,
    )


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
    aberto = fluxo is not None and not getattr(fluxo, "closed", False)
    if aberto and hasattr(fluxo, "isatty") and fluxo.isatty():
        return None

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
    if a_janela_vai_para_a_tela(args):
        # A bandeja que o «Sair» dela fechou volta com a janela, se a escolha está ligada.
        from hefesto_dualsense4unix.app.actions.atos_da_bandeja import garantir_a_bandeja

        garantir_a_bandeja()
        trazer_o_servico()

    sys.argv = [piloto, *args]
    runpy.run_module(piloto, run_name="__main__")
    return 0


#: O Parar da aba Sistema deixa esta marca no runtime da sessão, e abrir a janela a respeita.
MARCA_DO_PARAR = "servico-parado-pela-aba-sistema"


def marca_do_parar() -> Path:
    """Onde mora a marca do Parar: no runtime da sessão, que o logout limpa."""
    from hefesto_dualsense4unix.utils.xdg_paths import runtime_dir

    return runtime_dir() / MARCA_DO_PARAR


def lembrar_o_parar(parado: bool) -> None:
    """Grava (o Parar da aba Sistema) ou apaga (o serviço que volta, o «Sair») a marca."""
    marca = marca_do_parar()
    with contextlib.suppress(OSError):
        if parado:
            marca.parent.mkdir(parents=True, exist_ok=True)
            marca.touch()
        else:
            marca.unlink(missing_ok=True)


def trazer_o_servico() -> bool:
    """Liga o serviço parado, num fio próprio para a janela não esperar a subida. Diz se tentou.

    Quem decide se liga é `a09_sistema.ativar_o_servico`, o dono do ato (sem unit, de pé ou com
    um avulso vivo, não liga); a marca do Parar da aba Sistema segura o serviço parado.
    """
    if marca_do_parar().exists():
        print("  o serviço foi parado na aba Sistema: segue parado")
        return False
    from hefesto_dualsense4unix.interface.pacotes import a09_sistema, fios

    def _subir() -> None:
        try:
            if a09_sistema.ativar_o_servico():
                print("  o serviço estava parado: voltou com a janela")
        except Exception as erro:
            print(f"  o serviço estava parado e não voltou: {erro}")

    fios.soltar("trazer-o-servico", _subir)
    return True


def entrada() -> int:
    """O console script `hefesto-dualsense4unix-gui`: a janela vai para a tela de quem pediu."""
    return abrir(na_tela_por_padrao=True)


if __name__ == "__main__":
    sys.exit(entrada())
