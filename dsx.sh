#!/usr/bin/env bash
# dsx.sh — "DualSense Fix": reaplica TUDO e diagnostica em 1 clique.
#
# Para o storm -71 do DualSense + HDMI piscando quando a Steam sobe. Causa-raiz:
# o DualSense está no controlador USB do Ryzen (0c:00.3), mesmo I/O die da linha
# PCIe da RTX 4060 — um blip de power acopla USB (controle cai) e GPU (HDMI pisca).
# Diagnóstico completo + playbook: docs/process/sprints/FEAT-DSX-DEFINITIVE-FIX-01.md
#
# Ordem: Aurora self-heal (re-pin kernel/power/OOM) -> udev hefesto -> Steam Input
#        OFF -> WirePlumber só-HID -> re-pin power (GPU/xHCI/DualSense) -> udevadm
#        trigger -> instala/garante watcher + guard -> restart daemon -> doctor.
#
# Uso:
#   ./dsx.sh                    reaplica tudo + diagnostica (pede sudo)
#   ./dsx.sh --install-launcher grava o atalho de duplo-clique (menu + Desktop)
#   ./dsx.sh --no-sudo          só as etapas que não precisam de root
#
# Duplo-clique no COSMIC Files: rode antes `./dsx.sh --install-launcher` e use o
# ícone "DualSense Fix (dsx)" — ele abre um terminal (Terminal=true).
set -euo pipefail

readonly ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly AURORA_HEAL="/usr/local/sbin/ritual-aurora-self-heal.sh"
readonly APP_ID="hefesto-dualsense4unix"
readonly USER_UNIT_DIR="${HOME}/.config/systemd/user"

c_ok=$'\033[1;32m'; c_warn=$'\033[1;33m'; c_err=$'\033[1;31m'; c_rst=$'\033[0m'
step() { printf '\n%s==>%s %s\n' "$c_ok" "$c_rst" "$*"; }
ok()   { printf '   %s%s %s\n' "$c_ok" "$c_rst" "$*"; }
warn() { printf '%s[aviso]%s %s\n' "$c_warn" "$c_rst" "$*"; }
errp() { printf '%s[ERRO]%s %s\n'  "$c_err"  "$c_rst" "$*"; }

WANT_SUDO=1
for arg in "$@"; do
    case "$arg" in
        --install-launcher) ;;   # tratado abaixo, antes do fluxo principal
        --no-sudo) WANT_SUDO=0 ;;
        -h|--help) sed -n '2,22p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) warn "argumento desconhecido: $arg" ;;
    esac
done

# ---------------------------------------------------------------------------
# --install-launcher: grava o .desktop com caminho absoluto resolvido
# ---------------------------------------------------------------------------
install_launcher() {
    local apps="${HOME}/.local/share/applications"
    local dst="${apps}/dsx-dualsense.desktop"
    mkdir -p "$apps"
    if [[ ! -f "${ROOT_DIR}/assets/dsx.desktop" ]]; then
        errp "assets/dsx.desktop ausente"; return 1
    fi
    sed "s#__DSX_PATH__#${ROOT_DIR}/dsx.sh#g" "${ROOT_DIR}/assets/dsx.desktop" > "$dst"
    chmod +x "$dst" 2>/dev/null || true
    command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$apps" 2>/dev/null || true
    ok "atalho no menu: $dst"
    # Cópia no Desktop p/ duplo-clique direto (COSMIC exige bit trusted).
    local desk="${XDG_DESKTOP_DIR:-}"
    [[ -z "$desk" || ! -d "$desk" ]] && desk="${HOME}/Área de Trabalho"
    [[ -d "$desk" ]] || desk="${HOME}/Desktop"
    if [[ -d "$desk" ]]; then
        cp "$dst" "${desk}/dsx-dualsense.desktop" && chmod +x "${desk}/dsx-dualsense.desktop"
        gio set "${desk}/dsx-dualsense.desktop" metadata::trusted true 2>/dev/null || true
        ok "atalho no Desktop: ${desk}/dsx-dualsense.desktop (duplo-clique)"
    else
        warn "pasta Desktop não encontrada — use o atalho do menu (busque 'DualSense Fix')"
    fi
}
if [[ " $* " == *" --install-launcher "* ]]; then
    install_launcher
    exit 0
fi

# ---------------------------------------------------------------------------
# sudo com keep-alive
# ---------------------------------------------------------------------------
HAVE_SUDO=0
SUDO_KEEPALIVE_PID=""
ensure_sudo() {
    [[ "$WANT_SUDO" -eq 1 ]] || { warn "--no-sudo: etapas de root puladas"; return 1; }
    command -v sudo >/dev/null 2>&1 || { warn "sudo ausente — etapas de root puladas"; return 1; }
    step "autenticação (sudo) — pode pedir sua senha"
    sudo -v || { errp "sudo falhou — sigo só com as etapas sem root"; return 1; }
    ( while true; do sudo -n true; sleep 50; kill -0 "$$" 2>/dev/null || exit; done ) 2>/dev/null &
    SUDO_KEEPALIVE_PID=$!
    return 0
}
cleanup() { [[ -n "${SUDO_KEEPALIVE_PID}" ]] && kill "${SUDO_KEEPALIVE_PID}" 2>/dev/null || true; }
trap cleanup EXIT

ensure_sudo && HAVE_SUDO=1 || true

# ---------------------------------------------------------------------------
# instala/garante o watcher (root) e o guard (--user) — idempotente
# ---------------------------------------------------------------------------
ensure_services() {
    # guard do Steam Input (--user)
    mkdir -p "${USER_UNIT_DIR}"
    install -Dm644 "${ROOT_DIR}/assets/hefesto-steam-input-guard.path"  "${USER_UNIT_DIR}/hefesto-steam-input-guard.path"  2>/dev/null || true
    install -Dm644 "${ROOT_DIR}/assets/hefesto-steam-input-guard.timer" "${USER_UNIT_DIR}/hefesto-steam-input-guard.timer" 2>/dev/null || true
    sed "s#__SCRIPT__#${ROOT_DIR}/scripts/disable_steam_input.sh#g" \
        "${ROOT_DIR}/assets/hefesto-steam-input-guard.service" > "${USER_UNIT_DIR}/hefesto-steam-input-guard.service" 2>/dev/null || true
    systemctl --user daemon-reload 2>/dev/null || true
    if systemctl --user enable --now hefesto-steam-input-guard.path hefesto-steam-input-guard.timer 2>/dev/null; then
        ok "guard do Steam Input ativo (path + timer 30min)"
    else
        warn "não habilitei o guard --user (sessão systemd ausente?) — pega no próximo login"
    fi
    # watcher de auto-recuperação (root)
    if [[ "$HAVE_SUDO" -eq 1 ]]; then
        sudo install -Dm755 "${ROOT_DIR}/scripts/dsx_recover.sh" /usr/local/sbin/dsx_recover.sh
        sudo install -Dm644 "${ROOT_DIR}/assets/hefesto-dsx-recover.service" /etc/systemd/system/hefesto-dsx-recover.service
        sudo systemctl daemon-reload
        if sudo systemctl enable --now hefesto-dsx-recover.service 2>/dev/null; then
            ok "watcher de auto-recuperação ativo (hefesto-dsx-recover.service)"
        else
            warn "não habilitei o watcher — confira: systemctl status hefesto-dsx-recover.service"
        fi
    else
        warn "sem sudo — watcher de auto-recuperação NÃO instalado"
    fi
}

# ---------------------------------------------------------------------------
# fluxo principal
# ---------------------------------------------------------------------------
step "(a) Aurora self-heal (re-pin kernel/power/OOM)"
if [[ "$HAVE_SUDO" -eq 1 && -x "$AURORA_HEAL" ]]; then
    sudo "$AURORA_HEAL" && ok "self-heal OK (log: /var/log/ritual-aurora-self-heal.log)" \
        || warn "self-heal retornou erro — veja /var/log/ritual-aurora-self-heal.log"
else
    warn "Aurora self-heal indisponível ($AURORA_HEAL) ou sem sudo — pulado"
fi

step "(b) regras udev do hefesto (+ DualSense pure-HID no USB)"
if [[ "$HAVE_SUDO" -eq 1 && -x "${ROOT_DIR}/scripts/install_udev.sh" ]]; then
    # --disable-usb-audio: regra 75 que deixa o controle só-HID no nível USB
    # (sem áudio nenhum), reduzindo a superfície que alimenta o storm -71.
    sudo bash "${ROOT_DIR}/scripts/install_udev.sh" --disable-usb-audio && ok "udev reaplicado (+ pure-HID)" || warn "install_udev.sh falhou"
else
    warn "sem sudo ou install_udev.sh ausente — udev pulado"
fi

step "(c) Steam Input PSSupport OFF"
bash "${ROOT_DIR}/scripts/disable_steam_input.sh" --apply && ok "PSSupport OFF" \
    || warn "disable_steam_input falhou"

step "(d) WirePlumber: desabilitar a source do DualSense (só-HID)"
rc=0; bash "${ROOT_DIR}/scripts/fix_wireplumber_default_source.sh" --disable-source || rc=$?
case "$rc" in
    0) ok "mic do DualSense desabilitado; microfone ativo != DualSense" ;;
    2) warn "DualSense ainda ativo por ser a ÚNICA fonte — conecte mic/webcam (mas o drop-in está aplicado)" ;;
    *) warn "disable-source retornou erro ($rc) — veja a saída acima" ;;
esac

step "(e) re-pin de power (GPU/xHCI/DualSense)"
if [[ "$HAVE_SUDO" -eq 1 ]]; then
    sudo bash -c '
        for f in /sys/bus/pci/devices/0000:0a:00.0/power/control \
                 /sys/bus/pci/devices/0000:0a:00.1/power/control; do
            [ -w "$f" ] && echo on > "$f" 2>/dev/null && echo "   pin GPU $f = on"
        done
        for f in /sys/bus/pci/drivers/xhci_hcd/*/power/control; do
            [ -w "$f" ] && echo on > "$f" 2>/dev/null
        done
        for d in /sys/bus/usb/devices/*; do
            [ -r "$d/idVendor" ] || continue
            [ "$(cat "$d/idVendor" 2>/dev/null)" = "054c" ] || continue
            echo on > "$d/power/control" 2>/dev/null && echo "   pin DualSense $(basename "$d") control=on"
            echo -1 > "$d/power/autosuspend_delay_ms" 2>/dev/null || true
        done
    ' && ok "power fixado" || warn "re-pin parcial"
else
    warn "sem sudo — re-pin pulado"
fi

step "(f) udevadm trigger (re-enumera sem mexer em porta)"
if [[ "$HAVE_SUDO" -eq 1 ]]; then
    sudo udevadm control --reload-rules 2>/dev/null || true
    sudo udevadm trigger --subsystem-match=usb --attr-match=idVendor=054c 2>/dev/null || true
    ok "udev disparado para o DualSense (054c)"
else
    warn "sem sudo — udevadm trigger pulado"
fi

step "(serviços) garantir watcher + guard instalados"
ensure_services

step "(g) restart do daemon hefesto (se instalado)"
if command -v systemctl >/dev/null 2>&1 && systemctl --user cat "${APP_ID}.service" >/dev/null 2>&1; then
    systemctl --user restart "${APP_ID}.service" && ok "${APP_ID}.service reiniciado" \
        || warn "restart do daemon falhou"
else
    printf '   daemon não instalado como serviço --user — pulado\n'
fi

step "(h) diagnóstico final (doctor.sh)"
bash "${ROOT_DIR}/scripts/doctor.sh" || true

printf '\n%s==> dsx concluído.%s\n' "$c_ok" "$c_rst"
printf '   Se o controle ainda cair, veja em tempo real:  scripts/doctor.sh --watch-dropout\n'
printf '   Para o HDMI parar de piscar de vez, é preciso REBOOTAR uma vez (nvidia-drm.fbdev=1).\n'

# Pausa só em terminal interativo (duplo-clique abre terminal com TTY).
if [[ -t 0 && -t 1 ]]; then
    read -r -n 1 -p "Pressione qualquer tecla para fechar..." _ || true
    echo
fi
