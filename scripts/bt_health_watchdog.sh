#!/usr/bin/env bash
# bt_health_watchdog.sh — vigia o estado "vivo mas doente" do bluetoothd e a
# persistência dos bonds (sprint 2026-07-21-sprint-pesquisa-bluez-estabilidade.md,
# camada 2). Roda pelo hefesto-bt-health-watchdog.timer (a cada 2 min), root.
#
# Duas vigias independentes:
#
# 1. ESTADO DOENTE pós-crash: o bluetoothd renascido recusa devices com
#    "Refusing connection ... unknown device" / "error updating services" em
#    loop (medido 21/07: o 8BitDo passou 47 min sendo recusado). Nem
#    Restart=on-failure nem WatchdogSec pegam isso (o processo está são do
#    ponto de vista do systemd). Cura: restart do serviço — MAS só quando:
#      a) as recusas passam de um limiar numa janela (>= LIMIAR em 10 min;
#         ocorrência isolada também acontece em daemon são — upstream #1570);
#      b) NENHUM device BT está conectado (nunca derrubar sessão viva; no
#         estado doente os controles não conseguem conectar mesmo);
#      c) rate-limit: no máximo 1 restart a cada 10 min (stamp em /run).
#
# 2. BOND TEMPORÁRIO (medido 22/07): device conectado com Paired=yes mas
#    Bonded=no vive só em memória e EVAPORA no disconnect — o caminho
#    confirmado no fonte do BlueZ que persiste é o Pair() explícito via D-Bus.
#    O watchdog tenta promover UMA VEZ por device por boot (stamp em /run):
#    `bluetoothctl pair <MAC>` num device já conectado + agente NoInputNoOutput
#    ativo completa silencioso quando o peer aceita re-pair (JustWorksRepairing).
#    Se o BlueZ recusar (ex.: AlreadyExists sem promover), loga o FAIL honesto —
#    o doctor exibe e o humano decide (remove + re-pair físico).
#    2b (medido 22/07): device com bond são mas Trusted=false não autoriza
#    reconexão ENTRANTE — o watchdog aplica Trusted=true via D-Bus (idempotente).
set -euo pipefail

JANELA_MIN=10
LIMIAR_RECUSAS=8
RATE_LIMIT_S=600
STAMP_RESTART=/run/hefesto-bt-watchdog.restart-stamp
STAMP_DIR=/run/hefesto-bt-watchdog
LOG_TAG=hefesto-bt-watchdog

log() { logger -t "${LOG_TAG}" "$*" 2>/dev/null || true; printf '%s\n' "$*"; }

# COMPAT BLUEZ-586-CTL-01: o bluetoothctl 5.86 é MUDO no modo one-shot
# (regressão do cliente, medida 22/07; o daemon está são). Consultas rodam
# via modo interativo com limpeza de ANSI/prompt (mesma sombra do doctor.sh);
# pair/trust usam _btctl_lento, que segura o quit — pair é ASSÍNCRONO e um
# quit imediato cancelaria o pareamento no meio.
bluetoothctl() {
    command -v bluetoothctl >/dev/null 2>&1 || return 127
    printf '%s\nquit\n' "$*" | command timeout 8 bluetoothctl 2>/dev/null \
        | sed -e $'s/\x1b\\[[0-9;]*[A-Za-z]//g' -e 's/\r//g' -e 's/^\[bluetoothctl\]> //' \
        | awk -v cmd="$*" 'BEGIN{seen=0} $0==cmd{seen=1;next} !seen{next} $0=="quit"{exit} /^\[/{next} {print}'
}
_btctl_lento() {
    # $1 = segundos de espera pós-comando; resto = comando.
    local espera="$1"; shift
    { printf '%s\n' "$*"; sleep "${espera}"; printf 'quit\n'; } \
        | command timeout "$((espera + 10))" bluetoothctl >/dev/null 2>&1
}

if [[ "$(id -u)" -ne 0 ]]; then
    printf 'bt_health_watchdog.sh: requer root\n' >&2
    exit 1
fi
install -d -m 700 "${STAMP_DIR}"

command -v bluetoothctl >/dev/null 2>&1 || { log "bluetoothctl ausente — nada a vigiar"; exit 0; }
systemctl is-active --quiet bluetooth.service || { log "bluetooth.service inativo — nada a vigiar"; exit 0; }

# --- vigia 1: estado doente ---------------------------------------------------
RECUSAS="$(journalctl -u bluetooth --since "-${JANELA_MIN} min" --no-pager 2>/dev/null \
    | grep -cE 'Refusing connection from .*: unknown device|error updating services' || true)"
CONECTADOS="$(bluetoothctl devices Connected 2>/dev/null | grep -c '^Device ' || true)"

if [[ "${RECUSAS}" -ge "${LIMIAR_RECUSAS}" ]]; then
    if [[ "${CONECTADOS}" -gt 0 ]]; then
        log "estado doente suspeito (${RECUSAS} recusas/${JANELA_MIN}min) mas há ${CONECTADOS} device(s) conectado(s) — restart adiado (nunca derrubo sessão viva)"
    else
        AGORA="$(date +%s)"
        ULTIMO=0
        [[ -f "${STAMP_RESTART}" ]] && ULTIMO="$(cat "${STAMP_RESTART}" 2>/dev/null || echo 0)"
        if (( AGORA - ULTIMO < RATE_LIMIT_S )); then
            log "estado doente (${RECUSAS} recusas/${JANELA_MIN}min) — restart segurado pelo rate-limit"
        else
            log "estado doente confirmado (${RECUSAS} recusas/${JANELA_MIN}min, 0 conectados) — reiniciando bluetooth.service"
            printf '%s' "${AGORA}" > "${STAMP_RESTART}"
            systemctl restart bluetooth.service || log "restart do bluetooth.service FALHOU"
        fi
    fi
fi

# --- vigia 2: bond temporário (Paired sem Bonded em device conectado) --------
bluetoothctl devices Connected 2>/dev/null | awk '/^Device /{print $2}' | while read -r MAC; do
    [[ -z "${MAC}" ]] && continue
    OBJ="/org/bluez/hci0/dev_${MAC//:/_}"
    PAIRED="$(busctl get-property org.bluez "${OBJ}" org.bluez.Device1 Paired 2>/dev/null | awk '{print $2}' || true)"
    BONDED="$(busctl get-property org.bluez "${OBJ}" org.bluez.Device1 Bonded 2>/dev/null | awk '{print $2}' || true)"
    # --- vigia 2b: bond são mas SEM trust (medido 22/07: roxo Bonded=true e
    # Trusted=false após promoção — o pair explícito NÃO seta trust, e sem
    # trust o BlueZ não autoriza a reconexão ENTRANTE do controle; o botão
    # PS/SYNC vira "não conecta"). Trust é idempotente e não mexe no link,
    # então corrige direto via D-Bus (busctl — imune ao bluetoothctl mudo).
    TRUSTED="$(busctl get-property org.bluez "${OBJ}" org.bluez.Device1 Trusted 2>/dev/null | awk '{print $2}' || true)"
    if [[ "${TRUSTED}" == "false" ]]; then
        if busctl set-property org.bluez "${OBJ}" org.bluez.Device1 Trusted b true 2>/dev/null; then
            log "device ${MAC} estava sem trust (reconexão entrante bloqueada) — Trusted=true aplicado"
        else
            log "falha ao aplicar Trusted=true em ${MAC} — o doctor vai apontar"
        fi
    fi
    # Bonded ausente na API (BlueZ < 5.65) => não dá para vigiar; pula.
    [[ -z "${BONDED}" ]] && continue
    if [[ "${BONDED}" == "false" ]]; then
        STAMP="${STAMP_DIR}/promoted-${MAC//:/-}"
        if [[ -f "${STAMP}" ]]; then
            log "bond temporário persiste em ${MAC} (Paired=${PAIRED}, Bonded=false) — promoção já tentada neste boot; re-pair manual necessário (bluetoothctl remove + pair)"
            continue
        fi
        : > "${STAMP}"
        log "device conectado com bond TEMPORÁRIO (${MAC}: Paired=${PAIRED}, Bonded=false) — tentando promover via Pair() explícito"
        _btctl_lento 25 pair "${MAC}" || true
        _btctl_lento 5 trust "${MAC}" || true
        BONDED2="$(busctl get-property org.bluez "${OBJ}" org.bluez.Device1 Bonded 2>/dev/null | awk '{print $2}' || true)"
        if [[ "${BONDED2}" == "true" ]]; then
            log "bond de ${MAC} promovido e persistido (Bonded=true)"
            /usr/local/lib/hefesto-dualsense4unix/bt_bonds_snapshot.sh --quiet 2>/dev/null || true
        else
            log "promoção de ${MAC} NÃO persistiu (Bonded=${BONDED2:-?}) — o doctor vai apontar; cura manual: bluetoothctl remove ${MAC} e re-parear em modo pareamento"
        fi
    fi
done
exit 0
