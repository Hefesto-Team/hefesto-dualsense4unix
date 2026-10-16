"""O analógico chega ao jogo no ritmo do controle (O-ANALOGICO-CHEGA-AO-JOGO-...-01).

O `EV_ABS` que anda duas contagens ou mais acorda a entrega no `EV_SYN` que fecha o quadro, e a
volta do aperto lê o snapshot fresco do leitor também para a cor que carrega o primário. Leitor,
pad e laço de mentira; nada toca o aparelho.
"""

from __future__ import annotations

import asyncio
import itertools
import time
from pathlib import Path
from types import MethodType, SimpleNamespace
from typing import Any

import pytest
from evdev import ecodes

from hefesto_dualsense4unix.core import evdev_reader as er
from hefesto_dualsense4unix.core import roteador_de_movimento as roteador
from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.core.evdev_reader import EvdevReader, MotionSensorReader
from hefesto_dualsense4unix.daemon import lifecycle as lc
from hefesto_dualsense4unix.daemon.lifecycle import Daemon
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.daemon.subsystems import coop as co
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from tests.unit.test_o_aperto_acorda_o_tique import (
    _apertar,
    _Evento,
    _gerente,
    _leitor,
    _LacoForaDaMesa,
    _numa_thread,
)

#: O teto declarado do orçamento: uma volta por quadro do aparelho (250 Hz no cabo).
TETO_DE_VOLTAS_POR_S = 250
#: O teto de CPU do fio do laço com o stick girando, por segundo: 15% de um núcleo para os três
#: controles. Medido em 16/10: 27,5 ms/s. Uma volta que custa 1 ms passa de 150 ms/s.
TETO_DE_CPU_DO_LACO_S = 0.150
#: A folga da chegada, medida em relógio de parede com a máquina dividida por três vagas de
#: pytest; o defeito que a régua pega espera o tique de 1 s do laço, não 30 ms.
CHEGADA_MAXIMA_S = 0.030


class _Relogio:
    """Os eventos do `EV_SYN` que o kernel manda: uma hora só por quadro."""

    def __init__(self) -> None:
        self.agora = 100.0

    def sincronia(self) -> Any:
        self.agora += 0.004
        return SimpleNamespace(
            type=ecodes.EV_SYN,
            code=ecodes.SYN_REPORT,
            value=0,
            sec=int(self.agora),
            usec=int((self.agora % 1) * 1e6),
        )


class _PadDoJogo:
    """O pad virtual de mentira (uhid DualSense ou uinput Xbox: o mesmo `forward_analog`)."""

    def __init__(self) -> None:
        self.analogicos: list[tuple[float, dict[str, int]]] = []

    def forward_analog(self, **eixos: int) -> None:
        self.analogicos.append((time.monotonic(), dict(eixos)))

    def forward_buttons(self, pressed: frozenset[str]) -> None:
        pass

    def chegou(self, **procurado: int) -> float | None:
        for em, eixos in self.analogicos:
            if all(eixos.get(k) == v for k, v in procurado.items()):
                return em
        return None


def _mexer(leitor: EvdevReader, **eixos: int) -> None:
    """Um quadro: os `EV_ABS` dos eixos e o `EV_SYN` que o fecha."""
    codigos = {
        "lx": ecodes.ABS_X,
        "ly": ecodes.ABS_Y,
        "rx": ecodes.ABS_RX,
        "ry": ecodes.ABS_RY,
        "l2": ecodes.ABS_Z,
        "r2": ecodes.ABS_RZ,
    }
    for nome, valor in eixos.items():
        leitor._handle_event(_Evento(ecodes.EV_ABS, codigos[nome], valor), ecodes)
    leitor._handle_event(_Evento(ecodes.EV_SYN, ecodes.SYN_REPORT, 0), ecodes)


@pytest.fixture(autouse=True)
def _o_laco_sem_a_maquina(monkeypatch: pytest.MonkeyPatch) -> Any:
    """O que o laço faz e toca a máquina fica de fora, como no teste do aperto."""
    monkeypatch.setattr(co.CoopManager, "sync", lambda self: None)
    monkeypatch.setattr(co.CoopManager, "_recolher_os_cedidos", lambda self: None)
    monkeypatch.setattr(co.CoopManager, "_promote_pending", lambda self: None)
    monkeypatch.setattr(lc, "reconciliar_as_mascaras", lambda daemon: None)
    monkeypatch.setattr(gp, "_reconciliar_launch", lambda d: None)
    monkeypatch.setattr(gp, "_avisar_troca_de_modo", lambda d: None)
    yield
    er.definir_o_despertador(None)


@pytest.fixture
def despertares() -> list[float]:
    """Cada acordar do leitor, com a hora."""
    horas: list[float] = []
    er.definir_o_despertador(lambda: horas.append(time.monotonic()))
    return horas


def _daemon_do_primario(
    leitor: EvdevReader, pad: _PadDoJogo, *, transporte: str = "usb"
) -> Any:
    daemon = SimpleNamespace(
        controller=SimpleNamespace(_evdev=leitor, is_connected=lambda: True),
        store=StateStore(),
        _gamepad_device=pad,
        _mouse_device=None,
        _input_ready_at=0.0,
        _last_state=ControllerState(
            battery_pct=80, l2_raw=0, r2_raw=0, connected=True, transport=transporte  # type: ignore[arg-type]
        ),
        _coop_manager=_gerente({}, {}),
    )
    daemon._coop_manager._daemon = daemon
    daemon._evdev_buttons_once = MethodType(Daemon._evdev_buttons_once, daemon)
    daemon._dispatch_gamepad_emulation = MethodType(Daemon._dispatch_gamepad_emulation, daemon)
    return daemon


# ---------------------------------------------------------------- o leitor acorda no quadro


def test_o_eixo_que_anda_acorda_a_entrega_no_fim_do_quadro(despertares: list[float]) -> None:
    # D-1610-A-ENTREGA-DO-EIXO-ANDA-NO-RITMO-DO-CONTROLE
    leitor = _leitor(1)
    leitor._handle_event(_Evento(ecodes.EV_ABS, ecodes.ABS_X, 168), ecodes)
    assert despertares == [], "acordou antes de o quadro fechar"
    leitor._handle_event(_Evento(ecodes.EV_SYN, ecodes.SYN_REPORT, 0), ecodes)
    assert len(despertares) == 1


def test_um_despertar_por_quadro_nunca_por_eixo(despertares: list[float]) -> None:
    """Os seis eixos andam no mesmo quadro: uma volta só."""
    leitor = _leitor(1)
    _mexer(leitor, lx=200, ly=60, rx=10, ry=250, l2=90, r2=40)
    assert len(despertares) == 1


def test_o_ruido_de_uma_contagem_no_stick_parado_nao_acorda(despertares: list[float]) -> None:
    """Mil quadros alternando ±1 em volta do repouso: nenhuma volta."""
    leitor = _leitor(1)
    for quadro in range(1000):
        _mexer(leitor, lx=128 + (1 if quadro % 2 == 0 else -1), ry=127 + quadro % 2)
    assert despertares == [], f"{len(despertares)} voltas por ruído de uma contagem"


def test_duas_contagens_acordam_e_a_ancora_anda(despertares: list[float]) -> None:
    """O limiar é de 2: 128 a 130 acorda; 130 a 131 não; 130 a 132 acorda."""
    leitor = _leitor(1)
    _mexer(leitor, lx=130)
    assert len(despertares) == 1
    _mexer(leitor, lx=131)
    assert len(despertares) == 1
    _mexer(leitor, lx=132)
    assert len(despertares) == 2


def test_a_deriva_lenta_acorda_quando_soma_duas_contagens(despertares: list[float]) -> None:
    """Uma contagem por quadro, sempre para o mesmo lado: o segundo quadro acorda."""
    leitor = _leitor(1)
    _mexer(leitor, rx=129)
    assert despertares == []
    _mexer(leitor, rx=130)
    assert len(despertares) == 1


def test_o_quadro_sem_eixo_andado_nao_acorda(despertares: list[float]) -> None:
    leitor = _leitor(1)
    leitor._handle_event(_Evento(ecodes.EV_SYN, ecodes.SYN_REPORT, 0), ecodes)
    assert despertares == []


def test_o_botao_segue_acordando_no_proprio_evento(despertares: list[float]) -> None:
    leitor = _leitor(1)
    _apertar(leitor, ecodes.BTN_SOUTH, 1)
    assert len(despertares) == 1


# ------------------------------------------------------------ a entrega ao jogo, todos os jogadores


@pytest.mark.parametrize("transporte", ["usb", "bt"])
def test_o_p1_recebe_o_eixo_fresco_na_volta_acordada(transporte: str) -> None:
    """Laço de 1 s parado: o stick de 40 contagens chega ao pad do P1 antes do tique."""
    leitor = _leitor(1)
    pad = _PadDoJogo()
    daemon = _daemon_do_primario(leitor, pad, transporte=transporte)
    moveu: dict[str, float] = {}

    def girar() -> None:
        moveu["em"] = time.monotonic()
        _mexer(leitor, lx=168)

    async def cenario() -> None:
        parada = asyncio.Event()
        # a espera de produção acorda no aperto; registra o despertador no laço
        espera = asyncio.create_task(lc._esperar_o_tique(daemon, parada, 1.0))
        await asyncio.sleep(0.1)
        _numa_thread(girar).join()
        await asyncio.sleep(0.1)
        parada.set()
        await espera

    asyncio.run(cenario())
    chegou = pad.chegou(lx=168)
    assert chegou is not None, "o eixo não chegou ao pad do P1 antes do tique"
    atraso = chegou - moveu["em"]
    print(f"[ritmo] P1 {transporte}: {atraso * 1000:.2f} ms do EV_ABS ao forward_analog")
    assert atraso < CHEGADA_MAXIMA_S, f"{atraso * 1000:.1f} ms"


@pytest.mark.parametrize("jogador", [2, 3, 4])
def test_os_jogadores_2_a_4_recebem_o_eixo_no_ritmo_do_controle(jogador: int) -> None:
    leitores = {n: _leitor(n) for n in (2, 3, 4)}
    pads = {n: _PadDoJogo() for n in (2, 3, 4)}
    daemon = _LacoForaDaMesa(_gerente(leitores, pads), poll_hz=1)  # type: ignore[arg-type]
    moveu: dict[str, float] = {}

    def girar() -> None:
        moveu["em"] = time.monotonic()
        _mexer(leitores[jogador], rx=40)

    async def cenario() -> None:
        await asyncio.sleep(0.2)
        _numa_thread(girar).join()
        await asyncio.sleep(0.15)

    asyncio.run(daemon.rodar(cenario))
    chegou = pads[jogador].chegou(rx=40)
    assert chegou is not None, f"o eixo do jogador {jogador} esperou o tique"
    atraso = chegou - moveu["em"]
    print(f"[ritmo] jogador {jogador}: {atraso * 1000:.2f} ms do EV_ABS ao forward_analog")
    assert atraso < CHEGADA_MAXIMA_S, f"{atraso * 1000:.1f} ms"
    for outro in (2, 3, 4):
        if outro != jogador:
            assert pads[outro].chegou(rx=40) is None


def test_o_p1_le_o_snapshot_do_leitor_e_nao_o_estado_do_ultimo_tique() -> None:
    """A volta do aperto devolve o stick de AGORA, com o `_last_state` ainda no 128 do tique."""
    leitor = _leitor(1)
    pad = _PadDoJogo()
    daemon = _daemon_do_primario(leitor, pad)
    _mexer(leitor, lx=40, ry=220, l2=77)
    assert daemon._last_state.raw_lx == 128

    async def uma_volta() -> None:
        lc._volta_do_aperto(daemon)

    asyncio.run(uma_volta())
    assert pad.analogicos, "a volta não entregou nada ao pad"
    ultimo = pad.analogicos[-1][1]
    assert (ultimo["lx"], ultimo["ry"], ultimo["l2"]) == (40, 220, 77)
    assert daemon._last_state.raw_lx == 128, "a volta não regrava o estado do tique"


# ----------------------------------------------------------------------------- o orçamento


def test_orcamento_do_stick_girando_a_250_hz(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stick contínuo a um quadro a cada 4 ms: voltas por segundo e CPU por volta ao relatório."""
    leitores = {n: _leitor(n) for n in (2, 3, 4)}
    pads = {n: _PadDoJogo() for n in (2, 3, 4)}
    daemon = _LacoForaDaMesa(_gerente(leitores, pads), poll_hz=1)  # type: ignore[arg-type]
    voltas: list[float] = []
    cpu: list[float] = []
    original = lc._volta_do_aperto

    def medir(d: Any) -> None:
        voltas.append(time.monotonic())
        antes = time.thread_time()
        original(d)
        cpu.append(time.thread_time() - antes)

    monkeypatch.setattr(lc, "_volta_do_aperto", medir)
    duracao = 1.0
    quadros = 0

    def girar() -> None:
        nonlocal quadros
        fim = time.monotonic() + duracao
        passo = 0
        while time.monotonic() < fim:
            passo += 1
            for leitor in leitores.values():
                _mexer(leitor, lx=128 + (passo * 7) % 90, ly=128 - (passo * 5) % 90)
            quadros += 1
            time.sleep(0.004)

    cpu_do_laco = 0.0

    async def cenario() -> None:
        nonlocal cpu_do_laco
        await asyncio.sleep(0.05)
        # O fio do laço inteiro: a volta, a espera que acorda e o agendamento que a volta não vê.
        inicio = time.thread_time()
        fio = _numa_thread(girar)
        while fio.is_alive():
            await asyncio.sleep(0.02)
        cpu_do_laco = time.thread_time() - inicio
        await asyncio.sleep(0.05)

    asyncio.run(daemon.rodar(cenario))
    por_s = len(voltas) / duracao
    media_us = 1e6 * sum(cpu) / max(1, len(cpu))
    print(
        f"[orcamento] {quadros} quadros por controle em {duracao:.1f} s, "
        f"{por_s:.0f} voltas/s, {media_us:.0f} us de CPU por volta, "
        f"{1e3 * cpu_do_laco / duracao:.1f} ms/s de CPU no fio do laço "
        f"({1e6 * cpu_do_laco / max(1, len(voltas)):.0f} us por volta com a espera)"
    )
    assert len(voltas) >= quadros // 3, f"o stick não acordou o laço ({len(voltas)} voltas)"
    assert len(voltas) <= TETO_DE_VOLTAS_POR_S * (duracao + 0.2)
    assert cpu_do_laco < TETO_DE_CPU_DO_LACO_S * duracao, (
        f"o laço gastou {1e3 * cpu_do_laco:.0f} ms de CPU em {duracao} s"
    )
    menor = min(b - a for a, b in itertools.pairwise(voltas))
    assert menor >= lc.INTERVALO_MINIMO_DA_VOLTA_S, f"{menor * 1000:.2f} ms"


# ------------------------------------------------------------------- o quadro de movimento


def _motion() -> MotionSensorReader:
    return MotionSensorReader(
        device_path=Path("/nao/existe/event-do-movimento"), target_uniq="aa:bb:cc:00:00:01"
    )


def _quadro_de_movimento(leitor: MotionSensorReader, relogio: _Relogio) -> None:
    for codigo in (ecodes.ABS_RX, ecodes.ABS_RY, ecodes.ABS_RZ):
        leitor._handle_event(_Evento(ecodes.EV_ABS, codigo, 900), ecodes)
    leitor._handle_event(relogio.sincronia(), ecodes)


def test_o_quadro_de_movimento_acorda_quando_o_giro_vai_ao_stick(despertares: list[float]) -> None:
    pergunta_feita: list[str | None] = []

    def pergunta(uniq: str | None) -> bool:
        pergunta_feita.append(uniq)
        return True

    er.definir_o_despertador(lambda: despertares.append(time.monotonic()), pergunta)
    leitor, relogio = _motion(), _Relogio()
    _quadro_de_movimento(leitor, relogio)
    assert len(despertares) == 1, "um despertar por quadro de movimento"
    assert pergunta_feita == ["aa:bb:cc:00:00:01"]


def test_o_quadro_de_movimento_cala_quando_ninguem_mistura_o_giro(
    despertares: list[float],
) -> None:
    er.definir_o_despertador(lambda: despertares.append(time.monotonic()), lambda _u: False)
    _quadro_de_movimento(_motion(), _Relogio())
    assert despertares == []


def test_sem_pergunta_o_movimento_nunca_acorda(despertares: list[float]) -> None:
    _quadro_de_movimento(_motion(), _Relogio())
    assert despertares == []


UNIQ = "aa:bb:cc:00:00:01"
OUTRO = "aa:bb:cc:00:00:02"


@pytest.mark.parametrize(
    ("arranjo", "esperado"),
    [
        (roteador.ArranjoDeMovimento(destino=roteador.DESTINO_ANALOGICO_DIREITO), True),
        (roteador.ArranjoDeMovimento(destino=roteador.DESTINO_ANALOGICO_ESQUERDO), True),
        (roteador.ArranjoDeMovimento(acelerometro=roteador.DESTINO_ANALOGICO_ESQUERDO), True),
        (roteador.ArranjoDeMovimento(destino=roteador.DESTINO_MOUSE), False),
        (roteador.ArranjoDeMovimento(), False),
        (None, False),
    ],
)
def test_quem_pergunta_pelo_movimento_olha_o_arranjo_da_mesa(
    arranjo: roteador.ArranjoDeMovimento | None, esperado: bool
) -> None:
    daemon = SimpleNamespace(store=StateStore())
    roteador.definir_ativo(daemon.store, arranjo)
    assert lc._o_movimento_vai_ao_stick(daemon, UNIQ) is esperado


def test_quem_pergunta_pelo_movimento_olha_o_arranjo_da_peca() -> None:
    daemon = SimpleNamespace(store=StateStore())
    roteador.definir_da_peca(
        daemon.store,
        UNIQ,
        roteador.ArranjoDeMovimento(destino=roteador.DESTINO_ANALOGICO_DIREITO),
    )
    assert lc._o_movimento_vai_ao_stick(daemon, UNIQ) is True
    assert lc._o_movimento_vai_ao_stick(daemon, OUTRO) is False


def test_sem_store_a_pergunta_do_movimento_responde_nao() -> None:
    assert lc._o_movimento_vai_ao_stick(SimpleNamespace(), UNIQ) is False


def test_o_laco_liga_a_pergunta_do_movimento_ao_despertador() -> None:
    """Pela espera de produção: o quadro de movimento de uma peça que mira acorda a volta."""
    leitor = _leitor(1)
    pad = _PadDoJogo()
    daemon = _daemon_do_primario(leitor, pad)
    roteador.definir_ativo(
        daemon.store, roteador.ArranjoDeMovimento(destino=roteador.DESTINO_ANALOGICO_DIREITO)
    )
    movimento, relogio = _motion(), _Relogio()

    async def cenario() -> int:
        parada = asyncio.Event()
        espera = asyncio.create_task(lc._esperar_o_tique(daemon, parada, 1.0))
        await asyncio.sleep(0.1)
        _numa_thread(lambda: _quadro_de_movimento(movimento, relogio)).join()
        await asyncio.sleep(0.1)
        voltas = daemon.store.counter("poll.volta_do_aperto")
        parada.set()
        await espera
        return int(voltas)

    assert asyncio.run(cenario()) == 1


def test_o_despertador_nao_empilha_chamadas_enquanto_a_volta_nao_come_a_anterior() -> None:
    """Um quadro seguido de outro antes de o laço correr: a fila do laço leva uma chamada."""
    leitor = _leitor(1)
    daemon = _daemon_do_primario(leitor, _PadDoJogo())
    chamadas: list[int] = []

    async def cenario() -> None:
        aperto = lc._o_aperto_do_laco(daemon)
        original = aperto.laco.call_soon_threadsafe

        def contar(*a: Any, **k: Any) -> Any:
            chamadas.append(1)
            return original(*a, **k)

        aperto.laco.call_soon_threadsafe = contar  # type: ignore[method-assign, assignment]
        er._acordar_quem_entrega_ao_jogo()
        await asyncio.sleep(0.01)
        assert aperto.evento.is_set()
        er._acordar_quem_entrega_ao_jogo()
        er._acordar_quem_entrega_ao_jogo()
        await asyncio.sleep(0.01)

    asyncio.run(cenario())
    assert len(chamadas) == 1, f"{len(chamadas)} chamadas ao laço para um evento já armado"
