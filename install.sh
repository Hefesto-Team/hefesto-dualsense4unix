#!/usr/bin/env bash
# install.sh — instala Hefesto - Dualsense4Unix completo no ambiente do usuário.
#
# Flags:
#   --no-udev             pula udev rules (sudo) — útil em CI.
#   --yes, -y             responde sim a todos os prompts sudo.
#   --no-systemd          pula a cópia da unit do daemon.
#   --no-hotplug-gui      pula a cópia da unit hotplug-gui.
#   --enable-autostart    habilita auto-start do daemon no boot (pula prompt).
#   --enable-hotplug-gui  habilita GUI auto-abrir ao plugar DualSense (pula prompt).
#
# Default: unit do daemon é COPIADA mas NÃO habilitada. Hotplug-GUI idem.
# Opt-in via prompt interativo ou flags acima (ver BUG-MULTI-INSTANCE-01).
#
# Reexecutável (idempotente).

set -euo pipefail

readonly ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly VENV_DIR="${ROOT_DIR}/.venv"
readonly APP_ID="hefesto-dualsense4unix"
readonly ICON_SRC="${ROOT_DIR}/assets/appimage/Hefesto-Dualsense4Unix.png"
readonly DESKTOP_TARGET="${HOME}/.local/share/applications/${APP_ID}.desktop"
readonly ICON_TARGET_DIR="${HOME}/.local/share/icons/hicolor/256x256/apps"
readonly ICON_TARGET="${ICON_TARGET_DIR}/${APP_ID}.png"
readonly BIN_DIR="${HOME}/.local/bin"
readonly LAUNCHER="${BIN_DIR}/hefesto-dualsense4unix-gui"

SKIP_UDEV=0
SKIP_SYSTEMD=0
SKIP_HOTPLUG_GUI=0
ENABLE_AUTOSTART=0
ENABLE_HOTPLUG_GUI=0
AUTO_YES=0

for arg in "$@"; do
    case "$arg" in
        --no-udev)            SKIP_UDEV=1 ;;
        --no-systemd)         SKIP_SYSTEMD=1 ;;
        --no-hotplug-gui)     SKIP_HOTPLUG_GUI=1 ;;
        --enable-autostart)   ENABLE_AUTOSTART=1 ;;
        --enable-hotplug-gui) ENABLE_HOTPLUG_GUI=1 ;;
        --yes|-y)             AUTO_YES=1 ;;
        -h|--help)
            sed -n '2,15p' "${BASH_SOURCE[0]}" | sed 's/^# //; s/^#//'
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
    # ask_yn "pergunta" auto_yes_var [default=y] → seta $REPLY como "y" ou "n"
    local prompt="$1" auto="$2" default="${3:-y}"
    if [[ "$auto" -eq 1 ]]; then
        REPLY="$default"; return
    fi
    local indicator
    if [[ "$default" == "y" ]]; then indicator="[Y/n]"; else indicator="[y/N]"; fi
    read -r -n 1 -p "      $prompt $indicator " REPLY
    echo
    REPLY="${REPLY:-$default}"
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
step "1/9" "verificando dependências do sistema"
require python3
ok

# Limpeza de caches Python e build dirs.
# Resíduos de instalação anterior (especialmente após module-rename ou
# upgrade major) podem causar imports stale ou metadata divergente.
# Always clean caches; venv é tratado dentro do passo 2/7 conforme o
# Python que criou.
for cache in .pytest_cache .ruff_cache .mypy_cache flatpak-build-dir .flatpak-builder dist build; do
    if [[ -d "${ROOT_DIR}/${cache}" ]]; then
        rm -rf "${ROOT_DIR}/${cache}"
    fi
done
find "${ROOT_DIR}" -type d -name "__pycache__" \
    -not -path "*/\.git/*" \
    -not -path "*/\.venv/*" \
    -exec rm -rf {} + 2>/dev/null || true
find "${ROOT_DIR}" -type f -name "*.pyc" \
    -not -path "*/\.git/*" \
    -not -path "*/\.venv/*" \
    -delete 2>/dev/null || true

# ---------------------------------------------------------------------------
# 2. venv + GTK3 + pacote Python
# ---------------------------------------------------------------------------
step "2/9" "preparando ambiente Python"

# Preferir /usr/bin/python3 (Python do apt) para que --system-site-packages
# inclua gi/PyGObject. pyenv, se ativo, aponta python3 para uma versão
# isolada cujos site-packages não contêm pacotes apt.
_VENV_PYTHON="python3"
if [[ -x /usr/bin/python3 ]]; then
    _VENV_PYTHON="/usr/bin/python3"
fi

# Se venv existe mas foi criado com Python não-sistema (pyenv), recriar.
if [[ -d "${VENV_DIR}" ]]; then
    _venv_home=$(grep "^home = " "${VENV_DIR}/pyvenv.cfg" 2>/dev/null | awk '{print $3}')
    if [[ -n "${_venv_home}" ]] && [[ "${_venv_home}" != "/usr/bin" ]] && [[ -x /usr/bin/python3 ]]; then
        printf '      venv criado com Python não-sistema (%s) — recriando...\n' "${_venv_home}"
        rm -rf "${VENV_DIR}"
    fi
fi

if [[ ! -d "${VENV_DIR}" ]]; then
    printf '      criando venv...\n'
    "${_VENV_PYTHON}" -m venv --system-site-packages "${VENV_DIR}" 2>/dev/null
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
step "3/9" "udev rules (hidraw + uinput + autosuspend + hotplug)"

if [[ "${SKIP_UDEV}" -eq 1 ]]; then
    printf '      pulado (--no-udev)\n'
else
    need_udev=1
    if [[ -f /etc/udev/rules.d/70-ps5-controller.rules ]] \
       && [[ -f /etc/udev/rules.d/71-uinput.rules ]] \
       && [[ -f /etc/udev/rules.d/72-ps5-controller-autosuspend.rules ]] \
       && [[ -f /etc/udev/rules.d/73-ps5-controller-hotplug.rules ]] \
       && [[ -f /etc/udev/rules.d/74-ps5-controller-hotplug-bt.rules ]]; then
        printf '      já instaladas\n'
        need_udev=0
    fi

    if [[ "${need_udev}" -eq 1 ]]; then
        printf '\n'
        printf '      Cinco regras serão copiadas para /etc/udev/rules.d/ (requer sudo):\n'
        printf '        70-ps5-controller.rules                permissão hidraw (USB e BT)\n'
        printf '        71-uinput.rules                        emulação Xbox360 via uinput\n'
        printf '        72-ps5-controller-autosuspend.rules    evita desconexão intermitente USB\n'
        printf '        73-ps5-controller-hotplug.rules        abre a GUI ao plugar o controle (USB)\n'
        printf '        74-ps5-controller-hotplug-bt.rules     abre a GUI ao parear o controle (BT)\n\n'

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
step "4/9" "atalho de aplicativo e launcher"

mkdir -p "${ICON_TARGET_DIR}"
cp -f "${ICON_SRC}" "${ICON_TARGET}"
mkdir -p "$(dirname "${DESKTOP_TARGET}")"

cat > "${DESKTOP_TARGET}" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Hefesto - Dualsense4Unix
GenericName=DualSense Controller
Comment=Daemon de gatilhos adaptativos para DualSense no Linux
Exec=${ROOT_DIR}/run.sh
Icon=${APP_ID}
Categories=Settings;HardwareSettings;
Terminal=false
StartupNotify=true
StartupWMClass=Hefesto-Dualsense4Unix
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
# 4b. Glyphs SVG dos botoes do DualSense
# ---------------------------------------------------------------------------
readonly GLYPHS_SRC="${ROOT_DIR}/assets/glyphs"
readonly GLYPHS_TARGET="${HOME}/.local/share/hefesto-dualsense4unix/glyphs"

if [[ -d "${GLYPHS_SRC}" ]]; then
    mkdir -p "${GLYPHS_TARGET}"
    cp -f "${GLYPHS_SRC}"/*.svg "${GLYPHS_TARGET}/"
fi

# ---------------------------------------------------------------------------
# 4c. Perfis default (primeira instalação copia; reinstalação preserva)
# ---------------------------------------------------------------------------
if [[ -f "${ROOT_DIR}/scripts/install_profiles.sh" ]]; then
    bash "${ROOT_DIR}/scripts/install_profiles.sh" "${ROOT_DIR}"
fi

# ---------------------------------------------------------------------------
# 5. Symlink ~/.local/bin/hefesto-dualsense4unix
# ---------------------------------------------------------------------------
step "5/9" "symlink ${BIN_DIR}/hefesto-dualsense4unix"
ln -sf "${VENV_DIR}/bin/hefesto-dualsense4unix" "${BIN_DIR}/hefesto-dualsense4unix"
ok

# ---------------------------------------------------------------------------
# 6. Daemon systemd --user (copia sempre; auto-start é opt-in)
# ---------------------------------------------------------------------------
step "6/9" "daemon systemd --user"

if [[ "${SKIP_SYSTEMD}" -eq 1 ]]; then
    printf '      pulado (--no-systemd)\n'
else
    # Decide se habilita auto-start ANTES de chamar o CLI.
    enable_daemon=0
    if [[ "${ENABLE_AUTOSTART}" -eq 1 ]]; then
        enable_daemon=1
    else
        ask_yn "habilitar auto-start do daemon no boot?" "${AUTO_YES}" "n"
        [[ "${REPLY,,}" =~ ^y ]] && enable_daemon=1
    fi

    cli_args=("install-service")
    [[ "${enable_daemon}" -eq 1 ]] && cli_args+=("--enable")

    if "${VENV_DIR}/bin/hefesto-dualsense4unix" daemon "${cli_args[@]}" >/dev/null 2>&1; then
        if [[ "${enable_daemon}" -eq 1 ]]; then
            printf '      unit instalada + auto-start habilitado\n'
        else
            printf '      unit instalada (auto-start desativado — subir só quando abrir a GUI)\n'
        fi
    else
        warn "falha ao instalar unit (sem systemd ou assets ausente)"
    fi
fi

# ---------------------------------------------------------------------------
# 7. Hotplug-gui unit (opt-in, default NÃO)
# ---------------------------------------------------------------------------
step "7/9" "hotplug USB → abre a GUI automaticamente"

if [[ "${SKIP_HOTPLUG_GUI}" -eq 1 ]]; then
    printf '      pulado (--no-hotplug-gui)\n'
else
    enable_hotplug=0
    if [[ "${ENABLE_HOTPLUG_GUI}" -eq 1 ]]; then
        enable_hotplug=1
    else
        ask_yn "abrir GUI automaticamente ao plugar DualSense?" "${AUTO_YES}" "n"
        [[ "${REPLY,,}" =~ ^y ]] && enable_hotplug=1
    fi

    if [[ "${enable_hotplug}" -eq 0 ]]; then
        printf '      desativado (abrir GUI manualmente pelo menu de aplicativos)\n'
    else
        readonly HOTPLUG_UNIT_SRC="${ROOT_DIR}/assets/hefesto-dualsense4unix-gui-hotplug.service"
        readonly USER_UNIT_DIR="${HOME}/.config/systemd/user"
        readonly HOTPLUG_UNIT_TARGET="${USER_UNIT_DIR}/hefesto-dualsense4unix-gui-hotplug.service"

        if [[ ! -f "${HOTPLUG_UNIT_SRC}" ]]; then
            warn "${HOTPLUG_UNIT_SRC} ausente — reinstale o repo"
        else
            mkdir -p "${USER_UNIT_DIR}"
            cp -f "${HOTPLUG_UNIT_SRC}" "${HOTPLUG_UNIT_TARGET}"
            if command -v systemctl >/dev/null 2>&1; then
                systemctl --user daemon-reload >/dev/null 2>&1 || true
                if systemctl --user enable hefesto-dualsense4unix-gui-hotplug.service >/dev/null 2>&1; then
                    printf '      habilitado\n'
                else
                    warn "enable falhou — habilite manualmente"
                fi
            else
                warn "systemctl ausente — unit copiada mas não habilitada"
            fi
        fi
    fi
fi

# ---------------------------------------------------------------------------
# 8. Extension AppIndicator no GNOME (necessária para o ícone de bandeja)
# ---------------------------------------------------------------------------
step "8/9" "GNOME: extension AppIndicator (tray icon)"

_desktop="${XDG_CURRENT_DESKTOP:-}"
if [[ -z "${_desktop}" ]]; then
    printf '      ambiente headless (sem XDG_CURRENT_DESKTOP) — pulado\n'
elif [[ "${_desktop,,}" != *gnome* ]]; then
    printf '      DE %s renderiza Ayatana nativamente — sem ação\n' "${_desktop}"
elif ! command -v gnome-extensions >/dev/null 2>&1; then
    warn "gnome-extensions CLI ausente — habilite manualmente a extension AppIndicator depois"
else
    _ext_id="ubuntu-appindicators@ubuntu.com"
    if gnome-extensions list --enabled 2>/dev/null | grep -qx "${_ext_id}"; then
        printf '      já habilitada\n'
    elif ! gnome-extensions list 2>/dev/null | grep -qx "${_ext_id}"; then
        warn "extension ${_ext_id} não instalada — instale via GNOME Extensions (https://extensions.gnome.org)"
    else
        printf '      extension %s está instalada mas desabilitada\n' "${_ext_id}"
        printf '      sem ela o ícone do Hefesto não aparece na barra superior do GNOME\n'
        ask_yn "habilitar agora?" "${AUTO_YES}"
        if [[ "${REPLY,,}" =~ ^y ]]; then
            if gnome-extensions enable "${_ext_id}" 2>/dev/null; then
                printf '      habilitada (pode exigir log out/in se for a primeira ativação)\n'
            else
                warn "falha ao habilitar — execute 'gnome-extensions enable ${_ext_id}' manualmente"
            fi
        else
            printf '      pulado a pedido — habilite depois com: gnome-extensions enable %s\n' "${_ext_id}"
        fi
    fi
fi

# ---------------------------------------------------------------------------
# 9. dualsensectl (opcional — aba Firmware)
# ---------------------------------------------------------------------------
step "9/9" "dualsensectl (opcional — aba Firmware)"

if command -v dualsensectl >/dev/null 2>&1; then
    printf '      já presente em %s\n' "$(command -v dualsensectl)"
elif ! command -v flatpak >/dev/null 2>&1; then
    printf '      ausente — para habilitar a aba Firmware, instale manualmente:\n'
    printf '        https://github.com/nowrep/dualsensectl  (build via cmake)\n'
    printf '      a aba Firmware ficará desabilitada até instalar (não bloqueia uso geral)\n'
elif ! { flatpak --user remotes 2>/dev/null; flatpak remotes 2>/dev/null; } \
        | awk '{print $1}' | grep -qx "flathub"; then
    printf '      flatpak presente mas remote flathub ausente. Configure com:\n'
    printf '        flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo\n'
    printf '      e rode novamente este install.sh\n'
else
    printf '      dualsensectl ausente — necessário para a aba Firmware da GUI (opcional)\n'
    printf '      Flathub: com.github.nowrep.dualsensectl\n'
    ask_yn "instalar agora via flatpak?" "${AUTO_YES}" "n"
    if [[ "${REPLY,,}" =~ ^y ]]; then
        if flatpak install --user -y flathub com.github.nowrep.dualsensectl >/dev/null 2>&1; then
            printf '      instalado via flatpak\n'
            printf '      lembrete: para que a GUI encontre o binário no PATH, exponha um wrapper:\n'
            printf '        echo -e "#!/bin/sh\\nflatpak run com.github.nowrep.dualsensectl \\"\\$@\\"" \\\n'
            printf '          | sudo tee /usr/local/bin/dualsensectl >/dev/null && sudo chmod +x /usr/local/bin/dualsensectl\n'
        else
            warn "flatpak install falhou — instale manualmente: flatpak install flathub com.github.nowrep.dualsensectl"
        fi
    else
        printf '      pulado a pedido — aba Firmware ficará desabilitada\n'
    fi
fi

# ---------------------------------------------------------------------------
# Pronto
# ---------------------------------------------------------------------------
printf '\n'
printf '─────────────────────────────────────────\n'
printf ' Hefesto - Dualsense4Unix instalado\n'
printf '─────────────────────────────────────────\n'
printf ' Abrir:       hefesto-dualsense4unix-gui\n'
printf ' Desinstalar: ./uninstall.sh\n'
printf '─────────────────────────────────────────\n'
printf '\n'

# "O que fazes com paz de espírito, isso sim dura." — Marco Aurélio
