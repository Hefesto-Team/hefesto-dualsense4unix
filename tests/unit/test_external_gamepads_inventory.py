"""8BIT-01 — inventário READ-ONLY de gamepads externos (todos os vendors).

Cobre o shape do `discover_external_gamepads` com evdev/sysfs FAKE (8BitDo em
modo Switch 057e:2009/nintendo/usb; X-input 045e:028e/xpad), as exclusões
dedicadas (vpad uhid sob /devices/virtual, vpads do Steam, teclado virtual do
daemon, DualSense físico — que é do caminho existente), a subida do sysfs
(driver/hidraw) em árvore real de tmp_path, o opt-in `external` do
`controller.list` (fora do event loop, via thread) e a invariante de que o
`state_full` (caminho quente) NUNCA paga a enumeração.

Regra do sprint: nós evdev renumeram a cada replug — os asserts localizam as
entradas por VID:PID e derivam o `evdev_path` esperado das variáveis do
próprio fake, nunca de um "eventN" literal repetido no assert.

MACs: SEMPRE na faixa forjada canônica da casa (`aa:bb:cc:*`) — o teste-guarda
de anonimato (`test_anonimato_de_fixtures`) só permite essas faixas; até um
OUI público com sufixo inventado reprova, de propósito (regra conservadora).
"""
from __future__ import annotations

import os
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core import evdev_reader as er_mod
from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.core.evdev_reader import (
    _sysfs_driver_hidraw,
    discover_external_gamepads,
)
from hefesto_dualsense4unix.daemon import ipc_handlers as ih_mod
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.testing import FakeController

# MAC 100% forjado na faixa canônica da casa (o teste-guarda de anonimato
# rejeita qualquer OUI fora de aa:bb:cc/02:fe — mesmo um OUI público).
MAC_8BITDO_FORJADO = "aa:bb:cc:00:be:ef"


@pytest.fixture(autouse=True)
def _led_writer_hermetico(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hermeticidade 8BIT-02/EXT-04: desde o EXT-04 a leitura é PURA (quem
    escreve LED é o tick do daemon), mas o dublê fica como DEFESA EM
    PROFUNDIDADE — uma regressão que reintroduzisse a escrita na leitura
    piscaria o LED FÍSICO do 8BitDo real da mantenedora ao rodar a suíte."""
    import hefesto_dualsense4unix.core.external_leds as leds_mod

    monkeypatch.setattr(leds_mod, "write_player_number", lambda *a, **k: False)


# --- fakes de evdev + sysfs -------------------------------------------------


def _instalar_evdev_fake(
    monkeypatch: pytest.MonkeyPatch, registry: dict[str, dict[str, Any]]
) -> None:
    """Substitui `evdev.list_devices`/`evdev.InputDevice` por um registro fake.

    Mesmo padrão do `test_evdev_reader.test_discover_nao_adota_o_vpad_uinput_0df2`:
    o módulo real `evdev` está instalado; só os pontos de entrada são dublados.
    """

    class _FakeDev:
        def __init__(self, path: str) -> None:
            spec = registry[path]
            self.path = path
            self.name = spec["name"]
            self.info = SimpleNamespace(
                vendor=spec["vid"], product=spec["pid"], bustype=spec["bus"]
            )
            self.uniq = spec.get("uniq", "")
            self._caps: dict[int, list[int]] = spec["caps"]

        def capabilities(self) -> dict[int, list[int]]:
            return self._caps

        def close(self) -> None: ...

    monkeypatch.setattr("evdev.list_devices", lambda: list(registry))
    monkeypatch.setattr("evdev.InputDevice", _FakeDev)


def _instalar_realpath_fake(
    monkeypatch: pytest.MonkeyPatch, device_dirs: dict[str, str]
) -> None:
    """`os.path.realpath` fake SÓ para os lookups /sys/class/input/<eventN>/device.

    Caminhos fora do mapa delegam ao realpath REAL — assim a subida no sysfs
    (`_sysfs_driver_hidraw`) resolve symlinks de verdade na árvore de tmp_path,
    e `_is_virtual_evdev` continua decidindo pelo substring `/devices/virtual/`.
    """
    real = os.path.realpath

    def fake(path: Any, **kw: Any) -> str:
        mapped = device_dirs.get(os.fspath(path))
        if mapped is not None:
            return mapped
        return real(path, **kw)

    monkeypatch.setattr("os.path.realpath", fake)


def _arvore_hid(
    tmp_path: Path,
    rel: str,
    driver: str | None,
    hidraw: str | None = None,
) -> str:
    """Monta em tmp_path uma árvore sysfs mínima e devolve o dir do input device.

    Layout real: `<pai>/input/inputN` com `driver` (symlink) e `hidraw/` no PAI
    — é a subida que o código de produção faz.
    """
    base = tmp_path / "sys" / "devices" / rel
    input_dir = base / "input" / f"input{abs(hash(rel)) % 1000}"
    input_dir.mkdir(parents=True)
    if driver is not None:
        drivers = tmp_path / "sys" / "bus" / "drivers" / driver
        drivers.mkdir(parents=True, exist_ok=True)
        (base / "driver").symlink_to(drivers)
    if hidraw is not None:
        (base / "hidraw" / hidraw).mkdir(parents=True)
    return str(input_dir)


def _caps_gamepad() -> dict[int, list[int]]:
    from evdev import ecodes

    return {ecodes.EV_KEY: [ecodes.BTN_SOUTH, ecodes.BTN_EAST]}


# --- discover_external_gamepads: shape --------------------------------------


def test_inventario_shape_8bitdo_switch_e_xinput(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """8BitDo em modo Switch (057e:2009/nintendo/usb + hidraw) e um X-input
    (045e:028e/xpad, sem hidraw) saem com o shape completo e serializável."""
    from evdev import ecodes

    # Números de node propositalmente "estranhos": renumeram a cada replug e
    # nenhum assert abaixo depende deles como literal.
    pro_path = "/dev/input/event261"
    xpad_path = "/dev/input/event97"
    imu_path = "/dev/input/event262"  # IMU do Pro Controller: sem BTN_SOUTH

    pro_dir = _arvore_hid(
        tmp_path, "usb1/1-2/1-2:1.0/0003:057E:2009.0015", "nintendo", "hidraw6"
    )
    xpad_dir = _arvore_hid(tmp_path, "usb3/3-1/3-1:1.0", "xpad")
    imu_dir = _arvore_hid(
        tmp_path, "usb1/1-2/1-2:1.0/0003:057E:2009.0016", "nintendo"
    )

    _instalar_evdev_fake(
        monkeypatch,
        {
            pro_path: {
                "name": "Nintendo Co., Ltd. Pro Controller",
                "vid": 0x057E,
                "pid": 0x2009,
                "bus": 0x03,
                "uniq": MAC_8BITDO_FORJADO,
                "caps": _caps_gamepad(),
            },
            imu_path: {
                "name": "Nintendo Co., Ltd. Pro Controller (IMU)",
                "vid": 0x057E,
                "pid": 0x2009,
                "bus": 0x03,
                "uniq": MAC_8BITDO_FORJADO,
                # Sem caps de gamepad: o nó de motion fica FORA do inventário.
                "caps": {ecodes.EV_ABS: [ecodes.ABS_X, ecodes.ABS_Y]},
            },
            xpad_path: {
                "name": "Microsoft X-Box 360 pad",
                "vid": 0x045E,
                "pid": 0x028E,
                "bus": 0x03,
                "uniq": "",
                "caps": _caps_gamepad(),
            },
        },
    )
    _instalar_realpath_fake(
        monkeypatch,
        {
            "/sys/class/input/event261/device": pro_dir,
            "/sys/class/input/event262/device": imu_dir,
            "/sys/class/input/event97/device": xpad_dir,
        },
    )

    inventario = discover_external_gamepads()

    por_vidpid = {(e["vid"], e["pid"]): e for e in inventario}
    assert len(inventario) == 2, "só os nós COM caps de gamepad entram"

    pro = por_vidpid[("057e", "2009")]
    assert pro == {
        "name": "Nintendo Co., Ltd. Pro Controller",
        "vid": "057e",
        "pid": "2009",
        "bus": "usb",
        "uniq": MAC_8BITDO_FORJADO,
        "driver": "nintendo",
        "evdev_path": pro_path,
        "hidraw": "/dev/hidraw6",
    }

    xpad = por_vidpid[("045e", "028e")]
    assert xpad["driver"] == "xpad"
    assert xpad["bus"] == "usb"
    assert xpad["hidraw"] is None, "xpad é USB puro: não existe hidraw irmão"
    assert xpad["uniq"] is None
    assert xpad["evdev_path"] == xpad_path

    # Serializável de ponta a ponta (vai direto no JSON-RPC).
    import json

    json.dumps(inventario)


def test_inventario_dedup_por_uniq_primeiro_node_vence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sessão BT fantasma + USB do MESMO pad (mesmo uniq) = UMA entrada, a de
    menor número de node — o espelho do dedup do `discover_dualsense_evdevs`."""
    usb_path = "/dev/input/event10"
    bt_path = "/dev/input/event40"
    usb_dir = _arvore_hid(
        tmp_path, "usb1/1-9/1-9:1.0/0003:057E:2009.0020", "nintendo", "hidraw3"
    )
    bt_dir = _arvore_hid(
        tmp_path, "bt/hci0/hci0:256/0005:057E:2009.0021", "nintendo", "hidraw9"
    )
    spec = {
        "name": "Nintendo Co., Ltd. Pro Controller",
        "vid": 0x057E,
        "pid": 0x2009,
        "uniq": MAC_8BITDO_FORJADO,
        "caps": _caps_gamepad(),
    }
    _instalar_evdev_fake(
        monkeypatch,
        {
            bt_path: {**spec, "bus": 0x05},
            usb_path: {**spec, "bus": 0x03},
        },
    )
    _instalar_realpath_fake(
        monkeypatch,
        {
            "/sys/class/input/event10/device": usb_dir,
            "/sys/class/input/event40/device": bt_dir,
        },
    )

    inventario = discover_external_gamepads()

    assert len(inventario) == 1
    assert inventario[0]["evdev_path"] == usb_path
    assert inventario[0]["bus"] == "usb"


# --- dedup quando o `uniq` NÃO identifica o aparelho (endereço sintético) ----
#
# O DKMS `hid-nintendo` deste projeto (patch 0003, parâmetro `usb_probe_degrade`)
# FABRICA um endereço quando o clone não responde ao `REQ_DEV_INFO` no cabo:
# `02` + VID + PID + número do barramento. Não há um bit do aparelho ali — dois
# clones idênticos recebem a MESMA string, como o próprio comentário do patch
# admite. Nunca escrevemos esse endereço como literal (o guarda de anonimato
# `test_anonimato_de_fixtures` reprova qualquer MAC-forma fora das faixas da
# casa, e com razão): ele é DERIVADO da mesma fórmula do kernel, o que de quebra
# documenta a fórmula aqui.

VID_NINTENDO = 0x057E
PID_PRO_CONTROLLER = 0x2009
BUS_USB = 0x03


def _uniq_sintetico(vid: int, pid: int, bus: int) -> str:
    """Reproduz o endereço que o `hid-nintendo` degradado sintetiza.

    Espelho fiel de `joycon_read_mac` no patch 0003: `mac_addr[0] = 0x02`
    (unicast administrado localmente), `[1..2]` = VID, `[3..4]` = PID e
    `[5]` = barramento — formatado em maiúsculas como o `devm_kasprintf` do
    kernel faz.
    """
    octetos = (0x02, vid >> 8, vid & 0xFF, pid >> 8, pid & 0xFF, bus)
    return ":".join(f"{b:02X}" for b in octetos)


def test_dois_clones_com_uniq_sintetico_igual_sao_dois_aparelhos(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pro genuíno + 8BitDo (ambos 057e:2009) degradados no mesmo barramento.

    O kernel entrega o MESMO `uniq` sintético para os dois. Antes da correção o
    `setdefault` engolia o segundo e ele sumia do inventário INTEIRO — sem GUI,
    sem número de jogador, sem uma linha de log. Cada um tem a SUA instância HID
    no sysfs (`.0001` contra `.0006`), e é ela que os separa.
    """
    uniq = _uniq_sintetico(VID_NINTENDO, PID_PRO_CONTROLLER, BUS_USB)

    pro_path = "/dev/input/event30"
    clone_path = "/dev/input/event34"
    pro_dir = _arvore_hid(
        tmp_path, "usb1/1-2/1-2:1.0/0003:057E:2009.0001", "nintendo", "hidraw2"
    )
    clone_dir = _arvore_hid(
        tmp_path, "usb1/1-6/1-6:1.0/0003:057E:2009.0006", "nintendo", "hidraw5"
    )
    spec = {
        "name": "Nintendo Co., Ltd. Pro Controller",
        "vid": VID_NINTENDO,
        "pid": PID_PRO_CONTROLLER,
        "bus": BUS_USB,
        "uniq": uniq,
        "caps": _caps_gamepad(),
    }
    _instalar_evdev_fake(
        monkeypatch, {pro_path: dict(spec), clone_path: dict(spec)}
    )
    _instalar_realpath_fake(
        monkeypatch,
        {
            "/sys/class/input/event30/device": pro_dir,
            "/sys/class/input/event34/device": clone_dir,
        },
    )

    inventario = discover_external_gamepads()

    caminhos = sorted(e["evdev_path"] for e in inventario)
    assert caminhos == [pro_path, clone_path], (
        "dois aparelhos distintos que só COMPARTILHAM o endereço sintetizado "
        "pelo kernel têm de aparecer os DOIS no inventário"
    )
    # O `uniq` segue sendo o que o kernel reporta — o inventário não inventa
    # identidade, só deixa de tratar o endereço sintético como se fosse uma.
    assert {e["uniq"] for e in inventario} == {uniq}
    assert {e["hidraw"] for e in inventario} == {"/dev/hidraw2", "/dev/hidraw5"}


def test_um_clone_com_uniq_sintetico_e_varios_nodes_colapsa_em_um(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O outro lado da moeda, que a correção não pode quebrar.

    UM controle publica vários nodes evdev com caps de gamepad (é o que o
    `hid_playstation` faz com gamepad/touchpad/motion, e o que um relatório HID
    com duas coleções faz em qualquer driver). Todos são filhos da MESMA
    instância HID no sysfs, então continuam colapsando numa entrada só — vence o
    de menor número de node.
    """
    uniq = _uniq_sintetico(VID_NINTENDO, PID_PRO_CONTROLLER, BUS_USB)

    primeiro = "/dev/input/event41"
    irmao = "/dev/input/event42"
    # Mesmo dono: `_arvore_hid` cria `<base>/input/inputN`, e a identidade de
    # aparelho é a `<base>` — o dir da instância HID.
    dono = "usb1/1-2/1-2:1.0/0003:057E:2009.0001"
    base = tmp_path / "sys" / "devices" / dono
    (base / "hidraw" / "hidraw2").mkdir(parents=True)
    input_a = base / "input" / "input70"
    input_b = base / "input" / "input71"
    input_a.mkdir(parents=True)
    input_b.mkdir(parents=True)

    spec = {
        "name": "Nintendo Co., Ltd. Pro Controller",
        "vid": VID_NINTENDO,
        "pid": PID_PRO_CONTROLLER,
        "bus": BUS_USB,
        "uniq": uniq,
        "caps": _caps_gamepad(),
    }
    _instalar_evdev_fake(monkeypatch, {irmao: dict(spec), primeiro: dict(spec)})
    _instalar_realpath_fake(
        monkeypatch,
        {
            "/sys/class/input/event41/device": str(input_a),
            "/sys/class/input/event42/device": str(input_b),
        },
    )

    inventario = discover_external_gamepads()

    assert len(inventario) == 1, (
        "nodes irmãos do MESMO aparelho não podem virar dois controles"
    )
    assert inventario[0]["evdev_path"] == primeiro


def test_dedup_por_mac_real_ignora_a_instancia_hid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Com MAC de verdade, o MAC continua mandando — mesmo em instâncias HID
    diferentes (é o caso do replug e o da sessão USB + Bluetooth ao mesmo
    tempo, em que o kernel cria dois HIDs para o mesmo aparelho)."""
    a_path = "/dev/input/event12"
    b_path = "/dev/input/event45"
    a_dir = _arvore_hid(
        tmp_path, "usb1/1-2/1-2:1.0/0003:057E:2009.0002", "nintendo", "hidraw1"
    )
    b_dir = _arvore_hid(
        tmp_path, "bt/hci0/hci0:512/0005:057E:2009.0007", "nintendo", "hidraw8"
    )
    spec = {
        "name": "Nintendo Co., Ltd. Pro Controller",
        "vid": VID_NINTENDO,
        "pid": PID_PRO_CONTROLLER,
        "uniq": MAC_8BITDO_FORJADO,
        "caps": _caps_gamepad(),
    }
    _instalar_evdev_fake(
        monkeypatch,
        {a_path: {**spec, "bus": BUS_USB}, b_path: {**spec, "bus": 0x05}},
    )
    _instalar_realpath_fake(
        monkeypatch,
        {
            "/sys/class/input/event12/device": a_dir,
            "/sys/class/input/event45/device": b_dir,
        },
    )

    inventario = discover_external_gamepads()

    assert len(inventario) == 1
    assert inventario[0]["evdev_path"] == a_path


def test_uniq_sintetico_e_reconhecido_so_com_o_proprio_vid_pid() -> None:
    """A detecção do endereço sintético é fechada: exige `02` + o VID e o PID
    DO PRÓPRIO aparelho. Um MAC forjado qualquer, ou o mesmo endereço lido de um
    aparelho com outro VID/PID, não passa por sintético — senão o remédio viraria
    o veneno oposto (um controle com MAC legítimo deixando de deduplicar)."""
    uniq = _uniq_sintetico(VID_NINTENDO, PID_PRO_CONTROLLER, BUS_USB)

    assert er_mod._is_synthetic_uniq(uniq, VID_NINTENDO, PID_PRO_CONTROLLER)
    # Mesma string, outro aparelho: não é o endereço sintético DELE.
    assert not er_mod._is_synthetic_uniq(uniq, 0x045E, 0x028E)
    # MAC de verdade (faixa forjada da casa), ausente e malformado.
    assert not er_mod._is_synthetic_uniq(
        MAC_8BITDO_FORJADO, VID_NINTENDO, PID_PRO_CONTROLLER
    )
    assert not er_mod._is_synthetic_uniq(None, VID_NINTENDO, PID_PRO_CONTROLLER)
    assert not er_mod._is_synthetic_uniq("", VID_NINTENDO, PID_PRO_CONTROLLER)
    assert not er_mod._is_synthetic_uniq(
        "nao-e-mac", VID_NINTENDO, PID_PRO_CONTROLLER
    )


def test_owner_dir_degrada_para_o_path_quando_o_sysfs_nao_responde(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sem dono resolvível o inventário cai no node (`path:`) e segue read-only:
    dois aparelhos com o mesmo `uniq` sintético continuam sendo dois."""
    uniq = _uniq_sintetico(VID_NINTENDO, PID_PRO_CONTROLLER, BUS_USB)
    a_path = "/dev/input/event80"
    b_path = "/dev/input/event81"
    spec = {
        "name": "Nintendo Co., Ltd. Pro Controller",
        "vid": VID_NINTENDO,
        "pid": PID_PRO_CONTROLLER,
        "bus": BUS_USB,
        "uniq": uniq,
        "caps": _caps_gamepad(),
    }
    _instalar_evdev_fake(monkeypatch, {a_path: dict(spec), b_path: dict(spec)})
    monkeypatch.setattr(er_mod, "_evdev_owner_dir", lambda _p: None)
    # Hermético: sem este dublê a subida do sysfs sairia de um caminho
    # inexistente e acabaria varrendo o /sys REAL da máquina de teste.
    monkeypatch.setattr(er_mod, "_external_device_sysfs", lambda _p: (None, None))

    inventario = discover_external_gamepads()

    assert sorted(e["evdev_path"] for e in inventario) == [a_path, b_path]


# --- exclusões dedicadas -----------------------------------------------------


def test_exclui_vpads_virtuais_teclado_do_daemon_e_dualsense_fisico(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """As três exclusões do 8BIT-01, cada uma pela SUA razão:

    - vpad uhid do daemon (Edge 054c:0df2 sob /devices/virtual/misc/uhid) e
      vpad do Steam (28de:11ff): virtuais (`_is_virtual_evdev`);
    - teclado virtual do daemon: virtual E sem caps de gamepad (o daemon fake
      TEM esse device aberto — correção 2 do "Honestidade primeiro");
    - DualSense FÍSICO (054c:0ce6): é do caminho existente
      (`discover_dualsense_evdevs`) — o inventário é SÓ dos externos.
    """
    from evdev import ecodes

    pro_path = "/dev/input/event33"
    vpad_uhid_path = "/dev/input/event50"
    vpad_steam_path = "/dev/input/event51"
    teclado_path = "/dev/input/event52"
    dualsense_path = "/dev/input/event7"

    pro_dir = _arvore_hid(
        tmp_path, "bt/hci0/hci0:256/0005:057E:2009.0014", "nintendo", "hidraw6"
    )

    _instalar_evdev_fake(
        monkeypatch,
        {
            dualsense_path: {
                "name": "Sony Interactive Entertainment DualSense Wireless Controller",
                "vid": 0x054C,
                "pid": 0x0CE6,
                "bus": 0x03,
                "uniq": "e8:47:3a:00:00:01",
                "caps": _caps_gamepad(),
            },
            pro_path: {
                "name": "Nintendo Co., Ltd. Pro Controller",
                "vid": 0x057E,
                "pid": 0x2009,
                "bus": 0x05,
                "uniq": MAC_8BITDO_FORJADO,
                "caps": _caps_gamepad(),
            },
            vpad_uhid_path: {
                "name": "Sony Interactive Entertainment DualSense Edge Wireless Controller",
                "vid": 0x054C,
                "pid": 0x0DF2,
                "bus": 0x03,
                "uniq": "02:fe:00:00:00:01",
                "caps": _caps_gamepad(),
            },
            vpad_steam_path: {
                "name": "Microsoft X-Box 360 pad 0",
                "vid": 0x28DE,
                "pid": 0x11FF,
                "bus": 0x03,
                "uniq": "",
                "caps": _caps_gamepad(),
            },
            teclado_path: {
                "name": "Hefesto - Dualsense4Unix Virtual Keyboard",
                "vid": 0x0000,
                "pid": 0x0000,
                "bus": 0x06,
                "uniq": "",
                "caps": {ecodes.EV_KEY: [ecodes.KEY_A, ecodes.KEY_B]},
            },
        },
    )
    _instalar_realpath_fake(
        monkeypatch,
        {
            # Físicos: fora de /devices/virtual/. O DualSense nem chega ao
            # sysfs walk (excluído por vendor/PID antes), então basta um
            # caminho não-virtual qualquer.
            "/sys/class/input/event33/device": pro_dir,
            "/sys/class/input/event7/device": (
                "/sys/devices/pci0000:00/usb1/1-5/1-5:1.3/0003:054C:0CE6.0002/"
                "input/input77"
            ),
            # Virtuais: uhid vive sob /devices/virtual/misc/uhid; uinput
            # (vpads do Steam e teclado do daemon) sob /devices/virtual/input.
            "/sys/class/input/event50/device": (
                "/sys/devices/virtual/misc/uhid/0003:054C:0DF2.0099/input/input300"
            ),
            "/sys/class/input/event51/device": "/sys/devices/virtual/input/input301",
            "/sys/class/input/event52/device": "/sys/devices/virtual/input/input302",
        },
    )

    inventario = discover_external_gamepads()

    assert [(e["vid"], e["pid"]) for e in inventario] == [("057e", "2009")], (
        "o inventário deve conter SÓ o Pro Controller externo"
    )
    entrada = inventario[0]
    assert entrada["bus"] == "bluetooth"
    assert entrada["driver"] == "nintendo"
    assert entrada["evdev_path"] == pro_path


# --- subida do sysfs (árvore REAL em tmp_path, sem monkeypatch) --------------


def test_sysfs_driver_hidraw_sobe_ate_o_pai_hid(tmp_path: Path) -> None:
    base = tmp_path / "0003:057E:2009.0015"
    input_dir = base / "input" / "input99"
    input_dir.mkdir(parents=True)
    drivers = tmp_path / "bus" / "hid" / "drivers" / "nintendo"
    drivers.mkdir(parents=True)
    (base / "driver").symlink_to(drivers)
    (base / "hidraw" / "hidraw6").mkdir(parents=True)

    assert _sysfs_driver_hidraw(str(input_dir)) == ("nintendo", "/dev/hidraw6")


def test_sysfs_driver_hidraw_tolerante_a_ausencia(tmp_path: Path) -> None:
    """Sem driver/hidraw resolvíveis o inventário degrada para None — nunca
    levanta (contrato read-only do 8BIT-01)."""
    solto = tmp_path / "sem_driver" / "input" / "input3"
    solto.mkdir(parents=True)
    assert _sysfs_driver_hidraw(str(solto)) == (None, None)
    assert _sysfs_driver_hidraw(str(tmp_path / "nao_existe")) == (None, None)


# --- handler controller.list: opt-in + fora do event loop --------------------


@pytest.fixture
def ipc_server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> IpcServer:
    """IpcServer mínimo (sem socket no ar) para chamar handlers direto."""
    target = tmp_path / "profiles"
    target.mkdir()

    def fake_profiles_dir(ensure: bool = False) -> Path:
        if ensure:
            target.mkdir(parents=True, exist_ok=True)
        return target

    monkeypatch.setattr(loader_module, "profiles_dir", fake_profiles_dir)
    fc = FakeController(transport="usb")
    fc.connect()
    store = StateStore()
    store.update_controller_state(
        ControllerState(
            battery_pct=50, l2_raw=0, r2_raw=0, connected=True, transport="usb"
        )
    )
    manager = ProfileManager(controller=fc, store=store)
    return IpcServer(
        controller=fc,
        store=store,
        profile_manager=manager,
        socket_path=tmp_path / "hefesto-dualsense4unix.sock",
    )


async def test_controller_list_external_roda_fora_do_event_loop(
    ipc_server: IpcServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Com opt-in, a enumeração roda em OUTRA thread (asyncio.to_thread) —
    nunca na thread do event loop do daemon (PERF-MULTI-CONTROLLER-01)."""
    loop_thread = threading.get_ident()
    visto: dict[str, int] = {}
    sentinela = [
        {
            "name": "Nintendo Co., Ltd. Pro Controller",
            "vid": "057e",
            "pid": "2009",
            "bus": "usb",
            "uniq": MAC_8BITDO_FORJADO,
            "driver": "nintendo",
            "evdev_path": "/dev/input/event261",
            "hidraw": "/dev/hidraw6",
        }
    ]

    def fake_discover() -> list[dict[str, Any]]:
        visto["thread"] = threading.get_ident()
        return [dict(sentinela[0])]

    monkeypatch.setattr(er_mod, "discover_external_gamepads", fake_discover)
    # Hermético: a sonda de holders não pode rodar pgrep de verdade no teste.
    monkeypatch.setattr(ih_mod, "_steam_hidraw_holders", lambda: {})

    result = await ipc_server._handle_controller_list({"external": True})

    assert len(result["external"]) == 1
    ext = dict(result["external"][0])
    # 8BIT-02: número GLOBAL de co-op. R-24: sem registry (o `ipc_server` do
    # teste não tem daemon fiado) o campo é `None` — o posicional legado, que
    # devolvia um número inventado aqui, era um SEGUNDO espaço de numeração.
    slot = ext.pop("player_slot")
    assert slot is None or (isinstance(slot, int) and slot >= 1)
    # CLONE-01: o payload carrega a identidade de APARELHO já resolvida pelo
    # daemon — com MAC de verdade ela é o MAC canônico (a MESMA key do
    # registry), e é dela que a GUI tira a chave do botão do seletor.
    assert ext.pop("identity") == MAC_8BITDO_FORJADO.replace(":", "")
    assert ext == sentinela[0]
    assert result["controllers"], "o shape legado continua presente"
    assert visto["thread"] != loop_thread, (
        "a enumeração (10-40 ms) rodou NA thread do event loop"
    )


async def test_controller_list_external_e_opt_in(
    ipc_server: IpcServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sem `{"external": true}` a resposta é byte-idêntica ao legado (sem a
    chave) e NINGUÉM paga a enumeração; tipo errado é INVALID_PARAMS."""
    chamadas = {"n": 0}

    def fake_discover() -> list[dict[str, Any]]:
        chamadas["n"] += 1
        return []

    monkeypatch.setattr(er_mod, "discover_external_gamepads", fake_discover)
    monkeypatch.setattr(ih_mod, "_steam_hidraw_holders", lambda: {})

    result = await ipc_server._handle_controller_list({})
    assert "external" not in result
    assert chamadas["n"] == 0

    result = await ipc_server._handle_controller_list({"external": False})
    assert "external" not in result
    assert chamadas["n"] == 0

    with pytest.raises(ValueError, match="external"):
        await ipc_server._handle_controller_list({"external": "sim"})
    assert chamadas["n"] == 0

    result = await ipc_server._handle_controller_list({"external": True})
    assert result["external"] == []
    assert chamadas["n"] == 1


async def test_state_full_nao_paga_o_inventario(
    ipc_server: IpcServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Caminho quente intocado: o `state_full` (10-20 Hz) jamais enumera
    /dev/input nem sonda /proc — custo do tick inalterado (8BIT-01)."""

    def bomba(*_a: Any, **_kw: Any) -> Any:
        raise AssertionError(
            "state_full chamou o inventário de externos (caminho quente!)"
        )

    monkeypatch.setattr(er_mod, "discover_external_gamepads", bomba)
    monkeypatch.setattr(ih_mod, "_steam_hidraw_holders", bomba)
    monkeypatch.setattr(ih_mod, "_external_inventory", bomba)

    result = await ipc_server._handle_daemon_state_full({})

    assert "external" not in result
    assert result["connected"] is True


# --- sonda holders: merge e degradação ---------------------------------------


def test_holders_merge_e_degradacao(monkeypatch: pytest.MonkeyPatch) -> None:
    """`holders` só aparece quando a sonda achou o Steam segurando AQUELE
    hidraw; sonda estourando = campo ausente, sem erro (opcional por contrato)."""
    base = {
        "name": "Nintendo Co., Ltd. Pro Controller",
        "vid": "057e",
        "pid": "2009",
        "bus": "usb",
        "uniq": MAC_8BITDO_FORJADO,
        "driver": "nintendo",
        "evdev_path": "/dev/input/event261",
        "hidraw": "/dev/hidraw6",
    }
    # Factory: dict NOVO por chamada — o merge muta a entrada e não pode
    # vazar de um teste para o outro.
    monkeypatch.setattr(
        er_mod, "discover_external_gamepads", lambda: [dict(base)]
    )

    monkeypatch.setattr(
        ih_mod, "_steam_hidraw_holders", lambda: {"/dev/hidraw6": [4242]}
    )
    inventario = ih_mod._external_inventory()
    assert inventario[0]["holders"] == {"steam_pids": [4242]}

    monkeypatch.setattr(
        ih_mod, "_steam_hidraw_holders", lambda: {"/dev/hidraw2": [4242]}
    )
    inventario = ih_mod._external_inventory()
    assert "holders" not in inventario[0], "hidraw de OUTRO device não respinga"

    def explode() -> dict[str, list[int]]:
        raise RuntimeError("/proc sumiu no meio")

    monkeypatch.setattr(ih_mod, "_steam_hidraw_holders", explode)
    inventario = ih_mod._external_inventory()
    # Degrada em silêncio: SEM `holders` (sonda quebrada), mas as CHAVES
    # `player_slot` (8BIT-02) e `identity` (CLONE-01) seguem expostas — são
    # independentes da sonda. R-24: sem `slot_resolver` o slot é `None` (null
    # honesto), nunca o posicional.
    assert "holders" not in inventario[0]
    assert inventario[0] == {
        **base,
        "identity": MAC_8BITDO_FORJADO.replace(":", ""),
        "player_slot": None,
    }


def test_external_inventory_e_leitura_pura_sem_escrita_de_led(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """EXT-04 item 1: listar externos NUNCA escreve LED (a escrita a cada poll
    de 4s da GUI matou o 8BitDo BT ao vivo — `joycon_enforce_subcmd_rate`)."""
    import hefesto_dualsense4unix.core.external_leds as leds_mod

    n1 = {
        "name": "Nintendo Co., Ltd. Pro Controller",
        "vid": "057e", "pid": "2009", "bus": "usb",
        "uniq": MAC_8BITDO_FORJADO, "driver": "nintendo",
        "evdev_path": "/dev/input/event261", "hidraw": "/dev/hidraw6",
    }
    n2 = {**n1, "uniq": "aa:bb:cc:00:be:f0",
          "evdev_path": "/dev/input/event262", "hidraw": "/dev/hidraw7"}
    monkeypatch.setattr(
        er_mod, "discover_external_gamepads", lambda: [dict(n1), dict(n2)]
    )
    monkeypatch.setattr(ih_mod, "_steam_hidraw_holders", lambda: {})

    def bomba_led(*_a: Any, **_kw: Any) -> bool:
        raise AssertionError("leitura de inventário escreveu LED (EXT-04!)")

    monkeypatch.setattr(leds_mod, "apply_player_number", bomba_led)
    monkeypatch.setattr(leds_mod, "write_player_number", bomba_led)
    monkeypatch.setattr(leds_mod, "write_lightbar_slot", bomba_led)

    # R-24: sem registry não existe número — `None` nos dois (o posicional
    # `dualsense_count+índice+1`, que devolvia [3, 4] aqui, era um segundo
    # espaço de numeração escrevendo no mesmo campo que a GUI exibe).
    inventario = ih_mod._external_inventory(dualsense_count=2)

    assert [e["player_slot"] for e in inventario] == [None, None]


def test_external_inventory_prefere_o_slot_do_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """EXT-04 item 2 + NUMA-05 (fim do posicional): com o registry opinando
    (via `slot_resolver`, leitura pura por uniq), o `player_slot` é o slot
    PERSISTENTE — nunca o posicional. Resolver PRESENTE sem opinião (None)
    ou que levanta é a fonte ÚNICA mesmo assim: devolve `player_slot=None`,
    NUNCA o posicional (falha-sem: no HEAD pré-NUMA-05 caía em
    `dualsense_count+índice+1`, reembaralhando a GUI a cada troca de
    `ds_count` — o ponto cego do incidente de 14:42)."""
    n1 = {
        "name": "Nintendo Co., Ltd. Pro Controller",
        "vid": "057e", "pid": "2009", "bus": "usb",
        "uniq": MAC_8BITDO_FORJADO, "driver": "nintendo",
        "evdev_path": "/dev/input/event261", "hidraw": "/dev/hidraw6",
    }
    n2 = {**n1, "uniq": "aa:bb:cc:00:be:f0",
          "evdev_path": "/dev/input/event262", "hidraw": "/dev/hidraw7"}
    monkeypatch.setattr(
        er_mod, "discover_external_gamepads", lambda: [dict(n1), dict(n2)]
    )
    monkeypatch.setattr(ih_mod, "_steam_hidraw_holders", lambda: {})

    # CLONE-01: o resolver é consultado pela IDENTIDADE (`identity_for_entry`),
    # que com MAC de verdade é o MAC CANÔNICO — a mesma key do registry real
    # (`ExternalIdentityRegistry._canonical`), não a string crua do kernel.
    slots = {MAC_8BITDO_FORJADO.replace(":", ""): 4}  # replug preservou o 4

    inventario = ih_mod._external_inventory(
        dualsense_count=1, slot_resolver=lambda uniq: slots.get(uniq or "")
    )

    # 1º externo: slot do registry (4). 2º: registry sem opinião → None
    # (NUMA-05 — nunca mais o posicional 1 DualSense + índice 1 + 1 = 3).
    assert [e["player_slot"] for e in inventario] == [4, None]

    def resolver_quebrado(_uniq: str | None) -> int | None:
        raise RuntimeError("registry indisponível")

    # Resolver PRESENTE que levanta em TODOS: ainda assim é a fonte única —
    # None nos dois, nunca o posicional [2, 3].
    inventario = ih_mod._external_inventory(
        dualsense_count=1, slot_resolver=resolver_quebrado
    )
    assert [e["player_slot"] for e in inventario] == [None, None]


def test_posicional_legado_nao_existe_mais_em_caminho_nenhum(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """R-24 (25/07) — TROCA DELIBERADA de contrato.

    Este caso era `test_external_inventory_posicional_so_sobrevive_sem_
    resolver` e CONGELAVA o posicional (`player_slot == [2]` com ds_count=1,
    `== [1]` com ds_count=0) como "compat do daemon antes do 8BIT-02". Três
    testes acima, o mesmo arquivo já chamava o posicional de causa raiz do
    incidente de 14:42 — congelar a causa raiz como compat é o que a mantinha
    viva. Ele era um SEGUNDO espaço de numeração escrevendo no MESMO campo que
    a GUI e a CLI exibem: mudar `ds_count` deslocava todos os externos e o
    número exibido divergia do LED aceso.

    Agora `player_slot` é ESTÁVEL sob a troca de `ds_count` em todos os
    caminhos — com resolver mudo E sem resolver nenhum.
    """
    n1 = {
        "name": "Nintendo Co., Ltd. Pro Controller",
        "vid": "057e", "pid": "2009", "bus": "usb",
        "uniq": MAC_8BITDO_FORJADO, "driver": "nintendo",
        "evdev_path": "/dev/input/event261", "hidraw": "/dev/hidraw6",
    }
    monkeypatch.setattr(
        er_mod, "discover_external_gamepads", lambda: [dict(n1)]
    )
    monkeypatch.setattr(ih_mod, "_steam_hidraw_holders", lambda: {})

    resolver_sem_opiniao = lambda _uniq: None  # noqa: E731 — registry mudo

    com_ds_count_1 = ih_mod._external_inventory(
        dualsense_count=1, slot_resolver=resolver_sem_opiniao
    )
    com_ds_count_0 = ih_mod._external_inventory(
        dualsense_count=0, slot_resolver=resolver_sem_opiniao
    )
    assert [e["player_slot"] for e in com_ds_count_1] == [None]
    assert [e["player_slot"] for e in com_ds_count_0] == [None]

    # SEM resolver nenhum: `None` também — e IGUAL sob qualquer `ds_count`.
    sem_resolver_1 = ih_mod._external_inventory(dualsense_count=1)
    sem_resolver_0 = ih_mod._external_inventory(dualsense_count=0)
    assert [e["player_slot"] for e in sem_resolver_1] == [None]
    assert [e["player_slot"] for e in sem_resolver_0] == [None]
