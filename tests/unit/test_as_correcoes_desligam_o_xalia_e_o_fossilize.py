"""O xalia fica fora de todo jogo — AS-CORRECOES-AUTOMATICAS-DESLIGAM-O-XALIA-E-O-FOSSILIZE-01.

Ela, 01/10: *«Fossilize e xalia entram no botão de aplicar correções
automáticas de qualquer forma.»* <!-- noqa-acento: citação literal dela -->

O `proton` liga o xalia quando `PROTON_USE_XALIA` não está no ambiente. Medido
no Pro Jank Footy: 135 quadros acima de 20 ms com ele, 28 sem. A régua roda o
lançador DE VERDADE num lar de mentira, com o `env` no lugar do jogo.

A MORDIDA: troque o `xf_envs="PROTON_USE_XALIA=0"` de `xalia_fora` em
`assets/hefesto-launch.sh` por `xf_envs=""` e
`test_todo_jogo_nasce_sem_o_xalia` reprova.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import lista_de_exclusao

RAIZ = Path(__file__).resolve().parents[2]
LANCADOR = RAIZ / "assets" / "hefesto-launch.sh"


@pytest.fixture
def lar(tmp_path: Path) -> Path:
    """Casa, config e estado de mentira, e o Game Mode mudo na frente do PATH."""
    casa = tmp_path / "casa"
    (casa / ".config").mkdir(parents=True)
    mudos = tmp_path / "mudos"
    mudos.mkdir()
    for nome in ("system76-power", "busctl", "dbus-send"):
        falso = mudos / nome
        falso.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        falso.chmod(0o755)
    assert not str(casa).startswith("/home/"), "o lar de mentira caiu numa casa de verdade"
    return tmp_path


def _lancar(lar: Path, **extra: str) -> dict[str, str]:
    ambiente = {
        "HOME": str(lar / "casa"),
        "XDG_CONFIG_HOME": str(lar / "casa" / ".config"),
        "XDG_STATE_HOME": str(lar / "estado"),
        "XDG_RUNTIME_DIR": str(lar / "runtime"),
        "PATH": f"{lar / 'mudos'}:/usr/bin:/bin",
        **extra,
    }
    saida = subprocess.run(
        ["sh", str(LANCADOR), "/usr/bin/env"],
        env=ambiente, capture_output=True, text=True, timeout=60, check=False,
    )
    assert saida.returncode == 0, saida.stderr
    visto: dict[str, str] = {}
    for linha in saida.stdout.splitlines():
        chave, _, valor = linha.partition("=")
        visto[chave] = valor
    return visto


def test_todo_jogo_nasce_sem_o_xalia(lar: Path) -> None:
    """Sem daemon e sem escolha gravada: o jogo recebe `PROTON_USE_XALIA=0`."""
    visto = _lancar(lar, SteamAppId="3621330")
    assert visto.get("PROTON_USE_XALIA") == "0", (
        "o lançador não desligou o xalia, e o proton o liga sozinho: "
        f"{visto.get('PROTON_USE_XALIA')!r}")


def test_o_jogo_sem_appid_tambem(lar: Path) -> None:
    """Um jogo de fora da Steam, sem `SteamAppId`, recebe o mesmo."""
    assert _lancar(lar).get("PROTON_USE_XALIA") == "0"


def test_a_launch_option_dela_manda(lar: Path) -> None:
    """Quem já pôs `PROTON_USE_XALIA` no ambiente não é sobrescrito."""
    assert _lancar(lar, SteamAppId="3621330", PROTON_USE_XALIA="1")["PROTON_USE_XALIA"] == "1"


def test_o_jogo_da_lista_de_exclusao_abre_como_sem_o_hefesto(lar: Path) -> None:
    """A lista de exclusão vale antes de tudo: nenhuma env do Hefesto."""
    status = lista_de_exclusao.adicionar(
        "steam_app_3621330", lancador="steam", nome="Pro Jank Footy",
        config_home=lar / "casa" / ".config")
    assert status == "adicionado", status
    assert "PROTON_USE_XALIA" not in _lancar(lar, SteamAppId="3621330")
