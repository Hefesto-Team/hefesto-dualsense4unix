"""FOCO-ERRANTE-01 — a janela da Steam levava o perfil do jogo junto."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest
import structlog

from hefesto_dualsense4unix.daemon.launch_env import launch_session_appid
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.autoswitch import (
    AutoSwitcher,
    jogo_do_wrapper_vivo,
)
from hefesto_dualsense4unix.profiles.loader import save_profile
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import (
    LedsConfig,
    MatchAny,
    MatchCriteria,
    Profile,
    TriggerConfig,
    TriggersConfig,
)
from hefesto_dualsense4unix.testing import FakeController

APPID = 2497900

CLASSE_DO_JOGO = f"steam_app_{APPID}"

JANELA_DO_JOGO = {"wm_class": CLASSE_DO_JOGO, "wm_name": "DON'T SCREAM"}

JANELA_DO_CLIENTE_STEAM = {"wm_class": "steam", "wm_name": ""}

OUTRO_APPID = 1599660

IDADE_MEDIDA_SEG = 1296


@pytest.fixture
def perfis_isolados(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Diretório de perfis em `tmp_path` (mesmo padrão do resto da suíte)."""
    alvo = tmp_path / "profiles"
    alvo.mkdir()

    def fake_profiles_dir(ensure: bool = False) -> Path:
        if ensure:
            alvo.mkdir(parents=True, exist_ok=True)
        return alvo

    monkeypatch.setattr(loader_module, "profiles_dir", fake_profiles_dir)
    return alvo


def _perfil(nome: str, *, janela: str | None = None, prioridade: int = 10) -> Profile:
    """Perfil mínimo com gatilhos e lightbar — o que a troca reescreve."""
    return Profile(
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


def _os_dois_perfis() -> list[Profile]:
    """O disco do usuário, reduzido ao par que brigou: o jogo e a navegação."""
    return [
        _perfil("dont_scream", janela=CLASSE_DO_JOGO, prioridade=97),
        _perfil("navegacao", janela="steam", prioridade=50),
    ]


def _switcher(
    manager: ProfileManager,
    store: StateStore,
    *,
    jogo_vivo: Any = None,
) -> AutoSwitcher:
    return AutoSwitcher(
        manager=manager,
        window_reader=lambda: {},
        store=store,
        jogo_vivo_reader=jogo_vivo,
    )


def _entrar_no_jogo(sw: AutoSwitcher, store: StateStore) -> float:
    """Leva o autoswitch ao perfil do jogo pelo caminho normal, e devolve `now`."""
    sw._tick(dict(JANELA_DO_JOGO), 0.0)
    sw._tick(dict(JANELA_DO_JOGO), 1.0)
    assert store.active_profile == "dont_scream", "o autoswitch não entrou no jogo"
    return 1.0


def _focar_a_steam(sw: AutoSwitcher, inicio: float, tiques: int = 20) -> None:
    """Segura a janela do cliente Steam em foco por `tiques` a 2 Hz."""
    for i in range(tiques):
        sw._tick(dict(JANELA_DO_CLIENTE_STEAM), inicio + 0.5 * (i + 1))


def _marker(
    tmp_path: Path,
    *,
    appid: int = APPID,
    idade_seg: int = 0,
    pid: int | None = None,
) -> Path:
    """Grava `last_run` com a idade pedida, e devolve o `base_dir`."""
    base = tmp_path / "launch_env"
    base.mkdir(exist_ok=True)
    (base / "last_run").write_text(
        f"appid={appid}\n"
        f"epoch={int(time.time()) - idade_seg}\n"
        f"pid={pid if pid is not None else os.getpid()}\n",
        encoding="utf-8",
    )
    return base


def _proc_falso(tmp_path: Path, *, cmdline: bytes, pid: int | None = None) -> Path:
    """Um `/proc` de mentira com a `cmdline` pedida, e devolve o `proc_dir`."""
    raiz = tmp_path / "proc"
    alvo = raiz / str(pid if pid is not None else os.getpid())
    alvo.mkdir(parents=True, exist_ok=True)
    (alvo / "cmdline").write_bytes(cmdline)
    return raiz


CMDLINE_MEDIDA = (
    b"/home/x/.steam/steam/ubuntu12_32/reaper\0SteamLaunch\0"
    b"AppId=2497900\0--\0/x/DontScream-Win64-Shipping.exe\0"
)


def test_a_janela_do_cliente_steam_nao_troca_o_perfil_com_o_jogo_vivo(
    perfis_isolados: Path,
) -> None:
    """MORDIDA nº 1: o defeito de 18/08, reduzido a dez segundos de tique."""
    manager, store = _bancada(_os_dois_perfis())
    sw = _switcher(manager, store, jogo_vivo=lambda: APPID)
    agora = _entrar_no_jogo(sw, store)

    with structlog.testing.capture_logs() as registros:
        _focar_a_steam(sw, agora)

    assert store.active_profile == "dont_scream"
    trocas = [r for r in registros if r["event"] == "profile_autoswitch"]
    assert trocas == [], f"o perfil foi roubado: {trocas}"


def test_a_recusa_preserva_o_gatilho_e_a_lightbar_do_jogo(
    perfis_isolados: Path,
) -> None:
    """O que ela PERDIA, no vocabulário do aparelho."""
    manager, store = _bancada(_os_dois_perfis())
    sw = _switcher(manager, store, jogo_vivo=lambda: APPID)
    agora = _entrar_no_jogo(sw, store)

    controller: Any = manager.controller
    lightbar_do_jogo = controller.last_led
    assert lightbar_do_jogo is not None, "o perfil do jogo nem chegou ao LED"
    escritas = store.counter("profile.activated")

    _focar_a_steam(sw, agora)

    assert controller.last_led == lightbar_do_jogo
    assert store.counter("profile.activated") == escritas


def test_sem_jogo_vivo_a_janela_da_steam_troca_normalmente(
    perfis_isolados: Path,
) -> None:
    """MORDIDA nº 2: arranque o termo de VITALIDADE e este teste reprova."""
    manager, store = _bancada(_os_dois_perfis())
    sw = _switcher(manager, store, jogo_vivo=lambda: None)
    agora = _entrar_no_jogo(sw, store)

    _focar_a_steam(sw, agora)

    assert store.active_profile == "navegacao"


def test_o_jogo_morre_e_a_guarda_solta(perfis_isolados: Path) -> None:
    """O ensaio E-4 da sprint, em memória: a MESMA janela, uma variável só."""
    manager, store = _bancada(_os_dois_perfis())
    vivo = [True]
    sw = _switcher(manager, store, jogo_vivo=lambda: APPID if vivo[0] else None)
    agora = _entrar_no_jogo(sw, store)

    _focar_a_steam(sw, agora, tiques=10)
    assert store.active_profile == "dont_scream"

    vivo[0] = False
    sw._tick(dict(JANELA_DO_CLIENTE_STEAM), agora + 6.0)
    sw._tick(dict(JANELA_DO_CLIENTE_STEAM), agora + 6.5)

    assert store.active_profile == "navegacao"


def test_janela_de_outro_app_nao_tira_o_perfil_com_o_jogo_vivo(
    perfis_isolados: Path,
) -> None:
    """MORDIDA nº 3: estreite a guarda de volta à janela da Steam e isto reprova."""
    manager, store = _bancada([*_os_dois_perfis(), _perfil("web", janela="firefox")])
    sw = _switcher(manager, store, jogo_vivo=lambda: APPID)
    agora = _entrar_no_jogo(sw, store)

    for i in range(6):
        sw._tick({"wm_class": "firefox", "wm_name": "Mozilla Firefox"}, agora + 0.5 * i)

    assert store.active_profile == "dont_scream"


def test_a_guarda_so_vale_para_o_jogo_do_perfil_corrente(
    perfis_isolados: Path,
) -> None:
    """MORDIDA nº 4: guarda cruzada — o marker de A não segura o perfil de B."""
    manager, store = _bancada(_os_dois_perfis())
    sw = _switcher(manager, store, jogo_vivo=lambda: OUTRO_APPID)
    agora = _entrar_no_jogo(sw, store)

    _focar_a_steam(sw, agora)

    assert store.active_profile == "navegacao"


def test_perfil_de_desktop_corrente_nao_ganha_guarda_nenhuma(
    perfis_isolados: Path,
) -> None:
    """A guarda exige que o perfil CORRENTE seja a regra própria de um jogo."""
    from hefesto_dualsense4unix.utils.session import save_last_profile

    manager, store = _bancada([_perfil("desktop"), _perfil("navegacao", janela="steam")])
    save_last_profile("desktop")
    sw = _switcher(manager, store, jogo_vivo=lambda: APPID)
    sw._tick({"wm_class": "nautilus"}, 0.0)
    sw._tick({"wm_class": "nautilus"}, 1.0)
    assert store.active_profile == "desktop"

    _focar_a_steam(sw, 1.0)

    assert store.active_profile == "navegacao"


def test_o_jogo_vivo_nao_expira_aos_quinze_minutos(
    perfis_isolados: Path, tmp_path: Path
) -> None:
    """MORDIDA nº 5: o número medido, 1296 s, contra a janela de 900 s."""
    base = _marker(tmp_path, idade_seg=IDADE_MEDIDA_SEG)
    proc = _proc_falso(tmp_path, cmdline=CMDLINE_MEDIDA)

    assert launch_session_appid(base_dir=base) is None
    assert jogo_do_wrapper_vivo(base_dir=base, proc_dir=proc) == APPID

    manager, store = _bancada(_os_dois_perfis())
    sw = _switcher(
        manager,
        store,
        jogo_vivo=lambda: jogo_do_wrapper_vivo(base_dir=base, proc_dir=proc),
    )
    agora = _entrar_no_jogo(sw, store)

    _focar_a_steam(sw, agora)

    assert store.active_profile == "dont_scream"


def test_marker_sem_pid_nao_atesta_vitalidade(tmp_path: Path) -> None:
    """Marker anterior ao NUMA-01 (sem `pid=`) não tem o que atestar."""
    base = tmp_path / "launch_env"
    base.mkdir()
    (base / "last_run").write_text(
        f"appid={APPID}\nepoch={int(time.time())}\n", encoding="utf-8"
    )

    assert jogo_do_wrapper_vivo(base_dir=base) is None


def test_sem_marker_nenhum_a_guarda_e_inerte(tmp_path: Path) -> None:
    """Máquina sem wrapper: a guarda nem chega a existir."""
    assert jogo_do_wrapper_vivo(base_dir=tmp_path / "vazio") is None


def test_o_last_exit_do_mesmo_launch_continua_invalidando(tmp_path: Path) -> None:
    """A correlação por pid do NUMA-01 sobrevive à retirada da janela de tempo."""
    base = _marker(tmp_path, idade_seg=10)
    proc = _proc_falso(tmp_path, cmdline=CMDLINE_MEDIDA)
    (base / "last_exit").write_text(
        f"epoch={int(time.time())}\npid={os.getpid()}\n", encoding="utf-8"
    )

    assert jogo_do_wrapper_vivo(base_dir=base, proc_dir=proc) is None


def test_pid_reciclado_nao_segura_o_perfil(
    perfis_isolados: Path, tmp_path: Path
) -> None:
    """MORDIDA nº 6: arranque a corroboração por `AppId=` e isto reprova."""
    base = _marker(tmp_path, idade_seg=IDADE_MEDIDA_SEG)
    proc = _proc_falso(
        tmp_path, cmdline=b"/usr/bin/python3\0-m\0pytest\0-q\0"
    )

    assert jogo_do_wrapper_vivo(base_dir=base, proc_dir=proc) is None

    manager, store = _bancada(_os_dois_perfis())
    sw = _switcher(
        manager,
        store,
        jogo_vivo=lambda: jogo_do_wrapper_vivo(base_dir=base, proc_dir=proc),
    )
    agora = _entrar_no_jogo(sw, store)

    _focar_a_steam(sw, agora)

    assert store.active_profile == "navegacao"


def test_a_corroboracao_nao_confunde_appid_prefixo(tmp_path: Path) -> None:
    """`AppId=249790` não é `AppId=2497900` — a fronteira do número é dura."""
    base = _marker(tmp_path)
    proc = _proc_falso(tmp_path, cmdline=b"reaper\0SteamLaunch\0AppId=24979000\0")

    assert jogo_do_wrapper_vivo(base_dir=base, proc_dir=proc) is None


def test_a_corroboracao_e_insensivel_a_caixa(tmp_path: Path) -> None:
    """A Steam escreve `AppId=`; a casa não aposta na grafia de ninguém."""
    base = _marker(tmp_path)
    proc = _proc_falso(tmp_path, cmdline=b"reaper\0SteamLaunch\0APPID=2497900\0--\0")

    assert jogo_do_wrapper_vivo(base_dir=base, proc_dir=proc) == APPID


def test_a_corroboracao_le_o_proc_de_verdade(tmp_path: Path) -> None:
    """A régua contra um processo REAL — o `/proc` de mentira não pode mentir."""
    filho = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import time; time.sleep(30)",
            "SteamLaunch",
            f"AppId={APPID}",
            "--",
        ],
    )
    try:
        base = _marker(tmp_path, idade_seg=IDADE_MEDIDA_SEG, pid=filho.pid)
        assert jogo_do_wrapper_vivo(base_dir=base) == APPID
    finally:
        filho.kill()
        filho.wait(timeout=10)

    assert jogo_do_wrapper_vivo(base_dir=base) is None


def test_a_recusa_loga_uma_vez_por_episodio(perfis_isolados: Path) -> None:
    """MORDIDA nº 7: arranque a chave de dedup e vira uma linha por tique."""
    manager, store = _bancada(_os_dois_perfis())
    sw = _switcher(manager, store, jogo_vivo=lambda: APPID)
    agora = _entrar_no_jogo(sw, store)

    with structlog.testing.capture_logs() as registros:
        _focar_a_steam(sw, agora, tiques=40)

    recusas = [
        r for r in registros if r["event"] == "autoswitch_recusou_a_troca_com_o_jogo_vivo"
    ]
    assert len(recusas) == 1, f"{len(recusas)} linhas em 40 tiques"
    assert recusas[0]["candidato"] == "navegacao"
    assert recusas[0]["perfil_corrente"] == "dont_scream"
    assert recusas[0]["appid"] == APPID


def test_um_episodio_novo_volta_a_aparecer_no_journal(perfis_isolados: Path) -> None:
    """Dedup não pode virar silêncio: o episódio SEGUINTE tem de aparecer."""
    manager, store = _bancada(_os_dois_perfis())
    sw = _switcher(manager, store, jogo_vivo=lambda: APPID)
    agora = _entrar_no_jogo(sw, store)

    with structlog.testing.capture_logs() as registros:
        _focar_a_steam(sw, agora, tiques=6)
        sw._tick(dict(JANELA_DO_JOGO), agora + 5.0)
        sw._tick(dict(JANELA_DO_JOGO), agora + 5.5)
        _focar_a_steam(sw, agora + 6.0, tiques=6)

    recusas = [
        r for r in registros if r["event"] == "autoswitch_recusou_a_troca_com_o_jogo_vivo"
    ]
    assert len(recusas) == 2


def test_a_entrada_no_perfil_do_jogo_continua_barata(perfis_isolados: Path) -> None:
    """GUARDA (passa nos dois estados): a UX-04 continua de pé."""
    manager, store = _bancada(_os_dois_perfis())
    sw = _switcher(manager, store, jogo_vivo=lambda: APPID)

    sw._tick(dict(JANELA_DO_JOGO), 0.0)
    sw._tick(dict(JANELA_DO_JOGO), 1.0)

    assert store.active_profile == "dont_scream"


def test_o_tique_cego_continua_retendo_o_perfil(perfis_isolados: Path) -> None:
    """GUARDA: a histerese UX-01 não foi tocada."""
    manager, store = _bancada(_os_dois_perfis())
    sw = _switcher(manager, store, jogo_vivo=lambda: APPID)
    agora = _entrar_no_jogo(sw, store)

    for i in range(10):
        sw._tick({}, agora + 0.5 * (i + 1))

    assert store.active_profile == "dont_scream"


def test_sem_leitor_injetado_a_guarda_nao_derruba_o_tique(
    perfis_isolados: Path,
) -> None:
    """GUARDA: o default de produção (ler o disco real) é inerte sem marker."""
    manager, store = _bancada(_os_dois_perfis())
    sw = _switcher(manager, store)
    agora = _entrar_no_jogo(sw, store)

    _focar_a_steam(sw, agora)

    assert store.active_profile == "navegacao"


def test_leitor_que_levanta_nao_derruba_o_tique(perfis_isolados: Path) -> None:
    """GUARDA: exceção na vitalidade vira "não sei", e "não sei" não recusa."""

    def _explode() -> int | None:
        raise RuntimeError("marker ilegível")

    manager, store = _bancada(_os_dois_perfis())
    sw = _switcher(manager, store, jogo_vivo=_explode)
    agora = _entrar_no_jogo(sw, store)

    _focar_a_steam(sw, agora)

    assert store.active_profile == "navegacao"
