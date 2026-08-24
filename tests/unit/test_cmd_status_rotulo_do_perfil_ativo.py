"""ONDA0-Z5/T13 [PROVISÓRIO — D-N] — o rótulo da CLI nomeia o que responde.

`hefesto-dualsense4unix status` mostrava a linha crua ``active_profile`` sem
dizer que ela é a rota "em vigor agora" — das TRÊS que guardam "perfil
ativo" na casa, as outras duas (`session.json`, `active_profile.txt`)
respondem "a última escolha" e podem divergir por decisão medida (§2.8 da
ONDA0-Z5). Este teste prova só o rótulo — não decide qual rota "vence"
quando elas divergem (isso é D-N, dela).
"""
from __future__ import annotations

import pytest
from rich.console import Console

from hefesto_dualsense4unix.cli import cmd_status


async def _status_falso() -> dict[str, object]:
    return {
        "connected": True,
        "transport": "usb",
        "active_profile": "vitoria",
        "battery_pct": 80,
    }


def test_a_linha_de_active_profile_diz_em_vigor_agora(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cmd_status, "_daemon_status_via_ipc", _status_falso)
    console_gravado = Console(record=True, width=120)
    monkeypatch.setattr(cmd_status, "console", console_gravado)

    cmd_status.status_cmd()

    saida = console_gravado.export_text()
    assert "active_profile (em vigor agora)" in saida, saida
    # A linha crua antiga, sem explicação, some — não pode sobrar as duas.
    linhas = [linha for linha in saida.splitlines() if "active_profile" in linha]
    assert len(linhas) == 1, f"linha de active_profile duplicada/ambígua: {linhas}"
