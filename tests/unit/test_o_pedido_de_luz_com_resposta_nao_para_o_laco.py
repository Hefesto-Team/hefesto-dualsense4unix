"""O pedido de luz do UDP e da extensão não escreve no fio do laço.

O-PEDIDO-DE-LUZ-DO-UDP-E-DA-EXTENSAO-NAO-ESCREVE-NO-FIO-DO-LACO-01, o resto da
D-2211-A-LUZ-SE-ESCREVE-FORA-DO-FIO-DO-LACO. Medido em 25/11: 60 RGBUpdate por segundo no
`UdpHandler`, com o nó e o `writeReport` de dois controles dormindo 500 ms, pararam o laço por
1496 ms; o `led.set` da camada da extensão pelo IPC, 1495 ms. Os dois passavam por
`agora=True`, que escreve no fio de quem chama.

Quatro controles (P1 e P2 no cabo, P3 e P4 no rádio); P1 e P3 dormem 500 ms em cada escrita,
P2 e P4 escrevem na hora. O backend, o `UdpHandler` e o mixin do IPC são os do produto; só o
handle e o nó são dublês. O atraso do laço é o do `_MedidorDoTique` (o acordar real contra o
previsto, tique de 5 ms).

MORDIDA: `_write_partial_output_em_futuro` de volta a `escritor.agora(...)` reprova pela frase
«a luz parou o laço».
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import pytest
from pydualsense.pydualsense import DSAudio, DSLight, DSTrigger

from hefesto_dualsense4unix.core import backend_pydualsense as bp
from hefesto_dualsense4unix.core.controller import OutputSpec
from hefesto_dualsense4unix.daemon import lifecycle as lc
from hefesto_dualsense4unix.daemon.ipc_handlers import CAMADA_DA_EXTENSAO, IpcHandlersMixin
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.daemon.udp_server import RateLimiter, UdpHandler

MACS = tuple(f"AA:BB:CC:00:00:0{n}" for n in range(1, 5))
TRANSPORTES = ("usb", "usb", "bt", "bt")
ATRASOS = (0.5, 0.0, 0.5, 0.0)
TETO_DO_LACO_S = 0.025
TIQUE_S = 0.005
DURACAO_S = 1.0
ESPERA_DA_FILA_S = 8.0


class _NoDeLed:
    """A classe LED do kernel de um controle: cada escrita dorme e guarda a cor com a hora."""

    def __init__(self, atraso: float, *, quebrado: bool = False) -> None:
        self.atraso = atraso
        self.quebrado = quebrado
        self.cores: list[tuple[int, int, int]] = []
        self.horas: list[float] = []
        self.indicator_dir = "/sys/class/leds/x"

    def writable(self) -> bool:
        return True

    def set_rgb(self, r: int, g: int, b: int, *, verify: bool = False) -> bool:
        time.sleep(self.atraso)
        if self.quebrado:
            raise OSError("nó de mentira quebrado")
        self.cores.append((r, g, b))
        self.horas.append(time.monotonic())
        return True

    def set_players(self, bits: tuple[bool, ...]) -> bool:
        return True

    def set_players_verified(self, bits: tuple[bool, ...]) -> bool:
        return True

    def invalidate_cache(self) -> None:
        return None

    def get_rgb(self) -> tuple[int, int, int] | None:
        return self.cores[-1] if self.cores else None


def _handle(transporte: str, atraso: float, *, quebrado: bool = False) -> SimpleNamespace:
    handle = SimpleNamespace(
        conType=SimpleNamespace(name="BT_31" if transporte == "bt" else "USB_01"),
        triggerL=DSTrigger(), triggerR=DSTrigger(), light=DSLight(), audio=DSAudio(),
        _raw_trigger_left=None, _raw_trigger_right=None, _output_muted=False,
        _escritor_da_luz=bp._EscritorDaLuz("hefesto-luz-teste"),
    )

    def _escreve(report: Any) -> int:
        time.sleep(atraso)
        if quebrado:
            raise OSError("report de mentira quebrado")
        return len(report)

    handle.writeReport = _escreve
    return handle


class _Mesa:
    def __init__(
        self,
        *,
        quebrados: tuple[bool, ...] = (False,) * 4,
        atrasos: tuple[float, ...] = ATRASOS,
    ) -> None:
        self.ctl = bp.PyDualSenseController()
        self.handles = [
            _handle(t, a, quebrado=q)
            for t, a, q in zip(TRANSPORTES, atrasos, quebrados, strict=True)
        ]
        self.ctl._handles = dict(zip(MACS, self.handles, strict=True))
        self.nos = {
            mac: _NoDeLed(a, quebrado=q)
            for mac, a, q in zip(MACS, atrasos, quebrados, strict=True)
        }
        self.ctl._sysfs = dict(self.nos)

    def esperar_a_luz(self) -> None:
        for handle in self.handles:
            assert handle._escritor_da_luz.esperar(ESPERA_DA_FILA_S), "a fila da luz não esvaziou"

    def fechar(self) -> None:
        for handle in self.handles:
            handle._escritor_da_luz.fechar()


@pytest.fixture
def mesa() -> Iterator[_Mesa]:
    m = _Mesa()
    yield m
    m.fechar()


class _Handlers(IpcHandlersMixin):
    def __init__(self, controller: Any) -> None:
        self.controller = controller
        self.daemon = None


async def _medir_o_laco(mandar: Any) -> float:
    """Roda `mandar` por `DURACAO_S` com o tique de 5 ms ao lado; devolve o pior atraso."""
    store = StateStore()
    medidor = lc._MedidorDoTique(store)
    fim = time.monotonic() + DURACAO_S
    pior = 0.0

    async def ticar() -> None:
        nonlocal pior
        while time.monotonic() < fim + 0.2:
            previsto = time.monotonic() + TIQUE_S
            await asyncio.sleep(TIQUE_S)
            agora = time.monotonic()
            medidor.abrir(agora, previsto)
            pior = max(pior, agora - previsto)

    await asyncio.gather(ticar(), mandar(fim))
    return pior


def _datagrama(indice: int, cor: tuple[int, int, int]) -> bytes:
    instrucao = {"type": "RGBUpdate", "parameters": [indice, *cor]}
    return json.dumps({"instructions": [instrucao]}).encode()


def _udp(mesa: _Mesa, store: StateStore) -> UdpHandler:
    return UdpHandler(
        controller=mesa.ctl,
        store=store,
        rate_limiter=RateLimiter(10_000, 10_000),
        jogadores=lambda: {mac: n for n, mac in enumerate(MACS, 1)},
    )


@pytest.mark.asyncio
async def test_sessenta_rgbupdate_por_segundo_nao_param_o_laco(mesa: _Mesa) -> None:
    """60 RGBUpdate/s para os quatro jogadores: o laço não espera o nó lento de P1 e P3, e a cor
    de P2 e P4 (que escrevem na hora) não espera a de P1 e P3."""
    store = StateStore()
    udp = _udp(mesa, store)
    ultimas: dict[str, tuple[int, int, int]] = {}
    enviadas: dict[str, list[float]] = {mac: [] for mac in MACS}

    async def mandar(fim: float) -> None:
        i = 0
        while time.monotonic() < fim:
            i += 1
            for indice, mac in enumerate(MACS):
                cor = (i % 256, indice, 7)
                enviadas[mac].append(time.monotonic())
                udp.handle_datagram(_datagrama(indice, cor), ("127.0.0.1", 9))
                ultimas[mac] = cor
            await asyncio.sleep(1 / 60)

    pior = await _medir_o_laco(mandar)
    assert pior < TETO_DO_LACO_S, f"a luz parou o laço por {pior * 1000:.0f} ms"
    await asyncio.to_thread(mesa.esperar_a_luz)
    for mac in MACS:
        assert mesa.nos[mac].cores[-1] == ultimas[mac], f"{mac}: a última cor não chegou"
    for mac in (MACS[1], MACS[3]):
        no = mesa.nos[mac]
        assert len(no.cores) >= 0.5 * len(enviadas[mac]), (
            f"{mac}: a escrita na hora esperou o controle lento ({len(no.cores)} de "
            f"{len(enviadas[mac])})"
        )
    assert store.snapshot().counters.get("udp.applied.RGBUpdate", 0) >= 4


@pytest.mark.asyncio
async def test_o_led_da_extensao_pelo_ipc_nao_para_o_laco_e_responde_o_que_saiu(
    mesa: _Mesa,
) -> None:
    """O `led.set` da camada da extensão em P1 (cabo) e P3 (rádio), lentos: o laço segue, e a
    resposta espera a escrita e diz onde a cor saiu."""
    handlers = _Handlers(mesa.ctl)
    respostas: list[dict[str, Any]] = []

    async def pedir(mac: str, fim: float) -> None:
        i = 0
        while time.monotonic() < fim:
            i += 1
            resposta = await handlers._handle_led_set(
                {"rgb": [i % 256, 1, 2], "uniq": mac, "camada": CAMADA_DA_EXTENSAO}
            )
            respostas.append(resposta)
            await asyncio.sleep(1 / 60)

    async def mandar(fim: float) -> None:
        await asyncio.gather(pedir(MACS[0], fim), pedir(MACS[2], fim))

    pior = await _medir_o_laco(mandar)
    assert pior < TETO_DO_LACO_S, f"a luz parou o laço por {pior * 1000:.0f} ms"
    assert respostas
    assert all(r["aplicado_em"] in ([MACS[0]], [MACS[2]]) for r in respostas), respostas


@pytest.mark.asyncio
async def test_a_cor_de_todos_pela_janela_nao_para_o_laco_e_chega_aos_quatro(
    mesa: _Mesa,
) -> None:
    """O `led.set` sem `uniq` (o «Todos» da janela) registra a cor em cada controle e espera as
    quatro escritas juntas pela fila de cada um: o laço segue com P1 (cabo) e P3 (rádio) lentos,
    e a resposta diz os quatro.

    MORDIDA: o `set_led` ou o `_registrar_em_todos` de volta ao fio do laço o param.
    """
    handlers = _Handlers(mesa.ctl)
    handlers._uniqs_conectados = lambda: list(MACS)  # type: ignore[method-assign]
    respostas: list[dict[str, Any]] = []

    async def mandar(fim: float) -> None:
        i = 0
        while time.monotonic() < fim:
            i += 1
            respostas.append(await handlers._handle_led_set({"rgb": [i % 256, 3, 4]}))
            await asyncio.sleep(1 / 60)

    pior = await _medir_o_laco(mandar)
    assert pior < TETO_DO_LACO_S, f"a luz parou o laço por {pior * 1000:.0f} ms"
    assert respostas
    assert all(sorted(r["aplicado_em"]) == sorted(MACS) for r in respostas), respostas[:2]


@pytest.mark.asyncio
async def test_o_registro_de_todos_espera_as_quatro_escritas_sem_parar_o_laco(
    mesa: _Mesa,
) -> None:
    """O registro da cor de «Todos» em cada controle (`_registrar_em_todos`, também do número)
    espera as quatro escritas juntas pela fila de cada uma: o laço segue com P1 e P3 lentos.

    MORDIDA: o `apply_output_for` síncrono no `_registrar_em_todos` para o laço.
    """
    handlers = _Handlers(mesa.ctl)
    handlers._uniqs_conectados = lambda: list(MACS)  # type: ignore[method-assign]
    aplicados: list[list[str]] = []

    async def mandar(fim: float) -> None:
        i = 0
        while time.monotonic() < fim:
            i += 1
            aplicados.append(await handlers._registrar_em_todos(led=(i % 256, 5, 6)))
            await asyncio.sleep(1 / 60)

    pior = await _medir_o_laco(mandar)
    assert pior < TETO_DO_LACO_S, f"a luz parou o laço por {pior * 1000:.0f} ms"
    assert aplicados and all(sorted(a) == sorted(MACS) for a in aplicados), aplicados[:2]


@pytest.mark.asyncio
async def test_o_soltar_da_extensao_espera_a_escrita_sem_parar_o_laco(mesa: _Mesa) -> None:
    """Soltar a cor da extensão devolve a do perfil pela fila, e o laço segue durante a escrita."""
    handlers = _Handlers(mesa.ctl)
    await asyncio.to_thread(mesa.ctl.apply_output_for, MACS[0], OutputSpec(led=(9, 9, 9)))
    await handlers._handle_led_set(
        {"rgb": [1, 2, 3], "uniq": MACS[0], "camada": CAMADA_DA_EXTENSAO}
    )

    async def mandar(fim: float) -> None:
        resposta = await handlers._handle_led_set(
            {"uniq": MACS[0], "camada": CAMADA_DA_EXTENSAO, "soltar": True}
        )
        assert resposta["aplicado_em"] == [MACS[0]]

    pior = await _medir_o_laco(mandar)
    assert pior < TETO_DO_LACO_S, f"a luz parou o laço por {pior * 1000:.0f} ms"
    assert mesa.nos[MACS[0]].cores[-1] == (9, 9, 9)


@pytest.mark.asyncio
async def test_a_cor_que_nao_saiu_conta_o_erro_do_udp_e_a_resposta_do_ipc_nao_afirma() -> None:
    """O nó quebrado de P1: o UDP conta `udp.error.RGBUpdate` quando a palavra chega, e o IPC
    responde sem `aplicado_em`. P2, sem defeito, segue escrevendo."""
    mesa = _Mesa(quebrados=(True, False, False, False))
    try:
        store = StateStore()
        udp = _udp(mesa, store)
        udp.handle_datagram(_datagrama(0, (5, 5, 5)), ("127.0.0.1", 9))
        udp.handle_datagram(_datagrama(1, (6, 6, 6)), ("127.0.0.1", 9))
        resposta = await _Handlers(mesa.ctl)._handle_led_set(
            {"rgb": [4, 4, 4], "uniq": MACS[0], "camada": CAMADA_DA_EXTENSAO}
        )
        await asyncio.to_thread(mesa.esperar_a_luz)
        assert resposta["aplicado_em"] == []
        assert store.snapshot().counters.get("udp.error.RGBUpdate", 0) >= 1
        assert mesa.nos[MACS[1]].cores[-1] == (6, 6, 6)
    finally:
        mesa.fechar()


def test_o_vigia_reafirma_os_controles_em_paralelo_fora_do_laco() -> None:
    """`reafirmar_barra_e_numero` (o vigia, que roda no pool) pede pela fila de cada controle e
    espera todas juntas: P3 e P4 (rádio), lentos, custam um atraso, não a soma dos dois."""
    mesa = _Mesa(atrasos=(0.5,) * 4)

    def _cronometrar(alvos: tuple[str, ...]) -> tuple[float, dict[str, bool]]:
        inicio = time.monotonic()
        resultado = mesa.ctl.reafirmar_barra_e_numero(alvos)
        return time.monotonic() - inicio, resultado

    try:
        so_p3, _ = _cronometrar((MACS[2],))
        so_p4, _ = _cronometrar((MACS[3],))
        juntos, resultado = _cronometrar((MACS[2], MACS[3]))
    finally:
        mesa.fechar()
    assert set(resultado.values()) == {True}, resultado
    assert so_p3 > 0.3 and so_p4 > 0.3, "o dublê do rádio não dormiu: a régua não mede nada"
    assert juntos < 0.75 * (so_p3 + so_p4), (
        f"o vigia esperou {juntos:.2f} s por P3 e P4, {so_p3:.2f} + {so_p4:.2f} s um a um: "
        "as escritas foram em série"
    )


def test_o_aviso_de_modo_devolve_a_cor_pela_fila(mesa: _Mesa) -> None:
    """`restaurar_lightbar_do_perfil` só usa o resultado no diário: pede pela fila e volta."""
    inicio = time.monotonic()
    devolvidos = mesa.ctl.restaurar_lightbar_do_perfil()
    assert time.monotonic() - inicio < 0.2, "o aviso de modo esperou a escrita"
    assert devolvidos == 4
    mesa.esperar_a_luz()
    assert all(no.cores for no in mesa.nos.values())
