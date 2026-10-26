#!/usr/bin/env bash

set -euo pipefail

readonly ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
_wp_forma() {
    local raiz sistema="${HEFESTO_WIREPLUMBER_SISTEMA:-/usr/share/wireplumber:/etc/wireplumber}"
    local IFS=:
    for raiz in ${sistema}; do
        [[ -n "${raiz}" ]] || continue
        [[ -d "${raiz}/main.lua.d" ]] && { printf 'lua'; return 0; }
        [[ -f "${raiz}/wireplumber.conf" || -d "${raiz}/wireplumber.conf.d" ]] \
            && { printf 'conf'; return 0; }
    done
    printf 'conf'
}
readonly WP_FORMA="$(_wp_forma)"
if [[ "${WP_FORMA}" == "lua" ]]; then
    readonly WP_EXT="lua"
    readonly WP_SUBPASTA="main.lua.d"
    readonly DROPIN_NAME="51-hefesto-dualsense-no-default-source.lua"
    readonly DROPIN_DISABLE_NAME="52-hefesto-dualsense-disable-source.lua"
    readonly DROPIN_OUTPUT_NAME="53-hefesto-dualsense-disable-output.lua"
    readonly DROPIN_ACORDADO_NAME="54-hefesto-dualsense-alto-falante-nunca-dorme.lua"
else
    readonly WP_EXT="conf"
    readonly WP_SUBPASTA="wireplumber.conf.d"
    readonly DROPIN_NAME="51-hefesto-dualsense-no-default-source.conf"
    readonly DROPIN_DISABLE_NAME="52-hefesto-dualsense-disable-source.conf"
    readonly DROPIN_OUTPUT_NAME="53-hefesto-dualsense-disable-output.conf"
    readonly DROPIN_ACORDADO_NAME="54-hefesto-dualsense-alto-falante-nunca-dorme.conf"
fi
readonly WP_RAIZ_DE_USUARIO="${HOME}/.config/wireplumber"
WP_ALTEROU=0
readonly DROPIN_SRC="${ROOT_DIR}/assets/wireplumber/${DROPIN_NAME}"
readonly DROPIN_DIR="${WP_RAIZ_DE_USUARIO}/${WP_SUBPASTA}"
readonly DROPIN_DST="${DROPIN_DIR}/${DROPIN_NAME}"
readonly DROPIN_DISABLE_SRC="${ROOT_DIR}/assets/wireplumber/${DROPIN_DISABLE_NAME}"
readonly DROPIN_DISABLE_DST="${DROPIN_DIR}/${DROPIN_DISABLE_NAME}"
readonly DROPIN_OUTPUT_SRC="${ROOT_DIR}/assets/wireplumber/${DROPIN_OUTPUT_NAME}"
readonly DROPIN_OUTPUT_DST="${DROPIN_DIR}/${DROPIN_OUTPUT_NAME}"
readonly DROPIN_ACORDADO_SRC="${ROOT_DIR}/assets/wireplumber/${DROPIN_ACORDADO_NAME}"
readonly DROPIN_ACORDADO_DST="${DROPIN_DIR}/${DROPIN_ACORDADO_NAME}"
readonly STATE_FILE="${HOME}/.local/state/wireplumber/default-nodes"
readonly MARCA_MIC_DIR="${XDG_STATE_HOME:-${HOME}/.local/state}/hefesto-dualsense4unix"
readonly MARCA_MIC_DST="${MARCA_MIC_DIR}/mic-do-dualsense-pedido.conf"
readonly DOCTOR_SH="${ROOT_DIR}/scripts/doctor.sh"

MODE="install"
FONTE_CONSULTADA=""
AGUARDA_NOME=0
for arg in "$@"; do
    if [[ "${AGUARDA_NOME}" -eq 1 ]]; then
        FONTE_CONSULTADA="$arg"
        AGUARDA_NOME=0
        continue
    fi
    case "$arg" in
        --fonte-se-sustenta=*)
            MODE="fonte-se-sustenta"
            FONTE_CONSULTADA="${arg#*=}"
            continue
            ;;
        --fonte-se-sustenta)
            MODE="fonte-se-sustenta"
            AGUARDA_NOME=1
            continue
            ;;
    esac
    case "$arg" in
        --melhor-fonte-elegivel) MODE="melhor-fonte-elegivel" ;;
        --outra-captura-elegivel) MODE="outra-captura-elegivel" ;;
        --install)        MODE="install" ;;
        --disable-source) MODE="disable" ;;
        --reset-only)     MODE="reset" ;;
        --enable-mic)     MODE="enable-mic" ;;
        --promote-source) MODE="promote" ;;
        --unmute-routes)  MODE="unmute-routes" ;;
        --nunca-dorme)    MODE="nunca-dorme" ;;
        --marcar-gesto-do-mic)  MODE="marcar-gesto" ;;
        --apagar-gesto-do-mic)  MODE="apagar-gesto" ;;
        --status)         MODE="status" ;;
        *) printf '[wp-fix] aviso: argumento desconhecido: %s\n' "$arg" ;;
    esac
done

log() { printf '[wp-fix] %s\n' "$*"; }

_tira_a_outra_forma() {
    local dst="$1" nome base
    nome="$(basename "${dst}")"
    base="${nome%.*}"
    local velha
    if [[ "${WP_EXT}" == "lua" ]]; then
        velha="${WP_RAIZ_DE_USUARIO}/wireplumber.conf.d/${base}.conf"
    else
        velha="${WP_RAIZ_DE_USUARIO}/main.lua.d/${base}.lua"
    fi
    if [[ -e "${velha}" ]]; then
        rm -f "${velha}"
        WP_ALTEROU=1
    fi
}

_poe_o_dropin() {
    local src="$1" dst="$2"
    if [[ -f "${dst}" ]] && cmp -s "${src}" "${dst}"; then
        return 3
    fi
    mkdir -p "$(dirname "${dst}")"
    cp -f "${src}" "${dst}"
    WP_ALTEROU=1
    return 0
}

_wp_subiu_em() {
    command -v systemctl >/dev/null 2>&1 || return 0
    local t
    t="$(systemctl --user show wireplumber -p ActiveEnterTimestamp --value --timestamp=unix 2>/dev/null)" || return 0
    t="${t#@}"
    if [[ "${t}" =~ ^[0-9]+$ && "${t}" -gt 0 ]]; then
        printf '%s' "${t}"
    fi
    return 0
}

_wp_nao_leu_o_disco() {
    local subiu f quando raiz="${HEFESTO_RAIZ_UCM:-/usr/share/alsa/ucm2}"
    subiu="$(_wp_subiu_em)"
    [[ -n "${subiu}" ]] || return 1
    for f in "${DROPIN_DST}" "${DROPIN_DISABLE_DST}" "${DROPIN_OUTPUT_DST}" \
             "${DROPIN_ACORDADO_DST}" "${raiz}/USB-Audio/Hefesto/DualSense-HiFi.conf" \
             "${raiz}"/conf.d/USB-Audio/*DualSense*.conf; do
        [[ -f "${f}" ]] || continue
        quando="$(stat -c %Y "${f}" 2>/dev/null)" || continue
        if [[ "${quando}" -gt "${subiu}" ]]; then
            log "${f} é mais novo que o WirePlumber vivo"
            return 0
        fi
    done
    return 1
}

restart_wireplumber_se_alterou() {
    if [[ "${WP_ALTEROU}" -eq 1 ]] || _wp_nao_leu_o_disco; then
        restart_wireplumber
    else
        log "nada a reiniciar — o WirePlumber já roda com a regra"
    fi
}

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
        local guardada
        guardada="$(sed -n 's/^default\.configured\.audio\.source=//p' "${STATE_FILE}" 2>/dev/null | head -n1 || true)"
        log "preferência de fonte guardada no WirePlumber (lida do estado dele): ${guardada:-(nenhuma)}"
    fi
}

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

fontes_elegiveis() {
    [[ -r "${DOCTOR_SH}" ]] || return 1
    command -v pactl >/dev/null 2>&1 || return 1
    local longo curta
    longo="$(LC_ALL=C pactl --format=json list sources 2>/dev/null || true)"
    curta="$(LC_ALL=C pactl list sources short 2>/dev/null || true)"
    [[ -n "${curta}" ]] || return 1
    printf '%s\n' "${curta}" | bash -c '
        doutor="$1"; longo="$2"
        set --
        source "${doutor}" >/dev/null 2>&1 || exit 0
        _sources_com_porta_usavel "${longo}" \
            | awk "tolower(\$2) ~ /dualsense/ { next }
                   tolower(\$2) ~ /\\.monitor\$/ { next }
                   { print }"
    ' -- "${DOCTOR_SH}" "${longo}" 2>/dev/null || true
}

fonte_se_sustenta() {
    local nome="${1:-}"
    [[ -n "${nome}" ]] || return 0
    [[ -r "${DOCTOR_SH}" ]] || return 1
    command -v pactl >/dev/null 2>&1 || return 1
    local longo curta
    longo="$(LC_ALL=C pactl --format=json list sources 2>/dev/null || true)"
    curta="$(LC_ALL=C pactl list sources short 2>/dev/null || true)"
    [[ -n "${curta}" ]] || return 1
    printf '%s\n' "${curta}" | bash -c '
        doutor="$1"; longo="$2"; alvo="$3"
        set --
        source "${doutor}" >/dev/null 2>&1 || exit 0
        _sources_com_porta_usavel "${longo}" \
            | awk -v alvo="${alvo}" "\$2 == alvo { print \$2 }"
    ' -- "${DOCTOR_SH}" "${longo}" "${nome}" 2>/dev/null || true
}

pick_target_source_name() {
    local elegiveis
    elegiveis="$(fontes_elegiveis)" || return 1
    [[ -n "${elegiveis}" ]] || return 0
    printf '%s\n' "${elegiveis}" | bash -c '
        doutor="$1"
        set --
        source "${doutor}" >/dev/null 2>&1 || exit 0
        _melhor_source_de_captura 0
    ' -- "${DOCTOR_SH}" 2>/dev/null || true
}

outra_captura_elegivel() {
    local elegiveis
    elegiveis="$(fontes_elegiveis)" || return 1
    elegiveis="$(printf '%s\n' "${elegiveis}" | awk 'tolower($2) !~ /^hefesto_mic_/')"
    [[ -n "${elegiveis}" ]] || return 0
    printf '%s\n' "${elegiveis}" | bash -c '
        doutor="$1"
        set --
        source "${doutor}" >/dev/null 2>&1 || exit 0
        _melhor_source_de_captura 0
    ' -- "${DOCTOR_SH}" 2>/dev/null || true
}

install_dropin() {
    if [[ ! -f "${DROPIN_SRC}" ]]; then
        log "ERRO: asset não encontrado: ${DROPIN_SRC}"
        return 1
    fi
    local rc=0
    _poe_o_dropin "${DROPIN_SRC}" "${DROPIN_DST}" || rc=$?
    _tira_a_outra_forma "${DROPIN_DST}"
    if [[ "${rc}" -eq 3 ]]; then
        log "drop-in já estava igual: ${DROPIN_DST}"
    else
        log "drop-in instalado: ${DROPIN_DST}"
    fi
}

install_dropin_acordado() {
    if [[ ! -f "${DROPIN_ACORDADO_SRC}" ]]; then
        log "ERRO: asset não encontrado: ${DROPIN_ACORDADO_SRC}"
        return 1
    fi
    if [[ -f "${DROPIN_ACORDADO_DST}" ]] \
        && cmp -s "${DROPIN_ACORDADO_SRC}" "${DROPIN_ACORDADO_DST}"; then
        _tira_a_outra_forma "${DROPIN_ACORDADO_DST}"
        log "o alto-falante já está marcado para nunca dormir: ${DROPIN_ACORDADO_DST}"
        return 3
    fi
    _poe_o_dropin "${DROPIN_ACORDADO_SRC}" "${DROPIN_ACORDADO_DST}" || true
    _tira_a_outra_forma "${DROPIN_ACORDADO_DST}"
    log "drop-in NUNCA-DORME instalado: ${DROPIN_ACORDADO_DST}"
    log "  o sink do controle para de ser suspenso; o primeiro som depois do"
    log "  silêncio sai inteiro (SOM-QUE-NAO-DORME-01)"
    return 0
}

install_disable_dropin() {
    if [[ ! -f "${DROPIN_DISABLE_SRC}" ]]; then
        log "ERRO: asset não encontrado: ${DROPIN_DISABLE_SRC}"
        return 1
    fi
    _poe_o_dropin "${DROPIN_DISABLE_SRC}" "${DROPIN_DISABLE_DST}" || true
    _tira_a_outra_forma "${DROPIN_DISABLE_DST}"
    log "drop-in DISABLE instalado: ${DROPIN_DISABLE_DST}"
    if [[ -f "${DROPIN_OUTPUT_SRC}" ]]; then
        _poe_o_dropin "${DROPIN_OUTPUT_SRC}" "${DROPIN_OUTPUT_DST}" || true
        _tira_a_outra_forma "${DROPIN_OUTPUT_DST}"
        log "drop-in DISABLE-OUTPUT instalado: ${DROPIN_OUTPUT_DST}"
        log "AVISO: o 53 desabilita também o SINK (saida) do DualSense — o"
        log "       alto-falante e o fone no jack do controle ficam MUDOS, e o"
        log "       canal de haptic-de-audio some. O rumble do jogo NAO usa esse"
        log "       canal (vai por HID/vpad), entao a vibracao in-game continua."
        log "       Reverter: bash scripts/fix_wireplumber_default_source.sh --enable-mic"
        log "       + systemctl --user restart wireplumber."
    fi
}

_pilha_sem_dualsense() {
    awk '
        BEGIN { base = "default.configured.audio.source" }
        {
            linha = $0
            p = index(linha, "=")
            chave = (p > 1) ? substr(linha, 1, p - 1) : ""
            valor = (p > 0) ? substr(linha, p + 1) : ""
            if (chave != base && chave !~ ("^" base "\\.[0-9]+$")) { print; next }
            if (tolower(valor) ~ /dualsense/) next
            pilha[n++] = valor
        }
        END {
            for (i = 0; i < n; i++) {
                if (i == 0) print base "=" pilha[i]
                else        print base "." (i - 1) "=" pilha[i]
            }
        }
    '
}

remove_configured_dualsense() {
    [[ -f "${STATE_FILE}" ]] || return 0
    if grep -qiE '^default\.configured\.audio\.source(\.[0-9]+)?=.*[Dd]ual[Ss]ense' "${STATE_FILE}" 2>/dev/null; then
        cp -f "${STATE_FILE}" "${STATE_FILE}.bak" 2>/dev/null || true
        local tmp
        tmp="$(mktemp "${STATE_FILE}.hefesto.XXXXXX")" || return 1
        if _pilha_sem_dualsense < "${STATE_FILE}" > "${tmp}"; then
            mv -f "${tmp}" "${STATE_FILE}"
            WP_ALTEROU=1
            log "entradas do DualSense removidas da pilha de fonte padrão, resto do histórico preservado (backup .bak)"
        else
            rm -f "${tmp}"
            log "ERRO: não consegui reescrever ${STATE_FILE} — nada foi alterado"
            return 1
        fi
    fi
}

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

other_source_available() {
    local elegiveis
    if elegiveis="$(fontes_elegiveis)"; then
        [[ -n "${elegiveis}" ]]
        return
    fi
    wpctl status 2>/dev/null | awk '
        /Sources:/ {insrc=1; next}
        insrc && (/Filters:/ || /Sinks:/ || /Streams:/ || /Video/) {insrc=0}
        insrc && /[0-9]+\./ && $0 !~ /[Dd]ual[Ss]ense/ { found=1 }
        END { exit (found ? 0 : 1) }'
}

is_dualsense_mic() {
    [[ "$1" =~ [Dd]ual[Ss]ense ]] && [[ "$1" != *[Mm]onitor* ]]
}

is_monitor_source() {
    [[ "$1" == *.monitor ]] || [[ "$1" == *.[Mm]onitor ]]
}

e_o_nada_do_pipewire() {
    [[ "$1" == auto_null* ]]
}

verify_active_not_dualsense() {
    local i cur=""
    for i in $(seq 1 20); do
        cur="$(active_default_source || true)"
        if [[ -n "${cur}" ]] \
           && ! e_o_nada_do_pipewire "${cur}" \
           && ! is_monitor_source "${cur}" \
           && ! is_dualsense_mic "${cur}"; then
            break
        fi
        sleep 0.25
    done
    if e_o_nada_do_pipewire "${cur}"; then
        log "FALHA: depois de ~5s a fonte padrão ainda é o ${cur} — o nó de"
        log "       escassez do PipeWire. Não há fonte de captura PRONTA nesta"
        log "       máquina: nem microfone, nem webcam, nem o DualSense."
        log "       Conecte um microfone e rode de novo."
        return 3
    fi
    if is_monitor_source "${cur}"; then
        log "FALHA: a fonte padrão é um MONITOR (${cur}) — não é microfone nenhum:"
        log "       o que qualquer aplicativo gravar é o áudio de SAÍDA do sistema,"
        log "       não a voz — e o medidor de nível mostra sinal, então PARECE que"
        log "       está funcionando."
        return 3
    fi
    if ! is_dualsense_mic "${cur}"; then
        log "OK: microfone padrão ativo = ${cur:-<nenhum>} (DualSense fora)"
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
    local nome=""
    if nome="$(pick_target_source_name)"; then
        if [[ -z "${nome}" ]]; then
            log "nenhuma fonte de captura com porta usável para eleger — não elejo nada"
            log "  (eleger uma fonte sem porta usável é o que o WirePlumber desfaz sozinho,"
            log "   devolvendo o monitor do sink e sobrescrevendo a preferência persistida)"
            return 0
        fi
        if pactl set-default-source "${nome}" 2>/dev/null; then
            log "fonte padrão reeleita para ${nome} (porta usável, critério do doctor)"
            return 0
        fi
        log "aviso: 'pactl set-default-source ${nome}' falhou — tento pelo wpctl"
    fi
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

unmute_dualsense_routes() {
    local rotas="${HOME}/.local/state/wireplumber/default-routes"
    [[ -f "$rotas" ]] || { log "sem default-routes — nada a desmutar"; return 0; }
    grep -qiE 'dualsense.*"mute":true' "$rotas" || {
        log "rotas do DualSense já sem mute"
        return 0
    }
    command -v systemctl >/dev/null 2>&1 && systemctl --user stop wireplumber 2>/dev/null || true
    cp -f "$rotas" "${rotas}.hefesto.bak" 2>/dev/null || true
    sed -i -E '/[Dd]ual[Ss]ense/ s/"mute":true/"mute":false/g' "$rotas"
    log "mute persistido do DualSense removido (backup em ${rotas}.hefesto.bak)"
}

usb_quirk_active_session() {
    local marker="054c:0ce6:gn"
    grep -q "${marker}" /proc/cmdline 2>/dev/null && return 0
    { [[ -r /sys/module/usbcore/parameters/quirks ]] \
        && grep -q "${marker}" /sys/module/usbcore/parameters/quirks 2>/dev/null; } && return 0
    return 1
}

_arma_dropins_do_mic() {
    local modo="${1:-}"
    local f removed=0
    for f in "${DROPIN_DISABLE_DST}" "${DROPIN_OUTPUT_DST}"; do
        _tira_a_outra_forma "$f"
        if [[ -f "$f" ]]; then
            rm -f "$f" && { log "removido drop-in de supressão: $f"; removed=1; }
        fi
    done
    [[ "$removed" -eq 0 ]] && log "nenhum drop-in de supressão presente (mic já livre)"
    if [[ "${modo}" == "sem-promotor" ]]; then
        _tira_a_outra_forma "${DROPIN_DST}"
        if [[ -f "${DROPIN_DST}" ]]; then
            rm -f "${DROPIN_DST}" \
                && log "removido o drop-in 51 (promoção explícita: a ausência dele é o sinal que o doctor lê)"
        fi
        return 0
    fi
    if [[ -f "${DROPIN_DST}" ]]; then
        log "promotor mantido: ${DROPIN_DST} (a entrada do controle fica acima de qualquer monitor)"
    elif install_dropin; then
        log "promotor instalado: sem ele o monitor da saída venceria o microfone"
    else
        log "AVISO: não consegui instalar o promotor (${DROPIN_NAME}) — o mic fica livre, mas um monitor pode vencê-lo"
    fi
    return 0
}

_marca_do_gesto_gravar() {
    local gesto="${1:-enable-mic}"
    if [[ -f "${MARCA_MIC_DST}" ]]; then
        log "marca do gesto já existe: ${MARCA_MIC_DST} (a data do primeiro pedido fica)"
        return 0
    fi
    mkdir -p "${MARCA_MIC_DIR}" || { log "AVISO: não consegui criar ${MARCA_MIC_DIR}"; return 1; }
    {
        printf '# MARCA DO GESTO — DROPIN-AMBIGUO-01\n'
        printf '#\n'
        printf '# Este arquivo diz: "o microfone do DualSense é escolha DELA".\n'
        printf '# Sem ele, a ausência do drop-in 51 não distingue a promoção\n'
        printf '# explícita da cura que um uninstall desarmou — e o doctor dava\n'
        printf '# [OK] no meio do defeito. Ele é escrito pelo GESTO de ligar o\n'
        printf '# mic e apagado pelo gesto contrário; nunca inferido de estado.\n'
        printf '#\n'
        printf '# Quem lê: scripts/doctor.sh:_prefere_mic_do_dualsense\n'
        printf '# Quem escreve: scripts/fix_wireplumber_default_source.sh, install.sh\n'
        printf '# Quem apaga: --install, --disable-source, uninstall.sh\n'
        printf 'gesto=%s\n' "${gesto}"
        printf 'data=%s\n' "$(date -Is 2>/dev/null || date)"
    } > "${MARCA_MIC_DST}" || { log "AVISO: não consegui gravar ${MARCA_MIC_DST}"; return 1; }
    log "marca do gesto gravada: ${MARCA_MIC_DST} (gesto=${gesto})"
    return 0
}

_marca_do_gesto_apagar() {
    if [[ -f "${MARCA_MIC_DST}" ]]; then
        rm -f "${MARCA_MIC_DST}" && log "marca do gesto removida: ${MARCA_MIC_DST}"
    fi
    return 0
}

enable_mic_dualsense() {
    if [[ "${1:-}" == "sem-promotor" ]]; then
        _marca_do_gesto_gravar "promote-source" || true
    else
        _marca_do_gesto_gravar "enable-mic" || true
    fi
    if ! usb_quirk_active_session; then
        printf '[wp-fix] AVISO: ligar o mic do DualSense SEM o quirk de áudio USB ativo nesta sessão pode REABRIR o storm -71 (o controle cai no meio do jogo).\n' >&2
        printf '[wp-fix]        fix: aplique o quirk com `scripts/install_usb_quirk.sh` (efetivo só no próximo boot/replug).\n' >&2
    fi
    _arma_dropins_do_mic "${1:-}"
    unmute_dualsense_routes
    restart_wireplumber
}

pick_dualsense_source_id() {
    wpctl status 2>/dev/null | awk '
        /Sources:/ {insrc=1; next}
        insrc && (/Filters:/ || /Sinks:/ || /Streams:/ || /Video/) {insrc=0}
        insrc {
            if (match($0, /[0-9]+\./)) {
                id = substr($0, RSTART, RLENGTH - 1)
                desc = substr($0, RSTART + RLENGTH)
                if (desc ~ /[Dd]ual[Ss]ense/ && desc !~ /[Mm]onitor/) {
                    if (first == "") first = id
                }
            }
        }
        END { print first }
    '
}

promote_source_dualsense() {
    enable_mic_dualsense "sem-promotor"
    if [[ -x "${ROOT_DIR}/scripts/doctor.sh" ]]; then
        bash "${ROOT_DIR}/scripts/doctor.sh" --fix-mic --quiet || true
    fi
    if ! command -v wpctl >/dev/null 2>&1; then
        log "wpctl ausente — não consegui eleger o DualSense como fonte padrão"
        return 1
    fi
    local i alvo=""
    for i in 1 2 3 4 5 6 7 8 9 10; do
        alvo="$(pick_dualsense_source_id || true)"
        [[ -n "${alvo}" ]] && break
        sleep 0.3
    done
    if [[ -z "${alvo}" ]]; then
        log "nenhuma fonte de captura do DualSense apareceu — o controle está no cabo?"
        log "  (por Bluetooth não existe fonte para promover: o áudio vem como Opus"
        log "   dentro dos reports HID e precisa da ponte — 'hefesto-dualsense4unix mic bt')"
        return 1
    fi
    if wpctl set-default "${alvo}" 2>/dev/null; then
        log "mic do DualSense promovido a fonte padrão (id ${alvo}) e persistido"
    else
        log "aviso: 'wpctl set-default ${alvo}' falhou"
        return 1
    fi
}

[[ "${BASH_SOURCE[0]}" == "${0}" ]] || return 0

ACORDADO_MUDOU=1
if [[ "${MODE}" != "status" && "${MODE}" != "marcar-gesto" \
   && "${MODE}" != "apagar-gesto" && "${MODE}" != "fonte-se-sustenta" \
   && "${MODE}" != "melhor-fonte-elegivel" \
   && "${MODE}" != "outra-captura-elegivel" ]]; then
    rc_acordado=0
    install_dropin_acordado || rc_acordado=$?
    case "${rc_acordado}" in
        0) ACORDADO_MUDOU=0 ;;
        3) ACORDADO_MUDOU=1 ;;
        *) log "AVISO: não consegui instalar o ${DROPIN_ACORDADO_NAME} — o sink do"
           log "       controle vai continuar suspendendo, e o começo do som se perde" ;;
    esac
fi

case "${MODE}" in
    status)
        show_status
        ;;
    fonte-se-sustenta)
        rc_consulta=0
        fonte_se_sustenta "${FONTE_CONSULTADA}" || rc_consulta=$?
        exit "${rc_consulta}"
        ;;
    melhor-fonte-elegivel)
        rc_consulta=0
        pick_target_source_name || rc_consulta=$?
        exit "${rc_consulta}"
        ;;
    outra-captura-elegivel)
        rc_consulta=0
        outra_captura_elegivel || rc_consulta=$?
        exit "${rc_consulta}"
        ;;
    nunca-dorme)
        if [[ "${ACORDADO_MUDOU}" -eq 0 ]]; then
            restart_wireplumber
        else
            log "nada a reiniciar — o WirePlumber já roda com a regra"
        fi
        exit 0
        ;;
    marcar-gesto)
        _marca_do_gesto_gravar "keep-dualsense-mic"
        exit 0
        ;;
    apagar-gesto)
        _marca_do_gesto_apagar
        exit 0
        ;;
    enable-mic)
        enable_mic_dualsense
        show_status
        ;;
    unmute-routes)
        unmute_dualsense_routes
        restart_wireplumber
        ;;
    promote)
        rc=0; promote_source_dualsense || rc=$?
        show_status
        exit "${rc}"
        ;;
    reset)
        reset_default_source
        restart_wireplumber
        show_status
        ;;
    install)
        _marca_do_gesto_apagar
        install_dropin
        reset_default_source
        restart_wireplumber_se_alterou
        show_status
        sleep 0.5
        rc=0; verify_active_not_dualsense || rc=$?
        exit "${rc}"
        ;;
    disable)
        _marca_do_gesto_apagar
        install_disable_dropin
        remove_configured_dualsense
        restart_wireplumber_se_alterou
        sleep 1
        reset_default_source
        sleep 0.5
        rc=0; verify_active_not_dualsense || rc=$?
        show_status
        exit "${rc}"
        ;;
esac
