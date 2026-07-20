#!/usr/bin/env bash
# doctor.sh — diagnóstico de saúde do Hefesto - Dualsense4Unix.
#
# Verifica daemon, serviço, socket IPC, regras udev (incluindo a consistência do
# nome de unit do hotplug), uinput, a gravabilidade do nó de LED do DualSense
# físico (cor por-controle via sysfs, regra 77), applet COSMIC (.desktop + ícone
# resolvível), o detector de janela do autoswitch (perfil-por-jogo), o sequestro
# do microfone pelo WirePlumber e o alcance do controle; a autoridade de
# exibição do co-op (NUMA-05: quem manda em lightbar/numeração agora — jogo,
# daemon ou "unknown" — e a CAUSA quando presa em unknown); reconhece também,
# no journal do kernel, a assinatura de morte por Bluetooth do 8BitDo em modo
# Switch (cascata do hid-nintendo — informativo, não gerenciamos o controle);
# e (G2) o rádio/pareamento — versão do bluez vs. o piso 5.79, o
# hefesto-bt-agent.service, bond "meio-salvo" por dois ângulos (Connected sem
# hidraw correspondente E Paired sem Bonded) e o sink de áudio padrão mudo;
# e (BROKER-01, Onda S) o broker root hide-hidraw fd-injection — unit de
# SISTEMA ativa, ping autenticado por SO_PEERCRED, coerência do que está
# escondido com o daemon/Modo Nativo e recusa a outro uid.
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
                 78-dualsense-motion-not-joystick.rules
                 79-external-controller-leds.rules
                 80-motion-joydev-hide.rules
                 81-hefesto-usb-power.rules
                 81-hefesto-usb-host-power.rules)
    local total=${#rules[@]}
    for r in "${rules[@]}"; do
        if [[ -e "/etc/udev/rules.d/${r}" || -e "/usr/lib/udev/rules.d/${r}" ]]; then
            found=$((found + 1))
        else
            missing+=" ${r}"
        fi
    done
    if [[ "${found}" -eq "${total}" ]]; then
        pass "${total} regras udev canônicas presentes (70/71-uhid/71-uinput/72/76/77/78/79/80/81-power/81-host)"
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

# G2 item 5: sink de áudio PADRÃO mudo — sintoma do incidente U12 de hoje
# (mute global escondia áudio/haptic de todo mundo, não só do DualSense).
# Função PURA (_wpctl_volume_muted) só interpreta o texto do `wpctl
# get-volume`; nenhuma escrita.
_wpctl_volume_muted() {
    local out="$1"
    if [[ -z "${out}" ]]; then
        printf 'unknown\n'
    elif printf '%s' "${out}" | grep -qi 'MUTED'; then
        printf 'muted\n'
    else
        printf 'unmuted\n'
    fi
}

check_audio_sink_muted() {
    command -v wpctl >/dev/null 2>&1 || { info "wpctl ausente — não checo o mudo do sink padrão"; return; }
    local out veredito
    out="$(wpctl get-volume @DEFAULT_AUDIO_SINK@ 2>/dev/null || true)"
    veredito="$(_wpctl_volume_muted "${out}")"
    case "${veredito}" in
        muted)
            warn "sink de áudio PADRÃO está MUDO (${out}) — sintoma do incidente U12 (mute global, não só do DualSense); reative: wpctl set-mute @DEFAULT_AUDIO_SINK@ 0"
            ;;
        unmuted)
            pass "sink de áudio padrão não está mudo (${out})"
            ;;
        *)
            info "não consegui ler o volume do sink padrão (wpctl get-volume vazio) — WirePlumber parado?"
            ;;
    esac
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
    # PATH-06: o install cria ~/.local/bin/hefesto-launch — `hefesto-launch
    # %command%` digitado à mão passa a funcionar (a string canônica do botão
    # continua sendo o `sh -c` com caminho absoluto, que funciona sem PATH).
    local pathlink="${HOME}/.local/bin/hefesto-launch"
    if command -v hefesto-launch >/dev/null 2>&1; then
        pass "wrapper no PATH ($(command -v hefesto-launch))"
    elif [[ -x "${pathlink}" ]]; then
        warn "symlink ${pathlink} existe mas ~/.local/bin não está no PATH desta sessão — 'hefesto-launch %command%' digitado à mão só funciona com o PATH ajustado"
    else
        warn "wrapper fora do PATH (${pathlink} ausente) — rode ./install.sh (o passo 5 cria o symlink, sem flag)"
    fi
    local envdir="${HOME}/.local/state/hefesto-dualsense4unix/launch_env"
    if [[ -f "${envdir}/default.env" ]]; then
        pass "materialização de launch viva (${envdir}/default.env)"
        [[ "${QUIET}" -eq 1 ]] || sed -n 's/^# estado: /       estado: /p' "${envdir}/default.env" | head -1
    else
        warn "launch_env/default.env ausente — o daemon materializa ao (re)iniciar/ligar a emulação; sem ele o wrapper lança sem envs (fail-safe: jogo abre, pode duplicar)"
    fi
    # KERNEL-07/MISC-08: PROTON_ENABLE_HIDRAW é env MORTA nos Protons 10/11 (o
    # script nem a menciona; no winebus ela só AMPLIA exposição) — presença num
    # .env materializado = estado antigo do daemon.
    local stale_env
    stale_env="$(grep -ls "PROTON_ENABLE_HIDRAW" "${envdir}"/*.env 2>/dev/null | head -1)"
    if [[ -n "${stale_env}" ]]; then
        warn "launch_env com PROTON_ENABLE_HIDRAW (env morta nos Protons 10/11): ${stale_env} — materialização antiga; reinicie o daemon (systemctl --user restart hefesto-dualsense4unix) para regravar"
    fi
    # PATH-06 item 3: quantos jogos já chamam o wrapper nas LaunchOptions. O
    # caminho absoluto do wrapper só aparece no vdf dentro da string `sh -c`
    # que nós escrevemos — contá-lo = contar jogos com o wrapper aplicado.
    local vdf n_wrapper=0
    shopt -s nullglob
    for vdf in "${HOME}/.steam/steam/userdata/"*/config/localconfig.vdf \
               "${HOME}/.local/share/Steam/userdata/"*/config/localconfig.vdf; do
        [[ -f "${vdf}" ]] || continue
        n_wrapper=$((n_wrapper + $(grep -o '.local/share/hefesto-dualsense4unix/bin/hefesto-launch' "${vdf}" 2>/dev/null | wc -l)))
    done
    shopt -u nullglob
    if [[ "${n_wrapper}" -gt 0 ]]; then
        pass "${n_wrapper} jogo(s) com o wrapper hefesto-launch aplicado nas LaunchOptions"
    else
        warn "NENHUM jogo com o wrapper nas LaunchOptions — o jogo roda SEM dedup (foi a causa-mãe da sessão de 2026-07-18); use 'Aplicar aos jogos da Steam' na GUI (com a Steam fechada)"
    fi
    info "controle DOBRANDO no jogo? use o botão 'Copiar opções p/ jogos' da GUI (string constante do wrapper) ou 'Aplicar aos jogos da Steam' (aplica o wrapper aos jogos, preservando as opções existentes)."
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

# NUMA-05: diagnóstico da AUTORIDADE DE EXIBIÇÃO ('game'|'daemon'|'unknown',
# NUMA-01) — a causa-raiz do incidente de 14:42 era "não existe autoridade de
# exibição": sessão uhid do cliente Steam virava "jogo" aos olhos do daemon.
# Reporta o sinal ATUAL + a CAUSA quando ele está preso em 'unknown' (o
# comportamento degradado é sempre igual ao de hoje — nunca pior — mas
# escondido sem esta seção a mantenedora não teria como saber POR QUE). O
# posse-por-controle (`player_slot`/`lightbar_source`/`lightbar_rgb`, já no
# `state_full` desde STATUS-01/EXT-04) é listado junto — é o mesmo par
# get_players()/get_rgb() vs. autoridade que o `defend_display` compara.
check_display_authority() {
    local sock; sock="$(runtime_socket)"
    if [[ ! -S "${sock}" ]]; then
        info "daemon parado — sem sinal de autoridade de exibição a consultar (suba o daemon e rode de novo)"
        return
    fi
    if ! command -v python3 >/dev/null 2>&1; then
        warn "python3 ausente — não dá para consultar a autoridade de exibição via IPC"
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
gs = res.get("game_signal")
if not isinstance(gs, dict):
    print("sem_sinal=1")
else:
    print("sem_sinal=0")
    print(f"authority={gs.get('authority')}")
    print(f"evidencia={gs.get('evidencia') or ''}")
    print(f"motivo={gs.get('motivo') or ''}")
    print(f"degradado={gs.get('degradado')}")
for c in res.get("controllers") or []:
    if not isinstance(c, dict):
        continue
    slot = c.get("player_slot")
    fonte = c.get("lightbar_source")
    rgb = c.get("lightbar_rgb")
    print(f"posse|{slot}|{fonte}|{rgb}")
PYEOF
)"; then
        warn "IPC não respondeu — autoridade de exibição indisponível (daemon travado?)"
        return
    fi
    local sem_sinal authority evidencia motivo degradado
    sem_sinal="$(sed -n 's/^sem_sinal=//p' <<<"${out}")"
    if [[ "${sem_sinal}" == "1" ]]; then
        info "daemon não reporta o sinal de autoridade de exibição (versão antiga, sem NUMA-05)"
        return
    fi
    authority="$(sed -n 's/^authority=//p' <<<"${out}")"
    evidencia="$(sed -n 's/^evidencia=//p' <<<"${out}")"
    motivo="$(sed -n 's/^motivo=//p' <<<"${out}")"
    degradado="$(sed -n 's/^degradado=//p' <<<"${out}")"
    case "${authority}" in
        game)
            pass "autoridade de exibição: JOGO (evidência: ${evidencia:-desconhecida}) — DualSense mostram o número do jogo, externos sem disputa"
            ;;
        daemon)
            pass "autoridade de exibição: DAEMON — numeração/cor do co-op valendo, defesa contra escritor estrangeiro ativa"
            ;;
        unknown)
            if [[ "${degradado}" == "True" ]]; then
                warn "autoridade de exibição UNKNOWN (causa: ${motivo:-sem motivo reportado}) — degrada para o comportamento de hoje (réplica passa, jogo vence, daemon NÃO repinta); nunca pior, mas sem a defesa do NUMA-03"
            else
                info "autoridade de exibição unknown sem causa reportada — comportamento atual"
            fi
            ;;
        *)
            info "autoridade de exibição não reconhecida (${authority:-vazia}) — versão inconsistente do daemon?"
            ;;
    esac
    while IFS='|' read -r tag slot fonte rgb; do
        [[ "${tag}" == "posse" ]] || continue
        info "controle player_slot=${slot:-—} lightbar_source=${fonte:-desconhecida} lightbar_rgb=${rgb:-None}"
    done <<<"${out}"
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

# ============================================================================
# Energia USB e rádio (onda PLATAFORMA 2026-07-18) — tudo READ-ONLY.
# Estudos: 2026-07-18-estudo-kernel-hardening.md + 2026-07-18-estudo-bt-maximo.md.
# ============================================================================

# PLAT-03 item 1: nenhum device USB pode estar em economia de energia — um
# controle/adaptador dormindo é queda na certa (a regra 81 mantém tudo 'on').
check_usb_power_devices() {
    local dev ctl vid nome bad=0 total=0 exemplos=""
    for dev in /sys/bus/usb/devices/*; do
        [[ -r "${dev}/power/control" && -r "${dev}/idVendor" ]] || continue
        total=$((total + 1))
        ctl="$(cat "${dev}/power/control" 2>/dev/null)"
        if [[ "${ctl}" == "auto" ]]; then
            bad=$((bad + 1))
            vid="$(cat "${dev}/idVendor" 2>/dev/null)"
            nome="$(cat "${dev}/product" 2>/dev/null || true)"
            exemplos+=" $(basename "${dev}") (${vid} ${nome:-?})"
        fi
    done
    if [[ "${total}" -eq 0 ]]; then
        info "sem devices USB legíveis no sysfs — pulo o check de energia dos devices"
    elif [[ "${bad}" -eq 0 ]]; then
        pass "nenhum device USB em economia de energia (power/control=on em ${total}/${total})"
    else
        warn "economia de energia ATIVA em ${bad} device(s) USB:${exemplos} — a regra 81 deveria mantê-los 'on': sudo bash scripts/install_udev.sh (e replugue)"
    fi
}

# PLAT-03 item 3: o HOST xHCI em economia suspende o controlador PCI inteiro —
# num wake mal suportado o barramento TODO cai (teclado+mouse+controle juntos,
# visto em maio/2026). A regra 81-host mantém os hosts em 'on'.
check_usb_power_hosts() {
    local pci cls ctl found=0 bad=""
    for pci in /sys/bus/pci/devices/*; do
        cls="$(cat "${pci}/class" 2>/dev/null)" || continue
        [[ "${cls}" == 0x0c03* ]] || continue
        found=1
        ctl="$(cat "${pci}/power/control" 2>/dev/null)"
        [[ "${ctl}" != "on" ]] && bad+=" $(basename "${pci}")=${ctl:-?}"
    done
    if [[ "${found}" -eq 0 ]]; then
        info "nenhum host USB (classe PCI 0x0c03*) legível — pulo o check dos hosts"
    elif [[ -z "${bad}" ]]; then
        pass "hosts USB (xHCI) com power/control=on — o barramento inteiro não dorme"
    else
        warn "host(s) USB em economia:${bad} — a suspensão do CONTROLADOR derruba teclado, mouse e controle juntos; a regra 81-host corrige: sudo bash scripts/install_udev.sh"
    fi
}

# ASPM: a FONTE é o /proc/cmdline. ARMADILHA PROVADA (estudo 2026-07-18 §3):
# com pcie_aspm=off a policy do sysfs continua mostrando "[default]" — ela
# MENTE. NUNCA usar a policy sysfs como prova do off; quem confirma de verdade
# é o LnkCtl do lspci (exige sudo — fora do doctor).
check_pcie_aspm() {
    local tok policy
    tok="$(grep -o 'pcie_aspm=[^ ]*' /proc/cmdline 2>/dev/null | head -1)"
    if [[ -n "${tok}" ]]; then
        pass "ASPM definido no boot (${tok}) — lido do /proc/cmdline (a policy do sysfs mente com pcie_aspm=off; nunca a use como prova)"
        return
    fi
    policy="$(cat /sys/module/pcie_aspm/parameters/policy 2>/dev/null || true)"
    if [[ "${policy}" == *"[powersave]"* || "${policy}" == *"[powersupersave]"* ]]; then
        warn "sem pcie_aspm= no cmdline e policy de economia ativa (${policy}) — pode somar latência/instabilidade aos hosts USB; mudar é decisão do dono (ex.: pcie_aspm=off via kernelstub)"
    else
        info "sem pcie_aspm= no cmdline; policy ativa: ${policy:-ilegível} (informativo — a política é decisão do dono da máquina)"
    fi
}

# PLAT-03 item 4: caça a sabotadores de energia — ferramentas que RELIGAM o
# USB autosuspend por cima do udev. Nada é desinstalado; só instrução de exceção.
check_power_saboteurs() {
    local achados="" p
    if command -v dpkg-query >/dev/null 2>&1; then
        for p in tlp powertop tuned; do
            dpkg-query -W "$p" >/dev/null 2>&1 && achados+=" ${p}"
        done
    fi
    if [[ -n "${achados}" ]]; then
        warn "ferramenta(s) de economia presentes:${achados} — podem religar o USB autosuspend por cima do udev. Exceções: TLP → USB_DENYLIST=\"054c:0ce6 054c:0df2\"; powertop → NÃO use --auto-tune; tuned → evite perfis powersave (nada foi desinstalado)"
    else
        pass "sem TLP/powertop/tuned instalados (nenhum religador de economia USB)"
    fi
    # system76-power (Pop!_OS/COSMIC): não é inimigo dos controles (a regra 81
    # re-assert em 'change' defende o USB), mas o perfil importa em jogo — o
    # wrapper hefesto-launch pede Performance no launch e restaura no exit.
    if command -v systemctl >/dev/null 2>&1 \
       && systemctl is-active --quiet com.system76.PowerDaemon.service 2>/dev/null; then
        local prof=""
        command -v system76-power >/dev/null 2>&1 \
            && prof="$(timeout 3 system76-power profile 2>/dev/null | head -1 || true)"
        info "system76-power ativo (${prof:-perfil ilegível}) — o wrapper pede Performance durante o jogo e restaura o perfil ao sair"
    fi
    # Assinatura provada do system76-power no storage: link PM med_power_with_dipm.
    local h val achou=0
    for h in /sys/class/scsi_host/host*/link_power_management_policy; do
        [[ -r "${h}" ]] || continue
        val="$(cat "${h}" 2>/dev/null)"
        [[ "${val}" == med_power* ]] && achou=1
    done
    if [[ "${achou}" -eq 1 ]]; then
        info "storage com link PM em economia (med_power_with_dipm — assinatura do system76-power); não derruba os controles (USB defendido pela regra 81), mas mostra um agente de economia vivo"
    fi
}

# PLAT-04 item 1: o btusb liga o autosuspend do adaptador BT no probe (default
# do módulo). O conf do hefesto corta na raiz; esperado N pós-boot.
check_btusb_autosuspend() {
    local conf=/etc/modprobe.d/hefesto-btusb-no-autosuspend.conf
    local param=/sys/module/btusb/parameters/enable_autosuspend
    local val=""
    [[ -r "${param}" ]] && val="$(cat "${param}" 2>/dev/null)"
    if [[ "${val}" == "N" || "${val}" == "0" ]]; then
        pass "btusb sem autosuspend (enable_autosuspend=N) — o rádio dos controles não dorme"
    elif [[ -f "${conf}" ]]; then
        if [[ -z "${val}" ]]; then
            info "modprobe.d do btusb instalado; módulo btusb não carregado agora (sem adaptador BT?)"
        else
            info "modprobe.d do btusb instalado, mas o módulo ainda está com enable_autosuspend=${val} — vale no próximo probe (replug do adaptador BT ou reboot); o runtime já é coberto pela regra 81"
        fi
    else
        warn "btusb com autosuspend LIGADO (enable_autosuspend=${val:-?}) e sem o conf do hefesto — em máquina sem usbcore.autosuspend=-1 global o rádio dos controles dorme; rode ./install.sh (o conf entra por default)"
    fi
}

# PLAT-04 item 3: FastConnectable = reconexão entrante mais rápida (botão PS).
check_bluez_fastconnectable() {
    local dropin=/etc/bluetooth/main.conf.d/hefesto-fastconnectable.conf
    if [[ -f "${dropin}" ]]; then
        pass "FastConnectable do BlueZ instalado (drop-in main.conf.d) — botão PS reconecta mais rápido (vale desde o último start do bluetoothd)"
    elif grep -qsF '# >>> hefesto FastConnectable >>>' /etc/bluetooth/main.conf 2>/dev/null; then
        pass "FastConnectable do BlueZ instalado (bloco marcado no main.conf) — vale desde o último start do bluetoothd"
    elif grep -qsE '^[[:space:]]*FastConnectable[[:space:]]*=[[:space:]]*true' /etc/bluetooth/main.conf 2>/dev/null; then
        pass "FastConnectable já configurado por terceiro no main.conf"
    elif [[ ! -e /etc/bluetooth/main.conf ]]; then
        info "sem /etc/bluetooth/main.conf (BlueZ ausente?) — pulo o check de FastConnectable"
    else
        warn "reconexão rápida BT (FastConnectable) não configurada — rode ./install.sh (entra por default, SEM restart do bluetoothd)"
    fi
}

# O "clone DS4" 054C:05C4 que stormou o rádio com 211 mil erros de CRC numa
# noite (estudo 2026-07-18 §2.1). Pelo OUI no cache do adaptador, é quase
# certamente um 8BitDo em modo D-input — o conselho é TROCAR O MODO/cabo, não
# jogar fora. (054C:05C4 também é o PID do DS4 v1 legítimo; o journal
# desempata: hw_version=0x00000000 denuncia o firmware clone.)
check_bt_clone_ds4() {
    command -v bluetoothctl >/dev/null 2>&1 || { info "bluetoothctl ausente — pulo a caça ao clone DS4"; return; }
    local macs mac inf clone=0
    macs="$(timeout 4 bluetoothctl devices 2>/dev/null | awk '{print $2}')"
    if [[ -z "${macs}" ]]; then
        info "nenhum dispositivo Bluetooth pareado — sem clone DS4 possível"
        return
    fi
    for mac in ${macs}; do
        inf="$(timeout 4 bluetoothctl info "${mac}" 2>/dev/null || true)"
        if printf '%s' "${inf}" | grep -q 'Modalias: usb:v054Cp05C4'; then
            clone=1
            warn "controle 'tipo DualShock 4' (054C:05C4) pareado (${mac}) — esse firmware não calcula a verificação de integridade e INUNDA o sistema de erros (já foram 211 mil numa noite), degradando o Bluetooth de TODOS os controles"
            info "  provavelmente é um 8BitDo em modo D-input: troque o modo (Switch) ou use no cabo"
            info "  para desparear: bluetoothctl remove ${mac}  (se for um DS4 v1 legítimo, o journal desempata: 'hw_version=0x00000000' = clone)"
        fi
    done
    [[ "${clone}" -eq 0 ]] && pass "nenhum clone DS4 (054C:05C4) pareado"
}

# Saúde do rádio 2.4 GHz: RSSI, Trusted, Discovering, contadores do adaptador
# e IdleTimeout — os 5 checks do estudo BT §5/§6, todos read-only.
check_bt_radio() {
    command -v bluetoothctl >/dev/null 2>&1 || return 0
    local macs mac inf nome rssi gamepad_conectado=0
    macs="$(timeout 4 bluetoothctl devices 2>/dev/null | awk '{print $2}')"
    for mac in ${macs}; do
        inf="$(timeout 4 bluetoothctl info "${mac}" 2>/dev/null || true)"
        printf '%s' "${inf}" | grep -qiE 'dualsense|wireless controller|pro controller|8bitdo|joy-con|xbox' || continue
        nome="$(printf '%s\n' "${inf}" | sed -n 's/^[[:space:]]*Name: //p' | head -1)"
        if printf '%s' "${inf}" | grep -q 'Connected: yes'; then
            gamepad_conectado=1
            rssi="$(printf '%s\n' "${inf}" | awk '/RSSI:/{ for (i = 1; i <= NF; i++) if ($i ~ /^\(?-[0-9]+\)?$/) { gsub(/[()]/, "", $i); print $i; exit } }')"
            if [[ -n "${rssi}" ]] && (( rssi < -70 )); then
                warn "sinal fraco do ${nome:-controle} (${mac}): RSSI ${rssi} dBm (bom é > -60) — ponha o adaptador BT num extensor USB curto, fora da sombra do gabinete e a 20 cm ou mais dos receivers 2.4G"
            elif [[ -n "${rssi}" ]]; then
                pass "sinal do ${nome:-controle}: RSSI ${rssi} dBm"
            fi
        fi
        if printf '%s' "${inf}" | grep -q 'Trusted: no'; then
            warn "${nome:-controle} (${mac}) pareado mas SEM confiança (Trusted: no) — a reconexão pelo botão PS pode depender de autorização; cura de 1 comando (reversível): bluetoothctl trust ${mac}"
        fi
    done
    # Inquiry contínuo rouba banda dos links dos controles (provado ao vivo:
    # a tela de Bluetooth do cosmic-settings aberta mantém Discovering=yes).
    if [[ "${gamepad_conectado}" -eq 1 ]] \
       && timeout 4 bluetoothctl show 2>/dev/null | grep -q 'Discovering: yes'; then
        warn "adaptador em modo de busca (Discovering: yes) com controle BT conectado — feche a tela de Bluetooth (cosmic-settings) enquanto joga; a busca rouba banda do rádio"
    fi
    # Contadores do adaptador (proxy não-intrusivo de rádio sujo — sem btmon).
    if command -v hciconfig >/dev/null 2>&1; then
        local errs
        errs="$(hciconfig hci0 2>/dev/null | grep -oE 'errors:[0-9]+' | grep -oE '[0-9]+' | paste -sd/ -)"
        if [[ -n "${errs}" && "${errs}" != "0/0" ]]; then
            warn "adaptador BT com erros acumulados (RX/TX: ${errs}) — rádio sujo; veja as linhas [BT-ERR] no kernel.log e os conselhos de posicionamento acima"
        elif [[ -n "${errs}" ]]; then
            pass "adaptador BT sem erros de RX/TX (0/0)"
        fi
    fi
    # IdleTimeout do input.conf: default 0 = nunca desconecta por ociosidade
    # (já é o máximo). Valor > 0 = regressão de terceiro.
    local idle
    idle="$(grep -sE '^[[:space:]]*IdleTimeout[[:space:]]*=' /etc/bluetooth/input.conf 2>/dev/null | head -1 | sed 's/.*=[[:space:]]*//')"
    if [[ -n "${idle}" && "${idle}" != "0" ]]; then
        warn "desconexão por ociosidade LIGADA no BlueZ (input.conf IdleTimeout=${idle}) — controles BT vão cair sozinhos; o default 0 (nunca) é o certo: remova a linha de /etc/bluetooth/input.conf"
    else
        pass "sem desconexão por ociosidade no BlueZ (IdleTimeout no default 0)"
    fi
}

# Termômetro do rádio: 'input CRC's check failed' no boot atual. Fundo
# aceitável medido: 2–39; o storm do clone foi 211 mil (20/s).
check_bt_crc_counters() {
    command -v journalctl >/dev/null 2>&1 || return 0
    local nds nds4
    nds="$(journalctl -b -k --no-pager 2>/dev/null | grep -c "DualSense input CRC" || true)"
    nds4="$(journalctl -b -k --no-pager 2>/dev/null | grep -c "DualShock4 input CRC" || true)"
    nds="${nds:-0}"; nds4="${nds4:-0}"
    if [[ "${nds4}" -gt 100 ]]; then
        warn "DualShock4 com ${nds4} erros de CRC neste boot — assinatura do clone DS4 conectado bombardeando o rádio (troque o modo/cabo ou despareie; ver o aviso do clone acima)"
    fi
    if [[ "${nds}" -gt 100 ]]; then
        warn "DualSense com ${nds} erros de CRC neste boot — rádio sujo (interferência 2.4 GHz); afaste o dongle dos receivers (extensor USB) e evite Wi-Fi USB 2.4G durante o jogo"
    elif [[ "${nds4}" -le 100 ]]; then
        pass "integridade dos pacotes BT ok neste boot (DualSense: ${nds}, DualShock4: ${nds4} erros de CRC — fundo aceitável)"
    fi
}

# kernel-watch (PLAT-06 item 4): resume o log dedicado pro leigo. Lê o
# kernel.log novo (fallback: storm.log antigo) e conta ocorrências por tag.
check_kernel_watch() {
    local unit="hefesto-dualsense4unix-storm-watch.service"
    if command -v systemctl >/dev/null 2>&1; then
        if systemctl --user is-active --quiet "${unit}" 2>/dev/null; then
            pass "kernel-watch ativo (${unit})"
        elif systemctl --user cat "${unit}" >/dev/null 2>&1; then
            warn "kernel-watch instalado mas parado — ligue: systemctl --user enable --now ${unit}"
        else
            warn "kernel-watch não instalado — rode ./install.sh (entra por default; --no-kernel-watch é o opt-out)"
        fi
    fi
    local log="${HOME}/.local/state/hefesto-dualsense4unix/kernel.log"
    [[ -f "${log}" ]] || log="${HOME}/.local/state/hefesto-dualsense4unix/storm.log"
    if [[ ! -f "${log}" ]]; then
        info "sem log do kernel-watch ainda (nasce no primeiro start/evento)"
        return
    fi
    local tag n resumo="" n_joycon=0 n_usb71=0 n_bterr=0
    for tag in USB-71 JOYCON BT-HCI XHCI BT-ERR; do
        n="$(grep -cF "[${tag}]" "${log}" 2>/dev/null || true)"; n="${n:-0}"
        resumo+=" ${tag}=${n}"
        case "${tag}" in
            JOYCON) n_joycon="${n}" ;;
            USB-71) n_usb71="${n}" ;;
            BT-ERR) n_bterr="${n}" ;;
        esac
    done
    info "kernel-watch (${log##*/}):${resumo}"
    if [[ "${n_joycon}" -gt 0 ]]; then
        warn "o kernel deu rate-limit no controle Nintendo/8BitDo ${n_joycon} vez(es) [JOYCON] — é a morte do 8BitDo em Bluetooth (muro do hid-nintendo, sem knob de módulo); a configuração estável é NO CABO"
    fi
    if [[ "${n_usb71}" -gt 0 ]]; then
        warn "storm USB (-71) registrado ${n_usb71} vez(es) no kernel-watch [USB-71] — confira a seção USB/dropout abaixo"
    fi
    if [[ "${n_bterr}" -gt 0 ]]; then
        warn "o rádio BT acumulou erros em ${n_bterr} janela(s) [BT-ERR] — rádio sujo; ver os conselhos de posicionamento acima"
    fi
}

# PLAT-03 item 2: os params do hefesto no cmdline — comparação /proc/cmdline
# (boot ATUAL) × configuration do kernelstub/grub (PRÓXIMO boot) = "aplicado"
# vs "pendente de reboot". A policy sysfs NUNCA entra aqui (ela mente).
check_cmdline_platform() {
    local owners="${HOME}/.local/state/hefesto-dualsense4unix/cmdline-owners.conf"
    local tok ativo agendado
    for tok in "usbcore.autosuspend=-1" "054c:0ce6:gn" "054c:0df2:gn"; do
        ativo=0; agendado=0
        grep -qF "${tok}" /proc/cmdline 2>/dev/null && ativo=1
        { [[ -r /etc/kernelstub/configuration ]] && grep -qF "${tok}" /etc/kernelstub/configuration 2>/dev/null; } && agendado=1
        { [[ -r /etc/default/grub ]] && grep -qF "${tok}" /etc/default/grub 2>/dev/null; } && agendado=1
        if [[ "${ativo}" -eq 1 ]]; then
            pass "cmdline: ${tok} APLICADO neste boot"
        elif [[ "${agendado}" -eq 1 ]]; then
            warn "cmdline: ${tok} agendado mas NÃO ativo — pendente de reboot"
        else
            warn "cmdline: ${tok} ausente — rode ./install.sh (o passo 3e aplica com MERGE no token único e registro de dono)"
        fi
    done
    # O kernel respeita SÓ UM token usbcore.quirks= — mais de um é bug de merge.
    local n_tokens
    n_tokens="$(grep -o 'usbcore\.quirks=' /proc/cmdline 2>/dev/null | wc -l || true)"
    if [[ "${n_tokens:-0}" -gt 1 ]]; then
        warn "MAIS DE UM token usbcore.quirks= no cmdline (${n_tokens}) — o kernel respeita só um; rode ./install.sh (o passo 3e funde num token único)"
    fi
    if [[ -f "${owners}" ]]; then
        info "donos registrados: $(tr '\n' ' ' < "${owners}")"
    fi
}

# ============================================================================
# G2 — doctor: "Rádio e pareamento" (sprint 2026-07-19-sprint-onda-g-gyro02-
# doctor.md). Tudo READ-ONLY; fecha o ciclo do que a Onda R instala (backport
# bluez 5.85 + hefesto-bt-agent.service) com visibilidade pro leigo. A causa
# medida do bond "meio-salvo" (Paired: yes / Bonded: no) é "No agent available
# for request type 2" (estudo 2026-07-19-estudo-bluez-backport-onda-r.md §4):
# nenhum agente D-Bus respondeu no momento do pareamento. O check 6 do sprint
# ("autoridade de exibição unknown presa") JÁ existe (NUMA-05/
# check_display_authority, mais abaixo) — não duplicado aqui.
# ============================================================================

# Compara a versão do bluez instalada com o piso 5.79 (abaixo dele: crashes
# crônicos de input/HIDP documentados no estudo da Onda R). Função PURA —
# só `dpkg --compare-versions`, sem tocar em pacote nenhum.
_bluez_version_verdict() {
    local ver="$1"
    if [[ -z "${ver}" ]]; then
        printf 'unknown\n'
        return
    fi
    if dpkg --compare-versions "${ver}" ge 5.79 2>/dev/null; then
        printf 'ok\n'
    else
        printf 'old\n'
    fi
}

check_bluez_backport_version() {
    if ! command -v dpkg-query >/dev/null 2>&1 || ! command -v dpkg >/dev/null 2>&1; then
        info "dpkg ausente (sistema não-Debian?) — pulo o check de versão do bluez"
        return
    fi
    local ver veredito
    ver="$(dpkg-query -W -f='${Version}' bluez 2>/dev/null || true)"
    veredito="$(_bluez_version_verdict "${ver}")"
    case "${veredito}" in
        ok)
            pass "bluez ${ver} >= 5.79 (sem os crashes crônicos de input/HIDP do 5.72)"
            ;;
        old)
            fail "bluez ${ver} < 5.79 — crashes crônicos de input/HIDP (heap corruption, 6x/5 dias medidos) documentados; aplique o backport: ./install.sh (passo ONDA-R aplica sozinho se os .debs estiverem em ~/.cache/hefesto-dualsense4unix/bluez-backport/; senão, gere-os: docs/process/estudos/2026-07-19-estudo-bluez-backport-onda-r.md §3)"
            ;;
        *)
            info "bluez não instalado via dpkg (ou versão ilegível) — pulo o check de versão"
            ;;
    esac
}

# hefesto-bt-agent.service (Onda R): agente NoInputNoOutput persistente que
# responde o D-Bus na hora do pareamento — sem ele, um pareamento disparado
# fora da GUI/daemon (bluetoothctl manual, Blueman, re-pair em massa pós-
# migração do backport) fica "meio-salvo". É unit de SISTEMA (WantedBy=multi-
# user.target, /etc/systemd/system/) — por isso `systemctl` sem --user, ao
# contrário de check_service.
check_bt_agent_service() {
    command -v systemctl >/dev/null 2>&1 || { info "systemctl ausente — não checo o agente de pareamento"; return; }
    local state
    state="$(systemctl is-active hefesto-bt-agent.service 2>/dev/null || true)"
    if [[ "${state}" == "active" ]]; then
        pass "hefesto-bt-agent.service ativo — pareamento fora da GUI/daemon tem agente D-Bus para responder"
    elif systemctl cat hefesto-bt-agent.service >/dev/null 2>&1; then
        warn "hefesto-bt-agent.service instalado mas ${state:-inativo} — bond meio-salvo à espreita (Paired sem Bonded); ligue: sudo systemctl enable --now hefesto-bt-agent.service"
    else
        warn "hefesto-bt-agent.service não instalado — pareamento fora da GUI/daemon pode ficar meio-salvo (Paired sem Bonded, 'No agent available for request type 2'); rode ./install.sh (ONDA-R aplica por default)"
    fi
}

# Normaliza um MAC para minúsculo sem ':' — mesma forma usada para comparar
# HID_UNIQ (sysfs) com o MAC do bluetoothctl (formatos diferem em caixa).
_mac_norm() {
    local m="${1,,}"
    printf '%s\n' "${m//:/}"
}

# HID_UNIQ de cada hidraw vivo, normalizado (um por linha). Existe em USB E
# BT (mesma fonte de sysfs_leds._read_mac); raiz parametrizada p/ teste.
_hidraw_uniqs() {
    local root="${1:-/sys/class/hidraw}"
    local f uniq
    for f in "${root}"/*/device/uevent; do
        [[ -r "${f}" ]] || continue
        uniq="$(sed -n 's/^HID_UNIQ=//p' "${f}" | head -1)"
        [[ -z "${uniq}" ]] && continue
        _mac_norm "${uniq}"
    done
}

# Dado UM bloco de `bluetoothctl info <mac>` + a lista de HID_UNIQ vivos,
# imprime o MAC quando o device é gamepad (Icon: input-gaming), está
# Connected: yes, E nenhum hidraw bate com ele — senão nada (silencioso).
# Função PURA: só parsing de texto, sem chamar bluetoothctl/sysfs.
_bt_gamepad_missing_hidraw() {
    local info="$1" hidraw_list="$2" mac
    mac="$(printf '%s\n' "${info}" | awk '/^Device /{print $2; exit}')"
    [[ -z "${mac}" ]] && return 0
    printf '%s\n' "${info}" | grep -q '^[[:space:]]*Icon: input-gaming' || return 0
    printf '%s\n' "${info}" | grep -q '^[[:space:]]*Connected: yes' || return 0
    if printf '%s\n' "${hidraw_list}" | grep -qxF "$(_mac_norm "${mac}")"; then
        return 0
    fi
    printf '%s\n' "${mac}"
}

check_bt_connected_sem_hidraw() {
    command -v bluetoothctl >/dev/null 2>&1 || { info "bluetoothctl ausente — pulo o check de pareamento meio-salvo"; return; }
    local macs mac inf hidraw_list resultado achou=0
    macs="$(timeout 4 bluetoothctl devices 2>/dev/null | awk '{print $2}')"
    if [[ -z "${macs}" ]]; then
        info "nenhum dispositivo Bluetooth pareado — sem 'Connected sem hidraw' possível"
        return
    fi
    hidraw_list="$(_hidraw_uniqs)"
    for mac in ${macs}; do
        inf="$(timeout 4 bluetoothctl info "${mac}" 2>/dev/null || true)"
        resultado="$(_bt_gamepad_missing_hidraw "${inf}" "${hidraw_list}")"
        if [[ -n "${resultado}" ]]; then
            achou=1
            fail "controle BT ${resultado} CONECTADO mas SEM hidraw correspondente (HID_UNIQ) — pareamento meio-salvo; despareie e repareie: bluetoothctl remove ${resultado} (depois PS no controle)"
        fi
    done
    [[ "${achou}" -eq 0 ]] && pass "todo device BT conectado (gamepad) tem hidraw correspondente"
}

# Dado UM bloco de `bluetoothctl info <mac>`, imprime o MAC quando o bond
# está "meio-salvo" (Paired: yes / Bonded: no) — senão nada. Função PURA,
# mesmo padrão de _bt_gamepad_missing_hidraw.
_bt_paired_sem_bonded() {
    local info="$1" mac
    mac="$(printf '%s\n' "${info}" | awk '/^Device /{print $2; exit}')"
    [[ -z "${mac}" ]] && return 0
    printf '%s\n' "${info}" | grep -q '^[[:space:]]*Paired: yes' || return 0
    printf '%s\n' "${info}" | grep -q '^[[:space:]]*Bonded: no' || return 0
    printf '%s\n' "${mac}"
}

check_bt_paired_sem_bonded() {
    command -v bluetoothctl >/dev/null 2>&1 || { info "bluetoothctl ausente — pulo o check de bond meio-salvo"; return; }
    local macs mac inf resultado achou=0
    macs="$(timeout 4 bluetoothctl devices 2>/dev/null | awk '{print $2}')"
    if [[ -z "${macs}" ]]; then
        info "nenhum dispositivo Bluetooth pareado — sem bond meio-salvo possível"
        return
    fi
    for mac in ${macs}; do
        inf="$(timeout 4 bluetoothctl info "${mac}" 2>/dev/null || true)"
        resultado="$(_bt_paired_sem_bonded "${inf}")"
        if [[ -n "${resultado}" ]]; then
            achou=1
            fail "${resultado} Paired mas NÃO Bonded — bond meio-salvo ('No agent available for request type 2'); cura: bluetoothctl remove ${resultado} && repareie (PS no controle); confira o hefesto-bt-agent.service ativo acima"
        fi
    done
    [[ "${achou}" -eq 0 ]] && pass "nenhum device BT com bond meio-salvo (Paired sem Bonded)"
}

# PLAT-01: relatório read-only do Proton pinado (proton_pin.py --report).
check_proton_pin() {
    local py="${ROOT_DIR}/src/hefesto_dualsense4unix/integrations/proton_pin.py"
    local conf="${ROOT_DIR}/assets/proton-pin.conf"
    if [[ ! -f "${py}" || ! -f "${conf}" ]] || ! command -v python3 >/dev/null 2>&1; then
        info "proton_pin.py/proton-pin.conf ausentes ou sem python3 — pulo o check do Proton pinado"
        return
    fi
    if [[ ! -f "${HOME}/.steam/steam/config/config.vdf" \
          && ! -f "${HOME}/.local/share/Steam/config/config.vdf" ]]; then
        info "Steam não detectada (sem config.vdf) — pulo o check do Proton pinado"
        return
    fi
    local resumo
    resumo="$(python3 "${py}" --report 2>/dev/null | python3 -c '
import json
import sys

d = json.load(sys.stdin)
print("name=" + str(d.get("pinned_name", "")))
print("present=" + ("1" if d.get("pinned_present") else "0"))
print("manifest=" + ("1" if d.get("pinned_manifest_ok") else "0"))
print("global=" + ("1" if d.get("global_is_pinned") else "0"))
off = d.get("games_off_pin") or []
print("off=" + str(len(off)))
leaky = d.get("games_leaky_proton") or []
print("leaky=" + " ".join(f"{a}:{t}" for a, t in leaky))
' 2>/dev/null)"
    if [[ -z "${resumo}" ]]; then
        warn "relatório do Proton pinado indisponível — rode: python3 ${py} --report"
        return
    fi
    local nome present manifest glob off leaky
    nome="$(sed -n 's/^name=//p' <<<"${resumo}")"
    present="$(sed -n 's/^present=//p' <<<"${resumo}")"
    manifest="$(sed -n 's/^manifest=//p' <<<"${resumo}")"
    glob="$(sed -n 's/^global=//p' <<<"${resumo}")"
    off="$(sed -n 's/^off=//p' <<<"${resumo}")"
    leaky="$(sed -n 's/^leaky=//p' <<<"${resumo}")"
    if [[ "${present}" == "1" && "${manifest}" == "1" ]]; then
        pass "Proton pinado presente e íntegro (${nome})"
    elif [[ "${present}" == "1" ]]; then
        warn "Proton pinado presente (${nome}) mas o manifesto do hefesto não bate — reinstale: ./install.sh (re-verifica o SHA256)"
    else
        warn "Proton pinado AUSENTE (${nome}) — rode ./install.sh (baixa, verifica o SHA256 e extrai por default)"
    fi
    if [[ "${glob}" == "1" && "${off:-0}" -eq 0 ]]; then
        pass "todos os jogos travados no Proton pinado (default global + por jogo)"
    else
        [[ "${glob}" != "1" ]] && warn "default global da Steam NÃO aponta pro Proton pinado — use o botão 'Travar Proton validado' (aba Sistema da GUI, com a Steam fechada) ou rode ./install.sh"
        [[ "${off:-0}" -gt 0 ]] && warn "${off} jogo(s) fora do Proton pinado — um upgrade de Proton pode reintroduzir o controle duplicado nesses jogos"
    fi
    if [[ -n "${leaky}" ]]; then
        warn "jogo(s) em Proton <= 9: ${leaky} — nessa família o PROTON_DISABLE_HIDRAW não existe e o controle físico VAZA duplicado no jogo; trave no Proton pinado"
    fi
}

# BROKER-01 (Onda S — fd-injection): o broker root que esconde o hidraw
# FÍSICO do DualSense do JOGO (cura de raiz do duplicado, complementar ao
# wrapper de launch acima). Verifica a unit de SISTEMA (não --user), o ping
# autenticado por SO_PEERCRED, a coerência do que está escondido (com o
# daemon ativo e o Modo Nativo) e — best-effort — a recusa a outro uid.
# Desenho: docs/process/estudos/2026-07-20-desenho-onda-s-broker-fd-injection.md §7.3.
check_hidraw_broker() {
    command -v systemctl >/dev/null 2>&1 || { info "systemctl ausente — não checo o broker hide-hidraw"; return; }
    if ! systemctl cat hefesto-hidraw-broker.socket >/dev/null 2>&1; then
        info "broker hide-hidraw não instalado (rode ./install.sh — BROKER-01 é DEFAULT, sem flag)"
        return
    fi
    local sock_state
    sock_state="$(systemctl is-active hefesto-hidraw-broker.socket 2>/dev/null || true)"
    if [[ "${sock_state}" != "active" ]]; then
        warn "hefesto-hidraw-broker.socket instalado mas ${sock_state:-inativo} — o físico NÃO é escondido do jogo (P2 duplicado volta); ligue: sudo systemctl enable --now hefesto-hidraw-broker.socket"
        return
    fi
    pass "hefesto-hidraw-broker.socket ativo"

    if ! command -v python3 >/dev/null 2>&1; then
        warn "python3 ausente — não dá para pingar o broker"
        return
    fi
    local ping_out
    if ! ping_out="$(python3 - <<'PYEOF' 2>/dev/null
import glob
import json
import os
import socket
import struct

s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.settimeout(2.0)
s.connect("/run/hefesto-hidraw-broker/broker.sock")
s.sendall(json.dumps({"cmd": "ping"}).encode("utf-8") + b"\n")
buf = b""
while not buf.endswith(b"\n"):
    chunk = s.recv(4096)
    if not chunk:
        raise SystemExit(1)
    buf += chunk
resp = json.loads(buf.decode("utf-8"))
print(f"ok={resp.get('ok')}")
print(f"peer_uid={resp.get('peer_uid')}")

s.sendall(json.dumps({"cmd": "status"}).encode("utf-8") + b"\n")
buf = b""
while not buf.endswith(b"\n"):
    chunk = s.recv(65536)
    if not chunk:
        raise SystemExit(1)
    buf += chunk
resp = json.loads(buf.decode("utf-8"))
hidden = resp.get("hidden") or []
print(f"hidden_count={len(hidden)}")

# Onda S (achado #9): teste FUNCIONAL do cmd `open` — a rede de segurança que
# a tabela de riscos do desenho (§9) promete para DeviceAllow=char-hidraw e
# CapabilityBoundingSet. ping/status/hide NÃO exercitam o open(2) real sob o
# device cgroup (DevicePolicy=closed): só o `open` prova que o fd-injection
# (giroscópio sobrevivendo ao hide) está vivo. Candidatos: nós já escondidos
# (status acima) + hidraw de Sony no sysfs; o validador do broker decide o
# que é físico (vpad uhid vira reject_not_physical_dualsense = pulado).
candidatos = list(hidden)
for uevent in sorted(glob.glob("/sys/class/hidraw/hidraw*/device/uevent")):
    try:
        with open(uevent, encoding="utf-8", errors="replace") as fh:
            texto = fh.read()
    except OSError:
        continue
    if "054C" not in texto.upper():
        continue
    node = "/dev/" + uevent.split("/")[4]
    if node not in candidatos:
        candidatos.append(node)

resultado = "skip"
detalhe = ""
tam_fd = struct.calcsize("i")
espaco = socket.CMSG_SPACE(2 * tam_fd)
for node in candidatos:
    s.sendall(json.dumps({"cmd": "open", "node": node}).encode("utf-8") + b"\n")
    buf = b""
    fds = []
    while not buf.endswith(b"\n"):
        chunk, anc, _flags, _addr = s.recvmsg(65536, espaco)
        for nivel, tipo, dados in anc:
            if nivel == socket.SOL_SOCKET and tipo == socket.SCM_RIGHTS:
                n = len(dados) // tam_fd
                fds.extend(struct.unpack(f"{n}i", dados[: n * tam_fd]))
        if not chunk:
            raise SystemExit(1)
        buf += chunk
    resp = json.loads(buf.decode("utf-8"))
    for fd in fds:
        try:
            os.close(fd)  # o doctor só PROVA o open; nunca segura o fd
        except OSError:
            pass
    if resp.get("ok") and fds:
        resultado = "ok"
        detalhe = node
        break
    erro = resp.get("error") or ""
    if erro == "reject_not_physical_dualsense":
        continue  # vpad/uhid: nem falha nem sucesso — segue para o próximo
    resultado = "fail"
    detalhe = f"{node} erro={erro} errno={resp.get('errno')}"
    break
print(f"open={resultado}")
print(f"open_detalhe={detalhe}")
PYEOF
)"; then
        warn "broker não respondeu no socket (/run/hefesto-hidraw-broker/broker.sock) — verifique: systemctl status hefesto-hidraw-broker.service"
        return
    fi

    local ok peer_uid hidden_count
    ok="$(sed -n 's/^ok=//p' <<<"${ping_out}")"
    peer_uid="$(sed -n 's/^peer_uid=//p' <<<"${ping_out}")"
    hidden_count="$(sed -n 's/^hidden_count=//p' <<<"${ping_out}")"
    hidden_count="${hidden_count:-0}"

    if [[ "${ok}" != "True" ]]; then
        warn "broker recusou o ping (autorização por SO_PEERCRED/uid falhou)"
        return
    fi
    if [[ "${peer_uid}" != "$(id -u)" ]]; then
        warn "broker ecoou peer_uid=${peer_uid}, esperado $(id -u) — SO_PEERCRED inconsistente"
    else
        pass "ping ok — peer_uid=${peer_uid} confere (SO_PEERCRED)"
    fi

    # Onda S (achado #9): veredito do teste funcional do cmd `open` (feito no
    # python acima, na MESMA lease). Com o open quebrado — DeviceAllow com
    # 'r' em vez de 'rw', CapabilityBoundingSet sem CAP_DAC_OVERRIDE, hidraw
    # como módulo não carregado — ping/status/hide continuam verdes (não
    # dependem do device cgroup) e o gyro morre em silêncio sob o hide.
    local open_res open_det
    open_res="$(sed -n 's/^open=//p' <<<"${ping_out}")"
    open_det="$(sed -n 's/^open_detalhe=//p' <<<"${ping_out}")"
    case "${open_res}" in
        ok)
            pass "cmd open serviu fd real via SCM_RIGHTS (${open_det}) — fd-injection do giroscópio operante"
            ;;
        fail)
            fail "cmd open do broker FALHOU (${open_det}) — o giroscópio morre sob o hide; confira DeviceAllow=char-hidraw rw e CapabilityBoundingSet (CAP_DAC_OVERRIDE) em /etc/systemd/system/hefesto-hidraw-broker.service e rode: sudo systemctl restart hefesto-hidraw-broker.service"
            ;;
        *)
            info "cmd open não testado (nenhum hidraw físico de DualSense visível agora)"
            ;;
    esac

    # Coerência escondidos x daemon ativo x Modo Nativo — só cruza se o
    # daemon responde IPC (sem ele não há campo native_mode pra cruzar).
    local sock native_mode=""
    sock="$(runtime_socket)"
    if [[ -S "${sock}" ]]; then
        native_mode="$(python3 - "${sock}" <<'PYEOF' 2>/dev/null
import json
import socket
import sys

s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.settimeout(2.0)
s.connect(sys.argv[1])
s.sendall(
    json.dumps({"jsonrpc": "2.0", "id": 1, "method": "daemon.state_full", "params": {}}).encode("utf-8")
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
print(res.get("native_mode"))
PYEOF
)"
    fi

    if [[ "${hidden_count}" -gt 0 ]]; then
        if [[ ! -S "${sock}" ]]; then
            fail "broker com ${hidden_count} nó(s) escondido(s) e o daemon PARADO — invariante quebrada (belts falharam); cura: sudo systemctl restart hefesto-hidraw-broker.service"
        elif [[ "${native_mode}" == "True" ]]; then
            warn "broker com ${hidden_count} nó(s) escondido(s) em Modo Nativo — o físico deveria estar exposto ao jogo"
        else
            pass "broker escondendo ${hidden_count} nó(s) físico(s) — o jogo só vê o vpad (giroscópio sobrevive via fd-injection)"
        fi
    else
        info "broker sem nós escondidos no momento (emulação desligada ou nenhum grab ativo)"
    fi

    # Recusa a outro uid — best-effort (só roda com sudo -n disponível e o
    # usuário nobody presente); nunca falha o doctor por esta checagem.
    if sudo -n true 2>/dev/null && id nobody >/dev/null 2>&1; then
        if sudo -n -u nobody python3 - <<'PYEOF' >/dev/null 2>&1
import json
import socket
import sys

s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.settimeout(2.0)
s.connect("/run/hefesto-hidraw-broker/broker.sock")
s.sendall(json.dumps({"cmd": "ping"}).encode("utf-8") + b"\n")
buf = s.recv(4096)
sys.exit(0 if buf else 1)
PYEOF
        then
            warn "broker respondeu ping para outro uid (nobody) — recusa por SO_PEERCRED/DAC NÃO está funcionando"
        else
            pass "broker recusa outro uid (nobody) — DAC do socket + SO_PEERCRED ok"
        fi
    else
        info "validação de recusa a outro uid pulada (sem sudo -n ou usuário nobody ausente)"
    fi
}

# GYRO-03: o giroscópio está chegando ao jogo? ------------------------------
# O vpad uhid (máscara DualSense Edge) expõe um nó evdev próprio de motion
# ("Hefesto Virtual DualSense PN Motion Sensors"). Com o espelho de motion do
# daemon vivo (PhysicalReportReader), esse nó AMOSTRA continuamente — o gyro
# de um DualSense real nunca fica em silêncio absoluto (ruído do sensor).
# Silêncio de ~1s = o gyro NÃO está fluindo pro jogo. READ-ONLY: leitura
# O_RDONLY sem grab, o mesmo probe validado à mão em 2026-07-19.

# Nós eventN dos Motion Sensors DOS VPADS (nunca os do físico — o nome do
# físico começa com "Sony..."/"DualSense..."; só o vpad tem o prefixo
# "Hefesto Virtual"). Fonte parametrizada p/ teste hermético.
_vpad_motion_event_nodes() {
    local src="${1:-/proc/bus/input/devices}"
    [[ -r "${src}" ]] || return 0
    awk '
        /^N: Name=/ {
            alvo = ($0 ~ /Hefesto Virtual DualSense P[0-9]+ Motion Sensors/)
        }
        alvo && /^H: Handlers=/ {
            for (i = 2; i <= NF; i++) {
                t = $i
                sub(/^Handlers=/, "", t)
                if (t ~ /^event[0-9]+$/) print t
            }
        }
    ' "${src}" 2>/dev/null
}

# Amostra ~1s de UM nó evdev (só leitura, sem grab) e imprime "vivo" quando
# chega pelo menos um evento EV_ABS de eixo de gyro/accel, ou "silencio".
# GYRO-03-FIX: o hid_playstation emite EV_MSC/MSC_TIMESTAMP neste nó a CADA
# report 0x01 do vpad, mesmo com a janela de motion NEUTRA (espelho morto) —
# stick/botão durante a amostra virava falso "vivo". Só EV_ABS (type=3) com
# code de gyro/accel (ABS_X..ABS_RZ = 0..5) prova gyro fluindo: espelho vivo
# = ruído do sensor mudando valor sempre; janela neutra = o input core
# suprime ABS repetido e NADA de EV_ABS sai (mesma lógica do probe manual de
# 2026-07-19). struct input_event (64-bit) = 24 B: 16 de timestamp + u16
# type + u16 code + s32 value → com `od -tu2 -w24`, type é o 9º campo e
# code o 10º.
_motion_node_sample() {
    local node="$1" dur="${2:-1}"
    local veredito
    veredito="$(timeout "${dur}" dd if="${node}" bs=24 2>/dev/null \
        | od -An -v -tu2 -w24 \
        | awk '$9 == 3 && $10 <= 5 { print "vivo"; exit }')"
    printf '%s\n' "${veredito:-silencio}"
}

check_vpad_motion() {
    local nodes
    nodes="$(_vpad_motion_event_nodes)"
    if [[ -z "${nodes}" ]]; then
        info "nenhum nó Motion de vpad agora (emulação desligada, backend uinput ou máscara xbox) — giroscópio via vpad não se aplica"
        return
    fi
    local ev node veredito
    for ev in ${nodes}; do
        node="/dev/input/${ev}"
        if [[ ! -r "${node}" ]]; then
            warn "sem permissão de leitura em ${node} — não deu para amostrar o giroscópio do vpad (regra udev/uaccess? rode como o usuário da sessão)"
            continue
        fi
        veredito="$(_motion_node_sample "${node}")"
        if [[ "${veredito}" == "vivo" ]]; then
            pass "giroscópio chegando ao jogo: SIM (${ev} amostrando)"
        else
            warn "giroscópio chegando ao jogo: NÃO (${ev} em silêncio por ~1s) — o espelho de motion do daemon não está alimentando este vpad; veja motion_streaming/motion_hz abaixo e o journal do daemon"
        fi
    done
    # Telemetria do daemon (motion_streaming/motion_hz por vpad) — contexto
    # extra quando o IPC responde; a amostragem acima já deu o veredito.
    local sock; sock="$(runtime_socket)"
    [[ -S "${sock}" ]] || return 0
    command -v python3 >/dev/null 2>&1 || return 0
    local out
    out="$(python3 - "${sock}" <<'PYEOF' 2>/dev/null
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
for item in (res.get("rumble_ff") or {}).get("per_vpad") or []:
    streaming = "sim" if item.get("motion_streaming") else "não"
    hz = item.get("motion_hz") or 0.0
    print(
        f"vpad do jogador {item.get('player')}: espelho de motion "
        f"{'ATIVO' if streaming == 'sim' else 'inativo'} ({hz:.0f} Hz)"
    )
PYEOF
)" || return 0
    if [[ -n "${out}" ]]; then
        while IFS= read -r linha; do info "${linha}"; done <<<"${out}"
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
    hdr "energia USB e rádio"
    check_usb_power_devices
    check_usb_power_hosts
    check_pcie_aspm
    check_power_saboteurs
    check_btusb_autosuspend
    check_bluez_fastconnectable
    check_bt_clone_ds4
    check_bt_radio
    check_bt_crc_counters
    check_kernel_watch
    check_cmdline_platform
    hdr "rádio e pareamento (G2)"
    check_bluez_backport_version
    check_bt_agent_service
    check_bt_connected_sem_hidraw
    check_bt_paired_sem_bonded
    hdr "applet COSMIC"
    check_applet
    hdr "detector de janela (autoswitch / perfil-por-jogo)"
    check_window_detect
    hdr "áudio (microfone)"
    check_wireplumber_source
    check_dualsense_sink_disabled
    check_audio_sink_muted
    hdr "Steam Input"
    check_steam_input
    hdr "controle no jogo (duplicação / wrapper de launch)"
    check_launch_wrapper
    check_vdf_poison
    check_dedup_ipc
    check_display_authority
    check_proton_pin
    hdr "broker hide-hidraw (BROKER-01 — cura de raiz do duplicado)"
    check_hidraw_broker
    hdr "giroscópio no jogo (vpad Motion)"
    check_vpad_motion
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
