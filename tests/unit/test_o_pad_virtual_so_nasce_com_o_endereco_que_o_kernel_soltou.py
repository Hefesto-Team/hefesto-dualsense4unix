"""O-PAD-VIRTUAL-SO-NASCE-COM-O-ENDERECO-QUE-O-KERNEL-JA-SOLTOU-01 (22/11/2026).

O `hid_playstation` recusa o segundo DualSense com o endereço que já está na lista dele
(`-EEXIST`, «Duplicate device found for MAC address»). O pad que troca de roupa nasce no
uhid com o MESMO endereço do gadget que acabou de descer, e o kernel só tira o gadget
alguns milissegundos depois da resposta do broker: o pad novo era recusado e caía no uinput.

O kernel de mentira é o da régua dos dois vpads (a lista do driver, a recusa com `-17`); o
barramento HID é um diretório de mentira com um `uevent` e, quando há driver, o link
`driver`, como o `sysfs` da máquina; o gadget que desce é o `_GadgetDoPad` de verdade com um
broker de mentira que o tira do kernel depois de um tempo medido.
"""

from __future__ import annotations

import os
import shutil
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import o_cabo_em_espera, pad_usb, uhid_gamepad
from hefesto_dualsense4unix.integrations.uhid_blueprint import canonical_blueprint
from hefesto_dualsense4unix.integrations.uhid_gamepad import (
    DUALSENSE_VENDOR,
    UhidDualSense,
    vpad_mac,
    vpad_macs_do_aparelho,
)
from hefesto_dualsense4unix.integrations.virtual_pad import make_virtual_pad
from tests.unit.test_dois_vpads_nunca_tem_o_mesmo_mac import (
    KernelDoHidPlaystation,
    mac_no_report,
)

ROUPA_EDGE = 0x0DF2
ROUPA_COMUM = 0x0CE6

P1, P2, P3 = "aabbcc000001", "aabbcc000002", "aabbcc000003"

PRAZO_S = 0.4

PIOR_MEDIDO_S = 0.236


class _Broker:
    """O broker de mentira: o `desmontar` volta na hora e o kernel tira o gadget depois."""

    def __init__(self, mundo: Mundo, mac: str, depois_s: float | None) -> None:
        self.mundo, self.mac, self.depois_s = mundo, mac, depois_s
        self.desmontou_em: float | None = None

    def desmontar_pad_usb(self, _gadget: str) -> bool:
        self.desmontou_em = time.monotonic()
        if self.depois_s is not None:
            self.mundo.soltar_em(self.mac, self.depois_s)
        return True

    def close(self) -> None:
        pass


class Mundo:
    """O kernel (o uhid e a lista do driver), o barramento HID e os gadgets de uma mesa."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        self.kernel = KernelDoHidPlaystation()
        self.kernel.instalar(monkeypatch)
        self.raiz = tmp_path / "bus-hid"
        self.raiz.mkdir()
        self.driver = tmp_path / "drivers" / "playstation"
        self.driver.mkdir(parents=True)
        monkeypatch.setattr(o_cabo_em_espera, "RAIZ_DO_BARRAMENTO_HID", str(self.raiz))
        monkeypatch.setattr(
            uhid_gamepad, "_GADGETS_ESTACIONADOS", uhid_gamepad._GadgetsEstacionados()
        )
        monkeypatch.setattr(uhid_gamepad, "_O_KERNEL_ESPERA_S", PRAZO_S)
        self.dirs: dict[str, Path] = {}
        self.soltou_em: dict[str, float] = {}
        self.create2: list[tuple[float, str]] = []
        self._timers: list[threading.Timer] = []
        self._n = 0
        original = self.kernel._criar

        def criar(device: Any, dados: bytes) -> None:
            uniq = dados[196:260].split(b"\0", 1)[0].decode("ascii", "replace")
            self.create2.append((time.monotonic(), uniq))
            original(device, dados)

        self.kernel._criar = criar  # type: ignore[method-assign]

    def plantar(self, mac: str, *, driver: bool = True, na_lista: bool = True) -> None:
        """Um HID com `HID_UNIQ=mac`; com driver ele também está na lista do `hid_playstation`."""
        self._n += 1
        pasta = self.raiz / f"0003:054C:0DF2.{0x40 + self._n:04X}"
        pasta.mkdir()
        (pasta / "uevent").write_text(
            "DRIVER=playstation\nHID_ID=0003:0000054C:00000DF2\n"
            f"HID_NAME=Sony\nHID_UNIQ={mac}\nMODALIAS=hid:b0003\n",
            encoding="utf-8",
        )
        if driver:
            os.symlink(self.driver, pasta / "driver")
        if na_lista:
            self.kernel.lista[mac_no_report(mac)] = -1
        self.dirs[mac] = pasta

    def soltar(self, mac: str) -> None:
        """O `device_del`: o link some do barramento e o `ps_remove` tira o endereço da lista."""
        pasta = self.dirs.pop(mac, None)
        if pasta is not None:
            shutil.rmtree(pasta, ignore_errors=True)
        self.kernel.lista.pop(mac_no_report(mac), None)
        self.soltou_em[mac] = time.monotonic()

    def soltar_em(self, mac: str, segundos: float) -> None:
        if segundos <= 0:
            self.soltar(mac)
            return
        timer = threading.Timer(segundos, self.soltar, args=(mac,))
        timer.daemon = True
        self._timers.append(timer)
        timer.start()

    def gadget(
        self, identidade: str, par: tuple[int, int], mac: str, depois_s: float | None
    ) -> Any:
        """Um gadget do aparelho, de pé no kernel com `mac`; `depois_s` é quando ele sai."""
        self.plantar(mac)
        broker = _Broker(self, mac, depois_s)
        return uhid_gamepad._GadgetDoPad(
            cliente=broker, fd=90_000 + self._n, gadget=f"hefesto-pad-{self._n}",
            serial=f"serial-{self._n}", identidade=identidade, hidraw=None,
            interface="usb-de-mentira", par=par,
        )

    def estacionar(self, identidade: str, gadget: Any) -> None:
        chave = pad_usb._so_hex(identidade)
        uhid_gamepad._GADGETS_ESTACIONADOS._por_aparelho[chave] = uhid_gamepad._Estacionado(
            gadget
        )

    def nascer(self, identidade: str, jogador: int, roupa: int = ROUPA_EDGE) -> Any:
        return make_virtual_pad(
            "dualsense", identity=identidade, player=jogador, allow_uhid=True, roupa=roupa
        )

    def fechar(self) -> None:
        for timer in self._timers:
            timer.cancel()


@pytest.fixture
def mundo(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[Mundo]:
    m = Mundo(monkeypatch, tmp_path)
    try:
        yield m
    finally:
        m.fechar()


def _no_uhid(pad: Any, mundo: Mundo) -> None:
    assert pad is not None and pad.backend == "uhid", getattr(pad, "fallback_motivo", None)
    assert mundo.kernel.recusas == [], mundo.kernel.recusas
    assert pad.mac in mundo.kernel.macs_na_lista()


def _primeiro(identidade: str, jogador: int) -> str:
    return vpad_mac(identidade, jogador)


def _segundo(identidade: str, jogador: int) -> str:
    macs = vpad_macs_do_aparelho(identidade, jogador)
    next(macs)
    return next(macs)


def test_o_prazo_cobre_o_pior_gemeo_medido() -> None:
    """O prazo da espera do gêmeo é próprio: acima do pior medido (236 ms), abaixo de 2 s."""
    assert PIOR_MEDIDO_S < uhid_gamepad._O_KERNEL_ESPERA_S <= 2.0


def test_o_pad_nao_nasce_com_o_gemeo_vivo_no_kernel(mundo: Mundo) -> None:
    """D-2211-O-PAD-VIRTUAL-SO-NASCE-COM-O-ENDERECO-SOLTO.

    O gêmeo sai em 100 ms: o `UHID_CREATE2` só é escrito depois, e com o primeiro endereço."""
    mac = _primeiro(P2, 2)
    mundo.plantar(mac)
    mundo.soltar_em(mac, 0.1)

    pad = mundo.nascer(P2, 2)

    _no_uhid(pad, mundo)
    assert pad.mac == mac
    assert [uniq for _t, uniq in mundo.create2] == [mac]
    assert mundo.create2[0][0] >= mundo.soltou_em[mac]


def test_o_gemeo_que_nao_sai_muda_o_endereco_nao_o_caminho(mundo: Mundo) -> None:
    """O gêmeo fica além do prazo: o pad nasce no uhid com o segundo endereço, não no uinput."""
    mac = _primeiro(P2, 2)
    mundo.plantar(mac)

    comeco = time.monotonic()
    pad = mundo.nascer(P2, 2)
    levou = time.monotonic() - comeco

    _no_uhid(pad, mundo)
    assert pad.mac == _segundo(P2, 2) != mac
    assert [uniq for _t, uniq in mundo.create2] == [pad.mac]
    assert levou >= PRAZO_S, "o pad não esperou o prazo antes de trocar o endereço"
    assert levou < PRAZO_S + 1.0


def test_o_estacionado_de_outra_roupa_desce_antes_de_o_endereco_ser_escolhido(
    mundo: Mundo,
) -> None:
    """O estacionado `0ce6` e o pad novo `0df2`: a descida está na fila quando a espera roda."""
    mac = _primeiro(P2, 2)
    gadget = mundo.gadget(P2, (DUALSENSE_VENDOR, ROUPA_COMUM), mac, 0.1)
    mundo.estacionar(P2, gadget)

    pad = mundo.nascer(P2, 2, ROUPA_EDGE)

    _no_uhid(pad, mundo)
    assert pad.mac == mac, "o pad veste o segundo endereço: não esperou a descida"
    broker = gadget.cliente
    assert broker.desmontou_em is not None and broker.desmontou_em <= mundo.soltou_em[mac]
    assert mundo.create2[0][0] >= mundo.soltou_em[mac]


def test_a_mesa_de_tres_trocando_de_roupa_junta(mundo: Mundo) -> None:
    """P1, P2 e P3 trocam no mesmo lançamento; os gêmeos saem em 0, 63 e 236 ms."""
    identidades = {1: P1, 2: P2, 3: P3}
    saidas = {1: 0.0, 2: 0.063, 3: 0.236}
    comeco = time.monotonic()
    for jogador, identidade in identidades.items():
        mac = _primeiro(identidade, jogador)
        mundo.plantar(mac)
        mundo.soltar_em(mac, max(0.0, saidas[jogador] - (time.monotonic() - comeco)))

    pads = {j: mundo.nascer(i, j) for j, i in identidades.items()}

    for jogador, pad in pads.items():
        assert pad is not None and pad.backend == "uhid", (jogador, pad.fallback_motivo)
        assert pad.mac == _primeiro(identidades[jogador], jogador)
    assert mundo.kernel.recusas == []
    assert mundo.kernel.macs_na_lista() == sorted(p.mac for p in pads.values())


def _no_gadget(monkeypatch: pytest.MonkeyPatch) -> None:
    """O lado do gadget que não é do endereço: as features, a enumeração e o fio do fd."""
    monkeypatch.setattr(pad_usb, "escrever_get_report", lambda *_a: None)
    monkeypatch.setattr(pad_usb, "medir_a_marca_do_f_hid", lambda: True)
    monkeypatch.setattr(uhid_gamepad, "_vigiar_a_enumeracao", lambda _pad: None)
    monkeypatch.setattr(UhidDualSense, "_iniciar_o_fio_do_uhid", lambda *_a: None)
    monkeypatch.setattr(UhidDualSense, "_parar_o_fio_do_uhid", lambda *_a: None)


def _pad_na_mao(identidade: str, jogador: int) -> UhidDualSense:
    pad = UhidDualSense.for_flavor(
        "dualsense", player=jogador, blueprint=canonical_blueprint(), identity=identidade,
        roupa=ROUPA_EDGE,
    )
    assert pad is not None
    return pad


def test_o_estacionado_da_mesma_roupa_volta_com_o_mesmo_endereco_sem_espera(
    mundo: Mundo, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O estacionado é o próprio aparelho: o pad o retoma, veste o primeiro e não espera."""
    _no_gadget(monkeypatch)
    monkeypatch.setattr(uhid_gamepad, "_O_KERNEL_ESPERA_S", 1.0)
    mac = _primeiro(P2, 2)
    gadget = mundo.gadget(P2, (DUALSENSE_VENDOR, ROUPA_EDGE), mac, None)
    mundo.estacionar(P2, gadget)
    pad = _pad_na_mao(P2, 2)

    comeco = time.monotonic()
    assert pad.start()
    levou = time.monotonic() - comeco

    try:
        assert pad._gadget is gadget
        assert pad.mac == mac
        assert levou < 0.3, f"o pad esperou {levou:.2f} s pelo próprio gadget"
        assert mundo.create2 == []
    finally:
        pad.stop()


def test_o_hid_recusado_nao_e_gemeo(mundo: Mundo, monkeypatch: pytest.MonkeyPatch) -> None:
    """O HID com o mesmo `HID_UNIQ` e sem driver não está na lista: o pad nasce na hora."""
    monkeypatch.setattr(uhid_gamepad, "_O_KERNEL_ESPERA_S", 1.0)
    mac = _primeiro(P2, 2)
    mundo.plantar(mac, driver=False, na_lista=False)

    comeco = time.monotonic()
    pad = mundo.nascer(P2, 2)
    levou = time.monotonic() - comeco

    _no_uhid(pad, mundo)
    assert pad.mac == mac
    assert levou < 0.3, f"o pad esperou {levou:.2f} s por um HID que não recusa ninguém"


def test_a_volta_ao_uhid_no_tique_nao_espera(
    mundo: Mundo, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O gadget não enumerou e o HID dele segue no kernel: o `pump_ff` troca o endereço."""
    _no_gadget(monkeypatch)
    monkeypatch.setattr(uhid_gamepad, "_O_KERNEL_ESPERA_S", 1.0)
    monkeypatch.setattr(pad_usb, "anotar_falha_da_porta", lambda _jogador: 1)
    mac = _primeiro(P2, 2)
    gadget = mundo.gadget(P2, (DUALSENSE_VENDOR, ROUPA_EDGE), mac, None)
    mundo.estacionar(P2, gadget)
    pad = _pad_na_mao(P2, 2)
    assert pad.start() and pad._gadget is gadget
    pad._gadget_falhou = True

    comeco = time.monotonic()
    pad.pump_ff()
    levou = time.monotonic() - comeco

    try:
        assert pad._gadget is None and pad._fd is not None
        assert pad.mac == _segundo(P2, 2) != mac
        assert [uniq for _t, uniq in mundo.create2] == [pad.mac]
        assert mundo.kernel.recusas == []
        assert levou < 0.2, f"o tique esperou {levou:.2f} s pelo gêmeo"
    finally:
        pad.stop()
