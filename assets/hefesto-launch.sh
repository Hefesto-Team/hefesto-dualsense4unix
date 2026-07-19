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
            PROTON_DISABLE_HIDRAW=*)             printf '%s\n' "$line" ;;
            __GL_SHADER_DISK_CACHE=*)            printf '%s\n' "$line" ;;
            __GL_SHADER_DISK_CACHE_SKIP_CLEANUP=*) printf '%s\n' "$line" ;;
        esac
    done < "$envfile"
    return 0
}

record_last_run() {
    # Marker de execução (GUERRA-01 / honestidade do dedup): prova que o jogo
    # PASSOU pelo wrapper — o daemon compara com a janela steam_app detectada
    # e expõe `wrapper_used` no state_full (o `dedup_ok` sozinho é
    # falso-tranquilizante: nunca checa se o jogo herdou a env).
    #
    # Arquivo: $XDG_STATE_HOME/hefesto-dualsense4unix/launch_env/last_run
    # Formato (chave=valor, uma por linha; consumido pelo daemon):
    #   appid=<SteamAppId numérico do launch>
    #   epoch=<unix epoch em segundos do launch>
    #
    # Best-effort de ponta a ponta: gravado ANTES do gate de vida (o marker
    # atesta o wrapper, não o daemon) e NENHUMA falha aqui pode atrasar ou
    # derrubar o launch. Escrita via tmp+mv para o daemon nunca ler metade.
    lr_appid="${SteamAppId:-}"
    case "$lr_appid" in
        ''|0) return 0 ;;
        *[!0-9]*) return 0 ;;
    esac
    lr_dir="${XDG_STATE_HOME:-$HOME/.local/state}/hefesto-dualsense4unix/launch_env"
    mkdir -p "$lr_dir" 2>/dev/null || return 0
    {
        printf 'appid=%s\n' "$lr_appid"
        printf 'epoch=%s\n' "$(date +%s)"
    } > "$lr_dir/last_run.tmp" 2>/dev/null || return 0
    mv -f "$lr_dir/last_run.tmp" "$lr_dir/last_run" 2>/dev/null || true
    return 0
}

# --- Game Mode COSMIC (PLAT-05) ---------------------------------------------
# Pede Performance ao system76-power na largada do jogo e devolve o perfil
# anterior quando ele terminar. Best-effort ABSOLUTO: sem system76-power =>
# no-op silencioso; qualquer falha (D-Bus mudo, timeout) NUNCA atrasa o launch
# além de ~2 s por chamada nem impede o jogo de abrir.
#
# Detecção (nesta ordem): binário system76-power (o cliente oficial — mesma
# package do daemon) > busctl > dbus-send. A interface D-Bus REAL
# (introspecção ao vivo 2026-07-18) NÃO tem SetProfile: os setters são os
# métodos Performance/Balanced/Battery (sem argumento) e o getter é
# GetProfile — codificado contra o que existe, não contra o esperado.
#
# Restauração: o `exec env` final PRESERVA o PID (o wrapper VIRA o jogo),
# então o trap de EXIT do sh morre no exec — quem restaura é um filho em
# background que espera este PID sumir. O trap fica mesmo assim: cobre a
# saída SEM exec (ex.: env(1) ausente). Restaurar duas vezes é inócuo.
# Se quem lança matar o grupo de processos inteiro no fim, a restauração se
# perde — best-effort documentado, nunca pior que não ter Game Mode.
#
# HEFESTO_GM_POLL_SECS: período do poll do restaurador (default 2 s);
# override existe para os testes não esperarem segundos reais.

GM_BUS_DEST="com.system76.PowerDaemon"
GM_BUS_PATH="/com/system76/PowerDaemon"

gm_have_transport() {
    # Alguém para conversar? Sem transporte, o Game Mode inteiro é no-op —
    # e nenhum sed/head roda à toa (ambientes mínimos não têm nem eles).
    command -v system76-power >/dev/null 2>&1 && return 0
    command -v busctl >/dev/null 2>&1 && return 0
    command -v dbus-send >/dev/null 2>&1
}

gm_run() {
    # Timeout curto (2 s) quando timeout(1) existir; sem ele, roda direto.
    if command -v timeout >/dev/null 2>&1; then
        timeout 2 "$@" 2>/dev/null
    else
        "$@" 2>/dev/null
    fi
}

gm_current_profile() {
    # Imprime o perfil atual em minúsculas (performance/balanced/battery)
    # ou nada quando não dá para perguntar.
    if command -v system76-power >/dev/null 2>&1; then
        gm_run system76-power profile \
            | sed -n 's/^Power Profile:[[:space:]]*//p'
    elif command -v busctl >/dev/null 2>&1; then
        gm_run busctl --system call \
            "$GM_BUS_DEST" "$GM_BUS_PATH" "$GM_BUS_DEST" GetProfile \
            | sed -n 's/^s[[:space:]]*"\(.*\)"$/\1/p'
    elif command -v dbus-send >/dev/null 2>&1; then
        gm_run dbus-send --system --print-reply --dest="$GM_BUS_DEST" \
            "$GM_BUS_PATH" "$GM_BUS_DEST.GetProfile" \
            | sed -n 's/.*string "\(.*\)".*/\1/p'
    fi | head -n 1 | tr '[:upper:]' '[:lower:]'
}

gm_set_profile() {
    # $1 SEMPRE validado antes: battery|balanced|performance (minúsculas).
    # Saída inesperada do daemon nunca vira comando (case fechado).
    case "$1" in
        battery) gm_method="Battery" ;;
        balanced) gm_method="Balanced" ;;
        performance) gm_method="Performance" ;;
        *) return 1 ;;
    esac
    if command -v system76-power >/dev/null 2>&1; then
        gm_run system76-power profile "$1" >/dev/null
    elif command -v busctl >/dev/null 2>&1; then
        gm_run busctl --system call \
            "$GM_BUS_DEST" "$GM_BUS_PATH" "$GM_BUS_DEST" "$gm_method" \
            >/dev/null
    elif command -v dbus-send >/dev/null 2>&1; then
        gm_run dbus-send --system --print-reply --dest="$GM_BUS_DEST" \
            "$GM_BUS_PATH" "$GM_BUS_DEST.$gm_method" >/dev/null
    else
        return 1
    fi
}

enter_game_mode() {
    gm_have_transport || return 0
    gm_prev="$(gm_current_profile)" || gm_prev=""
    case "$gm_prev" in
        battery|balanced) ;;
        *) return 0 ;;  # vazio, performance ou desconhecido: nada a fazer
    esac
    gm_set_profile performance || return 0
    # Trap só para a saída SEM exec (exec bem-sucedido descarta traps).
    trap 'gm_set_profile "$gm_prev" || true' EXIT
    gm_pid=$$
    (
        # Restaurador: espera o PID do jogo (o mesmo deste wrapper, via
        # exec) sumir e devolve o perfil anterior. FDs fechados para nunca
        # segurar o pipe de stdout do jogo aberto (Steam esperaria).
        gm_poll="${HEFESTO_GM_POLL_SECS:-2}"
        while kill -0 "$gm_pid" 2>/dev/null; do
            sleep "$gm_poll" || break
        done
        gm_set_profile "$gm_prev"
    ) </dev/null >/dev/null 2>&1 &
    return 0
}

record_last_run || true

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

# Game Mode COSMIC (PLAT-05): DEPOIS das envs decididas, ANTES do exec — e à
# prova de falha: o jogo abre mesmo se nada disso funcionar.
enter_game_mode || true

exec env "$@"
