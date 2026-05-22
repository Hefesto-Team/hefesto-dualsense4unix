#!/usr/bin/env bash
# fix_wireplumber_default_source.sh — impede o DualSense de virar o microfone
# padrão do sistema (FEAT-WIREPLUMBER-DUALSENSE-NOT-DEFAULT-SOURCE-01).
#
# Instala um drop-in do WirePlumber que rebaixa a prioridade da fonte de áudio
# do DualSense e reseta a fonte padrão JÁ persistida para uma fonte sã (ex.: o
# microfone da webcam ou o onboard). Cobre o sintoma "o controle fica
# diminuindo/mexendo no microfone" — que é o WirePlumber elegendo o mic do
# controle como entrada padrão ao conectar, não o daemon do Hefesto.
#
# Uso:
#   scripts/fix_wireplumber_default_source.sh [--install|--reset-only|--status]
#     --install     (default) instala o drop-in + reset + restart do WirePlumber.
#     --reset-only  só reelege a fonte padrão e reinicia (sem (re)instalar drop-in).
#     --status      mostra a fonte padrão atual e sai.

set -euo pipefail

readonly ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly DROPIN_NAME="51-hefesto-dualsense-no-default-source.conf"
readonly DROPIN_SRC="${ROOT_DIR}/assets/wireplumber/${DROPIN_NAME}"
readonly DROPIN_DIR="${HOME}/.config/wireplumber/wireplumber.conf.d"
readonly DROPIN_DST="${DROPIN_DIR}/${DROPIN_NAME}"
readonly STATE_FILE="${HOME}/.local/state/wireplumber/default-nodes"

MODE="install"
for arg in "$@"; do
    case "$arg" in
        --install)    MODE="install" ;;
        --reset-only) MODE="reset" ;;
        --status)     MODE="status" ;;
        *) printf '[wp-fix] aviso: argumento desconhecido: %s\n' "$arg" ;;
    esac
done

log() { printf '[wp-fix] %s\n' "$*"; }

show_status() {
    if command -v wpctl >/dev/null 2>&1; then
        log "Default Configured Devices (wpctl):"
        wpctl status 2>/dev/null | sed -n '/Default Configured/,$p' | sed -n '1,6p' || true
    fi
    if [[ -f "${STATE_FILE}" ]]; then
        local persisted
        persisted="$(grep '^default.configured.audio.source=' "${STATE_FILE}" 2>/dev/null || true)"
        log "persistido: ${persisted:-(default.configured.audio.source não definido)}"
    fi
}

# Lê a seção Sources do `wpctl status` e devolve o ID de uma fonte que NÃO seja
# o DualSense — preferindo a marcada como default (*), senão a primeira.
pick_target_source_id() {
    wpctl status 2>/dev/null | awk '
        /Sources:/ {insrc=1; next}
        insrc && (/Filters:/ || /Sinks:/ || /Streams:/ || /Video/) {insrc=0}
        insrc {
            isdef = ($0 ~ /\*/)
            if (match($0, /[0-9]+\./)) {
                id = substr($0, RSTART, RLENGTH - 1)
                desc = substr($0, RSTART + RLENGTH)
                if (desc !~ /[Dd]ual[Ss]ense/) {
                    if (first == "") first = id
                    if (isdef) def = id
                }
            }
        }
        END { if (def != "") print def; else print first }
    '
}

install_dropin() {
    if [[ ! -f "${DROPIN_SRC}" ]]; then
        log "ERRO: asset não encontrado: ${DROPIN_SRC}"
        return 1
    fi
    mkdir -p "${DROPIN_DIR}"
    cp -f "${DROPIN_SRC}" "${DROPIN_DST}"
    log "drop-in instalado: ${DROPIN_DST}"
}

reset_default_source() {
    if ! command -v wpctl >/dev/null 2>&1; then
        log "wpctl ausente — pulei o reset da fonte padrão"
        return 0
    fi
    local target
    target="$(pick_target_source_id || true)"
    if [[ -n "${target}" ]]; then
        if wpctl set-default "${target}" 2>/dev/null; then
            log "fonte padrão reeleita para o id ${target} (não-DualSense)"
        else
            log "aviso: 'wpctl set-default ${target}' falhou"
        fi
    else
        log "aviso: nenhuma fonte não-DualSense encontrada para eleger como padrão"
    fi
}

restart_wireplumber() {
    if command -v systemctl >/dev/null 2>&1; then
        if systemctl --user restart wireplumber 2>/dev/null; then
            log "WirePlumber reiniciado"
        else
            log "aviso: falha ao reiniciar WirePlumber — reinicie a sessão para aplicar"
        fi
    fi
}

case "${MODE}" in
    status)
        show_status
        ;;
    reset)
        reset_default_source
        restart_wireplumber
        show_status
        ;;
    install)
        install_dropin
        reset_default_source
        restart_wireplumber
        show_status
        ;;
esac
