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
#   --dry-run, -n         ENSAIO. Imprime CADA mudança que este script faria —
#                         arquivo por arquivo, unit por unit, pacote por pacote —
#                         e NÃO ESCREVE NADA: nenhum arquivo copiado, nenhum
#                         pacote instalado, nenhum serviço reiniciado, nenhum
#                         módulo DKMS compilado, nenhum `localconfig.vdf` da
#                         Steam tocado. Nem sequer pergunta a senha do sudo.
#                         Existe porque este arquivo mexe em udev, DKMS,
#                         systemd, no cmdline do kernel e nos arquivos da Steam
#                         de quem instala, e ninguém tinha como VER antes.
#                         O ensaio respeita todas as outras flags: o plano que
#                         ele imprime é o plano DAQUELA linha de comando, nesta
#                         máquina, agora.
#                         SEM CREDENCIAL SUDO EM CACHE os passos de root
#                         aparecem como "PULARIA (sudo)", porque é isso que
#                         aconteceria de verdade. Para ver o plano inteiro:
#                             sudo -v && ./install.sh --dry-run
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
# ENSAIO-DO-INSTALL-01 (03/09/2026). Pedido dela ao rever o instalador antes de
# rodá-lo: *"antes revisa o install. não roda agora."* São 3.4 mil linhas que
# mexem em udev, DKMS, systemd, no cmdline do kernel e nos arquivos da Steam
# DELA, e até hoje não havia forma de ver o que fariam sem deixá-las fazer.
# `--dry-run` é essa forma: imprime o plano e não escreve nada.
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
        --dry-run|-n)         DRY_RUN=1 ;;
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

# ---------------------------------------------------------------------------
# ENSAIO-DO-INSTALL-01 — as três palavras do `--dry-run`
# ---------------------------------------------------------------------------
# A CONDIÇÃO É SEMPRE ESCRITA À MÃO nos passos, como
# `[[ "${DRY_RUN:-0}" -eq 1 ]]`, e nunca como uma função `_ensaio`. A razão é
# medida, não estética: dezenas de testes desta casa EXTRAEM um bloco deste
# arquivo (do `step "N/11"` até a régua seguinte) e o EXECUTAM num bash com
# preâmbulo mínimo — só `step`, `warn` e duas ou três variáveis. Um `_ensaio`
# no meio do bloco viraria "command not found" ali dentro; o `${DRY_RUN:-0}`
# resolve para 0 num shell que nunca ouviu falar da flag, o `else` roda o
# código de sempre, e a régua continua medindo o que sempre mediu.
#
# Pela mesma razão as três funções abaixo SÓ são chamadas dentro do ramo do
# ensaio: num bloco extraído elas nunca são alcançadas.
_ENSAIO_MUDANCAS=0
_ENSAIO_ROOT=0

# Uma mudança que o install faria no HOME/na sessão de quem instala.
_faria() {
    _ENSAIO_MUDANCAS=$((_ENSAIO_MUDANCAS + 1))
    printf '      FARIA        %s\n' "$*"
}

# Uma mudança que exige root — a que mais importa ver antes.
_faria_root() {
    _ENSAIO_MUDANCAS=$((_ENSAIO_MUDANCAS + 1))
    _ENSAIO_ROOT=$((_ENSAIO_ROOT + 1))
    printf '      FARIA (root) %s\n' "$*"
}

# O que o ensaio NÃO faria, e por quê — um passo pulado é informação tanto
# quanto um passo aplicado (foi a lição do 3d sem `else`, em 06/08/2026).
_nao_faria() { printf '      não faria:   %s\n' "$*"; }

# O fecho do ensaio. Repete a promessa no FIM, e não só no começo: quem rola
# quarenta passos de tela não se lembra do cabeçalho, e a pergunta que fica é
# "isto já mexeu na minha máquina?".
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
    # ask_yn "pergunta" auto_yes_var [default=y] → seta $REPLY como "y" ou "n"
    local prompt="$1" auto="$2" default="${3:-y}"
    # No ensaio nada é perguntado: uma pergunta é um passo que ESPERA, e quem
    # roda `--dry-run` quer o plano, não uma conversa. Assumimos o mesmo default
    # que o `--yes` assumiria e DIZEMOS o que assumimos — senão o plano seria o
    # de uma resposta que ela não deu, sem nada na tela indicando isso.
    if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
        REPLY="$default"
        printf '      perguntaria: "%s" — no ensaio assumo "%s"\n' "${prompt}" "${default}"
        return
    fi
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

# ---------------------------------------------------------------------------
# DEPS-UNIVERSAIS-01 (19/08/2026) — o install deixa de ser só-apt.
#
# O pedido dela, literal: *"corrige nosso install pra instalar isso tudo aí"* e,
# a frase que manda no desenho, *"qualquer install. inclusive o do andre ou de
# qualquer outro user"*. Ou seja: a cura não é para a bancada dela.
#
# O que havia antes: `run_apt` era a ÚNICA porta, e o `_reconhecimento()` dizia
# por escrito que fora da família Debian o instalador nativo não garante nada.
# Numa máquina limpa de Fedora ou de Arch o install terminava "ok" com a
# libhidapi ausente — o verde mentiroso que `install.sh` já nomeia no bloco DKMS.
#
# O desenho, em três peças, e o molde é da própria casa
# (`scripts/install_osk.sh:206-220`, que já despacha por família):
#
#   _familia_pacotes()  descobre a família (apt/dnf/pacman/nenhum);
#   _pkg_nome()         UMA tabela: nome canônico -> nome em cada família;
#   run_pkg()           instala nomes canônicos na família corrente.
#
# `run_apt` CONTINUA existindo, e virou o braço apt do `run_pkg` — não uma
# fachada morta. Razão: é ele que guarda a disciplina de saída quieta (só fala
# se falhar), ele é citado por teste e por documento desta casa, e duplicar
# essa disciplina no `run_pkg` seria dois lugares para consertar quando ela
# mudar. Quem chama `run_apt` direto passa nome de pacote APT — hoje ninguém,
# só o `run_pkg`.
#
# De onde vêm os nomes: dos empacotamentos que esta casa já publica
# (`packaging/debian/control`, `packaging/fedora/*.spec`, `packaging/arch/PKGBUILD`)
# e da matriz `smoke-multi-distro` do CI (`.github/workflows/ci.yml:796-811`),
# que já declara os nomes de runtime de Fedora 40, Arch e Debian 12. Não são
# palpite: cada nome tem empacotamento ou contêiner de CI por trás.
#
# NOTA DATADA — 19/08/2026: o **openSUSE SAIU**, e a coluna `zypper` com ele.
# A leva da manhã tinha acrescentado a família com nomes de pacote INFERIDOS em
# 100% das linhas — o repositório não tem uma linha sequer sobre zypper — e sem
# nenhum smoke que os conferisse. Prometer openSUSE assim é afirmação forte sem
# teste que a sustente, e esta casa tem portão contra isso. É decisão dela,
# tomada no mesmo dia, e fica registrada em vez de sair calada.
#
# Quem está no openSUSE cai no caminho de "família sem tratamento", que já
# existe e já é honesto: o install DIZ o que falta, com o nome no Debian/Ubuntu
# como referência, e SEGUE sem instalar nada — não aborta.
#
# O QUE O TRAZ DE VOLTA: um contêiner openSUSE na matriz `smoke-multi-distro`
# do CI (`.github/workflows/ci.yml`), conferindo os nomes de pacote de verdade
# numa máquina limpa. Com esse smoke verde, a coluna volta — medida, e não
# inferida.
_OS_RELEASE="${HEFESTO_OS_RELEASE:-/etc/os-release}"

# Família do gerenciador de pacotes. `/etc/os-release` primeiro (é a fonte
# padrão e sobrevive a máquinas com dois gerenciadores instalados); o PATH só
# decide quando o os-release não conclui. `HEFESTO_FAMILIA_PACOTES` é o gancho
# de teste, no mesmo espírito do `HEFESTO_OSK_GERENCIADOR`.
_familia_pacotes() {
    if [[ -n "${HEFESTO_FAMILIA_PACOTES:-}" ]]; then
        printf '%s\n' "${HEFESTO_FAMILIA_PACOTES}"
        return 0
    fi
    local _id="" _id_like="" _token
    if [[ -r "${_OS_RELEASE}" ]]; then
        _id="$(sed -n 's/^ID=//p' "${_OS_RELEASE}" | tr -d '"' | head -1)"
        _id_like="$(sed -n 's/^ID_LIKE=//p' "${_OS_RELEASE}" | tr -d '"' | head -1)"
    fi
    # shellcheck disable=SC2086  # a quebra em palavras do ID_LIKE é o objetivo
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

# A TABELA. Nome canônico -> nome real em cada família. Vazio quer dizer "esta
# família não tem esse pacote com nome que eu saiba" — e aí o `run_pkg` diz
# isso em voz alta em vez de instalar a coisa errada.
_pkg_nome() {
    local _canon="$1" _familia="${2:-}"
    [[ -z "${_familia}" ]] && _familia="$(_familia_pacotes)"
    local _apt="" _dnf="" _pacman=""
    case "${_canon}" in
        # --- OBRIGATÓRIAS -------------------------------------------------
        # A biblioteca que o backend do controle abre por dlopen. A wheel
        # `hidapi` do pip é wrapper CFFI e NÃO traz o .so: sem o pacote do
        # sistema, `import hidapi` levanta OSError e nenhum aparelho sobe.
        hidapi)
            _apt="libhidapi-hidraw0"; _dnf="hidapi"
            _pacman="hidapi" ;;
        # O loader SVG do gdk-pixbuf. ARMADILHA DE NOME: `librsvg2-bin` é o
        # `rsvg-convert`, ferramenta de BUILD; quem desenha na tela é o
        # `librsvg2-common`. Sem ele o ícone da bandeja some e todo glifo SVG
        # da interface cai junto (BUG-TRAY-ICONE-INVISIVEL-01, app/arranque.py).
        svg-loader)
            _apt="librsvg2-common";   _dnf="librsvg2"
            _pacman="librsvg" ;;
        # O módulo venv. Só o Debian o separa do interpretador; nas outras
        # famílias ele vem no pacote do próprio Python (listado para que a
        # mensagem de erro nunca fique sem nome de pacote).
        python-venv)
            _apt="python3-venv";      _dnf="python3-libs"
            _pacman="python" ;;
        # Compilar o que não tem wheel: python-uinput e evdev sempre saem do
        # sdist (BUG-CI-SMOKE-EVDEV-NO-GCC-01). Precisa de compilador,
        # `Python.h` e `linux/input.h`.
        toolchain-c)
            _apt="build-essential python3-dev linux-libc-dev"
            _dnf="gcc python3-devel kernel-headers"
            _pacman="gcc linux-api-headers" ;;
        # --- GUI ----------------------------------------------------------
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
        # O motor web da ROTA-WEBKIT: o mockup HTML dentro de um `Gtk.Window`
        # do produto. A série **4.1 é a de GTK 3** — a 6.0 é GTK 4 e não entra
        # no processo, que é GTK 3.0. Nomes MEDIDOS um a um em 29/08/2026, e
        # nenhum inferido: `gir1.2-webkit2-4.1` 2.52.3 nesta bancada; no Fedora
        # 43 o `webkit2gtk4.1` 2.52.5 TRAZ o typelib (o Fedora não separa o
        # gir, como já acontece com o `gtk3`); no Arch o `webkit2gtk-4.1`
        # 2.52.6 idem — os dois conferidos na LISTA DE ARQUIVOS do pacote. E
        # existem nas imagens do CI: o Debian 12 (o gate duro do
        # `install-multi-distro`) tem o `gir1.2-webkit2-4.1`, e o Fedora 40, o
        # `webkit2gtk4.1-2.44.0-2.fc40`.
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
        # --- ÁUDIO / RÁDIO / DIAGNÓSTICO ----------------------------------
        opus)
            _apt="libopus0";          _dnf="opus"
            _pacman="opus" ;;
        pactl)
            _apt="pulseaudio-utils";  _dnf="pulseaudio-utils"
            _pacman="libpulse" ;;
        bluez)
            _apt="bluez";             _dnf="bluez"
            _pacman="bluez bluez-utils" ;;
        # `bt-agent` (ONDA-R, cura do bond meio-salvo). O Fedora não empacota
        # `bluez-tools` com esse nome — deixado VAZIO de propósito: é melhor
        # dizer "não tenho nome para isso aqui" do que instalar outra coisa.
        # Escopo dela: se a cura vale só para Debian/Arch, é promessa do
        # produto que muda de valor conforme a distro.
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
        # --- DKMS ---------------------------------------------------------
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

# Roda o instalador quieto; só mostra saída se falhar. A disciplina é a mesma
# de sempre — barulho de gerenciador de pacotes num install que ela roda dez
# vezes por dia é defeito.
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

run_apt() {
    # O braço apt do run_pkg. Recebe nome de pacote APT, não canônico.
    _run_pkg_quieto sudo apt-get install -y -qq "$@"
}

# Instala uma lista de nomes CANÔNICOS na família desta máquina.
run_pkg() {
    local _familia _canon _nome _parte
    local _nomes=()
    _familia="$(_familia_pacotes)"
    for _canon in "$@"; do
        _nome="$(_pkg_nome "${_canon}" "${_familia}")"
        if [[ -z "${_nome}" ]]; then
            warn "não tenho nome de pacote para '${_canon}' em ${_familia} — instale o equivalente pela sua distro"
            return 1
        fi
        # shellcheck disable=SC2086  # um canônico pode valer vários pacotes
        for _parte in ${_nome}; do _nomes+=("${_parte}"); done
    done
    (( ${#_nomes[@]} )) || return 1
    # O ensaio devolve 0 de propósito: o plano tem de mostrar o caminho em que a
    # instalação DÁ CERTO, senão cada `run_pkg` falso arrastaria o resto do
    # roteiro para o ramo de erro e o plano descreveria uma instalação que
    # ninguém vai ter.
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
        dnf)    _run_pkg_quieto sudo dnf install -y "${_nomes[@]}" ;;
        pacman) _run_pkg_quieto sudo pacman -S --noconfirm --needed "${_nomes[@]}" ;;
        *)      warn "sem gerenciador de pacotes conhecido — não instalei ${*}"; return 1 ;;
    esac
}

# O comando exato que a pessoa roda se nós não conseguirmos — impresso, nunca
# escondido (mesma regra do `install_osk.sh:comando_manual`).
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
        *)      printf 'instale pela sua distro o equivalente a: %s\n' "${_lista}" ;;
    esac
}

# O CENSO, em código. Cada linha é
#     canônico|criticidade|checagem|o que quebra sem ele
#
# CRITICIDADE, e a diferença é a mesma que já existe no arquivo entre o bloco do
# GTK (fatal) e o BT-MIC-01 (best-effort):
#   obrigatoria -> `die`. Sem ela o produto não faz o que promete: ou nenhum
#                  aparelho sobe, ou a interface não consegue desenhar.
#   importante  -> `warn` e segue. Morre UMA função; o resto vive.
#
# O que NÃO entra aqui, de propósito: tudo que é só-de-CI. `libhidapi-dev`,
# `libudev-dev` e `libxi-dev` são CABEÇALHOS (quem instala precisa da
# biblioteca, não do -dev); `librsvg2-bin` é o `rsvg-convert`, que só o
# `scripts/gerar_icones.sh` usa; `gettext` não é preciso porque os `.mo` já vêm
# COMPILADOS na árvore e o install só os copia; `appstream`, `libfuse2` e
# `dpkg` são do build. Instalar isso na máquina de quem joga seria cobrar um
# preço por nada.
_DEPS_DE_SISTEMA=(
    "hidapi|obrigatoria|lib:libhidapi-hidraw.so.0,libhidapi-libusb.so.0|o backend do controle não abre NENHUM aparelho (o pydualsense faz dlopen da libhidapi; a wheel do pip não traz o .so)"
    "svg-loader|obrigatoria|svg|o ícone da bandeja some e todo glifo SVG da interface cai junto"
    "toolchain-c|importante|toolchain|as extensões sem wheel (python-uinput, evdev) não compilam e o passo 2 pode abortar"
    "appindicator|importante|appindicator|a bandeja não nasce: a janela abre, o ícone ao lado do relógio não"
    # ROTA-WEBKIT. `importante` VIRA `obrigatoria` — a troca é desta palavra,
    # nesta linha — no dia em que ela adotar a rota: aí o mockup É a interface
    # e sem o binding não há tela nenhuma. Enquanto a decisão não é dela,
    # ninguém paga o peso obrigatório de uma rota que pode não ser escolhida:
    # medido em 29/08/2026, são 25,2 MB baixados e ~93 MB em disco no apt (o
    # gir mais a `libwebkit2gtk-4.1-0`, sem contar as transitivas), e 140 MB em
    # disco no Arch.
    "webkit2gtk|importante|webkit|a rota WebKit (o mockup HTML dentro de um Gtk.Window) não abre nesta máquina; a interface GTK 3.0 de hoje continua inteira, e é só por isso que esta linha ainda não é obrigatória"
    "desktop-utils|importante|cmd:desktop-file-validate,update-desktop-database,gtk-update-icon-cache|o atalho e o ícone podem não aparecer no menu do sistema"
    "imagemagick|importante|cmd:convert|o ícone fica só no 256x256, sem as resoluções menores"
    # LUZ-DO-MIC-01 (03/09/2026). A luz do botão de mudo deixou de espelhar o
    # mudo e passou a dizer QUEM TE ESCUTA: apagada é ninguém, acesa é um app
    # com o microfone DESTE controle aberto, piscando é som entrando agora. A
    # resposta tem duas metades, e cada uma sai de um binário:
    #     `pactl list source-outputs`  -> quem está gravando a fonte do controle
    #     `parec` com `resample.peaks` -> se está entrando som, com o pico já
    #                                     calculado PELO SERVIDOR (100 bytes/s
    #                                     por canal; 0,121% de um núcleo, e
    #                                     ~0,59% com os quatro controles da mesa)
    #
    # OS DOIS SAEM DO MESMO PACOTE, e é isso que faz esta linha não custar nome
    # novo: MEDIDO em 03/09/2026 nesta bancada, `/usr/bin/parec` é um link para
    # `/usr/bin/pacat` e o `dpkg -S` dos dois devolve `pulseaudio-utils` — o
    # mesmo pacote do `pactl`, que a tabela `_pkg_nome` já traduz nas três
    # famílias (apt/dnf `pulseaudio-utils`, pacman `libpulse`). Também não há
    # dependência PYTHON nova: o leitor do pico é `struct.unpack` da stdlib, e
    # o numpy foi recusado de propósito — ele não está no `pyproject.toml`, e
    # importá-lo repetiria a dívida do `playwright`, que faz toda árvore nova
    # nascer com portão vermelho.
    #
    # POR QUE A CHECAGEM PEDE OS DOIS NOMES, e não só o `pactl`: a luz precisa
    # dos dois binários, e se algum dia uma família separá-los é ESTA linha que
    # grita. É a mesma disciplina da linha do `bluez` logo abaixo, que ficou
    # anos cega ao `btmgmt` por pedir só o `bluetoothctl`.
    #
    # POR QUE `importante` e não `obrigatoria`: sem estes binários o Hefesto
    # inteiro continua de pé — gatilhos, perfis, vibração, emulação, rádio. O
    # que morre é UMA função, e ela morre calada: a luz simplesmente fica
    # apagada, que é um estado válido do contrato. Morrer o install por causa
    # disso cobraria o preço errado.
    "pactl|importante|cmd:pactl,parec|a luz do microfone do controle fica apagada para sempre: sem o pactl ninguém sabe QUEM está ouvindo, sem o parec ninguém sabe se está entrando som (LUZ-DO-MIC-01) — e o microfone por Bluetooth também não sobe"
    # MIGRACAO-BLUEZ-DEPRECIADOS-01 (19/08/2026): a régua pedia SÓ o
    # `bluetoothctl`, e desde a migração o produto também chama o `btmgmt`
    # (`bt_active_mode.sh`, `doctor.sh`, `uninstall.sh`). Os dois entram, e a
    # tabela de pacotes NÃO muda — MEDIDO em contêiner limpo no mesmo dia,
    # família por família, e é o único jeito honesto de afirmar isto:
    #     debian:12   -> `dpkg -S /usr/bin/btmgmt` = bluez (o mesmo do bluetoothctl)
    #     fedora:40   -> `dnf repoquery --whatprovides /usr/bin/btmgmt` = bluez
    #     archlinux   -> `pacman -F usr/bin/btmgmt` = extra/bluez-utils
    # No Arch a dupla vive em `bluez-utils`, que a linha `bluez)` de `_pkg_nome`
    # já instala junto com o `bluez`. Se um dia alguma família separar os dois,
    # é ESTA linha que grita — antes era ela que ficava cega.
    "bluez|importante|cmd:bluetoothctl,btmgmt|parear pelo rádio, conferir o bond e o diagnóstico de Bluetooth param de funcionar"
    "usbutils|importante|cmd:lsusb|o diagnóstico perde a leitura do barramento USB"
    "fontconfig|importante|cmd:fc-cache|a interface troca de fonte em silêncio (Space Grotesk e JetBrains Mono não entram)"
    "curl|importante|cmd:curl|as fontes da identidade visual não são baixadas"
)

# Cheque ANTES de instalar. A instalação dela roda muitas vezes; chamar o
# gerenciador de pacotes à toa é barulho, e barulho é defeito. Cada checagem
# pergunta pelo EFEITO (a biblioteca abre? o gdk-pixbuf lê SVG?), nunca pelo
# nome do pacote — é o que faz a mesma régua valer nas quatro famílias.
_dep_presente() {
    local _checagem="$1" _bin _inc _saida
    case "${_checagem}" in
        lib:*)
            # A pergunta é "a biblioteca ABRE?", não "o `ldconfig` a lista?" —
            # e é a mesma disciplina do `svg` e do `appindicator` logo abaixo.
            # `ctypes.CDLL` é LITERALMENTE o que o produto faz: o `hidapi` do
            # pip abre por `ffi.dlopen` (`hidapi.py:149`) e o
            # `integrations/dualsense_bt_audio.py:473-494` abre a libopus por
            # `ctypes.CDLL`. Se abrir aqui, abre lá.
            #
            # POR QUE NÃO O `ldconfig`, e isto é um BLOQUEANTE medido em
            # 19/08/2026: ele mora em `/usr/sbin`, que NÃO está no PATH de
            # usuário comum no Debian 12 — só no do root. A régua sairia vazia
            # para toda pessoa que instala sem ser root, e TODA biblioteca
            # presente seria lida como ausente. O CI é cego para isso porque os
            # contêineres da matriz rodam como root, e o root tem sbin no PATH
            # em qualquer distro.
            #
            # E há um segundo buraco, medido no mesmo dia e que o `ldconfig`
            # tinha: com o `set -o pipefail` deste arquivo (linha 188), um
            # `ldconfig -p | grep -q` devolvia 141 — o `grep -q` sai no
            # primeiro acerto, o `ldconfig` morre de SIGPIPE, e o pipeline
            # inteiro reprova. Os dois buracos somem perguntando pelo efeito.
            #
            # O `ldconfig` fica como PLANO B, com caminho absoluto, para o caso
            # de o venv ainda não existir quando alguém chamar isto de outro
            # ponto do arquivo.
            # LISTA separada por vírgula, e ela não é conveniência: o wrapper
            # `hidapi.py` do pip percorre `libhidapi-hidraw.so[.0]`,
            # `libhidapi-libusb.so[.0]` e outros até um abrir (hidapi.py:136-144).
            # A régua tem de aceitar as mesmas alternativas, senão reprova numa
            # máquina em que o produto funcionaria.
            local _sos="${_checagem#lib:}" _so
            # shellcheck disable=SC2086  # a lista separada por vírgula é o objetivo
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
            # shellcheck disable=SC2086  # a lista separada por vírgula é o objetivo
            for _bin in ${_bins//,/ }; do
                command -v "${_bin}" >/dev/null 2>&1 || return 1
            done
            return 0
            ;;
        svg)
            # A pergunta certa não é "o pacote está instalado?", e sim "o
            # gdk-pixbuf sabe ler SVG?" — que é o que a interface faz.
            "${VENV_DIR}/bin/python" -c "import gi;gi.require_version('GdkPixbuf','2.0');from gi.repository import GdkPixbuf;import sys;sys.exit(0 if any(f.get_name()=='svg' for f in GdkPixbuf.Pixbuf.get_formats()) else 1)" >/dev/null 2>&1
            ;;
        appindicator)
            # A bandeja tenta Ayatana e cai no AppIndicator3 (app/tray.py) —
            # a checagem aceita os dois, como o produto.
            "${VENV_DIR}/bin/python" -c "import gi;gi.require_version('AyatanaAppIndicator3','0.1')" >/dev/null 2>&1 ||
            "${VENV_DIR}/bin/python" -c "import gi;gi.require_version('AppIndicator3','0.1')" >/dev/null 2>&1
            ;;
        webkit)
            # TOCA UM SÍMBOLO, e é por isso que a linha termina numa chamada.
            #
            # CORREÇÃO DE FATO, 29/08/2026: esta checagem dizia que o `import`
            # bastava, porque "o typelib sem a biblioteca passaria pela versão".
            # MEDIDO, remendando um typelib real com um SONAME inexistente:
            #
            #   require_version('WebKit2','4.1')   -> PASSA
            #   from gi.repository import WebKit2  -> PASSA TAMBÉM (só um WARNING
            #                                         no stderr, que o 2>&1 come)
            #   WebKit2.get_major_version()        -> GError: Could not locate
            #                                         webkit_get_major_version
            #
            # O import NÃO compra nada sobre o `require_version` para o caso que
            # a justificativa dizia pegar. Quem responde "o motor CARREGA?" é
            # tocar um símbolo. Custo medido: 21 ms (versão) / 67 (+import) /
            # 78 (+chamada) — 11 ms compram a garantia.
            #
            # RISCO REAL, honesto: o `gir1.2-webkit2-4.1` tem
            # `Depends: libwebkit2gtk-4.1-0 (= mesma versão)`, e Fedora e Arch
            # entregam os dois no mesmo pacote — gerenciador de pacotes não
            # produz esse estado. O fato errado estava na JUSTIFICATIVA, não na
            # máquina de ninguém. Mas régua que promete o que não faz é o padrão
            # que esta casa já nomeou: *a régua confunde a PALAVRA com o ATO*.
            #
            # A série é 4.1 porque é a de GTK 3. A 6.0 é GTK 4 e não entra no
            # processo do produto.
            "${VENV_DIR}/bin/python" -c "import gi;gi.require_version('WebKit2','4.1');from gi.repository import WebKit2;WebKit2.get_major_version()" >/dev/null 2>&1
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

# O passo que fecha a lacuna: garante o censo inteiro, em qualquer família.
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

    # Família sem tratamento (NixOS, Gentoo, container enxuto): não minta e não
    # aborte. Quem está lá tem de sair sabendo o que instalar à mão — inclusive
    # o que é OBRIGATÓRIO, que aqui vira aviso porque o instalador não tem como
    # cumprir a promessa nem como julgar o sistema de pacotes da pessoa.
    if [[ "${_familia}" == "nenhum" ]]; then
        warn "não reconheço o gerenciador de pacotes desta distro — não instalei nada"
        printf '      Instale o equivalente na sua distro (nome no Debian/Ubuntu como referência):\n'
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
        # Reconfere pelo EFEITO: morre só quem continuou faltando. Um nome de
        # pacote errado nesta tabela não pode passar por instalado.
        #
        # NO ENSAIO A RECONFERÊNCIA NÃO VALE, e deixá-la valer seria o pior
        # tipo de instrumento falso: nada foi instalado (é o ponto do ensaio),
        # então TODA obrigatória ausente continuaria ausente e o `die` abaixo
        # mataria o plano no meio — dizendo "faltam dependências obrigatórias"
        # sobre um instalador que teria acabado de instalá-las.
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
    # O ENSAIO NUNCA PEDE SENHA. Um modo que promete "não escrevo nada" e abre
    # um prompt de senha já quebrou a promessa antes da primeira linha do plano.
    # O preço é que os passos de root vão dizer "sudo recusado" — e é a verdade
    # do que aconteceria agora, com esta sessão. Dizemos como ver o plano
    # inteiro, em vez de fingir que ele existe.
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
    # O ensaio não pode PARAR num `read`: quem pede o plano quer o plano.
    # Assumimos o mesmo default do menu (native) e dizemos que assumimos.
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

# ---------------------------------------------------------------------------
# As DEZ curas de HOST moram em `scripts/lib/camada_de_maquina.sh` (31/08/2026)
# ---------------------------------------------------------------------------
# Elas moravam AQUI — `_render_broker_units` nas linhas 873-893 e as dez
# `*_host` nas 989-1677. Saíram por um motivo com data: ela desinstalou o
# Hefesto estável e ficou só com o de desenvolvimento, e o `install-dev.sh`
# dependia deste arquivo para a camada de máquina — dependência escrita no
# cabeçalho dele desde 29/08. Sem o estável, ninguém instalava udev, grupo
# `hefesto`, broker, resiliência do bluetoothd nem a ponte privilegiada.
#
# A cura NÃO foi duplicar: foi dar às dez uma casa que os DOIS instaladores
# possam sourcear. O `install-dev.sh` NUNCA executa este arquivo — sourcear a
# lib é o que torna isso possível, e a regra do `CLAUDE.md` ("nunca rode
# install.sh na árvore de dev") continua de pé, literal.
#
# Nada mudou de comportamento: as funções são as mesmas, byte por byte, e
# continuam sendo CHAMADAS daqui, dos dois lados da cerca. O portão
# `tests/unit/test_install_serve_os_dois_lados_da_cerca.py` passou a ler os
# corpos da lib e as regiões daqui, e continua cobrando o que sempre cobrou.
# shellcheck source=scripts/lib/camada_de_maquina.sh
source "${ROOT_DIR}/scripts/lib/camada_de_maquina.sh"

# ---------------------------------------------------------------------------
# O ENSAIO DAS CURAS DE HOST — o que cada `*_host` escreveria
# ---------------------------------------------------------------------------
# As onze curas moram na lib acima, e o ensaio NÃO PODE CHAMÁ-LAS: elas
# escrevem em `/etc`, compilam módulo de kernel e sobem serviço de sistema.
# Então elas são DESCRITAS aqui, e a descrição é uma cópia de conhecimento —
# exatamente o tipo de coisa que envelhece calada.
#
# O QUE IMPEDE A DIVERGÊNCIA: `tests/unit/test_o_ensaio_do_install_nao_escreve.py`
# lê cada caminho absoluto citado abaixo e exige que ele apareça no corpo da
# função correspondente em `scripts/lib/camada_de_maquina.sh`. Alguém que mude o
# alvo lá e esqueça daqui reprova, com o caminho na mensagem — é a mordida.
_ensaio_camada() {
    case "$1" in
        udev)
            _faria_root "copiar as regras udev canônicas de assets/*.rules para /etc/udev/rules.d/ e recarregar o udev (scripts/install_udev.sh)"
            ;;
        osk)
            _faria "instalar o teclado na tela do L3 pelo gerenciador de pacotes: wvkbd em Wayland, onboard em X11 (scripts/install_osk.sh)"
            _faria "gravar o que aconteceu em ${HOME}/.local/state/hefesto-dualsense4unix/teclado-na-tela.conf"
            ;;
        broker)
            _faria_root "instalar o broker em /usr/local/lib/hefesto-dualsense4unix/hefesto-hidraw-broker"
            _faria_root "instalar /etc/systemd/system/hefesto-hidraw-broker.service e .socket (renderizados com o seu uid e grupo)"
            _faria_root "systemctl daemon-reload e enable --now hefesto-hidraw-broker.socket"
            _faria "gravar o registro de posse em ${HOME}/.local/state/hefesto-dualsense4unix/broker-owner.conf"
            ;;
        bt-res)
            _faria_root "instalar oito roteiros de Bluetooth em /usr/local/lib/hefesto-dualsense4unix/ (snapshot e restauro de bonds, watchdog, modo ativo)"
            _faria_root "rodar bt_active_mode.sh AGORA (tira o Pro Controller do modo sniff — não reinicia o bluetoothd)"
            _faria_root "instalar /etc/systemd/system/bluetooth.service.d/10-hefesto-resilience.conf (Restart + WatchdogSec=0 + snapshot na parada)"
            _faria_root "instalar os timers hefesto-bt-bonds-snapshot e hefesto-bt-health-watchdog em /etc/systemd/system/ e habilitá-los"
            _faria_root "criar /var/lib/hefesto-dualsense4unix/bt-bonds (modo 700) para os snapshots"
            ;;
        bt-agent)
            _faria_root "instalar /etc/systemd/system/hefesto-bt-agent.service e habilitá-lo (agente de pareamento persistente; instala bluez-tools se faltar)"
            ;;
        bt-ponte)
            _faria_root "instalar /usr/local/lib/hefesto-dualsense4unix/bt_ponte_privilegiada.sh"
            _faria_root "gravar /etc/sudoers.d/49-hefesto-bt-ponte (0440 root:root) — CONFERIDO com 'visudo -c' antes; se não passar, nada é gravado"
            ;;
        gabinete)
            _faria_root "ler a tabela SMBIOS 8 com dmidecode (leitura pura, nada é escrito no firmware)"
            _faria "gravar o censo em ${HOME}/.local/state/hefesto-dualsense4unix/gabinete.json"
            ;;
        dkms-nintendo)
            _faria_root "compilar e instalar o módulo DKMS hefesto-hid-nintendo (substitui o hid-nintendo in-tree por precedência; o in-tree NUNCA é removido)"
            _faria_root "instalar /etc/modprobe.d/hefesto-hid-nintendo.conf (bt_probe_retries=3 + skip_tx_on_rate_exceeded=1)"
            ;;
        dkms-rtw88)
            _faria_root "compilar e instalar o módulo DKMS hefesto-rtw88-usb (cura do fantasma USB do dongle WiFi; sem conf em /etc/modprobe.d)"
            ;;
        dkms-playstation)
            _faria_root "compilar e instalar o módulo DKMS hefesto-hid-playstation (retry de feature report na contenção BT)"
            _faria_root "instalar /etc/modprobe.d/hefesto-hid-playstation.conf (feature_retries=2 + ds4_* do clone no cabo)"
            ;;
        initramfs)
            _faria_root "regenerar o initramfs UMA vez, e só se algum módulo DKMS acima tiver mudado (update-initramfs)"
            ;;
    esac
}

# NO ENSAIO, AS ONZE CURAS VIRAM DESCRIÇÃO — e a troca é feita AQUI, num lugar
# só, trocando o corpo das funções que a lib acabou de definir.
#
# POR QUE TROCAR O NOME, e não pôr um `if` em cada chamada: elas são VINTE, e
# estão espalhadas pelos dois lados da cerca dos formatos. Bastaria alguém
# acrescentar uma chamada nova sem o `if` para o ensaio ESCREVER no /etc de
# quem só queria ver o plano — um modo que promete não tocar em nada e toca é o
# instrumento falso mais caro que esta casa poderia produzir. Trocando o corpo,
# nenhuma chamada escapa, nem a que ainda não existe.
#
# POR QUE PELO `eval`, E NÃO ESCREVENDO `nome_host() { … }` À MÃO: medido em
# 03/09/2026, e é um defeito que este arquivo produziu e uma régua pegou. Seis
# testes desta casa acham o CORPO de uma cura procurando o texto
# `install_..._host() {` no `install.sh` — é assim que
# `test_a_ponte_privilegiada_entra_e_sai_do_install` confere que a regra do
# sudoers passa pelo `visudo` antes de ser gravada. Um segundo `nome_host() {`
# escrito aqui vira o corpo que essas réguas leem, e elas passam a medir a
# descrição do ensaio em vez da cura: as seis reprovaram de uma vez, dizendo
# que o install tinha parado de conferir o sudoers. Não tinha. A régua estava
# certa e o texto é que ficou ambíguo.
#
# Com a tabela abaixo, o `install.sh` não contém nenhuma linha que se pareça
# com a definição de uma cura, e o efeito em tempo de execução é idêntico.
# Quem guarda a tabela é `tests/unit/test_o_ensaio_do_install_nao_escreve.py`:
# ela tem de cobrir TODA função `*_host` da lib, inclusive a de amanhã.
_ENSAIO_CURAS_DE_HOST=(
    "install_udev_host:udev"
    "install_osk_host:osk"
    "install_broker_host:broker"
    "install_bt_resilience_host:bt-res"
    "install_bt_agent_host:bt-agent"
    "install_bt_ponte_privilegiada_host:bt-ponte"
    "install_censo_do_gabinete_host:gabinete"
    "install_dkms_hid_nintendo_host:dkms-nintendo"
    "install_dkms_rtw88_usb_host:dkms-rtw88"
    "install_dkms_hid_playstation_host:dkms-playstation"
    "flush_initramfs_host:initramfs"
)
if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
    for _ensaio_par in "${_ENSAIO_CURAS_DE_HOST[@]}"; do
        eval "${_ensaio_par%%:*}() { _ensaio_camada ${_ensaio_par##*:}; }"
    done
    unset _ensaio_par
fi

# Os OUTROS roteiros de `scripts/` que o install executa, descritos uma vez só —
# os dois lados da cerca chamam os mesmos, e uma descrição por lado divergiria.
# Mesma guarda do `_ensaio_camada`: o teste confere cada caminho absoluto daqui
# contra o roteiro que o escreve.
_ensaio_snd_quirk() {
    _faria_root "gravar /etc/modprobe.d/hefesto-dualsense-storm.conf (quirk_flags do snd_usb_audio — cura do storm -71 preservando mic e fone)"
    _faria_root "ativar o quirk a quente em /sys/module/snd_usb_audio/parameters/quirk_flags (sem reboot; sem isto, vale no próximo boot)"
}
_ensaio_wireplumber() {
    case "$1" in
        nunca-dorme)
            _faria "instalar o drop-in 54-hefesto-dualsense-alto-falante-nunca-dorme.conf em ${HOME}/.config/wireplumber/wireplumber.conf.d/"
            ;;
        install)
            _faria "instalar o drop-in 51-hefesto-dualsense-no-default-source.conf em ${HOME}/.config/wireplumber/wireplumber.conf.d/ (rebaixa o microfone do controle)"
            _faria "eleger outra fonte de captura como padrão do sistema, se houver uma de verdade"
            ;;
        disable-source)
            _faria "instalar os drop-ins 52- e 53- em ${HOME}/.config/wireplumber/wireplumber.conf.d/ (desabilitam a entrada e a saída do controle — ele vira só-HID)"
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

    # 1. Família da distro. DEPS-UNIVERSAIS-01 (19/08/2026) substituiu o texto
    # que estava aqui: ele dizia "o caminho nativo instala dependências só por
    # apt", e isso caducou — o `run_pkg` despacha para apt, dnf e pacman. Fato
    # errado se SUBSTITUI. O que sobra de aviso é honesto: fora do apt, os
    # nomes de pacote não têm hardware desta casa por trás.
    local _fam
    _fam="$(_familia_pacotes)"
    if [[ "${_fam}" == "nenhum" ]]; then
        warn "não reconheço o gerenciador de pacotes desta distro"
        printf '      O install vai DIZER o que falta, com o nome no Debian/Ubuntu como\n'
        printf '      referência, e seguir sem instalar nada — em Nix ou Gentoo, use o\n'
        printf '      pacote da sua distro (ver docs/usage/instalacao.md).\n'
        achou_algo=1
    elif [[ "${_fam}" != "apt" ]]; then
        warn "distro fora da família Debian/Ubuntu — o install usa ${_fam}"
        printf '      As dependências de sistema são instaladas pelo %s, com os nomes que\n' "${_fam}"
        printf '      esta casa já declara no empacotamento da sua família. O que ainda não\n'
        printf '      foi validado em hardware é a distro, não o instalador.\n'
        achou_algo=1
    fi

    # 2. BlueZ. A faixa validada é a mesma que o doctor cobra no fim.
    local _bz
    # `|| true` NÃO é decoração, e a falta dele foi MEDIDA em 19/08/2026 num
    # contêiner debian:12 limpo: sem `bluetoothctl` no PATH o `command not
    # found` devolve 127, o `set -o pipefail` da linha 188 propaga, o `set -e`
    # derruba o script — e o `2>/dev/null` engole até a mensagem. O instalador
    # morria calado, com código 127, ANTES do passo 1 de 11.
    #
    # E isso contradizia o desenho do próprio arquivo: o censo de dependências
    # lista `bluez` como IMPORTANTE, não obrigatória — ou seja, o instalador
    # deve seguir sem ele e só avisar. Quem descobriu foi o job novo que EXECUTA
    # o install.sh em contêiner; nenhuma máquina de quem desenvolve pega isto,
    # porque todas têm bluetoothctl.
    _bz="$(bluetoothctl --version 2>/dev/null | awk '{print $NF}' || true)"
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
# DEPS-UNIVERSAIS-01: o guarda era `command -v apt-get`, então fora do Debian o
# instalador nem PERGUNTAVA sobre os módulos — as três curas de raiz sumiam em
# silêncio, que é o verde mentiroso descrito acima. Agora vale em toda família
# reconhecida, com os nomes da tabela.
if [[ "${NO_DKMS}" -eq 0 ]] && [[ "$(_familia_pacotes)" != "nenhum" ]]; then
    _dkms_faltando=()
    command -v dkms >/dev/null 2>&1 || _dkms_faltando+=("dkms")
    command -v make >/dev/null 2>&1 || _dkms_faltando+=("compilador")
    [[ -d "/lib/modules/$(uname -r)/build" ]] || _dkms_faltando+=("kernel-headers")

    if [[ "${#_dkms_faltando[@]}" -gt 0 ]]; then
        printf '\n      Os três módulos de kernel desta casa precisam compilar, e falta:\n'
        printf '        %s\n' "$(comando_manual_pkg "${_dkms_faltando[@]}")"
        printf '      Sem eles, as curas NÃO entram: o controle da Nintendo pode não subir\n'
        printf '      pelo rádio, e dois DualSense no mesmo adaptador podem virar um só.\n\n'
        ask_yn "instalar agora com sudo?" "${AUTO_YES}"
        if [[ "${REPLY,,}" =~ ^y ]]; then
            if run_pkg "${_dkms_faltando[@]}"; then
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
        if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
        _ensaio_snd_quirk
        elif bash "${ROOT_DIR}/scripts/install_snd_quirk.sh"; then
            # A ATIVAÇÃO A QUENTE É CONFERIDA, e não declarada: ela estava num
            # `|| true` e a linha seguinte anunciava "instalada E ATIVADA" sem
            # ter olhado. Instalar é gravar o `.conf` (vale no próximo boot);
            # ativar é o `--runtime`, e os dois podem divergir.
            if bash "${ROOT_DIR}/scripts/install_snd_quirk.sh" --runtime >/dev/null 2>&1; then
                printf '      cura instalada e ativada (replug do controle p/ valer já)\n'
            else
                printf '      cura instalada; ativação a quente NÃO passou — vale no próximo boot\n'
            fi
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
    # ONDA-R2 (22/08/2026): mesmo achado do broker, na camada do Bluetooth. Os
    # formatos de pacote levavam as regras udev 82 e 83 — que existem SÓ para
    # chamar dois alvos desta camada — e saíam pelo `exit 0` sem a camada. A
    # regra 83 apontava para uma unit inexistente e o salva-vidas de bonds nunca
    # gravou nada para quem instalou por aqui (medido em 07/08, estudo da
    # cobertura do install, item 9). Mesma função do passo 3e-bis do nativo.
    step "bt-res" "ONDA-R2: resiliência do bluetoothd (DEFAULT em todo formato)"
    install_bt_resilience_host
    # ONDA-R (31/08/2026): o agente de pareamento persistente era código de topo
    # do lado NATIVE e ficava de fora daqui — flatpak/appimage/deb saíam sem
    # ele, e todo bond novo nascia meio-salvo (`Paired: yes / Bonded: no`) e
    # sumia. Escapou anos ao portão das curas de host por não ter nome: o
    # portão ancora no sufixo `_host`, e um bloco solto não tem. Virou função,
    # e o portão acusou a falta no mesmo minuto.
    step "bt-agent" "ONDA-R: agente de pareamento BT persistente (DEFAULT em todo formato)"
    install_bt_agent_host
    # PONTE-PRIVILEGIADA-01: mesma razão da linha acima, uma camada adiante —
    # é mudança de SISTEMA (helper em /usr/local/lib + regra em /etc/sudoers.d),
    # ortogonal ao formato do aplicativo. Sem esta chamada, quem instala por
    # flatpak/appimage/deb sairia com a aba de rádio pedindo senha a cada gesto.
    step "bt-ponte" "PONTE-PRIVILEGIADA-01: a ponte de root do Bluetooth (DEFAULT em todo formato)"
    install_bt_ponte_privilegiada_host
    # MOTOR-7: mesma razão das duas linhas acima. Ler a tabela SMBIOS é trabalho
    # de HOST — quem tem a tabela é a placa, não o formato do aplicativo. Sem
    # esta chamada, quem instala por flatpak/appimage/deb sairia pelo `exit 0`
    # abaixo com a aba Conexões pedindo os três números à mão, e sem nem saber
    # que a BIOS tinha uma resposta a dar.
    step "gabinete" "MOTOR-7: censo do gabinete pelo firmware (DEFAULT em todo formato)"
    install_censo_do_gabinete_host
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
        step "mic" "áudio: a voz do controle acima do eco da saída (MIC-EM-TODO-FORMATO-01)"
        # O `-ne 1` e não o `||`: rc 2 (o DualSense é a única fonte) e rc 3 (a
        # fonte padrão ainda não é um microfone) NÃO são falha do gesto — são o
        # estado da máquina, e o script já os explica na tela. Tratá-los como
        # falha mandaria ela rodar de novo um comando que faria exatamente o
        # mesmo, que é o laço que 01/09 curou.
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
if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
    # O ensaio nomeia os diretórios que EXISTEM: "apagaria dist/" só interessa
    # a quem tem um `dist/` com um pacote recém-construído dentro.
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
        if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
        _faria "APAGAR e recriar ${VENV_DIR} (o venv de hoje foi criado com um Python que não é o do sistema)"
        else
        rm -rf "${VENV_DIR}"
        fi
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
    # DEPS-UNIVERSAIS-01: o `2>/dev/null` sem checagem de retorno escondia o
    # caso mais banal de máquina Debian limpa — `python3-venv` não instalado.
    # O venv não nascia, o silêncio passava, e a linha seguinte rodava contra
    # um venv inexistente. Agora: tenta, instala o módulo, tenta de novo, e só
    # então morre — com o comando exato na tela.
    if ! "${_VENV_PYTHON}" -m venv --system-site-packages "${VENV_DIR}" 2>/dev/null; then
        printf '      módulo venv ausente — instalando pelo %s\n' "$(_familia_pacotes)"
        run_pkg python-venv || true
        if ! "${_VENV_PYTHON}" -m venv --system-site-packages "${VENV_DIR}" 2>/dev/null; then
            printf '      rode: %s\n' "$(comando_manual_pkg python-venv)"
            die "não consegui criar o venv em ${VENV_DIR}"
        fi
    fi
fi

if ! "${VENV_DIR}/bin/python" -c \
        "import gi; gi.require_version('Gtk','3.0')" >/dev/null 2>&1; then

    printf '\n      Bindings GTK3 não encontrados — obrigatórios para a GUI.\n'
    # DEPS-UNIVERSAIS-01: os nomes saem da tabela, na família desta máquina —
    # antes esta lista era a grafia do apt e, fora do Debian, o `run_apt`
    # falhava e o install MORRIA sem ter como acertar.
    printf '      Rodaria: %s\n\n' \
        "$(comando_manual_pkg python-gi python-gi-cairo gtk3 appindicator gi-dev)"

    ask_yn "instalar agora com sudo?" "${AUTO_YES}"
    if [[ "${REPLY,,}" =~ ^y ]]; then
        printf '      instalando...\n'
        run_pkg python-gi python-gi-cairo gtk3 appindicator gi-dev \
            || die "falha ao instalar GTK3 — verifique a conexão e tente novamente"
        printf '      GTK3 instalado\n'
    else
        die "GTK3 obrigatório. Instale manualmente e reexecute ./install.sh"
    fi
fi

# --- DEPS-UNIVERSAIS-01: o resto do censo, em qualquer família ---------------
# Aqui e não antes: as checagens do loader SVG e da bandeja perguntam ao
# `gi` do venv, que só existe depois do bloco acima.
_garantir_deps_de_sistema

# --- BT-MIC-01: o ÁUDIO do DualSense por Bluetooth, nas DUAS direções --------
# Em Bluetooth o DualSense NÃO fala A2DP/HFP: o áudio vai e vem como Opus
# dentro dos reports HID, e o Hefesto o codifica e o decodifica por ctypes
# sobre a libopus DO SISTEMA — de propósito, para não precisar de binding pip
# (regra do projeto: nada de pip ad-hoc; tudo replicável por script).
#
# A libopus SERVE ÀS DUAS PONTAS DESDE 10/09/2026, e antes desta data este
# bloco só conhecia a de ENTRADA:
#   * ENTRA  — o microfone. `mic bt` DECODIFICA (`integrations/dualsense_bt_audio.py`);
#   * SAI    — o alto-falante. O som CODIFICADO chega ao plástico pelo report
#              `0x35`, um quadro Opus de 10 ms (48 kHz estéreo, CBR 160 kbps)
#              a cada 10,667 ms. Medido na bancada dela em 10/09/2026, com a
#              orelha dela e 70 s sem um corte; o codificador é o
#              `integrations/alto_falante_bt.CodificadorOpus`, e ele abre a
#              MESMA `libopus.so.0` por um handle próprio (`:276`).
#
# **Sem a libopus o som por rádio não sai** — e o sintoma é silêncio, que se lê
# como «o controle não suporta». Era exatamente o que esta casa acreditava até
# 10/09. Ver `docs/protocol/dualsense-referencia-canonica.md`, seção *"O som que
# saiu pelo rádio"*.
# `pactl` (pulseaudio-utils) é quem publica o microfone no PipeWire.
# Best-effort: sem isso o hefesto inteiro funciona, só o `mic bt` não sobe —
# e ele já diz exatamente o que falta (`mic bt-status`).
# DEPS-UNIVERSAIS-01: nomes canônicos, para o mic por BT nascer também em
# Fedora e em Arch — antes este bloco só sabia falar apt.
# A checagem da libopus passou a ser a mesma régua do censo (`_dep_presente`)
# por um defeito MEDIDO em 19/08/2026: o `ldconfig -p | grep -q` que morava
# aqui devolvia 141 sob `pipefail` (SIGPIPE do ldconfig quando o grep sai no
# primeiro acerto), então este bloco chamava o gerenciador de pacotes para
# instalar a libopus JÁ INSTALADA a cada execução do install. Barulho é defeito.
#
# O `pactl` DAQUI NÃO É DUPLICATA — 03/09/2026. Desde a LUZ-DO-MIC-01 ele
# também vive no censo `_DEPS_DE_SISTEMA`, que roda logo acima. Quem aceitou lá
# chega aqui com o binário presente e este bloco fica calado; quem recusou lá
# ganha uma segunda chance, agora com o motivo do rádio na tela. As duas linhas
# pedem o MESMO canônico, então nenhuma instala coisa diferente da outra.
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
if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
    _faria "atualizar pip e packaging dentro de ${VENV_DIR}"
    _faria "instalar o pacote em modo editável no venv: pip install -e '${ROOT_DIR}[${_extras}]'"
elif ! "${VENV_DIR}/bin/pip" install \
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

    if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
        _ensaio_camada udev
        _faria_root "gravar /etc/modules-load.d/ para o uinput e o uhid subirem no boot, e recarregar o udev"
    elif bash "${ROOT_DIR}/scripts/install_udev.sh" >/dev/null 2>&1; then
        printf '      regras aplicadas + udev recarregado + uinput carregado\n'
    else
        warn "install_udev.sh falhou — rode manualmente: sudo bash scripts/install_udev.sh"
    fi

    # v3.3.1: se Flatpak Hefesto está instalado, propagar as regras pelo
    # caminho oficial do bundle também (defensive — install_udev.sh já cobriu
    # o host, mas o usuário pode esperar simetria explícita "tudo pro
    # Flatpak". A chamada é no-op se as regras já estão lá).
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
    if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
        _faria_root "acrescentar usbcore.quirks=054c:0ce6:gn,054c:0df2:gn ao cmdline do kernel (kernelstub ou grub) — vale no PRÓXIMO boot"
    elif bash "${ROOT_DIR}/scripts/install_usb_quirk.sh"; then
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
    if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
        _ensaio_snd_quirk
    elif bash "${ROOT_DIR}/scripts/install_snd_quirk.sh"; then
        bash "${ROOT_DIR}/scripts/install_snd_quirk.sh" --runtime >/dev/null 2>&1 || true
    else
        warn "install_snd_quirk.sh retornou erro — rode: sudo bash scripts/install_snd_quirk.sh"
    fi
    # Post-check: confirma que a cura PERSISTENTE realmente foi gravada. Sem sudo
    # cacheado (install não-interativo), o `as_root install` interno falhava e o
    # passo seguia como se tivesse aplicado — deixando só o runtime, que some no
    # reboot. Agora avisamos explicitamente se o .conf não existe.
    if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
        : # o ensaio não gravou nada; conferir a existência do .conf aqui só
          # produziria um "cura NÃO persistiu" sobre uma cura que ninguém tentou
    elif [[ -f "${SND_QUIRK_CONF}" ]]; then
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
# SEGUNDA NOTA DATADA — O FATO DE 06/08 CADUCOU EM 19/08/2026, e a decisão NÃO.
# Desde 19/08 o CI roda, sim, o `install.sh`: o job `install-multi-distro` do
# `ci.yml` o executa DE VERDADE dentro dos contêineres de Fedora 40, Arch e
# Debian 12, como USUÁRIA COMUM (o PATH de login dela, nunca o do root).
#
# O que NÃO mudou é o que sustenta este gate: ele se sustenta no CONTRATO
# documentado — `--no-udev` pula os passos que tocam `/etc`, e este escreve em
# `/etc/bluetooth/main.conf`. A justificativa antiga — a que falava em reescrever
# o `main.conf` da máquina onde o CI constrói — continua falsa e continua
# proibida por portão; a premissa de 06/08 é que envelheceu, e envelheceu porque
# o produto melhorou.
#
# E o job novo pagou por si no primeiro uso: achou DOIS bloqueantes vivos que
# nenhuma máquina de quem desenvolve pegava — o `bluetoothctl --version` sem
# guarda, que matava o instalador com 127 antes do passo 1 de 11 em qualquer
# máquina sem BlueZ; e um soname que o `dlopen` nunca abre. Os dois estão
# curados neste arquivo, com teste que morde.
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
    if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
        _faria_root "gravar /etc/modprobe.d/hefesto-btusb-no-autosuspend.conf (o adaptador Bluetooth nunca dorme)"
        _faria_root "zerar /sys/module/btusb/parameters/enable_autosuspend agora (a quente, sem reboot)"
        _faria_root "normalizar /etc/bluetooth/main.conf: FastConnectable ligado e JustWorksRepairing=confirm (backup ao lado; o bluetoothd NÃO é reiniciado)"
    elif ! sudo -n true 2>/dev/null; then
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
    if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
        if [[ "${SKIP_UDEV}" -eq 1 ]]; then
            _nao_faria "nada aqui: --no-udev pula os passos que tocam /etc"
        else
            _faria_root "gravar /etc/NetworkManager/conf.d/hefesto-wifi-powersave.conf (wifi.powersave=2) — vale na próxima reconexão; nada é tocado no rádio agora"
        fi
    elif [[ "${SKIP_UDEV}" -eq 1 ]]; then
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
                    # O `sed` LÊ o arquivo que a linha de cima acabou de
                    # escrever. No ensaio ninguém o escreveu (é o ponto do
                    # ensaio), e ler um arquivo inexistente cuspia um erro do
                    # `sed` no meio do plano e imprimia "dono registrado: "
                    # vazio — dois defeitos de tela criados pelo próprio modo
                    # que existe para não criar nada.
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
                    if [[ "${_cmdline_backend}" != "kernelstub" ]]; then
                        warn "${_param}: bootloader é grub — aplique manualmente em GRUB_CMDLINE_LINUX_DEFAULT: ${_token}"
                        [[ -n "${_removes}" ]] && warn "  (removendo antes o(s) token(s): ${_removes} — o kernel respeita SÓ UM usbcore.quirks=)"
                        continue
                    fi
                    if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
                        # O PLANO DO CMDLINE JÁ FOI CALCULADO ACIMA, e sem
                        # escrever nada: quem decide é o módulo puro
                        # `integrations/kernel_cmdline.py`, lendo o bootloader.
                        # Então este é o passo em que o ensaio mostra o TOKEN
                        # EXATO que entraria na linha de comando do kernel dela.
                        # `if`, e não `[[ ]] && cmd`: com `_removes` vazio a
                        # lista devolveria 1 e o `set -e` mataria o ensaio aqui.
                        # É a armadilha que o passo 11c já documenta neste
                        # arquivo, e ela pega igual dentro do ensaio.
                        if [[ -n "${_removes}" ]]; then
                            _faria_root "tirar do cmdline do kernel, antes de fundir (o kernel respeita SÓ UM usbcore.quirks=): ${_removes}"
                        fi
                        _faria_root "pôr no cmdline do kernel (kernelstub): ${_token} — vale no PRÓXIMO boot"
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
# 3e-bis. ONDA-R2: resiliência do bluetoothd — DEFAULT em TODO formato
# ---------------------------------------------------------------------------
# O corpo mora em `install_bt_resilience_host`, acima da bifurcação de formato,
# e o outro lado da cerca a chama também — o racional inteiro está lá.
# A POSIÇÃO AQUI É QUE IMPORTA: antes do 3f, porque o postinst do backport do
# BlueZ reinicia o bluetoothd, e o drop-in precisa existir para armar nesse
# restart.
step "3e-bis" "ONDA-R2: resiliência do bluetoothd (watchdog + snapshot de bonds)"
install_bt_resilience_host

# ---------------------------------------------------------------------------
# 3e-ter. PONTE-PRIVILEGIADA-01: a ponte de root do Bluetooth
# ---------------------------------------------------------------------------
# O corpo mora em `install_bt_ponte_privilegiada_host`, acima da bifurcação de
# formato, e o outro lado da cerca a chama também — o racional inteiro está lá.
# A posição aqui é indiferente (não depende do bluetoothd nem do backport);
# fica colada na resiliência porque é a mesma camada de Bluetooth.
step "3e-ter" "PONTE-PRIVILEGIADA-01: mover controle entre dongles sem pedir senha"
install_bt_ponte_privilegiada_host

# ---------------------------------------------------------------------------
# 3e-quater. MOTOR-7: o censo do gabinete, lido do firmware
# ---------------------------------------------------------------------------
# O corpo mora em `install_censo_do_gabinete_host`, acima da bifurcação de
# formato, e o outro lado da cerca a chama também — o racional inteiro está lá.
# A POSIÇÃO AQUI é a única que importa: DEPOIS do 3e-ter, porque é ali que o
# `sudo -n` desta execução já foi exercitado, e ANTES de qualquer passo que
# demore — o censo custa um `dmidecode` e uma varredura de `/sys` de 6,87 ms, e
# não faz sentido a pessoa esperar um DKMS para o gabinete dela aparecer.
step "3e-quater" "MOTOR-7: censo do gabinete (tabela SMBIOS 8 + barramento)"
install_censo_do_gabinete_host

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
        # Antes do pacote, o RÁDIO: quem cura o crash é o bluetoothd em
        # execução. Quem subiu o 5.86 pelo tarball (drop-in da unit apontando
        # /opt) tinha o dpkg dizendo 5.64 e ouvia deste passo que "o 5.72
        # crônico segue ativo", com o 5.86 rodando na frente dele.
        _bz_vivo="$(
            systemctl show bluetooth.service -p ExecStart --value 2>/dev/null \
                | grep -oE 'path=[^ ]+' | head -1 | cut -d= -f2
        )" || true
        _bz_ja_curado=0
        if [[ -n "${_bz_vivo}" && -x "${_bz_vivo}" ]]; then
            _bz_vv="$("${_bz_vivo}" --version 2>/dev/null | tr -d '[:space:]')" || true
            if [[ -n "${_bz_vv}" ]] && dpkg --compare-versions "${_bz_vv}" ge 5.79 2>/dev/null; then
                _bz_ja_curado=1
            fi
        fi
        _bz_cur="$(dpkg-query -W -f='${Version}' bluez 2>/dev/null || true)"
        if [[ "${_bz_ja_curado}" -eq 1 ]]; then
            printf '      bluetoothd em execução já é %s (%s) — nada a fazer\n' \
                "${_bz_vv}" "${_bz_vivo}"
        elif [[ -z "${_bz_cur}" ]]; then
            printf '      bluez não instalado via dpkg (sistema não-Debian?) — passo pulado\n'
        elif dpkg --compare-versions "${_bz_cur}" ge "${_BZ_TARGET}" 2>/dev/null; then
            printf '      bluez %s já ≥%s — nada a fazer\n' "${_bz_cur}" "${_BZ_TARGET}"
        else
            printf '      bluez %s < alvo %s (5.72: crashes crônicos de input/HIDP; 5.85: heap corruption no loop de reconexão — ver sprint 2026-07-21)\n' "${_bz_cur}" "${_BZ_TARGET}"
            _bz_dir="${HOME}/.cache/hefesto-dualsense4unix/bluez-backport"
            _bz_sums="${_bz_dir}/SHA256SUMS"
            _bz_deb_bluez="$(ls -t "${_bz_dir}"/bluez_*.deb 2>/dev/null | head -1)" || true
            _bz_deb_cups="$(ls -t "${_bz_dir}"/bluez-cups_*.deb 2>/dev/null | head -1)" || true
            _bz_deb_libbt="$(ls -t "${_bz_dir}"/libbluetooth3_*.deb 2>/dev/null | head -1)" || true
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
                    if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
                        _faria "gravar ${_bz_dir}/VERSOES-ANTERIORES.txt (o manifesto que o uninstall usa para devolver o BlueZ de origem)"
                        _faria_root "instalar os .debs do backport do BlueZ (libbluetooth3, bluez, bluez-cups) — o postinst do PRÓPRIO pacote REINICIA o bluetoothd e a migração DESCARTA os bonds atuais"
                    elif [[ "${REPLY,,}" =~ ^y ]]; then
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
                            # O `>` CRIA O ARQUIVO MESMO QUANDO O `dpkg-query`
                            # FALHA, e o `|| true` engole o erro. Pior: o guarda
                            # `! -f` acima faz um arquivo VAZIO nunca ser
                            # reescrito — o restore do BlueZ no uninstall ficaria
                            # sem manifesto PARA SEMPRE, e a tela teria dito
                            # "gravadas". Vazio some, e a falha sai em voz alta.
                            if [[ -s "${_bz_dir}/VERSOES-ANTERIORES.txt" ]]; then
                                printf '      versões anteriores gravadas em %s\n' "${_bz_dir}/VERSOES-ANTERIORES.txt"
                            else
                                rm -f "${_bz_dir}/VERSOES-ANTERIORES.txt"
                                warn "não consegui registrar as versões anteriores do BlueZ — o restore do uninstall não vai cobrir bluez/libbluetooth3"
                            fi
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

step "3g" "ONDA-R: agente de pareamento BT persistente (cura o bond meio-salvo)"
install_bt_agent_host

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
# O `cp` ERA NU, e o próprio comentário acima conta que este caminho já esteve
# quebrado uma vez (o `ICON_SRC` apontava para um PNG que não existia na
# árvore). Com o arquivo ausente o `cp` sai 1 e o `set -e` mata a instalação no
# passo 4 — depois do udev, do DKMS e do broker, e ANTES do daemon, da Steam e
# da conferência. Ícone é acabamento: ele avisa e o resto continua.
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

    # Caminho 1: wlrctl pelo gerenciador desta máquina (se não estiver no PATH).
    # DEPS-UNIVERSAIS-01: antes este bloco IMPRIMIA as linhas de Arch e Fedora
    # mas só INSTALAVA por apt — dizia o certo e fazia o do Debian.
    if ! command -v wlrctl >/dev/null 2>&1; then
        printf '      Caminho recomendado: instalar wlrctl - cobre qualquer\n'
        printf '      app Wayland (não so XWayland). Pacote no Ubuntu 24.04+.\n\n'
        ask_yn "instalar wlrctl agora?" "${AUTO_YES}" "y"
        if [[ "${REPLY,,}" =~ ^y ]]; then
            if command -v sudo >/dev/null 2>&1; then
                if run_pkg wlrctl 2>/dev/null; then
                    printf '      wlrctl instalado (%s)\n' "$(command -v wlrctl)"
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

# O QUE O ATALHO ABRE É A INTERFACE HTML — 01/09/2026, ordem dela: *"tudo tem
# que apontar pro nosso lancher html e tudo tem que apontar pros arquivos na
# nossa pasta"*. O `interface.sh` da raiz é a CARA (o que ela clica); ele
# delega ao `run.sh --gui`, que ativa a venv desta árvore, cuida do XWayland e
# do pixbuf, e chama `scripts/abrir_interface.py` — quem veste prgname,
# WM_CLASS e ícone no processo antes da primeira janela nascer.
#
# Aqui havia `Exec=${ROOT_DIR}/run.sh` quando o `run.sh` abria a janela GTK
# velha. O motor GTK não sumiu (os 74 handlers de `app/actions/` são o que a
# interface nova chama); o que mudou foi o LANÇADOR.
if [[ "${FORCE_XWAYLAND}" -eq 1 ]]; then
    _EXEC_LINE="env GDK_BACKEND=x11 ${ROOT_DIR}/interface.sh"
    printf '      .desktop com GDK_BACKEND=x11 (fallback XWayland)\n'
else
    _EXEC_LINE="${ROOT_DIR}/interface.sh"
fi

# O CABEÇALHO É O DO REPOSITÓRIO, e não um texto digitado aqui. O arquivo
# versionado (`packaging/${APP_ID}.desktop`) traz `@RAIZ@` no `Exec=`; a
# substituição abaixo é a única coisa de máquina que entra. Antes deste bloco
# havia um `.desktop` inteiro escrito à mão neste script, e ele já divergiu do
# versionado — foi assim que o `GenericName` existiu num e não no outro.
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
fi

if [[ "${DRY_RUN:-0}" -eq 0 ]]; then
command -v desktop-file-validate >/dev/null 2>&1 \
    && desktop-file-validate "${DESKTOP_TARGET}" >/dev/null 2>&1 || true
command -v gtk-update-icon-cache >/dev/null 2>&1 \
    && gtk-update-icon-cache -q -f "${HOME}/.local/share/icons/hicolor" 2>/dev/null || true
command -v update-desktop-database >/dev/null 2>&1 \
    && update-desktop-database -q "$(dirname "${DESKTOP_TARGET}")" 2>/dev/null || true

mkdir -p "${BIN_DIR}"
cat > "${LAUNCHER}" <<LAUNCH
#!/usr/bin/env bash
# O console script do mesmo nome (pyproject.toml) abre a MESMA interface, por
# `interface.hefesto_vivo:main`. Este arquivo o SOBRESCREVE de propósito: ele
# desprende a janela do terminal (setsid+nohup) e passa pelo `run.sh`, que
# cuida do XWayland e do pixbuf antes de o Python subir.
setsid nohup "${ROOT_DIR}/interface.sh" "\$@" </dev/null >/dev/null 2>&1 &
disown 2>/dev/null || true
LAUNCH
chmod +x "${LAUNCHER}"
fi
ok

# ---------------------------------------------------------------------------
# 4b. Glyphs SVG dos botoes do DualSense
# ---------------------------------------------------------------------------
readonly GLYPHS_SRC="${ROOT_DIR}/assets/glyphs"
readonly GLYPHS_TARGET="${HOME}/.local/share/hefesto-dualsense4unix/glyphs"

if [[ "${DRY_RUN:-0}" -eq 1 && -d "${GLYPHS_SRC}" ]]; then
    _faria "copiar os glifos dos botões (assets/glyphs/*.svg) para ${GLYPHS_TARGET}/"
elif [[ -d "${GLYPHS_SRC}" ]]; then
    mkdir -p "${GLYPHS_TARGET}"
    # O `|| true` não é descuido: um `assets/glyphs/` sem nenhum `.svg` faz o
    # glob não casar, o `cp` sair 1 e o `set -e` matar a instalação AQUI —
    # depois do udev, do DKMS e do broker, e antes do daemon. Glifo é
    # acabamento; derrubar o install por causa dele trocaria um problema
    # cosmético por um real (a mesma disciplina do bloco das fontes, no 4e).
    cp -f "${GLYPHS_SRC}"/*.svg "${GLYPHS_TARGET}/" 2>/dev/null || \
        warn "nenhum glifo copiado de ${GLYPHS_SRC} — a interface cai no desenho embutido"
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
if [[ "${DRY_RUN:-0}" -eq 1 && -f "${LAUNCH_WRAPPER_SRC}" ]]; then
    _faria "instalar o wrapper de launch da Steam em ${LAUNCH_WRAPPER_TARGET}"
elif [[ -f "${LAUNCH_WRAPPER_SRC}" ]]; then
    install -Dm755 "${LAUNCH_WRAPPER_SRC}" "${LAUNCH_WRAPPER_TARGET}"
    # Diretório da materialização (o daemon regrava a cada transição; criar
    # aqui garante que o wrapper nunca falha por diretório ausente).
    mkdir -p "${HOME}/.local/state/hefesto-dualsense4unix/launch_env"
else
    warn "assets/hefesto-launch.sh ausente — wrapper de launch da Steam não instalado"
fi

# ---------------------------------------------------------------------------
# 4b-3. Curador de camadas Vulkan (ENGASGO-VULKAN-01) — DEFAULT, sem flag
# ---------------------------------------------------------------------------
# Regra da casa (08/08/2026): toda cura entra no install, sem flag. O
# `hefesto-launch` acima chama este arquivo em TODO jogo lançado (portão barato
# em `sh`, 2 ms; o interpretador só sobe quando há camada ligada de verdade) e
# não pode depender do checkout existir — por isso o módulo é MATERIALIZADO ao
# lado do wrapper, no mesmo diretório e com o mesmo tratamento.
#
# A fonte da verdade continua UMA: `integrations/camadas_vulkan.py`, que é 100%
# stdlib de propósito (padrão do `proton_pin`/`steam_launch_options`) e roda com
# o python3 do SISTEMA, sem o pacote no `sys.path`. Reinstalar atualiza a cópia.
readonly CAMADAS_SRC="${ROOT_DIR}/src/hefesto_dualsense4unix/integrations/camadas_vulkan.py"
readonly CAMADAS_TARGET="${HOME}/.local/share/hefesto-dualsense4unix/bin/hefesto-camadas"
if [[ "${DRY_RUN:-0}" -eq 1 && -f "${CAMADAS_SRC}" ]]; then
    _faria "instalar o curador de camadas Vulkan em ${CAMADAS_TARGET}"
elif [[ -f "${CAMADAS_SRC}" ]]; then
    install -Dm755 "${CAMADAS_SRC}" "${CAMADAS_TARGET}"
else
    warn "camadas_vulkan.py ausente — cura do engasgo por camada Vulkan não instalada"
fi

# ---------------------------------------------------------------------------
# 4c. Perfis default (primeira instalação copia; reinstalação preserva)
# ---------------------------------------------------------------------------
if [[ "${DRY_RUN:-0}" -eq 1 && -f "${ROOT_DIR}/scripts/install_profiles.sh" ]]; then
    _faria "instalar os perfis de fábrica em ${HOME}/.config/hefesto-dualsense4unix/profiles/ (scripts/install_profiles.sh — os SEUS perfis são preservados)"
elif [[ -f "${ROOT_DIR}/scripts/install_profiles.sh" ]]; then
    # A CHAMADA ERA NUA, e este passo é o 4c de quarenta e poucos. O
    # `install_profiles.sh` tem `set -euo pipefail` e um `exit 1` explícito
    # quando `assets/profiles_default/` não existe — então uma árvore
    # incompleta matava o instalador AQUI, levando junto o daemon (6 e 7a), o
    # kernel-watch (7b), o applet (9), o áudio (10), TODOS os passos da Steam
    # (11 a 11c) e a conferência final. É o mesmo estrago do
    # BUG-INSTALL-READONLY-USER-UNIT-DIR-01, por outra porta.
    #
    # Perfil de fábrica é acabamento: sem ele o produto abre e a pessoa cria os
    # próprios. Derrubar a instalação por causa disso troca um problema pequeno
    # por um grande — a disciplina que os vizinhos 4e (fontes) e 4f (teclado)
    # já seguem.
    bash "${ROOT_DIR}/scripts/install_profiles.sh" "${ROOT_DIR}" \
        || warn "perfis de fábrica não instalados — rode: bash scripts/install_profiles.sh"
fi

# ---------------------------------------------------------------------------
# 4d. Catalogos i18n (.mo) — copia locale/ para ~/.local/share/locale/
# ---------------------------------------------------------------------------
# FEAT-I18N-CATALOGS-01 (v3.4.0). Idempotente — re-copia sobrescreve. Se
# locale/ não existe (usuário clonou e não rodou scripts/i18n_compile.sh),
# pulamos silenciosamente e o gettext faz fallback para PT-BR hardcoded.
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
# O mapa de fábrica dá ao L3 um token de OSK desde sempre (`__TOGGLE_OSK__`
# desde 02/09/2026, quando o L3 virou alternador; antes `__OPEN_OSK__`), e o
# daemon o cumpre abrindo um teclado na tela DO SISTEMA. Só que ninguém
# instalava esse teclado: medido em 09/08/2026 na máquina dela, `command -v onboard
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
if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
    _faria "criar o link ${BIN_DIR}/hefesto-dualsense4unix -> ${VENV_DIR}/bin/hefesto-dualsense4unix"
    _faria "criar o link ${BIN_DIR}/hefesto-launch -> ${LAUNCH_WRAPPER_TARGET}"
    _faria "copiar a chave de desligar tudo para ${BIN_DIR}/hefesto-chave"
else
ln -sf "${VENV_DIR}/bin/hefesto-dualsense4unix" "${BIN_DIR}/hefesto-dualsense4unix"
# PATH-06: o wrapper de launch também entra no PATH — `which hefesto-launch`
# passa a funcionar e a Launch Option pode ser digitada à mão como
# `hefesto-launch %command%`. A string canônica do botão (WRAPPER_LAUNCH,
# formato `sh -c` com caminho absoluto) continua a mesma: funciona SEM PATH.
if [[ -x "${LAUNCH_WRAPPER_TARGET}" ]]; then
    ln -sf "${LAUNCH_WRAPPER_TARGET}" "${BIN_DIR}/hefesto-launch"
fi

# A CHAVE — `hefesto-chave off|on|estado`, o desligamento completo e reversível.
# Pedido dela, 29/08/2026: *"temos que garantir que eu possa DESLIGAR o impacto
# por completo e RELIGAR"*. Ela para, desabilita e MASCARA as units do app, põe
# a chave em disco que o daemon lê no boot (`utils/chave.py` — o furo que a
# máscara não tapa é o botão "Ligar daemon" da GUI, que cai num `Popen`) e
# esconde o atalho da dock. Nada de sudo, nada apagado: `on` desfaz tudo.
#
# É CÓPIA, e não symlink: quem desliga o produto tem de conseguir desligá-lo
# mesmo que a árvore de desenvolvimento saia do disco.
if [[ -f "${ROOT_DIR}/scripts/hefesto-chave.sh" ]]; then
    install -m 755 "${ROOT_DIR}/scripts/hefesto-chave.sh" "${BIN_DIR}/hefesto-chave"
fi
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
elif [[ "${DRY_RUN:-0}" -eq 1 ]]; then
    # ESTE É O PASSO QUE MEXE NO PRODUTO QUE ELA ESTÁ USANDO AGORA, e por isso
    # o ensaio o descreve com todas as letras: um `restart` derruba o daemon
    # vivo e, com ele, os controles conectados, por alguns segundos.
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

    # A MÁSCARA DA CHAVE VEM ANTES DO `cp`, E ISSO É A CURA DE UM ESTRAGO REAL
    # (01/09/2026). `hefesto-chave off` MASCARA as units, e uma máscara é um
    # symlink `~/.config/systemd/user/<unit>` -> `/dev/null`. O `cp -f` SEGUE o
    # symlink: a unit vai inteira para dentro do `/dev/null`, e o `cp` devolve
    # `rc=0` — o `set -e` não pega. No `hefesto-chave on` seguinte o `unmask`
    # apaga o symlink e não há arquivo por baixo: a unit do daemon DESAPARECE.
    #
    # MEDIDO: `ln -s /dev/null u; cp -f fonte u` -> `cp rc=0`, `u` ainda é
    # symlink, conteúdo vazio.
    #
    # `unmask` antes do `cp` desfaz o symlink e o `cp` escreve arquivo de
    # verdade. A chave EM DISCO continua valendo (é ela que faz o daemon
    # recusar subir) e é lida logo abaixo — desmascarar não religa nada
    # sozinho, e é de propósito: a decisão dela continua de pé.
    if command -v systemctl >/dev/null 2>&1 \
       && [[ -L "${DAEMON_UNIT_TARGET}" ]] \
       && [[ "$(readlink -f "${DAEMON_UNIT_TARGET}" 2>/dev/null)" == "/dev/null" ]]; then
        systemctl --user unmask "${DAEMON_UNIT_NAME}" >/dev/null 2>&1 || true
        rm -f "${DAEMON_UNIT_TARGET}"
        printf '      a unit estava MASCARADA (hefesto-chave off) — máscara retirada para a unit poder ser gravada\n'
    fi

    cp -f "${DAEMON_UNIT_SRC}" "${DAEMON_UNIT_TARGET}"
    systemctl --user daemon-reload >/dev/null 2>&1 || true

    # A CHAVE EM DISCO: se ela desligou o Hefesto de propósito, o daemon vai
    # RECUSAR subir (`utils/chave.py`, lido no boot do daemon) — e anunciar
    # "daemon habilitado e no ar" em cima disso seria mentira. Não se apaga a
    # chave aqui: a decisão é dela, e o comando que a desfaz está na tela.
    _CHAVE_POSTA="${XDG_CONFIG_HOME:-${HOME}/.config}/${APP_ID}/DESLIGADO-pela-chave.flag"
    if [[ -f "${_CHAVE_POSTA}" ]]; then
        warn "o Hefesto está DESLIGADO pela chave — o daemon vai recusar subir"
        printf '      a chave está em %s\n' "${_CHAVE_POSTA}"
        printf '      para religar tudo como estava:  hefesto-chave on\n'
        enable_daemon=0
    fi
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

    if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
        _faria "instalar o vigia do kernel em ${STORM_SCRIPT_TARGET}"
        _faria "copiar ${STORM_UNIT_TARGET} e habilitá-lo (log em ${HOME}/.local/state/hefesto-dualsense4unix/kernel.log)"
    elif [[ ! -f "${STORM_SCRIPT_SRC}" || ! -f "${STORM_UNIT_SRC}" ]]; then
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
    # LIDO PARA VARIÁVEL, e não por cano: sob o `set -o pipefail` deste arquivo
    # (linha 188), `cmd | grep -q` devolve 141 quando ACHA — o `grep -q` sai no
    # primeiro acerto e quem escreve morre de SIGPIPE. Numa guarda `if !` isso
    # se inverte e vira sempre verdadeira. É o mesmo defeito do `ldconfig -p`
    # de 19/08 (linha 686) e das guardas do DKMS de 01/09; `tests/unit/
    # test_o_pipefail_nao_transforma_acerto_em_falha.py` guarda a forma.
    _ext_habilitadas=$'\n'"$(gnome-extensions list --enabled 2>/dev/null || true)"$'\n'
    _ext_todas=$'\n'"$(gnome-extensions list 2>/dev/null || true)"$'\n'
    # As quebras em volta fazem o casamento ser de LINHA INTEIRA, que é o que o
    # `grep -qx` fazia: sem elas, `foo@bar.com` casaria dentro de
    # `outro-foo@bar.com.br` e o instalador diria "já habilitada" sobre a
    # extension errada.
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
# O `if bash …` de baixo fica INTEIRO, e o ensaio entra por fora, e não por um
# `elif`. A razão é medida: `test_o_alto_falante_nunca_dorme_01` procura a
# chamada com `^\s*(?:if\s+)?bash …` e um `elif` a esconde — o portão passou a
# dizer que o caminho NATIVO tinha perdido a cura do alto-falante. Não tinha; a
# forma da linha é que mudou. Régua que lê texto não tem como desempatar, e
# quem tem de ceder é quem chegou depois.
if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
    _ensaio_wireplumber nunca-dorme
else
if bash "${ROOT_DIR}/scripts/fix_wireplumber_default_source.sh" --nunca-dorme; then
    : # a mensagem do próprio script já diz se instalou ou se já valia
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
        # foi era a metade da contradição que ela leu na tela.
        #
        # OS TRÊS DESFECHOS BONS SÃO DIFERENTES ENTRE SI, e desde 01/09/2026 a
        # tela diz qual foi. O `2` nasceu naquele dia: com a webcam dela
        # desconectada, o DualSense é a ÚNICA fonte de captura com porta usável,
        # e não há o que eleger no lugar dele. Cair no `else` diria "fonte
        # padrão reeleita" sobre uma eleição que não houve.
        case "${rc:-0}" in
            2)
                printf '      drop-in do WirePlumber instalado; o DualSense é a ÚNICA fonte de\n'
                printf '      captura com porta usável — conecte um microfone/webcam, ou rode\n'
                printf '      ./install.sh --with-wireplumber-disable-mic para tirá-lo de vez\n'
                ;;
            3)
                printf '      drop-in do WirePlumber instalado (a fonte padrão ainda não é um microfone)\n'
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
    # DROPIN-AMBIGUO-01 (26/08/2026) — o carimbo do GESTO, e a razão de ele
    # existir: até hoje este ramo terminava exatamente igual a uma máquina que
    # nunca instalou nada (sem o drop-in 51 no disco), e o
    # `doctor.sh:_prefere_mic_do_dualsense` lia essa ausência como "ela
    # promoveu o mic a dedo". Um estado, dois significados — e o [OK] caía em
    # cima do defeito. `--keep-dualsense-mic` É o pedido explícito, então ele
    # deixa de ser inferido e passa a ser escrito.
    if bash "${ROOT_DIR}/scripts/fix_wireplumber_default_source.sh" --marcar-gesto-do-mic; then
        printf '      marca do gesto gravada: o doctor sabe que a ausência do drop-in 51 aqui foi pedido seu\n'
    else
        warn "não consegui gravar a marca do gesto do microfone — o doctor vai avisar que a política não está armada"
    fi
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
    if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
        _faria "curar o microfone pelo doctor (--fix-mic): pôr o perfil da placa na entrada ANALÓGICA e tirar o mudo persistido por rota de captura"
    elif [[ ! -r "${ROOT_DIR}/scripts/doctor.sh" ]]; then
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
elif [[ "${DRY_RUN:-0}" -eq 1 ]]; then
    # A CONTA STEAM É DELA, e este é o passo que escreve dentro dela — por isso
    # o ensaio diz onde fica o backup e como se volta atrás, sem que ninguém
    # tenha de procurar.
    _faria "editar TODOS os localconfig.vdf de todos os usuários Steam (deb, Flatpak e Snap): zerar SteamController_PSSupport e UseSteamControllerConfig"
    _faria "guardar um backup .bak.steam-input-<carimbo> AO LADO de cada vdf tocado, ANTES de escrever (e só quando há mudança de verdade)"
    _faria "  (para desfazer: bash scripts/disable_steam_input.sh --restore)"
    _faria "  (para ver o estado de hoje sem mudar nada: bash scripts/disable_steam_input.sh --status)"
    _faria "instalar o vigia do vdf em ${HOME}/.config/systemd/user/hefesto-steam-input-guard.{path,timer,service} e habilitá-lo (repõe o que a Steam reescrever ao sair)"
elif [[ ! -x "${ROOT_DIR}/scripts/disable_steam_input.sh" ]]; then
    warn "scripts/disable_steam_input.sh ausente ou não-executável — pulado"
else
    if bash "${ROOT_DIR}/scripts/disable_steam_input.sh" --apply; then
        printf '      Steam Input PSSupport zerado em todos os localconfig.vdf\n'
        printf '      reverter: bash scripts/disable_steam_input.sh --restore\n'
    else
        warn "disable_steam_input.sh falhou — rode: bash scripts/disable_steam_input.sh --apply"
    fi

    # Guard: path unit + timer que desfazem o que a Steam reescreve no vdf
    # (update/saída). FEAT-STEAM-INPUT-SELF-HEAL-01 (Steam Input OFF) e
    # CARONA-NO-GUARD-01 (o wrapper hefesto-launch, na carona do mesmo gatilho:
    # o instante em que a Steam grava o vdf é o instante em que ela acabou de
    # sair, que é o ÚNICO em que a reposição sobrevive). Os dois passos adiam
    # sozinhos se a Steam estiver viva. Units --user, sem sudo.
    USER_UNIT_DIR="${HOME}/.config/systemd/user"
    mkdir -p "${USER_UNIT_DIR}"
    # ASSET AUSENTE NÃO PODE MATAR O INSTALL AQUI, e não podia desde sempre —
    # este passo é o 11 de 11, e um `set -e` disparado nele levaria junto a
    # migração das Launch Options (11b), o wrapper em todos os jogos (11b-bis),
    # a sentinela (11b-ter), o pino do Proton (11c) e a conferência final. É o
    # MESMO estrago que o BUG-INSTALL-READONLY-USER-UNIT-DIR-01 causou em 25/07,
    # por outra porta: lá era a variável `readonly`, aqui é o `install -Dm644`
    # sem guarda.
    #
    # E O `sed >` ERA PIOR QUE OS DOIS `install`: o redirecionamento CRIA o
    # arquivo de destino ANTES de o `sed` rodar. Com o asset ausente, a unit
    # ficava no disco VAZIA — e uma unit vazia é aceita pelo systemd e não faz
    # nada, que é o vigia do Steam Input existindo e não vigiando. Agora o
    # arquivo final só nasce se o `sed` tiver dado certo.
    #
    # OS DOIS NOMES FICAM ESCRITOS POR EXTENSO, e não num laço com
    # `${_guard_u}`: `test_a_doc_nomeia_as_unidades_que_o_install_instala` lê as
    # unidades `--user` que este arquivo escreve procurando
    # `${USER_UNIT_DIR}/<nome>` — um laço esconde os dois nomes dela, e a régua
    # passa a dizer que a documentação não precisa mais citá-los. Medido em
    # 03/09/2026: com o laço, o portão reprovou dizendo "esperava o par .path +
    # .timer do vigia no install.sh, achei []".
    _guard_ok=1
    install -Dm644 "${ROOT_DIR}/assets/hefesto-steam-input-guard.path" \
        "${USER_UNIT_DIR}/hefesto-steam-input-guard.path" 2>/dev/null || _guard_ok=0
    install -Dm644 "${ROOT_DIR}/assets/hefesto-steam-input-guard.timer" \
        "${USER_UNIT_DIR}/hefesto-steam-input-guard.timer" 2>/dev/null || _guard_ok=0
    SENTINELA_PY="${ROOT_DIR}/src/hefesto_dualsense4unix/integrations/sentinela_do_wrapper.py"
    _guard_tmp="$(mktemp)"
    if sed -e "s#__SCRIPT__#${ROOT_DIR}/scripts/disable_steam_input.sh#g" \
        -e "s#__SENTINELA__#${SENTINELA_PY}#g" \
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
    unset _guard_ok _guard_tmp
    if systemctl --user daemon-reload 2>/dev/null \
       && systemctl --user enable --now hefesto-steam-input-guard.path hefesto-steam-input-guard.timer 2>/dev/null; then
        printf '      guard do Steam Input + wrapper habilitado (path + timer 30min)\n'
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
    if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
        _faria "trocar as Opções de Inicialização VENENOSAS de ondas antigas (IGNORE_DEVICES fixo) pela chamada do wrapper, jogo por jogo — o que VOCÊ escreveu na linha é preservado"
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

# ---------------------------------------------------------------------------
# 11b-ter. Sentinela do wrapper: REPOR quem perdeu, e anotar quem tem
# ---------------------------------------------------------------------------
# SENTINELA-WRAPPER-01 (16/08/2026), sem flag como todo o resto. O passo acima
# põe o wrapper em todo mundo; este REPÕE onde a Steam o comeu depois e ANOTA
# quem ficou com ele (~/.local/state/hefesto-dualsense4unix/wrapper-visto.json).
#
# Sem essa anotação, o produto não tem como distinguir "este jogo PERDEU o
# wrapper" de "este jogo é novo na biblioteca" — e a diferença é a frase que
# ela precisava ouvir em 15/08, quando o Pragmata teve a chamada do wrapper
# SUBSTITUÍDA por `VKD3D_CONFIG=no_upload_hvv %command%` (a Steam guarda UMA
# linha por jogo e a sobrescreve sem avisar). O daemon estava saudável, o
# perfil aceso, a luz certa — e o jogo, no Bluetooth, sem controle nenhum.
#
# POR QUE REPARAR AQUI, e não só anotar (16/08, 05h)
# --------------------------------------------------
# Este passo rodava `--relatorio`, que só OLHA. Anotar um defeito e deixá-lo em
# pé é o defeito mais caro desta casa ("a casa sabe e o produto não faz"), e o
# install é o momento em que a cura é mais barata: a Steam costuma estar
# fechada (o passo 11b acabou de escrever no vdf) e a pessoa está na frente da
# tela, esperando. O vizinho de trinta linhas abaixo já faz assim há semanas —
# o 11c não "relata" o Proton fora do pin, ele roda `--ensure` e `--lock`.
#
# O reparo PRESERVA o que já estava na linha (é o `migrate_value`, que
# PREPENDE): o Pragmata volta com o wrapper E com o `VKD3D_CONFIG` que cura o
# crash de 14/08. Trocar um defeito por outro não é conserto.
#
# Ele NUNCA fecha a Steam por conta própria: adia (rc=3) com um jogo aberto ou
# com a Steam viva, porque a Steam regrava o vdf ao sair e engoliria a edição.
# Adiar não é falha do install — é a resposta certa, e por isso sai como aviso
# com o comando na mão, nunca como erro.
#
# Idempotente por construção (`WRAPPER_PREFIX in value` pula quem já tem), e o
# que ela marcou em `jogos_sem_wrapper.txt` fica de fora: o produto não briga
# com a dona da máquina.
#
# CICLO uninstall -> install: o `--strip` do uninstall tira o wrapper de todo
# mundo, e por isso o uninstall também apaga o `wrapper-visto.json` — sem isso,
# a instalação seguinte chamaria de REGRESSÃO ("este jogo perdeu o wrapper!")
# exatamente a remoção que ela pediu. Sem a memória, toda ausência volta como
# `novo`, o reparo repõe tudo do mesmo jeito, e a memória renasce aqui.
#
# O QUE ESTE PASSO NÃO ALCANÇA (medido em 16/08 05h07, e não é hipótese)
# ----------------------------------------------------------------------
# O censo lê os TRÊS blocos `apps` do localconfig.vdf como se fossem um só, e a
# última leitura vence. Só `UserLocalConfigStore/Software/Valve/Steam/apps` é a
# árvore que a Steam usa; as outras duas foram escritas por nós em 21/07 e são
# invisíveis para ela. Com o Pragmata quebrado NA árvore viva e o wrapper
# intacto NA secundária, o censo responde "nada a fazer" e este reparo passa
# batido. O doctor no fim do install nomeia o jogo assim mesmo — a régua
# independente está em `check_arvore_canonica_do_wrapper`, e a cura da fusão é
# do dono de `steam_launch_options.py`.
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
elif [[ "${DRY_RUN:-0}" -eq 1 ]]; then
    _faria "garantir a versão de Proton VALIDADA em compatibilitytools.d (cache em ${HOME}/.cache/hefesto-dualsense4unix/proton; SHA256 obrigatório — checksum errado e NADA é extraído)"
    _faria "TRAVAR nessa versão o Proton padrão e o dos jogos já instalados nela (CompatToolMapping do config.vdf), com backup config.vdf.bak.hefesto-proton-<carimbo> ao lado"
    _faria "  (com a Steam ou um jogo aberto, a trava é ADIADA; desfazer: ./uninstall.sh, que roda o --unlock)"
    _nao_faria "sobrescrever um Proton pinado que VOCÊ já tenha instalado por fora (ProtonUp ou à mão): ele é mantido"
else
    # CONSELHO-QUE-NAO-CURA-01 (02/09/2026): a saída do `--ensure` é CAPTURADA
    # (e reimpressa inteira) porque um dos desfechos de sucesso precisa ser dito
    # em voz alta. Quando o Proton pinado já está lá SEM o nosso manifesto —
    # instalado por ProtonUp ou à mão —, o `ensure_pinned_proton` devolve
    # `already` e MANTÉM o diretório de propósito: é dado da dona da máquina.
    # A consequência é que o doctor passa a dizer, para sempre, que o manifesto
    # não confere; e o conselho que ele dava era "rode ./install.sh", que é
    # exatamente o que acabou de rodar sem mudar nada. Medido na máquina dela
    # em 02/09: install com rc=0 e o mesmo aviso de volta.
    _pp_rc=0
    _pp_saida="$(python3 "${PROTON_PIN_PY}" --ensure 2>&1)" || _pp_rc=$?
    # `[[ ]] && printf` seria uma lista que devolve 1 com a saída vazia, e o
    # `set -e` desta casa mataria o instalador aqui. Vai de `if`, de propósito.
    if [[ -n "${_pp_saida}" ]]; then printf '%s\n' "${_pp_saida}"; fi
    if [[ "${_pp_rc}" -eq 1 ]]; then
        warn "checksum do Proton NÃO bateu — passo ABORTADO (nunca instalo binário não verificado)"
    elif [[ "${_pp_rc}" -eq 2 ]]; then
        warn "sem rede e sem cache — o pin fica PENDENTE (rode ./install.sh de novo com internet); trava adiada"
    elif [[ "${_pp_rc}" -ne 0 ]]; then
        warn "garantia da versão pinada falhou (rc=${_pp_rc}) — rode: python3 ${PROTON_PIN_PY} --ensure"
    else
        # O marcador vem do detalhe do `EnsureResult`; se ele mudar de texto,
        # `tests/unit/test_conselho_que_nao_cura_01_o_proton_e_a_sobra_inerte.py`
        # reprova — a frase é contrato entre os dois arquivos, não coincidência.
        if [[ "${_pp_saida}" == *"instalação pré-existente sem manifesto"* ]]; then
            printf '      o Proton pinado JÁ estava aí, instalado por FORA (ProtonUp ou à mão), e foi MANTIDO — não sobrescrevo o que você instalou.\n'
            printf '      Por isso não dá para conferir o SHA256 do release, e o doctor vai apontar isso toda vez. Rodar este instalador de novo NÃO muda.\n'
            printf '      Para ficar com a cópia que nós verificamos: tire o diretório do compatibilitytools.d do caminho e rode o instalador outra vez.\n'
        fi
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
    if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
        # O doctor é conferência, não cura — mas o ensaio não executa NENHUM
        # roteiro de fora, e a promessa vale mais inteira do que quase inteira.
        # Quem quiser o retrato de hoje tem o comando na linha de baixo, e ele
        # é o mesmo em qualquer momento.
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
            printf '      nenhuma FALHA — as curas desta casa estão armadas\n'
        fi
    fi
fi

# ---------------------------------------------------------------------------
# Pronto
# ---------------------------------------------------------------------------
if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
    _ensaio_resumo
    exit 0
fi
printf '\n'
printf '─────────────────────────────────────────\n'
printf ' Hefesto - Dualsense4Unix instalado\n'
printf '─────────────────────────────────────────\n'
printf ' Abrir:       hefesto-dualsense4unix-gui\n'
printf ' Desinstalar: ./uninstall.sh\n'
printf '─────────────────────────────────────────\n'

# IDENTIDADE-01 (25/08/2026): o app-id mudou, e o Flatpak NÃO MIGRA ID. Para
# ele o id novo é outro aplicativo: não atualiza o antigo, instala do lado — e
# quem já usava fica com DOIS Hefestos no menu, o velho parado e o novo vivo.
# Não desinstalamos por conta própria: mexer no que a pessoa instalou, sem
# pedir, é o tipo de surpresa que esta casa não faz. Avisamos e damos o comando.
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
