#!/usr/bin/env bash
# bt_bonds_autorestore.sh — BONDS-QUE-SOBREVIVEM-01: a VOLTA automática.
#
# Decisão dela, 08/08/2026: "restauro de bonds tem de ser automático — manual
# com sudo não é produto". E a regra irmã: toda cura entra no install, sem flag.
# O salva-vidas já GRAVAVA sozinho desde 21/07; a volta continuava sendo um
# comando que ela tinha de digitar com sudo, e por isso nunca acontecia.
#
# ---------------------------------------------------------------------------
# 1. O QUE APAGA OS BONDS — medido ao vivo em 15/08/2026, 06:29
# ---------------------------------------------------------------------------
# Não é hipótese, é relógio. Journal da máquina dela, na mesa dos quatro
# controles, com bluez 5.86 (o backport JÁ aplicado — ele não curou isto):
#
#   06:29:01  snapshot de bonds gravado ... (4 bond(s))
#   06:29:05  profiles/input/device.c:hidp_report_req_timeout() GET_REPORT timed out
#   06:29:41  snapshot de bonds gravado ... (1 bond(s))     <- 3 bonds em 40 s
#   06:29:46  bluetoothd: malloc_consolidate(): unaligned fastbin chunk detected
#   06:29:49  bluetooth.service: Main process exited, code=dumped, status=6/ABRT
#   06:29:50  bluetooth.service: Scheduled restart job, restart counter is at 1
#   06:29:56  snapshot de bonds gravado ... (2 bond(s))
#
# A corrupção de heap do `bluetoothd` APAGA os diretórios de device de
# /var/lib/bluetooth **segundos antes** de abortar. Quem some é o bond em
# disco; o SIGABRT é a mesma avaria, cinco segundos depois. O salva-vidas tinha
# a cópia boa (06:29:01, quatro bonds) e ninguém a usou: ela ficou com dois.
#
# ---------------------------------------------------------------------------
# 2. O GATILHO — ExecStopPost do bluetooth.service, e só na MORTE
# ---------------------------------------------------------------------------
# O `ExecStopPost` é o único instante em que tudo de que a restauração precisa
# já é verdade de graça:
#
#   - o `bluetoothd` JÁ morreu (o systemd só roda ExecStopPost depois que o
#     processo principal saiu), então o storage está parado. Não é preciso
#     `systemctl stop`, nem `mask --runtime`, nem derrubar o agente de
#     pareamento junto — que foi o defeito AGENTE-QUE-NAO-VOLTA-01 e custou
#     oito horas de Bluetooth em 14/08;
#   - o systemd vai reiniciar o daemon 1 s depois (Restart=on-failure +
#     RestartSec=1), e ele LÊ /var/lib/bluetooth no start: o que a gente
#     gravar aqui já vale na volta;
#   - roda como ROOT porque a unit roda como root. Nenhum sudo, nenhum polkit,
#     nenhum broker. O sandbox do bluez já dá as duas escritas de que
#     precisamos (StateDirectory=bluetooth e o ReadWritePaths do nosso drop-in).
#
# E o gatilho é a MORTE, nunca a parada: o systemd entrega `$SERVICE_RESULT` ao
# ExecStopPost, e só agimos quando ele NÃO é `success`. Um `systemctl stop`
# limpo — reboot, uninstall, o próprio bt_bonds_restore.sh — não restaura nada.
# É isso que impede que um `bluetoothctl remove` decidido por ela seja
# desfeito pelo produto no desligamento seguinte.
#
# Alternativas medidas e descartadas:
#   - `OnFailure=`: NÃO dispara. Com `Restart=on-failure` a unit vai para
#     `auto-restart`, nunca para `failed` — o journal de 06:29:50 diz
#     "Scheduled restart job", e `OnFailure` só corre em `failed`.
#   - udev na chegada do HID: tarde demais e no lugar errado — quando o
#     controle aparece, o bond de que ele precisava já faltou.
#   - `After=bluetooth.service`: rodaria com o daemon VIVO, e aí restaurar
#     exigiria pará-lo de novo — exatamente o ciclo que derrubou o agente.
#   - watchdog de 2 min: fica como rede de segurança possível, mas dois
#     minutos é depois de ela já ter tentado conectar e falhado.
#
# ---------------------------------------------------------------------------
# 3. POR QUE AGORA PODE SER AUTOMÁTICO (e antes não podia)
# ---------------------------------------------------------------------------
# O cabeçalho do bt_bonds_restore.sh guardava o motivo de a volta ser manual:
# se o CONTROLE rotacionou a própria chave, restaurar cegamente a LinkKey
# antiga produz chave que o peer rejeita -> loop de falha de autenticação, que
# é a classe de gatilho do próprio crash. O risco é real. O que ele não é, é
# inevitável — ele vem de restaurar POR CIMA. Aqui a restauração é ADITIVA:
#
#   - device que AINDA TEM `info` com `[LinkKey]` em disco NUNCA é tocado. A
#     chave viva é sempre a mais nova; quem rotacionou está protegido por
#     construção, porque nós não escrevemos onde há chave;
#   - só volta quem SUMIU (ou quem ficou com `info` sem chave nenhuma —
#     aí não há credencial a preservar, e sem ela o device é lixo mesmo);
#   - e há QUARENTENA, que é regra escrita da BONDS-QUE-SOBREVIVEM-01 (04/08,
#     E4): "restaurar o mesmo MAC duas vezes no mesmo boot é o começo do laço
#     que realimenta o crash — e é PROIBIDO". Um bond que sumiu DE NOVO depois
#     de já ter voltado neste boot não é vítima do crash: é chave velha, e
#     insistir é alimentar o loop de auth. Aí o journal diz o gesto que resolve.
#
# ---------------------------------------------------------------------------
# Uso:
#   bt_bonds_autorestore.sh [--quiet]   modo unit (exige $SERVICE_RESULT != success)
#   bt_bonds_autorestore.sh --force     ignora o gate (doctor/diagnóstico humano)
#   bt_bonds_autorestore.sh --dry-run   diz o que faria, não escreve nada
#   bt_bonds_autorestore.sh --status    mostra o histórico de restaurações
set -euo pipefail

# Overrides de TESTE. Em produção nada define isto: o script roda a partir do
# ExecStopPost, sem env nenhuma, e os defaults são os caminhos reais.
SRC_ROOT="${HEFESTO_BT_BONDS_SRC:-/var/lib/hefesto-dualsense4unix/bt-bonds}"
DST="${HEFESTO_BT_DST:-/var/lib/bluetooth}"
#: Snapshot mais velho que isto não é considerado. Bond que ela removeu de
#: propósito envelhece para fora da janela; bond comido por crash volta em
#: segundos, muito dentro dela.
MAX_IDADE_H="${HEFESTO_BT_AUTORESTORE_IDADE_H:-24}"
#: Quarentena da E4: quantas voltas o MESMO device pode ter no MESMO boot.
#: 1 = "voltou uma vez; se sumiu de novo, o problema não é o crash".
FREIO_MAX="${HEFESTO_BT_AUTORESTORE_FREIO_MAX:-1}"
AGORA="${HEFESTO_BT_AGORA:-$(date +%s)}"
#: O boot é o escopo da quarentena. `boot_id` é legível sem root e muda a cada
#: boot — é o carimbo mais barato que existe para "neste boot".
BOOT_ID="${HEFESTO_BT_BOOT_ID:-$(cat /proc/sys/kernel/random/boot_id 2>/dev/null || echo desconhecido)}"

LEDGER="${SRC_ROOT}/.autorestore-ledger"

#: MAC do BlueZ no nome de diretório: AA:BB:CC:DD:EE:FF.
_MAC_RE='^[0-9A-Fa-f]{2}(:[0-9A-Fa-f]{2}){5}$'

QUIET=0
FORCE=0
DRY=0
STATUS=0
for _arg in "$@"; do
    case "${_arg}" in
        --quiet)   QUIET=1 ;;
        --force)   FORCE=1 ;;
        --dry-run) DRY=1 ;;
        --status)  STATUS=1 ;;
        *) printf 'bt_bonds_autorestore.sh: argumento desconhecido: %s\n' "${_arg}" >&2; exit 2 ;;
    esac
done

log() {
    [[ "${QUIET}" -eq 1 ]] || printf '%s\n' "$*"
    logger -t hefesto-bt-autorestore "$*" 2>/dev/null || true
}

if [[ "${STATUS}" -eq 1 ]]; then
    if [[ -f "${LEDGER}" ]]; then
        cat "${LEDGER}"
    else
        printf 'nenhuma restauração automática registrada\n'
    fi
    exit 0
fi

# ---------------------------------------------------------------------------
# Gate 1 — só na MORTE do daemon.
# ---------------------------------------------------------------------------
# `$SERVICE_RESULT` é entregue pelo systemd ao ExecStop/ExecStopPost. Valores de
# falha: core-dump, signal, watchdog, timeout, exit-code, oom-kill, resources,
# protocol, start-limit-hit. `success` é a parada limpa; VAZIO é execução fora
# da unit (linha de comando), e aí também não restauramos nada — restaurar por
# engano é o único jeito de desfazer uma remoção que ela quis.
if [[ "${FORCE}" -eq 0 ]]; then
    case "${SERVICE_RESULT:-}" in
        success)
            log "parada limpa do bluetooth.service (SERVICE_RESULT=success) — nada a restaurar"
            exit 0
            ;;
        "")
            log "sem SERVICE_RESULT (execução fora da unit) — nada a restaurar; use --force para forçar"
            exit 0
            ;;
    esac
    log "bluetooth.service morreu (SERVICE_RESULT=${SERVICE_RESULT}${EXIT_STATUS:+/${EXIT_STATUS}}) — conferindo bonds"
fi

# ---------------------------------------------------------------------------
# Gate 2 — na árvore REAL, exige root e exige o daemon morto.
# ---------------------------------------------------------------------------
# Mesmo idioma do bt_bonds_snapshot.sh: a exigência é do CAMINHO, não do modo.
# Com as raízes de teste apontando para outro lugar, root não acrescenta nada —
# e exigi-lo tornaria a lógica de seleção não-testável.
if [[ "${DST}" == "/var/lib/bluetooth" ]]; then
    if [[ "$(id -u)" -ne 0 ]]; then
        printf 'bt_bonds_autorestore.sh: requer root\n' >&2
        exit 1
    fi
    # Escrever /var/lib/bluetooth por baixo de um bluetoothd VIVO é o caminho
    # para o storage inconsistente. No ExecStopPost ele já morreu; em qualquer
    # outro contexto, desistimos.
    #
    # O `--dry-run` passa por aqui de propósito: ele não escreve nada, e é
    # justamente com a máquina VIVA que a pergunta "o que voltaria agora?" tem
    # graça — é como se confere, sem parar nada, que o acervo ainda serve.
    if [[ "${DRY}" -eq 0 ]] \
       && command -v systemctl >/dev/null 2>&1 \
       && systemctl is-active --quiet bluetooth.service 2>/dev/null; then
        log "bluetooth.service ainda ATIVO — não escrevo no storage por baixo dele"
        exit 0
    fi
fi

[[ -d "${SRC_ROOT}" ]] || { log "sem acervo em ${SRC_ROOT} — nada a restaurar"; exit 0; }
[[ -d "${DST}" ]] || { log "sem ${DST} — nada a restaurar"; exit 0; }

# ---------------------------------------------------------------------------
# Validação de entrada (RADIO-ABERTO-01/E10, mesma régua do bt_bonds_restore.sh)
# ---------------------------------------------------------------------------
# `cp -a` preserva symlink em vez de segui-lo, e o bluetoothd escreve como
# ROOT através dele. Aqui a cópia já é por CONTEÚDO, arquivo a arquivo do
# conjunto esperado — mas a checagem fica explícita porque este caminho roda
# SOZINHO, sem humano olhando, que é justamente quando ninguém confere.
_arquivo_confiavel() {
    local caminho="$1" nlink
    [[ -L "${caminho}" ]] && return 1
    [[ -f "${caminho}" ]] || return 1
    nlink="$(stat -c '%h' "${caminho}" 2>/dev/null || echo 1)"
    [[ "${nlink}" -eq 1 ]] || return 1
    return 0
}

#: Um `info` só conta como BOND se traz credencial. Device meramente visto num
#: scan também tem `info`, e ressuscitá-lo não devolve pareamento nenhum.
_tem_chave() {
    grep -qE '^\[(LinkKey|LongTermKey|PeripheralLongTermKey)\]' "$1" 2>/dev/null
}

#: `YYYYmmdd-HHMMSS-PID` -> epoch. Nome, não mtime: o nome é o instante do
#: snapshot e não muda se alguém copiar o acervo.
_epoch_do_snapshot() {
    local n="$1"
    [[ "${n}" =~ ^([0-9]{8})-([0-9]{6}) ]] || return 1
    local d="${BASH_REMATCH[1]}" t="${BASH_REMATCH[2]}"
    date -d "${d:0:4}-${d:4:2}-${d:6:2} ${t:0:2}:${t:2:2}:${t:4:2}" +%s 2>/dev/null
}

#: Quantas vezes este device já foi restaurado NESTE boot (quarentena da E4).
_restauros_neste_boot() {
    local chave="$1" n=0 boot ts alvo
    [[ -f "${LEDGER}" ]] || { printf '0\n'; return 0; }
    while read -r boot ts alvo; do
        [[ "${ts}" =~ ^[0-9]+$ ]] || continue
        [[ "${boot}" == "${BOOT_ID}" ]] || continue
        [[ "${alvo}" == "${chave}" ]] || continue
        n=$((n + 1))
    done < "${LEDGER}"
    printf '%s\n' "${n}"
}

CORTE_IDADE=$((AGORA - MAX_IDADE_H * 3600))

# ---------------------------------------------------------------------------
# A varredura: do snapshot MAIS NOVO para o mais velho.
# ---------------------------------------------------------------------------
# ISTO É O CORAÇÃO, e é o que um `--latest` não faz. Em 06:29:41 o salva-vidas
# fotografou o estado DEGRADADO (1 bond) — o snapshot mais recente passou a ser
# o pior deles. Restaurar "o último" teria devolvido nada. O que serve é
# perguntar, device a device: qual foi a ÚLTIMA vez que eu vi este bond vivo?
# Por isso a varredura é por DEVICE, e o primeiro snapshot (mais novo) que
# contém aquele device com chave é o que ganha.
RESTAURADOS=0
SUSPENSOS=0
declare -A JA_VISTO=()

while IFS= read -r SNAP; do
    NOME="$(basename "${SNAP}")"
    [[ "${NOME}" == .* ]] && continue
    EPOCH="$(_epoch_do_snapshot "${NOME}" || true)"
    [[ -n "${EPOCH}" ]] || continue
    [[ "${EPOCH}" -ge "${CORTE_IDADE}" ]] || continue

    while IFS= read -r -d '' ADAPTER; do
        ABASE="$(basename "${ADAPTER}")"
        [[ "${ABASE}" =~ ${_MAC_RE} ]] || continue
        [[ -L "${ADAPTER}" ]] && continue

        while IFS= read -r -d '' DEVDIR; do
            DBASE="$(basename "${DEVDIR}")"
            [[ "${DBASE}" == "cache" ]] && continue
            [[ "${DBASE}" =~ ${_MAC_RE} ]] || continue
            [[ -L "${DEVDIR}" ]] && continue

            CHAVE="${ABASE}/${DBASE}"
            [[ -n "${JA_VISTO[${CHAVE}]:-}" ]] && continue

            SRC_INFO="${DEVDIR}/info"
            _arquivo_confiavel "${SRC_INFO}" || continue
            _tem_chave "${SRC_INFO}" || continue

            # ADITIVO: bond vivo com chave em disco é intocável. É esta linha
            # que torna a automação segura contra a chave rotacionada — a
            # credencial mais nova é sempre a que está lá, e nós nunca
            # escrevemos por cima dela.
            DST_INFO="${DST}/${CHAVE}/info"
            if [[ -f "${DST_INFO}" ]] && _tem_chave "${DST_INFO}"; then
                JA_VISTO["${CHAVE}"]=vivo
                continue
            fi

            JA_VISTO["${CHAVE}"]=tratado

            N_NESTE_BOOT="$(_restauros_neste_boot "${CHAVE}")"
            if [[ "${N_NESTE_BOOT}" -ge "${FREIO_MAX}" ]]; then
                log "QUARENTENA: ${DBASE} já voltou ${N_NESTE_BOOT}x neste boot e sumiu de novo — restauração SUSPENSA (chave provavelmente rotacionada pelo controle; insistir realimenta o laço de autenticação). O gesto que resolve: bluetoothctl remove ${DBASE} e parear outra vez"
                SUSPENSOS=$((SUSPENSOS + 1))
                continue
            fi

            if [[ "${DRY}" -eq 1 ]]; then
                log "DRY-RUN: restauraria ${CHAVE} de ${NOME}"
                RESTAURADOS=$((RESTAURADOS + 1))
                continue
            fi

            install -d -m 700 "${DST}/${ABASE}" 2>/dev/null || true
            install -d -m 700 "${DST}/${CHAVE}" 2>/dev/null || {
                log "não consegui criar ${DST}/${CHAVE} — pulando"
                continue
            }
            install -m 600 "${SRC_INFO}" "${DST_INFO}"
            SRC_ATTR="${DEVDIR}/attributes"
            if _arquivo_confiavel "${SRC_ATTR}"; then
                install -m 600 "${SRC_ATTR}" "${DST}/${CHAVE}/attributes"
            fi
            # cache/<MAC> (SDP-CACHE-01): sem o [ServiceRecords] o perfil HID
            # nunca sobe e o controle vira zumbi (ACL vivo, zero hidraw). Só
            # entra se o destino não tiver nada — nunca sobrescrever registro
            # bom com um envenenado.
            SRC_CACHE="${ADAPTER}/cache/${DBASE}"
            DST_CACHE="${DST}/${ABASE}/cache/${DBASE}"
            if [[ ! -e "${DST_CACHE}" ]] && _arquivo_confiavel "${SRC_CACHE}" \
               && grep -q '^\[ServiceRecords\]' "${SRC_CACHE}" 2>/dev/null; then
                install -d -m 700 "${DST}/${ABASE}/cache" 2>/dev/null || true
                install -m 600 "${SRC_CACHE}" "${DST_CACHE}" 2>/dev/null || true
            fi

            printf '%s %s %s\n' "${BOOT_ID}" "${AGORA}" "${CHAVE}" >> "${LEDGER}"
            chmod 600 "${LEDGER}" 2>/dev/null || true
            RESTAURADOS=$((RESTAURADOS + 1))
            log "bond de ${DBASE} restaurado do snapshot ${NOME} (sumiu do disco; nenhuma chave viva foi sobrescrita)"
        done < <(find "${ADAPTER}" -mindepth 1 -maxdepth 1 -type d -print0 2>/dev/null)
    done < <(find "${SNAP}" -mindepth 1 -maxdepth 1 -type d -print0 2>/dev/null)
done < <(find "${SRC_ROOT}" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sort -r)

if [[ "${RESTAURADOS}" -eq 0 && "${SUSPENSOS}" -eq 0 ]]; then
    log "nenhum bond faltando — nada a restaurar"
else
    log "restauração automática: ${RESTAURADOS} bond(s) de volta, ${SUSPENSOS} suspenso(s) pelo freio"
fi
exit 0
