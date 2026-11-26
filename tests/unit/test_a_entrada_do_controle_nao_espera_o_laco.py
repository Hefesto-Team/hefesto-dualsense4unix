"""A entrada do controle não espera o laço: o aperto vai do leitor ao pad pelo fio da entrada.

Com o laço asyncio parado 3 s (ou o fio do tique preso 3 s), o aperto de cada jogador, do P1 ao
P4, chega ao pad do jogador em menos de 20 ms, pelo ``UinputGamepad`` de produção sobre um nó de
mentira. O que solta durante a parada sai solto, cinco toques chegam como cinco, e o pad com
dois escritores (o fio da entrada e o tique) nunca rasga um report.
"""
from __future__ import annotations

import ast
import asyncio
import inspect
import sys
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from types import MethodType, SimpleNamespace
from typing import Any

import pytest
from evdev import ecodes

from hefesto_dualsense4unix.core import evdev_reader as er
from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.core.evdev_reader import EvdevReader
from hefesto_dualsense4unix.daemon import lifecycle as lc
from hefesto_dualsense4unix.daemon.lifecycle import Daemon
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.daemon.subsystems import coop as co
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.integrations import hotkey_daemon as hd
from hefesto_dualsense4unix.integrations.gestos_dos_acessorios import (
    GestosDosAcessorios,
    Opcoes,
)
from hefesto_dualsense4unix.integrations.uinput_gamepad import UinputGamepad

PARADA_S = 3.0
TETO_S = 0.020
_UNIQ = {n: f"aa:bb:cc:00:00:0{n}" for n in (1, 2, 3, 4)}


@dataclass
class _Evento:
    type: int
    code: int
    value: int


class _NoDeMentira:
    """O nó do uinput: a hora e o fio de cada escrita, e o ``syn``."""

    def __init__(self, ceder: bool = False) -> None:
        self.escritas: list[tuple[float, int, int, int, int]] = []
        self._ceder = ceder

    def write(self, tipo: int, codigo: int, valor: int) -> None:
        self.escritas.append((time.monotonic(), threading.get_ident(), tipo, codigo, valor))
        if self._ceder:
            time.sleep(0)

    def syn(self) -> None:
        self.escritas.append((time.monotonic(), threading.get_ident(), -1, 0, 0))

    def apertos(self, codigo: int) -> list[float]:
        return [t for t, _f, tipo, c, v in self.escritas
                if tipo == ecodes.EV_KEY and c == codigo and v == 1]

    def solto(self, codigo: int) -> bool:
        ultimos = [v for _t, _f, tipo, c, v in self.escritas
                   if tipo == ecodes.EV_KEY and c == codigo]
        return bool(ultimos) and ultimos[-1] == 0


def _pad(ceder: bool = False) -> tuple[UinputGamepad, _NoDeMentira]:
    no = _NoDeMentira(ceder)
    pad = UinputGamepad()
    pad._device = no
    pad._ecodes = ecodes
    return pad, no


def _leitor(n: int) -> EvdevReader:
    return EvdevReader(device_path=Path(f"/nao/existe/event-do-p{n}"))


def _apertar(leitor: EvdevReader, valor: int) -> None:
    leitor._handle_event(_Evento(ecodes.EV_KEY, ecodes.BTN_SOUTH, valor), ecodes)
    leitor._handle_event(_Evento(ecodes.EV_SYN, ecodes.SYN_REPORT, 0), ecodes)


@pytest.fixture(autouse=True)
def _sem_a_maquina(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """O que toca a máquina, ou não é o caminho do botão, sai."""
    monkeypatch.setattr(co.CoopManager, "sync", lambda self: None)
    monkeypatch.setattr(co.CoopManager, "_recolher_os_cedidos", lambda self: None)
    monkeypatch.setattr(co.CoopManager, "_promote_pending", lambda self: None)
    monkeypatch.setattr(gp, "_avisar_troca_de_modo", lambda d: None)
    yield
    er.definir_o_despertador(None)


def _mesa() -> tuple[Any, dict[int, EvdevReader], dict[int, _NoDeMentira]]:
    """P1 na mesa com o próprio pad, e P2 a P4 no co-op, cada um com leitor e pad próprios."""
    leitores = {n: _leitor(n) for n in (1, 2, 3, 4)}
    pads: dict[int, Any] = {}
    nos: dict[int, _NoDeMentira] = {}
    for n in (1, 2, 3, 4):
        pads[n], nos[n] = _pad()
    gerente = co.CoopManager.__new__(co.CoopManager)
    gerente._players = {}
    gerente._ordem_pendente = False
    for n in (2, 3, 4):
        gerente._players[_UNIQ[n]] = co._SecondaryPlayer(
            identity=_UNIQ[n], evdev_path=f"/dev/input/event-do-p{n}", reader=leitores[n],
            player_index=n, vpad=pads[n])
    daemon = SimpleNamespace(
        controller=SimpleNamespace(_evdev=leitores[1], is_connected=lambda: True),
        store=StateStore(),
        _gamepad_device=pads[1],
        _mouse_device=None,
        _input_ready_at=0.0,
        _last_state=ControllerState(
            battery_pct=80, l2_raw=0, r2_raw=0, connected=True, transport="usb"),
        _coop_manager=gerente,
    )
    gerente._daemon = daemon
    daemon._evdev_buttons_once = MethodType(Daemon._evdev_buttons_once, daemon)
    daemon._dispatch_gamepad_emulation = MethodType(Daemon._dispatch_gamepad_emulation, daemon)
    return daemon, leitores, nos


def _no_fio_do_leitor(alvo: Any) -> threading.Thread:
    fio = threading.Thread(target=alvo, name="leitor-de-mentira", daemon=True)
    fio.start()
    return fio


async def _preso(como: str) -> None:
    """A parada: o laço asyncio inteiro, ou o tique esperando o fio da leitura."""
    if como == "laco":
        time.sleep(PARADA_S)
    else:
        await asyncio.gather(
            asyncio.to_thread(time.sleep, PARADA_S), asyncio.to_thread(time.sleep, PARADA_S))


def _com_a_espera_de_producao(daemon: Any, durante: Any, como: str) -> None:
    """A espera do `_poll_loop` armada; ``durante`` roda no fio do leitor a 30 % da parada."""

    async def cenario() -> None:
        parada = asyncio.Event()
        espera = asyncio.create_task(lc._esperar_o_tique(daemon, parada, 30.0))
        await asyncio.sleep(0.05)
        timer = threading.Timer(PARADA_S * 0.3, lambda: _no_fio_do_leitor(durante).join())
        timer.start()
        await _preso(como)
        timer.join()
        await asyncio.sleep(0.05)
        parada.set()
        await espera

    asyncio.run(cenario())


@pytest.mark.parametrize("como", ["laco", "pool"])
def test_o_aperto_de_p1_a_p4_chega_ao_pad_com_o_laco_preso(como: str) -> None:
    """Laço preso 3 s, ou os dois fios presos 3 s: o X de cada jogador chega em menos de 20 ms.

    Prova da D-2611-A-ENTRADA-ANDA-NO-FIO-DA-ENTRADA-E-NAO-ESPERA-O-LACO.
    """
    daemon, leitores, nos = _mesa()
    apertou: dict[int, float] = {}

    def apertar() -> None:
        for n in (1, 2, 3, 4):
            apertou[n] = time.monotonic()
            _apertar(leitores[n], 1)
            time.sleep(0.03)

    _com_a_espera_de_producao(daemon, apertar, como)
    for n in (1, 2, 3, 4):
        chegadas = nos[n].apertos(ecodes.BTN_SOUTH)
        assert chegadas, f"o X do P{n} não chegou ao pad"
        atraso = chegadas[0] - apertou[n]
        assert atraso < TETO_S, f"P{n}: {atraso * 1000:.1f} ms com o {como} preso"


def test_soltar_na_parada_sai_solto_e_cinco_toques_chegam_como_cinco() -> None:
    """Com o laço preso, cinco toques do P3 e do P1 chegam ao pad como cinco, e o fim sai solto."""
    daemon, leitores, nos = _mesa()

    def tocar() -> None:
        for _ in range(5):
            for n in (1, 3):
                _apertar(leitores[n], 1)
            time.sleep(0.02)
            for n in (1, 3):
                _apertar(leitores[n], 0)
            time.sleep(0.02)

    _com_a_espera_de_producao(daemon, tocar, "laco")
    for n in (1, 3):
        assert len(nos[n].apertos(ecodes.BTN_SOUTH)) == 5, f"P{n}"
        assert nos[n].solto(ecodes.BTN_SOUTH), f"P{n} ficou apertado"
    assert nos[2].apertos(ecodes.BTN_SOUTH) == [] and nos[4].apertos(ecodes.BTN_SOUTH) == []


def test_o_pad_com_dois_escritores_nao_rasga_o_report() -> None:
    """Rajada de dois fios no mesmo pad: entre dois ``syn``, toda escrita é de um fio só."""
    antes = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    pad, no = _pad(ceder=True)
    largada = threading.Barrier(2)

    def rajada(botoes: tuple[frozenset[str], frozenset[str]]) -> None:
        largada.wait()
        for i in range(400):
            pad.forward_buttons(botoes[i % 2])
            pad.forward_analog(lx=i % 256, ly=0, rx=0, ry=0, l2=0, r2=0)

    try:
        fios = [
            threading.Thread(target=rajada, args=((frozenset({"cross", "circle"}), frozenset()),)),
            threading.Thread(target=rajada, args=((frozenset({"square"}), frozenset({"r1"})),)),
        ]
        for f in fios:
            f.start()
        for f in fios:
            f.join()
    finally:
        sys.setswitchinterval(antes)
    rasgados = 0
    fio_do_report: int | None = None
    for _t, fio, tipo, _c, _v in no.escritas:
        if fio_do_report is None:
            fio_do_report = fio
        elif fio != fio_do_report:
            rasgados += 1
        if tipo == -1:
            fio_do_report = None
    assert rasgados == 0, f"{rasgados} escritas de outro fio no meio de um report"


def _chamadas_com(rotina: Any) -> list[tuple[str, dict[str, Any]]]:
    """Cada chamada em ``rotina``: o nome e as palavras-chave constantes."""
    arvore = ast.parse(inspect.getsource(rotina).lstrip())
    chamadas: list[tuple[str, dict[str, Any]]] = []
    for no in ast.walk(arvore):
        if isinstance(no, ast.Call):
            alvo = no.func
            nome = alvo.id if isinstance(alvo, ast.Name) else getattr(alvo, "attr", "")
            chaves = {k.arg: k.value.value for k in no.keywords
                      if k.arg and isinstance(k.value, ast.Constant)}
            chamadas.append((nome, chaves))
    return chamadas


def test_o_fio_da_entrada_repassa_pela_mesma_mistura_sem_a_manutencao() -> None:
    """O fio da entrada chama o MESMO ``dispatch_gamepad`` e ``forward_all`` do tique (sem cópia
    da mistura), com ``manter=False``; e não pede o laço asyncio."""
    volta = _chamadas_com(lc._volta_do_aperto)
    nomes = {nome for nome, _k in volta}
    assert ("dispatch_gamepad", {"manter": False}) in volta
    assert ("forward_all", {"manter": False}) in volta
    assert all(k.get("manter") is False for nome, k in volta
               if nome in {"dispatch_gamepad", "forward_all"})
    assert "get_running_loop" not in nomes and "_dispatch_gamepad_emulation" not in nomes


def test_o_fio_da_entrada_nao_marca_o_fio_do_laco() -> None:
    """A guarda `_fio_do_laco` do co-op segue a do laço: o repasse no fio da entrada não a troca."""
    daemon, leitores, _nos = _mesa()

    async def cenario() -> int | None:
        daemon._coop_manager.forward_all()
        marcado = daemon._coop_manager._fio_do_laco
        parada = asyncio.Event()
        espera = asyncio.create_task(lc._esperar_o_tique(daemon, parada, 5.0))
        await asyncio.sleep(0.02)
        _no_fio_do_leitor(lambda: _apertar(leitores[2], 1)).join()
        await asyncio.sleep(0.05)
        parada.set()
        await espera
        assert daemon.store.counter("poll.volta_do_aperto") >= 1
        return marcado

    marcado = asyncio.run(cenario())
    assert marcado is not None and daemon._coop_manager._fio_do_laco == marcado


def test_o_p1_com_o_pad_dualsense_recebe_o_aperto_com_o_laco_preso(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O P1 com o ``UhidDualSense`` de produção (o fd do uhid de mentira): o report do X sai em
    menos de 20 ms com o laço preso 3 s."""
    import os
    import struct

    from hefesto_dualsense4unix.integrations.uhid_blueprint import canonical_blueprint
    from hefesto_dualsense4unix.integrations.uhid_gamepad import UHID_START, UhidDualSense

    lidos: list[bytes] = [struct.pack("<I", UHID_START)]
    escritas: list[float] = []

    def ler(_fd: int, _tamanho: int) -> bytes:
        if not lidos:
            raise BlockingIOError
        return lidos.pop(0)

    def escrever(_fd: int, dado: bytes) -> int:
        escritas.append(time.monotonic())
        return len(dado)

    monkeypatch.setattr(os, "open", lambda *_a, **_k: 4242)
    monkeypatch.setattr(os, "close", lambda _fd: None)
    monkeypatch.setattr(os, "set_blocking", lambda _fd, _b: None)
    monkeypatch.setattr(os, "write", escrever)
    monkeypatch.setattr(os, "read", ler)
    pad = UhidDualSense(player=1, blueprint=canonical_blueprint())
    assert pad.start() is True
    try:
        pad.pump_ff()
        daemon, leitores, _nos = _mesa()
        daemon._gamepad_device = pad
        apertou: dict[str, float] = {}

        def apertar() -> None:
            apertou["em"] = time.monotonic()
            _apertar(leitores[1], 1)

        _com_a_espera_de_producao(daemon, apertar, "laco")
    finally:
        pad.stop()
    depois = [t for t in escritas if t >= apertou["em"]]
    assert depois, "nenhum report saiu depois do aperto"
    assert depois[0] - apertou["em"] < TETO_S, f"{(depois[0] - apertou['em']) * 1000:.1f} ms"


_FIO_DA_ENTRADA = "entrada-de-mentira"


def _o_laco_espera(chamada: Any, dentro: threading.Event, seguir: threading.Event) -> bool:
    """Com o fio da entrada parado dentro da máquina, ``chamada`` no outro fio espera ele sair?"""
    assert dentro.wait(2.0), "o fio da entrada não entrou na máquina"
    acabou = threading.Event()

    def laco() -> None:
        chamada()
        acabou.set()

    fio = threading.Thread(target=laco, name="laco-de-mentira", daemon=True)
    fio.start()
    cedo = acabou.wait(0.2)
    seguir.set()
    fio.join(2.0)
    return not cedo and acabou.is_set()


@pytest.mark.parametrize("chamada", ["soltar_quem_saiu", "consumir", "avaliar"])
def test_a_maquina_dos_gestos_atende_um_fio_por_vez(chamada: str) -> None:
    """O fio da entrada (o repasse) e o laço (os atalhos) leem a mesma mão dos gestos: com o fio
    da entrada no meio da avaliação, o laço espera, e a borda do PS e do gatilho nasce uma vez.

    Prova da D-2611-A-MAQUINA-DOS-GESTOS-ATENDE-UM-FIO-POR-VEZ.
    """
    dentro = threading.Event()
    seguir = threading.Event()

    def emitir(_de: str | None, _gesto: str, _valor: float) -> None:
        if threading.current_thread().name == _FIO_DA_ENTRADA:
            dentro.set()
            seguir.wait(2.0)

    maquina = GestosDosAcessorios(
        valem=lambda _de: Opcoes(acelerador=True), emitir=emitir, relogio=lambda: 100.0)
    p1 = _UNIQ[1]
    maquina.avaliar({"ps"}, (0, 0), now=100.0, de=p1)
    entrada = threading.Thread(
        target=lambda: maquina.avaliar({"ps", "r2_btn"}, (0, 255), now=100.05, de=p1),
        name=_FIO_DA_ENTRADA, daemon=True)
    entrada.start()
    do_laco = {
        "soltar_quem_saiu": lambda: maquina.soltar_quem_saiu([]),
        "consumir": lambda: maquina.consumir(p1),
        "avaliar": lambda: maquina.avaliar({"ps", "r2_btn"}, (0, 255), now=100.05, de=p1),
    }[chamada]
    try:
        assert _o_laco_espera(do_laco, dentro, seguir), (
            f"o {chamada} do laço correu no meio da avaliação do fio da entrada")
    finally:
        seguir.set()
        entrada.join(2.0)


def test_o_aperto_de_cada_controle_nasce_e_sai_um_fio_por_vez(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O fio da entrada cria o aperto do controle novo enquanto o laço esquece quem saiu: o laço
    espera, e o dicionário dos apertos nunca muda no meio da volta.

    Prova da D-2611-A-MAQUINA-DOS-GESTOS-ATENDE-UM-FIO-POR-VEZ.
    """
    dentro = threading.Event()
    seguir = threading.Event()
    original = hd._Aperto

    def aperto_lento() -> Any:
        if threading.current_thread().name == _FIO_DA_ENTRADA:
            dentro.set()
            seguir.wait(2.0)
        return original()

    monkeypatch.setattr(hd, "_Aperto", aperto_lento)
    gerente = hd.HotkeyManager()
    entrada = threading.Thread(
        target=lambda: gerente.combo_buttons_active({"cross"}, de=_UNIQ[2]),
        name=_FIO_DA_ENTRADA, daemon=True)
    entrada.start()
    try:
        assert _o_laco_espera(lambda: gerente.soltar_quem_saiu([]), dentro, seguir), (
            "o laço esqueceu os apertos no meio da criação do fio da entrada")
    finally:
        seguir.set()
        entrada.join(2.0)
