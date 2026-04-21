#!/usr/bin/env bash
# install.sh - instala Hefesto GTK3 no ambiente do usuário.
# Cria .venv local, instala o pacote editavel, copia .desktop e icone,
# atualiza cache do menu de aplicativos. Sem sudo.

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

log() { printf '[install] %s\n' "$*"; }
die() { printf '[install] ERRO: %s\n' "$*" >&2; exit 1; }

require() {
    command -v "$1" >/dev/null 2>&1 || die "dependencia ausente: $1"
}

log "checando dependencias do sistema"
require python3
require pkg-config || true

if [[ ! -d "${VENV_DIR}" ]]; then
    log "criando venv em ${VENV_DIR}"
    python3 -m venv --system-site-packages "${VENV_DIR}"
fi

log "checando bindings GTK (python3-gi) no venv com --system-site-packages"
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

log "atualizando pip"
"${VENV_DIR}/bin/python" -m pip install --quiet --upgrade pip packaging

log "instalando Hefesto (editavel) + deps runtime"
"${VENV_DIR}/bin/pip" install --quiet -e "${ROOT_DIR}"

mkdir -p "${ICON_TARGET_DIR}"
log "copiando icone para ${ICON_TARGET}"
cp -f "${ICON_SRC}" "${ICON_TARGET}"

mkdir -p "$(dirname "${DESKTOP_TARGET}")"
log "gerando ${DESKTOP_TARGET}"
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
        log "aviso: desktop-file-validate retornou warnings (nao fatal)"
fi

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    log "atualizando cache de icones"
    gtk-update-icon-cache -q -f "${HOME}/.local/share/icons/hicolor" || true
fi

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q "$(dirname "${DESKTOP_TARGET}")" || true
fi

mkdir -p "${BIN_DIR}"
log "criando launcher em ${LAUNCHER}"
cat > "${LAUNCHER}" <<LAUNCH
#!/usr/bin/env bash
# Launcher desanexado: roda em background, fecha handles do terminal.
# Assim "Sair" do tray é o único caminho para encerrar o processo.
setsid nohup "${ROOT_DIR}/run.sh" "\$@" </dev/null >/dev/null 2>&1 &
disown 2>/dev/null || true
LAUNCH
chmod +x "${LAUNCHER}"

log "criando symlink ~/.local/bin/hefesto (consumido pela unit systemd)"
ln -sf "${VENV_DIR}/bin/hefesto" "${BIN_DIR}/hefesto"

log "instalando unit systemd --user (daemon em background)"
if "${VENV_DIR}/bin/hefesto" daemon install-service >/dev/null 2>&1; then
    log "unit instalada; iniciando via systemctl --user"
    if systemctl --user start hefesto.service >/dev/null 2>&1; then
        log "daemon iniciado"
    else
        log "aviso: falha ao iniciar hefesto.service (systemctl --user status hefesto.service)"
    fi
else
    log "aviso: falha ao instalar unit systemd (sem systemd ou assets/ ausente)"
fi

log "OK. Abra o painel: hefesto-gui (ou pelo menu de aplicativos)"
log "O daemon segue rodando em background; feche a janela e use o tray."
