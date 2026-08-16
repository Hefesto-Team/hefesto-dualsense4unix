#!/usr/bin/env bash
# bt_nosniff_now.sh — tira UM link BR/EDR do SNIFF no instante em que ele nasce.
#
# POR QUE EXISTE (BT-SNIFF-BORDA-01, 24/07)
#
# O `bt_active_mode.sh` já aplica o no-sniff por-conexão no Pro Controller
# genuíno, mas só a cada tick da vigia — 2 minutos. O comentário dele dizia que
# isso "cobre reconexão sem precisar caçar a borda"; a premissa caiu ao vivo: o
# Pro voltou a desconectar, e a janela entre o connect e o primeiro tick é
# exatamente onde o link negocia sniff e cai sob carga.
#
# O desfecho já estava previsto no próprio commit que criou o split por-OUI:
#
#   "Fica em aberto (gate humano): confirmar que o Pro aguenta uma sessão de 4
#    jogadores sob carga real com o no-sniff aplicado por-conexão em vez de
#    global. Se cair, o aprendizado é que ele precisa do no-sniff já DURANTE o
#    connect."
#
# Este script é esse "durante o connect": o udev o dispara na borda de criação
# do device HID (`82-nintendo-pro-nosniff.rules`), com o MAC vindo do HID_UNIQ.
#
# O QUE ELE NÃO FAZ: mexer no default do adaptador. O adaptador tem de MANTER o
# SNIFF permitido — o 8BitDo clone precisa dele para probar, e negá-lo
# globalmente mata a probe com `ret=-110` (medido 23/07). Aqui é por-link.
#
# Reverter um link: `hcitool lp <MAC> RSWITCH,HOLD,SNIFF,PARK`.
set -euo pipefail

MAC="${1:-}"
if [[ -z "${MAC}" ]]; then
    printf 'bt_nosniff_now.sh: uso: %s <MAC>\n' "${0##*/}" >&2
    exit 2
fi

#: OUI do Nintendo Pro Controller GENUÍNO — o ÚNICO que recebe o no-sniff.
#: Mesma fonte da verdade do `OUI_NINTENDO_REAL` em `bt_active_mode.sh` e do
#: `NINTENDO_REAL_OUI` do `external_identity.py`: sempre a OUI, nunca VID/PID
#: (o clone 8BitDo se anuncia com os mesmos VID/PID do Pro).
OUI_NINTENDO_REAL="E0:F6:B5"

# DIÁRIO-QUE-NAO-MENTE-01 (15/08/2026): vazio = journal (produção); caminho =
# arquivo; `none` = nada. Existe porque a suíte roda estes scripts DE VERDADE e
# sem isto grava, no journal da máquina dela, linhas que descrevem eventos que
# nunca aconteceram. Motivo completo no cabeçalho do bt_bonds_autorestore.sh.
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

if [[ "${MAC^^}" != "${OUI_NINTENDO_REAL}"* ]]; then
    exit 0  # não é o Pro genuíno: o sniff fica como está
fi

command -v hcitool >/dev/null 2>&1 || exit 0

# O device HID pode nascer alguns milissegundos antes de o link aceitar mudança
# de policy. Três tentativas curtas cobrem isso sem segurar o udev: se ainda
# assim falhar, a vigia de 2 min aplica no próximo tick (degradação, não perda).
for _ in 1 2 3; do
    if hcitool lp "${MAC}" RSWITCH >/dev/null 2>&1; then
        _registrar "no-sniff aplicado na borda de conexão de ${MAC} (Pro genuíno)"
        exit 0
    fi
    sleep 0.2
done

_registrar "no-sniff na borda falhou para ${MAC}; a vigia tenta no próximo tick"
exit 0
