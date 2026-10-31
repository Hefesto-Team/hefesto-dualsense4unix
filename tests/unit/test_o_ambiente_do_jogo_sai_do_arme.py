"""O ambiente do jogo sai do arme, com a receita, e é o mesmo no arquivo e na resposta.

Sprint O-AMBIENTE-DO-JOGO-SAI-DO-ARME-COM-A-RECEITA-E-SEM-O-MODO-VIVO-01.

O ``steam_app_<id>.env`` e o bloco ``ambiente`` do ``daemon.status {appid}`` saem de um dono só
(``o_ambiente_do_jogo``). As réguas medem as três divergências que a conta dupla deixava: a roupa
do jogo sem perfil lida do pad de pé, e não do arme; a receita que só o arquivo levava; e as
linhas do arquivo e da resposta para cada appid.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon import launch_env as le
from hefesto_dualsense4unix.daemon.subsystems import gamepad
from hefesto_dualsense4unix.profiles.schema import MatchCriteria, Profile, ProfileModeConfig
from tests.unit.test_o_jogo_so_nasce_com_o_ambiente_do_proprio_arme import (
    APPID,
    LENTA_S,
    TETO_S,
    _a_mesa_do_lancamento,
    _env_dir,
    _marker,
    _Mesa,
    _runtime,
    _ServidorNoFio,
    _sock,
)

_ROOT = Path(__file__).resolve().parents[2]
_WRAPPER = _ROOT / "assets" / "hefesto-launch.sh"
_VELHA = "dinput8=n"
_NOVA = "xgameruntime=b"


@pytest.fixture
def sem_escrevente(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(le, "_ESCREVENTE", None)
    yield
    escrevente = le._ESCREVENTE
    if escrevente is not None:
        le.desarmar_o_escrevente(escrevente)


@pytest.fixture
def runtime() -> Iterator[Path]:
    base = _runtime()
    yield base
    shutil.rmtree(base, ignore_errors=True)


def _o_pad_fica_no_padrao(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """O pad de pé não troca de roupa no arme (o fio do co-op ainda não entregou)."""
    pedidas: list[int] = []
    monkeypatch.setattr(gamepad, "vestir_a_roupa", lambda _d, roupa: pedidas.append(roupa) or [])
    monkeypatch.setattr(gamepad, "a_roupa_que_o_pad_veste", lambda _d: le.ROUPA_PADRAO)
    return pedidas


def _do_ambiente(texto: str) -> list[str]:
    return [
        linha for linha in texto.splitlines()
        if linha and not linha.startswith("#") and linha.split("=", 1)[0] in le.ENV_ALLOWLIST
    ]


def _da_receita(texto: str) -> list[str]:
    return [linha for linha in texto.splitlines() if linha.startswith("WINEDLL")]


def test_o_jogo_sem_perfil_com_a_roupa_comum_responde_o_comum_com_o_pad_ainda_no_padrao(
    sem_escrevente: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A prova (1): a roupa sai do arme (a gravada no disco), e não do pad de pé naquele instante.

    O arquivo que a escrita grava depois traz as mesmas linhas que a resposta deu ao wrapper.
    """
    _a_mesa_do_lancamento(tmp_path, monkeypatch, None, em_disco=[], lenta_s=0.0)  # type: ignore[arg-type]
    monkeypatch.setattr(le, "_steam_profiles", lambda _daemon: [])
    monkeypatch.setattr(le, "_jogos_do_comum", lambda _foto: {str(APPID): "sdl"})
    pedidas = _o_pad_fica_no_padrao(monkeypatch)
    do_jogo = tmp_path / f"steam_app_{APPID}.env"
    do_jogo.write_text("# roupa: 0ce6 (sdl)\n", encoding="utf-8")
    antes = time.time() - 60
    os.utime(do_jogo, (antes, antes))
    _marker(tmp_path)
    daemon: Any = _Mesa(flavor="dualsense")
    bloco = le.o_ambiente_no_status(daemon, {"appid": APPID})
    assert pedidas == [le.ROUPA_COMUM], f"o arme não pediu a roupa comum: {pedidas}"
    linhas = bloco["ambiente"]["linhas"]
    le.materialize_launch_env(daemon)
    padrao = _do_ambiente((tmp_path / "default.env").read_text(encoding="utf-8"))
    assert linhas != padrao, "a roupa comum não muda o ambiente: a régua não distingue"
    assert linhas == _do_ambiente(do_jogo.read_text(encoding="utf-8")), (
        f"a resposta não é o arquivo do jogo:\n{linhas}\n{do_jogo.read_text(encoding='utf-8')}")


def test_o_jogo_sem_perfil_depois_de_um_jogo_em_xbox_nao_traz_o_hidapi_desligado(
    sem_escrevente: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A prova (2): o jogo sem perfil sai do modo do computador, e não do Xbox do jogo anterior."""
    _a_mesa_do_lancamento(
        tmp_path, monkeypatch,
        _perfil(APPID, ProfileModeConfig(kind="gamepad", gamepad_flavor="xbox")),
        em_disco=[], lenta_s=0.0)
    daemon: Any = _Mesa(flavor="dualsense")
    _marker(tmp_path)
    le.o_ambiente_no_status(daemon, {"appid": APPID})
    daemon.o_fio_entrega()
    assert daemon._gamepad_device.flavor == "xbox", "premissa: o jogo anterior vestiu o Xbox"
    outro = APPID + 1
    (tmp_path / "last_run").write_text(
        f"appid={outro}\nepoch={int(time.time()) + 1}\npid=1\n", encoding="utf-8")
    linhas = le.o_ambiente_no_status(daemon, {"appid": outro})["ambiente"]["linhas"]
    assert linhas, "o jogo sem perfil ficou sem ambiente"
    assert "SDL_JOYSTICK_HIDAPI=0" not in linhas, f"o jogo sem perfil herdou o Xbox: {linhas}"


def _a_peca(lar: Path) -> None:
    pasta = lar / ".local" / "share" / "hefesto-dualsense4unix" / "wine" / "x86_64-windows"
    pasta.mkdir(parents=True)
    (pasta / "xgameruntime.dll").write_bytes(b"MZ a peca de mentira do teste")


def _o_wrapper(runtime: Path, state_home: Path) -> tuple[subprocess.CompletedProcess[str], float]:
    mudos = runtime / "game-mode-mudo"
    mudos.mkdir(exist_ok=True)
    lar = runtime / "lar"
    _a_peca(lar)
    for nome in ("system76-power", "busctl", "dbus-send", "systemd-run"):
        falso = mudos / nome
        falso.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        falso.chmod(0o755)
    env = {
        "PATH": f"{mudos}:{os.environ.get('PATH', '/usr/bin:/bin')}",
        "HOME": str(lar),
        "XDG_CONFIG_HOME": str(lar / ".config"),
        "XDG_RUNTIME_DIR": str(runtime),
        "XDG_STATE_HOME": str(state_home),
        "SteamAppId": str(APPID),
        "HEFESTO_PLACA_ACORDADA": str(runtime / "sem-placa"),
        "HEFESTO_SYSFS": str(runtime / "sys-vazio"),
    }
    t0 = time.monotonic()
    feito = subprocess.run(
        ["sh", str(_WRAPPER), "sh", "-c",
         'printf "%s|%s" "${WINEDLLOVERRIDES-ausente}" "${WINEDLLPATH-ausente}"'],
        env=env, capture_output=True, text=True, timeout=30, check=False)
    return feito, time.monotonic() - t0


def test_a_receita_nova_chega_ao_jogo_pela_resposta_com_o_arquivo_velho_em_disco(
    sem_escrevente: None, runtime: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A prova (3): o wrapper de verdade contra o ``IpcServer`` de verdade.

    Em disco, o arquivo do jogo tem a receita velha; a escrita do fio escrevente leva
    ``LENTA_S``. O jogo recebe o ``WINEDLLOVERRIDES`` da receita de agora, em menos de ``TETO_S``.
    """
    from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
    from hefesto_dualsense4unix.daemon.state_store import StateStore
    from hefesto_dualsense4unix.profiles.manager import ProfileManager
    from hefesto_dualsense4unix.testing import FakeController

    state_home = tmp_path / "state"
    env_dir = _env_dir(state_home)
    _a_mesa_do_lancamento(env_dir, monkeypatch, None, lenta_s=LENTA_S)  # type: ignore[arg-type]
    monkeypatch.setattr(le, "_steam_profiles", lambda _daemon: [])
    monkeypatch.setattr(
        le, "_receitas_dos_jogos",
        lambda: {str(APPID): {"WINEDLLOVERRIDES": _NOVA, "WINEDLLPATH": "@hefesto-wine"}})
    (env_dir / f"steam_app_{APPID}.env").write_text(
        f"WINEDLLOVERRIDES={_VELHA}\n", encoding="utf-8")
    fc = FakeController(transport="usb")
    fc.connect()
    store = StateStore()
    server = IpcServer(
        controller=fc, store=store, profile_manager=ProfileManager(controller=fc, store=store),
        socket_path=_sock(runtime), daemon=_Mesa(store))
    no_ar = _ServidorNoFio(server)
    try:
        feito, gasto = _o_wrapper(runtime, state_home)
    finally:
        no_ar.parar()
    assert feito.returncode == 0, feito.stderr
    dll, _, pasta = feito.stdout.partition("|")
    assert dll == _NOVA, f"o jogo recebeu a receita do arquivo velho: {feito.stdout}"
    assert pasta.endswith("/hefesto-dualsense4unix/wine"), feito.stdout
    assert gasto < TETO_S, f"o lançamento esperou {gasto:.2f} s"


_OS_JOGOS = {
    9931101: ProfileModeConfig(kind="gamepad", gamepad_flavor="dualsense"),
    9931102: ProfileModeConfig(kind="gamepad", gamepad_flavor="xbox"),
    9931103: None,
}
_DO_COMUM = {"9931101": "sdl", "9931104": "sdl"}
_RECEITAS = {
    "9931102": {"WINEDLLOVERRIDES": _NOVA, "WINEDLLPATH": "@hefesto-wine"},
    "9931105": {"WINEDLLOVERRIDES": _VELHA},
}


def _perfil(appid: int, mode: ProfileModeConfig | None) -> Profile:
    return Profile(
        name=f"Jogo {appid}", match=MatchCriteria(window_class=[f"steam_app_{appid}"]),
        priority=90, mode=mode)


@pytest.mark.parametrize("flavor", ["dualsense", "xbox"])
def test_para_todo_appid_o_arquivo_e_a_resposta_dizem_as_mesmas_linhas(
    flavor: str, sem_escrevente: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A prova (4): perfil com modo e sem modo, jogo do comum, receita, e o jogo sem nada."""
    _a_mesa_do_lancamento(tmp_path, monkeypatch, None, em_disco=[], lenta_s=0.0)  # type: ignore[arg-type]
    perfis = [(appid, _perfil(appid, modo)) for appid, modo in _OS_JOGOS.items()]
    monkeypatch.setattr(le, "_steam_profiles", lambda _daemon: perfis)
    monkeypatch.setattr(le, "_jogos_do_comum", lambda _foto: dict(_DO_COMUM))
    monkeypatch.setattr(
        le, "_receitas_dos_jogos", lambda: {k: dict(v) for k, v in _RECEITAS.items()})
    daemon: Any = _Mesa(flavor=flavor)
    le.materialize_launch_env(daemon)
    todos = sorted({*_OS_JOGOS, *map(int, _DO_COMUM), *map(int, _RECEITAS), 9931106})
    escritos = 0
    for appid in todos:
        arquivo = tmp_path / f"steam_app_{appid}.env"
        if not arquivo.exists():
            arquivo = tmp_path / "default.env"
        else:
            escritos += 1
        texto = arquivo.read_text(encoding="utf-8")
        resposta = le.ambiente_do_lancamento(daemon, appid)
        assert resposta["linhas"] == _do_ambiente(texto), (appid, resposta, texto)
        assert resposta["receita"] == _da_receita(texto), (appid, resposta, texto)
    minimo = {"dualsense": 4, "xbox": 3}[flavor]
    assert escritos >= minimo, f"só {escritos} arquivos de jogo: a régua não cobre os ramos"
