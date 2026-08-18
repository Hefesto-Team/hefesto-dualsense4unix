#!/usr/bin/env bash
# storm_loadtest.sh — teste de carga decisivo do storm -71 do DualSense.
#
# O storm é gatilhado por CARGA (jogo/Steam), não por ociosidade — então o teste
# real é: controle plugado + carga + monitorar `error -71`/disconnect no kernel.
# Este script versiona o "teste pós-reboot §6.5" que era manual.
#
# Uso:
#   scripts/storm_loadtest.sh [SEGUNDOS]   (default 180)
#
# Faz:
#   1. Confirma o DualSense plugado (USB ou já enumerado).
#   2. Registra a contagem de `-71` baseline (dmesg).
#   3. Sobe carga sintética (stress-ng --cpu, se disponível) — OU peça para abrir
#      um jogo na Steam em paralelo (a carga real da GPU/CPU é o gatilho).
#   4. Monitora o kernel por SEGUNDOS, contando -71/disconnect/queda de velocidade.
#   5. Veredito: PASSOU (0 novos sinais) ou STORM (controle instável).
#
# Não mexe em porta/cabo/BIOS (resolvido). Foca em validar a config de software.
set -uo pipefail

DURATION="${1:-180}"
VID="054c"  # Sony

log() { printf '\033[1;35m[storm-test]\033[0m %s\n' "$*"; }

need_sudo() {
    if sudo -n true 2>/dev/null; then SUDO="sudo";
    elif [ "$(id -u)" -eq 0 ]; then SUDO="";
    else SUDO="sudo"; log "vou pedir a senha do sudo para ler o dmesg do kernel"; fi
}

count_71() { $SUDO dmesg 2>/dev/null | grep -ciE 'error -71|not accepting address|unable to enumerate'; }

dualsense_present() { lsusb 2>/dev/null | grep -qiE "${VID}:0ce6|${VID}:0df2"; }

need_sudo

if ! dualsense_present; then
    log "DualSense NÃO está plugado/enumerado (lsusb sem ${VID}). Plugue o controle e rode de novo."
    log "Se ele caiu num storm e sumiu do barramento: desplugue e replugue (de preferência numa porta traseira)."
    exit 2
fi

BASE="$(count_71)"
log "DualSense presente. Baseline de sinais -71 neste boot: ${BASE}"
log "Monitorando por ${DURATION}s. ABRA UM JOGO NA STEAM AGORA (a carga é o gatilho do storm)."

# Carga sintética opcional (complementa o jogo). stress-ng se houver.
STRESS_PID=""
if command -v stress-ng >/dev/null 2>&1; then
    NPROC="$(nproc 2>/dev/null || echo 4)"
    log "subindo stress-ng --cpu ${NPROC} por ${DURATION}s (carga sintética de apoio)"
    stress-ng --cpu "${NPROC}" --timeout "${DURATION}s" >/dev/null 2>&1 &
    STRESS_PID=$!
else
    log "stress-ng ausente — confie na carga do jogo. (instale com: sudo apt install stress-ng)"
fi

# Monitor do kernel em tempo real (não-bloqueante): conta sinais novos.
DEADLINE=$(( $(date +%s) + DURATION ))
LAST="$BASE"
STORM=0
while [ "$(date +%s)" -lt "$DEADLINE" ]; do
    NOW="$(count_71)"
    if [ "$NOW" -gt "$LAST" ]; then
        DELTA=$(( NOW - LAST ))
        log "  +${DELTA} sinais -71 (total ${NOW}) — storm em andamento!"
        $SUDO dmesg 2>/dev/null | grep -iE 'usb .*-71|disconnect|full-speed' | tail -3 | sed 's/^/      /'
        STORM=1
        LAST="$NOW"
    fi
    if ! dualsense_present; then
        log "  DualSense SUMIU do barramento durante a carga — dropout confirmado."
        STORM=1
        break
    fi
    sleep 3
done

[ -n "$STRESS_PID" ] && kill "$STRESS_PID" 2>/dev/null || true

FINAL="$(count_71)"
NEW=$(( FINAL - BASE ))
echo
if [ "$STORM" -eq 0 ] && [ "$NEW" -eq 0 ]; then
    log " PASSOU — 0 novos sinais -71 em ${DURATION}s sob carga, controle estável. Config de software OK."
    exit 0
else
    log " STORM — ${NEW} novos sinais -71 / dropout sob carga. A config de software NÃO segurou."
    log "   Próximos passos (software, NÃO hardware): rodar scripts/doctor.sh; conferir drop-ins 52/53;"
    log "   considerar o quirk usbcore.quirks=054c:0ce6:gn,054c:0df2:gn (g=DELAY_INIT, n=DELAY_CTRL_MSG)"
    log "   como próxima cartada — instale com: scripts/install_usb_quirk.sh (PRESERVA o áudio do DualSense)."
    exit 1
fi
