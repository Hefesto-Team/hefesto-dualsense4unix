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

# Raízes parametrizadas p/ teste (mesmo idioma de doctor.sh:_hidraw_uniqs).
# Em produção NADA define estas variáveis.
BT_STORAGE="${HEFESTO_BT_SRC:-/var/lib/bluetooth}"
HIDRAW_ROOT="${HEFESTO_HIDRAW_ROOT:-/sys/class/hidraw}"
_uniqs_hidraw() {
    local f u
    for f in "${HIDRAW_ROOT}"/*/device/uevent; do
        [[ -r "${f}" ]] || continue
        u="$(grep -m1 '^HID_UNIQ=' "${f}" 2>/dev/null | cut -d= -f2)"
        [[ -n "${u}" ]] && printf '%s\n' "${u,,}"
    done
}

if [[ "$(id -u)" -ne 0 ]] && [[ "${BT_STORAGE}" == "/var/lib/bluetooth" ]]; then
    printf 'bt_health_watchdog.sh: requer root\n' >&2
    exit 1
fi
STAMP_DIR="${HEFESTO_BT_STAMP_DIR:-${STAMP_DIR}}"
install -d -m 700 "${STAMP_DIR}"

# --- vigia 3: controle ZUMBI por SDP não-resolvido (SDP-CACHE-01, 23/07) ------
# Assinatura medida ao vivo 23/07 20h15 no DualSense roxo: bond íntegro, ACL
# AUTH+ENCRYPT vivo, Connected=true no BlueZ e na GUI do COSMIC — e ZERO
# hidraw, zero uhid, zero input. O bluetoothd repetia
#   profiles/input/device.c:hidp_add_connection() Could not parse HID SDP record
# porque cache/<MAC> tinha 46 bytes (só [General] Name=), sem [ServiceRecords]
# — enquanto os 3 controles sãos tinham 1124..1433 bytes COM a seção.
#
# MECANISMO, lido no fonte do 5.86 que o projeto empacota (src/device.c:4415):
# ao carregar o device, o BlueZ olha o cache e, sem o grupo [ServiceRecords],
# marca bredr_state.svc_resolved=false. E device_connect_profiles() faz
# `if (!state->svc_resolved) goto resolve_services` → device_browse_sdp().
# Ou seja: do lado do HOST o BlueZ SABE se recuperar — o cache podre NÃO é um
# estado auto-sustentável (hipótese levantada e REFUTADA no fonte em 23/07).
#
# O que sobra são DUAS causas distintas, e elas pedem respostas diferentes:
#
#   (a) DIREÇÃO da conexão. Controle reconecta sempre ENTRANTE (botão PS/SYNC),
#       e no caminho entrante o perfil input só consulta o registro em cache
#       (extract_hid_record → idev->rec == NULL → -ENOENT); nada ali dispara
#       browse. O browse só acontece quando o HOST inicia. Curável daqui:
#       com o ACL de pé, chamar org.bluez.Device1.Connect() força o browse,
#       grava o [ServiceRecords] e o HID sobe. A LinkKey nunca é tocada.
#
#   (b) DISPOSITIVO travado. Medido no DualSense roxo em 23/07 20h50: ACL
#       AUTH+ENCRYPT de pé, e `sdptool browse` estoura 35 s com ZERO linhas
#       (o controle são responde em <1 s); Connect() volta
#       "Connection refused (111)" no PSM de controle HID. O controle aceita o
#       link e não responde mais nada acima dele. Daqui NÃO há cura por
#       software — a saída é o reset de hardware do próprio controle (furinho
#       atrás, procedimento do fabricante). Este caso também explica como o
#       cache fica com 46 bytes: o BlueZ obtém o nome e grava o arquivo, mas o
#       browse não devolve serviço nenhum. O cache truncado é SINTOMA, não causa.
#
# Esta vigia tenta (a) e, se não resolver, LOGA o caso (b) com honestidade em
# vez de insistir — o doctor mostra e a humana decide.
#
#  NÃO apagar o cache aqui: o arquivo é reescrito pelo browse bem-sucedido, e
# apagá-lo depois destrói justamente o registro recém-obtido (erro cometido e
# medido na sessão de 23/07).  NÃO desconectar: o DualSense dorme ao perder o
# link e só o PS o acorda — derrubar transforma uma cura automática em
# intervenção manual.
vigia_sdp_cache() {
    local UNIQS PATHS INFO DEVDIR MAC ADPDIR CACHE OBJ TENTATIVA
    UNIQS="$(_uniqs_hidraw)"
    # WATCHDOG-HCI-HARDCODE-01 (23/07): o path D-Bus tem de sair da árvore REAL.
    # Concatenar 'hci0' fazia a vigia virar no-op MUDO num adaptador hci1 — e
    # hci1 acontece nesta máquina (journal de 23/07 09:22: "Bluetooth: hci1:
    # Resetting usb device"). Uma consulta só, fora do laço.
    PATHS="$(_dbus_device_paths)"
    while IFS= read -r INFO; do
        [[ -z "${INFO}" ]] && continue
        DEVDIR="$(dirname "${INFO}")"
        MAC="$(basename "${DEVDIR}")"
        ADPDIR="$(dirname "${DEVDIR}")"
        CACHE="${ADPDIR}/cache/${MAC}"

        # Só device de perfil HID (controle) — 0x1124 = HumanInterfaceDevice.
        grep -qi '^Services=.*00001124-0000-1000-8000-00805f9b34fb' "${INFO}" 2>/dev/null || continue

        OBJ="$(grep -im1 "/dev_${MAC//:/_}\$" <<<"${PATHS}" || true)"
        if [[ -z "${OBJ}" ]]; then
            # Bond em disco sem objeto no BlueZ: adaptador ausente/trocado ou
            # device ainda não carregado. Não é falha, mas não pode sumir do radar.
            log "device ${MAC} tem bond em disco mas nenhum objeto D-Bus (adaptador ausente?) — pulando nesta rodada"
            continue
        fi
        # Zumbi = conectado E sem hidraw com o HID_UNIQ dele. Sem ACL não há o
        # que curar (o browse precisa do link vivo) — fica pro próximo tick.
        [[ "$(_dbus_device_prop "${OBJ}" Connected)" == "true" ]] || continue
        grep -qix "${MAC,,}" <<<"${UNIQS}" && continue
        # Cache com [ServiceRecords] + sem hidraw é OUTRA doença (bond, driver,
        # uhid) — as vigias 1/2 e o doctor cuidam; aqui seria falso-positivo.
        grep -q '^\[ServiceRecords\]' "${CACHE}" 2>/dev/null && continue

        log "controle ${MAC} ZUMBI (conectado, SDP não-resolvido, zero hidraw) — forçando SDP browse via Connect()"
        for TENTATIVA in 1 2 3 4 5 6; do
            # br-connection-busy é esperado enquanto a conexão entrante ainda
            # está em curso; insistir é o certo (medido: sucesso na 3ª/12ª).
            busctl call org.bluez "${OBJ}" org.bluez.Device1 Connect >/dev/null 2>&1 || true
            sleep 2
            if grep -q '^\[ServiceRecords\]' "${CACHE}" 2>/dev/null; then
                log "SDP de ${MAC} resolvido na tentativa ${TENTATIVA} — [ServiceRecords] gravado; o HID sobe sozinho"
                break
            fi
            [[ "$(_dbus_device_prop "${OBJ}" Connected)" == "true" ]] || {
                log "ACL de ${MAC} caiu durante o browse — retomo no próximo tick (ou aperte PS)"
                break
            }
        done
        # Caso (b): o device não responde SDP. Distinguir de (a) é barato e evita
        # mandar a humana re-parear um controle que vai recusar do mesmo jeito.
        if ! grep -q '^\[ServiceRecords\]' "${CACHE}" 2>/dev/null; then
            if command -v sdptool >/dev/null 2>&1 \
               && ! timeout 20 sdptool browse "${MAC}" >/dev/null 2>&1; then
                log "controle ${MAC} NÃO responde SDP (browse direto estoura) — o link sobe mas o stack do controle está travado; re-parear NÃO resolve. Cura: reset de hardware do controle (furinho atrás, ~5 s com um clipe) e ligar de novo"
            else
                log "SDP de ${MAC} não resolveu em 6 tentativas mas o device responde ao browse direto — o doctor aponta; último recurso é bluetoothctl remove ${MAC} + re-parear"
            fi
        fi
    done < <(find "${BT_STORAGE}" -mindepth 3 -maxdepth 3 -type f -name info 2>/dev/null | sort)
}

# --sdp-cache-only: roda SÓ a vigia 3. Existe para o teste exercitar a decisão
# de apagar/preservar cache sem disparar as vigias que mexem no serviço.
if [[ "${1:-}" == "--sdp-cache-only" ]]; then
    vigia_sdp_cache
    exit 0
fi

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


vigia_sdp_cache
exit 0
