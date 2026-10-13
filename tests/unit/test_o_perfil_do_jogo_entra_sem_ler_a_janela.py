"""O perfil do jogo entra sem ler a janela (sprint de 09/10/2026).

Três réguas: a entrada pela prova do jogo em cena (leitura de janela vazia, ou
janela sem regra de jogo), o ambiente gráfico que o serviço completa (as três
variáveis, uma a uma) e a unit sem a linha que copiava o gerenciador para ele
mesmo.
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.daemon.subsystems import autoswitch as sub
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.autoswitch import AutoSwitcher
from hefesto_dualsense4unix.profiles.loader import save_profile
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import (
    LedsConfig,
    MatchAny,
    MatchCriteria,
    Profile,
    ProfileModeConfig,
    TriggerConfig,
    TriggersConfig,
)
from hefesto_dualsense4unix.testing import FakeController

APPID = 2497900
CLASSE = f"steam_app_{APPID}"
RAIZ = Path(__file__).resolve().parents[2]


@pytest.fixture
def perfis_isolados(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    alvo = tmp_path / "profiles"
    alvo.mkdir()
    monkeypatch.setattr(loader_module, "profiles_dir", lambda ensure=False: alvo)
    return alvo


def _perfil(
    nome: str,
    *,
    janela: str | None = None,
    prioridade: int = 10,
    modo: ProfileModeConfig | None = None,
) -> Profile:
    return Profile(
        mode=modo,
        name=nome,
        match=MatchAny() if janela is None else MatchCriteria(window_class=[janela]),
        priority=0 if janela is None else prioridade,
        triggers=TriggersConfig(
            left=TriggerConfig(mode="Off"),
            right=TriggerConfig(mode="Rigid", params=[0, 100]),
        ),
        leds=LedsConfig(lightbar=(129, 61, 156)),
    )


def _bancada(perfis: list[Profile]) -> tuple[ProfileManager, StateStore]:
    for perfil in perfis:
        save_profile(perfil)
    fc = FakeController()
    fc.connect()
    store = StateStore()
    return ProfileManager(controller=fc, store=store), store


def _os_perfis() -> list[Profile]:
    return [
        _perfil(
            "o_jogo",
            janela=CLASSE,
            prioridade=97,
            modo=ProfileModeConfig(kind="gamepad", gamepad_flavor="dualsense"),
        ),
        _perfil("navegacao", janela="firefox", prioridade=50),
        _perfil("geral"),
    ]


class _Cena:
    """O jogo em cena segundo o serviço: o teste liga e desliga."""

    def __init__(self) -> None:
        self.appid: int | None = None

    def __call__(self) -> int | None:
        return self.appid


def _switcher(
    manager: ProfileManager, store: StateStore, cena: _Cena | None
) -> AutoSwitcher:
    return AutoSwitcher(
        manager=manager,
        window_reader=lambda: {},
        store=store,
        jogo_em_cena_reader=cena,
        jogo_vivo_reader=lambda: None,
    )


def _tiques(sw: AutoSwitcher, info: dict[str, Any], de: float, ate: float) -> None:
    t = de
    while t <= ate:
        sw._tick(dict(info), t)
        t += 0.5


# A entrada pela prova do jogo -------------------------------------------------------


def test_leitura_vazia_com_o_jogo_em_cena_entra_no_perfil_dele(
    perfis_isolados: Path,
) -> None:
    manager, store = _bancada(_os_perfis())
    cena = _Cena()
    cena.appid = APPID
    sw = _switcher(manager, store, cena)
    _tiques(sw, {}, 0.0, 2.0)
    assert store.active_profile == "o_jogo"


def test_leitura_vazia_sem_jogo_em_cena_fica_no_de_antes(perfis_isolados: Path) -> None:
    manager, store = _bancada(_os_perfis())
    manager.activate("geral")
    sw = _switcher(manager, store, _Cena())
    _tiques(sw, {}, 0.0, 2.0)
    assert store.active_profile == "geral"


def test_janela_sem_regra_de_jogo_com_o_jogo_em_cena_entra_no_do_jogo(
    perfis_isolados: Path,
) -> None:
    manager, store = _bancada(_os_perfis())
    cena = _Cena()
    cena.appid = APPID
    sw = _switcher(manager, store, cena)
    _tiques(sw, {"wm_class": "firefox", "wm_name": "Mozilla"}, 0.0, 2.0)
    assert store.active_profile == "o_jogo"


def test_a_janela_sem_regra_e_sem_jogo_em_cena_segue_a_janela(
    perfis_isolados: Path,
) -> None:
    manager, store = _bancada(_os_perfis())
    sw = _switcher(manager, store, _Cena())
    _tiques(sw, {"wm_class": "firefox", "wm_name": "Mozilla"}, 0.0, 2.0)
    assert store.active_profile == "navegacao"


def test_jogo_em_cena_sem_perfil_proprio_nao_inventa_perfil(
    perfis_isolados: Path,
) -> None:
    manager, store = _bancada(_os_perfis())
    manager.activate("geral")
    cena = _Cena()
    cena.appid = 999
    sw = _switcher(manager, store, cena)
    _tiques(sw, {}, 0.0, 2.0)
    assert store.active_profile == "geral"


def test_sem_leitor_do_jogo_em_cena_o_caminho_de_hoje_nao_muda(
    perfis_isolados: Path,
) -> None:
    manager, store = _bancada(_os_perfis())
    manager.activate("geral")
    sw = _switcher(manager, store, None)
    _tiques(sw, {}, 0.0, 2.0)
    assert store.active_profile == "geral"


def test_o_leitor_que_levanta_nao_derruba_o_tique(perfis_isolados: Path) -> None:
    manager, store = _bancada(_os_perfis())
    manager.activate("geral")

    def _quebra() -> int | None:
        raise RuntimeError("serviço sem sinal")

    sw = _switcher(manager, store, _quebra)  # type: ignore[arg-type]
    _tiques(sw, {}, 0.0, 2.0)
    assert store.active_profile == "geral"


def test_quando_a_prova_some_e_a_leitura_segue_vazia_volta_a_escolha_dela(
    perfis_isolados: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hefesto_dualsense4unix.utils import session

    monkeypatch.setattr(session, "a_escolha_dela", lambda **_k: "navegacao")
    manager, store = _bancada(_os_perfis())
    cena = _Cena()
    cena.appid = APPID
    sw = _switcher(manager, store, cena)
    _tiques(sw, {}, 0.0, 2.0)
    assert store.active_profile == "o_jogo"
    cena.appid = None
    _tiques(sw, {}, 3.0, 20.0)
    assert store.active_profile == "navegacao"


def test_a_prova_do_jogo_nao_passa_por_cima_do_que_ela_escolheu_a_mao(
    perfis_isolados: Path,
) -> None:
    manager, store = _bancada(_os_perfis())
    cena = _Cena()
    cena.appid = APPID
    sw = _switcher(manager, store, cena)
    manager.activate("navegacao")
    store.mark_manual_profile_lock(time.monotonic() + 3600.0)
    _tiques(sw, {}, 0.0, 2.0)
    assert store.active_profile == "navegacao"


def test_o_servico_entrega_o_jogo_em_cena_ao_autoswitch(
    perfis_isolados: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import asyncio
    from types import SimpleNamespace

    monkeypatch.setattr(sub, "_ensure_display_env", lambda: None)
    monkeypatch.setenv("HEFESTO_DUALSENSE4UNIX_NO_WINDOW_DETECT", "1")
    daemon = SimpleNamespace(appid_em_cena=APPID)
    ctx = SimpleNamespace(daemon=daemon, controller=FakeController(), store=StateStore())
    subsistema = sub.AutoswitchSubsystem()
    asyncio.run(subsistema.start(ctx))  # type: ignore[arg-type]
    leitor = subsistema._autoswitch.jogo_em_cena_reader
    assert leitor is not None
    assert leitor() == APPID
    daemon.appid_em_cena = None
    assert leitor() is None
    daemon.appid_em_cena = True  # um bool não é appid
    assert leitor() is None


# O ambiente gráfico -----------------------------------------------------------------------


def _systemctl_com(monkeypatch: pytest.MonkeyPatch, saida: str) -> MagicMock:
    for chave in ("WAYLAND_DISPLAY", "DISPLAY", "XAUTHORITY"):
        monkeypatch.delenv(chave, raising=False)
    monkeypatch.setattr("shutil.which", lambda _n: "/usr/bin/systemctl")
    rodou = MagicMock(return_value=MagicMock(stdout=saida))
    monkeypatch.setattr("subprocess.run", rodou)
    return rodou


def test_o_ambiente_traz_as_tres_variaveis(monkeypatch: pytest.MonkeyPatch) -> None:
    _systemctl_com(monkeypatch, "DISPLAY=:1\nXAUTHORITY=/x\nWAYLAND_DISPLAY=wayland-1\n")
    sub._ensure_display_env()
    assert os.environ["DISPLAY"] == ":1"
    assert os.environ["XAUTHORITY"] == "/x"
    assert os.environ["WAYLAND_DISPLAY"] == "wayland-1"


def test_o_processo_com_o_display_completa_a_autorizacao_que_faltava(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rodou = _systemctl_com(monkeypatch, "DISPLAY=:1\nXAUTHORITY=/x\n")
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    sub._ensure_display_env()
    rodou.assert_called_once()
    assert os.environ["WAYLAND_DISPLAY"] == "wayland-0"
    assert os.environ["DISPLAY"] == ":1"
    assert os.environ["XAUTHORITY"] == "/x"


def test_com_as_tres_no_processo_nao_pergunta_ao_systemctl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rodou = _systemctl_com(monkeypatch, "")
    for chave, valor in (("WAYLAND_DISPLAY", "w"), ("DISPLAY", ":0"), ("XAUTHORITY", "/y")):
        monkeypatch.setenv(chave, valor)
    sub._ensure_display_env()
    rodou.assert_not_called()


# A unit ------------------------------------------------------------------------------------


def test_a_unit_nao_tem_o_import_environment_inutil() -> None:
    unit = (RAIZ / "assets" / "hefesto-dualsense4unix.service").read_text(encoding="utf-8")
    linhas_ativas = [ln for ln in unit.splitlines() if not ln.lstrip().startswith("#")]
    assert not any("import-environment" in ln for ln in linhas_ativas)
    assert "_ensure_display_env" in unit
