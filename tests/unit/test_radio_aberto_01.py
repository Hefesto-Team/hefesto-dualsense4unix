"""RADIO-ABERTO-01 — o portão da combinação que anula a autenticação do BT."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
ASSETS_BT = REPO_ROOT / "assets" / "bluetooth"

ASSETS_COM_A_CHAVE = (
    ASSETS_BT / "hefesto-justworks.conf",
    ASSETS_BT / "hefesto-justworks.block",
    ASSETS_BT / "hefesto-bt.block",
)

_ATIVA_ALWAYS = re.compile(r"^[ \t]*JustWorksRepairing[ \t]*=[ \t]*always[ \t]*$", re.M)
_ATIVA_CONFIRM = re.compile(r"^[ \t]*JustWorksRepairing[ \t]*=[ \t]*confirm[ \t]*$", re.M)


@pytest.mark.parametrize("asset", ASSETS_COM_A_CHAVE, ids=lambda p: p.name)
def test_nenhum_asset_pede_just_works_sempre(asset: Path) -> None:
    """`always` remove a última recusa do BlueZ. Nenhum asset pode pedi-lo."""
    assert asset.exists(), f"asset sumiu: {asset.relative_to(REPO_ROOT)}"
    texto = asset.read_text(encoding="utf-8")
    achado = _ATIVA_ALWAYS.search(texto)
    assert achado is None, (
        f"{asset.name} voltou a pedir JustWorksRepairing=always. Isso remove a "
        "ÚLTIMA recusa do BlueZ ao re-pareamento por Just Works de quem já tem "
        "bond e, com o agente NoInputNoOutput, o caminho termina em injeção de "
        "teclas (RADIO-ABERTO-01). Se uma janela de `always` for mesmo "
        "necessária, ela tem de ser ARMADA POR GESTO E DESARMADA POR TIMER — "
        "nunca um regime permanente instalado por padrão."
    )


@pytest.mark.parametrize("asset", ASSETS_COM_A_CHAVE, ids=lambda p: p.name)
def test_os_assets_declaram_confirm(asset: Path) -> None:
    """Ausência de `always` não basta: a chave tem de estar lá, com `confirm`."""
    texto = asset.read_text(encoding="utf-8")
    assert _ATIVA_CONFIRM.search(texto) is not None, (
        f"{asset.name} não declara JustWorksRepairing=confirm — o valor tem de "
        "ser explícito, não herdado do default da distro"
    )


def test_a_justificativa_do_always_ficou_registrada() -> None:
    """A decisão anterior era MEDIDA e não se apaga: ganha nota datada."""
    for asset in ASSETS_COM_A_CHAVE:
        texto = asset.read_text(encoding="utf-8")
        assert "RADIO-ABERTO-01" in texto, (
            f"{asset.name} mudou de valor sem registrar por quê e desde quando"
        )
        assert "always" in texto, (
            f"{asset.name} apagou a memória do valor anterior — a nota datada "
            "precisa dizer o que caducou"
        )
