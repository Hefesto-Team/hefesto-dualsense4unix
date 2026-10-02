"""VERDADE-01 — o retorno que mentia, e o laço que ele alimentava (18→19/08)."""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon import lifecycle as lifecycle_mod
from hefesto_dualsense4unix.daemon.lifecycle import (
    ADIADO_JOGO_ABERTO,
    APLICADO,
    Daemon,
    DaemonConfig,
)
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gamepad_mod
from hefesto_dualsense4unix.daemon.subsystems.gamepad import (
    EMU_APLICADO,
    EMU_BLOQUEADO_POR_JOGO,
    EMU_JA_ESTAVA,
    start_gamepad_emulation,
    start_gamepad_emulation_desfecho,
)
from hefesto_dualsense4unix.profiles.schema import Profile, ProfileModeConfig
from hefesto_dualsense4unix.testing import FakeController


class _FakePad:
    """Vpad de mentira, VIVO (sem `_started` False) — ver `vpad_vivo`."""

    backend = "uhid"

    def __init__(self, flavor: str) -> None:
        self.flavor = flavor
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True


@pytest.fixture()
def daemon(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Daemon real com a fábrica de vpad e o disco dublados."""
    monkeypatch.setattr(
        "hefesto_dualsense4unix.utils.session.save_gamepad_emulation",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.launch_env.materialize_launch_env",
        lambda _daemon: None,
    )
    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.virtual_pad.make_virtual_pad",
        lambda flavor, **_kw: _FakePad(str(flavor)),
    )
    monkeypatch.setattr(gamepad_mod, "_set_controller_grab", lambda *_a: None)
    d = Daemon(
        controller=FakeController(transport="usb"),
        config=DaemonConfig(ipc_enabled=False, udp_enabled=False),
    )
    d._coop_manager = SimpleNamespace(
        sync=lambda **_k: None, disable=lambda: None, player_count=lambda: 1
    )
    return d


def _autoridade(daemon: Any, valor: str) -> None:
    """NUMA-01: a autoridade de exibição vem do `GameSignal` (fiado em `run()`)."""
    daemon._game_signal = SimpleNamespace(authority=valor)


def _perfil(flavor: str, *, nome: str = "dont_scream") -> Profile:
    return Profile.model_validate(
        {
            "name": nome,
            "version": 1,
            "match": {"type": "criteria", "window_class": ["steam_app_2497900"]},
            "priority": 80,
            "mode": {"kind": "gamepad", "gamepad_flavor": flavor},
        }
    )


def test_os_tres_desfechos_sao_distinguiveis(daemon: Any) -> None:
    _autoridade(daemon, "daemon")
    assert (
        start_gamepad_emulation_desfecho(daemon, "dualsense", origin="profile")
        == EMU_APLICADO
    )
    assert (
        start_gamepad_emulation_desfecho(daemon, "dualsense", origin="profile")
        == EMU_JA_ESTAVA
    )

    _autoridade(daemon, "game")
    assert (
        start_gamepad_emulation_desfecho(daemon, "xbox", origin="profile")
        == EMU_BLOQUEADO_POR_JOGO
    ), "o gate R-04 recusou a troca — e agora isso TEM nome"
    assert daemon._gamepad_device.flavor == "dualsense", (
        "bloqueado é bloqueado: a máscara vigente não pode ter mudado"
    )


def test_o_bool_continua_dizendo_ativo_ao_final_nos_tres(daemon: Any) -> None:
    """Por que a mentira passava: o bool é o MESMO nos três desfechos."""
    _autoridade(daemon, "daemon")
    assert start_gamepad_emulation(daemon, "dualsense", origin="profile") is True
    assert start_gamepad_emulation(daemon, "dualsense", origin="profile") is True
    _autoridade(daemon, "game")
    assert start_gamepad_emulation(daemon, "xbox", origin="profile") is True


def test_o_applier_diz_adiado_e_nao_repete_o_pedido(
    daemon: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A cura da noite: bloqueio vira ESTADO, não retry."""
    _autoridade(daemon, "daemon")
    start_gamepad_emulation(daemon, "dualsense", origin="profile")
    device = daemon._gamepad_device
    _autoridade(daemon, "game")

    pedidos: list[str | None] = []
    real = daemon.set_gamepad_emulation_desfecho

    def espiao(enabled: bool, flavor: str | None = None, **kw: Any) -> str:
        pedidos.append(flavor)
        return real(enabled, flavor, **kw)

    monkeypatch.setattr(daemon, "set_gamepad_emulation_desfecho", espiao)

    perfil = _perfil("xbox")
    estados = [
        daemon.apply_profile_mode(perfil.mode, profile=perfil, origin="autoswitch")
        for _ in range(5)
    ]

    assert estados == [ADIADO_JOGO_ABERTO] * 5, (
        "o applier não pode dizer 'aplicado' sobre uma troca recusada"
    )
    assert pedidos == ["xbox"], (
        "o pedido recusado foi repetido — é este o laço que matou o controle "
        f"dela no meio da partida (pedidos={pedidos})"
    )
    assert daemon._gamepad_device is device and device.stopped is False, (
        "o vpad do jogo foi destruído/recriado"
    )
    assert daemon._mascara_adiada_por_jogo is not None
    assert daemon._mascara_adiada_por_jogo.flavor == "xbox"


def test_o_pingue_pongue_de_duas_janelas_tambem_para(
    daemon: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Duas janelas se revezando pediam máscaras OPOSTAS a cada volta."""
    _autoridade(daemon, "daemon")
    start_gamepad_emulation(daemon, "dualsense", origin="profile")
    _autoridade(daemon, "game")

    pedidos: list[str | None] = []
    real = daemon.set_gamepad_emulation_desfecho

    def espiao(enabled: bool, flavor: str | None = None, **kw: Any) -> str:
        pedidos.append(flavor)
        return real(enabled, flavor, **kw)

    monkeypatch.setattr(daemon, "set_gamepad_emulation_desfecho", espiao)

    for flavor in ("xbox", "dualsense", "xbox", "dualsense"):
        perfil = _perfil(flavor, nome=f"janela_{flavor}")
        daemon.apply_profile_mode(perfil.mode, profile=perfil, origin="autoswitch")

    assert pedidos == ["xbox"], f"o revezamento voltou a pedir (pedidos={pedidos})"


def test_o_journal_diz_uma_vez_por_episodio(
    daemon: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`vpad_recriacao_bloqueada_por_jogo` é fato, não batimento cardíaco."""
    _autoridade(daemon, "daemon")
    start_gamepad_emulation(daemon, "dualsense", origin="profile")
    _autoridade(daemon, "game")

    avisos: list[str] = []
    espiao = SimpleNamespace(
        warning=lambda evento, **_kw: avisos.append(evento),
        info=lambda *_a, **_kw: None,
        debug=lambda *_a, **_kw: None,
    )
    monkeypatch.setattr(gamepad_mod, "logger", espiao)

    for _ in range(4):
        assert (
            start_gamepad_emulation_desfecho(daemon, "xbox", origin="profile")
            == EMU_BLOQUEADO_POR_JOGO
        )

    assert avisos.count("vpad_recriacao_bloqueada_por_jogo") == 1, (
        "o gate gritou a cada volta — foi assim que o journal dela virou muro "
        f"(avisos={avisos})"
    )
    _autoridade(daemon, "daemon")
    assert gamepad_mod._recriacao_bloqueada_por_jogo(
        daemon, origin="profile", motivo="teste"
    ) is False
    _autoridade(daemon, "game")
    assert gamepad_mod._recriacao_bloqueada_por_jogo(
        daemon, origin="profile", motivo="teste"
    ) is True
    assert avisos.count("vpad_recriacao_bloqueada_por_jogo") == 2


def test_quando_o_jogo_devolve_a_autoridade_a_mascara_entra(daemon: Any) -> None:
    _autoridade(daemon, "daemon")
    start_gamepad_emulation(daemon, "dualsense", origin="profile")
    _autoridade(daemon, "game")
    perfil = _perfil("xbox")

    assert (
        daemon.apply_profile_mode(perfil.mode, profile=perfil, origin="autoswitch")
        == ADIADO_JOGO_ABERTO
    )

    _autoridade(daemon, "daemon")
    assert (
        daemon.apply_profile_mode(perfil.mode, profile=perfil, origin="autoswitch")
        == APLICADO
    )
    assert daemon._gamepad_device.flavor == "xbox"
    assert daemon._mascara_adiada_por_jogo is None


def test_gesto_manual_na_mascara_esquece_a_divergencia(daemon: Any) -> None:
    """A palavra dela é mais nova que a de qualquer perfil (R-02/C6)."""
    _autoridade(daemon, "daemon")
    start_gamepad_emulation(daemon, "dualsense", origin="profile")
    _autoridade(daemon, "game")
    perfil = _perfil("xbox")
    daemon.apply_profile_mode(perfil.mode, profile=perfil, origin="autoswitch")
    assert daemon._mascara_adiada_por_jogo is not None

    daemon.set_gamepad_emulation(True, "dualsense", origin="manual")

    assert daemon._mascara_adiada_por_jogo is None


def test_ela_ativando_o_perfil_na_mao_troca_a_mascara_com_jogo_aberto(
    daemon: Any,
) -> None:
    """`origin="manual"` na ativação = `profile.switch` da GUI/applet ou o
    PS+D-pad no controle — nas rotas de ativação NADA MAIS usa essa origem
    (autoswitch, launch, sinal de jogo e dreno têm as suas). É vontade
    explícita da usuária, e o gate R-04 sempre disse que a última palavra é
    dela."""
    _autoridade(daemon, "daemon")
    start_gamepad_emulation(daemon, "dualsense", origin="profile")
    _autoridade(daemon, "game")
    perfil = _perfil("xbox")

    estado = daemon.apply_profile_mode(perfil.mode, profile=perfil, origin="manual")

    assert estado == APLICADO
    assert daemon._gamepad_device.flavor == "xbox"


def test_o_gesto_de_perfil_nao_grava_preferencia_nem_promove_backend(
    monkeypatch: pytest.MonkeyPatch, daemon: Any
) -> None:
    """`gesto_de_perfil` é "profile" em TUDO, menos no gate R-04."""
    gravou: list[Any] = []
    monkeypatch.setattr(
        "hefesto_dualsense4unix.utils.session.save_gamepad_emulation",
        lambda *a, **k: gravou.append(a),
    )
    _autoridade(daemon, "daemon")
    start_gamepad_emulation(daemon, "dualsense", origin="profile")
    _autoridade(daemon, "game")
    perfil = _perfil("xbox")

    daemon.apply_profile_mode(perfil.mode, profile=perfil, origin="manual")

    assert gravou == [], "a máscara do perfil não é a preferência dela"
    assert "gesto_de_perfil" in gamepad_mod.ORIGENS_GESTO_DELA
    assert gamepad_mod._deve_promover_backend(
        daemon, _FakePad("dualsense"), "dualsense", "gesto_de_perfil"
    ) is False


def test_o_gate_r04_continua_barrando_o_caminho_automatico(daemon: Any) -> None:
    _autoridade(daemon, "game")
    start_gamepad_emulation(daemon, "dualsense", origin="profile")
    device = daemon._gamepad_device

    for origem in ("profile", "hotplug", "autoswitch"):
        assert (
            gamepad_mod._recriacao_bloqueada_por_jogo(
                daemon, origin=origem, motivo="teste"
            )
            is True
        )
    assert daemon._gamepad_device is device


def test_modo_jogo_padrao_nao_vira_laco_com_a_mascara_divergente(
    daemon: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """MODO-01/B3 pede o modo a 2 Hz enquanto o jogo está na frente."""
    _autoridade(daemon, "daemon")
    start_gamepad_emulation(daemon, "dualsense", origin="profile")
    _autoridade(daemon, "game")
    daemon.config.gamepad_flavor = "xbox"

    pedidos: list[str | None] = []
    real = daemon.set_gamepad_emulation_desfecho

    def espiao(enabled: bool, flavor: str | None = None, **kw: Any) -> str:
        pedidos.append(flavor)
        return real(enabled, flavor, **kw)

    monkeypatch.setattr(daemon, "set_gamepad_emulation_desfecho", espiao)

    for _ in range(6):
        daemon.aplicar_modo_jogo_padrao(wm_class="steam_app_2497900")

    assert pedidos == ["xbox"], f"o tique de 2 Hz voltou a pedir (pedidos={pedidos})"


def test_o_dublê_de_modo_sem_flavor_nao_mexe_na_mascara(daemon: Any) -> None:
    """Perfil `kind="gamepad"` sem `gamepad_flavor` é ausência de opinião sobre"""
    _autoridade(daemon, "daemon")
    start_gamepad_emulation(daemon, "dualsense", origin="profile")
    _autoridade(daemon, "game")
    device = daemon._gamepad_device

    estado = daemon.apply_profile_mode(
        ProfileModeConfig(kind="gamepad", gamepad_flavor=None), origin="autoswitch"
    )

    assert estado == APLICADO
    assert daemon._gamepad_device is device
    assert daemon._mascara_adiada_por_jogo is None


def test_o_vocabulario_do_applier_e_o_mesmo_da_casa() -> None:
    """R-03: o retorno dos appliers é string, e o novo estado entra nele."""
    assert lifecycle_mod.ADIADO_JOGO_ABERTO == "adiado_jogo_aberto"
    assert lifecycle_mod.APLICADO == "aplicado"
