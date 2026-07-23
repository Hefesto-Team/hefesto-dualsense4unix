"""Contratos de wiring da onda PLATAFORMA (sprint 2026-07-18).

Padrão do repo para lógica que vive em shell: testes de TEXTO travam o
contrato dos 3 scripts (install.sh, uninstall.sh, scripts/doctor.sh) e dos
instaladores de pacote — a validação viva acontece no ciclo final do install
(gate do orquestrador). Estudos: 2026-07-18-estudo-kernel-hardening.md +
2026-07-18-estudo-bt-maximo.md.

O que está travado aqui:
- PLAT-01: Proton pinado DEFAULT no install (--ensure → --lock; opt-out
  --no-proton-pin; checksum errado ABORTA), unlock simétrico no uninstall
  (o Proton extraído FICA — dado do usuário) e --report no doctor.
- PLAT-03: regras 81 (devices+hosts) em todos os instaladores + trigger pci;
  cmdline gerenciado com MERGE do token único usbcore.quirks e registro de
  dono (cmdline-owners.conf); uninstall reverte SÓ o registrado como nosso
  (strip_quirks_token para o token compartilhado).
- PLAT-04: modprobe.d do btusb DEFAULT + FastConnectable sem restart do
  bluetoothd (drop-in OU bloco marcado com sentinelas; uninstall remove).
- PLAT-06: kernel-watch DEFAULT (opt-out --no-kernel-watch); doctor resume o
  kernel.log (fallback storm.log) por tag e nunca usa a policy sysfs de ASPM.
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

INSTALL = (REPO_ROOT / "install.sh").read_text(encoding="utf-8")
UNINSTALL = (REPO_ROOT / "uninstall.sh").read_text(encoding="utf-8")
DOCTOR = (REPO_ROOT / "scripts" / "doctor.sh").read_text(encoding="utf-8")


# --- PLAT-01: Proton pinado --------------------------------------------------


class TestProtonPinWiring:
    def test_install_chama_ensure_e_lock_por_default(self) -> None:
        assert "integrations/proton_pin.py" in INSTALL
        assert '--ensure' in INSTALL
        assert '--lock' in INSTALL

    def test_install_tem_opt_out_documentado(self) -> None:
        assert "--no-proton-pin" in INSTALL

    def test_install_aborta_no_checksum_errado(self) -> None:
        # rc 1 do --ensure = checksum_mismatch → o passo NUNCA segue pro lock.
        assert "checksum" in INSTALL.lower()
        assert "não verificado" in INSTALL

    def test_install_adia_lock_com_steam_aberta(self) -> None:
        # rc 3 do --lock = Steam/jogo abertos → adiar com instrução, nunca matar.
        assert "-eq 3" in INSTALL

    def test_uninstall_destrava_e_preserva_o_proton_extraido(self) -> None:
        assert "--unlock" in UNINSTALL
        assert "dado do usuário" in UNINSTALL

    def test_uninstall_unlock_antes_do_strip_das_launch_options(self) -> None:
        # O strip (--stop-steam) REABRE a Steam ao final; o unlock exige Steam
        # fechada — então precisa vir ANTES no fluxo.
        assert UNINSTALL.index("--unlock") < UNINSTALL.index("--strip --stop-steam")

    def test_doctor_usa_o_report_read_only(self) -> None:
        assert "proton_pin.py" in DOCTOR
        assert "--report" in DOCTOR
        assert "games_off_pin" in DOCTOR or "off=" in DOCTOR

    def test_doctor_avisa_proton_9_vazando(self) -> None:
        assert "Proton <= 9" in DOCTOR


# --- PLAT-03: regras 81 + cmdline gerenciado ---------------------------------


@pytest.mark.parametrize(
    "arquivo",
    [
        "scripts/install_udev.sh",
        "scripts/install-host-udev.sh",
        "uninstall.sh",
        "scripts/doctor.sh",
        "flatpak/br.andrefarias.Hefesto.yml",
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
        # "hefesto" de install passado vence o "terceiro" do plano novo.
        assert "_register_cmdline_owner" in INSTALL

    def test_uninstall_reverte_so_o_registrado_como_nosso(self) -> None:
        assert "cmdline-owners.conf" in UNINSTALL
        assert "strip_quirks_token" in UNINSTALL
        # terceiro (Aurora) NUNCA é tocado.
        assert "preservado" in UNINSTALL

    def test_doctor_compara_proc_cmdline_e_configuration(self) -> None:
        assert "pendente de reboot" in DOCTOR
        assert "/proc/cmdline" in DOCTOR

    def test_doctor_nunca_usa_a_policy_sysfs_como_prova_de_aspm(self) -> None:
        # Armadilha provada: com pcie_aspm=off a policy sysfs mostra [default].
        assert "pcie_aspm" in DOCTOR
        assert "mente" in DOCTOR

    def test_doctor_acusa_token_usbcore_quirks_duplicado(self) -> None:
        assert "MAIS DE UM token" in DOCTOR


# --- PLAT-04: btusb + FastConnectable ---------------------------------------


class TestBtMaximoWiring:
    def test_install_instala_o_modprobe_do_btusb(self) -> None:
        assert "modprobe.d/hefesto-btusb-no-autosuspend.conf" in INSTALL

    def test_uninstall_remove_o_modprobe_do_btusb(self) -> None:
        assert "/etc/modprobe.d/hefesto-btusb-no-autosuspend.conf" in UNINSTALL

    def test_install_decide_dropin_ou_bloco_marcado(self) -> None:
        assert "/etc/bluetooth/main.conf.d" in INSTALL
        assert "hefesto-fastconnectable.conf" in INSTALL
        # ONDA-R2 (camada 1 da sprint BlueZ 2026-07-21): o bloco apensado ao
        # main.conf virou o UNIFICADO (hefesto-bt.block), reescrito de forma
        # idempotente — os .block legados só existem para o uninstall limpar
        # instalações antigas.
        assert "hefesto-bt.block" in INSTALL

    def test_install_faz_backup_do_conffile_antes_de_apensar(self) -> None:
        assert "main.conf.bak.hefesto-" in INSTALL

    def test_uninstall_remove_pelo_bloco_de_sentinelas(self) -> None:
        assert "# >>> hefesto FastConnectable >>>" in UNINSTALL
        assert "# <<< hefesto FastConnectable <<<" in UNINSTALL

    @pytest.mark.parametrize("texto", [INSTALL, UNINSTALL])
    def test_nunca_reinicia_o_bluetoothd(self, texto: str) -> None:
        # Derrubaria os controles BT conectados (provado ao vivo 2026-07-17).
        assert "systemctl restart bluetooth" not in texto
        assert "systemctl restart bluetoothd" not in texto

    def test_doctor_checa_btusb_e_fastconnectable(self) -> None:
        assert "enable_autosuspend" in DOCTOR
        assert "FastConnectable" in DOCTOR


# --- PLAT-04/doctor: clone DS4 e rádio ---------------------------------------


class TestDoctorRadio:
    def test_clone_ds4_detectado_por_modalias_com_texto_de_troca_de_modo(self) -> None:
        assert "usb:v054Cp05C4" in DOCTOR
        assert "troque o modo" in DOCTOR
        # Nunca "jogue fora" — é provavelmente um 8BitDo em modo D-input.
        assert "jogue fora" not in DOCTOR

    def test_rssi_discovering_trusted_e_idletimeout(self) -> None:
        assert "RSSI" in DOCTOR
        assert "Discovering: yes" in DOCTOR
        # WATCHDOG-FP-01: a cura de trust agora é ensinada via D-Bus (o
        # bluetoothctl 5.86 one-shot é mudo; o watchdog corrige sozinho).
        assert "Trusted b true" in DOCTOR
        assert "IdleTimeout" in DOCTOR

    def test_contadores_de_crc_como_termometro(self) -> None:
        assert "DualShock4 input CRC" in DOCTOR
        assert "DualSense input CRC" in DOCTOR


# --- PLAT-06: kernel-watch ---------------------------------------------------


class TestKernelWatchWiring:
    def test_install_tem_kernel_watch_default_com_opt_out(self) -> None:
        assert "--no-kernel-watch" in INSTALL
        # O gate antigo (opt-in via --with-storm-watch/AUTO_YES) morreu.
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


# --- doctor: regras 81 no conjunto canônico ----------------------------------


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
