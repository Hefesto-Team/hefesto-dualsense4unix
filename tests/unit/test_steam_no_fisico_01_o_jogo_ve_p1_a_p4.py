"""STEAM-NO-FISICO-01 — o jogo vê a ordem da mesa: os vpads nascem P1→P4.

A terceira obrigação da decisão dela de 23/09/2026: *"O P1 do Hefesto é o
jogador 1 do jogo: os controles virtuais chegam ao jogo na ordem P1→P4. Meça
como o SDL e o Proton numeram (pela ordem de criação do nó? pelo índice do
hidraw?) e faça a criação obedecer ao número da aba Controles."*

A MEDIÇÃO, no fonte (`libsdl-org/SDL@0c8feecc`): o SDL dá a cada joystick novo
o menor índice livre (`SDL_joystick.c`, `SDL_PrivateJoystickAdded` →
`SDL_FindFreePlayerIndex`); a enumeração inicial do HIDAPI é o
`udev_enumerate_scan_devices` do subsistema `hidraw` (`linux/hid.c`), que o
udev ordena pelo syspath — e o syspath de um vpad uhid leva o número de
sequência do HID, isto é, a ORDEM DE CRIAÇÃO. O índice do `/dev/hidrawN` não
entra na conta. O winebus do Proton enumera pelo mesmo udev.

Logo: o jogo numera os vpads na ordem em que eles nascem. O co-op os criava na
ordem do `eventN` (a ordem em que o kernel viu os controles), e o grab ou a
calibração que atrasavam um jogador deixavam o seguinte passar na frente.

AS MORDIDAS, exercidas e devolvidas: (1) o `sync` na ordem de `want` cria o P4
antes do P2; (2) o `_promote_pending` sem a espera deixa o P3 nascer antes do
P2 de grab pendente; (3) sem o prazo, o P3 espera o P2 para sempre.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any, ClassVar

import pytest

from hefesto_dualsense4unix.daemon.subsystems import coop as coop_mod
from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager

P1 = "aabbcc000001"
P2 = "aabbcc000002"
P3 = "aabbcc000003"
P4 = "aabbcc000004"

#: A carta de cada um na aba Controles.
CARTAS = {P1: 1, P2: 2, P3: 3, P4: 4}

#: A ordem em que o kernel os viu (o `eventN`): nada a ver com a carta.
EVDEVS = {
    P1: "/dev/input/event20",
    P4: "/dev/input/event21",
    P2: "/dev/input/event22",
    P3: "/dev/input/event23",
}


class _Leitor:
    """Leitor evdev falso; `pendentes` são os que o grab deixa em "pending"."""

    pendentes: ClassVar[set[str]] = set()

    def __init__(self, device_path: Any = None, target_uniq: str | None = None) -> None:
        self.device_path = device_path
        self.target_uniq = target_uniq
        self.grab_state = "off"
        self.snap = SimpleNamespace(
            lx=128, ly=128, rx=128, ry=128, l2_raw=0, r2_raw=0,
            buttons_pressed=frozenset(),
        )

    def start(self) -> bool:
        return True

    def set_grab(self, grab: bool) -> bool:
        if grab and self.target_uniq in type(self).pendentes:
            self.grab_state = "pending"
            return True
        self.grab_state = "held" if grab else "off"
        return True

    def stop(self) -> None:
        return None

    def snapshot(self) -> Any:
        return self.snap


class _Vpad:
    def __init__(self, identidade: str) -> None:
        self.identidade = identidade
        self.flavor = "dualsense"

    def stop(self) -> None:
        return None

    def forward_analog(self, **_kw: int) -> None:
        return None

    def forward_buttons(self, _pressed: frozenset[str]) -> None:
        return None

    def pump_ff(self) -> None:
        return None


@pytest.fixture
def nascimentos(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """A ordem em que os vpads nascem — que é a ordem que o jogo vê."""
    ordem: list[str] = []
    _Leitor.pendentes = set()
    monkeypatch.setattr(
        "hefesto_dualsense4unix.core.evdev_reader.InputDirWatch.poll", lambda self: True
    )
    monkeypatch.setattr("hefesto_dualsense4unix.core.evdev_reader.EvdevReader", _Leitor)
    monkeypatch.setattr(
        "hefesto_dualsense4unix.core.evdev_reader.discover_dualsense_evdevs",
        lambda: dict(EVDEVS),
    )

    def _nasce(_flavor: Any, *, identity: str | None = None, **_kw: Any) -> _Vpad:
        ordem.append(str(identity))
        return _Vpad(str(identity))

    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.virtual_pad.make_virtual_pad", _nasce
    )
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.launch_env.materialize_launch_env",
        lambda daemon: None,
    )
    monkeypatch.setattr("hefesto_dualsense4unix.core.sysfs_leds.discover", lambda: {})
    return ordem


def _daemon(cartas: dict[str, int] | None = CARTAS) -> Any:
    registro = (
        SimpleNamespace(numero_da_lampada=lambda mac, assign=False: cartas.get(mac))
        if cartas is not None
        else None
    )
    return SimpleNamespace(
        config=SimpleNamespace(coop_enabled=True, gamepad_flavor="dualsense"),
        _gamepad_device=object(),
        controller=SimpleNamespace(
            primary_uniq=P1,
            _evdev=SimpleNamespace(_device_path="/dev/input/event20"),
        ),
        identity_registry=registro,
        _coop_manager=None,
    )


class TestONascimentoSegueACarta:
    def test_a_mesa_cheia_nasce_na_ordem_da_carta(self, nascimentos: list[str]) -> None:
        """A MORDIDA (1): na ordem do `eventN` nasceria P4, P2, P3 — e o jogo
        chamaria o P4 dela de «jogador 2»."""
        mgr = CoopManager(_daemon())

        mgr.sync()

        assert nascimentos == [P2, P3, P4]

    def test_sem_registro_a_ordem_e_a_de_sempre(self, nascimentos: list[str]) -> None:
        """Sem quem responda o número (dublê, backend legado), nada muda."""
        mgr = CoopManager(_daemon(cartas=None))

        mgr.sync()

        assert nascimentos == [P4, P2, P3]

    def test_a_carta_trocada_pela_aba_vale(self, nascimentos: list[str]) -> None:
        """A aba Controles renumerou: o P4 do kernel é o jogador 2 dela."""
        mgr = CoopManager(_daemon(cartas={P1: 1, P4: 2, P3: 3, P2: 4}))

        mgr.sync()

        assert nascimentos == [P4, P3, P2]


class TestQuemAtrasaNaoPerdeOLugar:
    def test_o_grab_pendente_do_p2_segura_o_p3(self, nascimentos: list[str]) -> None:
        """A MORDIDA (2): o grab do P2 confirma um tique depois; sem a espera,
        o P3 nasceria antes e seria o «jogador 2» do jogo."""
        _Leitor.pendentes = {P2}
        mgr = CoopManager(_daemon())

        mgr.sync()
        assert nascimentos == []  # P2 pendente; P3 e P4 esperam a vez dele

        mgr._players[P2].reader.grab_state = "held"
        mgr._promote_pending()

        assert nascimentos == [P2, P3, P4]

    def test_o_prazo_e_o_piso_de_quem_esta_pronto(
        self, nascimentos: list[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A MORDIDA (3): o P2 que nunca confirma não deixa o P3 sem controle —
        passado `ESPERA_PELA_ORDEM_S`, o P3 nasce e o diário diz."""
        relogio = {"t": 1000.0}
        monkeypatch.setattr(coop_mod.time, "monotonic", lambda: relogio["t"])
        _Leitor.pendentes = {P2}
        mgr = CoopManager(_daemon())

        mgr.sync()
        relogio["t"] += coop_mod.ESPERA_PELA_ORDEM_S - 0.1
        mgr._promote_pending()
        assert nascimentos == []

        relogio["t"] += 0.2
        mgr._promote_pending()

        assert nascimentos == [P3, P4]
        assert mgr._players[P2].vpad is None

    def test_quem_ja_tem_vpad_nao_segura_ninguem(self, nascimentos: list[str]) -> None:
        """A espera é só por quem AINDA não nasceu: um P2 de pé não trava o P3."""
        mgr = CoopManager(_daemon())
        mgr.sync()
        assert nascimentos == [P2, P3, P4]

        mgr._teardown_player(P3)
        mgr.sync()

        assert nascimentos == [P2, P3, P4, P3]


class TestOTiqueNaoPagaAOrdem:
    def test_com_todos_nascidos_o_tique_nao_pergunta_a_carta(
        self, nascimentos: list[str]
    ) -> None:
        """O `_promote_pending` roda a cada tique do poll loop (~10 ms). Com
        todos os vpads de pé não há fila a ordenar, e ele não pode ir ao
        registro por carta — seriam centenas de idas por segundo sob o lock
        dele. A ordem só custa enquanto alguém espera nascer."""
        consultas: list[str] = []

        def _carta(mac: str, assign: bool = False) -> int | None:
            consultas.append(mac)
            return CARTAS.get(mac)

        daemon = _daemon()
        daemon.identity_registry = SimpleNamespace(numero_da_lampada=_carta)
        mgr = CoopManager(daemon)
        mgr.sync()
        assert nascimentos == [P2, P3, P4]

        consultas.clear()
        for _ in range(100):
            mgr._promote_pending()

        assert consultas == []
