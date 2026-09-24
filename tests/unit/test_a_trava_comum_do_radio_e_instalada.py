"""A trava comum do rádio: o install a cria, na ordem certa, e o doctor sabe dizer.

INSTALL-E-UNINSTALL-DO-RADIO-01 (23/09/2026), o pedido P-2 da O-DIARIO-DO-RADIO-01:
o watchdog do Bluetooth (root) e o daemon (a sessão) só se põem em fila se
abrirem o MESMO arquivo, `/run/hefesto-dualsense4unix/radio.lock` — e até esta
sprint ninguém o criava. Medido na máquina dela em 23/09: a pasta não existia.

O que se tranca aqui:

1. o `install_trava_do_radio_host` grava o `tmpfiles.d` e o APLICA na hora, e
   respeita o `--no-udev` e a falta do grupo `hefesto` (sem ele o `tmpfiles`
   recusaria a linha);
2. a posição: ANTES da resiliência nos dois lados da cerca — a resiliência roda
   o `bt_active_mode.sh` como root na hora, e ele abre a trava; com a pasta de
   pé e o arquivo ausente, o root o criaria 0644 root:root;
3. o asset diz o que a sprint pediu: pasta 0755 do root, arquivo 0660 com o
   grupo `hefesto` (0664 deixaria qualquer conta segurar a trava);
4. o `doctor` distingue as quatro respostas, e a pasta gravável pela sessão é
   FALHA, não aviso.

A MORDIDA, medida: trocar a ordem das duas chamadas do lado nativo reprova o
teste 2; trocar o 0660 do asset por 0664, o 3; tirar o `fail` da pasta
gravável do doctor, o 4.
"""

from __future__ import annotations

import grp
import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

BASH = shutil.which("bash") or "/bin/bash"
RAIZ = Path(__file__).resolve().parents[2]
INSTALL = (RAIZ / "install.sh").read_text(encoding="utf-8")
CAMADA = RAIZ / "scripts" / "lib" / "camada_de_maquina.sh"
DOCTOR = RAIZ / "scripts" / "doctor.sh"
ASSET = RAIZ / "assets" / "tmpfiles.d" / "hefesto-dualsense4unix-radio.conf"


def _fake(pasta: Path, nome: str, corpo: str) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    alvo = pasta / nome
    alvo.write_text("#!/bin/sh\n" + corpo, encoding="utf-8")
    alvo.chmod(alvo.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def _roda_a_cura(tmp_path: Path, *, skip_udev: int = 0, tem_grupo: bool = True):
    fakes = tmp_path / "fakes"
    diario = tmp_path / "chamadas.log"
    _fake(fakes, "sudo", f'printf "sudo %s\\n" "$*" >> "{diario}"\nexit 0\n')
    _fake(fakes, "systemd-tmpfiles", "exit 0\n")
    _fake(fakes, "getent", f"exit {0 if tem_grupo else 2}\n")
    script = (
        "set -euo pipefail\n"
        f'ROOT_DIR="{RAIZ}"\n'
        f"SKIP_UDEV={skip_udev}\n"
        f'source "{CAMADA}"\n'
        "install_trava_do_radio_host\n"
    )
    r = subprocess.run(
        [BASH, "-c", script],
        env={"PATH": f"{fakes}:/usr/bin:/bin", "HOME": str(tmp_path)},
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    chamadas = diario.read_text(encoding="utf-8").splitlines() if diario.exists() else []
    return r, chamadas


class TestACura:
    def test_grava_e_aplica_o_tmpfiles_na_hora(self, tmp_path: Path) -> None:
        r, chamadas = _roda_a_cura(tmp_path)
        assert r.returncode == 0, r.stderr
        grava = [i for i, c in enumerate(chamadas) if "install -Dm644" in c and "tmpfiles.d" in c]
        aplica = [i for i, c in enumerate(chamadas) if "systemd-tmpfiles --create" in c]
        assert grava and aplica, "\n".join(chamadas)
        assert grava[0] < aplica[0], "o tmpfiles foi aplicado antes de existir"
        assert "/etc/tmpfiles.d/hefesto-dualsense4unix-radio.conf" in chamadas[grava[0]]

    def test_no_udev_nao_escreve(self, tmp_path: Path) -> None:
        r, chamadas = _roda_a_cura(tmp_path, skip_udev=1)
        assert r.returncode == 0, r.stderr
        assert not [c for c in chamadas if "install" in c or "tmpfiles" in c], chamadas
        assert "--no-udev" in r.stdout

    def test_sem_o_grupo_hefesto_diz_e_nao_grava(self, tmp_path: Path) -> None:
        r, chamadas = _roda_a_cura(tmp_path, tem_grupo=False)
        assert r.returncode == 0, r.stderr
        assert not [c for c in chamadas if "install" in c], chamadas
        assert "grupo 'hefesto' não existe" in r.stdout


def test_a_trava_vem_antes_da_resiliencia_nos_dois_lados_da_cerca() -> None:
    cerca = INSTALL.index('if [[ "${FORMAT}" != "native" ]]; then')
    fim_da_cerca = INSTALL.index("# 1. Verificar Python", cerca)
    formatos = INSTALL[cerca:fim_da_cerca]
    nativo = INSTALL[fim_da_cerca:]
    for lado, texto in (("formatos", formatos), ("nativo", nativo)):
        trava = texto.find("\n    install_trava_do_radio_host\n")
        if trava == -1:
            trava = texto.find("\ninstall_trava_do_radio_host\n")
        resiliencia = texto.find("install_bt_resilience_host\n")
        assert trava != -1, f"o lado {lado} não chama install_trava_do_radio_host"
        assert trava < resiliencia, (
            f"no lado {lado} a resiliência roda ANTES da trava: o bt_active_mode.sh "
            "abriria a trava como root e a criaria 0644 root:root"
        )


def test_o_asset_diz_o_que_a_sprint_pediu() -> None:
    linhas = [
        linha.split()
        for linha in ASSET.read_text(encoding="utf-8").splitlines()
        if linha.strip() and not linha.startswith("#")
    ]
    assert ["d", "/run/hefesto-dualsense4unix", "0755", "root", "root", "-"] in linhas, linhas
    trava = ["f", "/run/hefesto-dualsense4unix/radio.lock", "0660", "root", "hefesto", "-"]
    assert trava in linhas, (
        "a trava tem de ser 0660 com o grupo hefesto — com leitura para «outros» qualquer "
        f"conta local seguraria a trava e o watchdog pularia todo tique: {linhas}"
    )


# ---------------------------------------------------------------------------
# O doctor
# ---------------------------------------------------------------------------


def _doctor(tmp_path: Path, conf: Path, pasta: Path, *, com_motor_root: bool = True) -> str:
    # O motor root (watchdog, drop-in do bluetoothd, ponte) é desviado para o
    # berço: a régua não depende do /etc de quem a roda.
    motor = tmp_path / "motor-root"
    if com_motor_root:
        motor.write_text("", encoding="utf-8")
    r = subprocess.run(
        [BASH, "-c", f'source "{DOCTOR}"; check_trava_do_radio'],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env={
            "PATH": "/usr/bin:/bin",
            "HOME": str(tmp_path),
            "HEFESTO_DOCTOR_TRAVA_CONF": str(conf),
            "HEFESTO_DOCTOR_TRAVA_DIR": str(pasta),
            "HEFESTO_DOCTOR_TRAVA_MOTORES": f"{tmp_path / 'nao-ha'}:{motor}",
        },
    )
    return r.stdout + r.stderr


class TestODoctor:
    def test_sem_o_tmpfiles_avisa_que_nao_esta_instalada(self, tmp_path: Path) -> None:
        saida = _doctor(tmp_path, tmp_path / "nao-existe.conf", tmp_path / "run")
        assert "[WARN] a trava comum do rádio não está instalada" in saida, saida

    def test_sem_motor_root_a_falta_da_trava_nao_e_aviso(self, tmp_path: Path) -> None:
        """Pacote ou `--no-udev`: sem watchdog, drop-in nem ponte, a trava da
        sessão basta (P-2.9), e mandar «atualizar» era mandar repetir o que não
        entrega. MORDIDA: tirar o ramo `com_motor` volta o WARN."""
        saida = _doctor(
            tmp_path, tmp_path / "nao-existe.conf", tmp_path / "run", com_motor_root=False
        )
        assert "[WARN]" not in saida, saida
        assert "sem motor root que a dispute" in saida, saida

    def test_pasta_gravavel_pela_sessao_e_falha(self, tmp_path: Path) -> None:
        conf = tmp_path / "radio.conf"
        conf.write_text("d x\n", encoding="utf-8")
        pasta = tmp_path / "run"
        pasta.mkdir()
        saida = _doctor(tmp_path, conf, pasta)
        assert "[FAIL]" in saida and "GRAVÁVEL" in saida, saida

    def test_trava_com_modo_errado_avisa(self, tmp_path: Path) -> None:
        conf = tmp_path / "radio.conf"
        conf.write_text("d x\n", encoding="utf-8")
        pasta = tmp_path / "run"
        pasta.mkdir()
        (pasta / "radio.lock").write_text("", encoding="utf-8")
        (pasta / "radio.lock").chmod(0o644)
        pasta.chmod(0o555)
        try:
            saida = _doctor(tmp_path, conf, pasta)
        finally:
            pasta.chmod(0o755)
        assert "[WARN]" in saida and "está 644" in saida, saida

    def test_de_pe_passa(self, tmp_path: Path) -> None:
        try:
            gid = grp.getgrnam("hefesto").gr_gid
        except KeyError:
            pytest.skip("sem o grupo hefesto nesta máquina")
        if gid not in os.getgroups():
            pytest.skip("esta sessão não está no grupo hefesto")
        conf = tmp_path / "radio.conf"
        conf.write_text("d x\n", encoding="utf-8")
        pasta = tmp_path / "run"
        pasta.mkdir()
        trava = pasta / "radio.lock"
        trava.write_text("", encoding="utf-8")
        os.chown(trava, -1, gid)
        trava.chmod(0o660)
        pasta.chmod(0o555)
        try:
            saida = _doctor(tmp_path, conf, pasta)
        finally:
            pasta.chmod(0o755)
        assert "[ OK ] trava comum do rádio de pé" in saida, saida
