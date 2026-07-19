"""Forma das regras udev 81 (PLAT-03: USB sem economia de energia).

Estudo 2026-07-18-estudo-kernel-hardening.md §2. Dois assets NOVOS:

- ``81-hefesto-usb-power.rules``: controles (Sony/Nintendo/8BitDo/Microsoft) e
  adaptadores BT (classe e0) com power/control=on + autosuspend_delay_ms=-1;
- ``81-hefesto-usb-host-power.rules``: HOSTS USB PCI por CLASSE (0x0c03*) com
  power/control=on — a economia no host derruba o barramento INTEIRO.

Contratos travados: ACTION add|change, guarda TEST=="power/control", DEVTYPE
usb_device nos devices, match por classe PCI nos hosts, nada de uaccess (a
restrição "<73" da memória só vale para TAG+="uaccess"), e a justificativa
"udev e não tmpfiles" registrada no arquivo dos hosts.
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DEVICES_RULE = REPO_ROOT / "assets" / "81-hefesto-usb-power.rules"
HOSTS_RULE = REPO_ROOT / "assets" / "81-hefesto-usb-host-power.rules"

# Vendors cobertos (PLAT-03 item 1): Sony, Nintendo, 8BitDo, Microsoft.
VENDORS = ("054c", "057e", "2dc8", "045e")


def _rule_lines(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    return [
        ln.strip()
        for ln in text.splitlines()
        if ln.strip() and not ln.lstrip().startswith("#")
    ]


@pytest.fixture(scope="module")
def devices_lines() -> list[str]:
    return _rule_lines(DEVICES_RULE)


@pytest.fixture(scope="module")
def hosts_lines() -> list[str]:
    return _rule_lines(HOSTS_RULE)


def test_arquivos_existem() -> None:
    assert DEVICES_RULE.is_file(), f"regra ausente: {DEVICES_RULE}"
    assert HOSTS_RULE.is_file(), f"regra ausente: {HOSTS_RULE}"


def test_cabecalho_marca_origem_hefesto() -> None:
    for path in (DEVICES_RULE, HOSTS_RULE):
        primeira = path.read_text(encoding="utf-8").splitlines()[0]
        assert "hefesto-dualsense4unix" in primeira, (
            f"{path.name}: primeira linha deve marcar a origem hefesto"
        )


class TestRegraDevices:
    def test_cobre_todos_os_vendors_de_controle(self, devices_lines: list[str]) -> None:
        blob = "\n".join(devices_lines)
        for vendor in VENDORS:
            assert f'ATTR{{idVendor}}=="{vendor}"' in blob, f"vendor {vendor} não coberto"

    def test_cobre_adaptador_bt_por_classe_e0(self, devices_lines: list[str]) -> None:
        blob = "\n".join(devices_lines)
        assert 'ATTR{bDeviceClass}=="e0"' in blob, (
            "adaptadores BT (classe e0, ex.: TP-Link 2357:0604) não cobertos"
        )

    def test_toda_linha_e_add_change_usb_device_com_guarda(
        self, devices_lines: list[str]
    ) -> None:
        assert devices_lines, "nenhuma linha de regra"
        for ln in devices_lines:
            assert 'ACTION=="add|change"' in ln, f"sem add|change: {ln}"
            assert 'SUBSYSTEM=="usb"' in ln, f"sem SUBSYSTEM usb: {ln}"
            assert 'ENV{DEVTYPE}=="usb_device"' in ln, (
                f"power/ vive no device, não na interface: {ln}"
            )
            assert 'TEST=="power/control"' in ln, f"sem guarda TEST: {ln}"
            assert 'ATTR{power/control}="on"' in ln, f"sem power/control=on: {ln}"
            assert 'ATTR{power/autosuspend_delay_ms}="-1"' in ln, (
                f"sem a trava redundante delay=-1: {ln}"
            )


class TestRegraHosts:
    def test_match_por_classe_pci_nao_por_driver(self, hosts_lines: list[str]) -> None:
        assert hosts_lines, "nenhuma linha de regra"
        for ln in hosts_lines:
            assert 'SUBSYSTEM=="pci"' in ln, f"sem SUBSYSTEM pci: {ln}"
            assert 'ATTR{class}=="0x0c03*"' in ln, (
                f"match deve ser por CLASSE USB-host (0x0c03*), não por driver: {ln}"
            )
            assert 'ACTION=="add|change"' in ln, f"sem add|change: {ln}"
            assert 'TEST=="power/control"' in ln, f"sem guarda TEST: {ln}"
            assert 'ATTR{power/control}="on"' in ln, f"sem power/control=on: {ln}"

    def test_nao_usa_driver_xhci_hcd(self, hosts_lines: list[str]) -> None:
        # A Aurora usa DRIVER=="xhci_hcd"; a nossa pega o host ANTES do bind.
        blob = "\n".join(hosts_lines)
        assert 'DRIVER=="xhci_hcd"' not in blob

    def test_justificativa_udev_e_nao_tmpfiles_documentada(self) -> None:
        texto = HOSTS_RULE.read_text(encoding="utf-8").lower()
        assert "tmpfiles" in texto, (
            "o arquivo dos hosts deve explicar por que udev e NÃO tmpfiles "
            "(tmpfiles não filtra por atributo — pegaria GPU/NVMe)"
        )


def test_nenhuma_regra_81_usa_uaccess() -> None:
    # uaccess exige número < 73 (memória reference_udev_uaccess_ordem_73);
    # estas regras não concedem ACL — não podem usar a TAG.
    for path in (DEVICES_RULE, HOSTS_RULE):
        assert "uaccess" not in path.read_text(encoding="utf-8"), (
            f"{path.name}: TAG uaccess proibida numa regra 81"
        )


def test_nomes_distintos_mesmo_numero_nao_colidem() -> None:
    # Escolha documentada: ambos 81 (nomes distintos; udev ordena léxico).
    assert DEVICES_RULE.name != HOSTS_RULE.name
    assert DEVICES_RULE.name.startswith("81-")
    assert HOSTS_RULE.name.startswith("81-")
