"""A queda nativa do serviço deixa no stderr, que o diário recolhe, a pilha de cada fio."""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from hefesto_dualsense4unix.cli import cmd_doctor

_O_SERVICO_QUE_CAI = textwrap.dedent(
    """
    import os, signal, threading
    from hefesto_dualsense4unix.daemon import main

    def o_fio_da_subida(pronto):
        pronto.set()
        threading.Event().wait()

    def cair():
        pronto = threading.Event()
        fio = threading.Thread(target=o_fio_da_subida, args=(pronto,), name="subida")
        fio.start()
        pronto.wait()
        signal.pthread_kill(fio.ident, signal.SIGSEGV)
        threading.Event().wait(30)

    main.ajustar_a_vez_do_gil = cair
    main.run_daemon()
    """
)

_O_PROCESSO_LONGO = textwrap.dedent(
    """
    import faulthandler, sys
    from hefesto_dualsense4unix.utils.logging_config import get_logger
    get_logger("processo_longo")
    sys.stdout.write(str(faulthandler.is_enabled()))
    """
)


def _no_lar_de_mentira(tmp_path: Path) -> dict[str, str]:
    lar = tmp_path / "lar"
    ambiente = {
        chave: valor for chave, valor in os.environ.items()
        if chave not in {"PYTHONFAULTHANDLER", "PYTEST_CURRENT_TEST"}
    }
    ambiente.update(
        HOME=str(lar),
        XDG_CONFIG_HOME=str(lar / ".config"),
        XDG_STATE_HOME=str(lar / ".local/state"),
        XDG_DATA_HOME=str(lar / ".local/share"),
        XDG_CACHE_HOME=str(lar / ".cache"),
        XDG_RUNTIME_DIR=str(tmp_path / "run"),
        HEFESTO_DUALSENSE4UNIX_FAKE="1",
    )
    (tmp_path / "run").mkdir(mode=0o700)
    return ambiente


def test_a_queda_do_fio_da_subida_deixa_a_pilha_de_cada_fio(tmp_path: Path) -> None:
    """D-1911-A-QUEDA-NATIVA-DEIXA-A-PILHA: o SIGSEGV num fio sai com a pilha dos fios."""
    feito = subprocess.run(
        [sys.executable, "-c", _O_SERVICO_QUE_CAI],
        env=_no_lar_de_mentira(tmp_path), capture_output=True, text=True, timeout=60,
        check=False,
    )

    assert feito.returncode == -signal.SIGSEGV
    assert "Fatal Python error: Segmentation fault" in feito.stderr
    assert "in o_fio_da_subida" in feito.stderr
    assert "in cair" in feito.stderr
    assert "in run_daemon" in feito.stderr


def test_todo_processo_longo_da_casa_liga_a_pilha(tmp_path: Path) -> None:
    """D-1911-A-QUEDA-NATIVA-DEIXA-A-PILHA: o processo que configura o diário liga a pilha."""
    feito = subprocess.run(
        [sys.executable, "-c", _O_PROCESSO_LONGO],
        env=_no_lar_de_mentira(tmp_path), capture_output=True, text=True, timeout=60,
        check=False,
    )

    assert feito.stdout == "True", feito.stderr


@pytest.mark.parametrize(
    ("saida", "esperado"),
    [
        ("0\n", ("[ OK ]", "o serviço não reiniciou sozinho")),
        ("3\n", ("[INFO]", "o serviço reiniciou sozinho 3 vezes")),
        ("1\n", ("[INFO]", "o serviço reiniciou sozinho 1 vez")),
        ("", None),
        ("[not set]\n", None),
    ],
)
def test_o_doctor_conta_as_voltas_sozinho(
    monkeypatch: pytest.MonkeyPatch, saida: str, esperado: tuple[str, str] | None
) -> None:
    """D-1911-A-QUEDA-NATIVA-DEIXA-A-PILHA: o doctor diz o NRestarts da unit do serviço."""
    pedidos: list[list[str]] = []

    def systemctl(argv: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        pedidos.append(argv)
        return subprocess.CompletedProcess(argv, 0, saida, "")

    monkeypatch.setattr(cmd_doctor.subprocess, "run", systemctl)

    assert cmd_doctor._linha_das_voltas_sozinho() == esperado
    assert pedidos == [["systemctl", "--user", "show", "hefesto-dualsense4unix.service",
                        "--property=NRestarts", "--value"]]
