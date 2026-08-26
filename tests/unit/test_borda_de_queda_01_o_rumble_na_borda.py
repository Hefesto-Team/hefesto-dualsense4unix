"""BORDA-DE-QUEDA-01 (26/08/2026): o motor para ANTES de o vpad morrer.

O defeito, medido na sessão dela: jogando com dois ou mais no rádio, um cai e
o motor do controle **fica vibrando** até o teto de 3 s do relógio cortar —
quatro vezes em 28 s, uma delas em (230, 230), quase máximo. O
`_teardown_player` desmontava reader, motion_reader e vpad sem uma única linha
que zerasse o rumble.

A mordida é de **ORDEM**, não de efeito: depois do `vpad.stop()` o sink de FF
daquele jogador já morreu, e um stop mandado ali não teria por onde sair. O
teste grava uma fita única de chamadas e afirma que `force_rumble_stop(uniq)`
aparece ANTES de `vpad.stop()`.
"""
from __future__ import annotations

import contextlib
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems.coop import (
    CoopManager,
    _SecondaryPlayer,
)

_MAC = "aabbccddee02"


class _Fita:
    """A fita única: quem chamou o quê, na ordem em que aconteceu."""

    def __init__(self) -> None:
        self.eventos: list[tuple[str, Any]] = []

    def anotar(self, o_que: str, alvo: Any = None) -> None:
        self.eventos.append((o_que, alvo))

    @property
    def nomes(self) -> list[str]:
        return [nome for nome, _ in self.eventos]


class _VpadDeFita:
    """Vpad que só sabe morrer — e anota a hora em que morreu."""

    def __init__(self, fita: _Fita) -> None:
        self.fita = fita
        self.flavor = "dualsense"
        self._started = True

    def stop(self) -> None:
        self.fita.anotar("vpad.stop")
        self._started = False


class _ControllerDeFita:
    """Backend dublê com a API por-uniq do `force_rumble_stop` (BORDA-01).

    Guarda o estado dos motores para que a fita conte a história inteira: o
    jogador entra vibrando em (230, 230) e tem de sair em (0, 0).
    """

    def __init__(self, fita: _Fita) -> None:
        self.fita = fita
        self._evdev = SimpleNamespace(set_grab=lambda _g: True, grab_state="held")
        self.motores: dict[str, tuple[int, int]] = {}
        self.explode = False

    def hidraw_path(self, uniq: str | None = None) -> str | None:
        return {None: "/dev/hidraw3", _MAC: "/dev/hidraw7"}.get(uniq)

    def force_rumble_stop(self, uniq: str | None = None) -> None:
        if self.explode:
            raise OSError("handle morreu junto com o controle")
        self.fita.anotar("force_rumble_stop", uniq)
        alvos = [uniq] if uniq is not None else list(self.motores)
        for alvo in alvos:
            if alvo is not None:
                self.motores[alvo] = (0, 0)

    def set_rumble(self, weak: int = 0, strong: int = 0) -> None: ...

    def read_calibration(self, uniq: str | None = None) -> bytes | None:
        return None

    def attach_motion_reader(self, reader: Any | None) -> None: ...


class _DaemonDeFita:
    def __init__(self, fita: _Fita) -> None:
        self._gamepad_device = None
        self._coop_manager = None
        self._hidraw_broker_client = SimpleNamespace(
            hide=lambda _n: True,
            restore=lambda _n: True,
            restore_all=lambda: True,
        )
        self.controller = _ControllerDeFita(fita)
        self.config = SimpleNamespace(gamepad_emulation_enabled=True)

    def is_native_mode(self) -> bool:
        return False


def _mesa(
    identity: str = _MAC, *, com_vpad: bool = True
) -> tuple[CoopManager, _DaemonDeFita, _Fita, _SecondaryPlayer]:
    fita = _Fita()
    daemon = _DaemonDeFita(fita)
    manager = CoopManager(daemon)  # type: ignore[arg-type]
    reader = SimpleNamespace(
        set_grab=lambda _g: True, stop=lambda: fita.anotar("reader.stop"),
        grab_state="held",
    )
    player = _SecondaryPlayer(
        identity=identity,
        evdev_path="/dev/input/event99",
        reader=reader,  # type: ignore[arg-type]
        player_index=2,
        vpad=_VpadDeFita(fita) if com_vpad else None,  # type: ignore[arg-type]
    )
    manager._players[identity] = player
    # O jogador está VIBRANDO no instante em que cai — é o (230, 230) do
    # journal dela, e sem ele o teste mediria uma borda em silêncio.
    daemon.controller.motores[identity] = (230, 230)
    return manager, daemon, fita, player


def test_o_teardown_zera_o_motor_antes_de_matar_o_vpad() -> None:
    """A mordida: `force_rumble_stop(uniq)` ANTES de `vpad.stop()`."""
    manager, daemon, fita, player = _mesa()

    manager._teardown_player(player.identity)

    assert "force_rumble_stop" in fita.nomes, (
        "o jogador saiu da mesa com o motor em (230, 230) e NADA mandou o "
        "report de stop — o motor morre vibrando até o teto de 3 s do relógio"
    )
    assert "vpad.stop" in fita.nomes
    assert fita.nomes.index("force_rumble_stop") < fita.nomes.index("vpad.stop"), (
        "o stop saiu DEPOIS de o vpad morrer: o sink de FF daquele jogador já "
        f"não existe mais e o report não tem por onde sair — fita: {fita.nomes}"
    )
    # E ele foi endereçado a ESTE jogador, não à mesa inteira: os outros três
    # continuam jogando, e um broadcast os deixaria mudos no meio da partida.
    alvos = [alvo for nome, alvo in fita.eventos if nome == "force_rumble_stop"]
    assert alvos == [_MAC], f"stop endereçado errado (broadcast?): {alvos}"
    assert daemon.controller.motores[_MAC] == (0, 0)


def test_o_backend_que_explode_nao_aborta_o_teardown() -> None:
    """Best-effort sagrado: motor preso é ruim, nó 0600 sem dono é pior.

    O caso REAL do hotplug-out — o handle morreu junto com o controle — e o
    teardown tem de seguir até o fim mesmo assim.
    """
    manager, daemon, fita, player = _mesa()
    daemon.controller.explode = True

    manager._teardown_player(player.identity)  # não levanta

    assert "vpad.stop" in fita.nomes
    assert manager._players == {}


def test_jogador_sem_mac_nao_para_a_mesa_inteira() -> None:
    """Identidade `path:*` (externo) é NO-OP, e é decisão, não esquecimento.

    Sem MAC não há endereço; a única chamada possível seria o broadcast, que
    pararia o motor de quem continua jogando. O relógio do
    `uhid_gamepad._expirar_rumble_preso` é o segundo cinto para esse caso.
    """
    manager, _daemon, fita, player = _mesa("path:/dev/input/event9")

    manager._teardown_player(player.identity)

    assert "force_rumble_stop" not in fita.nomes
    assert "vpad.stop" in fita.nomes


def test_backend_sem_a_api_nao_explode() -> None:
    """Fake/legado sem `force_rumble_stop` (o FakeController do smoke)."""
    manager, daemon, fita, player = _mesa()
    daemon.controller = SimpleNamespace(  # type: ignore[assignment]
        _evdev=SimpleNamespace(set_grab=lambda _g: True, grab_state="held"),
    )

    manager._teardown_player(player.identity)  # não levanta

    assert "force_rumble_stop" not in fita.nomes
    assert "vpad.stop" in fita.nomes


# --- o lado do backend: o alvo é UM, e o broadcast continua existindo -------


class _HandleFalso:
    def __init__(self) -> None:
        self.esquerdo: int | None = None
        self.direito: int | None = None
        self._rumble_stop_pending = False

    def setLeftMotor(self, v: int) -> None:  # noqa: N802 (API da pydualsense)
        self.esquerdo = v

    def setRightMotor(self, v: int) -> None:  # noqa: N802
        self.direito = v


@pytest.fixture()
def backend() -> Any:
    from hefesto_dualsense4unix.core import backend_pydualsense as bp

    ctl = bp.PyDualSenseController()
    ctl._handles = {  # type: ignore[assignment]
        "AA:BB:CC:DD:EE:02": _HandleFalso(),
        "AA:BB:CC:DD:EE:03": _HandleFalso(),
    }
    return ctl


def test_force_rumble_stop_com_uniq_arma_so_o_alvo(backend: Any) -> None:
    """O par da cura no backend: um jogador cai, os outros seguem vibrando."""
    backend.force_rumble_stop("aabbccddee02")

    alvo = backend._handles["AA:BB:CC:DD:EE:02"]
    vizinho = backend._handles["AA:BB:CC:DD:EE:03"]
    assert alvo._rumble_stop_pending is True
    assert (alvo.esquerdo, alvo.direito) == (0, 0)
    assert vizinho._rumble_stop_pending is False, (
        "o stop de UM jogador emudeceu o motor de outro que continua jogando"
    )


def test_force_rumble_stop_sem_uniq_segue_broadcast(backend: Any) -> None:
    """HARM-16 intacto: saída de modo continua alcançando TODA a mesa."""
    backend.force_rumble_stop()

    for handle in backend._handles.values():
        assert handle._rumble_stop_pending is True


def test_alvo_que_nao_casa_handle_e_no_op(backend: Any) -> None:
    """O controle já saiu: não há nada a parar, e nada a explodir."""
    with contextlib.suppress(Exception):
        backend.force_rumble_stop("ffffffffffff")
    for handle in backend._handles.values():
        assert handle._rumble_stop_pending is False
