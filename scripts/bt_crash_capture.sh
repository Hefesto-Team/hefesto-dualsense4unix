#!/usr/bin/env bash
# bt_crash_capture.sh — captura forense do PRÓXIMO crash do bluetoothd.
# OPT-IN e temporário (sprint 2026-07-21-sprint-pesquisa-bluez-estabilidade.md,
# camada 3): o install NUNCA liga isto; liga-se à mão numa janela de
# diagnóstico e desliga-se depois.
#
# Por que existe: a assinatura `malloc(): unaligned fastbin chunk detected 2`
# do bluetoothd é INÉDITA publicamente e nunca foi capturada aqui — o
# core_pattern do Pop!_OS aponta para o apport, que IGNORA pacote fora da
# distro (nosso bluez é ~hefesto), então todos os crashes até hoje morreram
# sem dump. Sem core file não há bisect nem report upstream.
#
# O que --on faz (e --off desfaz simetricamente):
#   1. /etc/sysctl.d/99-hefesto-bt-coredump.conf → core_pattern para o
#      systemd-coredump. CUSTO: core_pattern é GLOBAL do kernel (não há como
#      escopar por serviço) — por isso é toggle, nunca default.
#   2. /etc/systemd/system/bluetooth.service.d/90-hefesto-debug.conf →
#      LimitCORE=infinity + MALLOC_CHECK_=3 + MALLOC_PERTURB_=165 (aborta
#      LIMPO no ponto da corrupção em vez de espalhar; ~30% de overhead de
#      malloc — aceitável no bluetoothd por janela curta, não para sempre).
#   3. daemon-reload. O drop-in só arma no PRÓXIMO restart do bluetoothd —
#      este script NÃO reinicia o serviço (decisão do humano: derrubaria os
#      controles BT conectados).
#
# Uso: bt_crash_capture.sh --on | --off | --status
set -euo pipefail

SYSCTL_FILE=/etc/sysctl.d/99-hefesto-bt-coredump.conf
DROPIN_DIR=/etc/systemd/system/bluetooth.service.d
DROPIN_FILE="${DROPIN_DIR}/90-hefesto-debug.conf"

if [[ "$(id -u)" -ne 0 ]]; then
    printf 'bt_crash_capture.sh: requer root\n' >&2
    exit 1
fi

status() {
    printf 'sysctl coredump : %s\n' "$([[ -f "${SYSCTL_FILE}" ]] && echo LIGADO || echo desligado)"
    printf 'drop-in debug   : %s\n' "$([[ -f "${DROPIN_FILE}" ]] && echo LIGADO || echo desligado)"
    printf 'core_pattern    : %s\n' "$(cat /proc/sys/kernel/core_pattern 2>/dev/null | head -c 80)"
}

case "${1:-}" in
    --on)
        cat > "${SYSCTL_FILE}" <<'EOF'
# hefesto-dualsense4unix — captura forense TEMPORÁRIA do crash do bluetoothd.
# core_pattern é global do kernel; desligar com: bt_crash_capture.sh --off
kernel.core_pattern=|/usr/lib/systemd/systemd-coredump %P %u %g %s %t %c %h
EOF
        sysctl --system >/dev/null 2>&1 || sysctl -p "${SYSCTL_FILE}" >/dev/null
        install -d -m 755 "${DROPIN_DIR}"
        cat > "${DROPIN_FILE}" <<'EOF'
# hefesto-dualsense4unix — janela de diagnóstico do crash de heap (TEMPORÁRIO).
# MALLOC_CHECK_=3 aborta limpo no ponto da corrupção; PERTURB_ suja memória
# liberada para transformar use-after-free silencioso em crash visível.
[Service]
LimitCORE=infinity
Environment=MALLOC_CHECK_=3
Environment=MALLOC_PERTURB_=165
EOF
        systemctl daemon-reload
        printf 'captura LIGADA. Arma no próximo restart do bluetoothd (faça quando os controles estiverem desconectados):\n'
        printf '  sudo systemctl restart bluetooth.service\n'
        printf 'depois do crash: coredumpctl list bluetoothd ; coredumpctl gdb bluetoothd\n'
        printf 'ao terminar a janela: sudo %s --off\n' "$0"
        ;;
    --off)
        rm -f "${SYSCTL_FILE}" "${DROPIN_FILE}"
        sysctl --system >/dev/null 2>&1 || true
        systemctl daemon-reload
        printf 'captura DESLIGADA (core_pattern devolvido ao default do sistema via sysctl --system).\n'
        printf 'o MALLOC_CHECK_ sai do bluetoothd no próximo restart do serviço.\n'
        ;;
    --status) status ;;
    *) printf 'uso: %s --on | --off | --status\n' "$0" >&2; exit 1 ;;
esac
