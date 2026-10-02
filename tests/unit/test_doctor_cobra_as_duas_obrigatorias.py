"""VERDE-MENTIROSO-01 (19/08/2026) — o doctor não cobrava as duas obrigatórias."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.conftest import binario_do_venv

RAIZ = Path(__file__).resolve().parents[2]
DOCTOR = RAIZ / "scripts" / "doctor.sh"


def _funcao(nome: str) -> str:
    texto = DOCTOR.read_text(encoding="utf-8")
    m = re.search(rf"\n{nome}\(\) \{{.*?\n\}}\n", texto, re.S)
    assert m is not None, f"`{nome}` sumiu do doctor.sh"
    return m.group(0)


def _venv_python_ao_alcance() -> str:
    """O python de venv que o doctor vai achar — resolvido, nunca presumido."""
    achado = binario_do_venv("python")
    return str(achado) if achado is not None else str(RAIZ / ".venv/bin/python")


def _corpo_do_python_do_produto() -> str:
    """O corpo do doctor com a venv DESTA árvore no lugar da do produto."""
    corpo = _funcao("_python_do_produto")
    alvo = '"${ROOT_DIR}/.venv/bin/python"'
    assert alvo in corpo, "o candidato da venv do produto mudou de grafia"
    return corpo.replace(alvo, f'"{_venv_python_ao_alcance()}"')


def _python_que_o_doctor_usa() -> str:
    """O interpretador que as checagens do doctor vão de fato rodar."""
    saida = subprocess.run(
        ["/usr/bin/bash", "-c", _corpo_do_python_do_produto() + "\n_python_do_produto\n"],
        capture_output=True,
        text=True,
    )
    return saida.stdout.strip()


def _rodar(nome: str, *, mascarar: list[str] | None = None) -> int:
    """Roda UMA checagem do doctor, opcionalmente sem alguma biblioteca."""
    prelude = (
        "set -uo pipefail\n"
        "FAILS=0; WARNS=0\n"
        "pass() { printf '[ OK ] %s\\n' \"$*\"; }\n"
        "fail() { printf '[FAIL] %s\\n' \"$*\"; exit 7; }\n"
        "warn() { printf '[WARN] %s\\n' \"$*\"; exit 8; }\n"
        f'HEFESTO_RAIZ="{RAIZ}"\n'
    )
    corpo = _corpo_do_python_do_produto()
    script = prelude + corpo + _funcao(nome) + f"\n{nome}\n"
    cmd = ["/usr/bin/bash", "-c", script]
    if mascarar:
        import tempfile

        fd, vazio = tempfile.mkstemp(prefix="hefesto-mascara-", suffix=".so")
        os.close(fd)
        Path(vazio).write_bytes(b"")
        binds: list[str] = []
        for alvo in mascarar:
            if Path(alvo).exists():
                binds += ["--bind", vazio, alvo]
        if not binds:
            pytest.skip(f"nada para mascarar: {mascarar}")
        if shutil.which("bwrap") is None:
            pytest.skip("sem `bwrap` não dá para mascarar a biblioteca")
        envelope = ["bwrap", "--dev-bind", "/", "/", *binds]
        sonda = subprocess.run(
            [*envelope, "/usr/bin/bash", "-c", f'test ! -s "{mascarar[0]}"'],
            capture_output=True,
            text=True,
        )
        if sonda.returncode != 0:
            Path(vazio).unlink(missing_ok=True)
            pytest.skip(
                "o `bwrap` não conseguiu mascarar nesta máquina "
                f"(saiu {sonda.returncode}: {sonda.stderr.strip()[:120]}) — "
                "sem máscara não há mordida a medir"
            )
        cmd = [*envelope, *cmd]
        try:
            return subprocess.run(cmd, capture_output=True, text=True).returncode
        finally:
            Path(vazio).unlink(missing_ok=True)
    return subprocess.run(cmd, capture_output=True, text=True).returncode


def _existe(*caminhos: str) -> list[str]:
    return [c for c in caminhos if Path(c).exists()]


class TestOhDoctorCobraALibhidapi:
    def test_com_a_biblioteca_passa(self) -> None:
        assert _rodar("check_libhidapi") == 0, (
            "a régua da libhidapi reprova numa máquina que TEM a biblioteca — "
            "está perguntando outra coisa"
        )

    def test_a_mordida_sem_a_biblioteca_reprova(self) -> None:
        """Tire a régua e isto para de reprovar: o verde mentiroso volta."""
        alvos = _existe(
            "/usr/lib/x86_64-linux-gnu/libhidapi-hidraw.so.0",
            "/usr/lib/x86_64-linux-gnu/libhidapi-libusb.so.0",
            "/usr/lib/x86_64-linux-gnu/libhidapi-hidraw.so",
            "/usr/lib/x86_64-linux-gnu/libhidapi.so.0",
        )
        if not alvos:
            pytest.skip("libhidapi não está no caminho padrão desta máquina")
        assert _rodar("check_libhidapi", mascarar=alvos) == 7, (
            "com a libhidapi FORA do alcance do processo, o doctor deu verde — "
            "é o verde mentiroso que esta régua existe para matar"
        )


def _tem_loader_svg() -> bool:
    """O gdk-pixbuf desta máquina CARREGA um SVG?"""
    py = _python_que_o_doctor_usa()
    if not py:
        return False
    codigo = (
        "import gi; gi.require_version('GdkPixbuf','2.0');"
        "from gi.repository import GdkPixbuf;"
        "import os, tempfile, pathlib;"
        "fd, nome = tempfile.mkstemp(suffix='.svg'); os.close(fd);"
        "p=pathlib.Path(nome);"
        "p.write_text('<svg xmlns=\"http://www.w3.org/2000/svg\" "
        "width=\"8\" height=\"8\"/>');"
        "\ntry:\n"
        "    GdkPixbuf.Pixbuf.new_from_file_at_scale(str(p),8,8,True)\n"
        "finally:\n"
        "    p.unlink(missing_ok=True)"
    )
    return (
        subprocess.run([py, "-c", codigo], capture_output=True).returncode == 0
    )


class TestOhDoctorCobraOLoaderSVG:
    def test_com_o_loader_passa(self) -> None:
        if not _tem_loader_svg():
            pytest.skip("esta máquina não carrega SVG — não há loader a aferir")
        assert _rodar("check_loader_svg") == 0

    def test_a_mordida_sem_o_loader_reprova(self) -> None:
        """E ela mede o EFEITO, não o catálogo."""
        if not _tem_loader_svg():
            pytest.skip("esta máquina não carrega SVG — não há loader a aferir")
        alvos = _existe(
            *[
                str(p)
                for p in Path("/usr/lib/x86_64-linux-gnu/gdk-pixbuf-2.0").glob(
                    "*/loaders/libpixbufloader-svg.so"
                )
            ]
        )
        if not alvos:
            pytest.skip("o loader SVG não está num .so isolável nesta máquina")
        assert _rodar("check_loader_svg", mascarar=alvos) == 7, (
            "com o loader SVG fora do alcance, o doctor deu verde — a régua "
            "voltou a perguntar ao CATÁLOGO (`get_formats`) em vez de carregar "
            "um SVG de verdade"
        )
