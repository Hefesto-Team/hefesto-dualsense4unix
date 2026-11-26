"""O que está preso se solta quando a fonte cala.

A mão dos gestos dos acessórios sai emitindo o que segurava (o zero do acelerador, a camada 0, o
«desce» do lado segurado), e o tique dos acionadores roda uma vez por volta do laço do serviço,
antes do pad e do co-op: com o leitor do controle mudo, o acionador se solta quando o foco sai.
"""
from __future__ import annotations

import asyncio
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from types import MethodType, SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.core.evdev_reader import EvdevReader
from hefesto_dualsense4unix.daemon import lifecycle as lc
from hefesto_dualsense4unix.daemon.lifecycle import Daemon
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.daemon.subsystems import coop as co
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.daemon.subsystems.volta_dos_acessorios import (
    JANELA_DO_MEDIDOR_S,
    Ligacoes,
    VoltaDosAcessorios,
)
from hefesto_dualsense4unix.integrations.gestos_dos_acessorios import (
    GestosDosAcessorios,
    Opcoes,
)

P1 = "aa:bb:cc:00:00:01"
P2 = "aa:bb:cc:00:00:02"
NUMERO = (False, False, True, False, False)


@dataclass
class _Relogio:
    agora: float = 100.0

    def __call__(self) -> float:
        return self.agora


@dataclass
class _Gestos:
    """A máquina dos gestos com as opções trocáveis e o que a máquina emitiu."""

    opcoes: Opcoes | None
    ditos: list[tuple[str | None, str, float]] = field(default_factory=list)
    relogio: _Relogio = field(default_factory=_Relogio)

    def __post_init__(self) -> None:
        self.maquina = GestosDosAcessorios(
            valem=lambda _de: self.opcoes, emitir=self._emitir, relogio=self.relogio)
        self.ouvintes: list[Any] = []

    def _emitir(self, de: str | None, gesto: str, valor: float) -> None:
        self.ditos.append((de, gesto, valor))
        for ouvir in self.ouvintes:
            ouvir(de, gesto, valor)

    def ler(self, botoes: set[str], gatilhos: tuple[int, int] = (0, 0), de: str = P1) -> None:
        self.maquina.avaliar(botoes, gatilhos, now=self.relogio.agora, de=de)

    def andar(self, s: float) -> None:
        self.relogio.agora = round(self.relogio.agora + s, 6)


def test_o_acelerador_segurado_zera_quando_o_controle_sai() -> None:
    """R2 a fundo com o acelerador, e o controle sai: a mão emite o ``nivel_ao_vivo`` 0."""
    g = _Gestos(Opcoes(acelerador=True))
    g.ler({"ps"}, (0, 0))
    g.andar(0.05)
    g.ler({"ps", "r2_btn"}, (0, 255))
    assert (P1, "nivel_ao_vivo", 1.0) in g.ditos
    g.maquina.soltar_quem_saiu([P2])
    assert g.ditos[-1] == (P1, "nivel_ao_vivo", 0.0)


def test_o_lado_unico_segurado_desce_quando_os_gestos_deixam_de_valer() -> None:
    """R1 segurado no lado único, e o estado chega sem os gestos: sai o «desce» do lado."""
    g = _Gestos(Opcoes(lado_unico=True))
    g.ler({"ps"})
    g.andar(0.05)
    g.ler({"ps", "r1"})
    g.opcoes = None
    g.andar(0.05)
    g.ler({"ps", "r1"})
    assert g.ditos[-1] == (P1, "desce", 1)


def _volta_ligada_aos_gestos(g: _Gestos) -> tuple[VoltaDosAcessorios, list[Any]]:
    escritas: list[Any] = []
    volta = VoltaDosAcessorios(Ligacoes(
        motores=lambda *_a: None,
        ler_luzinhas=lambda _u: (NUMERO, 1),
        luzinhas=lambda uniq, acesas, degrau: escritas.append((uniq, acesas, degrau)),
        barra=lambda *_a: None,
        soltar_barra=lambda _u: None,
        pode_falar=lambda _u: True,
        o_jogo_pinta=lambda _u: False,
        estilo=lambda: None,
    ))
    volta.ao_estado({"ligado": True, "nivel": 3, "ajustes": {}}, g.relogio.agora)
    g.ouvintes.append(lambda de, gesto, valor: volta.ao_gesto(
        {"uniq": de, "gesto": gesto, "valor": valor}, g.relogio.agora))
    return volta, escritas


@pytest.mark.parametrize("como", ["sem_aparelhos", "o_controle_saiu", "o_prazo_venceu"])
def test_a_camada_que_cala_fecha_o_medidor_das_luzinhas(como: str) -> None:
    """Camada ligada, e a fonte cala (estado sem aparelhos, controle fora ou prazo vencido): o
    medidor das luzinhas fecha e o número do jogador volta."""
    g = _Gestos(Opcoes(camada=True, camada_s=1.0))
    volta, escritas = _volta_ligada_aos_gestos(g)
    g.ler({"ps"})
    g.andar(0.05)
    g.ler(set())
    g.andar(0.05)
    g.ler({"ps"})
    assert (P1, "camada", 1) in g.ditos and g.maquina.camada_ligada(P1)
    g.andar(0.05)
    g.ler(set())
    if como == "sem_aparelhos":
        g.opcoes = None
        g.ler(set())
    elif como == "o_controle_saiu":
        g.maquina.soltar_quem_saiu([])
    else:
        g.andar(1.5)
        g.ler(set())
    assert g.ditos[-1] == (P1, "camada", 0)
    fim = g.relogio.agora + JANELA_DO_MEDIDOR_S + 0.1
    while g.relogio.agora < fim:
        g.andar(0.05)
        volta.tique(g.relogio.agora)
    assert P1 not in volta._medidores, "o medidor ficou preso na camada"
    assert escritas[-1] == (P1, NUMERO, 1)


class _Aparelho:
    """O acionador aberto: quem o prende e o solta, e uma fila vazia."""

    def __init__(self) -> None:
        self.gestos: list[str] = []

    def read_one(self) -> None:
        return None

    def grab(self) -> None:
        self.gestos.append("grab")

    def ungrab(self) -> None:
        self.gestos.append("ungrab")

    def close(self) -> None: ...


class _Mudo(EvdevReader):
    """O leitor do controle calado: o rádio que some sem desconectar."""


@pytest.fixture(autouse=True)
def _sem_a_maquina(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(co.CoopManager, "sync", lambda self: None)
    monkeypatch.setattr(co.CoopManager, "_recolher_os_cedidos", lambda self: None)
    monkeypatch.setattr(co.CoopManager, "_promote_pending", lambda self: None)
    monkeypatch.setattr(lc, "reconciliar_as_mascaras", lambda daemon: None)
    monkeypatch.setattr(gp, "_reconciliar_launch", lambda d: None)
    monkeypatch.setattr(gp, "_avisar_troca_de_modo", lambda d: None)
    monkeypatch.setattr(lc, "INPUT_GRACE_SEC", 0.0)
    monkeypatch.setattr(lc, "RELOGIOS_LENTOS", ())
    monkeypatch.setattr(gp, "o_pad_da_peca_muda_repousa", lambda _d, _l: True)
    monkeypatch.setattr(co, "o_pad_da_peca_muda_repousa", lambda _d, _l: True)
    yield


class _LacoComOControleMudo:
    """O `_poll_loop` de produção: o P1 e o P2 de pé com o leitor calado, e um acionador preso."""

    def __init__(self, voltas: int) -> None:
        estado = ControllerState(
            battery_pct=80, l2_raw=0, r2_raw=0, connected=True, transport="bt")
        self.config = SimpleNamespace(poll_hz=60)
        self.controller: Any = SimpleNamespace(
            is_connected=lambda: True, read_state=lambda: estado)
        self.store = StateStore()
        self.bus = SimpleNamespace(publish=lambda *_a, **_k: None)
        self._stop_event: asyncio.Event | None = None
        self._input_ready_at = 0.0
        self._external_tick_task: Any = None
        self._steam_jogo_task: Any = None
        self._game_signal_task: Any = None
        self._last_state: Any = None
        self._gamepad_device: Any = SimpleNamespace(
            forward_analog=lambda **_k: None, forward_buttons=lambda _b: None)
        self._mouse_device: Any = None
        self._keyboard_device: Any = None
        self._touchpad_reader: Any = None
        self._hotkey_manager: Any = None
        self._plugins_subsystem: Any = None
        self._motion_reader: Any = _Mudo(device_path=Path("/nao/existe/p1"))
        self._paused = False
        self._native_mode = False
        self._emulation_suppressed = False
        self._emu_calada_motivo: Any = None
        self._janela_de_jogo_em_foco = lambda: False
        gerente = co.CoopManager.__new__(co.CoopManager)
        gerente._players = {P2: co._SecondaryPlayer(
            identity=P2, evdev_path="/dev/input/event-do-p2",
            reader=_Mudo(device_path=Path("/nao/existe/p2")), player_index=2,
            vpad=self._gamepad_device)}
        gerente._daemon = self  # type: ignore[assignment]
        self._coop_manager = gerente
        self.aparelho = _Aparelho()
        self._maquina = SimpleNamespace(acionadores={
            "pedal": SimpleNamespace(teclas={"30": "cross"}, controle=P1)})
        ponte = gp.PonteDosAcionadores(relogio=lambda: 0.0)
        ponte._abertos["pedal"] = gp._AcionadorAberto("/dev/input/event-do-pedal",
                                                     self.aparelho, preso=True)
        ponte._procurou_em = 0.0
        self._ponte_dos_acionadores = ponte
        self.ponte = ponte
        self._poll_loop = Daemon._poll_loop.__get__(self)
        self._dispatch_gamepad_emulation = MethodType(Daemon._dispatch_gamepad_emulation, self)
        self._restantes = voltas

    def _is_stopping(self) -> bool:
        self._restantes -= 1
        return self._restantes < 0

    async def _run_blocking(self, fn: Any, *args: Any) -> Any:
        return fn(*args)

    async def _run_tick_blocking(self, fn: Any, *args: Any) -> Any:
        return fn(*args)

    def _evdev_buttons_once(self) -> frozenset[str]:
        return frozenset()

    def _sync_identity_registry(self) -> None: ...
    def _seguir_a_carta(self) -> None: ...
    def aplicar_gamepad_para_multiplos_controles(self) -> None: ...
    def _amostrar_bateria(self, _agora: float) -> None: ...
    def _schedule_external_tick(self) -> None: ...
    def _schedule_steam_jogo_tick(self) -> None: ...
    def _reconciliar_exposicao_do_modo_nativo(self, **_k: object) -> None: ...
    def _drenar_modo_pendente(self) -> None: ...
    async def _sync_game_signal(self) -> None: ...
    def _reassert_rumble(self, _agora: float) -> None: ...
    def _jogo_no_controle_do_desktop(self) -> None:
        return None

    def _calar_emulacao_de_desktop(self, *_a: Any) -> None: ...
    def _liberar_emulacao_de_desktop(self, *_a: Any) -> None: ...
    def _prime_keyboard_emulation(self, *_a: Any) -> None: ...
    def _dispatch_keyboard_emulation(self, *_a: Any) -> None: ...
    def _dispatch_mouse_emulation(self, *_a: Any) -> None: ...

    async def rodar(self) -> None:
        self._stop_event = asyncio.Event()
        await self._poll_loop()


def test_o_acionador_preso_se_solta_com_o_controle_mudo_quando_o_foco_sai() -> None:
    """Leitor do P1 e do P2 calados, acionador preso e o foco fora do jogo: depois de uma volta
    do laço o aparelho está solto, sem depender do despacho do pad."""
    daemon = _LacoComOControleMudo(voltas=1)
    asyncio.run(daemon.rodar())
    assert daemon.aparelho.gestos == ["ungrab"]
    assert daemon.ponte._abertos["pedal"].preso is False
