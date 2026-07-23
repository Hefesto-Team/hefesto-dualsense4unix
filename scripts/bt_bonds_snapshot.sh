#!/usr/bin/env bash
# bt_bonds_snapshot.sh — fotografa os bonds do BlueZ (/var/lib/bluetooth) para
# /var/lib/hefesto-dualsense4unix/bt-bonds/<timestamp>/.
#
# Motivação (sprint 2026-07-21-sprint-pesquisa-bluez-estabilidade.md, camada 2):
# o crash de heap do bluetoothd DESTRÓI bonds — e re-parear 4 controles na mão
# toda vez é exatamente a dor que o projeto promete curar. O snapshot roda:
#   1. periodicamente (hefesto-bt-bonds-snapshot.timer);
#   2. a cada parada do serviço (ExecStopPost no drop-in 10-hefesto-resilience).
#
# Regras de segurança do desenho (NÃO relaxar):
#   - NUNCA fotografa estado vazio: pós-crash os bonds já eram — sobrescrever o
#     backup bom com o vazio destruiria a única cópia. Zero arquivos `info` =
#     sai silencioso.
#   - Deduplicação por conteúdo: estado idêntico ao último snapshot = no-op
#     (o timer pode rodar a cada 15 min sem churn de disco).
#   - `cache/` fica de fora (é só cache de SDP/nome, grande e não-crítico).
#   - LinkKey é CREDENCIAL: diretório 700/600, dono root, e este script nunca
#     imprime conteúdo de chave (nem em modo verboso).
#   - A RESTAURAÇÃO é manual e separada (bt_bonds_restore.sh) — restaurar
#     automaticamente uma chave que o controle já rotacionou criaria loop de
#     falha de autenticação (o próprio gatilho do crash que queremos evitar).
#
# Uso: bt_bonds_snapshot.sh [--quiet]
# Requer root. Exit 0 sempre que a decisão for legítima (inclusive "nada a fazer").
set -euo pipefail

QUIET=0
[[ "${1:-}" == "--quiet" ]] && QUIET=1

SRC=/var/lib/bluetooth
DST_ROOT=/var/lib/hefesto-dualsense4unix/bt-bonds
KEEP=12

log() { [[ "${QUIET}" -eq 1 ]] || printf '%s\n' "$*"; logger -t hefesto-bt-bonds "$*" 2>/dev/null || true; }

if [[ "$(id -u)" -ne 0 ]]; then
    printf 'bt_bonds_snapshot.sh: requer root\n' >&2
    exit 1
fi

[[ -d "${SRC}" ]] || { log "sem ${SRC} — nada a fotografar"; exit 0; }

# Bonds reais = arquivos info em <adapter>/<device>/info. Zero = NUNCA fotografar
# (estado pós-crash; preservar o último backup bom é o objetivo do desenho).
mapfile -t INFOS < <(find "${SRC}" -mindepth 3 -maxdepth 3 -type f -name info 2>/dev/null | sort)
if [[ "${#INFOS[@]}" -eq 0 ]]; then
    log "zero bonds em disco — snapshot recusado de propósito (não sobrescrevo backup bom com vazio)"
    exit 0
fi

# Assinatura de conteúdo p/ dedup (caminhos + conteúdo; nunca impressa).
SIG="$(cat "${INFOS[@]}" 2>/dev/null | cat <(printf '%s\n' "${INFOS[@]}") - | sha256sum | awk '{print $1}')"

install -d -m 700 "${DST_ROOT}"

# SNAPSHOT-LOCK-01 (22/07): o ExecStopPost e outra instância (timer/watchdog)
# podem disparar no MESMO segundo — medido 22/07 22:43:13: dois processos
# colidiram no mesmo diretório-timestamp e o install falhou com "não foi
# possível mudar as permissões ... Arquivo ou diretório inexistente".
# Serializa por flock; o nome do diretório ganha o PID como sufixo único.
exec 9>"${DST_ROOT}/.lock"
if ! flock -w 30 9; then
    log "outro snapshot em andamento há >30s — desisto (o timer cobre)"
    exit 0
fi

LAST_SIG_FILE="${DST_ROOT}/.last-signature"
if [[ -f "${LAST_SIG_FILE}" ]] && [[ "$(cat "${LAST_SIG_FILE}" 2>/dev/null)" == "${SIG}" ]]; then
    log "estado idêntico ao último snapshot — no-op"
    exit 0
fi

TS="$(date +%Y%m%d-%H%M%S)-$$"
DST="${DST_ROOT}/${TS}"
if ! install -d -m 700 "${DST}" 2>/dev/null; then
    log "não consegui criar ${DST} (ambiente restrito no stop?) — snapshot fica pro próximo timer"
    exit 0
fi

# Copia cada adaptador SEM o cache/ (cp -a preserva modos; a poda do cache é
# feita por exclusão manual porque cp não tem --exclude portável).
while IFS= read -r -d '' ADAPTER; do
    BASE="$(basename "${ADAPTER}")"
    install -d -m 700 "${DST}/${BASE}"
    # Arquivos do nível do adaptador (settings, attributes, ...).
    find "${ADAPTER}" -mindepth 1 -maxdepth 1 -type f -exec cp -a {} "${DST}/${BASE}/" \;
    # Diretórios de device (bonds) — tudo, menos cache/.
    while IFS= read -r -d '' DEVDIR; do
        [[ "$(basename "${DEVDIR}")" == "cache" ]] && continue
        cp -a "${DEVDIR}" "${DST}/${BASE}/"
    done < <(find "${ADAPTER}" -mindepth 1 -maxdepth 1 -type d -print0)
done < <(find "${SRC}" -mindepth 1 -maxdepth 1 -type d -print0)

chmod -R go-rwx "${DST}"
printf '%s' "${SIG}" > "${LAST_SIG_FILE}"
chmod 600 "${LAST_SIG_FILE}"
log "snapshot de bonds gravado em ${DST} (${#INFOS[@]} bond(s))"

# Poda: mantém os KEEP mais recentes.
mapfile -t OLD < <(find "${DST_ROOT}" -mindepth 1 -maxdepth 1 -type d | sort | head -n -"${KEEP}")
for D in "${OLD[@]:-}"; do
    [[ -n "${D}" ]] && rm -rf "${D}"
done
exit 0
