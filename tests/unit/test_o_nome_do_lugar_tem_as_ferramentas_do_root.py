"""O install confere que o root tem as três ferramentas do nome do lugar."""

from __future__ import annotations

import shutil
import stat
import subprocess
from pathlib import Path

BASH = shutil.which("bash") or "/bin/bash"
RAIZ = Path(__file__).resolve().parents[2]
CAMADA = RAIZ / "scripts" / "lib" / "camada_de_maquina.sh"


def _faltam(tmp_path: Path, presentes: tuple[str, ...]) -> list[str]:
    pasta = tmp_path / "bin-do-root"
    pasta.mkdir()
    for nome in presentes:
        alvo = pasta / nome
        alvo.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        alvo.chmod(alvo.stat().st_mode | stat.S_IEXEC)
    r = subprocess.run(
        [
            BASH,
            "-c",
            f'ROOT_DIR="{RAIZ}"; source "{CAMADA}"; '
            f'_ferramentas_que_faltam_ao_nome_do_lugar "{pasta}"',
        ],
        env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)},
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert r.returncode == 0, r.stderr
    return r.stdout.split()


def test_com_as_tres_nada_falta(tmp_path: Path) -> None:
    assert _faltam(tmp_path, ("python3", "udevadm", "getent")) == []


def test_sem_o_udevadm_ele_e_nomeado(tmp_path: Path) -> None:
    assert _faltam(tmp_path, ("python3", "getent")) == ["udevadm"]


def test_a_resiliencia_recopia_o_script_e_confere_as_ferramentas() -> None:
    texto = CAMADA.read_text(encoding="utf-8")
    inicio = texto.index("\ninstall_bt_resilience_host() {\n")
    corpo = texto[inicio : texto.index("\n}\n", inicio)]
    assert "bt_active_mode.sh" in corpo.split("for _btres_s in", 1)[1].split("\n", 1)[0], (
        "o laço da resiliência deixou de recopiar o bt_active_mode.sh"
    )
    assert "_ferramentas_que_faltam_ao_nome_do_lugar" in corpo, (
        "o install deixou de conferir python3/udevadm/getent no PATH do root"
    )
