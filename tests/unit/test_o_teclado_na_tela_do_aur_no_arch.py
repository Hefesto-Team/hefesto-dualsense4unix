from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

BASH = shutil.which("bash") or "/bin/bash"
RAIZ = Path(__file__).resolve().parents[2]
DONO = RAIZ / "scripts" / "install_osk.sh"
DOCTOR = RAIZ / "scripts" / "doctor.sh"
FERRAMENTAS = ("mkdir", "dirname", "date", "mv", "sed", "head", "tail", "cat", "mktemp", "rm")


def _pasta(tmp_path: Path, pacman_rc: int, ajudante: str = "") -> Path:
    pasta = tmp_path / "bin"
    pasta.mkdir()
    for nome in FERRAMENTAS:
        alvo = shutil.which(nome)
        if alvo:
            (pasta / nome).symlink_to(alvo)
    (pasta / "pacman").write_text(f"#!/bin/sh\nexit {pacman_rc}\n", encoding="utf-8")
    (pasta / "sudo").write_text(
        f'#!/bin/sh\necho "$@" >> "{tmp_path}/sudo.log"\nexit 0\n', encoding="utf-8"
    )
    for nome in ("pacman", "sudo"):
        (pasta / nome).chmod(0o755)
    if ajudante:
        (pasta / ajudante).write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        (pasta / ajudante).chmod(0o755)
    return pasta


def _roda_dono(tmp_path: Path, pasta: Path, dry_run: str = "0") -> tuple[str, dict[str, str]]:
    sentinela = tmp_path / "teclado.conf"
    env = {
        "PATH": str(pasta),
        "HOME": str(tmp_path),
        "HEFESTO_OSK_STATE": str(sentinela),
        "HEFESTO_OSK_SESSAO": "wayland",
        "HEFESTO_OSK_GERENCIADOR": "pacman",
        "HEFESTO_OSK_INSTALADO": "nenhum",
        "HEFESTO_OSK_DRY_RUN": dry_run,
    }
    feito = subprocess.run(
        [BASH, str(DONO), "--yes"], capture_output=True, text=True, env=env, timeout=60
    )
    assert feito.returncode == 0, feito.stderr
    gravado = dict(
        linha.split("=", 1)
        for linha in sentinela.read_text(encoding="utf-8").splitlines()
        if "=" in linha and not linha.startswith("#")
    )
    return feito.stdout + feito.stderr, gravado


def test_fora_dos_repositorios_o_dono_diz_o_aur_e_nao_chama_o_pacman(tmp_path: Path) -> None:
    saida, gravado = _roda_dono(tmp_path, _pasta(tmp_path, pacman_rc=1))
    assert gravado["motivo"] == "so-no-aur"
    assert "mora no AUR" in saida
    assert "paru -S wvkbd" in saida
    assert not (tmp_path / "sudo.log").exists()


def test_com_o_yay_na_maquina_o_comando_e_o_dele(tmp_path: Path) -> None:
    saida, _ = _roda_dono(tmp_path, _pasta(tmp_path, pacman_rc=1, ajudante="yay"))
    assert "rode: yay -S wvkbd" in saida


def test_no_repositorio_oficial_segue_pelo_pacman(tmp_path: Path) -> None:
    _, gravado = _roda_dono(tmp_path, _pasta(tmp_path, pacman_rc=0), dry_run="1")
    assert gravado["resultado"] == "dry-run"


def _roda_doctor(tmp_path: Path, pacman_rc: int, sentinela: str) -> str:
    pasta = _pasta(tmp_path, pacman_rc)
    lar = tmp_path / "lar"
    estado = lar / ".local" / "state" / "hefesto-dualsense4unix"
    estado.mkdir(parents=True)
    (estado / "teclado-na-tela.conf").write_text(sentinela, encoding="utf-8")
    env = dict(os.environ)
    env.update({"HOME": str(lar), "PATH": str(pasta), "WAYLAND_DISPLAY": "wayland-1"})
    feito = subprocess.run(
        [BASH, "-c", f"source '{DOCTOR}'; check_teclado_na_tela"],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    return feito.stdout


def test_o_doctor_avisa_o_aur_sem_dar_falha(tmp_path: Path) -> None:
    saida = _roda_doctor(
        tmp_path,
        1,
        "resultado=falhou\npacote=wvkbd\nmotivo=so-no-aur\ndata=2026-11-14T18:00:00\n",
    )
    assert "[FAIL]" not in saida
    assert "mora no AUR" in saida
    assert "paru -S wvkbd" in saida


def test_o_doctor_segue_falhando_quando_o_pacman_falhou_de_verdade(tmp_path: Path) -> None:
    saida = _roda_doctor(
        tmp_path,
        0,
        "resultado=falhou\npacote=wvkbd\nmotivo=gerenciador-falhou\ndata=2026-11-14T18:00:00\n",
    )
    assert "[FAIL]" in saida
    assert "sudo pacman -S wvkbd" in saida
