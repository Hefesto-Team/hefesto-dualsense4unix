"""A matriz de versões publicada tem de bater com o que o código confere."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

tomllib = pytest.importorskip("tomllib", reason="tomllib exige Python 3.11+")

from tests.conftest import arvore_congelada

PAGINA = Path("docs/usage/versoes-validadas.md")


def _raiz_do_repo() -> Path:
    """A raiz de trabalho."""
    return Path(__file__).resolve().parents[2]


def _pagina() -> str:
    caminho = _raiz_do_repo() / PAGINA
    assert caminho.is_file(), (
        f"{PAGINA} sumiu. Ela é o único lugar onde a pessoa que instala descobre "
        "em que versões isto funciona."
    )
    return caminho.read_text(encoding="utf-8")


def _doctor() -> str:
    return (arvore_congelada() / "scripts" / "doctor.sh").read_text(encoding="utf-8")


def test_a_faixa_do_bluez_bate():
    """O piso e o teto do BlueZ são os mesmos na página e no `doctor.sh`."""
    doctor = _doctor()
    pisos = set(re.findall(r"\b5\.79\b", doctor))
    tetos = set(re.findall(r"\b5\.87\b", doctor))
    assert pisos, "o doctor.sh não menciona mais 5.79 — o piso mudou?"
    assert tetos, "o doctor.sh não menciona mais 5.87 — o teto mudou?"

    pagina = _pagina()
    assert "5.79" in pagina, (
        "o doctor.sh cobra piso 5.79 e a página não o menciona; quem instalar "
        f"não vai saber. Atualize {PAGINA}."
    )
    assert "5.87" in pagina, (
        f"o doctor.sh usa 5.87 como teto e a página não o menciona. Atualize {PAGINA}."
    )


def test_o_python_minimo_bate():
    """O `requires-python` do pyproject aparece na página."""
    dados = tomllib.loads(
        (_raiz_do_repo() / "pyproject.toml").read_text(encoding="utf-8")
    )
    exigido = dados["project"]["requires-python"]
    numero = re.search(r"(\d+\.\d+)", exigido).group(1)
    assert numero in _pagina(), (
        f"o pyproject exige Python {exigido} e a página não cita {numero}. "
        f"Atualize {PAGINA}."
    )


def test_o_kernel_testado_bate():
    """O kernel que o `doctor.sh` chama de testado aparece na página."""
    doctor = _doctor()
    achado = re.search(
        r'HEFESTO_DKMS_KERNEL_TESTED="([^"]+)"', doctor
    )
    assert achado, "a constante HEFESTO_DKMS_KERNEL_TESTED sumiu do doctor.sh"
    kernel = achado.group(1)
    assert kernel in _pagina(), (
        f"o doctor.sh testa contra o kernel {kernel} e a página não o cita. "
        f"Atualize {PAGINA}."
    )


def test_o_pino_do_rtw88_bate():
    """O kernel pinado do `rtw88-usb` aparece na página."""
    conf = (_raiz_do_repo() / "assets/dkms/rtw88-usb/dkms.conf").read_text(
        encoding="utf-8"
    )
    achado = re.search(r'BUILD_EXCLUSIVE_KERNEL="([^"]+)"', conf)
    assert achado, "o rtw88-usb perdeu o BUILD_EXCLUSIVE_KERNEL"
    versao = re.search(r"(\d+\.\d+\.\d+)", achado.group(1).replace("\\", ""))
    assert versao, f"não consegui ler a versão de {achado.group(1)!r}"
    assert versao.group(1) in _pagina(), (
        f"o rtw88-usb é pinado em {versao.group(1)} e a página não o cita. "
        f"Atualize {PAGINA}."
    )


@pytest.mark.parametrize(
    "assunto",
    ["Secure Boot", "kernel", "Debian", "COSMIC"],
)
def test_a_pagina_declara_o_que_nao_foi_testado(assunto):
    """A seção de honestidade não pode sumir."""
    pagina = _pagina()
    assert "não foi testado" in pagina.lower(), (
        "a seção do que não foi testado sumiu; sem ela a página promete mais do "
        "que a casa mediu"
    )
    assert assunto in pagina, f"a página deixou de mencionar {assunto!r} entre os limites"
