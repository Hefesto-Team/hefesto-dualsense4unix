"""O-TECLADO-VIRTUAL-DIGITA-TODA-TECLA-QUE-O-PERFIL-ACEITA-01: uma lista só, a do nó.

O nó do teclado virtual nascia com uma lista escrita à mão (77 teclas e depois mais algumas), e as
duas validações do perfil divergiam da lista: `button_actions` recusava `KEY_MINUS`, `key_bindings`
aceitava qualquer `KEY_*` do `evdev.ecodes` e o nó nunca a digitava. Agora o nó nasce com todas as
teclas de teclado e de mídia do `evdev.ecodes` (código 1 a 255), as duas validações perguntam a
mesma lista, e a tecla fora das capacidades do nó é recusada com aviso em vez de emitida ao vazio.

Decisão: D-2511-O-NO-DO-TECLADO-TEM-TODA-TECLA-DO-KERNEL (o nó e o perfil falam a mesma lista).

O leitor é o `uinput` de mentira que grava as capacidades que o nó declara e cada evento que ele
emite, e a enumeração do `evdev.ecodes` aqui é feita pelo mapa de código para nome (`ecodes.KEY`),
não pela função que a cura usa.

MORDIDAS: tirar uma tecla da lista (a F24), voltar a validação de `key_bindings` para o
`hasattr(ecodes, ...)`, voltar a de `button_actions` para uma lista à mão e tirar a recusa por
capacidade de `_evento` reprovam.
"""
from __future__ import annotations

import sys
import types
from typing import Any

import pytest
from evdev import ecodes

from hefesto_dualsense4unix.core import acoes_de_botao as acoes
from hefesto_dualsense4unix.integrations import uinput_keyboard
from hefesto_dualsense4unix.integrations.uinput_keyboard import (
    SUPPORTED_KEYS,
    UinputKeyboardDevice,
)
from hefesto_dualsense4unix.profiles.schema import Profile, _e_combinacao_de_teclas


class _Uinput(types.ModuleType):
    """O módulo `uinput`: `KEY_*` com o código do kernel, capacidades e eventos gravados."""

    def __init__(self) -> None:
        super().__init__("uinput")
        self.capacidades: list[tuple[int, int]] = []
        self.saiu: list[tuple[int, int]] = []

    def __getattr__(self, nome: str) -> Any:
        codigo = ecodes.ecodes.get(nome) if nome.startswith("KEY_") else None
        if isinstance(codigo, int):
            return (ecodes.EV_KEY, codigo)
        raise AttributeError(nome)

    def Device(self, caps: Any, name: str = "") -> Any:  # noqa: N802
        self.capacidades = list(caps)
        mod = self

        class _Dev:
            def emit(self, ev: Any, valor: int, syn: bool = True) -> None:
                mod.saiu.append((ev[1], valor))

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


def _teclas_de_teclado_do_kernel() -> set[int]:
    """Os códigos 1 a 255 que o `ecodes.KEY` nomeia, sem o reservado e o desconhecido."""
    fora = {ecodes.KEY_RESERVED, ecodes.KEY_UNKNOWN}
    return {codigo for codigo in ecodes.KEY if 1 <= codigo <= 255 and codigo not in fora}


def _aceita_em_key_bindings(nome: str) -> bool:
    try:
        Profile.model_validate({
            "name": "t", "match": {"type": "any"}, "key_bindings": {"cross": [nome]}})
    except ValueError:
        return False
    return True


def _aceita_em_button_actions(nome: str) -> bool:
    return _e_combinacao_de_teclas(nome)


def test_o_no_nasce_com_toda_tecla_de_teclado_do_kernel(uinput: _Uinput) -> None:
    """As capacidades que o nó declara são todas as teclas 1 a 255, nem mais nem menos.

    MORDIDA: tirar a F24 da lista (ou voltar à lista escrita à mão) reprova.
    """
    teclado = UinputKeyboardDevice()
    assert teclado.start()
    declaradas = {codigo for tipo, codigo in uinput.capacidades if tipo == ecodes.EV_KEY}
    assert declaradas == _teclas_de_teclado_do_kernel()
    for nome in ("KEY_MINUS", "KEY_EQUAL", "KEY_F13", "KEY_F24", "KEY_PAUSE", "KEY_102ND",
                 "KEY_KP5", "KEY_CAPSLOCK", "KEY_PLAYPAUSE", "KEY_SYSRQ"):
        assert nome in SUPPORTED_KEYS, nome


def test_toda_tecla_aceita_por_qualquer_validacao_esta_no_no_e_vice_versa(
    uinput: _Uinput,
) -> None:
    """As duas validações do perfil aceitam exatamente as teclas que o nó declara.

    MORDIDA: voltar `key_bindings` ao `hasattr(ecodes, ...)` ou `button_actions` a uma lista à mão.
    """
    teclado = UinputKeyboardDevice()
    assert teclado.start()
    no = {codigo for tipo, codigo in uinput.capacidades if tipo == ecodes.EV_KEY}
    nomes = {nome for nome in ecodes.ecodes if nome.startswith("KEY_")}
    for nome in sorted(nomes):
        codigo = ecodes.ecodes[nome]
        no_no = isinstance(codigo, int) and codigo in no
        assert _aceita_em_key_bindings(nome) is no_no, f"key_bindings e o nó divergem em {nome}"
        assert _aceita_em_button_actions(nome) is no_no, (
            f"button_actions e o nó divergem em {nome}")


@pytest.mark.parametrize("nome", ["KEY_RESERVED", "KEY_UNKNOWN", "KEY_MAX", "KEY_NAO_EXISTE"])
def test_a_tecla_que_o_no_nao_tem_e_recusada_nas_duas_validacoes(nome: str) -> None:
    assert not _aceita_em_key_bindings(nome)
    assert not _aceita_em_button_actions(nome)


def test_o_menos_num_botao_chega_ao_no(uinput: _Uinput) -> None:
    """KEY_MINUS em `button_actions` carrega, resolve para o teclado e o nó digita o traço."""
    perfil = Profile.model_validate({
        "name": "t", "match": {"type": "any"}, "button_actions": {"triangle": "KEY_MINUS"}})
    _do_mouse, do_teclado, _sem_dono = acoes.resolver(perfil.button_actions)
    assert do_teclado["triangle"] == ("KEY_MINUS",)
    teclado = UinputKeyboardDevice()
    assert teclado.start()
    teclado.set_bindings({"triangle": do_teclado["triangle"]})
    teclado.dispatch(frozenset({"triangle"}))
    teclado.dispatch(frozenset())
    assert uinput.saiu == [(ecodes.KEY_MINUS, 1), (ecodes.KEY_MINUS, 0)]


def test_a_tecla_sem_capacidade_e_recusada_com_aviso(
    uinput: _Uinput, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A ligação com uma tecla que o nó não declara não emite nada e avisa.

    MORDIDA: tirar a conferência das capacidades de `_evento` (o módulo tem o nome e o evento
    sairia ao vazio, com o diário dizendo que saiu).
    """
    avisos: list[tuple[str, dict[str, Any]]] = []
    falso = types.SimpleNamespace(
        warning=lambda evento, **kw: avisos.append((evento, kw)),
        info=lambda *a, **k: None, debug=lambda *a, **k: None)
    monkeypatch.setattr(uinput_keyboard, "logger", falso)
    teclado = UinputKeyboardDevice(bindings={"cross": ("KEY_MAX",)})
    assert teclado.start()
    uinput.KEY_MAX = (ecodes.EV_KEY, 0x2FF)  # type: ignore[attr-defined]
    teclado.dispatch(frozenset({"cross"}))
    assert uinput.saiu == []
    assert [nome for nome, _ in avisos] == ["keyboard_key_unknown"]
    assert avisos[0][1]["key"] == "KEY_MAX"


def test_a_lista_tem_um_dono_so() -> None:
    """A captura de tecla da tela lê a mesma lista que o nó e as validações."""
    from hefesto_dualsense4unix.interface.pacotes import a13_mapa_do_controle as a13

    capturaveis = {tecla for tecla in a13.CODIGO_DA_TECLA.values() if tecla in SUPPORTED_KEYS}
    assert capturaveis
    assert all(_aceita_em_button_actions(tecla) for tecla in capturaveis)
