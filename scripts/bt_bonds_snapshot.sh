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
#   - `cache/` dos devices COM BOND entra no snapshot (SDP-CACHE-01, 23/07).
#     A premissa antiga ("é só cache de nome, não-crítico") estava ERRADA e
#     custou o 4º controle: o registro SDP do perfil HID mora em
#     `cache/<MAC>`, seção [ServiceRecords], e é dele que o BlueZ tira o
#     descritor HID em profiles/input/device.c:hidp_add_connection(). Sem a
#     seção o perfil HID nunca sobe — e como `info` já lista
#     `Services=...1124...`, o BlueZ acha que conhece os serviços e NUNCA
#     refaz o browse: vira zumbi permanente (ACL vivo + Connected=true, zero
#     hidraw, ReconnectMode="none"). Só o cache dos devices com bond é
#     copiado — o resto do cache/ (dezenas de MACs só vistos em scan) segue
#     de fora, que é o que de fato era grande e não-crítico.
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

# Raízes parametrizadas p/ teste (mesmo idioma de doctor.sh:_hidraw_uniqs).
# Em produção NADA define estas variáveis — os defaults são os caminhos reais.
SRC="${HEFESTO_BT_SRC:-/var/lib/bluetooth}"
DST_ROOT="${HEFESTO_BT_SNAP_ROOT:-/var/lib/hefesto-dualsense4unix/bt-bonds}"
KEEP=12

log() { [[ "${QUIET}" -eq 1 ]] || printf '%s\n' "$*"; logger -t hefesto-bt-bonds "$*" 2>/dev/null || true; }

# Root só é exigido para a árvore REAL (/var/lib/bluetooth é 700 do root). Com
# as raízes de teste apontando para outro lugar, root não acrescenta nada — e
# exigi-lo tornaria a lógica de seleção do cache não-testável.
if [[ "${SRC}" == "/var/lib/bluetooth" ]] && [[ "$(id -u)" -ne 0 ]]; then
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
#
# SNAPSHOT-SIG-COBRE-TUDO-01 (23/07): a assinatura tem de cobrir EXATAMENTE o
# conjunto que o laço de cópia grava. Antes ela hasheava só os `info`, então
# uma mudança em qualquer outro arquivo copiado — inclusive o cache SDP que o
# SDP-CACHE-01 passou a preservar — caía no no-op de "estado idêntico" e nunca
# virava snapshot. Medido ao vivo em 23/07: o sha256 dos 4 `info` batia com o
# .last-signature e o snapshot mais recente não tinha diretório cache/ nenhum —
# ou seja, o fix do cache nascia INERTE nesta máquina.
#
# O prefixo FMT é marcador de versão do FORMATO do snapshot: incrementá-lo
# força UMA gravação na primeira execução após a mudança, mesmo com o estado do
# BlueZ idêntico. É o que destrava máquinas que já têm .last-signature antigo.
mapfile -t SIG_ARQUIVOS < <(
    {
        printf '%s\n' "${INFOS[@]}"
        # attributes de device, e settings/attributes do nível do adaptador.
        find "${SRC}" -mindepth 2 -maxdepth 2 -type f 2>/dev/null
        find "${SRC}" -mindepth 3 -maxdepth 3 -type f ! -name info 2>/dev/null
        # cache/<MAC> APENAS dos devices com bond — a mesma seleção do laço de
        # cópia abaixo; entradas de MAC só visto em scan não entram (nem no
        # snapshot, nem na assinatura).
        for _I in "${INFOS[@]}"; do
            _DEV="$(dirname "${_I}")"
            _C="$(dirname "${_DEV}")/cache/$(basename "${_DEV}")"
            [[ -f "${_C}" ]] && printf '%s\n' "${_C}"
        done
    } | sort -u
)
SIG="$( { printf 'FMT=2\n'; printf '%s\n' "${SIG_ARQUIVOS[@]}"; cat "${SIG_ARQUIVOS[@]}" 2>/dev/null; } | sha256sum | awk '{print $1}')"

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

# Copia cada adaptador: diretórios de bond inteiros + APENAS as entradas de
# cache/ que correspondem a um bond (SDP-CACHE-01). cp -a preserva modos; a
# seleção é manual porque cp não tem --exclude portável.
while IFS= read -r -d '' ADAPTER; do
    BASE="$(basename "${ADAPTER}")"
    install -d -m 700 "${DST}/${BASE}"
    # Arquivos do nível do adaptador (settings, attributes, ...).
    find "${ADAPTER}" -mindepth 1 -maxdepth 1 -type f -exec cp -a {} "${DST}/${BASE}/" \;
    # Diretórios de device (bonds) — tudo, menos cache/ (tratado abaixo).
    while IFS= read -r -d '' DEVDIR; do
        [[ "$(basename "${DEVDIR}")" == "cache" ]] && continue
        cp -a "${DEVDIR}" "${DST}/${BASE}/"
    done < <(find "${ADAPTER}" -mindepth 1 -maxdepth 1 -type d -print0)
    # cache/ dos devices com bond: é onde vive o registro SDP do perfil HID.
    # Sem ele o controle reconecta e nunca vira hidraw (ver cabeçalho).
    if [[ -d "${ADAPTER}/cache" ]]; then
        N_CACHE=0
        while IFS= read -r -d '' DEVDIR; do
            MAC="$(basename "${DEVDIR}")"
            [[ -f "${ADAPTER}/cache/${MAC}" ]] || continue
            install -d -m 700 "${DST}/${BASE}/cache"
            cp -a "${ADAPTER}/cache/${MAC}" "${DST}/${BASE}/cache/"
            N_CACHE=$((N_CACHE + 1))
        done < <(find "${ADAPTER}" -mindepth 1 -maxdepth 1 -type d ! -name cache -print0)
        [[ "${N_CACHE}" -gt 0 ]] && log "cache SDP de ${N_CACHE} device(s) com bond incluído"
    fi
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
