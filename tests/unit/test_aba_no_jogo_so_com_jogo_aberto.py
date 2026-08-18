"""ABA-DO-JOGO-01 — a aba "No jogo" só existe com jogo da Steam aberto.

O PEDIDO DELA, LITERAL (10/08/2026)
===================================
    *"essa aba no jogo só deveria aparecer quando efetivamente eu tivesse com
    um jogo steam aberto"*

Hoje ela aparece sempre.

A CAUSA, MEDIDA
===============
A aba nunca teve condição de visibilidade nenhuma. É página FIXA do Glade
(`main.glade`, `tab_no_jogo_box`), montada sem portão (`install_no_jogo_tab`,
chamada direto pelo `install_status_polling`). O único portão que existia era o
de PINTURA — o `id_da_pagina_corrente(notebook) != ABA_NO_JOGO` de
`_sync_paineis_no_jogo`, que decide se REPINTA quando ela já está à vista —, e
ele foi confundido com portão de existência.

Nenhuma capacidade nova entrou: quem responde *"há jogo da Steam aberto?"* é a
`steam_game_running_appid`, escrita em 08/08 (RELANCAR-AGORA-01) e até hoje só
chamada por gesto dela, dentro da janela. O que esta leva faz é o fato VIAJAR —
o daemon sonda, o `state_full` leva, a janela lê.

O QUE CADA TESTE MORDE
======================
Cada teste diz, na própria docstring, qual linha arrancar para vê-lo reprovar.
As mordidas foram executadas de verdade antes desta leva entrar.

O TRI-ESTADO, QUE É A PARTE FÁCIL DE PERDER
===========================================
`appid=None` responde a duas perguntas muito diferentes: "sondei e não há jogo"
e "ainda não sondei". Por isso o par `lido`+`appid`. Sem o `lido`, a aba some no
instante em que o daemon sobe — inclusive com o jogo dela aberto — e volta dois
segundos depois: pisca a cada restart do daemon. O teste
`test_ainda_nao_perguntei_nao_e_nao_ha_jogo` é o que trava isso, e ele reprova
com qualquer simplificação que jogue o `lido` fora.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

# GI-REAL-01: este módulo importa `app/`, que sobe PyGObject no import.
# Sem esta guarda ele não COLETA num runner sem GTK, e o censo de coleta
# do `ci.yml` reprova a leva inteira. Medido em 13/08/2026: era um dos
# três módulos que derrubavam o `lint-test` nas três versões de Python.
exigir_gi_real("aba No jogo só com jogo aberto (importa app.widgets.painel_no_jogo)")

from hefesto_dualsense4unix.app.widgets.painel_no_jogo import jogo_steam_aberto
from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.lifecycle import Daemon
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.testing import FakeController

#: O Pragmata, o jogo com que ela mediu o defeito do controle duplicado em
#: 10/08 — o mesmo appid que já aparece em `test_o_perfil_do_jogo_que_nao_entrou`.
PRAGMATA = 3357650


# ---------------------------------------------------------------------------
# 1. A leitura da janela: três respostas, e o `None` é uma delas
# ---------------------------------------------------------------------------


def test_com_jogo_aberto_a_resposta_e_sim() -> None:
    """O caso que faz a aba aparecer.

    Arranque para ver reprovar: fazer `jogo_steam_aberto` devolver sempre
    `False` (ou ignorar o `appid`).
    """
    estado = {"jogo_steam": {"lido": True, "appid": PRAGMATA}}

    assert jogo_steam_aberto(estado) is True


def test_ainda_nao_perguntei_nao_e_nao_ha_jogo() -> None:
    """O TRI-ESTADO, que é a razão de o `lido` existir.

    Os dois estados abaixo têm `appid=None` e mandam a janela fazer coisas
    OPOSTAS: o primeiro é "não mexa na aba", o segundo é "esconda a aba".

    Arranque para ver reprovar: tirar o `lido` da conta em `jogo_steam_aberto`
    (devolver `isinstance(appid, int)` direto). As duas linhas passam a devolver
    `False` e a primeira asserção reprova — que é, letra por letra, a aba
    piscando a cada vez que o daemon sobe.
    """
    ainda_nao = {"jogo_steam": {"lido": False, "appid": None}}
    nao_ha = {"jogo_steam": {"lido": True, "appid": None}}

    assert jogo_steam_aberto(ainda_nao) is None
    assert jogo_steam_aberto(nao_ha) is False


def test_daemon_velho_e_daemon_desligado_nao_decidem_nada() -> None:
    """Silêncio nunca vira "não há jogo".

    Um daemon anterior a esta versão não conhece a chave `jogo_steam` — e nesta
    casa o daemon vivo ser mais velho que o código é rotina (install editable: a
    cura do daemon só vale no próximo start). Um `False` inventado a partir do
    silêncio faria a aba sumir por causa da IDADE do daemon.

    Arranque para ver reprovar: devolver `False` quando a chave falta.
    """
    assert jogo_steam_aberto({"connected": True}) is None
    assert jogo_steam_aberto(None) is None
    assert jogo_steam_aberto({"jogo_steam": "sim"}) is None


# ---------------------------------------------------------------------------
# 2. O store: quem guarda o tri-estado
# ---------------------------------------------------------------------------


def test_o_store_nasce_sem_ter_perguntado() -> None:
    """Boot do daemon: ninguém sondou ainda, e o store diz isso.

    Arranque para ver reprovar: nascer com `_steam_jogo_lido = True`.
    """
    store = StateStore()

    assert store.steam_jogo_lido is False
    assert store.steam_jogo_appid is None


def test_sondar_e_nao_achar_jogo_e_uma_resposta() -> None:
    """`set_steam_jogo_appid(None)` é "não há jogo", não "não sei".

    Arranque para ver reprovar: não marcar `_steam_jogo_lido` quando o appid é
    `None` (só marcar quando há jogo).
    """
    store = StateStore()
    store.set_steam_jogo_appid(None)

    assert store.steam_jogo_lido is True
    assert store.steam_jogo_appid is None


def test_o_appid_do_jogo_aberto_fica_no_store() -> None:
    store = StateStore()
    store.set_steam_jogo_appid(PRAGMATA)

    assert store.steam_jogo_lido is True
    assert store.steam_jogo_appid == PRAGMATA


# ---------------------------------------------------------------------------
# 3. O daemon: sondar, publicar, e estar de fato LIGADO no laço
# ---------------------------------------------------------------------------


class _DaemonDeSonda:
    """O mínimo que a sonda toca: um store de verdade e um `_run_blocking`."""

    def __init__(self, resposta: Any) -> None:
        self.store = StateStore()
        self._resposta = resposta
        self.chamadas = 0
        self._sondar_steam_jogo = Daemon._sondar_steam_jogo.__get__(self)

    async def _run_blocking(self, fn: Any, *args: Any) -> Any:
        self.chamadas += 1
        if isinstance(self._resposta, Exception):
            raise self._resposta
        return self._resposta


def test_a_sonda_publica_o_appid_no_store() -> None:
    """O caminho feliz: o daemon pergunta e o fato entra no store.

    Arranque para ver reprovar: tirar o `set_steam_jogo_appid` de
    `_sondar_steam_jogo`.
    """
    daemon = _DaemonDeSonda(PRAGMATA)
    asyncio.run(daemon._sondar_steam_jogo())

    assert daemon.chamadas == 1
    assert daemon.store.steam_jogo_appid == PRAGMATA
    assert daemon.store.steam_jogo_lido is True


def test_sonda_que_falha_nao_apaga_o_que_se_sabia() -> None:
    """`pgrep` que estoura não vira "não há jogo".

    É a diferença entre a aba sumir debaixo dela no meio da partida por causa de
    um susto do sistema, e a aba ficar exatamente como estava.

    Arranque para ver reprovar: trocar o `return` do `except` por
    `self.store.set_steam_jogo_appid(None)`.
    """
    daemon = _DaemonDeSonda(PRAGMATA)
    asyncio.run(daemon._sondar_steam_jogo())
    daemon._resposta = OSError("fork falhou")
    asyncio.run(daemon._sondar_steam_jogo())

    assert daemon.store.steam_jogo_appid == PRAGMATA


class _DaemonDeLaco(_DaemonDeSonda):
    """O `_poll_loop` de PRODUÇÃO, reduzido ao osso de antes do gate de conexão.

    Tudo o que os outros blocos do tique lento fazem vira no-op; o que fica de
    pé é o laço de verdade, com a sua aritmética de `next_at` — que é justamente
    o que este teste precisa exercitar. O controle nasce desconectado de
    propósito: é a prova de que a sonda roda ANTES daquele gate, e portanto com
    o jogo dela aberto e o DualSense carregando fora da mesa.
    """

    def __init__(self, resposta: Any, *, ticks: int = 4) -> None:
        super().__init__(resposta)
        self.config = SimpleNamespace(poll_hz=200, auto_reconnect=False)
        self.controller = SimpleNamespace(is_connected=lambda: False)
        self.bus = SimpleNamespace(publish=lambda *a, **k: None)
        self._stop_event: Any = None
        self._input_ready_at = float("inf")  # sem grace: o co-op fica de fora
        self._external_tick_task: Any = None
        self._steam_jogo_task: Any = None
        self._restantes = ticks
        self._poll_loop = Daemon._poll_loop.__get__(self)
        self._schedule_steam_jogo_tick = Daemon._schedule_steam_jogo_tick.__get__(
            self
        )

    def _is_stopping(self) -> bool:
        self._restantes -= 1
        return self._restantes < 0

    def _sync_identity_registry(self) -> None: ...
    def aplicar_gamepad_para_multiplos_controles(self) -> None: ...
    def _amostrar_bateria(self, _agora: float) -> None: ...
    def _schedule_external_tick(self) -> None: ...
    def _drenar_modo_pendente(self) -> None: ...
    async def _sync_game_signal(self) -> None: ...

    async def rodar(self) -> None:
        self._stop_event = asyncio.Event()
        await self._poll_loop()
        if self._steam_jogo_task is not None:
            await asyncio.gather(self._steam_jogo_task, return_exceptions=True)


def test_o_poll_loop_agenda_a_sonda() -> None:
    """A cura tem de estar LIGADA — o defeito mais caro desta casa é a que não está.

    *"A casa sabe e o produto não faz"*: o `_poll_loop` é o único relógio do
    daemon, e uma sonda que ninguém agenda deixa `steam_jogo_lido` em `False`
    para sempre — a aba nunca mais apareceria, e todos os outros testes desta
    bancada continuariam verdes.

    Roda o laço de PRODUÇÃO, com o controle DESCONECTADO: se a sonda for parar
    depois do gate de conexão, ela nunca acontece e o store fica virgem.

    Arranque para ver reprovar: apagar o bloco do `steam_jogo_next_at` do
    `_poll_loop`, ou movê-lo para depois do `if not self.controller.is_connected()`.
    """
    daemon = _DaemonDeLaco(PRAGMATA)
    asyncio.run(daemon.rodar())

    assert daemon.store.steam_jogo_lido is True
    assert daemon.store.steam_jogo_appid == PRAGMATA


def test_a_sonda_nao_empilha_a_cada_tique() -> None:
    """`pgrep` é subprocesso: um tique que não voltou não ganha companhia.

    Quatro voltas do laço, e a sonda de 0,5 Hz acontece UMA vez — a aritmética
    do `next_at` mais a guarda de reentrância do `_schedule_steam_jogo_tick`.

    Arranque para ver reprovar: tirar o `if task is not None and not task.done()`
    do `_schedule_steam_jogo_tick` E o `steam_jogo_next_at = tick_started + 2.0`.
    """
    daemon = _DaemonDeLaco(PRAGMATA, ticks=4)
    asyncio.run(daemon.rodar())

    assert daemon.chamadas == 1


# ---------------------------------------------------------------------------
# 4. O `state_full`: o fato viaja até a janela
# ---------------------------------------------------------------------------


@pytest.fixture
def ipc_server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> IpcServer:
    """IpcServer mínimo (sem socket no ar), no molde de `test_state_full_game_signal`."""
    target = tmp_path / "profiles"
    target.mkdir()

    def fake_profiles_dir(ensure: bool = False) -> Path:
        if ensure:
            target.mkdir(parents=True, exist_ok=True)
        return target

    monkeypatch.setattr(loader_module, "profiles_dir", fake_profiles_dir)
    fc = FakeController(transport="usb")
    fc.connect()
    store = StateStore()
    store.update_controller_state(
        ControllerState(
            battery_pct=50, l2_raw=0, r2_raw=0, connected=True, transport="usb"
        )
    )
    manager = ProfileManager(controller=fc, store=store)
    return IpcServer(
        controller=fc,
        store=store,
        profile_manager=manager,
        socket_path=tmp_path / "hefesto-dualsense4unix.sock",
    )


async def test_o_state_full_leva_o_tri_estado_inteiro(ipc_server: IpcServer) -> None:
    """As duas chaves viajam juntas — a `appid` sozinha não responde nada.

    Arranque para ver reprovar: publicar só o `appid` (ou nem publicar: sem a
    chave `jogo_steam` o teste estoura em `KeyError`, que é o estado do HEAD
    antes desta leva).
    """
    antes = await ipc_server._handle_daemon_state_full({})
    assert antes["jogo_steam"] == {"lido": False, "appid": None}

    ipc_server.store.set_steam_jogo_appid(PRAGMATA)
    com_jogo = await ipc_server._handle_daemon_state_full({})
    assert com_jogo["jogo_steam"] == {"lido": True, "appid": PRAGMATA}

    ipc_server.store.set_steam_jogo_appid(None)
    sem_jogo = await ipc_server._handle_daemon_state_full({})
    assert sem_jogo["jogo_steam"] == {"lido": True, "appid": None}


async def test_a_ponta_a_ponta_o_state_full_faz_a_janela_decidir(
    ipc_server: IpcServer,
) -> None:
    """O que o daemon publica é exatamente o que a janela sabe ler.

    Este é o teste que impede as duas pontas de divergirem em silêncio: o nome
    da chave está escrito em dois arquivos (o handler e o `painel_no_jogo`), e
    um `rename` de um lado só passaria por todos os outros testes desta bancada.
    """
    ipc_server.store.set_steam_jogo_appid(PRAGMATA)
    assert jogo_steam_aberto(await ipc_server._handle_daemon_state_full({})) is True

    ipc_server.store.set_steam_jogo_appid(None)
    assert jogo_steam_aberto(await ipc_server._handle_daemon_state_full({})) is False
