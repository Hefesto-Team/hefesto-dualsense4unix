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
    return f"hefesto-pad-02fe8a0000{n:02x}"


@pytest.fixture
def kernel(tmp_path: Path) -> KernelDeMentira:
    return KernelDeMentira(tmp_path)


class TestOBrokerMontaOGadgetSoHid:
    def test_o_gadget_montado_tem_so_a_funcao_hid_sem_out(self, kernel: KernelDeMentira) -> None:
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
