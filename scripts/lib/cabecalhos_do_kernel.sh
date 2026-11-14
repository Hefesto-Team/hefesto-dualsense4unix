#!/usr/bin/env bash

cabecalhos_do_kernel_no_pacman() {
    local _kver="${1:-$(uname -r)}" _dono=""
    _dono="$(pacman -Qqo "/usr/lib/modules/${_kver}/vmlinuz" 2>/dev/null | head -n 1)"
    printf '%s-headers\n' "${_dono:-linux}"
}
