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
#: RADIO-ABERTO-01/E8: unit transitória que fecha a janela sozinha. Nome fixo
#: para ser idempotente — ligar duas vezes não acumula timers.
AUTO_OFF_UNIT=hefesto-bt-crash-capture-off

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
        # RADIO-ABERTO-01/E8 (05/08/2026): a janela arma o PRÓPRIO desligamento.
        # `core_pattern` é global do kernel, e até aqui o `--off` dependia só da
        # memória de quem ligou — uma janela de diagnóstico esquecida aberta
        # deixa a máquina gravando core de TODO processo que morrer, e um core
        # do bluetoothd contém todas as LinkKeys, LTKs e IRKs residentes.
        _HORAS="${HEFESTO_BT_CAPTURE_HORAS:-8}"
        if command -v systemd-run >/dev/null 2>&1; then
            systemctl stop "${AUTO_OFF_UNIT}.timer" >/dev/null 2>&1 || true
            if systemd-run --on-active="${_HORAS}h" --unit="${AUTO_OFF_UNIT}" \
                    --description="hefesto: fecha a janela de captura de core do bluetoothd" \
                    "$(readlink -f "$0")" --off >/dev/null 2>&1; then
                printf 'desligamento automático armado para daqui a %sh (unit %s).\n' \
                    "${_HORAS}" "${AUTO_OFF_UNIT}"
            else
                printf 'AVISO: não consegui armar o desligamento automático — anote para rodar --off.\n' >&2
            fi
        else
            printf 'AVISO: sem systemd-run; o --off depende de você lembrar.\n' >&2
        fi
        printf 'captura LIGADA. Arma no próximo restart do bluetoothd (faça quando os controles estiverem desconectados):\n'
        printf '  sudo systemctl restart bluetooth.service\n'
        printf 'depois do crash: coredumpctl list bluetoothd ; coredumpctl info bluetoothd\n'
        printf 'ao terminar a janela: sudo %s --off\n' "$0"
        printf '\n'
        printf 'POLÍTICA (RADIO-ABERTO-01/E7): o core do bluetoothd NUNCA sai desta máquina.\n'
        printf 'Ele contém todas as LinkKeys, LTKs e IRKs residentes, mais os MACs e nomes\n'
        printf 'de todos os aparelhos da casa. Para relatar upstream vai o BACKTRACE\n'
        printf '(coredumpctl info), nunca o core. Ver docs/process/POLITICA-core-nunca-sai-da-maquina.md\n'
        ;;
    --off)
        rm -f "${SYSCTL_FILE}" "${DROPIN_FILE}"
        sysctl --system >/dev/null 2>&1 || true
        # E8: desarma o timer se o --off veio antes da hora (gesto manual dela).
        systemctl stop "${AUTO_OFF_UNIT}.timer" >/dev/null 2>&1 || true
        systemctl reset-failed "${AUTO_OFF_UNIT}.service" >/dev/null 2>&1 || true
        systemctl daemon-reload
        printf 'captura DESLIGADA (core_pattern devolvido ao default do sistema via sysctl --system).\n'
        printf 'o MALLOC_CHECK_ sai do bluetoothd no próximo restart do serviço.\n'
        ;;
    --status) status ;;
    *) printf 'uso: %s --on | --off | --status\n' "$0" >&2; exit 1 ;;
esac
