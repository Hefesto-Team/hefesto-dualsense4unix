#!/usr/bin/env bash
# bt_health_watchdog.sh — vigia o estado "vivo mas doente" do bluetoothd e a
# persistência dos bonds (sprint 2026-07-21-sprint-pesquisa-bluez-estabilidade.md,
# camada 2). Roda pelo hefesto-bt-health-watchdog.timer (a cada 2 min), root.
#
# Vigias independentes (as duas primeiras dão nome ao script; as demais
# entraram depois e estão documentadas no corpo, cada uma com sua medição):
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
#
# 4. CONTROLE ÓRFÃO por probe perdida (REBIND-PROBE-01, medido 25/07): com dois
#    controles subindo quase juntos, o segundo perde o canal de controle L2CAP,
#    o GET_REPORT expira no BlueZ (REPORT_REQ_TIMEOUT = 3 s), o uhid entrega
#    -EIO e a probe morre — device sem driver, sem hidraw, sem input, sem LED.
#    É transiente: um rebind no driver VANILLA ressuscita (provado ao vivo).
#    Delegado a scripts/bt_rebind_orphans.sh (escopo estreito + guarda contra
#    laço). Vale ouro no alvo de 4 controles por Bluetooth ao mesmo tempo.
#
# 5. ADAPTADOR TRAVADO EM LAÇO (O-DIARIO-DO-RADIO-01, a família 3): a cada tique
#    o watchdog pede à ponte privilegiada o `reiniciar-travado`, que só age se o
#    journal do KERNEL mostra o laço de «command tx timeout» num adaptador sem
#    ninguém conectado. Em 13/09 um Realtek passou 17 h assim. O freio mora na
#    ponte: um reinício por porta a cada 15 min, e PARA depois de três seguidos
#    sem cura (GOVERNADOR-DO-RADIO-01) — daí em diante o sino diz «tire e
#    ponha», e o watchdog segue perguntando só para a ponte ver o laço sumir.
#
# A TRAVA E O DIÁRIO (O-DIARIO-DO-RADIO-01, 23/09/2026): um dos três motores do
# rádio (os outros: o vigia de zumbis e a central do daemon). O tique inteiro
# roda com a trava comum na mão (`flock` em /run/hefesto-dualsense4unix/radio.lock,
# com prazo); a espera, a desistência e as ações vão para o diário do root
# (/var/lib/hefesto-dualsense4unix/radio-diario.jsonl). Sob sudo os ganchos de
# teste morrem (menos o de LOG), como na ponte: o root abre a trava e o diário.
set -euo pipefail
if [[ -n "${SUDO_UID:-}" || -n "${SUDO_USER:-}" ]]; then
    unset HEFESTO_BT_SRC HEFESTO_BT_STAMP_DIR HEFESTO_HIDRAW_ROOT HEFESTO_RADIO_DIARIO_ROOT HEFESTO_RADIO_TRAVA HEFESTO_RADIO_TRAVA_PRAZO_S
fi
JANELA_MIN=10
LIMIAR_RECUSAS=8
# VIGIA-QUE-DERRUBA-01 (08/08/2026): quantos APARELHOS DISTINTOS precisam estar
# sendo recusados para que isso seja doença do daemon, e não de um aparelho.
# Dois é o menor número que separa as duas leituras: um aparelho martelando é o
# caso medido em 08/08 (nove recusas, um 8BitDo, e o restart custou os controles
# dela); a doença de 21/07, que esta vigia existe para pegar, atinge vários ao
# mesmo tempo porque o defeito é do daemon.
LIMIAR_APARELHOS=2
RATE_LIMIT_S=600
STAMP_RESTART=/run/hefesto-bt-watchdog.restart-stamp
STAMP_DIR=/run/hefesto-bt-watchdog
LOG_TAG=hefesto-bt-watchdog

# DIÁRIO-QUE-NAO-MENTE-01 (15/08/2026): vazio = journal (produção); caminho =
# arquivo; `none` = nada. Existe porque a suíte roda estes scripts DE VERDADE e
# sem isto grava, no journal da máquina dela, linhas que descrevem eventos que
# nunca aconteceram. Motivo completo no cabeçalho do bt_bonds_autorestore.sh.
LOG_DEST="${HEFESTO_BT_LOG_DEST:-}"
_registrar() {
    case "${LOG_DEST}" in
        "")   logger -t "${LOG_TAG}" "$*" 2>/dev/null || true ;;
        none) : ;;
        *)    printf '%s %s: %s\n' "$(date -Is 2>/dev/null || true)" "${LOG_TAG}" "$*" \
                  2>/dev/null >>"${LOG_DEST}" || true ;;
    esac
}
log() { _registrar "$*"; printf '%s\n' "$*"; }

# --- o diário do root (O-DIARIO-DO-RADIO-01) -------------------------------
#
# DUAS CÓPIAS, UMA FORMA: `_json_texto` e `_diario_escrever` existem byte a
# byte iguais aqui e no `bt_ponte_privilegiada.sh`, os dois escritores root do
# diário — sem `source`, porque script root que lê outro arquivo herda o risco
# de quem pode escrevê-lo. A régua `tests/unit/test_o_diario_do_radio.py`
# confere as duas cópias.
#: Texto -> string JSON. Barra e aspas escapadas; controle vira espaço.
_json_texto() {
    local s="${1:-}"
    s="${s//\\/\\\\}"
    s="${s//\"/\\\"}"
    s="$(printf '%s' "${s}" | tr '\000-\037' ' ')"
    printf '"%s"' "${s}"
}

#: Uma ação no diário do root. $1 destino (vazio = não registra) · $2 quem ·
#: $3 o quê · $4 por quê · $5 antes (JSON) · $6 depois (JSON) · $7 campos a
#: mais, já em JSON (`"porta": "3-4.1.4"`). Nunca falha: a ação já aconteceu.
_diario_escrever() {
    local alvo="${1:-}" linha tamanho
    [[ -n "${alvo}" ]] || return 0
    [[ -L "${alvo}" ]] && return 0
    linha="{\"quando\": $(_json_texto "$(date -Iseconds 2>/dev/null || true)"), \"carimbo\": $(date +%s), \"quem\": $(_json_texto "$2"), \"o_que\": $(_json_texto "$3"), \"por_que\": $(_json_texto "$4"), \"antes\": ${5:-null}, \"depois\": ${6:-null}${7:+, $7}}"
    install -d -m 0755 "${alvo%/*}" 2>/dev/null || true
    tamanho="$(stat -c %s "${alvo}" 2>/dev/null || echo 0)"
    if [[ "${tamanho}" -gt 524288 ]]; then
        mv -f -- "${alvo}" "${alvo}.1" 2>/dev/null || true
    fi
    printf '%s\n' "${linha}" >>"${alvo}" 2>/dev/null || true
    return 0
}

#: O diário do root, ou nenhum: com a árvore do BlueZ desviada (a suíte) e
#: sem o gancho, este script não escreve no disco dela.
DIARIO_DO_RADIO="${HEFESTO_RADIO_DIARIO_ROOT:-}"
if [[ -z "${DIARIO_DO_RADIO}" && -z "${HEFESTO_BT_SRC:-}" ]]; then
    DIARIO_DO_RADIO="/var/lib/hefesto-dualsense4unix/radio-diario.jsonl"
fi
_diario() { _diario_escrever "${DIARIO_DO_RADIO}" "bt-watchdog" "$@"; }

# --- a trava do rádio ------------------------------------------------------
#: A mesma guarda do diário: com a árvore do BlueZ desviada (a suíte) e sem o
#: gancho, este script não segura a trava DELA — um teste que rodasse o tique
#: prenderia o watchdog e o daemon dela, e escreveria o próprio nome no arquivo.
TRAVA_DO_RADIO="${HEFESTO_RADIO_TRAVA:-}"
if [[ -z "${TRAVA_DO_RADIO}" && -z "${HEFESTO_BT_SRC:-}" ]]; then
    TRAVA_DO_RADIO="/run/hefesto-dualsense4unix/radio.lock"
fi
PRAZO_DA_TRAVA_S="${HEFESTO_RADIO_TRAVA_PRAZO_S:-60}"
[[ "${PRAZO_DA_TRAVA_S}" =~ ^[0-9]+$ ]] || PRAZO_DA_TRAVA_S=60
TRAVA_FD=""

#: Pega a trava comum com prazo. 0 = com ela (ou sem trava comum nesta
#: máquina, dito no log); 1 = outro motor a segurou o prazo inteiro.
#:
#: ROOT NUM ARQUIVO QUE ELA TAMBÉM ABRE. O arquivo da trava tem o grupo dela
#: (o daemon escreve nele quem está com a trava), então este script nunca o
#: reabre pelo nome depois de aberto: o dono é escrito PELO DESCRITOR, e um
#: link simbólico no lugar do arquivo é recusado antes do `open`. O diretório
#: é do root e não é gravável por ela (ver o que o install precisa, na sprint),
#: e é isso que fecha a corrida entre a conferência e o `open`.
_pegar_a_trava() {
    local dono inicio fim milis
    if [[ -z "${TRAVA_DO_RADIO}" ]]; then
        log "árvore do BlueZ desviada e sem HEFESTO_RADIO_TRAVA: sigo sem a trava (a comum é a da máquina)"
        return 0
    fi
    if [[ ! -d "${TRAVA_DO_RADIO%/*}" ]]; then
        log "sem a trava comum do rádio (${TRAVA_DO_RADIO%/*} não existe — é o install que a cria); sigo sem ela"
        return 0
    fi
    if [[ -L "${TRAVA_DO_RADIO}" ]]; then
        log "recusando a trava do rádio: ${TRAVA_DO_RADIO} é link simbólico; sigo sem ela"
        return 0
    fi
    if ! exec {TRAVA_FD}<>"${TRAVA_DO_RADIO}"; then
        log "não consegui abrir a trava do rádio (${TRAVA_DO_RADIO}); sigo sem ela"
        TRAVA_FD=""
        return 0
    fi
    if ! flock -n "${TRAVA_FD}"; then
        dono="$(head -n1 -- "${TRAVA_DO_RADIO}" 2>/dev/null | cut -c1-120 || true)"
        inicio="$(date +%s%N)"
        if ! flock -w "${PRAZO_DA_TRAVA_S}" "${TRAVA_FD}"; then
            _diario "desistiu da trava" "${dono:-outro motor} segurou a trava por mais de ${PRAZO_DA_TRAVA_S} s" \
                "{\"dono\": $(_json_texto "${dono}")}" "{\"espera_s\": ${PRAZO_DA_TRAVA_S}}"
            log "a trava do rádio ficou com ${dono:-outro motor} por ${PRAZO_DA_TRAVA_S} s — pulo este tique"
            return 1
        fi
        fim="$(date +%s%N)"
        milis=$(( (fim - inicio) / 1000000 ))
        _diario "esperou a trava" "${dono:-outro motor} estava com ela" \
            "{\"dono\": $(_json_texto "${dono}")}" \
            "{\"espera_s\": $(printf '%d.%03d' $((milis / 1000)) $((milis % 1000)))}"
    fi
    #: Pelo descritor, na posição 0, sem truncar: quem lê fica com a primeira
    #: linha, que é esta.
    printf 'bt-watchdog %s\n' "$$" 1>&"${TRAVA_FD}" 2>/dev/null || true
    return 0
}

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
        _diario "forçou o SDP por Connect()" "conectado, sem registro SDP e sem hidraw" \
            "{\"sdp\": false}" null "\"controle\": $(_json_texto "${MAC}")"
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
            # SEM SUCESSOR VIVO (MIGRACAO-BLUEZ-DEPRECIADOS-01, 19/08/2026): o
            # browse SDP sob demanda num device só existe no `sdptool`, que o
            # BlueZ depreciou; `bluetoothctl` lê UUIDs do CACHE (o mesmo que
            # acabou de falhar) e `btmgmt find-service` é varredura por UUID no
            # ar, não pergunta a um device já conectado — conferido nos dois
            # `--help` do 5.86 em 19/08/2026.
            #
            # O ramo `else` daqui cobria DOIS casos com uma frase só: "o device
            # responde ao browse direto" era escrito também quando o `sdptool`
            # não existia — ou seja, sem ter perguntado nada. Numa distro que
            # moveu as depreciadas de pacote, a vigia afirmava saúde que não
            # mediu. Agora são três ramos, e o terceiro diz "não sei".
            if ! command -v sdptool >/dev/null 2>&1; then
                log "SDP de ${MAC} não resolveu em 6 tentativas e NÃO SEI dizer qual das duas causas é: o browse direto exigia o 'sdptool', depreciado pelo BlueZ e ausente nesta máquina (pacote bluez-deprecated / bluez-deprecated-tools), e nenhuma ferramenta viva o substitui. Instale-o para a vigia voltar a distinguir 'direção da conexão' de 'controle travado'. Enquanto isso: se o próximo tick também não resolver, trate como controle travado — reset de hardware do controle (furinho atrás, ~5 s com um clipe)"
            elif ! timeout 20 sdptool browse "${MAC}" >/dev/null 2>&1; then
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

# --so-a-trava <SEGUNDOS>: pega a trava como o tique pega, segura por
# <SEGUNDOS> e sai. Existe para a régua provar que este watchdog e o daemon
# disputam a MESMA trava, sem rodar vigia nenhuma.
if [[ "${1:-}" == "--so-a-trava" ]]; then
    _pegar_a_trava || exit 3
    sleep "${2:-0}"
    exit 0
fi

# O tique inteiro roda com a trava do rádio na mão. Sem ela no prazo, o tique
# é pulado: o próximo vem em dois minutos, e agir por cima de outro motor é o
# defeito que a trava existe para impedir.
_pegar_a_trava || exit 0

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
# VIGIA-QUE-DERRUBA-01 (08/08/2026): a contagem é de APARELHOS DISTINTOS, não de
# eventos. MEDIDO na máquina dela: às 00:56:26 a vigia registrou "estado doente
# confirmado (9 recusas/10min, 0 conectados)" e REINICIOU o `bluetooth.service`.
# As nove recusas eram de **um aparelho só** (o 8BitDo, `E4:17:…`), insistindo
# depois que o crash do bluetoothd às 00:27:35 levou os quatro bonds embora.
#
# Um aparelho insistindo nove vezes não é daemon doente. E a "cura" é pior que o
# sintoma, porque não tem relação com ele: **reiniciar o serviço não cria bond
# nenhum** — só derruba quem estava de pé, e o restart matou junto o
# `hefesto-bt-agent`, que é quem confirmaria o repareamento.
#
# A doença que esta vigia existe para pegar (medida em 21/07) é o daemon recusando
# device PRESENTE na lista — e essa se manifesta em VÁRIOS aparelhos ao mesmo
# tempo, porque o defeito é do daemon, não do aparelho. Contar aparelhos
# distintos separa as duas leituras sem inventar instrumento novo.
DEVICE_PATHS="$(_dbus_device_paths)"
RECUSAS=0
RECUSAS_ORFAS=0
MACS_RECUSADOS=""
while IFS= read -r MAC; do
    [[ -z "${MAC}" ]] && continue
    if grep -qi "dev_${MAC//:/_}$" <<<"${DEVICE_PATHS}"; then
        RECUSAS=$((RECUSAS + 1))
        MACS_RECUSADOS+="${MAC,,}"$'\n'
    else
        RECUSAS_ORFAS=$((RECUSAS_ORFAS + 1))
    fi
done < <(journalctl -u bluetooth --since "-${JANELA_MIN} min" --no-pager 2>/dev/null \
    | grep -E 'Refusing connection from .*: unknown device|error updating services' \
    | grep -oE '([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}' || true)
if [[ "${RECUSAS_ORFAS}" -gt 0 ]]; then
    log "${RECUSAS_ORFAS} recusa(s) de MAC sem objeto no BlueZ ignoradas (órfão re-tentando; daemon são)"
fi
APARELHOS_RECUSADOS=0
if [[ -n "${MACS_RECUSADOS}" ]]; then
    APARELHOS_RECUSADOS="$(printf '%s' "${MACS_RECUSADOS}" | sort -u | grep -c . || true)"
fi

CONECTADOS=0
while IFS= read -r OBJ; do
    [[ -z "${OBJ}" ]] && continue
    if [[ "$(_dbus_device_prop "${OBJ}" Connected)" == "true" ]]; then
        CONECTADOS=$((CONECTADOS + 1))
    fi
done <<<"${DEVICE_PATHS}"

if [[ "${RECUSAS}" -ge "${LIMIAR_RECUSAS}" ]]; then
    if [[ "${APARELHOS_RECUSADOS}" -lt "${LIMIAR_APARELHOS}" ]]; then
        # VIGIA-QUE-DERRUBA-01: um aparelho só, martelando. É problema DELE (bond
        # perdido, chave rotacionada, firmware confuso), e reiniciar o serviço não
        # resolve nenhum dos três — só derruba os outros. Vira AVISO, que é o que
        # o sintoma merece: alguém precisa saber, ninguém precisa ser derrubado.
        log "AVISO: ${RECUSAS} recusa(s)/${JANELA_MIN}min concentradas em ${APARELHOS_RECUSADOS} aparelho(s) — parece bond perdido do aparelho, não daemon doente; restart NÃO resolveria (ver VIGIA-QUE-DERRUBA-01)"
    elif [[ "${CONECTADOS}" -gt 0 ]]; then
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
            _diario "reiniciou o bluetooth.service" \
                "estado doente: ${RECUSAS} recusas de ${APARELHOS_RECUSADOS} aparelhos em ${JANELA_MIN} min, nenhum conectado" \
                "{\"recusas\": ${RECUSAS}, \"conectados\": 0}" null
            systemctl restart bluetooth.service || log "restart do bluetooth.service FALHOU"
        fi
    fi
fi

# --- vigia 2b: TRUST em device com bond, CONECTADO OU NÃO --------------------
# WATCHDOG-TRUST-DEADLOCK-01 (23/07, medido ao vivo): esta vigia estava DENTRO
# do laço da vigia 2, atrás do gate `Connected == true`. Isso a tornava
# inalcançável exatamente para quem mais precisa dela — um deadlock:
#
#   device sem trust  ->  BlueZ RECUSA a reconexão entrante
#                         ("Refusing connection from <MAC>: unknown device")
#   device recusado   ->  nunca fica Connected
#   nunca Connected   ->  a vigia 2b nunca o alcança  ->  segue sem trust
#
# Medido em 23/07 22h58: 8BitDo e Pro Nintendo com Bonded=true e Trusted=false,
# ambos desconectados, o log martelando "unknown device" a cada toque no botão
# de sync. A mantenedora descreveu como "a conexão automática voltou e assim ele
# nunca conecta". Nenhum tick do watchdog resolvia, por construção.
#
# Trust é idempotente, não mexe no link e não depende de conexão — então roda
# no seu próprio laço, sobre TODO device com bond. É o pré-requisito para o
# controle conseguir voltar sozinho.
while IFS= read -r OBJ; do
    [[ -z "${OBJ}" ]] && continue
    # Só device com bond de verdade: dar trust a um device meramente visto num
    # scan seria autorizar quem nunca foi pareado.
    [[ "$(_dbus_device_prop "${OBJ}" Bonded)" == "true" ]] || continue
    [[ "$(_dbus_device_prop "${OBJ}" Trusted)" == "false" ]] || continue
    MAC_TRUST="${OBJ##*dev_}"
    MAC_TRUST="${MAC_TRUST//_/:}"
    if busctl set-property org.bluez "${OBJ}" org.bluez.Device1 Trusted b true 2>/dev/null; then
        log "device ${MAC_TRUST} tinha bond mas estava SEM trust (reconexão entrante recusada como 'unknown device') — Trusted=true aplicado"
        _diario "aplicou Trusted=true" "bond sem trust: a reconexão entrante era recusada" \
            "{\"trusted\": false}" "{\"trusted\": true}" \
            "\"controle\": $(_json_texto "${MAC_TRUST}"), \"hci\": $(_json_texto "$(cut -d/ -f4 <<<"${OBJ}")")"
    else
        log "falha ao aplicar Trusted=true em ${MAC_TRUST} — o doctor vai apontar"
    fi
done <<<"${DEVICE_PATHS}"

# --- vigia 2: bond temporário (Paired sem Bonded em device conectado) --------
# Fonte da lista: D-Bus (WATCHDOG-FP-01). A lista via bluetoothctl vinha VAZIA
# no 5.86 e as vigias 2/2b passavam sem olhar device nenhum (medido 22/07:
# 4 controles conectados, todos Trusted=false, vigia 2b inerte a sessão toda).
#
# Esta vigia (promoção de bond temporário) SEGUE exigindo `Connected` — ao
# contrário do trust, promover bond precisa do link vivo (o Pair() explícito
# corre sobre a conexão).
while IFS= read -r OBJ; do
    [[ -z "${OBJ}" ]] && continue
    [[ "$(_dbus_device_prop "${OBJ}" Connected)" == "true" ]] || continue
    MAC_U="${OBJ##*dev_}"
    MAC="${MAC_U//_/:}"
    PAIRED="$(_dbus_device_prop "${OBJ}" Paired)"
    BONDED="$(_dbus_device_prop "${OBJ}" Bonded)"
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
        _diario "promoveu o bond temporário" "conectado com Paired e sem Bonded: o bond evaporaria no desligar" \
            "{\"bonded\": false}" "{\"bonded\": $([[ "${BONDED2}" == "true" ]] && echo true || echo false)}" \
            "\"controle\": $(_json_texto "${MAC}")"
        if [[ "${BONDED2}" == "true" ]]; then
            log "bond de ${MAC} promovido e persistido (Bonded=true)"
            /usr/local/lib/hefesto-dualsense4unix/bt_bonds_snapshot.sh --quiet 2>/dev/null || true
        else
            log "promoção de ${MAC} NÃO persistiu (Bonded=${BONDED2:-?}) — o doctor vai apontar; cura manual: bluetoothctl remove ${MAC} e re-parear em modo pareamento"
        fi
    fi
done <<<"${DEVICE_PATHS}"


vigia_sdp_cache

# --- vigia 4: controle ÓRFÃO por probe perdida (REBIND-PROBE-01, 25/07) ------
# Quando dois controles sobem quase juntos no mesmo adaptador, o segundo pode
# perder o canal de controle L2CAP: o GET_REPORT expira no BlueZ
# (REPORT_REQ_TIMEOUT = 3 s), o uhid entrega -EIO ao driver e a probe morre. O
# device fica em /sys/bus/hid/devices SEM driver — sem hidraw, sem input, sem
# LED. É contenção TRANSIENTE: passada a janela, um rebind no driver VANILLA
# ressuscita o controle (provado ao vivo 25/07 12:06). Com o alvo de 4
# controles por Bluetooth, isso deixa de ser exceção.
# A lógica (escopo estreito + guarda contra laço) fica toda no script
# dedicado; aqui só chamamos. --quiet: em passagem normal não há órfão e o
# watchdog não deve virar ruído de 2 em 2 min.
vigia_rebind_orfaos() {
    local _s
    for _s in \
        /usr/local/lib/hefesto-dualsense4unix/bt_rebind_orphans.sh \
        "$(dirname "$(readlink -f "$0")")/bt_rebind_orphans.sh" \
    ; do
        if [[ -x "${_s}" ]]; then
            "${_s}" --quiet || true
            return 0
        fi
    done
    return 0
}

vigia_rebind_orfaos

# --- vigia 5: adaptador travado em laço (O-DIARIO-DO-RADIO-01) ---------------
# Quem decide é a ponte (o journal do kernel, a porta, ninguém conectado, o
# freio de 15 min e o que PARA depois de três reinícios sem cura) — aqui só se
# chama, com a trava já na mão, e a cada tique: é o tique que deixa a ponte ver
# o laço sumir e soltar o freio. A árvore de teste não chama: o verbo leria o
# journal DELA.
vigia_adaptador_travado() {
    local _s
    [[ -z "${HEFESTO_BT_SRC:-}" ]] || return 0
    for _s in \
        /usr/local/lib/hefesto-dualsense4unix/bt_ponte_privilegiada.sh \
        "$(dirname "$(readlink -f "$0")")/bt_ponte_privilegiada.sh" \
    ; do
        if [[ -x "${_s}" ]]; then
            "${_s}" reiniciar-travado >/dev/null 2>&1 || true
            return 0
        fi
    done
    return 0
}

vigia_adaptador_travado
exit 0
