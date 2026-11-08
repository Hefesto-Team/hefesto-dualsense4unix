#!/usr/bin/env bash
set -uo pipefail

BASE="${HEFESTO_PACOTE_BASE:-/usr/share/hefesto-dualsense4unix}"

_os_modulos() {
    local conf pacote ko
    for conf in "${BASE}"/dkms/*/dkms.conf; do
        [[ -f "${conf}" ]] || continue
        pacote="$(sed -n 's/^PACKAGE_NAME="\(.*\)"$/\1/p' "${conf}")"
        ko="$(sed -n 's/^BUILT_MODULE_NAME\[0\]="\(.*\)"$/\1/p' "${conf}")"
        if [[ "${ko}" == "uhid" && "${COM_UHID_CONTRAPRESSAO:-0}" != 1 \
              && ! -f "${HEFESTO_UHID_CONF:-/etc/modprobe.d/hefesto-uhid.conf}" ]]; then
            continue
        fi
        printf '%s\t%s\t%s\n' "${pacote}" "${conf%/dkms.conf}" "${ko}"
    done
}

if [[ "${1:-}" == "--lista" ]]; then
    _os_modulos | while IFS=$'\t' read -r _ _ ko; do printf '%s\n' "${ko}"; done
    exit 0
fi

export HEFESTO_DKMS_KERNEL="${1:-}"

if [[ "$(id -u)" -eq 0 ]]; then
    sudo() { "$@"; }
fi

# shellcheck source=dkms_lib.sh
source "${BASE}/scripts/dkms_lib.sh"

mapfile -t _linhas < <(_os_modulos)
for _linha in "${_linhas[@]}"; do
    IFS=$'\t' read -r pacote fonte ko <<< "${_linha}"
    dkms_install_patched_module "${pacote}" "$(dkms_pkg_version "${fonte}")" "${fonte}" "${ko}"
done

dkms_flush_initramfs
exit 0
