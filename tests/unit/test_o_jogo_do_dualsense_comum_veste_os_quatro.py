"""O jogo do DualSense comum veste os quatro.

A régua da O-JOGO-DO-DUALSENSE-COMUM-VESTE-OS-QUATRO-JOGADORES-01.
A roupa é do jogo, não do P1: com o jogo do `0ce6` no ar, todo pad que nasce veste o
`0ce6`, o do controle que chega atrasado, o do que sai e volta, o do que muda de número
e o P1 que nasce no meio do jogo, no cabo e no rádio. E o report do `0ce6` em repouso não
aperta nada: os eixos no centro, os gatilhos soltos, o d-pad no estado nulo.
"""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.core.numeros_da_sony import ROUPA_COMUM
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager
from hefesto_dualsense4unix.daemon.subsystems.external_mask import registro_de_mascaras
from hefesto_dualsense4unix.integrations import uhid_gamepad
from hefesto_dualsense4unix.integrations import virtual_pad as vp
from hefesto_dualsense4unix.integrations.uhid_blueprint import canonical_blueprint
from hefesto_dualsense4unix.testing.fake_controller import FakeController
from tests.unit.test_no_modo_xbox_o_jogo_ve_o_pad import MACS, _daemon_do_p1
from tests.unit.test_o_pad_veste_o_dualsense_comum_e_o_fisico_se_esconde_pelo_dono import (
    _PadUhidDeMentira,
    _uhid_de_pe,
)
from tests.unit.test_subsystem_coop import (
    MAC_P1,
    MAC_P2,
    MAC_P3,
    MAC_P4,
    _FakeReader,
    _make_daemon,
    _set_evdevs,
)

COMUM = ROUPA_COMUM
_NO = {MAC_P1: "/dev/input/event5", MAC_P2: "/dev/input/event7",
       MAC_P3: "/dev/input/event8", MAC_P4: "/dev/input/event9"}


def _coop_de_mentira(monkeypatch: pytest.MonkeyPatch, slots: dict[str, int]) -> Any:
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
    daemon = _make_daemon(slots=slots)
    daemon.config.gamepad_emulation_enabled = True
    daemon._native_mode = False
    daemon.roupa_do_pad = COMUM
    mgr = CoopManager(daemon)
    daemon._coop_manager = mgr
    return mgr


def _roupas(mgr: CoopManager) -> dict[str, int]:
    return {m: j.vpad.product for m, j in mgr._players.items() if j.vpad is not None}


def test_o_controle_que_chega_sai_e_muda_de_numero_veste_o_comum(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MORDIDA: a roupa só no P1 (o `_roupa` do co-op no Edge) e P2 a P4 nascem Edge."""
    slots = {MAC_P1: 1, MAC_P2: 2}
    mgr = _coop_de_mentira(monkeypatch, slots)
    _set_evdevs(monkeypatch, {m: _NO[m] for m in (MAC_P1, MAC_P2)})
    mgr.sync()
    assert _roupas(mgr) == {MAC_P2: COMUM}, "o P2 que já estava"

    slots.update({MAC_P3: 3, MAC_P4: 4})
    _set_evdevs(monkeypatch, _NO)
    mgr.sync()
    assert _roupas(mgr) == dict.fromkeys((MAC_P2, MAC_P3, MAC_P4), COMUM), "os que chegam depois"

    del slots[MAC_P3]
    slots[MAC_P4] = 3
    _set_evdevs(monkeypatch, {m: _NO[m] for m in (MAC_P1, MAC_P2, MAC_P4)})
    mgr.sync()
    assert _roupas(mgr) == dict.fromkeys((MAC_P2, MAC_P4), COMUM), "o que muda de número"

    slots[MAC_P3] = 4
    _set_evdevs(monkeypatch, _NO)
    mgr.sync()
    assert _roupas(mgr) == dict.fromkeys((MAC_P2, MAC_P3, MAC_P4), COMUM), "o que volta"
    assert {p.product for p in _PadUhidDeMentira.criados} == {COMUM}, "nenhum Edge no jogo"
    assert not mgr.algum_boneco_ficou_para_tras()


@pytest.mark.parametrize("transporte", ["usb", "bt"])
@pytest.mark.parametrize("quem", range(4), ids=[f"controle-{n + 1}" for n in range(4)])
def test_o_p1_que_nasce_no_meio_do_jogo_veste_o_comum(
    monkeypatch: pytest.MonkeyPatch, transporte: str, quem: int,
) -> None:
    """O P1 é qualquer um dos quatro, no cabo ou no rádio, e nasce com o jogo já no `0ce6`."""
    monkeypatch.setattr(gp, "controller_allows_uhid", lambda _d: True)
    monkeypatch.setattr(gp, "_o_broker_atende", lambda _d: True)
    _uhid_de_pe(monkeypatch)
    registro_de_mascaras().set_mask(MACS[quem], "dualsense")
    d = _daemon_do_p1(monkeypatch)
    d.controller = FakeController(transport=transporte)
    d.controller.primary_uniq = MACS[quem]
    d.roupa_do_pad = COMUM
    try:
        gp.start_gamepad_emulation_desfecho(d, "dualsense", origin="profile",
                                            caminho=vp.CAMINHO_DUALSENSE)
        assert (d._gamepad_device.backend, d._gamepad_device.product) == ("uhid", COMUM)
        assert gp.dedup_status(d) == (True, [])
    finally:
        gp.stop_gamepad_emulation(d, persist=False)


# --- o report do `0ce6` em repouso ------------------------------------------------------


@pytest.mark.parametrize("jogador", [1, 2, 3, 4])
def test_o_comum_em_repouso_nao_aperta_nada(jogador: int) -> None:
    """MORDIDA: o d-pad neutro como 0 (o «cima» do hat) ou os eixos em 0 e a régua reprova."""
    pad = uhid_gamepad.UhidDualSense(
        player=jogador, product=COMUM, blueprint=canonical_blueprint(),
        identity=f"aa:bb:cc:00:00:{jogador:02x}")
    corpo = pad._encode_body()
    sticks_e_gatilhos = tuple(corpo[0:6])
    hat = corpo[uhid_gamepad._BUTTONS0_OFFSET] & 0x0F

    assert sticks_e_gatilhos == (0x80, 0x80, 0x80, 0x80, 0, 0)
    assert hat == 8, f"o hat do repouso é {hat}, e 0 é o «cima»"
    assert corpo[uhid_gamepad._BUTTONS0_OFFSET] & 0xF0 == 0
    assert corpo[uhid_gamepad._BUTTONS1_OFFSET] == 0
    assert corpo[uhid_gamepad._BUTTONS2_OFFSET] == 0


def test_o_cima_solto_volta_ao_repouso(monkeypatch: pytest.MonkeyPatch) -> None:
    """O «cima» apertado e solto devolve o hat nulo no report que sai, não fica preso."""
    enviados: list[bytes] = []
    pad = uhid_gamepad.UhidDualSense(
        player=1, product=COMUM, blueprint=canonical_blueprint(), identity="aa:bb:cc:00:00:01")
    pad._fd = 4242

    def _enviar(report: bytes) -> bool:
        enviados.append(report)
        return True

    monkeypatch.setattr(pad, "send_report", _enviar)

    pad.forward_buttons(frozenset({"dpad_up"}))
    pad.forward_buttons(frozenset())

    hats = [r[1 + uhid_gamepad._BUTTONS0_OFFSET] & 0x0F for r in enviados]
    assert hats == [0, 8], hats
