"""A matriz de versões publicada tem de bater com o que o código confere.

Nasceu de uma pergunta dela em 11/08/2026: *"talvez seja importante setar as
versões que tudo funciona pro user, não?"*

O defeito que ela nomeou: até aqui, os números que decidem se o produto funciona
viviam em QUATRO arquivos diferentes e nenhum sabia do outro — o piso do BlueZ
no `doctor.sh`, o Python no `pyproject.toml`, o kernel pinado no `dkms.conf` do
`rtw88-usb`, e o kernel testado noutro ponto do `doctor.sh`. Quem fosse instalar
noutra máquina não tinha onde olhar.

`docs/usage/versoes-validadas.md` passou a ser esse lugar. Este teste é o que
impede que ele vire mais um documento envelhecendo em silêncio: se alguém subir
o piso do BlueZ no `doctor.sh` e não atualizar a página, aqui reprova.

O que este teste NÃO faz: julgar se os números estão certos. Ele só exige que a
página e o código digam a MESMA coisa. Trocar um número é decisão de quem mede;
trocar num lugar só é defeito.

A MORDIDA, provada em 11/08/2026
================================
Trocado o piso do BlueZ de 5.79 para 5.80 só na página,
`test_a_faixa_do_bluez_bate` reprova nomeando os dois valores. Trocado só no
`doctor.sh`, reprova igual. Removida a menção ao kernel testado da página,
`test_o_kernel_testado_bate` reprova. Desfeitas, verde.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

# PY310-TOMLLIB-01 (13/08/2026): `tomllib` entrou na biblioteca padrão no
# Python 3.11, e o `pyproject.toml` desta casa declara `py310`. O `ci.yml`
# roda a matriz 3.10/3.11/3.12 — no 3.10 este import derrubava a COLETA do
# módulo inteiro, e o censo do CI reprovava a leva. `pytest.importorskip`
# pula com a razão dita em voz alta, em vez de explodir calado.
tomllib = pytest.importorskip("tomllib", reason="tomllib exige Python 3.11+")

from tests.conftest import arvore_congelada

PAGINA = Path("docs/usage/versoes-validadas.md")


def _raiz_do_repo() -> Path:
    """A raiz de trabalho.

    `docs/` não entra em `_CONGELAR` (tests/conftest.py) — a foto da sessão
    cobre só o que uma bancada de shell executa —, então a página é lida daqui.
    """
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
    # O doctor compara com `sort -V`; os dois números aparecem no texto do
    # veredito e nos comentários que explicam a razão de cada um.
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
    # ">=3.10" -> "3.10"
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
    """O kernel pinado do `rtw88-usb` aparece na página.

    Este módulo é o único com `BUILD_EXCLUSIVE_KERNEL`, e isso é decisão: em
    outro kernel ele não constrói de propósito, e o in-tree fica. Quem instala
    noutra máquina precisa saber que aquele comportamento é esperado.
    """
    # `assets/dkms/` não entra em `_CONGELAR` (só `assets/bluetooth` entra), e
    # este arquivo é lido, nunca executado — então vem da árvore de trabalho.
    conf = (_raiz_do_repo() / "assets/dkms/rtw88-usb/dkms.conf").read_text(
        encoding="utf-8"
    )
    achado = re.search(r'BUILD_EXCLUSIVE_KERNEL="([^"]+)"', conf)
    assert achado, "o rtw88-usb perdeu o BUILD_EXCLUSIVE_KERNEL"
    # O valor é uma regex de shell: "^7\.0\.11-76070011-". Extrai só a versão.
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
    """A seção de honestidade não pode sumir.

    Um documento que lista só o que funciona vira promessa. O valor desta
    página está tanto no que ela garante quanto no que ela recusa a garantir —
    e foi por não dizer isso que uma instalação em máquina nova podia sair
    verde com três curas ausentes.
    """
    pagina = _pagina()
    assert "NÃO foi testado" in pagina, (
        "a seção do que não foi testado sumiu; sem ela a página promete mais do "
        "que a casa mediu"
    )
    assert assunto in pagina, f"a página deixou de mencionar {assunto!r} entre os limites"
