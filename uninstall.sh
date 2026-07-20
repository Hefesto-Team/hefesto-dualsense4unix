#!/usr/bin/env bash
# uninstall.sh - WIPE do Hefesto - Dualsense4Unix.
# Remove artefatos do install nativo, o applet COSMIC, .deb (apt remove),
# Flatpak, AppImage em ~/Aplicativos, .venv, caches Python, runtime e dados.
#
# Config do usuário (perfis, sessão, preferências) é PRESERVADA por padrão e,
# quando apagada, é antes copiada para um backup. Cobre tanto o caminho atual
# (~/.config/hefesto-dualsense4unix) quanto o legado curto (~/.config/hefesto).
#
# Flags:
#   --keep-udev          PRESERVA udev rules + modules-load (default: remove, sudo).
#   --udev               [DEPRECATED] no-op — remoção é default desde v3.8.3.
#   --remove-usb-quirk   EXPLÍCITO (default NÃO remove): tira o quirk de boot
#                        usbcore.quirks=054c:0ce6:gn,054c:0df2:gn do cmdline
#                        (kernelstub/grub) via scripts/install_usb_quirk.sh --remove.
#                        Por default NÃO remove: cmdline é sensível e pode ser
#                        mantido por toolchain externa do usuário (ex.: Aurora).
#   --purge-config       APAGA a config do usuário (com backup antes). Default: preserva.
#   --keep-config        preserva a config (default; mantido por retrocompatibilidade).
#   --keep-steam-input   PRESERVA Steam Input PSSupport (default: desliga em TODOS os
#                        localconfig.vdf de todos os Steam users em todos os formatos).
#                        Simétrico ao install.sh — se sai sem desligar, o sintoma
#                        "controle vira mouse / botões em background" volta na hora.
#                        Reverter desligamento: scripts/disable_steam_input.sh --restore.
#   --keep-bluez         PRESERVA o backport do bluez (default: RESTAURA as versões
#                        originais do noble via VERSOES-ANTERIORES.txt do cache).
#                        Onda R — remoção BRUTAL de propósito (reinicia o bluetoothd
#                        e descarta os bonds outra vez); pede confirmação interativa
#                        (--yes pula). Detalhe completo mais abaixo ("Onda R").
#   --yes,-y             responde 'sim' para prompts.
#
# Onda PLATAFORMA (2026-07-18) — removidos por DEFAULT, simétricos ao install:
#   - regras udev 81 (USB power devices + hosts) + modprobe.d do btusb — rm +
#     reload; o power/control atual NÃO é revertido a quente (inócuo até reboot).
#   - FastConnectable do BlueZ: drop-in main.conf.d OU bloco marcado do
#     main.conf (entre as sentinelas hefesto), com backup; SEM restart do
#     bluetoothd (vale no próximo boot/restart natural).
#   - Proton pinado: destrava SÓ o CompatToolMapping que NÓS escrevemos
#     (proton_pin.py --unlock); o Proton EXTRAÍDO fica (dado do usuário).
#   - cmdline: reverte SÓ os params registrados como "hefesto" no estado local
#     (cmdline-owners.conf); token usbcore.quirks "compartilhado" perde só os
#     IDs nossos (merge inverso). Params de terceiro (Aurora) NUNCA são tocados.
#
# BUG-UNINSTALL-UDEV-DEFAULT-01 (fix): install.sh aplica as 5 udev rules + modules-
# load por default (--no-udev é o opt-out). Symmetric, o uninstall.sh deve REMOVER
# por default. Versões anteriores exigiam --udev explícito, deixando 6 arquivos no
# /etc/ que continuavam disparando hotplug-units inexistentes ao plugar o controle.
#
# FEAT-DISABLE-STEAM-INPUT-PSSUPPORT-01: install.sh, por default, desliga Steam
# Input PSSupport+UseSteamControllerConfig em todos os localconfig.vdf para evitar
# conflito Steam-vs-daemon. O uninstall, simétrico, repete o desligar — porque sem
# o daemon do Hefesto domesticando o DualSense, Steam Input PSSupport=2 reproduz
# imediatamente os 3 sintomas (touchpad → cursor, mic spam, botões em background)
# que motivam o usuário a desinstalar.
#
# Onda S (2026-07-20, broker root hide-hidraw fd-injection — BROKER-01, ver
# docs/process/estudos/2026-07-20-desenho-onda-s-broker-fd-injection.md):
#   - hefesto-hidraw-broker.{service,socket} (PRIMEIRO serviço de SISTEMA
#     socket-activated do projeto): desabilitado + parado por DEFAULT — o
#     stop dispara ExecStopPost --restore-all-and-exit, então NENHUM hidraw
#     físico fica 0600 órfão. Um belt explícito roda o mesmo restore-all-
#     and-exit ANTES de remover o binário (o binário precisa existir ainda
#     para rodar). Remove só os caminhos que o install.sh REGISTROU em
#     broker-owner.conf e que carregam o header do hefesto — nunca toca
#     unit de terceiros.
#
# Onda R (2026-07-19, bluetoothd 5.72 crasha crônico — ver estudo
# docs/process/estudos/2026-07-19-estudo-bluez-backport-onda-r.md):
#   --keep-bluez         PRESERVA o backport do bluez (default: RESTAURA as versões
#                        originais do noble via VERSOES-ANTERIORES.txt do cache).
#                        Remoção BRUTAL de propósito (reinicia o bluetoothd — a
#                        ÚNICA exceção documentada à regra de nunca reiniciar —
#                        e descarta os bonds outra vez): pede confirmação
#                        interativa (--yes pula) ANTES de aplicar via apt.
#   - bloco JustWorksRepairing do main.conf: removido por default, mesmo
#     mecanismo (sentinelas/drop-in) do FastConnectable — sem restart do bluetoothd.
#   - hefesto-bt-agent.service (agente de pareamento persistente): desabilitado
#     e removido por default; o pacote bluez-tools (dependência) NÃO é removido
#     (pode ser útil ao usuário fora do Hefesto — mesma lógica de preservar deps
#     compartilhadas do sistema).
#
# Onda T (2026-07-20, DKMS hid-nintendo patchado — probe BT resiliente, ver
# docs/process/estudos/2026-07-20-desenho-onda-t-patch-dkms.md):
#   - módulo out-of-tree hid-nintendo (hefesto-hid-nintendo/1.0.0): removido
#     por DEFAULT via `dkms remove --all` (scripts/dkms_lib.sh) + a conf
#     /etc/modprobe.d/hefesto-hid-nintendo.conf. Sem flag nova (simétrico ao
#     install SEM FLAGS). O in-tree volta sozinho no próximo BOOT (replug
#     NÃO troca módulo carregado) — NUNCA descarregamos um módulo em uso
#     (mesma regra do broker/btusb); os params vivos voltam a 0 a quente.
#
# Onda W (2026-07-20, DKMS rtw88_usb patchado — fantasma USB do dongle WiFi,
# ver docs/process/estudos/2026-07-20-desenho-onda-w-patch-dkms.md):
#   - módulo out-of-tree rtw88_usb (hefesto-rtw88-usb/1.0.0): removido por
#     DEFAULT via `dkms remove --all` (mesma scripts/dkms_lib.sh, 2ª
#     instância). Sem flag nova (simétrico ao install SEM FLAGS). O in-tree
#     volta sozinho no próximo BOOT (replug do dongle NÃO troca módulo
#     carregado) — NUNCA descarregamos um módulo em uso (o WiFi cairia).
#     Diferente do hid-nintendo, não há conf em /etc/modprobe.d/ (o gate da
#     parte agressiva é o module param `hang_reset`, default Y já embutido
#     no .ko) — se o patchado estiver CARREGADO, devolvemos hang_reset a 0
#     a quente (desliga só o reset; a detecção/silenciamento continua até o
#     módulo sair de fato no próximo boot). Também remove, se presente, o
#     conf.d de powersave do NetworkManager (W2, opt-in/gateado por
#     evidência) — sem flag nova, simetria "se instalado, some".

set -euo pipefail

readonly APP_ID="hefesto-dualsense4unix"
readonly DESKTOP_TARGET="${HOME}/.local/share/applications/${APP_ID}.desktop"
readonly ICON_TARGET="${HOME}/.local/share/icons/hicolor/256x256/apps/${APP_ID}.png"
readonly LAUNCHER="${HOME}/.local/bin/hefesto-dualsense4unix-gui"
readonly BIN_SYMLINK="${HOME}/.local/bin/hefesto-dualsense4unix"
readonly HOTPLUG_UNIT_TARGET="${HOME}/.config/systemd/user/hefesto-dualsense4unix-gui-hotplug.service"

# Artefatos do applet COSMIC (instalados por packaging/cosmic-applet via sudo).
# O uninstall nativo não os conhecia → sobreviviam ao wipe (rastro deixado).
readonly APPLET_BIN="/usr/local/bin/hefesto-dualsense4unix-applet"
readonly APPLET_DESKTOP="/usr/share/applications/com.vitoriamaria.HefestoDualsense4Unix.desktop"
readonly APPLET_ICON="/usr/share/icons/hicolor/scalable/apps/com.vitoriamaria.HefestoDualsense4Unix-symbolic.svg"
readonly APPLET_ICON_PNG="/usr/share/icons/hicolor/256x256/apps/com.vitoriamaria.HefestoDualsense4Unix.png"
# Drop-in do WirePlumber (fix de microfone) — só o nosso arquivo, nunca o dir.
readonly WIREPLUMBER_DROPIN="${HOME}/.config/wireplumber/wireplumber.conf.d/51-hefesto-dualsense-no-default-source.conf"
# Variante --disable-source (node.disabled). Removida incondicionalmente (não tem
# caso de "workaround standalone" — é gerada só pelo nosso --disable-source).
readonly WIREPLUMBER_DROPIN_DISABLE="${HOME}/.config/wireplumber/wireplumber.conf.d/52-hefesto-dualsense-disable-source.conf"
# Variante --disable-output (53): gerada junto do 52 pelo --disable-source.
# Removida incondicionalmente (simetria — o uninstall esquecia dela).
readonly WIREPLUMBER_DROPIN_OUTPUT="${HOME}/.config/wireplumber/wireplumber.conf.d/53-hefesto-dualsense-disable-output.conf"
# environment.d do modo-jogo (PS_LONG_PRESS_MS=0). Hoje redundante (o default do
# código é 0), mas é artefato do hefesto — remove na desinstalação por simetria.
readonly ENVIRONMENTD_GAMEMODE="${HOME}/.config/environment.d/91-hefesto-dualsense-gamemode.conf"

readonly ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly VENV_HEFESTO="${ROOT_DIR}/.venv/bin/hefesto-dualsense4unix"

# Default: remove udev rules + modules-load (espelha install.sh, que aplica por default).
# Ver BUG-UNINSTALL-UDEV-DEFAULT-01 no cabeçalho.
REMOVE_UDEV=1
REMOVE_USB_QUIRK=0       # cmdline é sensível: só remove com --remove-usb-quirk explícito
KEEP_CONFIG=1            # preserva config por padrão (perfis do user) — apagar exige --purge-config
KEEP_STEAM_INPUT=0       # desliga Steam Input PSSupport por default (FEAT-DISABLE-STEAM-INPUT-PSSUPPORT-01)
KEEP_BLUEZ=0             # Onda R: restaura o bluez do noble por default (opt-out --keep-bluez)
AUTO_YES=0
for arg in "$@"; do
    case "$arg" in
        --keep-udev)         REMOVE_UDEV=0 ;;
        --udev)              REMOVE_UDEV=1 ;;  # deprecated: já é default; mantido p/ compat
        --remove-usb-quirk)  REMOVE_USB_QUIRK=1 ;;
        --purge-config)      KEEP_CONFIG=0 ;;
        --keep-config)       KEEP_CONFIG=1 ;;
        --keep-steam-input)  KEEP_STEAM_INPUT=1 ;;
        --keep-bluez)        KEEP_BLUEZ=1 ;;
        --yes|-y)            AUTO_YES=1 ;;
        *) printf '[uninstall] aviso: argumento desconhecido: %s\n' "$arg" ;;
    esac
done

log() { printf '[uninstall] %s\n' "$*"; }

# ---------------------------------------------------------------------------
# Credencial sudo: adquirir UMA vez no início (BUG-UNINSTALL-SUDO-NONINTERACTIVE-01)
# ---------------------------------------------------------------------------
# Simétrico ao acquire_sudo do install.sh. Vários passos usam sudo (remoção das
# udev rules + a cura do storm em /etc/modprobe.d, o applet COSMIC em /usr/local,
# o watcher dsx-recover, o `apt remove`). Sem cachear a credencial no começo, cada
# um pedia a senha por conta própria e, sem TTY, FALHAVA — deixando a cura .conf e
# o binário do applet para trás (o `sudo rm ... || true` do applet mascarava a
# falha; o bloco udev abortava com "sudo recusado/sem TTY"). Aqui primamos uma vez
# e mantemos a credencial viva durante todo o uninstall.
SUDO_KEEPALIVE_PID=""
_start_sudo_keepalive() {
    [[ -n "${SUDO_KEEPALIVE_PID}" ]] && return 0
    ( while kill -0 "$$" 2>/dev/null; do sudo -n true 2>/dev/null || exit 0; sleep 50; done ) &
    SUDO_KEEPALIVE_PID=$!
}
acquire_sudo() {
    [[ "${EUID:-$(id -u)}" -eq 0 ]] && return 0          # já é root
    command -v sudo >/dev/null 2>&1 || return 0          # sem sudo — cada passo avisa
    if sudo -n true 2>/dev/null; then                    # credencial já em cache
        _start_sudo_keepalive
        return 0
    fi
    [[ "${_NEEDS_SUDO:-1}" -eq 1 ]] || return 0          # nenhum passo com root pedido
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

# Prime a credencial só se algum passo com root vai rodar: remoção de udev
# (default), applet COSMIC instalado, watcher dsx-recover, pacote .deb ou os
# artefatos de plataforma (FastConnectable do BlueZ / cmdline registrado).
_NEEDS_SUDO=0
[[ "${REMOVE_UDEV}" -eq 1 ]] && _NEEDS_SUDO=1
# BUG-UNINSTALL-STORM-CONF-ORPHAN-KEEP-UDEV-01: storm.conf sai SEMPRE (mesmo
# com --keep-udev) — precisa entrar na priming independente do REMOVE_UDEV.
[[ -e /etc/modprobe.d/hefesto-dualsense-storm.conf ]] && _NEEDS_SUDO=1
[[ -e /etc/bluetooth/main.conf.d/hefesto-fastconnectable.conf ]] && _NEEDS_SUDO=1
grep -qsF '# >>> hefesto FastConnectable >>>' /etc/bluetooth/main.conf 2>/dev/null && _NEEDS_SUDO=1
[[ -f "${HOME}/.local/state/hefesto-dualsense4unix/cmdline-owners.conf" ]] && _NEEDS_SUDO=1
[[ -e "${APPLET_BIN}" || -e "${APPLET_DESKTOP}" || -e "${APPLET_ICON}" || -e "${APPLET_ICON_PNG}" ]] && _NEEDS_SUDO=1
[[ -e /etc/systemd/system/hefesto-dsx-recover.service ]] && _NEEDS_SUDO=1
dpkg -l "${APP_ID}" >/dev/null 2>&1 && _NEEDS_SUDO=1
# Onda R: bloco JustWorksRepairing (main.conf/drop-in), agente de pareamento
# (unit de sistema) e restauração do bluez (apt) — todos pedem root.
[[ -e /etc/bluetooth/main.conf.d/hefesto-justworks.conf ]] && _NEEDS_SUDO=1
grep -qsF '# >>> hefesto JustWorksRepairing >>>' /etc/bluetooth/main.conf 2>/dev/null && _NEEDS_SUDO=1
[[ -e /etc/systemd/system/hefesto-bt-agent.service ]] && _NEEDS_SUDO=1
[[ "${KEEP_BLUEZ}" -eq 0 && -f "${HOME}/.cache/hefesto-dualsense4unix/bluez-backport/VERSOES-ANTERIORES.txt" ]] && _NEEDS_SUDO=1
# Onda S: broker root hide-hidraw (BROKER-01) — unit de sistema, precisa root.
[[ -e /etc/systemd/system/hefesto-hidraw-broker.service ]] && _NEEDS_SUDO=1
[[ -e /etc/systemd/system/hefesto-hidraw-broker.socket ]] && _NEEDS_SUDO=1
# Onda T: DKMS hid-nintendo patchado (probe BT resiliente) — dkms remove +
# /etc/modprobe.d, ambos root. `dkms status` sem sudo já lista o registro
# (leitura de /var/lib/dkms), então a checagem de presença aqui não precisa
# de credencial — só a REMOÇÃO precisa.
[[ -e /etc/modprobe.d/hefesto-hid-nintendo.conf ]] && _NEEDS_SUDO=1
command -v dkms >/dev/null 2>&1 \
    && dkms status hefesto-hid-nintendo 2>/dev/null | grep -q . \
    && _NEEDS_SUDO=1
# Onda W: DKMS rtw88_usb patchado (fantasma USB) — dkms remove é root; sem
# conf em /etc/modprobe.d (mesma observação da Onda T: `dkms status` sem
# sudo já lista o registro, então só a REMOÇÃO precisa de credencial). O
# conf.d de powersave do NM (W2) também precisa root para remover.
command -v dkms >/dev/null 2>&1 \
    && dkms status hefesto-rtw88-usb 2>/dev/null | grep -q . \
    && _NEEDS_SUDO=1
[[ -e /etc/NetworkManager/conf.d/hefesto-wifi-powersave.conf ]] && _NEEDS_SUDO=1
acquire_sudo

log "parando daemon hefesto-dualsense4unix (se ativo)"
timeout 5 systemctl --user stop hefesto-dualsense4unix.service >/dev/null 2>&1 || true
systemctl --user disable hefesto-dualsense4unix.service >/dev/null 2>&1 || true
rm -f "${HOME}/.config/systemd/user/hefesto-dualsense4unix.service"
systemctl --user daemon-reload >/dev/null 2>&1 || true

# Mata GUIs e daemons órfãos — qualquer processo do hefesto, mesmo se rodando
# fora do systemd (CLI manual, hotplug-gui spawn, foreground dev).
#
# BUG-UNINSTALL-PKILL-SELF-01 (fix): patterns precisam ser **específicos**
# pra não casar o próprio uninstall.sh. Quando o script roda a partir de
# `/home/.../hefesto-dualsense4unix/uninstall.sh`, o cmdline do bash que o
# executa contém "hefesto-dualsense4unix" e `pkill -f 'hefesto-dualsense4unix'`
# se mata (exit 144). Os patterns abaixo casam só processos legítimos:
# `daemon ` (espaço final) cobre `daemon start/run`, `-gui` cobre o launcher,
# `_dualsense4unix` (underscore) cobre processos Python que importam o módulo.
log "matando processos hefesto*"
for pat in 'hefesto-dualsense4unix daemon ' 'hefesto-dualsense4unix-gui' 'hefesto_dualsense4unix' 'br\.andrefarias\.Hefesto'; do
    pkill -TERM -f "$pat" 2>/dev/null || true
done
sleep 2
for pat in 'hefesto-dualsense4unix daemon ' 'hefesto-dualsense4unix-gui' 'hefesto_dualsense4unix' 'br\.andrefarias\.Hefesto'; do
    pkill -KILL -f "$pat" 2>/dev/null || true
done

# Unit user de hotplug-gui (se existir)
if [[ -f "${HOTPLUG_UNIT_TARGET}" ]]; then
    log "desabilitando hefesto-dualsense4unix-gui-hotplug.service"
    systemctl --user disable hefesto-dualsense4unix-gui-hotplug.service >/dev/null 2>&1 || true
    log "removendo ${HOTPLUG_UNIT_TARGET}"
    rm -f "${HOTPLUG_UNIT_TARGET}"
    systemctl --user daemon-reload >/dev/null 2>&1 || true
else
    log "ausente: ${HOTPLUG_UNIT_TARGET}"
fi

# kernel-watch (--user; nomes storm-watch preservados por compat) — DEFAULT no
# install desde a onda PLATAFORMA. Simétrico: unit + script saem; os LOGS ficam
# (kernel.log/storm.log são dado de diagnóstico do usuário). O symlink de
# compat storm.log→kernel.log é artefato NOSSO e sai; um storm.log ARQUIVO
# real (histórico antigo) fica.
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
if [[ -L "${HOME}/.local/state/hefesto-dualsense4unix/storm.log" ]]; then
    log "removendo symlink de compat storm.log→kernel.log (o kernel.log fica — é seu histórico)"
    rm -f "${HOME}/.local/state/hefesto-dualsense4unix/storm.log"
fi

# Guard do Steam Input (path + timer, --user) — FEAT-STEAM-INPUT-SELF-HEAL-01
log "removendo guard do Steam Input (path/timer/service --user)"
systemctl --user disable --now hefesto-steam-input-guard.path hefesto-steam-input-guard.timer >/dev/null 2>&1 || true
rm -f "${HOME}/.config/systemd/user/hefesto-steam-input-guard.path" \
      "${HOME}/.config/systemd/user/hefesto-steam-input-guard.timer" \
      "${HOME}/.config/systemd/user/hefesto-steam-input-guard.service"
systemctl --user daemon-reload >/dev/null 2>&1 || true

# Watcher de auto-recuperação (serviço de sistema/root) — FEAT-DSX-RECOVER-01
if [[ -e /etc/systemd/system/hefesto-dsx-recover.service ]]; then
    log "removendo watcher hefesto-dsx-recover.service (precisa sudo)"
    sudo systemctl disable --now hefesto-dsx-recover.service >/dev/null 2>&1 || true
    sudo rm -f /etc/systemd/system/hefesto-dsx-recover.service /usr/local/sbin/dsx_recover.sh || true
    sudo systemctl daemon-reload >/dev/null 2>&1 || true
fi

# Launcher standalone "DualSense Fix (dsx)" — REMOVIDO do projeto (teoria de HW
# refutada; a cura de raiz do storm está integrada). Limpa resíduos: o
# --install-launcher gravava no ~/.local, e o .deb em /usr/share.
rm -f "${HOME}/.local/share/applications/dsx-dualsense.desktop" 2>/dev/null || true
if [[ -e /usr/share/applications/dsx-dualsense.desktop ]]; then
    sudo rm -f /usr/share/applications/dsx-dualsense.desktop 2>/dev/null || true
fi

for path in "${DESKTOP_TARGET}" "${ICON_TARGET}" "${LAUNCHER}" "${BIN_SYMLINK}"; do
    if [[ -e "${path}" ]]; then
        log "removendo ${path}"
        rm -f "${path}"
    else
        log "ausente: ${path}"
    fi
done

# FEAT-ICON-MULTI-RES-01 (fix): install.sh gera PNGs em 11 resolucoes
# (16/22/24/32/48/64/96/128/192/256/512) + SVG escalavel + pixmap
# legacy. Limpa todos. Nunca remove dirs `<size>x<size>/apps/` (outros
# apps usam).
log "removendo icones multi-res hicolor + SVG + pixmap"
for size in 16 22 24 32 48 64 96 128 192 256 512; do
    rm -f "${HOME}/.local/share/icons/hicolor/${size}x${size}/apps/${APP_ID}.png"
done
rm -f "${HOME}/.local/share/icons/hicolor/scalable/apps/${APP_ID}.svg"
rm -f "${HOME}/.local/share/pixmaps/${APP_ID}.png"

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -q -f "${HOME}/.local/share/icons/hicolor" 2>/dev/null || true
fi

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q "${HOME}/.local/share/applications" 2>/dev/null || true
fi

# Applet COSMIC nativo (Rust): instalado em /usr/local + /usr/share via sudo
# por packaging/cosmic-applet. Remove só se existir (evita pedir sudo à toa).
if [[ -e "${APPLET_BIN}" || -e "${APPLET_DESKTOP}" || -e "${APPLET_ICON}" || -e "${APPLET_ICON_PNG}" ]]; then
    log "removendo applet COSMIC (sudo): binário + .desktop + ícones"
    sudo rm -f "${APPLET_BIN}" "${APPLET_DESKTOP}" "${APPLET_ICON}" "${APPLET_ICON_PNG}" 2>/dev/null || true
    sudo gtk-update-icon-cache -q -f /usr/share/icons/hicolor 2>/dev/null || true
    sudo update-desktop-database -q /usr/share/applications 2>/dev/null || true
    # cosmic-panel só relê a lista de applets ao reiniciar — sem isso o applet
    # fica fantasma na lista de Miniaplicativos mesmo após remover os arquivos.
    command -v killall >/dev/null 2>&1 && killall cosmic-panel 2>/dev/null || true
fi

# Drop-in do WirePlumber (fix de microfone). Remove só o nosso arquivo, nunca
# o diretório wireplumber.conf.d/ (outros apps/usuário podem ter configs lá).
#
# BUG-UNINSTALL-WIREPLUMBER-WORKAROUND-PRESERVE-01 (fix): se o header do drop-in
# contiver o marker "Recriado manualmente" (ou "Recriado manualmente apos"), o
# usuário decidiu mantê-lo como workaround standalone (sem o daemon do hefesto).
# Nesse caso, preservamos — caso contrário, removemos como antes. O reinstall
# sobrescreve com a versão canônica do hefesto via --with-wireplumber-fix.
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
# Variante --disable-source (52): remove incondicional + restart (simetria com
# o --with-wireplumber-disable-mic do install.sh).
if [[ -f "${WIREPLUMBER_DROPIN_DISABLE}" ]]; then
    log "removendo drop-in WirePlumber (disable-source): ${WIREPLUMBER_DROPIN_DISABLE}"
    rm -f "${WIREPLUMBER_DROPIN_DISABLE}"
    systemctl --user restart wireplumber >/dev/null 2>&1 || true
fi

# Variante --disable-output (53): simetria com o --with-wireplumber-disable-mic.
if [[ -f "${WIREPLUMBER_DROPIN_OUTPUT}" ]]; then
    log "removendo drop-in WirePlumber (disable-output): ${WIREPLUMBER_DROPIN_OUTPUT}"
    rm -f "${WIREPLUMBER_DROPIN_OUTPUT}"
    systemctl --user restart wireplumber >/dev/null 2>&1 || true
fi

# environment.d do modo-jogo (91): artefato do hefesto — remove por simetria.
if [[ -f "${ENVIRONMENTD_GAMEMODE}" ]]; then
    log "removendo environment.d do modo-jogo: ${ENVIRONMENTD_GAMEMODE}"
    rm -f "${ENVIRONMENTD_GAMEMODE}"
fi

if [[ "${REMOVE_UDEV}" -eq 1 ]]; then
    # Conjunto canônico sincronizado com scripts/install_udev.sh + install-host-udev.sh.
    # As rules + modules-load uinput são SEMPRE instaladas em conjunto e devem
    # ser SEMPRE removidas em conjunto — não há combinação parcial suportada.
    # (75 é opt-in mas removida sempre; 76/77 entram por default desde v3.9.x.)
    #
    # BUG-UNINSTALL-SUDO-SILENT-FAIL-01 (fix): a versão anterior tinha
    # `sudo rm ... 2>/dev/null || true`, que mascarava falha de TTY para senha
    # (script chamado de subshell sem terminal) — log dizia "removendo" mas
    # nada saía. O acquire_sudo no topo já cacheia a credencial upfront; aqui só
    # testamos se dá pra sudo AGORA sem prompt via `sudo -n true` — NÃO `sudo -v`,
    # que sob `NOPASSWD:ALL` falha exigindo terminal mesmo com o sudo utilizável.
    # Falha visível se sudo não estiver disponível, com idempotência em rm -f.
    log "removendo udev rules + modules-load uinput (sudo)"
    if ! sudo -n true 2>/dev/null; then
        log "ERRO: sudo recusado/sem TTY — udev rules NÃO foram removidas."
        log "      rode: sudo bash $0 ${*:-} (ou re-execute interativamente)"
    else
        # 73/74 saíram do repo (2026-07-18) mas o rm fica: limpa instalações antigas.
        sudo rm -f /etc/udev/rules.d/70-ps5-controller.rules \
                   /etc/udev/rules.d/71-uinput.rules \
                   /etc/udev/rules.d/72-ps5-controller-autosuspend.rules \
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
                   /etc/modules-load.d/hefesto-dualsense4unix.conf \
                   /etc/modprobe.d/hefesto-btusb-no-autosuspend.conf
        # hefesto-dualsense-storm.conf NÃO entra nesta lista de propósito — ver
        # BUG-UNINSTALL-STORM-CONF-ORPHAN-KEEP-UDEV-01 logo abaixo (removido
        # SEMPRE, independente de --keep-udev).
        sudo udevadm control --reload-rules
        # Re-trigger eventos para que devices PS5 já plugados percam os
        # atributos injetados pelas rules removidas (autosuspend forçado,
        # SYSTEMD_USER_WANTS de unit inexistente). Sem isso, comportamento
        # residual persiste até desplugar/replugar ou reboot.
        sudo udevadm trigger --action=change --subsystem-match=usb 2>/dev/null || true
        sudo udevadm trigger --action=change --subsystem-match=hidraw 2>/dev/null || true
        # input: devolve os js de Motion Sensors (regra 80) e as flags ID_INPUT_*
        # (regra 78) ao default do kernel sem exigir replug.
        sudo udevadm trigger --action=change --subsystem-match=input 2>/dev/null || true
        # Regras 81 (PLAT-03): SÓ rm + reload, de propósito — o power/control
        # "on" atual dos devices/hosts NÃO é revertido a quente (é inócuo; o
        # kernel volta ao default no próximo boot/replug sem as regras).
    fi
else
    log "udev rules preservadas (--keep-udev). Para remover depois:"
    log "  sudo rm /etc/udev/rules.d/{70,72,73,74,75}-*ps5*.rules /etc/udev/rules.d/7{6,7,8}-dualsense*.rules /etc/udev/rules.d/79-external-controller-leds.rules /etc/udev/rules.d/80-motion-joydev-hide.rules /etc/udev/rules.d/81-hefesto-usb-power.rules /etc/udev/rules.d/81-hefesto-usb-host-power.rules /etc/udev/rules.d/71-uinput.rules /etc/udev/rules.d/71-uhid.rules /etc/modules-load.d/hefesto-dualsense4unix.conf /etc/modprobe.d/hefesto-btusb-no-autosuspend.conf"
fi

# ---------------------------------------------------------------------------
# BUG-UNINSTALL-STORM-CONF-ORPHAN-KEEP-UDEV-01 (fix): hefesto-dualsense-storm.conf
# (cura de raiz do storm -71, SPRINT-GAME-RUMBLE-01) morava dentro do bloco
# REMOVE_UDEV acima — com --keep-udev ele sobrevivia órfão (nem o texto do
# "para remover depois" o citava). storm.conf não é uma regra udev: é uma cura
# de /etc/modprobe.d com ciclo de vida PRÓPRIO (instalada no passo 3c do
# install, condicionado só a --no-snd-quirk). Removida SEMPRE por default aqui
# (simetria — feedback_uninstall_simetrico_default), independente de
# --keep-udev; --keep-udev preserva só as regras udev de fato.
# ---------------------------------------------------------------------------
if sudo -n true 2>/dev/null; then
    if [[ -e /etc/modprobe.d/hefesto-dualsense-storm.conf ]]; then
        log "removendo cura de raiz do storm (modprobe.d, independente de --keep-udev)"
        sudo rm -f /etc/modprobe.d/hefesto-dualsense-storm.conf
        # Limpa também o quirk_flags runtime (vale no próximo replug do controle).
        [[ -e /sys/module/snd_usb_audio/parameters/quirk_flags ]] && \
            printf '' | sudo tee /sys/module/snd_usb_audio/parameters/quirk_flags >/dev/null 2>&1 || true
    fi
elif [[ -e /etc/modprobe.d/hefesto-dualsense-storm.conf ]]; then
    log "sudo indisponível — cura de raiz do storm (modprobe.d) NÃO removida"
    log "  sudo rm /etc/modprobe.d/hefesto-dualsense-storm.conf"
fi

# ---------------------------------------------------------------------------
# FastConnectable do BlueZ (PLAT-04) — simétrico ao install 3d. Drop-in OU
# bloco marcado entre as sentinelas hefesto no /etc/bluetooth/main.conf
# (conffile do dpkg → backup antes de mexer). NUNCA reinicia o bluetoothd
# (derrubaria os controles BT conectados); a remoção vale no próximo
# boot/restart natural do serviço.
# ---------------------------------------------------------------------------
if sudo -n true 2>/dev/null; then
    if [[ -f /etc/bluetooth/main.conf.d/hefesto-fastconnectable.conf ]]; then
        log "removendo FastConnectable (drop-in /etc/bluetooth/main.conf.d)"
        sudo rm -f /etc/bluetooth/main.conf.d/hefesto-fastconnectable.conf || true
    fi
    if [[ -f /etc/bluetooth/main.conf ]] \
       && sudo grep -qF '# >>> hefesto FastConnectable >>>' /etc/bluetooth/main.conf 2>/dev/null; then
        log "removendo bloco FastConnectable do /etc/bluetooth/main.conf (backup antes)"
        sudo cp /etc/bluetooth/main.conf \
            "/etc/bluetooth/main.conf.bak.hefesto-uninstall-$(date +%s)" 2>/dev/null || true
        sudo sed -i '/^# >>> hefesto FastConnectable >>>$/,/^# <<< hefesto FastConnectable <<<$/d' \
            /etc/bluetooth/main.conf || log "  ERRO: sed do bloco marcado falhou — remova manualmente"
        log "  (vale no próximo boot/restart do bluetoothd — não reiniciamos o serviço)"
    fi
elif [[ -e /etc/bluetooth/main.conf.d/hefesto-fastconnectable.conf ]] \
     || grep -qsF '# >>> hefesto FastConnectable >>>' /etc/bluetooth/main.conf 2>/dev/null; then
    log "sudo indisponível — FastConnectable do BlueZ não removido"
    log "  (remova /etc/bluetooth/main.conf.d/hefesto-fastconnectable.conf ou o bloco"
    log "   entre as sentinelas '# >>> hefesto FastConnectable >>>' do main.conf)"
fi

# ---------------------------------------------------------------------------
# Onda R (bluetoothd 5.72 crasha crônico — estudo 2026-07-19-estudo-bluez-
# backport-onda-r.md): JustWorksRepairing do BlueZ + agente de pareamento
# persistente + restauração do bluez. Mesmo cuidado da FastConnectable: NUNCA
# reinicia o bluetoothd na remoção do bloco/drop-in (só a restauração do bluez,
# mais abaixo, reinicia — e por isso pede confirmação).
# ---------------------------------------------------------------------------

# JustWorksRepairing — sentinelas/drop-in, mesmo mecanismo da FastConnectable.
if sudo -n true 2>/dev/null; then
    if [[ -f /etc/bluetooth/main.conf.d/hefesto-justworks.conf ]]; then
        log "removendo JustWorksRepairing (drop-in /etc/bluetooth/main.conf.d)"
        sudo rm -f /etc/bluetooth/main.conf.d/hefesto-justworks.conf || true
    fi
    if [[ -f /etc/bluetooth/main.conf ]] \
       && sudo grep -qF '# >>> hefesto JustWorksRepairing >>>' /etc/bluetooth/main.conf 2>/dev/null; then
        log "removendo bloco JustWorksRepairing do /etc/bluetooth/main.conf (backup antes)"
        sudo cp /etc/bluetooth/main.conf \
            "/etc/bluetooth/main.conf.bak.hefesto-uninstall-$(date +%s)" 2>/dev/null || true
        sudo sed -i '/^# >>> hefesto JustWorksRepairing >>>$/,/^# <<< hefesto JustWorksRepairing <<<$/d' \
            /etc/bluetooth/main.conf || log "  ERRO: sed do bloco marcado falhou — remova manualmente"
        log "  (vale no próximo boot/restart do bluetoothd — não reiniciamos o serviço)"
    fi
elif [[ -e /etc/bluetooth/main.conf.d/hefesto-justworks.conf ]] \
     || grep -qsF '# >>> hefesto JustWorksRepairing >>>' /etc/bluetooth/main.conf 2>/dev/null; then
    log "sudo indisponível — JustWorksRepairing do BlueZ não removido"
    log "  (remova /etc/bluetooth/main.conf.d/hefesto-justworks.conf ou o bloco"
    log "   entre as sentinelas '# >>> hefesto JustWorksRepairing >>>' do main.conf)"
fi

# Agente de pareamento persistente (bt-agent --capability=NoInputNoOutput via
# systemd system unit) — cura o bond "Paired sem Bonded" ("No agent available
# for request type 2"). O pacote bluez-tools (dependência do bt-agent) NÃO é
# removido: é um pacote de sistema que o usuário pode querer por conta própria
# (mesma lógica de preservar libs/deps compartilhadas — ver notas de pip acima).
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

# Broker root hide-hidraw (BROKER-01/Onda S — fd-injection). Simétrico ao
# install.sh (passo 3h): disable+stop dispara o ExecStopPost
# --restore-all-and-exit da própria unit (nenhum hidraw físico fica 0600
# órfão); um belt explícito roda o MESMO restore ANTES de remover o binário
# (precisa existir ainda para rodar). Remove SÓ os caminhos que o install
# REGISTROU em broker-owner.conf e que ainda carregam o header do hefesto —
# nunca toca unit de terceiros. Desenho:
# docs/process/estudos/2026-07-20-desenho-onda-s-broker-fd-injection.md §7.2.
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
            # Sem registro (instalação de uma onda anterior, ou perdido):
            # remove só os 3 caminhos CANÔNICOS fixos, nunca glob.
            log "sem registro de posse (${BROKER_OWNER_FILE} ausente) — removendo caminhos canônicos"
            [[ -e "${BROKER_SERVICE}" ]] && sudo rm -f "${BROKER_SERVICE}"
            [[ -e "${BROKER_SOCKET}" ]] && sudo rm -f "${BROKER_SOCKET}"
            [[ -e "${BROKER_BIN}" ]] && sudo rm -f "${BROKER_BIN}"
        fi
        sudo rm -f "${BROKER_OWNER_FILE}"
        sudo systemctl daemon-reload >/dev/null 2>&1 || true
    else
        log "sudo indisponível — broker hide-hidraw NÃO removido"
        log "  sudo systemctl disable --now hefesto-hidraw-broker.socket hefesto-hidraw-broker.service"
        log "  sudo ${BROKER_BIN} --restore-all-and-exit"
        log "  sudo rm -f ${BROKER_SERVICE} ${BROKER_SOCKET} ${BROKER_BIN} ${BROKER_OWNER_FILE}"
    fi
fi

# ---------------------------------------------------------------------------
# Onda T (2026-07-20, DKMS hid-nintendo patchado — probe BT resiliente, ver
# docs/process/estudos/2026-07-20-desenho-onda-t-patch-dkms.md): removido por
# DEFAULT, sem flag nova (install é SEM FLAGS; uninstall é simétrico).
# `dkms remove --all` desregistra o pkg/versão de TODOS os kernels e apaga
# /usr/src/<pkg>-<ver>; a options do modprobe.d sai junto. O in-tree volta
# SOZINHO no próximo BOOT (dkms remove já roda depmod; replug NÃO troca
# módulo carregado) — até lá, se o patchado estiver CARREGADO, ele continua
# rodando. Para ele ficar de fato inócuo (== vanilla) devolvemos também os
# params vivos a 0 via /sys (0644, sem reload — a conf que os ligou já saiu).
# ---------------------------------------------------------------------------
if command -v dkms >/dev/null 2>&1 \
        && dkms status hefesto-hid-nintendo 2>/dev/null | grep -q .; then
    if sudo -n true 2>/dev/null; then
        log "removendo patch DKMS do hid-nintendo (Onda T): dkms remove --all"
        # shellcheck source=scripts/dkms_lib.sh
        source "${ROOT_DIR}/scripts/dkms_lib.sh"
        dkms_remove_patched_module hefesto-hid-nintendo 1.0.0
    else
        log "sudo indisponível — patch DKMS do hid-nintendo NÃO removido"
        log "  sudo dkms remove hefesto-hid-nintendo/1.0.0 --all"
    fi
fi
if [[ -e /etc/modprobe.d/hefesto-hid-nintendo.conf ]]; then
    if sudo -n true 2>/dev/null; then
        log "removendo opções do hid-nintendo patchado (/etc/modprobe.d/hefesto-hid-nintendo.conf)"
        sudo rm -f /etc/modprobe.d/hefesto-hid-nintendo.conf
        # Módulo patchado ainda CARREGADO? Devolve o comportamento vanilla a
        # quente (params 0644; NUNCA reload — derrubaria Pro/8BitDo em uso).
        if [[ -d /sys/module/hid_nintendo/parameters ]]; then
            printf '0' | sudo tee /sys/module/hid_nintendo/parameters/bt_probe_retries >/dev/null 2>&1 || true
            printf '0' | sudo tee /sys/module/hid_nintendo/parameters/skip_tx_on_rate_exceeded >/dev/null 2>&1 || true
            log "params vivos do hid_nintendo devolvidos a 0 (comportamento vanilla até o boot)"
        fi
    else
        log "sudo indisponível — /etc/modprobe.d/hefesto-hid-nintendo.conf NÃO removido"
        log "  sudo rm -f /etc/modprobe.d/hefesto-hid-nintendo.conf"
    fi
fi

# ---------------------------------------------------------------------------
# Onda W (2026-07-20, DKMS rtw88_usb patchado — fantasma USB do dongle WiFi,
# ver docs/process/estudos/2026-07-20-desenho-onda-w-patch-dkms.md): removido
# por DEFAULT, sem flag nova (install é SEM FLAGS; uninstall é simétrico).
# `dkms remove --all` desregistra o pkg/versão de TODOS os kernels e apaga
# /usr/src/<pkg>-<ver>. O in-tree volta SOZINHO no próximo BOOT (dkms remove
# já roda depmod; replug do dongle NÃO troca módulo carregado) — até lá, se
# o patchado estiver CARREGADO, ele continua rodando. Diferente da Onda T,
# não há conf em /etc/modprobe.d/ para apagar (hang_reset é module param com
# default Y embutido no .ko, não uma opção externa) — para o módulo ficar
# menos agressivo até o boot, devolvemos SÓ o hang_reset a 0 via /sys (0644,
# sem reload): desliga o usb_queue_reset_device; a detecção/silenciamento de
# device-gone continua (== comportamento rtw89 vanilla, documentado como
# troca consciente no README do patch).
# ---------------------------------------------------------------------------
if command -v dkms >/dev/null 2>&1 \
        && dkms status hefesto-rtw88-usb 2>/dev/null | grep -q .; then
    if sudo -n true 2>/dev/null; then
        log "removendo patch DKMS do rtw88_usb (Onda W): dkms remove --all"
        # shellcheck source=scripts/dkms_lib.sh
        source "${ROOT_DIR}/scripts/dkms_lib.sh"
        dkms_remove_patched_module hefesto-rtw88-usb 1.0.0
        if [[ -e /sys/module/rtw88_usb/parameters/hang_reset ]]; then
            printf '0' | sudo tee /sys/module/rtw88_usb/parameters/hang_reset >/dev/null 2>&1 || true
            log "hang_reset do rtw88_usb devolvido a 0 (sem reset agressivo até o boot; detecção/silenciamento seguem ativos)"
        fi
    else
        log "sudo indisponível — patch DKMS do rtw88_usb NÃO removido"
        log "  sudo dkms remove hefesto-rtw88-usb/1.0.0 --all"
    fi
fi
# Conf.d de powersave do WiFi (W2 — opt-in/gateado por evidência, NÃO
# instalado por default pelo install.sh hoje): removido SE presente, sem
# flag nova (simetria "se instalado, some" — mesmo padrão do storm.conf).
# Só rm de um arquivo .conf: NUNCA chamamos nmcli/rfkill aqui.
if [[ -e /etc/NetworkManager/conf.d/hefesto-wifi-powersave.conf ]]; then
    if sudo -n true 2>/dev/null; then
        log "removendo conf de powersave do WiFi (/etc/NetworkManager/conf.d/hefesto-wifi-powersave.conf)"
        sudo rm -f /etc/NetworkManager/conf.d/hefesto-wifi-powersave.conf
    else
        log "sudo indisponível — /etc/NetworkManager/conf.d/hefesto-wifi-powersave.conf NÃO removido"
        log "  sudo rm -f /etc/NetworkManager/conf.d/hefesto-wifi-powersave.conf"
    fi
fi

# Restauração do bluez (backport 5.85 → versões originais do noble). Por
# DEFAULT o uninstall É simétrico: devolve o pacote ao estado pré-Hefesto —
# ficar com um bluez de terceiro (~hefesto24.04.1) órfão, sem o
# doctor/pin/gerenciamento que o justificava, é pior do que voltar ao
# 5.72 do noble. --keep-bluez preserva o backport (opt-out explícito: é
# REMOÇÃO BRUTAL de propósito, pois reinicia o bluetoothd — a ÚNICA exceção
# documentada à regra "uninstall nunca reinicia o bluetoothd" — e descarta os
# bonds pareados outra vez, os mesmos efeitos colaterais medidos na migração
# de ida). Por isso pede confirmação interativa antes de aplicar (--yes pula).
BLUEZ_BACKPORT_CACHE="${HOME}/.cache/hefesto-dualsense4unix/bluez-backport"
BLUEZ_VERSOES_FILE="${BLUEZ_BACKPORT_CACHE}/VERSOES-ANTERIORES.txt"
if [[ "${KEEP_BLUEZ}" -eq 1 ]]; then
    log "bluez backport preservado (--keep-bluez) — a versão atual continua ativa"
elif [[ ! -f "${BLUEZ_VERSOES_FILE}" ]]; then
    log "sem registro de backport do bluez (${BLUEZ_VERSOES_FILE} ausente) — nada a restaurar"
elif ! sudo -n true 2>/dev/null; then
    log "sudo indisponível — bluez backport NÃO restaurado"
    log "  reverta manualmente com as versões de ${BLUEZ_VERSOES_FILE}"
else
    # Monta pkg=versão só para os pacotes do registro que estão REALMENTE
    # instalados agora (dpkg -l) — evita o apt tentar reinstalar algo ausente.
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
            # Se o apt reclamar de versão indisponível, o archive do noble-updates
            # pode ter revisado o pacote desde a captura do registro — restaure
            # manualmente com a versão disponível mais próxima ou mantenha o
            # backport (--keep-bluez).
            # DEBIAN_FRONTEND=noninteractive + --force-confdef/--force-confold: o
            # main.conf continua sendo o conffile MODIFICADO pelo hefesto (bloco
            # FastConnectable/JustWorks) neste ponto — sem forçar, o dpkg pode
            # parar esperando resposta interativa sobre o que fazer com o conffile.
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

# Quirk de boot do áudio USB (usbcore.quirks). NÃO removido por default: é
# cmdline do kernel (sensível) e pode ser mantido por toolchain externa do
# usuário (ex.: Ritual da Aurora, dona dos kernel params). Só sai com a flag
# explícita --remove-usb-quirk. install_usb_quirk.sh --remove é idempotente
# (no-op se o token já estiver ausente).
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

# ---------------------------------------------------------------------------
# Cmdline gerenciado (PLAT-03) — reverte SÓ o que o install registrou como
# NOSSO no estado local (cmdline-owners.conf). "terceiro" (Aurora/manual)
# NUNCA é tocado; "compartilhado" (token usbcore.quirks fundido) perde SÓ os
# IDs do hefesto (strip_quirks_token do módulo puro) e o restante é re-adicionado.
# Sem registro = install nunca escreveu cmdline = nada a reverter.
# ---------------------------------------------------------------------------
CMDLINE_OWNERS_FILE="${HOME}/.local/state/hefesto-dualsense4unix/cmdline-owners.conf"
if [[ -f "${CMDLINE_OWNERS_FILE}" ]]; then
    _cmdline_reverted=0
    if ! command -v kernelstub >/dev/null 2>&1; then
        log "cmdline: registro presente mas sem kernelstub — reverta manualmente os"
        log "  params marcados 'hefesto' em ${CMDLINE_OWNERS_FILE} (registro preservado)"
    elif ! sudo -n true 2>/dev/null; then
        log "cmdline: sudo indisponível — params NÃO revertidos (registro preservado;"
        log "  re-execute o uninstall com sudo para reverter)"
    else
        _own_autosusp="$(sed -n 's/^cmdline\.usbcore\.autosuspend=//p' "${CMDLINE_OWNERS_FILE}" | head -1)"
        _own_quirks="$(sed -n 's/^cmdline\.usbcore\.quirks=//p' "${CMDLINE_OWNERS_FILE}" | head -1)"
        _cmdline_reverted=1
        if [[ "${_own_autosusp}" == "hefesto" ]]; then
            log "cmdline: removendo usbcore.autosuspend=-1 (registrado como nosso; vale no próximo boot)"
            sudo kernelstub --delete-options "usbcore.autosuspend=-1" >/dev/null 2>&1 \
                || log "  ERRO: kernelstub --delete-options falhou — rode manualmente"
        elif [[ -n "${_own_autosusp}" ]]; then
            log "cmdline: usbcore.autosuspend é de ${_own_autosusp} — preservado"
        fi
        if [[ "${_own_quirks}" == "hefesto" || "${_own_quirks}" == "compartilhado" ]]; then
            if command -v python3 >/dev/null 2>&1; then
                _quirks_plan="$(python3 - "${ROOT_DIR}" <<'PYEOF'
import json
import os
import sys

root = sys.argv[1]
sys.path.insert(0, os.path.join(root, "src"))
from hefesto_dualsense4unix.integrations import kernel_cmdline as kc

try:
    with open("/etc/kernelstub/configuration", encoding="utf-8") as fh:
        data = json.load(fh)
    tokens = list((data.get("user") or {}).get("kernel_options") or [])
except (OSError, ValueError):
    raise SystemExit(0)
for tok in kc.tokens_for_param(tokens, kc.QUIRKS_PARAM):
    rest, changed = kc.strip_quirks_token(tok)
    if not changed:
        continue
    print("del\t" + tok)
    if rest is not None:
        print("add\t" + rest)
PYEOF
)" || _quirks_plan=""
                if [[ -n "${_quirks_plan}" ]]; then
                    log "cmdline: removendo os IDs do hefesto do usbcore.quirks (dono: ${_own_quirks}; vale no próximo boot)"
                    while IFS=$'\t' read -r _qop _qtok; do
                        case "${_qop}" in
                            del) sudo kernelstub --delete-options "${_qtok}" >/dev/null 2>&1 \
                                     || log "  ERRO: delete-options '${_qtok}' falhou" ;;
                            add) sudo kernelstub --add-options "${_qtok}" >/dev/null 2>&1 \
                                     || log "  ERRO: add-options '${_qtok}' falhou (re-adicione o restante do token!)" ;;
                        esac
                    done <<<"${_quirks_plan}"
                else
                    log "cmdline: usbcore.quirks sem IDs nossos na configuration — nada a reverter"
                fi
            else
                log "cmdline: sem python3 — usbcore.quirks compartilhado NÃO revertido (registro preservado)"
                _cmdline_reverted=0
            fi
        elif [[ -n "${_own_quirks}" ]]; then
            log "cmdline: usbcore.quirks é de ${_own_quirks} — preservado"
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

# Caches Python e build (deixar resíduos quebra reinstall com module-rename).
for cache in .pytest_cache .ruff_cache .mypy_cache flatpak-build-dir .flatpak-builder dist build; do
    if [[ -d "${ROOT_DIR}/${cache}" ]]; then
        log "removendo ${cache}"
        rm -rf "${ROOT_DIR}/${cache}"
    fi
done

# Bytecode espalhado: __pycache__/ em src/ tests/ scripts/
find "${ROOT_DIR}" -type d -name "__pycache__" \
    -not -path "*/\.git/*" \
    -exec rm -rf {} + 2>/dev/null || true
find "${ROOT_DIR}" -type f -name "*.pyc" \
    -not -path "*/\.git/*" \
    -delete 2>/dev/null || true

# Glyphs SVG copiados pelo install.sh (step 4b) — sao artefatos do pacote, não
# dados do usuário, entao removemos sempre (independente de --purge-config).
# BUG-UNINSTALL-GLYPHS-ORPHAN-01: ficavam em ~/.local/share/hefesto-dualsense4unix/
# glyphs/ apos uninstall, criando rastro.
if [[ -d "${HOME}/.local/share/hefesto-dualsense4unix/glyphs" ]]; then
    log "removendo glyphs do user"
    rm -rf "${HOME}/.local/share/hefesto-dualsense4unix/glyphs"
fi

# BUG-UNINSTALL-SHARE-DIR-ORPHAN-01 (fix): após remover glyphs/ (e quaisquer
# outros subdirs no futuro), o diretório-pai fica vazio mas presente, marcando
# ~/.local/share/hefesto-dualsense4unix/ como rastro órfão. Removemos só se
# estiver vazio — preserva dados se algo foi colocado lá fora do install.sh.
if [[ -d "${HOME}/.local/share/hefesto-dualsense4unix" ]] \
   && [[ -z "$(ls -A "${HOME}/.local/share/hefesto-dualsense4unix" 2>/dev/null)" ]]; then
    log "removendo diretório-pai vazio ~/.local/share/hefesto-dualsense4unix"
    rmdir "${HOME}/.local/share/hefesto-dualsense4unix" 2>/dev/null || true
fi

# .deb instalado via apt: sudo apt remove (idempotente — silencioso se ausente).
if dpkg -l hefesto-dualsense4unix >/dev/null 2>&1; then
    log "removendo pacote .deb hefesto-dualsense4unix (sudo)"
    sudo apt-get remove -y hefesto-dualsense4unix >/dev/null 2>&1 || true
fi

# Flatpak: desinstalar app + cleanup runtime (mas não remove runtime GNOME
# se outras apps usam — flatpak gerencia rc).
if flatpak list --user --app 2>/dev/null | grep -q "br.andrefarias.Hefesto"; then
    log "desinstalando Flatpak br.andrefarias.Hefesto"
    flatpak uninstall --user -y br.andrefarias.Hefesto >/dev/null 2>&1 || true
fi
# Cache flatpak do app (logs, dados em runtime/sandbox)
rm -rf "${HOME}/.var/app/br.andrefarias.Hefesto" 2>/dev/null || true

# AppImage em locais convencionais
for appimg_dir in "${HOME}/Aplicativos" "${HOME}/Applications" "${HOME}/Downloads" "${HOME}/.local/bin"; do
    [[ -d "$appimg_dir" ]] || continue
    for f in "$appimg_dir"/Hefesto-Dualsense4Unix*.AppImage "$appimg_dir"/hefesto-dualsense4unix*.AppImage; do
        if [[ -f "$f" ]]; then
            log "removendo AppImage ${f}"
            rm -f "$f"
        fi
    done
done

# Configs e dados do user. PRESERVADOS por padrão; --purge-config apaga (com
# backup antes). Cobre o caminho atual (longo) E o legado curto (~/.config/
# hefesto), onde versões pré-rename gravavam perfis/sessão/preferências.
if [[ "${KEEP_CONFIG}" -eq 0 ]]; then
    backup_dir="${HOME}/.config/hefesto-dualsense4unix.backup-$(date +%s)"
    backed_up=0
    for path in \
        "${HOME}/.config/hefesto-dualsense4unix" \
        "${HOME}/.local/share/hefesto-dualsense4unix" \
        "${HOME}/.cache/hefesto-dualsense4unix" \
        "${HOME}/.config/hefesto" \
        "${HOME}/.local/share/hefesto" \
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
    # paused.flag (FEAT-DAEMON-PAUSE-RESUME-01) fica em ~/.config/hefesto-dualsense4unix/
    # e e propositalmente preservado junto com a config, para o usuário retomar
    # do mesmo estado se reinstalar. Use --purge-config para apaga-lo tambem.
fi

# BUG-UNINSTALL-LOCALE-NOT-REMOVED-01 (fix): catalogos .mo do install.sh
# step 4d (FEAT-I18N-CATALOGS-01) ficavam orfaos em ~/.local/share/locale/
# <lang>/LC_MESSAGES/. Removemos so o nosso domain (`hefesto-dualsense4unix.mo`),
# nunca o LC_MESSAGES/ ou <lang>/ inteiro — outros apps podem usar.
log "removendo catalogos i18n .mo do user"
for lang_dir in "${HOME}/.local/share/locale"/*/; do
    [[ -d "$lang_dir" ]] || continue
    mo="${lang_dir}LC_MESSAGES/${APP_ID}.mo"
    if [[ -f "$mo" ]]; then
        log "  ${mo}"
        rm -f "$mo"
    fi
done

# Runtime dir do socket IPC e pid files (sempre limpa, é volátil)
runtime_dir="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/hefesto-dualsense4unix"
if [[ -d "$runtime_dir" ]]; then
    log "removendo ${runtime_dir}"
    rm -rf "$runtime_dir"
fi

# Pip user packages (deps modernas que install.sh ou usuário possa ter colocado)
# Não removidas por default — podem ser usadas por outros apps. Deixar como
# nota informativa.
log "(nota) deps Python via pip --user em ~/.local/lib/python*/site-packages preservadas"
log "       — remova manualmente se quiser wipe absoluto do user-site"

# BUG-UNINSTALL-OUT-OF-SCOPE-CLARITY-01: documentar o que o uninstall
# explicitamente NÃO toca, pra evitar atribuição equivocada de problemas
# de outras toolchains ao hefesto.
log ""
log "fora do escopo (não removido — não é do hefesto):"
log "  /etc/udev/rules.d/99-usb-*.rules         — toolchain de power-mgmt do user (ex: Aurora self-heal)"
log "  /etc/udev/rules.d/99-storage-no-link-pm.rules — idem (storage PM)"
log "  /etc/udev/rules.d/50-system76-power.rules    — polkit pra system76-power (Pop_OS)"
log "  kernel cmdline de TERCEIRO (pcie_aspm, mitigations, etc.) — só os params"
log "    REGISTRADOS como do hefesto (cmdline-owners.conf) são revertidos acima"
log "  ~/.config/wireplumber/wireplumber.conf.d/   — dir compartilhado, só nosso .conf é removido"
log "  ~/.local/lib/python*/site-packages/         — pip --user pode ser compartilhado"

# FEAT-DISABLE-STEAM-INPUT-PSSUPPORT-01: desliga Steam Input PSSupport em
# todos os localconfig.vdf por default. Simétrico com install.sh — sem isso,
# o usuário desinstala o Hefesto e os sintomas que o levaram a desinstalar
# (touchpad como mouse, mic spam, botões em background) voltam IMEDIATAMENTE
# porque a Steam preenche o vácuo do controle. Reverter:
# scripts/disable_steam_input.sh --restore (mantém os backups .bak.steam-input-<ts>).
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

# PLAT-01: destrava o CompatToolMapping do Proton pinado — SÓ o que NÓS
# escrevemos (registro em ~/.local/state/.../proton-pin-lock.json). Roda ANTES
# do strip das Launch Options DE PROPÓSITO: o strip (--stop-steam) REABRE a
# Steam ao final, e o unlock exige Steam fechada. O Proton EXTRAÍDO em
# compatibilitytools.d FICA — é dado do usuário (apague a pasta GE-Proton*
# manualmente se não quiser mais).
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

# DEDUP-04/DEDUP-05 (INCONDICIONAL, sem flag — o índice da onda manda): remove
# das LaunchOptions o NOSSO trecho, novo E legado. Ordem OBRIGATÓRIA: o vdf é
# desenvenenado ANTES de apagar o wrapper (regra histórica da simetria — a
# assimetria já quebrou o mic; aqui, com o hefesto desinstalado, o veneno
# `IGNORE_DEVICES` persistido esconderia o físico => jogo com ZERO controles,
# e a revisão REFUTOU qualquer gate neste caminho). `__GL_SHADER_*` e opções
# do usuário são preservadas byte a byte. --stop-steam: a Steam regrava o vdf
# ao sair, então o strip fecha (e reabre) a Steam se preciso.
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

# Só DEPOIS do vdf limpo o wrapper pode sair (simetria com o passo 4b-2 do
# install.sh). O launch_env/ é materialização volátil do daemon — sai junto.
readonly LAUNCH_WRAPPER="${HOME}/.local/share/hefesto-dualsense4unix/bin/hefesto-launch"
if [[ -e "${LAUNCH_WRAPPER}" ]]; then
    log "removendo wrapper de launch ${LAUNCH_WRAPPER}"
    rm -f "${LAUNCH_WRAPPER}"
fi
# PATH-06: o symlink do wrapper no PATH sai junto (simétrico ao passo 5 do install).
if [[ -L "${HOME}/.local/bin/hefesto-launch" || -e "${HOME}/.local/bin/hefesto-launch" ]]; then
    log "removendo symlink ${HOME}/.local/bin/hefesto-launch"
    rm -f "${HOME}/.local/bin/hefesto-launch"
fi
rmdir "${HOME}/.local/share/hefesto-dualsense4unix/bin" 2>/dev/null || true
if [[ -d "${HOME}/.local/state/hefesto-dualsense4unix/launch_env" ]]; then
    log "removendo materialização de launch (~/.local/state/hefesto-dualsense4unix/launch_env)"
    rm -rf "${HOME}/.local/state/hefesto-dualsense4unix/launch_env"
fi
rmdir "${HOME}/.local/state/hefesto-dualsense4unix" 2>/dev/null || true
# O passo anterior de limpeza do share-dir roda antes do wrapper sair — repete
# a checagem de diretório-pai vazio para não deixar rastro.
if [[ -d "${HOME}/.local/share/hefesto-dualsense4unix" ]] \
   && [[ -z "$(ls -A "${HOME}/.local/share/hefesto-dualsense4unix" 2>/dev/null)" ]]; then
    rmdir "${HOME}/.local/share/hefesto-dualsense4unix" 2>/dev/null || true
fi

printf '\n─────────────────────────────────────────\n'
printf ' Hefesto - Dualsense4Unix desinstalado (wipe completo)\n'
printf '─────────────────────────────────────────\n\n'
