#!/usr/bin/env bash
# doctor.sh — diagnóstico de saúde do Hefesto - Dualsense4Unix.
#
# Verifica daemon, serviço, socket IPC, regras udev (incluindo a consistência do
# nome de unit do hotplug), uinput, a gravabilidade do nó de LED do DualSense
# físico (cor por-controle via sysfs, regra 77), applet COSMIC (.desktop + ícone
# resolvível), o detector de janela do autoswitch (perfil-por-jogo), o sequestro
# do microfone pelo WirePlumber e o alcance do controle; reconhece também, no
# journal do kernel, a assinatura de morte por Bluetooth do 8BitDo em modo
# Switch (cascata do hid-nintendo — informativo, não gerenciamos o controle).
# Saída PASS/FAIL/WARN por item.
# Marcadores ASCII (compat sanitizer de anonimato).
#
# Uso: scripts/doctor.sh [--fix] [--quiet] [--watch-dropout] [--suggest-port]
#   --fix             aplica correções seguras: reaplica udev e instala/reseta o
#                     fix de áudio do WirePlumber.
#   --quiet           só mostra FAIL/WARN.
#   --watch-dropout   vigia o journal do kernel e bloqueia até o primeiro sintoma
#                     de dropout USB (-71); imprime a linha e sai. (Ctrl-C para sair.)
#   --suggest-port    diz em qual controlador USB o DualSense está (diagnóstico
#                     NEUTRO). O storm -71 é port-independente (A/B comprovado):
#                     o fix real é o quirk usbcore.quirks=...gn,gn (alavanca A,
#                     preserva áudio) OU a regra 75 authorized=0 (alavanca B),
#                     não trocar de porta/Bluetooth.
#
# Exit code != 0 se houver qualquer FAIL. FEAT-DOCTOR-HEALTHCHECK-01,
# FEAT-DOCTOR-USB-DROPOUT-DIAGNOSTIC-01.

set -uo pipefail   # sem -e de propósito: cada check trata a própria falha.

readonly ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly APP_ID="hefesto-dualsense4unix"
readonly HOTPLUG_UNIT="hefesto-dualsense4unix-gui-hotplug.service"
readonly APPLET_DESKTOP="/usr/share/applications/com.vitoriamaria.HefestoDualsense4Unix.desktop"

DO_FIX=0
QUIET=0
WATCH_DROPOUT=0
SUGGEST_PORT=0
for arg in "$@"; do
    case "$arg" in
        --fix)            DO_FIX=1 ;;
        --quiet)          QUIET=1 ;;
        --watch-dropout)  WATCH_DROPOUT=1 ;;
        --suggest-port)   SUGGEST_PORT=1 ;;
        *) printf '[doctor] aviso: argumento desconhecido: %s\n' "$arg" ;;
    esac
done

FAILS=0
WARNS=0
pass() { [[ "${QUIET}" -eq 1 ]] || printf '[ OK ] %s\n' "$*"; }
fail() { printf '[FAIL] %s\n' "$*"; FAILS=$((FAILS + 1)); }
warn() { printf '[WARN] %s\n' "$*"; WARNS=$((WARNS + 1)); }
info() { [[ "${QUIET}" -eq 1 ]] || printf '       %s\n' "$*"; }
hdr()  { [[ "${QUIET}" -eq 1 ]] || printf '\n== %s ==\n' "$*"; }

runtime_socket() {
    printf '%s/%s/%s.sock' "${XDG_RUNTIME_DIR:-/run/user/$(id -u)}" "${APP_ID}" "${APP_ID}"
}

check_daemon_installed() {
    local found
    found="$(command -v hefesto-dualsense4unix 2>/dev/null || true)"
    [[ -z "${found}" && -e "${HOME}/.local/bin/hefesto-dualsense4unix" ]] && found="${HOME}/.local/bin/hefesto-dualsense4unix"
    [[ -z "${found}" && -e /usr/bin/hefesto-dualsense4unix ]] && found="/usr/bin/hefesto-dualsense4unix"
    if [[ -n "${found}" ]]; then
        pass "daemon/CLI instalado (${found})"
    else
        fail "CLI hefesto-dualsense4unix não encontrado — instale: ./install.sh --native"
    fi
}

check_service() {
    command -v systemctl >/dev/null 2>&1 || { warn "systemctl ausente — não checo o serviço"; return; }
    local state
    state="$(systemctl --user is-active "${APP_ID}.service" 2>/dev/null || true)"
    if [[ "${state}" == "active" ]]; then
        pass "serviço ${APP_ID}.service ativo"
    elif systemctl --user cat "${APP_ID}.service" >/dev/null 2>&1; then
        warn "serviço instalado mas ${state:-inativo} (start: systemctl --user start ${APP_ID}.service, ou abra a GUI)"
    else
        warn "serviço não instalado (autostart é opt-in: ./install.sh --enable-autostart)"
    fi
}

check_socket() {
    local sock; sock="$(runtime_socket)"
    if [[ -S "${sock}" ]]; then
        pass "socket IPC presente"
    else
        warn "socket IPC ausente (daemon parado?): ${sock}"
    fi
}

check_udev() {
    # DOCTOR-UDEV-CANONICAL-FIX-01 + COR-06/STATUS-07: o conjunto CANÔNICO é o
    # que o install_udev.sh põe SEM FLAG: 70, 71-uhid, 71-uinput, 72, 76
    # (touchpad-ignore), 77 (LEDs graváveis) e 78 (motion fora do joystick).
    # A ÚNICA opt-in é a 75 (audio-off, --disable-usb-audio) — fora da contagem.
    # As regras 73/74 (hotplug-GUI) foram REMOVIDAS por alimentarem a
    # re-enumeração do storm -71 (install_udev.sh faz `rm -f`). Antes o doctor
    # exigia 5 (70-74) e reportava "3/5 — faltam 73 74" PARA SEMPRE após um
    # install limpo (falso-negativo permanente); depois chamou a 76 de opt-in
    # (falso: é default desde o install) e ignorou 77/78 — sem a 77 o nó de LED
    # não é gravável e a cor por-controle degrada p/ hidraw em silêncio.
    # Regra da casa: um item no install = um check no doctor.
    local r found=0 missing=""
    local rules=(70-ps5-controller.rules 71-uhid.rules 71-uinput.rules
                 72-ps5-controller-autosuspend.rules
                 76-dualsense-touchpad-libinput-ignore.rules
                 77-dualsense-leds.rules
                 78-dualsense-motion-not-joystick.rules)
    local total=${#rules[@]}
    for r in "${rules[@]}"; do
        if [[ -e "/etc/udev/rules.d/${r}" || -e "/usr/lib/udev/rules.d/${r}" ]]; then
            found=$((found + 1))
        else
            missing+=" ${r}"
        fi
    done
    if [[ "${found}" -eq "${total}" ]]; then
        pass "${total} regras udev canônicas presentes (70/71-uhid/71-uinput/72/76/77/78)"
    elif [[ "${found}" -eq 0 ]]; then
        fail "nenhuma regra udev instalada — rode: sudo bash scripts/install_udev.sh"
    else
        warn "regras udev incompletas (${found}/${total}) — faltam:${missing} — rode: sudo bash scripts/install_udev.sh"
    fi
    # 73/74 (hotplug-GUI) foram DESCONTINUADAS (amplificavam o storm -71). Se
    # sobraram de uma instalação antiga, avisa para limpar.
    for r in 73-ps5-controller-hotplug.rules 74-ps5-controller-hotplug-bt.rules; do
        if [[ -e "/etc/udev/rules.d/${r}" || -e "/usr/lib/udev/rules.d/${r}" ]]; then
            warn "${r}: regra descontinuada presente (amplificava o storm -71) — remova: sudo bash scripts/install_udev.sh"
        fi
    done
}

# True (0) se o snd-usb-audio AINDA está bindado em alguma interface de áudio
# (bInterfaceClass==01) de um DualSense (VID 054c). Lê os nós de interface USB em
# /sys e segue o symlink `driver`. Usado para validar se a regra 75 pegou.
dualsense_audio_bound() {
    local iface base vid cls drv
    for iface in /sys/bus/usb/devices/*:*.*; do
        [[ -r "${iface}/bInterfaceClass" ]] || continue
        cls="$(cat "${iface}/bInterfaceClass" 2>/dev/null)"
        [[ "${cls}" == "01" ]] || continue
        base="${iface%:*}"   # /sys/bus/usb/devices/3-2:1.0 -> /sys/bus/usb/devices/3-2
        vid="$(cat "${base}/idVendor" 2>/dev/null)"
        [[ "${vid}" == "054c" ]] || continue
        drv="$(basename "$(readlink -f "${iface}/driver" 2>/dev/null)" 2>/dev/null)"
        [[ "${drv}" == "snd-usb-audio" ]] && return 0
    done
    return 1
}

# FEAT-DSX-DEFINITIVE-FIX-01 §7.5: a regra 75 (OPT-IN) desliga o áudio USB do
# DualSense (authorized=0 + unbind do snd-usb-audio) para matar o gatilho do
# storm -71. Aqui validamos que, SE instalada, ela realmente pegou. Não alarmamos
# quem QUER o mic do DualSense (HEFESTO_DUALSENSE4UNIX_DUALSENSE_MIC_INTENDED=1)
# nem o caminho padrão (75 ausente = áudio preservado).
check_usb_audio_off() {
    local rule75=""
    if [[ -e /etc/udev/rules.d/75-ps5-controller-disable-usb-audio.rules ]]; then
        rule75=/etc/udev/rules.d/75-ps5-controller-disable-usb-audio.rules
    elif [[ -e /usr/lib/udev/rules.d/75-ps5-controller-disable-usb-audio.rules ]]; then
        rule75=/usr/lib/udev/rules.d/75-ps5-controller-disable-usb-audio.rules
    fi

    local mic_intended=0
    case "${HEFESTO_DUALSENSE4UNIX_DUALSENSE_MIC_INTENDED:-}" in
        1|true|yes|TRUE|YES) mic_intended=1 ;;
    esac

    # Caminho padrão: regra opt-in não instalada → áudio preservado, sem alarme.
    [[ -z "${rule75}" ]] && return

    if [[ "${mic_intended}" -eq 1 ]]; then
        # Config contraditória, mas a usuária pediu áudio — não alarmar (info).
        info "regra 75 (áudio USB off) instalada, mas DUALSENSE_MIC_INTENDED=1 pede o mic — contraditório; para ter o mic remova a 75 (uninstall) ou reinstale sem --disable-usb-audio"
        return
    fi

    # Regra instalada e mic não desejado: o áudio USB deve estar desligado.
    if dualsense_audio_bound; then
        warn "regra 75 instalada mas snd-usb-audio ainda bindado no áudio do DualSense — a regra não pegou; replugue o controle (ou: sudo bash scripts/install_udev.sh --disable-usb-audio)"
    elif command -v lsusb >/dev/null 2>&1 && lsusb 2>/dev/null | grep -qiE '054c'; then
        pass "regra 75 ativa — áudio USB do DualSense desligado (sem snd-usb-audio nas interfaces de áudio)"
    else
        info "regra 75 instalada; DualSense não conectado via USB agora — replugue para validar o desligamento do áudio"
    fi
}

# DOCTOR-UINPUT-ACESSO-01: existir NÃO basta. O nó nasce root-only e quem o torna
# usável é a regra udev (uaccess). Checar só `-e` dava PASS com o daemon incapaz de
# criar vpad nenhum — falso-positivo justamente no caso que o install passou a
# cobrir (`udevadm trigger --subsystem-match=misc`, sem o qual a regra só valia no
# próximo boot).
_check_node_gravavel() {
    local node="$1" modulo="$2" para_que="$3"
    if [[ ! -e "${node}" ]]; then
        fail "${node} ausente — rode: sudo modprobe ${modulo} (ou reinstale as regras udev)"
        return
    fi
    if [[ -w "${node}" ]]; then
        pass "${node} presente e gravável (${para_que})"
    else
        fail "${node} existe mas SEM permissão para o seu usuário — ${para_que} não vai funcionar. Rode: sudo bash scripts/install_udev.sh"
    fi
}

check_uinput() {
    _check_node_gravavel /dev/uinput uinput "gamepad virtual"
}

# SPRINT-UHID-VPAD-01: sem /dev/uhid o gamepad virtual cai no uinput, que não tem
# hidraw — e aí a vibração não funciona com a máscara DualSense. É degradação, não
# quebra: warn, nunca fail.
check_uhid() {
    if [[ ! -e /dev/uhid ]]; then
        warn "/dev/uhid ausente — o controle virtual funciona, mas a vibração só vale com a máscara Xbox 360. Rode: sudo modprobe uhid"
        return
    fi
    if [[ -w /dev/uhid ]]; then
        pass "/dev/uhid presente e gravável (vibração nas duas máscaras)"
    else
        warn "/dev/uhid existe mas SEM permissão para o seu usuário — a vibração só vai funcionar com a máscara Xbox 360. Rode: sudo bash scripts/install_udev.sh"
    fi
}

# O hid_playstation é quem entrega lightbar e LED de jogador pelo sysfs (regra 77) e
# quem faz o gamepad virtual virar um DualSense de verdade (uhid). Sem ele o daemon
# funciona, mas essas features somem — por isso warn, não fail.
check_hid_playstation() {
    if lsmod 2>/dev/null | grep -q '^hid_playstation'; then
        pass "driver hid_playstation carregado (cor da luz e LED de jogador)"
    elif [[ -d /sys/module/hid_playstation ]]; then
        pass "driver hid_playstation ativo (embutido no kernel)"
    else
        warn "driver hid_playstation não carregado — cor da luz e LED de jogador podem não funcionar. Kernel muito antigo? Rode: sudo modprobe hid_playstation"
    fi
}

# COR-06/STATUS-07: probe READ-ONLY da gravabilidade do LED do DualSense FÍSICO.
# A regra 77 (default no install) dá escrita ao usuário nos nós de LED do kernel;
# sem ela o daemon só alcança a cor por hidraw — que em BT sofre EIO — e a cor
# por-controle degrada em silêncio (lightbar_source=="desired"). Só `test -w`:
# este check NUNCA escreve no nó. O vpad uhid do daemon também cria um nó
# rgb:indicator, mas o realpath do device dele vive em /devices/virtual/ e NÃO
# serve de alvo (filtrado). Sem DualSense físico conectado: pula sem falhar.
check_led_sysfs_gravavel() {
    local node dev_real nome ok_nodes="" bad_nodes=""
    for node in /sys/class/leds/*rgb:indicator*; do
        [[ -e "${node}" ]] || continue
        dev_real="$(readlink -f "${node}/device" 2>/dev/null || true)"
        [[ -z "${dev_real}" ]] && dev_real="$(readlink -f "${node}" 2>/dev/null || true)"
        [[ "${dev_real}" == */devices/virtual/* ]] && continue   # vpad do daemon
        [[ -e "${node}/multi_intensity" ]] || continue
        nome="${node##*/}"
        if [[ -w "${node}/multi_intensity" ]]; then
            ok_nodes+=" ${nome}"
        else
            bad_nodes+=" ${nome}"
        fi
    done
    if [[ -n "${bad_nodes}" ]]; then
        warn "nó de LED do DualSense físico SEM escrita p/ o seu usuário:${bad_nodes} — a cor por-controle (sobretudo em BT) depende do sysfs; a regra 77 dá a permissão: sudo bash scripts/install_udev.sh (e reconecte o controle)"
    elif [[ -n "${ok_nodes}" ]]; then
        pass "nó de LED do DualSense físico gravável pelo usuário (${ok_nodes# }) — cor por-controle via sysfs OK (regra 77 valendo)"
    else
        info "sem DualSense físico com nó de LED agora (só o controle virtual, ou nenhum) — pulo o teste de gravabilidade; conecte o controle p/ validar a regra 77"
    fi
}

# FEAT-DSX-DEFINITIVE-FIX-01 §7.5 (Opção D): o quirk de boot
# usbcore.quirks=054c:0ce6:gn,054c:0df2:gn é a alavanca do storm -71 que PRESERVA
# o áudio do DualSense (ALTERNATIVA à regra 75, que desliga o áudio). É um
# PARÂMETRO DE CMDLINE do kernel (NÃO é regra udev) e OPT-IN — por isso este check
# é puramente informativo: NUNCA fail nem warn. Reporta ativo (/proc/cmdline),
# agendado (config do bootloader), runtime (sysfs) ou ausente.
check_usb_quirk() {
    local marker="054c:0ce6:gn"
    local active=0 scheduled=0 runtime=0
    grep -q "${marker}" /proc/cmdline 2>/dev/null && active=1
    { [[ -r /etc/kernelstub/configuration ]] && grep -q "${marker}" /etc/kernelstub/configuration 2>/dev/null; } && scheduled=1
    { [[ -r /etc/default/grub ]] && grep -q "${marker}" /etc/default/grub 2>/dev/null; } && scheduled=1
    { [[ -r /sys/module/usbcore/parameters/quirks ]] && grep -q "${marker}" /sys/module/usbcore/parameters/quirks 2>/dev/null; } && runtime=1

    if [[ "${active}" -eq 1 ]]; then
        info "quirk de áudio USB ATIVO neste boot (usbcore.quirks=...gn) — storm -71 mitigado PRESERVANDO o áudio do DualSense"
    elif [[ "${scheduled}" -eq 1 ]]; then
        info "quirk de áudio USB agendado p/ o próximo boot (config do bootloader) — reinicie para valer; status: scripts/install_usb_quirk.sh --status"
    elif [[ "${runtime}" -eq 1 ]]; then
        info "quirk de áudio USB armado em runtime (sysfs) — vale no próximo replug; para persistir no cmdline: scripts/install_usb_quirk.sh"
    else
        info "quirk de áudio USB ausente (opt-in) — alternativa que PRESERVA o áudio: scripts/install_usb_quirk.sh (ou regra 75 p/ áudio-off). Use uma OU outra."
    fi
    if [[ "${active}" -eq 1 || "${scheduled}" -eq 1 || "${runtime}" -eq 1 ]]; then
        info "  caveat: o quirk preserva o áudio no nível do KERNEL (sem storm); com os WP 52/53 o nó segue suprimido no PipeWire até removê-los ou definir DUALSENSE_MIC_INTENDED=1"
    fi
}

# CROSS-CHECK do storm -71: a regra 75 (áudio-off) e o quirk (preserva-áudio)
# são alavancas ALTERNATIVAS do MESMO storm — instalar AS DUAS é contraditório:
# o quirk espaça a rajada de control-transfers para PRESERVAR o áudio, mas a
# regra 75 desliga esse mesmo áudio. Se ambas estiverem presentes (75 instalada
# E quirk ativo/agendado/runtime), avisamos para escolher UMA. Não substitui
# check_usb_audio_off nem check_usb_quirk; só cruza os dois sinais com warn().
check_usb_storm_config_conflict() {
    local rule75=0
    if [[ -e /etc/udev/rules.d/75-ps5-controller-disable-usb-audio.rules \
          || -e /usr/lib/udev/rules.d/75-ps5-controller-disable-usb-audio.rules ]]; then
        rule75=1
    fi

    local marker="054c:0ce6:gn" quirk=0
    grep -q "${marker}" /proc/cmdline 2>/dev/null && quirk=1
    { [[ -r /etc/kernelstub/configuration ]] && grep -q "${marker}" /etc/kernelstub/configuration 2>/dev/null; } && quirk=1
    { [[ -r /etc/default/grub ]] && grep -q "${marker}" /etc/default/grub 2>/dev/null; } && quirk=1
    { [[ -r /sys/module/usbcore/parameters/quirks ]] && grep -q "${marker}" /sys/module/usbcore/parameters/quirks 2>/dev/null; } && quirk=1

    if [[ "${rule75}" -eq 1 && "${quirk}" -eq 1 ]]; then
        warn "config contraditória: o quirk (usbcore.quirks=...gn) PRESERVA o áudio do DualSense, mas a regra 75 o DESLIGA — escolha UMA. Para manter o áudio: remova a 75 (uninstall ou reinstale sem --disable-usb-audio). Para áudio-off: remova o quirk (scripts/install_usb_quirk.sh --remove)."
    fi
}

check_applet() {
    if [[ ! -e "${APPLET_DESKTOP}" ]]; then
        warn "applet COSMIC não instalado (.desktop ausente) — opcional: ./install.sh --enable-cosmic-applet"
        return
    fi
    if grep -q '^X-CosmicApplet=true' "${APPLET_DESKTOP}"; then
        pass "applet .desktop com X-CosmicApplet=true"
    else
        fail "applet .desktop sem X-CosmicApplet=true"
    fi
    if grep -q '^X-HostWaylandDisplay=true' "${APPLET_DESKTOP}"; then
        pass "applet .desktop com X-HostWaylandDisplay=true"
    else
        warn "applet .desktop sem X-HostWaylandDisplay=true — recomendado p/ falar com o sistema (reinstale o applet)"
    fi
    local icon
    icon="$(sed -n 's/^Icon=//p' "${APPLET_DESKTOP}" | head -1)"
    if [[ -n "${icon}" ]] && ls /usr/share/icons/hicolor/*/apps/"${icon}".* >/dev/null 2>&1; then
        pass "ícone do applet resolvível (${icon})"
    else
        fail "ícone do applet NÃO resolvível (Icon=${icon}) — falta o arquivo correspondente"
    fi
    if [[ -e "/usr/share/icons/hicolor/256x256/apps/com.vitoriamaria.HefestoDualsense4Unix.png" ]]; then
        pass "ícone PNG 256x256 do applet presente"
    else
        warn "ícone PNG 256x256 do applet ausente — a lista de Miniaplicativos pode não mostrar o ícone colorido"
    fi
    if command -v desktop-file-validate >/dev/null 2>&1; then
        if desktop-file-validate "${APPLET_DESKTOP}" >/dev/null 2>&1; then
            pass "desktop-file-validate sem erros"
        else
            info "desktop-file-validate emitiu avisos (não-fatal)"
        fi
    fi
}

# BUG-WIREPLUMBER-FIX-FALSE-SUCCESS-01 / ADR-019: checa o microfone ATIVO
# (pactl get-default-source; fallback ao '*' do wpctl), não o `configured`.
# 3 estados: OK (ativo != DualSense); WARN (DualSense por ser a única fonte);
# FAIL (DualSense ativo COM outra fonte available — drop-in não pegou).
check_wireplumber_source() {
    local cur=""
    if command -v pactl >/dev/null 2>&1; then
        cur="$(pactl get-default-source 2>/dev/null || true)"
    fi
    if [[ -z "${cur}" ]] && command -v wpctl >/dev/null 2>&1; then
        cur="$(wpctl status 2>/dev/null | awk '
            /Sources:/{s=1;next} s&&(/Filters:/||/Sinks:/||/Streams:/||/Video/){s=0}
            s&&/\*/{sub(/.*\*[[:space:]]+[0-9]+\.[[:space:]]*/,"");print;exit}')"
    fi
    if [[ -z "${cur}" ]]; then
        warn "não consegui ler o microfone ativo (pactl/wpctl ausentes ou WirePlumber parado)"
        return
    fi
    # O '.monitor' do sink do DualSense casa "DualSense" no nome mas é o loopback
    # da saída, não o mic — inofensivo. Só o alsa_input (mic) é o sintoma real.
    if [[ ! "${cur}" =~ [Dd]ual[Ss]ense ]] || [[ "${cur}" == *[Mm]onitor* ]]; then
        pass "microfone ativo não é o mic do DualSense (${cur})"
        return
    fi
    # ativo É o DualSense. Se a usuária QUER o mic do DualSense (opt-in), isso é
    # o desejado — não alarmar. Espelha a guarda de check_usb_audio_off e de
    # system_check.py (_dualsense_mic_intended), evitando falso-positivo.
    case "${HEFESTO_DUALSENSE4UNIX_DUALSENSE_MIC_INTENDED:-}" in
        1|true|yes|TRUE|YES)
            pass "microfone ativo é o DualSense (DUALSENSE_MIC_INTENDED=1 — desejado)"
            return ;;
    esac
    # ativo É o DualSense (não desejado) — distingue escassez (única fonte) de falha real.
    local has_other=""
    if command -v wpctl >/dev/null 2>&1; then
        has_other="$(wpctl status 2>/dev/null | awk '
            /Sources:/{s=1;next} s&&(/Filters:/||/Sinks:/||/Streams:/||/Video/){s=0}
            s&&/[0-9]+\./&&!/[Dd]ual[Ss]ense/{print;exit}')"
    fi
    if [[ -n "${has_other}" ]]; then
        fail "DualSense é o microfone ATIVO com outra fonte disponível — rode: scripts/doctor.sh --fix"
    else
        warn "DualSense é o microfone ATIVO por ser a única fonte — conecte mic/webcam, ou desligue de vez: fix_wireplumber_default_source.sh --disable-source"
    fi
}

# O drop-in 53 (disable-output) põe node.disabled no SINK do DualSense — deixa o
# alto-falante e o fone no jack do controle MUDOS e derruba o canal de
# haptic-de-áudio. Instalado SÓ pelo fluxo de mic-off (--disable-source /
# install --with-wireplumber-disable-mic). Aqui só REPORTAMOS: presença = saída
# do controle desligada de propósito. NÃO afeta o rumble in-game (HID/vpad).
check_dualsense_sink_disabled() {
    local d="${HOME}/.config/wireplumber/wireplumber.conf.d/53-hefesto-dualsense-disable-output.conf"
    if [[ -f "${d}" ]]; then
        warn "saída de áudio do DualSense DESLIGADA (drop-in 53) — alto-falante/fone do controle mudos e canal de haptic-de-áudio off. Se não foi intencional: fix_wireplumber_default_source.sh --enable-mic + systemctl --user restart wireplumber"
    else
        pass "saída de áudio do DualSense preservada (sem o drop-in 53 disable-output)"
    fi
}

# Duplicação no jogo — DEDUP-04/UX-05: o doctor PAROU de recomendar a env
# estática (`IGNORE_DEVICES` colado por jogo era o veneno do "em BT nada
# funciona": quando o vpad degrada, a opção persistida esconde o ÚNICO
# controle => jogo com zero controles). O caminho suportado é o wrapper
# `hefesto-launch %command%`: string constante que decide as envs NA HORA
# consultando o daemon via IPC e degrada para "nenhuma env" (jogo sempre
# abre; pior caso: duplicado). Aqui: verificação do wrapper instalado + da
# materialização viva.
check_launch_wrapper() {
    local wrapper="${HOME}/.local/share/hefesto-dualsense4unix/bin/hefesto-launch"
    if [[ -x "${wrapper}" ]]; then
        pass "wrapper de launch instalado (${wrapper})"
    elif [[ -e "${wrapper}" ]]; then
        fail "wrapper hefesto-launch presente mas NÃO executável — rode: chmod +x ${wrapper}"
    else
        fail "wrapper hefesto-launch ausente — rode ./install.sh (entra por default, sem flag)"
    fi
    local envdir="${HOME}/.local/state/hefesto-dualsense4unix/launch_env"
    if [[ -f "${envdir}/default.env" ]]; then
        pass "materialização de launch viva (${envdir}/default.env)"
        [[ "${QUIET}" -eq 1 ]] || sed -n 's/^# estado: /       estado: /p' "${envdir}/default.env" | head -1
    else
        warn "launch_env/default.env ausente — o daemon materializa ao (re)iniciar/ligar a emulação; sem ele o wrapper lança sem envs (fail-safe: jogo abre, pode duplicar)"
    fi
    info "controle DOBRANDO no jogo? use o botão 'Copiar opções p/ jogos' da GUI (string constante do wrapper) ou 'Aplicar aos jogos da Steam' (migra os jogos já configurados)."
}

# UX-04: ACUSA (nunca recomenda) o veneno estático persistido nos
# localconfig.vdf — a assinatura `SDL_GAMECONTROLLER_IGNORE_DEVICES=
# 0x054c/0x0ce6` colada por jogo esconde físico E vpad quando o vpad degrada.
check_vdf_poison() {
    shopt -s nullglob
    local vdfs=(
        "${HOME}/.steam/steam/userdata/"*/config/localconfig.vdf
        "${HOME}/.local/share/Steam/userdata/"*/config/localconfig.vdf
        "${HOME}/.var/app/com.valvesoftware.Steam/.steam/steam/userdata/"*/config/localconfig.vdf
        "${HOME}/snap/steam/common/.steam/steam/userdata/"*/config/localconfig.vdf
    )
    shopt -u nullglob
    if [[ "${#vdfs[@]}" -eq 0 ]]; then
        info "nenhum localconfig.vdf da Steam encontrado — nada a acusar"
        return
    fi
    local vdf poisoned=0
    for vdf in "${vdfs[@]}"; do
        [[ -f "${vdf}" ]] || continue
        if grep -q 'SDL_GAMECONTROLLER_IGNORE_DEVICES=0x054c/0x0ce6' "${vdf}" 2>/dev/null; then
            poisoned=1
            warn "veneno estático persistido em ${vdf} — se o Hefesto cair/degradar, esse jogo abre com ZERO controles"
        fi
    done
    if [[ "${poisoned}" -eq 1 ]]; then
        info "cura (com a Steam fechada): botão 'Aplicar aos jogos da Steam' na GUI, ou:"
        info "  python3 ${ROOT_DIR}/src/hefesto_dualsense4unix/integrations/steam_launch_options.py --migrate"
    else
        pass "nenhuma Launch Option com o veneno estático nos localconfig.vdf"
    fi
}

# DEDUP-06: o guard anti-veneno consultado do MESMO jeito que o wrapper
# consulta o daemon — via IPC no socket de produção (nunca inspeção de
# processo). Reporta o `dedup_ok` agregado POR JOGADOR (P1 + co-op) e o aviso
# BT+Nativo (o SDL pode não enxergar o físico BT — fora do alcance do wrapper).
check_dedup_ipc() {
    local sock; sock="$(runtime_socket)"
    if [[ ! -S "${sock}" ]]; then
        info "daemon parado — sem estado de dedup a consultar (suba o daemon e rode de novo)"
        return
    fi
    if ! command -v python3 >/dev/null 2>&1; then
        warn "python3 ausente — não dá para consultar o dedup via IPC"
        return
    fi
    local out
    if ! out="$(python3 - "${sock}" <<'PYEOF' 2>/dev/null
import json
import socket
import sys

s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.settimeout(2.0)
s.connect(sys.argv[1])
s.sendall(
    json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": "daemon.state_full", "params": {}}
    ).encode("utf-8")
    + b"\n"
)
buf = b""
while not buf.endswith(b"\n"):
    chunk = s.recv(65536)
    if not chunk:
        raise SystemExit(1)
    buf += chunk
data = json.loads(buf.decode("utf-8"))
res = data.get("result") or {}
ge = res.get("gamepad_emulation") or {}
print(f"enabled={ge.get('enabled')}")
print(f"dedup_ok={ge.get('dedup_ok')}")
print(f"dedup_motivo={ge.get('dedup_motivo') or ''}")
print(f"native_bt={res.get('native_bt_fragil')}")
PYEOF
)"; then
        warn "IPC não respondeu — estado de dedup indisponível (daemon travado?)"
        return
    fi
    local enabled dedup_ok motivo native_bt
    enabled="$(sed -n 's/^enabled=//p' <<<"${out}")"
    dedup_ok="$(sed -n 's/^dedup_ok=//p' <<<"${out}")"
    motivo="$(sed -n 's/^dedup_motivo=//p' <<<"${out}")"
    native_bt="$(sed -n 's/^native_bt=//p' <<<"${out}")"
    if [[ "${native_bt}" == "True" ]]; then
        warn "Modo Nativo com o controle em BLUETOOTH — o SDL pode não enxergar o físico BT (limite do HIDAPI); se o jogo não vir o controle, use cabo USB ou a emulação"
    fi
    if [[ "${enabled}" != "True" ]]; then
        info "emulação de gamepad desligada — dedup por vpad não se aplica agora"
    elif [[ "${dedup_ok}" == "True" ]]; then
        pass "dedup POR JOGADOR ok (todos os vpads Edge/uhid, ou máscara Xbox)"
    elif [[ "${dedup_ok}" == "False" ]]; then
        warn "dedup QUEBRADA (${motivo:-sem motivo}) — jogo aberto com o IGNORE congelado pode deixar esse jogador com ZERO controles; reinicie o Hefesto na aba Sistema"
    else
        info "daemon não reporta dedup_ok (versão antiga do daemon?)"
    fi
}

# FEAT-WINDOW-DETECT-DIAG-01: diagnóstico do detector de janela do autoswitch
# (perfil-por-jogo). Quando a detecção falha, o autoswitch fica silenciosamente
# cego e o perfil-por-jogo vira letra morta — esta seção torna o estado visível.
# Cobre: DISPLAY/WAYLAND_DISPLAY do shell atual E do systemd --user (o daemon
# importa de lá quando sobe sem display — _ensure_display_env), o backend xlib
# (X11/XWayland: inclui jogos Proton/Steam), o portal XDG (GetActiveWindow) e o
# wlrctl. Caso COSMIC validado ao vivo: o cosmic-comp NÃO expõe
# wlr-foreign-toplevel-management ("Foreign Toplevel Management interface not
# found") — wlrctl instalado NÃO ajuda; suporte nativo exigiria o protocolo
# próprio zcosmic_toplevel_info_v1. Veredito: OK / DEGRADADO (só XWayland) /
# CEGO.
check_window_detect() {
    local env_display="${DISPLAY:-}" env_wayland="${WAYLAND_DISPLAY:-}"
    local sysd_env="" sysd_display="" sysd_wayland=""
    if command -v systemctl >/dev/null 2>&1; then
        sysd_env="$(systemctl --user show-environment 2>/dev/null || true)"
        sysd_display="$(printf '%s\n' "${sysd_env}" | sed -n 's/^DISPLAY=//p' | head -1)"
        sysd_wayland="$(printf '%s\n' "${sysd_env}" | sed -n 's/^WAYLAND_DISPLAY=//p' | head -1)"
    fi
    info "shell atual:    DISPLAY=${env_display:-<vazio>}  WAYLAND_DISPLAY=${env_wayland:-<vazio>}"
    info "systemd --user: DISPLAY=${sysd_display:-<vazio>}  WAYLAND_DISPLAY=${sysd_wayland:-<vazio>}"

    # Valores efetivos: espelha o daemon (usa o env; se faltar, importa do
    # systemd --user via _ensure_display_env no boot do autoswitch).
    local eff_display="${env_display:-${sysd_display}}"
    local eff_wayland="${env_wayland:-${sysd_wayland}}"
    if [[ -z "${env_display}" && -n "${sysd_display}" ]]; then
        info "DISPLAY só existe no systemd --user — o daemon importa sozinho no boot do autoswitch"
    fi

    # Backend xlib (X11/XWayland). xprop prova que o servidor X responde;
    # python-xlib (o que o daemon usa de fato) fica como probe secundário
    # porque o python3 do PATH pode não ser o venv do daemon.
    local xlib_ok=0
    if [[ -n "${eff_display}" ]]; then
        if command -v xprop >/dev/null 2>&1 \
           && DISPLAY="${eff_display}" timeout 3 xprop -root _NET_ACTIVE_WINDOW >/dev/null 2>&1; then
            xlib_ok=1
            pass "servidor X responde em DISPLAY=${eff_display} (xprop) — backend xlib viável"
        elif DISPLAY="${eff_display}" timeout 3 python3 -c \
             'from Xlib import display; display.Display().close()' >/dev/null 2>&1; then
            xlib_ok=1
            pass "python-xlib conecta em DISPLAY=${eff_display} — backend xlib viável"
        else
            warn "DISPLAY=${eff_display} setado, mas nem xprop nem python-xlib falam com o X — backend xlib fora"
        fi
    else
        info "sem DISPLAY — backend xlib indisponível (jogos XWayland/Proton NÃO detectáveis)"
    fi

    # Portal XDG: interface Window com o método GetActiveWindow de verdade
    # (busctl com filtro de interface SEMPRE sai 0 — o grep é o teste real).
    local portal_ok=0
    if command -v busctl >/dev/null 2>&1; then
        if busctl --user --timeout=3 introspect org.freedesktop.portal.Desktop \
             /org/freedesktop/portal/desktop org.freedesktop.portal.Window 2>/dev/null \
             | grep -q 'GetActiveWindow'; then
            portal_ok=1
            pass "portal XDG expõe org.freedesktop.portal.Window::GetActiveWindow"
        else
            info "portal XDG sem GetActiveWindow (esperado no COSMIC atual) — backend portal fora"
        fi
    fi

    # wlrctl (wlr-foreign-toplevel-management), interpretando o caso COSMIC.
    local wlrctl_ok=0 wlrctl_out="" wlrctl_rc=0
    if ! command -v wlrctl >/dev/null 2>&1; then
        info "wlrctl não instalado — backend wlrctl indisponível (irrelevante se o veredito abaixo for OK)"
    elif [[ -z "${eff_wayland}" ]]; then
        info "wlrctl instalado, mas sem WAYLAND_DISPLAY — nada a testar"
    else
        wlrctl_out="$(WAYLAND_DISPLAY="${eff_wayland}" timeout 3 wlrctl toplevel list 2>&1)"
        wlrctl_rc=$?
        if printf '%s' "${wlrctl_out}" | grep -qi 'toplevel management interface not found'; then
            info "compositor SEM wlr-foreign-toplevel-management (caso do cosmic-comp) — wlrctl instalado não ajuda aqui; jogos XWayland/Proton continuam detectáveis via xlib. Suporte nativo ao COSMIC exigiria zcosmic_toplevel_info_v1."
        elif [[ "${wlrctl_rc}" -eq 0 ]]; then
            wlrctl_ok=1
            pass "wlrctl responde (wlr-foreign-toplevel-management OK)"
        else
            warn "wlrctl falhou (rc=${wlrctl_rc}): $(printf '%s' "${wlrctl_out}" | head -1)"
        fi
    fi

    # Veredito.
    if [[ "${xlib_ok}" -eq 1 && -z "${eff_wayland}" ]]; then
        pass "veredito: OK via xlib (sessão X11 pura — todas as janelas detectáveis)"
    elif [[ "${xlib_ok}" -eq 1 && ( "${portal_ok}" -eq 1 || "${wlrctl_ok}" -eq 1 ) ]]; then
        pass "veredito: OK via xlib + backend Wayland disponível (cobertura total)"
    elif [[ "${xlib_ok}" -eq 1 ]]; then
        warn "veredito: DEGRADADO — só XWayland: jogos Proton/Steam e apps X11 são detectados (xlib), mas apps Wayland nativos aparecem como 'unknown'. Limitação do compositor (COSMIC exigiria zcosmic_toplevel_info_v1), não do hefesto."
    elif [[ "${portal_ok}" -eq 1 ]]; then
        pass "veredito: OK via portal XDG (Wayland puro)"
    elif [[ "${wlrctl_ok}" -eq 1 ]]; then
        pass "veredito: OK via wlrctl (Wayland puro)"
    elif [[ -z "${eff_display}" && -z "${eff_wayland}" ]]; then
        fail "veredito: CEGO — sem DISPLAY e sem WAYLAND_DISPLAY (nem no systemd --user). Se o daemon subiu antes do login gráfico, reinicie: systemctl --user restart ${APP_ID}.service"
    else
        fail "veredito: CEGO — há display no ambiente mas nenhum backend funciona (X inacessível, portal sem GetActiveWindow, wlrctl sem protocolo); o autoswitch ficará no fallback e perfil-por-jogo não muda sozinho"
    fi
}

check_steam_input() {
    local script="${ROOT_DIR}/scripts/disable_steam_input.sh"
    if [[ ! -x "$script" ]]; then
        info "scripts/disable_steam_input.sh ausente — skip"
        return
    fi
    # Reusa o --status do próprio script (cobre deb/flatpak/snap, todos os users).
    local out
    out="$(bash "$script" --status 2>&1)"
    if printf '%s\n' "$out" | grep -q 'tudo limpo'; then
        pass "Steam Input PSSupport desligado em todos os localconfig.vdf"
    elif printf '%s\n' "$out" | grep -q 'ação sugerida'; then
        fail "Steam Input ATIVO (PSSupport=2 ou UseSteamControllerConfig=2) — conflita com o daemon; rode: scripts/doctor.sh --fix"
    elif printf '%s\n' "$out" | grep -q 'nenhum localconfig.vdf encontrado'; then
        info "Steam não detectada (sem localconfig.vdf)"
    else
        info "Steam Input status:"
        printf '%s\n' "$out" | sed 's/^/         /'
    fi
}

check_controller() {
    local h hidraw=0
    for h in /dev/hidraw*; do [[ -e "$h" ]] && hidraw=1; done
    [[ "${hidraw}" -eq 1 ]] && info "nós hidraw: $(ls /dev/hidraw* 2>/dev/null | tr '\n' ' ')"
    if command -v lsusb >/dev/null 2>&1 && lsusb 2>/dev/null | grep -qiE '054c'; then
        pass "DualSense conectado via USB (vendor 054c)"
    elif command -v bluetoothctl >/dev/null 2>&1 && timeout 4 bluetoothctl devices 2>/dev/null | grep -qi 'DualSense'; then
        pass "DualSense pareado via Bluetooth (conecte para usar)"
    else
        warn "controle não detectado agora — conecte o DualSense para testar"
    fi
}

check_perms_soft() {
    local h mode
    for h in /dev/hidraw*; do
        [[ -e "$h" ]] || continue
        mode="$(stat -c '%a' "$h" 2>/dev/null || echo '?')"
        [[ "${mode}" == "666" ]] && warn "${h} está 0666 (rw global) — provável ajuste manual; esperado é 0660+uaccess"
    done
}

# 8BIT-03: assinatura de morte por Bluetooth do 8BitDo SN30 Pro (firmware
# clone) em modo Switch — o hid-nintendo desiste do controle e o input morre
# com o link BT ainda de pé. PROVADO ao vivo (2026-07-16, journal desta
# máquina) que o gate tem de ser a CASCATA, nunca a linha isolada:
#   - morte real (0005:057E:2009.0014, 13:23:47->13:24:00): dezenas de
#     "timeout waiting for input report" culminando em
#     "joycon_enforce_subcmd_rate: exceeded max attempts";
#   - NÃO-terminal medido (.0008 às 12:38:46: 3x exceeded com UM timeout;
#     o controle viveu mais ~8 min): "exceeded" isolado NÃO pode disparar.
# O hefesto está fora da cadeia causal (o daemon só abre DualSense — filtro
# Sony 054c — e é incapaz de tocar um device 057e); a morte aconteceu até SEM
# Steam rodando, então "feche o Steam" não é cura. A coabitação Steam×hidraw
# NUNCA vira warning aqui: o Steam segura o hidraw de TODO controle
# suportado, inclusive dos DualSense saudáveis.
#
# Função PURA e testável: lê linhas do journal do kernel no stdin e imprime
# "instância N" (uma por linha, N = timeouts acumulados até o último
# "exceeded max attempts" qualificado) só para instâncias hid com a cascata:
# >= $1 timeouts (default 10) acumulados ANTES de um "exceeded" na MESMA
# instância. Journal limpo ou só linhas isoladas => saída vazia.
_hid_nintendo_cascade_scan() {
    local min="${1:-10}"
    sed -nE \
        -e 's/^.*([0-9A-Fa-f]{4}:[0-9A-Fa-f]{4}:[0-9A-Fa-f]{4}\.[0-9A-Fa-f]{4}).*timeout waiting for input report.*$/\1 timeout/p' \
        -e 's/^.*([0-9A-Fa-f]{4}:[0-9A-Fa-f]{4}:[0-9A-Fa-f]{4}\.[0-9A-Fa-f]{4}).*joycon_enforce_subcmd_rate: exceeded max attempts.*$/\1 exceeded/p' \
      | awk -v min="${min}" '
            $2 == "timeout"                    { t[$1]++ }
            $2 == "exceeded" && t[$1] >= min   { casc[$1] = t[$1] }
            END { for (i in casc) printf "%s %d\n", i, casc[i] }
        ' | sort
}

# Check INFORMATIVO (warn no positivo; exit code inalterado; nada muda no
# sistema; nenhuma flag nova). Silencioso quando o boot atual não tem a
# cascata — o 8BitDo não é gerenciado pelo hefesto e um "OK" aqui só faria
# barulho. Usa `journalctl -b -k` SEM sudo (grupo adm; o dmesg cru é
# restrito por kernel.dmesg_restrict=1) — mesmo padrão dos outros checks.
check_hid_nintendo_bt_cascade() {
    command -v journalctl >/dev/null 2>&1 || return 0
    local hits
    hits="$(journalctl -b -k --no-pager 2>/dev/null | _hid_nintendo_cascade_scan)"
    [[ -z "${hits}" ]] && return 0
    local inst n
    while read -r inst n; do
        [[ -z "${inst}" ]] && continue
        warn "o driver desistiu do controle (instância ${inst}, neste boot): ${n}x 'timeout waiting for input report' culminando em 'joycon_enforce_subcmd_rate: exceeded max attempts' — por Bluetooth o firmware 8BitDo em modo Switch engasga com o hid-nintendo"
    done <<<"${hits}"
    info "a configuração provadamente estável é cabo em modo Switch; X-input por cabo vira Xbox 360 real (sem gyro); X-input por Bluetooth é experimento"
    info "não é o hefesto: o daemon só abre DualSense (filtro Sony 054c) e é incapaz de tocar um device Nintendo (057e)"
    info "guia: docs/usage/troubleshooting-8bitdo.md"
}

# FEAT-DOCTOR-USB-DROPOUT-DIAGNOSTIC-01.
# Resolve o controlador PCI (xHCI) onde um device USB (sysfs path) está pendurado:
# o último 0000:XX:YY.Z na cadeia antes do /usbN é o controlador.
usb_pci_controller() {
    local devpath="$1" real
    real="$(readlink -f "${devpath}" 2>/dev/null || true)"
    printf '%s\n' "${real}" | grep -oE '0000:[0-9a-f]{2}:[0-9a-f]{2}\.[0-9a-f]' | tail -1
}

pci_label() {
    case "$1" in
        *0c:00.3) echo "CPU/Ryzen (0c:00.3)" ;;      # controlador USB integrado do Ryzen
        *02:00.0) echo "chipset (02:00.0)" ;;        # controlador USB do southbridge
        "")       echo "desconhecido" ;;
        *)        echo "$1" ;;
    esac
}

# Mapeia um número de bus USB para o rótulo do controlador PCI do seu root hub.
bus_to_label() {
    pci_label "$(usb_pci_controller "/sys/bus/usb/devices/usb${1}" 2>/dev/null)"
}

# Conta sintomas de dropout -71 (EPROTO) e ATRIBUI corretamente a fonte.
check_usb_dropout() {
    command -v journalctl >/dev/null 2>&1 || { info "journalctl ausente — pulo o check de dropout"; return; }

    # Localização: em qual controlador o DualSense (vendor 054c) está agora.
    local d ds_dev="" ds_pci="" ds_devname=""
    for d in /sys/bus/usb/devices/*; do
        [[ -r "$d/idVendor" ]] || continue
        [[ "$(cat "$d/idVendor" 2>/dev/null)" == "054c" ]] && ds_dev="$d"
    done
    if [[ -n "$ds_dev" ]]; then
        ds_pci="$(usb_pci_controller "$ds_dev")"
        ds_devname="$(basename "$ds_dev")"
        info "DualSense no controlador $(pci_label "$ds_pci"), Bus $(cat "$ds_dev/busnum" 2>/dev/null), power/control=$(cat "$ds_dev/power/control" 2>/dev/null)"
    else
        info "DualSense não conectado via USB agora (pode estar via Bluetooth) — pulo a localização de barramento"
    fi

    # Sintomas de -71 no boot atual (read-only).
    local lines n
    lines="$(journalctl -b -k --no-pager 2>/dev/null \
              | grep -iE 'error -71|device descriptor read/64, error|not accepting address|unable to enumerate USB device' || true)"
    n="$(printf '%s' "$lines" | grep -c . || true)"; n="${n:-0}"
    if [[ "${n}" -eq 0 ]]; then
        pass "sem dropout -71 neste boot"
        return
    fi
    warn "dropout USB: ${n} sintoma(s) -71/enum neste boot"

    # ATRIBUIÇÃO HONESTA (corrige a heurística antiga que culpava o controlador
    # do Ryzen só por o dsx estar lá): extrai QUAIS devices 'usb X-Y' geraram o
    # -71 e mapeia o bus -> controlador. O -71 de boot costuma ser OUTRO device
    # (ex: webcam no chipset), não o DualSense.
    local devs dev busnum hits dsx_hits=0 other_count=0
    devs="$(printf '%s\n' "$lines" | grep -oE 'usb [0-9]+-[0-9.]+' | awk '{print $2}' | sort -u)"
    [[ -n "$devs" ]] && info "fonte(s) do -71 neste boot:"
    for dev in $devs; do
        busnum="${dev%%-*}"
        hits="$(printf '%s\n' "$lines" | grep -c "usb ${dev}:" || true)"
        if [[ -n "$ds_devname" && "$dev" == "$ds_devname" ]]; then
            dsx_hits="$hits"
            info "  - usb ${dev} = DualSense (Bus ${busnum} = $(bus_to_label "$busnum")) -- ${hits}x"
        else
            other_count=$((other_count + 1))
            info "  - usb ${dev} = outro device (Bus ${busnum} = $(bus_to_label "$busnum")) -- ${hits}x"
        fi
    done

    if [[ "${dsx_hits:-0}" -gt 0 ]]; then
        info "o -71 ATINGE o DualSense -- storm port-independente; fix: quirk usbcore.quirks=...gn,gn (alavanca A, preserva áudio) OU regra 75 authorized=0 (alavanca B). Cheque: scripts/install_usb_quirk.sh --check"
    else
        info "o -71 deste boot NÃO é do DualSense -- provável outro device (ex: webcam). Valide o dsx abrindo a Steam com --watch-dropout."
    fi

    # rede de segurança (watcher) — NÃO é a solução, só mitigação.
    if systemctl is-enabled --quiet hefesto-dsx-recover.service 2>/dev/null \
       || systemctl is-active --quiet hefesto-dsx-recover.service 2>/dev/null; then
        info "watcher de auto-recuperação ativo (hefesto-dsx-recover.service)"
    else
        info "auto-recuperação NÃO instalada -- instale o watcher: sudo install -Dm755 scripts/dsx_recover.sh /usr/local/sbin/dsx_recover.sh && sudo install -Dm644 assets/hefesto-dsx-recover.service /etc/systemd/system/ && sudo systemctl enable --now hefesto-dsx-recover.service"
    fi
    info "ver em tempo real: scripts/doctor.sh --watch-dropout"
}

# --suggest-port: diz em qual controlador USB o DualSense está. DIAGNÓSTICO
# NEUTRO -- o storm -71 é port-independente (A/B comprovado: cai em qualquer
# porta sob carga de GPU/Steam quando o snd-usb-audio enumera as 3 interfaces
# de áudio do controle). A localização do controlador NÃO é o fix; o fix é o
# quirk (alavanca A) OU a regra 75 (alavanca B). Esta função só ajuda a mapear
# topologia (ex: o dongle WiFi no mesmo controlador, que o rebind por software
# derrubaria).
suggest_port() {
    local d ds_dev=""
    for d in /sys/bus/usb/devices/*; do
        [[ -r "$d/idVendor" ]] || continue
        [[ "$(cat "$d/idVendor" 2>/dev/null)" == "054c" ]] && ds_dev="$d"
    done
    if [[ -z "$ds_dev" ]]; then
        if command -v bluetoothctl >/dev/null 2>&1 && timeout 4 bluetoothctl devices 2>/dev/null | grep -qi 'DualSense'; then
            info "DualSense via Bluetooth (sem caminho USB) -- sem snd-usb-audio, logo sem storm pelo controle"
        else
            info "DualSense não conectado via USB nem Bluetooth -- conecte para avaliar"
        fi
        return
    fi
    local ds_pci bus
    ds_pci="$(usb_pci_controller "$ds_dev")"
    bus="$(cat "$ds_dev/busnum" 2>/dev/null)"
    info "DualSense em Bus ${bus}, controlador $(pci_label "$ds_pci")"
    info "  topologia apenas (diagnóstico neutro). O storm -71 é port-independente:"
    info "  o fix é o quirk usbcore.quirks=...gn,gn (alavanca A, preserva áudio)"
    info "  OU a regra 75 authorized=0 (alavanca B). Cheque: scripts/install_usb_quirk.sh --check"
}

# Modo --watch-dropout: bloqueia até o primeiro sintoma de dropout e sai.
watch_dropout() {
    printf 'vigiando o journal do kernel por dropout -71 (Ctrl-C para sair)...\n'
    journalctl -kf -o cat --since now 2>/dev/null \
      | grep -m1 -iE 'error -71|device descriptor read/64, error|not accepting address|device not responding' \
      && printf '\n[WATCH] primeiro sinal de dropout capturado acima.\n'
}

apply_fixes() {
    hdr "aplicando correções (--fix)"
    if command -v sudo >/dev/null 2>&1; then
        if sudo bash "${ROOT_DIR}/scripts/install_udev.sh" >/dev/null 2>&1; then
            pass "regras udev reaplicadas"
        else
            warn "falha ao reaplicar udev"
        fi
    else
        warn "sudo ausente — não reapliquei udev"
    fi
    if bash "${ROOT_DIR}/scripts/fix_wireplumber_default_source.sh" --install >/dev/null 2>&1; then
        pass "fix de áudio do WirePlumber aplicado"
    else
        warn "fix de áudio do WirePlumber falhou"
    fi
    if [[ -x "${ROOT_DIR}/scripts/disable_steam_input.sh" ]]; then
        if bash "${ROOT_DIR}/scripts/disable_steam_input.sh" --apply >/dev/null 2>&1; then
            pass "Steam Input PSSupport desligado (todos os localconfig.vdf)"
        else
            warn "disable_steam_input.sh falhou"
        fi
    fi
}

main() {
    [[ "${WATCH_DROPOUT}" -eq 1 ]] && { watch_dropout; exit 0; }
    [[ "${SUGGEST_PORT}" -eq 1 ]] && { suggest_port; exit 0; }
    [[ "${DO_FIX}" -eq 1 ]] && apply_fixes
    hdr "daemon"
    check_daemon_installed
    check_service
    check_socket
    hdr "kernel / udev"
    check_udev
    check_usb_audio_off
    check_usb_quirk
    check_usb_storm_config_conflict
    check_uinput
    check_uhid
    check_hid_playstation
    check_led_sysfs_gravavel
    hdr "applet COSMIC"
    check_applet
    hdr "detector de janela (autoswitch / perfil-por-jogo)"
    check_window_detect
    hdr "áudio (microfone)"
    check_wireplumber_source
    check_dualsense_sink_disabled
    hdr "Steam Input"
    check_steam_input
    hdr "controle no jogo (duplicação / wrapper de launch)"
    check_launch_wrapper
    check_vdf_poison
    check_dedup_ipc
    hdr "controle"
    check_controller
    check_perms_soft
    check_hid_nintendo_bt_cascade
    hdr "USB / dropout"
    check_usb_dropout

    printf '\n─────────────────────────────────────────\n'
    if [[ "${FAILS}" -eq 0 ]]; then
        printf ' Diagnóstico: tudo OK (%d aviso(s))\n' "${WARNS}"
    else
        printf ' Diagnóstico: %d FALHA(s), %d aviso(s)\n' "${FAILS}" "${WARNS}"
    fi
    printf '─────────────────────────────────────────\n'
    [[ "${FAILS}" -eq 0 ]]
}

# `source scripts/doctor.sh` (testes de unidade das funções de parse, ex.
# _hid_nintendo_cascade_scan) carrega as funções SEM executar o diagnóstico;
# a execução direta segue idêntica.
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main
fi
