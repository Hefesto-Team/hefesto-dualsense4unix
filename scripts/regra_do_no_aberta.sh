#!/usr/bin/env bash
set -euo pipefail

ORIGEM="${1:-}"
DESTINO="${2:-}"

if [[ -z "${ORIGEM}" || -z "${DESTINO}" ]]; then
    echo "uso: bash scripts/regra_do_no_aberta.sh ORIGEM DESTINO" >&2
    exit 2
fi

if [[ ! -f "${ORIGEM}" ]]; then
    echo "ERRO: origem ausente: ${ORIGEM}" >&2
    exit 1
fi

_tmp="$(mktemp)"
trap 'rm -f "${_tmp}"' EXIT

sed -E -e 's/MODE:?="0600", OWNER:?="root", GROUP:?="root", TAG-="uaccess"/MODE="0660", TAG+="uaccess"/' \
    "${ORIGEM}" > "${_tmp}"

_regras() { grep -v '^[[:space:]]*#' "$1" || true; }

if _regras "${_tmp}" | grep -q 'TAG-="uaccess"'; then
    echo "ERRO: não foi possível reabrir todas as linhas de ${ORIGEM}." >&2
    echo "      nada foi escrito em ${DESTINO}." >&2
    exit 1
fi

_abertas="$(_regras "${_tmp}" | grep -v 'DEVPATH==' | grep -ci '0ce6.*TAG+="uaccess"' || true)"
if [[ "${_abertas}" -ne 2 ]]; then
    echo "ERRO: a variante aberta de ${ORIGEM} tem ${_abertas} linha(s) 0ce6 com uaccess; esperadas 2." >&2
    echo "      nada foi escrito em ${DESTINO}." >&2
    exit 1
fi

install -Dm644 "${_tmp}" "${DESTINO}"
