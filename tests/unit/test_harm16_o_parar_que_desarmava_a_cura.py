"""HARM-16 — o "Parar" da aba Rumble desarmava a cura para o resto da sessão.

**O defeito, medido em 25/08/2026.** `zero_motors_on_mode_exit`
(`daemon/subsystems/rumble.py`) é a cura HARM-16: ao SAIR de um modo, quem
dirigia os motores some no meio de uma vibração e ninguém zera o hardware — o
reassert do poll loop é no-op justamente em passthrough. A guarda dela era
`if daemon.config.rumble_active is not None: return`, escrita para não desfazer
o gesto da usuária quando ela FIXA um par pela aba.

`rumble.stop` — o botão "Parar" — grava `(0, 0)`, **que também não é `None`**.
Logo, depois de UM clique em "Parar" na sessão, sair de um modo deixava de zerar
os motores. E o estado é vitalício por decisão medida:
`lifecycle.apply_profile_rumble_passthrough` preserva o `(0, 0)` de propósito,
então nem trocar de perfil o soltava — só "Devolver ao jogo" ou um rumble novo.

A forma já tinha nome nesta casa: a NATIVO-RUMBLE-01 (19/08/2026) reconheceu
*"`(0,0)` não é `None`"* na porta do Modo Nativo e curou **só aquela**. Esta
entrega fecha a porta que ficou aberta, com o mesmo teste que
`_handle_rumble_stop` e `_lembrar_dono_vibrando` já usam: `any(par)`.

**O que morde:** devolver a guarda antiga (`par is not None`) reprova os dois
primeiros testes. E o terceiro existe para que a cura não vire o defeito
oposto — zerar sempre desfaria o par não-nulo que ela fixou.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.daemon.subsystems.rumble import (
    RUMBLE_PARADO,
    zero_motors_on_mode_exit,
)
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.testing import FakeController


@pytest.fixture
async def servidor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """IpcServer + Daemon com FakeController. Devolve (server, daemon, fc).

    Mesmo molde do `test_nativo_rumble_01_a_recusa_com_motivo.py`, pelo mesmo
    motivo: o defeito mora na conversa entre o handler de IPC e o par gravado
    no `DaemonConfig`, e um dublê que só tivesse o `config` não exercitaria a
    porta por onde o `(0, 0)` entra de verdade.
    """
    fc = FakeController(transport="usb")
    fc.connect()
    store = StateStore()
    store.update_controller_state(
        ControllerState(
            battery_pct=90, l2_raw=0, r2_raw=0, connected=True, transport="usb"
        )
    )
    cfg = DaemonConfig(
        poll_hz=60,
        ipc_enabled=False,
        udp_enabled=False,
        autoswitch_enabled=False,
        auto_reconnect=False,
    )
    daemon = Daemon(controller=fc, store=store, config=cfg)
    monkeypatch.setattr(daemon, "_reapply_last_profile", lambda: None)
    manager = ProfileManager(controller=fc, store=store)
    server = IpcServer(
        controller=fc,
        store=store,
        profile_manager=manager,
        socket_path=tmp_path / "hefesto_test.sock",
        daemon=daemon,
    )
    await server.start()
    try:
        yield server, daemon, fc
    finally:
        await server.stop()


def _rumbles(fc: FakeController) -> list[tuple[int, int]]:
    return [c.payload for c in fc.commands if c.kind == "set_rumble"]


# --- 1. O caminho de produção inteiro, do clique à saída do modo -------------


@pytest.mark.asyncio
async def test_o_parar_da_aba_nao_desarma_a_saida_de_modo(servidor: Any) -> None:
    """O gesto que a usuária faz, na ordem em que ela o faz.

    MORDE: com a guarda antiga (`rumble_active is not None`), o `(0, 0)`
    gravado pelo "Parar" faz `zero_motors_on_mode_exit` voltar sem escrever
    nada — `_rumbles(fc)` fica vazio e o motor que o jogo deixou girando por
    fora continua girando.
    """
    server, daemon, fc = servidor

    r = await server._handle_rumble_stop({})
    assert r["desfecho"] == RUMBLE_PARADO
    # É este par — e não `None` — que a guarda antiga lia como "o dono é ela".
    assert daemon.config.rumble_active == (0, 0)

    fc.commands.clear()
    zero_motors_on_mode_exit(daemon)

    assert _rumbles(fc) == [(0, 0)], (
        "a saída de modo tem de zerar os motores mesmo com o silêncio fixado "
        "pelo «Parar»: zerar É o gesto dela, palavra por palavra"
    )


@pytest.mark.asyncio
async def test_o_parar_continua_desarmando_depois_de_trocar_de_perfil(
    servidor: Any,
) -> None:
    """O que torna o defeito caro: o `(0, 0)` é vitalício.

    `apply_profile_rumble_passthrough` preserva o par por decisão medida, então
    a sessão inteira depois de um "Parar" ficava sem a HARM-16 — não só a
    próxima saída de modo.

    MORDE: com a guarda antiga, a segunda saída de modo também é no-op.
    """
    server, daemon, fc = servidor

    await server._handle_rumble_stop({})
    fc.commands.clear()
    zero_motors_on_mode_exit(daemon)
    zero_motors_on_mode_exit(daemon)

    assert _rumbles(fc) == [(0, 0), (0, 0)]


# --- 2. A cura não pode virar o defeito oposto ------------------------------


@pytest.mark.asyncio
async def test_o_par_nao_nulo_que_ela_fixou_continua_intocado(
    servidor: Any,
) -> None:
    """A metade que impede o conserto de reintroduzir outro defeito.

    Com um par NÃO-NULO o dono é a usuária: o reassert re-afirma o valor em
    200 ms de qualquer forma, e zerar aqui seria desfazer o gesto dela.

    MORDE: uma cura que zerasse sempre (guarda apagada inteira) escreveria
    `(0, 0)` aqui e apagaria a vibração que ela acabou de travar.
    """
    server, daemon, fc = servidor

    await server._handle_rumble_set({"weak": 160, "strong": 220})
    assert daemon.config.rumble_active == (160, 220)

    fc.commands.clear()
    zero_motors_on_mode_exit(daemon)

    assert _rumbles(fc) == []


def test_passthrough_continua_sendo_o_caso_canonico() -> None:
    """O caso para o qual a HARM-16 nasceu não pode ter mudado.

    MORDE: qualquer reescrita da guarda que perca o `None` (por exemplo trocar
    o teste inteiro por `if not any(par)`, que estoura em `None`) reprova aqui.
    """
    chamadas: list[str] = []
    daemon = SimpleNamespace(
        config=SimpleNamespace(rumble_active=None),
        controller=SimpleNamespace(
            set_rumble=lambda weak, strong: chamadas.append(f"zero={weak},{strong}")
        ),
    )

    zero_motors_on_mode_exit(daemon)  # type: ignore[arg-type]

    assert chamadas == ["zero=0,0"]
