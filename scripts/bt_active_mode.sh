#!/usr/bin/env bash
# bt_active_mode.sh — deixa o rádio BR/EDR do adaptador amigável aos controles
# Nintendo (Switch Pro / 8BitDo modo Switch), curando na RAIZ a desconexão sob
# carga (BT-NINTENDO-ACTIVE-01, 22/07). Root. Idempotente. Reversível.
#
# DUAS medidas, ambas medidas/pesquisadas
# (docs/process/estudos/2026-07-22-pesquisa-pro-controller-bt-e-lightbar-keepalive.md):
#
# 1) NOME do host prefixado "Nintendo": o Pro Controller LÊ o nome Bluetooth do
#    host e, se não for "Nintendo*", cai num sniff mode frágil que não manda
#    keepalive — sob rumble+IMU os reports enfileiram e o controle desconecta.
#    3 fontes independentes (Fyra Labs, bluez#1797, ArchWiki): renomear o
#    adaptador com prefixo "Nintendo" tira o controle desse modo. Aplicado via
#    Alias do BlueZ (persiste em /var/lib/bluetooth/<adapter>/settings).
#
# 2) LINK POLICY sem SNIFF: complementa o nome no nível HCI — o LM local passa a
#    RECUSAR LMP_sniff_req, forçando modo ativo. Setado como default do
#    adaptador (novas conexões herdam) + por-conexão nos já conectados. Provado
#    ao vivo 22/07: os DualSense seguem conectados normalmente sem sniff.
#
# Reverter: `hciconfig hci0 lp rswitch hold sniff park` e Alias de volta ao
# hostname (o uninstall faz). Vale a partir do próximo start do bluetoothd/boot;
# este script NUNCA reinicia o serviço.
set -euo pipefail

LOG_TAG=hefesto-bt-active
log() { logger -t "${LOG_TAG}" "$*" 2>/dev/null || true; [[ "${QUIET:-0}" -eq 1 ]] || printf '%s\n' "$*"; }

if [[ "$(id -u)" -ne 0 ]]; then
    printf 'bt_active_mode.sh: requer root\n' >&2
    exit 1
fi

QUIET=0
[[ "${1:-}" == "--quiet" ]] && QUIET=1

command -v hciconfig >/dev/null 2>&1 || { log "hciconfig ausente (bluez-hcidump/bluez) — nada a fazer"; exit 0; }

# Adaptador primário (hci0 por padrão; deriva do primeiro listado).
HCI="$(hciconfig 2>/dev/null | awk -F: '/^hci/{print $1; exit}')"
[[ -z "${HCI}" ]] && { log "nenhum adaptador HCI — nada a fazer"; exit 0; }

# --- 1) NOME "Nintendo*" via Alias do BlueZ (idempotente) --------------------
if command -v busctl >/dev/null 2>&1; then
    ADAPTER_OBJ="/org/bluez/${HCI}"
    ALIAS_ATUAL="$(busctl get-property org.bluez "${ADAPTER_OBJ}" org.bluez.Adapter1 Alias 2>/dev/null | sed -E 's/^s "?//; s/"?$//' || true)"
    if [[ -n "${ALIAS_ATUAL}" && "${ALIAS_ATUAL}" != Nintendo* ]]; then
        NOVO="Nintendo ${ALIAS_ATUAL}"
        if busctl set-property org.bluez "${ADAPTER_OBJ}" org.bluez.Adapter1 Alias s "${NOVO}" 2>/dev/null; then
            log "alias do adaptador -> '${NOVO}' (tira o Pro do sniff frágil)"
        else
            log "falha ao setar alias (adaptador não pronto?) — o watchdog re-tenta"
        fi
    fi
fi

# --- 2) LINK POLICY sem SNIFF ------------------------------------------------
# Default do adaptador (novas conexões herdam — instantâneo p/ quem conectar
# depois, sem precisar caçar a borda da conexão).
if hciconfig "${HCI}" lp 2>/dev/null | grep -q 'SNIFF'; then
    hciconfig "${HCI}" lp rswitch 2>/dev/null \
        && log "link policy default de ${HCI} -> RSWITCH (sem SNIFF)" \
        || log "falha ao setar link policy default (adaptador não pronto?)"
fi

# Por-conexão nos já conectados (belt-and-suspenders; hcitool ausente = pula).
if command -v hcitool >/dev/null 2>&1; then
    hcitool con 2>/dev/null | awk '/[0-9A-F:]{17}/{for(i=1;i<=NF;i++) if($i ~ /^([0-9A-F]{2}:){5}[0-9A-F]{2}$/){print $i; break}}' \
    | while read -r MAC; do
        [[ -z "${MAC}" ]] && continue
        hcitool lp "${MAC}" RSWITCH >/dev/null 2>&1 \
            && log "link policy de ${MAC} -> RSWITCH (sem SNIFF)" || true
    done
fi

exit 0
