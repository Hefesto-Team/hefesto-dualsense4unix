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
#   scripts/fix_wireplumber_default_source.sh [--install|--disable-source|--reset-only|--status]
#     --install         (default) instala o drop-in que REBAIXA + reset + restart.
#     --disable-source  DESABILITA a source do DualSense (node.disabled; só-HID).
#                       Remove o mic do controle de vez — vence até escassez de fonte.
#     --reset-only      só reelege a fonte padrão e reinicia (sem (re)instalar drop-in).
#     --enable-mic      REMOVE os drop-ins de supressão e deixa o mic do DualSense
#                       utilizável/elegível como padrão (o oposto de --install).
#     --status          mostra a fonte padrão atual e sai.
#
#   Env: HEFESTO_DUALSENSE4UNIX_DUALSENSE_MIC_INTENDED=1 faz --install/--disable
#        virarem --enable-mic automaticamente (a usuária QUER o mic do DualSense).
#
# Exit code (modos install/disable-source): 0 = microfone ativo != DualSense (OK);
#   2 = DualSense ainda ativo por ser a ÚNICA fonte disponível (aviso, não falha);
#   1 = DualSense ativo COM outra fonte available (falha real — drop-in não pegou).
# (FEAT-WIREPLUMBER-DISABLE-SOURCE-MODE-01, BUG-WIREPLUMBER-FIX-FALSE-SUCCESS-01, ADR-019.)

set -euo pipefail

readonly ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly DROPIN_NAME="51-hefesto-dualsense-no-default-source.conf"
readonly DROPIN_SRC="${ROOT_DIR}/assets/wireplumber/${DROPIN_NAME}"
readonly DROPIN_DIR="${HOME}/.config/wireplumber/wireplumber.conf.d"
readonly DROPIN_DST="${DROPIN_DIR}/${DROPIN_NAME}"
readonly DROPIN_DISABLE_NAME="52-hefesto-dualsense-disable-source.conf"
readonly DROPIN_DISABLE_SRC="${ROOT_DIR}/assets/wireplumber/${DROPIN_DISABLE_NAME}"
readonly DROPIN_DISABLE_DST="${DROPIN_DIR}/${DROPIN_DISABLE_NAME}"
readonly STATE_FILE="${HOME}/.local/state/wireplumber/default-nodes"

MODE="install"
for arg in "$@"; do
    case "$arg" in
        --install)        MODE="install" ;;
        --disable-source) MODE="disable" ;;
        --reset-only)     MODE="reset" ;;
        --enable-mic)     MODE="enable-mic" ;;
        --status)         MODE="status" ;;
        *) printf '[wp-fix] aviso: argumento desconhecido: %s\n' "$arg" ;;
    esac
done

log() { printf '[wp-fix] %s\n' "$*"; }

# FEAT-DUALSENSE-MIC-INTENDED-01: se a usuária declarou que QUER o mic do DualSense
# (env HEFESTO_DUALSENSE4UNIX_DUALSENSE_MIC_INTENDED=1), suprimir o mic é o oposto do
# desejado — então qualquer install/disable vira "enable-mic" (remove os drop-ins de
# supressão e deixa o mic utilizável/elegível como padrão).
if [[ "${HEFESTO_DUALSENSE4UNIX_DUALSENSE_MIC_INTENDED:-}" =~ ^(1|true|yes|TRUE|YES)$ ]]; then
    if [[ "${MODE}" == "install" || "${MODE}" == "disable" ]]; then
        log "DUALSENSE_MIC_INTENDED=1 — mic do DualSense é desejado; não suprimo (modo enable-mic)"
        MODE="enable-mic"
    fi
fi

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

install_disable_dropin() {
    if [[ ! -f "${DROPIN_DISABLE_SRC}" ]]; then
        log "ERRO: asset não encontrado: ${DROPIN_DISABLE_SRC}"
        return 1
    fi
    mkdir -p "${DROPIN_DIR}"
    cp -f "${DROPIN_DISABLE_SRC}" "${DROPIN_DISABLE_DST}"
    log "drop-in DISABLE instalado: ${DROPIN_DISABLE_DST}"
}

# Remove a chave de fonte padrão persistida que aponta para o DualSense, para que
# o WirePlumber não tente reeleger o mic do controle no próximo boot. Preserva o
# resto do state. Idempotente.
remove_configured_dualsense() {
    [[ -f "${STATE_FILE}" ]] || return 0
    if grep -qiE '^default\.configured\.audio\.source=.*[Dd]ual[Ss]ense' "${STATE_FILE}" 2>/dev/null; then
        sed -i.bak '/^default\.configured\.audio\.source=.*[Dd]ual[Ss]ense/Id' "${STATE_FILE}"
        log "removida a chave configured do DualSense do state (backup .bak)"
    fi
}

# Nome do default-source ATIVO (pactl preferido; fallback ao '*' do wpctl).
active_default_source() {
    if command -v pactl >/dev/null 2>&1; then
        local p
        p="$(pactl get-default-source 2>/dev/null || true)"
        [[ -n "${p}" ]] && { printf '%s\n' "${p}"; return 0; }
    fi
    wpctl status 2>/dev/null | awk '
        /Sources:/ {insrc=1; next}
        insrc && (/Filters:/ || /Sinks:/ || /Streams:/ || /Video/) {insrc=0}
        insrc && /\*/ { sub(/.*\*[[:space:]]+[0-9]+\.[[:space:]]*/, ""); print; exit }'
}

# 0 se há alguma fonte de captura available que NÃO seja o DualSense.
other_source_available() {
    wpctl status 2>/dev/null | awk '
        /Sources:/ {insrc=1; next}
        insrc && (/Filters:/ || /Sinks:/ || /Streams:/ || /Video/) {insrc=0}
        insrc && /[0-9]+\./ && $0 !~ /[Dd]ual[Ss]ense/ { found=1 }
        END { exit (found ? 0 : 1) }'
}

# O que importa é o MIC do DualSense (alsa_input). O '.monitor' do sink (loopback
# da saída) também casa "DualSense" no nome, mas é inofensivo — não é o microfone
# nem o sintoma de "controle mexendo no mic". Tratamos monitor como OK.
is_dualsense_mic() {
    [[ "$1" =~ [Dd]ual[Ss]ense ]] && [[ "$1" != *[Mm]onitor* ]]
}

# Verifica que o microfone ATIVO não é o MIC do DualSense (settle ~2s).
# Exit: 0 OK; 2 ÚNICO (DualSense por escassez — aviso); 1 FALHA real.
verify_active_not_dualsense() {
    local i cur=""
    for i in 1 2 3 4 5 6 7 8; do          # ~2s (8 x 250ms)
        cur="$(active_default_source || true)"
        is_dualsense_mic "${cur}" || break
        sleep 0.25
    done
    if ! is_dualsense_mic "${cur}"; then
        if [[ "${cur}" =~ [Dd]ual[Ss]ense ]]; then
            log "OK: mic do DualSense desabilitado (ativo é só o monitor do sink: ${cur})"
        else
            log "OK: microfone padrão ativo = ${cur:-<nenhum>} (DualSense fora)"
        fi
        return 0
    fi
    if other_source_available; then
        log "FALHA: o MIC (alsa_input) do DualSense ainda é o ativo, com outra fonte disponível (drop-in não aplicou?)"
        return 1
    fi
    log "AVISO: DualSense é a única fonte de captura disponível — por isso segue ativo."
    log "       conecte webcam/mic, ou use --disable-source para removê-lo de vez."
    return 2
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

enable_mic_dualsense() {
    # Remove os drop-ins que suprimem/desabilitam o mic do DualSense, deixando-o
    # utilizável e elegível como fonte padrão (a persistência do default fica por
    # conta do estado do WirePlumber + profile pro-audio do card). Idempotente.
    local f removed=0
    for f in "${DROPIN_DST}" "${DROPIN_DISABLE_DST}"; do
        if [[ -f "$f" ]]; then
            rm -f "$f" && { log "removido drop-in de supressão: $f"; removed=1; }
        fi
    done
    [[ "$removed" -eq 0 ]] && log "nenhum drop-in de supressão presente (mic já livre)"
    restart_wireplumber
}

case "${MODE}" in
    status)
        show_status
        ;;
    enable-mic)
        enable_mic_dualsense
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
        # BUG-WIREPLUMBER-FIX-FALSE-SUCCESS-01: validar o ATIVO, não só o configured.
        sleep 0.5
        rc=0; verify_active_not_dualsense || rc=$?
        exit "${rc}"
        ;;
    disable)
        install_disable_dropin
        remove_configured_dualsense
        restart_wireplumber
        # após o disable o mic some; elege a onboard como default (evita cair no
        # monitor do sink do DualSense) e confirma que o ativo != mic do DualSense.
        sleep 1
        reset_default_source
        sleep 0.5
        rc=0; verify_active_not_dualsense || rc=$?
        show_status
        exit "${rc}"
        ;;
esac
