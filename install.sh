#!/usr/bin/env bash
# install.sh — instala Hefesto completo no ambiente do usuário.
#
# Orquestra, em ordem: dependências do sistema, venv + pacote editável,
# udev rules (hidraw + uinput + USB autosuspend), atalho .desktop + ícone,
# launcher desanexado, symlink bin, unit systemd --user, start do daemon.
#
# Flags:
#   --no-udev        pula a instalação de udev rules (sudo) — útil em CI.
#   --yes, -y        responde 'sim' ao prompt de sudo das udev rules.
#   --no-systemd     pula install + start da unit systemd do daemon.
#   --no-hotplug-gui pula a unit user que abre a GUI ao plugar o controle.
#
# Reexecutável (idempotente).

set -euo pipefail

readonly ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly VENV_DIR="${ROOT_DIR}/.venv"
readonly APP_ID="hefesto"
readonly ICON_SRC="${ROOT_DIR}/assets/appimage/Hefesto.png"
readonly DESKTOP_TARGET="${HOME}/.local/share/applications/${APP_ID}.desktop"
readonly ICON_TARGET_DIR="${HOME}/.local/share/icons/hicolor/256x256/apps"
readonly ICON_TARGET="${ICON_TARGET_DIR}/${APP_ID}.png"
readonly BIN_DIR="${HOME}/.local/bin"
readonly LAUNCHER="${BIN_DIR}/hefesto-gui"

SKIP_UDEV=0
SKIP_SYSTEMD=0
SKIP_HOTPLUG_GUI=0
AUTO_YES=0

for arg in "$@"; do
    case "$arg" in
        --no-udev)        SKIP_UDEV=1 ;;
        --no-systemd)     SKIP_SYSTEMD=1 ;;
        --no-hotplug-gui) SKIP_HOTPLUG_GUI=1 ;;
        --yes|-y)         AUTO_YES=1 ;;
        -h|--help)
            sed -n '2,15p' "${BASH_SOURCE[0]}" | sed 's/^# //; s/^#//'
            exit 0
            ;;
        *) printf '[install] aviso: argumento desconhecido: %s\n' "$arg" ;;
    esac
done

log() { printf '[install] %s\n' "$*"; }
die() { printf '[install] ERRO: %s\n' "$*" >&2; exit 1; }

require() {
    command -v "$1" >/dev/null 2>&1 || die "dependencia ausente: $1"
}

###############################################################################
# 1. Dependências do sistema
###############################################################################
log "[1/7] checando dependencias do sistema"
require python3
require pkg-config || true

###############################################################################
# 2. venv + pacote editável
###############################################################################
log "[2/7] preparando venv e instalando o pacote"
if [[ ! -d "${VENV_DIR}" ]]; then
    log "criando venv em ${VENV_DIR}"
    python3 -m venv --system-site-packages "${VENV_DIR}"
fi

if ! "${VENV_DIR}/bin/python" -c \
        "import gi; gi.require_version('Gtk','3.0')" >/dev/null 2>&1; then
    cat >&2 <<'MSG'
[install] bindings GTK3 ausentes no sistema. Instale:
  sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0 \
                   gir1.2-ayatanaappindicator3-0.1 libgirepository1.0-dev \
                   libcairo2-dev desktop-file-utils imagemagick
MSG
    exit 1
fi

"${VENV_DIR}/bin/python" -m pip install --quiet --upgrade pip packaging
"${VENV_DIR}/bin/pip" install --quiet -e "${ROOT_DIR}"

###############################################################################
# 3. udev rules (requer sudo)
###############################################################################
if [[ "${SKIP_UDEV}" -eq 1 ]]; then
    log "[3/7] udev rules puladas (--no-udev)"
else
    log "[3/7] udev rules: hidraw + uinput + USB autosuspend + hotplug GUI"
    need_udev=1
    # Se as quatro regras já estão em /etc/udev/rules.d/, pula com aviso
    if [[ -f /etc/udev/rules.d/70-ps5-controller.rules ]] \
       && [[ -f /etc/udev/rules.d/71-uinput.rules ]] \
       && [[ -f /etc/udev/rules.d/72-ps5-controller-autosuspend.rules ]] \
       && [[ -f /etc/udev/rules.d/73-ps5-controller-hotplug.rules ]]; then
        log "udev rules ja instaladas, pulando (use uninstall.sh para remover)"
        need_udev=0
    fi

    if [[ "${need_udev}" -eq 1 ]]; then
        if [[ "${AUTO_YES}" -eq 0 ]]; then
            cat <<'MSG'

As udev rules dao permissao ao usuario para abrir hidraw, /dev/uinput,
desabilitam autosuspend USB do DualSense (evita desconexao intermitente)
e marcam o device para que o systemd --user abra a GUI no hotplug.
Requer sudo uma unica vez.

Arquivos instalados em /etc/udev/rules.d/:
  - 70-ps5-controller.rules             (permissao hidraw)
  - 71-uinput.rules                     (emulacao Xbox360 via uinput)
  - 72-ps5-controller-autosuspend.rules (power/control=on — ADR-013)
  - 73-ps5-controller-hotplug.rules     (SYSTEMD_USER_WANTS=GUI)

MSG
            read -r -p "[install] instalar udev rules agora? [Y/n] " resp
            resp="${resp:-Y}"
        else
            resp="Y"
        fi

        if [[ "${resp,,}" =~ ^y(es)?$ ]]; then
            if ! command -v sudo >/dev/null 2>&1; then
                log "aviso: sudo ausente; pule com --no-udev e instale manualmente"
            else
                bash "${ROOT_DIR}/scripts/install_udev.sh" || \
                    log "aviso: install_udev.sh falhou — rode manualmente mais tarde"
            fi
        else
            log "udev rules puladas a pedido. Rode ./scripts/install_udev.sh depois"
        fi
    fi
fi

###############################################################################
# 4. Ícone + .desktop + launcher desanexado
###############################################################################
log "[4/7] atalho de aplicativo (.desktop + icone + launcher)"
mkdir -p "${ICON_TARGET_DIR}"
cp -f "${ICON_SRC}" "${ICON_TARGET}"

mkdir -p "$(dirname "${DESKTOP_TARGET}")"
cat > "${DESKTOP_TARGET}" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Hefesto
GenericName=DualSense Controller
Comment=Daemon de gatilhos adaptativos para DualSense no Linux
Exec=${ROOT_DIR}/run.sh
Icon=${APP_ID}
Categories=Settings;HardwareSettings;
Terminal=false
StartupNotify=true
StartupWMClass=hefesto
DESKTOP

if command -v desktop-file-validate >/dev/null 2>&1; then
    desktop-file-validate "${DESKTOP_TARGET}" || \
        log "aviso: desktop-file-validate retornou warnings (não fatal)"
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -q -f "${HOME}/.local/share/icons/hicolor" || true
fi
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q "$(dirname "${DESKTOP_TARGET}")" || true
fi

mkdir -p "${BIN_DIR}"
cat > "${LAUNCHER}" <<LAUNCH
#!/usr/bin/env bash
# Launcher desanexado: roda em background, fecha handles do terminal.
# Assim "Sair" do tray é o único caminho para encerrar o processo.
setsid nohup "${ROOT_DIR}/run.sh" "\$@" </dev/null >/dev/null 2>&1 &
disown 2>/dev/null || true
LAUNCH
chmod +x "${LAUNCHER}"

###############################################################################
# 5. Symlink ~/.local/bin/hefesto (consumido pela unit systemd)
###############################################################################
log "[5/7] symlink ${BIN_DIR}/hefesto"
ln -sf "${VENV_DIR}/bin/hefesto" "${BIN_DIR}/hefesto"

###############################################################################
# 6. Unit systemd --user + start
###############################################################################
if [[ "${SKIP_SYSTEMD}" -eq 1 ]]; then
    log "[6/7] unit systemd pulada (--no-systemd)"
else
    log "[6/7] unit systemd --user (daemon em background)"
    # install-service cadeia: daemon-reload + systemctl --user enable hefesto.service
    if "${VENV_DIR}/bin/hefesto" daemon install-service >/dev/null 2>&1; then
        if systemctl --user restart hefesto.service >/dev/null 2>&1; then
            log "daemon ativo (systemctl --user status hefesto.service para detalhes)"
        else
            log "aviso: systemctl --user restart falhou — rode manualmente"
        fi
    else
        log "aviso: falha ao instalar unit systemd (sem systemd ou assets ausente)"
    fi
fi

###############################################################################
# 7. Unit user de hotplug-gui (abre a GUI ao plugar o DualSense)
###############################################################################
if [[ "${SKIP_HOTPLUG_GUI}" -eq 1 ]]; then
    log "[7/7] unit hotplug-gui pulada (--no-hotplug-gui)"
else
    log "[7/7] unit user hefesto-gui-hotplug.service (hotplug USB -> GUI)"
    readonly HOTPLUG_UNIT_SRC="${ROOT_DIR}/assets/hefesto-gui-hotplug.service"
    readonly USER_UNIT_DIR="${HOME}/.config/systemd/user"
    readonly HOTPLUG_UNIT_TARGET="${USER_UNIT_DIR}/hefesto-gui-hotplug.service"

    if [[ ! -f "${HOTPLUG_UNIT_SRC}" ]]; then
        log "aviso: ${HOTPLUG_UNIT_SRC} ausente — pule ou reinstale o repo"
    else
        mkdir -p "${USER_UNIT_DIR}"
        cp -f "${HOTPLUG_UNIT_SRC}" "${HOTPLUG_UNIT_TARGET}"
        if command -v systemctl >/dev/null 2>&1; then
            systemctl --user daemon-reload >/dev/null 2>&1 || \
                log "aviso: systemctl --user daemon-reload falhou"
            if systemctl --user enable hefesto-gui-hotplug.service >/dev/null 2>&1; then
                log "hotplug-gui habilitado (será disparado pelo udev no próximo plug USB)"
            else
                log "aviso: enable hefesto-gui-hotplug.service falhou — habilite manualmente"
            fi
        else
            log "aviso: systemctl ausente — unit copiada mas não habilitada"
        fi
    fi
fi

cat <<'FIM'

Instalação concluída.
  - Abra o painel: hefesto-gui (ou pelo menu de aplicativos).
  - Tray continua ativo; fechar a janela some para o tray.
  - Daemon em background via systemd --user (restart automático).
  - Plugar o DualSense via USB abre a GUI automaticamente (hotplug).
    Pule com --no-hotplug-gui. Desabilite depois via:
      systemctl --user disable hefesto-gui-hotplug.service
  - Se o DualSense desconectar intermitente, confirme que a regra
    72-ps5-controller-autosuspend.rules está em /etc/udev/rules.d/.

Para desinstalar: ./uninstall.sh
FIM

# "O que fazes com paz de espirito, isso sim dura." — Marco Aurelio
