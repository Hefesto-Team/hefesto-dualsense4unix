"""BROADCAST-QUE-NAO-MENTE-01 (02/08) — `led.set` sem `uniq` APLICAVA NADA.

Defeito medido na máquina dela, com dois DualSense na mesa e a paleta
automática ligada: um ``led.set`` com ``rgb=[0,255,0]`` e SEM ``uniq``
respondia ``{"status": "ok"}`` e o sysfs não mudava — os controles seguiam
azul (slot 1) e vermelho (slot 2). O MESMO pedido COM ``uniq`` nos dois MACs
pintava os dois de verde, e o verde ficava.

A causa é a ORDEM DAS CAMADAS do merge, não a escrita: o broadcast grava a cor
no ``_desired_default`` (``_record_desired_locked`` com alvo ``None``), que fica
ABAIXO da camada automática do slot (COR-03) em ``_merged_desired_for_key``;
o ``reassert_resolved_outputs`` do próprio handler (fix cross-cutting U x N)
re-resolve por controle e repinta a paleta por cima. O caminho por-``uniq``
sempre funcionou porque ``apply_output_for`` grava em ``_desired_by_uniq``, que
está ACIMA da automática no mesmo merge.

Cura: o broadcast passou a registrar a intenção na camada da USUÁRIA de cada
controle conectado (``_registrar_em_todos``) — a mesma disciplina que a GUI já
tinha desde a R-14, agora no daemon, valendo também para a CLI e para qualquer
chamada IPC.

Instrumento: backend REAL (``PyDualSenseController``) com handles e nós sysfs
falsos — é o merge de verdade que está sob medição, não um dublê dele. O
provider automático é o mesmo contrato do ``make_auto_output_provider``
(``daemon/subsystems/identity.py``) e as cores saem de ``player_slot_color``,
para a medição usar a MESMA paleta que ela viu na tela.

Falha-sem (cura arrancada): a última escrita em CADA nó volta a ser a cor da
paleta, e ``aplicado_em`` some da resposta.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.core import backend_pydualsense as bp
from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.core.led_control import (
    player_led_pattern,
    player_slot_color,
)
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.testing import FakeController

#: MACs forjados na faixa aa:bb:cc (guarda de anonimato) — key do handle no
#: formato que o backend recebe do hidapi, e o `uniq` normalizado que sai do
#: `describe_controllers`.
MAC_1 = "AA:BB:CC:00:00:01"
MAC_2 = "AA:BB:CC:00:00:02"
UNIQ_1 = "aabbcc000001"
UNIQ_2 = "aabbcc000002"

#: A paleta que ela viu: slot 1 azul, slot 2 vermelho (`player_slot_color`).
AZUL = player_slot_color(1)
VERMELHO = player_slot_color(2)
VERDE = (0, 255, 0)


class _FakeLedNode:
    """Nó sysfs de LED falso (mesma forma do `_FakeLedNode` da corretora)."""

    def __init__(self) -> None:
        self.rgb_calls: list[tuple[int, int, int]] = []
        self.player_calls: list[tuple[bool, ...]] = []

    def set_rgb(self, r: int, g: int, b: int, *, verify: bool = False) -> bool:
        self.rgb_calls.append((r, g, b))
        return True

    def set_players(self, bits: tuple[bool, ...]) -> bool:
        self.player_calls.append(tuple(bits))
        return True

    def set_players_verified(self, bits: tuple[bool, ...]) -> bool:
        return self.set_players(bits)

    def invalidate_cache(self) -> None:
        return None


def _fake_pydual_handle() -> Any:
    """Handle pydualsense falso — `connected=True` é o que o describe lê.

    Sem esse atributo o `describe_controllers` do backend real marca a entrada
    como desconectada e o fan-out por MAC nem seria tentado: o teste passaria
    pelo motivo errado.
    """
    from types import SimpleNamespace

    from pydualsense.pydualsense import DSAudio, DSLight, DSTrigger

    return SimpleNamespace(
        connected=True,
        triggerL=DSTrigger(),
        triggerR=DSTrigger(),
        light=DSLight(),
        audio=DSAudio(),
        _raw_trigger_left=None,
        _raw_trigger_right=None,
    )


def _provider_da_paleta(
    *, cores: bool = True, numeros: bool = False
) -> Any:
    """Provider automático (COR-03) com o MESMO contrato do daemon.

    Devolve a cor do slot (D11) e/ou o padrão de número (D7) por MAC; `None`
    para quem não está na mesa — exatamente como `make_auto_output_provider`.
    """
    slots = {UNIQ_1: 1, UNIQ_2: 2}

    def provider(uniq: str) -> Any:
        slot = slots.get(uniq)
        if slot is None:
            return None
        campos: dict[str, Any] = {}
        if cores:
            campos["led"] = player_slot_color(slot)
        if numeros:
            campos["player_leds"] = player_led_pattern(slot)
        if not campos:
            return None
        return bp._DesiredOutput(**campos)

    return provider


def _mesa_com_dois_controles(
    tmp_path: Path, *, cores: bool = True, numeros: bool = False
) -> tuple[IpcServer, bp.PyDualSenseController, _FakeLedNode, _FakeLedNode]:
    """Backend real com dois controles conectados e a paleta automática ligada."""
    ctl = bp.PyDualSenseController()
    ctl._handles = {MAC_1: _fake_pydual_handle(), MAC_2: _fake_pydual_handle()}
    no_1 = _FakeLedNode()
    no_2 = _FakeLedNode()
    ctl._sysfs = {MAC_1: no_1, MAC_2: no_2}
    ctl.set_auto_output_provider(_provider_da_paleta(cores=cores, numeros=numeros))
    # Sem jogo: a camada GAME fica FORA do merge (o gate da Onda N é medido em
    # `test_o_jogo_continua_vencendo_o_broadcast`, à parte).
    ctl.set_game_authority_provider(lambda: "daemon")
    store = StateStore()
    store.update_controller_state(
        ControllerState(
            battery_pct=100, l2_raw=0, r2_raw=0, connected=True, transport="usb"
        )
    )
    server = IpcServer(
        controller=ctl,
        store=store,
        profile_manager=ProfileManager(controller=ctl, store=store),
        socket_path=tmp_path / "broadcast.sock",
    )
    return server, ctl, no_1, no_2


@pytest.mark.asyncio
async def test_broadcast_pinta_os_dois_controles_de_verdade(tmp_path: Path) -> None:
    """O pedido SEM `uniq` tem de chegar ao hardware dos dois — era o defeito.

    Falha-sem: a última escrita em cada nó é a cor da paleta (azul e vermelho),
    que é exatamente o que ela mediu no sysfs depois do "ok".
    """
    server, _ctl, no_1, no_2 = _mesa_com_dois_controles(tmp_path)

    resultado = await server._handle_led_set({"rgb": list(VERDE)})

    assert resultado["status"] == "ok"
    assert no_1.rgb_calls[-1] == VERDE, "controle 1 ficou com a cor da paleta"
    assert no_2.rgb_calls[-1] == VERDE, "controle 2 ficou com a cor da paleta"


@pytest.mark.asyncio
async def test_broadcast_sobrevive_ao_proximo_reassert(tmp_path: Path) -> None:
    """A cor tem de estar REGISTRADA, não só ter sido a última escrita.

    A defesa de exibição (NUMA-03) e todo hotplug re-resolvem pelo mesmo merge:
    se a intenção não ficasse na camada certa, a paleta voltaria segundos
    depois — o defeito só teria mudado de horário.
    """
    server, ctl, no_1, no_2 = _mesa_com_dois_controles(tmp_path)
    await server._handle_led_set({"rgb": list(VERDE)})
    no_1.rgb_calls.clear()
    no_2.rgb_calls.clear()

    ctl.reassert_resolved_outputs()

    assert no_1.rgb_calls[-1] == VERDE
    assert no_2.rgb_calls[-1] == VERDE


@pytest.mark.asyncio
async def test_resposta_diz_em_quais_controles_a_cor_ficou(tmp_path: Path) -> None:
    """`aplicado_em` publica os MACs — o "ok" sozinho não distinguia nada."""
    server, _ctl, _no_1, _no_2 = _mesa_com_dois_controles(tmp_path)

    resultado = await server._handle_led_set({"rgb": list(VERDE)})

    assert resultado["aplicado_em"] == [UNIQ_1, UNIQ_2]


@pytest.mark.asyncio
async def test_caminho_com_uniq_continua_mirando_so_um(tmp_path: Path) -> None:
    """Regressão do PERFIL-05: com `uniq`, o outro controle NÃO pode mudar."""
    server, _ctl, no_1, no_2 = _mesa_com_dois_controles(tmp_path)

    resultado = await server._handle_led_set({"rgb": list(VERDE), "uniq": UNIQ_2})

    assert resultado["aplicado_em"] == [UNIQ_2]
    assert no_2.rgb_calls[-1] == VERDE
    assert no_1.rgb_calls[-1] == AZUL, "o controle não mirado perdeu a cor do slot"


@pytest.mark.asyncio
async def test_o_jogo_continua_vencendo_o_broadcast(tmp_path: Path) -> None:
    """O fix cross-cutting U x N (2026-07-20) segue de pé.

    A camada da usuária entrou ABAIXO da camada GAME de propósito: com uma
    sessão de jogo aberta, a cor que o jogo pintou tem de vencer o pedido
    manual no mesmo instante. Falha-sem (cura errada): quem arrancar o
    `reassert_resolved_outputs` do handler vê a cor manual grudar por cima do
    jogo — o furo que aquele fix fechou.
    """
    server, ctl, no_1, no_2 = _mesa_com_dois_controles(tmp_path)
    ctl.set_game_authority_provider(lambda: "game")
    assert ctl.set_game_output_for(MAC_1, led=(255, 0, 255)) is True
    no_1.rgb_calls.clear()
    no_2.rgb_calls.clear()

    await server._handle_led_set({"rgb": list(VERDE)})

    assert no_1.rgb_calls[-1] == (255, 0, 255), "o jogo perdeu o controle dele"
    assert no_2.rgb_calls[-1] == VERDE, "quem o jogo não usa ficou sem a cor dela"


@pytest.mark.asyncio
async def test_player_set_broadcast_desenha_de_verdade(tmp_path: Path) -> None:
    """Mesmo defeito, mesma cura: a numeração automática vencia o broadcast."""
    server, _ctl, no_1, no_2 = _mesa_com_dois_controles(
        tmp_path, cores=False, numeros=True
    )
    bits = (True, False, False, False, True)

    resultado = await server._handle_led_player_set({"bits": list(bits)})

    assert resultado["bits"] == list(bits)  # contrato antigo intacto
    assert resultado["aplicado_em"] == [UNIQ_1, UNIQ_2]
    assert no_1.player_calls[-1] == bits
    assert no_2.player_calls[-1] == bits


@pytest.mark.asyncio
async def test_backend_sem_api_por_uniq_diz_que_nao_registrou(
    tmp_path: Path,
) -> None:
    """Caminho degradado HONESTO: escreve pelo clássico e não finge registro.

    Backend sem `apply_output_for`/`describe_controllers` (FakeController,
    backend legado) não tem como registrar por MAC — e é justamente aí que ele
    também não tem paleta automática nenhuma para perder a disputa. A resposta
    diz `aplicado_em: []` em vez de inventar uma lista.
    """
    fc = FakeController(transport="usb")
    fc.connect()
    store = StateStore()
    server = IpcServer(
        controller=fc,
        store=store,
        profile_manager=ProfileManager(controller=fc, store=store),
        socket_path=tmp_path / "degradado.sock",
    )

    resultado = await server._handle_led_set({"rgb": list(VERDE)})

    assert resultado["status"] == "ok"
    assert resultado["aplicado_em"] == []
    assert fc.last_led is not None and fc.last_led.color == VERDE
