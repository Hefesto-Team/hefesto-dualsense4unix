#!/usr/bin/env bash
set -euo pipefail

DESTINO="${1:-}"
BINARIO="${2:-}"

if [[ -z "${DESTINO}" || -z "${BINARIO}" ]]; then
    echo "uso: bash scripts/broker_do_pacote.sh DIRETORIO_DAS_UNITS CAMINHO_DO_BINARIO" >&2
    exit 2
fi
if [[ "${BINARIO}" != /* ]]; then
    echo "ERRO: o binário tem de ser um caminho absoluto: ${BINARIO}" >&2
    exit 2
fi

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICO_SRC="${RAIZ}/assets/systemd/hefesto-hidraw-broker.service"
SOCKET_SRC="${RAIZ}/assets/systemd/hefesto-hidraw-broker.socket"
BINARIO_DO_INSTALL="/usr/local/lib/hefesto-dualsense4unix/hefesto-hidraw-broker"

for _f in "${SERVICO_SRC}" "${SOCKET_SRC}"; do
    [[ -f "${_f}" ]] || { echo "ERRO: asset ausente: ${_f}" >&2; exit 1; }
done

mkdir -p "${DESTINO}"
_s="${DESTINO}/hefesto-hidraw-broker.service"
_k="${DESTINO}/hefesto-hidraw-broker.socket"

sed -e "s/__NO_NASCE_FECHADO__/1/" \
    -e "s|${BINARIO_DO_INSTALL}|${BINARIO}|g" \
    "${SERVICO_SRC}" > "${_s}"
cat "${SOCKET_SRC}" > "${_k}"

if grep -q '__[A-Z_]*__' "${_s}" "${_k}"; then
    rm -f "${_s}" "${_k}"
    echo "ERRO: a unit do broker ficou com placeholder sobrando" >&2
    exit 1
fi
if grep -q "${BINARIO_DO_INSTALL}" "${_s}" && [[ "${BINARIO}" != "${BINARIO_DO_INSTALL}" ]]; then
    rm -f "${_s}" "${_k}"
    echo "ERRO: a unit do broker ainda aponta para o caminho do install nativo" >&2
    exit 1
fi
if ! grep -q "^ExecStart=${BINARIO}\$" "${_s}"; then
    rm -f "${_s}" "${_k}"
    echo "ERRO: o ExecStart da unit do broker não aponta para ${BINARIO}" >&2
    exit 1
fi
