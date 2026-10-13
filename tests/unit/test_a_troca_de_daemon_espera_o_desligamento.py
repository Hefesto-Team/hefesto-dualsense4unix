"""A-TROCA-DE-DAEMON-ESPERA-O-DESLIGAMENTO-INTEIRO-01 — um prazo só.

O systemd espera o desligamento do daemon por 45 s (`TimeoutStopSec`), e a troca
de instância esperava 2 s antes do SIGKILL: um terço dos desligamentos reais
passava de 2 s, e o SIGKILL chegava antes de o controle voltar ao Linux e de o
som ser recolhido. Agora o prazo é um só (`PRAZO_DO_DESLIGAMENTO_S`).
"""
from __future__ import annotations

import importlib
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from hefesto_dualsense4unix.utils import single_instance

UNIT = Path(__file__).resolve().parents[2] / "assets" / "hefesto-dualsense4unix.service"

#: O desligamento lento: o SIGTERM só é atendido 3 s depois, e a saída é limpa (código 0).
DESLIGAMENTO_LENTO_S = 3.0

_FILHO_QUE_DESLIGA_DEVAGAR = (
    "import signal, sys, time\n"
    "from hefesto_dualsense4unix.utils import single_instance\n"
    "def _desliga(*_):\n"
    f"    time.sleep({DESLIGAMENTO_LENTO_S})\n"
    "    sys.exit(0)\n"
    "signal.signal(signal.SIGTERM, _desliga)\n"
    "single_instance.acquire_or_takeover(sys.argv[1])\n"
    "time.sleep(60)\n"
)


@pytest.fixture
def runtime_isolado(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Os pid files num berço do teste, nunca no runtime de quem roda."""
    berco = tmp_path / "runtime"
    berco.mkdir()
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(berco))
    from hefesto_dualsense4unix.utils import xdg_paths

    importlib.reload(xdg_paths)
    importlib.reload(single_instance)
    assert xdg_paths.runtime_dir().parent == berco
    return berco


def test_o_predecessor_que_desliga_devagar_sai_limpo_e_nao_leva_sigkill(
    runtime_isolado: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(single_instance, "_is_hefesto_dualsense4unix_process", lambda pid: True)
    pid_file = runtime_isolado / "hefesto-dualsense4unix" / "daemon.pid"
    filho = subprocess.Popen([sys.executable, "-c", _FILHO_QUE_DESLIGA_DEVAGAR, "daemon"])
    try:
        limite = time.monotonic() + 20
        while not (pid_file.exists() and pid_file.read_text().strip() == str(filho.pid)):
            assert filho.poll() is None, f"o filho saiu antes do lock ({filho.returncode})"
            assert time.monotonic() < limite, "o filho não escreveu o pid file"
            time.sleep(0.05)

        inicio = time.monotonic()
        novo = single_instance.acquire_or_takeover("daemon")
        espera = time.monotonic() - inicio

        assert novo == os.getpid()
        codigo = filho.wait(timeout=10)
        assert codigo == 0, (
            f"o predecessor devia terminar o desligamento e sair limpo, saiu com {codigo} "
            f"(SIGKILL = {-signal.SIGKILL})"
        )
        assert espera >= DESLIGAMENTO_LENTO_S - 0.5, "a troca não esperou o desligamento"
        assert pid_file.read_text().strip() == str(novo)
    finally:
        if filho.poll() is None:
            filho.kill()
        filho.wait(timeout=5)
        single_instance.release("daemon")


def test_o_prazo_da_troca_e_o_timeout_stop_da_unit() -> None:
    texto = UNIT.read_text(encoding="utf-8")
    achados = re.findall(r"^TimeoutStopSec=(\d+)\s*$", texto, re.M)
    assert len(achados) == 1, "a unit precisa declarar o TimeoutStopSec uma vez"
    assert float(achados[0]) == single_instance.PRAZO_DO_DESLIGAMENTO_S
