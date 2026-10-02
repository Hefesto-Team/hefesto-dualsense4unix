"""ESCRITOR-CRU-01 — a Steam apaga a barra, e o produto não reagia."""
from __future__ import annotations

import asyncio
import os
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest import mock

import pytest

import hefesto_dualsense4unix.core.escritor_cru as _escritor_cru
import hefesto_dualsense4unix.daemon.connection as conn_mod
from hefesto_dualsense4unix.app.widgets.controller_card import (
    ROTULO_LIGHTBAR_SEGURADA,
    rotulo_lightbar,
)
from hefesto_dualsense4unix.core.escritor_cru import (
    SentinelaDeEscritorCru,
    Veredito,
)
from hefesto_dualsense4unix.core.events import EventBus
from hefesto_dualsense4unix.core.sysfs_leds import SysfsLedNode
from hefesto_dualsense4unix.daemon.connection import (
    reconnect_loop,
    registro_de_gatilhos_de,
    sentinela_de_escritor_cru_de,
)
from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin

UNIQ_A = "aabbcc000001"
UNIQ_B = "aabbcc000002"
NO_A = "/dev/hidraw90"
NO_B = "/dev/hidraw91"

ATRASO_CURTO = 0.05


def test_a_classe_led_nao_ve_o_escritor_cru(tmp_path: Path) -> None:
    """O detector antigo, exercitado contra um escritor CRU: ele não vê nada."""
    indicador = tmp_path / "input9:rgb:indicator"
    indicador.mkdir()
    (indicador / "multi_intensity").write_text("0 0 0")
    (indicador / "brightness").write_text("0")
    node = SysfsLedNode(str(indicador), [])

    assert node.set_rgb(0, 255, 0) is True
    assert (indicador / "multi_intensity").read_text().strip() == "0 255 0"

    assert node.set_rgb(0, 255, 0, verify=True) is True
    assert node.get_rgb() == (0, 255, 0), "a classe LED segue com a nossa cor"


def _sonda(mapa: Mapping[str, list[int]]) -> Callable[..., dict[str, list[int]]]:
    """Sonda injetada: devolve `mapa` filtrado pelos nós pedidos. Conta chamadas."""

    def sonda(nos: Iterable[str] | None = None) -> dict[str, list[int]]:
        sonda.chamadas += 1  # type: ignore[attr-defined]
        alvos = set(nos or ())
        return {n: list(p) for n, p in mapa.items() if not alvos or n in alvos}

    sonda.chamadas = 0  # type: ignore[attr-defined]
    return sonda


def test_o_sentinela_ve_o_escritor_que_a_classe_nao_ve() -> None:
    """A resposta a *"quem escreveu preto?"* — pelo `fd`, que é observável."""
    sentinela = SentinelaDeEscritorCru(sonda=_sonda({NO_A: [4242]}))

    veredito, novos = sentinela.sondar([NO_A, NO_B], 100.0)
    assert veredito.sondado is True
    assert veredito.segurado(NO_A) is True
    assert veredito.pids(NO_A) == (4242,)
    assert veredito.segurado(NO_B) is False
    assert novos == ()


def test_veredito_novo_nasce_sem_sonda_e_isso_nao_e_limpo() -> None:
    """O terceiro estado: **não sondado** não é "ninguém segura"."""
    vazio = Veredito()
    assert vazio.sondado is False
    assert vazio.algum is False
    assert vazio.segurado(NO_A) is False


def test_a_steam_aberta_o_dia_inteiro_e_borda_uma_vez_so() -> None:
    """Segurar o `fd` é estado NORMAL — só a BORDA licencia reafirmar."""
    sonda = _sonda({})
    sentinela = SentinelaDeEscritorCru(sonda=sonda, validade_s=0.0)

    sentinela.sondar([NO_A], 100.0)

    sentinela._sonda = _sonda({NO_A: [4242]})  # type: ignore[assignment]
    _veredito, novos = sentinela.sondar([NO_A], 101.0)
    assert novos == (NO_A,)

    for t in (102.0, 103.0, 104.0):
        _v, novos = sentinela.sondar([NO_A], t)
        assert novos == (), "Steam aberta em regime não pode armar de novo"


def test_a_validade_evita_a_rajada_de_pgrep() -> None:
    """Arrastar o seletor de cor não pode virar uma rajada de subprocessos."""
    sonda = _sonda({NO_A: [4242]})
    sentinela = SentinelaDeEscritorCru(sonda=sonda, validade_s=5.0)

    sentinela.sondar([NO_A], 100.0)
    for t in (100.1, 100.5, 101.0, 104.9):
        sentinela.sondar([NO_A], t)
    assert sonda.chamadas == 1, "sondou dentro da validade"  # type: ignore[attr-defined]

    sentinela.sondar([NO_A], 105.1)
    assert sonda.chamadas == 2  # type: ignore[attr-defined]

    sentinela.sondar([NO_A], 105.2, forcar=True)
    assert sonda.chamadas == 3  # type: ignore[attr-defined]


def test_a_sonda_que_falha_preserva_a_foto() -> None:
    """`pgrep` que morreu não é prova de que a Steam fechou."""

    def explode(nos: Iterable[str] | None = None) -> dict[str, list[int]]:
        raise OSError("sem /proc")

    sentinela = SentinelaDeEscritorCru(sonda=_sonda({NO_A: [7]}), validade_s=0.0)
    sentinela.sondar([NO_A], 100.0)
    sentinela._sonda = explode  # type: ignore[assignment]

    veredito, novos = sentinela.sondar([NO_A], 101.0)
    assert veredito.segurado(NO_A) is True, "apagou a foto por causa da falha"
    assert novos == ()


def test_o_sentinela_do_daemon_e_um_so() -> None:
    """Uma foto por daemon: o vigia que arma e a aba Status leem a MESMA."""
    daemon = SimpleNamespace(_sentinela_de_escritor_cru=None)
    primeiro = sentinela_de_escritor_cru_de(daemon)  # type: ignore[arg-type]
    assert isinstance(primeiro, SentinelaDeEscritorCru)
    assert sentinela_de_escritor_cru_de(daemon) is primeiro  # type: ignore[arg-type]


class _Controller:
    """Backend de mentira com os dois sinais do gatilho e a repintura."""

    def __init__(self, *, nos: dict[str, str] | None = None) -> None:
        self.connect_calls = 0
        self.pinturas = 0
        self.repinturas = 0
        self.nos = nos if nos is not None else {UNIQ_A: NO_A}

    def connect(self) -> None:
        self.connect_calls += 1

    def is_connected(self) -> bool:
        return True

    def get_transport(self) -> str:
        return "bt"

    def pintou(self, quantas: int = 1) -> None:
        """O que o `_pintar_por_hidraw_bt` faz quando um comando nosso sai."""
        self.pinturas += quantas

    def consumir_pinturas_de_lightbar(self) -> int:
        n = self.pinturas
        self.pinturas = 0
        return n

    def consumir_conexoes_bt_novas(self) -> int:
        return 0

    def nos_hidraw_por_uniq(self) -> dict[str, str]:
        return dict(self.nos)

    def reescrever_lightbar_por_hidraw(self) -> dict[str, bool]:
        self.repinturas += 1
        return {UNIQ_A: True}


class _FakeWatch:
    def __init__(self) -> None:
        self._changed = False

    def trip(self) -> None:
        self._changed = True

    def poll(self) -> bool:
        mudou = self._changed
        self._changed = False
        return mudou


class _StubDaemon:
    """Superfície mínima do DaemonProtocol que o `reconnect_loop` toca."""

    def __init__(self, controller: _Controller, *, nativo: bool = False) -> None:
        self.controller = controller
        self.bus = EventBus()
        self.config = SimpleNamespace(reconnect_backoff_sec=0.01, auto_reconnect=True)
        self._stop_event = asyncio.Event()
        self._registro_de_gatilhos: Any = None
        self._sentinela_de_escritor_cru: Any = None
        self._nativo = nativo

    def is_native_mode(self) -> bool:
        return self._nativo

    def _is_stopping(self) -> bool:
        return self._stop_event.is_set()

    async def _run_blocking(self, fn: Callable[..., Any], *args: Any) -> Any:
        return fn(*args)

    def _arm_input_grace(self) -> None:
        pass

    def stop(self) -> None:
        self._stop_event.set()


async def _until(cond: Callable[[], bool], timeout: float = 3.0) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while not cond():
        if loop.time() > deadline:
            raise AssertionError("condição não alcançada dentro do prazo")
        await asyncio.sleep(0.005)


def _fatias_curtas(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(conn_mod, "RECONNECT_HOTPLUG_POLL_INTERVAL_SEC", 0.01)
    monkeypatch.setattr(conn_mod, "RECONNECT_ONLINE_CHECK_INTERVAL_SEC", 30.0)
    monkeypatch.setattr(conn_mod, "PASSO_ENQUANTO_O_GATILHO_ESTA_ARMADO_SEC", 0.01)


async def _laco(
    daemon: _StubDaemon, watch: _FakeWatch, sentinela: SentinelaDeEscritorCru
) -> asyncio.Task[None]:
    daemon._sentinela_de_escritor_cru = sentinela
    task = asyncio.create_task(
        reconnect_loop(daemon, input_watch=watch)  # type: ignore[arg-type]
    )
    await _until(lambda: daemon.controller.connect_calls >= 1)
    gatilho = registro_de_gatilhos_de(daemon).obter("lightbar")  # type: ignore[arg-type]
    assert gatilho is not None, "o laço não registrou o gatilho da lightbar"
    gatilho._atraso_s = ATRASO_CURTO
    return task


@pytest.mark.asyncio
async def test_a_mordida_comando_nosso_com_a_steam_segurando_repinta_no_silencio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A CURA, ponta a ponta — e é este teste que reprova se ela for arrancada."""
    _fatias_curtas(monkeypatch)
    ctrl = _Controller()
    daemon = _StubDaemon(ctrl)
    watch = _FakeWatch()
    sentinela = SentinelaDeEscritorCru(sonda=_sonda({NO_A: [4242]}), validade_s=0.0)
    task = await _laco(daemon, watch, sentinela)
    try:
        for _ in range(3):
            ctrl.pintou()
            await asyncio.sleep(ATRASO_CURTO / 3)
        await _until(lambda: ctrl.repinturas >= 1)
        await asyncio.sleep(ATRASO_CURTO * 4)
        assert ctrl.repinturas == 1, "repintou mais de uma vez pela mesma rajada"
    finally:
        daemon.stop()
        await task


@pytest.mark.asyncio
async def test_sem_escritor_cru_o_comando_nosso_nao_repinta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sem Steam na mesa, pintar não licencia repintar."""
    _fatias_curtas(monkeypatch)
    ctrl = _Controller()
    daemon = _StubDaemon(ctrl)
    watch = _FakeWatch()
    sentinela = SentinelaDeEscritorCru(sonda=_sonda({}), validade_s=0.0)
    task = await _laco(daemon, watch, sentinela)
    try:
        ctrl.pintou()
        await asyncio.sleep(ATRASO_CURTO * 6)
        assert ctrl.repinturas == 0
    finally:
        daemon.stop()
        await task


@pytest.mark.asyncio
async def test_em_modo_nativo_nao_sonda_nem_repinta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regra dela: *"no modo nativo devolvemos o controle pra steam"*."""
    _fatias_curtas(monkeypatch)
    ctrl = _Controller()
    daemon = _StubDaemon(ctrl, nativo=True)
    watch = _FakeWatch()
    sonda = _sonda({NO_A: [4242]})
    sentinela = SentinelaDeEscritorCru(sonda=sonda, validade_s=0.0)
    task = await _laco(daemon, watch, sentinela)
    try:
        ctrl.pintou()
        await asyncio.sleep(ATRASO_CURTO * 6)
        assert ctrl.repinturas == 0
        assert sonda.chamadas == 0, "sondou /proc em Modo Nativo"  # type: ignore[attr-defined]
    finally:
        daemon.stop()
        await task


@pytest.mark.asyncio
async def test_a_steam_subindo_repinta_sem_ninguem_mexer_em_nada(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A outra metade da medição: *"o daemon NÃO reagiu em 60 s"*."""
    _fatias_curtas(monkeypatch)
    ctrl = _Controller()
    daemon = _StubDaemon(ctrl)
    watch = _FakeWatch()
    sentinela = SentinelaDeEscritorCru(sonda=_sonda({}), validade_s=0.0)
    task = await _laco(daemon, watch, sentinela)
    try:
        await asyncio.sleep(ATRASO_CURTO * 4)
        assert ctrl.repinturas == 0, "repintou com a mesa limpa"
        sentinela._sonda = _sonda({NO_A: [4242]})  # type: ignore[assignment]
        watch.trip()
        await _until(lambda: ctrl.repinturas >= 1)
        await asyncio.sleep(ATRASO_CURTO * 4)
        assert ctrl.repinturas == 1, "a Steam aberta em regime virou martelo"
    finally:
        daemon.stop()
        await task


def test_a_aba_status_conta_que_a_barra_esta_disputada() -> None:
    """Hoje o card mostra a cor PEDIDA como se fosse a acesa. Agora ele avisa."""
    entry = {
        "lightbar_rgb": [0, 255, 0],
        "lightbar_on": True,
        "lightbar_source": "sysfs",
        "lightbar_disputada": True,
    }
    rotulo, base = rotulo_lightbar(entry, {})
    assert rotulo == ROTULO_LIGHTBAR_SEGURADA
    assert "escreve" not in rotulo
    assert base == (0, 255, 0)

    entry["lightbar_disputada"] = False
    assert rotulo_lightbar(entry, {}) == (None, (0, 255, 0))


class _Handler(IpcHandlersMixin):
    """O mixin com o mínimo que `_lightbar_disputada` toca."""

    def __init__(self, daemon: Any) -> None:
        self.daemon = daemon  # type: ignore[assignment]


def test_o_campo_da_disputa_sai_da_foto_e_nunca_de_um_dible() -> None:
    """A regra dura: sem sonda, sem aviso — e MagicMock não vira alarme."""
    from unittest.mock import MagicMock

    nos = {UNIQ_A: NO_A, UNIQ_B: NO_B}

    assert _Handler(MagicMock())._lightbar_disputada(UNIQ_A, nos) is False
    assert _Handler(None)._lightbar_disputada(UNIQ_A, nos) is False

    daemon = SimpleNamespace(_sentinela_de_escritor_cru=SentinelaDeEscritorCru())
    handler = _Handler(daemon)
    assert handler._lightbar_disputada(UNIQ_A, nos) is False

    daemon._sentinela_de_escritor_cru._veredito = Veredito(
        sondado_em=1.0, por_no={NO_A: (os.getpid(),)}
    )
    assert handler._lightbar_disputada(UNIQ_A, nos) is True
    assert handler._lightbar_disputada(UNIQ_B, nos) is False, "respingou no vizinho"
    assert handler._lightbar_disputada(None, nos) is False

    daemon._sentinela_de_escritor_cru._veredito = Veredito(
        sondado_em=1.0, por_no={NO_A: (4242,)}
    )
    with mock.patch.object(_escritor_cru, "processo_vivo", lambda _p: False):
        assert handler._lightbar_disputada(UNIQ_A, nos) is False


def test_no_modo_nativo_o_aviso_da_disputa_continua_valendo() -> None:
    """A Steam segurando o `fd` é aviso sobre a CONFIANÇA na cor, e ele vale no"""
    entry = {
        "lightbar_rgb": [0, 255, 0],
        "lightbar_on": True,
        "lightbar_source": "sysfs",
        "lightbar_disputada": True,
    }
    rotulo, _base = rotulo_lightbar(entry, {"native_mode": True})
    assert rotulo == ROTULO_LIGHTBAR_SEGURADA
