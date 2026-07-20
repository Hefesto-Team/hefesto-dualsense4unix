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


def _mk_lightbar_nodes(root: Path, prefix: str) -> None:
    """Cria a lightbar RGB de um DS4 no sysfs falso (red/green/blue/global)."""
    for ch in ("red", "green", "blue", "global"):
        node = root / f"{prefix}:{ch}"
        node.mkdir(parents=True)
        (node / "brightness").write_text("0", encoding="ascii")


def _read_lb(root: Path, prefix: str, ch: str) -> str:
    return (root / f"{prefix}:{ch}" / "brightness").read_text().strip()


class TestWriteLightbarSlot:
    """8BitDo por BT (modo DS4): pinta a lightbar com a COR do slot."""

    def test_slot_3_pinta_verde(self, tmp_path: Path) -> None:
        _mk_lightbar_nodes(tmp_path, "input111")
        assert (
            external_leds.write_lightbar_slot("input111", 3, leds_root=str(tmp_path))
            is True
        )
        # player_slot_color(3) = verde (0, 255, 0); 'global' mestre = 1.
        assert _read_lb(tmp_path, "input111", "red") == "0"
        assert _read_lb(tmp_path, "input111", "green") == "255"
        assert _read_lb(tmp_path, "input111", "blue") == "0"
        assert _read_lb(tmp_path, "input111", "global") == "1"

    def test_slot_1_pinta_azul(self, tmp_path: Path) -> None:
        _mk_lightbar_nodes(tmp_path, "input111")
        external_leds.write_lightbar_slot("input111", 1, leds_root=str(tmp_path))
        # slot 1 = azul (0, 0, 255) — mesma paleta dos DualSense.
        assert _read_lb(tmp_path, "input111", "blue") == "255"
        assert _read_lb(tmp_path, "input111", "red") == "0"
        assert _read_lb(tmp_path, "input111", "green") == "0"

    def test_sem_nos_best_effort(self, tmp_path: Path) -> None:
        # Sem a regra udev do DS4 / sem os nós: não levanta e devolve False.
        assert (
            external_leds.write_lightbar_slot("input111", 3, leds_root=str(tmp_path))
            is False
        )


class TestResolveExternalLeds:
    def test_nintendo_quando_ha_green_player(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        _mk_player_nodes(tmp_path, _INST)
        monkeypatch.setattr(external_leds, "hid_instance_for_hidraw", lambda h: _INST)
        assert external_leds.resolve_external_leds(
            "/dev/hidraw2", leds_root=str(tmp_path)
        ) == ("nintendo", _INST)

    def test_ds4_lightbar_via_realpath(self, tmp_path: Path, monkeypatch) -> None:
        # Sem barra verde -> resolve pela lightbar RGB (nó :red cujo device é o
        # mesmo do hidraw). Prefixo = inputNN real, NÃO a instância HID.
        hid_dir = tmp_path / "hiddev"
        real_red = hid_dir / "leds" / "input111:red"
        real_red.mkdir(parents=True)
        (real_red / "brightness").write_text("0", encoding="ascii")
        leds = tmp_path / "leds"
        leds.mkdir()
        os.symlink(real_red, leds / "input111:red")
        monkeypatch.setattr(external_leds, "_hid_device_dir", lambda h: str(hid_dir))
        monkeypatch.setattr(
            external_leds, "hid_instance_for_hidraw", lambda h: "0005:054C:05C4.0016"
        )
        assert external_leds.resolve_external_leds(
            "/dev/hidraw7", leds_root=str(leds)
        ) == ("ds4", "input111")

    def test_nenhum_modo(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(external_leds, "hid_instance_for_hidraw", lambda h: None)
        monkeypatch.setattr(external_leds, "_hid_device_dir", lambda h: None)
        assert external_leds.resolve_external_leds(
            "/dev/hidraw9", leds_root=str(tmp_path)
        ) == (None, None)


class TestApplyPlayerNumber:
    """Despacha o indicador de posição pelo MODO — cabo (verde) OU BT (lightbar)."""

    def test_despacha_nintendo(self, tmp_path: Path, monkeypatch) -> None:
        _mk_player_nodes(tmp_path, _INST)
        monkeypatch.setattr(
            external_leds, "resolve_external_leds", lambda h, r=None: ("nintendo", _INST)
        )
        assert (
            external_leds.apply_player_number(
                "/dev/hidraw2", 3, leds_root=str(tmp_path)
            )
            is True
        )
        assert [_read(tmp_path, _INST, "green", i) for i in range(1, 5)] == [
            "1",
            "1",
            "1",
            "0",
        ]

    def test_despacha_ds4_lightbar(self, tmp_path: Path, monkeypatch) -> None:
        _mk_lightbar_nodes(tmp_path, "input111")
        monkeypatch.setattr(
            external_leds, "resolve_external_leds", lambda h, r=None: ("ds4", "input111")
        )
        assert (
            external_leds.apply_player_number(
                "/dev/hidraw7", 3, leds_root=str(tmp_path)
            )
            is True
        )
        assert _read_lb(tmp_path, "input111", "green") == "255"

    def test_sem_modo_e_noop(self, monkeypatch) -> None:
        monkeypatch.setattr(
            external_leds, "resolve_external_leds", lambda h, r=None: (None, None)
        )
        assert external_leds.apply_player_number("/dev/hidraw9", 3) is False


# --- GYRO-02: pacote cru + escrita do Enable-IMU (0x40/0x01) -----------------


class TestBuildEnableImuPacket:
    """Golden bytes do subcomando Enable-IMU (protocolo Switch, hid-nintendo).

    Envelope rumble+subcmd: output_id(1B)=0x01, packet_num(1B), rumble_data
    neutro (8B), subcmd_id(1B)=0x40, arg(1B)=0x01 — 12 bytes no total.
    """

    def test_pacote_padrao_packet_num_zero(self) -> None:
        pacote = external_leds.build_enable_imu_packet()
        assert pacote == bytes(
            (
                0x01,  # output_id: rumble + subcmd
                0x00,  # packet_num
                0x00, 0x01, 0x40, 0x40,  # rumble neutro (esquerda)
                0x00, 0x01, 0x40, 0x40,  # rumble neutro (direita)
                0x40,  # subcmd_id: Enable-IMU
                0x01,  # arg: ligar
            )
        )
        assert len(pacote) == 12

    def test_packet_num_capado_em_4_bits(self) -> None:
        """O contador do firmware é 0..0xF — valores fora capam por máscara."""
        pacote = external_leds.build_enable_imu_packet(packet_num=0x1F)
        assert pacote[1] == 0x0F

    def test_e_funcao_pura_sem_hidraw_nenhum(self) -> None:
        """Duas chamadas com o mesmo argumento dão o MESMO pacote (sem estado)."""
        a = external_leds.build_enable_imu_packet(packet_num=3)
        b = external_leds.build_enable_imu_packet(packet_num=3)
        assert a == b


class TestEnableImu:
    """``enable_imu`` escreve o pacote CRU no hidraw — best-effort, nunca levanta."""

    def test_escreve_o_pacote_exato_no_device(self, tmp_path: Path) -> None:
        no = tmp_path / "hidraw7"
        no.write_bytes(b"")
        assert external_leds.enable_imu(str(no)) is True
        assert no.read_bytes() == external_leds.build_enable_imu_packet()

    def test_sem_device_e_false_sem_levantar(self, tmp_path: Path) -> None:
        assert external_leds.enable_imu(str(tmp_path / "nao-existe")) is False

    def test_hidraw_none_e_false(self) -> None:
        assert external_leds.enable_imu(None) is False

    def test_sem_permissao_e_false_sem_levantar(self, tmp_path: Path) -> None:
        no = tmp_path / "hidraw8"
        no.write_bytes(b"")
        os.chmod(no, 0o000)
        try:
            assert external_leds.enable_imu(str(no)) is False
        finally:
            os.chmod(no, 0o600)  # devolve p/ o tmp_path poder limpar
