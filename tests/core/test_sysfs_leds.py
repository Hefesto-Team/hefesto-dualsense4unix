"""Testes herméticos da rota sysfs de LED do kernel (FEAT-DSX-LIGHTBAR-SYSFS-01).

Monta uma árvore /sys/class/leds falsa em tmp_path espelhando o layout que o
`hid_playstation` cria (lightbar `*:rgb:indicator` + 5 `*:white:player-N`,
device HID com `uevent` contendo `HID_UNIQ`) e valida discovery por MAC,
gravabilidade e escrita.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from hefesto_dualsense4unix.core import sysfs_leds


def _build_fake_leds(root: Path, *, mac: str, prefix: str = "input88", players: int = 5) -> Path:
    """Cria a árvore sysfs falsa e devolve o diretório /sys/class/leds simulado.

    Estrutura espelhando o kernel:
        <dev>/uevent                       (HID_UNIQ=<mac>)
        <dev>/leds/<prefix>:rgb:indicator/{multi_intensity,brightness}
        <dev>/leds/<prefix>:white:player-N/brightness
        <leds_class>/<nome>  -> symlink p/ o nó real (como /sys/class/leds)
    """
    dev = root / "devices" / "hid0"
    leds_real = dev / "leds"
    (dev).mkdir(parents=True)
    (dev / "uevent").write_text(
        f"HID_ID=0005:0000054C:00000CE6\nHID_NAME=DualSense Wireless Controller\nHID_UNIQ={mac}\n"
    )
    leds_class = root / "class" / "leds"
    leds_class.mkdir(parents=True)

    def _mk_led(name: str, attrs: dict[str, str]) -> None:
        d = leds_real / name
        d.mkdir(parents=True)
        for attr, val in attrs.items():
            (d / attr).write_text(val)
        (leds_class / name).symlink_to(d)

    _mk_led(f"{prefix}:rgb:indicator", {"multi_intensity": "0 0 255", "brightness": "255"})
    for i in range(1, players + 1):
        _mk_led(f"{prefix}:white:player-{i}", {"brightness": "0"})
    return leds_class


@pytest.fixture
def fake_leds(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    leds_class = _build_fake_leds(tmp_path, mac="AA:BB:CC:00:00:01")
    monkeypatch.setattr(sysfs_leds, "LEDS_ROOT", str(leds_class))
    return leds_class


def test_norm_mac_strips_colons_and_lowercases() -> None:
    assert sysfs_leds.norm_mac("AA:BB:CC:00:00:01") == "aabbcc000001"
    assert sysfs_leds.norm_mac("aabbcc000001") == "aabbcc000001"
    assert sysfs_leds.norm_mac(None) is None
    assert sysfs_leds.norm_mac("") is None
    # string sem nenhum dígito hex -> None (não casa um nó por MAC)
    assert sysfs_leds.norm_mac("ghijkl") is None
    # um path qualquer só preserva os hex contíguos — nunca colide com um MAC
    # real (12 dígitos), então cai no fallback single-controle do backend.
    assert sysfs_leds.norm_mac("/dev/hidraw5") == "deda5"


def test_discover_keys_by_normalized_mac(fake_leds: Path) -> None:
    found = sysfs_leds.discover()
    assert set(found) == {"aabbcc000001"}
    node = found["aabbcc000001"]
    assert node.indicator_dir.endswith("input88:rgb:indicator")
    assert len(node.player_dirs) == 5


def test_discover_falls_back_to_uniq_when_no_hid_uniq(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # uevent sem HID_UNIQ, mas com input/<prefix>/uniq preenchido.
    dev = tmp_path / "devices" / "hid0"
    (dev / "input" / "input88").mkdir(parents=True)
    (dev / "uevent").write_text("HID_NAME=DualSense Wireless Controller\n")
    (dev / "input" / "input88" / "uniq").write_text("aa:bb:cc:00:00:01\n")
    leds_real = dev / "leds" / "input88:rgb:indicator"
    leds_real.mkdir(parents=True)
    (leds_real / "multi_intensity").write_text("0 0 0")
    (leds_real / "brightness").write_text("0")
    leds_class = tmp_path / "class" / "leds"
    leds_class.mkdir(parents=True)
    (leds_class / "input88:rgb:indicator").symlink_to(leds_real)
    monkeypatch.setattr(sysfs_leds, "LEDS_ROOT", str(leds_class))

    found = sysfs_leds.discover()
    assert set(found) == {"aabbcc000001"}


def test_set_rgb_writes_intensity_and_full_brightness(fake_leds: Path) -> None:
    node = sysfs_leds.discover()["aabbcc000001"]
    assert node.set_rgb(255, 90, 0) is True
    assert Path(node._multi_intensity).read_text() == "255 90 0"
    assert Path(node._indicator_brightness).read_text() == "255"


def test_set_rgb_clamps_out_of_range(fake_leds: Path) -> None:
    node = sysfs_leds.discover()["aabbcc000001"]
    assert node.set_rgb(999, -5, 256) is True
    assert Path(node._multi_intensity).read_text() == "255 0 255"


def test_set_players_maps_bits_to_brightness(fake_leds: Path) -> None:
    node = sysfs_leds.discover()["aabbcc000001"]
    assert node.set_players((True, False, True, False, True)) is True
    vals = [Path(d, "brightness").read_text() for d in node.player_dirs]
    assert vals == ["1", "0", "1", "0", "1"]


def test_writable_reflects_permission(fake_leds: Path) -> None:
    node = sysfs_leds.discover()["aabbcc000001"]
    assert node.writable() is True
    # remove permissão de escrita -> writable() vira False (gate anti-regressão)
    os.chmod(node._multi_intensity, 0o444)
    assert node.writable() is False


def test_discover_empty_when_no_nodes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    empty = tmp_path / "class" / "leds"
    empty.mkdir(parents=True)
    monkeypatch.setattr(sysfs_leds, "LEDS_ROOT", str(empty))
    assert sysfs_leds.discover() == {}
