"""A tela de mentira só se adota quando o ``Xvfb`` que segura o lock e escuta é o deste processo."""

from __future__ import annotations

import json
import os
import shutil
import socket
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


_FALSO_XVFB = r"""
import os, socket, sys, time
from pathlib import Path
Path("/tmp/.X80-lock").write_text(f"{os.getpid():>10}\n")
time.sleep(float(sys.argv[1]))
if sys.argv[2] == "escuta":
    tela = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    tela.bind("\0/tmp/.X11-unix/X80")
    tela.listen()
    time.sleep(60)
"""

_CONFERENCIA = r"""
import json, socket, subprocess, sys, time
from hefesto_dualsense4unix.utils import tela_de_mentira as t
alheio = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
if sys.argv[3] == "alheio":
    alheio.bind("\0/tmp/.X11-unix/X80")
    alheio.listen()
inicio = time.monotonic()
proc = subprocess.Popen([sys.executable, "-c", sys.argv[1], sys.argv[2], sys.argv[3]])
adotou = t._a_tela_e_deste_xvfb(proc, 80)
espera = time.monotonic() - inicio
t._encerrar(proc)
print(json.dumps({"adotou": adotou, "espera": espera}))
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


def _correr(*argumentos: str) -> dict[str, object]:
    ambiente = {
        chave: valor for chave, valor in os.environ.items()
        if chave not in {"HEFESTO_NA_TELA", "WAYLAND_DISPLAY", "TMPDIR"}
    }
    ambiente.update({"DISPLAY": ":0", "TMPDIR": "/tmp", "PYTHONPATH": str(_SRC)})
    feito = subprocess.run(
        [*_caixa(), sys.executable, "-c", *argumentos],
        capture_output=True, text=True, env=ambiente, timeout=60,
    )
    assert feito.returncode == 0, feito.stderr[-2000:]
    medida: dict[str, object] = json.loads(feito.stdout.strip().splitlines()[-1])
    return medida


def test_o_xvfb_que_perdeu_a_corrida_nao_adota_a_tela_do_vizinho() -> None:
    """Prova da D-3110-A-TELA-DE-MENTIRA-SO-SE-ADOTA-QUANDO-E-DESTE-PROCESSO.

    O vizinho pega o ``:80`` depois da conferência do socket e antes do nosso
    ``Xvfb`` firmar o lock; o nosso fica vivo na espera do lock temporário. Adotar
    o ``:80`` é morrer calado quando o dono derruba a tela dele. MORDE: com a
    espera só pelo caminho do socket, a tela volta ``:80`` e o dono é o vizinho."""
    medida = _correr(_CORRIDA, _VIZINHO, "0.3")
    assert medida["tela"] == ":81", medida
    assert medida["dono"] == medida["nosso"], medida
    assert medida["dono"] != medida["vizinho"], medida


def test_o_xvfb_que_perdeu_a_corrida_nao_fica_orfao() -> None:
    """O ``Xvfb`` que perdeu o ``:80`` sai pelas mãos de quem o criou, e o da tela
    adotada sai no ``derrubar``: nenhum fica vivo na caixa."""
    medida = _correr(_CORRIDA, _VIZINHO, "0.3")
    assert medida["sobras"] == [], medida


def test_o_lock_do_proprio_xvfb_so_adota_quando_ele_ja_escuta_a_tela() -> None:
    """O lock nasce antes do socket: adotar só pelo lock aponta o GTK para uma tela
    que ainda não atende. MORDE: sem a conferência do socket, a espera cai a zero."""
    medida = _correr(_CONFERENCIA, _FALSO_XVFB, "0.8", "escuta")
    assert medida["adotou"] is True, medida
    assert float(str(medida["espera"])) >= 0.8, medida


def test_o_lock_do_proprio_xvfb_nao_adota_o_socket_de_outro_processo() -> None:
    """Com o ``/tmp`` próprio e a rede dividida, o lock é nosso e o socket abstrato
    da tela é de outro processo, e é a ele que o GTK se liga primeiro. MORDE: sem a
    conferência do socket, a tela alheia se adota."""
    medida = _correr(_CONFERENCIA, _FALSO_XVFB, "1.0", "alheio")
    assert medida["adotou"] is False, medida


_DERRUBA_A_TELA_COM_O_BARRAMENTO_ABERTO = r"""
import os, time
from gi.repository import Gio, GLib
from hefesto_dualsense4unix.utils import tela_de_mentira as t
t.garantir_tela_de_mentira(anunciar=False)
try:
    Gio.bus_get_sync(Gio.BusType.SESSION, None)
except GLib.Error:
    pass
t.derrubar_tela_de_mentira()
contexto, fim = GLib.MainContext.default(), time.monotonic() + 2
while time.monotonic() < fim:
    contexto.iteration(False)
    time.sleep(0.01)
print(os.environ.get("DBUS_SESSION_BUS_ADDRESS"))
"""


_SO_O_ENDERECO = r"""
import os
from hefesto_dualsense4unix.utils import tela_de_mentira as t
t.garantir_tela_de_mentira(anunciar=False)
t.derrubar_tela_de_mentira()
print(os.environ.get("DBUS_SESSION_BUS_ADDRESS"))
"""


def _derrubar_a_tela(
    tmp_path: Path, sonda: str = _DERRUBA_A_TELA_COM_O_BARRAMENTO_ABERTO, **ambiente: str
) -> subprocess.CompletedProcess[str]:
    if shutil.which("Xvfb") is None:
        pytest.skip("sem `Xvfb` não há tela de mentira a derrubar")
    limpo = {
        chave: valor for chave, valor in os.environ.items()
        if chave not in {"HEFESTO_NA_TELA", "WAYLAND_DISPLAY", "DBUS_SESSION_BUS_ADDRESS"}
    }
    limpo.update({"DISPLAY": ":0", "HOME": str(tmp_path), "XDG_RUNTIME_DIR": str(tmp_path),
                  "PYTHONPATH": str(_SRC), **ambiente})
    return subprocess.run([sys.executable, "-c", sonda],
                          env=limpo, capture_output=True, text=True, timeout=60)


def test_derrubar_a_tela_nao_mata_quem_nao_tinha_barramento(tmp_path: Path) -> None:
    """Sem barramento de sessão, a GLib o sobe pelo `dbus-launch`, preso a esta tela, e a conexão
    dele nasce com `exit-on-close`: a tela cai, o barramento cai, e a GDBus faz `raise(SIGTERM)`.

    Medido por `strace` em 06/11/2026 no contêiner 26.04: `kill(xvfb)`, 1 ms depois
    `tgkill(pytest, gdbus, SIGTERM)`, e o `test_a_tela_nao_samba` morria com 143 depois do sumário.
    O sinal sai do laço principal da GLib: sem iterar o contexto, a conexão morta passa calada.
    MORDIDA: tirar o `disabled:` de `garantir_tela_de_mentira` reprova aqui pelo endereço. A morte
    mede-se fora do pytest: no contêiner, a sonda sai com 143, e o `test_a_tela_nao_samba` pelo
    `rodar-a-suite.sh --lote` diz `MORREU PELO SINAL 15` sem o `disabled:` e fecha verde com ele."""
    from tests.conftest import exigir_gi_real

    exigir_gi_real("a sonda abre a conexão da GDBus")
    feito = _derrubar_a_tela(tmp_path)
    assert (feito.returncode, feito.stdout.strip()) == (0, "disabled:"), feito.stderr[-400:]


def test_o_barramento_que_ja_existe_fica(tmp_path: Path) -> None:
    from tests.conftest import exigir_gi_real

    exigir_gi_real("a sonda abre a conexão da GDBus")
    endereco = f"unix:path={tmp_path}/nenhum"
    feito = _derrubar_a_tela(tmp_path, DBUS_SESSION_BUS_ADDRESS=endereco)
    assert (feito.returncode, feito.stdout.strip()) == (0, endereco), feito.stderr[-400:]


def test_o_barramento_do_xdg_runtime_dir_fica(tmp_path: Path) -> None:
    """A sessão de `systemd --user` nem sempre exporta o endereço: a GLib acha o `bus` sozinha, e
    esse barramento não depende da tela. MORDIDA: voltar a olhar só o ambiente reprova."""
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as ouvinte:
        ouvinte.bind(str(tmp_path / "bus"))
        feito = _derrubar_a_tela(tmp_path, _SO_O_ENDERECO)
    assert (feito.returncode, feito.stdout.strip()) == (0, "None"), feito.stderr[-400:]


def test_um_arquivo_comum_no_lugar_do_socket_nao_e_barramento(tmp_path: Path) -> None:
    (tmp_path / "bus").write_text("", encoding="utf-8")
    feito = _derrubar_a_tela(tmp_path, _SO_O_ENDERECO)
    assert (feito.returncode, feito.stdout.strip()) == (0, "disabled:"), feito.stderr[-400:]
