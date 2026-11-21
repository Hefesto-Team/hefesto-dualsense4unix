"""Os pacotes levam todo módulo que o produto importa.

OS-PACOTES-LEVAM-TODO-MODULO-QUE-O-PRODUTO-IMPORTA-01: cada receita redigitava a lista de
dependências. O Arch e o Fedora instalavam o `pydualsense` com `--no-deps` e ficavam sem o
`hidapi-usb` que ele importa; o `python-uinput` (mouse, cursor pelo touchpad, teclado emulado) e o
`jeepney` só vinham pelos extras, que nenhum pacote pedia. A régua lê o `pyproject.toml` e o
METADATA do `pydualsense` e reprova a receita que não leva cada módulo.

A MORDIDA: tire o extra do `build_deb.sh`, o `python-uinput` do `pip` do PKGBUILD ou do spec, o
`bubblewrap` do control, e a régua reprova.
"""
from __future__ import annotations

import importlib.metadata as metadados
import importlib.util
import re
import subprocess
import tomllib
from pathlib import Path
from typing import Any

import pytest

RAIZ = Path(__file__).resolve().parents[2]
PKGBUILD = RAIZ / "packaging/arch/PKGBUILD"
SPEC = RAIZ / "packaging/fedora/hefesto-dualsense4unix.spec"
CONTROL = RAIZ / "packaging/debian/control"
NIX = RAIZ / "packaging/nix/package.nix"
BUILD_DEB = RAIZ / "scripts/build_deb.sh"
BUILD_APPIMAGE = RAIZ / "scripts/build_appimage.sh"
DOCTOR = RAIZ / "scripts/doctor.sh"

EXTRAS_DO_PRODUTO = ("emulation", "cosmic")
VIA_PIP_NO_ARCH_E_NO_FEDORA = ("pydualsense", "hidapi-usb", "python-uinput")
APELIDOS = {"yaml": "pyyaml"}
LINHA_SEM_O_MODULO = "emulação de mouse e teclado: módulo uinput ausente nesta instalação"


def _nome(requisito: str) -> str:
    achado = re.match(r"[A-Za-z0-9][A-Za-z0-9_.-]*", requisito.strip())
    assert achado, requisito
    nome = achado.group(0).lower().replace("_", "-").replace(".", "-")
    for prefixo in ("python3-", "python-"):
        nome = nome.removeprefix(prefixo)
    return APELIDOS.get(nome, nome)


def _projeto() -> dict[str, list[str]]:
    dados = tomllib.loads((RAIZ / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    return {"": dados["dependencies"], **dados["optional-dependencies"]}


def _o_que_o_pip_traz(extras: tuple[str, ...]) -> set[str]:
    projeto = _projeto()
    return {_nome(r) for chave in ("", *extras) for r in projeto[chave]} | _o_que_a_cadeia_pede()


def _o_que_a_cadeia_pede() -> set[str]:
    pedidos: set[str] = set()
    for dist in ("pydualsense", "hidapi-usb"):
        pedidos |= {_nome(r) for r in metadados.requires(dist) or [] if "extra ==" not in r}
    return pedidos


def _o_produto_pede() -> set[str]:
    return _o_que_o_pip_traz(EXTRAS_DO_PRODUTO)


def _extras_do_comando(texto: str, padrao: str) -> tuple[str, ...]:
    achado = re.search(padrao, texto)
    assert achado, f"nenhum pip pede os extras ({padrao})"
    return tuple(achado.group(1).split(","))


def _aspas(texto: str) -> set[str]:
    return {_nome(m) for m in re.findall(r'"([A-Za-z][^"]*)"', texto)}


def _bloco_do_pip(texto: str) -> str:
    achado = re.search(r"^[ \t]*pip3? install((?:[^\n]*\\\n)*[^\n]*)", texto, re.M)
    assert achado, "a receita não tem o pip install"
    return achado.group(1)


def _levado_pelo_arch() -> set[str]:
    texto = PKGBUILD.read_text(encoding="utf-8")
    depende = re.search(r"\ndepends=\((.*?)\n\)", texto, re.S)
    assert depende
    itens = re.findall(r"^\s*'([A-Za-z0-9][^'<>=:]*)", depende.group(1), re.M)
    return {_nome(i) for i in itens} | _aspas(_bloco_do_pip(texto))


def _levado_pelo_fedora() -> set[str]:
    texto = SPEC.read_text(encoding="utf-8")
    itens = re.findall(r"^Requires:\s+(\S+)", texto, re.M)
    return {_nome(i) for i in itens} | _aspas(_bloco_do_pip(texto))


def _levado_pelo_nix() -> set[str]:
    texto = NIX.read_text(encoding="utf-8")
    lista = texto[texto.index("with python3Packages; ["):]
    lista = lista[:lista.index("(python3Packages.buildPythonPackage")]
    soltos = re.findall(r"^\s+([A-Za-z][A-Za-z0-9_-]*)\s*$", lista, re.M)
    deles = [
        n
        for d in re.findall(r"dependencies = [^\[\n]*\[\s*([^\]]+?)\s*\]", texto)
        for n in d.split()
    ]
    derivacoes = dict(
        re.findall(r'(\w+) = python3Packages\.buildPythonPackage \{\s*pname = "([^"]+)"', texto)
    )
    da_lista = re.findall(r'buildPythonPackage rec \{\s*pname = "([^"]+)"', texto)
    levados = [derivacoes.get(n, n) for n in (*soltos, *deles)]
    return {_nome(n) for n in (*levados, *da_lista)}


def _levado_pelo_deb() -> set[str]:
    extras = _extras_do_comando(
        BUILD_DEB.read_text(encoding="utf-8"), r'install[^\n]*"?\.\[([a-z,]+)\]"?'
    )
    return _o_que_o_pip_traz(extras)


def _levado_pelo_appimage() -> set[str]:
    extras = _extras_do_comando(
        BUILD_APPIMAGE.read_text(encoding="utf-8"), r"\$WHEEL\[([a-z,]+)\]"
    )
    return _o_que_o_pip_traz(extras)


RECEITAS = {
    "arch": _levado_pelo_arch,
    "fedora": _levado_pelo_fedora,
    "nix": _levado_pelo_nix,
    "deb": _levado_pelo_deb,
    "appimage": _levado_pelo_appimage,
}


@pytest.mark.parametrize("formato", RECEITAS)
def test_toda_receita_leva_cada_modulo_que_o_produto_importa(formato: str) -> None:
    """D-2011-O-PACOTE-LEVA-TODO-MODULO-QUE-O-PRODUTO-IMPORTA: cada receita leva o módulo."""
    faltam = _o_produto_pede() - RECEITAS[formato]()
    assert not faltam, f"o pacote «{formato}» não leva: {sorted(faltam)}"


@pytest.mark.parametrize("arquivo", [PKGBUILD, SPEC], ids=["arch", "fedora"])
def test_arch_e_fedora_instalam_pelo_mesmo_pip_o_que_nao_tem_pacote(arquivo: Path) -> None:
    """Sem o `hidapi-usb`, o `import pydualsense` levanta ao subir o serviço."""
    instalados = _aspas(_bloco_do_pip(arquivo.read_text(encoding="utf-8")))
    assert {_nome(n) for n in VIA_PIP_NO_ARCH_E_NO_FEDORA} <= instalados, instalados


def test_a_cadeia_do_pydualsense_e_a_que_o_metadata_diz() -> None:
    assert _o_que_a_cadeia_pede() == {"hidapi-usb", "cffi"}


@pytest.mark.parametrize(
    ("arquivo", "bwrap"),
    [(PKGBUILD, "'bubblewrap'"), (SPEC, "Requires:       bubblewrap"), (CONTROL, "bubblewrap")],
    ids=["arch", "fedora", "deb"],
)
def test_sem_o_bwrap_nenhuma_extensao_abre(arquivo: Path, bwrap: str) -> None:
    texto = arquivo.read_text(encoding="utf-8")
    codigo = "\n".join(ln for ln in texto.splitlines() if not ln.lstrip().startswith("#"))
    assert bwrap in codigo


def test_o_arch_declara_o_que_o_python_uinput_precisa_para_compilar() -> None:
    texto = PKGBUILD.read_text(encoding="utf-8")
    faz = re.search(r"\nmakedepends=\((.*?)\n\)", texto, re.S)
    assert faz
    assert "'gcc'" in faz.group(1) and "'python-setuptools'" in faz.group(1)
    assert not re.search(r"^arch=\('any'\)", texto, re.M), "o pacote leva um .so: não é `any`"


def test_o_fedora_declara_o_que_o_python_uinput_precisa_para_compilar() -> None:
    texto = SPEC.read_text(encoding="utf-8")
    for pedido in ("gcc", "python3-setuptools", "systemd-devel"):
        assert re.search(rf"^BuildRequires:\s+{pedido}\b", texto, re.M), pedido
    assert not re.search(r"^BuildArch:\s+noarch", texto, re.M), "o pacote leva um .so"
    assert "%{python3_sitearch}/uinput/" in texto
    assert "%{python3_sitearch}/_libsuinput*.so" in texto


def test_o_nix_compila_o_python_uinput_com_a_libudev() -> None:
    texto = NIX.read_text(encoding="utf-8")
    bloco = texto[texto.index('pname = "python-uinput"'):]
    bloco = bloco[:bloco.index("doCheck = false;")]
    assert "systemd" in bloco and 'pythonImportsCheck = [ "uinput" ]' in bloco


def _avisos_do_boot(monkeypatch: pytest.MonkeyPatch, *, com_o_modulo: bool) -> list[str]:
    from hefesto_dualsense4unix.core import system_check
    from hefesto_dualsense4unix.integrations import curas_da_casa

    avisos: list[str] = []

    class Registro:
        def warning(self, _evento: str, detail: str) -> None:
            avisos.append(detail)

    achar = importlib.util.find_spec
    monkeypatch.setattr(system_check, "system_warnings", lambda: [])
    monkeypatch.setattr(curas_da_casa, "avisar_uma_vez_por_kernel", lambda: True)
    monkeypatch.setattr(
        "hefesto_dualsense4unix.utils.logging_config.get_logger", lambda _n: Registro()
    )

    def achar_uinput(nome: str, *a: Any) -> Any:
        if nome == "uinput":
            return object() if com_o_modulo else None
        return achar(nome, *a)

    monkeypatch.setattr(importlib.util, "find_spec", achar_uinput)
    system_check.avisar_da_infra_no_boot(dormir=lambda _s: None)
    return avisos


def test_o_boot_diz_quando_falta_o_modulo_uinput(monkeypatch: pytest.MonkeyPatch) -> None:
    """MORDIDA: apague a chamada em `avisar_da_infra_no_boot` e o boot volta a calar."""
    assert _avisos_do_boot(monkeypatch, com_o_modulo=False) == [LINHA_SEM_O_MODULO]
    assert _avisos_do_boot(monkeypatch, com_o_modulo=True) == []


def _doctor(tmp_path: Path, python: str) -> str:
    falso = tmp_path / "python"
    falso.write_text(python, encoding="utf-8")
    falso.chmod(0o755)
    roteiro = (
        f'set --; source "{DOCTOR}"; _python_do_produto() {{ echo "{falso}"; }}; '
        "conselho_de_instalacao() { printf 'reinstale'; }; check_emulacao_de_mouse_e_teclado; true"
    )
    feito = subprocess.run(
        ["bash", "-c", roteiro],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)},
    )
    return feito.stdout


def test_o_doctor_diz_quando_falta_o_modulo_uinput(tmp_path: Path) -> None:
    """MORDIDA: tire o `check_emulacao_de_mouse_e_teclado` do doctor e ele cala."""
    sem = _doctor(tmp_path, "#!/bin/sh\nexit 1\n")
    assert f"[WARN] {LINHA_SEM_O_MODULO}" in sem, sem
    com = _doctor(tmp_path, "#!/bin/sh\nexit 0\n")
    assert "[ OK ]" in com and "[WARN]" not in com, com
    assert "check_emulacao_de_mouse_e_teclado\n" in DOCTOR.read_text(encoding="utf-8")
