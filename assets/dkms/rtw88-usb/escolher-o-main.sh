#!/usr/bin/env bash
set -euo pipefail

AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KVER="${1:?uso: escolher-o-main.sh <kernelver>}"

BUILD="${KVER%-*}"
ALVO="${AQUI}/main-por-kernel/main-${BUILD}.h"

if [[ ! -f "${ALVO}" ]]; then
    echo "hefesto-rtw88-usb: não tenho main.h validado para ${BUILD}." >&2
    echo "  validados: $(cd "${AQUI}/main-por-kernel" && ls main-*.h | sed 's/^main-//;s/\.h$//' | tr '\n' ' ')" >&2
    echo "  o ritual de rebase está em patch/BASELINE" >&2
    exit 1
fi

POR_KERNEL="${AQUI}/fonte-por-kernel"
if [[ -d "${POR_KERNEL}/${BUILD}" ]]; then
    for arquivo in "${POR_KERNEL}/${BUILD}"/*; do
        [[ -f "${arquivo}" ]] && cp -f "${arquivo}" "${AQUI}/$(basename "${arquivo}")"
    done
    echo "hefesto-rtw88-usb: o fonte de ${BUILD} no lugar"
elif grep -qxF "${BUILD}" "${POR_KERNEL}/raiz.txt" 2>/dev/null; then
    echo "hefesto-rtw88-usb: o fonte da raiz serve a ${BUILD}"
else
    echo "hefesto-rtw88-usb: não tenho fonte conferido para ${BUILD}." >&2
    echo "  conferidos: $(tr '\n' ' ' < "${POR_KERNEL}/raiz.txt" 2>/dev/null)$(cd "${POR_KERNEL}" && ls -d */ 2>/dev/null | tr -d / | tr '\n' ' ')" >&2
    echo "  o ritual de rebase está em patch/BASELINE" >&2
    exit 1
fi

cp -f "${ALVO}" "${AQUI}/main.h"
echo "hefesto-rtw88-usb: main.h de ${BUILD} no lugar"
