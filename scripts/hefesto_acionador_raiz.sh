#!/usr/bin/env bash
set -u

if [[ "$(id -u)" -eq 0 ]]; then
    export PATH=/usr/sbin:/usr/bin:/sbin:/bin
    PASTA=/var/lib/hefesto-dualsense4unix/acionadores
else
    PASTA="${HEFESTO_ACIONADOR_PASTA:-}"
fi
LISTA="${PASTA}/autorizados"
FORMA='^[0-9a-f]{4}:[0-9a-f]{4}:[0-9a-f]{8}$'
MAXIMO=64

umask 022

_recusar() { printf '%s: %s\n' "${0##*/}" "$*" >&2; exit 2; }

_juntar() {
    local novo
    if [[ -e "${PASTA}" && ( -L "${PASTA}" || ! -d "${PASTA}" ) ]]; then
        _recusar "${PASTA} não é uma pasta"
    fi
    mkdir -p "${PASTA}" && chmod 0755 "${PASTA}" || _recusar "não consegui criar ${PASTA}"
    if [[ -L "${LISTA}" || ( -e "${LISTA}" && ! -f "${LISTA}" ) ]]; then
        _recusar "${LISTA} não é um arquivo comum"
    fi
    novo="$(mktemp "${PASTA}/.autorizados.XXXXXX")" || _recusar "não consegui escrever em ${PASTA}"
    {
        [[ -f "${LISTA}" ]] && cat -- "${LISTA}"
        printf '%s\n' "$@"
    } | grep -E "${FORMA}" | sort -u | head -n "${MAXIMO}" >"${novo}"
    if ! chmod 0644 "${novo}" || ! mv -f "${novo}" "${LISTA}"; then
        rm -f "${novo}"
        _recusar "não consegui gravar ${LISTA}"
    fi
}

_autorizar() {
    local chave=""
    IFS= read -r -n 32 chave
    [[ "${chave}" =~ ${FORMA} ]] || _recusar "a chave do aparelho não tem a forma vvvv:pppp:hhhhhhhh"
    _juntar "${chave}"
}

_semear() {
    local chave chaves=()
    [[ -e "${LISTA}" ]] && return 0
    while IFS= read -r -n 32 chave && [[ "${#chaves[@]}" -lt "${MAXIMO}" ]]; do
        [[ "${chave}" =~ ${FORMA} ]] && chaves+=("${chave}")
    done
    _juntar ${chaves[@]+"${chaves[@]}"}
}

[[ -n "${PASTA}" ]] || _recusar "'${1:-}' requer root"
case "${1:-}" in
    autorizar) _autorizar ;;
    semear) _semear ;;
    *) _recusar "uso: ${0##*/} autorizar|semear (as chaves chegam pelo stdin)" ;;
esac
