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

    def test_slot_5_acende_so_o_azul(self, tmp_path: Path) -> None:
        """R-25: o 5º LED (azul) é o bit "+5" — slot 5 = azul sozinho."""
        _mk_player_nodes(tmp_path, _INST)
        external_leds.write_player_number(_INST, 5, leds_root=str(tmp_path))
        assert [_read(tmp_path, _INST, "green", i) for i in range(1, 5)] == [
            "0",
            "0",
            "0",
            "0",
        ]
        assert _read(tmp_path, _INST, "blue", 5) == "1"

    def test_slot_7_nao_pode_ser_igual_ao_4(self, tmp_path: Path) -> None:
        """R-25 — TROCA DELIBERADA de contrato (`test_capa_acima_de_4`).

        Este caso assertava que o slot 7 acendia EXATAMENTE o mesmo padrão do
        slot 4 (capping em 4). Com o espaço de numeração único (R-24) o slot
        7 é alcançável de verdade (2 DualSense + Pro + 8BitDo + …), e dois
        controles idênticos na barra é a queixa "nunca sei o que é o quê"
        chegando ao hardware. Agora 7 = azul + 2 verdes.
        """
        _mk_player_nodes(tmp_path, _INST)
        external_leds.write_player_number(_INST, 7, leds_root=str(tmp_path))
        sete = [_read(tmp_path, _INST, "green", i) for i in range(1, 5)] + [
            _read(tmp_path, _INST, "blue", 5)
        ]
        assert sete == ["1", "1", "0", "0", "1"]

        external_leds.write_player_number(_INST, 4, leds_root=str(tmp_path))
        quatro = [_read(tmp_path, _INST, "green", i) for i in range(1, 5)] + [
            _read(tmp_path, _INST, "blue", 5)
        ]
        assert quatro != sete

    def test_padroes_de_1_a_9_sao_todos_distintos(self, tmp_path: Path) -> None:
        """R-25: a barra (4 verdes + azul) codifica 9 números SEM repetir.

        Falha-sem: com o capping em 4, os slots 4..9 escreviam o mesmo padrão
        — seis controles indistinguíveis.
        """
        _mk_player_nodes(tmp_path, _INST)
        vistos: list[tuple[str, ...]] = []
        for slot in range(1, 10):
            external_leds.write_player_number(_INST, slot, leds_root=str(tmp_path))
            vistos.append(
                tuple(
                    [_read(tmp_path, _INST, "green", i) for i in range(1, 5)]
                    + [_read(tmp_path, _INST, "blue", 5)]
                )
            )
        assert len(set(vistos)) == 9

    def test_sem_o_azul_capa_em_4_por_limite_fisico(self, tmp_path: Path) -> None:
        """Hardware sem a 5ª lâmpada não tem como exibir 5+: capa em 4 (o
        histórico), nunca apaga a barra inteira (que é o que "5 = só o azul"
        faria num controle sem azul)."""
        _mk_player_nodes(tmp_path, _INST, blue5=False)
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

    def test_slot_ate_4_apaga_o_5_azul(self, tmp_path: Path) -> None:
        # R-25: o azul é o bit "+5" — slot ≤4 tem de apagá-lo, senão o 2 seria
        # lido como 7 (e o tick repintaria o mesmo LED de 2 em 2 segundos).
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


class TestReadPlayerPattern:
    """R-25: o reader tem de decodificar EXATAMENTE o que o writer escreve.

    Se o writer usa o azul como "+5" e o reader ignora o azul, todo controle
    em slot ≥5 é lido como um número diferente do escrito, o tick o declara
    "escritor estrangeiro" (NUMA-03) e repinta o MESMO LED a cada 2 s — o
    bombardeio de subcomando que matou o 8BitDo ao vivo (EXT-04).
    """

    def _escreve(self, tmp: Path, slot: int) -> None:
        external_leds.write_player_number(_INST, slot, leds_root=str(tmp))

    def test_ida_e_volta_de_1_a_9(self, tmp_path: Path) -> None:
        _mk_player_nodes(tmp_path, _INST)
        for slot in range(1, 10):
            self._escreve(tmp_path, slot)
            assert (
                external_leds.read_player_pattern(_INST, leds_root=str(tmp_path))
                == slot
            ), f"slot {slot} não sobreviveu ao round-trip"

    def test_tudo_apagado_e_zero(self, tmp_path: Path) -> None:
        _mk_player_nodes(tmp_path, _INST)
        (tmp_path / f"{_INST}:blue:player-5" / "brightness").write_text(
            "0", encoding="ascii"
        )
        assert external_leds.read_player_pattern(_INST, leds_root=str(tmp_path)) == 0

    def test_buraco_nos_verdes_e_estrangeiro(self, tmp_path: Path) -> None:
        """O 'player 1+3' que a Steam pinta segue sendo -1 (não é padrão nosso)."""
        _mk_player_nodes(tmp_path, _INST)
        for i, aceso in enumerate(["1", "0", "1", "0"], start=1):
            (tmp_path / f"{_INST}:green:player-{i}" / "brightness").write_text(
                aceso, encoding="ascii"
            )
        assert external_leds.read_player_pattern(_INST, leds_root=str(tmp_path)) == -1

    def test_sem_o_azul_le_como_sem_mais_5(self, tmp_path: Path) -> None:
        """Nó azul ausente = "sem +5" (é o mesmo hardware em que o writer capa
        em 4) — nunca `None`, que congelaria a defesa de repintura."""
        _mk_player_nodes(tmp_path, _INST, blue5=False)
        self._escreve(tmp_path, 3)
        assert external_leds.read_player_pattern(_INST, leds_root=str(tmp_path)) == 3

    def test_verde_ausente_e_none(self, tmp_path: Path) -> None:
        """Barra verde inexistente (device sumiu, modo DS4) = sem leitura."""
        assert external_leds.read_player_pattern(_INST, leds_root=str(tmp_path)) is None


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
