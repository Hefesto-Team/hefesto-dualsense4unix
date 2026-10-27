#!/usr/bin/env bash

set -euo pipefail
_ajuda() {
  cat <<'AJUDA'
install.sh — instala Hefesto - DualSense4Unix no ambiente do usuário.

Formatos (--format=FMT, ou prompt interativo; default: native):
  native     venv editável + atalho (instalação de desenvolvimento, atual).
  flatpak    build local + flatpak install --user (sandbox GNOME//47).
  appimage   build do .AppImage GUI + atalho em ~/.local/bin.
  deb        build do .deb + sudo apt install (venv bundlado).
Atalhos equivalentes: --flatpak, --appimage, --deb, --native.

Flags:
  --dry-run, -n         ENSAIO. Imprime CADA mudança que este script faria —
                        arquivo por arquivo, unit por unit, pacote por pacote —
                        e NÃO ESCREVE NADA: nenhum arquivo copiado, nenhum
                        pacote instalado, nenhum serviço reiniciado, nenhum
                        módulo DKMS compilado, nenhum `localconfig.vdf` da
                        Steam tocado. Nem sequer pergunta a senha do sudo.
                        Existe porque este arquivo mexe em udev, DKMS,
                        systemd, no cmdline do kernel e nos arquivos da Steam
                        de quem instala, e ninguém tinha como VER antes.
                        O ensaio respeita todas as outras flags: o plano que
                        ele imprime é o plano DAQUELA linha de comando, nesta
                        máquina, agora.
                        SEM CREDENCIAL SUDO EM CACHE os passos de root
                        aparecem como "PULARIA (sudo)", porque é isso que
                        aconteceria de verdade. Para ver o plano inteiro:
                            sudo -v && ./install.sh --dry-run
  --format=FMT          escolhe o formato (native|flatpak|appimage|deb).
  --no-udev             pula udev rules (sudo) — útil em CI sem hardware.
                        POR DEFAULT, as regras canônicas + modules-load (uinput, uhid)
                        são aplicadas automaticamente (re-cópia é idempotente).
                        Se Flatpak Hefesto está instalado, também propaga.
  --with-usb-quirk      OPT-IN (default OFF): aplica o quirk de boot
                        usbcore.quirks=054c:0ce6:gn — a alavanca do
                        storm -71 que PRESERVA o áudio do DualSense (ALTERNATIVA
                        à regra 75 de áudio-off; use uma OU outra). É cmdline do
                        kernel (NÃO é regra udev); ciente do bootloader
                        (kernelstub/grub), idempotente e reversível. O install
                        DEFAULT NÃO aplica (mudança de cmdline é sensível).
                        ATENÇÃO: o passo 3e (cmdline gerenciado, DEFAULT) já
                        grava esses MESMOS tokens de quirk — esta flag só
                        adianta o passo 3b e é redundante com o default.
  --no-snd-quirk        OPT-OUT do quirk do snd_usb_audio (DEFAULT ON, passo
                        3c): grava /etc/modprobe.d/hefesto-dualsense-storm.conf
                        com quirk_flags do DualSense (ignore_ctl_error e
                        ctl_msg_delay_1m) — a cura de raiz do storm -71 na
                        camada de ÁUDIO, que PRESERVA mic e fone (ao contrário
                        da regra 75). Use em CI/sem hardware; --no-udev também
                        pula este passo.
  --no-ucm              OPT-OUT do perfil UCM do DualSense (DEFAULT ON, passo
                        3c-bis): grava o verbo HiFi e um gancho por controlador
                        USB em /usr/share/alsa/ucm2, sem tocar o alsa-ucm-conf.
                        Sem ele o GE-Proton não acha a vibração dos jogos da
                        Sony pelo cabo. --no-udev também pula este passo.
  --no-fechar-o-no      OPT-OUT do nó que nasce FECHADO (DEFAULT ON). Por
                        default o hidraw do DualSense
                        físico nasce 0600 root (TAG-="uaccess") e o broker o
                        abre sob pedido — é o que impede a Steam de pegá-lo no
                        instante da conexão e deixar a barra de luz apagada.
                        Com esta flag o nó volta a nascer aberto para a sessão,
                        e o broker é renderizado sabendo disso (as duas metades
                        da cura têm de concordar). Use só se precisar do nó
                        aberto para ferramenta de terceiro.
  --no-kernel-watch     OPT-OUT do kernel-watch (DEFAULT ON): serviço de
                        usuário que vigia o ecossistema USB/BT/xHCI no journal
                        (storm -71, rate-limit do 8BitDo BT, erros de hci/xHCI
                        e contadores de erro do rádio) num log dedicado
                        (~/.local/state/hefesto-dualsense4unix/kernel.log;
                        compat: storm.log). Sem sudo, replicável, simétrico.
  --with-storm-watch    [DEPRECATED] no-op — o kernel-watch (sucessor) já é
                        DEFAULT; mantida por compatibilidade.
  --no-proton-pin       OPT-OUT do Proton pinado (DEFAULT ON): o install
                        garante a versão de Proton VALIDADA (assets/
                        proton-pin.conf, SHA256 obrigatório, cache offline em
                        ~/.cache/hefesto-dualsense4unix/proton) e TRAVA o
                        default global + os jogos instalados nela
                        (CompatToolMapping; exige Steam fechada, com backup).
                        Sem o pin, um upgrade de Proton pode reintroduzir o
                        controle duplicado (semântica winebus mudou no 10).
  (DEFAULT) plataforma: regras udev 81 (controles/adaptadores BT e hosts USB
                        sem economia de energia), modprobe.d do btusb
                        (enable_autosuspend=0), FastConnectable do BlueZ
                        (SEM restart do bluetoothd) e cmdline gerenciado
                        (usbcore.autosuspend/usbcore.quirks com MERGE e
                        registro de dono). --no-udev pula os que tocam /etc.
  (DEFAULT) broker root hide-hidraw (fd-injection): passo
                        3h — esconde o hidraw FÍSICO do DualSense do JOGO
                        (cura de raiz do controle duplicado) via broker de
                        SISTEMA socket-activated; serve fd O_RDWR ao daemon
                        via SCM_RIGHTS (cmd `open`) para o giroscópio nunca
                        morrer, mesmo com o nó escondido. PRIMEIRO serviço de
                        SISTEMA (systemd system, não --user) do projeto. Sem
                        flag de opt-out ainda (broker ausente/recusado
                        degrada para o comportamento de hoje — duplicado,
                        nunca zero controles). Vale para TODO formato
                        (native/flatpak/appimage/deb).
                        --no-udev pula (mesmo gate dos passos de plataforma).
  (DEFAULT) DKMS hid-nintendo corrigido (cura de raiz do probe BT
                        que mata o Pro Controller/8BitDo em silêncio, sem
                        re-probar): módulo out-of-tree via DKMS
                        (assets/dkms/hid-nintendo/) que substitui o in-tree
                        (vence por precedência updates/dkms; NUNCA remove o
                        in-tree). Defaults do patch == comportamento vanilla;
                        a cura (retry de probe em BT) entra pela conf
                        /etc/modprobe.d/hefesto-hid-nintendo.conf
                        (bt_probe_retries=3). Fail-safe total: dkms/headers
                        ausentes ou build falho = aviso honesto, o in-tree
                        segue valendo, o install NUNCA aborta. Ativação
                        NUNCA recarrega um módulo já carregado (derrubaria
                        controles em uso) — vale no próximo boot/replug se
                        o módulo estiver descarregado. Vale para TODO
                        formato. Opt-out: --no-dkms (CI/sem hardware/kernel
                        sem headers, como --no-udev; desliga AMBOS os
                        módulos DKMS — hid-nintendo e rtw88_usb, abaixo).
  (DEFAULT) DKMS rtw88_usb corrigido (cura de raiz do fantasma USB
                        do dongle WiFi/RTL8822BU: quando um port-status-change
                        se perde no xHCI, o driver in-tree nunca detecta que o
                        device sumiu e segue tentando I/O contra hardware
                        ausente — só unbind manual ou reboot recicla o device,
                        medido 13h de fantasma em 20/07): módulo out-of-tree
                        via DKMS (assets/dkms/rtw88-usb/) que substitui o
                        in-tree (vence por precedência updates/dkms; NUNCA
                        remove o in-tree). Detecta -ENODEV/-ESHUTDOWN
                        (device sumiu de verdade) ou 5 -EPROTO consecutivos
                        sem NENHUM sucesso no meio (zera a cada sucesso) e
                        enfileira usb_queue_reset_device — gate: module
                        param hang_reset (default Y; N desliga só o reset,
                        a detecção/silenciamento continua). Fail-safe
                        total: dkms/headers ausentes, kernel fora do pino
                        BUILD_EXCLUSIVE_KERNEL (ABI privada do rtw88) ou
                        build falho = aviso honesto, o in-tree segue
                        valendo, o install NUNCA aborta. Ativação NUNCA
                        recarrega um módulo já carregado (derrubaria o
                        WiFi ao vivo) — vale no próximo boot/replug do
                        dongle. Vale para TODO formato. Opt-out: --no-dkms
                        (mesma flag do hid-nintendo, acima).
  (DEFAULT) vigia do dongle Wi-Fi USB: o scan de fundo do
                        wpa_supplicant sai a cada associação (derrubava o
                        dongle de 300 em 300 s) e um vigia de minuto em
                        minuto reinicia a porta USB quando o rádio trava
                        MUDO (associado e o roteador sem ping nem ARP por
                        3 min; freios: um reinício a cada 10 min, e para
                        depois de 3 sem cura). Vale para qualquer Wi-Fi USB;
                        sem dongle, fica armado e não faz nada. Vai em
                        /usr/local/lib/hefesto-dualsense4unix/wifi_usb.sh, no
                        dispatcher do NetworkManager (90-hefesto-wifi-usb) e
                        no hefesto-wifi-usb-vigia.timer. Vale para TODO
                        formato. --no-udev também pula.
  --no-wifi-usb         OPT-OUT do vigia do Wi-Fi USB (acima).
  --desempenho          responde SIM, sem perguntar, ao modo desempenho: o
                        perfil de energia fica em Performance a cada boot (unit
                        hefesto-desempenho.service, para o system76-power ou o
                        power-profiles-daemon). Cada ajuste é um arquivo
                        permanente; o uninstall desfaz e o doctor diz o estado
                        de cada um. O que a máquina não tem é pulado e dito.
                        Sem a flag o install PERGUNTA; sem TTY (--yes) vale o
                        padrão: sim no desktop, não no notebook (com bateria).
                        --no-udev também pula.
  --sem-desempenho      responde NÃO ao modo desempenho, sem perguntar. Não
                        escreve nada.
  --wifi-powersave-off  aceita, sem efeito a mais: desligar a economia de energia
                        do Wi-Fi (conf.d do NetworkManager, wifi.powersave=2, e
                        `iw dev <if> set power_save off` na hora) é o padrão em
                        toda máquina com Wi-Fi (passo 3d-bis). NUNCA reconecta a
                        rede para aplicar. --no-udev pula. uninstall.sh remove.
  --yes, -y             responde sim a todos os prompts (autostart, hotplug,
                        AppIndicator extension, etc) e assume --format=native.
  --no-systemd          pula a unit do daemon por INTEIRO (passo 6 E passo 7a):
                        nada é copiado, nada é habilitado, nada sobe.
  --no-hotplug-gui      pula a cópia da unit hotplug-gui.
  --enable-autostart    habilita auto-start do daemon no boot (pula prompt).
  --enable-hotplug-gui  abre a janela no início da sessão gráfica (pula prompt).
  --enable-cosmic-applet  compila+instala o applet COSMIC nativo (Rust).
                        APOSENTADO: o ícone da bandeja faz
                        o mesmo, aparece sozinho e tem menu mais rico. Sem
                        esta flag o applet NÃO é instalado em máquina alguma.
                        (a 1a build do libcosmic e longa, >10 min; requer
                        cargo+just — se ausentes, o install NÃO falha.)
  --no-cosmic-applet    aceita e não faz nada: o default já é não instalar.
                        Fica para não quebrar quem a tenha num script.
  --dev                 cria o venv COM o extra [dev] (ruff/mypy/pytest), para
                        quem vai mexer no código. Por DEFAULT o venv vem só
                        com o que o produto usa: a primeira instalação de
                        quem só usa não baixa ferramenta de desenvolvimento.
  --no-dev              aceita e não faz nada: o default já é sem [dev]. Fica
                        para não quebrar quem a tenha num script.
  --no-fonts            pula as fontes da identidade visual (Space Grotesk +
                        JetBrains Mono, que a interface pede). Por DEFAULT
                        elas são instaladas em best-effort pelo
                        scripts/install_fonts.sh — pacote da distro primeiro,
                        download PINADO + SHA-256 só se não houver pacote.
                        Nada quebra sem elas (o CSS tem fallback); o que muda é
                        a interface ser a do design e as medidas de texto
                        baterem com as do mockup.
  (DEFAULT) teclado na tela — o que o L3 do controle abre. Instalado em TODO
                        formato pelo scripts/install_osk.sh, que escolhe pela
                        SESSÃO: em Wayland o `wvkbd` (binário wvkbd-mobintl,
                        cliente Wayland puro, digita pelo
                        zwp_virtual_keyboard_manager_v1 que o cosmic-comp
                        expõe — medido); em X11 o `onboard` (GTK3, digita por
                        XTEST, que em Wayland só alcança janelas XWayland).
                        Importa porque nenhum dos nove atalhos de fábrica
                        digita uma LETRA: sem isto, "o teclado emulado não
                        digita" é literalmente verdade. Best-effort (o install
                        nunca aborta por causa dele) e o passo GRAVA o que fez
                        em ~/.local/state/hefesto-dualsense4unix/
                        teclado-na-tela.conf, para o doctor distinguir "ela não
                        quis" de "o install não instalou". Opt-out: --no-osk.
  --no-osk              pula o teclado na tela. O L3 do controle passa a só
                        avisar na tela que não tem o que abrir.
  (DEFAULT) cura gentil do WirePlumber: REBAIXA o DualSense para não virar o
                        microfone padrão (drop-in 51, user-space) — simétrica com o
                        uninstall que a remove. Opt-out: --keep-dualsense-mic.
  --keep-dualsense-mic  NÃO rebaixa o DualSense (deixa-o elegível como mic padrão).
  --with-wireplumber-fix  redundante (já é o default); mantida para compat.
  --with-wireplumber-disable-mic  DESABILITA de vez a source (mic) do DualSense
  --no-doctor           pula a CONFERÊNCIA final. Por padrão o install roda o
                        doctor no fim e mostra o veredito: uma instalação que
                        termina com cura desarmada tem de DIZER isso.
                        (node.disabled; controle vira só-HID). Vence até escassez
                        de fonte. Mutuamente exclusiva com --with-wireplumber-fix.
  --keep-steam-input    preserva Steam Input PSSupport (default: desliga).
                        Sem esta flag, o install zera SteamController_PSSupport
                        e UseSteamControllerConfig em TODOS os localconfig.vdf
                        (todos os Steam users em qualquer formato: deb/flatpak/
                        snap), evitando que a Steam intercepte o DualSense e
                        entre em conflito com o daemon. Reverte com:
                        scripts/disable_steam_input.sh --restore.
  --force-xwayland      grava GDK_BACKEND=x11 no .desktop. Escape
                        declarado (sessão sem Wayland, compositor que não
                        desenhe bem o WebKit); o default é Wayland nativo.

Default (sem flag nenhuma): a unit do daemon é COPIADA, HABILITADA no boot e
SOBE na hora. Quem manda é a sua resposta ao passo 6 ("habilitar auto-start do
daemon no boot?", default sim): responder "não" copia a unit e NÃO habilita
nem sobe o daemon; --no-systemd pula os dois passos (6 e 7a) por inteiro.
Hotplug-GUI continua opt-in (prompt com default NÃO).
udev rules SÃO aplicadas (incondicional desde v3.3.1 — sem elas o controle
não funciona em nenhum formato).

Reexecutável (idempotente).
AJUDA
}

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
WITH_DEV=0
NO_FONTS=0
NO_OSK=0
WITH_WIREPLUMBER_FIX=1
WITH_WIREPLUMBER_DISABLE_MIC=0
WITH_USB_QUIRK=0
NO_DKMS=0
COM_UHID_CONTRAPRESSAO=0
SKIP_KERNEL_WATCH=0
NO_PROTON_PIN=0
SKIP_SND_QUIRK=0
NO_UCM=0
ABRIR_O_NO=0
KEEP_STEAM_INPUT=0
RUN_DOCTOR=1
FORCE_XWAYLAND=0
NO_WIFI_USB=0
DESEMPENHO_PEDIDO=""
DESEMPENHO_PROVADOS=""
AUTO_YES=0
DRY_RUN=0
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
        --dev)                WITH_DEV=1 ;;
        --no-dev)             WITH_DEV=0 ;;
        --no-fonts)           NO_FONTS=1 ;;
        --no-osk)             NO_OSK=1 ;;
        --with-wireplumber-fix) WITH_WIREPLUMBER_FIX=1 ;;
        --keep-dualsense-mic) WITH_WIREPLUMBER_FIX=0 ;;
        --no-doctor) RUN_DOCTOR=0 ;;
        --with-wireplumber-disable-mic) WITH_WIREPLUMBER_DISABLE_MIC=1 ;;
        --with-usb-quirk)     WITH_USB_QUIRK=1 ;;
        --no-dkms)            NO_DKMS=1 ;;
        --uhid-contrapressao) COM_UHID_CONTRAPRESSAO=1 ;;
        --no-snd-quirk)       SKIP_SND_QUIRK=1 ;;
        --no-ucm)             NO_UCM=1 ;;
        --no-fechar-o-no)     ABRIR_O_NO=1 ;;
        --no-kernel-watch)    SKIP_KERNEL_WATCH=1 ;;
        --with-storm-watch)   : ;;
        --no-proton-pin)      NO_PROTON_PIN=1 ;;
        --keep-steam-input)   KEEP_STEAM_INPUT=1 ;;
        --wifi-powersave-off) : ;;
        --no-wifi-usb)        NO_WIFI_USB=1 ;;
        --desempenho)         DESEMPENHO_PEDIDO="sim" ;;
        --sem-desempenho)     DESEMPENHO_PEDIDO="sem" ;;
        --force-xwayland)     FORCE_XWAYLAND=1 ;;
        --format=*)           FORMAT="${arg#*=}" ;;
        --native)             FORMAT="native" ;;
        --flatpak)            FORMAT="flatpak" ;;
        --appimage)           FORMAT="appimage" ;;
        --deb)                FORMAT="deb" ;;
        --yes|-y)             AUTO_YES=1 ;;
        --dry-run|-n)         DRY_RUN=1 ;;
        -h|--help)
            _ajuda
            exit 0
            ;;
        *)
            printf 'argumento desconhecido: %s\n' "$arg" >&2
            printf 'nada foi instalado. Use --help para ver as opções.\n' >&2
            exit 2
            ;;
    esac
done

case "${FORMAT}" in
    ""|native|flatpak|appimage|deb) ;;
    *) printf 'ERRO: formato inválido: %s (use native|flatpak|appimage|deb)\n' "${FORMAT}" >&2; exit 2 ;;
esac

DESKTOP_IS_COSMIC=0
if [[ "${XDG_CURRENT_DESKTOP:-}${XDG_SESSION_DESKTOP:-}" == *[Cc][Oo][Ss][Mm][Ii][Cc]* ]]; then
    DESKTOP_IS_COSMIC=1
fi
DESKTOP_IS_WLROOTS=0
case "${XDG_CURRENT_DESKTOP:-}:${XDG_SESSION_DESKTOP:-}" in
    *[Ss][Ww][Aa][Yy]*|*[Hh][Yy][Pp][Rr][Ll][Aa][Nn][Dd]*|*[Nn][Ii][Rr][Ii]*|*[Rr][Ii][Vv][Ee][Rr]*)
        DESKTOP_IS_WLROOTS=1 ;;
esac

step()  { printf '\n[%s] %s\n' "$1" "$2"; }
ok()    { printf '      ok\n'; }
warn()  { printf '      aviso: %s\n' "$*"; }
die()   { printf '\nERRO: %s\n' "$*" >&2; exit 1; }

_ENSAIO_MUDANCAS=0
_ENSAIO_ROOT=0

_faria() {
    _ENSAIO_MUDANCAS=$((_ENSAIO_MUDANCAS + 1))
    printf '      FARIA        %s\n' "$*"
}

_faria_root() {
    _ENSAIO_MUDANCAS=$((_ENSAIO_MUDANCAS + 1))
    _ENSAIO_ROOT=$((_ENSAIO_ROOT + 1))
    printf '      FARIA (root) %s\n' "$*"
}

_nao_faria() { printf '      não faria:   %s\n' "$*"; }

_ensaio_resumo() {
    printf '\n'
    printf '═════════════════════════════════════════════════════════════════\n'
    printf ' FIM DO ENSAIO — NADA foi escrito, instalado, habilitado ou reiniciado\n'
    printf '═════════════════════════════════════════════════════════════════\n'
    printf ' %d mudanças planejadas, %d delas com root.\n' \
        "${_ENSAIO_MUDANCAS}" "${_ENSAIO_ROOT}"
    printf ' Para fazer de verdade, é a MESMA linha de comando sem o --dry-run.\n'
    printf ' Para desfazer depois:  ./uninstall.sh\n'
    printf '═════════════════════════════════════════════════════════════════\n\n'
}

ask_yn() {
    local prompt="$1" auto="$2" default="${3:-y}"
    if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
        REPLY="$default"
        printf '      perguntaria: "%s" — no ensaio assumo "%s"\n' "${prompt}" "${default}"
        return
    fi
    if [[ "$auto" -eq 1 ]]; then
        REPLY="$default"; return
    fi
    if [[ ! -t 0 ]]; then
        REPLY="$default"; return
    fi
    local indicator
    if [[ "$default" == "y" ]]; then indicator="[Y/n]"; else indicator="[y/N]"; fi
    read -r -n 1 -p "      $prompt $indicator " REPLY || REPLY="$default"
    echo
    REPLY="${REPLY:-$default}"
}

_OS_RELEASE="${HEFESTO_OS_RELEASE:-/etc/os-release}"

_familia_pacotes() {
    if [[ -n "${HEFESTO_FAMILIA_PACOTES:-}" ]]; then
        printf '%s\n' "${HEFESTO_FAMILIA_PACOTES}"
        return 0
    fi
    if [[ -e "${HEFESTO_OSTREE_MARCA:-/run/ostree-booted}" ]]; then
        printf 'imutavel\n'
        return 0
    fi
    if command -v steamos-readonly >/dev/null 2>&1 \
        && [[ "$(steamos-readonly status 2>/dev/null | tr -d '[:space:]' | tr 'A-Z' 'a-z')" == "enabled" ]]; then
        printf 'imutavel\n'
        return 0
    fi
    local _id="" _id_like="" _token
    if [[ -r "${_OS_RELEASE}" ]]; then
        _id="$(sed -n 's/^ID=//p' "${_OS_RELEASE}" | tr -d '"' | head -1)"
        _id_like="$(sed -n 's/^ID_LIKE=//p' "${_OS_RELEASE}" | tr -d '"' | head -1)"
    fi
    # shellcheck disable=SC2086
    for _token in ${_id} ${_id_like}; do
        case "${_token}" in
            debian|ubuntu|linuxmint|pop|raspbian|devuan)  printf 'apt\n';    return 0 ;;
            fedora|rhel|centos|almalinux|rocky|nobara)    printf 'dnf\n';    return 0 ;;
            arch|archlinux|manjaro|endeavouros|cachyos)   printf 'pacman\n'; return 0 ;;
        esac
    done
    command -v apt-get >/dev/null 2>&1 && { printf 'apt\n';    return 0; }
    command -v dnf     >/dev/null 2>&1 && { printf 'dnf\n';    return 0; }
    command -v pacman  >/dev/null 2>&1 && { printf 'pacman\n'; return 0; }
    printf 'nenhum\n'
}

_pkg_nome() {
    local _canon="$1" _familia="${2:-}"
    [[ -z "${_familia}" ]] && _familia="$(_familia_pacotes)"
    local _apt="" _dnf="" _pacman=""
    case "${_canon}" in
        hidapi)
            _apt="libhidapi-hidraw0"; _dnf="hidapi"
            _pacman="hidapi" ;;
        svg-loader)
            _apt="librsvg2-common";   _dnf="librsvg2"
            _pacman="librsvg" ;;
        python-venv)
            _apt="python3-venv";      _dnf="python3-libs"
            _pacman="python" ;;
        toolchain-c)
            _apt="build-essential python3-dev linux-libc-dev"
            _dnf="gcc python3-devel kernel-headers"
            _pacman="gcc linux-api-headers" ;;
        python-gi)
            _apt="python3-gi";        _dnf="python3-gobject"
            _pacman="python-gobject" ;;
        python-gi-cairo)
            _apt="python3-gi-cairo";  _dnf="python3-cairo"
            _pacman="python-cairo" ;;
        gtk3)
            _apt="gir1.2-gtk-3.0";    _dnf="gtk3"
            _pacman="gtk3" ;;
        appindicator)
            _apt="gir1.2-ayatanaappindicator3-0.1"
            _dnf="libayatana-appindicator-gtk3"
            _pacman="libayatana-appindicator" ;;
        webkit2gtk)
            _apt="gir1.2-webkit2-4.1"; _dnf="webkit2gtk4.1"
            _pacman="webkit2gtk-4.1" ;;
        gi-dev)
            _apt="libgirepository1.0-dev libcairo2-dev"
            _dnf="gobject-introspection-devel cairo-devel"
            _pacman="gobject-introspection cairo" ;;
        desktop-utils)
            _apt="desktop-file-utils libgtk-3-bin"
            _dnf="desktop-file-utils gtk-update-icon-cache"
            _pacman="desktop-file-utils gtk-update-icon-cache" ;;
        imagemagick)
            _apt="imagemagick";       _dnf="ImageMagick"
            _pacman="imagemagick" ;;
        opus)
            _apt="libopus0";          _dnf="opus"
            _pacman="opus" ;;
        pactl)
            _apt="pulseaudio-utils";  _dnf="pulseaudio-utils"
            _pacman="libpulse" ;;
        alsa-ucm)
            _apt="alsa-ucm-conf";     _dnf="alsa-ucm"
            _pacman="alsa-ucm-conf" ;;
        bluez)
            _apt="bluez";             _dnf="bluez"
            _pacman="bluez bluez-utils" ;;
        bt-agent)
            _apt="bluez-tools";       _dnf=""
            _pacman="bluez-tools" ;;
        wlrctl)
            _apt="wlrctl";            _dnf="wlrctl"
            _pacman="wlrctl" ;;
        usbutils)
            _apt="usbutils";          _dnf="usbutils"
            _pacman="usbutils" ;;
        fontconfig)
            _apt="fontconfig";        _dnf="fontconfig"
            _pacman="fontconfig" ;;
        curl)
            _apt="curl";              _dnf="curl"
            _pacman="curl" ;;
        dkms)
            _apt="dkms";              _dnf="dkms"
            _pacman="dkms" ;;
        compilador)
            _apt="build-essential";   _dnf="gcc make"
            _pacman="base-devel" ;;
        kernel-headers)
            _apt="linux-headers-$(uname -r)"; _dnf="kernel-devel"
            _pacman="linux-headers" ;;
    esac
    case "${_familia}" in
        apt)    printf '%s\n' "${_apt}" ;;
        dnf)    printf '%s\n' "${_dnf}" ;;
        pacman) printf '%s\n' "${_pacman}" ;;
        *)      printf '%s\n' "" ;;
    esac
}

_run_pkg_quieto() {
    local _tmp
    _tmp="$(mktemp)"
    if ! "$@" > "$_tmp" 2>&1; then
        cat "$_tmp" >&2
        rm -f "$_tmp"
        return 1
    fi
    rm -f "$_tmp"
}

readonly _RC_PACOTE_A_MEIO=75
_PACOTES_A_MEIO_LISTA=""
_pacotes_a_meio() {
    command -v dpkg-query >/dev/null 2>&1 || return 0
    dpkg-query -W -f='${db:Status-Abbrev} ${Package}\n' 2>/dev/null \
        | awk 'substr($1, 2, 1) ~ /[HUF]/ || substr($1, 3, 1) == "R" { printf "%s%s", (n++ ? " " : ""), $2 }
               END { if (n) printf "\n" }' || true
}

_avisa_pacote_a_meio() {
    local _meio="${2-}"
    [[ -n "${_meio}" ]] || _meio="$(_pacotes_a_meio)"
    [[ -n "${_meio}" ]] || return 1
    if [[ "${_PACOTE_A_MEIO_DITO:-0}" -eq 0 ]]; then
        _PACOTE_A_MEIO_DITO=1
        warn "o sistema tem pacote a meio de uma atualização (${_meio}) — isso é do sistema, não do Hefesto; não chamei o apt, que tentaria reconfigurá-lo e falharia de novo"
        printf '      para consertar o sistema:   sudo apt-get install -f   (ou: sudo dpkg --configure -a)\n'
    else
        warn "o sistema segue com pacote a meio — não instalei $1"
    fi
    return 0
}

_pids_da_trava() {
    local _st _dev _ino _chave
    [[ -r /proc/locks ]] || return 0
    _st="$(stat -L -c '%d %i' "$1" 2>/dev/null)" || return 0
    _dev="${_st% *}"
    _ino="${_st#* }"
    _chave="$(printf '%02x:%02x:%s' $(( (_dev >> 8) & 0xfff )) \
        $(( (_dev & 0xff) | ((_dev >> 12) & 0xfff00) )) "${_ino}")"
    awk -v k="${_chave}" '$2 != "->" { for (i = 2; i <= NF; i++) if ($i == k) { print $(i - 1); break } }' \
        /proc/locks 2>/dev/null | sort -u || true
}

_quem_segura_a_trava() {
    local _pid _nome _quem=""
    for _pid in $( { _pids_da_trava "$1"; fuser "$1" 2>/dev/null; } | tr -s ' ' '\n' | sort -un || true); do
        [[ "${_pid}" =~ ^[0-9]+$ ]] || continue
        _nome="$(ps -o comm= -p "${_pid}" 2>/dev/null || true)"
        _quem="${_quem}${_quem:+, }${_nome:-?} (pid ${_pid})"
    done
    [[ -z "${_quem}" ]] || printf '%s\n' "${_quem}"
    return 0
}

_trava_ocupada() {
    local _arq="$1" _modo="$2"
    [[ -e "${_arq}" ]] || return 1
    [[ "${_modo}" == "existe" ]] && return 0
    [[ -z "$(_pids_da_trava "${_arq}")" ]] || return 0
    if command -v fuser >/dev/null 2>&1 && fuser -s "${_arq}" 2>/dev/null; then
        return 0
    fi
    if command -v flock >/dev/null 2>&1 && ! flock -n "${_arq}" true 2>/dev/null; then
        return 0
    fi
    return 1
}

_esperar_trava() {
    local _teto="${HEFESTO_TRAVA_TETO:-120}" _seg=0 _quem
    _trava_ocupada "$@" || return 0
    printf '      outro gerenciador de pacotes está em uso — esperando até %ss...\n' "${_teto}"
    while _trava_ocupada "$@"; do
        if (( _seg >= _teto )); then
            _quem="$(_quem_segura_a_trava "$1")"
            warn "o gerenciador de pacotes seguiu ocupado por ${_teto}s (trava ${1}${_quem:+, segurada por ${_quem}}) — não instalei"
            return 1
        fi
        sleep 1
        _seg=$((_seg + 1))
    done
}

run_apt() {
    local _quem
    if ! _run_pkg_quieto sudo apt-get install -y -qq \
            -o "DPkg::Lock::Timeout=${HEFESTO_TRAVA_TETO:-120}" "$@"; then
        _quem="$(_quem_segura_a_trava "${HEFESTO_TRAVA_DPKG:-/var/lib/dpkg/lock-frontend}")"
        [[ -z "${_quem}" ]] || warn "o dpkg está ocupado por ${_quem}"
        return 1
    fi
}

run_pkg() {
    local _familia _canon _nome _parte
    local _nomes=()
    _familia="$(_familia_pacotes)"
    if [[ "${_familia}" == "imutavel" ]]; then
        if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
            _nao_faria "instalar pacote(s) $*: a distro é somente leitura e não há gerente de pacotes a chamar"
            return 0
        fi
        warn "distro somente leitura — não instalei $*: a imagem do sistema não aceita pacote solto"
        return 1
    fi
    for _canon in "$@"; do
        _nome="$(_pkg_nome "${_canon}" "${_familia}")"
        if [[ -z "${_nome}" ]]; then
            warn "não tenho nome de pacote para '${_canon}' em ${_familia} — instale o equivalente pela sua distro"
            return 1
        fi
        # shellcheck disable=SC2086
        for _parte in ${_nome}; do _nomes+=("${_parte}"); done
    done
    (( ${#_nomes[@]} )) || return 1
    if [[ "${_familia}" == "apt" ]]; then
        local _meio
        _meio="$(_pacotes_a_meio)"
        if [[ -n "${_meio}" ]]; then
            if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
                _nao_faria "instalar pacote(s) ${_nomes[*]}: o sistema tem pacote a meio (${_meio})"
                return 0
            fi
            _avisa_pacote_a_meio "${_nomes[*]}" "${_meio}"
            printf '      depois, para instalar o que o Hefesto pede:   %s\n' "$(comando_manual_pkg "$@")"
            _PACOTES_A_MEIO_LISTA="${_meio}"
            return "${_RC_PACOTE_A_MEIO}"
        fi
    fi
    if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
        _faria_root "instalar pacote(s) com ${_familia}: ${_nomes[*]}"
        return 0
    fi
    if ! command -v sudo >/dev/null 2>&1; then
        warn "sudo ausente — não consigo instalar ${_nomes[*]}"
        return 1
    fi
    case "${_familia}" in
        apt)    run_apt "${_nomes[@]}" ;;
        dnf)
            _esperar_trava "${HEFESTO_TRAVA_DNF:-/var/lib/rpm/.rpm.lock}" flock || return 1
            _run_pkg_quieto sudo dnf install -y "${_nomes[@]}" ;;
        pacman)
            _esperar_trava "${HEFESTO_TRAVA_PACMAN:-/var/lib/pacman/db.lck}" existe || return 1
            _run_pkg_quieto sudo pacman -S --noconfirm --needed "${_nomes[@]}" ;;
        *)      warn "sem gerenciador de pacotes conhecido — não instalei ${*}"; return 1 ;;
    esac
}

comando_manual_pkg() {
    local _familia _canon _nome _lista=""
    _familia="$(_familia_pacotes)"
    for _canon in "$@"; do
        _nome="$(_pkg_nome "${_canon}" "${_familia}")"
        [[ -z "${_nome}" ]] && _nome="$(_pkg_nome "${_canon}" apt)"
        [[ -z "${_nome}" ]] && _nome="${_canon}"
        _lista="${_lista}${_lista:+ }${_nome}"
    done
    case "${_familia}" in
        apt)    printf 'sudo apt install %s\n' "${_lista}" ;;
        dnf)    printf 'sudo dnf install %s\n' "${_lista}" ;;
        pacman) printf 'sudo pacman -S %s\n' "${_lista}" ;;
        imutavel) printf 'peça à imagem do sistema o equivalente a: %s\n' "${_lista}" ;;
        *)      printf 'instale pela sua distro o equivalente a: %s\n' "${_lista}" ;;
    esac
}

_DEPS_DE_SISTEMA=(
    "hidapi|obrigatoria|lib:libhidapi-hidraw.so.0,libhidapi-libusb.so.0|o backend do controle não abre NENHUM aparelho (o pydualsense faz dlopen da libhidapi; a wheel do pip não traz o .so)"
    "svg-loader|obrigatoria|svg|o ícone da bandeja some"
    "toolchain-c|importante|toolchain|as extensões sem wheel (python-uinput, evdev) não compilam e o passo 2 pode abortar"
    "appindicator|importante|appindicator|a bandeja não nasce: a janela abre, o ícone ao lado do relógio não"
    "webkit2gtk|obrigatoria|webkit|a interface não abre: o serviço sobe, mas a janela morre com «Namespace WebKit2 not available»"
    "desktop-utils|importante|cmd:desktop-file-validate,update-desktop-database,gtk-update-icon-cache|o atalho e o ícone podem não aparecer no menu do sistema"
    "imagemagick|importante|cmd:convert|o ícone fica só no 256x256, sem as resoluções menores"
    "pactl|importante|cmd:pactl,parec|a luz do microfone do controle fica apagada para sempre: sem o pactl ninguém sabe QUEM está ouvindo, sem o parec ninguém sabe se está entrando som — e o microfone por Bluetooth também não sobe"
    "alsa-ucm|importante|arquivo:/usr/share/alsa/ucm2/ucm.conf|a vibração dos jogos da Sony pelo DualSense no cabo não chega: sem o UCM do sistema a placa do controle não abre pelo perfil HiFi"
    "bluez|importante|cmd:bluetoothctl,btmgmt|parear pelo rádio, conferir o bond e o diagnóstico de Bluetooth param de funcionar"
    "usbutils|importante|cmd:lsusb|o diagnóstico perde a leitura do barramento USB"
    "fontconfig|importante|cmd:fc-cache|a interface troca de fonte em silêncio (Space Grotesk e JetBrains Mono não entram)"
    "curl|importante|cmd:curl|as fontes da identidade visual não são baixadas"
)

_dep_presente() {
    local _checagem="$1" _bin _inc _saida _py_gi="${VENV_DIR}/bin/python"
    [[ -x "${_py_gi}" ]] || _py_gi="${_VENV_PYTHON:-python3}"
    case "${_checagem}" in
        lib:*)
            local _sos="${_checagem#lib:}" _so
            # shellcheck disable=SC2086
            for _so in ${_sos//,/ }; do
                if [[ -x "${VENV_DIR}/bin/python" ]]; then
                    "${VENV_DIR}/bin/python" -c \
                        "import ctypes,sys; sys.exit(0 if ctypes.CDLL('${_so}') else 1)" \
                        >/dev/null 2>&1 && return 0
                    continue
                fi
                break
            done
            if [[ -x "${VENV_DIR}/bin/python" ]]; then
                return 1
            fi
            local _ldconfig=""
            for _bin in /usr/sbin/ldconfig /sbin/ldconfig ldconfig; do
                command -v "${_bin}" >/dev/null 2>&1 && { _ldconfig="${_bin}"; break; }
            done
            [[ -z "${_ldconfig}" ]] && return 1
            _saida="$("${_ldconfig}" -p 2>/dev/null || true)"
            [[ "${_saida}" == *"${_so}"* ]]
            ;;
        cmd:*)
            local _bins="${_checagem#cmd:}"
            # shellcheck disable=SC2086
            for _bin in ${_bins//,/ }; do
                command -v "${_bin}" >/dev/null 2>&1 || return 1
            done
            return 0
            ;;
        arquivo:*)
            [[ -f "${_checagem#arquivo:}" ]]
            ;;
        svg)
            "${_py_gi}" -c "import gi;gi.require_version('GdkPixbuf','2.0');from gi.repository import GdkPixbuf;import sys;sys.exit(0 if any(f.get_name()=='svg' for f in GdkPixbuf.Pixbuf.get_formats()) else 1)" >/dev/null 2>&1
            ;;
        appindicator)
            "${_py_gi}" -c "import gi;gi.require_version('AyatanaAppIndicator3','0.1')" >/dev/null 2>&1 ||
            "${_py_gi}" -c "import gi;gi.require_version('AppIndicator3','0.1')" >/dev/null 2>&1
            ;;
        webkit)
            "${_py_gi}" -c "import gi;gi.require_version('WebKit2','4.1');from gi.repository import WebKit2;WebKit2.get_major_version()" >/dev/null 2>&1
            ;;
        toolchain)
            command -v cc >/dev/null 2>&1 || return 1
            [[ -f /usr/include/linux/input.h ]] || return 1
            _inc="$("${_VENV_PYTHON:-python3}" -c \
                'import sysconfig;print(sysconfig.get_paths()["include"])' 2>/dev/null)"
            [[ -n "${_inc}" && -f "${_inc}/Python.h" ]]
            ;;
        *)
            return 0
            ;;
    esac
}

_garantir_deps_de_sistema() {
    local _familia _linha _canon _crit _checagem _razao
    local _obrig=() _import=() _ainda=()
    _familia="$(_familia_pacotes)"

    for _linha in "${_DEPS_DE_SISTEMA[@]}"; do
        IFS='|' read -r _canon _crit _checagem _razao <<< "${_linha}"
        _dep_presente "${_checagem}" && continue
        printf '      falta %s — sem ele, %s\n' "${_canon}" "${_razao}"
        if [[ "${_crit}" == "obrigatoria" ]]; then
            _obrig+=("${_canon}")
        else
            _import+=("${_canon}")
        fi
    done
    (( ${#_obrig[@]} + ${#_import[@]} )) || return 0

    if [[ "${_familia}" == "nenhum" || "${_familia}" == "imutavel" ]]; then
        if [[ "${_familia}" == "imutavel" ]]; then
            warn "distro somente leitura — não instalei nada: o que falta tem de vir da imagem do sistema"
            printf '      Peça-o pela camada de pacotes da sua distro (nome no Debian/Ubuntu como referência):\n'
        else
            warn "não reconheço o gerenciador de pacotes desta distro — não instalei nada"
            printf '      Instale o equivalente na sua distro (nome no Debian/Ubuntu como referência):\n'
        fi
        for _canon in ${_obrig[@]+"${_obrig[@]}"} ${_import[@]+"${_import[@]}"}; do
            printf '        %-14s %s\n' "${_canon}" "$(_pkg_nome "${_canon}" apt)"
        done
        return 0
    fi

    if (( ${#_obrig[@]} )); then
        printf '\n      Obrigatórias — sem elas o produto não funciona: %s\n' "${_obrig[*]}"
        ask_yn "instalar agora com sudo?" "${AUTO_YES}" "y"
        if [[ "${REPLY,,}" =~ ^y ]]; then
            run_pkg ${_obrig[@]+"${_obrig[@]}"} || true
        fi
        if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
            printf '      (ensaio: depois de instaladas, as obrigatórias seriam RECONFERIDAS pelo\n'
            printf '       efeito — a biblioteca abre? o gdk-pixbuf lê SVG? — e o install morreria\n'
            printf '       aqui se alguma continuasse faltando)\n'
        else
        for _linha in "${_DEPS_DE_SISTEMA[@]}"; do
            IFS='|' read -r _canon _crit _checagem _razao <<< "${_linha}"
            [[ "${_crit}" == "obrigatoria" ]] || continue
            _dep_presente "${_checagem}" || _ainda+=("${_canon}")
        done
        if (( ${#_ainda[@]} )); then
            printf '      rode: %s\n' "$(comando_manual_pkg ${_ainda[@]+"${_ainda[@]}"})"
            die "faltam dependências obrigatórias (${_ainda[*]}) — instale e reexecute ./install.sh"
        fi
        printf '      obrigatórias ok\n'
        fi
    fi

    if (( ${#_import[@]} )); then
        printf '\n      Importantes — cada uma custa uma função: %s\n' "${_import[*]}"
        ask_yn "instalar agora com sudo?" "${AUTO_YES}" "y"
        if [[ "${REPLY,,}" =~ ^y ]] && run_pkg ${_import[@]+"${_import[@]}"}; then
            printf '      importantes ok\n'
        else
            warn "sem ${_import[*]} — as funções acima ficam indisponíveis"
            printf '      quando quiser: %s\n' "$(comando_manual_pkg ${_import[@]+"${_import[@]}"})"
        fi
    fi
}

require() { command -v "$1" >/dev/null 2>&1 || die "dependência ausente: $1"; }

readonly CMDLINE_OWNERS_FILE="${HOME}/.local/state/hefesto-dualsense4unix/cmdline-owners.conf"
_register_cmdline_owner() {
    local key="$1" value="$2" prev=""
    if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
        _faria "gravar o dono do parâmetro de cmdline em ${CMDLINE_OWNERS_FILE}: ${key}=${value}"
        return 0
    fi
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


SUDO_KEEPALIVE_PID=""

_start_sudo_keepalive() {
    [[ -n "${SUDO_KEEPALIVE_PID}" ]] && return 0
    ( while kill -0 "$$" 2>/dev/null; do sudo -n true 2>/dev/null || exit 0; sleep 50; done ) &
    SUDO_KEEPALIVE_PID=$!
}

acquire_sudo() {
    [[ "${EUID:-$(id -u)}" -eq 0 ]] && return 0
    command -v sudo >/dev/null 2>&1 || return 0
    if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
        if sudo -n true 2>/dev/null; then
            printf '\n>>> ENSAIO: há credencial sudo em cache — o plano abaixo é o COMPLETO.\n'
        else
            printf '\n>>> ENSAIO: SEM credencial sudo em cache, e o ensaio não pede senha.\n'
            printf '    Os passos que precisam de root aparecem abaixo como PULADOS — é o que\n'
            printf '    aconteceria AGORA. Num install de verdade você digita a senha uma vez\n'
            printf '    e eles acontecem. Para ver o plano inteiro, sem instalar nada:\n'
            printf '        sudo -v && ./install.sh --dry-run\n'
        fi
        return 0
    fi
    if sudo -n true 2>/dev/null; then
        _start_sudo_keepalive
        return 0
    fi
    [[ "${_NEEDS_SUDO:-1}" -eq 1 ]] || return 0
    if [[ -n "${SUDO_ASKPASS:-}" ]] && sudo -A -v 2>/dev/null; then
        _start_sudo_keepalive
        return 0
    fi
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

if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
    printf '\n'
    printf '═════════════════════════════════════════════════════════════════\n'
    printf ' ENSAIO (--dry-run) — NADA vai ser escrito, instalado ou reiniciado\n'
    printf '═════════════════════════════════════════════════════════════════\n'
    printf ' Cada linha "FARIA" abaixo é uma mudança que um install de verdade\n'
    printf ' faria nesta máquina, com ESTA linha de comando. As marcadas (root)\n'
    printf ' pedem senha. Nenhuma acontece agora.\n'
    printf ' O plano depende das flags: rode com as mesmas que vai usar de verdade.\n'
    printf '═════════════════════════════════════════════════════════════════\n'
fi

if [[ -z "${FORMAT}" ]]; then
    if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
        FORMAT="native"
        printf '\n      perguntaria o formato (1-4) — no ensaio assumo "native" (o default do menu)\n'
    elif [[ "${AUTO_YES}" -eq 1 ]]; then
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

_NEEDS_SUDO=1
if [[ "${SKIP_UDEV}" -eq 1 && "${FORMAT}" != "deb" \
        && "${ENABLE_COSMIC_APPLET}" -eq 0 && "${NO_DKMS}" -eq 1 ]]; then
    _NEEDS_SUDO=0
fi
acquire_sudo

# shellcheck source=scripts/lib/camada_de_maquina.sh
source "${ROOT_DIR}/scripts/lib/camada_de_maquina.sh"
# shellcheck source=scripts/lib/som_da_sessao.sh
source "${ROOT_DIR}/scripts/lib/som_da_sessao.sh"

_ensaio_camada() {
    if _distro_so_leitura; then
        case "$1" in
            dkms-nintendo)    _nao_faria "módulo DKMS hefesto-hid-nintendo (distro somente leitura): $(_efeito_so_leitura nintendo)"; return 0 ;;
            dkms-rtw88)       _nao_faria "módulo DKMS hefesto-rtw88-usb (distro somente leitura): $(_efeito_so_leitura rtw88)"; return 0 ;;
            dkms-playstation) _nao_faria "módulo DKMS hefesto-hid-playstation (distro somente leitura): $(_efeito_so_leitura playstation)"; return 0 ;;
            dkms-uhid)        _nao_faria "uhid com contrapressão (distro somente leitura): $(_efeito_so_leitura uhid)"; return 0 ;;
            dkms-usb-f-hid)   _nao_faria "módulo DKMS hefesto-usb-f-hid (distro somente leitura): $(_efeito_so_leitura usb_f_hid)"; return 0 ;;
            initramfs)        _nao_faria "regenerar o initramfs (distro somente leitura): $(_efeito_so_leitura initramfs)"; return 0 ;;
            ucm)              _nao_faria "perfil UCM do DualSense (distro somente leitura): $(_efeito_so_leitura ucm)"; return 0 ;;
        esac
    fi
    case "$1" in
        udev)
            if [[ "${SKIP_UDEV}" -eq 1 ]]; then
                _nao_faria "regras udev (--no-udev)"
                return 0
            fi
            if [[ "${ABRIR_O_NO:-0}" -eq 1 ]]; then
                _faria_root "copiar as regras udev canônicas de assets/*.rules para /etc/udev/rules.d/ e recarregar o udev (scripts/install_udev.sh) — a regra do nó do DualSense vai ABERTA (--no-fechar-o-no)"
            else
                _faria_root "copiar as regras udev canônicas de assets/*.rules para /etc/udev/rules.d/ e recarregar o udev (scripts/install_udev.sh)"
            fi
            ;;
        osk)
            if [[ "${NO_OSK}" -eq 1 ]]; then
                _nao_faria "teclado na tela do L3 (--no-osk)"
                _faria "gravar a escolha (resultado=pulado) em ${HOME}/.local/state/hefesto-dualsense4unix/teclado-na-tela.conf"
                return 0
            fi
            _faria "instalar o teclado na tela do L3 pelo gerenciador de pacotes: wvkbd em Wayland, onboard em X11 (scripts/install_osk.sh)"
            _faria "gravar o que aconteceu em ${HOME}/.local/state/hefesto-dualsense4unix/teclado-na-tela.conf"
            ;;
        broker)
            if [[ "${SKIP_UDEV}" -eq 1 ]]; then
                _nao_faria "broker hide-hidraw (--no-udev)"
                return 0
            fi
            _faria_root "instalar o broker em /usr/local/lib/hefesto-dualsense4unix/hefesto-hidraw-broker"
            if [[ "${ABRIR_O_NO:-0}" -eq 1 ]]; then
                _faria_root "instalar /etc/systemd/system/hefesto-hidraw-broker.service e .socket (sem uid nem grupo por máquina; o nó nasce ABERTO: --no-fechar-o-no)"
            else
                _faria_root "instalar /etc/systemd/system/hefesto-hidraw-broker.service e .socket (sem uid nem grupo por máquina: atende quem está na frente do computador)"
            fi
            _faria_root "systemctl daemon-reload e enable --now hefesto-hidraw-broker.socket"
            _faria "gravar o registro de posse em ${HOME}/.local/state/hefesto-dualsense4unix/broker-owner.conf"
            ;;
        trava-do-radio)
            if [[ "${SKIP_UDEV}" -eq 1 ]]; then
                _nao_faria "a trava comum do rádio (--no-udev) — o daemon segue com a trava da sessão, que o root não enxerga"
                return 0
            fi
            _faria_root "gravar /etc/tmpfiles.d/hefesto-dualsense4unix-radio.conf e rodar systemd-tmpfiles --create nele: /run/hefesto-dualsense4unix do root (0755) e a trava radio.lock (0660, grupo hefesto) que o watchdog e o daemon disputam"
            ;;
        bt-res)
            if [[ "${SKIP_UDEV}" -eq 1 ]]; then
                _nao_faria "resiliência do bluetoothd (--no-udev)"
                return 0
            fi
            _faria_root "instalar oito roteiros de Bluetooth em /usr/local/lib/hefesto-dualsense4unix/ (snapshot e restauro de bonds, watchdog, modo ativo)"
            _faria_root "rodar bt_active_mode.sh AGORA (tira o Pro Controller do modo sniff — não reinicia o bluetoothd)"
            _faria_root "instalar /etc/systemd/system/bluetooth.service.d/10-hefesto-resilience.conf (Restart + WatchdogSec=0 + snapshot na parada)"
            _faria_root "instalar os timers hefesto-bt-bonds-snapshot e hefesto-bt-health-watchdog em /etc/systemd/system/ e habilitá-los"
            _faria_root "gravar /etc/systemd/system/hefesto-bt-health-watchdog.service.d/10-hefesto-maquina.conf (o watchdog enxerga só o ${HOME}/.config/hefesto-dualsense4unix/maquina.json, só leitura, para dar ao adaptador o nome do lugar)"
            _faria_root "criar /var/lib/hefesto-dualsense4unix/bt-bonds (modo 700) para os snapshots"
            ;;
        bt-agent)
            if [[ "${SKIP_UDEV}" -eq 1 ]]; then
                _nao_faria "agente de pareamento (--no-udev)"
                return 0
            fi
            _faria_root "instalar /etc/systemd/system/hefesto-bt-agent.service e habilitá-lo (agente de pareamento persistente; instala bluez-tools se faltar)"
            ;;
        bt-ponte)
            _faria_root "instalar /usr/local/lib/hefesto-dualsense4unix/bt_ponte_privilegiada.sh"
            _faria_root "pôr a sua conta no grupo hefesto (a regra do sudoers da ponte é do grupo, e não só sua)"
            _faria_root "gravar /etc/sudoers.d/49-hefesto-bt-ponte (0440 root:root) — CONFERIDO com 'visudo -c' antes; se não passar, nada é gravado"
            ;;
        placa)
            _faria_root "instalar /usr/local/lib/hefesto-dualsense4unix/hefesto_placa_acordada.sh"
            _faria_root "gravar /etc/sudoers.d/49-hefesto-placa (0440 root:root) — CONFERIDO com 'visudo -c' antes; se não passar, nada é gravado"
            ;;
        gabinete)
            _faria_root "ler a tabela SMBIOS 8 com dmidecode (leitura pura, nada é escrito no firmware)"
            _faria "gravar o censo em ${HOME}/.local/state/hefesto-dualsense4unix/gabinete.json"
            ;;
        dkms-nintendo)
            if [[ "${NO_DKMS}" -eq 1 ]]; then
                _nao_faria "módulo DKMS hefesto-hid-nintendo (--no-dkms)"
                return 0
            fi
            _faria_root "compilar e instalar o módulo DKMS hefesto-hid-nintendo (substitui o hid-nintendo in-tree por precedência; o in-tree NUNCA é removido)"
            _faria_root "instalar /etc/modprobe.d/hefesto-hid-nintendo.conf (bt_probe_retries=$(opcao_do_modprobe "${ROOT_DIR}/assets/modprobe.d/hefesto-hid-nintendo.conf" bt_probe_retries) + skip_tx_on_rate_exceeded=$(opcao_do_modprobe "${ROOT_DIR}/assets/modprobe.d/hefesto-hid-nintendo.conf" skip_tx_on_rate_exceeded))"
            ;;
        dkms-rtw88)
            if [[ "${NO_DKMS}" -eq 1 ]]; then
                _nao_faria "módulo DKMS hefesto-rtw88-usb (--no-dkms)"
                return 0
            fi
            if ! _rtw88_adaptadores_presentes >/dev/null; then
                _nao_faria "módulo DKMS hefesto-rtw88-usb (nenhum adaptador Wi-Fi USB que o rtw88_usb atenda nesta máquina, ou o modprobe não responde)"
                return 0
            fi
            _faria_root "compilar e instalar o módulo DKMS hefesto-rtw88-usb (cura do fantasma USB do dongle WiFi; sem conf em /etc/modprobe.d)"
            ;;
        wifi-usb)
            if [[ "${NO_WIFI_USB}" -eq 1 ]]; then
                _nao_faria "vigia do Wi-Fi USB (--no-wifi-usb)"
                return 0
            fi
            if [[ "${SKIP_UDEV}" -eq 1 ]]; then
                _nao_faria "vigia do Wi-Fi USB (--no-udev)"
                return 0
            fi
            if [[ -z "$(_wifi_usb_agora)" ]]; then
                _nao_faria "vigia do Wi-Fi USB (nenhuma interface Wi-Fi sob o barramento USB nesta máquina)"
                return 0
            fi
            _faria_root "instalar /usr/local/lib/hefesto-dualsense4unix/wifi_usb.sh e a cópia dele em /etc/NetworkManager/dispatcher.d/90-hefesto-wifi-usb (root, 755) — o scan de fundo do Wi-Fi USB sai a cada associação"
            _faria_root "instalar /etc/systemd/system/hefesto-wifi-usb-vigia.service e hefesto-wifi-usb-vigia.timer e habilitar o timer (reinicia a porta do dongle quando ele trava mudo; sem Wi-Fi USB, não faz nada)"
            ;;
        desempenho)
            if [[ "${SKIP_UDEV}" -eq 1 ]]; then
                _nao_faria "modo desempenho (--no-udev)"
                return 0
            fi
            if [[ "${DESEMPENHO_PEDIDO:-}" == "sem" ]]; then
                _nao_faria "modo desempenho (--sem-desempenho)"
                return 0
            fi
            _desempenho_decidir
            if [[ "${_DESEMPENHO_QUER}" != "sim" ]]; then
                _nao_faria "modo desempenho (a resposta assumida é não)"
                return 0
            fi
            _faria_root "gravar /etc/systemd/system/hefesto-desempenho.service e habilitar (o perfil de energia em Performance a cada boot; para o system76-power ou o power-profiles-daemon, o que a máquina tiver)"
            if [[ -n "${DESEMPENHO_PROVADOS//[[:space:]]/}" ]]; then
                _faria_root "os ajustes provados no aparelho (${DESEMPENHO_PROVADOS}): arquivos em /etc/modprobe.d e /etc/tmpfiles.d (hefesto-desempenho-nvidia.conf, hefesto-desempenho-audio.conf, hefesto-desempenho-aspm.conf), valem no próximo boot"
            else
                _nao_faria "os ajustes ainda sem prova no aparelho (NVIDIA, áudio HDA, ASPM): o doctor os diz «a provar»"
            fi
            ;;
        dkms-playstation)
            if [[ "${NO_DKMS}" -eq 1 ]]; then
                _nao_faria "módulo DKMS hefesto-hid-playstation (--no-dkms)"
                return 0
            fi
            _faria_root "compilar e instalar o módulo DKMS hefesto-hid-playstation (retry de feature report na contenção BT)"
            _faria_root "instalar /etc/modprobe.d/hefesto-hid-playstation.conf (feature_retries=$(opcao_do_modprobe "${ROOT_DIR}/assets/modprobe.d/hefesto-hid-playstation.conf" feature_retries) + ds4_* do clone no cabo)"
            ;;
        dkms-uhid)
            if [[ "${COM_UHID_CONTRAPRESSAO:-0}" -ne 1 ]]; then
                _nao_faria "uhid com contrapressão (opt-in: --uhid-contrapressao)"
                return 0
            fi
            if [[ "${NO_DKMS}" -eq 1 ]]; then
                _nao_faria "uhid com contrapressão (--no-dkms)"
                return 0
            fi
            _faria_root "compilar e instalar o módulo DKMS hefesto-uhid (só nos kernels conferidos do dkms.conf; fora deles o de fábrica assume)"
            _faria_root "instalar /etc/modprobe.d/hefesto-uhid.conf (backpressure=$(opcao_do_modprobe "${ROOT_DIR}/assets/modprobe.d/hefesto-uhid.conf" backpressure)) e, com o patchado já carregado, ligar a contrapressão a quente em /sys/module/uhid/parameters/backpressure (o uhid NUNCA é recarregado)"
            ;;
        dkms-usb-f-hid)
            if [[ "${NO_DKMS}" -eq 1 ]]; then
                _nao_faria "módulo DKMS hefesto-usb-f-hid (--no-dkms)"
                return 0
            fi
            _faria_root "compilar e instalar o módulo DKMS hefesto-usb-f-hid (a resposta do GET_REPORT dos pads USB virtuais; só nos kernels conferidos do dkms.conf)"
            _faria_root "trocar o usb_f_hid carregado sem a marca get_report_sized: o daemon solta os pads, modprobe -r usb_f_hid e modprobe usb_f_hid, e o daemon sobe de novo (com gadget alheio, só no próximo boot)"
            ;;
        ucm)
            if [[ "${NO_UCM}" -eq 1 ]]; then
                _nao_faria "perfil UCM do DualSense (--no-ucm)"
                return 0
            fi
            if [[ "${SKIP_UDEV}" -eq 1 ]]; then
                _nao_faria "perfil UCM do DualSense (--no-udev)"
                return 0
            fi
            _faria_root "gravar o verbo HiFi do DualSense em /usr/share/alsa/ucm2/USB-Audio/Hefesto/ e um gancho por controlador USB em /usr/share/alsa/ucm2/conf.d/USB-Audio/ (o pacote alsa-ucm-conf fica intacto; scripts/install_ucm_dualsense.sh)"
            ;;
        initramfs)
            if [[ "${NO_DKMS}" -eq 1 ]]; then
                _nao_faria "regenerar o initramfs (--no-dkms)"
                return 0
            fi
            _faria_root "regenerar o initramfs UMA vez, e só se algum módulo DKMS acima tiver mudado (update-initramfs)"
            ;;
    esac
}

_ENSAIO_CURAS_DE_HOST=(
    "install_udev_host:udev"
    "install_osk_host:osk"
    "install_broker_host:broker"
    "install_trava_do_radio_host:trava-do-radio"
    "install_bt_resilience_host:bt-res"
    "install_bt_agent_host:bt-agent"
    "install_bt_ponte_privilegiada_host:bt-ponte"
    "install_placa_acordada_host:placa"
    "install_censo_do_gabinete_host:gabinete"
    "install_dkms_hid_nintendo_host:dkms-nintendo"
    "install_dkms_rtw88_usb_host:dkms-rtw88"
    "install_wifi_usb_host:wifi-usb"
    "install_desempenho_host:desempenho"
    "install_dkms_hid_playstation_host:dkms-playstation"
    "install_dkms_uhid_host:dkms-uhid"
    "install_dkms_usb_f_hid_host:dkms-usb-f-hid"
    "install_ucm_dualsense_host:ucm"
    "flush_initramfs_host:initramfs"
)
if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
    for _ensaio_par in "${_ENSAIO_CURAS_DE_HOST[@]}"; do
        eval "${_ensaio_par%%:*}() { _ensaio_camada ${_ensaio_par##*:}; }"
    done
    unset _ensaio_par
fi

_ensaio_snd_quirk() {
    _faria_root "gravar /etc/modprobe.d/hefesto-dualsense-storm.conf (quirk_flags do snd_usb_audio — cura do storm -71 preservando mic e fone)"
    _faria_root "ativar o quirk a quente em /sys/module/snd_usb_audio/parameters/quirk_flags (sem reboot; sem isto, vale no próximo boot)"
}
_ensaio_wireplumber() {
    case "$1" in
        nunca-dorme)
            _faria "instalar o drop-in 54-hefesto-dualsense-alto-falante-nunca-dorme em ${HOME}/.config/wireplumber/ (wireplumber.conf.d/ no WirePlumber 0.5, main.lua.d/ no 0.4)"
            ;;
        install)
            _faria "instalar o drop-in 51-hefesto-dualsense-no-default-source em ${HOME}/.config/wireplumber/ (wireplumber.conf.d/ no WirePlumber 0.5, main.lua.d/ no 0.4; rebaixa o microfone do controle)"
            _faria "eleger outra fonte de captura como padrão do sistema, se houver uma de verdade"
            ;;
        disable-source)
            _faria "instalar os drop-ins 52- e 53- em ${HOME}/.config/wireplumber/ (wireplumber.conf.d/ no WirePlumber 0.5, main.lua.d/ no 0.4; desabilitam a entrada e a saída do controle — ele vira só-HID)"
            ;;
        marcar-gesto)
            _faria "gravar a marca do gesto em ${HOME}/.local/state/hefesto-dualsense4unix/mic-do-dualsense-pedido.conf"
            ;;
    esac
}

format_flatpak() {
    step "flatpak" "build + flatpak install --user (GNOME//47)"
    if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
        _faria "rodar scripts/build_flatpak.sh --install (compila o bundle e o instala com flatpak --user)"
        _faria_root "aplicar as regras udev no host (scripts/install_udev.sh)"
        return 0
    fi
    require flatpak
    command -v flatpak-builder >/dev/null 2>&1 \
        || die "flatpak-builder ausente. Instale: sudo apt install flatpak-builder (ou flatpak install flathub org.flatpak.Builder)"
    bash "${ROOT_DIR}/scripts/build_flatpak.sh" --install \
        || die "build_flatpak.sh falhou"
    install_udev_host
    printf '\n      Abrir: flatpak run io.github.hefesto_team.hefesto_dualsense4unix\n'
}

format_appimage() {
    step "appimage" "build do .AppImage GUI + atalho"
    if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
        _faria "rodar scripts/build_appimage_gui.sh (constrói o .AppImage em dist/appimage/)"
        _faria "copiar o .AppImage para ${BIN_DIR}/Hefesto-Dualsense4Unix.AppImage"
        _faria "copiar o ícone para ${ICON_TARGET}"
        _faria "escrever o atalho ${DESKTOP_TARGET}"
        _faria_root "aplicar as regras udev no host (scripts/install_udev.sh)"
        _faria "instalar os perfis de fábrica (scripts/install_profiles.sh)"
        return 0
    fi
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
Name=Hefesto - DualSense4Unix
GenericName=DualSense Controller
Comment=Gerenciador DualSense para Linux
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
    if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
        _faria "rodar scripts/build_deb.sh (constrói o pacote em dist/)"
        _faria_root "instalar o .deb com apt-get install (o postinst dele aplica udev e o .desktop)"
        return 0
    fi
    bash "${ROOT_DIR}/scripts/build_deb.sh" \
        || die "build_deb.sh falhou"
    local deb
    deb="$(ls -t "${ROOT_DIR}/dist/"*.deb 2>/dev/null | head -1)"
    [[ -n "${deb}" ]] || die "nenhum .deb gerado em dist/"
    command -v sudo >/dev/null 2>&1 || die "sudo necessário para 'apt install'"
    if _avisa_pacote_a_meio "o .deb"; then
        printf '      depois, para instalar o Hefesto:   sudo apt install %s\n' "${deb}"
        die "o .deb não foi instalado: o sistema tem pacote a meio"
    fi
    sudo apt-get install -y "${deb}" || die "apt install falhou"
    printf '\n      Instalado via apt (udev + .desktop via postinst).\n      Abrir: hefesto-dualsense4unix-gui\n'
}

_reconhecimento() {
    local achou_algo=0

    local _fam
    _fam="$(_familia_pacotes)"
    if [[ "${_fam}" == "nenhum" ]]; then
        warn "não reconheço o gerenciador de pacotes desta distro"
        printf '      O install vai DIZER o que falta, com o nome no Debian/Ubuntu como\n'
        printf '      referência, e seguir sem instalar nada — em Nix ou Gentoo, use o\n'
        printf '      pacote da sua distro (ver docs/usage/instalacao.md).\n'
        achou_algo=1
    elif [[ "${_fam}" == "imutavel" ]]; then
        warn "distro somente leitura (Bazzite, Silverblue, SteamOS ou parente)"
        printf '      O install não chama gerente de pacotes nem DKMS: grava só a casa do\n'
        printf '      usuário, as regras udev e as units em /etc, e diz o que fica de fora.\n'
        achou_algo=1
    elif [[ "${_fam}" != "apt" ]]; then
        warn "distro fora da família Debian/Ubuntu — o install usa ${_fam}"
        printf '      As dependências de sistema são instaladas pelo %s, com os nomes que\n' "${_fam}"
        printf '      o Hefesto já declara no empacotamento da sua família. O que ainda não\n'
        printf '      foi validado em hardware é a distro, não o instalador.\n'
        achou_algo=1
    fi

    local _bz
    _bz="$(bluetoothctl --version 2>/dev/null | awk '{print $NF}' || true)"
    if [[ -n "${_bz}" ]]; then
        if [[ "$(printf '%s\n5.79\n' "${_bz}" | sort -V | head -1)" != "5.79" ]]; then
            warn "bluez ${_bz} — abaixo de 5.79, a faixa que o Hefesto validou"
            printf '      Abaixo de 5.79 há crashes crônicos de input/HIDP (medidos: 6 em 5 dias).\n'
            printf '      A conferência final vai REPROVAR por isto. A cura é um backport, e a\n'
            printf '      receita está em docs/usage/receita-backport-bluez.md\n'
            achou_algo=1
        fi
    fi

    # shellcheck source=scripts/dkms_lib.sh
    source "${ROOT_DIR}/scripts/dkms_lib.sh"
    if [[ "${NO_DKMS}" -eq 0 ]] && [[ "${_fam}" != "imutavel" ]] \
        && dkms_secure_boot_ligado && ! dkms_chave_mok_inscrita; then
        warn "Secure Boot ligado, e a chave do DKMS não está inscrita"
        printf '      Os módulos do Hefesto não vão ser instalados: o kernel os recusaria\n'
        printf '      no boot, e o DualSense ficaria sem driver nenhum. O driver de fábrica\n'
        printf '      fica, o DualSense funciona sem as curas, e o microfone pelo rádio\n'
        printf '      fica desligado. Para ganhar as curas: %s.\n' "$(dkms_passo_da_mok)"
        achou_algo=1
    fi

    [[ "${achou_algo}" -eq 0 ]] && printf '      distro, bluez e Secure Boot: nada que atrapalha\n'
    return 0
}
_reconhecimento
ok

if [[ "${NO_DKMS}" -eq 0 ]] && [[ "$(_familia_pacotes)" == "imutavel" ]]; then
    printf '\n      Distro somente leitura: não há gerente de pacotes nem DKMS a chamar. O que fica de fora:\n'
    printf '        módulos DKMS: %s\n' "$(_efeito_so_leitura playstation)"
    printf '        perfil UCM:   %s\n' "$(_efeito_so_leitura ucm)"
    printf '      O resto segue: a casa do usuário, as regras udev e as units em /etc.\n'
elif [[ "${NO_DKMS}" -eq 0 ]] && [[ "$(_familia_pacotes)" != "nenhum" ]]; then
    _dkms_faltando=()
    command -v dkms >/dev/null 2>&1 || _dkms_faltando+=("dkms")
    command -v make >/dev/null 2>&1 || _dkms_faltando+=("compilador")
    [[ -d "/lib/modules/$(uname -r)/build" ]] || _dkms_faltando+=("kernel-headers")

    if [[ "${#_dkms_faltando[@]}" -gt 0 ]]; then
        printf '\n      Os três módulos de kernel do Hefesto precisam compilar, e falta:\n'
        printf '        %s\n' "$(comando_manual_pkg "${_dkms_faltando[@]}")"
        printf '      Sem eles, as curas NÃO entram: o microfone do DualSense pelo rádio\n'
        printf '      fica desligado (o driver de fábrica o leria como botão e mexeria o\n'
        printf '      cursor), dois DualSense no mesmo adaptador podem virar um só, e o\n'
        printf '      controle da Nintendo pode não subir pelo rádio.\n\n'
        ask_yn "instalar agora com sudo?" "${AUTO_YES}"
        if [[ "${REPLY,,}" =~ ^y ]]; then
            if run_pkg "${_dkms_faltando[@]}"; then
                printf '      pronto para compilar os módulos\n'
            else
                warn "não consegui instalar ${_dkms_faltando[*]} — os módulos DKMS vão ser pulados"
                printf '      O produto funciona com os drivers in-tree, sem as curas do Hefesto.\n'
                printf '      A conferência final no fim vai dizer quais faltaram.\n'
            fi
        else
            warn "sem ${_dkms_faltando[*]}: os três módulos DKMS vão ser pulados"
            printf '      Reexecute o install depois de instalá-los para ganhar as curas.\n'
        fi
    fi
    unset _dkms_faltando
fi


if [[ "${FORMAT}" != "native" ]]; then
    case "${FORMAT}" in
        flatpak)  format_flatpak ;;
        appimage) format_appimage ;;
        deb)      format_deb ;;
    esac
    if [[ "${SKIP_SND_QUIRK}" -eq 0 ]]; then
        step "cura" "cura de raiz do storm (snd_usb_audio quirk — preserva mic+fone)"
        if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
        _ensaio_snd_quirk
        elif bash "${ROOT_DIR}/scripts/install_snd_quirk.sh"; then
            if bash "${ROOT_DIR}/scripts/install_snd_quirk.sh" --runtime >/dev/null 2>&1; then
                printf '      cura instalada e ativada (replug do controle p/ valer já)\n'
            else
                printf '      cura instalada; ativação a quente NÃO passou — vale no próximo boot\n'
            fi
        else
            warn "install_snd_quirk.sh falhou — rode: sudo bash scripts/install_snd_quirk.sh"
        fi
    fi
    step "ucm" "perfil UCM do DualSense: a vibração dos jogos da Sony pelo cabo (DEFAULT em todo formato)"
    install_ucm_dualsense_host
    step "broker" "o controle físico escondido dos jogos, entregue ao Hefesto (DEFAULT em todo formato)"
    install_broker_host
    step "trava" "a trava comum do rádio (DEFAULT em todo formato)"
    install_trava_do_radio_host
    step "bt-res" "Bluetooth mais resistente a quedas (DEFAULT em todo formato)"
    install_bt_resilience_host
    step "bt-agent" "agente de pareamento Bluetooth sempre de pé (DEFAULT em todo formato)"
    install_bt_agent_host
    step "bt-ponte" "mover controle entre adaptadores Bluetooth sem pedir senha (DEFAULT em todo formato)"
    install_bt_ponte_privilegiada_host
    step "placa" "a placa de vídeo acordada enquanto um jogo vive (DEFAULT em todo formato)"
    install_placa_acordada_host
    step "gabinete" "as entradas USB do gabinete, lidas do firmware (DEFAULT em todo formato)"
    install_censo_do_gabinete_host
    step "dkms" "módulo hid-nintendo corrigido (DKMS; DEFAULT em todo formato)"
    install_dkms_hid_nintendo_host
    step "dkms-w" "módulo rtw88_usb corrigido (DKMS; DEFAULT em todo formato)"
    install_dkms_rtw88_usb_host
    step "wifi-usb" "vigia do dongle Wi-Fi USB (DEFAULT em todo formato; opt-out --no-wifi-usb)"
    install_wifi_usb_host
    step "desempenho" "modo desempenho: o perfil de energia em Performance (pergunta; --desempenho / --sem-desempenho)"
    install_desempenho_host
    step "dkms-p" "módulo hid-playstation corrigido (DKMS; DEFAULT em todo formato)"
    install_dkms_hid_playstation_host
    step "dkms-u" "uhid com contrapressão (OPT-IN: --uhid-contrapressao)"
    install_dkms_uhid_host
    step "dkms-f" "usb_f_hid corrigido (DKMS: a resposta do GET_REPORT dos pads USB virtuais)"
    install_dkms_usb_f_hid_host
    step "dkms-i" "regenerar o initramfs se algum módulo DKMS mudou"
    flush_initramfs_host
    step "osk" "teclado na tela do L3 (DEFAULT em todo formato)"
    install_osk_host
    step "som" "áudio: o alto-falante do controle nunca dorme"
    if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
    _ensaio_wireplumber nunca-dorme
    else
    bash "${ROOT_DIR}/scripts/fix_wireplumber_default_source.sh" --nunca-dorme \
        || warn "nunca-dorme falhou — rode: bash scripts/fix_wireplumber_default_source.sh --nunca-dorme"
    fi
    if [[ "${WITH_WIREPLUMBER_DISABLE_MIC}" -eq 1 ]]; then
        step "mic" "áudio: desabilitar o microfone do DualSense (--with-wireplumber-disable-mic)"
        if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
        _ensaio_wireplumber disable-source
        else
        bash "${ROOT_DIR}/scripts/fix_wireplumber_default_source.sh" --disable-source \
            || warn "disable-source falhou — rode: bash scripts/fix_wireplumber_default_source.sh --disable-source"
        fi
    elif [[ "${WITH_WIREPLUMBER_FIX}" -eq 1 ]]; then
        step "mic" "áudio: a voz do controle acima do eco da saída"
        if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
        _ensaio_wireplumber install
        elif bash "${ROOT_DIR}/scripts/fix_wireplumber_default_source.sh" --install; rc=$?; \
           [[ "${rc:-0}" -eq 1 ]]; then
            warn "fix do WirePlumber falhou — rode: bash scripts/fix_wireplumber_default_source.sh --install"
        fi
    fi
    if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
        _ensaio_resumo
        exit 0
    fi
    printf '\n─────────────────────────────────────────\n'
    printf ' Hefesto - DualSense4Unix instalado (%s)\n' "${FORMAT}"
    printf ' Obs.: desligar do Steam Input, preparo dos jogos da Steam e os\n'
    printf ' passos de plataforma (Proton pinado, BT no máximo, cmdline) só\n'
    printf ' valem no formato "native" (padrão).\n'
    printf ' Desinstalar: ./uninstall.sh\n'
    printf '─────────────────────────────────────────\n'
    dizer_o_reinicio_pendente
    printf '\n'
    exit 0
fi

step "1/11" "verificando dependências do sistema"
require python3

ok

if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
    _ensaio_caches=()
    for cache in .pytest_cache .ruff_cache .mypy_cache flatpak-build-dir .flatpak-builder dist build; do
        [[ -d "${ROOT_DIR}/${cache}" ]] && _ensaio_caches+=("${cache}")
    done
    if (( ${#_ensaio_caches[@]} )); then
        _faria "apagar da árvore do projeto: ${_ensaio_caches[*]} (caches de build; nada de configuração sua)"
    fi
    _faria "apagar os __pycache__ e os .pyc da árvore, fora de .git e de .venv"
    unset _ensaio_caches
else
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
fi

step "2/11" "preparando ambiente Python"

_VENV_PYTHON="python3"
if [[ -x /usr/bin/python3 ]]; then
    _VENV_PYTHON="/usr/bin/python3"
fi

if [[ -d "${VENV_DIR}" ]]; then
    _venv_home=$(grep "^home = " "${VENV_DIR}/pyvenv.cfg" 2>/dev/null | awk '{print $3}')
    if [[ -n "${_venv_home}" ]] && [[ "${_venv_home}" != "/usr/bin" ]] && [[ -x /usr/bin/python3 ]]; then
        printf '      venv criado com Python não-sistema (%s) — recriando...\n' "${_venv_home}"
        if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
        _faria "APAGAR e recriar ${VENV_DIR} (o venv de hoje foi criado com um Python que não é o do sistema)"
        else
        rm -rf "${VENV_DIR}"
        fi
    fi
fi

if [[ -d "${VENV_DIR}" ]]; then
    _sys_ver=$("${_VENV_PYTHON}" -c 'import sys;print("%d.%d"%sys.version_info[:2])' 2>/dev/null)
    _venv_ver=$("${VENV_DIR}/bin/python" -c 'import sys;print("%d.%d"%sys.version_info[:2])' 2>/dev/null)
    if [[ -z "${_venv_ver}" ]]; then
        printf '      venv com Python inexecutável (provável dist upgrade) — recriando...\n'
        if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
        _faria "APAGAR e recriar ${VENV_DIR} (o Python dele não executa — provável dist upgrade)"
        else
        rm -rf "${VENV_DIR}"
        fi
    elif [[ -n "${_sys_ver}" ]] && [[ "${_venv_ver}" != "${_sys_ver}" ]]; then
        printf '      venv em Python %s, sistema agora em %s — recriando...\n' \
            "${_venv_ver}" "${_sys_ver}"
        if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
        _faria "APAGAR e recriar ${VENV_DIR} (Python ${_venv_ver} no venv, ${_sys_ver} no sistema)"
        else
        rm -rf "${VENV_DIR}"
        fi
    fi
fi

if [[ "${DRY_RUN:-0}" -eq 1 ]] && [[ ! -d "${VENV_DIR}" ]]; then
    _faria "criar o venv em ${VENV_DIR} com ${_VENV_PYTHON} (--system-site-packages, para enxergar o PyGObject do sistema)"
elif [[ ! -d "${VENV_DIR}" ]]; then
    printf '      criando venv...\n'
    if ! "${_VENV_PYTHON}" -m venv --system-site-packages "${VENV_DIR}" 2>/dev/null; then
        printf '      módulo venv ausente — instalando pelo %s\n' "$(_familia_pacotes)"
        run_pkg python-venv || true
        if ! "${_VENV_PYTHON}" -m venv --system-site-packages "${VENV_DIR}" 2>/dev/null; then
            printf '      rode: %s\n' "$(comando_manual_pkg python-venv)"
            die "não consegui criar o venv em ${VENV_DIR}"
        fi
    fi
fi

_PY_DO_GTK="${VENV_DIR}/bin/python"
[[ -x "${_PY_DO_GTK}" ]] || _PY_DO_GTK="${_VENV_PYTHON}"
if ! "${_PY_DO_GTK}" -c \
        "import gi; gi.require_version('Gtk','3.0')" >/dev/null 2>&1; then

    printf '\n      Bindings GTK3 não encontrados — obrigatórios para a GUI.\n'
    printf '      Rodaria: %s\n\n' \
        "$(comando_manual_pkg python-gi python-gi-cairo gtk3 appindicator gi-dev)"

    ask_yn "instalar agora com sudo?" "${AUTO_YES}"
    if [[ "${REPLY,,}" =~ ^y ]]; then
        printf '      instalando...\n'
        _rc_pkg=0
        run_pkg python-gi python-gi-cairo gtk3 appindicator gi-dev || _rc_pkg=$?
        if (( _rc_pkg == _RC_PACOTE_A_MEIO )); then
            printf '      para consertar o sistema:   sudo apt-get install -f   (ou: sudo dpkg --configure -a)\n'
            die "o GTK3 não foi instalado porque o sistema tem pacote a meio de uma atualização (${_PACOTES_A_MEIO_LISTA}) — conserte o sistema pelo comando acima e reexecute ./install.sh"
        elif (( _rc_pkg )); then
            die "falha ao instalar GTK3 — $([[ "$(_familia_pacotes)" == "imutavel" ]] && printf 'a imagem do sistema não os trouxe; peça-os pela camada de pacotes da sua distro' || printf 'verifique a conexão e tente novamente')"
        fi
        printf '      GTK3 instalado\n'
    else
        die "GTK3 obrigatório. Instale manualmente e reexecute ./install.sh"
    fi
fi

_garantir_deps_de_sistema

_btmic_faltando=()
_dep_presente "lib:libopus.so.0" || _btmic_faltando+=(opus)
_dep_presente "cmd:pactl" || _btmic_faltando+=(pactl)
if (( ${#_btmic_faltando[@]} )); then
    printf '\n      Áudio do controle por Bluetooth (microfone E alto-falante): faltam %s\n' \
        "${_btmic_faltando[*]}"
    ask_yn "instalar agora com sudo?" "${AUTO_YES}" "y"
    if [[ "${REPLY,,}" =~ ^y ]]; then
        if run_pkg "${_btmic_faltando[@]}"; then
            printf '      ok — `hefesto-dualsense4unix mic bt` e o som por rádio disponíveis\n'
        else
            warn "não instalei ${_btmic_faltando[*]} — o mic por BT e o som por rádio ficam indisponíveis"
        fi
    else
        printf '      pulando (mic e som por BT indisponíveis; instale depois: %s)\n' \
            "$(comando_manual_pkg "${_btmic_faltando[@]}")"
    fi
fi
unset _btmic_faltando

printf '      instalando pacote Python...\n'
if [[ "${DRY_RUN:-0}" -eq 0 ]]; then
"${VENV_DIR}/bin/python" -m pip install \
    --quiet --disable-pip-version-check --upgrade pip packaging 2>/dev/null
fi

_extras="emulation,cosmic"
if [[ "${WITH_DEV}" -eq 1 ]]; then _extras="${_extras},dev"; fi
_travas=()
[[ -r "${ROOT_DIR}/constraints.txt" ]] && _travas=(-c "${ROOT_DIR}/constraints.txt")
if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
    _faria "atualizar pip e packaging dentro de ${VENV_DIR}"
    _faria "instalar o pacote em modo editável no venv: pip install ${_travas[*]} -e '${ROOT_DIR}[${_extras}]'"
elif ! "${VENV_DIR}/bin/pip" install \
        --quiet --disable-pip-version-check "${_travas[@]}" -e "${ROOT_DIR}[${_extras}]" 2>/dev/null; then
    if [[ "${WITH_DEV}" -eq 1 ]]; then
        warn "pip install com [dev] falhou — tentando só o essencial (ruff/mypy/pytest ficam de fora)"
        "${VENV_DIR}/bin/pip" install \
            --quiet --disable-pip-version-check "${_travas[@]}" -e "${ROOT_DIR}[emulation,cosmic]" 2>/dev/null \
            || die "pip install do pacote falhou — verifique a conexão e reexecute"
    else
        die "pip install do pacote falhou — verifique a conexão e reexecute"
    fi
fi
ok

step "3/11" "udev rules (hidraw + uinput + autosuspend)"

if [[ "${SKIP_UDEV}" -eq 1 ]]; then
    printf '      pulado (--no-udev) — IMPORTANTE: o controle precisa das regras\n'
    printf '      para funcionar. Rode depois: sudo bash scripts/install_udev.sh\n'
elif ! command -v sudo >/dev/null 2>&1; then
    warn "sudo ausente — pulando (rode scripts/install_udev.sh manualmente como root)"
else
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
            73-hefesto-ps5-controller.rules) rules_desc='hidraw do DualSense físico fechado; o vpad aberto (USB e BT)' ;;
            71-uinput.rules) rules_desc='emulação Xbox360 via uinput' ;;
            71-uhid.rules) rules_desc='DualSense virtual via uhid (vibração na máscara PS)' ;;
            72-hefesto-touchpad-motion-uaccess.rules) rules_desc='touchpad e giroscópio acessíveis à sessão (uaccess)' ;;
            72-*) rules_desc='evita desconexão intermitente USB' ;;
            76-*) rules_desc='touchpad só pelo hefesto (sem briga)' ;;
            77-*) rules_desc='lightbar/player-LED graváveis via sysfs' ;;
            78-*) rules_desc='motion sensors fora da lista de joysticks' ;;
            79-*) rules_desc='LED de player dos controles Nintendo/8BitDo' ;;
            80-*) rules_desc='motion sensors fora da API js legada' ;;
            81-hefesto-usb-power.rules) rules_desc='controles e adaptadores BT nunca dormem (USB)' ;;
            81-hefesto-usb-host-power.rules) rules_desc='hosts USB (xHCI) sem economia que derruba o barramento' ;;
            82-nintendo-pro-nosniff.rules) rules_desc='Pro Controller sai do sniff na borda da conexão (BT)' ;;
            83-hefesto-bond-snapshot.rules) rules_desc='snapshot dos bonds BT na borda da conexão' ;;
            84-nintendo-pro-variant.rules) rules_desc='separa o Pro genuíno do 8BitDo clone (bcdDevice)' ;;
            *)    rules_desc='' ;;
        esac
        printf '        %-45s %s\n' "${rules_base}" "${rules_desc}"
    done
    printf '      (75 áudio-off é opt-in: sudo bash scripts/install_udev.sh --disable-usb-audio)\n'

    if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
        _ensaio_camada udev
        _faria_root "gravar /etc/modules-load.d/ para o uinput e o uhid subirem no boot, e recarregar o udev"
    elif bash "${ROOT_DIR}/scripts/install_udev.sh" >/dev/null 2>&1; then
        printf '      regras aplicadas + udev recarregado + uinput carregado\n'
    else
        warn "install_udev.sh falhou — rode manualmente: sudo bash scripts/install_udev.sh"
    fi

    if command -v flatpak >/dev/null 2>&1 \
       && flatpak info io.github.hefesto_team.hefesto_dualsense4unix >/dev/null 2>&1; then
        printf '      Flatpak Hefesto detectado — sincronizando regras via bundle\n'
        if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
        _faria_root "repassar as regras udev pelo bundle Flatpak (flatpak run --command=install-host-udev.sh) — no-op se já estiverem lá"
        else
        flatpak run --command=install-host-udev.sh io.github.hefesto_team.hefesto_dualsense4unix \
            >/dev/null 2>&1 \
            || warn "flatpak install-host-udev.sh falhou (regras já vieram via install_udev.sh)"
        fi
    fi
fi

if [[ "${WITH_USB_QUIRK}" -eq 1 ]]; then
    step "3b" "quirk de boot usbcore.quirks (preserva o áudio do DualSense)"
    if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
        _faria_root "acrescentar usbcore.quirks=054c:0ce6:gn ao cmdline do kernel (kernelstub ou grub) — vale no PRÓXIMO boot"
    elif bash "${ROOT_DIR}/scripts/install_usb_quirk.sh"; then
        printf '      quirk aplicado (vale no próximo boot) — confira: scripts/install_usb_quirk.sh --status\n'
    else
        warn "install_usb_quirk.sh falhou — rode: sudo bash scripts/install_usb_quirk.sh"
    fi
fi

if [[ "${SKIP_SND_QUIRK}" -eq 0 && "${SKIP_UDEV}" -eq 0 ]]; then
    step "3c" "cura de raiz do storm (snd_usb_audio quirk — preserva mic+fone)"
    SND_QUIRK_CONF="/etc/modprobe.d/hefesto-dualsense-storm.conf"
    if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
        _ensaio_snd_quirk
    elif bash "${ROOT_DIR}/scripts/install_snd_quirk.sh"; then
        bash "${ROOT_DIR}/scripts/install_snd_quirk.sh" --runtime >/dev/null 2>&1 || true
    else
        warn "install_snd_quirk.sh retornou erro — rode: sudo bash scripts/install_snd_quirk.sh"
    fi
    if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
        :
    elif [[ -f "${SND_QUIRK_CONF}" ]]; then
        printf '      cura persistente OK em %s + ativada (replug do controle p/ valer já)\n' "${SND_QUIRK_CONF}"
    else
        warn "cura NÃO persistiu — ${SND_QUIRK_CONF} ausente (sudo recusado?)"
        warn "rode manualmente: sudo bash scripts/install_snd_quirk.sh"
    fi
fi

step "3c-bis" "perfil UCM do DualSense (a vibração dos jogos da Sony pelo cabo)"
install_ucm_dualsense_host

if [[ "${SKIP_UDEV}" -eq 1 ]]; then
    step "3d" "Bluetooth no máximo — PULADO (--no-udev)"
    warn "btusb sem autosuspend e config do BlueZ NÃO aplicados (o passo toca /etc)"
    warn "  falta fazer: sudo bash ${ROOT_DIR}/scripts/bluez_config.sh aplicar"
    warn "  falta fazer: sudo install -Dm644 assets/modprobe.d/hefesto-btusb-no-autosuspend.conf /etc/modprobe.d/hefesto-btusb-no-autosuspend.conf"
    _bt_estado="$(HEFESTO_BT_SUDO="" HEFESTO_BT_ASSETS="${ROOT_DIR}/assets/bluetooth" \
        bash "${ROOT_DIR}/scripts/bluez_config.sh" verificar 2>/dev/null \
        | sed -n 's/^JustWorksRepairing: //p' || true)"
    if [[ "${_bt_estado}" == "always" ]]; then
        warn "  e ATENÇÃO: o disco está com JustWorksRepairing=always AGORA — com --no-udev este install NÃO corrigiu isso (o valor seguro é confirm)"
    elif [[ -n "${_bt_estado}" && "${_bt_estado}" != "confirm" && "${_bt_estado}" != "ausente" ]]; then
        warn "  e o disco está com JustWorksRepairing=${_bt_estado} AGORA — este install NÃO tocou nesse valor"
    fi
    unset _bt_estado
elif command -v sudo >/dev/null 2>&1; then
    step "3d" "Bluetooth no máximo (btusb sem autosuspend + reconexão rápida)"
    if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
        _faria_root "gravar /etc/modprobe.d/hefesto-btusb-no-autosuspend.conf (o adaptador Bluetooth nunca dorme)"
        _faria_root "zerar /sys/module/btusb/parameters/enable_autosuspend agora (a quente, sem reboot)"
        _faria_root "normalizar /etc/bluetooth/main.conf: FastConnectable ligado e JustWorksRepairing=confirm (backup ao lado; o bluetoothd NÃO é reiniciado)"
    elif ! sudo -n true 2>/dev/null; then
        warn "sudo recusado — passos de BT no máximo pulados (re-execute ./install.sh)"
    else
        if sudo install -Dm644 "${ROOT_DIR}/assets/modprobe.d/hefesto-btusb-no-autosuspend.conf" \
                /etc/modprobe.d/hefesto-btusb-no-autosuspend.conf 2>/dev/null; then
            printf '      modprobe.d do btusb instalado (adaptador BT nunca dorme; vale no próximo probe)\n'
        else
            warn "não consegui gravar /etc/modprobe.d/hefesto-btusb-no-autosuspend.conf"
        fi
        if [[ -e /sys/module/btusb/parameters/enable_autosuspend ]]; then
            _v="$(opcao_do_modprobe "${ROOT_DIR}/assets/modprobe.d/hefesto-btusb-no-autosuspend.conf" enable_autosuspend)" && printf '%s' "${_v}" | sudo tee /sys/module/btusb/parameters/enable_autosuspend >/dev/null 2>&1 || true
        fi
        if ! HEFESTO_BT_ASSETS="${ROOT_DIR}/assets/bluetooth" \
             bash "${ROOT_DIR}/scripts/bluez_config.sh" aplicar; then
            warn "config do BlueZ (FastConnectable + JustWorksRepairing) não ficou garantida"
        fi
    fi
else
    step "3d" "Bluetooth no máximo — PULADO (sem sudo nesta máquina)"
    warn "sem o comando sudo: config do BlueZ e modprobe.d do btusb NÃO aplicados"
    warn "  falta fazer, como root: bash ${ROOT_DIR}/scripts/bluez_config.sh aplicar"
fi

_wifi_ferramenta() {
    local nome dir
    for nome in iw iwconfig; do
        if command -v "${nome}" >/dev/null 2>&1; then
            command -v "${nome}"
            return 0
        fi
        for dir in /usr/sbin /sbin; do
            if [[ -x "${dir}/${nome}" ]]; then
                printf '%s\n' "${dir}/${nome}"
                return 0
            fi
        done
    done
    return 1
}

_wifi_interfaces() {
    case "${1##*/}" in
        iw)       "$1" dev 2>/dev/null | awk '$1 == "Interface" { print $2 }' ;;
        iwconfig) "$1" 2>/dev/null | awk '/^[^ \t]/ && !/no wireless extensions/ { print $1 }' ;;
    esac
}

_wifi_economia_ligada() {
    case "${1##*/}" in
        iw)       "$1" dev "$2" get power_save 2>/dev/null | grep -qi 'power save: *on' ;;
        iwconfig) "$1" "$2" 2>/dev/null | grep -qi 'power management: *on' ;;
        *)        return 1 ;;
    esac
}

_wifi_comando_desliga() {
    case "${1##*/}" in
        iw) printf '%s dev %s set power_save off\n' "$1" "$2" ;;
        *)  printf '%s %s power off\n' "$1" "$2" ;;
    esac
}

_wifi_desliga_economia() {
    case "${1##*/}" in
        iw) sudo "$1" dev "$2" set power_save off ;;
        *)  sudo "$1" "$2" power off ;;
    esac
}

aplicar_wifi_powersave_off() {
    local alvo="/etc/NetworkManager/conf.d/hefesto-wifi-powersave.conf"
    local asset="${ROOT_DIR}/assets/NetworkManager/hefesto-wifi-powersave.conf"
    local conf_igual=0 ifc ferramenta=""
    local -a ligadas=()
    if cmp -s "${asset}" "${alvo}" 2>/dev/null; then conf_igual=1; fi
    ferramenta="$(_wifi_ferramenta)" || ferramenta=""
    if [[ -n "${ferramenta}" ]]; then
        while IFS= read -r ifc; do
            [[ -n "${ifc}" ]] || continue
            if _wifi_economia_ligada "${ferramenta}" "${ifc}"; then ligadas+=("${ifc}"); fi
        done < <(_wifi_interfaces "${ferramenta}")
    fi
    local sem_ferramenta="sem iw nem iwconfig, a economia de cada interface não se confere agora (o conf vale no próximo boot)"

    if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
        if [[ "${SKIP_UDEV}" -eq 1 ]]; then
            _nao_faria "nada aqui: --no-udev pula os passos que tocam /etc"
            return 0
        fi
        if [[ "${conf_igual}" -eq 1 ]]; then
            _nao_faria "gravar ${alvo}: já está igual"
        else
            _faria_root "gravar ${alvo} (wifi.powersave=2) — o NetworkManager o lê no próximo boot"
        fi
        for ifc in ${ligadas[@]+"${ligadas[@]}"}; do
            _faria_root "desligar a economia de energia de ${ifc} na hora (power_save off, sem reconectar)"
        done
        if [[ -z "${ferramenta}" ]]; then
            _nao_faria "desligar na hora: ${sem_ferramenta}"
        elif [[ "${conf_igual}" -eq 1 && "${#ligadas[@]}" -eq 0 ]]; then
            _nao_faria "mexer no Wi-Fi: a economia de energia já está desligada"
        fi
        return 0
    fi
    if [[ "${SKIP_UDEV}" -eq 1 ]]; then
        warn "--no-udev ativo — passo de /etc pulado (rode sem --no-udev para aplicar)"
        return 0
    fi
    if [[ "${conf_igual}" -eq 1 && "${#ligadas[@]}" -eq 0 ]]; then
        if [[ -n "${ferramenta}" ]]; then
            printf '      economia de energia do Wi-Fi já desligada (conf igual, nenhuma interface com ela ligada)\n'
        else
            printf '      conf igual; %s\n' "${sem_ferramenta}"
        fi
        return 0
    fi
    if ! command -v sudo >/dev/null 2>&1 || ! sudo -n true 2>/dev/null; then
        warn "sudo indisponível/recusado — a economia de energia do Wi-Fi NÃO foi desligada; re-execute:"
        [[ "${conf_igual}" -eq 1 ]] || warn "  sudo install -Dm644 assets/NetworkManager/hefesto-wifi-powersave.conf ${alvo}"
        for ifc in ${ligadas[@]+"${ligadas[@]}"}; do
            warn "  sudo $(_wifi_comando_desliga "${ferramenta}" "${ifc}")"
        done
        return 0
    fi
    if [[ "${conf_igual}" -eq 0 ]]; then
        if sudo install -Dm644 "${asset}" "${alvo}" 2>/dev/null; then
            printf '      conf instalado em %s (wifi.powersave=2)\n' "${alvo}"
            anotar_reinicio_pendente "a economia de energia do Wi-Fi desligada de vez (o NetworkManager lê o conf no boot)"
        else
            warn "não consegui gravar ${alvo}"
        fi
        [[ -n "${ferramenta}" ]] || printf '      %s\n' "${sem_ferramenta}"
    fi
    for ifc in ${ligadas[@]+"${ligadas[@]}"}; do
        if _wifi_desliga_economia "${ferramenta}" "${ifc}" 2>/dev/null \
                && ! _wifi_economia_ligada "${ferramenta}" "${ifc}"; then
            printf '      economia de energia de %s desligada agora (a conexão não foi tocada)\n' "${ifc}"
        else
            warn "não consegui desligar a economia de energia de ${ifc} agora — o conf vale no próximo boot"
        fi
    done
}

step "3d-bis" "economia de energia do WiFi OFF (conf.d do NetworkManager + na hora)"
aplicar_wifi_powersave_off

if [[ "${SKIP_UDEV}" -eq 0 ]] && command -v python3 >/dev/null 2>&1; then
    step "3e" "cmdline do kernel (usbcore.autosuspend + usbcore.quirks com merge)"
    _cmdline_bateria=0
    if _desempenho_tem_bateria; then _cmdline_bateria=1; fi
    _cmdline_plan="$(python3 - "${ROOT_DIR}" "${_cmdline_bateria}" <<'PYEOF'
import os
import sys
from pathlib import Path

root = sys.argv[1]
com_bateria = sys.argv[2] == "1"
sys.path.insert(0, os.path.join(root, "src"))
from hefesto_dualsense4unix.integrations import kernel_cmdline as kc

lugares = kc.Lugares(
    kernelstub=Path("/etc/kernelstub/configuration"),
    grub=Path("/etc/default/grub"),
    kernel_cmdline=Path("/etc/kernel/cmdline"),
    raiz=Path("/"),
)
carregador = kc.ler_o_carregador(lugares)
tokens = list(carregador.tokens)
backend = carregador.backend
if backend == kc.BACKEND_NENHUM:
    try:
        with open("/proc/cmdline", encoding="utf-8") as fh:
            tokens = kc.parse_cmdline(fh.read())
    except OSError:
        tokens = []
actions = kc.plan_tokens(tokens, com_bateria=com_bateria)
violations = kc.forbidden_reintroductions(actions)
if violations:
    print("backend=guard-violation")
    for violation in violations:
        print("viol\t" + violation)
    raise SystemExit(0)
print("backend=" + backend)
for a in actions:
    print("\t".join(["plan", a.param, a.op, a.token, a.owner or "-", " ".join(a.remove_tokens)]))
PYEOF
)" || _cmdline_plan=""
    _cmdline_backend="$(sed -n 's/^backend=//p' <<<"${_cmdline_plan}" | head -1)"
    if [[ -z "${_cmdline_backend}" ]]; then
        warn "o plano do cmdline não saiu — passo pulado (nada registrado)"
    elif [[ "${_cmdline_backend}" == "guard-violation" ]]; then
        warn "guarda anti-reintrodução disparou — passo ABORTADO (nada foi escrito):"
        sed -n 's/^viol\t/        /p' <<<"${_cmdline_plan}"
    else
        _cmdline_changed=0
        _cmdline_args=()
        _cmdline_pendentes=()
        while IFS=$'\t' read -r _tagp _param _op _token _owner _removes; do
            [[ "${_tagp}" == "plan" ]] || continue
            case "${_op}" in
                skip)
                    printf '      %s: pulado — este computador tem bateria (USB sem economia custaria a carga de quem joga fora da tomada); o usbcore.quirks do DualSense segue\n' \
                        "${_param}"
                    ;;
                none)
                    _register_cmdline_owner "cmdline.${_param}" "${_owner}"
                    if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
                        printf '      %s: já garantido nesta máquina (dono que eu registraria: %s) — não toco no cmdline\n' \
                            "${_param}" "${_owner}"
                    else
                    printf '      %s: já garantido (dono registrado: %s) — não toco\n' \
                        "${_param}" \
                        "$(sed -n "s/^cmdline.${_param}=//p" "${CMDLINE_OWNERS_FILE}" | head -1)"
                    fi
                    ;;
                add|replace)
                    if [[ "${_cmdline_backend}" == "none" ]]; then
                        warn "${_param}: carregador de boot desconhecido (sem kernelstub, /etc/default/grub ou /etc/kernel/cmdline) — ponha à mão no cmdline do kernel, no arquivo do seu carregador: ${_token}"
                        if [[ -n "${_removes}" ]]; then
                            warn "  (tirando antes o(s) token(s): ${_removes} — o kernel respeita SÓ UM usbcore.quirks=)"
                        fi
                        continue
                    fi
                    if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
                        if [[ -n "${_removes}" ]]; then
                            _faria_root "tirar do cmdline do kernel, antes de fundir (o kernel respeita SÓ UM usbcore.quirks=): ${_removes}"
                        fi
                        _faria_root "pôr no cmdline do kernel (${_cmdline_backend}): ${_token} — vale no PRÓXIMO boot"
                        continue
                    fi
                    for _rm_tok in ${_removes}; do
                        _cmdline_args+=(--tira "${_rm_tok}")
                    done
                    _cmdline_args+=(--poe "${_token}")
                    _cmdline_pendentes+=("${_param}"$'\t'"${_token}"$'\t'"${_owner}")
                    ;;
            esac
        done <<<"${_cmdline_plan}"
        _cmdline_dono="${ROOT_DIR}/src/hefesto_dualsense4unix/integrations/kernel_cmdline.py"
        if [[ "${#_cmdline_pendentes[@]}" -gt 0 ]]; then
            if ! sudo -n true 2>/dev/null; then
                warn "cmdline: sudo indisponível — NÃO escrito (re-execute ./install.sh)"
            elif sudo python3 -I "${_cmdline_dono}" escrever --backend "${_cmdline_backend}" \
                    "${_cmdline_args[@]}" >/dev/null 2>&1; then
                _register_cmdline_owner "cmdline.backend" "${_cmdline_backend}"
                for _pend in "${_cmdline_pendentes[@]}"; do
                    IFS=$'\t' read -r _param _token _owner <<<"${_pend}"
                    _register_cmdline_owner "cmdline.${_param}" "${_owner}"
                    printf '      %s: %s aplicado em %s (dono: %s) — vale no PRÓXIMO boot\n' \
                        "${_param}" "${_token}" "${_cmdline_backend}" "${_owner}"
                done
                _cmdline_changed=1
            else
                warn "cmdline: a escrita em ${_cmdline_backend} falhou — rode: sudo python3 -I ${_cmdline_dono} escrever --backend ${_cmdline_backend} ${_cmdline_args[*]}"
            fi
        fi
        [[ "${_cmdline_changed}" -eq 0 ]] && printf '      nada a mudar no cmdline (estado já garantido; donos em %s)\n' "${CMDLINE_OWNERS_FILE}"
        if [[ "${_cmdline_changed}" -eq 1 ]]; then
            anotar_reinicio_pendente "${_PENDENTE_DO_CMDLINE}"
        fi
    fi
fi

step "3e-trava" "a trava comum do rádio (o watchdog root e o daemon no mesmo arquivo)"
install_trava_do_radio_host

step "3e-bis" "Bluetooth mais resistente a quedas (vigia do bluetoothd + cópia dos pareamentos)"
install_bt_resilience_host

step "3e-ter" "mover controle entre adaptadores Bluetooth sem pedir senha"
install_bt_ponte_privilegiada_host

step "3e-ter-bis" "a placa de vídeo acordada enquanto um jogo vive"
install_placa_acordada_host

step "3e-quater" "as entradas USB do gabinete (tabela SMBIOS 8 + barramento)"
install_censo_do_gabinete_host

_bz_veredito() {
    local vivo="$1" baseline="$2" alvo="$3"
    local nome marca pkg ver do_dpkg=0 perguntadas=0
    local faltam=() atras=()
    if [[ -z "${vivo}" || ! -f "${vivo}" ]]; then
        printf 'sem-binario\t\n'
        return 0
    fi
    while IFS=$'\t' read -r nome marca; do
        [[ -n "${marca}" ]] || continue
        perguntadas=$((perguntadas + 1))
        grep -a -q -F -- "${marca}" "${vivo}" 2>/dev/null || faltam+=("${nome}")
    done < <(sed -n 's/^MARCA_\([^=]*\)=\(.*\)$/\1\t\2/p' "${baseline}" 2>/dev/null)
    if [[ "${perguntadas}" -eq 0 ]]; then
        printf 'sem-marcas\t%s\n' "${baseline}"
        return 0
    fi
    dpkg -S "${vivo}" >/dev/null 2>&1 && do_dpkg=1
    if [[ "${#faltam[@]}" -gt 0 ]]; then
        if [[ "${do_dpkg}" -eq 1 ]]; then
            printf 'precisa\t%s\n' "${faltam[*]}"
        else
            printf 'fora-do-dpkg\t%s\n' "${faltam[*]}"
        fi
        return 0
    fi
    if [[ "${do_dpkg}" -eq 1 ]]; then
        for pkg in bluez bluez-cups libbluetooth3; do
            ver="$(dpkg-query -W -f='${Version}' "${pkg}" 2>/dev/null || true)"
            [[ -n "${ver}" ]] || continue
            if dpkg --compare-versions "${ver}" lt "${alvo}" 2>/dev/null; then
                atras+=("${pkg}=${ver}")
            fi
        done
    fi
    if [[ "${#atras[@]}" -gt 0 ]]; then
        printf 'atras\t%s\n' "${atras[*]}"
    else
        printf 'curado\t\n'
    fi
}

_bz_maior_do_archive() {
    local pkg="$1" linhas v maior=""
    linhas="$(apt-cache madison "${pkg}" 2>/dev/null || true)"
    while IFS= read -r v; do
        [[ -n "${v}" && "${v}" != *~hefesto* ]] || continue
        if [[ -z "${maior}" ]] || dpkg --compare-versions "${v}" gt "${maior}" 2>/dev/null; then
            maior="${v}"
        fi
    done < <(awk -F'|' '{ gsub(/[[:space:]]/, "", $2); print $2 }' <<<"${linhas}")
    printf '%s\n' "${maior}"
}

if [[ "${SKIP_UDEV}" -eq 0 ]] && command -v dpkg-query >/dev/null 2>&1 \
   && command -v dpkg >/dev/null 2>&1 && command -v sudo >/dev/null 2>&1; then
    step "3f" "BlueZ corrigido (5.87 com as correções de segurança: sem os travamentos, o laço de reconexão e a queda por buffer cheio)"
    _BZ_TARGET="5.87-0ubuntu0.1~hefesto24.04.5"
    _bz_baseline="${ROOT_DIR}/assets/bluez-backport/BASELINE"
    _bz_dir="${HOME}/.cache/hefesto-dualsense4unix/bluez-backport"
    _bz_vivo="$(
        systemctl show bluetooth.service -p ExecStart --value 2>/dev/null \
            | grep -oE 'path=[^ ]+' | head -1 | cut -d= -f2
    )" || true
    if [[ -z "${_bz_vivo}" ]]; then
        _bz_lista="$(dpkg -L bluez 2>/dev/null || true)"
        _bz_vivo="$(grep -m1 '/bluetoothd$' <<<"${_bz_lista}" || true)"
    fi
    IFS=$'\t' read -r _bz_ver _bz_det <<<"$(_bz_veredito "${_bz_vivo}" "${_bz_baseline}" "${_BZ_TARGET}")"
    case "${_bz_ver}" in
        curado)
            printf '      o bluetoothd em execução (%s) já traz as curas do backport — nada a fazer\n' "${_bz_vivo}"
            ;;
        sem-binario)
            printf '      bluetoothd não encontrado (nem na unit, nem no pacote bluez) — passo pulado\n'
            ;;
        sem-marcas)
            warn "não sei conferir as curas do backport: ${_bz_det} não traz nenhuma linha MARCA_ — passo pulado (o bluetoothd de agora segue)"
            ;;
        fora-do-dpkg)
            warn "o bluetoothd em execução (${_bz_vivo}) não é do dpkg e não traz ${_bz_det} — trocar o pacote não troca o que o systemd executa; reconstrua esse binário com as curas (scripts/construir_bluez_backport.sh traz a receita) ou volte a unit para o do pacote"
            ;;
        precisa|atras)
            if [[ "${_bz_ver}" == "precisa" ]]; then
                printf '      o bluetoothd em execução (%s) não traz %s — o backport %s traz\n' \
                    "${_bz_vivo}" "${_bz_det}" "${_BZ_TARGET}"
            else
                printf '      o bluetoothd já traz as curas, mas %s está abaixo do alvo %s\n' \
                    "${_bz_det}" "${_BZ_TARGET}"
            fi
            _bz_sums="${_bz_dir}/SHA256SUMS"
            _bz_arch="$(dpkg --print-architecture 2>/dev/null || echo amd64)"
            _bz_debs=()
            _bz_ok=1
            for _bz_pkg in libbluetooth3 bluez bluez-cups; do
                _bz_bn="${_bz_pkg}_${_BZ_TARGET}_${_bz_arch}.deb"
                _bz_sum="$(awk -v bn="${_bz_bn}" '{ n = $2; sub(/^.*\//, "", n); if (n == bn) { print $1; exit } }' "${_bz_sums}" 2>/dev/null || true)"
                _bz_actual="$(sha256sum "${_bz_dir}/${_bz_bn}" 2>/dev/null | awk '{print $1}' || true)"
                if [[ -z "${_bz_sum}" || -z "${_bz_actual}" || "${_bz_sum}" != "${_bz_actual}" ]]; then
                    _bz_ok=0
                    break
                fi
                _bz_debs+=("${_bz_dir}/${_bz_bn}")
            done
            if [[ "${_bz_ok}" -eq 0 ]]; then
                warn "o backport ${_BZ_TARGET} não está inteiro (e conferido pelo SHA256SUMS) em ${_bz_dir} — o bluetoothd de agora segue"
                printf '      como gerar: scripts/construir_bluez_backport.sh (uns 3 minutos; não instala nada — depois rode ./install.sh de novo)\n'
            elif [[ "${DRY_RUN:-0}" -eq 1 ]]; then
                _faria "gravar ${_bz_dir}/VERSOES-ANTERIORES.txt (o manifesto que o uninstall usa para devolver o BlueZ de origem — com a versão que o archive SERVE)"
                _faria_root "instalar os .debs do backport do BlueZ ${_BZ_TARGET} (libbluetooth3, bluez, bluez-cups) — o postinst do PRÓPRIO pacote REINICIA o bluetoothd e os controles por Bluetooth caem até reconectar"
            elif ! sudo -n true 2>/dev/null; then
                warn "sudo recusado — passo do backport bluez pulado (re-execute ./install.sh)"
            elif _avisa_pacote_a_meio "o backport do BlueZ ${_BZ_TARGET}"; then
                printf '      depois, rode ./install.sh de novo (os .debs ficam em %s)\n' "${_bz_dir}"
            else
                printf '\n      >>> AVISO: aplicar o backport do bluez REINICIA o bluetoothd\n'
                printf '          (os controles BT caem até reconectar; se algum não voltar,\n'
                printf '          aperte o PS dele). Na migração 5.72 -> 5.8x os bonds antigos\n'
                printf '          se perdiam (reparear uma vez); entre revisões do 5.86 não se\n'
                printf '          mediu perda, e do 5.86 para o 5.87 a bancada confere. É a ÚNICA exceção à regra de nunca reiniciar o\n'
                printf '          serviço: quem reinicia é o postinst do PRÓPRIO pacote bluez.\n\n'
                ask_yn "aplicar o backport agora?" "${AUTO_YES}" "y"
                if [[ "${REPLY,,}" =~ ^y ]]; then
                    if [[ ! -f "${_bz_dir}/VERSOES-ANTERIORES.txt" ]]; then
                        _bz_reg="$(
                            for _bz_pkg in bluez bluez-cups "libbluetooth3:${_bz_arch}"; do
                                _bz_v="$(dpkg-query -W -f='${Version}' "${_bz_pkg}" 2>/dev/null || true)"
                                [[ -n "${_bz_v}" ]] || continue
                                if [[ "${_bz_v}" == *~hefesto* ]]; then
                                    _bz_v="$(_bz_maior_do_archive "${_bz_pkg%%:*}")"
                                fi
                                [[ -n "${_bz_v}" ]] && printf '%s\t%s\n' "${_bz_pkg}" "${_bz_v}"
                            done
                        )" || _bz_reg=""
                        if [[ -n "${_bz_reg}" ]]; then
                            printf '%s\n' "${_bz_reg}" > "${_bz_dir}/VERSOES-ANTERIORES.txt"
                            printf '      versões anteriores gravadas em %s\n' "${_bz_dir}/VERSOES-ANTERIORES.txt"
                        else
                            warn "não consegui registrar as versões anteriores do BlueZ — o restore do uninstall não vai cobrir bluez/libbluetooth3"
                        fi
                    fi
                    if sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y --allow-downgrades \
                            -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold" \
                            "${_bz_debs[@]}" >/dev/null 2>&1; then
                        printf '      backport %s aplicado — o bluetoothd reiniciou; os controles BT voltam sozinhos ou com o PS\n' "${_BZ_TARGET}"
                    else
                        warn "apt-get install do backport falhou — rode manualmente com os .debs em ${_bz_dir}"
                    fi
                else
                    printf '      pulado a pedido — o bluetoothd de agora segue\n'
                fi
            fi
            ;;
    esac
fi

_pw_versao_ii() {
    dpkg-query -W -f='${db:Status-Abbrev}|${Version}\n' "$1" 2>/dev/null \
        | awk -F'|' '$1 ~ /^ii/ { print $2; exit }' || true
}

_pw_veredito() {
    local alvo_pw="$1" alvo_wp="$2" pw wp
    pw="$(_pw_versao_ii libpipewire-0.3-modules)"
    if [[ -z "${pw}" ]]; then
        printf 'sem-pipewire\n'
        return 0
    fi
    wp="$(_pw_versao_ii wireplumber)"
    if dpkg --compare-versions "${pw}" lt "${alvo_pw}" 2>/dev/null \
        || { [[ -n "${wp}" ]] && dpkg --compare-versions "${wp}" lt "${alvo_wp}" 2>/dev/null; }; then
        printf 'precisa\n'
    else
        printf 'curado\n'
    fi
}

_pw_debs_da_maquina() {
    local dir="$1" alvo_pw="$2" alvo_wp="$3" sha nome resto ver pkg atual
    local entram=()
    [[ -s "${dir}/SHA256SUMS" ]] || return 1
    while read -r sha nome; do
        [[ -n "${sha}" ]] || continue
        nome="${nome#\*}"
        nome="${nome##*/}"
        resto="${nome#*_}"
        ver="${resto%_*}"
        [[ "${nome}" == *.deb && ( "${ver}" == "${alvo_pw}" || "${ver}" == "${alvo_wp}" ) ]] || return 1
        atual="$(sha256sum "${dir}/${nome}" 2>/dev/null | awk '{ print $1 }' || true)"
        [[ -n "${atual}" && "${atual}" == "${sha}" ]] || return 1
        pkg="${nome%%_*}"
        atual="$(_pw_versao_ii "${pkg}")"
        [[ -n "${atual}" ]] || continue
        dpkg --compare-versions "${atual}" lt "${ver}" 2>/dev/null || continue
        entram+=("${dir}/${nome}")
    done < "${dir}/SHA256SUMS"
    [[ "${#entram[@]}" -eq 0 ]] || printf '%s\n' "${entram[@]}"
}

_pw_versoes_anteriores() {
    local deb pkg estado nome ver
    for deb in "$@"; do
        pkg="${deb##*/}"
        pkg="${pkg%%_*}"
        while IFS='|' read -r estado nome ver; do
            [[ "${estado}" == ii* && -n "${nome}" && -n "${ver}" ]] || continue
            if [[ "${ver}" == *~hefesto* ]]; then
                ver="$(_bz_maior_do_archive "${nome%%:*}")"
                [[ -n "${ver}" ]] || continue
            fi
            printf '%s=%s\n' "${nome}" "${ver}"
        done < <(dpkg-query -W -f='${db:Status-Abbrev}|${binary:Package}|${Version}\n' "${pkg}" 2>/dev/null || true)
    done
}

_pw_o_que_sairia() {
    local sim arch p
    arch="$(dpkg --print-architecture 2>/dev/null || echo amd64)"
    sim="$(LC_ALL=C apt-get install -s "$@" 2>&1)" || return 1
    while read -r p; do
        case "${p%:"${arch}"}" in
            libspa-0.2-libcamera|pipewire-libcamera) ;;
            *) printf '%s\n' "${p}" ;;
        esac
    done < <(awk '$1 == "Remv" { print $2 }' <<<"${sim}")
}

_pw_steam_aberta() {
    pgrep -u "$(id -u)" -x steam >/dev/null 2>&1 \
        || pgrep -u "$(id -u)" -x steamwebhelper >/dev/null 2>&1
}

install_pipewire_da_casa() {
    local baseline="${ROOT_DIR}/assets/pipewire-backport/BASELINE"
    local pref="${ROOT_DIR}/assets/pipewire-backport/apt/hefesto-pipewire.pref"
    local construtor="${ROOT_DIR}/scripts/construir_pipewire_backport.sh"
    local cache="${HOME}/.cache/hefesto-dualsense4unix"
    local dir="${cache}/pipewire-backport"
    local log="${cache}/pipewire-construir.log"
    local alvo_pw alvo_wp rc lista sairia registro
    local debs=()
    alvo_pw="$(sed -n 's/^PW_REVISAO=//p' "${baseline}" 2>/dev/null || true)"
    alvo_wp="$(sed -n 's/^WP_REVISAO=//p' "${baseline}" 2>/dev/null || true)"
    if [[ -z "${alvo_pw}" || -z "${alvo_wp}" ]]; then
        warn "${baseline} não diz as revisões do PipeWire da casa — passo pulado (o PipeWire de agora segue)"
        return 0
    fi
    case "$(_pw_veredito "${alvo_pw}" "${alvo_wp}")" in
        curado)
            printf '      o PipeWire desta máquina já tem a cura do metadata (o %s ou mais novo) — nada a fazer\n' "${alvo_pw}"
            return 0
            ;;
        sem-pipewire)
            printf '      o PipeWire desta máquina não é do dpkg — passo pulado (o doctor diz se ele tem a cura)\n'
            return 0
            ;;
    esac
    printf '      o PipeWire desta máquina é o %s, sem a cura do metadata; a casa tem o %s e o WirePlumber %s\n' \
        "$(_pw_versao_ii libpipewire-0.3-modules)" "${alvo_pw}" "${alvo_wp}"
    if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
        _faria "construir o PipeWire ${alvo_pw} e o WirePlumber ${alvo_wp} em ${dir} (scripts/construir_pipewire_backport.sh, uns 5 minutos, sem sudo)"
        _faria "gravar ${dir}/VERSOES-ANTERIORES.txt (o caminho de volta, só com os pacotes que trocam)"
        _faria_root "fixar a prioridade do apt em /etc/apt/preferences.d/hefesto-pipewire (o apt fica com a versão mais nova, a da casa ou a da distro)"
        _faria_root "instalar só os pacotes do PipeWire e do WirePlumber que a máquina já tem, conferidos pelo SHA256SUMS — com a Steam aberta, o passo recusa"
        _faria "REINICIAR o som da sessão (pipewire, pipewire-pulse e wireplumber): os controles perdem o som e o microfone por alguns segundos"
        return 0
    fi
    mkdir -p "${cache}"
    printf '      construindo pelo scripts/construir_pipewire_backport.sh (uns 5 minutos na primeira vez; o registro fica em %s)\n' "${log}"
    rc=0
    HEFESTO_PIPEWIRE_CACHE="${cache}" bash "${construtor}" > "${log}" 2>&1 || rc=$?
    if [[ "${rc}" -eq 3 ]]; then
        warn "faltam dependências de build do PipeWire da casa — o PipeWire de agora segue"
        tail -n 15 "${log}" 2>/dev/null | sed 's/^/      /' || true
        printf '      a ordem de instalar está na receita: docs/usage/receita-backport-pipewire.md (depois rode ./install.sh de novo)\n'
        return 0
    elif [[ "${rc}" -ne 0 ]]; then
        warn "a construção do PipeWire da casa parou (código ${rc}; o registro está em ${log}) — o PipeWire de agora segue"
        return 0
    fi
    if ! lista="$(_pw_debs_da_maquina "${dir}" "${alvo_pw}" "${alvo_wp}")"; then
        warn "a entrega em ${dir} não confere pelo SHA256SUMS com as revisões ${alvo_pw} e ${alvo_wp} — nada foi instalado (o PipeWire de agora segue)"
        return 0
    fi
    if [[ -z "${lista}" ]]; then
        printf '      nenhum pacote da entrega está instalado abaixo da casa nesta máquina — nada a trocar\n'
        return 0
    fi
    mapfile -t debs <<<"${lista}"
    if _pw_steam_aberta; then
        warn "a Steam está aberta — o PipeWire da casa NÃO foi instalado: trocar o PipeWire reinicia o som, e o reinício do WirePlumber com a Steam aberta é o que a deixa sem fechar"
        printf '      feche a Steam pelo menu e rode ./install.sh de novo (os pacotes já estão construídos em %s)\n' "${dir}"
        return 0
    fi
    if ! sudo -n true 2>/dev/null; then
        warn "sudo recusado — passo do PipeWire da casa pulado (re-execute ./install.sh)"
        return 0
    fi
    if _avisa_pacote_a_meio "o PipeWire da casa"; then
        printf '      depois, rode ./install.sh de novo (os pacotes já estão construídos em %s)\n' "${dir}"
        return 0
    fi
    if ! sairia="$(_pw_o_que_sairia "${debs[@]}")"; then
        warn "o apt não aceita trocar o PipeWire por estes pacotes nesta máquina — nada foi instalado; a simulação é: apt-get install -s ${debs[*]}"
        return 0
    fi
    if [[ -n "${sairia}" ]]; then
        warn "instalar o PipeWire da casa tiraria da máquina: $(tr '\n' ' ' <<<"${sairia}")— nada foi instalado (o PipeWire de agora segue)"
        return 0
    fi
    printf '\n      >>> AVISO: instalar o PipeWire da casa REINICIA o som da sessão\n'
    printf '          (os controles perdem o som e o microfone por alguns segundos, e um\n'
    printf '          jogo aberto pode perder a saída até ser reaberto).\n\n'
    ask_yn "instalar o PipeWire da casa agora?" "${AUTO_YES}" "y"
    if [[ ! "${REPLY,,}" =~ ^y ]]; then
        printf '      pulado a pedido — o PipeWire de agora segue\n'
        return 0
    fi
    if [[ ! -f "${dir}/VERSOES-ANTERIORES.txt" ]]; then
        registro="$(_pw_versoes_anteriores "${debs[@]}")" || registro=""
        if [[ -n "${registro}" ]]; then
            printf '%s\n' "${registro}" > "${dir}/VERSOES-ANTERIORES.txt"
            printf '      versões anteriores gravadas em %s\n' "${dir}/VERSOES-ANTERIORES.txt"
        else
            warn "não consegui registrar as versões anteriores do PipeWire — a volta pela receita não vai cobrir estes pacotes"
        fi
    fi
    if ! sudo install -m 0644 "${pref}" /etc/apt/preferences.d/hefesto-pipewire 2>/dev/null; then
        warn "não consegui gravar /etc/apt/preferences.d/hefesto-pipewire — no Pop!_OS, o próximo apt upgrade voltaria o PipeWire para o da distro"
    fi
    if sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y \
            -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold" \
            "${debs[@]}" >/dev/null 2>&1; then
        printf '      PipeWire %s e WirePlumber %s instalados (%d pacotes)\n' "${alvo_pw}" "${alvo_wp}" "${#debs[@]}"
        if reiniciar_o_som_da_sessao; then
            printf '      som reiniciado — confira o som e o microfone de cada controle\n'
            case "${SOM_PAINEL_DO_COSMIC}" in
                voltou) printf '      o painel do COSMIC voltou a mostrar o som (cosmic-settings-daemon religado)\n' ;;
                nao-voltou) warn "o painel do COSMIC ficou sem o som — rode: ${SOM_CURA_DO_PAINEL}" ;;
            esac
        else
            warn "não consegui reiniciar o som — rode: systemctl --user restart pipewire pipewire-pulse wireplumber"
        fi
    else
        warn "apt-get install do PipeWire da casa falhou — rode à mão com os .deb em ${dir} (a receita: docs/usage/receita-backport-pipewire.md)"
    fi
}

if [[ "${SKIP_UDEV}" -eq 0 ]] && command -v dpkg-query >/dev/null 2>&1 \
   && command -v dpkg >/dev/null 2>&1 && command -v sudo >/dev/null 2>&1; then
    step "3f-bis" "PipeWire corrigido (1.6.9 com o WirePlumber 0.5.18: a Steam fecha mesmo depois de o som reiniciar)"
    install_pipewire_da_casa
fi

step "3g" "agente de pareamento Bluetooth sempre de pé (evita o pareamento pela metade)"
install_bt_agent_host

if [[ "${SKIP_UDEV}" -eq 0 ]] && command -v sudo >/dev/null 2>&1; then
    step "3h" "o controle físico escondido dos jogos, entregue ao Hefesto (sem jogador duplicado)"
    install_broker_host
fi

step "3i" "módulo hid-nintendo corrigido (DKMS: conexão Bluetooth mais resistente)"
install_dkms_hid_nintendo_host

step "3j" "módulo rtw88_usb corrigido (DKMS: o adaptador Wi-Fi USB sem aparelho fantasma)"
install_dkms_rtw88_usb_host

step "3j2" "vigia do dongle Wi-Fi USB (scan de fundo + travamento mudo)"
install_wifi_usb_host

step "3j3" "modo desempenho (o perfil de energia em Performance, se a pessoa quiser)"
install_desempenho_host

step "3k" "módulo hid-playstation corrigido (DKMS: o microfone pelo Bluetooth e vários controles no mesmo adaptador)"
install_dkms_hid_playstation_host

step "3k2" "uhid com contrapressão (OPT-IN: --uhid-contrapressao)"
install_dkms_uhid_host

step "3k3" "usb_f_hid corrigido (DKMS: a resposta do GET_REPORT dos pads USB virtuais)"
install_dkms_usb_f_hid_host

step "3l" "regenerar o initramfs se algum módulo DKMS mudou"
flush_initramfs_host

step "4/11" "atalho de aplicativo e launcher"

ICON_HICOLOR_BASE="${HOME}/.local/share/icons/hicolor"
ICON_SIZES="16 22 24 32 48 64 96 128 192 256 512"

if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
    _faria "copiar o ícone para ${ICON_TARGET}"
    if command -v convert >/dev/null 2>&1; then
        _faria "gerar o ícone em ${ICON_SIZES} px sob ${ICON_HICOLOR_BASE}/, e o pixmap legado em ${HOME}/.local/share/pixmaps/"
        _faria "apagar ${ICON_HICOLOR_BASE}/scalable/apps/${APP_ID}.svg, se houver (o SVG placeholder de instalações antigas — o simbólico, que tem outro nome, NÃO é tocado)"
    else
        _nao_faria "gerar os tamanhos menores do ícone: falta o ImageMagick (convert) nesta máquina"
    fi
else
mkdir -p "${ICON_TARGET_DIR}"
cp -f "${ICON_SRC}" "${ICON_TARGET}" \
    || warn "ícone não copiado (${ICON_SRC} ausente?) — o menu pode mostrar um ícone genérico"
mkdir -p "$(dirname "${DESKTOP_TARGET}")"

if command -v convert >/dev/null 2>&1; then
    printf '      gerando icone multi-res do PNG 256x256 (ImageMagick Lanczos)\n'
    for size in ${ICON_SIZES}; do
        target_dir="${ICON_HICOLOR_BASE}/${size}x${size}/apps"
        mkdir -p "${target_dir}"
        convert "${ICON_SRC}" -filter Lanczos -resize "${size}x${size}" \
            "${target_dir}/${APP_ID}.png" 2>/dev/null || true
    done
    mkdir -p "${HOME}/.local/share/pixmaps"
    cp -f "${ICON_SRC}" "${HOME}/.local/share/pixmaps/${APP_ID}.png"
    rm -f "${ICON_HICOLOR_BASE}/scalable/apps/${APP_ID}.svg"
else
    printf '      aviso: ImageMagick (convert) ausente — so 256x256 PNG\n'
    printf '             instale: sudo apt install imagemagick\n'
fi
fi

ICON_SIMBOLICO_SRC="${ROOT_DIR}/assets/simbolico/hefesto-dualsense4unix-symbolic.svg"
ICON_SIMBOLICO_DIR="${ICON_HICOLOR_BASE}/symbolic/apps"
if [[ "${DRY_RUN:-0}" -eq 1 && -r "${ICON_SIMBOLICO_SRC}" ]]; then
    _faria "copiar o ícone simbólico da bandeja para ${ICON_SIMBOLICO_DIR}/${APP_ID}-symbolic.svg"
elif [[ -r "${ICON_SIMBOLICO_SRC}" ]]; then
    mkdir -p "${ICON_SIMBOLICO_DIR}"
    cp -f "${ICON_SIMBOLICO_SRC}" "${ICON_SIMBOLICO_DIR}/${APP_ID}-symbolic.svg"
    printf '      ícone simbólico da bandeja instalado (%s-symbolic.svg)\n' "${APP_ID}"
else
    printf '      aviso: %s ausente — a bandeja cai no ícone colorido\n' \
        "assets/simbolico/hefesto-dualsense4unix-symbolic.svg"
fi

if [[ "${DESKTOP_IS_WLROOTS}" -eq 1 ]]; then
    if ! command -v wlrctl >/dev/null 2>&1; then
        printf '\n      Compositor wlroots detectado (XDG_CURRENT_DESKTOP=%s).\n' \
            "${XDG_CURRENT_DESKTOP:-$XDG_SESSION_DESKTOP}"
        printf '      O wlrctl conta ao Hefesto a janela em foco dos apps Wayland\n'
        printf '      nativos (wlr-foreign-toplevel-management).\n\n'
        ask_yn "instalar wlrctl agora?" "${AUTO_YES}" "y"
        if [[ "${REPLY,,}" =~ ^y ]]; then
            if command -v sudo >/dev/null 2>&1; then
                _rc_pkg=0
                run_pkg wlrctl 2>/dev/null || _rc_pkg=$?
                if (( _rc_pkg == 0 )); then
                    printf '      wlrctl instalado (%s)\n' "$(command -v wlrctl)"
                elif (( _rc_pkg == _RC_PACOTE_A_MEIO )); then
                    :
                else
                    warn "wlrctl não esta nos repos deste sistema (Ubuntu <24.04?)"
                    printf '      alternativas:\n'
                    printf '        - pelo gerenciador: %s\n' "$(comando_manual_pkg wlrctl)"
                    printf '        - fonte:  https://git.sr.ht/~brocellous/wlrctl\n'
                fi
            else
                warn "sudo ausente - rode manualmente: $(comando_manual_pkg wlrctl)"
            fi
        fi
    else
        printf '      wlrctl ja instalado (%s) - WlrctlBackend vai detectar.\n' \
            "$(command -v wlrctl)"
    fi
fi

if [[ "${DESKTOP_IS_COSMIC}" -eq 1 ]]; then
    printf '\n'
    printf '      COSMIC detectado (XDG_CURRENT_DESKTOP=%s).\n' \
        "${XDG_CURRENT_DESKTOP:-$XDG_SESSION_DESKTOP}"
    printf '      A troca de perfil pela janela em foco usa o protocolo do\n'
    printf '      próprio COSMIC (zcosmic_toplevel_info_v1): nada a instalar.\n'

    if [[ "${FORCE_XWAYLAND}" -eq 1 ]]; then
        printf '\n      XWayland pedido por --force-xwayland (o default é Wayland nativo).\n'
    fi
fi

if [[ "${FORCE_XWAYLAND}" -eq 1 ]]; then
    _EXEC_LINE="env GDK_BACKEND=x11 HEFESTO_NA_TELA=1 ${ROOT_DIR}/run.sh --gui"
    printf '      .desktop com GDK_BACKEND=x11 (--force-xwayland)\n'
else
    _EXEC_LINE="env HEFESTO_NA_TELA=1 ${ROOT_DIR}/run.sh --gui"
fi

_DESKTOP_FONTE="${ROOT_DIR}/packaging/${APP_ID}.desktop"
if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
    _faria "escrever o atalho ${DESKTOP_TARGET} com Exec=${_EXEC_LINE}"
    _faria "escrever o lançador ${LAUNCHER} (abre a interface desprendida do terminal)"
    _faria "atualizar o cache de ícones e o banco de atalhos do sistema (gtk-update-icon-cache, update-desktop-database)"
elif [[ -r "${_DESKTOP_FONTE}" ]]; then
    sed -e "s|@RAIZ@|${ROOT_DIR}|g" \
        -e "s|^Exec=.*|Exec=${_EXEC_LINE}|" \
        "${_DESKTOP_FONTE}" > "${DESKTOP_TARGET}"
else
    warn "packaging/${APP_ID}.desktop ausente — atalho escrito no mínimo"
    cat > "${DESKTOP_TARGET}" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Hefesto - DualSense4Unix
GenericName=DualSense Controller
Comment=Gerenciador DualSense para Linux
Exec=${_EXEC_LINE}
Icon=${APP_ID}
Categories=Settings;HardwareSettings;
Terminal=false
StartupNotify=true
StartupWMClass=Hefesto-Dualsense4Unix
DESKTOP
fi

if [[ "${DRY_RUN:-0}" -eq 0 ]]; then
command -v desktop-file-validate >/dev/null 2>&1 \
    && desktop-file-validate "${DESKTOP_TARGET}" >/dev/null 2>&1 || true
command -v gtk-update-icon-cache >/dev/null 2>&1 \
    && gtk-update-icon-cache -q -f "${HOME}/.local/share/icons/hicolor" 2>/dev/null || true
command -v update-desktop-database >/dev/null 2>&1 \
    && update-desktop-database -q "$(dirname "${DESKTOP_TARGET}")" 2>/dev/null || true

_AUTOSTART_DIR="${HOME}/.config/autostart"
_AUTOSTART_TARGET="${_AUTOSTART_DIR}/${APP_ID}-tray.desktop"
_AUTOSTART_FONTE="${ROOT_DIR}/packaging/${APP_ID}-tray.desktop"
_AUTOSTART_LIGADO=true
if grep -qx 'X-GNOME-Autostart-enabled=false' "${_AUTOSTART_TARGET}" 2>/dev/null; then
    _AUTOSTART_LIGADO=false
fi
if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
    _faria "escrever o autostart do tray em ${_AUTOSTART_TARGET} (ligado=${_AUTOSTART_LIGADO})"
elif [[ -r "${_AUTOSTART_FONTE}" ]]; then
    mkdir -p "${_AUTOSTART_DIR}"
    sed -e "s|@RAIZ@|${ROOT_DIR}|g" \
        -e "s|^X-GNOME-Autostart-enabled=.*|X-GNOME-Autostart-enabled=${_AUTOSTART_LIGADO}|" \
        "${_AUTOSTART_FONTE}" > "${_AUTOSTART_TARGET}"
    printf '      autostart do tray: %s (ligado=%s)\n' "${_AUTOSTART_TARGET}" "${_AUTOSTART_LIGADO}"
else
    warn "packaging/${APP_ID}-tray.desktop ausente — o tray não subirá sozinho"
fi

mkdir -p "${BIN_DIR}"
cat > "${LAUNCHER}" <<LAUNCH
#!/usr/bin/env bash
# O console script do mesmo nome (pyproject.toml) abre a MESMA interface, por
# interface.abrir:entrada. Este arquivo o SOBRESCREVE de propósito: ele
# desprende a janela do terminal (setsid+nohup) e passa pelo run.sh, que
# cuida do XWayland e do pixbuf antes de o Python subir. HEFESTO_NA_TELA nasce
# 1 (a janela vai para a tela de quem clicou); HEFESTO_NA_TELA=0 no ambiente
# devolve a guarda, para quem chama este lançador sem tela.
HEFESTO_NA_TELA="\${HEFESTO_NA_TELA:-1}" setsid nohup "${ROOT_DIR}/run.sh" --gui "\$@" </dev/null >/dev/null 2>&1 &
disown 2>/dev/null || true
LAUNCH
chmod +x "${LAUNCHER}"
fi
ok

readonly GLYPHS_SRC="${ROOT_DIR}/assets/glyphs"
readonly GLYPHS_TARGET="${HOME}/.local/share/hefesto-dualsense4unix/glyphs"

if [[ "${DRY_RUN:-0}" -eq 1 && -d "${GLYPHS_SRC}" ]]; then
    _faria "copiar os glifos dos botões (assets/glyphs/*.svg) para ${GLYPHS_TARGET}/"
elif [[ -d "${GLYPHS_SRC}" ]]; then
    mkdir -p "${GLYPHS_TARGET}"
    cp -f "${GLYPHS_SRC}"/*.svg "${GLYPHS_TARGET}/" 2>/dev/null || \
        warn "nenhum glifo copiado de ${GLYPHS_SRC} — a interface cai no desenho embutido"
fi

readonly LAUNCH_WRAPPER_SRC="${ROOT_DIR}/assets/hefesto-launch.sh"
readonly LAUNCH_WRAPPER_TARGET="${HOME}/.local/share/hefesto-dualsense4unix/bin/hefesto-launch"
if [[ "${DRY_RUN:-0}" -eq 1 && -f "${LAUNCH_WRAPPER_SRC}" ]]; then
    _faria "instalar o wrapper de launch da Steam em ${LAUNCH_WRAPPER_TARGET}"
elif [[ -f "${LAUNCH_WRAPPER_SRC}" ]]; then
    install -Dm755 "${LAUNCH_WRAPPER_SRC}" "${LAUNCH_WRAPPER_TARGET}"
    mkdir -p "${HOME}/.local/state/hefesto-dualsense4unix/launch_env"
else
    warn "assets/hefesto-launch.sh ausente — wrapper de launch da Steam não instalado"
fi

readonly CAMADAS_SRC="${ROOT_DIR}/src/hefesto_dualsense4unix/integrations/camadas_vulkan.py"
readonly CAMADAS_TARGET="${HOME}/.local/share/hefesto-dualsense4unix/bin/hefesto-camadas"
if [[ "${DRY_RUN:-0}" -eq 1 && -f "${CAMADAS_SRC}" ]]; then
    _faria "instalar o curador de camadas Vulkan em ${CAMADAS_TARGET}"
elif [[ -f "${CAMADAS_SRC}" ]]; then
    install -Dm755 "${CAMADAS_SRC}" "${CAMADAS_TARGET}"
else
    warn "camadas_vulkan.py ausente — as sobreposições Vulkan não vão sair no lançamento dos jogos"
fi

readonly AUDIO_KS_SRC="${ROOT_DIR}/src/hefesto_dualsense4unix/integrations/audio_ks_dualsense.py"
readonly AUDIO_KS_TARGET="${HOME}/.local/share/hefesto-dualsense4unix/bin/hefesto-audio-ks"
if [[ "${DRY_RUN:-0}" -eq 1 && -f "${AUDIO_KS_SRC}" ]]; then
    _faria "instalar o curador do device de áudio KS em ${AUDIO_KS_TARGET}"
elif [[ -f "${AUDIO_KS_SRC}" ]]; then
    install -Dm755 "${AUDIO_KS_SRC}" "${AUDIO_KS_TARGET}"
else
    warn "audio_ks_dualsense.py ausente — a háptica nativa do DualSense não chega aos jogos RE Engine"
fi

readonly PECA_GDK_PINO="${ROOT_DIR}/assets/gdk-runtime/pino.txt"
readonly PECA_GDK_TARGET="${HOME}/.local/share/hefesto-dualsense4unix/wine/x86_64-windows/xgameruntime.dll"
readonly PECA_GAMEINPUT_TARGET="${HOME}/.local/share/hefesto-dualsense4unix/wine/nativa/gameinput.dll"
_peca_gdk_pino() { sed -n "s/^$1=//p" "${PECA_GDK_PINO}" | head -n 1; }
_peca_gdk_sha() { sha256sum "$1" 2>/dev/null | cut -d' ' -f1; }
_peca_gdk_instalar() {
    local nome="$1" chave_sha="$2" chave_url="$3" arquivo="$4" alvo="$5"
    local _peca_sha_pino _peca_versao _peca_url _peca_tmp _peca_ok
    _peca_sha_pino="$(_peca_gdk_pino "${chave_sha}")"
    if [[ -z "${_peca_sha_pino}" ]]; then
        warn "o pino não traz ${chave_sha} — ${nome} ficou de fora"
        return 0
    fi
    if [[ -f "${alvo}" && "$(_peca_gdk_sha "${alvo}")" == "${_peca_sha_pino}" ]]; then
        printf '      %s: já no lugar, e bate com o pino\n' "${nome}"
        return 0
    fi
    _peca_versao="$(sed -n 's/^version *= *"\(.*\)"/\1/p' "${ROOT_DIR}/pyproject.toml" | head -n 1)"
    _peca_url="$(_peca_gdk_pino "${chave_url}")"
    _peca_url="${_peca_url//\{versao\}/${_peca_versao}}"
    _peca_tmp="$(mktemp -d)"
    _peca_ok=""
    if command -v curl >/dev/null 2>&1 \
       && curl -fsSL --max-time 60 -o "${_peca_tmp}/${arquivo}" "${_peca_url}" 2>/dev/null \
       && [[ "$(_peca_gdk_sha "${_peca_tmp}/${arquivo}")" == "${_peca_sha_pino}" ]]; then
        _peca_ok="${_peca_tmp}/${arquivo}"
    elif command -v x86_64-w64-mingw32-gcc-posix >/dev/null 2>&1 \
       && bash "${ROOT_DIR}/assets/gdk-runtime/construir.sh" "${_peca_tmp}/construida" >/dev/null 2>&1 \
       && [[ "$(_peca_gdk_sha "${_peca_tmp}/construida/${arquivo}")" == "${_peca_sha_pino}" ]]; then
        _peca_ok="${_peca_tmp}/construida/${arquivo}"
    fi
    if [[ -n "${_peca_ok}" ]]; then
        install -Dm644 "${_peca_ok}" "${alvo}"
        ok
    else
        warn "${nome} ficou de fora: o download (${_peca_url}) e a compilação local não deram o sha256 do pino — os jogos GDK abrem sem isso"
    fi
    rm -rf "${_peca_tmp}"
}
if [[ "${DRY_RUN:-0}" -eq 1 && -f "${PECA_GDK_PINO}" ]]; then
    _faria "pôr a peça GDK em ${PECA_GDK_TARGET} e o GameInput em ${PECA_GAMEINPUT_TARGET} (baixados pelo pino ou compilados aqui, se o sha256 bater)"
elif [[ -f "${PECA_GDK_PINO}" ]]; then
    _peca_gdk_instalar "a peça GDK" sha256 url xgameruntime.dll "${PECA_GDK_TARGET}"
    _peca_gdk_instalar "o GameInput do Hefesto" gameinput_sha256 gameinput_url gameinput.dll "${PECA_GAMEINPUT_TARGET}"
else
    warn "assets/gdk-runtime/pino.txt ausente — a peça GDK não foi instalada"
fi

if [[ "${DRY_RUN:-0}" -eq 1 && -f "${ROOT_DIR}/scripts/install_profiles.sh" ]]; then
    _faria "instalar os perfis de fábrica em ${HOME}/.config/hefesto-dualsense4unix/profiles/ (scripts/install_profiles.sh — os SEUS perfis são preservados)"
elif [[ -f "${ROOT_DIR}/scripts/install_profiles.sh" ]]; then
    bash "${ROOT_DIR}/scripts/install_profiles.sh" "${ROOT_DIR}" \
        || warn "perfis de fábrica não instalados — rode: bash scripts/install_profiles.sh"
fi

readonly LOCALE_SRC="${ROOT_DIR}/locale"
readonly LOCALE_TARGET="${HOME}/.local/share/locale"
if [[ "${DRY_RUN:-0}" -eq 1 && -d "${LOCALE_SRC}" ]]; then
    _faria "copiar os catálogos de tradução (.mo) de locale/ para ${LOCALE_TARGET}/"
elif [[ -d "${LOCALE_SRC}" ]]; then
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

if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
    if [[ "${NO_FONTS}" -eq 1 ]]; then
        _nao_faria "instalar as fontes da identidade visual (--no-fonts) — a interface usa o fallback do CSS"
    else
        _faria "instalar as fontes Space Grotesk e JetBrains Mono (pacote da distro primeiro; só se não houver, download PINADO e conferido por SHA-256) — scripts/install_fonts.sh"
    fi
elif [[ "${NO_FONTS}" -eq 1 ]]; then
    printf '      fontes: pulado (--no-fonts) — a interface usa o fallback do CSS\n'
elif [[ ! -r "${ROOT_DIR}/scripts/install_fonts.sh" ]]; then
    warn "scripts/install_fonts.sh ausente — fontes da identidade visual puladas"
else
    if [[ "${AUTO_YES}" -eq 1 ]]; then
        bash "${ROOT_DIR}/scripts/install_fonts.sh" --yes \
            || printf '      fontes: incompletas — rode: bash scripts/install_fonts.sh\n'
    else
        bash "${ROOT_DIR}/scripts/install_fonts.sh" \
            || printf '      fontes: incompletas — rode: bash scripts/install_fonts.sh\n'
    fi
fi

step "4f" "teclado na tela do L3 (wvkbd em Wayland, onboard em X11)"
install_osk_host

step "5/11" "symlink ${BIN_DIR}/hefesto-dualsense4unix"
if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
    _faria "criar o link ${BIN_DIR}/hefesto-dualsense4unix -> ${VENV_DIR}/bin/hefesto-dualsense4unix"
    _faria "criar o link ${BIN_DIR}/hefesto-launch -> ${LAUNCH_WRAPPER_TARGET}"
    _faria "copiar a chave de desligar tudo para ${BIN_DIR}/hefesto-chave"
else
ln -sf "${VENV_DIR}/bin/hefesto-dualsense4unix" "${BIN_DIR}/hefesto-dualsense4unix"
if [[ -x "${LAUNCH_WRAPPER_TARGET}" ]]; then
    ln -sf "${LAUNCH_WRAPPER_TARGET}" "${BIN_DIR}/hefesto-launch"
fi

if [[ -f "${ROOT_DIR}/scripts/hefesto-chave.sh" ]]; then
    install -m 755 "${ROOT_DIR}/scripts/hefesto-chave.sh" "${BIN_DIR}/hefesto-chave"
fi
fi
ok

step "6/11" "daemon systemd --user"

enable_daemon=0

if [[ "${SKIP_SYSTEMD}" -eq 1 ]]; then
    printf '      pulado (--no-systemd)\n'
else
    if [[ "${ENABLE_AUTOSTART}" -eq 1 ]]; then
        enable_daemon=1
    else
        ask_yn "habilitar auto-start do daemon no boot?" "${AUTO_YES}" "y"
        [[ "${REPLY,,}" =~ ^y ]] && enable_daemon=1
    fi

    cli_args=("install-service")
    [[ "${enable_daemon}" -eq 1 ]] && cli_args+=("--enable")

    if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
        _faria "instalar a unit do daemon pelo CLI (hefesto-dualsense4unix daemon ${cli_args[*]})"
        if [[ "${enable_daemon}" -eq 1 ]]; then
            _faria "habilitar o daemon no boot"
        else
            _nao_faria "habilitar o daemon no boot (você respondeu que não)"
        fi
    elif "${VENV_DIR}/bin/hefesto-dualsense4unix" daemon "${cli_args[@]}" >/dev/null 2>&1; then
        if [[ "${enable_daemon}" -eq 1 ]]; then
            printf '      unit instalada + auto-start habilitado\n'
        else
            printf '      unit instalada (auto-start desativado — subir só quando abrir a GUI)\n'
        fi
    else
        warn "falha ao instalar unit (sem systemd ou assets ausente)"
    fi
fi

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
        USER_UNIT_DIR="${HOME}/.config/systemd/user"
        readonly HOTPLUG_UNIT_TARGET="${USER_UNIT_DIR}/hefesto-dualsense4unix-gui-hotplug.service"

        if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
            _faria "copiar ${HOTPLUG_UNIT_TARGET} e habilitá-lo (a janela abre sozinha quando o DualSense é plugado)"
        elif [[ ! -f "${HOTPLUG_UNIT_SRC}" ]]; then
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

step "7a/11" "daemon: unit do systemd (usuário)"
DAEMON_UNIT_SRC="${ROOT_DIR}/assets/hefesto-dualsense4unix.service"
DAEMON_USER_UNIT_DIR="${HOME}/.config/systemd/user"
DAEMON_UNIT_TARGET="${DAEMON_USER_UNIT_DIR}/hefesto-dualsense4unix.service"
DAEMON_UNIT_NAME="hefesto-dualsense4unix.service"
if [[ "${SKIP_SYSTEMD}" -eq 1 ]]; then
    printf '      pulado (--no-systemd)\n'
elif [[ ! -f "${DAEMON_UNIT_SRC}" ]]; then
    warn "unit do daemon ausente em assets/ — reinstale o repo"
elif ! command -v systemctl >/dev/null 2>&1; then
    warn "systemctl ausente — daemon não habilitado (inicie com: hefesto-dualsense4unix daemon start)"
elif [[ "${DRY_RUN:-0}" -eq 1 ]]; then
    if [[ -L "${DAEMON_UNIT_TARGET}" ]] \
       && [[ "$(readlink -f "${DAEMON_UNIT_TARGET}" 2>/dev/null)" == "/dev/null" ]]; then
        _faria "tirar a MÁSCARA da unit do daemon (ela está mascarada por 'hefesto-chave off') antes de gravá-la — sem isto o cp escreveria dentro de /dev/null e a unit sumiria no próximo 'hefesto-chave on'"
    fi
    _faria "copiar ${DAEMON_UNIT_TARGET} e recarregar o systemd do usuário"
    _CHAVE_POSTA="${XDG_CONFIG_HOME:-${HOME}/.config}/${APP_ID}/DESLIGADO-pela-chave.flag"
    if [[ -f "${_CHAVE_POSTA}" ]]; then
        _nao_faria "subir o daemon: o Hefesto está DESLIGADO pela chave (${_CHAVE_POSTA}); a decisão é sua e o ensaio não a desfaz"
    elif [[ "${enable_daemon}" -eq 1 ]]; then
        _faria "habilitar o daemon no boot e REINICIÁ-LO agora — o daemon em execução CAI e volta, e os controles conectados piscam nesse instante"
    elif systemctl --user is-active --quiet "${DAEMON_UNIT_NAME}"; then
        _faria "REINICIAR o daemon que já está no ar (para não ficar rodando o binário antigo); NÃO habilitar o auto-start"
    else
        _nao_faria "habilitar nem subir o daemon (você respondeu que não, e ele não está no ar)"
    fi
else
    mkdir -p "${DAEMON_USER_UNIT_DIR}"

    if command -v systemctl >/dev/null 2>&1 \
       && [[ -L "${DAEMON_UNIT_TARGET}" ]] \
       && [[ "$(readlink -f "${DAEMON_UNIT_TARGET}" 2>/dev/null)" == "/dev/null" ]]; then
        systemctl --user unmask "${DAEMON_UNIT_NAME}" >/dev/null 2>&1 || true
        rm -f "${DAEMON_UNIT_TARGET}"
        printf '      a unit estava MASCARADA (hefesto-chave off) — máscara retirada para a unit poder ser gravada\n'
    fi

    cp -f "${DAEMON_UNIT_SRC}" "${DAEMON_UNIT_TARGET}"
    systemctl --user daemon-reload >/dev/null 2>&1 || true

    _CHAVE_POSTA="${XDG_CONFIG_HOME:-${HOME}/.config}/${APP_ID}/DESLIGADO-pela-chave.flag"
    if [[ -f "${_CHAVE_POSTA}" ]]; then
        warn "o Hefesto está DESLIGADO pela chave — o daemon vai recusar subir"
        printf '      a chave está em %s\n' "${_CHAVE_POSTA}"
        printf '      para religar tudo como estava:  hefesto-chave on\n'
        enable_daemon=0
    fi
    if [[ "${enable_daemon}" -eq 1 ]]; then
        if systemctl --user enable "${DAEMON_UNIT_NAME}" >/dev/null 2>&1 \
           && systemctl --user restart "${DAEMON_UNIT_NAME}" >/dev/null 2>&1; then
            printf '      daemon habilitado e no ar\n'
        else
            warn "enable/restart do daemon falhou — suba com: systemctl --user enable --now hefesto-dualsense4unix.service"
        fi
    else
        if systemctl --user is-active --quiet "${DAEMON_UNIT_NAME}"; then
            systemctl --user restart "${DAEMON_UNIT_NAME}" >/dev/null 2>&1 \
                || warn "restart do daemon já em execução falhou"
            printf '      unit atualizada; auto-start NÃO habilitado (respeitando a resposta do passo 6)\n'
        else
            printf '      unit copiada; auto-start NÃO habilitado (respeitando a resposta do passo 6) — suba quando quiser: systemctl --user start hefesto-dualsense4unix.service\n'
        fi
    fi
fi

if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
    _faria "fechar e reabrir a janela e o ícone na bandeja que estiverem abertos, para valer o código novo; sem ícone de pé, subi-lo se a escolha está ligada"
elif [[ -z "${WAYLAND_DISPLAY:-}${DISPLAY:-}" ]]; then
    printf '      sem sessão gráfica: a bandeja sobe no próximo login\n'
elif [[ -x "${VENV_DIR}/bin/python" ]]; then
    if _RECARGA="$("${VENV_DIR}/bin/python" -m hefesto_dualsense4unix.app.actions.recarga_do_install 2>/dev/null)"; then
        printf '%s\n' "${_RECARGA}" | sed 's/^/      /'
    else
        warn "não consegui recarregar a janela e a bandeja — feche e abra a interface para valer o código novo"
    fi
fi

PRESENCA_UNIT_SRC="${ROOT_DIR}/assets/hefesto-dualsense4unix-presenca.service"
PRESENCA_UNIT_NAME="hefesto-dualsense4unix-presenca.service"
PRESENCA_UNIT_TARGET="${DAEMON_USER_UNIT_DIR}/${PRESENCA_UNIT_NAME}"
if [[ "${SKIP_SYSTEMD}" -eq 1 ]] || ! command -v systemctl >/dev/null 2>&1; then
    :
elif [[ ! -f "${PRESENCA_UNIT_SRC}" ]]; then
    warn "unit de presença ausente em assets/ — reinstale o repo"
elif [[ "${DRY_RUN:-0}" -eq 1 ]]; then
    _faria "copiar ${PRESENCA_UNIT_TARGET} e habilitá-la (com o daemon desligado, o controle volta ao sistema depois do login)"
else
    mkdir -p "${DAEMON_USER_UNIT_DIR}"
    sed "s|__PYTHON__|${VENV_DIR}/bin/python|g" "${PRESENCA_UNIT_SRC}" > "${PRESENCA_UNIT_TARGET}"
    systemctl --user daemon-reload >/dev/null 2>&1 || true
    if systemctl --user enable --now "${PRESENCA_UNIT_NAME}" >/dev/null 2>&1; then
        printf '      presença habilitada (com o daemon desligado, o controle volta ao sistema)\n'
    else
        warn "enable da presença falhou — habilite: systemctl --user enable --now ${PRESENCA_UNIT_NAME}"
    fi
fi

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

    readonly STORM_MARCA="${XDG_STATE_HOME:-${HOME}/.local/state}/hefesto-dualsense4unix/kernel-watch.boot"
    _storm_ativa=0
    if command -v systemctl >/dev/null 2>&1 \
            && systemctl --user is-active --quiet hefesto-dualsense4unix-storm-watch.service 2>/dev/null; then
        _storm_ativa=1
    fi

    if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
        _faria "instalar o vigia do kernel em ${STORM_SCRIPT_TARGET}"
        _faria "copiar ${STORM_UNIT_TARGET} e habilitá-lo (log em ${HOME}/.local/state/hefesto-dualsense4unix/kernel.log)"
        if [[ "${_storm_ativa}" -eq 1 ]]; then
            _faria "gravar o boot de agora em ${STORM_MARCA} e REINICIAR a vigia que já roda (sem reler o boot, para não duplicar o kernel.log)"
        fi
    elif [[ ! -f "${STORM_SCRIPT_SRC}" || ! -f "${STORM_UNIT_SRC}" ]]; then
        warn "kernel-watch: arquivos-fonte ausentes — reinstale o repo"
    else
        mkdir -p "${STORM_SCRIPT_DIR}" "${STORM_USER_UNIT_DIR}"
        install -m755 "${STORM_SCRIPT_SRC}" "${STORM_SCRIPT_TARGET}"
        cp -f "${STORM_UNIT_SRC}" "${STORM_UNIT_TARGET}"
        if command -v systemctl >/dev/null 2>&1; then
            systemctl --user daemon-reload >/dev/null 2>&1 || true
            if [[ "${_storm_ativa}" -eq 1 ]]; then
                _storm_boot="$(cat /proc/sys/kernel/random/boot_id 2>/dev/null || true)"
                if [[ -n "${_storm_boot}" ]]; then
                    mkdir -p "$(dirname "${STORM_MARCA}")"
                    printf '%s\n' "${_storm_boot}" > "${STORM_MARCA}"
                fi
                systemctl --user enable hefesto-dualsense4unix-storm-watch.service >/dev/null 2>&1 || true
                if systemctl --user restart hefesto-dualsense4unix-storm-watch.service >/dev/null 2>&1; then
                    printf '      reiniciado com o script novo — log em ~/.local/state/hefesto-dualsense4unix/kernel.log (compat: storm.log)\n'
                else
                    warn "restart falhou — reinicie: systemctl --user restart hefesto-dualsense4unix-storm-watch.service"
                fi
            elif systemctl --user enable --now hefesto-dualsense4unix-storm-watch.service >/dev/null 2>&1; then
                printf '      habilitado — log em ~/.local/state/hefesto-dualsense4unix/kernel.log (compat: storm.log)\n'
            else
                warn "enable falhou — habilite: systemctl --user enable --now hefesto-dualsense4unix-storm-watch.service"
            fi
        else
            warn "systemctl ausente — unit copiada mas não habilitada"
        fi
    fi
fi

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
    _ext_habilitadas=$'\n'"$(gnome-extensions list --enabled 2>/dev/null || true)"$'\n'
    _ext_todas=$'\n'"$(gnome-extensions list 2>/dev/null || true)"$'\n'
    if [[ "${_ext_habilitadas}" == *$'\n'"${_ext_id}"$'\n'* ]]; then
        printf '      já habilitada\n'
    elif [[ "${_ext_todas}" != *$'\n'"${_ext_id}"$'\n'* ]]; then
        warn "extension ${_ext_id} não instalada — instale via GNOME Extensions (https://extensions.gnome.org)"
    else
        printf '      extension %s está instalada mas desabilitada\n' "${_ext_id}"
        printf '      sem ela o ícone do Hefesto não aparece na barra superior do GNOME\n'
        ask_yn "habilitar agora?" "${AUTO_YES}"
        if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
            _faria "habilitar a extensão do GNOME ${_ext_id} (sem ela o ícone do Hefesto não aparece na barra)"
        elif [[ "${REPLY,,}" =~ ^y ]]; then
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

readonly APPLET_BIN="/usr/local/bin/hefesto-dualsense4unix-applet"
step "9/11" "applet COSMIC (APOSENTADO — o tray o substitui; --enable-cosmic-applet força)"
install_cosmic_applet() {
    local applet_dir="${ROOT_DIR}/packaging/cosmic-applet"
    if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
        if ! command -v cargo >/dev/null 2>&1 || ! command -v just >/dev/null 2>&1; then
            _nao_faria "compilar o applet COSMIC: faltam cargo e/ou just nesta máquina (o install segue normal sem ele)"
        else
            _faria "COMPILAR o applet COSMIC em Rust — a primeira build do libcosmic passa de 10 minutos"
            _faria_root "instalar o applet em ${APPLET_BIN} e o .desktop dele (o 'just install' usa sudo)"
        fi
        return 0
    fi
    if ! command -v cargo >/dev/null 2>&1 || ! command -v just >/dev/null 2>&1; then
        warn "cargo/just ausentes — applet COSMIC pulado (o install segue normal)"
        printf '        instale rustup (https://rustup.rs) + just e os -dev, depois:\n'
        printf '        sudo apt install just libxkbcommon-dev libwayland-dev libgbm-dev \\\n'
        printf '             libegl-dev libinput-dev libudev-dev pkg-config\n'
        printf '        e rode: ./install.sh --enable-cosmic-applet\n'
        return 0
    fi
    printf '      compilando + instalando (1a build do libcosmic e LONGA, >10 min)\n'
    local _applet_sudo=()
    [[ -n "${SUDO_ASKPASS:-}" ]] && _applet_sudo=(--set sudo "sudo -A")
    if just "${_applet_sudo[@]}" -f "${applet_dir}/justfile" -d "${applet_dir}" install; then
        printf '      applet instalado — adicione em Config. > Paineis > Miniaplicativos\n'
    else
        warn "build/instalacao do applet falhou — veja o log acima"
    fi
}
_applet_installed=0
[[ -e "${APPLET_BIN}" ]] && _applet_installed=1
if [[ "${ENABLE_COSMIC_APPLET}" -eq 1 ]]; then
    install_cosmic_applet
elif [[ "${DISABLE_COSMIC_APPLET}" -eq 1 ]]; then
    printf '      pulado (--no-cosmic-applet — e o default já é este)\n'
else
    printf '      aposentado — o tray faz o mesmo (force: ./install.sh --enable-cosmic-applet)\n'
fi
if [[ "${_applet_installed}" -eq 1 && "${ENABLE_COSMIC_APPLET}" -eq 0 ]]; then
    printf '      há um applet instalado de antes (%s)\n' "${APPLET_BIN}"
    printf '      para removê-lo SEM tocar em mais nada: ./uninstall.sh --so-o-applet\n'
fi

step "som" "áudio: o alto-falante do controle nunca dorme"
if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
    _ensaio_wireplumber nunca-dorme
else
if bash "${ROOT_DIR}/scripts/fix_wireplumber_default_source.sh" --nunca-dorme; then
    :
else
    warn "nunca-dorme falhou — rode: bash scripts/fix_wireplumber_default_source.sh --nunca-dorme"
fi
fi

step "10/11" "audio: impedir o DualSense de virar o microfone padrão"
if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
    if [[ "${WITH_WIREPLUMBER_DISABLE_MIC}" -eq 1 ]]; then
        _ensaio_wireplumber disable-source
    elif [[ "${WITH_WIREPLUMBER_FIX}" -eq 1 ]]; then
        _ensaio_wireplumber install
    else
        _nao_faria "rebaixar o microfone do controle (--keep-dualsense-mic) — ele pode virar o microfone padrão do sistema"
        _ensaio_wireplumber marcar-gesto
    fi
elif [[ "${WITH_WIREPLUMBER_DISABLE_MIC}" -eq 1 ]]; then
    [[ "${WITH_WIREPLUMBER_FIX}" -eq 1 ]] && warn "--with-wireplumber-disable-mic vence --with-wireplumber-fix"
    if bash "${ROOT_DIR}/scripts/fix_wireplumber_default_source.sh" --disable-source; rc=$?; [[ "${rc:-0}" -ne 1 ]]; then
        printf '      mic do DualSense DESABILITADO (node.disabled; controle só-HID)\n'
    else
        warn "disable-source falhou — rode: bash scripts/fix_wireplumber_default_source.sh --disable-source"
    fi
elif [[ "${WITH_WIREPLUMBER_FIX}" -eq 1 ]]; then
    if bash "${ROOT_DIR}/scripts/fix_wireplumber_default_source.sh" --install; rc=$?; [[ "${rc:-0}" -ne 1 ]]; then
        case "${rc:-0}" in
            2)
                printf '      drop-in do WirePlumber instalado; o DualSense é a ÚNICA fonte de\n'
                printf '      captura com porta usável — conecte um microfone/webcam, ou rode\n'
                printf '      ./install.sh --with-wireplumber-disable-mic para tirá-lo de vez\n'
                ;;
            3)
                printf '      drop-in do WirePlumber instalado (o veredito do microfone sai no fim deste passo)\n'
                ;;
            *)
                printf '      drop-in do WirePlumber instalado + fonte padrão reeleita\n'
                ;;
        esac
    else
        warn "fix do WirePlumber falhou — rode: bash scripts/fix_wireplumber_default_source.sh --install"
    fi
else
    printf '      pulado (--keep-dualsense-mic): o DualSense pode virar o microfone padrão\n'
    if bash "${ROOT_DIR}/scripts/fix_wireplumber_default_source.sh" --marcar-gesto-do-mic; then
        printf '      marca do gesto gravada: o doctor sabe que a ausência do drop-in 51 aqui foi pedido seu\n'
    else
        warn "não consegui gravar a marca do gesto do microfone — o doctor vai avisar que a política não está armada"
    fi
fi

if [[ "${WITH_WIREPLUMBER_DISABLE_MIC}" -ne 1 ]]; then
    if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
        _faria "curar o microfone pelo doctor (--fix-mic): pôr o perfil da placa numa entrada com porta de captura e tirar o mudo persistido por rota de captura"
    elif [[ ! -r "${ROOT_DIR}/scripts/doctor.sh" ]]; then
        warn "scripts/doctor.sh ausente — cura do microfone pulada"
    elif bash "${ROOT_DIR}/scripts/doctor.sh" --fix-mic --quiet; then
        printf '      microfone: camadas 1 e 2 conferidas (doctor.sh --fix-mic)\n'
    else
        printf '      microfone: a cura do doctor não fechou tudo — o que falta está nas linhas acima\n'
    fi
fi

if command -v pactl >/dev/null 2>&1; then
    _fonte_agora="$(pactl get-default-source 2>/dev/null || true)"
    case "${_fonte_agora}" in
        *.monitor|*.Monitor)
            warn "o microfone padrão do sistema é um MONITOR (${_fonte_agora})"
            printf '      isto NÃO é microfone: o que Discord, chat de jogo ou gravador\n'
            printf '      captarem é o áudio que SAI do PC, não a voz de quem fala — e o\n'
            printf '      medidor de nível mostra sinal, então parece estar funcionando.\n'
            _no_ar="$(bash "${ROOT_DIR}/scripts/fix_wireplumber_default_source.sh" --melhor-fonte-elegivel 2>/dev/null || true)"
            [[ -n "${_no_ar}" ]] || _no_ar="$(bash "${ROOT_DIR}/scripts/fix_wireplumber_default_source.sh" --fonte-se-sustenta "$(pactl list sources short 2>/dev/null | awk 'tolower($2) ~ /^alsa_input\..*dualsense/ { print $2; exit }')" 2>/dev/null || true)"
            if [[ -n "${_no_ar}" ]]; then
                printf '      Há uma entrada com porta usável no ar (%s), e o WirePlumber\n' "${_no_ar}"
                printf '      ainda não a elegeu. A janela do Hefesto avisa enquanto durar.\n'
            else
                printf '      Não há comando que resolva sem uma entrada de verdade: conecte o\n'
                printf '      DualSense (no cabo), um microfone/headset no jack, ou uma webcam\n'
                printf '      com microfone. A janela do Hefesto avisa enquanto durar.\n'
            fi
            ;;
        "")
            printf '      microfone: nenhuma fonte padrão eleita (PipeWire parado?)\n'
            ;;
        *)
            _porta_usavel="$(bash "${ROOT_DIR}/scripts/fix_wireplumber_default_source.sh" --fonte-se-sustenta "${_fonte_agora}" 2>/dev/null || true)"
            if [[ -z "${_porta_usavel}" ]]; then
                warn "o microfone padrão do sistema (${_fonte_agora}) não tem porta de captura usável — vai gravar silêncio"
            else
                case "${_fonte_agora}" in
                    *[Dd]ual[Ss]ense*)
                        _outra_entrada="$(bash "${ROOT_DIR}/scripts/fix_wireplumber_default_source.sh" --melhor-fonte-elegivel 2>/dev/null || true)"
                        if [[ -z "${_outra_entrada}" ]]; then
                            printf '      microfone padrão do sistema: %s\n' "${_fonte_agora}"
                            printf '      (o DualSense, porque é a ÚNICA entrada com porta usável agora)\n'
                        else
                            warn "o microfone padrão do sistema é o DualSense (${_fonte_agora}), mas há outra entrada com porta usável: ${_outra_entrada}"
                        fi
                        ;;
                    *)
                        printf '      microfone padrão do sistema: %s (entrada de verdade)\n' "${_fonte_agora}"
                        ;;
                esac
            fi
            ;;
    esac
    unset _fonte_agora _no_ar _porta_usavel _outra_entrada
fi

step "11a" "Proton pinado: baixar e conferir a versão validada (antes de fechar a Steam)"
PROTON_PIN_PY="${ROOT_DIR}/src/hefesto_dualsense4unix/integrations/proton_pin.py"
_pp_pronto=0
if [[ "${NO_PROTON_PIN}" -eq 1 ]]; then
    printf '      pulado (--no-proton-pin) — sem o pin, um upgrade de Proton pode duplicar o controle\n'
elif [[ ! -f "${PROTON_PIN_PY}" ]] || ! command -v python3 >/dev/null 2>&1; then
    warn "proton_pin.py ausente ou sem python3 — pin do Proton pulado"
elif [[ ! -f "${ROOT_DIR}/assets/proton-pin.conf" ]]; then
    warn "assets/proton-pin.conf ausente — pin do Proton pulado (reinstale o repo)"
elif [[ "${DRY_RUN:-0}" -eq 1 ]]; then
    _faria "garantir a versão de Proton VALIDADA em compatibilitytools.d (cache em ${HOME}/.cache/hefesto-dualsense4unix/proton; SHA256 obrigatório — checksum errado e NADA é extraído)"
    _faria "  (sem Steam nativa nesta máquina, só baixa e confere para o cache: nada é extraído e a pasta da Steam não é criada)"
    _nao_faria "sobrescrever um Proton pinado que VOCÊ já tenha instalado por fora (ProtonUp ou à mão): ele é mantido"
else
    _pp_rc=0
    _pp_saida="$(python3 "${PROTON_PIN_PY}" --ensure 2>&1)" || _pp_rc=$?
    if [[ -n "${_pp_saida}" ]]; then printf '%s\n' "${_pp_saida}"; fi
    case "${_pp_rc}" in
        0)
            _pp_pronto=1
            if [[ "${_pp_saida}" == *"instalação pré-existente sem manifesto"* ]]; then
                printf '      o Proton pinado JÁ estava aí, instalado por FORA (ProtonUp ou à mão), e foi MANTIDO — não sobrescrevo o que você instalou.\n'
                printf '      Por isso não dá para conferir o SHA256 do release, e o doctor vai apontar isso toda vez. Rodar este instalador de novo NÃO muda.\n'
                printf '      Para ficar com a cópia que nós verificamos: tire o diretório do compatibilitytools.d do caminho e rode o instalador outra vez.\n'
            fi
            ;;
        1)
            warn "checksum do Proton NÃO bateu — passo ABORTADO (nunca instalo binário não verificado)"
            ;;
        2)
            warn "sem rede e sem cache — o pin fica PENDENTE (rode ./install.sh de novo com internet); trava adiada"
            ;;
        4)
            warn "pino do Proton ADIADO: não há Steam nativa onde extraí-lo (o motivo está na linha acima) — nada foi criado na pasta da Steam"
            warn "  quando a Steam nativa existir, o vigia da Steam extrai do cache e trava sozinho; ou rode: python3 ${PROTON_PIN_PY} --ensure && python3 ${PROTON_PIN_PY} --lock --todos"
            ;;
        5)
            warn "o Proton bateu com o SHA256 e a EXTRAÇÃO falhou — veja o espaço livre em disco e rode: python3 ${PROTON_PIN_PY} --ensure"
            ;;
        7)
            warn "pino do Proton ADIADO: a Steam desta máquina é Flatpak/Snap, e o Proton extraído aqui fora não serve dentro da caixa dela — nada foi baixado (o motivo está na linha acima)"
            ;;
        *)
            warn "garantia da versão pinada falhou (rc=${_pp_rc}) — rode: python3 ${PROTON_PIN_PY} --ensure"
            ;;
    esac
    unset _pp_rc _pp_saida
fi

step "11a-bis" "Steam: fechar uma vez só, para os passos que editam os arquivos dela"
LAUNCH_MIGRATE_PY="${ROOT_DIR}/src/hefesto_dualsense4unix/integrations/steam_launch_options.py"
_steam_fechada_pelo_install=0
_reabrir_a_steam_se_o_install_fechou() {
    [[ "${_steam_fechada_pelo_install:-0}" -eq 1 ]] || return 0
    _steam_fechada_pelo_install=0
    python3 "${LAUNCH_MIGRATE_PY}" --reabrir-steam >/dev/null 2>&1 || true
}
_vigia_parado_pelo_install=0
_religar_o_vigia_se_o_install_parou() {
    [[ "${_vigia_parado_pelo_install:-0}" -eq 1 ]] || return 0
    _vigia_parado_pelo_install=0
    systemctl --user start hefesto-steam-input-guard.path hefesto-steam-input-guard.timer >/dev/null 2>&1 || true
}
if [[ "${DRY_RUN:-0}" -ne 1 ]]; then
    systemctl --user stop hefesto-steam-input-guard.path hefesto-steam-input-guard.timer >/dev/null 2>&1 || true
    _vigia_parado_pelo_install=1
    trap '_cleanup_sudo_keepalive; _reabrir_a_steam_se_o_install_fechou; _religar_o_vigia_se_o_install_parou' EXIT
fi
if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
    _faria "parar o vigia da Steam durante os passos 11 a 11c (ele escreve os mesmos arquivos) e religá-lo no fim"
    _faria "FECHAR a Steam, se ela estiver aberta, UMA vez para os passos 11 a 11c (ela regrava os arquivos ao sair, e com ela viva as edições seriam engolidas), e reabri-la no fim. Com um JOGO aberto, nada é fechado e esses passos adiam."
elif [[ -f "${LAUNCH_MIGRATE_PY}" ]] && command -v python3 >/dev/null 2>&1; then
    printf '      se a Steam estiver aberta, ela fecha agora UMA vez e reabre no fim\n'
    printf '      dos passos da Steam — pause downloads antes de seguir.\n'
    printf '      (com um jogo aberto, nada é fechado e esses passos adiam.)\n'
    _fs_rc=0
    python3 "${LAUNCH_MIGRATE_PY}" --fechar-steam || _fs_rc=$?
    case "${_fs_rc}" in
        0)
            _steam_fechada_pelo_install=1
            ;;
        4)
            :
            ;;
        *)
            warn "a Steam segue aberta (jogo aberto, ou ela não fechou) — os passos 11 a 11c adiam o que precisar dela, cada um com o comando"
            ;;
    esac
    unset _fs_rc
else
    warn "steam_launch_options.py ausente ou sem python3 — cada passo da Steam cuida da própria janela"
fi

step "11/11" "Steam: desligar PSSupport do PlayStation Controller"
if [[ "${KEEP_STEAM_INPUT}" -eq 1 ]]; then
    printf '      pulado (--keep-steam-input) — Steam Input pode conflitar com o daemon\n'
elif [[ "${DRY_RUN:-0}" -eq 1 ]]; then
    _faria "editar TODOS os localconfig.vdf de todos os usuários Steam (deb, Flatpak e Snap): zerar SteamController_PSSupport e UseSteamControllerConfig"
    _faria "guardar um backup .bak.steam-input-<carimbo> AO LADO de cada vdf tocado, ANTES de escrever (e só quando há mudança de verdade)"
    _faria "  (para desfazer: bash scripts/disable_steam_input.sh --restore)"
    _faria "  (para ver o estado de hoje sem mudar nada: bash scripts/disable_steam_input.sh --status)"
elif [[ ! -x "${ROOT_DIR}/scripts/disable_steam_input.sh" ]]; then
    warn "scripts/disable_steam_input.sh ausente ou não-executável — pulado"
else
    if bash "${ROOT_DIR}/scripts/disable_steam_input.sh" --apply; then
        printf '      Steam Input PSSupport zerado em todos os localconfig.vdf\n'
        printf '      reverter: bash scripts/disable_steam_input.sh --restore\n'
    else
        warn "disable_steam_input.sh falhou — rode: bash scripts/disable_steam_input.sh --apply"
    fi
fi

if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
    _faria "instalar o vigia do vdf em ${HOME}/.config/systemd/user/hefesto-steam-input-guard.{path,timer,service} e habilitá-lo (repõe o que a Steam reescrever ao sair)"
    if [[ "${KEEP_STEAM_INPUT}" -eq 1 ]]; then
        _faria "  (com --keep-steam-input, sem a linha que desliga o Steam Input: ele repõe só o atalho de inicialização e o Proton pinado)"
    fi
else
    USER_UNIT_DIR="${HOME}/.config/systemd/user"
    mkdir -p "${USER_UNIT_DIR}"
    _guard_ok=1
    install -Dm644 "${ROOT_DIR}/assets/hefesto-steam-input-guard.path" \
        "${USER_UNIT_DIR}/hefesto-steam-input-guard.path" 2>/dev/null || _guard_ok=0
    install -Dm644 "${ROOT_DIR}/assets/hefesto-steam-input-guard.timer" \
        "${USER_UNIT_DIR}/hefesto-steam-input-guard.timer" 2>/dev/null || _guard_ok=0
    SENTINELA_PY="${ROOT_DIR}/src/hefesto_dualsense4unix/integrations/sentinela_do_wrapper.py"
    OPCOES_POR_JOGO_PY="${ROOT_DIR}/src/hefesto_dualsense4unix/integrations/opcoes_por_jogo.py"
    _guard_linhas_que_saem=()
    if [[ "${NO_PROTON_PIN}" -eq 1 ]]; then
        _guard_linhas_que_saem=(-e '/^ExecStart=.*__PROTON_PIN__/d')
    fi
    if [[ "${KEEP_STEAM_INPUT}" -eq 1 || ! -x "${ROOT_DIR}/scripts/disable_steam_input.sh" ]]; then
        _guard_linhas_que_saem+=(-e '/^ExecStart=.*__SCRIPT__/d')
    fi
    _guard_tmp="$(mktemp)"
    if sed ${_guard_linhas_que_saem[@]+"${_guard_linhas_que_saem[@]}"} \
        -e "s#__SCRIPT__#${ROOT_DIR}/scripts/disable_steam_input.sh#g" \
        -e "s#__SENTINELA__#${SENTINELA_PY}#g" \
        -e "s#__PROTON_PIN__#${PROTON_PIN_PY}#g" \
        -e "s#__OPCOES_POR_JOGO__#${OPCOES_POR_JOGO_PY}#g" \
        "${ROOT_DIR}/assets/hefesto-steam-input-guard.service" > "${_guard_tmp}" 2>/dev/null \
       && [[ -s "${_guard_tmp}" ]]; then
        install -Dm644 "${_guard_tmp}" "${USER_UNIT_DIR}/hefesto-steam-input-guard.service" \
            2>/dev/null || _guard_ok=0
    else
        _guard_ok=0
    fi
    rm -f "${_guard_tmp}"
    if [[ "${_guard_ok}" -eq 0 ]]; then
        warn "vigia do Steam Input NÃO instalado (asset ausente em assets/) — o que a Steam reescrever ao sair não será reposto sozinho"
    fi
    unset _guard_ok _guard_tmp _guard_linhas_que_saem
    if systemctl --user daemon-reload 2>/dev/null \
       && systemctl --user enable hefesto-steam-input-guard.path hefesto-steam-input-guard.timer 2>/dev/null; then
        printf '      guard do Steam Input + wrapper habilitado (path + timer 30min; liga no fim do install)\n'
    else
        warn "não consegui habilitar o guard --user (sessão systemd ausente?) — será pego no próximo login"
    fi
fi

step "11b" "Steam: migrar Launch Options antigas para o wrapper hefesto-launch"
LAUNCH_MIGRATE_PY="${ROOT_DIR}/src/hefesto_dualsense4unix/integrations/steam_launch_options.py"
if [[ -f "${LAUNCH_MIGRATE_PY}" ]] && command -v python3 >/dev/null 2>&1; then
    printf '      (com um jogo aberto, a migração é adiada e nada é fechado.)\n'
    if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
        _faria "trocar as Opções de Inicialização antigas que escondiam o controle com um IGNORE_DEVICES fixo (e deixavam o jogo sem controle nenhum quando o virtual caía) pela chamada do wrapper, jogo por jogo — o que VOCÊ escreveu na linha é preservado"
        _faria "guardar um backup .bak.hefesto-launch-<carimbo> ao lado de cada vdf tocado"
        _faria "FECHAR a Steam, se ela estiver aberta, e reabri-la ao terminar (ela regrava o vdf ao sair, e sem isso a edição seria engolida). Com um JOGO aberto, nada é fechado e a migração é adiada."
    elif python3 "${LAUNCH_MIGRATE_PY}" --migrate --stop-steam; then
        printf '      Launch Options antigas do Hefesto migradas para o wrapper hefesto-launch\n'
    else
        warn "migração das Launch Options adiada — rode com a Steam fechada (e sem jogo aberto): python3 ${LAUNCH_MIGRATE_PY} --migrate"
    fi
else
    warn "steam_launch_options.py ausente ou sem python3 — migração pulada; rode depois: python3 ${LAUNCH_MIGRATE_PY} --migrate"
fi

step "11b-bis" "Steam: aplicar o wrapper hefesto-launch a todos os jogos"
if [[ -f "${LAUNCH_MIGRATE_PY}" ]] && command -v python3 >/dev/null 2>&1; then
    printf '      sem isto, as opções de inicialização ficam vazias e o jogo\n'
    printf '      enxerga dois DualSense (jogos que já têm o wrapper são pulados).\n'
    if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
        _faria "pôr a chamada do wrapper hefesto-launch nas Opções de Inicialização de TODOS os jogos da Steam (quem já tem é pulado; Steam Flatpak/Snap fica inteira de fora)"
        _faria "guardar um backup .bak.hefesto-launch-<carimbo> ao lado de cada vdf tocado"
        _faria "FECHAR e reabrir a Steam, se preciso; com um jogo aberto, nada é tocado"
    elif python3 "${LAUNCH_MIGRATE_PY}" --apply --stop-steam; then
        printf '      wrapper hefesto-launch nas Launch Options de todos os jogos\n'
    else
        warn "aplicação do wrapper adiada — rode com a Steam fechada (e sem jogo aberto): python3 ${LAUNCH_MIGRATE_PY} --apply"
    fi
else
    warn "steam_launch_options.py ausente ou sem python3 — wrapper NÃO aplicado; rode depois: python3 ${LAUNCH_MIGRATE_PY} --apply"
fi

step "11b-ter" "Steam: repor o wrapper onde a Steam o apagou (sentinela)"
LAUNCH_SENTINELA_PY="${ROOT_DIR}/src/hefesto_dualsense4unix/integrations/sentinela_do_wrapper.py"
if [[ "${DRY_RUN:-0}" -eq 1 ]] && [[ -f "${LAUNCH_SENTINELA_PY}" ]]; then
    _faria "REPOR a chamada do wrapper nos jogos de que a Steam a apagou (preservando o resto da linha), e anotar quem tem o wrapper em ${HOME}/.local/state/hefesto-dualsense4unix/wrapper-visto.json"
    _faria "  (com a Steam ou um jogo aberto, o reparo é ADIADO e nada é tocado)"
elif [[ -f "${LAUNCH_SENTINELA_PY}" ]] && command -v python3 >/dev/null 2>&1; then
    _sw_rc=0
    python3 "${LAUNCH_SENTINELA_PY}" --reparar || _sw_rc=$?
    case "${_sw_rc}" in
        0)
            printf '      se um jogo perder o wrapper depois, o doctor e a janela dizem QUAL\n'
            ;;
        3)
            warn "reparo do wrapper ADIADO (Steam ou um jogo aberto) — feche a Steam e rode:"
            warn "  python3 ${LAUNCH_SENTINELA_PY} --reparar"
            ;;
        *)
            warn "reparo do wrapper falhou (rc=${_sw_rc}) — rode depois: python3 ${LAUNCH_SENTINELA_PY} --reparar"
            ;;
    esac
    unset _sw_rc
else
    warn "sentinela_do_wrapper.py ausente ou sem python3 — sem memória de quem tem o wrapper; regressão futura apareceria como 'jogo novo'"
fi

step "11c" "Proton pinado: trava dos jogos na versão validada"
if [[ "${NO_PROTON_PIN}" -eq 1 ]]; then
    printf '      pulado (--no-proton-pin)\n'
elif [[ "${DRY_RUN:-0}" -eq 1 ]]; then
    _faria "TRAVAR nessa versão o Proton padrão e o dos jogos instalados que rodam por Proton (CompatToolMapping do config.vdf), com backup config.vdf.bak.hefesto-proton-<carimbo> ao lado"
    _faria "  (com a Steam ou um jogo aberto, a trava é ADIADA; desfazer: ./uninstall.sh, que roda o --unlock)"
    _nao_faria "travar jogo com versão Linux nativa, nem trocar a ferramenta de quem roda nativo, nem tocar nos jogos que você nomeou em jogos_fora_do_pino.txt"
elif [[ "${_pp_pronto}" -ne 1 ]]; then
    printf '      trava adiada — o Proton pinado não ficou pronto no passo 11a (ver acima)\n'
else
    _pl_rc=0
    python3 "${PROTON_PIN_PY}" --lock --todos || _pl_rc=$?
    if [[ "${_pl_rc}" -eq 0 ]]; then
        printf '      jogos travados na versão pinada (backup do config.vdf ao lado; reverter: uninstall)\n'
    elif [[ "${_pl_rc}" -eq 3 ]]; then
        warn "Steam (ou um jogo) aberta — trava ADIADA; o vigia da Steam trava sozinho quando ela fechar, ou rode: python3 ${PROTON_PIN_PY} --lock --todos"
    elif [[ "${_pl_rc}" -eq 4 ]]; then
        printf '      trava adiada — a Steam ainda não entrou numa conta; o vigia da Steam trava quando ela sair pela primeira vez\n'
    else
        warn "trava do Proton falhou — rode manualmente: python3 ${PROTON_PIN_PY} --lock --todos"
    fi
    unset _pl_rc
fi

if [[ "${_steam_fechada_pelo_install}" -eq 1 ]]; then
    step "11d" "Steam: reabrir (ela estava aberta quando o install começou)"
    _reabrir_a_steam_se_o_install_fechou
fi
_religar_o_vigia_se_o_install_parou
trap _cleanup_sudo_keepalive EXIT

if [[ "${RUN_DOCTOR}" -eq 1 ]]; then
    printf '\n'
    printf '─────────────────────────────────────────\n'
    printf ' Conferência final (doctor)\n'
    printf '─────────────────────────────────────────\n'
    if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
        printf '      no ensaio o doctor não roda. Para o retrato da máquina agora:\n'
        printf '        bash scripts/doctor.sh\n'
    elif [[ ! -r "${ROOT_DIR}/scripts/doctor.sh" ]]; then
        warn "scripts/doctor.sh ausente — conferência final pulada"
    else
        doctor_saida="$(bash "${ROOT_DIR}/scripts/doctor.sh" 2>&1 || true)"
        printf '%s\n' "${doctor_saida}" | grep -E '^\[FAIL\]| Diagnóstico:' || true
        if printf '%s' "${doctor_saida}" | grep -q '^\[FAIL\]'; then
            printf '\n'
            warn "a instalação terminou com FALHA(s) acima — veja tudo com:"
            warn "  bash scripts/doctor.sh"
            warn "e tente a cura automática com:"
            warn "  bash scripts/doctor.sh --fix"
        else
            printf '      nenhuma FALHA — as curas do Hefesto estão armadas\n'
        fi
    fi
fi

if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
    _ensaio_resumo
    exit 0
fi
printf '\n'
printf '─────────────────────────────────────────\n'
printf ' Hefesto - DualSense4Unix instalado\n'
printf '─────────────────────────────────────────\n'
printf ' Abrir:       hefesto-dualsense4unix-gui\n'
printf ' Desinstalar: ./uninstall.sh\n'
printf '─────────────────────────────────────────\n'

APP_ID_FLATPAK_ANTIGO="br.andrefarias.Hefesto"
if command -v flatpak >/dev/null 2>&1 \
   && flatpak info "${APP_ID_FLATPAK_ANTIGO}" >/dev/null 2>&1; then
    printf '\n'
    printf ' Você tem a versão ANTIGA do Hefesto instalada pelo Flatpak.\n'
    printf '   O aplicativo trocou de identidade nesta versão, e o Flatpak trata\n'
    printf '   identidade nova como outro aplicativo: ele instala ao lado em vez de\n'
    printf '   atualizar. Ficam dois Hefestos no menu, e só o novo recebe conserto.\n'
    printf '   Os seus perfis não se perdem — o novo lê os do antigo ao abrir pela\n'
    printf '   primeira vez, sem apagar nada.\n'
    printf '   Para tirar o antigo do menu:\n'
    printf '     flatpak uninstall --user %s\n' "${APP_ID_FLATPAK_ANTIGO}"
    printf '─────────────────────────────────────────\n'
fi

QUIRK_MARKER="054c:0ce6:gn"
quirk_ativo=0
quirk_agendado=0
if grep -q "${QUIRK_MARKER}" /proc/cmdline 2>/dev/null; then quirk_ativo=1; fi
if [[ -r /sys/module/usbcore/parameters/quirks ]] && grep -q "${QUIRK_MARKER}" /sys/module/usbcore/parameters/quirks 2>/dev/null; then quirk_ativo=1; fi
if [[ -r /etc/kernelstub/configuration ]] && grep -q "${QUIRK_MARKER}" /etc/kernelstub/configuration 2>/dev/null; then quirk_agendado=1; fi
if [[ -r /etc/default/grub ]] && grep -q "${QUIRK_MARKER}" /etc/default/grub 2>/dev/null; then quirk_agendado=1; fi
if [[ "${quirk_ativo}" -eq 0 && "${quirk_agendado}" -eq 1 ]]; then
    anotar_reinicio_pendente "${_PENDENTE_DO_CMDLINE}"
elif [[ "${quirk_ativo}" -eq 0 ]]; then
    printf '\n'
    printf ' Vai usar o MICROFONE do DualSense no cabo?\n'
    printf '   O quirk de áudio USB segura o storm -71 com o mic ligado, e o\n'
    printf '   install não o escreveu na linha de comando do kernel. Para\n'
    printf '   aplicá-lo (vale no próximo boot):\n'
    printf '     bash scripts/install_usb_quirk.sh\n'
    printf '─────────────────────────────────────────\n'
fi
dizer_o_reinicio_pendente
printf '\n'
