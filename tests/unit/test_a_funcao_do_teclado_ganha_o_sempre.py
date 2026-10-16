"""A-FUNCAO-DO-TECLADO-GANHA-O-SEMPRE-01: a quarta palavra do teclado digita com e sem jogo.

«Sempre» é o teclado ligado com `teclado_sempre`: digita fora do jogo (como «Só fora») e também com
um jogo aberto (como «Só dentro»). As três palavras de antes seguem iguais, o perfil de ontem lê o
mesmo estado, e a supressão que o usuário ligou continua calando o teclado.

O teclado do laço é um dublê que anota cada `dispatch`; o disco é o lar de mentira da suíte.

MORDIDAS: tirar o `or _teclado_sempre` de `despachar_no_jogo` (o «Sempre» cala no jogo), religar o
`_teclado_so_no_jogo` no «Sempre» (cala fora do jogo), fazer o gesto «Só fora do jogo» deixar o
`teclado_sempre` ligado (a palavra volta a ser «Sempre» sozinha) e tirar a checagem da supressão do
usuário reprovam.
"""
from __future__ import annotations

import asyncio
import pathlib
import sys
import time
import types
from typing import Any
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.daemon.subsystems import mouse as sub_mouse
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.schema import MatchAny, MatchManual, Profile
from hefesto_dualsense4unix.testing import FakeController

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))


class _TecladoDeMentira:
    def __init__(self) -> None:
        self.dispatches: list[frozenset[str]] = []
        self.primes: list[frozenset[str]] = []

    def dispatch(self, botoes: frozenset[str]) -> None:
        self.dispatches.append(frozenset(botoes))

    def prime(self, botoes: frozenset[str]) -> None:
        self.primes.append(frozenset(botoes))

    def stop(self) -> None:
        pass


def _estado() -> ControllerState:
    return ControllerState(  # type: ignore[call-arg]
        battery_pct=80, connected=True, transport="usb", l2_raw=0, r2_raw=0)


async def _roda_o_laco(
    monkeypatch: pytest.MonkeyPatch, *, so_dentro: bool, sempre: bool, no_jogo: bool,
) -> _TecladoDeMentira:
    """O laço de produção por alguns tiques com o Cruz apertado."""
    monkeypatch.setattr("hefesto_dualsense4unix.daemon.lifecycle.INPUT_GRACE_SEC", 0.0)

    class _Snap:
        buttons_pressed = ["cross"]  # noqa: RUF012

    fc = FakeController(transport="usb", states=[_estado() for _ in range(40)])
    evdev = MagicMock()
    evdev.is_available.return_value = True
    evdev.snapshot.return_value = _Snap()
    fc._evdev = evdev
    daemon = Daemon(
        controller=fc,
        config=DaemonConfig(
            poll_hz=200, ipc_enabled=False, udp_enabled=False,
            autoswitch_enabled=False, mouse_emulation_enabled=False,
            keyboard_emulation_enabled=False,
        ),
    )
    teclado = _TecladoDeMentira()
    daemon._keyboard_device = teclado
    daemon._teclado_so_no_jogo = so_dentro
    daemon._teclado_sempre = sempre
    if no_jogo:
        daemon._gamepad_device = MagicMock()
        daemon._dispatch_gamepad_emulation = lambda estado, botoes: None  # type: ignore[method-assign]
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.subsystems.poll.gatilhos_de_cada_controle",
        lambda d: {})

    run_task = asyncio.create_task(daemon.run())
    prazo = time.monotonic() + 5.0
    while len(teclado.dispatches) + len(teclado.primes) < 3 and time.monotonic() < prazo:
        await asyncio.sleep(0.005)
    daemon.stop()
    await run_task
    return teclado


def _digitou(teclado: _TecladoDeMentira) -> bool:
    return any("cross" in d for d in teclado.dispatches)


# ---------------------------------------------------------------- o laço do daemon


@pytest.mark.asyncio
async def test_sempre_digita_fora_do_jogo(monkeypatch: pytest.MonkeyPatch) -> None:
    """MORDIDA: ligar o `_teclado_so_no_jogo` junto com o «Sempre» cala o teclado fora do jogo."""
    teclado = await _roda_o_laco(monkeypatch, so_dentro=False, sempre=True, no_jogo=False)
    assert _digitou(teclado), "o «Sempre» não digitou fora do jogo"


@pytest.mark.asyncio
async def test_sempre_digita_com_o_jogo_aberto(monkeypatch: pytest.MonkeyPatch) -> None:
    """MORDIDA: tirar o `or _teclado_sempre` de `despachar_no_jogo` deixa o teclado calado."""
    teclado = await _roda_o_laco(monkeypatch, so_dentro=False, sempre=True, no_jogo=True)
    assert _digitou(teclado), f"o «Sempre» não digitou com o jogo aberto: {teclado.dispatches[:2]}"


@pytest.mark.asyncio
async def test_as_tres_de_antes_seguem_iguais(monkeypatch: pytest.MonkeyPatch) -> None:
    """«Só fora» digita fora e cala dentro; «Só dentro» cala fora e digita dentro."""
    so_fora_fora = await _roda_o_laco(monkeypatch, so_dentro=False, sempre=False, no_jogo=False)
    so_fora_dentro = await _roda_o_laco(monkeypatch, so_dentro=False, sempre=False, no_jogo=True)
    so_dentro_fora = await _roda_o_laco(monkeypatch, so_dentro=True, sempre=False, no_jogo=False)
    so_dentro_dentro = await _roda_o_laco(monkeypatch, so_dentro=True, sempre=False, no_jogo=True)
    assert _digitou(so_fora_fora) and not _digitou(so_fora_dentro)
    assert not _digitou(so_dentro_fora) and _digitou(so_dentro_dentro)


def test_a_supressao_do_usuario_cala_o_sempre_com_o_jogo_aberto() -> None:
    """«Suspender mouse e teclado» vale com o jogo aberto, também no «Sempre».

    MORDIDA: tirar o `_suspenso_por_ela` de `despachar_no_jogo`.
    """
    teclado = _TecladoDeMentira()
    chamadas: list[frozenset[str]] = []
    daemon: Any = types.SimpleNamespace(
        _tabela_no_jogo=None, _teclado_so_no_jogo=False, _teclado_sempre=True,
        _estava_no_jogo=False, _keyboard_device=teclado,
        _emulation_suppressed=True, _suppress_from_profile=False,
        _dispatch_keyboard_emulation=lambda botoes: chamadas.append(frozenset(botoes)))
    sub_mouse.despachar_no_jogo(daemon, None, frozenset({"cross"}), no_jogo=True)
    assert chamadas == [], "o teclado digitou com a emulação suspensa por ela"

    daemon._emulation_suppressed = False
    sub_mouse.despachar_no_jogo(daemon, None, frozenset({"cross"}), no_jogo=True)
    assert chamadas == [frozenset({"cross"})]


def test_o_campo_chega_ao_daemon_na_ativacao_do_perfil() -> None:
    """A ativação trava o `teclado_sempre` do perfil, e um perfil sem ele o zera."""
    daemon: Any = types.SimpleNamespace(_tabela_no_jogo=None, _teclado_so_no_jogo=False,
                                        _teclado_sempre=False)
    sub_mouse.trocar_a_tabela_no_jogo(
        daemon, types.SimpleNamespace(teclado_sempre=True, teclado_so_no_jogo=None,
                                      tabela_no_jogo=None))
    assert daemon._teclado_sempre is True
    sub_mouse.trocar_a_tabela_no_jogo(
        daemon, types.SimpleNamespace(teclado_sempre=None, teclado_so_no_jogo=None,
                                      tabela_no_jogo=None))
    assert daemon._teclado_sempre is False


# ---------------------------------------------------------------- o perfil


def test_o_perfil_de_ontem_nao_ganha_o_campo_e_le_o_mesmo_estado() -> None:
    """Sem `teclado_sempre` no disco ele fica ausente, e as três palavras de antes não mudam."""
    from pacotes import a06_navegacao as mod

    ontem = Profile.model_validate({"name": "ontem", "match": {"type": "any"},
                                    "teclado_emulado": True})
    assert ontem.teclado_sempre is None
    assert "teclado_sempre" not in ontem.model_dump(mode="json", exclude_none=True)
    dentro = Profile(name="d", match=MatchAny(), teclado_emulado=True, teclado_so_no_jogo=True)
    sempre = Profile(name="s", match=MatchAny(), teclado_emulado=True, teclado_sempre=True)
    assert Profile.model_validate(sempre.model_dump(mode="json")).teclado_sempre is True
    assert mod._o_teclado_em_palavras(True) == mod.TECLADO_SO_FORA
    assert mod._o_teclado_em_palavras(False) == mod.TECLADO_DESATIVADO
    assert mod._o_teclado_em_palavras(True, so_dentro=bool(dentro.teclado_so_no_jogo)) \
        == mod.TECLADO_SO_DENTRO
    assert mod._o_teclado_em_palavras(
        True, sempre=bool(sempre.teclado_sempre)) in {mod.TECLADO_SEMPRE, mod.TECLADO_SO_FORA}


class _Ponte:
    def __init__(self) -> None:
        self.chamadas: list[tuple[str, dict[str, Any]]] = []

    def resultado(self, metodo: str, **params: Any) -> dict[str, Any]:
        self.chamadas.append((metodo, dict(params)))
        return {"status": "ok", "keyboard_emulation": {"enabled": bool(params.get("enabled"))}}

    def chamar(self, metodo: str, **params: Any) -> bool:
        self.chamadas.append((metodo, dict(params)))
        return True

    def profile_reaplicar(self, nome: str) -> bool:
        self.chamadas.append(("profile.reaplicar", {"nome": nome}))
        return True


@pytest.fixture
def ativo() -> Any:
    import pacotes

    loader.save_profile(Profile(name="regua", match=MatchManual()), origem="regua")
    return pacotes.Contexto(state={"active_profile": "regua"})


def test_o_gesto_sempre_liga_o_teclado_e_grava_so_o_sempre(ativo: Any) -> None:
    """«Sempre» liga o teclado, grava `teclado_sempre` e deixa o «Só dentro» desligado.

    MORDIDA: gravar também `teclado_so_no_jogo=True` no «Sempre» (o teclado calaria fora do jogo).
    """
    # Prova da D-1510-O-TECLADO-GANHA-O-SEMPRE-E-A-VELOCIDADE-E-ABSOLUTA.
    from pacotes import a06_navegacao as mod

    ponte = _Ponte()
    mod.teclado(ativo, {"valor": mod.TECLADO_SEMPRE}, ponte)
    assert ("keyboard.emulation.set", {"enabled": True}) in ponte.chamadas
    gravado = loader.load_profile("regua")
    assert gravado.teclado_emulado is True
    assert gravado.teclado_sempre is True
    assert not gravado.teclado_so_no_jogo


def test_voltar_ao_so_fora_apaga_o_sempre(ativo: Any) -> None:
    """MORDIDA: o gesto «Só fora do jogo» deixa o `teclado_sempre` ligado."""
    from pacotes import a06_navegacao as mod

    mod.teclado(ativo, {"valor": mod.TECLADO_SEMPRE}, _Ponte())
    mod.teclado(ativo, {"valor": mod.TECLADO_SO_FORA}, _Ponte())
    gravado = loader.load_profile("regua")
    assert gravado.teclado_emulado is True
    assert not gravado.teclado_sempre and not gravado.teclado_so_no_jogo
    mod.teclado(ativo, {"valor": mod.TECLADO_SO_DENTRO}, _Ponte())
    gravado = loader.load_profile("regua")
    assert gravado.teclado_so_no_jogo is True and not gravado.teclado_sempre
    mod.teclado(ativo, {"valor": mod.TECLADO_DESATIVADO}, _Ponte())
    assert loader.load_profile("regua").teclado_emulado is False


def test_a_lista_do_desenho_traz_a_quarta_palavra() -> None:
    """O gerador e o pacote falam a mesma lista, e o «Sempre» tem resposta no gesto."""
    import aba06
    from pacotes import a06_navegacao as mod

    assert mod.TECLADO_SEMPRE in aba06.OPCOES_TECLADO
    assert len(aba06.OPCOES_TECLADO) == 4
    ponte = _Ponte()
    mod.teclado(__import__("pacotes").Contexto(state={}), {"valor": mod.TECLADO_SEMPRE}, ponte)
    assert ponte.chamadas[0] == ("keyboard.emulation.set", {"enabled": True})
