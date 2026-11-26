"""O-SAIR-DO-MODO-JOGO-VALE-NA-TABELA-DO-JOGO-01: a saída passa sob a supressão do usuário.

Com o jogo aberto e mouse e teclado suspensos pelo gesto, a tabela «Também no jogo» e o teclado
«Só dentro do jogo» ou «Sempre» entravam por `despachar_no_jogo`, que soltava tudo: o botão
ligado a «Sair do modo jogo» ali não saía. Agora `despachar_no_jogo` entrega, sob a supressão
que o USUÁRIO ligou, só o botão dessa ligação, pelo mesmo filtro do teclado do desktop
(`so_a_saida_do_modo_jogo`), e toda outra tecla segue calada.

O leitor é o uinput de mentira que grava cada evento, e o comando é o atendente de produção
(`atendente_do_teclado_na_tela`): a saída é medida pelo `set_emulation_suppressed(False)` que o
daemon recebe, a tecla calada pelo que o uinput nunca emitiu.

MORDIDAS: devolver o `no_jogo = False` sem a entrega da saída (`_so_a_saida_sob_a_supressao`),
trocar o filtro por «tudo passa» ou por «nada passa», e ler só o primário na tabela reprovam.
"""
from __future__ import annotations

import sys
import types
from typing import Any

import pytest

from hefesto_dualsense4unix.core import acoes_de_botao as acoes
from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.daemon.lifecycle import Daemon
from hefesto_dualsense4unix.daemon.subsystems import mouse as sub_mouse
from hefesto_dualsense4unix.daemon.subsystems.keyboard import atendente_do_teclado_na_tela
from hefesto_dualsense4unix.daemon.subsystems.mouse import TabelaNoJogo
from hefesto_dualsense4unix.integrations.uinput_keyboard import UinputKeyboardDevice

P3 = "aa:bb:cc:00:00:03"


class _Ev:
    def __init__(self, nome: str) -> None:
        self.nome = nome


class _Uinput(types.ModuleType):
    """O módulo `uinput`: grava cada evento que qualquer device emite."""

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


def _daemon(
    *, do_usuario: bool = True, so_dentro: bool = False, sempre: bool = False,
    teclado: Any = None,
) -> Any:
    """O daemon de mentira: a supressão e a chamada que a saída faz."""
    d = types.SimpleNamespace(
        config=types.SimpleNamespace(mouse_speed=6, mouse_scroll_speed=1, poll_hz=60),
        controller=None, store=None,
        _tabela_no_jogo=None, _teclado_so_no_jogo=so_dentro, _teclado_sempre=sempre,
        _estava_no_jogo=False, _keyboard_device=teclado,
        _mouse_device=None, _touchpad_reader=None,
        _emulation_suppressed=True, _suppress_from_profile=not do_usuario,
        saidas=0,
    )

    def solta(suprimido: bool) -> None:
        d.saidas += 1
        d._emulation_suppressed = suprimido

    d.set_emulation_suppressed = solta
    d._dispatch_keyboard_emulation = lambda botoes: teclado.dispatch(botoes)
    return d


def _tabela(daemon: Any) -> TabelaNoJogo:
    """A tabela do jogo com «Sair do modo jogo» no Círculo e a letra A no Cruz."""
    tabela = TabelaNoJogo(
        {"circle": acoes.TOKEN_SAIR_DO_JOGO, "cross": "KEY_A"}, None, ligada=True)
    daemon._tabela_no_jogo = tabela
    return tabela


def _teclado_do_desktop() -> UinputKeyboardDevice:
    teclado = UinputKeyboardDevice(bindings={
        "circle": (acoes.TOKEN_SAIR_DO_JOGO,), "cross": ("KEY_A",)})
    assert teclado.start()
    return teclado


def _teclas(uinput: _Uinput) -> list[str]:
    return [nome for nome, valor in uinput.saiu if valor == 1]


def _sem_os_outros(monkeypatch: pytest.MonkeyPatch,
                   outros: dict[str, tuple[frozenset[str], int, int]] | None = None) -> None:
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.subsystems.poll.gatilhos_de_cada_controle",
        lambda d: dict(outros or {}))


def _liga_o_atendente(daemon: Any, teclado: UinputKeyboardDevice) -> None:
    teclado.virtual_token_callback = atendente_do_teclado_na_tela(daemon)


def test_a_tabela_do_jogo_sai_do_modo_jogo_sob_a_supressao(
    uinput: _Uinput, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O Círculo na tabela do jogo, com o gesto de suspender ligado: o modo jogo sai.

    MORDIDA: devolver o `no_jogo = False` sem a entrega (o laço solta tudo e cala a saída).
    """
    _sem_os_outros(monkeypatch)
    daemon = _daemon()
    _tabela(daemon)
    sub_mouse.despachar_no_jogo(daemon, _estado(), frozenset({"circle"}), no_jogo=True)
    assert daemon.saidas == 1, "o botão de «Sair do modo jogo» não saiu pela tabela do jogo"


def test_outra_tecla_da_tabela_segue_calada_sob_a_supressao(
    uinput: _Uinput, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O Cruz (letra A) calado, mesmo apertado junto com o Círculo.

    MORDIDA: trocar o filtro por «tudo passa» (a letra A sai com o mouse suspenso).
    """
    _sem_os_outros(monkeypatch)
    daemon = _daemon()
    _tabela(daemon)
    sub_mouse.despachar_no_jogo(daemon, _estado(), frozenset({"cross"}), no_jogo=True)
    assert daemon.saidas == 0 and "KEY_A" not in _teclas(uinput)
    sub_mouse.despachar_no_jogo(daemon, _estado(), frozenset({"cross", "circle"}), no_jogo=True)
    assert daemon.saidas == 1
    assert "KEY_A" not in _teclas(uinput), "a letra A saiu com o mouse e o teclado suspensos"


def test_o_botao_de_outro_controle_sai_pela_tabela(
    uinput: _Uinput, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O Círculo do P3 sai do modo jogo: a saída lê os controles, não só o primário.

    MORDIDA: ler só o `emu_buttons` do primário na tabela.
    """
    _sem_os_outros(monkeypatch, {P3: (frozenset({"circle"}), 0, 0)})
    daemon = _daemon()
    _tabela(daemon)
    sub_mouse.despachar_no_jogo(daemon, _estado(), frozenset(), no_jogo=True)
    assert daemon.saidas == 1


@pytest.mark.parametrize("so_dentro, sempre", [(True, False), (False, True)])
def test_o_teclado_so_dentro_do_jogo_e_o_sempre_saem_sob_a_supressao(
    uinput: _Uinput, monkeypatch: pytest.MonkeyPatch, so_dentro: bool, sempre: bool
) -> None:
    """O teclado do desktop em «Só dentro do jogo» ou «Sempre» entrega a saída e mais nada."""
    _sem_os_outros(monkeypatch)
    teclado = _teclado_do_desktop()
    daemon = _daemon(so_dentro=so_dentro, sempre=sempre, teclado=teclado)
    _liga_o_atendente(daemon, teclado)
    sub_mouse.despachar_no_jogo(daemon, _estado(), frozenset({"cross"}), no_jogo=True)
    assert daemon.saidas == 0 and "KEY_A" not in _teclas(uinput)
    sub_mouse.despachar_no_jogo(daemon, _estado(), frozenset({"circle", "cross"}), no_jogo=True)
    assert daemon.saidas == 1
    assert "KEY_A" not in _teclas(uinput)


def test_o_filtro_e_o_mesmo_do_teclado_do_desktop(uinput: _Uinput) -> None:
    """O teclado do desktop (sem jogo) e o do jogo leem o filtro de `so_a_saida_do_modo_jogo`.

    MORDIDA: voltar a escrever o filtro à mão no `Daemon` com outro critério.
    """
    teclado = _teclado_do_desktop()
    daemon = _daemon(teclado=teclado)
    _liga_o_atendente(daemon, teclado)
    eu = types.SimpleNamespace(
        _keyboard_device=teclado, _mouse_device=None, _touchpad_reader=None)
    Daemon._dispatch_so_a_saida_do_modo_jogo(eu, frozenset({"cross"}))  # type: ignore[arg-type]
    assert daemon.saidas == 0
    Daemon._dispatch_so_a_saida_do_modo_jogo(  # type: ignore[arg-type]
        eu, frozenset({"cross", "circle"}))
    assert daemon.saidas == 1
    assert sub_mouse.so_a_saida_do_modo_jogo(
        frozenset({"cross", "circle"}), teclado.bindings) == frozenset({"circle"})


def test_a_supressao_do_perfil_do_jogo_nao_muda(
    uinput: _Uinput, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A supressão do PERFIL não cala a tabela: o Cruz segue digitando, a saída não é filtrada."""
    _sem_os_outros(monkeypatch)
    daemon = _daemon(do_usuario=False)
    tabela = _tabela(daemon)
    sub_mouse.despachar_no_jogo(daemon, _estado(), frozenset({"cross"}), no_jogo=True)
    assert tabela._teclado is not None
    assert "KEY_A" in _teclas(uinput)
