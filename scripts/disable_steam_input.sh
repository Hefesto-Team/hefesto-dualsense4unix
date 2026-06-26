#!/usr/bin/env bash
# disable_steam_input.sh — desliga Steam Input PSSupport no DualSense para
# evitar conflito com o daemon Hefesto (FEAT-DISABLE-STEAM-INPUT-PSSUPPORT-01).
#
# Por quê: a Steam, com "PlayStation Controller Support" em modo "Always
# enabled" (SteamController_PSSupport=2), pega o /dev/hidraw* do DualSense
# exclusivamente e re-injeta como "Steam Virtual Gamepad" com bindings de
# desktop_ps4.vdf — mapeia touchpad como mouse absoluto, botões como teclas
# globais, em qualquer janela em background. Isso conflita com o daemon
# Hefesto, que também quer ler o controle, e (sem o daemon) é a causa dos
# 3 sintomas clássicos: touchpad move cursor, mic muting spam, botões em
# background. No Windows o driver Sony nativo evita esse caminho.
#
# As keys ficam em `localconfig.vdf` per-user em Steam moderno (não no
# config.vdf global como nas versões antigas). Por padrão este script
# itera por TODOS os installs de Steam conhecidos (.deb, Flatpak, Snap,
# Steam tarball) e por TODOS os user-ids dentro de cada um.
#
# Uso:
#   scripts/disable_steam_input.sh [--apply|--apply-quiet|--status|--restore]
#     --apply       (default) fecha Steam, edita os .vdf, reabre Steam se
#                   estava rodando. Backup automático ao lado de cada .vdf.
#     --apply-quiet edita SÓ se a Steam NÃO estiver rodando; se estiver, ADIA
#                   (loga e sai 0) sem fechar a Steam. Usado pelo guard (path/timer)
#                   para nunca matar a Steam no meio de um jogo — a reescrita
#                   acontece quando a Steam já saiu (que é quando ela grava o vdf).
#     --status      só relata o estado atual (PSSupport / UseSteamControllerConfig)
#                   em cada .vdf. Não modifica nada.
#     --restore     reverte o último backup (.bak.steam-input-<ts>) de cada .vdf.
#
# Backups: `<localconfig.vdf>.bak.steam-input-<unix-ts>`. Idempotente.
# Exit 0 se nada precisava ser feito, 0 se ação aplicada com sucesso,
# != 0 em erro (sed/cp falham, Steam não fechou, etc.).

set -uo pipefail   # sem -e: cada usuário tem o seu vdf, falha de um não derruba os outros.

MODE="apply"
for arg in "$@"; do
    case "$arg" in
        --apply)       MODE="apply" ;;
        --apply-quiet) MODE="apply-quiet" ;;
        --status)      MODE="status" ;;
        --restore)     MODE="restore" ;;
        -h|--help)
            sed -n '2,30p' "${BASH_SOURCE[0]}" | sed 's/^# //; s/^#//'
            exit 0
            ;;
        *) printf '[steam-input] aviso: argumento desconhecido: %s\n' "$arg" ;;
    esac
done

log() { printf '[steam-input] %s\n' "$*"; }

# Globs de localconfig.vdf cobrindo formatos comuns de Steam no Linux.
# Bash globbing: matches que não existem são removidos via nullglob.
shopt -s nullglob
VDF_GLOBS=(
    "${HOME}/.steam/steam/userdata/"*/config/localconfig.vdf
    "${HOME}/.local/share/Steam/userdata/"*/config/localconfig.vdf
    "${HOME}/.var/app/com.valvesoftware.Steam/.steam/steam/userdata/"*/config/localconfig.vdf
    "${HOME}/snap/steam/common/.steam/steam/userdata/"*/config/localconfig.vdf
)
# Dedup: paths via symlink (ex: ~/.steam/steam -> ~/.steam/debian-installation)
# podem aparecer duplicados; resolvemos via readlink -f e mantemos só uniques.
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
    exit 0
fi

# Retorna 0 se o vdf tem PSSupport ou UseSteamControllerConfig em "1" OU "2";
# 1 caso contrário. "[12]" pega tanto o "Always enabled" (=2) quanto o per-game
# "1" que o legado aurora-steam-input-fix escrevia (e que antes escapava daqui).
needs_fix() {
    local vdf="$1"
    grep -qE '"(SteamController_PSSupport|UseSteamControllerConfig)"[[:space:]]+"[12]"' "$vdf" 2>/dev/null
}

# Lê e mostra contagem por arquivo.
report_state() {
    local vdf="$1" pss uscc
    pss="$(grep -E '"SteamController_PSSupport"[[:space:]]+"[12]"' "$vdf" 2>/dev/null | wc -l)"
    uscc="$(grep -E '"UseSteamControllerConfig"[[:space:]]+"[12]"' "$vdf" 2>/dev/null | wc -l)"
    printf '  %s\n' "$vdf"
    printf '    SteamController_PSSupport="1"|"2": %s\n' "$pss"
    printf '    UseSteamControllerConfig="1"|"2": %s\n' "$uscc"
}

# Steam estava rodando antes? Usado para decidir se reabrimos depois.
steam_running() {
    pgrep -af 'steamrt64/steam' >/dev/null 2>&1 || pgrep -af 'steamwebhelper' >/dev/null 2>&1
}

stop_steam() {
    if ! steam_running; then
        return 0
    fi
    log "fechando Steam (steam -shutdown)..."
    if command -v steam >/dev/null 2>&1; then
        steam -shutdown >/dev/null 2>&1 &
        # Aguarda Steam realmente sair (até 30s). Polling barato.
        local i
        for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
            sleep 2
            steam_running || break
        done
    fi
    if steam_running; then
        log "steam -shutdown não fechou em 30s — fallback pkill"
        pkill -TERM -f 'steamrt64/steam|steamwebhelper' 2>/dev/null || true
        sleep 3
        pkill -KILL -f 'steamrt64/steam|steamwebhelper' 2>/dev/null || true
    fi
    sleep 2  # margem para Steam terminar de gravar últimos arquivos
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
    setsid nohup steam </dev/null >/dev/null 2>&1 &
    disown 2>/dev/null || true
}

# Edita um único .vdf inplace, com backup. Idempotente.
# Trocas:
#   "SteamController_PSSupport"\t\t"2"    -> "0"
#   "UseSteamControllerConfig"\t\t"2"     -> "0"
# (Steam usa tabs literais entre key e value no VDF; preservamos exatamente.)
apply_vdf() {
    local vdf="$1"
    if ! needs_fix "$vdf"; then
        log "ok (nada a fazer): $vdf"
        return 0
    fi
    local ts bak
    ts="$(date +%s)"
    bak="${vdf}.bak.steam-input-${ts}"
    if ! cp -a -- "$vdf" "$bak"; then
        log "ERRO: cp falhou ao criar backup: $bak"
        return 1
    fi
    # sed com $'\t' garante tab literal (não a string literal "\t").
    # -i.tmp evita perda em filesystem sem inplace nativo; removemos o .tmp depois.
    local tab=$'\t'
    if ! sed -i.tmp \
            -e "s/\"SteamController_PSSupport\"${tab}${tab}\"[12]\"/\"SteamController_PSSupport\"${tab}${tab}\"0\"/g" \
            -e "s/\"UseSteamControllerConfig\"${tab}${tab}\"[12]\"/\"UseSteamControllerConfig\"${tab}${tab}\"0\"/g" \
            -- "$vdf"; then
        log "ERRO: sed falhou em $vdf — restaurando do backup"
        cp -a -- "$bak" "$vdf" || true
        return 1
    fi
    rm -f -- "${vdf}.tmp"
    log "editado (backup em $bak): $vdf"
}

# Reverte um único .vdf do backup mais recente.
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

case "${MODE}" in
    status)
        log "${#VDFS[@]} localconfig.vdf encontrado(s):"
        any_needs=0
        for vdf in "${VDFS[@]}"; do
            report_state "$vdf"
            if needs_fix "$vdf"; then any_needs=1; fi
        done
        if [[ "${any_needs}" -eq 1 ]]; then
            log "ação sugerida: scripts/disable_steam_input.sh --apply"
        else
            log "tudo limpo — Steam Input PSSupport não está em modo 2 em nenhum arquivo"
        fi
        ;;
    restore)
        log "revertendo do backup mais recente em cada arquivo"
        was_running=0
        steam_running && was_running=1
        if [[ "${was_running}" -eq 1 ]]; then
            stop_steam || exit 1
        fi
        rc=0
        for vdf in "${VDFS[@]}"; do
            restore_vdf "$vdf" || rc=1
        done
        [[ "${was_running}" -eq 1 ]] && reopen_steam
        exit "${rc}"
        ;;
    apply)
        # Pré-flight: alguém precisa fix? Se ninguém, evita fechar Steam à toa.
        any_needs=0
        for vdf in "${VDFS[@]}"; do
            needs_fix "$vdf" && any_needs=1
        done
        if [[ "${any_needs}" -eq 0 ]]; then
            log "nada a fazer — Steam Input já está OFF em todos os ${#VDFS[@]} vdf(s)"
            exit 0
        fi
        was_running=0
        steam_running && was_running=1
        if [[ "${was_running}" -eq 1 ]]; then
            stop_steam || exit 1
        fi
        rc=0
        for vdf in "${VDFS[@]}"; do
            apply_vdf "$vdf" || rc=1
        done
        [[ "${was_running}" -eq 1 ]] && reopen_steam
        exit "${rc}"
        ;;
    apply-quiet)
        # Nunca fecha a Steam. Se ela está viva, adia (a reescrita pega quando sair).
        if steam_running; then
            log "Steam rodando — adiado (não vou fechar; reaplico quando a Steam sair)"
            exit 0
        fi
        any_needs=0
        for vdf in "${VDFS[@]}"; do
            needs_fix "$vdf" && any_needs=1
        done
        if [[ "${any_needs}" -eq 0 ]]; then
            log "nada a fazer — Steam Input já está OFF em todos os ${#VDFS[@]} vdf(s)"
            exit 0
        fi
        rc=0
        for vdf in "${VDFS[@]}"; do
            apply_vdf "$vdf" || rc=1
        done
        # Steam não estava rodando — nada a reabrir.
        exit "${rc}"
        ;;
esac
