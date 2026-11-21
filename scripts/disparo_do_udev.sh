#!/usr/bin/env bash
set -u

AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PASTA_DA_REMOCAO="${HEFESTO_RUN_DA_REMOCAO:-/run/hefesto-dualsense4unix-remocao}"
MODO="${1:-}"

decidir() {
    local candidato leitor=""
    for candidato in \
        "${AQUI}/quem_o_jogo_le.py" \
        "${AQUI}/../src/hefesto_dualsense4unix/integrations/quem_o_jogo_le.py" \
    ; do
        if [[ -f "${candidato}" ]]; then
            leitor="${candidato}"
            break
        fi
    done
    JOGO=3
    if [[ -n "${leitor}" ]] && command -v python3 >/dev/null 2>&1; then
        python3 -I "${leitor}" --ha-jogo --proc "${HEFESTO_RAIZ_PROC:-/proc}" >/dev/null 2>&1
        JOGO=$?
    fi
}

aplicar() {
    case "${JOGO}" in
        10)
            udevadm trigger --action=change --subsystem-match=hidraw 2>/dev/null || true
            udevadm trigger --subsystem-match=usb --attr-match=idVendor=054c 2>/dev/null || true
            udevadm trigger --action=change --subsystem-match=usb 2>/dev/null || true
            udevadm trigger --action=change --subsystem-match=input 2>/dev/null || true
            ;;
        0)
            echo "  com um jogo aberto, o controle não é reenumerado: ${REGRAS} no próximo plugue"
            ;;
        *)
            echo "  não deu para saber se há jogo aberto, então o controle não é reenumerado: ${REGRAS} no próximo plugue"
            ;;
    esac

    udevadm trigger --subsystem-match=leds --action=add 2>/dev/null || true
    udevadm trigger --subsystem-match=misc --action=add 2>/dev/null || true
    udevadm trigger --action=change --subsystem-match=pci 2>/dev/null || true

    if [[ "${JOGO}" -eq 10 ]]; then
        udevadm trigger 2>/dev/null || true
    fi
}

if [[ "${MODO}" == "--pode-reenumerar" ]]; then
    decidir
    [[ "${JOGO}" -eq 10 ]]
    exit $?
fi

command -v udevadm >/dev/null 2>&1 || exit 0

case "${MODO}" in
    --preparar-a-remocao)
        decidir
        mkdir -p "${PASTA_DA_REMOCAO}" 2>/dev/null || exit 0
        printf '%s\n' "${JOGO}" > "${PASTA_DA_REMOCAO}/veredito" 2>/dev/null || true
        install -m 0755 "${BASH_SOURCE[0]}" "${PASTA_DA_REMOCAO}/disparo_do_udev.sh" 2>/dev/null || true
        ;;
    --apos-a-remocao)
        JOGO=3
        if [[ -f "${PASTA_DA_REMOCAO}/veredito" ]]; then
            read -r JOGO < "${PASTA_DA_REMOCAO}/veredito" || JOGO=3
        fi
        [[ "${JOGO}" =~ ^[0-9]+$ ]] || JOGO=3
        REGRAS="a remoção das regras vale"
        rm -f "${PASTA_DA_REMOCAO}/veredito" "${PASTA_DA_REMOCAO}/disparo_do_udev.sh" 2>/dev/null || true
        rmdir "${PASTA_DA_REMOCAO}" 2>/dev/null || true
        aplicar
        ;;
    *)
        REGRAS="as regras novas valem"
        decidir
        aplicar
        ;;
esac

exit 0
