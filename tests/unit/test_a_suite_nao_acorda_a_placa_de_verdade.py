"""A-SUITE-NAO-ACORDA-A-PLACA-DE-VERDADE-01: teste nenhum chega ao script de root.

O `assets/hefesto-launch.sh` chama `sudo -n <placa acordada> acordar` quando o
script instalado existe, e ele trava o clock da placa da máquina. O desvio único
mora no `tests/conftest.py`, no nascimento de todo filho; estas réguas provam que
ele alcança o filho de ambiente montado do zero, o de ambiente herdado e o
lançador de verdade, com um `sudo` de mentira que anota quem o chamou.
"""
from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

from tests.conftest import (
    PLACA_ACORDADA_DESVIADA,
    PLACA_ACORDADA_ENV,
    PLACA_ACORDADA_INSTALADA,
)

_RAIZ = Path(__file__).resolve().parents[2]
_LANCADOR = _RAIZ / "assets" / "hefesto-launch.sh"
_LER_A_VARIAVEL = f'printf "%s" "${{{PLACA_ACORDADA_ENV}-ausente}}"'


def _placa_que_o_filho_ve(env: dict[str, str] | None) -> str:
    feito = subprocess.run(
        ["/bin/sh", "-c", _LER_A_VARIAVEL], env=env,
        capture_output=True, text=True, timeout=10, check=True,
    )
    return feito.stdout


def test_o_filho_de_ambiente_montado_do_zero_herda_o_desvio() -> None:
    vista = _placa_que_o_filho_ve({"PATH": "/usr/bin:/bin"})
    assert vista == PLACA_ACORDADA_DESVIADA, (
        f"o filho de `env={{…}}` viu {vista!r}: o lançador cai no script instalado"
    )
    assert not os.access(vista, os.X_OK)


def test_o_filho_de_ambiente_herdado_herda_o_desvio() -> None:
    assert _placa_que_o_filho_ve(None) == PLACA_ACORDADA_DESVIADA


def test_o_caminho_instalado_posto_a_mao_tambem_se_desvia() -> None:
    vista = _placa_que_o_filho_ve(
        {"PATH": "/usr/bin:/bin", PLACA_ACORDADA_ENV: PLACA_ACORDADA_INSTALADA}
    )
    assert vista == PLACA_ACORDADA_DESVIADA


def test_o_duble_de_quem_testa_a_placa_continua_dele(tmp_path: Path) -> None:
    duble = str(tmp_path / "placa.sh")
    vista = _placa_que_o_filho_ve({"PATH": "/usr/bin:/bin", PLACA_ACORDADA_ENV: duble})
    assert vista == duble


def test_o_lancador_nao_chama_o_sudo_da_placa(tmp_path: Path) -> None:
    """O lançador inteiro, com o ambiente que os testes dele montam: sem `sudo`."""
    falsos = tmp_path / "bin"
    falsos.mkdir()
    registro = tmp_path / "sudo.log"
    (falsos / "sudo").write_text(
        f'#!/bin/sh\nprintf "%s\\n" "$*" >> "{registro}"\nexit 1\n', encoding="utf-8"
    )
    for mudo in ("system76-power", "busctl", "dbus-send"):
        (falsos / mudo).write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    for falso in falsos.iterdir():
        falso.chmod(0o755)
    (tmp_path / "run").mkdir()
    feito = subprocess.run(
        ["/bin/sh", str(_LANCADOR), "/bin/echo", "ABRIU"],
        env={
            "PATH": f"{falsos}:/usr/bin:/bin",
            "HOME": str(tmp_path),
            "XDG_RUNTIME_DIR": str(tmp_path / "run"),
            "XDG_STATE_HOME": str(tmp_path / "state"),
            "SteamAppId": "1599660",
            "HEFESTO_GM_POLL_SECS": "0.2",
        },
        capture_output=True, text=True, timeout=30, check=False,
    )
    assert "ABRIU" in feito.stdout, feito.stderr
    time.sleep(0.5)
    chamadas = registro.read_text(encoding="utf-8") if registro.exists() else ""
    assert "hefesto_placa_acordada" not in chamadas, (
        f"o lançador chamou o sudo da placa debaixo da suíte: {chamadas!r}"
    )
