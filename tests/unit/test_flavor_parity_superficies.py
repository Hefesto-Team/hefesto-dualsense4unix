"""A máscara padrão tem de ser a MESMA em toda porta de entrada (HARM-08).

Achado da auditoria de harmonia (2026-07-15): o mesmo gesto ligava máscaras
diferentes conforme por onde a pessoa entrasse —

  - daemon/GUI: ``xbox``   (`uinput_gamepad.DEFAULT_FLAVOR`, desde SPRINT-GAME-RUMBLE-01)
  - CLI:        ``dualsense``  (default hardcoded em `cmd_gamepad.cmd_on`)

Como a máscara DualSense não vibra na maioria dos jogos (o vpad de uinput não tem
hidraw — ver SPRINT-UHID-VPAD-01), um `gamepad on` pela CLI **matava o rumble** de
quem tinha Xbox configurado, em silêncio.
"""
from __future__ import annotations

import re
from pathlib import Path

from hefesto_dualsense4unix.integrations import uinput_gamepad as ug


def test_cli_nao_tem_default_de_mascara_hardcoded() -> None:
    """`gamepad on` sem --flavor tem de PRESERVAR a máscara atual (não escolher uma)."""
    from hefesto_dualsense4unix.cli import cmd_gamepad

    fonte = Path(cmd_gamepad.__file__).read_text(encoding="utf-8")
    assert 'typer.Option(\n        "dualsense"' not in fonte
    assert 'typer.Option("dualsense"' not in fonte


def test_o_default_e_o_que_vibra() -> None:
    """Se um dia inverter, é para ser decisão consciente — não regressão."""
    assert ug.DEFAULT_FLAVOR == "xbox"


def test_ninguem_em_python_redefine_o_default() -> None:
    """Um dono só: os outros módulos REEXPORTAM, não redefinem."""
    raiz = Path(__file__).resolve().parents[2] / "src" / "hefesto_dualsense4unix"
    donos = [
        py.relative_to(raiz).as_posix()
        for py in raiz.rglob("*.py")
        if re.search(r'^DEFAULT_FLAVOR\s*=\s*["\']', py.read_text(encoding="utf-8"),
                     re.MULTILINE)
    ]

    assert donos == ["integrations/uinput_gamepad.py"], (
        f"mais de um módulo define DEFAULT_FLAVOR: {donos} — reexporte do "
        f"uinput_gamepad em vez de redefinir"
    )


def test_mode_transition_usa_o_mesmo_default() -> None:
    from hefesto_dualsense4unix.app.actions import mode_transition

    assert mode_transition.DEFAULT_FLAVOR == ug.DEFAULT_FLAVOR
