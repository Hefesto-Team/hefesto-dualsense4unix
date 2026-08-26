"""BORDA-DE-QUEDA-01 (26/08/2026): o P1 morre, os secundários ficam escondidos.

`rehide_physical_hidraw` tinha `if not _vpad_vivo(daemon): return` no TOPO, e
`_vpad_vivo` olha **só** `daemon._gamepad_device` — o vpad do Jogador 1. Com o
uhid do P1 derrubado (UHID_STOP de um probe), a função inteira devolvia antes
de chegar ao laço dos jogadores 2..4. Cada replug/wake BT recria o nó físico
VISÍVEL (rule 70 + uaccess do udev), e a reconciliação online, que existe
justamente para reesconder, ficava muda: o jogo passava a ver o físico E o
vpad de cada secundário — os **controles duplicados**, o defeito histórico
mais caro desta casa.

A mordida: mesa com o P1 morto e os jogadores 2 e 3 vivos afirma **dois**
`client.hide(n)`. Devolvendo o gate ao topo dá zero, e o teste reprova
nomeando os dois nós que o jogo passou a ver dobrados.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp

_P2 = "aabbccddee02"
_P3 = "aabbccddee03"


class _BrokerDeFita:
    def __init__(self) -> None:
        self.escondidos: list[str] = []

    def hide(self, node: str) -> bool:
        self.escondidos.append(node)
        return True

    def restore(self, node: str) -> bool:
        return True

    def restore_all(self) -> bool:
        return True


class _VpadFalso:
    """`_started` só existe no uhid; False = UHID_STOP derrubou o device."""

    def __init__(self, *, started: bool | None = None) -> None:
        self.flavor = "dualsense"
        if started is not None:
            self._started = started


class _ControllerFalso:
    def __init__(self, nodes: dict[str | None, str | None]) -> None:
        self.nodes = nodes

    def hidraw_path(self, uniq: str | None = None) -> str | None:
        return self.nodes.get(uniq)


class _DaemonFalso:
    def __init__(self) -> None:
        self._gamepad_device: Any = None
        self._coop_manager: Any = None
        self._hidraw_broker_client = _BrokerDeFita()
        self.controller = _ControllerFalso(
            {None: "/dev/hidraw3", _P2: "/dev/hidraw7", _P3: "/dev/hidraw9"}
        )
        self.config = SimpleNamespace(gamepad_emulation_enabled=True)
        self._native = False

    def is_native_mode(self) -> bool:
        return self._native

    @property
    def broker(self) -> _BrokerDeFita:
        return self._hidraw_broker_client


@pytest.fixture()
def mesa() -> _DaemonFalso:
    return _DaemonFalso()


def _com_secundarios_vivos(daemon: _DaemonFalso) -> None:
    daemon._coop_manager = SimpleNamespace(
        _players={
            _P2: SimpleNamespace(vpad=_VpadFalso(started=True)),
            _P3: SimpleNamespace(vpad=_VpadFalso(started=True)),
        }
    )


def test_os_secundarios_sao_reescondidos_sem_o_p1(mesa: _DaemonFalso) -> None:
    """A mordida: P1 morto, jogadores 2 e 3 vivos → DOIS hides."""
    mesa._gamepad_device = _VpadFalso(started=False)  # UHID_STOP derrubou o P1
    _com_secundarios_vivos(mesa)

    gp.rehide_physical_hidraw(mesa)  # type: ignore[arg-type]

    escondidos = sorted(mesa.broker.escondidos)
    assert escondidos == ["/dev/hidraw7", "/dev/hidraw9"], (
        "com o vpad do P1 morto, os nós físicos dos jogadores 2 e 3 ficaram "
        "VISÍVEIS: o jogo vê /dev/hidraw7 e /dev/hidraw9 dobrados (físico + "
        f"vpad de cada um). Escondidos de fato: {escondidos}"
    )
    # E o nó do P1 NÃO entra: o vpad dele está morto, e esconder o físico de
    # quem não tem vpad vivo é o caminho direto para ZERO controles.
    assert "/dev/hidraw3" not in mesa.broker.escondidos


def test_com_o_p1_vivo_os_tres_nos_somem(mesa: _DaemonFalso) -> None:
    """O caminho feliz continua igual — a cura é aditiva, não substitutiva."""
    mesa._gamepad_device = _VpadFalso(started=True)
    _com_secundarios_vivos(mesa)

    gp.rehide_physical_hidraw(mesa)  # type: ignore[arg-type]

    assert sorted(mesa.broker.escondidos) == [
        "/dev/hidraw3",
        "/dev/hidraw7",
        "/dev/hidraw9",
    ]


def test_secundario_morto_continua_sem_autorizar_o_proprio_no(
    mesa: _DaemonFalso,
) -> None:
    """Cada jogador é guardado pelo vpad DELE — o gate por-nó nos dois sentidos.

    Achado Onda S #1 intacto: a mudança move o gate do P1, não o afrouxa.
    """
    mesa._gamepad_device = _VpadFalso(started=False)
    mesa._coop_manager = SimpleNamespace(
        _players={
            _P2: SimpleNamespace(vpad=_VpadFalso(started=False)),
            _P3: SimpleNamespace(vpad=_VpadFalso(started=True)),
        }
    )

    gp.rehide_physical_hidraw(mesa)  # type: ignore[arg-type]

    assert mesa.broker.escondidos == ["/dev/hidraw9"]


def test_p1_morto_e_sem_secundarios_nao_esconde_nada(mesa: _DaemonFalso) -> None:
    """A regra de ouro de sempre: sem vpad vivo nenhum, ninguém some."""
    mesa._gamepad_device = _VpadFalso(started=False)

    gp.rehide_physical_hidraw(mesa)  # type: ignore[arg-type]

    assert mesa.broker.escondidos == []


def test_os_gates_da_mesa_inteira_continuam_de_pe(mesa: _DaemonFalso) -> None:
    """Modo Nativo e emulação desligada seguem cortando ANTES de tudo.

    Esses três (nativo, emulação, backend com `hidraw_path`) valem para a mesa
    inteira; só o gate de vpad virou por-nó.
    """
    _com_secundarios_vivos(mesa)

    mesa._native = True
    gp.rehide_physical_hidraw(mesa)  # type: ignore[arg-type]
    assert mesa.broker.escondidos == []

    mesa._native = False
    mesa.config.gamepad_emulation_enabled = False
    gp.rehide_physical_hidraw(mesa)  # type: ignore[arg-type]
    assert mesa.broker.escondidos == []

    mesa.config.gamepad_emulation_enabled = True
    mesa.controller = SimpleNamespace()  # type: ignore[assignment]
    gp.rehide_physical_hidraw(mesa)  # type: ignore[arg-type]
    assert mesa.broker.escondidos == []


def test_externo_sem_mac_nunca_autoriza_hide(mesa: _DaemonFalso) -> None:
    """`path:*` continua fora, com ou sem P1 — ele não tem handle no backend."""
    mesa._gamepad_device = _VpadFalso(started=False)
    mesa._coop_manager = SimpleNamespace(
        _players={
            "path:/dev/input/event9": SimpleNamespace(vpad=_VpadFalso(started=True)),
            _P2: SimpleNamespace(vpad=_VpadFalso(started=True)),
        }
    )

    gp.rehide_physical_hidraw(mesa)  # type: ignore[arg-type]

    assert mesa.broker.escondidos == ["/dev/hidraw7"]
