"""OS-TOCADORES-DA-HAPTICA-MORREM-COM-O-PAI-01: o `pw-cat` da háptica não sobrevive ao daemon.

Os dois tocadores (o do rumble e o do estalo) lançavam o `pw-cat` com o `subprocess.Popen` puro,
sem o `preexec_fn` que o dono dos filhos de som já tinha. Com o daemon morto por SIGKILL fora do
systemd, o filho ficava até o cano fechar.

A cura é um lançador só (`filho_de_som.lancar_filho`). O `PR_SET_PDEATHSIG` dispara na morte do
fio que fez o fork, então o teste confere também que cada tocador lança do fio dele, que só acaba
em `parar`, e não de um fio que acabe antes do filho. Nada aqui toca o servidor de som.
"""

from __future__ import annotations

import ast
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.app import mic_monitor as mm
from hefesto_dualsense4unix.integrations import alto_falante_bt as af
from hefesto_dualsense4unix.integrations import endpoint_de_haptica as eh
from hefesto_dualsense4unix.integrations import filho_de_som
from hefesto_dualsense4unix.integrations import transiente_do_jogo as tj

RAIZ = Path(__file__).resolve().parents[2]
SRC = RAIZ / "src" / "hefesto_dualsense4unix"

PROGRAMAS_DE_SOM = ("pw-cat", "pacat", "pw-loopback", "pw-record", "parec")

SEM_PDEATHSIG_AINDA: dict[str, str] = {}


class _RecusaError(OSError):
    """O espião de `Popen` que anota o pedido e recusa subir o processo."""


@pytest.fixture()
def espiao(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    visto: dict[str, Any] = {"pedidos": [], "fios": [], "chegou": threading.Event()}

    def _popen(argv: Any, *_a: Any, **kw: Any) -> Any:
        visto["pedidos"].append((list(argv), kw))
        visto["fios"].append(threading.current_thread())
        visto["chegou"].set()
        raise _RecusaError("espião")

    monkeypatch.setattr(filho_de_som.subprocess, "Popen", _popen)
    return visto


def test_o_tocador_do_rumble_lanca_preso_ao_pai(espiao: dict[str, Any]) -> None:
    """D-2011-OS-TOCADORES-DA-HAPTICA-MORREM-COM-O-PAI: o `Popen` leva o `preexec_fn` do dono."""
    tocador = eh.TocadorDoRumble("APARELHOTESTEX", argv_de=lambda *_a: ["pw-cat", "--playback"])

    tocador._tocar("sink-de-mentira")

    (argv, kw), = espiao["pedidos"]
    assert argv == ["pw-cat", "--playback"]
    assert kw["preexec_fn"] is filho_de_som.morrer_com_o_pai


def test_o_tocador_do_estalo_lanca_preso_ao_pai(espiao: dict[str, Any]) -> None:
    """MORDIDA: o estalo de volta ao `Popen` puro reprova aqui."""
    tocador = tj.TocadorDoEstalo("sink-de-mentira", argv_de=lambda *_a: ["pw-cat", "--playback"])

    tocador._tocar()

    (_, kw), = espiao["pedidos"]
    assert kw["preexec_fn"] is filho_de_som.morrer_com_o_pai


def _o_fio_que_lancou_vive_ate_o_parar(tocador: Any, espiao: dict[str, Any]) -> None:
    assert espiao["chegou"].wait(timeout=10), "o tocador não tentou subir o processo"
    fio = espiao["fios"][0]
    assert fio is tocador._fio, "o filho saiu de um fio que não é o do tocador"
    assert fio.is_alive(), "o fio que lançou o filho acabou antes do filho"
    tocador.parar()
    assert not fio.is_alive()


def test_o_rumble_lanca_do_fio_do_tocador_que_vive_ate_o_parar(espiao: dict[str, Any]) -> None:
    tocador = eh.TocadorDoRumble("APARELHOTESTEX", argv_de=lambda *_a: ["pw-cat"])
    tocador.levar(10, 10, sink="sink-de-mentira", dono="d")
    _o_fio_que_lancou_vive_ate_o_parar(tocador, espiao)


def test_o_estalo_lanca_do_fio_do_tocador_que_vive_ate_o_parar(espiao: dict[str, Any]) -> None:
    tocador = tj.TocadorDoEstalo(
        "sink-de-mentira", argv_de=lambda *_a: ["pw-cat"], o_jogo_toca=lambda *_a: False)
    tocador.tocar(tj.recorte_pronto(bytes(tj.BYTES_DO_BLOCO)))
    _o_fio_que_lancou_vive_ate_o_parar(tocador, espiao)


def _vivo(pid: int) -> bool:
    try:
        estado = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8").rpartition(")")[2].split()[0]
    except OSError:
        return False
    return estado != "Z"


def test_o_filho_cai_com_o_daemon_que_leva_sigkill(tmp_path: Path) -> None:
    """MORDIDA: `lancar_filho` sem o `preexec_fn` deixa o filho vivo depois do SIGKILL."""
    pidfile = tmp_path / "pid"
    codigo = (
        "import os, signal, subprocess\n"
        "from hefesto_dualsense4unix.integrations.filho_de_som import lancar_filho\n"
        "nada = subprocess.DEVNULL\n"
        "filho = lancar_filho(['sleep', '300'], stdout=nada, stderr=nada)\n"
        f"open({str(pidfile)!r}, 'w').write(str(filho.pid))\n"
        "os.kill(os.getpid(), signal.SIGKILL)\n"
    )
    daemon = subprocess.run(
        [sys.executable, "-c", codigo], env={**os.environ, "PYTHONPATH": str(RAIZ / "src")},
        timeout=60, check=False, capture_output=True)
    assert daemon.returncode == -signal.SIGKILL, daemon.stderr.decode()[-400:]
    pid = int(pidfile.read_text(encoding="utf-8"))
    try:
        fim = time.monotonic() + 5.0
        while _vivo(pid) and time.monotonic() < fim:
            time.sleep(0.02)
        assert not _vivo(pid), "o filho seguiu vivo depois do daemon morrer"
    finally:
        if _vivo(pid):
            os.kill(pid, signal.SIGKILL)


def _lancamentos_sem_o_dono(arquivo: Path) -> list[int]:
    """As linhas com `subprocess.Popen` fora de anotação e sem `preexec_fn=…morrer_com_o_pai`."""
    arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
    presos: set[int] = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Call):
            for kw in no.keywords:
                nome = getattr(kw.value, "id", getattr(kw.value, "attr", ""))
                if kw.arg == "preexec_fn" and nome.endswith("morrer_com_o_pai"):
                    presos.add(id(no.func))
        if isinstance(no, ast.Subscript):
            presos.add(id(no.value))
    return sorted(
        no.lineno for no in ast.walk(arvore)
        if isinstance(no, ast.Attribute) and no.attr == "Popen" and id(no) not in presos
    )


def _arquivos_de_som() -> list[Path]:
    achados = []
    for arquivo in sorted(SRC.rglob("*.py")):
        texto = arquivo.read_text(encoding="utf-8")
        if arquivo.name != "filho_de_som.py" and any(
            f'"{programa}"' in texto or f"'{programa}'" in texto for programa in PROGRAMAS_DE_SOM
        ):
            achados.append(arquivo)
    return achados


def test_nenhum_filho_de_som_sai_do_src_sem_o_pai() -> None:
    """MORDIDA: um `subprocess.Popen` de `pw-cat`, `pw-loopback` ou `parec` sem o dono reprova."""
    soltos = {
        str(a.relative_to(SRC)): _lancamentos_sem_o_dono(a)
        for a in _arquivos_de_som()
        if str(a.relative_to(SRC)) not in SEM_PDEATHSIG_AINDA
    }
    assert {k: v for k, v in soltos.items() if v} == {}


def test_a_lista_dos_que_ainda_nao_prendem_so_tem_quem_ainda_solta() -> None:
    """A lista de exceção não envelhece calada: sai quem passou a prender."""
    for nome in SEM_PDEATHSIG_AINDA:
        assert _lancamentos_sem_o_dono(SRC / nome), f"{nome} já prende o filho: tire da lista"


def test_a_regua_enxerga_o_popen_puro_e_o_default_do_tocador(tmp_path: Path) -> None:
    solto = tmp_path / "solto.py"
    solto.write_text(
        "import subprocess\n"
        "lancar = outro or subprocess.Popen\n"
        "subprocess.Popen(['pw-cat'])\n"
        "def f() -> subprocess.Popen[bytes]: ...\n", encoding="utf-8")
    preso = tmp_path / "preso.py"
    preso.write_text(
        "import subprocess\n"
        "from x import morrer_com_o_pai\n"
        "subprocess.Popen(['pw-cat'], preexec_fn=morrer_com_o_pai)\n", encoding="utf-8")
    assert _lancamentos_sem_o_dono(solto) == [2, 3]
    assert _lancamentos_sem_o_dono(preso) == []


def test_o_tocador_da_caixa_nasce_pelo_dono_dos_filhos(monkeypatch: pytest.MonkeyPatch) -> None:
    """D-2011-OS-TOCADORES-DA-HAPTICA-MORREM-COM-O-PAI: o tocador lança por ``lancar_filho``.

    MORDIDA: o ``Popen`` próprio de volta no ``lancar_tocador`` deixa o dono sem o pedido.
    """
    pedidos: list[tuple[list[str], dict[str, Any]]] = []

    def _lancar(argv: Any, **kw: Any) -> str:
        pedidos.append((list(argv), kw))
        return "filho"

    monkeypatch.setattr(filho_de_som, "lancar_filho", _lancar)
    monkeypatch.setattr(filho_de_som.subprocess, "Popen", lambda *_a, **_k: "popen-direto")

    assert af.lancar_tocador(["pw-cat", "--playback"]) == "filho"

    (argv, kw), = pedidos
    assert argv == ["pw-cat", "--playback"]
    assert kw == {
        "stdin": subprocess.PIPE, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}


def test_o_parec_do_medidor_nasce_pelo_dono_dos_filhos(monkeypatch: pytest.MonkeyPatch) -> None:
    """MORDIDA: o ``Popen`` próprio de volta no ``_abrir_captura`` solta o ``parec`` da janela."""
    pedidos: list[tuple[list[str], dict[str, Any]]] = []

    def _lancar(argv: Any, **kw: Any) -> str:
        pedidos.append((list(argv), kw))
        return "filho"

    monkeypatch.setattr(filho_de_som, "lancar_filho", _lancar)
    monkeypatch.setattr(mm.shutil, "which", lambda _nome: "/usr/bin/parec")
    monkeypatch.setattr(filho_de_som.subprocess, "Popen", lambda *_a, **_k: "popen-direto")

    assert mm._abrir_captura("fonte-de-mentira") == "filho"

    (argv, kw), = pedidos
    assert argv[0] == "parec" and "--device=fonte-de-mentira" in argv
    assert kw["stdout"] == subprocess.PIPE and kw["stderr"] == subprocess.DEVNULL
    assert kw["env"]["LC_ALL"] == "C"


_FILHOS_DE_MENTIRA = {
    "caixa": ("pw-cat", "from hefesto_dualsense4unix.integrations.alto_falante_bt import "
              "lancar_tocador\nlancar_tocador(['pw-cat'])\n"),
    "medidor": ("parec", "from hefesto_dualsense4unix.app.mic_monitor import _abrir_captura\n"
                "_abrir_captura('fonte-de-mentira')\n"),
}


@pytest.mark.parametrize("quem", sorted(_FILHOS_DE_MENTIRA))
def test_o_filho_do_som_cai_com_o_pai_que_leva_sigkill(tmp_path: Path, quem: str) -> None:
    """MORDIDA: o ``parec`` do medidor sem o dono segue vivo com o cano calado depois do SIGKILL.

    O programa de som é um script de mentira num ``PATH`` temporário que dorme; o pai é um
    processo filho do teste, que lança o filho e leva o próprio SIGKILL.
    """
    programa, lancamento = _FILHOS_DE_MENTIRA[quem]
    binario = tmp_path / "bin"
    binario.mkdir()
    script = binario / programa
    script.write_text('#!/bin/sh\necho $$ > "$PIDFILE"\nexec sleep 300\n', encoding="utf-8")
    script.chmod(0o755)
    pidfile = tmp_path / "pid"
    casa = tmp_path / "casa"
    casa.mkdir()
    codigo = f"import os, signal\n{lancamento}" "os.kill(os.getpid(), signal.SIGKILL)\n"
    pai = subprocess.run(
        [sys.executable, "-c", codigo], timeout=60, check=False, capture_output=True,
        env={
            **os.environ, "PYTHONPATH": str(RAIZ / "src"), "PIDFILE": str(pidfile),
            "PATH": f"{binario}:{os.environ['PATH']}", "HOME": str(casa),
            "XDG_STATE_HOME": str(casa / "state"), "XDG_CONFIG_HOME": str(casa / "config"),
        })
    assert pai.returncode == -signal.SIGKILL, pai.stderr.decode()[-400:]
    fim = time.monotonic() + 5.0
    while not (pidfile.exists() and pidfile.read_text(encoding="utf-8").strip()):
        assert time.monotonic() < fim, "o filho de mentira não gravou o PID"
        time.sleep(0.02)
    pid = int(pidfile.read_text(encoding="utf-8"))
    try:
        while _vivo(pid) and time.monotonic() < fim + 5.0:
            time.sleep(0.02)
        assert not _vivo(pid), f"o filho do {quem} seguiu vivo depois do pai morrer"
    finally:
        if _vivo(pid):
            os.kill(pid, signal.SIGKILL)
