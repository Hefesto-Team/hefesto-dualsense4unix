"""O jogo só nasce com o ambiente do próprio arme.

Sprint O-JOGO-SO-NASCE-COM-O-AMBIENTE-DO-PROPRIO-ARME-01.

Medido em 31/10/2026: o arme do appid 1875580 subiu a escada para ``gamepad/dualsense`` às
05:26:00, mas o wrapper leu o ``default.env`` escrito às 05:25:41 com ``mascara=xbox``
(``SDL_JOYSTICK_HIDAPI=0``); o arquivo seguinte só saiu 41 s depois do lançamento. As réguas
armam um jogo DualSense com o ``default.env`` do Xbox em disco e a escrita do fio escrevente
lenta (``LENTA_S``), e medem o ambiente que o wrapper recebe.
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import socket
import subprocess
import tempfile
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon import launch_env as le
from hefesto_dualsense4unix.profiles.schema import MatchCriteria, Profile, ProfileModeConfig

APPID = 9931031
LENTA_S = 3.0
TETO_S = 1.0
_ROOT = Path(__file__).resolve().parents[2]
_WRAPPER = _ROOT / "assets" / "hefesto-launch.sh"
_PROBE = (
    'printf "IGNORE=%s|HIDAPI=%s|HIDRAW=%s\\n" '
    '"$SDL_GAMECONTROLLER_IGNORE_DEVICES" "$SDL_JOYSTICK_HIDAPI" "$PROTON_DISABLE_HIDRAW"'
)
_XBOX = [
    "# estado: native=False emulacao=True mascara=xbox backends=['uinput']",
    "SDL_JOYSTICK_HIDAPI=0",
    "PROTON_DISABLE_HIDRAW=0x054C/0x0CE6",
    "SDL_GAMECONTROLLER_IGNORE_DEVICES=0x054c/0x0ce6,0x28de/0x11ff",
]
_DUALSENSE = [
    "PROTON_DISABLE_HIDRAW=0x054C/0x0CE6",
    "SDL_GAMECONTROLLER_IGNORE_DEVICES=0x054c/0x0ce6,0x28de/0x11ff",
]


class _Mesa:
    """O daemon em ``xbox``/uinput; o modo do arme veste ``dualsense``/uhid."""

    def __init__(self, store: Any = None) -> None:
        self.config = SimpleNamespace(gamepad_emulation_enabled=True, gamepad_flavor="xbox")
        self._gamepad_device = SimpleNamespace(backend="uinput", flavor="xbox")
        self._coop_manager = None
        self.controller = SimpleNamespace()
        self.store = store
        self.aplicados: list[Any] = []

    def is_native_mode(self) -> bool:
        return False

    def is_paused(self) -> bool:
        return False

    def apply_profile_mode(self, mode: Any, *, profile: Any = None, origin: str = "") -> str:
        self.aplicados.append(mode)
        if getattr(mode, "kind", None) == "gamepad":
            self.config.gamepad_flavor = mode.gamepad_flavor
            self._gamepad_device = SimpleNamespace(backend="uhid", flavor=mode.gamepad_flavor)
        return "aplicado"

    def apply_profile_suppression(
        self, desired: bool, *, profile: Any = None, origin: str = ""
    ) -> str:
        return "aplicado"


def _perfil(mode: ProfileModeConfig | None) -> Profile:
    return Profile(
        name="Jogo da Régua",
        match=MatchCriteria(window_class=[f"steam_app_{APPID}"]),
        priority=90,
        mode=mode,
    )


_PERFIS = {
    "sem_modo_a_escada": None,
    "modo_dualsense": ProfileModeConfig(kind="gamepad", gamepad_flavor="dualsense"),
}


@pytest.fixture
def sem_escrevente(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(le, "_ESCREVENTE", None)
    yield
    escrevente = le._ESCREVENTE
    if escrevente is not None:
        le.desarmar_o_escrevente(escrevente)


def _a_mesa_do_lancamento(
    env_dir: Path, monkeypatch: pytest.MonkeyPatch, perfil: Profile
) -> Callable[[], int]:
    """O disco com o ``default.env`` do Xbox, a escrita lenta, e quantas escritas acabaram."""
    from hefesto_dualsense4unix.integrations import cura_por_estrada
    from hefesto_dualsense4unix.profiles import manager

    env_dir.mkdir(parents=True, exist_ok=True)
    (env_dir / "default.env").write_text("\n".join(_XBOX) + "\n", encoding="utf-8")
    monkeypatch.setattr(le, "launch_env_dir", lambda ensure=False: env_dir)
    monkeypatch.setattr(le, "_steam_profiles", lambda _daemon: [(APPID, perfil)])
    monkeypatch.setattr(le, "steam_input_appids", lambda path=None: set())
    monkeypatch.setattr(le, "_receitas_dos_jogos", lambda: {})
    monkeypatch.setattr(le, "_jogos_do_comum", lambda _foto: {})
    monkeypatch.setattr(le, "_device_ks_nos_lancadores", lambda: None)
    monkeypatch.setattr(cura_por_estrada, "curar_todas_as_estradas", lambda: ())
    monkeypatch.setattr(
        manager, "gerente_do_daemon",
        lambda daemon, **kw: SimpleNamespace(activate=lambda *a, **k: None))
    original = le._a_parte_de_fora
    acabadas = [0]

    def lenta(foto: Any, devolver: Any) -> None:
        time.sleep(LENTA_S)
        original(foto, devolver)
        acabadas[0] += 1

    monkeypatch.setattr(le, "_a_parte_de_fora", lenta)
    return lambda: acabadas[0]


def _marker(env_dir: Path) -> None:
    (env_dir / "last_run").write_text(
        f"appid={APPID}\nepoch={int(time.time())}\npid=1\n", encoding="utf-8")


@pytest.mark.parametrize("caso", sorted(_PERFIS))
def test_o_status_com_o_appid_devolve_o_ambiente_do_arme_sem_esperar_a_escrita(
    caso: str, sem_escrevente: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O ``daemon.status`` com o ``appid`` arma e responde o DualSense antes da escrita lenta.

    E o arquivo do jogo, quando a escrita acaba, sai do modo desse arme (a escada inclusa).
    """
    acabadas = _a_mesa_do_lancamento(tmp_path, monkeypatch, _perfil(_PERFIS[caso]))
    _marker(tmp_path)
    daemon: Any = _Mesa()

    async def corpo() -> tuple[dict[str, Any], float]:
        laco: Any = asyncio.get_running_loop()
        assert le.armar_o_escrevente(laco.call_soon_threadsafe, laco) is not None
        t0 = time.perf_counter()
        bloco = le.o_ambiente_no_status(daemon, {"appid": APPID})
        gasto = time.perf_counter() - t0
        fim = time.monotonic() + LENTA_S * 3
        while acabadas() < 1 and time.monotonic() < fim:
            await asyncio.sleep(0.05)
        return bloco, gasto

    bloco, gasto = asyncio.run(corpo())
    assert daemon.aplicados, "o status com o appid não armou o jogo"
    linhas = bloco["ambiente"]["linhas"]
    assert gasto < TETO_S, f"a resposta esperou {gasto:.2f} s pela escrita do lançamento"
    assert "SDL_JOYSTICK_HIDAPI=0" not in linhas, (
        f"o jogo DualSense recebeu o ambiente do Xbox: {linhas}")
    for linha in _DUALSENSE:
        assert linha in linhas
    assert "mascara=dualsense" in bloco["ambiente"]["estado"]
    assert acabadas() >= 1, "a escrita lenta não acabou"
    do_jogo = (tmp_path / f"steam_app_{APPID}.env").read_text(encoding="utf-8")
    assert "mascara=dualsense" in do_jogo and "SDL_JOYSTICK_HIDAPI=0" not in do_jogo, (
        f"o arquivo do jogo não é o do último arme dele:\n{do_jogo}")


def test_o_status_sem_o_appid_nao_arma_nem_responde_ambiente(
    sem_escrevente: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O ``daemon.status`` da CLI e da interface (sem ``appid``) continua sem o bloco."""
    _a_mesa_do_lancamento(tmp_path, monkeypatch, _perfil(None))
    _marker(tmp_path)
    daemon: Any = _Mesa()
    assert le.o_ambiente_no_status(daemon, {}) == {}
    assert le.o_ambiente_no_status(None, {"appid": APPID}) == {}
    assert daemon.aplicados == []
    for ruim in (0, -1, "1", True, 1.5):
        with pytest.raises(ValueError):
            le.o_ambiente_no_status(daemon, {"appid": ruim})


def _runtime() -> Path:
    raiz = os.environ.get("TMPDIR") or "/tmp"
    base = Path(tempfile.mkdtemp(prefix="hefa-", dir=raiz if len(raiz) < 40 else "/tmp"))
    (base / "hefesto-dualsense4unix").mkdir()
    return base


def _sock(runtime: Path) -> Path:
    return runtime / "hefesto-dualsense4unix" / "hefesto-dualsense4unix.sock"


@pytest.fixture
def runtime() -> Iterator[Path]:
    base = _runtime()
    yield base
    shutil.rmtree(base, ignore_errors=True)


def _o_wrapper(runtime: Path, state_home: Path) -> tuple[subprocess.CompletedProcess[str], float]:
    mudos = runtime / "game-mode-mudo"
    mudos.mkdir(exist_ok=True)
    for nome in ("system76-power", "busctl", "dbus-send", "systemd-run"):
        falso = mudos / nome
        falso.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        falso.chmod(0o755)
    env = {
        "PATH": f"{mudos}:{os.environ.get('PATH', '/usr/bin:/bin')}",
        "HOME": os.environ.get("HOME", "/tmp"),
        "XDG_RUNTIME_DIR": str(runtime),
        "XDG_STATE_HOME": str(state_home),
        "SteamAppId": str(APPID),
        "HEFESTO_PLACA_ACORDADA": str(runtime / "sem-placa"),
        "HEFESTO_SYSFS": str(runtime / "sys-vazio"),
    }
    t0 = time.monotonic()
    feito = subprocess.run(
        ["sh", str(_WRAPPER), "sh", "-c", _PROBE],
        env=env, capture_output=True, text=True, timeout=30, check=False)
    return feito, time.monotonic() - t0


def _env_dir(state_home: Path) -> Path:
    alvo = state_home / "hefesto-dualsense4unix" / "launch_env"
    alvo.mkdir(parents=True, exist_ok=True)
    return alvo


def _fonte(state_home: Path) -> dict[str, str]:
    texto = (_env_dir(state_home) / "fonte_do_ambiente").read_text(encoding="utf-8")
    return dict(linha.split("=", 1) for linha in texto.splitlines() if "=" in linha)


class _SocketFalso:
    """O socket do daemon: ``responder(params)`` devolve o ``result`` de cada pedido."""

    def __init__(self, path: Path, responder: Callable[[dict[str, Any]], dict[str, Any]]) -> None:
        self.pedidos: list[dict[str, Any]] = []
        self._responder = responder
        self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._sock.bind(str(path))
        self._sock.listen(4)
        self._parar = threading.Event()
        self._fio = threading.Thread(target=self._servir, daemon=True)
        self._fio.start()

    def _servir(self) -> None:
        while not self._parar.is_set():
            try:
                self._sock.settimeout(0.2)
                conn, _ = self._sock.accept()
            except TimeoutError:
                continue
            except OSError:
                return
            with conn:
                conn.settimeout(2.0)
                buf = b""
                while not buf.endswith(b"\n"):
                    pedaco = conn.recv(4096)
                    if not pedaco:
                        break
                    buf += pedaco
                pedido = json.loads(buf.decode("utf-8"))
                self.pedidos.append(pedido)
                resposta = {"jsonrpc": "2.0", "id": pedido.get("id"),
                            "result": self._responder(pedido.get("params") or {})}
                conn.sendall(json.dumps(resposta).encode("utf-8") + b"\n")

    def parar(self) -> None:
        self._parar.set()
        self._sock.close()
        self._fio.join(timeout=2)


def test_o_wrapper_exporta_o_ambiente_da_resposta_e_nao_o_do_arquivo(
    runtime: Path, tmp_path: Path
) -> None:
    """Com o daemon respondendo o ``ambiente``, as linhas vêm da resposta, e a fonte diz isso."""
    (_env_dir(tmp_path) / "default.env").write_text("\n".join(_XBOX) + "\n", encoding="utf-8")

    def responder(params: dict[str, Any]) -> dict[str, Any]:
        if "appid" not in params:
            return {"connected": True}
        return {"connected": True, "ambiente": {
            "appid": params["appid"], "linhas": [*_DUALSENSE, "LD_PRELOAD=/x.so"],
            "estado": "mascara=dualsense"}}

    falso = _SocketFalso(_sock(runtime), responder)
    try:
        feito, _gasto = _o_wrapper(runtime, tmp_path)
    finally:
        falso.parar()
    assert feito.returncode == 0, feito.stderr
    assert feito.stdout.strip() == (
        "IGNORE=0x054c/0x0ce6,0x28de/0x11ff|HIDAPI=|HIDRAW=0x054C/0x0CE6"), feito.stdout
    assert falso.pedidos[0]["params"] == {"appid": APPID}
    assert _fonte(tmp_path)["fonte"] == "daemon"


def test_o_wrapper_do_daemon_antigo_le_o_arquivo_escrito_durante_o_ping(
    runtime: Path, tmp_path: Path
) -> None:
    """O daemon que não conhece o ``ambiente``: o arquivo do jogo se escolhe DEPOIS do ping."""
    env_dir = _env_dir(tmp_path)
    (env_dir / "default.env").write_text("\n".join(_XBOX) + "\n", encoding="utf-8")

    def responder(_params: dict[str, Any]) -> dict[str, Any]:
        (env_dir / f"steam_app_{APPID}.env").write_text(
            "\n".join(_DUALSENSE) + "\n", encoding="utf-8")
        return {"connected": True}

    falso = _SocketFalso(_sock(runtime), responder)
    try:
        feito, _gasto = _o_wrapper(runtime, tmp_path)
    finally:
        falso.parar()
    assert feito.returncode == 0, feito.stderr
    assert "HIDAPI=|" in feito.stdout, f"o wrapper escolheu o arquivo antes do ping: {feito.stdout}"
    assert "IGNORE=0x054c/0x0ce6,0x28de/0x11ff" in feito.stdout
    assert _fonte(tmp_path) | {"epoch": ""} == {
        "appid": str(APPID), "fonte": "arquivo", "arquivo": f"steam_app_{APPID}.env", "epoch": ""}


def test_o_wrapper_sem_o_socket_nao_exporta_nada_e_diz_a_fonte(
    runtime: Path, tmp_path: Path
) -> None:
    """Sem daemon, o gate de vida (DEDUP-04) vale: nenhuma linha, mesmo com o arquivo em disco."""
    (_env_dir(tmp_path) / "default.env").write_text("\n".join(_XBOX) + "\n", encoding="utf-8")
    feito, _gasto = _o_wrapper(runtime, tmp_path)
    assert feito.returncode == 0, feito.stderr
    assert feito.stdout.strip() == "IGNORE=|HIDAPI=|HIDRAW="
    assert _fonte(tmp_path)["fonte"] == "nenhuma"


class _ServidorNoFio:
    """O ``IpcServer`` de verdade num laço em fio próprio, como o daemon o põe no ar."""

    def __init__(self, server: Any) -> None:
        self._server = server
        self._laco = asyncio.new_event_loop()
        self._fio = threading.Thread(target=self._laco.run_forever, daemon=True)
        self._fio.start()
        asyncio.run_coroutine_threadsafe(server.start(), self._laco).result(10)

    def parar(self) -> None:
        asyncio.run_coroutine_threadsafe(self._server.stop(), self._laco).result(10)
        self._laco.call_soon_threadsafe(self._laco.stop)
        self._fio.join(timeout=5)
        self._laco.close()


@pytest.mark.parametrize("caso", sorted(_PERFIS))
def test_o_jogo_dualsense_nasce_com_o_ambiente_dualsense_com_o_xbox_em_disco(
    caso: str, sem_escrevente: None, runtime: Path, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A prova (1) da sprint: o wrapper de verdade contra o ``IpcServer`` de verdade.

    O ``default.env`` em disco é o do Xbox e a escrita do fio escrevente leva ``LENTA_S``; o
    ambiente que o jogo recebe é o do DualSense, em menos de ``TETO_S``.
    """
    from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
    from hefesto_dualsense4unix.daemon.state_store import StateStore
    from hefesto_dualsense4unix.profiles.manager import ProfileManager
    from hefesto_dualsense4unix.testing import FakeController

    state_home = tmp_path / "state"
    _a_mesa_do_lancamento(_env_dir(state_home), monkeypatch, _perfil(_PERFIS[caso]))
    fc = FakeController(transport="usb")
    fc.connect()
    store = StateStore()
    daemon = _Mesa(store)
    server = IpcServer(
        controller=fc, store=store, profile_manager=ProfileManager(controller=fc, store=store),
        socket_path=_sock(runtime), daemon=daemon)
    no_ar = _ServidorNoFio(server)
    try:
        feito, gasto = _o_wrapper(runtime, state_home)
    finally:
        no_ar.parar()
    assert feito.returncode == 0, feito.stderr
    assert daemon.aplicados, "o wrapper não armou o jogo"
    assert "HIDAPI=0" not in feito.stdout, (
        f"o jogo DualSense nasceu com o ambiente do Xbox: {feito.stdout}")
    assert feito.stdout.strip() == (
        "IGNORE=0x054c/0x0ce6,0x28de/0x11ff|HIDAPI=|HIDRAW=0x054C/0x0CE6"), feito.stdout
    assert gasto < TETO_S, f"o lançamento esperou {gasto:.2f} s"
    assert _fonte(state_home)["fonte"] == "daemon"
