"""D-1410-O-PERFIL-FICA-NO-ULTIMO-JOGO: o reinício volta ao último jogo COM o gamepad dele.

Medido em 14/10/2026: depois do reinício do serviço, o daemon subiu com
`gamepad_emulation.enabled=false`, e os pads só subiram quando o jogo abriu de
novo. O nome do perfil voltar não basta: o restore do boot não aplica o modo
(BUG-BOOT-RESTORE-FLIPS-EMULATION-01), e o flag em disco é o da escolha de fora
do jogo, porque o modo que o jogo liga não grava o flag. Esta régua sobe o
`Daemon` REAL num lar de mentira (o `_lar` da régua do reinício com o jogo
aberto) e mede o pad que nasce, não o campo do perfil.
"""
from __future__ import annotations

import asyncio

from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.core.events import EventBus
from hefesto_dualsense4unix.daemon import lifecycle
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.schema import (
    MatchAny,
    MatchCriteria,
    Profile,
    ProfileModeConfig,
)
from hefesto_dualsense4unix.testing import FakeController
from hefesto_dualsense4unix.utils import session
from tests.unit.test_o_reinicio_com_o_jogo_aberto_nasce_no_modo_do_jogo import (
    APPID,
    DELA,
    FREESTYLE,
    JOGO,
    _config,
    _lar,  # noqa: F401
)


def _o_disco(*, ultimo_jogo: bool) -> None:
    """O jogo em Xbox, a escolha de fora do jogo em DualSense, e o flag do gamepad desligado."""
    loader.save_profile(Profile(
        name=FREESTYLE, match=MatchAny(),
        mode=ProfileModeConfig(kind="gamepad", caminho="dualsense"),
    ), origem="régua")
    loader.save_profile(Profile(
        name=JOGO, match=MatchCriteria(window_class=[f"steam_app_{APPID}"]), priority=80,
        mode=ProfileModeConfig(kind="gamepad", caminho="xbox"),
    ), origem="régua")
    loader.save_profile(Profile(
        name=DELA, match=MatchCriteria(window_class=["zathura"]), priority=60,
        mode=ProfileModeConfig(kind="gamepad", caminho="dualsense"),
    ), origem="régua")
    session.save_last_profile(DELA)
    session.save_freestyle_ligado(False)
    session.save_gamepad_emulation(False)
    if ultimo_jogo:
        session.lembrar_o_ultimo_jogo(JOGO)


async def _o_reinicio(nome: str) -> lifecycle.Daemon:
    """O `Daemon` REAL até o restauro e o primeiro tique; nenhum autoswitch depois."""
    store = StateStore()
    estado = ControllerState(
        battery_pct=80, l2_raw=0, r2_raw=0, connected=True,
        transport="usb", buttons_pressed=frozenset(),
    )
    daemon = lifecycle.Daemon(
        controller=FakeController(transport="usb", states=[estado]),
        bus=EventBus(), store=store, config=_config(),
    )
    corrida = asyncio.create_task(daemon.run())
    try:
        for _ in range(600):
            if store.active_profile == nome and store.counter("poll.tick"):
                break
            await asyncio.sleep(0.01)
        assert store.active_profile == nome, (
            f"o boot abriu em {store.active_profile!r}, e o caso pede {nome!r}")
    finally:
        daemon.stop()
        await corrida
    return daemon


def test_o_reinicio_depois_do_jogo_sobe_o_pad_dele_com_o_flag_desligado(
    _lar: list[str],  # noqa: F811
) -> None:
    """Sem jogo aberto, o perfil do último jogo volta, e o pad nasce no caminho dele.

    MORDIDA: tire a chamada do ``_o_pad_do_jogo_volta_no_boot`` no boot do
    ``Daemon.run`` e nenhum pad nasce, com o perfil do jogo ativo.
    """
    _o_disco(ultimo_jogo=True)

    daemon = asyncio.run(_o_reinicio(JOGO))

    assert _lar.count("pad") == 1, f"o pad do P1 nasceu {_lar.count('pad')} vez(es)"
    assert gp.caminho_da_sessao(daemon) == "xbox"
    assert session.load_gamepad_emulation()[0] is False, (
        "o flag em disco é o da escolha de fora do jogo, e o boot não o reescreve")


def test_sem_ultimo_jogo_o_flag_desligado_governa_o_boot(
    _lar: list[str],  # noqa: F811
) -> None:
    """A escolha de fora do jogo segue nos flags: com o gamepad desligado, nenhum pad.

    MORDIDA: faça o ``connection.o_jogo_que_o_boot_restaura`` devolver todo perfil
    restaurado, não só o de jogo, e a escolha liga o pad por cima do flag.
    """
    _o_disco(ultimo_jogo=False)

    asyncio.run(_o_reinicio(DELA))

    assert _lar.count("pad") == 0, "a escolha de fora do jogo ligou o pad por cima do flag"
