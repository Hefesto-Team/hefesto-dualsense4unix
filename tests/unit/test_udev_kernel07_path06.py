"""Contratos KERNEL-07 + PATH-06 (sprint 2026-07-18-sprint-infra-kernel-install).

Padrão do repo para lógica que vive em shell/regras udev: testes de TEXTO
travam o contrato dos arquivos (assets/*.rules, install/uninstall, doctor) —
a validação viva acontece no ciclo final do install (gate do orquestrador).

- Regra 70 cobre o hidraw do VPAD uhid (bus 0003, sem pai USB real) — sem
  depender do steam-devices de terceiro; uaccess vale porque 70 < 73-seat-late.
- Regra 80 esconde os js legados de Motion Sensors (MODE 0000).
- Regra 78 ampliada: nomes BT (sem prefixo Sony) e vpads Hefesto Virtual.
- Assets 73/74 (hotplug-GUI) fora do repo; rm compensatório preservado.
- Symlink ~/.local/bin/hefesto-launch no install, removido no uninstall.
- Doctor: wrapper no PATH + contagem de jogos com wrapper + WARN da env morta
  PROTON_ENABLE_HIDRAW no launch_env.
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
ASSETS = REPO_ROOT / "assets"


def _rule_lines(path: Path) -> list[str]:
    """Linhas de regra (não-comentário, não-vazias) de um .rules."""
    return [
        ln.strip()
        for ln in path.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.lstrip().startswith("#")
    ]


# --- regra 70: hidraw do vpad uhid ------------------------------------------


def test_regra_70_cobre_o_hidraw_do_vpad_uhid() -> None:
    linhas = _rule_lines(ASSETS / "70-ps5-controller.rules")
    vpad = [ln for ln in linhas if 'KERNELS=="0003:054C:0DF2.*"' in ln]
    assert vpad, "regra 70 sem o match do vpad uhid (KERNELS 0003:054C:0DF2.*)"
    for ln in vpad:
        assert 'MODE="0660"' in ln, ln
        assert 'TAG+="uaccess"' in ln, ln
        assert 'SUBSYSTEM=="hidraw"' in ln, ln


def test_regra_70_mantem_fisico_usb_e_bt() -> None:
    blob = "\n".join(_rule_lines(ASSETS / "70-ps5-controller.rules"))
    assert 'ATTRS{idVendor}=="054c"' in blob  # USB físico
    assert 'KERNELS=="0005:054C:0CE6.*"' in blob  # BT standard
    assert 'KERNELS=="0005:054C:0DF2.*"' in blob  # BT Edge


# --- regra 80: js de Motion Sensors fora da API legada -----------------------


def test_regra_80_esconde_js_de_motion_sensors() -> None:
    linhas = _rule_lines(ASSETS / "80-motion-joydev-hide.rules")
    assert linhas, "80-motion-joydev-hide.rules sem linhas de regra"
    for ln in linhas:
        assert 'SUBSYSTEM=="input"' in ln, ln
        assert 'KERNEL=="js[0-9]*"' in ln, ln
        # ATTRS (plural) sobe a hierarquia js -> input parent, onde vive o name.
        assert 'ATTRS{name}=="*Motion Sensors*"' in ln, ln
        assert 'MODE="0000"' in ln, ln


def test_regra_80_nunca_toca_event_nem_hidraw() -> None:
    blob = "\n".join(_rule_lines(ASSETS / "80-motion-joydev-hide.rules"))
    assert 'KERNEL=="event' not in blob, "80 não pode tocar evdev (IMU real dos apps)"
    assert "hidraw" not in blob


# --- regra 78 ampliada: nomes BT e vpads -------------------------------------


@pytest.mark.parametrize(
    "nome",
    [
        # físico USB (prefixo Sony) — cobertura original
        "Sony Interactive Entertainment DualSense Wireless Controller Motion Sensors",
        "Sony Interactive Entertainment DualSense Edge Wireless Controller Motion Sensors",
        # BT: o kernel expõe SEM o prefixo do vendor
        '=="DualSense Wireless Controller Motion Sensors"',
        '=="DualSense Edge Wireless Controller Motion Sensors"',
        # vpads uhid do daemon (nome próprio, P1..P4 via wildcard)
        "Hefesto Virtual DualSense P* Motion Sensors",
    ],
)
def test_regra_78_cobre_todos_os_nomes(nome: str) -> None:
    blob = "\n".join(_rule_lines(ASSETS / "78-dualsense-motion-not-joystick.rules"))
    assert nome in blob, f"regra 78 não cobre: {nome}"


def test_regra_78_sempre_zera_joystick_e_marca_acelerometro() -> None:
    for ln in _rule_lines(ASSETS / "78-dualsense-motion-not-joystick.rules"):
        assert 'ENV{ID_INPUT_JOYSTICK}=""' in ln, ln
        assert 'ENV{ID_INPUT_ACCELEROMETER}="1"' in ln, ln


# --- assets 73/74 removidos, rm compensatório preservado ---------------------


def test_assets_73_e_74_sairam_do_repo() -> None:
    assert not (ASSETS / "73-ps5-controller-hotplug.rules").exists()
    assert not (ASSETS / "74-ps5-controller-hotplug-bt.rules").exists()


def test_rm_compensatorio_de_73_74_permanece_no_install_udev() -> None:
    """Instalações antigas ainda têm 73/74 em /etc — o rm fica por 1 release."""
    texto = (REPO_ROOT / "scripts/install_udev.sh").read_text(encoding="utf-8")
    assert "rm -f /etc/udev/rules.d/73-ps5-controller-hotplug.rules" in texto
    assert "74-ps5-controller-hotplug-bt.rules" in texto


# --- conjunto canônico sincronizado em todos os instaladores -----------------


@pytest.mark.parametrize(
    "arquivo",
    [
        "scripts/install_udev.sh",
        "scripts/install-host-udev.sh",
        "uninstall.sh",
        "scripts/doctor.sh",
        "scripts/build_deb.sh",
        "flatpak/br.andrefarias.Hefesto.yml",
        "packaging/fedora/hefesto-dualsense4unix.spec",
    ],
)
def test_regra_80_coberta_nos_instaladores(arquivo: str) -> None:
    texto = (REPO_ROOT / arquivo).read_text(encoding="utf-8")
    assert "80-motion-joydev-hide.rules" in texto or "assets/80-*.rules" in texto, (
        f"{arquivo} não cobre a regra 80"
    )


def test_uninstall_dispara_trigger_de_input() -> None:
    """Sem o trigger de input os js da 80 e as flags da 78 só voltam no replug."""
    texto = (REPO_ROOT / "uninstall.sh").read_text(encoding="utf-8")
    assert "--subsystem-match=input" in texto


def test_install_host_udev_dispara_trigger_de_input() -> None:
    texto = (REPO_ROOT / "scripts/install-host-udev.sh").read_text(encoding="utf-8")
    assert "--subsystem-match=input" in texto


# --- PATH-06: symlink do wrapper no PATH -------------------------------------


def test_install_cria_symlink_hefesto_launch_no_path() -> None:
    texto = (REPO_ROOT / "install.sh").read_text(encoding="utf-8")
    assert 'ln -sf "${LAUNCH_WRAPPER_TARGET}" "${BIN_DIR}/hefesto-launch"' in texto


def test_uninstall_remove_o_symlink_do_path() -> None:
    texto = (REPO_ROOT / "uninstall.sh").read_text(encoding="utf-8")
    assert '.local/bin/hefesto-launch' in texto
    assert 'rm -f "${HOME}/.local/bin/hefesto-launch"' in texto


def test_string_canonica_do_wrapper_continua_por_caminho_absoluto() -> None:
    """PATH-06 item 1: o symlink é conveniência — WRAPPER_LAUNCH INALTERADA
    (formato `sh -c` com caminho absoluto, funciona sem PATH)."""
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    assert slo.WRAPPER_LAUNCH.startswith("sh -c '")
    assert slo.WRAPPER_HOME_RELPATH in slo.WRAPPER_LAUNCH
    assert slo.WRAPPER_LAUNCH.endswith(" %command%")


# --- doctor: checks novos ----------------------------------------------------


def test_doctor_checa_wrapper_no_path() -> None:
    texto = (REPO_ROOT / "scripts/doctor.sh").read_text(encoding="utf-8")
    assert "command -v hefesto-launch" in texto
    assert "wrapper no PATH" in texto


def test_doctor_conta_jogos_com_wrapper_aplicado() -> None:
    texto = (REPO_ROOT / "scripts/doctor.sh").read_text(encoding="utf-8")
    assert ".local/share/hefesto-dualsense4unix/bin/hefesto-launch" in texto
    assert "wrapper hefesto-launch aplicado" in texto


def test_doctor_avisa_env_morta_proton_enable_hidraw() -> None:
    """MISC-08 item 6: PROTON_ENABLE_HIDRAW é herança do Proton <= 9 — presença
    num launch_env/*.env indica materialização antiga do daemon."""
    texto = (REPO_ROOT / "scripts/doctor.sh").read_text(encoding="utf-8")
    assert "PROTON_ENABLE_HIDRAW" in texto
    assert "env morta" in texto


def test_doctor_lista_a_80_no_conjunto_canonico() -> None:
    texto = (REPO_ROOT / "scripts/doctor.sh").read_text(encoding="utf-8")
    assert "80-motion-joydev-hide.rules" in texto
