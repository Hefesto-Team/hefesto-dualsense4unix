#!/usr/bin/env bash
set -uo pipefail

BASE="${HEFESTO_PACOTE_BASE:-/usr/share/hefesto-dualsense4unix}"
export HEFESTO_DKMS_KERNEL="${1:-}"

if [[ "$(id -u)" -eq 0 ]]; then
    sudo() { "$@"; }
fi

# shellcheck source=dkms_lib.sh
source "${BASE}/scripts/dkms_lib.sh"

for conf in "${BASE}"/dkms/*/dkms.conf; do
    [[ -f "${conf}" ]] || continue
    pacote="$(sed -n 's/^PACKAGE_NAME="\(.*\)"$/\1/p' "${conf}")"
    modulo="$(sed -n 's/^BUILT_MODULE_NAME\[0\]="\(.*\)"$/\1/p' "${conf}")"
    fonte="${conf%/dkms.conf}"
    if [[ "${modulo}" == "uhid" && "${COM_UHID_CONTRAPRESSAO:-0}" -ne 1 \
          && ! -f "${HEFESTO_UHID_CONF:-/etc/modprobe.d/hefesto-uhid.conf}" ]]; then
        continue
    fi
    dkms_install_patched_module "${pacote}" "$(dkms_pkg_version "${fonte}")" "${fonte}" "${modulo}"
done

dkms_flush_initramfs
exit 0
