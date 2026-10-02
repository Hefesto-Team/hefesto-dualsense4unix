"""O doctor sabe dizer se o alto-falante do controle ainda pode dormir."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

BASH = shutil.which("bash") or "/bin/bash"
RAIZ = Path(__file__).resolve().parents[2]
DOCTOR = RAIZ / "scripts" / "doctor.sh"
NOME = "54-hefesto-dualsense-alto-falante-nunca-dorme.conf"
ASSET = RAIZ / "assets" / "wireplumber" / NOME


def _doctor(casa: Path) -> str:
    r = subprocess.run(
        [BASH, "-c", f'source "{DOCTOR}"; check_dropin_do_alto_falante_acordado'],
        env={"PATH": "/usr/bin:/bin", "HOME": str(casa)},
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    return r.stdout + r.stderr


def _pasta(casa: Path) -> Path:
    pasta = casa / ".config" / "wireplumber" / "wireplumber.conf.d"
    pasta.mkdir(parents=True)
    return pasta


def test_sem_o_drop_in_avisa_e_diz_o_gesto(tmp_path: Path) -> None:
    saida = _doctor(tmp_path)
    assert "[WARN]" in saida and "pode dormir no cabo" in saida, saida
    assert "--nunca-dorme" in saida, "o aviso tem de dizer o gesto que cura"


def test_com_o_desta_versao_passa(tmp_path: Path) -> None:
    shutil.copy(ASSET, _pasta(tmp_path) / NOME)
    assert "[ OK ] o alto-falante do controle não dorme no cabo" in _doctor(tmp_path)


def test_com_o_de_outra_versao_avisa(tmp_path: Path) -> None:
    (_pasta(tmp_path) / NOME).write_text("# velho\n", encoding="utf-8")
    saida = _doctor(tmp_path)
    assert "[WARN]" in saida and "outra versão" in saida, saida


def test_o_nome_e_o_do_asset_e_o_main_pergunta() -> None:
    texto = DOCTOR.read_text(encoding="utf-8")
    assert ASSET.is_file(), "o asset do drop-in 54 mudou de nome — o doctor procuraria outro"
    assert f"local nome={NOME}" in texto
    assert "\n    check_dropin_do_alto_falante_acordado\n" in texto, (
        "o main do doctor não chama a conferência do drop-in 54"
    )
