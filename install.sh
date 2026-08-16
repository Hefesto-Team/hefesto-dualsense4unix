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
#                         ATENÇÃO: o passo 3e (cmdline gerenciado, DEFAULT) já
#                         grava esses MESMOS tokens de quirk — esta flag só
#                         adianta o passo 3b e é redundante com o default.
#   --no-snd-quirk        OPT-OUT do quirk do snd_usb_audio (DEFAULT ON, passo
#                         3c): grava /etc/modprobe.d/hefesto-dualsense-storm.conf
#                         com quirk_flags do DualSense (ignore_ctl_error e
#                         ctl_msg_delay_1m) — a cura de raiz do storm -71 na
#                         camada de ÁUDIO, que PRESERVA mic e fone (ao contrário
#                         da regra 75). Use em CI/sem hardware; --no-udev também
#                         pula este passo.
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
#                         sem headers, como --no-udev; desliga AMBOS os
#                         módulos DKMS — hid-nintendo e rtw88_usb, abaixo).
#   (DEFAULT) DKMS rtw88_usb patchado (Onda W — cura de raiz do fantasma USB
#                         do dongle WiFi/RTL8822BU: quando um port-status-change
#                         se perde no xHCI, o driver in-tree nunca detecta que o
#                         device sumiu e segue tentando I/O contra hardware
#                         ausente — só unbind manual ou reboot recicla o device,
#                         medido 13h de fantasma em 20/07): módulo out-of-tree
#                         via DKMS (assets/dkms/rtw88-usb/) que substitui o
#                         in-tree (vence por precedência updates/dkms; NUNCA
#                         remove o in-tree). Detecta -ENODEV/-ESHUTDOWN
#                         (device sumiu de verdade) ou 5 -EPROTO consecutivos
#                         sem NENHUM sucesso no meio (zera a cada sucesso) e
#                         enfileira usb_queue_reset_device — gate: module
#                         param hang_reset (default Y; N desliga só o reset,
#                         a detecção/silenciamento continua). Fail-safe
#                         total: dkms/headers ausentes, kernel fora do pino
#                         BUILD_EXCLUSIVE_KERNEL (ABI privada do rtw88) ou
#                         build falho = aviso honesto, o in-tree segue
#                         valendo, o install NUNCA aborta. Ativação NUNCA
#                         recarrega um módulo já carregado (derrubaria o
#                         WiFi ao vivo) — vale no próximo boot/replug do
#                         dongle. Vale para TODO formato. Opt-out: --no-dkms
#                         (mesma flag do hid-nintendo, acima).
#   --wifi-powersave-off  OPT-IN (W2 — gateado por evidência): instala
#                         assets/NetworkManager/hefesto-wifi-powersave.conf em
#                         /etc/NetworkManager/conf.d/ (wifi.powersave=2). Use
#                         SÓ depois que scripts/medir_w2_lps.sh provar ganho
#                         com margem clara. NUNCA chama nmcli/rfkill — vale na
#                         próxima (re)conexão do NM. uninstall.sh remove.
#   --yes, -y             responde sim a todos os prompts (autostart, hotplug,
#                         AppIndicator extension, etc) e assume --format=native.
#   --no-systemd          pula a unit do daemon por INTEIRO (passo 6 E passo 7a):
#                         nada é copiado, nada é habilitado, nada sobe.
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
#   --no-fonts            pula as fontes da identidade visual (Space Grotesk +
#                         JetBrains Mono, que o gui/theme.css pede). Por DEFAULT
#                         elas são instaladas em best-effort pelo
#                         scripts/install_fonts.sh — pacote da distro primeiro,
#                         download PINADO + SHA-256 só se não houver pacote.
#                         Nada quebra sem elas (o CSS tem fallback); o que muda é
#                         a interface ser a do design e as medidas de texto
#                         baterem com as do mockup.
#   (DEFAULT) teclado na tela — o que o L3 do controle abre. Instalado em TODO
#                         formato pelo scripts/install_osk.sh, que escolhe pela
#                         SESSÃO: em Wayland o `wvkbd` (binário wvkbd-mobintl,
#                         cliente Wayland puro, digita pelo
#                         zwp_virtual_keyboard_manager_v1 que o cosmic-comp
#                         expõe — medido); em X11 o `onboard` (GTK3, digita por
#                         XTEST, que em Wayland só alcança janelas XWayland).
#                         Importa porque nenhum dos nove atalhos de fábrica
#                         digita uma LETRA: sem isto, "o teclado emulado não
#                         digita" é literalmente verdade. Best-effort (o install
#                         nunca aborta por causa dele) e o passo GRAVA o que fez
#                         em ~/.local/state/hefesto-dualsense4unix/
#                         teclado-na-tela.conf, para o doctor distinguir "ela não
#                         quis" de "o install não instalou". Opt-out: --no-osk.
#   --no-osk              pula o teclado na tela. O L3 do controle passa a só
#                         avisar na tela que não tem o que abrir.
#   (DEFAULT) cura gentil do WirePlumber: REBAIXA o DualSense para não virar o
#                         microfone padrão (drop-in 51, user-space) — simétrica com o
#                         uninstall que a remove. Opt-out: --keep-dualsense-mic.
#   --keep-dualsense-mic  NÃO rebaixa o DualSense (deixa-o elegível como mic padrão).
#   --with-wireplumber-fix  redundante (já é o default); mantida para compat.
#   --with-wireplumber-disable-mic  DESABILITA de vez a source (mic) do DualSense
#   --no-doctor           pula a CONFERÊNCIA final. Por padrão o install roda o
#                         doctor no fim e mostra o veredito: uma instalação que
#                         termina com cura desarmada tem de DIZER isso.
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
# Default (sem flag nenhuma): a unit do daemon é COPIADA, HABILITADA no boot e
# SOBE na hora. Quem manda é a sua resposta ao passo 6 ("habilitar auto-start do
# daemon no boot?", default sim): responder "não" copia a unit e NÃO habilita
# nem sobe o daemon; --no-systemd pula os dois passos (6 e 7a) por inteiro.
# Hotplug-GUI continua opt-in (prompt com default NÃO).
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
# FONTE-PADRAO-01, item 3: DEFAULT ON. Medido em 29/07/2026 — `grep -c fonts
# install.sh` dava 0: o scripts/install_fonts.sh existia e NINGUÉM o chamava.
# Nesta máquina as duas famílias já estão instaladas, então o defeito é invisível
# aqui e morde só em instalação nova: a interface cai no fallback do CSS sem
# nada indicar, e as MEDIDAS de texto mudam com a fonte — foi a falta dessas
# métricas que fez a CI pedir 431px de altura onde aqui cabia em 357.
NO_FONTS=0
# TECLADO-QUE-NAO-DIGITA-01 (10/08/2026). DEFAULT ON, pela regra dela de
# 08/08: "toda cura entra no install, sem flag — nada à mão, nada opt-in".
# Medido antes desta linha existir: `grep -c onboard install.sh` dava 0, e o
# `command -v onboard wvkbd-mobintl` na máquina dela não achava nenhum dos
# dois. O produto oferecia "Abrir teclado na tela" no L3 e não instalava o que
# ele precisa. O opt-out existe pelo mesmo motivo que o --no-fonts: CI e
# máquina enxuta não querem pacote gráfico novo.
NO_OSK=0
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
# CONFERENCIA-FINAL-01: o doctor roda no fim, por padrão. `--no-doctor` pula.
RUN_DOCTOR=1
FORCE_XWAYLAND=0
# W2 (corretor final, achado #5): a flag documentada no asset e no desenho da
# Onda W nunca tinha sido implementada — o parser só avisava "argumento
# desconhecido" e a operadora podia achar que a cura foi aplicada. Opt-in,
# nasce desligada; só vira default quando a medição do medir_w2_lps.sh provar.
WIFI_POWERSAVE_OFF=0
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
        --no-fonts)           NO_FONTS=1 ;;
        --no-osk)             NO_OSK=1 ;;
        --with-wireplumber-fix) WITH_WIREPLUMBER_FIX=1 ;;  # já é default; mantida p/ compat
        --keep-dualsense-mic) WITH_WIREPLUMBER_FIX=0 ;;
        --no-doctor) RUN_DOCTOR=0 ;;
        --with-wireplumber-disable-mic) WITH_WIREPLUMBER_DISABLE_MIC=1 ;;
        --with-usb-quirk)     WITH_USB_QUIRK=1 ;;
        --no-dkms)            NO_DKMS=1 ;;
        --no-snd-quirk)       SKIP_SND_QUIRK=1 ;;
        --no-kernel-watch)    SKIP_KERNEL_WATCH=1 ;;
        --with-storm-watch)   : ;;  # deprecated: o kernel-watch já é DEFAULT
        --no-proton-pin)      NO_PROTON_PIN=1 ;;
        --keep-steam-input)   KEEP_STEAM_INPUT=1 ;;
        --wifi-powersave-off) WIFI_POWERSAVE_OFF=1 ;;
        --force-xwayland)     FORCE_XWAYLAND=1 ;;
        --format=*)           FORMAT="${arg#*=}" ;;
        --native)             FORMAT="native" ;;
        --flatpak)            FORMAT="flatpak" ;;
        --appimage)           FORMAT="appimage" ;;
        --deb)                FORMAT="deb" ;;
        --yes|-y)             AUTO_YES=1 ;;
        -h|--help)
            # BUG-INSTALL-HELP-TRUNCADO-01 (29/07): era `sed -n '2,128p'` — uma
            # faixa FIXA que envelheceu junto com o cabeçalho. Quando o bloco de
            # comentário passou de 128 linhas, o --help calou flags REAIS: a
            # --force-xwayland (a que a operadora precisa em COSMIC) simplesmente
            # não aparecia, e quem lesse o --help concluía que ela não existia.
            # Agora o fim NÃO é número: o awk imprime da linha 2 até a última
            # linha do bloco de comentário (a primeira linha que não começa com
            # '#' encerra), então o --help cresce sozinho com o cabeçalho.
            awk 'NR == 1 { next } /^#/ { sub(/^# ?/, ""); print; next } { exit }' \
                "${BASH_SOURCE[0]}"
            exit 0
            ;;
        # BUG-INSTALL-ARG-DESCONHECIDO-SILENCIOSO-01: um aviso solto rolava para
        # fora da tela e o install seguia com os DEFAULTS — quem errou o nome de
        # uma flag (ou usou uma que já foi renomeada) achava que tinha pedido
        # algo e recebia outra coisa, sem jeito de perceber. Aborta.
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
    # INSTALL-HEADLESS-01 (auditoria 21/07): sem TTY (stdin não é terminal —
    # CI, pipe, execução headless), NÃO travar o `set -euo pipefail` no EOF do
    # `read`. Antes, `./install.sh` sem -y e sem TTY MORRIA no 1o prompt (passo
    # 4, atalho/launcher) com rc=1 e pulava os passos seguintes. Sem TTY usamos
    # o mesmo default seguro que o -y usaria (o valor recomendado); o `|| REPLY`
    # é cinto extra caso o `read` retorne não-zero por outro motivo.
    if [[ ! -t 0 ]]; then
        REPLY="$default"; return
    fi
    local indicator
    if [[ "$default" == "y" ]]; then indicator="[Y/n]"; else indicator="[y/N]"; fi
    read -r -n 1 -p "      $prompt $indicator " REPLY || REPLY="$default"
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
    # INSTALL-HEADLESS-01 (auditoria 21/07): com SUDO_ASKPASS setado (execução
    # não-interativa — CI/headless), valida a credencial pelo helper (-A), SEM
    # exigir TTY. Assim `./install.sh` sem flags roda os passos root num
    # ambiente sem terminal, bastando exportar SUDO_ASKPASS=<helper>.
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

# TECLADO-QUE-NAO-DIGITA-01: o teclado na tela é DEFAULT em TODO formato, pela
# mesma razão do broker logo abaixo — e pelo mesmo furo. O `exit 0` do bloco de
# formatos (poucas linhas adiante) deixa doze passos de cura para trás, e um
# passo escrito só no fluxo native cairia do lado errado da cerca: flatpak,
# appimage e deb sairiam sem o único caminho do produto para ESCREVER TEXTO,
# em silêncio. Por isso a função nasce AQUI, acima da bifurcação, e é chamada
# dos DOIS lados — é o mesmo molde do `install_broker_host`.
#
# Best-effort integral: o `scripts/install_osk.sh` sai 0 mesmo quando não
# consegue instalar (sem sudo, sem rede, distro sem o pacote) e grava o que
# aconteceu na sentinela; o `if` aqui é só o cinto contra o `set -e`.
install_osk_host() {
    if [[ "${NO_OSK}" -eq 1 ]]; then
        printf '      teclado na tela pulado (--no-osk) — o L3 do controle só avisa que não tem o que abrir\n'
        # A escolha dela também vira sentinela: sem isto, "ela não quis" e "o
        # install não instalou" ficariam com a MESMA cara para o doctor — a
        # armadilha do commit 108b711, palavra por palavra.
        mkdir -p "${HOME}/.local/state/hefesto-dualsense4unix" 2>/dev/null || true
        {
            printf '# gravado por install.sh (--no-osk) — NÃO editar à mão.\n'
            printf 'resultado=pulado\n'
            printf 'motivo=--no-osk\n'
            printf 'data=%s\n' "$(date -Is 2>/dev/null || date)"
        } > "${HOME}/.local/state/hefesto-dualsense4unix/teclado-na-tela.conf" 2>/dev/null || true
        return 0
    fi
    if [[ ! -r "${ROOT_DIR}/scripts/install_osk.sh" ]]; then
        warn "scripts/install_osk.sh ausente — teclado na tela pulado"
        return 0
    fi
    if [[ "${AUTO_YES}" -eq 1 ]]; then
        bash "${ROOT_DIR}/scripts/install_osk.sh" --yes || true
    else
        bash "${ROOT_DIR}/scripts/install_osk.sh" || true
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
    dkms_warn_secureboot_once  # PKG-1: avisa (não aborta) se SB pode barrar o .ko
    # PKG-3: versão do dkms.conf (fonte da verdade), não literal hardcoded.
    local _hidn_src="${ROOT_DIR}/assets/dkms/hid-nintendo"
    dkms_install_patched_module hefesto-hid-nintendo \
        "$(dkms_pkg_version "${_hidn_src}")" "${_hidn_src}" hid-nintendo
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
        # AUTO-01.7: com o patchado carregado, escreve os params A QUENTE —
        # paridade com o caminho de instalação por PACOTE
        # (scripts/install-host-udev.sh), que já fazia isto e o install.sh não.
        # Os dois são lidos A CADA PROBE, então a cura vale no próximo PLUG do
        # controle, sem esperar reboot; e é a única janela possível, porque
        # recarregar o módulo é proibido (derrubaria Pro/8BitDo em uso).
        # Best-effort: param read-only ou sudo expirado não interrompe nada.
        # O portão é de EXISTÊNCIA (`-e`) e nunca `-w`: os arquivos em
        # /sys/module são root:root 0644 e o install roda SEM sudo (com sudo o
        # HOME vira /root e o venv nasce errado), então `-w` é sempre falso e o
        # passo vira silêncio — quem escreve abaixo é o `sudo tee`, não quem
        # testa o portão.
        if [[ -e /sys/module/hid_nintendo/parameters/bt_probe_retries ]]; then
            printf '3' | sudo tee /sys/module/hid_nintendo/parameters/bt_probe_retries >/dev/null 2>&1 || true
            printf '1' | sudo tee /sys/module/hid_nintendo/parameters/skip_tx_on_rate_exceeded >/dev/null 2>&1 || true
            printf '      params aplicados a quente (valem no próximo plug, sem reboot)\n'
        fi
        # Os três do patch 0003 (handshake USB do clone 057E:2009) são lidos NA
        # PROBE, então valem do próximo plug em diante. O uninstall os devolve a
        # 0, logo o rearme aqui é obrigatório: sem ele o ciclo uninstall+install
        # deixa o 8BitDo no cabo sem cura até o boot seguinte. Portão próprio
        # porque o módulo patchado ANTIGO não tem estes params. A simetria com o
        # uninstall é cobrada por teste.
        if [[ -e /sys/module/hid_nintendo/parameters/usb_cmd_pad_to_report ]]; then
            printf '1' | sudo tee /sys/module/hid_nintendo/parameters/usb_cmd_pad_to_report >/dev/null 2>&1 || true
            printf '1' | sudo tee /sys/module/hid_nintendo/parameters/usb_send_conn_status >/dev/null 2>&1 || true
            printf '1' | sudo tee /sys/module/hid_nintendo/parameters/usb_probe_degrade >/dev/null 2>&1 || true
            printf '      handshake USB do clone rearmado a quente (vale no próximo plug)\n'
        fi
    elif [[ -d /sys/module/hid_nintendo ]]; then
        printf '      módulo in-tree em uso — NÃO recarregamos (derrubaria Pro/8BitDo conectados);\n'
        printf '      o patchado vale no próximo boot (replug re-liga no módulo já carregado)\n'
    else
        printf '      hid_nintendo descarregado — o patchado entra sozinho no próximo plug\n'
    fi
    return 0
}

# Contenção BT (25/07): módulo hid-playstation patchado (retry opcional nos
# feature reports da probe) via a MESMA lib genérica scripts/dkms_lib.sh (3ª
# instância — hid-nintendo é a 1ª, rtw88_usb a 2ª; ZERO ajuste na lib).
# DEFAULT ON (regra da casa: install SEM FLAGS aplica), mesmo gate NO_DKMS.
# Motivo: com dois DualSense pareando com ~1 s de diferença, o 2º perde o
# canal de controle L2CAP, o GET_REPORT expira no BlueZ (REPORT_REQ_TIMEOUT,
# 3 s), o uhid entrega -EIO ao driver e o controle inteiro é perdido. Detalhe
# completo em assets/dkms/hid-playstation/README.md.
install_dkms_hid_playstation_host() {
    if [[ "${NO_DKMS}" -eq 1 ]]; then
        printf '      pulado (--no-dkms)\n'
        return 0
    fi
    if ! command -v sudo >/dev/null 2>&1; then
        warn "sudo ausente — patch DKMS do hid-playstation NÃO instalado (driver in-tree continua, fail-safe)"
        return 0
    fi
    if ! sudo -n true 2>/dev/null; then
        warn "sudo recusado — patch DKMS do hid-playstation pulado (re-execute ./install.sh)"
        return 0
    fi
    # shellcheck source=scripts/dkms_lib.sh
    source "${ROOT_DIR}/scripts/dkms_lib.sh"
    dkms_warn_secureboot_once  # PKG-1: avisa (não aborta) se SB pode barrar o .ko
    local _hidp_src="${ROOT_DIR}/assets/dkms/hid-playstation"
    dkms_install_patched_module hefesto-hid-playstation \
        "$(dkms_pkg_version "${_hidp_src}")" "${_hidp_src}" hid-playstation
    if sudo install -Dm644 "${ROOT_DIR}/assets/modprobe.d/hefesto-hid-playstation.conf" \
            /etc/modprobe.d/hefesto-hid-playstation.conf 2>/dev/null; then
        printf '      opções instaladas em /etc/modprobe.d/hefesto-hid-playstation.conf (feature_retries=2 + ds4_* do clone no cabo)\n'
    else
        warn "não consegui gravar /etc/modprobe.d/hefesto-hid-playstation.conf"
    fi
    # Mesmo achado #5 do hid-nintendo: dkms_install_patched_module é fail-safe
    # POR DESENHO (retorna 0 em TODOS os ramos) — o único juiz de "staged de
    # verdade" é o modinfo resolver p/ updates/dkms.
    if ! dkms_module_from_updates hid-playstation; then
        warn "patch DKMS do hid-playstation NÃO ficou staged (veja avisos acima) — driver in-tree continua (fail-safe); a conf do modprobe.d é inerte com o in-tree ('unknown parameter ignored') e o 2º DualSense segue podendo se perder na probe"
        return 0
    fi
    # ATIVAÇÃO FAIL-SAFE — aqui a regra é MAIS dura que a do hid-nintendo:
    # recarregar o hid_playstation derruba TODOS os DualSense, e os por
    # Bluetooth perdem o link. NUNCA recarregamos. O marcador de "patchado
    # carregado" é o parâmetro NOVO feature_retries (o in-tree tem zero
    # params, então o diretório parameters/ sequer existe nele).
    if [[ -e /sys/module/hid_playstation/parameters/feature_retries ]]; then
        printf '      módulo patchado JÁ carregado (feature_retries visível em /sys/module/hid_playstation/parameters)\n'
        # AUTO-01.7: param A QUENTE — paridade com o caminho por PACOTE
        # (scripts/install-host-udev.sh). `feature_retries` é lido A CADA
        # PROBE, e o probe roda a cada CONEXÃO do controle: escrever aqui faz a
        # cura do "segundo DualSense que some" valer no próximo pareamento, sem
        # reboot e sem reload (proibido: derrubaria os DualSense por BT).
        # Portão de EXISTÊNCIA, nunca `-w`: /sys/module é root:root 0644 e o
        # install roda SEM sudo, então `-w` é sempre falso e a escrita por
        # `sudo tee` logo abaixo nunca aconteceria (mesma restrição do
        # hid-nintendo acima).
        if [[ -e /sys/module/hid_playstation/parameters/feature_retries ]]; then
            printf '2' | sudo tee /sys/module/hid_playstation/parameters/feature_retries >/dev/null 2>&1 || true
            printf '      feature_retries aplicado a quente (vale na próxima conexão, sem reboot)\n'
        fi
        # Mesma lógica para a cura do CLONE no cabo (pairing info de 9 bytes
        # em vez de 16): lidos a cada probe, valem no próximo plug. Ausentes
        # no módulo patchado antigo (só tinha feature_retries) — por isso cada
        # um é decidido pela sua própria EXISTÊNCIA, sem avisar à toa. Caminhos
        # LITERAIS de propósito: a paridade com o install-host-udev.sh é
        # verificada por grep (AUTO-01.7).
        if [[ -e /sys/module/hid_playstation/parameters/ds4_short_pairing_info ]]; then
            printf 'Y' | sudo tee /sys/module/hid_playstation/parameters/ds4_short_pairing_info >/dev/null 2>&1 || true
            printf '      ds4_short_pairing_info aplicado a quente (clone no cabo; vale no próximo plug)\n'
        fi
        if [[ -e /sys/module/hid_playstation/parameters/ds4_synthetic_mac ]]; then
            printf 'Y' | sudo tee /sys/module/hid_playstation/parameters/ds4_synthetic_mac >/dev/null 2>&1 || true
            printf '      ds4_synthetic_mac aplicado a quente (clone no cabo; vale no próximo plug)\n'
        fi
    elif [[ -d /sys/module/hid_playstation ]]; then
        printf '      módulo in-tree em uso — NÃO recarregamos (derrubaria os DualSense, inclusive os por BT);\n'
        printf '      o patchado vale no próximo boot (reconectar NÃO troca módulo carregado)\n'
    else
        printf '      hid_playstation descarregado — o patchado entra sozinho na próxima conexão\n'
    fi
    return 0
}

# INITRAMFS-01 (25/07): fecha o furo entre `dkms install` e o BOOT. O initramfs
# leva uma CÓPIA do .ko e não é regenerado pelo dkms — o boot seguia carregando
# o módulo da geração anterior. Compartilhada entre o passo 3k (native) e o
# bloco dos formatos de pacote, igual às duas funções DKMS acima; roda UMA vez
# porque a lib coalesce (dkms_mark_initramfs_stale × dkms_flush_initramfs).
# Silenciosa e no-op quando nenhum módulo DKMS ficou staged (--no-dkms, dkms
# ausente, build falho): quem marca é só o ramo de sucesso da lib.
flush_initramfs_host() {
    if [[ "${NO_DKMS}" -eq 1 ]]; then
        printf '      pulado (--no-dkms)\n'
        return 0
    fi
    if ! command -v sudo >/dev/null 2>&1 || ! sudo -n true 2>/dev/null; then
        warn "sudo indisponível — initramfs NÃO regenerado; se um módulo DKMS mudou, o próximo boot ainda carrega a cópia antiga (rode: sudo update-initramfs -u)"
        return 0
    fi
    # shellcheck source=scripts/dkms_lib.sh
    source "${ROOT_DIR}/scripts/dkms_lib.sh"
    dkms_flush_initramfs
    return 0
}

# Onda W (desenho: docs/process/estudos/2026-07-20-desenho-onda-w-patch-dkms.md):
# módulo rtw88_usb patchado (device-gone + queue de port reset — cura do
# fantasma USB do dongle WiFi) via a MESMA lib genérica scripts/dkms_lib.sh
# (2ª instância — hid-nintendo é a 1ª; ZERO ajuste na lib). DEFAULT ON (regra
# da casa: install SEM FLAGS aplica), mesmo gate NO_DKMS do hid-nintendo
# acima (--no-dkms desliga AMBOS). Compartilhada entre o passo 3j (native) e
# o bloco dos formatos de pacote (mesmo padrão do broker/hid-nintendo acima)
# — DKMS é mudança de SISTEMA/kernel, ortogonal ao formato do app. Contrato
# fail-safe fica TODO dentro de dkms_lib.sh: esta função só decide SE chama
# (flag/sudo) e a mensagem de ativação, nunca recarrega/descarrega o módulo.
#
# Diferente do hid-nintendo (sem conf de /etc/modprobe.d): o gate da parte
# agressiva do patch (usb_queue_reset_device) É o próprio module param
# `hang_reset`, com default Y JÁ embutido no .ko (assets/dkms/rtw88-usb/
# usb.c) — não há arquivo externo a instalar/remover para ativá-lo.
install_dkms_rtw88_usb_host() {
    if [[ "${NO_DKMS}" -eq 1 ]]; then
        printf '      pulado (--no-dkms)\n'
        return 0
    fi
    if ! command -v sudo >/dev/null 2>&1; then
        warn "sudo ausente — patch DKMS do rtw88_usb NÃO instalado (driver in-tree continua, fail-safe)"
        return 0
    fi
    if ! sudo -n true 2>/dev/null; then
        warn "sudo recusado — patch DKMS do rtw88_usb pulado (re-execute ./install.sh)"
        return 0
    fi
    # shellcheck source=scripts/dkms_lib.sh
    source "${ROOT_DIR}/scripts/dkms_lib.sh"
    dkms_warn_secureboot_once  # PKG-1: avisa (não aborta) se SB pode barrar o .ko
    # PKG-3: versão do dkms.conf (fonte da verdade), não literal hardcoded.
    local _rtw_src="${ROOT_DIR}/assets/dkms/rtw88-usb"
    dkms_install_patched_module hefesto-rtw88-usb \
        "$(dkms_pkg_version "${_rtw_src}")" "${_rtw_src}" rtw88_usb
    # Mesmo achado #5 do hid-nintendo: dkms_install_patched_module é
    # fail-safe POR DESENHO (retorna 0 em TODOS os ramos) — o único juiz de
    # "staged de verdade" é o modinfo resolver p/ updates/dkms.
    if ! dkms_module_from_updates rtw88_usb; then
        warn "patch DKMS do rtw88_usb NÃO ficou staged (veja avisos acima) — driver in-tree continua (fail-safe); sem device-gone/port-reset, o fantasma USB do dongle (device retido após disconnect perdido) segue possível"
        return 0
    fi
    # ATIVAÇÃO FAIL-SAFE (mesmo princípio do hid-nintendo acima): NUNCA
    # recarregamos um módulo em uso — a mantenedora depende do WiFi AGORA, e
    # substituir o módulo carregado o derrubaria. Diferente do hid_nintendo
    # (0 params no in-tree), o rtw88_usb in-tree JÁ expõe `switch_usb_mode`
    # — a presença do diretório parameters/ sozinha NÃO distingue patchado
    # de in-tree. O marcador é o PARÂMETRO NOVO `hang_reset` (só o patch
    # tem). Nota de precisão (igual ao hid-nintendo): substituição de módulo
    # NÃO pega em replug do dongle — se o in-tree está CARREGADO, o replug
    # o re-liga a ele mesmo; só o próximo BOOT troca. "Entra no próximo
    # plug" só é verdade quando o módulo está DESCARREGADO agora (3º ramo).
    if [[ -e /sys/module/rtw88_usb/parameters/hang_reset ]]; then
        printf '      módulo patchado JÁ carregado (hang_reset visível em /sys/module/rtw88_usb/parameters)\n'
        # O uninstall devolve `hang_reset` a 0 de propósito (driver menos
        # agressivo até o boot), e sem este rearme o ciclo uninstall+install
        # deixa o reset de porta do fantasma do dongle desligado, com o default
        # Y do .ko só voltando no próximo boot. O param é lido em tempo de
        # execução, então escrever aqui vale agora. Simetria cobrada por teste.
        printf 'Y' | sudo tee /sys/module/rtw88_usb/parameters/hang_reset >/dev/null 2>&1 || true
    elif [[ -d /sys/module/rtw88_usb ]]; then
        printf '      módulo in-tree em uso — NÃO recarregamos (derrubaria o WiFi ao vivo);\n'
        printf '      o patchado vale no próximo boot (replug NÃO troca módulo carregado)\n'
    else
        printf '      rtw88_usb descarregado — o patchado entra sozinho no próximo plug do dongle\n'
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
    bash "${ROOT_DIR}/scripts/build_deb.sh" \
        || die "build_deb.sh falhou"
    local deb
    deb="$(ls -t "${ROOT_DIR}/dist/"*.deb 2>/dev/null | head -1)"
    [[ -n "${deb}" ]] || die "nenhum .deb gerado em dist/"
    command -v sudo >/dev/null 2>&1 || die "sudo necessário para 'apt install'"
    sudo apt-get install -y "${deb}" || die "apt install falhou"
    printf '\n      Instalado via apt (udev + .desktop via postinst).\n      Abrir: hefesto-dualsense4unix-gui\n'
}

# ANTES DO DESVIO DE FORMATO (11/08/2026) — e a posição importa.
#
# Estes dois blocos nasceram DEPOIS da linha do `exit 0`, e a revisão de 11/08
# pegou o furo: os três módulos DKMS são construídos no ramo de pacote (os
# `step "dkms*"` logo abaixo), ANTES daquele `exit`. Garantir as dependências
# só no fluxo nativo deixava o "verde mentiroso" de pé em `--deb`, `--flatpak`
# e `--appimage` — exatamente o que o bloco existe para curar. Mover para cá é
# a cura; deixar embaixo era comentário prometendo o que a posição não
# entregava.

# VOO DE RECONHECIMENTO (11/08/2026) — o que esta máquina é, ANTES de mexer
# nela.
#
# Nasceu de uma frase dela sobre levar o produto para outro PC: "o ideal é que o
# nosso install contivesse isso também". Antes, as três respostas que decidem se
# a instalação vai funcionar só apareciam DEPOIS: o aviso de Secure Boot mora em
# `scripts/dkms_lib.sh:110` e só dispara no passo 3i, quando a senha já foi
# digitada e quarenta passos já rodaram; o veredito de BlueZ só sai na
# conferência final; e a família da distro só se descobre quando o `run_apt`
# falha.
#
# Nenhum destes três ABORTA. Eles informam no momento em que a informação ainda
# muda a decisão de quem instala — que é a diferença entre um aviso e um
# lamento.
_reconhecimento() {
    local achou_algo=0

    # 1. Família da distro. O caminho nativo só sabe `apt-get` (ver `run_apt`).
    if ! command -v apt-get >/dev/null 2>&1; then
        warn "sem apt-get: esta não é uma distro da família Debian/Ubuntu"
        printf '      O caminho nativo instala dependências só por apt. Em Fedora, Arch ou\n'
        printf '      Nix, use o pacote da sua distro (ver docs/usage/instalacao.md) — e saiba\n'
        printf '      que nenhum deles foi validado em hardware ainda.\n'
        achou_algo=1
    fi

    # 2. BlueZ. A faixa validada é a mesma que o doctor cobra no fim.
    local _bz
    _bz="$(bluetoothctl --version 2>/dev/null | awk '{print $NF}')"
    if [[ -n "${_bz}" ]]; then
        # Compara só major.minor; o formato do bluetoothctl é "bluetoothctl: 5.86".
        if [[ "$(printf '%s\n5.79\n' "${_bz}" | sort -V | head -1)" != "5.79" ]]; then
            warn "bluez ${_bz} — abaixo de 5.79, a faixa que esta casa validou"
            printf '      Abaixo de 5.79 há crashes crônicos de input/HIDP (medidos: 6 em 5 dias).\n'
            printf '      A conferência final vai REPROVAR por isto. A cura é um backport, e a\n'
            printf '      receita está em docs/process/estudos/2026-07-19-estudo-bluez-backport-onda-r.md\n'
            achou_algo=1
        fi
    fi

    # 3. Secure Boot. É o único dos três que deixa a máquina PIOR que antes: o
    # kernel recusa o .ko e NÃO volta ao módulo in-tree sozinho.
    if command -v mokutil >/dev/null 2>&1 &&
       mokutil --sb-state 2>/dev/null | grep -qi 'SecureBoot enabled'; then
        warn "Secure Boot ATIVO — os módulos DKMS podem não carregar no próximo boot"
        printf '      Sem a chave MOK enrolada, o kernel RECUSA o .ko e não volta ao driver\n'
        printf '      in-tree sozinho: um controle Nintendo pode sumir depois de reiniciar.\n'
        printf '      Se acontecer: sudo mokutil --import /var/lib/dkms/mok.pub\n'
        printf '      (placa NVIDIA por DKMS funcionando indica que a chave já está enrolada.)\n'
        achou_algo=1
    fi

    # `info` NUNCA foi função deste script — só existem step/ok/warn/die (l. 323-326).
    # O shell caía no /usr/bin/info do sistema (o leitor de documentação GNU), que
    # sai com erro, e o `set -e` derrubava a instalação no passo 1. E a linha só
    # executa quando NADA atrapalha — ou seja, quebrava exatamente na máquina limpa,
    # que é a primeira coisa que um PC novo faz. Medido no ciclo uninstall→install
    # de 12/08/2026: zero regras udev, daemon inativo, produto ausente.
    [[ "${achou_algo}" -eq 0 ]] && printf '      distro, bluez e Secure Boot: nada que atrapalha\n'
    return 0
}
_reconhecimento
ok

# --- DKMS-CAUSA-RAIZ-01: o que os três módulos precisam para COMPILAR --------
# Medido em 11/08/2026, na auditoria de "o que só existe nesta máquina": o
# `install.sh` instala TRÊS módulos DKMS por padrão, sem flag, e nunca garantia
# `dkms` nem os headers do kernel. Quando faltam, `scripts/dkms_lib.sh:269` e
# `:273` pulam o módulo com um aviso que some entre 46 passos — e, pior, o
# `doctor` chama módulo ausente de `info`, que não conta como falha.
#
# O resultado numa máquina nova era o pior possível: os três forks não entram,
# a conferência final sai VERDE, e o aparelho se comporta diferente sem que
# nada na tela explique por quê. Esta é a causa raiz daquele verde mentiroso.
#
# Best-effort com a mesma disciplina do bloco de áudio abaixo: se ela recusar,
# ou se a distro não tiver os headers deste kernel exato (kernel de fora do
# apt), o instalador AVISA e SEGUE. Abortar seria pior — o driver in-tree
# continua funcionando, só sem as curas.
if [[ "${NO_DKMS}" -eq 0 ]] && command -v apt-get >/dev/null 2>&1; then
    _dkms_faltando=()
    command -v dkms >/dev/null 2>&1 || _dkms_faltando+=("dkms")
    command -v make >/dev/null 2>&1 || _dkms_faltando+=("build-essential")
    [[ -d "/lib/modules/$(uname -r)/build" ]] || _dkms_faltando+=("linux-headers-$(uname -r)")

    if [[ "${#_dkms_faltando[@]}" -gt 0 ]]; then
        printf '\n      Os três módulos de kernel desta casa precisam compilar, e falta:\n'
        printf '        %s\n' "${_dkms_faltando[*]}"
        printf '      Sem eles, as curas NÃO entram: o controle da Nintendo pode não subir\n'
        printf '      pelo rádio, e dois DualSense no mesmo adaptador podem virar um só.\n\n'
        ask_yn "instalar agora com sudo?" "${AUTO_YES}"
        if [[ "${REPLY,,}" =~ ^y ]]; then
            if run_apt "${_dkms_faltando[@]}"; then
                printf '      pronto para compilar os módulos\n'
            else
                warn "não consegui instalar ${_dkms_faltando[*]} — os módulos DKMS vão ser pulados"
                printf '      O produto funciona com os drivers in-tree, sem as curas desta casa.\n'
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
    # Onda W (mesmo achado equivalente ao #7 do broker): rtw88_usb patchado é
    # a 2ª instância da mesma mudança de SISTEMA/kernel — mesma função do
    # passo 3j do fluxo native. Opt-out compartilhado: --no-dkms.
    step "dkms-w" "DKMS rtw88_usb patchado (Onda W — DEFAULT em todo formato)"
    install_dkms_rtw88_usb_host
    # 3ª instância da mesma mudança de SISTEMA/kernel — mesma função do passo
    # 3k do fluxo native. Opt-out compartilhado: --no-dkms.
    step "dkms-p" "DKMS hid-playstation patchado (contenção BT — DEFAULT em todo formato)"
    install_dkms_hid_playstation_host
    # INITRAMFS-01: um flush só, DEPOIS de todos os DKMS (regenerar por módulo
    # custaria dezenas de segundos e ~140 MB de escrita cada). No-op se nenhum
    # módulo ficou staged.
    step "dkms-i" "regenerar initramfs se algum módulo DKMS mudou (INITRAMFS-01)"
    flush_initramfs_host
    # TECLADO-QUE-NAO-DIGITA-01: mesmo achado do broker (#7 da Onda S) numa
    # camada nova — o teclado na tela é pacote do SISTEMA, ortogonal ao formato
    # do app. Sem esta chamada, `--flatpak`/`--appimage`/`--deb` sairiam pelo
    # `exit 0` logo abaixo sem o único caminho do produto para digitar texto.
    step "osk" "teclado na tela do L3 (TECLADO-QUE-NAO-DIGITA-01 — DEFAULT em todo formato)"
    install_osk_host
    # MIC-EM-TODO-FORMATO-01 (10/08/2026): a voz dela também é ortogonal ao
    # formato do app, e ficava para trás por acidente de posição.
    #
    # Os drop-ins do WirePlumber vivem em `~/.config/wireplumber/` — o HOME dela,
    # não o prefixo do pacote. **Nenhum formato os empacota** (conferido: zero
    # ocorrências de "wireplumber" em packaging/ e flatpak/), então o único jeito
    # de eles chegarem é este script chamar o dono deles. Instalando por
    # `--flatpak`/`--appimage`/`--deb`, o microfone do controle ficava sem o
    # promotor: a entrada nasce com `priority.session = 50`, o monitor da saída
    # ganha a eleição, e o que qualquer aplicativo grava é o eco do que sai — não
    # a voz dela. Medido em 08/08 e curado no MONITOR-QUE-VENCE-01, mas só no
    # caminho nativo.
    #
    # Respeita as MESMAS flags do passo 10 do nativo: quem pediu
    # `--keep-dualsense-mic` continua sem ninguém mexendo no áudio, e
    # `--with-wireplumber-disable-mic` continua vencendo. O que muda é só a
    # posição no arquivo — a decisão é a dela, em qualquer formato.
    # SOM-QUE-NAO-DORME-01 (16/08/2026) — SEM FLAG, e ANTES de qualquer decisão
    # sobre o microfone, porque não é uma decisão sobre o microfone.
    #
    # Medido na orelha dela em 15/08 23h45: com o nó do PipeWire SUSPENSO, o
    # primeiro som depois do silêncio se perde no religar do hardware — num jogo,
    # é o SFX importante sumindo. Nenhuma das flags de mic
    # (`--keep-dualsense-mic`, `--with-wireplumber-disable-mic`) diz nada sobre o
    # sono do ALTO-FALANTE, então nenhuma delas pode decidir isto.
    step "som" "áudio: o alto-falante do controle nunca dorme (SOM-QUE-NAO-DORME-01)"
    bash "${ROOT_DIR}/scripts/fix_wireplumber_default_source.sh" --nunca-dorme \
        || warn "nunca-dorme falhou — rode: bash scripts/fix_wireplumber_default_source.sh --nunca-dorme"
    if [[ "${WITH_WIREPLUMBER_DISABLE_MIC}" -eq 1 ]]; then
        step "mic" "áudio: desabilitar o microfone do DualSense (--with-wireplumber-disable-mic)"
        bash "${ROOT_DIR}/scripts/fix_wireplumber_default_source.sh" --disable-source \
            || warn "disable-source falhou — rode: bash scripts/fix_wireplumber_default_source.sh --disable-source"
    elif [[ "${WITH_WIREPLUMBER_FIX}" -eq 1 ]]; then
        step "mic" "áudio: a voz do controle acima do eco da saída (MIC-EM-TODO-FORMATO-01)"
        bash "${ROOT_DIR}/scripts/fix_wireplumber_default_source.sh" --install \
            || warn "fix do WirePlumber falhou — rode: bash scripts/fix_wireplumber_default_source.sh --install"
    fi
    printf '\n─────────────────────────────────────────\n'
    printf ' Hefesto - Dualsense4Unix instalado (%s)\n' "${FORMAT}"
    printf ' Obs.: desligar do Steam Input, preparo dos jogos da Steam e os\n'
    printf ' passos de plataforma (Proton pinado, BT no máximo, cmdline) só\n'
    printf ' valem no formato "native" (padrão).\n'
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

# --- BT-MIC-01: microfone do DualSense por Bluetooth -------------------------
# Em Bluetooth o DualSense NÃO fala A2DP/HFP: o áudio do microfone vem como
# Opus dentro dos reports HID e a ponte (`mic bt`) o decodifica por ctypes
# sobre a libopus DO SISTEMA — de propósito, para não precisar de binding pip
# (regra do projeto: nada de pip ad-hoc; tudo replicável por script).
# `pactl` (pulseaudio-utils) é quem publica o microfone no PipeWire.
# Best-effort: sem isso o hefesto inteiro funciona, só o `mic bt` não sobe —
# e ele já diz exatamente o que falta (`mic bt-status`).
_btmic_faltando=()
ldconfig -p 2>/dev/null | grep -q 'libopus\.so\.0' || _btmic_faltando+=(libopus0)
command -v pactl >/dev/null 2>&1 || _btmic_faltando+=(pulseaudio-utils)
if (( ${#_btmic_faltando[@]} )); then
    printf '\n      Microfone por Bluetooth: faltam %s\n' "${_btmic_faltando[*]}"
    ask_yn "instalar agora com sudo?" "${AUTO_YES}" "y"
    if [[ "${REPLY,,}" =~ ^y ]]; then
        if run_apt "${_btmic_faltando[@]}"; then
            printf '      ok — `hefesto-dualsense4unix mic bt` disponível\n'
        else
            warn "não instalei ${_btmic_faltando[*]} — o mic por BT fica indisponível"
        fi
    else
        printf '      pulando (mic por BT indisponível; instale depois: sudo apt install %s)\n' \
            "${_btmic_faltando[*]}"
    fi
fi
unset _btmic_faltando

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
    # BUG-INSTALL-SUGERE-FLAG-INEXISTENTE-01 (29/07): a mensagem dizia
    # "opt-in via --disable-usb-audio" como se fosse flag DESTE script. Não é:
    # o parser aqui não a conhece e ABORTA com código 2 ("argumento
    # desconhecido"), então quem seguisse a sugestão não instalava nada. A flag
    # é do scripts/install_udev.sh — a mensagem passa a dizer o comando que
    # funciona de verdade.
    printf '      (75 áudio-off é opt-in: sudo bash scripts/install_udev.sh --disable-usb-audio)\n'

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
#
# O PULO TEM DE FALAR (achado de 06/08/2026): este passo era gateado por
# `SKIP_UDEV -eq 0` SEM `else`. Com `--no-udev`, o `step "3d"` nem imprimia: a
# cura do BlueZ inteira sumia da saída, e numa máquina com
# `JustWorksRepairing=always` no disco o valor perigoso SOBREVIVIA ao install
# sem uma palavra — enquanto o detector novo do doctor manda "rode ./install.sh"
# sem ressalva. O vizinho 3d-bis já fazia certo.
#
# NOTA DATADA — A JUSTIFICATIVA ANTERIOR ERA FALSA (06/08/2026). Até hoje este
# comentário sustentava o gate dizendo que "é o que o CI sem hardware usa:
# separar o gate faria o CI reescrever /etc/bluetooth/main.conf da máquina de
# build". MEDIDO que a premissa não existe: **o CI não roda o `install.sh`**.
#
# E A INSTRUÇÃO DE REPRODUÇÃO DESTA NOTA ESTAVA ERRADA (correção do mesmo dia,
# achado por verificação independente): ela mandava rodar
# `grep -rn 'install\.sh' .github/workflows/` e dizia que acha UMA linha. Acha
# DUAS, e a segunda é armadilha de leitura — `ci.yml:120` casa porque a palavra
# `install.sh` está DENTRO de `uninstall.sh`, num comentário. A conclusão não
# muda: a única linha que fala do arquivo é `ci.yml:136`,
# `shellcheck -S error scripts/*.sh install.sh uninstall.sh`, e nenhuma das duas
# INVOCA o instalador. Mas mandar o próximo leitor conferir um número que não
# bate é o começo de ele desconfiar do resto — e o resto está certo.
#
# Decisão gravada sobre medição que não existe é a semente da próxima "hipótese
# que não explica o que já funcionava", então a nota fica.
#
# A DECISÃO SE MANTÉM, pelo motivo VERDADEIRO: `--no-udev` está documentado no
# cabeçalho deste arquivo (linha "…--no-udev pula os que tocam /etc") como o
# opt-out dos passos que escrevem em /etc, e este passo escreve em
# /etc/bluetooth/main.conf — que é conffile do dpkg. Tirar o passo do gate faria
# a flag deixar de cumprir o próprio contrato, na máquina de quem a usa por
# escolha e não em CI nenhum. O que MUDOU em 06/08 é que o pulo é anunciado, com
# o comando exato do que ficou por fazer, e o estado ATUAL do disco é lido e
# dito — leitura pura, pelo dono único, sem sudo.
if [[ "${SKIP_UDEV}" -eq 1 ]]; then
    step "3d" "Bluetooth no máximo — PULADO (--no-udev)"
    warn "btusb sem autosuspend e config do BlueZ NÃO aplicados (o passo toca /etc)"
    warn "  falta fazer: sudo bash ${ROOT_DIR}/scripts/bluez_config.sh aplicar"
    warn "  falta fazer: sudo install -Dm644 assets/modprobe.d/hefesto-btusb-no-autosuspend.conf /etc/modprobe.d/hefesto-btusb-no-autosuspend.conf"
    _bt_estado="$(HEFESTO_BT_SUDO="" HEFESTO_BT_ASSETS="${ROOT_DIR}/assets/bluetooth" \
        bash "${ROOT_DIR}/scripts/bluez_config.sh" verificar 2>/dev/null \
        | sed -n 's/^JustWorksRepairing: //p' || true)"
    if [[ "${_bt_estado}" == "always" ]]; then
        warn "  e ATENÇÃO: o disco está com JustWorksRepairing=always AGORA — com --no-udev este install NÃO corrigiu isso (RADIO-ABERTO-01)"
    elif [[ -n "${_bt_estado}" && "${_bt_estado}" != "confirm" && "${_bt_estado}" != "ausente" ]]; then
        warn "  e o disco está com JustWorksRepairing=${_bt_estado} AGORA — este install NÃO tocou nesse valor"
    fi
    unset _bt_estado
elif command -v sudo >/dev/null 2>&1; then
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
        # Config do BlueZ (FastConnectable + JustWorksRepairing): o dono é o
        # scripts/bluez_config.sh, e a lógica saiu DAQUI de propósito.
        #
        # RADIO-ABERTO-01/E1-bis (06/08/2026) — POR QUE A MUDANÇA:
        # o mecanismo morava inline neste arquivo, e por isso nenhum teste da
        # suíte conseguia EXERCITÁ-LO (todos liam install.sh/uninstall.sh como
        # texto). Foi assim que passou despercebido o defeito MEDIDO na máquina
        # dela em 06/08: `/etc/bluetooth/main.conf:25` com
        # `JustWorksRepairing=always`, DENTRO do bloco `# >>> hefesto bluetooth
        # >>>` — escrito por uma versão anterior deste próprio projeto. Os
        # assets passaram a `confirm` em 05/08 e o valor perigoso continuou no
        # disco porque só uma execução do install reescreve o arquivo, e não
        # houve nenhuma entre as duas datas. Com o mecanismo num script
        # próprio, a bancada de raiz falsa (tests/unit/test_bluez_config_sh.py)
        # prova que valor inseguro preexistente vira `confirm`.
        #
        # O que o `aplicar` garante, e este passo não repete para não divergir:
        # idempotência (rodar N vezes não acumula seção nem backup), backup do
        # conffile só quando há mudança real, escrita ATÔMICA (temporário no
        # mesmo diretório + rename, para que uma queda no meio não deixe o
        # conffile dela truncado), neutralização reversível de chave de
        # terceiro, RELATÓRIO (nunca poda automática) dos backups e — a
        # assimetria fechada — o
        # main.conf normalizado SEMPRE, com os drop-ins de main.conf.d POR CIMA
        # quando o diretório existe (antes, o diretório presente fazia o
        # install anunciar `confirm` sem nunca abrir o main.conf, onde o
        # `always` seguia vivo).
        # ARMADILHA respeitada: NUNCA reiniciamos o bluetoothd aqui.
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

# ---------------------------------------------------------------------------
# 3d-bis. Powersave do WiFi desligado (Onda W2) — OPT-IN, gateado por evidência
# ---------------------------------------------------------------------------
# SÓ com --wifi-powersave-off: instala o conf.d do NetworkManager que põe
# wifi.powersave=2 (disable) — a via de PROMOÇÃO documentada no próprio asset
# para quando a medição A/B do scripts/medir_w2_lps.sh provar ganho (o LPS
# raso do firmware rtw88 em dongle USB tem histórico de 'failed to leave lps
# state'/beacon loss). NUNCA chamamos nmcli/rfkill aqui: só a cópia do conf —
# vale na próxima (re)conexão gerida pelo NM. Remoção: uninstall.sh (simétrico,
# "se instalado, some") ou sudo rm do conf. doctor.sh reporta o estado.
if [[ "${WIFI_POWERSAVE_OFF}" -eq 1 ]]; then
    step "3d-bis" "powersave do WiFi OFF (conf.d do NetworkManager — opt-in W2)"
    if [[ "${SKIP_UDEV}" -eq 1 ]]; then
        warn "--no-udev ativo — passo de /etc pulado (rode sem --no-udev para aplicar)"
    elif ! command -v sudo >/dev/null 2>&1 || ! sudo -n true 2>/dev/null; then
        warn "sudo indisponível/recusado — conf de powersave NÃO instalado; re-execute:"
        warn "  sudo install -Dm644 assets/NetworkManager/hefesto-wifi-powersave.conf /etc/NetworkManager/conf.d/hefesto-wifi-powersave.conf"
    elif sudo install -Dm644 "${ROOT_DIR}/assets/NetworkManager/hefesto-wifi-powersave.conf" \
            /etc/NetworkManager/conf.d/hefesto-wifi-powersave.conf 2>/dev/null; then
        printf '      conf instalado em /etc/NetworkManager/conf.d/hefesto-wifi-powersave.conf (wifi.powersave=2)\n'
        printf '      vale na próxima (re)conexão do NM — nada foi tocado no rádio agora\n'
    else
        warn "não consegui gravar /etc/NetworkManager/conf.d/hefesto-wifi-powersave.conf"
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
# 3e-bis. ONDA-R2: resiliência do bluetoothd — DEFAULT (camada 2 da sprint
#         2026-07-21-sprint-pesquisa-bluez-estabilidade.md)
# ---------------------------------------------------------------------------
# O crash de heap do bluetoothd destrói bonds e deixa o daemon renascido
# "doente" (recusa devices pareados em loop — medido 21/07). Quatro entregas:
#   1. scripts de sistema em /usr/local/lib/hefesto-dualsense4unix/ (mesma
#      casa do broker root): snapshot/restore de bonds, watchdog de saúde e
#      captura forense (esta última NUNCA ligada por default);
#   2. drop-in do bluetooth.service: Restart=on-failure reafirmado (o template
#      upstream traz comentado — bump futuro do pacote pode regredir) +
#      WatchdogSec=0 (BLUETOOTHD-MORTO-POR-NOS-01: era 30 e o systemd MATOU o
#      bluetoothd dela com SIGABRT em 08/08, levando os quatro pareamentos)
#      + snapshot de bonds a cada parada;
#   3. timer de snapshot (15min, deduplicado por conteúdo, NUNCA fotografa
#      estado vazio, e a poda nunca joga fora o MELHOR snapshot) + a VOLTA
#      automática (bt_bonds_autorestore.sh no ExecStopPost do drop-in), que é a
#      decisão dela de 08/08: "restauro de bonds tem de ser automático; manual
#      com sudo não é produto". A volta só corre quando o daemon MORREU
#      (SERVICE_RESULT != success), é ADITIVA (nunca escreve por cima de uma
#      [LinkKey] viva — é assim que a chave rotacionada deixa de ser risco) e
#      tem quarentena por boot. O bt_bonds_restore.sh continua existindo para o
#      restauro completo decidido à mão;
#   4. timer do watchdog (2min): estado doente → restart rate-limitado (só com
#      0 devices conectados); bond Paired-sem-Bonded (temporário, evapora no
#      disconnect — medido 22/07) → promoção via Pair() explícito 1x/boot.
# Ordem importa: este passo vem ANTES do 3f porque o postinst do backport
# reinicia o bluetoothd — o drop-in precisa existir para armar nesse restart.
if [[ "${SKIP_UDEV}" -eq 0 ]] && command -v sudo >/dev/null 2>&1; then
    step "3e-bis" "ONDA-R2: resiliência do bluetoothd (watchdog + snapshot de bonds)"
    if ! sudo -n true 2>/dev/null; then
        warn "sudo recusado — resiliência do bluetoothd pulada (re-execute ./install.sh)"
    else
        _btres_ok=1
        for _btres_s in bt_bonds_snapshot.sh bt_bonds_restore.sh bt_bonds_autorestore.sh bt_health_watchdog.sh bt_crash_capture.sh bt_active_mode.sh bt_nosniff_now.sh bt_rebind_orphans.sh; do
            sudo install -Dm755 "${ROOT_DIR}/scripts/${_btres_s}" \
                "/usr/local/lib/hefesto-dualsense4unix/${_btres_s}" 2>/dev/null || _btres_ok=0
        done
        # BT-NINTENDO-ACTIVE-01: aplica JÁ (nome "Nintendo*" + link policy sem
        # SNIFF) — cura de raiz da queda do Pro/8BitDo sob carga (pesquisa
        # 2026-07-22). Idempotente; o drop-in reaplica a cada start do
        # bluetoothd e o watchdog reafirma a cada 2 min.
        sudo /usr/local/lib/hefesto-dualsense4unix/bt_active_mode.sh 2>/dev/null || true
        sudo install -Dm644 "${ROOT_DIR}/assets/systemd/bluetooth-dropin-10-hefesto-resilience.conf" \
            /etc/systemd/system/bluetooth.service.d/10-hefesto-resilience.conf 2>/dev/null || _btres_ok=0
        for _btres_u in hefesto-bt-bonds-snapshot.service hefesto-bt-bonds-snapshot.timer \
                        hefesto-bt-health-watchdog.service hefesto-bt-health-watchdog.timer; do
            sudo install -Dm644 "${ROOT_DIR}/assets/systemd/${_btres_u}" \
                "/etc/systemd/system/${_btres_u}" 2>/dev/null || _btres_ok=0
        done
        sudo install -d -m700 /var/lib/hefesto-dualsense4unix/bt-bonds 2>/dev/null || true
        sudo systemctl daemon-reload >/dev/null 2>&1 || true
        if sudo systemctl enable --now hefesto-bt-bonds-snapshot.timer \
                hefesto-bt-health-watchdog.timer >/dev/null 2>&1; then
            printf '      timers ativos: snapshot de bonds (15 em 15 min) + watchdog de saúde (2 em 2 min)\n'
        else
            warn "enable dos timers de resiliência falhou — habilite manualmente (systemctl enable --now hefesto-bt-*.timer)"
            _btres_ok=0
        fi
        if [[ "${_btres_ok}" -eq 1 ]]; then
            printf '      drop-in de resiliência instalado (Restart reafirmado + WatchdogSec=0 + snapshot na parada)\n'
            printf '      restauro AUTOMÁTICO de bonds armado: se o bluetoothd morrer, os bonds que\n'
            printf '        ele comeu voltam sozinhos antes do próximo start (aditivo; nunca por cima\n'
            printf '        de chave viva). Nada a digitar, nenhum sudo.\n'
            printf '      vale no próximo restart do bluetoothd; captura forense é OPT-IN: bt_crash_capture.sh --on\n'
        else
            warn "resiliência do bluetoothd instalada PARCIALMENTE — confira as mensagens acima"
        fi
    fi
fi

# ---------------------------------------------------------------------------
# 3f. ONDA-R: BlueZ resiliente (backport local — alvo 5.86) — DEFAULT
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
    step "3f" "ONDA-R: BlueZ resiliente (backport 5.86 — crashes crônicos + heap do loop de reconexão)"
    if ! sudo -n true 2>/dev/null; then
        warn "sudo recusado — passo do backport bluez pulado (re-execute ./install.sh)"
    else
        # Alvo do backport (sprint 2026-07-21-sprint-pesquisa-bluez-estabilidade.md):
        # 5.86 traz o retry-limit + backoff em loops de reconexão (upstream
        # 17a227b7) — o retrato estrutural do gatilho do crash de heap medido
        # em 21/07 no 5.85. 5.87 foi descartado (UAF novo em dev_disconnected,
        # fix só em git HEAD sem release).
        # 24.04.2 (22/07): patch hefesto-0001 — mantém o bond no Virtual Cable
        # Unplug (Pro/8BitDo evaporavam o bond a cada queda no caminho uhid;
        # ver docs/process/estudos/2026-07-22-pesquisa-pro-controller-bt-*.md).
        # Alvo é a VERSÃO COMPLETA (não "5.86") para o compare-versions detectar
        # o upgrade .1→.2 — senão o "já ≥5.86" pularia o patch novo.
        _BZ_TARGET="5.86-0ubuntu0.1~hefesto24.04.3"
        _bz_cur="$(dpkg-query -W -f='${Version}' bluez 2>/dev/null || true)"
        if [[ -z "${_bz_cur}" ]]; then
            printf '      bluez não instalado via dpkg (sistema não-Debian?) — passo pulado\n'
        elif dpkg --compare-versions "${_bz_cur}" ge "${_BZ_TARGET}" 2>/dev/null; then
            printf '      bluez %s já ≥%s — nada a fazer\n' "${_bz_cur}" "${_BZ_TARGET}"
        else
            printf '      bluez %s < alvo %s (5.72: crashes crônicos de input/HIDP; 5.85: heap corruption no loop de reconexão — ver sprint 2026-07-21)\n' "${_bz_cur}" "${_BZ_TARGET}"
            _bz_dir="${HOME}/.cache/hefesto-dualsense4unix/bluez-backport"
            _bz_sums="${_bz_dir}/SHA256SUMS"
            _bz_deb_bluez="$(ls -t "${_bz_dir}"/bluez_*.deb 2>/dev/null | head -1)"
            _bz_deb_cups="$(ls -t "${_bz_dir}"/bluez-cups_*.deb 2>/dev/null | head -1)"
            _bz_deb_libbt="$(ls -t "${_bz_dir}"/libbluetooth3_*.deb 2>/dev/null | head -1)"
            if [[ ! -f "${_bz_sums}" || -z "${_bz_deb_bluez}" || -z "${_bz_deb_cups}" || -z "${_bz_deb_libbt}" ]]; then
                # (d) .debs ausentes: NÃO falha o install, só orienta o build.
                warn "backport não encontrado em ${_bz_dir} — bluetoothd 5.72 crônico segue ativo"
                # A receita mora na ÁRVORE desde 11/08/2026. Antes esta linha
                # mandava para `git show arquivo/processo-pre-1.0:...`, um ramo
                # arquivado — e o `install.sh:1638` já citava o documento como se
                # ele estivesse aqui. Quem levasse o produto para outra máquina
                # lia uma instrução que não podia seguir.
                printf '      como gerar: docs/process/estudos/2026-07-19-estudo-bluez-backport-onda-r.md, seção 3, caminho 1\n'
                printf '      resumo: dget do .dsc do resolute -> dch --local -> mk-build-deps -ir -> dpkg-buildpackage -us -uc -b\n'
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
                    printf '\n      >>> AVISO: aplicar o backport do bluez REINICIA o bluetoothd\n'
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
                # AGENTE-EM-FAILED-NAO-VOLTA-PELO-INSTALL-01 (15/08/2026) — MEDIDO.
                #
                # `enable --now` NÃO tira uma unit do estado `failed`: o systemd
                # recusa iniciar quem bateu o `StartLimitBurst`, e o install
                # terminava com "habilitado" no texto e o agente morto de fato.
                #
                # O preço disso foi medido em 14/08: o agente ficou `failed` das
                # 16:17 às 00:31 e, sem ele, TODO bond novo nasce meio-salvo
                # (`Paired: yes / Bonded: no`) e some — que é o "conectam sozinhos
                # e desligam em sequência" que ela relatou. Reinstalar não
                # resolveria; só um `reset-failed` explícito resolve.
                #
                # O `KillSignal=SIGKILL` da unit (mesma data) impede que ele
                # ENTRE em `failed`. Esta linha cuida de quem JÁ está — as duas
                # são necessárias, e nenhuma substitui a outra.
                sudo systemctl reset-failed hefesto-bt-agent.service >/dev/null 2>&1 || true
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
# 3j. DKMS rtw88_usb patchado (Onda W) — DEFAULT, opt-out --no-dkms (compartilhado)
# ---------------------------------------------------------------------------
# Cura de RAIZ do fantasma USB do dongle WiFi (TP-Link Archer T3U/RTL8822BU):
# quando um port-status-change se perde no xHCI, o driver in-tree nunca detecta
# que o device sumiu e segue fazendo I/O contra hardware ausente — só um
# `unbind` manual ou reboot recicla o device (medido 20/07: 13h de fantasma).
# Módulo out-of-tree via DKMS (device-gone + queue de port reset, modelo
# rtw89 v7.0.11: RTW89_FLAG_UNPLUGGED + continual_io_error>4; reset imediato
# só em -ENODEV/-ESHUTDOWN, -EPROTO exige 5 falhas CONSECUTIVAS sem sucesso
# no meio) via a MESMA lib genérica scripts/dkms_lib.sh (Onda T é a 1ª
# instância; ZERO ajuste na lib). Desenho completo:
# docs/process/estudos/2026-07-20-desenho-onda-w-patch-dkms.md.
# Contrato fail-safe: dkms/headers ausentes, kernel fora do pino
# BUILD_EXCLUSIVE_KERNEL (ABI privada do rtw88) ou build falho = aviso
# honesto, o in-tree segue valendo, o install NUNCA aborta por causa disto.
step "3j" "Onda W: rtw88_usb patchado via DKMS (fantasma USB + teardown limpo)"
install_dkms_rtw88_usb_host

# ---------------------------------------------------------------------------
# 3k. DKMS hid-playstation patchado (contenção BT) — DEFAULT, opt-out --no-dkms
# ---------------------------------------------------------------------------
# Cura de RAIZ da perda de um DualSense inteiro quando vários controles pareiam
# quase juntos no mesmo adaptador — o cenário NORMAL do alvo do projeto (4 por
# Bluetooth, um por jogador). Medido em 25/07: o 2º DualSense perdeu o canal de
# controle L2CAP, o GET_REPORT expirou no BlueZ (REPORT_REQ_TIMEOUT = 3 s), o
# uhid achatou o ETIMEDOUT em -EIO e a probe morreu — device sem hidraw, sem
# input, sem LED. Diagnóstico completo (as 3 medidas encadeadas) em
# assets/dkms/hid-playstation/README.md.
# Contrato fail-safe idêntico ao 3i/3j: nada aqui aborta o install.
step "3k" "contenção BT: hid-playstation patchado via DKMS (retry de feature report)"
install_dkms_hid_playstation_host

# ---------------------------------------------------------------------------
# 3l. Regenerar o initramfs (INITRAMFS-01) — DEFAULT, sem flag
# ---------------------------------------------------------------------------
# `dkms install` grava em updates/dkms e roda depmod, mas NÃO regenera o
# initramfs — e o initramfs carrega uma CÓPIA do hid-nintendo (é driver de
# gamepad/teclado USB, entra na geração "most" do Ubuntu/Pop). Medido em
# 25/07: initramfs de 23/07 contra DKMS de 25/07, boot subindo o módulo VELHO,
# e como os params do patch novo não existiam nele o kernel descartava o
# /etc/modprobe.d/hefesto-hid-nintendo.conf INTEIRO ("unknown parameter"),
# levando junto curas que já funcionavam. Roda UMA vez para todos os módulos.
step "3l" "INITRAMFS-01: regenerar o initramfs se algum módulo DKMS mudou"
flush_initramfs_host

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
# BUG-ICON-FROM-PLACEHOLDER-SVG-01 (v3.4.3): v3.4.2 usava um SVG que era
# PLACEHOLDER (chama laranja + texto "HEFESTO"), e a app library mostrava
# chama em vez do martelo. A cura da epoca foi eleger o PNG como fonte.
#
# NOTA DE VERIFICACAO — 01/08/2026. Este comentario CADUCOU, e por dois
# motivos medidos:
#
#   1. o SVG deixou de ser placeholder. `assets/hefesto-logo.svg` TEM o
#      martelo, a bigorna e a chama, e o `rsvg-convert` gera dele um PNG
#      indistinguivel do que estava versionado. A troca aconteceu em algum
#      momento e ninguem atualizou este texto — que passou a mentir com
#      autoridade;
#   2. o ICON_SRC apontava para `assets/appimage/Hefesto-Dualsense4Unix.png`,
#      que NAO EXISTIA nesta arvore. O `cp -f` falhava em silencio e o icone
#      que aparecia no sistema vinha, por acidente, do PNG do applet COSMIC.
#      Havia dois caminhos, e o documentado era o quebrado.
#
# Agora ha UMA fonte: `assets/hefesto-logo.svg`. Os PNGs derivados sao
# gerados por `scripts/gerar_icones.sh` e travados por
# `tests/unit/test_icones_refletem_o_svg.py` — mexer no desenho sem regerar
# reprova. O install continua consumindo o PNG (o Lanczos do ImageMagick da
# downsample melhor que o rsvg em tamanhos pequenos), mas o PNG deixou de
# ser fonte: virou derivado.
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
    #
    # ATENÇÃO, 07/08/2026 (APPLET-MONOCROMÁTICO-01): esta linha apaga
    # `scalable/apps/${APP_ID}.svg` — o nome SEM sufixo, e SÓ ele. Ela NÃO
    # alcança o simbólico instalado logo abaixo, que se chama
    # `${APP_ID}-symbolic.svg` e vive em `symbolic/apps/`. O alvo está cravado
    # de propósito: um `rm -f .../scalable/apps/${APP_ID}*.svg` apagaria o
    # simbólico a cada instalação, e o sintoma seria um joystick genérico na
    # barra dela, sem ninguém entender por quê.
    rm -f "${ICON_HICOLOR_BASE}/scalable/apps/${APP_ID}.svg"
else
    printf '      aviso: ImageMagick (convert) ausente — so 256x256 PNG\n'
    printf '             instale: sudo apt install imagemagick\n'
fi

# ICONE SIMBOLICO DA BANDEJA — APPLET-MONOCROMATICO-01 (07/08/2026)
# ------------------------------------------------------------------
# Pedido dela, olhando a própria barra: "o applet do hefesto deve ficar em preto
# e branco (...) no cosmic todos os applet são assim". Estava certa: dez dos
# treze applets do System76 declaram `-symbolic`, e o Hefesto era o único de
# glifo fixo que não declarava.
#
# Este arquivo NÃO é derivado dos PNGs acima, e não passa pelo ImageMagick: é
# desenho próprio na grade 16x16 (a logo cheia a 20 px vira borrão). Por isso
# fica FORA do `if command -v convert` — sem ImageMagick o resto degrada, este
# não precisa degradar junto.
#
# O destino é `symbolic/apps/`, e isso foi MEDIDO em 07/08 na máquina dela: o
# `index.theme` do `hicolor` do HOME dela NÃO lista `symbolic/apps`, e mesmo
# assim a busca de ícones acha o arquivo lá (GTK) — e o painel desenhou um item
# de bandeja de prova servido desse diretório. É onde o `hicolor` do sistema
# declara o bloco `[symbolic/apps]` e onde o vizinho que já funciona (Flatpak do
# Spotify) põe o dele.
#
# Sem este arquivo, `tray.py` cai para o nome antigo (logo colorida) e, se nem
# ele existir, para o joystick genérico `input-gaming`.
ICON_SIMBOLICO_SRC="${ROOT_DIR}/assets/simbolico/hefesto-dualsense4unix-symbolic.svg"
ICON_SIMBOLICO_DIR="${ICON_HICOLOR_BASE}/symbolic/apps"
if [[ -r "${ICON_SIMBOLICO_SRC}" ]]; then
    mkdir -p "${ICON_SIMBOLICO_DIR}"
    cp -f "${ICON_SIMBOLICO_SRC}" "${ICON_SIMBOLICO_DIR}/${APP_ID}-symbolic.svg"
    printf '      ícone simbólico da bandeja instalado (%s-symbolic.svg)\n' "${APP_ID}"
else
    printf '      aviso: %s ausente — a bandeja cai no ícone colorido\n' \
        "assets/simbolico/hefesto-dualsense4unix-symbolic.svg"
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
Comment=Gerenciador DualSense para Linux
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
# 4e. Fontes da identidade visual (Space Grotesk + JetBrains Mono)
# ---------------------------------------------------------------------------
# FONTE-PADRAO-01, item 3. O `scripts/install_fonts.sh` existia, com download
# pinado e SHA-256, e NINGUÉM o chamava: `grep -c fonts install.sh` dava 0. O
# `gui/theme.css` pede "Space Grotesk" na interface e "JetBrains Mono" nos
# valores/logs, e numa máquina limpa nenhuma das duas existe — o fontconfig
# substitui EM SILÊNCIO e a interface nunca é a do design.
#
# Fica junto do passo 4 (atalho, glyphs, i18n) porque é a mesma natureza:
# acabamento da GUI, no HOME da usuária, sem sudo obrigatório.
#
# BEST-EFFORT, no molde dos outros passos opcionais: o `if` impede o `set -e` de
# abortar e o próprio script sai 0 mesmo quando não consegue instalar. Fonte é
# acabamento, não requisito — fazer a instalação inteira falhar por causa disso
# trocaria um problema cosmético por um problema real. `--yes` só quando ela já
# disse sim a tudo; nunca forçamos `--no-download` aqui (o download é pinado num
# commit e conferido por SHA-256, e é o único caminho em distro sem o pacote).
if [[ "${NO_FONTS}" -eq 1 ]]; then
    printf '      fontes: pulado (--no-fonts) — a interface usa o fallback do CSS\n'
elif [[ ! -r "${ROOT_DIR}/scripts/install_fonts.sh" ]]; then
    warn "scripts/install_fonts.sh ausente — fontes da identidade visual puladas"
else
    # `--yes` só quando ela já disse sim a tudo. Sem array vazio de propósito:
    # `"${arr[@]}"` vazio sob `set -u` quebra em bash < 4.4, e este script roda
    # em máquina de quem instala, não só na desta casa.
    if [[ "${AUTO_YES}" -eq 1 ]]; then
        bash "${ROOT_DIR}/scripts/install_fonts.sh" --yes \
            || printf '      fontes: incompletas — rode: bash scripts/install_fonts.sh\n'
    else
        bash "${ROOT_DIR}/scripts/install_fonts.sh" \
            || printf '      fontes: incompletas — rode: bash scripts/install_fonts.sh\n'
    fi
fi

# ---------------------------------------------------------------------------
# 4f. Teclado na tela — o que o L3 do controle abre (TECLADO-QUE-NAO-DIGITA-01)
# ---------------------------------------------------------------------------
# O mapa de fábrica dá ao L3 o token `__OPEN_OSK__` desde sempre, e o daemon o
# cumpre abrindo um teclado na tela DO SISTEMA. Só que ninguém instalava esse
# teclado: medido em 09/08/2026 na máquina dela, `command -v onboard
# wvkbd-mobintl` não achava nenhum dos dois e `grep -c onboard install.sh` dava
# ZERO. Como nenhum dos nove atalhos de fábrica digita uma LETRA (Super,
# PrintScreen, Alt+Tab, Alt+Shift+Tab, Enter, Delete, Backspace e os dois
# tokens de OSK), sem o teclado na tela a frase "o teclado emulado não digita"
# era literalmente verdade.
#
# Fica ao lado das fontes porque é a mesma natureza: acabamento que o produto
# PROMETE, que vem de pacote da distribuição, best-effort, sem derrubar o
# install. A escolha do pacote (wvkbd em Wayland, onboard em X11) e o porquê
# MEDIDO moram num dono só — scripts/install_osk.sh —, para o instalador, o
# doctor e o daemon nunca divergirem sobre qual binário é o certo.
step "4f" "teclado na tela do L3 (wvkbd em Wayland, onboard em X11)"
install_osk_host

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
# 6. Daemon systemd --user (copia sempre; auto-start segue a resposta dela)
# ---------------------------------------------------------------------------
step "6/11" "daemon systemd --user"

# BUG-INSTALL-ATROPELA-O-NAO-DO-AUTOSTART-01 (29/07): esta variável nasce AQUI,
# fora do `if`, porque o passo 7a mais abaixo TAMBÉM a lê — ele escreve o mesmo
# ~/.config/systemd/user/hefesto-dualsense4unix.service e antes fazia enable +
# restart sem olhar nem a flag nem a resposta. Sob `set -u` uma variável só
# definida dentro do ramo `else` mataria o install quando --no-systemd fosse
# usado, então o default explícito (0) fica antes de qualquer ramo.
enable_daemon=0

if [[ "${SKIP_SYSTEMD}" -eq 1 ]]; then
    printf '      pulado (--no-systemd)\n'
else
    # Decide se habilita auto-start ANTES de chamar o CLI.
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
        # BUG-INSTALL-READONLY-USER-UNIT-DIR-01 (25/07): este nome NÃO pode ser
        # `readonly`. O passo 11 (guard do Steam Input) reatribui a MESMA variável
        # mais abaixo, e sob `set -euo pipefail` uma atribuição a variável somente
        # leitura devolve rc=1 e MATA o install. Efeito medido: com o hotplug-gui
        # habilitado (--enable-hotplug-gui ou "sim" no prompt), o install abortava
        # em silêncio no passo 11 — sem o guard do Steam Input, sem a migração das
        # Launch Options (11b), sem o pino do Proton (11c) e sem sequer imprimir o
        # banner final. Nome genérico e compartilhado entre passos: assignment comum.
        USER_UNIT_DIR="${HOME}/.config/systemd/user"
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
# 7a-bis. A UNIT DO DAEMON PRINCIPAL.
#     BUG-INSTALL-NAO-INSTALA-A-UNIT-DO-DAEMON-01 (25/07): assimetria de
#     primeira grandeza. O `uninstall.sh` para, desabilita e REMOVE
#     ~/.config/systemd/user/hefesto-dualsense4unix.service (uninstall.sh:284-288),
#     e o install NUNCA a instalava — `grep -c assets/hefesto-dualsense4unix.service
#     install.sh` dava ZERO. A unit só existia nas máquinas onde tinha
#     sobrevivido de uma instalação antiga; quem fizesse o ciclo completo
#     (uninstall -> install) ficava SEM daemon, e portanto sem vpad, sem
#     gatilhos, sem lightbar — com o install anunciando sucesso.
#     Aqui a simetria é fechada: copia, habilita e SOBE (`--now`), como já se
#     fazia para o kernel-watch e para o guard do Steam Input. Sem `--now` o
#     daemon só nasceria no próximo login, e a instalação "bem-sucedida" não
#     entregaria nada até lá.
#
#     BUG-INSTALL-ATROPELA-O-NAO-DO-AUTOSTART-01 (29/07): fechar a assimetria
#     abriu o bug OPOSTO. Este passo escreve o MESMO arquivo do passo 6
#     (~/.config/systemd/user/hefesto-dualsense4unix.service) e fazia `enable` +
#     `restart` sem gate nenhum: nem --no-systemd, nem a resposta ao prompt do
#     passo 6. Resultado medido: quem passava --no-systemd via o passo 6 dizer
#     "pulado" e o 7a instalar e habilitar a unit três linhas depois; quem
#     respondia "não" a "habilitar auto-start do daemon no boot?" via o passo 6
#     dizer "auto-start desativado" e o 7a habilitar mesmo assim. O "não" dela
#     era atropelado. Agora o passo 7a obedece aos dois:
#       - --no-systemd  -> não copia, não habilita, não sobe (igual ao passo 6);
#       - resposta "não" -> copia a unit (simetria com o uninstall preservada) e
#         NÃO habilita nem sobe; um daemon que JÁ estivesse no ar só é
#         reiniciado para não ficar rodando o binário antigo — nunca iniciado.
#     O default SEM FLAGS continua o de sempre: copia, habilita e sobe.
# ---------------------------------------------------------------------------
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
else
    mkdir -p "${DAEMON_USER_UNIT_DIR}"
    cp -f "${DAEMON_UNIT_SRC}" "${DAEMON_UNIT_TARGET}"
    systemctl --user daemon-reload >/dev/null 2>&1 || true
    if [[ "${enable_daemon}" -eq 1 ]]; then
        # `restart` e não `start`: numa reinstalação por cima, o daemon em memória
        # é o binário ANTIGO — sem isso a pessoa roda o install, vê "sucesso" e
        # segue usando o código anterior até relogar.
        if systemctl --user enable "${DAEMON_UNIT_NAME}" >/dev/null 2>&1 \
           && systemctl --user restart "${DAEMON_UNIT_NAME}" >/dev/null 2>&1; then
            printf '      daemon habilitado e no ar\n'
        else
            warn "enable/restart do daemon falhou — suba com: systemctl --user enable --now hefesto-dualsense4unix.service"
        fi
    else
        # Ela respondeu "não" ao passo 6: nada de enable, nada de start. Só o
        # daemon que JÁ estava no ar é reiniciado (senão a reinstalação deixaria
        # o binário antigo rodando) — e isso não inicia nada que estivesse
        # parado nem habilita o auto-start.
        if systemctl --user is-active --quiet "${DAEMON_UNIT_NAME}"; then
            systemctl --user restart "${DAEMON_UNIT_NAME}" >/dev/null 2>&1 \
                || warn "restart do daemon já em execução falhou"
            printf '      unit atualizada; auto-start NÃO habilitado (respeitando a resposta do passo 6)\n'
        else
            printf '      unit copiada; auto-start NÃO habilitado (respeitando a resposta do passo 6) — suba quando quiser: systemctl --user start hefesto-dualsense4unix.service\n'
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
    # INSTALL-APPLET-HEADLESS-01: o `just install` usa {{sudo}} p/ copiar os
    # arquivos como root. Interativo, "sudo" puro prompta no TTY; HEADLESS (sem
    # TTY, SUDO_ASKPASS setado) o "sudo" puro FALHA — passamos "sudo -A" p/ o
    # just usar o askpass (o `sudo -n` não herda o ticket sem TTY nesta máquina).
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
# SOM-QUE-NAO-DORME-01 (16/08/2026) — SEM FLAG, e num passo PRÓPRIO, antes do
# 10/11 (que decide o microfone).
#
# A decisão dela, textual: *"garantir que sempre fique acordado"*. O defeito foi
# medido na orelha dela em 15/08 23h45 (ensaio `sfx-no-suspenso-come-o-comeco`):
# o WirePlumber suspende o sink do controle depois de 5 s ociosos, e o religar do
# hardware COME O COMEÇO DO SOM.
#
# Por que passo próprio, e não uma linha dentro do 10/11: os três ramos de lá
# decidem o MICROFONE. Quem pediu `--keep-dualsense-mic` pediu para não
# rebaixarem a entrada dele — não pediu para perder o começo de cada efeito
# sonoro. São perguntas diferentes, e amarrar uma na outra deixaria a cura
# opt-in por acidente de posição (foi o que MIC-EM-TODO-FORMATO-01 pagou em
# 10/08). Separado também mantém o bloco do 10/11 do tamanho que o portão
# `test_o_instalador_que_aprovou_o_monitor` lê.
step "som" "áudio: o alto-falante do controle nunca dorme (SOM-QUE-NAO-DORME-01)"
if bash "${ROOT_DIR}/scripts/fix_wireplumber_default_source.sh" --nunca-dorme; then
    : # a mensagem do próprio script já diz se instalou ou se já valia
else
    warn "nunca-dorme falhou — rode: bash scripts/fix_wireplumber_default_source.sh --nunca-dorme"
fi

step "10/11" "audio: impedir o DualSense de virar o microfone padrão"
if [[ "${WITH_WIREPLUMBER_DISABLE_MIC}" -eq 1 ]]; then
    [[ "${WITH_WIREPLUMBER_FIX}" -eq 1 ]] && warn "--with-wireplumber-disable-mic vence --with-wireplumber-fix"
    # exit 2 (DualSense é a única fonte) não é falha de instalação — só aviso.
    # exit 3 (a fonte padrão é um MONITOR) não fala do DualSense: quem dá esse
    # veredito é a conferência do fim deste passo, depois da cura do microfone.
    if bash "${ROOT_DIR}/scripts/fix_wireplumber_default_source.sh" --disable-source; rc=$?; [[ "${rc:-0}" -ne 1 ]]; then
        printf '      mic do DualSense DESABILITADO (node.disabled; controle só-HID)\n'
    else
        warn "disable-source falhou — rode: bash scripts/fix_wireplumber_default_source.sh --disable-source"
    fi
elif [[ "${WITH_WIREPLUMBER_FIX}" -eq 1 ]]; then
    if bash "${ROOT_DIR}/scripts/fix_wireplumber_default_source.sh" --install; rc=$?; [[ "${rc:-0}" -ne 1 ]]; then
        # INSTALADOR-QUE-APROVOU-O-MONITOR-01: o drop-in ter entrado NÃO é o
        # microfone estar certo, e dizer "fonte padrão reeleita" quando ela não
        # foi era a metade da contradição que ela leu na tela. rc 3 = monitor.
        if [[ "${rc:-0}" -eq 3 ]]; then
            printf '      drop-in do WirePlumber instalado (a fonte padrão ainda não é um microfone)\n'
        else
            printf '      drop-in do WirePlumber instalado + fonte padrão reeleita\n'
        fi
    else
        warn "fix do WirePlumber falhou — rode: bash scripts/fix_wireplumber_default_source.sh --install"
    fi
else
    printf '      pulado (--keep-dualsense-mic): o DualSense pode virar o microfone padrão\n'
fi

# MIC-USB-01, entrega 7 — a cura das camadas 1 e 2 do microfone mudo, que
# existia em `scripts/doctor.sh --fix-mic` e que NINGUÉM chamava. Medido em
# 25/07: depois de um uninstall + install completos o perfil da placa voltou
# sozinho para a entrada digital (`input:iec958-stereo`, que é S/PDIF e não
# carrega sinal), e uma instalação limpa entregava o microfone mudo com a cura
# pronta no repositório.
#
# As duas ações deste passo são complementares e não conflitam: o drop-in acima
# decide QUEM é o microfone padrão do sistema; a cura abaixo garante que o
# microfone FUNCIONA quando escolhido (perfil da placa na entrada analógica e
# nenhum mute persistido por rota de captura).
#
# Não roda com `--with-wireplumber-disable-mic`: ali a source foi desabilitada
# DE PROPÓSITO, e ressuscitá-la desfaria a escolha da usuária no mesmo passo.
#
# Best-effort, como o resto do instalador: o `if` impede o `set -e` de abortar,
# e `--quiet` mantém a cura silenciosa quando não há DualSense presente na hora
# da instalação (sem controle o doctor só emite linhas informativas). FAIL e
# WARN continuam saindo — o silêncio é do sucesso, não do problema.
if [[ "${WITH_WIREPLUMBER_DISABLE_MIC}" -ne 1 ]]; then
    if [[ ! -r "${ROOT_DIR}/scripts/doctor.sh" ]]; then
        warn "scripts/doctor.sh ausente — cura do microfone pulada"
    elif bash "${ROOT_DIR}/scripts/doctor.sh" --fix-mic --quiet; then
        printf '      microfone: camadas 1 e 2 conferidas (doctor.sh --fix-mic)\n'
    else
        printf '      microfone: cura incompleta — rode: bash scripts/doctor.sh --fix-mic\n'
    fi
fi

# INSTALADOR-QUE-APROVOU-O-MONITOR-01 (09/08/2026) — a CONFERÊNCIA FINAL do
# microfone, e o motivo de ela existir.
#
# MEDIDO na máquina dela, no mesmo terminal, com dois minutos de diferença:
#
#   passo 10/11:  OK: microfone padrão ativo = alsa_output…iec958-stereo.monitor
#   doctor.sh:    [FAIL] a fonte de captura padrão é um MONITOR — o que qualquer
#                 app gravar é o áudio de SAÍDA do sistema, não a voz
#
# O install declarava sucesso sobre um estado que o próprio produto reprova. A
# verificação do `--install` do wp-fix já parou de aprovar monitor (exit 3), mas
# ela roda ANTES da cura (`--fix-mic`), então o veredito dela é sempre parcial:
# quem tem a última palavra é esta leitura, DEPOIS de tudo o que o passo tenta.
#
# Não oferece comando: RECEITA-ERRADA-01 mostrou o preço de mandar rodar algo que
# não pode funcionar. Quando não há microfone nenhum na máquina, o que resolve é
# hardware — e é isso que a linha diz.
if command -v pactl >/dev/null 2>&1; then
    _fonte_agora="$(pactl get-default-source 2>/dev/null || true)"
    case "${_fonte_agora}" in
        *.monitor|*.Monitor)
            warn "o microfone padrão do sistema é um MONITOR (${_fonte_agora})"
            printf '      isto NÃO é microfone: o que Discord, chat de jogo ou gravador\n'
            printf '      captarem é o áudio que SAI do PC, não a voz de quem fala — e o\n'
            printf '      medidor de nível mostra sinal, então parece estar funcionando.\n'
            printf '      Não há comando que resolva sem uma entrada de verdade: conecte o\n'
            printf '      DualSense (no cabo), um microfone/headset no jack, ou uma webcam\n'
            printf '      com microfone. A janela do Hefesto avisa enquanto durar.\n'
            ;;
        "")
            printf '      microfone: nenhuma fonte padrão eleita (PipeWire parado?)\n'
            ;;
        *)
            printf '      microfone padrão do sistema: %s (entrada de verdade)\n' "${_fonte_agora}"
            ;;
    esac
    unset _fonte_agora
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
# 11b-bis. Launch Options: APLICAR o wrapper a TODOS os jogos — DEFAULT, sem flag
# ---------------------------------------------------------------------------
# JOGO-COMPLETO-01 entrega E4, pedido literal dela: "isso deveria estar no
# install sem flag". O passo 11b só MIGRA veneno legado — numa instalação
# limpa não existe veneno, então ele não põe nada e NENHUM jogo fica com o
# wrapper. Medido em 02/08 nesta máquina: `--status` dizia "veneno estático: 0
# / chamadas do wrapper: 0" e o doctor avisava "NENHUM jogo com o wrapper".
# Sem a chamada do wrapper, as envs que o projeto materializa
# (SDL_GAMECONTROLLER_IGNORE_DEVICES, PROTON_DISABLE_HIDRAW) nunca são
# exportadas e todo jogo enxerga DOIS DualSense — o defeito do controle
# duplicado voltando pela porta dos fundos.
#
# Idempotente por construção (requisito dela): jogo que já chama o wrapper é
# PULADO, nada é duplicado, e um vdf sem nada a fazer não é sequer reescrito —
# rodar o install N vezes é igual a rodar uma. Steam Flatpak/Snap é pulada
# inteira (o wrapper do host é invisível dentro da sandbox, DEDUP-04).
#
# ORDEM — armadilha 1 da sprint, "não ligar o broker antes do wrapper": o
# broker hide-hidraw é instalado lá atrás, no passo 3h, e este passo vem só
# aqui. É seguro, e o motivo é que o 3h NÃO esconde nada: ele instala o
# binário e habilita o .socket; o .service só sobe na primeira conexão do
# daemon e o hide do hidraw FÍSICO acontece em tempo de JOGO, com vpad vivo
# confirmado (`coop._broker_hide_player`). Entre o 3h e este passo nenhum nó é
# escondido — e este passo RECUSA rodar com um jogo aberto (rc=3, nada é
# tocado), de modo que o primeiro jogo a subir depois do install já encontra o
# wrapper posto. A rede de segurança nunca fica no ar sozinha.
#
# Falha aqui é best-effort, como nos vizinhos: o wrapper degrada por desenho
# (`[ -x "$W" ] && exec "$W" "$@"; exec env "$@"`), logo o pior caso continua
# sendo o controle duplicado de hoje — nunca um jogo que não abre.
step "11b-bis" "Steam: aplicar o wrapper hefesto-launch a todos os jogos"
if [[ -f "${LAUNCH_MIGRATE_PY}" ]] && command -v python3 >/dev/null 2>&1; then
    printf '      sem isto, as opções de inicialização ficam vazias e o jogo\n'
    printf '      enxerga dois DualSense (jogos que já têm o wrapper são pulados).\n'
    if python3 "${LAUNCH_MIGRATE_PY}" --apply --stop-steam; then
        printf '      wrapper hefesto-launch nas Launch Options de todos os jogos\n'
    else
        warn "aplicação do wrapper adiada — rode com a Steam fechada (e sem jogo aberto): python3 ${LAUNCH_MIGRATE_PY} --apply"
    fi
else
    warn "steam_launch_options.py ausente ou sem python3 — wrapper NÃO aplicado; rode depois: python3 ${LAUNCH_MIGRATE_PY} --apply"
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
# Conferência final: o doctor
# ---------------------------------------------------------------------------
# CONFERENCIA-FINAL-01, 04/08/2026 — pedido dela, e nascido de um defeito real:
#
#   *"nosso install não deveria rodar o doctor por default sem flag? pra
#   garantir tudo tudo real mesmo?"*
#
# Na noite de 03→04/08 a máquina dela estava SEM o drop-in
# `51-hefesto-dualsense-no-default-source.conf`. Sem ele o WirePlumber promoveu
# o DualSense a microfone padrão do sistema, o mic ficou mudo por estado
# persistido por rota, e o alto-falante do controle ficou MUTED — os três
# sintomas que ela reportou como "não funciona nem mic, nem os botões de som".
#
# O install TINHA o passo que arma o drop-in (passo 10) e o uninstall TEM a
# linha que o remove. O que não havia era alguém CONFERINDO no fim: uma
# instalação podia terminar imprimindo "instalado" com cura desarmada, e o
# único jeito de descobrir era ela sentir o defeito jogando.
#
# Por que CONFERIR e não `--fix`: os passos acima já são as curas, e cada um
# reporta o que fez. Este passo existe para dizer a VERDADE sobre o resultado
# — se ele precisasse curar, o defeito seria do passo, e escondê-lo com um
# `--fix` no fim tiraria justamente o sinal que aponta para o passo furado.
#
# Por que não derruba a instalação: sem controle plugado o doctor emite muitos
# avisos legítimos (nada a medir), e um `exit 1` aqui transformaria "instalei
# sem o controle na mão" em "a instalação falhou". FALHA aparece na tela, em
# destaque, com o comando para investigar — e a decisão é dela.
if [[ "${RUN_DOCTOR}" -eq 1 ]]; then
    printf '\n'
    printf '─────────────────────────────────────────\n'
    printf ' Conferência final (doctor)\n'
    printf '─────────────────────────────────────────\n'
    if [[ ! -r "${ROOT_DIR}/scripts/doctor.sh" ]]; then
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
            printf '      nenhuma FALHA — as curas desta casa estão armadas\n'
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
