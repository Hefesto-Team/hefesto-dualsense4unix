"""Contratos de wiring da onda PLATAFORMA (sprint 2026-07-18)."""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

INSTALL = (REPO_ROOT / "install.sh").read_text(encoding="utf-8")
UNINSTALL = (REPO_ROOT / "uninstall.sh").read_text(encoding="utf-8")
DOCTOR = (REPO_ROOT / "scripts" / "doctor.sh").read_text(encoding="utf-8")
BLUEZ_CONFIG = (REPO_ROOT / "scripts" / "bluez_config.sh").read_text(encoding="utf-8")


class TestProtonPinWiring:
    def test_install_chama_ensure_e_lock_por_default(self) -> None:
        assert "integrations/proton_pin.py" in INSTALL
        assert '--ensure' in INSTALL
        assert '--lock' in INSTALL

    def test_install_tem_opt_out_documentado(self) -> None:
        assert "--no-proton-pin" in INSTALL

    def test_install_aborta_no_checksum_errado(self) -> None:
        assert "checksum" in INSTALL.lower()
        assert "não verificado" in INSTALL

    def test_install_adia_lock_com_steam_aberta(self) -> None:
        assert "-eq 3" in INSTALL

    def test_uninstall_destrava_e_preserva_o_proton_extraido(self) -> None:
        assert "--unlock" in UNINSTALL
        assert "dado do usuário" in UNINSTALL

    def test_uninstall_unlock_antes_do_strip_das_launch_options(self) -> None:
        assert UNINSTALL.index("--unlock") < UNINSTALL.index("--strip --stop-steam")

    def test_doctor_usa_o_report_read_only(self) -> None:
        assert "proton_pin.py" in DOCTOR
        assert "--report" in DOCTOR
        assert "games_off_pin" in DOCTOR or "off=" in DOCTOR

    def test_doctor_avisa_proton_9_vazando(self) -> None:
        assert "Proton <= 9" in DOCTOR


@pytest.mark.parametrize(
    "arquivo",
    [
        "scripts/install_udev.sh",
        "scripts/install-host-udev.sh",
        "uninstall.sh",
        "scripts/doctor.sh",
        "flatpak/io.github.hefesto_team.hefesto_dualsense4unix.yml",
        "packaging/fedora/hefesto-dualsense4unix.spec",
        "packaging/arch/PKGBUILD",
    ],
)
@pytest.mark.parametrize(
    "regra", ["81-hefesto-usb-power.rules", "81-hefesto-usb-host-power.rules"]
)
def test_regras_81_cobertas_nos_instaladores(arquivo: str, regra: str) -> None:
    texto = (REPO_ROOT / arquivo).read_text(encoding="utf-8")
    assert regra in texto, f"{arquivo} não cobre a regra {regra}"


def test_build_deb_cobre_as_81_por_glob() -> None:
    texto = (REPO_ROOT / "scripts" / "build_deb.sh").read_text(encoding="utf-8")
    assert "assets/81-*.rules" in texto


@pytest.mark.parametrize(
    "arquivo", ["scripts/install_udev.sh", "scripts/install-host-udev.sh"]
)
def test_trigger_pci_aplica_a_81_host_sem_reboot(arquivo: str) -> None:
    texto = (REPO_ROOT / arquivo).read_text(encoding="utf-8")
    assert "--subsystem-match=pci" in texto


class TestCmdlineGerenciado:
    def test_install_usa_o_modulo_puro_de_merge(self) -> None:
        assert "kernel_cmdline" in INSTALL
        assert "plan_tokens" in INSTALL
        assert "forbidden_reintroductions" in INSTALL

    def test_install_traduz_o_plano_em_kernelstub(self) -> None:
        assert "kernelstub --delete-options" in INSTALL
        assert "kernelstub --add-options" in INSTALL

    def test_install_registra_dono_em_estado_local(self) -> None:
        assert "cmdline-owners.conf" in INSTALL
        assert "_register_cmdline_owner" in INSTALL

    def test_uninstall_reverte_so_o_registrado_como_nosso(self) -> None:
        assert "cmdline-owners.conf" in UNINSTALL
        assert "strip_quirks_token" in UNINSTALL
        assert "preservado" in UNINSTALL

    def test_doctor_compara_proc_cmdline_e_configuration(self) -> None:
        assert "pendente de reboot" in DOCTOR
        assert "/proc/cmdline" in DOCTOR

    def test_doctor_nunca_usa_a_policy_sysfs_como_prova_de_aspm(self) -> None:
        assert "pcie_aspm" in DOCTOR
        assert "mente" in DOCTOR

    def test_doctor_acusa_token_usbcore_quirks_duplicado(self) -> None:
        assert "MAIS DE UM token" in DOCTOR


class TestBtMaximoWiring:
    def test_install_instala_o_modprobe_do_btusb(self) -> None:
        assert "modprobe.d/hefesto-btusb-no-autosuspend.conf" in INSTALL

    def test_uninstall_remove_o_modprobe_do_btusb(self) -> None:
        assert "/etc/modprobe.d/hefesto-btusb-no-autosuspend.conf" in UNINSTALL

    def test_install_e_uninstall_chamam_o_dono_da_config_do_bluez(self) -> None:
        """A fiação que substitui os testes de texto: quem faz é o script."""
        assert 'scripts/bluez_config.sh" aplicar' in INSTALL
        assert 'scripts/bluez_config.sh" remover' in UNINSTALL

    def test_install_escreve_dropin_e_tambem_o_bloco_marcado(self) -> None:
        assert "/etc/bluetooth" in BLUEZ_CONFIG
        assert "hefesto-fastconnectable.conf" in BLUEZ_CONFIG
        assert "hefesto-bt.block" in BLUEZ_CONFIG

    def test_install_faz_backup_do_conffile_antes_de_apensar(self) -> None:
        assert "main.conf.bak.hefesto-" in BLUEZ_CONFIG

    def test_uninstall_remove_pelo_bloco_de_sentinelas(self) -> None:
        assert "hefesto (bluetooth|FastConnectable|JustWorksRepairing) >>>" in BLUEZ_CONFIG
        assert "hefesto (bluetooth|FastConnectable|JustWorksRepairing) <<<" in BLUEZ_CONFIG

    @pytest.mark.parametrize("texto", [INSTALL, UNINSTALL, BLUEZ_CONFIG])
    def test_nunca_reinicia_o_bluetoothd(self, texto: str) -> None:
        assert "systemctl restart bluetooth" not in texto
        assert "systemctl restart bluetoothd" not in texto

    def test_doctor_checa_btusb_e_fastconnectable(self) -> None:
        assert "enable_autosuspend" in DOCTOR
        assert "FastConnectable" in DOCTOR
        assert "JustWorksRepairing" in DOCTOR


class TestDoctorRadio:
    def test_clone_ds4_detectado_por_modalias_com_texto_de_troca_de_modo(self) -> None:
        assert "usb:v054Cp05C4" in DOCTOR
        assert "não troque para Switch sem o cabo" in DOCTOR
        assert "RECOMENDADO por rádio" in DOCTOR
        assert "degradando o Bluetooth de TODOS" not in DOCTOR
        assert "jogue fora" not in DOCTOR

    def test_rssi_discovering_trusted_e_idletimeout(self) -> None:
        assert "RSSI" in DOCTOR
        assert "Discovering: yes" in DOCTOR
        assert "Trusted b true" in DOCTOR
        assert "IdleTimeout" in DOCTOR

    def test_contadores_de_crc_como_termometro(self) -> None:
        assert "DualShock4 input CRC" in DOCTOR
        assert "DualSense input CRC" in DOCTOR


class TestKernelWatchWiring:
    def test_install_tem_kernel_watch_default_com_opt_out(self) -> None:
        assert "--no-kernel-watch" in INSTALL
        assert 'WITH_STORM_WATCH}" -eq 1' not in INSTALL

    def test_flag_antiga_segue_aceita_como_compat(self) -> None:
        assert "--with-storm-watch" in INSTALL

    def test_doctor_le_kernel_log_com_fallback_storm_log(self) -> None:
        assert "kernel.log" in DOCTOR
        assert "storm.log" in DOCTOR

    @pytest.mark.parametrize("tag", ["USB-71", "JOYCON", "BT-HCI", "XHCI", "BT-ERR"])
    def test_doctor_conta_por_tag(self, tag: str) -> None:
        assert tag in DOCTOR

    def test_uninstall_remove_symlink_de_compat_mas_preserva_log(self) -> None:
        assert "storm.log" in UNINSTALL
        assert "kernel.log" in UNINSTALL


def test_doctor_lista_as_81_no_conjunto_canonico() -> None:
    assert "81-hefesto-usb-power.rules" in DOCTOR
    assert "81-hefesto-usb-host-power.rules" in DOCTOR


def test_doctor_checa_power_control_de_devices_e_hosts() -> None:
    assert "/sys/bus/usb/devices" in DOCTOR
    assert "0x0c03" in DOCTOR


def test_doctor_caca_sabotadores_de_energia() -> None:
    assert "tlp" in DOCTOR
    assert "powertop" in DOCTOR
    assert "tuned" in DOCTOR
    assert "med_power" in DOCTOR
