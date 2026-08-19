"""VERDE-MENTIROSO-01 (19/08/2026) — o doctor não cobrava as duas obrigatórias.

`grep -n "hidapi\\|rsvg" scripts/doctor.sh` dava ZERO antes desta leva. O
instalador só passou a GARANTIR a `libhidapi` e o loader SVG em 19/08 — quem
instalou antes disso, ou instalou por pacote da distro, seguia com verde
mentiroso na conferência: o doctor dizia que estava tudo bem e o produto não
abria aparelho nenhum, ou desenhava a bandeja vazia.

A ARMADILHA QUE ESTA LEVA PAGOU, e é por isso que este arquivo mede o EFEITO:
a primeira versão da régua do SVG perguntava `GdkPixbuf.Pixbuf.get_formats()`.
Isso lê o CACHE do gdk-pixbuf (`loaders.cache`), não o loader. Medido com o
`libpixbufloader-svg.so` fora do alcance do processo: o catálogo continuava
dizendo que sabe ler SVG, e a régua dava verde sobre uma máquina em que o ícone
sairia vazio. Agora ela CARREGA um SVG, que é o que a interface faz 38 vezes.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
DOCTOR = RAIZ / "scripts" / "doctor.sh"


def _funcao(nome: str) -> str:
    texto = DOCTOR.read_text(encoding="utf-8")
    m = re.search(rf"\n{nome}\(\) \{{.*?\n\}}\n", texto, re.S)
    assert m is not None, f"`{nome}` sumiu do doctor.sh"
    return m.group(0)


def _rodar(nome: str, *, mascarar: list[str] | None = None) -> int:
    """Roda UMA checagem do doctor, opcionalmente sem alguma biblioteca.

    Máscara por `bwrap --bind` de arquivo vazio: nada é apagado da máquina, e a
    biblioteca só fica fora do alcance DESTE processo.
    """
    prelude = (
        "set -uo pipefail\n"
        "FAILS=0; WARNS=0\n"
        "pass() { printf '[ OK ] %s\\n' \"$*\"; }\n"
        "fail() { printf '[FAIL] %s\\n' \"$*\"; exit 7; }\n"
        "warn() { printf '[WARN] %s\\n' \"$*\"; exit 8; }\n"
        f'HEFESTO_RAIZ="{RAIZ}"\n'
    )
    corpo = _funcao("_python_do_produto").replace(
        '"$(dirname "$0")/../.venv/bin/python"', '"${HEFESTO_RAIZ}/.venv/bin/python"'
    )
    script = prelude + corpo + _funcao(nome) + f"\n{nome}\n"
    cmd = ["/usr/bin/bash", "-c", script]
    if mascarar:
        # BERCO-DE-TMP-01: caminho FIXO em /tmp ignora o TMPDIR do berço e suja
        # a máquina dela. O `tempfile` respeita o berço.
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
        # O CI não traz `bwrap`. Sem esta guarda o `subprocess.run` estourava com
        # `FileNotFoundError` e a mordida virava ERRO — que se lê como "a régua
        # do doctor quebrou", quando o que falta é a ferramenta de mascarar.
        if shutil.which("bwrap") is None:
            pytest.skip("sem `bwrap` não dá para mascarar a biblioteca")
        envelope = ["bwrap", "--dev-bind", "/", "/", *binds]
        # MASCARA-QUE-NAO-PEGOU-01 (19/08/2026): PROVE que a máscara pegou antes
        # de acreditar no código de saída. Sem esta sonda o `returncode` podia ser
        # do `bwrap`, não do doctor — e foi: no runner do Ubuntu 24.04 o AppArmor
        # bloqueia user namespace sem privilégio, o `bwrap` saía com 1, e a
        # mordida reprovava dizendo "o doctor deu verde" com o doctor nunca tendo
        # rodado. Alarme convincente e falso, a armadilha nº 1 desta casa.
        #
        # A sonda pergunta pelo EFEITO: dentro do envelope, o primeiro alvo é um
        # arquivo VAZIO? Se sim, a máscara está de pé e o que voltar depois é do
        # doctor. Se não — por qualquer motivo —, o instrumento se declara
        # incapaz em vez de dar veredito sobre o produto.
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
            # BERCO-DE-TMP-01: a máscara sai com o teste. Ela é um `.so` VAZIO e
            # inofensivo, mas o berço conta entradas, não perigo.
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
    """O gdk-pixbuf desta máquina CARREGA um SVG?

    A pergunta é pelo efeito, e não pelo pacote — é a mesma disciplina do
    `check_loader_svg` que este arquivo afere. E precisa ser feita: o job
    `lint-test` do CI não instala o loader, então "com o loader passa" ali não
    tinha premissa. Reprovava dizendo que a régua estava errada, quando o que
    faltava era a coisa medida.
    """
    codigo = (
        "import gi; gi.require_version('GdkPixbuf','2.0');"
        "from gi.repository import GdkPixbuf;"
        "import os, tempfile, pathlib;"
        # BERCO-DE-TMP-01: o SVG de mentira sai com o processo. Sem isto a régua
        # deixava lixo em /tmp e o próprio berço da suíte reclamava dela.
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
        subprocess.run(
            [sys.executable, "-c", codigo], capture_output=True
        ).returncode
        == 0
    )


class TestOhDoctorCobraOLoaderSVG:
    def test_com_o_loader_passa(self) -> None:
        if not _tem_loader_svg():
            pytest.skip("esta máquina não carrega SVG — não há loader a aferir")
        assert _rodar("check_loader_svg") == 0

    def test_a_mordida_sem_o_loader_reprova(self) -> None:
        """E ela mede o EFEITO, não o catálogo.

        Se alguém trocar o carregamento por `Pixbuf.get_formats()`, este teste
        volta a dar verde com o loader mascarado — medido em 19/08.
        """
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
