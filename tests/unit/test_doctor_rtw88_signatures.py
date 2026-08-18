"""Onda W — os 3 checks novos do rtw88 no doctor.sh.

Desenho: docs/process/estudos/2026-07-20-desenho-onda-w-patch-dkms.md (§3):
1. check_hefesto_rtw88_usb_dkms — status do patch DKMS + marcador de carga
   pelo PARÂMETRO hang_reset (o in-tree JÁ expõe parameters/ com
   switch_usb_mode: o diretório sozinho NÃO distingue — armadilha própria
   da Onda W, diferente do hid_nintendo);
2. check_usb_fantasma — a assinatura MEDIDA do incidente de 20/07 (13h de
   device retido após port-status-change perdido no xHCI): duplicata de
   idVendor:idProduct no driver rtw88_usb, colisão de rename do udev
   (wlx… File exists) e device sem net/ com -71 no boot;
3. check_wifi_powersave — powersave EFETIVO do NM lido SÓ de arquivo
   (conf.d), sem julgamento até a medição W2, + contagem de
   'failed to leave lps state' (assinatura do LPS raso).

Cobertura (falha-sem/passa-com, sem journal/sysfs reais — funções extraídas
rodam em bash com stub de journalctl e sysfs/conf.d sintéticos via
substituição textual da raiz, mesma técnica de fixture dos testes da Onda T).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

BASH = shutil.which("bash") or "/bin/bash"
REPO_ROOT = Path(__file__).resolve().parents[2]
DOCTOR_PATH = REPO_ROOT / "scripts" / "doctor.sh"
DKMS_CONF_PATH = REPO_ROOT / "assets" / "dkms" / "rtw88-usb" / "dkms.conf"

DOCTOR = DOCTOR_PATH.read_text(encoding="utf-8") if DOCTOR_PATH.exists() else ""
DKMS_CONF = DKMS_CONF_PATH.read_text(encoding="utf-8") if DKMS_CONF_PATH.exists() else ""

CHECKS = ("check_hefesto_rtw88_usb_dkms", "check_usb_fantasma", "check_wifi_powersave")

SHIMS = (
    'warn() { printf "WARN: %s\\n" "$*"; }\n'
    'info() { printf "INFO: %s\\n" "$*"; }\n'
    'pass() { printf "PASS: %s\\n" "$*"; }\n'
)


def _extrai_funcao_bash(fonte: str, nome: str) -> str:
    match = re.search(rf"^{re.escape(nome)}\(\) \{{\n", fonte, re.MULTILINE)
    assert match is not None, f"função {nome}() não encontrada"
    fim = re.search(r"^\}$", fonte[match.end() :], re.MULTILINE)
    assert fim is not None, f"fim de {nome}() não encontrado"
    return fonte[match.start() : match.end() + fim.end() + 1]


def _sem_comentarios(texto: str) -> str:
    linhas = [re.sub(r"(^|\s)#.*$", r"\1", linha) for linha in texto.splitlines()]
    return "\n".join(linhas)


def _roda_check(
    tmp_path: Path, nome: str, raiz_original: str, raiz_fixture: Path, jornal: str
) -> subprocess.CompletedProcess[str]:
    """Extrai o check, aponta a raiz hardcoded (sysfs/etc) p/ a fixture e
    roda com journalctl stubado — determinístico, sem depender do host."""
    stubs = tmp_path / "bin"
    stubs.mkdir(exist_ok=True)
    fixture = tmp_path / "jornal.txt"
    fixture.write_text(jornal, encoding="utf-8")
    stub = stubs / "journalctl"
    stub.write_text(f'#!/bin/sh\ncat "{fixture}"\n', encoding="utf-8")
    stub.chmod(0o755)
    funcao = _extrai_funcao_bash(DOCTOR, nome).replace(raiz_original, str(raiz_fixture))
    corpo = f"{SHIMS}{funcao}\n{nome}\nprintf 'RC=%s\\n' \"$?\"\n"
    script = tmp_path / "cena.sh"
    script.write_text(corpo, encoding="utf-8")
    env = dict(os.environ)
    env["PATH"] = f"{stubs}:/usr/bin:/bin"
    return subprocess.run(
        [BASH, str(script)], capture_output=True, text=True, check=False, env=env
    )


def _device_usb(
    raiz: Path, nome: str, com_driver: bool = True, com_net: bool = False
) -> None:
    d = raiz / nome
    d.mkdir(parents=True)
    (d / "idVendor").write_text("0bda\n", encoding="utf-8")
    (d / "idProduct").write_text("b812\n", encoding="utf-8")
    if com_driver:
        drivers = raiz / "_drivers" / "rtw88_usb"
        drivers.mkdir(parents=True, exist_ok=True)
        (d / "driver").symlink_to(drivers)
    if com_net:
        (d / "net" / "wlx0013ef5f1234").mkdir(parents=True)


class TestWiringDosChecks:
    def test_bash_n_doctor(self) -> None:
        resultado = subprocess.run(
            ["bash", "-n", str(DOCTOR_PATH)], capture_output=True, text=True, check=False
        )
        assert resultado.returncode == 0, resultado.stderr

    def test_checks_definidos_e_chamados_no_main(self) -> None:
        for nome in CHECKS:
            assert f"{nome}()" in DOCTOR, f"{nome} não definido"
            assert re.search(rf"^\s*{nome}\s*$", DOCTOR, re.MULTILINE), (
                f"{nome} precisa ser CHAMADO no fluxo principal, não só definido"
            )

    def test_pkg_e_versao_batem_com_o_dkms_conf(self) -> None:
        pkg = re.search(r'^readonly HEFESTO_DKMS_RTW88_PKG="([^"]+)"$', DOCTOR, re.MULTILINE)
        ver = re.search(r'^readonly HEFESTO_DKMS_RTW88_VER="([^"]+)"$', DOCTOR, re.MULTILINE)
        assert pkg is not None and ver is not None, "constantes do doctor ausentes"
        assert f'PACKAGE_NAME="{pkg.group(1)}"' in DKMS_CONF
        assert f'PACKAGE_VERSION="{ver.group(1)}"' in DKMS_CONF, (
            "bump de versão exige atualizar os DOIS lados (doctor + dkms.conf)"
        )


class TestChecksReadOnly:
    def test_nenhum_check_instala_recarrega_ou_toca_o_radio(self) -> None:
        for nome in CHECKS:
            corpo = _sem_comentarios(_extrai_funcao_bash(DOCTOR, nome))
            assert not re.search(r"\bdkms (install|build|add|remove)\b", corpo), (
                f"{nome}: doctor diagnostica; instalar/remover é do install/uninstall"
            )
            assert not re.search(r"\b(modprobe(?!\.d)|rmmod|insmod)\b", corpo), nome
            assert not re.search(r"\bnmcli\b", corpo), (
                f"{nome}: powersave é lido de ARQUIVO (conf.d), nunca via nmcli"
            )
            assert not re.search(r"\brfkill\b", corpo), nome

    def test_deteccao_nunca_usa_srcversion(self) -> None:
        corpo = _sem_comentarios(_extrai_funcao_bash(DOCTOR, "check_hefesto_rtw88_usb_dkms"))
        assert "srcversion" not in corpo, (
            "srcversion difere entre builds do MESMO source (armadilha da Onda T)"
        )


class TestCheckDkmsRtw88:
    def test_marcador_do_patchado_e_o_param_hang_reset(self) -> None:
        corpo = _extrai_funcao_bash(DOCTOR, "check_hefesto_rtw88_usb_dkms")
        assert "/sys/module/rtw88_usb/parameters/hang_reset" in corpo, (
            "o in-tree JÁ tem parameters/ (switch_usb_mode) — o marcador "
            "exclusivo do patchado é o PARÂMETRO hang_reset"
        )

    def test_proximo_carregamento_por_modinfo_filename(self) -> None:
        corpo = _extrai_funcao_bash(DOCTOR, "check_hefesto_rtw88_usb_dkms")
        assert "modinfo -F filename rtw88_usb" in corpo
        assert "*/updates/dkms/*" in corpo

    def test_in_tree_carregado_avisa_so_proximo_boot(self) -> None:
        corpo = _extrai_funcao_bash(DOCTOR, "check_hefesto_rtw88_usb_dkms")
        assert "próximo boot" in corpo
        assert "replug NÃO troca módulo carregado" in corpo, (
            "a mensagem explica POR QUE replug não ajuda (mesma lição do "
            "achado #6 do corretor da Onda T)"
        )
        assert "derrubaria o WiFi" in corpo, (
            "a razão de nunca recarregar (WiFi em uso) fica na mensagem"
        )

    def test_kernel_fora_do_pino_e_warn_de_rebase(self) -> None:
        corpo = _extrai_funcao_bash(DOCTOR, "check_hefesto_rtw88_usb_dkms")
        assert "rebase pendente" in corpo
        assert "BUILD_EXCLUSIVE_KERNEL" in corpo, (
            "kernel novo cai no pino de ABI — o warn precisa apontar o ritual "
            "de rebase, não deixar a cura sumir em silêncio"
        )

    def test_remediacao_acionavel_tambem_sem_checkout(self) -> None:
        corpo = _extrai_funcao_bash(DOCTOR, "check_hefesto_rtw88_usb_dkms")
        assert "install-host-udev.sh" in corpo, (
            "usuário de pacote precisa de um caminho de cura que ele TEM"
        )


class TestAssinaturaFantasmaUsb:
    """Funcional: sysfs sintético (raiz substituída) + journalctl stubado."""

    RAIZ = "/sys/bus/usb/devices"

    def _roda(
        self, tmp_path: Path, jornal: str
    ) -> subprocess.CompletedProcess[str]:
        return _roda_check(
            tmp_path, "check_usb_fantasma", self.RAIZ, tmp_path / "sysdev", jornal
        )

    def test_duplicata_do_mesmo_dongle_dispara_warn(self, tmp_path: Path) -> None:
        # A assinatura REAL do incidente: fantasma 4-3 + device vivo 4-2,
        # mesmos idVendor:idProduct, mesmo driver — só existe um dongle físico.
        raiz = tmp_path / "sysdev"
        _device_usb(raiz, "4-2")
        _device_usb(raiz, "4-3")
        resultado = self._roda(tmp_path, "")
        assert "RC=" in resultado.stdout, resultado.stderr
        assert "WARN: device USB fantasma" in resultado.stdout
        assert "unbind" in resultado.stdout, "o warn carrega a cura (unbind/reboot)"

    def test_colisao_de_rename_do_udev_dispara_warn(self, tmp_path: Path) -> None:
        raiz = tmp_path / "sysdev"
        _device_usb(raiz, "4-2", com_net=True)
        jornal = (
            "jul 20 12:09:01 meow systemd-udevd[512]: wlx0013ef5f1234: "
            "Failed to rename network interface 3 from 'wlan0' to "
            "'wlx0013ef5f1234': File exists\n"
        )
        resultado = self._roda(tmp_path, jornal)
        assert "WARN: colisão de rename do udev" in resultado.stdout, (
            "o dano concreto do fantasma: a interface nova não assume o nome "
            "wlx… que o device fantasma ainda segura"
        )

    def test_device_sem_net_com_eproto_dispara_warn(self, tmp_path: Path) -> None:
        # Firmware wedged/disconnect perdido: driver ligado, nenhuma
        # interface de rede e -71 no kernel log do MESMO device.
        raiz = tmp_path / "sysdev"
        _device_usb(raiz, "4-3", com_net=False)
        jornal = (
            "jul 20 23:16:40 meow kernel: usb 4-3: device descriptor "
            "read/64, error -71\n"
            "jul 20 23:16:41 meow kernel: usb 4-3: device descriptor "
            "read/64, error -71\n"
        )
        resultado = self._roda(tmp_path, jornal)
        assert "WARN: device USB 4-3" in resultado.stdout
        assert "device-gone" in resultado.stdout

    def test_maquina_saudavel_fica_em_silencio(self, tmp_path: Path) -> None:
        raiz = tmp_path / "sysdev"
        _device_usb(raiz, "4-2", com_net=True)
        resultado = self._roda(tmp_path, "jul 20 11:00:00 meow kernel: usb 3-3: ok\n")
        assert "RC=0" in resultado.stdout, resultado.stderr
        assert "WARN" not in resultado.stdout
        assert "PASS: sem sinal de device USB fantasma" in resultado.stdout

    def test_devices_de_outros_drivers_sao_ignorados(self, tmp_path: Path) -> None:
        # Dois devices com os MESMOS ids mas sem vínculo com rtw88_usb
        # (ex.: dois controles) não podem virar falso fantasma.
        raiz = tmp_path / "sysdev"
        _device_usb(raiz, "3-2", com_driver=False)
        _device_usb(raiz, "3-4", com_driver=False)
        resultado = self._roda(tmp_path, "")
        assert "WARN" not in resultado.stdout
        assert "PASS: sem sinal de device USB fantasma" in resultado.stdout


class TestCheckWifiPowersave:
    """Funcional: conf.d sintético (raiz substituída) + journalctl stubado."""

    RAIZ = "/etc/NetworkManager"

    def _roda(
        self, tmp_path: Path, jornal: str = ""
    ) -> subprocess.CompletedProcess[str]:
        return _roda_check(
            tmp_path, "check_wifi_powersave", self.RAIZ, tmp_path / "nm", jornal
        )

    def test_powersave_3_vira_info_apontando_a_medicao(self, tmp_path: Path) -> None:
        confd = tmp_path / "nm" / "conf.d"
        confd.mkdir(parents=True)
        (confd / "default-wifi-powersave-on.conf").write_text(
            "[connection]\nwifi.powersave = 3\n", encoding="utf-8"
        )
        resultado = self._roda(tmp_path)
        assert "RC=0" in resultado.stdout, resultado.stderr
        assert "INFO: wifi.powersave=3" in resultado.stdout
        assert "medir_w2_lps.sh" in resultado.stdout, (
            "sem a medição W2 o doctor NÃO julga — só aponta o script A/B"
        )
        assert "WARN" not in resultado.stdout

    def test_conf_do_hefesto_com_2_e_pass(self, tmp_path: Path) -> None:
        confd = tmp_path / "nm" / "conf.d"
        confd.mkdir(parents=True)
        (confd / "hefesto-wifi-powersave.conf").write_text(
            "[connection.hefesto-wifi-powersave]\n"
            "match-device=type:wifi\n"
            "wifi.powersave=2\n",
            encoding="utf-8",
        )
        resultado = self._roda(tmp_path)
        assert "PASS: wifi.powersave=2" in resultado.stdout

    def test_sem_conf_nenhuma_fica_em_info_neutro(self, tmp_path: Path) -> None:
        (tmp_path / "nm").mkdir()
        resultado = self._roda(tmp_path)
        assert "RC=0" in resultado.stdout, resultado.stderr
        assert "INFO: NetworkManager sem wifi.powersave configurado" in resultado.stdout
        assert "WARN" not in resultado.stdout

    def test_failed_to_leave_lps_state_vira_warn(self, tmp_path: Path) -> None:
        (tmp_path / "nm").mkdir()
        jornal = (
            "jul 20 10:00:00 meow kernel: rtw_8822bu 4-3:1.2: failed to leave lps state\n"
            "jul 20 10:00:05 meow kernel: rtw_8822bu 4-3:1.2: failed to leave lps state\n"
        )
        resultado = self._roda(tmp_path, jornal)
        assert "WARN: 2x 'failed to leave lps state'" in resultado.stdout
        assert "LPS raso" in resultado.stdout, (
            "a assinatura aponta o vilão ATIVO (LPS raso via mac80211) — o "
            "deep PS é NO-OP em USB e não entra no diagnóstico"
        )

    def test_journal_limpo_sem_warn_de_lps(self, tmp_path: Path) -> None:
        (tmp_path / "nm").mkdir()
        resultado = self._roda(tmp_path, "jul 20 10:00:00 meow kernel: nada de lps\n")
        assert "WARN" not in resultado.stdout
