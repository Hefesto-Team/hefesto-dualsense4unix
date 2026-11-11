"""O-FIO-DE-FUNDO-NAO-SOBREVIVE-AO-TESTE-01: o fio que a interface solta morre com o teste.

A parte 07 da suíte inteira morreu pelo sinal 11 (11/11/2026): o fio `radio-<chave>` corria em C
(`libudev`, `getenv`) quando o teste seguinte trocou o `os.environ`. A fixture de
`tests/conftest.py` junta os fios que `fios.soltar` registra, antes da volta do `monkeypatch`, e
reprova o teste cujo fio passa do prazo. A sessão interna abaixo é uma sessão de pytest inteira,
com o `conftest` como plugin.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import textwrap
import threading
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.interface.pacotes import fios

RAIZ = Path(__file__).resolve().parents[2]


def test_o_registro_lista_o_fio_que_corre_e_esquece_o_que_acabou() -> None:
    solto = threading.Event()
    fio = fios.soltar("fio-da-regua", solto.wait)
    try:
        assert fio in fios.vivos()
    finally:
        solto.set()
        fio.join(5)
    assert fio not in fios.vivos()


def test_o_fio_de_duble_sem_referencia_fraca_nao_derruba_o_soltar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _SemReferenciaFraca:
        __slots__ = ("alvo",)

        def __init__(self, target: Any, args: Any, name: str, daemon: bool) -> None:
            self.alvo = target

        def start(self) -> None:
            self.alvo()

    monkeypatch.setattr(threading, "Thread", _SemReferenciaFraca)
    chamado: list[int] = []

    fios.soltar("fio-de-mentira", lambda: chamado.append(1))

    assert chamado == [1]
    assert fios.vivos() == []


_DENTRO = textwrap.dedent('''
    import os, pathlib, threading, time

    import pytest

    from tests import conftest
    from hefesto_dualsense4unix.interface.pacotes import fios

    conftest._PRAZO_DOS_FIOS_S = 0.6
    SAIDA = pathlib.Path(os.environ["HEFESTO_SAIDA"])


    def test_fio_que_acaba_a_tempo():
        fios.soltar("fio-curto", time.sleep, 0.1)


    def test_fio_que_ainda_ve_o_ambiente_do_teste(monkeypatch):
        monkeypatch.setenv("FDF_MARCA", "do-teste")

        def olhar():
            time.sleep(0.3)
            SAIDA.write_text(os.environ.get("FDF_MARCA", "sumiu"))

        fios.soltar("fio-que-olha", olhar)


    def test_fio_que_passa_do_prazo():
        fios.soltar("fio-dorminhoco", time.sleep, 3)
''')


def _sessao_interna(tmp_path: Path) -> tuple[str, Path]:
    lar = tmp_path / "lar"
    lar.mkdir()
    teste = tmp_path / "test_dentro.py"
    teste.write_text(_DENTRO, encoding="utf-8")
    saida = tmp_path / "o-que-o-fio-viu.txt"
    env = {
        "HOME": str(lar), "PATH": os.environ["PATH"], "PYTHONPATH": str(RAIZ / "src"),
        "HEFESTO_SAIDA": str(saida), "TMPDIR": os.environ.get("TMPDIR", "/tmp"),
    }
    feito = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "tests.conftest", "-p", "no:cacheprovider",
         "--rootdir", str(tmp_path), "-q", "-rA", str(teste)],
        cwd=RAIZ, env=env, capture_output=True, text=True, timeout=120, check=False)
    return feito.stdout + feito.stderr, saida


def test_o_fio_solto_e_juntado_antes_da_volta_do_monkeypatch_e_o_que_passa_do_prazo_reprova(
    tmp_path: Path,
) -> None:
    texto, saida = _sessao_interna(tmp_path)

    assert saida.read_text() == "do-teste", texto
    assert re.search(r"PASSED \S*test_dentro\.py::test_fio_que_acaba_a_tempo", texto), texto
    assert re.search(
        r"PASSED \S*test_dentro\.py::test_fio_que_ainda_ve_o_ambiente_do_teste", texto), texto
    assert re.search(r"ERROR \S*test_dentro\.py::test_fio_que_passa_do_prazo", texto), texto
    assert "fio da interface vivo depois do teste" in texto and "fio-dorminhoco" in texto, texto
    assert "fio-curto" not in texto.split("fio da interface vivo", 1)[-1], texto
