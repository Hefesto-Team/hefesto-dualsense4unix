"""A-MIRA-POR-MOVIMENTO-NA-TELA-01 — a mira que nunca andou, e o chip dela.

A SEGUNDA PALAVRA DELA, 23/09/2026: um botão «Mira Virtual» ao lado de
Giroscópio e Acelerômetro, POR CONTROLE, com a dica *«Usar os movimentos do
controle como mira (analógico R), para pessoas com deficiência motora.»*

O ACHADO QUE ABRE ESTE ARQUIVO, e ele é o defeito vivo
-------------------------------------------------------
**A MIRA NUNCA ANDOU NO PRODUTO.** O motor (`gamepad.aplicar_o_movimento`)
pergunta ``getattr(daemon, "_garantir_sensor_hub", None)`` e, sem resposta,
devolve os quatro eixos intactos. O `Daemon` de verdade (`daemon/lifecycle.py`)
não tinha o método — só o `IpcServer` tinha. As réguas da
MOVIMENTO-EM-QUALQUER-MASCARA-01 davam verde porque os três dublês de daemon
penduravam ``_garantir_sensor_hub=lambda: hub`` num `SimpleNamespace`: **o
dublê tinha o que o real não tem**, e a mira ficou verde sem mover um eixo.

Por isso a primeira seção daqui NÃO dubla o daemon: monta o `Daemon` real, o
`IpcServer` real e o `SensorHub` real (só o leitor do nó é de mentira, porque
não há aparelho), e roda o tique real — o `dispatch_gamepad` do P1 e o
`CoopManager.forward_all` dos P2 a P4.

MORDIDA: apague ``Daemon._garantir_sensor_hub`` de `daemon/lifecycle.py` e as
réguas da seção 1 reprovam dizendo que o analógico direito saiu parado.

Endereços de rádio: a faixa SINTÉTICA da casa (``aa:bb:cc``), nunca um OUI real.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.core.virtual_motion import REGISTRO
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.lifecycle import Daemon
from hefesto_dualsense4unix.daemon.sensor_hub import SensorHub
from hefesto_dualsense4unix.daemon.subsystems import coop as co
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import (
    MatchAny,
    Profile,
    ProfileMovimentoConfig,
)
from hefesto_dualsense4unix.testing import FakeController

_P1, _P2, _P3, _P4 = (
    "aa:bb:cc:00:00:01",
    "aa:bb:cc:00:00:02",
    "aa:bb:cc:00:00:03",
    "aa:bb:cc:00:00:04",
)

#: Um giro de pulso de verdade, em graus/s no eixo `yaw` (y): bem acima da zona
#: morta padrão e abaixo do teto, então a deflexão é franca e não satura.
_GIRO = (0.0, 150.0, 0.0)


@pytest.fixture(autouse=True)
def _registro_limpo() -> Iterator[None]:
    """O `REGISTRO` dos sensores é do processo: nada desta régua vaza dele."""
    REGISTRO.limpar()
    yield
    REGISTRO.limpar()


# ---------------------------------------------------------------------------
# 1. O DAEMON DE VERDADE — a cura do achado
# ---------------------------------------------------------------------------


class _LeitorDoNo:
    """O leitor do nó «Motion Sensors» — a única peça de mentira da torneira.

    Do tamanho do `MotionSensorReader` para o que o hub pergunta: `start()`
    afirma que abriu (o hub DESCARTA quem não afirma), `snapshot()` devolve os
    três eixos e `consume_angulo()` drena.
    """

    def __init__(self, giro: tuple[float, float, float]) -> None:
        self._giro = giro

    def start(self) -> bool:
        return True

    def stop(self) -> None:
        pass

    def snapshot(self) -> Any:
        return SimpleNamespace(x=self._giro[0], y=self._giro[1], z=self._giro[2])

    def consume_angulo(self) -> tuple[float, float, float]:
        return (0.0, 0.0, 0.0)


def _hub(giro_por_uniq: dict[str, tuple[float, float, float]]) -> SensorHub:
    """O `SensorHub` REAL, com o nó e o leitor dublados — nenhum aparelho aberto."""
    hub = SensorHub(
        motion_factory=lambda uniq, node: _LeitorDoNo(giro_por_uniq[uniq]),
        touch_factory=lambda uniq, node: _LeitorDoNo((0.0, 0.0, 0.0)),
        gamepad_factory=lambda uniq, node: _LeitorDoNo((0.0, 0.0, 0.0)),
        descobrir_motion=lambda: {u: Path(f"/dev/input/event-{u}") for u in giro_por_uniq},
        descobrir_touch=dict,
        descobrir_gamepad=dict,
        auto_manutencao=False,
    )
    hub._watch = SimpleNamespace(poll=lambda: False)
    return hub


def _mesa_de_verdade(
    tmp_path: Path, transporte: str, hub: SensorHub
) -> tuple[Daemon, IpcServer]:
    """O `Daemon` e o `IpcServer` do produto, ligados como o `start_ipc` liga."""
    controle = FakeController(transport=transporte)  # type: ignore[arg-type]
    # A IDENTIDADE DO P1 como o backend real a publica (`primary_uniq`): é
    # isto que o `primary_identity` do tique lê — nenhum monkeypatch nele.
    controle.primary_uniq = _P1  # type: ignore[attr-defined]
    daemon = Daemon(controller=controle)
    gerente = ProfileManager(controller=controle, store=daemon.store)
    servidor = IpcServer(
        controller=controle,
        store=daemon.store,
        profile_manager=gerente,
        socket_path=tmp_path / "mira.sock",
        daemon=daemon,
    )
    # O hub mora no SERVIDOR, como no produto (`_garantir_sensor_hub` do mixin
    # o cria no primeiro uso); a régua só o injeta antes, com o leitor dublado.
    servidor._sensor_hub = hub
    daemon._ipc_server = servidor
    gerente.apply_movimento(
        Profile(
            name="Com mira",
            match=MatchAny(type="any"),
            movimento=ProfileMovimentoConfig(destino="analogico_direito"),
        )
    )
    return daemon, servidor


class _Vpad:
    """O gamepad virtual: guarda o que o JOGO receberia."""

    def __init__(self) -> None:
        self.analog: list[dict[str, int]] = []

    def forward_analog(self, **kw: int) -> None:
        self.analog.append(kw)

    def forward_buttons(self, pressed: frozenset[str]) -> None:
        pass


def _estado(transporte: str) -> ControllerState:
    return ControllerState(
        battery_pct=100, l2_raw=0, r2_raw=0, connected=True, transport=transporte  # type: ignore[arg-type]
    )


def _tique_do_p1(
    monkeypatch: pytest.MonkeyPatch, daemon: Daemon, hub: SensorHub, transporte: str
) -> _Vpad:
    """Dois tiques do `dispatch_gamepad`, com a reconciliação do hub no meio.

    O primeiro tique REGISTRA A DEMANDA (é o que abre o leitor, na volta de
    manutenção do hub); o segundo lê o giro. É o mesmo ritmo do produto, com a
    volta de um segundo trocada por uma chamada.
    """
    # As duas extras do tique que não são da mira — o arming de launch e o aviso
    # de troca de modo leem arquivos da Steam e o barramento; ficam de fora.
    monkeypatch.setattr(gp, "_reconciliar_launch", lambda d: None)
    monkeypatch.setattr(gp, "_avisar_troca_de_modo", lambda d: None)
    vpad = _Vpad()
    daemon._gamepad_device = vpad
    gp.dispatch_gamepad(daemon, _estado(transporte), frozenset())
    hub.reconciliar()
    gp.dispatch_gamepad(daemon, _estado(transporte), frozenset())
    return vpad


@pytest.mark.parametrize("transporte", ["usb", "bt"])
def test_a_mira_anda_no_daemon_de_verdade(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, transporte: str
) -> None:
    """O P1, no cabo e no rádio, com o `Daemon` que o produto sobe.

    MORDIDA: apague ``Daemon._garantir_sensor_hub`` e este teste reprova — era
    o estado do produto até 24/09/2026.
    """
    hub = _hub({_P1: _GIRO})
    daemon, _servidor = _mesa_de_verdade(tmp_path, transporte, hub)
    vpad = _tique_do_p1(monkeypatch, daemon, hub, transporte)
    assert vpad.analog, "o tique nem chegou ao vpad"
    assert vpad.analog[-1]["rx"] != 128, (
        f"o controle girou {_GIRO} graus/s e o analógico direito saiu parado "
        f"({vpad.analog[-1]}) — o `Daemon` real não entrega o hub ao motor")


@pytest.mark.parametrize("transporte", ["usb", "bt"])
def test_a_mira_anda_nos_jogadores_2_3_e_4_no_daemon_de_verdade(
    tmp_path: Path, transporte: str
) -> None:
    """Os P2 a P4, pelo `CoopManager` real sobre o mesmo `Daemon` real.

    *"cara nenhuma solução pode ser feita só pro p1"* — e o laço dos
    secundários passa `self._daemon` ao motor, que é este objeto.
    """
    giros = {_P2: _GIRO, _P3: _GIRO, _P4: _GIRO}
    hub = _hub(giros)
    daemon, _servidor = _mesa_de_verdade(tmp_path, transporte, hub)
    gerente = co.CoopManager(daemon)
    vpads: dict[str, _Vpad] = {}
    for n, uniq in enumerate(sorted(giros), start=2):
        vpads[uniq] = _Vpad()
        gerente._players[uniq] = co._SecondaryPlayer(
            identity=uniq,
            evdev_path=f"/dev/input/event{n}",
            reader=SimpleNamespace(
                snapshot=lambda: SimpleNamespace(
                    lx=128, ly=128, rx=128, ry=128, l2_raw=0, r2_raw=0,
                    buttons_pressed=frozenset()),
                grab_state="held",
            ),
            player_index=n,
            vpad=vpads[uniq],
        )
    gerente.forward_all()
    hub.reconciliar()
    gerente.forward_all()
    for uniq, vpad in sorted(vpads.items()):
        assert vpad.analog[-1]["rx"] != 128, (
            f"o jogador {uniq} girou o controle e não mirou — o `Daemon` real "
            f"não entrega o hub ao laço dos secundários")


def test_o_hub_da_mira_e_o_mesmo_do_ipc(tmp_path: Path) -> None:
    """UM HUB SÓ POR SESSÃO. Dois hubs abririam dois leitores no mesmo nó e
    duas máquinas de `EVIOCGRAB` brigando pelo interruptor de sensor dela.

    MORDIDA: faça o `Daemon` criar o próprio `SensorHub` (copiar o método do
    mixin, em vez de delegar) e este teste reprova.
    """
    hub = _hub({_P1: _GIRO})
    daemon, servidor = _mesa_de_verdade(tmp_path, "usb", hub)
    assert daemon._garantir_sensor_hub() is servidor._garantir_sensor_hub() is hub


def test_sem_servidor_os_eixos_saem_como_entraram(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """O instante antes de o IPC subir (ou um IPC que caiu): sem hub, sem mira,
    e SEM AVISO — o motor pediria o hub 60 vezes por segundo.

    MORDIDA: devolva ``None`` em vez de ``HUB_AUSENTE`` e este teste reprova
    pelo aviso `roteador_de_movimento_falhou` a cada tique.
    """
    from structlog.testing import capture_logs

    hub = _hub({_P1: _GIRO})
    daemon, _servidor = _mesa_de_verdade(tmp_path, "usb", hub)
    daemon._ipc_server = None
    with capture_logs() as logs:
        vpad = _tique_do_p1(monkeypatch, daemon, hub, "usb")
    assert vpad.analog and vpad.analog[-1]["rx"] == 128
    avisos = [e for e in logs if e.get("event") == "roteador_de_movimento_falhou"]
    assert not avisos, f"o tique sem servidor registrou {len(avisos)} aviso(s): {avisos}"
