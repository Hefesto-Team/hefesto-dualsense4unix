"""PLAT-05: Game Mode COSMIC no wrapper `hefesto-launch` — best-effort puro.

Cada teste roda o wrapper POSIX-sh REAL via subprocess com um
`system76-power` FAKE na frente do PATH (nunca o daemon de energia real da
máquina — o fake sombreia o binário; nos cenários de ausência o PATH é
RESTRITO a um diretório controlado, para o fallback busctl/dbus-send jamais
alcançar o D-Bus de verdade):

- perfil anterior != performance => pede Performance na largada e RESTAURA o
  perfil anterior depois que o jogo termina (restaurador em background — o
  `exec env` preserva o PID, trap de EXIT morre no exec);
- já em Performance => só consulta, não seta nada (nada a restaurar);
- system76-power/busctl/dbus-send AUSENTES => no-op silencioso;
- `set` falhando => o jogo abre do mesmo jeito (nenhum rastro de restore);
- fallback busctl => métodos REAIS da interface (Performance/Balanced +
  GetProfile — introspecção ao vivo 2026-07-18; SetProfile NÃO existe).

Em TODOS os casos o comando embrulhado executa — o jogo sempre abre.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_WRAPPER = _ROOT / "assets" / "hefesto-launch.sh"

_FAKE_S76 = """#!/bin/sh
# fake system76-power do teste — loga chamadas e simula o perfil em arquivo.
log="${FAKE_S76_LOG:?}"
prof_file="${FAKE_S76_PROFILE:?}"
if [ "$#" -ge 2 ] && [ "$1" = "profile" ]; then
    if [ "${FAKE_S76_SET_FAILS:-0}" = "1" ]; then
        echo "set-fail $2" >> "$log"
        exit 1
    fi
    echo "set $2" >> "$log"
    printf '%s\\n' "$2" > "$prof_file"
    exit 0
fi
if [ "$#" -ge 1 ] && [ "$1" = "profile" ]; then
    echo "get" >> "$log"
    printf 'Power Profile: %s\\n' "$(cat "$prof_file")"
    exit 0
fi
exit 0
"""

_FAKE_BUSCTL = """#!/bin/sh
# fake busctl do teste — loga a chamada inteira e responde só o GetProfile.
log="${FAKE_BUSCTL_LOG:?}"
echo "busctl $*" >> "$log"
case "$*" in
    *GetProfile*) printf 's "Balanced"\\n' ;;
esac
exit 0
"""


def _write_exec(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


def _restricted_bin(tmp_path: Path, tools: list[str]) -> Path:
    """PATH mínimo: só as ferramentas listadas (por symlink) — garante que o
    fallback D-Bus NUNCA encontra o busctl/dbus-send reais da máquina."""
    bindir = tmp_path / "bin-restrito"
    bindir.mkdir(exist_ok=True)
    for tool in tools:
        real = shutil.which(tool)
        assert real is not None, f"ferramenta de teste ausente: {tool}"
        (bindir / tool).symlink_to(real)
    return bindir


def _run_wrapper(
    *,
    tmp_path: Path,
    path_env: str,
    extra_env: dict[str, str] | None = None,
    args: list[str] | None = None,
    timeout: float = 20.0,
) -> subprocess.CompletedProcess[str]:
    env = {
        "PATH": path_env,
        "HOME": str(tmp_path),
        "XDG_RUNTIME_DIR": str(tmp_path / "run"),
        "XDG_STATE_HOME": str(tmp_path / "state"),
        "SteamAppId": "1599660",
        # Poll curto do restaurador — o default (2 s) deixaria o teste lento.
        "HEFESTO_GM_POLL_SECS": "0.2",
    }
    env.update(extra_env or {})
    (tmp_path / "run").mkdir(exist_ok=True)
    cmd = [
        "sh",
        str(_WRAPPER),
        *(args if args is not None else ["sh", "-c", "printf jogo-abriu"]),
    ]
    return subprocess.run(
        cmd, env=env, capture_output=True, text=True,
        timeout=timeout, check=False,
    )


def _wait_for_log(log: Path, needle: str, timeout: float = 8.0) -> str:
    """Espera o restaurador em background escrever `needle` no log."""
    deadline = time.monotonic() + timeout
    conteudo = ""
    while time.monotonic() < deadline:
        conteudo = log.read_text(encoding="utf-8") if log.exists() else ""
        if needle in conteudo:
            return conteudo
        time.sleep(0.1)
    return conteudo


def _s76_env(tmp_path: Path, perfil: str) -> tuple[Path, Path, dict[str, str]]:
    fakebin = tmp_path / "fakebin"
    fakebin.mkdir(exist_ok=True)
    _write_exec(fakebin / "system76-power", _FAKE_S76)
    log = tmp_path / "s76.log"
    prof = tmp_path / "s76.profile"
    prof.write_text(perfil + "\n", encoding="utf-8")
    return fakebin, log, {
        "FAKE_S76_LOG": str(log),
        "FAKE_S76_PROFILE": str(prof),
    }


def test_pede_performance_e_restaura_o_perfil_anterior(tmp_path: Path) -> None:
    """Caminho feliz: Balanced → Performance na largada; jogo termina →
    o restaurador devolve Balanced (sem segurar o stdout do jogo)."""
    fakebin, log, extra = _s76_env(tmp_path, "Balanced")
    path_env = f"{fakebin}:{os.environ.get('PATH', '/usr/bin:/bin')}"

    result = _run_wrapper(tmp_path=tmp_path, path_env=path_env, extra_env=extra)

    assert result.returncode == 0
    assert result.stdout == "jogo-abriu"  # o jogo SEMPRE abre
    conteudo = _wait_for_log(log, "set balanced")
    linhas = conteudo.strip().splitlines()
    assert linhas[0] == "get"
    assert "set performance" in linhas
    assert linhas.index("set performance") < linhas.index("set balanced")


def test_ja_em_performance_so_consulta_e_nao_seta(tmp_path: Path) -> None:
    fakebin, log, extra = _s76_env(tmp_path, "Performance")
    path_env = f"{fakebin}:{os.environ.get('PATH', '/usr/bin:/bin')}"

    result = _run_wrapper(tmp_path=tmp_path, path_env=path_env, extra_env=extra)

    assert result.returncode == 0
    assert result.stdout == "jogo-abriu"
    time.sleep(0.6)  # janela para um restaurador indevido aparecer
    conteudo = log.read_text(encoding="utf-8")
    assert "get" in conteudo
    assert "set" not in conteudo  # nada a trocar, nada a restaurar


def test_perfil_desconhecido_nao_vira_comando(tmp_path: Path) -> None:
    """Saída inesperada do daemon (case fechado): consulta e para."""
    fakebin, log, extra = _s76_env(tmp_path, "Turbo; rm -rf /")

    result = _run_wrapper(
        tmp_path=tmp_path,
        path_env=f"{fakebin}:{os.environ.get('PATH', '/usr/bin:/bin')}",
        extra_env=extra,
    )

    assert result.returncode == 0
    assert result.stdout == "jogo-abriu"
    time.sleep(0.4)
    assert "set" not in log.read_text(encoding="utf-8")


def test_ausencia_total_e_noop_silencioso(tmp_path: Path) -> None:
    """Sem system76-power NEM busctl NEM dbus-send no PATH: o Game Mode
    inteiro é no-op e o jogo abre — PATH restrito prova que o fallback
    D-Bus nunca alcança o barramento real."""
    bindir = _restricted_bin(tmp_path, ["sh", "env", "date", "mkdir"])

    result = _run_wrapper(tmp_path=tmp_path, path_env=str(bindir))

    assert result.returncode == 0
    assert result.stdout == "jogo-abriu"
    assert result.stderr == ""  # nem ruído de ferramenta ausente


def test_set_falhando_nao_derruba_nem_atrasa_o_jogo(tmp_path: Path) -> None:
    fakebin, log, extra = _s76_env(tmp_path, "Balanced")
    extra["FAKE_S76_SET_FAILS"] = "1"

    result = _run_wrapper(
        tmp_path=tmp_path,
        path_env=f"{fakebin}:{os.environ.get('PATH', '/usr/bin:/bin')}",
        extra_env=extra,
    )

    assert result.returncode == 0
    assert result.stdout == "jogo-abriu"
    time.sleep(0.6)
    conteudo = log.read_text(encoding="utf-8")
    assert "set-fail performance" in conteudo
    # set falhou => NÃO agenda restauração (não há o que restaurar).
    assert "set-fail balanced" not in conteudo


def test_fallback_busctl_usa_os_metodos_reais_da_interface(
    tmp_path: Path,
) -> None:
    """Sem o binário system76-power, o wrapper fala com o fake busctl usando
    os métodos REAIS (GetProfile / Performance / Balanced) — nunca o
    SetProfile imaginado (não existe na interface)."""
    tools = ["sh", "env", "date", "mkdir", "sed", "head", "tr", "sleep", "cat"]
    bindir = _restricted_bin(tmp_path, tools)
    _write_exec(bindir / "busctl", _FAKE_BUSCTL)
    log = tmp_path / "busctl.log"

    result = _run_wrapper(
        tmp_path=tmp_path,
        path_env=str(bindir),
        extra_env={"FAKE_BUSCTL_LOG": str(log)},
    )

    assert result.returncode == 0
    assert result.stdout == "jogo-abriu"
    conteudo = _wait_for_log(log, "com.system76.PowerDaemon Balanced")
    assert "com.system76.PowerDaemon GetProfile" in conteudo
    assert "com.system76.PowerDaemon Performance" in conteudo  # a ida
    assert "SetProfile" not in conteudo  # o método que NÃO existe
