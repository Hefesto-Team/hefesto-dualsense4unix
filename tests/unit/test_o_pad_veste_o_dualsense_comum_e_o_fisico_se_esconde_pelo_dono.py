"""O pad veste o DualSense comum, e o físico se esconde pelo dono.

A régua da O-PAD-VIRTUAL-SE-APRESENTA-COMO-DUALSENSE-COMUM-01: o pad do modo
DualSense pode nascer ``054c:0ce6`` (a roupa comum) sem esconder a si mesmo. O
broker veste os dois pares, a posse separa o pad do físico, a regra 73 abre o
pad e fecha o físico, a quirk ``n`` do par deixa o pad comum no uhid, a env não
nomeia o par da roupa, e os juízes de recriação comparam a roupa sem laço. Tudo
num sysfs, num configfs e num udev de mentira, com as faixas sintéticas.
"""

from __future__ import annotations

import fnmatch
import os
import re
import stat
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.broker import hidraw_broker as broker
from hefesto_dualsense4unix.core.numeros_da_sony import (
    PAR_DUALSENSE_FISICO,
    ROUPA_COMUM,
    ROUPA_EDGE,
    ROUPA_PADRAO,
    VENDOR_SONY,
    roupa_normalizada,
)
from hefesto_dualsense4unix.daemon import launch_env
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager
from hefesto_dualsense4unix.daemon.subsystems.external_mask import registro_de_mascaras
from hefesto_dualsense4unix.integrations import pad_usb, uhid_gamepad
from hefesto_dualsense4unix.integrations import virtual_pad as vp
from hefesto_dualsense4unix.integrations.hidraw_broker_client import HidrawBrokerClient
from tests.unit.test_no_modo_xbox_o_jogo_ve_o_pad import (  # noqa: F401
    MACS,
    _daemon_do_p1,
    _evdev_que_grava,
    _hermetico,
    _no_de,
)
from tests.unit.test_o_broker_veste_o_pid_que_o_pad_pede import Gravador, _corpo
from tests.unit.test_o_pad_nasce_no_mesmo_usb_do_som import KernelDeMentira, _pedido, _serial
from tests.unit.test_subsystem_coop import (
    MAC_P1,
    MAC_P2,
    MAC_P3,
    MAC_P4,
    _FakeReader,
    _make_daemon,
    _set_evdevs,
)

RAIZ = Path(__file__).resolve().parents[2]
REGRA_73 = RAIZ / "assets" / "73-hefesto-ps5-controller.rules"
REGRA_ABERTA_SH = RAIZ / "scripts" / "regra_do_no_aberta.sh"
SONY = VENDOR_SONY
COMUM = ROUPA_COMUM
EDGE = ROUPA_EDGE
ROUPAS = (EDGE, COMUM)
JOGADORES = (1, 2, 3, 4)
DS = vp.CAMINHO_DUALSENSE


@pytest.mark.parametrize("produto", ROUPAS)
def test_o_broker_veste_o_comum_e_recusa_o_resto(tmp_path: Path, produto: int) -> None:
    """``0ce6`` e ``0df2`` montam nos quatro; ``05c4``, ``09cc`` e o Xbox voltam recusados.

    Prova da D-2210-O-PAD-PODE-VESTIR-O-DUALSENSE-COMUM.
    """
    kernel = KernelDeMentira(tmp_path)
    estado = kernel.estado()
    for jogador in JOGADORES:
        resposta, fd = estado.handle_line(
            jogador, 1000, _pedido(_serial(jogador), par=(SONY, produto)))
        assert resposta["ok"] is True, resposta
        assert fd is not None
        os.close(fd)
        g = kernel.gadget(str(resposta["gadget"]))
        assert kernel.lido(g / "idProduct") == f"0x{produto:04x}"
        assert kernel.lido(g / "strings/0x409/product") == broker.PAD_USB_VESTIDOS[(SONY, produto)]
    for vendor, product in ((SONY, 0x05C4), (SONY, 0x09CC), (0x045E, 0x028E)):
        resposta, fd = estado.handle_line(
            9, 1000, _corpo(_serial(1), vendor=vendor, product=product))
        assert fd is None
        assert resposta.get("error") == "reject_bad_product", (vendor, product, resposta)


_RDEV_MAJOR = 237


@dataclass
class _Hidraw:
    """Um ``hidrawN`` do sysfs de mentira: o pai HID real, o uevent e o ``dev``."""

    base: str
    pai: str
    uevent: str
    serial_do_usb: str | None = None


def _sysfs(tmp_path: Path, nos: list[_Hidraw]) -> dict[str, str]:
    """Monta dev/ e sys/ de mentira; devolve as raízes."""
    dev = tmp_path / "dev"
    dev.mkdir(exist_ok=True)
    classe = tmp_path / "sys" / "class" / "hidraw"
    classe.mkdir(parents=True, exist_ok=True)
    for indice, no in enumerate(nos):
        alvo = tmp_path / "sys" / "devices" / no.pai
        alvo.mkdir(parents=True, exist_ok=True)
        (alvo / "uevent").write_text(no.uevent, encoding="ascii")
        if no.serial_do_usb is not None:
            usb_device = Path(pad_usb.usb_device_do_caminho(str(alvo)))
            (usb_device / "serial").write_text(no.serial_do_usb + "\n", encoding="ascii")
        entrada = classe / no.base
        entrada.mkdir()
        (entrada / "device").symlink_to(alvo)
        (entrada / "dev").write_text(f"{_RDEV_MAJOR}:{indice}\n", encoding="ascii")
        (dev / no.base).touch()
    bt = tmp_path / "sys" / "class" / "bluetooth" / "hci0"
    bt.mkdir(parents=True, exist_ok=True)
    (bt / "address").write_text("aa:bb:cc:00:00:01\n", encoding="ascii")
    return {"dev": str(dev), "classe": str(classe), "bt": str(bt.parent)}


def _uevent(hid_id: str, phys: str, uniq: str) -> str:
    return (f"DRIVER=playstation\nHID_ID={hid_id}\nHID_NAME=DualSense Wireless Controller\n"
            f"HID_PHYS={phys}\nHID_UNIQ={uniq}\n")


_ID_USB_COMUM = f"0003:0000{SONY:04X}:0000{COMUM:04X}"
_ID_BT_COMUM = f"0005:0000{SONY:04X}:0000{COMUM:04X}"

_NOS = [
    (_Hidraw("hidraw5", "virtual/misc/uhid/0003:054C:0CE6.0001",
             _uevent(_ID_USB_COMUM, "hefesto-vpad-p1", "02:fe:00:00:00:01")), True),
    (_Hidraw("hidraw6", "platform/vhci_hcd.0/usb3/3-1/3-1:1.0/0003:054C:0CE6.0010",
             _uevent(_ID_USB_COMUM, "usb-vhci_hcd.0-1/input0", ""),
             serial_do_usb="hefesto-pad-02fe00000002"), True),
    (_Hidraw("hidraw2", "pci0000:00/0000:00:14.0/usb1/1-2/1-2:1.3/0003:054C:0CE6.0002",
             _uevent(_ID_USB_COMUM, "usb-0000:00:14.0-2/input3", ""),
             serial_do_usb="aabbcc000007"), False),
    (_Hidraw("hidraw3", "virtual/misc/uhid/0005:054C:0CE6.0006",
             _uevent(_ID_BT_COMUM, "aa:bb:cc:00:00:01", "e8:47:3a:00:00:07")), False),
]


def test_o_pad_comum_nunca_passa_por_fisico(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """MORDIDA: tire a guarda de posse do `_is_dualsense`, e o pad comum vira físico.

    Prova da D-2210-O-PAD-SE-RECONHECE-PELA-POSSE.
    """
    raizes = _sysfs(tmp_path, [no for no, _nosso in _NOS])
    monkeypatch.setattr(uhid_gamepad, "RAIZ_DOS_HIDRAW", raizes["classe"])
    for indice, (no, nosso) in enumerate(_NOS):

        def _chr(_p: str, _i: int = indice) -> Any:
            return SimpleNamespace(st_mode=stat.S_IFCHR | 0o600,
                                   st_rdev=os.makedev(_RDEV_MAJOR, _i))

        posse = pad_usb.e_hidraw_de_pad_nosso(no.base, raiz_class_hidraw=raizes["classe"])
        validado = broker.validate_physical_node(
            f"{raizes['dev']}/{no.base}", dev_root=raizes["dev"],
            sys_class_hidraw=raizes["classe"], sys_class_bluetooth=raizes["bt"],
            stat_fn=_chr)
        assert posse is nosso, f"{no.pai}: a posse disse {posse}"
        assert uhid_gamepad._is_dualsense(no.base) is (not nosso), no.pai
        assert validado == (None if nosso else no.base), f"{no.pai}: o broker disse {validado}"


_CHAVE = re.compile(
    r'(?P<k>[A-Z_]+)(?:\{(?P<a>[^}]+)\})?\s*(?P<op>==|!=|\+=|-=|:=|=)\s*"(?P<v>[^"]*)"')
_CASA = ("==", "!=")


@dataclass
class _No:
    """Um nó hidraw do ponto de vista do udev: o caminho e a cadeia de pais com os ATTRS."""

    rotulo: str
    devpath: str
    cadeia: list[tuple[str, dict[str, str]]] = field(default_factory=list)

    @property
    def kernel(self) -> str:
        return self.devpath.rsplit("/", 1)[-1]


def _linhas_efetivas(texto: str) -> Iterator[list[tuple[str, str | None, str, str]]]:
    for linha in texto.splitlines():
        crua = linha.strip()
        if not crua or crua.startswith("#"):
            continue
        yield [(m["k"], m["a"], m["op"], m["v"]) for m in _CHAVE.finditer(crua)]


def _o_udev_aplica(texto: str, no: _No) -> tuple[str, str, set[str]]:
    """(MODE, OWNER, TAGs) que o udev deixa no nó, partindo do nó ABERTO por outra regra."""
    env: dict[str, str] = {}
    valores = {"MODE": "0666", "OWNER": "root", "GROUP": "root"}
    finais: set[str] = set()
    tags = {"uaccess"}
    for chaves in _linhas_efetivas(texto):
        casou = True
        for chave, attr, op, valor in chaves:
            if op not in _CASA:
                continue
            if chave == "KERNEL":
                alvos: list[str] = [no.kernel]
            elif chave == "SUBSYSTEM":
                alvos = ["hidraw"]
            elif chave == "DEVPATH":
                alvos = [no.devpath]
            elif chave == "KERNELS":
                alvos = [no.kernel] + [nome for nome, _a in no.cadeia]
            elif chave == "ATTRS":
                alvos = [a[attr] for _n, a in no.cadeia if attr in a]
            elif chave == "ENV":
                alvos = [env.get(str(attr), "")]
            else:
                raise AssertionError(f"chave sem casador na régua: {chave}")
            achou = any(fnmatch.fnmatchcase(alvo, valor) for alvo in alvos)
            if achou is not (op == "=="):
                casou = False
                break
        if not casou:
            continue
        for chave, attr, op, valor in chaves:
            if op in _CASA:
                continue
            if chave == "ENV":
                env[str(attr)] = valor
            elif chave == "TAG":
                (tags.add if op == "+=" else tags.discard)(valor)
            elif chave in valores:
                if chave in finais:
                    continue
                valores[chave] = valor
                if op == ":=":
                    finais.add(chave)
            else:
                raise AssertionError(f"atribuição sem casador na régua: {chave}")
    return valores["MODE"], valores["OWNER"], tags


def _nos_do_udev(produto: int) -> list[tuple[_No, bool]]:
    pid = f"{produto:04X}"
    usb = {"idVendor": f"{SONY:04x}", "idProduct": pid.lower()}
    return [
        (_No("pad uhid", f"/devices/virtual/misc/uhid/0003:054C:{pid}.0001/hidraw/hidraw5",
             [(f"0003:054C:{pid}.0001", {}), ("uhid", {}), ("misc", {})]), True),
        (_No("pad USB",
             f"/devices/platform/vhci_hcd.0/usb3/3-1/3-1:1.0/0003:054C:{pid}.0010/hidraw/hidraw6",
             [(f"0003:054C:{pid}.0010", {}), ("3-1:1.0", {}),
              ("3-1", {**usb, "serial": "hefesto-pad-02fe00000002"}),
              ("usb3", {"idVendor": "1d6b", "idProduct": "0002"}), ("vhci_hcd.0", {})]), True),
        (_No("físico no cabo",
             f"/devices/pci0000:00/0000:00:14.0/usb1/1-2/1-2:1.3/0003:054C:{pid}.0002/hidraw/hidraw2",
             [(f"0003:054C:{pid}.0002", {}), ("1-2:1.3", {}), ("1-2", dict(usb)),
              ("usb1", {"idVendor": "1d6b", "idProduct": "0002"})]), False),
        (_No("físico no rádio", f"/devices/virtual/misc/uhid/0005:054C:{pid}.0006/hidraw/hidraw3",
             [(f"0005:054C:{pid}.0006", {}), ("uhid", {}), ("misc", {})]), False),
    ]


@pytest.mark.parametrize("produto", ROUPAS)
def test_a_regra_73_abre_o_pad_comum_e_fecha_o_fisico(tmp_path: Path, produto: int) -> None:
    """MORDIDA: tire o ``ENV{HEFESTO_PAD_USB}!="1"`` da linha USB do ``0ce6``, e o pad USB fecha.

    Prova da D-2210-O-FISICO-SE-ESCONDE-PELO-DONO.
    """
    texto = REGRA_73.read_text(encoding="utf-8")
    for no, nosso in _nos_do_udev(produto):
        modo, dono, tags = _o_udev_aplica(texto, no)
        if nosso:
            assert (modo, "uaccess" in tags) == ("0660", True), f"{no.rotulo} {produto:04x}"
        else:
            assert (modo, dono, "uaccess" in tags) == ("0600", "root", False), (
                f"{no.rotulo} {produto:04x}: o físico saiu aberto")
    aberta = tmp_path / "73-aberta.rules"
    feito = subprocess.run(["bash", str(REGRA_ABERTA_SH), str(REGRA_73), str(aberta)],
                           capture_output=True, text=True, check=False)
    assert feito.returncode == 0, feito.stderr
    fechadas = [linha for chaves in _linhas_efetivas(texto) for linha in [chaves]
                if ("TAG", None, "-=", "uaccess") in linha]
    assert len(fechadas) == 4, "as quatro linhas do físico (cabo e rádio, comum e Edge)"
    for no, _nosso in _nos_do_udev(produto):
        modo, _dono, tags = _o_udev_aplica(aberta.read_text(encoding="utf-8"), no)
        assert (modo, "uaccess" in tags) == ("0660", True), f"aberta: {no.rotulo}"


@pytest.fixture
def gravador(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Gravador:
    g = Gravador()
    monkeypatch.setattr(HidrawBrokerClient, "_request_with_fds",
                        lambda _cliente, payload: g.responder(payload))
    monkeypatch.setattr(uhid_gamepad, "PEDIR_O_PAD_USB", uhid_gamepad._pedir_ao_broker)
    monkeypatch.setattr(uhid_gamepad, "CONTRATO_QUE_FALTA", lambda **_kw: [])
    monkeypatch.setattr(uhid_gamepad, "_GADGETS_ESTACIONADOS",
                        uhid_gamepad._GadgetsEstacionados())
    uhid_falso = tmp_path / "uhid-de-mentira"
    uhid_falso.write_bytes(b"")
    monkeypatch.setattr(uhid_gamepad, "UHID_NODE", str(uhid_falso))
    return g


@pytest.mark.parametrize("quirks", ["054c:0ce6:gn", "054c:0ce6:g", ""])
@pytest.mark.parametrize("produto", ROUPAS)
def test_com_a_quirk_n_o_comum_fica_no_uhid(
    gravador: Gravador, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    quirks: str, produto: int,
) -> None:
    """MORDIDA: tire a leitura da quirk do `_o_pad_em_usb`, e o comum pede o gadget lento."""
    from hefesto_dualsense4unix.integrations.uhid_blueprint import canonical_blueprint

    arquivo = tmp_path / "quirks"
    arquivo.write_text(quirks + "\n", encoding="ascii")
    monkeypatch.setattr(uhid_gamepad, "QUIRK_DO_PAR",
                        lambda par: pad_usb.o_par_tem_a_quirk_que_atrasa(par, str(arquivo)))
    identidade = f"02:fe:00:00:{produto & 0xFF:02x}:{len(quirks):02x}"
    pad = uhid_gamepad.UhidDualSense(player=2, product=produto,
                                     blueprint=canonical_blueprint(), identity=identidade)
    try:
        assert pad.start() is True
    finally:
        pad.stop()
    fica = produto == COMUM and quirks.endswith("n")
    if fica:
        assert gravador.pedidos == [], "o comum com a quirk n pediu o gadget"
        assert pad_usb.porque_sem_porta(identidade) == "quirk_do_par"
    else:
        assert [(p["vendor"], p["product"]) for p in gravador.pedidos] == [(SONY, produto)]


_HOJE_DUALSENSE = {
    "PROTON_DISABLE_HIDRAW": launch_env._DISABLE_HIDRAW_VALUE,
    "SDL_GAMECONTROLLER_IGNORE_DEVICES": launch_env._IGNORE_VALUE,
}


@pytest.mark.parametrize("vpads", [1, 4])
def test_a_env_nao_nomeia_o_pid_que_o_pad_veste(vpads: int) -> None:
    """MORDIDA: devolva o `_IGNORE_VALUE` fixo, e o pad comum some do jogo."""
    comum_no_sdl = launch_env.valor_ignore_devices([PAR_DUALSENSE_FISICO]).lower()
    base = {"native_mode": False, "emulation_enabled": True, "flavor": "dualsense",
            "backends": ["uhid"] * vpads, "fisicos": vpads}
    com_o_comum = launch_env.compose_env(**base, roupa=COMUM)  # type: ignore[arg-type]
    for chave in _HOJE_DUALSENSE:
        assert comum_no_sdl not in com_o_comum.get(chave, "").lower(), chave
    assert "PROTON_DISABLE_HIDRAW" not in com_o_comum, "a lista vazia sai da env"
    assert com_o_comum["SDL_GAMECONTROLLER_IGNORE_DEVICES"] == launch_env.valor_ignore_devices(
        [launch_env.PAR_STEAM_INPUT_VIRTUAL])
    hoje = launch_env.compose_env(**base)  # type: ignore[arg-type]
    assert hoje == launch_env.compose_env(**base, roupa=EDGE)  # type: ignore[arg-type]
    for chave, valor in _HOJE_DUALSENSE.items():
        assert hoje[chave] == valor, chave
    assert set(hoje) - set(com_o_comum) == {"PROTON_DISABLE_HIDRAW"}
    for flavor in ("xbox", "nintendo"):
        outra = {**base, "flavor": flavor}
        assert launch_env.compose_env(**outra, roupa=COMUM) == launch_env.compose_env(**outra)  # type: ignore[arg-type]


def test_sem_o_broker_a_roupa_e_o_edge(monkeypatch: pytest.MonkeyPatch) -> None:
    """A pedida só vale com o dono escondendo o físico; o uinput nunca veste o comum."""
    atende = {"broker": True}
    monkeypatch.setattr(gp, "_o_broker_atende", lambda _d: atende["broker"])
    d = SimpleNamespace(roupa_do_pad=COMUM, _native_mode=False)
    assert gp.a_roupa_que_o_pad_veste(d) == COMUM
    atende["broker"] = False
    assert gp.a_roupa_que_o_pad_veste(d) == ROUPA_PADRAO
    atende["broker"] = True
    d._native_mode = True
    assert gp.a_roupa_que_o_pad_veste(d) == ROUPA_PADRAO
    d._native_mode = False
    for pedida in (None, 0x05C4, True, "0ce6"):
        d.roupa_do_pad = pedida
        assert gp.a_roupa_que_o_pad_veste(d) == ROUPA_PADRAO, pedida
    pad = vp.make_virtual_pad("dualsense", caminho=DS, player=1, identity=MACS[0], roupa=COMUM)
    assert pad is not None
    try:
        assert pad.backend == "uinput"
        assert _no_de(pad).vidpid != (SONY, COMUM)
        assert not vp.a_roupa_mudou(pad, COMUM), "o uinput não tem roupa a comparar"
    finally:
        pad.stop()


@dataclass
class _GadgetDeMentira:
    par: tuple[int, int]
    gadget: str = "hefesto-pad-0"
    serial: str = "hefesto-pad-de-mentira"
    na_casa: int = 0
    desmontado: int = 0

    def desmontar(self) -> None:
        self._soltar_na_casa()
        self._devolver_ao_broker()

    def _soltar_na_casa(self) -> None:
        self.na_casa += 1

    def _devolver_ao_broker(self) -> None:
        self.desmontado += 1


def test_o_gadget_estacionado_nao_troca_de_roupa(monkeypatch: pytest.MonkeyPatch) -> None:
    descida = uhid_gamepad._DescidaAoBroker()
    monkeypatch.setattr(uhid_gamepad, "_DESCIDA_AO_BROKER", descida)
    estacionados = uhid_gamepad._GadgetsEstacionados()
    estacionados._vigia = SimpleNamespace(is_alive=lambda: True)  # type: ignore[assignment]
    edge = _GadgetDeMentira((SONY, EDGE))
    estacionados.estacionar(MACS[1], edge)  # type: ignore[arg-type]
    assert estacionados.retomar(MACS[1], (SONY, COMUM)) is None
    assert edge.na_casa == 1, "o gadget de outra roupa desce na hora"
    assert descida.esperar_tudo(2.0) and edge.desmontado == 1
    assert estacionados.quantos() == 0
    outro = _GadgetDeMentira((SONY, EDGE))
    estacionados.estacionar(MACS[1], outro)  # type: ignore[arg-type]
    assert estacionados.retomar(MACS[1], (SONY, EDGE)) is outro
    assert outro.desmontado == 0


def _uhid_de_pe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(uhid_gamepad, "uhid_available", lambda: True)
    monkeypatch.setattr(uhid_gamepad.UhidDualSense, "start", lambda self: True)
    monkeypatch.setattr(uhid_gamepad.UhidDualSense, "wait_for_bind",
                        lambda self, timeout_s=2.0: True)
    monkeypatch.setattr(uhid_gamepad.UhidDualSense, "stop", lambda self: None)


def test_vestir_a_roupa_recria_o_p1(monkeypatch: pytest.MonkeyPatch) -> None:
    """MORDIDA: tire a roupa do juiz do `start_gamepad_emulation_desfecho`, e o P1 fica Edge."""
    monkeypatch.setattr(gp, "controller_allows_uhid", lambda _d: True)
    monkeypatch.setattr(gp, "_o_broker_atende", lambda _d: True)
    _uhid_de_pe(monkeypatch)
    registro_de_mascaras().set_mask(MACS[0], "dualsense")
    d = _daemon_do_p1(monkeypatch)
    try:
        gp.start_gamepad_emulation_desfecho(d, "dualsense", origin="profile", caminho=DS)
        edge = d._gamepad_device
        assert (edge.backend, edge.product) == ("uhid", EDGE), "premissa: o P1 nasce Edge"
        assert gp.vestir_a_roupa(d, COMUM) == ["p1"]
        comum = d._gamepad_device
        assert comum is not edge and (comum.backend, comum.product) == ("uhid", COMUM)
        assert gp.vestir_a_roupa(d, COMUM) == ["p1"]
        for _ in range(10):
            gp.reconciliar_as_mascaras(d)
        assert d._gamepad_device is comum, "a mesma roupa recriou em laço"
        assert gp.dedup_status(d) == (True, [])
        d._pad_travado_pelo_lancamento = object()
        assert gp.vestir_a_roupa(d, EDGE) == [], "com a trava, a troca é recusada"
        assert d._gamepad_device is comum and d.roupa_do_pad == COMUM
        d._pad_travado_pelo_lancamento = None
        monkeypatch.setattr(gp, "_o_broker_atende", lambda _d: False)
        assert gp.dedup_status(d) == (False, ["roupa_sem_o_dono"])
        assert gp.vestir_a_roupa(d, COMUM) == ["p1"]
        assert d._gamepad_device.product == EDGE, "sem o broker, o P1 volta ao Edge"
    finally:
        gp.stop_gamepad_emulation(d, persist=False)


class _PadUhidDeMentira:
    """O pad uhid dos secundários: veste a roupa que a fábrica recebeu."""

    backend = "uhid"
    criados: list[_PadUhidDeMentira] = []  # noqa: RUF012

    def __init__(self, flavor: str | None, identity: str | None, roupa: object) -> None:
        self.flavor = flavor or "dualsense"
        self.identity = identity
        self.product = roupa_normalizada(roupa)
        self.parado = False
        type(self).criados.append(self)

    def start(self) -> bool:
        return True

    def stop(self) -> None:
        self.parado = True

    def forward_analog(self, **_kw: int) -> None:
        return

    def forward_buttons(self, _pressed: frozenset[str]) -> None:
        return

    def pump_ff(self) -> None:
        return


def test_vestir_a_roupa_recria_os_secundarios(monkeypatch: pytest.MonkeyPatch) -> None:
    """P2 a P4 pelo co-op, na ordem da carta; a mesma roupa não recria; a trava recusa."""
    _FakeReader.grab_ok = True
    _FakeReader.grab_result = "held"
    _PadUhidDeMentira.criados = []
    monkeypatch.setattr("hefesto_dualsense4unix.core.evdev_reader.InputDirWatch.poll",
                        lambda self: True)
    monkeypatch.setattr("hefesto_dualsense4unix.core.evdev_reader.EvdevReader", _FakeReader)
    monkeypatch.setattr("hefesto_dualsense4unix.core.sysfs_leds.discover", lambda: {})
    monkeypatch.setattr(
        vp, "make_virtual_pad",
        lambda flavor, *, identity=None, roupa=None, **_kw: _PadUhidDeMentira(
            flavor, identity, roupa))
    monkeypatch.setattr(gp, "_o_broker_atende", lambda _d: True)
    macs = (MAC_P2, MAC_P3, MAC_P4)
    _set_evdevs(monkeypatch, {MAC_P1: "/dev/input/event5",
                              **{m: f"/dev/input/event{7 + i}" for i, m in enumerate(macs)}})
    daemon = _make_daemon()
    daemon.config.gamepad_emulation_enabled = True
    daemon._native_mode = False
    mgr = CoopManager(daemon)
    daemon._coop_manager = mgr
    mgr.sync()
    assert sorted(mgr._players) == sorted(macs)
    assert {mgr._players[m].vpad.product for m in macs} == {EDGE}, "premissa: nascem Edge"
    nasceram = len(_PadUhidDeMentira.criados)
    vestidos = gp.vestir_a_roupa(daemon, COMUM)
    assert sorted(vestidos) == sorted(["p1", *macs])
    assert {mgr._players[m].vpad.product for m in macs} == {COMUM}
    trocados = _PadUhidDeMentira.criados[nasceram:]
    assert [p.identity for p in trocados] == mgr._na_ordem_da_carta(macs)
    for _ in range(5):
        mgr.sync()
        gp.vestir_a_roupa(daemon, COMUM)
    assert len(_PadUhidDeMentira.criados) == nasceram + len(macs), "a mesma roupa recriou"
    assert not mgr.algum_boneco_ficou_para_tras()
    daemon._pad_travado_pelo_lancamento = object()
    assert gp.vestir_a_roupa(daemon, EDGE) == []
    assert {mgr._players[m].vpad.product for m in macs} == {COMUM}
