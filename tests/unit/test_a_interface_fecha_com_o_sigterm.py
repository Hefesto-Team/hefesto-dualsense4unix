"""A interface fecha com o SIGTERM e com o SIGHUP, pelo mesmo caminho do «Fechar».

Medido em 19/10/2026 na bancada: um `kill -TERM` no processo da interface escreveu
`[janela] fechou: sinal SIGTERM` no diário e o processo ficou em `futex_do_wait` até o
`kill -9`. A linha prova que o tratador correu no laço do GLib; a espera veio depois do
laço. O «Fechar» e o Alt+F4 sempre saíram, e a diferença entre os caminhos era uma: eles
destroem a janela (o WebView e o contexto de GL dele) ainda dentro do laço, e o sinal só
pedia `Gtk.main_quit`, deixando a janela viva para o fim do intérprete. No processo dela o
WebView tem contexto de GL na placa de vídeo, e o fim do intérprete com ele vivo é onde a
espera mora; no Xvfb não há esse contexto, e por isso o prazo daqui passa com ou sem a cura.

A régua que morde é a do caminho: o sinal destrói a janela antes de o laço acabar.
MORDIDA: voltar o `_chegou_o_sinal` a `anotar_o_fim` + `Gtk.main_quit` (sem passar pelo
`fechar`): os dois casos do caminho reprovam («a janela não foi destruída dentro do laço»).

Tudo roda num filho sob `xvfb-run`, num lar de mentira (HOME, XDG e o barramento de sistema
desviados; o soquete do broker aponta para dentro do lar): nada fala com a sessão, o serviço
ou o aparelho de quem roda.
"""

from __future__ import annotations

import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import textwrap
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("A-INTERFACE-FECHA-COM-O-SIGTERM-01")

RAIZ = Path(__file__).resolve().parents[2]
FIM = re.compile(r"\[janela\] fechou: (?P<motivo>.+) · aberta há (?P<s>\d+) s")
PRAZO_S = 3.0

pytestmark = pytest.mark.skipif(
    shutil.which("xvfb-run") is None,
    reason="sem `xvfb-run` a janela nasceria na tela de quem roda",
)


def _ambiente_do_lar(lar: Path) -> dict[str, str]:
    """Sem a sessão, o barramento, o som, o serviço e o broker de quem roda."""
    env = {
        k: v for k, v in os.environ.items()
        if k not in {
            "DISPLAY", "WAYLAND_DISPLAY", "DBUS_SESSION_BUS_ADDRESS", "PULSE_SERVER",
            "PIPEWIRE_REMOTE", "HEFESTO_SEM_JANELA", "HEFESTO_NA_TELA",
        }
    }
    env.update(
        HOME=str(lar), XDG_CONFIG_HOME=str(lar / "c"), XDG_DATA_HOME=str(lar / "d"),
        XDG_STATE_HOME=str(lar / "s"), XDG_CACHE_HOME=str(lar / "k"),
        XDG_RUNTIME_DIR=str(lar / "r"), GDK_BACKEND="x11",
        DBUS_SYSTEM_BUS_ADDRESS=f"unix:path={lar / 'r' / 'sem-barramento'}",
        HEFESTO_BROKER_SOCKET=str(lar / "r" / "sem-broker.sock"),
        PYTHONPATH=str(RAIZ / "src"), PYTHONDONTWRITEBYTECODE="1", PYTHONUNBUFFERED="1",
    )
    for pasta in ("c", "d", "s", "k", "r"):
        (lar / pasta).mkdir()
    (lar / "r").chmod(0o700)
    return env


@pytest.fixture
def lar() -> Iterator[Path]:
    pasta = Path(tempfile.mkdtemp(prefix="sig-", dir="/tmp"))
    yield pasta
    shutil.rmtree(pasta, ignore_errors=True)


def _vivo(pid: int) -> bool:
    try:
        estado = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
    except (OSError, IndexError):
        return False
    return estado != "Z"


def _esperar(condicao: Callable[[], bool], prazo: float) -> bool:
    fim = time.monotonic() + prazo
    while time.monotonic() < fim:
        if condicao():
            return True
        time.sleep(0.05)
    return condicao()


_FILHO_DO_CAMINHO = textwrap.dedent(
    """
    import pathlib, signal, sys
    signal.signal(signal.SIGHUP, signal.SIG_DFL)
    from hefesto_dualsense4unix.interface import janela as jn
    from gi.repository import GLib, Gtk
    alvo = pathlib.Path(sys.argv[1])
    alvo.write_text("<!doctype html><title>Prova do sinal</title><p>oi", encoding="utf-8")
    tela = jn.JanelaDaAba(arquivo=alvo, titulo_esperado="Prova do sinal",
                          ao_carregar=lambda: None, oculta=False)
    no_laco = [False]
    tela.janela.connect("destroy", lambda *_: print(
        "DESTRUIDA", "dentro-do-laco" if no_laco[0] else "fora-do-laco", flush=True))
    tela.fechar_por_sinal()
    def pronto():
        no_laco[0] = True
        print("PRONTO", flush=True)
        return False
    GLib.timeout_add(300, pronto)
    GLib.timeout_add(20000, Gtk.main_quit)
    Gtk.main()
    no_laco[0] = False
    print("SAIU-DO-LACO", flush=True)
    """
)


@pytest.mark.parametrize("sinal", [signal.SIGTERM, signal.SIGHUP], ids=["SIGTERM", "SIGHUP"])
def test_o_sinal_destroi_a_janela_dentro_do_laco_como_o_fechar(
    lar: Path, sinal: signal.Signals
) -> None:
    """O sinal fecha a janela de verdade (com barra) pelo `fechar`: o `destroy` chega com o laço

    A prova da D-2110-O-SINAL-FECHA-PELO-FECHAR.
    ainda girando, a linha do fim diz o sinal uma vez só, e o processo sai com rc 0."""
    env = _ambiente_do_lar(lar)
    script = lar / "filho.py"
    script.write_text(
        "import os\nprint('PID', os.getpid(), flush=True)\n" + _FILHO_DO_CAMINHO,
        encoding="utf-8")
    filho = subprocess.Popen(
        ["xvfb-run", "-a", "-s", "-screen 0 1920x1080x24", sys.executable, str(script),
         str(lar / "prova.html")],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    linhas: list[str] = []
    try:
        assert filho.stdout is not None
        pid = 0
        for linha in filho.stdout:
            linhas.append(linha.rstrip("\n"))
            if linha.startswith("PID "):
                pid = int(linha.split()[1])
            if linha.startswith("PRONTO"):
                break
        assert pid, "\n".join(linhas[-30:])
        os.kill(pid, sinal)
        resto, _ = filho.communicate(timeout=30)
        linhas += resto.splitlines()
    finally:
        if filho.poll() is None:
            filho.kill()
            filho.wait(10)
    saida = "\n".join(linhas)
    assert filho.returncode == 0, saida[-1500:]
    assert "DESTRUIDA dentro-do-laco" in linhas, (
        "a janela não foi destruída dentro do laço: o sinal saiu sem passar pelo `fechar`\n"
        + saida[-1500:])
    assert linhas.index("DESTRUIDA dentro-do-laco") < linhas.index("SAIU-DO-LACO")
    motivos = [m["motivo"] for linha in linhas if (m := FIM.search(linha))]
    assert motivos == [f"sinal {sinal.name}"], saida[-1500:]


_FILHO_DA_INTERFACE = textwrap.dedent(
    """
    import os, pathlib, signal, sys
    signal.signal(signal.SIGHUP, signal.SIG_DFL)
    do_pid = sys.argv[1]
    pathlib.Path(do_pid).write_text(str(os.getpid()))
    from hefesto_dualsense4unix.interface import abrir
    rc = abrir.abrir(sys.argv[2:])
    with open(do_pid, "a") as arquivo:
        arquivo.write(f" {rc}")
    raise SystemExit(rc)
    """
)


@pytest.mark.parametrize(
    ("modo", "sinal"),
    [("oculta", signal.SIGTERM), ("oculta", signal.SIGHUP), ("janela", signal.SIGTERM)],
    ids=["oculta-SIGTERM", "oculta-SIGHUP", "janela-SIGTERM"],
)
def test_a_interface_sai_em_menos_de_tres_segundos_com_a_linha_do_fim(
    lar: Path, modo: str, sinal: signal.Signals
) -> None:
    """A porta do produto (`interface/abrir.py`), de pé, recebe o sinal e o processo some em
    menos de 3 s, com rc 0 e a linha do fim no diário."""
    env = _ambiente_do_lar(lar)
    script = lar / "interface.py"
    script.write_text(_FILHO_DA_INTERFACE, encoding="utf-8")
    arquivo_do_pid = lar / "pid"
    args = ["--abre", "01-jogar.html"] + (["--oculta"] if modo == "oculta" else [])
    diario = lar / "s" / "hefesto-dualsense4unix" / "interface.log"
    filho = subprocess.Popen(
        ["xvfb-run", "-a", "-s", "-screen 0 1920x1080x24", sys.executable, str(script),
         str(arquivo_do_pid), *args],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
        text=True)
    try:
        def de_pe() -> bool:
            return diario.is_file() and "primeira pintura" in diario.read_text(errors="replace")

        assert _esperar(de_pe, 90), (
            f"a interface não pintou: {filho.poll()}\n"
            + (diario.read_text(errors="replace")[-1500:] if diario.is_file() else ""))
        pid = int(arquivo_do_pid.read_text())
        time.sleep(1.0)
        inicio = time.monotonic()
        os.kill(pid, sinal)
        saiu = _esperar(lambda: not _vivo(pid), PRAZO_S + 5)
        levou = time.monotonic() - inicio
        filho.communicate(timeout=30)
    finally:
        if filho.poll() is None:
            filho.kill()
            filho.wait(10)
    texto = diario.read_text(errors="replace")
    assert saiu and levou < PRAZO_S, f"o processo levou {levou:.1f} s\n{texto[-1500:]}"
    lido = arquivo_do_pid.read_text().split()
    voltou = lido[1] if len(lido) > 1 else "nada: o processo morreu antes de ele voltar"
    assert filho.returncode == 0, (
        f"o xvfb-run saiu com {filho.returncode}; o `abrir` devolveu {voltou}\n" + texto[-1500:])
    motivos = [m["motivo"] for linha in texto.splitlines() if (m := FIM.search(linha))]
    assert motivos == [f"sinal {sinal.name}"], texto[-1500:]
