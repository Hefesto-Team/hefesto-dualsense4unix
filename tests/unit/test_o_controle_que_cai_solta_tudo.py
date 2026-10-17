"""Quem perde o controle solta tudo o que ele segurava (AS-PROMESSAS-DE-16-10-SEM-CHAMADOR-01).

O botão alternado, a repetição e a trava (`soltar_a_ativacao`), o clique travado dos dois
mouses (`mouse.soltar_o_cursor`) e o pad do P1 em repouso saem juntos pelo
`gamepad.soltar_o_que_o_controle_segurava`, nas duas bordas do laço: o controle que some
(`not is_connected`) e a leitura que levanta. A saída do jogo (`end_game_output_session`), a
pausa, o Modo Nativo e a emulação suspensa soltam o clique travado. O `esquecer()` das duas
tabelas de estado tolera o laço criando estado enquanto o IPC esquece.

A MORDIDA, e cada uma foi rodada na entrega:

- tire a chamada do ramo `not is_connected` do `_poll_loop` e
  :func:`test_o_controle_que_some_solta_tudo` reprova;
- tire a chamada do ramo da leitura que levanta e
  :func:`test_a_leitura_que_levanta_solta_o_primario` reprova;
- tire o `soltar_o_cursor` do `end_game_output_session` e
  :func:`test_a_saida_do_jogo_solta_o_clique_travado` reprova;
- tire o `soltar_o_cursor` do ramo do input não pronto e
  :func:`test_a_pausa_solta_o_clique_travado` reprova;
- tire o `soltar_o_cursor` do `else` do mouse do desktop e
  :func:`test_a_emulacao_suspensa_solta_o_clique_travado` reprova;
- volte o `esquecer()` a iterar o dicionário vivo com `del` e
  :func:`test_esquecer_tolera_quem_mexe_nos_estados_no_meio` reprova.
"""
from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.core import ativacao_de_botao, filtro_de_botao
from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.daemon import lifecycle
from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.daemon.subsystems import gamepad, mouse
from hefesto_dualsense4unix.testing import FakeController
from hefesto_dualsense4unix.utils import session

PRIMARIO = "aa:bb:cc:00:00:01"
PRAZO_S = 5.0


async def _esperar(condicao: Callable[[], bool], o_que: str) -> None:
    """Espera a CONDIÇÃO, com prazo: sob carga o laço de 200 Hz chega tarde."""
    limite = time.monotonic() + PRAZO_S
    while not condicao():
        if time.monotonic() >= limite:
            pytest.fail(f"em {PRAZO_S:.0f} s não aconteceu: {o_que}")
        await asyncio.sleep(0.01)


def _estados(n: int) -> list[ControllerState]:
    return [
        ControllerState(battery_pct=80, l2_raw=0, r2_raw=0, connected=True, transport="usb")
        for _ in range(n)
    ]


def _daemon(fc: FakeController) -> Daemon:
    return Daemon(
        controller=fc,
        config=DaemonConfig(
            poll_hz=200,
            ipc_enabled=False,
            udp_enabled=False,
            autoswitch_enabled=False,
            mouse_emulation_enabled=False,
            keyboard_emulation_enabled=False,
        ),
    )


class _Travado:
    """Um mouse virtual que só sabe soltar o clique travado, e conta quantas vezes soltou."""

    def __init__(self) -> None:
        self.soltou = 0

    def soltar_o_clique_travado(self) -> None:
        self.soltou += 1


# -- o ajudante -----------------------------------------------------------------------------


def test_o_ajudante_solta_a_ativacao_os_dois_mouses_e_o_pad_do_p1() -> None:
    store = SimpleNamespace()
    estados = {("", ativacao_de_botao.chave(PRIMARIO)): object(), ("", "ff"): object()}
    store._ativacao_de_botao_estados = estados
    do_desktop, da_tabela = _Travado(), _Travado()
    pad = MagicMock()
    daemon = SimpleNamespace(
        store=store,
        _mouse_device=do_desktop,
        _tabela_no_jogo=SimpleNamespace(_mouse=da_tabela),
        _gamepad_device=pad,
    )

    gamepad.soltar_o_que_o_controle_segurava(daemon, PRIMARIO)

    assert list(estados) == [("", "ff")], "só o estado do controle que caiu sai"
    assert (do_desktop.soltou, da_tabela.soltou) == (1, 1)
    pad.forward_analog.assert_called_once_with(lx=128, ly=128, rx=128, ry=128, l2=0, r2=0)
    pad.forward_buttons.assert_called_once_with(frozenset())


def test_o_ajudante_sem_nada_no_ar_nao_levanta() -> None:
    gamepad.soltar_o_que_o_controle_segurava(SimpleNamespace())
    pad = MagicMock()
    pad.forward_buttons.side_effect = OSError("o nó sumiu")
    gamepad.soltar_o_que_o_controle_segurava(SimpleNamespace(_gamepad_device=pad))


# -- as duas bordas do laço ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_o_controle_que_some_solta_tudo(monkeypatch: pytest.MonkeyPatch) -> None:
    chamadas: list[tuple[Any, ...]] = []
    monkeypatch.setattr(
        lifecycle, "soltar_o_que_o_controle_segurava", lambda d, *a: chamadas.append(a))
    fc = FakeController(transport="usb", states=_estados(60))
    daemon = _daemon(fc)
    tarefa = asyncio.create_task(daemon.run())
    try:
        await _esperar(lambda: daemon._last_state is not None, "um tique com o controle")
        assert chamadas == [], "com o controle no ar, nada se solta"
        fc.desplugar()
        await _esperar(lambda: () in chamadas, "a queda soltar o que o controle segurava")
        await asyncio.sleep(0.05)
        # A leitura já na fila pode levantar antes (a borda dela solta o primário); a do
        # controle que some solta todos, uma vez.
        assert chamadas.count(()) == 1 and len(chamadas) <= 2, chamadas
    finally:
        daemon.stop()
        await tarefa


@pytest.mark.asyncio
async def test_a_leitura_que_levanta_solta_o_primario(monkeypatch: pytest.MonkeyPatch) -> None:
    chamadas: list[tuple[Any, ...]] = []
    monkeypatch.setattr(
        lifecycle, "soltar_o_que_o_controle_segurava", lambda d, *a: chamadas.append(a))
    fc = FakeController(transport="usb", states=_estados(60))
    fc.primary_uniq = PRIMARIO
    daemon = _daemon(fc)
    original = fc.read_state
    quebrou = {"agora": False}

    def _ler() -> ControllerState:
        if quebrou["agora"]:
            raise RuntimeError("leitura de mentira que levanta")
        return original()

    monkeypatch.setattr(fc, "read_state", _ler)
    tarefa = asyncio.create_task(daemon.run())
    try:
        await _esperar(lambda: daemon._last_state is not None, "um tique com o controle")
        quebrou["agora"] = True
        await _esperar(lambda: bool(chamadas), "a leitura que levanta soltar o primário")
        await asyncio.sleep(0.05)
        assert chamadas == [(PRIMARIO,)], "uma vez por episódio, do primário"
    finally:
        daemon.stop()
        await tarefa


# -- a saída do jogo, a pausa e a emulação suspensa -------------------------------------------


def test_a_saida_do_jogo_solta_o_clique_travado() -> None:
    do_desktop, da_tabela = _Travado(), _Travado()
    daemon = SimpleNamespace(
        store=SimpleNamespace(),
        controller=SimpleNamespace(),
        _mouse_device=do_desktop,
        _tabela_no_jogo=SimpleNamespace(_mouse=da_tabela),
    )
    gamepad.end_game_output_session(daemon, target_uniq=PRIMARIO)
    assert (do_desktop.soltou, da_tabela.soltou) == (1, 1)


async def _laco_com_o_espiao(
    monkeypatch: pytest.MonkeyPatch, preparar: Callable[[Daemon], None], *, pausado: bool
) -> None:
    """Sobe o laço e espera o `soltar_o_cursor` chamado com o daemon no estado pedido."""
    soltou = asyncio.Event()
    laco = asyncio.get_running_loop()
    original = mouse.soltar_o_cursor

    def _espiao(daemon: Any) -> None:
        if daemon._paused is pausado:
            laco.call_soon_threadsafe(soltou.set)
        original(daemon)

    # O `run()` lê a pausa do arquivo da sessão: a pausa do teste entra por ele.
    monkeypatch.setattr(session, "load_paused_state", lambda: pausado)

    monkeypatch.setattr(lifecycle, "INPUT_GRACE_SEC", 0.0)
    monkeypatch.setattr(mouse, "soltar_o_cursor", _espiao)
    fc = FakeController(transport="usb", states=_estados(400))
    daemon = _daemon(fc)
    preparar(daemon)
    tarefa = asyncio.create_task(daemon.run())
    try:
        await asyncio.wait_for(soltou.wait(), PRAZO_S)
    except asyncio.TimeoutError:
        pytest.fail(f"em {PRAZO_S:.0f} s o laço não soltou o clique travado")
    finally:
        daemon.stop()
        await tarefa


@pytest.mark.asyncio
async def test_a_pausa_solta_o_clique_travado(monkeypatch: pytest.MonkeyPatch) -> None:
    await _laco_com_o_espiao(monkeypatch, lambda d: None, pausado=True)


@pytest.mark.asyncio
async def test_a_emulacao_suspensa_solta_o_clique_travado(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _suspender(daemon: Daemon) -> None:
        # Com o mouse do desktop de pé, só a supressão leva ao `else` que solta.
        daemon._mouse_device = MagicMock()
        daemon._emulation_suppressed = True

    await _laco_com_o_espiao(monkeypatch, _suspender, pausado=False)


# -- a corrida do esquecer() -------------------------------------------------------------------


class _QuemMexe:
    """A identidade de um estado que, ao ser comparada, mexe nos estados (o outro fio)."""

    def __init__(self, estados: dict[Any, Any], mexida: str) -> None:
        self._estados = estados
        self._mexida = mexida

    def __eq__(self, outro: object) -> bool:
        if self._mexida == "cria":
            self._estados[("", "ccdd")] = object()
        else:
            self._estados.pop(("", "aabb"), None)
        return False

    __hash__ = object.__hash__


@pytest.mark.parametrize("mexida", ["cria", "apaga"])
@pytest.mark.parametrize(
    "dono_do_estado", [ativacao_de_botao, filtro_de_botao], ids=["ativação", "filtro"]
)
def test_esquecer_tolera_quem_mexe_nos_estados_no_meio(dono_do_estado: Any, mexida: str) -> None:
    estados: dict[Any, Any] = {}
    estados[("", _QuemMexe(estados, mexida))] = object()
    estados[("", "aabb")] = object()
    dono = SimpleNamespace()
    dono._ativacao_de_botao_estados = estados
    dono._filtro_de_botao_estados = estados

    dono_do_estado.esquecer(dono, "aa:bb")

    assert ("", "aabb") not in estados
    assert (("", "ccdd") in estados) is (mexida == "cria"), "o estado do outro controle fica"
