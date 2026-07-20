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
#                         POR DEFAULT, as regras canônicas + modules-load (uinput, uhid)
#                         são aplicadas automaticamente (re-cópia é idempotente).
#                         Se Flatpak Hefesto está instalado, também propaga.
#   --with-usb-quirk      OPT-IN (default OFF): aplica o quirk de boot
#                         usbcore.quirks=054c:0ce6:gn,054c:0df2:gn — a alavanca do
#                         storm -71 que PRESERVA o áudio do DualSense (ALTERNATIVA
#                         à regra 75 de áudio-off; use uma OU outra). É cmdline do
#                         kernel (NÃO é regra udev); ciente do bootloader
#                         (kernelstub/grub), idempotente e reversível. O install
#                         DEFAULT NÃO aplica (mudança de cmdline é sensível).
#   --no-kernel-watch     OPT-OUT do kernel-watch (DEFAULT ON): serviço de
#                         usuário que vigia o ecossistema USB/BT/xHCI no journal
#                         (storm -71, rate-limit do 8BitDo BT, erros de hci/xHCI
#                         e contadores de erro do rádio) num log dedicado
#                         (~/.local/state/hefesto-dualsense4unix/kernel.log;
#                         compat: storm.log). Sem sudo, replicável, simétrico.
#   --with-storm-watch    [DEPRECATED] no-op — o kernel-watch (sucessor) já é
#                         DEFAULT; mantida por compatibilidade.
#   --no-proton-pin       OPT-OUT do Proton pinado (DEFAULT ON): o install
#                         garante a versão de Proton VALIDADA (assets/
#                         proton-pin.conf, SHA256 obrigatório, cache offline em
#                         ~/.cache/hefesto-dualsense4unix/proton) e TRAVA o
#                         default global + os jogos instalados nela
#                         (CompatToolMapping; exige Steam fechada, com backup).
#                         Sem o pin, um upgrade de Proton pode reintroduzir o
#                         controle duplicado (semântica winebus mudou no 10).
#   (DEFAULT) plataforma: regras udev 81 (controles/adaptadores BT e hosts USB
#                         sem economia de energia), modprobe.d do btusb
#                         (enable_autosuspend=0), FastConnectable do BlueZ
#                         (SEM restart do bluetoothd) e cmdline gerenciado
#                         (usbcore.autosuspend/usbcore.quirks com MERGE e
#                         registro de dono). --no-udev pula os que tocam /etc.
#   (DEFAULT) broker root hide-hidraw (BROKER-01/Onda S — fd-injection): passo
#                         3h — esconde o hidraw FÍSICO do DualSense do JOGO
#                         (cura de raiz do controle duplicado) via broker de
#                         SISTEMA socket-activated; serve fd O_RDWR ao daemon
#                         via SCM_RIGHTS (cmd `open`) para o giroscópio nunca
#                         morrer, mesmo com o nó escondido. PRIMEIRO serviço de
#                         SISTEMA (systemd system, não --user) do projeto. Sem
#                         flag de opt-out ainda (broker ausente/recusado
#                         degrada para o comportamento de hoje — duplicado,
#                         nunca zero controles). Vale para TODO formato
#                         (native/flatpak/appimage/deb — achado Onda S #7).
#                         --no-udev pula (mesmo gate dos passos de plataforma).
#   (DEFAULT) DKMS hid-nintendo patchado (Onda T — cura de raiz do probe BT
#                         que mata o Pro Controller/8BitDo em silêncio, sem
#                         re-probar): módulo out-of-tree via DKMS
#                         (assets/dkms/hid-nintendo/) que substitui o in-tree
#                         (vence por precedência updates/dkms; NUNCA remove o
#                         in-tree). Defaults do patch == comportamento vanilla;
#                         a cura (retry de probe em BT) entra pela conf
#                         /etc/modprobe.d/hefesto-hid-nintendo.conf
#                         (bt_probe_retries=3). Fail-safe total: dkms/headers
#                         ausentes ou build falho = aviso honesto, o in-tree
#                         segue valendo, o install NUNCA aborta. Ativação
#                         NUNCA recarrega um módulo já carregado (derrubaria
#                         controles em uso) — vale no próximo boot/replug se
#                         o módulo estiver descarregado. Vale para TODO
#                         formato. Opt-out: --no-dkms (CI/sem hardware/kernel
#                         sem headers, como --no-udev).
#   --yes, -y             responde sim a todos os prompts (autostart, hotplug,
#                         AppIndicator extension, etc) e assume --format=native.
#   --no-systemd          pula a cópia da unit do daemon.
#   --no-hotplug-gui      pula a cópia da unit hotplug-gui.
#   --enable-autostart    habilita auto-start do daemon no boot (pula prompt).
#   --enable-hotplug-gui  habilita GUI auto-abrir ao plugar DualSense (pula prompt).
#   --enable-cosmic-applet  força compilar+instalar o applet COSMIC nativo
#                         (Rust) mesmo fora do COSMIC. Em COSMIC o applet já é
#                         DEFAULT-ON (a 1a build do libcosmic e longa, >10 min;
#                         requer cargo+just — se ausentes, o install NÃO falha,
#                         só avisa como instalar).
#   --no-cosmic-applet    OPT-OUT do applet COSMIC (não compila nem instala; um
#                         applet já instalado é preservado — remova via uninstall).
#   --no-dev              cria o venv SEM o extra [dev] (ruff/mypy/pytest). Por
#                         DEFAULT o venv já vem com os dev tools (gate local).
#                         Use em CI/máquina enxuta que só precisa rodar o app.
#   (DEFAULT) cura gentil do WirePlumber: REBAIXA o DualSense para não virar o
#                         microfone padrão (drop-in 51, user-space) — simétrica com o
#                         uninstall que a remove. Opt-out: --keep-dualsense-mic.
#   --keep-dualsense-mic  NÃO rebaixa o DualSense (deixa-o elegível como mic padrão).
#   --with-wireplumber-fix  redundante (já é o default); mantida para compat.
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
DISABLE_COSMIC_APPLET=0
NO_DEV=0
# BUG-UNINSTALL-WP-ASYMMETRY: DEFAULT ON. O uninstall remove o drop-in 51 por
# padrão, então o install tem de recolocá-lo por padrão (simetria) — senão o
# ciclo uninstall→install deixa o DualSense virar o microfone padrão. É a cura
# GENTIL (só rebaixa a prioridade, user-space, sem sudo, idempotente). Opt-out:
# --keep-dualsense-mic (ou export HEFESTO_DUALSENSE4UNIX_DUALSENSE_MIC_INTENDED=1).
WITH_WIREPLUMBER_FIX=1
WITH_WIREPLUMBER_DISABLE_MIC=0
WITH_USB_QUIRK=0
NO_DKMS=0
SKIP_KERNEL_WATCH=0
NO_PROTON_PIN=0
SKIP_SND_QUIRK=0
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
        --enable-cosmic-applet) ENABLE_COSMIC_APPLET=1; DISABLE_COSMIC_APPLET=0 ;;
        --no-cosmic-applet|--disable-cosmic-applet) DISABLE_COSMIC_APPLET=1 ;;
        --no-dev)             NO_DEV=1 ;;
        --with-wireplumber-fix) WITH_WIREPLUMBER_FIX=1 ;;  # já é default; mantida p/ compat
        --keep-dualsense-mic) WITH_WIREPLUMBER_FIX=0 ;;
        --with-wireplumber-disable-mic) WITH_WIREPLUMBER_DISABLE_MIC=1 ;;
        --with-usb-quirk)     WITH_USB_QUIRK=1 ;;
        --no-dkms)            NO_DKMS=1 ;;
        --no-snd-quirk)       SKIP_SND_QUIRK=1 ;;
        --no-kernel-watch)    SKIP_KERNEL_WATCH=1 ;;
        --with-storm-watch)   : ;;  # deprecated: o kernel-watch já é DEFAULT
        --no-proton-pin)      NO_PROTON_PIN=1 ;;
        --keep-steam-input)   KEEP_STEAM_INPUT=1 ;;
        --force-xwayland)     FORCE_XWAYLAND=1 ;;
        --format=*)           FORMAT="${arg#*=}" ;;
        --native)             FORMAT="native" ;;
        --flatpak)            FORMAT="flatpak" ;;
        --appimage)           FORMAT="appimage" ;;
        --deb)                FORMAT="deb" ;;
        --yes|-y)             AUTO_YES=1 ;;
        -h|--help)
            sed -n '2,99p' "${BASH_SOURCE[0]}" | sed 's/^# //; s/^#//'
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

# Registro de dono dos params de cmdline (PLAT-03): estado local que diz quem
# garante cada parâmetro — "hefesto" (nosso; o uninstall reverte), "terceiro"
# (Aurora/manual; o uninstall NUNCA toca) ou "compartilhado" (token
# usbcore.quirks fundido; o uninstall remove SÓ os IDs nossos). Regra da
# preservação: "hefesto"/"compartilhado" de um install PASSADO vence o
# "terceiro" do plano novo (o plano novo vê o token presente e não sabe que
# fomos nós que o pusemos).
readonly CMDLINE_OWNERS_FILE="${HOME}/.local/state/hefesto-dualsense4unix/cmdline-owners.conf"
_register_cmdline_owner() {
    local key="$1" value="$2" prev=""
    mkdir -p "$(dirname "${CMDLINE_OWNERS_FILE}")"
    if [[ -f "${CMDLINE_OWNERS_FILE}" ]]; then
        prev="$(sed -n "s/^${key}=//p" "${CMDLINE_OWNERS_FILE}" | head -1)"
    fi
    if [[ "${value}" == "terceiro" && ( "${prev}" == "hefesto" || "${prev}" == "compartilhado" ) ]]; then
        value="${prev}"
    fi
    {
        if [[ -f "${CMDLINE_OWNERS_FILE}" ]]; then
            grep -v "^${key}=" "${CMDLINE_OWNERS_FILE}" || true
        fi
        printf '%s=%s\n' "${key}" "${value}"
    } > "${CMDLINE_OWNERS_FILE}.tmp"
    mv "${CMDLINE_OWNERS_FILE}.tmp" "${CMDLINE_OWNERS_FILE}"
}

# Render das units do broker root hide-hidraw (BROKER-01/Onda S): substitui
# __SESSION_UID__/__SESSION_GROUP__ pelos valores reais da sessão e GARANTE
# que nenhum placeholder sobra (guarda pós-render — lição 6 da auditoria:
# nunca instalar unit com __SESSION_* literal, que autorizaria um uid
# inválido no .service ou deixaria o .socket sem grupo). Escreve os 2
# arquivos renderizados em "${out_dir}" e devolve 0; devolve 1 SEM escrever
# nada utilizável se o placeholder sobrar (ex.: asset editado errado). Função
# isolada de propósito — testável sem sudo/systemctl (tests/unit/
# test_install_broker_step.py).
_render_broker_units() {
    local service_src="$1" socket_src="$2" out_dir="$3" uid="$4" grupo="$5"
    sed "s/__SESSION_UID__/${uid}/" "${service_src}" \
        > "${out_dir}/hefesto-hidraw-broker.service"
    sed "s/__SESSION_GROUP__/${grupo}/" "${socket_src}" \
        > "${out_dir}/hefesto-hidraw-broker.socket"
    if grep -q '__SESSION_' "${out_dir}/hefesto-hidraw-broker.service" \
            "${out_dir}/hefesto-hidraw-broker.socket"; then
        return 1
    fi
    return 0
}

# ---------------------------------------------------------------------------
# Credencial sudo: adquirir UMA vez no início (BUG-INSTALL-SUDO-NONINTERACTIVE-01)
# ---------------------------------------------------------------------------
# Vários sub-passos usam sudo internamente (install_udev.sh, install_snd_quirk.sh
# → as_root install, o `just install` do applet → sudo install). Sem cachear a
# credencial no começo, cada um tenta pedir a senha por conta própria e, sem TTY
# (install rodado não-interativo), FALHA — e o passo seguia como se tivesse dado
# certo: o step 3c não gravava /etc/modprobe.d/hefesto-dualsense-storm.conf e o
# applet não era instalado, ambos em silêncio. Aqui primamos a credencial (uma
# senha) e a mantemos viva durante todo o install (a build do applet passa de
# 10 min e estouraria o timestamp_timeout default do sudo, ~15 min).
SUDO_KEEPALIVE_PID=""

_start_sudo_keepalive() {
    [[ -n "${SUDO_KEEPALIVE_PID}" ]] && return 0
    # Renova a cada 50s enquanto o install ($$) estiver vivo; para se a
    # credencial não puder mais ser renovada (evita loop preso).
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
    printf '\n>>> Alguns passos precisam de sudo (udev, cura do storm, applet COSMIC).\n'
    printf '    Vou pedir sua senha UMA vez; os passos seguintes reusam a credencial.\n'
    if sudo -v; then
        _start_sudo_keepalive
    else
        warn "sudo indisponível (senha/TTY) — passos com root serão pulados e avisados"
    fi
    return 0
}

_cleanup_sudo_keepalive() {
    [[ -n "${SUDO_KEEPALIVE_PID}" ]] && kill "${SUDO_KEEPALIVE_PID}" 2>/dev/null || true
}
trap _cleanup_sudo_keepalive EXIT

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

# Prime a credencial sudo uma vez (ver acquire_sudo). Só pede a senha se algum
# passo com root está de fato habilitado: udev (default), format deb (apt), o
# applet forçado (--enable-cosmic-applet) ou o DKMS (default, Onda T — --no-udev
# NÃO o desliga de propósito, é gate independente: --no-dkms). Em COSMIC o
# applet é default-on e também usa sudo, mas aí o udev já cobre o prime;
# --no-udev (CI sem hardware) dispensa o prompt salvo se deb/applet/dkms
# explícito.
_NEEDS_SUDO=1
if [[ "${SKIP_UDEV}" -eq 1 && "${FORMAT}" != "deb" \
        && "${ENABLE_COSMIC_APPLET}" -eq 0 && "${NO_DKMS}" -eq 1 ]]; then
    _NEEDS_SUDO=0
fi
acquire_sudo

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

# BROKER-01 (Onda S — achado #7): o broker root hide-hidraw é DEFAULT em TODO
# formato de instalação, não só no native. flatpak/appimage/deb davam `exit 0`
# ANTES do passo 3h e ficavam sem a cura de raiz do controle duplicado, em
# silêncio. Função compartilhada: o passo 3h (native) e o bloco dos formatos
# de pacote chamam o MESMO caminho (render por-máquina + enable do .socket).
# Best-effort integral: qualquer falha vira warn e o install segue (broker
# ausente degrada para o comportamento de hoje — duplicado, nunca zero).
install_broker_host() {
    if [[ "${SKIP_UDEV}" -eq 1 ]]; then
        printf '      broker pulado (--no-udev) — re-execute ./install.sh sem a flag para ativá-lo\n'
        return 0
    fi
    if ! command -v sudo >/dev/null 2>&1; then
        warn "sudo ausente — broker hide-hidraw NÃO instalado (a cura de raiz do duplicado fica de fora)"
        return 0
    fi
    if ! sudo -n true 2>/dev/null; then
        warn "sudo recusado — broker hide-hidraw pulado (re-execute ./install.sh)"
        return 0
    fi
    _broker_uid="${SUDO_UID:-$(id -u)}"
    if [[ "${_broker_uid}" == "0" ]]; then
        # Lição 6 (auditoria): renderizar uid 0 criaria um broker que só
        # autoriza ROOT — nenhum daemon de usuária conseguiria conectar.
        # Aborta SÓ este passo (nunca o install inteiro).
        warn "SESSION_UID resolveu 0 (root) — o broker autorizaria ROOT e nenhum daemon de usuária conectaria. Rode ./install.sh da SESSÃO da usuária (sudo é pedido internamente). Passo ABORTADO."
        return 0
    fi
    _broker_grupo="$(id -gn -- "${_broker_uid}")"
    _broker_bin_src="${ROOT_DIR}/src/hefesto_dualsense4unix/broker/hidraw_broker.py"
    _broker_bin_dst="/usr/local/lib/hefesto-dualsense4unix/hefesto-hidraw-broker"
    _broker_tmp="$(mktemp -d)"
    if [[ ! -f "${_broker_bin_src}" ]]; then
        warn "src/hefesto_dualsense4unix/broker/hidraw_broker.py ausente — broker NÃO instalado"
    elif ! _render_broker_units \
            "${ROOT_DIR}/assets/systemd/hefesto-hidraw-broker.service" \
            "${ROOT_DIR}/assets/systemd/hefesto-hidraw-broker.socket" \
            "${_broker_tmp}" "${_broker_uid}" "${_broker_grupo}"; then
        warn "render das units do broker deixou placeholder __SESSION_* sobrando — broker NÃO instalado"
    elif ! sudo install -Dm755 "${_broker_bin_src}" "${_broker_bin_dst}" 2>/dev/null; then
        warn "não consegui gravar ${_broker_bin_dst}"
    elif ! sudo install -Dm644 "${_broker_tmp}/hefesto-hidraw-broker.service" \
            /etc/systemd/system/hefesto-hidraw-broker.service 2>/dev/null \
         || ! sudo install -Dm644 "${_broker_tmp}/hefesto-hidraw-broker.socket" \
            /etc/systemd/system/hefesto-hidraw-broker.socket 2>/dev/null; then
        warn "não consegui gravar as units do broker em /etc/systemd/system"
    else
        sudo systemctl daemon-reload >/dev/null 2>&1 || true
        if sudo systemctl enable --now hefesto-hidraw-broker.socket >/dev/null 2>&1; then
            printf '      hefesto-hidraw-broker.socket habilitado (uid %s, grupo %s — só o .socket; o .service sobe na 1ª conexão)\n' \
                "${_broker_uid}" "${_broker_grupo}"
            # Registro de posse p/ uninstall (mesma disciplina do
            # cmdline-owners PLAT-03): caminhos + sha256, p/ o
            # uninstall remover SÓ o que fomos NÓS que instalamos.
            _broker_owner_file="${HOME}/.local/state/hefesto-dualsense4unix/broker-owner.conf"
            mkdir -p "$(dirname "${_broker_owner_file}")"
            {
                for _bp in "${_broker_bin_dst}" \
                           /etc/systemd/system/hefesto-hidraw-broker.service \
                           /etc/systemd/system/hefesto-hidraw-broker.socket; do
                    printf '%s=%s\n' "${_bp}" "$(sha256sum "${_bp}" 2>/dev/null | awk '{print $1}')"
                done
            } > "${_broker_owner_file}"
        else
            warn "enable --now do hefesto-hidraw-broker.socket falhou — habilite manualmente"
        fi
    fi
    rm -rf "${_broker_tmp}"
}

# Onda T (desenho: docs/process/estudos/2026-07-20-desenho-onda-t-patch-dkms.md):
# módulo hid-nintendo patchado (probe BT resiliente + module params) via DKMS
# genérico (scripts/dkms_lib.sh — reusado pela Onda W/rtw88). DEFAULT ON (regra
# da casa: install SEM FLAGS aplica), opt-out --no-dkms. Compartilhada entre o
# passo 3i (native) e o bloco dos formatos de pacote (mesmo padrão do broker
# acima) — DKMS é uma mudança de SISTEMA/kernel, ortogonal ao formato do app.
# Contrato fail-safe fica TODO dentro de dkms_lib.sh (ver seu cabeçalho): esta
# função só decide SE chama (flag/sudo) e a mensagem de ativação, nunca
# recarrega/descarrega o módulo.
install_dkms_hid_nintendo_host() {
    if [[ "${NO_DKMS}" -eq 1 ]]; then
        printf '      pulado (--no-dkms)\n'
        return 0
    fi
    if ! command -v sudo >/dev/null 2>&1; then
        warn "sudo ausente — patch DKMS do hid-nintendo NÃO instalado (driver in-tree continua, fail-safe)"
        return 0
    fi
    if ! sudo -n true 2>/dev/null; then
        warn "sudo recusado — patch DKMS do hid-nintendo pulado (re-execute ./install.sh)"
        return 0
    fi
    # shellcheck source=scripts/dkms_lib.sh
    source "${ROOT_DIR}/scripts/dkms_lib.sh"
    dkms_install_patched_module hefesto-hid-nintendo 1.0.0 \
        "${ROOT_DIR}/assets/dkms/hid-nintendo" hid-nintendo
    if sudo install -Dm644 "${ROOT_DIR}/assets/modprobe.d/hefesto-hid-nintendo.conf" \
            /etc/modprobe.d/hefesto-hid-nintendo.conf 2>/dev/null; then
        printf '      opções instaladas em /etc/modprobe.d/hefesto-hid-nintendo.conf (bt_probe_retries=3 + skip_tx_on_rate_exceeded=1)\n'
    else
        warn "não consegui gravar /etc/modprobe.d/hefesto-hid-nintendo.conf"
    fi
    # dkms_install_patched_module é fail-safe POR DESENHO: retorna 0 em TODOS
    # os ramos (sucesso E falha). O único juiz de "staged de verdade" é o
    # modinfo resolver p/ updates/dkms — sem esta checagem, o install
    # anunciava ativação futura mesmo com dkms ausente/build falho (mensagem
    # FALSA: nada foi staged e o próximo plug carrega o in-tree vanilla).
    if ! dkms_module_from_updates hid-nintendo; then
        warn "patch DKMS do hid-nintendo NÃO ficou staged (veja avisos acima) — driver in-tree continua (fail-safe); a conf do modprobe.d é inerte com o in-tree ('unknown parameter ignored')"
        return 0
    fi
    # ATIVAÇÃO FAIL-SAFE (mesmo princípio do btusb/broker acima): NUNCA
    # recarregamos um módulo em uso — a mantenedora joga com Pro Controller e
    # 8BitDo conectados AGORA, e substituir o módulo carregado os derrubaria.
    # Nota de precisão (diferente do btusb): substituição de módulo NÃO pega
    # em replug — se o in-tree está CARREGADO, o replug o re-liga a ele
    # mesmo; só o próximo BOOT troca. Mensagem honesta nos dois ramos.
    if [[ -d /sys/module/hid_nintendo/parameters ]]; then
        printf '      módulo patchado JÁ carregado (params visíveis em /sys/module/hid_nintendo/parameters)\n'
    elif [[ -d /sys/module/hid_nintendo ]]; then
        printf '      módulo in-tree em uso — NÃO recarregamos (derrubaria Pro/8BitDo conectados);\n'
        printf '      o patchado vale no próximo boot (replug re-liga no módulo já carregado)\n'
    else
        printf '      hid_nintendo descarregado — o patchado entra sozinho no próximo plug\n'
    fi
    return 0
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
    # SPRINT-GAME-RUMBLE-01 (H4): a cura de RAIZ do storm é DEFAULT também nos
    # formatos de pacote. O fluxo nativo a aplica no step 3c (abaixo), mas os
    # formatos dão `exit 0` antes dele. O .deb já entrega o .conf em
    # /usr/lib/modprobe.d (pega no próximo boot); aqui ativamos A QUENTE (sem
    # reboot) e cobrimos flatpak/appimage, que não escrevem em /etc. Preserva
    # mic+fone. --no-snd-quirk pula.
    if [[ "${SKIP_SND_QUIRK}" -eq 0 ]]; then
        step "cura" "cura de raiz do storm (snd_usb_audio quirk — preserva mic+fone)"
        if bash "${ROOT_DIR}/scripts/install_snd_quirk.sh"; then
            bash "${ROOT_DIR}/scripts/install_snd_quirk.sh" --runtime >/dev/null 2>&1 || true
            printf '      cura instalada e ativada (replug do controle p/ valer já)\n'
        else
            warn "install_snd_quirk.sh falhou — rode: sudo bash scripts/install_snd_quirk.sh"
        fi
    fi
    # BROKER-01 (Onda S — achado #7): o broker hide-hidraw é DEFAULT em TODO
    # formato (regra da casa: install SEM FLAGS). Antes, flatpak/appimage/deb
    # saíam daqui sem o broker e sem nenhum aviso — o P2 duplicado voltava em
    # qualquer jogo sem wrapper. Mesmo passo 3h do fluxo native.
    step "broker" "broker root hide-hidraw (BROKER-01 — DEFAULT em todo formato)"
    install_broker_host
    # Onda T (achado equivalente ao #7 do broker): DKMS é mudança de
    # SISTEMA/kernel, ortogonal ao formato do app — mesma função do passo 3i
    # do fluxo native. Opt-out: --no-dkms.
    step "dkms" "DKMS hid-nintendo patchado (Onda T — DEFAULT em todo formato)"
    install_dkms_hid_nintendo_host
    printf '\n─────────────────────────────────────────\n'
    printf ' Hefesto - Dualsense4Unix instalado (%s)\n' "${FORMAT}"
    printf ' Obs.: ajuste do microfone, desligar do Steam Input, preparo dos\n'
    printf ' jogos da Steam e os passos de plataforma (Proton pinado, BT no\n'
    printf ' máximo, cmdline) só valem no formato "native" (padrão).\n'
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
# BUG-INSTALL-VENV-NO-DEV-01: o extra [dev] (ruff/mypy/pytest) entra POR PADRÃO
# — assim o venv recém-criado já roda o gate pré-release local (antes o install
# recriava o venv sem dev tools e o `ruff`/`mypy` sumiam). --no-dev pula
# (CI/máquina enxuta). Se a instalação COM dev falhar (ex.: offline), cai para
# só o essencial e avisa, em vez de abortar o install inteiro.
_extras="emulation,cosmic"
[[ "${NO_DEV}" -eq 0 ]] && _extras="${_extras},dev"
if ! "${VENV_DIR}/bin/pip" install \
        --quiet --disable-pip-version-check -e "${ROOT_DIR}[${_extras}]" 2>/dev/null; then
    if [[ "${NO_DEV}" -eq 0 ]]; then
        warn "pip install com [dev] falhou — tentando só o essencial (ruff/mypy/pytest ficam de fora)"
        "${VENV_DIR}/bin/pip" install \
            --quiet --disable-pip-version-check -e "${ROOT_DIR}[emulation,cosmic]" 2>/dev/null \
            || die "pip install do pacote falhou — verifique a conexão e reexecute"
    else
        die "pip install do pacote falhou — verifique a conexão e reexecute"
    fi
fi
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
    # FIX-PACKAGING-SEED-PARITY-01: lista derivada de assets/*.rules em vez de
    # texto estático — o antigo citava "4 regras" quando o conjunto canônico já
    # tinha 6 (faltavam a 77-leds e a 78-motion-not-joystick). Regra nova em
    # assets/ aparece aqui automaticamente (descrição é best-effort por prefixo).
    # Fora do conjunto canônico: só a 75 (opt-in). 73/74 descontinuadas SAÍRAM
    # do repo em 2026-07-18 (o install_udev.sh ainda as remove de máquinas antigas).
    canonical_rules=()
    for rules_path in "${ROOT_DIR}/assets/"[0-9][0-9]-*.rules; do
        [[ -f "${rules_path}" ]] || continue
        rules_base="$(basename "${rules_path}")"
        case "${rules_base}" in
            75-*) continue ;;
        esac
        canonical_rules+=("${rules_base}")
    done
    printf '      copiando %d regras canônicas + modules-load (uinput, uhid) (sudo)\n' \
        "${#canonical_rules[@]}"
    for rules_base in "${canonical_rules[@]}"; do
        case "${rules_base}" in
            70-*) rules_desc='permissão hidraw (USB, BT e vpad virtual)' ;;
            71-uinput.rules) rules_desc='emulação Xbox360 via uinput' ;;
            71-uhid.rules) rules_desc='DualSense virtual via uhid (vibração na máscara PS)' ;;
            72-*) rules_desc='evita desconexão intermitente USB' ;;
            76-*) rules_desc='touchpad só pelo hefesto (sem briga)' ;;
            77-*) rules_desc='lightbar/player-LED graváveis via sysfs' ;;
            78-*) rules_desc='motion sensors fora da lista de joysticks' ;;
            79-*) rules_desc='LED de player dos controles Nintendo/8BitDo' ;;
            80-*) rules_desc='motion sensors fora da API js legada' ;;
            81-hefesto-usb-power.rules) rules_desc='controles e adaptadores BT nunca dormem (USB)' ;;
            81-hefesto-usb-host-power.rules) rules_desc='hosts USB (xHCI) sem economia que derruba o barramento' ;;
            *)    rules_desc='' ;;
        esac
        printf '        %-45s %s\n' "${rules_base}" "${rules_desc}"
    done
    printf '      (75 áudio-off é opt-in via --disable-usb-audio)\n'

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
# 3c. Cura de RAIZ do storm na camada de ÁUDIO (DEFAULT ON — modprobe.d)
# ---------------------------------------------------------------------------
# quirk_flags do snd_usb_audio (ignore_ctl_error|ctl_msg_delay_1m) para o
# DualSense: torna o probe do mixer UAC tolerante e ESPAÇA os control-transfers
# no EP0 — a rajada que gera o storm -71 na re-enumeração sob carga. PRESERVA
# mic+fone (NÃO desliga áudio), então é DEFAULT — ao contrário do 3b (cmdline,
# sensível) e da regra 75 (áudio-off total). Escreve só em /etc/modprobe.d (não
# boot-crítico). --no-snd-quirk pula (CI/sem hardware, como --no-udev). Validado
# ao vivo (storm zero em gameplay). SPRINT-GAME-RUMBLE-01.
if [[ "${SKIP_SND_QUIRK}" -eq 0 && "${SKIP_UDEV}" -eq 0 ]]; then
    step "3c" "cura de raiz do storm (snd_usb_audio quirk — preserva mic+fone)"
    SND_QUIRK_CONF="/etc/modprobe.d/hefesto-dualsense-storm.conf"
    if bash "${ROOT_DIR}/scripts/install_snd_quirk.sh"; then
        bash "${ROOT_DIR}/scripts/install_snd_quirk.sh" --runtime >/dev/null 2>&1 || true
    else
        warn "install_snd_quirk.sh retornou erro — rode: sudo bash scripts/install_snd_quirk.sh"
    fi
    # Post-check: confirma que a cura PERSISTENTE realmente foi gravada. Sem sudo
    # cacheado (install não-interativo), o `as_root install` interno falhava e o
    # passo seguia como se tivesse aplicado — deixando só o runtime, que some no
    # reboot. Agora avisamos explicitamente se o .conf não existe.
    if [[ -f "${SND_QUIRK_CONF}" ]]; then
        printf '      cura persistente OK em %s + ativada (replug do controle p/ valer já)\n' "${SND_QUIRK_CONF}"
    else
        warn "cura NÃO persistiu — ${SND_QUIRK_CONF} ausente (sudo recusado?)"
        warn "rode manualmente: sudo bash scripts/install_snd_quirk.sh"
    fi
fi

# ---------------------------------------------------------------------------
# 3d. Bluetooth no máximo (PLAT-04) — DEFAULT, sem flag
# ---------------------------------------------------------------------------
# As regras 81 (devices + hosts USB sem economia) entram junto com as udev do
# passo 3 (install_udev.sh é o dono). Aqui entram as camadas restantes:
#   - modprobe.d do btusb (enable_autosuspend=0): o btusb LIGA o autosuspend
#     do adaptador BT no probe (default Y do módulo — o furo provado no estudo
#     2026-07-18). O conf corta na raiz, inclusive p/ adaptadores composite
#     (classe ef) que escapam da regra 81. Vale no próximo probe; o runtime
#     imediato já é coberto pela regra 81 (power/control=on).
#   - FastConnectable do BlueZ: page scan agressivo → o botão PS reconecta
#     mais rápido. Drop-in em /etc/bluetooth/main.conf.d/ SE o BlueZ suportar
#     o diretório; senão bloco marcado idempotente APENSADO ao main.conf
#     (conffile do dpkg → backup antes). ARMADILHA respeitada: NUNCA
#     reiniciamos o bluetoothd (derrubaria os controles BT conectados —
#     provado ao vivo 2026-07-17); vale no próximo boot/restart natural.
if [[ "${SKIP_UDEV}" -eq 0 ]] && command -v sudo >/dev/null 2>&1; then
    step "3d" "Bluetooth no máximo (btusb sem autosuspend + reconexão rápida)"
    if ! sudo -n true 2>/dev/null; then
        warn "sudo recusado — passos de BT no máximo pulados (re-execute ./install.sh)"
    else
        # btusb: conf persistente + runtime p/ probes futuros (best-effort).
        if sudo install -Dm644 "${ROOT_DIR}/assets/modprobe.d/hefesto-btusb-no-autosuspend.conf" \
                /etc/modprobe.d/hefesto-btusb-no-autosuspend.conf 2>/dev/null; then
            printf '      modprobe.d do btusb instalado (adaptador BT nunca dorme; vale no próximo probe)\n'
        else
            warn "não consegui gravar /etc/modprobe.d/hefesto-btusb-no-autosuspend.conf"
        fi
        if [[ -e /sys/module/btusb/parameters/enable_autosuspend ]]; then
            printf '0' | sudo tee /sys/module/btusb/parameters/enable_autosuspend >/dev/null 2>&1 || true
        fi
        # FastConnectable (decisão por suporte real do BlueZ da máquina).
        FASTCONN_SENTINEL='# >>> hefesto FastConnectable >>>'
        if [[ -d /etc/bluetooth/main.conf.d ]]; then
            if sudo install -Dm644 "${ROOT_DIR}/assets/bluetooth/hefesto-fastconnectable.conf" \
                    /etc/bluetooth/main.conf.d/hefesto-fastconnectable.conf 2>/dev/null; then
                printf '      FastConnectable via drop-in main.conf.d (vale no próximo boot/restart do bluetoothd)\n'
            else
                warn "drop-in do FastConnectable falhou"
            fi
        elif [[ -f /etc/bluetooth/main.conf ]]; then
            if sudo grep -qF "${FASTCONN_SENTINEL}" /etc/bluetooth/main.conf 2>/dev/null; then
                printf '      FastConnectable já aplicado (bloco marcado presente) — nada a fazer\n'
            else
                _bt_backup="/etc/bluetooth/main.conf.bak.hefesto-$(date +%s)"
                if sudo cp /etc/bluetooth/main.conf "${_bt_backup}" 2>/dev/null \
                   && { printf '\n'; cat "${ROOT_DIR}/assets/bluetooth/hefesto-fastconnectable.block"; } \
                        | sudo tee -a /etc/bluetooth/main.conf >/dev/null 2>&1; then
                    printf '      FastConnectable apensado ao main.conf (backup: %s)\n' "${_bt_backup}"
                    printf '      vale no próximo boot/restart do bluetoothd — NÃO reiniciamos o serviço (derrubaria os controles BT)\n'
                else
                    warn "não consegui apensar o bloco FastConnectable ao /etc/bluetooth/main.conf"
                fi
            fi
        else
            printf '      sem /etc/bluetooth/main.conf (BlueZ ausente?) — FastConnectable pulado\n'
        fi

        # JustWorksRepairing (Onda R) — mesmo mecanismo do FastConnectable
        # acima (drop-in OU bloco apensado com sentinela própria), pelo mesmo
        # motivo: main.conf é conffile do dpkg, então SEMPRE com backup antes.
        # Sem isso, re-parear um controle com bond já existente (pós-migração
        # do backport bluez 5.85 — ONDA-R "BlueZ resiliente" abaixo — ou o
        # bond "meio-salvo" Paired-sem-Bonded) pode ser rejeitado pelo BlueZ
        # até timeout. Ver estudo 2026-07-19-estudo-bluez-backport-onda-r.md §4.
        JUSTWORKS_SENTINEL='# >>> hefesto JustWorksRepairing >>>'
        if [[ -d /etc/bluetooth/main.conf.d ]]; then
            if sudo install -Dm644 "${ROOT_DIR}/assets/bluetooth/hefesto-justworks.conf" \
                    /etc/bluetooth/main.conf.d/hefesto-justworks.conf 2>/dev/null; then
                printf '      JustWorksRepairing via drop-in main.conf.d (vale no próximo boot/restart do bluetoothd)\n'
            else
                warn "drop-in do JustWorksRepairing falhou"
            fi
        elif [[ -f /etc/bluetooth/main.conf ]]; then
            if sudo grep -qF "${JUSTWORKS_SENTINEL}" /etc/bluetooth/main.conf 2>/dev/null; then
                printf '      JustWorksRepairing já aplicado (bloco marcado presente) — nada a fazer\n'
            else
                _bt_backup_jw="/etc/bluetooth/main.conf.bak.hefesto-$(date +%s)"
                if sudo cp /etc/bluetooth/main.conf "${_bt_backup_jw}" 2>/dev/null \
                   && { printf '\n'; cat "${ROOT_DIR}/assets/bluetooth/hefesto-justworks.block"; } \
                        | sudo tee -a /etc/bluetooth/main.conf >/dev/null 2>&1; then
                    printf '      JustWorksRepairing apensado ao main.conf (backup: %s)\n' "${_bt_backup_jw}"
                    printf '      vale no próximo boot/restart do bluetoothd — NÃO reiniciamos o serviço (derrubaria os controles BT)\n'
                else
                    warn "não consegui apensar o bloco JustWorksRepairing ao /etc/bluetooth/main.conf"
                fi
            fi
        else
            printf '      sem /etc/bluetooth/main.conf (BlueZ ausente?) — JustWorksRepairing pulado\n'
        fi
    fi
fi

# ---------------------------------------------------------------------------
# 3e. Cmdline do kernel gerenciado (PLAT-03 item 2) — DEFAULT, registro de dono
# ---------------------------------------------------------------------------
# Garante usbcore.autosuspend=-1 + usbcore.quirks=054c:0ce6:gn,054c:0df2:gn no
# cmdline do PRÓXIMO boot, com as regras provadas no estudo 2026-07-18:
#   - o kernel respeita SÓ UM token usbcore.quirks= → o passo faz MERGE no
#     token existente (delete + add do fundido), NUNCA adiciona um segundo;
#   - já presente (Aurora/manual) = registra "terceiro" e NÃO toca — na
#     máquina de referência o passo é no-op com atribuição registrada;
#   - ausente = aplica e registra "hefesto" — o uninstall reverte SÓ o nosso;
#   - NUNCA reintroduz 054c:0ce6:k / processor.max_cstate / threadirqs
#     (removidos de propósito pela Aurora v3.24 — guarda no módulo).
# Quem DECIDE é o módulo puro integrations/kernel_cmdline.py (100% stdlib,
# testável); aqui só traduzimos o plano em kernelstub --delete/--add-options.
if [[ "${SKIP_UDEV}" -eq 0 ]] && command -v python3 >/dev/null 2>&1; then
    step "3e" "cmdline do kernel (usbcore.autosuspend + usbcore.quirks com merge)"
    _cmdline_plan="$(python3 - "${ROOT_DIR}" <<'PYEOF'
import json
import os
import shutil
import sys

root = sys.argv[1]
sys.path.insert(0, os.path.join(root, "src"))
from hefesto_dualsense4unix.integrations import kernel_cmdline as kc

tokens = None
backend = "none"
conf = "/etc/kernelstub/configuration"
grub = "/etc/default/grub"
if shutil.which("kernelstub") and os.path.isfile(conf):
    try:
        with open(conf, encoding="utf-8") as fh:
            data = json.load(fh)
        tokens = list((data.get("user") or {}).get("kernel_options") or [])
        backend = "kernelstub"
    except (OSError, ValueError):
        tokens = None
if tokens is None and os.path.isfile(grub):
    try:
        line = ""
        with open(grub, encoding="utf-8") as fh:
            for raw in fh:
                raw = raw.strip()
                if raw.startswith("GRUB_CMDLINE_LINUX_DEFAULT="):
                    line = raw.split("=", 1)[1].strip().strip('"')
        tokens = line.split()
        backend = "grub"
    except OSError:
        tokens = None
if tokens is None:
    print("backend=none")
    raise SystemExit(0)
actions = kc.plan_tokens(tokens)
violations = kc.forbidden_reintroductions(actions)
if violations:
    print("backend=guard-violation")
    for violation in violations:
        print("viol\t" + violation)
    raise SystemExit(0)
print("backend=" + backend)
for a in actions:
    print("\t".join(["plan", a.param, a.op, a.token, a.owner, " ".join(a.remove_tokens)]))
PYEOF
)" || _cmdline_plan=""
    _cmdline_backend="$(sed -n 's/^backend=//p' <<<"${_cmdline_plan}" | head -1)"
    if [[ -z "${_cmdline_backend}" || "${_cmdline_backend}" == "none" ]]; then
        warn "sem kernelstub e sem /etc/default/grub legíveis — passo pulado (nada registrado)"
    elif [[ "${_cmdline_backend}" == "guard-violation" ]]; then
        warn "guarda anti-reintrodução disparou — passo ABORTADO (nada foi escrito):"
        sed -n 's/^viol\t/        /p' <<<"${_cmdline_plan}"
    else
        _cmdline_changed=0
        while IFS=$'\t' read -r _tagp _param _op _token _owner _removes; do
            [[ "${_tagp}" == "plan" ]] || continue
            case "${_op}" in
                none)
                    _register_cmdline_owner "cmdline.${_param}" "${_owner}"
                    printf '      %s: já garantido (dono registrado: %s) — não toco\n' \
                        "${_param}" \
                        "$(sed -n "s/^cmdline.${_param}=//p" "${CMDLINE_OWNERS_FILE}" | head -1)"
                    ;;
                add|replace)
                    if [[ "${_cmdline_backend}" != "kernelstub" ]]; then
                        warn "${_param}: bootloader é grub — aplique manualmente em GRUB_CMDLINE_LINUX_DEFAULT: ${_token}"
                        [[ -n "${_removes}" ]] && warn "  (removendo antes o(s) token(s): ${_removes} — o kernel respeita SÓ UM usbcore.quirks=)"
                        continue
                    fi
                    if ! sudo -n true 2>/dev/null; then
                        warn "${_param}: sudo indisponível — cmdline NÃO escrito (re-execute ./install.sh)"
                        continue
                    fi
                    _ks_ok=1
                    for _rm_tok in ${_removes}; do
                        sudo kernelstub --delete-options "${_rm_tok}" >/dev/null 2>&1 || _ks_ok=0
                    done
                    sudo kernelstub --add-options "${_token}" >/dev/null 2>&1 || _ks_ok=0
                    if [[ "${_ks_ok}" -eq 1 ]]; then
                        _register_cmdline_owner "cmdline.${_param}" "${_owner}"
                        _cmdline_changed=1
                        printf '      %s: %s aplicado (dono: %s) — vale no PRÓXIMO boot\n' \
                            "${_param}" "${_token}" "${_owner}"
                    else
                        warn "${_param}: kernelstub falhou — rode: sudo kernelstub --add-options '${_token}'"
                    fi
                    ;;
            esac
        done <<<"${_cmdline_plan}"
        [[ "${_cmdline_changed}" -eq 0 ]] && printf '      nada a mudar no cmdline (estado já garantido; donos em %s)\n' "${CMDLINE_OWNERS_FILE}"
    fi
fi

# ---------------------------------------------------------------------------
# 3f. ONDA-R: BlueZ resiliente (backport local 5.85 do resolute) — DEFAULT
# ---------------------------------------------------------------------------
# Estudo docs/process/estudos/2026-07-19-estudo-bluez-backport-onda-r.md: o
# bluez 5.72-0ubuntu5.5 do noble crashou 6x em 5 dias (heap corruption/SEGV em
# hidp_add_connection/control_connect_cb — sempre em sessão com controles BT
# ativos); o 6º crash CHEGOU A COMER um bond recém-pareado. Nenhum SRU do
# noble toca esse subsistema. O rebuild do source package do resolute (26.04
# LTS, 5.85) traz ~10 fixes de crash de input/uhid ausentes no 5.72 (família
# upstream #815 + fixes de HIDP core).
#
# Este passo só CONSOME um build feito à parte (dget + dch --local +
# mk-build-deps + dpkg-buildpackage — ver o estudo §3 item 1): .debs
# versionados em ~/.cache/hefesto-dualsense4unix/bluez-backport/ com
# SHA256SUMS. Sem o cache, avisamos como gerar e seguimos SEM falhar o
# install (o backport é conveniência de resiliência, não requisito de
# funcionamento — o controle já funciona no 5.72).
#
# EFEITO COLATERAL MEDIDO (documentado, não escondido):
#   (a) o postinst do PRÓPRIO pacote bluez reinicia o bluetoothd ao trocar de
#       versão — a ÚNICA exceção à regra de nunca reiniciar o serviço, porque
#       é o próprio dpkg quem faz, não este script (idempotente: com a versão
#       já nossa, é no-op e o postinst nem roda de novo);
#   (b) a migração DESCARTA os bonds antigos no 1º start pós-troca (medido ao
#       vivo) — reparear uma vez resolve; bonds NOVOS (pareados já em 5.85)
#       persistem em restarts seguintes (também medido);
#   (c) ≥5.73 muda o input BT para a via uhid (bluetoothd passa a ser dono do
#       /dev/uhid do controle) — contingência documentada se aparecer
#       regressão: UserspaceHID=false em /etc/bluetooth/input.conf.
if [[ "${SKIP_UDEV}" -eq 0 ]] && command -v dpkg-query >/dev/null 2>&1 \
   && command -v dpkg >/dev/null 2>&1 && command -v sudo >/dev/null 2>&1; then
    step "3f" "ONDA-R: BlueZ resiliente (backport 5.85 — cura crashes crônicos do bluetoothd)"
    if ! sudo -n true 2>/dev/null; then
        warn "sudo recusado — passo do backport bluez pulado (re-execute ./install.sh)"
    else
        _bz_cur="$(dpkg-query -W -f='${Version}' bluez 2>/dev/null || true)"
        if [[ -z "${_bz_cur}" ]]; then
            printf '      bluez não instalado via dpkg (sistema não-Debian?) — passo pulado\n'
        elif dpkg --compare-versions "${_bz_cur}" ge 5.79 2>/dev/null; then
            # (e) no-op: já ≥5.79, sem o histórico de crash de input/uhid do 5.72.
            printf '      bluez %s já ≥5.79 — nada a fazer\n' "${_bz_cur}"
        else
            printf '      bluez %s < 5.79 (crashes crônicos de input/HIDP documentados no estudo)\n' "${_bz_cur}"
            _bz_dir="${HOME}/.cache/hefesto-dualsense4unix/bluez-backport"
            _bz_sums="${_bz_dir}/SHA256SUMS"
            _bz_deb_bluez="$(ls -t "${_bz_dir}"/bluez_*.deb 2>/dev/null | head -1)"
            _bz_deb_cups="$(ls -t "${_bz_dir}"/bluez-cups_*.deb 2>/dev/null | head -1)"
            _bz_deb_libbt="$(ls -t "${_bz_dir}"/libbluetooth3_*.deb 2>/dev/null | head -1)"
            if [[ ! -f "${_bz_sums}" || -z "${_bz_deb_bluez}" || -z "${_bz_deb_cups}" || -z "${_bz_deb_libbt}" ]]; then
                # (d) .debs ausentes: NÃO falha o install, só orienta o build.
                warn "backport não encontrado em ${_bz_dir} — bluetoothd 5.72 crônico segue ativo"
                printf '      como gerar: docs/process/estudos/2026-07-19-estudo-bluez-backport-onda-r.md §3 item 1\n'
            else
                # SHA256SUMS por basename (portátil — o arquivo pode ter sido
                # gerado com caminho absoluto de outra máquina/usuário).
                _bz_ok=1
                while read -r _bz_sum _bz_path; do
                    [[ -z "${_bz_sum}" ]] && continue
                    _bz_bn="$(basename "${_bz_path}")"
                    _bz_actual="$(sha256sum "${_bz_dir}/${_bz_bn}" 2>/dev/null | awk '{print $1}')"
                    if [[ -z "${_bz_actual}" || "${_bz_actual}" != "${_bz_sum}" ]]; then
                        _bz_ok=0
                        break
                    fi
                done < "${_bz_sums}"
                if [[ "${_bz_ok}" -eq 0 ]]; then
                    warn "SHA256SUMS não bateu em ${_bz_dir} — backport ABORTADO (nunca instalo .deb não verificado)"
                else
                    # (c) AVISO ALTO pré-aplicação — sob --yes prossegue; interativo
                    # tem Enter=sim (mesma filosofia de default-apply do install),
                    # mas o texto dá ao usuário a chance de recusar vendo o custo.
                    printf '\n      >>> AVISO: aplicar o backport bluez 5.85 REINICIA o bluetoothd\n'
                    printf '          (os controles BT caem até reconectar) e a migração DESCARTA os\n'
                    printf '          bonds antigos — reparei UMA VEZ os controles BT depois (PS+Create\n'
                    printf '          no DualSense). É a ÚNICA exceção à regra de nunca reiniciar o\n'
                    printf '          serviço: quem reinicia é o postinst do PRÓPRIO pacote bluez.\n\n'
                    ask_yn "aplicar o backport agora?" "${AUTO_YES}" "y"
                    if [[ "${REPLY,,}" =~ ^y ]]; then
                        # (b) grava a versão anterior ANTES de trocar, SE ainda não
                        # registrada (idempotente — não sobrescreve um registro que
                        # já exista de uma execução anterior do install).
                        if [[ ! -f "${_bz_dir}/VERSOES-ANTERIORES.txt" ]]; then
                            # Arquitetura via dpkg --print-architecture (nunca hardcoded):
                            # numa arquitetura != amd64 o "libbluetooth3:amd64" fixo faria
                            # o dpkg-query falhar silenciosamente (stderr descartado, ||
                            # true) e o registro sairia incompleto, deixando o restore do
                            # uninstall sem cobrir libbluetooth3.
                            _bz_arch="$(dpkg --print-architecture 2>/dev/null || echo amd64)"
                            dpkg-query -W -f='${Package}\t${Version}\n' bluez bluez-cups "libbluetooth3:${_bz_arch}" \
                                > "${_bz_dir}/VERSOES-ANTERIORES.txt" 2>/dev/null || true
                            printf '      versões anteriores gravadas em %s\n' "${_bz_dir}/VERSOES-ANTERIORES.txt"
                        fi
                        # DEBIAN_FRONTEND=noninteractive + --force-confdef/--force-confold:
                        # /etc/bluetooth/main.conf é conffile do dpkg e a esta altura JÁ
                        # ESTÁ modificado por nós (bloco FastConnectable/JustWorks apensado
                        # no passo 3d) — sem forçar, um dpkg interativo perguntaria o que
                        # fazer com o conffile local; sob --yes (ou sem tty) isso pode travar
                        # esperando resposta. Forçamos manter a versão atual (a nossa).
                        if sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y --allow-downgrades \
                                -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold" \
                                "${_bz_deb_libbt}" "${_bz_deb_bluez}" "${_bz_deb_cups}" >/dev/null 2>&1; then
                            printf '      backport aplicado — reparei os controles BT UMA VEZ (bonds antigos foram descartados)\n'
                        else
                            warn "apt-get install do backport falhou — rode manualmente com os .debs em ${_bz_dir}"
                        fi
                    else
                        printf '      pulado a pedido — bluetoothd 5.72 crônico segue ativo\n'
                    fi
                fi
            fi
        fi
    fi
fi

# ---------------------------------------------------------------------------
# 3g. ONDA-R: agente de pareamento BT persistente — DEFAULT (bond meio-salvo)
# ---------------------------------------------------------------------------
# "No agent available for request type 2" = nenhum agente de pareamento D-Bus
# registrado no momento em que o BlueZ pede confirmação → autenticação nunca
# completa → nasce o bond "meio-salvo" (Paired: yes / Bonded: no), que trava o
# controle até um re-pareamento manual. Cura: bt-agent (pacote bluez-tools do
# noble) como serviço de SISTEMA persistente com --capability=NoInputNoOutput
# (aceita automaticamente pareamentos sem PIN/senha — o caso do DualSense/
# 8BitDo/Nintendo Pro). Ver estudo §4. `--now` aqui é seguro: habilita/inicia
# SÓ o agente, nunca mexe no bluetoothd.
if [[ "${SKIP_UDEV}" -eq 0 ]] && command -v sudo >/dev/null 2>&1; then
    step "3g" "ONDA-R: agente de pareamento BT persistente (cura o bond meio-salvo)"
    if ! sudo -n true 2>/dev/null; then
        warn "sudo recusado — agente de pareamento pulado (re-execute ./install.sh)"
    else
        if ! command -v bt-agent >/dev/null 2>&1; then
            printf '      bluez-tools ausente (fornece bt-agent) — instalando (sudo)\n'
            if run_apt bluez-tools; then
                printf '      bluez-tools instalado\n'
            else
                warn "não consegui instalar bluez-tools — instale manualmente: sudo apt install bluez-tools"
            fi
        else
            printf '      bluez-tools já presente (bt-agent em %s)\n' "$(command -v bt-agent)"
        fi
        if command -v bt-agent >/dev/null 2>&1; then
            if sudo install -Dm644 "${ROOT_DIR}/assets/systemd/hefesto-bt-agent.service" \
                    /etc/systemd/system/hefesto-bt-agent.service 2>/dev/null; then
                sudo systemctl daemon-reload >/dev/null 2>&1 || true
                if sudo systemctl enable --now hefesto-bt-agent.service >/dev/null 2>&1; then
                    printf '      hefesto-bt-agent.service habilitado (agente NoInputNoOutput persistente)\n'
                else
                    warn "enable --now do hefesto-bt-agent.service falhou — habilite manualmente"
                fi
            else
                warn "não consegui gravar /etc/systemd/system/hefesto-bt-agent.service"
            fi
        else
            warn "bt-agent ainda ausente — agente de pareamento NÃO habilitado"
        fi
    fi
fi

# ---------------------------------------------------------------------------
# 3h. Broker root hide-hidraw (BROKER-01/Onda S — fd-injection) — DEFAULT
# ---------------------------------------------------------------------------
# Esconde o hidraw FÍSICO do DualSense do JOGO (cura de RAIZ do controle
# duplicado): broker de SISTEMA (PRIMEIRO da história do projeto — os demais
# são --user), socket-activated, que recebe hide/restore do daemon E devolve
# um fd O_RDWR via SCM_RIGHTS (cmd `open`) para o motion reader nunca precisar
# reabrir por caminho — o giroscópio sobrevive mesmo com o nó escondido.
# Desenho completo: docs/process/estudos/2026-07-20-desenho-onda-s-broker-fd-injection.md
# §7.1. Sem flag de opt-out: broker ausente/recusado degrada para o
# comportamento de hoje (duplicado, nunca zero controles — invariante sagrado).
if [[ "${SKIP_UDEV}" -eq 0 ]] && command -v sudo >/dev/null 2>&1; then
    step "3h" "broker root hide-hidraw (cura de raiz do P2 duplicado — BROKER-01)"
    # Achado Onda S #7: o corpo virou a função compartilhada
    # `install_broker_host` — o MESMO caminho roda nos formatos
    # flatpak/appimage/deb (que saem com `exit 0` antes deste passo).
    install_broker_host
fi

# ---------------------------------------------------------------------------
# 3i. DKMS hid-nintendo patchado (Onda T) — DEFAULT, opt-out --no-dkms
# ---------------------------------------------------------------------------
# Cura de RAIZ da morte silenciosa do Pro Controller/8BitDo em Bluetooth: o
# driver in-tree falha o PROBE (joycon_read_info -110) e NUNCA re-proba — o
# device some do sistema até replug/power-cycle (medido 3x nesta máquina).
# Módulo out-of-tree via DKMS (probe BT com retry opcional + module params;
# defaults == vanilla) via a lib genérica scripts/dkms_lib.sh (reusada pela
# Onda W/rtw88). Desenho completo:
# docs/process/estudos/2026-07-20-desenho-onda-t-patch-dkms.md.
# Contrato fail-safe: dkms/headers ausentes ou build falho = aviso honesto,
# o in-tree segue valendo, o install NUNCA aborta por causa disto.
step "3i" "Onda T: hid-nintendo patchado via DKMS (probe BT resiliente + module params)"
install_dkms_hid_nintendo_host

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
# 4b-2. Wrapper de launch da Steam (DEDUP-04) — DEFAULT, sem flag, sem sudo
# ---------------------------------------------------------------------------
# `hefesto-launch %command%` é a Opção de Inicialização CONSTANTE: o wrapper
# decide as envs na hora do launch consultando o daemon via IPC (daemon morto/
# degradado => nenhuma env => o jogo abre com o físico visível — pior caso é
# controle duplicado, nunca zero). Passo de USUÁRIO de propósito: instalável
# sem sudo e simétrico no uninstall (que limpa o vdf ANTES de apagar isto).
readonly LAUNCH_WRAPPER_SRC="${ROOT_DIR}/assets/hefesto-launch.sh"
readonly LAUNCH_WRAPPER_TARGET="${HOME}/.local/share/hefesto-dualsense4unix/bin/hefesto-launch"
if [[ -f "${LAUNCH_WRAPPER_SRC}" ]]; then
    install -Dm755 "${LAUNCH_WRAPPER_SRC}" "${LAUNCH_WRAPPER_TARGET}"
    # Diretório da materialização (o daemon regrava a cada transição; criar
    # aqui garante que o wrapper nunca falha por diretório ausente).
    mkdir -p "${HOME}/.local/state/hefesto-dualsense4unix/launch_env"
else
    warn "assets/hefesto-launch.sh ausente — wrapper de launch da Steam não instalado"
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
# PATH-06: o wrapper de launch também entra no PATH — `which hefesto-launch`
# passa a funcionar e a Launch Option pode ser digitada à mão como
# `hefesto-launch %command%`. A string canônica do botão (WRAPPER_LAUNCH,
# formato `sh -c` com caminho absoluto) continua a mesma: funciona SEM PATH.
if [[ -x "${LAUNCH_WRAPPER_TARGET}" ]]; then
    ln -sf "${LAUNCH_WRAPPER_TARGET}" "${BIN_DIR}/hefesto-launch"
fi
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
# 7b. kernel-watch (DEFAULT — opt-out --no-kernel-watch): vigia do ecossistema
#     USB/BT/xHCI num log dedicado. Evolução do storm-watch (PLAT-06 item 4):
#     além do storm -71, vigia o rate-limit do hid-nintendo (a morte do 8BitDo
#     em BT), erros de hci/xHCI e o delta dos contadores de erro do rádio BT.
#     Script/unit mantêm os NOMES antigos (compat); o log novo é
#     ~/.local/state/hefesto-dualsense4unix/kernel.log (storm.log vira symlink
#     se não existir como arquivo). Sem sudo; simétrico no uninstall.
# ---------------------------------------------------------------------------
if [[ "${SKIP_KERNEL_WATCH}" -eq 1 ]]; then
    step "7b/11" "kernel-watch pulado (--no-kernel-watch)"
else
    step "7b/11" "kernel-watch: vigia USB/BT/xHCI (log dedicado do ecossistema)"
    readonly STORM_SCRIPT_SRC="${ROOT_DIR}/scripts/storm_watch.sh"
    readonly STORM_SCRIPT_DIR="${HOME}/.local/share/hefesto-dualsense4unix/scripts"
    readonly STORM_SCRIPT_TARGET="${STORM_SCRIPT_DIR}/storm_watch.sh"
    readonly STORM_UNIT_SRC="${ROOT_DIR}/assets/hefesto-dualsense4unix-storm-watch.service"
    readonly STORM_USER_UNIT_DIR="${HOME}/.config/systemd/user"
    readonly STORM_UNIT_TARGET="${STORM_USER_UNIT_DIR}/hefesto-dualsense4unix-storm-watch.service"

    if [[ ! -f "${STORM_SCRIPT_SRC}" || ! -f "${STORM_UNIT_SRC}" ]]; then
        warn "kernel-watch: arquivos-fonte ausentes — reinstale o repo"
    else
        mkdir -p "${STORM_SCRIPT_DIR}" "${STORM_USER_UNIT_DIR}"
        install -m755 "${STORM_SCRIPT_SRC}" "${STORM_SCRIPT_TARGET}"
        cp -f "${STORM_UNIT_SRC}" "${STORM_UNIT_TARGET}"
        if command -v systemctl >/dev/null 2>&1; then
            systemctl --user daemon-reload >/dev/null 2>&1 || true
            if systemctl --user enable --now hefesto-dualsense4unix-storm-watch.service >/dev/null 2>&1; then
                printf '      habilitado — log em ~/.local/state/hefesto-dualsense4unix/kernel.log (compat: storm.log)\n'
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
# 9. Applet COSMIC nativo (Rust + libcosmic) — DEFAULT-ON em COSMIC
# ---------------------------------------------------------------------------
# BUG-INSTALL-APPLET-OPT-IN-SKIPPED-01: o applet era opt-in (--enable-cosmic-
# applet), então um ./install.sh normal PULAVA — e quem já tinha o applet o
# perdia/deixava stale num ciclo uninstall+install. Agora é DEFAULT-ON: instala
# quando faz sentido (em COSMIC, ou se já está instalado, ou se forçado por
# --enable-cosmic-applet). Opt-out via --no-cosmic-applet. A build exige
# cargo+just; se ausentes, NÃO falha o install (só avisa como instalar Rust).
readonly APPLET_BIN="/usr/local/bin/hefesto-dualsense4unix-applet"
step "9/11" "applet COSMIC nativo (padrão em COSMIC; --no-cosmic-applet desativa)"
install_cosmic_applet() {
    local applet_dir="${ROOT_DIR}/packaging/cosmic-applet"
    if ! command -v cargo >/dev/null 2>&1 || ! command -v just >/dev/null 2>&1; then
        warn "cargo/just ausentes — applet COSMIC pulado (o install segue normal)"
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
_applet_installed=0
[[ -e "${APPLET_BIN}" ]] && _applet_installed=1
if [[ "${DISABLE_COSMIC_APPLET}" -eq 1 ]]; then
    printf '      pulado (--no-cosmic-applet)\n'
    [[ "${_applet_installed}" -eq 1 ]] \
        && printf '      (applet já instalado foi preservado — remova via ./uninstall.sh)\n'
elif [[ "${ENABLE_COSMIC_APPLET}" -eq 1 || "${DESKTOP_IS_COSMIC}" -eq 1 || "${_applet_installed}" -eq 1 ]]; then
    install_cosmic_applet
else
    printf '      fora do COSMIC e não instalado — pulado (force: ./install.sh --enable-cosmic-applet)\n'
fi

# ---------------------------------------------------------------------------
# 10. WirePlumber: DualSense fora da fonte de áudio padrão — DEFAULT (opt-out: --keep-dualsense-mic)
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
    printf '      pulado (--keep-dualsense-mic): o DualSense pode virar o microfone padrão\n'
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
# 11b. Launch Options: migrar o veneno estático para o wrapper — DEFAULT, sem flag
# ---------------------------------------------------------------------------
# DEDUP-05 (P0, "inseparável do DEDUP-04"): migra as Launch Options VENENOSAS
# de ondas anteriores (IGNORE_DEVICES estático persistido por jogo — esconde o
# único controle quando o vpad degrada => jogo com ZERO controles) para a
# chamada do wrapper hefesto-launch. Só toca linhas com a assinatura nossa;
# opções do usuário são preservadas. --stop-steam: fecha a Steam se preciso
# (ela regrava o vdf ao sair) e reabre depois; com um JOGO aberto o módulo
# RECUSA (rc=3) em vez de matá-lo. Módulo 100% stdlib — python3 do sistema.
#
# Passo PRÓPRIO, fora do bloco do Steam Input, de propósito (achado MED da
# revisão adversarial): --keep-steam-input é opt-out SÓ do PSSupport e não
# pode pular o desenvenenamento; e a migração tampouco depende de o
# disable_steam_input.sh existir/ser executável.
step "11b" "Steam: migrar Launch Options antigas para o wrapper hefesto-launch"
LAUNCH_MIGRATE_PY="${ROOT_DIR}/src/hefesto_dualsense4unix/integrations/steam_launch_options.py"
if [[ -f "${LAUNCH_MIGRATE_PY}" ]] && command -v python3 >/dev/null 2>&1; then
    printf '      se a Steam estiver aberta, ela será fechada e reaberta só para\n'
    printf '      concluir a migração — pause downloads antes de seguir.\n'
    printf '      (com um jogo aberto, a migração é adiada e nada é fechado.)\n'
    if python3 "${LAUNCH_MIGRATE_PY}" --migrate --stop-steam; then
        printf '      Launch Options antigas do Hefesto migradas para o wrapper hefesto-launch\n'
    else
        warn "migração das Launch Options adiada — rode com a Steam fechada (e sem jogo aberto): python3 ${LAUNCH_MIGRATE_PY} --migrate"
    fi
else
    warn "steam_launch_options.py ausente ou sem python3 — migração pulada; rode depois: python3 ${LAUNCH_MIGRATE_PY} --migrate"
fi

# ---------------------------------------------------------------------------
# 11c. Proton PINADO (PLAT-01) — DEFAULT, opt-out --no-proton-pin
# ---------------------------------------------------------------------------
# A semântica do winebus MUDOU entre Proton 9→10 (PROTON_ENABLE_HIDRAW morreu
# — provado no estudo 2026-07-18); sem pin, um upgrade automático de Proton
# pode reintroduzir o controle duplicado da noite pro dia. O módulo
# integrations/proton_pin.py (100% stdlib, python3 do sistema) garante a
# versão validada do assets/proton-pin.conf em compatibilitytools.d (cache
# offline-first em ~/.cache/hefesto-dualsense4unix/proton; SHA256 OBRIGATÓRIO
# — checksum errado = NADA é extraído) e TRAVA o default global + os jogos
# instalados nela (CompatToolMapping no config.vdf, com backup
# config.vdf.bak.hefesto-proton-<ts>; com a Steam/jogo abertos a trava é
# ADIADA com instrução — mesmo gate dos outros passos que editam vdf).
# Upgrade é sempre DELIBERADO: editar o proton-pin.conf + rodar o install.
step "11c" "Proton pinado: versão validada + trava dos jogos"
PROTON_PIN_PY="${ROOT_DIR}/src/hefesto_dualsense4unix/integrations/proton_pin.py"
if [[ "${NO_PROTON_PIN}" -eq 1 ]]; then
    printf '      pulado (--no-proton-pin) — sem o pin, um upgrade de Proton pode duplicar o controle\n'
elif [[ ! -f "${PROTON_PIN_PY}" ]] || ! command -v python3 >/dev/null 2>&1; then
    warn "proton_pin.py ausente ou sem python3 — pin do Proton pulado"
elif [[ ! -f "${ROOT_DIR}/assets/proton-pin.conf" ]]; then
    warn "assets/proton-pin.conf ausente — pin do Proton pulado (reinstale o repo)"
else
    _pp_rc=0
    python3 "${PROTON_PIN_PY}" --ensure || _pp_rc=$?
    if [[ "${_pp_rc}" -eq 1 ]]; then
        warn "checksum do Proton NÃO bateu — passo ABORTADO (nunca instalo binário não verificado)"
    elif [[ "${_pp_rc}" -eq 2 ]]; then
        warn "sem rede e sem cache — o pin fica PENDENTE (rode ./install.sh de novo com internet); trava adiada"
    elif [[ "${_pp_rc}" -ne 0 ]]; then
        warn "garantia da versão pinada falhou (rc=${_pp_rc}) — rode: python3 ${PROTON_PIN_PY} --ensure"
    else
        _pl_rc=0
        python3 "${PROTON_PIN_PY}" --lock || _pl_rc=$?
        if [[ "${_pl_rc}" -eq 0 ]]; then
            printf '      jogos travados na versão pinada (backup do config.vdf ao lado; reverter: uninstall)\n'
        elif [[ "${_pl_rc}" -eq 3 ]]; then
            warn "Steam (ou um jogo) aberta — trava ADIADA; feche a Steam e rode: python3 ${PROTON_PIN_PY} --lock"
            warn "  (ou use o botão 'Travar Proton validado' na aba Sistema da GUI)"
        else
            warn "trava do Proton falhou — rode manualmente: python3 ${PROTON_PIN_PY} --lock"
        fi
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
