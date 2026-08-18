"""DEDUP-04: o wrapper `hefesto-launch` de verdade, contra sockets de verdade.

O gate de vida é connect()+ping JSON-RPC no socket de PRODUÇÃO por nome
EXATO — nunca "o arquivo de socket existe" (arquivo sobrevive a crash; o
socket FAKE mora no mesmo diretório). Cada teste roda o wrapper POSIX-sh
REAL via subprocess, com XDG_* apontando para diretórios controlados (nunca
o daemon real da máquina):

- daemon vivo  => exporta as envs do arquivo materializado (só a allowlist);
- socket órfão (arquivo sem listener) => NENHUMA env;
- socket ausente => NENHUMA env;
- listener que aceita e NUNCA responde => timeout curto => NENHUMA env
  (e o launch não fica pendurado);
- SteamAppId ausente/atalho não-Steam => NENHUMA env.

Em TODOS os casos o comando embrulhado executa — o jogo sempre abre.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import tempfile
import threading
import time
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_WRAPPER = _ROOT / "assets" / "hefesto-launch.sh"

#: Imprime as envs relevantes vistas pelo "jogo" (via env(1) do wrapper).
_PROBE = (
    'printf "IGNORE=%s|HIDAPI=%s|HIDRAW=%s|LD=%s\\n" '
    '"$SDL_GAMECONTROLLER_IGNORE_DEVICES" "$SDL_JOYSTICK_HIDAPI" '
    '"$PROTON_DISABLE_HIDRAW" "$LD_PRELOAD"'
)


def _runtime_dir() -> Path:
    """Diretório de runtime CURTO (limite de ~108 bytes do AF_UNIX) e isolado
    do XDG_RUNTIME_DIR real — o teste nunca pode falar com o daemon dela."""
    base = Path(tempfile.mkdtemp(prefix="hefl-"))
    (base / "hefesto-dualsense4unix").mkdir()
    return base


def _socket_path(runtime: Path) -> Path:
    return runtime / "hefesto-dualsense4unix" / "hefesto-dualsense4unix.sock"


def _run_wrapper(
    *,
    runtime: Path,
    state_home: Path,
    appid: str | None = "1599660",
    args: list[str] | None = None,
    timeout: float = 15.0,
) -> subprocess.CompletedProcess[str]:
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", "/tmp"),
        "XDG_RUNTIME_DIR": str(runtime),
        "XDG_STATE_HOME": str(state_home),
    }
    if appid is not None:
        env["SteamAppId"] = appid
    cmd = ["sh", str(_WRAPPER), *(args if args is not None else ["sh", "-c", _PROBE])]
    return subprocess.run(
        cmd, env=env, capture_output=True, text=True, timeout=timeout, check=False
    )


def _write_env_file(state_home: Path, name: str, lines: list[str]) -> None:
    target = state_home / "hefesto-dualsense4unix" / "launch_env"
    target.mkdir(parents=True, exist_ok=True)
    (target / name).write_text("\n".join(lines) + "\n", encoding="utf-8")


class _FakeDaemon:
    """Servidor IPC mínimo: responde 1 linha JSON-RPC com result (ping OK)."""

    def __init__(self, path: Path, *, respond: bool = True) -> None:
        self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._sock.bind(str(path))
        self._sock.listen(2)
        self._respond = respond
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self) -> None:
        while not self._stop.is_set():
            try:
                self._sock.settimeout(0.2)
                conn, _ = self._sock.accept()
            except TimeoutError:
                continue
            except OSError:
                return
            with conn:
                if not self._respond:
                    # Aceita e NUNCA responde: o timeout do wrapper decide.
                    time.sleep(3.0)
                    continue
                try:
                    conn.settimeout(1.0)
                    data = conn.recv(4096)
                    if data:
                        req = json.loads(data.decode("utf-8"))
                        resp = {
                            "jsonrpc": "2.0",
                            "id": req.get("id"),
                            "result": {"connected": True},
                        }
                        conn.sendall(json.dumps(resp).encode("utf-8") + b"\n")
                except (OSError, ValueError):
                    pass

    def stop(self) -> None:
        self._stop.set()
        self._sock.close()
        self._thread.join(timeout=2)


@pytest.fixture()
def runtime():
    """Runtime dir curto (AF_UNIX limita o path do socket a ~108 bytes — o
    tmp_path do pytest estoura), com limpeza no teardown."""
    import shutil

    base = _runtime_dir()
    yield base
    shutil.rmtree(base, ignore_errors=True)


def test_daemon_vivo_exporta_as_envs_materializadas(runtime, tmp_path):
    """Critério (a): gate de vida passa => as envs do arquivo chegam ao jogo."""
    _write_env_file(
        tmp_path, "default.env",
        [
            "# materializado em teste",
            "SDL_GAMECONTROLLER_IGNORE_DEVICES=0x054c/0x0ce6",
            "PROTON_DISABLE_HIDRAW=0x054C/0x0CE6",
        ],
    )
    daemon = _FakeDaemon(_socket_path(runtime))
    try:
        result = _run_wrapper(runtime=runtime, state_home=tmp_path)
    finally:
        daemon.stop()
    assert result.returncode == 0
    assert (
        result.stdout.strip()
        == "IGNORE=0x054c/0x0ce6|HIDAPI=|HIDRAW=0x054C/0x0CE6|LD="
    )


def test_arquivo_por_appid_vence_o_default(runtime, tmp_path):
    _write_env_file(
        tmp_path, "default.env",
        ["SDL_GAMECONTROLLER_IGNORE_DEVICES=0x054c/0x0ce6"],
    )
    _write_env_file(tmp_path, "steam_app_42.env", ["SDL_JOYSTICK_HIDAPI=0"])
    daemon = _FakeDaemon(_socket_path(runtime))
    try:
        result = _run_wrapper(runtime=runtime, state_home=tmp_path, appid="42")
    finally:
        daemon.stop()
    assert result.stdout.strip() == "IGNORE=|HIDAPI=0|HIDRAW=|LD="


def test_socket_orfao_stale_nao_exporta_nada(runtime, tmp_path):
    """Critério (d): arquivo de socket SEM listener (sobrevive a crash) —
    gate por connect, não por existência => nenhuma env, jogo abre."""
    _write_env_file(
        tmp_path, "default.env",
        ["SDL_GAMECONTROLLER_IGNORE_DEVICES=0x054c/0x0ce6"],
    )
    sock_path = _socket_path(runtime)
    stale = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    stale.bind(str(sock_path))
    stale.close()  # o ARQUIVO fica; nenhum listener atrás dele
    assert sock_path.exists()
    result = _run_wrapper(runtime=runtime, state_home=tmp_path)
    assert result.returncode == 0
    assert result.stdout.strip() == "IGNORE=|HIDAPI=|HIDRAW=|LD="


def test_daemon_morto_sem_socket_nao_exporta_nada(runtime, tmp_path):
    _write_env_file(
        tmp_path, "default.env",
        ["SDL_GAMECONTROLLER_IGNORE_DEVICES=0x054c/0x0ce6"],
    )
    result = _run_wrapper(runtime=runtime, state_home=tmp_path)
    assert result.returncode == 0
    assert result.stdout.strip() == "IGNORE=|HIDAPI=|HIDRAW=|LD="


def test_ipc_pendurado_da_timeout_curto_e_nao_atrasa_o_launch(runtime, tmp_path):
    """Listener que aceita e nunca responde: o wrapper desiste em ~1 s
    (timeout do probe) e lança SEM envs — o launch não fica pendurado."""
    _write_env_file(
        tmp_path, "default.env",
        ["SDL_GAMECONTROLLER_IGNORE_DEVICES=0x054c/0x0ce6"],
    )
    daemon = _FakeDaemon(_socket_path(runtime), respond=False)
    inicio = time.monotonic()
    try:
        result = _run_wrapper(runtime=runtime, state_home=tmp_path)
    finally:
        daemon.stop()
    duracao = time.monotonic() - inicio
    assert result.returncode == 0
    assert result.stdout.strip() == "IGNORE=|HIDAPI=|HIDRAW=|LD="
    assert duracao < 5.0, f"launch atrasou {duracao:.1f}s — timeout não é curto"


def test_sem_steamappid_nao_exporta_nada_mesmo_com_daemon_vivo(runtime, tmp_path):
    """Atalho não-Steam (SteamAppId ausente) => fail-safe: nenhuma env."""
    _write_env_file(
        tmp_path, "default.env",
        ["SDL_GAMECONTROLLER_IGNORE_DEVICES=0x054c/0x0ce6"],
    )
    daemon = _FakeDaemon(_socket_path(runtime))
    try:
        result = _run_wrapper(runtime=runtime, state_home=tmp_path, appid=None)
    finally:
        daemon.stop()
    assert result.stdout.strip() == "IGNORE=|HIDAPI=|HIDRAW=|LD="


def test_allowlist_barra_env_fora_da_lista(runtime, tmp_path):
    """Arquivo adulterado com LD_PRELOAD não passa do wrapper (allowlist) — e
    a env APOSENTADA (PROTON_ENABLE_HIDRAW, GUERRA-01) também é descartada."""
    _write_env_file(
        tmp_path, "default.env",
        [
            "LD_PRELOAD=/tmp/evil.so",
            "PROTON_ENABLE_HIDRAW=1",
            "PROTON_DISABLE_HIDRAW=0x054C/0x0CE6",
        ],
    )
    daemon = _FakeDaemon(_socket_path(runtime))
    try:
        result = _run_wrapper(runtime=runtime, state_home=tmp_path)
        # A aposentada não chega ao jogo nem por arquivo rançoso (daemon VIVO).
        check = _run_wrapper(
            runtime=runtime,
            state_home=tmp_path,
            args=["sh", "-c", 'printf "ENABLE=%s\\n" "${PROTON_ENABLE_HIDRAW:-}"'],
        )
    finally:
        daemon.stop()
    assert result.stdout.strip() == "IGNORE=|HIDAPI=|HIDRAW=0x054C/0x0CE6|LD="
    assert check.stdout.strip() == "ENABLE="


def test_launch_options_do_usuario_sobrevivem_ao_wrapper(runtime, tmp_path):
    """Critério (f): `VAR=VAL %command%` pré-existente vira argumento do
    env(1) — o jogo abre com a var, nunca ENOENT."""
    result = _run_wrapper(
        runtime=runtime,
        state_home=tmp_path,
        args=["VAR_DA_USUARIA=oi", "sh", "-c", 'printf "%s\\n" "$VAR_DA_USUARIA"'],
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "oi"


# --- marker de execução last_run (GUERRA-01 / honestidade do dedup) ----------


def _last_run(state_home: Path) -> dict[str, str]:
    marker = state_home / "hefesto-dualsense4unix" / "launch_env" / "last_run"
    out: dict[str, str] = {}
    for linha in marker.read_text(encoding="utf-8").splitlines():
        chave, _, valor = linha.partition("=")
        out[chave] = valor
    return out


def test_marker_last_run_gravado_com_appid_e_epoch(runtime, tmp_path):
    """O wrapper grava appid + epoch em chave=valor — é o que o daemon compara
    com a janela steam_app para expor `wrapper_used` (dedup honesto)."""
    antes = int(time.time())
    result = _run_wrapper(runtime=runtime, state_home=tmp_path, appid="1599660")
    assert result.returncode == 0
    marker = _last_run(tmp_path)
    assert marker["appid"] == "1599660"
    assert antes <= int(marker["epoch"]) <= int(time.time()) + 1


def test_marker_last_run_independe_do_daemon_vivo(runtime, tmp_path):
    """Best-effort de propósito: o marker atesta que o jogo passou pelo
    WRAPPER (não que o daemon vive) — daemon morto grava do mesmo jeito."""
    assert not _socket_path(runtime).exists()
    result = _run_wrapper(runtime=runtime, state_home=tmp_path, appid="42")
    assert result.returncode == 0
    assert _last_run(tmp_path)["appid"] == "42"


def test_marker_last_run_sem_appid_nao_grava(runtime, tmp_path):
    """Atalho não-Steam (SteamAppId ausente/0) => sem marker (nada a casar
    com janela steam_app), e o launch segue normal."""
    for appid in (None, "0", "abc"):
        result = _run_wrapper(runtime=runtime, state_home=tmp_path, appid=appid)
        assert result.returncode == 0
    marker = tmp_path / "hefesto-dualsense4unix" / "launch_env" / "last_run"
    assert not marker.exists()


def test_marker_last_run_regravado_a_cada_launch(runtime, tmp_path):
    """Dois launches => o marker reflete o ÚLTIMO (mv atômico, nunca metade)."""
    _run_wrapper(runtime=runtime, state_home=tmp_path, appid="10")
    _run_wrapper(runtime=runtime, state_home=tmp_path, appid="20")
    marker = _last_run(tmp_path)
    assert marker["appid"] == "20"
    tmp_sobra = tmp_path / "hefesto-dualsense4unix" / "launch_env" / "last_run.tmp"
    assert not tmp_sobra.exists()


# --- NUMA-01: pid=$$ no last_run + marker last_exit ---------------------------


def _last_exit(state_home: Path) -> dict[str, str]:
    marker = state_home / "hefesto-dualsense4unix" / "launch_env" / "last_exit"
    out: dict[str, str] = {}
    for linha in marker.read_text(encoding="utf-8").splitlines():
        chave, _, valor = linha.partition("=")
        out[chave] = valor
    return out


def test_marker_last_run_grava_pid(runtime, tmp_path):
    """NUMA-01: `pid=$$` no `last_run` — o `exec env` final preserva o PID
    (o wrapper VIRA o jogo), então este é o pid do próprio processo do jogo
    enquanto ele roda."""
    result = _run_wrapper(runtime=runtime, state_home=tmp_path, appid="1599660")
    assert result.returncode == 0
    marker = _last_run(tmp_path)
    assert marker["pid"].isdigit()
    assert int(marker["pid"]) > 0


def test_launch_normal_nao_grava_last_exit(runtime, tmp_path):
    """Caminho feliz (o `exec` no fim do wrapper SUCEDE): o handler de EXIT
    nunca dispara — `last_exit` não é gravado. A liveness de "jogo ainda
    rodando" é o `pid` do `last_run` (checado via kill(pid, 0) pelo
    daemon), não este marker."""
    daemon = _FakeDaemon(_socket_path(runtime))
    try:
        result = _run_wrapper(runtime=runtime, state_home=tmp_path)
    finally:
        daemon.stop()
    assert result.returncode == 0
    marker = tmp_path / "hefesto-dualsense4unix" / "launch_env" / "last_exit"
    assert not marker.exists()


def test_exec_falhando_grava_last_exit_e_o_launch_nao_trava(runtime, tmp_path):
    """NUMA-01: PATH sem o binário `env(1)` => o `exec env "$@"` final falha
    e o wrapper cai no handler de EXIT (`_hefesto_on_exit`) — `last_exit`
    é gravado best-effort e o processo termina (nunca trava esperando)."""
    import shutil

    bindir = tmp_path / "bin-sem-env"
    bindir.mkdir()
    for tool in ("sh", "date", "mkdir", "mv"):
        real_path = shutil.which(tool)
        assert real_path is not None, f"ferramenta de teste ausente: {tool}"
        (bindir / tool).symlink_to(real_path)

    env = {
        "PATH": str(bindir),
        "HOME": os.environ.get("HOME", "/tmp"),
        "XDG_RUNTIME_DIR": str(runtime),
        "XDG_STATE_HOME": str(tmp_path),
        "SteamAppId": "1599660",
    }
    antes = int(time.time())
    result = subprocess.run(
        ["sh", str(_WRAPPER), "sh", "-c", "printf jogo-abriu"],
        env=env,
        capture_output=True,
        text=True,
        timeout=10.0,
        check=False,
    )
    # exec falhou (env ausente) => o comando embrulhado NUNCA rodou, mas o
    # wrapper termina (não trava) e grava o marker de saída.
    assert result.returncode != 0
    assert "jogo-abriu" not in result.stdout
    saida = _last_exit(tmp_path)
    assert antes <= int(saida["epoch"]) <= int(time.time()) + 1
    # Correção pós-auditoria da Onda N: `pid=$$` no `last_exit` correlaciona
    # a saída ao PRÓPRIO wrapper que a gravou — sem isso, `last_run`/
    # `last_exit` sendo arquivos GLOBAIS, o `last_exit` de UM launch que
    # falhou o `exec` podia invalidar o `last_run` de um launch B
    # POSTERIOR e bem-sucedido só por ordem de escrita no disco.
    assert saida["pid"].isdigit()
    assert int(saida["pid"]) > 0


def test_last_exit_best_effort_com_diretorio_ilegivel(runtime, tmp_path):
    """`record_last_exit`/`record_last_run` nunca travam nem derrubam o
    launch mesmo com o diretório de estado ILEGÍVEL (ex.: permissão
    negada) — o jogo abre do mesmo jeito."""
    state_home = tmp_path / "estado"
    launch_env_dir = state_home / "hefesto-dualsense4unix" / "launch_env"
    launch_env_dir.parent.mkdir(parents=True)
    launch_env_dir.parent.chmod(0o500)  # sem permissão de escrita
    try:
        result = _run_wrapper(runtime=runtime, state_home=state_home)
    finally:
        launch_env_dir.parent.chmod(0o700)
    assert result.returncode == 0
    assert result.stdout.strip() == "IGNORE=|HIDAPI=|HIDRAW=|LD="
