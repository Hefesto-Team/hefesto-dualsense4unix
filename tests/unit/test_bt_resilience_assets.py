"""ONDA-R2 — assets de resiliência do bluetoothd (camada 1+2 da sprint BlueZ).

Sprint: docs/process/sprints/2026-07-21-sprint-pesquisa-bluez-estabilidade.md.
Diagnóstico: docs/process/estudos/2026-07-22-diagnostico-dualsense-bt-bonds-fantasma.md.

Contrato dos assets (falha-sem/passa-com; SEM root, SEM systemd vivo — só
arquivos e `bash -n`):

- bloco unificado do main.conf (hefesto-bt.block) com UMA seção [General]
  contendo FastConnectable E JustWorksRepairing, entre as sentinelas do bloco
  unificado — e o install.sh reescrevendo de forma idempotente (remove os
  blocos legados E o unificado antes de apensar; bug real: 3x [General]);
- drop-in do bluetooth.service com Restart=on-failure + WatchdogSec +
  ExecStopPost do snapshot (o "-" na frente: falha do snapshot nunca pode
  poluir o resultado do stop do serviço);
- scripts bt_* executáveis, com sintaxe bash válida e as invariantes de
  segurança do desenho: snapshot NUNCA fotografa estado vazio; restore é
  manual e avisa sobre chave rotacionada; watchdog nunca reinicia com device
  conectado e promove bond temporário no máximo 1x/boot; captura forense é
  opt-in com --on/--off simétricos;
- units/timers com os nomes que install/uninstall/doctor referenciam;
- simetria: todo artefato que o install.sh instala aparece no uninstall.sh.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

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
    REPO_ROOT / "scripts" / "bt_health_watchdog.sh",
    REPO_ROOT / "scripts" / "bt_crash_capture.sh",
    REPO_ROOT / "scripts" / "bt_active_mode.sh",
]
INSTALL = REPO_ROOT / "install.sh"
UNINSTALL = REPO_ROOT / "uninstall.sh"
DOCTOR = REPO_ROOT / "scripts" / "doctor.sh"


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
        # Conta só linhas-cabeçalho reais (o comentário do bloco também cita
        # "[General]" em prosa — não vale).
        headers = re.findall(r"^\[General\]$", text, re.M)
        assert len(headers) == 1, "o bloco unificado deve ter UMA seção [General]"
        assert re.search(r"^FastConnectable=true$", text, re.M)
        assert re.search(r"^JustWorksRepairing=always$", text, re.M)
        assert "# >>> hefesto bluetooth >>>" in text
        assert "# <<< hefesto bluetooth <<<" in text

    def test_install_reescreve_removendo_blocos_anteriores(self) -> None:
        text = INSTALL.read_text(encoding="utf-8")
        # O awk de reescrita precisa cobrir o bloco unificado E os dois legados.
        assert "hefesto (bluetooth|FastConnectable|JustWorksRepairing)" in text, (
            "install.sh deve remover os três blocos sentinelados antes de apensar"
        )
        assert "hefesto-bt.block" in text

    def test_uninstall_remove_o_bloco_unificado(self) -> None:
        text = UNINSTALL.read_text(encoding="utf-8")
        assert "# >>> hefesto bluetooth >>>" in text
        # E segue removendo os legados de instalações antigas.
        assert "# >>> hefesto JustWorksRepairing >>>" in text
        assert "# >>> hefesto FastConnectable >>>" in text


class TestDropinResilience:
    def test_dropin_tem_watchdog_restart_e_snapshot_na_parada(self) -> None:
        text = DROPIN.read_text(encoding="utf-8")
        assert re.search(r"^Restart=on-failure$", text, re.M)
        assert re.search(r"^WatchdogSec=\d+$", text, re.M)
        # "-" prefixado: falha do snapshot nunca contamina o stop do serviço.
        assert re.search(
            r"^ExecStopPost=-/usr/local/lib/hefesto-dualsense4unix/bt_bonds_snapshot\.sh",
            text,
            re.M,
        )

    def test_dropin_aplica_modo_ativo_nintendo_no_start(self) -> None:
        """BT-NINTENDO-ACTIVE-01: ExecStartPost aplica nome+link-policy a cada
        (re)start do bluetoothd. "-" prefixado = não-fatal (adaptador pode não
        estar pronto no start; o watchdog reafirma)."""
        text = DROPIN.read_text(encoding="utf-8")
        assert re.search(
            r"^ExecStartPost=-/usr/local/lib/hefesto-dualsense4unix/bt_active_mode\.sh",
            text,
            re.M,
        )

    def test_active_mode_desliga_sniff_e_prefixa_nintendo(self) -> None:
        """O script tira o SNIFF (link policy rswitch) e prefixa 'Nintendo' no
        alias — as duas alavancas medidas na pesquisa 2026-07-22."""
        text = (REPO_ROOT / "scripts" / "bt_active_mode.sh").read_text(encoding="utf-8")
        assert "lp rswitch" in text, "deve setar link policy sem SNIFF"
        assert "Nintendo ${ALIAS_ATUAL}" in text, "deve prefixar 'Nintendo' no alias"

    def test_watchdog_reafirma_modo_ativo(self) -> None:
        """O watchdog (2 min) delega ao bt_active_mode.sh — cobre adaptador que
        resetou (rfkill/suspend zeram a link policy) e conexões novas."""
        text = (REPO_ROOT / "scripts" / "bt_health_watchdog.sh").read_text(
            encoding="utf-8"
        )
        assert "bt_active_mode.sh" in text

    def test_uninstall_reverte_sniff_e_nome(self) -> None:
        """Uninstall simétrico: volta o SNIFF default e tira o prefixo Nintendo."""
        text = UNINSTALL.read_text(encoding="utf-8")
        assert "lp rswitch hold sniff park" in text
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
        assert "systemctl stop bluetooth.service" in text

    def test_watchdog_nunca_reinicia_com_device_conectado(self) -> None:
        text = (REPO_ROOT / "scripts" / "bt_health_watchdog.sh").read_text(encoding="utf-8")
        assert "nunca derrubo sessão viva" in text
        assert "rate-limit" in text
        # Promoção de bond temporário: no máximo uma tentativa por device/boot,
        # via modo interativo com quit segurado (pair é assíncrono —
        # COMPAT BLUEZ-586-CTL-01: o one-shot do cliente 5.86 é mudo).
        assert "promoted-" in text
        assert "_btctl_lento 25 pair" in text
        assert "COMPAT BLUEZ-586-CTL-01" in text

    def test_crash_capture_e_opt_in_simetrico(self) -> None:
        text = (REPO_ROOT / "scripts" / "bt_crash_capture.sh").read_text(encoding="utf-8")
        for flag in ("--on", "--off", "--status"):
            assert flag in text
        # O install NUNCA liga a captura: pode CITAR o comando em mensagem de
        # ajuda, mas nenhuma linha pode EXECUTÁ-LO (sudo/execução direta).
        install_text = INSTALL.read_text(encoding="utf-8")
        assert not re.search(
            r"^\s*(sudo\s+)?(/[\w/.-]*)?bt_crash_capture\.sh\s+--on", install_text, re.M
        ), "install.sh não pode executar a captura forense (é opt-in humano)"


class TestSimetriaInstallUninstall:
    def test_units_instaladas_sao_removidas(self) -> None:
        install_text = INSTALL.read_text(encoding="utf-8")
        uninstall_text = UNINSTALL.read_text(encoding="utf-8")
        for unit in UNITS:
            assert unit.name in install_text, f"install.sh não instala {unit.name}"
            assert unit.name in uninstall_text, f"uninstall.sh não remove {unit.name}"
        for script in SCRIPTS:
            assert script.name in install_text, f"install.sh não instala {script.name}"
            assert script.name in uninstall_text, f"uninstall.sh não remove {script.name}"
        assert "10-hefesto-resilience.conf" in uninstall_text
        # O uninstall também precisa desarmar uma janela forense esquecida.
        assert "90-hefesto-debug.conf" in uninstall_text
        assert "99-hefesto-bt-coredump.conf" in uninstall_text

    def test_doctor_cobre_resiliencia_e_bonds(self) -> None:
        text = DOCTOR.read_text(encoding="utf-8")
        assert "check_bt_resilience" in text
        assert "check_bt_bonds_persistidos" in text
        assert "hefesto-bt-bonds-snapshot.timer" in text


class TestAlvoBluez586:
    def test_install_aponta_para_o_alvo_586(self) -> None:
        text = INSTALL.read_text(encoding="utf-8")
        # 22/07: o alvo virou a VERSÃO COMPLETA ~hefesto24.04.2 (patch BOND-KEEP-01)
        # — o compare-versions precisa distinguir .1 de .2; um "5.86" nu pularia
        # o upgrade. Aceita 5.86 base OU a versão hefesto completa.
        assert re.search(r'_BZ_TARGET="5\.86', text), (
            "passo 3f deve mirar o BlueZ 5.86 (sprint 2026-07-21: retry-limit 17a227b7)"
        )
        assert "hefesto24.04.2" in text, (
            "o alvo do 3f deve ser a versão hefesto completa .2 (patch BOND-KEEP-01)"
        )
