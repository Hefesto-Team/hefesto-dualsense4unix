"""GUI-05 item 3 (lado daemon) — `wrapper_used` honesto no state_full.

FATO 0 do estudo 2026-07-18: o jogo rodou SEM o wrapper `hefesto-launch` e o
`dedup_ok: true` era falso-tranquilizante (só checava "vpads são uhid", nunca
se o jogo herdou a env). Aqui trava-se:

1. a decisão PURA (`wrapper_used_state`, parametrizada) e o parse tolerante
   do marker `last_run` que o wrapper grava (`read_last_run_marker`);
2. o handler `daemon.state_full`: `gamepad_emulation.wrapper_used` =
   true/false com jogo detectado, null sem jogo — e `dedup_ok` refletindo
   (jogo sem wrapper derruba o dedup_ok com motivo `jogo_sem_wrapper`,
   exceto quando não há env que importe: Modo Nativo/emulação off).
"""
from __future__ import annotations

import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.daemon import launch_env as le_mod
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.launch_env import (
    WRAPPER_MARKER_WINDOW_SEC,
    pid_is_alive,
    read_last_exit_marker,
    read_last_exit_pid,
    read_last_run_marker,
    read_last_run_pid,
    steam_appid_from_wm_class,
    wrapper_game_running,
    wrapper_used_state,
)
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.testing import FakeController

APPID = 1599660  # Sackboy (wm_class provado ao vivo)


# --- decisão pura -------------------------------------------------------------


@pytest.mark.parametrize(
    ("marker", "first_seen", "esperado"),
    [
        # Sem marker: o wrapper nunca rodou.
        (None, 1000.0, False),
        # Marker de OUTRO appid não conta.
        ((999, 1000), 1000.0, False),
        # Caso bom: wrapper rodou logo antes de a janela aparecer.
        ((APPID, 990), 1000.0, True),
        # Fronteira: exatamente na janela.
        ((APPID, 1000 - int(WRAPPER_MARKER_WINDOW_SEC)), 1000.0, True),
        # Marker velho demais (launch anterior, sessão de ontem).
        ((APPID, 1000 - int(WRAPPER_MARKER_WINDOW_SEC) - 1), 1000.0, False),
        # Marker mais NOVO que a 1ª detecção (relaunch com leitura quente).
        ((APPID, 1005), 1000.0, True),
    ],
)
def test_wrapper_used_state_parametrizado(
    marker: tuple[int, int] | None, first_seen: float, esperado: bool
) -> None:
    assert (
        wrapper_used_state(appid=APPID, marker=marker, first_seen_epoch=first_seen)
        is esperado
    )


def test_wrapper_used_jogo_pesado_abre_janela_minutos_depois() -> None:
    """Regressão do falso alarme "jogo sem wrapper" em AAA de carregamento
    longo (RDR2/compilação de shaders): a janela `steam_app_N` só aparece
    ~5 min APÓS o launch. O marker é do LAUNCH, então o gap marker→janela é de
    300 s — dentro da janela de 15 min, mas passava dos 120 s antigos. O
    wrapper RODOU e exportou as envs; `wrapper_used` tem que continuar True (o
    número é concreto de propósito: falha com a janela de 120 s, passa com 900).
    """
    gap = 300.0  # 5 min entre o launch (marker) e a 1ª janela do jogo
    first_seen = 10_000.0
    marker = (APPID, int(first_seen - gap))
    assert (
        wrapper_used_state(appid=APPID, marker=marker, first_seen_epoch=first_seen)
        is True
    )
    # A constante precisa ser generosa o bastante para cobrir AAA pesado.
    assert gap <= WRAPPER_MARKER_WINDOW_SEC


def test_steam_appid_from_wm_class() -> None:
    assert steam_appid_from_wm_class(f"steam_app_{APPID}") == APPID
    assert steam_appid_from_wm_class("Main.py") is None
    assert steam_appid_from_wm_class("steam_app_") is None
    assert steam_appid_from_wm_class(None) is None


# --- parse do marker ----------------------------------------------------------


def _grava_marker(base: Path, texto: str) -> None:
    base.mkdir(parents=True, exist_ok=True)
    (base / "last_run").write_text(texto, encoding="utf-8")


def test_read_last_run_marker_formato_canonico(tmp_path: Path) -> None:
    _grava_marker(tmp_path, f"appid={APPID}\nepoch=1234567\n")
    assert read_last_run_marker(tmp_path) == (APPID, 1234567)


def test_read_last_run_marker_tolerante_a_lixo(tmp_path: Path) -> None:
    _grava_marker(
        tmp_path,
        f"# comentario\nfoo=bar\nappid={APPID}\nepoch=99\nLD_PRELOAD=/evil\n",
    )
    assert read_last_run_marker(tmp_path) == (APPID, 99)


@pytest.mark.parametrize(
    "texto",
    [
        "",  # vazio
        "appid=123\n",  # sem epoch
        "epoch=99\n",  # sem appid
        "appid=abc\nepoch=99\n",  # appid não-numérico
        "appid=0\nepoch=99\n",  # appid 0 = launch fora da Steam
        "appid=-3\nepoch=99\n",  # negativo não passa no isdigit
    ],
)
def test_read_last_run_marker_invalido_devolve_none(
    tmp_path: Path, texto: str
) -> None:
    _grava_marker(tmp_path, texto)
    assert read_last_run_marker(tmp_path) is None


def test_read_last_run_marker_sem_arquivo(tmp_path: Path) -> None:
    assert read_last_run_marker(tmp_path / "nao_existe") is None


# --- NUMA-01: pid opcional, last_exit, wrapper_game_running -------------------


def test_read_last_run_marker_tolera_pid_opcional(tmp_path: Path) -> None:
    """`pid=` é um campo NOVO opcional — `read_last_run_marker` continua
    devolvendo o mesmo `(appid, epoch)` de sempre (compat com
    `wrapper_used_state`, que desempacota um par)."""
    _grava_marker(tmp_path, f"appid={APPID}\nepoch=1234567\npid=999\n")
    assert read_last_run_marker(tmp_path) == (APPID, 1234567)


def test_read_last_run_pid_le_o_campo_novo(tmp_path: Path) -> None:
    _grava_marker(tmp_path, f"appid={APPID}\nepoch=1234567\npid=4242\n")
    assert read_last_run_pid(tmp_path) == 4242


def test_read_last_run_pid_ausente_devolve_none(tmp_path: Path) -> None:
    """Marker ANTIGO (sem o campo `pid=`, de antes do NUMA-01) não quebra."""
    _grava_marker(tmp_path, f"appid={APPID}\nepoch=1234567\n")
    assert read_last_run_pid(tmp_path) is None


def test_read_last_run_pid_lixo_devolve_none(tmp_path: Path) -> None:
    _grava_marker(tmp_path, f"appid={APPID}\nepoch=1234567\npid=abc\n")
    assert read_last_run_pid(tmp_path) is None


def test_read_last_run_pid_sem_arquivo(tmp_path: Path) -> None:
    assert read_last_run_pid(tmp_path / "nao_existe") is None


def test_read_last_exit_marker_formato_canonico(tmp_path: Path) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "last_exit").write_text("epoch=555\n", encoding="utf-8")
    assert read_last_exit_marker(tmp_path) == 555


def test_read_last_exit_marker_tolerante_a_lixo(tmp_path: Path) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "last_exit").write_text(
        "# comentario\nfoo=bar\nepoch=abc\n", encoding="utf-8"
    )
    assert read_last_exit_marker(tmp_path) is None


def test_read_last_exit_marker_sem_arquivo(tmp_path: Path) -> None:
    assert read_last_exit_marker(tmp_path / "nao_existe") is None


def test_read_last_exit_pid_le_o_campo_novo(tmp_path: Path) -> None:
    """Correção pós-auditoria: `pid=` no `last_exit` correlaciona a saída ao
    launch que a gravou (ver `TestWrapperGameRunning`)."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "last_exit").write_text("epoch=555\npid=111\n", encoding="utf-8")
    assert read_last_exit_pid(tmp_path) == 111


def test_read_last_exit_pid_ausente_devolve_none(tmp_path: Path) -> None:
    """`last_exit` ANTIGO (de antes da correção, sem o campo) não quebra."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "last_exit").write_text("epoch=555\n", encoding="utf-8")
    assert read_last_exit_pid(tmp_path) is None


def test_read_last_exit_pid_lixo_devolve_none(tmp_path: Path) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "last_exit").write_text("epoch=555\npid=xyz\n", encoding="utf-8")
    assert read_last_exit_pid(tmp_path) is None


def test_read_last_exit_pid_sem_arquivo(tmp_path: Path) -> None:
    assert read_last_exit_pid(tmp_path / "nao_existe") is None


class TestPidIsAlive:
    def test_none_e_zero_e_negativo_sao_falsos(self) -> None:
        assert pid_is_alive(None) is False
        assert pid_is_alive(0) is False
        assert pid_is_alive(-1) is False

    def test_processo_vivo_e_true(self) -> None:
        import os

        assert pid_is_alive(os.getpid()) is True

    def test_process_lookup_error_e_falso(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import os

        def _explode(pid: int, sig: int) -> None:
            raise ProcessLookupError

        monkeypatch.setattr(os, "kill", _explode)
        assert pid_is_alive(4242) is False

    def test_permission_error_ainda_conta_como_vivo(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import os

        def _explode(pid: int, sig: int) -> None:
            raise PermissionError

        monkeypatch.setattr(os, "kill", _explode)
        assert pid_is_alive(4242) is True

    def test_oserror_generico_nunca_levanta_e_e_falso(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import os

        def _explode(pid: int, sig: int) -> None:
            raise OSError("erro qualquer")

        monkeypatch.setattr(os, "kill", _explode)
        assert pid_is_alive(4242) is False


class TestWrapperGameRunning:
    """NUMA-01 — evidência #3: marker fresco + pid vivo + sem exit mais novo."""

    def test_marker_none_e_falso(self) -> None:
        assert (
            wrapper_game_running(marker=None, exit_marker=None, pid_alive=True)
            is False
        )

    def test_fresco_pid_vivo_sem_exit_e_true(self) -> None:
        assert (
            wrapper_game_running(
                marker=(APPID, 990),
                exit_marker=None,
                pid_alive=True,
                now=1000.0,
            )
            is True
        )

    def test_na_fronteira_da_janela_e_true(self) -> None:
        assert (
            wrapper_game_running(
                marker=(APPID, 1000 - int(WRAPPER_MARKER_WINDOW_SEC)),
                exit_marker=None,
                pid_alive=True,
                now=1000.0,
            )
            is True
        )

    def test_marker_velho_demais_e_false(self) -> None:
        assert (
            wrapper_game_running(
                marker=(APPID, 1000 - int(WRAPPER_MARKER_WINDOW_SEC) - 1),
                exit_marker=None,
                pid_alive=True,
                now=1000.0,
            )
            is False
        )

    def test_pid_morto_e_false_mesmo_com_marker_fresco(self) -> None:
        assert (
            wrapper_game_running(
                marker=(APPID, 990),
                exit_marker=None,
                pid_alive=False,
                now=1000.0,
            )
            is False
        )

    def test_exit_mais_novo_que_o_marker_e_false(self) -> None:
        """Aquele launch já terminou — o marker não atesta jogo rodando."""
        assert (
            wrapper_game_running(
                marker=(APPID, 990),
                exit_marker=995,
                pid_alive=True,
                now=1000.0,
            )
            is False
        )

    def test_exit_igual_ao_marker_e_false(self) -> None:
        """Fronteira: `exit_marker >= marker_epoch` — empate conta como
        "já terminou" (fail-safe do lado conservador desta evidência
        específica; `classify` ainda tem os outros 2 ramos)."""
        assert (
            wrapper_game_running(
                marker=(APPID, 990),
                exit_marker=990,
                pid_alive=True,
                now=1000.0,
            )
            is False
        )

    def test_exit_mais_velho_que_o_marker_e_ignorado(self) -> None:
        """`last_exit` de um launch ANTERIOR (mais velho que o marker
        atual) não invalida o launch corrente."""
        assert (
            wrapper_game_running(
                marker=(APPID, 990),
                exit_marker=100,
                pid_alive=True,
                now=1000.0,
            )
            is True
        )

    def test_nunca_levanta_com_entradas_esquisitas(self) -> None:
        assert (
            wrapper_game_running(
                marker=(0, -5), exit_marker=-10, pid_alive=True, now=0.0
            )
            is True
        )

    # --- correção pós-auditoria: correlação por pid entre last_run/last_exit
    #
    # Achado: `last_run`/`last_exit` são arquivos GLOBAIS (sem pid/sessão
    # amarrando um ao outro). Sequência do incidente: launch A grava
    # last_run(epoch=990, pid=P_A) e o próprio `exec` FALHA; launch B (retry
    # ou outro jogo) grava last_run(epoch=995, pid=P_B) com SUCESSO — P_B
    # vivo rodando o jogo de verdade; o trap tardio de A só termina de
    # gravar last_exit(epoch=999) DEPOIS que B já sobrescreveu o marker. Sem
    # a correlação por pid, exit_marker(999) >= marker_epoch(995) derrubava
    # B com o jogo de B genuinamente vivo.

    def test_exit_de_outro_launch_nao_invalida_com_pids_correlacionados(
        self,
    ) -> None:
        """`exit_pid` (do launch A, que falhou) != `marker_pid` (do launch B,
        vivo): o `last_exit` tardio de A é reconhecido como de OUTRO launch
        e IGNORADO — B continua contando como jogo rodando."""
        assert (
            wrapper_game_running(
                marker=(APPID, 995),  # last_run do launch B (sucesso)
                exit_marker=999,  # last_exit tardio do launch A (falhou)
                pid_alive=True,  # P_B (o pid do marker atual) está vivo
                marker_pid=222,  # pid de B
                exit_pid=111,  # pid de A — DIFERENTE de marker_pid
                now=1000.0,
            )
            is True
        )

    def test_exit_do_mesmo_launch_ainda_invalida_com_pids_iguais(self) -> None:
        """Quando `exit_pid` CASA com `marker_pid` (o mesmo launch cujo
        `exec` falhou de verdade), o critério antigo se mantém: o marker
        não atesta jogo rodando."""
        assert (
            wrapper_game_running(
                marker=(APPID, 990),
                exit_marker=995,
                pid_alive=True,
                marker_pid=111,
                exit_pid=111,  # MESMO pid do marker — mesmo launch
                now=1000.0,
            )
            is False
        )

    def test_sem_pids_cai_no_criterio_antigo_so_por_epoch(self) -> None:
        """`marker_pid`/`exit_pid` ausentes (markers antigos, gravados antes
        da correção, ou leitura que falhou): fallback conservador idêntico
        ao comportamento pré-correção — exit mais novo/igual invalida."""
        assert (
            wrapper_game_running(
                marker=(APPID, 990),
                exit_marker=995,
                pid_alive=True,
                now=1000.0,
            )
            is False
        )


# --- state_full: wrapper_used + dedup_ok refletido ----------------------------


@pytest.fixture()
def server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> IpcServer:
    target = tmp_path / "profiles"
    target.mkdir()

    def fake_profiles_dir(ensure: bool = False) -> Path:
        if ensure:
            target.mkdir(parents=True, exist_ok=True)
        return target

    monkeypatch.setattr(loader_module, "profiles_dir", fake_profiles_dir)
    # Marker do wrapper em tmp (o read usa o launch_env_dir do módulo).
    monkeypatch.setattr(
        le_mod, "launch_env_dir", lambda ensure=False: tmp_path / "launch_env"
    )

    fc = FakeController(transport="usb")
    fc.connect()
    store = StateStore()
    store.update_controller_state(
        ControllerState(
            battery_pct=50, l2_raw=0, r2_raw=0, connected=True, transport="usb"
        )
    )
    daemon = SimpleNamespace(
        _last_state=None,
        config=SimpleNamespace(
            mouse_emulation_enabled=False,
            mouse_speed=6,
            mouse_scroll_speed=1,
            gamepad_emulation_enabled=True,
            gamepad_flavor="dualsense",
            coop_enabled=False,
            rumble_policy="balanceado",
            rumble_policy_custom_mult=0.7,
            rumble_active=None,
        ),
        is_paused=lambda: False,
        is_native_mode=lambda: False,
        _emulation_suppressed=False,
        _gamepad_device=SimpleNamespace(
            backend="uhid", flavor="dualsense", ff_supported=True
        ),
        _coop_manager=None,
        _mode_from_profile=None,
        _last_auto_mult=1.0,
        external_registry=None,
    )
    manager = ProfileManager(controller=fc, store=store)
    return IpcServer(
        controller=fc,
        store=store,
        profile_manager=manager,
        socket_path=tmp_path / "hefesto-dualsense4unix.sock",
        daemon=daemon,  # type: ignore[arg-type]
    )


async def test_wrapper_used_null_sem_jogo(server: IpcServer) -> None:
    result = await server._handle_daemon_state_full({})
    ge = result["gamepad_emulation"]
    assert ge["wrapper_used"] is None
    assert ge["dedup_ok"] is True, "sem jogo detectado o dedup_ok não muda"


async def test_wrapper_used_true_com_marker_fresco(
    server: IpcServer, tmp_path: Path
) -> None:
    server.store.record_window_detect_read("xlib", f"steam_app_{APPID}")
    _grava_marker(
        tmp_path / "launch_env", f"appid={APPID}\nepoch={int(time.time())}\n"
    )
    result = await server._handle_daemon_state_full({})
    ge = result["gamepad_emulation"]
    assert ge["wrapper_used"] is True
    assert ge["dedup_ok"] is True
    assert "dedup_motivo" not in ge


async def test_wrapper_used_false_sem_marker_derruba_dedup_ok(
    server: IpcServer,
) -> None:
    """O FATO 0 curado: jogo aberto sem wrapper → wrapper_used=false E o
    dedup_ok deixa de mentir (motivo `jogo_sem_wrapper`)."""
    server.store.record_window_detect_read("xlib", f"steam_app_{APPID}")
    result = await server._handle_daemon_state_full({})
    ge = result["gamepad_emulation"]
    assert ge["wrapper_used"] is False
    assert ge["dedup_ok"] is False
    assert "jogo_sem_wrapper" in ge["dedup_motivo"]


async def test_wrapper_used_false_com_marker_velho(
    server: IpcServer, tmp_path: Path
) -> None:
    epoch_velho = int(time.time() - WRAPPER_MARKER_WINDOW_SEC - 60)
    server.store.record_window_detect_read("xlib", f"steam_app_{APPID}")
    _grava_marker(
        tmp_path / "launch_env", f"appid={APPID}\nepoch={epoch_velho}\n"
    )
    result = await server._handle_daemon_state_full({})
    assert result["gamepad_emulation"]["wrapper_used"] is False


async def test_wrapper_used_false_em_nativo_nao_derruba_dedup(
    server: IpcServer,
) -> None:
    """Modo Nativo: não há env que importe (o launch_env omite DISABLE/IGNORE)
    — wrapper ausente é informativo, não quebra de dedup."""
    server.daemon.is_native_mode = lambda: True  # type: ignore[union-attr]
    server.store.record_window_detect_read("xlib", f"steam_app_{APPID}")
    result = await server._handle_daemon_state_full({})
    ge = result["gamepad_emulation"]
    assert ge["wrapper_used"] is False
    assert ge["dedup_ok"] is True
    assert "dedup_motivo" not in ge


async def test_wrapper_marker_cache_ttl(
    server: IpcServer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O marker é arquivo — o state_full (10-20 Hz) lê com cache TTL, nunca a
    cada chamada."""
    leituras = {"n": 0}
    real = le_mod.read_last_run_marker

    def contando(base_dir: Any = None) -> Any:
        leituras["n"] += 1
        return real(base_dir)

    monkeypatch.setattr(le_mod, "read_last_run_marker", contando)
    server.store.record_window_detect_read("xlib", f"steam_app_{APPID}")
    for _ in range(5):
        await server._handle_daemon_state_full({})
    assert leituras["n"] == 1
