"""Varredura de `/proc` que detecta o jogo da Steam (PERF-PROC-SCAN-01)."""

from __future__ import annotations

import pytest

from hefesto_dualsense4unix.integrations import steam_launch_options as slo

REAPER = (
    "/home/vitoriamaria/.steam/debian-installation/ubuntu12_32/reaper "
    "SteamLaunch AppId=1599660 -- /.../proton waitforexitandrun /.../Launcher.exe"
)
ISCA_PGREP = "pgrep -f reaper SteamLaunch AppId= "
ISCA_EXECCOND = (
    "/bin/sh -c ! /usr/bin/pgrep -f \"SteamLaunch[ ]AppId=[0-9]\" >/dev/null 2>&1"
)


@pytest.fixture(autouse=True)
def _sem_foto_herdada():
    """A varredura ganhou memória na BG-03 (25/08/2026) — e memória vaza."""
    slo.invalidar_varredura_de_proc()
    yield
    slo.invalidar_varredura_de_proc()


@pytest.fixture
def proc_falso(monkeypatch):
    """Instala um /proc sintético. Devolve um setter que recebe {pid: cmdline}."""

    def _instalar(mapa: dict[str, str]) -> None:
        monkeypatch.setattr(slo, "_cmdline_of", lambda pid: mapa.get(str(pid), ""))
        monkeypatch.setattr(
            slo.os, "listdir", lambda path: [*mapa, "self", "cpuinfo"]
        )
        import sys

        monkeypatch.setitem(
            sys.modules,
            "hefesto_dualsense4unix.daemon.launch_env",
            _ModuloSemMarker(),
        )

    return _instalar


class _ModuloSemMarker:
    """Stand-in de `daemon.launch_env` sem marker (o caminho rápido falha)."""

    @staticmethod
    def read_last_run_marker():
        return None

    @staticmethod
    def read_last_run_pid():
        return None


def test_so_isca_nao_e_jogo(proc_falso):
    """A isca sozinha não pode virar 'há jogo' — era falso-positivo antigo."""
    proc_falso({"100": ISCA_PGREP, "101": "cosmic-comp"})
    assert slo.steam_game_running() is False
    assert slo.steam_game_running_appid() is None


def test_isca_com_pid_menor_nao_esconde_o_jogo(proc_falso):
    """O caso que quebrava: isca com pid MENOR que o do jogo."""
    proc_falso({"100": ISCA_PGREP, "200": REAPER})
    assert slo.steam_game_running() is True
    assert slo.steam_game_running_appid() == 1599660


def test_isca_com_pid_maior_tambem(proc_falso):
    """A ordem inversa também: o resultado não pode depender do sorteio de pid."""
    proc_falso({"100": REAPER, "200": ISCA_PGREP})
    assert slo.steam_game_running() is True
    assert slo.steam_game_running_appid() == 1599660


def test_execcondition_das_units_nao_casa(proc_falso):
    """O `[ ]` das units systemd quebra a substring — não pode virar jogo."""
    proc_falso({"100": ISCA_EXECCOND})
    assert slo.steam_game_running() is False
    assert slo.steam_game_running_appid() is None


def test_running_e_appid_nunca_discordam(proc_falso):
    """Se casou, há appid — fora o avaliador do install script (13/09/2026)."""
    for mapa in (
        {"1": ISCA_PGREP, "2": REAPER},
        {"1": REAPER},
        {"1": ISCA_PGREP},
        {"1": ISCA_EXECCOND, "2": "kthreadd"},
        {},
    ):
        proc_falso(mapa)
        assert slo.steam_game_running() is (slo.steam_game_running_appid() is not None)


def test_cmdline_vazia_e_proc_sem_jogo(proc_falso):
    """Kernel threads têm cmdline vazia; nada disso pode explodir nem casar."""
    proc_falso({"2": "", "3": "", "4": "cosmic-panel"})
    assert slo.steam_game_running() is False


def test_listdir_falhando_nao_levanta(monkeypatch):
    """/proc ilegível devolve None, nunca exceção para quem chamou."""

    def _boom(path):
        raise OSError("sem /proc")

    monkeypatch.setattr(slo.os, "listdir", _boom)
    import sys

    monkeypatch.setitem(
        sys.modules,
        "hefesto_dualsense4unix.daemon.launch_env",
        _ModuloSemMarker(),
    )
    assert slo._steam_launch_cmdline() is None
    assert slo.steam_game_running() is False


def test_caminho_rapido_usa_o_marker(monkeypatch):
    """Com marker válido, resolve sem varrer /proc nenhum."""

    class _ComMarker:
        @staticmethod
        def read_last_run_marker():
            return (1599660, 1786513632)

        @staticmethod
        def read_last_run_pid():
            return 62720

    import sys

    monkeypatch.setitem(
        sys.modules, "hefesto_dualsense4unix.daemon.launch_env", _ComMarker()
    )
    monkeypatch.setattr(slo, "_cmdline_of", lambda pid: REAPER if pid == 62720 else "")

    def _nao_deve_varrer(path):  # pragma: no cover - só falha se for chamado
        raise AssertionError("varreu /proc apesar do marker válido")

    monkeypatch.setattr(slo.os, "listdir", _nao_deve_varrer)
    assert slo.steam_game_running_appid() == 1599660


def test_marker_com_pid_morto_cai_na_varredura(monkeypatch):
    """Marker global sobrevive ao jogo: pid morto tem de cair no fallback."""

    class _MarkerVelho:
        @staticmethod
        def read_last_run_marker():
            return (1599660, 1)

        @staticmethod
        def read_last_run_pid():
            return 62720

    import sys

    monkeypatch.setitem(
        sys.modules, "hefesto_dualsense4unix.daemon.launch_env", _MarkerVelho()
    )
    monkeypatch.setattr(
        slo, "_cmdline_of", lambda pid: "" if str(pid) == "62720" else REAPER
    )
    monkeypatch.setattr(slo.os, "listdir", lambda path: ["777"])
    assert slo.steam_game_running_appid() == 1599660


def test_marker_de_outro_appid_nao_confirma(monkeypatch):
    """Marker apontando para appid diferente do que roda no pid: não confirma."""

    class _MarkerPrefixo:
        @staticmethod
        def read_last_run_marker():
            return (159, 1)

        @staticmethod
        def read_last_run_pid():
            return 62720

    import sys

    monkeypatch.setitem(
        sys.modules, "hefesto_dualsense4unix.daemon.launch_env", _MarkerPrefixo()
    )
    monkeypatch.setattr(slo, "_cmdline_of", lambda pid: REAPER)
    monkeypatch.setattr(slo.os, "listdir", lambda path: [])
    assert slo.steam_game_running_appid() is None


def test_import_do_marker_falhando_cai_na_varredura(monkeypatch):
    """Sem venv (uninstall.sh roda o módulo avulso), o ImportError é esperado."""
    import builtins

    real_import = builtins.__import__

    def _sem_daemon(nome, *args, **kwargs):
        if nome.startswith("hefesto_dualsense4unix.daemon"):
            raise ImportError("sem venv")
        return real_import(nome, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _sem_daemon)
    monkeypatch.setattr(slo, "_cmdline_of", lambda pid: REAPER)
    monkeypatch.setattr(slo.os, "listdir", lambda path: ["500"])
    assert slo.steam_game_running_appid() == 1599660
