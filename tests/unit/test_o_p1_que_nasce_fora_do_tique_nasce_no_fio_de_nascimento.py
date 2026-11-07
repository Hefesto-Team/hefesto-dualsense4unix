"""O-P1-QUE-NASCE-FORA-DO-TIQUE-NASCE-NO-FIO-DE-NASCIMENTO-01 — todo P1 nasce no fio.

O `Daemon` REAL, com o `CoopManager` real, o fio de nascimento do daemon
(`virtual_pad.FioDeNascimento`) e o broker de mentira, que segura o pedido do P1 até o
tique o soltar. O laço do tique é emulado a 60 Hz na thread do teste: a cada volta, o
`forward_all` dos secundários, o `fechar_o_p1_que_nasceu` que o `_poll_loop` roda depois
dele, e a entrada do White. O tique solta o broker depois de o White jogar três voltas com
o pedido em voo.

Os cinco caminhos que sobem o P1 fora do `reerguer_o_p1` (o passo `coop_gamepad`, o
PS + R3, a troca de roupa, a saída do Modo Nativo e a IPC) voltam antes de o broker ser
solto, o White joga enquanto o P1 nasce, e o P1 nasce quando a resposta chega. A IPC
responde o desfecho de verdade, depois de o broker ser solto. Tudo se prova pela ORDEM dos
eventos, nunca pela duração: quem espera o P1 no laço fica preso até a guarda do broker, e
a guarda deixa a marca «prazo» na ordem; quem espera a entrega no laço por um prazo curto,
antes de o broker ser solto, deixa a marca «esperou».

Nenhum endereço real: faixa forjada ``aa:bb:cc`` com os octetos 4 e 5 zerados.
"""

from __future__ import annotations

import asyncio
import threading
import time
from collections.abc import Callable, Coroutine, Iterator
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core import physical_report_reader as prr
from hefesto_dualsense4unix.core.evdev_reader import EvdevReader
from hefesto_dualsense4unix.core.numeros_da_sony import ROUPA_COMUM, ROUPA_PADRAO
from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
from hefesto_dualsense4unix.daemon.lifecycle import Daemon
from hefesto_dualsense4unix.daemon.subsystems import coop as coop_mod
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.daemon.subsystems import hotkey
from hefesto_dualsense4unix.integrations import virtual_pad as vp
from hefesto_dualsense4unix.integrations.uinput_gamepad import normalize_flavor
from hefesto_dualsense4unix.profiles import loader as _loader  # noqa: F401
from hefesto_dualsense4unix.testing import FakeController

_P1 = "aabbcc000001"
_WHITE = "aabbcc000002"
_CALIB = bytes([0x05]) + bytes([0xAB]) * 40
_TIQUE_S = 1.0 / 60.0
_TIQUES_DO_WHITE = 3
_GUARDA_DO_BROKER_S = 5.0
_GUARDA_S = 2 * _GUARDA_DO_BROKER_S
_PEDIDO = "pedido"
_SOLTO = "solto"
_PRAZO = "prazo"
_ESPEROU = "esperou"
_TIQUE_DO_WHITE = "tique do White"
_GESTO_VOLTOU = "gesto voltou"
_RESPONDEU = "respondeu"


class _Pad:
    """O pad de mentira: anota quando recebe entrada e quando para."""

    def __init__(self, identity: str | None, flavor: Any, caminho: Any, roupa: Any) -> None:
        self.identity = identity
        self.flavor = flavor
        self.backend = "uhid"
        self.caminho = caminho
        self.product = ROUPA_PADRAO if roupa is None else roupa
        self.entradas: list[float] = []
        self.parado = False

    def forward_buttons(self, pressed: frozenset[str]) -> None:
        self.entradas.append(time.monotonic())

    def forward_analog(self, *args: Any, **kwargs: Any) -> None:
        pass

    def forward_triggers(self, *args: Any, **kwargs: Any) -> None:
        pass

    def pump_ff(self) -> None:
        pass

    def is_active(self) -> bool:
        return not self.parado

    def stop(self) -> None:
        self.parado = True


class _Leitor(EvdevReader):
    def __init__(self) -> None:
        self._grab_state = "held"

    def set_grab(self, grab: bool) -> bool:
        return True

    def stop(self) -> None:
        pass

    def snapshot(self) -> Any:
        return SimpleNamespace(lx=128, ly=128, rx=128, ry=128, l2_raw=0, r2_raw=0,
                               buttons_pressed=frozenset(), apertos=None)


class _Ipc(IpcHandlersMixin):
    def __init__(self, daemon: Any) -> None:
        self.daemon = daemon


_CALIBRACAO_DE_VERDADE = gp.read_primary_calibration


@pytest.fixture
def mesa(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> Iterator[SimpleNamespace]:
    from hefesto_dualsense4unix.utils import session as session_mod

    monkeypatch.setattr(session_mod, "config_dir", lambda ensure=False: tmp_path)
    monkeypatch.setattr(prr, "PhysicalReportReader", lambda **_k: None)
    for nome in ("_materialize_launch_env", "_broker_hide_player",
                 "_start_player_motion_reader", "_armar_sossego_do_launch_env"):
        monkeypatch.setattr(coop_mod.CoopManager, nome, lambda self, *a, **k: None)
    for nome in ("_set_controller_grab", "start_motion_reader", "stop_motion_reader",
                 "_materialize_launch_env", "soltar_a_ativacao", "notify_vpad_degradado"):
        monkeypatch.setattr(gp, nome, lambda *a, **k: None)
    monkeypatch.setattr(gp, "read_primary_calibration", lambda _d: None)
    monkeypatch.setattr(gp, "controller_allows_uhid", lambda _d: True)
    monkeypatch.setattr(gp, "_ha_jogo_em_foco", lambda _d: False)
    monkeypatch.setattr(gp, "make_primary_rumble_sink", lambda _d: None)
    monkeypatch.setattr(gp, "make_primary_replica_sinks", lambda _d: {})
    estado = SimpleNamespace(falhar=False, pedidos=[], pads={}, ordem=[],
                             soltar=threading.Event())
    laco = threading.current_thread()
    esperar = vp.PedidoDePad.esperar

    def _esperar(pedido: vp.PedidoDePad, prazo_s: float | None = None) -> bool:
        """A espera da entrega, que só a borda fora do laço faz."""
        if threading.current_thread() is laco and not estado.soltar.is_set():
            estado.ordem.append(_ESPEROU)
        return esperar(pedido, prazo_s)

    monkeypatch.setattr(vp.PedidoDePad, "esperar", _esperar)

    def _fabrica(flavor: Any, **kwargs: Any) -> _Pad | None:
        """A fábrica do pad: o do P1 espera o tique soltar o broker de mentira; o do White, não.

        Ninguém soltou até a guarda: o broker responde pelo relógio dele e deixa «prazo».
        """
        identidade = kwargs.get("identity")
        if identidade is None:
            estado.pedidos.append(threading.current_thread().name)
            estado.ordem.append(_PEDIDO)
            if not estado.soltar.wait(_GUARDA_DO_BROKER_S):
                estado.ordem.append(_PRAZO)
            if estado.falhar:
                return None
        pad = _Pad(identidade, flavor, kwargs.get("caminho"), kwargs.get("roupa"))
        estado.pads[str(identidade)] = pad
        return pad

    monkeypatch.setattr(vp, "make_virtual_pad", _fabrica)
    daemon = Daemon(controller=FakeController())
    daemon.config.coop_enabled = True
    daemon._fio_de_nascimento = vp.FioDeNascimento()
    gravados: list[tuple[str, Any]] = []
    monkeypatch.setattr(daemon, "gravar_o_modo_escolhido", lambda modo, **_k: gravados.append(
        (modo, daemon._gamepad_device)))
    manager = coop_mod.get_coop_manager(daemon)
    coop_mod.calibration_cache(daemon)[_WHITE] = _CALIB
    white = coop_mod._SecondaryPlayer(
        identity=_WHITE, evdev_path="/dev/input/event92", reader=_Leitor(), player_index=2,
    )
    manager._players[_WHITE] = white
    m = SimpleNamespace(daemon=daemon, manager=manager, white=white, gravados=gravados,
                        estado=estado)
    _ate(m, lambda: white.vpad is not None)
    yield m
    estado.soltar.set()
    daemon._fio_de_nascimento.parar()


def _fechar(daemon: Any) -> None:
    """O passo do `_poll_loop` depois do `forward_all` (ausente na medida de antes)."""
    fechar = getattr(gp, "fechar_o_p1_que_nasceu", None)
    if fechar is not None:
        fechar(daemon)


def _soltar(m: SimpleNamespace) -> None:
    m.estado.ordem.append(_SOLTO)
    m.estado.soltar.set()


def _tique_sem_dormir(m: SimpleNamespace) -> None:
    """Uma volta do laço, na ordem do `_poll_loop`: os secundários, o que nasceu e o White.

    A volta em que o White jogou entra na ordem; com o pedido do P1 em voo há
    `_TIQUES_DO_WHITE` voltas, o tique solta o broker.
    """
    entradas = len(m.white.vpad.entradas) if m.white.vpad is not None else 0
    m.manager.forward_all()
    _fechar(m.daemon)
    if m.white.vpad is not None:
        m.white.vpad.forward_buttons(frozenset())
        if len(m.white.vpad.entradas) > entradas:
            m.estado.ordem.append(_TIQUE_DO_WHITE)
    ordem = m.estado.ordem
    if (not m.estado.soltar.is_set() and _PEDIDO in ordem
            and ordem[ordem.index(_PEDIDO):].count(_TIQUE_DO_WHITE) >= _TIQUES_DO_WHITE):
        _soltar(m)


def _tique(m: SimpleNamespace) -> None:
    inicio = time.monotonic()
    _tique_sem_dormir(m)
    sobra = _TIQUE_S - (time.monotonic() - inicio)
    if sobra > 0:
        time.sleep(sobra)


def _ate(m: SimpleNamespace, pronto: Callable[[], bool], prazo_s: float = _GUARDA_S) -> None:
    """Tiques até `pronto`; o prazo é só a guarda contra o teste que nunca termina."""
    limite = time.monotonic() + prazo_s
    while not pronto():
        assert time.monotonic() < limite, "o pad não nasceu no prazo"
        _tique(m)


def _antes(ordem: list[str], primeiro: str, depois: str) -> bool:
    return (primeiro in ordem and depois in ordem
            and ordem.index(primeiro) < ordem.index(depois))


def _ninguem_esperou_o_p1(m: SimpleNamespace, marco: str, quem: str) -> None:
    """Ninguém esperou o broker no laço: ele respondeu porque o tique o soltou.

    `quem` é o suspeito antes de `marco`; a guarda que vence depois dele é do tique.
    """
    ordem = m.estado.ordem
    if _ESPEROU in ordem:
        if marco in ordem and ordem.index(marco) < ordem.index(_ESPEROU):
            quem = "o tique"
        pytest.fail(f"{quem} esperou o P1 no laço: esperou a entrega antes de o broker "
                    f"ser solto ({ordem})")
    if _PRAZO in ordem:
        if marco in ordem and ordem.index(marco) < ordem.index(_PRAZO):
            quem = "o tique"
        pytest.fail(f"{quem} esperou o P1 no laço: o broker respondeu pela guarda, "
                    f"sem que o tique o soltasse ({ordem})")


def _o_white_jogou_com_o_p1_em_voo(m: SimpleNamespace) -> None:
    ordem = m.estado.ordem
    assert _antes(ordem, _PEDIDO, _SOLTO), f"o broker não foi solto ({ordem})"
    jogadas = ordem[ordem.index(_PEDIDO):ordem.index(_SOLTO)].count(_TIQUE_DO_WHITE)
    assert jogadas >= _TIQUES_DO_WHITE, f"o White parou enquanto o P1 nascia ({ordem})"


def _o_p1_vivo(m: SimpleNamespace, velho: Any = None) -> Any:
    """O pad do P1 que o broker de mentira entregou, já instalado no daemon."""
    novo = m.estado.pads.get("None")
    atual = m.daemon._gamepad_device
    return atual if atual is not None and atual is novo and atual is not velho else None


def _o_gesto_volta_na_hora_e_o_p1_nasce_pelo_fio(
    m: SimpleNamespace, gesto: Callable[[], Any], *, velho: Any = None,
) -> Any:
    """O caminho volta antes de o broker ser solto, o White joga enquanto o pedido está em
    voo, e o P1 nasce quando o broker responde. Devolve o que o gesto devolveu."""
    devolvido = gesto()
    m.estado.ordem.append(_GESTO_VOLTOU)
    _ate(m, lambda: _o_p1_vivo(m, velho) is not None)
    assert len(m.estado.pedidos) == 1, m.estado.pedidos
    assert m.estado.pedidos[0] == "hefesto-nascimento-do-pad", "o P1 não nasceu no fio"
    _ninguem_esperou_o_p1(m, _GESTO_VOLTOU, "o gesto")
    assert _antes(m.estado.ordem, _GESTO_VOLTOU, _SOLTO), (
        f"o P1 nasceu no laço do tique: o gesto voltou depois do broker ({m.estado.ordem})")
    _o_white_jogou_com_o_p1_em_voo(m)
    assert m.daemon.config.gamepad_emulation_enabled
    return devolvido


def test_o_segundo_controle_que_chega_liga_a_emulacao_pelo_fio(
    mesa: SimpleNamespace, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O passo `coop_gamepad`: dois controles na mão, a emulação desligada."""
    monkeypatch.setattr(mesa.daemon, "contar_controles_fisicos", lambda: 2)
    mesa.daemon._gamepad_device = None
    estado = _o_gesto_volta_na_hora_e_o_p1_nasce_pelo_fio(
        mesa, mesa.daemon.aplicar_gamepad_para_multiplos_controles)
    assert estado == "aplicado"


def test_o_passo_que_se_repete_enquanto_o_p1_nasce_nao_pede_outro(
    mesa: SimpleNamespace, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O relógio da identidade volta antes de o broker responder: o pedido em voo vale."""
    monkeypatch.setattr(mesa.daemon, "contar_controles_fisicos", lambda: 2)
    mesa.daemon._gamepad_device = None

    def _duas_vezes() -> None:
        mesa.daemon.aplicar_gamepad_para_multiplos_controles()
        _tique(mesa)
        mesa.daemon.aplicar_gamepad_para_multiplos_controles()

    _o_gesto_volta_na_hora_e_o_p1_nasce_pelo_fio(mesa, _duas_vezes)


def test_o_ps_r3_troca_a_ponte_pelo_fio_e_grava_o_modo_depois_do_pad(
    mesa: SimpleNamespace,
) -> None:
    velho = _Pad(None, "dualsense", vp.CAMINHO_DUALSENSE, ROUPA_PADRAO)
    mesa.daemon._gamepad_device = velho
    mesa.daemon.config.gamepad_emulation_enabled = True
    de_pe = _o_gesto_volta_na_hora_e_o_p1_nasce_pelo_fio(
        mesa, lambda: hotkey._aplicar_ponte(mesa.daemon, hotkey.PONTE_XBOX), velho=velho)
    assert de_pe is True
    assert velho.parado
    novo = _o_p1_vivo(mesa, velho)
    assert novo.caminho == vp.CAMINHO_XBOX, "o P1 nasceu sem o caminho pedido"
    assert mesa.gravados == [("gamepad", novo)], (
        "o modo se grava depois de o pad existir, uma vez", mesa.gravados)


def test_a_troca_de_roupa_recria_o_p1_pelo_fio(
    mesa: SimpleNamespace, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O broker esconde o físico, e a roupa pedida vale; os secundários são do co-op."""
    monkeypatch.setattr(gp, "_o_fisico_esta_exposto", lambda _d: False)
    monkeypatch.setattr(gp, "_o_broker_atende", lambda _d: True)
    monkeypatch.setattr(coop_mod.CoopManager, "vestir_a_roupa", lambda self: [])
    velho = _Pad(None, normalize_flavor("dualsense"), vp.CAMINHO_DUALSENSE, ROUPA_PADRAO)
    mesa.daemon._gamepad_device = velho
    mesa.daemon.config.gamepad_emulation_enabled = True
    vestem = _o_gesto_volta_na_hora_e_o_p1_nasce_pelo_fio(
        mesa, lambda: gp.vestir_a_roupa(mesa.daemon, ROUPA_COMUM), velho=velho)
    assert "p1" in vestem, "o P1 que nasce na roupa pedida conta como quem a veste"
    assert _o_p1_vivo(mesa, velho).product == ROUPA_COMUM


def test_a_saida_do_modo_nativo_devolve_o_p1_pelo_fio(mesa: SimpleNamespace) -> None:
    mesa.daemon._gamepad_device = None
    mesa.daemon._native_mode = True
    mesa.daemon._native_emu_stash = {"gamepad": [True, "dualsense"], "mouse": [False, None, None]}
    _o_gesto_volta_na_hora_e_o_p1_nasce_pelo_fio(
        mesa, lambda: mesa.daemon.set_native_mode(
            False, origin="manual", reapply=False, restore_stash=True))
    assert not mesa.daemon.is_native_mode()


def _no_laco(m: SimpleNamespace, pedido: Callable[[], Coroutine[Any, Any, Any]]) -> Any:
    """O pedido no mesmo laço do asyncio que roda o tique, como no daemon.

    A resposta entra na ordem como «respondeu».
    """

    async def _correr() -> Any:
        parar = asyncio.Event()

        async def _laco() -> None:
            while not parar.is_set():
                _tique_sem_dormir(m)
                await asyncio.sleep(_TIQUE_S)

        laco = asyncio.create_task(_laco())
        await asyncio.sleep(_TIQUE_S)
        try:
            return await pedido()
        finally:
            m.estado.ordem.append(_RESPONDEU)
            parar.set()
            await laco

    return asyncio.run(_correr())


def _respondeu_depois_do_pad(m: SimpleNamespace) -> None:
    """A IPC não segurou o laço e só respondeu depois de o broker ser solto."""
    _ninguem_esperou_o_p1(m, _RESPONDEU, "o laço (a IPC ou o tique)")
    assert _antes(m.estado.ordem, _SOLTO, _RESPONDEU), (
        f"a IPC respondeu antes de o pad existir ({m.estado.ordem})")
    _o_white_jogou_com_o_p1_em_voo(m)


def test_a_ipc_liga_pelo_fio_e_responde_depois_do_pad_existir(mesa: SimpleNamespace) -> None:
    mesa.daemon._gamepad_device = None
    resposta = _no_laco(mesa, lambda: _Ipc(mesa.daemon)._handle_gamepad_emulation_set(
        {"enabled": True, "caminho": "xbox", "origin": "manual"}))
    assert mesa.estado.pedidos == ["hefesto-nascimento-do-pad"], "o P1 não nasceu no fio"
    _respondeu_depois_do_pad(mesa)
    assert resposta["status"] == "ok" and resposta["enabled"] is True, resposta
    assert resposta["caminho"] == vp.CAMINHO_XBOX, resposta
    assert _o_p1_vivo(mesa) is not None


def test_a_ipc_diz_falhou_quando_o_pad_nao_nasce(mesa: SimpleNamespace) -> None:
    """O desfecho de verdade: o broker respondeu sem pad, e a IPC não diz «ok»."""
    mesa.daemon._gamepad_device = None
    mesa.estado.falhar = True
    resposta = _no_laco(mesa, lambda: _Ipc(mesa.daemon)._handle_gamepad_emulation_set(
        {"enabled": True, "origin": "manual"}))
    _respondeu_depois_do_pad(mesa)
    assert resposta["status"] == "failed" and resposta["enabled"] is False, resposta
    assert mesa.daemon._gamepad_device is None
    assert mesa.gravados == [], "o modo que não ficou de pé não se grava"


def test_fora_do_laco_a_borda_nasce_na_hora(mesa: SimpleNamespace) -> None:
    """Fora do fio do laço (a borda, um executor), o P1 nasce na hora, como antes."""
    mesa.daemon._gamepad_device = None
    feito: list[Any] = []
    fio = threading.Thread(target=lambda: feito.append(mesa.daemon.set_gamepad_emulation(
        True, origin="profile")))
    fio.start()
    limite = time.monotonic() + _GUARDA_S
    while _PEDIDO not in mesa.estado.ordem:
        assert time.monotonic() < limite, "a borda não pediu o pad"
        time.sleep(_TIQUE_S)
    assert not feito, "a borda voltou antes de o pad existir"
    _soltar(mesa)
    fio.join(timeout=_GUARDA_S)
    assert feito == [True]
    assert _PRAZO not in mesa.estado.ordem, mesa.estado.ordem
    assert mesa.estado.pedidos == [fio.name]
    assert mesa.daemon._gamepad_device is mesa.estado.pads["None"]


def test_a_calibracao_do_p1_vai_ao_aparelho_no_fio_de_nascimento(
    mesa: SimpleNamespace, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A ida e volta do ``HIDIOCGFEATURE`` dorme, e o White segue jogando com o P1 nascendo.

    MORDIDA: em ``start_gamepad_emulation_desfecho``, leia ``read_primary_calibration(daemon)``
    na hora, em vez de o entregar ao fio.
    """
    fios: list[str] = []

    def dorme() -> bytes:
        fios.append(threading.current_thread().name)
        time.sleep(0.2)
        return _CALIB

    monkeypatch.setattr(gp, "read_primary_calibration", _CALIBRACAO_DE_VERDADE)
    monkeypatch.setattr(mesa.daemon.controller, "read_calibration", dorme, raising=False)
    monkeypatch.setattr(mesa.daemon, "contar_controles_fisicos", lambda: 2)
    mesa.daemon._gamepad_device = None

    _o_gesto_volta_na_hora_e_o_p1_nasce_pelo_fio(
        mesa, mesa.daemon.aplicar_gamepad_para_multiplos_controles)

    assert fios == ["hefesto-nascimento-do-pad"], fios
