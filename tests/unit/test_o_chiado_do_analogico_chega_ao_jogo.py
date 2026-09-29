"""D-2909-O-CHIADO-DO-ANALOGICO-VAI-AO-JOGO — a régua da decisão.

A bancada de 29/09/2026 mediu quatro DualSense parados na mesa: todo eixo que
se mexeu trocou 1 unidade em 255 (o repouso cai na fronteira entre dois
valores do conversor, e o aparelho publica a troca). A decisão, por
delegação, é que **o pad repete o byte do aparelho**: o Hefesto não põe filtro
nem zona morta no analógico que vai ao jogo. A zona é do jogo; um filtro
quebraria a fidelidade medida em 15/08, o casamento pad↔físico pelo centro de
repouso, e comeria o movimento pequeno de quem tem pouca amplitude na mão.

Estas réguas prendem o repasse inteiro, nos dois laços do tique e nos dois
tipos de pad:

1. o P1 (`gamepad.dispatch_gamepad`) entrega cada troca, na ordem;
2. os jogadores 2 a 4 (`coop.CoopManager.forward_all`) entregam cada um a sua;
3. o pad `uinput` (máscaras Xbox e Nintendo) escreve cada troca, com o SYN;
4. o pad `uhid` (DualSense) leva a troca no report, nos dois relógios.

Mordida: uma histerese de 1 LSB antes do `forward_analog` do
`dispatch_gamepad` reprova a 1; antes do do `forward_all`, reprova a 2.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core import roteador_de_movimento as rot

#: O `rx` do P1 na bancada de 29/09: 131↔132, parado na mesa.
_CHIADO_DO_P1 = [131, 132] * 5

_UNIQ = "aa:bb:cc:00:00:01"
_P2, _P3, _P4 = "aa:bb:cc:00:00:02", "aa:bb:cc:00:00:03", "aa:bb:cc:00:00:04"


class _Pad:
    """O pad de mentira do tique: guarda o que o JOGO receberia, tique a tique."""

    def __init__(self) -> None:
        self.analog: list[dict[str, int]] = []

    def forward_analog(self, **kw: int) -> None:
        self.analog.append(kw)

    def forward_buttons(self, pressed: frozenset[str]) -> None:
        pass


class _HubQuieto:
    """O hub com o giroscópio parado: a Mira ligada não mexe no analógico."""

    def velocidade_do_movimento(self, uniq: str) -> Any:
        return (0.0, 0.0, 0.0)

    def angulo_do_movimento(self, uniq: str) -> Any:
        return (0.0, 0.0, 0.0)


def _daemon(pad: Any, arranjo: Any) -> SimpleNamespace:
    """O daemon dublado com o caminho do hub do `Daemon` de verdade."""
    from types import MethodType

    from hefesto_dualsense4unix.daemon.lifecycle import Daemon

    store = SimpleNamespace(udp_trigger_thresholds=(0, 0))
    if arranjo is not None:
        rot.definir_ativo(store, arranjo)
    daemon = SimpleNamespace(
        _ipc_server=SimpleNamespace(_garantir_sensor_hub=lambda: _HubQuieto()),
        store=store,
        _gamepad_device=pad,
        _mouse_device=None,
    )
    daemon._garantir_sensor_hub = MethodType(Daemon._garantir_sensor_hub, daemon)
    return daemon


#: Sem arranjo (o perfil sem a Mira) e com a Mira ligada e o giro parado (o
#: Freestyle da bancada): nos dois, o analógico chega ao jogo como veio.
_ARRANJOS = [
    pytest.param(None, id="sem-a-mira"),
    pytest.param(
        rot.ArranjoDeMovimento(destino=rot.DESTINO_ANALOGICO_DIREITO), id="com-a-mira-parada"
    ),
]


@pytest.fixture
def _registro_com_giro(monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.core.virtual_motion import REGISTRO

    monkeypatch.setattr(REGISTRO, "estado", lambda uniq: SimpleNamespace(giroscopio=True))


# ---------------------------------------------------------------------------
# 1. O P1: `dispatch_gamepad`
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("_registro_com_giro")
@pytest.mark.parametrize("arranjo", _ARRANJOS)
def test_o_p1_entrega_cada_troca_do_chiado(monkeypatch: pytest.MonkeyPatch, arranjo: Any) -> None:
    """Dez tiques com o `rx` trocando 131↔132: o pad recebe os dez, na ordem.

    Mordida: uma histerese de 1 LSB antes do `device.forward_analog` do
    `dispatch_gamepad` segura o 132 e esta régua reprova."""
    from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp

    monkeypatch.setattr(gp, "_reconciliar_launch", lambda d: None)
    monkeypatch.setattr(gp, "_avisar_troca_de_modo", lambda d: None)
    monkeypatch.setattr(gp, "primary_identity", lambda d: _UNIQ)
    pad = _Pad()
    daemon = _daemon(pad, arranjo)
    for rx in _CHIADO_DO_P1:
        estado = SimpleNamespace(
            raw_lx=127, raw_ly=128, raw_rx=rx, raw_ry=128, l2_raw=0, r2_raw=0
        )
        gp.dispatch_gamepad(daemon, estado, frozenset())
    assert [kw["rx"] for kw in pad.analog] == _CHIADO_DO_P1
    assert {kw["lx"] for kw in pad.analog} == {127}


# ---------------------------------------------------------------------------
# 2. Os jogadores 2 a 4: `coop.forward_all`
# ---------------------------------------------------------------------------


class _LeitorQueTroca:
    """O leitor de um jogador: cada tique devolve o valor seguinte do eixo."""

    def __init__(self, eixo: str, valores: list[int]) -> None:
        self._eixo = eixo
        self._valores: Iterator[int] = iter(valores)

    def snapshot(self) -> Any:
        eixos = {"lx": 128, "ly": 128, "rx": 128, "ry": 128}
        eixos[self._eixo] = next(self._valores)
        return SimpleNamespace(**eixos, l2_raw=0, r2_raw=0, buttons_pressed=frozenset())


#: A medida de 29/09 por jogador: o eixo e os dois valores entre os quais ele
#: trocou (P2 `lx` 125↔126, P3 `rx` 128↔129, P4 `ry` 124↔125).
_CHIADO_POR_JOGADOR = {
    _P2: ("lx", [125, 126] * 4),
    _P3: ("rx", [128, 128, 129, 128, 128, 128, 129, 128]),
    _P4: ("ry", [124, 125] * 4),
}


@pytest.mark.usefixtures("_registro_com_giro")
@pytest.mark.parametrize("arranjo", _ARRANJOS)
def test_os_jogadores_2_a_4_entregam_cada_um_o_seu_chiado(
    monkeypatch: pytest.MonkeyPatch, arranjo: Any
) -> None:
    """Cada pad recebe as trocas do SEU jogador, tique a tique.

    Mordida: uma histerese de 1 LSB antes do `player.vpad.forward_analog` do
    `forward_all` segura as trocas e esta régua reprova."""
    from hefesto_dualsense4unix.daemon.subsystems import coop as co
    from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager, _SecondaryPlayer

    monkeypatch.setattr(co.CoopManager, "_recolher_os_cedidos", lambda self: None)
    monkeypatch.setattr(co.CoopManager, "_promote_pending", lambda self: None)
    gerente = CoopManager.__new__(CoopManager)
    gerente._daemon = _daemon(None, arranjo)  # type: ignore[attr-defined]
    gerente._players = {}  # type: ignore[attr-defined]
    pads: dict[str, _Pad] = {}
    for n, (uniq, (eixo, valores)) in enumerate(sorted(_CHIADO_POR_JOGADOR.items()), start=2):
        pads[uniq] = _Pad()
        gerente._players[uniq] = _SecondaryPlayer(  # type: ignore[attr-defined]
            identity=uniq,
            evdev_path=f"/dev/input/event{n}",
            reader=_LeitorQueTroca(eixo, valores),
            player_index=n,
            vpad=pads[uniq],
        )
    for _ in range(8):
        gerente.forward_all()
    for uniq, (eixo, valores) in _CHIADO_POR_JOGADOR.items():
        assert [kw[eixo] for kw in pads[uniq].analog] == valores, uniq


# ---------------------------------------------------------------------------
# 3. O pad `uinput`: as máscaras Xbox e Nintendo
# ---------------------------------------------------------------------------


class _Gravador:
    """O nó `uinput` de mentira: guarda cada `write` e cada `syn`."""

    def __init__(self) -> None:
        self.escritas: list[tuple[int, int, int]] = []
        self.syns = 0

    def write(self, tipo: int, codigo: int, valor: int) -> None:
        self.escritas.append((tipo, codigo, valor))

    def syn(self) -> None:
        self.syns += 1


@pytest.mark.parametrize("mascara", ["xbox", "nintendo"])
def test_o_pad_uinput_escreve_cada_troca(mascara: str) -> None:
    """131→132→131 dá três escritas de `ABS_RX` e três SYN.

    A primeira é a do nó recém-nascido (todo eixo sai uma vez); as duas
    seguintes são o chiado, e nenhuma delas é engolida."""
    ecodes = pytest.importorskip("evdev").ecodes
    from hefesto_dualsense4unix.integrations.uinput_gamepad import UinputGamepad

    pad = UinputGamepad.for_flavor(mascara)
    gravador = _Gravador()
    pad._device = gravador
    pad._ecodes = ecodes
    for rx in (131, 132, 131):
        pad.forward_analog(lx=128, ly=128, rx=rx, ry=128, l2=0, r2=0)
    rx_escritos = [
        v for t, c, v in gravador.escritas if t == ecodes.EV_ABS and c == ecodes.ABS_RX
    ]
    assert rx_escritos == [131, 132, 131]
    assert gravador.syns == 3
    pad.forward_analog(lx=128, ly=128, rx=131, ry=128, l2=0, r2=0)
    assert gravador.syns == 3, "valor repetido não escreve nada"


# ---------------------------------------------------------------------------
# 4. O pad `uhid`: o DualSense, nos dois relógios
# ---------------------------------------------------------------------------

#: O byte do `RX` no report `0x01`: o id do report, e o corpo começa em `lx`.
_BYTE_DO_RX = 1 + 2


@pytest.fixture
def _uhid() -> Iterator[tuple[Any, list[bytes]]]:
    """O `UhidDualSense` de verdade com o fd no `/dev/null` e os reports gravados."""
    from hefesto_dualsense4unix.integrations.uhid_gamepad import UhidDualSense

    pad = UhidDualSense(player=2, blueprint=None)
    pad._fd = os.open(os.devnull, os.O_WRONLY)
    reports: list[bytes] = []
    enviar = pad.send_report

    def _gravar(report: bytes) -> bool:
        reports.append(bytes(report))
        return enviar(report)

    pad.send_report = _gravar  # type: ignore[method-assign]
    try:
        yield pad, reports
    finally:
        fd, pad._fd = pad._fd, None
        os.close(fd)


def test_o_pad_uhid_leva_cada_troca_num_report(_uhid: tuple[Any, list[bytes]]) -> None:
    """Sem o movimento no ar, quem emite é o tique: cada troca sai num report."""
    pad, reports = _uhid
    for rx in (131, 132, 131, 132):
        pad.forward_analog(lx=128, ly=128, rx=rx, ry=128, l2=0, r2=0)
    assert [r[_BYTE_DO_RX] for r in reports] == [131, 132, 131, 132]
    pad.forward_analog(lx=128, ly=128, rx=132, ry=128, l2=0, r2=0)
    assert len(reports) == 4, "valor repetido não emite report"


def test_com_o_movimento_no_ar_a_troca_sai_no_report_seguinte_do_leitor(
    _uhid: tuple[Any, list[bytes]],
) -> None:
    """Com o `_motion_streaming`, o relógio é o do físico: o tique só guarda,
    e a troca pega carona no report seguinte do leitor, sem report a mais."""
    from hefesto_dualsense4unix.integrations import uhid_gamepad

    pad, reports = _uhid
    pad._motion_streaming = True
    for n, rx in enumerate((131, 132, 131, 132)):
        pad.forward_analog(lx=128, ly=128, rx=rx, ry=128, l2=0, r2=0)
        assert len(reports) == n, "o tique não emite com o leitor no relógio"
        janela = bytes([n + 1]) + bytes(uhid_gamepad._MOTION_WINDOW_LEN - 1)
        pad.forward_motion(janela)
        assert reports[-1][_BYTE_DO_RX] == rx
    assert len(reports) == 4
