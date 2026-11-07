"""A mira nos quatro jogadores: `aplicar_o_movimento` real, P1 pelo `dispatch_gamepad`, P2 a P4
pelo `CoopManager.forward_all`, o `Daemon` e o `SensorHub` do produto, só o nó dublado.

Prova só no P1 não fecha: quem gira mexe só o próprio analógico, com o lado, a inversão, as
sensibilidades e o gatilho dele, com o jogador em qualquer posição e a mesa em qualquer transporte.

MORDIDAS: trocar o `_mira_da_peca` por um estado único reprova a matriz; tirar os eixos do
`_forward_analog_procon` reprova a máscara `nintendo`; tirar o portão do parado
em `aplicar_o_movimento` reprova o esbarrão; tirar a busca pela forma normalizada de `_abrir_um`
reprova tudo com endereço escrito de outro jeito.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from evdev import ecodes

from hefesto_dualsense4unix.core import roteador_de_movimento as rot
from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.core.remapeamento_de_botao import GATILHOS
from hefesto_dualsense4unix.core.virtual_motion import REGISTRO, chave_de_sensor
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.lifecycle import Daemon
from hefesto_dualsense4unix.daemon.sensor_hub import SensorHub
from hefesto_dualsense4unix.daemon.subsystems import coop as co
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.integrations.uinput_gamepad import UinputGamepad
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import (
    ControllerOverrides,
    MatchAny,
    Profile,
    ProfileMovimentoConfig,
)
from hefesto_dualsense4unix.testing import FakeController

P1, P2, P3, P4 = (f"aa:bb:cc:00:00:0{n}" for n in range(1, 5))
QUATRO = (P1, P2, P3, P4)
TIQUE_S = 0.016
A_ESQUERDA = (0.0, 90.0, 0.0)
PARA_CIMA = (90.0, 0.0, 0.0)
EM_PE = (0.0, 1.0, 0.0)
PARADO = (0.0, 0.0, 0.0)


@pytest.fixture(autouse=True)
def _registro_limpo() -> Iterator[None]:
    REGISTRO.limpar()
    yield
    REGISTRO.limpar()


class _Relogio:
    """O relógio do tique: o módulo `time` de verdade, com o `monotonic` na mão da régua."""

    def __init__(self) -> None:
        self.agora = 1000.0

    def monotonic(self) -> float:
        return self.agora

    def __getattr__(self, nome: str) -> Any:
        return getattr(time, nome)


class _NoDeMovimento:
    """O nó «Motion Sensors» de uma peça: entrega o que a mão faz, com o tempo do kernel."""

    def __init__(self) -> None:
        self.giro = PARADO
        self.acel = EM_PE

    def start(self) -> bool:
        return True

    def stop(self) -> None:
        pass

    def snapshot(self) -> Any:
        return SimpleNamespace(x=self.giro[0], y=self.giro[1], z=self.giro[2])

    def accel_snapshot(self) -> Any:
        return SimpleNamespace(x=self.acel[0], y=self.acel[1], z=self.acel[2])

    def consume_angulo(self) -> tuple[tuple[float, float, float], float]:
        gx, gy, gz = self.giro
        return (gx * TIQUE_S, gy * TIQUE_S, gz * TIQUE_S), TIQUE_S


class _Pad:
    """O gamepad virtual: guarda o que o JOGO receberia."""

    def __init__(self) -> None:
        self.analog: list[dict[str, int]] = []

    def forward_analog(self, **eixos: int) -> None:
        self.analog.append(eixos)

    def forward_buttons(self, pressed: frozenset[str]) -> None:
        pass

    def centro(self) -> bool:
        return all(self.analog[-1][e] == 128 for e in ("lx", "ly", "rx", "ry"))


class _Mesa:
    def __init__(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        transporte: str,
        pecas: dict[str, dict[str, Any]],
        *,
        secundarios: tuple[str, ...] = (P2, P3, P4),
        mesa: dict[str, Any] | None = None,
    ) -> None:
        self.relogio = _Relogio()
        monkeypatch.setattr(gp, "time", self.relogio)
        monkeypatch.setattr(gp, "_reconciliar_launch", lambda d: None)
        monkeypatch.setattr(gp, "_avisar_troca_de_modo", lambda d: None)
        self.transporte = transporte
        self.nos = {uniq: _NoDeMovimento() for uniq in (P1, *secundarios)}
        self.botoes: dict[str, frozenset[str]] = {u: frozenset() for u in self.nos}
        self.hub = SensorHub(
            motion_factory=lambda uniq, node: self.nos[uniq],
            touch_factory=lambda uniq, node: _NoDeMovimento(),
            gamepad_factory=lambda uniq, node: _NoDeMovimento(),
            descobrir_motion=lambda: {
                chave_de_sensor(u): Path(f"/dev/input/event-{n}")
                for n, u in enumerate(self.nos)
            },
            descobrir_touch=dict,
            descobrir_gamepad=dict,
            auto_manutencao=False,
        )
        self.hub._watch = SimpleNamespace(poll=lambda: False)
        controle = FakeController(transport=transporte)  # type: ignore[arg-type]
        controle.primary_uniq = P1  # type: ignore[attr-defined]
        self.daemon = Daemon(controller=controle)
        gerente = ProfileManager(controller=controle, store=self.daemon.store)
        servidor = IpcServer(
            controller=controle,
            store=self.daemon.store,
            profile_manager=gerente,
            socket_path=tmp_path / "mira.sock",
            daemon=self.daemon,
        )
        servidor._sensor_hub = self.hub
        self.daemon._ipc_server = servidor
        gerente.apply_movimento(
            Profile(
                name="A mesa",
                match=MatchAny(type="any"),
                movimento=ProfileMovimentoConfig(**mesa) if mesa is not None else None,
                controllers={
                    chave_de_sensor(uniq): ControllerOverrides(
                        movimento=ProfileMovimentoConfig(**campos)
                    )
                    for uniq, campos in pecas.items()
                },
            )
        )
        self.coop = co.CoopManager(self.daemon)
        self.pads = {P1: _Pad()}
        self.daemon._gamepad_device = self.pads[P1]
        for n, uniq in enumerate(secundarios, start=2):
            self.pads[uniq] = _Pad()
            self.coop._players[uniq] = co._SecondaryPlayer(
                identity=uniq,
                evdev_path=f"/dev/input/event{n}",
                reader=SimpleNamespace(
                    snapshot=lambda u=uniq: SimpleNamespace(
                        lx=128, ly=128, rx=128, ry=128, l2_raw=0, r2_raw=0,
                        buttons_pressed=self.botoes[u]),
                    grab_state="held",
                ),
                player_index=n,
                vpad=self.pads[uniq],
            )
        self.tiques(2)
        self.hub.reconciliar()

    def tiques(self, quantos: int) -> None:
        estado = ControllerState(
            battery_pct=100, l2_raw=0, r2_raw=0, connected=True,
            transport=self.transporte,  # type: ignore[arg-type]
        )
        for _ in range(quantos):
            self.relogio.agora += TIQUE_S
            gp.dispatch_gamepad(self.daemon, estado, self.botoes[P1])
            self.coop.forward_all()

    def segundos(self, quantos: float) -> None:
        self.tiques(round(quantos / TIQUE_S))

    def gira(self, uniq: str, giro: tuple[float, float, float]) -> dict[str, int]:
        self.nos[uniq].giro = giro
        self.tiques(4)
        ultimo = dict(self.pads[uniq].analog[-1])
        self.nos[uniq].giro = PARADO
        self.tiques(4)
        return ultimo


def _arranjos() -> dict[str, dict[str, Any]]:
    return {
        P1: {"destino": "analogico_direito"},
        P2: {"destino": "analogico_direito", "sensibilidade_h": 10, "inverter_horizontal": True},
        P3: {"destino": "analogico_esquerdo", "sensibilidade_v": 0},
        P4: {"destino": "analogico_direito", "gatilho": "l2"},
    }


@pytest.mark.parametrize("transporte", ["usb", "bt"])
@pytest.mark.parametrize("quem", QUATRO)
def test_quem_gira_mexe_so_o_proprio_analogico(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, transporte: str, quem: str
) -> None:
    mesa = _Mesa(monkeypatch, tmp_path, transporte, _arranjos())
    mesa.botoes[P4] = frozenset({GATILHOS["l2"]})
    mesa.nos[quem].giro = A_ESQUERDA
    mesa.tiques(4)
    for uniq, pad in mesa.pads.items():
        if uniq != quem:
            assert pad.centro(), f"{quem} girou e o analógico de {uniq} andou: {pad.analog[-1]}"
    assert not mesa.pads[quem].centro(), f"{quem} girou e não mirou"


def test_cada_um_com_o_seu_lado_sentido_e_sensibilidade(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    mesa = _Mesa(monkeypatch, tmp_path, "usb", _arranjos())
    mesa.botoes[P4] = frozenset({GATILHOS["l2"]})
    base = rot.ArranjoDeMovimento(destino=rot.DESTINO_ANALOGICO_DIREITO)
    padrao = 128 + rot.deflexao(A_ESQUERDA, base)[0]
    assert mesa.gira(P1, A_ESQUERDA)["rx"] == pytest.approx(padrao, abs=1)
    forte = mesa.gira(P2, A_ESQUERDA)["rx"]
    assert forte > 128 and forte - 128 > 128 - padrao, "o P2 é invertido e mais sensível"
    esquerdo = mesa.gira(P3, A_ESQUERDA)
    assert esquerdo["lx"] == pytest.approx(padrao, abs=1)
    assert esquerdo["rx"] == 128
    assert mesa.gira(P3, PARA_CIMA)["ly"] == 128, "o P3 pôs a vertical em 0"
    assert mesa.gira(P1, PARA_CIMA)["ry"] < 128


def test_o_gatilho_e_de_cada_um(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    mesa = _Mesa(monkeypatch, tmp_path, "bt", _arranjos())
    assert mesa.gira(P4, A_ESQUERDA)["rx"] == 128
    mesa.botoes[P4] = frozenset({GATILHOS["l2"]})
    assert mesa.gira(P4, A_ESQUERDA)["rx"] != 128


@pytest.mark.parametrize(
    ("transporte", "presentes"),
    [
        ("usb", (P3,)),
        ("bt", (P4,)),
        ("usb", (P2, P4)),
        ("bt", (P3, P4)),
    ],
)
def test_o_jogador_em_qualquer_posicao_com_buraco_no_meio(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, transporte: str, presentes: tuple[str, ...]
) -> None:
    pecas = {u: {"destino": "analogico_direito"} for u in presentes}
    mesa = _Mesa(monkeypatch, tmp_path, transporte, pecas, secundarios=presentes)
    for uniq in presentes:
        assert mesa.gira(uniq, A_ESQUERDA)["rx"] < 128
    assert mesa.gira(P1, A_ESQUERDA)["rx"] == 128, "o P1 não acendeu o chip"


def test_soltar_o_gatilho_leva_o_resto_junto(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pecas = {P4: {"destino": "analogico_direito", "gatilho": "l2"}}
    mesa = _Mesa(monkeypatch, tmp_path, "bt", pecas)
    mesa.botoes[P4] = frozenset({GATILHOS["l2"]})
    mesa.nos[P4].giro = (0.0, 33.0, 0.0)
    mesa.tiques(3)
    estado = rot._mira_da_peca(mesa.daemon.store, P4)
    assert estado.resto_h != 0.0
    mesa.botoes[P4] = frozenset()
    mesa.tiques(1)
    assert estado.resto_h == 0.0


def test_a_mira_da_mesa_vale_para_quem_nao_tem_opiniao(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    mesa = _Mesa(monkeypatch, tmp_path, "usb", {}, mesa={"destino": "analogico_direito"})
    for uniq in QUATRO:
        assert mesa.gira(uniq, A_ESQUERDA)["rx"] < 128


def _a_peca_descansa(mesa: _Mesa, uniq: str) -> None:
    mesa.nos[uniq].giro = PARADO
    mesa.segundos(rot.TEMPO_DO_PARADO_S + 0.5)


@pytest.mark.parametrize("quem", QUATRO)
def test_o_esbarrao_na_peca_parada_nao_mexe_no_analogico(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, quem: str
) -> None:
    pecas = {u: {"destino": "analogico_direito"} for u in QUATRO}
    mesa = _Mesa(monkeypatch, tmp_path, "usb", pecas)
    _a_peca_descansa(mesa, quem)
    mesa.nos[quem].giro = (0.0, 200.0, 0.0)
    mesa.nos[quem].acel = (0.1, 0.99, 0.0)
    antes = len(mesa.pads[quem].analog)
    mesa.segundos(0.1)
    mesa.nos[quem].giro = PARADO
    mesa.nos[quem].acel = EM_PE
    mesa.segundos(0.1)
    for eixos in mesa.pads[quem].analog[antes:]:
        assert eixos["rx"] == 128, f"o toque na mesa andou o analógico de {quem}: {eixos}"


@pytest.mark.parametrize("quem", QUATRO)
def test_a_mao_que_pega_e_gira_anda(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, quem: str
) -> None:
    pecas = {u: {"destino": "analogico_direito"} for u in QUATRO}
    mesa = _Mesa(monkeypatch, tmp_path, "bt", pecas)
    _a_peca_descansa(mesa, quem)
    mesa.nos[quem].giro = A_ESQUERDA
    mesa.nos[quem].acel = (0.0, 0.8, 0.6)
    mesa.segundos(rot.TEMPO_DA_PEGADA_S + 0.1)
    assert mesa.pads[quem].analog[-1]["rx"] < 128


def test_so_a_peca_largada_para_de_mirar(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pecas = {u: {"destino": "analogico_direito"} for u in QUATRO}
    mesa = _Mesa(monkeypatch, tmp_path, "usb", pecas)
    for volta in range(round((rot.TEMPO_DO_PARADO_S + 0.5) / TIQUE_S)):
        mesa.nos[P3].giro = (0.0, 40.0 if volta % 2 else 30.0, 0.0)
        mesa.tiques(1)
    assert rot.mira_parada(mesa.daemon.store, P2, mesa.relogio.agora)
    assert not rot.mira_parada(mesa.daemon.store, P3, mesa.relogio.agora)
    assert mesa.pads[P3].analog[-1]["rx"] < 128


def test_mesmo_parado_e_de_quem_quer_a_mira_sem_a_pausa(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pecas = {
        P1: {"destino": "analogico_direito"},
        P2: {"destino": "analogico_direito", "mesmo_parado": True},
    }
    mesa = _Mesa(monkeypatch, tmp_path, "usb", pecas, secundarios=(P2,))
    mesa.segundos(rot.TEMPO_DO_PARADO_S + 0.5)
    mesa.nos[P2].giro = A_ESQUERDA
    mesa.nos[P1].giro = A_ESQUERDA
    mesa.tiques(2)
    assert mesa.pads[P2].analog[-1]["rx"] < 128
    assert mesa.pads[P1].analog[-1]["rx"] == 128


def test_o_peso_de_um_jogador_nao_pesa_nos_outros(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pecas = {u: {"destino": "analogico_direito"} for u in QUATRO}
    mesa = _Mesa(monkeypatch, tmp_path, "usb", pecas)
    livre = mesa.gira(P2, A_ESQUERDA)["rx"]
    rot.PESO_DA_MIRA.pedir("teste", P3, 0.3, 5000)
    try:
        assert mesa.gira(P2, A_ESQUERDA)["rx"] == livre
        pesado = mesa.gira(P3, A_ESQUERDA)["rx"]
    finally:
        rot.PESO_DA_MIRA.soltar()
    assert livre < pesado < 128 - 33


def test_o_hub_acha_o_no_pelo_endereco_em_qualquer_grafia(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A descoberta devolve a forma normalizada, e a identidade chega com dois-pontos."""
    mesa = _Mesa(monkeypatch, tmp_path, "usb", {P2: {"destino": "analogico_direito"}})
    assert ":" in P2
    assert P2 in mesa.hub._motion
    assert mesa.hub.velocidade_do_movimento(P2) == PARADO


def test_a_queda_de_amostra_nao_prende_o_analogico(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pecas = {P2: {"destino": "analogico_direito"}}
    mesa = _Mesa(monkeypatch, tmp_path, "bt", pecas)
    mesa.nos[P2].giro = A_ESQUERDA
    mesa.tiques(3)
    assert mesa.pads[P2].analog[-1]["rx"] < 128

    def sem_amostra() -> tuple[tuple[float, float, float], float]:
        return PARADO, 0.0

    monkeypatch.setattr(mesa.nos[P2], "consume_angulo", sem_amostra)
    mesa.tiques(1)
    assert mesa.pads[P2].analog[-1]["rx"] < 128, "um tique sem amostra repete o último"
    mesa.segundos(rot.SILENCIO_DA_AMOSTRA_S + 0.05)
    assert mesa.pads[P2].analog[-1]["rx"] == 128, "o analógico ficou preso na queda"


def test_o_tique_sem_amostra_nao_herda_o_giro_do_outro(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pecas = {uniq: {"destino": "analogico_direito"} for uniq in (P1, P2)}
    mesa = _Mesa(monkeypatch, tmp_path, "bt", pecas)

    def sem_amostra() -> tuple[tuple[float, float, float], float]:
        return PARADO, 0.0

    monkeypatch.setattr(mesa.nos[P2], "consume_angulo", sem_amostra)
    mesa.nos[P1].giro = A_ESQUERDA
    mesa.tiques(3)
    assert mesa.pads[P1].analog[-1]["rx"] < 128
    assert mesa.pads[P2].analog[-1]["rx"] == 128, "o giro de um andou no pad do outro"


class _NoDoPad:
    """O nó uinput do pad de cada máscara: guarda o último valor de cada eixo."""

    def __init__(self) -> None:
        self.eixos: dict[int, int] = {}

    def write(self, tipo: int, codigo: int, valor: int) -> None:
        if tipo == ecodes.EV_ABS:
            self.eixos[codigo] = valor

    def syn(self) -> None:
        pass


@pytest.mark.parametrize("transporte", ["usb", "bt"])
@pytest.mark.parametrize(
    "mascaras",
    [
        {P1: "xbox", P2: "nintendo", P3: "dualsense", P4: "xbox"},
        {P1: "nintendo", P2: "xbox", P3: "nintendo", P4: "dualsense"},
    ],
)
def test_toda_mascara_recebe_o_analogico_de_quem_mira(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, transporte: str, mascaras: dict[str, str]
) -> None:
    mesa = _Mesa(monkeypatch, tmp_path, transporte, {u: {"destino": "analogico_direito"}
                                                     for u in QUATRO})
    nos = {uniq: _NoDoPad() for uniq in QUATRO}
    for uniq, mascara in mascaras.items():
        pad = UinputGamepad(flavor=mascara)
        pad._device = nos[uniq]
        pad._ecodes = ecodes
        if uniq == P1:
            mesa.daemon._gamepad_device = pad
        else:
            mesa.coop._players[uniq].vpad = pad
    for uniq in QUATRO:
        mesa.nos[uniq].giro = A_ESQUERDA
    mesa.tiques(4)
    for uniq, no in nos.items():
        assert no.eixos[ecodes.ABS_RX] < 60, f"{mascaras[uniq]} de {uniq}: {no.eixos}"


@pytest.mark.parametrize("transporte", ["usb", "bt"])
@pytest.mark.parametrize("quem", QUATRO)
def test_o_volante_com_o_controle_de_pe_mira_em_cada_jogador(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, transporte: str, quem: str
) -> None:
    """Medido em 06/11: com o controle de pé, o gesto de volante sai em `ABS_RY`."""
    mesa = _Mesa(monkeypatch, tmp_path, transporte, _arranjos())
    mesa.botoes[P4] = frozenset({GATILHOS["l2"]})
    mesa.nos[quem].acel = (0.0, 0.0, -1.0)
    mesa.tiques(2)
    mesa.nos[quem].giro = A_ESQUERDA
    mesa.tiques(4)
    assert not mesa.pads[quem].centro(), f"{quem} virou como volante e nada andou"
