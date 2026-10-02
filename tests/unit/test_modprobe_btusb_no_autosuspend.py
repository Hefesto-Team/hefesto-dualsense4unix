"""Forma do modprobe.d do btusb (PLAT-04 item 1: BT no máximo)."""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CONF_PATH = REPO_ROOT / "assets" / "modprobe.d" / "hefesto-btusb-no-autosuspend.conf"

EXPECTED_OPTION = "options btusb enable_autosuspend=0"


@pytest.fixture(scope="module")
def conf_text() -> str:
    return CONF_PATH.read_text(encoding="utf-8")


def test_arquivo_existe() -> None:
    assert CONF_PATH.is_file(), f"conf ausente em {CONF_PATH}"


def test_linha_de_opcao_exata(conf_text: str) -> None:
    ativos = [
        ln.strip()
        for ln in conf_text.splitlines()
        if ln.strip() and not ln.lstrip().startswith("#")
    ]
    assert ativos == [EXPECTED_OPTION], (
        f"esperada EXATAMENTE uma linha ativa '{EXPECTED_OPTION}', veio: {ativos}"
    )


def test_cabecalho_marca_origem_e_reversao(conf_text: str) -> None:
    primeira = conf_text.splitlines()[0]
    assert "hefesto-dualsense4unix" in primeira
    assert "REVERSÍVEL" in conf_text or "reversível" in conf_text.lower(), (
        "documentar como reverter (apagar o arquivo + replug/reboot)"
    )


def test_explica_o_furo_composite(conf_text: str) -> None:
    assert "ef" in conf_text and "composite" in conf_text.lower(), (
        "documentar que cobre adaptadores composite (classe ef) que escapam "
        "da regra udev por classe e0"
    )
