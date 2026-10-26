#!/usr/bin/env bash

set -uo pipefail

readonly ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly APP_ID="hefesto-dualsense4unix"
readonly HOTPLUG_UNIT="hefesto-dualsense4unix-gui-hotplug.service"
readonly APPLET_DESKTOP="/usr/share/applications/com.vitoriamaria.HefestoDualsense4Unix.desktop"

DO_FIX=0
QUIET=0
WATCH_DROPOUT=0
SUGGEST_PORT=0
FIX_MIC=0; BASICO=0
RESTAURAR_HIDRAW=0
for arg in "$@"; do
    case "$arg" in
        --fix)            DO_FIX=1 ;;
        --fix-mic)        FIX_MIC=1 ;;
        --restaurar-hidraw-uaccess) RESTAURAR_HIDRAW=1 ;;
        --quiet)          QUIET=1 ;;
        --watch-dropout)  WATCH_DROPOUT=1 ;;
        --suggest-port)   SUGGEST_PORT=1 ;; --basico) BASICO=1 ;;
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

esta_instalacao_e_um_checkout() {
    [[ -f "${ROOT_DIR}/install.sh" ]]
}

_CONSELHO_GESTO_GENERICO="atualize o Hefesto pelo mesmo caminho por onde você o instalou"

_dono_do_arquivo() {
    local alvo="${1:?}"
    if command -v pacman >/dev/null 2>&1 && pacman -Qo "${alvo}" >/dev/null 2>&1; then
        printf 'arch'
    elif command -v dpkg >/dev/null 2>&1 && dpkg -S "${alvo}" >/dev/null 2>&1; then
        printf 'debian'
    elif command -v rpm >/dev/null 2>&1 && rpm -qf "${alvo}" >/dev/null 2>&1; then
        printf 'fedora'
    fi
}

_formato_desta_instalacao() {
    local alvo="${1:-${BASH_SOURCE[0]}}" dono
    if esta_instalacao_e_um_checkout; then
        printf 'checkout'
        return 0
    fi
    local marca_flatpak="${HEFESTO_MARCA_SANDBOX:-/.flatpak-info}"
    if [[ -f "${marca_flatpak}" || -n "${FLATPAK_ID:-}" ]]; then
        printf 'flatpak'
        return 0
    fi
    if [[ "${alvo}" == /nix/store/* ]]; then
        printf 'nix'
        return 0
    fi
    dono="$(_dono_do_arquivo "${alvo}")"
    printf '%s' "${dono:-desconhecido}"
}

_gesto_de_atualizar() {
    case "$(_formato_desta_instalacao "${1:-}")" in
        flatpak) printf 'rode flatpak update' ;;
        arch)    printf 'rode sudo pacman -Syu' ;;
        fedora)  printf 'rode sudo dnf upgrade' ;;
        debian)  printf 'rode sudo apt upgrade' ;;
        nix)     printf 'rode nix profile upgrade' ;;
        *)       printf '%s' "${_CONSELHO_GESTO_GENERICO}" ;;
    esac
}

conselho_de_instalacao() {
    local flags="${1:-}" reparador="${2:-}" ressalva="${3:-}"
    if esta_instalacao_e_um_checkout; then
        printf 'rode ./install.sh%s' "${flags:+ ${flags}}"
    elif [[ -n "${reparador}" && -f "${reparador}" ]]; then
        printf 'rode o reparador que veio no seu pacote: sudo %s%s' \
            "${reparador}" "${ressalva:+ ${ressalva}}"
    else
        printf '%s' "$(_gesto_de_atualizar)"
    fi
}

so_no_checkout() {
    esta_instalacao_e_um_checkout || return 0
    printf ' %s' "${1:-}"
}

runtime_socket() {
    printf '%s/%s/%s.sock' "${XDG_RUNTIME_DIR:-/run/user/$(id -u)}" "${APP_ID}" "${APP_ID}"
}

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
        fail "CLI hefesto-dualsense4unix não encontrado — $(conselho_de_instalacao --native)"
    fi
}

_python_do_produto() {
    local py
    for py in "${ROOT_DIR}/.venv/bin/python" \
              "${HOME}/.local/share/hefesto-dualsense4unix/venv/bin/python" \
              "/opt/hefesto-dualsense4unix/venv/bin/python"; do
        [[ -x "${py}" ]] && { printf '%s\n' "${py}"; return 0; }
    done
    command -v python3 2>/dev/null
}

check_libhidapi() {
    local py; py="$(_python_do_produto)"
    [[ -z "${py}" ]] && { warn "sem python para conferir a libhidapi"; return; }
    if "${py}" -c "import ctypes,sys
for so in ('libhidapi-hidraw.so.0','libhidapi-libusb.so.0','libhidapi-hidraw.so','libhidapi.so.0'):
    try:
        ctypes.CDLL(so); sys.exit(0)
    except OSError:
        pass
sys.exit(1)" 2>/dev/null; then
        pass "libhidapi presente (o backend do controle consegue abrir aparelho)"
    else
        fail "libhidapi AUSENTE — sem ela o backend não abre NENHUM aparelho (o pydualsense faz dlopen dela; a wheel do pip não traz o .so); a libhidapi entra por default no instalador do Hefesto: $(conselho_de_instalacao)"
    fi
}

check_loader_svg() {
    local py; py="$(_python_do_produto)"
    [[ -z "${py}" ]] && { warn "sem python para conferir o loader SVG"; return; }
    if "${py}" -c "import gi,sys,tempfile,os
gi.require_version('GdkPixbuf','2.0')
from gi.repository import GdkPixbuf
svg = b'<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"8\" height=\"8\"><rect width=\"8\" height=\"8\"/></svg>'
fd, caminho = tempfile.mkstemp(suffix='.svg')
try:
    os.write(fd, svg); os.close(fd)
    pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(caminho, 8, 8, True)
    sys.exit(0 if pb is not None else 1)
except Exception:
    sys.exit(1)
finally:
    os.unlink(caminho)" 2>/dev/null; then
        pass "loader SVG do gdk-pixbuf presente (o ícone da bandeja desenha)"
    else
        fail "loader SVG AUSENTE — o ícone some da barra. Instale o loader do librsvg (Debian: librsvg2-common), ou $(conselho_de_instalacao)"
    fi
}

check_binding_webkit() {
    local py; py="$(_python_do_produto)"
    [[ -z "${py}" ]] && { warn "sem python para conferir o WebKit da interface"; return; }
    if "${py}" -c "import gi
gi.require_version('WebKit2', '4.1')
from gi.repository import WebKit2
WebKit2.get_major_version()" >/dev/null 2>&1; then
        pass "WebKit 4.1 presente (a interface consegue abrir)"
        return
    fi
    local pacote="gir1.2-webkit2-4.1 (Debian/Ubuntu), webkit2gtk4.1 (Fedora) ou webkit2gtk-4.1 (Arch)"
    if command -v apt-get >/dev/null 2>&1; then
        pacote="sudo apt install gir1.2-webkit2-4.1"
    elif command -v dnf >/dev/null 2>&1; then
        pacote="sudo dnf install webkit2gtk4.1"
    elif command -v pacman >/dev/null 2>&1; then
        pacote="sudo pacman -S webkit2gtk-4.1"
    fi
    fail "WebKit 4.1 AUSENTE — o serviço sobe, mas a janela não abre (Namespace WebKit2 not available). Instale: ${pacote}, ou $(conselho_de_instalacao)"
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
        warn "serviço não instalado (autostart é opt-in — $(conselho_de_instalacao --enable-autostart))"
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
    local r found=0 missing=""
    local rules=(73-hefesto-ps5-controller.rules 71-uhid.rules 71-uinput.rules
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
                 84-nintendo-pro-variant.rules
                 85-hefesto-o-cabo-assume.rules)
    local total=${#rules[@]}
    for r in "${rules[@]}"; do
        if [[ -e "/etc/udev/rules.d/${r}" || -e "/usr/lib/udev/rules.d/${r}" ]]; then
            found=$((found + 1))
        else
            missing+=" ${r}"
        fi
    done
    if [[ "${found}" -eq "${total}" ]]; then
        pass "${total} regras udev canônicas presentes (73-hefesto/71-uhid/71-uinput/72-autosuspend/72-uaccess/76/77/78/79/80/81-power/81-host/82/83/84/85)"
    elif [[ "${found}" -eq 0 ]]; then
        fail "nenhuma regra udev instalada — rode: sudo bash scripts/install_udev.sh"
    else
        warn "regras udev incompletas (${found}/${total}) — faltam:${missing} — rode: sudo bash scripts/install_udev.sh"
    fi
    for r in 73-ps5-controller-hotplug.rules 74-ps5-controller-hotplug-bt.rules; do
        if [[ -e "/etc/udev/rules.d/${r}" || -e "/usr/lib/udev/rules.d/${r}" ]]; then
            warn "${r}: regra descontinuada presente (amplificava o storm -71) — remova: sudo bash scripts/install_udev.sh"
        fi
    done
    if { [[ -e /etc/udev/rules.d/82-nintendo-pro-nosniff.rules ]] \
         || [[ -e /usr/lib/udev/rules.d/82-nintendo-pro-nosniff.rules ]]; } \
       && [[ ! -f /usr/local/lib/hefesto-dualsense4unix/bt_nosniff_now.sh ]]; then
        warn "82-nintendo-pro-nosniff.rules instalada e o alvo do RUN+= dela NÃO (/usr/local/lib/hefesto-dualsense4unix/bt_nosniff_now.sh) — a regra fica inerte (o TEST== dela não acha o alvo) e o Pro genuíno não perde o sniff na borda da conexão; traga o alvo: $(conselho_de_instalacao "" "/usr/share/hefesto-dualsense4unix/scripts/install-host-udev.sh")"
    fi
    if { [[ -e /etc/udev/rules.d/83-hefesto-bond-snapshot.rules ]] \
         || [[ -e /usr/lib/udev/rules.d/83-hefesto-bond-snapshot.rules ]]; } \
       && [[ ! -f /usr/local/lib/hefesto-dualsense4unix/bt_bonds_snapshot.sh ]]; then
        warn "83-hefesto-bond-snapshot.rules instalada e o alvo do RUN+= dela NÃO (/usr/local/lib/hefesto-dualsense4unix/bt_bonds_snapshot.sh, o ExecStart da unit de snapshot) — a regra fica inerte e o salva-vidas de bonds não grava nada quando um controle Bluetooth chega; traga o alvo: $(conselho_de_instalacao "" "/usr/share/hefesto-dualsense4unix/scripts/install-host-udev.sh")"
    fi
}

_DIRS_DE_REGRAS_UDEV=(/etc/udev/rules.d /run/udev/rules.d /usr/local/lib/udev/rules.d
                      /usr/lib/udev/rules.d /lib/udev/rules.d)

readonly REGRA_DO_NO="73-hefesto-ps5-controller.rules"
readonly REGRA_DO_NO_VELHA="70-ps5-controller.rules"

_regras_udev_em_ordem() {
    local dirs=("$@") d f base
    [[ ${#dirs[@]} -gt 0 ]] || dirs=("${_DIRS_DE_REGRAS_UDEV[@]}")
    local -A visto=()
    for d in "${dirs[@]}"; do
        [[ -d "${d}" ]] || continue
        for f in "${d}"/*.rules; do
            [[ -e "${f}" || -L "${f}" ]] || continue
            base="${f##*/}"
            [[ -n "${visto[${base}]:-}" ]] && continue
            visto[${base}]=1
            [[ -f "${f}" ]] || continue
            printf '%s\t%s\n' "${base}" "${f}"
        done
    done | LC_ALL=C sort -t $'\t' -k1,1
}

_caminho_da_regra_do_no() {
    local nome caminho achou=""
    while IFS=$'\t' read -r nome caminho; do
        [[ "${nome}" == "${REGRA_DO_NO}" ]] && { printf '%s\n' "${caminho}"; return 0; }
        [[ "${nome}" == "${REGRA_DO_NO_VELHA}" ]] && achou="${caminho}"
    done < <(_regras_udev_em_ordem "$@")
    [[ -n "${achou}" ]] && printf '%s\n' "${achou}"
    return 0
}

_regra_do_no_instalada() {
    local caminho
    caminho="$(_caminho_da_regra_do_no "$@")"
    [[ -n "${caminho}" ]] && printf '%s\n' "${caminho##*/}"
    return 0
}

_regra_do_no_e_a_aberta() {
    local caminho="$1" efetivas
    [[ -r "${caminho}" ]] || return 1
    efetivas="$(grep -v '^[[:space:]]*#' "${caminho}" 2>/dev/null || true)"
    [[ "${efetivas}" != *'TAG-="uaccess"'* ]]
}

_regras_que_reabrem_o_fisico() {
    local nossa="$1"; shift
    local nome caminho quando depois=0
    while IFS=$'\t' read -r nome caminho; do
        if [[ "${depois}" -eq 0 ]]; then
            [[ "${nome}" == "${nossa}" ]] && depois=1
            continue
        fi
        [[ -r "${caminho}" ]] || continue
        quando="nascimento"
        [[ "$(printf '%s\n%s\n' "${nome}" "73-seat-late.rules" | LC_ALL=C sort | head -1)" \
            == "73-seat-late.rules" ]] && quando="login"
        awk -v arq="${caminho}" -v quando="${quando}" '
            {
                linha = $0
                sub(/^[[:space:]]+/, "", linha)
                sub(/[[:space:]]+$/, "", linha)
            }
            linha == "" || linha ~ /^#/ { next }
            {
                # Concede: `TAG+="uaccess"` (ou `TAG=`), ou o builtin chamado
                # por RUN. O `TAG-=` e o `TAG==` (casamento) não concedem.
                concede = (linha ~ /TAG[[:space:]]*\+?=[[:space:]]*"uaccess"/ || linha ~ /RUN[^,]*uaccess/)
                if (!concede) next
                # Alcança o hidraw: cita hidraw, ou não restringe KERNEL nem
                # SUBSYSTEM (casa todo filho do aparelho, o hidraw junto).
                hid = (linha ~ /hidraw/)
                sem_alvo = (linha !~ /(^|[ ,])KERNEL[[:space:]]*[!=]=/ \
                            && linha !~ /(^|[ ,])SUBSYSTEM[[:space:]]*[!=]=/)
                if (!hid && !sem_alvo) next
                u = toupper(linha)
                dualsense = (u ~ /054C/ && (u ~ /0CE6/ || u ~ /0DF2/))
                # Estreita: qualquer condição sobre o aparelho (atributo, pai,
                # propriedade). Só a linha SEM nenhuma é a que abre todo hidraw.
                estreita = (linha ~ /ATTRS?\{/ || linha ~ /(KERNELS|SUBSYSTEMS|DRIVERS)[[:space:]]*[!=]=/ \
                            || linha ~ /ENV\{[^}]*\}[[:space:]]*[!=]=/)
                if (dualsense || (hid && !estreita)) print arq ":" FNR ":" quando ":" linha
            }
        ' "${caminho}" 2>/dev/null
    done < <(_regras_udev_em_ordem "$@")
}

_tags_correntes_do_no() {
    local consulta="$1" no="$2" props v_udev campo="CURRENT_TAGS"
    props="$("${consulta}" info --query=property --name="${no}" 2>/dev/null)" || return 1
    [[ -n "${props}" ]] || return 1
    v_udev="$("${consulta}" --version 2>/dev/null | sed -n '1s/^[^0-9]*\([0-9][0-9]*\).*/\1/p')"
    if [[ "${v_udev}" =~ ^[0-9]+$ && "${v_udev}" -lt 247 ]]; then
        campo="TAGS"
    fi
    sed -n "s/^${campo}=//p" <<<"${props}" | tr ':' '\n' | sed '/^$/d'
    return 0
}

_veredito_do_no_fisico_no_udev() {
    local consulta="$1" sysroot="$2" censo="$3"
    shift 3
    local nossa no base bus prod transp tags abertos=() sem_seat=0 total=0
    nossa="$(_regra_do_no_instalada "$@")"
    if [[ -z "${censo}" ]]; then
        info "nenhum DualSense físico no censo agora — o efeito da regra do nó se confere com um controle conectado"
        return 0
    fi
    if ! command -v "${consulta}" >/dev/null 2>&1; then
        info "sem o programa que pergunta ao udev — não dá para conferir como os DualSense físicos nasceram"
        return 0
    fi
    for no in ${censo}; do
        base="${no##*/}"
        [[ -d "${sysroot}/${base}" ]] || continue
        tags="$(_tags_correntes_do_no "${consulta}" "${no}")" || continue
        total=$((total + 1))
        grep -qx 'uaccess' <<<"${tags}" || continue
        bus="$(sed -n 's/^HID_ID=\([0-9A-Fa-f]*\):.*/\1/p' "${sysroot}/${base}/device/uevent" 2>/dev/null)"
        prod="$(sed -n 's/^HID_ID=.*:0*\([0-9A-Fa-f]*\)$/\1/p' "${sysroot}/${base}/device/uevent" 2>/dev/null)"
        case "${bus}" in
            *5) transp="rádio" ;;
            *3) transp="cabo" ;;
            *)  transp="?" ;;
        esac
        [[ "${prod^^}" == "DF2" || "${prod^^}" == "0DF2" ]] && transp="${transp}, Edge"
        abertos+=("${base} (${transp})")
        grep -qx 'seat' <<<"${tags}" || sem_seat=1
    done
    if [[ "${total}" -eq 0 ]]; then
        info "o udev não respondeu sobre os DualSense físicos — não dá para conferir como eles nasceram"
        return 0
    fi
    if [[ ${#abertos[@]} -eq 0 ]]; then
        pass "o hidraw dos ${total} DualSense físico(s) nasceu sem a ACL da sessão — a regra do nó (${nossa:-?}) falou por último"
        return 0
    fi
    local caminho_nossa
    caminho_nossa="$(_caminho_da_regra_do_no "$@")"
    if [[ -n "${caminho_nossa}" ]] && _regra_do_no_e_a_aberta "${caminho_nossa}"; then
        info "${#abertos[@]} de ${total} DualSense físico(s) nasceram com a ACL da sessão, e é o combinado: a regra do nó instalada (${caminho_nossa}) é a variante aberta (--no-fechar-o-no, ou o pacote sem o broker)"
        return 0
    fi
    fail "${#abertos[@]} de ${total} DualSense físico(s) nasceram com a ACL da sessão: ${abertos[*]} — qualquer programa da sessão (a Steam, por exemplo) abre o nó antes de o Hefesto escondê-lo, e esconder depois não fecha o que ele abriu"
    if [[ -z "${nossa}" ]]; then
        info "  a regra do nó do Hefesto não está instalada; $(conselho_de_instalacao)"
        return 0
    fi
    if [[ "${nossa}" == "${REGRA_DO_NO_VELHA}" ]]; then
        info "  a regra do nó instalada é a de antes (${REGRA_DO_NO_VELHA}), que as regras 71-* de terceiro desfazem; a de hoje é a ${REGRA_DO_NO} — $(conselho_de_instalacao)"
    fi
    local culpados linha
    culpados="$(_regras_que_reabrem_o_fisico "${nossa}" "$@")"
    if [[ -n "${culpados}" ]]; then
        info "  quem devolve o uaccess DEPOIS da regra do Hefesto (nenhum destes arquivos é do Hefesto):"
        while IFS= read -r linha; do
            [[ -n "${linha}" ]] || continue
            case "${linha}" in
                *:login:*)  info "    ${linha%%:login:*} — depois da 73-seat-late: reabre na troca de sessão (login)" ;;
                *)          info "    ${linha%%:nascimento:*}" ;;
            esac
        done <<<"${culpados}"
    elif [[ "${sem_seat}" -eq 1 ]]; then
        info "  o banco tem uaccess sem seat — a assinatura de uma regra entre a 71-seat e a 73-seat-late que esta leitura não reconheceu (ENV, GOTO ou programa)"
    else
        info "  nenhuma regra lida explica — o nó pode ter nascido antes da regra atual: reconecte o controle"
    fi
    info "  o controle que já nasceu assim só se solta reconectando (o descritor que outro programa abriu não fecha com chmod)"
}

check_o_no_fisico_nasce_sem_acl() {
    if [[ -e "/etc/udev/rules.d/${REGRA_DO_NO}" && -e "/etc/udev/rules.d/${REGRA_DO_NO_VELHA}" ]]; then
        warn "sobrou a regra do nó com o nome de antes (/etc/udev/rules.d/${REGRA_DO_NO_VELHA}) ao lado da de hoje — $(conselho_de_instalacao)"
    fi
    _veredito_do_no_fisico_no_udev "udevadm" /sys/class/hidraw "$(_censo_de_fisicos)"
}

dualsense_audio_bound() {
    local iface base vid cls drv
    for iface in /sys/bus/usb/devices/*:*.*; do
        [[ -r "${iface}/bInterfaceClass" ]] || continue
        cls="$(cat "${iface}/bInterfaceClass" 2>/dev/null)"
        [[ "${cls}" == "01" ]] || continue
        base="${iface%:*}"
        vid="$(cat "${base}/idVendor" 2>/dev/null)"
        [[ "${vid}" == "054c" ]] || continue
        drv="$(basename "$(readlink -f "${iface}/driver" 2>/dev/null)" 2>/dev/null)"
        [[ "${drv}" == "snd-usb-audio" ]] && return 0
    done
    return 1
}

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

    [[ -z "${rule75}" ]] && return

    if [[ "${mic_intended}" -eq 1 ]]; then
        info "regra 75 (áudio USB off) instalada, mas DUALSENSE_MIC_INTENDED=1 pede o mic — contraditório; para ter o mic remova a 75 (uninstall) ou reinstale sem --disable-usb-audio"
        return
    fi

    if dualsense_audio_bound; then
        warn "regra 75 instalada mas snd-usb-audio ainda bindado no áudio do DualSense — a regra não pegou; replugue o controle (ou: sudo bash scripts/install_udev.sh --disable-usb-audio)"
    elif command -v lsusb >/dev/null 2>&1 && lsusb 2>/dev/null | grep -qiE '054c'; then
        pass "regra 75 ativa — áudio USB do DualSense desligado (sem snd-usb-audio nas interfaces de áudio)"
    else
        info "regra 75 instalada; DualSense não conectado via USB agora — replugue para validar o desligamento do áudio"
    fi
}

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

_vpad09_qualifica_acesso() {
    local node="$1" para_que="$2" grp
    grp="$(stat -c '%G' "${node}" 2>/dev/null || true)"
    if [[ "${grp}" != "hefesto" ]]; then
        warn "${node} gravável só pela ACL do login — no boot o daemon pode perder a corrida contra o logind. Rode: sudo bash scripts/install_udev.sh"
    elif id -nG 2>/dev/null | tr ' ' '\n' | grep -qx hefesto; then
        pass "${node} presente e gravável (${para_que}; grupo hefesto ativo — sem corrida no boot)"
    else
        info "${node} com grupo hefesto, mas sua sessão ainda não está no grupo (vale no próximo login) — até lá o acesso é a ACL do login"
    fi
}

check_uinput() {
    _check_node_gravavel /dev/uinput uinput "gamepad virtual"
}

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

check_uhid_contrapressao() {
    local conf="${HEFESTO_DOCTOR_UHID_CONF:-/etc/modprobe.d/hefesto-uhid.conf}"
    local param="${HEFESTO_DOCTOR_UHID_PARAM:-/sys/module/uhid/parameters/backpressure}"
    local baseline="${ROOT_DIR}/assets/dkms/uhid/patch/BASELINE"
    local kernel="${HEFESTO_DOCTOR_KERNEL:-$(uname -r)}" validados="" um valor
    [[ -f "${conf}" ]] || return 0
    if [[ -r "${param}" ]]; then
        valor="$(cat "${param}" 2>/dev/null || true)"
        if [[ "${valor}" == "1" || "${valor}" == "Y" ]]; then
            pass "contrapressão do uhid ligada (o rádio cheio diz «espere» em vez de perder o comando)"
        else
            warn "a contrapressão do uhid foi pedida e está DESLIGADA agora (${valor:-?}) — ligue sem recarregar o uhid: echo 1 | sudo tee ${param}"
        fi
        return
    fi
    if [[ -r "${baseline}" ]]; then
        validados="$(sed -n 's/^KERNELS_VALIDADOS=//p' "${baseline}" | head -1 | tr ',' ' ')"
        for um in ${validados}; do
            if [[ "${kernel}" == "${um}" || "${kernel}" == "${um}"-* ]]; then
                info "a contrapressão do uhid foi pedida e entra no PRÓXIMO BOOT (o uhid de fábrica está carregado; recarregá-lo derrubaria todo HID por Bluetooth)"
                return
            fi
        done
        warn "a contrapressão do uhid foi pedida, mas o kernel ${kernel} não está entre os conferidos (${validados:-nenhum}) — o uhid de fábrica segue, e o pedido não vale neste kernel"
        return
    fi
    info "a contrapressão do uhid foi pedida e o uhid carregado é o de fábrica — não sei dizer se o patchado entra no próximo boot (sem o patch/BASELINE nesta instalação)"
}

check_hid_playstation() {
    if lsmod 2>/dev/null | grep -q '^hid_playstation'; then
        pass "driver hid_playstation carregado (cor da luz e LED de jogador)"
    elif [[ -d /sys/module/hid_playstation ]]; then
        pass "driver hid_playstation ativo (embutido no kernel)"
    else
        warn "driver hid_playstation não carregado — cor da luz e LED de jogador podem não funcionar. Kernel muito antigo? Rode: sudo modprobe hid_playstation"
    fi
}

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

_hid_playstation_orfaos_agora() {
    local raiz="${HEFESTO_HID_DEVICES_DIR:-/sys/bus/hid/devices}" dev id bus vid
    for dev in "${raiz}"/*; do
        [[ -d "${dev}" ]] || continue
        [[ -e "${dev}/driver" ]] && continue
        id="$(basename "${dev}")"
        bus="${id%%:*}"
        vid="${id#*:}"; vid="${vid%%:*}"
        [[ "${bus}" == "0005" ]] || continue
        [[ "${vid^^}" == "054C" ]] || continue
        printf '%s\n' "${id}"
    done
}

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
        info "não é hardware (tese vetada por ela, por escrito, depois de dias perdidos nela): é contenção — dois DualSense subindo no mesmo adaptador com ~1 s de diferença; o segundo perde o canal de controle L2CAP e o BlueZ desiste no teto de 3 s (hidp_report_req_timeout). Cadeia medida: assets/dkms/hid-playstation/README.md:65-117"
        return
    fi

    if [[ -n "${abortos}" ]]; then
        local total_probe total_feature instancias
        total_probe="$(printf '%s\n' "${abortos}" | awk '{s += $2} END {printf "%d", s + 0}')"
        total_feature="$(printf '%s\n' "${abortos}" | awk '{s += $3} END {printf "%d", s + 0}')"
        instancias="$(printf '%s\n' "${abortos}" | awk '{printf "%s%s", (NR > 1 ? ", " : ""), $1}')"
        info "aborto de probe do hid-playstation na janela (${janela}), JÁ RECUPERADO: ${total_probe}x 'probe with driver playstation failed' em ${instancias} (${total_feature}x 'Failed to retrieve feature' antes) — nenhum DualSense está órfão AGORA, então não há o que fazer: é histórico, não defeito ativo (os 6 abortos de 08/08 voltaram sozinhos em 2 a 20 min, por reconexão)"
        info "se acontecer de novo COM o controle sumindo, o Hefesto o religa sozinho na hora do aviso do kernel (o kernel-watch chama o rebind pela ponte privilegiada), e a vigia hefesto-bt-health-watchdog.timer é a rede, de 2 em 2 minutos; à mão: sudo /usr/local/lib/hefesto-dualsense4unix/bt_rebind_orphans.sh; a causa medida é contenção de dois controles no mesmo adaptador, não hardware (assets/dkms/hid-playstation/README.md:65-117)"
        return
    fi

    if [[ "${tem_journal}" -eq 0 ]]; then
        info "nenhum DualSense órfão agora (todo device HID Sony por Bluetooth tem driver) — sem journalctl não dá para olhar o histórico de abortos de probe"
        return
    fi
    pass "nenhum DualSense órfão agora e nenhum aborto de probe do hid-playstation na janela (${janela})"
}

check_led_sysfs_gravavel() {
    local node dev_real nome phys ok_nodes="" bad_nodes=""
    for node in /sys/class/leds/*rgb:indicator*; do
        [[ -e "${node}" ]] || continue
        dev_real="$(readlink -f "${node}/device" 2>/dev/null || true)"
        [[ -z "${dev_real}" ]] && dev_real="$(dirname "$(dirname "$(readlink -f "${node}" 2>/dev/null || echo /)")")"
        phys="$(sed -n 's/^HID_PHYS=//p' "${dev_real}/uevent" 2>/dev/null || true)"
        [[ "${phys}" == hefesto-vpad* ]] && continue
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

check_input_uaccess() {
    local regra="72-hefesto-touchpad-motion-uaccess.rules"
    if [[ ! -e "/etc/udev/rules.d/${regra}" && ! -e "/usr/lib/udev/rules.d/${regra}" ]]; then
        fail "${regra} ausente — o touchpad e o giroscópio só funcionam para quem está no grupo 'input' por fora do produto (numa máquina nova, não funcionam). Rode: sudo bash scripts/install_udev.sh"
        return
    fi
    local node base nome vid pid uniq dev_real eu classe
    local vistos_fis=0 vistos_virt=0
    local sem_acesso=() so_pelo_grupo=() sem_acesso_virt=() so_grupo_virt=()
    local sock_do_broker="/run/hefesto-hidraw-broker/broker.sock"
    local fechados_pelo_hefesto=() nasceu_aberto=() devolvidos_ao_nativo=()
    local do_nativo=" "
    if [[ -e "${sock_do_broker}" ]]; then
        do_nativo=" $(_entradas_devolvidas_pelo_nativo "${sock_do_broker}" | tr '\n' ' ') "
    fi
    eu="$(id -un 2>/dev/null || true)"
    for node in /dev/input/event*; do
        [[ -e "${node}" ]] || continue
        base="$(basename "${node}")"
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
        uniq="$(cat "/sys/class/input/${base}/device/uniq" 2>/dev/null || true)"
        if [[ ( "${dev_real}" == */devices/virtual/* \
                && ( "${dev_real}" != */misc/uhid/* || -z "${uniq}" || "${uniq,,}" == 02:fe:* ) ) \
              || ( "${dev_real}" == */vhci_hcd.*/* && "${uniq,,}" == 02:fe:* ) ]]; then
            classe="virt"
            vistos_virt=$((vistos_virt + 1))
        else
            classe="fis"
            vistos_fis=$((vistos_fis + 1))
        fi
        pid="$(cat "/sys/class/input/${base}/device/id/product" 2>/dev/null || true)"
        if [[ "${classe}" == "fis" && "${vid}" == "054c" \
              && ( "${pid}" == "0ce6" || "${pid}" == "0df2" ) && -e "${sock_do_broker}" ]]; then
            if [[ -r "${node}" && "${do_nativo}" == *" ${base} "* ]]; then
                devolvidos_ao_nativo+=("${base}")
            elif [[ -r "${node}" ]]; then
                nasceu_aberto+=("${base}")
            else
                fechados_pelo_hefesto+=("${base}")
            fi
            continue
        fi
        if [[ ! -r "${node}" ]]; then
            [[ "${classe}" == "fis" ]] && sem_acesso+=("${base}") || sem_acesso_virt+=("${base}")
        elif command -v getfacl >/dev/null 2>&1 && [[ -n "${eu}" ]] \
             && ! getfacl -p "${node}" 2>/dev/null | grep -q "^user:${eu}:"; then
            [[ "${classe}" == "fis" ]] && so_pelo_grupo+=("${base}") || so_grupo_virt+=("${base}")
        fi
    done
    if [[ "${#sem_acesso_virt[@]}" -gt 0 ]]; then
        local espera="${HEFESTO_DOCTOR_ESPERA_DO_VPAD:-5}" ainda=() b s
        command -v udevadm >/dev/null 2>&1 && udevadm settle --timeout="${espera}" >/dev/null 2>&1
        for b in "${sem_acesso_virt[@]}"; do
            s=0
            while [[ ! -r "/dev/input/${b}" && "${s}" -lt "${espera}" ]]; do
                sleep 1
                s=$((s + 1))
            done
            [[ -r "/dev/input/${b}" ]] || ainda+=("${b}")
        done
        sem_acesso_virt=("${ainda[@]}")
    fi
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
    if [[ "${#nasceu_aberto[@]}" -gt 0 ]]; then
        warn "o broker está de pé e ${#nasceu_aberto[@]} nó(s) de touchpad/movimento do controle FÍSICO seguem abertos (${nasceu_aberto[*]}) — quem enumera /dev/input acha o controle dobrado. Nasceram antes do broker, ou o broker em memória é o de antes da cura: reconecte o controle; se persistir, veja o check do broker em memória"
        return
    fi
    if [[ "${#devolvidos_ao_nativo[@]}" -gt 0 ]]; then
        pass "touchpad e giroscópio do controle físico devolvidos ao jogo pelo Modo Nativo em ${#devolvidos_ao_nativo[@]} nó(s) (${devolvidos_ao_nativo[*]}) — só o Nativo os abre"
    fi
    local cobertos=$(( ${#fechados_pelo_hefesto[@]} + ${#devolvidos_ao_nativo[@]} ))
    if [[ "${#fechados_pelo_hefesto[@]}" -gt 0 && "${cobertos}" -eq "${vistos_fis}" ]]; then
        pass "touchpad e giroscópio do controle físico fechados para todos menos o Hefesto em ${#fechados_pelo_hefesto[@]} nó(s) (${fechados_pelo_hefesto[*]}) — o daemon os lê pelo broker"
        return
    fi
    [[ "${cobertos}" -eq "${vistos_fis}" ]] && return
    local vistos_com_acl=$((vistos_fis - cobertos))
    if [[ "${#sem_acesso[@]}" -gt 0 ]]; then
        fail "sem permissão de leitura em ${#sem_acesso[@]} de ${vistos_com_acl} nó(s) FÍSICOS de touchpad/movimento (${sem_acesso[*]}) — o daemon engole o EACCES e relata 'sem sensor'. A ACL nasce no (re)add do device: desconecte e reconecte o controle; se persistir, rode: sudo bash scripts/install_udev.sh"
        return
    fi
    if [[ "${#so_pelo_grupo[@]}" -gt 0 ]]; then
        warn "${#so_pelo_grupo[@]} de ${vistos_com_acl} nó(s) FÍSICOS de touchpad/movimento legíveis só pelo GRUPO do nó (${so_pelo_grupo[*]}), sem a ACL da sessão — funciona NESTA máquina (você está no grupo 'input') e NÃO funcionaria numa limpa. Reconecte o controle para a ${regra} pegar."
        return
    fi
    pass "touchpad e giroscópio com ACL da sessão em ${vistos_com_acl} nó(s) do controle físico — sem depender do grupo 'input'"
}

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
        info "quirk de áudio USB ausente — o install o põe por default (passo 3e, cmdline gerenciado); à mão: scripts/install_usb_quirk.sh. É a alavanca que PRESERVA o áudio (a regra 75 é a que o desliga): use uma OU outra."
    fi
    if [[ "${active}" -eq 1 || "${scheduled}" -eq 1 || "${runtime}" -eq 1 ]]; then
        info "  caveat: o quirk preserva o áudio no nível do KERNEL (sem storm); com os WP 52/53 o nó segue suprimido no PipeWire até removê-los ou definir DUALSENSE_MIC_INTENDED=1"
    fi
}

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

check_bandeja() {
    local autostart="${HOME}/.config/autostart/hefesto-dualsense4unix-tray.desktop"
    if [[ -r "${autostart}" ]]; then
        local exec_do_autostart
        exec_do_autostart="$(sed -n 's/^Exec=//p' "${autostart}" | head -1)"
        if [[ "${exec_do_autostart}" == *--tray* ]]; then
            pass "autostart do tray instalado (${exec_do_autostart})"
        else
            fail "o autostart existe mas não pede o tray (Exec=${exec_do_autostart}) — reinstale"
        fi
    else
        warn "autostart do tray ausente — o ícone não sobe no login. Para instalar: $(conselho_de_instalacao)"
    fi

    local dono_do_watcher=""
    if command -v busctl >/dev/null 2>&1; then
        dono_do_watcher="$(busctl --user status org.kde.StatusNotifierWatcher 2>/dev/null \
            | sed -n 's/^Comm=//p' | head -1)"
    fi
    if [[ -n "${dono_do_watcher}" ]]; then
        pass "hospedeiro da bandeja de pé (org.kde.StatusNotifierWatcher: ${dono_do_watcher})"
    else
        warn "nenhum org.kde.StatusNotifierWatcher no barramento — o ícone do tray não tem onde aparecer. No COSMIC, acrescente «Área de status» em Config. > Paineis > Miniaplicativos"
    fi

    if pgrep -f 'cli.app tray|hefesto-dualsense4unix tray' >/dev/null 2>&1; then
        pass "tray de pé"
    else
        info "tray não está rodando — ele sobe no próximo login, ou agora com: ./run.sh --tray"
    fi

    if [[ -e "${APPLET_DESKTOP}" || -e "/usr/local/bin/hefesto-dualsense4unix-applet" ]]; then
        info "há um applet COSMIC instalado de antes — ele foi APOSENTADO em 19/09/2026 e o tray o substitui. Para removê-lo sem tocar em mais nada: ./uninstall.sh --so-o-applet"
    fi
}


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
    if [[ "${cur}" == *[Mm]onitor* ]]; then
        info "a fonte padrão é um MONITOR (${cur}) — não é o mic do DualSense; veredito em 'fonte de captura padrão'"
        return
    fi
    if [[ ! "${cur}" =~ [Dd]ual[Ss]ense ]]; then
        pass "microfone ativo não é o mic do DualSense (${cur})"
        return
    fi
    case "${HEFESTO_DUALSENSE4UNIX_DUALSENSE_MIC_INTENDED:-}" in
        1|true|yes|TRUE|YES)
            pass "microfone ativo é o DualSense (DUALSENSE_MIC_INTENDED=1 — desejado)"
            return ;;
    esac
    if [[ -f "$(_wp_dropin 51-hefesto-dualsense-no-default-source.conf)" ]]; then
        pass "microfone ativo é o DualSense (o promotor está instalado — foi pedido)"
        return
    fi
    if [[ -f "$(_marca_do_gesto_do_mic)" ]]; then
        pass "microfone ativo é o DualSense (foi pedido — marca do gesto em $(_marca_do_gesto_do_mic))"
        return
    fi
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

_marca_do_gesto_do_mic() {
    printf '%s/hefesto-dualsense4unix/mic-do-dualsense-pedido.conf\n' \
        "${XDG_STATE_HOME:-${HOME}/.local/state}"
}

_prefere_mic_do_dualsense() {
    [[ -f "$(_wp_dropin 52-hefesto-dualsense-disable-source.conf)" ]] && return 1
    case "${HEFESTO_DUALSENSE4UNIX_DUALSENSE_MIC_INTENDED:-}" in
        1|true|yes|TRUE|YES) return 0 ;;
    esac
    [[ -f "$(_wp_dropin 51-hefesto-dualsense-no-default-source.conf)" ]] && return 1
    [[ -f "$(_marca_do_gesto_do_mic)" ]] && return 0
    return 1
}

_source_porta_ativa_indisponivel() {
    python3 -c '
import json, sys
alvo, arquivo = sys.argv[1], sys.argv[2]
try:
    dados = json.load(sys.stdin if arquivo == "-" else open(arquivo, encoding="utf-8"))
except (OSError, ValueError):
    sys.exit(1)
for no in dados:
    if no.get("name") != alvo:
        continue
    ativa = no.get("active_port")
    for porta in no.get("ports") or []:
        if porta.get("name") == ativa:
            sys.exit(0 if porta.get("availability") == "not available" else 1)
sys.exit(1)
' "$1" "${2:--}"
}

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

_pactl_json() {
    LC_ALL=C pactl --format=json list "$1" 2>/dev/null || true
}

_wp_forma() {
    local raiz sistema="${HEFESTO_WIREPLUMBER_SISTEMA:-/usr/share/wireplumber:/etc/wireplumber}"
    local IFS=:
    for raiz in ${sistema}; do
        [[ -n "${raiz}" ]] || continue
        [[ -d "${raiz}/main.lua.d" ]] && { printf 'lua'; return 0; }
        [[ -f "${raiz}/wireplumber.conf" || -d "${raiz}/wireplumber.conf.d" ]] \
            && { printf 'conf'; return 0; }
    done
    printf 'conf'
}
_wp_dropin_dir() {
    if [[ "$(_wp_forma)" == "lua" ]]; then
        printf '%s' "${HOME}/.config/wireplumber/main.lua.d"
    else
        printf '%s' "${HOME}/.config/wireplumber/wireplumber.conf.d"
    fi
}
_wp_dropin() {
    local nome="${1%.conf}" ext=conf
    [[ "$(_wp_forma)" == "lua" ]] && ext=lua
    printf '%s/%s.%s' "$(_wp_dropin_dir)" "${nome}" "${ext}"
}
_wireplumber_leu_a_regra() {
    local prop="$1" valor="$2" prefixo="$3" id texto achou_no=0
    command -v wpctl >/dev/null 2>&1 || return 2
    local ids
    ids="$(timeout 5 wpctl status 2>/dev/null | grep -i dualsense | grep -oE '[0-9]+\.' | tr -d '.' | sort -un)" || ids=""
    [[ -n "${ids}" ]] || return 2
    for id in ${ids}; do
        texto="$(timeout 5 wpctl inspect "${id}" 2>/dev/null)" || continue
        grep -qiE "node\.name = \"${prefixo}[^\"]*dualsense" <<<"${texto}" || continue
        achou_no=1
        grep -qE "${prop//./\\.}[[:space:]]*=[[:space:]]*\"?${valor}\"?[[:space:]]*$" <<<"${texto}" && return 0
    done
    [[ "${achou_no}" -eq 1 ]] && return 1
    return 2
}

_dualsense_por_falta_com_o_51() { [[ "${2:-0}" -eq 0 && "${1,,}" == *dualsense* && -f "$(_wp_dropin 51-hefesto-dualsense-no-default-source.conf)" ]]; }

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
        local sources_txt
        sources_txt="$(_pactl_json sources)"
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
    local prefere=0 alvo longo
    _prefere_mic_do_dualsense && prefere=1
    longo="$(_pactl_json sources)"
    alvo="$(LC_ALL=C pactl list sources short 2>/dev/null \
            | _sources_com_porta_usavel "${longo}" \
            | _melhor_source_de_captura "${prefere}")"
    if [[ -n "${alvo}" ]] && _dualsense_por_falta_com_o_51 "${alvo}" "${prefere}"; then
        fail "a fonte de captura padrão é um MONITOR (${cur}) — o que qualquer app gravar é o áudio de SAÍDA, não a voz; a entrada do DualSense está no ar e o drop-in 51 a põe acima de qualquer monitor, então o WirePlumber ainda não a elegeu (o --fix-mic NÃO grava essa escolha, que venceria a próxima webcam plugada; se o monitor continuar, o 51 pode não ter sido lido nesta sessão do WirePlumber, que só o lê ao iniciar)"
    elif [[ -n "${alvo}" ]]; then
        fail "a fonte de captura padrão é um MONITOR (${cur}) — o que qualquer app gravar é o áudio de SAÍDA, não a voz; rode: scripts/doctor.sh --fix-mic"
        info "  cura: pactl set-default-source ${alvo}"
    else
        fail "a fonte de captura padrão é um MONITOR (${cur}) — o que qualquer app gravar é o áudio de SAÍDA do sistema, não a voz, e o medidor de nível ainda mostra sinal (parece funcionando)"
        info "  o --fix-mic NÃO resolve este caso: ele só sabe ELEGER outra fonte de captura, e não há nenhuma com porta usável nesta máquina agora"
        info "  o que resolve é hardware: conecte um mic, uma webcam com mic, ou o DualSense (no cabo, ou por Bluetooth com o mic ligado)"
    fi
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

fix_default_source_monitor() {
    command -v pactl >/dev/null 2>&1 || return 0
    local cur
    cur="$(pactl get-default-source 2>/dev/null || true)"
    [[ "$(_default_source_classe "${cur}")" == "monitor" ]] || return 0
    local prefere=0 alvo
    _prefere_mic_do_dualsense && prefere=1

    local lista_curta lista_completa _linha _nome
    lista_completa="$(_pactl_json sources)"
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
        warn "a fonte padrão é um MONITOR (${cur}) e não há nenhuma fonte de captura com porta usável para eleger"
        info "  enquanto isso durar, TUDO o que qualquer aplicativo gravar é o áudio de SAÍDA do sistema, não a voz"
        info "  esta cura só sabe eleger outra fonte de captura — sem nenhuma, o que resolve é conectar um mic, uma webcam com mic, ou o DualSense"
        return 0
    fi
    _dualsense_por_falta_com_o_51 "${alvo}" "${prefere}" && { info "  não gravo ${alvo} como fonte padrão: com o drop-in 51 o WirePlumber a elege sozinho acima de qualquer monitor, e gravada ela venceria a próxima webcam plugada"; return 0; }
    if pactl set-default-source "${alvo}" 2>/dev/null; then
        pass "fonte padrão trocada do monitor para a entrada ${alvo}"
    else
        warn "falha ao eleger ${alvo} como fonte padrão (a padrão segue o monitor ${cur})"
    fi
}

check_dropin_do_mic_armado() {
    local marca; marca="$(_marca_do_gesto_do_mic)"
    if [[ -f "$(_wp_dropin 52-hefesto-dualsense-disable-source.conf)" ]]; then
        info "microfone do DualSense desligado de propósito (drop-in 52) — não há política de eleição a armar"
        return
    fi
    if [[ -f "$(_wp_dropin 51-hefesto-dualsense-no-default-source.conf)" ]]; then
        local leu=0; _wireplumber_leu_a_regra priority.session 1500 alsa_input || leu=$?
        if [[ "${leu}" -eq 1 ]]; then
            warn "o drop-in 51 está em $(_wp_dropin_dir), mas o WirePlumber não leu a regra (o nó de captura do controle está sem priority.session = 1500) — o controle pode virar o microfone padrão sozinho: $(conselho_de_instalacao)$(so_no_checkout "(só ele: bash scripts/fix_wireplumber_default_source.sh --install)")"
            return
        fi
        pass "a política de microfone do install está armada (drop-in 51 no lugar)"
        return
    fi
    if _prefere_mic_do_dualsense; then
        local quando=""
        [[ -r "${marca}" ]] && quando="$(sed -n 's/^data=//p' "${marca}" | head -n1)"
        if [[ -n "${quando}" ]]; then
            pass "o mic do DualSense é escolha dela, de ${quando} (marca do gesto em ${marca})"
        else
            pass "o mic do DualSense é escolha dela (sinal explícito: DUALSENSE_MIC_INTENDED)"
        fi
        return
    fi
    warn "a política de microfone do install NÃO está armada e ninguém pediu para promover o controle — sem o drop-in 51 o WirePlumber pode eleger o mic do DualSense sozinho, e o que os aplicativos gravam vira o eco da saída em vez da voz"
    info "  se foi um uninstall que a desarmou, rearme: bash scripts/fix_wireplumber_default_source.sh --install"
    info "  se o mic do controle é o que você quer, peça de propósito: hefesto-dualsense4unix mic promote (isso grava a marca em ${marca}, e o doctor para de reclamar)"
}

check_dropin_do_alto_falante_acordado() {
    local posto; posto="$(_wp_dropin 54-hefesto-dualsense-alto-falante-nunca-dorme.conf)"
    local nome; nome="$(basename "${posto}")"
    local fonte="${ROOT_DIR}/assets/wireplumber/${nome}"
    if [[ ! -f "${posto}" ]]; then
        warn "o alto-falante do controle pode dormir no cabo (falta ${posto}) — o começo de cada som depois de um silêncio se perde: $(conselho_de_instalacao)$(so_no_checkout "(só ele: bash scripts/fix_wireplumber_default_source.sh --nunca-dorme)")"
        return
    fi
    if [[ -r "${fonte}" ]] && ! cmp -s "${fonte}" "${posto}"; then
        warn "o drop-in ${nome} é de outra versão — $(conselho_de_instalacao)$(so_no_checkout "(só ele: bash scripts/fix_wireplumber_default_source.sh --nunca-dorme)")"
        return
    fi
    local leu=0; _wireplumber_leu_a_regra session.suspend-timeout-seconds 0 alsa_output || leu=$?
    if [[ "${leu}" -eq 1 ]]; then
        warn "o drop-in 54 está em $(_wp_dropin_dir), mas o WirePlumber não leu a regra (o nó de saída do controle está sem session.suspend-timeout-seconds = 0) — o alto-falante pode dormir e o começo de cada som se perde: $(conselho_de_instalacao)$(so_no_checkout "(só ele: bash scripts/fix_wireplumber_default_source.sh --nunca-dorme)")"
        return
    fi
    pass "o alto-falante do controle não dorme no cabo (drop-in 54 no lugar)"
}

check_dualsense_sink_disabled() {
    local d; d="$(_wp_dropin 53-hefesto-dualsense-disable-output.conf)"
    if [[ -f "${d}" ]]; then
        warn "saída de áudio do DualSense DESLIGADA (drop-in 53) — alto-falante/fone do controle mudos e canal de haptic-de-áudio off. Se não foi intencional: fix_wireplumber_default_source.sh --enable-mic + systemctl --user restart wireplumber"
    else
        pass "saída de áudio do DualSense preservada (sem o drop-in 53 disable-output)"
    fi
}

check_ucm_do_dualsense() {
    local raiz="${HEFESTO_RAIZ_UCM:-/usr/share/alsa/ucm2}"
    local cards="${HEFESTO_PROC_CARDS:-/proc/asound/cards}"
    local linha nome placas=0 sem=0
    local -a placas_no_cabo=()
    if [[ -r "${cards}" ]]; then
        while IFS= read -r linha; do
            nome="${linha#"${linha%%[![:space:]]*}"}"
            [[ "${nome}" == "Sony Interactive Entertainment DualSense"* ]] || continue
            placas_no_cabo+=("${nome}")
        done < "${cards}"
    fi
    if [[ ! -f "${raiz}/ucm.conf" ]]; then
        if [[ "${#placas_no_cabo[@]}" -gt 0 ]]; then
            warn "DualSense no cabo e sem ${raiz}/ucm.conf — sem o UCM do sistema (o pacote alsa-ucm-conf; no Fedora, alsa-ucm) a placa do controle não abre pelo perfil e a vibração dos jogos da Sony não chega pelo cabo. Depois de instalar o pacote, rode scripts/doctor.sh --fix (ou bash scripts/install_ucm_dualsense.sh)"
        else
            info "sem ${raiz}/ucm.conf — esta distro não usa UCM; perfil do DualSense não conferido"
        fi
        return
    fi
    [[ -r "${cards}" ]] || return
    for nome in ${placas_no_cabo[@]+"${placas_no_cabo[@]}"}; do
        placas=$((placas + 1))
        if [[ ! -f "${raiz}/conf.d/USB-Audio/${nome}.conf" ]]; then
            sem=$((sem + 1))
            warn "DualSense no cabo sem o perfil UCM (${nome}) — a vibração dos jogos da Sony não chega pelo cabo. Rode: bash scripts/install_ucm_dualsense.sh (ou scripts/doctor.sh --fix)"
        fi
    done
    if [[ "${placas}" -eq 0 ]]; then
        info "nenhum DualSense no cabo — perfil UCM não conferido"
        return
    fi
    [[ "${sem}" -eq 0 ]] || return
    local sinks total hifi
    sinks="$(timeout 5 pactl list short sinks 2>/dev/null)" || sinks=""
    total="$(printf '%s\n' "${sinks}" | grep -ci 'alsa_output[^[:space:]]*dualsense' || true)"
    hifi="$(printf '%s\n' "${sinks}" | grep -ci 'alsa_output[^[:space:]]*dualsense[^[:space:]]*Speaker__sink' || true)"
    if [[ "${total}" -gt "${hifi}" ]]; then
        warn "o gancho UCM existe, mas $((total - hifi)) placa(s) do DualSense abriram sem ele — replugue o controle (ou: systemctl --user restart wireplumber)"
    else
        pass "perfil UCM do DualSense armado (${placas} placa(s) no cabo)"
    fi
}

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

_dualsense_rotas_mudas() {
    local arquivo="${1:-${HOME}/.local/state/wireplumber/default-routes}"
    local direcao="${2:-input}"
    [[ -r "${arquivo}" ]] || return 0
    grep -iE "^[^=]*dual[[:alnum:]_]*sense[^=:]*:${direcao}:[^=]*=.*\"mute\":[[:space:]]*true" \
        "${arquivo}" 2>/dev/null | sed -E 's/=.*$//' || true
}

_dualsense_source_nome() {
    awk 'tolower($2) ~ /^alsa_input\..*dualsense/ { print $2; exit }' "${1:--}"
}

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

_dualsense_perfil_status() {
    python3 -c '
import json, sys
arquivo = sys.argv[1]
try:
    cartoes = json.load(sys.stdin if arquivo == "-" else open(arquivo, encoding="utf-8"))
except (OSError, ValueError):
    sys.exit(0)
card = ativo = ""
melhor, melhorprio, serve = "", 0, {}
for c in cartoes:
    nome = c.get("name") or ""
    if not nome.startswith("alsa_card.") or "dualsense" not in nome.lower():
        continue
    card = nome
    ativo = c.get("active_profile") or ""
    for chave, perfil in (c.get("profiles") or {}).items():
        # `sources` e `available` saem do próprio pactl. Sem fonte de captura o perfil
        # não serve ao microfone; indisponível, ele produz o nó sem porta que
        # silenciou a medição.
        temfonte = (perfil.get("sources") or 0) >= 1
        disponivel = perfil.get("available") is True
        prio = perfil.get("priority") or 0
        if temfonte and disponivel and prio > melhorprio:
            melhorprio, melhor = prio, chave
        serve[chave] = temfonte and disponivel
if card:
    escolhido = melhor if (not serve.get(ativo) and melhor and melhor != ativo) else ""
    print("%s\t%s\t%s" % (card, ativo, escolhido))
' "${1:--}"
}

_porta_ativa_da_captura_do_dualsense() {
    python3 -c '
import json, sys
try:
    nos = json.load(open(sys.argv[1], encoding="utf-8"))
except (OSError, ValueError):
    sys.exit(0)
for no in nos:
    nome = (no.get("name") or "").lower()
    if nome.startswith("alsa_input.") and "dualsense" in nome and no.get("active_port"):
        print(no["active_port"])
        break
' "$1"
}

_dualsense_porta_de_captura_status() {
    local porta elemento liga="não" fora="não"

    porta="$(_porta_ativa_da_captura_do_dualsense "${1:-/dev/null}")"
    [[ -n "${porta}" ]] || return 0

    elemento="$(awk -v aspa="'" '
        index($0, "Simple mixer control ") == 1 {
            nome = substr($0, index($0, aspa) + 1)
            corte = index(nome, aspa)
            if (corte > 1) { nome = substr(nome, 1, corte - 1) } else { nome = "" }
            tem = 0
            next
        }
        /Capabilities:/ && /cvolume/ { tem = 1 }
        tem && /Capture channels:/ && nome != "" { print nome; exit }
    ' "${2:-/dev/null}")"

    if [[ -r "${3:-}" ]] && [[ -n "${elemento}" ]] && awk -v alvo="${elemento}" '
        /^[[:space:]]*(CaptureVolume|CaptureMixerElem)[[:space:]]/ {
            if (index($0, alvo) > 0) { ligou = 1 }
            next
        }
        /^[[:space:]]*\[/ {
            secao = $0
            sub(/^[[:space:]]*/, "", secao)
            sub(/[[:space:]]*$/, "", secao)
            dentro = (secao == "[Element " alvo "]" || index(secao, "[Element " alvo ",") == 1)
            next
        }
        dentro && /^[[:space:]]*volume[[:space:]]*=[[:space:]]*merge[[:space:]]*$/ { ligou = 1 }
        END { exit(ligou ? 0 : 1) }
    ' "${3}"; then
        liga="sim"
    fi

    if [[ -n "${elemento}" && "${liga}" == "não" ]]; then
        fora="sim"
    fi
    printf '%s\t%s\t%s\n' "${porta}" "${elemento}" "${fora}"
}

_definicao_da_porta_de_captura() {
    local porta="$1" saida="$2"
    local raiz_ucm="${HEFESTO_RAIZ_UCM:-/usr/share/alsa/ucm2}"
    local raiz_acp="${HEFESTO_RAIZ_ACP:-/usr/share/alsa-card-profile/mixer/paths}"
    : > "${saida}"
    case "${porta}" in
        "[In] "*|"[Out] "*)
            local dispositivo="${porta#*] }"
            local verbo
            verbo="$(find "${raiz_ucm}" -name 'DualSense-HiFi.conf' -print -quit 2>/dev/null)"
            [[ -r "${verbo}" ]] || return 0
            awk -v alvo="SectionDevice.\"${dispositivo}\"" '
                index($0, alvo) == 1 { dentro = 1 }
                dentro { print }
                dentro && /^}/ { exit }
            ' "${verbo}" > "${saida}"
            ;;
        *)
            [[ -r "${raiz_acp}/${porta}.conf" ]] || return 0
            cat "${raiz_acp}/${porta}.conf" > "${saida}"
            ;;
    esac
}

_source_tem_porta_ativa() {
    python3 -c '
import json, sys
alvo, arquivo = sys.argv[1], sys.argv[2]
try:
    dados = json.load(sys.stdin if arquivo == "-" else open(arquivo, encoding="utf-8"))
except (OSError, ValueError):
    sys.exit(1)
for no in dados:
    if no.get("name") == alvo and (no.get("active_port") or "") not in ("", "(null)"):
        sys.exit(0)
sys.exit(1)
' "$1" "${2:--}"
}

_dualsense_source_tem_porta() {
    local nome="$1"
    [[ -z "${nome}" ]] && return 1
    _pactl_json sources | _source_tem_porta_ativa "${nome}"
}

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

check_mic_perfil_sem_sinal() {
    command -v pactl >/dev/null 2>&1 || { info "pactl ausente — não checo o perfil da placa do DualSense"; return; }
    local linha card ativo alvo
    linha="$(_pactl_json cards | _dualsense_perfil_status)"
    if [[ -z "${linha}" ]]; then
        info "nenhuma placa de áudio do DualSense agora (controle fora do cabo — por BT não existe placa)"
        return
    fi
    IFS=$'\t' read -r card ativo alvo <<< "${linha}"
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

check_mic_ganho_de_captura() {
    command -v pactl >/dev/null 2>&1 || { info "pactl ausente — não checo o ganho de captura do DualSense"; return; }
    command -v amixer >/dev/null 2>&1 || { info "amixer ausente — não checo o ganho de captura do DualSense"; return; }
    local indice
    indice="$(awk 'tolower($0) ~ /dualsense/ { print $1; exit }' \
        "${HEFESTO_PROC_CARDS:-/proc/asound/cards}" 2>/dev/null)"
    if [[ -z "${indice}" ]]; then
        info "nenhum DualSense no cabo — ganho de captura não conferido"
        return
    fi
    local tmp porta elemento fora
    tmp="$(mktemp -d)" || return
    _pactl_json sources > "${tmp}/sources"
    LC_ALL=C amixer -c "${indice}" scontents > "${tmp}/scontents" 2>/dev/null || true
    porta="$(_porta_ativa_da_captura_do_dualsense "${tmp}/sources")"
    _definicao_da_porta_de_captura "${porta}" "${tmp}/porta"
    local linha
    linha="$(_dualsense_porta_de_captura_status "${tmp}/sources" "${tmp}/scontents" "${tmp}/porta")"
    rm -rf "${tmp}"
    if [[ -z "${linha}" ]]; then
        info "sem source de captura do DualSense agora — ganho de captura não conferido"
        return
    fi
    IFS=$'\t' read -r porta elemento fora <<< "${linha}"
    if [[ "${fora}" == "sim" ]]; then
        warn "a porta de captura do DualSense (${porta}) não liga o elemento '${elemento}' — o ganho de captura fica fora do alcance do PipeWire, da tela e dela. Isto é sobre a CONFIGURAÇÃO do som, não sobre a qualidade do áudio"
        info "  quem define a porta hoje é o UCM do Hefesto (assets/ucm/DualSense-HiFi.conf); ligá-lo muda o SISTEMA de quem usa, e é escolha sua"
        info "  mede antes: scripts/ensaios/o_caminho_do_mic_no_cabo.py --ganho-plano"
        return
    fi
    pass "a porta de captura do DualSense (${porta}) alcança o ganho de hardware${elemento:+ ('${elemento}')} — e isto NÃO é um veredito sobre a qualidade do áudio"
}

fix_mic_dualsense() {
    if [[ -n "$(_dualsense_rotas_mudas)" ]]; then
        if bash "${ROOT_DIR}/scripts/fix_wireplumber_default_source.sh" --unmute-routes >/dev/null 2>&1; then
            pass "mute persistido das rotas do DualSense removido (camada 1)"
        else
            warn "falha ao remover o mute persistido das rotas do DualSense"
        fi
    fi

    command -v pactl >/dev/null 2>&1 || return 0

    local linha card ativo alvo
    linha="$(_pactl_json cards | _dualsense_perfil_status)"
    if [[ -n "${linha}" ]]; then
        IFS=$'\t' read -r card ativo alvo <<< "${linha}"
        local src_antes
        src_antes="$(LC_ALL=C pactl list sources short 2>/dev/null | _dualsense_source_nome)"
        if _dualsense_source_tem_porta "${src_antes}"; then
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

    fix_default_source_monitor

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

check_launch_wrapper() {
    local wrapper="${HOME}/.local/share/hefesto-dualsense4unix/bin/hefesto-launch"
    if [[ -x "${wrapper}" ]]; then
        pass "wrapper de launch instalado (${wrapper})"
    elif [[ -e "${wrapper}" ]]; then
        fail "wrapper hefesto-launch presente mas NÃO executável — rode: chmod +x ${wrapper}"
    else
        fail "wrapper hefesto-launch ausente — $(conselho_de_instalacao)$(so_no_checkout "(entra por default, sem flag)")"
    fi
    local pathlink="${HOME}/.local/bin/hefesto-launch"
    if command -v hefesto-launch >/dev/null 2>&1; then
        pass "wrapper no PATH ($(command -v hefesto-launch))"
    elif [[ -x "${pathlink}" ]]; then
        warn "symlink ${pathlink} existe mas ~/.local/bin não está no PATH desta sessão — 'hefesto-launch %command%' digitado à mão só funciona com o PATH ajustado"
    else
        warn "wrapper fora do PATH (${pathlink} ausente) — $(conselho_de_instalacao)$(so_no_checkout "(o passo 5 cria o symlink, sem flag)")"
    fi
    local envdir="${HOME}/.local/state/hefesto-dualsense4unix/launch_env"
    if [[ -f "${envdir}/default.env" ]]; then
        pass "materialização de launch viva (${envdir}/default.env)"
        [[ "${QUIET}" -eq 1 ]] || sed -n 's/^# estado: /       estado: /p' "${envdir}/default.env" | head -1
    else
        warn "launch_env/default.env ausente — o daemon materializa ao (re)iniciar/ligar a emulação; sem ele o wrapper lança sem envs (fail-safe: jogo abre, pode duplicar)"
    fi
    local stale_env
    stale_env="$(grep -ls "PROTON_ENABLE_HIDRAW" "${envdir}"/*.env 2>/dev/null | head -1)"
    if [[ -n "${stale_env}" ]]; then
        warn "launch_env com PROTON_ENABLE_HIDRAW (env morta nos Protons 10/11): ${stale_env} — materialização antiga; reinicie o daemon (systemctl --user restart hefesto-dualsense4unix) para regravar"
    fi
    info "controle DOBRANDO no jogo? use o botão 'Copiar opções p/ jogos' da GUI (string constante do wrapper) ou 'Aplicar aos jogos da Steam' (aplica o wrapper aos jogos, preservando as opções existentes)."
    check_sentinela_wrapper
    check_opcoes_por_jogo
}

check_copias_do_wrapper() {
    local bin="${HOME}/.local/share/hefesto-dualsense4unix/bin"
    local par nome fonte alvo razao velhas="" instaladas=0
    for par in \
        "hefesto-launch|assets/hefesto-launch.sh|" \
        "hefesto-camadas|src/hefesto_dualsense4unix/integrations/camadas_vulkan.py|as sobreposições Vulkan não saem no lançamento dos jogos" \
        "hefesto-audio-ks|src/hefesto_dualsense4unix/integrations/audio_ks_dualsense.py|a vibração dos jogos da Sony pelo DualSense não chega ao jogo sob Proton"; do
        IFS='|' read -r nome fonte razao <<<"${par}"
        alvo="${bin}/${nome}"
        if [[ ! -x "${alvo}" ]]; then
            [[ -n "${razao}" ]] && warn "curador ${nome} ausente ou sem permissão de execução em ${bin} — ${razao}; $(conselho_de_instalacao)"
            continue
        fi
        instaladas=$((instaladas + 1))
        esta_instalacao_e_um_checkout || continue
        command -v cmp >/dev/null 2>&1 || continue
        [[ -f "${ROOT_DIR}/${fonte}" ]] || continue
        cmp -s "${ROOT_DIR}/${fonte}" "${alvo}" || velhas="${velhas}${velhas:+, }${nome}"
    done
    if [[ -n "${velhas}" ]]; then
        warn "cópia em ${bin} diferente deste checkout: ${velhas} — o lançamento roda a versão velha até reinstalar; $(conselho_de_instalacao) (as cópias em bin/ só se refazem no install)"
    elif [[ "${instaladas}" -eq 3 ]]; then
        if esta_instalacao_e_um_checkout; then
            pass "wrapper e curadores do lançamento instalados e iguais a este checkout"
        else
            pass "wrapper e curadores do lançamento instalados (${bin})"
        fi
    fi
}

check_ultimo_device_ks() {
    local arq="${XDG_STATE_HOME:-${HOME}/.local/state}/hefesto-dualsense4unix/launch_env/audio_ks_ultimo"
    if [[ ! -f "${arq}" ]]; then
        info "device KS do DualSense: nenhum lançamento pelo Proton registrado ainda"
        return
    fi
    local chave valor appid="" epoch="" rc="" motivo="" tentativas=""
    while IFS='=' read -r chave valor; do
        case "${chave}" in
            appid)      appid="${valor}" ;;
            epoch)      epoch="${valor}" ;;
            rc)         rc="${valor}" ;;
            motivo)     motivo="${valor}" ;;
            tentativas) tentativas="${valor}" ;;
        esac
    done < "${arq}"
    local jogo="um jogo sem appid" quando="" agora
    [[ "${appid}" =~ ^[0-9]+$ ]] && jogo="$(_rotulo_do_appid "${appid}")"
    agora="$(date +%s 2>/dev/null || true)"
    if [[ "${epoch}" =~ ^[0-9]+$ && "${agora}" =~ ^[0-9]+$ && "${agora}" -ge "${epoch}" ]]; then
        local seg=$((agora - epoch))
        if [[ "${seg}" -lt 3600 ]]; then
            quando=", há $((seg / 60)) min"
        elif [[ "${seg}" -lt 172800 ]]; then
            quando=", há $((seg / 3600)) h"
        else
            quando=", há $((seg / 86400)) dia(s)"
        fi
    fi
    case "${motivo}" in
        ok)
            pass "device KS do DualSense conferido no último lançamento pelo Proton (${jogo}${quando})" ;;
        sem-registro)
            info "o jogo ${jogo} abriu antes de o prefixo existir${quando}; a vibração do DualSense nele vale a partir do próximo lançamento" ;;
        ocupado)
            warn "device KS do DualSense NÃO gravado no último lançamento (${jogo}${quando}): o wineserver daquele prefixo continuou vivo depois de ${tentativas:-?} tentativa(s) — feche o jogo por completo e abra de novo" ;;
        erro)
            warn "o curador do device KS falhou no último lançamento (${jogo}${quando}, código ${rc:-?}) — a vibração dos jogos da Sony pode não chegar; rode à mão para ver o erro: python3 ${HOME}/.local/share/hefesto-dualsense4unix/bin/hefesto-audio-ks --prefixo <compatdata do jogo>" ;;
        sem-curador)
            warn "o último lançamento (${jogo}${quando}) não achou o curador do device KS — $(conselho_de_instalacao)" ;;
        sem-python)
            warn "o último lançamento pelo Proton (${jogo}${quando}) não achou python3 no PATH — sem ele o lançamento não fala com o daemon e a vibração dos jogos da Sony não chega; instale o python3 pelo gerenciador de pacotes da sua distribuição e abra o jogo de novo" ;;
        desligado)
            info "último lançamento pelo Proton (${jogo}${quando}) sem a opção da vibração: sem DualSense na mesa quando o jogo abriu, ou com o daemon fora do ar — quem entrar depois nessa sessão fica sem vibração até reabrir o jogo" ;;
        removido)
            info "último lançamento pelo Proton (${jogo}${quando}) sem a opção da vibração: sem DualSense na mesa quando o jogo abriu, ou com o daemon fora do ar — quem entrar depois nessa sessão fica sem vibração até reabrir o jogo, e o device KS de um lançamento anterior saiu do prefixo" ;;
        *)
            info "rastro do device KS ilegível em ${arq}" ;;
    esac
}

check_sentinela_wrapper() {
    local py="${ROOT_DIR}/src/hefesto_dualsense4unix/integrations/sentinela_do_wrapper.py"
    if [[ ! -f "${py}" ]] || ! command -v python3 >/dev/null 2>&1; then
        return
    fi
    local resumo
    resumo="$(python3 "${py}" --censo 2>/dev/null | python3 -c '
import json
import sys

d = json.load(sys.stdin)
falta = d.get("faltantes") or []
def rot(m):
    return "; ".join(j["rotulo"] for j in falta if j["motivo"] == m)
print("regressao=" + rot("regressao"))
print("novo=" + rot("novo"))
print("estendido=" + rot("ignore_estendido"))
print("recusados=" + ", ".join(d.get("recusados") or []))
print("steam=" + ("1" if d.get("steam_aberta") else "0"))
print("jogo=" + ("1" if d.get("jogo_aberto") else "0"))
print("erros=" + str(len(d.get("erros") or [])))
' 2>/dev/null)"
    if [[ -z "${resumo}" ]]; then
        info "censo do wrapper indisponível — rode: python3 ${py} --relatorio"
        return
    fi
    local regressao novo estendido recusados steam jogo
    regressao="$(sed -n 's/^regressao=//p' <<<"${resumo}")"
    novo="$(sed -n 's/^novo=//p' <<<"${resumo}")"
    estendido="$(sed -n 's/^estendido=//p' <<<"${resumo}")"
    recusados="$(sed -n 's/^recusados=//p' <<<"${resumo}")"
    steam="$(sed -n 's/^steam=//p' <<<"${resumo}")"
    jogo="$(sed -n 's/^jogo=//p' <<<"${resumo}")"

    local como="o Hefesto repõe sozinho assim que a Steam fechar; para não esperar: python3 ${py} --reparar"
    if [[ "${jogo}" == "1" ]]; then
        como="há um JOGO aberto — o reparo fica para quando a Steam fechar (fechá-la agora mataria o jogo)"
    elif [[ "${steam}" == "1" ]]; then
        como="a Steam está aberta — o Hefesto repõe assim que ela fechar (com ela viva a edição seria engolida na saída)"
    fi

    if [[ -n "${regressao}" ]]; then
        fail "contrato steam-localconfig quebrou (confira: grep -c hefesto-launch ~/.steam/steam/userdata/*/config/localconfig.vdf): jogo(s) que PERDERAM as Opções de Inicialização do Hefesto: ${regressao} — no Bluetooth o jogo tende a não enxergar controle nenhum, com o controle vivo, a luz acesa e o perfil aplicado (foi o defeito do Pragmata em 15/08); ${como}"
    elif [[ -n "${novo}" ]]; then
        warn "jogo(s) sem as Opções de Inicialização do Hefesto: ${novo} — ${como}"
    else
        pass "nenhum jogo perdeu as Opções de Inicialização do Hefesto"
    fi
    [[ -n "${estendido}" ]] && warn "Opções com a lista de IGNORE ESTENDIDA à mão em ${estendido} — intocáveis de propósito (remover só o trecho do Hefesto deixaria um fragmento que impede o jogo de abrir); reparo manual"
    [[ -n "${recusados}" ]] && info "fora do wrapper por escolha dela (jogos_sem_wrapper.txt): ${recusados}"
    check_arvore_canonica_do_wrapper
    return 0
}

check_opcoes_por_jogo() {
    local py="${ROOT_DIR}/src/hefesto_dualsense4unix/integrations/opcoes_por_jogo.py"
    if [[ ! -f "${py}" ]] || ! command -v python3 >/dev/null 2>&1; then
        return
    fi
    local resumo
    resumo="$(python3 "${py}" --conferir 2>/dev/null | HEFESTO_SRC="${ROOT_DIR}/src" python3 -c '
import json
import os
import sys

sys.path.insert(0, os.environ.get("HEFESTO_SRC", ""))
d = json.load(sys.stdin)
from hefesto_dualsense4unix.integrations.opcoes_por_jogo import AVISO_DO_DEFEITO
print("jogos=" + str(len(d.get("jogos") or [])))
vistos = set()
for x in d.get("defeitos") or []:
    linha = "defeito=%s|%s|%s" % (x["estado"], x["appid"], AVISO_DO_DEFEITO.get(x["estado"], ""))
    if linha not in vistos:
        vistos.add(linha)
        print(linha)
' 2>/dev/null)"
    [[ -z "${resumo}" ]] && return
    local jogos defeitos
    jogos="$(sed -n 's/^jogos=//p' <<<"${resumo}")"
    defeitos="$(sed -n 's/^defeito=//p' <<<"${resumo}")"
    if [[ -z "${defeitos}" ]]; then
        if [[ "${jogos}" != "0" ]]; then
            pass "as opções por jogo declaradas no Hefesto estão onde a Steam as lê"
        fi
        return 0
    fi
    local estado appid aviso nome
    while IFS='|' read -r estado appid aviso; do
        [[ -z "${estado}" ]] && continue
        nome="a conta da Steam"
        [[ "${appid}" =~ ^[0-9]+$ ]] && nome="$(_rotulo_do_appid "${appid}")"
        warn "contrato steam-localconfig: opção por jogo de ${nome}: ${aviso} (confira: python3 ${py} --conferir)"
    done <<<"${defeitos}"
    return 0
}

check_arvore_canonica_do_wrapper() {
    command -v python3 >/dev/null 2>&1 || return 0
    local saida
    saida="$(HEFESTO_SRC="${ROOT_DIR}/src" python3 - <<'PY' 2>/dev/null
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.environ.get("HEFESTO_SRC", ""))
try:
    from hefesto_dualsense4unix.integrations.steam_launch_options import (
        WRAPPER_PREFIX,
        discover_vdfs,
        is_sandboxed_layout,
        rotulo_do_jogo,
    )
except Exception:  # noqa: BLE001
    sys.exit(0)

CANONICA = ("UserLocalConfigStore", "Software", "Valve", "Steam", "apps")
CHAVE = re.compile(r'^"((?:\\.|[^"\\])*)"$')
PAR = re.compile(r'^"LaunchOptions"\s+"(?P<v>(?:\\.|[^"\\])*)"$', re.IGNORECASE)

canonicos: dict[str, str] = {}
secundarios: dict[str, str] = {}
valor_secundario: dict[str, str] = {}
lidos = 0
for vdf in discover_vdfs():
    if is_sandboxed_layout(vdf):
        continue
    try:
        texto = vdf.read_text(encoding="utf-8")
    except (OSError, ValueError):
        continue
    pilha: list[str] = []
    pendente = None
    visto = False
    for bruta in texto.splitlines():
        linha = bruta.strip()
        if not linha:
            continue
        if linha == "{":
            pilha.append(pendente or "")
            pendente = None
            continue
        if linha == "}":
            if pilha:
                pilha.pop()
            pendente = None
            continue
        chave = CHAVE.match(linha)
        if chave is not None:
            pendente = chave.group(1)
            continue
        pendente = None
        par = PAR.match(linha)
        if par is None or len(pilha) < 2 or not pilha[-1].isdigit():
            continue
        visto = True
        appid = pilha[-1]
        valor = par.group("v").replace('\\"', '"').replace("\\\\", "\\")
        if tuple(pilha[:-1]) == CANONICA:
            canonicos[appid] = valor
        else:
            secundarios.setdefault(appid, "/".join(pilha[:-1]))
            valor_secundario.setdefault(appid, valor)
    lidos += 1 if visto else 0

if not lidos:
    sys.exit(0)
sem = [a for a, v in canonicos.items() if WRAPPER_PREFIX not in v]
orfaos = [a for a in secundarios if a not in canonicos]
nossos = [a for a in orfaos if WRAPPER_PREFIX in valor_secundario.get(a, "")]
alheios = [a for a in orfaos if a not in nossos]
print("total=%d" % len(canonicos))
print("sem=" + "; ".join(rotulo_do_jogo(a) for a in sorted(sem)))
print("orfaos_nossos=" + "; ".join(rotulo_do_jogo(a) for a in sorted(nossos)))
print("orfaos_alheios=" + "; ".join(rotulo_do_jogo(a) for a in sorted(alheios)))
print("poluidos=%d" % len(secundarios))
print(
    "poluidos_nossos=%d"
    % sum(1 for v in valor_secundario.values() if WRAPPER_PREFIX in v)
)
PY
)"
    [[ -n "${saida}" ]] || return 0
    local total sem orfaos_nossos orfaos_alheios poluidos poluidos_nossos
    total="$(sed -n 's/^total=//p' <<<"${saida}")"
    sem="$(sed -n 's/^sem=//p' <<<"${saida}")"
    orfaos_nossos="$(sed -n 's/^orfaos_nossos=//p' <<<"${saida}")"
    orfaos_alheios="$(sed -n 's/^orfaos_alheios=//p' <<<"${saida}")"
    poluidos="$(sed -n 's/^poluidos=//p' <<<"${saida}")"
    poluidos_nossos="$(sed -n 's/^poluidos_nossos=//p' <<<"${saida}")"

    if [[ -n "${sem}" ]]; then
        fail "na árvore que a Steam de fato lê (Software/Valve/Steam/apps), ESTE(S) jogo(s) NÃO chamam o wrapper: ${sem} — sem eles, no Bluetooth o jogo tende a não enxergar controle nenhum, mesmo com o controle vivo e o perfil aplicado. Reparo: o Hefesto repõe sozinho assim que a Steam fechar (é quando a reposição sobrevive), e também ao salvar ou aplicar um perfil"
    else
        pass "os ${total:-0} jogos da árvore viva (Software/Valve/Steam/apps) chamam o wrapper"
    fi
    if [[ -n "${orfaos_nossos}" ]]; then
        warn "Opções de Inicialização NOSSAS (com a chamada do wrapper) numa árvore que a Steam não lê, para jogo(s) que nem existem na árvore viva: ${orfaos_nossos} — não quebram nada e não contam como cobertura, mas são lixo nosso no arquivo dela; recolha com a Steam fechada: python3 ${ROOT_DIR}/src/hefesto_dualsense4unix/integrations/steam_launch_options.py --recolher-fora-da-arvore-viva"
    elif [[ -n "${orfaos_alheios}" ]]; then
        info "sobra inerte numa árvore que a Steam não lê, para jogo(s) fora da árvore viva: ${orfaos_alheios} — a linha NÃO carrega a nossa chamada do wrapper, e o censo não a conta (ele lê só Software/Valve/Steam/apps desde 16/08). Quem abriu esse buraco foi um escritor nosso sem âncora, em 21/07; para recolher, com a Steam fechada: python3 ${ROOT_DIR}/src/hefesto_dualsense4unix/integrations/steam_launch_options.py --recolher-fora-da-arvore-viva"
    elif [[ "${poluidos_nossos:-0}" -gt 0 ]]; then
        info "${poluidos_nossos} de ${poluidos:-0} bloco(s) de 'apps' fora da árvore viva ainda têm a chamada do wrapper (escritas por nós em 21/07) — inertes para a Steam e ignoradas pelo censo; recolha com a Steam fechada: python3 ${ROOT_DIR}/src/hefesto_dualsense4unix/integrations/steam_launch_options.py --recolher-fora-da-arvore-viva"
    elif [[ "${poluidos:-0}" -gt 0 ]]; then
        info "${poluidos} bloco(s) de 'apps' fora da árvore viva também têm LaunchOptions — inertes para a Steam, sem a chamada do wrapper, e o censo não as lê. Quem as pôs lá foi um escritor nosso sem âncora (21/07); para recolher, com a Steam fechada: python3 ${ROOT_DIR}/src/hefesto_dualsense4unix/integrations/steam_launch_options.py --recolher-fora-da-arvore-viva"
    fi
    return 0
}

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
frageis = res.get("native_bt_fragil_controles")
nums = (
    [n for n in frageis if isinstance(n, int) and not isinstance(n, bool)]
    if isinstance(frageis, list)
    else []
)
if len(nums) > 1:
    quais = ", ".join(str(n) for n in nums[:-1]) + " e " + str(nums[-1])
else:
    quais = "".join(str(n) for n in nums)
print("native_bt_quais=" + quais)
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
        info "daemon não reporta o sinal de autoridade de exibição (versão antiga, de antes desse sinal)"
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
                warn "autoridade de exibição UNKNOWN (causa: ${motivo:-sem motivo reportado}) — degrada para o comportamento de hoje (réplica passa, jogo vence, daemon NÃO repinta); nunca pior, mas sem a defesa de repintar a cor que o jogo apagou"
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
        info "controle player_slot=${slot:-—} lightbar_source=${fonte:-desconhecida} cor_pedida=${rgb:-None}"
    done <<<"${out}"
}

_saida_do_modo_no_ar() {
    local sock="$1" py="$2"
    HEFESTO_SRC="${ROOT_DIR}/src" "${py}" - "${sock}" <<'PY' 2>/dev/null
import json
import os
import socket
import sys
import time

src = os.environ.get("HEFESTO_SRC", "")
if src and os.path.isdir(src):
    sys.path.insert(0, src)
try:
    from hefesto_dualsense4unix.core.o_modo_no_ar import FALHA, modo_contra_o_ar
except Exception:  # noqa: BLE001
    print("sem-produto")
    raise SystemExit(0)


def _estado():
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(2.0)
    try:
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
                break
            buf += chunk
    finally:
        s.close()
    resultado = json.loads(buf.decode("utf-8")).get("result")
    if not isinstance(resultado, dict) or not resultado:
        raise ValueError("sem estado")
    return resultado


try:
    estado = _estado()
except Exception:  # noqa: BLE001
    print("sem-ipc")
    raise SystemExit(0)
try:
    linhas = modo_contra_o_ar(estado)
    if any(linha.veredito == FALHA for linha in linhas):
        time.sleep(1.5)
        try:
            estado = _estado()
        except Exception:  # noqa: BLE001
            pass
        else:
            linhas = modo_contra_o_ar(estado)
except ImportError:
    print("sem-produto")
    raise SystemExit(0)
except Exception as erro:  # noqa: BLE001
    print(f"erro|{type(erro).__name__}")
    raise SystemExit(0)
if not linhas:
    modo = "Conexão Nativa" if estado.get("native_mode") is True else "emulação desligada"
    print(f"sem-jogador|{modo}")
for linha in linhas:
    print(f"{linha.veredito}|{linha.frase()}")
PY
}

check_o_modo_no_ar() {
    local sock py saida
    sock="$(runtime_socket)"
    if [[ ! -S "${sock}" ]]; then
        info "daemon parado — sem modo no ar a conferir (suba o daemon e rode de novo)"
        return
    fi
    py="$(_python_do_produto)"
    [[ -n "${py}" ]] || { info "sem python para conferir o modo de cada jogador"; return; }
    saida="$(_saida_do_modo_no_ar "${sock}" "${py}")" || saida=""
    case "${saida}" in
        sem-produto)
            info "o modo de cada jogador não foi conferido (o pacote não está ao alcance do python ${py})"
            return ;;
        sem-ipc|"")
            warn "IPC não respondeu — o modo de cada jogador não foi conferido (daemon travado?)"
            return ;;
        erro\|*)
            warn "a conferência do modo de cada jogador quebrou (${saida#erro|}) — o modo não foi conferido"
            return ;;
        sem-jogador\|*)
            pass "${saida#sem-jogador|}: nenhum jogador com pad e nenhum pad no ar"
            return ;;
    esac
    local veredito frase
    while IFS='|' read -r veredito frase; do
        case "${veredito}" in
            ok)    pass "${frase}" ;;
            aviso) warn "${frase}" ;;
            falha) fail "${frase}" ;;
        esac
    done <<<"${saida}"
}

check_a_hora_do_pad() {
    local sock py saida
    sock="$(runtime_socket)"
    if [[ ! -S "${sock}" ]]; then
        info "daemon parado — a hora de nascer de cada pad não se mede (suba o daemon e rode de novo)"
        return
    fi
    command -v journalctl >/dev/null 2>&1 || { info "journalctl ausente — a hora de nascer de cada pad não se mede"; return; }
    py="$(_python_do_produto)"
    [[ -n "${py}" ]] || { info "sem python para medir a hora de nascer de cada pad"; return; }
    saida="$(HEFESTO_SRC="${ROOT_DIR}/src" "${py}" - \
        <(journalctl -b _TRANSPORT=kernel -o short-iso-precise --no-pager 2>/dev/null \
            | grep -E ' as /devices/virtual/input/input[0-9]+$') \
        <(journalctl --user -b -u "${APP_ID}.service" -o short-iso-precise --no-pager 2>/dev/null \
            | grep -E 'daemon_starting|uinput_device_created') <<'PY' 2>/dev/null
import os
import sys

src = os.environ.get("HEFESTO_SRC", "")
if src and os.path.isdir(src):
    sys.path.insert(0, src)
try:
    from hefesto_dualsense4unix.core.o_modo_no_ar import hora_do_pad
except Exception:  # noqa: BLE001
    print("sem-produto")
    raise SystemExit(0)
with open(sys.argv[1], encoding="utf-8", errors="replace") as fh:
    kernel = fh.read().splitlines()
with open(sys.argv[2], encoding="utf-8", errors="replace") as fh:
    daemon = fh.read().splitlines()
partidas = [i for i, linha in enumerate(daemon) if "daemon_starting" in linha]
if not partidas:
    print("sem-diario")
    raise SystemExit(0)
registrados = sum("uinput_device_created" in linha for linha in daemon[partidas[-1] + 1 :])
try:
    medidas = hora_do_pad(kernel, daemon)
except Exception as erro:  # noqa: BLE001
    print(f"erro|{type(erro).__name__}")
    raise SystemExit(0)
if len(medidas) != registrados:
    print(f"erro|pads no diário: {registrados}, lidos: {len(medidas)}")
    raise SystemExit(0)
if not medidas:
    print("sem-pad")
    raise SystemExit(0)
if not any(linha.strip() for linha in kernel):
    print(f"sem-kernel|{len(medidas)}")
    raise SystemExit(0)
for medida in medidas:
    print(f"{medida.veredito}|{medida.frase()}")
PY
)" || saida=""
    case "${saida}" in
        sem-produto)
            info "a hora de nascer de cada pad não foi medida (o pacote não está ao alcance do python ${py})"
            return ;;
        sem-diario)
            info "o diário do daemon não tem a subida dele — a hora de nascer de cada pad não foi medida"
            return ;;
        "")
            warn "a medida da hora de cada pad não respondeu — a hora não foi medida"
            return ;;
        erro\|*)
            warn "a medida da hora de cada pad quebrou (${saida#erro|}) — a hora não foi medida"
            return ;;
        sem-pad)
            info "nenhum pad uinput nasceu desde que o daemon subiu — a hora do pad não tem o que medir"
            return ;;
        sem-kernel\|*)
            warn "o diário do kernel não está ao alcance deste usuário (ele pede o grupo systemd-journal ou adm) — a hora de nascer de ${saida#sem-kernel|} pad(s) não foi medida"
            return ;;
    esac
    local veredito frase
    while IFS='|' read -r veredito frase; do
        case "${veredito}" in
            ok)    pass "${frase}" ;;
            aviso) warn "${frase}" ;;
            falha) fail "${frase}" ;;
        esac
    done <<<"${saida}"
}

check_o_pad_em_usb() {
    local py saida
    py="$(_python_do_produto)"
    [[ -n "${py}" ]] || { info "sem python para conferir o contrato do pad em USB"; return; }
    saida="$(HEFESTO_SRC="${ROOT_DIR}/src" "${py}" - <<'PY' 2>/dev/null
import os
import sys

src = os.environ.get("HEFESTO_SRC", "")
if src and os.path.isdir(src):
    sys.path.insert(0, src)
try:
    from hefesto_dualsense4unix.core.system_check import (
        contrato_do_pad_em_usb,
        vagas_do_pad_em_usb,
    )
except Exception:  # noqa: BLE001
    print("sem-produto")
    raise SystemExit(0)
raiz = os.environ.get("HEFESTO_RAIZ_MODULOS") or "/sys/module"
faltam = contrato_do_pad_em_usb(
    raiz_modulos=raiz,
    lib_modules=os.environ.get("HEFESTO_LIB_MODULES") or None,
)
vagas, teto = vagas_do_pad_em_usb(raiz_modulos=raiz)
if not faltam and vagas is not None and vagas < teto:
    print(f"vagas:{vagas}:{teto}")
else:
    print("faltam:" + ",".join(faltam))
PY
)" || saida=""
    case "${saida}" in
        "faltam:")
            pass "o pad virtual pode nascer em USB (libcomposite, usb_f_hid, usbip_vudc e vhci_hcd ao alcance)" ;;
        vagas:*)
            local vagas="${saida#vagas:}"
            warn "o usbip_vudc está no ar com ${vagas%%:*} vagas e o Hefesto usa ${vagas#*:}: do pad $(( ${vagas%%:*} + 1 )) em diante o controle nasce uhid, sem par USB, e o jogo com a biblioteca da Sony varre o áudio; reinicie o hefesto-hidraw-broker sem jogo aberto (ele recarrega o módulo com ${vagas#*:} vagas)" ;;
        "faltam:?")
            info "o contrato do pad em USB não se deixou ler" ;;
        faltam:*)
            warn "o kernel não traz ${saida#faltam:} — o pad virtual nasce uhid, sem porta USB própria, e fica sem a háptica por áudio no rádio (no cabo ela segue pela placa do controle); com os módulos instalados para este kernel, reinicie o hefesto-hidraw-broker (ele os carrega)" ;;
        *)
            info "contrato do pad em USB não conferido (o pacote não está ao alcance do python ${py})" ;;
    esac
}

check_o_pad_no_uhid() {
    local sock py saida
    sock="$(runtime_socket)"
    if [[ ! -S "${sock}" ]]; then
        info "daemon parado — não sei quais pads ficaram no uhid (suba o daemon e rode de novo)"
        return
    fi
    command -v journalctl >/dev/null 2>&1 || { info "journalctl ausente — não sei quais pads ficaram no uhid"; return; }
    py="$(_python_do_produto)"
    [[ -n "${py}" ]] || { info "sem python — não sei quais pads ficaram no uhid"; return; }
    saida="$(HEFESTO_SRC="${ROOT_DIR}/src" "${py}" - \
        <(journalctl --user -b -u "${APP_ID}.service" -o short-iso-precise --no-pager 2>/dev/null \
            | grep -E 'daemon_starting|pad_usb_|uhid_device_created|vpad_parou') <<'PY' 2>/dev/null
import os
import sys

src = os.environ.get("HEFESTO_SRC", "")
if src and os.path.isdir(src):
    sys.path.insert(0, src)
try:
    from hefesto_dualsense4unix.integrations.pad_usb import quem_ficou_no_uhid
except Exception:  # noqa: BLE001
    print("sem-produto")
    raise SystemExit(0)
with open(sys.argv[1], encoding="utf-8", errors="replace") as fh:
    no_uhid = quem_ficou_no_uhid(fh.read().splitlines())
if no_uhid is None:
    print("sem-diario")
elif not no_uhid:
    print("ok")
else:
    for jogador, motivo in sorted(no_uhid.items()):
        print(f"{jogador}|{motivo}")
PY
)" || saida=""
    case "${saida}" in
        sem-produto)
            info "não sei quais pads ficaram no uhid (o pacote não está ao alcance do python ${py})"
            return ;;
        sem-diario|"")
            info "o diário do daemon não tem a subida dele — não sei quais pads ficaram no uhid"
            return ;;
        ok)
            pass "nenhum pad ficou no uhid desde que o daemon subiu"
            return ;;
    esac
    local jogador motivo porque
    while IFS='|' read -r jogador motivo; do
        case "${motivo}" in
            nao_enumerou) porque="o gadget dele não enumerou pelo vhci_hcd no prazo" ;;
            caiu) porque="o gadget dele caiu (o broker reiniciou ou o vhci soltou a porta)" ;;
            porta_fora) porque="a porta USB dele falhou duas vezes seguidas e saiu do rodízio até o daemon reiniciar" ;;
            features_recusadas) porque="o gadget recusou as features do probe" ;;
            sem_contrato) porque="falta um contrato do kernel (veja a linha do pad em USB)" ;;
            indisponivel) porque="o broker não montou o gadget" ;;
            *) porque="${motivo}" ;;
        esac
        warn "o pad do jogador ${jogador} está no uhid, sem porta USB própria: ${porque}; o jogo com a biblioteca da Sony varre o áudio por este controle"
    done <<<"${saida}"
}

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

    local eff_display="${env_display:-${sysd_display}}"
    local eff_wayland="${env_wayland:-${sysd_wayland}}"
    if [[ -z "${env_display}" && -n "${sysd_display}" ]]; then
        info "DISPLAY só existe no systemd --user — o daemon importa sozinho no boot do autoswitch"
    fi

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

    local cosmic_ok=0 cosmic_linha="" py_produto=""
    py_produto="$(_python_do_produto)"
    if [[ -z "${eff_wayland}" ]]; then
        info "sem WAYLAND_DISPLAY — não há compositor Wayland a quem perguntar"
    else
        if [[ -n "${py_produto}" ]]; then
            cosmic_linha="$(WAYLAND_DISPLAY="${eff_wayland}" timeout 5 "${py_produto}" -m \
                hefesto_dualsense4unix.integrations.window_backends.cosmic_toplevel \
                2>/dev/null || true)"
        fi
        if [[ "${cosmic_linha}" == protocolo=sim* ]]; then
            cosmic_ok=1
            pass "compositor responde zcosmic_toplevel_info_v1 — apps Wayland nativos detectáveis (${cosmic_linha})"
        elif [[ "${cosmic_linha}" == protocolo=nao* ]]; then
            info "compositor sem zcosmic_toplevel_info_v1 (não é COSMIC) — backend cosmic fora"
        elif command -v wayland-info >/dev/null 2>&1; then
            if WAYLAND_DISPLAY="${eff_wayland}" timeout 3 wayland-info 2>/dev/null \
                 | grep -q 'zcosmic_toplevel_info_v1'; then
                warn "o compositor PUBLICA zcosmic_toplevel_info_v1, mas o hefesto instalado não sabe usá-lo — atualize: $(conselho_de_instalacao)"
            else
                info "compositor sem zcosmic_toplevel_info_v1 (wayland-info) — backend cosmic fora"
            fi
        else
            info "não deu para perguntar pelo zcosmic_toplevel_info_v1 (sem python do produto e sem wayland-info)"
        fi
    fi

    local wlrctl_ok=0 wlrctl_out="" wlrctl_rc=0
    if ! command -v wlrctl >/dev/null 2>&1; then
        info "wlrctl não instalado — backend wlrctl indisponível (irrelevante se o veredito abaixo for OK)"
    elif [[ -z "${eff_wayland}" ]]; then
        info "wlrctl instalado, mas sem WAYLAND_DISPLAY — nada a testar"
    else
        wlrctl_out="$(WAYLAND_DISPLAY="${eff_wayland}" timeout 3 wlrctl toplevel list 2>&1)"
        wlrctl_rc=$?
        if printf '%s' "${wlrctl_out}" | grep -qi 'toplevel management interface not found'; then
            info "compositor SEM wlr-foreign-toplevel-management (caso do cosmic-comp) — wlrctl instalado não ajuda aqui; quem cobre o COSMIC é o zcosmic_toplevel_info_v1, conferido acima"
        elif [[ "${wlrctl_rc}" -eq 0 ]]; then
            wlrctl_ok=1
            pass "wlrctl responde (wlr-foreign-toplevel-management OK)"
        else
            warn "wlrctl falhou (rc=${wlrctl_rc}): $(printf '%s' "${wlrctl_out}" | head -1)"
        fi
    fi

    local wayland_ok=0
    if [[ "${cosmic_ok}" -eq 1 || "${wlrctl_ok}" -eq 1 ]]; then
        wayland_ok=1
    fi
    if [[ "${xlib_ok}" -eq 1 && -z "${eff_wayland}" ]]; then
        pass "veredito: OK via xlib (sessão X11 pura — todas as janelas detectáveis)"
    elif [[ "${xlib_ok}" -eq 1 && "${wayland_ok}" -eq 1 ]]; then
        pass "veredito: OK via xlib + backend Wayland (cobertura total: jogos XWayland/Proton pelo xlib, apps Wayland nativos pelo compositor)"
    elif [[ "${xlib_ok}" -eq 1 ]]; then
        warn "veredito: DEGRADADO — só XWayland: jogos Proton/Steam e apps X11 são detectados (xlib), mas apps Wayland nativos aparecem como 'unknown'. Este compositor não publica nenhum dos dois caminhos Wayland (zcosmic_toplevel_info_v1, wlr-foreign-toplevel-management)."
    elif [[ "${wayland_ok}" -eq 1 ]]; then
        pass "veredito: OK via backend Wayland (sessão Wayland pura — sem o nome do processo, que só o xlib resolve)"
    elif [[ -z "${eff_display}" && -z "${eff_wayland}" ]]; then
        fail "veredito: CEGO — sem DISPLAY e sem WAYLAND_DISPLAY (nem no systemd --user). Se o daemon subiu antes do login gráfico, reinicie: systemctl --user restart ${APP_ID}.service"
    else
        fail "veredito: CEGO — há display no ambiente mas nenhum backend funciona (X inacessível, compositor sem zcosmic_toplevel_info_v1, wlrctl sem protocolo); o autoswitch ficará no fallback e perfil-por-jogo não muda sozinho"
    fi
}

profiles_dir_path() {
    printf '%s/%s/profiles' "${XDG_CONFIG_HOME:-${HOME}/.config}" "${APP_ID}"
}

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

_doctor_tem_bateria() {
    compgen -G "${HEFESTO_DOCTOR_SYS:-/sys}/class/power_supply/BAT*" >/dev/null 2>&1
}

_USB_VENDORES_DE_CONTROLE=" 054c 057e 2dc8 045e "

check_usb_power_devices() {
    local dev ctl vid nome bad=0 total=0 exemplos="" bateria=0 poupados=0
    _doctor_tem_bateria && bateria=1
    for dev in "${HEFESTO_DOCTOR_SYS:-/sys}"/bus/usb/devices/*; do
        [[ -r "${dev}/power/control" && -r "${dev}/idVendor" ]] || continue
        total=$((total + 1))
        ctl="$(cat "${dev}/power/control" 2>/dev/null)"
        if [[ "${ctl}" == "auto" ]]; then
            vid="$(cat "${dev}/idVendor" 2>/dev/null)"
            if [[ "${bateria}" -eq 1 && "${_USB_VENDORES_DE_CONTROLE}" != *" ${vid} "* ]]; then
                poupados=$((poupados + 1))
                continue
            fi
            bad=$((bad + 1))
            nome="$(cat "${dev}/product" 2>/dev/null || true)"
            exemplos+=" $(basename "${dev}") (${vid} ${nome:-?})"
        fi
    done
    if [[ "${total}" -eq 0 ]]; then
        info "sem devices USB legíveis no sysfs — pulo o check de energia dos devices"
    elif [[ "${bad}" -eq 0 && "${poupados}" -gt 0 ]]; then
        pass "nenhum controle USB em economia de energia; ${poupados} outro(s) device(s) em 'auto', de propósito: o computador tem bateria, e o install só mantém acordado o controle"
    elif [[ "${bad}" -eq 0 ]]; then
        pass "nenhum device USB em economia de energia (power/control=on em ${total}/${total})"
    else
        warn "economia de energia ATIVA em ${bad} device(s) USB:${exemplos} — a regra 81 deveria mantê-los 'on': sudo bash scripts/install_udev.sh (e replugue)"
    fi
}

check_usb_power_hosts() {
    local pci cls ctl found=0 bad=""
    if _doctor_tem_bateria; then
        info "hosts USB (xHCI) seguem a economia do kernel, de propósito: o computador tem bateria, e a regra 81-host só liga o host em máquina sem bateria"
        return
    fi
    for pci in "${HEFESTO_DOCTOR_SYS:-/sys}"/bus/pci/devices/*; do
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
    if command -v systemctl >/dev/null 2>&1 \
       && systemctl is-active --quiet com.system76.PowerDaemon.service 2>/dev/null; then
        local prof=""
        command -v system76-power >/dev/null 2>&1 \
            && prof="$(timeout 3 system76-power profile 2>/dev/null | head -1 || true)"
        info "system76-power ativo (${prof:-perfil ilegível}) — o wrapper pede Performance durante o jogo e restaura o perfil ao sair"
    fi
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

check_btusb_autosuspend() {
    local conf="${HEFESTO_DOCTOR_BTUSB_CONF:-}"
    local param="${HEFESTO_DOCTOR_BTUSB_PARAM:-/sys/module/btusb/parameters/enable_autosuspend}" val=""
    [[ -r "${param}" ]] && val="$(cat "${param}" 2>/dev/null)"
    if [[ "${val}" == "N" || "${val}" == "0" ]]; then
        pass "btusb sem autosuspend (enable_autosuspend=N) — o rádio dos controles não dorme"
    elif [[ -z "${conf}" ]] && ! conf="$(_regra_que_o_kmod_le hefesto-btusb-no-autosuspend.conf)"; then
        info "não consegui perguntar ao Hefesto onde o kmod lê o modprobe.d do btusb (enable_autosuspend=${val:-sem o módulo})"
    elif [[ -f "${conf}" && -z "${val}" ]]; then
        info "modprobe.d do btusb instalado; módulo btusb não carregado agora (sem adaptador BT?)"
    elif [[ -f "${conf}" ]]; then
        warn "modprobe.d do btusb instalado, mas o módulo ainda está com enable_autosuspend=${val} — vale no próximo probe (replug do adaptador BT ou reboot); até lá a regra 81 só segura o adaptador de classe e0 em máquina sem bateria"
    elif [[ -z "${val}" ]]; then
        info "módulo btusb não carregado agora (sem adaptador BT?) e sem o conf do hefesto — o adaptador que entrar pode dormir; $(conselho_de_instalacao)$(so_no_checkout "(o conf entra por default)")"
    else
        warn "btusb com autosuspend LIGADO (enable_autosuspend=${val}) e sem o conf do hefesto — em máquina sem usbcore.autosuspend=-1 global o rádio dos controles dorme; $(conselho_de_instalacao)$(so_no_checkout "(o conf entra por default)")"
    fi
}

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
        warn "reconexão rápida BT (FastConnectable) não configurada — $(conselho_de_instalacao)$(so_no_checkout "(entra por default, SEM restart do bluetoothd)")"
    fi
}

check_bluez_justworks_repairing() {
    local dono="${ROOT_DIR}/scripts/bluez_config.sh" valor state
    local etc_bt="${HEFESTO_BT_ETC:-/etc/bluetooth}"
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
            pass "JustWorksRepairing=confirm no main.conf — re-pareamento de quem já tem bond passa pelo agente"
            _t_conf="$(stat -c %Y "${etc_bt}/main.conf" 2>/dev/null || echo 0)"
            _t_bluez="${HEFESTO_BT_ATIVO_DESDE:-}"
            if [[ -z "${_t_bluez}" ]]; then
                _ts_bluez="$(systemctl show bluetooth.service \
                    -p ActiveEnterTimestamp --value 2>/dev/null || true)"
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
                fail "pareamento por rádio PARADO: JustWorksRepairing=confirm só aceita com um agente registrado para confirmar, e o hefesto-bt-agent.service está ${state:-ausente} — sem ele o BlueZ RECUSA o re-pareamento ('Refusing connection from ...') e nenhum controle volta a entrar por Bluetooth. Ligue: sudo systemctl enable --now hefesto-bt-agent.service"
            fi
            ;;
        always)
            fail "JustWorksRepairing=always ATIVO no ${etc_bt}/main.conf — remove a última recusa do BlueZ ao re-pareamento por Just Works de quem já tem bond; com o agente NoInputNoOutput isso termina em injeção de teclas. Cura, em qualquer formato: sudo bash ${dono} aplicar — corrige o bloco antigo do hefesto SEM reiniciar o bluetoothd$(so_no_checkout "— o ./install.sh SEM --no-udev faz o mesmo (a flag pula este passo inteiro)")"
            ;;
        ausente|"")
            warn "JustWorksRepairing não está declarado no main.conf — o BlueZ cai no default da distro, que não é decisão do Hefesto; cura em qualquer formato: sudo bash ${dono} aplicar$(so_no_checkout "— o ./install.sh também aplica, por default, mas NÃO com --no-udev, que pula este passo")"
            ;;
        ilegível)
            warn "não consigo LER ${etc_bt}/main.conf — sem leitura não sei o valor de JustWorksRepairing; rode: sudo bash ${dono} verificar"
            ;;
        recusado)
            fail "${etc_bt}/main.conf tem uma linha que o parser do bluetoothd (GKeyFile) RECUSA, e uma linha recusada invalida o ARQUIVO INTEIRO: o BlueZ fica sem config nenhuma — nem JustWorksRepairing, nem FastConnectable, nem o que já era dela. Veja qual linha é e conserte-a à mão: bash ${dono} verificar"
            ;;
        never)
            warn "JustWorksRepairing=never no main.conf — é MAIS restritivo que o 'confirm' do Hefesto (recusa todo re-pareamento de quem já tem bond). Se foi escolha sua, NÃO deixe o Hefesto reescrever o valor: 'sudo bash ${dono} aplicar' rebaixa para 'confirm'$(so_no_checkout "— e o ./install.sh também"). E confira ONDE a sua linha está: FORA das sentinelas do hefesto ela é neutralizada e o 'bluez_config.sh remover' a devolve inteira; DENTRO do bloco ela é reescrita junto com o bloco e não volta (só o backup guarda)"
            ;;
        *)
            warn "JustWorksRepairing=${valor} no main.conf — o Hefesto instala 'confirm'; se o valor não foi escolha sua, $(conselho_de_instalacao)"
            ;;
    esac
}

_dbus_bt_device_paths() {
    busctl tree org.bluez --list 2>/dev/null \
        | grep -oE '/org/bluez/hci[0-9]+/dev_[0-9A-Fa-f_]+$' | sort -u || true
}
_dbus_bt_prop() {
    busctl get-property org.bluez "$1" "$2" "$3" 2>/dev/null \
        | sed -e 's/^[a-z]* //' -e 's/^"//' -e 's/"$//' || true
}

_bt_adaptadores() {
    local raiz="${HEFESTO_BT_SYSFS_ROOT:-/sys/class/bluetooth}"
    local p nome achou=0 lista
    for p in "${raiz}"/hci*; do
        [[ -e "${p}" ]] || continue
        nome="${p##*/}"
        [[ "${nome}" =~ ^hci[0-9]+$ ]] || continue
        printf '%s\n' "${nome}"
        achou=1
    done
    [[ "${achou}" -eq 1 ]] && return 0
    if command -v busctl >/dev/null 2>&1; then
        lista="$(busctl tree org.bluez --list 2>/dev/null \
            | grep -oE '/org/bluez/hci[0-9]+' | sed 's#.*/##' | sort -u || true)"
        if [[ -n "${lista}" ]]; then
            printf '%s\n' "${lista}"
            return 0
        fi
    fi
    command -v hciconfig >/dev/null 2>&1 || return 0
    hciconfig 2>/dev/null | awk -F: '/^hci/{print $1}' || true
}

OUIS_CLONE=("e4:17:d8")
OUIS_NINTENDO_VISTAS=("e0:f6:b5")
NOMES_PRO=("pro controller")
NOMES_LINHAGEM=("pro controller" "nintendo" "8bitdo")

_bt_e_da_linhagem() {
    local mac="${1,,}" nome="${2,,}" marca
    for marca in "${OUIS_NINTENDO_VISTAS[@]}" "${OUIS_CLONE[@]}"; do
        [[ "${mac}" == "${marca}"* ]] && return 0
    done
    for marca in "${NOMES_LINHAGEM[@]}"; do
        [[ "${nome}" == *"${marca}"* ]] && return 0
    done
    return 1
}

_bt_e_pro_genuino() {
    local mac="${1,,}" nome="${2,,}" marca
    for marca in "${OUIS_CLONE[@]}"; do
        [[ "${mac}" == "${marca}"* ]] && return 1
    done
    for marca in "${OUIS_NINTENDO_VISTAS[@]}"; do
        [[ "${mac}" == "${marca}"* ]] && return 0
    done
    for marca in "${NOMES_PRO[@]}"; do
        [[ "${nome}" == *"${marca}"* ]] && return 0
    done
    return 1
}

_bt_nome_do_controle() {
    local mac="${1^^}" caminho nome
    if command -v busctl >/dev/null 2>&1; then
        caminho="$(busctl tree org.bluez --list 2>/dev/null \
            | grep -oE "/org/bluez/hci[0-9]+/dev_${mac//:/_}$" | head -1 || true)"
        if [[ -n "${caminho}" ]]; then
            nome="$(busctl get-property org.bluez "${caminho}" org.bluez.Device1 Alias 2>/dev/null \
                | sed -E 's/^s "?//; s/"?$//' || true)"
            [[ -n "${nome}" ]] && { printf '%s\n' "${nome}"; return 0; }
        fi
    fi
    sed -n 's/^Name=//p' /var/lib/bluetooth/*/"${mac}"/info 2>/dev/null | head -1 || true
}

_bt_hospeda_linhagem() {
    local alvo="$1" caminho mac nome dir end
    [[ -n "${alvo}" ]] || return 1
    if command -v busctl >/dev/null 2>&1; then
        while IFS= read -r caminho; do
            [[ -n "${caminho}" ]] || continue
            [[ "${caminho}" == "/org/bluez/${alvo}/dev_"* ]] || continue
            mac="${caminho##*/dev_}"; mac="${mac//_/:}"
            nome="$(busctl get-property org.bluez "${caminho}" org.bluez.Device1 Alias 2>/dev/null \
                | sed -E 's/^s "?//; s/"?$//' || true)"
            _bt_e_da_linhagem "${mac}" "${nome}" && return 0
        done <<<"$(busctl tree org.bluez --list 2>/dev/null \
            | grep -oE "/org/bluez/${alvo}/dev_[0-9A-Fa-f_]+$" | sort -u || true)"
    fi
    end="$(cat "/sys/class/bluetooth/${alvo}/address" 2>/dev/null | tr 'a-f' 'A-F' || true)"
    [[ -n "${end}" ]] || return 1
    dir="/var/lib/bluetooth/${end}"
    [[ -d "${dir}" ]] || return 1
    for caminho in "${dir}"/*/info; do
        [[ -e "${caminho}" ]] || continue
        mac="${caminho%/info}"; mac="${mac##*/}"
        nome="$(grep -m1 '^Name=' "${caminho}" 2>/dev/null | cut -d= -f2- || true)"
        _bt_e_da_linhagem "${mac}" "${nome}" && return 0
    done
    return 1
}

_bt_macs_conectados() {
    local p mac saida="" achou=0
    if command -v busctl >/dev/null 2>&1; then
        while IFS= read -r p; do
            [[ -z "${p}" ]] && continue
            [[ "$(_dbus_bt_prop "${p}" org.bluez.Device1 Connected)" == "true" ]] || continue
            mac="${p##*/dev_}"
            printf '%s\n' "${mac//_/:}"
            achou=1
        done <<<"$(_dbus_bt_device_paths)"
        [[ "${achou}" -eq 1 ]] && return 0
    fi
    if command -v btmgmt >/dev/null 2>&1; then
        saida="$(timeout 5 btmgmt con 2>/dev/null \
            | grep -oE '([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}' || true)"
        if [[ -n "${saida}" ]]; then
            printf '%s\n' "${saida^^}"
            return 0
        fi
    fi
    command -v hcitool >/dev/null 2>&1 || return 0
    saida="$(hcitool con 2>/dev/null \
        | grep -oE '([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}' || true)"
    [[ -n "${saida}" ]] && printf '%s\n' "${saida^^}"
    return 0
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
            warn "controle 'tipo DualShock 4' (054C:05C4) pareado (${mac}) — esse firmware não calcula a verificação de integridade e enche o diário do kernel de erros de CRC"
            info "  provavelmente é um 8BitDo em modo DirectInput/PS4, que é o modo RECOMENDADO por rádio — não troque para Switch sem o cabo, que por rádio é instável"
            info "  o barulho fica no diário: 26.884 erros de CRC mediram ZERO frames corrompidos (medido em 04/08/2026)"
            info "  para desparear: bluetoothctl remove ${mac}  (se for um DS4 v1 legítimo, o journal desempata: 'hw_version=0x00000000' = clone)"
        fi
    done <<<"${paths}"
    [[ "${clone}" -eq 0 ]] && pass "nenhum clone DS4 (054C:05C4) pareado"
}

check_bt_rfkill() {
    local raiz="${HEFESTO_BT_SYSFS_ROOT:-/sys/class/bluetooth}"
    local hci rf soft hard lido bloqueados=0 _hcis=() _lidos=() _sem_leitura=()
    mapfile -t _hcis < <(_bt_adaptadores)
    if [[ "${#_hcis[@]}" -eq 0 ]]; then
        info "nenhum adaptador Bluetooth presente — os controles só conectam pelo cabo (o dongle está na porta?)"
        return 0
    fi
    for hci in "${_hcis[@]}"; do
        lido=0
        for rf in "${raiz}/${hci}"/rfkill*; do
            [[ -r "${rf}/soft" && -r "${rf}/hard" ]] || continue
            soft="$(cat "${rf}/soft" 2>/dev/null)"
            hard="$(cat "${rf}/hard" 2>/dev/null)"
            [[ "${soft}" =~ ^[01]$ && "${hard}" =~ ^[01]$ ]] || continue
            lido=1
            if [[ "${hard}" == "1" ]]; then
                bloqueados=$((bloqueados + 1))
                warn "${hci} bloqueado pela chave física ou pela BIOS (rfkill hard) — nenhum controle conecta por ele até a chave voltar"
            elif [[ "${soft}" == "1" ]]; then
                bloqueados=$((bloqueados + 1))
                warn "${hci} desligado por software (rfkill soft) — parece «sem adaptador»: o controle não conecta e nada diz por quê. Ligue pelo botão de Bluetooth do painel ou: rfkill unblock bluetooth"
            fi
        done
        if [[ "${lido}" -eq 1 ]]; then
            _lidos+=("${hci}")
        else
            _sem_leitura+=("${hci}")
        fi
    done
    if [[ "${#_sem_leitura[@]}" -gt 0 ]]; then
        info "não consegui ler o rfkill de ${_sem_leitura[*]} — não sei dizer se esse rádio está bloqueado"
    fi
    if [[ "${#_lidos[@]}" -gt 0 && "${bloqueados}" -eq 0 ]]; then
        pass "rádio Bluetooth ligado em ${#_lidos[@]} adaptador(es) (rfkill sem bloqueio)"
    fi
}

check_bt_radio() {
    command -v busctl >/dev/null 2>&1 || return 0
    local paths p mac alias connected trusted rssi disc gamepad_conectado=0
    local adps_com_controle="" adp
    paths="$(_dbus_bt_device_paths)"
    while IFS= read -r p; do
        [[ -z "${p}" ]] && continue
        mac="${p##*dev_}"; mac="${mac//_/:}"
        alias="$(_dbus_bt_prop "${p}" org.bluez.Device1 Alias)"
        printf '%s' "${alias}" | grep -qiE 'dualsense|wireless controller|pro controller|8bitdo|joy-con|xbox' || continue
        connected="$(_dbus_bt_prop "${p}" org.bluez.Device1 Connected)"
        if [[ "${connected}" == "true" ]]; then
            gamepad_conectado=1
            adps_com_controle+="${p%/*}"$'\n'
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
        if [[ "$(_dbus_bt_prop "${p}" org.bluez.Device1 Paired)" == "true" ]] \
                && ! _dbus_bt_prop "${p}" org.bluez.Device1 UUIDs \
                    | grep -q '00001124-0000-1000-8000-00805f9b34fb'; then
            fail "${alias:-controle} (${mac}) tem bond mas NENHUM perfil HID registrado (SDP vazio) — o BlueZ recusa a reconexão dele como 'unknown device' e o link cai sozinho. Cura (apaga o pareamento): busctl call org.bluez ${p%/*} org.bluez.Adapter1 RemoveDevice o ${p} — e pareie de novo. O próprio RemoveDevice tira o [ServiceRecords] do cache (device.c:5440 do BlueZ 5.86), e sem ele o BlueZ refaz o SDP na conexão seguinte: não há arquivo para apagar à mão (contrato bluez-dbus)"
        fi
    done <<<"${paths}"
    if [[ "${gamepad_conectado}" -eq 1 ]]; then
        while IFS= read -r adp; do
            [[ -z "${adp}" ]] && continue
            disc="$(_dbus_bt_prop "${adp}" org.bluez.Adapter1 Discovering)"
            if [[ "${disc}" == "true" ]]; then
                warn "adaptador ${adp##*/} em modo de busca (Discovering: yes) com controle BT conectado nele — MEDIDO: a busca derruba de 32,5% a 43,4% dos pacotes do controle que está NESTE adaptador (19/09/2026, duas corridas). Feche a tela de Bluetooth do cosmic-settings (a busca é do adaptador em que você ENTROU, não da lista) e espere ~21 s: ela continua varrendo depois de a janela fechar"
            fi
        done <<<"$(printf '%s' "${adps_com_controle}" | sort -u)"
    fi
    local _adp _adps_erro=()
    mapfile -t _adps_erro < <(_bt_adaptadores)
    if [[ "${#_adps_erro[@]}" -eq 0 ]]; then
        info "nenhum adaptador Bluetooth no sistema — sem contadores de rádio para ler"
    elif command -v hciconfig >/dev/null 2>&1; then
        local errs _algum_erro=0 _algum_lido=0
        for _adp in "${_adps_erro[@]}"; do
            errs="$(hciconfig "${_adp}" 2>/dev/null | grep -oE 'errors:[0-9]+' | grep -oE '[0-9]+' | paste -sd/ -)"
            [[ -n "${errs}" ]] && _algum_lido=1
            if [[ -n "${errs}" && "${errs}" != "0/0" ]]; then
                _algum_erro=1
                warn "adaptador ${_adp} com erros acumulados (RX/TX: ${errs}) — rádio sujo; veja as linhas [BT-ERR] no kernel.log e os conselhos de posicionamento acima"
            fi
        done
        errs=""
        [[ "${_algum_lido}" -eq 1 ]] && errs="0/0"
        if [[ "${_algum_erro}" -eq 1 ]]; then
            :
        elif [[ -n "${errs}" ]]; then
            pass "adaptador BT sem erros de RX/TX (0/0)"
        fi
    else
        info "NÃO SEI se o rádio acumulou erros de RX/TX em ${_adps_erro[*]}: esses contadores só saem do 'hciconfig' (ioctl HCIGETDEVINFO), que o BlueZ depreciou e sua distribuição moveu de pacote — instale bluez-deprecated (ou bluez-deprecated-tools) se quiser esta medida de volta. Nem btmgmt nem bluetoothctl a substituem, e as linhas [BT-ERR] do kernel-watch dependem da mesma fonte"
    fi
    local idle
    idle="$(grep -sE '^[[:space:]]*IdleTimeout[[:space:]]*=' /etc/bluetooth/input.conf 2>/dev/null | head -1 | sed 's/.*=[[:space:]]*//')"
    if [[ -n "${idle}" && "${idle}" != "0" ]]; then
        warn "desconexão por ociosidade LIGADA no BlueZ (input.conf IdleTimeout=${idle}) — controles BT vão cair sozinhos; o default 0 (nunca) é o certo: remova a linha de /etc/bluetooth/input.conf"
    else
        pass "sem desconexão por ociosidade no BlueZ (IdleTimeout no default 0)"
    fi
}

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

_o_endereco_do_storm() {
    local log="${1}" dias="${2}"
    local py arquivo raiz_usb
    py="$(_python_do_produto)"
    arquivo="${ROOT_DIR:-}/src/hefesto_dualsense4unix/integrations/exame_da_mesa.py"
    if [[ -z "${py}" || ! -f "${arquivo}" ]]; then
        info "NÃO SEI em qual porta esses -71 aconteceram: o exame_da_mesa.py não está ao alcance deste doctor (instalação por pacote sem o módulo, ou python ausente)"
        return
    fi
    raiz_usb="${HEFESTO_DOCTOR_RAIZ_USB:-/sys/bus/usb/devices}"
    local laudo
    laudo="$("${py}" "${arquivo}" --storm-usb --log "${log}" --dias "${dias}" \
             --raiz-usb "${raiz_usb}" 2>/dev/null | "${py}" -c '
import json
import sys

d = json.load(sys.stdin)
if d.get("porque_nao"):
    print("naosei\t" + str(d["porque_nao"]))
for p in d.get("portas") or []:
    texto = str(p.get("porque") or "").strip()
    if texto:
        print("porta\t" + texto)
    parada = str(p.get("parada") or "").strip()
    if parada:
        marca = "parada_hid" if (p.get("aparelho") or {}).get("hid_sem_driver") else "parada_vazia"
        print(marca + "\t" + str(p.get("entrada") or p.get("porta") or "") + ": " + parada)
for h in d.get("hubs_em_comum") or []:
    texto = str(h.get("porque") or "").strip()
    if texto:
        print("hub\t" + texto)
sobra = int(d.get("sem_endereco") or 0)
if sobra > 0:
    # AUSÊNCIA É RESPOSTA: a soma das portas acima é MENOR que o total contado,
    # e quem lê tem de saber disso. Engolir a diferença deixaria uma forma de
    # linha nova do kernel invisível para sempre.
    print("naosei\t" + str(sobra) + " evento(s) [USB-71] da janela ficaram SEM endereço — o kernel usou uma forma de linha que este doctor ainda não sabe ler; a soma das portas acima é menor que o total")
' 2>/dev/null)"
    if [[ -z "${laudo}" ]]; then
        info "NÃO SEI em qual porta esses -71 aconteceram: o cruzamento com a topologia do /sys não devolveu nada — o módulo não respondeu"
        return
    fi
    local marca texto vigia=""
    while IFS=$'\t' read -r marca texto; do
        [[ -n "${texto}" ]] || continue
        case "${marca}" in
            porta) info "  -71 em ${texto}" ;;
            parada_hid) vigia="${vigia:-${HEFESTO_DOCTOR_VIGIA_DO_REBIND:-$(systemctl is-active hefesto-bt-health-watchdog.timer 2>/dev/null || true)}}"; if [[ "${vigia}" == "active" ]]; then warn "${texto}. O Hefesto tenta religá-lo sozinho a cada 2 minutos, até três vezes; se esta linha continuar, tire e ponha o cabo desse controle, e se ele cair de novo ali, troque de entrada"; else warn "${texto}. A vigia que o religaria sozinha (hefesto-bt-health-watchdog.timer) está ${vigia:-ausente}: tire e ponha o cabo desse controle, e se ele cair de novo ali, troque de entrada; para o Hefesto voltar a religá-lo sozinho, ligue: sudo systemctl enable --now hefesto-bt-health-watchdog.timer"; fi ;;
            parada_vazia) warn "${texto}. Se o controle ou o adaptador BT ainda está encaixado nela, tire e ponha: o kernel só volta a olhar essa entrada quando algo é encaixado de novo" ;;
            hub) warn "${texto}. É o suspeito a trocar primeiro: tire um dos aparelhos desse hub e ligue direto numa entrada do computador, ou troque o hub (de preferência um com fonte própria)" ;;
            naosei) info "${texto}" ;;
        esac
    done <<<"${laudo}"
}

check_kernel_watch() {
    local unit="hefesto-dualsense4unix-storm-watch.service"
    if command -v systemctl >/dev/null 2>&1; then
        if systemctl --user is-active --quiet "${unit}" 2>/dev/null; then
            pass "kernel-watch ativo (${unit})"
        elif systemctl --user cat "${unit}" >/dev/null 2>&1; then
            warn "kernel-watch instalado mas parado — ligue: systemctl --user enable --now ${unit}"
        else
            warn "kernel-watch não instalado — $(conselho_de_instalacao)$(so_no_checkout "(entra por default; --no-kernel-watch é o opt-out)")"
        fi
    fi
    local log="${HOME}/.local/state/hefesto-dualsense4unix/kernel.log"
    [[ -f "${log}" ]] || log="${HOME}/.local/state/hefesto-dualsense4unix/storm.log"
    if [[ ! -f "${log}" ]]; then
        info "sem log do kernel-watch ainda (nasce no primeiro start/evento)"
        return
    fi
    local dias_da_janela="${HEFESTO_DOCTOR_JANELA_DIAS:-7}"
    local corte
    corte="$(date -d "${dias_da_janela} days ago" +%Y-%m-%d 2>/dev/null || echo 0000-00-00)"

    _quantos_desde() {
        awk -v tag="[$1]" -v corte="$2" \
            'index($0, tag) && substr($0,1,10) >= corte { n++ } END { print n+0 }' \
            "${log}" 2>/dev/null || echo 0
    }
    _quando_o_ultimo() {
        grep -F "[$1]" "${log}" 2>/dev/null | tail -1 |
            awk '{ d=substr($0,1,10); if (d ~ /^[0-9]{4}-/) printf "%s/%s", substr(d,9,2), substr(d,6,2) }'
    }
    _relata() {
        if [[ "${3:-0}" -gt 0 ]]; then
            warn "$5 — ${3} vez(es) nos últimos ${dias_da_janela} dias (a última em ${4:-?}); ${2} no log inteiro"
        elif [[ "${2:-0}" -gt 0 ]]; then
            info "[$1] não aconteceu nos últimos ${dias_da_janela} dias. O log guarda ${2} do passado, a última em ${4:-?} — histórico, não o estado de agora"
        fi
    }

    _ocorrencias_no_log() {
        awk -v tag="[$1]" '
            index($0, tag) {
                if (match($0, / (repetiu|segue) \+[0-9]+ \(/)) {
                    s = substr($0, RSTART, RLENGTH); gsub(/[^0-9]/, "", s); n += s
                } else n++
            }
            END { print n + 0 }' "${log}" 2>/dev/null || echo 0
    }
    local tag n resumo="" n_joycon=0 n_joycon_probe=0 n_usb71=0 n_bterr=0
    for tag in USB-71 JOYCON JOYCON-PROBE BT-HCI XHCI BT-ERR; do
        n="$(_ocorrencias_no_log "${tag}")"; n="${n:-0}"
        resumo+=" ${tag}=${n}"
        case "${tag}" in
            JOYCON) n_joycon="${n}" ;;
            JOYCON-PROBE) n_joycon_probe="${n}" ;;
            USB-71) n_usb71="${n}" ;;
            BT-ERR) n_bterr="${n}" ;;
        esac
    done
    info "kernel-watch (${log##*/}), o log INTEIRO desde $(head -1 "${log}" 2>/dev/null | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}' | head -1):${resumo}"

    _relata JOYCON "${n_joycon}" "$(_quantos_desde JOYCON "${corte}")" \
        "$(_quando_o_ultimo JOYCON)" \
        "o kernel deu rate-limit no controle Nintendo/8BitDo [JOYCON] — é a morte do 8BitDo em Bluetooth (muro do hid-nintendo); a configuração estável é NO CABO. O patch DKMS do hid-nintendo (ver seção abaixo) reduz a chance do link cair, mas não elimina a degradação de rádio"
    _relata JOYCON-PROBE "${n_joycon_probe}" "$(_quantos_desde JOYCON-PROBE "${corte}")" \
        "$(_quando_o_ultimo JOYCON-PROBE)" \
        "o hid-nintendo falhou no PROBE [JOYCON-PROBE] — morte 'invisível' (o device nem chega a registrar; sem cascata [JOYCON]); ver a seção DKMS hid-nintendo abaixo"
    local recentes_usb71
    recentes_usb71="$(_quantos_desde USB-71 "${corte}")"
    _relata USB-71 "${n_usb71}" "${recentes_usb71}" \
        "$(_quando_o_ultimo USB-71)" \
        "storm USB (-71) registrado no kernel-watch [USB-71] — a ENTRADA e o CONTROLE de cada um saem logo abaixo; as alavancas (quirk, regra 75) estão na seção USB/dropout"
    if [[ "${recentes_usb71:-0}" -gt 0 ]]; then
        _o_endereco_do_storm "${log}" "${dias_da_janela}"
    fi
    _relata BT-ERR "${n_bterr}" "$(_quantos_desde BT-ERR "${corte}")" \
        "$(_quando_o_ultimo BT-ERR)" \
        "o rádio BT acumulou erros [BT-ERR] — rádio sujo; ver os conselhos de posicionamento acima"
    local n_semcontador
    n_semcontador="$(grep -cF '[BT-SEM-CONTADOR]' "${log}" 2>/dev/null || true)"
    if [[ "${n_semcontador:-0}" -gt 0 ]]; then
        info "o kernel-watch NÃO está medindo os erros do rádio ([BT-SEM-CONTADOR]) — o 'hciconfig' foi depreciado pelo BlueZ e não está aqui, e nenhuma ferramenta viva devolve esses contadores. Não leia 'BT-ERR=0' acima como rádio limpo: é ausência de medida, não medida de ausência. Para recuperá-la, instale bluez-deprecated (ou bluez-deprecated-tools)"
    fi
}

check_familias_do_radio() {
    local log="${HOME}/.local/state/hefesto-dualsense4unix/kernel.log"
    local dias="${HEFESTO_DOCTOR_JANELA_DIAS:-7}" corte py saida
    [[ -f "${log}" ]] || return 0
    corte="$(date -d "${dias} days ago" +%Y-%m-%d 2>/dev/null || echo 0000-00-00)"
    py="$(_python_do_produto)"
    [[ -n "${py}" ]] || { info "sem python para ler as famílias do rádio no kernel-watch"; return; }
    saida="$(HEFESTO_SRC="${ROOT_DIR}/src" "${py}" - "${log}" "${corte}" <<'PY' 2>/dev/null
import os
import sys

src = os.environ.get("HEFESTO_SRC", "")
if src and os.path.isdir(src):
    sys.path.insert(0, src)
try:
    from hefesto_dualsense4unix.integrations.storm_doctor import (
        FAMILIAS_DO_RADIO,
        classificar_o_historico,
    )
except Exception:  # noqa: BLE001
    print("sem-produto")
    raise SystemExit(0)
with open(sys.argv[1], encoding="utf-8", errors="ignore") as fh:
    linhas = fh.read().splitlines()
tudo = classificar_o_historico(linhas)
janela = classificar_o_historico(
    [linha for linha in linhas if linha.startswith("#") or linha[:10] >= sys.argv[2]]
)
for tag, (familia, nome) in FAMILIAS_DO_RADIO.items():
    if familia == "1":
        continue
    conta = tudo.get(familia)
    if conta is None:
        print(f"naoolhei\t{tag}\t{nome}")
        continue
    recente = janela.get(familia)
    dia = conta.ultima[:10]
    quando = f"{dia[8:10]}/{dia[5:7]}" if len(dia) == 10 else "?"
    print(
        f"familia\t{tag}\t{nome}\t{conta.rajadas}\t{recente.rajadas if recente else 0}\t{quando}"
    )
PY
)" || saida=""
    if [[ -z "${saida}" || "${saida}" == "sem-produto" ]]; then
        info "NÃO SEI ler as famílias do rádio no kernel-watch: o storm_doctor não está ao alcance do python ${py}"
        return
    fi
    local marca tag nome total recentes quando cura naoolhei=()
    while IFS=$'\t' read -r marca tag nome total recentes quando; do
        if [[ "${marca}" == "naoolhei" ]]; then
            naoolhei+=("${nome} ${tag}")
            continue
        fi
        case "${tag}" in
            "[BT-SOCKET]") cura="É o que derruba os controles por Bluetooth: o bluetoothd com o hefesto-0002 (o backport do passo 3f) segura a sessão" ;;
            "[FILA-CHEIA]") cura="A fila de saída de um controle encheu: o uhid com contrapressão segura$(so_no_checkout "(./install.sh --uhid-contrapressao)")" ;;
            "[ENLACE-PARADO]") cura="O enlace de um controle parou de andar: distância ou interferência — aproxime o controle do adaptador" ;;
            "[BT-TRAVADO]") cura="Um adaptador travou: o watchdog o reinicia sozinho, até três vezes seguidas; se não voltar, tire e ponha o adaptador" ;;
            "[CRC]") cura="Pacotes corrompidos: interferência de 2.4 GHz — afaste o adaptador dos receivers e do Wi-Fi USB" ;;
            *) cura="" ;;
        esac
        if [[ "${recentes:-0}" -gt 0 ]]; then
            warn "rádio: ${nome} ${tag} — ${recentes} vez(es) nos últimos ${dias} dias (a última em ${quando}); ${total} no log inteiro. ${cura}"
        elif [[ "${total:-0}" -gt 0 ]]; then
            info "rádio: ${nome} ${tag} não aconteceu nos últimos ${dias} dias. O log guarda ${total}, a última em ${quando} — histórico, não o estado de agora"
        fi
    done <<<"${saida}"
    if [[ "${#naoolhei[@]}" -gt 0 ]]; then
        local lista
        lista="$(printf '%s, ' "${naoolhei[@]}")"
        info "o kernel-watch deste log ainda não procurava: ${lista%, } — zero aqui é «não olhei»; a vigia nova, que o install reinicia, passa a procurar"
    fi
}

check_cmdline_platform() {
    local owners="${HOME}/.local/state/hefesto-dualsense4unix/cmdline-owners.conf"
    local tok ativo agendado bateria=0 lido backend seguintes
    local cmdline="${HEFESTO_DOCTOR_CMDLINE:-/proc/cmdline}" kcmd="${HEFESTO_DOCTOR_KERNEL_CMDLINE:-/etc/kernel/cmdline}"
    local kstub="${HEFESTO_DOCTOR_KERNELSTUB:-/etc/kernelstub/configuration}" grub="${HEFESTO_DOCTOR_GRUB:-/etc/default/grub}"
    _doctor_tem_bateria && bateria=1
    lido="$(python3 -I "${ROOT_DIR}/src/hefesto_dualsense4unix/integrations/kernel_cmdline.py" ler --kernelstub-conf "${kstub}" --grub-conf "${grub}" --kernel-cmdline "${kcmd}" 2>/dev/null || true)"
    backend="$(sed -n 's/^backend=//p' <<<"${lido}")"; seguintes="$(sed -n 's/^tokens=//p' <<<"${lido}")"
    if [[ -z "${lido}" ]]; then seguintes="$(cat "${kstub}" "${grub}" "${kcmd}" 2>/dev/null || true)"; fi
    for tok in "usbcore.autosuspend=-1" "054c:0ce6:gn"; do
        ativo=0; agendado=0; [[ "${seguintes}" == *"${tok}"* ]] && agendado=1
        grep -qF "${tok}" "${cmdline}" 2>/dev/null && ativo=1
        if [[ "${ativo}" -eq 1 ]]; then
            pass "cmdline: ${tok} APLICADO neste boot"
        elif [[ "${tok}" == "usbcore.autosuspend=-1" && "${bateria}" -eq 1 ]]; then
            info "cmdline: ${tok} fica de fora, de propósito: o computador tem bateria, e ele desligaria a economia de todo aparelho USB"
        elif [[ "${agendado}" -eq 1 ]]; then
            warn "cmdline: ${tok} agendado mas NÃO ativo — pendente de reboot"
        elif [[ "${backend}" == "none" ]]; then info "cmdline: ${tok} ausente, e o carregador de boot daqui não é kernelstub, grub nem /etc/kernel/cmdline: ponha à mão no cmdline do kernel ${tok/#054c/usbcore.quirks=054c}"
        else
            warn "cmdline: ${tok} ausente — $(conselho_de_instalacao)$(so_no_checkout "(o passo 3e aplica com MERGE no token único e registro de dono)")"
        fi
    done
    local n_tokens
    n_tokens="$(grep -o 'usbcore\.quirks=' "${cmdline}" 2>/dev/null | wc -l || true)"
    if [[ "${n_tokens:-0}" -gt 1 ]]; then
        warn "MAIS DE UM token usbcore.quirks= no cmdline (${n_tokens}) — o kernel respeita só um; $(conselho_de_instalacao)$(so_no_checkout "(o passo 3e funde num token único)")"
    fi
    if [[ -f "${owners}" ]]; then
        info "donos registrados: $(tr '\n' ' ' < "${owners}")"
    fi
}

readonly _BZ_PISO="5.79"
readonly _BZ_TETO="5.87"

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

_bluez_binario_vivo() {
    local caminho
    caminho="$(systemctl show bluetooth.service -p ExecStart --value 2>/dev/null \
        | grep -oE 'path=[^ ]+' | head -1 | cut -d= -f2)"
    [[ -n "${caminho}" && -x "${caminho}" ]] || return 1
    printf '%s\n' "${caminho}"
}

_bluez_versao_do_daemon_vivo() {
    local caminho
    caminho="$(_bluez_binario_vivo)" || return 1
    "${caminho}" --version 2>/dev/null | tr -d '[:space:]'
}

check_bluez_curas_do_backport() {
    local vivo baseline="${HEFESTO_DOCTOR_BLUEZ_BASELINE:-${ROOT_DIR}/assets/bluez-backport/BASELINE}"
    local nome marca faltam=() tem=()
    vivo="${HEFESTO_DOCTOR_BLUETOOTHD:-$(_bluez_binario_vivo || true)}"
    if [[ ! -r "${baseline}" ]]; then
        info "não sei conferir as curas do backport do BlueZ nesta instalação (sem o assets/bluez-backport/BASELINE)"
        return
    fi
    if [[ -z "${vivo}" || ! -r "${vivo}" ]]; then
        info "não achei o bluetoothd que o systemd executa — pulo a conferência das curas do backport"
        return
    fi
    while IFS=$'\t' read -r nome marca; do
        [[ -n "${marca}" ]] || continue
        if grep -a -q -F -- "${marca}" "${vivo}" 2>/dev/null; then
            tem+=("${nome}")
        else
            faltam+=("${nome}")
        fi
    done < <(sed -n 's/^MARCA_\([^=]*\)=\(.*\)$/\1\t\2/p' "${baseline}" 2>/dev/null)
    if [[ "${#faltam[@]}" -eq 0 && "${#tem[@]}" -gt 0 ]]; then
        pass "o bluetoothd em execução traz as curas do backport do Hefesto (${tem[*]})"
    elif [[ "${#faltam[@]}" -gt 0 ]] \
         && ! command -v "${HEFESTO_DOCTOR_DPKG:-dpkg}" >/dev/null 2>&1; then
        warn "o bluetoothd em execução (${vivo}) não traz ${faltam[*]} — com três ou mais controles pelo rádio, a sessão cai no EAGAIN (o rádio cheio derruba os controles por Bluetooth). O backport do Hefesto é .deb e esta distro não tem dpkg: os patches estão em assets/bluez-backport/patches, para o BlueZ da sua distro"
    elif [[ "${#faltam[@]}" -gt 0 ]]; then
        warn "o bluetoothd em execução (${vivo}) não traz ${faltam[*]} — sem o hefesto-0002, o rádio cheio (EAGAIN) derruba a sessão dos controles por Bluetooth: $(conselho_de_instalacao)$(so_no_checkout "(o passo 3f instala o backport que estiver no cache; sem ele: scripts/construir_bluez_backport.sh)")"
    else
        info "não sei conferir as curas do backport do BlueZ: ${baseline} não traz nenhuma linha MARCA_"
    fi
}

_bluez_linha_do_changelog() {
    local rotulo="$1" texto
    local arquivo="${HEFESTO_DOCTOR_BLUEZ_CHANGELOG:-/usr/share/doc/bluez/changelog.Debian.gz}"
    [[ -r "${arquivo}" ]] || return 1
    if [[ "${arquivo}" == *.gz ]]; then
        texto="$(zcat "${arquivo}" 2>/dev/null || true)"
    else
        texto="$(cat "${arquivo}" 2>/dev/null || true)"
    fi
    awk -v r="${rotulo}: " '
        /^ -- / { exit }
        { i = index($0, r); if (i) { print substr($0, i + length(r)); exit } }
        ' <<<"${texto}" | sed 's/[[:space:]]*$//' | grep . || return 1
}

_bluez_a_casa_leva_o_5bc6aa79() {
    local ver="$1" pacote leva
    command -v dpkg-query >/dev/null 2>&1 || return 1
    pacote="$(dpkg-query -W -f='${Version}' bluez 2>/dev/null || true)"
    [[ "${pacote}" == *~hefesto* && "${pacote%%-*}" == "${ver%%-*}" ]] || return 1
    leva="$(_bluez_linha_do_changelog "Leva do upstream" || true)"
    [[ " ${leva} " == *" 5bc6aa79"* ]]
}

_bluez_base_do_backport() {
    local log base="" achou
    local logs=("${HEFESTO_DOCTOR_DPKG_LOG:-/var/log/dpkg.log}")
    if [[ -z "${HEFESTO_DOCTOR_DPKG_LOG:-}" ]]; then
        local extra
        for extra in /var/log/dpkg.log.*; do
            [[ -f "${extra}" ]] && logs+=("${extra}")
        done
    fi
    for log in $(printf '%s\n' "${logs[@]}" | sort -V); do
        [[ -r "${log}" ]] || continue
        if [[ "${log}" == *.gz ]]; then
            achou="$(zcat "${log}" 2>/dev/null | grep -E ' (upgrade|install) bluez:[^ ]+ [^ ~]+ [^ ]*~hefesto' | tail -1 || true)"
        else
            achou="$(grep -E ' (upgrade|install) bluez:[^ ]+ [^ ~]+ [^ ]*~hefesto' "${log}" 2>/dev/null | tail -1 || true)"
        fi
        if [[ -n "${achou}" ]]; then
            base="$(awk '{print $5}' <<<"${achou}")"
            break
        fi
    done
    [[ -n "${base}" && "${base}" != "<none>" ]] && printf '%s\n' "${base}"
}

_bluez_candidata_da_distro() {
    command -v apt-cache >/dev/null 2>&1 || return 1
    local versao="" melhor="" v
    local texto
    texto="$(LC_ALL=C apt-cache policy bluez 2>/dev/null)" || return 1
    while IFS= read -r v; do
        [[ -n "${v}" ]] || continue
        if [[ -z "${melhor}" ]] || dpkg --compare-versions "${v}" gt "${melhor}" 2>/dev/null; then
            melhor="${v}"
        fi
    done < <(awk '
        /^[ *]+[0-9][^ ]* +[0-9]+$/ { sub(/^[ *]+/, ""); vlinha = $1; next }
        /^ +[0-9]+ +[^ ]/ { if (vlinha != "" && $2 != "/var/lib/dpkg/status" && vlinha !~ /~hefesto/) print vlinha; next }
        ' <<<"${texto}")
    [[ -n "${melhor}" ]] && printf '%s\n' "${melhor}"
}

check_bluez_distro_depois_do_backport() {
    local pacote candidata base
    command -v dpkg-query >/dev/null 2>&1 || return 0
    pacote="$(dpkg-query -W -f='${Version}' bluez 2>/dev/null || true)"
    [[ "${pacote}" == *~hefesto* ]] || return 0
    candidata="$(_bluez_candidata_da_distro || true)"
    [[ -n "${candidata}" ]] || return 0
    base="$(_bluez_linha_do_changelog "Cobre a segurança da distro até" || true)"
    [[ -n "${base}" ]] || base="$(_bluez_base_do_backport || true)"
    if [[ -z "${base}" ]]; then
        info "o bluez ${pacote} é o backport do Hefesto, e não achei de que versão da distro ele nasceu (o dpkg.log não a guarda): a distro publica o bluez ${candidata}, que o apt não aplica por cima do backport"
        return 0
    fi
    if dpkg --compare-versions "${candidata}" gt "${base}" 2>/dev/null; then
        warn "a distro publicou o bluez ${candidata} depois do backport, que cobre a segurança dela até o ${base}; o apt não aplica a correção dela por cima do ${pacote}. A receita do backport precisa de uma revisão nova que leve a correção da distro$(so_no_checkout "(docs/usage/receita-backport-bluez.md)")"
    else
        pass "o backport do bluez (${pacote}) está em dia com a distro (a candidata dela, ${candidata}, não passa da base ${base})"
    fi
}

_PW_COM_A_CURA="1.6.9"
_pw_versao_do_upstream() {
    local v="${1#*:}"
    printf '%s' "${v%%-*}"
}
_pw_gesto_da_cura() {
    if [[ "$1" == "dpkg" ]]; then
        so_no_checkout "(./install.sh, passo 3f-bis, ou a receita: docs/usage/receita-backport-pipewire.md)"
        return 0
    fi
    case "$(_dono_do_arquivo "$(command -v pipewire)")" in
        fedora) printf ' (a cura vem da distro, que já entrega a 1.6.9: sudo dnf upgrade)' ;;
        arch) printf ' (a cura vem da distro, que já entrega a 1.6.9: sudo pacman -Syu)' ;;
        *) printf ' (a cura vem da distro: atualize o PipeWire para a 1.6.9 ou mais nova)' ;;
    esac
}
check_pipewire_cura_do_metadata() {
    local pw wp up linha_wp fonte="dpkg"
    if command -v dpkg-query >/dev/null 2>&1; then
        pw="$(dpkg-query -W -f='${Version}' libpipewire-0.3-modules 2>/dev/null || true)"
        wp="$(dpkg-query -W -f='${Version}' wireplumber 2>/dev/null || true)"
    fi
    if [[ -z "${pw:-}" ]] && command -v pipewire >/dev/null 2>&1; then
        fonte="fora"
        pw="$(pipewire --version 2>/dev/null | sed -n 's/^Linked with libpipewire \([0-9][0-9.]*\).*/\1/p' | head -n1)"
    fi
    if [[ -z "${pw:-}" ]]; then
        info "não achei o PipeWire (nem o pacote, nem o binário) — pulo a conferência da cura do metadata"
        return 0
    fi
    up="$(_pw_versao_do_upstream "${pw}")"
    if [[ -z "${wp:-}" ]]; then
        linha_wp="o WirePlumber não está no dpkg"
    elif [[ "${wp}" == *~hefesto* ]]; then
        linha_wp="o WirePlumber é o ${wp}, o da casa"
    else
        linha_wp="o WirePlumber é o ${wp}, o da distro"
    fi
    if [[ "$(printf '%s\n%s\n' "${_PW_COM_A_CURA}" "${up}" | sort -V | head -n1)" == "${_PW_COM_A_CURA}" ]]; then
        pass "o PipeWire ${pw} tem a cura do metadata (>= ${_PW_COM_A_CURA}, issue #5445); ${linha_wp}"
    else
        warn "o PipeWire ${pw} não tem a cura do metadata (chegou na ${_PW_COM_A_CURA}, issue #5445): depois de um reinício do WirePlumber, um cliente como o \`wpctl\` que a Steam roda pode ficar preso, e a Steam não fecha. ${linha_wp^}$(_pw_gesto_da_cura "${fonte}")"
    fi
}

check_bluez_backport_version() {
    if ! command -v dpkg >/dev/null 2>&1; then
        info "dpkg ausente (sistema não-Debian?) — pulo o check de versão do bluez"
        return
    fi
    local ver veredito origem
    ver="$(_bluez_versao_do_daemon_vivo || true)"
    if [[ -n "${ver}" ]]; then
        origem=" (daemon em execução)"
    elif command -v dpkg-query >/dev/null 2>&1; then
        ver="$(dpkg-query -W -f='${Version}' bluez 2>/dev/null || true)"
        origem=" (pacote dpkg — daemon parado)"
    else
        origem=""
    fi
    veredito="$(_bluez_version_verdict "${ver}")"
    case "${veredito}" in
        ok)
            pass "bluez ${ver}${origem} >= ${_BZ_PISO} e < ${_BZ_TETO} (sem os crashes crônicos de input/HIDP do 5.72, e sem o UAF do 5.87)"
            ;;
        nova)
            if _bluez_a_casa_leva_o_5bc6aa79 "${ver}"; then
                pass "bluez ${ver}${origem} é o backport do Hefesto, que leva a correção 5bc6aa79 do uso-depois-de-liberado do 5.87 (a linha «Leva do upstream» do changelog dele)"
            else
                warn "bluez ${ver}${origem} >= ${_BZ_TETO} — o 5.87 carrega um uso-depois-de-liberado em dev_disconnected (src/adapter.c: device_is_connected() chamado depois de adapter_remove_connection() liberar o device; commit 5d836f1). A correção 5bc6aa79 está um commit DEPOIS do 5.87 e nenhum lançamento a carregava até 07/08/2026 — se esta versão é o 5.88 ou mais nova, confira se ela já traz o 5bc6aa79 e suba o teto (_BZ_TETO) no doctor.sh. O backport do Hefesto é o 5.87 com o 5bc6aa79$(so_no_checkout "(./install.sh, passo 3f)")."
            fi
            ;;
        old)
            warn "bluez ${ver}${origem} < 5.79 — com controles pelo rádio o bluetoothd pode cair (crashes de input/HIDP, heap corruption, 6x em 5 dias medidos no 5.72); o cabo não depende disso. O backport do Hefesto é a opção para quem usa o rádio: $(conselho_de_instalacao)$(so_no_checkout "(o passo 3f aplica sozinho se os .debs estiverem em ~/.cache/hefesto-dualsense4unix/bluez-backport/; senão, gere-os com scripts/construir_bluez_backport.sh, pela receita em docs/usage/receita-backport-bluez.md)")"
            ;;
        *)
            info "bluez não encontrado (nem daemon em execução, nem pacote) — pulo o check de versão"
            ;;
    esac
    check_bluez_distro_depois_do_backport
}

check_bt_agent_service() {
    command -v systemctl >/dev/null 2>&1 || { info "systemctl ausente — não checo o agente de pareamento"; return; }
    local state
    state="$(systemctl is-active hefesto-bt-agent.service 2>/dev/null || true)"
    if [[ "${state}" == "active" ]]; then
        pass "hefesto-bt-agent.service ativo — pareamento fora da GUI/daemon tem agente D-Bus para responder"
    elif systemctl cat hefesto-bt-agent.service >/dev/null 2>&1; then
        warn "hefesto-bt-agent.service instalado mas ${state:-inativo} — bond meio-salvo à espreita (Paired sem Bonded); ligue: sudo systemctl enable --now hefesto-bt-agent.service"
    else
        warn "hefesto-bt-agent.service não instalado — pareamento fora da GUI/daemon pode ficar meio-salvo (Paired sem Bonded, 'No agent available for request type 2'); $(conselho_de_instalacao)$(so_no_checkout "(o passo 3g aplica por default)")"
    fi
}

check_trava_do_radio() {
    local conf="${HEFESTO_DOCTOR_TRAVA_CONF:-/etc/tmpfiles.d/hefesto-dualsense4unix-radio.conf}"
    local pasta="${HEFESTO_DOCTOR_TRAVA_DIR:-/run/hefesto-dualsense4unix}"
    local motores="${HEFESTO_DOCTOR_TRAVA_MOTORES:-/etc/systemd/system/hefesto-bt-health-watchdog.timer:/etc/systemd/system/bluetooth.service.d/10-hefesto-resilience.conf}"
    local trava="${pasta}/radio.lock"
    local modo grupo um com_motor=0 _motores_da_trava=()
    if [[ ! -f "${conf}" ]]; then
        IFS=: read -r -a _motores_da_trava <<<"${motores}"
        for um in ${_motores_da_trava[@]+"${_motores_da_trava[@]}"}; do
            [[ -n "${um}" && -e "${um}" ]] && com_motor=1
        done
        if [[ "${com_motor}" -eq 0 ]]; then
            info "sem a trava comum do rádio, e sem motor root que a dispute (o watchdog do Bluetooth e o modo ativo no start do bluetoothd não estão instalados): o daemon põe os próprios motores em fila pela trava da sessão"
            return
        fi
        warn "a trava comum do rádio não está instalada — o watchdog do Bluetooth (root) e o daemon mexem no rádio sem se enxergar: $(conselho_de_instalacao)$(so_no_checkout "(o passo 3e-trava a cria)")"
        return
    fi
    if [[ ! -d "${pasta}" ]]; then
        warn "a trava comum do rádio está instalada mas ${pasta} não existe — ela nasce no boot; para agora: sudo systemd-tmpfiles --create ${conf}"
        return
    fi
    if [[ -w "${pasta}" ]]; then
        fail "${pasta} é GRAVÁVEL pela sua sessão — o root abre a trava ali, e uma pasta gravável deixaria trocá-la por um link; corrija: sudo systemd-tmpfiles --create ${conf}"
        return
    fi
    if [[ -L "${trava}" || ! -f "${trava}" ]]; then
        warn "a trava ${trava} falta (ou é um link) — sudo systemd-tmpfiles --create ${conf}"
        return
    fi
    read -r modo grupo <<<"$(stat -c '%a %G' "${trava}" 2>/dev/null || echo '? ?')"
    if [[ "${modo}" != "660" || "${grupo}" != "hefesto" ]]; then
        warn "a trava ${trava} está ${modo}, grupo ${grupo} (o certo é 660, grupo hefesto) — sudo systemd-tmpfiles --create ${conf}"
        return
    fi
    if [[ -w "${trava}" ]]; then
        pass "trava comum do rádio de pé (${trava}, 660, grupo hefesto) — o watchdog e o daemon disputam o mesmo arquivo"
    else
        warn "a trava comum do rádio está de pé, mas esta sessão ainda não está no grupo hefesto — o daemon a usa só para ler (a fila funciona) até você sair e entrar na sessão"
    fi
}

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
        warn "resiliência do bluetoothd não instalada (crash do bluetoothd destrói bonds sem backup): $(conselho_de_instalacao "" "/usr/share/hefesto-dualsense4unix/scripts/install-host-udev.sh" "— atenção: ele traz os alvos das regras 82/83, mas NÃO os timers")$(so_no_checkout "— em QUALQUER formato, inclusive --flatpak/--appimage/--deb")"
    fi
    if [[ ! -f /etc/systemd/system/bluetooth.service.d/10-hefesto-resilience.conf ]]; then
        warn "drop-in 10-hefesto-resilience.conf ausente — sem o desarme do watchdog do systemd (que matava o bluetoothd) e sem snapshot na parada do serviço"
    fi
    local _hci _lp _alias _mac _pro_mac _pro_lp _hcis=()
    mapfile -t _hcis < <(_bt_adaptadores)
    for _hci in "${_hcis[@]}"; do
    if [[ -n "${_hci}" ]] && _bt_hospeda_linhagem "${_hci}"; then
        _alias="$(busctl get-property org.bluez "/org/bluez/${_hci}" org.bluez.Adapter1 Alias 2>/dev/null | sed -E 's/^s "?//; s/"?$//' || true)"
        if command -v hciconfig >/dev/null 2>&1; then
            _lp="$(hciconfig "${_hci}" lp 2>/dev/null | grep -o 'SNIFF' || true)"
        else
            _lp="?"
        fi
        _pro_lp="ausente"
        _pro_mac=""
        while IFS= read -r _mac; do
            [[ -n "${_mac}" ]] || continue
            _bt_e_pro_genuino "${_mac}" "$(_bt_nome_do_controle "${_mac}")" || continue
            _pro_mac="${_mac}"
            if ! command -v hcitool >/dev/null 2>&1; then
                _pro_lp="?"
                break
            fi
            if hcitool lp "${_mac}" 2>/dev/null | grep -q 'SNIFF'; then
                _pro_lp="SNIFF"
                break
            fi
            _pro_lp="sem-sniff"
        done <<<"$(_bt_macs_conectados)"
        if [[ "${_lp}" == "?" || "${_pro_lp}" == "?" ]]; then
            if [[ "${_alias}" == Nintendo* ]]; then
                warn "modo ativo p/ Nintendo pela METADE do que dá para conferir: o nome do adaptador está certo ('${_alias}'), mas NÃO SEI dizer o estado do SNIFF (nem do adaptador, nem do Pro genuíno) — a link policy só sai de 'hciconfig lp'/'hcitool lp', que o BlueZ depreciou e não estão nesta máquina, e a mgmt API (btmgmt/bluetoothctl) não a expõe. Instale bluez-deprecated (ou bluez-deprecated-tools) para esta conferência voltar"
            else
                warn "modo ativo p/ Nintendo incompleto (alias='${_alias:-?}') e SEM COMO conferir o SNIFF nesta máquina (hciconfig/hcitool depreciados e ausentes; btmgmt/bluetoothctl não leem link policy) — reaplique: sudo /usr/local/lib/hefesto-dualsense4unix/bt_active_mode.sh"
            fi
        elif [[ -n "${_lp}" && "${_alias}" == Nintendo* ]]; then
            if [[ "${_pro_lp}" == "SNIFF" ]]; then
                warn "modo ativo p/ Nintendo: alias e SNIFF do adaptador OK, mas o Pro genuíno conectado está COM sniff (deveria ser sem). Reaplique: sudo /usr/local/lib/hefesto-dualsense4unix/bt_active_mode.sh"
            else
                pass "modo ativo p/ Nintendo (nome '${_alias}' + SNIFF no adaptador p/ o 8BitDo probar + no-sniff só no Pro genuíno)"
            fi
        else
            warn "modo ativo p/ Nintendo incompleto (alias='${_alias:-?}', SNIFF-adaptador=${_lp:-AUSENTE}); o adaptador deve MANTER o SNIFF (o 8BitDo precisa) — reaplique: sudo /usr/local/lib/hefesto-dualsense4unix/bt_active_mode.sh"
        fi
    fi
    done
}

_bt_caches_orfaos() {
    awk -F/ '
        NF < 3 { next }
        $NF == "info"      { bond[$(NF-2) "/" $(NF-1)] = 1; next }
        $(NF-1) == "cache" { sdp[$(NF-2) "/" $NF] = 1 }
        END { n = 0; for (k in sdp) if (!(k in bond)) n++; print n }
    '
}

check_bt_bonds_persistidos() {
    if ! sudo -n true 2>/dev/null; then
        info "sem sudo sem senha — não leio /var/lib/bluetooth (confira à mão: sudo find /var/lib/bluetooth -name info)"
        return
    fi
    local n_info n_cache n_orfaos
    n_info="$(sudo -n find /var/lib/bluetooth -mindepth 3 -maxdepth 3 -type f -name info 2>/dev/null | wc -l)"
    n_cache="$(sudo -n find /var/lib/bluetooth -mindepth 3 -maxdepth 3 -type f -path '*/cache/*' 2>/dev/null | wc -l)"
    n_orfaos="$( { sudo -n find /var/lib/bluetooth -mindepth 3 -maxdepth 3 -type f -name info
                   sudo -n find /var/lib/bluetooth -mindepth 3 -maxdepth 3 -type f -path '*/cache/*' \
                        -exec grep -l '^\[ServiceRecords\]' {} +
                 } 2>/dev/null | _bt_caches_orfaos )"
    if [[ "${n_info}" -gt 0 ]]; then
        pass "bonds BT persistidos em disco: ${n_info} (cache com ${n_cache} devices vistos)"
    elif [[ "${n_orfaos:-0}" -gt 0 ]]; then
        fail "ZERO bonds em disco e ${n_orfaos} aparelho(s) com registro de serviço no cache — pareamentos vivendo só em memória (evaporam no disconnect) ou destruídos por crash; re-pareie com Pair() explícito (bluetoothctl pair <MAC>) e confira Bonded: yes; se houver snapshot: sudo /usr/local/lib/hefesto-dualsense4unix/bt_bonds_restore.sh --list"
    elif [[ "${n_cache}" -gt 0 ]]; then
        info "nenhum controle pareado agora — os ${n_cache} do cache são só nomes vistos em buscas; pareamento removido pelo sistema não deixa bond nem registro de serviço, e isso é escolha, não perda"
    else
        info "nenhum bond nem cache em /var/lib/bluetooth — adaptador nunca pareou nada (ou árvore em outro lugar)"
    fi
}

check_bt_sdp_cache_envenenado() {
    if ! sudo -n true 2>/dev/null; then
        info "sem sudo sem senha — não leio o cache SDP (confira: sudo grep -L ServiceRecords /var/lib/bluetooth/*/cache/*)"
        return
    fi
    local achou=0 mac
    local -r _sem_service_records='for i in /var/lib/bluetooth/*/*/info; do
        grep -qi "^Services=.*00001124-0000-1000-8000-00805f9b34fb" "$i" || continue
        d=${i%/info}; m=${d##*/}; c=${d%/*}/cache/$m
        [ -f "$c" ] || continue; grep -q "^\[ServiceRecords\]" "$c" || echo "$m"
    done'
    while IFS= read -r mac; do
        [[ -z "${mac}" ]] && continue
        achou=1
        local _como_distinguir
        if command -v sdptool >/dev/null 2>&1; then
            _como_distinguir="Primeiro confira QUAL das duas causas é: 'sudo sdptool browse ${mac}' — se responder em <1 s, é só a direção da conexão e o watchdog cura sozinho no próximo tick (Connect() pelo host, sem desparear); se ESTOURAR o timeout, o stack do controle travou e nem re-parear resolve: reset de hardware do controle (furinho atrás, ~5 s com um clipe)"
        else
            _como_distinguir="NÃO DÁ para distinguir as duas causas nesta máquina: o browse SDP sob demanda só existia no 'sdptool', que o BlueZ depreciou e não está instalado aqui (pacote bluez-deprecated / bluez-deprecated-tools), e btmgmt/bluetoothctl não o substituem. Faça o barato primeiro: o watchdog tenta Connect() a cada 2 min — se em dois ticks o [ServiceRecords] não aparecer, trate como stack do controle travado (nem re-parear resolve): reset de hardware do controle (furinho atrás, ~5 s com um clipe)"
        fi
        fail "cache SDP de ${mac} SEM [ServiceRecords] — o perfil HID não sobe (controle 'Conectado' e sem input). ${_como_distinguir}"
    done < <(sudo -n sh -c "${_sem_service_records}" 2>/dev/null)
    [[ "${achou}" -eq 0 ]] && pass "cache SDP íntegro em todos os controles com bond (todos têm [ServiceRecords])"
}

_mac_norm() {
    local m="${1,,}"
    printf '%s\n' "${m//:/}"
}

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
    if [[ -n "${bonded}" ]]; then
        printf '\tBonded: %s\n' "$([[ "${bonded}" == "true" ]] && echo yes || echo no)"
    fi
}

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

_bond_dobrado_por_controle() {
    local paths p mac hci
    paths="$(_dbus_bt_device_paths)"
    [[ -z "${paths}" ]] && return 0
    while IFS= read -r p; do
        [[ -z "${p}" ]] && continue
        [[ "$(_dbus_bt_prop "${p}" org.bluez.Device1 Paired)" == "true" ]] || continue
        hci="${p#/org/bluez/}"; hci="${hci%%/*}"
        mac="${p##*/dev_}"; mac="${mac//_/:}"
        [[ -z "${mac}" || -z "${hci}" ]] && continue
        printf '%s\t%s\n' "${mac}" "${hci}"
    done <<<"${paths}" | sort -u | awk -F'\t' '
        { onde[$1] = onde[$1] " " $2; n[$1]++ }
        END { for (m in n) if (n[m] > 1) print m onde[m] }
    '
}

check_bond_dobrado() {
    command -v busctl >/dev/null 2>&1 || { info "busctl ausente — pulo o check de bond dobrado"; return; }
    local linha mac adps achou=0
    while IFS= read -r linha; do
        [[ -z "${linha}" ]] && continue
        achou=1
        mac="${linha%% *}"
        adps="${linha#* }"
        warn "o controle ${mac} tem chave de pareamento em MAIS DE UM adaptador (${adps# }) — migração feita pela metade: o bond do adaptador de ORIGEM ficou. Na reconexão o adaptador errado pode ganhar a corrida, e a conta de ocupação do rádio soma o mesmo controle duas vezes. O Hefesto esquece a sobra sozinho assim que o controle conectar pelo rádio (a chave que ele usar é a que fica). Para não esperar, apague a do adaptador que sai (os dois endereços vão pelo stdin, e o registro do sudo fica sem eles): printf '%s\n%s\n' <adaptador-que-sai> ${mac} | sudo /usr/local/lib/hefesto-dualsense4unix/bt_ponte_privilegiada.sh esquecer"
    done < <(_bond_dobrado_por_controle)
    [[ "${achou}" -eq 0 ]] && pass "nenhum controle com bond em mais de um adaptador"
}

check_exame_da_mesa() {
    local py arquivo
    py="$(_python_do_produto)"
    arquivo="${ROOT_DIR}/src/hefesto_dualsense4unix/integrations/exame_da_mesa.py"
    if [[ -z "${py}" || ! -f "${arquivo}" ]]; then
        return
    fi
    local resumo
    resumo="$("${py}" "${arquivo}" --censo 2>/dev/null | "${py}" -c '
import json
import sys

d = json.load(sys.stdin)
itens = d.get("itens") or []
print("veredito=" + str(d.get("veredito") or ""))
for i in itens:
    estado = str(i.get("estado") or "")
    if estado == "certo":
        continue
    rotulo = str(i.get("rotulo") or "").strip()
    porque = str(i.get("porque") or "").strip()
    # O RÓTULO FICA NA FRENTE quando ele acrescenta — ele nomeia a CLASSE do
    # achado. Quando o `porque` está vazio (nunca visto, mas o dono permite),
    # o rótulo sozinho ainda é melhor que uma linha muda.
    texto = (rotulo + ": " + porque) if (rotulo and porque) else (porque or rotulo)
    if texto:
        print("item\t" + estado + "\t" + texto)
' 2>/dev/null)"
    if [[ -z "${resumo}" ]]; then
        info "exame da mesa indisponível — rode: ${py} ${arquivo} --relatorio"
        return
    fi
    local veredito
    veredito="$(sed -n 's/^veredito=//p' <<<"${resumo}")"

    local achou_algum=0
    while IFS=$'\t' read -r marca estado texto; do
        [[ "${marca}" == "item" ]] || continue
        [[ -n "${texto}" ]] || continue
        achou_algum=1
        case "${estado}" in
            problema)
                fail "exame da mesa: ${texto} (aba Conexões, seção Check-up)" ;;
            atencao)  # (noqa-acento)
                warn "exame da mesa: ${texto} (aba Conexões, seção Check-up)" ;;
            *)
                info "exame da mesa: ${texto} (aba Conexões, seção Check-up)" ;;
        esac
    done <<<"${resumo}"

    if [[ "${achou_algum}" -eq 0 ]]; then
        if [[ "${veredito}" == "certo" ]]; then
            pass "exame da mesa: as conferências da aba Conexões passaram"
        else
            info "exame da mesa: nem tudo deu para conferir sem senha"
        fi
    fi
}

check_proton_pin() {
    local py="${ROOT_DIR}/src/hefesto_dualsense4unix/integrations/proton_pin.py"
    local conf="${ROOT_DIR}/assets/proton-pin.conf"
    if [[ ! -f "${py}" || ! -f "${conf}" ]] || ! command -v python3 >/dev/null 2>&1; then
        info "proton_pin.py/proton-pin.conf ausentes ou sem python3 — pulo o check do Proton pinado"
        return
    fi
    local envenenada
    envenenada="$(HEFESTO_PP="${py}" python3 - <<'PY' 2>/dev/null
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(os.environ.get("HEFESTO_PP", "")).parent))
try:
    import proton_pin as pp
except Exception:  # noqa: BLE001
    sys.exit(0)
alvo = getattr(pp, "raiz_envenenada", lambda: None)()
if alvo is not None:
    print(alvo)
PY
)"
    if [[ -n "${envenenada}" ]]; then
        fail "${envenenada} é uma pasta que um instalador antigo do Hefesto criou antes de existir Steam aqui (só tem o Proton pinado dentro): com ela no caminho, a Steam adota ${HOME}/.steam como casa e o Hefesto deixa de achá-la. Com a Steam FECHADA, rode: mv \"${envenenada}\" \"${envenenada}.sobra-do-hefesto\" — na próxima abertura a Steam recria o atalho, e o vigia da Steam reextrai o Proton pinado do cache"
        return
    fi
    if [[ ! -f "${HOME}/.steam/steam/config/config.vdf" \
          && ! -f "${HOME}/.local/share/Steam/config/config.vdf" \
          && ! -f "${HOME}/.var/app/com.valvesoftware.Steam/.steam/steam/config/config.vdf" \
          && ! -f "${HOME}/snap/steam/common/.steam/steam/config/config.vdf" ]]; then
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
print("offids=" + " ".join(str(a) for a in off))
leaky = d.get("games_leaky_proton") or []
print("leaky=" + " ".join(f"{a}:{t}" for a, t in leaky))
' 2>/dev/null)"
    if [[ -z "${resumo}" ]]; then
        warn "relatório do Proton pinado indisponível — rode: python3 ${py} --report"
        return
    fi
    local nome present manifest glob off offids leaky
    nome="$(sed -n 's/^name=//p' <<<"${resumo}")"
    present="$(sed -n 's/^present=//p' <<<"${resumo}")"
    manifest="$(sed -n 's/^manifest=//p' <<<"${resumo}")"
    glob="$(sed -n 's/^global=//p' <<<"${resumo}")"
    off="$(sed -n 's/^off=//p' <<<"${resumo}")"
    offids="$(sed -n 's/^offids=//p' <<<"${resumo}")"
    leaky="$(sed -n 's/^leaky=//p' <<<"${resumo}")"

    local detalhe
    detalhe="$(HEFESTO_PP="${py}" HEFESTO_CONF="${conf}" HEFESTO_OFF="${offids}" \
        python3 - <<'PY' 2>/dev/null
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(os.environ.get("HEFESTO_PP", "")).parent))
try:
    import proton_pin as pp
except Exception:  # noqa: BLE001
    sys.exit(0)
try:
    conf = pp.parse_pin_conf(
        Path(os.environ["HEFESTO_CONF"]).read_text(encoding="utf-8")
    )
except (OSError, ValueError, KeyError):
    sys.exit(0)

raiz = pp.default_compat_dir() / conf["name"]
print("compat=" + str(raiz))

alvo = raiz / pp.MANIFEST_BASENAME
if not alvo.is_file():
    estado = "ausente"
else:
    try:
        sha = json.loads(alvo.read_text(encoding="utf-8")).get("sha256")
    except (OSError, ValueError):
        sha = None
    if not isinstance(sha, str):
        estado = "corrompido"
    elif sha.lower() == conf["sha256"].lower():
        estado = "ok"
    else:
        estado = "divergente"
print("manifesto=" + estado)

try:
    registro = json.loads(
        pp.default_lock_state_path().read_text(encoding="utf-8")
    ).get("changes") or {}
except (OSError, ValueError, AttributeError):
    registro = {}
try:
    from steam_launch_options import rotulo_do_jogo
except Exception:  # noqa: BLE001
    def rotulo_do_jogo(appid, home=None):
        return f"appid {appid}"

try:
    nomeados = set(pp.ler_jogos_fora_do_pino())
    arquivo = pp.fora_do_pino_path()
except AttributeError:
    nomeados, arquivo = set(), None
try:
    mapa = pp.extract_compat_tool_mapping(
        pp.default_config_vdf().read_text(encoding="utf-8")
    )
except (OSError, ValueError):
    mapa = {}
da_familia = getattr(pp, "e_da_familia_proton", lambda n: "proton" in n.lower())
nomeado, nativo, fora = [], [], []
for appid in (os.environ.get("HEFESTO_OFF") or "").split():
    atual = mapa.get(appid) or mapa.get("0") or (
        (registro.get(appid) or {}).get("previous_name") or "?"
    )
    if appid in nomeados:
        nomeado.append(rotulo_do_jogo(appid))
    elif atual != "?" and not da_familia(atual):
        nativo.append(f"{rotulo_do_jogo(appid)} em {atual}")
    else:
        fora.append(f"{rotulo_do_jogo(appid)} em {atual}")
print("nomeados=" + "; ".join(nomeado))
print("nativos=" + "; ".join(nativo))
print("fora=" + "; ".join(fora))
if nomeado and arquivo is not None:
    import time

    try:
        quando = time.strftime("%d/%m/%Y", time.localtime(arquivo.stat().st_mtime))
    except OSError:
        quando = "?"
    print(f"arquivo_nomeados={arquivo} (alterado em {quando})")
PY
)"
    local raiz_do_pin manifesto nomeados nativos fora arquivo_nomeados
    raiz_do_pin="$(sed -n 's/^compat=//p' <<<"${detalhe}")"
    manifesto="$(sed -n 's/^manifesto=//p' <<<"${detalhe}")"
    nomeados="$(sed -n 's/^nomeados=//p' <<<"${detalhe}")"
    nativos="$(sed -n 's/^nativos=//p' <<<"${detalhe}")"
    fora="$(sed -n 's/^fora=//p' <<<"${detalhe}")"
    arquivo_nomeados="$(sed -n 's/^arquivo_nomeados=//p' <<<"${detalhe}")"

    if [[ "${present}" == "1" && "${manifest}" == "1" ]]; then
        pass "Proton pinado presente e íntegro (${nome})"
    elif [[ "${present}" == "1" && "${manifesto}" == "divergente" ]]; then
        warn "Proton pinado presente (${nome}) e o manifesto do hefesto aponta OUTRO sha256 — $(conselho_de_instalacao)$(so_no_checkout "(re-extrai do cache e re-verifica o SHA256)")"
    elif [[ "${present}" == "1" && "${manifesto}" == "ausente" ]]; then
        info "Proton pinado presente (${nome}), instalado por FORA do hefesto (ProtonUp ou à mão): mantemos de propósito o que você instalou, e por isso NÃO dá para conferir aqui o SHA256 do release — rodar o instalador de novo não muda isto. Para ficar com a cópia que nós verificamos, tire ${raiz_do_pin:-o diretório dele} do caminho e $(conselho_de_instalacao)"
    elif [[ "${present}" == "1" && "${manifesto}" == "corrompido" ]]; then
        warn "Proton pinado presente (${nome}) e o manifesto do hefesto está ilegível — o instalador trata isso como 'sem manifesto' e MANTÉM o diretório, então rodá-lo de novo não muda nada. Para refazer verificado, tire ${raiz_do_pin:-o diretório dele} do caminho e $(conselho_de_instalacao)"
    elif [[ "${present}" == "1" ]]; then
        warn "Proton pinado presente (${nome}) mas não consegui ler o manifesto do hefesto — rode: python3 ${py} --report"
    else
        warn "Proton pinado AUSENTE (${nome}) — $(conselho_de_instalacao)$(so_no_checkout "(baixa, verifica o SHA256 e extrai por default)")"
    fi
    if [[ "${glob}" == "1" && "${off:-0}" -eq 0 ]]; then
        pass "todos os jogos travados no Proton pinado (default global + por jogo)"
    else
        [[ "${glob}" != "1" ]] && warn "default global da Steam NÃO aponta pro Proton pinado — $(_gesto_da_trava_do_pino "${present}"); ou, para refazer tudo, $(conselho_de_instalacao)"
        [[ -n "${nomeados}" ]] && info "fora do Proton pinado por exceção que você nomeou em ${arquivo_nomeados:-jogos_fora_do_pino.txt}: ${nomeados} — o install, o vigia da Steam e o botão não tocam nestes; para devolver um: python3 ${py} --de-volta-ao-pino APPID"
        [[ -n "${nativos}" ]] && info "rodando por uma ferramenta que não é Proton, a escolha de rodar nativo, que o produto não troca: ${nativos} — o pino existe por causa do Wine, e estes não passam por ele"
        [[ -n "${fora}" ]] && warn "jogo(s) fora do Proton pinado, em outro Proton: ${fora} — a ordem de 17/09/2026 é todo jogo que roda por Proton no pino, e um upgrade de Proton pode trazer de volta o controle duplicado neles; $(_gesto_da_trava_do_pino "${present}"). Para deixar um de fora: python3 ${py} --fora-do-pino APPID"
        if [[ "${off:-0}" -gt 0 && -z "${nomeados}" && -z "${nativos}" && -z "${fora}" ]]; then
            warn "${off} jogo(s) fora do Proton pinado — um upgrade de Proton pode reintroduzir o controle duplicado nesses jogos; $(_gesto_da_trava_do_pino "${present}")"
        fi
    fi
    if [[ -n "${leaky}" ]]; then
        warn "jogo(s) em Proton <= 9: ${leaky} — nessa família o PROTON_DISABLE_HIDRAW não existe e o controle físico VAZA duplicado no jogo; trave no Proton pinado"
    fi
}

_nos_de_entrada_do_hidraw() {
    local no="$1" base hid alvo
    base="$(basename "${no}")"
    hid="$(readlink -f "/sys/class/hidraw/${base}/device" 2>/dev/null || true)"
    [[ -n "${hid}" && -d "${hid}" ]] || return 0
    for alvo in "${hid}"/input/input*/event* "${hid}"/input/input*/js*; do
        [[ -e "${alvo}" ]] || continue
        basename "${alvo}"
    done
}

_entradas_devolvidas_pelo_nativo() {
    command -v python3 >/dev/null 2>&1 || return 0
    local no
    for no in $(_entradas_expostas_no_broker "$1"); do
        _nos_de_entrada_do_hidraw "${no}"
    done
}

_entradas_expostas_no_broker() {
    python3 - "$1" <<'PYEOF' 2>/dev/null || true
import json
import socket
import sys

s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.settimeout(2.0)
try:
    s.connect(sys.argv[1])
    s.sendall(b'{"cmd": "status"}\n')
    buf = b""
    while not buf.endswith(b"\n"):
        pedaco = s.recv(65536)
        if not pedaco:
            break
        buf += pedaco
    resposta = json.loads(buf.decode("utf-8"))
    print(" ".join(str(no) for no in resposta.get("entradas_expostas") or []))
except (OSError, ValueError, AttributeError):
    pass
PYEOF
}

_entrada_alcancavel_pelo_jogo() {
    local no="$1" modo grupo_no g
    [[ -e "${no}" ]] || return 1
    modo="$(stat -c '%04a' "${no}" 2>/dev/null || true)"
    [[ -n "${modo}" ]] || return 1
    case "${modo: -1}" in
        [4567]) return 0 ;;
    esac
    if command -v getfacl >/dev/null 2>&1 \
       && getfacl -p "${no}" 2>/dev/null | grep -E '^user:[^:]+:r' | grep -vq '#effective:-'; then
        return 0
    fi
    case "${modo: -2:1}" in
        [4567])
            grupo_no="$(stat -c '%G' "${no}" 2>/dev/null || true)"
            if [[ -n "${grupo_no}" ]]; then
                for g in $(id -nG 2>/dev/null); do
                    [[ "${g}" == "${grupo_no}" ]] && return 0
                done
            fi
            ;;
    esac
    return 1
}

_tres_superficies_medir() {
    TRES_SUP_CONTROLES=0
    TRES_SUP_ESCONDIDOS=0
    TRES_SUP_ABERTOS=""
    TRES_SUP_N_ABERTOS=0
    TRES_SUP_SEM_MAPA=0
    local no base entradas aberto_deste
    for no in "$@"; do
        [[ -n "${no}" ]] || continue
        TRES_SUP_CONTROLES=$((TRES_SUP_CONTROLES + 1))
        entradas="$(_nos_de_entrada_do_hidraw "${no}")"
        if [[ -z "${entradas}" ]]; then
            TRES_SUP_SEM_MAPA=$((TRES_SUP_SEM_MAPA + 1))
            continue
        fi
        aberto_deste=0
        for base in ${entradas}; do
            if _entrada_alcancavel_pelo_jogo "/dev/input/${base}"; then
                aberto_deste=1
                TRES_SUP_ABERTOS="${TRES_SUP_ABERTOS} ${base}"
                TRES_SUP_N_ABERTOS=$((TRES_SUP_N_ABERTOS + 1))
            fi
        done
        [[ "${aberto_deste}" -eq 0 ]] && TRES_SUP_ESCONDIDOS=$((TRES_SUP_ESCONDIDOS + 1))
    done
    TRES_SUP_ABERTOS="${TRES_SUP_ABERTOS# }"
}

_censo_de_fisicos() {
    local py; py="$(_python_do_produto)"
    [[ -n "${py}" ]] || return 0
    HEFESTO_SRC="${ROOT_DIR}/src" "${py}" - <<'PY' 2>/dev/null || true
import os
import sys

sys.path.insert(0, os.environ.get("HEFESTO_SRC", ""))
try:
    from hefesto_dualsense4unix.broker.hidraw_broker import physical_nodes_exposure
except Exception:  # noqa: BLE001
    sys.exit(0)
print(" ".join(sorted(physical_nodes_exposure(os.getuid()))), end="")
PY
}

_veredito_do_hide() {
    local hidden_count="$1" daemon_vivo="$2" native_mode="$3" censo="$4"
    shift 4
    if [[ "${hidden_count}" -le 0 ]]; then
        info "broker sem nós escondidos no momento (emulação desligada ou nenhum grab ativo)"
        return
    fi
    if [[ "${daemon_vivo}" != "1" ]]; then
        fail "broker com ${hidden_count} nó(s) escondido(s) e o daemon PARADO — invariante quebrada (belts falharam); cura: sudo systemctl restart hefesto-hidraw-broker.service"
        return
    fi
    if [[ "${native_mode}" == "True" ]]; then
        warn "broker com ${hidden_count} nó(s) escondido(s) em Modo Nativo — o físico deveria estar exposto ao jogo"
        return
    fi
    local _fisico _escondido _visto fora=""
    for _fisico in ${censo}; do
        _visto=0
        for _escondido in "$@"; do
            [[ "${_escondido}" == "${_fisico}" ]] && { _visto=1; break; }
        done
        [[ "${_visto}" -eq 0 ]] && fora="${fora} ${_fisico}"
    done
    fora="${fora# }"
    if [[ -n "${fora}" ]]; then
        warn "o hide não cobre a mesa inteira: ${hidden_count} nó(s) escondido(s), mas o censo do produto vê DualSense físico FORA do hide (${fora}) — o jogo enxerga esse(s) controle(s) direto, e quem enumerar /dev/input ou hidraw acha o controle dobrado; este check NÃO afirma que o jogo só vê o vpad"
        info "  confira se a emulação está ligada para ele na aba Emulação; se estiver, o broker não pegou o nó: sudo systemctl restart hefesto-hidraw-broker.service"
        return
    fi
    local contados="${hidden_count}" _do_censo sobra=""
    local -a no_censo=()
    if [[ -n "${censo}" ]]; then
        for _escondido in "$@"; do
            _visto=0
            for _do_censo in ${censo}; do
                [[ "${_do_censo}" == "${_escondido}" ]] && { _visto=1; break; }
            done
            if [[ "${_visto}" -eq 1 ]]; then
                no_censo+=("${_escondido}")
            else
                sobra="${sobra} ${_escondido}"
            fi
        done
        sobra="${sobra# }"
        contados="${#no_censo[@]}"
        [[ -n "${sobra}" ]] && info "fora deste veredito: ${sobra} — o broker ainda conta esse(s) nome(s) como escondido(s), e o censo não o(s) reconhece hoje como DualSense físico"
        set -- "${no_censo[@]}"
    fi
    _tres_superficies_medir "$@"
    if [[ "${TRES_SUP_CONTROLES}" -eq 0 || "${TRES_SUP_SEM_MAPA}" -eq "${TRES_SUP_CONTROLES}" ]]; then
        pass "broker escondendo ${contados} nó(s) hidraw físico(s) (giroscópio sobrevive via fd-injection)"
        info "as superfícies evdev/joydev desses nós não estão legíveis no sysfs agora — este check NÃO afirma que o jogo só vê o vpad"
        return
    fi
    [[ "${TRES_SUP_SEM_MAPA}" -gt 0 ]] && info "${TRES_SUP_SEM_MAPA} nó(s) escondido(s) sem mapa no sysfs — ficaram fora do veredito abaixo"
    if [[ -n "${TRES_SUP_ABERTOS}" ]]; then
        warn "o hide não fechou os nós de entrada: ${TRES_SUP_ESCONDIDOS} de ${TRES_SUP_CONTROLES} controle(s) escondido(s) do jogo — o FÍSICO segue alcançável em ${TRES_SUP_N_ABERTOS} nó(s) de entrada (${TRES_SUP_ABERTOS}), e quem enumerar /dev/input em vez de hidraw acha o controle dobrado. O broker fecha os quatro junto com o hidraw desde 24/09/2026; se ele não fechou, o que roda é o de antes da cura (veja o check do broker em memória acima). Reinicie sem abrir o físico: ${GESTO_DE_REINICIAR_O_BROKER}"
        return
    fi
    local medidos=$((TRES_SUP_CONTROLES - TRES_SUP_SEM_MAPA))
    if [[ "${TRES_SUP_SEM_MAPA}" -gt 0 ]]; then
        pass "broker escondendo ${contados} nó(s) físico(s), e as TRÊS superfícies dos ${medidos} controle(s) MEDIDO(S) fechadas (hidraw + evdev + joydev). NÃO afirmo nada sobre ${TRES_SUP_SEM_MAPA} outro(s), que o sysfs não soube mapear (giroscópio sobrevive via fd-injection)"
        return
    fi
    pass "broker escondendo ${contados} nó(s) físico(s), e as TRÊS superfícies dos ${medidos} controle(s) fechadas (hidraw + evdev + joydev) — o jogo só vê o vpad (giroscópio sobrevive via fd-injection)"
}

GESTO_DE_REINICIAR_O_BROKER="sudo touch /run/hefesto-hidraw-broker/reinicio-sem-abrir && sudo systemctl kill -s SIGKILL hefesto-hidraw-broker.service && sudo systemctl restart hefesto-hidraw-broker.service"

_veredito_do_broker_em_memoria() {
    local inicio="$1" instalado="$2" recarregar="$3"
    if [[ "${recarregar}" == "yes" ]]; then
        warn "a unit do broker mudou no disco e o systemd ainda segue a de antes — rode: sudo systemctl daemon-reload && ${GESTO_DE_REINICIAR_O_BROKER}"
    fi
    if [[ -z "${inicio}" || -z "${instalado}" ]]; then
        return
    fi
    if (( instalado > inicio )); then
        warn "o broker em memória é de antes do binário instalado (subiu em $(date -d "@${inicio}" '+%d/%m %H:%M'), o binário é de $(date -d "@${instalado}" '+%d/%m %H:%M')) — o código novo só vale depois de reiniciar, e este reinício não abre o físico: ${GESTO_DE_REINICIAR_O_BROKER}"
        return
    fi
    pass "o broker em memória é o binário instalado (subiu depois dele)"
}

_veredito_do_open_de_entrada() {
    local resultado="$1" detalhe="$2"
    case "${resultado}" in
        ok)
            pass "cmd open serviu o nó de ENTRADA do físico (${detalhe}) — o gamepad, o touchpad e o giroscópio chegam ao daemon com os nós fechados"
            ;;
        velho)
            warn "o broker em memória não conhece os nós de entrada (recusou ${detalhe} como caminho) — é o de antes de 24/09/2026 (quando o broker passou a fechar os nós de entrada junto com o hidraw), e com a regra 72 nova o daemon fica sem o gamepad, o touchpad e o giroscópio do físico até ele reiniciar: ${GESTO_DE_REINICIAR_O_BROKER}"
            ;;
        fail)
            fail "cmd open do nó de ENTRADA falhou (${detalhe}) — o daemon fica sem o gamepad, o touchpad e o giroscópio do físico; confira DeviceAllow=char-input rw em /etc/systemd/system/hefesto-hidraw-broker.service e rode: sudo systemctl daemon-reload && ${GESTO_DE_REINICIAR_O_BROKER}"
            ;;
        *)
            ;;
    esac
}

_medir_o_broker_em_memoria() {
    local pid idade inicio="" instalado recarregar
    pid="$(systemctl show -p MainPID --value hefesto-hidraw-broker.service 2>/dev/null || true)"
    if [[ "${pid}" =~ ^[0-9]+$ && "${pid}" -gt 0 ]]; then
        idade="$(ps -o etimes= -p "${pid}" 2>/dev/null | tr -d ' ' || true)"
        if [[ "${idade}" =~ ^[0-9]+$ ]]; then
            inicio=$(( $(date +%s) - idade ))
        fi
    fi
    instalado="$(stat -c %Y /usr/local/lib/hefesto-dualsense4unix/hefesto-hidraw-broker 2>/dev/null || true)"
    recarregar="$(systemctl show -p NeedDaemonReload --value hefesto-hidraw-broker.service 2>/dev/null || true)"
    _veredito_do_broker_em_memoria "${inicio}" "${instalado}" "${recarregar}"
}

check_hidraw_broker() {
    command -v systemctl >/dev/null 2>&1 || { info "systemctl ausente — não checo o broker hide-hidraw"; return; }
    if ! systemctl cat hefesto-hidraw-broker.socket >/dev/null 2>&1; then
        info "broker hide-hidraw não instalado ($(conselho_de_instalacao)$(so_no_checkout "— o broker vem por default, sem flag"))"
        return
    fi
    local sock_state
    sock_state="$(systemctl is-active hefesto-hidraw-broker.socket 2>/dev/null || true)"
    if [[ "${sock_state}" != "active" ]]; then
        warn "hefesto-hidraw-broker.socket instalado mas ${sock_state:-inativo} — o físico NÃO é escondido do jogo (P2 duplicado volta); ligue: sudo systemctl enable --now hefesto-hidraw-broker.socket"
        return
    fi
    pass "hefesto-hidraw-broker.socket ativo"
    _medir_o_broker_em_memoria

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
print("hidden_nodes=" + " ".join(hidden))

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
            os.close(fd)
        except OSError:
            pass
    if resp.get("ok") and fds:
        resultado = "ok"
        detalhe = node
        break
    erro = resp.get("error") or ""
    if erro == "reject_not_physical_dualsense":
        continue
    resultado = "fail"
    detalhe = f"{node} erro={erro} errno={resp.get('errno')}"
    break
print(f"open={resultado}")
print(f"open_detalhe={detalhe}")

resultado_e = "skip"
detalhe_e = ""
for classe in sorted(glob.glob("/sys/class/input/event*")):
    try:
        with open(classe + "/device/id/vendor", encoding="ascii") as fh:
            vendor = fh.read().strip().lower()
        with open(classe + "/device/id/product", encoding="ascii") as fh:
            produto = fh.read().strip().lower()
    except OSError:
        continue
    if vendor != "054c" or produto not in ("0ce6", "0df2"):
        continue
    node = "/dev/input/" + os.path.basename(classe)
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
            os.close(fd)
        except OSError:
            pass
    if resp.get("ok") and fds:
        resultado_e = "ok"
        detalhe_e = node
        break
    erro = resp.get("error") or ""
    if erro == "reject_not_physical_dualsense":
        continue
    if erro == "reject_bad_path":
        resultado_e = "velho"
        detalhe_e = node
        break
    resultado_e = "fail"
    detalhe_e = f"{node} erro={erro} errno={resp.get('errno')}"
    break
print(f"open_entrada={resultado_e}")
print(f"open_entrada_detalhe={detalhe_e}")
PYEOF
)"; then
        warn "broker não respondeu no socket (/run/hefesto-hidraw-broker/broker.sock) — verifique: systemctl status hefesto-hidraw-broker.service"
        return
    fi

    local ok peer_uid hidden_count hidden_nodes
    ok="$(sed -n 's/^ok=//p' <<<"${ping_out}")"
    peer_uid="$(sed -n 's/^peer_uid=//p' <<<"${ping_out}")"
    hidden_count="$(sed -n 's/^hidden_count=//p' <<<"${ping_out}")"
    hidden_count="${hidden_count:-0}"
    hidden_nodes="$(sed -n 's/^hidden_nodes=//p' <<<"${ping_out}")"

    if [[ "${ok}" != "True" ]]; then
        warn "broker recusou o ping (autorização por SO_PEERCRED/uid falhou)"
        return
    fi
    if [[ "${peer_uid}" != "$(id -u)" ]]; then
        warn "broker ecoou peer_uid=${peer_uid}, esperado $(id -u) — SO_PEERCRED inconsistente"
    else
        pass "ping ok — peer_uid=${peer_uid} confere (SO_PEERCRED)"
    fi

    local open_res open_det
    open_res="$(sed -n 's/^open=//p' <<<"${ping_out}")"
    open_det="$(sed -n 's/^open_detalhe=//p' <<<"${ping_out}")"
    case "${open_res}" in
        ok)
            pass "cmd open serviu fd real via SCM_RIGHTS (${open_det}) — fd-injection do giroscópio operante"
            info "porta: broker (SCM_RIGHTS) via /run/hefesto-hidraw-broker/broker.sock — nenhum open() direto de /dev/hidraw* neste diagnóstico"
            ;;
        fail)
            fail "cmd open do broker FALHOU (${open_det}) — o giroscópio morre sob o hide; confira DeviceAllow=char-hidraw rw e CapabilityBoundingSet (CAP_DAC_OVERRIDE) em /etc/systemd/system/hefesto-hidraw-broker.service e rode: sudo systemctl restart hefesto-hidraw-broker.service"
            ;;
        *)
            info "cmd open não testado (nenhum hidraw físico de DualSense visível agora)"
            ;;
    esac
    _veredito_do_open_de_entrada \
        "$(sed -n 's/^open_entrada=//p' <<<"${ping_out}")" \
        "$(sed -n 's/^open_entrada_detalhe=//p' <<<"${ping_out}")"

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

    local daemon_vivo=0
    [[ -S "${sock}" ]] && daemon_vivo=1
    local censo_fisicos
    censo_fisicos="$(_censo_de_fisicos)"
    # shellcheck disable=SC2086
    _veredito_do_hide "${hidden_count}" "${daemon_vivo}" "${native_mode}" "${censo_fisicos}" ${hidden_nodes}

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

_veredito_de_quem_segura_o_fisico() {
    local proc="$1" censo="$2" nativo="$3"
    if [[ -z "${censo}" ]]; then
        info "nenhum DualSense físico no censo agora — sem nó para conferir quem segura"
        return 0
    fi
    local dir alvo pid cmd nome chave
    local -A visto=() por_no=()
    while read -r dir alvo; do
        case " ${censo} " in *" ${alvo} "*) ;; *) continue ;; esac
        pid="${dir#"${proc}"/}"
        pid="${pid%%/*}"
        chave="${pid}|${alvo}"
        [[ -n "${visto[${chave}]:-}" ]] && continue
        visto[${chave}]=1
        cmd="$(tr '\0' ' ' < "${proc}/${pid}/cmdline" 2>/dev/null)"
        [[ "${cmd}" == *hefesto* ]] && continue
        nome="$(cat "${proc}/${pid}/comm" 2>/dev/null)"
        por_no[${alvo}]+="${nome:-?} (PID ${pid}), "
    done < <(find "${proc}"/[0-9]*/fd -mindepth 1 -maxdepth 1 -type l -printf '%h %l\n' 2>/dev/null)
    if [[ ${#por_no[@]} -eq 0 ]]; then
        pass "só o Hefesto segura o hidraw dos DualSense físicos"
        return 0
    fi
    local no
    if [[ "${nativo}" == "True" ]]; then
        for no in $(printf '%s\n' "${!por_no[@]}" | LC_ALL=C sort); do
            info "Modo Nativo: ${no##*/} aberto por ${por_no[${no}]%, } — no Nativo o físico fica exposto à sessão de propósito"
        done
        return 0
    fi
    warn "${#por_no[@]} DualSense físico(s) com o hidraw aberto por outro programa — ele abriu antes de o Hefesto esconder o nó, e esconder não fecha o que já estava aberto; enquanto ele segurar, a barra desse controle pode não obedecer ao Hefesto"
    for no in $(printf '%s\n' "${!por_no[@]}" | LC_ALL=C sort); do
        info "  ${no##*/}: ${por_no[${no}]%, }"
    done
    info "  reconectar o controle solta o nó; com a regra do nó falando por último (${REGRA_DO_NO}), a próxima conexão já nasce fechada"
}

_nascimentos_do_daemon() {
    python3 - "$1" <<'PYEOF' 2>/dev/null
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
res = json.loads(buf.decode("utf-8")).get("result") or {}
print(f"nativo={res.get('native_mode')}")
for c in res.get("controllers") or []:
    if not isinstance(c, dict):
        continue
    n = c.get("nascimento")
    if not isinstance(n, dict):
        continue
    print(f"nasc|{c.get('player_slot')}|{n.get('pede_reconexao')}|{n.get('instancia')}")
PYEOF
}

_veredito_dos_nascimentos() {
    local texto="$1" tag slot pede inst condenados=() carimbados=0
    while IFS='|' read -r tag slot pede inst; do
        [[ "${tag}" == "nasc" ]] || continue
        carimbados=$((carimbados + 1))
        [[ "${pede}" == "True" ]] && condenados+=("P${slot:-?} (instância ${inst:-?})")
    done <<<"${texto}"
    if [[ "${carimbados}" -eq 0 ]]; then
        info "o daemon não carimbou nascimento nenhum (parado, sem controle, ou versão sem o carimbo)"
        return 0
    fi
    if [[ ${#condenados[@]} -eq 0 ]]; then
        pass "nenhum nascimento condenado vivo (${carimbados} carimbado(s))"
        return 0
    fi
    warn "nascimento condenado vivo em ${condenados[*]}: a conexão nasceu com outro programa segurando o nó, e nessa condição a barra pode não obedecer ao Hefesto — reconectar o controle com o nó limpo devolve"
}

check_quem_segura_o_fisico() {
    local censo nasc="" nativo="" sock
    censo="$(_censo_de_fisicos)"
    sock="$(runtime_socket)"
    if [[ -S "${sock}" ]] && command -v python3 >/dev/null 2>&1; then
        nasc="$(_nascimentos_do_daemon "${sock}")"
        nativo="$(sed -n 's/^nativo=//p' <<<"${nasc}")"
    fi
    _veredito_de_quem_segura_o_fisico /proc "${censo}" "${nativo}"
    _veredito_dos_nascimentos "${nasc}"
}

readonly OSK_BIN_WAYLAND="wvkbd-mobintl"
readonly OSK_BIN_X11="onboard"
readonly OSK_PKG_WAYLAND="wvkbd"
readonly OSK_PKG_X11="onboard"
readonly OSK_SENTINELA="${HOME:-}/.local/state/hefesto-dualsense4unix/teclado-na-tela.conf"

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

    local resultado motivo data pacote_gravado
    resultado="$(_osk_sentinela resultado || true)"
    motivo="$(_osk_sentinela motivo || true)"
    data="$(_osk_sentinela data || true)"
    pacote_gravado="$(_osk_sentinela pacote || true)"

    case "${resultado}" in
        pulado)
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
            info "rode: ${comando}    — ou $(conselho_de_instalacao)"
            ;;
    esac
}

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

check_steam_input_allowlist() {
    local arquivo="${XDG_CONFIG_HOME:-$HOME/.config}/hefesto-dualsense4unix/steam_input_apps.txt"
    if [[ ! -f "${arquivo}" ]]; then
        info "sem allowlist per-app do Steam Input (${arquivo} ausente) — nenhum jogo pediu exceção"
        return
    fi
    local appids
    appids="$(sed 's/#.*$//' "${arquivo}" 2>/dev/null | tr -d '[:blank:]' | grep -E '^[0-9]+$' || true)"
    if [[ -z "${appids}" ]]; then
        info "allowlist per-app do Steam Input vazia (${arquivo})"
        return
    fi
    local appid rotulo valor nomes="" desligado="" ausente=""
    for appid in ${appids}; do
        [[ -n "${appid}" ]] || continue
        rotulo="$(_rotulo_do_appid "${appid}")"
        nomes+="${nomes:+; }${rotulo}"
        valor="$(_steam_input_do_appid "${appid}")"
        case "${valor}" in
            0) desligado+="${desligado:+; }${rotulo}" ;;
            "") ausente+="${ausente:+; }${rotulo}" ;;
        esac
    done
    pass "allowlist do Steam Input (o Hefesto não desliga o Steam Input destes): ${nomes}"
    [[ -n "${desligado}" ]] && warn "jogo(s) na allowlist com o Steam Input DESLIGADO na Steam (UseSteamControllerConfig=0): ${desligado} — entrar na allowlist só IMPEDE o Hefesto de desligar, nunca LIGA; ligue na Steam (Propriedades → Controle → 'Ativar Entrada Steam'), ou tire o jogo da lista se a intenção mudou"
    [[ -n "${ausente}" ]] && info "jogo(s) na allowlist sem a chave UseSteamControllerConfig no vdf (a Steam nunca gravou nada para eles): ${ausente} — vale o default da Steam, que o Hefesto não mediu; abrir Propriedades → Controle uma vez faz a Steam escrever a chave"
    return 0
}

_rotulo_do_appid() {
    local appid="$1"
    if ! command -v python3 >/dev/null 2>&1; then
        printf 'appid %s' "${appid}"
        return 0
    fi
    HEFESTO_SRC="${ROOT_DIR}/src" HEFESTO_APPID="${appid}" python3 - <<'PY' 2>/dev/null || printf 'appid %s' "${appid}"
import os
import sys

sys.path.insert(0, os.environ.get("HEFESTO_SRC", ""))
appid = os.environ.get("HEFESTO_APPID", "")
try:
    from hefesto_dualsense4unix.integrations.steam_launch_options import rotulo_do_jogo
except Exception:  # noqa: BLE001
    print("appid %s" % appid, end="")
else:
    print(rotulo_do_jogo(appid), end="")
PY
}

_steam_input_do_appid() {
    local appid="$1" vdf linha
    shopt -s nullglob
    for vdf in "${HOME}/.steam/steam/userdata/"*/config/localconfig.vdf \
               "${HOME}/.local/share/Steam/userdata/"*/config/localconfig.vdf \
               "${HOME}/.var/app/com.valvesoftware.Steam/.steam/steam/userdata/"*/config/localconfig.vdf \
               "${HOME}/snap/steam/common/.steam/steam/userdata/"*/config/localconfig.vdf; do
        [[ -f "${vdf}" ]] || continue
        linha="$(awk -v alvo="${appid}" '
            /^[[:space:]]*"[^"]*"[[:space:]]*$/ { nome = $0; gsub(/^[[:space:]]*"|"[[:space:]]*$/, "", nome); pend = nome; next }
            /^[[:space:]]*\{[[:space:]]*$/ { depth++; stack[depth] = pend; pend = ""; next }
            /^[[:space:]]*\}[[:space:]]*$/ { if (depth > 0) { delete stack[depth]; depth-- } next }
            /"UseSteamControllerConfig"/ {
                if (depth > 0 && stack[depth] == alvo) {
                    if (match($0, /"UseSteamControllerConfig"[^"]*"[^"]*"/)) {
                        v = substr($0, RSTART, RLENGTH)
                        sub(/.*"UseSteamControllerConfig"[^"]*"/, "", v)
                        sub(/"$/, "", v)
                        print v
                    }
                }
            }
        ' "${vdf}" 2>/dev/null | head -1)"
        if [[ -n "${linha}" ]]; then
            shopt -u nullglob
            printf '%s' "${linha}"
            return 0
        fi
    done
    shopt -u nullglob
    return 0
}

_VIDS_DE_CONTROLE="054c 057e 045e 2dc8 0f0d 20d6 28de"

_controles_no_kernel() {
    local raiz="${1:-${HEFESTO_HIDRAW_ROOT:-/sys/class/hidraw}}" ue id bus vid pid phys uniq
    for ue in "${raiz}"/*/device/uevent; do
        [[ -r "${ue}" ]] || continue
        id="$(grep -m1 '^HID_ID=' "${ue}" 2>/dev/null | cut -d= -f2)"
        phys="$(grep -m1 '^HID_PHYS=' "${ue}" 2>/dev/null | cut -d= -f2)"
        uniq="$(grep -m1 '^HID_UNIQ=' "${ue}" 2>/dev/null | cut -d= -f2)"
        uniq="${uniq,,}"
        if [[ "${phys}" == hefesto-vpad* || "${uniq}" == 02:fe:* ]]; then
            continue
        fi
        IFS=: read -r bus vid pid <<<"${id}"
        vid="${vid: -4}"; vid="${vid,,}"
        pid="${pid: -4}"; pid="${pid,,}"
        if [[ " ${_VIDS_DE_CONTROLE} " != *" ${vid} "* ]]; then
            continue
        fi
        case "${bus}" in
            0003) printf 'USB %s:%s %s\n' "${vid}" "${pid}" "${uniq:-${ue%/device/uevent}}" ;;
            0005) printf 'BT %s:%s %s\n' "${vid}" "${pid}" "${uniq:-${ue%/device/uevent}}" ;;
        esac
    done | sort -u
}

_controles_pareados_no_bluez() {
    local p cls
    while IFS= read -r p; do
        [[ -z "${p}" ]] && continue
        [[ "$(_dbus_bt_prop "${p}" org.bluez.Device1 Paired)" == "true" ]] || continue
        cls="$(_dbus_bt_prop "${p}" org.bluez.Device1 Class)"
        [[ "${cls}" =~ ^[0-9]+$ ]] || continue
        if (( ((cls >> 8) & 0x1F) == 5 && ( ((cls >> 2) & 0x0F) == 1 || ((cls >> 2) & 0x0F) == 2 ) )); then
            printf '%s\n' "${p##*/dev_}"
        fi
    done < <(_dbus_bt_device_paths) | sort -u
}

check_controller() {
    local h hidraw=0 vivos pelo_usb pelo_bt
    for h in /dev/hidraw*; do [[ -e "$h" ]] && hidraw=1; done
    [[ "${hidraw}" -eq 1 ]] && info "nós hidraw: $(ls /dev/hidraw* 2>/dev/null | tr '\n' ' ')"
    vivos="$(_controles_no_kernel)"
    pelo_usb="$(grep -c '^USB ' <<<"${vivos}")"
    pelo_bt="$(grep -c '^BT ' <<<"${vivos}")"
    if (( pelo_usb + pelo_bt > 0 )); then
        pass "controle conectado agora: ${pelo_usb} pelo USB e ${pelo_bt} pelo BT"
    elif [[ -n "$(_controles_pareados_no_bluez)" ]]; then
        pass "controle pareado pelo BT (conecte para usar)"
    else
        warn "controle não detectado agora — conecte o controle para testar"
    fi
}

_udev_hidraw_scan() {
    local vista="$1"; shift
    local dirs=("$@")
    [[ ${#dirs[@]} -gt 0 ]] || dirs=("${_DIRS_DE_REGRAS_UDEV[@]}")
    local d f base v sombreado vistos=()
    for d in "${dirs[@]}"; do
        [[ -d "${d}" ]] || continue
        for f in "${d}"/*.rules; do
            [[ -e "${f}" || -L "${f}" ]] || continue
            base="${f##*/}"
            sombreado=0
            for v in ${vistos[@]+"${vistos[@]}"}; do
                [[ "${v}" == "${base}" ]] && sombreado=1
            done
            vistos+=("${base}")
            [[ "${sombreado}" -eq 1 ]] && continue
            [[ -f "${f}" && -r "${f}" ]] || continue
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

_udev_hidraw_rw_global() { _udev_hidraw_scan manta "$@"; }

_udev_hidraw_rw_estreitas() { _udev_hidraw_scan estreita "$@"; }

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
        [[ "${mode}" =~ ^[0-7]*[1-7]$ ]] || continue
        abertos+=("${h}")
        classes+="  ${h} (${mode}): $(_hidraw_classe_humana "${h}" "${sysroot}")"$'\n'
    done
    [[ ${#abertos[@]} -eq 0 ]] && return 0
    causas="$(_udev_hidraw_rw_global ${dirs[@]+"${dirs[@]}"})"
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
        warn "${#abertos[@]} nó(s) hidraw abertos a qualquer usuário local, e uma regra udev ESTREITADA por aparelho explica cada um — é decisão de quem escreveu a regra, não defeito do Hefesto"
    fi
    printf '%s' "${classes}"
    if [[ -n "${causas}" ]]; then
        info "  CAUSA (regra udev que abre TODO hidraw, sem estreitar por aparelho):"
        printf '%s\n' "${causas}" | while IFS= read -r linha; do
            [[ -n "${linha}" ]] && info "    ${linha}"
        done
        info "  este arquivo NÃO é do Hefesto — a decisão de mantê-lo é de quem o instalou."
        _rules_nossas=""
        if [[ -e "/etc/udev/rules.d/${REGRA_DO_NO}" ]]; then
            _rules_nossas="/etc/udev/rules.d/${REGRA_DO_NO}"
        elif [[ -e "/etc/udev/rules.d/${REGRA_DO_NO_VELHA}" ]]; then
            _rules_nossas="/etc/udev/rules.d/${REGRA_DO_NO_VELHA}"
        fi
        _nossa_trava=0
        if [[ -n "${_rules_nossas}" ]] && grep -q 'MODE:="0600"' "${_rules_nossas}" 2>/dev/null; then
            _nossa_trava=1
        fi
        _culpado_tardio=0
        while IFS= read -r _entrada; do
            [[ -z "${_entrada}" ]] && continue
            _arq="${_entrada%%:*}"
            _depois=0
            if [[ -n "${_rules_nossas}" ]] && [[ "$(printf '%s\n%s\n' "${_arq##*/}" "${_rules_nossas##*/}" \
                    | LC_ALL=C sort | head -1)" == "${_rules_nossas##*/}" ]]; then
                _depois=1
            fi
            [[ "${_depois}" -eq 1 && "${_nossa_trava}" -eq 0 ]] && _culpado_tardio=1
            case "${_entrada}" in
                *MODE\ :=*|*MODE:=*) [[ "${_depois}" -eq 0 ]] && _culpado_tardio=1 ;;
            esac
        done <<< "${causas}"
        if [[ -z "${_rules_nossas}" ]]; then
            info "  as regras do Hefesto NÃO estão instaladas aqui — então nada devolve esses nós ao esperado; $(conselho_de_instalacao "" "/usr/share/hefesto-dualsense4unix/scripts/install-host-udev.sh")."
        elif [[ "${_culpado_tardio}" -eq 1 ]]; then
            info "  ATENÇÃO: a regra acima roda DEPOIS das do Hefesto (ou usa 'MODE:='), então ela vence — os nós dos controles também ficam abertos."
        else
            info "  os aparelhos do Hefesto não são afetados: a regra deles roda depois e os devolve ao esperado (o controle físico 0600, aberto pelo broker; o virtual 0660+uaccess)."
        fi
    fi
    if [[ ${#alvos[@]} -gt 0 ]]; then
        info "  o conserto EXISTE e não roda sozinho: scripts/doctor.sh --restaurar-hidraw-uaccess"
        info "  o que ele VAI fazer, e nada além disso: tirar o bit de OUTROS de ${#alvos[@]} nó(s) — ${alvos[*]}"
        info "  o que ele NÃO faz: não cria regra udev, não escreve em /etc, não concede acesso a ninguém e não toca em nó que alguma regra explique."
        info "  o que ele NÃO resolve: ele não IMPEDE o nó de reabrir. Se o nó voltar a abrir depois, existe regra que este diagnóstico não lê (ENV{...}, GOTO, ou programa fora do udev) — e aí o conserto não dura."
    elif [[ ${#pulo_no[@]} -gt 0 ]]; then
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

restaurar_hidraw_uaccess() {
    local devdir="${1:-/dev}" sysroot="${2:-/sys/class/hidraw}"
    [[ $# -gt 0 ]] && shift
    [[ $# -gt 0 ]] && shift
    local dirs=("$@")
    local plano tipo no campo3 campo4 i alvo modo depois
    local alvos=() modos=() pulo_no=() pulo_motivo=() pulo_end=()

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

    info "vou tirar o bit de OUTROS destes ${#alvos[@]} nó(s), e nada além disso:"
    for i in "${!alvos[@]}"; do
        info "  ${alvos[$i]}: ${modos[$i]} -> ${modos[$i]%?}0   ($(_hidraw_classe_humana "${alvos[$i]}" "${sysroot}"))"
    done
    info "nenhuma regra udev é criada, nada é escrito em /etc, e nenhum acesso é concedido a ninguém."
    info "o que isto NÃO resolve: não IMPEDE o nó de reabrir. Se ele voltar a abrir, existe regra que este diagnóstico não lê (ENV{...}, GOTO, ou programa fora do udev) — e aí o conserto não dura."
    info "quem CONCEDE o uaccess aos nós do Hefesto é a regra udev, não este comando: $(conselho_de_instalacao "" "/usr/share/hefesto-dualsense4unix/scripts/install-host-udev.sh"), ou scripts/doctor.sh --fix."

    for i in "${!alvos[@]}"; do
        alvo="${alvos[$i]}"
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

readonly HEFESTO_DKMS_HID_NINTENDO_PKG="hefesto-hid-nintendo"
readonly HEFESTO_DKMS_HID_NINTENDO_VER="1.0.0"

readonly HEFESTO_DKMS_KERNEL_TESTED="7.0.11-76070011-generic"

check_cmdline_pad_virtual() {
    local cmdline="${HEFESTO_DOCTOR_CMDLINE:-/proc/cmdline}"
    local kstub="${HEFESTO_DOCTOR_KERNELSTUB:-/etc/kernelstub/configuration}"
    local grub="${HEFESTO_DOCTOR_GRUB:-/etc/default/grub}"
    local velho="054c:0df2:gn" onde="" agendado=0 vivo=0
    local sysq="${HEFESTO_DOCTOR_SYS:-/sys}/module/usbcore/parameters/quirks"
    grep -qF "${velho}" "${cmdline}" 2>/dev/null && onde="${onde} neste boot"
    { [[ -r "${kstub}" ]] && grep -qF "${velho}" "${kstub}" 2>/dev/null; } && { onde="${onde} no kernelstub"; agendado=1; }
    { [[ -r "${grub}" ]] && grep -qF "${velho}" "${grub}" 2>/dev/null; } && { onde="${onde} no grub"; agendado=1; }
    { [[ -r "${sysq}" ]] && grep -qF "${velho}" "${sysq}" 2>/dev/null; } && { onde="${onde} no sysfs"; vivo=1; }
    if [[ "${agendado}" -eq 1 ]]; then
        warn "DEFEITO: cmdline: ${velho} (${onde# }) — o pad virtual espera 200 ms por pedido; com 4 controles o jogo perde os controles. $(conselho_de_instalacao)$(so_no_checkout "(o passo 3e tira o 054c:0df2 e mantém o 054c:0ce6)")"
    elif [[ "${vivo}" -eq 1 ]]; then
        warn "DEFEITO: cmdline: ${velho} (${onde# }) — o pad virtual espera 200 ms por pedido; com 4 controles o jogo perde os controles. O bootloader já está curado: reinicie o computador."
    elif [[ -n "${onde}" ]]; then
        info "cmdline: ${velho} só na linha deste boot, fora do sysfs e do bootloader — some no próximo boot"
    fi
}

_dkms_kernels_validados() {
    local baseline lista=""
    for baseline in \
        "${ROOT_DIR}/assets/dkms/rtw88-usb/patch/BASELINE" \
        "/usr/share/hefesto-dualsense4unix/dkms/rtw88-usb/patch/BASELINE" \
    ; do
        [[ -r "${baseline}" ]] || continue
        lista="$(sed -n 's/^KERNELS_VALIDADOS=//p' "${baseline}" | head -1)"
        [[ -n "${lista}" ]] && break
    done
    printf '%s\n' "${lista}"
}

_DKMS_SB_WARNED=0

_check_dkms_kernel_drift() {
    local kver validados build
    kver="$(uname -r)"
    [[ "${kver}" == "${HEFESTO_DKMS_KERNEL_TESTED}" ]] && return

    validados="$(_dkms_kernels_validados)"
    for build in ${validados}; do
        if [[ "${kver%-*}" == "${build}" ]]; then
            pass "kernel atual (${kver}) está entre os kernels validados na BASELINE do DKMS"
            return
        fi
    done

    warn "kernel atual (${kver}) não está entre os kernels validados dos patches DKMS (${validados:-${HEFESTO_DKMS_KERNEL_TESTED}}) — se o build passou, o módulo do hefesto pode estar MASCARANDO um in-tree mais novo (fixes/suporte a devices); confira o rebase do BASELINE antes de confiar na cura, ou 'sudo dkms remove' para voltar ao in-tree"
}

_check_dkms_secureboot() {
    [[ "${_DKMS_SB_WARNED}" -eq 1 ]] && return
    [[ -r "${ROOT_DIR}/scripts/dkms_lib.sh" ]] || return
    ( source "${ROOT_DIR}/scripts/dkms_lib.sh"; dkms_secure_boot_ligado && ! dkms_chave_mok_inscrita ) \
        || return
    local kver; kver="$(uname -r)"
    if compgen -G "${HEFESTO_DKMS_MODULES_ROOT:-/lib/modules}/${kver}/updates/dkms/*.ko*" >/dev/null 2>&1; then
        _DKMS_SB_WARNED=1
        warn "Secure Boot ligado, a chave do DKMS não está inscrita, e há módulos do Hefesto em updates/dkms — o kernel os RECUSA no boot e NÃO volta ao driver de fábrica (o DualSense, o controle Nintendo ou o Wi-Fi USB ficam sem driver): $( source "${ROOT_DIR}/scripts/dkms_lib.sh"; dkms_passo_da_mok )"
    fi
}

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

check_hefesto_hid_nintendo_dkms() {
    if ! command -v dkms >/dev/null 2>&1; then
        info "dkms ausente — patch DKMS do hid-nintendo (a cura do probe pelo Bluetooth) não instalado (opcional: sudo apt install dkms$(so_no_checkout "— ou ./install.sh, que o instala por default"))"
        return
    fi
    local kver status
    kver="$(uname -r)"
    status="$(dkms status "${HEFESTO_DKMS_HID_NINTENDO_PKG}/${HEFESTO_DKMS_HID_NINTENDO_VER}" 2>/dev/null)"
    if [[ -z "${status}" ]]; then
        info "patch DKMS do hid-nintendo não instalado — driver in-tree em uso (cura de raiz do probe BT: $(conselho_de_instalacao "" "/usr/share/hefesto-dualsense4unix/scripts/install-host-udev.sh")$(so_no_checkout "— opt-out: --no-dkms"))"
        return
    fi
    if printf '%s\n' "${status}" | grep -qF ", ${kver}"; then
        pass "DKMS ${HEFESTO_DKMS_HID_NINTENDO_PKG}/${HEFESTO_DKMS_HID_NINTENDO_VER} construído p/ o kernel atual (${kver})"
        _check_dkms_kernel_drift
    else
        warn "DKMS ${HEFESTO_DKMS_HID_NINTENDO_PKG} instalado mas NÃO p/ o kernel atual (${kver}) — rebase pendente, in-tree em uso; status: ${status}"
    fi
    _check_dkms_secureboot

    local modpath
    modpath="$(modinfo -F filename hid_nintendo 2>/dev/null)"
    if [[ "${modpath}" == */updates/dkms/* ]]; then
        info "próximo carregamento resolve para o módulo patchado (${modpath})"
    elif [[ -n "${modpath}" ]]; then
        info "próximo carregamento ainda resolve para o in-tree (${modpath}) — confira /etc/depmod.d ou rode: sudo depmod -a"
    fi

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

readonly HEFESTO_DKMS_RTW88_PKG="hefesto-rtw88-usb"
readonly HEFESTO_DKMS_RTW88_VER="1.0.0"

check_hefesto_rtw88_usb_dkms() {
    if ! command -v dkms >/dev/null 2>&1; then
        info "dkms ausente — patch DKMS do rtw88_usb (a cura do fantasma USB do dongle Wi-Fi) não instalado (opcional: sudo apt install dkms$(so_no_checkout "— ou ./install.sh, que o instala por default"))"
        return
    fi
    local kver status
    kver="$(uname -r)"
    status="$(dkms status "${HEFESTO_DKMS_RTW88_PKG}/${HEFESTO_DKMS_RTW88_VER}" 2>/dev/null)"
    if [[ -z "${status}" ]]; then
        info "patch DKMS do rtw88_usb não instalado — driver in-tree em uso (cura de raiz do fantasma USB do dongle WiFi: $(conselho_de_instalacao "" "/usr/share/hefesto-dualsense4unix/scripts/install-host-udev.sh")$(so_no_checkout "— opt-out: --no-dkms"))"
        return
    fi
    if printf '%s\n' "${status}" | grep -qF ", ${kver}"; then
        pass "DKMS ${HEFESTO_DKMS_RTW88_PKG}/${HEFESTO_DKMS_RTW88_VER} construído p/ o kernel atual (${kver})"
        _check_dkms_kernel_drift
    else
        warn "DKMS ${HEFESTO_DKMS_RTW88_PKG} instalado mas NÃO p/ o kernel atual (${kver}) — rebase pendente OU kernel fora do pino BUILD_EXCLUSIVE_KERNEL (7.0.y é EOL, série nova precisa de rebase do BASELINE), in-tree em uso; status: ${status}"
    fi
    _check_dkms_secureboot

    local modpath
    modpath="$(modinfo -F filename rtw88_usb 2>/dev/null)"
    if [[ "${modpath}" == */updates/dkms/* ]]; then
        info "próximo carregamento resolve para o módulo patchado (${modpath})"
    elif [[ -n "${modpath}" ]]; then
        info "próximo carregamento ainda resolve para o in-tree (${modpath}) — confira /etc/depmod.d ou rode: sudo depmod -a"
    fi

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

readonly HEFESTO_DKMS_HID_PLAYSTATION_BASELINE="assets/dkms/hid-playstation/patch/BASELINE"

_hid_playstation_baseline() {
    local c
    for c in "${ROOT_DIR}/${HEFESTO_DKMS_HID_PLAYSTATION_BASELINE}" \
             "/usr/share/hefesto-dualsense4unix/dkms/hid-playstation/patch/BASELINE"; do
        [[ -r "${c}" ]] && { printf '%s\n' "${c}"; return 0; }
    done
    return 1
}

_hid_playstation_carregado_guarda_o_audio() {
    local modulo="$1" baseline="$2" marca src
    marca="$(cat "${modulo}/parameters/mic_frames_ignored" 2>/dev/null || true)"
    [[ "${marca}" == "Y" || "${marca}" == "1" ]] && return 0
    src="$(cat "${modulo}/srcversion" 2>/dev/null || true)"
    [[ -n "${src}" && -n "${baseline}" ]] || return 1
    [[ " $(sed -n 's/^SRCVERSION_DO_0003_SEM_A_MARCA=//p' "${baseline}" | head -1) " == *" ${src} "* ]]
}

check_hefesto_hid_playstation_dkms() {
    local kver="${HEFESTO_DOCTOR_KERNEL:-$(uname -r)}"
    local modulo="${HEFESTO_DOCTOR_SYS_MODULE:-/sys/module}/hid_playstation"
    local baseline validados="" um na_lista=0 modpath staged=0
    baseline="$(_hid_playstation_baseline || true)"
    if [[ -n "${baseline}" ]]; then
        validados="$(sed -n 's/^KERNELS_VALIDADOS=//p' "${baseline}" | head -1 | tr ',' ' ')"
        for um in ${validados}; do
            [[ "${kver}" == "${um}" || "${kver}" == "${um}"-* ]] && na_lista=1
        done
    fi
    modpath="$(modinfo -k "${kver}" -F filename hid_playstation 2>/dev/null || true)"
    [[ "${modpath}" == */updates/dkms/* ]] && staged=1

    if [[ -d "${modulo}" ]] && _hid_playstation_carregado_guarda_o_audio "${modulo}" "${baseline}"; then
        pass "o driver do DualSense carregado descarta o áudio do microfone (o hid-playstation do Hefesto): o microfone pelo rádio pode subir"
        return
    fi
    if [[ ! -d "${modulo}" ]]; then
        if [[ "${staged}" -eq 1 ]]; then
            info "o driver do DualSense não está carregado agora (sem DualSense ligado?) — o do Hefesto entra na próxima conexão (${modpath})"
        else
            info "o driver do DualSense não está carregado agora (sem DualSense ligado?)"
        fi
        return
    fi
    local efeito="o microfone do DualSense pelo rádio fica desligado, porque o driver carregado leria o áudio como botão e mexeria o cursor"
    if [[ "${staged}" -eq 1 ]]; then
        warn "${efeito} — o driver do Hefesto já está instalado para este kernel e entra no PRÓXIMO BOOT: reinicie o computador"
    elif [[ -n "${baseline}" && "${na_lista}" -eq 0 ]]; then
        warn "${efeito} — o kernel ${kver} não está entre os conferidos (${validados:-nenhum}), e o driver do Hefesto não se constrói nele de propósito (patch/BASELINE); o de fábrica segue. Para o microfone voltar, inicie um kernel dessa lista ou espere o Hefesto conferir este"
    elif [[ -r "${ROOT_DIR}/scripts/dkms_lib.sh" ]] \
         && ( source "${ROOT_DIR}/scripts/dkms_lib.sh"; dkms_secure_boot_ligado && ! dkms_chave_mok_inscrita ); then
        warn "${efeito} — Secure Boot ligado e a chave do DKMS não está inscrita, e sem ela o driver do Hefesto não se instala: $( source "${ROOT_DIR}/scripts/dkms_lib.sh"; dkms_passo_da_mok )"
    elif ! command -v dkms >/dev/null 2>&1; then
        warn "${efeito} — falta o dkms (e os headers do kernel) para construir o driver do Hefesto: instale os dois e $(conselho_de_instalacao)"
    else
        warn "${efeito} — o driver do Hefesto não está instalado para o kernel ${kver}: $(conselho_de_instalacao)"
    fi
}

_usb_f_hid_baseline() {
    local c
    for c in "${ROOT_DIR}/assets/dkms/usb-f-hid/patch/BASELINE" \
             "/usr/share/hefesto-dualsense4unix/dkms/usb-f-hid/patch/BASELINE"; do
        [[ -r "${c}" ]] && { printf '%s\n' "${c}"; return 0; }
    done
    return 1
}

check_hefesto_usb_f_hid_dkms() {
    local kver="${HEFESTO_DOCTOR_KERNEL:-$(uname -r)}"
    local modulo="${HEFESTO_DOCTOR_SYS_MODULE:-/sys/module}/usb_f_hid"
    local baseline validados="" um na_lista=0 modpath staged=0 marca
    baseline="$(_usb_f_hid_baseline || true)"
    if [[ -n "${baseline}" ]]; then
        validados="$(sed -n 's/^KERNELS_VALIDADOS=//p' "${baseline}" | head -1 | tr ',' ' ')"
        for um in ${validados}; do
            [[ "${kver}" == "${um}" || "${kver}" == "${um}"-* ]] && na_lista=1
        done
    fi
    modpath="$(modinfo -k "${kver}" -F filename usb_f_hid 2>/dev/null || true)"
    [[ "${modpath}" == */updates/dkms/* ]] && staged=1

    if [[ ! -d "${modulo}" ]]; then
        if [[ "${staged}" -eq 1 ]]; then
            info "a função HID dos pads USB virtuais não está carregada (nenhum pad USB no ar) — a do Hefesto entra no próximo carregamento (${modpath})"
        fi
        return
    fi
    marca="$(cat "${modulo}/parameters/get_report_sized" 2>/dev/null || true)"
    if [[ "${marca}" == "Y" || "${marca}" == "1" ]]; then
        pass "a função HID dos pads USB virtuais é a do Hefesto: a resposta do pedido de feature fecha no tamanho certo"
        return
    fi
    local efeito="a função HID dos pads USB virtuais é a de fábrica: o jogo no Proton espera 5 s por pedido de feature e perde os controles"
    if [[ "${staged}" -eq 1 ]]; then
        fail "${efeito} — a do Hefesto já está instalada para este kernel e não foi trocada: $(conselho_de_instalacao) (ele solta os pads e troca), ou reinicie o computador"
    elif [[ -n "${baseline}" && "${na_lista}" -eq 0 ]]; then
        fail "${efeito} — o kernel ${kver} não está entre os conferidos (${validados:-nenhum}); a do Hefesto só se constrói depois de o fonte deste kernel ser conferido e o kernel entrar no patch/BASELINE"
    elif [[ -r "${ROOT_DIR}/scripts/dkms_lib.sh" ]] \
         && ( source "${ROOT_DIR}/scripts/dkms_lib.sh"; dkms_secure_boot_ligado && ! dkms_chave_mok_inscrita ); then
        fail "${efeito} — Secure Boot ligado e a chave do DKMS não está inscrita: $( source "${ROOT_DIR}/scripts/dkms_lib.sh"; dkms_passo_da_mok )"
    elif ! command -v dkms >/dev/null 2>&1; then
        fail "${efeito} — falta o dkms (e os headers do kernel) para construir a do Hefesto: instale os dois e $(conselho_de_instalacao)"
    else
        fail "${efeito} — a do Hefesto não está instalada para o kernel ${kver}: $(conselho_de_instalacao)"
    fi
}

_modulo_pede_reinicio() {
    local nome="$1" raiz="${HEFESTO_DOCTOR_SYS_MODULE:-/sys/module}" carregado arquivo novo
    carregado="$(cat "${raiz}/${nome//-/_}/srcversion" 2>/dev/null || true)"
    [[ -n "${carregado}" ]] || return 1
    arquivo="$(modinfo -F filename "${nome}" 2>/dev/null || true)"
    [[ "${arquivo}" == */updates/dkms/* ]] || return 1
    novo="$(modinfo -F srcversion "${nome}" 2>/dev/null || true)"
    [[ -n "${novo}" && "${novo}" != "${carregado}" ]]
}

check_reinicio_pendente() {
    local nome pendentes=()
    for nome in hid-playstation hid-nintendo rtw88_usb uhid usb_f_hid; do
        _modulo_pede_reinicio "${nome}" && pendentes+=("${nome}")
    done
    if [[ "${#pendentes[@]}" -gt 0 ]]; then
        warn "reinício pendente: o módulo carregado não é o instalado (${pendentes[*]}) — o instalado entra no próximo boot; reinicie o computador"
    fi
}

check_usb_fantasma() {
    local d driver idv idp key any=0
    local -A _seen=()

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

    local ligadas="" ifc ferr="" nome dir desliga=""
    for nome in iw iwconfig; do
        ferr="$(command -v "${nome}" 2>/dev/null)" && break
        for dir in /usr/sbin /sbin; do
            [[ -x "${dir}/${nome}" ]] && { ferr="${dir}/${nome}"; break 2; }
        done
        ferr=""
    done
    case "${ferr##*/}" in
        iw)
            while IFS= read -r ifc; do
                [[ -n "${ifc}" ]] || continue
                if "${ferr}" dev "${ifc}" get power_save 2>/dev/null | grep -qi 'power save: *on'; then
                    ligadas+="${ligadas:+ }${ifc}"
                fi
            done < <("${ferr}" dev 2>/dev/null | awk '$1 == "Interface" { print $2 }')
            desliga="sudo ${ferr} dev ${ligadas%% *} set power_save off"
            ;;
        iwconfig)
            while IFS= read -r ifc; do
                [[ -n "${ifc}" ]] || continue
                if "${ferr}" "${ifc}" 2>/dev/null | grep -qi 'power management: *on'; then
                    ligadas+="${ligadas:+ }${ifc}"
                fi
            done < <("${ferr}" 2>/dev/null | awk '/^[^ \t]/ && !/no wireless extensions/ { print $1 }')
            desliga="sudo ${ferr} ${ligadas%% *} power off"
            ;;
    esac
    local agora="nenhuma interface Wi-Fi com ela ligada agora"
    [[ -n "${ferr}" ]] || agora="sem iw nem iwconfig, cada interface não se confere"

    if [[ "${val}" == "2" && "${src}" == "/etc/NetworkManager/conf.d/hefesto-wifi-powersave.conf" ]]; then
        if [[ -n "${ligadas}" ]]; then
            warn "o conf do hefesto desliga a economia de energia do Wi-Fi (wifi.powersave=2), mas ${ligadas} ainda está com ela LIGADA — rode o install de novo, ou: ${desliga} (vale na hora, não reconecta)"
        else
            pass "economia de energia do Wi-Fi desligada (wifi.powersave=2 via o conf.d do hefesto; ${agora})"
        fi
    elif [[ -n "${ligadas}" ]]; then
        warn "economia de energia do Wi-Fi LIGADA em ${ligadas} (${src:-sem wifi.powersave configurado}) — histórico de instabilidade em dongles Realtek USB (rtw88); o install do hefesto a desliga sem reconectar"
    elif [[ -z "${val}" ]]; then
        info "NetworkManager sem wifi.powersave configurado (default do driver/firmware vale); o install do hefesto grava o conf que desliga a economia"
    elif [[ "${val}" == "3" ]]; then
        info "wifi.powersave=3 (LIGA o power save do firmware) via ${src}, e ${agora}; o install do hefesto grava o conf que a desliga"
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

check_wifi_usb() {
    local instalado="${HEFESTO_WIFI_INSTALADO:-/usr/local/lib/hefesto-dualsense4unix/wifi_usb.sh}"
    local dispatcher="${HEFESTO_WIFI_DISPATCHER:-/etc/NetworkManager/dispatcher.d/90-hefesto-wifi-usb}"
    local script="" lista="" linha st_timer="" dono_modo="" diario="" n_reset=0 problema=0
    local ultimo_estado="" onde_o_dispatcher="sem NetworkManager nesta máquina, sem dispatcher"
    if [[ -x "${ROOT_DIR}/scripts/wifi_usb.sh" ]]; then
        script="${ROOT_DIR}/scripts/wifi_usb.sh"
    elif [[ -x "${instalado}" ]]; then
        script="${instalado}"
    fi
    if [[ -z "${script}" ]]; then
        info "vigia do Wi-Fi USB: o wifi_usb.sh não está nesta instalação — não sei dizer se há dongle Wi-Fi USB"
        return 0
    fi
    lista="$(bash "${script}" --lista 2>/dev/null || true)"
    if command -v systemctl >/dev/null 2>&1; then
        st_timer="$(systemctl is-active hefesto-wifi-usb-vigia.timer 2>/dev/null || true)"
    fi
    if [[ -z "${lista}" ]]; then
        if [[ "${st_timer}" == "active" ]]; then
            pass "nenhum Wi-Fi USB agora — o vigia está armado e não faz nada"
        else
            info "nenhum Wi-Fi USB agora (o vigia do dongle não está ativo; só faz falta a quem tiver um)"
        fi
        return 0
    fi
    lista="$(printf '%s' "${lista}" | tr '\n' ' ' | sed 's/ $//')"
    if [[ ! -x "${instalado}" ]]; then
        if esta_instalacao_e_um_checkout; then
            warn "há Wi-Fi USB (${lista}) e o vigia do dongle não está instalado — o scan de fundo pode derrubá-lo de 5 em 5 min e um travamento mudo fica sem cura: $(conselho_de_instalacao)"
        else
            warn "há Wi-Fi USB (${lista}) e o vigia do dongle não está ligado — o scan de fundo pode derrubá-lo de 5 em 5 min e um travamento mudo fica sem cura. O pacote não o liga (é um serviço de root que reinicia porta USB); quem o liga é o instalador do repositório do Hefesto, rodado de um clone dele, em qualquer formato"
        fi
        problema=1
    elif [[ "${st_timer}" != "active" ]]; then
        warn "o vigia do Wi-Fi USB está instalado e o timer não está ativo (${st_timer:-?}) — ligue: sudo systemctl enable --now hefesto-wifi-usb-vigia.timer"
        problema=1
    fi
    if [[ -d "$(dirname "$(dirname "${dispatcher}")")" ]]; then
        onde_o_dispatcher="dispatcher do NetworkManager no lugar"
        if [[ ! -e "${dispatcher}" ]]; then
            if [[ -x "${instalado}" ]]; then
                warn "o dispatcher ${dispatcher} não existe — cada associação nova nasce com o scan de fundo ligado até o próximo tique do vigia"
                problema=1
            fi
        else
            dono_modo="$(stat -c '%U %a' "${dispatcher}" 2>/dev/null || true)"
            if [[ "${dono_modo}" != "root 755" ]]; then
                warn "o dispatcher ${dispatcher} está '${dono_modo:-?}' e o NetworkManager só roda script de root, 755 — ele é ignorado. Reinstale: $(conselho_de_instalacao)"
                problema=1
            fi
        fi
    fi
    while IFS= read -r linha; do
        [[ -n "${linha}" ]] || continue
        if [[ "${linha}" == *"AVISO: mesmo hub que o Bluetooth"* ]]; then
            warn "Wi-Fi USB e Bluetooth no mesmo hub: ${linha} — afaste o dongle dos adaptadores (outra porta, outro hub)"
            problema=1
        else
            info "wifi: ${linha}"
        fi
    done < <(bash "${script}" --status 2>/dev/null || true)
    if command -v journalctl >/dev/null 2>&1; then
        diario="$(journalctl -b -q --no-pager -t hefesto-wifi-usb 2>/dev/null || true)"
        n_reset="$(printf '%s\n' "${diario}" | grep -c 'reiniciada (' || true)"
        ultimo_estado="$(printf '%s\n' "${diario}" \
            | grep -E 'parei\. Tire e ponha o dongle|o roteador voltou a responder|curado depois de' \
            | tail -n 1 || true)"
        if [[ "${ultimo_estado}" == *"parei. Tire e ponha o dongle"* ]]; then
            warn "o vigia do Wi-Fi USB reiniciou a porta 3 vezes sem cura e PAROU neste boot — tire e ponha o dongle (de preferência noutra porta)"
            problema=1
        elif [[ "${n_reset:-0}" -gt 0 && -n "${ultimo_estado}" ]]; then
            info "o vigia reiniciou a porta do dongle ${n_reset}x neste boot, e o roteador voltou a responder depois"
        elif [[ "${n_reset:-0}" -gt 0 ]]; then
            info "o vigia reiniciou a porta do dongle ${n_reset}x neste boot"
        fi
    fi
    [[ "${problema}" -eq 0 ]] && pass "vigia do Wi-Fi USB de pé (${lista}): timer ativo, ${onde_o_dispatcher}"
    return 0
}

usb_pci_controller() {
    local devpath="$1" real
    real="$(readlink -f "${devpath}" 2>/dev/null || true)"
    printf '%s\n' "${real}" | grep -oE '0000:[0-9a-f]{2}:[0-9a-f]{2}\.[0-9a-f]' | tail -1
}

pci_label() {
    case "$1" in
        *0c:00.3) echo "CPU/Ryzen (0c:00.3)" ;;
        *02:00.0) echo "chipset (02:00.0)" ;;
        "")       echo "desconhecido" ;;
        *)        echo "$1" ;;
    esac
}

bus_to_label() {
    pci_label "$(usb_pci_controller "/sys/bus/usb/devices/usb${1}" 2>/dev/null)"
}

check_usb_dropout() {
    command -v journalctl >/dev/null 2>&1 || { info "journalctl ausente — pulo o check de dropout"; return; }

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

    local lines n
    lines="$(journalctl -b -k --no-pager 2>/dev/null \
              | grep -iE 'error -71|device descriptor read/64, error|not accepting address|unable to enumerate USB device' || true)"
    n="$(printf '%s' "$lines" | grep -c . || true)"; n="${n:-0}"
    if [[ "${n}" -eq 0 ]]; then
        pass "sem dropout -71 neste boot"
        return
    fi
    warn "dropout USB: ${n} sintoma(s) -71/enum neste boot"

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

    info "ver em tempo real: scripts/doctor.sh --watch-dropout"
}

suggest_port() {
    local d ds_dev=""
    for d in /sys/bus/usb/devices/*; do
        [[ -r "$d/idVendor" ]] || continue
        [[ "$(cat "$d/idVendor" 2>/dev/null)" == "054c" ]] && ds_dev="$d"
    done
    if [[ -z "$ds_dev" ]]; then
        if _controles_no_kernel | grep -q '^BT 054c:'; then
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

watch_dropout() {
    printf 'vigiando o journal do kernel por dropout -71 (Ctrl-C para sair)...\n'
    journalctl -kf -o cat --since now 2>/dev/null \
      | grep -m1 -iE 'error -71|device descriptor read/64, error|not accepting address|device not responding' \
      && printf '\n[WATCH] primeiro sinal de dropout capturado acima.\n'
}

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

fix_fila_sem_fixture() {
    [[ -f "${ROOT_DIR}/scripts/check_faixa_sintetica.py" ]] || return 0
    local py saida fecho estado
    py="$(_python_do_produto)"
    if [[ -z "${py}" ]]; then
        warn "limpeza da fila não rodou: sem python para o check_faixa_sintetica.py"
        return
    fi
    saida="$("${py}" "${ROOT_DIR}/scripts/check_faixa_sintetica.py" --casa --limpar 2>&1)" || true
    if [[ $'\n'"${saida}" == *$'\n'"OK:"* ]]; then
        pass "fila de numeração: sem endereço de fixture"
        return
    fi
    if [[ $'\n'"${saida}" != *$'\n'"LIMPO:"* ]]; then
        fecho="${saida##*$'\n'}"
        warn "limpeza da fila não rodou: ${fecho:-o check_faixa_sintetica.py não respondeu} (python: ${py})"
        return
    fi
    pass "fila de numeração: endereços de fixture retirados"
    if ! command -v systemctl >/dev/null 2>&1; then
        [[ -S "$(runtime_socket)" ]] && warn "sem systemctl para reiniciar o daemon: ele guarda a fila antiga na memória e a regrava quando um controle chegar — feche-o e rode --fix de novo"
        return
    fi
    systemctl --user try-restart "${APP_ID}.service" >/dev/null 2>&1 || true
    estado="$(systemctl --user is-active "${APP_ID}.service" 2>/dev/null || true)"
    if [[ "${estado}" == "active" ]]; then
        pass "daemon reiniciado para ler a fila limpa (${APP_ID}.service)"
    elif [[ -S "$(runtime_socket)" ]]; then
        warn "o socket do daemon está de pé sem o ${APP_ID}.service: um daemon aberto fora do systemd guarda a fila antiga na memória e a regrava quando um controle chegar — feche-o e rode --fix de novo"
    fi
}

fix_ucm_do_dualsense() {
    [[ -f "${ROOT_DIR}/scripts/install_ucm_dualsense.sh" ]] || return 0
    local saida fecho rc=0
    saida="$(bash "${ROOT_DIR}/scripts/install_ucm_dualsense.sh" \
        --raiz-ucm "${HEFESTO_RAIZ_UCM:-/usr/share/alsa/ucm2}" \
        --sysfs "${HEFESTO_SYSFS:-/sys}" 2>&1)" || rc=$?
    fecho="${saida##*$'\n'}"
    fecho="${fecho#\[ucm\] }"
    fecho="${fecho#aviso: }"
    if [[ "${rc}" -ne 0 ]]; then
        warn "install_ucm_dualsense.sh falhou (código ${rc}): ${fecho:-sem resposta} — rode: bash scripts/install_ucm_dualsense.sh"
    elif [[ $'\n'"${saida}" == *$'\n'"[ucm] "[0-9]*" gancho(s) em "* ]]; then
        pass "perfil UCM do DualSense conferido (um gancho por controlador USB)"
    else
        info "perfil UCM do DualSense não gravado: ${fecho:-o install_ucm_dualsense.sh não respondeu}"
    fi
}

_o_vigia_recusou_o_pino() {
    local unidade="${HOME}/.config/systemd/user/hefesto-steam-input-guard.service"
    [[ -f "${unidade}" ]] && ! grep -qE '^ExecStart=.*--manter' "${unidade}" 2>/dev/null
}

_gesto_da_trava_do_pino() {
    if [[ "${1:-0}" != "1" ]]; then
        printf '%s' "a trava espera o Proton pinado ficar instalado (ver o aviso de AUSENTE acima)"
    elif _o_vigia_recusou_o_pino; then
        printf '%s' "o vigia da Steam foi instalado sem o passo do pino (--no-proton-pin, ou um instalador anterior a 18/09/2026); para travar, $(conselho_de_instalacao)"
    else
        printf '%s' "rode: scripts/doctor.sh --fix (trava com a Steam fechada; o vigia da Steam também trava sozinho quando ela sai)"
    fi
}

fix_proton_pinado() {
    local py="${ROOT_DIR}/src/hefesto_dualsense4unix/integrations/proton_pin.py"
    [[ -f "${py}" && -f "${ROOT_DIR}/assets/proton-pin.conf" ]] || return 0
    command -v python3 >/dev/null 2>&1 || return 0
    if [[ ! -f "${HOME}/.steam/steam/config/config.vdf" \
          && ! -f "${HOME}/.local/share/Steam/config/config.vdf" ]]; then
        return 0
    fi
    if _o_vigia_recusou_o_pino; then
        info "Proton pinado: o vigia da Steam desta máquina foi instalado sem o passo do pino (--no-proton-pin, ou um instalador anterior a 18/09/2026) — o --fix não trava por cima disso; para travar, $(conselho_de_instalacao)"
        return 0
    fi
    local rc=0
    python3 "${py}" --manter >/dev/null 2>&1 || rc=$?
    case "${rc}" in
        0) pass "Proton pinado conferido e jogos travados nele (--manter)" ;;
        2) warn "trava do Proton pinado ESPERA o pino: ele não está instalado e o tarball não está no cache (o --fix não baixa nada) — $(conselho_de_instalacao)" ;;
        3) warn "trava do Proton pinado ADIADA — a Steam (ou um jogo) está aberta; feche e rode de novo: scripts/doctor.sh --fix" ;;
        5) warn "o Proton pinado bateu com o SHA256 e a EXTRAÇÃO falhou — veja o espaço livre em disco e rode de novo: scripts/doctor.sh --fix" ;;
        *) warn "trava do Proton pinado falhou (rc=${rc}) — rode: python3 ${py} --manter" ;;
    esac
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
    fix_ucm_do_dualsense
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
    fix_mic_dualsense
    fix_proton_pinado
    fix_fila_sem_fixture
}

_DESEMPENHO_PROVADOS=""

_desempenho_boot() {
    local b="${HEFESTO_DESEMPENHO_BOOT:-}"
    [[ -n "${b}" ]] || b="$(awk '/^btime/ { print $2 }' "${HEFESTO_PROC:-/proc}/stat" 2>/dev/null)"
    printf '%s' "${b:-0}"
}

_desempenho_cliente() {
    local d="${HEFESTO_DESEMPENHO_BIN:-}" nome
    for nome in system76-power powerprofilesctl; do
        if [[ -n "${d}" ]]; then
            [[ -x "${d}/${nome}" ]] && { printf '%s' "${d}/${nome}"; return 0; }
        elif command -v "${nome}" 2>/dev/null; then
            return 0
        fi
    done
    return 0
}

_desempenho_ppd_sem_performance() {
    local lista
    lista="$(timeout 3 "$1" list 2>/dev/null)" || return 1
    ! grep -Eq '^[[:space:]*]*performance:' <<<"${lista}"
}

_desempenho_perfil_agora() {
    local bin
    bin="$(_desempenho_cliente)"
    case "${bin}" in
        */system76-power)
            timeout 3 "${bin}" profile 2>/dev/null | sed -n 's/^Power Profile: *//p' | head -1 | tr '[:upper:]' '[:lower:]' || true
            ;;
        */powerprofilesctl)
            timeout 3 "${bin}" get 2>/dev/null | head -1 | tr '[:upper:]' '[:lower:]' || true
            ;;
    esac
}

_desempenho_ligar_arquivo() {
    local arq="$1" destino="$2"
    if [[ -f "${ROOT_DIR}/assets/desempenho/${arq}" ]]; then
        printf 'sudo install -Dm644 %s/assets/desempenho/%s %s (vale no próximo boot)' "${ROOT_DIR}" "${arq}" "${destino}"
    else
        printf '%s' "$(conselho_de_instalacao --desempenho)"
    fi
}

_desempenho_diz() {
    local id="$1" rotulo="$2" arq="$3" agora="$4" quer="$5" ligar="$6" desligar="$7"
    local provado=0 mtime
    [[ "${id}" == "perfil" || " ${_DESEMPENHO_PROVADOS} " == *" ${id} "* ]] && provado=1
    if [[ -f "${arq}" ]]; then
        if [[ "${agora}" == "${quer}" ]]; then
            pass "modo desempenho, ${rotulo}: aplicado (agora: ${agora}). Para desligar: ${desligar}"
            return
        fi
        mtime="$(stat -c %Y "${arq}" 2>/dev/null || echo 0)"
        if [[ "${mtime}" -gt "$(_desempenho_boot)" ]]; then
            info "modo desempenho, ${rotulo}: gravado, vale no PRÓXIMO BOOT (agora: ${agora:-?}). Para desligar: ${desligar}"
        else
            warn "modo desempenho, ${rotulo}: DESFEITO por outro programa (o arquivo pede ${quer}, agora está ${agora:-?}). Veja o que escreve ali depois do boot; para desligar de vez: ${desligar}"
        fi
    elif [[ "${provado}" -eq 1 ]]; then
        if [[ "${agora}" == "${quer}" ]]; then
            info "modo desempenho, ${rotulo}: não pedido; já está assim agora (${agora}), mas o Hefesto não o guarda depois do boot. Para guardar: ${ligar}"
        else
            info "modo desempenho, ${rotulo}: não pedido (agora: ${agora:-?}). Para ligar: ${ligar}"
        fi
    else
        info "modo desempenho, ${rotulo}: não aplicado: a provar (agora: ${agora:-?}) — só entra depois da medida no aparelho. À mão: ${ligar}; para desligar: ${desligar}"
    fi
}

check_desempenho() {
    local raiz="${HEFESTO_DESEMPENHO_RAIZ:-}" sys="${HEFESTO_SYSFS:-/sys}" proc="${HEFESTO_PROC:-/proc}"
    local etc="${raiz}/etc" agora ligar cliente
    local unit="${etc}/systemd/system/hefesto-desempenho.service"
    local wants="${etc}/systemd/system/multi-user.target.wants/hefesto-desempenho.service"
    ligar="$(conselho_de_instalacao --desempenho)"

    agora="$(_desempenho_perfil_agora)"
    cliente="$(_desempenho_cliente)"
    if [[ -z "${cliente}" ]]; then
        info "modo desempenho, perfil de energia: pulado, sem system76-power nem power-profiles-daemon não há perfil a pedir"
    elif [[ "${cliente}" == */powerprofilesctl ]] && _desempenho_ppd_sem_performance "${cliente}"; then
        info "modo desempenho, perfil de energia: pulado, o power-profiles-daemon desta máquina não oferece o perfil performance"
    elif [[ -f "${unit}" && ! -L "${wants}" ]]; then
        warn "modo desempenho, perfil de energia: a unit hefesto-desempenho.service está gravada e NÃO habilitada (agora: ${agora:-?}). Habilitar: sudo systemctl enable --now hefesto-desempenho.service"
    elif [[ -f "${unit}" && "${agora}" != "performance" ]]; then
        info "modo desempenho, perfil de energia: a unit pede Performance a cada boot, e agora está ${agora:-?} (trocado depois, no menu de energia ou por outro programa). Para voltar: sudo systemctl restart hefesto-desempenho.service; para desligar: sudo systemctl disable --now hefesto-desempenho.service && sudo rm /etc/systemd/system/hefesto-desempenho.service"
    else
        _desempenho_diz perfil "perfil de energia em Performance" "${unit}" "${agora}" performance \
            "${ligar}" "sudo systemctl disable --now hefesto-desempenho.service && sudo rm /etc/systemd/system/hefesto-desempenho.service"
    fi

    if [[ -r "${proc}/driver/nvidia/params" ]]; then
        agora="$(sed -n 's/^DynamicPowerManagement: *//p' "${proc}/driver/nvidia/params" 2>/dev/null | head -1)"
        _desempenho_diz nvidia "GPU NVIDIA sem o modo de economia de notebook (DynamicPowerManagement=0)" \
            "${etc}/modprobe.d/hefesto-desempenho-nvidia.conf" "${agora}" 0 \
            "$(_desempenho_ligar_arquivo hefesto-desempenho-nvidia.conf /etc/modprobe.d/hefesto-desempenho-nvidia.conf)" \
            "sudo rm /etc/modprobe.d/hefesto-desempenho-nvidia.conf (vale no próximo boot)"
    else
        info "modo desempenho, GPU NVIDIA: pulado, sem o driver NVIDIA carregado (a placa é outra, ou está sem driver)"
    fi

    if [[ -d "${sys}/module/snd_hda_intel" ]]; then
        agora="$(cat "${sys}/module/snd_hda_intel/parameters/power_save" 2>/dev/null || echo '?')/$(cat "${sys}/module/snd_hda_intel/parameters/power_save_controller" 2>/dev/null || echo '?')"
        _desempenho_diz audio "áudio da placa-mãe sem o sono do codec (power_save=0)" \
            "${etc}/modprobe.d/hefesto-desempenho-audio.conf" "${agora}" "0/N" \
            "$(_desempenho_ligar_arquivo hefesto-desempenho-audio.conf /etc/modprobe.d/hefesto-desempenho-audio.conf)" \
            "sudo rm /etc/modprobe.d/hefesto-desempenho-audio.conf (vale no próximo boot)"
    else
        info "modo desempenho, áudio da placa-mãe: pulado, sem snd_hda_intel carregado (o áudio desta máquina é outro)"
    fi

    if [[ -r "${sys}/module/pcie_aspm/parameters/policy" ]]; then
        agora="$(sed -n 's/.*\[\([a-z]*\)\].*/\1/p' "${sys}/module/pcie_aspm/parameters/policy" 2>/dev/null | head -1)"
        _desempenho_diz aspm "PCIe com a política de ASPM em performance" \
            "${etc}/tmpfiles.d/hefesto-desempenho-aspm.conf" "${agora}" performance \
            "$(_desempenho_ligar_arquivo hefesto-desempenho-aspm.conf /etc/tmpfiles.d/hefesto-desempenho-aspm.conf)" \
            "sudo rm /etc/tmpfiles.d/hefesto-desempenho-aspm.conf (vale no próximo boot)"
    else
        info "modo desempenho, ASPM do PCIe: pulado, este kernel não expõe a política"
    fi
}

_cosmic_settings_daemon_pids() {
    local p argv0
    for p in $(pgrep -u "$(id -u)" -x cosmic-settings 2>/dev/null || true); do
        argv0=""
        IFS= read -r -d '' argv0 2>/dev/null < "/proc/${p}/cmdline" || true
        if [[ "${argv0##*/}" == cosmic-settings-daemon ]]; then
            printf '%s\n' "${p}"
        fi
    done
}
check_o_painel_do_cosmic_ve_o_som() {
    local clientes pids argv0 programa cura
    pgrep -u "$(id -u)" -x cosmic-session >/dev/null 2>&1 || return 0
    command -v pw-cli >/dev/null 2>&1 || return 0
    clientes="$(timeout 5 pw-cli ls Client 2>/dev/null || true)"
    if [[ "${clientes}" != *PipeWire:Interface:Client* ]]; then
        info "o PipeWire não respondeu — pulo a conferência do painel de som do COSMIC"
        return 0
    fi
    if [[ "${clientes}" == *'application.name = "cosmic-settings-daemon"'* ]]; then
        pass "o painel do COSMIC vê o som (o cosmic-settings-daemon é cliente do PipeWire)"
        return 0
    fi
    pids="$(_cosmic_settings_daemon_pids)"
    argv0=""
    if [[ -n "${pids}" ]]; then
        IFS= read -r -d '' argv0 2>/dev/null < "/proc/${pids%%$'\n'*}/cmdline" || true
    fi
    if [[ "${argv0}" == /* ]]; then
        programa="${argv0}"
    else
        programa="$(command -v cosmic-settings-daemon 2>/dev/null || printf '/usr/bin/cosmic-settings-daemon')"
    fi
    LC_ALL=C grep -qa 'libpipewire-0\.3\.so' "${programa}" 2>/dev/null || return 0
    cura="systemd-run --user --collect ${programa}"
    if [[ -n "${pids}" ]]; then
        warn "o painel do COSMIC está sem o som: o cosmic-settings-daemon está vivo e fora do PipeWire (o som foi reiniciado depois dele) — rode: kill $(tr '\n' ' ' <<<"${pids}")&& ${cura}"
    else
        warn "o painel do COSMIC está sem o som: o cosmic-settings-daemon não está no ar — rode: ${cura}"
    fi
}

_BASICO_SEGUNDOS_DA_SESSAO=5
check_o_basico() {
    local protocolo="${ROOT_DIR}/scripts/o_basico.py" py sock sub rc saida resumo
    local -a argv
    if [[ ! -f "${protocolo}" ]]; then
        info "o protocolo do básico não veio nesta instalação (scripts/o_basico.py) — nada foi medido"
        return
    fi
    sock="$(runtime_socket)"
    if [[ ! -S "${sock}" ]]; then
        warn "o básico não foi medido: o daemon não está no ar (suba o daemon e rode de novo)"
        return
    fi
    py="$(_python_do_produto)"
    [[ -n "${py}" ]] || { warn "o básico não foi medido: sem python"; return; }
    for sub in retrato sessao eixos; do  # (noqa-acento)
        argv=("${sub}")
        [[ "${sub}" == "sessao" ]] && argv+=(--segundos "${_BASICO_SEGUNDOS_DA_SESSAO}")  # (noqa-acento)
        saida="$(timeout 300 "${py}" "${protocolo}" "${argv[@]}" 2>&1)"
        rc=$?
        resumo="$(grep -E "^${sub}: rc=" <<<"${saida}" | tail -n 1)"
        [[ -n "${resumo}" ]] || resumo="${sub}: rc=${rc}"
        case "${rc}" in
            0) pass "o básico, ${sub}: tudo no critério (${resumo#*: })" ;;
            1) fail "o básico, ${sub}: há linha vermelha (${resumo#*: })"
               grep -E '^\s+\[ +VERMELHO\]' <<<"${saida}" | while IFS= read -r linha; do info "${linha#"${linha%%[![:space:]]*}"}"; done ;;
            2) warn "o básico, ${sub}: recusado, nada foi provado (${resumo#*: })"
               grep -E '^RECUSO: ' <<<"${saida}" | head -n 3 | while IFS= read -r linha; do info "${linha#"${linha%%[![:space:]]*}"}"; done ;;
            3) warn "o básico, ${sub}: há linha que não se soube medir (${resumo#*: })"
               grep -E '^\s+\[ +NÃO SEI\]' <<<"${saida}" | head -n 3 | while IFS= read -r linha; do info "${linha#"${linha%%[![:space:]]*}"}"; done ;;
            124) warn "o básico, ${sub}: passou do teto de 300 s e foi cortado" ;;
            *) warn "o básico, ${sub}: o protocolo saiu com ${rc} (${resumo#*: })" ;;
        esac
    done
}

main() {
    [[ "${WATCH_DROPOUT}" -eq 1 ]] && { watch_dropout; exit 0; }
    [[ "${SUGGEST_PORT}" -eq 1 ]] && { suggest_port; exit 0; }
    if [[ "${BASICO}" -eq 1 ]]; then
        hdr "o básico medido (retrato, sessão e eixos)"
        check_o_basico
        [[ "${FAILS}" -eq 0 ]]
        exit $?
    fi
    if [[ "${RESTAURAR_HIDRAW}" -eq 1 ]]; then
        hdr "restauro de permissão dos nós hidraw (--restaurar-hidraw-uaccess)"
        restaurar_hidraw_uaccess
        [[ "${FAILS}" -eq 0 ]]
        exit $?
    fi
    if [[ "${FIX_MIC}" -eq 1 ]]; then
        hdr "microfone do DualSense (camadas 1 e 2)"
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
    check_libhidapi
    check_loader_svg
    check_binding_webkit
    hdr "kernel / udev"
    check_udev
    check_o_no_fisico_nasce_sem_acl
    check_usb_audio_off
    check_usb_quirk
    check_usb_storm_config_conflict
    check_uinput
    check_uhid
    check_uhid_contrapressao
    check_hid_playstation
    check_hid_playstation_probe_abortado
    check_led_sysfs_gravavel
    check_input_uaccess
    hdr "energia USB e rádio"
    check_usb_power_devices
    check_usb_power_hosts
    check_pcie_aspm
    check_power_saboteurs
    check_btusb_autosuspend
    check_desempenho
    check_bluez_fastconnectable
    check_bluez_justworks_repairing
    check_bt_clone_ds4
    check_bt_rfkill
    check_bt_radio
    check_bt_crc_counters
    check_kernel_watch
    check_familias_do_radio
    check_cmdline_platform
    check_cmdline_pad_virtual
    hdr "rádio e pareamento (G2)"
    check_bluez_backport_version
    check_bluez_curas_do_backport
    check_bt_agent_service
    check_bt_resilience
    check_trava_do_radio
    check_bt_bonds_persistidos
    check_bt_connected_sem_hidraw
    check_bt_sdp_cache_envenenado
    check_bt_paired_sem_bonded
    check_bond_dobrado
    check_exame_da_mesa
    hdr "a bandeja do sistema (tray)"
    check_bandeja
    hdr "detector de janela (autoswitch / perfil-por-jogo)"
    check_window_detect
    check_perfis_inalcancaveis
    hdr "áudio (microfone)"
    check_wireplumber_source
    check_dropin_do_mic_armado
    check_default_source_monitor
    check_dualsense_sink_disabled
    check_dropin_do_alto_falante_acordado
    check_ucm_do_dualsense
    check_audio_sink_muted
    check_mic_mute_persistido
    check_mic_perfil_sem_sinal
    check_mic_ganho_de_captura
    check_pipewire_cura_do_metadata
    check_o_painel_do_cosmic_ve_o_som
    hdr "Steam Input"
    check_steam_input
    check_steam_input_allowlist
    hdr "controle no jogo (duplicação / wrapper de launch)"
    check_launch_wrapper
    check_copias_do_wrapper
    check_ultimo_device_ks
    check_vdf_poison
    check_dedup_ipc
    check_display_authority
    check_proton_pin
    hdr "o modo de cada jogador e a hora de cada pad"
    check_o_modo_no_ar
    check_a_hora_do_pad
    check_o_pad_em_usb
    check_o_pad_no_uhid
    hdr "broker hide-hidraw (cura de raiz do controle duplicado)"
    check_hidraw_broker
    check_quem_segura_o_fisico
    hdr "giroscópio no jogo (vpad Motion)"
    check_vpad_motion
    hdr "teclado na tela (o que o L3 do controle abre)"
    check_teclado_na_tela
    hdr "controle"
    check_controller
    check_perms_soft
    check_hid_nintendo_bt_cascade
    hdr "DKMS hid-nintendo (cura de raiz do probe pelo Bluetooth)"
    check_hefesto_hid_nintendo_dkms
    hdr "DKMS hid-playstation (a guarda do microfone pelo rádio)"
    check_hefesto_hid_playstation_dkms
    hdr "DKMS usb_f_hid (a resposta do pedido de feature dos pads USB virtuais)"
    check_hefesto_usb_f_hid_dkms
    hdr "DKMS rtw88_usb / WiFi (fantasma USB + powersave)"
    check_hefesto_rtw88_usb_dkms
    check_usb_fantasma
    check_wifi_powersave
    check_wifi_usb
    hdr "reinício pendente"
    check_reinicio_pendente
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

_regra_que_o_kmod_le() {
    local py
    py="$(_python_do_produto)"
    [[ -n "${py}" ]] || return 1
    HEFESTO_SRC="${ROOT_DIR}/src" "${py}" - "$1" "${HEFESTO_DOCTOR_BTUSB_RAIZ:-/}" <<'PY' 2>/dev/null
import os
import sys
from pathlib import Path

src = os.environ.get("HEFESTO_SRC", "")
if src and os.path.isdir(src):
    sys.path.insert(0, src)
try:
    from hefesto_dualsense4unix.integrations.exame_da_mesa import regra_que_o_kmod_le
except ImportError:
    raise SystemExit(3)
caminho = regra_que_o_kmod_le(sys.argv[1], Path(sys.argv[2]))
print(caminho if caminho is not None else "")
PY
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main
fi
