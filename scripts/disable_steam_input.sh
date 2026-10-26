#!/usr/bin/env bash

set -uo pipefail
_ajuda() {
  cat <<'AJUDA'
disable_steam_input.sh — desliga Steam Input PSSupport no DualSense para
evitar conflito com o daemon Hefesto (FEAT-DISABLE-STEAM-INPUT-PSSUPPORT-01).

Uso:
  scripts/disable_steam_input.sh [--apply|--apply-quiet|--status|--restore]
    --apply       (default) fecha Steam, edita os .vdf, reabre Steam se
                  estava rodando. Backup automático ao lado de cada .vdf.
    --apply-quiet edita SÓ se a Steam NÃO estiver rodando; se estiver, ADIA
                  (loga e sai 0) sem fechar a Steam. Usado pelo guard (path/timer)
                  para nunca matar a Steam no meio de um jogo — a reescrita
                  acontece quando a Steam já saiu (que é quando ela grava o vdf).
    --status      só relata o estado atual (PSSupport / SwitchSupport /
                  UseSteamControllerConfig) em cada .vdf. Não modifica nada.
AJUDA
}

MODE="apply"
for arg in "$@"; do
    case "$arg" in
        --apply)       MODE="apply" ;;
        --apply-quiet) MODE="apply-quiet" ;;
        --status)      MODE="status" ;;
        --restore)     MODE="restore" ;;
        -h|--help)
            _ajuda
            exit 0
            ;;
        *) printf '[steam-input] aviso: argumento desconhecido: %s\n' "$arg" ;;
    esac
done

log() { printf '[steam-input] %s\n' "$*"; }

resultado() { printf '[steam-input] resultado=%s\n' "$1"; }

shopt -s nullglob
VDF_GLOBS=(
    "${HOME}/.steam/steam/userdata/"*/config/localconfig.vdf
    "${HOME}/.local/share/Steam/userdata/"*/config/localconfig.vdf
    "${HOME}/.var/app/com.valvesoftware.Steam/.steam/steam/userdata/"*/config/localconfig.vdf
    "${HOME}/snap/steam/common/.steam/steam/userdata/"*/config/localconfig.vdf
)
VDFS=()
declare -A SEEN
for vdf in "${VDF_GLOBS[@]}"; do
    real="$(readlink -f -- "$vdf" 2>/dev/null || true)"
    [[ -n "${real}" && -f "${real}" ]] || continue
    [[ -n "${SEEN[$real]:-}" ]] && continue
    SEEN[$real]=1
    VDFS+=("$real")
done
shopt -u nullglob

if [[ "${#VDFS[@]}" -eq 0 ]]; then
    log "nenhum localconfig.vdf encontrado — Steam pode não estar instalada ou nunca foi logada"
    resultado "nada-a-fazer"
    exit 0
fi

needs_fix() {
    local vdf="$1"
    grep -qE '"(SteamController_PSSupport|SteamController_SwitchSupport|UseSteamControllerConfig)"[[:space:]]+"[12]"' "$vdf" 2>/dev/null
}

report_state() {
    local vdf="$1" pss sws uscc
    pss="$(grep -E '"SteamController_PSSupport"[[:space:]]+"[12]"' "$vdf" 2>/dev/null | wc -l)"
    sws="$(grep -E '"SteamController_SwitchSupport"[[:space:]]+"[12]"' "$vdf" 2>/dev/null | wc -l)"
    uscc="$(grep -E '"UseSteamControllerConfig"[[:space:]]+"[12]"' "$vdf" 2>/dev/null | wc -l)"
    printf '  %s\n' "$vdf"
    printf '    SteamController_PSSupport="1"|"2": %s\n' "$pss"
    printf '    SteamController_SwitchSupport="1"|"2": %s\n' "$sws"
    printf '    UseSteamControllerConfig="1"|"2": %s\n' "$uscc"
}

steam_running() {
    pgrep -af 'steamrt64/steam' >/dev/null 2>&1 || pgrep -x steamwebhelper >/dev/null 2>&1
}

steam_game_running() {
    pgrep -f 'SteamLaunch[ ]AppId=[0-9]' >/dev/null 2>&1
}

podar_bins_do_interpretador() {
    la_novo=""
    [ -n "$1" ] || return 0
    la_resto="$1:"
    la_primeiro=1
    while [ -n "$la_resto" ]; do
        la_dir="${la_resto%%:*}"
        la_resto="${la_resto#*:}"
        la_cmp="${la_dir%/}"
        if [ -n "$la_cmp" ]; then
            [ "$la_cmp" = "$la_bin_venv" ] && continue
            [ "$la_cmp" = "$la_bin_conda" ] && continue
        fi
        if [ "$la_primeiro" = 1 ]; then
            la_novo="$la_dir"
            la_primeiro=0
        else
            la_novo="$la_novo:$la_dir"
        fi
    done
    return 0
}

limpar_ambiente_do_interpretador() {
    la_bin_venv=""
    la_bin_conda=""
    la_base="${VIRTUAL_ENV:-}"
    la_base="${la_base%/}"
    [ -n "$la_base" ] && la_bin_venv="$la_base/bin"
    la_base="${CONDA_PREFIX:-}"
    la_base="${la_base%/}"
    [ -n "$la_base" ] && la_bin_conda="$la_base/bin"
    unset VIRTUAL_ENV CONDA_PREFIX CONDA_DEFAULT_ENV CONDA_SHLVL PYTHONHOME PYTHONPATH PYENV_VERSION
    [ -n "$la_bin_venv$la_bin_conda" ] || return 0
    podar_bins_do_interpretador "${PATH:-}"
    [ -n "$la_novo" ] && PATH="$la_novo"
    podar_bins_do_interpretador "${SYSTEM_PATH:-}"
    [ -n "$la_novo" ] && export SYSTEM_PATH="$la_novo"
    return 0
}

stop_steam() {
    if ! steam_running; then
        return 0
    fi
    log "fechando Steam (steam -shutdown)..."
    if command -v steam >/dev/null 2>&1; then
        (
            limpar_ambiente_do_interpretador
            exec steam -shutdown
        ) >/dev/null 2>&1 &
        local i
        for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
            sleep 2
            steam_running || break
        done
    fi
    if steam_running; then
        log "steam -shutdown não fechou em 30s — fallback pkill"
        pkill -TERM -f 'steamrt64/steam' 2>/dev/null || true
        pkill -TERM -x steamwebhelper 2>/dev/null || true
        sleep 3
        pkill -KILL -f 'steamrt64/steam' 2>/dev/null || true
        pkill -KILL -x steamwebhelper 2>/dev/null || true
    fi
    sleep 2
    if steam_running; then
        log "ERRO: Steam ainda rodando — não vou arriscar editar enquanto está vivo"
        return 1
    fi
    return 0
}

reopen_steam() {
    if ! command -v steam >/dev/null 2>&1; then
        log "binário 'steam' fora do PATH — não consigo reabrir; abra manualmente"
        return 0
    fi
    log "reabrindo Steam"
    (
        limpar_ambiente_do_interpretador
        exec setsid nohup steam
    ) </dev/null >/dev/null 2>&1 &
    disown 2>/dev/null || true
}

ALLOWLIST_FILE="${XDG_CONFIG_HOME:-$HOME/.config}/hefesto-dualsense4unix/steam_input_apps.txt"

_SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PONTE_PY="${PONTE_PY:-${_SCRIPT_DIR}/../src/hefesto_dualsense4unix/integrations/steam_input_ponte.py}"

ligar_ponte_da_allowlist() {
    if [[ ! -f "${PONTE_PY}" ]] || ! command -v python3 >/dev/null 2>&1; then
        return 0
    fi
    if steam_running; then
        log "ponte: Steam viva — não escrevo agora (a saída dela engoliria)"
        return 0
    fi
    local saida
    saida="$(python3 "${PONTE_PY}" --ligar 2>&1)" || true
    printf '%s\n' "${saida}" | while IFS= read -r linha; do
        [[ -n "${linha}" ]] && printf '%s\n' "${linha}"
    done
    saida="$(python3 "${PONTE_PY}" --desligar-fora-da-lista 2>&1)" || true
    printf '%s\n' "${saida}" | while IFS= read -r linha; do
        [[ -n "${linha}" ]] && printf '%s\n' "${linha}"
    done
}

ponte_pendente() {
    [[ -f "${PONTE_PY}" ]] || return 1
    command -v python3 >/dev/null 2>&1 || return 1
    python3 "${PONTE_PY}" --estado 2>/dev/null | python3 -c '
import json
import sys

try:
    dados = json.load(sys.stdin)
except (ValueError, OSError):
    sys.exit(1)
pendentes = dados.get("pendentes") or []
for jogo in pendentes:
    print("[steam-input] ponte pendente: " + str(jogo.get("rotulo")))
sys.exit(0 if pendentes else 1)
'
}

_transform_vdf() {
    awk -v allowfile="${ALLOWLIST_FILE}" '
    BEGIN {
        if (allowfile != "") {
            while ((getline linha < allowfile) > 0) {
                sub(/#.*$/, "", linha)
                gsub(/[[:space:]]/, "", linha)
                if (linha != "") allow[linha] = 1
            }
            close(allowfile)
        }
        depth = 0
        pending = ""
    }
    {
        line = $0
        if (line ~ /^[[:space:]]*"[^"]*"[[:space:]]*$/) {
            nome = line
            gsub(/^[[:space:]]*"/, "", nome)
            gsub(/"[[:space:]]*$/, "", nome)
            pending = nome
            print line
            next
        }
        if (line ~ /^[[:space:]]*\{[[:space:]]*$/) {
            depth++
            stack[depth] = pending
            pending = ""
            print line
            next
        }
        if (line ~ /^[[:space:]]*\}[[:space:]]*$/) {
            if (depth > 0) { delete stack[depth]; depth-- }
            print line
            next
        }
        gsub(/"SteamController_PSSupport"\t\t"[12]"/, "\"SteamController_PSSupport\"\t\t\"0\"", line)
        gsub(/"SteamController_SwitchSupport"\t\t"[12]"/, "\"SteamController_SwitchSupport\"\t\t\"0\"", line)
        if (line ~ /"UseSteamControllerConfig"\t\t"[12]"/) {
            if (!(depth > 0 && (stack[depth] in allow))) {
                gsub(/"UseSteamControllerConfig"\t\t"[12]"/, "\"UseSteamControllerConfig\"\t\t\"0\"", line)
            }
        }
        print line
    }'
}

apply_vdf() {
    local vdf="$1"
    if ! needs_fix "$vdf"; then
        log "ok (nada a fazer): $vdf"
        return 0
    fi
    local tmp="${vdf}.hefesto-tmp"
    if ! _transform_vdf < "$vdf" > "$tmp"; then
        log "ERRO: transformação falhou em $vdf"
        rm -f -- "$tmp"
        return 1
    fi
    if cmp -s -- "$vdf" "$tmp"; then
        log "ok (restante é allowlist per-app, preservada): $vdf"
        rm -f -- "$tmp"
        return 0
    fi
    local ts bak
    ts="$(date +%s)"
    bak="${vdf}.bak.steam-input-${ts}"
    if ! cp -a -- "$vdf" "$bak"; then
        log "ERRO: cp falhou ao criar backup: $bak"
        rm -f -- "$tmp"
        return 1
    fi
    if ! cat -- "$tmp" > "$vdf"; then
        log "ERRO: escrita falhou em $vdf — restaurando do backup"
        cp -a -- "$bak" "$vdf" || true
        rm -f -- "$tmp"
        return 1
    fi
    rm -f -- "$tmp"
    log "editado (backup em $bak): $vdf"
}

restore_vdf() {
    local vdf="$1"
    local latest
    latest="$(ls -1t "${vdf}.bak.steam-input-"* 2>/dev/null | head -1 || true)"
    if [[ -z "${latest}" ]]; then
        log "sem backup para restaurar: $vdf"
        return 0
    fi
    if cp -a -- "$latest" "$vdf"; then
        log "restaurado de $latest -> $vdf"
    else
        log "ERRO: falha ao restaurar $vdf"
        return 1
    fi
}

needs_real_fix() {
    local vdf="$1"
    needs_fix "$vdf" || return 1
    local tmp
    tmp="$(mktemp)"
    if ! _transform_vdf < "$vdf" > "$tmp" 2>/dev/null; then
        rm -f -- "$tmp"
        return 0
    fi
    if cmp -s -- "$vdf" "$tmp"; then
        rm -f -- "$tmp"
        return 1
    fi
    rm -f -- "$tmp"
    return 0
}

case "${MODE}" in
    status)
        log "${#VDFS[@]} localconfig.vdf encontrado(s):"
        any_needs=0
        any_allow=0
        for vdf in "${VDFS[@]}"; do
            report_state "$vdf"
            if needs_real_fix "$vdf"; then
                any_needs=1
            elif needs_fix "$vdf"; then
                any_allow=1
            fi
        done
        if ponte_pendente; then
            any_needs=1
        fi
        if [[ "${any_needs}" -eq 1 ]]; then
            log "ação sugerida: scripts/disable_steam_input.sh --apply"
            resultado "precisa-corrigir"
        else
            if [[ "${any_allow}" -eq 1 ]]; then
                log "nota: Steam Input per-app ATIVO só em apps da allowlist (deliberado — ex.: MMJ)"
            fi
            log "tudo limpo — PSSupport/SwitchSupport não estão em modo 1|2 em nenhum arquivo (fora da allowlist)"
            resultado "nada-a-fazer"
        fi
        ;;
    restore)
        if steam_game_running; then
            log "RECUSADO: há um JOGO da Steam em execução — fechar a Steam agora o MATARIA"
            resultado "recusado-jogo-aberto"
            exit 4
        fi
        log "revertendo do backup mais recente em cada arquivo"
        was_running=0
        steam_running && was_running=1
        if [[ "${was_running}" -eq 1 ]]; then
            if ! stop_steam; then
                resultado "steam-nao-fechou"
                exit 5
            fi
        fi
        rc=0
        for vdf in "${VDFS[@]}"; do
            restore_vdf "$vdf" || rc=1
        done
        [[ "${was_running}" -eq 1 ]] && reopen_steam
        if [[ "${rc}" -eq 0 ]]; then resultado "restaurado"; else resultado "erro"; fi
        exit "${rc}"
        ;;
    apply)
        if steam_game_running; then
            log "RECUSADO: há um JOGO da Steam em execução — fechar a Steam agora o MATARIA"
            log "  feche o jogo e rode de novo (nada foi tocado)"
            resultado "recusado-jogo-aberto"
            exit 4
        fi
        any_needs=0
        for vdf in "${VDFS[@]}"; do
            needs_real_fix "$vdf" && any_needs=1
        done
        if ponte_pendente >/dev/null 2>&1; then
            any_needs=1
        fi
        if [[ "${any_needs}" -eq 0 ]]; then
            log "nada a fazer — Steam Input já está OFF em todos os ${#VDFS[@]} vdf(s)"
            resultado "nada-a-fazer"
            exit 0
        fi
        was_running=0
        steam_running && was_running=1
        if [[ "${was_running}" -eq 1 ]]; then
            if ! stop_steam; then
                resultado "steam-nao-fechou"
                exit 5
            fi
        fi
        rc=0
        for vdf in "${VDFS[@]}"; do
            apply_vdf "$vdf" || rc=1
        done
        ligar_ponte_da_allowlist
        [[ "${was_running}" -eq 1 ]] && reopen_steam
        if [[ "${rc}" -eq 0 ]]; then resultado "aplicado"; else resultado "erro"; fi
        exit "${rc}"
        ;;
    apply-quiet)
        if steam_running; then
            log "Steam rodando — adiado (não vou fechar; reaplico quando a Steam sair)"
            resultado "adiado-steam-aberta"
            exit 0
        fi
        any_needs=0
        for vdf in "${VDFS[@]}"; do
            needs_real_fix "$vdf" && any_needs=1
        done
        ligar_ponte_da_allowlist
        if [[ "${any_needs}" -eq 0 ]]; then
            log "nada a fazer — Steam Input já está OFF em todos os ${#VDFS[@]} vdf(s)"
            resultado "nada-a-fazer"
            exit 0
        fi
        rc=0
        for vdf in "${VDFS[@]}"; do
            apply_vdf "$vdf" || rc=1
        done
        if [[ "${rc}" -eq 0 ]]; then resultado "aplicado"; else resultado "erro"; fi
        exit "${rc}"
        ;;
esac
