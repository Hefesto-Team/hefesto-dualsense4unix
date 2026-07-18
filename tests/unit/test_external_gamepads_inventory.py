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
    """Hermeticidade 8BIT-02: o `_external_inventory` ESCREVE o LED de player do
    controle externo. Sem isto, rodar a suíte na máquina da mantenedora (com um
    8BitDo real em `/dev/hidraw6`) piscaria o LED FÍSICO. Neutraliza por padrão;
    o teste dedicado ao LED re-substitui por um captor depois deste fixture."""
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
    slot = ext.pop("player_slot")  # 8BIT-02: número GLOBAL de co-op, sempre >= 1
    assert isinstance(slot, int) and slot >= 1
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
    # Degrada em silêncio: SEM `holders` (sonda quebrada), mas o `player_slot`
    # (8BIT-02) segue exposto — é independente da sonda.
    assert "holders" not in inventario[0]
    assert inventario[0] == {**base, "player_slot": 1}


def test_external_inventory_numera_slot_global_e_escreve_led(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """8BIT-02: cada externo recebe `player_slot` = dualsense_count + índice + 1
    (continua a contagem dos DualSense) e o daemon ESCREVE esse número no LED
    de player do próprio controle (best-effort — só LED, nunca input)."""
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
    # Captura as escritas de LED por hidraw (sem tocar o sysfs real). O daemon
    # chama apply_player_number, que escolhe a barra verde (Switch/cabo) ou a
    # lightbar RGB (8BitDo-DS4 por BT) conforme o modo — cobre CABO e BLUETOOTH.
    escritas: list[tuple[str, int]] = []
    monkeypatch.setattr(
        leds_mod, "apply_player_number",
        lambda hidraw, num: (escritas.append((hidraw, num)), True)[1],
    )

    # Com 2 DualSense (slots 1 e 2), os externos são 3 e 4.
    inventario = ih_mod._external_inventory(dualsense_count=2)

    assert [e["player_slot"] for e in inventario] == [3, 4]
    assert escritas == [
        ("/dev/hidraw6", 3),
        ("/dev/hidraw7", 4),
    ]
