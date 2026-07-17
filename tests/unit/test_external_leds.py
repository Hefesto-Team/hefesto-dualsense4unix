"""8BIT-02 — escrita do LED de player dos controles externos (Nintendo/8BitDo).

Cobre o writer PURO ``core/external_leds``: acende os N LEDs verdes à esquerda,
apaga o resto, garante o 5º (azul) apagado, capa em [1,4], é best-effort (nunca
levanta sem os nós/permissão) e resolve a instância HID a partir do hidraw.
Sem daemon, sem GTK — só o sysfs falso em ``tmp_path``.
"""
from __future__ import annotations

import os
from pathlib import Path

from hefesto_dualsense4unix.core import external_leds


def _mk_player_nodes(root: Path, inst: str, *, blue5: bool = True) -> None:
    """Cria os nós de LED (verde 1..4 [+ azul 5]) de um controle no sysfs falso."""
    for i in range(1, 5):
        node = root / f"{inst}:green:player-{i}"
        node.mkdir(parents=True)
        (node / "brightness").write_text("0", encoding="ascii")
    if blue5:
        node = root / f"{inst}:blue:player-5"
        node.mkdir(parents=True)
        (node / "brightness").write_text("1", encoding="ascii")


def _read(root: Path, inst: str, cor: str, i: int) -> str:
    return (root / f"{inst}:{cor}:player-{i}" / "brightness").read_text().strip()


_INST = "0003:057E:2009.000E"


class TestWritePlayerNumber:
    def test_acende_n_a_esquerda_apaga_o_resto(self, tmp_path: Path) -> None:
        _mk_player_nodes(tmp_path, _INST)
        assert external_leds.write_player_number(_INST, 3, leds_root=str(tmp_path)) is True
        assert [_read(tmp_path, _INST, "green", i) for i in range(1, 5)] == [
            "1",
            "1",
            "1",
            "0",
        ]

    def test_player_1(self, tmp_path: Path) -> None:
        _mk_player_nodes(tmp_path, _INST)
        external_leds.write_player_number(_INST, 1, leds_root=str(tmp_path))
        assert [_read(tmp_path, _INST, "green", i) for i in range(1, 5)] == [
            "1",
            "0",
            "0",
            "0",
        ]

    def test_player_4_todos_acesos(self, tmp_path: Path) -> None:
        _mk_player_nodes(tmp_path, _INST)
        external_leds.write_player_number(_INST, 4, leds_root=str(tmp_path))
        assert [_read(tmp_path, _INST, "green", i) for i in range(1, 5)] == [
            "1",
            "1",
            "1",
            "1",
        ]

    def test_capa_acima_de_4(self, tmp_path: Path) -> None:
        # co-op passa slot GLOBAL (pode ser 5, 6...); o LED de player capa em 4.
        _mk_player_nodes(tmp_path, _INST)
        external_leds.write_player_number(_INST, 7, leds_root=str(tmp_path))
        assert [_read(tmp_path, _INST, "green", i) for i in range(1, 5)] == [
            "1",
            "1",
            "1",
            "1",
        ]

    def test_capa_abaixo_de_1(self, tmp_path: Path) -> None:
        _mk_player_nodes(tmp_path, _INST)
        external_leds.write_player_number(_INST, 0, leds_root=str(tmp_path))
        assert [_read(tmp_path, _INST, "green", i) for i in range(1, 5)] == [
            "1",
            "0",
            "0",
            "0",
        ]

    def test_apaga_o_5_azul(self, tmp_path: Path) -> None:
        # o azul (player-5) começa aceso; o co-op 1..4 deve apagá-lo.
        _mk_player_nodes(tmp_path, _INST, blue5=True)
        external_leds.write_player_number(_INST, 2, leds_root=str(tmp_path))
        assert _read(tmp_path, _INST, "blue", 5) == "0"

    def test_sem_nos_e_best_effort(self, tmp_path: Path) -> None:
        # Sem a regra udev / sem os nós: NÃO levanta e devolve False (sem regressão).
        assert (
            external_leds.write_player_number(_INST, 2, leds_root=str(tmp_path)) is False
        )

    def test_sem_o_5_azul_ainda_escreve_os_verdes(self, tmp_path: Path) -> None:
        _mk_player_nodes(tmp_path, _INST, blue5=False)
        assert (
            external_leds.write_player_number(_INST, 2, leds_root=str(tmp_path)) is True
        )
        assert [_read(tmp_path, _INST, "green", i) for i in range(1, 5)] == [
            "1",
            "1",
            "0",
            "0",
        ]


class TestHidInstanceForHidraw:
    def test_resolve_via_sysfs(self, tmp_path: Path, monkeypatch) -> None:
        # /sys/class/hidraw/hidraw2/device -> .../0003:057E:2009.000E
        dev_dir = tmp_path / "sys" / "bus" / "hid" / "devices" / _INST
        dev_dir.mkdir(parents=True)
        link_dir = tmp_path / "sys" / "class" / "hidraw" / "hidraw2"
        link_dir.mkdir(parents=True)
        os.symlink(dev_dir, link_dir / "device")

        real = os.path.realpath

        def fake_realpath(p: str) -> str:
            if p == "/sys/class/hidraw/hidraw2/device":
                return str(dev_dir)
            return real(p)

        monkeypatch.setattr(os.path, "realpath", fake_realpath)
        assert external_leds.hid_instance_for_hidraw("/dev/hidraw2") == _INST

    def test_none_para_vazio(self) -> None:
        assert external_leds.hid_instance_for_hidraw(None) is None
        assert external_leds.hid_instance_for_hidraw("") is None

    def test_none_para_nao_hidraw(self) -> None:
        assert external_leds.hid_instance_for_hidraw("/dev/input/event8") is None
