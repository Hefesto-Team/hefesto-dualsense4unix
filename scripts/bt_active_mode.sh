#!/usr/bin/env bash
# bt_active_mode.sh — deixa o rádio BR/EDR amigável aos controles da linhagem
# Nintendo (Switch Pro genuíno / 8BitDo modo Switch), curando na RAIZ a
# desconexão sob carga (BT-NINTENDO-ACTIVE-01, 22/07). Root. Idempotente.
# Reversível.
#
# DUAS medidas com ESCOPOS DIFERENTES (BT-SNIFF-PER-OUI-01, 23/07):
#   (1) o NOME é do adaptador  — vale para todos, e o A/B de 23/07 provou que
#       não atrapalha o clone;
#   (2) o NO-SNIFF é POR DISPOSITIVO — só o Pro genuíno. Aplicá-lo como default
#       do adaptador quebrava a probe do 8BitDo (regressão medida; §2).
#
# As duas entraram juntas em fb5e3ad e por isso ficaram acopladas até 23/07.
#
# Pesquisa original
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
#    RECUSAR LMP_sniff_req, forçando modo ativo. Provado ao vivo 22/07: os
#    DualSense seguem conectados normalmente sem sniff.
#     ESCOPO CORRIGIDO em 23/07 (BT-SNIFF-PER-OUI-01): era default do
#    ADAPTADOR e por isso atingia TODO mundo — inclusive o 8BitDo, cuja probe
#    morre sem sniff. Agora é aplicada SÓ por-conexão, no Pro genuíno. Detalhes
#    e o A/B que mediu isso estão na seção 2 do corpo.
#
# Reverter: `hciconfig hci0 lp rswitch,hold,sniff,park` (VÍRGULA — com
# espaços o hciconfig lê só o primeiro token e a reversão é no-op
# silencioso; medido 23/07) e Alias de volta ao
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

# --- 2) LINK POLICY sem SNIFF — POR DISPOSITIVO (BT-SNIFF-PER-OUI-01) --------
#
#  Esta medida É por-dispositivo. Aplicá-la como default do ADAPTADOR foi uma
# regressão medida (23/07) — ver o A/B abaixo.
#
# Os dois controles da linhagem Nintendo têm requisitos de firmware
# INCOMPATÍVEIS entre si, e nenhum ajuste global satisfaz os dois:
#
#                        | Pro genuíno (e0:f6:b5) | 8BitDo clone (e4:17:d8)
#   ---------------------|------------------------|------------------------
#   SNIFF permitido      | cai sob carga          | FUNCIONA
#   SNIFF recusado       | ESTÁVEL                | probe morre (-110)
#
# A/B de 23/07 (watchdog parado para não contaminar): com no-sniff global, o
# 8BitDo acumulou 4 probes falhadas e 0 sucessos, sempre em
# `Failed to get joycon info; ret=-110` — o LM local recusa `LMP_sniff_req`, e
# o firmware clone trata a recusa como erro e não completa o handshake de
# subcomando. Devolvido o SNIFF ao adaptador, ele probou em 54 s na primeira
# tentativa e ficou de pé. No mesmo teste o alias "Nintendo" seguiu aplicado —
# ou seja, o NOME não atrapalha o clone; só o no-sniff atrapalha. As duas
# medidas do BT-NINTENDO-ACTIVE-01, que entraram juntas em fb5e3ad e nunca
# tinham sido separadas, ficam separadas aqui.
#
# Por que aplicar DEPOIS do connect basta para o Pro: ele proba bem com sniff
# (era o comportamento antes do fb5e3ad); o que ele não aguenta é a operação
# SUSTENTADA sob carga. O 8BitDo, ao contrário, precisa do sniff justamente na
# janela da probe. O default do adaptador fica então COM sniff (o que o clone
# precisa) e o Pro recebe o tratamento no handle dele, já conectado.
#
# "Só o nome" NÃO é alternativa: medido em 22/07 — com o alias sozinho o Pro
# durou muito mais, "mas sob carga pesada ele ainda caiu. Não é cura completa
# sozinho" (docs/process/estudos/2026-07-22-pesquisa-pro-controller-bt-*).

#: OUI (maiúsculas, com ':') do Nintendo Pro Controller GENUÍNO — o ÚNICO que
#: recebe o no-sniff. Mesma fonte da verdade do `NINTENDO_REAL_OUI` do
#: external_identity.py: a OUI, nunca VID/PID (o clone se anuncia como
#: 057E:2009 igualzinho).
OUI_NINTENDO_REAL="E0:F6:B5"

# Default do adaptador: SNIFF PERMITIDO. Se uma versão anterior deixou o
# adaptador sem SNIFF, isto o devolve — é o que destrava o clone.
# ATENÇÃO: a lista vai separada por VÍRGULA; com espaços o hciconfig lê só o
# primeiro token e o comando vira no-op silencioso (medido 23/07).
if ! hciconfig "${HCI}" lp 2>/dev/null | grep -q 'SNIFF'; then
    hciconfig "${HCI}" lp rswitch,hold,sniff,park 2>/dev/null \
        && log "link policy default de ${HCI} -> RSWITCH,HOLD,SNIFF,PARK (o clone 8BitDo precisa do SNIFF para probar)" \
        || log "falha ao devolver o SNIFF ao default (adaptador não pronto?)"
fi

# Por-conexão: no-sniff SÓ no Pro genuíno. Reaplicado a cada tick da vigia 0
# (2 min), o que cobre reconexão sem precisar caçar a borda.
if command -v hcitool >/dev/null 2>&1; then
    hcitool con 2>/dev/null | awk '/[0-9A-F:]{17}/{for(i=1;i<=NF;i++) if($i ~ /^([0-9A-F]{2}:){5}[0-9A-F]{2}$/){print $i; break}}' \
    | while read -r MAC; do
        [[ -z "${MAC}" ]] && continue
        if [[ "${MAC^^}" != "${OUI_NINTENDO_REAL}"* ]]; then
            continue
        fi
        hcitool lp "${MAC}" RSWITCH >/dev/null 2>&1 \
            && log "link policy de ${MAC} -> RSWITCH (sem SNIFF; Pro genuíno)" || true
    done
fi

exit 0
