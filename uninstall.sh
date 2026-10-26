#!/usr/bin/env bash

set -euo pipefail

readonly APP_ID="hefesto-dualsense4unix"
readonly DESKTOP_TARGET="${HOME}/.local/share/applications/${APP_ID}.desktop"
readonly AUTOSTART_TARGET="${HOME}/.config/autostart/${APP_ID}-tray.desktop"
readonly ICON_TARGET="${HOME}/.local/share/icons/hicolor/256x256/apps/${APP_ID}.png"
readonly LAUNCHER="${HOME}/.local/bin/hefesto-dualsense4unix-gui"
readonly BIN_SYMLINK="${HOME}/.local/bin/hefesto-dualsense4unix"
readonly CHAVE_BIN="${HOME}/.local/bin/hefesto-chave"
readonly HOTPLUG_UNIT_TARGET="${HOME}/.config/systemd/user/hefesto-dualsense4unix-gui-hotplug.service"

readonly APPLET_BIN="/usr/local/bin/hefesto-dualsense4unix-applet"
readonly APPLET_DESKTOP="/usr/share/applications/com.vitoriamaria.HefestoDualsense4Unix.desktop"
readonly APPLET_ICON="/usr/share/icons/hicolor/scalable/apps/com.vitoriamaria.HefestoDualsense4Unix-symbolic.svg"
readonly APPLET_ICON_SYMB="/usr/share/icons/hicolor/symbolic/apps/com.vitoriamaria.HefestoDualsense4Unix-symbolic.svg"
readonly APPLET_ICON_PNG="/usr/share/icons/hicolor/256x256/apps/com.vitoriamaria.HefestoDualsense4Unix.png"
readonly WIREPLUMBER_DROPIN="${HOME}/.config/wireplumber/wireplumber.conf.d/51-hefesto-dualsense-no-default-source.conf"
readonly WIREPLUMBER_DROPIN_DISABLE="${HOME}/.config/wireplumber/wireplumber.conf.d/52-hefesto-dualsense-disable-source.conf"
readonly WIREPLUMBER_DROPIN_OUTPUT="${HOME}/.config/wireplumber/wireplumber.conf.d/53-hefesto-dualsense-disable-output.conf"
readonly WIREPLUMBER_DROPIN_ACORDADO="${HOME}/.config/wireplumber/wireplumber.conf.d/54-hefesto-dualsense-alto-falante-nunca-dorme.conf"
readonly MARCA_MIC_PEDIDO="${XDG_STATE_HOME:-${HOME}/.local/state}/hefesto-dualsense4unix/mic-do-dualsense-pedido.conf"
readonly ENVIRONMENTD_GAMEMODE="${HOME}/.config/environment.d/91-hefesto-dualsense-gamemode.conf"

readonly ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly VENV_HEFESTO="${ROOT_DIR}/.venv/bin/hefesto-dualsense4unix"

readonly ESTADO_DO_XDG="${XDG_STATE_HOME:-${HOME}/.local/state}/${APP_ID}"
ESTADOS_DO_HEFESTO=("${ESTADO_DO_XDG}")
if [[ "${HOME}/.local/state/${APP_ID}" != "${ESTADO_DO_XDG}" ]]; then
    ESTADOS_DO_HEFESTO+=("${HOME}/.local/state/${APP_ID}")
fi

REMOVE_UDEV=1
REMOVE_USB_QUIRK=0
KEEP_CONFIG=1
SO_O_APPLET=0
KEEP_STEAM_INPUT=0
KEEP_BLUEZ=1
RESTORE_PIPEWIRE=0
AUTO_YES=0
DRY_RUN=0

uso() {
    cat <<'FIM'
Uso: ./uninstall.sh [opções]

Remove o Hefesto - DualSense4Unix (serviços, binários, regras udev, módulos
DKMS, drop-ins). Por padrão PRESERVA sua configuração e seus perfis.

Opções:
  --keep-udev           preserva as regras udev + modules-load (a do nó do
                        DualSense fica aberta, porque o broker sai)
  --remove-usb-quirk    remove também o quirk da cmdline (sensível; exige reboot)
  --purge-config        APAGA config, perfis e as cópias de pareamento do
                        Bluetooth (destrutivo; o padrão é preservar)
  --so-o-applet         remove SÓ o applet COSMIC aposentado (binário, .desktop
                        e ícones) e sai. Não toca em daemon, udev, Steam nem
                        config. O applet saiu do instalador em 19/09/2026 —
                        o tray faz o mesmo.
  --keep-config         preserva config e perfis (padrão)
  --keep-steam-input    não mexe no PSSupport do Steam Input
  --restore-bluez       DEVOLVE o BlueZ original da distro (o padrão PRESERVA o
                        backport). Destrutivo: reinicia o bluetoothd e descarta
                        os bonds pareados.
  --restore-pipewire    DEVOLVE o PipeWire de antes do install, sem perguntar (sem a
                        flag, pergunta; com --yes ou sem TTY, preserva). Reinicia o
                        som e recusa com a Steam aberta.
  --keep-bluez          [no-op] preservar já é o padrão desde 02/08/2026
  --yes, -y             não pergunta nada (necessário sem TTY)
  --dry-run, -n         ensaio: diz o que removeria nesta máquina e não remove
                        nada (não pede senha, não para processo nenhum)
  --help, -h            mostra esta ajuda e sai

Nada é removido enquanto esta ajuda estiver sendo exibida.
FIM
}

for arg in "$@"; do
    case "$arg" in
        --keep-udev)         REMOVE_UDEV=0 ;;
        --udev)              REMOVE_UDEV=1 ;;
        --remove-usb-quirk)  REMOVE_USB_QUIRK=1 ;;
        --so-o-applet)       SO_O_APPLET=1 ;;
        --purge-config)      KEEP_CONFIG=0 ;;
        --keep-config)       KEEP_CONFIG=1 ;;
        --keep-steam-input)  KEEP_STEAM_INPUT=1 ;;
        --keep-bluez)        KEEP_BLUEZ=1 ;;
        --restore-bluez)     KEEP_BLUEZ=0 ;;
        --restore-pipewire)  RESTORE_PIPEWIRE=1 ;;
        --yes|-y)            AUTO_YES=1 ;;
        --dry-run|-n)        DRY_RUN=1 ;;
        --help|-h)           uso; exit 0 ;;
        *)
            printf '[uninstall] argumento desconhecido: %s\n' "$arg" >&2
            printf '[uninstall] nada foi removido. Use --help para ver as opções.\n' >&2
            exit 2
            ;;
    esac
done

log() { printf '[uninstall] %s\n' "$*"; }

# shellcheck source=scripts/lib/som_da_sessao.sh
source "${ROOT_DIR}/scripts/lib/som_da_sessao.sh"

SUDO_KEEPALIVE_PID=""
_start_sudo_keepalive() {
    [[ -n "${SUDO_KEEPALIVE_PID}" ]] && return 0
    ( while kill -0 "$$" 2>/dev/null; do sudo -n true 2>/dev/null || exit 0; sleep 50; done ) &
    SUDO_KEEPALIVE_PID=$!
}
acquire_sudo() {
    [[ "${EUID:-$(id -u)}" -eq 0 ]] && return 0
    command -v sudo >/dev/null 2>&1 || return 0
    if sudo -n true 2>/dev/null; then
        _start_sudo_keepalive
        return 0
    fi
    [[ "${_NEEDS_SUDO:-1}" -eq 1 ]] || return 0
    if [[ -n "${SUDO_ASKPASS:-}" ]] && sudo -A -v 2>/dev/null; then
        _start_sudo_keepalive
        return 0
    fi
    printf '[uninstall] Alguns passos precisam de sudo (udev, cura do storm, applet COSMIC).\n'
    printf '[uninstall] Vou pedir sua senha UMA vez; os passos seguintes reusam a credencial.\n'
    if sudo -v; then
        _start_sudo_keepalive
    else
        log "sudo indisponível (senha/TTY) — passos com root serão pulados/avisados"
    fi
    return 0
}
_cleanup_sudo_keepalive() {
    [[ -n "${SUDO_KEEPALIVE_PID}" ]] && kill "${SUDO_KEEPALIVE_PID}" 2>/dev/null || true
}
trap _cleanup_sudo_keepalive EXIT

if [[ "${DRY_RUN}" -eq 1 ]]; then
    exec 3>&1
    AUTO_YES=1
    log() { printf '[uninstall · ensaio] %s\n' "$*"; }
    _faria() { printf '[uninstall · ensaio] FARIA: %s%s\n' "${_ENS_ROOT:-}" "$*" >&3; }
    log "ENSAIO: nada é removido, nada é parado, nenhuma senha é pedida — cada linha FARIA é o que o uninstall de verdade faria nesta máquina"
    _start_sudo_keepalive() { :; }
    sudo() {
        case "$*" in
            "-n true"|"-v"|"-A -v"|"-n -v") return 0 ;;
        esac
        local -a _ens_argv=("$@")
        while [[ "${_ens_argv[0]:-}" == -[nAEHkS] ]]; do _ens_argv=("${_ens_argv[@]:1}"); done
        case "${_ens_argv[0]:-}" in
            diff) command diff "${_ens_argv[@]:1}"; return ;;
            systemctl|dkms|flatpak|busctl|udevadm|hciconfig|python3)
                _ENS_ROOT="(root) " "${_ens_argv[@]}"; return ;;
        esac
        _ENS_ROOT="(root) " _faria "${_ens_argv[*]}"
        return 0
    }
    for _ens_cmd in rm rmdir mv cp install mkdir ln chmod chown touch tee find \
                    pkill killall pip pip3 apt-get dnf pacman kernelstub \
                    update-desktop-database gtk-update-icon-cache update-initramfs \
                    gpasswd depmod modprobe rmmod gsettings dconf gnome-extensions \
                    systemd-run bash sh; do
        eval "${_ens_cmd}() { _faria \"${_ens_cmd} \$*\"; return 0; }"
    done
    unset _ens_cmd
    kill() { if [[ "${1:-}" == "-0" ]]; then builtin kill "$@"; else _faria "kill $*"; fi; }
    mktemp() { return 1; }
    sleep() { :; }
    timeout() { while [[ "${1:-}" == -* ]]; do shift; done; shift; "$@"; }
    systemctl() {
        local _ens_a
        for _ens_a in "$@"; do
            [[ "${_ens_a}" == -* ]] && continue
            case "${_ens_a}" in
                is-active|is-enabled|is-failed|cat|show|status|list-units|list-unit-files|list-timers)
                    command systemctl "$@"; return ;;
            esac
            break
        done
        _faria "systemctl $*"
    }
    dkms() { if [[ "${1:-}" == "status" ]]; then command dkms "$@"; else _faria "dkms $*"; fi; }
    flatpak() { case "${1:-}" in list|info) command flatpak "$@" ;; *) _faria "flatpak $*" ;; esac; }
    busctl() { case "${1:-}" in get-property|tree|introspect|status|list) command busctl "$@" ;; *) _faria "busctl $*" ;; esac; }
    udevadm() { if [[ "${1:-}" == "info" ]]; then command udevadm "$@"; else _faria "udevadm $*"; fi; }
    hciconfig() { if [[ $# -le 1 ]]; then command hciconfig "$@"; else _faria "hciconfig $*"; fi; }
    python3() {
        if [[ "${1:-}" == "-" || ( "${1:-}" == "-I" && "${2:-}" == "-c" ) ]]; then
            command python3 "$@"
        else
            _faria "python3 $*"
        fi
    }
fi

_NEEDS_SUDO=0
[[ "${REMOVE_UDEV}" -eq 1 ]] && _NEEDS_SUDO=1
[[ -e /etc/modprobe.d/hefesto-dualsense-storm.conf ]] && _NEEDS_SUDO=1
[[ -e /usr/share/alsa/ucm2/USB-Audio/Hefesto/DualSense-HiFi.conf ]] && _NEEDS_SUDO=1
[[ -e /etc/systemd/system/hefesto-desempenho.service \
   || -e /etc/modprobe.d/hefesto-desempenho-nvidia.conf \
   || -e /etc/modprobe.d/hefesto-desempenho-audio.conf \
   || -e /etc/tmpfiles.d/hefesto-desempenho-aspm.conf ]] && _NEEDS_SUDO=1
[[ -e /etc/bluetooth/main.conf.d/hefesto-fastconnectable.conf ]] && _NEEDS_SUDO=1
grep -qsE '^# >>> hefesto (bluetooth|FastConnectable|JustWorksRepairing) >>>' \
    /etc/bluetooth/main.conf 2>/dev/null && _NEEDS_SUDO=1
grep -qsF '#hefesto-desativou# ' /etc/bluetooth/main.conf 2>/dev/null && _NEEDS_SUDO=1
[[ -f "${HOME}/.local/state/hefesto-dualsense4unix/cmdline-owners.conf" ]] && _NEEDS_SUDO=1
[[ -e "${APPLET_BIN}" || -e "${APPLET_DESKTOP}" || -e "${APPLET_ICON}" || -e "${APPLET_ICON_SYMB}" || -e "${APPLET_ICON_PNG}" ]] && _NEEDS_SUDO=1
dpkg -l "${APP_ID}" >/dev/null 2>&1 && _NEEDS_SUDO=1
[[ -e /etc/bluetooth/main.conf.d/hefesto-justworks.conf ]] && _NEEDS_SUDO=1
grep -qsF '# >>> hefesto JustWorksRepairing >>>' /etc/bluetooth/main.conf 2>/dev/null && _NEEDS_SUDO=1
[[ -e /etc/systemd/system/hefesto-bt-agent.service ]] && _NEEDS_SUDO=1
[[ -e /etc/sudoers.d/49-hefesto-bt-ponte ]] && _NEEDS_SUDO=1
[[ -e /usr/local/lib/hefesto-dualsense4unix/bt_ponte_privilegiada.sh ]] && _NEEDS_SUDO=1
[[ -e /etc/sudoers.d/49-hefesto-placa ]] && _NEEDS_SUDO=1
[[ -e /usr/local/lib/hefesto-dualsense4unix/hefesto_placa_acordada.sh ]] && _NEEDS_SUDO=1
[[ "${KEEP_BLUEZ}" -eq 0 && -f "${HOME}/.cache/hefesto-dualsense4unix/bluez-backport/VERSOES-ANTERIORES.txt" ]] && _NEEDS_SUDO=1
[[ -e /etc/apt/preferences.d/hefesto-pipewire ]] && _NEEDS_SUDO=1
[[ -f "${HOME}/.cache/hefesto-dualsense4unix/pipewire-backport/VERSOES-ANTERIORES.txt" ]] \
    && [[ "${RESTORE_PIPEWIRE}" -eq 1 || ( "${AUTO_YES}" -eq 0 && -t 0 ) ]] && _NEEDS_SUDO=1
[[ -e /etc/tmpfiles.d/hefesto-dualsense4unix-radio.conf ]] && _NEEDS_SUDO=1
[[ -e /run/hefesto-dualsense4unix || -e /run/hefesto-bt-ponte || -e /run/hefesto-bt-rebind || -e /run/hefesto-bt-watchdog ]] && _NEEDS_SUDO=1
compgen -G '/var/lib/hefesto-dualsense4unix/radio-diario.jsonl*' >/dev/null 2>&1 && _NEEDS_SUDO=1
[[ "${KEEP_CONFIG}" -eq 0 ]] \
    && compgen -G '/var/lib/hefesto-dualsense4unix/bt-bonds.pre-uninstall-*' >/dev/null 2>&1 \
    && _NEEDS_SUDO=1
[[ -e /etc/systemd/system/hefesto-hidraw-broker.service ]] && _NEEDS_SUDO=1
[[ -e /etc/systemd/system/hefesto-hidraw-broker.socket ]] && _NEEDS_SUDO=1
[[ "${REMOVE_UDEV}" -eq 0 && -f /etc/udev/rules.d/73-hefesto-ps5-controller.rules ]] && _NEEDS_SUDO=1
[[ "${REMOVE_UDEV}" -eq 0 && -f /etc/udev/rules.d/70-ps5-controller.rules ]] && _NEEDS_SUDO=1
[[ -e /etc/modprobe.d/hefesto-hid-nintendo.conf ]] && _NEEDS_SUDO=1
[[ -e /etc/modprobe.d/hefesto-hid-playstation.conf ]] && _NEEDS_SUDO=1
[[ -e /etc/modprobe.d/hefesto-uhid.conf ]] && _NEEDS_SUDO=1
command -v dkms >/dev/null 2>&1 \
    && [[ -n "$(dkms status hefesto-hid-playstation 2>/dev/null)" ]] \
    && _NEEDS_SUDO=1
command -v dkms >/dev/null 2>&1 \
    && [[ -n "$(dkms status hefesto-usb-f-hid 2>/dev/null)" ]] \
    && _NEEDS_SUDO=1
command -v dkms >/dev/null 2>&1 \
    && [[ -n "$(dkms status hefesto-hid-nintendo 2>/dev/null)" ]] \
    && _NEEDS_SUDO=1
command -v dkms >/dev/null 2>&1 \
    && [[ -n "$(dkms status hefesto-rtw88-usb 2>/dev/null)" ]] \
    && _NEEDS_SUDO=1
[[ -e /etc/NetworkManager/conf.d/hefesto-wifi-powersave.conf ]] && _NEEDS_SUDO=1
[[ -e /etc/systemd/system/hefesto-wifi-usb-vigia.timer ]] && _NEEDS_SUDO=1
[[ -e /etc/systemd/system/hefesto-wifi-usb-vigia.service ]] && _NEEDS_SUDO=1
[[ -e /etc/NetworkManager/dispatcher.d/90-hefesto-wifi-usb ]] && _NEEDS_SUDO=1
[[ -e /usr/local/lib/hefesto-dualsense4unix/wifi_usb.sh ]] && _NEEDS_SUDO=1
[[ -e /etc/systemd/system/hefesto-bt-health-watchdog.service.d/10-hefesto-maquina.conf ]] && _NEEDS_SUDO=1
remover_o_applet() {
    if [[ ! -e "${APPLET_BIN}" && ! -e "${APPLET_DESKTOP}" && ! -e "${APPLET_ICON}" \
          && ! -e "${APPLET_ICON_SYMB}" && ! -e "${APPLET_ICON_PNG}" ]]; then
        log "applet COSMIC: nada a remover (nenhum dos cinco arquivos existe)"
        return 0
    fi
    log "removendo applet COSMIC (sudo): binário + .desktop + ícones"
    sudo rm -f "${APPLET_BIN}" "${APPLET_DESKTOP}" "${APPLET_ICON}" "${APPLET_ICON_SYMB}" "${APPLET_ICON_PNG}" 2>/dev/null || true
    sudo gtk-update-icon-cache -q -f /usr/share/icons/hicolor 2>/dev/null || true
    sudo update-desktop-database -q /usr/share/applications 2>/dev/null || true
    local esta_na_lista=0
    local lista
    for lista in "${HOME}"/.config/cosmic/com.system76.CosmicPanel.*/v1/plugins_*; do
        [[ -r "${lista}" ]] || continue
        grep -qF 'com.vitoriamaria.HefestoDualsense4Unix' "${lista}" && esta_na_lista=1
    done
    if [[ "${esta_na_lista}" -eq 1 ]]; then
        log "o applet estava na lista de Miniaplicativos — recarregando o painel"
        command -v killall >/dev/null 2>&1 && killall cosmic-panel 2>/dev/null || true
    fi
}

if [[ "${SO_O_APPLET}" -eq 1 ]]; then
    log "--so-o-applet: removendo apenas o applet COSMIC aposentado"
    remover_o_applet
    log "pronto. Nada mais foi tocado: daemon, udev, Steam, config e perfis seguem."
    exit 0
fi

acquire_sudo

log "parando daemon hefesto-dualsense4unix (se ativo)"
timeout 5 systemctl --user stop hefesto-dualsense4unix.service >/dev/null 2>&1 || true
systemctl --user disable hefesto-dualsense4unix.service >/dev/null 2>&1 || true
rm -f "${HOME}/.config/systemd/user/hefesto-dualsense4unix.service"
systemctl --user disable --now hefesto-dualsense4unix-presenca.service >/dev/null 2>&1 || true
rm -f "${HOME}/.config/systemd/user/hefesto-dualsense4unix-presenca.service"
systemctl --user daemon-reload >/dev/null 2>&1 || true

log "matando processos hefesto*"
for pat in 'hefesto-dualsense4unix daemon ' 'hefesto-dualsense4unix-gui' 'hefesto_dualsense4unix' 'io\.github\.hefesto_team\.hefesto_dualsense4unix' 'br\.andrefarias\.Hefesto'; do
    pkill -TERM -f "$pat" 2>/dev/null || true
done
sleep 2
for pat in 'hefesto-dualsense4unix daemon ' 'hefesto-dualsense4unix-gui' 'hefesto_dualsense4unix' 'io\.github\.hefesto_team\.hefesto_dualsense4unix' 'br\.andrefarias\.Hefesto'; do
    pkill -KILL -f "$pat" 2>/dev/null || true
done

_PY_DAS_MODIFICACOES='
import json, os, sys
try:
    estado = json.load(open(sys.argv[1], encoding="utf-8"))
except (OSError, ValueError):
    sys.exit(0)
mods = estado.get("mods") if isinstance(estado, dict) else None
if not isinstance(mods, dict):
    sys.exit(0)
def vivo(pid):
    try:
        for linha in open("/proc/%d/status" % pid, encoding="utf-8"):
            if linha.startswith("State:"):
                return linha.split()[1] != "Z"
    except OSError:
        pass
    return False
for mod_id, linha in sorted(mods.items()):
    pid = linha.get("pid") if isinstance(linha, dict) else None
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 1 or not vivo(pid):
        continue
    try:
        ambiente = open("/proc/%d/environ" % pid, "rb").read().split(b"\0")
        lider = os.getpgid(pid) == pid
    except OSError:
        continue
    if ("HEFESTO_MOD_ID=%s" % mod_id).encode() in ambiente:
        print(mod_id, ("-" if lider else "") + str(pid))
'

_as_modificacoes_vivas() {
    local arquivo="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/hefesto-dualsense4unix/mods-estado.json"
    [[ -f "${arquivo}" ]] || return 0
    python3 -I -c "${_PY_DAS_MODIFICACOES}" "${arquivo}" || true
}

parar_as_modificacoes() {
    local -a vivas=()
    local linha alvo
    mapfile -t vivas < <(_as_modificacoes_vivas)
    [[ "${#vivas[@]}" -gt 0 ]] || return 0
    for linha in "${vivas[@]}"; do
        alvo="${linha#* }"
        log "parando a extensão ${linha% *} (processo ${alvo#-})"
        kill -TERM -- "${alvo}" 2>/dev/null || true
    done
    sleep 2
    mapfile -t vivas < <(_as_modificacoes_vivas)
    for linha in "${vivas[@]}"; do
        alvo="${linha#* }"
        log "a extensão ${linha% *} não parou; mandando o fim (processo ${alvo#-})"
        kill -KILL -- "${alvo}" 2>/dev/null || true
    done
}
parar_as_modificacoes

if [[ -f "${HOTPLUG_UNIT_TARGET}" ]]; then
    log "desabilitando hefesto-dualsense4unix-gui-hotplug.service"
    systemctl --user disable hefesto-dualsense4unix-gui-hotplug.service >/dev/null 2>&1 || true
    log "removendo ${HOTPLUG_UNIT_TARGET}"
    rm -f "${HOTPLUG_UNIT_TARGET}"
    systemctl --user daemon-reload >/dev/null 2>&1 || true
else
    log "ausente: ${HOTPLUG_UNIT_TARGET}"
fi

readonly STORM_UNIT_TARGET="${HOME}/.config/systemd/user/hefesto-dualsense4unix-storm-watch.service"
readonly STORM_SCRIPT_TARGET="${HOME}/.local/share/hefesto-dualsense4unix/scripts/storm_watch.sh"
if [[ -f "${STORM_UNIT_TARGET}" ]]; then
    log "desabilitando hefesto-dualsense4unix-storm-watch.service (kernel-watch)"
    systemctl --user disable --now hefesto-dualsense4unix-storm-watch.service >/dev/null 2>&1 || true
    log "removendo ${STORM_UNIT_TARGET}"
    rm -f "${STORM_UNIT_TARGET}"
    systemctl --user daemon-reload >/dev/null 2>&1 || true
else
    log "ausente: ${STORM_UNIT_TARGET}"
fi
rm -f "${STORM_SCRIPT_TARGET}"
rmdir "${HOME}/.local/share/hefesto-dualsense4unix/scripts" 2>/dev/null || true
for _estado in "${ESTADOS_DO_HEFESTO[@]}"; do
    if [[ -L "${_estado}/storm.log" ]]; then
        log "removendo symlink de compat storm.log→kernel.log (o kernel.log fica — é seu histórico)"
        rm -f "${_estado}/storm.log"
    fi
done

log "removendo guard do Steam Input (path/timer/service --user)"
systemctl --user disable --now hefesto-steam-input-guard.path hefesto-steam-input-guard.timer >/dev/null 2>&1 || true
rm -f "${HOME}/.config/systemd/user/hefesto-steam-input-guard.path" \
      "${HOME}/.config/systemd/user/hefesto-steam-input-guard.timer" \
      "${HOME}/.config/systemd/user/hefesto-steam-input-guard.service"
systemctl --user daemon-reload >/dev/null 2>&1 || true

rm -f "${HOME}/.local/share/applications/dsx-dualsense.desktop" 2>/dev/null || true
if [[ -e /usr/share/applications/dsx-dualsense.desktop ]]; then
    sudo rm -f /usr/share/applications/dsx-dualsense.desktop 2>/dev/null || true
fi

for path in "${DESKTOP_TARGET}" "${AUTOSTART_TARGET}" "${ICON_TARGET}" \
            "${LAUNCHER}" "${BIN_SYMLINK}" "${CHAVE_BIN}"; do
    if [[ -e "${path}" || -L "${path}" ]]; then
        log "removendo ${path}"
        rm -f "${path}"
    else
        log "ausente: ${path}"
    fi
done

log "removendo icones multi-res hicolor + SVG + pixmap"
for size in 16 22 24 32 48 64 96 128 192 256 512; do
    rm -f "${HOME}/.local/share/icons/hicolor/${size}x${size}/apps/${APP_ID}.png"
done
rm -f "${HOME}/.local/share/icons/hicolor/scalable/apps/${APP_ID}.svg"
rm -f "${HOME}/.local/share/icons/hicolor/symbolic/apps/${APP_ID}-symbolic.svg"
rm -f "${HOME}/.local/share/pixmaps/${APP_ID}.png"

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -q -f "${HOME}/.local/share/icons/hicolor" 2>/dev/null || true
fi

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q "${HOME}/.local/share/applications" 2>/dev/null || true
fi

if [[ -r "${ROOT_DIR}/scripts/install_fonts.sh" ]]; then
    log "removendo as fontes que o install instalou (best-effort)"
    bash "${ROOT_DIR}/scripts/install_fonts.sh" --remove || true
fi


remover_o_applet

if [[ -f "${WIREPLUMBER_DROPIN}" ]]; then
    if head -5 "${WIREPLUMBER_DROPIN}" 2>/dev/null | grep -qiE 'recriado manualmente|workaround|standalone'; then
        log "preservando drop-in WirePlumber (marker 'recriado manualmente' no header)"
        log "  ${WIREPLUMBER_DROPIN}"
        log "  remova manualmente se não quiser mais o filtro do DualSense"
    else
        log "removendo drop-in WirePlumber: ${WIREPLUMBER_DROPIN}"
        rm -f "${WIREPLUMBER_DROPIN}"
        systemctl --user restart wireplumber >/dev/null 2>&1 || true
    fi
fi
if [[ -f "${WIREPLUMBER_DROPIN_DISABLE}" ]]; then
    log "removendo drop-in WirePlumber (disable-source): ${WIREPLUMBER_DROPIN_DISABLE}"
    rm -f "${WIREPLUMBER_DROPIN_DISABLE}"
    systemctl --user restart wireplumber >/dev/null 2>&1 || true
fi

if [[ -f "${WIREPLUMBER_DROPIN_OUTPUT}" ]]; then
    log "removendo drop-in WirePlumber (disable-output): ${WIREPLUMBER_DROPIN_OUTPUT}"
    rm -f "${WIREPLUMBER_DROPIN_OUTPUT}"
    systemctl --user restart wireplumber >/dev/null 2>&1 || true
fi

if [[ -f "${WIREPLUMBER_DROPIN_ACORDADO}" ]]; then
    log "removendo drop-in WirePlumber (nunca-dorme): ${WIREPLUMBER_DROPIN_ACORDADO}"
    rm -f "${WIREPLUMBER_DROPIN_ACORDADO}"
    systemctl --user restart wireplumber >/dev/null 2>&1 || true
fi

_wp_do_xdg="${XDG_CONFIG_HOME:-${HOME}/.config}/wireplumber/wireplumber.conf.d"
if [[ "${_wp_do_xdg}" != "${HOME}/.config/wireplumber/wireplumber.conf.d" ]]; then
    for _wp in 51-hefesto-dualsense-no-default-source.conf \
               52-hefesto-dualsense-disable-source.conf \
               53-hefesto-dualsense-disable-output.conf \
               54-hefesto-dualsense-alto-falante-nunca-dorme.conf; do
        [[ -f "${_wp_do_xdg}/${_wp}" ]] || continue
        _cabecalho="$(head -5 "${_wp_do_xdg}/${_wp}" 2>/dev/null || true)"
        if [[ "${_wp}" == 51-* ]] \
                && grep -qiE 'recriado manualmente|workaround|standalone' <<<"${_cabecalho}"; then
            log "preservando drop-in WirePlumber (marker 'recriado manualmente' no header): ${_wp_do_xdg}/${_wp}"
            continue
        fi
        log "removendo drop-in WirePlumber: ${_wp_do_xdg}/${_wp}"
        rm -f "${_wp_do_xdg}/${_wp}"
        systemctl --user restart wireplumber >/dev/null 2>&1 || true
    done
fi

for _wp_raiz in "${HOME}/.config" "${XDG_CONFIG_HOME:-${HOME}/.config}"; do
    for _wp in 51-hefesto-dualsense-no-default-source.lua \
               52-hefesto-dualsense-disable-source.lua \
               53-hefesto-dualsense-disable-output.lua \
               54-hefesto-dualsense-alto-falante-nunca-dorme.lua; do
        [[ -f "${_wp_raiz}/wireplumber/main.lua.d/${_wp}" ]] || continue
        _cabecalho="$(head -5 "${_wp_raiz}/wireplumber/main.lua.d/${_wp}" 2>/dev/null || true)"
        if [[ "${_wp}" == 51-* ]] \
                && grep -qiE 'recriado manualmente|workaround|standalone' <<<"${_cabecalho}"; then
            log "preservando drop-in WirePlumber (marker 'recriado manualmente' no header): ${_wp_raiz}/wireplumber/main.lua.d/${_wp}"
            continue
        fi
        log "removendo drop-in WirePlumber (Lua): ${_wp_raiz}/wireplumber/main.lua.d/${_wp}"
        rm -f "${_wp_raiz}/wireplumber/main.lua.d/${_wp}"
        systemctl --user restart wireplumber >/dev/null 2>&1 || true
    done
done

MEMORIA_DOS_CONTROLES_PY="${ROOT_DIR}/src/hefesto_dualsense4unix/utils/memoria_dos_controles.py"
_wp_estado="${XDG_STATE_HOME:-${HOME}/.local/state}/wireplumber"
if [[ -d "${_wp_estado}" && -f "${MEMORIA_DOS_CONTROLES_PY}" ]] \
        && command -v python3 >/dev/null 2>&1; then
    _wp_nossas="$(python3 -I -c '
import runpy, sys
from pathlib import Path
dono = runpy.run_path(sys.argv[1])
print(sum(len(v) for v in dono["chaves_nossas_do_wireplumber"](Path(sys.argv[2])).values()))
' "${MEMORIA_DOS_CONTROLES_PY}" "${_wp_estado}" 2>/dev/null || true)"
    if [[ "${_wp_nossas}" =~ ^[1-9][0-9]*$ ]]; then
        log "tirando do estado do WirePlumber ${_wp_nossas} chave(s) com nome do Hefesto (o WirePlumber para e volta)"
        systemctl --user stop wireplumber >/dev/null 2>&1 || true
        python3 "${MEMORIA_DOS_CONTROLES_PY}" wireplumber --tirar --pasta "${_wp_estado}" \
            || log "  não consegui reescrever o estado do WirePlumber em ${_wp_estado}"
        systemctl --user start wireplumber >/dev/null 2>&1 || true
    fi
fi

if [[ -f "${MARCA_MIC_PEDIDO}" ]]; then
    log "removendo a marca do gesto do microfone: ${MARCA_MIC_PEDIDO}"
    rm -f "${MARCA_MIC_PEDIDO}"
fi

if [[ -f "${ENVIRONMENTD_GAMEMODE}" ]]; then
    log "removendo environment.d do modo-jogo: ${ENVIRONMENTD_GAMEMODE}"
    rm -f "${ENVIRONMENTD_GAMEMODE}"
fi

_abrir_a_regra_do_no_que_fica() {
    local regra aberta efetivas
    for regra in /etc/udev/rules.d/73-hefesto-ps5-controller.rules \
                 /etc/udev/rules.d/70-ps5-controller.rules; do
        [[ -f "${regra}" ]] || continue
        efetivas="$(grep -v '^[[:space:]]*#' "${regra}" 2>/dev/null || true)"
        [[ "${efetivas}" == *'TAG-="uaccess"'* ]] || continue
        if [[ "${DRY_RUN}" -eq 1 ]]; then
            _faria "(root) trocar ${regra} pela variante aberta (scripts/regra_do_no_aberta.sh): o broker sai"
            continue
        fi
        aberta=""
        if aberta="$(mktemp)" \
                && bash "${ROOT_DIR}/scripts/regra_do_no_aberta.sh" "${regra}" "${aberta}" >/dev/null 2>&1 \
                && [[ -s "${aberta}" ]]; then
            log "a regra do nó preservada vira a variante aberta (o broker sai): ${regra}"
            sudo install -Dm644 "${aberta}" "${regra}"
        else
            log "a regra do nó preservada não reabre — sai junto com o broker: ${regra}"
            sudo rm -f "${regra}"
        fi
        if [[ -n "${aberta}" ]]; then
            rm -f "${aberta}"
        fi
    done
    return 0
}

if [[ "${REMOVE_UDEV}" -eq 1 ]]; then
    log "removendo udev rules + modules-load uinput (sudo)"
    if ! sudo -n true 2>/dev/null; then
        log "ERRO: sudo recusado/sem TTY — udev rules NÃO foram removidas."
        log "      reexecute ./uninstall.sh ${*:-} nesta sessão, de forma interativa"
        log "      (a senha é pedida uma vez), ou exporte SUDO_ASKPASS antes de rodar."
    else
        sudo rm -f /etc/udev/rules.d/73-hefesto-ps5-controller.rules \
                   /etc/udev/rules.d/70-ps5-controller.rules \
                   /etc/udev/rules.d/71-uinput.rules \
                   /etc/udev/rules.d/72-ps5-controller-autosuspend.rules \
                   /etc/udev/rules.d/72-hefesto-touchpad-motion-uaccess.rules \
                   /etc/udev/rules.d/73-ps5-controller-hotplug.rules \
                   /etc/udev/rules.d/74-ps5-controller-hotplug-bt.rules \
                   /etc/udev/rules.d/75-ps5-controller-disable-usb-audio.rules \
                   /etc/udev/rules.d/76-dualsense-touchpad-libinput-ignore.rules \
                   /etc/udev/rules.d/77-dualsense-leds.rules \
                   /etc/udev/rules.d/78-dualsense-motion-not-joystick.rules \
                   /etc/udev/rules.d/79-external-controller-leds.rules \
                   /etc/udev/rules.d/80-motion-joydev-hide.rules \
                   /etc/udev/rules.d/81-hefesto-usb-power.rules \
                   /etc/udev/rules.d/81-hefesto-usb-host-power.rules \
                   /etc/udev/rules.d/71-uhid.rules \
                   /etc/udev/rules.d/82-nintendo-pro-nosniff.rules \
                   /etc/udev/rules.d/83-hefesto-bond-snapshot.rules \
                   /etc/udev/rules.d/84-nintendo-pro-variant.rules \
                   /etc/udev/rules.d/85-hefesto-o-cabo-assume.rules \
                   /etc/modules-load.d/hefesto-dualsense4unix.conf \
                   /etc/modprobe.d/hefesto-btusb-no-autosuspend.conf
        sudo udevadm control --reload-rules
        sudo udevadm trigger --action=change --subsystem-match=usb 2>/dev/null || true
        sudo udevadm trigger --action=change --subsystem-match=hidraw 2>/dev/null || true
        sudo udevadm trigger --action=change --subsystem-match=input 2>/dev/null || true
        log "removendo grupo 'hefesto' (dono de /dev/uhid e /dev/uinput)"
        sudo gpasswd -d "$(id -un)" hefesto >/dev/null 2>&1 || true
        sudo groupdel hefesto 2>/dev/null || true
    fi
else
    if sudo -n true 2>/dev/null; then
        _abrir_a_regra_do_no_que_fica
    elif [[ -f /etc/udev/rules.d/73-hefesto-ps5-controller.rules \
            || -f /etc/udev/rules.d/70-ps5-controller.rules ]]; then
        log "sudo indisponível — a regra do nó ficou como estava, e sem o broker ela não pode ficar fechada:"
        log "  sudo rm -f /etc/udev/rules.d/73-hefesto-ps5-controller.rules /etc/udev/rules.d/70-ps5-controller.rules"
    fi
    log "udev rules preservadas (--keep-udev). Para remover depois:"
    log "  sudo rm /etc/udev/rules.d/73-hefesto-ps5-controller.rules /etc/udev/rules.d/70-ps5-controller.rules /etc/udev/rules.d/71-uinput.rules /etc/udev/rules.d/71-uhid.rules /etc/udev/rules.d/72-ps5-controller-autosuspend.rules /etc/udev/rules.d/72-hefesto-touchpad-motion-uaccess.rules /etc/udev/rules.d/75-ps5-controller-disable-usb-audio.rules /etc/udev/rules.d/76-dualsense-touchpad-libinput-ignore.rules /etc/udev/rules.d/77-dualsense-leds.rules /etc/udev/rules.d/78-dualsense-motion-not-joystick.rules /etc/udev/rules.d/79-external-controller-leds.rules /etc/udev/rules.d/80-motion-joydev-hide.rules /etc/udev/rules.d/81-hefesto-usb-power.rules /etc/udev/rules.d/81-hefesto-usb-host-power.rules /etc/udev/rules.d/82-nintendo-pro-nosniff.rules /etc/udev/rules.d/83-hefesto-bond-snapshot.rules /etc/udev/rules.d/84-nintendo-pro-variant.rules /etc/udev/rules.d/85-hefesto-o-cabo-assume.rules /etc/modules-load.d/hefesto-dualsense4unix.conf /etc/modprobe.d/hefesto-btusb-no-autosuspend.conf"
    log "  as 82 e 83 chamam alvos por RUN+= — os alvos ficaram junto com elas."
    log "  Ao remover as regras, remova também:"
    log "  sudo rm /usr/local/lib/hefesto-dualsense4unix/bt_nosniff_now.sh /usr/local/lib/hefesto-dualsense4unix/bt_bonds_snapshot.sh /etc/systemd/system/hefesto-bt-bonds-snapshot.service"
fi

if sudo -n true 2>/dev/null; then
    if [[ -e /etc/modprobe.d/hefesto-dualsense-storm.conf ]]; then
        log "removendo cura de raiz do storm (modprobe.d, independente de --keep-udev)"
        sudo rm -f /etc/modprobe.d/hefesto-dualsense-storm.conf
        [[ -e /sys/module/snd_usb_audio/parameters/quirk_flags ]] && \
            printf '' | sudo tee /sys/module/snd_usb_audio/parameters/quirk_flags >/dev/null 2>&1 || true
    fi
elif [[ -e /etc/modprobe.d/hefesto-dualsense-storm.conf ]]; then
    log "sudo indisponível — cura de raiz do storm (modprobe.d) NÃO removida"
    log "  sudo rm /etc/modprobe.d/hefesto-dualsense-storm.conf"
fi

UCM_VERBO=/usr/share/alsa/ucm2/USB-Audio/Hefesto/DualSense-HiFi.conf
if [[ -e "${UCM_VERBO}" ]]; then
    if sudo -n true 2>/dev/null; then
        log "removendo o perfil UCM do DualSense"
        bash "${ROOT_DIR}/scripts/install_ucm_dualsense.sh" --remover || \
            log "  ERRO: remoção adiada — rode: bash scripts/install_ucm_dualsense.sh --remover"
    else
        log "sudo indisponível — perfil UCM do DualSense NÃO removido"
        log "  bash scripts/install_ucm_dualsense.sh --remover"
    fi
fi

if [[ -e /etc/systemd/system/hefesto-desempenho.service \
      || -e /etc/modprobe.d/hefesto-desempenho-nvidia.conf \
      || -e /etc/modprobe.d/hefesto-desempenho-audio.conf \
      || -e /etc/tmpfiles.d/hefesto-desempenho-aspm.conf ]]; then
    if sudo -n true 2>/dev/null; then
        log "removendo o modo desempenho (unit do perfil de energia, modprobe.d e tmpfiles.d)"
        bash "${ROOT_DIR}/scripts/desempenho.sh" remover \
            || log "  ERRO: remoção adiada — rode: bash scripts/desempenho.sh remover"
    else
        log "sudo indisponível — o modo desempenho NÃO foi removido"
        log "  (rode: bash ${ROOT_DIR}/scripts/desempenho.sh remover)"
    fi
fi

if sudo -n true 2>/dev/null; then
    log "removendo config do BlueZ do hefesto (bloco do main.conf + drop-ins)"
    HEFESTO_BT_ASSETS="${ROOT_DIR}/assets/bluetooth" \
        bash "${ROOT_DIR}/scripts/bluez_config.sh" remover \
        || log "  ERRO: remoção da config do BlueZ falhou — confira /etc/bluetooth/main.conf"
elif [[ -e /etc/bluetooth/main.conf.d/hefesto-fastconnectable.conf ]] \
     || [[ -e /etc/bluetooth/main.conf.d/hefesto-justworks.conf ]] \
     || grep -qsE '^# >>> hefesto (bluetooth|FastConnectable|JustWorksRepairing) >>>' \
             /etc/bluetooth/main.conf 2>/dev/null; then
    log "sudo indisponível — config do BlueZ do hefesto NÃO removida"
    log "  (rode: sudo bash ${ROOT_DIR}/scripts/bluez_config.sh remover)"
fi

if sudo -n true 2>/dev/null; then
    if [[ -e /etc/systemd/system/hefesto-bt-bonds-snapshot.timer \
          || -e /etc/systemd/system/hefesto-bt-health-watchdog.timer ]]; then
        log "desabilitando timers de resiliência do bluetoothd (snapshot de bonds + watchdog)"
        sudo systemctl disable --now hefesto-bt-bonds-snapshot.timer \
            hefesto-bt-health-watchdog.timer >/dev/null 2>&1 || true
    fi
    sudo rm -f /etc/systemd/system/hefesto-bt-bonds-snapshot.timer \
        /etc/systemd/system/hefesto-bt-health-watchdog.service \
        /etc/systemd/system/hefesto-bt-health-watchdog.timer 2>/dev/null || true
    sudo rm -f /etc/systemd/system/hefesto-bt-health-watchdog.service.d/10-hefesto-maquina.conf 2>/dev/null || true
    sudo rmdir /etc/systemd/system/hefesto-bt-health-watchdog.service.d 2>/dev/null || true
    if [[ -e /etc/systemd/system/bluetooth.service.d/10-hefesto-resilience.conf \
          || -e /etc/systemd/system/bluetooth.service.d/90-hefesto-debug.conf ]]; then
        log "removendo drop-ins do bluetooth.service (resiliência + debug forense)"
        sudo rm -f /etc/systemd/system/bluetooth.service.d/10-hefesto-resilience.conf \
            /etc/systemd/system/bluetooth.service.d/90-hefesto-debug.conf 2>/dev/null || true
        sudo rmdir /etc/systemd/system/bluetooth.service.d 2>/dev/null || true
    fi
    if [[ -f /etc/sysctl.d/99-hefesto-bt-coredump.conf ]]; then
        log "removendo captura forense do core_pattern (sysctl.d) e reaplicando defaults"
        sudo rm -f /etc/sysctl.d/99-hefesto-bt-coredump.conf
        sudo sysctl --system >/dev/null 2>&1 || true
    fi
    sudo rm -f /usr/local/lib/hefesto-dualsense4unix/bt_bonds_restore.sh \
        /usr/local/lib/hefesto-dualsense4unix/bt_bonds_autorestore.sh \
        /usr/local/lib/hefesto-dualsense4unix/bt_health_watchdog.sh \
        /usr/local/lib/hefesto-dualsense4unix/bt_crash_capture.sh \
        /usr/local/lib/hefesto-dualsense4unix/bt_active_mode.sh \
        /usr/local/lib/hefesto-dualsense4unix/bt_rebind_orphans.sh 2>/dev/null || true
    if [[ -e /etc/sudoers.d/49-hefesto-bt-ponte ]]; then
        log "removendo a regra da ponte privilegiada do Bluetooth (/etc/sudoers.d/49-hefesto-bt-ponte)"
        sudo rm -f /etc/sudoers.d/49-hefesto-bt-ponte 2>/dev/null || true
    fi
    sudo rm -f /usr/local/lib/hefesto-dualsense4unix/bt_ponte_privilegiada.sh 2>/dev/null || true
    if [[ -x /usr/local/lib/hefesto-dualsense4unix/hefesto_placa_acordada.sh ]]; then
        printf '0\n' | sudo bash /usr/local/lib/hefesto-dualsense4unix/hefesto_placa_acordada.sh devolver \
            >/dev/null 2>&1 || true
    fi
    if [[ -e /etc/sudoers.d/49-hefesto-placa ]]; then
        log "removendo a regra da placa acordada (/etc/sudoers.d/49-hefesto-placa)"
        sudo rm -f /etc/sudoers.d/49-hefesto-placa 2>/dev/null || true
    fi
    sudo rm -f /usr/local/lib/hefesto-dualsense4unix/hefesto_placa_acordada.sh 2>/dev/null || true
    sudo rm -rf /run/hefesto-dualsense4unix/placa 2>/dev/null || true
    sudo rm -rf /run/hefesto-bt-ponte /run/hefesto-bt-rebind /run/hefesto-bt-watchdog \
        /run/hefesto-bt-watchdog.restart-stamp 2>/dev/null || true
    if [[ -e /etc/tmpfiles.d/hefesto-dualsense4unix-radio.conf || -d /run/hefesto-dualsense4unix ]]; then
        log "removendo a trava comum do rádio (tmpfiles.d + /run/hefesto-dualsense4unix)"
        sudo rm -f /etc/tmpfiles.d/hefesto-dualsense4unix-radio.conf \
            /run/hefesto-dualsense4unix/radio.lock 2>/dev/null || true
        sudo rmdir /run/hefesto-dualsense4unix 2>/dev/null || true
    fi
    if [[ "${REMOVE_UDEV}" -eq 1 ]]; then
        sudo rm -f /etc/systemd/system/hefesto-bt-bonds-snapshot.service \
            /usr/local/lib/hefesto-dualsense4unix/bt_bonds_snapshot.sh \
            /usr/local/lib/hefesto-dualsense4unix/bt_nosniff_now.sh 2>/dev/null || true
    else
        log "alvos das regras 82/83 preservados (--keep-udev): bt_nosniff_now.sh,"
        log "  bt_bonds_snapshot.sh e hefesto-bt-bonds-snapshot.service — sem eles as"
        log "  regras que ficaram virariam enfeite (o TEST== delas não acharia o alvo)."
    fi
    _hcis=()
    for _hci_p in "${HEFESTO_SYSFS_BLUETOOTH:-/sys/class/bluetooth}"/hci*; do
        [[ -e "${_hci_p}" ]] || continue
        [[ "${_hci_p##*/}" =~ ^hci[0-9]+$ ]] || continue
        _hcis+=("${_hci_p##*/}")
    done
    if [[ "${#_hcis[@]}" -eq 0 ]] && command -v busctl >/dev/null 2>&1; then
        mapfile -t _hcis < <(busctl tree org.bluez --list 2>/dev/null \
            | grep -oE '/org/bluez/hci[0-9]+' | sed 's#.*/##' | sort -u || true)
    fi
    if [[ "${#_hcis[@]}" -eq 0 ]] && command -v btmgmt >/dev/null 2>&1; then
        mapfile -t _hcis < <(timeout 5 btmgmt info 2>/dev/null | grep -oE '^hci[0-9]+' | sort -u || true)
    fi
    if [[ "${#_hcis[@]}" -eq 0 ]] && command -v hciconfig >/dev/null 2>&1; then
        mapfile -t _hcis < <(hciconfig 2>/dev/null | awk -F: '/^hci/{print $1}' || true)
    fi
    _nomes_do_hefesto=()
    _maquina_json="${XDG_CONFIG_HOME:-${HOME}/.config}/hefesto-dualsense4unix/maquina.json"
    if [[ -f "${_maquina_json}" ]] && command -v python3 >/dev/null 2>&1; then
        mapfile -t _nomes_do_hefesto < <(python3 -I -c '
import json, sys
def ler(caminho):
    try:
        with open(caminho, encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}
def de(registro):
    return list(registro.values()) if isinstance(registro, dict) else []
doc = ler(sys.argv[1])
copia = ler(sys.argv[1] + ".com-os-lugares")
mapa = doc.get("mapa") if isinstance(doc.get("mapa"), dict) else {}
registros = de(doc.get("adaptadores")) + de(mapa.get("portas"))
registros += de(doc.get("lugares")) + de(copia.get("lugares"))
for dele in registros:
    nome = dele.get("nome") if isinstance(dele, dict) else None
    if isinstance(nome, str) and nome.strip() and "\n" not in nome:
        print(nome.strip())
' "${_maquina_json}" 2>/dev/null || true)
    fi
    _texto_do_adaptador() {
        local bruto
        bruto="$(busctl get-property org.bluez "/org/bluez/$1" org.bluez.Adapter1 "$2" --json=short 2>/dev/null || true)"
        bruto="$(sed -nE 's/^.*"data":"(.*)"\}$/\1/p' <<<"${bruto}")"
        if [[ -z "${bruto}" ]]; then
            bruto="$(busctl get-property org.bluez "/org/bluez/$1" org.bluez.Adapter1 "$2" 2>/dev/null | sed -E 's/^s "?//; s/"?$//' || true)"
        fi
        [[ "${bruto}" == *\\* ]] && return 0
        printf '%s\n' "${bruto}"
    }
    for _hci in ${_hcis[@]+"${_hcis[@]}"}; do
        if command -v hciconfig >/dev/null 2>&1; then
            sudo hciconfig "${_hci}" lp rswitch,hold,sniff,park 2>/dev/null || true
        else
            log "link policy de ${_hci} NÃO revertida: só o 'hciconfig' escreve"
            log "  link policy (ioctl HCIGETDEVINFO) e ele não está nesta máquina"
            log "  (pacote bluez-deprecated / bluez-deprecated-tools). O SNIFF do"
            log "  adaptador segue como a cura do Pro o deixou — instale o pacote e"
            log "  rode: sudo hciconfig ${_hci} lp rswitch,hold,sniff,park"
        fi
        command -v busctl >/dev/null 2>&1 || continue
        _alias="$(_texto_do_adaptador "${_hci}" Alias)"
        [[ -n "${_alias}" ]] || continue
        _nome_do_sistema="$(_texto_do_adaptador "${_hci}" Name)"
        _base="${_alias#Nintendo }"
        _e_do_hefesto=0
        for _um_nome in ${_nomes_do_hefesto[@]+"${_nomes_do_hefesto[@]}"}; do
            [[ "${_base}" == "${_um_nome}" ]] && _e_do_hefesto=1
        done
        if [[ "${_alias}" == Nintendo\ * && -n "${_nome_do_sistema}" && "${_base% #[0-9]*}" == "${_nome_do_sistema% #[0-9]*}" ]]; then
            _e_do_hefesto=1
        fi
        if [[ "${_e_do_hefesto}" -eq 1 ]]; then
            sudo busctl set-property org.bluez "/org/bluez/${_hci}" org.bluez.Adapter1 Alias s "" 2>/dev/null || true
            log "nome do adaptador ${_hci} devolvido ao padrão do sistema${_nome_do_sistema:+ ('${_nome_do_sistema}')} — '${_alias}' era do Hefesto"
        elif [[ "${_alias}" == Nintendo\ * ]]; then
            sudo busctl set-property org.bluez "/org/bluez/${_hci}" org.bluez.Adapter1 Alias s "${_base}" 2>/dev/null || true
            log "nome do adaptador revertido para '${_base}' (tirado o prefixo Nintendo)"
        fi
    done
    _carimbo_do_acervo="$(date +%Y%m%d-%H%M%S)"
    if [[ -d /var/lib/hefesto-dualsense4unix/bt-bonds ]]; then
        if [[ "${KEEP_CONFIG}" -eq 1 ]]; then
            _bonds_destino="/var/lib/hefesto-dualsense4unix/bt-bonds.pre-uninstall-${_carimbo_do_acervo}"
            log "preservando snapshots de bonds (contêm LinkKeys) em ${_bonds_destino}"
            log "  para restaurar: sudo cp -a ${_bonds_destino}/. /var/lib/hefesto-dualsense4unix/bt-bonds/"
            log "  para apagar de vez: rode o uninstall com --purge-config"
            sudo mv "/var/lib/hefesto-dualsense4unix/bt-bonds" "${_bonds_destino}" 2>/dev/null \
                || sudo rm -rf /var/lib/hefesto-dualsense4unix/bt-bonds
        else
            log "removendo snapshots de bonds em /var/lib/hefesto-dualsense4unix/bt-bonds (--purge-config)"
            log "  (contêm LinkKeys — wipe pedido explicitamente)"
            sudo rm -rf /var/lib/hefesto-dualsense4unix/bt-bonds
        fi
    fi
    _diarios_root=()
    for _diario_root in /var/lib/hefesto-dualsense4unix/radio-diario.jsonl \
                        /var/lib/hefesto-dualsense4unix/radio-diario.jsonl.1; do
        [[ -f "${_diario_root}" ]] && _diarios_root+=("${_diario_root}")
    done
    if [[ "${#_diarios_root[@]}" -gt 0 ]]; then
        if [[ "${KEEP_CONFIG}" -eq 1 ]]; then
            _bonds_destino="/var/lib/hefesto-dualsense4unix/bt-bonds.pre-uninstall-${_carimbo_do_acervo}"
            log "guardando o diário do rádio do root junto dos bonds, em ${_bonds_destino}/"
            sudo install -d -m700 "${_bonds_destino}" 2>/dev/null || true
            sudo mv -f "${_diarios_root[@]}" "${_bonds_destino}/" 2>/dev/null || true
        else
            log "removendo o diário do rádio do root (--purge-config)"
            sudo rm -f "${_diarios_root[@]}" 2>/dev/null || true
        fi
    fi
    if [[ "${KEEP_CONFIG}" -eq 0 ]]; then
        for _copia_antiga in /var/lib/hefesto-dualsense4unix/bt-bonds.pre-uninstall-*; do
            [[ -e "${_copia_antiga}" || -L "${_copia_antiga}" ]] || continue
            log "removendo a cópia de pareamento de um uninstall anterior (--purge-config): ${_copia_antiga}"
            sudo rm -rf -- "${_copia_antiga}" 2>/dev/null \
                || log "  ela FICOU — apague à mão: sudo rm -rf ${_copia_antiga}"
        done
    fi
    if [[ "${REMOVE_UDEV}" -eq 1 ]]; then
        sudo rmdir /var/lib/hefesto-dualsense4unix 2>/dev/null || true
    fi
    sudo systemctl daemon-reload >/dev/null 2>&1 || true
elif [[ -e /etc/systemd/system/hefesto-bt-bonds-snapshot.timer \
        || -e /etc/systemd/system/bluetooth.service.d/10-hefesto-resilience.conf \
        || -e /etc/tmpfiles.d/hefesto-dualsense4unix-radio.conf \
        || -e /etc/sudoers.d/49-hefesto-bt-ponte \
        || -e /etc/sudoers.d/49-hefesto-placa ]]; then
    log "sudo indisponível — resiliência do bluetoothd (timers/drop-ins/scripts) NÃO removida"
    if [[ -e /etc/tmpfiles.d/hefesto-dualsense4unix-radio.conf ]]; then
        log "  nem a trava comum do rádio:"
        log "  sudo rm -f /etc/tmpfiles.d/hefesto-dualsense4unix-radio.conf /run/hefesto-dualsense4unix/radio.lock && sudo rmdir /run/hefesto-dualsense4unix"
    fi
    if [[ -e /etc/sudoers.d/49-hefesto-bt-ponte ]]; then
        log "  e a ponte privilegiada FICOU: é privilégio de root pendurado, remova à mão —"
        log "  sudo rm /etc/sudoers.d/49-hefesto-bt-ponte /usr/local/lib/hefesto-dualsense4unix/bt_ponte_privilegiada.sh"
    fi
    if [[ -e /etc/sudoers.d/49-hefesto-placa ]]; then
        log "  e a placa acordada FICOU: é privilégio de root pendurado, remova à mão —"
        log "  sudo rm /etc/sudoers.d/49-hefesto-placa /usr/local/lib/hefesto-dualsense4unix/hefesto_placa_acordada.sh"
    fi
fi
if [[ "${KEEP_CONFIG}" -eq 0 ]] && ! sudo -n true 2>/dev/null \
    && compgen -G '/var/lib/hefesto-dualsense4unix/bt-bonds.pre-uninstall-*' >/dev/null 2>&1; then
    log "sudo indisponível — as cópias de pareamento de uninstalls anteriores FICARAM (têm LinkKeys):"
    log "  sudo rm -rf /var/lib/hefesto-dualsense4unix/bt-bonds.pre-uninstall-*"
fi

if [[ -e /etc/systemd/system/hefesto-bt-agent.service ]]; then
    if sudo -n true 2>/dev/null; then
        log "desabilitando e removendo hefesto-bt-agent.service (sudo)"
        sudo systemctl disable --now hefesto-bt-agent.service >/dev/null 2>&1 || true
        sudo rm -f /etc/systemd/system/hefesto-bt-agent.service
        sudo systemctl daemon-reload >/dev/null 2>&1 || true
    else
        log "sudo indisponível — hefesto-bt-agent.service NÃO removido"
        log "  sudo systemctl disable --now hefesto-bt-agent.service && sudo rm /etc/systemd/system/hefesto-bt-agent.service"
    fi
fi

BROKER_BIN="/usr/local/lib/hefesto-dualsense4unix/hefesto-hidraw-broker"
BROKER_SERVICE="/etc/systemd/system/hefesto-hidraw-broker.service"
BROKER_SOCKET="/etc/systemd/system/hefesto-hidraw-broker.socket"
BROKER_OWNER_FILE="${HOME}/.local/state/hefesto-dualsense4unix/broker-owner.conf"
if [[ -e "${BROKER_SERVICE}" || -e "${BROKER_SOCKET}" || -e "${BROKER_BIN}" ]]; then
    if sudo -n true 2>/dev/null; then
        log "desabilitando hefesto-hidraw-broker (socket + service — dispara restore-all no stop)"
        sudo systemctl disable --now hefesto-hidraw-broker.socket hefesto-hidraw-broker.service \
            >/dev/null 2>&1 || true
        if [[ -x "${BROKER_BIN}" ]]; then
            log "belt: restore-all-and-exit explícito (cobre unit editada/broker morto)"
            sudo "${BROKER_BIN}" --restore-all-and-exit >/dev/null 2>&1 || true
        fi
        if [[ -f "${BROKER_OWNER_FILE}" ]]; then
            while IFS='=' read -r _bp _bsum; do
                [[ -z "${_bp}" ]] && continue
                if grep -qF 'instalado por hefesto-dualsense4unix' "${_bp}" 2>/dev/null \
                        || [[ "${_bp}" == "${BROKER_BIN}" ]]; then
                    log "removendo ${_bp}"
                    sudo rm -f "${_bp}"
                else
                    log "aviso: ${_bp} não carrega o header do hefesto — NÃO removido"
                fi
            done < "${BROKER_OWNER_FILE}"
        else
            log "sem registro de posse (${BROKER_OWNER_FILE} ausente) — removendo caminhos canônicos"
            [[ -e "${BROKER_SERVICE}" ]] && sudo rm -f "${BROKER_SERVICE}"
            [[ -e "${BROKER_SOCKET}" ]] && sudo rm -f "${BROKER_SOCKET}"
            [[ -e "${BROKER_BIN}" ]] && sudo rm -f "${BROKER_BIN}"
        fi
        sudo rm -f "${BROKER_OWNER_FILE}"
        sudo rm -rf /run/hefesto-hidraw-broker 2>/dev/null || true
        sudo systemctl daemon-reload >/dev/null 2>&1 || true
    else
        log "sudo indisponível — broker hide-hidraw NÃO removido"
        log "  sudo systemctl disable --now hefesto-hidraw-broker.socket hefesto-hidraw-broker.service"
        log "  sudo ${BROKER_BIN} --restore-all-and-exit"
        log "  sudo rm -f ${BROKER_SERVICE} ${BROKER_SOCKET} ${BROKER_BIN} ${BROKER_OWNER_FILE}"
    fi
fi

if [[ -e /etc/systemd/system/hefesto-wifi-usb-vigia.timer \
      || -e /etc/systemd/system/hefesto-wifi-usb-vigia.service \
      || -e /etc/NetworkManager/dispatcher.d/90-hefesto-wifi-usb \
      || -e /usr/local/lib/hefesto-dualsense4unix/wifi_usb.sh ]]; then
    if sudo -n true 2>/dev/null; then
        log "removendo o vigia do Wi-Fi USB (timer, unit, dispatcher do NetworkManager e script)"
        sudo systemctl disable --now hefesto-wifi-usb-vigia.timer >/dev/null 2>&1 || true
        sudo rm -f /etc/systemd/system/hefesto-wifi-usb-vigia.timer \
            /etc/systemd/system/hefesto-wifi-usb-vigia.service \
            /etc/NetworkManager/dispatcher.d/90-hefesto-wifi-usb \
            /usr/local/lib/hefesto-dualsense4unix/wifi_usb.sh 2>/dev/null || true
        sudo rm -rf /run/hefesto-wifi-usb 2>/dev/null || true
        sudo systemctl daemon-reload >/dev/null 2>&1 || true
        log "  o scan de fundo não é religado: a próxima associação nasce com o default do NetworkManager"
    else
        log "sudo indisponível — o vigia do Wi-Fi USB NÃO foi removido"
        log "  sudo systemctl disable --now hefesto-wifi-usb-vigia.timer"
        log "  sudo rm -f /etc/systemd/system/hefesto-wifi-usb-vigia.timer /etc/systemd/system/hefesto-wifi-usb-vigia.service /etc/NetworkManager/dispatcher.d/90-hefesto-wifi-usb /usr/local/lib/hefesto-dualsense4unix/wifi_usb.sh"
    fi
fi

if [[ -d /usr/local/lib/hefesto-dualsense4unix ]] && sudo -n true 2>/dev/null; then
    sudo rmdir /usr/local/lib/hefesto-dualsense4unix 2>/dev/null || true
fi

if ! command -v dkms >/dev/null 2>&1; then
    _orfaos=""
    for _pkg in hefesto-hid-nintendo hefesto-rtw88-usb hefesto-hid-playstation hefesto-usb-f-hid; do
        compgen -G "/usr/src/${_pkg}-*" >/dev/null 2>&1 && _orfaos="${_orfaos} ${_pkg}(src)"
    done
    for _ko in hid-nintendo rtw88_usb hid-playstation usb_f_hid; do
        compgen -G "/lib/modules/$(uname -r)/updates/dkms/${_ko}.ko*" >/dev/null 2>&1 \
            && _orfaos="${_orfaos} ${_ko}(.ko)"
    done
    if [[ -n "${_orfaos}" ]]; then
        log "AVISO: dkms ausente, mas há artefato DKMS do hefesto órfão:${_orfaos}"
        log "  o .ko em updates/dkms segue vencendo o in-tree — instale o dkms e re-rode ./uninstall.sh,"
        log "  ou remova à mão: sudo rm -rf /usr/src/hefesto-* /lib/modules/\$(uname -r)/updates/dkms/{hid-nintendo,rtw88_usb,hid-playstation,usb_f_hid}.ko* && sudo depmod -a && sudo update-initramfs -u"
    fi
fi

if command -v dkms >/dev/null 2>&1 \
        && [[ -n "$(dkms status hefesto-hid-nintendo 2>/dev/null)" ]]; then
    if sudo -n true 2>/dev/null; then
        log "removendo o módulo hid-nintendo corrigido (DKMS): dkms remove --all"
        # shellcheck source=scripts/dkms_lib.sh
        source "${ROOT_DIR}/scripts/dkms_lib.sh"
        dkms_remove_patched_module hefesto-hid-nintendo \
            "$(dkms_pkg_version "${ROOT_DIR}/assets/dkms/hid-nintendo")" \
            hid-nintendo
    else
        log "sudo indisponível — patch DKMS do hid-nintendo NÃO removido"
        log "  sudo dkms remove hefesto-hid-nintendo/1.0.0 --all"
    fi
fi
if [[ -e /etc/modprobe.d/hefesto-hid-nintendo.conf ]]; then
    if sudo -n true 2>/dev/null; then
        log "removendo opções do hid-nintendo patchado (/etc/modprobe.d/hefesto-hid-nintendo.conf)"
        sudo rm -f /etc/modprobe.d/hefesto-hid-nintendo.conf
        if [[ -d /sys/module/hid_nintendo/parameters ]]; then
            printf '0' | sudo tee /sys/module/hid_nintendo/parameters/bt_probe_retries >/dev/null 2>&1 || true
            printf '0' | sudo tee /sys/module/hid_nintendo/parameters/skip_tx_on_rate_exceeded >/dev/null 2>&1 || true
            printf '0' | sudo tee /sys/module/hid_nintendo/parameters/usb_cmd_pad_to_report >/dev/null 2>&1 || true
            printf '0' | sudo tee /sys/module/hid_nintendo/parameters/usb_send_conn_status >/dev/null 2>&1 || true
            printf '0' | sudo tee /sys/module/hid_nintendo/parameters/usb_probe_degrade >/dev/null 2>&1 || true
            log "params vivos do hid_nintendo devolvidos a 0 (comportamento vanilla até o boot)"
        fi
    else
        log "sudo indisponível — /etc/modprobe.d/hefesto-hid-nintendo.conf NÃO removido"
        log "  sudo rm -f /etc/modprobe.d/hefesto-hid-nintendo.conf"
    fi
fi

if command -v dkms >/dev/null 2>&1 \
        && [[ -n "$(dkms status hefesto-rtw88-usb 2>/dev/null)" ]]; then
    if sudo -n true 2>/dev/null; then
        log "removendo o módulo rtw88_usb corrigido (DKMS): dkms remove --all"
        # shellcheck source=scripts/dkms_lib.sh
        source "${ROOT_DIR}/scripts/dkms_lib.sh"
        dkms_remove_patched_module hefesto-rtw88-usb \
            "$(dkms_pkg_version "${ROOT_DIR}/assets/dkms/rtw88-usb")" \
            rtw88_usb
        if [[ -e /sys/module/rtw88_usb/parameters/hang_reset ]]; then
            printf '0' | sudo tee /sys/module/rtw88_usb/parameters/hang_reset >/dev/null 2>&1 || true
            log "hang_reset do rtw88_usb devolvido a 0 (sem reset agressivo até o boot; detecção/silenciamento seguem ativos)"
        fi
    else
        log "sudo indisponível — patch DKMS do rtw88_usb NÃO removido"
        log "  sudo dkms remove hefesto-rtw88-usb/1.0.0 --all"
    fi
fi

if command -v dkms >/dev/null 2>&1 \
        && [[ -n "$(dkms status hefesto-hid-playstation 2>/dev/null)" ]]; then
    if sudo -n true 2>/dev/null; then
        log "removendo patch DKMS do hid-playstation (contenção BT): dkms remove --all"
        # shellcheck source=scripts/dkms_lib.sh
        source "${ROOT_DIR}/scripts/dkms_lib.sh"
        dkms_remove_patched_module hefesto-hid-playstation \
            "$(dkms_pkg_version "${ROOT_DIR}/assets/dkms/hid-playstation")" \
            hid-playstation
    else
        log "sudo indisponível — patch DKMS do hid-playstation NÃO removido"
        log "  sudo dkms remove hefesto-hid-playstation/1.0.0 --all"
    fi
fi
if [[ -e /etc/modprobe.d/hefesto-hid-playstation.conf ]]; then
    if sudo -n true 2>/dev/null; then
        log "removendo opções do hid-playstation patchado (/etc/modprobe.d/hefesto-hid-playstation.conf)"
        sudo rm -f /etc/modprobe.d/hefesto-hid-playstation.conf
        if [[ -e /sys/module/hid_playstation/parameters/feature_retries ]]; then
            printf '0' | sudo tee /sys/module/hid_playstation/parameters/feature_retries >/dev/null 2>&1 || true
            log "feature_retries do hid_playstation devolvido a 0 (vanilla já na próxima conexão; NUNCA recarregamos o módulo)"
        fi
        if [[ -e /sys/module/hid_playstation/parameters/ds4_short_pairing_info ]]; then
            printf 'N' | sudo tee /sys/module/hid_playstation/parameters/ds4_short_pairing_info >/dev/null 2>&1 || true
            log "ds4_short_pairing_info devolvido a N (vanilla na próxima conexão)"
        fi
        if [[ -e /sys/module/hid_playstation/parameters/ds4_synthetic_mac ]]; then
            printf 'N' | sudo tee /sys/module/hid_playstation/parameters/ds4_synthetic_mac >/dev/null 2>&1 || true
            log "ds4_synthetic_mac devolvido a N (vanilla na próxima conexão)"
        fi
    else
        log "sudo indisponível — /etc/modprobe.d/hefesto-hid-playstation.conf NÃO removido"
        log "  sudo rm -f /etc/modprobe.d/hefesto-hid-playstation.conf"
    fi
fi

if command -v dkms >/dev/null 2>&1 \
        && [[ -n "$(dkms status hefesto-usb-f-hid 2>/dev/null)" ]]; then
    if sudo -n true 2>/dev/null; then
        log "removendo o patch DKMS do usb_f_hid (hefesto-usb-f-hid): dkms remove --all"
        # shellcheck source=scripts/dkms_lib.sh
        source "${ROOT_DIR}/scripts/dkms_lib.sh"
        dkms_remove_patched_module hefesto-usb-f-hid \
            "$(dkms_pkg_version "${ROOT_DIR}/assets/dkms/usb-f-hid")" \
            usb_f_hid
    else
        log "sudo indisponível — patch DKMS do usb_f_hid NÃO removido"
        log "  sudo dkms remove hefesto-usb-f-hid/1.0.0 --all"
    fi
fi

if grep -q '^hefesto-uhid' <<<"$(dkms status 2>/dev/null)"; then
    if sudo -n true 2>/dev/null; then
        log "removendo o patch DKMS do uhid (hefesto-uhid)"
        sudo dkms remove hefesto-uhid/1.0.0 --all >/dev/null 2>&1 || true
    else
        log "sudo indisponível — patch DKMS do uhid NÃO removido"
        log "  sudo dkms remove hefesto-uhid/1.0.0 --all"
    fi
fi
if [[ -e /etc/modprobe.d/hefesto-uhid.conf ]]; then
    if sudo -n true 2>/dev/null; then
        log "removendo a contrapressão do uhid (/etc/modprobe.d/hefesto-uhid.conf)"
        sudo rm -f /etc/modprobe.d/hefesto-uhid.conf
        if [[ -e /sys/module/uhid/parameters/backpressure ]]; then
            printf '0' | sudo tee /sys/module/uhid/parameters/backpressure >/dev/null 2>&1 || true
            log "backpressure do uhid devolvido a 0 — comportamento de fábrica JÁ VALE (NUNCA recarregamos o uhid)"
        fi
    else
        log "sudo indisponível — /etc/modprobe.d/hefesto-uhid.conf NÃO removido"
        log "  sudo rm -f /etc/modprobe.d/hefesto-uhid.conf"
    fi
fi

if command -v dkms >/dev/null 2>&1 && sudo -n true 2>/dev/null; then
    # shellcheck source=scripts/dkms_lib.sh
    source "${ROOT_DIR}/scripts/dkms_lib.sh"
    dkms_flush_initramfs
fi
if [[ -e /etc/NetworkManager/conf.d/hefesto-wifi-powersave.conf ]]; then
    if sudo -n true 2>/dev/null; then
        log "removendo conf de powersave do WiFi (/etc/NetworkManager/conf.d/hefesto-wifi-powersave.conf)"
        sudo rm -f /etc/NetworkManager/conf.d/hefesto-wifi-powersave.conf
    else
        log "sudo indisponível — /etc/NetworkManager/conf.d/hefesto-wifi-powersave.conf NÃO removido"
        log "  sudo rm -f /etc/NetworkManager/conf.d/hefesto-wifi-powersave.conf"
    fi
fi

BLUEZ_BACKPORT_CACHE="${HOME}/.cache/hefesto-dualsense4unix/bluez-backport"
BLUEZ_VERSOES_FILE="${BLUEZ_BACKPORT_CACHE}/VERSOES-ANTERIORES.txt"
if [[ "${KEEP_BLUEZ}" -eq 1 ]]; then
    log "bluez backport preservado (o padrão; --restore-bluez devolve o da distribuição) — a versão atual continua ativa"
elif [[ ! -f "${BLUEZ_VERSOES_FILE}" ]]; then
    log "sem registro de backport do bluez (${BLUEZ_VERSOES_FILE} ausente) — nada a restaurar"
elif ! sudo -n true 2>/dev/null; then
    log "sudo indisponível — bluez backport NÃO restaurado"
    log "  reverta manualmente com as versões de ${BLUEZ_VERSOES_FILE}"
else
    _bluez_pkgs=()
    while IFS=$'\t' read -r _pkg _ver; do
        [[ -n "${_pkg}" && -n "${_ver}" ]] || continue
        dpkg -l "${_pkg%%:*}" >/dev/null 2>&1 && _bluez_pkgs+=("${_pkg}=${_ver}")
    done < "${BLUEZ_VERSOES_FILE}"
    if [[ "${#_bluez_pkgs[@]}" -eq 0 ]]; then
        log "VERSOES-ANTERIORES.txt presente mas nenhum pacote listado está instalado — nada a fazer"
    else
        printf '[uninstall] AVISO ALTO: restaurar o bluez para a versão do noble (%s)\n' "${_bluez_pkgs[*]}"
        printf '[uninstall]   REINICIA o bluetoothd (única exceção à regra de nunca reiniciar) e\n'
        printf '[uninstall]   DESCARTA os bonds Bluetooth pareados — re-pareie os controles depois.\n'
        _bluez_confirm=1
        if [[ "${AUTO_YES}" -ne 1 ]]; then
            printf '[uninstall] Continuar? [s/N] '
            read -r _resp || _resp=""
            case "${_resp}" in
                [sS]*) _bluez_confirm=1 ;;
                *)     _bluez_confirm=0 ;;
            esac
        fi
        if [[ "${_bluez_confirm}" -eq 1 ]]; then
            log "restaurando bluez: ${_bluez_pkgs[*]}"
            if sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y --allow-downgrades \
                    -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold" \
                    "${_bluez_pkgs[@]}"; then
                log "  bluez restaurado — re-pareie os controles Bluetooth"
            else
                log "  ERRO: apt-get install --allow-downgrades falhou — restaure manualmente:"
                log "        sudo apt-get install --allow-downgrades ${_bluez_pkgs[*]}"
            fi
        else
            log "restauração do bluez CANCELADA pelo usuário — backport permanece ativo"
            log "  (rode depois: sudo apt-get install --allow-downgrades ${_bluez_pkgs[*]})"
        fi
    fi
fi

PIPEWIRE_PREF=/etc/apt/preferences.d/hefesto-pipewire
devolver_o_pipewire() {
    local registro="${HOME}/.cache/hefesto-dualsense4unix/pipewire-backport/VERSOES-ANTERIORES.txt"
    local devolver=0 steam=0 pacote ver atual resp sairia
    local pkgs=()
    if [[ ! -f "${registro}" && ! -e "${PIPEWIRE_PREF}" ]]; then
        log "sem registro do PipeWire de antes (${registro} ausente) — nada a devolver"
        return 0
    fi
    if pgrep -u "$(id -u)" -x steam >/dev/null 2>&1 \
        || pgrep -u "$(id -u)" -x steamwebhelper >/dev/null 2>&1; then
        steam=1
    fi
    if [[ ! -f "${registro}" ]]; then
        log "sem registro do PipeWire de antes (${registro} ausente) — só a trava do apt sai"
    else
        while IFS='=' read -r pacote ver; do
            [[ -n "${pacote}" && -n "${ver}" ]] || continue
            atual="$(dpkg-query -W -f='${db:Status-Abbrev}|${Version}\n' "${pacote}" 2>/dev/null \
                | awk -F'|' '$1 ~ /^ii/ { print $2; exit }' || true)"
            [[ -n "${atual}" && "${atual}" != "${ver}" ]] || continue
            pkgs+=("${pacote}=${ver}")
        done < "${registro}"
        if [[ "${#pkgs[@]}" -eq 0 ]]; then
            log "o PipeWire desta máquina já está nas versões do registro — nada a devolver"
        elif [[ "${RESTORE_PIPEWIRE}" -eq 1 ]]; then
            devolver=1
        elif [[ "${AUTO_YES}" -eq 1 || ! -t 0 ]]; then
            log "PipeWire da casa preservado (o padrão sem pergunta; --restore-pipewire devolve o de antes: ${pkgs[*]})"
        elif [[ "${steam}" -eq 1 ]]; then
            log "a Steam está aberta — o PipeWire de antes não pode voltar agora (feche a Steam e rode ./uninstall.sh --restore-pipewire)"
        else
            printf '[uninstall] AVISO: devolver o PipeWire de antes (%s)\n' "${pkgs[*]}"
            printf '[uninstall]   REINICIA o som da sessão: os controles perdem o som e o microfone por\n'
            printf '[uninstall]   alguns segundos, e um jogo aberto pode perder a saída até ser reaberto.\n'
            printf '[uninstall] Devolver o PipeWire de antes? [s/N] '
            read -r resp || resp=""
            case "${resp}" in
                [sS]*) devolver=1 ;;
                *)     log "PipeWire da casa preservado a pedido (rode depois: ./uninstall.sh --restore-pipewire)" ;;
            esac
        fi
        if [[ "${devolver}" -eq 1 && "${steam}" -eq 1 ]]; then
            log "a Steam está aberta — o PipeWire de antes NÃO foi devolvido: trocar o PipeWire reinicia o som, e o reinício do WirePlumber com a Steam aberta é o que a deixa sem fechar"
            log "  feche a Steam pelo menu e rode: ./uninstall.sh --restore-pipewire"
            devolver=0
        fi
        if [[ "${devolver}" -eq 1 ]] && ! sudo -n true 2>/dev/null; then
            log "sudo indisponível — PipeWire NÃO devolvido"
            log "  reverta à mão: sudo apt-get install --allow-downgrades ${pkgs[*]}"
            devolver=0
        fi
        if [[ "${devolver}" -eq 1 && "${DRY_RUN}" -ne 1 ]]; then
            if ! sairia="$(LC_ALL=C apt-get install -s --allow-downgrades "${pkgs[@]}" 2>&1)"; then
                log "o apt não aceita devolver estes pacotes (a versão pode ter saído do archive) — nada foi trocado"
                log "  a simulação é: apt-get install -s --allow-downgrades ${pkgs[*]}"
                devolver=0
            else
                sairia="$(awk '$1 == "Remv" { print $2 }' <<<"${sairia}" | tr '\n' ' ')"
                if [[ -n "${sairia}" ]]; then
                    log "devolver o PipeWire de antes tiraria da máquina: ${sairia}— nada foi trocado"
                    devolver=0
                fi
            fi
        fi
        if [[ "${devolver}" -eq 1 ]]; then
            log "devolvendo o PipeWire de antes: ${pkgs[*]}"
            if sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y --allow-downgrades \
                    -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold" \
                    "${pkgs[@]}"; then
                log "  PipeWire de antes devolvido"
                if reiniciar_o_som_da_sessao; then
                    log "  som reiniciado — confira o som e o microfone de cada controle"
                    case "${SOM_PAINEL_DO_COSMIC}" in
                        voltou) log "  o painel do COSMIC voltou a mostrar o som (cosmic-settings-daemon religado)" ;;
                        nao-voltou) log "  o painel do COSMIC ficou sem o som — rode: ${SOM_CURA_DO_PAINEL}" ;;
                    esac
                else
                    log "  não consegui reiniciar o som — rode: systemctl --user restart pipewire pipewire-pulse wireplumber"
                fi
            else
                log "  ERRO: apt-get install --allow-downgrades falhou — devolva à mão:"
                log "        sudo apt-get install --allow-downgrades ${pkgs[*]}"
            fi
        fi
    fi
    if [[ -e "${PIPEWIRE_PREF}" ]]; then
        if sudo -n true 2>/dev/null && sudo rm -f "${PIPEWIRE_PREF}"; then
            log "removida a trava do apt do PipeWire (${PIPEWIRE_PREF})"
            if [[ "${#pkgs[@]}" -gt 0 && "${devolver}" -eq 0 ]]; then
                log "  sem ela, no Pop!_OS o próximo apt upgrade volta o PipeWire para o da distro"
            fi
        else
            log "sudo indisponível — a trava do apt NÃO foi removida"
            log "  sudo rm -f ${PIPEWIRE_PREF}"
        fi
    fi
}
devolver_o_pipewire

for _bz_sobra in "${HOME}/.cache/hefesto-dualsense4unix/bluez-obra" \
                 "${HOME}/.cache/hefesto-dualsense4unix/bluez-fontes"; do
    if [[ -d "${_bz_sobra}" ]]; then
        log "removendo a obra do backport do BlueZ (${_bz_sobra}) — regenerável pelo scripts/construir_bluez_backport.sh"
        rm -rf "${_bz_sobra}" 2>/dev/null \
            || log "  não consegui apagar ${_bz_sobra} inteira — confira os donos dos arquivos"
    fi
done

if [[ "${REMOVE_USB_QUIRK}" -eq 1 ]]; then
    if [[ -x "${ROOT_DIR}/scripts/install_usb_quirk.sh" ]]; then
        log "removendo quirk de boot usbcore.quirks (--remove-usb-quirk)"
        bash "${ROOT_DIR}/scripts/install_usb_quirk.sh" --remove \
            || log "  ERRO: install_usb_quirk.sh --remove falhou — rode manualmente"
    else
        log "scripts/install_usb_quirk.sh ausente — pulei a remoção do quirk de boot"
    fi
else
    log "quirk de boot usbcore.quirks preservado (cmdline é sensível). Para remover:"
    log "  bash scripts/install_usb_quirk.sh --remove   (ou ./uninstall.sh --remove-usb-quirk)"
fi

CMDLINE_OWNERS_FILE="${HOME}/.local/state/hefesto-dualsense4unix/cmdline-owners.conf"
if [[ -f "${CMDLINE_OWNERS_FILE}" ]]; then
    _cmdline_reverted=0
    _cmdline_backend="$(sed -n 's/^cmdline\.backend=//p' "${CMDLINE_OWNERS_FILE}" | head -1)"
    _cmdline_backend="${_cmdline_backend:-kernelstub}"
    _cmdline_dono="${ROOT_DIR}/src/hefesto_dualsense4unix/integrations/kernel_cmdline.py"
    _own_autosusp="$(sed -n 's/^cmdline\.usbcore\.autosuspend=//p' "${CMDLINE_OWNERS_FILE}" | head -1)"
    _own_quirks="$(sed -n 's/^cmdline\.usbcore\.quirks=//p' "${CMDLINE_OWNERS_FILE}" | head -1)"
    if ! command -v python3 >/dev/null 2>&1 || [[ ! -f "${_cmdline_dono}" ]]; then
        log "cmdline: sem python3 ou sem ${_cmdline_dono} — reverta manualmente os params"
        log "  marcados 'hefesto' em ${CMDLINE_OWNERS_FILE} (${_cmdline_backend}; registro preservado)"
    elif ! sudo -n true 2>/dev/null; then
        log "cmdline: sudo indisponível — params NÃO revertidos (registro preservado;"
        log "  re-execute o uninstall com sudo para reverter)"
    else
        _cmdline_plan="$(python3 - "${ROOT_DIR}" "${_cmdline_backend}" "${_own_autosusp}" "${_own_quirks}" <<'PYEOF'
import os
import sys

root, backend, own_autosusp, own_quirks = sys.argv[1:5]
sys.path.insert(0, os.path.join(root, "src"))
from hefesto_dualsense4unix.integrations import kernel_cmdline as kc

presentes = {c.backend: c for c in kc.carregadores_presentes()}
if backend not in presentes:
    print("sem\t" + backend)
    raise SystemExit(0)
tokens = list(presentes[backend].tokens)
if own_autosusp == "hefesto" and kc.AUTOSUSPEND_TOKEN in tokens:
    print("del\t" + kc.AUTOSUSPEND_TOKEN)
if own_quirks in ("hefesto", "compartilhado"):
    for tok in kc.tokens_for_param(tokens, kc.QUIRKS_PARAM):
        rest, changed = kc.strip_quirks_token(tok)
        if not changed:
            continue
        print("del\t" + tok)
        if rest is not None:
            print("add\t" + rest)
PYEOF
)" || _cmdline_plan=$'sem\t'"${_cmdline_backend}"
        _cmdline_args=()
        _cmdline_sem=""
        while IFS=$'\t' read -r _qop _qtok; do
            case "${_qop}" in
                del) _cmdline_args+=(--tira "${_qtok}") ;;
                add) _cmdline_args+=(--poe "${_qtok}") ;;
                sem) _cmdline_sem="${_qtok}" ;;
            esac
        done <<<"${_cmdline_plan}"
        for _dono in "autosuspend:${_own_autosusp}" "quirks:${_own_quirks}"; do
            if [[ -n "${_dono#*:}" && "${_dono#*:}" != "hefesto" && "${_dono#*:}" != "compartilhado" ]]; then
                log "cmdline: usbcore.${_dono%%:*} é de ${_dono#*:} — preservado"
            fi
        done
        if [[ -n "${_cmdline_sem}" ]]; then
            log "cmdline: o install escreveu em ${_cmdline_sem}, e ele não está legível agora — reverta"
            log "  manualmente os params marcados em ${CMDLINE_OWNERS_FILE} (registro preservado)"
        elif [[ "${#_cmdline_args[@]}" -eq 0 ]]; then
            log "cmdline: nada nosso em ${_cmdline_backend} — nada a reverter"
            _cmdline_reverted=1
        elif sudo python3 -I "${_cmdline_dono}" escrever --backend "${_cmdline_backend}" \
                "${_cmdline_args[@]}" >/dev/null 2>&1; then
            log "cmdline: tirei de ${_cmdline_backend} o que era nosso: ${_cmdline_args[*]} (vale no próximo boot)"
            _cmdline_reverted=1
        else
            log "  ERRO: a escrita em ${_cmdline_backend} falhou — rode: sudo python3 -I ${_cmdline_dono} escrever --backend ${_cmdline_backend} ${_cmdline_args[*]}"
        fi
    fi
    if [[ "${_cmdline_reverted}" -eq 1 ]]; then
        log "removendo registro de dono ${CMDLINE_OWNERS_FILE}"
        rm -f "${CMDLINE_OWNERS_FILE}"
    fi
fi

if [[ -d "${ROOT_DIR}/.venv" ]]; then
    log "removendo .venv"
    rm -rf "${ROOT_DIR}/.venv"
fi

for cache in .pytest_cache .ruff_cache .mypy_cache flatpak-build-dir .flatpak-builder dist build; do
    if [[ -d "${ROOT_DIR}/${cache}" ]]; then
        log "removendo ${cache}"
        rm -rf "${ROOT_DIR}/${cache}"
    fi
done

find "${ROOT_DIR}" -type d -name "__pycache__" \
    -not -path "*/\.git/*" \
    -exec rm -rf {} + 2>/dev/null || true
find "${ROOT_DIR}" -type f -name "*.pyc" \
    -not -path "*/\.git/*" \
    -delete 2>/dev/null || true

if [[ -d "${HOME}/.local/share/hefesto-dualsense4unix/glyphs" ]]; then
    log "removendo glyphs do user"
    rm -rf "${HOME}/.local/share/hefesto-dualsense4unix/glyphs"
fi

if [[ -d "${HOME}/.local/share/hefesto-dualsense4unix" ]] \
   && [[ -z "$(ls -A "${HOME}/.local/share/hefesto-dualsense4unix" 2>/dev/null)" ]]; then
    log "removendo diretório-pai vazio ~/.local/share/hefesto-dualsense4unix"
    rmdir "${HOME}/.local/share/hefesto-dualsense4unix" 2>/dev/null || true
fi

if dpkg -l hefesto-dualsense4unix >/dev/null 2>&1; then
    log "removendo pacote .deb hefesto-dualsense4unix (sudo)"
    sudo apt-get remove -y hefesto-dualsense4unix >/dev/null 2>&1 || true
fi

HEFESTO_FLATPAK_APP_IDS=(
    "io.github.hefesto_team.hefesto_dualsense4unix"
    "br.andrefarias.Hefesto"
)
for _fp_id in "${HEFESTO_FLATPAK_APP_IDS[@]}"; do
    if grep -q "${_fp_id}" <<<"$(flatpak list --user --app 2>/dev/null)"; then
        log "desinstalando Flatpak ${_fp_id}"
        flatpak uninstall --user -y "${_fp_id}" >/dev/null 2>&1 || true
    fi
done

for _fp_id in "${HEFESTO_FLATPAK_APP_IDS[@]}"; do
    _fp_home="${HOME}/.var/app/${_fp_id}"
    [[ -d "${_fp_home}" ]] || continue
    rm -rf "${_fp_home}/cache" 2>/dev/null || true
    if [[ "${KEEP_CONFIG}" -eq 0 ]]; then
        _fp_backup="${XDG_CONFIG_HOME:-${HOME}/.config}/hefesto-dualsense4unix.backup-$(date +%s)-flatpak-${_fp_id}"
        mkdir -p "${_fp_backup}"
        cp -a "${_fp_home}/." "${_fp_backup}/" 2>/dev/null || true
        log "backup do sandbox ${_fp_id} em ${_fp_backup}"
        log "removendo ${_fp_home}"
        rm -rf "${_fp_home}" 2>/dev/null || true
    else
        log "config do sandbox ${_fp_id} preservada (use --purge-config para apagar)"
    fi
done

for appimg_dir in "${HOME}/Aplicativos" "${HOME}/Applications" "${HOME}/Downloads" "${HOME}/.local/bin"; do
    [[ -d "$appimg_dir" ]] || continue
    for f in "$appimg_dir"/Hefesto-Dualsense4Unix*.AppImage "$appimg_dir"/hefesto-dualsense4unix*.AppImage; do
        if [[ -f "$f" ]]; then
            log "removendo AppImage ${f}"
            rm -f "$f"
        fi
    done
done

log "removendo catalogos i18n .mo do user"
for lang_dir in "${HOME}/.local/share/locale"/*/; do
    [[ -d "$lang_dir" ]] || continue
    mo="${lang_dir}LC_MESSAGES/${APP_ID}.mo"
    if [[ -f "$mo" ]]; then
        log "  ${mo}"
        rm -f "$mo"
    fi
done

runtime_dir="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/hefesto-dualsense4unix"
if [[ -d "$runtime_dir" ]]; then
    log "removendo ${runtime_dir}"
    rm -rf "$runtime_dir"
fi

log "(nota) deps Python via pip --user em ~/.local/lib/python*/site-packages preservadas"
log "       — remova manualmente se quiser wipe absoluto do user-site"

log ""
log "fora do escopo (não removido — não é do hefesto):"
log "  /etc/udev/rules.d/99-usb-*.rules         — de outra ferramenta de energia do usuário"
log "  /etc/udev/rules.d/99-storage-no-link-pm.rules — idem (storage PM)"
log "  /etc/udev/rules.d/50-system76-power.rules    — polkit pra system76-power (Pop_OS)"
log "  kernel cmdline de TERCEIRO (pcie_aspm, mitigations, etc.) — só os params"
log "    REGISTRADOS como do hefesto (cmdline-owners.conf) são revertidos acima"
log "  ~/.config/wireplumber/wireplumber.conf.d/   — dir compartilhado, só nosso .conf é removido"
log "  ~/.local/lib/python*/site-packages/         — pip --user pode ser compartilhado"
log "  wvkbd / onboard (teclado na tela do L3)      — pacote do sistema, pode servir a outra coisa"
log "    (mesma decisão do libopus0 da ponte de mic: o install instala, o uninstall não desinstala)"

DISABLE_STEAM_INPUT_SCRIPT="${ROOT_DIR}/scripts/disable_steam_input.sh"
if [[ "${KEEP_STEAM_INPUT}" -eq 1 ]]; then
    log "Steam Input PSSupport preservado (--keep-steam-input)"
elif [[ ! -x "${DISABLE_STEAM_INPUT_SCRIPT}" ]]; then
    log "scripts/disable_steam_input.sh ausente — pulei o desligar do Steam Input"
    log "  (rode depois: bash scripts/disable_steam_input.sh --apply)"
else
    log "desligando Steam Input PSSupport em todos os localconfig.vdf"
    if bash "${DISABLE_STEAM_INPUT_SCRIPT}" --apply; then
        log "  reverter: bash scripts/disable_steam_input.sh --restore"
    else
        log "  ERRO: disable_steam_input.sh falhou — rode manualmente"
    fi
fi

LISTAS_DE_EXCLUSAO=()
LISTAS_GUARDADAS_DE=()
LISTAS_GUARDADAS_PARA=()

CURA_POR_ESTRADA_PY="${ROOT_DIR}/src/hefesto_dualsense4unix/integrations/cura_por_estrada.py"
_estradas_desfeitas=0
for _cfg in "${XDG_CONFIG_HOME:-${HOME}/.config}" "${HOME}/.config"; do
    _lista="${_cfg}/hefesto-dualsense4unix/lista_de_exclusao.json"
    [[ -f "${_lista}" ]] || continue
    [[ " ${LISTAS_DE_EXCLUSAO[*]} " == *" ${_lista} "* ]] && continue
    LISTAS_DE_EXCLUSAO+=("${_lista}")
done
_guardar_as_listas_para_depois() {
    local _i=0 _l
    for _l in "${LISTAS_DE_EXCLUSAO[@]}"; do
        _i=$((_i + 1))
        LISTAS_GUARDADAS_DE+=("${_l}")
        if [[ "${KEEP_CONFIG}" -eq 0 ]]; then
            LISTAS_GUARDADAS_PARA+=("${ESTADOS_DO_HEFESTO[0]}/launch_env/lista_de_exclusao-${_i}.json")
        else
            LISTAS_GUARDADAS_PARA+=("${_l}")
        fi
    done
}
_args_das_listas_de_depois() {
    local _l
    for _l in "${LISTAS_GUARDADAS_PARA[@]}"; do
        printf ' --lista-de-exclusao %q' "${_l}"
    done
}
if [[ -f "${CURA_POR_ESTRADA_PY}" ]] && command -v python3 >/dev/null 2>&1; then
    log "tirando dos lançadores (Heroic e as cópias por jogo dele, overrides do Flatpak) só o ambiente que o Hefesto escreveu"
    _args_das_estradas=(--desfazer --lar "${HOME}")
    for _estado in "${ESTADOS_DO_HEFESTO[@]}"; do
        _args_das_estradas+=(--pasta-do-ambiente "${_estado}/launch_env")
    done
    for _lista in "${LISTAS_DE_EXCLUSAO[@]}"; do
        _args_das_estradas+=(--lista-de-exclusao "${_lista}")
    done
    _rc_das_estradas=0
    _saida_das_estradas="$(python3 "${CURA_POR_ESTRADA_PY}" "${_args_das_estradas[@]}" 2>&1)" \
        || _rc_das_estradas=$?
    while IFS= read -r _linha; do
        if [[ -n "${_linha}" ]]; then log "  ${_linha}"; fi
    done <<<"${_saida_das_estradas}"
    if [[ "${_rc_das_estradas}" -eq 0 ]]; then
        _estradas_desfeitas=1
    else
        _guardar_as_listas_para_depois
        log "  ADIADO: feche o lançador e rode: python3 ${CURA_POR_ESTRADA_PY} --desfazer$(_args_das_listas_de_depois)"
        log "  (o registro do que é do Hefesto fica em launch_env/estradas.json, e a lista de exclusão com ele, até lá)"
    fi
else
    _guardar_as_listas_para_depois
    log "cura_por_estrada.py ausente ou sem python3 — o ambiente do Hefesto pode ter ficado no Heroic e nos overrides do Flatpak"
    log "  (o registro fica em launch_env/estradas.json, e a lista de exclusão com ele; rode depois: python3 <repositório>/src/hefesto_dualsense4unix/integrations/cura_por_estrada.py --desfazer$(_args_das_listas_de_depois))"
fi

PROTON_PIN_PY="${ROOT_DIR}/src/hefesto_dualsense4unix/integrations/proton_pin.py"
if [[ -f "${PROTON_PIN_PY}" ]] && command -v python3 >/dev/null 2>&1; then
    log "destravando o Proton pinado (só o mapping que o hefesto escreveu)"
    _pp_rc=0
    python3 "${PROTON_PIN_PY}" --unlock || _pp_rc=$?
    if [[ "${_pp_rc}" -eq 3 ]]; then
        log "  ADIADO: feche a Steam (e o jogo) e rode: python3 ${PROTON_PIN_PY} --unlock"
    elif [[ "${_pp_rc}" -ne 0 ]]; then
        log "  ERRO: unlock falhou (rc=${_pp_rc}) — rode: python3 ${PROTON_PIN_PY} --unlock"
    fi
    log "  o Proton extraído (compatibilitytools.d) FICA — é dado do usuário"
else
    log "proton_pin.py ausente ou sem python3 — pulei o destravamento do Proton pinado"
fi

_cfg_do_xdg="${XDG_CONFIG_HOME:-${HOME}/.config}"
_dados_do_xdg="${XDG_DATA_HOME:-${HOME}/.local/share}"
_cache_do_xdg="${XDG_CACHE_HOME:-${HOME}/.cache}"
_mods_codigo="${_dados_do_xdg}/hefesto-dualsense4unix/mods"
_mods_dados="${XDG_STATE_HOME:-${HOME}/.local/state}/hefesto-dualsense4unix/mods"
_mods_registro="${_cfg_do_xdg}/hefesto-dualsense4unix/mods.json"
for _mod_lugar in "${_mods_codigo}" "${_mods_dados}" "${_mods_registro}"; do
    [[ -e "${_mod_lugar}" ]] || continue
    if [[ "${KEEP_CONFIG}" -eq 0 ]]; then
        log "as extensões saem junto, com o backup: ${_mod_lugar} (--purge-config)"
    else
        log "as extensões instaladas ficam: ${_mod_lugar} (apagar de vez: --purge-config)"
    fi
done
unset _mod_lugar
if [[ "${KEEP_CONFIG}" -eq 0 ]]; then
    backup_dir="${_cfg_do_xdg}/hefesto-dualsense4unix.backup-$(date +%s)"
    backed_up=0
    for _i in "${!LISTAS_GUARDADAS_DE[@]}"; do
        _de="${LISTAS_GUARDADAS_DE[${_i}]}"
        _para="${LISTAS_GUARDADAS_PARA[${_i}]}"
        [[ "${_de}" == "${_para}" || ! -f "${_de}" ]] && continue
        mkdir -p "$(dirname "${_para}")"
        if cp -a "${_de}" "${_para}"; then
            log "a lista de exclusão fica em ${_para} até o desfazer dos lançadores"
        else
            log "não consegui guardar a lista de exclusão em ${_para} — ela está no backup da config"
        fi
    done
    for path in \
        "${_cfg_do_xdg}/hefesto-dualsense4unix" \
        "${HOME}/.config/hefesto-dualsense4unix" \
        "${_dados_do_xdg}/hefesto-dualsense4unix" \
        "${HOME}/.local/share/hefesto-dualsense4unix" \
        "${_cache_do_xdg}/hefesto-dualsense4unix" \
        "${HOME}/.cache/hefesto-dualsense4unix" \
        "${_cfg_do_xdg}/hefesto" \
        "${HOME}/.config/hefesto" \
        "${_dados_do_xdg}/hefesto" \
        "${HOME}/.local/share/hefesto" \
        "${_cache_do_xdg}/hefesto" \
        "${HOME}/.cache/hefesto"; do
        if [[ -d "$path" ]]; then
            mkdir -p "${backup_dir}"
            rel="${path#"${HOME}"/}"
            cp -a "$path" "${backup_dir}/${rel//\//_}" 2>/dev/null || true
            backed_up=1
            log "removendo ${path}"
            rm -rf "$path"
        fi
    done
    [[ "${backed_up}" -eq 1 ]] && log "backup da config em ${backup_dir}"
else
    log "configs preservadas (default): ~/.config/hefesto + ~/.config/hefesto-dualsense4unix"
    log "  (use --purge-config para apagar, com backup automático)"
fi

LAUNCH_STRIP_PY="${ROOT_DIR}/src/hefesto_dualsense4unix/integrations/steam_launch_options.py"
if [[ -f "${LAUNCH_STRIP_PY}" ]] && command -v python3 >/dev/null 2>&1; then
    log "removendo Launch Options do Hefesto (wrapper + veneno legado) dos localconfig.vdf"
    if python3 "${LAUNCH_STRIP_PY}" --strip --stop-steam; then
        log "  backups .bak.hefesto-launch-<ts> ao lado de cada vdf"
    else
        log "  ERRO: strip adiado (Steam não fechou?) — rode com a Steam fechada:"
        log "        python3 ${LAUNCH_STRIP_PY} --strip"
    fi
else
    log "steam_launch_options.py ausente ou sem python3 — pulei o strip das Launch Options"
    log "  (a string do wrapper degrada sozinha: o jogo continua abrindo sem ele)"
fi

CAMADAS_PY="${ROOT_DIR}/src/hefesto_dualsense4unix/integrations/camadas_vulkan.py"
if [[ -f "${CAMADAS_PY}" ]] && command -v python3 >/dev/null 2>&1; then
    log "devolvendo as sobreposições que o Hefesto tinha desligado nos jogos"
    python3 "${CAMADAS_PY}" --devolver || \
        log "  ERRO: devolução adiada — rode: python3 ${CAMADAS_PY} --devolver"
else
    log "camadas_vulkan.py ausente ou sem python3 — pulei a devolução das sobreposições"
fi
readonly CAMADAS_TARGET="${HOME}/.local/share/hefesto-dualsense4unix/bin/hefesto-camadas"
if [[ -e "${CAMADAS_TARGET}" ]]; then
    log "removendo curador de camadas ${CAMADAS_TARGET}"
    rm -f "${CAMADAS_TARGET}"
fi
for _estado in "${ESTADOS_DO_HEFESTO[@]}"; do
    if [[ -f "${_estado}/camadas-vulkan.json" ]]; then
        log "removendo o registro das sobreposições (${_estado}/camadas-vulkan.json)"
        rm -f "${_estado}/camadas-vulkan.json"
    fi
done

AUDIO_KS_PY="${ROOT_DIR}/src/hefesto_dualsense4unix/integrations/audio_ks_dualsense.py"
if [[ -f "${AUDIO_KS_PY}" ]] && command -v python3 >/dev/null 2>&1; then
    log "tirando o device de áudio KS do DualSense dos prefixos dos jogos"
    python3 "${AUDIO_KS_PY}" --remover-de-todos || \
        log "  ERRO: remoção adiada — rode: python3 ${AUDIO_KS_PY} --remover-de-todos"
else
    log "audio_ks_dualsense.py ausente ou sem python3 — pulei a remoção do device KS"
fi
readonly AUDIO_KS_TARGET="${HOME}/.local/share/hefesto-dualsense4unix/bin/hefesto-audio-ks"
if [[ -e "${AUDIO_KS_TARGET}" ]]; then
    log "removendo o curador do device KS ${AUDIO_KS_TARGET}"
    rm -f "${AUDIO_KS_TARGET}"
fi

readonly LAUNCH_WRAPPER="${HOME}/.local/share/hefesto-dualsense4unix/bin/hefesto-launch"
if [[ -e "${LAUNCH_WRAPPER}" ]]; then
    log "removendo wrapper de launch ${LAUNCH_WRAPPER}"
    rm -f "${LAUNCH_WRAPPER}"
fi
if [[ -L "${HOME}/.local/bin/hefesto-launch" || -e "${HOME}/.local/bin/hefesto-launch" ]]; then
    log "removendo symlink ${HOME}/.local/bin/hefesto-launch"
    rm -f "${HOME}/.local/bin/hefesto-launch"
fi
rmdir "${HOME}/.local/share/hefesto-dualsense4unix/bin" 2>/dev/null || true
readonly PECA_GDK_PASTA="${HOME}/.local/share/hefesto-dualsense4unix/wine"
if [[ -d "${PECA_GDK_PASTA}" ]]; then
    log "removendo a peça GDK ${PECA_GDK_PASTA}"
    rm -rf "${PECA_GDK_PASTA}"
fi
for _estado in "${ESTADOS_DO_HEFESTO[@]}"; do
    [[ -d "${_estado}/launch_env" ]] || continue
    _fica_para_depois=0
    if [[ "${_estradas_desfeitas}" -eq 0 ]]; then
        for _le in "${_estado}/launch_env"/estradas.json "${_estado}/launch_env"/lista_de_exclusao-*.json; do
            [[ -e "${_le}" ]] && _fica_para_depois=1
        done
    fi
    if [[ "${_fica_para_depois}" -eq 0 ]]; then
        log "removendo materialização de launch (${_estado}/launch_env)"
        rm -rf "${_estado}/launch_env"
    else
        log "removendo materialização de launch (${_estado}/launch_env) — menos o registro das estradas e a lista de exclusão, que ficam até o desfazer"
        for _le in "${_estado}/launch_env"/* "${_estado}/launch_env"/.[!.]*; do
            [[ -e "${_le}" || -L "${_le}" ]] || continue
            case "${_le##*/}" in estradas.json|lista_de_exclusao-*.json) continue ;; esac
            rm -rf "${_le}"
        done
    fi
done
for _estado in "${ESTADOS_DO_HEFESTO[@]}"; do
    if [[ -f "${_estado}/wrapper-visto.json" ]]; then
        log "removendo o registro do wrapper (${_estado}/wrapper-visto.json)"
        rm -f "${_estado}/wrapper-visto.json"
    fi
done
for _estado in "${ESTADOS_DO_HEFESTO[@]}"; do
    if [[ -f "${_estado}/opcoes-escritas.json" ]]; then
        log "removendo o registro das opções por jogo (${_estado}/opcoes-escritas.json)"
        rm -f "${_estado}/opcoes-escritas.json"
    fi
done
for _estado in "${ESTADOS_DO_HEFESTO[@]}"; do
    if [[ -f "${_estado}/teclado-na-tela.conf" ]]; then
        log "removendo a sentinela do teclado na tela (o PACOTE wvkbd/onboard fica — é do sistema)"
        rm -f "${_estado}/teclado-na-tela.conf"
    fi
done
for _estado in "${ESTADOS_DO_HEFESTO[@]}"; do
    if [[ -f "${_estado}/gabinete.json" ]]; then
        log "removendo o censo do gabinete (${_estado}/gabinete.json)"
        rm -f "${_estado}/gabinete.json"
    fi
done
ESTADO_DO_RADIO="${XDG_STATE_HOME:-${HOME}/.local/state}/hefesto-dualsense4unix"
if [[ -f "${ESTADO_DO_RADIO}/lugares-dos-adaptadores.json" ]]; then
    log "removendo o registro dos lugares dos adaptadores (${ESTADO_DO_RADIO}/lugares-dos-adaptadores.json)"
    rm -f "${ESTADO_DO_RADIO}/lugares-dos-adaptadores.json"
fi
for _estado in "${ESTADOS_DO_HEFESTO[@]}"; do
    if [[ -f "${_estado}/conexao-zumbi.json" ]]; then
        log "removendo a última volta da vigia de conexões (${_estado}/conexao-zumbi.json)"
        rm -f "${_estado}/conexao-zumbi.json"
    fi
done
_carimbo_do_diario="$(date +%Y%m%d-%H%M%S)"
_diarios_da_sessao=("${ESTADO_DO_RADIO}/radio-diario.jsonl" "${ESTADO_DO_RADIO}/radio-diario.jsonl.1")
if [[ "${KEEP_CONFIG}" -eq 0 ]]; then
    for _diario_sessao in "${ESTADO_DO_RADIO}"/radio-diario.pre-uninstall-*.jsonl*; do
        [[ -f "${_diario_sessao}" ]] && _diarios_da_sessao+=("${_diario_sessao}")
    done
fi
for _diario_sessao in "${_diarios_da_sessao[@]}"; do
    [[ -f "${_diario_sessao}" ]] || continue
    if [[ "${KEEP_CONFIG}" -eq 1 ]]; then
        _diario_guardado="${_diario_sessao%%.jsonl*}.pre-uninstall-${_carimbo_do_diario}.jsonl${_diario_sessao##*.jsonl}"
        log "preservando o diário do rádio em ${_diario_guardado} (apagar de vez: --purge-config)"
        mv -f "${_diario_sessao}" "${_diario_guardado}" 2>/dev/null || true
    else
        log "removendo o diário do rádio ${_diario_sessao} (--purge-config)"
        rm -f "${_diario_sessao}"
    fi
done
if [[ "${KEEP_CONFIG}" -eq 0 ]]; then
    for _kw in "${ESTADO_DO_RADIO}/kernel.log" "${ESTADO_DO_RADIO}/kernel-watch.boot"; do
        if [[ -f "${_kw}" ]]; then
            log "removendo ${_kw} (--purge-config)"
            rm -f "${_kw}"
        fi
    done
fi
rmdir "${HOME}/.local/state/hefesto-dualsense4unix" 2>/dev/null || true
rmdir "${ESTADO_DO_RADIO}" 2>/dev/null || true
for _estado in "${ESTADOS_DO_HEFESTO[@]}"; do
    [[ -d "${_estado}" ]] || continue
    if [[ "${KEEP_CONFIG}" -eq 0 ]]; then
        for _sobra in "${_estado}"/* "${_estado}"/.[!.]*; do
            [[ -e "${_sobra}" || -L "${_sobra}" ]] || continue
            case "${_sobra##*/}" in
                proton-pin-lock.json|cmdline-owners.conf|broker-owner.conf|launch_env)
                    log "fica ${_sobra}: o desfazer dele foi adiado (a linha dele, acima, diz como terminar)"
                    ;;
                mods)
                    _rel_do_estado="${_estado#"${HOME}"/}"
                    _backup_do_estado="${backup_dir:-${XDG_CONFIG_HOME:-${HOME}/.config}/hefesto-dualsense4unix.backup-$(date +%s)}/${_rel_do_estado//\//_}"
                    mkdir -p "${_backup_do_estado}"
                    if mv -f "${_sobra}" "${_backup_do_estado}/" 2>/dev/null; then
                        log "guardando os dados das extensões ${_sobra} no backup (${_backup_do_estado})"
                    else
                        log "não consegui guardar os dados das extensões ${_sobra} no backup — ficaram"
                    fi
                    ;;
                *)
                    _rel_do_estado="${_estado#"${HOME}"/}"
                    _backup_do_estado="${backup_dir:-${XDG_CONFIG_HOME:-${HOME}/.config}/hefesto-dualsense4unix.backup-$(date +%s)}/${_rel_do_estado//\//_}"
                    mkdir -p "${_backup_do_estado}"
                    if mv -f "${_sobra}" "${_backup_do_estado}/" 2>/dev/null; then
                        log "guardando ${_sobra} no backup (${_backup_do_estado}) — nenhum passo o nomeia"
                    else
                        log "não consegui guardar ${_sobra} no backup — ficou"
                    fi
                    ;;
            esac
        done
    fi
    if ! rmdir "${_estado}" 2>/dev/null && [[ -d "${_estado}" ]]; then
        mapfile -t _ficou < <(ls -A "${_estado}" 2>/dev/null)
        log "a pasta de estado ${_estado} fica, com: ${_ficou[*]}"
        if [[ "${KEEP_CONFIG}" -eq 1 ]]; then
            log "  (o histórico fica de propósito; apagar de vez: --purge-config)"
        fi
    fi
done
if [[ -d "${HOME}/.local/share/hefesto-dualsense4unix" ]] \
   && [[ -z "$(ls -A "${HOME}/.local/share/hefesto-dualsense4unix" 2>/dev/null)" ]]; then
    rmdir "${HOME}/.local/share/hefesto-dualsense4unix" 2>/dev/null || true
fi

printf '\n─────────────────────────────────────────\n'
if [[ "${DRY_RUN}" -eq 1 ]]; then
    printf ' Hefesto - DualSense4Unix: ENSAIO — nada foi removido; as linhas FARIA são o plano\n'
else
    printf ' Hefesto - DualSense4Unix desinstalado (wipe completo)\n'
fi
printf '─────────────────────────────────────────\n\n'
