"""A seta segurada se solta quando o perfil troca.

A-SETA-SEGURADA-SE-SOLTA-QUANDO-O-PERFIL-TROCA-01.

O mouse virtual emite o d-pad como `KEY_UP/DOWN/LEFT/RIGHT`. A troca da tabela
(`set_button_actions`, que chega a cada perfil aplicado, inclusive pela troca
automática ao mudar de janela) tem de soltar as setas que a tabela anterior
mantinha apertadas, e a borda seguinte tem de ser calculada pelos CÓDIGOS
emitidos, e não pelo mapa vigente: senão a seta fica presa no desktop, com a
repetição de tecla correndo, até o nó morrer.

O dublê do `uinput` é um gravador estrito: cada código é um objeto próprio, e o
device anota `(código, valor)` na ordem em que o produto emite.
"""
from __future__ import annotations

import sys
from itertools import pairwise
from types import SimpleNamespace

import pytest

from hefesto_dualsense4unix.integrations.uinput_mouse import UinputMouseDevice

_CODIGOS = (
    "REL_X", "REL_Y", "REL_WHEEL", "REL_HWHEEL",
    "BTN_LEFT", "BTN_RIGHT", "BTN_MIDDLE",
    "KEY_UP", "KEY_DOWN", "KEY_LEFT", "KEY_RIGHT",
    "KEY_ENTER", "KEY_ESC",
)
_SETAS = ("KEY_UP", "KEY_DOWN", "KEY_LEFT", "KEY_RIGHT")


class _Gravador:
    """O nó de mentira: guarda os eventos emitidos, na ordem."""

    def __init__(self, *_a: object, **_k: object) -> None:
        self.eventos: list[tuple[str, int]] = []

    def emit(self, ev: tuple[int, int], valor: int, syn: bool = True) -> None:
        self.eventos.append((_CODIGOS[ev[1]], valor))

    def syn(self) -> None:
        self.eventos.append(("SYN", 0))

    def destroy(self) -> None:
        pass


_Mouse = tuple[UinputMouseDevice, _Gravador]


@pytest.fixture
def mouse(monkeypatch: pytest.MonkeyPatch) -> _Mouse:
    gravador = _Gravador()
    mod = SimpleNamespace(Device=lambda *_a, **_k: gravador)
    for i, nome in enumerate(_CODIGOS):
        setattr(mod, nome, (1, i))
    monkeypatch.setitem(sys.modules, "uinput", mod)
    dev = UinputMouseDevice()
    assert dev.start() is True
    return dev, gravador


def _tique(dev: UinputMouseDevice, *botoes: str) -> None:
    dev.dispatch(lx=128, ly=128, rx=128, ry=128, l2=0, r2=0,
                 buttons=frozenset(botoes), now=0.0)


def _de(gravador: _Gravador, codigo: str) -> list[int]:
    return [v for c, v in gravador.eventos if c == codigo]


def _balanceado(gravador: _Gravador) -> None:
    """Cada `KEY_* 1` tem o seu `KEY_* 0`, e nenhum código aperta duas vezes seguidas."""
    for seta in _SETAS:
        valores = _de(gravador, seta)
        for antes, depois in pairwise(valores):
            assert antes != depois, f"{seta}: {valores}"
        assert valores.count(1) == valores.count(0), f"{seta}: {valores}"


def test_a_seta_solta_quando_o_perfil_da_o_dpad_a_um_clique(mouse: _Mouse) -> None:
    dev, gravador = mouse
    _tique(dev, "dpad_up")
    assert _de(gravador, "KEY_UP") == [1]

    dev.set_button_actions({"dpad_up": "BTN_LEFT"})
    assert _de(gravador, "KEY_UP") == [1, 0], "a troca tem de soltar a seta"

    _tique(dev, "dpad_up")
    _tique(dev)
    assert _de(gravador, "KEY_UP") == [1, 0], "KEY_UP 0 sai exatamente uma vez"
    assert _de(gravador, "BTN_LEFT") == [1, 0]
    _balanceado(gravador)


def test_de_fabrica_para_de_fabrica_a_seta_solta_e_volta(mouse: _Mouse) -> None:
    dev, gravador = mouse
    _tique(dev, "dpad_left")
    dev.set_button_actions(None)
    assert _de(gravador, "KEY_LEFT") == [1, 0]

    _tique(dev, "dpad_left")
    assert _de(gravador, "KEY_LEFT") == [1, 0, 1], "o dedo segue: a seta volta"
    _tique(dev)
    assert _de(gravador, "KEY_LEFT") == [1, 0, 1, 0]
    _balanceado(gravador)


def test_a_seta_calada_pelo_perfil_solta_e_nao_volta(mouse: _Mouse) -> None:
    dev, gravador = mouse
    _tique(dev, "dpad_down")
    dev.set_button_actions({}, calados=frozenset({"dpad_down"}))
    _tique(dev, "dpad_down")
    _tique(dev)
    assert _de(gravador, "KEY_DOWN") == [1, 0]
    _balanceado(gravador)


def test_em_toda_sequencia_cada_seta_apertada_se_solta(mouse: _Mouse) -> None:
    dev, gravador = mouse
    tabelas: tuple[dict[str, str] | None, ...] = (
        None,
        {"dpad_up": "BTN_LEFT"},
        {"dpad_right": "BTN_RIGHT", "dpad_left": "BTN_MIDDLE"},
        {},
        None,
    )
    sequencia = (
        ("dpad_up", "dpad_right"), ("dpad_up",), ("dpad_left", "dpad_down"),
        ("dpad_right",), (), ("dpad_up", "dpad_down", "dpad_left", "dpad_right"),
    )
    for tabela in tabelas:
        for botoes in sequencia:
            _tique(dev, *botoes)
        _tique(dev, "dpad_up", "dpad_left")
        dev.set_button_actions(tabela)
    _tique(dev)
    _balanceado(gravador)


def test_parar_o_no_esquece_as_setas(mouse: _Mouse) -> None:
    dev, _gravador = mouse
    _tique(dev, "dpad_right")
    dev.stop()
    assert dev._setas_apertadas == frozenset()
