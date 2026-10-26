"""O BlueZ da casa leva as correções de segurança, e o doctor sabe ler isso.

O-BLUEZ-DA-CASA-LEVA-AS-CORRECOES-DE-SEGURANCA-01 (15/10/2026). A revisão 5 do
backport é o upstream 5.87 com os commits do master que ele não tem (os CVE de
a2dp, avrcp, sdp-xml e eir, e o ``5bc6aa79`` do uso-depois-de-liberado), e o
changelog dela escreve duas linhas que o ``scripts/doctor.sh`` lê:

1. «Cobre a segurança da distro até: <versão>» é a base contra a qual a
   candidata da distro se compara (sem ela, a base é a do ``dpkg.log``);
2. «Leva do upstream: <commits>» deixa o 5.87 da casa passar pelo teto que barra
   o 5.87 de fora.

Tudo com dublês em ``tmp_path``: nenhum ``apt``, ``dpkg``, log ou changelog desta
máquina.
"""

from __future__ import annotations

import gzip
import hashlib
import os
import re
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DOCTOR = ROOT / "scripts" / "doctor.sh"
SCRIPT = ROOT / "scripts" / "construir_bluez_backport.sh"
ASSETS = ROOT / "assets" / "bluez-backport"
CHANGELOG_HEFESTO = ASSETS / "debian" / "changelog.hefesto"

R5 = "5.87-0ubuntu0.1~hefesto24.04.5"
R4 = "5.86-0ubuntu0.1~hefesto24.04.4"
COBERTA = "5.72-0ubuntu5.8"
BASE_DO_DPKG = "5.72-0ubuntu5.4"


def _baseline() -> dict[str, str]:
    valores: dict[str, str] = {}
    for linha in (ASSETS / "BASELINE").read_text(encoding="utf-8").splitlines():
        if linha and not linha.startswith("#") and "=" in linha:
            chave, valor = linha.split("=", 1)
            valores[chave] = valor
    return valores


def _entrada_de_cima(versao: str) -> str:
    """A entrada do changelog.hefesto daquela versão, como o pacote a instala."""
    texto = CHANGELOG_HEFESTO.read_text(encoding="utf-8")
    inicio = texto.index(f"bluez ({versao}) noble;")
    fim = texto.index("\n -- ", inicio)
    return texto[inicio : texto.index("\n", fim + 1) + 1]


def _bin(pasta: Path, nome: str, corpo: str) -> Path:
    alvo = pasta / nome
    alvo.write_text(f"#!/usr/bin/env bash\n{corpo}\n", encoding="utf-8")
    alvo.chmod(alvo.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return alvo


def _politica(instalado: str, *repo: str) -> str:
    fonte = "http://archive.ubuntu.com/ubuntu noble-updates/main amd64 Packages"
    linhas = "".join(f"     {v} 500\n        500 {fonte}\n" for v in repo)
    return (
        f"bluez:\n  Installed: {instalado}\n  Candidate: {instalado}\n  Version table:\n"
        f" *** {instalado} 100\n        100 /var/lib/dpkg/status\n{linhas}"
    )


def _ambiente(
    tmp_path: Path,
    *,
    pacote: str,
    changelog: str | None,
    candidatas: tuple[str, ...] = (),
    daemon: str | None = None,
) -> dict[str, str]:
    """systemctl, dpkg-query, apt-cache e o bluetoothd de mentira; log e changelog desviados."""
    fake = tmp_path / "fakebin"
    fake.mkdir(exist_ok=True)
    if daemon is None:
        _bin(fake, "systemctl", "exit 1")
    else:
        vivo = _bin(fake, "bluetoothd-falso", f'echo "{daemon}"')
        _bin(fake, "systemctl", f'echo "{{ path={vivo} ; argv[]={vivo} ; ignore_errors=no }}"')
    _bin(fake, "dpkg-query", f'printf "%s" "{pacote}"')
    (tmp_path / "politica.txt").write_text(_politica(pacote, *candidatas), encoding="utf-8")
    _bin(fake, "apt-cache", f'cat "{tmp_path / "politica.txt"}"')
    log = tmp_path / "dpkg.log"
    log.write_text(
        f"2026-10-15 06:10:12 upgrade bluez:amd64 {BASE_DO_DPKG} {pacote}\n", encoding="utf-8"
    )
    alvo = tmp_path / "changelog.Debian.gz"
    if changelog is not None:
        alvo.write_bytes(gzip.compress(changelog.encode("utf-8")))
    return {
        "PATH": f"{fake}:/usr/bin:/bin",
        "DOCTOR_SH": str(DOCTOR),
        "HEFESTO_DOCTOR_DPKG_LOG": str(log),
        "HEFESTO_DOCTOR_BLUEZ_CHANGELOG": str(alvo),
    }


def _rodar(corpo: str, env: dict[str, str]) -> str:
    res = subprocess.run(
        ["bash", "-c", f'set --; source "$DOCTOR_SH"; {corpo}; true'],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env=env,
    )
    assert res.returncode == 0, res.stderr
    return res.stdout


def test_o_changelog_da_r5_diz_o_que_cobre_e_o_que_leva() -> None:
    entrada = _entrada_de_cima(R5)
    assert CHANGELOG_HEFESTO.read_text(encoding="utf-8").startswith(f"bluez ({R5}) noble;")
    assert f"Cobre a segurança da distro até: {COBERTA}\n" in entrada
    for cve in (
        "CVE-2026-19774",
        "CVE-2026-75032",
        "CVE-2026-80185",
        "CVE-2026-80186",
        "CVE-2026-85218",
    ):
        assert cve in entrada, cve
    leva = re.search(r"Leva do upstream: (.+)\n", entrada)
    assert leva, entrada
    assert leva.group(1).split()[0].startswith("5bc6aa79")


def test_a_lista_do_changelog_e_a_dos_patches_do_upstream() -> None:
    """Cada commit que o changelog diz levar é um patch da série, na mesma ordem."""
    base = _baseline()
    commits = [
        base[f"UPSTREAM_{'-'.join(nome.split('-')[:2])}"].split()[0]
        for nome in base["PATCHES_R5"].split()
        if f"UPSTREAM_{'-'.join(nome.split('-')[:2])}" in base
    ]
    assert len(commits) == 12
    leva = re.search(r"Leva do upstream: (.+)\n", _entrada_de_cima(R5))
    assert leva
    curtos = leva.group(1).split()
    assert len(curtos) == len(commits)
    for curto, inteiro in zip(curtos, commits, strict=True):
        assert inteiro.startswith(curto), (curto, inteiro)


@pytest.mark.parametrize("nome", _baseline()["PATCHES_R5"].split()[2:])
def test_cada_patch_do_upstream_abre_com_o_commit_e_tem_o_hash_do_baseline(nome: str) -> None:
    chave = "UPSTREAM_" + "-".join(nome.split("-")[:2])
    commit, sha = _baseline()[chave].split()
    arquivo = ASSETS / "patches" / nome
    assert arquivo.read_text(encoding="utf-8").startswith(f"From {commit} ")
    assert hashlib.sha256(arquivo.read_bytes()).hexdigest() == sha


def test_a_distro_no_ponto_que_a_casa_cobre_passa(tmp_path: Path) -> None:
    """O dpkg.log diz 5.4, mas o changelog diz que a R5 cobre até o 5.8."""
    env = _ambiente(tmp_path, pacote=R5, changelog=_entrada_de_cima(R5), candidatas=(COBERTA,))
    saida = _rodar("check_bluez_distro_depois_do_backport", env)
    assert "[ OK ]" in saida and "[WARN]" not in saida, saida
    assert COBERTA in saida


def test_a_distro_alem_do_que_a_casa_cobre_pede_revisao_nova(tmp_path: Path) -> None:
    env = _ambiente(
        tmp_path, pacote=R5, changelog=_entrada_de_cima(R5), candidatas=("5.72-0ubuntu5.9",)
    )
    saida = _rodar("check_bluez_distro_depois_do_backport", env)
    assert "[WARN]" in saida, saida
    assert "5.72-0ubuntu5.9" in saida and COBERTA in saida
    assert "revisão nova" in saida
    assert "Reconstrua" not in saida


def test_sem_a_linha_a_base_e_a_do_dpkg_log(tmp_path: Path) -> None:
    """As revisões até a 4 não escrevem a linha: vale o dpkg.log, como antes."""
    env = _ambiente(tmp_path, pacote=R4, changelog=_entrada_de_cima(R4), candidatas=(COBERTA,))
    saida = _rodar("check_bluez_distro_depois_do_backport", env)
    assert "[WARN]" in saida and BASE_DO_DPKG in saida, saida


def test_so_a_entrada_de_cima_conta(tmp_path: Path) -> None:
    """Uma revisão futura sem a linha não herda a cobertura da R5 de baixo."""
    futura = (
        "bluez (5.88-0ubuntu0.1~hefesto24.04.6) noble; urgency=medium\n\n"
        "  * sem a linha.\n\n"
        " -- Bancada <bancada@example.invalid>  Thu, 15 Oct 2026 06:00:00 -0300\n\n"
    )
    pergunta = '_bluez_linha_do_changelog "Cobre a segurança da distro até"'
    env = _ambiente(tmp_path, pacote=R5, changelog=futura + _entrada_de_cima(R5))
    assert _rodar(pergunta, env).strip() == ""
    env = _ambiente(tmp_path, pacote=R5, changelog=_entrada_de_cima(R5))
    assert _rodar(pergunta, env).strip() == COBERTA


def test_o_5_87_da_casa_passa_no_teto(tmp_path: Path) -> None:
    env = _ambiente(tmp_path, pacote=R5, changelog=_entrada_de_cima(R5), daemon="5.87")
    saida = _rodar("check_bluez_backport_version", env)
    assert "[ OK ]" in saida and "5bc6aa79" in saida, saida
    assert "uso-depois-de-liberado" in saida
    assert "[WARN]" not in saida.split("\n", 1)[0]


@pytest.mark.parametrize(
    ("caso", "pacote", "com_changelog"),
    [
        ("o_5_87_de_fora", "5.87-0ubuntu1", True),
        ("o_da_casa_sem_a_linha", R5, False),
        ("o_daemon_e_outro_upstream", R4, True),
    ],
)
def test_o_5_87_que_nao_leva_o_5bc6aa79_segue_barrado(
    tmp_path: Path, caso: str, pacote: str, com_changelog: bool
) -> None:
    env = _ambiente(
        tmp_path,
        pacote=pacote,
        changelog=_entrada_de_cima(R5) if com_changelog else None,
        daemon="5.87",
    )
    primeira = _rodar("check_bluez_backport_version", env).splitlines()[0]
    assert "[WARN]" in primeira and "dev_disconnected" in primeira, (caso, primeira)


def _conferir(tmp_path: Path, patch: Path) -> subprocess.CompletedProcess[str]:
    linhas = SCRIPT.read_text(encoding="utf-8").rstrip("\n").split("\n")
    assert linhas[-1] == 'main "$@"'
    sem_main = tmp_path / "sem_main.sh"
    sem_main.write_text("\n".join(linhas[:-1]) + "\n", encoding="utf-8")
    env = dict(os.environ)
    env["HEFESTO_BLUEZ_CACHE"] = str(tmp_path / "cache")
    env["HEFESTO_BLUEZ_BASELINE"] = str(ASSETS / "BASELINE")
    return subprocess.run(
        ["bash", "-c", f"source '{sem_main}'; conferir_patch_do_upstream '{patch}'"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env=env,
    )


def test_o_script_recusa_o_patch_do_upstream_mexido(tmp_path: Path) -> None:
    nome = _baseline()["PATCHES_R5"].split()[2]
    copia = tmp_path / "patches" / nome
    copia.parent.mkdir()
    shutil.copyfile(ASSETS / "patches" / nome, copia)
    proc = _conferir(tmp_path, copia)
    assert proc.returncode == 0 and not proc.stderr, proc.stderr
    copia.write_bytes(copia.read_bytes() + b"\n")
    proc = _conferir(tmp_path, copia)
    assert proc.returncode == 5, proc.stdout + proc.stderr
    assert "o BASELINE diz" in proc.stderr
