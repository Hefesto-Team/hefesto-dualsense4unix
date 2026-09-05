"""PERFIL-PADRAO-PERSONALIZADO-01, metade B — abrir no ÚLTIMO perfil ativado.

Palavra dela, 05/09/2026: *"ao abrir o programa ele deve iniciar com o ultimo
perfil ativado. **ate eu alterar novamente e ativar outro perfil**"*.

MEDIDO ANTES DE CONSTRUIR, e o veredito é que **já funciona** — o item B não
pediu código, pediu prova. A prova ao vivo, no daemon dela, em 05/09 às 02:05:

    02:05:00  profile_activated      name=fallback   origin=manual  priority=0
    02:05:03  Stopped/Started hefesto-dualsense4unix.service
    02:05:04  profile_activated      name=fallback   origin=system  priority=0
    02:05:04  last_profile_restored  name=fallback
    02:05:21  profile_activated      name=meu_perfil origin=manual  priority=1
    02:05:23  Stopped/Started hefesto-dualsense4unix.service
    02:05:25  last_profile_restored  name=meu_perfil

O que este arquivo acrescenta é a régua que faltava: a suíte já cobria UM
gesto manual sobrevivendo ao autoswitch (`test_session_persist.py`), mas **não
cobria o segundo gesto** — que é a metade da frase dela que diz "até eu alterar
novamente". E é a metade com defeito possível: `resolve_boot_profile` dá a
VITÓRIA AO MARKER quando os dois arquivos divergem, então um caminho que
gravasse só o `session.json` na segunda ativação faria o boot voltar no perfil
ANTERIOR — com todos os testes de hoje verdes.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from hefesto_dualsense4unix.utils.session import (
    load_last_profile,
    read_active_marker,
    resolve_boot_profile,
    save_active_marker,
)


@pytest.fixture()
def lar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Config e perfis num lar de mentira — nada toca o disco de ninguém."""
    from hefesto_dualsense4unix.profiles import loader as loader_module
    from hefesto_dualsense4unix.utils import session, xdg_paths

    config = tmp_path / "config"
    config.mkdir()
    perfis = tmp_path / "profiles"
    perfis.mkdir()
    monkeypatch.setattr(xdg_paths, "config_dir", lambda ensure=False: config)
    monkeypatch.setattr(session, "config_dir", lambda ensure=False: config)
    monkeypatch.setattr(
        loader_module, "profiles_dir", lambda ensure=False: perfis
    )
    monkeypatch.setattr(
        xdg_paths, "profiles_dir", lambda ensure=False: perfis
    )
    # A semeadura não pode despejar os presets do repositório aqui dentro.
    monkeypatch.setattr(loader_module, "_seed_attempted", True)
    return tmp_path


class _DaemonDeBoot:
    """O mínimo que `restore_last_profile` consome, com executor inline."""

    def __init__(self, controller: object, store: object) -> None:
        self.controller = controller
        self.store = store
        self._native_mode = False
        self._keyboard_device = None

    async def _run_blocking(self, fn: object, *args: object) -> object:
        return fn(*args)  # type: ignore[operator]


def _ativa_na_mao(manager: object, nome: str) -> None:
    """O gesto dela, com os DOIS escritores que o produto usa.

    O `profile.switch` do IPC (`daemon/ipc_handlers.py`) e o ciclo por hotkey
    (`daemon/subsystems/hotkey.py`) fazem exatamente estes dois passos, nesta
    ordem: `activate(origin="manual")` grava o `session.json`, e o
    `save_active_marker` grava o `active_profile.txt`.
    """
    manager.activate(nome, origin="manual")  # type: ignore[attr-defined]
    save_active_marker(nome)


@pytest.mark.asyncio
async def test_o_ciclo_ativa_a_ativa_b_reinicia_e_volta_em_b(lar: Path) -> None:
    """A frase dela inteira: ativa A, ativa B, reinicia — tem de voltar em B.

    O que morde aqui é a SEGUNDA ativação. Um produto em que ela só pudesse
    escolher uma vez passaria em todos os outros testes de sessão desta casa.
    """
    from hefesto_dualsense4unix.daemon.connection import restore_last_profile
    from hefesto_dualsense4unix.daemon.state_store import StateStore
    from hefesto_dualsense4unix.profiles.loader import save_profile
    from hefesto_dualsense4unix.profiles.manager import ProfileManager
    from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile
    from hefesto_dualsense4unix.testing import FakeController

    for nome in ("Personalizado", "Sofá"):
        save_profile(Profile(name=nome, match=MatchAny(), priority=1))

    controle = FakeController()
    controle.connect()
    manager = ProfileManager(controller=controle, store=StateStore())

    _ativa_na_mao(manager, "Personalizado")
    assert resolve_boot_profile() == "Personalizado"

    # ...até ela alterar novamente e ativar outro perfil.
    _ativa_na_mao(manager, "Sofá")
    assert load_last_profile() == "Sofá"
    assert read_active_marker() == "Sofá"
    assert resolve_boot_profile() == "Sofá", (
        "os dois arquivos têm de andar juntos: quando divergem, o marker VENCE "
        "em resolve_boot_profile, e o boot voltaria no perfil anterior"
    )

    # "Reinicia": um daemon novo, do zero.
    store = StateStore()
    await restore_last_profile(  # type: ignore[arg-type]
        _DaemonDeBoot(controller=controle, store=store)
    )
    assert store.active_profile == "Sofá"

    # E o restore não é gesto novo: a intenção dela continua sendo a dela.
    assert resolve_boot_profile() == "Sofá"


@pytest.mark.asyncio
async def test_o_ciclo_sobrevive_ao_jogo_que_abre_e_fecha(lar: Path) -> None:
    """O buraco que o item mandou procurar: o auto-switch no meio do ciclo.

    Ela ativa "Sofá" na mão, um jogo abre e o autoswitch troca o perfil, o jogo
    fecha e o autoswitch volta ao catch-all. Nenhuma dessas trocas é gesto
    dela, e nenhuma pode reescrever a escolha — o defeito que PERFIL-03 curou
    era exatamente o autoswitch clobberando o `session.json` a cada janela.
    """
    from hefesto_dualsense4unix.daemon.connection import restore_last_profile
    from hefesto_dualsense4unix.daemon.state_store import StateStore
    from hefesto_dualsense4unix.profiles.loader import save_profile
    from hefesto_dualsense4unix.profiles.manager import ProfileManager
    from hefesto_dualsense4unix.profiles.schema import (
        MatchAny,
        MatchCriteria,
        Profile,
    )
    from hefesto_dualsense4unix.testing import FakeController

    for nome in ("Personalizado", "Sofá"):
        save_profile(Profile(name=nome, match=MatchAny(), priority=1))
    save_profile(
        Profile(
            name="Stray",
            match=MatchCriteria(process_name=["Stray.exe"]),
            priority=80,
        )
    )

    controle = FakeController()
    controle.connect()
    manager = ProfileManager(controller=controle, store=StateStore())

    _ativa_na_mao(manager, "Personalizado")
    _ativa_na_mao(manager, "Sofá")

    manager.activate("Stray", origin="autoswitch")  # o jogo abriu
    manager.activate("Personalizado", origin="autoswitch")  # o jogo fechou

    assert load_last_profile() == "Sofá"
    assert read_active_marker() == "Sofá"

    store = StateStore()
    await restore_last_profile(  # type: ignore[arg-type]
        _DaemonDeBoot(controller=controle, store=store)
    )
    assert store.active_profile == "Sofá"


@pytest.mark.asyncio
async def test_o_perfil_renomeado_continua_voltando_no_boot(lar: Path) -> None:
    """A metade A e a metade B no MESMO teste — é onde elas se quebram.

    Renomear o perfil padrão sem repontar `session.json`/`active_profile.txt`
    deixaria o boot procurando `meu_perfil`, que não existe mais: o restore
    falharia e ela abriria o programa sem perfil nenhum. Este teste roda a
    migração de verdade, do disco à ativação.
    """
    import json

    from hefesto_dualsense4unix.daemon.connection import restore_last_profile
    from hefesto_dualsense4unix.daemon.state_store import StateStore
    from hefesto_dualsense4unix.profiles.loader import (
        NOME_DO_PADRAO,
        migrate_default_profile_name,
        profiles_dir,
        save_profile,
    )
    from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile
    from hefesto_dualsense4unix.testing import FakeController
    from hefesto_dualsense4unix.utils.session import save_last_profile

    # O disco dela ANTES da atualização: o perfil com o nome antigo, ativo.
    save_profile(Profile(name="meu_perfil", match=MatchAny(), priority=1))
    save_last_profile("meu_perfil")
    save_active_marker("meu_perfil")

    assert migrate_default_profile_name() == NOME_DO_PADRAO

    perfis = profiles_dir()
    assert json.loads(
        (perfis / "personalizado.json").read_text(encoding="utf-8")
    )["name"] == NOME_DO_PADRAO

    controle = FakeController()
    controle.connect()
    store = StateStore()
    await restore_last_profile(  # type: ignore[arg-type]
        _DaemonDeBoot(controller=controle, store=store)
    )
    assert store.active_profile == NOME_DO_PADRAO
