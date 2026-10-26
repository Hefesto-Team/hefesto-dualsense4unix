#!/usr/bin/env bash
set -euo pipefail

AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KVER="${1:?uso: escolher-o-fonte.sh <kernelver>}"
BUILD="${KVER%-*}"

DRIVER="$(sed -n 's/^BUILT_MODULE_NAME\[0\]="\([^"]*\)"$/\1/p' "${AQUI}/dkms.conf")"
if [[ -z "${DRIVER}" ]]; then
    echo "escolher-o-fonte: o dkms.conf não diz o BUILT_MODULE_NAME[0]" >&2
    exit 1
fi

POR_KERNEL="${AQUI}/fonte-por-kernel"
if [[ -f "${POR_KERNEL}/${BUILD}/${DRIVER}.c" ]]; then
    cp -f "${POR_KERNEL}/${BUILD}/${DRIVER}.c" "${AQUI}/${DRIVER}.c"
    cp -f "${POR_KERNEL}/${BUILD}/hid-ids.h" "${AQUI}/hid-ids.h"
    echo "hefesto-${DRIVER}: o fonte de ${BUILD} no lugar"
    exit 0
fi

if grep -qxF "${BUILD}" "${POR_KERNEL}/raiz.txt" 2>/dev/null; then
    echo "hefesto-${DRIVER}: o fonte da raiz serve a ${BUILD}"
    exit 0
fi

echo "hefesto-${DRIVER}: não tenho fonte conferido para ${BUILD}." >&2
echo "  conferidos: $(tr '\n' ' ' < "${POR_KERNEL}/raiz.txt" 2>/dev/null)$(cd "${POR_KERNEL}" && ls -d */ 2>/dev/null | tr -d / | tr '\n' ' ')" >&2
echo "  o ritual está em patch/BASELINE" >&2
exit 1
