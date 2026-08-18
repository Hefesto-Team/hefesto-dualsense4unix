#!/usr/bin/env bash
# bt_rebind_orphans.sh — recupera o controle Bluetooth que PERDEU A PROBE e
# ficou órfão (device HID existente, driver NENHUM). Cura de PRIMEIRA LINHA da
# contenção de probe: um rebind no driver VANILLA in-tree, sem patch de kernel,
# sem reboot e sem tocar em quem já está funcionando.
#
# ─── O sintoma (medido 25/07) ────────────────────────────────────────────────
# Dois DualSense conectando no mesmo adaptador com ~1 s de diferença. O 1º
# concluiu a probe em 74 ms. O 2º pegou o pairing info (reportID 9) e perdeu o
# firmware info (reportID 32):
#
#   playstation 0005:054C:0CE6.000F: Failed to retrieve feature with reportID 32: -5
#   playstation 0005:054C:0CE6.000F: probe with driver playstation failed with error -5
#
# O device fica em /sys/bus/hid/devices SEM symlink `driver`: sem hidraw, sem
# input, sem LED, sem bateria. O hid-generic NÃO assume, porque um driver
# específico deu match. É por isso que o sintoma é detectável com precisão
# cirúrgica — e é exatamente o que este script procura.
#
# ─── Por que o rebind CURA (medido 25/07 12:06) ──────────────────────────────
# O -5 é máscara. A cadeia real: o uhid achata qualquer erro do transporte em
# -EIO; o kernel ainda esperava (a espera dele é de 5 s) mas o BlueZ desistiu
# antes, no seu REPORT_REQ_TIMEOUT de 3 s, e registrou
# "hidp_report_req_timeout() ... GET_REPORT request timed out". Ou seja: o
# controle estava VIVO — tinha acabado de responder o feature report anterior —
# e só não ganhou o canal de controle L2CAP dentro de 3 s enquanto o outro pad
# subia no mesmo rádio. Contenção TRANSIENTE.
#
# Passada a janela, o MESMO GET_REPORT passa. Provado ao vivo com o driver
# vanilla, sem retry nenhum no probe:
#
#   echo "0005:054C:0CE6.000F" > /sys/bus/hid/drivers/playstation/bind
#   -> playstation 0005:054C:0CE6.000F: Registered DualSense controller
#      hw_version=0x00000710 fw_version=0x0110002a
#
# O controle subiu de primeira e o daemon criou o vpad em seguida. Isso PROVA
# que o device continua plenamente utilizável: a falha é só na JANELA DE PROBE,
# não no controle nem no link.
#
# Importa para o alvo do projeto (4 controles por Bluetooth ao mesmo tempo):
# com 4 pads subindo no mesmo rádio a contenção deixa de ser exceção, e uma
# cura automática em userspace vale mais que uma que exige reboot.
#
# ─── Escopo deliberadamente ESTREITO ─────────────────────────────────────────
# Só age em device que satisfaz TODAS estas condições:
#   1. está em /sys/bus/hid/devices SEM symlink `driver` (o sintoma exato);
#   2. o barramento é 0005 = BLUETOOTH. É o único onde a contenção medida
#      acontece (o timeout é do canal de controle L2CAP do BlueZ), e é o que
#      exclui por construção o vpad do próprio hefesto, que nasce por uhid no
#      barramento 0003;
#   3. o vendor é 054C (Sony) — o dono é o driver `playstation`.
# Qualquer outro device órfão é IGNORADO e apenas contado no resumo: chutar
# bind em device alheio é como se inventa bug novo.
#
# ─── Guarda contra laço (disciplina da casa) ─────────────────────────────────
# Contador POR DEVICE em /run: depois de MAX_TENTATIVAS falhas seguidas o
# script PARA de tentar aquele device e loga UMA vez. O histórico do projeto
# tem laço de 1 Hz que encheu o log por 45 min — aqui não se repete. Como o id
# do device muda a cada reconexão (0009 -> 000F), reconectar dá orçamento novo
# de graça, que é o comportamento certo: o humano replugou, tenta de novo.
#
# NUNCA carrega/descarrega módulo: recarregar hid_playstation derrubaria TODOS
# os DualSense, inclusive os por Bluetooth.
#
# Uso:
#   bt_rebind_orphans.sh              cura (requer root p/ escrever no sysfs)
#   bt_rebind_orphans.sh --dry-run    só relata o que faria (não requer root)
#   bt_rebind_orphans.sh --quiet      só fala quando age ou falha
set -euo pipefail

# Raízes parametrizáveis (defaults == sistema real). Existem como COSTURA DE
# TESTE: a suíte exercita órfão-no-escopo, órfão-fora-do-escopo e o teto de
# tentativas sem root e sem hardware, apontando tudo para diretórios temporários.
# Em produção NUNCA são definidas — os defaults valem.
MAX_TENTATIVAS="${HEFESTO_REBIND_MAX_TENTATIVAS:-3}"
STAMP_DIR="${HEFESTO_REBIND_STAMP_DIR:-/run/hefesto-bt-rebind}"
LOG_TAG=hefesto-bt-rebind
HID_DEVICES="${HEFESTO_HID_DEVICES_DIR:-/sys/bus/hid/devices}"
HID_DRIVERS="${HEFESTO_HID_DRIVERS_DIR:-/sys/bus/hid/drivers}"

DRY_RUN=0
QUIET=0
for arg in "$@"; do
    case "${arg}" in
        --dry-run) DRY_RUN=1 ;;
        --quiet)   QUIET=1 ;;
        -h|--help)
            sed -n '2,60p' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *)
            printf 'uso: %s [--dry-run] [--quiet]\n' "$(basename "$0")" >&2
            exit 2
            ;;
    esac
done

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

log() {
    _registrar "$*"
    printf '%s\n' "$*"
}
# Só aparece quando NÃO estamos em --quiet (ruído de rotina do watchdog).
log_info() { [[ "${QUIET}" -eq 1 ]] && return 0; log "$*"; }

# Identidade do device a partir do nome do diretório: BUS:VID:PID.INSTANCIA.
# Ex.: 0005:054C:0CE6.000F -> bus=0005 vid=054C pid=0CE6
_bus_de() { printf '%s' "${1%%:*}"; }
_vid_de() { local r="${1#*:}"; printf '%s' "${r%%:*}"; }

# O device é candidato à cura? (ver "Escopo deliberadamente ESTREITO" acima)
_e_candidato() {
    local id="$1" bus vid
    bus="$(_bus_de "${id}")"
    vid="$(_vid_de "${id}" | tr 'a-f' 'A-F')"
    [[ "${bus}" == "0005" ]] || return 1   # só Bluetooth
    [[ "${vid}" == "054C" ]] || return 1   # só Sony (dono = driver playstation)
    return 0
}

curados=0
falhados=0
ignorados=0
esgotados=0
orfaos=0

shopt -s nullglob
for dev in "${HID_DEVICES}"/*; do
    [[ -e "${dev}/driver" ]] && continue   # tem driver: nada a fazer
    id="$(basename "${dev}")"
    orfaos=$((orfaos + 1))

    if ! _e_candidato "${id}"; then
        # Órfão que não é nosso escopo: reporta, não toca. Chutar bind em
        # device alheio é como se inventa bug novo.
        log_info "device HID órfão FORA do escopo, ignorado: ${id} (só curamos Sony 054C no barramento 0005/Bluetooth)"
        ignorados=$((ignorados + 1))
        continue
    fi

    bind="${HID_DRIVERS}/playstation/bind"
    if [[ ! -w "${bind}" && "${DRY_RUN}" -eq 0 ]]; then
        if [[ ! -e "${bind}" ]]; then
            log "driver playstation ausente em ${HID_DRIVERS} — módulo não carregado; NÃO carregamos módulo aqui (derrubaria os DualSense em uso). ${id} segue órfão"
        else
            log "sem permissão de escrita em ${bind} (rode como root) — ${id} segue órfão"
        fi
        falhados=$((falhados + 1))
        continue
    fi

    # Guarda contra laço: contador por device, zerado naturalmente a cada
    # reconexão (o id muda). Depois do teto, loga UMA vez e desiste.
    stamp="${STAMP_DIR}/${id}"
    tentativas=0
    [[ -f "${stamp}" ]] && tentativas="$(cat "${stamp}" 2>/dev/null || printf '0')"
    [[ "${tentativas}" =~ ^[0-9]+$ ]] || tentativas=0

    if [[ "${tentativas}" -ge "${MAX_TENTATIVAS}" ]]; then
        if [[ ! -f "${stamp}.desisti" ]]; then
            [[ "${DRY_RUN}" -eq 0 ]] && : > "${stamp}.desisti" 2>/dev/null || true
            log "DESISTINDO de ${id} após ${MAX_TENTATIVAS} rebinds sem sucesso — não é a contenção transiente de probe (essa cura de primeira); provável controle travado ou link ruim. Cura manual: desligue o controle (PS 10 s), reconecte; se insistir, 'bluetoothctl remove <MAC>' e re-pareie"
        fi
        esgotados=$((esgotados + 1))
        continue
    fi

    if [[ "${DRY_RUN}" -eq 1 ]]; then
        log "[dry-run] faria: echo '${id}' > ${bind} (tentativa $((tentativas + 1))/${MAX_TENTATIVAS})"
        curados=$((curados + 1))
        continue
    fi

    mkdir -p "${STAMP_DIR}" 2>/dev/null || true
    printf '%s' "$((tentativas + 1))" > "${stamp}" 2>/dev/null || true

    # O write falha (ENODEV/EBUSY) se o driver não casar ou o device sumir —
    # guardado, porque o script roda com set -e.
    if printf '%s' "${id}" > "${bind}" 2>/dev/null && [[ -e "${dev}/driver" ]]; then
        log "controle órfão RECUPERADO por rebind: ${id} (perdeu a probe por contenção de canal de controle; o device estava íntegro)"
        rm -f "${stamp}" "${stamp}.desisti" 2>/dev/null || true
        curados=$((curados + 1))
    else
        log "rebind de ${id} NÃO pegou (tentativa $((tentativas + 1))/${MAX_TENTATIVAS}) — nova tentativa na próxima passagem do watchdog"
        falhados=$((falhados + 1))
    fi
done
shopt -u nullglob

# Limpeza dos contadores de devices que não existem mais (reconexão troca o id;
# sem isto o /run acumularia stamp morto até o reboot).
if [[ "${DRY_RUN}" -eq 0 && -d "${STAMP_DIR}" ]]; then
    shopt -s nullglob
    for stamp in "${STAMP_DIR}"/*; do
        alvo="$(basename "${stamp}")"
        alvo="${alvo%.desisti}"
        [[ -e "${HID_DEVICES}/${alvo}" ]] || rm -f "${stamp}" 2>/dev/null || true
    done
    shopt -u nullglob
fi

if [[ "${orfaos}" -eq 0 ]]; then
    log_info "nenhum device HID órfão — todos os controles têm driver"
else
    log_info "órfãos=${orfaos} curados=${curados} falhados=${falhados} esgotados=${esgotados} ignorados=${ignorados}"
fi
exit 0
