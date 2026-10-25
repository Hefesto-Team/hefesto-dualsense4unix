"""O tópico ``movimento``: o giroscópio e o acelerômetro de CADA controle (24/10/2026).

A sprint O-MOVIMENTO-DE-CADA-CONTROLE-CHEGA-AS-EXTENSOES-01. A porta entregava os botões e as
entradas de cada controle, e o movimento não saía por tópico nenhum, embora o ``SensorHub`` o
leia por controle. Aqui:

1. cada controle da mesa (P1 a P4, cabo e rádio) sai com o ``uniq``, o ``jogador`` e o
   ``transporte`` dele, no tique comum e no congelado (o Modo Nativo e a pausa);
2. o leitor de movimento só fica vivo por quem assina ``movimento``; quem assina só as
   ``entradas`` não o segura, e o pedido nunca abre o touchpad nem graba o nó;
3. o controle parado não sai de novo, o ritmo nunca passa de 30 por segundo e o último valor
   chega; o controle que sai manda o repouso uma vez.

Os dublês são os do aparelho (o leitor de movimento do hub e o backend sem E/S); a porta, o
socket, o ``SensorHub`` e o laço do serviço são os de verdade.
"""

from __future__ import annotations

import asyncio
import math
import os
import pathlib
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.core.events import EventBus, EventTopic
from hefesto_dualsense4unix.core.evdev_reader import AccelSnapshot, GyroSnapshot
from hefesto_dualsense4unix.daemon.sensor_hub import SensorHub
from hefesto_dualsense4unix.mods.manifesto import (
    NOME_DO_MOVIMENTO,
    TOPICOS_DE_LEITURA,
    o_que_a_permissao_deixa,
    permissao_valida,
)
from hefesto_dualsense4unix.mods.porta import (
    FAIXA_MORTA_DA_ACEL,
    FAIXA_MORTA_DO_GIRO,
    MOVIMENTO_POR_SEGUNDO,
    Porta,
    entradas_de_todo_controle_no_servico,
    movimento_de_todo_controle_no_servico,
)
from tests.unit.test_a_coluna_agora_e_o_parar_tudo_vem_do_servico import curto  # noqa: F401
from tests.unit.test_a_porta_entrega_as_entradas_de_cada_controle import (
    _drenar,
    _Extensao,
    _Relogio,
)

#: A faixa forjada da casa: nenhum endereço de verdade.
UNIQS = ("aabbcc000011", "aabbcc000012", "aabbcc000013", "aabbcc000014")
P1, P2, P3, P4 = UNIQS

#: As mesas da casa: sempre mista (p1-usb, p2-bt, p3-usb, p4-bt), e os quatro de cada jeito.
MESAS = {
    "mista": ("usb", "bt", "usb", "bt"),
    "todos-no-cabo": ("usb", "usb", "usb", "usb"),
    "todos-no-bt": ("bt", "bt", "bt", "bt"),
    "um-so-no-cabo": ("usb",),
    "um-so-no-bt": ("bt",),
}
#: O controle parado na mesa: o viés da unidade no giro e a gravidade no eixo de cima.
PARADO = ((0.5, -0.4, 0.2), (0.0, 0.98, 0.1))
TIQUE = 1.0 / 120


class _LeitorDoMovimento:
    """O ``MotionSensorReader`` do hub: o giro e a aceleração de agora, sem nó nenhum."""

    def __init__(self) -> None:
        self.giro, self.acel = PARADO
        self.parado = False

    def snapshot(self) -> GyroSnapshot:
        return GyroSnapshot(*self.giro)

    def accel_snapshot(self) -> AccelSnapshot:
        return AccelSnapshot(*self.acel)

    def start(self) -> bool:
        return True

    def stop(self) -> None:
        self.parado = True


class _Backend:
    """O que o backend responde sem E/S: quem está na mesa, por onde, e quem é o posto."""

    def __init__(self, uniqs: tuple[str, ...], vias: tuple[str, ...]) -> None:
        self.primary_uniq = uniqs[0]
        self._alvos = {f"chave-{n}": u for n, u in enumerate(uniqs)}
        self._vias = {f"chave-{n}": v for n, v in enumerate(vias)}

    def alvos_conectados(self) -> dict[str, str]:
        return dict(self._alvos)

    def transportes_dos_alvos(self) -> dict[str, str]:
        return dict(self._vias)


class _Mesa:
    """A mesa de ``vias``: o P1 é o posto; o hub é o de verdade, com um leitor por controle."""

    def __init__(self, porta: Porta, vias: tuple[str, ...]) -> None:
        self.uniqs = UNIQS[: len(vias)]
        self.vias = dict(zip(self.uniqs, vias, strict=True))
        self.hub = SensorHub(auto_manutencao=False)
        self.leitores = {u: _LeitorDoMovimento() for u in self.uniqs}
        self.hub._motion.update(self.leitores)
        numeros = {u: n + 1 for n, u in enumerate(self.uniqs)}
        self.daemon = SimpleNamespace(
            controller=_Backend(self.uniqs, vias),
            _coop_manager=None,
            _mods_supervisor=SimpleNamespace(porta=porta),
            _garantir_sensor_hub=lambda: self.hub,
            identity_registry=SimpleNamespace(
                numero_da_lampada=lambda uniq, assign=False: numeros.get(uniq)),
        )
        self.posto = ControllerState(battery_pct=80, l2_raw=0, r2_raw=0, connected=True,
                                     transport=vias[0])

    def mexer(self, uniq: str, giro: tuple[float, float, float],
              acel: tuple[float, float, float] | None = None) -> None:
        leitor = self.leitores[uniq]
        leitor.giro = giro
        if acel is not None:
            leitor.acel = acel

    def tique(self, relogio: _Relogio, segundos: float = 0.05) -> None:
        relogio.t += segundos
        movimento_de_todo_controle_no_servico(self.daemon, self.posto)


async def _porta(pasta: pathlib.Path, relogio: _Relogio) -> Porta:
    async def escritor(metodo: str, pedido: dict[str, Any]) -> Any:
        return {"status": "ok"}

    porta = Porta(pasta / "mods.sock", EventBus(), escritor=escritor,
                  o_jogo_escreve=lambda uniq, canal: False, uniq_do_posto=lambda: P1,
                  relogio=relogio)
    await porta.iniciar()
    porta.registrar("ficha", "exemplo", os.getpid(), ["ler:movimento", "ler:entradas"])
    return porta


async def _entrar(pasta: pathlib.Path, topicos: list[str]) -> _Extensao:
    ext = _Extensao(pasta / "mods.sock")
    await asyncio.to_thread(ext.pedir, "mod.ola", {"ficha": "ficha"})
    assinou = await asyncio.to_thread(ext.pedir, "eventos.assinar", {"topicos": topicos})
    assert "result" in assinou, assinou
    return ext


def _so_o_movimento(eventos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    assert all(e["topico"] == "movimento" and e["nome"] == NOME_DO_MOVIMENTO for e in eventos)
    assert all(e["uniq"] == e["dados"]["uniq"] for e in eventos), "o envelope perdeu o uniq"
    return [e["dados"] for e in eventos]


def _giro(dados: dict[str, Any]) -> tuple[float, float, float]:
    return (dados["giro"]["x"], dados["giro"]["y"], dados["giro"]["z"])


def test_o_topico_e_a_permissao_existem_e_dizem_o_que_entregam() -> None:
    assert TOPICOS_DE_LEITURA["movimento"] == (NOME_DO_MOVIMENTO,)
    assert NOME_DO_MOVIMENTO == "controle.movimento"
    assert permissao_valida("ler:movimento")
    assert "giroscópio" in o_que_a_permissao_deixa("ler:movimento")


def test_sem_a_permissao_a_assinatura_e_recusada(curto: pathlib.Path) -> None:  # noqa: F811
    relogio = _Relogio()

    async def corrida() -> dict[str, Any]:
        porta = await _porta(curto, relogio)
        porta.registrar("ficha", "exemplo", os.getpid(), ["ler:entradas"])
        ext = _Extensao(curto / "mods.sock")
        try:
            await asyncio.to_thread(ext.pedir, "mod.ola", {"ficha": "ficha"})
            return await asyncio.to_thread(
                ext.pedir, "eventos.assinar", {"topicos": ["movimento"]})
        finally:
            ext.fechar()
            await porta.parar()

    resposta = asyncio.run(corrida())
    assert "ler:movimento" in resposta["error"]["message"]


# -- 1: cada controle sai com o dele, no tique comum e no congelado -------------------------


@pytest.mark.parametrize("mesa", list(MESAS))
def test_cada_controle_sai_com_o_uniq_o_jogador_e_o_transporte_dele(
    curto: pathlib.Path, mesa: str,  # noqa: F811
) -> None:
    """A assinatura entrega a pose de cada um; depois cada controle gira e para, um por vez."""
    relogio = _Relogio()

    async def corrida() -> tuple[_Mesa, list[dict[str, Any]]]:
        porta = await _porta(curto, relogio)
        bancada = _Mesa(porta, MESAS[mesa])
        ext = await _entrar(curto, ["movimento"])
        try:
            bancada.tique(relogio)
            for n, uniq in enumerate(bancada.uniqs):
                bancada.mexer(uniq, (100.0 + n, -50.0, 20.0), (0.0, 0.5, 0.85))
                bancada.tique(relogio)
                bancada.mexer(uniq, PARADO[0], PARADO[1])
                bancada.tique(relogio)
            return bancada, _so_o_movimento(await asyncio.to_thread(_drenar, ext))
        finally:
            ext.fechar()
            await porta.parar()

    bancada, dados = asyncio.run(corrida())
    visto = [(d["uniq"], d["jogador"], d["transporte"], _giro(d)) for d in dados]
    poses = [(u, n + 1, bancada.vias[u], PARADO[0]) for n, u in enumerate(bancada.uniqs)]
    gestos = [
        (uniq, n + 1, bancada.vias[uniq], giro)
        for n, uniq in enumerate(bancada.uniqs)
        for giro in ((100.0 + n, -50.0, 20.0), PARADO[0])
    ]
    assert visto == poses + gestos, f"{mesa}: {visto}"
    girando = dados[len(poses)]
    assert girando["acel"] == {"x": 0.0, "y": 0.5, "z": 0.85}


@pytest.mark.asyncio
@pytest.mark.parametrize("modo", ["nativo", "pausa", "fora-do-nativo"])
@pytest.mark.parametrize("mesa", list(MESAS))
async def test_o_laco_do_servico_entrega_o_movimento_em_todo_modo(
    curto: pathlib.Path, monkeypatch: pytest.MonkeyPatch, mesa: str,  # noqa: F811
    modo: str,
) -> None:
    # D-2410-A-PORTA-ENTREGA-AS-ENTRADAS-DE-CADA-CONTROLE-EM-TODO-MODO
    """O ``_poll_loop`` de verdade: cada controle da mesa gira, e o movimento sai com o dele."""
    from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
    from hefesto_dualsense4unix.daemon.state_store import StateStore
    from hefesto_dualsense4unix.testing import FakeController

    vias = MESAS[mesa]
    uniqs = UNIQS[: len(vias)]
    monkeypatch.setattr("hefesto_dualsense4unix.daemon.lifecycle.INPUT_GRACE_SEC", 0.0)
    monkeypatch.setattr("hefesto_dualsense4unix.daemon.lifecycle._a_fabrica_do_supervisor",
                        lambda: lambda daemon: None)
    hub = SensorHub(auto_manutencao=False)
    leitores = {u: _LeitorDoMovimento() for u in uniqs}
    hub._motion.update(leitores)
    monkeypatch.setattr(Daemon, "_garantir_sensor_hub", lambda self: hub)
    # Quem está na mesa e por onde, só para a leitura do movimento: o resto do serviço vê o
    # controle de mentira.
    monkeypatch.setattr("hefesto_dualsense4unix.daemon.subsystems.poll._na_mesa",
                        lambda controller: list(uniqs))
    monkeypatch.setattr("hefesto_dualsense4unix.mods.porta._transportes_por_controle",
                        lambda daemon: dict(zip(uniqs, vias, strict=True)))
    repouso = ControllerState(battery_pct=80, l2_raw=0, r2_raw=0, connected=True,
                              transport=vias[0])
    controle = FakeController(transport=vias[0], states=[repouso])
    relogio = _Relogio()
    porta = await _porta(curto, relogio)
    ext = await _entrar(curto, ["movimento"])
    daemon = Daemon(controller=controle, bus=EventBus(), store=StateStore(), config=DaemonConfig(
        poll_hz=120, ipc_enabled=False, udp_enabled=False, autoswitch_enabled=False))

    async def _nada() -> None:
        return None

    daemon._mods_supervisor = SimpleNamespace(porta=porta, parar=_nada)
    # O Nativo e a pausa correm pelo tique congelado; fora deles, pelo comum.
    contador = "poll.tick" if modo == "fora-do-nativo" else "input.settling.tick"
    rodando = asyncio.create_task(daemon.run())
    laco = asyncio.get_running_loop()
    try:
        prazo = laco.time() + 8.0
        while controle._idx < 1 and laco.time() < prazo:
            await asyncio.sleep(0.02)
        daemon._native_mode = modo == "nativo"
        daemon._paused = modo == "pausa"
        for n, uniq in enumerate(uniqs):
            leitores[uniq].giro = (200.0 + n, 0.0, 0.0)
            antes = daemon.store.counter(contador)
            while daemon.store.counter(contador) < antes + 3 and laco.time() < prazo:
                relogio.t += 0.1
                await asyncio.sleep(0.02)
    finally:
        daemon.stop()
        await rodando
    dados = _so_o_movimento(await asyncio.to_thread(_drenar, ext))
    ext.fechar()
    await porta.parar()
    vistos = {(d["uniq"], d["transporte"], d["giro"]["x"]) for d in dados}
    esperado = {(u, v, 200.0 + n) for n, (u, v) in enumerate(zip(uniqs, vias, strict=True))}
    assert esperado <= vistos, f"{mesa}/{modo}: {sorted(vistos)}"
    assert not any(leitor.parado for leitor in leitores.values())


# -- 2: o leitor de movimento vive só por quem o pede ---------------------------------------


class _VigiaParada:
    """O ``InputDirWatch`` de mentira: ``/dev/input`` não mudou."""

    def poll(self) -> bool:
        return False


def _hub_que_descobre(uniqs: tuple[str, ...], relogio: _Relogio | None = None) -> SensorHub:
    """Um ``SensorHub`` que abre leitores de mentira pela reconciliação de verdade."""
    nos = {u: f"/dev/input/mentira-{n}" for n, u in enumerate(uniqs)}
    hub = SensorHub(
        relogio=relogio,
        auto_manutencao=False,
        motion_factory=lambda uniq, no: _LeitorDoMovimento(),
        touch_factory=lambda uniq, no: _LeitorDoMovimento(),
        gamepad_factory=lambda uniq, no: _LeitorDoMovimento(),
        descobrir_motion=lambda: dict(nos),
        descobrir_touch=lambda: dict(nos),
        descobrir_gamepad=lambda: dict(nos),
    )
    hub._watch = _VigiaParada()
    return hub


def test_quem_assina_o_movimento_segura_so_o_leitor_de_movimento(
    curto: pathlib.Path,  # noqa: F811
) -> None:
    """Assinado o ``movimento``, a reconciliação abre o leitor de cada controle, sem o toque."""
    relogio = _Relogio()

    async def corrida() -> SensorHub:
        porta = await _porta(curto, relogio)
        bancada = _Mesa(porta, MESAS["mista"])
        bancada.hub = _hub_que_descobre(bancada.uniqs)
        bancada.daemon._garantir_sensor_hub = lambda: bancada.hub
        ext = await _entrar(curto, ["movimento"])
        try:
            bancada.tique(relogio)
            bancada.hub.reconciliar()
            return bancada.hub
        finally:
            ext.fechar()
            await porta.parar()

    hub = asyncio.run(corrida())
    assert set(hub._motion) == set(UNIQS), "o pedido não abriu o leitor de movimento"
    assert hub._touch == {} and hub._gamepad == {}, "o pedido do movimento abriu outro leitor"
    assert hub._demanda == {}, "o pedido do movimento passou pela demanda do toque"


def test_o_leitor_de_movimento_morre_quando_o_ultimo_assinante_sai(
    curto: pathlib.Path,  # noqa: F811
) -> None:
    """Assinado, o leitor de cada controle abre; a extensão sai, e ele fecha passado o prazo."""
    relogio = _Relogio()

    async def corrida() -> tuple[set[str], set[str], dict[str, Any]]:
        porta = await _porta(curto, relogio)
        bancada = _Mesa(porta, MESAS["mista"])
        bancada.hub = _hub_que_descobre(bancada.uniqs, relogio)
        bancada.daemon._garantir_sensor_hub = lambda: bancada.hub
        ext = await _entrar(curto, ["movimento"])
        try:
            bancada.tique(relogio)
            bancada.hub.reconciliar()
            abertos = set(bancada.hub._motion)
            leitores = dict(bancada.hub._motion)
        finally:
            ext.fechar()
        prazo = asyncio.get_running_loop().time() + 3.0
        while porta.le_o_movimento() and asyncio.get_running_loop().time() < prazo:
            await asyncio.sleep(0.02)
        try:
            for _ in range(3):  # os tiques seguem, e ninguém mais pede
                bancada.tique(relogio, SensorHub._DEMANDA_TTL_S)
            bancada.hub.reconciliar()
            return abertos, set(bancada.hub._motion), leitores
        finally:
            await porta.parar()

    abertos, depois, leitores = asyncio.run(corrida())
    assert abertos == set(UNIQS), "o pedido não abriu o leitor de movimento"
    assert depois == set(), f"o leitor seguiu vivo sem assinante: {sorted(depois)}"
    assert all(leitor.parado for leitor in leitores.values()), "o leitor saiu sem parar"


def test_quem_assina_so_as_entradas_nao_pede_o_movimento(
    curto: pathlib.Path,  # noqa: F811
) -> None:
    """A leitura das entradas e a do movimento são pedidos à parte: o das entradas não pede este."""
    relogio = _Relogio()

    async def corrida() -> SensorHub:
        porta = await _porta(curto, relogio)
        bancada = _Mesa(porta, MESAS["mista"])
        ext = await _entrar(curto, ["entradas"])
        try:
            bancada.tique(relogio)
            entradas_de_todo_controle_no_servico(bancada.daemon, bancada.posto)
            return bancada.hub
        finally:
            ext.fechar()
            await porta.parar()

    hub = asyncio.run(corrida())
    assert hub._demanda_do_movimento == {}, "a leitura das entradas pediu o movimento"


@pytest.mark.skipif(
    not hasattr(SensorHub, "toque_visto"),
    reason="a leitura das entradas só deixa de segurar os sensores com o d0a4d6879 (porta-2)",
)
def test_quem_assina_so_as_entradas_nao_segura_o_leitor_de_movimento(
    curto: pathlib.Path,  # noqa: F811
) -> None:
    """Com as entradas assinadas e o movimento não, a reconciliação não abre leitor de movimento."""
    relogio = _Relogio()

    async def corrida() -> SensorHub:
        porta = await _porta(curto, relogio)
        bancada = _Mesa(porta, MESAS["mista"])
        bancada.hub = _hub_que_descobre(bancada.uniqs)
        bancada.daemon._garantir_sensor_hub = lambda: bancada.hub
        ext = await _entrar(curto, ["entradas"])
        try:
            bancada.tique(relogio)
            entradas_de_todo_controle_no_servico(bancada.daemon, bancada.posto)
            bancada.hub.reconciliar()
            return bancada.hub
        finally:
            ext.fechar()
            await porta.parar()

    hub = asyncio.run(corrida())
    assert hub._motion == {}, "a leitura das entradas manteve o leitor de movimento vivo"


def test_sem_assinante_nenhum_leitor_e_pedido(curto: pathlib.Path) -> None:  # noqa: F811
    relogio = _Relogio()

    async def corrida() -> _Mesa:
        porta = await _porta(curto, relogio)
        bancada = _Mesa(porta, MESAS["mista"])
        ext = await _entrar(curto, ["entradas"])  # assinou outro tópico, não o movimento
        try:
            bancada.mexer(P2, (300.0, 0.0, 0.0))
            bancada.tique(relogio)
            return bancada
        finally:
            ext.fechar()
            await porta.parar()

    bancada = asyncio.run(corrida())
    assert bancada.hub._demanda_do_movimento == {}


def test_o_movimento_visto_nao_registra_demanda_nem_drena() -> None:
    hub = SensorHub(auto_manutencao=False)
    leitor = _LeitorDoMovimento()
    hub._motion[P1] = leitor
    assert hub.movimento_visto(P1) == PARADO
    assert hub.movimento_visto(P2) is None
    assert hub._demanda == {} and hub._demanda_do_movimento == {}
    hub.pedir_o_movimento(P1)
    assert set(hub._demanda_do_movimento) == {P1} and hub._demanda == {}


# -- 3: o ritmo, a faixa morta e o repouso --------------------------------------------------


def test_o_parado_nao_sai_de_novo_o_ritmo_tem_teto_e_o_ultimo_valor_chega(
    curto: pathlib.Path,  # noqa: F811
) -> None:
    """200 tiques com o controle tremendo na mesa: só a pose da assinatura. Dois segundos
    girando a 120 Hz: no máximo 30 por segundo, e a parada chega."""
    relogio = _Relogio()

    async def corrida() -> tuple[list[dict[str, Any]], list[tuple[float, dict[str, Any]]]]:
        porta = await _porta(curto, relogio)
        bancada = _Mesa(porta, MESAS["mista"])
        ext = await _entrar(curto, ["movimento"])
        try:
            tremor = FAIXA_MORTA_DO_GIRO * 0.7
            for n in range(200):  # o ruído do controle parado: abaixo das duas faixas
                sinal = 1 if n % 2 else -1
                bancada.mexer(P2, (0.5 + sinal * tremor / 2, -0.4, 0.2),
                              (0.0, 0.98 + sinal * FAIXA_MORTA_DA_ACEL * 0.4, 0.1))
                bancada.tique(relogio, TIQUE)
            parado = _so_o_movimento(await asyncio.to_thread(_drenar, ext, 0.2))
            instantes: list[tuple[float, dict[str, Any]]] = []
            for n in range(240):
                bancada.mexer(P2, (float(n * 3), 0.0, 0.0))
                bancada.tique(relogio, TIQUE)
                for dados in _so_o_movimento(await asyncio.to_thread(_drenar, ext, 0.002)):
                    instantes.append((relogio.t, dados))
            bancada.mexer(P2, PARADO[0])
            for _ in range(6):  # mais que 1/30 s: o teto segura e o tique seguinte entrega
                bancada.tique(relogio, TIQUE)
            instantes += [(relogio.t, d) for d in
                          _so_o_movimento(await asyncio.to_thread(_drenar, ext))]
            return parado, instantes
        finally:
            ext.fechar()
            await porta.parar()

    parado, instantes = asyncio.run(corrida())
    assert sorted(d["uniq"] for d in parado) == sorted(UNIQS), (
        f"o parado saiu além da pose de cada um: {parado}")
    tempos = [t for t, _ in instantes]
    pior = max(sum(1 for t in tempos if inicio <= t < inicio + 1.0) for inicio in tempos)
    assert pior <= MOVIMENTO_POR_SEGUNDO, f"{pior} num segundo"
    assert pior >= MOVIMENTO_POR_SEGUNDO - 10, f"o teto segurou demais: {pior} num segundo"
    assert _giro(instantes[-1][1]) == PARADO[0], "a parada não chegou"
    assert all(d["uniq"] == P2 for _, d in instantes)


def test_um_eixo_que_passa_da_faixa_sai_e_o_que_nao_passa_nao(
    curto: pathlib.Path,  # noqa: F811
) -> None:
    # D-2510-O-MOVIMENTO-CHEGA-AS-EXTENSOES-COM-FAIXA-MORTA
    relogio = _Relogio()

    async def corrida() -> list[dict[str, Any]]:
        porta = await _porta(curto, relogio)
        bancada = _Mesa(porta, MESAS["um-so-no-bt"])
        ext = await _entrar(curto, ["movimento"])
        try:
            bancada.tique(relogio)
            gx, gy, gz = PARADO[0]
            ax, ay, az = PARADO[1]
            bancada.mexer(P1, (gx, gy, gz + FAIXA_MORTA_DO_GIRO * 0.9))
            bancada.tique(relogio)
            bancada.mexer(P1, (gx, gy, gz + FAIXA_MORTA_DO_GIRO * 1.1))
            bancada.tique(relogio)
            bancada.mexer(P1, (gx, gy, gz + FAIXA_MORTA_DO_GIRO * 1.1),
                          (ax + FAIXA_MORTA_DA_ACEL * 1.5, ay, az))
            bancada.tique(relogio)
            return _so_o_movimento(await asyncio.to_thread(_drenar, ext))
        finally:
            ext.fechar()
            await porta.parar()

    dados = asyncio.run(corrida())
    assert len(dados) == 3, dados
    assert math.isclose(dados[1]["giro"]["z"], round(0.2 + FAIXA_MORTA_DO_GIRO * 1.1, 2))
    assert dados[2]["acel"]["x"] == round(FAIXA_MORTA_DA_ACEL * 1.5, 3)


def test_o_controle_que_sai_manda_o_repouso_uma_vez(curto: pathlib.Path) -> None:  # noqa: F811
    relogio = _Relogio()

    async def corrida() -> list[dict[str, Any]]:
        porta = await _porta(curto, relogio)
        bancada = _Mesa(porta, MESAS["mista"])
        ext = await _entrar(curto, ["movimento"])
        try:
            bancada.tique(relogio)
            await asyncio.to_thread(_drenar, ext, 0.2)
            bancada.mexer(P3, (250.0, 0.0, 0.0))
            bancada.tique(relogio)
            del bancada.daemon.controller._alvos["chave-2"]
            bancada.tique(relogio)
            bancada.tique(relogio)
            return _so_o_movimento(await asyncio.to_thread(_drenar, ext))
        finally:
            ext.fechar()
            await porta.parar()

    visto = [(d["uniq"], d["jogador"], d["transporte"], _giro(d), d["acel"])
             for d in asyncio.run(corrida())]
    zero = {"x": 0.0, "y": 0.0, "z": 0.0}
    assert visto == [(P3, 3, "usb", (250.0, 0.0, 0.0), {"x": 0.0, "y": 0.98, "z": 0.1}),
                     (P3, 3, "usb", (0.0, 0.0, 0.0), zero)]


@pytest.mark.parametrize("quem", [P1, P4])
def test_a_queda_leva_o_repouso_mesmo_sem_tique(curto: pathlib.Path, quem: str) -> None:  # noqa: F811
    relogio = _Relogio()

    async def corrida() -> list[dict[str, Any]]:
        porta = await _porta(curto, relogio)
        bancada = _Mesa(porta, MESAS["mista"])
        ext = await _entrar(curto, ["movimento"])
        try:
            bancada.tique(relogio)
            await asyncio.to_thread(_drenar, ext, 0.2)
            porta.bus.publish(EventTopic.CONTROLLER_DISCONNECTED,
                              {"reason": "alvo_sumiu", "uniq": quem})
            await asyncio.sleep(0.05)
            porta.bus.publish(EventTopic.CONTROLLER_DISCONNECTED,
                              {"reason": "alvo_sumiu", "uniq": quem})  # a segunda não repete
            return _so_o_movimento(await asyncio.to_thread(_drenar, ext))
        finally:
            ext.fechar()
            await porta.parar()

    visto = [(d["uniq"], _giro(d)) for d in asyncio.run(corrida())]
    assert visto == [(quem, (0.0, 0.0, 0.0))]


def test_quem_assina_depois_recebe_o_movimento_de_agora(curto: pathlib.Path) -> None:  # noqa: F811
    relogio = _Relogio()

    async def corrida() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        porta = await _porta(curto, relogio)
        bancada = _Mesa(porta, MESAS["mista"])
        primeira = await _entrar(curto, ["movimento"])
        try:
            bancada.mexer(P2, (80.0, 0.0, 0.0))
            bancada.tique(relogio)
            await asyncio.to_thread(_drenar, primeira, 0.2)
            segunda = await _entrar(curto, ["movimento"])
            try:
                bancada.tique(relogio)
                return (_so_o_movimento(await asyncio.to_thread(_drenar, primeira)),
                        _so_o_movimento(await asyncio.to_thread(_drenar, segunda)))
            finally:
                segunda.fechar()
        finally:
            primeira.fechar()
            await porta.parar()

    _primeira, segunda = asyncio.run(corrida())
    assert (P2, (80.0, 0.0, 0.0)) in [(d["uniq"], _giro(d)) for d in segunda]
    assert sorted(d["uniq"] for d in segunda) == sorted(UNIQS)
