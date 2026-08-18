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
"""
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture()
def isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isola config_dir (session.json + active_profile.txt) em tmp_path.

    Cópia deliberada do fixture de `test_session_persist.py`: são dois patches
    porque `utils.session` alcança o `config_dir` por dois caminhos (o import do
    topo, usado por `_session_path`, e o import lazy das funções do marker).
    """
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
    """Grava o perfil `Sackboy` COMO ELE ESTÁ na máquina dela (08/08 01:49).

    O `window_class` é o que torna o perfil escopado a janela — é ele que faz
    `restore_last_profile` desistir. `steam_app_1599660` é o Sackboy na Steam.
    """
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
async def test_boot_adia_perfil_de_janela_e_diz_que_adiou(
    isolated_config: Path, isolated_profiles: Path
) -> None:
    """O caso dela, fim a fim: o perfil não entra — e o estado explica por quê.

    O `active_profile is None` é o desenho de 22/07 e continua valendo (esta
    cura NÃO força o restore). O que muda é o campo ao lado: agora existe onde
    ler que o perfil ADIADO é o `Sackboy`, esperando a janela do jogo.
    """
    from hefesto_dualsense4unix.daemon.connection import restore_last_profile
    from hefesto_dualsense4unix.daemon.state_store import StateStore
    from hefesto_dualsense4unix.testing import FakeController
    from hefesto_dualsense4unix.utils.session import (
        save_active_marker,
        save_last_profile,
    )

    _salvar_sackboy_dela()
    # Os DOIS arquivos apontam `Sackboy` — é o disco dela, medido: session.json
    # `{"last_profile": "Sackboy"}` e active_profile.txt `Sackboy` (convergem,
    # então o seed de migração do marker não entra em cena aqui).
    save_last_profile("Sackboy")
    save_active_marker("Sackboy")

    fc = FakeController()
    fc.connect()
    store = StateStore()
    daemon = _BootDaemon(controller=fc, store=store)
    await restore_last_profile(daemon)  # type: ignore[arg-type]

    # O desenho, intacto: nada foi ativado no boot.
    assert store.active_profile is None
    # A cura: a espera é LEGÍVEL, em vez de morrer no journal.
    assert store.perfil_adiado_por_janela == "Sackboy"


@pytest.mark.asyncio
async def test_boot_sem_perfil_nenhum_nao_inventa_espera(
    isolated_config: Path, isolated_profiles: Path
) -> None:
    """O contraste que dá sentido ao campo — e a mordida de verdade.

    Instalação sem session.json e sem marker: `active_profile` é `None` pelo
    motivo BANAL (não há perfil nenhum). Um campo que respondesse "Sackboy"
    sempre — ou que ficasse preso do boot anterior — passaria no teste de cima e
    reprovaria aqui. É este par que faz os dois `None` deixarem de ser a mesma
    palavra.
    """
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
    """A espera TERMINA quando o perfil entra — por qualquer porta.

    Encena o que o journal dela mostra acontecendo de verdade: o boot adia, ela
    abre o Sackboy e o autoswitch ativa o perfil (`profile_autoswitch
    to=Sackboy wm_class=steam_app_1599660`, 16 vezes em 08/08). A dica não pode
    sobreviver a isso: mostrar "esperando a janela" com o perfil já ativo seria
    trocar uma mentira por outra.

    `origin="autoswitch"` de propósito — é a porta pela qual o perfil realmente
    volta na máquina dela, e a que NÃO regrava a intenção manual (PERFIL-03).
    """
    from hefesto_dualsense4unix.daemon.connection import restore_last_profile
    from hefesto_dualsense4unix.daemon.state_store import StateStore
    from hefesto_dualsense4unix.profiles.manager import ProfileManager
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
    assert store.perfil_adiado_por_janela == "Sackboy"

    # A janela do jogo apareceu: o autoswitch ativa o perfil.
    ProfileManager(controller=fc, store=store).activate(
        "Sackboy", origin="autoswitch"
    )

    assert store.active_profile == "Sackboy"
    assert store.perfil_adiado_por_janela is None
