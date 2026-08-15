#!/usr/bin/env bash
# doctor.sh — diagnóstico de saúde do Hefesto - Dualsense4Unix.
#
# Verifica daemon, serviço, socket IPC, regras udev (incluindo a consistência do
# nome de unit do hotplug), uinput, a gravabilidade do nó de LED do DualSense
# físico (cor por-controle via sysfs, regra 77), applet COSMIC (.desktop + ícone
# resolvível), o detector de janela do autoswitch (perfil-por-jogo) e os perfis
# INALCANÇÁVEIS por ele (sem critério de janela: nunca ativam sozinhos), o sequestro
# do microfone pelo WirePlumber e o alcance do controle; a autoridade de
# exibição do co-op (NUMA-05: quem manda em lightbar/numeração agora — jogo,
# daemon ou "unknown" — e a CAUSA quando presa em unknown); reconhece também,
# no journal do kernel, a assinatura de morte por Bluetooth do 8BitDo em modo
# Switch (cascata do hid-nintendo — informativo, não gerenciamos o controle) e
# a do DualSense que o driver do kernel ABORTOU no probe (PROBE-MORTO-PS-01 —
# aborto cruzado com o estado de agora: órfão AGORA é FAIL com a cura pronta,
# aborto que já recuperou é só informação);
# e (G2) o rádio/pareamento — versão do bluez vs. a faixa aceita (piso 5.79,
# teto 5.87: o UAF em dev_disconnected), o
# hefesto-bt-agent.service, bond "meio-salvo" por dois ângulos (Connected sem
# hidraw correspondente E Paired sem Bonded) e o sink de áudio padrão mudo;
# e (BROKER-01, Onda S) o broker root hide-hidraw fd-injection — unit de
# SISTEMA ativa, ping autenticado por SO_PEERCRED, coerência do que está
# escondido com o daemon/Modo Nativo e recusa a outro uid; e (Onda W) o
# patch DKMS do rtw88_usb (dongle WiFi) — status do módulo patchado vs.
# in-tree, a assinatura do fantasma USB (device retido após disconnect
# perdido: duplicata de idVendor:idProduct, colisão de rename wlx... e -71
# sem interface de rede) e o powersave EFETIVO do WiFi via NetworkManager
# conf.d (leitura de arquivo só — nunca nmcli/rfkill).
# Saída PASS/FAIL/WARN por item.
# Marcadores ASCII (compat sanitizer de anonimato).
#
# Uso: scripts/doctor.sh [--fix] [--fix-mic] [--restaurar-hidraw-uaccess]
#                        [--quiet] [--watch-dropout] [--suggest-port]
#   --fix             aplica correções seguras: reaplica udev, instala/reseta o
#                     fix de áudio do WirePlumber e cura as camadas 1 e 2 do
#                     microfone mudo (MIC-USB-01: mute persistido por rota e
#                     perfil da placa preso na entrada digital sem sinal).
#   --fix-mic         SÓ o microfone (camadas 1 e 2) — cura, mostra o veredito
#                     das duas e sai. Rota curta de quem quer o mic de volta.
#   --restaurar-hidraw-uaccess
#                     tira o bit de OUTROS dos nós /dev/hidraw* que estão
#                     abertos a qualquer usuário local E que NENHUMA regra udev
#                     explica (0666 -> 0660). Nunca roda sozinho: NÃO entra no
#                     --fix e NÃO entra no install. Decisão dela, 07/08/2026
#                     (resposta 16 do painel). Ver RESTAURO-SO-COM-SINTOMA-01.
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
FIX_MIC=0
RESTAURAR_HIDRAW=0
for arg in "$@"; do
    case "$arg" in
        --fix)            DO_FIX=1 ;;
        --fix-mic)        FIX_MIC=1 ;;
        --restaurar-hidraw-uaccess) RESTAURAR_HIDRAW=1 ;;
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

# COMPAT BLUEZ-586-CTL-01 (medido 22/07 nesta máquina): o bluetoothctl 5.86
# ficou MUDO no modo one-shot (`bluetoothctl list` imprime NADA, rc=0 — com
# ou sem TTY, com ou sem --timeout), enquanto o modo interativo funciona e o
# daemon está são no D-Bus. Esta função SOMBREIA o binário para todos os ~25
# usos deste script: roda o comando via modo interativo, tira ANSI/prompt e
# só emite o que vem DEPOIS do eco do próprio comando (o arranque imprime
# eventos [NEW]/SupportedUUIDs que não são resposta). Sem bluetoothctl no
# PATH, degrada para o comportamento antigo (command retorna 127 e os checks
# tratam vazio como "sem dados", como sempre trataram).
bluetoothctl() {
    command -v bluetoothctl >/dev/null 2>&1 || return 127
    printf '%s\nquit\n' "$*" | command timeout 8 bluetoothctl 2>/dev/null \
        | sed -e $'s/\x1b\\[[0-9;]*[A-Za-z]//g' -e 's/\r//g' -e 's/^\[bluetoothctl\]> //' \
        | awk -v cmd="$*" 'BEGIN{seen=0} $0==cmd{seen=1;next} !seen{next} $0=="quit"{exit} /^\[/{next} {print}'
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
    #
    # NOTA DATADA 06/08/2026: a lista tinha caducado de novo, e a própria regra
    # escrita acima é que apanhou. O `install_udev.sh` instala SEM FLAG também a
    # 82 (nosniff do Pro), a 83 (snapshot de bonds na borda udev) e a 84
    # (variante do clone 8BitDo) — linhas 132, 133 e 138 — e nenhuma das três era
    # conferida aqui. Quem instalasse antes delas existirem ficava sem as três,
    # em silêncio, e o doctor dava [OK]. As três entram na contagem.
    #
    # NOTA DATADA 09/08/2026 (OQ-6): entra a 72-hefesto-touchpad-motion-uaccess,
    # que o `install_udev.sh` também põe SEM FLAG. Ela é a que dá ACL da sessão
    # aos nós de ENTRADA do touchpad e dos sensores de movimento — a regra do
    # sistema (70-uaccess.rules) só marca `ID_INPUT_JOYSTICK`, e esses dois nós
    # são `ID_INPUT_TOUCHPAD`/`ID_INPUT_ACCELEROMETER`. A presença do ARQUIVO é
    # o que se cobra aqui; o EFEITO (a ACL existir no nó vivo) é outra pergunta,
    # e tem função própria — `check_input_uaccess`. As duas são necessárias:
    # a regra pode estar no disco e não ter pegado (ver o comentário de lá).
    local r found=0 missing=""
    local rules=(70-ps5-controller.rules 71-uhid.rules 71-uinput.rules
                 72-ps5-controller-autosuspend.rules
                 72-hefesto-touchpad-motion-uaccess.rules
                 76-dualsense-touchpad-libinput-ignore.rules
                 77-dualsense-leds.rules
                 78-dualsense-motion-not-joystick.rules
                 79-external-controller-leds.rules
                 80-motion-joydev-hide.rules
                 81-hefesto-usb-power.rules
                 81-hefesto-usb-host-power.rules
                 82-nintendo-pro-nosniff.rules
                 83-hefesto-bond-snapshot.rules
                 84-nintendo-pro-variant.rules)
    local total=${#rules[@]}
    for r in "${rules[@]}"; do
        if [[ -e "/etc/udev/rules.d/${r}" || -e "/usr/lib/udev/rules.d/${r}" ]]; then
            found=$((found + 1))
        else
            missing+=" ${r}"
        fi
    done
    if [[ "${found}" -eq "${total}" ]]; then
        pass "${total} regras udev canônicas presentes (70/71-uhid/71-uinput/72-autosuspend/72-uaccess/76/77/78/79/80/81-power/81-host/82/83/84)"
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
        _vpad09_qualifica_acesso "${node}" "${para_que}"
    else
        fail "${node} existe mas SEM permissão para o seu usuário — ${para_que} não vai funcionar. Rode: sudo bash scripts/install_udev.sh"
    fi
}

# VPAD-09: gravável AGORA pode ser só a ACL do uaccess, que o logind aplica NO
# LOGIN — depois do daemon de sessão subir (corrida perdida ao vivo em 21/07:
# EACCES no boot, vpad nenhum). O acesso determinístico é o dono de grupo
# 'hefesto' (regras 71-*), aplicado na criação do nó, antes de qualquer login.
_vpad09_qualifica_acesso() {
    local node="$1" para_que="$2" grp
    grp="$(stat -c '%G' "${node}" 2>/dev/null || true)"
    if [[ "${grp}" != "hefesto" ]]; then
        warn "${node} gravável só pela ACL do login — no boot o daemon pode perder a corrida contra o logind (VPAD-09). Rode: sudo bash scripts/install_udev.sh"
    elif id -nG 2>/dev/null | tr ' ' '\n' | grep -qx hefesto; then
        pass "${node} presente e gravável (${para_que}; grupo hefesto ativo — sem corrida no boot)"
    else
        info "${node} com grupo hefesto, mas sua sessão ainda não está no grupo (vale no próximo login) — até lá o acesso é a ACL do login (VPAD-09)"
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
        _vpad09_qualifica_acesso /dev/uhid "vibração nas duas máscaras"
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

# ---------------------------------------------------------------------------
# PROBE-MORTO-PS-01 — o DualSense que o driver do kernel ABORTOU no probe.
# ---------------------------------------------------------------------------
# check_hid_playstation (acima) só conferia se o MÓDULO carregou. Módulo
# carregado e controle invisível são compatíveis, e foi o que aconteceu 6x na
# máquina dela em 08/08/2026: o controle conecta no Bluetooth, acende a luz do
# PRÓPRIO firmware e não existe para o sistema — sem hidraw, sem input, sem nó
# de LED, sem bateria. A dona tinha dois controles ligados, a janela mostrava
# um, e nada em lugar nenhum do produto sabia dizer por quê.
#
# A assinatura no journal do kernel:
#
#   playstation 0005:054C:0CE6.0069: Failed to retrieve feature with reportID 32: -5
#   playstation 0005:054C:0CE6.0069: Failed to retrieve DualSense firmware info: -5
#   playstation 0005:054C:0CE6.0069: Failed to create dualsense.
#   playstation 0005:054C:0CE6.0069: probe with driver playstation failed with error -5
#
# NÃO é hardware — tese vetada por escrito por ela depois de dias perdidos
# nela. É CONTENÇÃO: dois DualSense subindo no mesmo adaptador com ~1 s de
# diferença; o segundo perde o canal de controle L2CAP, o BlueZ estoura o teto
# de 3 s (hidp_report_req_timeout) e o uhid achata o erro em -EIO (o -5 é
# máscara). A cadeia está medida elo a elo em
# assets/dkms/hid-playstation/README.md:62-114.
#
# Função PURA (stdin -> stdout), uma linha por instância hid que abortou:
# "INSTANCIA n_probe n_feature". O gate é o ABORTO (probe >= 1); a falha de
# feature é CORROBORAÇÃO da causa — contada e reportada, nunca exigida, porque
# um aborto por outro motivo não pode ficar invisível. Falha de feature SEM
# aborto é o transiente que o probe sobreviveu: sai vazio de propósito.
_hid_playstation_probe_scan() {
    sed -nE \
        -e 's/^.*playstation ([0-9A-Fa-f]{4}:[0-9A-Fa-f]{4}:[0-9A-Fa-f]{4}\.[0-9A-Fa-f]{4,}).*probe with driver playstation failed.*$/\1 probe/p' \
        -e 's/^.*playstation ([0-9A-Fa-f]{4}:[0-9A-Fa-f]{4}:[0-9A-Fa-f]{4}\.[0-9A-Fa-f]{4,}).*Failed to retrieve feature with reportID.*$/\1 feature/p' \
      | awk '
            $2 == "probe"   { p[$1]++ }
            $2 == "feature" { f[$1]++ }
            END {
                for (i in p) printf "%s %d %d\n", i, p[i], (i in f ? f[i] : 0)
            }
        ' | sort
}

# O estado ATUAL, que é quem decide o veredito: DualSense por Bluetooth em
# /sys/bus/hid/devices SEM o symlink `driver` — órfão é o que NÃO tem driver.
# Mesmo escopo estreito do scripts/bt_rebind_orphans.sh, e pelas mesmas razões:
# barramento 0005 (Bluetooth) é o único onde a contenção medida acontece, e
# exclui por construção o vpad do próprio hefesto, que nasce por uhid no
# barramento 0003; vendor 054C (Sony) é o dono do driver `playstation`. Só
# leitura de sysfs. HEFESTO_HID_DEVICES_DIR é a MESMA costura de teste do
# bt_rebind_orphans.sh — em produção nunca é definida.
_hid_playstation_orfaos_agora() {
    local raiz="${HEFESTO_HID_DEVICES_DIR:-/sys/bus/hid/devices}" dev id bus vid
    for dev in "${raiz}"/*; do
        [[ -d "${dev}" ]] || continue
        [[ -e "${dev}/driver" ]] && continue   # tem driver: foi adotado
        id="$(basename "${dev}")"
        bus="${id%%:*}"
        vid="${id#*:}"; vid="${vid%%:*}"
        [[ "${bus}" == "0005" ]] || continue
        [[ "${vid^^}" == "054C" ]] || continue
        printf '%s\n' "${id}"
    done
}

# O veredito. TRÊS casos, e a diferença entre eles é o que separa diagnóstico
# de ruído: dos 6 abortos de 08/08, TODOS recuperaram sozinhos em 2 a 20 min.
# Um FAIL por aborto que já passou ensina a ignorar o doctor — por isso o
# aborto é cruzado com o estado de AGORA:
#   1. controle órfão AGORA          -> FAIL (defeito ativo, cura pronta);
#   2. aborto na janela, sem órfão   -> info (histórico, nada a fazer);
#   3. nem uma coisa nem outra       -> pass.
# O órfão é conferido ANTES do journal e vale sozinho: o journal pode estar
# ilegível (sem grupo adm) e o sintoma continua sendo o sysfs.
#
# JANELA: `journalctl _TRANSPORT=kernel --since`, NUNCA `journalctl -k` — o -k
# implica o boot atual, e uma janela que atravessa reboot devolveria ZERO,
# indistinguível de "não houve nada". Esta casa já pagou quatro medições
# falsas por essa armadilha (índice de 08/08, §8).
#
# O TAMANHO da janela foi MEDIDO na máquina dela em 09/08, e a primeira
# escolha estava errada: com 24 h a mesma consulta via 1 dos 6 abortos de
# 08/08 (o boot dela é mais velho que um dia), e com 3 dias via os 6. Como o
# aborto recuperado é só `info`, uma janela larga custa pouco ruído e devolve
# o contexto inteiro do episódio. HEFESTO_DOCTOR_PROBE_JANELA ajusta.
#
# READ-ONLY, como todo check: aponta a cura (scripts/bt_rebind_orphans.sh) e
# a vigia que a chama de 2 em 2 min, e NÃO executa nenhuma das duas — o
# doctor confere e não cura.
check_hid_playstation_probe_abortado() {
    local janela="${HEFESTO_DOCTOR_PROBE_JANELA:-3 days ago}"
    local orfaos abortos tem_journal=0
    orfaos="$(_hid_playstation_orfaos_agora)"
    abortos=""
    if command -v journalctl >/dev/null 2>&1; then
        tem_journal=1
        abortos="$(journalctl _TRANSPORT=kernel --since "${janela}" --no-pager 2>/dev/null \
            | _hid_playstation_probe_scan)"
    fi

    if [[ -n "${orfaos}" ]]; then
        local id detalhe
        while read -r id; do
            [[ -z "${id}" ]] && continue
            detalhe=""
            if [[ -n "${abortos}" ]]; then
                detalhe="$(printf '%s\n' "${abortos}" \
                    | awk -v alvo="${id}" '$1 == alvo { printf "%dx aborto e %dx falha de feature no journal", $2, $3 }')"
            fi
            fail "DualSense ÓRFÃO AGORA (${id}): o driver playstation abortou a probe e o controle NÃO existe para o sistema — sem hidraw, sem input, sem nó de LED, sem bateria; invisível para o daemon e para a janela, mesmo conectado e com a luz acesa pelo próprio firmware${detalhe:+ (${detalhe})}. Cura pronta, sem reboot e sem derrubar quem já funciona: sudo /usr/local/lib/hefesto-dualsense4unix/bt_rebind_orphans.sh (no checkout: sudo bash scripts/bt_rebind_orphans.sh)"
        done <<<"${orfaos}"
        local tw=""
        if command -v systemctl >/dev/null 2>&1; then
            tw="$(systemctl is-active hefesto-bt-health-watchdog.timer 2>/dev/null || true)"
        fi
        if [[ "${tw}" == "active" ]]; then
            info "a vigia hefesto-bt-health-watchdog.timer está ativa e chama esse mesmo rebind de 2 em 2 minutos — se o controle voltar sozinho em até 2 min, foi ela"
        else
            warn "a vigia que chamaria o rebind sozinha (hefesto-bt-health-watchdog.timer) está ${tw:-ausente} — sem ela o controle órfão só volta à mão; ligue: sudo systemctl enable --now hefesto-bt-health-watchdog.timer"
        fi
        info "não é hardware (tese vetada por ela, por escrito, depois de dias perdidos nela): é contenção — dois DualSense subindo no mesmo adaptador com ~1 s de diferença; o segundo perde o canal de controle L2CAP e o BlueZ desiste no teto de 3 s (hidp_report_req_timeout). Cadeia medida: assets/dkms/hid-playstation/README.md:62-114"
        return
    fi

    if [[ -n "${abortos}" ]]; then
        local total_probe total_feature instancias
        total_probe="$(printf '%s\n' "${abortos}" | awk '{s += $2} END {printf "%d", s + 0}')"
        total_feature="$(printf '%s\n' "${abortos}" | awk '{s += $3} END {printf "%d", s + 0}')"
        instancias="$(printf '%s\n' "${abortos}" | awk '{printf "%s%s", (NR > 1 ? ", " : ""), $1}')"
        info "aborto de probe do hid-playstation na janela (${janela}), JÁ RECUPERADO: ${total_probe}x 'probe with driver playstation failed' em ${instancias} (${total_feature}x 'Failed to retrieve feature' antes) — nenhum DualSense está órfão AGORA, então não há o que fazer: é histórico, não defeito ativo (os 6 abortos de 08/08 voltaram sozinhos em 2 a 20 min, por reconexão)"
        info "se acontecer de novo COM o controle sumindo, a cura é o rebind (sudo /usr/local/lib/hefesto-dualsense4unix/bt_rebind_orphans.sh) e a vigia hefesto-bt-health-watchdog.timer a chama de 2 em 2 minutos; a causa medida é contenção de dois controles no mesmo adaptador, não hardware (assets/dkms/hid-playstation/README.md:62-114)"
        return
    fi

    if [[ "${tem_journal}" -eq 0 ]]; then
        info "nenhum DualSense órfão agora (todo device HID Sony por Bluetooth tem driver) — sem journalctl não dá para olhar o histórico de abortos de probe"
        return
    fi
    pass "nenhum DualSense órfão agora e nenhum aborto de probe do hid-playstation na janela (${janela})"
}

# COR-06/STATUS-07: probe READ-ONLY da gravabilidade do LED do DualSense FÍSICO.
# A regra 77 (default no install) dá escrita ao usuário nos nós de LED do kernel;
# sem ela o daemon só alcança a cor por hidraw — que em BT sofre EIO — e a cor
# por-controle degrada em silêncio (lightbar_source=="desired"). Só `test -w`:
# este check NUNCA escreve no nó. O vpad uhid do daemon também cria um nó
# rgb:indicator, mas o realpath do device dele vive em /devices/virtual/ e NÃO
# serve de alvo (filtrado). Sem DualSense físico conectado: pula sem falhar.
#
# LED-QUE-NÃO-AFIRMA-01 (13/08/2026): o `pass` daqui dizia "cor por-controle via
# sysfs OK (regra 77 valendo)" — e isso é uma afirmação de EFEITO que este check
# não tem como fazer, porque ele nunca escreveu no nó (o comentário três linhas
# acima já dizia isso). Ela lê o doctor justamente quando a cor NÃO está saindo:
# um `[ OK ]` afirmando que a cor funciona manda procurar no lugar errado. O
# texto passou a dizer o que foi medido — permissão de escrita — e `test -w` só
# derruba a hipótese "falta permissão"; a cor pode continuar sem sair por hidraw
# em EIO, por lightbar_source=="desired", ou por driver ausente. Há teste que
# reprova se a afirmação de efeito voltar: tests/unit/test_doctor_nao_afirma_efeito.py
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
        pass "nó de LED do DualSense físico GRAVÁVEL pelo usuário (${ok_nodes# }) — a regra 77 está valendo. Só \`test -w\`: este check NUNCA escreve no nó, então isto é PERMISSÃO, não prova de que a cor sai"
    else
        info "sem DualSense físico com nó de LED agora (só o controle virtual, ou nenhum) — pulo o teste de gravabilidade; conecte o controle p/ validar a regra 77"
    fi
}

# ---------------------------------------------------------------------------
# OQ-6 (09/08/2026) — o touchpad e o giroscópio funcionavam por ACIDENTE.
# ---------------------------------------------------------------------------
# A regra do SISTEMA que dá ACL aos nós de entrada
# (/usr/lib/udev/rules.d/70-uaccess.rules) só marca ID_INPUT_JOYSTICK, e o
# `input_id` do kernel classifica o nó de movimento como
# ID_INPUT_ACCELEROMETER e o do touchpad como ID_INPUT_TOUCHPAD. Nenhum dos
# dois casava, e regra nenhuma desta casa os cobria: o acesso vinha do grupo
# `input`, em que a usuária desta máquina está POR FORA do produto (instalador
# nenhum daqui toca esse grupo). Numa máquina nova, nada funciona — e o sintoma
# é a AUSÊNCIA de dado: `core/evdev_reader.py:1396` engole a PermissionError
# num `except Exception: continue`, o nó some do mapa e o daemon relata
# "esse controle não tem sensor".
#
# A cura é `assets/72-hefesto-touchpad-motion-uaccess.rules`.
#
# POR QUE ESTA FUNÇÃO EXISTE SE `check_udev` JÁ CONFERE O ARQUIVO: porque as
# duas perguntas são diferentes. `check_udev` responde "a regra está no disco?";
# esta responde "a regra PEGOU?". Uma regra udev só age no (re)add do device —
# um controle que já estava conectado quando a regra chegou continua sem ACL
# até o replug. Arquivo presente e efeito ausente é exatamente o estado que
# passa despercebido.
#
# CONFERE E NÃO CURA (regra da casa): diz o comando, nunca o executa. E
# distingue os DOIS jeitos de o nó estar legível — a ACL da sessão (que a
# regra entrega, e que existe em máquina limpa) e o grupo do nó (o acidente,
# que não existe em máquina limpa). Só o primeiro é PASS.
#
# FÍSICO E VIRTUAL SÃO CONTADOS SEPARADAMENTE, e isso não é preciosismo — foi
# um FALSO VERDE MEDIDO em 09/08/2026. Rodando a primeira versão desta função
# nesta máquina ela imprimiu "[PASS] ... em 2 nó(s)", e os dois nós eram
# `.../input/event259` e `event261`, ambos em
# `/sys/devices/virtual/misc/uhid/0003:054C:0DF2.008F` — os nós auxiliares do
# VPAD que o próprio daemon acabara de criar. Não havia DualSense físico
# conectado. O instrumento deu verde sobre um device que nós mesmos fabricamos,
# e ficou calado exatamente sobre o que a pergunta era (o controle dela).
# `check_led_sysfs_gravavel` já resolvia isto do jeito certo, com
# `[[ "${dev_real}" == */devices/virtual/* ]] && continue`.
#
# OS DOIS IMPORTAM, por motivos diferentes, e por isso nenhum é descartado:
#   - o FÍSICO é o que alimenta a interface (o widget de giroscópio da aba
#     Status, via `daemon/sensor_hub.py`) e o cursor/teclas do touchpad;
#   - o VIRTUAL é o que o JOGO abre na máscara DualSense — sem ACL nele, o
#     jogo não lê giroscópio nem touchpad do vpad.
# O que não pode acontecer é um verde do virtual passar por resposta sobre o
# físico. Quando não há físico agora, a função DIZ que não há.
check_input_uaccess() {
    local regra="72-hefesto-touchpad-motion-uaccess.rules"
    if [[ ! -e "/etc/udev/rules.d/${regra}" && ! -e "/usr/lib/udev/rules.d/${regra}" ]]; then
        fail "${regra} ausente — o touchpad e o giroscópio só funcionam para quem está no grupo 'input' por fora do produto (numa máquina nova, não funcionam). Rode: sudo bash scripts/install_udev.sh"
        return
    fi
    local node base nome vid dev_real eu classe
    local vistos_fis=0 vistos_virt=0
    local sem_acesso=() so_pelo_grupo=() sem_acesso_virt=() so_grupo_virt=()
    eu="$(id -un 2>/dev/null || true)"
    for node in /dev/input/event*; do
        [[ -e "${node}" ]] || continue
        base="$(basename "${node}")"
        # Âncora de FABRICANTE, igual à da regra — sem ela o check alarmaria
        # sobre um touchpad de notebook cujo nome também termina em "Touchpad",
        # que a regra nunca cobre. Instrumento e produto casam o MESMO conjunto.
        vid="$(cat "/sys/class/input/${base}/device/id/vendor" 2>/dev/null || true)"
        case "${vid}" in
            054c|057e) ;;
            *) continue ;;
        esac
        nome="$(cat "/sys/class/input/${base}/device/name" 2>/dev/null || true)"
        case "${nome}" in
            *"Motion Sensors"|*"Touchpad"|*"(IMU)") ;;
            *) continue ;;
        esac
        dev_real="$(readlink -f "/sys/class/input/${base}/device" 2>/dev/null || true)"
        if [[ "${dev_real}" == */devices/virtual/* ]]; then
            classe="virt"
            vistos_virt=$((vistos_virt + 1))
        else
            classe="fis"
            vistos_fis=$((vistos_fis + 1))
        fi
        if [[ ! -r "${node}" ]]; then
            [[ "${classe}" == "fis" ]] && sem_acesso+=("${base}") || sem_acesso_virt+=("${base}")
        elif command -v getfacl >/dev/null 2>&1 && [[ -n "${eu}" ]] \
             && ! getfacl -p "${node}" 2>/dev/null | grep -q "^user:${eu}:"; then
            [[ "${classe}" == "fis" ]] && so_pelo_grupo+=("${base}") || so_grupo_virt+=("${base}")
        fi
    done
    # O vpad primeiro e sempre em separado: ele é nosso, e um problema nele é
    # problema do jogo, não da interface.
    if [[ "${#sem_acesso_virt[@]}" -gt 0 ]]; then
        fail "o gamepad VIRTUAL tem ${#sem_acesso_virt[@]} nó(s) de touchpad/movimento sem leitura (${sem_acesso_virt[*]}) — na máscara DualSense o jogo não lê giroscópio nem touchpad do vpad. Rode: sudo bash scripts/install_udev.sh"
    elif [[ "${#so_grupo_virt[@]}" -gt 0 ]]; then
        warn "o gamepad VIRTUAL tem ${#so_grupo_virt[@]} nó(s) legíveis só pelo GRUPO (${so_grupo_virt[*]}), sem ACL da sessão — funciona nesta máquina e não numa limpa"
    fi
    if [[ "${vistos_fis}" -eq 0 ]]; then
        if [[ "${vistos_virt}" -gt 0 ]]; then
            info "nenhum controle FÍSICO com nó de touchpad/movimento agora — os ${vistos_virt} nó(s) vistos são do gamepad virtual (/devices/virtual). Conecte o controle para validar o caso que importa."
        else
            info "nenhum nó de touchpad/movimento presente agora (controle desligado?) — nada a conferir"
        fi
        return
    fi
    if [[ "${#sem_acesso[@]}" -gt 0 ]]; then
        fail "sem permissão de leitura em ${#sem_acesso[@]} de ${vistos_fis} nó(s) FÍSICOS de touchpad/movimento (${sem_acesso[*]}) — o daemon engole o EACCES e relata 'sem sensor'. A ACL nasce no (re)add do device: desconecte e reconecte o controle; se persistir, rode: sudo bash scripts/install_udev.sh"
        return
    fi
    if [[ "${#so_pelo_grupo[@]}" -gt 0 ]]; then
        warn "${#so_pelo_grupo[@]} de ${vistos_fis} nó(s) FÍSICOS de touchpad/movimento legíveis só pelo GRUPO do nó (${so_pelo_grupo[*]}), sem a ACL da sessão — funciona NESTA máquina (você está no grupo 'input') e NÃO funcionaria numa limpa. Reconecte o controle para a ${regra} pegar."
        return
    fi
    pass "touchpad e giroscópio com ACL da sessão em ${vistos_fis} nó(s) do controle físico — sem depender do grupo 'input'"
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
    # da saída, não o mic. O racional original está certo pela metade: monitor
    # NÃO é o mic do controle, então este check (que pergunta "o mic do DualSense
    # virou o padrão sozinho?") não tem o que reprovar aqui.
    #
    # O que ele NÃO podia continuar fazendo era chamar isso de "pass" e encerrar
    # o assunto: medido nesta máquina em 29/07/2026, a fonte padrão do sistema
    # ERA o monitor do alto-falante do próprio controle, e este [OK] era a única
    # linha do diagnóstico sobre o assunto. Ser um MONITOR é defeito PRÓPRIO, e
    # quem dá o veredito é `check_default_source_monitor`, logo abaixo.
    if [[ "${cur}" == *[Mm]onitor* ]]; then
        info "a fonte padrão é um MONITOR (${cur}) — não é o mic do DualSense; veredito em 'fonte de captura padrão'"
        return
    fi
    if [[ ! "${cur}" =~ [Dd]ual[Ss]ense ]]; then
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
    # O-PRODUTO-PROMOVE-E-RECLAMA-01 (10/08/2026): o PROMOTOR no disco também é
    # opt-in, e é o único que ela consegue dar.
    #
    # A incoerência foi medida no install dela, e terminava em `[FAIL]` na tela:
    #
    #   [FAIL] DualSense é o microfone ATIVO com outra fonte disponível
    #   [ OK ] a fonte de captura padrão é uma entrada de verdade (alsa_input...DualSense...)
    #
    # Duas linhas seguidas, o mesmo aparelho, vereditos opostos — e as seis
    # linhas seguintes todas OK. O motivo: em 08/08 (MONITOR-QUE-VENCE-01) o
    # drop-in 51 deixou de SUPRIMIR e passou a PROMOVER a entrada do controle
    # (`priority.session = 1500`), e ele entra por DEFAULT no install
    # (`WITH_WIREPLUMBER_FIX=1`). O produto passou a criar a condição que este
    # check continuou acusando. O nome do arquivo ainda diz "no-default-source",
    # que é o fóssil da regra antiga.
    #
    # E o opt-in que existia era uma VARIÁVEL DE AMBIENTE. Pela regra desta casa
    # (*"tudo tem que focar em funcionar na interface do app e no install"*),
    # opt-in que só se alcança exportando env não é opt-in dela: é opt-in de
    # quem lê o código. O promotor no disco, sim, é gesto dela — ele só existe
    # se o install rodou sem `--keep-dualsense-mic` ou se ela clicou "Ligar" na
    # aba Emulação.
    #
    # Continua ALARMANDO no caso que o check foi criado para pegar: promotor
    # ausente e o DualSense virando padrão sozinho, que é o mic dela sequestrado
    # sem ninguém pedir.
    if [[ -f "${HOME}/.config/wireplumber/wireplumber.conf.d/51-hefesto-dualsense-no-default-source.conf" ]]; then
        pass "microfone ativo é o DualSense (o promotor está instalado — foi pedido)"
        return
    fi
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

# --- FONTE-PADRAO-01: a fonte de captura padrão é um MONITOR ----------------
#
# MEDIDO nesta máquina em 29/07/2026, com o DualSense no cabo:
#
#   $ pactl get-default-source
#   alsa_output.usb-...DualSense...analog-surround-40.monitor
#
# Monitor é o loopback da SAÍDA. Enquanto ele for a fonte padrão, todo
# aplicativo que gravar sem escolher a fonte na mão capta o som que SAI do
# controle — jogo, música, a chamada inteira — e nunca a voz de quem fala. Não é
# "mic ausente": é mic TROCADO por um gravador de tela sonoro, e passa
# despercebido porque o medidor mostra sinal.
#
# A causa está documentada no próprio drop-in 51, que o install instala por
# DEFAULT: rebaixar o `alsa_input` do DualSense para ele não ser eleito padrão
# sozinho é a política certa, mas o rebaixamento faz o monitor do SINK do mesmo
# controle (que herda a prioridade alta da saída) ganhar a eleição. Somando a
# isso, o `default.configured.audio.source` persistido aqui apontava para
# `alsa_input...analog-stereo` — uma source que NÃO EXISTE neste perfil, rastro
# da cura de camada 2 que a medição de 26/07 refutou. Configurado num fantasma,
# o WirePlumber cai na eleição automática e o monitor vence.
#
# Classificação da fonte padrão. Função PURA: recebe o NOME e imprime
# `monitor` | `captura` | `vazio`. No PipeWire todo monitor termina em
# `.monitor` — o sufixo é do nó, não uma heurística de nome.
_default_source_classe() {
    local nome="$1"
    if [[ -z "${nome}" ]]; then
        printf 'vazio\n'
    elif [[ "${nome}" == *.monitor ]] || [[ "${nome}" == *.[Mm]onitor ]]; then
        printf 'monitor\n'
    else
        printf 'captura\n'
    fi
}

# 0 quando o mic do DualSense PODE ser eleito fonte padrão do sistema.
#
# Três sinais EXPLÍCITOS, nenhum adivinhado — e a ordem é a hierarquia de quem
# manda. Isto existe para a cura não desfazer escolha de ninguém: promover o
# controle por conta própria reabriria a queixa que criou o drop-in 51 ("o
# controle fica mexendo no microfone") e faria `check_wireplumber_source`
# REPROVAR a máquina que acabamos de curar.
_prefere_mic_do_dualsense() {
    local conf="${HOME}/.config/wireplumber/wireplumber.conf.d"
    # 1. Quem DESLIGOU de propósito vem antes de tudo: o drop-in 52
    #    (`--disable-source` / `install --with-wireplumber-disable-mic`) é a
    #    escolha explícita de "o controle é só-HID". Mesmo precedente do
    #    `check_dualsense_sink_disabled` e do passo 10 do install.
    [[ -f "${conf}/52-hefesto-dualsense-disable-source.conf" ]] && return 1
    # 2. Opt-in explícito da usuária — a MESMA variável que
    #    check_wireplumber_source, check_usb_audio_off e system_check.py
    #    (_dualsense_mic_intended) já honram.
    case "${HEFESTO_DUALSENSE4UNIX_DUALSENSE_MIC_INTENDED:-}" in
        1|true|yes|TRUE|YES) return 0 ;;
    esac
    # 3. O drop-in 51 é a política DEFAULT do install: rebaixar. Enquanto ele
    #    estiver no lugar, o controle é a ÚLTIMA opção — não a primeira. Sua
    #    ausência (ex.: `fix_wireplumber_default_source.sh --promote-source`,
    #    `mic promote`) é a promoção explícita.
    [[ -f "${conf}/51-hefesto-dualsense-no-default-source.conf" ]] && return 1
    return 0
}

# PURA: 0 quando a PORTA ATIVA da source `$1` está marcada `not available` pelo
# ALSA, no texto de `LC_ALL=C pactl list sources` (`$2` ou stdin).
#
# Este é o segundo degrau do critério de porta, e ele foi medido nesta máquina em
# 29/07/2026. Ter porta ativa não basta: a entrada analógica da onboard tem
# `Active Port: analog-input-front-mic` e as TRÊS portas de captura dela estão
# `not available` (nada plugado no jack). Ela é uma fonte de captura legítima e
# vai gravar silêncio. A entrada do DualSense, no mesmo instante, tinha porta com
# disponibilidade `unknown` e gravou pico 4606 na medição de 26/07 — por isso
# `unknown` conta como USÁVEL e só o `not available` explícito reprova.
#
# Serve para DIZER a verdade, nunca para escolher escondido: quem decide quem é a
# fonte padrão é `_prefere_mic_do_dualsense`, com os sinais explícitos dela.
_source_porta_ativa_indisponivel() {
    awk -v alvo="$1" '
        /^[[:space:]]+Name: / {
            atual = substr($0, index($0, ": ") + 2)
            next
        }
        atual != alvo { next }
        /^[[:space:]]+Active Port: / {
            ativa = substr($0, index($0, ": ") + 2)
            next
        }
        # Linha de porta: `<chave>: <descrição> (type: ..., not available)`.
        # O `(` é o que separa porta de `Volume:`/`Latency:` e das propriedades
        # (que usam ` = `, não `: `).
        /^[[:space:]]+[A-Za-z0-9_-]+: .*\(/ {
            linha = $0
            sub(/^[[:space:]]+/, "", linha)
            p = index(linha, ": ")
            if (p < 2) next
            chave = substr(linha, 1, p - 1)
            if (chave ~ /[[:space:]]/) next
            indisp[chave] = (linha ~ /not available/)
            next
        }
        END { exit ((ativa != "" && indisp[ativa]) ? 0 : 1) }
    ' "${2:--}"
}

# Melhor fonte de CAPTURA de verdade num `pactl list sources short` (arquivo ou
# stdin). `$1` = 1 para preferir o DualSense, 0 para deixá-lo como último
# recurso. Silêncio = não há nenhuma fonte de captura.
#
# Monitor NUNCA entra: é ele o defeito. E o DualSense nunca é DESCARTADO — um
# mic de verdade, mesmo o do controle, é melhor que gravar o próprio
# alto-falante; ele só perde a vez para outra entrada quando a política manda.
# Função PURA: só parsing, nenhuma escrita.
_melhor_source_de_captura() {
    awk -v prefere="${1:-0}" '
        tolower($2) ~ /\.monitor$/ { next }
        $2 == "" { next }
        {
            if (tolower($2) ~ /dualsense/) { if (ds == "") ds = $2 }
            else if (outro == "") outro = $2
        }
        END {
            if (prefere == 1) { escolha = (ds != "") ? ds : outro }
            else             { escolha = (outro != "") ? outro : ds }
            if (escolha != "") print escolha
        }
    ' "${2:--}"
}

# PURA: filtra um `pactl list sources short` (stdin) e deixa passar só as fontes
# cuja porta ativa NÃO está explicitamente `not available`. `$1` = o texto de
# `LC_ALL=C pactl list sources` (o longo), de onde sai a disponibilidade.
#
# Existe para que o CHECK e a CURA usem o mesmo critério. Enquanto cada um tinha
# o seu, o doctor reprovava e mandava eleger a onboard, e o `--fix-mic` — que já
# filtrava — se recusava a eleger a mesma onboard. Duas verdades no mesmo
# programa, e a que ela lia na tela era a errada (RECEITA-ERRADA-01, 06/08/2026).
_sources_com_porta_usavel() {
    local longo="$1" linha nome
    while IFS= read -r linha; do
        [[ -n "${linha}" ]] || continue
        nome="$(printf '%s\n' "${linha}" | awk '{print $2}')"
        if [[ -n "${nome}" ]] \
           && printf '%s\n' "${longo}" | _source_porta_ativa_indisponivel "${nome}"; then
            continue
        fi
        printf '%s\n' "${linha}"
    done
}

check_default_source_monitor() {
    command -v pactl >/dev/null 2>&1 || { info "pactl ausente — não checo a fonte de captura padrão"; return; }
    local cur classe
    cur="$(pactl get-default-source 2>/dev/null || true)"
    classe="$(_default_source_classe "${cur}")"
    if [[ "${classe}" == "vazio" ]]; then
        info "não consegui ler a fonte de captura padrão (PipeWire parado?)"
        return
    fi
    if [[ "${classe}" != "monitor" ]]; then
        pass "a fonte de captura padrão é uma entrada de verdade (${cur})"
        # A METADE QUE FALTAVA. Sair daqui com [OK] e nada mais era como o
        # "pass" que aprovava o monitor: a fonte pode ser uma entrada legítima e
        # gravar silêncio, porque a porta ativa dela está `not available`. Medido
        # em 29/07 nesta máquina: eleita a entrada da onboard, as três portas de
        # captura estavam sem nada plugado, e o único mic que captava era o do
        # controle. Isto é INFO, não reprovação — quem manda na promoção é ela.
        local sources_txt
        sources_txt="$(LC_ALL=C pactl list sources 2>/dev/null || true)"
        if printf '%s\n' "${sources_txt}" | _source_porta_ativa_indisponivel "${cur}"; then
            info "  mas a porta ativa dela está indisponível (nada plugado) — vai gravar silêncio"
            local src_ds
            src_ds="$(LC_ALL=C pactl list sources short 2>/dev/null | _dualsense_source_nome)"
            if [[ -n "${src_ds}" ]] \
               && ! printf '%s\n' "${sources_txt}" | _source_porta_ativa_indisponivel "${src_ds}"; then
                info "  o mic do DualSense TEM porta usável agora — para elegê-lo: hefesto-dualsense4unix mic promote"
            fi
        fi
        return
    fi
    # RECEITA-ERRADA-01 (06/08/2026) — a mensagem mandava rodar `--fix-mic` SEM
    # saber se ele tem o que fazer, e o alvo que ela oferecia saía de uma lista
    # SEM o filtro de porta que a cura aplica. Nesta máquina isso produziu as
    # duas metades do mesmo defeito:
    #
    #   - MEDIDO em 06/08, sem webcam e sem controle no cabo: o check reprovava
    #     e mandava rodar `--fix-mic`; o `--fix-mic` respondia "não há nenhuma
    #     fonte de captura com porta usável para eleger" e não fazia nada. A
    #     receita levava a um comando que não podia funcionar;
    #   - MEDIDO em 29 e 30/07: o check oferecia `pactl set-default-source
    #     <onboard>`, cujas três portas estão `not available` — o pactl aceita,
    #     o WirePlumber não consegue honrar e REELEGE o monitor. A receita
    #     levava ao lugar errado, e o defeito voltava sozinho.
    #
    # Agora o alvo sai do MESMO filtro que a cura usa, então check e cura não
    # podem mais discordar; e quando não há alvo, o texto diz o que está
    # acontecendo em vez de apontar para um comando impotente.
    local prefere=0 alvo longo
    _prefere_mic_do_dualsense && prefere=1
    longo="$(LC_ALL=C pactl list sources 2>/dev/null || true)"
    alvo="$(LC_ALL=C pactl list sources short 2>/dev/null \
            | _sources_com_porta_usavel "${longo}" \
            | _melhor_source_de_captura "${prefere}")"
    if [[ -n "${alvo}" ]]; then
        fail "a fonte de captura padrão é um MONITOR (${cur}) — o que qualquer app gravar é o áudio de SAÍDA, não a voz; rode: scripts/doctor.sh --fix-mic"
        info "  cura: pactl set-default-source ${alvo}"
    else
        fail "a fonte de captura padrão é um MONITOR (${cur}) — o que qualquer app gravar é o áudio de SAÍDA do sistema, não a voz, e o medidor de nível ainda mostra sinal (parece funcionando)"
        info "  o --fix-mic NÃO resolve este caso: ele só sabe ELEGER outra fonte de captura, e não há nenhuma com porta usável nesta máquina agora"
        info "  o que resolve é hardware: conecte um mic, uma webcam com mic, ou o DualSense (no cabo, ou por Bluetooth com o mic ligado)"
    fi
    # O rastro que explica o sintoma: configurado num nó que não existe mais, o
    # WirePlumber cai na eleição automática e o monitor ganha do mic rebaixado.
    local estado cfg
    estado="${HOME}/.local/state/wireplumber/default-nodes"
    if [[ -r "${estado}" ]]; then
        cfg="$(sed -n 's/^default\.configured\.audio\.source=//p' "${estado}" | head -n1)"
        if [[ -n "${cfg}" ]] \
           && ! LC_ALL=C pactl list sources short 2>/dev/null | awk -v n="${cfg}" '$2 == n { achou = 1 } END { exit (achou ? 0 : 1) }'; then
            info "  a fonte configurada em ${estado} é um FANTASMA (${cfg}): não existe entre as sources de agora"
        fi
    fi
}

# Cura de FONTE-PADRAO-01. Chamada pelo `fix_mic_dualsense` (logo, pelo --fix e
# pelo --fix-mic), DEPOIS da camada 2: é a troca de perfil que decide qual
# `alsa_input` existe, e eleger antes elegeria o nó errado.
fix_default_source_monitor() {
    command -v pactl >/dev/null 2>&1 || return 0
    local cur
    cur="$(pactl get-default-source 2>/dev/null || true)"
    # Só age no defeito. Fonte de captura de verdade — QUALQUER uma, inclusive
    # uma que não seja a que escolheríamos — é escolha de quem usa a máquina, e
    # não se mexe no que funciona.
    [[ "$(_default_source_classe "${cur}")" == "monitor" ]] || return 0
    local prefere=0 alvo
    _prefere_mic_do_dualsense && prefere=1

    # FONTE-PADRÃO-01, segunda metade — a fiação que faltava, medida em 30/07 num
    # `uninstall` + `install` limpos na máquina da mantenedora.
    #
    # O `_source_porta_ativa_indisponivel` já existia, com a medição escrita ao
    # lado dele, e NINGUÉM o chamava: o `_melhor_source_de_captura` escolhia a
    # primeira entrada não-DualSense e pronto. Nesta máquina isso elegia a onboard
    # `alsa_input.pci-...analog-stereo`, cujas TRÊS portas de captura estão
    # `not available` (nada plugado no jack). O `pactl set-default-source` até
    # aceita — e o WirePlumber, que não consegue honrar um nó sem porta usável,
    # reelege sozinho e volta para o MONITOR. A cura reportava sucesso e o defeito
    # continuava na tela, o que é pior do que não curar.
    #
    # Aqui a lista de candidatos é filtrada ANTES da escolha: fonte cuja porta
    # ativa está explicitamente indisponível sai da disputa. `unknown` continua
    # valendo — é o caso da entrada do DualSense, que grava de verdade (medido:
    # pico 441 num quarto silencioso, contra pico 0 do silêncio digital).
    #
    # O filtro virou `_sources_com_porta_usavel` (06/08/2026) para que o CHECK
    # ofereça exatamente o alvo que a CURA elegeria — antes cada um tinha o seu
    # critério, e a tela dizia uma coisa e o `--fix-mic` fazia outra.
    local lista_curta lista_completa _linha _nome
    lista_completa="$(LC_ALL=C pactl list sources 2>/dev/null || true)"
    lista_curta="$(LC_ALL=C pactl list sources short 2>/dev/null \
                   | _sources_com_porta_usavel "${lista_completa}")"
    while IFS= read -r _linha; do
        [[ -n "${_linha}" ]] || continue
        _nome="$(printf '%s\n' "${_linha}" | awk '{print $2}')"
        [[ -n "${_nome}" ]] || continue
        printf '%s\n' "${lista_curta}" | awk -v n="${_nome}" '$2 == n { achou = 1 } END { exit (achou ? 0 : 1) }' \
            || info "  ${_nome}: porta de captura indisponível (nada plugado) — fora da disputa"
    done < <(LC_ALL=C pactl list sources short 2>/dev/null || true)

    alvo="$(printf '%s\n' "${lista_curta}" | _melhor_source_de_captura "${prefere}")"
    if [[ -z "${alvo}" ]]; then
        # RECEITA-ERRADA-01: dizer que não deu não basta. O estado em que ela
        # fica é o defeito INTEIRO de pé — e ele não parece defeito, porque o
        # medidor de nível mostra sinal (é o áudio de saída da máquina).
        warn "a fonte padrão é um MONITOR (${cur}) e não há nenhuma fonte de captura com porta usável para eleger"
        info "  enquanto isso durar, TUDO o que qualquer aplicativo gravar é o áudio de SAÍDA do sistema, não a voz"
        info "  esta cura só sabe eleger outra fonte de captura — sem nenhuma, o que resolve é conectar um mic, uma webcam com mic, ou o DualSense"
        return 0
    fi
    if pactl set-default-source "${alvo}" 2>/dev/null; then
        pass "fonte padrão trocada do monitor para a entrada ${alvo} (FONTE-PADRAO-01)"
    else
        warn "falha ao eleger ${alvo} como fonte padrão (a padrão segue o monitor ${cur})"
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

# --- MIC-USB-01: as três camadas de mudo empilhadas -------------------------
#
# Medido ao vivo em 25/07, com o controle no cabo: o microfone estava mudo por
# TRÊS motivos diferentes, em três donos diferentes, e cada cura revelava o de
# baixo. A aba Status dizia a verdade o tempo todo — o medidor era a única coisa
# funcionando. Duas dessas camadas são do WirePlumber e cabem aqui:
#
#   camada 1 — MUTE PERSISTIDO POR ROTA. O WirePlumber guarda mute e volume por
#     ROTA de placa em ~/.local/state/wireplumber/default-routes e restaura
#     fielmente a cada conexão, SEM NADA NO LOG. Sobrevive a reboot, replug e
#     reinstalação. Foi diagnosticado à mão uma vez e VOLTOU — a prova de que um
#     conserto que não é código não é conserto, é adiamento. Por isso ele está
#     aqui.
#   camada 2 — PERFIL DA PLACA NA ENTRADA SEM SINAL. O DualSense expõe
#     `input:analog-stereo` (onde o microfone realmente vive, marcado
#     `available: no`) e `input:iec958-stereo` (S/PDIF, `available: yes` e SEM
#     SINAL). O WirePlumber escolhe por disponibilidade e marca a analógica como
#     indisponível porque a detecção de jack não vê fone plugado — a porta se
#     chama `analog-input-headset-mic`. Mas o microfone EMBUTIDO usa esse mesmo
#     caminho: no mixer ALSA o controle de captura se chama literalmente
#     `Headset`. Resultado: sem fone plugado o perfil cai no S/PDIF e a gravação
#     dá pico 0.
#   camada 3 — o mudo no FIRMWARE do controle. Não é do WirePlumber e não se vê
#     por aqui: vive no `daemon.state_full` (`audio.mic_mudo`) e agora tem cura
#     pelo `mic.set` do IPC (`hefesto-dualsense4unix mic unmute`).
#
# Nada aqui hardcoda o nome do card ou da source: eles carregam o nome do
# produto e o sufixo da porta USB, e mudam de máquina para máquina.

# Rotas do DualSense com `"mute":true` no estado persistido do WirePlumber,
# SEPARADAS POR DIREÇÃO. `$2` = `input` (captura — o microfone; é o default) ou
# `output` (o alto-falante embutido do controle).
#
# A separação é a cura de um falso positivo MEDIDO em 28/07 nesta máquina. O
# filtro antigo casava qualquer rota cujo nome tivesse "dualsense", e a única
# rota muda do arquivo era `...:output:analog-output` — o ALTO-FALANTE. O
# portão reprovava o MICROFONE por causa da caixa de som, e essa linha [FAIL]
# levou dois levantamentos do mesmo dia a conclusões opostas. Só rota de
# CAPTURA pode falar pelo microfone; o alto-falante mudo é escolha legítima da
# usuária e vira INFO, nunca reprovação.
#
# A chave de rota é `<card>:<direção>:<porta>`, e a direção vem LOGO depois do
# nome da placa: por isso o `[^=:]*` entre "sense" e a direção, que proíbe o
# casamento de atravessar um `:`. Sem esse detalhe as entradas `:profile:` do
# mesmo arquivo entrariam pela porta dos fundos — o nome do perfil é
# `output:analog-surround-40+input:analog-stereo` e traz as duas palavras.
#
# Imprime a CHAVE de cada rota muda (uma por linha); silêncio = nada a fazer.
# Função PURA: recebe o arquivo, não escreve nada, não chama pactl.
_dualsense_rotas_mudas() {
    local arquivo="${1:-${HOME}/.local/state/wireplumber/default-routes}"
    local direcao="${2:-input}"
    [[ -r "${arquivo}" ]] || return 0
    # `|| true`: silêncio é a resposta NORMAL (nada mudo) e grep sai 1 nesse
    # caso — deixar o 1 escapar faria o chamador confundir "está tudo bem" com
    # "o check quebrou".
    grep -iE "^[^=]*dual[[:alnum:]_]*sense[^=:]*:${direcao}:[^=]*=.*\"mute\":[[:space:]]*true" \
        "${arquivo}" 2>/dev/null | sed -E 's/=.*$//' || true
}

# Nome da source de CAPTURA do DualSense em `pactl list sources short` (arquivo
# ou stdin). Só `alsa_input.*` — o `.monitor` do sink também casa "DualSense" no
# nome mas é o loopback da SAÍDA, não o microfone. Função PURA.
_dualsense_source_nome() {
    awk 'tolower($2) ~ /^alsa_input\..*dualsense/ { print $2; exit }' "${1:--}"
}

# Interpreta a saída do `pactl get-source-mute` (texto do pactl, LC_ALL=C).
# Imprime muted | unmuted | unknown. Função PURA (espelha _wpctl_volume_muted).
_source_mute_veredito() {
    local out="$1"
    if [[ -z "${out}" ]]; then
        printf 'unknown\n'
    elif printf '%s' "${out}" | grep -qiE 'mute:[[:space:]]*(yes|sim)'; then
        printf 'muted\n'
    elif printf '%s' "${out}" | grep -qiE 'mute:[[:space:]]*(no|não)'; then
        printf 'unmuted\n'
    else
        printf 'unknown\n'
    fi
}

# Camada 2, em uma linha: `card<TAB>perfil_ativo<TAB>perfil_alvo` a partir de um
# `pactl list cards` (arquivo ou stdin). `perfil_alvo` vazio = nada a trocar.
# Silêncio total = não há DualSense.
#
# ATENÇÃO — este decisor foi REESCRITO em 26/07/2026, e o motivo importa mais
# que o código. A versão anterior trocava o perfil sempre que a entrada ativa
# fosse `iec958`, mirando `input:analog-stereo`, porque a sprint MIC-USB-01
# afirmava que o microfone "vive" na entrada analógica.
#
# Medido no hardware, com o controle no cabo: o perfil analógico estava marcado
# `available: no` pelo próprio ALSA, e forçá-lo produzia uma source SEM NENHUMA
# PORTA DE CAPTURA, que entrega 327.680 bytes de silêncio digital. O
# `iec958-stereo` — o que a sprint mandava evitar — gravou pico 4606 e RMS 374.
# Ou seja: a "cura" SILENCIAVA o microfone de quem a rodasse.
#
# A regra nova não adivinha qual entrada é a boa. Ela só considera perfis que
# (a) oferecem fonte de captura (`sources: >= 1`) e (b) o ALSA declara
# `available: yes`, e escolhe o de maior prioridade entre esses. Se o perfil
# ATIVO já satisfaz os dois, não há troca — devolve alvo vazio. O contrato de
# preservar a SAÍDA continua valendo pela prioridade: os perfis com saída têm
# prioridade muito maior que os só-de-entrada, então o eleito mantém o
# alto-falante/fone do controle e o canal de haptic-de-áudio.
# Função PURA: só parsing, nenhuma escrita.
_dualsense_perfil_status() {
    awk '
        /^[[:space:]]+Name: alsa_card\./ {
            nome = substr($0, index($0, ": ") + 2)
            alvo = (tolower(nome) ~ /dualsense/)
            if (alvo) { card = nome }
            secao = ""
            next
        }
        !alvo { next }
        /^[[:space:]]+Profiles:/ { secao = "perfis"; next }
        /^[[:space:]]+Active Profile:/ {
            ativo = substr($0, index($0, ": ") + 2)
            secao = ""
            next
        }
        secao == "perfis" {
            linha = $0
            sub(/^[[:space:]]+/, "", linha)
            pos = index(linha, ": ")
            if (pos < 2) next
            chave = substr(linha, 1, pos - 1)
            if (chave ~ /[[:space:]]/) next
            # `sources: N` e `available: yes|no` saem do próprio pactl em
            # LC_ALL=C. Sem fonte de captura o perfil não serve ao microfone;
            # indisponível, ele produz o nó sem porta que silenciou a medição.
            temfonte = (linha ~ /sources: [1-9]/)
            disponivel = (linha ~ /available: yes/)
            prio = 0
            if (match(linha, /priority: [0-9]+/)) {
                prio = substr(linha, RSTART + 10, RLENGTH - 10) + 0
            }
            if (temfonte && disponivel && prio > melhorprio) {
                melhorprio = prio
                melhor = chave
            }
            # Guardado por chave, e NÃO comparado com `ativo` aqui: no `pactl`
            # a linha `Active Profile:` vem DEPOIS da lista, então neste ponto
            # `ativo` ainda está vazio. Comparar aqui fazia a guarda nunca
            # ligar — defeito que o teste pegou.
            serve[chave] = (temfonte && disponivel)
            next
        }
        END {
            if (card == "") exit 0
            escolhido = ""
            # Alvo só quando o ativo NÃO serve e há alternativa de verdade.
            if (!serve[ativo] && melhor != "" && melhor != ativo) escolhido = melhor
            printf "%s\t%s\t%s\n", card, ativo, escolhido
        }
    ' "${1:--}"
}

# PURA: 0 quando a source de nome `$1` tem PORTA ATIVA no texto de
# `LC_ALL=C pactl list sources` lido de `$2` (arquivo) ou do stdin.
#
# É este o critério honesto de "dá para captar", e não o nome do perfil: uma
# source sem porta abre o fluxo e entrega zeros, em qualquer perfil. Medido em
# 26/07 — ver a nota em `_dualsense_perfil_status`.
_source_tem_porta_ativa() {
    awk -v alvo="$1" '
        /^[[:space:]]+Name: / {
            atual = substr($0, index($0, ": ") + 2)
            next
        }
        /^[[:space:]]+Active Port: / {
            if (atual == alvo) {
                porta = substr($0, index($0, ": ") + 2)
                if (porta != "" && porta != "(null)") { achou = 1 }
            }
            next
        }
        END { exit (achou ? 0 : 1) }
    ' "${2:--}"
}

# Face viva do critério acima: pergunta ao pactl desta máquina.
_dualsense_source_tem_porta() {
    local nome="$1"
    [[ -z "${nome}" ]] && return 1
    LC_ALL=C pactl list sources 2>/dev/null | _source_tem_porta_ativa "${nome}"
}

# CAMADA 1 — mute guardado por rota (arquivo) e mute vivo na source (pactl).
check_mic_mute_persistido() {
    local rotas="${HOME}/.local/state/wireplumber/default-routes"
    local mudas saida_mudas r
    mudas="$(_dualsense_rotas_mudas "${rotas}" input)"
    if [[ -n "${mudas}" ]]; then
        fail "microfone do DualSense MUDO por estado PERSISTIDO do WirePlumber (camada 1) — rode: scripts/doctor.sh --fix"
        while read -r r; do
            [[ -n "${r}" ]] && info "  rota muda: ${r}"
        done <<< "${mudas}"
        info "  o mute vive por ROTA em ${rotas} e é restaurado a cada conexão sem nada no log"
    elif [[ -r "${rotas}" ]]; then
        pass "nenhuma rota de CAPTURA do DualSense com mute persistido (camada 1)"
    else
        info "sem ${rotas} — o WirePlumber ainda não gravou estado de rota"
    fi

    # O alto-falante do controle mudo é um FATO sobre a saída, e a usuária pode
    # tê-lo escolhido. Ele aparece porque some é pior — mas como INFO, do lado
    # de fora do veredito do microfone.
    saida_mudas="$(_dualsense_rotas_mudas "${rotas}" output)"
    if [[ -n "${saida_mudas}" ]]; then
        info "o ALTO-FALANTE do DualSense está mudo no estado persistido — isso NÃO afeta o microfone"
        while read -r r; do
            [[ -n "${r}" ]] && info "  rota de saída muda: ${r}"
        done <<< "${saida_mudas}"
    fi

    command -v pactl >/dev/null 2>&1 || { info "pactl ausente — não checo o mudo VIVO da source"; return; }
    local src veredito
    src="$(LC_ALL=C pactl list sources short 2>/dev/null | _dualsense_source_nome)"
    if [[ -z "${src}" ]]; then
        info "sem source de captura do DualSense agora (controle fora do cabo, ou mic suprimido pelo drop-in 52)"
        return
    fi
    veredito="$(_source_mute_veredito "$(LC_ALL=C pactl get-source-mute "${src}" 2>/dev/null || true)")"
    case "${veredito}" in
        muted)   fail "a source do DualSense está MUDA agora (${src}) — rode: scripts/doctor.sh --fix" ;;
        unmuted) pass "source do DualSense não está muda (${src})" ;;
        *)       info "não consegui ler o mudo de ${src} (PipeWire parado?)" ;;
    esac
}

# CAMADA 2 — perfil da placa apontando para a entrada digital, que não tem sinal.
check_mic_perfil_sem_sinal() {
    command -v pactl >/dev/null 2>&1 || { info "pactl ausente — não checo o perfil da placa do DualSense"; return; }
    local linha card ativo alvo
    linha="$(LC_ALL=C pactl list cards 2>/dev/null | _dualsense_perfil_status)"
    if [[ -z "${linha}" ]]; then
        info "nenhuma placa de áudio do DualSense agora (controle fora do cabo — por BT não existe placa)"
        return
    fi
    IFS=$'\t' read -r card ativo alvo <<< "${linha}"
    # A PORTA manda. Fonte com porta de captura capta — em qualquer perfil, e
    # inclusive no `iec958-stereo` que a sprint MIC-USB-01 mandava evitar (foi
    # ele que gravou pico 4606 na medição de 26/07). Nome de perfil não é
    # veredito: porta é.
    local src_atual
    src_atual="$(LC_ALL=C pactl list sources short 2>/dev/null | _dualsense_source_nome)"
    if _dualsense_source_tem_porta "${src_atual}"; then
        pass "a entrada do DualSense tem porta de captura (${ativo:-<vazio>})"
        return
    fi
    if [[ -z "${alvo}" ]]; then
        warn "a entrada do DualSense não tem porta de captura e não há perfil disponível melhor (${ativo:-<vazio>}) — sem porta, a gravação sai em silêncio digital"
        return
    fi
    fail "a entrada do DualSense não tem porta de captura (camada 2): ${ativo} — rode: scripts/doctor.sh --fix"
    info "  sem porta a source abre o fluxo e entrega zeros (medido: 327.680 bytes de silêncio digital)"
    info "  cura: pactl set-card-profile ${card} \"${alvo}\""
}

# Cura das camadas 1 e 2. Chamada pelo --fix (junto das demais) e pelo --fix-mic
# (sozinha, para quem só quer o microfone de volta agora). Idempotente: cada
# passo confere antes de escrever e cala a boca quando não há o que fazer.
fix_mic_dualsense() {
    # Camada 1: o desmute das rotas mora no fix_wireplumber_default_source.sh,
    # que é o dono das escritas no estado do WirePlumber (ele para o serviço
    # antes de editar — com o WirePlumber vivo, o arquivo seria reescrito no
    # shutdown por cima da nossa edição).
    #
    # Sem segundo argumento a consulta é só de CAPTURA: uma cura de microfone
    # não pode ser disparada pelo alto-falante mudo, que a usuária pode ter
    # escolhido e que ninguém pediu para reativar.
    if [[ -n "$(_dualsense_rotas_mudas)" ]]; then
        if bash "${ROOT_DIR}/scripts/fix_wireplumber_default_source.sh" --unmute-routes >/dev/null 2>&1; then
            pass "mute persistido das rotas do DualSense removido (camada 1)"
        else
            warn "falha ao remover o mute persistido das rotas do DualSense"
        fi
    fi

    command -v pactl >/dev/null 2>&1 || return 0

    # Camada 2: perfil da placa num nó que REALMENTE capta.
    local linha card ativo alvo
    linha="$(LC_ALL=C pactl list cards 2>/dev/null | _dualsense_perfil_status)"
    if [[ -n "${linha}" ]]; then
        IFS=$'\t' read -r card ativo alvo <<< "${linha}"
        local src_antes
        src_antes="$(LC_ALL=C pactl list sources short 2>/dev/null | _dualsense_source_nome)"
        if _dualsense_source_tem_porta "${src_antes}"; then
            # NÃO TOCAR. Foi exatamente aqui que a versão anterior estragava a
            # máquina: trocava um perfil que captava por outro que o ALSA marca
            # indisponível, e a source nascia sem porta — silêncio digital.
            pass "a entrada do DualSense já tem porta de captura (${ativo:-<vazio>}) — camada 2 sem nada a fazer"
        elif [[ -n "${alvo}" ]]; then
            if pactl set-card-profile "${card}" "${alvo}" 2>/dev/null; then
                pass "perfil da placa do DualSense trocado para ${alvo} (camada 2, disponível e com fonte)"
            else
                warn "falha ao trocar o perfil da placa do DualSense para ${alvo}"
            fi
        else
            warn "sem porta de captura e sem perfil disponível melhor (${ativo:-<vazio>}) — o microfone não vai captar"
        fi
    fi

    # FONTE-PADRAO-01: com o perfil já resolvido acima, decidir QUEM é a fonte
    # padrão. Nesta ordem de propósito — é a troca de perfil que define qual
    # `alsa_input` existe, e eleger antes elegeria um nó que vai desaparecer.
    fix_default_source_monitor

    # Camada 1, face viva: a source pode estar muda sem que o arquivo diga —
    # o WirePlumber só grava o estado ao sair. Roda DEPOIS da troca de perfil,
    # porque é ela que faz a source analógica existir.
    local src veredito
    src="$(LC_ALL=C pactl list sources short 2>/dev/null | _dualsense_source_nome)"
    [[ -z "${src}" ]] && return 0
    veredito="$(_source_mute_veredito "$(LC_ALL=C pactl get-source-mute "${src}" 2>/dev/null || true)")"
    if [[ "${veredito}" == "muted" ]]; then
        if pactl set-source-mute "${src}" 0 2>/dev/null; then
            pass "source do DualSense desmutada (${src})"
        else
            warn "falha ao desmutar ${src}"
        fi
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
# MESA-CHEIA-11/E1: QUAIS controles estão frágeis (a flag acima virou "algum").
# Lista vazia = daemon antigo, ou mesa desconhecida — o aviso sai sem nomes.
frageis = res.get("native_bt_fragil_controles")
nums = (
    [n for n in frageis if isinstance(n, int) and not isinstance(n, bool)]
    if isinstance(frageis, list)
    else []
)
# CONSERTO 1.7: "2, 3 e 4", a MESMA grafia da janela (`juntar_rotulos`) — a
# mesma mesa não pode sair escrita de dois jeitos em duas telas da mesma casa.
if len(nums) > 1:
    quais = ", ".join(str(n) for n in nums[:-1]) + " e " + str(nums[-1])
else:
    quais = "".join(str(n) for n in nums)
print("native_bt_quais=" + quais)
# ...e QUANTOS, porque o shell não sabe contar uma frase: com UM frágil o texto
# dizia "com os Controles 3 ... esses controles" (plural para um), e a janela,
# no mesmo estado, acertava. O número é que escolhe o molde.
print(f"native_bt_quantos={len(nums)}")
PYEOF
)"; then
        warn "IPC não respondeu — estado de dedup indisponível (daemon travado?)"
        return
    fi
    local enabled dedup_ok motivo native_bt native_bt_quais native_bt_quantos
    enabled="$(sed -n 's/^enabled=//p' <<<"${out}")"
    dedup_ok="$(sed -n 's/^dedup_ok=//p' <<<"${out}")"
    motivo="$(sed -n 's/^dedup_motivo=//p' <<<"${out}")"
    native_bt="$(sed -n 's/^native_bt=//p' <<<"${out}")"
    native_bt_quais="$(sed -n 's/^native_bt_quais=//p' <<<"${out}")"
    native_bt_quantos="$(sed -n 's/^native_bt_quantos=//p' <<<"${out}")"
    if [[ "${native_bt}" == "True" ]]; then
        # MESA-CHEIA-11/E1: com quatro na mesa a pergunta seguinte é "quais?" —
        # e a resposta agora vem do daemon, que olha CADA controle em vez de só
        # o primário (com o Controle 1 no cabo, este aviso calava para os três
        # no rádio).
        #
        # CONSERTO 1.7: e são DOIS moldes, como na janela. Quem tem um controle
        # só no rádio — exatamente quem este aviso nasceu para socorrer — lia
        # "com os Controles 3 ... se o jogo não vir esses controles".
        if [[ "${native_bt_quantos}" == "1" && -n "${native_bt_quais}" ]]; then
            warn "Modo Nativo com o Controle ${native_bt_quais} em BLUETOOTH — o SDL pode não enxergar o físico BT (limite do HIDAPI); se o jogo não vir esse controle, use cabo USB ou a emulação"
        elif [[ -n "${native_bt_quais}" ]]; then
            warn "Modo Nativo com os Controles ${native_bt_quais} em BLUETOOTH — o SDL pode não enxergar o físico BT (limite do HIDAPI); se o jogo não vir esses controles, use cabo USB ou a emulação"
        else
            warn "Modo Nativo com o controle em BLUETOOTH — o SDL pode não enxergar o físico BT (limite do HIDAPI); se o jogo não vir o controle, use cabo USB ou a emulação"
        fi
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

# Caminho dos perfis. É o mesmo que `utils.xdg_paths.profiles_dir` resolve
# (platformdirs = XDG_CONFIG_HOME, com ~/.config de default) — lido do DISCO
# de propósito: o diagnóstico dos perfis tem de funcionar com o daemon parado,
# que é justamente quando a mantenedora vai olhar por que um perfil não entra.
profiles_dir_path() {
    printf '%s/%s/profiles' "${XDG_CONFIG_HOME:-${HOME}/.config}" "${APP_ID}"
}

# R-12 item 3 (débito da auditoria 23/07): classifica cada perfil do diretório
# em uma linha `estado<TAB>arquivo<TAB>nome`. Função PURA (recebe o diretório,
# só imprime) para ser exercitada por teste com um diretório sintético.
#
# Estados:
#   inalcancavel — `criteria` com os TRÊS campos vazios. `MatchCriteria.matches`
#                  devolve False sem condição alguma, então o autoswitch NUNCA
#                  escolhe esse perfil. Foi assim que o preset `coop_local` de
#                  fábrica passou meses sem nunca ativar, sem erro nenhum.
#   manual       — sentinel `{"type": "manual"}`: a MESMA inércia, só que
#                  declarada. Não é defeito, e por isso sai como informação.
#   ilegivel     — JSON quebrado (o daemon já pula com WARN no boot; aqui é
#                  para o item não sumir do relatório em silêncio).
# Perfil `any` e `criteria` com alvo não saem: são os casos sãos.
_perfis_inalcancaveis() {
    local dir="${1:-}"
    [[ -n "${dir}" ]] || dir="$(profiles_dir_path)"
    [[ -d "${dir}" ]] || return 0
    command -v python3 >/dev/null 2>&1 || return 0
    python3 - "${dir}" <<'PYEOF' 2>/dev/null
import json
import sys
from pathlib import Path

for path in sorted(Path(sys.argv[1]).glob("*.json")):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"ilegivel\t{path.name}\t{type(exc).__name__}")
        continue
    if not isinstance(data, dict):
        print(f"ilegivel\t{path.name}\tjson não é um objeto")
        continue
    nome = str(data.get("name") or path.stem)
    match = data.get("match")
    tipo = match.get("type") if isinstance(match, dict) else None
    if tipo == "manual":
        print(f"manual\t{path.name}\t{nome}")
    elif tipo == "criteria" and not (
        match.get("window_class")
        or match.get("window_title_regex")
        or match.get("process_name")
    ):
        print(f"inalcancavel\t{path.name}\t{nome}")
PYEOF
}

# R-12 item 3: o relatório de linha de comando do que a GUI já mostra na coluna
# "Quando usar" ("Só manual (nunca ativa sozinho)"). Um perfil sem alvo não
# falha, não loga e não aparece em lugar nenhum — ele simplesmente nunca entra,
# e a leitura de quem está do lado de cá é "o autoswitch está quebrado".
check_perfis_inalcancaveis() {
    local dir; dir="$(profiles_dir_path)"
    if [[ ! -d "${dir}" ]]; then
        info "sem diretório de perfis ainda (${dir}) — os presets nascem no primeiro boot do daemon"
        return
    fi
    if ! command -v python3 >/dev/null 2>&1; then
        warn "python3 ausente — não dá para ler os perfis"
        return
    fi
    local linhas total mortos="" manuais="" ilegiveis=""
    total="$(find "${dir}" -maxdepth 1 -name '*.json' -type f 2>/dev/null | wc -l)"
    linhas="$(_perfis_inalcancaveis "${dir}")"
    local estado arquivo nome
    while IFS=$'\t' read -r estado arquivo nome; do
        [[ -n "${estado}" ]] || continue
        case "${estado}" in
            inalcancavel) mortos+=" ${nome} (${arquivo})" ;;
            manual)       manuais+=" ${nome}" ;;
            ilegivel)     ilegiveis+=" ${arquivo} [${nome}]" ;;
        esac
    done <<< "${linhas}"

    if [[ -n "${ilegiveis}" ]]; then
        warn "perfil ilegível (o daemon pula com WARN no boot):${ilegiveis}"
    fi
    if [[ -n "${mortos}" ]]; then
        warn "perfil INALCANÇÁVEL pelo autoswitch — nenhum critério de janela:${mortos}. Ele só entra se você ativar na mão. Cura: abra a aba Perfis e dê um alvo (programa, jogo da Steam ou título), ou declare de propósito com \"match\": {\"type\": \"manual\"} no JSON"
    fi
    if [[ -n "${manuais}" ]]; then
        info "perfil só-manual por declaração (nunca ativa sozinho, e está certo assim):${manuais}"
    fi
    if [[ -z "${mortos}" && -z "${ilegiveis}" ]]; then
        pass "perfis alcançáveis pelo autoswitch (${total} no disco, nenhum sem alvo por acidente)"
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
#
# RADIO-ABERTO-01/E1-bis (06/08/2026): esta função só conhecia a sentinela
# LEGADA `# >>> hefesto FastConnectable >>>`, que o bloco unificado (escrito
# por todo install desde 21/07) NÃO tem. Reproduzi a cadeia de ramos na máquina
# dela: caía no ramo do grep genérico e imprimia "FastConnectable já
# configurado por TERCEIRO no main.conf" — o doctor atribuía a um terceiro o
# bloco que este projeto tinha acabado de escrever. O alternador cobre as três
# sentinelas e o doctor volta a saber de quem é o bloco.
check_bluez_fastconnectable() {
    local dropin=/etc/bluetooth/main.conf.d/hefesto-fastconnectable.conf
    if [[ -f "${dropin}" ]]; then
        pass "FastConnectable do BlueZ instalado (drop-in main.conf.d) — botão PS reconecta mais rápido (vale desde o último start do bluetoothd)"
    elif grep -qsE '^# >>> hefesto (bluetooth|FastConnectable) >>>' /etc/bluetooth/main.conf 2>/dev/null; then
        pass "FastConnectable do BlueZ instalado (bloco marcado hefesto no main.conf) — vale desde o último start do bluetoothd"
    elif grep -qsE '^[[:space:]]*FastConnectable[[:space:]]*=[[:space:]]*true' /etc/bluetooth/main.conf 2>/dev/null; then
        pass "FastConnectable já configurado por terceiro no main.conf"
    elif [[ ! -e /etc/bluetooth/main.conf ]]; then
        info "sem /etc/bluetooth/main.conf (BlueZ ausente?) — pulo o check de FastConnectable"
    else
        warn "reconexão rápida BT (FastConnectable) não configurada — rode ./install.sh (entra por default, SEM restart do bluetoothd)"
    fi
}

# RADIO-ABERTO-01/E1-bis (06/08/2026) — O DETECTOR QUE NÃO EXISTIA.
#
# Até hoje o `doctor.sh` mencionava `JustWorksRepairing` ZERO vezes (grep fecha
# a conta). Foi essa cegueira, somada ao check acima que mentia sobre a
# autoria do bloco, que deixou `JustWorksRepairing=always` viver quatro dias em
# /etc/bluetooth/main.conf DEPOIS de a sprint declarar a E1 "FEITA": o valor
# seguro estava no repositório e ninguém tinha como ver que não estava no disco.
#
# `always` remove a ÚLTIMA recusa do BlueZ ao re-pareamento por Just Works de
# quem já tem bond. Com o agente NoInputNoOutput e o FastConnectable, quem
# clonar o BD_ADDR de um controle bondado sobrescreve a LinkKey sem interação
# humana — e o device que sobe escolhe o próprio descritor HID, que pode ser um
# TECLADO. Por isso o veredito aqui é `fail`, não `warn`.
#
# O segundo ramo é a contrapartida honesta da cura: `confirm` aceita SÓ se
# houver agente registrado, enquanto `always` aceitava sem depender de ninguém.
# A troca transfere peso para o `hefesto-bt-agent.service`, uma unit que já
# falhou duas vezes em 04/08 (BT-AGENT-TRAVA-O-RESTART-01 e
# BT-AGENT-MORTO-FICA-MORTO-01). Com o agente morto, o re-pareamento legítimo
# dela para de funcionar — e é o doctor que tem de dizer isso antes que ela
# descubra pelo controle que não conecta.
#
# QUEM LÊ O VALOR (06/08/2026): `scripts/bluez_config.sh verificar`, e só ele.
# A primeira versão desta função REIMPLEMENTAVA aqui o mesmo `sed` do dono da
# config — duas fontes para a mesma regra, que é exatamente a classe de defeito
# que esta leva veio fechar (a lógica morava dentro do install.sh, ninguém
# conseguia exercitá-la, e o `always` viveu quatro dias). O `verificar` é modo
# de leitura pura, e aqui roda com `HEFESTO_BT_SUDO=""` de propósito: um
# diagnóstico não pede senha. Se o arquivo estiver ilegível, ele diz
# `ilegível` — e nós dizemos também, em vez de inventar "não declarado".
#
# POR QUE A RAIZ É VARIÁVEL AQUI (06/08/2026): a raiz vinha literal
# (`/etc/bluetooth/main.conf`), e era isso que tornava esta função INTESTÁVEL —
# nenhuma bancada pode exercitá-la contra o /etc de verdade, e por isso os dois
# únicos testes que existiam eram grep de TEXTO no doctor.sh. MEDIDO: trocar o
# `fail` do ramo `always` por `pass` deixava a suíte INTEIRA verde (138 passed),
# e apagar a CHAMADA em `main()` também — o detector de segurança podia ser
# invertido ou desligado sem uma linha vermelha. Com a raiz saindo de
# `HEFESTO_BT_ETC` (o mesmo override que o dono único já usa; em produção fica
# no padrão), `tests/unit/test_doctor_justworks_comportamento.py` roda os cinco
# ramos DE VERDADE contra uma raiz falsa, e as duas mutações ficam vermelhas.
check_bluez_justworks_repairing() {
    local dono="${ROOT_DIR}/scripts/bluez_config.sh" valor state
    local etc_bt="${HEFESTO_BT_ETC:-/etc/bluetooth}"
    # "NÃO EXISTE" e "NÃO CONSIGO VER" são respostas diferentes, e o doctor
    # dizia a primeira nos dois casos (achado de 06/08/2026).
    #
    # Dentro de um Flatpak sem `--filesystem=host` — que é o caso do nosso
    # manifesto — `/etc/bluetooth` simplesmente NÃO EXISTE no sandbox: o /etc do
    # host não é alcançável. O ramo abaixo caía no `info ... pulo o check`, que
    # não é WARN nem FAIL, numa máquina cujo HOST tem `JustWorksRepairing=always`
    # ativo. Pior que o caso do .deb, que ao menos avisava com WARN. Silêncio
    # sobre injeção de teclas é o defeito que abriu esta sprint, de costas.
    #
    # O marcador é `/.flatpak-info`, que o próprio flatpak monta em todo
    # sandbox; `FLATPAK_ID`, `SNAP` e `/run/.containerenv` cobrem os vizinhos.
    # Os dois caminhos saem de variável para a bancada poder exercitá-los sem
    # container nenhum — mesma escola do `HEFESTO_BT_ETC`.
    local marca_flatpak="${HEFESTO_MARCA_SANDBOX:-/.flatpak-info}"
    local marca_container="${HEFESTO_MARCA_CONTAINER:-/run/.containerenv}"
    local em_sandbox=0
    if [[ -e "${marca_flatpak}" || -e "${marca_container}" \
          || -n "${FLATPAK_ID:-}" || -n "${SNAP:-}" ]]; then
        em_sandbox=1
    fi
    if [[ ! -e "${etc_bt}/main.conf" && "${em_sandbox}" -eq 1 ]]; then
        warn "NÃO SEI o valor de JustWorksRepairing nesta máquina: estou num sandbox (Flatpak/Snap/container) e o /etc do host não é alcançável daqui — ${etc_bt}/main.conf não existe DENTRO do sandbox, o que não diz nada sobre o host. Rode o doctor FORA do pacote: bash scripts/doctor.sh, ou sudo bash scripts/bluez_config.sh verificar"
        return
    fi
    if [[ ! -e "${etc_bt}/main.conf" ]]; then
        info "sem ${etc_bt}/main.conf (BlueZ ausente?) — pulo o check de JustWorksRepairing"
        return
    fi
    if [[ ! -f "${dono}" ]]; then
        warn "scripts/bluez_config.sh ausente — o dono único da config do BlueZ não está aqui, e não leio JustWorksRepairing por fora dele"
        return
    fi
    valor="$(HEFESTO_BT_SUDO="" bash "${dono}" verificar 2>/dev/null \
        | sed -n 's/^JustWorksRepairing: //p' || true)"
    case "${valor}" in
        confirm)
            pass "JustWorksRepairing=confirm no main.conf — re-pareamento de quem já tem bond passa pelo agente (RADIO-ABERTO-01)"
            # SELO-VERDE-CEDO-DEMAIS-01 (06/08/2026, achado de verificação
            # adversarial): dizer só "confirm no main.conf" carimbava VERDE um
            # rádio ainda ABERTO. O `bluez_config.sh` grava e NÃO reinicia o
            # bluetoothd de propósito (derrubaria os controles conectados), e diz
            # isso por escrito: "VALEM NO PRÓXIMO BOOT". Entre a cura e o próximo
            # start, o daemon VIVO segue com `always` — e quem lesse este `[ OK ]`
            # fecharia o terminal achando que a janela de Just Works fechou.
            #
            # Em vez de só ressalvar, MEDIMOS: se o main.conf é mais novo que o
            # start do bluetoothd, o disco ainda não é o que o daemon carregou.
            # O irmão FastConnectable já dizia "vale desde o último start" — a
            # ressalva existia no arquivo e faltava logo na chave de segurança.
            _t_conf="$(stat -c %Y "${etc_bt}/main.conf" 2>/dev/null || echo 0)"
            # `HEFESTO_BT_ATIVO_DESDE` existe para a bancada morder os DOIS
            # ramos (o `systemctl` de mentira dela não tem relógio). Em produção
            # nunca vem definida, e o valor sai do systemd logo abaixo.
            _t_bluez="${HEFESTO_BT_ATIVO_DESDE:-}"
            if [[ -z "${_t_bluez}" ]]; then
                _ts_bluez="$(systemctl show bluetooth.service \
                    -p ActiveEnterTimestamp --value 2>/dev/null || true)"
                # `date -d ""` NÃO falha: o GNU date devolve MEIA-NOITE DE HOJE
                # (medido em 06/08/2026). Sem esta guarda, toda máquina em que o
                # `bluetooth.service` não reporta — inativo, mascarado, container
                # sem systemd — comparava o `main.conf` contra meia-noite, e o
                # aviso saía em falso para qualquer arquivo tocado no dia. O
                # `|| echo 0` original não protegia nada, porque não havia erro.
                if [[ -n "${_ts_bluez//[[:space:]]/}" ]]; then
                    _t_bluez="$(date -d "${_ts_bluez}" +%s 2>/dev/null || echo 0)"
                else
                    _t_bluez=0
                fi
            fi
            if [[ "${_t_conf}" -gt 0 && "${_t_bluez}" -gt 0 \
                  && "${_t_conf}" -gt "${_t_bluez}" ]]; then
                warn "o main.conf mudou DEPOIS do último start do bluetoothd — o daemon VIVO ainda roda com o valor anterior, e o rádio só fecha no próximo boot (ou com 'sudo systemctl restart bluetooth', que derruba os controles conectados agora)"
            fi
            state="$(systemctl is-active hefesto-bt-agent.service 2>/dev/null || true)"
            if [[ "${state}" != "active" ]]; then
                warn "JustWorksRepairing=confirm depende de um agente registrado, e o hefesto-bt-agent.service está ${state:-ausente} — re-pareamento legítimo pode ser RECUSADO ('Refusing connection from ...'); ligue: sudo systemctl enable --now hefesto-bt-agent.service"
            fi
            ;;
        always)
            fail "JustWorksRepairing=always ATIVO no ${etc_bt}/main.conf — remove a última recusa do BlueZ ao re-pareamento por Just Works de quem já tem bond; com o agente NoInputNoOutput isso termina em injeção de teclas (RADIO-ABERTO-01). Cura: rode ./install.sh SEM --no-udev (a flag pula este passo inteiro) ou, direto, sudo bash scripts/bluez_config.sh aplicar — os dois corrigem o bloco antigo do hefesto SEM reiniciar o bluetoothd"
            ;;
        ausente|"")
            warn "JustWorksRepairing não está declarado no main.conf — o BlueZ cai no default da distro, que não é decisão desta casa; rode ./install.sh (entra por default, e NÃO com --no-udev, que pula este passo)"
            ;;
        ilegível)
            warn "não consigo LER ${etc_bt}/main.conf — sem leitura não sei o valor de JustWorksRepairing; rode: sudo bash ${dono} verificar"
            ;;
        recusado)
            # Achado de 06/08/2026: uma linha malformada em QUALQUER ponto do
            # arquivo faz o GKeyFile abortar a carga, e o bluetoothd fica sem
            # config nenhuma — nem a nossa. Antes, o dono lia a chave normal e o
            # doctor dava selo verde a um arquivo que o BlueZ descarta inteiro.
            fail "${etc_bt}/main.conf tem uma linha que o parser do bluetoothd (GKeyFile) RECUSA, e uma linha recusada invalida o ARQUIVO INTEIRO: o BlueZ fica sem config nenhuma — nem JustWorksRepairing, nem FastConnectable, nem o que já era dela. Veja qual linha é e conserte-a à mão: bash ${dono} verificar"
            ;;
        never)
            # A PROMESSA AQUI ERA FALSA NA METADE DOS CASOS (06/08/2026): dizia
            # sem ressalva que "a sua linha é neutralizada, e 'remover' a
            # devolve". Só vale FORA do bloco hefesto. DENTRO do bloco — que é
            # onde quem lê este aviso vai escrever, porque é onde a chave já
            # está — a faixa inteira é reescrita, nenhuma marca é gravada e o
            # `remover` entrega o arquivo SEM a chave. O `aplicar` sabe dizer
            # qual dos dois casos é o dela (ele lê a posição da linha que vence);
            # o doctor não precisa saber, precisa é não prometer o que não pode.
            warn "JustWorksRepairing=never no main.conf — é MAIS restritivo que o 'confirm' desta casa (recusa todo re-pareamento de quem já tem bond). Se foi escolha sua, NÃO rode ./install.sh: ele rebaixa para 'confirm'. E confira ONDE a sua linha está: FORA das sentinelas do hefesto ela é neutralizada e o 'bluez_config.sh remover' a devolve inteira; DENTRO do bloco ela é reescrita junto com o bloco e não volta (só o backup guarda)"
            ;;
        *)
            warn "JustWorksRepairing=${valor} no main.conf — esta casa instala 'confirm'; rode ./install.sh se o valor não foi escolha sua"
            ;;
    esac
}

# O "clone DS4" 054C:05C4 que stormou o rádio com 211 mil erros de CRC numa
# noite (estudo 2026-07-18 §2.1). Pelo OUI no cache do adaptador, é quase
# certamente um 8BitDo em modo D-input — o conselho é TROCAR O MODO/cabo, não
# jogar fora. (054C:05C4 também é o PID do DS4 v1 legítimo; o journal
# desempata: hw_version=0x00000000 denuncia o firmware clone.)
# WATCHDOG-FP-01 (22/07): consultas de estado BT saem do D-Bus — o
# bluetoothctl 5.86 one-shot é mudo (COMPAT BLUEZ-586-CTL-01) e `timeout N
# bluetoothctl ...` invoca o BINÁRIO, pulando a função-sombra acima; foi
# assim que a caça ao clone e o check de rádio ficaram cegos (4 controles
# Trusted=false e nenhum aviso).
_dbus_bt_device_paths() {
    busctl tree org.bluez --list 2>/dev/null \
        | grep -oE '/org/bluez/hci[0-9]+/dev_[0-9A-Fa-f_]+$' | sort -u || true
}
_dbus_bt_prop() {
    # $1=path  $2=interface  $3=propriedade → valor cru sem aspas (vazio se n/d)
    busctl get-property org.bluez "$1" "$2" "$3" 2>/dev/null \
        | sed -e 's/^[a-z]* //' -e 's/^"//' -e 's/"$//' || true
}

check_bt_clone_ds4() {
    command -v busctl >/dev/null 2>&1 || { info "busctl ausente — pulo a caça ao clone DS4"; return; }
    local paths p mac modalias clone=0
    paths="$(_dbus_bt_device_paths)"
    if [[ -z "${paths}" ]]; then
        info "nenhum dispositivo Bluetooth pareado — sem clone DS4 possível"
        return
    fi
    while IFS= read -r p; do
        [[ -z "${p}" ]] && continue
        mac="${p##*dev_}"; mac="${mac//_/:}"
        modalias="$(_dbus_bt_prop "${p}" org.bluez.Device1 Modalias)"
        if printf '%s' "${modalias}" | grep -q 'usb:v054Cp05C4'; then
            clone=1
            warn "controle 'tipo DualShock 4' (054C:05C4) pareado (${mac}) — esse firmware não calcula a verificação de integridade e INUNDA o sistema de erros (já foram 211 mil numa noite), degradando o Bluetooth de TODOS os controles"
            info "  provavelmente é um 8BitDo em modo D-input: troque o modo (Switch) ou use no cabo"
            info "  para desparear: bluetoothctl remove ${mac}  (se for um DS4 v1 legítimo, o journal desempata: 'hw_version=0x00000000' = clone)"
        fi
    done <<<"${paths}"
    [[ "${clone}" -eq 0 ]] && pass "nenhum clone DS4 (054C:05C4) pareado"
}

# Saúde do rádio 2.4 GHz: RSSI, Trusted, Discovering, contadores do adaptador
# e IdleTimeout — os 5 checks do estudo BT §5/§6, todos read-only.
check_bt_radio() {
    command -v busctl >/dev/null 2>&1 || return 0
    local paths p mac alias connected trusted rssi disc gamepad_conectado=0
    paths="$(_dbus_bt_device_paths)"
    while IFS= read -r p; do
        [[ -z "${p}" ]] && continue
        mac="${p##*dev_}"; mac="${mac//_/:}"
        alias="$(_dbus_bt_prop "${p}" org.bluez.Device1 Alias)"
        printf '%s' "${alias}" | grep -qiE 'dualsense|wireless controller|pro controller|8bitdo|joy-con|xbox' || continue
        connected="$(_dbus_bt_prop "${p}" org.bluez.Device1 Connected)"
        if [[ "${connected}" == "true" ]]; then
            gamepad_conectado=1
            # RSSI via D-Bus só existe durante discovery — mesmo limite do
            # `bluetoothctl info` antigo; sem valor, sem veredito.
            rssi="$(_dbus_bt_prop "${p}" org.bluez.Device1 RSSI)"
            if [[ -n "${rssi}" ]] && (( rssi < -70 )); then
                warn "sinal fraco do ${alias:-controle} (${mac}): RSSI ${rssi} dBm (bom é > -60) — ponha o adaptador BT num extensor USB curto, fora da sombra do gabinete e a 20 cm ou mais dos receivers 2.4G"
            elif [[ -n "${rssi}" ]]; then
                pass "sinal do ${alias:-controle}: RSSI ${rssi} dBm"
            fi
        fi
        trusted="$(_dbus_bt_prop "${p}" org.bluez.Device1 Trusted)"
        if [[ "${trusted}" == "false" ]]; then
            warn "${alias:-controle} (${mac}) pareado mas SEM confiança (Trusted: no) — a reconexão pelo botão PS pode depender de autorização; o watchdog corrige no próximo tick; na mão: busctl set-property org.bluez ${p} org.bluez.Device1 Trusted b true"
        fi
        # BT-SDP-VAZIO-01 (02/08): bond SEM registro de serviços SDP. O
        # `profiles/input/server.c` do BlueZ recusa conexão ENTRANTE de quem
        # não tem o perfil HID (0x1124) registrado — "Refusing connection:
        # unknown device" — e o device entra num laço: o rádio sobe, o perfil
        # não, o link cai. Nenhum dos checks acima enxergava isso: Paired,
        # Bonded e Trusted ficam todos `true` o tempo todo.
        #
        # Sem este aviso o defeito se parece com regressão do Hefesto, e foi
        # exatamente assim que ele chegou (a queixa dela: "conecta sozinho e
        # algo apaga a conexão"). Vale para device pareado, conectado ou não.
        if [[ "$(_dbus_bt_prop "${p}" org.bluez.Device1 Paired)" == "true" ]] \
                && ! _dbus_bt_prop "${p}" org.bluez.Device1 UUIDs \
                    | grep -q '00001124-0000-1000-8000-00805f9b34fb'; then
            fail "${alias:-controle} (${mac}) tem bond mas NENHUM perfil HID registrado (SDP vazio) — o BlueZ recusa a reconexão dele como 'unknown device' e o link cai sozinho. Cura (apaga o pareamento): busctl call org.bluez /org/bluez/hci0 org.bluez.Adapter1 RemoveDevice o ${p} && sudo rm -f /var/lib/bluetooth/*/cache/${mac} — e pareie de novo. O cache TEM de sair junto (SDP-CACHE-01), senão o pareamento novo nasce igual"
        fi
    done <<<"${paths}"
    # Inquiry contínuo rouba banda dos links dos controles (provado ao vivo:
    # a tela de Bluetooth do cosmic-settings aberta mantém Discovering=yes).
    if [[ "${gamepad_conectado}" -eq 1 ]]; then
        disc="$(_dbus_bt_prop /org/bluez/hci0 org.bluez.Adapter1 Discovering)"
        if [[ "${disc}" == "true" ]]; then
            warn "adaptador em modo de busca (Discovering: yes) com controle BT conectado — feche a tela de Bluetooth (cosmic-settings) enquanto joga; a busca rouba banda do rádio"
        fi
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
    local tag n resumo="" n_joycon=0 n_joycon_probe=0 n_usb71=0 n_bterr=0
    for tag in USB-71 JOYCON JOYCON-PROBE BT-HCI XHCI BT-ERR; do
        n="$(grep -cF "[${tag}]" "${log}" 2>/dev/null || true)"; n="${n:-0}"
        resumo+=" ${tag}=${n}"
        case "${tag}" in
            JOYCON) n_joycon="${n}" ;;
            JOYCON-PROBE) n_joycon_probe="${n}" ;;
            USB-71) n_usb71="${n}" ;;
            BT-ERR) n_bterr="${n}" ;;
        esac
    done
    info "kernel-watch (${log##*/}):${resumo}"
    if [[ "${n_joycon}" -gt 0 ]]; then
        warn "o kernel deu rate-limit no controle Nintendo/8BitDo ${n_joycon} vez(es) [JOYCON] — é a morte do 8BitDo em Bluetooth (muro do hid-nintendo); a configuração estável é NO CABO. Onda T: o patch DKMS (ver seção abaixo) reduz a chance do link cair, mas não elimina a degradação de rádio"
    fi
    if [[ "${n_joycon_probe}" -gt 0 ]]; then
        warn "o hid-nintendo falhou no PROBE ${n_joycon_probe} vez(es) [JOYCON-PROBE] neste log — morte 'invisível' (o device nem chega a registrar; sem cascata [JOYCON]); ver a seção DKMS hid-nintendo abaixo"
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

# A faixa de bluez que esta casa aceita tem DOIS limites, não um.
#
# PISO 5.79 — abaixo dele, crashes crônicos de input/HIDP (estudo da Onda R,
#   2026-07-19-estudo-bluez-backport-onda-r.md).
#
# TETO 5.87 — a MENOR versão REJEITADA conhecida. Motivo medido (estudo
#   docs/process/estudos/2026-08-07-o-defeito-do-bluez-que-ela-lembrou-e-os-
#   outros-cinco.md §D, GRAU MEDIDO pela topologia do git): o commit `5d836f1`
#   introduziu um uso-depois-de-liberado (UAF) em `dev_disconnected`
#   (`src/adapter.c`) — `device_is_connected()` chamado DEPOIS de
#   `adapter_remove_connection()`, que pode ter liberado o device. `5d836f1` é
#   ancestral da tag 5.87 (dentro); a correção `5bc6aa79` está UM commit depois
#   do 5.87 e NENHUM lançamento a carrega ainda. Por isso o alvo do backport é
#   o 5.86 (install.sh, passo 3f) e o 5.87 foi recusado em 22/07 e de novo em
#   07/08 — com número.
#
# Por que o teto é WARN e não FAIL: numa máquina que já veio com bluez ≥ 5.87
# (o caso do PC novo), nada disto é escolha dela, e o primeiro lançamento pós-
# 5.87 que carregue o `5bc6aa79` (previsivelmente o 5.88) sai desta faixa por
# mérito próprio. O dever do doctor aqui é NOMEAR o motivo, não decidir por
# ela. Quando o 5.88 sair com a correção, este teto sobe — e o estudo §D é o
# lugar onde se confere isso antes de mexer.
readonly _BZ_PISO="5.79"
readonly _BZ_TETO="5.87"

# Compara a versão do bluez instalada com a faixa [_BZ_PISO, _BZ_TETO).
# Função PURA — só `dpkg --compare-versions`, sem tocar em pacote nenhum.
_bluez_version_verdict() {
    local ver="$1"
    if [[ -z "${ver}" ]]; then
        printf 'unknown\n'
        return
    fi
    if ! dpkg --compare-versions "${ver}" ge "${_BZ_PISO}" 2>/dev/null; then
        printf 'old\n'
    elif dpkg --compare-versions "${ver}" ge "${_BZ_TETO}" 2>/dev/null; then
        printf 'nova\n'
    else
        printf 'ok\n'
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
            pass "bluez ${ver} >= ${_BZ_PISO} e < ${_BZ_TETO} (sem os crashes crônicos de input/HIDP do 5.72, e sem o UAF do 5.87)"
            ;;
        nova)
            warn "bluez ${ver} >= ${_BZ_TETO} — o 5.87 carrega um uso-depois-de-liberado em dev_disconnected (src/adapter.c: device_is_connected() chamado depois de adapter_remove_connection() liberar o device; commit 5d836f1). A correção 5bc6aa79 está um commit DEPOIS do 5.87 e nenhum lançamento a carregava até 07/08/2026 — se esta versão é o 5.88 ou mais nova, confira se ela já traz o 5bc6aa79 e suba o teto (_BZ_TETO) no doctor.sh. O alvo desta casa é o backport 5.86 (./install.sh, passo 3f); o porquê está em docs/process/estudos/2026-08-07-o-defeito-do-bluez-que-ela-lembrou-e-os-outros-cinco.md §D"
            ;;
        old)
            fail "bluez ${ver} < 5.79 — crashes crônicos de input/HIDP (heap corruption, 6x/5 dias medidos) documentados; aplique o backport: ./install.sh (passo ONDA-R aplica sozinho se os .debs estiverem em ~/.cache/hefesto-dualsense4unix/bluez-backport/; senão, gere-os pela receita em docs/process/estudos/2026-07-19-estudo-bluez-backport-onda-r.md, seção 3, caminho 1)"
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

# ONDA-R2 (sprint 2026-07-21 BlueZ, camada 2): resiliência do bluetoothd —
# timers de snapshot de bonds + watchdog de saúde ativos e drop-in presente.
check_bt_resilience() {
    command -v systemctl >/dev/null 2>&1 || { info "systemctl ausente — não checo a resiliência do bluetoothd"; return; }
    local t1 t2
    t1="$(systemctl is-active hefesto-bt-bonds-snapshot.timer 2>/dev/null || true)"
    t2="$(systemctl is-active hefesto-bt-health-watchdog.timer 2>/dev/null || true)"
    if [[ "${t1}" == "active" && "${t2}" == "active" ]]; then
        pass "resiliência do bluetoothd ativa (snapshot de bonds 15min + watchdog de saúde 2min)"
    elif systemctl cat hefesto-bt-bonds-snapshot.timer >/dev/null 2>&1; then
        warn "timers de resiliência do bluetoothd instalados mas não ativos (snapshot=${t1:-?}, watchdog=${t2:-?}); ligue: sudo systemctl enable --now hefesto-bt-bonds-snapshot.timer hefesto-bt-health-watchdog.timer"
    else
        warn "resiliência do bluetoothd não instalada (crash do bluetoothd destrói bonds sem backup); rode ./install.sh (passo ONDA-R2 aplica por default)"
    fi
    if [[ ! -f /etc/systemd/system/bluetooth.service.d/10-hefesto-resilience.conf ]]; then
        warn "drop-in 10-hefesto-resilience.conf ausente — sem o desarme do watchdog do systemd (BLUETOOTHD-MORTO-POR-NOS-01) e sem snapshot na parada do serviço"
    fi
    # BT-NINTENDO-ACTIVE-01 + BT-SNIFF-PER-OUI-01 (23/07): o modo ativo é o nome
    # "Nintendo*" (do ADAPTADOR, vale para todos) + no-sniff SÓ no Pro genuíno
    # (POR CONEXÃO, não no adaptador). O A/B de 23/07 provou que no-sniff no
    # adaptador quebra a probe do 8BitDo (clone) — então o default do adaptador
    # DEVE manter o SNIFF. O que se verifica agora:
    #   - o alias começa com "Nintendo";
    #   - o adaptador MANTÉM o SNIFF (o clone precisa dele);
    #   - o Pro genuíno conectado, se houver, está com no-sniff na SUA conexão.
    if command -v hciconfig >/dev/null 2>&1; then
        local _hci _lp _alias _pro_mac _pro_lp
        _hci="$(hciconfig 2>/dev/null | awk -F: '/^hci/{print $1; exit}')"
        if [[ -n "${_hci}" ]]; then
            _lp="$(hciconfig "${_hci}" lp 2>/dev/null | grep -o 'SNIFF' || true)"
            _alias="$(busctl get-property org.bluez "/org/bluez/${_hci}" org.bluez.Adapter1 Alias 2>/dev/null | sed -E 's/^s "?//; s/"?$//' || true)"
            # Pro Nintendo genuíno conectado (OUI E0:F6:B5) — se houver, checa a
            # policy DELE (deve ser sem SNIFF).
            _pro_lp="ausente"
            if command -v hcitool >/dev/null 2>&1; then
                _pro_mac="$(hcitool con 2>/dev/null | grep -oiE 'E0:F6:B5(:[0-9A-F]{2}){3}' | head -1 || true)"
                if [[ -n "${_pro_mac}" ]]; then
                    _pro_lp="$(hcitool lp "${_pro_mac}" 2>/dev/null | grep -o 'SNIFF' || echo 'sem-sniff')"
                fi
            fi
            if [[ -n "${_lp}" && "${_alias}" == Nintendo* ]]; then
                if [[ "${_pro_lp}" == "SNIFF" ]]; then
                    warn "modo ativo p/ Nintendo: alias e SNIFF do adaptador OK, mas o Pro genuíno conectado está COM sniff (deveria ser sem). Reaplique: sudo /usr/local/lib/hefesto-dualsense4unix/bt_active_mode.sh"
                else
                    pass "modo ativo p/ Nintendo (nome '${_alias}' + SNIFF no adaptador p/ o 8BitDo probar + no-sniff só no Pro genuíno — BT-SNIFF-PER-OUI-01)"
                fi
            else
                warn "modo ativo p/ Nintendo incompleto (alias='${_alias:-?}', SNIFF-adaptador=${_lp:-AUSENTE}); o adaptador deve MANTER o SNIFF (o 8BitDo precisa) — reaplique: sudo /usr/local/lib/hefesto-dualsense4unix/bt_active_mode.sh"
            fi
        fi
    fi
}

# ONDA-R2: bonds em disco vs cache — a assinatura medida em 22/07 do estado
# "pareamentos que evaporam" é cache/ populado com ZERO diretórios de bond
# (<MAC>/info) em /var/lib/bluetooth. Leitura exige root (árvore 700) —
# best-effort: sem sudo -n, só informa como conferir.
check_bt_bonds_persistidos() {
    if ! sudo -n true 2>/dev/null; then
        info "sem sudo sem senha — não leio /var/lib/bluetooth (confira à mão: sudo find /var/lib/bluetooth -name info)"
        return
    fi
    local n_info n_cache
    n_info="$(sudo -n find /var/lib/bluetooth -mindepth 3 -maxdepth 3 -type f -name info 2>/dev/null | wc -l)"
    n_cache="$(sudo -n find /var/lib/bluetooth -mindepth 3 -maxdepth 3 -type f -path '*/cache/*' 2>/dev/null | wc -l)"
    if [[ "${n_info}" -gt 0 ]]; then
        pass "bonds BT persistidos em disco: ${n_info} (cache com ${n_cache} devices vistos)"
    elif [[ "${n_cache}" -gt 0 ]]; then
        fail "ZERO bonds em disco com cache de ${n_cache} devices — pareamentos vivendo só em memória (evaporam no disconnect) ou destruídos por crash; re-pareie com Pair() explícito (bluetoothctl pair <MAC>) e confira Bonded: yes; se houver snapshot: sudo /usr/local/lib/hefesto-dualsense4unix/bt_bonds_restore.sh --list"
    else
        info "nenhum bond nem cache em /var/lib/bluetooth — adaptador nunca pareou nada (ou árvore em outro lugar)"
    fi
}

# SDP-CACHE-01 (23/07, medido ao vivo): o registro SDP do perfil HID mora em
# /var/lib/bluetooth/<adapter>/cache/<MAC>, seção [ServiceRecords], e é dele que
# o BlueZ tira o descritor HID (profiles/input/device.c:hidp_add_connection).
# Uma entrada SEM essa seção acompanha o controle ZUMBI: bond íntegro, ACL
# AUTH+ENCRYPT vivo, "Conectado" na GUI — e zero hidraw, zero input.
#
# Medido: 46 bytes (só [General] Name=) no controle quebrado, contra 1124..1433
# bytes COM [ServiceRecords] nos três sãos.
#
# Este check aponta o SINTOMA, que tem duas causas possíveis (o próprio check
# não as distingue; a mensagem cobre as duas):
#   (a) só a direção da conexão — o controle reconecta ENTRANTE (PS/SYNC) e esse
#       caminho não dispara SDP browse; um Connect() iniciado pelo HOST resolve
#       (o watchdog faz isso sozinho, e o BlueZ coopera: sem [ServiceRecords] ele
#       marca svc_resolved=false, src/device.c:4415);
#   (b) o controle parou de responder SDP — aí o cache truncado é consequência,
#       não causa, e nem Connect() nem re-pareamento resolvem. Confirme com
#       `sudo sdptool browse <MAC>`: controle são responde em <1 s; travado
#       estoura o timeout. Cura: reset de hardware do controle.
check_bt_sdp_cache_envenenado() {
    if ! sudo -n true 2>/dev/null; then
        info "sem sudo sem senha — não leio o cache SDP (confira: sudo grep -L ServiceRecords /var/lib/bluetooth/*/cache/*)"
        return
    fi
    local achou=0 info_f devdir mac adpdir cache
    while IFS= read -r info_f; do
        [[ -z "${info_f}" ]] && continue
        devdir="$(dirname "${info_f}")"
        mac="$(basename "${devdir}")"
        adpdir="$(dirname "${devdir}")"
        cache="${adpdir}/cache/${mac}"
        # Só device de perfil HID (0x1124 = HumanInterfaceDevice).
        sudo -n grep -qi '^Services=.*00001124-0000-1000-8000-00805f9b34fb' "${info_f}" 2>/dev/null || continue
        # Cache ausente é SÃO: o BlueZ refaz o browse na próxima conexão.
        sudo -n test -f "${cache}" 2>/dev/null || continue
        sudo -n grep -q '^\[ServiceRecords\]' "${cache}" 2>/dev/null && continue
        achou=1
        fail "cache SDP de ${mac} SEM [ServiceRecords] — o perfil HID não sobe (controle 'Conectado' e sem input). Primeiro confira QUAL das duas causas é: 'sudo sdptool browse ${mac}' — se responder em <1 s, é só a direção da conexão e o watchdog cura sozinho no próximo tick (Connect() pelo host, sem desparear); se ESTOURAR o timeout, o stack do controle travou e nem re-parear resolve: reset de hardware do controle (furinho atrás, ~5 s com um clipe)"
    done < <(sudo -n find /var/lib/bluetooth -mindepth 3 -maxdepth 3 -type f -name info 2>/dev/null | sort)
    [[ "${achou}" -eq 0 ]] && pass "cache SDP íntegro em todos os controles com bond (todos têm [ServiceRecords])"
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

# Sintetiza um "bloco info" mínimo via D-Bus com as linhas que as funções
# puras abaixo consomem (Device/Icon/Connected/Paired/Bonded) — as puras e
# seus testes ficam intactos enquanto a FONTE deixa de ser o bluetoothctl
# 5.86 mudo (WATCHDOG-FP-01: "nenhum dispositivo pareado" com 4 em disco).
_dbus_bt_info_bloco() {
    local p="$1" mac icon conn paired bonded
    mac="${p##*dev_}"; mac="${mac//_/:}"
    icon="$(_dbus_bt_prop "${p}" org.bluez.Device1 Icon)"
    conn="$(_dbus_bt_prop "${p}" org.bluez.Device1 Connected)"
    paired="$(_dbus_bt_prop "${p}" org.bluez.Device1 Paired)"
    bonded="$(_dbus_bt_prop "${p}" org.bluez.Device1 Bonded)"
    printf 'Device %s (public)\n' "${mac}"
    if [[ -n "${icon}" ]]; then printf '\tIcon: %s\n' "${icon}"; fi
    printf '\tConnected: %s\n' "$([[ "${conn}" == "true" ]] && echo yes || echo no)"
    printf '\tPaired: %s\n' "$([[ "${paired}" == "true" ]] && echo yes || echo no)"
    # Bonded ausente na API (BlueZ < 5.65) fica FORA do bloco — igual ao
    # bluetoothctl antigo, para a pura não acusar "meio-salvo" por engano.
    if [[ -n "${bonded}" ]]; then
        printf '\tBonded: %s\n' "$([[ "${bonded}" == "true" ]] && echo yes || echo no)"
    fi
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
    command -v busctl >/dev/null 2>&1 || { info "busctl ausente — pulo o check de pareamento meio-salvo"; return; }
    local paths p inf hidraw_list resultado achou=0
    paths="$(_dbus_bt_device_paths)"
    if [[ -z "${paths}" ]]; then
        info "nenhum dispositivo Bluetooth pareado — sem 'Connected sem hidraw' possível"
        return
    fi
    hidraw_list="$(_hidraw_uniqs)"
    while IFS= read -r p; do
        [[ -z "${p}" ]] && continue
        inf="$(_dbus_bt_info_bloco "${p}")"
        resultado="$(_bt_gamepad_missing_hidraw "${inf}" "${hidraw_list}")"
        if [[ -n "${resultado}" ]]; then
            achou=1
            fail "controle BT ${resultado} CONECTADO mas SEM hidraw correspondente (HID_UNIQ) — controle ZUMBI; veja o check de cache SDP logo abaixo ANTES de desparear (na maioria dos casos a causa é cache SDP envenenado e o bond não precisa ser destruído)"
        fi
    done <<<"${paths}"
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
    command -v busctl >/dev/null 2>&1 || { info "busctl ausente — pulo o check de bond meio-salvo"; return; }
    local paths p inf resultado achou=0
    paths="$(_dbus_bt_device_paths)"
    if [[ -z "${paths}" ]]; then
        info "nenhum dispositivo Bluetooth pareado — sem bond meio-salvo possível"
        return
    fi
    while IFS= read -r p; do
        [[ -z "${p}" ]] && continue
        inf="$(_dbus_bt_info_bloco "${p}")"
        resultado="$(_bt_paired_sem_bonded "${inf}")"
        if [[ -n "${resultado}" ]]; then
            achou=1
            fail "${resultado} Paired mas NÃO Bonded — bond meio-salvo ('No agent available for request type 2'); cura: bluetoothctl remove ${resultado} && repareie (PS no controle); confira o hefesto-bt-agent.service ativo acima"
        fi
    done <<<"${paths}"
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
            # A PORTA, DECLARADA (A-PORTA-QUE-A-CASA-CONSTRUIU-01, 15/08/2026).
            # Este diagnóstico NUNCA abre /dev/hidraw* por conta própria: ele
            # pede o fd ao broker, que é a porta que a casa construiu para o nó
            # escondido. Dizer isso na tela importa porque quem lê o doctor
            # decide, a seguir, por onde o PRÓXIMO instrumento vai medir — e a
            # sessão de 15/08 se perdeu justamente batendo na porta errada.
            info "porta: broker (SCM_RIGHTS) via /run/hefesto-hidraw-broker/broker.sock — nenhum open() direto de /dev/hidraw* neste diagnóstico"
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

# ---------------------------------------------------------------------------
# TECLADO-QUE-NAO-DIGITA-01 — o teclado na tela que o L3 do controle abre.
# ---------------------------------------------------------------------------
# ESTE CHECK CONFERE E NÃO CURA. É regra desta casa, e aqui ela tem dente
# próprio: instalar pacote de sistema é decisão com senha de root, e o doctor
# roda no meio de um diagnóstico — quem instala é o install.sh (passo 4f e o
# bloco dos formatos de pacote), quem confere é este. Nem o `--fix` toca nisto.
#
# O CONTRATO DE NOMES é o mesmo do `scripts/install_osk.sh` e o mesmo do
# `daemon/subsystems/keyboard.py`, e o `scripts/check_packaging_parity.sh`
# cobra a coincidência dos três: instalador, conferidor e daemon têm de estar
# falando do MESMO binário para a MESMA sessão, senão o produto instala um e
# procura outro — e ninguém percebe, porque cada um dos três passa sozinho.
#
# A ARMADILHA QUE ESTE CHECK EXISTE PARA NÃO REPETIR (commit 108b711):
# "install.sh ARMA, uninstall.sh DESARMA, doctor.sh lê a AUSÊNCIA como escolha
# dela — máquina curada e máquina quebrada são o MESMO estado para o portão".
# Aqui a ausência tem QUATRO histórias possíveis, e o binário faltando é
# idêntico nas quatro:
#
#   1. o install nunca passou por aqui (produto anterior a esta cura, ou
#      install nunca rodado nesta máquina);
#   2. ela pediu para pular (`--no-osk`);
#   3. o install TENTOU e não conseguiu (sem sudo, sem rede, distro sem o
#      pacote);
#   4. o pacote foi instalado e alguém o removeu depois — não fomos nós: o
#      uninstall do Hefesto NUNCA remove pacote de sistema.
#
# O que as distingue é a sentinela que o install grava
# (~/.local/state/hefesto-dualsense4unix/teclado-na-tela.conf). Sem ela, este
# check só poderia dizer "não tem" — que é exatamente a resposta que fez a
# máquina dela ficar quatro dias quebrada em agosto. O caso (2) é o único que
# NÃO é FAIL: é escolha dela, registrada e datada.
readonly OSK_BIN_WAYLAND="wvkbd-mobintl"
readonly OSK_BIN_X11="onboard"
readonly OSK_PKG_WAYLAND="wvkbd"
readonly OSK_PKG_X11="onboard"
# `${HOME:-}` e não `${HOME}`: este `readonly` roda no SOURCE do arquivo, e o
# doctor.sh é sourceado por testes de unidade das funções de parse com um
# ambiente mínimo, sem HOME (ver o rodapé deste arquivo). Sob `set -u`, um
# `${HOME}` aqui derruba o source inteiro com "unbound variable" — e o que
# quebra não é o teclado na tela, é toda a suíte que source este arquivo.
readonly OSK_SENTINELA="${HOME:-}/.local/state/hefesto-dualsense4unix/teclado-na-tela.conf"

# `WAYLAND_DISPLAY` primeiro, `DISPLAY` só depois: numa sessão Wayland com
# XWayland os DOIS estão setados (nesta máquina, `WAYLAND_DISPLAY=wayland-1` e
# `DISPLAY=:1`), então olhar `DISPLAY` antes diria "X11" para toda sessão
# Wayland moderna — e o veredito sairia invertido.
_osk_sessao() {
    if [[ -n "${WAYLAND_DISPLAY:-}" ]] || [[ "${XDG_SESSION_TYPE:-}" == "wayland" ]]; then
        printf 'wayland\n'
    elif [[ -n "${DISPLAY:-}" ]] || [[ "${XDG_SESSION_TYPE:-}" == "x11" ]]; then
        printf 'x11\n'
    else
        printf 'desconhecida\n'
    fi
}

_osk_sentinela() {
    local chave="$1"
    [[ -r "${OSK_SENTINELA}" ]] || return 1
    sed -n "s/^${chave}=//p" "${OSK_SENTINELA}" | head -1
}

check_teclado_na_tela() {
    local sessao esperado pacote gestor comando instalado outro
    sessao="$(_osk_sessao)"
    if [[ "${sessao}" == "x11" ]]; then
        esperado="${OSK_BIN_X11}";     pacote="${OSK_PKG_X11}"
        outro="${OSK_BIN_WAYLAND}"
    else
        esperado="${OSK_BIN_WAYLAND}"; pacote="${OSK_PKG_WAYLAND}"
        outro="${OSK_BIN_X11}"
    fi
    gestor="sua distribuição"
    comando="instale o pacote ${pacote} pela ${gestor}"
    if command -v apt-get >/dev/null 2>&1; then
        comando="sudo apt install ${pacote}"
    elif command -v dnf >/dev/null 2>&1; then
        comando="sudo dnf install ${pacote}"
    elif command -v pacman >/dev/null 2>&1; then
        comando="sudo pacman -S ${pacote}"
    fi

    if command -v "${esperado}" >/dev/null 2>&1; then
        pass "teclado na tela: ${esperado} instalado (sessão ${sessao}) — o L3 do controle abre"
        return
    fi

    # O caso que mais engana: o binário do OUTRO mundo está instalado. "Tem
    # teclado na tela" seria verdade e resposta errada — o onboard numa sessão
    # Wayland ABRE (via XWayland) e as teclas só chegam a clientes XWayland; o
    # wvkbd numa sessão X11 nem abre, porque é cliente Wayland puro.
    if command -v "${outro}" >/dev/null 2>&1; then
        if [[ "${sessao}" == "x11" ]]; then
            warn "teclado na tela: só ${outro} instalado, e esta sessão é X11 — ele é cliente Wayland puro e não abre aqui"
        else
            warn "teclado na tela: só ${outro} instalado, e esta sessão é Wayland — ele digita por XTEST e as teclas só chegam a janelas XWayland (abre e não digita)"
        fi
        info "quem digita nesta sessão é ${esperado}: ${comando}"
        info "o Hefesto NÃO remove o ${outro} — pacote de sistema é seu, não nosso"
        return
    fi

    # Daqui para baixo: nenhum dos dois no disco. Qual das quatro histórias?
    local resultado motivo data pacote_gravado
    resultado="$(_osk_sentinela resultado || true)"
    motivo="$(_osk_sentinela motivo || true)"
    data="$(_osk_sentinela data || true)"
    pacote_gravado="$(_osk_sentinela pacote || true)"

    case "${resultado}" in
        pulado)
            # ESCOLHA DELA — e é por isso que não é FAIL. Sem a sentinela esta
            # linha seria indistinguível do FAIL de baixo, que é o defeito de
            # 04/08 (108b711) inteiro em uma frase.
            info "teclado na tela: PULADO a pedido (${motivo:-"--no-osk"}, em ${data:-data não registrada})"
            info "o L3 do controle avisa na tela que não tem o que abrir, em vez de abrir"
            info "para ter: ${comando} (ou reinstale sem --no-osk)"
            ;;
        instalado|ja-instalado)
            fail "teclado na tela: o install registrou ${pacote_gravado:-${pacote}} instalado em ${data:-data não registrada}, e ele NÃO está mais na máquina"
            info "não fomos nós: o uninstall do Hefesto nunca remove pacote de sistema"
            info "para devolver: ${comando}"
            ;;
        falhou|dry-run)
            fail "teclado na tela: o install TENTOU instalar ${pacote_gravado:-${pacote}} e não conseguiu (motivo: ${motivo:-não registrado}, em ${data:-data não registrada})"
            info "rode: ${comando}"
            ;;
        *)
            fail "teclado na tela AUSENTE (${esperado}) e o install nunca passou por aqui — sem sentinela em ${OSK_SENTINELA}"
            info "é o ÚNICO caminho de fábrica para ESCREVER TEXTO com o controle:"
            info "nenhum dos nove atalhos padrão digita letra (Super, PrintScreen,"
            info "Alt+Tab, Alt+Shift+Tab, Enter, Delete, Backspace e os dois de OSK)"
            info "rode: ${comando}    — ou reinstale: ./install.sh"
            ;;
    esac
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

# R-06 (auditoria 23/07): a allowlist per-app do Steam Input
# (`steam_input_apps.txt`) era INERTE fora do guard de VDF — nada no caminho de
# lançamento a consultava e o broker escondia o hidraw do físico do mesmo jeito,
# então o jogo cujo DualSense vem PELA Steam (medido: Mullet Mad Jack, 2111190)
# não achava controle nenhum. Este check separa as duas perguntas que viviam
# coladas: a exceção está CONFIGURADA? e ela está EFETIVA (o .env por appid
# nasceu sem dedup)? "Efetiva agora" no hidraw só faz sentido com o jogo aberto,
# então aqui o veredito é sobre o que dá para afirmar sem o jogo rodando.
check_steam_input_allowlist() {
    local arquivo="${XDG_CONFIG_HOME:-$HOME/.config}/hefesto-dualsense4unix/steam_input_apps.txt"
    if [[ ! -f "${arquivo}" ]]; then
        info "sem allowlist per-app do Steam Input (${arquivo} ausente) — nenhum jogo pediu exceção"
        return
    fi
    local appids
    appids="$(sed 's/#.*$//' "${arquivo}" 2>/dev/null | tr -d '[:space:]' | grep -E '^[0-9]+$' || true)"
    if [[ -z "${appids}" ]]; then
        info "allowlist per-app do Steam Input vazia (${arquivo})"
        return
    fi
    local envdir="${HOME}/.local/state/hefesto-dualsense4unix/launch_env"
    local appid arquivo_env faltando=0 envenenado=0
    while IFS= read -r appid; do
        [[ -n "${appid}" ]] || continue
        arquivo_env="${envdir}/steam_app_${appid}.env"
        if [[ ! -f "${arquivo_env}" ]]; then
            faltando=$((faltando + 1))
            continue
        fi
        # A exceção só é EFETIVA se o .env daquele appid não carrega o dedup —
        # com IGNORE/PROTON_DISABLE_HIDRAW o físico segue escondido do jogo e a
        # allowlist volta a ser decorativa.
        if grep -qE '^(SDL_GAMECONTROLLER_IGNORE_DEVICES|PROTON_DISABLE_HIDRAW)=' "${arquivo_env}" 2>/dev/null; then
            envenenado=$((envenenado + 1))
        fi
    done <<< "${appids}"
    local total
    total="$(printf '%s\n' "${appids}" | grep -c . || true)"
    if [[ "${envenenado}" -gt 0 ]]; then
        fail "allowlist do Steam Input com ${envenenado} appid(s) cujo .env ainda esconde o físico (IGNORE/PROTON_DISABLE_HIDRAW) — a exceção NÃO vale; reinicie o daemon para regravar: systemctl --user restart hefesto-dualsense4unix"
    elif [[ "${faltando}" -gt 0 ]]; then
        warn "allowlist do Steam Input com ${faltando}/${total} appid(s) sem .env materializado — o jogo cai no default.env (com dedup) e a exceção não vale; reinicie o daemon para regravar"
    else
        pass "allowlist do Steam Input efetiva: ${total} appid(s) com .env próprio SEM dedup (o jogo enxerga o controle físico)"
    fi
}

check_controller() {
    # As duas linhas abaixo LISTAM nós, e nunca abrem nenhum: `[[ -e ]]` e `ls`
    # não fazem `open(2)`. É a exceção declarada no portão da porta
    # (tests/unit/test_a_porta_que_a_casa_construiu_01.py) — quem precisa de um
    # fd de hidraw neste arquivo pede ao broker, em `check_hidraw_broker`.
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

# PURA: varre regras udev e imprime `arquivo:linha:conteúdo` de toda regra que
# abre TODO nó hidraw para quem não é dono nem do grupo. Nenhum privilégio é
# necessário — `/etc/udev/rules.d` e `/usr/lib/udev/rules.d` são legíveis por
# qualquer usuário. Sem argumento, varre esses dois, nessa ordem.
#
# ACUSA-O-CULPADO-01 (medido nesta máquina em 06/08/2026). O aviso antigo dizia
# "provável ajuste manual" para cada nó 0666 — e o ajuste manual não existia. A
# causa era UMA linha, `KERNEL=="hidraw*", MODE="0666"`, num arquivo de terceiro
# (`60-openrgb.rules`), que abria os SEIS nós que ninguém reivindicava — entre
# eles os receptores do teclado e do mouse dela. A mensagem acusava a única
# pessoa que não tinha feito aquilo, e mandava procurar onde não estava.
#
# Os três critérios, e por que cada um:
#
#  1. a linha tem de casar `hidraw` (`KERNEL=="hidraw*"` ou `SUBSYSTEM=="hidraw"`);
#  2. o MODE tem de dar algum bit para OUTROS (último octeto != 0). O check
#     antigo casava só o literal `666` e deixava passar `664`, `662` e `646` —
#     e é o bit de LEITURA (4) que vaza o que é digitado, não só o de escrita;
#  3. a regra NÃO pode estreitar por aparelho. `ATTRS{idVendor}`, `KERNELS==` e
#     companhia são o que separa "abriu o gamepad dele" de "abriu a máquina
#     inteira". CONTROLE POSITIVO vivo nesta máquina:
#     `/usr/lib/udev/rules.d/71-pdp-controllers.rules` tem `MODE="0666"` com
#     `ATTRS{idVendor}=="0e6f"` — é regra de distro, mira UM controle, e NÃO
#     pode aparecer aqui.
#
# SOMBRA: arquivo de mesmo nome em `/etc` anula o de `/usr/lib` (é assim que o
# udev resolve), então o primeiro diretório em que o nome aparece é o que vale.
#
# RESTAURO-SO-COM-SINTOMA-01 (07/08/2026): a varredura ganhou uma SEGUNDA vista,
# e o corpo virou `_udev_hidraw_scan <manta|estreita>` para as duas nascerem do
# MESMO awk. O motivo é a lição da RECEITA-ERRADA-01: enquanto o critério for
# escrito duas vezes, ele diverge — e o pior lugar para a divergência aparecer é
# a tela, porque é ali que ela vira instrução.
#
#   manta    = a regra abre TODO hidraw (a de ACUSA-O-CULPADO-01, acima);
#   estreita = a regra abre hidraw MAS estreita por aparelho. Essa NUNCA é
#              acusada — e agora precisa ser ENUMERADA, porque é ela que
#              distingue "nó aberto por decisão de terceiro" (mexer é atropelo,
#              e o próximo evento de udev desfaz) de "nó aberto sem explicação"
#              (é aí, e só aí, que o restauro vale). CONTROLE POSITIVO vivo
#              nesta máquina em 07/08: `71-pdp-controllers.rules:8` abre um
#              controle PDP com MODE="0666" estreitando por idVendor 0e6f.
#
# Na vista `estreita` a saída ganha um campo: `arquivo:linha:ids:conteúdo`, onde
# `ids` são os identificadores de 4 hex citados pela regra (minúsculos, com
# vírgula no fim de cada um). O casamento com o nó é DELIBERADAMENTE frouxo — um
# id em comum basta — porque todo erro dele tem de cair para o lado de NÃO agir.
_udev_hidraw_scan() {
    local vista="$1"; shift
    local dirs=("$@")
    [[ ${#dirs[@]} -gt 0 ]] || dirs=(/etc/udev/rules.d /usr/lib/udev/rules.d)
    local d f base v sombreado vistos=()
    for d in "${dirs[@]}"; do
        [[ -d "${d}" ]] || continue
        for f in "${d}"/*.rules; do
            [[ -f "${f}" ]] || continue
            base="${f##*/}"
            sombreado=0
            for v in ${vistos[@]+"${vistos[@]}"}; do
                [[ "${v}" == "${base}" ]] && sombreado=1
            done
            vistos+=("${base}")
            [[ "${sombreado}" -eq 1 ]] && continue
            awk -v arq="${f}" -v vista="${vista}" '
                {
                    linha = $0
                    sub(/^[[:space:]]+/, "", linha)
                    sub(/[[:space:]]+$/, "", linha)
                }
                linha == "" || linha ~ /^#/ { next }
                linha !~ /KERNEL=="hidraw/ && linha !~ /SUBSYSTEM=="hidraw"/ { next }
                {
                    if (match(linha, /MODE[[:space:]]*:?=[[:space:]]*"[0-7]+"/) == 0) next
                    modo = substr(linha, RSTART, RLENGTH)
                    # O valor do MODE sai do texto ANTES da colheita de ids:
                    # "0666" é quatro dígitos hexadecimais válidos e viraria um
                    # identificador fantasma em toda regra estreitada.
                    resto = substr(linha, 1, RSTART - 1) substr(linha, RSTART + RLENGTH)
                    gsub(/[^0-7]/, "", modo)
                    if (modo == "") next
                    outros = substr(modo, length(modo), 1)
                    if (outros == "0") next

                    # Estreitamento por aparelho: a regra é de quem a escreveu.
                    estreita = 0
                    if (linha ~ /ATTRS?\{id(Vendor|Product)\}/) estreita = 1
                    if (linha ~ /KERNELS[[:space:]]*==/)        estreita = 1
                    if (linha ~ /ENV\{ID_(VENDOR|MODEL)_ID\}/)  estreita = 1

                    if (vista == "manta"    && estreita == 1) next
                    if (vista == "estreita" && estreita == 0) next
                    if (vista != "estreita") { print arq ":" FNR ":" linha; next }

                    # Colhe todo bloco de exatamente 4 hex delimitado por
                    # não-hex. Pega `ATTRS{idVendor}=="0e6f"` e também o
                    # `KERNELS=="*045e:02ea*"` das regras de distro, que embutem
                    # vendor:produto dentro de um curinga.
                    ids = ""
                    tmp = resto
                    while (match(tmp, /[0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F]/)) {
                        tok    = substr(tmp, RSTART, 4)
                        antes  = (RSTART == 1) ? "" : substr(tmp, RSTART - 1, 1)
                        depois = substr(tmp, RSTART + 4, 1)
                        tmp    = substr(tmp, RSTART + 4)
                        if (antes ~ /[0-9a-fA-F]/ || depois ~ /[0-9a-fA-F]/) continue
                        ids = ids tolower(tok) ","
                    }
                    print arq ":" FNR ":" ids ":" linha
                }
            ' "${f}"
        done
    done
}

# A vista de ACUSA-O-CULPADO-01, intocada no nome, na assinatura e na saída:
# `arquivo:linha:conteúdo` de toda regra que abre TODO nó hidraw.
_udev_hidraw_rw_global() { _udev_hidraw_scan manta "$@"; }

# A vista nova: `arquivo:linha:ids:conteúdo` de toda regra que abre hidraw
# ESTREITANDO por aparelho. Não é acusação — é o inventário de decisões alheias
# que o restauro tem de respeitar.
_udev_hidraw_rw_estreitas() { _udev_hidraw_scan estreita "$@"; }

# Os identificadores 4-hex do aparelho por trás do nó, como `vendor,produto`
# minúsculos, lidos do uevent do sysfs:
#
#   HID_ID=0003:0000054C:00000CE6  ->  054c,0ce6
#
# Sem uevent legível devolve VAZIO — e quem chama trata "não sei" como "não
# mexo", nunca como "está livre".
_hidraw_ids_do_no() {
    local no="${1##*/}" sysroot="${2:-/sys/class/hidraw}" ue hid vend prod
    for ue in "${sysroot}/${no}/device/uevent" "${sysroot}/${no}/uevent"; do
        [[ -r "${ue}" ]] || continue
        hid="$(sed -n 's/^HID_ID=//p' "${ue}" 2>/dev/null | head -n1)"
        [[ -n "${hid}" ]] || continue
        prod="${hid##*:}"
        vend="${hid%:*}"; vend="${vend##*:}"
        [[ ${#vend} -ge 4 ]] && vend="${vend: -4}"
        [[ ${#prod} -ge 4 ]] && prod="${prod: -4}"
        printf '%s,%s' "${vend,,}" "${prod,,}"
        return 0
    done
    return 0
}

# O CRITÉRIO DE "HÁ SINTOMA", num lugar só — RESTAURO-SO-COM-SINTOMA-01.
#
# É esta função que o CHECK consulta para decidir se OFERECE o conserto, e é a
# mesma que a CURA consulta para decidir em que tocar. Um cano só, porque dois
# critérios com o mesmo nome divergem (RECEITA-ERRADA-01) e a tela passa a
# prometer o que a cura não faz.
#
# Imprime uma linha por nó ABERTO A OUTROS (os fechados não são sintoma nenhum):
#
#   alvo <nó> <modo>                 -> nenhuma regra udev explica: restaurar VALE
#   pulo <nó> manta    <arq:linha>   -> uma regra abre TODO hidraw
#   pulo <nó> estreita <arq:linha>   -> uma regra abre ESTE aparelho, de propósito
#   pulo <nó> incerta  <arq:linha>   -> abre hidraw estreitando por chave que não
#                                       sei avaliar, ou o nó não tem ids legíveis
#
# Por que os três `pulo` são recusa, e não preguiça — as DUAS metades importam:
#
#   1. ATROPELO: quem escreveu a regra escolheu abrir aquilo. Um projeto de
#      gamepad reescrevendo permissão de aparelho alheio é invasão de
#      configuração, mesmo com a intenção certa;
#   2. INUTILIDADE: a regra continua lá. No próximo evento de udev (add/change)
#      ela reabre o nó, e o conserto nem dura até o replug.
#
# Uma das duas já bastaria para não agir. As duas juntas fazem do `pulo` a única
# resposta honesta — e é por isso que o texto diz as duas.
_hidraw_alvos_do_restauro() {
    local devdir="${1:-/dev}" sysroot="${2:-/sys/class/hidraw}"
    [[ $# -gt 0 ]] && shift
    [[ $# -gt 0 ]] && shift
    local dirs=("$@")
    local mantas estreitas h mode ids linha end idlista casou incerta id
    mantas="$(_udev_hidraw_rw_global ${dirs[@]+"${dirs[@]}"})"
    estreitas="$(_udev_hidraw_rw_estreitas ${dirs[@]+"${dirs[@]}"})"
    for h in "${devdir}"/hidraw*; do
        [[ -e "${h}" ]] || continue
        mode="$(stat -c '%a' "${h}" 2>/dev/null || echo '?')"
        # Mesmo teste do check_perms_soft: último octeto != 0 = algum bit para
        # "outros". 4 (leitura) já basta — é a leitura que vaza a tecla.
        [[ "${mode}" =~ ^[0-7]*[1-7]$ ]] || continue
        if [[ -n "${mantas}" ]]; then
            printf 'pulo %s manta %s\n' "${h}" \
                   "$(printf '%s\n' "${mantas}" | head -n1 | cut -d: -f1,2)"
            continue
        fi
        ids="$(_hidraw_ids_do_no "${h}" "${sysroot}")"
        casou=""; incerta=""
        while IFS= read -r linha; do
            [[ -n "${linha}" ]] || continue
            end="$(printf '%s' "${linha}" | cut -d: -f1,2)"
            idlista="$(printf '%s' "${linha}" | cut -d: -f3)"
            if [[ -z "${idlista}" || -z "${ids}" ]]; then
                [[ -n "${incerta}" ]] || incerta="incerta ${end}"
                continue
            fi
            for id in ${ids//,/ }; do
                [[ -n "${id}" ]] || continue
                case ",${idlista}" in
                    *",${id},"*) casou="estreita ${end}" ;;
                esac
            done
            [[ -n "${casou}" ]] && break
        done <<< "${estreitas}"
        if [[ -n "${casou}" ]]; then
            printf 'pulo %s %s\n' "${h}" "${casou}"
        elif [[ -n "${incerta}" ]]; then
            printf 'pulo %s %s\n' "${h}" "${incerta}"
        else
            printf 'alvo %s %s\n' "${h}" "${mode}"
        fi
    done
}

# O que o nó hidraw É, em palavra humana — para o aviso poder dizer o que está
# aberto em vez de só o caminho. Sem udevadm, devolve vazio (e o aviso degrada
# para o nome do nó, que é melhor que nada).
_hidraw_classe_humana() {
    local no="${1##*/}" sys="${2:-/sys/class/hidraw}/${1##*/}/device" nome="" props="" classe=""
    command -v udevadm >/dev/null 2>&1 || return 0
    [[ -d "${sys}" ]] || return 0
    nome="$(udevadm info -q property -p "${sys}" 2>/dev/null \
            | sed -n 's/^HID_NAME=//p' | head -n1)"
    local i
    for i in "${sys}"/input/input*; do
        [[ -d "${i}" ]] || continue
        props+="$(udevadm info -q property -p "${i}" 2>/dev/null \
                  | grep -E '^ID_INPUT_(KEYBOARD|MOUSE)=1' || true)"$'\n'
    done
    [[ "${props}" == *ID_INPUT_KEYBOARD=1* ]] && classe="teclado"
    if [[ "${props}" == *ID_INPUT_MOUSE=1* ]]; then
        classe="${classe:+${classe}+}mouse"
    fi
    printf '%s' "${classe:+${classe} }${nome:-${no}}"
}

# ACUSA-O-CULPADO-01: UM aviso por CAUSA, não um por nó. Uma linha de regra
# produziu quatro avisos idênticos em 06/08 — quatro vezes a mesma notícia, e
# nenhuma vez o endereço.
#
# O grau continua [WARN] DE PROPÓSITO, e isso foi decidido, não esquecido: só o
# `fail` alimenta o `FAILS` que é o código de saída do doctor. Fazer a
# configuração de um programa de TERCEIRO reprovar o portão de saúde do Hefesto
# seria dizer "estou doente" por algo que não é nosso, e empurrar quem usa a
# desinstalar o vizinho para o nosso relatório ficar verde. A gravidade vai no
# TEXTO, que é onde ela sempre deveria ter estado.
check_perms_soft() {
    local devdir="${1:-/dev}" sysroot="${2:-/sys/class/hidraw}"
    [[ $# -gt 0 ]] && shift
    [[ $# -gt 0 ]] && shift
    local dirs=("$@")
    local h mode abertos=() classes="" causas="" plano="" tipo no campo3 campo4
    local alvos=() pulo_no=() pulo_motivo=() pulo_end=()
    for h in "${devdir}"/hidraw*; do
        [[ -e "$h" ]] || continue
        mode="$(stat -c '%a' "$h" 2>/dev/null || echo '?')"
        # Último octeto != 0 = algum bit para "outros". 4 (leitura) já basta:
        # hidraw entrega os relatórios de entrada CRUS, em paralelo ao evdev —
        # quem lê o nó do receptor do teclado lê o que está sendo digitado.
        [[ "${mode}" =~ ^[0-7]*[1-7]$ ]] || continue
        abertos+=("${h}")
        classes+="  ${h} (${mode}): $(_hidraw_classe_humana "${h}" "${sysroot}")"$'\n'
    done
    [[ ${#abertos[@]} -eq 0 ]] && return 0
    causas="$(_udev_hidraw_rw_global ${dirs[@]+"${dirs[@]}"})"
    # O MESMO cano que a cura usa. Se o check calculasse por conta própria, a
    # tela ofereceria o que a cura recusaria — foi exatamente esse o defeito da
    # RECEITA-ERRADA-01, e é o único jeito de ele não voltar.
    plano="$(_hidraw_alvos_do_restauro "${devdir}" "${sysroot}" ${dirs[@]+"${dirs[@]}"})"
    while read -r tipo no campo3 campo4; do
        case "${tipo}" in
            alvo) alvos+=("${no}") ;;
            pulo) pulo_no+=("${no}"); pulo_motivo+=("${campo3}"); pulo_end+=("${campo4}") ;;
        esac
    done <<< "${plano}"
    if [[ -n "${causas}" ]]; then
        warn "${#abertos[@]} nó(s) hidraw abertos a qualquer usuário local — QUALQUER processo, sem privilégio, lê o que esses aparelhos reportam"
    elif [[ ${#alvos[@]} -gt 0 ]]; then
        warn "${#abertos[@]} nó(s) hidraw abertos a qualquer usuário local, e NENHUMA regra udev explica — aí sim, ajuste manual é hipótese (esperado é 0660+uaccess)"
    else
        # RESTAURO-SO-COM-SINTOMA-01, nota datada de 07/08/2026: até aqui esta
        # linha era a de cima, e ela AFIRMAVA "NENHUMA regra udev explica" sempre
        # que a varredura de manta voltava vazia. Isso é falso quando a regra
        # estreita por aparelho — que é justamente o caso que a varredura de
        # manta se recusa a acusar, por decisão medida de ACUSA-O-CULPADO-01.
        # CONTROLE POSITIVO vivo nesta máquina em 07/08:
        # `/usr/lib/udev/rules.d/71-pdp-controllers.rules:8` abre um controle PDP
        # com MODE="0666" estreitando por `ATTRS{idVendor}=="0e6f"`. Com esse
        # controle no cabo, o doctor dizia "ninguém explica" sobre um nó que a
        # distribuição abriu de propósito.
        warn "${#abertos[@]} nó(s) hidraw abertos a qualquer usuário local, e uma regra udev ESTREITADA por aparelho explica cada um — é decisão de quem escreveu a regra, não defeito do Hefesto"
    fi
    printf '%s' "${classes}"
    if [[ -n "${causas}" ]]; then
        info "  CAUSA (regra udev que abre TODO hidraw, sem estreitar por aparelho):"
        printf '%s\n' "${causas}" | while IFS= read -r linha; do
            [[ -n "${linha}" ]] && info "    ${linha}"
        done
        info "  este arquivo NÃO é do Hefesto — a decisão de mantê-lo é de quem o instalou."
        # AFIRMACAO-SO-NO-ESTADO-DELA-01 (06/08/2026, achado de verificação
        # adversarial): esta linha afirmava, sem condição, que "os aparelhos do
        # Hefesto não são afetados". É verdade só quando o culpado está numerado
        # ABAIXO das nossas regras — que é o estado desta bancada (culpado em 60,
        # nós em 70+). É FALSA em três estados plausíveis, e um deles é o mais
        # provável de todos: a receita de internet mais copiada para hidraw é
        # `99-hidraw-permissions.rules`, que roda DEPOIS de nós e vence. Os
        # outros dois: `MODE:=` (atribuição final, que ninguém desfaz) e a
        # máquina sem as nossas regras instaladas — que é justamente quando se
        # roda o doctor.
        #
        # Então a frase passa a ser MEDIDA em vez de afirmada: só sai quando o
        # menor número de regra nossa é maior que o do culpado, e nenhum culpado
        # usa `:=`.
        # `causas` vem como "arquivo:linha:conteúdo", uma por linha.
        _rules_nossas="$(ls /etc/udev/rules.d/7*-ps5-controller.rules 2>/dev/null | head -1)"
        _culpado_tardio=0
        while IFS= read -r _entrada; do
            [[ -z "${_entrada}" ]] && continue
            _arq="${_entrada%%:*}"
            _num="$(basename "${_arq}" | sed -n 's/^\([0-9]\{1,3\}\).*/\1/p')"
            if [[ -n "${_num}" ]] && [[ "${_num}" -ge 70 ]]; then
                _culpado_tardio=1
            fi
            case "${_entrada}" in
                *MODE\ :=*|*MODE:=*) _culpado_tardio=1 ;;
            esac
        done <<< "${causas}"
        if [[ -z "${_rules_nossas}" ]]; then
            info "  as regras do Hefesto NÃO estão instaladas aqui — então nada devolve esses nós ao esperado; rode ./install.sh."
        elif [[ "${_culpado_tardio}" -eq 1 ]]; then
            info "  ATENÇÃO: a regra acima roda DEPOIS das do Hefesto (ou usa 'MODE:='), então ela vence — os nós dos controles também ficam abertos."
        else
            info "  os aparelhos do Hefesto não são afetados: a regra deles roda depois e os devolve a 0660+uaccess."
        fi
    fi
    # A OFERTA — decisão dela de 07/08/2026, resposta 16 do painel: o restauro
    # mora no doctor e só aparece quando há sintoma. O diagnóstico NÃO age: ele
    # diz que o conserto existe, o que ele vai fazer antes de fazer, e o que ele
    # não resolve. Diagnóstico que conserta sozinho é o oposto de diagnóstico.
    if [[ ${#alvos[@]} -gt 0 ]]; then
        info "  o conserto EXISTE e não roda sozinho: scripts/doctor.sh --restaurar-hidraw-uaccess"
        info "  o que ele VAI fazer, e nada além disso: tirar o bit de OUTROS de ${#alvos[@]} nó(s) — ${alvos[*]}"
        info "  o que ele NÃO faz: não cria regra udev, não escreve em /etc, não concede acesso a ninguém e não toca em nó que alguma regra explique."
        info "  o que ele NÃO resolve: ele não IMPEDE o nó de reabrir. Se o nó voltar a abrir depois, existe regra que este diagnóstico não lê (ENV{...}, GOTO, ou programa fora do udev) — e aí o conserto não dura."
    elif [[ ${#pulo_no[@]} -gt 0 ]]; then
        # RECEITA-ERRADA-01: citar o comando para dizer que ele NÃO serve é
        # honestidade; mandar rodá-lo é que era o defeito.
        info "  o --restaurar-hidraw-uaccess NÃO resolve este caso, e por isso ele não é oferecido aqui:"
        local i
        for i in "${!pulo_no[@]}"; do
            case "${pulo_motivo[$i]}" in
                manta)
                    info "    ${pulo_no[$i]}: a regra ${pulo_end[$i]} abre TODO hidraw — fechar agora desfaria o que esse arquivo manda de propósito, e o nó reabriria no próximo evento de udev"
                    ;;
                estreita)
                    info "    ${pulo_no[$i]}: a regra ${pulo_end[$i]} abre ESTE aparelho, estreitando por ele — a decisão é de quem escreveu a regra, e o nó reabriria no próximo evento de udev"
                    ;;
                *)
                    info "    ${pulo_no[$i]}: a regra ${pulo_end[$i]} abre hidraw estreitando por chave que não sei avaliar — não mexo no que não consigo provar que está órfão"
                    ;;
            esac
        done
    fi
}

# A CURA de RESTAURO-SO-COM-SINTOMA-01 — decisão dela, 07/08/2026, resposta 16
# do painel: *"o `--restaurar-hidraw-uaccess`: só no `doctor`, quando houver
# sintoma"*.
#
# POR QUE NÃO ENTRA NO INSTALL, na palavra dela: o install roda SEMPRE, e
# reescreveria permissão que outro programa pôs de propósito. O caso concreto
# desta casa é o OpenRGB (ACUSA-O-CULPADO-01). Pelo mesmo motivo isto NÃO entra
# no `--fix`: o `--fix` é o laço que roda tudo de uma vez, e roda ANTES dos
# checks — agiria sem sintoma nenhum. Há teste que cobra as duas ausências.
#
# O QUE ELE FAZ, por inteiro: `chmod o=` nos nós que o critério aprovou. Só
# isso. Não instala regra, não escreve em /etc, não concede acesso a ninguém.
#
# Por que o mecanismo é `chmod o=` e não `chmod 0660` nem `setfacl`:
#
#   - `chmod o=` tira SÓ o bit de outros: mexe na entrada `other::` e não toca
#     no `mask::` nem nas entradas nomeadas. `chmod 0660` escreveria a classe de
#     GRUPO, que num nó com ACL é a MÁSCARA — e o efeito medido não é fechar, é
#     ABRIR. MEDIDO nesta bancada em 07/08/2026, num nó com
#     `user:nobody:rwx` sob `mask::r--`:
#
#         chmod 0660  ->  mask::rw-   e nobody sai de #effective:r-- para rw-
#         chmod o=    ->  mask::r--   intacta, nobody continua em r--
#
#     Ou seja: o `chmod 0660` CONCEDE, no meio de uma operação que se chama
#     restauro, uma escrita que alguém tinha mascarado de propósito. GRAU:
#     MEDIDO (o teste `test_a_cura_nao_alarga_a_mascara_da_acl` reprova com a
#     troca feita — e a primeira versão dele NÃO reprovava, porque olhava um nó
#     cuja máscara já era `rw-`: nesse nó os dois comandos dão no mesmo);
#   - CONCEDER acesso não é RESTAURAR. Um `setfacl` nosso num nó alheio daria à
#     sessão acesso que ela não tinha — que é precisamente o que a casa recusou
#     por escrito (2026-08-06-RECOMENDACAO-A-ELA, "o que o Hefesto NÃO vai
#     fazer"): projeto de gamepad não legisla a política de segurança da máquina
#     inteira. Quem CONCEDE o uaccess aos nós do Hefesto é a regra udev — o
#     `./install.sh` e o `scripts/doctor.sh --fix`, que a reaplicam.
#
# O nome da opção é o DELA (resposta 16) e não foi trocado; a metade "uaccess"
# do nome descreve o estado a que os nós do Hefesto voltam, não uma concessão
# que este comando faça.
restaurar_hidraw_uaccess() {
    local devdir="${1:-/dev}" sysroot="${2:-/sys/class/hidraw}"
    [[ $# -gt 0 ]] && shift
    [[ $# -gt 0 ]] && shift
    local dirs=("$@")
    local plano tipo no campo3 campo4 i alvo modo depois
    local alvos=() modos=() pulo_no=() pulo_motivo=() pulo_end=()

    # AGIR CALADO É O QUE NÃO PODE ACONTECER. O `--quiet` existe para o
    # diagnóstico caber numa linha de log; aqui ele apagaria justamente o texto
    # que diz o que vai ser feito ANTES de ser feito. Neste modo ele não vale.
    QUIET=0

    plano="$(_hidraw_alvos_do_restauro "${devdir}" "${sysroot}" ${dirs[@]+"${dirs[@]}"})"
    while read -r tipo no campo3 campo4; do
        case "${tipo}" in
            alvo) alvos+=("${no}"); modos+=("${campo3}") ;;
            pulo) pulo_no+=("${no}"); pulo_motivo+=("${campo3}"); pulo_end+=("${campo4}") ;;
        esac
    done <<< "${plano}"

    if [[ ${#alvos[@]} -eq 0 ]]; then
        if [[ ${#pulo_no[@]} -eq 0 ]]; then
            pass "nenhum nó hidraw aberto a outros — não há o que restaurar (é este o estado esperado)"
            return 0
        fi
        info "não vou tocar em nada, e o motivo é este — em cada caso, mexer seria ao mesmo tempo atropelo e inútil:"
        for i in "${!pulo_no[@]}"; do
            case "${pulo_motivo[$i]}" in
                manta)
                    info "  ${pulo_no[$i]}: a regra ${pulo_end[$i]} abre TODO hidraw — fechar agora desfaria o que esse arquivo manda de propósito, e o nó reabriria no próximo evento de udev"
                    ;;
                estreita)
                    info "  ${pulo_no[$i]}: a regra ${pulo_end[$i]} abre ESTE aparelho, estreitando por ele — a decisão é de quem escreveu a regra, e o nó reabriria no próximo evento de udev"
                    ;;
                *)
                    info "  ${pulo_no[$i]}: a regra ${pulo_end[$i]} abre hidraw estreitando por chave que não sei avaliar — não mexo no que não consigo provar que está órfão"
                    ;;
            esac
        done
        info "se a permissão desse arquivo estiver errada, o conserto é no arquivo, não no nó: edite a regra e rode 'sudo udevadm control --reload-rules'."
        return 0
    fi

    # O TEXTO ANTES DA AÇÃO (RECEITA-ERRADA-01): quem lê tem de saber o que vai
    # acontecer enquanto ainda dá para desistir.
    info "vou tirar o bit de OUTROS destes ${#alvos[@]} nó(s), e nada além disso:"
    for i in "${!alvos[@]}"; do
        info "  ${alvos[$i]}: ${modos[$i]} -> ${modos[$i]%?}0   ($(_hidraw_classe_humana "${alvos[$i]}" "${sysroot}"))"
    done
    info "nenhuma regra udev é criada, nada é escrito em /etc, e nenhum acesso é concedido a ninguém."
    info "o que isto NÃO resolve: não IMPEDE o nó de reabrir. Se ele voltar a abrir, existe regra que este diagnóstico não lê (ENV{...}, GOTO, ou programa fora do udev) — e aí o conserto não dura."
    info "quem CONCEDE o uaccess aos nós do Hefesto é a regra udev, não este comando: ./install.sh ou scripts/doctor.sh --fix."

    for i in "${!alvos[@]}"; do
        alvo="${alvos[$i]}"
        # Sem sudo primeiro: quem já pode (root, ou dono do nó) não gasta
        # elevação, e a suíte exercita a cura DE VERDADE sem privilégio nenhum.
        if ! chmod o= "${alvo}" 2>/dev/null; then
            if command -v sudo >/dev/null 2>&1; then
                sudo chmod o= "${alvo}" 2>/dev/null || true
            fi
        fi
        depois="$(stat -c '%a' "${alvo}" 2>/dev/null || echo '?')"
        modo="${modos[$i]}"
        if [[ "${depois}" =~ ^[0-7]*[1-7]$ ]]; then
            fail "${alvo} continua aberto a outros (${modo} -> ${depois}) — o chmod não pegou; confira quem é o dono do nó (ls -l ${alvo})"
        else
            pass "${alvo} restaurado (${modo} -> ${depois})"
        fi
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

# ---------------------------------------------------------------------------
# Onda T — patch DKMS do hid-nintendo (probe BT resiliente + module params).
# Desenho: docs/process/estudos/2026-07-20-desenho-onda-t-patch-dkms.md.
# ---------------------------------------------------------------------------
# Nomes fixos (mesmos do assets/dkms/hid-nintendo/dkms.conf) — mudar de
# versão exige atualizar os dois lados.
readonly HEFESTO_DKMS_HID_NINTENDO_PKG="hefesto-hid-nintendo"
readonly HEFESTO_DKMS_HID_NINTENDO_VER="1.0.0"

# T-2/PKG-1 (auditoria 21/07): kernel contra o qual os patches T e W foram
# escritos/testados (KERNEL_TESTED dos dois BASELINE — hoje o mesmo). Num
# upgrade de kernel em que o .c ainda COMPILE, o DKMS de safra antiga mascara
# para sempre o in-tree mais novo (fixes/devices novos) e o doctor daria pass.
readonly HEFESTO_DKMS_KERNEL_TESTED="7.0.11-76070011-generic"

# Guard idempotente do aviso de Secure Boot (PKG-1): as duas seções DKMS
# chamam o helper, mas o aviso sai UMA vez por execução do doctor.
_DKMS_SB_WARNED=0

# T-2: WARN (não fail) quando o kernel atual difere do KERNEL_TESTED — o
# módulo patchado de safra antiga pode estar mascarando um in-tree mais novo.
_check_dkms_kernel_drift() {
    local kver
    kver="$(uname -r)"
    if [[ "${kver}" != "${HEFESTO_DKMS_KERNEL_TESTED}" ]]; then
        warn "kernel atual (${kver}) != kernel testado dos patches DKMS (${HEFESTO_DKMS_KERNEL_TESTED}) — se o build passou, o módulo do hefesto pode estar MASCARANDO um in-tree mais novo (fixes/suporte a devices); confira o rebase do BASELINE antes de confiar na cura, ou 'sudo dkms remove' para voltar ao in-tree"
    fi
}

# PKG-1: com Secure Boot enforcing e MOK não enrolado, o load do .ko de
# updates/dkms FALHA e NÃO há fallback automático ao in-tree (modules.dep
# aponta um caminho só) — a máquina ficaria sem hid-nintendo E/OU WiFi no
# boot seguinte. Só avisa se mokutil existe, SB está ON e há .ko do hefesto.
_check_dkms_secureboot() {
    [[ "${_DKMS_SB_WARNED}" -eq 1 ]] && return
    command -v mokutil >/dev/null 2>&1 || return
    mokutil --sb-state 2>/dev/null | grep -qi 'SecureBoot enabled' || return
    local kver; kver="$(uname -r)"
    if compgen -G "/lib/modules/${kver}/updates/dkms/*.ko*" >/dev/null 2>&1; then
        _DKMS_SB_WARNED=1
        warn "Secure Boot ATIVO + módulos DKMS em updates/dkms — se a chave MOK do DKMS não estiver enrolada, o kernel RECUSA o .ko no boot e NÃO cai no in-tree (máquina sem hid-nintendo/WiFi): enrole a chave (sudo mokutil --import /var/lib/dkms/mok.pub) ou assine os módulos; nvidia-DKMS funcionando é bom sinal de que já está resolvido"
    fi
}

# Onda T (assinatura complementar à cascata de check_hid_nintendo_bt_cascade
# acima): "exceeded max attempts" DENSO mas SEM a cascata de timeouts que o
# gate `_hid_nintendo_cascade_scan` exige (>=10) aponta para OUTRA coisa —
# jitter/contenda de rádio (BT degradado mas NÃO morto), não a queda
# terminal. Função PURA (mesma leitura de journal, stdin → stdout): gate
# PRÓPRIO (exceeded >= $1, default 5, E timeouts < exceeded na MESMA
# instância hid). Journal limpo ou só a cascata terminal => saída vazia.
_hid_nintendo_dense_exceeded_scan() {
    local min="${1:-5}"
    sed -nE \
        -e 's/^.*([0-9A-Fa-f]{4}:[0-9A-Fa-f]{4}:[0-9A-Fa-f]{4}\.[0-9A-Fa-f]{4}).*timeout waiting for input report.*$/\1 timeout/p' \
        -e 's/^.*([0-9A-Fa-f]{4}:[0-9A-Fa-f]{4}:[0-9A-Fa-f]{4}\.[0-9A-Fa-f]{4}).*joycon_enforce_subcmd_rate: exceeded max attempts.*$/\1 exceeded/p' \
      | awk -v min="${min}" '
            $2 == "timeout"  { t[$1]++ }
            $2 == "exceeded" { e[$1]++ }
            END {
                for (i in e) {
                    to = (i in t ? t[i] : 0)
                    if (e[i] >= min && to < e[i]) printf "%s %d %d\n", i, e[i], to
                }
            }
        ' | sort
}

# Assinaturas do estudo de premissas (LER: docs/process/estudos/2026-07-20-
# estudo-premissas-onda-t-hid-nintendo.md, premissa 7) que HOJE não têm check
# dedicado: a morte por PROBE (o driver falha ANTES de registrar o device —
# "exceeded max attempts" nem entra na cadeia, então check_hid_nintendo_bt_
# cascade não vê nada) e o "exceeded" denso sem cascata (acima). Usa
# `_TRANSPORT=kernel` — NUNCA `journalctl -k` sozinho para checks novos (a
# armadilha "-k implica -b" documentada no sprint T0 já confundiu um
# diagnóstico desta onda); `-b` aqui é explícito e proposital (histórico
# deste boot, mesmo escopo do check_hid_nintendo_bt_cascade acima).
_check_hid_nintendo_probe_death_signature() {
    command -v journalctl >/dev/null 2>&1 || return 0
    local jlog info_fail probe_fail retry_hits
    jlog="$(journalctl -b _TRANSPORT=kernel --no-pager 2>/dev/null)"
    [[ -z "${jlog}" ]] && return 0
    info_fail="$(printf '%s\n' "${jlog}" | grep -ciE 'Failed to get joycon info; ret=-[0-9]+' || true)"
    probe_fail="$(printf '%s\n' "${jlog}" | grep -ciE 'probe - fail = -[0-9]+' || true)"
    retry_hits="$(printf '%s\n' "${jlog}" | grep -ciE 'init over bluetooth failed.*retrying' || true)"
    info_fail="${info_fail:-0}"; probe_fail="${probe_fail:-0}"; retry_hits="${retry_hits:-0}"
    if [[ "${info_fail}" -gt 0 && "${probe_fail}" -gt 0 ]]; then
        warn "morte por PROBE do hid-nintendo neste boot: ${info_fail}x 'Failed to get joycon info' + ${probe_fail}x 'probe - fail' — o driver falhou ANTES de registrar o device e o in-tree NÃO re-proba sozinho; sem o patch DKMS, replug/power-cycle é a única saída"
        if [[ "${retry_hits}" -gt 0 ]]; then
            info "o retry do patch DKMS está agindo (${retry_hits}x 'init over bluetooth failed; retrying') — se o probe passou depois, a cura funcionou"
        else
            info "sem sinal do retry do patch neste boot — confira acima se o módulo CARREGADO é o patchado"
        fi
    fi
}

_check_hid_nintendo_exceeded_dense_signature() {
    command -v journalctl >/dev/null 2>&1 || return 0
    local hits
    hits="$(journalctl -b _TRANSPORT=kernel --no-pager 2>/dev/null | _hid_nintendo_dense_exceeded_scan)"
    [[ -z "${hits}" ]] && return 0
    local inst n_exc n_to
    while read -r inst n_exc n_to; do
        [[ -z "${inst}" ]] && continue
        warn "interferência/contenda BT no controle Nintendo/8BitDo (instância ${inst}, neste boot): ${n_exc}x 'exceeded max attempts' com só ${n_to}x timeout — rádio degradado SEM a cascata de morte terminal (gate >=10 timeouts do check acima); o link não caiu, mas está sob contenda"
    done <<<"${hits}"
}

# Check principal da Onda T: o patch DKMS está instalado/ativo? Read-only —
# NUNCA chama modprobe/rmmod/dkms install aqui (isso é do install.sh).
check_hefesto_hid_nintendo_dkms() {
    if ! command -v dkms >/dev/null 2>&1; then
        info "dkms ausente — patch DKMS do hid-nintendo (Onda T) não instalado (opcional; ./install.sh instala por default, ou: sudo apt install dkms)"
        return
    fi
    local kver status
    kver="$(uname -r)"
    status="$(dkms status "${HEFESTO_DKMS_HID_NINTENDO_PKG}/${HEFESTO_DKMS_HID_NINTENDO_VER}" 2>/dev/null)"
    if [[ -z "${status}" ]]; then
        info "patch DKMS do hid-nintendo (Onda T) não instalado — driver in-tree em uso (cura de raiz do probe BT: ./install.sh no checkout do repo, ou, instalado por pacote .deb/rpm/arch: sudo /usr/share/hefesto-dualsense4unix/scripts/install-host-udev.sh; opt-out: --no-dkms)"
        return
    fi
    if printf '%s\n' "${status}" | grep -qF ", ${kver}"; then
        pass "DKMS ${HEFESTO_DKMS_HID_NINTENDO_PKG}/${HEFESTO_DKMS_HID_NINTENDO_VER} construído p/ o kernel atual (${kver})"
        _check_dkms_kernel_drift
    else
        warn "DKMS ${HEFESTO_DKMS_HID_NINTENDO_PKG} instalado mas NÃO p/ o kernel atual (${kver}) — rebase pendente, in-tree em uso; status: ${status}"
    fi
    _check_dkms_secureboot

    # Próximo carregamento: NUNCA usar srcversion (armadilha do estudo — não
    # distingue in-tree de DKMS); modinfo -F filename aponta o caminho real.
    local modpath
    modpath="$(modinfo -F filename hid_nintendo 2>/dev/null)"
    if [[ "${modpath}" == */updates/dkms/* ]]; then
        info "próximo carregamento resolve para o módulo patchado (${modpath})"
    elif [[ -n "${modpath}" ]]; then
        info "próximo carregamento ainda resolve para o in-tree (${modpath}) — confira /etc/depmod.d ou rode: sudo depmod -a"
    fi

    # Módulo CARREGADO agora: só o patchado expõe parameters/ (0 params no
    # in-tree — confirmado byte a byte no estudo de premissas).
    if [[ -d /sys/module/hid_nintendo/parameters ]]; then
        local retries skiptx regleds
        retries="$(cat /sys/module/hid_nintendo/parameters/bt_probe_retries 2>/dev/null || echo '?')"
        skiptx="$(cat /sys/module/hid_nintendo/parameters/skip_tx_on_rate_exceeded 2>/dev/null || echo '?')"
        regleds="$(cat /sys/module/hid_nintendo/parameters/register_leds_on_set_failure 2>/dev/null || echo '?')"
        pass "módulo hid_nintendo CARREGADO é o patchado (bt_probe_retries=${retries}, skip_tx_on_rate_exceeded=${skiptx}, register_leds_on_set_failure=${regleds}; esperados 3/Y/Y via /etc/modprobe.d/hefesto-hid-nintendo.conf — regleds '?' = módulo anterior ao fix 21/07, reinstale)"
    elif [[ -d /sys/module/hid_nintendo ]]; then
        warn "módulo hid_nintendo carregado é o in-tree (sem parameters/) — o patchado vale SÓ no próximo boot (replug NÃO troca módulo carregado: re-liga no driver residente; substituir módulo em uso derrubaria Pro Controller/8BitDo conectados)"
    else
        info "hid_nintendo não está carregado agora (sem controle Nintendo/8BitDo plugado?)"
    fi

    _check_hid_nintendo_probe_death_signature
    _check_hid_nintendo_exceeded_dense_signature
}

# ---------------------------------------------------------------------------
# Onda W — patch DKMS do rtw88_usb (device-gone + queue de port reset — cura
# do fantasma USB do dongle WiFi). Desenho:
# docs/process/estudos/2026-07-20-desenho-onda-w-patch-dkms.md.
# ---------------------------------------------------------------------------
# Nomes fixos (mesmos do assets/dkms/rtw88-usb/dkms.conf) — mudar de versão
# exige atualizar os dois lados.
readonly HEFESTO_DKMS_RTW88_PKG="hefesto-rtw88-usb"
readonly HEFESTO_DKMS_RTW88_VER="1.0.0"

# Check principal da Onda W: o patch DKMS está instalado/ativo? Read-only —
# NUNCA chama modprobe/rmmod/dkms install aqui (isso é do install.sh).
check_hefesto_rtw88_usb_dkms() {
    if ! command -v dkms >/dev/null 2>&1; then
        info "dkms ausente — patch DKMS do rtw88_usb (Onda W) não instalado (opcional; ./install.sh instala por default, ou: sudo apt install dkms)"
        return
    fi
    local kver status
    kver="$(uname -r)"
    status="$(dkms status "${HEFESTO_DKMS_RTW88_PKG}/${HEFESTO_DKMS_RTW88_VER}" 2>/dev/null)"
    if [[ -z "${status}" ]]; then
        info "patch DKMS do rtw88_usb (Onda W) não instalado — driver in-tree em uso (cura de raiz do fantasma USB do dongle WiFi: ./install.sh no checkout do repo, ou, instalado por pacote .deb/rpm/arch: sudo /usr/share/hefesto-dualsense4unix/scripts/install-host-udev.sh; opt-out: --no-dkms)"
        return
    fi
    if printf '%s\n' "${status}" | grep -qF ", ${kver}"; then
        pass "DKMS ${HEFESTO_DKMS_RTW88_PKG}/${HEFESTO_DKMS_RTW88_VER} construído p/ o kernel atual (${kver})"
        _check_dkms_kernel_drift
    else
        warn "DKMS ${HEFESTO_DKMS_RTW88_PKG} instalado mas NÃO p/ o kernel atual (${kver}) — rebase pendente OU kernel fora do pino BUILD_EXCLUSIVE_KERNEL (7.0.y é EOL, série nova precisa de rebase do BASELINE), in-tree em uso; status: ${status}"
    fi
    _check_dkms_secureboot

    # Próximo carregamento: NUNCA usar srcversion (mesma armadilha do estudo
    # da Onda T — não distingue in-tree de DKMS); modinfo -F filename aponta
    # o caminho real.
    local modpath
    modpath="$(modinfo -F filename rtw88_usb 2>/dev/null)"
    if [[ "${modpath}" == */updates/dkms/* ]]; then
        info "próximo carregamento resolve para o módulo patchado (${modpath})"
    elif [[ -n "${modpath}" ]]; then
        info "próximo carregamento ainda resolve para o in-tree (${modpath}) — confira /etc/depmod.d ou rode: sudo depmod -a"
    fi

    # Módulo CARREGADO agora: diferente do hid_nintendo (0 params no
    # in-tree), o rtw88_usb in-tree JÁ expõe parameters/ (switch_usb_mode) —
    # o marcador exclusivo do patchado é o PARÂMETRO NOVO hang_reset.
    if [[ -e /sys/module/rtw88_usb/parameters/hang_reset ]]; then
        local hang
        hang="$(cat /sys/module/rtw88_usb/parameters/hang_reset 2>/dev/null || echo '?')"
        pass "módulo rtw88_usb CARREGADO é o patchado (hang_reset=${hang}; Y = usb_queue_reset_device ativo em device-gone, N = só detecção/silenciamento)"
    elif [[ -d /sys/module/rtw88_usb ]]; then
        warn "módulo rtw88_usb carregado é o in-tree (sem hang_reset) — o patchado vale SÓ no próximo boot (replug NÃO troca módulo carregado: o dongle re-liga no driver residente; substituir módulo em uso derrubaria o WiFi)"
    else
        info "rtw88_usb não está carregado agora (dongle WiFi desconectado?)"
    fi
}

# Assinatura do fantasma USB (W1, medido 20/07: 13h de device retido após um
# port-status-change perdido no xHCI). Read-only, três ângulos independentes
# — cada um vira warn com a cura; journal do BOOT ATUAL só (mesma disciplina
# do check_usb_dropout acima).
check_usb_fantasma() {
    local d driver idv idp key any=0
    local -A _seen=()

    # (a) DUPLICATA: mais de um device em /sys/bus/usb/devices/* com o mesmo
    # idVendor:idProduct AINDA vinculado ao driver rtw88_usb — a assinatura
    # real do incidente (fantasma + device vivo re-enumerado, mesmos IDs, um
    # único dongle físico).
    for d in /sys/bus/usb/devices/*; do
        [[ -r "$d/idVendor" && -r "$d/idProduct" ]] || continue
        driver="$(basename "$(readlink -f "$d/driver" 2>/dev/null || true)" 2>/dev/null)"
        [[ "${driver}" == "rtw88_usb" ]] || continue
        idv="$(cat "$d/idVendor" 2>/dev/null)"
        idp="$(cat "$d/idProduct" 2>/dev/null)"
        key="${idv}:${idp}"
        if [[ -n "${_seen[$key]:-}" ]]; then
            any=1
            warn "device USB fantasma: $(basename "$d") E ${_seen[$key]} vinculados ao MESMO driver rtw88_usb com idVendor:idProduct=${key} — só existe um dongle físico; um 'USB disconnect' não foi processado. Cura: sudo sh -c 'echo ${_seen[$key]} > /sys/bus/usb/drivers/rtw88_usb/unbind' (confira o endereço exato) ou reboot"
        else
            _seen["${key}"]="$(basename "$d")"
        fi
    done

    # (b) journal do boot com colisão de rename do udev — o dano concreto do
    # fantasma (a interface nova não consegue assumir o nome wlx... que o
    # device fantasma ainda segura). NÃO restrito a _TRANSPORT=kernel: quem
    # renomeia é o systemd-udevd (userspace).
    if command -v journalctl >/dev/null 2>&1; then
        local rename_n
        rename_n="$(journalctl -b --no-pager 2>/dev/null \
            | grep -ciE 'wlx[0-9a-f]+.*(File exists|Arquivo existe)' || true)"
        rename_n="${rename_n:-0}"
        if [[ "${rename_n}" -gt 0 ]]; then
            any=1
            warn "colisão de rename do udev neste boot: ${rename_n}x 'wlx... File exists/Arquivo existe' — sintoma do fantasma (a interface nova não consegue assumir o nome que o device fantasma ainda segura)"
        fi
    fi

    # (c) device com driver rtw88_usb em sysfs SEM filho net/ (nunca virou
    # interface de rede, ou a perdeu) + -71 recente no kernel log deste
    # device — o padrão do firmware wedged/disconnect perdido medido 20/07.
    if command -v journalctl >/dev/null 2>&1; then
        local jlog
        jlog="$(journalctl -b -k --no-pager 2>/dev/null)"
        for d in /sys/bus/usb/devices/*; do
            [[ -r "$d/idVendor" ]] || continue
            driver="$(basename "$(readlink -f "$d/driver" 2>/dev/null || true)" 2>/dev/null)"
            [[ "${driver}" == "rtw88_usb" ]] || continue
            if find "$d" -maxdepth 2 -type d -name net 2>/dev/null | grep -q .; then
                continue
            fi
            local devname eproto_n
            devname="$(basename "$d")"
            eproto_n="$(printf '%s\n' "${jlog}" | grep -c "usb ${devname}:.*error -71" || true)"
            eproto_n="${eproto_n:-0}"
            if [[ "${eproto_n}" -gt 0 ]]; then
                any=1
                warn "device USB ${devname} (driver rtw88_usb) SEM interface de rede (net/) e com ${eproto_n}x '-71' neste boot — assinatura de device-gone (firmware wedged ou disconnect perdido). Cura: sudo sh -c 'echo ${devname} > /sys/bus/usb/drivers/rtw88_usb/unbind' ou reboot"
            fi
        done
    fi

    [[ "${any}" -eq 0 ]] && pass "sem sinal de device USB fantasma (rtw88_usb) neste boot"
}

# Powersave EFETIVO do WiFi (W2 — vilão ATIVO é o LPS RASO via mac80211,
# ligado hoje por wifi.powersave=3 do NetworkManager; disable_lps_deep é
# NO-OP em USB, não é medido/julgado aqui). Leitura SÓ de arquivo (conf.d) —
# NUNCA invoca nmcli/rfkill (regra da casa: doctor é read-only e não toca
# NetworkManager). Sem julgamento até scripts/medir_w2_lps.sh medir A/B.
check_wifi_powersave() {
    local -a files=(/etc/NetworkManager/NetworkManager.conf)
    if [[ -d /etc/NetworkManager/conf.d ]]; then
        local f
        while IFS= read -r -d '' f; do
            files+=("${f}")
        done < <(find /etc/NetworkManager/conf.d -maxdepth 1 -name '*.conf' -print0 2>/dev/null | sort -z)
    fi
    local val="" src="" f hit
    for f in "${files[@]}"; do
        [[ -r "${f}" ]] || continue
        hit="$(sed -n 's/^[[:space:]]*wifi\.powersave[[:space:]]*=[[:space:]]*\([0-9]\+\).*/\1/p' "${f}" 2>/dev/null | tail -1)"
        [[ -n "${hit}" ]] && { val="${hit}"; src="${f}"; }
    done
    if [[ -z "${val}" ]]; then
        info "NetworkManager sem wifi.powersave configurado (default do driver/firmware vale) — não medido ainda: scripts/medir_w2_lps.sh"
    elif [[ "${val}" == "3" ]]; then
        info "wifi.powersave=3 (LIGA o power save do firmware) via ${src} — histórico de instabilidade em dongles Realtek USB (rtw88); meça antes de mudar: scripts/medir_w2_lps.sh"
    elif [[ "${val}" == "2" && "${src}" == "/etc/NetworkManager/conf.d/hefesto-wifi-powersave.conf" ]]; then
        pass "wifi.powersave=2 (desliga) via o conf.d do hefesto — opt-in aplicado após medição W2 confirmar ganho"
    else
        info "wifi.powersave=${val} via ${src}"
    fi

    if command -v journalctl >/dev/null 2>&1; then
        local n
        n="$(journalctl -b -k --no-pager 2>/dev/null | grep -ciE 'failed to leave lps state' || true)"
        n="${n:-0}"
        if [[ "${n}" -gt 0 ]]; then
            warn "${n}x 'failed to leave lps state' neste boot — assinatura do LPS raso (mac80211 emperrando ao sair do power save); reforça o histórico de instabilidade citado acima"
        fi
    fi
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

    # O watcher de auto-recuperação por authorized-toggle saiu do projeto: a
    # auditoria do storm de 26/06 mediu que re-enumerar por software realimenta
    # o próprio storm, e a cura de raiz é o quirk acima.
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

# IRMAO-SEM-CARONA-01 (12/08/2026) — quem reaplica as regras udev depende do
# layout em que ESTE doctor está rodando, e até aqui só um dos dois existia no
# código.
#
# MEDIDO: `scripts/build_deb.sh:216` leva o `doctor.sh` para dentro do pacote
# (`/usr/share/hefesto-dualsense4unix/scripts/`), e o `ROOT_DIR` deste arquivo
# é derivado do lugar dele (:60) — no .deb, portanto,
# `${ROOT_DIR}/scripts/install_udev.sh` NÃO EXISTE: aquele laço leva cinco
# scripts, e o `install_udev.sh` não é um deles. O que o pacote leva, e leva de
# propósito para este exato serviço, é o `install-host-udev.sh` (a forma 3 do
# cabeçalho dele: "Direto de um .deb instalado"). O resultado na máquina de
# quem instalou pelo pacote era `hefesto-dualsense4unix doctor --fix` dizendo
# "falha ao reaplicar udev" — cura prometida, caminho inexistente.
#
# A escolha é por EXISTÊNCIA, não por adivinhar o layout: o checkout tem os
# dois e o `install_udev.sh` vem primeiro porque é o dono nativo (conjunto
# canônico das regras); o pacote tem só o `install-host-udev.sh`, que resolve
# as regras em `/usr/share/hefesto-dualsense4unix/udev-rules/`. Se nenhum dos
# dois estiver aqui, o recado diz qual arquivo faltou — em vez do "falha ao
# reaplicar" mudo, que não distingue script ausente de script que reprovou.
#
# Portão: a seção "irmão sem carona" de `scripts/check_packaging_parity.sh`, e
# `tests/unit/test_portao_reprova_irmao_sem_carona.py`.
_dono_das_regras_udev() {
    if [[ -f "${ROOT_DIR}/scripts/install_udev.sh" ]]; then
        printf '%s' "${ROOT_DIR}/scripts/install_udev.sh"
        return 0
    fi
    if [[ -f "${ROOT_DIR}/scripts/install-host-udev.sh" ]]; then
        printf '%s' "${ROOT_DIR}/scripts/install-host-udev.sh"
        return 0
    fi
    return 1
}

apply_fixes() {
    hdr "aplicando correções (--fix)"
    local _udev_dono=""
    _udev_dono="$(_dono_das_regras_udev || true)"
    if [[ -z "${_udev_dono}" ]]; then
        warn "nem install_udev.sh nem install-host-udev.sh estão em ${ROOT_DIR}/scripts — não reapliquei udev"
    elif command -v sudo >/dev/null 2>&1; then
        if sudo bash "${_udev_dono}" >/dev/null 2>&1; then
            pass "regras udev reaplicadas ($(basename "${_udev_dono}"))"
        else
            warn "falha ao reaplicar udev ($(basename "${_udev_dono}"))"
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
    # MIC-USB-01: camadas 1 e 2 do microfone mudo. Depois do fix de áudio acima,
    # que pode reinstalar o drop-in e reiniciar o WirePlumber — o perfil da placa
    # e o mute da source precisam ser conferidos com o serviço já de pé.
    fix_mic_dualsense
    # AUSÊNCIA DELIBERADA — RESTAURO-SO-COM-SINTOMA-01, decisão dela de
    # 07/08/2026: `restaurar_hidraw_uaccess` NÃO é chamado aqui. O `--fix` roda
    # tudo de uma vez e roda ANTES dos checks, então chamá-lo daqui seria agir
    # sem sintoma — exatamente o motivo pelo qual ela recusou pôr isto no
    # install. O restauro só existe atrás da opção própria. Há teste que cobra
    # esta ausência, porque uma linha a mais aqui a desfaz em silêncio.
}

main() {
    [[ "${WATCH_DROPOUT}" -eq 1 ]] && { watch_dropout; exit 0; }
    [[ "${SUGGEST_PORT}" -eq 1 ]] && { suggest_port; exit 0; }
    # RESTAURO-SO-COM-SINTOMA-01 (decisão dela, 07/08/2026): rota própria, pedida
    # a dedo. Ela não é alcançável por nenhum outro modo do doctor — nem pelo
    # --fix, nem pelo install.
    if [[ "${RESTAURAR_HIDRAW}" -eq 1 ]]; then
        hdr "restauro de permissão dos nós hidraw (--restaurar-hidraw-uaccess)"
        restaurar_hidraw_uaccess
        [[ "${FAILS}" -eq 0 ]]
        exit $?
    fi
    # MIC-USB-01: rota curta para quem só quer o microfone de volta agora —
    # cura as camadas 1 e 2, mostra o veredito das duas e sai. É também o que o
    # `fix_wireplumber_default_source.sh --promote-source` chama, para a cura
    # das camadas ter UM dono só e não virar dois códigos que divergem.
    if [[ "${FIX_MIC}" -eq 1 ]]; then
        hdr "microfone do DualSense (MIC-USB-01 — camadas 1 e 2)"
        fix_mic_dualsense
        check_mic_mute_persistido
        check_mic_perfil_sem_sinal
        check_default_source_monitor
        info "camada 3 (mudo no firmware do controle): hefesto-dualsense4unix mic unmute"
        [[ "${FAILS}" -eq 0 ]]
        exit $?
    fi
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
    check_hid_playstation_probe_abortado
    check_led_sysfs_gravavel
    # OQ-6: logo depois do check da 77 (nó de LED gravável) porque é a mesma
    # pergunta — "a regra desta casa chegou a valer no nó vivo?" — só que para
    # os nós de ENTRADA do touchpad e dos sensores de movimento.
    check_input_uaccess
    hdr "energia USB e rádio"
    check_usb_power_devices
    check_usb_power_hosts
    check_pcie_aspm
    check_power_saboteurs
    check_btusb_autosuspend
    check_bluez_fastconnectable
    check_bluez_justworks_repairing
    check_bt_clone_ds4
    check_bt_radio
    check_bt_crc_counters
    check_kernel_watch
    check_cmdline_platform
    hdr "rádio e pareamento (G2)"
    check_bluez_backport_version
    check_bt_agent_service
    check_bt_resilience
    check_bt_bonds_persistidos
    check_bt_connected_sem_hidraw
    check_bt_sdp_cache_envenenado
    check_bt_paired_sem_bonded
    hdr "applet COSMIC"
    check_applet
    hdr "detector de janela (autoswitch / perfil-por-jogo)"
    check_window_detect
    check_perfis_inalcancaveis
    hdr "áudio (microfone)"
    check_wireplumber_source
    check_default_source_monitor
    check_dualsense_sink_disabled
    check_audio_sink_muted
    check_mic_mute_persistido
    check_mic_perfil_sem_sinal
    hdr "Steam Input"
    check_steam_input
    check_steam_input_allowlist
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
    hdr "teclado na tela (o que o L3 do controle abre)"
    check_teclado_na_tela
    hdr "controle"
    check_controller
    check_perms_soft
    check_hid_nintendo_bt_cascade
    hdr "DKMS hid-nintendo (Onda T — cura de raiz do probe BT)"
    check_hefesto_hid_nintendo_dkms
    hdr "DKMS rtw88_usb / WiFi (Onda W — fantasma USB + powersave)"
    check_hefesto_rtw88_usb_dkms
    check_usb_fantasma
    check_wifi_powersave
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
