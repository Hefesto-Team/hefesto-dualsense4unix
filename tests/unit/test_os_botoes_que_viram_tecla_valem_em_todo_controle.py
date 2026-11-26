"""OS-BOTOES-QUE-VIRAM-TECLA-VALEM-EM-TODO-CONTROLE-01: a tecla de qualquer controle chega ao PC.

Antes, o laço entregava ao teclado do computador só o `buttons_pressed` do primário: o botão
ligado a uma tecla, apertado no P2, P3 ou P4, não saía. Agora o teclado recebe a união dos botões
de cada controle (as leituras de `poll.gatilhos_de_cada_controle`, as mesmas da tabela do jogo e
dos atalhos), e o cursor segue o primário. A contagem de quem segura cada tecla segue o nome do
botão: soltar um não solta a tecla que outro ainda segura.

Decisão: D-2511-A-TECLA-DE-TODO-CONTROLE-CHEGA-AO-COMPUTADOR, que estende
D-1710-OS-ANALOGICOS-OFERECEM-TECLAS-SO-NA-LINHA-DELES (as teclas valem para todos os controles).

O instrumento é o laço de produção com o teclado virtual de produção sobre o `uinput` de mentira
que grava cada evento. Os quatro controles vêm das três fontes reais: o P1 do leitor do primário,
o P2 do co-op (cabo) e o P3 e o P4 do leitor passivo do hub (rádio).

MORDIDAS: devolver ao laço o `emu_buttons` só do primário (`no_teclado`), tirar a união do
`despachar_no_jogo`, tirar o filtro do gesto do PS por controle e devolver ao `dispatch_mouse` só
os botões do primário (as setas, o Enter e o Esc que o mouse virtual digita) reprovam.
"""
from __future__ import annotations

import asyncio
import sys
import time
import types
from typing import Any
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.daemon.subsystems import mouse as sub_mouse
from hefesto_dualsense4unix.integrations.uinput_keyboard import UinputKeyboardDevice
from hefesto_dualsense4unix.testing import FakeController

P1 = "aa:bb:cc:00:00:01"
P2 = "aa:bb:cc:00:00:02"
P3 = "aa:bb:cc:00:00:03"
P4 = "aa:bb:cc:00:00:04"


class _Ev:
    def __init__(self, nome: str) -> None:
        self.nome = nome


class _Uinput(types.ModuleType):
    def __init__(self) -> None:
        super().__init__("uinput")
        self.saiu: list[tuple[str, int]] = []

    def __getattr__(self, nome: str) -> Any:
        if nome.startswith(("KEY_", "BTN_", "REL_")):
            return _Ev(nome)
        raise AttributeError(nome)

    def Device(self, caps: Any, name: str = "") -> Any:  # noqa: N802
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
def uinput(monkeypatch: pytest.MonkeyPatch) -> _Uinput:
    mod = _Uinput()
    monkeypatch.setitem(sys.modules, "uinput", mod)
    return mod


def _estado() -> ControllerState:
    return ControllerState(  # type: ignore[call-arg]
        battery_pct=80, connected=True, transport="usb", l2_raw=0, r2_raw=0)


LIGACOES = {
    "cross": ("KEY_A",), "triangle": ("KEY_A",),
    "square": ("KEY_B",), "circle": ("KEY_C",), "r1": ("KEY_D",),
}


class _Mesa:
    """Os quatro controles e o que cada um aperta; o laço lê pelas três fontes reais."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, uinput: _Uinput) -> None:
        self.aperta: dict[str, set[str]] = {P1: set(), P2: set(), P3: set(), P4: set()}
        self.tiques = 0
        self.uinput = uinput
        monkeypatch.setattr("hefesto_dualsense4unix.daemon.lifecycle.INPUT_GRACE_SEC", 0.0)
        mesa = self

        class _Snap:
            @property
            def buttons_pressed(self) -> list[str]:
                mesa.tiques += 1
                return sorted(mesa.aperta[P1])

        fc = FakeController(transport="usb", states=[_estado() for _ in range(4000)])
        evdev = MagicMock()
        evdev.is_available.return_value = True
        evdev.snapshot.side_effect = lambda: _Snap()
        fc._evdev = evdev
        fc.primary_uniq = P1  # type: ignore[attr-defined]
        fc.alvos_conectados = lambda: {  # type: ignore[attr-defined]
            "/dev/a": P1, "/dev/b": P2, "/dev/c": P3, "/dev/d": P4}
        self.daemon = Daemon(
            controller=fc,
            config=DaemonConfig(
                poll_hz=200, ipc_enabled=False, udp_enabled=False,
                autoswitch_enabled=False, mouse_emulation_enabled=False,
                keyboard_emulation_enabled=False,
            ),
        )
        self.teclado = UinputKeyboardDevice(bindings=dict(LIGACOES))
        assert self.teclado.start()
        self.daemon._keyboard_device = self.teclado
        monkeypatch.setattr(
            "hefesto_dualsense4unix.daemon.subsystems.poll._snapshots_do_coop",
            lambda d: {P2: types.SimpleNamespace(
                buttons_pressed=sorted(mesa.aperta[P2]),
                lx=128, ly=128, rx=128, ry=128, l2_raw=0, r2_raw=0)})
        monkeypatch.setattr(
            "hefesto_dualsense4unix.daemon.subsystems.poll._sentados_no_coop",
            lambda d: frozenset())
        monkeypatch.setattr(
            "hefesto_dualsense4unix.daemon.subsystems.poll._entradas_do_hub",
            lambda d: lambda uniq: {
                "buttons": sorted(mesa.aperta[uniq]),
                "lx": 128, "ly": 128, "rx": 128, "ry": 128, "l2_raw": 0, "r2_raw": 0})
        self._tarefa: asyncio.Task[Any] | None = None

    async def __aenter__(self) -> _Mesa:
        self._tarefa = asyncio.create_task(self.daemon.run())
        await self.passam_tiques(3)
        self.teclado.set_bindings(dict(LIGACOES))
        self.uinput.saiu.clear()
        return self

    async def __aexit__(self, *_: object) -> None:
        self.daemon.stop()
        assert self._tarefa is not None
        await self._tarefa

    async def passam_tiques(self, n: int = 12) -> None:
        """Espera o laço ler `n` vezes o primário (um tique cada), no máximo cinco segundos."""
        alvo = self.tiques + n
        prazo = time.monotonic() + 5.0
        while self.tiques < alvo and time.monotonic() < prazo:
            await asyncio.sleep(0.005)
        assert self.tiques >= alvo, "o laço não andou"

    def teclas(self) -> list[tuple[str, int]]:
        return list(self.uinput.saiu)


@pytest.mark.asyncio
@pytest.mark.parametrize("quem, botao, tecla", [
    (P2, "square", "KEY_B"), (P3, "cross", "KEY_A"), (P4, "circle", "KEY_C"),
])
async def test_o_botao_de_tecla_de_cada_controle_chega_ao_pc(
    monkeypatch: pytest.MonkeyPatch, uinput: _Uinput, quem: str, botao: str, tecla: str,
) -> None:
    """O P2 (cabo, co-op) e o P3 e o P4 (rádio, hub) apertam: a tecla sai e solta.

    MORDIDA: devolver ao laço só o `emu_buttons` do primário.
    """
    async with _Mesa(monkeypatch, uinput) as mesa:
        mesa.aperta[quem] = {botao}
        await mesa.passam_tiques()
        assert (tecla, 1) in mesa.teclas(), f"a tecla do {quem} não saiu: {mesa.teclas()}"
        mesa.aperta[quem] = set()
        await mesa.passam_tiques()
        assert mesa.teclas()[-1] == (tecla, 0)


@pytest.mark.asyncio
async def test_soltar_um_controle_nao_solta_a_tecla_que_outro_segura(
    monkeypatch: pytest.MonkeyPatch, uinput: _Uinput,
) -> None:
    """O P1 (Triângulo) e o P3 (Cruz) seguram a MESMA tecla; soltar um não a solta.

    MORDIDA: contar a tecla uma vez só (a segunda pressão vira key up cedo) reprova.
    """
    async with _Mesa(monkeypatch, uinput) as mesa:
        mesa.aperta[P1] = {"triangle"}
        await mesa.passam_tiques()
        mesa.aperta[P3] = {"cross"}
        await mesa.passam_tiques()
        mesa.aperta[P1] = set()
        await mesa.passam_tiques()
        assert mesa.teclas().count(("KEY_A", 1)) == 1
        assert ("KEY_A", 0) not in mesa.teclas(), "soltar o P1 soltou a tecla que o P3 segura"
        mesa.aperta[P3] = set()
        await mesa.passam_tiques()
        assert mesa.teclas().count(("KEY_A", 0)) == 1


@pytest.mark.asyncio
async def test_o_mesmo_botao_em_dois_controles_solta_so_com_o_ultimo(
    monkeypatch: pytest.MonkeyPatch, uinput: _Uinput,
) -> None:
    """O Cruz do P1 e o Cruz do P4 juntos: a tecla sai uma vez e solta quando o último solta."""
    async with _Mesa(monkeypatch, uinput) as mesa:
        mesa.aperta[P1] = {"cross"}
        mesa.aperta[P4] = {"cross"}
        await mesa.passam_tiques()
        mesa.aperta[P1] = set()
        await mesa.passam_tiques()
        assert mesa.teclas() == [("KEY_A", 1)]
        mesa.aperta[P4] = set()
        await mesa.passam_tiques()
        assert mesa.teclas() == [("KEY_A", 1), ("KEY_A", 0)]


@pytest.mark.asyncio
async def test_o_primario_segue_digitando_como_antes(
    monkeypatch: pytest.MonkeyPatch, uinput: _Uinput,
) -> None:
    async with _Mesa(monkeypatch, uinput) as mesa:
        mesa.aperta[P1] = {"r1"}
        await mesa.passam_tiques()
        assert mesa.teclas() == [("KEY_D", 1)]


@pytest.mark.asyncio
async def test_o_botao_do_outro_controle_apertado_na_carencia_nao_digita_ao_terminar_a_espera(
    monkeypatch: pytest.MonkeyPatch, uinput: _Uinput,
) -> None:
    """O botão que o P3 já segurava quando o controle ligou é semeado (prime), não apertado.

    MORDIDA: semear só o primário na carência faz a tecla do P3 sair ao terminar a espera.
    """
    mesa = _Mesa(monkeypatch, uinput)
    monkeypatch.setattr("hefesto_dualsense4unix.daemon.lifecycle.INPUT_GRACE_SEC", 0.5)
    mesa.aperta[P3] = {"cross"}
    async with mesa:
        await mesa.passam_tiques(5)
        assert mesa.teclas() == [], f"a tecla do P3 saiu na carência: {mesa.teclas()}"
        await asyncio.sleep(0.7)
        await mesa.passam_tiques(5)
        assert ("KEY_A", 1) not in mesa.teclas(), "o botão já apertado digitou ao fim da carência"


def test_o_gesto_do_ps_de_cada_controle_cala_os_membros_dele(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O R3 do P3 junto com o PS dele fica no gesto e não vira tecla; o R3 do P2 segue.

    MORDIDA: tirar de `botoes_dos_outros_controles` o `combo_buttons_active` por controle.
    """
    calados = {P3: frozenset({"r3"})}

    def combo(botoes: Any, *, de: str | None = None, gatilhos: Any = None) -> frozenset[str]:
        return calados.get(de or "", frozenset())

    daemon: Any = types.SimpleNamespace(
        _hotkey_manager=types.SimpleNamespace(combo_buttons_active=combo),
        _navegacao_interna=None,
    )
    alvo = "hefesto_dualsense4unix.daemon.subsystems.poll.gatilhos_de_cada_controle"
    monkeypatch.setattr(alvo, lambda d: {
        P2: (frozenset({"r3", "cross"}), 0, 0), P3: (frozenset({"r3", "cross"}), 0, 0)})
    assert sub_mouse.botoes_dos_outros_controles(daemon) == frozenset({"r3", "cross"})
    monkeypatch.setattr(alvo, lambda d: {P3: (frozenset({"r3"}), 0, 0)})
    assert sub_mouse.botoes_dos_outros_controles(daemon) == frozenset()


def test_o_gatilho_do_outro_controle_vira_botao_pelo_limiar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O R2 a fundo do P4 entra como `r2`; o solto, não."""
    daemon: Any = types.SimpleNamespace(_hotkey_manager=None, _navegacao_interna=None)
    alvo = "hefesto_dualsense4unix.daemon.subsystems.poll.gatilhos_de_cada_controle"
    monkeypatch.setattr(alvo, lambda d: {P4: (frozenset(), 0, 255)})
    assert "r2" in sub_mouse.botoes_dos_outros_controles(daemon)
    monkeypatch.setattr(alvo, lambda d: {P4: (frozenset(), 0, 0)})
    assert sub_mouse.botoes_dos_outros_controles(daemon) == frozenset()


def test_com_o_jogo_aberto_o_teclado_so_dentro_do_jogo_le_todo_controle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D-2511-A-TECLA-DE-TODO-CONTROLE-CHEGA-AO-COMPUTADOR: «Só dentro do jogo» sem tabela, o
    teclado do desktop despacha a união dos controles.

    MORDIDA: tirar `botoes_para_o_teclado` do ramo do `despachar_no_jogo`.
    """
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.subsystems.poll.gatilhos_de_cada_controle",
        lambda d: {P3: (frozenset({"cross"}), 0, 0), P4: (frozenset({"circle"}), 0, 0)})
    chamadas: list[frozenset[str]] = []
    daemon: Any = types.SimpleNamespace(
        _tabela_no_jogo=None, _teclado_so_no_jogo=True, _teclado_sempre=False,
        _estava_no_jogo=False, _keyboard_device=MagicMock(),
        _emulation_suppressed=False, _suppress_from_profile=False,
        _hotkey_manager=None, _navegacao_interna=None,
        _dispatch_keyboard_emulation=lambda botoes: chamadas.append(frozenset(botoes)))
    sub_mouse.despachar_no_jogo(daemon, None, frozenset({"square"}), no_jogo=True)
    assert chamadas == [frozenset({"square", "cross", "circle"})]


def _mouse_do_desktop(uinput: _Uinput, ligacoes: dict[str, str] | None = None) -> Any:
    from hefesto_dualsense4unix.integrations.uinput_mouse import UinputMouseDevice

    mouse = UinputMouseDevice()
    assert mouse.start()
    if ligacoes is not None:
        mouse.set_button_actions(ligacoes, frozenset())
    uinput.saiu.clear()
    return mouse


def _despachar_o_mouse(daemon: Any, botoes_do_p1: frozenset[str]) -> None:
    estado = types.SimpleNamespace(
        raw_lx=128, raw_ly=128, raw_rx=128, raw_ry=128, l2_raw=0, r2_raw=0)
    sub_mouse.dispatch_mouse(daemon, estado, botoes_do_p1)


def test_a_seta_o_enter_e_o_esc_do_mouse_saem_de_todo_controle_e_o_clique_so_do_p1(
    monkeypatch: pytest.MonkeyPatch, uinput: _Uinput,
) -> None:
    """Sem troca no perfil, o direcional, o Círculo e o Quadrado viram tecla no mouse virtual.

    O P3 aperta Cima e Círculo e o P4 aperta Quadrado: as três teclas saem. O Cruz do P3 (o clique
    esquerdo) não clica: o clique e o cursor seguem o P1.

    MORDIDA: devolver ao `dispatch_mouse` só os botões do primário.
    """
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.subsystems.poll.gatilhos_de_cada_controle",
        lambda d: {P3: (frozenset({"dpad_up", "circle", "cross"}), 0, 0),
                   P4: (frozenset({"square"}), 0, 0)})
    mouse = _mouse_do_desktop(uinput)
    daemon: Any = types.SimpleNamespace(
        _mouse_device=mouse, store=None, _hotkey_manager=None, _navegacao_interna=None,
        _touchpad_reader=None, config=types.SimpleNamespace(mouse_emulation_enabled=True))
    _despachar_o_mouse(daemon, frozenset())
    saiu = list(uinput.saiu)
    for tecla in ("KEY_UP", "KEY_ENTER", "KEY_ESC"):
        assert (tecla, 1) in saiu, f"{tecla} do outro controle não saiu: {saiu}"
    assert ("BTN_LEFT", 1) not in saiu, "o Cruz do P3 clicou: o clique é do P1"


def test_a_tecla_que_o_perfil_tirou_do_mouse_nao_sai_dele_pelo_outro_controle(
    monkeypatch: pytest.MonkeyPatch, uinput: _Uinput,
) -> None:
    """O perfil que põe o Cima no clique tira a seta do mouse: o Cima do P3 não vira seta."""
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.subsystems.poll.gatilhos_de_cada_controle",
        lambda d: {P3: (frozenset({"dpad_up"}), 0, 0)})
    mouse = _mouse_do_desktop(uinput, {"dpad_up": "BTN_LEFT"})
    daemon: Any = types.SimpleNamespace(
        _mouse_device=mouse, store=None, _hotkey_manager=None, _navegacao_interna=None,
        _touchpad_reader=None, config=types.SimpleNamespace(mouse_emulation_enabled=True))
    _despachar_o_mouse(daemon, frozenset())
    assert uinput.saiu == [], uinput.saiu
