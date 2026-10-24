"""O-LUGAR-GUARDADO-ESPERA-NO-VPAD-DE-CADA-JOGADOR-01: o P2, o P3 e o P4 que caem esperam no vpad.

A `D-2409` guardava o boneco só do P1: o secundário que saía da mesa caía no
`teardown` e o jogo perdia o vpad dele num soluço do rádio. A régua roda a mesa
mista (cabo e rádio, de um a quatro jogadores): o controle sai, volta com nó
novo, e o vpad é o MESMO objeto, parado no quadro neutro enquanto esperou.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, ClassVar

import pytest

from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager

P1 = "aabbcc000011"
P2 = "aabbcc000022"
P3 = "aabbcc000033"
P4 = "aabbcc000044"
PRAZO_S = 30.0


class _Leitor:
    criados: ClassVar[list[_Leitor]] = []

    def __init__(self, device_path: Any = None, target_uniq: str | None = None) -> None:
        self.device_path = device_path
        self.target_uniq = target_uniq
        self.parado = False
        self.reabertos: list[str] = []
        self.grab_state = "off"
        self.snap = SimpleNamespace(
            lx=255, ly=0, rx=128, ry=128, l2_raw=200, r2_raw=0,
            buttons_pressed=frozenset({"cross"}), apertos={},
        )
        type(self).criados.append(self)

    def start(self) -> bool:
        return True

    def set_grab(self, grab: bool) -> bool:
        self.grab_state = "held" if grab else "off"
        return True

    def stop(self) -> None:
        self.parado = True

    def request_reopen(self, reason: str = "") -> None:
        self.reabertos.append(reason)

    def snapshot(self) -> Any:
        return self.snap


class _Vpad:
    criados: ClassVar[list[_Vpad]] = []

    def __init__(self) -> None:
        self.paradas = 0
        self.flavor = ""
        self.analog: list[dict[str, int]] = []
        self.buttons: list[frozenset[str]] = []
        self.rumble_sink: Any = None

    @classmethod
    def for_flavor(cls, flavor: str, *, rumble_sink: Any = None) -> _Vpad:
        inst = cls()
        inst.flavor = flavor
        inst.rumble_sink = rumble_sink
        cls.criados.append(inst)
        return inst

    def start(self) -> bool:
        return True

    def stop(self) -> None:
        self.paradas += 1

    def forward_analog(self, **kw: int) -> None:
        self.analog.append(kw)

    def forward_buttons(self, pressed: frozenset[str]) -> None:
        self.buttons.append(pressed)


class _Registro:
    """O dono do número e do prazo: cada um que sai guarda o lugar por PRAZO_S."""

    def __init__(self, relogio: list[float]) -> None:
        self.relogio = relogio
        self.slots = {P1: 1, P2: 2, P3: 3, P4: 4}
        self.ligados: set[str] = set(self.slots)
        self.saiu_em: dict[str, float] = {}

    def slot_for(self, uniq: str, assign: bool = True) -> int | None:
        return self.slots.get(uniq)

    def sair(self, uniq: str) -> None:
        self.ligados.discard(uniq)
        self.saiu_em[uniq] = self.relogio[0]

    def voltar(self, uniq: str) -> None:
        self.ligados.add(uniq)
        self.saiu_em.pop(uniq, None)

    def o_lugar_espera(self, uniq: str | None) -> bool:
        if uniq in self.ligados:
            return True
        saiu = self.saiu_em.get(uniq or "")
        return saiu is not None and self.relogio[0] - saiu < PRAZO_S


class _Mesa:
    """A mesa de mentira: os nós de cada controle, o registro e o daemon."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, nos: dict[str, str]) -> None:
        self.monkeypatch = monkeypatch
        self.nos = dict(nos)
        self.relogio = [0.0]
        self.registro = _Registro(self.relogio)
        self.paradas_de_rumble: list[str] = []
        self.em_troca: set[str] = set()
        controller = SimpleNamespace(
            _evdev=SimpleNamespace(_device_path=Path(nos[P1])),
            primary_uniq=P1,
            _desired=SimpleNamespace(player_leds=None),
            set_player_leds=lambda bits: None,
            force_rumble_stop=self.paradas_de_rumble.append,
            em_troca_de_transporte=lambda uniq: uniq in self.em_troca,
        )
        self.daemon = SimpleNamespace(
            config=SimpleNamespace(coop_enabled=True, gamepad_flavor="dualsense"),
            _gamepad_device=object(),
            controller=controller,
            _coop_manager=None,
            identity_registry=self.registro,
            display_authority="game",
        )
        monkeypatch.setattr(
            "hefesto_dualsense4unix.core.evdev_reader.discover_dualsense_evdevs",
            lambda: {mac: Path(p) for mac, p in self.nos.items()},
        )
        self.mgr = CoopManager(self.daemon)
        self.mgr.sync()

    def sai(self, *macs: str) -> None:
        for mac in macs:
            self.nos.pop(mac)
            self.registro.sair(mac)
        self.mgr.sync()

    def volta(self, mac: str, no: str) -> None:
        self.nos[mac] = no
        self.registro.voltar(mac)
        self.mgr.sync()

    def passa(self, segundos: float) -> None:
        self.relogio[0] += segundos
        self.mgr.sync()


@pytest.fixture
def mesa_de_mentira(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    _Leitor.criados = []
    _Vpad.criados = []
    monkeypatch.setattr(
        "hefesto_dualsense4unix.core.evdev_reader.InputDirWatch.poll", lambda self: True
    )
    monkeypatch.setattr("hefesto_dualsense4unix.core.evdev_reader.EvdevReader", _Leitor)
    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.uinput_gamepad.UinputGamepad", _Vpad
    )
    monkeypatch.setattr("hefesto_dualsense4unix.core.sysfs_leds.discover", lambda: {})
    return monkeypatch


MESA_MISTA = {P1: "/dev/input/event5", P2: "/dev/input/event7",
              P3: "/dev/input/event9", P4: "/dev/input/event11"}

#: (rótulo da mesa, quem sai junto, quem fica olhando). O transporte de cada um
#: está no rótulo: o laço do co-op não tem ramo de transporte, e a régua prova
#: que a cura não ganha um.
MATRIZ = [
    ("p1-usb,p2-bt,p3-usb,p4-bt", (P2, P3), (P4,)),
    ("tres-adaptadores-e-um-no-cabo", (P4,), (P2, P3)),
    ("todos-no-cabo", (P3,), (P2, P4)),
]


@pytest.mark.parametrize(("mesa", "saem", "ficam"), MATRIZ, ids=[m[0] for m in MATRIZ])
def test_quem_cai_e_volta_no_prazo_fica_no_mesmo_vpad(
    mesa_de_mentira: pytest.MonkeyPatch, mesa: str, saem: tuple[str, ...],
    ficam: tuple[str, ...],
) -> None:
    m = _Mesa(mesa_de_mentira, MESA_MISTA)
    mgr = m.mgr
    vpads = {mac: mgr._players[mac].vpad for mac in (P2, P3, P4)}
    leitores = {mac: mgr._players[mac].reader for mac in (P2, P3, P4)}
    numeros = mgr.player_indexes()
    mgr.forward_all()  # o Cruz e o stick torto chegam ao vpad antes da queda

    m.sai(*saem)
    for mac in saem:
        jogador = mgr._players[mac]
        assert jogador.a_espera, f"{mesa}: {mac} caiu no teardown"
        assert jogador.vpad is vpads[mac]
        assert vpads[mac].paradas == 0
        assert leitores[mac].parado
        assert vpads[mac].buttons[-1] == frozenset()
        assert vpads[mac].analog[-1] == dict(lx=128, ly=128, rx=128, ry=128, l2=0, r2=0)
        assert mac in m.paradas_de_rumble
    neutros = {mac: len(vpads[mac].buttons) for mac in saem}

    m.passa(1.0)
    mgr.forward_all()
    for mac in saem:
        # Um quadro neutro só: o tique não volta a escrever no vpad que espera.
        assert len(vpads[mac].buttons) == neutros[mac]
        assert mac not in mgr.live_snapshots()

    for i, mac in enumerate(saem):
        m.volta(mac, f"/dev/input/event{30 + i}")
        jogador = mgr._players[mac]
        assert jogador.vpad is vpads[mac]
        assert vpads[mac].paradas == 0
        assert not jogador.a_espera
        assert jogador.evdev_path == f"/dev/input/event{30 + i}"
        assert jogador.reader is not leitores[mac]
        assert str(jogador.reader.device_path) == f"/dev/input/event{30 + i}"
        assert jogador.reader.target_uniq == mac
        assert jogador.reader.grab_state == "held"

    for mac in ficam:
        assert mgr._players[mac].vpad is vpads[mac]
        assert mgr._players[mac].reader is leitores[mac]
    assert mgr.player_indexes() == numeros
    assert all(v.paradas == 0 for v in vpads.values())
    assert len(_Vpad.criados) == 3


def test_todos_no_radio_o_prazo_de_cada_um_corre_sozinho(
    mesa_de_mentira: pytest.MonkeyPatch,
) -> None:
    m = _Mesa(mesa_de_mentira, MESA_MISTA)
    mgr = m.mgr
    vpad_p3 = mgr._players[P3].vpad
    vpad_p4 = mgr._players[P4].vpad

    m.sai(P2)
    m.passa(26.0)
    m.sai(P4)
    assert mgr._players[P2].a_espera and mgr._players[P4].a_espera

    m.passa(5.0)  # o prazo do P2 venceu (31 s); o do P4 tem 5 s
    assert P2 not in mgr._players
    assert mgr._players[P4].a_espera and mgr._players[P4].vpad is vpad_p4
    assert vpad_p4.paradas == 0
    # O P3 não desce para o 2: o vpad dele é o mesmo e o número também.
    assert mgr._players[P3].vpad is vpad_p3 and vpad_p3.paradas == 0
    assert mgr.player_indexes()[P3] == 3

    m.volta(P4, "/dev/input/event40")
    assert mgr._players[P4].vpad is vpad_p4 and not mgr._players[P4].a_espera
    assert mgr.player_indexes()[P4] == 4


def test_o_prazo_vencido_e_o_teardown(mesa_de_mentira: pytest.MonkeyPatch) -> None:
    m = _Mesa(mesa_de_mentira, MESA_MISTA)
    vpad = m.mgr._players[P2].vpad
    m.sai(P2)
    assert m.mgr._players[P2].a_espera
    m.passa(PRAZO_S + 1)
    assert P2 not in m.mgr._players
    assert vpad.paradas == 1


def test_sem_a_autoridade_do_jogo_o_teardown_e_na_hora(
    mesa_de_mentira: pytest.MonkeyPatch,
) -> None:
    m = _Mesa(mesa_de_mentira, MESA_MISTA)
    m.daemon.display_authority = "unknown"
    vpad = m.mgr._players[P2].vpad
    m.sai(P2)
    assert P2 not in m.mgr._players
    assert vpad.paradas == 1


def test_o_jogo_que_fecha_solta_quem_esperava(mesa_de_mentira: pytest.MonkeyPatch) -> None:
    m = _Mesa(mesa_de_mentira, MESA_MISTA)
    vpad = m.mgr._players[P3].vpad
    m.sai(P3)
    assert m.mgr._players[P3].a_espera
    m.daemon.display_authority = "desktop"
    m.passa(1.0)
    assert P3 not in m.mgr._players
    assert vpad.paradas == 1


def test_a_troca_de_transporte_segue_no_dono_dela(mesa_de_mentira: pytest.MonkeyPatch) -> None:
    m = _Mesa(mesa_de_mentira, MESA_MISTA)
    leitor = m.mgr._players[P2].reader
    m.em_troca.add(P2)
    m.nos[P2] = "/dev/input/event50"
    m.mgr.sync()
    jogador = m.mgr._players[P2]
    assert not jogador.a_espera
    assert jogador.reader is leitor and leitor.reabertos == ["troca_de_transporte"]
    assert not leitor.parado


def test_um_so_o_posto_do_p1_e_a_mesma_pergunta(mesa_de_mentira: pytest.MonkeyPatch) -> None:
    """Com um só, o P1: a pergunta do posto é a de antes, nas oito combinações."""
    m = _Mesa(mesa_de_mentira, {P1: "/dev/input/event5"})
    mgr = m.mgr

    def de_antes(uniq: str) -> bool:
        if not mgr.should_be_active() or not mgr._jogo_com_a_autoridade():
            return False
        pergunta = getattr(m.registro, "o_lugar_espera", None)
        return callable(pergunta) and bool(pergunta(uniq))

    for coop in (True, False):
        for autoridade in ("game", "desktop"):
            for espera in (True, False):
                m.daemon.config.coop_enabled = coop
                m.daemon.display_authority = autoridade
                m.registro.ligados = {P1} if espera else set()
                m.registro.saiu_em = {}
                assert mgr.o_posto_do_p1_espera(P1) is de_antes(P1)
                assert mgr.o_lugar_do_jogador_espera(P1) is de_antes(P1)


def test_quem_espera_no_lugar_nao_segura_os_atalhos_da_vaga(
    mesa_de_mentira: pytest.MonkeyPatch,
) -> None:
    """Na vaga do posto do P1, os atalhos vão ao próximo SENTADO: o P2 que espera não tem mão."""
    from hefesto_dualsense4unix.daemon.subsystems import poll

    m = _Mesa(mesa_de_mentira, MESA_MISTA)
    m.daemon._coop_manager = m.mgr
    m.daemon.controller._posto_vago_de = P1
    assert poll._o_proximo_da_fila(m.daemon) == P2
    m.sai(P2)
    assert m.mgr.quem_espera_no_lugar() == frozenset({P2})
    assert m.mgr.numeros_de_jogador().get(P2) == 2, "quem espera guarda o número"
    assert poll._o_proximo_da_fila(m.daemon) == P3
    m.volta(P2, "/dev/input/event60")
    assert poll._o_proximo_da_fila(m.daemon) == P2


def test_o_prazo_vencido_solta_o_vpad_mesmo_com_o_laco_adiado(
    mesa_de_mentira: pytest.MonkeyPatch,
) -> None:
    """O laço do co-op adia enquanto o primário não tem MAC; o vpad de quem venceu sai igual.

    Sem isso, o P2 cujo prazo venceu seguiria de pé no jogo enquanto o posto do P1 não
    resolve o MAC (`coop_sync_defer_primary_sem_mac`): um boneco fantasma no lugar dele.
    """
    m = _Mesa(mesa_de_mentira, MESA_MISTA)
    vpad = m.mgr._players[P2].vpad
    m.sai(P2)
    assert m.mgr._players[P2].a_espera
    m.daemon.controller.primary_uniq = None
    m.passa(PRAZO_S + 1)
    assert P2 not in m.mgr._players, "o prazo venceu e o vpad dele ficou no jogo"
    assert vpad.paradas == 1
