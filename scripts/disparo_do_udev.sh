#!/usr/bin/env bash
set -u

AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

command -v udevadm >/dev/null 2>&1 || exit 0

LEITOR=""
for candidato in \
    "${AQUI}/quem_o_jogo_le.py" \
    "${AQUI}/../src/hefesto_dualsense4unix/integrations/quem_o_jogo_le.py" \
; do
    if [[ -f "${candidato}" ]]; then
        LEITOR="${candidato}"
        break
    fi
done

JOGO=2
if [[ -n "${LEITOR}" ]] && command -v python3 >/dev/null 2>&1; then
    python3 -I "${LEITOR}" --ha-jogo --proc "${HEFESTO_RAIZ_PROC:-/proc}" >/dev/null 2>&1
    JOGO=$?
fi

case "${JOGO}" in
    1)
        udevadm trigger --action=change --subsystem-match=hidraw 2>/dev/null || true
        udevadm trigger --subsystem-match=usb --attr-match=idVendor=054c 2>/dev/null || true
        udevadm trigger --action=change --subsystem-match=usb 2>/dev/null || true
        udevadm trigger --action=change --subsystem-match=input 2>/dev/null || true
        ;;
    0)
        echo "  com um jogo aberto, o controle não é reenumerado: as regras novas valem no próximo plugue"
        ;;
    *)
        echo "  não deu para saber se há jogo aberto, então o controle não é reenumerado: as regras novas valem no próximo plugue"
        ;;
esac

udevadm trigger --subsystem-match=leds --action=add 2>/dev/null || true
udevadm trigger --subsystem-match=misc --action=add 2>/dev/null || true
udevadm trigger --action=change --subsystem-match=pci 2>/dev/null || true

if [[ "${JOGO}" -eq 1 ]]; then
    udevadm trigger 2>/dev/null || true
fi

exit 0
