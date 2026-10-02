"""ONDA-R2 — assets de resiliência do bluetoothd (camada 1+2 da sprint BlueZ)."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from tests.unit.fonte_do_instalador import texto_do_instalador

REPO_ROOT = Path(__file__).resolve().parents[2]
BT_BLOCK = REPO_ROOT / "assets" / "bluetooth" / "hefesto-bt.block"
DROPIN = REPO_ROOT / "assets" / "systemd" / "bluetooth-dropin-10-hefesto-resilience.conf"
UNITS = [
    REPO_ROOT / "assets" / "systemd" / "hefesto-bt-bonds-snapshot.service",
    REPO_ROOT / "assets" / "systemd" / "hefesto-bt-bonds-snapshot.timer",
    REPO_ROOT / "assets" / "systemd" / "hefesto-bt-health-watchdog.service",
    REPO_ROOT / "assets" / "systemd" / "hefesto-bt-health-watchdog.timer",
]
SCRIPTS = [
    REPO_ROOT / "scripts" / "bt_bonds_snapshot.sh",
    REPO_ROOT / "scripts" / "bt_bonds_restore.sh",
    REPO_ROOT / "scripts" / "bt_bonds_autorestore.sh",
    REPO_ROOT / "scripts" / "bt_health_watchdog.sh",
    REPO_ROOT / "scripts" / "bt_crash_capture.sh",
    REPO_ROOT / "scripts" / "bt_active_mode.sh",
]
INSTALL = REPO_ROOT / "install.sh"
UNINSTALL = REPO_ROOT / "uninstall.sh"
DOCTOR = REPO_ROOT / "scripts" / "doctor.sh"
BLUEZ_CONFIG = REPO_ROOT / "scripts" / "bluez_config.sh"


class TestAssetsExistem:
    def test_todos_os_arquivos_presentes(self) -> None:
        for path in [BT_BLOCK, DROPIN, INSTALL, UNINSTALL, DOCTOR, *UNITS, *SCRIPTS]:
            assert path.exists(), f"asset da ONDA-R2 ausente: {path.relative_to(REPO_ROOT)}"

    def test_scripts_executaveis_e_sintaxe_bash(self) -> None:
        for script in SCRIPTS:
            assert script.stat().st_mode & 0o111, f"{script.name} não é executável"
            proc = subprocess.run(
                ["bash", "-n", str(script)], capture_output=True, text=True
            )
            assert proc.returncode == 0, f"bash -n falhou em {script.name}: {proc.stderr}"


class TestBlocoUnificadoMainConf:
    def test_uma_unica_secao_general_com_as_duas_chaves(self) -> None:
        text = BT_BLOCK.read_text(encoding="utf-8")
        headers = re.findall(r"^\[General\]$", text, re.M)
        assert len(headers) == 1, "o bloco unificado deve ter UMA seção [General]"
        assert re.search(r"^FastConnectable=true$", text, re.M)
        assert re.search(r"^JustWorksRepairing=confirm$", text, re.M)
        assert "# >>> hefesto bluetooth >>>" in text
        assert "# <<< hefesto bluetooth <<<" in text

    def test_install_reescreve_removendo_blocos_anteriores(self) -> None:
        text = BLUEZ_CONFIG.read_text(encoding="utf-8")
        assert "hefesto (bluetooth|FastConnectable|JustWorksRepairing)" in text, (
            "bluez_config.sh deve remover os três blocos sentinelados antes de apensar"
        )
        assert "hefesto-bt.block" in text
        assert 'scripts/bluez_config.sh" aplicar' in texto_do_instalador()

    def test_uninstall_remove_o_bloco_unificado(self) -> None:
        text = BLUEZ_CONFIG.read_text(encoding="utf-8")
        assert "hefesto (bluetooth|FastConnectable|JustWorksRepairing) >>>" in text
        assert 'scripts/bluez_config.sh" remover' in UNINSTALL.read_text(encoding="utf-8")


class TestDropinResilience:
    def test_dropin_tem_watchdog_restart_e_snapshot_na_parada(self) -> None:
        text = DROPIN.read_text(encoding="utf-8")
        assert re.search(r"^Restart=on-failure$", text, re.M)
        assert re.search(r"^WatchdogSec=0$", text, re.M), (
            "o `WatchdogSec` do drop-in não é 0. Ligar o watchdog do systemd "
            "sobre o bluetoothd faz o systemd MATAR o daemon quando ele demora a "
            "responder — e ele demora por motivos legítimos (um `sdptool browse` "
            "medido em 35 s). Ver "
            "docs/process/sprints/2026-08-08-BLUETOOTHD-MORTO-POR-NOS-01-*.md"
        )
        assert re.search(
            r"^ExecStopPost=-/usr/local/lib/hefesto-dualsense4unix/bt_bonds_snapshot\.sh",
            text,
            re.M,
        )

    def test_dropin_aplica_modo_ativo_nintendo_no_start(self) -> None:
        """BT-NINTENDO-ACTIVE-01: ExecStartPost aplica nome+link-policy a cada"""
        text = DROPIN.read_text(encoding="utf-8")
        assert re.search(
            r"^ExecStartPost=-\+/usr/local/lib/hefesto-dualsense4unix/bt_active_mode\.sh",
            text,
            re.M,
        )

    def test_active_mode_prefixa_nintendo_no_alias(self) -> None:
        """O NOME é do adaptador — vale para todos os controles."""
        text = (REPO_ROOT / "scripts" / "bt_active_mode.sh").read_text(encoding="utf-8")
        prefixado = re.search(r'(\w+)="Nintendo \$\{\w+\}"', text)
        assert prefixado, "deve prefixar 'Nintendo' no alias"
        assert f'Alias s "${{{prefixado.group(1)}}}"' in text, (
            "o valor prefixado tem de ser o que vai ao Alias"
        )

    def test_no_sniff_e_por_dispositivo_nao_do_adaptador(self) -> None:
        """BT-SNIFF-PER-OUI-01 (23/07) — o escopo do no-sniff é POR CONTROLE."""
        text = (REPO_ROOT / "scripts" / "bt_active_mode.sh").read_text(encoding="utf-8")
        codigo = "\n".join(
            linha for linha in text.splitlines() if not linha.lstrip().startswith("#")
        )
        assert "lp rswitch,hold,sniff,park" in codigo, (
            "o default do adaptador tem de permitir SNIFF — sem ele o 8BitDo "
            "não completa a probe"
        )
        assert "lp rswitch 2" not in codigo and "lp rswitch\n" not in codigo, (
            "no-sniff como default do ADAPTADOR é a regressão medida em 23/07"
        )
        assert 'hcitool lp "${MAC}" RSWITCH' in codigo, (
            "o no-sniff deixou de mirar o endereço do controle: se o alvo virar "
            "um `hciN`, ele volta a ser default do adaptador e a probe do "
            "8BitDo morre de novo em ret=-110"
        )
        assert re.search(r"^\s*_e_pro_genuino\b.*\|\|\s*continue\s*$", codigo, re.M), (
            "o laço por-conexão perdeu o filtro por controle: sem ele o "
            "`hcitool lp` alcança TODO mundo que estiver conectado, e o clone "
            "8BitDo — que precisa do sniff — volta a levar o no-sniff junto"
        )

    def test_watchdog_reafirma_modo_ativo(self) -> None:
        """O watchdog (2 min) delega ao bt_active_mode.sh — cobre adaptador que"""
        text = (REPO_ROOT / "scripts" / "bt_health_watchdog.sh").read_text(
            encoding="utf-8"
        )
        assert "bt_active_mode.sh" in text

    def test_uninstall_reverte_sniff_e_nome(self) -> None:
        """Uninstall simétrico: volta o SNIFF default e tira o prefixo Nintendo."""
        text = UNINSTALL.read_text(encoding="utf-8")
        assert "lp rswitch,hold,sniff,park" in text
        codigo = "\n".join(
            linha for linha in text.splitlines() if not linha.lstrip().startswith("#")
        )
        assert "lp rswitch hold sniff park" not in codigo, (
            "sintaxe com espaços não reverte nada (hciconfig lê só o 1º token)"
        )
        assert "bt_active_mode.sh" in text


class TestInvariantesDosScripts:
    def test_snapshot_nunca_fotografa_vazio(self) -> None:
        text = (REPO_ROOT / "scripts" / "bt_bonds_snapshot.sh").read_text(encoding="utf-8")
        assert "snapshot recusado" in text, (
            "invariante: zero bonds em disco => sair sem tocar nos backups"
        )

    def test_restore_avisa_sobre_chave_rotacionada(self) -> None:
        text = (REPO_ROOT / "scripts" / "bt_bonds_restore.sh").read_text(encoding="utf-8")
        assert "bluetoothctl remove" in text
        assert "mask --runtime" in text
        assert "systemctl stop --job-mode=replace-irreversibly bluetooth.service" in text

    def test_watchdog_nunca_reinicia_com_device_conectado(self) -> None:
        text = (REPO_ROOT / "scripts" / "bt_health_watchdog.sh").read_text(encoding="utf-8")
        assert "nunca derrubo sessão viva" in text
        assert "rate-limit" in text
        assert "promoted-" in text
        assert "_btctl_lento 25 pair" in text
        assert "COMPAT BLUEZ-586-CTL-01" in text

    def test_trust_nao_depende_de_conexao(self) -> None:
        """WATCHDOG-TRUST-DEADLOCK-01 (23/07) — o deadlock do trust."""
        text = (REPO_ROOT / "scripts" / "bt_health_watchdog.sh").read_text(
            encoding="utf-8"
        )
        bloco = text.split("vigia 2b:", 1)[1].split("vigia 2: bond temporário", 1)[0]
        codigo = "\n".join(
            linha for linha in bloco.splitlines() if not linha.lstrip().startswith("#")
        )
        assert 'Connected' not in codigo, (
            "o trust não pode ficar atrás do gate de conexão — é o deadlock"
        )
        assert '_dbus_device_prop "${OBJ}" Bonded' in codigo, (
            "só device COM BOND ganha trust (dar trust a quem só apareceu num "
            "scan seria autorizar quem nunca foi pareado)"
        )
        assert "Trusted b true" in codigo
        vigia2 = text.split("vigia 2: bond temporário", 1)[1]
        assert '"${OBJ}" Connected)" == "true" ]] || continue' in vigia2

    def test_crash_capture_e_opt_in_simetrico(self) -> None:
        text = (REPO_ROOT / "scripts" / "bt_crash_capture.sh").read_text(encoding="utf-8")
        for flag in ("--on", "--off", "--status"):
            assert flag in text
        install_text = texto_do_instalador()
        assert not re.search(
            r"^\s*(sudo\s+)?(/[\w/.-]*)?bt_crash_capture\.sh\s+--on", install_text, re.M
        ), "install.sh não pode executar a captura forense (é opt-in humano)"


class TestSimetriaInstallUninstall:
    def test_units_instaladas_sao_removidas(self) -> None:
        install_text = texto_do_instalador()
        uninstall_text = UNINSTALL.read_text(encoding="utf-8")
        for unit in UNITS:
            assert unit.name in install_text, (
                f"o instalador não instala {unit.name} (procurei no install.sh "
                "e em scripts/lib/camada_de_maquina.sh)"
            )
            assert unit.name in uninstall_text, f"uninstall.sh não remove {unit.name}"
        for script in SCRIPTS:
            assert script.name in install_text, (
                f"o instalador não instala {script.name} (procurei no install.sh "
                "e em scripts/lib/camada_de_maquina.sh)"
            )
            assert script.name in uninstall_text, f"uninstall.sh não remove {script.name}"
        assert "10-hefesto-resilience.conf" in uninstall_text
        assert "90-hefesto-debug.conf" in uninstall_text
        assert "99-hefesto-bt-coredump.conf" in uninstall_text

    def test_doctor_cobre_resiliencia_e_bonds(self) -> None:
        text = DOCTOR.read_text(encoding="utf-8")
        assert "check_bt_resilience" in text
        assert "check_bt_bonds_persistidos" in text
        assert "hefesto-bt-bonds-snapshot.timer" in text


class TestAlvoBluez586:
    def test_install_aponta_para_o_alvo_586(self) -> None:
        text = texto_do_instalador()
        assert re.search(r'_BZ_TARGET="5\.86', text), (
            "passo 3f deve mirar o BlueZ 5.86 (sprint 2026-07-21: retry-limit 17a227b7)"
        )
        baseline = (
            Path(__file__).resolve().parents[2] / "assets" / "bluez-backport" / "BASELINE"
        ).read_text(encoding="utf-8")
        base = re.search(r"^VERSAO_BASE=(\S+)$", baseline, re.MULTILINE)
        revisao = re.search(r"^REVISAO_ULTIMA=(\d+)$", baseline, re.MULTILINE)
        assert base and revisao, "o BASELINE do backport perdeu VERSAO_BASE ou REVISAO_ULTIMA"
        alvo = f"{base.group(1)}~hefesto24.04.{revisao.group(1)}"
        assert f'_BZ_TARGET="{alvo}"' in text, (
            f"o alvo do 3f tem de ser a ÚLTIMA revisão do BASELINE ({alvo}) — é "
            "ela que o construir_bluez_backport.sh entrega no cache"
        )
