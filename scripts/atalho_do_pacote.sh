#!/usr/bin/env bash
set -euo pipefail

uso() {
    echo "uso: bash scripts/atalho_do_pacote.sh MODELO.desktop SAIDA.desktop EXECUTAVEL [ARGUMENTO...]" >&2
    echo "  EXECUTAVEL é o caminho absoluto que o formato instala; cada argumento entra citado." >&2
}

if [[ "$#" -lt 3 ]]; then
    uso
    exit 2
fi

MODELO="$1"
SAIDA="$2"
shift 2
EXECUTAVEL="$1"

if [[ ! -f "${MODELO}" ]]; then
    echo "ERRO: modelo ausente: ${MODELO}" >&2
    exit 1
fi
if [[ "${EXECUTAVEL}" != /* ]]; then
    echo "ERRO: o executável tem de ser um caminho absoluto: ${EXECUTAVEL}" >&2
    exit 2
fi

_citar() {
    local s="${1//\%/%%}"
    if [[ "${s}" =~ ^[A-Za-z0-9_./+:,=%-]+$ ]]; then
        printf '%s' "${s}"
        return 0
    fi
    s="${s//\\/\\\\\\\\}"
    s="${s//\"/\\\\\"}"
    s="${s//\`/\\\\\`}"
    s="${s//\$/\\\\\$}"
    printf '"%s"' "${s}"
}

_linha_do_modelo="$(sed -n 's/^Exec=//p' "${MODELO}" | head -1)"
if [[ "${_linha_do_modelo}" != *" @RAIZ@"* ]]; then
    echo "ERRO: o Exec= do modelo não tem a forma «<prefixo> @RAIZ@/...»: ${_linha_do_modelo}" >&2
    exit 1
fi
PREFIXO="${_linha_do_modelo%% @RAIZ@*}"

LINHA="${PREFIXO}"
for _parte in "$@"; do
    LINHA+=" $(_citar "${_parte}")"
done

mkdir -p "$(dirname "${SAIDA}")"
_parcial="$(mktemp "${SAIDA}.XXXXXX")"
trap 'rm -f "${_parcial}"' EXIT

EXEC_DO_ATALHO="${LINHA}" awk '
    /^[[:space:]]*#/ { next }
    /^X-HefestoNaoEmpacotado[[:space:]]*=/ { next }
    /^Exec[[:space:]]*=/ { print "Exec=" ENVIRON["EXEC_DO_ATALHO"]; achou = 1; next }
    { print }
    END { if (!achou) exit 3 }
' "${MODELO}" > "${_parcial}" || {
    echo "ERRO: o modelo não tem linha Exec=: ${MODELO}" >&2
    exit 1
}

if grep -qE '@[A-Za-z_]+@' "${_parcial}"; then
    echo "ERRO: o atalho ficou com marcador @...@ sobrando:" >&2
    grep -nE '@[A-Za-z_]+@' "${_parcial}" >&2
    exit 1
fi
if grep -q '^X-HefestoNaoEmpacotado' "${_parcial}"; then
    echo "ERRO: o atalho do pacote ficou com a chave X-HefestoNaoEmpacotado" >&2
    exit 1
fi

chmod 644 "${_parcial}"
mv -f "${_parcial}" "${SAIDA}"
trap - EXIT
echo "atalho: ${SAIDA} -> ${LINHA}"
