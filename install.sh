#!/usr/bin/env bash
# install.sh — instala Hefesto - Dualsense4Unix completo no ambiente do usuário.
#
# Flags:
#   --no-udev             pula udev rules (sudo) — útil em CI sem hardware.
#                         POR DEFAULT, as 5 regras + modules-load uinput são
#                         aplicadas automaticamente (re-cópia é idempotente).
#                         Se Flatpak Hefesto está instalado, também propaga.
#   --yes, -y             responde sim a todos os prompts (autostart, hotplug,
#                         COSMIC XWayland, AppIndicator extension, etc).
#   --no-systemd          pula a cópia da unit do daemon.
#   --no-hotplug-gui      pula a cópia da unit hotplug-gui.
#   --enable-autostart    habilita auto-start do daemon no boot (pula prompt).
#   --enable-hotplug-gui  habilita GUI auto-abrir ao plugar DualSense (pula prompt).
#   --force-xwayland      grava GDK_BACKEND=x11 no .desktop (recomendado
#                         para COSMIC enquanto xdg-desktop-portal-cosmic
#                         não implementa GetActiveWindow). Ativada
#                         automaticamente se XDG_CURRENT_DESKTOP casa
#                         COSMIC e o usuário confirma via prompt.
#
# Default: unit do daemon é COPIADA mas NÃO habilitada. Hotplug-GUI idem.
# udev rules SÃO aplicadas (incondicional desde v3.3.1 — sem elas o controle
# não funciona em nenhum formato).
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
FORCE_XWAYLAND=0
AUTO_YES=0

for arg in "$@"; do
    case "$arg" in
        --no-udev)            SKIP_UDEV=1 ;;
        --no-systemd)         SKIP_SYSTEMD=1 ;;
        --no-hotplug-gui)     SKIP_HOTPLUG_GUI=1 ;;
        --enable-autostart)   ENABLE_AUTOSTART=1 ;;
        --enable-hotplug-gui) ENABLE_HOTPLUG_GUI=1 ;;
        --force-xwayland)     FORCE_XWAYLAND=1 ;;
        --yes|-y)             AUTO_YES=1 ;;
        -h|--help)
            sed -n '2,20p' "${BASH_SOURCE[0]}" | sed 's/^# //; s/^#//'
            exit 0
            ;;
        *) printf 'aviso: argumento desconhecido: %s\n' "$arg" ;;
    esac
done

# Detecta COSMIC: XDG_CURRENT_DESKTOP contém "COSMIC" (case-insensitive).
# Se detectado e usuário não passou --force-xwayland explícito, pergunta
# interativamente se quer ativar (opt-in). O fallback XWayland faz a GUI
# rodar sob XlibBackend em vez de depender do portal Wayland — até o
# xdg-desktop-portal-cosmic implementar
# org.freedesktop.portal.Window::GetActiveWindow.
DESKTOP_IS_COSMIC=0
if [[ "${XDG_CURRENT_DESKTOP:-}${XDG_SESSION_DESKTOP:-}" == *[Cc][Oo][Ss][Mm][Ii][Cc]* ]]; then
    DESKTOP_IS_COSMIC=1
fi

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

# Extras instalados sempre: emulation (uinput) + cosmic (jeepney para portal Wayland).
# `jeepney` é puro Python, sem deps nativas; vale habilitar mesmo em DE não-Wayland
# porque o WaylandPortalBackend faz `try: import jeepney` e ignora se ausente — mas
# se está instalado o cascade portal→wlrctl funciona em qualquer compositor que
# implemente o portal.
"${VENV_DIR}/bin/pip" install \
    --quiet --disable-pip-version-check -e "${ROOT_DIR}[emulation,cosmic]" 2>/dev/null
ok

# ---------------------------------------------------------------------------
# 3. udev rules — SEMPRE aplicado por default (requer sudo)
# ---------------------------------------------------------------------------
# v3.3.1: udev agora é incondicional (era opt-in via prompt). Motivação: sem
# essas regras o controle não funciona, e o prompt levava usuários a "pular"
# sem entender que depois nada ia funcionar. Re-cópia é idempotente e o
# reload/trigger é barato (<100 ms). Para CI sem sudo, use `--no-udev`.
step "3/9" "udev rules (hidraw + uinput + autosuspend + hotplug)"

if [[ "${SKIP_UDEV}" -eq 1 ]]; then
    printf '      pulado (--no-udev) — IMPORTANTE: o controle precisa das regras\n'
    printf '      para funcionar. Rode depois: sudo bash scripts/install_udev.sh\n'
elif ! command -v sudo >/dev/null 2>&1; then
    warn "sudo ausente — pulando (rode scripts/install_udev.sh manualmente como root)"
else
    printf '      copiando 5 regras + modules-load uinput (sudo)\n'
    printf '        70-ps5-controller.rules                permissão hidraw (USB e BT)\n'
    printf '        71-uinput.rules                        emulação Xbox360 via uinput\n'
    printf '        72-ps5-controller-autosuspend.rules    evita desconexão intermitente USB\n'
    printf '        73-ps5-controller-hotplug.rules        hotplug-GUI ao plugar (USB)\n'
    printf '        74-ps5-controller-hotplug-bt.rules     hotplug-GUI ao parear (BT)\n'

    if bash "${ROOT_DIR}/scripts/install_udev.sh" >/dev/null 2>&1; then
        printf '      regras aplicadas + udev recarregado + uinput carregado\n'
    else
        warn "install_udev.sh falhou — rode manualmente: sudo bash scripts/install_udev.sh"
    fi

    # v3.3.1: se Flatpak Hefesto está instalado, propagar as regras pelo
    # caminho oficial do bundle também (defensive — install_udev.sh já cobriu
    # o host, mas o usuário pode esperar simetria explícita "tudo pro
    # Flatpak". A chamada é no-op se as regras já estão lá).
    if command -v flatpak >/dev/null 2>&1 \
       && flatpak info br.andrefarias.Hefesto >/dev/null 2>&1; then
        printf '      Flatpak Hefesto detectado — sincronizando regras via bundle\n'
        flatpak run --command=install-host-udev.sh br.andrefarias.Hefesto \
            >/dev/null 2>&1 \
            || warn "flatpak install-host-udev.sh falhou (regras já vieram via install_udev.sh)"
    fi
fi

# ---------------------------------------------------------------------------
# 4. Ícone + .desktop + launcher
# ---------------------------------------------------------------------------
step "4/9" "atalho de aplicativo e launcher"

# FEAT-ICON-MULTI-RES-01: gera o icone em todas resolucoes do hicolor +
# SVG escalavel + pixmap legacy. Antes so existia 256x256 PNG, que fazia
# o COSMIC App Library / GNOME Activities renderizar fallback generico
# para sizes nao-256 (ex: chip 32x32 do menu apps).
#
# Estrategia: prefere rsvg-convert (renderiza nitido do vetor original);
# fallback para ImageMagick convert (resample do PNG 256 — qualidade
# inferior em sizes pequenos mas funciona). Se nenhum disponivel, mantem
# so o PNG 256 (comportamento legado).
ICON_SVG_SRC="${ROOT_DIR}/assets/appimage/Hefesto-Dualsense4Unix.svg"
ICON_HICOLOR_BASE="${HOME}/.local/share/icons/hicolor"
ICON_SIZES="16 22 24 32 48 64 96 128 192 256 512"

# Sempre garante o 256x256 PNG (path legacy)
mkdir -p "${ICON_TARGET_DIR}"
cp -f "${ICON_SRC}" "${ICON_TARGET}"
mkdir -p "$(dirname "${DESKTOP_TARGET}")"

# Multi-res se rsvg-convert disponivel
if [[ -f "${ICON_SVG_SRC}" ]] && command -v rsvg-convert >/dev/null 2>&1; then
    printf '      gerando icone multi-res (rsvg-convert)\n'
    for size in ${ICON_SIZES}; do
        target_dir="${ICON_HICOLOR_BASE}/${size}x${size}/apps"
        mkdir -p "${target_dir}"
        rsvg-convert -w "${size}" -h "${size}" "${ICON_SVG_SRC}" \
            -o "${target_dir}/${APP_ID}.png" 2>/dev/null || true
    done
    # SVG escalavel — moderno (COSMIC/GNOME 47+ preferem)
    mkdir -p "${ICON_HICOLOR_BASE}/scalable/apps"
    cp -f "${ICON_SVG_SRC}" "${ICON_HICOLOR_BASE}/scalable/apps/${APP_ID}.svg"
    # Pixmap legacy fallback (DEs antigos)
    mkdir -p "${HOME}/.local/share/pixmaps"
    cp -f "${ICON_HICOLOR_BASE}/256x256/apps/${APP_ID}.png" \
        "${HOME}/.local/share/pixmaps/${APP_ID}.png"
elif command -v convert >/dev/null 2>&1; then
    printf '      gerando icone multi-res (ImageMagick — instale librsvg2-bin para qualidade superior)\n'
    for size in ${ICON_SIZES}; do
        [[ "${size}" == "256" ]] && continue  # ja copiado acima
        target_dir="${ICON_HICOLOR_BASE}/${size}x${size}/apps"
        mkdir -p "${target_dir}"
        convert "${ICON_SRC}" -resize "${size}x${size}" \
            "${target_dir}/${APP_ID}.png" 2>/dev/null || true
    done
    mkdir -p "${HOME}/.local/share/pixmaps"
    cp -f "${ICON_TARGET}" "${HOME}/.local/share/pixmaps/${APP_ID}.png"
else
    printf '      aviso: rsvg-convert nem convert disponivel — so 256x256 PNG\n'
    printf '             instale: sudo apt install librsvg2-bin\n'
fi

# Detecção COSMIC → dois caminhos complementares para autoswitch funcionar:
#
#   1. wlrctl (recomendado): cobre TODOS os apps via protocolo
#      wlr-foreign-toplevel-management. WlrctlBackend detecta automaticamente
#      se o binário está no PATH (window_backends/wlr_toplevel.py).
#
#   2. XWayland (fallback): força GTK a rodar sob XWayland via GDK_BACKEND=x11.
#      XlibBackend passa a ver janelas XWayland (Steam, Proton).
#      Limitação: apps Wayland nativos ficam invisíveis.
#
# Os dois são compatíveis — o cascade Wayland em window_detect.py tenta
# portal → wlrctl → None, e XWayland roda paralelo via XlibBackend.
#
# Auto-aplicação: sob --yes/-y, instala wlrctl (se disponível no apt) + ativa
# XWayland (apenas se --force-xwayland também foi passado, ou se aceitar prompt).
if [[ "${DESKTOP_IS_COSMIC}" -eq 1 ]]; then
    printf '\n'
    printf '      COSMIC detectado (XDG_CURRENT_DESKTOP=%s).\n' \
        "${XDG_CURRENT_DESKTOP:-$XDG_SESSION_DESKTOP}"
    printf '      Enquanto o xdg-desktop-portal-cosmic não implementa o\n'
    printf '      método org.freedesktop.portal.Window::GetActiveWindow,\n'
    printf '      o autoswitch de perfil precisa de uma das opções abaixo:\n\n'

    # Caminho 1: wlrctl via apt (se não estiver no PATH já).
    if ! command -v wlrctl >/dev/null 2>&1; then
        printf '      Caminho recomendado: instalar wlrctl (apt) - cobre qualquer\n'
        printf '      app Wayland (não so XWayland). Pacote no Ubuntu 24.04+.\n\n'
        ask_yn "instalar wlrctl via apt agora?" "${AUTO_YES}" "y"
        if [[ "${REPLY,,}" =~ ^y ]]; then
            if command -v sudo >/dev/null 2>&1; then
                if run_apt wlrctl 2>/dev/null; then
                    printf '      wlrctl instalado (%s)\n' "$(command -v wlrctl)"
                else
                    warn "wlrctl não esta nos repos deste sistema (Ubuntu <24.04?)"
                    printf '      alternativas:\n'
                    printf '        - Arch:   sudo pacman -S wlrctl\n'
                    printf '        - Fedora: sudo dnf install wlrctl\n'
                    printf '        - fonte:  https://git.sr.ht/~brocellous/wlrctl\n'
                fi
            else
                warn "sudo ausente - rode manualmente: sudo apt install wlrctl"
            fi
        fi
    else
        printf '      wlrctl ja instalado (%s) - WlrctlBackend vai detectar.\n' \
            "$(command -v wlrctl)"
    fi

    # Caminho 2: XWayland (fallback, complementar). Se usuário passou
    # --force-xwayland via CLI, pula o prompt.
    if [[ "${FORCE_XWAYLAND}" -eq 0 ]]; then
        printf '\n      Caminho alternativo: rodar a GUI sob XWayland. Cobre so\n'
        printf '      janelas XWayland (Steam, Proton), mas não precisa wlrctl.\n\n'
        ask_yn "ativar GDK_BACKEND=x11 no atalho (recomendado como complemento)?" \
            "${AUTO_YES}" "y"
        [[ "${REPLY,,}" =~ ^y ]] && FORCE_XWAYLAND=1
    fi
fi

if [[ "${FORCE_XWAYLAND}" -eq 1 ]]; then
    _EXEC_LINE="env GDK_BACKEND=x11 ${ROOT_DIR}/run.sh"
    printf '      .desktop com GDK_BACKEND=x11 (fallback XWayland)\n'
else
    _EXEC_LINE="${ROOT_DIR}/run.sh"
fi

cat > "${DESKTOP_TARGET}" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Hefesto - Dualsense4Unix
GenericName=DualSense Controller
Comment=Daemon de gatilhos adaptativos para DualSense no Linux
Exec=${_EXEC_LINE}
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
# 4d. Catalogos i18n (.mo) — copia locale/ para ~/.local/share/locale/
# ---------------------------------------------------------------------------
# FEAT-I18N-CATALOGS-01 (v3.4.0). Idempotente — re-copia sobrescreve. Se
# locale/ nao existe (usuario clonou e nao rodou scripts/i18n_compile.sh),
# pulamos silenciosamente e o gettext faz fallback para PT-BR hardcoded.
readonly LOCALE_SRC="${ROOT_DIR}/locale"
readonly LOCALE_TARGET="${HOME}/.local/share/locale"
if [[ -d "${LOCALE_SRC}" ]]; then
    for lang_dir in "${LOCALE_SRC}"/*/; do
        [[ -d "${lang_dir}" ]] || continue
        lang="$(basename "${lang_dir}")"
        src_mo="${lang_dir}LC_MESSAGES/hefesto-dualsense4unix.mo"
        [[ -f "${src_mo}" ]] || continue
        target_dir="${LOCALE_TARGET}/${lang}/LC_MESSAGES"
        mkdir -p "${target_dir}"
        cp -f "${src_mo}" "${target_dir}/hefesto-dualsense4unix.mo"
    done
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
