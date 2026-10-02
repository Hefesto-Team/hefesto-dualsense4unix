"""O boot que adia o perfil de janela tem de DIZER que adiou.

PERFIL-ADIADO-POR-JANELA-01 (09/08/2026).

O defeito medido na máquina dela: depois de reiniciar o daemon,
`daemon.state_full` respondia `active_profile: None` com os dois DualSense na
mesa e o perfil `Sackboy` — o dela — válido em disco. Um `profile.switch`
manual o aplicava na hora, então o perfil nunca esteve quebrado: ele só não
voltava sozinho.

A causa é DESENHO, e o desenho está certo: `restore_last_profile`
(`daemon/connection.py`) recusa restaurar perfil escopado a janela
(RESTORE-ESCOPO-01, 22/07) porque ele pertence ao autoswitch, que o ativa
quando a janela existir — e na máquina dela isso de fato acontece (o journal de
08/08 tem 16 `profile_autoswitch to=Sackboy wm_class=steam_app_1599660`).
Forçar o restore reabriria o defeito que aquela sprint fechou: perfil de jogo
pintando a lightbar e suprimindo a paleta automática com o jogo fechado.

O que era defeito é OUTRA coisa: a recusa vivia só no journal
(`last_profile_restore_pulado_perfil_de_janela`, 30+ ocorrências desde 31/07) e
o estado público respondia `None` — a MESMA palavra que usa para "não há perfil
nenhum". A janela não tinha como contar a diferença, e a leitura que sobrava
para ela era "o Hefesto perdeu o meu perfil".

Estes testes fixam as três coisas que passam a ser distinguíveis, e a nº 3 é a
que dá sentido às outras duas: sem ela, um campo que responde sempre o mesmo
"Sackboy" passaria igual.

NOTA DATADA — 01/10/2026 (`D-2909-O-HEFESTO-ABRE-NA-ESCOLHA-DELA`, item 4):
a RESTORE-ESCOPO-01 caducou para a escolha dela. O boot restaura o perfil que
ela ativou à mão, com regra de janela ou sem: medido no diário de 28 e 29/09,
seis boots com a sessão num perfil de jogo, e nenhum abriu nele — o Freestyle
entrava no lugar. Nada mais espera a janela no boot, e o campo
`perfil_adiado_por_janela` ficou sem escritor (o `state_store` não é desta
sprint; a saída dele está no relato). A régua do caso dela vira a do boot que
abre no Sackboy; a do contraste e a do campo que se limpa ficam.
"""
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture()
def isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isola config_dir (session.json + active_profile.txt) em tmp_path."""
    config = tmp_path / "config"
    config.mkdir()

    def fake_config_dir(ensure: bool = False) -> Path:
        if ensure:
            config.mkdir(parents=True, exist_ok=True)
        return config

    monkeypatch.setattr(
        "hefesto_dualsense4unix.utils.session.config_dir", fake_config_dir
    )
    from hefesto_dualsense4unix.utils import xdg_paths

    monkeypatch.setattr(xdg_paths, "config_dir", fake_config_dir)
    return config


@pytest.fixture()
def isolated_profiles(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isola profiles_dir em tmp_path (padrão dos testes de loader)."""
    from hefesto_dualsense4unix.profiles import loader as loader_module

    profiles = tmp_path / "profiles"
    profiles.mkdir()

    def fake_profiles_dir(ensure: bool = False) -> Path:
        if ensure:
            profiles.mkdir(parents=True, exist_ok=True)
        return profiles

    monkeypatch.setattr(loader_module, "profiles_dir", fake_profiles_dir)
    return profiles


class _BootDaemon:
    """Daemon mínimo para `restore_last_profile` (executor inline)."""

    def __init__(self, controller: object, store: object) -> None:
        self.controller = controller
        self.store = store
        self._native_mode = False
        self._keyboard_device = None

    async def _run_blocking(self, fn: object, *args: object) -> object:
        return fn(*args)  # type: ignore[operator]


def _salvar_sackboy_dela() -> None:
    """Grava o perfil `Sackboy` COMO ELE ESTÁ na máquina dela (08/08 01:49)."""
    from hefesto_dualsense4unix.profiles.loader import save_profile
    from hefesto_dualsense4unix.profiles.schema import MatchCriteria, Profile

    save_profile(
        Profile(
            name="Sackboy",
            match=MatchCriteria(window_class=["steam_app_1599660"]),
            priority=200,
        )
    )


@pytest.mark.asyncio
async def test_boot_restaura_o_perfil_de_janela_que_ela_escolheu(
    isolated_config: Path, isolated_profiles: Path
) -> None:
    """O caso dela, fim a fim: o Sackboy que ela ativou à mão volta no boot."""
    from hefesto_dualsense4unix.daemon.connection import restore_last_profile
    from hefesto_dualsense4unix.daemon.state_store import StateStore
    from hefesto_dualsense4unix.testing import FakeController
    from hefesto_dualsense4unix.utils.session import (
        save_active_marker,
        save_last_profile,
    )

    _salvar_sackboy_dela()
    save_last_profile("Sackboy")
    save_active_marker("Sackboy")

    fc = FakeController()
    fc.connect()
    store = StateStore()
    daemon = _BootDaemon(controller=fc, store=store)
    await restore_last_profile(daemon)  # type: ignore[arg-type]

    assert store.active_profile == "Sackboy"
    assert store.perfil_adiado_por_janela is None


@pytest.mark.asyncio
async def test_boot_sem_perfil_nenhum_nao_inventa_espera(
    isolated_config: Path, isolated_profiles: Path
) -> None:
    """O contraste que dá sentido ao campo — e a mordida de verdade."""
    from hefesto_dualsense4unix.daemon.connection import restore_last_profile
    from hefesto_dualsense4unix.daemon.state_store import StateStore
    from hefesto_dualsense4unix.testing import FakeController

    fc = FakeController()
    fc.connect()
    store = StateStore()
    daemon = _BootDaemon(controller=fc, store=store)
    await restore_last_profile(daemon)  # type: ignore[arg-type]

    assert store.active_profile is None
    assert store.perfil_adiado_por_janela is None


@pytest.mark.asyncio
async def test_abrir_o_jogo_encerra_a_espera(
    isolated_config: Path, isolated_profiles: Path
) -> None:
    """A espera TERMINA quando o perfil entra — por qualquer porta."""
    from hefesto_dualsense4unix.daemon.state_store import StateStore
    from hefesto_dualsense4unix.profiles.manager import ProfileManager
    from hefesto_dualsense4unix.testing import FakeController

    _salvar_sackboy_dela()

    fc = FakeController()
    fc.connect()
    store = StateStore()
    store.set_perfil_adiado_por_janela("Sackboy")
    assert store.perfil_adiado_por_janela == "Sackboy"

    ProfileManager(controller=fc, store=store).activate(
        "Sackboy", origin="autoswitch"
    )

    assert store.active_profile == "Sackboy"
    assert store.perfil_adiado_por_janela is None
