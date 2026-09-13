#!/usr/bin/env python3
"""O BOOT ENTREGA O PS DO PERFIL — F1-REMAPEAR-02, 13/09/2026.

O ACHADO veio lido pela F1-REMAPEAR e foi MEDIDO com dublê antes da cura:
`daemon/connection.py::restore_last_profile` montava o `ProfileManager` à mão
e sem o `ps_action_sink`. A ativação do boot rodava inteira, o perfil dava uma
tecla ao PS, e `hotkey.definir_acao_do_ps` não era chamado nenhuma vez — a
escolha só chegava ao `ps_solo` na primeira troca de perfil. Na base
(`e1c7d96b`) o mesmo roteiro deste arquivo imprimiu
`definir_acao_do_ps chamado com: []`.

A CURA passa ao boot o MESMO canal que `profiles/manager.gerente_do_daemon`
passa às outras rotas (`_canal_do_ps`), e mais nada: o `mouse_applier` e o
`mode_applier` continuam `None` pelo BUG-BOOT-RESTORE-FLIPS-EMULATION-01.

O DUBLÊ SABE AS DUAS RESPOSTAS: o perfil que dá uma tecla ao PS a entrega, e o
perfil que não opina APAGA a do perfil de antes — o `None` é metade do
contrato de `definir_acao_do_ps`.

A MORDIDA: tire `ps_action_sink=_canal_do_ps(daemon)` do `restore_last_profile`
e os três casos reprovam.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon import connection
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.daemon.subsystems import hotkey
from hefesto_dualsense4unix.profiles import loader, manager
from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile
from hefesto_dualsense4unix.utils import session

NOME = "Régua do Boot"

#: Uma tecla que `core/acoes_de_botao` conhece — o esquema recusa as outras.
TECLA = "KEY_ESC"


class _Controle:
    """Aceita tudo o que a ativação pedir ao aparelho, e não fala com nenhum."""

    def __getattr__(self, _nome: str) -> Any:
        return lambda *a, **k: None


def _perfil(**campos: Any) -> Profile:
    return Profile(name=NOME, match=MatchAny(), **campos)


@pytest.fixture
def boot(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """O `restore_last_profile` DE VERDADE, com o perfil que o caso der.

    Dublê só nas bordas: o nome do boot, o disco, o aparelho e as três
    aplicações que falam com device. O `ProfileManager`, a ativação, o
    `apply_button_actions`, o `_canal_do_ps` e o `definir_acao_do_ps` são os do
    produto — o espião só anota e repassa.
    """
    chamadas: list[str | None] = []
    construidos: list[dict[str, Any]] = []
    original = hotkey.definir_acao_do_ps

    def espiao(daemon: Any, token: str | None) -> None:
        chamadas.append(token)
        original(daemon, token)

    monkeypatch.setattr(hotkey, "definir_acao_do_ps", espiao)
    classe = manager.ProfileManager
    iniciar = classe.__init__

    def iniciar_anotando(self: Any, *args: Any, **kwargs: Any) -> None:
        construidos.append(kwargs)
        iniciar(self, *args, **kwargs)

    monkeypatch.setattr(classe, "__init__", iniciar_anotando)
    for metodo in ("apply", "apply_keyboard", "apply_emulation"):
        monkeypatch.setattr(classe, metodo, lambda self, *a, **k: None)
    monkeypatch.setattr(session, "resolve_boot_profile", lambda: NOME)

    async def bloqueante(fn: Any) -> Any:
        return fn()

    def rodar(perfil: Profile, daemon: Any = None) -> Any:
        monkeypatch.setattr(loader, "load_profile", lambda nome: perfil)
        monkeypatch.setattr(manager, "load_profile", lambda nome: perfil)
        alvo = daemon or SimpleNamespace(
            controller=_Controle(), store=StateStore(),
            _run_blocking=bloqueante, _native_mode=False)
        asyncio.run(connection.restore_last_profile(alvo))
        return alvo

    return SimpleNamespace(rodar=rodar, chamadas=chamadas, construidos=construidos)


def test_o_boot_entrega_ao_ps_a_tecla_do_perfil(boot: SimpleNamespace) -> None:
    daemon = boot.rodar(_perfil(button_actions={"ps": TECLA}))
    assert boot.chamadas == [TECLA], (
        f"o boot chamou `definir_acao_do_ps` com {boot.chamadas} — a escolha do "
        "perfil para o PS só chegaria ao `ps_solo` na primeira troca de perfil")
    assert hotkey.acao_do_ps_do_perfil(daemon) == TECLA


def test_o_perfil_do_boot_que_nao_opina_apaga_a_escolha_de_antes(
    boot: SimpleNamespace,
) -> None:
    """A segunda resposta do dublê: sem opinião sobre o PS, vale a da máquina."""
    daemon = boot.rodar(_perfil(button_actions={"ps": TECLA}))
    boot.rodar(_perfil(), daemon=daemon)
    assert boot.chamadas == [TECLA, None], boot.chamadas
    assert hotkey.acao_do_ps_do_perfil(daemon) is None, (
        "o boot com um perfil que não opina deixou valendo a tecla do perfil "
        "de antes")


def test_o_boot_nao_liga_o_mouse_nem_o_modo(boot: SimpleNamespace) -> None:
    """O canal do PS entra; os dois appliers que o boot desliga continuam fora."""
    boot.rodar(_perfil(button_actions={"ps": TECLA}))
    assert boot.construidos, "o boot não montou gerente nenhum"
    kwargs = boot.construidos[0]
    assert callable(kwargs.get("ps_action_sink")), sorted(kwargs)
    assert kwargs["mouse_applier"] is None, (
        "o boot passou a ligar o `mouse_applier` — BUG-BOOT-RESTORE-FLIPS-EMULATION-01")
    assert kwargs["mode_applier"] is None, (
        "o boot passou a ligar o `mode_applier` — FEAT-PROFILE-MODE-01")
