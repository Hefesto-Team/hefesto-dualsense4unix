"""Varredura de `/proc` que detecta o jogo da Steam (PERF-PROC-SCAN-01).

Estes testes existem porque uma auditoria de 12/08/2026 apontou o buraco com
todas as letras: os 40+ testes que tocam `steam_game_running` fazem
`monkeypatch.setattr(slo, "steam_game_running", ...)` na FRONTEIRA, então a
suíte inteira **passaria idêntica se `_steam_launch_cmdline` devolvesse sempre
None**. Verde não era evidência sobre esta mudança.

O caso que motivou tudo, e que a suíte antiga não pegaria: existem processos
vivos nesta máquina cuja cmdline CONTÉM a agulha porque estão procurando por
ela (`pgrep -f 'reaper SteamLaunch AppId='` do `aurora-game-watch-daemon.sh`, a
cada 15 s). Como a varredura devolve UMA cmdline — a primeira em ordem de pid —
uma isca com pid menor que o do jogo fazia `steam_game_running()` responder True
e `steam_game_running_appid()` responder None ao mesmo tempo. O estrago: o botão
"Fechar o jogo e abrir de novo" fechava e não reabria.
"""

from __future__ import annotations

import pytest

from hefesto_dualsense4unix.integrations import steam_launch_options as slo

REAPER = (
    "/home/vitoriamaria/.steam/debian-installation/ubuntu12_32/reaper "
    "SteamLaunch AppId=1599660 -- /.../proton waitforexitandrun /.../Launcher.exe"
)
#: A isca real: um `pgrep` caçando a agulha. Note que ela termina no `=`, sem
#: appid — é exatamente isso que o `\d` da regex usa para descartá-la.
ISCA_PGREP = "pgrep -f reaper SteamLaunch AppId= "
#: A isca do ExecCondition das units systemd, que usa o truque do `[ ]`.
ISCA_EXECCOND = (
    "/bin/sh -c ! /usr/bin/pgrep -f \"SteamLaunch[ ]AppId=[0-9]\" >/dev/null 2>&1"
)


@pytest.fixture
def proc_falso(monkeypatch):
    """Instala um /proc sintético. Devolve um setter que recebe {pid: cmdline}."""

    def _instalar(mapa: dict[str, str]) -> None:
        # Sem marker: força o caminho de varredura em todos os testes que usam
        # esta fixture. O caminho rápido tem os seus próprios testes abaixo.
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
    """O caso que quebrava: isca com pid MENOR que o do jogo.

    A varredura devolve a primeira cmdline que casa, em ordem de pid. Com a
    agulha antiga (substring `SteamLaunch AppId=`), a isca casava primeiro e
    `steam_game_running_appid()` devolvia None com o jogo aberto.
    """
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
    """Invariante de construção: se casou, há appid para extrair."""
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
    """Marker global sobrevive ao jogo: pid morto tem de cair no fallback.

    É o ESTADO PERMANENTE de um daemon 24/7 com o jogo fechado — o marker fica
    no disco apontando para um pid que já morreu.
    """

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
    # pid do marker não devolve nada (morreu); o jogo está em outro pid.
    monkeypatch.setattr(
        slo, "_cmdline_of", lambda pid: "" if str(pid) == "62720" else REAPER
    )
    monkeypatch.setattr(slo.os, "listdir", lambda path: ["777"])
    assert slo.steam_game_running_appid() == 1599660


def test_marker_de_outro_appid_nao_confirma(monkeypatch):
    """Marker apontando para appid diferente do que roda no pid: não confirma.

    E o `\\b` impede o casamento por prefixo — appid 159 não pode confirmar
    contra um jogo 1599660.
    """

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
    # Caiu na varredura (que está vazia) em vez de confirmar errado.
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
