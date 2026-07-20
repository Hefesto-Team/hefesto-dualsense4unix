"""NUMA-05 — check "autoridade de exibição" do doctor.sh, hermético.

A lógica vive em shell puro (`check_display_authority`, scripts/doctor.sh),
testável via `source` (mesmo padrão de `test_doctor_vpad_motion.py` /
`test_doctor_8bitdo_cascade.py`). O IPC é um servidor UNIX socket FAKE nesta
suíte (sem daemon real) respondendo `daemon.state_full` com um `game_signal`
canned — cobre:

1. sem socket: `info` neutro, sem FAIL/WARN.
2. `game_signal` ausente do payload (daemon antigo, pré-NUMA-05): `info`
   neutro.
3. `authority == "game"`: PASS mencionando a evidência.
4. `authority == "unknown"` com `degradado=True`: WARN citando o `motivo`
   (a causa) — FALHA-SEM: sem o check, a mantenedora não saberia POR QUE.
5. `authority == "daemon"`: PASS.
"""
from __future__ import annotations

import json
import shutil
import socket
import subprocess
import tempfile
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
DOCTOR = ROOT / "scripts" / "doctor.sh"
APP_ID = "hefesto-dualsense4unix"


@pytest.fixture
def runtime_dir() -> Iterator[Path]:
    """Diretório CURTO em `/tmp` (não o `tmp_path` do pytest — profundo demais:
    estoura o limite de ~108 bytes de path de um AF_UNIX socket)."""
    d = Path(tempfile.mkdtemp(prefix="hf-doc-"))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


def _servir_uma_resposta(sock_path: Path, result: dict[str, Any]) -> threading.Thread:
    """Sobe um server UNIX socket que aceita 1 conexão e responde 1x."""
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(str(sock_path))
    srv.listen(1)
    srv.settimeout(5.0)

    def _loop() -> None:
        try:
            conn, _ = srv.accept()
        except OSError:
            return
        try:
            conn.settimeout(5.0)
            buf = b""
            while not buf.endswith(b"\n"):
                chunk = conn.recv(65536)
                if not chunk:
                    break
                buf += chunk
            payload = json.dumps({"jsonrpc": "2.0", "id": 1, "result": result})
            conn.sendall(payload.encode("utf-8") + b"\n")
        finally:
            conn.close()
            srv.close()

    thread = threading.Thread(target=_loop, daemon=True)
    thread.start()
    return thread


def _rodar_check(runtime_dir: Path) -> str:
    res = subprocess.run(
        ["bash", "-c", 'set --; source "$DOCTOR_SH"; check_display_authority'],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env={
            "PATH": "/usr/bin:/bin",
            "DOCTOR_SH": str(DOCTOR),
            "XDG_RUNTIME_DIR": str(runtime_dir),
        },
    )
    assert res.returncode == 0, res.stderr
    return res.stdout


def _sock_path(runtime_dir: Path) -> Path:
    d = runtime_dir / APP_ID
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{APP_ID}.sock"


def test_sem_socket_e_info_neutro(runtime_dir: Path) -> None:
    saida = _rodar_check(runtime_dir)
    assert "daemon parado" in saida
    assert "[FAIL]" not in saida
    assert "[WARN]" not in saida


def test_game_signal_ausente_e_info_neutro(runtime_dir: Path) -> None:
    """Daemon antigo (pré-NUMA-05) não manda `game_signal` — nunca WARN/FAIL."""
    sock = _sock_path(runtime_dir)
    thread = _servir_uma_resposta(sock, {"connected": True})
    try:
        saida = _rodar_check(runtime_dir)
    finally:
        thread.join(timeout=5)
    assert "versão antiga" in saida
    assert "[FAIL]" not in saida
    assert "[WARN]" not in saida


def test_authority_game_e_pass(runtime_dir: Path) -> None:
    sock = _sock_path(runtime_dir)
    thread = _servir_uma_resposta(
        sock,
        {
            "game_signal": {
                "authority": "game",
                "evidencia": "wm_class_steam_app",
                "motivo": None,
                "desde": 10.0,
                "degradado": False,
            },
            "controllers": [],
        },
    )
    try:
        saida = _rodar_check(runtime_dir)
    finally:
        thread.join(timeout=5)
    assert "[ OK ]" in saida
    assert "JOGO" in saida
    assert "wm_class_steam_app" in saida


def test_authority_daemon_e_pass(runtime_dir: Path) -> None:
    sock = _sock_path(runtime_dir)
    thread = _servir_uma_resposta(
        sock,
        {
            "game_signal": {
                "authority": "daemon",
                "evidencia": None,
                "motivo": None,
                "desde": None,
                "degradado": False,
            },
            "controllers": [],
        },
    )
    try:
        saida = _rodar_check(runtime_dir)
    finally:
        thread.join(timeout=5)
    assert "[ OK ]" in saida
    assert "DAEMON" in saida


def test_authority_unknown_degradado_e_warn_com_causa(runtime_dir: Path) -> None:
    """FALHA-SEM: sem o check, a causa do `unknown` preso ficava invisível."""
    sock = _sock_path(runtime_dir)
    thread = _servir_uma_resposta(
        sock,
        {
            "game_signal": {
                "authority": "unknown",
                "evidencia": None,
                "motivo": "detector_de_janela_cego",
                "desde": None,
                "degradado": True,
            },
            "controllers": [
                {"player_slot": 1, "lightbar_source": "sysfs", "lightbar_rgb": [0, 0, 255]}
            ],
        },
    )
    try:
        saida = _rodar_check(runtime_dir)
    finally:
        thread.join(timeout=5)
    assert "[WARN]" in saida
    assert "UNKNOWN" in saida
    assert "detector_de_janela_cego" in saida
    # posse por-controle listada junto (get_players()/get_rgb() x posse).
    assert "player_slot=1" in saida
    assert "lightbar_source=sysfs" in saida
