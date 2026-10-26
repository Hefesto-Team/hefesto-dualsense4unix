#!/usr/bin/env bash
set -euo pipefail
_ajuda() {
  cat <<'AJUDA'
bt_bonds_restore.sh — restauração MANUAL de um snapshot de bonds do BlueZ.

Uso:
  bt_bonds_restore.sh --list           lista snapshots disponíveis
  bt_bonds_restore.sh --verificar <ts> valida um snapshot SEM restaurar nada
  bt_bonds_restore.sh --latest         restaura o snapshot mais recente
  bt_bonds_restore.sh <timestamp>      restaura um snapshot específico
AJUDA
}

SRC_ROOT="${HEFESTO_BT_BONDS_SRC:-/var/lib/hefesto-dualsense4unix/bt-bonds}"
DST="${HEFESTO_BT_DST:-/var/lib/bluetooth}"

_ARQUIVOS_DE_DEVICE_OK=" info attributes "
_ARQUIVOS_DE_ADAPTADOR_OK=" settings attributes cache "

_MAC_RE='^[0-9A-Fa-f]{2}(:[0-9A-Fa-f]{2}){5}$'

_recusa() {
    printf 'bt_bonds_restore.sh: RECUSADO — %s\n' "$1" >&2
    printf '   (RADIO-ABERTO-01/E10: um snapshot só é restaurado se cada entrada\n' >&2
    printf '    for arquivo ou diretório comum, com nome esperado. Nada de symlink.)\n' >&2
}

_entrada_comum_ok() {
    local caminho="$1" rotulo="$2"
    if [[ -L "${caminho}" ]]; then
        _recusa "${rotulo} é um SYMLINK (${caminho} -> $(readlink "${caminho}" 2>/dev/null))"
        return 1
    fi
    if [[ -d "${caminho}" ]]; then
        return 0
    fi
    if [[ ! -f "${caminho}" ]]; then
        _recusa "${rotulo} não é arquivo comum nem diretório (${caminho})"
        return 1
    fi
    local nlink
    nlink="$(stat -c '%h' "${caminho}" 2>/dev/null || echo 1)"
    if [[ "${nlink}" -gt 1 ]]; then
        _recusa "${rotulo} tem ${nlink} hardlinks (${caminho})"
        return 1
    fi
    return 0
}

_validar_snapshot() {
    local snap="$1" problemas=0 adapter base dev devbase arquivo nome entry
    while IFS= read -r -d '' adapter; do
        base="$(basename "${adapter}")"
        _entrada_comum_ok "${adapter}" "adaptador '${base}'" || { problemas=1; continue; }
        if [[ ! "${base}" =~ ${_MAC_RE} ]]; then
            _recusa "nome de adaptador não é um MAC: '${base}'"
            problemas=1
            continue
        fi
        while IFS= read -r -d '' entry; do
            nome="$(basename "${entry}")"
            _entrada_comum_ok "${entry}" "'${base}/${nome}'" || { problemas=1; continue; }
            if [[ -d "${entry}" ]]; then
                if [[ "${nome}" != "cache" && ! "${nome}" =~ ${_MAC_RE} ]]; then
                    _recusa "diretório inesperado em '${base}': '${nome}'"
                    problemas=1
                    continue
                fi
                while IFS= read -r -d '' arquivo; do
                    devbase="$(basename "${arquivo}")"
                    _entrada_comum_ok "${arquivo}" "'${base}/${nome}/${devbase}'" \
                        || { problemas=1; continue; }
                    if [[ -d "${arquivo}" ]]; then
                        _recusa "subdiretório inesperado em '${base}/${nome}': '${devbase}'"
                        problemas=1
                        continue
                    fi
                    if [[ "${nome}" == "cache" ]]; then
                        [[ "${devbase}" =~ ${_MAC_RE} ]] && continue
                        _recusa "entrada de cache com nome que não é MAC: '${devbase}'"
                        problemas=1
                    else
                        [[ "${_ARQUIVOS_DE_DEVICE_OK}" == *" ${devbase} "* ]] && continue
                        _recusa "arquivo inesperado em '${base}/${nome}': '${devbase}'"
                        problemas=1
                    fi
                done < <(find "${entry}" -mindepth 1 -maxdepth 1 -print0)
            else
                if [[ "${_ARQUIVOS_DE_ADAPTADOR_OK}" != *" ${nome} "* ]]; then
                    _recusa "arquivo inesperado em '${base}': '${nome}'"
                    problemas=1
                fi
            fi
        done < <(find "${adapter}" -mindepth 1 -maxdepth 1 -print0)
    done < <(find "${snap}" -mindepth 1 -maxdepth 1 -print0)
    return "${problemas}"
}

case "${1:-}" in
    --list|--verificar) ;;
    *)
        if [[ "$(id -u)" -ne 0 ]]; then
            printf 'bt_bonds_restore.sh: requer root\n' >&2
            exit 1
        fi
        ;;
esac

usage() { _ajuda; exit 1; }

ARG="${1:-}"
[[ -z "${ARG}" ]] && usage

if [[ "${ARG}" == "--list" ]]; then
    if [[ ! -d "${SRC_ROOT}" ]]; then
        printf 'nenhum snapshot (diretório %s ausente)\n' "${SRC_ROOT}"
        exit 0
    fi
    find "${SRC_ROOT}" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort | while read -r TS; do
        N="$(find "${SRC_ROOT}/${TS}" -mindepth 3 -maxdepth 3 -type f -name info 2>/dev/null | wc -l)"
        printf '%s  (%s bond(s))\n' "${TS}" "${N}"
    done
    exit 0
fi

SO_VERIFICAR=0
if [[ "${ARG}" == "--verificar" ]]; then
    SO_VERIFICAR=1
    ARG="${2:---latest}"
fi

if [[ "${ARG}" == "--latest" ]]; then
    SNAP="$(find "${SRC_ROOT}" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sort | tail -1)"
    [[ -z "${SNAP}" ]] && { printf 'nenhum snapshot disponível em %s\n' "${SRC_ROOT}" >&2; exit 1; }
else
    SNAP="${SRC_ROOT}/${ARG}"
    [[ -d "${SNAP}" ]] || { printf 'snapshot %s não existe (use --list)\n' "${ARG}" >&2; exit 1; }
fi

if ! _validar_snapshot "${SNAP}"; then
    printf 'bt_bonds_restore.sh: snapshot %s REPROVADO na validação — nada foi restaurado\n' \
        "${SNAP}" >&2
    exit 1
fi

if [[ "${SO_VERIFICAR}" -eq 1 ]]; then
    printf 'snapshot %s: validação OK (nada foi restaurado — modo --verificar)\n' "${SNAP}"
    exit 0
fi

N="$(find "${SNAP}" -mindepth 3 -maxdepth 3 -type f -name info 2>/dev/null | wc -l)"
if [[ "${N}" -eq 0 ]]; then
    printf 'snapshot %s não tem nenhum bond — nada a restaurar\n' "${SNAP}" >&2
    exit 1
fi

printf '>>> restaurando %s bond(s) de %s\n' "${N}" "${SNAP}"
printf '>>> o bluetooth.service vai ser PARADO durante a cópia (controles BT caem)\n'
printf '>>> se um controle recusar conexão depois: bluetoothctl remove <MAC> e re-pareie\n'

systemctl mask --runtime bluetooth.service >/dev/null 2>&1 || true
trap '
    systemctl unmask --runtime bluetooth.service >/dev/null 2>&1 || true
    systemctl start bluetooth.service
    systemctl reset-failed hefesto-bt-agent.service >/dev/null 2>&1 || true
    systemctl start hefesto-bt-agent.service >/dev/null 2>&1 || true
' EXIT
systemctl stop --job-mode=replace-irreversibly bluetooth.service
for _i in 1 2 3 4 5 6 7 8 9 10 11 12; do
    systemctl is-active --quiet bluetooth.service || break
    sleep 5
done
if systemctl is-active --quiet bluetooth.service; then
    printf 'bt_bonds_restore.sh: bluetooth.service não parou (60s) — abortando sem mexer no storage\n' >&2
    exit 1
fi

while IFS= read -r -d '' ADAPTER; do
    BASE="$(basename "${ADAPTER}")"
    install -d -m 700 "${DST}/${BASE}"
    find "${ADAPTER}" -mindepth 1 -maxdepth 1 -type f -exec cp -a {} "${DST}/${BASE}/" \;
    while IFS= read -r -d '' DEVDIR; do
        DEVBASE="$(basename "${DEVDIR}")"
        [[ "${DEVBASE}" == "cache" ]] && continue
        install -d -m 700 "${DST}/${BASE}/${DEVBASE}"
        find "${DEVDIR}" -mindepth 1 -maxdepth 1 -type f \
            \( -name info -o -name attributes \) \
            -exec cp -a {} "${DST}/${BASE}/${DEVBASE}/" \;
    done < <(find "${ADAPTER}" -mindepth 1 -maxdepth 1 -type d -print0)
    if [[ -d "${ADAPTER}/cache" ]]; then
        install -d -m 700 "${DST}/${BASE}/cache"
        while IFS= read -r -d '' ENTRY; do
            MAC="$(basename "${ENTRY}")"
            if ! grep -q '^\[ServiceRecords\]' "${ENTRY}" 2>/dev/null; then
                printf '   cache SDP de %s no snapshot está sem [ServiceRecords] — não restaurado\n' "${MAC}"
                continue
            fi
            cp -a "${ENTRY}" "${DST}/${BASE}/cache/"
        done < <(find "${ADAPTER}/cache" -mindepth 1 -maxdepth 1 -type f -print0)
    fi
done < <(find "${SNAP}" -mindepth 1 -maxdepth 1 -type d -print0)

chmod -R go-rwx "${DST}"
printf 'restaurado. religando o bluetooth.service...\n'
exit 0
