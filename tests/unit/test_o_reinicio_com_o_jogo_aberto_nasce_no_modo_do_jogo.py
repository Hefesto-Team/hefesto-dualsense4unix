"""O reinício com o jogo aberto nasce no modo do jogo (A-TRAVA-DO-JOGO-ABERTO-TEM-UM-DONO-01).

Medido em 30/09: o «Reiniciar» da aba Sistema com o Future Knight aberto
(perfil em Xbox) subiu o pad do P1 às 03:06:47 no modo de fora do jogo
(DualSense), o sinal de jogo só foi fiado às 03:06:50 e subiu às 03:06:51, e
às 03:06:59 o autoswitch ativou o Future Knight e a trava recusou a troca:
ela passou a proteger um modo que ninguém escolheu para aquele jogo. Ela
resolveu na mão às 03:07:09, com o PS + R3.

A cura (`D-3009-O-REINICIO-COM-O-JOGO-ABERTO-NASCE-NO-PERFIL-DO-JOGO`, a
validar
pelo usuário): o sinal nasce e é avaliado antes do primeiro pad, e o boot
pergunta pelo jogo em cena antes da escolha do usuário — o pad, o perfil ativo e a
tela nascem do mesmo perfil.

O lar é de mentira (`XDG_*` desviados, com guarda que sai): o marcador do
lançador com o appid e um pid vivo (o desta régua), um perfil com a regra
`steam_app_<appid>` em Xbox, o Freestyle desligado, e a escolha do usuário num
terceiro perfil em DualSense. A varredura de processos é calada: o jogo em
cena é o do marcador, e um jogo aberto na máquina de quem roda não decide nada.
"""
from __future__ import annotations

import asyncio
import os
import time
from collections.abc import Iterator
from typing import Any

import pytest

from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.core.events import EventBus
from hefesto_dualsense4unix.daemon import lifecycle
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.daemon.subsystems import external_mask as em
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.integrations import virtual_pad as vp
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.schema import (
    MatchAny,
    MatchCriteria,
    Profile,
    ProfileModeConfig,
)
from hefesto_dualsense4unix.testing import FakeController
from hefesto_dualsense4unix.utils import session, xdg_paths

_SALVAR_EMULACAO_REAL = session.save_gamepad_emulation
_PREFERENCIA_REAL = session.load_gamepad_preference

APPID = 4235410
JOGO = "Future Knight"
DELA = "Desktop Dela"
FREESTYLE = loader.NOME_DO_PADRAO


class _Vpad:
    """O pad de mentira: publica o que a fábrica real publica."""

    def __init__(self, mascara: str, identity: str | None, caminho: str | None) -> None:
        self.flavor = mascara
        self.identity = identity
        self.backend = "uhid" if vp.quer_uhid(caminho, mascara) else "uinput"
        vp._pendurar_o_caminho(self, vp.caminho_resolvido(caminho, mascara))
        self.parado = False

    def stop(self) -> None:
        self.parado = True


@pytest.fixture
def _lar(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> Iterator[list[str]]:
    """O lar de mentira, a borda do pad dublada, e o diário da ordem do boot."""
    for var, sub in (("XDG_CONFIG_HOME", "config"), ("XDG_STATE_HOME", "state")):
        monkeypatch.setenv(var, str(tmp_path / sub))
    casa = xdg_paths.config_dir(ensure=True)
    if not str(casa).startswith(str(tmp_path)):
        pytest.exit(f"a régua ia ler o config_dir de verdade: {casa}", returncode=3)
    monkeypatch.setattr(session, "load_gamepad_preference", _PREFERENCIA_REAL)
    _SALVAR_EMULACAO_REAL(True, "dualsense")
    ordem: list[str] = []

    def _fabrica(flavor: Any, *, identity: Any = None, caminho: Any = None, **_kw: Any) -> _Vpad:
        ordem.append("pad")
        return _Vpad(em.mascara_efetiva(identity, flavor), identity, caminho)

    monkeypatch.setattr(vp, "make_virtual_pad", _fabrica)
    for nome, valor in {
        "_set_controller_grab": lambda d, g: None,
        "_materialize_launch_env": lambda d: None,
        "start_motion_reader": lambda d, dev: None,
        "read_primary_calibration": lambda d: None,
        "make_primary_rumble_sink": lambda d: None,
        "make_primary_replica_sinks": lambda d: {},
        "controller_allows_uhid": lambda d: True,
        "vpad_vivo": lambda dev: True,
        "_deve_promover_backend": lambda *a, **k: False,
    }.items():
        monkeypatch.setattr(gp, nome, valor)
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.launch_env.materialize_launch_env", lambda daemon: None
    )
    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.steam_launch_options.steam_game_running_appid",
        lambda *a, **k: None,
    )
    sincronizar = lifecycle.Daemon._sync_game_signal

    async def _sincroniza_e_anota(self: Any) -> None:
        ordem.append("sinal")
        await sincronizar(self)

    monkeypatch.setattr(lifecycle.Daemon, "_sync_game_signal", _sincroniza_e_anota)
    em._zerar_registro_de_mascaras()
    yield ordem
    em._zerar_registro_de_mascaras()


def _o_disco(caso: str) -> str:
    """O disco do caso; devolve o perfil que o boot tem de abrir."""
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
    session.save_freestyle_ligado(caso == "freestyle-ligado")
    if caso != "sem-jogo":
        appid = 999999 if caso == "jogo-sem-perfil" else APPID
        pasta = xdg_paths.launch_env_dir(ensure=True)
        (pasta / "last_run").write_text(
            f"appid={appid}\nepoch={int(time.time()) - 300}\npid={os.getpid()}\n",
            encoding="utf-8")
    return {"jogo-com-perfil": JOGO, "freestyle-ligado": FREESTYLE}.get(caso, DELA)


def _config() -> lifecycle.DaemonConfig:
    return lifecycle.DaemonConfig(  # type: ignore[arg-type]
        poll_hz=200, auto_reconnect=False, ipc_enabled=False, udp_enabled=False,
        autoswitch_enabled=False, mouse_emulation_enabled=False,
        keyboard_emulation_enabled=False, ps_button_action="none",
        mic_button_toggles_system=False,
    )


async def _o_reinicio(nome: str) -> lifecycle.Daemon:
    """O `Daemon` REAL até o restauro, e o tique do autoswitch que chega depois."""
    from hefesto_dualsense4unix.profiles.manager import gerente_do_daemon

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
        if not session.load_freestyle_ligado():
            jogo_na_janela = JOGO if nome == JOGO else nome
            gerente_do_daemon(daemon, store=store).activate(jogo_na_janela, origin="autoswitch")
    finally:
        daemon.stop()
        await corrida
    return daemon


CASOS = {
    "jogo-com-perfil": "xbox",
    "freestyle-ligado": "dualsense",
    "jogo-sem-perfil": "dualsense",
    "sem-jogo": "dualsense",
}


@pytest.mark.parametrize("caso", sorted(CASOS))
def test_o_reinicio_nasce_no_modo_do_jogo_em_cena(caso: str, _lar: list[str]) -> None:
    """O pad do P1 nasce UMA vez, no modo do perfil que o boot abre, e a trava não segura nada.

    - `jogo-com-perfil`: o Future Knight em cena → o pad em Xbox, o perfil dele
      ativo (`origin="system"`), e o tique do autoswitch acha o modo já certo;
    - `freestyle-ligado`: o Freestyle manda, e o modo é o dele;
    - `jogo-sem-perfil` e `sem-jogo`: a escolha do usuário (a da O-HEFESTO-ABRE).

    MORDIDA: tire o jogo em cena do `connection._o_nome_que_o_boot_restaura`
    (o `if appid_em_cena is not None:`) e o caso `jogo-com-perfil` nasce
    DualSense, com o contador da trava em 1.
    """
    nome = _o_disco(caso)

    daemon = asyncio.run(_o_reinicio(nome))

    pads = [x for x in _lar if x == "pad"]
    assert len(pads) == 1, f"o pad do P1 nasceu {len(pads)} vezes"
    assert gp.caminho_da_sessao(daemon) == CASOS[caso], (
        f"o pad nasceu em {gp.caminho_da_sessao(daemon)!r}, e o perfil {nome!r} pede "
        f"{CASOS[caso]!r}")
    assert daemon.store.counter("gamepad.recreate.blocked_by_game") == 0, (
        "a trava segurou a troca: o pad nasceu num modo que ninguém escolheu para o jogo")


def test_o_sinal_e_avaliado_antes_do_primeiro_pad(_lar: list[str]) -> None:
    """No boot, a primeira avaliação do sinal de jogo vem antes da criação do pad do P1."""
    nome = _o_disco("jogo-com-perfil")

    asyncio.run(_o_reinicio(nome))

    assert "sinal" in _lar and "pad" in _lar
    assert _lar.index("sinal") < _lar.index("pad"), f"a ordem do boot foi {_lar[:4]}"


def test_o_jogo_em_cena_nao_vira_a_escolha_dela(_lar: list[str]) -> None:
    """Depois do reinício no jogo, a escolha do usuário segue no terceiro perfil."""
    nome = _o_disco("jogo-com-perfil")

    asyncio.run(_o_reinicio(nome))

    assert session.load_last_profile() == DELA
    assert session.load_freestyle_ligado() is False
