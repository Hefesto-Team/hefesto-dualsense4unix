"""MODO-JOGO-VONTADE-DELA-01 (09/08/2026) — a junta entre a janela e o daemon."""
from __future__ import annotations

from pathlib import Path

import pytest

from hefesto_dualsense4unix.app.draft_config import DraftConfig
from hefesto_dualsense4unix.daemon.lifecycle import (
    APLICADO,
    IGNORADO_CATCH_ALL,
    Daemon,
    DaemonConfig,
)
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.loader import save_profile
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import (
    LedsConfig,
    MatchAny,
    MatchCriteria,
    Profile,
)
from hefesto_dualsense4unix.testing import FakeController


@pytest.fixture
def perfis_isolados(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Diretório de perfis em ``tmp_path`` (CANÁRIO-FS-01)."""
    alvo = tmp_path / "profiles"
    alvo.mkdir()

    def fake_profiles_dir(ensure: bool = False) -> Path:
        if ensure:
            alvo.mkdir(parents=True, exist_ok=True)
        return alvo

    monkeypatch.setattr(loader_module, "profiles_dir", fake_profiles_dir)
    return alvo


@pytest.fixture(autouse=True)
def _sem_notificacao(monkeypatch: pytest.MonkeyPatch) -> None:
    """BUG-TEST-DBUS-NOTIFY-NONHERMETIC-01: ``set_emulation_suppressed``"""
    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.desktop_notifications."
        "notify_emulation_suppressed",
        lambda _estado: None,
    )


def _perfil_de_origem(nome: str, *, catch_all: bool) -> Profile:
    """O perfil que a janela ABRIU (ainda sem o modo jogo)."""
    return Profile(
        name=nome,
        match=MatchAny() if catch_all else MatchCriteria(window_class=[f"{nome}_cls"]),
        priority=0 if catch_all else 10,
        leds=LedsConfig(lightbar=(10, 20, 30)),
    )


def o_que_a_janela_salva(nome: str, *, catch_all: bool) -> Profile:
    """O arquivo que nasce do gesto dela: abrir o perfil, ligar o modo jogo, salvar."""
    draft = DraftConfig.from_profile(_perfil_de_origem(nome, catch_all=catch_all))
    return draft.with_suppress(True).to_profile(nome)


def _daemon() -> Daemon:
    return Daemon(controller=FakeController(), config=DaemonConfig())


def _bancada(perfis: list[Profile], daemon: Daemon) -> tuple[ProfileManager, StateStore]:
    """``ProfileManager`` real com o applier REAL do daemon injetado."""
    for perfil in perfis:
        save_profile(perfil)
    fc = FakeController()
    fc.connect()
    store = StateStore()
    manager = ProfileManager(
        controller=fc,
        store=store,
        suppression_applier=daemon.apply_profile_suppression,
    )
    return manager, store


def test_o_gesto_dela_num_catch_all_chega_ao_arquivo() -> None:
    """O arquivo que este portão vai ativar existe — e é catch-all mesmo."""
    salvo = o_que_a_janela_salva("vitoria", catch_all=True)

    assert salvo.e_catch_all is True
    assert salvo.suppress_desktop_emulation is True


def test_o_catch_all_que_ela_salvou_nao_suspende_na_ativacao(
    perfis_isolados: Path,
) -> None:
    """MORDIDA: o alçapão continua fechado no caminho de ativação INTEIRO."""
    daemon = _daemon()
    manager, _store = _bancada(
        [o_que_a_janela_salva("vitoria", catch_all=True)], daemon
    )

    relatorio: dict[str, str] = {}
    manager.activate("vitoria", origin="autoswitch", relatorio=relatorio)

    assert relatorio["suppression"] == IGNORADO_CATCH_ALL
    assert daemon._emulation_suppressed is False
    assert daemon._suppress_from_profile is False


def test_o_restauro_do_boot_nao_acorda_com_mouse_e_teclado_suspensos(
    perfis_isolados: Path,
) -> None:
    """MORDIDA, no caminho que mais dói: o restauro do último perfil no boot."""
    daemon = _daemon()
    manager, _store = _bancada(
        [o_que_a_janela_salva("vitoria", catch_all=True)], daemon
    )

    manager.activate("vitoria", origin="system")

    assert daemon._emulation_suppressed is False


def test_o_perfil_com_regra_continua_ligando_o_modo_jogo(
    perfis_isolados: Path,
) -> None:
    """GUARDA: o gate é sobre AUSÊNCIA de regra, não sobre o modo jogo."""
    daemon = _daemon()
    manager, _store = _bancada(
        [o_que_a_janela_salva("sackboy", catch_all=False)], daemon
    )

    relatorio: dict[str, str] = {}
    manager.activate("sackboy", origin="autoswitch", relatorio=relatorio)

    assert relatorio["suppression"] == APLICADO
    assert daemon._emulation_suppressed is True
    assert daemon._suppress_from_profile is True


def test_ela_continua_podendo_sair_do_modo_jogo_pela_janela(
    perfis_isolados: Path,
) -> None:
    """GUARDA: o botão "Sair do modo jogo" é a saída, e ele não passa por perfil."""
    daemon = _daemon()
    manager, _store = _bancada(
        [o_que_a_janela_salva("sackboy", catch_all=False)], daemon
    )
    manager.activate("sackboy", origin="autoswitch")
    assert daemon._emulation_suppressed is True

    daemon.set_emulation_suppressed(False)

    assert daemon._emulation_suppressed is False
    assert daemon._suppress_from_profile is False
