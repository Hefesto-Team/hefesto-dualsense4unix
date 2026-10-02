"""Os ícones do projeto têm de refletir o SVG canônico."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
SVG = RAIZ / "assets" / "hefesto-logo.svg"
GERADOR = RAIZ / "scripts" / "gerar_icones.sh"

DERIVADOS = (
    "packaging/cosmic-applet/data/icons/hicolor/256x256/apps/"
    "com.vitoriamaria.HefestoDualsense4Unix.png",
    "assets/appimage/Hefesto-Dualsense4Unix.png",
)


def test_a_fonte_canonica_existe() -> None:
    """Sem ela, todo o resto é órfão."""
    assert SVG.is_file(), (
        f"{SVG.relative_to(RAIZ)} sumiu — é a fonte canônica de todos os "
        "ícones do projeto."
    )


def test_o_gerador_existe_e_e_executavel() -> None:
    assert GERADOR.is_file(), "scripts/gerar_icones.sh sumiu"
    import os

    assert os.access(GERADOR, os.X_OK), "scripts/gerar_icones.sh perdeu o +x"


@pytest.mark.parametrize("relativo", DERIVADOS)
def test_o_derivado_existe(relativo: str) -> None:
    """O `install.sh` copia estes caminhos. Ausente = `cp` falhando em silêncio."""
    caminho = RAIZ / relativo

    assert caminho.is_file(), (
        f"{relativo} não existe, e o install.sh o copia. Rode: "
        "scripts/gerar_icones.sh"
    )


def test_todo_derivado_esta_no_gerador() -> None:
    """Um destino que o teste conhece e o gerador não seria eterno órfão."""
    fonte = GERADOR.read_text(encoding="utf-8")
    faltando = [rel for rel in DERIVADOS if rel not in fonte]

    assert not faltando, (
        f"o gerador não conhece: {', '.join(faltando)}. Acrescente-os em "
        "DESTINOS, ou eles nunca vão refletir o SVG."
    )


@pytest.mark.skipif(
    shutil.which("rsvg-convert") is None or shutil.which("compare") is None,
    reason="precisa de librsvg2-bin e imagemagick para comparar pixel a pixel",
)
def test_os_icones_refletem_o_svg() -> None:
    """A mordida: mexer no SVG sem rodar o gerador reprova AQUI."""
    resultado = subprocess.run(
        [str(GERADOR), "--check"],
        capture_output=True,
        text=True,
        cwd=RAIZ,
    )

    assert resultado.returncode == 0, (
        "os ícones não refletem mais o SVG:\n"
        f"{resultado.stdout}{resultado.stderr}\n"
        "Alguém mexeu no desenho e não rodou `scripts/gerar_icones.sh`."
    )
