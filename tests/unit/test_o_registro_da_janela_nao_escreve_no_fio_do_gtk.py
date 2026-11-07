"""O-REGISTRO-DA-JANELA-NAO-ESCREVE-NO-FIO-DO-GTK-01 — as réguas.

Todo ``print`` da janela só enfileira, e o disco é de um fio próprio. Com o disco preso 2 s, o
``print`` volta em menos de 8 ms, a linha chega quando o disco volta, e nada se perde na saída.
MORDIDA: ``diario_da_janela`` devolver o arquivo direto, ou ``_FilaDoDiario.write`` gravar no
fio de quem chama, reprova a primeira régua.
"""
from __future__ import annotations

import io
import os
import re
import stat
import subprocess
import sys
import textwrap
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.interface import abrir as ab

RAIZ = Path(__file__).resolve().parents[2]
_HORA = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?")
_TIQUE_S = 0.008


class _Arquivo:
    """O arquivo de verdade, com o ``write`` que passa pelo disco dublado."""

    def __init__(self, real: Any, ao_escrever: Callable[[], None]) -> None:
        self.real = real
        self.ao_escrever = ao_escrever

    def write(self, dados: Any) -> int:
        self.ao_escrever()
        return self.real.write(dados)

    def __getattr__(self, nome: str) -> Any:
        return getattr(self.real, nome)


@pytest.fixture
def estado(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    monkeypatch.setattr(sys, "stderr", io.StringIO())
    return tmp_path / "hefesto-dualsense4unix"


@pytest.fixture
def disco(monkeypatch: pytest.MonkeyPatch) -> list[Callable[[], None]]:
    """O que o ``write`` do ``interface.log`` faz antes de escrever."""
    atraso: list[Callable[[], None]] = [lambda: None]
    abrir = Path.open

    def _open(self: Path, mode: str = "r", *a: Any, **k: Any) -> Any:
        real = abrir(self, mode, *a, **k)
        if self.name == "interface.log" and mode.startswith("a"):
            return _Arquivo(real, lambda: atraso[0]())
        return real

    monkeypatch.setattr(Path, "open", _open)
    return atraso


@pytest.fixture
def fluxo(estado: Path, disco: list[Callable[[], None]]) -> Iterator[Any]:
    aberto = ab.diario_da_janela()
    assert aberto is not None
    yield aberto
    aberto.close()


def _ler(estado: Path) -> list[str]:
    return (estado / "interface.log").read_text(encoding="utf-8").splitlines()


def _escoar(fluxo: Any, prazo: float = 6.0) -> None:
    fluxo.flush()
    assert fluxo.buffer.raw.escoar(prazo), "a fila não chegou ao disco"


def test_o_print_nao_espera_o_disco_preso_e_a_linha_chega_depois(
    estado: Path, disco: list[Callable[[], None]], fluxo: Any,
) -> None:
    disco[0] = lambda: time.sleep(2.0)
    tempos: list[float] = []
    for i in range(400):
        t0 = time.perf_counter()
        print(f"tique lento {i}", file=fluxo)
        tempos.append(time.perf_counter() - t0)
        assert tempos[-1] < 0.5, f"o print {i} esperou o disco: {tempos[-1]:.3f} s"
    tempos.sort()
    assert tempos[int(len(tempos) * 0.99)] < _TIQUE_S, tempos[-5:]

    assert not (estado / "interface.log").stat().st_size, "o disco não estava preso"
    _escoar(fluxo)
    linhas = _ler(estado)
    assert [x.split(" ", 1)[1] for x in linhas] == [f"tique lento {i}" for i in range(400)]


def test_toda_linha_tem_uma_hora_so(estado: Path, fluxo: Any) -> None:
    print("[gesto] 02-controles.html · salvar → aplicado", file=fluxo)
    print("[gesto falhou] 04-iluminacao.html · cor: recusado", file=fluxo)
    print("2026-11-06T19:48:34.123456 [info     ] profile_salvo  arquivo=x", file=fluxo)
    print("\n===== a janela abriu em 2026-11-06T19:48:34 =====", file=fluxo)
    print("  duas\n  linhas", file=fluxo)
    _escoar(fluxo)

    linhas = _ler(estado)
    assert linhas[3] == "", "a linha em branco fica em branco"
    for linha in (x for x in linhas if x):
        assert _HORA.match(linha), linha
        assert not _HORA.match(linha.split(" ", 1)[1]), f"hora dupla: {linha}"
    assert linhas[2] == "2026-11-06T19:48:34.123456 [info     ] profile_salvo  arquivo=x"
    assert linhas[0].split(" ", 1)[1].startswith("[gesto] 02-controles")
    assert linhas[1].split(" ", 1)[1].startswith("[gesto falhou] 04-iluminacao")


def test_o_pedaco_sem_quebra_junta_ate_a_quebra(estado: Path, fluxo: Any) -> None:
    print("Traceback ", end="", file=fluxo)
    fluxo.flush()
    print("(most recent ", end="", file=fluxo, flush=True)
    print("call last):", file=fluxo)
    print("sem quebra no fim", end="", file=fluxo)
    _escoar(fluxo)

    linhas = [x.split(" ", 1)[1] for x in _ler(estado)]
    assert linhas == ["Traceback (most recent call last):", "sem quebra no fim"]


def test_a_fila_tem_teto_e_o_diario_conta_quantas_sairam(
    estado: Path, disco: list[Callable[[], None]], fluxo: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ab, "TETO_DA_FILA_DO_DIARIO", 4096)
    solta = threading.Event()
    disco[0] = lambda: solta.wait(6.0) and None
    print("a primeira", file=fluxo)
    time.sleep(0.05)
    total = 300
    for i in range(total):
        print(f"{i:04d} " + "." * 74, file=fluxo)
    solta.set()
    _escoar(fluxo)

    linhas = [x.split(" ", 1)[1] for x in _ler(estado)]
    assert linhas[0] == "a primeira"
    numeros = [int(x[:4]) for x in linhas[2:]]
    perdidas = total - len(numeros)
    assert perdidas > 0
    assert linhas[1] == f"({perdidas} linhas saíram: o disco não acompanhou)"
    assert numeros == list(range(perdidas, total)), "saiu outra além da mais velha"


_FILHO = textwrap.dedent(
    """
    import pathlib, sys, time
    from hefesto_dualsense4unix.interface import abrir as ab

    abrir = pathlib.Path.open
    class Lento:
        def __init__(self, real):
            self.real = real
        def write(self, dados):
            time.sleep(0.4)
            return self.real.write(dados)
        def __getattr__(self, nome):
            return getattr(self.real, nome)
    pathlib.Path.open = lambda self, mode="r", *a, **k: (
        Lento(abrir(self, mode, *a, **k)) if mode == "ab" else abrir(self, mode, *a, **k))
    fluxo = ab.diario_da_janela()
    sys.stdout = sys.stderr = fluxo
    for i in range(3000):
        print(f"linha {i}")
    {fim}
    """
)


@pytest.mark.parametrize("fim,final", [
    ('print("a última linha")', "a última linha"),
    ('print("sem quebra", end="")', "sem quebra"),
    ('raise RuntimeError("caiu no fim")', "RuntimeError: caiu no fim"),
])
def test_sair_com_a_fila_cheia_nao_perde_a_ultima_linha(
    tmp_path: Path, fim: str, final: str,
) -> None:
    ambiente = {**os.environ, "XDG_STATE_HOME": str(tmp_path), "PYTHONPATH": str(RAIZ / "src"),
                "PYTHONDONTWRITEBYTECODE": "1"}
    proc = subprocess.run(
        [sys.executable, "-c", _FILHO.replace("{fim}", fim)], env=ambiente,
        stdin=subprocess.DEVNULL, capture_output=True, timeout=30)
    assert proc.stdout == b"", proc.stdout
    linhas = _ler(tmp_path / "hefesto-dualsense4unix")
    assert linhas[-1].split(" ", 1)[1] == final, linhas[-3:]


def test_sair_com_o_disco_preso_nao_segura_o_processo(tmp_path: Path) -> None:
    filho = textwrap.dedent(
        """
        import pathlib, sys, time
        from hefesto_dualsense4unix.interface import abrir as ab
        ab.ESPERA_DO_DIARIO_NA_SAIDA_S = 0.2
        abrir = pathlib.Path.open
        class Preso:
            def __init__(self, real):
                self.real = real
            def write(self, dados):
                time.sleep(60)
            def __getattr__(self, nome):
                return getattr(self.real, nome)
        pathlib.Path.open = lambda self, mode="r", *a, **k: (
            Preso(abrir(self, mode, *a, **k)) if mode == "ab" else abrir(self, mode, *a, **k))
        fluxo = ab.diario_da_janela()
        print("presa", file=fluxo)
        """
    )
    ambiente = {**os.environ, "XDG_STATE_HOME": str(tmp_path), "PYTHONPATH": str(RAIZ / "src"),
                "PYTHONDONTWRITEBYTECODE": "1"}
    t0 = time.monotonic()
    subprocess.run([sys.executable, "-c", filho], env=ambiente, stdin=subprocess.DEVNULL,
                   capture_output=True, timeout=30, check=True)
    assert time.monotonic() - t0 < 10.0


def test_com_terminal_devolve_none(monkeypatch: pytest.MonkeyPatch) -> None:
    class Terminal(io.StringIO):
        def isatty(self) -> bool:
            return True

    monkeypatch.setattr(sys, "stderr", Terminal())
    assert ab.diario_da_janela() is None


def test_o_fluxo_e_um_arquivo_para_quem_pede_o_descritor(estado: Path, fluxo: Any) -> None:
    subprocess.run(["sh", "-c", "echo do filho"], stdout=fluxo, check=True)
    print("do pai", file=fluxo)
    _escoar(fluxo)
    assert fluxo.isatty() is False
    linhas = _ler(estado)
    assert "do filho" in linhas
    assert linhas[-1].endswith(" do pai")


def test_a_rotacao_e_o_teto_seguem_iguais(estado: Path, disco: list[Callable[[], None]]) -> None:
    estado.mkdir(parents=True, exist_ok=True)
    grande = estado / "interface.log"
    grande.write_bytes(b"velha\n" * (ab.TETO_DO_DIARIO // 6 + 1))
    tamanho = grande.stat().st_size

    aberto = ab.diario_da_janela()

    assert aberto is not None
    print("nova", file=aberto)
    aberto.close()
    assert (estado / "interface.log.1").stat().st_size == tamanho
    assert [x.split(" ", 1)[1] for x in _ler(estado)] == ["nova"]
    assert stat.S_ISREG(grande.stat().st_mode)


@pytest.mark.parametrize("de_pe", [
    ("P1", "P2", "P3", "P4"),
    ("P3",),
    ("P2", "P4"),
])
def test_os_gestos_de_cada_jogador_saem_com_hora(
    estado: Path, fluxo: Any, de_pe: tuple[str, ...],
) -> None:
    """O diário não olha controle, transporte nem modo: a linha é a do gesto de quem apertou."""
    for jogador in de_pe:
        print(f"[gesto] 08-conexoes.html · {jogador} → aplicado", file=fluxo)
    _escoar(fluxo)
    linhas = _ler(estado)
    assert [x.split(" ", 1)[1] for x in linhas] == [
        f"[gesto] 08-conexoes.html · {j} → aplicado" for j in de_pe]
    assert all(_HORA.match(x) for x in linhas)
