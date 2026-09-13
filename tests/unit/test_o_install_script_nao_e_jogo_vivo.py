"""JOGO-SEM-EXCLUSIVIDADE-01 (13/09/2026) — o install script não é jogo vivo.

A Steam roda o avaliador do install script de um jogo ANTES do jogo, e ele
carrega a mesma agulha do lançamento: ``reaper SteamLaunch AppId=<id>
Install=1 -- …``. Medido no log da Steam e no journal: o avaliador pôs a
autoridade de exibição em `game` 4 a 5 s antes do ping do wrapper, e o
lançamento caiu no ramo `jogo_vivo` (`ponte_escada_nao_arma motivo=jogo_vivo`)
em 6 de 6 aberturas — sem primeiro degrau, sem `.env` por jogo, sem confirmação
por silêncio. Os jogos sem install script armaram pelo ping.

Este arquivo trava as duas perguntas separadas:

1. **qual jogo está aberto** (`steam_game_running_appid`, a evidência E4 do
   sinal de jogo) — o avaliador responde None;
2. **há algo que fechar a Steam mataria** (`steam_game_running`, o guarda do
   `steam -shutdown`) — o avaliador responde True.

E o fio inteiro, com dublê: a linha do avaliador → `classify` → a autoridade →
`arm_launch_profile` → `ponte_tentativa.comecar` com `primeiro_degrau`.
Arrancar a exclusão devolve `jogo_vivo`, que é a linha do journal.
"""

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

#: A forma da linha do log da Steam, com o appid como parâmetro: a cura é por
#: assinatura, e os dois appids abaixo são os dois que rodaram o avaliador nos
#: logs de 13/09 — nenhum deles é citado pelo produto.
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


# ---------------------------------------------------------------------------
# 1. As duas perguntas, separadas
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("appid", _APPIDS)
def test_o_avaliador_segura_a_steam_mas_nao_e_jogo(
    monkeypatch: pytest.MonkeyPatch, appid: int
) -> None:
    """A MORDIDA da agulha. Arranque o `e_avaliador_do_install_script` de
    `steam_game_running_appid` e o appid volta — a evidência E4 do journal."""
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
    """A varredura devolve UMA cmdline. O jogo vence, qualquer que seja a
    ordem dos pids. MORDE a preferência da camada 4 de `_steam_launch_cmdline`:
    sem ela, o avaliador de pid menor esconde o jogo e o appid some."""
    _instalar_proc(monkeypatch, mapa)

    assert slo.steam_game_running_appid() == 4235410


def test_a_foto_do_avaliador_nao_esconde_o_jogo_que_nasce_depois(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A varredura tem memória (BG-03): o pid achado é reconfirmado sem varrer.

    Com o avaliador na foto, reconfirmar só ele deixaria o jogo que nasceu ao
    lado invisível enquanto o avaliador vivesse. MORDE o `foto = None` da camada
    2: sem ele, a segunda pergunta ainda responde None.
    """
    mapa = {"100": _AVALIADOR.format(appid=1599660)}
    _instalar_proc(monkeypatch, mapa)
    assert slo.steam_game_running_appid() is None

    mapa["200"] = _JOGO.format(appid=1599660)

    assert slo.steam_game_running_appid() == 1599660


# ---------------------------------------------------------------------------
# 2. O fio inteiro: a linha do avaliador até o primeiro degrau da escada
# ---------------------------------------------------------------------------
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
    """Um tique do sinal de jogo com SÓ esta cmdline viva e o detector são.

    O marker do wrapper ainda não existe: é o instante do journal, 4 a 5 s
    antes do ping, em que só o avaliador está de pé.
    """
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
    """A MORDIDA do fio. Arranque a exclusão em `steam_game_running_appid` e a
    autoridade vira `game`, o `comecar` responde `jogo_vivo` e nada é armado —
    a linha `ponte_escada_nao_arma motivo=jogo_vivo` das 05:00:20."""
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
    """O dublê sabe RECUSAR: com o reaper do JOGO de pé, o mesmo fio dá
    `jogo_vivo`. Sem esta metade, um `primeiro_degrau` fixo passaria."""
    autoridade = _autoridade_do_tique(monkeypatch, _JOGO.format(appid=APPID))
    assert autoridade == "game"

    resultado, motivos, daemon = _armar(monkeypatch, tmp_path, autoridade)

    assert motivos == [pt.COMECO_JOGO_VIVO], motivos
    assert resultado is not None
    assert resultado["armado"] is False
    assert daemon.aplicados == []
