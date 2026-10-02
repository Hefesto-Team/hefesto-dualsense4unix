"""JOGO-SEM-EXCLUSIVIDADE-01 (13/09/2026) — o install script não é jogo vivo."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon import launch_env as le
from hefesto_dualsense4unix.daemon.subsystems.game_signal import GameSignal, classify
from hefesto_dualsense4unix.integrations import ponte_tentativa as pt
from hefesto_dualsense4unix.integrations import steam_launch_options as slo
from hefesto_dualsense4unix.profiles.schema import MatchCriteria, Profile

_AVALIADOR = (
    "~/.steam/debian-installation/ubuntu12_32/reaper SteamLaunch AppId={appid} "
    "Install=1 -- ~/.steam/debian-installation/ubuntu12_32/steam-launch-wrapper "
    "-- /.../installscript-evaluator "
)
_JOGO = (
    "~/.steam/debian-installation/ubuntu12_32/reaper SteamLaunch AppId={appid} "
    "-- /.../proton waitforexitandrun /.../Jogo.exe "
)
_APPIDS = (1599660, 2424420)


class _ModuloSemMarker:
    """Stand-in de `daemon.launch_env` sem marker: o caminho rápido falha."""

    @staticmethod
    def read_last_run_marker() -> None:
        return None

    @staticmethod
    def read_last_run_pid() -> None:
        return None


@pytest.fixture(autouse=True)
def _sem_foto_herdada() -> Any:
    slo.invalidar_varredura_de_proc()
    yield
    slo.invalidar_varredura_de_proc()


def _instalar_proc(monkeypatch: pytest.MonkeyPatch, mapa: dict[str, str]) -> None:
    monkeypatch.setattr(slo, "_cmdline_of", lambda pid: mapa.get(str(pid), ""))
    monkeypatch.setattr(slo.os, "listdir", lambda path: [*mapa, "self"])
    monkeypatch.setitem(
        sys.modules, "hefesto_dualsense4unix.daemon.launch_env", _ModuloSemMarker()
    )


@pytest.mark.parametrize("appid", _APPIDS)
def test_o_avaliador_segura_a_steam_mas_nao_e_jogo(
    monkeypatch: pytest.MonkeyPatch, appid: int
) -> None:
    """A MORDIDA da agulha. Arranque o `e_avaliador_do_install_script` de"""
    _instalar_proc(monkeypatch, {"100": _AVALIADOR.format(appid=appid)})

    assert slo.steam_game_running_appid() is None
    assert slo.steam_game_running() is True, (
        "fechar a Steam no meio do install script aborta o lançamento: o guarda "
        "do `steam -shutdown` tem de continuar vendo o avaliador"
    )


def test_o_token_so_vale_nos_argumentos_do_reaper() -> None:
    """`Install=1` depois do `--` é argumento do JOGO, não do avaliador."""
    jogo_com_o_token = _JOGO.format(appid=1599660) + "Install=1 "
    assert slo.e_avaliador_do_install_script(_AVALIADOR.format(appid=1599660))
    assert not slo.e_avaliador_do_install_script(jogo_com_o_token)
    assert not slo.e_avaliador_do_install_script(_JOGO.format(appid=1599660))
    assert not slo.e_avaliador_do_install_script("pgrep -f SteamLaunch AppId= Install=1")


def test_o_jogo_de_verdade_continua_sendo_jogo(monkeypatch: pytest.MonkeyPatch) -> None:
    """Contraprova: a régua sabe dizer "jogo". Sem ela, um None fixo passaria."""
    _instalar_proc(monkeypatch, {"100": _JOGO.format(appid=1599660)})

    assert slo.steam_game_running_appid() == 1599660
    assert slo.steam_game_running() is True


@pytest.mark.parametrize(
    "mapa",
    [
        {"100": _AVALIADOR.format(appid=1599660), "200": _JOGO.format(appid=4235410)},
        {"100": _JOGO.format(appid=4235410), "200": _AVALIADOR.format(appid=1599660)},
    ],
    ids=["avaliador-com-pid-menor", "avaliador-com-pid-maior"],
)
def test_o_avaliador_nao_esconde_o_jogo_que_convive_com_ele(
    monkeypatch: pytest.MonkeyPatch, mapa: dict[str, str]
) -> None:
    """A varredura devolve UMA cmdline. O jogo vence, qualquer que seja a"""
    _instalar_proc(monkeypatch, mapa)

    assert slo.steam_game_running_appid() == 4235410


def test_a_foto_do_avaliador_nao_esconde_o_jogo_que_nasce_depois(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A varredura tem memória (BG-03): o pid achado é reconfirmado sem varrer."""
    mapa = {"100": _AVALIADOR.format(appid=1599660)}
    _instalar_proc(monkeypatch, mapa)
    assert slo.steam_game_running_appid() is None

    mapa["200"] = _JOGO.format(appid=1599660)

    assert slo.steam_game_running_appid() == 1599660


APPID = 1599660
EPOCH = 1000


class _DaemonFalso:
    """Mesa em `xbox`/uhid; a autoridade vem do sinal de jogo, não à mão."""

    def __init__(self, *, authority: str) -> None:
        self.aplicados: list[tuple[Any, Any, str]] = []
        self.config = SimpleNamespace(gamepad_emulation_enabled=True, gamepad_flavor="xbox")
        self._gamepad_device = SimpleNamespace(backend="uhid", flavor="xbox")
        self._coop_manager = None
        self.controller = SimpleNamespace()
        self.display_authority = authority

    def is_native_mode(self) -> bool:
        return False

    def apply_profile_mode(
        self, mode: Any, *, profile: Any = None, origin: str = "autoswitch"
    ) -> str:
        self.aplicados.append((mode, profile, origin))
        if getattr(mode, "kind", None) == "gamepad":
            self.config.gamepad_flavor = mode.gamepad_flavor
            self._gamepad_device = SimpleNamespace(
                backend="uhid", flavor=mode.gamepad_flavor
            )
        return "aplicado"


def _autoridade_do_tique(monkeypatch: pytest.MonkeyPatch, cmdline: str) -> str:
    """Um tique do sinal de jogo com SÓ esta cmdline viva e o detector são."""
    with monkeypatch.context() as m:
        _instalar_proc(m, {"100": cmdline})
        appid = slo.steam_game_running_appid()
    bruto = classify(
        window_healthy=True,
        window_class_current=None,
        window_seen_age=None,
        profile_rule_match=False,
        marker=None,
        marker_pid_alive=False,
        exit_marker=None,
        session_open=True,
        now=float(EPOCH),
        appid_de_jogo_vivo=appid,
    )
    return GameSignal().evaluate(bruto, session_open=True)


def _armar(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, autoridade: str) -> tuple[
    dict[str, Any] | None, list[str], _DaemonFalso
]:
    monkeypatch.setattr(le, "launch_env_dir", lambda ensure=False: tmp_path)
    monkeypatch.setattr(le, "materialize_launch_env", lambda daemon: None)
    monkeypatch.setattr(le, "steam_input_appids", lambda path=None: set())
    perfil = Profile(
        name="jogo-com-install-script",
        match=MatchCriteria(window_class=[f"steam_app_{APPID}"]),
        priority=80,
    )
    monkeypatch.setattr(le, "_steam_profiles", lambda d: [(APPID, perfil)])
    (tmp_path / "last_run").write_text(
        f"appid={APPID}\nepoch={EPOCH}\npid=1\n", encoding="utf-8"
    )
    motivos: list[str] = []
    comecar_de_verdade = pt.comecar

    def _comecar_espiado(*args: Any, **kwargs: Any) -> Any:
        comeco = comecar_de_verdade(*args, **kwargs)
        motivos.append(comeco.motivo)
        return comeco

    monkeypatch.setattr(pt, "comecar", _comecar_espiado)
    daemon = _DaemonFalso(authority=autoridade)
    resultado = le.arm_launch_profile(daemon, base_dir=tmp_path, now=EPOCH + 1.0)
    return resultado, motivos, daemon


def test_com_o_avaliador_vivo_o_lancamento_arma_o_primeiro_degrau(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A MORDIDA do fio. Arranque a exclusão em `steam_game_running_appid` e a"""
    autoridade = _autoridade_do_tique(monkeypatch, _AVALIADOR.format(appid=APPID))

    resultado, motivos, daemon = _armar(monkeypatch, tmp_path, autoridade)

    assert motivos == [pt.COMECO_PRIMEIRO_DEGRAU], (
        f"o lançamento caiu em {motivos} com a autoridade em {autoridade!r}"
    )
    assert autoridade != "game", "o avaliador do install script subiu a autoridade"
    assert resultado is not None
    assert resultado["escada"] == pt.COMECO_PRIMEIRO_DEGRAU
    assert resultado["armado"] is True
    assert [m.gamepad_flavor for m, _p, _o in daemon.aplicados] == ["dualsense"]


def test_contraprova_com_o_jogo_vivo_o_lancamento_nao_arma(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """O dublê sabe RECUSAR: com o reaper do JOGO de pé, o mesmo fio dá"""
    autoridade = _autoridade_do_tique(monkeypatch, _JOGO.format(appid=APPID))
    assert autoridade == "game"

    resultado, motivos, daemon = _armar(monkeypatch, tmp_path, autoridade)

    assert motivos == [pt.COMECO_JOGO_VIVO], motivos
    assert resultado is not None
    assert resultado["armado"] is False
    assert daemon.aplicados == []
