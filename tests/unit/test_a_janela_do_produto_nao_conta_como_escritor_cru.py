"""A janela do produto não conta como escritor cru de fora (23/11/2026).

Medido no `servico.log` de 23/11: `lightbar_escritor_cru_detectado` às 01h40 e às 04h00 acusou um
processo do próprio produto segurando o hidraw do controle, e o gatilho da barra armou à toa.
`escritores_crus_alheios` tirava só o pid do serviço e o pai dele.

O processo do produto se prova pelo `/proc` (o executável, a linha de comando, a ascendência),
nunca pelo nome. O `/proc` dos casos de nó é de mentira (os nós `hidraw` de verdade são do
controle); o caso da ascendência lê o `/proc` de verdade de um filho deste processo.

MORDIDA: `escritores_crus_alheios` de volta a tirar só `{eu, pai}` reprova a janela, a bandeja e a
extensão; md5 igual na volta.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from hefesto_dualsense4unix.core import escritor_cru as ec

SERVICO = 4000
PAI_DO_SERVICO = 3999
SESSAO = 1500
PYTHON = "/usr/bin/python3.12"
RAIZ = Path(ec.__file__).resolve().parents[3]
JANELA = str(RAIZ / "scripts" / "abrir_interface.py")


def _processo(exe: str, argv: list[str], pai: int, cwd: str = "/") -> dict[str, object]:
    return {"exe": exe, "argv": argv, "pai": pai, "cwd": cwd}


PRODUTO = {
    4100: _processo(PYTHON, ["python3", JANELA], SESSAO),
    4101: _processo(PYTHON, ["python3", "-m", "hefesto_dualsense4unix.cli.app", "tray"], SESSAO),
    4102: _processo("/usr/bin/node", ["node", "motor.js"], SERVICO),
    4103: _processo("/usr/bin/bash", ["bash", "-c", "x"], 4102),
    4104: _processo(PYTHON, ["python3", "scripts/abrir_interface.py"], SESSAO, cwd=str(RAIZ)),
}

DE_FORA = {
    6001: _processo("/home/u/.steam/ubuntu12_64/steam", ["/home/u/.local/share/Steam/"
                                                        "ubuntu12_64/steamrt64/steam"], SESSAO),
    6002: _processo(PYTHON, ["python3", "/tmp/hefesto_dualsense4unix/scripts/abrir_interface.py"],
                    SESSAO),
    6003: _processo(PYTHON, ["python3", "-m", "hefesto_dualsense4unix.falso"], SESSAO),
    6004: _processo("/opt/x/hefesto-dualsense4unix", ["hefesto-dualsense4unix", "daemon"], SESSAO),
    6005: _processo(PYTHON, ["python3", "scripts/abrir_interface.py"], SESSAO, cwd="/tmp/imita"),
    6006: _processo(PYTHON, ["python3", "-c", "import hefesto_dualsense4unix"], SESSAO),
}


def _proc_de_mentira(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    processos: dict[int, dict[str, object]],
    fds: dict[int, list[str]],
) -> None:
    """`/proc/<pid>/{fd,exe,cwd,cmdline,stat}` num tmp, lido pelas mesmas portas do módulo."""
    raiz = tmp_path / "proc"
    raiz.mkdir()
    for pid, p in processos.items():
        d = raiz / str(pid)
        (d / "fd").mkdir(parents=True)
        for n, alvo in enumerate(fds.get(pid, []), start=3):
            (d / "fd" / str(n)).symlink_to(alvo)
        (d / "exe").symlink_to(str(p["exe"]))
        (d / "cwd").symlink_to(str(p["cwd"]))
        argv = p["argv"]
        assert isinstance(argv, list)
        (d / "cmdline").write_bytes(b"\0".join(a.encode() for a in argv) + b"\0")
        (d / "stat").write_text(f"{pid} (x y) S {p['pai']} 1 1 0", encoding="utf-8")
    listdir_real = os.listdir
    readlink_real = os.readlink

    def _no_tmp(caminho: object) -> str:
        return str(raiz) + str(caminho)[len("/proc"):]

    def listdir(caminho: object, *a: object, **k: object) -> list[str]:
        s = str(caminho)
        if s == "/proc" or s.startswith("/proc/"):
            return listdir_real(_no_tmp(s))
        return listdir_real(caminho, *a, **k)  # type: ignore[arg-type]

    def readlink(caminho: object, *a: object, **k: object) -> str:
        s = str(caminho)
        if s.startswith("/proc/"):
            return readlink_real(_no_tmp(s))
        return readlink_real(caminho, *a, **k)  # type: ignore[arg-type]

    def ler(pid: int, nome: str) -> bytes:
        try:
            return Path(_no_tmp(f"/proc/{int(pid)}/{nome}")).read_bytes()
        except OSError:
            return b""

    monkeypatch.setattr(ec.os, "listdir", listdir)
    monkeypatch.setattr(ec.os, "readlink", readlink)
    monkeypatch.setattr(ec, "_ler_do_proc", ler)
    monkeypatch.setattr(ec.os, "getppid", lambda: PAI_DO_SERVICO)


def _mesa(quantos: int) -> list[str]:
    """Os nós de `quantos` controles: o hidraw é o mesmo nó no cabo e no rádio."""
    return [f"/dev/hidraw{n}" for n in range(quantos)]


@pytest.mark.parametrize("quantos", [1, 2, 3, 4])
def test_o_produto_com_o_no_aberto_nao_e_escritor_de_fora(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, quantos: int
) -> None:
    nos = _mesa(quantos)
    processos = {SERVICO: _processo(PYTHON, ["python", "/x/hefesto"], PAI_DO_SERVICO),
                 **PRODUTO}
    _proc_de_mentira(tmp_path, monkeypatch, processos, {pid: nos for pid in processos})

    assert ec.escritores_crus_alheios(nos, meu_pid=SERVICO) == {}


@pytest.mark.parametrize("quantos", [1, 2, 3, 4])
@pytest.mark.parametrize("de_fora", sorted(DE_FORA))
def test_o_programa_de_fora_segue_acusado_em_todo_no(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, quantos: int, de_fora: int
) -> None:
    """Inclusive o de fora com nome, pasta ou módulo parecidos com os do produto."""
    nos = _mesa(quantos)
    processos = {SERVICO: _processo(PYTHON, ["python", "/x/hefesto"], PAI_DO_SERVICO),
                 **PRODUTO, de_fora: DE_FORA[de_fora]}
    _proc_de_mentira(tmp_path, monkeypatch, processos, {pid: nos for pid in processos})

    assert ec.escritores_crus_alheios(nos, meu_pid=SERVICO) == {no: [de_fora] for no in nos}


def test_o_programa_que_o_proprio_servico_roda_e_do_produto(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A ferramenta pelo mesmo lançador do serviço (o `doctor`, por exemplo)."""
    lancador = str(tmp_path / "bin" / "hefesto-dualsense4unix")
    processos = {
        SERVICO: _processo(PYTHON, ["python", lancador, "daemon", "start"], PAI_DO_SERVICO),
        4200: _processo(PYTHON, ["python", lancador, "doctor"], SESSAO),
    }
    _proc_de_mentira(tmp_path, monkeypatch, processos, {4200: ["/dev/hidraw0"]})

    assert ec.escritores_crus_alheios(["/dev/hidraw0"], meu_pid=SERVICO) == {}


def test_a_ascendencia_se_le_no_proc_de_verdade() -> None:
    """O filho deste processo é do «serviço» que é este processo; de outro serviço, não."""
    filho = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        assert ec.processo_do_produto(filho.pid, servico=os.getpid()) is True
        assert ec.processo_do_produto(filho.pid, servico=filho.pid + 999_999) is False
    finally:
        filho.kill()
        filho.wait(5)
