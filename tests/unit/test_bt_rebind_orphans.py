"""REBIND-PROBE-01 (25/07) — cura de PRIMEIRA linha do controle órfão.

Sintoma medido: com dois DualSense subindo no mesmo adaptador com ~1 s de
diferença, o segundo perde o canal de controle L2CAP; o GET_REPORT expira no
BlueZ (`REPORT_REQ_TIMEOUT` = 3 s), o `uhid` entrega `-EIO` ao driver e a probe
morre. O device fica em `/sys/bus/hid/devices` **sem symlink `driver`** — sem
hidraw, sem input, sem LED, sem bateria.

Cura VALIDADA AO VIVO (25/07 12:06): um rebind no driver **vanilla** in-tree
ressuscita o controle de primeira, sem patch de kernel e sem reboot —
provando que a contenção é transiente e que o device seguia íntegro.

Contrato (falha-sem/passa-com; SEM root, SEM hardware — sysfs falso em tmp):

- cura o órfão NO escopo (Bluetooth + Sony);
- IGNORA órfão fora do escopo (nunca chuta bind em device alheio);
- NUNCA toca em device que já tem driver (inclusive o vpad do hefesto, que
  nasce no barramento 0003 e por isso está fora do escopo por construção);
- GUARDA CONTRA LAÇO: para após MAX tentativas e loga a desistência UMA vez;
- NUNCA carrega/descarrega módulo (recarregar hid_playstation derrubaria
  todos os DualSense, inclusive os por Bluetooth).
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "bt_rebind_orphans.sh"
SCRIPT_TEXT = SCRIPT.read_text(encoding="utf-8")

ORFAO_NO_ESCOPO = "0005:054C:0CE6.000F"       # DualSense por Bluetooth
ORFAO_FORA_ESCOPO = "0003:057E:2009.0001"     # Pro Controller por USB
VPAD_COM_DRIVER = "0003:054C:0DF2.0010"       # vpad do hefesto (uhid, bus 0003)


def _monta_sysfs(tmp_path: Path, orfaos: list[str], com_driver: list[str]) -> Path:
    devices = tmp_path / "devices"
    drivers = tmp_path / "drivers"
    (drivers / "playstation").mkdir(parents=True)
    (drivers / "playstation" / "bind").write_text("", encoding="utf-8")
    fake_drv = tmp_path / "fakedrv"
    fake_drv.mkdir()
    for dev in orfaos:
        (devices / dev).mkdir(parents=True)
    for dev in com_driver:
        (devices / dev).mkdir(parents=True)
        os.symlink(fake_drv, devices / dev / "driver")
    (tmp_path / "stamps").mkdir()
    return tmp_path


def _roda(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env.update(
        HEFESTO_HID_DEVICES_DIR=str(tmp_path / "devices"),
        HEFESTO_HID_DRIVERS_DIR=str(tmp_path / "drivers"),
        HEFESTO_REBIND_STAMP_DIR=str(tmp_path / "stamps"),
    )
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


class TestEscopo:
    def test_cura_orfao_bluetooth_sony(self, tmp_path: Path) -> None:
        _monta_sysfs(tmp_path, [ORFAO_NO_ESCOPO], [])
        r = _roda(tmp_path, "--dry-run")
        assert r.returncode == 0
        assert ORFAO_NO_ESCOPO in r.stdout
        assert "faria" in r.stdout

    def test_ignora_orfao_fora_do_escopo(self, tmp_path: Path) -> None:
        # Chutar bind em device alheio é como se inventa bug novo.
        _monta_sysfs(tmp_path, [ORFAO_FORA_ESCOPO], [])
        r = _roda(tmp_path, "--dry-run")
        assert r.returncode == 0
        assert "ignorado" in r.stdout
        assert "faria" not in r.stdout

    def test_nunca_toca_em_device_que_ja_tem_driver(self, tmp_path: Path) -> None:
        # O vpad do hefesto está SEMPRE nesta situação; um rebind nele seria
        # briga com o daemon.
        _monta_sysfs(tmp_path, [], [VPAD_COM_DRIVER])
        r = _roda(tmp_path, "--dry-run")
        assert r.returncode == 0
        assert VPAD_COM_DRIVER not in r.stdout
        assert "nenhum device HID órfão" in r.stdout

    def test_escopo_e_bluetooth_mais_sony_no_codigo(self) -> None:
        # O barramento 0005 é o que exclui o vpad (uhid nasce no 0003) — se
        # alguém afrouxar isso, o script passa a brigar com o daemon.
        assert '"${bus}" == "0005"' in SCRIPT_TEXT
        assert '"${vid}" == "054C"' in SCRIPT_TEXT


class TestGuardaContraLaco:
    def test_para_apos_o_teto_e_desiste_uma_vez_so(self, tmp_path: Path) -> None:
        # bind aceita a escrita mas o driver nunca aparece == falha permanente.
        _monta_sysfs(tmp_path, [ORFAO_NO_ESCOPO], [])
        saidas = [_roda(tmp_path, "--quiet").stdout for _ in range(5)]

        tentativas = [s for s in saidas if "NÃO pegou" in s]
        assert len(tentativas) == 3, "o teto padrão é 3 tentativas"

        desistencias = [s for s in saidas if "DESISTINDO" in s]
        assert len(desistencias) == 1, (
            "a desistência tem que ser logada UMA vez — este projeto já teve "
            "laço de 1 Hz enchendo log por 45 min"
        )
        assert saidas[-1].strip() == "", "depois de desistir, silêncio total"

    def test_teto_e_configuravel_e_contador_por_device(self, tmp_path: Path) -> None:
        _monta_sysfs(tmp_path, [ORFAO_NO_ESCOPO], [])
        env = dict(os.environ)
        env.update(
            HEFESTO_HID_DEVICES_DIR=str(tmp_path / "devices"),
            HEFESTO_HID_DRIVERS_DIR=str(tmp_path / "drivers"),
            HEFESTO_REBIND_STAMP_DIR=str(tmp_path / "stamps"),
            HEFESTO_REBIND_MAX_TENTATIVAS="1",
        )
        subprocess.run(["bash", str(SCRIPT), "--quiet"], capture_output=True,
                       text=True, check=False, env=env)
        r = subprocess.run(["bash", str(SCRIPT), "--quiet"], capture_output=True,
                           text=True, check=False, env=env)
        assert "DESISTINDO" in r.stdout
        # o contador é por device (o id muda a cada reconexão -> orçamento novo)
        assert (tmp_path / "stamps" / ORFAO_NO_ESCOPO).exists()

    def test_stamp_de_device_que_sumiu_e_limpo(self, tmp_path: Path) -> None:
        _monta_sysfs(tmp_path, [ORFAO_NO_ESCOPO], [])
        _roda(tmp_path, "--quiet")
        assert (tmp_path / "stamps" / ORFAO_NO_ESCOPO).exists()
        # controle desconectou: o diretório do device some do sysfs
        (tmp_path / "devices" / ORFAO_NO_ESCOPO).rmdir()
        _roda(tmp_path, "--quiet")
        assert not (tmp_path / "stamps" / ORFAO_NO_ESCOPO).exists(), (
            "sem a limpeza, /run acumularia stamp morto até o reboot"
        )


class TestContratoDeSeguranca:
    def test_nunca_carrega_ou_descarrega_modulo(self) -> None:
        # Recarregar hid_playstation derrubaria TODOS os DualSense, inclusive
        # os por Bluetooth. Mesma regra do dkms_lib.sh.
        codigo = "\n".join(
            linha for linha in SCRIPT_TEXT.splitlines() if not linha.strip().startswith("#")
        )
        assert not re.search(r"\b(modprobe|rmmod|insmod)\b", codigo), (
            "bt_rebind_orphans.sh NUNCA pode carregar/descarregar módulo"
        )

    def test_dry_run_nao_escreve_nada(self, tmp_path: Path) -> None:
        _monta_sysfs(tmp_path, [ORFAO_NO_ESCOPO], [])
        _roda(tmp_path, "--dry-run")
        bind = tmp_path / "drivers" / "playstation" / "bind"
        assert bind.read_text(encoding="utf-8") == ""
        assert list((tmp_path / "stamps").iterdir()) == []

    def test_sai_zero_mesmo_sem_orfao(self, tmp_path: Path) -> None:
        # Roda de dentro do watchdog, que tem set -e: sair != 0 mataria as
        # outras vigias.
        _monta_sysfs(tmp_path, [], [VPAD_COM_DRIVER])
        assert _roda(tmp_path).returncode == 0

    def test_set_euo_pipefail(self) -> None:
        assert "set -euo pipefail" in SCRIPT_TEXT


class TestIntegracaoComOWatchdog:
    def test_watchdog_chama_a_vigia_de_rebind(self) -> None:
        watchdog = (REPO_ROOT / "scripts" / "bt_health_watchdog.sh").read_text(
            encoding="utf-8"
        )
        assert "vigia_rebind_orfaos" in watchdog
        assert "bt_rebind_orphans.sh" in watchdog
        assert "--quiet" in watchdog, (
            "o watchdog passa a cada 2 min — sem --quiet viraria ruído"
        )

    def test_install_e_uninstall_sao_simetricos(self) -> None:
        install = (REPO_ROOT / "install.sh").read_text(encoding="utf-8")
        uninstall = (REPO_ROOT / "uninstall.sh").read_text(encoding="utf-8")
        assert "bt_rebind_orphans.sh" in install, "o helper precisa ser instalado"
        assert "bt_rebind_orphans.sh" in uninstall, "e removido junto (simetria)"

    def test_script_e_executavel(self) -> None:
        assert os.access(SCRIPT, os.X_OK), "o watchdog o invoca direto"


class TestDocumentaAMedicao:
    def test_cabecalho_registra_a_cadeia_causal_e_a_prova(self) -> None:
        # Sem isso, em 6 meses alguém "simplifica" o escopo e volta o bug.
        cabecalho = SCRIPT_TEXT.split("set -euo pipefail")[0]
        assert "REPORT_REQ_TIMEOUT" in cabecalho
        assert "uhid" in cabecalho
        assert "reportID 32" in cabecalho
        assert "bind" in cabecalho, "a prova ao vivo do rebind"
        assert "TRANSIENTE" in cabecalho or "transiente" in cabecalho
