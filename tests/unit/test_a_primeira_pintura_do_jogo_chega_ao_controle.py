"""A primeira pintura do jogo chega ao controle (A-PRIMEIRA-PINTURA-DO-JOGO-CHEGA-AO-CONTROLE-01).

O jogo escreve o número e a cor na abertura, antes de o tique do sinal de jogo abrir o portão: a
escrita fica retida sob ``daemon``. Na abertura, chega o retido do processo que segura o pad e é o
jogo; o do cliente da Steam continua descartado. Quem segura cada pad é o leitor do produto
(`quem_segura_o_pad.jogos_por_pad`) sobre um ``/proc`` de mentira, com um nó por pad.
"""
from __future__ import annotations

import os
import select
import struct
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pydualsense.pydualsense import DSAudio, DSLight, DSTrigger

from hefesto_dualsense4unix.core import backend_pydualsense as bp
from hefesto_dualsense4unix.core.led_control import player_led_pattern, player_slot_color
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp_mod
from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager
from hefesto_dualsense4unix.integrations import uhid_gamepad
from hefesto_dualsense4unix.integrations.quem_segura_o_pad import jogos_por_pad
from hefesto_dualsense4unix.integrations.uhid_gamepad import (
    _GAME_REPLICA_GRACE_S,
    HID_MAX_DESCRIPTOR_SIZE,
    UHID_CLOSE,
    UHID_OPEN,
    UHID_OUTPUT,
    UHID_START,
    UhidDualSense,
    _GadgetDoPad,
)

MACS = {n: f"AA:BB:CC:00:00:0{n}" for n in (1, 2, 3, 4)}
PID_DA_STEAM = 100
PID_DO_JOGO = 200
COR_DO_JOGO = (0, 200, 40)
COR_DA_PALETA = (64, 0, 0)

COMBINACOES = [
    (player, via, caminho)
    for player in (1, 2, 3, 4)
    for via in ("cabo", "radio")
    for caminho in ("uhid", "gadget")
]


_RELOGIOS: dict[int, Any] = {}


class _NoDeLed:
    def __init__(self) -> None:
        self.rgb_calls: list[tuple[int, int, int]] = []
        self.player_calls: list[tuple[bool, ...]] = []

    def set_rgb(self, r: int, g: int, b: int) -> bool:
        self.rgb_calls.append((r, g, b))
        return True

    def set_players(self, bits: tuple[bool, ...]) -> bool:
        self.player_calls.append(tuple(bits))
        return True

    def invalidate_cache(self) -> None:
        return None


class _Proc:
    """Um ``/proc`` de mentira: quem tem o descritor do nó do pad virtual."""

    def __init__(self, raiz: Path) -> None:
        self.proc = raiz / "proc"
        self.dev = raiz / "dev"
        self.dev.mkdir(parents=True)
        self.nos = {n: self.dev / f"hidraw1{n}" for n in MACS}
        for no in self.nos.values():
            no.write_bytes(b"")
        self._criar(PID_DA_STEAM, "steam", "/home/u/.steam/ubuntu12_32/steam")
        self._criar(PID_DO_JOGO, "Jogo.exe", "Z:\\jogo\\Jogo.exe")

    def _criar(self, pid: int, nome: str, cmdline: str) -> None:
        pasta = self.proc / str(pid)
        (pasta / "fd").mkdir(parents=True)
        (pasta / "comm").write_text(nome + "\n")
        (pasta / "cmdline").write_bytes(cmdline.encode() + b"\0")

    def segura(self, pid: int, segura: bool, players: tuple[int, ...] = tuple(MACS)) -> None:
        for n in players:
            link = self.proc / str(pid) / "fd" / f"1{n}"
            if segura and not link.is_symlink():
                link.symlink_to(self.nos[n])
            elif not segura and link.is_symlink():
                link.unlink()

    def leitor(self) -> Any:
        vpads = {MACS[n]: SimpleNamespace(mac=f"02:fe:00:00:00:0{n}", name="pad") for n in MACS}
        nos = {
            f"02:fe:00:00:00:0{n}": (str(self.nos[n]), os.stat(self.nos[n]).st_ino) for n in MACS
        }
        return lambda: jogos_por_pad(
            vpads,
            raiz_proc=str(self.proc),
            resolver=lambda uniq, **_k: {"hidraw": nos[uniq][0], "hidraw_ino": nos[uniq][1]},
            raiz_dev=str(self.dev),
            meu_pid=1,
        )


def _handle(via: str) -> SimpleNamespace:
    handle = SimpleNamespace(
        triggerL=DSTrigger(),
        triggerR=DSTrigger(),
        light=DSLight(),
        audio=DSAudio(),
        _raw_trigger_left=None,
        _raw_trigger_right=None,
        is_edge=False,
        connected=True,
        escritos=[],
    )
    if via == "radio":
        handle.conType = SimpleNamespace(name="BT")
        handle.writeReport = handle.escritos.append
    return handle


def _mesa(via: str, proc: _Proc) -> tuple[bp.PyDualSenseController, dict[int, _NoDeLed], Any]:
    ctl = bp.PyDualSenseController()
    nos = {n: _NoDeLed() for n in MACS}
    ctl._handles = {MACS[n]: _handle(via) for n in MACS}
    ctl._sysfs = {MACS[n]: nos[n] for n in MACS}
    ctl._primary_key = MACS[1]
    for n in MACS:
        uniq = MACS[n].replace(":", "").lower()
        ctl._desired_by_uniq[uniq] = bp._DesiredOutput(
            led=player_slot_color(n), player_leds=player_led_pattern(n)
        )
        ctl._desired_owner_by_uniq[uniq] = {
            "led": bp._LAYER_PROFILE,
            "player_leds": bp._LAYER_PROFILE,
        }
    sinal = SimpleNamespace(valor="daemon")
    ctl.set_game_authority_provider(lambda: sinal.valor)
    leitor = proc.leitor()
    ctl.set_quem_segura_o_pad(leitor)
    daemon = SimpleNamespace(
        controller=ctl, display_authority="daemon", sinal=sinal, leitor=leitor
    )
    return ctl, nos, daemon


def _pad(daemon: Any, player: int, caminho: str) -> UhidDualSense:
    relogio = SimpleNamespace(t=0.0)
    _RELOGIOS[player] = relogio
    if player == 1:
        ralos = gp_mod.make_primary_replica_sinks(daemon)
    else:
        ralos = CoopManager(daemon)._make_player_replica_sinks(MACS[player])
    pad = UhidDualSense(
        player=player,
        identity=MACS[player],
        product=0x0CE6,
        time_fn=lambda: relogio.t,
        sleep_fn=lambda _s: None,
        **ralos,
    )
    if caminho == "gadget":
        pad._gadget = _GadgetDoPad(cliente=None, fd=-1, gadget="g", serial=f"hefesto-pad-{player}")
    pad._handle_event(struct.pack("<I", UHID_START))
    relogio.t = _GAME_REPLICA_GRACE_S + 0.5
    pad._handle_event(struct.pack("<I", UHID_OPEN))
    return pad


def _escreve(pad: UhidDualSense, caminho: str, numero: int, cor: tuple[int, int, int]) -> None:
    _RELOGIOS[pad.player].t += 1.0
    corpo = bytearray(47)
    corpo[1] = uhid_gamepad._PLAYER_INDICATOR_CONTROL_ENABLE | uhid_gamepad._LIGHTBAR_CONTROL_ENABLE
    corpo[43] = sum(1 << i for i, b in enumerate(player_led_pattern(numero)) if b)
    corpo[44:47] = bytes(cor)
    report = bytes([0x02]) + bytes(corpo)
    if caminho == "uhid":
        pad._handle_event(
            struct.pack("<I", UHID_OUTPUT)
            + report.ljust(HID_MAX_DESCRIPTOR_SIZE, b"\0")[:HID_MAX_DESCRIPTOR_SIZE]
            + struct.pack("<HB", len(report), 1)
        )
        return
    leitura, escrita = os.pipe()
    try:
        os.set_blocking(leitura, False)
        os.write(escrita, report)
        uhid_gamepad._drenar_o_gadget(pad, leitura, select.POLLIN)
    finally:
        os.close(leitura)
        os.close(escrita)


def _espera_os_autores(ctl: bp.PyDualSenseController) -> None:
    """O fio de fundo deu autor a toda escrita retida."""
    prazo = time.monotonic() + 5.0
    while ctl._fio_dos_autores is not None or ctl._retido_sem_autor:
        assert time.monotonic() < prazo, "o fio de fundo não resolveu o autor das escritas retidas"
        time.sleep(0.005)


def _abre_o_portao(ctl: bp.PyDualSenseController, daemon: Any) -> None:
    """O tique: a varredura em `_run_blocking` guarda a resposta por pad e a borda abre o portão."""
    ctl.set_jogos_nos_pads(daemon.leitor())
    daemon.sinal.valor = "game"
    ctl.replay_retained_game_outputs()


def _o_que_vale(ctl: bp.PyDualSenseController, player: int) -> tuple[Any, Any]:
    with ctl._io_lock:
        merged = ctl._merged_desired_for_key(MACS[player])
    return merged.player_leds, merged.led


def _numero(player: int) -> int:
    return player % 4 + 1


@pytest.mark.parametrize(("player", "via", "caminho"), COMBINACOES)
def test_a_escrita_retida_do_jogo_chega_na_abertura(
    player: int, via: str, caminho: str, tmp_path: Path
) -> None:
    """MORDIDA: devolver o descarte total na abertura e o número e a cor do jogo nunca chegam."""
    proc = _Proc(tmp_path)
    proc.segura(PID_DO_JOGO, True)
    ctl, nos, daemon = _mesa(via, proc)
    pad = _pad(daemon, player, caminho)

    _escreve(pad, caminho, _numero(player), COR_DO_JOGO)
    assert COR_DO_JOGO not in nos[player].rgb_calls, "sob daemon a escrita chegou antes do portão"

    _abre_o_portao(ctl, daemon)

    assert _o_que_vale(ctl, player) == (player_led_pattern(_numero(player)), COR_DO_JOGO)
    assert COR_DO_JOGO in nos[player].rgb_calls
    assert player_led_pattern(_numero(player)) in nos[player].player_calls
    if via == "radio":
        assert ctl._handles[MACS[player]].escritos, "pelo rádio o 0x31 da luz não saiu"
    for outro in MACS:
        if outro != player:
            assert COR_DO_JOGO not in nos[outro].rgb_calls


@pytest.mark.parametrize(("player", "via", "caminho"), COMBINACOES)
def test_a_escrita_retida_da_steam_e_descartada(
    player: int, via: str, caminho: str, tmp_path: Path
) -> None:
    """D-0311-A-PRIMEIRA-PINTURA-DO-JOGO.

    MORDIDA: reaplicar todo retido e a paleta da Steam vira o número e a cor do jogador."""
    proc = _Proc(tmp_path)
    proc.segura(PID_DA_STEAM, True)
    ctl, nos, daemon = _mesa(via, proc)
    pad = _pad(daemon, player, caminho)

    _escreve(pad, caminho, _numero(player), COR_DA_PALETA)
    _espera_os_autores(ctl)
    proc.segura(PID_DO_JOGO, True)
    _abre_o_portao(ctl, daemon)

    assert _o_que_vale(ctl, player) == (player_led_pattern(player), player_slot_color(player))
    assert COR_DA_PALETA not in nos[player].rgb_calls
    assert ctl._game_output_by_uniq == {}


@pytest.mark.parametrize(("player", "via", "caminho"), COMBINACOES)
def test_a_steam_e_o_jogo_no_mesmo_controle_so_o_do_jogo_chega(
    player: int, via: str, caminho: str, tmp_path: Path
) -> None:
    proc = _Proc(tmp_path)
    proc.segura(PID_DA_STEAM, True)
    ctl, nos, daemon = _mesa(via, proc)
    pad = _pad(daemon, player, caminho)

    _escreve(pad, caminho, _numero(player) % 4 + 1, COR_DA_PALETA)
    _espera_os_autores(ctl)
    proc.segura(PID_DO_JOGO, True)
    _escreve(pad, caminho, _numero(player), COR_DO_JOGO)
    _abre_o_portao(ctl, daemon)

    assert _o_que_vale(ctl, player) == (player_led_pattern(_numero(player)), COR_DO_JOGO)
    assert COR_DA_PALETA not in nos[player].rgb_calls


def test_a_ultima_escrita_do_jogo_vence_a_da_steam_que_veio_depois(tmp_path: Path) -> None:
    proc = _Proc(tmp_path)
    proc.segura(PID_DO_JOGO, True)
    ctl, nos, daemon = _mesa("cabo", proc)
    ctl.set_game_output_for(MACS[2], led=COR_DO_JOGO)
    _espera_os_autores(ctl)
    proc.segura(PID_DO_JOGO, False)
    proc.segura(PID_DA_STEAM, True)
    ctl.set_game_output_for(MACS[2], led=COR_DA_PALETA)
    _espera_os_autores(ctl)
    proc.segura(PID_DO_JOGO, True)

    _abre_o_portao(ctl, daemon)

    assert _o_que_vale(ctl, 2)[1] == COR_DO_JOGO
    assert COR_DA_PALETA not in nos[2].rgb_calls


def test_o_retido_de_um_jogo_que_ja_saiu_nao_chega_no_seguinte(tmp_path: Path) -> None:
    proc = _Proc(tmp_path)
    proc.segura(PID_DO_JOGO, True)
    ctl, nos, daemon = _mesa("cabo", proc)
    ctl.set_game_output_for(MACS[1], led=COR_DO_JOGO)
    _espera_os_autores(ctl)
    proc.segura(PID_DO_JOGO, False)

    _abre_o_portao(ctl, daemon)

    assert _o_que_vale(ctl, 1)[1] == player_slot_color(1)
    assert COR_DO_JOGO not in nos[1].rgb_calls


@pytest.mark.parametrize("caminho", ["uhid", "gadget"])
def test_o_fim_da_sessao_esquece_o_autor_do_retido(caminho: str, tmp_path: Path) -> None:
    """MORDIDA: o fim da sessão sem esquecer o autor e o número da sessão velha volta na nova."""
    proc = _Proc(tmp_path)
    proc.segura(PID_DO_JOGO, True)
    ctl, nos, daemon = _mesa("cabo", proc)
    pad = _pad(daemon, 3, caminho)
    _escreve(pad, caminho, 1, COR_DA_PALETA)
    pad._handle_event(struct.pack("<I", UHID_CLOSE))
    pad._handle_event(struct.pack("<I", UHID_OPEN))

    ctl.set_game_output_for(MACS[3], led=COR_DO_JOGO)
    _abre_o_portao(ctl, daemon)

    assert _o_que_vale(ctl, 3) == (player_led_pattern(3), COR_DO_JOGO)
    assert player_led_pattern(1) not in nos[3].player_calls
    assert COR_DA_PALETA not in nos[3].rgb_calls


def test_o_leitor_que_falha_vale_como_ninguem(tmp_path: Path) -> None:
    proc = _Proc(tmp_path)
    ctl, nos, daemon = _mesa("cabo", proc)

    def quebra() -> Any:
        raise OSError("proc sumiu")

    ctl.set_quem_segura_o_pad(quebra)
    ctl.set_game_output_for(MACS[1], led=COR_DO_JOGO)
    _abre_o_portao(ctl, daemon)

    assert COR_DO_JOGO not in nos[1].rgb_calls


def test_o_daemon_liga_ao_backend_o_leitor_de_quem_segura_o_pad(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MORDIDA: tirar a fiação do `_wire_game_signal` e o backend nunca sabe quem escreveu."""
    from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
    from hefesto_dualsense4unix.integrations import quem_segura_o_pad

    ctl = bp.PyDualSenseController()
    daemon = Daemon(controller=ctl, config=DaemonConfig(ipc_enabled=False, udp_enabled=False))
    jogo = SimpleNamespace(pid=PID_DO_JOGO, nome="Jogo.exe", no="/dev/hidraw12")
    monkeypatch.setattr(quem_segura_o_pad, "jogos_por_pad", lambda _pads: {MACS[2]: jogo})

    daemon._wire_game_signal()

    uniq = MACS[2].replace(":", "").lower()
    assert ctl._os_jogos_nos_pads() == {uniq: (PID_DO_JOGO, "Jogo.exe")}
    assert daemon._processo_no_pad() == "Jogo.exe"
    assert ctl._jogo_por_alvo == {uniq: (PID_DO_JOGO, "Jogo.exe")}
