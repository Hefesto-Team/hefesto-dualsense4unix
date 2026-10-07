"""O Nix dá ao `pydualsense` o `hidapi-usb`, não o `hidapi` homônimo do nixpkgs.

O CI do `dev` reprovou em 07/10/2026 com `hidapi-usb not installed`: o
`pydualsense` 0.7.5 pede `hidapi-usb` e faz `import hidapi` (o módulo CFFI), e
o `python3Packages.hidapi` do nixpkgs é outro pacote (o `import hid`, em
Cython). Sem `nix` na máquina, a régua lê o `package.nix`.
"""
from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
NIX = RAIZ / "packaging" / "nix" / "package.nix"
TRAVAS = RAIZ / "constraints.txt"


def _bloco(texto: str, abre: str) -> str:
    """Do `abre` até a chave que fecha o `buildPythonPackage` dele."""
    ini = texto.index(abre)
    fundo = texto.index("buildPythonPackage", ini)
    nivel, i = 0, texto.index("{", fundo)
    for j in range(i, len(texto)):
        if texto[j] == "{":
            nivel += 1
        elif texto[j] == "}":
            nivel -= 1
            if nivel == 0:
                return texto[i : j + 1]
    raise AssertionError(f"o bloco de {abre!r} não fecha")


def _pydualsense() -> str:
    texto = NIX.read_text(encoding="utf-8")
    ini = texto.index('pname = "pydualsense"')
    return texto[ini : texto.index("})", ini)]


def test_o_pydualsense_nao_depende_do_hidapi_homonimo() -> None:
    bloco = _pydualsense()
    dependencias = re.search(r"dependencies\s*=\s*([^;]*);", bloco)
    assert dependencias, "o pydualsense do Nix ficou sem `dependencies`"
    corpo = dependencias.group(1)
    assert "hidapiUsb" in corpo, (
        "o pydualsense pede hidapi-usb: o Nix tem de dar-lhe o hidapiUsb"
    )
    assert not re.search(r"\bhidapi\b(?!Usb)", corpo), (
        "`python3Packages.hidapi` é o `import hid`, outro pacote: a checagem "
        "de dependências da construção reprova com `hidapi-usb not installed`"
    )


def test_o_import_do_pydualsense_e_conferido_na_construcao() -> None:
    assert 'pythonImportsCheck = [ "pydualsense" ]' in _pydualsense()


def test_o_hidapi_usb_do_nix_e_o_que_a_casa_mediu() -> None:
    texto = NIX.read_text(encoding="utf-8")
    bloco = _bloco(texto, "hidapiUsb =")
    assert 'pname = "hidapi-usb"' in bloco
    versao = re.search(r'version\s*=\s*"([^"]+)"', bloco)
    travada = re.search(r"^hidapi-usb==(\S+)", TRAVAS.read_text("utf-8"), re.M)
    assert versao and travada
    assert versao.group(1) == travada.group(1), (
        "o Nix empacota outra versão do hidapi-usb que a medida em constraints.txt"
    )
    assert re.search(r'hash\s*=\s*"sha256-[A-Za-z0-9+/]{43}="', bloco), (
        "o sdist do hidapi-usb tem de ter hash conferido"
    )
    assert "cffi" in bloco, "o hidapi-usb é CFFI: sem o cffi o import cai"
    assert 'pythonImportsCheck = [ "hidapi" ]' in bloco


def test_o_modulo_acha_a_libhidapi_no_caminho_do_nixpkgs() -> None:
    """`ffi.dlopen` de nome solto não acha a lib na construção do Nix."""
    bloco = _bloco(NIX.read_text(encoding="utf-8"), "hidapiUsb =")
    assert "libhidapi-hidraw.so.0" in bloco
    assert "lib.getLib hidapi" in bloco
    assert "--replace-fail" in bloco, (
        "o substituteInPlace tem de falhar alto se o módulo mudar de forma"
    )
