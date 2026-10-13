"""A tela é dependência dura: o WebKit que o `janela.py` exige entra em todo lugar.

O dono do namespace é `interface/janela.py` (`gi.require_version("WebKit2", "4.1")`,
sem alternativa). Esta régua o lê de lá e exige o mesmo binding como obrigatório
no install, como dependência dura nos quatro manifestos e como pergunta no doctor.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
JANELA = RAIZ / "src/hefesto_dualsense4unix/interface/janela.py"
INSTALL = (RAIZ / "install.sh").read_text(encoding="utf-8")
DOCTOR = RAIZ / "scripts/doctor.sh"
DOCTOR_TEXTO = DOCTOR.read_text(encoding="utf-8")

_REQUIRE = re.search(
    r'gi\.require_version\(\s*"(WebKit2)"\s*,\s*"([0-9.]+)"\s*\)',
    JANELA.read_text(encoding="utf-8"),
)
assert _REQUIRE is not None, "o janela.py deixou de exigir o WebKit2 por require_version"
NAMESPACE, SERIE = _REQUIRE.group(1), _REQUIRE.group(2)


def _nomes_do_install() -> dict[str, str]:
    """Os nomes por família que `_pkg_nome` dá ao binding (o install é o dono)."""
    bloco = re.search(r"\n\s*webkit2gtk\)\n(.*?);;", INSTALL, re.S)
    assert bloco is not None, "o `webkit2gtk)` sumiu da tabela `_pkg_nome`"
    corpo = bloco.group(1)
    achados = {
        familia: re.search(rf'_{familia}="([^"]+)"', corpo) for familia in ("apt", "dnf", "pacman")
    }
    assert all(achados.values()), f"a tabela não nomeia o binding nas três famílias: {corpo!r}"
    return {f: m.group(1) for f, m in achados.items() if m}


def _sem_comentario(texto: str, marca: str) -> str:
    return "\n".join(
        linha for linha in texto.splitlines() if not linha.lstrip().startswith(marca)
    )


def test_o_install_declara_o_binding_obrigatorio() -> None:
    linha = next(
        (x for x in re.findall(r'"([^"]*\|[^"]*)"', INSTALL) if x.startswith("webkit2gtk|")),
        None,
    )
    assert linha is not None, "o binding saiu do censo do install"
    _, criticidade, checagem, razao = linha.split("|")
    assert criticidade == "obrigatoria", (
        f"o binding do {NAMESPACE} {SERIE} está {criticidade!r} no install: sem ele "
        "a janela não abre, e o install tem de morrer pedindo o pacote"
    )
    assert checagem == "webkit"
    assert "interface" in razao.lower(), "a razão tem de dizer o efeito: a interface não abre"


def test_a_sonda_do_install_pergunta_o_mesmo_que_o_janela() -> None:
    sonda = re.search(r"\n\s*webkit\)\n(.*?);;", INSTALL, re.S)
    assert sonda is not None
    assert f"require_version('{NAMESPACE}','{SERIE}')" in sonda.group(1).replace('"', "'")


def test_os_quatro_manifestos_declaram_o_binding_como_dependencia_dura() -> None:
    nomes = _nomes_do_install()
    debian = (RAIZ / "packaging/debian/control").read_text(encoding="utf-8")
    depends = re.search(r"^Depends:(.*?)^\S", debian, re.S | re.M)
    assert depends is not None and nomes["apt"] in depends.group(1), (
        f"o Depends do .deb não traz {nomes['apt']}"
    )

    pkgbuild = (RAIZ / "packaging/arch/PKGBUILD").read_text(encoding="utf-8")
    bloco = re.search(r"^depends=\((.*?)^\)", pkgbuild, re.S | re.M)
    assert bloco is not None
    assert f"'{nomes['pacman']}'" in _sem_comentario(bloco.group(1), "#"), (
        f"o `depends` do PKGBUILD não traz {nomes['pacman']}"
    )

    spec = (RAIZ / "packaging/fedora/hefesto-dualsense4unix.spec").read_text(encoding="utf-8")
    assert re.search(rf"^Requires:\s+{re.escape(nomes['dnf'])}\s*$", spec, re.M), (
        f"a spec não tem `Requires: {nomes['dnf']}`"
    )

    nix = (RAIZ / "packaging/nix/package.nix").read_text(encoding="utf-8")
    args = _sem_comentario(nix.split("}:", 1)[0], "#")
    assert re.search(r"^,\s*webkitgtk_4_1\s*$", args, re.M), (
        "o argumento `webkitgtk_4_1` saiu do package.nix"
    )
    inputs = re.search(r"^  buildInputs = \[(.*?)^  \];", nix, re.S | re.M)
    assert inputs is not None
    assert re.search(r"^\s+webkitgtk_4_1\s*$", _sem_comentario(inputs.group(1), "#"), re.M), (
        "o `webkitgtk_4_1` saiu dos buildInputs (é de lá que o wrapGAppsHook3 monta o "
        "GI_TYPELIB_PATH do wrapper)"
    )


def test_o_nome_da_serie_nos_manifestos_e_o_do_janela() -> None:
    for familia, nome in _nomes_do_install().items():
        assert SERIE in nome or SERIE.replace(".", "-") in nome, (
            f"{familia}: {nome!r} não é da série {SERIE} que o janela.py exige"
        )


# ---------------------------------------------------------------- o doctor


def _funcao_do_doctor(nome: str) -> str:
    m = re.search(rf"\n{nome}\(\) \{{.*?\n\}}\n", DOCTOR_TEXTO, re.S)
    assert m is not None, f"`{nome}` não existe no doctor.sh"
    return m.group(0)


def _gi_de_mentira(tmp_path: Path, repositorio: str, require: str) -> Path:
    stub = tmp_path / "stub"
    (stub / "gi" / "repository").mkdir(parents=True)
    (stub / "gi" / "__init__.py").write_text(require, encoding="utf-8")
    (stub / "gi" / "repository" / "__init__.py").write_text(repositorio, encoding="utf-8")
    py = tmp_path / "python-falso"
    py.write_text(
        f'#!/usr/bin/bash\nexec /usr/bin/env PYTHONPATH="{stub}" "{sys.executable}" "$@"\n',
        encoding="utf-8",
    )
    py.chmod(0o755)
    return py


_REQUIRE_OK = "def require_version(espaco, serie):\n    return None\n"
_REQUIRE_SEM_TYPELIB = (
    "def require_version(espaco, serie):\n"
    "    raise ValueError('Namespace %s not available for version %s' % (espaco, serie))\n"
)
_MOTOR_OK = "class WebKit2:\n    @staticmethod\n    def get_major_version():\n        return 2\n"
_MOTOR_SEM_BIBLIOTECA = (
    "class WebKit2:\n    @staticmethod\n    def get_major_version():\n"
    "        raise RuntimeError('Could not locate webkit_get_major_version')\n"
)


def _roda_o_check(
    tmp_path: Path, py: Path, gestor: str | None = None
) -> subprocess.CompletedProcess[str]:
    bin_ = tmp_path / "bin"
    bin_.mkdir(exist_ok=True)
    if gestor:
        (bin_ / gestor).write_text("#!/bin/sh\n", encoding="utf-8")
        (bin_ / gestor).chmod(0o755)
    script = (
        "set -uo pipefail\n"
        "pass() { printf '[ OK ] %s\\n' \"$*\"; }\n"
        "fail() { printf '[FAIL] %s\\n' \"$*\"; exit 7; }\n"
        "warn() { printf '[WARN] %s\\n' \"$*\"; exit 8; }\n"
        "conselho_de_instalacao() { printf 'rode ./install.sh'; }\n"
        f"_python_do_produto() {{ printf '%s\\n' '{py}'; }}\n"
        f"PATH='{bin_}'\n"
        + _funcao_do_doctor("check_binding_webkit")
        + "\ncheck_binding_webkit\n"
    )
    return subprocess.run(
        ["/usr/bin/bash", "-c", script], capture_output=True, text=True, timeout=120
    )


def test_o_doctor_chama_a_pergunta_no_main() -> None:
    corpo = _funcao_do_doctor("main") if "\nmain() {" in DOCTOR_TEXTO else DOCTOR_TEXTO
    assert re.search(r"^\s+check_binding_webkit\s*$", corpo, re.M), (
        "o doctor define `check_binding_webkit` e não a chama"
    )


def test_o_doctor_pergunta_o_mesmo_namespace_do_janela() -> None:
    corpo = _funcao_do_doctor("check_binding_webkit").replace('"', "'")
    assert f"require_version('{NAMESPACE}', '{SERIE}')" in corpo
    assert "get_major_version()" in corpo, (
        "a pergunta tem de tocar um símbolo da biblioteca: o typelib sem a lib passa "
        "pelo require_version"
    )


def test_com_o_binding_e_o_motor_o_doctor_passa(tmp_path: Path) -> None:
    py = _gi_de_mentira(tmp_path, _MOTOR_OK, _REQUIRE_OK)
    proc = _roda_o_check(tmp_path, py)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "[ OK ]" in proc.stdout


def test_sem_o_typelib_o_doctor_falha(tmp_path: Path) -> None:
    py = _gi_de_mentira(tmp_path, _MOTOR_OK, _REQUIRE_SEM_TYPELIB)
    proc = _roda_o_check(tmp_path, py)
    assert proc.returncode == 7, proc.stdout + proc.stderr


def test_typelib_sem_a_biblioteca_o_doctor_falha(tmp_path: Path) -> None:
    py = _gi_de_mentira(tmp_path, _MOTOR_SEM_BIBLIOTECA, _REQUIRE_OK)
    proc = _roda_o_check(tmp_path, py)
    assert proc.returncode == 7, proc.stdout + proc.stderr


@pytest.mark.parametrize("gestor", ["apt-get", "dnf", "pacman"])
def test_a_falha_nomeia_o_pacote_da_familia(tmp_path: Path, gestor: str) -> None:
    py = _gi_de_mentira(tmp_path, _MOTOR_OK, _REQUIRE_SEM_TYPELIB)
    proc = _roda_o_check(tmp_path, py, gestor)
    nomes = _nomes_do_install()
    esperado = nomes[{"apt-get": "apt", "dnf": "dnf", "pacman": "pacman"}[gestor]]
    assert proc.returncode == 7
    assert esperado in proc.stdout, proc.stdout
