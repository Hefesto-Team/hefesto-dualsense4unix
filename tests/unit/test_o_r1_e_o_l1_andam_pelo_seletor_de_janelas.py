"""O-R1-E-O-L1-ANDAM-PELO-SELETOR-DE-JANELAS-NOS-DOIS-SENTIDOS-01: o L1 volta, o R1 avança.

Com os padrões de fábrica (R1 = Alt+Tab, L1 = Alt+Shift+Tab), segurar o R1 e tocar o L1 mantinha o
seletor de janelas aberto e não voltava um item: o Tab já estava de pé e o segundo pedido não
saía. Agora só os modificadores (Alt, Shift, Ctrl, Super) ficam presos enquanto algum botão os
segura, e a tecla final de uma combinação é tocada de novo a cada aperto do botão que a pede, mesmo
com outro botão a segurando. A tecla de um botão sem modificador (uma letra de movimento, por
exemplo) segue presa e dividida entre os botões, sem soltar nem reapertar.

Decisão: D-2511-O-R1-E-O-L1-ANDAM-PELO-SELETOR-DE-JANELAS, que emenda
D-1310-O-TECLADO-CONTA-QUANTOS-BOTOES-SEGURAM-CADA-TECLA, que deixou o gesto de ir e voltar
para depois.

O leitor é o `uinput` de mentira que grava `(tecla, valor)` na ordem em que o produto emite; a
tecla final é lida junto do estado do Shift naquele instante, pelo fluxo gravado.

MORDIDAS: voltar a não reemitir a tecla segura (tirar o retoque do `_emit_sequence_press`),
estender o retoque à tecla de um botão sem modificador e tratar o Shift como tecla final reprovam.
"""
from __future__ import annotations

import sys
import types
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import mouse as sub_mouse
from hefesto_dualsense4unix.integrations.uinput_keyboard import UinputKeyboardDevice

P3 = "aa:bb:cc:00:00:03"


class _Uinput(types.ModuleType):
    def __init__(self) -> None:
        super().__init__("uinput")
        self.saiu: list[tuple[str, int]] = []

    def __getattr__(self, nome: str) -> Any:
        if nome.startswith(("KEY_", "BTN_", "REL_")):
            return nome
        raise AttributeError(nome)

    def Device(self, caps: Any, name: str = "") -> Any:  # noqa: N802
        mod = self

        class _Dev:
            def emit(self, ev: Any, valor: int, syn: bool = True) -> None:
                mod.saiu.append((ev, valor))

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


def _teclado() -> UinputKeyboardDevice:
    teclado = UinputKeyboardDevice()
    assert teclado.start()
    return teclado


def _toques_do_tab_com_o_shift(eventos: list[tuple[str, int]]) -> list[bool]:
    """Cada vez que o Tab desce, o Shift estava de pé? Na ordem do fluxo gravado."""
    shift = False
    saida: list[bool] = []
    for tecla, valor in eventos:
        if tecla == "KEY_LEFTSHIFT":
            shift = bool(valor)
        elif tecla == "KEY_TAB" and valor == 1:
            saida.append(shift)
    return saida


def test_r1_de_pe_e_l1_tocado_duas_vezes_volta_duas_janelas(uinput: _Uinput) -> None:
    """O Alt fica preso do começo ao fim, o Tab desce três vezes e duas com o Shift de pé.

    MORDIDA: tirar o retoque da tecla final de `_emit_sequence_press` (o Tab sobe uma vez só).
    """
    teclado = _teclado()
    teclado.dispatch(frozenset({"r1"}))
    teclado.dispatch(frozenset({"r1", "l1"}))
    teclado.dispatch(frozenset({"r1"}))
    teclado.dispatch(frozenset({"r1", "l1"}))
    teclado.dispatch(frozenset({"r1"}))
    teclado.dispatch(frozenset())
    alt = [valor for tecla, valor in uinput.saiu if tecla == "KEY_LEFTALT"]
    assert alt == [1, 0], f"o Alt não ficou preso do começo ao fim: {alt}"
    assert uinput.saiu[-1] == ("KEY_LEFTALT", 0), "o Alt não foi solto por último"
    assert _toques_do_tab_com_o_shift(uinput.saiu) == [False, True, True], uinput.saiu
    shift = [valor for tecla, valor in uinput.saiu if tecla == "KEY_LEFTSHIFT"]
    assert shift == [1, 0, 1, 0]


def test_a_tecla_final_so_fica_solta_no_fim(uinput: _Uinput) -> None:
    """Cada retoque solta e aperta; ao soltar o R1 o Tab sobe e o Alt sobe por último."""
    teclado = _teclado()
    teclado.dispatch(frozenset({"r1"}))
    teclado.dispatch(frozenset({"r1", "l1"}))
    teclado.dispatch(frozenset({"r1"}))
    teclado.dispatch(frozenset())
    tab = [valor for tecla, valor in uinput.saiu if tecla == "KEY_TAB"]
    assert tab == [1, 0, 1, 0], f"o Tab não foi retocado e solto: {tab}"
    assert [tecla for tecla, _ in uinput.saiu[-2:]] == ["KEY_TAB", "KEY_LEFTALT"]


def test_o_r1_sozinho_e_o_l1_sozinho_seguem_como_antes(uinput: _Uinput) -> None:
    teclado = _teclado()
    teclado.dispatch(frozenset({"r1"}))
    teclado.dispatch(frozenset())
    assert uinput.saiu == [
        ("KEY_LEFTALT", 1), ("KEY_TAB", 1), ("KEY_TAB", 0), ("KEY_LEFTALT", 0)]
    uinput.saiu.clear()
    teclado.dispatch(frozenset({"l1"}))
    teclado.dispatch(frozenset())
    assert uinput.saiu == [
        ("KEY_LEFTALT", 1), ("KEY_LEFTSHIFT", 1), ("KEY_TAB", 1),
        ("KEY_TAB", 0), ("KEY_LEFTSHIFT", 0), ("KEY_LEFTALT", 0)]


def test_a_tecla_de_botao_sem_modificador_segue_presa_e_dividida(uinput: _Uinput) -> None:
    """Dois botões na mesma letra: a tecla desce uma vez e só sobe com o último, sem retoque.

    MORDIDA: estender o retoque à tecla sozinha (a letra de movimento falharia no jogo).
    """
    teclado = UinputKeyboardDevice(bindings={"cross": ("KEY_A",), "triangle": ("KEY_A",)})
    assert teclado.start()
    teclado.dispatch(frozenset({"cross"}))
    teclado.dispatch(frozenset({"cross", "triangle"}))
    teclado.dispatch(frozenset({"triangle"}))
    assert uinput.saiu == [("KEY_A", 1)]
    teclado.dispatch(frozenset())
    assert uinput.saiu == [("KEY_A", 1), ("KEY_A", 0)]


def test_o_shift_nao_e_tecla_final(uinput: _Uinput) -> None:
    """Uma combinação que termina em modificador não retoca nada: o Shift segue contado.

    MORDIDA: tirar a conferência de `MODIFICADORES` do retoque.
    """
    teclado = UinputKeyboardDevice(bindings={
        "cross": ("KEY_LEFTCTRL", "KEY_LEFTSHIFT"), "circle": ("KEY_LEFTALT", "KEY_LEFTSHIFT")})
    assert teclado.start()
    teclado.dispatch(frozenset({"cross"}))
    teclado.dispatch(frozenset({"cross", "circle"}))
    assert [v for t, v in uinput.saiu if t == "KEY_LEFTSHIFT"] == [1]


def test_o_l1_de_outro_controle_tambem_volta(
    uinput: _Uinput, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O R1 do P1 de pé e o L1 do P3 tocado, pela tabela do jogo: o Tab é retocado com o Shift.

    A tabela usa o mesmo teclado e a mesma união de controles: vale para o botão de qualquer
    controle, de P1 a P4.
    """
    tabela = sub_mouse.TabelaNoJogo(
        {"r1": "KEY_LEFTALT+KEY_TAB", "l1": "KEY_LEFTALT+KEY_LEFTSHIFT+KEY_TAB"},
        None, ligada=True)
    daemon: Any = types.SimpleNamespace(
        config=types.SimpleNamespace(mouse_speed=6, mouse_scroll_speed=1, poll_hz=60),
        controller=None, store=None, _tabela_no_jogo=tabela, _teclado_so_no_jogo=False,
        _teclado_sempre=False, _estava_no_jogo=False, _keyboard_device=None,
        _emulation_suppressed=False, _suppress_from_profile=False,
        _hotkey_manager=None, _navegacao_interna=None)
    estado = types.SimpleNamespace(
        raw_lx=128, raw_ly=128, raw_rx=128, raw_ry=128, l2_raw=0, r2_raw=0)
    do_p3 = {"l1": frozenset[str]()}
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.subsystems.poll.gatilhos_de_cada_controle",
        lambda d: {P3: (do_p3["l1"], 0, 0)})
    sub_mouse.despachar_no_jogo(daemon, estado, frozenset({"r1"}), no_jogo=True)
    for _ in range(2):
        do_p3["l1"] = frozenset({"l1"})
        sub_mouse.despachar_no_jogo(daemon, estado, frozenset({"r1"}), no_jogo=True)
        do_p3["l1"] = frozenset()
        sub_mouse.despachar_no_jogo(daemon, estado, frozenset({"r1"}), no_jogo=True)
    sub_mouse.despachar_no_jogo(daemon, estado, frozenset(), no_jogo=True)
    teclas = [(t, v) for t, v in uinput.saiu if t.startswith("KEY_")]
    assert _toques_do_tab_com_o_shift(teclas) == [False, True, True], teclas
