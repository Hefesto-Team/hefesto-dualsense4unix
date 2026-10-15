#!/usr/bin/env bash
# escolher-o-fonte.sh — põe no lugar o `.c` do driver e o `hid-ids.h` do kernel
# que está sendo compilado. É o mesmo arquivo, byte a byte, no `hid-nintendo` e
# no `hid-playstation`; o driver sai do `BUILT_MODULE_NAME[0]` do `dkms.conf`.
#
# POR QUE ISTO EXISTE (15/10/2026). O `.c` deste pacote SUBSTITUI o de fábrica.
# Construído contra um kernel cujo de fábrica é outro, ele compila limpo e
# devolve o arquivo ERRADO: os consertos do kernel novo somem em silêncio. Por
# isso cada kernel conferido tem o seu fonte, a série aplicada sobre o de
# fábrica DELE, e o `PRE_BUILD` do `dkms.conf` escolhe pelo build exato.
#
# A escolha, por build (`7.2.6-76070206-generic` -> `7.2.6-76070206`, porque o
# sabor não muda o fonte):
#   - `fonte-por-kernel/<build>/` existe: o `.c` e o `hid-ids.h` dele vão para a
#     raiz do diretório de build;
#   - o build está em `fonte-por-kernel/raiz.txt`: o `.c` da raiz é o dele;
#   - nenhum dos dois: sai com erro. O `BUILD_EXCLUSIVE_KERNEL` barra antes, e
#     este é o segundo trinco, para o dia em que a regex e a pasta divergirem.
#
# O `patch/BASELINE` não chega aqui: o `dkms_lib.sh` apaga o `patch/` do
# `/usr/src`. Por isso a lista da raiz mora em `fonte-por-kernel/raiz.txt`, e
# uma régua cobra que ela, as pastas, o `KERNELS_VALIDADOS` e a regex digam o
# mesmo. O ritual para acrescentar um kernel está no `patch/BASELINE`.
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
