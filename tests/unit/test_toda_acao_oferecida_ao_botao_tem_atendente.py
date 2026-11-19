"""TODA-ACAO-OFERECIDA-AO-BOTAO-TEM-QUEM-A-FACA-01 (19/11/2026): o que a linha oferece, se faz.

Medido com o `resolver` de verdade: «Abrir a Steam», «Sair do modo jogo» e «Escolher um
programa…» se ofereciam a toda linha de botão da aba Navegação e caíam em `sem_dono`, que
só vai ao diário. Agora as duas primeiras vão ao teclado virtual como token, e o
atendente do teclado as faz no aperto; a terceira sai da lista.

MORDIDA: tirar do `atendente_do_teclado_na_tela` o ramo da Steam e do sair reprova as duas
linhas da primeira régua com «Abrir a Steam» e «Sair do modo jogo»; tirar do `por_grupo` o
filtro do `SEM_ATENDENTE` as reprova com «Escolher um programa…».
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core import acoes_de_botao as acoes
from hefesto_dualsense4unix.core.keyboard_mappings import (
    TOKEN_CLOSE_OSK,
    TOKEN_OPEN_OSK,
    TOKEN_TOGGLE_OSK,
    is_virtual_token,
)
from hefesto_dualsense4unix.daemon.subsystems import keyboard
from hefesto_dualsense4unix.integrations import steam_launcher
from hefesto_dualsense4unix.integrations.uinput_keyboard import UinputKeyboardDevice

_DO_TECLADO_NA_TELA = (TOKEN_TOGGLE_OSK, TOKEN_OPEN_OSK, TOKEN_CLOSE_OSK)


class _TecladoNaTela:
    def __init__(self) -> None:
        self.atendidos: list[str] = []

    def dispatch_token(self, token: str, phase: str) -> None:
        if phase == "press" and token in _DO_TECLADO_NA_TELA:
            self.atendidos.append(token)


class _Daemon:
    def __init__(self) -> None:
        self._osk_controller = _TecladoNaTela()
        self.supressao: list[bool | None] = []

    def set_emulation_suppressed(self, value: bool | None = None) -> bool:
        self.supressao.append(value)
        return bool(value)


class _Uinput:
    def __getattr__(self, nome: str) -> str:
        if nome.startswith("KEY_"):
            return nome
        raise AttributeError(nome)


class _Fio:
    def __init__(self) -> None:
        self.saiu: list[tuple[str, int]] = []

    def emit(self, ev: str, valor: int, syn: bool = True) -> None:
        self.saiu.append((ev, valor))

    def syn(self) -> None:
        pass


@pytest.fixture
def steam(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    abertas: list[str] = []
    monkeypatch.setattr(steam_launcher, "open_or_focus_steam", lambda: abertas.append("steam"))
    return abertas


def _apertar(linha: str, seq: tuple[str, ...], daemon: _Daemon) -> _Fio:
    fio = _Fio()
    dev = UinputKeyboardDevice(bindings={linha: seq})
    dev._device = fio
    dev._uinput_mod = _Uinput()
    dev.virtual_token_callback = keyboard.atendente_do_teclado_na_tela(daemon)
    dev.dispatch(frozenset({linha}))
    dev.dispatch(frozenset())
    return fio


def _quem_fez(linha: str, token: str, steam: list[str]) -> str | None:
    do_mouse, do_teclado, sem_dono = acoes.resolver({linha: token})
    if linha in sem_dono:
        return None
    if linha in do_mouse:
        return "mouse"
    seq = do_teclado.get(linha)
    if seq is None:
        return None
    daemon = _Daemon()
    antes = len(steam)
    fio = _apertar(linha, seq, daemon)
    assert keyboard._FIO_DA_STEAM.esperar(5.0)
    if not all(is_virtual_token(t) for t in seq):
        return "teclado" if (seq[0], 1) in fio.saiu else None
    if daemon._osk_controller.atendidos:
        return "teclado na tela"
    if len(steam) > antes:
        return "steam"
    if daemon.supressao == [False]:
        return "sair do modo jogo"
    return None


@pytest.mark.parametrize("linha", ["triangle", "dpad_up"])
def test_cada_rotulo_da_linha_tem_quem_o_faca(linha: str, steam: list[str]) -> None:
    """D-1911-TODA-ACAO-DO-BOTAO-TEM-QUEM-A-FACA: toda ação oferecida tem quem a faça."""
    sem_quem: list[str] = []
    for _grupo, rotulos in acoes.por_grupo(linha):
        for rotulo in rotulos:
            token = acoes.token_do_rotulo(rotulo)
            assert token is not None, rotulo
            if token == acoes.TOKEN_NADA:
                continue
            if _quem_fez(linha, token, steam) is None:
                sem_quem.append(rotulo)
    assert sem_quem == [], f"a linha {linha} oferece sem quem faça: {sem_quem}"


def test_a_steam_e_o_sair_do_modo_jogo_se_fazem_no_aperto(steam: list[str]) -> None:
    """O aperto abre a Steam uma vez e solta a supressão; o soltar não repete."""
    assert _quem_fez("cross", acoes.TOKEN_STEAM, steam) == "steam"
    assert steam == ["steam"]
    assert _quem_fez("circle", acoes.TOKEN_SAIR_DO_JOGO, steam) == "sair do modo jogo"


def test_escolher_um_programa_sai_da_lista() -> None:
    """D-1911-TODA-ACAO-DO-BOTAO-TEM-QUEM-A-FACA: o «Escolher um programa…» sai da lista."""
    rotulo = acoes.rotulo(acoes.TOKEN_PROGRAMA)
    for linha in (None, *acoes.BOTOES):
        oferecidos = {r for _g, rs in acoes.por_grupo(linha) for r in rs}
        assert rotulo not in oferecidos, linha
    assert acoes.token_do_rotulo(rotulo) == acoes.TOKEN_PROGRAMA


def test_o_teclado_do_desktop_usa_o_mesmo_atendente(monkeypatch: pytest.MonkeyPatch) -> None:
    """O `start_keyboard_emulation` liga o device ao atendente que faz a Steam e o sair."""
    criado: list[Any] = []

    class _Device(UinputKeyboardDevice):
        def start(self) -> bool:
            criado.append(self)
            return True

    import hefesto_dualsense4unix.integrations.uinput_keyboard as uk

    monkeypatch.setattr(uk, "UinputKeyboardDevice", _Device)
    monkeypatch.setattr(keyboard, "_start_touchpad_reader", lambda _d: None)
    daemon = SimpleNamespace(
        _keyboard_device=None, _osk_controller=None, config=None,
        set_emulation_suppressed=lambda value=None: criado.append(("sair", value)),
    )
    assert keyboard.start_keyboard_emulation(daemon)  # type: ignore[arg-type]
    criado[0].virtual_token_callback(acoes.TOKEN_SAIR_DO_JOGO, "press")
    assert criado[1:] == [("sair", False)]
