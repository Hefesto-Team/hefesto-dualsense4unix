"""O que a aba Rumble PRECISA dizer, e antes de 11/08/2026 não dizia."""
from __future__ import annotations

from tests.conftest import exigir_gi_real

# módulo sob teste (`app.actions.rumble_actions`) importa `gi` na primeira
exigir_gi_real("aba Rumble: a voz do deslizador e o aviso de alcance")

from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions import rumble_actions
from hefesto_dualsense4unix.daemon.subsystems.rumble import (
    RUMBLE_POLICY_MULT,
    sem_dono_do_rumble,
)


def test_a_tela_oferece_exatamente_a_escada_que_o_daemon_aplica() -> None:
    """A tabela da aba deriva da do daemon — não é cópia que possa divergir."""
    da_tela = dict(rumble_actions._POLICY_MULT)
    assert da_tela.pop("auto") == pytest.approx(1.0)
    assert da_tela == RUMBLE_POLICY_MULT


class _FakeScale:
    def __init__(self, value: float = 0.0) -> None:
        self._value = float(value)

    def get_value(self) -> float:
        return self._value

    def set_value(self, v: float) -> None:
        self._value = float(v)


class _FakeToggle:
    def __init__(self, active: bool = False) -> None:
        self._active = active

    def get_active(self) -> bool:
        return self._active

    def set_active(self, v: bool) -> None:
        self._active = bool(v)


class _FakeLabel:
    def __init__(self) -> None:
        self.visivel = False
        self.texto = ""

    def set_visible(self, v: bool) -> None:
        self.visivel = bool(v)

    def get_visible(self) -> bool:
        return self.visivel

    def set_text(self, t: str) -> None:
        self.texto = t

    def set_markup(self, t: str) -> None:
        self.texto = t


class _FakeBarra:
    def __init__(self) -> None:
        self.mensagens: list[str] = []

    def get_context_id(self, _key: str) -> int:
        return 1

    def pop(self, _ctx: int) -> None:
        if self.mensagens:
            self.mensagens.pop()

    def push(self, _ctx: int, msg: str) -> None:
        self.mensagens.append(msg)


def test_vpad_que_nao_subiu_a_tela_diz_que_a_intensidade_nao_alcanca() -> None:
    texto = rumble_actions.texto_do_alcance_da_intensidade(
        {
            "rumble_ff": {"vpads": 0},
            "native_mode": False,
            "gamepad_emulation": {"enabled": True},
        }
    )
    assert texto is not None, (
        "emulação ligada, sem gamepad virtual e sem Nativo não pode ser "
        "silêncio: a tela seguia oferecendo os quatro botões"
    )
    assert "não está chegando" in texto
    # de *"a régua media o mundo de ontem"*.  # (noqa-acento: verbo medir, imperfeito)
    assert "gamepad virtual" in texto, "a frase tem de dizer o que falta"
    # e com ele falso `mode_of_state` só devolve `gamepad` ou `desktop` — os
    assert "aqui embaixo" in texto.lower(), (
        "sem dizer o que a intensidade AINDA faz, o aviso vira 'não serve para "
        "nada' — que é falso: ela vale para a vibração fixada"
    )


def test_no_nativo_a_frase_e_outra() -> None:
    """Ali não há defeito nenhum: é o modo funcionando como deve."""
    texto = rumble_actions.texto_do_alcance_da_intensidade(
        {"rumble_ff": {"vpads": 0}, "native_mode": True}
    )
    assert texto is not None
    assert "Conexão Nativa (Sony)" in texto
    assert "Jogar pelo Hefesto" not in texto


@pytest.mark.parametrize(
    ("native", "vpads", "emulacao"),
    [
        (native, vpads, emulacao)
        for native in (False, True)
        for vpads in (0, 2)
        for emulacao in (False, True)
    ],
)
def test_a_tela_e_o_journal_usam_um_criterio_so(
    native: bool, vpads: int, emulacao: bool
) -> None:
    """A tabela-verdade inteira, comparada contra o predicado do daemon."""
    estado = {
        "rumble_ff": {"vpads": vpads},
        "native_mode": native,
        "gamepad_emulation": {"enabled": emulacao},
    }
    texto = rumble_actions.texto_do_alcance_da_intensidade(estado)
    e_o_quadrante = sem_dono_do_rumble(
        native=native, backends=("vpad",) * vpads, emulacao=emulacao
    )
    disse_defeito = texto is not None and "não está chegando" in texto
    assert disse_defeito is e_o_quadrante, (
        "a tela e o journal discordaram sobre o mesmo quadrante"
    )


def test_com_gamepad_virtual_nao_ha_aviso() -> None:
    assert (
        rumble_actions.texto_do_alcance_da_intensidade({"rumble_ff": {"vpads": 2}})
        is None
    )


@pytest.mark.parametrize(
    "estado",
    [
        {},
        {"rumble_ff": {}},
        {"rumble_ff": {"vpads": None}},
        {"rumble_ff": {"vpads": True}},
        {"rumble_ff": "sei lá"},
    ],
)
def test_sem_o_dado_a_tela_nao_inventa_defeito(estado: dict[str, Any]) -> None:
    """"Não sei" e "não alcança" mandam caçar em lugares opostos.

    Daemon mais velho, resposta que não chegou: a linha fica calada. É a mesma
    disciplina de `texto_dos_pedidos_de_vibracao`, e `bool` é `int` em Python —
    daí o caso `vpads: True`.
    """
    assert rumble_actions.texto_do_alcance_da_intensidade(estado) is None


