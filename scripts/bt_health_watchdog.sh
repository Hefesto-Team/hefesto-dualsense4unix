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

# COMPAT BLUEZ-586-CTL-01 + WATCHDOG-FP-01 (22/07): o bluetoothctl 5.86 é MUDO
# no modo one-shot (regressão do cliente) e a função-sombra interativa também
# se provou cega aqui — "devices Connected" leu 0 com 3 controles vivos e o
# watchdog derrubou uma sessão saudável (22/07 22:41). TODA consulta de estado
# sai do D-Bus (busctl), a única fonte que o daemon responde de verdade.
# bluetoothctl fica SÓ para pair (_btctl_lento segura o quit — pair é
# ASSÍNCRONO e um quit imediato cancelaria o pareamento no meio).
_dbus_device_paths() {
    busctl tree org.bluez --list 2>/dev/null \
        | grep -oE '/org/bluez/hci[0-9]+/dev_[0-9A-Fa-f_]+$' | sort -u || true
}
_dbus_device_prop() {
    # $1 = path D-Bus do device; $2 = propriedade de org.bluez.Device1.
    busctl get-property org.bluez "$1" org.bluez.Device1 "$2" 2>/dev/null \
        | awk '{print $2}' || true
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

# --- vigia 0: modo ativo p/ Nintendo (BT-NINTENDO-ACTIVE-01) ------------------
# Reafirma nome "Nintendo*" + link policy sem SNIFF a cada tick (2 min): cobre
# adaptador que resetou (rfkill/suspend zeram a link policy) e conexões novas.
# Idempotente e barato; delega ao script dedicado. Antes das vigias de bond
# porque um controle em modo ativo cai menos = menos churn de bond.
_ACTIVE=/usr/local/lib/hefesto-dualsense4unix/bt_active_mode.sh
[[ -x "${_ACTIVE}" ]] && "${_ACTIVE}" --quiet 2>/dev/null || true

command -v busctl >/dev/null 2>&1 || { log "busctl ausente — nada a vigiar"; exit 0; }
systemctl is-active --quiet bluetooth.service || { log "bluetooth.service inativo — nada a vigiar"; exit 0; }

# --- vigia 1: estado doente ---------------------------------------------------
# Recusa SÓ conta como doença quando o MAC recusado EXISTE como objeto no
# BlueZ — a doença medida 21/07 era recusar device PRESENTE na lista. Recusar
# MAC sem objeto é o daemon SÃO cumprindo o protocolo (medido 22/07: um 8BitDo
# órfão de bond martelou "unknown device" 8x/10min e o watchdog derrubou uma
# sessão com 3 controles vivos por confundir isso com doença).
DEVICE_PATHS="$(_dbus_device_paths)"
RECUSAS=0
RECUSAS_ORFAS=0
while IFS= read -r MAC; do
    [[ -z "${MAC}" ]] && continue
    if grep -qi "dev_${MAC//:/_}$" <<<"${DEVICE_PATHS}"; then
        RECUSAS=$((RECUSAS + 1))
    else
        RECUSAS_ORFAS=$((RECUSAS_ORFAS + 1))
    fi
done < <(journalctl -u bluetooth --since "-${JANELA_MIN} min" --no-pager 2>/dev/null \
    | grep -E 'Refusing connection from .*: unknown device|error updating services' \
    | grep -oE '([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}' || true)
if [[ "${RECUSAS_ORFAS}" -gt 0 ]]; then
    log "${RECUSAS_ORFAS} recusa(s) de MAC sem objeto no BlueZ ignoradas (órfão re-tentando; daemon são)"
fi

CONECTADOS=0
while IFS= read -r OBJ; do
    [[ -z "${OBJ}" ]] && continue
    if [[ "$(_dbus_device_prop "${OBJ}" Connected)" == "true" ]]; then
        CONECTADOS=$((CONECTADOS + 1))
    fi
done <<<"${DEVICE_PATHS}"

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
# Fonte da lista: D-Bus (WATCHDOG-FP-01). A lista via bluetoothctl vinha VAZIA
# no 5.86 e as vigias 2/2b passavam sem olhar device nenhum (medido 22/07:
# 4 controles conectados, todos Trusted=false, vigia 2b inerte a sessão toda).
while IFS= read -r OBJ; do
    [[ -z "${OBJ}" ]] && continue
    [[ "$(_dbus_device_prop "${OBJ}" Connected)" == "true" ]] || continue
    MAC_U="${OBJ##*dev_}"
    MAC="${MAC_U//_/:}"
    PAIRED="$(_dbus_device_prop "${OBJ}" Paired)"
    BONDED="$(_dbus_device_prop "${OBJ}" Bonded)"
    # --- vigia 2b: bond são mas SEM trust (medido 22/07: roxo Bonded=true e
    # Trusted=false após promoção — o pair explícito NÃO seta trust, e sem
    # trust o BlueZ não autoriza a reconexão ENTRANTE do controle; o botão
    # PS/SYNC vira "não conecta"). Trust é idempotente e não mexe no link,
    # então corrige direto via D-Bus (busctl — imune ao bluetoothctl mudo).
    TRUSTED="$(_dbus_device_prop "${OBJ}" Trusted)"
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
        BONDED2="$(_dbus_device_prop "${OBJ}" Bonded)"
        if [[ "${BONDED2}" == "true" ]]; then
            log "bond de ${MAC} promovido e persistido (Bonded=true)"
            /usr/local/lib/hefesto-dualsense4unix/bt_bonds_snapshot.sh --quiet 2>/dev/null || true
        else
            log "promoção de ${MAC} NÃO persistiu (Bonded=${BONDED2:-?}) — o doctor vai apontar; cura manual: bluetoothctl remove ${MAC} e re-parear em modo pareamento"
        fi
    fi
done <<<"${DEVICE_PATHS}"
exit 0
