"""A tecla dividida só solta com o último botão.

O-MODIFICADOR-SEGURADO-POR-OUTRO-BOTAO-NAO-SE-SOLTA-01.

Os padrões de fábrica dividem teclas (`l1 = Alt+Shift+Tab`, `r1 = Alt+Tab`). O
teclado virtual conta quantos botões seguram cada tecla: o key down sai na
passagem de 0 para 1, o key up na de 1 para 0. Com o R1 de pé, tocar o L1 não
derruba o Alt do R1, e o seletor de janelas não fecha no meio do gesto.

A classe é a mesma para os dois teclados do P1 (o do desktop e o da tabela do
jogo); a régua prova que duas instâncias não se misturam.
"""
from __future__ import annotations

import sys
from collections.abc import Callable
from itertools import pairwise
from types import SimpleNamespace

import pytest

from hefesto_dualsense4unix.core.keyboard_mappings import DEFAULT_BUTTON_BINDINGS
from hefesto_dualsense4unix.integrations.uinput_keyboard import (
    SUPPORTED_KEYS,
    UinputKeyboardDevice,
)

_CODIGOS = tuple(SUPPORTED_KEYS)


class _Gravador:
    """O nó de mentira: guarda `(tecla, valor)` na ordem em que o produto emite."""

    def __init__(self) -> None:
        self.eventos: list[tuple[str, int]] = []

    def emit(self, ev: tuple[int, int], valor: int, syn: bool = True) -> None:
        self.eventos.append((_CODIGOS[ev[1]], valor))

    def syn(self) -> None:
        pass

    def destroy(self) -> None:
        pass


@pytest.fixture
def fabrica(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[], tuple[UinputKeyboardDevice, _Gravador]]:
    """Monta teclados com o `uinput` de mentira; cada um ganha o seu gravador."""
    gravadores: list[_Gravador] = []

    def _device(*_a: object, **_k: object) -> _Gravador:
        g = _Gravador()
        gravadores.append(g)
        return g

    mod = SimpleNamespace(Device=_device)
    for i, nome in enumerate(_CODIGOS):
        setattr(mod, nome, (1, i))
    monkeypatch.setitem(sys.modules, "uinput", mod)

    def _novo() -> tuple[UinputKeyboardDevice, _Gravador]:
        dev = UinputKeyboardDevice()
        assert dev.start() is True
        return dev, gravadores[-1]

    return _novo


_Fabrica = Callable[[], tuple[UinputKeyboardDevice, _Gravador]]


def _de(g: _Gravador, tecla: str) -> list[int]:
    return [v for t, v in g.eventos if t == tecla]


def _balanceado(g: _Gravador) -> None:
    for tecla in {t for t, _ in g.eventos}:
        valores = _de(g, tecla)
        for antes, depois in pairwise(valores):
            assert antes != depois, f"{tecla}: {valores}"
        assert valores.count(1) == valores.count(0), f"{tecla}: {valores}"


def test_os_padroes_de_fabrica_dividem_o_alt() -> None:
    assert "KEY_LEFTALT" in DEFAULT_BUTTON_BINDINGS["l1"]
    assert "KEY_LEFTALT" in DEFAULT_BUTTON_BINDINGS["r1"]


def test_o_l1_tocado_com_o_r1_de_pe_nao_derruba_o_alt(fabrica: _Fabrica) -> None:
    dev, g = fabrica()
    dev.dispatch(frozenset({"r1"}))
    dev.dispatch(frozenset({"r1", "l1"}))
    dev.dispatch(frozenset({"r1"}))
    assert 0 not in _de(g, "KEY_LEFTALT"), "o Alt caiu com o R1 de pé"
    assert 0 not in _de(g, "KEY_TAB"), "o Tab caiu com o R1 de pé"
    assert _de(g, "KEY_LEFTSHIFT") == [1, 0]

    dev.dispatch(frozenset())
    assert _de(g, "KEY_LEFTALT") == [1, 0]
    assert _de(g, "KEY_TAB") == [1, 0]
    _balanceado(g)


def test_o_r1_solta_primeiro_e_o_l1_segue_segurando(fabrica: _Fabrica) -> None:
    dev, g = fabrica()
    dev.dispatch(frozenset({"r1"}))
    dev.dispatch(frozenset({"r1", "l1"}))
    dev.dispatch(frozenset({"l1"}))
    assert _de(g, "KEY_LEFTALT") == [1]
    assert _de(g, "KEY_TAB") == [1]
    dev.dispatch(frozenset())
    _balanceado(g)


def test_set_bindings_com_os_dois_apertados_solta_cada_tecla_uma_vez(fabrica: _Fabrica) -> None:
    dev, g = fabrica()
    dev.dispatch(frozenset({"r1", "l1"}))
    dev.set_bindings(dict(DEFAULT_BUTTON_BINDINGS))
    for tecla in ("KEY_LEFTALT", "KEY_LEFTSHIFT", "KEY_TAB"):
        assert _de(g, tecla) == [1, 0], tecla
    assert dev._quem_segura == {}
    dev.dispatch(frozenset())
    _balanceado(g)


def test_parar_solta_cada_tecla_uma_vez(fabrica: _Fabrica) -> None:
    dev, g = fabrica()
    dev.dispatch(frozenset({"r1", "l1"}))
    dev.stop()
    for tecla in ("KEY_LEFTALT", "KEY_LEFTSHIFT", "KEY_TAB"):
        assert _de(g, tecla) == [1, 0], tecla


def test_o_teclado_da_tabela_do_jogo_nao_interfere_no_do_desktop(fabrica: _Fabrica) -> None:
    desktop, g1 = fabrica()
    jogo, g2 = fabrica()
    desktop.dispatch(frozenset({"r1"}))
    jogo.dispatch(frozenset({"r1"}))
    jogo.dispatch(frozenset())
    assert _de(g1, "KEY_LEFTALT") == [1]
    assert _de(g2, "KEY_LEFTALT") == [1, 0]
    desktop.dispatch(frozenset())
    _balanceado(g1)
    _balanceado(g2)


def test_o_token_virtual_fica_fora_da_conta(fabrica: _Fabrica) -> None:
    dev, g = fabrica()
    fases: list[tuple[str, str]] = []
    dev.virtual_token_callback = lambda tok, fase: fases.append((tok, fase))
    dev.set_bindings({"ps": ("__TOGGLE_OSK__",), "r1": ("KEY_LEFTALT", "KEY_TAB")})
    dev.dispatch(frozenset({"ps", "r1"}))
    dev.dispatch(frozenset())
    assert fases == [("__TOGGLE_OSK__", "press"), ("__TOGGLE_OSK__", "release")]
    assert "__TOGGLE_OSK__" not in dev._quem_segura
    _balanceado(g)


def test_o_botao_semeado_pelo_prime_solta_o_que_segura(fabrica: _Fabrica) -> None:
    dev, g = fabrica()
    dev.prime(frozenset({"r1"}))
    assert g.eventos == []
    dev.dispatch(frozenset({"r1", "l1"}))
    dev.dispatch(frozenset({"r1"}))
    assert 0 not in _de(g, "KEY_LEFTALT")
    dev.dispatch(frozenset())
    assert _de(g, "KEY_LEFTALT") == [0]


def test_set_bindings_solta_o_que_a_tabela_trocada_por_fora_ainda_segura(
    fabrica: _Fabrica,
) -> None:
    """A tabela trocada por atribuição direta (como o `_digitar_o_ps` faz) não prende tecla."""
    dev, g = fabrica()
    dev.dispatch(frozenset({"r1"}))
    dev.bindings = {**dev.bindings, "r1": ("KEY_ENTER",)}
    dev.set_bindings(dict(DEFAULT_BUTTON_BINDINGS))
    for tecla in ("KEY_LEFTALT", "KEY_TAB"):
        assert _de(g, tecla) == [1, 0], tecla
    assert _de(g, "KEY_ENTER") == []
    assert dev._quem_segura == {}
