"""O clique do Modo Freestyle não muda nada enquanto a suspensão existir.

Vitória, 30/09/2026: o modo fica no produto, e o botão não entra na jogatina
até a leva dele fechar. A flag é `freestyle_suspenso.flag`. Sem o arquivo, o
clique volta a valer.

Mordida: apague o `if freestyle_suspenso()` de `o_freestyle_manda` e o
primeiro teste passa com o store ligado.
"""
from __future__ import annotations

import asyncio

from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles.manager import (
    ligar_o_freestyle,
    o_freestyle_manda,
)
from hefesto_dualsense4unix.utils import session
from hefesto_dualsense4unix.utils.xdg_paths import config_dir


def _suspeita() -> None:
    config_dir(ensure=True).joinpath("freestyle_suspenso.flag").write_text(
        "1\n", encoding="utf-8"
    )


def test_com_a_flag_o_store_ligado_nao_manda() -> None:
    _suspeita()
    store = StateStore()
    store.set_freestyle_ligado(True)
    assert o_freestyle_manda(store) is False
    assert session.load_freestyle_ligado() is False


def test_com_a_flag_ligar_grava_desligado() -> None:
    _suspeita()
    store = StateStore()
    store.set_freestyle_ligado(True)
    ligar_o_freestyle(store, True)
    assert store.freestyle_ligado is False
    assert session.load_freestyle_ligado() is False
    assert not (config_dir() / "freestyle_ligado.flag").exists()


def test_sem_a_flag_ligar_grava() -> None:
    store = StateStore()
    ligar_o_freestyle(store, True)
    assert store.freestyle_ligado is True
    assert session.load_freestyle_ligado() is True


class _Handlers(IpcHandlersMixin):
    def __init__(self, store: StateStore) -> None:
        self.store = store
        self.daemon = None


def test_com_a_flag_o_botao_nao_troca_o_perfil() -> None:
    _suspeita()
    store = StateStore()
    store.set_active_profile("Future Knight")
    store.set_freestyle_ligado(True)
    resposta = asyncio.run(_Handlers(store)._handle_freestyle_set({"ligado": True}))
    assert resposta["freestyle_ligado"] is False
    assert resposta["freestyle_suspenso"] is True
    assert store.active_profile == "Future Knight"
    assert store.freestyle_ligado is False
