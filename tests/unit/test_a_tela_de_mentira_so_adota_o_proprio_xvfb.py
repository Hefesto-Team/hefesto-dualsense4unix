"""A tela de mentira só se adota quando o ``Xvfb`` que segura o lock e escuta é o deste processo."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import hefesto_dualsense4unix

_SRC = Path(hefesto_dualsense4unix.__file__).resolve().parents[1]

_VIZINHO = r"""
import os, socket, sys, time
from pathlib import Path
time.sleep(float(sys.argv[1]))
Path("/tmp/.X80-lock").write_text(f"{os.getpid():>10}\n")
caminho = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
caminho.bind("/tmp/.X11-unix/X80")
caminho.listen()
abstrato = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
abstrato.bind("\0/tmp/.X11-unix/X80")
abstrato.listen()
Path("/tmp/.tX80-lock").unlink()
time.sleep(60)
"""

_CORRIDA = r"""
import json, os, subprocess, sys, time
from pathlib import Path
os.makedirs("/tmp/.X11-unix", mode=0o1777, exist_ok=True)
Path("/tmp/.tX80-lock").write_text("")
vizinho = subprocess.Popen([sys.executable, "-c", sys.argv[1], sys.argv[2]])
from hefesto_dualsense4unix.utils import tela_de_mentira as t
tela = t.garantir_tela_de_mentira(anunciar=False)
numero = (tela or ":")[1:]
lock = Path(f"/tmp/.X{numero}-lock")
dono = int(lock.read_text()) if lock.exists() else None
nosso = t._XVFB.pid if t._XVFB is not None else None
t.derrubar_tela_de_mentira()
vizinho.kill()
vizinho.wait()
sobras = []
for pasta in Path("/proc").iterdir():
    if pasta.name.isdigit():
        try:
            argv = (pasta / "cmdline").read_bytes().split(b"\0")
        except OSError:
            continue
        if argv and argv[0].endswith(b"Xvfb"):
            sobras.append(b" ".join(argv).decode())
print(json.dumps({"tela": tela, "dono": dono, "nosso": nosso,
                  "vizinho": vizinho.pid, "sobras": sobras}))
"""


def _caixa() -> list[str]:
    if shutil.which("bwrap") is None:
        pytest.skip("sem `bwrap` não há /tmp e rede próprios para a corrida")
    if shutil.which("Xvfb") is None:
        pytest.skip("sem `Xvfb` não há tela de mentira a disputar")
    caixa = [
        "bwrap", "--dev-bind", "/", "/", "--tmpfs", "/tmp",
        "--unshare-net", "--unshare-pid", "--proc", "/proc", "--die-with-parent",
    ]
    sonda = subprocess.run([*caixa, "/usr/bin/true"], capture_output=True, text=True)
    if sonda.returncode != 0:
        pytest.skip(f"o `bwrap` não abriu a caixa nesta máquina: {sonda.stderr.strip()[:120]}")
    return caixa


def _correr(atraso_do_vizinho: float) -> dict[str, object]:
    ambiente = {
        chave: valor for chave, valor in os.environ.items()
        if chave not in {"HEFESTO_NA_TELA", "WAYLAND_DISPLAY", "TMPDIR"}
    }
    ambiente.update({"DISPLAY": ":0", "TMPDIR": "/tmp", "PYTHONPATH": str(_SRC)})
    feito = subprocess.run(
        [*_caixa(), sys.executable, "-c", _CORRIDA, _VIZINHO, str(atraso_do_vizinho)],
        capture_output=True, text=True, env=ambiente, timeout=60,
    )
    assert feito.returncode == 0, feito.stderr[-2000:]
    medida: dict[str, object] = json.loads(feito.stdout.strip().splitlines()[-1])
    return medida


def test_o_xvfb_que_perdeu_a_corrida_nao_adota_a_tela_do_vizinho() -> None:
    """O vizinho pega o ``:80`` depois da conferência do socket e antes do nosso
    ``Xvfb`` firmar o lock; o nosso fica vivo na espera do lock temporário. Adotar
    o ``:80`` é morrer calado quando o dono derruba a tela dele. MORDE: com a
    espera só pelo caminho do socket, a tela volta ``:80`` e o dono é o vizinho."""
    medida = _correr(0.3)
    assert medida["tela"] == ":81", medida
    assert medida["dono"] == medida["nosso"], medida
    assert medida["dono"] != medida["vizinho"], medida


def test_o_xvfb_que_perdeu_a_corrida_nao_fica_orfao() -> None:
    """O ``Xvfb`` que perdeu o ``:80`` sai pelas mãos de quem o criou, e o da tela
    adotada sai no ``derrubar``: nenhum fica vivo na caixa."""
    medida = _correr(0.3)
    assert medida["sobras"] == [], medida
