"""O-GATILHO-VIRA-CLIQUE-SEM-LIGAR-O-CURSOR-01 — a tabela de botões age com o jogo aberto.

Medido antes de curar (08/10/2026), no uinput de mentira que grava o que sai:

1. o cursor andava SEMPRE, qualquer que fosse a linha do analógico (`— Nada —`
   inclusive): o `dispatch` chamava `_emit_move` e `_emit_scroll` sem perguntar;
2. o L2 só clicava por ESPELHO do Cruz (e o R2 do Triângulo): pôr o L2 em «Botão
   direito» emitia `BTN_LEFT`, e a linha do L2 caía em «sem dono»;
3. o gatilho clicava a 27% do curso (limiar de 64/255) — com o dedo encostado;
4. com o gamepad virtual despachando, o laço pulava a emulação inteira: a tabela
   não agia com o jogo aberto, por mais que ela quisesse.

Os leitores aqui são os EVENTOS gravados pelo uinput de mentira e as capacidades
que o device declara — nunca a constante que a cura usa.
"""
from __future__ import annotations

import asyncio
import sys
import time
import types
from typing import Any
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.core import acoes_de_botao as acoes
from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.daemon.subsystems import mouse as sub_mouse
from hefesto_dualsense4unix.daemon.subsystems.mouse import TabelaNoJogo
from hefesto_dualsense4unix.integrations.uinput_mouse import UinputMouseDevice
from hefesto_dualsense4unix.testing import FakeController

CENTRO = dict(lx=128, ly=128, rx=128, ry=128)

# Curso do gatilho em 0-255. 80 = 31%, 100 = 39%: um de cada lado de 0,35.
ENCOSTADO = 80
APERTADO = 100


class _Ev:
    def __init__(self, nome: str) -> None:
        self.nome = nome


class _UinputGravador(types.ModuleType):
    """O módulo `uinput`: grava as capacidades e tudo o que o device emite."""

    def __init__(self) -> None:
        super().__init__("uinput")
        self.capacidades: list[str] = []
        self.saiu: list[tuple[str, int]] = []

    def __getattr__(self, nome: str) -> Any:
        if nome.startswith(("KEY_", "BTN_", "REL_")):
            return _Ev(nome)
        raise AttributeError(nome)

    def Device(self, caps: Any, name: str = "") -> Any:  # noqa: N802 - é o nome do uinput
        self.capacidades = [c.nome for c in caps]
        mod = self

        class _Dev:
            def emit(self, ev: Any, valor: int, syn: bool = True) -> None:
                mod.saiu.append((ev.nome, valor))

            def syn(self) -> None:
                pass

            def destroy(self) -> None:
                pass

        return _Dev()


@pytest.fixture
def uinput(monkeypatch: pytest.MonkeyPatch) -> _UinputGravador:
    mod = _UinputGravador()
    monkeypatch.setitem(sys.modules, "uinput", mod)
    return mod


def _mouse(uinput: _UinputGravador, escolhas: dict[str, str] | None) -> UinputMouseDevice:
    dev = UinputMouseDevice()
    assert dev.start()
    if escolhas is not None:
        do_mouse, _teclado, _sem = acoes.resolver(escolhas)
        dev.set_button_actions(do_mouse, acoes.botoes_calados(escolhas))
    return dev


def _dispatch(dev: UinputMouseDevice, *, buttons: frozenset[str] = frozenset(),
              l2: int = 0, r2: int = 0, now: float = 1.0, **eixos: int) -> None:
    dev.dispatch(**{**CENTRO, **eixos}, l2=l2, r2=r2, buttons=buttons, now=now)


def _nomes(uinput: _UinputGravador) -> list[str]:
    return [n for n, _v in uinput.saiu]


# -- o analógico: a linha dele liga o cursor e a rolagem ---------------------------


def test_o_de_fabrica_move_o_cursor_e_rola(uinput: _UinputGravador) -> None:
    dev = _mouse(uinput, None)
    _dispatch(dev, lx=255, ly=255, rx=128, ry=255, now=1.0)
    assert "REL_X" in _nomes(uinput), "o de fábrica tem de mover o cursor"
    assert "REL_WHEEL" in _nomes(uinput), "o de fábrica tem de rolar"


@pytest.mark.parametrize("token", [acoes.TOKEN_NADA, "BTN_LEFT", "KEY_E"])
def test_a_linha_do_analogico_diferente_do_cursor_nao_move_o_cursor(
    uinput: _UinputGravador, token: str
) -> None:
    """MORDIDA: voltar o `_emit_move` incondicional reprova os três casos."""
    dev = _mouse(uinput, {acoes.EIXO_ESQUERDO: token})
    _dispatch(dev, lx=255, ly=255, rx=128, ry=128)
    assert not [n for n in _nomes(uinput) if n in ("REL_X", "REL_Y")], (
        f"o analógico esquerdo em {token!r} moveu o cursor")


def test_a_rolagem_so_anda_com_a_linha_dela(uinput: _UinputGravador) -> None:
    """MORDIDA: voltar o `_emit_scroll` incondicional reprova."""
    dev = _mouse(uinput, {acoes.EIXO_DIREITO: acoes.TOKEN_NADA})
    _dispatch(dev, rx=128, ry=255)
    assert "REL_WHEEL" not in _nomes(uinput), "o analógico direito em Nada rolou"
    dev2 = _mouse(uinput, {acoes.EIXO_ESQUERDO: acoes.TOKEN_NADA})
    _dispatch(dev2, rx=128, ry=255, now=5.0)
    assert "REL_WHEEL" in _nomes(uinput), "calar o esquerdo não pode calar a rolagem"


def test_o_device_continua_declarando_cursor_e_roda(uinput: _UinputGravador) -> None:
    """Sem REL_X/REL_Y o udev não classifica o nó como mouse e o clique não chega.

    MORDIDA: tirar REL_X/REL_Y/REL_WHEEL de `_build_capabilities` reprova.
    """
    _mouse(uinput, {acoes.EIXO_ESQUERDO: acoes.TOKEN_NADA})
    for cap in ("REL_X", "REL_Y", "REL_WHEEL", "BTN_LEFT", "BTN_RIGHT"):
        assert cap in uinput.capacidades, f"o device deixou de declarar {cap}"


# -- o gatilho: linha própria, com o limiar da ponte -------------------------------


def test_o_gatilho_segue_a_propria_linha_e_nao_a_do_cruz(uinput: _UinputGravador) -> None:
    """L2 em «Botão direito»: sai BTN_RIGHT. MORDIDA: religar o espelho l2 -> cross."""
    dev = _mouse(uinput, {"l2": "BTN_RIGHT"})
    _dispatch(dev, l2=255)
    assert ("BTN_RIGHT", 1) in uinput.saiu
    assert "BTN_LEFT" not in _nomes(uinput), "o L2 clicou pela linha do Cruz"


def test_o_gatilho_sem_escolha_clica_como_antes(uinput: _UinputGravador) -> None:
    dev = _mouse(uinput, None)
    _dispatch(dev, l2=255, r2=255)
    assert ("BTN_LEFT", 1) in uinput.saiu and ("BTN_RIGHT", 1) in uinput.saiu


def test_o_gatilho_so_clica_a_partir_de_035_do_curso(uinput: _UinputGravador) -> None:
    """MORDIDA: devolver o limiar de 64 faz o encostado (80) clicar."""
    dev = _mouse(uinput, None)
    _dispatch(dev, l2=ENCOSTADO)
    assert "BTN_LEFT" not in _nomes(uinput), "o dedo encostado clicou"
    _dispatch(dev, l2=APERTADO, now=2.0)
    assert ("BTN_LEFT", 1) in uinput.saiu, "o gatilho apertado não clicou"
    _dispatch(dev, l2=0, now=3.0)
    assert ("BTN_LEFT", 0) in uinput.saiu, "o clique não soltou com o gatilho"


def test_dois_botoes_no_mesmo_clique_soltam_so_quando_o_ultimo_solta(
    uinput: _UinputGravador,
) -> None:
    """A Cruz e o L2 dão o mesmo clique: a borda é por CÓDIGO, não por botão."""
    dev = _mouse(uinput, None)
    _dispatch(dev, buttons=frozenset({"cross"}), l2=APERTADO, now=1.0)
    assert uinput.saiu.count(("BTN_LEFT", 1)) == 1, "o mesmo clique saiu duas vezes"
    _dispatch(dev, buttons=frozenset(), l2=APERTADO, now=2.0)
    assert ("BTN_LEFT", 0) not in uinput.saiu, "soltou com o L2 ainda apertado"
    _dispatch(dev, buttons=frozenset(), l2=0, now=3.0)
    assert ("BTN_LEFT", 0) in uinput.saiu


def test_trocar_a_tabela_solta_o_que_a_anterior_segurava(uinput: _UinputGravador) -> None:
    dev = _mouse(uinput, None)
    _dispatch(dev, l2=255)
    assert ("BTN_LEFT", 1) in uinput.saiu
    do_mouse, _t, _s = acoes.resolver({"l2": acoes.TOKEN_NADA})
    dev.set_button_actions(do_mouse, acoes.botoes_calados({"l2": acoes.TOKEN_NADA}))
    assert ("BTN_LEFT", 0) in uinput.saiu, "o clique do L2 ficou preso na troca da tabela"


# -- a tecla E no R2 (a ação ganha TECLAS) -----------------------------------------


def test_a_ação_e_do_teclado_vai_para_o_teclado_e_nao_para_o_mouse() -> None:
    do_mouse, do_teclado, sem_dono = acoes.resolver({"r2": "KEY_E"})
    assert do_teclado["r2"] == ("KEY_E",)
    assert "r2" not in do_mouse and "r2" not in sem_dono


def test_a_tecla_e_abre_a_lista_do_teclado() -> None:
    teclado = [t for t, (grupo, _r) in acoes.ACOES.items() if grupo == acoes.GRUPO_TECLADO]
    assert teclado[0] == "KEY_E", "a «E» é a primeira entrada de «Função do teclado»"
    assert acoes.rotulo("KEY_E") == "E"


def test_os_dois_gatilhos_sao_linhas_com_dono_no_de_fabrica() -> None:
    do_mouse, _t, sem_dono = acoes.resolver(None)
    assert do_mouse["l2"] == "BTN_LEFT" and do_mouse["r2"] == "BTN_RIGHT"
    assert "l2" not in sem_dono and "r2" not in sem_dono


# -- o laço: com o gamepad virtual despachando, a tabela age -----------------------


class _Gravador:
    """Um mouse/teclado privado de mentira que grava cada tique."""

    def __init__(self) -> None:
        self.chamadas: list[Any] = []

    def dispatch(self, *args: Any, **kw: Any) -> None:
        self.chamadas.append(kw if kw else args[0])

    def stop(self) -> None:
        pass


def _tabela_com_gravadores(button_actions: dict[str, str] | None,
                           ) -> tuple[TabelaNoJogo, _Gravador, _Gravador]:
    tabela = TabelaNoJogo(button_actions, None, ligada=True)
    mouse, teclado = _Gravador(), _Gravador()
    tabela._mouse, tabela._teclado = mouse, teclado
    return tabela, mouse, teclado


def _estado(**campos: int) -> ControllerState:
    base = dict(battery_pct=80, connected=True, transport="usb", l2_raw=0, r2_raw=0)
    return ControllerState(**{**base, **campos})  # type: ignore[arg-type]


def _daemon_de_mentira(outros: dict[str, tuple[frozenset[str], int, int]] | None = None,
                       ) -> Any:
    d = types.SimpleNamespace(
        config=types.SimpleNamespace(mouse_speed=6, mouse_scroll_speed=1, poll_hz=60),
        controller=None,
        _tabela_no_jogo=None, _teclado_so_no_jogo=False, _estava_no_jogo=False,
        _keyboard_device=None,
    )
    d._dispatch_keyboard_emulation = lambda botoes: None
    return d


def test_o_gatilho_do_p1_chega_ao_teclado_pelo_nome(monkeypatch: pytest.MonkeyPatch) -> None:
    """R2 em «E»: a tecla recebe `r2` no conjunto, e o mouse não clica por ele."""
    tabela, mouse, teclado = _tabela_com_gravadores({"r2": "KEY_E"})
    daemon = _daemon_de_mentira()
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.subsystems.poll.gatilhos_de_cada_controle",
        lambda d: {})
    tabela.tick(daemon, _estado(r2_raw=255), frozenset())
    assert "r2" in teclado.chamadas[-1]
    assert "r2" in mouse.chamadas[-1]["buttons"]


def test_cada_controle_aperta_as_proprias_linhas(monkeypatch: pytest.MonkeyPatch) -> None:
    """O P2 aperta o R2 (curso 255) e o P1 nada: a linha do R2 age."""
    tabela, _mouse, teclado = _tabela_com_gravadores({"r2": "KEY_E", "cross": "KEY_ENTER"})
    daemon = _daemon_de_mentira()
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.subsystems.poll.gatilhos_de_cada_controle",
        lambda d: {"aa:bb:cc:00:00:02": (frozenset({"cross"}), 0, 255)})
    tabela.tick(daemon, _estado(), frozenset())
    assert {"r2", "cross"} <= set(teclado.chamadas[-1])


def test_o_cursor_e_a_rolagem_so_andam_pelo_p1(monkeypatch: pytest.MonkeyPatch) -> None:
    """Os eixos do P2 nunca chegam ao mouse: o `dispatch` recebe os do P1."""
    tabela, mouse, _teclado = _tabela_com_gravadores(None)
    daemon = _daemon_de_mentira()
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.subsystems.poll.gatilhos_de_cada_controle",
        lambda d: {"aa:bb:cc:00:00:02": (frozenset(), 0, 0)})
    tabela.tick(daemon, _estado(raw_lx=10, raw_ly=20, raw_rx=30, raw_ry=40), frozenset())
    kw = mouse.chamadas[-1]
    assert (kw["lx"], kw["ly"], kw["rx"], kw["ry"]) == (10, 20, 30, 40)


def test_sair_do_jogo_solta_o_que_a_tabela_segurava() -> None:
    tabela, mouse, teclado = _tabela_com_gravadores(None)
    daemon = _daemon_de_mentira()
    daemon._tabela_no_jogo = tabela
    sub_mouse.despachar_no_jogo(daemon, _estado(), frozenset({"cross"}), no_jogo=True)
    antes = len(mouse.chamadas)
    sub_mouse.despachar_no_jogo(daemon, _estado(), frozenset(), no_jogo=False)
    assert len(mouse.chamadas) == antes + 1
    ultimo = mouse.chamadas[-1]
    assert ultimo["buttons"] == frozenset() and ultimo["l2"] == 0
    assert teclado.chamadas[-1] == frozenset()


def test_sem_a_chave_a_tabela_nao_nasce() -> None:
    daemon = _daemon_de_mentira()
    sub_mouse.trocar_a_tabela_no_jogo(daemon, types.SimpleNamespace(
        tabela_no_jogo=None, button_actions=None, key_bindings=None))
    assert daemon._tabela_no_jogo is None
    sub_mouse.trocar_a_tabela_no_jogo(daemon, types.SimpleNamespace(
        tabela_no_jogo=True, button_actions=None, key_bindings=None))
    assert isinstance(daemon._tabela_no_jogo, TabelaNoJogo)
    sub_mouse.trocar_a_tabela_no_jogo(daemon, types.SimpleNamespace(
        tabela_no_jogo=False, button_actions=None, key_bindings=None))
    assert daemon._tabela_no_jogo is None


@pytest.mark.asyncio
async def test_o_laco_real_chama_a_tabela_com_o_vpad_despachando(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O laço de produção: com `gamepad_dispatched`, o L2 apertado chega à tabela.

    MORDIDA: devolver o `if not gamepad_dispatched` cego (tirar a chamada de
    `despachar_no_jogo` do laço) deixa o gravador vazio e este teste reprova.
    """
    monkeypatch.setattr("hefesto_dualsense4unix.daemon.lifecycle.INPUT_GRACE_SEC", 0.0)

    class _Snap:
        buttons_pressed = ["cross"]  # noqa: RUF012

    fc = FakeController(transport="usb", states=[
        _estado(l2_raw=255, r2_raw=0) for _ in range(40)])
    mock_evdev = MagicMock()
    mock_evdev.is_available.return_value = True
    mock_evdev.snapshot.return_value = _Snap()
    fc._evdev = mock_evdev
    daemon = Daemon(
        controller=fc,
        config=DaemonConfig(
            poll_hz=200, auto_reconnect=False, ipc_enabled=False, udp_enabled=False,
            autoswitch_enabled=False, mouse_emulation_enabled=False,
            keyboard_emulation_enabled=False,
        ),
    )
    daemon._gamepad_device = MagicMock()
    daemon._dispatch_gamepad_emulation = lambda estado, botoes: None  # type: ignore[method-assign]
    tabela, mouse, _teclado = _tabela_com_gravadores(None)
    daemon._tabela_no_jogo = tabela
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.subsystems.poll.gatilhos_de_cada_controle",
        lambda d: {})

    run_task = asyncio.create_task(daemon.run())
    prazo = time.monotonic() + 5.0
    while len(mouse.chamadas) < 3 and time.monotonic() < prazo:
        await asyncio.sleep(0.005)
    daemon.stop()
    await run_task

    assert len(mouse.chamadas) >= 3, "o laço não chamou a tabela com o vpad despachando"
    vistos = [c["buttons"] for c in mouse.chamadas if isinstance(c, dict)]
    assert any("l2" in b for b in vistos), "o L2 apertado não chegou à tabela"


# -- os dois devices privados, de verdade, sobre o uinput de mentira ---------------


class _UinputPorDevice(types.ModuleType):
    """O `uinput` com um gravador POR device (o mouse e o teclado da tabela)."""

    def __init__(self) -> None:
        super().__init__("uinput")
        self.saiu: dict[str, list[tuple[str, int]]] = {}

    def __getattr__(self, nome: str) -> Any:
        if nome.startswith(("KEY_", "BTN_", "REL_")):
            return _Ev(nome)
        raise AttributeError(nome)

    def Device(self, caps: Any, name: str = "") -> Any:  # noqa: N802 - é o nome do uinput
        gravado = self.saiu.setdefault(name, [])

        class _Dev:
            def emit(self, ev: Any, valor: int, syn: bool = True) -> None:
                gravado.append((ev.nome, valor))

            def syn(self) -> None:
                pass

            def destroy(self) -> None:
                pass

        return _Dev()


class _OskDeMentira:
    def __init__(self) -> None:
        self.toques: list[tuple[str, str]] = []

    def dispatch_token(self, token: str, fase: str) -> None:
        self.toques.append((token, fase))


@pytest.fixture
def dois_devices(monkeypatch: pytest.MonkeyPatch) -> _UinputPorDevice:
    mod = _UinputPorDevice()
    monkeypatch.setitem(sys.modules, "uinput", mod)
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.subsystems.poll.gatilhos_de_cada_controle",
        lambda d: {})
    return mod


def _saidas(mod: _UinputPorDevice) -> tuple[list[tuple[str, int]], list[tuple[str, int]]]:
    from hefesto_dualsense4unix.integrations.uinput_keyboard import DEVICE_NAME as TECLADO
    from hefesto_dualsense4unix.integrations.uinput_mouse import DEVICE_NAME as MOUSE

    return mod.saiu.get(MOUSE, []), mod.saiu.get(TECLADO, [])


def test_o_r2_na_e_sai_pelo_teclado_da_tabela_e_nao_clica(
    dois_devices: _UinputPorDevice,
) -> None:
    """O GON: R2 em «E». A tabela ABRE os dois devices e os liga pela tabela.

    O leitor é o evento de cada device, e não o gravador que troca os devices:
    esta régua passa pelo `_abrir`, que é onde a tecla e o clique se repartem.
    MORDIDA: entregar ao mouse da tabela só os `calados` (sem as linhas do
    teclado) faz o direcional sair duas vezes, e esta régua reprova.
    """
    daemon = _daemon_de_mentira()
    daemon._osk_controller = _OskDeMentira()
    tabela = TabelaNoJogo({"r2": "KEY_E", "l3_direcao": acoes.TOKEN_NADA}, None, ligada=True)
    tabela.tick(daemon, _estado(r2_raw=255, raw_lx=255, raw_ly=255), frozenset({"dpad_up"}))
    mouse, teclado = _saidas(dois_devices)
    assert ("KEY_E", 1) in teclado, f"o R2 não digitou E: {teclado}"
    assert ("KEY_UP", 1) in teclado, "o direcional não saiu pelo teclado"
    assert "BTN_RIGHT" not in [n for n, _v in mouse], "o R2 em «E» também clicou"
    assert "KEY_UP" not in [n for n, _v in mouse], "o direcional saiu duas vezes"
    assert not [n for n, _v in mouse if n in ("REL_X", "REL_Y")], (
        "o analógico em «— Nada —» moveu o cursor com o jogo aberto")


def test_o_l3_de_fabrica_abre_o_teclado_na_tela_tambem_no_jogo(
    dois_devices: _UinputPorDevice,
) -> None:
    """A linha do L3 (teclado na tela) tem o mesmo atendente do desktop.

    MORDIDA: tirar o `virtual_token_callback` do teclado da tabela deixa o
    toque sem ninguém (`keyboard_virtual_token_sem_callback`) e esta régua reprova.
    """
    daemon = _daemon_de_mentira()
    osk = _OskDeMentira()
    daemon._osk_controller = osk
    tabela = TabelaNoJogo(None, None, ligada=True)
    tabela.tick(daemon, _estado(), frozenset({"l3"}))
    assert ("__TOGGLE_OSK__", "press") in osk.toques, osk.toques


@pytest.mark.parametrize("de_quem", ["gesto", "perfil"])
def test_suspender_mouse_e_teclado_cala_a_tabela_no_jogo(de_quem: str) -> None:
    """«Suspender mouse e teclado» (o PS + Options) vale com o jogo aberto.

    A supressão que ELA ligou cala a tabela; a do perfil do jogo não, porque o
    jogo aberto é justamente onde a chave age. MORDIDA: tirar o
    `_suspenso_por_ela` de `despachar_no_jogo` faz o caso «gesto» reprovar.
    """
    tabela, mouse, _teclado = _tabela_com_gravadores(None)
    daemon = _daemon_de_mentira()
    daemon._tabela_no_jogo = tabela
    daemon._emulation_suppressed = True
    daemon._suppress_from_profile = de_quem == "perfil"
    sub_mouse.despachar_no_jogo(daemon, _estado(), frozenset({"cross"}), no_jogo=True)
    apertou = [c for c in mouse.chamadas if isinstance(c, dict) and c["buttons"]]
    if de_quem == "gesto":
        assert not apertou, "a tabela clicou com o mouse e o teclado suspensos por ela"
    else:
        assert apertou, "a supressão do perfil do jogo calou a chave «Também no jogo»"


def test_suspender_cala_o_teclado_so_dentro_do_jogo() -> None:
    """O mesmo para o teclado «Só dentro do jogo»: suspenso por ela, não digita."""
    daemon = _daemon_de_mentira()
    daemon._teclado_so_no_jogo = True
    daemon._keyboard_device = _Gravador()
    digitou: list[frozenset[str]] = []
    daemon._dispatch_keyboard_emulation = digitou.append
    daemon._emulation_suppressed = True
    daemon._suppress_from_profile = False
    sub_mouse.despachar_no_jogo(daemon, _estado(), frozenset({"cross"}), no_jogo=True)
    assert not digitou, "«Só dentro do jogo» digitou com o teclado suspenso por ela"


@pytest.mark.asyncio
@pytest.mark.parametrize("transporte", ["usb", "bt"])
async def test_o_laco_solta_a_tabela_na_parada(
    monkeypatch: pytest.MonkeyPatch, transporte: str,
) -> None:
    """Pelo cabo e pelo rádio: o laço entrega o L2 à tabela, e a parada a fecha.

    MORDIDA: tirar o `fechar()` do `finally` do `Daemon.run` deixa a tabela de pé.
    """
    monkeypatch.setattr("hefesto_dualsense4unix.daemon.lifecycle.INPUT_GRACE_SEC", 0.0)

    class _Snap:
        buttons_pressed: list[str] = []  # noqa: RUF012

    fc = FakeController(transport=transporte, states=[
        _estado(l2_raw=255, transport=transporte) for _ in range(40)])  # type: ignore[arg-type]
    mock_evdev = MagicMock()
    mock_evdev.is_available.return_value = True
    mock_evdev.snapshot.return_value = _Snap()
    fc._evdev = mock_evdev
    daemon = Daemon(
        controller=fc,
        config=DaemonConfig(
            poll_hz=200, auto_reconnect=False, ipc_enabled=False, udp_enabled=False,
            autoswitch_enabled=False, mouse_emulation_enabled=False,
            keyboard_emulation_enabled=False,
        ),
    )
    daemon._gamepad_device = MagicMock()
    daemon._dispatch_gamepad_emulation = lambda estado, botoes: None  # type: ignore[method-assign]
    tabela, mouse, _teclado = _tabela_com_gravadores(None)
    fechou: list[bool] = []
    tabela.fechar = lambda: fechou.append(True)  # type: ignore[method-assign]
    daemon._tabela_no_jogo = tabela
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.subsystems.poll.gatilhos_de_cada_controle",
        lambda d: {})

    run_task = asyncio.create_task(daemon.run())
    prazo = time.monotonic() + 5.0
    while len(mouse.chamadas) < 3 and time.monotonic() < prazo:
        await asyncio.sleep(0.005)
    daemon.stop()
    await run_task

    assert any("l2" in c["buttons"] for c in mouse.chamadas if isinstance(c, dict)), (
        f"o L2 do {transporte} não chegou à tabela")
    assert fechou and daemon._tabela_no_jogo is None, "a parada deixou a tabela de pé"


@pytest.mark.asyncio
async def test_no_nativo_a_tabela_nao_age(monkeypatch: pytest.MonkeyPatch) -> None:
    """No Modo Nativo o jogo lê o controle direto: a chave ligada não aperta nada.

    A tela apaga a chave no Nativo; o laço tem de concordar com ela.
    MORDIDA: tirar o `not self._native_mode` do `input_ready` faz o L2 chegar à tabela.
    """
    monkeypatch.setattr("hefesto_dualsense4unix.daemon.lifecycle.INPUT_GRACE_SEC", 0.0)

    class _Snap:
        buttons_pressed: list[str] = []  # noqa: RUF012

    fc = FakeController(transport="usb", states=[
        _estado(l2_raw=255, transport="usb") for _ in range(40)])  # type: ignore[arg-type]
    mock_evdev = MagicMock()
    mock_evdev.is_available.return_value = True
    mock_evdev.snapshot.return_value = _Snap()
    fc._evdev = mock_evdev
    daemon = Daemon(
        controller=fc,
        config=DaemonConfig(
            poll_hz=200, auto_reconnect=False, ipc_enabled=False, udp_enabled=False,
            autoswitch_enabled=False, mouse_emulation_enabled=False,
            keyboard_emulation_enabled=False,
        ),
    )
    daemon._gamepad_device = MagicMock()
    daemon._dispatch_gamepad_emulation = lambda estado, botoes: None  # type: ignore[method-assign]
    daemon._native_mode = True
    # A sessão do teste não guarda Nativo: o `run` o leria de volta como desligado.
    daemon._carregar_o_modo_nativo = lambda: None  # type: ignore[method-assign]
    tabela, mouse, _teclado = _tabela_com_gravadores(None)
    daemon._tabela_no_jogo = tabela
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.subsystems.poll.gatilhos_de_cada_controle",
        lambda d: {})

    run_task = asyncio.create_task(daemon.run())
    prazo = time.monotonic() + 5.0
    while daemon.store.counter("input.settling.tick") < 5 and time.monotonic() < prazo:
        await asyncio.sleep(0.005)
    daemon.stop()
    await run_task

    assert daemon.store.counter("input.settling.tick") >= 5, "o laço não girou no Nativo"
    assert not any("l2" in c["buttons"] for c in mouse.chamadas if isinstance(c, dict)), (
        "no Nativo o L2 chegou à tabela")
