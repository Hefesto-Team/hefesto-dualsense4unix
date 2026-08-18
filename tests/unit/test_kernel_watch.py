"""kernel-watch (PLAT-06 item 4): evolução do storm_watch.sh.

Estudo 2026-07-18-estudo-kernel-hardening.md §6. Contratos travados:

- o NOME do script continua ``scripts/storm_watch.sh`` (a unit
  ``hefesto-dualsense4unix-storm-watch.service`` aponta para ele — compat);
- classificador de tags via hook PURO ``--classify`` (stdin→stdout, sem tocar
  journal/estado), testado com linhas SINTÉTICAS de journal (short-iso);
- ``[JOYCON]`` pega o joycon_enforce_subcmd_rate (o assassino do 8BitDo BT,
  provado ao vivo 2026-07-18); ``[USB-71]`` reusa os padrões do doctor;
- ``[BT-HCI]``/``[XHCI]`` são PREVENTIVOS: só geram linha quando ocorrem;
- ``[BT-ERR]`` (delta dos contadores hciconfig) só é emitido quando PIOROU.

Os hooks rodam com XDG_STATE_HOME em tmpdir (defensivo — eles nem tocam estado).
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "storm_watch.sh"
UNIT_PATH = REPO_ROOT / "assets" / "hefesto-dualsense4unix-storm-watch.service"

# Linhas SINTÉTICAS no formato short-iso do journalctl (TS host ident: msg).
LINHA_JOYCON = (
    "2026-07-18T20:23:22-0300 meowsystem kernel: nintendo 0005:057E:2009.000C: "
    "joycon_enforce_subcmd_rate: exceeded max attempts"
)
LINHA_USB71 = (
    "2026-07-18T10:00:00-0300 meowsystem kernel: usb 3-4: "
    "device descriptor read/64, error -71"
)
LINHA_USB71_HID = (
    "2026-07-18T10:00:01-0300 meowsystem kernel: usbhid 3-4:1.3: "
    "can't add hid device: -71"
)
LINHA_XHCI = (
    "2026-07-18T11:00:00-0300 meowsystem kernel: xhci_hcd 0000:02:00.0: "
    "HC died; cleaning up"
)
LINHA_BT_HCI = (
    "2026-07-18T12:00:00-0300 meowsystem kernel: Bluetooth: hci0: "
    "command tx timeout"
)
LINHA_NEUTRA = (
    "2026-07-18T13:00:00-0300 meowsystem kernel: usb 3-4: new high-speed USB device"
)


def _run(args: list[str], stdin: str = "", tmp_path: Path | None = None) -> str:
    env = dict(os.environ)
    if tmp_path is not None:
        env["XDG_STATE_HOME"] = str(tmp_path)
    result = subprocess.run(
        ["bash", str(SCRIPT_PATH), *args],
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
        env=env,
        timeout=30,
    )
    assert result.returncode == 0, f"rc={result.returncode}: {result.stderr}"
    return result.stdout


def test_sintaxe_bash_valida() -> None:
    result = subprocess.run(
        ["bash", "-n", str(SCRIPT_PATH)], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, f"erro de sintaxe bash:\n{result.stderr}"


def test_unit_continua_apontando_para_storm_watch_sh() -> None:
    # Compat deliberada: o script evoluiu SEM renomear — a unit não muda.
    texto = UNIT_PATH.read_text(encoding="utf-8")
    assert "scripts/storm_watch.sh" in texto


class TestClassify:
    def test_joycon_e_o_mais_especifico(self, tmp_path: Path) -> None:
        saida = _run(["--classify"], stdin=LINHA_JOYCON + "\n", tmp_path=tmp_path)
        assert "[JOYCON]" in saida
        assert saida.startswith("2026-07-18T20:23:22-0300 [JOYCON] nintendo")

    def test_usb71_cobre_padroes_do_doctor(self, tmp_path: Path) -> None:
        saida = _run(
            ["--classify"],
            stdin=LINHA_USB71 + "\n" + LINHA_USB71_HID + "\n",
            tmp_path=tmp_path,
        )
        assert saida.count("[USB-71]") == 2

    def test_xhci_preventivo_taggeia_hc_died(self, tmp_path: Path) -> None:
        saida = _run(["--classify"], stdin=LINHA_XHCI + "\n", tmp_path=tmp_path)
        assert "[XHCI]" in saida

    def test_bt_hci_preventivo_taggeia_timeout(self, tmp_path: Path) -> None:
        saida = _run(["--classify"], stdin=LINHA_BT_HCI + "\n", tmp_path=tmp_path)
        assert "[BT-HCI]" in saida

    def test_linha_neutra_cai_no_fallback_kernel(self, tmp_path: Path) -> None:
        saida = _run(["--classify"], stdin=LINHA_NEUTRA + "\n", tmp_path=tmp_path)
        assert "[KERNEL]" in saida

    def test_formato_ts_tag_mensagem_sem_hostname(self, tmp_path: Path) -> None:
        # "TS host kernel: msg" vira "TS [TAG] msg" (formato do estudo §6).
        saida = _run(["--classify"], stdin=LINHA_JOYCON + "\n", tmp_path=tmp_path)
        assert "meowsystem" not in saida
        assert "kernel:" not in saida


class TestBtDelta:
    def test_emite_quando_piorou(self, tmp_path: Path) -> None:
        saida = _run(
            ["--test-bt-delta", "0", "0", "118", "0", "hci0"], tmp_path=tmp_path
        )
        assert "[BT-ERR] hci0 delta rx_errors=+118 tx_errors=+0 (acumulado 118/0)" in saida

    def test_silencioso_sem_delta(self, tmp_path: Path) -> None:
        saida = _run(["--test-bt-delta", "5", "7", "5", "7", "hci0"], tmp_path=tmp_path)
        assert saida == ""

    def test_delta_de_tx_tambem_conta(self, tmp_path: Path) -> None:
        saida = _run(["--test-bt-delta", "0", "1", "0", "3", "hci0"], tmp_path=tmp_path)
        assert "tx_errors=+2" in saida
        assert "(acumulado 0/3)" in saida


@pytest.fixture(scope="module")
def script_text() -> str:
    return SCRIPT_PATH.read_text(encoding="utf-8")


class TestContratoDeTexto:
    def test_loga_em_kernel_log_com_compat_storm_log(self, script_text: str) -> None:
        assert "kernel.log" in script_text
        assert "storm.log" in script_text, "compat com o storm.log antigo documentada"

    def test_preventivos_documentados_como_silenciosos(self, script_text: str) -> None:
        assert "PREVENTIVO" in script_text or "preventivo" in script_text.lower()

    def test_todos_os_padroes_do_estudo_presentes(self, script_text: str) -> None:
        for padrao in (
            "error -71",
            "joycon_enforce_subcmd_rate",
            "not accepting address",
            "unable to enumerate usb device",
            "device descriptor read/64, error",
            "xhci_hcd",
        ):
            assert padrao in script_text, f"padrão vigiado ausente: {padrao}"

    def test_nao_alarma_por_historico(self, script_text: str) -> None:
        # -n0: começa do AGORA (não relê o histórico do journal a cada restart).
        assert "-n0" in script_text
