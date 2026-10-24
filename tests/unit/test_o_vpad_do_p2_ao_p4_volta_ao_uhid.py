"""O-VPAD-DO-P2-AO-P4-QUE-CAIU-NO-UINPUT-VOLTA-AO-UHID-01: a rede do P1 vale para os quatro.

O secundário que nasceu no `uinput` sem o `/dev/uhid` pronto ficava Xbox 360
no jogo: só o P1 tinha quem o promovesse. Na mesa mista, com a fábrica de
verdade e o `uhid` de mentira, o degradado renasce `uhid` no mesmo número, com
o cooldown de cada um sozinho. Sem o jogo, quem vem DEPOIS dele na carta
renasce junto (`D-2309-FORA-DE-ORDEM-SE-RECRIA-NA-HORA`); quem vem antes, não.
"""
from __future__ import annotations

import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, ClassVar

import pytest

from hefesto_dualsense4unix.daemon.subsystems import coop as coop_mod
from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager
from hefesto_dualsense4unix.daemon.subsystems.gamepad import REBACKEND_COOLDOWN_SEC

P1 = "aabbcc000011"
P2 = "aabbcc000022"
P3 = "aabbcc000033"
P4 = "aabbcc000044"


class _Leitor:
    def __init__(self, device_path: Any = None, target_uniq: str | None = None) -> None:
        self.device_path = device_path
        self.target_uniq = target_uniq
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


class _Pad:
    """O vpad de mentira: diz o `backend`, a máscara e o motivo que a fábrica pendura."""

    criados: ClassVar[list[_Pad]] = []

    def __init__(self, backend: str, flavor: str) -> None:
        self.backend = backend
        self.flavor = flavor
        self.paradas = 0
        self.rumble_sink: Any = None
        type(self).criados.append(self)

    @classmethod
    def for_flavor(cls, flavor: str, *, rumble_sink: Any = None) -> _Pad:
        pad = cls("uinput", flavor)
        pad.rumble_sink = rumble_sink
        return pad

    def start(self) -> bool:
        return True

    def stop(self) -> None:
        self.paradas += 1

    def forward_analog(self, **kw: int) -> None:
        pass

    def forward_buttons(self, pressed: frozenset[str]) -> None:
        pass


class _Registro:
    def __init__(self, macs: tuple[str, ...]) -> None:
        self.slots = {mac: n for n, mac in enumerate(macs, start=1)}

    def slot_for(self, uniq: str, assign: bool = True) -> int | None:
        return self.slots.get(uniq)

    def o_lugar_espera(self, uniq: str | None) -> bool:
        return uniq in self.slots


class _Mesa:
    """Os nós, o `uhid` que liga e desliga, o relógio e o daemon com o backend real."""

    def __init__(
        self,
        monkeypatch: pytest.MonkeyPatch,
        macs: tuple[str, ...],
        *,
        sem_uhid_no_boot: set[str] | None = None,
    ) -> None:
        self.nos = {mac: f"/dev/input/event{5 + 2 * n}" for n, mac in enumerate(macs)}
        self.uhid = False
        self.sem_uhid_no_boot = set(macs) if sem_uhid_no_boot is None else sem_uhid_no_boot
        self.relogio = [1000.0]
        self.registro = _Registro(macs)
        _Pad.criados = []
        monkeypatch.setattr(
            coop_mod, "time",
            SimpleNamespace(monotonic=lambda: self.relogio[0], time=time.time, sleep=time.sleep),
        )
        monkeypatch.setattr(
            "hefesto_dualsense4unix.core.evdev_reader.InputDirWatch.poll", lambda self: True
        )
        monkeypatch.setattr("hefesto_dualsense4unix.core.evdev_reader.EvdevReader", _Leitor)
        monkeypatch.setattr(
            "hefesto_dualsense4unix.core.evdev_reader.discover_dualsense_evdevs",
            lambda: {mac: Path(p) for mac, p in self.nos.items()},
        )
        monkeypatch.setattr(
            "hefesto_dualsense4unix.integrations.uinput_gamepad.UinputGamepad", _Pad
        )
        monkeypatch.setattr(
            "hefesto_dualsense4unix.integrations.virtual_pad._try_uhid",
            self._try_uhid,
        )
        monkeypatch.setattr(
            "hefesto_dualsense4unix.integrations.uhid_gamepad.uhid_available",
            lambda: self.uhid,
        )
        monkeypatch.setattr("hefesto_dualsense4unix.core.sysfs_leds.discover", lambda: {})
        controller = SimpleNamespace(
            _evdev=SimpleNamespace(_device_path=Path(self.nos[P1])),
            primary_uniq=P1,
            _desired=SimpleNamespace(player_leds=None),
            set_player_leds=lambda bits: None,
            force_rumble_stop=lambda uniq: None,
            em_troca_de_transporte=lambda uniq: False,
            hidraw_path=lambda *a: None,
        )
        self.daemon = SimpleNamespace(
            config=SimpleNamespace(coop_enabled=True, gamepad_flavor="dualsense"),
            _gamepad_device=object(),
            controller=controller,
            _coop_manager=None,
            identity_registry=self.registro,
            display_authority="daemon",
        )
        self.mgr = CoopManager(self.daemon)  # type: ignore[arg-type]
        self.mgr.sync()

    def _try_uhid(self, flavor: str, **kw: Any) -> tuple[Any, str | None]:
        if self.uhid or kw.get("identity") not in self.sem_uhid_no_boot:
            return _Pad("uhid", flavor), None
        return None, "sem_uhid"

    def ordem_no_jogo(self) -> list[str]:
        """As chaves dos secundários na ordem em que o jogo os enumera."""
        mesa = self.mgr._mesa_do_jogo
        return [mesa[lugar] for lugar in sorted(mesa) if mesa[lugar] in self.mgr._players]

    def vpads(self) -> dict[str, Any]:
        return {mac: p.vpad for mac, p in self.mgr._players.items()}

    def backends(self) -> dict[str, str]:
        return {mac: getattr(v, "backend", "") for mac, v in self.vpads().items()}

    def tique(self, segundos: float = 2.0) -> None:
        self.relogio[0] += segundos
        self.mgr.sync()


MESA_MISTA = (P1, P2, P3, P4)

#: (rótulo da mesa, os degradados). O transporte de cada um está no rótulo: a
#: queda para o `uinput` é do `/dev/uhid`, e a cura não tem ramo de transporte.
MATRIZ = [
    ("p1-usb,p2-bt,p3-usb,p4-bt", (P2, P3)),
    ("tres-adaptadores-e-um-no-cabo", (P4,)),
    ("todos-no-cabo", (P2,)),
    ("todos-no-radio", (P2, P3, P4)),
]


@pytest.mark.parametrize(("mesa", "degradados"), MATRIZ, ids=[m[0] for m in MATRIZ])
def test_o_degradado_volta_ao_uhid_no_primeiro_tique(
    monkeypatch: pytest.MonkeyPatch, mesa: str, degradados: tuple[str, ...]
) -> None:
    m = _Mesa(monkeypatch, MESA_MISTA, sem_uhid_no_boot=set(degradados))
    assert {mac for mac, b in m.backends().items() if b == "uinput"} == set(degradados)
    primeiro = min(MESA_MISTA.index(mac) for mac in degradados)
    intactos = {mac: v for mac, v in m.vpads().items() if MESA_MISTA.index(mac) < primeiro}
    numeros = m.mgr.numeros_de_jogador()
    ordem = m.ordem_no_jogo()

    m.uhid = True
    m.tique()

    assert set(m.backends().values()) == {"uhid"}, f"ficou degradado: {m.backends()}"
    for mac, vpad in intactos.items():
        assert m.vpads()[mac] is vpad, f"{mac} vem antes do degradado e foi recriado"
        assert vpad.paradas == 0
    assert m.mgr.numeros_de_jogador() == numeros, "o número mudou na promoção"
    assert m.ordem_no_jogo() == ordem == [P2, P3, P4], "o jogo viu a mesa fora da carta"


def test_um_so_nao_ha_secundario_a_promover(monkeypatch: pytest.MonkeyPatch) -> None:
    m = _Mesa(monkeypatch, (P1,))
    m.uhid = True
    assert m.mgr.promover_os_degradados() == []
    assert m.mgr._players == {}


def test_com_o_jogo_na_autoridade_nada_se_recria(monkeypatch: pytest.MonkeyPatch) -> None:
    m = _Mesa(monkeypatch, MESA_MISTA)
    antes = m.vpads()
    m.daemon.display_authority = "game"
    m.uhid = True
    for _ in range(5):
        m.tique()
    assert m.vpads() == antes
    assert set(m.backends().values()) == {"uinput"}
    m.daemon.display_authority = "daemon"
    m.tique()
    assert set(m.backends().values()) == {"uhid"}, "o jogo fechou e o degradado ficou"


def test_sem_uhid_nada_se_recria(monkeypatch: pytest.MonkeyPatch) -> None:
    m = _Mesa(monkeypatch, MESA_MISTA)
    antes = m.vpads()
    for _ in range(int(3 * REBACKEND_COOLDOWN_SEC / 2.0)):
        m.tique()
    assert m.vpads() == antes
    assert all(v.paradas == 0 for v in antes.values())


def test_o_uhid_que_volta_a_cair_tenta_uma_vez_por_cooldown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O `uhid_available()` diz sim e o CREATE2 cai: no máximo uma volta por janela."""
    m = _Mesa(monkeypatch, MESA_MISTA)
    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.virtual_pad._try_uhid",
        lambda flavor, **kw: (None, "uhid_sem_bind"),
    )
    m.uhid = True
    janela = int(REBACKEND_COOLDOWN_SEC / 2.0)
    for _ in range(3 * janela):
        m.tique()
    tentativas = len(_Pad.criados) - 3
    assert 3 * 2 <= tentativas <= 3 * 4, f"{tentativas} tentativas em três janelas"
    assert set(m.backends().values()) == {"uinput"}


def test_o_cooldown_de_um_nao_segura_o_outro(monkeypatch: pytest.MonkeyPatch) -> None:
    """Todos no rádio: o P2 acabou de tentar, e o P3 e o P4 voltam no mesmo tique."""
    m = _Mesa(monkeypatch, MESA_MISTA)
    m.mgr._promovido_em = {P2: m.relogio[0]}  # type: ignore[attr-defined]
    m.uhid = True
    m.tique()
    assert m.backends() == {P2: "uinput", P3: "uhid", P4: "uhid"}
    m.tique(REBACKEND_COOLDOWN_SEC)
    assert m.backends() == {P2: "uhid", P3: "uhid", P4: "uhid"}
