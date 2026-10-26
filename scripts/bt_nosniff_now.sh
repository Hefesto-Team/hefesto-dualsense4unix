#!/usr/bin/env bash
set -euo pipefail

MAC="${1:-}"
NOME="${2:-${HID_NAME:-}}"
if [[ -z "${MAC}" ]]; then
    printf 'bt_nosniff_now.sh: uso: %s <MAC> [NOME]\n' "${0##*/}" >&2
    exit 2
fi

OUIS_CLONE=("e4:17:d8")
OUIS_NINTENDO_VISTAS=("e0:f6:b5")
NOMES_PRO=("pro controller")

LOG_TAG=hefesto-bt
LOG_DEST="${HEFESTO_BT_LOG_DEST:-}"
_registrar() {
    case "${LOG_DEST}" in
        "")   logger -t "${LOG_TAG}" "$*" 2>/dev/null || true ;;
        none) : ;;
        *)    printf '%s %s: %s\n' "$(date -Is 2>/dev/null || true)" "${LOG_TAG}" "$*" \
                  2>/dev/null >>"${LOG_DEST}" || true ;;
    esac
}

_recusar() { _registrar "no-sniff na borda NÃO aplicado em ${MAC}: $*"; exit 0; }

if [[ ! "${MAC}" =~ ^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$ ]]; then
    _recusar "'${MAC}' não tem forma de endereço BR/EDR (seis octetos hex separados por ':') — pelo cabo o HID_UNIQ é o serial do device, e cabo não tem link para tirar do sniff"
fi

for _marca in "${OUIS_CLONE[@]}"; do
    if [[ "${MAC,,}" == "${_marca}"* ]]; then
        _recusar "é a faixa do clone 8BitDo, e para ele o no-sniff é veneno — o firmware trata a recusa de sniff como erro e a probe morre em 'ret=-110' (A/B de 23/07/2026). Recusar aqui É a cura, não uma falha"
    fi
done

_conhecida=1
for _marca in "${OUIS_NINTENDO_VISTAS[@]}"; do
    [[ "${MAC,,}" == "${_marca}"* ]] && { _conhecida=0; break; }
done

if [[ "${_conhecida}" -ne 0 ]]; then
    _parece_pro=1
    for _marca in "${NOMES_PRO[@]}"; do
        [[ "${NOME,,}" == *"${_marca}"* ]] && { _parece_pro=0; break; }
    done
    if [[ "${_parece_pro}" -ne 0 ]]; then
        if [[ -z "${NOME}" ]]; then
            _recusar "a faixa não é nenhuma das que esta casa já viu num aparelho e o CHAMADOR NÃO DECLAROU o nome — isto é 'não dá para saber se é um Pro', e não 'não é um Pro'. Quem chama passa o HID_NAME como 2º argumento e eu decido"
        fi
        _recusar "o nome declarado ('${NOME}') não é de um Pro Controller — o sniff fica como está"
    fi
fi

if ! command -v hcitool >/dev/null 2>&1; then
    _registrar "no-sniff na borda de ${MAC} NÃO aplicado: o 'hcitool' foi depreciado pelo BlueZ e não está nesta máquina (pacote bluez-deprecated / bluez-deprecated-tools), e nenhuma ferramenta viva escreve link policy — o Pro genuíno vai cair sob carga até isso ser resolvido"
    exit 0
fi

for _ in 1 2 3; do
    if hcitool lp "${MAC}" RSWITCH >/dev/null 2>&1; then
        _registrar "no-sniff aplicado na borda de conexão de ${MAC} (Pro genuíno)"
        exit 0
    fi
    sleep 0.2
done

_registrar "no-sniff na borda falhou para ${MAC}; a vigia tenta no próximo tick"
exit 0
