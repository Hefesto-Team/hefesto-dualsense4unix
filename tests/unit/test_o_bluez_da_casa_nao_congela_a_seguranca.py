"""O BlueZ da distro ganha recado, e o da casa não congela a segurança.

O-BLUEZ-DA-CASA-NAO-CONGELA-A-SEGURANCA-01 (13/10/2026). Duas perguntas do
``scripts/doctor.sh``:

1. abaixo do piso 5.79 a severidade é ``warn`` com o EFEITO (o rádio pode cair; o
   cabo não depende disso), nunca ``fail``: Ubuntu 24.04, Mint 22 (5.72) e
   Debian 12 (5.66) caem aí na primeira corrida;
2. com o backport do Hefesto por cima, o ``apt`` nunca aplica a correção de
   segurança da distro (``5.86-…~hefesto`` é maior que ``5.72-0ubuntu5.N``), e o
   doctor lê a candidata da distro (``apt-cache policy``, só leitura) contra a
   base de onde o backport nasceu (o ``upgrade`` do próprio ``dpkg.log``).

Tudo com dublês em ``tmp_path``: nenhum ``apt``, ``dpkg`` ou log desta máquina.
"""

from __future__ import annotations

import gzip
import stat
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DOCTOR = ROOT / "scripts" / "doctor.sh"

BACKPORT = "5.86-0ubuntu0.1~hefesto24.04.4"
BASE = "5.72-0ubuntu5.4"

POLITICA = """\
bluez:
  Installed: {instalado}
  Candidate: {instalado}
  Version table:
 *** {instalado} 100
        100 /var/lib/dpkg/status
{linhas}"""


def _politica(*repo: str) -> str:
    fonte = "http://archive.ubuntu.com/ubuntu noble-updates/main amd64 Packages"
    linhas = "".join(f"     {v} 500\n        500 {fonte}\n" for v in repo)
    return POLITICA.format(instalado=BACKPORT, linhas=linhas)


def _bin(pasta: Path, nome: str, corpo: str) -> None:
    alvo = pasta / nome
    alvo.write_text(f"#!/usr/bin/env bash\n{corpo}\n", encoding="utf-8")
    alvo.chmod(alvo.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def _ambiente(
    tmp_path: Path,
    *,
    instalado: str,
    politica: str | None = None,
    log: str | None = None,
) -> dict[str, str]:
    """PATH com dublês de systemctl, dpkg-query e apt-cache; o log do dpkg desviado."""
    fake = tmp_path / "fakebin"
    fake.mkdir(exist_ok=True)
    _bin(fake, "systemctl", "exit 1")
    _bin(fake, "dpkg-query", f'printf "%s" "{instalado}"')
    if politica is None:
        _bin(fake, "apt-cache", "exit 1")
    else:
        (tmp_path / "politica.txt").write_text(politica, encoding="utf-8")
        _bin(fake, "apt-cache", f'cat "{tmp_path / "politica.txt"}"')
    alvo = tmp_path / "dpkg.log"
    alvo.write_text(log or "", encoding="utf-8")
    return {
        "PATH": f"{fake}:/usr/bin:/bin",
        "DOCTOR_SH": str(DOCTOR),
        "HEFESTO_DOCTOR_DPKG_LOG": str(alvo),
        # sem a linha do changelog (as revisões até a 4), a base é a do dpkg.log
        "HEFESTO_DOCTOR_BLUEZ_CHANGELOG": str(tmp_path / "sem-changelog.gz"),
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


def _linha_do_dpkg(velha: str = BASE, nova: str = BACKPORT) -> str:
    return (
        "2026-09-23 06:10:11 status installed bluez:amd64 " + velha + "\n"
        f"2026-09-23 06:10:12 upgrade bluez:amd64 {velha} {nova}\n"
    )


# ---------------------------------------------------------------- 1. a severidade


@pytest.mark.parametrize("vers", ["5.72-0ubuntu5.5", "5.66-1+deb12u2", "5.64-0ubuntu1.4"])
def test_abaixo_do_piso_e_aviso_com_o_efeito_e_nunca_falha(tmp_path: Path, vers: str) -> None:
    saida = _rodar("check_bluez_backport_version", _ambiente(tmp_path, instalado=vers))
    assert "[WARN]" in saida, saida
    assert "[FAIL]" not in saida, saida
    assert vers in saida
    assert "rádio" in saida and "pode cair" in saida
    assert "o cabo não depende disso" in saida
    assert "opção" in saida, "o backport é uma opção, não uma ordem"


def test_no_piso_nada_muda(tmp_path: Path) -> None:
    saida = _rodar("check_bluez_backport_version", _ambiente(tmp_path, instalado="5.79"))
    assert "[ OK ]" in saida and "[WARN]" not in saida and "[FAIL]" not in saida


# -------------------------------------------------- 2. a distro depois do backport


def test_a_distro_publicou_depois_do_backport_avisa_nomeando_as_duas_versoes(
    tmp_path: Path,
) -> None:
    env = _ambiente(
        tmp_path,
        instalado=BACKPORT,
        politica=_politica("5.72-0ubuntu5.6", "5.72-0ubuntu5.4"),
        log=_linha_do_dpkg(),
    )
    saida = _rodar("check_bluez_distro_depois_do_backport", env)
    assert "[WARN]" in saida, saida
    assert "5.72-0ubuntu5.6" in saida, "a candidata da distro"
    assert BASE in saida, "a base de onde o backport nasceu"
    assert "[ OK ]" not in saida
    assert "revisão nova" in saida
    assert "Reconstrua" not in saida, "o aviso aponta a receita, não manda reconstruir"


def test_a_candidata_e_a_maior_da_distro_e_nunca_a_nossa(tmp_path: Path) -> None:
    env = _ambiente(
        tmp_path,
        instalado=BACKPORT,
        politica=_politica("5.72-0ubuntu5", "5.72-0ubuntu5.6", "5.72-0ubuntu5.4"),
    )
    assert _rodar("_bluez_candidata_da_distro", env).strip() == "5.72-0ubuntu5.6"


def test_sem_repositorio_da_distro_nao_ha_candidata(tmp_path: Path) -> None:
    env = _ambiente(tmp_path, instalado=BACKPORT, politica=_politica())
    assert _rodar("_bluez_candidata_da_distro", env).strip() == ""
    assert _rodar("check_bluez_distro_depois_do_backport", env).strip() == ""


def test_a_distro_no_mesmo_ponto_da_base_passa(tmp_path: Path) -> None:
    env = _ambiente(
        tmp_path,
        instalado=BACKPORT,
        politica=_politica(BASE),
        log=_linha_do_dpkg(),
    )
    saida = _rodar("check_bluez_distro_depois_do_backport", env)
    assert "[ OK ]" in saida and "[WARN]" not in saida, saida


def test_sem_registro_da_base_diz_que_nao_sabe_e_nao_acusa(tmp_path: Path) -> None:
    env = _ambiente(tmp_path, instalado=BACKPORT, politica=_politica("5.72-0ubuntu5.6"))
    saida = _rodar("check_bluez_distro_depois_do_backport", env)
    assert "não achei de que versão da distro ele nasceu" in saida, saida
    assert "5.72-0ubuntu5.6" in saida
    assert "[WARN]" not in saida and "[FAIL]" not in saida and "[ OK ]" not in saida


def test_bluez_da_distro_sem_backport_nao_pergunta_nada(tmp_path: Path) -> None:
    env = _ambiente(
        tmp_path,
        instalado="5.72-0ubuntu5.5",
        politica=_politica("5.72-0ubuntu5.6"),
        log=_linha_do_dpkg(),
    )
    assert _rodar("check_bluez_distro_depois_do_backport", env).strip() == ""


def test_a_base_vem_do_log_rotacionado_em_gz(tmp_path: Path) -> None:
    env = _ambiente(tmp_path, instalado=BACKPORT)
    rotacionado = tmp_path / "dpkg.log.3.gz"
    rotacionado.write_bytes(gzip.compress(_linha_do_dpkg("5.72-0ubuntu5.2").encode()))
    env["HEFESTO_DOCTOR_DPKG_LOG"] = str(rotacionado)
    assert _rodar("_bluez_base_do_backport", env).strip() == "5.72-0ubuntu5.2"


def test_so_um_upgrade_para_o_backport_conta_como_base(tmp_path: Path) -> None:
    """Um `upgrade` entre versões da distro não é a origem do backport."""
    log = (
        "2026-05-01 10:00:00 upgrade bluez:amd64 5.72-0ubuntu5.2 5.72-0ubuntu5.3\n"
        + _linha_do_dpkg("5.72-0ubuntu5.3")
    )
    env = _ambiente(tmp_path, instalado=BACKPORT, log=log)
    assert _rodar("_bluez_base_do_backport", env).strip() == "5.72-0ubuntu5.3"


def test_a_checagem_de_versao_chama_a_da_distro(tmp_path: Path) -> None:
    """Ela entra no mesmo check que o doctor já roda, sem passo a mais no `main`."""
    env = _ambiente(
        tmp_path,
        instalado=BACKPORT,
        politica=_politica("5.72-0ubuntu5.6"),
        log=_linha_do_dpkg(),
    )
    saida = _rodar("check_bluez_backport_version", env)
    assert "5.72-0ubuntu5.6" in saida and "[WARN]" in saida, saida


def test_a_revisao_nova_do_backport_nao_vira_a_base(tmp_path: Path) -> None:
    """`.3` para `.4` é troca de revisão nossa: a base segue sendo a da distro."""
    log = _linha_do_dpkg(BASE, "5.86-0ubuntu0.1~hefesto24.04.3") + (
        "2026-10-02 09:00:00 upgrade bluez:amd64 5.86-0ubuntu0.1~hefesto24.04.3 " + BACKPORT + "\n"
    )
    env = _ambiente(tmp_path, instalado=BACKPORT, log=log)
    assert _rodar("_bluez_base_do_backport", env).strip() == BASE


def test_o_backport_servido_por_um_repositorio_nao_e_a_candidata_da_distro(
    tmp_path: Path,
) -> None:
    fonte = "http://repo.local/hefesto noble/main amd64 Packages"
    politica = _politica("5.72-0ubuntu5.6") + f"     {BACKPORT} 500\n        500 {fonte}\n"
    env = _ambiente(tmp_path, instalado=BACKPORT, politica=politica)
    assert _rodar("_bluez_candidata_da_distro", env).strip() == "5.72-0ubuntu5.6"
