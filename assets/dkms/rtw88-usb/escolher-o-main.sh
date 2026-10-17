#!/usr/bin/env bash
# escolher-o-main.sh — põe no lugar o `main.h` do kernel que está sendo compilado
# e, quando o fonte de fábrica dele não é o da raiz, o `usb.c` e o `rx.h` dele.
#
# POR QUE ISTO EXISTE, e é a coisa mais perigosa deste módulo (01/09/2026).
#
# O `linux-headers` NÃO traz headers de driver: só `Kconfig` e `Makefile` do
# rtw88 (conferido nos dois kernels desta máquina). Então o `main.h` viaja
# dentro do nosso pacote — e ele é quem CONGELA o layout de `struct rtw_dev`.
#
# O `usb.c` chama `rtw_get_usb_priv(rtwdev)`, que é `(struct rtw_usb *)
# rtwdev->priv`. O `priv` é o ÚLTIMO membro de `struct rtw_dev`, logo o
# deslocamento dele é resolvido em tempo de COMPILAÇÃO a partir do tamanho da
# struct. Se o kernel em execução tiver uma struct MAIOR, o `rtw88_core` alocou
# o `priv` mais adiante — e o nosso módulo escreveria dentro do coex. Linka
# limpo (não há CRC de modversions para `static inline`) e corrompe memória em
# runtime.
#
# MEDIDO entre 7.0.11-76070011 e 7.1.5-76070105: o `usb.c` e o `usb.h` são
# IDÊNTICOS byte a byte depois dos patches, e nove dos dez headers também. Só o
# `main.h` diverge, em duas mudanças aditivas — um `enum rtw_quirk_dis_caps`
# (inócuo) e um `bool bt_ctr_ok` DENTRO de `struct rtw_coex_stat`, que é membro
# de `struct rtw_dev`. Duas linhas, e são exatamente as que deslocam o `priv`.
#
# POR ISSO A ESCOLHA É POR BUILD EXATO, e não por versão nominal: um respin da
# mesma 7.1.5 com struct diferente teria o mesmo nome e o layout errado. Kernel
# que não estiver nesta pasta não compila — o `BUILD_EXCLUSIVE_KERNEL` do
# `dkms.conf` o barra antes, e o in-tree assume sozinho (fail-safe: nunca ficar
# sem WiFi).
#
# O `usb.c` E O `rx.h` POR KERNEL (17/10/2026). O 7.2.6 mudou o de fábrica: o
# `rtw_rx_query_rx_desc` passou a devolver `int` (o `rx.h` o declara) e o
# `rtw_usb_rx_handler` testa o retorno. O `usb.c` da raiz, construído ali,
# desfaria a mudança em silêncio. Por isso o kernel cujo de fábrica não é o da
# raiz ganha `fonte-por-kernel/<build>/` com o `usb.c` (a série aplicada sobre
# o de fábrica DELE), o `rx.h` dele e a série rebaseada em `patch/`; os builds
# que a raiz serve moram em `fonte-por-kernel/raiz.txt`, porque o
# `dkms_lib.sh` apaga o `patch/` do /usr/src e a BASELINE não chega aqui. A
# cada build o DKMS refaz a pasta de build do zero (`rm -rf` em `prepare_build`),
# então o arquivo trocado não vaza para o build seguinte.
#
# COMO ACRESCENTAR UM KERNEL, o ritual inteiro está em `patch/BASELINE`.
set -euo pipefail

AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KVER="${1:?uso: escolher-o-main.sh <kernelver>}"

# `7.1.5-76070105-generic` -> `7.1.5-76070105`: o sufixo de sabor (-generic,
# -lowlatency) não muda struct nenhuma, e exigi-lo no nome do arquivo faria a
# mesma ABI precisar de duas cópias idênticas.
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
