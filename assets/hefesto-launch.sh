#!/bin/sh
# hefesto-launch — wrapper de Opções de Inicialização da Steam (DEDUP-04).
#
# Instalado pelo passo de USUÁRIO do install.sh (sem sudo, sem flag) em:
#   ~/.local/share/hefesto-dualsense4unix/bin/hefesto-launch
#
# Na Steam a string é CONSTANTE (o botão "Copiar opções p/ jogos" gera):
#   sh -c '...' hefesto-launch %command%
# e ela mesma degrada quando este arquivo faltar. O wrapper roda no HOST,
# ANTES do container do Steam Linux Runtime (launch options embrulham o
# %command% inteiro — é assim que mangohud funciona), então:
#   - o env herdado carrega LD_LIBRARY_PATH/LD_PRELOAD do runtime scout:
#     os helpers do host (python3 do probe IPC) rodam com essas vars limpas,
#     preservando o env original no exec do jogo;
#   - o exec final é `exec env "$@"` (NUNCA `exec "$@"`): LaunchOptions
#     pré-existentes no formato `VAR=VAL %command%` viram $1 e o env(1) as
#     processa como assignment — `exec "$@"` tentaria EXECUTÁ-las (ENOENT).
#
# Decisão das envs (fail-safe por construção — pior caso: controle
# duplicado, NUNCA zero controles nem jogo que não abre):
#   1. $SteamAppId ausente/0 (atalho não-Steam) ................ nenhuma env
#   2. arquivo materializado ausente ........................... nenhuma env
#   3. gate de vida: connect()+ping JSON-RPC no socket de PRODUÇÃO por nome
#      EXATO (nunca glob — o socket FAKE mora no mesmo diretório; arquivo de
#      socket sobrevive a crash, então "o arquivo existe" NÃO é gate) —
#      daemon morto/stale/timeout ............................. nenhuma env
#   4. daemon vivo => exporta SÓ as envs da allowlist lidas do arquivo que o
#      daemon regrava a cada transição (backend REAL por jogador: qualquer
#      vpad degradado => o próprio arquivo já vem SEM o IGNORE).
#
# Allowlist ESPELHADA em src/hefesto_dualsense4unix/daemon/launch_env.py.

set -u

decide_envs() {
    # Imprime no stdout uma linha VAR=VAL por env aprovada. Qualquer falha
    # (return sem imprimir) significa "nenhuma env nossa".
    appid="${SteamAppId:-}"
    case "$appid" in
        ''|0) return 0 ;;
        *[!0-9]*) return 0 ;;
    esac

    state_dir="${XDG_STATE_HOME:-$HOME/.local/state}/hefesto-dualsense4unix/launch_env"
    envfile="$state_dir/steam_app_${appid}.env"
    [ -f "$envfile" ] || envfile="$state_dir/default.env"
    [ -f "$envfile" ] || return 0

    command -v python3 >/dev/null 2>&1 || return 0

    runtime="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
    sock="$runtime/hefesto-dualsense4unix/hefesto-dualsense4unix.sock"
    [ -S "$sock" ] || return 0

    # Gate de vida com timeout CURTO (1 s) para não atrasar o launch. As
    # vars do loader ficam limpas SÓ para o helper (o env do jogo não muda).
    LD_LIBRARY_PATH= LD_PRELOAD= PYTHONPATH= PYTHONHOME= \
        python3 - "$sock" <<'PYEOF' >/dev/null 2>&1 || return 0
import json
import socket
import sys

s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.settimeout(1.0)
s.connect(sys.argv[1])
s.sendall(
    json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": "daemon.status", "params": {}}
    ).encode("utf-8")
    + b"\n"
)
buf = b""
while not buf.endswith(b"\n"):
    chunk = s.recv(4096)
    if not chunk:
        raise SystemExit(1)
    buf += chunk
data = json.loads(buf.decode("utf-8"))
raise SystemExit(0 if isinstance(data, dict) and "result" in data else 1)
PYEOF

    # Daemon vivo: só linhas da allowlist passam (arquivo corrompido ou
    # adulterado não consegue exportar LD_PRELOAD e afins).
    while IFS= read -r line; do
        case "$line" in
            SDL_GAMECONTROLLER_IGNORE_DEVICES=*) printf '%s\n' "$line" ;;
            SDL_JOYSTICK_HIDAPI=*)               printf '%s\n' "$line" ;;
            PROTON_ENABLE_HIDRAW=*)              printf '%s\n' "$line" ;;
            __GL_SHADER_DISK_CACHE=*)            printf '%s\n' "$line" ;;
            __GL_SHADER_DISK_CACHE_SKIP_CLEANUP=*) printf '%s\n' "$line" ;;
        esac
    done < "$envfile"
    return 0
}

hefesto_envs="$(decide_envs)" || hefesto_envs=""

if [ -n "$hefesto_envs" ]; then
    # Prependa cada VAR=VAL como argumento do env(1) — assignments precisam
    # vir antes do comando; a ordem entre eles é irrelevante. O heredoc NÃO
    # cria subshell (pipe criaria), então o `set --` sobrevive ao loop.
    while IFS= read -r kv; do
        [ -n "$kv" ] && set -- "$kv" "$@"
    done <<HEFESTO_EOF
$hefesto_envs
HEFESTO_EOF
fi

exec env "$@"
