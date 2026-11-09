"""O BlueZ da casa sobe para o 5.88, e o teto do doctor sobe junto.

O-BLUEZ-DA-CASA-SOBE-PARA-O-5-88-01 (09/11/2026). O 5.88 (05/11) já traz os doze commits do
master que a revisão 5 levava, o 5bc6aa79e entre eles (``git merge-base --is-ancestor``): eles
saem da série, a revisão 6 leva só o hefesto-0001 e o 0002, e o 5.88 de qualquer distro passa
no teto. O fixture ``tests/fixtures/bluez-5.88/recorte/`` guarda, do fonte do 5.88, só os trechos
que os doze patches tocam.

AS MORDIDAS (feitas na sprint, com a cura devolvida): o teto de volta a 5.87 reprova o caso do
5.88 de fora; um patch que o upstream já traz, deixado na série da R6, reprova o ``patch -F0``
sobre o recorte; o patch da casa sem a MARCA_ nem a linha UPSTREAM_ reprova o caso da série; o
alvo do install escrito à mão reprova o caso do alvo.
"""
from __future__ import annotations

import shutil
import stat
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
ASSETS = RAIZ / "assets" / "bluez-backport"
DOCTOR = RAIZ / "scripts" / "doctor.sh"
INSTALL = (RAIZ / "install.sh").read_text(encoding="utf-8")
RECORTE_588 = RAIZ / "tests" / "fixtures" / "bluez-5.88" / "recorte"
BASH = shutil.which("bash") or "/bin/bash"


def _baseline() -> dict[str, str]:
    valores = {}
    for linha in (ASSETS / "BASELINE").read_text(encoding="utf-8").splitlines():
        if linha and not linha.startswith("#") and "=" in linha:
            chave, valor = linha.split("=", 1)
            valores[chave] = valor
    return valores


def _exe(pasta: Path, nome: str, corpo: str) -> Path:
    pasta.mkdir(parents=True, exist_ok=True)
    alvo = pasta / nome
    alvo.write_text("#!/usr/bin/env bash\n" + corpo + "\n", encoding="utf-8")
    alvo.chmod(alvo.stat().st_mode | stat.S_IEXEC)
    return alvo


def _doctor_com_o_daemon(tmp_path: Path, versao: str) -> str:
    falsos = tmp_path / "falsos"
    daemon = _exe(falsos, "bluetoothd-da-distro", f'echo "{versao}"')
    _exe(falsos, "systemctl", f'echo "{{ path={daemon} ; argv[]={daemon} ; ignore_errors=no }}"')
    _exe(falsos, "dpkg-query", f'echo -n "{versao}-1"')
    feito = subprocess.run(
        [BASH, "-c", 'set --; source "$DOCTOR_SH"; check_bluez_backport_version; true'],
        capture_output=True, text=True, timeout=30, check=False,
        env={"PATH": f"{falsos}:/usr/bin:/bin", "DOCTOR_SH": str(DOCTOR)})
    assert feito.returncode == 0, feito.stderr
    return feito.stdout


@pytest.mark.skipif(shutil.which("dpkg") is None, reason="sem dpkg para comparar versões")
def test_o_5_88_de_qualquer_distro_passa_no_teto(tmp_path: Path) -> None:
    """Prova da D-0911-O-BLUEZ-DA-CASA-SOBE-PARA-O-5-88: o 5.88 sem as MARCA_ passa no teto."""
    saida = _doctor_com_o_daemon(tmp_path, "5.88")
    assert "[ OK ]" in saida and "[WARN]" not in saida, saida
    assert "5bc6aa79" in saida


@pytest.mark.skipif(shutil.which("dpkg") is None, reason="sem dpkg para comparar versões")
def test_o_5_87_de_fora_segue_barrado(tmp_path: Path) -> None:
    saida = _doctor_com_o_daemon(tmp_path, "5.87")
    assert "[WARN]" in saida and "dev_disconnected" in saida and "5.88" in saida, saida


def test_a_revisao_6_e_o_5_88_com_as_duas_da_casa() -> None:
    base = _baseline()
    assert base["VERSAO_UPSTREAM"] == "5.88"
    assert base["FONTE_UPSTREAM_URL"].endswith("/bluez-5.88.tar.xz")
    assert base["REVISAO_ULTIMA"] == "6"
    assert f"{base['VERSAO_BASE']}~hefesto24.04.6" == "5.88-0ubuntu0.1~hefesto24.04.6"
    for nome in base["PATCHES_R6"].split():
        curto = "-".join(nome.split("-")[:2])
        assert f"MARCA_{curto}" in base or f"UPSTREAM_{curto}" in base, (
            f"{nome} não tem a MARCA_ nem o motivo de não ter")
    entrada = (ASSETS / "debian" / "changelog.hefesto").read_text(encoding="utf-8")
    assert entrada.startswith("bluez (5.88-0ubuntu0.1~hefesto24.04.6) noble;")
    assert "Cobre a segurança da distro até: 5.72-0ubuntu5.8\n" in entrada.split("\n -- ", 1)[0]


def test_o_que_o_5_88_traz_sai_da_serie() -> None:
    base = _baseline()
    ja_no_upstream = base["NO_UPSTREAM_R6"].split()
    serie = {"-".join(n.split("-")[:2]) for n in base["PATCHES_R6"].split()}
    assert not serie & set(ja_no_upstream)
    assert set(ja_no_upstream) == {
        "-".join(n.split("-")[:2]) for n in base["PATCHES_R5"].split()[2:]}
    for curto in ja_no_upstream:
        assert f"UPSTREAM_{curto}" in base, curto


@pytest.mark.skipif(shutil.which("patch") is None, reason="sem o patch")
@pytest.mark.parametrize("curto", _baseline()["NO_UPSTREAM_R6"].split())
def test_o_patch_que_o_5_88_ja_traz_nao_aplica_sem_fuzz(tmp_path: Path, curto: str) -> None:
    arvore = tmp_path / "bluez-5.88"
    shutil.copytree(RECORTE_588, arvore)
    patch = next((ASSETS / "patches").glob(f"{curto}-*.patch"))
    feito = subprocess.run(["patch", "-p1", "-F0", "-N", "--dry-run", "-s"], cwd=arvore,
                           input=patch.read_bytes(), capture_output=True, timeout=30)
    assert feito.returncode != 0, f"{patch.name} aplicaria sobre o 5.88: não saiu da série"


def test_o_alvo_e_o_rotulo_do_3f_seguem_o_baseline(tmp_path: Path) -> None:
    passo = INSTALL[INSTALL.index('    _bz_baseline="${ROOT_DIR}/assets/bluez-backport/BASELINE"'):]
    linhas = passo.splitlines()[1:3]
    assert linhas[0].strip().startswith("_BZ_TARGET=") and 'step "3f"' in linhas[1]
    script = ("step() { printf '%s\\n' \"$2\"; }\n"
              + INSTALL[INSTALL.index("_bz_do_baseline() {"):].split("\n}\n", 1)[0] + "\n}\n"
              + "\n".join(linhas) + '\nprintf "%s\\n" "${_BZ_TARGET}"\n')
    feito = subprocess.run([BASH, "-c", script], capture_output=True, text=True, timeout=30,
                           env={"ROOT_DIR": str(RAIZ), "PATH": "/usr/bin:/bin"})
    assert feito.stdout.splitlines() == [
        "BlueZ corrigido (5.88 com as correções de segurança: sem os travamentos, o laço de "
        "reconexão e a queda por buffer cheio)",
        "5.88-0ubuntu0.1~hefesto24.04.6",
    ], feito.stdout + feito.stderr
