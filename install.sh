#!/usr/bin/env bash
# install.sh — instala Hefesto - Dualsense4Unix no ambiente do usuário.
#
# Formatos (--format=FMT, ou prompt interativo; default: native):
#   native     venv editável + atalho (instalação de desenvolvimento, atual).
#   flatpak    build local + flatpak install --user (sandbox GNOME//47).
#   appimage   build do .AppImage GUI + atalho em ~/.local/bin.
#   deb        build do .deb + sudo apt install (venv bundlado).
# Atalhos equivalentes: --flatpak, --appimage, --deb, --native.
#
# Flags:
#   --format=FMT          escolhe o formato (native|flatpak|appimage|deb).
#   --no-udev             pula udev rules (sudo) — útil em CI sem hardware.
#                         POR DEFAULT, as 3 regras canônicas + modules-load uinput
#                         são aplicadas automaticamente (re-cópia é idempotente).
#                         Se Flatpak Hefesto está instalado, também propaga.
#   --with-usb-quirk      OPT-IN (default OFF): aplica o quirk de boot
#                         usbcore.quirks=054c:0ce6:gn,054c:0df2:gn — a alavanca do
#                         storm -71 que PRESERVA o áudio do DualSense (ALTERNATIVA
#                         à regra 75 de áudio-off; use uma OU outra). É cmdline do
#                         kernel (NÃO é regra udev); ciente do bootloader
#                         (kernelstub/grub), idempotente e reversível. O install
#                         DEFAULT NÃO aplica (mudança de cmdline é sensível).
#   --with-storm-watch    OPT-IN (default OFF): instala um serviço de usuário que
#                         registra o storm USB (-71) do DualSense num log dedicado
#                         (~/.local/state/hefesto-dualsense4unix/storm.log).
#                         Replicável e sobrevive reboot (sem /tmp, sem sudo). O
#                         journald já guarda tudo; isto é só um recorte legível.
#   --yes, -y             responde sim a todos os prompts (autostart, hotplug,
#                         AppIndicator extension, etc) e assume --format=native.
#   --no-systemd          pula a cópia da unit do daemon.
#   --no-hotplug-gui      pula a cópia da unit hotplug-gui.
#   --enable-autostart    habilita auto-start do daemon no boot (pula prompt).
#   --enable-hotplug-gui  habilita GUI auto-abrir ao plugar DualSense (pula prompt).
#   --enable-cosmic-applet  compila e instala o applet COSMIC nativo (Rust; a
#                         1a build do libcosmic e longa, >10 min). Opt-in.
#   --with-wireplumber-fix  instala drop-in do WirePlumber que REBAIXA o DualSense
#                         para não virar o microfone padrão do sistema + reset.
#   --with-wireplumber-disable-mic  DESABILITA de vez a source (mic) do DualSense
#                         (node.disabled; controle vira só-HID). Vence até escassez
#                         de fonte. Mutuamente exclusiva com --with-wireplumber-fix.
#   --keep-steam-input    preserva Steam Input PSSupport (default: desliga).
#                         Sem esta flag, o install zera SteamController_PSSupport
#                         e UseSteamControllerConfig em TODOS os localconfig.vdf
#                         (todos os Steam users em qualquer formato: deb/flatpak/
#                         snap), evitando que a Steam intercepte o DualSense e
#                         entre em conflito com o daemon. Reverte com:
#                         scripts/disable_steam_input.sh --restore.
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
ENABLE_COSMIC_APPLET=0
WITH_WIREPLUMBER_FIX=0
WITH_WIREPLUMBER_DISABLE_MIC=0
WITH_USB_QUIRK=0
WITH_STORM_WATCH=0
KEEP_STEAM_INPUT=0
FORCE_XWAYLAND=0
AUTO_YES=0
FORMAT=""

for arg in "$@"; do
    case "$arg" in
        --no-udev)            SKIP_UDEV=1 ;;
        --no-systemd)         SKIP_SYSTEMD=1 ;;
        --no-hotplug-gui)     SKIP_HOTPLUG_GUI=1 ;;
        --enable-autostart)   ENABLE_AUTOSTART=1 ;;
        --enable-hotplug-gui) ENABLE_HOTPLUG_GUI=1 ;;
        --enable-cosmic-applet) ENABLE_COSMIC_APPLET=1 ;;
        --no-cosmic-applet)   ENABLE_COSMIC_APPLET=0 ;;
        --with-wireplumber-fix) WITH_WIREPLUMBER_FIX=1 ;;
        --with-wireplumber-disable-mic) WITH_WIREPLUMBER_DISABLE_MIC=1 ;;
        --with-usb-quirk)     WITH_USB_QUIRK=1 ;;
        --with-storm-watch)   WITH_STORM_WATCH=1 ;;
        --keep-steam-input)   KEEP_STEAM_INPUT=1 ;;
        --force-xwayland)     FORCE_XWAYLAND=1 ;;
        --format=*)           FORMAT="${arg#*=}" ;;
        --native)             FORMAT="native" ;;
        --flatpak)            FORMAT="flatpak" ;;
        --appimage)           FORMAT="appimage" ;;
        --deb)                FORMAT="deb" ;;
        --yes|-y)             AUTO_YES=1 ;;
        -h|--help)
            sed -n '2,42p' "${BASH_SOURCE[0]}" | sed 's/^# //; s/^#//'
            exit 0
            ;;
        *) printf 'aviso: argumento desconhecido: %s\n' "$arg" ;;
    esac
done

case "${FORMAT}" in
    ""|native|flatpak|appimage|deb) ;;
    *) printf 'ERRO: formato inválido: %s (use native|flatpak|appimage|deb)\n' "${FORMAT}" >&2; exit 2 ;;
esac

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
# 0. Seleção de formato de instalação
# ---------------------------------------------------------------------------
# native (default) faz a instalação de desenvolvimento (venv editável + atalho
# para run.sh). flatpak/appimage/deb reusam os build scripts e instalam o
# pacote real. udev é sempre aplicado no host (o controle não funciona sem as
# regras, em qualquer formato).
if [[ -z "${FORMAT}" ]]; then
    if [[ "${AUTO_YES}" -eq 1 ]]; then
        FORMAT="native"
    else
        printf '\nFormato de instalação:\n'
        printf '  1) native    venv editável + atalho (desenvolvimento; default)\n'
        printf '  2) flatpak   build local + flatpak install --user (sandbox GNOME//47)\n'
        printf '  3) appimage  build do .AppImage GUI + atalho em ~/.local/bin\n'
        printf '  4) deb       build do .deb + sudo apt install (venv bundlado)\n'
        _fmt_choice=""
        read -r -p "Escolha [1-4] (Enter = native): " _fmt_choice || true
        case "${_fmt_choice:-}" in
            2|flatpak)  FORMAT="flatpak" ;;
            3|appimage) FORMAT="appimage" ;;
            4|deb)      FORMAT="deb" ;;
            *)          FORMAT="native" ;;
        esac
    fi
fi
printf '\n>>> Formato escolhido: %s\n' "${FORMAT}"

# udev no host — compartilhado por todos os formatos (o pacote .deb já cobre
# via postinst; flatpak/appimage/native precisam desta chamada explícita).
install_udev_host() {
    if [[ "${SKIP_UDEV}" -eq 1 ]]; then
        printf '      udev pulado (--no-udev) — rode depois: sudo bash scripts/install_udev.sh\n'
    elif command -v sudo >/dev/null 2>&1; then
        if bash "${ROOT_DIR}/scripts/install_udev.sh" >/dev/null 2>&1; then
            printf '      udev rules aplicadas + recarregadas\n'
        else
            warn "install_udev.sh falhou — rode manualmente: sudo bash scripts/install_udev.sh"
        fi
    else
        warn "sudo ausente — rode scripts/install_udev.sh como root depois"
    fi
}

format_flatpak() {
    step "flatpak" "build + flatpak install --user (GNOME//47)"
    require flatpak
    command -v flatpak-builder >/dev/null 2>&1 \
        || die "flatpak-builder ausente. Instale: sudo apt install flatpak-builder (ou flatpak install flathub org.flatpak.Builder)"
    bash "${ROOT_DIR}/scripts/build_flatpak.sh" --install \
        || die "build_flatpak.sh falhou"
    install_udev_host
    printf '\n      Abrir: flatpak run br.andrefarias.Hefesto\n'
}

format_appimage() {
    step "appimage" "build do .AppImage GUI + atalho"
    bash "${ROOT_DIR}/scripts/build_appimage_gui.sh" \
        || die "build_appimage_gui.sh falhou (veja pré-requisitos no cabeçalho do script)"
    local appimage
    appimage="$(ls -t "${ROOT_DIR}/dist/appimage/"*.AppImage 2>/dev/null | head -1)"
    [[ -n "${appimage}" ]] || die "nenhum .AppImage gerado em dist/appimage/"
    mkdir -p "${BIN_DIR}"
    local target="${BIN_DIR}/Hefesto-Dualsense4Unix.AppImage"
    cp -f "${appimage}" "${target}"
    chmod +x "${target}"
    mkdir -p "${ICON_TARGET_DIR}" "$(dirname "${DESKTOP_TARGET}")"
    cp -f "${ICON_SRC}" "${ICON_TARGET}"
    cat > "${DESKTOP_TARGET}" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Hefesto - Dualsense4Unix
GenericName=DualSense Controller
Comment=Daemon de gatilhos adaptativos para DualSense no Linux
Exec=${target} --gui
Icon=${APP_ID}
Categories=Settings;HardwareSettings;
Terminal=false
StartupNotify=true
StartupWMClass=Hefesto-Dualsense4Unix
DESKTOP
    command -v update-desktop-database >/dev/null 2>&1 \
        && update-desktop-database -q "$(dirname "${DESKTOP_TARGET}")" 2>/dev/null || true
    install_udev_host
    [[ -f "${ROOT_DIR}/scripts/install_profiles.sh" ]] \
        && bash "${ROOT_DIR}/scripts/install_profiles.sh" "${ROOT_DIR}" >/dev/null 2>&1 || true
    printf '\n      Instalado: %s\n      Abrir pelo menu de apps ou: %s --gui\n' "${target}" "${target}"
}

format_deb() {
    step "deb" "build do .deb + sudo apt install"
    bash "${ROOT_DIR}/scripts/build_deb.sh" \
        || die "build_deb.sh falhou"
    local deb
    deb="$(ls -t "${ROOT_DIR}/dist/"*.deb 2>/dev/null | head -1)"
    [[ -n "${deb}" ]] || die "nenhum .deb gerado em dist/"
    command -v sudo >/dev/null 2>&1 || die "sudo necessário para 'apt install'"
    sudo apt-get install -y "${deb}" || die "apt install falhou"
    printf '\n      Instalado via apt (udev + .desktop via postinst).\n      Abrir: hefesto-dualsense4unix-gui\n'
}

if [[ "${FORMAT}" != "native" ]]; then
    case "${FORMAT}" in
        flatpak)  format_flatpak ;;
        appimage) format_appimage ;;
        deb)      format_deb ;;
    esac
    printf '\n─────────────────────────────────────────\n'
    printf ' Hefesto - Dualsense4Unix instalado (%s)\n' "${FORMAT}"
    printf ' Desinstalar: ./uninstall.sh\n'
    printf '─────────────────────────────────────────\n\n'
    exit 0
fi

# ---------------------------------------------------------------------------
# 1. Verificar Python
# ---------------------------------------------------------------------------
step "1/11" "verificando dependências do sistema"
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
step "2/11" "preparando ambiente Python"

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

# DURABILIDADE-DIST-UPGRADE-01: um full dist upgrade pode bumpar o Python do
# sistema (ex.: 3.11 -> 3.12), quebrando o venv — o symlink bin/python passa a
# apontar para um interpretador removido e os site-packages ficam da versão
# antiga. O check de "home" acima só pega o caso pyenv. Aqui detectamos
# bin/python inexecutável OU divergência de minor version e recriamos. Idempotente:
# quando a versão bate, é no-op.
if [[ -d "${VENV_DIR}" ]]; then
    _sys_ver=$("${_VENV_PYTHON}" -c 'import sys;print("%d.%d"%sys.version_info[:2])' 2>/dev/null)
    _venv_ver=$("${VENV_DIR}/bin/python" -c 'import sys;print("%d.%d"%sys.version_info[:2])' 2>/dev/null)
    if [[ -z "${_venv_ver}" ]]; then
        printf '      venv com Python inexecutável (provável dist upgrade) — recriando...\n'
        rm -rf "${VENV_DIR}"
    elif [[ -n "${_sys_ver}" ]] && [[ "${_venv_ver}" != "${_sys_ver}" ]]; then
        printf '      venv em Python %s, sistema agora em %s — recriando...\n' \
            "${_venv_ver}" "${_sys_ver}"
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
step "3/11" "udev rules (hidraw + uinput + autosuspend)"

if [[ "${SKIP_UDEV}" -eq 1 ]]; then
    printf '      pulado (--no-udev) — IMPORTANTE: o controle precisa das regras\n'
    printf '      para funcionar. Rode depois: sudo bash scripts/install_udev.sh\n'
elif ! command -v sudo >/dev/null 2>&1; then
    warn "sudo ausente — pulando (rode scripts/install_udev.sh manualmente como root)"
else
    printf '      copiando 4 regras canônicas + modules-load uinput (sudo)\n'
    printf '        70-ps5-controller.rules                permissão hidraw (USB e BT)\n'
    printf '        71-uinput.rules                        emulação Xbox360 via uinput\n'
    printf '        72-ps5-controller-autosuspend.rules    evita desconexão intermitente USB\n'
    printf '        76-...-touchpad-libinput-ignore.rules  touchpad só pelo hefesto (sem briga)\n'
    printf '      (73/74 descontinuadas; 75 áudio-off é opt-in via --disable-usb-audio)\n'

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
# 3b. Quirk de boot do áudio USB (OPT-IN — default OFF; cmdline, NÃO udev)
# ---------------------------------------------------------------------------
# A alavanca do storm -71 que PRESERVA o áudio do DualSense
# (usbcore.quirks=054c:0ce6:gn,054c:0df2:gn). É um PARÂMETRO DE CMDLINE do
# kernel — uma regra udev não consegue alterar o próprio enumeramento do device,
# por isso entra como passo de install ciente do bootloader (kernelstub/grub).
# Mudança de cmdline é sensível: só aplica com --with-usb-quirk. ALTERNATIVA à
# regra 75 (áudio-off via install_udev.sh --disable-usb-audio) — use uma OU outra.
# Idempotente (o script não duplica token). FEAT-DSX-DEFINITIVE-FIX-01 §7.5.
if [[ "${WITH_USB_QUIRK}" -eq 1 ]]; then
    step "3b" "quirk de boot usbcore.quirks (preserva o áudio do DualSense)"
    if bash "${ROOT_DIR}/scripts/install_usb_quirk.sh"; then
        printf '      quirk aplicado (vale no próximo boot) — confira: scripts/install_usb_quirk.sh --status\n'
    else
        warn "install_usb_quirk.sh falhou — rode: sudo bash scripts/install_usb_quirk.sh"
    fi
fi

# ---------------------------------------------------------------------------
# 4. Ícone + .desktop + launcher
# ---------------------------------------------------------------------------
step "4/11" "atalho de aplicativo e launcher"

# FEAT-ICON-MULTI-RES-01 (v3.4.2, refinado em v3.4.3): gera o icone em
# todas resolucoes do hicolor + pixmap legacy. Antes so existia 256x256
# PNG, fazendo o COSMIC App Library / GNOME Activities renderizar
# fallback generico em sizes nao-256 (chip 32x32 do menu apps, 128x128
# do grid).
#
# BUG-ICON-FROM-PLACEHOLDER-SVG-01 (v3.4.3 fix): v3.4.2 usava SVG como
# source para o rsvg-convert. Mas assets/appimage/Hefesto-Dualsense4Unix.
# svg eh um PLACEHOLDER simples (chama laranja + texto "HEFESTO"),
# não a logo real (martelo + gradiente roxo/azul/rosa no PNG 256x256).
# Resultado: app library mostrava chama laranja em vez do martelo.
# Fix: source canonico eh o PNG 256x256 sempre, com Lanczos downsample
# do ImageMagick para outras resolucoes. Sem SVG escalavel ate termos
# um SVG real do martelo.
ICON_HICOLOR_BASE="${HOME}/.local/share/icons/hicolor"
ICON_SIZES="16 22 24 32 48 64 96 128 192 256 512"

# Sempre garante o 256x256 PNG (path legacy)
mkdir -p "${ICON_TARGET_DIR}"
cp -f "${ICON_SRC}" "${ICON_TARGET}"
mkdir -p "$(dirname "${DESKTOP_TARGET}")"

if command -v convert >/dev/null 2>&1; then
    printf '      gerando icone multi-res do PNG 256x256 (ImageMagick Lanczos)\n'
    for size in ${ICON_SIZES}; do
        target_dir="${ICON_HICOLOR_BASE}/${size}x${size}/apps"
        mkdir -p "${target_dir}"
        convert "${ICON_SRC}" -filter Lanczos -resize "${size}x${size}" \
            "${target_dir}/${APP_ID}.png" 2>/dev/null || true
    done
    # Pixmap legacy fallback (DEs antigos)
    mkdir -p "${HOME}/.local/share/pixmaps"
    cp -f "${ICON_SRC}" "${HOME}/.local/share/pixmaps/${APP_ID}.png"
    # Remove SVG placeholder de instalações anteriores (v3.4.2 colocava lah).
    rm -f "${ICON_HICOLOR_BASE}/scalable/apps/${APP_ID}.svg"
else
    printf '      aviso: ImageMagick (convert) ausente — so 256x256 PNG\n'
    printf '             instale: sudo apt install imagemagick\n'
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
# locale/ não existe (usuário clonou e não rodou scripts/i18n_compile.sh),
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
step "5/11" "symlink ${BIN_DIR}/hefesto-dualsense4unix"
ln -sf "${VENV_DIR}/bin/hefesto-dualsense4unix" "${BIN_DIR}/hefesto-dualsense4unix"
ok

# ---------------------------------------------------------------------------
# 6. Daemon systemd --user (copia sempre; auto-start é opt-in)
# ---------------------------------------------------------------------------
step "6/11" "daemon systemd --user"

if [[ "${SKIP_SYSTEMD}" -eq 1 ]]; then
    printf '      pulado (--no-systemd)\n'
else
    # Decide se habilita auto-start ANTES de chamar o CLI.
    enable_daemon=0
    if [[ "${ENABLE_AUTOSTART}" -eq 1 ]]; then
        enable_daemon=1
    else
        # Default 'y': o daemon precisa estar rodando pro controle funcionar;
        # autostart no boot é o esperado de "instala tudo" (sem passo manual
        # após reboot/formatar). Quem não quiser: responder 'n' (ou não usar -y).
        ask_yn "habilitar auto-start do daemon no boot?" "${AUTO_YES}" "y"
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
step "7/11" "hotplug USB → abre a GUI automaticamente"

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
# 7b. Storm-watch (opt-in): serviço de usuário que loga o -71 num arquivo
#     dedicado. FEAT-DSX-STORM-WATCH-01. Habilitado por --with-storm-watch ou
#     pelo modo "tudo" (--yes). Replicável e simétrico no uninstall.
# ---------------------------------------------------------------------------
if [[ "${WITH_STORM_WATCH}" -eq 1 || "${AUTO_YES}" -eq 1 ]]; then
    step "7b/11" "Storm-watch: serviço de usuário (log dedicado do -71)"
    readonly STORM_SCRIPT_SRC="${ROOT_DIR}/scripts/storm_watch.sh"
    readonly STORM_SCRIPT_DIR="${HOME}/.local/share/hefesto-dualsense4unix/scripts"
    readonly STORM_SCRIPT_TARGET="${STORM_SCRIPT_DIR}/storm_watch.sh"
    readonly STORM_UNIT_SRC="${ROOT_DIR}/assets/hefesto-dualsense4unix-storm-watch.service"
    readonly STORM_USER_UNIT_DIR="${HOME}/.config/systemd/user"
    readonly STORM_UNIT_TARGET="${STORM_USER_UNIT_DIR}/hefesto-dualsense4unix-storm-watch.service"

    if [[ ! -f "${STORM_SCRIPT_SRC}" || ! -f "${STORM_UNIT_SRC}" ]]; then
        warn "storm-watch: arquivos-fonte ausentes — reinstale o repo"
    else
        mkdir -p "${STORM_SCRIPT_DIR}" "${STORM_USER_UNIT_DIR}"
        install -m755 "${STORM_SCRIPT_SRC}" "${STORM_SCRIPT_TARGET}"
        cp -f "${STORM_UNIT_SRC}" "${STORM_UNIT_TARGET}"
        if command -v systemctl >/dev/null 2>&1; then
            systemctl --user daemon-reload >/dev/null 2>&1 || true
            if systemctl --user enable --now hefesto-dualsense4unix-storm-watch.service >/dev/null 2>&1; then
                printf '      habilitado — log em ~/.local/state/hefesto-dualsense4unix/storm.log\n'
            else
                warn "enable falhou — habilite: systemctl --user enable --now hefesto-dualsense4unix-storm-watch.service"
            fi
        else
            warn "systemctl ausente — unit copiada mas não habilitada"
        fi
    fi
fi

# ---------------------------------------------------------------------------
# 8. Extension AppIndicator no GNOME (necessária para o ícone de bandeja)
# ---------------------------------------------------------------------------
step "8/11" "GNOME: extension AppIndicator (tray icon)"

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
# 9. Applet COSMIC nativo (Rust + libcosmic) — opt-in
# ---------------------------------------------------------------------------
step "9/11" "applet COSMIC nativo (opt-in)"
install_cosmic_applet() {
    local applet_dir="${ROOT_DIR}/packaging/cosmic-applet"
    if ! command -v cargo >/dev/null 2>&1 || ! command -v just >/dev/null 2>&1; then
        warn "cargo/just ausentes — applet COSMIC pulado"
        printf '        instale rustup (https://rustup.rs) + just e os -dev, depois:\n'
        printf '        sudo apt install just libxkbcommon-dev libwayland-dev libgbm-dev \\\n'
        printf '             libegl-dev libinput-dev libudev-dev pkg-config\n'
        printf '        e rode: ./install.sh --enable-cosmic-applet\n'
        return 0
    fi
    printf '      compilando + instalando (1a build do libcosmic e LONGA, >10 min)\n'
    if just -f "${applet_dir}/justfile" -d "${applet_dir}" install; then
        printf '      applet instalado — adicione em Config. > Paineis > Miniaplicativos\n'
    else
        warn "build/instalacao do applet falhou — veja o log acima"
    fi
}
if [[ "${ENABLE_COSMIC_APPLET}" -eq 1 ]]; then
    install_cosmic_applet
elif [[ "${DESKTOP_IS_COSMIC}" -eq 1 ]]; then
    ask_yn "instalar o applet COSMIC nativo agora? (1a build do libcosmic e longa)" "${AUTO_YES}" "n"
    if [[ "${REPLY,,}" =~ ^y ]]; then
        install_cosmic_applet
    else
        printf '      pulado (instale depois: ./install.sh --enable-cosmic-applet)\n'
    fi
else
    printf '      fora do COSMIC — pulado\n'
fi

# ---------------------------------------------------------------------------
# 10. WirePlumber: DualSense fora da fonte de áudio padrão — opt-in
# ---------------------------------------------------------------------------
step "10/11" "audio: impedir o DualSense de virar o microfone padrão"
if [[ "${WITH_WIREPLUMBER_DISABLE_MIC}" -eq 1 ]]; then
    [[ "${WITH_WIREPLUMBER_FIX}" -eq 1 ]] && warn "--with-wireplumber-disable-mic vence --with-wireplumber-fix"
    # exit 2 (DualSense é a única fonte) não é falha de instalação — só aviso.
    if bash "${ROOT_DIR}/scripts/fix_wireplumber_default_source.sh" --disable-source; rc=$?; [[ "${rc:-0}" -ne 1 ]]; then
        printf '      mic do DualSense DESABILITADO (node.disabled; controle só-HID)\n'
    else
        warn "disable-source falhou — rode: bash scripts/fix_wireplumber_default_source.sh --disable-source"
    fi
elif [[ "${WITH_WIREPLUMBER_FIX}" -eq 1 ]]; then
    if bash "${ROOT_DIR}/scripts/fix_wireplumber_default_source.sh" --install; rc=$?; [[ "${rc:-0}" -ne 1 ]]; then
        printf '      drop-in do WirePlumber instalado + fonte padrão reeleita\n'
    else
        warn "fix do WirePlumber falhou — rode: bash scripts/fix_wireplumber_default_source.sh --install"
    fi
else
    printf '      pulado (use --with-wireplumber-disable-mic ou --with-wireplumber-fix, ou: scripts/doctor.sh --fix)\n'
fi

# ---------------------------------------------------------------------------
# 11. Steam Input: desligar PSSupport (default ON, opt-out --keep-steam-input)
# ---------------------------------------------------------------------------
# FEAT-DISABLE-STEAM-INPUT-PSSUPPORT-01. Sem isso, a Steam com PSSupport=2 +
# UseSteamControllerConfig=2 (default da própria Steam após o wizard
# Deck_Configurator*_SteamInputOptIn) pega o /dev/hidraw* do DualSense
# exclusivamente e re-injeta como Steam Virtual Gamepad com bindings do
# desktop_ps4.vdf — conflitando com o daemon do Hefesto e produzindo os 3
# sintomas clássicos (touchpad → cursor, mic muting spam, botões em
# background). O script itera por TODOS os localconfig.vdf de todos os
# Steam users em todos os formatos (.deb / Flatpak / Snap), backup ao lado.
step "11/11" "Steam: desligar PSSupport do PlayStation Controller"
if [[ "${KEEP_STEAM_INPUT}" -eq 1 ]]; then
    printf '      pulado (--keep-steam-input) — Steam Input pode conflitar com o daemon\n'
elif [[ ! -x "${ROOT_DIR}/scripts/disable_steam_input.sh" ]]; then
    warn "scripts/disable_steam_input.sh ausente ou não-executável — pulado"
else
    if bash "${ROOT_DIR}/scripts/disable_steam_input.sh" --apply; then
        printf '      Steam Input PSSupport zerado em todos os localconfig.vdf\n'
        printf '      reverter: bash scripts/disable_steam_input.sh --restore\n'
    else
        warn "disable_steam_input.sh falhou — rode: bash scripts/disable_steam_input.sh --apply"
    fi

    # Guard: path unit + timer que reaplicam PSSupport=OFF se a Steam reescrever
    # o vdf (update/saída). FEAT-STEAM-INPUT-SELF-HEAL-01. Usa --apply-quiet
    # (nunca fecha a Steam). Units --user, sem sudo.
    USER_UNIT_DIR="${HOME}/.config/systemd/user"
    mkdir -p "${USER_UNIT_DIR}"
    install -Dm644 "${ROOT_DIR}/assets/hefesto-steam-input-guard.path"  "${USER_UNIT_DIR}/hefesto-steam-input-guard.path"
    install -Dm644 "${ROOT_DIR}/assets/hefesto-steam-input-guard.timer" "${USER_UNIT_DIR}/hefesto-steam-input-guard.timer"
    sed "s#__SCRIPT__#${ROOT_DIR}/scripts/disable_steam_input.sh#g" \
        "${ROOT_DIR}/assets/hefesto-steam-input-guard.service" > "${USER_UNIT_DIR}/hefesto-steam-input-guard.service"
    if systemctl --user daemon-reload 2>/dev/null \
       && systemctl --user enable --now hefesto-steam-input-guard.path hefesto-steam-input-guard.timer 2>/dev/null; then
        printf '      guard do Steam Input habilitado (path + timer 30min)\n'
    else
        warn "não consegui habilitar o guard --user (sessão systemd ausente?) — será pego no próximo login"
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

# BUG-MIC-ON-SEM-QUIRK-REABRE-STORM-01: recomendação (apenas print) para quem usa
# o microfone do DualSense. O quirk de áudio USB (usbcore.quirks=054c:0ce6:gn) é
# o que segura o storm -71 COM o mic ligado; ligar o mic sem ele pode reabrir o
# storm. NÃO aplicamos nem tocamos no cmdline (gerido pela toolchain pessoal
# Aurora) — só avisamos. Mesma detecção do doctor.sh (ativo/agendado/runtime).
QUIRK_MARKER="054c:0ce6:gn"
quirk_present=0
if grep -q "${QUIRK_MARKER}" /proc/cmdline 2>/dev/null; then quirk_present=1; fi
if [[ -r /etc/kernelstub/configuration ]] && grep -q "${QUIRK_MARKER}" /etc/kernelstub/configuration 2>/dev/null; then quirk_present=1; fi
if [[ -r /etc/default/grub ]] && grep -q "${QUIRK_MARKER}" /etc/default/grub 2>/dev/null; then quirk_present=1; fi
if [[ -r /sys/module/usbcore/parameters/quirks ]] && grep -q "${QUIRK_MARKER}" /sys/module/usbcore/parameters/quirks 2>/dev/null; then quirk_present=1; fi
if [[ "${quirk_present}" -eq 0 ]]; then
    printf '\n'
    printf ' Vai usar o MICROFONE do DualSense?\n'
    printf '   O quirk de áudio USB segura o storm -71 com o mic ligado.\n'
    printf '   Para aplicá-lo (vale no próximo boot, NÃO mexe no cmdline agora):\n'
    printf '     bash scripts/install_usb_quirk.sh\n'
    printf '─────────────────────────────────────────\n'
fi
printf '\n'

# "O que fazes com paz de espírito, isso sim dura." — Marco Aurélio
