"""O pad virtual e o som dele nascem no mesmo USB (O-PAD-VIRTUAL-E-O-SOM-DELE-NASCEM-NO-MESMO-USB-01).

Tudo aqui roda num sysfs e num configfs DE MENTIRA, montados no ``tmp_path``: a
suíte nunca monta gadget, nunca escreve no ``/sys`` real e nunca acha o aparelho
de quem roda. A prova no aparelho e no jogo é da bancada, no fecho.

O que se prova, nesta ordem:

1. **«É pad nosso» tem um dono** (``integrations/pad_usb.py``): reconhece o uhid
   e o gadget sob o ``vhci_hcd``, e recusa o Edge FÍSICO pelo cabo, pelo rádio e
   por um ``usbip`` de verdade. O espelho do broker responde igual em toda a
   tabela. Os seis lugares que perguntavam por ``misc/uhid`` perguntam a ele.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from hefesto_dualsense4unix.broker import hidraw_broker as broker
from hefesto_dualsense4unix.integrations import pad_usb

# Faixas forjadas da casa: ``aa:bb:cc`` e ``02:fe``; nunca um endereço real.
MAC_DO_PAD = "02:fe:8a:00:00:01"
SERIAL_DO_PAD = "hefesto-pad-02fe8a000001"
MAC_DO_EDGE = "aa:bb:cc:00:00:11"
MAC_DO_ADAPTADOR = "aa:bb:cc:00:00:10"


def _escrever(caminho: Path, texto: str) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(texto, encoding="utf-8")


def _uevent(hid_id: str, phys: str = "", uniq: str = "") -> str:
    linhas = ["DRIVER=playstation", f"HID_ID={hid_id}"]
    if phys:
        linhas.append(f"HID_PHYS={phys}")
    if uniq:
        linhas.append(f"HID_UNIQ={uniq}")
    return "\n".join(linhas) + "\n"


def _usb_device(raiz: Path, rel: str, *, serial: str, pid: str = "0df2") -> Path:
    dev = raiz / rel
    _escrever(dev / "idVendor", "054c\n")
    _escrever(dev / "idProduct", f"{pid}\n")
    _escrever(dev / "busnum", rel.split("/")[-2].removeprefix("usb") + "\n")
    _escrever(dev / "devnum", "2\n")
    if serial:
        _escrever(dev / "serial", serial + "\n")
    return dev


class Mesa:
    """Um sysfs de mentira com os cinco aparelhos que a pergunta separa."""

    def __init__(self, raiz: Path) -> None:
        self.raiz = raiz
        sys = raiz / "sys"
        self.sys = sys
        gadget = _usb_device(
            sys, "devices/platform/vhci_hcd.0/usb3/3-1", serial=SERIAL_DO_PAD
        )
        self.gadget_usb = gadget
        self.gadget_hid = gadget / "3-1:1.0" / "0003:054C:0DF2.0010"
        _escrever(
            self.gadget_hid / "uevent",
            _uevent("0003:0000054C:00000DF2", "usb-vhci_hcd.0-1/input0", MAC_DO_PAD),
        )
        self.uhid_hid = sys / "devices/virtual/misc/uhid/0003:054C:0DF2.0011"
        _escrever(
            self.uhid_hid / "uevent",
            _uevent("0003:0000054C:00000DF2", "hefesto-vpad-1", MAC_DO_PAD),
        )
        self.bt_hid = sys / "devices/virtual/misc/uhid/0005:054C:0DF2.0012"
        _escrever(
            self.bt_hid / "uevent",
            _uevent("0005:0000054C:00000DF2", MAC_DO_ADAPTADOR, MAC_DO_EDGE),
        )
        cabo = _usb_device(
            sys, "devices/pci0000:00/0000:00:14.0/usb1/1-2", serial=""
        )
        self.cabo_hid = cabo / "1-2:1.3" / "0003:054C:0DF2.0013"
        _escrever(
            self.cabo_hid / "uevent",
            _uevent("0003:0000054C:00000DF2", "usb-0000:00:14.0-2/input3", MAC_DO_EDGE),
        )
        # Um Edge de plástico emprestado por um ``usbip`` de verdade: mora sob o
        # ``vhci_hcd`` como o gadget, sem nenhuma marca do Hefesto.
        usbip = _usb_device(sys, "devices/platform/vhci_hcd.0/usb3/3-2", serial="")
        self.usbip_hid = usbip / "3-2:1.3" / "0003:054C:0DF2.0014"
        _escrever(
            self.usbip_hid / "uevent",
            _uevent("0003:0000054C:00000DF2", "usb-vhci_hcd.0-2/input3", MAC_DO_EDGE),
        )
        self.classe = sys / "class" / "hidraw"
        self.classe.mkdir(parents=True)
        for n, hid in enumerate(
            (self.gadget_hid, self.uhid_hid, self.bt_hid, self.cabo_hid, self.usbip_hid)
        ):
            (hid / "hidraw" / f"hidraw{n}").mkdir(parents=True)
            (self.classe / f"hidraw{n}").mkdir()
            os.symlink(hid, self.classe / f"hidraw{n}" / "device")

    def casos(self) -> list[tuple[str, Path, bool]]:
        return [
            ("gadget", self.gadget_hid, True),
            ("uhid", self.uhid_hid, True),
            ("edge-pelo-radio", self.bt_hid, False),
            ("edge-pelo-cabo", self.cabo_hid, False),
            ("edge-por-usbip", self.usbip_hid, False),
        ]


@pytest.fixture
def mesa(tmp_path: Path) -> Mesa:
    return Mesa(tmp_path)


def _campos(hid: Path) -> dict[str, str]:
    return pad_usb.campos_do_uevent((hid / "uevent").read_text(encoding="utf-8"))


def _pergunta_ao_dono(hid: Path, **troca: str) -> bool:
    campos = _campos(hid) | troca
    return pad_usb.e_pad_nosso(
        str(hid),
        phys=campos.get("HID_PHYS", ""),
        uniq=campos.get("HID_UNIQ", ""),
        bus=pad_usb.bus_do_hid_id(campos.get("HID_ID", "")),
    )


def _pergunta_ao_broker(hid: Path, **troca: str) -> bool:
    campos = _campos(hid) | troca
    bus = pad_usb.bus_do_hid_id(campos.get("HID_ID", ""))
    assert bus is not None
    return broker._e_o_nosso_vpad(campos, str(hid), bus)


class TestEPadNossoTemUmDono:
    def test_reconhece_o_uhid_e_o_gadget_e_recusa_o_edge_fisico(self, mesa: Mesa) -> None:
        for nome, hid, esperado in mesa.casos():
            assert _pergunta_ao_dono(hid) is esperado, nome

    def test_o_gadget_antes_do_probe_e_nosso_pelo_serial(self, mesa: Mesa) -> None:
        """Antes do ``hid_playstation``, o ``HID_UNIQ`` é o serial USB."""
        assert _pergunta_ao_dono(mesa.gadget_hid, HID_UNIQ=SERIAL_DO_PAD)

    def test_o_gadget_sem_uniq_e_nosso_pelo_serial_do_usb_device(self, mesa: Mesa) -> None:
        """Sem marca no uevent, quem responde é o serial do ``usb_device`` pai."""
        assert _pergunta_ao_dono(mesa.gadget_hid, HID_UNIQ="")

    def test_o_espelho_do_broker_responde_igual_em_toda_a_tabela(self, mesa: Mesa) -> None:
        trocas: list[dict[str, str]] = [{}, {"HID_UNIQ": ""}, {"HID_UNIQ": SERIAL_DO_PAD}]
        for nome, hid, _ in mesa.casos():
            for troca in trocas:
                assert _pergunta_ao_dono(hid, **troca) == _pergunta_ao_broker(hid, **troca), (
                    nome,
                    troca,
                )

    def test_o_broker_nunca_toma_o_gadget_por_fisico(self, mesa: Mesa) -> None:
        nao_ha_radio = str(mesa.raiz / "sem-bluetooth")
        for nome, hid, nosso in mesa.casos():
            if nome == "edge-pelo-radio":
                continue  # o D3/D4 do rádio tem régua própria (test_hidraw_broker_validator)
            fisico = broker._pai_hid_e_dualsense_fisico(
                str(hid), _campos(hid), sys_class_bluetooth=nao_ha_radio
            )
            assert fisico is (not nosso), nome

    def test_o_serial_do_pad_leva_o_mac_inteiro(self) -> None:
        assert pad_usb.serial_do_pad(MAC_DO_PAD) == SERIAL_DO_PAD
        with pytest.raises(ValueError):
            pad_usb.serial_do_pad("02:fe")


class TestOsSeisLugaresPerguntamAoDono:
    def test_o_backend_nao_adota_o_gadget(
        self, mesa: Mesa, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from hefesto_dualsense4unix.core import backend_pydualsense as bp

        monkeypatch.setattr(bp, "RAIZ_CLASS_HIDRAW", str(mesa.classe))
        vistos = {n: bp._is_virtual_hidraw(f"/dev/hidraw{n}".encode()) for n in range(5)}
        assert vistos == {0: True, 1: True, 2: False, 3: False, 4: False}

    def test_o_evdev_nao_adota_o_gadget(self, mesa: Mesa, monkeypatch: pytest.MonkeyPatch) -> None:
        from hefesto_dualsense4unix.core import evdev_reader as er

        entradas = {
            "event20": (mesa.gadget_hid / "input" / "input90", MAC_DO_PAD, ""),
            "event21": (mesa.cabo_hid / "input" / "input91", MAC_DO_EDGE, ""),
            "event22": (mesa.usbip_hid / "input" / "input92", MAC_DO_EDGE, ""),
        }
        attrs = {str(link): {"uniq": uniq, "phys": phys} for link, uniq, phys in entradas.values()}
        realpath = os.path.realpath

        def _real(caminho: str) -> str:
            if caminho.startswith("/sys/class/input/"):
                return str(entradas[caminho.split("/")[4]][0])
            return realpath(caminho)

        monkeypatch.setattr(os.path, "realpath", _real)
        monkeypatch.setattr(er, "_read_input_attr", lambda d, a: attrs[d][a])
        assert er._is_virtual_evdev("/dev/input/event20") is True
        assert er._is_virtual_evdev("/dev/input/event21") is False
        assert er._is_virtual_evdev("/dev/input/event22") is False

    def test_o_usb_pai_nao_da_o_pai_do_gadget(self, mesa: Mesa) -> None:
        from hefesto_dualsense4unix.integrations import usb_pai

        achados = usb_pai.usb_pai_por_uniq([MAC_DO_PAD, MAC_DO_EDGE], raiz=str(mesa.classe))
        assert achados[MAC_DO_PAD] == ""
        assert achados[MAC_DO_EDGE].endswith("usb1/1-2")

    def test_o_quem_o_jogo_le_ve_o_gadget_como_pad(
        self, mesa: Mesa, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from hefesto_dualsense4unix.integrations import quem_o_jogo_le as qjl

        monkeypatch.setattr(qjl, "RAIZ_CLASS_HIDRAW", str(mesa.classe))
        nomes = [f"hidraw{n}" for n in range(5)]
        assert qjl.hidraws_de_vpad(nomes) == {"hidraw0", "hidraw1"}

    def test_a_sinal_da_barra_lista_o_edge_do_radio_e_nao_o_pad(self, mesa: Mesa) -> None:
        from hefesto_dualsense4unix.integrations import sinal_da_barra as sb

        raiz_uhid = mesa.sys / "devices/virtual/misc/uhid"
        (achada,) = sb.instancias_dualsense(str(raiz_uhid))
        assert (achada.instancia, achada.transporte) == ("0012", "bt")
