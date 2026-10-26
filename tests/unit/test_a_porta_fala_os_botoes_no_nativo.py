"""A porta fala os botões no Modo Nativo e só lê os dedos enquanto alguém os pede (24/10/2026).

A sprint A-PORTA-FALA-OS-BOTOES-NO-NATIVO-E-SO-LE-OS-DEDOS-DE-QUEM-PEDE-01:

1. o tópico ``botoes`` sai nos dois ramos do tique (o comum e o congelado do Nativo, da pausa e da
   carência), pela mesma coleta do ``entradas``;
2. a extensão inscrita em ``entradas`` não segura leitor de movimento nem de toque: os dedos são o
   que o hub já lê, e o leitor de toque só vive para quem o pede (``dedos: true`` no
   ``eventos.assinar``), sem grabar o nó.

Os dublês são os do aparelho (o leitor do hub, o descobridor dos nós, o backend sem E/S); a porta,
o socket, o ``SensorHub`` e o laço do serviço são os de verdade.
"""

from __future__ import annotations

import asyncio
import os
import pathlib
from types import SimpleNamespace
from typing import Any, Literal

import pytest

from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.core.evdev_reader import EvdevSnapshot, PontoDeToque, TouchState
from hefesto_dualsense4unix.core.events import EventBus, EventTopic
from hefesto_dualsense4unix.daemon.sensor_hub import SensorHub
from hefesto_dualsense4unix.mods.porta import Porta, entradas_de_todo_controle_no_servico
from tests.unit.test_a_coluna_agora_e_o_parar_tudo_vem_do_servico import curto  # noqa: F401
from tests.unit.test_a_porta_entrega_as_entradas_de_cada_controle import (
    MESAS,
    UNIQS,
    _Backend,
    _drenar,
    _Extensao,
    _Relogio,
)

P1, P2 = UNIQS[0], UNIQS[1]


async def _porta(pasta: pathlib.Path, relogio: _Relogio) -> Porta:
    async def escritor(metodo: str, pedido: dict[str, Any]) -> Any:
        return {"status": "ok"}

    porta = Porta(pasta / "mods.sock", EventBus(), escritor=escritor,
                  o_jogo_escreve=lambda uniq, canal: False, uniq_do_posto=lambda: P1,
                  relogio=relogio)
    await porta.iniciar()
    porta.registrar("ficha", "exemplo", os.getpid(), ["ler:entradas", "ler:botoes"])
    return porta


async def _entrar(pasta: pathlib.Path, params: dict[str, Any]) -> _Extensao:
    ext = _Extensao(pasta / "mods.sock")
    await asyncio.to_thread(ext.pedir, "mod.ola", {"ficha": "ficha"})
    assinou = await asyncio.to_thread(ext.pedir, "eventos.assinar", params)
    assert "result" in assinou, assinou
    return ext


async def _nada() -> None:
    return None


class _Passivo:
    """O leitor passivo do hub de um controle que não é o posto: o snapshot de agora."""

    def __init__(self) -> None:
        self.snap = EvdevSnapshot()

    def snapshot(self) -> EvdevSnapshot:
        return self.snap

    def stop(self) -> None:
        """Nada a parar no dublê."""


@pytest.mark.asyncio
@pytest.mark.parametrize("nativo", [True, False], ids=["nativo", "comum"])
@pytest.mark.parametrize("mesa", ["mista", "tres-adaptadores-e-um-cabo", "todos-no-cabo",
                                  "todos-no-bt", "um-so-no-cabo", "um-so-no-bt"])
async def test_o_aperto_de_cada_controle_chega_no_nativo_e_fora_dele(
    curto: pathlib.Path, monkeypatch: pytest.MonkeyPatch, mesa: str, nativo: bool,  # noqa: F811
) -> None:
    """O ``_poll_loop`` de verdade: o posto e os do hub apertam o ✕, e a borda chega à extensão."""
    from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
    from hefesto_dualsense4unix.daemon.state_store import StateStore
    from hefesto_dualsense4unix.testing import FakeController

    vias = MESAS[mesa]
    outros = UNIQS[1:len(vias)]
    via: Literal["usb", "bt"] = "bt" if vias[0] == "bt" else "usb"
    monkeypatch.setattr("hefesto_dualsense4unix.daemon.lifecycle.INPUT_GRACE_SEC", 0.0)
    monkeypatch.setattr("hefesto_dualsense4unix.daemon.lifecycle._a_fabrica_do_supervisor",
                        lambda: lambda daemon: None)
    hub = SensorHub(auto_manutencao=False)
    passivos = {u: _Passivo() for u in outros}
    hub._gamepad.update(passivos)
    monkeypatch.setattr(Daemon, "_garantir_sensor_hub", lambda self: hub)
    monkeypatch.setattr("hefesto_dualsense4unix.daemon.subsystems.poll._na_mesa",
                        lambda controller: list(outros))

    def estado(*botoes: str) -> ControllerState:
        return ControllerState(battery_pct=80, l2_raw=0, r2_raw=0, connected=True,
                               transport=via,
                               buttons_pressed=frozenset(botoes))

    controle = FakeController(transport=via, states=[estado()])
    relogio = _Relogio()
    porta = await _porta(curto, relogio)
    ext = await _entrar(curto, {"topicos": ["botoes"]})
    daemon = Daemon(controller=controle, bus=EventBus(), store=StateStore(), config=DaemonConfig(
        poll_hz=120, ipc_enabled=False, udp_enabled=False, autoswitch_enabled=False))
    daemon._mods_supervisor = SimpleNamespace(porta=porta, parar=_nada)
    rodando = asyncio.create_task(daemon.run())
    laco = asyncio.get_running_loop()
    contador = "input.settling.tick" if nativo else "poll.tick"

    async def tiques(n: int) -> None:
        alvo = daemon.store.counter(contador) + n
        while daemon.store.counter(contador) < alvo and laco.time() < prazo:
            await asyncio.sleep(0.01)

    try:
        prazo = laco.time() + 8.0
        while controle._idx < 1 and laco.time() < prazo:
            await asyncio.sleep(0.02)
        daemon._native_mode = nativo
        await tiques(3)
        controle._states, controle._idx = [estado("cross")], 0
        await tiques(3)
        controle._states, controle._idx = [estado()], 0
        await tiques(3)
        for uniq in outros:
            passivos[uniq].snap = EvdevSnapshot(buttons_pressed=frozenset({"cross"}))
            await tiques(3)
            passivos[uniq].snap = EvdevSnapshot()
            await tiques(3)
    finally:
        daemon.stop()
        await rodando
    eventos = await asyncio.to_thread(_drenar, ext)
    ext.fechar()
    await porta.parar()
    assert laco.time() < prazo, f"o laço não andou os tiques de {contador}"
    for nome in (EventTopic.BUTTON_DOWN, EventTopic.BUTTON_UP):
        visto = [e["dados"]["uniq"] for e in eventos
                 if e["nome"] == nome and e["dados"]["botao"] == "cross"]
        assert visto == [None, *outros], f"{mesa}/{'nativo' if nativo else 'comum'} {nome}: {visto}"


class _Leitor:
    """Um leitor do hub de mentira (movimento, toque ou gamepad): nasce, para e conta o grab."""

    def __init__(self, uniq: str) -> None:
        self.uniq = uniq
        self.grabs: list[bool] = []
        self.estado = TouchState()

    def start(self) -> bool:
        return True

    def stop(self) -> None:
        """Nada a parar no dublê."""

    def snapshot(self) -> EvdevSnapshot:
        return EvdevSnapshot()

    def touch_state(self) -> TouchState:
        return self.estado

    def set_grab(self, querido: bool) -> None:
        self.grabs.append(querido)

    grab_state = "off"


def _hub(relogio: _Relogio) -> SensorHub:
    """O hub de verdade, com um nó de cada tipo para cada controle da mesa."""
    nos = {u: f"/dev/input/de-mentira-{n}" for n, u in enumerate(UNIQS)}
    return SensorHub(
        motion_factory=lambda uniq, no: _Leitor(uniq),
        touch_factory=lambda uniq, no: _Leitor(uniq),
        gamepad_factory=lambda uniq, no: _Leitor(uniq),
        descobrir_motion=lambda: dict(nos),
        descobrir_touch=lambda: dict(nos),
        descobrir_gamepad=lambda: dict(nos),
        relogio=relogio,
        auto_manutencao=False,
    )


def _daemon(porta: Porta, hub: SensorHub) -> SimpleNamespace:
    numeros = {u: n + 1 for n, u in enumerate(UNIQS)}
    return SimpleNamespace(
        controller=_Backend(UNIQS, MESAS["mista"]),
        _coop_manager=None,
        _mods_supervisor=SimpleNamespace(porta=porta),
        _garantir_sensor_hub=lambda: hub,
        identity_registry=SimpleNamespace(
            numero_da_lampada=lambda uniq, assign=False: numeros.get(uniq)),
    )


_POSTO = ControllerState(battery_pct=80, l2_raw=0, r2_raw=0, connected=True,
                         transport="usb")


def _vivos(
    curto: pathlib.Path, params: dict[str, Any] | None, *,  # noqa: F811
    tela: str | None = None,
    tocar: bool = False,
) -> tuple[SensorHub, list[dict[str, Any]]]:
    """Dez tiques com a manutenção do hub entre eles; ``params`` é o ``eventos.assinar``."""
    relogio = _Relogio()

    async def corrida() -> tuple[SensorHub, list[dict[str, Any]]]:
        porta = await _porta(curto, relogio)
        hub = _hub(relogio)
        daemon = _daemon(porta, hub)
        ext = await _entrar(curto, params) if params is not None else None
        try:
            for _ in range(10):
                relogio.t += 0.1
                if tela is not None:
                    hub.leitura(tela)
                entradas_de_todo_controle_no_servico(daemon, _POSTO)
                await asyncio.to_thread(hub.reconciliar)
                if tocar:
                    for leitor in hub._touch.values():
                        leitor.estado = TouchState(
                            touching=True, x=960, y=540,
                            pontos=(PontoDeToque(slot=0, x=960, y=540, identidade=1),))
            eventos = await asyncio.to_thread(_drenar, ext) if ext is not None else []
            return hub, [e["dados"] for e in eventos]
        finally:
            if ext is not None:
                ext.fechar()
            await porta.parar()

    return asyncio.run(corrida())


def test_quem_le_as_entradas_nao_segura_o_leitor_de_movimento_nem_o_de_toque(
    curto: pathlib.Path,  # noqa: F811
) -> None:
    sem, _ = _vivos(curto, None)
    com, _ = _vivos(curto, {"topicos": ["entradas"]})
    assert (len(sem._motion), len(sem._touch)) == (0, 0)
    assert (len(com._motion), len(com._touch)) == (len(sem._motion), len(sem._touch)), (
        f"a extensão inscrita em entradas segurou {len(com._motion)} leitores de movimento e "
        f"{len(com._touch)} de toque")


def test_o_dedo_que_o_hub_ja_le_pela_tela_chega_sem_segurar_nada(
    curto: pathlib.Path,  # noqa: F811
) -> None:
    """A tela aberta pede o P2: o dedo dele chega à extensão, e o leitor vive pela tela."""
    hub, dados = _vivos(curto, {"topicos": ["entradas"]}, tela=P2, tocar=True)
    assert set(hub._touch) == {P2}, "o leitor de toque vive pela tela, e só o dela"
    assert {d["uniq"] for d in dados if d["dedos"]} == {P2}
    assert all(not leitor.grabs or not any(leitor.grabs) for leitor in hub._touch.values())


def test_quem_pede_os_dedos_segura_so_o_leitor_de_toque_e_sem_grab(
    curto: pathlib.Path,  # noqa: F811
) -> None:
    """Prova da D-2510-OS-DEDOS-SO-PARA-QUEM-PEDE."""
    hub, dados = _vivos(curto, {"topicos": ["entradas"], "dedos": True}, tocar=True)
    assert set(hub._touch) == set(UNIQS), "quem pediu os dedos não segurou o leitor de toque"
    assert hub._motion == {}, "pedir os dedos não segura o leitor de movimento"
    assert all(True not in leitor.grabs for leitor in hub._touch.values()), "os dedos grabaram"
    assert {d["uniq"] for d in dados if d["dedos"] == [{"x": 0.5, "y": 0.5}]} == set(UNIQS)


def test_o_pedido_dos_dedos_so_vale_com_o_topico_entradas(curto: pathlib.Path) -> None:  # noqa: F811
    async def corrida() -> dict[str, Any]:
        porta = await _porta(curto, _Relogio())
        ext = _Extensao(curto / "mods.sock")
        try:
            await asyncio.to_thread(ext.pedir, "mod.ola", {"ficha": "ficha"})
            return await asyncio.to_thread(
                ext.pedir, "eventos.assinar", {"topicos": ["botoes"], "dedos": True})
        finally:
            ext.fechar()
            await porta.parar()

    resposta = asyncio.run(corrida())
    assert "error" in resposta and "entradas" in resposta["error"]["message"], resposta
