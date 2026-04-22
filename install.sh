#!/usr/bin/env bash
# install.sh — instala Hefesto completo no ambiente do usuário.
#
# Flags:
#   --no-udev        pula udev rules (sudo) — útil em CI.
#   --yes, -y        responde sim a todos os prompts sudo.
#   --no-systemd     pula install + start da unit do daemon.
#   --no-hotplug-gui pula a unit que abre a GUI ao plugar o controle.
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
            sed -n '2,10p' "${BASH_SOURCE[0]}" | sed 's/^# //; s/^#//'
            exit 0
            ;;
        *) printf 'aviso: argumento desconhecido: %s\n' "$arg" ;;
    esac
done

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

step()  { printf '\n[%s] %s\n' "$1" "$2"; }
ok()    { printf '      ok\n'; }
warn()  { printf '      aviso: %s\n' "$*"; }
die()   { printf '\nERRO: %s\n' "$*" >&2; exit 1; }

ask_yn() {
    # ask_yn "pergunta" auto_yes_var → seta $REPLY como "y" ou "n"
    local prompt="$1" auto="$2"
    if [[ "$auto" -eq 1 ]]; then
        REPLY="y"; return
    fi
    read -r -n 1 -p "      $prompt [Y/n] " REPLY
    echo
    REPLY="${REPLY:-y}"
}

run_apt() {
    # Roda apt-get quieto; só mostra saída se falhar.
    local _tmp
    _tmp="$(mktemp)"
    if ! sudo apt-get install -y -qq "$@" > "$_tmp" 2>&1; then
        cat "$_tmp" >&2
        rm -f "$_tmp"
        return 1
    fi
    rm -f "$_tmp"
}

require() { command -v "$1" >/dev/null 2>&1 || die "dependência ausente: $1"; }

# ---------------------------------------------------------------------------
# 1. Verificar Python
# ---------------------------------------------------------------------------
step "1/7" "verificando dependências do sistema"
require python3
ok

# ---------------------------------------------------------------------------
# 2. venv + GTK3 + pacote Python
# ---------------------------------------------------------------------------
step "2/7" "preparando ambiente Python"

if [[ ! -d "${VENV_DIR}" ]]; then
    printf '      criando venv...\n'
    python3 -m venv --system-site-packages "${VENV_DIR}" 2>/dev/null
fi

if ! "${VENV_DIR}/bin/python" -c \
        "import gi; gi.require_version('Gtk','3.0')" >/dev/null 2>&1; then

    printf '\n      Bindings GTK3 não encontrados — obrigatórios para a GUI.\n'
    printf '      Pacotes: python3-gi  python3-gi-cairo  gir1.2-gtk-3.0\n'
    printf '               gir1.2-ayatanaappindicator3-0.1  libgirepository1.0-dev\n'
    printf '               libcairo2-dev  desktop-file-utils  imagemagick\n\n'

    ask_yn "instalar agora com sudo?" "${AUTO_YES}"
    if [[ "${REPLY,,}" =~ ^y ]]; then
        printf '      instalando...\n'
        run_apt \
            python3-gi python3-gi-cairo gir1.2-gtk-3.0 \
            gir1.2-ayatanaappindicator3-0.1 libgirepository1.0-dev \
            libcairo2-dev desktop-file-utils imagemagick \
            || die "falha ao instalar GTK3 — verifique a conexão e tente novamente"
        printf '      GTK3 instalado\n'
    else
        die "GTK3 obrigatório. Instale manualmente e reexecute ./install.sh"
    fi
fi

printf '      instalando pacote Python...\n'
"${VENV_DIR}/bin/python" -m pip install \
    --quiet --disable-pip-version-check --upgrade pip packaging 2>/dev/null
"${VENV_DIR}/bin/pip" install \
    --quiet --disable-pip-version-check -e "${ROOT_DIR}[emulation]" 2>/dev/null
ok

# ---------------------------------------------------------------------------
# 3. udev rules (requer sudo)
# ---------------------------------------------------------------------------
step "3/7" "udev rules (hidraw + uinput + autosuspend + hotplug)"

if [[ "${SKIP_UDEV}" -eq 1 ]]; then
    printf '      pulado (--no-udev)\n'
else
    need_udev=1
    if [[ -f /etc/udev/rules.d/70-ps5-controller.rules ]] \
       && [[ -f /etc/udev/rules.d/71-uinput.rules ]] \
       && [[ -f /etc/udev/rules.d/72-ps5-controller-autosuspend.rules ]] \
       && [[ -f /etc/udev/rules.d/73-ps5-controller-hotplug.rules ]]; then
        printf '      já instaladas\n'
        need_udev=0
    fi

    if [[ "${need_udev}" -eq 1 ]]; then
        printf '\n'
        printf '      Quatro regras serão copiadas para /etc/udev/rules.d/ (requer sudo):\n'
        printf '        70-ps5-controller.rules             permissão hidraw\n'
        printf '        71-uinput.rules                     emulação Xbox360 via uinput\n'
        printf '        72-ps5-controller-autosuspend.rules evita desconexão intermitente\n'
        printf '        73-ps5-controller-hotplug.rules     abre a GUI ao plugar o controle\n\n'

        ask_yn "instalar agora com sudo?" "${AUTO_YES}"
        if [[ "${REPLY,,}" =~ ^y ]]; then
            if ! command -v sudo >/dev/null 2>&1; then
                warn "sudo ausente — instale com --no-udev e rode scripts/install_udev.sh depois"
            else
                printf '      instalando...\n'
                bash "${ROOT_DIR}/scripts/install_udev.sh" >/dev/null \
                    || warn "install_udev.sh falhou — rode manualmente depois"
                ok
            fi
        else
            printf '      pulado a pedido — rode ./scripts/install_udev.sh depois\n'
        fi
    fi
fi

# ---------------------------------------------------------------------------
# 4. Ícone + .desktop + launcher
# ---------------------------------------------------------------------------
step "4/7" "atalho de aplicativo e launcher"

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

command -v desktop-file-validate >/dev/null 2>&1 \
    && desktop-file-validate "${DESKTOP_TARGET}" >/dev/null 2>&1 || true
command -v gtk-update-icon-cache >/dev/null 2>&1 \
    && gtk-update-icon-cache -q -f "${HOME}/.local/share/icons/hicolor" 2>/dev/null || true
command -v update-desktop-database >/dev/null 2>&1 \
    && update-desktop-database -q "$(dirname "${DESKTOP_TARGET}")" 2>/dev/null || true

mkdir -p "${BIN_DIR}"
cat > "${LAUNCHER}" <<LAUNCH
#!/usr/bin/env bash
setsid nohup "${ROOT_DIR}/run.sh" "\$@" </dev/null >/dev/null 2>&1 &
disown 2>/dev/null || true
LAUNCH
chmod +x "${LAUNCHER}"
ok

# ---------------------------------------------------------------------------
# 5. Symlink ~/.local/bin/hefesto
# ---------------------------------------------------------------------------
step "5/7" "symlink ${BIN_DIR}/hefesto"
ln -sf "${VENV_DIR}/bin/hefesto" "${BIN_DIR}/hefesto"
ok

# ---------------------------------------------------------------------------
# 6. Daemon systemd --user
# ---------------------------------------------------------------------------
step "6/7" "daemon systemd --user"

if [[ "${SKIP_SYSTEMD}" -eq 1 ]]; then
    printf '      pulado (--no-systemd)\n'
else
    if "${VENV_DIR}/bin/hefesto" daemon install-service >/dev/null 2>&1; then
        if systemctl --user restart hefesto.service >/dev/null 2>&1; then
            printf '      daemon ativo\n'
        else
            warn "restart falhou — rode: systemctl --user start hefesto.service"
        fi
    else
        warn "falha ao instalar unit (sem systemd ou assets ausente)"
    fi
fi

# ---------------------------------------------------------------------------
# 7. Hotplug-gui unit
# ---------------------------------------------------------------------------
step "7/7" "hotplug USB → abre a GUI automaticamente"

if [[ "${SKIP_HOTPLUG_GUI}" -eq 1 ]]; then
    printf '      pulado (--no-hotplug-gui)\n'
else
    readonly HOTPLUG_UNIT_SRC="${ROOT_DIR}/assets/hefesto-gui-hotplug.service"
    readonly USER_UNIT_DIR="${HOME}/.config/systemd/user"
    readonly HOTPLUG_UNIT_TARGET="${USER_UNIT_DIR}/hefesto-gui-hotplug.service"

    if [[ ! -f "${HOTPLUG_UNIT_SRC}" ]]; then
        warn "${HOTPLUG_UNIT_SRC} ausente — reinstale o repo"
    else
        mkdir -p "${USER_UNIT_DIR}"
        cp -f "${HOTPLUG_UNIT_SRC}" "${HOTPLUG_UNIT_TARGET}"
        if command -v systemctl >/dev/null 2>&1; then
            systemctl --user daemon-reload >/dev/null 2>&1 || true
            if systemctl --user enable hefesto-gui-hotplug.service >/dev/null 2>&1; then
                printf '      habilitado\n'
            else
                warn "enable falhou — habilite manualmente"
            fi
        else
            warn "systemctl ausente — unit copiada mas não habilitada"
        fi
    fi
fi

# ---------------------------------------------------------------------------
# Pronto
# ---------------------------------------------------------------------------
printf '\n'
printf '─────────────────────────────────────────\n'
printf ' Hefesto instalado\n'
printf '─────────────────────────────────────────\n'
printf ' Abrir:       hefesto-gui\n'
printf ' Desinstalar: ./uninstall.sh\n'
printf '─────────────────────────────────────────\n'
printf '\n'

# "O que fazes com paz de espírito, isso sim dura." — Marco Aurélio
