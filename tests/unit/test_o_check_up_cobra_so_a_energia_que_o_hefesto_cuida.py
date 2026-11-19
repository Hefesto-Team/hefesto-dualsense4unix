"""O Check-up cobra só a energia USB que o Hefesto mantém acordada.

O-CHECK-UP-COBRA-SO-A-ENERGIA-QUE-O-HEFESTO-CUIDA-01 (19/11/2026). A regra 81 põe em ``on`` os
quatro fabricantes de controle, sempre, e o adaptador de classe ``e0`` só em computador sem
bateria; o hub fica com o kernel. «Tem bateria» é ``type=Battery`` com ``scope`` diferente de
``Device``. O exame (``exame_da_mesa``), a R5 (``ordens_da_mesa``) e o ``doctor.sh`` perguntam
a esse conjunto. TUDO É DE MENTIRA: o ``/sys`` mora em ``tmp_path``.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import bateria_do_computador
from hefesto_dualsense4unix.integrations import exame_da_mesa as exame
from hefesto_dualsense4unix.integrations import ordens_da_mesa as ordens
from hefesto_dualsense4unix.integrations.censo_do_barramento import Censo
from tests.unit import ensaio_das_ordens as ensaio

BASH = shutil.which("bash") or "/bin/bash"
DOCTOR = Path(__file__).resolve().parents[2] / "scripts" / "doctor.sh"
RODE = "Rode a instalação"


def _aparelho(sysfs: Path, no: str, vid: str, classe: str, controle: str) -> Path:
    real = sysfs / "devices" / "pci0000:00" / "usb1" / no
    (real / "power").mkdir(parents=True)
    (real / "idVendor").write_text(f"{vid}\n", encoding="utf-8")
    (real / "bDeviceClass").write_text(f"{classe}\n", encoding="utf-8")
    (real / "power" / "control").write_text(f"{controle}\n", encoding="utf-8")
    (real / "subsystem").symlink_to(sysfs / "bus" / "usb")
    (sysfs / "bus" / "usb" / "devices" / no).symlink_to(real)
    return real


def _fonte(sysfs: Path, nome: str, escopo: str) -> None:
    fonte = sysfs / "class" / "power_supply" / nome
    fonte.mkdir(parents=True)
    (fonte / "type").write_text("Battery\n", encoding="utf-8")
    (fonte / "scope").write_text(f"{escopo}\n", encoding="utf-8")


def _radio(sysfs: Path, pai: Path) -> None:
    hci = pai / "bluetooth" / "hci0"
    hci.mkdir(parents=True)
    (sysfs / "class" / "bluetooth").mkdir(parents=True)
    (sysfs / "class" / "bluetooth" / "hci0").symlink_to(hci)


def _sys(tmp_path: Path, *, bateria: bool, dualsense: str = "on", adaptador: str = "on") -> Path:
    """Hub raiz e hub em ``auto``, DualSense e adaptador ``e0`` com o rádio."""
    sysfs = tmp_path / "sys"
    (sysfs / "bus" / "usb" / "devices").mkdir(parents=True)
    _aparelho(sysfs, "usb1", "1d6b", "09", "auto")
    _aparelho(sysfs, "1-1", "05e3", "09", "auto")
    _aparelho(sysfs, "1-1.2", "054c", "00", dualsense)
    adaptador_no = _aparelho(sysfs, "1-1.4", "2357", "e0", adaptador)
    _radio(sysfs, adaptador_no / "1-1.4:1.0")
    _fonte(sysfs, "ps-controller-battery-aa", "Device")
    if bateria:
        _fonte(sysfs, "BATT", "System")
    return sysfs


def _portas(sysfs: Path) -> exame.Item:
    return exame.energia_das_portas(
        raiz=sysfs / "bus" / "usb" / "devices", fontes_de_energia=sysfs / "class" / "power_supply"
    )


def _doctor(sysfs: Path, funcao: str, **env: str) -> str:
    r = subprocess.run(
        [BASH, "-c", f'source "{DOCTOR}"; QUIET=0; {funcao}'],
        capture_output=True, text=True, timeout=60, check=False,
        env={"PATH": "/usr/bin:/bin", "HOME": str(sysfs), "HEFESTO_DOCTOR_SYS": str(sysfs), **env},
    )
    return r.stdout + r.stderr


def test_sem_bateria_o_hub_em_auto_nao_e_aviso_e_o_controle_e(tmp_path: Path) -> None:
    """D-1310-A-ENERGIA-USB-DE-DESKTOP-SO-SEM-BATERIA: só o que a regra 81 acorda conta."""
    sysfs = _sys(tmp_path, bateria=False)
    assert _portas(sysfs).estado == exame.ESTADO_CERTO
    assert "[WARN]" not in _doctor(sysfs, "check_usb_power_devices")
    sysfs = _sys(tmp_path / "doente", bateria=False, dualsense="auto")
    item = _portas(sysfs)
    assert item.estado == exame.ESTADO_ATENCAO and item.porque.startswith("1 de 2 ")
    assert "economia de energia ATIVA em 1 device(s) USB: 1-1.2 (054c" in _doctor(
        sysfs, "check_usb_power_devices")


def test_com_bateria_o_adaptador_em_auto_nao_manda_instalar(tmp_path: Path) -> None:
    sysfs = _sys(tmp_path, bateria=True, adaptador="auto")
    item = _portas(sysfs)
    assert item.estado == exame.ESTADO_CERTO and item.cura is None
    saida = _doctor(sysfs, "check_usb_power_devices")
    assert "[WARN]" not in saida and "3 outro(s) device(s) em 'auto'" in saida, saida
    dormindo = ensaio.aparelho(
        "3-1.1.4", pai="3-1.1", busnum=3, devpath="1.1.4", pci=ensaio.PCI_DO_HUB,
        atras_de_hub=True, classe="e0", subclasse="01", protocolo="01", vid="2357",
        pid="0604", controle="auto",
    )
    sadios = tuple(a for a in ensaio.APARELHOS if a.nome_do_kernel != "3-1.1.4")
    censo = Censo(aparelhos=(*sadios, dormindo))
    sem = ordens.Leitura(censo=censo, entradas=ensaio.entradas())
    assert ordens.dongle_dorme(sem) is not None
    com = ordens.Leitura(censo=censo, entradas=ensaio.entradas(), bateria=True)
    assert ordens.dongle_dorme(com) is None
    assert all(RODE not in (o.acao or "") for o in ordens.catalogo(com))


@pytest.mark.parametrize(("escopo", "bateria"), [("System", True), ("Device", False)])
def test_a_bateria_e_a_do_computador_pelo_tipo(tmp_path: Path, escopo: str,
                                                bateria: bool) -> None:
    sysfs = tmp_path / "sys"
    _fonte(sysfs, "CMB0", escopo)
    assert bateria_do_computador.tem_bateria(sysfs / "class" / "power_supply") is bateria
    r = subprocess.run(
        [BASH, "-c", f'source "{DOCTOR}"; _doctor_tem_bateria && echo sim || echo falso'],
        capture_output=True, text=True, timeout=60, check=False,
        env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path), "HEFESTO_DOCTOR_SYS": str(sysfs)},
    )
    assert r.stdout.strip() == ("sim" if bateria else "falso"), r.stderr


@pytest.mark.parametrize("usb", [True, False])
def test_o_radio_que_nao_e_usb_nao_cobra_o_btusb(tmp_path: Path, usb: bool) -> None:
    """D-1911-O-RADIO-QUE-NAO-E-USB-NAO-COBRA-O-BTUSB: UART, SDIO e PCIe ficam certos."""
    sysfs = tmp_path / "sys"
    if usb:
        sysfs = _sys(tmp_path, bateria=False)
    else:
        _radio(sysfs, sysfs / "devices" / "platform" / "serial8250" / "serial0" / "serial0-0")
    sem_btusb = tmp_path / "sem-btusb" / "enable_autosuspend"
    item = exame.energia_do_radio(
        parametro=sem_btusb, conf=tmp_path / "sem-conf", bluetooth=sysfs / "class" / "bluetooth"
    )
    saida = _doctor(sysfs, "check_btusb_autosuspend", HEFESTO_DOCTOR_BTUSB_PARAM=str(sem_btusb),
                    HEFESTO_DOCTOR_BTUSB_CONF=str(tmp_path / "sem-conf"))
    if usb:
        assert item.estado == exame.ESTADO_NAO_SEI and item.cura is not None
        assert "não é USB" not in saida, saida
    else:
        assert (item.estado, item.cura) == (exame.ESTADO_CERTO, None)
        assert "o adaptador Bluetooth não é USB" in saida, saida
