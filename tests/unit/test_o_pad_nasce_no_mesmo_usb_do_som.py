"""O pad virtual e o som dele nascem no mesmo USB.

A sprint é a O-PAD-VIRTUAL-E-O-SOM-DELE-NASCEM-NO-MESMO-USB-01 (07/10/2026).

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

import errno
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.broker import hidraw_broker as broker
from hefesto_dualsense4unix.integrations import pad_usb

# Faixas forjadas da casa: ``aa:bb:cc`` e ``02:fe:00``; nunca um endereço real.
MAC_DO_PAD = "02:fe:00:8a:00:01"
SERIAL_DO_PAD = "hefesto-pad-02fe008a0001"
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


# --- 2. O broker monta o gadget só HID, liga ao vhci e desmonta no EOF --------


_ATTRS_DO_GRUPO = {
    "gadget": ("idVendor", "idProduct", "bcdDevice", "bcdUSB", "UDC"),
    "0x409": ("manufacturer", "product", "serialnumber"),
    "c.1": ("MaxPower",),
    "hid.usb0": ("protocol", "subclass", "report_length", "report_desc", "no_out_endpoint"),
}


class KernelDeMentira:
    """O configfs, o vudc, o vhci e o /dev de mentira, estritos como os de verdade.

    O ``povoar`` publica os atributos de cada grupo, como o configfs faz ao
    nascer o grupo; o ``remover`` recusa diretório com grupo ou elo dentro,
    como o ``rmdir`` do configfs. ``sem`` tira do kernel um pedaço do contrato.
    """

    def __init__(self, raiz: Path, *, udcs: int = 4, sem: frozenset[str] = frozenset()) -> None:
        self.raiz = raiz
        self.sem = sem
        self.raizes = broker.RaizesDoPad(
            configfs=str(raiz / "configfs/usb_gadget"),
            plataforma=str(raiz / "platform"),
            classe_udc=str(raiz / "class/udc"),
            dev=str(raiz / "dev"),
        )
        if "libcomposite" not in sem:
            Path(self.raizes.configfs).mkdir(parents=True)
        Path(self.raizes.dev).mkdir(parents=True)
        Path(self.raizes.classe_udc).mkdir(parents=True)
        if "usbip_vudc" not in sem:
            for n in range(udcs):
                (Path(self.raizes.classe_udc) / f"usbip-vudc.{n}").mkdir()
                _escrever(Path(self.raizes.plataforma) / f"usbip-vudc.{n}/usbip_sockfd", "")
        if "vhci_hcd" not in sem:
            vhci = Path(self.raizes.plataforma) / "vhci_hcd.0"
            linhas = ["hub port sta spd dev      sockfd local_busid"]
            linhas += [f"hs  {p:04d} 004 000 00000000 000000 0-0" for p in range(4)]
            linhas += [f"ss  {p:04d} 004 000 00000000 000000 0-0" for p in range(4, 8)]
            _escrever(vhci / "status", "\n".join(linhas) + "\n")
            _escrever(vhci / "attach", "")
            _escrever(vhci / "detach", "")
        self.rdev: dict[str, int] = {}
        self.anexos: list[str] = []
        self.desligadas: list[str] = []
        self.proximo_menor = 0
        self.concedidos: list[tuple[str, int]] = []
        #: os grupos que o configfs cria sozinho e some com o pai.
        self.padrao: set[str] = set()

    def povoar(self, grupo: str) -> None:
        nome = os.path.basename(grupo)
        if os.path.dirname(grupo) == self.raizes.configfs:
            nome = "gadget"
            for sub in ("strings", "configs", "functions"):
                os.mkdir(os.path.join(grupo, sub))
                self.padrao.add(os.path.join(grupo, sub))
        if nome == "c.1":
            os.mkdir(os.path.join(grupo, "strings"))
            self.padrao.add(os.path.join(grupo, "strings"))
        for attr in _ATTRS_DO_GRUPO.get(nome, ()):
            if nome == "hid.usb0" and attr in self.sem:
                continue
            _escrever(Path(grupo) / attr, "0\n" if attr == "no_out_endpoint" else "")
        if nome == "hid.usb0":
            menor = self.proximo_menor
            self.proximo_menor += 1
            _escrever(Path(grupo) / "dev", f"240:{menor}\n")
            no = Path(self.raizes.dev) / f"hidg{menor}"
            no.write_text("", encoding="utf-8")
            self.rdev[str(no)] = os.makedev(240, menor)

    def remover(self, caminho: str) -> None:
        if caminho in self.padrao:
            raise OSError(1, "grupo padrão do configfs não se remove sozinho", caminho)
        padroes = []
        for filho in os.scandir(caminho):
            vazio_padrao = filho.path in self.padrao and not any(os.scandir(filho.path))
            if filho.is_symlink() or (filho.is_dir() and not vazio_padrao):
                raise OSError(39, "o configfs não remove grupo com grupo dentro", caminho)
            if filho.is_dir():
                padroes.append(filho.path)
        for filho in os.scandir(caminho):
            if not filho.is_dir():
                os.unlink(filho.path)
        for sub in padroes:
            os.rmdir(sub)
            self.padrao.discard(sub)
        os.rmdir(caminho)

    def ops(self) -> broker.PadUsbOps:
        return broker.PadUsbOps(
            self.raizes,
            remover=self.remover,
            povoar=self.povoar,
            abrir=lambda p: os.open(p, os.O_PATH | os.O_CLOEXEC | os.O_NOFOLLOW),
            rdev_de=lambda fd: self.rdev[os.readlink(f"/proc/self/fd/{fd}")],
            conceder=lambda fd, uid: self.concedidos.append(
                (os.readlink(f"/proc/self/fd/{fd}"), uid)
            ),
        )

    def estado(self, **kw: object) -> broker.BrokerState:
        return broker.BrokerState(allowed_uid=1000, pad_ops=self.ops(), log=lambda *_a, **_k: None)

    def gadget(self, nome: str) -> Path:
        return Path(self.raizes.configfs) / nome

    def lido(self, caminho: Path) -> str:
        return caminho.read_text(encoding="utf-8").strip()


def _descritor() -> bytes:
    from hefesto_dualsense4unix.integrations.uhid_blueprint import CANONICAL_DESCRIPTOR_USB

    return CANONICAL_DESCRIPTOR_USB


def _pedido(serial: str = SERIAL_DO_PAD, descritor: bytes | None = None) -> bytes:
    import json

    corpo = {
        "cmd": "pad_usb_montar",
        "serial": serial,
        "descritor": (_descritor() if descritor is None else descritor).hex(),
    }
    return json.dumps(corpo).encode()


def _serial(n: int) -> str:
    return f"hefesto-pad-02fe008a00{n:02x}"


@pytest.fixture
def kernel(tmp_path: Path) -> KernelDeMentira:
    return KernelDeMentira(tmp_path)


class TestOBrokerMontaOGadgetSoHid:
    def test_o_gadget_montado_tem_so_a_funcao_hid_sem_out(self, kernel: KernelDeMentira) -> None:
        """D-0710-O-PAD-E-UM-GADGET-SO-HID: só a função HID, sem OUT, no lugar do uhid."""
        estado = kernel.estado()
        resposta, fd = estado.handle_line(7, 1000, _pedido())
        assert resposta["ok"] is True, resposta
        assert fd is not None
        os.close(fd)
        g = kernel.gadget(str(resposta["gadget"]))
        assert sorted(os.listdir(g / "functions")) == ["hid.usb0"]
        elos = [e for e in os.listdir(g / "configs/c.1") if (g / "configs/c.1" / e).is_symlink()]
        assert elos == ["hid.usb0"]
        hid = g / "functions/hid.usb0"
        assert kernel.lido(hid / "no_out_endpoint") == "1"
        assert kernel.lido(hid / "report_length") == "64"
        assert (hid / "report_desc").read_bytes() == _descritor()
        assert (kernel.lido(g / "idVendor"), kernel.lido(g / "idProduct")) == ("0x054c", "0x0df2")
        assert kernel.lido(g / "strings/0x409/serialnumber") == SERIAL_DO_PAD
        assert kernel.lido(g / "UDC") == "usbip-vudc.0"
        porta, _sockfd, devid, velocidade = kernel.lido(
            Path(kernel.raizes.plataforma) / "vhci_hcd.0/attach"
        ).split()
        assert (porta, devid, velocidade) == ("0", "0", "3")
        assert resposta["porta"] == 0
        assert kernel.concedidos == [(str(Path(kernel.raizes.dev) / "hidg0"), 1000)]

    def test_a_porta_livre_pula_a_linha_torta_e_a_ocupada(self, kernel: KernelDeMentira) -> None:
        status = Path(kernel.raizes.plataforma) / "vhci_hcd.0/status"
        _escrever(status, "\n".join([
            "hub port sta spd dev      sockfd local_busid",
            "hs  000x 004 000 00000000 000000 0-0",
            "hs  0000 006 003 00010002 000003 1-1",
            "hs  0001 004 000 00000000 000000 0-0",
        ]) + "\n")
        assert kernel.ops().porta_livre() == 1

    @pytest.mark.parametrize(("hid_id", "bus"), [
        ("0003:0000054C:00000DF2", 3), ("0005:0000054C:00000CE6", 5),
        ("", None), ("zz03:0000054C:00000DF2", None), ("-3:0", None),
    ])
    def test_o_barramento_do_hid_id_e_hex_ou_nao_sei(self, hid_id: str, bus: int | None) -> None:
        assert pad_usb.bus_do_hid_id(hid_id) == bus

    def test_o_no_cedido_e_o_do_gadget_e_nao_o_hidg_de_outro(
        self, kernel: KernelDeMentira
    ) -> None:
        alheio = Path(kernel.raizes.dev) / "hidg0"
        alheio.write_text("", encoding="utf-8")
        kernel.rdev[str(alheio)] = os.makedev(240, 9)
        kernel.proximo_menor = 1
        _, fd = kernel.estado().handle_line(7, 1000, _pedido())
        assert fd is not None
        os.close(fd)
        assert kernel.concedidos == [(str(Path(kernel.raizes.dev) / "hidg1"), 1000)]

    def test_o_eof_da_conexao_desmonta_o_gadget(self, kernel: KernelDeMentira) -> None:
        estado = kernel.estado()
        resposta, fd = estado.handle_line(7, 1000, _pedido())
        assert fd is not None
        os.close(fd)
        estado.on_conn_closed(7)
        assert os.listdir(kernel.raizes.configfs) == []
        assert kernel.lido(Path(kernel.raizes.plataforma) / "vhci_hcd.0/detach") == str(
            resposta["porta"]
        )

    def test_o_desmontar_pedido_so_vale_para_quem_montou(self, kernel: KernelDeMentira) -> None:
        import json

        estado = kernel.estado()
        resposta, fd = estado.handle_line(7, 1000, _pedido())
        assert fd is not None
        os.close(fd)
        pedido = json.dumps({"cmd": "pad_usb_desmontar", "gadget": resposta["gadget"]}).encode()
        alheio, _ = estado.handle_line(8, 1000, pedido)
        assert alheio["error"] == "reject_not_held"
        dono, _ = estado.handle_line(7, 1000, pedido)
        assert dono["ok"] is True
        assert os.listdir(kernel.raizes.configfs) == []

    def test_com_mais_de_quatro_controles_nascem_quatro_pads(
        self, tmp_path: Path
    ) -> None:
        kernel = KernelDeMentira(tmp_path, udcs=6)
        estado = kernel.estado()
        montados = []
        for n in range(5):
            resposta, fd = estado.handle_line(7, 1000, _pedido(_serial(n)))
            if fd is not None:
                os.close(fd)
                montados.append(resposta["gadget"])
            else:
                assert resposta["error"] == "reject_quinto_pad"
        assert len(montados) == 4
        assert len(os.listdir(kernel.raizes.configfs)) == 4

    def test_com_o_vudc_preso_o_pad_fica_sem_vaga_e_nao_sem_contrato(
        self, tmp_path: Path
    ) -> None:
        # O `usbip-vudc` carregado antes do broker com uma instância só: o
        # `modprobe num=4` dele não troca o que já está no kernel. O segundo
        # pad fica sem vaga, e isso não pode virar «falta o usbip_vudc», que o
        # daemon guarda e com que manda todo pad seguinte ao uhid.
        kernel = KernelDeMentira(tmp_path, udcs=1)
        estado = kernel.estado()
        _, fd = estado.handle_line(7, 1000, _pedido(_serial(0)))
        assert fd is not None
        os.close(fd)
        resposta, fd2 = estado.handle_line(7, 1000, _pedido(_serial(1)))
        assert fd2 is None
        assert resposta["error"] == "pad_usb_sem_udc_livre", resposta
        assert "contrato" not in resposta
        assert len(os.listdir(kernel.raizes.configfs)) == 1

    def test_o_mesmo_serial_nao_monta_dois_pads(self, kernel: KernelDeMentira) -> None:
        estado = kernel.estado()
        _, fd = estado.handle_line(7, 1000, _pedido())
        assert fd is not None
        os.close(fd)
        resposta, fd2 = estado.handle_line(7, 1000, _pedido())
        assert fd2 is None
        assert resposta["error"] == "reject_serial_repetido"

    def test_o_broker_nao_monta_descritor_alheio_nem_serial_fora_do_formato(
        self, kernel: KernelDeMentira
    ) -> None:
        estado = kernel.estado()
        teclado = bytes.fromhex("05010906a101050719e029e715002501750195088102c0")
        resposta, fd = estado.handle_line(7, 1000, _pedido(descritor=teclado))
        assert (resposta["error"], fd) == ("reject_bad_descriptor", None)
        resposta, fd = estado.handle_line(7, 1000, _pedido(serial="hefesto-pad-zz"))
        assert (resposta["error"], fd) == ("reject_bad_serial", None)
        assert os.listdir(kernel.raizes.configfs) == []

    def test_o_hash_do_broker_e_o_do_descritor_do_blueprint(self) -> None:
        import hashlib

        assert hashlib.sha256(_descritor()).hexdigest() in broker.PAD_USB_DESCRITORES_SHA256

    @pytest.mark.parametrize(
        "sem", ["libcomposite", "usbip_vudc", "vhci_hcd", "no_out_endpoint"]
    )
    def test_sem_o_contrato_o_broker_diz_qual_e_nao_deixa_resto(
        self, tmp_path: Path, sem: str
    ) -> None:
        kernel = KernelDeMentira(tmp_path, sem=frozenset({sem}))
        estado = kernel.estado()
        resposta, fd = estado.handle_line(7, 1000, _pedido())
        assert fd is None
        assert resposta["error"] == "pad_usb_sem_contrato", resposta
        esperado = "usb_f_hid" if sem == "no_out_endpoint" else sem
        assert resposta["contrato"] == esperado
        if sem != "libcomposite":
            assert os.listdir(kernel.raizes.configfs) == []

    def test_o_broker_sem_raizes_da_suite_nao_ve_o_configfs_da_maquina(self) -> None:
        # Todo `BrokerState()` das outras réguas nasce sem `pad_ops`: o EOF e o
        # `restore_all` delas listariam os gadgets do usuário e tentariam
        # desmontá-los. O `conftest` desvia as raízes para uma pasta vazia.
        raizes = broker.BrokerState(allowed_uid=1000, log=lambda *_a, **_k: None)._pad_ops.raizes
        for raiz in (raizes.configfs, raizes.plataforma, raizes.classe_udc):
            assert not raiz.startswith("/sys"), raizes

    def test_o_cinto_do_broker_desmonta_o_pad_orfao(self, kernel: KernelDeMentira) -> None:
        _, fd = kernel.estado().handle_line(7, 1000, _pedido())
        assert fd is not None
        os.close(fd)
        assert kernel.ops().desmontar_todos() == ["hefesto-pad-0"]
        assert os.listdir(kernel.raizes.configfs) == []


class TestOClienteRecebeOPadPeloSocket:
    """Ponta a ponta: o cliente do daemon pede, o broker monta e cede, o EOF desmonta."""

    def test_o_cliente_reabre_o_no_cedido_e_o_eof_desmonta(
        self, kernel: KernelDeMentira
    ) -> None:
        import socket
        import threading

        from hefesto_dualsense4unix.integrations.hidraw_broker_client import HidrawBrokerClient

        estado = kernel.estado()
        estado.allowed_uid = os.getuid()
        servidor = broker.Broker(estado, None, log=lambda *_a, **_k: None)
        a, b = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        assert servidor.register_client(a) is not None
        b.settimeout(5.0)
        cliente = HidrawBrokerClient("/nao/existe")
        cliente._sock = b
        passo = threading.Thread(target=servidor.step, kwargs={"timeout": 5.0})
        passo.start()
        fd, resposta = cliente.montar_pad_usb(SERIAL_DO_PAD, _descritor())
        passo.join(5.0)
        assert resposta is not None and resposta["ok"] is True, resposta
        assert fd is not None
        try:
            assert os.fstat(fd).st_ino == os.stat(Path(kernel.raizes.dev) / "hidg0").st_ino
            assert fcntl_acesso(fd) == os.O_RDWR
        finally:
            os.close(fd)
        assert os.listdir(kernel.raizes.configfs) == ["hefesto-pad-0"]
        b.close()
        servidor.step(timeout=2.0)
        assert os.listdir(kernel.raizes.configfs) == []


def fcntl_acesso(fd: int) -> int:
    import fcntl

    return fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_ACCMODE


# --- 3. O vpad nasce no gadget, fala pelo /dev/hidgN e volta ao uhid ----------


IDENTIDADE = "aa:bb:cc:00:00:11"
INTERFACE_DO_GADGET = "/devices/platform/vhci_hcd.0/usb3/3-1/3-1:1.0"


class ClienteDeMentira:
    def __init__(self) -> None:
        self.desmontados: list[str] = []
        self.fechado = False

    def desmontar_pad_usb(self, gadget: str) -> bool:
        self.desmontados.append(gadget)
        return True

    def close(self) -> None:
        self.fechado = True


class BancadaDoGadget:
    """O lado do jogo de um /dev/hidgN: um par SEQPACKET guarda um report por escrita."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        import socket

        from hefesto_dualsense4unix.integrations import uhid_gamepad

        self.ug = uhid_gamepad
        self.pedidos: list[tuple[str, bytes, str]] = []
        self.clientes: list[ClienteDeMentira] = []
        self.guardadas: dict[int, bytes] = {}
        self.enumerado: tuple[str, str] | None = None
        self.jogo_aberto = False
        #: o aparelho físico na máquina; False = ele CAIU (o caso do estacionar).
        self.aparelho_presente = False
        self.falta: list[str] = []
        self.jogo: socket.socket | None = None
        self.ioctl_erro: int | None = None

        def pedir(serial: str, descritor: bytes, identidade: str) -> Any:
            self.pedidos.append((serial, descritor, identidade))
            nosso, jogo = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
            jogo.settimeout(2.0)
            self.jogo = jogo
            os.set_blocking(nosso.fileno(), False)
            cliente = ClienteDeMentira()
            self.clientes.append(cliente)
            return uhid_gamepad._GadgetDoPad(
                cliente=cliente, fd=nosso.detach(), gadget=f"hefesto-pad-{len(self.pedidos) - 1}",
                serial=serial, identidade=identidade,
            )

        def escrever(fd: int, report_id: int, dados: bytes, **_k: Any) -> None:
            if self.ioctl_erro is not None:
                raise OSError(self.ioctl_erro, "ioctl")
            self.guardadas[report_id] = bytes(dados)

        monkeypatch.setattr(uhid_gamepad, "PEDIR_O_PAD_USB", pedir)
        monkeypatch.setattr(uhid_gamepad, "HIDRAW_DO_GADGET", lambda _s: self.enumerado)
        monkeypatch.setattr(uhid_gamepad, "JOGO_ABERTO", lambda: self.jogo_aberto)
        monkeypatch.setattr(
            uhid_gamepad, "APARELHO_PRESENTE", lambda _i: self.aparelho_presente
        )
        monkeypatch.setattr(uhid_gamepad, "CONTRATO_QUE_FALTA", lambda: list(self.falta))
        monkeypatch.setattr(pad_usb, "escrever_get_report", escrever)
        monkeypatch.setattr(pad_usb, "_INTERFACE_DO_APARELHO", {})
        monkeypatch.setattr(pad_usb, "_CONTRATO_QUE_FALTOU", [])
        monkeypatch.setattr(
            uhid_gamepad, "_GADGETS_ESTACIONADOS", uhid_gamepad._GadgetsEstacionados()
        )
        uhid_falso = tmp_path / "uhid-de-mentira"
        uhid_falso.write_bytes(b"")
        monkeypatch.setattr(uhid_gamepad, "UHID_NODE", str(uhid_falso))

    def pad(self, **kw: Any) -> Any:
        from hefesto_dualsense4unix.integrations.uhid_blueprint import canonical_blueprint

        kw.setdefault("identity", IDENTIDADE)
        return self.ug.UhidDualSense(player=1, blueprint=canonical_blueprint(), **kw)

    def esperar(self, condicao: Callable[[], bool], segundos: float = 3.0) -> bool:
        import time

        fim = time.monotonic() + segundos
        while time.monotonic() < fim:
            if condicao():
                return True
            time.sleep(0.02)
        return condicao()


@pytest.fixture
def bancada(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> BancadaDoGadget:
    return BancadaDoGadget(monkeypatch, tmp_path)


class _EspiaoDoDiario:
    """O logger de verdade, que também anota ``(nível, evento)`` de cada linha."""

    def __init__(self, real: Any) -> None:
        self.real = real
        self.eventos: list[tuple[str, str]] = []

    def __getattr__(self, nivel: str) -> Callable[..., Any]:
        alvo = getattr(self.real, nivel)

        def anotar(evento: str, *args: Any, **kw: Any) -> Any:
            self.eventos.append((nivel, evento))
            return alvo(evento, *args, **kw)

        return anotar


class TestOVpadNasceNoGadget:
    def test_o_vpad_nasce_no_gadget_com_as_features_do_probe(
        self, bancada: BancadaDoGadget
    ) -> None:
        pad = bancada.pad()
        try:
            assert pad.start() is True
            assert pad._gadget is not None
            serial, descritor, identidade = bancada.pedidos[0]
            assert serial == pad_usb.serial_do_pad(pad.mac)
            assert descritor == _descritor()
            assert identidade == IDENTIDADE
            assert sorted(bancada.guardadas) == [0x05, 0x09, 0x20]
            mac_le = bytes(int(x, 16) for x in reversed(pad.mac.split(":")))
            assert bancada.guardadas[0x09][1:7] == mac_le
            assert pad.wait_for_bind(0.5) is True
            assert pad.is_bound is False
            bancada.enumerado = ("hidraw9", INTERFACE_DO_GADGET)
            assert bancada.esperar(lambda: pad.is_bound)
            assert pad_usb.interface_do_aparelho(IDENTIDADE) == INTERFACE_DO_GADGET
        finally:
            pad.stop()

    def test_a_entrada_sai_crua_e_o_output_do_jogo_chega_ao_controle(
        self, bancada: BancadaDoGadget, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from hefesto_dualsense4unix.integrations import uhid_gamepad

        espiao = _EspiaoDoDiario(uhid_gamepad.logger)
        monkeypatch.setattr(uhid_gamepad, "logger", espiao)
        pedidos: list[tuple[int, int]] = []
        pad = bancada.pad(rumble_sink=lambda w, s: pedidos.append((w, s)))
        bancada.enumerado = ("hidraw9", INTERFACE_DO_GADGET)
        try:
            assert pad.start()
            assert bancada.esperar(lambda: pad.is_bound)
            assert bancada.jogo is not None
            pad.forward_buttons(frozenset({"cross"}))
            report = bancada.jogo.recv(512)
            assert len(report) == 64 and report[0] == 0x01
            saida = bytearray(48)
            saida[0] = 0x02
            saida[1] = 0x03  # valid_flag0: as duas vibrações
            saida[3], saida[4] = 0x40, 0x80
            import time

            time.sleep(0.6)  # a graça do bind (`_GAME_REPLICA_GRACE_S`)
            bancada.jogo.send(bytes([0x08]) + bytes(46))
            bancada.jogo.send(bytes(saida))
            assert bancada.esperar(lambda: pad.output_count == 1)
            for _ in range(20):
                pad.pump_ff()
                if pedidos:
                    break
                time.sleep(0.02)
            assert pedidos and pedidos[-1] != (0, 0)
            assert pad.ff_report_estranho_count == 0
            # A fila do f_hid vazia (EAGAIN) é o fim da drenagem, não falha.
            assert ("warning", "pad_usb_leitura_falhou") not in espiao.eventos
        finally:
            pad.stop()

    def test_sem_o_contrato_o_vpad_nasce_uhid_e_nao_pede_ao_broker(
        self, bancada: BancadaDoGadget
    ) -> None:
        bancada.falta = ["usbip_vudc"]
        pad = bancada.pad()
        try:
            assert pad.start() is True
            assert pad._gadget is None
            assert bancada.pedidos == []
        finally:
            pad.stop()

    def test_sem_o_ioctl_o_contrato_vai_ao_doctor_e_o_vpad_nasce_uhid(
        self, bancada: BancadaDoGadget
    ) -> None:
        bancada.ioctl_erro = errno.ENOTTY
        pad = bancada.pad()
        try:
            assert pad.start() is True
            assert pad._gadget is None
            assert bancada.clientes[0].desmontados == ["hefesto-pad-0"]
            assert pad_usb.CONTRATO_DO_IOCTL in pad_usb.contrato_que_faltou_ao_montar()
        finally:
            pad.stop()

    def test_o_gadget_que_nao_enumera_volta_ao_uhid(
        self, bancada: BancadaDoGadget
    ) -> None:
        relogio = [100.0]
        pad = bancada.pad(time_fn=lambda: relogio[0])
        try:
            assert pad.start()
            relogio[0] += 16.0
            assert bancada.esperar(lambda: pad._gadget_falhou)
            pad.pump_ff()
            assert pad._gadget is None and pad.is_active
            assert bancada.clientes[0].desmontados == ["hefesto-pad-0"]
            assert bancada.ug.CONTRATO_DA_ENUMERACAO in pad_usb.contrato_que_faltou_ao_montar()
        finally:
            pad.stop()

    def test_sem_jogo_o_gadget_desce_com_o_vpad(self, bancada: BancadaDoGadget) -> None:
        bancada.enumerado = ("hidraw9", INTERFACE_DO_GADGET)
        pad = bancada.pad()
        assert pad.start()
        assert bancada.esperar(lambda: pad.is_bound)
        pad.stop()
        assert bancada.clientes[0].desmontados == ["hefesto-pad-0"]
        assert pad_usb.interface_do_aparelho(IDENTIDADE) is None

    def test_com_o_jogo_aberto_o_gadget_espera_e_o_aparelho_o_retoma(
        self, bancada: BancadaDoGadget
    ) -> None:
        bancada.enumerado = ("hidraw9", INTERFACE_DO_GADGET)
        bancada.jogo_aberto = True
        pad = bancada.pad()
        assert pad.start()
        assert bancada.esperar(lambda: pad.is_bound)
        assert bancada.jogo is not None
        pad.forward_buttons(frozenset({"cross"}))
        bancada.jogo.recv(512)
        pad.stop()
        neutro = bancada.jogo.recv(512)
        assert neutro[0] == 0x01 and neutro[1:5] == bytes([0x80] * 4)
        assert neutro[8] == 0x08  # o d-pad no neutro, e nenhum botão
        assert bancada.clientes[0].desmontados == []
        assert pad_usb.interface_do_aparelho(IDENTIDADE) == INTERFACE_DO_GADGET
        de_volta = bancada.pad()
        try:
            assert de_volta.start()
            assert len(bancada.pedidos) == 1
            assert de_volta.is_bound
        finally:
            de_volta.stop()
        assert bancada.ug._GADGETS_ESTACIONADOS.quantos() == 1
        bancada.jogo_aberto = False
        assert bancada.ug._GADGETS_ESTACIONADOS.varrer() == 1
        assert bancada.clientes[0].desmontados == ["hefesto-pad-0"]

    def test_o_estacionado_desce_quando_o_jogo_fecha(self, bancada: BancadaDoGadget) -> None:
        bancada.enumerado = ("hidraw9", INTERFACE_DO_GADGET)
        bancada.jogo_aberto = True
        pad = bancada.pad()
        assert pad.start()
        assert bancada.esperar(lambda: pad.is_bound)
        pad.stop()
        estacionados = bancada.ug._GADGETS_ESTACIONADOS
        assert estacionados.varrer() == 0
        bancada.jogo_aberto = False
        assert estacionados.varrer() == 1
        assert bancada.clientes[0].desmontados == ["hefesto-pad-0"]


class TestOPadEmUsbNaoQuebraOResto:
    """O que o conferente final achou: o gadget convivendo com o co-op e a máscara."""

    def test_em_enumeracao_o_pad_esta_vivo_para_o_coop(self, bancada: BancadaDoGadget) -> None:
        """~9 s sem o ``_started``: sem isto o co-op renascia o jogador a cada tique."""
        from unittest.mock import MagicMock

        from hefesto_dualsense4unix.daemon.subsystems.gamepad import vpad_vivo

        relogio = [100.0]
        pad = bancada.pad(time_fn=lambda: relogio[0])
        try:
            assert pad.start()
            assert pad._started is False
            assert vpad_vivo(pad) is True
            relogio[0] += 16.0
            assert bancada.esperar(lambda: pad._gadget_falhou)
            assert vpad_vivo(pad) is False
        finally:
            pad.stop()
        # O dublê de sempre (um MagicMock morto) continua morto.
        assert vpad_vivo(MagicMock(_started=False)) is False

    def test_o_estacionado_do_aparelho_que_ficou_e_fantasma_e_desce_com_o_jogo(
        self, bancada: BancadaDoGadget
    ) -> None:
        """A troca de máscara com o jogo aberto não deixa um DualSense fantasma.

        O pad que renasce na hora retoma o gadget (o GUID do jogo fica); o
        aparelho que está AQUI e não o retoma no prazo trocou de máscara ou
        saiu da emulação, e o gadget desce. O que CAIU continua esperando.
        """
        import time

        bancada.enumerado = ("hidraw9", INTERFACE_DO_GADGET)
        bancada.jogo_aberto = True
        bancada.aparelho_presente = True
        pad = bancada.pad()
        assert pad.start()
        assert bancada.esperar(lambda: pad.is_bound)
        pad.stop()
        estacionados = bancada.ug._GADGETS_ESTACIONADOS
        prazo = bancada.ug._GADGET_RETOMA_S
        assert estacionados.quantos() == 1
        assert estacionados.varrer(agora=time.monotonic() + 1.0) == 0
        bancada.aparelho_presente = False
        assert estacionados.varrer(agora=time.monotonic() + prazo + 1.0) == 0
        assert bancada.clientes[0].desmontados == []
        bancada.aparelho_presente = True
        assert estacionados.varrer(agora=time.monotonic() + prazo + 1.0) == 1
        assert estacionados.quantos() == 0
        assert bancada.clientes[0].desmontados == ["hefesto-pad-0"]

    def test_o_gadget_que_cai_com_o_jogo_aberto_volta_ao_uhid(
        self, bancada: BancadaDoGadget
    ) -> None:
        """O broker que cai tira o gadget de baixo do pad: ele renasce, não emudece."""
        bancada.enumerado = ("hidraw9", INTERFACE_DO_GADGET)
        bancada.jogo_aberto = True
        pad = bancada.pad()
        try:
            assert pad.start()
            assert bancada.esperar(lambda: pad.is_bound)
            assert bancada.jogo is not None
            bancada.jogo.close()
            # A escrita falha com o hidraw ainda de pé: não caiu, só falhou.
            pad.forward_buttons(frozenset({"cross"}))
            assert pad._gadget_caiu is False
            bancada.enumerado = None
            pad.forward_buttons(frozenset({"circle"}))
            assert bancada.esperar(lambda: pad._gadget_caiu, segundos=6.0)
            pad.pump_ff()
            assert pad._gadget is None and pad.is_active
            assert bancada.clientes[0].desmontados == ["hefesto-pad-0"]
            assert bancada.ug._GADGETS_ESTACIONADOS.quantos() == 0
            assert bancada.ug.CONTRATO_DA_ENUMERACAO not in (
                pad_usb.contrato_que_faltou_ao_montar()
            )
        finally:
            pad.stop()


def _sysfs_do_aparelho(raiz: Path) -> tuple[Path, Path]:
    """Uma classe hidraw e uma classe input de mentira, vazias."""
    hidraw = raiz / "class" / "hidraw"
    entrada = raiz / "class" / "input"
    hidraw.mkdir(parents=True)
    entrada.mkdir(parents=True)
    return hidraw, entrada


def _hidraw(raiz: Path, classe: Path, nome: str, devpath: str, uniq: str) -> None:
    hid = raiz / devpath
    hid.mkdir(parents=True)
    _escrever(hid / "uevent", _uevent("0005:0000054C:00000CE6", uniq=uniq))
    (classe / nome).mkdir()
    (classe / nome / "device").symlink_to(hid)


class TestOAparelhoPresente:
    def _pergunta(self, identidade: str, hidraw: Path, entrada: Path) -> bool:
        return pad_usb.aparelho_presente(
            identidade, raiz_class_hidraw=str(hidraw), raiz_class_input=str(entrada)
        )

    def test_o_aparelho_pelo_radio_esta_aqui(self, tmp_path: Path) -> None:
        hidraw, entrada = _sysfs_do_aparelho(tmp_path)
        _hidraw(tmp_path, hidraw, "hidraw3", "devices/bt/0005:054C:0CE6.0003", MAC_DO_EDGE)
        assert self._pergunta(MAC_DO_EDGE, hidraw, entrada) is True
        assert self._pergunta(MAC_DO_EDGE.replace(":", "").upper(), hidraw, entrada) is True

    def test_o_aparelho_so_pelo_uniq_do_evdev_esta_aqui(self, tmp_path: Path) -> None:
        hidraw, entrada = _sysfs_do_aparelho(tmp_path)
        _escrever(entrada / "input7" / "uniq", MAC_DO_EDGE + "\n")
        assert self._pergunta(MAC_DO_EDGE, hidraw, entrada) is True

    def test_o_aparelho_que_saiu_nao_esta(self, tmp_path: Path) -> None:
        hidraw, entrada = _sysfs_do_aparelho(tmp_path)
        _hidraw(tmp_path, hidraw, "hidraw3", "devices/bt/0005:054C:0CE6.0003",
                "aa:bb:cc:00:00:22")
        _escrever(entrada / "input7" / "uniq", "aa:bb:cc:00:00:22\n")
        assert self._pergunta(MAC_DO_EDGE, hidraw, entrada) is False

    def test_o_pad_nosso_com_o_mesmo_uniq_nao_e_o_aparelho(self, tmp_path: Path) -> None:
        hidraw, entrada = _sysfs_do_aparelho(tmp_path)
        _hidraw(tmp_path, hidraw, "hidraw4", "devices/virtual/misc/uhid/0005:054C:0CE6.0004",
                MAC_DO_EDGE)
        _escrever(tmp_path / "devices/virtual/misc/uhid/0005:054C:0CE6.0004/uevent",
                  _uevent("0005:0000054C:00000CE6", phys="hefesto-vpad-1", uniq=MAC_DO_EDGE))
        assert self._pergunta(MAC_DO_EDGE, hidraw, entrada) is False

    def test_na_duvida_o_aparelho_esta_aqui(self, tmp_path: Path) -> None:
        hidraw, entrada = _sysfs_do_aparelho(tmp_path)
        assert self._pergunta("path:/dev/input/event7", hidraw, entrada) is True
        assert self._pergunta(MAC_DO_EDGE, tmp_path / "nao-existe", entrada) is True


class TestOGetReportEOHidrawDoGadget:
    def test_a_struct_do_get_report_e_a_do_kernel(self) -> None:
        pacote = pad_usb.pacote_do_get_report(0x09, b"\x09" + bytes(19))
        assert len(pacote) == 72  # sizeof(struct usb_hidg_report)
        assert pacote[0] == 0x09 and pacote[1] == 0  # 0 = vale para todo pedido futuro
        assert int.from_bytes(pacote[2:4], "little") == 20
        with pytest.raises(ValueError):
            pad_usb.pacote_do_get_report(0x20, bytes(65))
        chamadas: list[tuple[int, int, bytes]] = []
        pad_usb.escrever_get_report(7, 0x05, b"\x05", ioctl=lambda *a: chamadas.append(a))
        assert chamadas[0][:2] == (7, pad_usb.GADGET_HID_WRITE_GET_REPORT)

    def test_o_get_report_pendente_se_responde_com_a_feature_guardada(
        self, bancada: BancadaDoGadget, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import select

        pad = bancada.pad()
        try:
            assert pad.start()
            monkeypatch.setattr(pad_usb, "ler_o_id_do_get_report", lambda _fd: 0x20)
            bancada.guardadas.clear()
            bancada.ug._drenar_o_gadget(pad, pad._fd, select.POLLPRI)
            assert bancada.guardadas == {0x20: pad._features[0x20]}
        finally:
            pad.stop()

    def test_o_hidraw_do_gadget_e_o_do_serial_dele_sob_o_vhci(self, tmp_path: Path) -> None:
        sys_ = tmp_path / "sys"
        classe = sys_ / "class" / "hidraw"
        classe.mkdir(parents=True)
        series = {}

        def aparelho(nome: str, usb_device: Path, serial: str) -> None:
            hid = usb_device / f"{usb_device.name}:1.0" / "0003:054C:0DF2.0001"
            hid.mkdir(parents=True)
            (classe / nome).mkdir()
            (classe / nome / "device").symlink_to(hid)
            series[str(usb_device / "serial")] = serial

        vhci = sys_ / "devices" / "platform" / "vhci_hcd.0" / "usb3"
        aparelho("hidraw3", vhci / "3-1", "hefesto-pad-02fe00800001")
        aparelho("hidraw4", vhci / "3-2", "hefesto-pad-02fe00800002")
        fisico = sys_ / "devices" / "pci0000:00" / "usb1"
        aparelho("hidraw1", fisico / "1-4", "hefesto-pad-02fe00800002")

        def ler(caminho: str) -> str:
            return series.get(caminho, "")

        achado = pad_usb.hidraw_do_gadget(
            "hefesto-pad-02fe00800002", raiz_class_hidraw=str(classe), ler=ler
        )
        assert achado == ("hidraw4", "/devices/platform/vhci_hcd.0/usb3/3-2/3-2:1.0")
        assert pad_usb.hidraw_do_gadget(
            "hefesto-pad-02fe00800009", raiz_class_hidraw=str(classe), ler=ler
        ) is None
        assert pad_usb.hidraw_do_gadget("teclado", raiz_class_hidraw=str(classe), ler=ler) is None


# --- 4. O som se ancora no gadget do próprio aparelho -------------------------


def _usb_da_mesa(
    sysfs: Path, pai: str, nome: str, *, vid: str, pid: str, dev: str, serial: str = ""
) -> Path:
    raiz = sysfs / pai / nome
    (raiz / f"{nome}:1.0").mkdir(parents=True)
    (raiz / f"{nome}:1.0" / "uevent").write_text("DEVTYPE=usb_interface\n")
    for attr, valor in {
        "busnum": nome.split("-")[0], "devnum": "2", "idVendor": vid,
        "idProduct": pid, "dev": dev, "serial": serial, "product": "x",
    }.items():
        (raiz / attr).write_text(valor + "\n")
    ligacoes = sysfs / "bus" / "usb" / "devices"
    ligacoes.mkdir(parents=True, exist_ok=True)
    (ligacoes / nome).symlink_to(raiz)
    return raiz


@pytest.fixture
def mesa_do_som(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    sysfs = tmp_path / "sys"
    _usb_da_mesa(sysfs, "devices/platform/vhci_hcd.0/usb3", "3-1", vid="054c", pid="0df2",
                dev="189:257", serial=pad_usb.serial_do_pad("02:fe:00:80:00:01"))
    _usb_da_mesa(sysfs, "devices/pci0000:00/0000:00:14.0/usb1", "1-2", vid="046d",
                pid="c52b", dev="189:2")
    _usb_da_mesa(sysfs, "devices/pci0000:00/0000:00:14.0/usb1", "1-3", vid="1a2c",
                pid="2124", dev="189:3")
    monkeypatch.setattr(pad_usb, "_INTERFACE_DO_APARELHO", {})
    return sysfs


class TestOSomSeAncoraNoGadget:
    def test_o_gadget_nunca_e_ancora_emprestada(self, mesa_do_som: Path) -> None:
        """D-0710-O-SOM-DO-PAD-ANCORA-NO-GADGET: o gadget é âncora só do próprio aparelho."""
        from hefesto_dualsense4unix.integrations import endpoint_de_haptica as eh

        achadas = [a.syspath for a in eh.ancoras(mesa_do_som)]
        assert achadas == [
            "/devices/pci0000:00/0000:00:14.0/usb1/1-2",
            "/devices/pci0000:00/0000:00:14.0/usb1/1-3",
        ]

    def test_o_aparelho_com_gadget_ancora_nele_e_o_sem_gadget_empresta(
        self, mesa_do_som: Path
    ) -> None:
        from hefesto_dualsense4unix.integrations import endpoint_de_haptica as eh
        from hefesto_dualsense4unix.integrations.dualsense_bt_audio import marca_do_aparelho

        com, sem = "aa:bb:cc:00:00:01", "aa:bb:cc:00:00:02"
        interface = "/devices/platform/vhci_hcd.0/usb3/3-1/3-1:1.0"
        pad_usb.registrar_gadget(com, interface)
        marca_com, marca_sem = marca_do_aparelho(com), marca_do_aparelho(sem)
        emprestadas = eh.ancoras(mesa_do_som)
        postas = eh.distribuir_ancoras(
            [marca_com, marca_sem], emprestadas,
            ja_postas={marca_com: emprestadas[0]},
            proprias={marca_com: eh.ancora_do_gadget(com)},  # type: ignore[dict-item]
        )
        assert postas[marca_com].declarado == interface
        assert postas[marca_sem].syspath == emprestadas[0].syspath
        assert eh.ancora_do_gadget(sem) is None

    def test_o_no_de_som_e_o_pad_dao_o_mesmo_container(
        self, mesa_do_som: Path, tmp_path: Path
    ) -> None:
        import re

        from hefesto_dualsense4unix.integrations import audio_ks_dualsense as ks
        from hefesto_dualsense4unix.integrations import endpoint_de_haptica as eh

        uniq = "aa:bb:cc:00:00:01"
        pad_usb.registrar_gadget(uniq, "/devices/platform/vhci_hcd.0/usb3/3-1/3-1:1.0")
        ancora = eh.ancora_do_gadget(uniq)
        assert ancora is not None
        props = eh.propriedades_do_endpoint(uniq, ancora, rotulo="Háptica")
        caminho = re.search(r"sysfs\.path=(\S+)", props)
        assert caminho is not None
        sink = (
            "Sink #7\n\tName: alsa_output.usb-Sony_x.HiFi__Speaker__sink\n\tProperties:\n"
            '\t\tdevice.vendor.id = "054c"\n\t\tdevice.product.id = "0ce6"\n'
            f'\t\tsysfs.path = "{caminho.group(1)}"\n'
        )
        udev = tmp_path / "udev"
        udev.mkdir()
        (udev / "c189:257").write_text("I:1234567\n")
        controles = ks.controles_no_radio(mesa_do_som, udev, runner=lambda _a: sink)
        assert len(controles) == 1
        c = controles[0]
        # o que o winebus lê do usb_device do pad: 054c:0df2, o bus 3, o devnum 2
        assert (c.container_vid, c.container_pid, c.bus, c.dev, c.usec) == (
            0x054C, 0x0DF2, 3, 2, 1234567,
        )


def test_o_alto_falante_ancora_o_no_do_aparelho_no_gadget_dele(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A reconciliação do daemon, com a mesa de mentira da háptica: P3 tem gadget."""
    from tests.unit import test_a_haptica_chega_a_quem_entra_depois as h

    mesa = h.mesa.__wrapped__(monkeypatch, tmp_path)  # type: ignore[attr-defined]
    monkeypatch.setattr(pad_usb, "_INTERFACE_DO_APARELHO", {})
    _usb_da_mesa(mesa.sysfs, "devices/platform/vhci_hcd.0/usb5", "5-1", vid="054c",
                 pid="0df2", dev="189:513", serial=pad_usb.serial_do_pad("02:fe:00:80:00:03"))
    interface = "/devices/platform/vhci_hcd.0/usb5/5-1/5-1:1.0"
    pad_usb.registrar_gadget(h._P3, interface)
    for uniq, lugar in ((h._P3, 3), (h._P4, 4)):
        mesa.assentos[uniq] = lugar
    mesa.volta(h._Controle(h._P3, "bt", "/dev/hidraw3"), h._Controle(h._P4, "bt", "/dev/hidraw4"))
    assert h._ancora_do_aparelho(mesa.servidor, h._P3) == interface
    emprestada = h._ancora_do_aparelho(mesa.servidor, h._P4)
    assert "/vhci_hcd." not in emprestada and emprestada.startswith("/devices/pci0000:00/")
    do_gadget = [c for c in mesa.registro() if c.container_pid == 0x0DF2]
    assert [(c.bus, c.dev) for c in do_gadget] == [(5, 2)]


# --- 5. A regra 73 abre o pad em USB ao jogo, e o Edge físico segue fechado ---


def _pelo_vhci(serial: str | None) -> Any:
    """Um 0df2 ligado pelo `vhci_hcd`: o nosso gadget, ou um Edge de verdade por usbip."""
    from tests.unit.test_o_fisico_nasce_escondido_em_qualquer_maquina import Aparelho, Elo

    hid = "0003:054C:0DF2.0010"
    attrs = {"idVendor": "054c", "idProduct": "0df2"}
    if serial is not None:
        attrs["serial"] = serial
    return Aparelho(
        f"/devices/platform/vhci_hcd.0/usb3/3-1/3-1:1.0/{hid}/hidraw/hidraw9",
        [
            Elo(hid, "hid", "playstation"),
            Elo("3-1:1.0", "usb", "usbhid"),
            Elo("3-1", "usb", "usb", attrs),
            Elo("usb3", "usb", "usb", {"idVendor": "1d6b", "idProduct": "0002"}),
            Elo("vhci_hcd.0", "platform", "vhci_hcd"),
        ],
    )


@pytest.mark.parametrize("maquina", ["as-duas", "nenhuma", "so-game-devices-udev", "arch-so-steam"])
class TestARegra73AbreOPadEmUsb:
    def _rodar(self, tmp_path: Path, maquina: str, ap: Any) -> Any:
        from tests.unit import test_o_fisico_nasce_escondido_em_qualquer_maquina as udev

        raiz = udev.montar(tmp_path, terceiros=udev.TERCEIROS_POR_MAQUINA[maquina])
        return udev.rodar(ap, raiz)

    def test_o_pad_em_usb_nasce_aberto_para_o_jogo(self, tmp_path: Path, maquina: str) -> None:
        ap = self._rodar(tmp_path, maquina, _pelo_vhci(pad_usb.serial_do_pad("02:fe:00:80:00:01")))
        assert ap.acl_da_sessao and ap.modo == "0660", (ap.tags, ap.modo, ap.run)

    @pytest.mark.parametrize("serial", [None, "", "8c41f2000000", "HEFESTO"])
    def test_o_edge_fisico_por_usbip_segue_fechado(
        self, tmp_path: Path, maquina: str, serial: str | None
    ) -> None:
        from tests.unit import test_o_fisico_nasce_escondido_em_qualquer_maquina as udev

        fechado, motivo = udev._fechado(self._rodar(tmp_path, maquina, _pelo_vhci(serial)))
        assert fechado, motivo

    def test_o_serial_do_hefesto_fora_do_vhci_nao_abre_o_cabo(
        self, tmp_path: Path, maquina: str
    ) -> None:
        from tests.unit import test_o_fisico_nasce_escondido_em_qualquer_maquina as udev

        ap = udev.pelo_cabo("0df2")
        ap.pais[2].attrs["serial"] = pad_usb.serial_do_pad("02:fe:00:80:00:01")
        fechado, motivo = udev._fechado(self._rodar(tmp_path, maquina, ap))
        assert fechado, motivo


def test_a_marca_da_regra_73_e_o_serial_que_o_broker_escreve() -> None:
    from hefesto_dualsense4unix.broker import hidraw_broker

    regra = (Path(__file__).resolve().parents[2] / "assets" / "73-hefesto-ps5-controller.rules")
    texto = regra.read_text(encoding="utf-8")
    assert f'ATTRS{{serial}}=="{pad_usb.SERIAL_PREFIXO}*"' in texto
    assert hidraw_broker.PAD_USB_NOME == pad_usb.SERIAL_PREFIXO
    assert 'KERNEL=="hidg*", SUBSYSTEM=="hidg", MODE="0660"' in texto


# --- 6. Sem o kernel, o pad é uhid, e o doctor diz o contrato que falta ------


def _modulos(tmp_path: Path, carregados: tuple[str, ...]) -> tuple[Path, Path]:
    raiz = tmp_path / "module"
    raiz.mkdir()
    for nome in carregados:
        (raiz / nome).mkdir()
    lib = tmp_path / "lib-modules"
    lib.mkdir()
    (lib / "modules.dep").write_text("kernel/drivers/usb/gadget/udc/dummy_hcd.ko.zst:\n")
    (lib / "modules.builtin").write_text("")
    return raiz, lib


def _doctor_do_pad(tmp_path: Path, raiz: Path, lib: Path) -> str:
    import subprocess
    import sys

    doctor = Path(__file__).resolve().parents[2] / "scripts" / "doctor.sh"
    feito = subprocess.run(
        ["bash", "-c",
         f'source "{doctor}"; '
         f"_python_do_produto() {{ printf '%s\\n' '{sys.executable}'; }}; "
         "check_o_pad_em_usb"],
        capture_output=True, text=True, timeout=60, check=False,
        env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path),
             "HEFESTO_RAIZ_MODULOS": str(raiz), "HEFESTO_LIB_MODULES": str(lib)},
    )
    return feito.stdout + feito.stderr


class TestSemOKernelODoctorDizOContrato:
    def test_o_system_check_nomeia_o_que_falta(self, tmp_path: Path) -> None:
        from hefesto_dualsense4unix.core import system_check

        raiz, lib = _modulos(tmp_path, ("libcomposite", "usb_f_hid"))
        assert system_check.contrato_do_pad_em_usb(
            raiz_modulos=str(raiz), lib_modules=str(lib)
        ) == ["usbip_vudc", "vhci_hcd"]

    def test_o_doctor_avisa_o_contrato_que_falta(self, tmp_path: Path) -> None:
        raiz, lib = _modulos(tmp_path, ("libcomposite", "usb_f_hid", "vhci_hcd"))
        saida = _doctor_do_pad(tmp_path, raiz, lib)
        assert "[WARN]" in saida and "usbip_vudc" in saida, saida
        assert "nasce uhid" in saida

    def test_com_o_contrato_o_doctor_diz_que_o_pad_nasce_em_usb(self, tmp_path: Path) -> None:
        raiz, lib = _modulos(tmp_path, pad_usb.MODULOS_DO_GADGET)
        saida = _doctor_do_pad(tmp_path, raiz, lib)
        assert "[ OK ]" in saida and "[WARN]" not in saida, saida

    def test_o_daemon_avisa_uma_vez_e_o_pad_nasce_uhid(
        self, bancada: BancadaDoGadget, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        avisos: list[dict[str, Any]] = []
        monkeypatch.setattr(bancada.ug, "_CONTRATOS_JA_AVISADOS", set())
        monkeypatch.setattr(
            bancada.ug.logger, "warning",
            lambda evento, **kw: avisos.append({"evento": evento, **kw}),
        )
        bancada.falta = ["vhci_hcd"]
        for _ in range(2):
            pad = bancada.pad()
            try:
                assert pad.start() and pad._gadget is None
            finally:
                pad.stop()
        sem = [a for a in avisos if a["evento"] == "pad_usb_sem_contrato_fica_o_uhid"]
        assert sem == [{"evento": "pad_usb_sem_contrato_fica_o_uhid", "contratos": ["vhci_hcd"]}]
