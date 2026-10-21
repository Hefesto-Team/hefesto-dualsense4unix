"""Toda saída da interface passa pelo `fechar`, que destrói a janela dentro do laço.

Desde a A-INTERFACE-FECHA-COM-O-SIGTERM-01 o sinal fecha pelo `fechar`. O `agendar_saida` (o
prazo do `--segundos` do piloto) e o `_morrer` (a carga que falha) ainda chamavam `Gtk.main_quit`
direto: a janela, o WebView e o contexto de GL dele ficavam vivos até o fim do intérprete, que é
onde a espera do sinal mora na placa NVIDIA (medido em 19/10/2026, ver o irmão
`test_a_interface_fecha_com_o_sigterm.py`).

A cura é de lugar: `fechar` é o ÚNICO método que encerra o laço (e o `_ao_destruir`, que o
`destroy` do `fechar` dispara). Duas réguas, de gentes diferentes:

1. a ESTRUTURA, sem GTK: nenhum outro método da `JanelaDaAba` chama `Gtk.main_quit`;
2. o COMPORTAMENTO, num filho sob `xvfb-run` e num lar de mentira: o prazo e a carga morta
   chegam ao `destroy` com o laço girando, a linha do fim sai uma vez, o processo sai com rc 0.

O sinal já tem o caso dele no irmão; aqui ficam os outros dois caminhos.

MORDIDAS (a régua reprova sem a cura): (a) o `Gtk.main_quit` solto de volta no `_morrer` e no
`sair` do `agendar_saida` reprova a régua de estrutura; (b) um `fechar` que só anota e sai (o
comportamento antigo desses dois caminhos) reprova a régua de comportamento nos dois casos.
O que a placa NVIDIA faz com o processo é a conferência dela, na máquina do usuário.
"""
from __future__ import annotations

import ast
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
from collections.abc import Iterator
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
JANELA = RAIZ / "src" / "hefesto_dualsense4unix" / "interface" / "janela.py"
FIM = re.compile(r"\[janela\] fechou: (?P<motivo>.+) · aberta há (?P<s>\d+) s")
# Quem pode encerrar o laço: o `fechar` (o caminho) e o `_ao_destruir` (o destroy que ele dispara).
PODEM_ENCERRAR_O_LACO = {"fechar", "_ao_destruir"}
PRAZO_DO_FILHO_S = 90


# --- 1. a estrutura: um lugar só encerra o laço (sem GTK) ------------------------------------


def quem_encerra_o_laco(fonte: str) -> set[str]:
    """Os métodos da `JanelaDaAba` que chamam `Gtk.main_quit()`, inclusive de função aninhada."""
    arvore = ast.parse(fonte)
    classe = next(
        n for n in ast.walk(arvore) if isinstance(n, ast.ClassDef) and n.name == "JanelaDaAba"
    )
    achados: set[str] = set()
    for quem in classe.body:
        if not isinstance(quem, ast.FunctionDef):
            continue
        for no in ast.walk(quem):
            if (
                isinstance(no, ast.Call)
                and isinstance(no.func, ast.Attribute)
                and no.func.attr == "main_quit"
                and isinstance(no.func.value, ast.Name)
                and no.func.value.id == "Gtk"
            ):
                achados.add(quem.name)
    return achados


def test_so_o_fechar_e_o_destroy_dele_encerram_o_laco() -> None:
    donos = quem_encerra_o_laco(JANELA.read_text(encoding="utf-8"))
    assert donos == PODEM_ENCERRAR_O_LACO, (
        f"métodos que chamam Gtk.main_quit fora do caminho do `fechar`: "
        f"{sorted(donos - PODEM_ENCERRAR_O_LACO)}; sem o `fechar` o intérprete acaba com a "
        f"janela viva: {sorted(PODEM_ENCERRAR_O_LACO - donos)}"
    )


def test_o_prazo_e_a_carga_morta_chamam_o_fechar() -> None:
    """A estrutura sozinha aceitaria os dois sem sair; a régua exige a chamada ao `fechar`."""
    fonte = JANELA.read_text(encoding="utf-8")
    for quem in ("_morrer", "agendar_saida"):
        corpo = ast.get_source_segment(
            fonte,
            next(
                n
                for n in ast.walk(ast.parse(fonte))
                if isinstance(n, ast.FunctionDef) and n.name == quem
            ),
        )
        assert corpo is not None and "self.fechar(" in corpo, (
            f"`{quem}` não sai pelo `self.fechar`"
        )


@pytest.mark.parametrize("quem", ["_morrer", "agendar_saida"])
def test_mordida_main_quit_solto_de_volta_reprova_a_estrutura(quem: str) -> None:
    """Arrancar a cura de um caminho (a chamada ao `fechar` vira `Gtk.main_quit()`) reprova."""
    fonte = JANELA.read_text(encoding="utf-8")
    linhas = fonte.splitlines()
    dentro = False
    for i, linha in enumerate(linhas):
        if re.match(rf"    def {quem}\(", linha):
            dentro = True
        elif dentro and re.match(r"    def ", linha):
            break
        elif dentro and "self.fechar(" in linha:
            linhas[i] = re.sub(r"self\.fechar\(.*\)", "Gtk.main_quit()", linha)
            break
    mordida = "\n".join(linhas)
    assert mordida != fonte, f"a mordida não achou o `self.fechar` em `{quem}`"
    assert quem_encerra_o_laco(mordida) == PODEM_ENCERRAR_O_LACO | {quem}


# --- 2. o comportamento: o prazo e a carga morta destroem a janela dentro do laço -------------


def _sem_gi_real() -> bool:
    """Sem o PyGObject real e o WebKit, o filho não nasce. A guarda é de função, não de módulo:
    a régua de estrutura de cima roda em todo lugar."""
    teste = subprocess.run(
        [sys.executable, "-c",
         "import gi; gi.require_version('Gtk', '3.0'); gi.require_version('WebKit2', '4.1');"
         "from gi.repository import Gtk, WebKit2"],
        capture_output=True, check=False, timeout=60)
    return teste.returncode != 0


def _exigir_o_ambiente_da_janela() -> None:
    if shutil.which("xvfb-run") is None:
        pytest.skip("sem `xvfb-run` a janela nasceria na tela de quem roda")
    if _sem_gi_real():
        if os.environ.get("HEFESTO_EXIGE_GTK_REAL") == "1":
            pytest.fail("HEFESTO_EXIGE_GTK_REAL=1 e o GTK/WebKit real não está disponível")
        pytest.skip("sem o PyGObject real com WebKit2 4.1")


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
    pasta = Path(tempfile.mkdtemp(prefix="sai-", dir="/tmp"))
    yield pasta
    shutil.rmtree(pasta, ignore_errors=True)


_FILHO = textwrap.dedent(
    """
    import pathlib, signal, sys
    signal.signal(signal.SIGHUP, signal.SIG_DFL)
    from hefesto_dualsense4unix.interface import janela as jn
    from gi.repository import GLib, Gtk
    caminho, morde = sys.argv[1], sys.argv[2]
    alvo = pathlib.Path(sys.argv[3])
    alvo.write_text("<!doctype html><title>Prova da saida</title><p>oi", encoding="utf-8")
    if morde == "morde":
        # O comportamento antigo desses dois caminhos: anota e encerra o laço, sem destruir.
        def fechar_sem_destruir(self, motivo="Fechar"):
            self.anotar_o_fim(motivo)
            Gtk.main_quit()
        jn.JanelaDaAba.fechar = fechar_sem_destruir
    tela = jn.JanelaDaAba(arquivo=alvo, titulo_esperado="Prova da saida",
                          ao_carregar=lambda: None, oculta=False)
    no_laco = [False]
    tela.janela.connect("destroy", lambda *_: print(
        "DESTRUIDA", "dentro-do-laco" if no_laco[0] else "fora-do-laco", flush=True))
    antes = []
    if caminho == "agendada":
        tela.agendar_saida(1.0, antes=lambda: antes.append(print("ANTES", flush=True)))
    else:
        GLib.timeout_add(1000, lambda: (tela._morrer("prova de carga"), False)[1])
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

MOTIVO_ESPERADO = {
    "agendada": "o prazo de 1 s acabou",
    "morta": "a carga falhou (prova de carga)",
}


def _rodar_o_filho(lar: Path, caminho: str, morde: bool) -> tuple[int, list[str]]:
    env = _ambiente_do_lar(lar)
    script = lar / "filho.py"
    script.write_text(_FILHO, encoding="utf-8")
    filho = subprocess.Popen(
        ["xvfb-run", "-a", "-s", "-screen 0 1920x1080x24", sys.executable, str(script),
         caminho, "morde" if morde else "cura", str(lar / "prova.html")],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
        text=True)
    try:
        saida, _ = filho.communicate(timeout=PRAZO_DO_FILHO_S)
    finally:
        if filho.poll() is None:
            filho.kill()
            filho.wait(10)
    return filho.returncode, saida.splitlines()


def faltas_do_filho(caminho: str, rc: int, linhas: list[str]) -> list[str]:
    """O que o filho tinha de mostrar e não mostrou. Função pura: a mordida a chama."""
    faltas = []
    if rc != 0:
        faltas.append(f"o processo saiu com rc {rc}")
    if "DESTRUIDA dentro-do-laco" not in linhas:
        faltas.append("a janela não foi destruída dentro do laço (saiu sem passar pelo `fechar`)")
    elif "SAIU-DO-LACO" not in linhas or linhas.index("DESTRUIDA dentro-do-laco") > linhas.index(
        "SAIU-DO-LACO"
    ):
        faltas.append("o destroy veio depois de o laço acabar")
    motivos = [m["motivo"] for linha in linhas if (m := FIM.search(linha))]
    if motivos != [MOTIVO_ESPERADO[caminho]]:
        faltas.append(f"a linha do fim devia dizer só «{MOTIVO_ESPERADO[caminho]}»: {motivos}")
    if caminho == "agendada" and "ANTES" not in linhas:
        faltas.append("o `antes` do agendar_saida não correu")
    return faltas


@pytest.mark.parametrize("caminho", ["agendada", "morta"])
def test_o_prazo_e_a_carga_morta_destroem_a_janela_dentro_do_laco(lar: Path, caminho: str) -> None:
    _exigir_o_ambiente_da_janela()
    rc, linhas = _rodar_o_filho(lar, caminho, morde=False)
    assert faltas_do_filho(caminho, rc, linhas) == [], "\n".join(linhas[-30:])


@pytest.mark.parametrize("caminho", ["agendada", "morta"])
def test_mordida_o_fechar_que_so_anota_reprova_o_comportamento(lar: Path, caminho: str) -> None:
    """O `fechar` do comportamento antigo (anota e sai, sem destruir): a régua tem de reprovar."""
    _exigir_o_ambiente_da_janela()
    rc, linhas = _rodar_o_filho(lar, caminho, morde=True)
    faltas = faltas_do_filho(caminho, rc, linhas)
    assert any("não foi destruída dentro do laço" in f for f in faltas), "\n".join(linhas[-30:])


def test_a_regua_do_filho_reprova_a_saida_que_nao_destruiu() -> None:
    """Sem GTK: a função pura vê a diferença entre a saída com e sem o destroy."""
    boa = ["PRONTO", "DESTRUIDA dentro-do-laco",
           "[janela] fechou: o prazo de 1 s acabou · aberta há 1 s", "SAIU-DO-LACO"]
    assert faltas_do_filho("agendada", 0, ["ANTES", *boa]) == []
    sem_destroy = [x for x in boa if not x.startswith("DESTRUIDA")]
    faltas = faltas_do_filho("agendada", 0, ["ANTES", *sem_destroy])
    assert any("não foi destruída" in f for f in faltas)
    assert any("devia dizer só" in f for f in faltas_do_filho("morta", 0, boa))
