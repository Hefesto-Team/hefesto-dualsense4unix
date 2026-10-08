"""O restaurador do lançamento solta quando o jogo acaba.

O-RESTAURADOR-DO-LANCAMENTO-SOLTA-QUANDO-O-JOGO-ACABA-01. Na Steam, o `$$` do
`hefesto-launch` vira o reaper do `%command%`, que espera todo descendente; o
restaurador que mora na árvore dele espera o reaper, e os dois ficam presos. O
reaper de mentira daqui é subreaper e espera até o `ECHILD`, como o de verdade;
o `systemd-run` de mentira entrega o comando a um processo DESTE teste, fora da
árvore do reaper, com o ambiente mínimo do gerente de usuário (nada do ambiente
do jogo chega a ele).
"""
from __future__ import annotations

import contextlib
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
LANCADOR = RAIZ / "assets" / "hefesto-launch.sh"
PERIODO = 0.5

_REAPER = """\
import ctypes, os, sys, time
ctypes.CDLL(None, use_errno=True).prctl(36, 1, 0, 0, 0)  # PR_SET_CHILD_SUBREAPER
jogo = os.fork()
if jogo == 0:
    os.execvp(sys.argv[2], sys.argv[2:])
marca = sys.argv[1]
while True:
    try:
        pid, _ = os.wait()
    except ChildProcessError:
        break
    if pid == jogo:
        with open(marca, "w") as f:
            f.write(repr(time.time()))
"""


def _exec(caminho: Path, corpo: str) -> None:
    caminho.write_text(corpo, encoding="utf-8")
    caminho.chmod(0o755)


class Bancada:
    """Os dublês do lançamento: perfil, placa, sudo e o `systemd-run`."""

    def __init__(self, base: Path, *, com_systemd_run: bool = True) -> None:
        self.base = base
        self.bin = base / "bin"
        self.bin.mkdir()
        self.log = base / "chamadas.log"
        self.perfil = base / "perfil"
        self.perfil.write_text("balanced\n", encoding="utf-8")
        self.fila = base / "fila"
        self.fila.mkdir()
        self.marca = base / "jogo-acabou"
        self.filhos: list[subprocess.Popen[bytes]] = []
        _exec(self.bin / "system76-power", (
            "#!/bin/sh\n"
            f'if [ "$#" -ge 2 ]; then echo "perfil $2" >> "{self.log}"; '
            f'printf "%s\\n" "$2" > "{self.perfil}"; exit 0; fi\n'
            f'printf "Power Profile: %s\\n" "$(cat "{self.perfil}")"\n'))
        _exec(self.bin / "sudo", '#!/bin/sh\n[ "$1" = "-n" ] && shift\nexec "$@"\n')
        self.placa = base / "placa.sh"
        _exec(self.placa, f'#!/bin/sh\nread pid\necho "placa $1 $pid" >> "{self.log}"\n')
        if com_systemd_run:
            _exec(self.bin / "systemd-run", (
                "#!/bin/sh\n"
                'while [ "$#" -gt 0 ]; do case "$1" in --) shift; break ;; '
                "--*) shift ;; *) break ;; esac; done\n"
                f'f="{self.fila}/$$"\n'
                'for a in "$@"; do printf "%s\\0" "$a"; done > "$f.tmp"\n'
                'mv "$f.tmp" "$f"\n'))

    def ambiente(self) -> dict[str, str]:
        casa = self.base / "casa"
        (casa / ".config").mkdir(parents=True, exist_ok=True)
        assert not str(casa).startswith("/home/"), "o lar de mentira caiu numa casa de verdade"
        return {
            "HOME": str(casa),
            "XDG_CONFIG_HOME": str(casa / ".config"),
            "XDG_STATE_HOME": str(self.base / "estado"),
            "XDG_RUNTIME_DIR": str(self.base / "runtime"),
            "PATH": f"{self.bin}:/usr/bin:/bin",
            "HEFESTO_PLACA_ACORDADA": str(self.placa),
            "HEFESTO_GM_POLL_SECS": str(PERIODO),
            "SteamAppId": "3621330",
        }

    def gerente(self, parar: threading.Event) -> None:
        """O gerente de usuário de mentira: roda cada unidade fora do reaper."""
        while not parar.is_set():
            for pedido in sorted(self.fila.glob("[0-9]*")):
                if pedido.suffix:
                    continue
                argv = pedido.read_bytes().split(b"\0")[:-1]
                pedido.unlink()
                self.filhos.append(subprocess.Popen(
                    argv, env={"PATH": "/usr/bin:/bin"}, stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    start_new_session=True))
            time.sleep(0.05)

    def chamadas(self) -> list[str]:
        return self.log.read_text(encoding="utf-8").splitlines() if self.log.exists() else []

    def esperar(self, linha: str, prazo: float = 10.0) -> list[str]:
        fim = time.monotonic() + prazo
        while time.monotonic() < fim and linha not in self.chamadas():
            time.sleep(0.05)
        return self.chamadas()


@pytest.fixture
def bancada(tmp_path: Path) -> Iterator[Bancada]:
    b = Bancada(tmp_path)
    parar = threading.Event()
    fio = threading.Thread(target=b.gerente, args=(parar,), daemon=True)
    fio.start()
    yield b
    parar.set()
    fio.join(timeout=5)
    for filho in b.filhos:
        if filho.poll() is None:
            os.killpg(filho.pid, signal.SIGKILL)
            filho.wait()


def _lancar_pela_steam(b: Bancada) -> subprocess.Popen[bytes]:
    reaper = b.base / "reaper.py"
    reaper.write_text(_REAPER, encoding="utf-8")
    return subprocess.Popen(
        ["sh", str(LANCADOR), sys.executable, str(reaper), str(b.marca), "sleep", "1"],
        env=b.ambiente(), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, start_new_session=True)


def test_o_reaper_sai_com_o_jogo_e_a_devolucao_chega(bancada: Bancada) -> None:
    lancamento = _lancar_pela_steam(bancada)
    with contextlib.suppress(subprocess.TimeoutExpired):
        lancamento.wait(timeout=1 + 3 * PERIODO + 10)
    fim = time.time()
    if lancamento.poll() is None:
        os.killpg(lancamento.pid, signal.SIGKILL)
        lancamento.wait()
        pytest.fail("o lançamento não terminou: o restaurador está preso na árvore do reaper")
    jogo_acabou = float(bancada.marca.read_text(encoding="utf-8"))
    assert fim - jogo_acabou < 3 * PERIODO, (
        f"o reaper durou {fim - jogo_acabou:.2f} s depois do jogo")
    bancada.esperar(f"placa devolver {lancamento.pid}")
    chamadas = bancada.esperar("perfil balanced")
    assert f"placa acordar {lancamento.pid}" in chamadas, chamadas
    assert f"placa devolver {lancamento.pid}" in chamadas, chamadas
    assert chamadas.index("perfil performance") < chamadas.index("perfil balanced"), chamadas
    assert bancada.perfil.read_text(encoding="utf-8").strip() == "balanced"


def test_sem_systemd_run_nao_troca_nem_acorda(tmp_path: Path) -> None:
    b = Bancada(tmp_path, com_systemd_run=False)
    restrito = tmp_path / "restrito"
    restrito.mkdir()
    for ferramenta in ("sh", "env", "date", "mkdir", "sed", "head", "tr", "cat", "sleep", "true"):
        real = shutil.which(ferramenta)
        assert real is not None, ferramenta
        (restrito / ferramenta).symlink_to(real)
    ambiente = b.ambiente()
    ambiente["PATH"] = f"{b.bin}:{restrito}"
    saida = subprocess.run(["sh", str(LANCADOR), "true"], env=ambiente, capture_output=True,
                           text=True, timeout=60, check=False)
    assert saida.returncode == 0, saida.stderr
    time.sleep(3 * PERIODO)
    assert b.chamadas() == [], "trocou sem ter quem devolva"


def test_o_systemd_run_que_falha_desfaz_na_hora(tmp_path: Path) -> None:
    b = Bancada(tmp_path)
    _exec(b.bin / "systemd-run", "#!/bin/sh\nexit 1\n")
    saida = subprocess.run(["sh", str(LANCADOR), "true"], env=b.ambiente(),
                           capture_output=True, text=True, timeout=60, check=False)
    assert saida.returncode == 0, saida.stderr
    chamadas = b.chamadas()
    assert chamadas[:2] == ["perfil performance", "perfil balanced"], chamadas
    assert [c.split()[1] for c in chamadas[2:]] == ["acordar", "devolver"], chamadas
    assert b.perfil.read_text(encoding="utf-8").strip() == "balanced"
