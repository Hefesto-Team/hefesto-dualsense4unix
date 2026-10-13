"""O-PAR-DO-GESTO-DO-PS-NAO-CHEGA-AO-JOGO-01 — o gesto do PS fica com o Hefesto.

O filtro do combo (`HotkeyManager.combo_buttons_active`) só alimentava o mouse e
o teclado do desktop: o pad virtual do P1 (`dispatch_gamepad`) e os do co-op
(`forward_all`) recebiam os botões crus. PS + R3 (trocar o modo) entregava o R3
ao jogo, PS + L3 o L3, PS + cima/baixo o direcional, PS + Options o Options. E
o latch era um só para a mesa, embora o aperto já fosse por controle.

Agora os dois caminhos do pad passam por `gamepad.sem_o_gesto_do_ps`, que lê o
latch DAQUELE controle. O jogo é lido pelo olho dele: o pad é o `UinputGamepad`
do produto, na máscara DualSense e na Xbox, com o nó trocado por um gravador
dos `EV_KEY` que o jogo leria.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest
from evdev import ecodes

from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager, _SecondaryPlayer
from hefesto_dualsense4unix.integrations.hotkey_daemon import HotkeyManager
from hefesto_dualsense4unix.integrations.uinput_gamepad import UinputGamepad

P1 = "aabbcc000001"
P2 = "aabbcc000002"
MASCARAS = ("dualsense", "xbox")
GESTOS = (
    ("ps", "r3"),
    ("ps", "l3"),
    ("ps", "dpad_up"),
    ("ps", "options"),
)


#: O direcional chega ao jogo como chapéu (`ABS_HAT0*`), não como tecla.
DIRECIONAL = {
    "dpad_up": (ecodes.ABS_HAT0Y, -1),
    "dpad_down": (ecodes.ABS_HAT0Y, 1),
    "dpad_left": (ecodes.ABS_HAT0X, -1),
    "dpad_right": (ecodes.ABS_HAT0X, 1),
}


class _No:
    """O nó do uinput de mentira: guarda as teclas e o chapéu que o jogo leria."""

    def __init__(self) -> None:
        self.teclas: list[tuple[int, int]] = []
        self.chapeu: list[tuple[int, int]] = []

    def write(self, tipo: int, codigo: int, valor: int) -> None:
        if tipo == ecodes.EV_KEY:
            self.teclas.append((codigo, valor))
        elif tipo == ecodes.EV_ABS and codigo in (ecodes.ABS_HAT0X, ecodes.ABS_HAT0Y):
            self.chapeu.append((codigo, valor))

    def syn(self) -> None:
        pass


def _pad(mascara: str) -> tuple[UinputGamepad, _No]:
    no = _No()
    pad = UinputGamepad(flavor=mascara)
    pad._device = no
    pad._ecodes = ecodes
    return pad, no


def _apertou(pad: UinputGamepad, no: _No, botao: str) -> bool:
    if botao in DIRECIONAL:
        return DIRECIONAL[botao] in no.chapeu
    codigo = pad._resolve_evdev(botao, ecodes)
    assert codigo is not None, f"{botao} não existe na máscara {pad.mascara_no_jogo}"
    return (codigo, 1) in no.teclas


class _Leitor:
    """O leitor do co-op: devolve o retrato que o teste põe na mão do jogador."""

    grab_state = "held"

    def __init__(self) -> None:
        self.botoes: frozenset[str] = frozenset()

    def snapshot(self) -> Any:
        return SimpleNamespace(
            lx=128, ly=128, rx=128, ry=128, l2_raw=0, r2_raw=0, buttons_pressed=self.botoes
        )


class _Mesa:
    """O P1 no `dispatch_gamepad` e o P2 no `forward_all`, um `HotkeyManager` só."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, mascara: str) -> None:
        monkeypatch.setattr(gp, "_reconciliar_launch", lambda d: None)
        monkeypatch.setattr(gp, "_avisar_troca_de_modo", lambda d: None)
        self.pad_p1, self.no_p1 = _pad(mascara)
        self.pad_p2, self.no_p2 = _pad(mascara)
        self.daemon = SimpleNamespace(
            store=SimpleNamespace(),
            controller=SimpleNamespace(primary_uniq=P1),
            config=SimpleNamespace(coop_enabled=True, gamepad_flavor=mascara),
            identity_registry=None,
            _gamepad_device=self.pad_p1,
            _coop_manager=None,
            _hotkey_manager=HotkeyManager(),
        )
        self.coop = CoopManager(self.daemon)
        self.leitor_p2 = _Leitor()
        self.coop._players[P2] = _SecondaryPlayer(
            identity=P2,
            evdev_path="/dev/input/event9",
            reader=cast(Any, self.leitor_p2),
            player_index=2,
            vpad=self.pad_p2,
        )

    def p1(self, *botoes: str) -> None:
        estado = SimpleNamespace(
            raw_lx=128, raw_ly=128, raw_rx=128, raw_ry=128, l2_raw=0, r2_raw=0
        )
        gp.dispatch_gamepad(self.daemon, estado, frozenset(botoes))

    def p2(self, *botoes: str) -> None:
        self.leitor_p2.botoes = frozenset(botoes)
        self.coop.forward_all()


@pytest.mark.parametrize("mascara", MASCARAS)
@pytest.mark.parametrize("gesto", GESTOS, ids=lambda g: "+".join(g))
def test_o_membro_do_gesto_nao_chega_ao_pad_do_p1_nem_do_p2(
    monkeypatch: pytest.MonkeyPatch, mascara: str, gesto: tuple[str, str]
) -> None:
    mesa = _Mesa(monkeypatch, mascara)
    ps, membro = gesto

    mesa.p1(ps, membro)
    mesa.p2(ps, membro)

    assert not _apertou(mesa.pad_p1, mesa.no_p1, membro), f"o {membro} do P1 chegou ao jogo"
    assert not _apertou(mesa.pad_p2, mesa.no_p2, membro), f"o {membro} do P2 chegou ao jogo"
    assert _apertou(mesa.pad_p1, mesa.no_p1, "ps"), "o PS sozinho segue como hoje"
    assert _apertou(mesa.pad_p2, mesa.no_p2, "ps"), "o PS sozinho segue como hoje"


@pytest.mark.parametrize("mascara", MASCARAS)
def test_soltar_o_ps_e_apertar_o_r3_sozinho_leva_o_r3(
    monkeypatch: pytest.MonkeyPatch, mascara: str
) -> None:
    mesa = _Mesa(monkeypatch, mascara)
    for jogador in (mesa.p1, mesa.p2):
        jogador("ps", "r3")
        jogador("r3")  # o PS soltou antes: o R3 ainda é do gesto
        jogador()
        jogador("r3")

    for pad, no in ((mesa.pad_p1, mesa.no_p1), (mesa.pad_p2, mesa.no_p2)):
        codigo = pad._resolve_evdev("r3", ecodes)
        assert codigo is not None
        assert no.teclas.count((codigo, 1)) == 1, (
            f"o R3 apertado sozinho tem de chegar uma vez, e só ele: {no.teclas}"
        )


@pytest.mark.parametrize("mascara", MASCARAS)
def test_o_gesto_do_p2_nao_cala_o_r3_do_p1(monkeypatch: pytest.MonkeyPatch, mascara: str) -> None:
    mesa = _Mesa(monkeypatch, mascara)

    mesa.p2("ps", "r3")
    mesa.p1("r3")

    assert _apertou(mesa.pad_p1, mesa.no_p1, "r3"), "o gesto do P2 calou o R3 do P1"
    assert not _apertou(mesa.pad_p2, mesa.no_p2, "r3")


@pytest.mark.parametrize("mascara", MASCARAS)
def test_o_gesto_do_p1_nao_cala_o_r3_do_p2(monkeypatch: pytest.MonkeyPatch, mascara: str) -> None:
    mesa = _Mesa(monkeypatch, mascara)

    mesa.p1("ps", "r3")
    mesa.p2("r3")

    assert _apertou(mesa.pad_p2, mesa.no_p2, "r3"), "o gesto do P1 calou o R3 do P2"
    assert not _apertou(mesa.pad_p1, mesa.no_p1, "r3")


def test_o_desktop_le_o_latch_do_primario() -> None:
    """O teclado e o mouse do P1 seguem lendo o mesmo latch, na chave do P1."""
    mgr = HotkeyManager()
    assert mgr.combo_buttons_active({"ps", "r3"}, de=P2) == {"ps", "r3"}
    assert mgr.combo_buttons_active({"r3"}, de=P1) == frozenset()
    assert mgr.combo_buttons_active({"r3"}, de=P2) == {"r3"}


@pytest.mark.parametrize("mascara", MASCARAS)
def test_o_latch_atravessa_o_tique_dos_atalhos(
    monkeypatch: pytest.MonkeyPatch, mascara: str
) -> None:
    """O laço de verdade: entre um tique e outro, os atalhos esquecem quem não leram.

    O `observar_os_atalhos` chama o `soltar_quem_saiu` com as chaves que ELE leu
    (o `primary_uniq` do P1 e o MAC de cada jogador do co-op). Se a chave do
    latch no pad não for a mesma, o latch some a cada tique, e o R3 que ainda
    está apertado depois de o PS soltar chega ao jogo.
    """
    from hefesto_dualsense4unix.daemon.subsystems.poll import observar_os_atalhos

    mesa = _Mesa(monkeypatch, mascara)
    mesa.daemon._coop_manager = mesa.coop
    agora = 1000.0
    for botoes in (("ps", "r3"), ("r3",), (), ("r3",)):
        mesa.p1(*botoes)
        mesa.p2(*botoes)
        observar_os_atalhos(mesa.daemon, frozenset(botoes), now=agora)
        agora += 0.5

    for pad, no in ((mesa.pad_p1, mesa.no_p1), (mesa.pad_p2, mesa.no_p2)):
        codigo = pad._resolve_evdev("r3", ecodes)
        assert codigo is not None
        assert no.teclas.count((codigo, 1)) == 1, (
            f"o latch não atravessou o tique dos atalhos: {no.teclas}"
        )
