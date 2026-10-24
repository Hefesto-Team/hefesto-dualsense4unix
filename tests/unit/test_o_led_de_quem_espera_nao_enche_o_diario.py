"""O-LED-DE-QUEM-ESPERA-NO-LUGAR-NAO-ENCHE-O-DIARIO-01: quem espera no lugar não enche o diário.

Enquanto um jogador espera no lugar guardado (D-2410-O-LUGAR-GUARDADO-ESPERA-NOS-QUATRO),
o `_retry_spawn` faz o ciclo cheio a cada tique, e o ciclo cheio termina no
`_apply_coop_player_leds`. No caminho do sysfs (sem a camada do co-op), o ausente
não tem nó, e o aviso `coop_player_led_indisponivel` saía uma vez por tique.
A régua roda a mesa mista, de dois a quatro jogadores, e conta as linhas.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from collections.abc import MutableMapping
from typing import Any

import pytest
import structlog

from hefesto_dualsense4unix.core.led_control import player_led_pattern
from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager

P1 = "aabbcc000011"
P2 = "aabbcc000022"
P3 = "aabbcc000033"
P4 = "aabbcc000044"
PRAZO_S = 30.0
TIQUES = 30
AVISO = "coop_player_led_indisponivel"


class _Leitor:
    def __init__(self, device_path: Any = None, target_uniq: str | None = None) -> None:
        self.device_path = device_path
        self.grab_state = "off"
        self.snap = SimpleNamespace(
            lx=128, ly=128, rx=128, ry=128, l2_raw=0, r2_raw=0,
            buttons_pressed=frozenset(), apertos={},
        )

    def start(self) -> bool:
        return True

    def set_grab(self, grab: bool) -> bool:
        self.grab_state = "held" if grab else "off"
        return True

    def stop(self) -> None:
        pass

    def request_reopen(self, reason: str = "") -> None:
        pass

    def snapshot(self) -> Any:
        return self.snap


class _Vpad:
    def __init__(self) -> None:
        self.flavor = ""

    @classmethod
    def for_flavor(cls, flavor: str, *, rumble_sink: Any = None) -> _Vpad:
        inst = cls()
        inst.flavor = flavor
        return inst

    def start(self) -> bool:
        return True

    def stop(self) -> None:
        pass

    def forward_analog(self, **kw: int) -> None:
        pass

    def forward_buttons(self, pressed: frozenset[str]) -> None:
        pass


class _No:
    """O nó de LED do sysfs de um controle presente: guarda o que lhe escreveram."""

    def __init__(self, escritas: list[tuple[str, tuple[bool, ...]]], mac: str) -> None:
        self.escritas = escritas
        self.mac = mac

    def set_players(self, bits: tuple[bool, bool, bool, bool, bool]) -> bool:
        self.escritas.append((self.mac, tuple(bits)))
        return True


class _Registro:
    def __init__(self, relogio: list[float], macs: list[str]) -> None:
        self.relogio = relogio
        self.slots = {mac: i + 1 for i, mac in enumerate(macs)}
        self.ligados: set[str] = set(self.slots)
        self.saiu_em: dict[str, float] = {}

    def slot_for(self, uniq: str, assign: bool = True) -> int | None:
        return self.slots.get(uniq)

    def o_lugar_espera(self, uniq: str | None) -> bool:
        if uniq in self.ligados:
            return True
        saiu = self.saiu_em.get(uniq or "")
        return saiu is not None and self.relogio[0] - saiu < PRAZO_S


class _Mesa:
    """Os nós de evdev e de LED de cada controle, e um watch que só dispara na mudança."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, nos: dict[str, str]) -> None:
        self.nos = dict(nos)
        self.leds = set(nos)
        self.escritas: list[tuple[str, tuple[bool, ...]]] = []
        self.mudou = [True]
        self.relogio = [0.0]
        self.registro = _Registro(self.relogio, list(nos))
        self.em_troca: set[str] = set()
        controller = SimpleNamespace(
            _evdev=SimpleNamespace(_device_path=Path(nos[P1])),
            primary_uniq=P1,
            _desired=SimpleNamespace(player_leds=None),
            set_player_leds=lambda bits: None,
            force_rumble_stop=lambda uniq: None,
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

        def poll(_self: Any) -> bool:
            mudou, self.mudou[0] = self.mudou[0], False
            return mudou

        monkeypatch.setattr("hefesto_dualsense4unix.core.evdev_reader.InputDirWatch.poll", poll)
        monkeypatch.setattr("hefesto_dualsense4unix.core.evdev_reader.EvdevReader", _Leitor)
        monkeypatch.setattr(
            "hefesto_dualsense4unix.integrations.uinput_gamepad.UinputGamepad", _Vpad
        )
        monkeypatch.setattr(
            "hefesto_dualsense4unix.core.evdev_reader.discover_dualsense_evdevs",
            lambda: {mac: Path(p) for mac, p in self.nos.items()},
        )
        monkeypatch.setattr(
            "hefesto_dualsense4unix.core.sysfs_leds.discover",
            lambda: {mac: _No(self.escritas, mac) for mac in self.leds},
        )
        self.mgr = CoopManager(self.daemon)
        self.mgr.sync()

    def sai(self, *macs: str) -> None:
        for mac in macs:
            self.nos.pop(mac)
            self.leds.discard(mac)
            self.registro.ligados.discard(mac)
            self.registro.saiu_em[mac] = self.relogio[0]
        self.mudou[0] = True
        self.mgr.sync()

    def volta(self, mac: str, no: str) -> None:
        self.nos[mac] = no
        self.leds.add(mac)
        self.registro.ligados.add(mac)
        self.registro.saiu_em.pop(mac, None)
        self.mudou[0] = True
        self.mgr.sync()

    def tiques(self, n: int) -> None:
        for _ in range(n):
            self.relogio[0] += 0.5
            self.mgr.sync()


def _avisos(registros: list[MutableMapping[str, Any]]) -> list[str]:
    return [str(r.get("identity")) for r in registros if r.get("event") == AVISO]


QUATRO = {P1: "/dev/input/event5", P2: "/dev/input/event7",
          P3: "/dev/input/event9", P4: "/dev/input/event11"}

#: (rótulo da mesa, os nós, quem espera). O laço do co-op não tem ramo de
#: transporte; o rótulo diz a mesa, e a régua prova que a cura não ganha um.
MATRIZ = [
    ("p1-usb,p2-bt,p3-usb,p4-bt", QUATRO, (P2,)),
    ("tres-adaptadores-e-um-no-cabo", QUATRO, (P4,)),
    ("todos-no-cabo", QUATRO, (P3,)),
    ("todos-no-bt", QUATRO, (P2, P3)),
    ("dois-na-mesa", {P1: QUATRO[P1], P2: QUATRO[P2]}, (P2,)),
]


@pytest.mark.parametrize(("mesa", "nos", "esperam"), MATRIZ, ids=[m[0] for m in MATRIZ])
def test_quem_espera_trinta_tiques_nao_repete_o_aviso_do_led(
    monkeypatch: pytest.MonkeyPatch, mesa: str, nos: dict[str, str], esperam: tuple[str, ...]
) -> None:
    m = _Mesa(monkeypatch, nos)
    assert all(m.mgr._players[mac].vpad is not None for mac in esperam), mesa
    assert {mac for mac, _ in m.escritas} >= set(esperam), "a mesa nasceu sem LED"
    m.escritas.clear()
    with structlog.testing.capture_logs() as registros:
        m.sai(*esperam)
        m.tiques(TIQUES)
    assert all(m.mgr._players[mac].a_espera for mac in esperam), mesa
    avisos = _avisos(registros)
    for mac in esperam:
        assert avisos.count(mac) == 0, (
            f"{mesa}: {avisos.count(mac)} avisos de LED de {mac} em {TIQUES} tiques de espera; "
            f"o lugar que espera não tem lâmpada a acender, e a espera já se diz no diário"
        )
    assert not [mac for mac, _ in m.escritas if mac in esperam], (
        f"{mesa}: o lugar que espera recebeu escrita de LED sem ter lâmpada")


def test_quem_volta_ao_lugar_acende_o_numero_dele(monkeypatch: pytest.MonkeyPatch) -> None:
    m = _Mesa(monkeypatch, QUATRO)
    m.sai(P2)
    m.tiques(10)
    m.escritas.clear()
    with structlog.testing.capture_logs() as registros:
        m.volta(P2, "/dev/input/event40")
    assert not m.mgr._players[P2].a_espera
    numero = m.mgr.numeros_de_jogador()[P2]
    assert (P2, tuple(player_led_pattern(numero))) in m.escritas, m.escritas
    assert not _avisos(registros)


def test_na_troca_de_transporte_o_aviso_sai_uma_vez(monkeypatch: pytest.MonkeyPatch) -> None:
    """A troca de transporte, sem o nó novo ainda, segura o vpad e tem o mesmo padrão."""
    m = _Mesa(monkeypatch, QUATRO)
    m.em_troca.add(P2)
    with structlog.testing.capture_logs() as registros:
        m.nos.pop(P2)
        m.leds.discard(P2)
        m.mudou[0] = True
        m.mgr.sync()
        m.tiques(TIQUES)
    assert _avisos(registros).count(P2) == 1, _avisos(registros)
    with structlog.testing.capture_logs() as registros:
        m.nos[P2] = "/dev/input/event50"
        m.leds.add(P2)
        m.mudou[0] = True
        m.mgr.sync()
        m.em_troca.discard(P2)
        m.leds.discard(P2)
        m.mudou[0] = True
        m.mgr.sync()
    assert _avisos(registros).count(P2) == 1, (
        "o nó que voltou e sumiu de novo é outra borda, e o aviso tem de sair outra vez")


def _a_lampada_do_registro(m: _Mesa) -> None:
    """O `numero_da_lampada` do registro de verdade: o ausente não tem número a acender."""
    m.registro.numero_da_lampada = (  # type: ignore[attr-defined]
        lambda uniq, assign=True: m.registro.slots.get(uniq)
        if uniq in m.registro.ligados else None
    )


def _planos(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    from hefesto_dualsense4unix.daemon.subsystems import coop

    feitos: list[list[str]] = []
    original = coop.planejar_a_ordem

    def planejar(*args: Any, **kwargs: Any) -> tuple[list[str], bool]:
        recriar, inteira = original(*args, **kwargs)
        feitos.append(list(recriar))
        return recriar, inteira

    monkeypatch.setattr(coop, "planejar_a_ordem", planejar)
    return feitos


@pytest.mark.parametrize(("mesa", "nos", "esperam"), MATRIZ, ids=[m[0] for m in MATRIZ])
def test_a_ordem_segue_enquanto_alguem_espera_no_lugar(
    monkeypatch: pytest.MonkeyPatch, mesa: str, nos: dict[str, str], esperam: tuple[str, ...]
) -> None:
    """Com a carta do ausente em ``None``, o `_ordenar` saía cedo e ninguém se ordenava."""
    m = _Mesa(monkeypatch, nos)
    _a_lampada_do_registro(m)
    m.sai(*esperam)
    feitos = _planos(monkeypatch)
    m.mgr._ordenar(None)
    assert feitos == [[]], f"{mesa}: a ordem não foi planejada com quem espera ({feitos})"


def test_o_vpad_de_quem_espera_nunca_e_recriado_pela_ordem(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Quem espera fica parado e vivo no lugar dele no jogo, mesmo com a ordem fora."""
    m = _Mesa(monkeypatch, QUATRO)
    _a_lampada_do_registro(m)
    m.sai(P2)
    vpad = m.mgr._players[P2].vpad
    # a carta do P4 menor que a de quem espera: fora dos fixos, o P2 entraria no recriar
    m.registro.slots[P4] = 1
    feitos = _planos(monkeypatch)
    m.mgr._ordenar(None)
    assert feitos and all(P2 not in recriar for recriar in feitos), feitos
    assert m.mgr._players[P2].vpad is vpad and m.mgr._players[P2].a_espera


@pytest.mark.parametrize("p3_slot", [1, 3, 4])
def test_sem_o_jogo_na_autoridade_a_ordem_nao_recria_quem_espera(
    monkeypatch: pytest.MonkeyPatch, p3_slot: int
) -> None:
    """O jogo soltou a autoridade com o P2 à espera, antes do `sync` soltá-lo.

    Sem a autoridade os `fixos` ficam vazios, como o posto vago do P1; a carta
    de quem espera também não vale, e a ordem sai cedo em vez de recriar o vpad.
    """
    m = _Mesa(monkeypatch, QUATRO)
    _a_lampada_do_registro(m)
    m.sai(P2)
    vpad = m.mgr._players[P2].vpad
    m.registro.slots[P4] = 1
    m.registro.slots[P3] = p3_slot
    m.daemon.display_authority = "unknown"
    feitos = _planos(monkeypatch)
    m.mgr._ordenar(None)
    assert all(P2 not in recriar for recriar in feitos), feitos
    assert m.mgr._players[P2].vpad is vpad and m.mgr._players[P2].a_espera
