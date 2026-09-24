#!/usr/bin/env bash
# doctor.sh — diagnóstico de saúde do Hefesto - DualSense4Unix.
#
# Verifica daemon, serviço, socket IPC, regras udev (incluindo a consistência do
# nome de unit do hotplug), uinput, a gravabilidade do nó de LED do DualSense
# físico (cor por-controle via sysfs, regra 77), a bandeja do sistema (o
# autostart do tray, o hospedeiro SNI e o processo), o detector de janela do autoswitch (perfil-por-jogo) e os perfis
# INALCANÇÁVEIS por ele (sem critério de janela: nunca ativam sozinhos), o sequestro
# do microfone pelo WirePlumber e o alcance do controle; a autoridade de
# exibição do co-op (NUMA-05: quem manda em lightbar/numeração agora — jogo,
# daemon ou "unknown" — e a CAUSA quando presa em unknown); reconhece também,
# no journal do kernel, a assinatura de morte por Bluetooth do 8BitDo em modo
# Switch (cascata do hid-nintendo — informativo, não gerenciamos o controle) e
# a do DualSense que o driver do kernel ABORTOU no probe (PROBE-MORTO-PS-01 —
# aborto cruzado com o estado de agora: órfão AGORA é FAIL com a cura pronta,
# aborto que já recuperou é só informação);
# e (G2) o rádio/pareamento — versão do bluez vs. a faixa aceita (piso 5.79,
# teto 5.87: o UAF em dev_disconnected), o
# hefesto-bt-agent.service, bond "meio-salvo" por dois ângulos (Connected sem
# hidraw correspondente E Paired sem Bonded) e o sink de áudio padrão mudo;
# e (BROKER-01, Onda S) o broker root hide-hidraw fd-injection — unit de
# SISTEMA ativa, ping autenticado por SO_PEERCRED, coerência do que está
# escondido com o daemon/Modo Nativo e recusa a outro uid; e (Onda W) o
# patch DKMS do rtw88_usb (dongle WiFi) — status do módulo patchado vs.
# in-tree, a assinatura do fantasma USB (device retido após disconnect
# perdido: duplicata de idVendor:idProduct, colisão de rename wlx... e -71
# sem interface de rede) e o powersave EFETIVO do WiFi via NetworkManager
# conf.d (leitura de arquivo só — nunca nmcli/rfkill).
# Saída PASS/FAIL/WARN por item.
# Marcadores ASCII (compat sanitizer de anonimato).
#
# Uso: scripts/doctor.sh [--fix] [--fix-mic] [--restaurar-hidraw-uaccess]
#                        [--quiet] [--watch-dropout] [--suggest-port]
#   --fix             aplica correções seguras: reaplica udev, instala/reseta o
#                     fix de áudio do WirePlumber e cura as camadas 1 e 2 do
#                     microfone mudo (MIC-USB-01: mute persistido por rota e
#                     perfil da placa numa entrada sem porta de captura); trava
#                     os jogos no Proton pinado (adia com a Steam aberta).
#   --fix-mic         SÓ o microfone (camadas 1 e 2) — cura, mostra o veredito
#                     das duas e sai. Rota curta de quem quer o mic de volta.
#   --restaurar-hidraw-uaccess
#                     tira o bit de OUTROS dos nós /dev/hidraw* que estão
#                     abertos a qualquer usuário local E que NENHUMA regra udev
#                     explica (0666 -> 0660). Nunca roda sozinho: NÃO entra no
#                     --fix e NÃO entra no install. Decisão dela, 07/08/2026
#                     (resposta 16 do painel). Ver RESTAURO-SO-COM-SINTOMA-01.
#   --quiet           só mostra FAIL/WARN.
#   --watch-dropout   vigia o journal do kernel e bloqueia até o primeiro sintoma
#                     de dropout USB (-71); imprime a linha e sai. (Ctrl-C para sair.)
#   --suggest-port    diz em qual controlador USB o DualSense está (diagnóstico
#                     NEUTRO). O storm -71 é port-independente (A/B comprovado):
#                     o fix real é o quirk usbcore.quirks=...gn,gn (alavanca A,
#                     preserva áudio) OU a regra 75 authorized=0 (alavanca B),
#                     não trocar de porta/Bluetooth.
#
# Exit code != 0 se houver qualquer FAIL. FEAT-DOCTOR-HEALTHCHECK-01,
# FEAT-DOCTOR-USB-DROPOUT-DIAGNOSTIC-01.

set -uo pipefail   # sem -e de propósito: cada check trata a própria falha.

readonly ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly APP_ID="hefesto-dualsense4unix"
readonly HOTPLUG_UNIT="hefesto-dualsense4unix-gui-hotplug.service"
readonly APPLET_DESKTOP="/usr/share/applications/com.vitoriamaria.HefestoDualsense4Unix.desktop"

DO_FIX=0
QUIET=0
WATCH_DROPOUT=0
SUGGEST_PORT=0
FIX_MIC=0
RESTAURAR_HIDRAW=0
for arg in "$@"; do
    case "$arg" in
        --fix)            DO_FIX=1 ;;
        --fix-mic)        FIX_MIC=1 ;;
        --restaurar-hidraw-uaccess) RESTAURAR_HIDRAW=1 ;;
        --quiet)          QUIET=1 ;;
        --watch-dropout)  WATCH_DROPOUT=1 ;;
        --suggest-port)   SUGGEST_PORT=1 ;;
        *) printf '[doctor] aviso: argumento desconhecido: %s\n' "$arg" ;;
    esac
done

FAILS=0
WARNS=0
pass() { [[ "${QUIET}" -eq 1 ]] || printf '[ OK ] %s\n' "$*"; }
fail() { printf '[FAIL] %s\n' "$*"; FAILS=$((FAILS + 1)); }
warn() { printf '[WARN] %s\n' "$*"; WARNS=$((WARNS + 1)); }
info() { [[ "${QUIET}" -eq 1 ]] || printf '       %s\n' "$*"; }
hdr()  { [[ "${QUIET}" -eq 1 ]] || printf '\n== %s ==\n' "$*"; }

# ---------------------------------------------------------------------------
# BG-06 (25/08/2026) — O CONSELHO IMPOSSÍVEL.
#
# Trinta e três frases deste exame mandavam "rode ./install.sh" como gesto, e
# o `install.sh` só existe para quem CLONOU o repositório. A tabela é da T-03
# (medida em 23/08/2026, por formato de pacote):
#
#   checkout ............................. tem o instalador: SIM
#   .deb ................................. tem o instalador: não (leva os scripts)
#   Flatpak/AppImage/Arch/Fedora/Nix ..... tem o instalador: não (nem os scripts)
#
# Em CINCO dos SEIS formatos a pessoa via a frase com MAIS frequência — porque
# as coisas realmente faltavam — e a instrução que recebia era a única que ela
# não tinha como cumprir.
#
# ONDE ESTE RACIOCÍNIO JÁ MORAVA: `esta_instalacao_e_um_checkout()` e
# `como_atualizar_esta_instalacao()`, em
# `src/hefesto_dualsense4unix/app/actions/daemon_actions.py`, escritas na T-03
# e já usadas pela aba Sistema. Este script é shell e não importa Python: a
# lógica NASCE aqui de novo. É DUPLICAÇÃO DECLARADA, não descuido — está
# escrita no relatório da BG-06 para quem for resolvê-la. A régua das duas é a
# mesma pergunta, e é a pergunta inteira: existe um instalador ao lado deste
# código?
#
# NO CHECKOUT A TELA NÃO MUDA. `conselho_de_instalacao` devolve exatamente
# "rode ./install.sh" (mais o que o chamador passar) e `so_no_checkout` some
# fora dele: o texto novo aparece SÓ onde o texto velho era impossível.
esta_instalacao_e_um_checkout() {
    [[ -f "${ROOT_DIR}/install.sh" ]]
}

#: O que dizer a quem NÃO tem checkout, quando não há gesto melhor. A T-03
#: redigiu este mínimo e o carimbou PROVISÓRIO (aguarda o olho dela): ele é
#: honesto e universal, mas não nomeia o gesto do formato — um `flatpak
#: update`, um `apt upgrade`. Nomear é texto novo de tela, e isso é decisão
#: dela. É a MESMA frase que já está no produto, palavra por palavra — não uma
#: segunda redação com o mesmo sentido, que é como duas verdades começam.
#: `tests/unit/test_bg06_o_grau_e_o_conselho_que_serve_para_esta_instalacao.py`
#: compara as duas e reprova se divergirem.
#:
#: ELA É UM GESTO, não uma explicação, e isso é de propósito: entra no MESMO
#: lugar da frase onde entrava "rode ./install.sh" ("…, ou <isto>", "traga o
#: alvo: <isto>"). A primeira redação era uma oração inteira ("este passo é do
#: ./install.sh, que só existe…") e quebrava a gramática de sete frases —
#: visto renderando as 33 lado a lado, não lendo o fonte.
_CONSELHO_GESTO_GENERICO="atualize o Hefesto pelo mesmo caminho por onde você o instalou"

# ---------------------------------------------------------------------------
# BG-06b (26/08/2026) — O GESTO GANHA NOME, POR FORMATO.
#
# A frase acima é honesta e universal, e é o ÚLTIMO degrau — não o único. Quem
# instalou por Flatpak, Arch, Fedora, Debian ou Nix pode receber o gesto com
# nome, e recebe.
#
# O QUE ISTO NÃO FAZ: adivinhar o formato pela distribuição. "Tem `apt`, logo
# é `.deb`" está errado para todo AppImage e todo `pip install --user` numa
# máquina Debian — e gesto errado é pior que gesto vago. A pergunta é sempre
# sobre ESTE arquivo no disco: quem é o dono dele?
#
# A cópia em Python é `integrations/storm_doctor.GESTO_DE_ATUALIZAR` +
# `formato_desta_instalacao`. DUPLICAÇÃO DECLARADA, pelo mesmo motivo de
# sempre (este script é shell e não importa Python), e com o mesmo portão em
# cima: `test_bg06_…::test_o_gesto_e_nomeado_por_formato` compara as duas nos
# cinco formatos e reprova se divergirem.
#
# **PROVISÓRIO — decisão dela**: os cinco gestos nomeados são texto novo de
# tela. Carimbo herdado da T-03, que redigiu a genérica e parou aqui de
# propósito.

#: Qual gerenciador de pacotes assume um caminho. `$1` é o caminho; ecoa
#: `arch`/`debian`/`fedora` ou NADA. É uma pergunta ao disco, não um palpite:
#: AppImage e instalação à mão não são de ninguém, e caem na genérica.
_dono_do_arquivo() {
    local alvo="${1:?}"
    if command -v pacman >/dev/null 2>&1 && pacman -Qo "${alvo}" >/dev/null 2>&1; then
        printf 'arch'
    elif command -v dpkg >/dev/null 2>&1 && dpkg -S "${alvo}" >/dev/null 2>&1; then
        printf 'debian'
    elif command -v rpm >/dev/null 2>&1 && rpm -qf "${alvo}" >/dev/null 2>&1; then
        printf 'fedora'
    fi
}

#: O formato desta instalação em uma palavra. `$1` é o caminho do código a
#: interrogar (default: este script) — é parâmetro, e não variável de
#: ambiente, porque é assim que a bancada planta um `/nix/store` de mentira
#: sem abrir uma porta dos fundos no produto.
#:
#: A ordem é uma ESCADA, e cada degrau é medição: checkout (o `install.sh` ao
#: lado), flatpak (o `/.flatpak-info` que o próprio flatpak monta), nix (o
#: código dentro do `/nix/store`), o dono do arquivo, e a genérica.
_formato_desta_instalacao() {
    local alvo="${1:-${BASH_SOURCE[0]}}" dono
    if esta_instalacao_e_um_checkout; then
        printf 'checkout'
        return 0
    fi
    local marca_flatpak="${HEFESTO_MARCA_SANDBOX:-/.flatpak-info}"
    if [[ -f "${marca_flatpak}" || -n "${FLATPAK_ID:-}" ]]; then
        printf 'flatpak'
        return 0
    fi
    if [[ "${alvo}" == /nix/store/* ]]; then
        printf 'nix'
        return 0
    fi
    dono="$(_dono_do_arquivo "${alvo}")"
    printf '%s' "${dono:-desconhecido}"
}

#: O gesto de atualizar com nome, ou a genérica. `$1` é repassado ao
#: `_formato_desta_instalacao`.
#:
#: Cada gesto é UM GESTO ("rode X"), pela mesma razão da genérica: ele entra no
#: MESMO lugar da frase ("…, ou <isto>", "traga o alvo: <isto>"), e uma oração
#: inteira ali quebra a gramática de quem a hospeda.
_gesto_de_atualizar() {
    case "$(_formato_desta_instalacao "${1:-}")" in
        flatpak) printf 'rode flatpak update' ;;
        arch)    printf 'rode sudo pacman -Syu' ;;
        fedora)  printf 'rode sudo dnf upgrade' ;;
        debian)  printf 'rode sudo apt upgrade' ;;
        nix)     printf 'rode nix profile upgrade' ;;
        *)       printf '%s' "${_CONSELHO_GESTO_GENERICO}" ;;
    esac
}
# ---------------------------------------------------------------------------

# O gesto de instalar/reparar que serve para ESTA máquina.
#   $1 — o que vem DEPOIS de `./install.sh` no checkout (as flags). Opcional.
#   $2 — o CAMINHO de um reparador que os pacotes levam e que refaz este passo
#        (o `install-host-udev.sh`, hoje). Opcional — e MEDIDO, não presumido:
#        só entra na frase se o arquivo existir nesta máquina. É a mesma
#        pergunta do checkout, um andar abaixo: quem instalou por Flatpak não
#        tem `/usr/share/hefesto-dualsense4unix` nenhum, e mandá-lo ali seria
#        trocar um conselho impossível por outro.
#   $3 — ressalva que anda JUNTO do reparador, e só com ele (opcional). O
#        `install-host-udev.sh` não faz tudo o que o instalador faz — não
#        instala os timers de resiliência, por exemplo —, e a ressalva não
#        pode aparecer numa máquina que nem o reparador tem. Amarrá-la ao
#        ramo é o que impede a frase de prometer o que ninguém vai rodar.
conselho_de_instalacao() {
    local flags="${1:-}" reparador="${2:-}" ressalva="${3:-}"
    if esta_instalacao_e_um_checkout; then
        printf 'rode ./install.sh%s' "${flags:+ ${flags}}"
    elif [[ -n "${reparador}" && -f "${reparador}" ]]; then
        printf 'rode o reparador que veio no seu pacote: sudo %s%s' \
            "${reparador}" "${ressalva:+ ${ressalva}}"
    else
        # BG-06b: a genérica deixou de ser o único destino deste ramo — ela é
        # o último degrau de `_gesto_de_atualizar`, e continua sendo a resposta
        # de quem não tem dono (AppImage, instalação à mão).
        printf '%s' "$(_gesto_de_atualizar)"
    fi
}

# Um aparte que SÓ faz sentido para quem tem o repositório: o nome de uma flag,
# o número de um passo do instalador. Fora do checkout devolve NADA — é o que
# mantém a frase de hoje intacta na máquina dela e limpa nas outras.
#
# ELE JÁ VEM COM O ESPAÇO NA FRENTE, e por isso o aparte NÃO pode começar por
# pontuação: `"; opt-out: --no-dkms"` sai como "install.sh ; opt-out", com o
# espaço solto antes do ponto e vírgula. Medido em 25/08/2026 renderando as 33
# frases em paralelo, que é o único jeito de ver isto — no fonte não aparece.
# Comece o aparte por travessão ou por parêntese.
so_no_checkout() {
    esta_instalacao_e_um_checkout || return 0
    printf ' %s' "${1:-}"
}
# ---------------------------------------------------------------------------

runtime_socket() {
    printf '%s/%s/%s.sock' "${XDG_RUNTIME_DIR:-/run/user/$(id -u)}" "${APP_ID}" "${APP_ID}"
}

# COMPAT BLUEZ-586-CTL-01 (medido 22/07 nesta máquina): o bluetoothctl 5.86
# ficou MUDO no modo one-shot (`bluetoothctl list` imprime NADA, rc=0 — com
# ou sem TTY, com ou sem --timeout), enquanto o modo interativo funciona e o
# daemon está são no D-Bus. Esta função SOMBREIA o binário para todos os ~25
# usos deste script: roda o comando via modo interativo, tira ANSI/prompt e
# só emite o que vem DEPOIS do eco do próprio comando (o arranque imprime
# eventos [NEW]/SupportedUUIDs que não são resposta). Sem bluetoothctl no
# PATH, degrada para o comportamento antigo (command retorna 127 e os checks
# tratam vazio como "sem dados", como sempre trataram).
bluetoothctl() {
    command -v bluetoothctl >/dev/null 2>&1 || return 127
    printf '%s\nquit\n' "$*" | command timeout 8 bluetoothctl 2>/dev/null \
        | sed -e $'s/\x1b\\[[0-9;]*[A-Za-z]//g' -e 's/\r//g' -e 's/^\[bluetoothctl\]> //' \
        | awk -v cmd="$*" 'BEGIN{seen=0} $0==cmd{seen=1;next} !seen{next} $0=="quit"{exit} /^\[/{next} {print}'
}

check_daemon_installed() {
    local found
    found="$(command -v hefesto-dualsense4unix 2>/dev/null || true)"
    [[ -z "${found}" && -e "${HOME}/.local/bin/hefesto-dualsense4unix" ]] && found="${HOME}/.local/bin/hefesto-dualsense4unix"
    [[ -z "${found}" && -e /usr/bin/hefesto-dualsense4unix ]] && found="/usr/bin/hefesto-dualsense4unix"
    if [[ -n "${found}" ]]; then
        pass "daemon/CLI instalado (${found})"
    else
        fail "CLI hefesto-dualsense4unix não encontrado — $(conselho_de_instalacao --native)"
    fi
}

# VERDE-MENTIROSO-01 (19/08/2026). Duas dependências OBRIGATÓRIAS não tinham
# régua aqui — `grep -n "hidapi\|rsvg" scripts/doctor.sh` dava ZERO —, e o
# instalador só passou a garanti-las em 19/08. Quem instalou ANTES disso, ou
# instalou por pacote da distro, segue com verde mentiroso na conferência: o
# doctor diz que está tudo bem e o produto não abre aparelho nenhum.
#
# As duas perguntam pelo EFEITO, nunca pelo nome do pacote — é a mesma
# disciplina que o `install.sh` declara na `_dep_presente`, e a que sobrevive a
# distro que empacota com outro nome.
#
# A ORDEM DOS CANDIDATOS (INSTALL-UNIVERSAL, 18/09/2026): a venv do produto é a
# que o install cria AO LADO deste script (`VENV_DIR="${ROOT_DIR}/.venv"`, a
# mesma do lançador em ~/.local/bin), e ela vem PRIMEIRO. Aqui havia um
# `${HOME}/.venv/bin/python` antes dela — numa máquina de outra pessoa, é o
# nome mais comum de venv que existe, e qualquer uma servia de "python do
# produto": sem `platformdirs`, sem `gi`, e o check respondia sobre ela. O
# `/opt/...` é a venv que o `.deb` traz (`scripts/build_deb.sh`, FINAL_VENV):
# lá este script mora longe dela e não há `.venv` ao lado.
_python_do_produto() {
    local py
    for py in "${ROOT_DIR}/.venv/bin/python" \
              "${HOME}/.local/share/hefesto-dualsense4unix/venv/bin/python" \
              "/opt/hefesto-dualsense4unix/venv/bin/python"; do
        [[ -x "${py}" ]] && { printf '%s\n' "${py}"; return 0; }
    done
    command -v python3 2>/dev/null
}

check_libhidapi() {
    local py; py="$(_python_do_produto)"
    [[ -z "${py}" ]] && { warn "sem python para conferir a libhidapi"; return; }
    # O `hidapi` do pip é wrapper CFFI e NÃO traz o `.so`: ele percorre
    # `libhidapi-hidraw.so[.0]` e `libhidapi-libusb.so[.0]` até um abrir. Sem a
    # biblioteca do sistema o `import pydualsense` levanta OSError e NENHUM
    # aparelho sobe — é falha, não aviso.
    if "${py}" -c "import ctypes,sys
for so in ('libhidapi-hidraw.so.0','libhidapi-libusb.so.0','libhidapi-hidraw.so','libhidapi.so.0'):
    try:
        ctypes.CDLL(so); sys.exit(0)
    except OSError:
        pass
sys.exit(1)" 2>/dev/null; then
        pass "libhidapi presente (o backend do controle consegue abrir aparelho)"
    else
        fail "libhidapi AUSENTE — sem ela o backend não abre NENHUM aparelho (o pydualsense faz dlopen dela; a wheel do pip não traz o .so); a libhidapi entra por default no instalador desta casa: $(conselho_de_instalacao)"
    fi
}

check_loader_svg() {
    local py; py="$(_python_do_produto)"
    [[ -z "${py}" ]] && { warn "sem python para conferir o loader SVG"; return; }
    # A pergunta certa não é "o pacote está instalado?", e sim "o gdk-pixbuf sabe
    # ler SVG?" — que é o que a interface faz 38 vezes (os glifos dos botões) e
    # mais uma no ícone da bandeja. ARMADILHA DE NOME já paga por esta casa: o
    # pacote de EXECUÇÃO é o loader (`librsvg2-common` no Debian); o
    # `librsvg2-bin` é o `rsvg-convert`, ferramenta de build.
    # MEDIDO em 19/08/2026, e a primeira versão desta régua ERRAVA: perguntar
    # `Pixbuf.get_formats()` lê o CACHE do gdk-pixbuf (`loaders.cache`), não o
    # loader. Com o `libpixbufloader-svg.so` fora do alcance do processo, o
    # catálogo continuava dizendo que sabe ler SVG — verde sobre uma máquina em
    # que o ícone da bandeja sairia vazio. Agora a régua CARREGA um SVG de
    # verdade, que é o que a interface faz 38 vezes.
    if "${py}" -c "import gi,sys,tempfile,os
gi.require_version('GdkPixbuf','2.0')
from gi.repository import GdkPixbuf
svg = b'<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"8\" height=\"8\"><rect width=\"8\" height=\"8\"/></svg>'
fd, caminho = tempfile.mkstemp(suffix='.svg')
try:
    os.write(fd, svg); os.close(fd)
    pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(caminho, 8, 8, True)
    sys.exit(0 if pb is not None else 1)
except Exception:
    sys.exit(1)
finally:
    os.unlink(caminho)" 2>/dev/null; then
        pass "loader SVG do gdk-pixbuf presente (os glifos e o ícone da bandeja desenham)"
    else
        fail "loader SVG AUSENTE — o ícone some da barra e os 38 glifos dos botões saem vazios (BUG-TRAY-ICONE-INVISIVEL-01). Instale o loader do librsvg (Debian: librsvg2-common), ou $(conselho_de_instalacao)"
    fi
}

check_service() {
    command -v systemctl >/dev/null 2>&1 || { warn "systemctl ausente — não checo o serviço"; return; }
    local state
    state="$(systemctl --user is-active "${APP_ID}.service" 2>/dev/null || true)"
    if [[ "${state}" == "active" ]]; then
        pass "serviço ${APP_ID}.service ativo"
    elif systemctl --user cat "${APP_ID}.service" >/dev/null 2>&1; then
        warn "serviço instalado mas ${state:-inativo} (start: systemctl --user start ${APP_ID}.service, ou abra a GUI)"
    else
        warn "serviço não instalado (autostart é opt-in — $(conselho_de_instalacao --enable-autostart))"
    fi
}

check_socket() {
    local sock; sock="$(runtime_socket)"
    if [[ -S "${sock}" ]]; then
        pass "socket IPC presente"
    else
        warn "socket IPC ausente (daemon parado?): ${sock}"
    fi
}

check_udev() {
    # DOCTOR-UDEV-CANONICAL-FIX-01 + COR-06/STATUS-07: o conjunto CANÔNICO é o
    # que o install_udev.sh põe SEM FLAG: 70, 71-uhid, 71-uinput, 72, 76
    # (touchpad-ignore), 77 (LEDs graváveis) e 78 (motion fora do joystick).
    # A ÚNICA opt-in é a 75 (audio-off, --disable-usb-audio) — fora da contagem.
    # As regras 73/74 (hotplug-GUI) foram REMOVIDAS por alimentarem a
    # re-enumeração do storm -71 (install_udev.sh faz `rm -f`). Antes o doctor
    # exigia 5 (70-74) e reportava "3/5 — faltam 73 74" PARA SEMPRE após um
    # install limpo (falso-negativo permanente); depois chamou a 76 de opt-in
    # (falso: é default desde o install) e ignorou 77/78 — sem a 77 o nó de LED
    # não é gravável e a cor por-controle degrada p/ hidraw em silêncio.
    # Regra da casa: um item no install = um check no doctor.
    #
    # NOTA DATADA 06/08/2026: a lista tinha caducado de novo, e a própria regra
    # escrita acima é que apanhou. O `install_udev.sh` instala SEM FLAG também a
    # 82 (nosniff do Pro), a 83 (snapshot de bonds na borda udev) e a 84
    # (variante do clone 8BitDo) — linhas 132, 133 e 138 — e nenhuma das três era
    # conferida aqui. Quem instalasse antes delas existirem ficava sem as três,
    # em silêncio, e o doctor dava [OK]. As três entram na contagem.
    #
    # NOTA DATADA 09/08/2026 (OQ-6): entra a 72-hefesto-touchpad-motion-uaccess,
    # que o `install_udev.sh` também põe SEM FLAG. Ela é a que dá ACL da sessão
    # aos nós de ENTRADA do touchpad e dos sensores de movimento — a regra do
    # sistema (70-uaccess.rules) só marca `ID_INPUT_JOYSTICK`, e esses dois nós
    # são `ID_INPUT_TOUCHPAD`/`ID_INPUT_ACCELEROMETER`. A presença do ARQUIVO é
    # o que se cobra aqui; o EFEITO (a ACL existir no nó vivo) é outra pergunta,
    # e tem função própria — `check_input_uaccess`. As duas são necessárias:
    # a regra pode estar no disco e não ter pegado (ver o comentário de lá).
    local r found=0 missing=""
    local rules=(70-ps5-controller.rules 71-uhid.rules 71-uinput.rules
                 72-ps5-controller-autosuspend.rules
                 72-hefesto-touchpad-motion-uaccess.rules
                 76-dualsense-touchpad-libinput-ignore.rules
                 77-dualsense-leds.rules
                 78-dualsense-motion-not-joystick.rules
                 79-external-controller-leds.rules
                 80-motion-joydev-hide.rules
                 81-hefesto-usb-power.rules
                 81-hefesto-usb-host-power.rules
                 82-nintendo-pro-nosniff.rules
                 83-hefesto-bond-snapshot.rules
                 84-nintendo-pro-variant.rules)
    local total=${#rules[@]}
    for r in "${rules[@]}"; do
        if [[ -e "/etc/udev/rules.d/${r}" || -e "/usr/lib/udev/rules.d/${r}" ]]; then
            found=$((found + 1))
        else
            missing+=" ${r}"
        fi
    done
    if [[ "${found}" -eq "${total}" ]]; then
        pass "${total} regras udev canônicas presentes (70/71-uhid/71-uinput/72-autosuspend/72-uaccess/76/77/78/79/80/81-power/81-host/82/83/84)"
    elif [[ "${found}" -eq 0 ]]; then
        fail "nenhuma regra udev instalada — rode: sudo bash scripts/install_udev.sh"
    else
        warn "regras udev incompletas (${found}/${total}) — faltam:${missing} — rode: sudo bash scripts/install_udev.sh"
    fi
    # 73/74 (hotplug-GUI) foram DESCONTINUADAS (amplificavam o storm -71). Se
    # sobraram de uma instalação antiga, avisa para limpar.
    for r in 73-ps5-controller-hotplug.rules 74-ps5-controller-hotplug-bt.rules; do
        if [[ -e "/etc/udev/rules.d/${r}" || -e "/usr/lib/udev/rules.d/${r}" ]]; then
            warn "${r}: regra descontinuada presente (amplificava o storm -71) — remova: sudo bash scripts/install_udev.sh"
        fi
    done
    # REGRA-COLA SEM O ALVO (22/08/2026) — a metade B que nenhum portão media.  # (noqa-acento: verbo medir, imperfeito)
    #
    # O estudo de 07/08 (cobertura do install, item 9) mediu isto: o portão de
    # paridade e este doctor davam `[OK]` para as regras 82 e 83 olhando só se o
    # ARQUIVO existe, enquanto o alvo do `RUN+=` de cada uma não existia em
    # empacotamento nenhum. Regra-cola sem alvo é enfeite: a 82 não tira o Pro
    # genuíno do sniff na borda, e a 83 não fotografa bond nenhum — que é a cura
    # do crash que comeu 2 dos 3 pareamentos dela em 24/07.
    #
    # O `TEST==` que as duas regras carregam desde 22/08 faz a regra órfã ficar
    # INERTE em vez de falhar a cada conexão Bluetooth. Este bloco é a VOZ que
    # falta ao silêncio: inerte sem ninguém dizendo é o defeito de novo.
    #
    # OS DOIS PARES ESTÃO ESCRITOS POR EXTENSO, um `[[ -f ]]` literal cada, em
    # vez de um laço sobre uma lista — pela mesma razão que o
    # `_dono_das_regras_udev` logo acima: a guarda de carona do
    # `scripts/check_packaging_parity.sh` procura o NOME do script numa linha de
    # teste de arquivo, e o que não está escrito portão nenhum lê. Escrito com
    # variável, este bloco reprovava a paridade (medido em 22/08) — o gate via o
    # doctor citar dois scripts que o .deb não empacota e não achava a guarda.
    if { [[ -e /etc/udev/rules.d/82-nintendo-pro-nosniff.rules ]] \
         || [[ -e /usr/lib/udev/rules.d/82-nintendo-pro-nosniff.rules ]]; } \
       && [[ ! -f /usr/local/lib/hefesto-dualsense4unix/bt_nosniff_now.sh ]]; then
        warn "82-nintendo-pro-nosniff.rules instalada e o alvo do RUN+= dela NÃO (/usr/local/lib/hefesto-dualsense4unix/bt_nosniff_now.sh) — a regra fica inerte (o TEST== dela não acha o alvo) e o Pro genuíno não perde o sniff na borda da conexão; traga o alvo: $(conselho_de_instalacao "" "/usr/share/hefesto-dualsense4unix/scripts/install-host-udev.sh")"
    fi
    if { [[ -e /etc/udev/rules.d/83-hefesto-bond-snapshot.rules ]] \
         || [[ -e /usr/lib/udev/rules.d/83-hefesto-bond-snapshot.rules ]]; } \
       && [[ ! -f /usr/local/lib/hefesto-dualsense4unix/bt_bonds_snapshot.sh ]]; then
        warn "83-hefesto-bond-snapshot.rules instalada e o alvo do RUN+= dela NÃO (/usr/local/lib/hefesto-dualsense4unix/bt_bonds_snapshot.sh, o ExecStart da unit de snapshot) — a regra fica inerte e o salva-vidas de bonds não grava nada quando um controle Bluetooth chega; traga o alvo: $(conselho_de_instalacao "" "/usr/share/hefesto-dualsense4unix/scripts/install-host-udev.sh")"
    fi
}

# True (0) se o snd-usb-audio AINDA está bindado em alguma interface de áudio
# (bInterfaceClass==01) de um DualSense (VID 054c). Lê os nós de interface USB em
# /sys e segue o symlink `driver`. Usado para validar se a regra 75 pegou.
dualsense_audio_bound() {
    local iface base vid cls drv
    for iface in /sys/bus/usb/devices/*:*.*; do
        [[ -r "${iface}/bInterfaceClass" ]] || continue
        cls="$(cat "${iface}/bInterfaceClass" 2>/dev/null)"
        [[ "${cls}" == "01" ]] || continue
        base="${iface%:*}"   # /sys/bus/usb/devices/3-2:1.0 -> /sys/bus/usb/devices/3-2
        vid="$(cat "${base}/idVendor" 2>/dev/null)"
        [[ "${vid}" == "054c" ]] || continue
        drv="$(basename "$(readlink -f "${iface}/driver" 2>/dev/null)" 2>/dev/null)"
        [[ "${drv}" == "snd-usb-audio" ]] && return 0
    done
    return 1
}

# FEAT-DSX-DEFINITIVE-FIX-01 §7.5: a regra 75 (OPT-IN) desliga o áudio USB do
# DualSense (authorized=0 + unbind do snd-usb-audio) para matar o gatilho do
# storm -71. Aqui validamos que, SE instalada, ela realmente pegou. Não alarmamos
# quem QUER o mic do DualSense (HEFESTO_DUALSENSE4UNIX_DUALSENSE_MIC_INTENDED=1)
# nem o caminho padrão (75 ausente = áudio preservado).
check_usb_audio_off() {
    local rule75=""
    if [[ -e /etc/udev/rules.d/75-ps5-controller-disable-usb-audio.rules ]]; then
        rule75=/etc/udev/rules.d/75-ps5-controller-disable-usb-audio.rules
    elif [[ -e /usr/lib/udev/rules.d/75-ps5-controller-disable-usb-audio.rules ]]; then
        rule75=/usr/lib/udev/rules.d/75-ps5-controller-disable-usb-audio.rules
    fi

    local mic_intended=0
    case "${HEFESTO_DUALSENSE4UNIX_DUALSENSE_MIC_INTENDED:-}" in
        1|true|yes|TRUE|YES) mic_intended=1 ;;
    esac

    # Caminho padrão: regra opt-in não instalada → áudio preservado, sem alarme.
    [[ -z "${rule75}" ]] && return

    if [[ "${mic_intended}" -eq 1 ]]; then
        # Config contraditória, mas a usuária pediu áudio — não alarmar (info).
        info "regra 75 (áudio USB off) instalada, mas DUALSENSE_MIC_INTENDED=1 pede o mic — contraditório; para ter o mic remova a 75 (uninstall) ou reinstale sem --disable-usb-audio"
        return
    fi

    # Regra instalada e mic não desejado: o áudio USB deve estar desligado.
    if dualsense_audio_bound; then
        warn "regra 75 instalada mas snd-usb-audio ainda bindado no áudio do DualSense — a regra não pegou; replugue o controle (ou: sudo bash scripts/install_udev.sh --disable-usb-audio)"
    elif command -v lsusb >/dev/null 2>&1 && lsusb 2>/dev/null | grep -qiE '054c'; then
        pass "regra 75 ativa — áudio USB do DualSense desligado (sem snd-usb-audio nas interfaces de áudio)"
    else
        info "regra 75 instalada; DualSense não conectado via USB agora — replugue para validar o desligamento do áudio"
    fi
}

# DOCTOR-UINPUT-ACESSO-01: existir NÃO basta. O nó nasce root-only e quem o torna
# usável é a regra udev (uaccess). Checar só `-e` dava PASS com o daemon incapaz de
# criar vpad nenhum — falso-positivo justamente no caso que o install passou a
# cobrir (`udevadm trigger --subsystem-match=misc`, sem o qual a regra só valia no
# próximo boot).
_check_node_gravavel() {
    local node="$1" modulo="$2" para_que="$3"
    if [[ ! -e "${node}" ]]; then
        fail "${node} ausente — rode: sudo modprobe ${modulo} (ou reinstale as regras udev)"
        return
    fi
    if [[ -w "${node}" ]]; then
        _vpad09_qualifica_acesso "${node}" "${para_que}"
    else
        fail "${node} existe mas SEM permissão para o seu usuário — ${para_que} não vai funcionar. Rode: sudo bash scripts/install_udev.sh"
    fi
}

# VPAD-09: gravável AGORA pode ser só a ACL do uaccess, que o logind aplica NO
# LOGIN — depois do daemon de sessão subir (corrida perdida ao vivo em 21/07:
# EACCES no boot, vpad nenhum). O acesso determinístico é o dono de grupo
# 'hefesto' (regras 71-*), aplicado na criação do nó, antes de qualquer login.
_vpad09_qualifica_acesso() {
    local node="$1" para_que="$2" grp
    grp="$(stat -c '%G' "${node}" 2>/dev/null || true)"
    if [[ "${grp}" != "hefesto" ]]; then
        warn "${node} gravável só pela ACL do login — no boot o daemon pode perder a corrida contra o logind (VPAD-09). Rode: sudo bash scripts/install_udev.sh"
    elif id -nG 2>/dev/null | tr ' ' '\n' | grep -qx hefesto; then
        pass "${node} presente e gravável (${para_que}; grupo hefesto ativo — sem corrida no boot)"
    else
        info "${node} com grupo hefesto, mas sua sessão ainda não está no grupo (vale no próximo login) — até lá o acesso é a ACL do login (VPAD-09)"
    fi
}

check_uinput() {
    _check_node_gravavel /dev/uinput uinput "gamepad virtual"
}

# SPRINT-UHID-VPAD-01: sem /dev/uhid o gamepad virtual cai no uinput, que não tem
# hidraw — e aí a vibração não funciona com a máscara DualSense. É degradação, não
# quebra: warn, nunca fail.
check_uhid() {
    if [[ ! -e /dev/uhid ]]; then
        warn "/dev/uhid ausente — o controle virtual funciona, mas a vibração só vale com a máscara Xbox 360. Rode: sudo modprobe uhid"
        return
    fi
    if [[ -w /dev/uhid ]]; then
        _vpad09_qualifica_acesso /dev/uhid "vibração nas duas máscaras"
    else
        warn "/dev/uhid existe mas SEM permissão para o seu usuário — a vibração só vai funcionar com a máscara Xbox 360. Rode: sudo bash scripts/install_udev.sh"
    fi
}

# A CONTRAPRESSÃO DO UHID (RADIO-AFOGADO-02, opt-in `--uhid-contrapressao`;
# conferida pelo doctor desde a INSTALL-E-UNINSTALL-DO-RADIO-01, 23/09/2026).
# O pedido é a conf em /etc/modprobe.d; o que vale é o parâmetro do módulo
# CARREGADO. Três respostas: ligada; pedida e desligada a quente (o uninstall a
# desliga, e um rearme que falhou a deixa assim até o boot); e pedida com o de
# fábrica carregado — que é «entra no próximo boot» num kernel conferido e
# «não vale neste kernel» fora da lista do `patch/BASELINE` (o DKMS pula ali,
# de propósito). Sem o pedido, nada a conferir. Ganchos `HEFESTO_DOCTOR_UHID_*`
# e `HEFESTO_DOCTOR_KERNEL`: a régua não depende do uhid de quem a roda.
check_uhid_contrapressao() {
    local conf="${HEFESTO_DOCTOR_UHID_CONF:-/etc/modprobe.d/hefesto-uhid.conf}"
    local param="${HEFESTO_DOCTOR_UHID_PARAM:-/sys/module/uhid/parameters/backpressure}"
    local baseline="${ROOT_DIR}/assets/dkms/uhid/patch/BASELINE"
    local kernel="${HEFESTO_DOCTOR_KERNEL:-$(uname -r)}" validados="" um valor
    [[ -f "${conf}" ]] || return 0
    if [[ -r "${param}" ]]; then
        valor="$(cat "${param}" 2>/dev/null || true)"
        if [[ "${valor}" == "1" || "${valor}" == "Y" ]]; then
            pass "contrapressão do uhid ligada (o rádio cheio diz «espere» em vez de perder o comando)"
        else
            warn "a contrapressão do uhid foi pedida e está DESLIGADA agora (${valor:-?}) — ligue sem recarregar o uhid: echo 1 | sudo tee ${param}"
        fi
        return
    fi
    if [[ -r "${baseline}" ]]; then
        validados="$(sed -n 's/^KERNELS_VALIDADOS=//p' "${baseline}" | head -1 | tr ',' ' ')"
        for um in ${validados}; do
            if [[ "${kernel}" == "${um}" || "${kernel}" == "${um}"-* ]]; then
                info "a contrapressão do uhid foi pedida e entra no PRÓXIMO BOOT (o uhid de fábrica está carregado; recarregá-lo derrubaria todo HID por Bluetooth)"
                return
            fi
        done
        warn "a contrapressão do uhid foi pedida, mas o kernel ${kernel} não está entre os conferidos (${validados:-nenhum}) — o uhid de fábrica segue, e o pedido não vale neste kernel"
        return
    fi
    info "a contrapressão do uhid foi pedida e o uhid carregado é o de fábrica — não sei dizer se o patchado entra no próximo boot (sem o patch/BASELINE nesta instalação)"
}

# O hid_playstation é quem entrega lightbar e LED de jogador pelo sysfs (regra 77) e
# quem faz o gamepad virtual virar um DualSense de verdade (uhid). Sem ele o daemon
# funciona, mas essas features somem — por isso warn, não fail.
check_hid_playstation() {
    if lsmod 2>/dev/null | grep -q '^hid_playstation'; then
        pass "driver hid_playstation carregado (cor da luz e LED de jogador)"
    elif [[ -d /sys/module/hid_playstation ]]; then
        pass "driver hid_playstation ativo (embutido no kernel)"
    else
        warn "driver hid_playstation não carregado — cor da luz e LED de jogador podem não funcionar. Kernel muito antigo? Rode: sudo modprobe hid_playstation"
    fi
}

# ---------------------------------------------------------------------------
# PROBE-MORTO-PS-01 — o DualSense que o driver do kernel ABORTOU no probe.
# ---------------------------------------------------------------------------
# check_hid_playstation (acima) só conferia se o MÓDULO carregou. Módulo
# carregado e controle invisível são compatíveis, e foi o que aconteceu 6x na
# máquina dela em 08/08/2026: o controle conecta no Bluetooth, acende a luz do
# PRÓPRIO firmware e não existe para o sistema — sem hidraw, sem input, sem nó
# de LED, sem bateria. A dona tinha dois controles ligados, a janela mostrava
# um, e nada em lugar nenhum do produto sabia dizer por quê.
#
# A assinatura no journal do kernel:
#
#   playstation 0005:054C:0CE6.0069: Failed to retrieve feature with reportID 32: -5
#   playstation 0005:054C:0CE6.0069: Failed to retrieve DualSense firmware info: -5
#   playstation 0005:054C:0CE6.0069: Failed to create dualsense.
#   playstation 0005:054C:0CE6.0069: probe with driver playstation failed with error -5
#
# NÃO é hardware — tese vetada por escrito por ela depois de dias perdidos
# nela. É CONTENÇÃO: dois DualSense subindo no mesmo adaptador com ~1 s de
# diferença; o segundo perde o canal de controle L2CAP, o BlueZ estoura o teto
# de 3 s (hidp_report_req_timeout) e o uhid achata o erro em -EIO (o -5 é
# máscara). A cadeia está medida elo a elo em
# assets/dkms/hid-playstation/README.md:62-114.
#
# Função PURA (stdin -> stdout), uma linha por instância hid que abortou:
# "INSTANCIA n_probe n_feature". O gate é o ABORTO (probe >= 1); a falha de
# feature é CORROBORAÇÃO da causa — contada e reportada, nunca exigida, porque
# um aborto por outro motivo não pode ficar invisível. Falha de feature SEM
# aborto é o transiente que o probe sobreviveu: sai vazio de propósito.
_hid_playstation_probe_scan() {
    sed -nE \
        -e 's/^.*playstation ([0-9A-Fa-f]{4}:[0-9A-Fa-f]{4}:[0-9A-Fa-f]{4}\.[0-9A-Fa-f]{4,}).*probe with driver playstation failed.*$/\1 probe/p' \
        -e 's/^.*playstation ([0-9A-Fa-f]{4}:[0-9A-Fa-f]{4}:[0-9A-Fa-f]{4}\.[0-9A-Fa-f]{4,}).*Failed to retrieve feature with reportID.*$/\1 feature/p' \
      | awk '
            $2 == "probe"   { p[$1]++ }
            $2 == "feature" { f[$1]++ }
            END {
                for (i in p) printf "%s %d %d\n", i, p[i], (i in f ? f[i] : 0)
            }
        ' | sort
}

# O estado ATUAL, que é quem decide o veredito: DualSense por Bluetooth em
# /sys/bus/hid/devices SEM o symlink `driver` — órfão é o que NÃO tem driver.
# Mesmo escopo estreito do scripts/bt_rebind_orphans.sh, e pelas mesmas razões:
# barramento 0005 (Bluetooth) é o único onde a contenção medida acontece, e
# exclui por construção o vpad do próprio hefesto, que nasce por uhid no
# barramento 0003; vendor 054C (Sony) é o dono do driver `playstation`. Só
# leitura de sysfs. HEFESTO_HID_DEVICES_DIR é a MESMA costura de teste do
# bt_rebind_orphans.sh — em produção nunca é definida.
_hid_playstation_orfaos_agora() {
    local raiz="${HEFESTO_HID_DEVICES_DIR:-/sys/bus/hid/devices}" dev id bus vid
    for dev in "${raiz}"/*; do
        [[ -d "${dev}" ]] || continue
        [[ -e "${dev}/driver" ]] && continue   # tem driver: foi adotado
        id="$(basename "${dev}")"
        bus="${id%%:*}"
        vid="${id#*:}"; vid="${vid%%:*}"
        [[ "${bus}" == "0005" ]] || continue
        [[ "${vid^^}" == "054C" ]] || continue
        printf '%s\n' "${id}"
    done
}

# O veredito. TRÊS casos, e a diferença entre eles é o que separa diagnóstico
# de ruído: dos 6 abortos de 08/08, TODOS recuperaram sozinhos em 2 a 20 min.
# Um FAIL por aborto que já passou ensina a ignorar o doctor — por isso o
# aborto é cruzado com o estado de AGORA:
#   1. controle órfão AGORA          -> FAIL (defeito ativo, cura pronta);
#   2. aborto na janela, sem órfão   -> info (histórico, nada a fazer);
#   3. nem uma coisa nem outra       -> pass.
# O órfão é conferido ANTES do journal e vale sozinho: o journal pode estar
# ilegível (sem grupo adm) e o sintoma continua sendo o sysfs.
#
# JANELA: `journalctl _TRANSPORT=kernel --since`, NUNCA `journalctl -k` — o -k
# implica o boot atual, e uma janela que atravessa reboot devolveria ZERO,
# indistinguível de "não houve nada". Esta casa já pagou quatro medições
# falsas por essa armadilha (índice de 08/08, §8).
#
# O TAMANHO da janela foi MEDIDO na máquina dela em 09/08, e a primeira
# escolha estava errada: com 24 h a mesma consulta via 1 dos 6 abortos de
# 08/08 (o boot dela é mais velho que um dia), e com 3 dias via os 6. Como o
# aborto recuperado é só `info`, uma janela larga custa pouco ruído e devolve
# o contexto inteiro do episódio. HEFESTO_DOCTOR_PROBE_JANELA ajusta.
#
# READ-ONLY, como todo check: aponta a cura (scripts/bt_rebind_orphans.sh) e
# a vigia que a chama de 2 em 2 min, e NÃO executa nenhuma das duas — o
# doctor confere e não cura.
check_hid_playstation_probe_abortado() {
    local janela="${HEFESTO_DOCTOR_PROBE_JANELA:-3 days ago}"
    local orfaos abortos tem_journal=0
    orfaos="$(_hid_playstation_orfaos_agora)"
    abortos=""
    if command -v journalctl >/dev/null 2>&1; then
        tem_journal=1
        abortos="$(journalctl _TRANSPORT=kernel --since "${janela}" --no-pager 2>/dev/null \
            | _hid_playstation_probe_scan)"
    fi

    if [[ -n "${orfaos}" ]]; then
        local id detalhe
        while read -r id; do
            [[ -z "${id}" ]] && continue
            detalhe=""
            if [[ -n "${abortos}" ]]; then
                detalhe="$(printf '%s\n' "${abortos}" \
                    | awk -v alvo="${id}" '$1 == alvo { printf "%dx aborto e %dx falha de feature no journal", $2, $3 }')"
            fi
            fail "DualSense ÓRFÃO AGORA (${id}): o driver playstation abortou a probe e o controle NÃO existe para o sistema — sem hidraw, sem input, sem nó de LED, sem bateria; invisível para o daemon e para a janela, mesmo conectado e com a luz acesa pelo próprio firmware${detalhe:+ (${detalhe})}. Cura pronta, sem reboot e sem derrubar quem já funciona: sudo /usr/local/lib/hefesto-dualsense4unix/bt_rebind_orphans.sh (no checkout: sudo bash scripts/bt_rebind_orphans.sh)"
        done <<<"${orfaos}"
        local tw=""
        if command -v systemctl >/dev/null 2>&1; then
            tw="$(systemctl is-active hefesto-bt-health-watchdog.timer 2>/dev/null || true)"
        fi
        if [[ "${tw}" == "active" ]]; then
            info "a vigia hefesto-bt-health-watchdog.timer está ativa e chama esse mesmo rebind de 2 em 2 minutos — se o controle voltar sozinho em até 2 min, foi ela"
        else
            warn "a vigia que chamaria o rebind sozinha (hefesto-bt-health-watchdog.timer) está ${tw:-ausente} — sem ela o controle órfão só volta à mão; ligue: sudo systemctl enable --now hefesto-bt-health-watchdog.timer"
        fi
        info "não é hardware (tese vetada por ela, por escrito, depois de dias perdidos nela): é contenção — dois DualSense subindo no mesmo adaptador com ~1 s de diferença; o segundo perde o canal de controle L2CAP e o BlueZ desiste no teto de 3 s (hidp_report_req_timeout). Cadeia medida: assets/dkms/hid-playstation/README.md:62-114"
        return
    fi

    if [[ -n "${abortos}" ]]; then
        local total_probe total_feature instancias
        total_probe="$(printf '%s\n' "${abortos}" | awk '{s += $2} END {printf "%d", s + 0}')"
        total_feature="$(printf '%s\n' "${abortos}" | awk '{s += $3} END {printf "%d", s + 0}')"
        instancias="$(printf '%s\n' "${abortos}" | awk '{printf "%s%s", (NR > 1 ? ", " : ""), $1}')"
        info "aborto de probe do hid-playstation na janela (${janela}), JÁ RECUPERADO: ${total_probe}x 'probe with driver playstation failed' em ${instancias} (${total_feature}x 'Failed to retrieve feature' antes) — nenhum DualSense está órfão AGORA, então não há o que fazer: é histórico, não defeito ativo (os 6 abortos de 08/08 voltaram sozinhos em 2 a 20 min, por reconexão)"
        info "se acontecer de novo COM o controle sumindo, a cura é o rebind (sudo /usr/local/lib/hefesto-dualsense4unix/bt_rebind_orphans.sh) e a vigia hefesto-bt-health-watchdog.timer a chama de 2 em 2 minutos; a causa medida é contenção de dois controles no mesmo adaptador, não hardware (assets/dkms/hid-playstation/README.md:62-114)"
        return
    fi

    if [[ "${tem_journal}" -eq 0 ]]; then
        info "nenhum DualSense órfão agora (todo device HID Sony por Bluetooth tem driver) — sem journalctl não dá para olhar o histórico de abortos de probe"
        return
    fi
    pass "nenhum DualSense órfão agora e nenhum aborto de probe do hid-playstation na janela (${janela})"
}

# COR-06/STATUS-07: probe READ-ONLY da gravabilidade do LED do DualSense FÍSICO.
# A regra 77 (default no install) dá escrita ao usuário nos nós de LED do kernel;
# sem ela o daemon só alcança a cor por hidraw — que em BT sofre EIO — e a cor
# por-controle degrada em silêncio (lightbar_source=="desired"). Só `test -w`:
# este check NUNCA escreve no nó. O vpad uhid do daemon também cria um nó
# rgb:indicator e precisa ser filtrado. Sem DualSense físico conectado: pula
# sem falhar.
#
# LUZ-CEGA-01 (22/08/2026) — o filtro do vpad comia TODO controle do RÁDIO.
# O critério era o caminho: `*/devices/virtual/*`. Mas o BlueZ moderno entrega
# HID por `uhid`, que é um `misc` VIRTUAL — então um DualSense de Bluetooth
# mora em `/sys/devices/virtual/misc/uhid/0005:054C:0CE6.xxxx/`, exatamente
# como o vpad. MEDIDO nesta bancada com QUATRO DualSense no rádio, todos com
# `multi_intensity` gravável: o check dizia *"sem DualSense físico com nó de
# LED agora (só o controle virtual, ou nenhum)"*. Zero de quatro.
#
# O preço do silêncio é o pior possível: ela abre o doctor justamente quando a
# cor não sai, e no rádio — que é onde a cor falha — o único check que olha o
# LED se declarava cego. Só quem usa CABO chegava a ver este check rodar.
#
# O critério certo é a IDENTIDADE, não o caminho: o vpad anuncia
# `HID_PHYS=hefesto-vpad` (a mesma marca que `broker/hidraw_broker.py:91`,
# `integrations/cor_do_plastico.py:176` e `integrations/uhid_gamepad.py:576`
# usam). Controle de verdade — cabo ou rádio — nunca tem esse `phys`.
# Teste que morde: tests/unit/test_o_doctor_enxerga_a_luz_do_radio.py
#
# LED-QUE-NÃO-AFIRMA-01 (13/08/2026): o `pass` daqui dizia "cor por-controle via
# sysfs OK (regra 77 valendo)" — e isso é uma afirmação de EFEITO que este check
# não tem como fazer, porque ele nunca escreveu no nó (o comentário três linhas
# acima já dizia isso). Ela lê o doctor justamente quando a cor NÃO está saindo:
# um `[ OK ]` afirmando que a cor funciona manda procurar no lugar errado. O
# texto passou a dizer o que foi medido — permissão de escrita — e `test -w` só
# derruba a hipótese "falta permissão"; a cor pode continuar sem sair por hidraw
# em EIO, por lightbar_source=="desired", ou por driver ausente. Há teste que
# reprova se a afirmação de efeito voltar: tests/unit/test_doctor_nao_afirma_efeito.py
check_led_sysfs_gravavel() {
    local node dev_real nome phys ok_nodes="" bad_nodes=""
    for node in /sys/class/leds/*rgb:indicator*; do
        [[ -e "${node}" ]] || continue
        dev_real="$(readlink -f "${node}/device" 2>/dev/null || true)"
        # Sem o link `device`: o nó mora em `<DEVICE_HID>/leds/<nome>` — dois
        # dirname sobem até o device. É a MESMA conta de
        # `core/sysfs_leds.py:discover`, de propósito: duas réguas que discordam
        # sobre onde está o device já custaram caro nesta casa.
        [[ -z "${dev_real}" ]] && dev_real="$(dirname "$(dirname "$(readlink -f "${node}" 2>/dev/null || echo /)")")"
        phys="$(sed -n 's/^HID_PHYS=//p' "${dev_real}/uevent" 2>/dev/null || true)"
        [[ "${phys}" == hefesto-vpad* ]] && continue   # vpad do daemon (LUZ-CEGA-01)
        [[ -e "${node}/multi_intensity" ]] || continue
        nome="${node##*/}"
        if [[ -w "${node}/multi_intensity" ]]; then
            ok_nodes+=" ${nome}"
        else
            bad_nodes+=" ${nome}"
        fi
    done
    if [[ -n "${bad_nodes}" ]]; then
        warn "nó de LED do DualSense físico SEM escrita p/ o seu usuário:${bad_nodes} — a cor por-controle (sobretudo em BT) depende do sysfs; a regra 77 dá a permissão: sudo bash scripts/install_udev.sh (e reconecte o controle)"
    elif [[ -n "${ok_nodes}" ]]; then
        pass "nó de LED do DualSense físico GRAVÁVEL pelo usuário (${ok_nodes# }) — a regra 77 está valendo. Só \`test -w\`: este check NUNCA escreve no nó, então isto é PERMISSÃO, não prova de que a cor sai"
    else
        info "sem DualSense físico com nó de LED agora (só o controle virtual, ou nenhum) — pulo o teste de gravabilidade; conecte o controle p/ validar a regra 77"
    fi
}

# ---------------------------------------------------------------------------
# OQ-6 (09/08/2026) — o touchpad e o giroscópio funcionavam por ACIDENTE.
# ---------------------------------------------------------------------------
# A regra do SISTEMA que dá ACL aos nós de entrada
# (/usr/lib/udev/rules.d/70-uaccess.rules) só marca ID_INPUT_JOYSTICK, e o
# `input_id` do kernel classifica o nó de movimento como
# ID_INPUT_ACCELEROMETER e o do touchpad como ID_INPUT_TOUCHPAD. Nenhum dos
# dois casava, e regra nenhuma desta casa os cobria: o acesso vinha do grupo
# `input`, em que a usuária desta máquina está POR FORA do produto (instalador
# nenhum daqui toca esse grupo). Numa máquina nova, nada funciona — e o sintoma
# é a AUSÊNCIA de dado: `core/evdev_reader.py:1396` engole a PermissionError
# num `except Exception: continue`, o nó some do mapa e o daemon relata
# "esse controle não tem sensor".
#
# A cura é `assets/72-hefesto-touchpad-motion-uaccess.rules`.
#
# POR QUE ESTA FUNÇÃO EXISTE SE `check_udev` JÁ CONFERE O ARQUIVO: porque as
# duas perguntas são diferentes. `check_udev` responde "a regra está no disco?";
# esta responde "a regra PEGOU?". Uma regra udev só age no (re)add do device —
# um controle que já estava conectado quando a regra chegou continua sem ACL
# até o replug. Arquivo presente e efeito ausente é exatamente o estado que
# passa despercebido.
#
# CONFERE E NÃO CURA (regra da casa): diz o comando, nunca o executa. E
# distingue os DOIS jeitos de o nó estar legível — a ACL da sessão (que a
# regra entrega, e que existe em máquina limpa) e o grupo do nó (o acidente,
# que não existe em máquina limpa). Só o primeiro é PASS.
#
# FÍSICO E VIRTUAL SÃO CONTADOS SEPARADAMENTE, e isso não é preciosismo — foi
# um FALSO VERDE MEDIDO em 09/08/2026. Rodando a primeira versão desta função
# nesta máquina ela imprimiu "[PASS] ... em 2 nó(s)", e os dois nós eram
# `.../input/event259` e `event261`, ambos em
# `/sys/devices/virtual/misc/uhid/0003:054C:0DF2.008F` — os nós auxiliares do
# VPAD que o próprio daemon acabara de criar. Não havia DualSense físico
# conectado. O instrumento deu verde sobre um device que nós mesmos fabricamos,
# e ficou calado exatamente sobre o que a pergunta era (o controle dela).
# `check_led_sysfs_gravavel` já resolvia isto do jeito certo, com
# `[[ "${dev_real}" == */devices/virtual/* ]] && continue`.
#
# OS DOIS IMPORTAM, por motivos diferentes, e por isso nenhum é descartado:
#   - o FÍSICO é o que alimenta a interface (o widget de giroscópio da aba
#     Status, via `daemon/sensor_hub.py`) e o cursor/teclas do touchpad;
#   - o VIRTUAL é o que o JOGO abre na máscara DualSense — sem ACL nele, o
#     jogo não lê giroscópio nem touchpad do vpad.
# O que não pode acontecer é um verde do virtual passar por resposta sobre o
# físico. Quando não há físico agora, a função DIZ que não há.
check_input_uaccess() {
    local regra="72-hefesto-touchpad-motion-uaccess.rules"
    if [[ ! -e "/etc/udev/rules.d/${regra}" && ! -e "/usr/lib/udev/rules.d/${regra}" ]]; then
        fail "${regra} ausente — o touchpad e o giroscópio só funcionam para quem está no grupo 'input' por fora do produto (numa máquina nova, não funcionam). Rode: sudo bash scripts/install_udev.sh"
        return
    fi
    local node base nome vid dev_real eu classe
    local vistos_fis=0 vistos_virt=0
    local sem_acesso=() so_pelo_grupo=() sem_acesso_virt=() so_grupo_virt=()
    eu="$(id -un 2>/dev/null || true)"
    for node in /dev/input/event*; do
        [[ -e "${node}" ]] || continue
        base="$(basename "${node}")"
        # Âncora de FABRICANTE, igual à da regra — sem ela o check alarmaria
        # sobre um touchpad de notebook cujo nome também termina em "Touchpad",
        # que a regra nunca cobre. Instrumento e produto casam o MESMO conjunto.
        vid="$(cat "/sys/class/input/${base}/device/id/vendor" 2>/dev/null || true)"
        case "${vid}" in
            054c|057e) ;;
            *) continue ;;
        esac
        nome="$(cat "/sys/class/input/${base}/device/name" 2>/dev/null || true)"
        case "${nome}" in
            *"Motion Sensors"|*"Touchpad"|*"(IMU)") ;;
            *) continue ;;
        esac
        dev_real="$(readlink -f "/sys/class/input/${base}/device" 2>/dev/null || true)"
        if [[ "${dev_real}" == */devices/virtual/* ]]; then
            classe="virt"
            vistos_virt=$((vistos_virt + 1))
        else
            classe="fis"
            vistos_fis=$((vistos_fis + 1))
        fi
        if [[ ! -r "${node}" ]]; then
            [[ "${classe}" == "fis" ]] && sem_acesso+=("${base}") || sem_acesso_virt+=("${base}")
        elif command -v getfacl >/dev/null 2>&1 && [[ -n "${eu}" ]] \
             && ! getfacl -p "${node}" 2>/dev/null | grep -q "^user:${eu}:"; then
            [[ "${classe}" == "fis" ]] && so_pelo_grupo+=("${base}") || so_grupo_virt+=("${base}")
        fi
    done
    # O vpad primeiro e sempre em separado: ele é nosso, e um problema nele é
    # problema do jogo, não da interface.
    if [[ "${#sem_acesso_virt[@]}" -gt 0 ]]; then
        fail "o gamepad VIRTUAL tem ${#sem_acesso_virt[@]} nó(s) de touchpad/movimento sem leitura (${sem_acesso_virt[*]}) — na máscara DualSense o jogo não lê giroscópio nem touchpad do vpad. Rode: sudo bash scripts/install_udev.sh"
    elif [[ "${#so_grupo_virt[@]}" -gt 0 ]]; then
        warn "o gamepad VIRTUAL tem ${#so_grupo_virt[@]} nó(s) legíveis só pelo GRUPO (${so_grupo_virt[*]}), sem ACL da sessão — funciona nesta máquina e não numa limpa"
    fi
    if [[ "${vistos_fis}" -eq 0 ]]; then
        if [[ "${vistos_virt}" -gt 0 ]]; then
            info "nenhum controle FÍSICO com nó de touchpad/movimento agora — os ${vistos_virt} nó(s) vistos são do gamepad virtual (/devices/virtual). Conecte o controle para validar o caso que importa."
        else
            info "nenhum nó de touchpad/movimento presente agora (controle desligado?) — nada a conferir"
        fi
        return
    fi
    if [[ "${#sem_acesso[@]}" -gt 0 ]]; then
        fail "sem permissão de leitura em ${#sem_acesso[@]} de ${vistos_fis} nó(s) FÍSICOS de touchpad/movimento (${sem_acesso[*]}) — o daemon engole o EACCES e relata 'sem sensor'. A ACL nasce no (re)add do device: desconecte e reconecte o controle; se persistir, rode: sudo bash scripts/install_udev.sh"
        return
    fi
    if [[ "${#so_pelo_grupo[@]}" -gt 0 ]]; then
        warn "${#so_pelo_grupo[@]} de ${vistos_fis} nó(s) FÍSICOS de touchpad/movimento legíveis só pelo GRUPO do nó (${so_pelo_grupo[*]}), sem a ACL da sessão — funciona NESTA máquina (você está no grupo 'input') e NÃO funcionaria numa limpa. Reconecte o controle para a ${regra} pegar."
        return
    fi
    pass "touchpad e giroscópio com ACL da sessão em ${vistos_fis} nó(s) do controle físico — sem depender do grupo 'input'"
}

# FEAT-DSX-DEFINITIVE-FIX-01 §7.5 (Opção D): o quirk de boot
# usbcore.quirks=054c:0ce6:gn,054c:0df2:gn é a alavanca do storm -71 que PRESERVA
# o áudio do DualSense (ALTERNATIVA à regra 75, que desliga o áudio). É um
# PARÂMETRO DE CMDLINE do kernel (NÃO é regra udev). Este check é puramente
# informativo: NUNCA fail nem warn. Reporta ativo (/proc/cmdline), agendado
# (config do bootloader), runtime (sysfs) ou ausente.
#
# NÃO É MAIS OPT-IN, e a frase de «ausente» dizia que era (O-QUE-E-DO-HEFESTO-
# SAI-DO-ZSH-01, 23/09/2026): o passo 3e do install (cmdline gerenciado, com
# MERGE e registro de dono) o aplica por DEFAULT há tempos; o `--with-usb-quirk`
# só adianta o passo 3b. O conselho passa a ser o do passo que de fato o põe.
# As duas portas para o mesmo token (3b e 3e) continuam sendo duas — fundi-las
# é dívida declarada, fora desta sprint.
check_usb_quirk() {
    local marker="054c:0ce6:gn"
    local active=0 scheduled=0 runtime=0
    grep -q "${marker}" /proc/cmdline 2>/dev/null && active=1
    { [[ -r /etc/kernelstub/configuration ]] && grep -q "${marker}" /etc/kernelstub/configuration 2>/dev/null; } && scheduled=1
    { [[ -r /etc/default/grub ]] && grep -q "${marker}" /etc/default/grub 2>/dev/null; } && scheduled=1
    { [[ -r /sys/module/usbcore/parameters/quirks ]] && grep -q "${marker}" /sys/module/usbcore/parameters/quirks 2>/dev/null; } && runtime=1

    if [[ "${active}" -eq 1 ]]; then
        info "quirk de áudio USB ATIVO neste boot (usbcore.quirks=...gn) — storm -71 mitigado PRESERVANDO o áudio do DualSense"
    elif [[ "${scheduled}" -eq 1 ]]; then
        info "quirk de áudio USB agendado p/ o próximo boot (config do bootloader) — reinicie para valer; status: scripts/install_usb_quirk.sh --status"
    elif [[ "${runtime}" -eq 1 ]]; then
        info "quirk de áudio USB armado em runtime (sysfs) — vale no próximo replug; para persistir no cmdline: scripts/install_usb_quirk.sh"
    else
        info "quirk de áudio USB ausente — o install o põe por default (passo 3e, cmdline gerenciado); à mão: scripts/install_usb_quirk.sh. É a alavanca que PRESERVA o áudio (a regra 75 é a que o desliga): use uma OU outra."
    fi
    if [[ "${active}" -eq 1 || "${scheduled}" -eq 1 || "${runtime}" -eq 1 ]]; then
        info "  caveat: o quirk preserva o áudio no nível do KERNEL (sem storm); com os WP 52/53 o nó segue suprimido no PipeWire até removê-los ou definir DUALSENSE_MIC_INTENDED=1"
    fi
}

# CROSS-CHECK do storm -71: a regra 75 (áudio-off) e o quirk (preserva-áudio)
# são alavancas ALTERNATIVAS do MESMO storm — instalar AS DUAS é contraditório:
# o quirk espaça a rajada de control-transfers para PRESERVAR o áudio, mas a
# regra 75 desliga esse mesmo áudio. Se ambas estiverem presentes (75 instalada
# E quirk ativo/agendado/runtime), avisamos para escolher UMA. Não substitui
# check_usb_audio_off nem check_usb_quirk; só cruza os dois sinais com warn().
check_usb_storm_config_conflict() {
    local rule75=0
    if [[ -e /etc/udev/rules.d/75-ps5-controller-disable-usb-audio.rules \
          || -e /usr/lib/udev/rules.d/75-ps5-controller-disable-usb-audio.rules ]]; then
        rule75=1
    fi

    local marker="054c:0ce6:gn" quirk=0
    grep -q "${marker}" /proc/cmdline 2>/dev/null && quirk=1
    { [[ -r /etc/kernelstub/configuration ]] && grep -q "${marker}" /etc/kernelstub/configuration 2>/dev/null; } && quirk=1
    { [[ -r /etc/default/grub ]] && grep -q "${marker}" /etc/default/grub 2>/dev/null; } && quirk=1
    { [[ -r /sys/module/usbcore/parameters/quirks ]] && grep -q "${marker}" /sys/module/usbcore/parameters/quirks 2>/dev/null; } && quirk=1

    if [[ "${rule75}" -eq 1 && "${quirk}" -eq 1 ]]; then
        warn "config contraditória: o quirk (usbcore.quirks=...gn) PRESERVA o áudio do DualSense, mas a regra 75 o DESLIGA — escolha UMA. Para manter o áudio: remova a 75 (uninstall ou reinstale sem --disable-usb-audio). Para áudio-off: remova o quirk (scripts/install_usb_quirk.sh --remove)."
    fi
}

# A BANDEJA DO PRODUTO É O TRAY — 19/09/2026, ordem dela: *"desabilitamos o
# applet pela complexidade. o tray faz o mesmo mas melhor."*
#
# Esta função auditava a saúde do applet COSMIC: `X-CosmicApplet`,
# `X-HostWaylandDisplay`, o ícone, o validador. Auditar a saúde de um
# componente aposentado é a definição de *medir outra coisa que não o
# produto* — e pior, havia um `fail` armado ali, que passaria a derrubar o
# diagnóstico de quem ainda tivesse o binário velho parado no disco.
#
# O QUE ELA MEDE AGORA é a corrente que leva o menu à barra dela:
#   1. o autostart existe? (sem ele o tray não sobe no login)
#   2. o hospedeiro da bandeja existe? (sem ele o ícone não tem onde aparecer)
#   3. o tray está de pé?
# E, só então, o applet — como RESTO a remover, não como produto a auditar.
check_bandeja() {
    local autostart="${HOME}/.config/autostart/hefesto-dualsense4unix-tray.desktop"
    if [[ -r "${autostart}" ]]; then
        local exec_do_autostart
        exec_do_autostart="$(sed -n 's/^Exec=//p' "${autostart}" | head -1)"
        if [[ "${exec_do_autostart}" == *--tray* ]]; then
            pass "autostart do tray instalado (${exec_do_autostart})"
        else
            # Um autostart que NÃO pede o tray abriria a JANELA a cada login,
            # na frente dela. É `fail` de propósito.
            fail "o autostart existe mas não pede o tray (Exec=${exec_do_autostart}) — reinstale"
        fi
    else
        warn "autostart do tray ausente — o ícone não sobe no login. Para instalar: $(conselho_de_instalacao)"
    fi

    # O HOSPEDEIRO DA BANDEJA. Este projeto afirmou por um mês que em Pop!_OS
    # COSMIC *"o org.kde.StatusNotifierWatcher que o libayatana usa não
    # existe"* — e foi essa premissa que fez nascer uma janela compacta
    # surrogate, hoje removida. Medido em 19/09/2026: ele EXISTE, servido pelo
    # `cosmic-applet-status-area`. Aqui a afirmacao vira medicao, e a maquina
    # de quem le responde por si.
    local dono_do_watcher=""
    if command -v busctl >/dev/null 2>&1; then
        dono_do_watcher="$(busctl --user status org.kde.StatusNotifierWatcher 2>/dev/null \
            | sed -n 's/^Comm=//p' | head -1)"
    fi
    if [[ -n "${dono_do_watcher}" ]]; then
        pass "hospedeiro da bandeja de pé (org.kde.StatusNotifierWatcher: ${dono_do_watcher})"
    else
        warn "nenhum org.kde.StatusNotifierWatcher no barramento — o ícone do tray não tem onde aparecer. No COSMIC, acrescente «Área de status» em Config. > Paineis > Miniaplicativos"
    fi

    if pgrep -f 'cli.app tray|hefesto-dualsense4unix tray' >/dev/null 2>&1; then
        pass "tray de pé"
    else
        info "tray não está rodando — ele sobe no próximo login, ou agora com: ./run.sh --tray"
    fi

    # O APPLET, COMO RESTO. Ele não é mais instalado por default (install.sh,
    # passo 9), e um binário parado não se anuncia sozinho: sem esta linha ela
    # veria dois ícones na barra um dia e leria como defeito novo.
    if [[ -e "${APPLET_DESKTOP}" || -e "/usr/local/bin/hefesto-dualsense4unix-applet" ]]; then
        info "há um applet COSMIC instalado de antes — ele foi APOSENTADO em 19/09/2026 e o tray o substitui. Para removê-lo sem tocar em mais nada: ./uninstall.sh --so-o-applet"
    fi
}


# BUG-WIREPLUMBER-FIX-FALSE-SUCCESS-01 / ADR-019: checa o microfone ATIVO
# (pactl get-default-source; fallback ao '*' do wpctl), não o `configured`.
# 3 estados: OK (ativo != DualSense); WARN (DualSense por ser a única fonte);
# FAIL (DualSense ativo COM outra fonte available — drop-in não pegou).
check_wireplumber_source() {
    local cur=""
    if command -v pactl >/dev/null 2>&1; then
        cur="$(pactl get-default-source 2>/dev/null || true)"
    fi
    if [[ -z "${cur}" ]] && command -v wpctl >/dev/null 2>&1; then
        cur="$(wpctl status 2>/dev/null | awk '
            /Sources:/{s=1;next} s&&(/Filters:/||/Sinks:/||/Streams:/||/Video/){s=0}
            s&&/\*/{sub(/.*\*[[:space:]]+[0-9]+\.[[:space:]]*/,"");print;exit}')"
    fi
    if [[ -z "${cur}" ]]; then
        warn "não consegui ler o microfone ativo (pactl/wpctl ausentes ou WirePlumber parado)"
        return
    fi
    # O '.monitor' do sink do DualSense casa "DualSense" no nome mas é o loopback
    # da saída, não o mic. O racional original está certo pela metade: monitor
    # NÃO é o mic do controle, então este check (que pergunta "o mic do DualSense
    # virou o padrão sozinho?") não tem o que reprovar aqui.
    #
    # O que ele NÃO podia continuar fazendo era chamar isso de "pass" e encerrar
    # o assunto: medido nesta máquina em 29/07/2026, a fonte padrão do sistema
    # ERA o monitor do alto-falante do próprio controle, e este [OK] era a única
    # linha do diagnóstico sobre o assunto. Ser um MONITOR é defeito PRÓPRIO, e
    # quem dá o veredito é `check_default_source_monitor`, logo abaixo.
    if [[ "${cur}" == *[Mm]onitor* ]]; then
        info "a fonte padrão é um MONITOR (${cur}) — não é o mic do DualSense; veredito em 'fonte de captura padrão'"
        return
    fi
    if [[ ! "${cur}" =~ [Dd]ual[Ss]ense ]]; then
        pass "microfone ativo não é o mic do DualSense (${cur})"
        return
    fi
    # ativo É o DualSense. Se a usuária QUER o mic do DualSense (opt-in), isso é
    # o desejado — não alarmar. Espelha a guarda de check_usb_audio_off e de
    # system_check.py (_dualsense_mic_intended), evitando falso-positivo.
    case "${HEFESTO_DUALSENSE4UNIX_DUALSENSE_MIC_INTENDED:-}" in
        1|true|yes|TRUE|YES)
            pass "microfone ativo é o DualSense (DUALSENSE_MIC_INTENDED=1 — desejado)"
            return ;;
    esac
    # O-PRODUTO-PROMOVE-E-RECLAMA-01 (10/08/2026): o PROMOTOR no disco também é
    # opt-in, e é o único que ela consegue dar.
    #
    # A incoerência foi medida no install dela, e terminava em `[FAIL]` na tela:
    #
    #   [FAIL] DualSense é o microfone ATIVO com outra fonte disponível
    #   [ OK ] a fonte de captura padrão é uma entrada de verdade (alsa_input...DualSense...)
    #
    # Duas linhas seguidas, o mesmo aparelho, vereditos opostos — e as seis
    # linhas seguintes todas OK. O motivo: em 08/08 (MONITOR-QUE-VENCE-01) o
    # drop-in 51 deixou de SUPRIMIR e passou a PROMOVER a entrada do controle
    # (`priority.session = 1500`), e ele entra por DEFAULT no install
    # (`WITH_WIREPLUMBER_FIX=1`). O produto passou a criar a condição que este
    # check continuou acusando. O nome do arquivo ainda diz "no-default-source",
    # que é o fóssil da regra antiga.
    #
    # E o opt-in que existia era uma VARIÁVEL DE AMBIENTE. Pela regra desta casa
    # (*"tudo tem que focar em funcionar na interface do app e no install"*),
    # opt-in que só se alcança exportando env não é opt-in dela: é opt-in de
    # quem lê o código. O promotor no disco, sim, é gesto dela — ele só existe
    # se o install rodou sem `--keep-dualsense-mic` ou se ela clicou "Ligar" na
    # aba Emulação.
    #
    # Continua ALARMANDO no caso que o check foi criado para pegar: promotor
    # ausente e o DualSense virando padrão sozinho, que é o mic dela sequestrado
    # sem ninguém pedir.
    if [[ -f "${HOME}/.config/wireplumber/wireplumber.conf.d/51-hefesto-dualsense-no-default-source.conf" ]]; then
        pass "microfone ativo é o DualSense (o promotor está instalado — foi pedido)"
        return
    fi
    # DROPIN-AMBIGUO-01 (26/08/2026) — a OUTRA metade do mesmo defeito. Sem o
    # 51, quem promoveu o mic a dedo (`mic promote`) recebia o FAIL abaixo a
    # cada execução do doctor, e um aviso que se aprende a ignorar é pior que
    # aviso nenhum. Agora quem responde é o GESTO gravado, não a ausência.
    if [[ -f "$(_marca_do_gesto_do_mic)" ]]; then
        pass "microfone ativo é o DualSense (foi pedido — marca do gesto em $(_marca_do_gesto_do_mic))"
        return
    fi
    # ativo É o DualSense (não desejado) — distingue escassez (única fonte) de falha real.
    local has_other=""
    if command -v wpctl >/dev/null 2>&1; then
        has_other="$(wpctl status 2>/dev/null | awk '
            /Sources:/{s=1;next} s&&(/Filters:/||/Sinks:/||/Streams:/||/Video/){s=0}
            s&&/[0-9]+\./&&!/[Dd]ual[Ss]ense/{print;exit}')"
    fi
    if [[ -n "${has_other}" ]]; then
        fail "DualSense é o microfone ATIVO com outra fonte disponível — rode: scripts/doctor.sh --fix"
    else
        warn "DualSense é o microfone ATIVO por ser a única fonte — conecte mic/webcam, ou desligue de vez: fix_wireplumber_default_source.sh --disable-source"
    fi
}

# --- FONTE-PADRAO-01: a fonte de captura padrão é um MONITOR ----------------
#
# MEDIDO nesta máquina em 29/07/2026, com o DualSense no cabo:
#
#   $ pactl get-default-source
#   alsa_output.usb-...DualSense...analog-surround-40.monitor
#
# Monitor é o loopback da SAÍDA. Enquanto ele for a fonte padrão, todo
# aplicativo que gravar sem escolher a fonte na mão capta o som que SAI do
# controle — jogo, música, a chamada inteira — e nunca a voz de quem fala. Não é
# "mic ausente": é mic TROCADO por um gravador de tela sonoro, e passa
# despercebido porque o medidor mostra sinal.
#
# A causa está documentada no próprio drop-in 51, que o install instala por
# DEFAULT: rebaixar o `alsa_input` do DualSense para ele não ser eleito padrão
# sozinho é a política certa, mas o rebaixamento faz o monitor do SINK do mesmo
# controle (que herda a prioridade alta da saída) ganhar a eleição. Somando a
# isso, o `default.configured.audio.source` persistido aqui apontava para
# `alsa_input...analog-stereo` — uma source que NÃO EXISTE neste perfil, rastro
# da cura de camada 2 que a medição de 26/07 refutou. Configurado num fantasma,
# o WirePlumber cai na eleição automática e o monitor vence.
#
# Classificação da fonte padrão. Função PURA: recebe o NOME e imprime
# `monitor` | `captura` | `vazio`. No PipeWire todo monitor termina em
# `.monitor` — o sufixo é do nó, não uma heurística de nome.
_default_source_classe() {
    local nome="$1"
    if [[ -z "${nome}" ]]; then
        printf 'vazio\n'
    elif [[ "${nome}" == *.monitor ]] || [[ "${nome}" == *.[Mm]onitor ]]; then
        printf 'monitor\n'
    else
        printf 'captura\n'
    fi
}

# DROPIN-AMBIGUO-01 — o caminho da MARCA DO GESTO, num lugar só.
#
# Quem escreve é `scripts/fix_wireplumber_default_source.sh` (nos gestos de
# LIGAR o mic) e o `install.sh --keep-dualsense-mic`; quem apaga são os gestos
# contrários e o `uninstall.sh`. Aqui só se LÊ. O caminho é duplicado por
# necessidade — o doctor não pode `source` um script que despacha —, e é o
# `tests/unit/test_dropin_ambiguo_01_a_marca_do_gesto.py` que cobra que os
# três arquivos digam o mesmo nome.
_marca_do_gesto_do_mic() {
    printf '%s/hefesto-dualsense4unix/mic-do-dualsense-pedido.conf\n' \
        "${XDG_STATE_HOME:-${HOME}/.local/state}"
}

# 0 quando o mic do DualSense PODE ser eleito fonte padrão do sistema.
#
# Três sinais EXPLÍCITOS, nenhum adivinhado — e a ordem é a hierarquia de quem
# manda. Isto existe para a cura não desfazer escolha de ninguém: promover o
# controle por conta própria reabriria a queixa que criou o drop-in 51 ("o
# controle fica mexendo no microfone") e faria `check_wireplumber_source`
# REPROVAR a máquina que acabamos de curar.
_prefere_mic_do_dualsense() {
    local conf="${HOME}/.config/wireplumber/wireplumber.conf.d"
    # 1. Quem DESLIGOU de propósito vem antes de tudo: o drop-in 52
    #    (`--disable-source` / `install --with-wireplumber-disable-mic`) é a
    #    escolha explícita de "o controle é só-HID". Mesmo precedente do
    #    `check_dualsense_sink_disabled` e do passo 10 do install.
    [[ -f "${conf}/52-hefesto-dualsense-disable-source.conf" ]] && return 1
    # 2. Opt-in explícito da usuária — a MESMA variável que
    #    check_wireplumber_source, check_usb_audio_off e system_check.py
    #    (_dualsense_mic_intended) já honram.
    case "${HEFESTO_DUALSENSE4UNIX_DUALSENSE_MIC_INTENDED:-}" in
        1|true|yes|TRUE|YES) return 0 ;;
    esac
    # 3. O drop-in 51 é a política DEFAULT do install: rebaixar. Enquanto ele
    #    estiver no lugar, o controle é a ÚLTIMA opção — não a primeira.
    [[ -f "${conf}/51-hefesto-dualsense-no-default-source.conf" ]] && return 1
    # 4. A MARCA DO GESTO (DROPIN-AMBIGUO-01, curado em 26/08/2026). Sem o 51,
    #    é ELA quem diz que a promoção foi pedida — e ela existe porque quem
    #    pediu deixou o gesto gravado, não porque um arquivo faltou.
    [[ -f "$(_marca_do_gesto_do_mic)" ]] && return 0
    # 5. Nem o 51 nem a marca: NÃO SEI, e "não sei" nunca é "ela pediu".
    #
    #    FATO ERRADO, SUBSTITUÍDO — esta linha era `return 0`, com o
    #    comentário *"sua ausência (ex.: --promote-source, mic promote) é a
    #    promoção explícita"*. A ausência tem DUAS origens e o disco não as
    #    distingue: a promoção explícita e o `uninstall` que desarmou a cura
    #    (ou a instalação que nunca houve). Lendo as duas como uma, o doctor
    #    dava [OK] — e ELEGIA o mic do controle a fonte padrão do sistema, com
    #    `pass` na tela — em cima de uma máquina com a cura desarmada. É desse
    #    estado que saiu a queixa dela de 04/08: *"não funciona nem mic, nem os
    #    botões de sons do jogo"* (DROPIN-AMBIGUO-01).
    #
    #    A migração escolhida é a CONSERVADORA (E4 da sprint, opção (b)):
    #    máquina que promoveu ANTES desta cura existir não tem marca e passa a
    #    ser tratada como "não sei". O preço é conhecido e pequeno — ela deixa
    #    de ser a primeira da fila quando a fonte padrão é um monitor, e o
    #    caminho de volta é um gesto só (`mic promote`). O preço da escolha
    #    oposta era o [OK] em cima do defeito, que já custou uma noite.
    return 1
}

# PURA: 0 quando a PORTA ATIVA da source `$1` está marcada `not available` pelo
# ALSA, no texto de `LC_ALL=C pactl list sources` (`$2` ou stdin).
#
# Este é o segundo degrau do critério de porta, e ele foi medido nesta máquina em
# 29/07/2026. Ter porta ativa não basta: a entrada analógica da onboard tem
# `Active Port: analog-input-front-mic` e as TRÊS portas de captura dela estão
# `not available` (nada plugado no jack). Ela é uma fonte de captura legítima e
# vai gravar silêncio. A entrada do DualSense, no mesmo instante, tinha porta com
# disponibilidade `unknown` e gravou pico 4606 na medição de 26/07 — por isso
# `unknown` conta como USÁVEL e só o `not available` explícito reprova.
#
# Serve para DIZER a verdade, nunca para escolher escondido: quem decide quem é a
# fonte padrão é `_prefere_mic_do_dualsense`, com os sinais explícitos dela.
_source_porta_ativa_indisponivel() {
    awk -v alvo="$1" '
        /^[[:space:]]+Name: / {
            atual = substr($0, index($0, ": ") + 2)
            next
        }
        atual != alvo { next }
        /^[[:space:]]+Active Port: / {
            ativa = substr($0, index($0, ": ") + 2)
            next
        }
        # Linha de porta: `<chave>: <descrição> (type: ..., not available)`.
        # O `(` é o que separa porta de `Volume:`/`Latency:` e das propriedades
        # (que usam ` = `, não `: `).
        /^[[:space:]]+[A-Za-z0-9_-]+: .*\(/ {
            linha = $0
            sub(/^[[:space:]]+/, "", linha)
            p = index(linha, ": ")
            if (p < 2) next
            chave = substr(linha, 1, p - 1)
            if (chave ~ /[[:space:]]/) next
            indisp[chave] = (linha ~ /not available/)
            next
        }
        END { exit ((ativa != "" && indisp[ativa]) ? 0 : 1) }
    ' "${2:--}"
}

# Melhor fonte de CAPTURA de verdade num `pactl list sources short` (arquivo ou
# stdin). `$1` = 1 para preferir o DualSense, 0 para deixá-lo como último
# recurso. Silêncio = não há nenhuma fonte de captura.
#
# Monitor NUNCA entra: é ele o defeito. E o DualSense nunca é DESCARTADO — um
# mic de verdade, mesmo o do controle, é melhor que gravar o próprio
# alto-falante; ele só perde a vez para outra entrada quando a política manda.
# Função PURA: só parsing, nenhuma escrita.
_melhor_source_de_captura() {
    awk -v prefere="${1:-0}" '
        tolower($2) ~ /\.monitor$/ { next }
        $2 == "" { next }
        {
            if (tolower($2) ~ /dualsense/) { if (ds == "") ds = $2 }
            else if (outro == "") outro = $2
        }
        END {
            if (prefere == 1) { escolha = (ds != "") ? ds : outro }
            else             { escolha = (outro != "") ? outro : ds }
            if (escolha != "") print escolha
        }
    ' "${2:--}"
}

# PURA: filtra um `pactl list sources short` (stdin) e deixa passar só as fontes
# cuja porta ativa NÃO está explicitamente `not available`. `$1` = o texto de
# `LC_ALL=C pactl list sources` (o longo), de onde sai a disponibilidade.
#
# Existe para que o CHECK e a CURA usem o mesmo critério. Enquanto cada um tinha
# o seu, o doctor reprovava e mandava eleger a onboard, e o `--fix-mic` — que já
# filtrava — se recusava a eleger a mesma onboard. Duas verdades no mesmo
# programa, e a que ela lia na tela era a errada (RECEITA-ERRADA-01, 06/08/2026).
_sources_com_porta_usavel() {
    local longo="$1" linha nome
    while IFS= read -r linha; do
        [[ -n "${linha}" ]] || continue
        nome="$(printf '%s\n' "${linha}" | awk '{print $2}')"
        if [[ -n "${nome}" ]] \
           && printf '%s\n' "${longo}" | _source_porta_ativa_indisponivel "${nome}"; then
            continue
        fi
        printf '%s\n' "${linha}"
    done
}

# MIC-PADRAO-NO-CABO-01 §D.7 (quem coordena): 0 = o alvo `$1` é o DualSense só por falta de outra entrada (`$2` = prefere 0) com o 51 no lugar; o WirePlumber o elege sozinho acima de qualquer monitor, e gravado ele venceria a webcam plugada depois (reproduzido com dublês, não medido no aparelho).
_dualsense_por_falta_com_o_51() { [[ "${2:-0}" -eq 0 && "${1,,}" == *dualsense* && -f "${HOME}/.config/wireplumber/wireplumber.conf.d/51-hefesto-dualsense-no-default-source.conf" ]]; }

check_default_source_monitor() {
    command -v pactl >/dev/null 2>&1 || { info "pactl ausente — não checo a fonte de captura padrão"; return; }
    local cur classe
    cur="$(pactl get-default-source 2>/dev/null || true)"
    classe="$(_default_source_classe "${cur}")"
    if [[ "${classe}" == "vazio" ]]; then
        info "não consegui ler a fonte de captura padrão (PipeWire parado?)"
        return
    fi
    if [[ "${classe}" != "monitor" ]]; then
        pass "a fonte de captura padrão é uma entrada de verdade (${cur})"
        # A METADE QUE FALTAVA. Sair daqui com [OK] e nada mais era como o
        # "pass" que aprovava o monitor: a fonte pode ser uma entrada legítima e
        # gravar silêncio, porque a porta ativa dela está `not available`. Medido
        # em 29/07 nesta máquina: eleita a entrada da onboard, as três portas de
        # captura estavam sem nada plugado, e o único mic que captava era o do
        # controle. Isto é INFO, não reprovação — quem manda na promoção é ela.
        local sources_txt
        sources_txt="$(LC_ALL=C pactl list sources 2>/dev/null || true)"
        if printf '%s\n' "${sources_txt}" | _source_porta_ativa_indisponivel "${cur}"; then
            info "  mas a porta ativa dela está indisponível (nada plugado) — vai gravar silêncio"
            local src_ds
            src_ds="$(LC_ALL=C pactl list sources short 2>/dev/null | _dualsense_source_nome)"
            if [[ -n "${src_ds}" ]] \
               && ! printf '%s\n' "${sources_txt}" | _source_porta_ativa_indisponivel "${src_ds}"; then
                info "  o mic do DualSense TEM porta usável agora — para elegê-lo: hefesto-dualsense4unix mic promote"
            fi
        fi
        return
    fi
    # RECEITA-ERRADA-01 (06/08/2026) — a mensagem mandava rodar `--fix-mic` SEM
    # saber se ele tem o que fazer, e o alvo que ela oferecia saía de uma lista
    # SEM o filtro de porta que a cura aplica. Nesta máquina isso produziu as
    # duas metades do mesmo defeito:
    #
    #   - MEDIDO em 06/08, sem webcam e sem controle no cabo: o check reprovava
    #     e mandava rodar `--fix-mic`; o `--fix-mic` respondia "não há nenhuma
    #     fonte de captura com porta usável para eleger" e não fazia nada. A
    #     receita levava a um comando que não podia funcionar;
    #   - MEDIDO em 29 e 30/07: o check oferecia `pactl set-default-source
    #     <onboard>`, cujas três portas estão `not available` — o pactl aceita,
    #     o WirePlumber não consegue honrar e REELEGE o monitor. A receita
    #     levava ao lugar errado, e o defeito voltava sozinho.
    #
    # Agora o alvo sai do MESMO filtro que a cura usa, então check e cura não
    # podem mais discordar; e quando não há alvo, o texto diz o que está
    # acontecendo em vez de apontar para um comando impotente.
    local prefere=0 alvo longo
    _prefere_mic_do_dualsense && prefere=1
    longo="$(LC_ALL=C pactl list sources 2>/dev/null || true)"
    alvo="$(LC_ALL=C pactl list sources short 2>/dev/null \
            | _sources_com_porta_usavel "${longo}" \
            | _melhor_source_de_captura "${prefere}")"
    if [[ -n "${alvo}" ]] && _dualsense_por_falta_com_o_51 "${alvo}" "${prefere}"; then
        fail "a fonte de captura padrão é um MONITOR (${cur}) — o que qualquer app gravar é o áudio de SAÍDA, não a voz; a entrada do DualSense está no ar e o drop-in 51 a põe acima de qualquer monitor, então o WirePlumber ainda não a elegeu (o --fix-mic NÃO grava essa escolha, que venceria a próxima webcam plugada; se o monitor continuar, o 51 pode não ter sido lido nesta sessão do WirePlumber, que só o lê ao iniciar)"
    elif [[ -n "${alvo}" ]]; then
        fail "a fonte de captura padrão é um MONITOR (${cur}) — o que qualquer app gravar é o áudio de SAÍDA, não a voz; rode: scripts/doctor.sh --fix-mic"
        info "  cura: pactl set-default-source ${alvo}"
    else
        fail "a fonte de captura padrão é um MONITOR (${cur}) — o que qualquer app gravar é o áudio de SAÍDA do sistema, não a voz, e o medidor de nível ainda mostra sinal (parece funcionando)"
        info "  o --fix-mic NÃO resolve este caso: ele só sabe ELEGER outra fonte de captura, e não há nenhuma com porta usável nesta máquina agora"
        info "  o que resolve é hardware: conecte um mic, uma webcam com mic, ou o DualSense (no cabo, ou por Bluetooth com o mic ligado)"
    fi
    # O rastro que explica o sintoma: configurado num nó que não existe mais, o
    # WirePlumber cai na eleição automática e o monitor ganha do mic rebaixado.
    local estado cfg
    estado="${HOME}/.local/state/wireplumber/default-nodes"
    if [[ -r "${estado}" ]]; then
        cfg="$(sed -n 's/^default\.configured\.audio\.source=//p' "${estado}" | head -n1)"
        if [[ -n "${cfg}" ]] \
           && ! LC_ALL=C pactl list sources short 2>/dev/null | awk -v n="${cfg}" '$2 == n { achou = 1 } END { exit (achou ? 0 : 1) }'; then
            info "  a fonte configurada em ${estado} é um FANTASMA (${cfg}): não existe entre as sources de agora"
        fi
    fi
}

# Cura de FONTE-PADRAO-01. Chamada pelo `fix_mic_dualsense` (logo, pelo --fix e
# pelo --fix-mic), DEPOIS da camada 2: é a troca de perfil que decide qual
# `alsa_input` existe, e eleger antes elegeria o nó errado.
fix_default_source_monitor() {
    command -v pactl >/dev/null 2>&1 || return 0
    local cur
    cur="$(pactl get-default-source 2>/dev/null || true)"
    # Só age no defeito. Fonte de captura de verdade — QUALQUER uma, inclusive
    # uma que não seja a que escolheríamos — é escolha de quem usa a máquina, e
    # não se mexe no que funciona.
    [[ "$(_default_source_classe "${cur}")" == "monitor" ]] || return 0
    local prefere=0 alvo
    _prefere_mic_do_dualsense && prefere=1

    # FONTE-PADRÃO-01, segunda metade — a fiação que faltava, medida em 30/07 num
    # `uninstall` + `install` limpos na máquina da mantenedora.
    #
    # O `_source_porta_ativa_indisponivel` já existia, com a medição escrita ao
    # lado dele, e NINGUÉM o chamava: o `_melhor_source_de_captura` escolhia a
    # primeira entrada não-DualSense e pronto. Nesta máquina isso elegia a onboard
    # `alsa_input.pci-...analog-stereo`, cujas TRÊS portas de captura estão
    # `not available` (nada plugado no jack). O `pactl set-default-source` até
    # aceita — e o WirePlumber, que não consegue honrar um nó sem porta usável,
    # reelege sozinho e volta para o MONITOR. A cura reportava sucesso e o defeito
    # continuava na tela, o que é pior do que não curar.
    #
    # Aqui a lista de candidatos é filtrada ANTES da escolha: fonte cuja porta
    # ativa está explicitamente indisponível sai da disputa. `unknown` continua
    # valendo — é o caso da entrada do DualSense, que grava de verdade (medido:
    # pico 441 num quarto silencioso, contra pico 0 do silêncio digital).
    #
    # O filtro virou `_sources_com_porta_usavel` (06/08/2026) para que o CHECK
    # ofereça exatamente o alvo que a CURA elegeria — antes cada um tinha o seu
    # critério, e a tela dizia uma coisa e o `--fix-mic` fazia outra.
    local lista_curta lista_completa _linha _nome
    lista_completa="$(LC_ALL=C pactl list sources 2>/dev/null || true)"
    lista_curta="$(LC_ALL=C pactl list sources short 2>/dev/null \
                   | _sources_com_porta_usavel "${lista_completa}")"
    while IFS= read -r _linha; do
        [[ -n "${_linha}" ]] || continue
        _nome="$(printf '%s\n' "${_linha}" | awk '{print $2}')"
        [[ -n "${_nome}" ]] || continue
        printf '%s\n' "${lista_curta}" | awk -v n="${_nome}" '$2 == n { achou = 1 } END { exit (achou ? 0 : 1) }' \
            || info "  ${_nome}: porta de captura indisponível (nada plugado) — fora da disputa"
    done < <(LC_ALL=C pactl list sources short 2>/dev/null || true)

    alvo="$(printf '%s\n' "${lista_curta}" | _melhor_source_de_captura "${prefere}")"
    if [[ -z "${alvo}" ]]; then
        # RECEITA-ERRADA-01: dizer que não deu não basta. O estado em que ela
        # fica é o defeito INTEIRO de pé — e ele não parece defeito, porque o
        # medidor de nível mostra sinal (é o áudio de saída da máquina).
        warn "a fonte padrão é um MONITOR (${cur}) e não há nenhuma fonte de captura com porta usável para eleger"
        info "  enquanto isso durar, TUDO o que qualquer aplicativo gravar é o áudio de SAÍDA do sistema, não a voz"
        info "  esta cura só sabe eleger outra fonte de captura — sem nenhuma, o que resolve é conectar um mic, uma webcam com mic, ou o DualSense"
        return 0
    fi
    _dualsense_por_falta_com_o_51 "${alvo}" "${prefere}" && { info "  não gravo ${alvo} como fonte padrão (§D.7 da MIC-PADRAO-NO-CABO-01): com o drop-in 51 o WirePlumber a elege sozinho acima de qualquer monitor, e gravada ela venceria a próxima webcam plugada"; return 0; }
    if pactl set-default-source "${alvo}" 2>/dev/null; then
        pass "fonte padrão trocada do monitor para a entrada ${alvo} (FONTE-PADRAO-01)"
    else
        warn "falha ao eleger ${alvo} como fonte padrão (a padrão segue o monitor ${cur})"
    fi
}

# O drop-in 53 (disable-output) põe node.disabled no SINK do DualSense — deixa o
# alto-falante e o fone no jack do controle MUDOS e derruba o canal de
# haptic-de-áudio. Instalado SÓ pelo fluxo de mic-off (--disable-source /
# install --with-wireplumber-disable-mic). Aqui só REPORTAMOS: presença = saída
# do controle desligada de propósito. NÃO afeta o rumble in-game (HID/vpad).
# DROPIN-AMBIGUO-01, E3 — o check que fala do ARQUIVO, não do sintoma.
#
# Todos os outros checks de microfone dependem do sintoma estar MANIFESTO:
# precisam de um mic ativo para ter o que reprovar. Com o DualSense na gaveta
# — que é a hora em que a maioria das instalações roda — o doctor ficava mudo
# sobre uma cura desarmada, e a máquina só descobria no meio do jogo. Este
# aqui lê disco, e por isso vale com nenhum controle conectado.
#
# PROVISÓRIO — decisão dela: as três frases desta função são texto novo de
# tela (LEVA-1-D, 26/08/2026).
check_dropin_do_mic_armado() {
    local conf="${HOME}/.config/wireplumber/wireplumber.conf.d"
    local marca; marca="$(_marca_do_gesto_do_mic)"
    if [[ -f "${conf}/52-hefesto-dualsense-disable-source.conf" ]]; then
        info "microfone do DualSense desligado de propósito (drop-in 52) — não há política de eleição a armar"
        return
    fi
    if [[ -f "${conf}/51-hefesto-dualsense-no-default-source.conf" ]]; then
        pass "a política de microfone do install está armada (drop-in 51 no lugar)"
        return
    fi
    # Sem o 51. O que essa AUSÊNCIA significa quem responde é o degrau da
    # marca do gesto — nunca a ausência por si.
    if _prefere_mic_do_dualsense; then
        local quando=""
        [[ -r "${marca}" ]] && quando="$(sed -n 's/^data=//p' "${marca}" | head -n1)"
        if [[ -n "${quando}" ]]; then
            pass "o mic do DualSense é escolha dela, de ${quando} (marca do gesto em ${marca})"
        else
            pass "o mic do DualSense é escolha dela (sinal explícito: DUALSENSE_MIC_INTENDED)"
        fi
        return
    fi
    warn "a política de microfone do install NÃO está armada e ninguém pediu para promover o controle — sem o drop-in 51 o WirePlumber pode eleger o mic do DualSense sozinho, e o que os aplicativos gravam vira o eco da saída em vez da voz"
    info "  se foi um uninstall que a desarmou, rearme: bash scripts/fix_wireplumber_default_source.sh --install"
    info "  se o mic do controle é o que você quer, peça de propósito: hefesto-dualsense4unix mic promote (isso grava a marca em ${marca}, e o doctor para de reclamar)"
}

# O ALTO-FALANTE QUE NÃO DORME (SOM-QUE-NAO-DORME-01; conferido pelo doctor
# desde a INSTALL-E-UNINSTALL-DO-RADIO-01, 23/09/2026). A cura é o drop-in 54
# do WirePlumber, que o install põe sem flag. O único aviso de que ele faltava
# era indireto — o «Canal dormindo» da tela, que saiu por ordem dela
# (O-ALTO-FALANTE-DIZ-ATIVO-01) —, e o leitor Python dele
# (`audio_saida.regra_nunca_dorme_instalada`) só alimentava a janela GTK. Lê o
# disco, então vale sem controle na mesa. Só o CABO depende dele: pelo rádio
# não há placa ALSA, e o som vai pela ponte do Hefesto.
check_dropin_do_alto_falante_acordado() {
    local nome=54-hefesto-dualsense-alto-falante-nunca-dorme.conf
    local posto="${HOME}/.config/wireplumber/wireplumber.conf.d/${nome}"
    local fonte="${ROOT_DIR}/assets/wireplumber/${nome}"
    if [[ ! -f "${posto}" ]]; then
        warn "o alto-falante do controle pode dormir no cabo (falta ${posto}) — o começo de cada som depois de um silêncio se perde: $(conselho_de_instalacao)$(so_no_checkout "(só ele: bash scripts/fix_wireplumber_default_source.sh --nunca-dorme)")"
        return
    fi
    if [[ -r "${fonte}" ]] && ! cmp -s "${fonte}" "${posto}"; then
        warn "o drop-in ${nome} é de outra versão — $(conselho_de_instalacao)$(so_no_checkout "(só ele: bash scripts/fix_wireplumber_default_source.sh --nunca-dorme)")"
        return
    fi
    pass "o alto-falante do controle não dorme no cabo (drop-in 54 no lugar)"
}

check_dualsense_sink_disabled() {
    local d="${HOME}/.config/wireplumber/wireplumber.conf.d/53-hefesto-dualsense-disable-output.conf"
    if [[ -f "${d}" ]]; then
        warn "saída de áudio do DualSense DESLIGADA (drop-in 53) — alto-falante/fone do controle mudos e canal de haptic-de-áudio off. Se não foi intencional: fix_wireplumber_default_source.sh --enable-mic + systemctl --user restart wireplumber"
    else
        pass "saída de áudio do DualSense preservada (sem o drop-in 53 disable-output)"
    fi
}

# HAPTICA-NATIVA-01 (18/09/2026): a vibração dos jogos da Sony pelo Proton
# viaja pelos canais 3 e 4 do sink `…HiFi__Speaker__sink`, e esse nome só
# existe com a placa do controle aberta por UCM. O
# `scripts/install_ucm_dualsense.sh` grava um gancho por controlador USB em
# `conf.d/USB-Audio/<nome longo da placa>.conf`; aqui se confere, placa por
# placa, que o gancho do nome dela existe — e depois que o PipeWire a abriu por
# ele, porque o gancho só vale no próximo replug. A primeira metade é a mesma
# pergunta do `_dualsenses_no_cabo_sem_ucm` do `core/system_check.py`, que a faz
# no boot do daemon. As duas variáveis de ambiente existem para os testes.
#
# SEM `ucm.conf` E COM DUALSENSE NO CABO É AVISO, não informação
# (INSTALL-UNIVERSAL, 18/09/2026). Aqui saía "esta distro não usa UCM" mesmo
# com o controle plugado: numa instalação sem `Recommends` (o `alsa-ucm-conf`
# vem como recomendação do `libasound2-data` no apt), a vibração pelo cabo
# sumia e o doctor a dava como escolha da distro. Sem controle no cabo, a
# frase antiga continua certa.
check_ucm_do_dualsense() {
    local raiz="${HEFESTO_RAIZ_UCM:-/usr/share/alsa/ucm2}"
    local cards="${HEFESTO_PROC_CARDS:-/proc/asound/cards}"
    local linha nome placas=0 sem=0
    local -a placas_no_cabo=()
    if [[ -r "${cards}" ]]; then
        while IFS= read -r linha; do
            nome="${linha#"${linha%%[![:space:]]*}"}"
            [[ "${nome}" == "Sony Interactive Entertainment DualSense"* ]] || continue
            placas_no_cabo+=("${nome}")
        done < "${cards}"
    fi
    if [[ ! -f "${raiz}/ucm.conf" ]]; then
        if [[ "${#placas_no_cabo[@]}" -gt 0 ]]; then
            warn "DualSense no cabo e sem ${raiz}/ucm.conf — sem o UCM do sistema (o pacote alsa-ucm-conf; no Fedora, alsa-ucm) a placa do controle não abre pelo perfil e a vibração dos jogos da Sony não chega pelo cabo. Depois de instalar o pacote, rode scripts/doctor.sh --fix (ou bash scripts/install_ucm_dualsense.sh)"
        else
            info "sem ${raiz}/ucm.conf — esta distro não usa UCM; perfil do DualSense não conferido"
        fi
        return
    fi
    [[ -r "${cards}" ]] || return
    for nome in ${placas_no_cabo[@]+"${placas_no_cabo[@]}"}; do
        placas=$((placas + 1))
        if [[ ! -f "${raiz}/conf.d/USB-Audio/${nome}.conf" ]]; then
            sem=$((sem + 1))
            warn "DualSense no cabo sem o perfil UCM (${nome}) — a vibração dos jogos da Sony não chega pelo cabo. Rode: bash scripts/install_ucm_dualsense.sh (ou scripts/doctor.sh --fix)"
        fi
    done
    if [[ "${placas}" -eq 0 ]]; then
        info "nenhum DualSense no cabo — perfil UCM não conferido"
        return
    fi
    [[ "${sem}" -eq 0 ]] || return
    local sinks total hifi
    sinks="$(timeout 5 pactl list short sinks 2>/dev/null)" || sinks=""
    total="$(printf '%s\n' "${sinks}" | grep -ci 'alsa_output[^[:space:]]*dualsense' || true)"
    hifi="$(printf '%s\n' "${sinks}" | grep -ci 'alsa_output[^[:space:]]*dualsense[^[:space:]]*Speaker__sink' || true)"
    if [[ "${total}" -gt "${hifi}" ]]; then
        warn "o gancho UCM existe, mas $((total - hifi)) placa(s) do DualSense abriram sem ele — replugue o controle (ou: systemctl --user restart wireplumber)"
    else
        pass "perfil UCM do DualSense armado (${placas} placa(s) no cabo)"
    fi
}

# HAPTICA-POR-RADIO-01 — AS ÂNCORAS USB (INSTALL-UNIVERSAL, 18/09/2026).
#
# Pelo rádio o controle não tem placa de som, e o endpoint que o jogo acha é um
# nó nosso que declara o `sysfs.path` de um aparelho USB SEM placa de som — a
# âncora de onde o Wine tira o ContainerId. É uma âncora por controle (duas
# iguais seriam dois endpoints com o mesmo ContainerId), e o daemon só entrega
# enquanto houver: o controle que sobra fica sem vibração, calado. Num desktop
# sobram âncoras (o próprio adaptador Bluetooth e os hubs internos); num
# notebook com a mesa de quatro, podem faltar.
#
# A pergunta é a MESMA do daemon, importada e não redigitada:
# `endpoint_de_haptica.ancoras` e a lista dos DualSense no rádio do
# `dualsense_bt_audio` (o mesmo filtro que o `alto_falante.controles_na_lista`
# aplica com `e_radio`, sem arrastar o pacote do daemon). Sem o pacote ao
# alcance (python sem as dependências), o check se declara incapaz em vez de
# responder. HEFESTO_SYSFS existe para os testes.
check_ancoras_da_haptica_por_radio() {
    local py saida radio ancoras
    py="$(_python_do_produto)"
    [[ -n "${py}" ]] || { info "sem python para conferir as âncoras da vibração pelo rádio"; return; }
    saida="$(HEFESTO_SRC="${ROOT_DIR}/src" HEFESTO_SYSFS="${HEFESTO_SYSFS:-/sys}" \
        "${py}" - <<'PY' 2>/dev/null
import os
import sys
from pathlib import Path

src = os.environ.get("HEFESTO_SRC", "")
if src and os.path.isdir(src):
    sys.path.insert(0, src)
try:
    from hefesto_dualsense4unix.integrations.dualsense_bt_audio import nos_dualsense_bluetooth
    from hefesto_dualsense4unix.integrations.endpoint_de_haptica import ancoras
except Exception:  # noqa: BLE001 - qualquer falha de import é "não sei"
    print("sem-produto")
    raise SystemExit(0)
sysfs = Path(os.environ.get("HEFESTO_SYSFS") or "/sys")
radio = {n.uniq for n in nos_dualsense_bluetooth(str(sysfs / "class" / "hidraw")) if n.uniq}
print(len(radio), len(ancoras(sysfs)))
PY
)" || saida=""
    if [[ ! "${saida}" =~ ^[0-9]+\ [0-9]+$ ]]; then
        info "âncoras da vibração pelo rádio não conferidas (o pacote não está ao alcance do python ${py})"
        return
    fi
    radio="${saida% *}"
    ancoras="${saida#* }"
    if [[ "${radio}" -eq 0 ]]; then
        info "nenhum DualSense no rádio — âncoras da vibração pelo rádio não conferidas (${ancoras} disponível(is))"
    elif [[ "${ancoras}" -ge "${radio}" ]]; then
        pass "âncoras USB da vibração pelo rádio: ${ancoras} para ${radio} controle(s)"
    else
        warn "a vibração pelo rádio precisa de um aparelho USB sem som por controle; ligue um hub ou um dongle — há ${ancoras} para ${radio} DualSense no rádio, e $((radio - ancoras)) fica(m) sem vibração nos jogos"
    fi
}

# G2 item 5: sink de áudio PADRÃO mudo — sintoma do incidente U12 de hoje
# (mute global escondia áudio/haptic de todo mundo, não só do DualSense).
# Função PURA (_wpctl_volume_muted) só interpreta o texto do `wpctl
# get-volume`; nenhuma escrita.
_wpctl_volume_muted() {
    local out="$1"
    if [[ -z "${out}" ]]; then
        printf 'unknown\n'
    elif printf '%s' "${out}" | grep -qi 'MUTED'; then
        printf 'muted\n'
    else
        printf 'unmuted\n'
    fi
}

check_audio_sink_muted() {
    command -v wpctl >/dev/null 2>&1 || { info "wpctl ausente — não checo o mudo do sink padrão"; return; }
    local out veredito
    out="$(wpctl get-volume @DEFAULT_AUDIO_SINK@ 2>/dev/null || true)"
    veredito="$(_wpctl_volume_muted "${out}")"
    case "${veredito}" in
        muted)
            warn "sink de áudio PADRÃO está MUDO (${out}) — sintoma do incidente U12 (mute global, não só do DualSense); reative: wpctl set-mute @DEFAULT_AUDIO_SINK@ 0"
            ;;
        unmuted)
            pass "sink de áudio padrão não está mudo (${out})"
            ;;
        *)
            info "não consegui ler o volume do sink padrão (wpctl get-volume vazio) — WirePlumber parado?"
            ;;
    esac
}

# --- MIC-USB-01: as três camadas de mudo empilhadas -------------------------
#
# Medido ao vivo em 25/07, com o controle no cabo: o microfone estava mudo por
# TRÊS motivos diferentes, em três donos diferentes, e cada cura revelava o de
# baixo. A aba Status dizia a verdade o tempo todo — o medidor era a única coisa
# funcionando. Duas dessas camadas são do WirePlumber e cabem aqui:
#
#   camada 1 — MUTE PERSISTIDO POR ROTA. O WirePlumber guarda mute e volume por
#     ROTA de placa em ~/.local/state/wireplumber/default-routes e restaura
#     fielmente a cada conexão, SEM NADA NO LOG. Sobrevive a reboot, replug e
#     reinstalação. Foi diagnosticado à mão uma vez e VOLTOU — a prova de que um
#     conserto que não é código não é conserto, é adiamento. Por isso ele está
#     aqui.
#   camada 2 — PERFIL DA PLACA NUMA ENTRADA SEM PORTA DE CAPTURA; decide a porta, não o nome do
#     perfil (`_dualsense_perfil_status`). FATO SUBSTITUÍDO (MIC-PADRAO-NO-CABO-01): o iec958 não é
#     "S/PDIF sem sinal" — o pico 0 de 25/07 foi com o mudo do firmware ativo; em 26/07, pico 4606.
#   camada 3 — o mudo no FIRMWARE do controle. Não é do WirePlumber e não se vê
#     por aqui: vive no `daemon.state_full` (`audio.mic_mudo`) e agora tem cura
#     pelo `mic.set` do IPC (`hefesto-dualsense4unix mic unmute`).
#
# Nada aqui hardcoda o nome do card ou da source: eles carregam o nome do
# produto e o sufixo da porta USB, e mudam de máquina para máquina.

# Rotas do DualSense com `"mute":true` no estado persistido do WirePlumber,
# SEPARADAS POR DIREÇÃO. `$2` = `input` (captura — o microfone; é o default) ou
# `output` (o alto-falante embutido do controle).
#
# A separação é a cura de um falso positivo MEDIDO em 28/07 nesta máquina. O
# filtro antigo casava qualquer rota cujo nome tivesse "dualsense", e a única
# rota muda do arquivo era `...:output:analog-output` — o ALTO-FALANTE. O
# portão reprovava o MICROFONE por causa da caixa de som, e essa linha [FAIL]
# levou dois levantamentos do mesmo dia a conclusões opostas. Só rota de
# CAPTURA pode falar pelo microfone; o alto-falante mudo é escolha legítima da
# usuária e vira INFO, nunca reprovação.
#
# A chave de rota é `<card>:<direção>:<porta>`, e a direção vem LOGO depois do
# nome da placa: por isso o `[^=:]*` entre "sense" e a direção, que proíbe o
# casamento de atravessar um `:`. Sem esse detalhe as entradas `:profile:` do
# mesmo arquivo entrariam pela porta dos fundos — o nome do perfil é
# `output:analog-surround-40+input:analog-stereo` e traz as duas palavras.
#
# Imprime a CHAVE de cada rota muda (uma por linha); silêncio = nada a fazer.
# Função PURA: recebe o arquivo, não escreve nada, não chama pactl.
_dualsense_rotas_mudas() {
    local arquivo="${1:-${HOME}/.local/state/wireplumber/default-routes}"
    local direcao="${2:-input}"
    [[ -r "${arquivo}" ]] || return 0
    # `|| true`: silêncio é a resposta NORMAL (nada mudo) e grep sai 1 nesse
    # caso — deixar o 1 escapar faria o chamador confundir "está tudo bem" com
    # "o check quebrou".
    grep -iE "^[^=]*dual[[:alnum:]_]*sense[^=:]*:${direcao}:[^=]*=.*\"mute\":[[:space:]]*true" \
        "${arquivo}" 2>/dev/null | sed -E 's/=.*$//' || true
}

# Nome da source de CAPTURA do DualSense em `pactl list sources short` (arquivo
# ou stdin). Só `alsa_input.*` — o `.monitor` do sink também casa "DualSense" no
# nome mas é o loopback da SAÍDA, não o microfone. Função PURA.
_dualsense_source_nome() {
    awk 'tolower($2) ~ /^alsa_input\..*dualsense/ { print $2; exit }' "${1:--}"
}

# Interpreta a saída do `pactl get-source-mute` (texto do pactl, LC_ALL=C).
# Imprime muted | unmuted | unknown. Função PURA (espelha _wpctl_volume_muted).
_source_mute_veredito() {
    local out="$1"
    if [[ -z "${out}" ]]; then
        printf 'unknown\n'
    elif printf '%s' "${out}" | grep -qiE 'mute:[[:space:]]*(yes|sim)'; then
        printf 'muted\n'
    elif printf '%s' "${out}" | grep -qiE 'mute:[[:space:]]*(no|não)'; then
        printf 'unmuted\n'
    else
        printf 'unknown\n'
    fi
}

# Camada 2, em uma linha: `card<TAB>perfil_ativo<TAB>perfil_alvo` a partir de um
# `pactl list cards` (arquivo ou stdin). `perfil_alvo` vazio = nada a trocar.
# Silêncio total = não há DualSense.
#
# ATENÇÃO — este decisor foi REESCRITO em 26/07/2026, e o motivo importa mais
# que o código. A versão anterior trocava o perfil sempre que a entrada ativa
# fosse `iec958`, mirando `input:analog-stereo`, porque a sprint MIC-USB-01
# afirmava que o microfone "vive" na entrada analógica.
#
# Medido no hardware, com o controle no cabo: o perfil analógico estava marcado
# `available: no` pelo próprio ALSA, e forçá-lo produzia uma source SEM NENHUMA
# PORTA DE CAPTURA, que entrega 327.680 bytes de silêncio digital. O
# `iec958-stereo` — o que a sprint mandava evitar — gravou pico 4606 e RMS 374.
# Ou seja: a "cura" SILENCIAVA o microfone de quem a rodasse.
#
# A regra nova não adivinha qual entrada é a boa. Ela só considera perfis que
# (a) oferecem fonte de captura (`sources: >= 1`) e (b) o ALSA declara
# `available: yes`, e escolhe o de maior prioridade entre esses. Se o perfil
# ATIVO já satisfaz os dois, não há troca — devolve alvo vazio. O contrato de
# preservar a SAÍDA continua valendo pela prioridade: os perfis com saída têm
# prioridade muito maior que os só-de-entrada, então o eleito mantém o
# alto-falante/fone do controle e o canal de haptic-de-áudio.
# Função PURA: só parsing, nenhuma escrita.
_dualsense_perfil_status() {
    awk '
        /^[[:space:]]+Name: alsa_card\./ {
            nome = substr($0, index($0, ": ") + 2)
            alvo = (tolower(nome) ~ /dualsense/)
            if (alvo) { card = nome }
            secao = ""
            next
        }
        !alvo { next }
        /^[[:space:]]+Profiles:/ { secao = "perfis"; next }
        /^[[:space:]]+Active Profile:/ {
            ativo = substr($0, index($0, ": ") + 2)
            secao = ""
            next
        }
        secao == "perfis" {
            linha = $0
            sub(/^[[:space:]]+/, "", linha)
            pos = index(linha, ": ")
            if (pos < 2) next
            chave = substr(linha, 1, pos - 1)
            if (chave ~ /[[:space:]]/) next
            # `sources: N` e `available: yes|no` saem do próprio pactl em
            # LC_ALL=C. Sem fonte de captura o perfil não serve ao microfone;
            # indisponível, ele produz o nó sem porta que silenciou a medição.
            temfonte = (linha ~ /sources: [1-9]/)
            disponivel = (linha ~ /available: yes/)
            prio = 0
            if (match(linha, /priority: [0-9]+/)) {
                prio = substr(linha, RSTART + 10, RLENGTH - 10) + 0
            }
            if (temfonte && disponivel && prio > melhorprio) {
                melhorprio = prio
                melhor = chave
            }
            # Guardado por chave, e NÃO comparado com `ativo` aqui: no `pactl`
            # a linha `Active Profile:` vem DEPOIS da lista, então neste ponto
            # `ativo` ainda está vazio. Comparar aqui fazia a guarda nunca
            # ligar — defeito que o teste pegou.
            serve[chave] = (temfonte && disponivel)
            next
        }
        END {
            if (card == "") exit 0
            escolhido = ""
            # Alvo só quando o ativo NÃO serve e há alternativa de verdade.
            if (!serve[ativo] && melhor != "" && melhor != ativo) escolhido = melhor
            printf "%s\t%s\t%s\n", card, ativo, escolhido
        }
    ' "${1:--}"
}

# --- MIC-CABO-SPDIF-01: a PORTA de captura, que a camada 2 não olha ---------
#
# O `_dualsense_perfil_status` acima decide no nível do PERFIL e está certo no
# que faz. Mas ele NUNCA olha a PORTA, e por isso não distingue uma porta que
# liga o elemento de ganho de captura de uma que não liga — que é o defeito
# medido em 17 e 20/09/2026 e que era invisível a todos os portões desta casa.
#
# O QUE ESTÁ FORA DE ALCANCE, e o número é do aparelho: o `Headset Capture
# Volume` do DualSense (Feature Unit 5 do descritor UAC, faixa 0…12288 =
# 0…+48 dB) foi lido em repouso a 100% / +48,00 dB. Nenhuma porta que o
# PipeWire ativou até hoje liga esse elemento, então o ganho não tem dono: nem
# o produto, nem a tela, nem ela.
#
# DOIS DONOS DIFERENTES PRODUZIRAM O MESMO ESTADO, e o segundo é NOSSO:
#   17/09 — a porta era `iec958-stereo-input`, do alsa-card-profile da distro,
#           cujo .conf tem um `[Element PCM Capture Source]` e NENHUM
#           `volume = merge`.
#   20/09 — com o UCM desta casa instalado (HAPTICA-NATIVA-01), a porta passou
#           a ser `[In] Mic`, do nosso `assets/ucm/DualSense-HiFi.conf`, cujo
#           `SectionDevice."Mic"` declara só `CapturePCM` e `CapturePriority`.
#           Sem `CaptureVolume`/`CaptureMixerElem`, o elemento continua fora.
# Trocar isso é mudança no SISTEMA dela e depende do par controlado do ganho
# (`scripts/ensaios/o_caminho_do_mic_no_cabo.py --ganho-plano`). Por isso este
# decisor DIZ, e não conserta.
#
# O DESENHO QUE CAIU, e fica escrito para ninguém refazê-lo: a sprint pedia os
# três textos `pactl list cards`, `pactl list sources` e `amixer scontents`.
# MEDIDO nesta bancada: **nenhuma saída do pactl distingue uma porta que liga
# elemento de captura de uma que não liga.** `Flags: HARDWARE` aparece até em
# monitor de sink puro, e `Base Volume: 100% / 0.00 dB` aparece igual na entrada
# de bordo, cujo elemento `Capture` está a +30,00 dB. Um decisor feito só de
# pactl responderia sobre outra coisa. Então o terceiro texto aqui é o que
# REALMENTE decide: a DEFINIÇÃO da porta ativa.
#
# PURA: três ARQUIVOS, nenhuma chamada a comando, nenhuma escrita.
#   $1 = `LC_ALL=C pactl list sources`
#   $2 = `LC_ALL=C amixer -c <N> scontents`
#   $3 = a definição da porta ATIVA (o `SectionDevice` do UCM, ou o
#        `paths/<porta>.conf` do alsa-card-profile)
# Imprime `porta_ativa<TAB>elemento_de_ganho<TAB>ganho_fora_de_alcance`.
# Silêncio total = não há source de captura do DualSense, e aí não há veredito.
_dualsense_porta_de_captura_status() {
    local porta elemento liga="não" fora="não"

    # A porta ATIVA da source de captura do DualSense. Só `alsa_input.*`: o
    # `.monitor` do sink também casa a marca no nome e é o loopback da SAÍDA.
    porta="$(awk '
        /^Source #/ { alvo = 0 }
        /^[[:space:]]+Name: / {
            nome = substr($0, index($0, ": ") + 2)
            alvo = (tolower(nome) ~ /^alsa_input\..*dualsense/)
            next
        }
        alvo && /^[[:space:]]+Active Port: / {
            print substr($0, index($0, ": ") + 2)
            exit
        }
    ' "${1:-/dev/null}")"
    [[ -n "${porta}" ]] || return 0

    # O elemento de ganho de CAPTURA que a placa tem para ligar. `cvolume` é a
    # capacidade de volume de captura no vocabulário do `amixer scontents`;
    # sem ela o elemento não é um ganho e não há nada fora de alcance.
    # A aspa simples vai por `-v`: escapá-la dentro do programa awk exigiria
    # `\x27`, que é extensão e esta casa roda mawk.
    elemento="$(awk -v aspa="'" '
        index($0, "Simple mixer control ") == 1 {
            nome = substr($0, index($0, aspa) + 1)
            corte = index(nome, aspa)
            if (corte > 1) { nome = substr(nome, 1, corte - 1) } else { nome = "" }
            tem = 0
            next
        }
        /Capabilities:/ && /cvolume/ { tem = 1 }
        tem && /Capture channels:/ && nome != "" { print nome; exit }
    ' "${2:-/dev/null}")"

    # A porta liga o ganho DESTE elemento? Os dois dialetos, e a pergunta é a
    # mesma nos dois: há ligação de VOLUME declarada **para o elemento que o
    # `scontents` achou** — não para um elemento qualquer do arquivo.
    #
    #   ACP  ..... `volume = merge` DENTRO do `[Element <elemento>]`. **Só o
    #              `merge`**, e quem decide isso é a documentação da distro, no
    #              disco desta máquina:
    #              `/usr/share/alsa-card-profile/mixer/paths/analog-output.conf.common`
    #              linhas 103-107 listam os cinco valores aceitos e dizem o que
    #              cada um faz — só o `merge` junta o elemento ao deslizante do
    #              dispositivo. O que põe no mínimo, o que crava 0 dB e o que
    #              crava um passo PRENDEM o elemento num valor fixo, que é
    #              palavra por palavra o defeito que este decisor existe para
    #              acusar. Contar qualquer um dos três daria verde sobre ele.
    #   UCM  ..... `CaptureVolume`/`CaptureMixerElem` cujo valor NOMEIE o
    #              elemento. O recorte de `$3` já é o `SectionDevice` da porta
    #              ativa, mas um dispositivo pode ligar OUTRO elemento da mesma
    #              placa — e ligar outro deixa este de fora do mesmo jeito.
    #
    # AMARRAR AO ELEMENTO É METADE DA RÉGUA: sem isso, uma porta que liga o
    # `[Element Speaker]` e não menciona o elemento de captura em lugar nenhum
    # seria declarada «alcança o ganho», que é verde sobre o defeito.
    if [[ -r "${3:-}" ]] && [[ -n "${elemento}" ]] && awk -v alvo="${elemento}" '
        /^[[:space:]]*(CaptureVolume|CaptureMixerElem)[[:space:]]/ {
            if (index($0, alvo) > 0) { ligou = 1 }
            next
        }
        /^[[:space:]]*\[/ {
            secao = $0
            sub(/^[[:space:]]*/, "", secao)
            sub(/[[:space:]]*$/, "", secao)
            dentro = (secao == "[Element " alvo "]" || index(secao, "[Element " alvo ",") == 1)
            next
        }
        dentro && /^[[:space:]]*volume[[:space:]]*=[[:space:]]*merge[[:space:]]*$/ { ligou = 1 }
        END { exit(ligou ? 0 : 1) }
    ' "${3}"; then
        liga="sim"
    fi

    # Reprova SÓ no cruzamento: a porta não liga E a placa tem o que ligar.
    # Sem elemento na placa não há nada fora de alcance, e reprovar aí seria
    # inventar defeito — foi por essa porta que voltou, em 26/07, a "cura" que
    # emudeceu o microfone de quem a rodou.
    if [[ -n "${elemento}" && "${liga}" == "não" ]]; then
        fora="sim"
    fi
    printf '%s\t%s\t%s\n' "${porta}" "${elemento}" "${fora}"
}

# A DEFINIÇÃO da porta `$1` no disco: o `SectionDevice` do UCM quando o nome
# vem do UCM (`[In] Mic`), ou o `paths/<porta>.conf` do alsa-card-profile.
# Grava num arquivo temporário e imprime o caminho — é a única parte IMPURA
# desta dupla, e existe para o decisor acima continuar puro.
_definicao_da_porta_de_captura() {
    local porta="$1" saida="$2"
    local raiz_ucm="${HEFESTO_RAIZ_UCM:-/usr/share/alsa/ucm2}"
    local raiz_acp="${HEFESTO_RAIZ_ACP:-/usr/share/alsa-card-profile/mixer/paths}"
    : > "${saida}"
    case "${porta}" in
        "[In] "*|"[Out] "*)
            # Nome de porta do UCM: `[In] Mic` → o `SectionDevice."Mic"`.
            local dispositivo="${porta#*] }"
            local verbo
            verbo="$(find "${raiz_ucm}" -name 'DualSense-HiFi.conf' -print -quit 2>/dev/null)"
            [[ -r "${verbo}" ]] || return 0
            awk -v alvo="SectionDevice.\"${dispositivo}\"" '
                index($0, alvo) == 1 { dentro = 1 }
                dentro { print }
                dentro && /^}/ { exit }
            ' "${verbo}" > "${saida}"
            ;;
        *)
            [[ -r "${raiz_acp}/${porta}.conf" ]] || return 0
            cat "${raiz_acp}/${porta}.conf" > "${saida}"
            ;;
    esac
}

# PURA: 0 quando a source de nome `$1` tem PORTA ATIVA no texto de
# `LC_ALL=C pactl list sources` lido de `$2` (arquivo) ou do stdin.
#
# É este o critério honesto de "dá para captar", e não o nome do perfil: uma
# source sem porta abre o fluxo e entrega zeros, em qualquer perfil. Medido em
# 26/07 — ver a nota em `_dualsense_perfil_status`.
_source_tem_porta_ativa() {
    awk -v alvo="$1" '
        /^[[:space:]]+Name: / {
            atual = substr($0, index($0, ": ") + 2)
            next
        }
        /^[[:space:]]+Active Port: / {
            if (atual == alvo) {
                porta = substr($0, index($0, ": ") + 2)
                if (porta != "" && porta != "(null)") { achou = 1 }
            }
            next
        }
        END { exit (achou ? 0 : 1) }
    ' "${2:--}"
}

# Face viva do critério acima: pergunta ao pactl desta máquina.
_dualsense_source_tem_porta() {
    local nome="$1"
    [[ -z "${nome}" ]] && return 1
    LC_ALL=C pactl list sources 2>/dev/null | _source_tem_porta_ativa "${nome}"
}

# CAMADA 1 — mute guardado por rota (arquivo) e mute vivo na source (pactl).
check_mic_mute_persistido() {
    local rotas="${HOME}/.local/state/wireplumber/default-routes"
    local mudas saida_mudas r
    mudas="$(_dualsense_rotas_mudas "${rotas}" input)"
    if [[ -n "${mudas}" ]]; then
        fail "microfone do DualSense MUDO por estado PERSISTIDO do WirePlumber (camada 1) — rode: scripts/doctor.sh --fix"
        while read -r r; do
            [[ -n "${r}" ]] && info "  rota muda: ${r}"
        done <<< "${mudas}"
        info "  o mute vive por ROTA em ${rotas} e é restaurado a cada conexão sem nada no log"
    elif [[ -r "${rotas}" ]]; then
        pass "nenhuma rota de CAPTURA do DualSense com mute persistido (camada 1)"
    else
        info "sem ${rotas} — o WirePlumber ainda não gravou estado de rota"
    fi

    # O alto-falante do controle mudo é um FATO sobre a saída, e a usuária pode
    # tê-lo escolhido. Ele aparece porque some é pior — mas como INFO, do lado
    # de fora do veredito do microfone.
    saida_mudas="$(_dualsense_rotas_mudas "${rotas}" output)"
    if [[ -n "${saida_mudas}" ]]; then
        info "o ALTO-FALANTE do DualSense está mudo no estado persistido — isso NÃO afeta o microfone"
        while read -r r; do
            [[ -n "${r}" ]] && info "  rota de saída muda: ${r}"
        done <<< "${saida_mudas}"
    fi

    command -v pactl >/dev/null 2>&1 || { info "pactl ausente — não checo o mudo VIVO da source"; return; }
    local src veredito
    src="$(LC_ALL=C pactl list sources short 2>/dev/null | _dualsense_source_nome)"
    if [[ -z "${src}" ]]; then
        info "sem source de captura do DualSense agora (controle fora do cabo, ou mic suprimido pelo drop-in 52)"
        return
    fi
    veredito="$(_source_mute_veredito "$(LC_ALL=C pactl get-source-mute "${src}" 2>/dev/null || true)")"
    case "${veredito}" in
        muted)   fail "a source do DualSense está MUDA agora (${src}) — rode: scripts/doctor.sh --fix" ;;
        unmuted) pass "source do DualSense não está muda (${src})" ;;
        *)       info "não consegui ler o mudo de ${src} (PipeWire parado?)" ;;
    esac
}

# CAMADA 2 — a entrada do DualSense sem porta de captura (o nome do perfil não decide).
check_mic_perfil_sem_sinal() {
    command -v pactl >/dev/null 2>&1 || { info "pactl ausente — não checo o perfil da placa do DualSense"; return; }
    local linha card ativo alvo
    linha="$(LC_ALL=C pactl list cards 2>/dev/null | _dualsense_perfil_status)"
    if [[ -z "${linha}" ]]; then
        info "nenhuma placa de áudio do DualSense agora (controle fora do cabo — por BT não existe placa)"
        return
    fi
    IFS=$'\t' read -r card ativo alvo <<< "${linha}"
    # A PORTA manda. Fonte com porta de captura capta — em qualquer perfil, e
    # inclusive no `iec958-stereo` que a sprint MIC-USB-01 mandava evitar (foi
    # ele que gravou pico 4606 na medição de 26/07). Nome de perfil não é
    # veredito: porta é.
    local src_atual
    src_atual="$(LC_ALL=C pactl list sources short 2>/dev/null | _dualsense_source_nome)"
    if _dualsense_source_tem_porta "${src_atual}"; then
        pass "a entrada do DualSense tem porta de captura (${ativo:-<vazio>})"
        return
    fi
    if [[ -z "${alvo}" ]]; then
        warn "a entrada do DualSense não tem porta de captura e não há perfil disponível melhor (${ativo:-<vazio>}) — sem porta, a gravação sai em silêncio digital"
        return
    fi
    fail "a entrada do DualSense não tem porta de captura (camada 2): ${ativo} — rode: scripts/doctor.sh --fix"
    info "  sem porta a source abre o fluxo e entrega zeros (medido: 327.680 bytes de silêncio digital)"
    info "  cura: pactl set-card-profile ${card} \"${alvo}\""
}

# MIC-CABO-SPDIF-01 — o ganho de captura que a porta ativa não liga.
#
# É WARN, e nunca FAIL, de propósito: o estado que ele descreve é o de sempre —
# nasceu com o produto e não é regressão de ninguém —, e a cura é mudança no
# SISTEMA dela que depende de uma medição com a orelha dela. Um FAIL aqui
# reprovaria toda instalação por um ponto que só ela pode fechar.
#
# E O VERDE DAQUI NÃO DIZ QUE O MICROFONE ESTÁ BOM. Ele responde sobre a
# configuração do PipeWire, não sobre o som: prova que o elemento existe e está
# (ou não) no caminho, nunca que o ganho melhora ou piora a captura. Quem ler
# de outro jeito leu errado, e por isso a frase está na própria linha.
check_mic_ganho_de_captura() {
    command -v pactl >/dev/null 2>&1 || { info "pactl ausente — não checo o ganho de captura do DualSense"; return; }
    command -v amixer >/dev/null 2>&1 || { info "amixer ausente — não checo o ganho de captura do DualSense"; return; }
    local indice
    indice="$(awk 'tolower($0) ~ /dualsense/ { print $1; exit }' \
        "${HEFESTO_PROC_CARDS:-/proc/asound/cards}" 2>/dev/null)"
    if [[ -z "${indice}" ]]; then
        info "nenhum DualSense no cabo — ganho de captura não conferido"
        return
    fi
    local tmp porta elemento fora
    tmp="$(mktemp -d)" || return
    LC_ALL=C pactl list sources > "${tmp}/sources" 2>/dev/null || true
    LC_ALL=C amixer -c "${indice}" scontents > "${tmp}/scontents" 2>/dev/null || true
    porta="$(awk '
        /^Source #/ { alvo = 0 }
        /^[[:space:]]+Name: / {
            nome = substr($0, index($0, ": ") + 2)
            alvo = (tolower(nome) ~ /^alsa_input\..*dualsense/)
            next
        }
        alvo && /^[[:space:]]+Active Port: / { print substr($0, index($0, ": ") + 2); exit }
    ' "${tmp}/sources")"
    _definicao_da_porta_de_captura "${porta}" "${tmp}/porta"
    local linha
    linha="$(_dualsense_porta_de_captura_status "${tmp}/sources" "${tmp}/scontents" "${tmp}/porta")"
    rm -rf "${tmp}"
    if [[ -z "${linha}" ]]; then
        info "sem source de captura do DualSense agora — ganho de captura não conferido"
        return
    fi
    IFS=$'\t' read -r porta elemento fora <<< "${linha}"
    if [[ "${fora}" == "sim" ]]; then
        warn "a porta de captura do DualSense (${porta}) não liga o elemento '${elemento}' — o ganho de captura fica fora do alcance do PipeWire, da tela e dela. Isto é sobre a CONFIGURAÇÃO do som, não sobre a qualidade do áudio"
        info "  quem define a porta hoje é o UCM desta casa (assets/ucm/DualSense-HiFi.conf); ligá-lo muda o SISTEMA dela e é decisão dela"
        info "  mede antes: scripts/ensaios/o_caminho_do_mic_no_cabo.py --ganho-plano"
        return
    fi
    pass "a porta de captura do DualSense (${porta}) alcança o ganho de hardware${elemento:+ ('${elemento}')} — e isto NÃO é um veredito sobre a qualidade do áudio"
}

# Cura das camadas 1 e 2. Chamada pelo --fix (junto das demais) e pelo --fix-mic
# (sozinha, para quem só quer o microfone de volta agora). Idempotente: cada
# passo confere antes de escrever e cala a boca quando não há o que fazer.
fix_mic_dualsense() {
    # Camada 1: o desmute das rotas mora no fix_wireplumber_default_source.sh,
    # que é o dono das escritas no estado do WirePlumber (ele para o serviço
    # antes de editar — com o WirePlumber vivo, o arquivo seria reescrito no
    # shutdown por cima da nossa edição).
    #
    # Sem segundo argumento a consulta é só de CAPTURA: uma cura de microfone
    # não pode ser disparada pelo alto-falante mudo, que a usuária pode ter
    # escolhido e que ninguém pediu para reativar.
    if [[ -n "$(_dualsense_rotas_mudas)" ]]; then
        if bash "${ROOT_DIR}/scripts/fix_wireplumber_default_source.sh" --unmute-routes >/dev/null 2>&1; then
            pass "mute persistido das rotas do DualSense removido (camada 1)"
        else
            warn "falha ao remover o mute persistido das rotas do DualSense"
        fi
    fi

    command -v pactl >/dev/null 2>&1 || return 0

    # Camada 2: perfil da placa num nó que REALMENTE capta.
    local linha card ativo alvo
    linha="$(LC_ALL=C pactl list cards 2>/dev/null | _dualsense_perfil_status)"
    if [[ -n "${linha}" ]]; then
        IFS=$'\t' read -r card ativo alvo <<< "${linha}"
        local src_antes
        src_antes="$(LC_ALL=C pactl list sources short 2>/dev/null | _dualsense_source_nome)"
        if _dualsense_source_tem_porta "${src_antes}"; then
            # NÃO TOCAR. Foi exatamente aqui que a versão anterior estragava a
            # máquina: trocava um perfil que captava por outro que o ALSA marca
            # indisponível, e a source nascia sem porta — silêncio digital.
            pass "a entrada do DualSense já tem porta de captura (${ativo:-<vazio>}) — camada 2 sem nada a fazer"
        elif [[ -n "${alvo}" ]]; then
            if pactl set-card-profile "${card}" "${alvo}" 2>/dev/null; then
                pass "perfil da placa do DualSense trocado para ${alvo} (camada 2, disponível e com fonte)"
            else
                warn "falha ao trocar o perfil da placa do DualSense para ${alvo}"
            fi
        else
            warn "sem porta de captura e sem perfil disponível melhor (${ativo:-<vazio>}) — o microfone não vai captar"
        fi
    fi

    # FONTE-PADRAO-01: com o perfil já resolvido acima, decidir QUEM é a fonte
    # padrão. Nesta ordem de propósito — é a troca de perfil que define qual
    # `alsa_input` existe, e eleger antes elegeria um nó que vai desaparecer.
    fix_default_source_monitor

    # Camada 1, face viva: a source pode estar muda sem que o arquivo diga —
    # o WirePlumber só grava o estado ao sair. Roda DEPOIS da troca de perfil,
    # porque é ela que faz a source analógica existir.
    local src veredito
    src="$(LC_ALL=C pactl list sources short 2>/dev/null | _dualsense_source_nome)"
    [[ -z "${src}" ]] && return 0
    veredito="$(_source_mute_veredito "$(LC_ALL=C pactl get-source-mute "${src}" 2>/dev/null || true)")"
    if [[ "${veredito}" == "muted" ]]; then
        if pactl set-source-mute "${src}" 0 2>/dev/null; then
            pass "source do DualSense desmutada (${src})"
        else
            warn "falha ao desmutar ${src}"
        fi
    fi
}

# Duplicação no jogo — DEDUP-04/UX-05: o doctor PAROU de recomendar a env
# estática (`IGNORE_DEVICES` colado por jogo era o veneno do "em BT nada
# funciona": quando o vpad degrada, a opção persistida esconde o ÚNICO
# controle => jogo com zero controles). O caminho suportado é o wrapper
# `hefesto-launch %command%`: string constante que decide as envs NA HORA
# consultando o daemon via IPC e degrada para "nenhuma env" (jogo sempre
# abre; pior caso: duplicado). Aqui: verificação do wrapper instalado + da
# materialização viva.
check_launch_wrapper() {
    local wrapper="${HOME}/.local/share/hefesto-dualsense4unix/bin/hefesto-launch"
    if [[ -x "${wrapper}" ]]; then
        pass "wrapper de launch instalado (${wrapper})"
    elif [[ -e "${wrapper}" ]]; then
        fail "wrapper hefesto-launch presente mas NÃO executável — rode: chmod +x ${wrapper}"
    else
        fail "wrapper hefesto-launch ausente — $(conselho_de_instalacao)$(so_no_checkout "(entra por default, sem flag)")"
    fi
    # PATH-06: o install cria ~/.local/bin/hefesto-launch — `hefesto-launch
    # %command%` digitado à mão passa a funcionar (a string canônica do botão
    # continua sendo o `sh -c` com caminho absoluto, que funciona sem PATH).
    local pathlink="${HOME}/.local/bin/hefesto-launch"
    if command -v hefesto-launch >/dev/null 2>&1; then
        pass "wrapper no PATH ($(command -v hefesto-launch))"
    elif [[ -x "${pathlink}" ]]; then
        warn "symlink ${pathlink} existe mas ~/.local/bin não está no PATH desta sessão — 'hefesto-launch %command%' digitado à mão só funciona com o PATH ajustado"
    else
        warn "wrapper fora do PATH (${pathlink} ausente) — $(conselho_de_instalacao)$(so_no_checkout "(o passo 5 cria o symlink, sem flag)")"
    fi
    local envdir="${HOME}/.local/state/hefesto-dualsense4unix/launch_env"
    if [[ -f "${envdir}/default.env" ]]; then
        pass "materialização de launch viva (${envdir}/default.env)"
        [[ "${QUIET}" -eq 1 ]] || sed -n 's/^# estado: /       estado: /p' "${envdir}/default.env" | head -1
    else
        warn "launch_env/default.env ausente — o daemon materializa ao (re)iniciar/ligar a emulação; sem ele o wrapper lança sem envs (fail-safe: jogo abre, pode duplicar)"
    fi
    # KERNEL-07/MISC-08: PROTON_ENABLE_HIDRAW é env MORTA nos Protons 10/11 (o
    # script nem a menciona; no winebus ela só AMPLIA exposição) — presença num
    # .env materializado = estado antigo do daemon.
    local stale_env
    stale_env="$(grep -ls "PROTON_ENABLE_HIDRAW" "${envdir}"/*.env 2>/dev/null | head -1)"
    if [[ -n "${stale_env}" ]]; then
        warn "launch_env com PROTON_ENABLE_HIDRAW (env morta nos Protons 10/11): ${stale_env} — materialização antiga; reinicie o daemon (systemctl --user restart hefesto-dualsense4unix) para regravar"
    fi
    # O CONTADOR SAIU (16/08/2026). Ele fazia `grep -o` do caminho do wrapper no
    # vdf inteiro e imprimia "N jogo(s) com o wrapper aplicado" em VERDE. Dois
    # defeitos numa linha só:
    #
    #   1. contava as TRÊS árvores `apps` do vdf, e a Steam só lê uma — medido
    #      às 05h35: "[ OK ] 76 jogo(s)" onde a árvore viva tem 63;
    #   2. contava sem NUNCA nomear quem faltava, que é a forma exata do
    #      WRAPPER-EM-TODOS-01 — o portão que passou a noite verde com o
    #      Pragmata quebrado.
    #
    # Nos últimos dias esse verde saía LOGO ACIMA do "[FAIL] PRAGMATA" do
    # `check_sentinela_wrapper`. O dano não é errar um diagnóstico: é a tela
    # ensinar que verde-e-vermelho juntos são normais por aqui, que é como um
    # portão morre de descrédito.
    #
    # O veredito agora vem inteiro do `check_sentinela_wrapper` (que nomeia) e
    # do `check_arvore_canonica_do_wrapper` (régua independente, ancorada no
    # caminho). Nenhum dos dois conta sem dizer quem.
    #
    # O caso "NENHUM jogo tem o wrapper" — a causa-mãe da sessão de 2026-07-18 —
    # continua coberto: sem wrapper em lugar nenhum, todo jogo cai em `novo` no
    # censo, e o censo os nomeia.
    info "controle DOBRANDO no jogo? use o botão 'Copiar opções p/ jogos' da GUI (string constante do wrapper) ou 'Aplicar aos jogos da Steam' (aplica o wrapper aos jogos, preservando as opções existentes)."
    check_sentinela_wrapper
}

# AS TRÊS CÓPIAS EM bin/ (INSTALL-UNIVERSAL, 18/09/2026). O wrapper chama dois
# curadores em Python — `hefesto-camadas` (ENGASGO-VULKAN-01) e
# `hefesto-audio-ks` (HAPTICA-NATIVA-01) — que o install MATERIALIZA ao lado
# dele, porque o lançamento não pode depender do checkout. Materializar tem um
# preço: as três cópias só se refazem no install, e um `git pull` sem
# reinstalar deixa o wrapper rodando a versão velha, sem aviso. O
# `check_launch_wrapper` só conferia a presença do `hefesto-launch`.
#
# É a CLASSE e não um curador: os três pares são o mesmo defeito, e o
# `cmp` só roda num checkout — fora dele não há fonte ao lado para comparar.
check_copias_do_wrapper() {
    local bin="${HOME}/.local/share/hefesto-dualsense4unix/bin"
    local par nome fonte alvo razao velhas="" instaladas=0
    for par in \
        "hefesto-launch|assets/hefesto-launch.sh|" \
        "hefesto-camadas|src/hefesto_dualsense4unix/integrations/camadas_vulkan.py|a cura do engasgo por camada Vulkan não roda no lançamento" \
        "hefesto-audio-ks|src/hefesto_dualsense4unix/integrations/audio_ks_dualsense.py|a vibração dos jogos da Sony pelo DualSense não chega ao jogo sob Proton"; do
        IFS='|' read -r nome fonte razao <<<"${par}"
        alvo="${bin}/${nome}"
        if [[ ! -x "${alvo}" ]]; then
            # O `hefesto-launch` ausente já é FAIL no `check_launch_wrapper`.
            [[ -n "${razao}" ]] && warn "curador ${nome} ausente ou sem permissão de execução em ${bin} — ${razao}; $(conselho_de_instalacao)"
            continue
        fi
        instaladas=$((instaladas + 1))
        esta_instalacao_e_um_checkout || continue
        command -v cmp >/dev/null 2>&1 || continue
        [[ -f "${ROOT_DIR}/${fonte}" ]] || continue
        cmp -s "${ROOT_DIR}/${fonte}" "${alvo}" || velhas="${velhas}${velhas:+, }${nome}"
    done
    if [[ -n "${velhas}" ]]; then
        warn "cópia em ${bin} diferente deste checkout: ${velhas} — o lançamento roda a versão velha até reinstalar; $(conselho_de_instalacao) (as cópias em bin/ só se refazem no install)"
    elif [[ "${instaladas}" -eq 3 ]]; then
        if esta_instalacao_e_um_checkout; then
            pass "wrapper e curadores do lançamento instalados e iguais a este checkout"
        else
            pass "wrapper e curadores do lançamento instalados (${bin})"
        fi
    fi
}

# O ÚLTIMO LANÇAMENTO DO DEVICE KS (INSTALL-UNIVERSAL, 18/09/2026). O curador
# roda dentro do lançamento, com a saída em /dev/null — é o jogo que está
# abrindo. O wrapper deixa uma linha de rastro em
# `launch_env/audio_ks_ultimo`, e é ela que se lê aqui:
#
#   sem-registro -> INFO. Todo jogo NOVO passa por aí: o prefixo nasce dentro
#                   do %command%, depois do wrapper, e o lançamento seguinte
#                   grava. Um aviso ali seria ruído a cada jogo instalado.
#   ocupado      -> WARN. O wineserver daquele prefixo continuou vivo mesmo
#                   depois da espera do wrapper (até cinco segundos).
#   erro         -> WARN, com o código de saída.
#   sem-curador  -> WARN. O install não materializou o `hefesto-audio-ks`.
#   sem-python   -> WARN. Sem python3 no PATH do lançamento, o wrapper não
#                   fala com o daemon (a opção nunca vem ligada) e o curador
#                   não roda — é a máquina, e não o controle.
#   desligado    -> INFO. A opção veio desligada e não havia bloco nosso.
#   removido     -> INFO, com a frase do `desligado`: a opção veio desligada
#                   e o device de um lançamento anterior SAIU do prefixo. O
#                   rastro dizia `ok`, e o doctor dava verde ao contrário.
check_ultimo_device_ks() {
    local arq="${XDG_STATE_HOME:-${HOME}/.local/state}/hefesto-dualsense4unix/launch_env/audio_ks_ultimo"
    if [[ ! -f "${arq}" ]]; then
        info "device KS do DualSense: nenhum lançamento pelo Proton registrado ainda"
        return
    fi
    local chave valor appid="" epoch="" rc="" motivo="" tentativas=""
    while IFS='=' read -r chave valor; do
        case "${chave}" in
            appid)      appid="${valor}" ;;
            epoch)      epoch="${valor}" ;;
            rc)         rc="${valor}" ;;
            motivo)     motivo="${valor}" ;;
            tentativas) tentativas="${valor}" ;;
        esac
    done < "${arq}"
    local jogo="um jogo sem appid" quando="" agora
    [[ "${appid}" =~ ^[0-9]+$ ]] && jogo="$(_rotulo_do_appid "${appid}")"
    agora="$(date +%s 2>/dev/null || true)"
    if [[ "${epoch}" =~ ^[0-9]+$ && "${agora}" =~ ^[0-9]+$ && "${agora}" -ge "${epoch}" ]]; then
        local seg=$((agora - epoch))
        if [[ "${seg}" -lt 3600 ]]; then
            quando=", há $((seg / 60)) min"
        elif [[ "${seg}" -lt 172800 ]]; then
            quando=", há $((seg / 3600)) h"
        else
            quando=", há $((seg / 86400)) dia(s)"
        fi
    fi
    case "${motivo}" in
        ok)
            pass "device KS do DualSense conferido no último lançamento pelo Proton (${jogo}${quando})" ;;
        sem-registro)
            info "o jogo ${jogo} abriu antes de o prefixo existir${quando}; a vibração do DualSense nele vale a partir do próximo lançamento" ;;
        ocupado)
            warn "device KS do DualSense NÃO gravado no último lançamento (${jogo}${quando}): o wineserver daquele prefixo continuou vivo depois de ${tentativas:-?} tentativa(s) — feche o jogo por completo e abra de novo" ;;
        erro)
            warn "o curador do device KS falhou no último lançamento (${jogo}${quando}, código ${rc:-?}) — a vibração dos jogos da Sony pode não chegar; rode à mão para ver o erro: python3 ${HOME}/.local/share/hefesto-dualsense4unix/bin/hefesto-audio-ks --prefixo <compatdata do jogo>" ;;
        sem-curador)
            warn "o último lançamento (${jogo}${quando}) não achou o curador do device KS — $(conselho_de_instalacao)" ;;
        sem-python)
            warn "o último lançamento pelo Proton (${jogo}${quando}) não achou python3 no PATH — sem ele o lançamento não fala com o daemon e a vibração dos jogos da Sony não chega; instale o python3 pelo gerenciador de pacotes da sua distribuição e abra o jogo de novo" ;;
        desligado)
            info "último lançamento pelo Proton (${jogo}${quando}) sem a opção da vibração: sem DualSense com endpoint de som, ou com o daemon fora do ar" ;;
        removido)
            info "último lançamento pelo Proton (${jogo}${quando}) sem a opção da vibração: sem DualSense com endpoint de som, ou com o daemon fora do ar — o device KS de um lançamento anterior saiu do prefixo" ;;
        *)
            info "rastro do device KS ilegível em ${arq}" ;;
    esac
}

# SENTINELA-WRAPPER-01 (16/08/2026): o contador acima diz QUANTOS jogos têm o
# wrapper e nunca diz QUAL não tem — e foi exatamente esse buraco que custou
# uma noite. Em 15/08 o Pragmata tinha `VKD3D_CONFIG=no_upload_hvv %command%`
# no lugar da chamada do wrapper (a Steam guarda UMA linha por jogo e a
# sobrescreve sem avisar); o contador dizia "60 jogos com o wrapper" e passava
# em verde, enquanto o jogo dela ficava sem controle nenhum no Bluetooth.
#
# O censo é READ-ONLY e roda com a Steam ABERTA — só a escrita é que exige a
# Steam fechada. `--censo` não anota nada em disco: o doctor diagnostica, quem
# grava a memória é o install/GUI.
check_sentinela_wrapper() {
    local py="${ROOT_DIR}/src/hefesto_dualsense4unix/integrations/sentinela_do_wrapper.py"
    if [[ ! -f "${py}" ]] || ! command -v python3 >/dev/null 2>&1; then
        return
    fi
    local resumo
    resumo="$(python3 "${py}" --censo 2>/dev/null | python3 -c '
import json
import sys

d = json.load(sys.stdin)
falta = d.get("faltantes") or []
def rot(m):
    return "; ".join(j["rotulo"] for j in falta if j["motivo"] == m)
print("regressao=" + rot("regressao"))
print("novo=" + rot("novo"))
print("estendido=" + rot("ignore_estendido"))
print("recusados=" + ", ".join(d.get("recusados") or []))
print("steam=" + ("1" if d.get("steam_aberta") else "0"))
print("jogo=" + ("1" if d.get("jogo_aberto") else "0"))
print("erros=" + str(len(d.get("erros") or [])))
' 2>/dev/null)"
    if [[ -z "${resumo}" ]]; then
        info "censo do wrapper indisponível — rode: python3 ${py} --relatorio"
        return
    fi
    local regressao novo estendido recusados steam jogo
    regressao="$(sed -n 's/^regressao=//p' <<<"${resumo}")"
    novo="$(sed -n 's/^novo=//p' <<<"${resumo}")"
    estendido="$(sed -n 's/^estendido=//p' <<<"${resumo}")"
    recusados="$(sed -n 's/^recusados=//p' <<<"${resumo}")"
    steam="$(sed -n 's/^steam=//p' <<<"${resumo}")"
    jogo="$(sed -n 's/^jogo=//p' <<<"${resumo}")"

    # CARONA-NO-GUARD-01: desde 16/08/2026 ela não precisa rodar nada. O
    # `hefesto-steam-input-guard` repõe sozinho quando a Steam grava o vdf —
    # que é o instante em que a Steam acabou de sair, o único em que a
    # reposição sobrevive. O comando fica escrito só para quem quiser não
    # esperar.
    local como="o Hefesto repõe sozinho assim que a Steam fechar; para não esperar: python3 ${py} --reparar"
    if [[ "${jogo}" == "1" ]]; then
        como="há um JOGO aberto — o reparo fica para quando a Steam fechar (fechá-la agora mataria o jogo)"
    elif [[ "${steam}" == "1" ]]; then
        como="a Steam está aberta — o Hefesto repõe assim que ela fechar (com ela viva a edição seria engolida na saída)"
    fi

    if [[ -n "${regressao}" ]]; then
        fail "jogo(s) que PERDERAM as Opções de Inicialização do Hefesto: ${regressao} — no Bluetooth o jogo tende a não enxergar controle nenhum, com o controle vivo, a luz acesa e o perfil aplicado (foi o defeito do Pragmata em 15/08); ${como}"
    elif [[ -n "${novo}" ]]; then
        warn "jogo(s) sem as Opções de Inicialização do Hefesto: ${novo} — ${como}"
    else
        pass "nenhum jogo perdeu as Opções de Inicialização do Hefesto"
    fi
    [[ -n "${estendido}" ]] && warn "Opções com a lista de IGNORE ESTENDIDA à mão em ${estendido} — intocáveis de propósito (remover só o trecho do Hefesto deixaria um fragmento que impede o jogo de abrir); reparo manual"
    [[ -n "${recusados}" ]] && info "fora do wrapper por escolha dela (jogos_sem_wrapper.txt): ${recusados}"
    check_arvore_canonica_do_wrapper
    return 0
}

# ARVORE-CANONICA-01 (16/08/2026) — a RÉGUA INDEPENDENTE do censo acima.
#
# O `localconfig.vdf` dela tem TRÊS árvores com blocos chamados `apps`, e as
# três carregam `LaunchOptions` por appid (medido às 05h07 de 16/08):
#
#   UserLocalConfigStore/Software/Valve/Steam/apps/<appid>   63 linhas  ← a viva
#   UserLocalConfigStore/apps/<appid>                        11 linhas
#   UserLocalConfigStore/WebStorage/apps/<appid>              3 linhas
#
# Qual é a viva não é palpite: quando ela digitou `VKD3D_CONFIG=no_upload_hvv
# %command%` nas Opções de Inicialização do Pragmata pela janela da Steam, foi
# a PRIMEIRA que mudou, e só ela. As outras duas seguem com a linha antiga.
#
# E as outras duas nasceram de NÓS: nos backups de 13/06 e de 16/07 (antes da
# primeira aplicação em massa) elas não existiam — zero `LaunchOptions` fora da
# canônica. No backup de 21/07 20:26, o da primeira aplicação em massa, a
# canônica salta de 6 para 55 linhas e as outras duas nascem juntas, com 9 e 2.
# O parser em massa casa qualquer bloco cujo PAI se chame `apps`, sem ancorar o
# caminho — então ele escreveu (e insere linha nova) em árvores que a Steam não
# lê.
#
# O estrago não era a linha a mais: era que o censo LIA a própria sujeira de
# volta. `read_apps_by_appid` fundia as três num dicionário só, por appid, e a
# ÚLTIMA lida vencia — e a última é a secundária. Resultado medido às 05h07: o
# censo jurava que o Pragmata tinha o wrapper, com a árvore viva dizendo
# `VKD3D_CONFIG` sozinho. Instrumento que confirma a si mesmo, a armadilha nº 1
# desta casa.
#
# CURADO às 05h45 do mesmo dia (ARVORE-ERRADA-01): `e_a_arvore_canonica` ancora
# o caminho no leitor e no escritor, e o censo passou a nomear o Pragmata. Este
# check CONTINUA valendo, e continua sendo escrito com um parser próprio, de
# propósito: uma régua que não compartilha código com a que ela audita é o que
# fez a contradição aparecer da primeira vez. Se as duas discordarem de novo, a
# discordância é o achado.
#
# Este check por isso NÃO importa o parser sob suspeita: ele reimplementa a
# pilha de blocos em vinte linhas e exige o caminho INTEIRO. Só o nome do jogo
# vem emprestado (`rotulo_do_jogo` lê os `.acf`, não o vdf).
check_arvore_canonica_do_wrapper() {
    command -v python3 >/dev/null 2>&1 || return 0
    local saida
    saida="$(HEFESTO_SRC="${ROOT_DIR}/src" python3 - <<'PY' 2>/dev/null
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.environ.get("HEFESTO_SRC", ""))
try:
    from hefesto_dualsense4unix.integrations.steam_launch_options import (
        WRAPPER_PREFIX,
        discover_vdfs,
        is_sandboxed_layout,
        rotulo_do_jogo,
    )
except Exception:  # noqa: BLE001 - sem o pacote o check simplesmente cala
    sys.exit(0)

CANONICA = ("UserLocalConfigStore", "Software", "Valve", "Steam", "apps")
CHAVE = re.compile(r'^"((?:\\.|[^"\\])*)"$')
PAR = re.compile(r'^"LaunchOptions"\s+"(?P<v>(?:\\.|[^"\\])*)"$', re.IGNORECASE)

canonicos: dict[str, str] = {}
secundarios: dict[str, str] = {}
#: appid -> o VALOR que está lá fora. É ele que diz se a linha é NOSSA
#: (tem a chamada do wrapper) ou se é sobra de texto de quem escreveu.
valor_secundario: dict[str, str] = {}
lidos = 0
for vdf in discover_vdfs():
    if is_sandboxed_layout(vdf):
        continue
    try:
        texto = vdf.read_text(encoding="utf-8")
    except (OSError, ValueError):
        continue
    pilha: list[str] = []
    pendente = None
    visto = False
    for bruta in texto.splitlines():
        linha = bruta.strip()
        if not linha:
            continue
        if linha == "{":
            pilha.append(pendente or "")
            pendente = None
            continue
        if linha == "}":
            if pilha:
                pilha.pop()
            pendente = None
            continue
        chave = CHAVE.match(linha)
        if chave is not None:
            pendente = chave.group(1)
            continue
        pendente = None
        par = PAR.match(linha)
        if par is None or len(pilha) < 2 or not pilha[-1].isdigit():
            continue
        visto = True
        appid = pilha[-1]
        valor = par.group("v").replace('\\"', '"').replace("\\\\", "\\")
        if tuple(pilha[:-1]) == CANONICA:
            canonicos[appid] = valor
        else:
            secundarios.setdefault(appid, "/".join(pilha[:-1]))
            valor_secundario.setdefault(appid, valor)
    lidos += 1 if visto else 0

if not lidos:
    sys.exit(0)
sem = [a for a, v in canonicos.items() if WRAPPER_PREFIX not in v]
orfaos = [a for a in secundarios if a not in canonicos]
nossos = [a for a in orfaos if WRAPPER_PREFIX in valor_secundario.get(a, "")]
alheios = [a for a in orfaos if a not in nossos]
print("total=%d" % len(canonicos))
print("sem=" + "; ".join(rotulo_do_jogo(a) for a in sorted(sem)))
print("orfaos_nossos=" + "; ".join(rotulo_do_jogo(a) for a in sorted(nossos)))
print("orfaos_alheios=" + "; ".join(rotulo_do_jogo(a) for a in sorted(alheios)))
print("poluidos=%d" % len(secundarios))
print(
    "poluidos_nossos=%d"
    % sum(1 for v in valor_secundario.values() if WRAPPER_PREFIX in v)
)
PY
)"
    [[ -n "${saida}" ]] || return 0
    local total sem orfaos_nossos orfaos_alheios poluidos poluidos_nossos
    total="$(sed -n 's/^total=//p' <<<"${saida}")"
    sem="$(sed -n 's/^sem=//p' <<<"${saida}")"
    orfaos_nossos="$(sed -n 's/^orfaos_nossos=//p' <<<"${saida}")"
    orfaos_alheios="$(sed -n 's/^orfaos_alheios=//p' <<<"${saida}")"
    poluidos="$(sed -n 's/^poluidos=//p' <<<"${saida}")"
    poluidos_nossos="$(sed -n 's/^poluidos_nossos=//p' <<<"${saida}")"

    if [[ -n "${sem}" ]]; then
        fail "na árvore que a Steam de fato lê (Software/Valve/Steam/apps), ESTE(S) jogo(s) NÃO chamam o wrapper: ${sem} — sem eles, no Bluetooth o jogo tende a não enxergar controle nenhum, mesmo com o controle vivo e o perfil aplicado. Reparo: o Hefesto repõe sozinho assim que a Steam fechar (é quando a reposição sobrevive), e também ao salvar ou aplicar um perfil"
    else
        pass "os ${total:-0} jogos da árvore viva (Software/Valve/Steam/apps) chamam o wrapper"
    fi
    # AUTORIA-DA-SOBRA-01 (02/09/2026): as duas frases daqui AFIRMAVAM duas
    # coisas que a medição derrubou — que a linha era "escrita por nós", sem
    # olhar o valor, e que "o censo as conta como cobertura", que o censo não
    # faz desde a âncora de caminho de 16/08 (ARVORE-ERRADA-01). Medido no vdf
    # dela: o único órfão (appid 413080) carrega `VKD3D_CONFIG=no_upload_hvv
    # %command%` — sem a chamada do wrapper — e o `censo_do_wrapper` devolveu
    # 63 com wrapper, que é exatamente o total da árvore viva. Agora a autoria
    # é LIDA no valor, e o que sobra é dito pelo que é: inerte.
    if [[ -n "${orfaos_nossos}" ]]; then
        warn "Opções de Inicialização NOSSAS (com a chamada do wrapper) numa árvore que a Steam não lê, para jogo(s) que nem existem na árvore viva: ${orfaos_nossos} — não quebram nada e não contam como cobertura, mas são lixo nosso no arquivo dela; recolha com a Steam fechada: python3 ${ROOT_DIR}/src/hefesto_dualsense4unix/integrations/steam_launch_options.py --recolher-fora-da-arvore-viva"
    elif [[ -n "${orfaos_alheios}" ]]; then
        info "sobra inerte numa árvore que a Steam não lê, para jogo(s) fora da árvore viva: ${orfaos_alheios} — a linha NÃO carrega a nossa chamada do wrapper, e o censo não a conta (ele lê só Software/Valve/Steam/apps desde 16/08). Quem abriu esse buraco foi um escritor nosso sem âncora, em 21/07; para recolher, com a Steam fechada: python3 ${ROOT_DIR}/src/hefesto_dualsense4unix/integrations/steam_launch_options.py --recolher-fora-da-arvore-viva"
    elif [[ "${poluidos_nossos:-0}" -gt 0 ]]; then
        info "${poluidos_nossos} de ${poluidos:-0} bloco(s) de 'apps' fora da árvore viva ainda têm a chamada do wrapper (escritas por nós em 21/07) — inertes para a Steam e ignoradas pelo censo; recolha com a Steam fechada: python3 ${ROOT_DIR}/src/hefesto_dualsense4unix/integrations/steam_launch_options.py --recolher-fora-da-arvore-viva"
    elif [[ "${poluidos:-0}" -gt 0 ]]; then
        info "${poluidos} bloco(s) de 'apps' fora da árvore viva também têm LaunchOptions — inertes para a Steam, sem a chamada do wrapper, e o censo não as lê. Quem as pôs lá foi um escritor nosso sem âncora (21/07); para recolher, com a Steam fechada: python3 ${ROOT_DIR}/src/hefesto_dualsense4unix/integrations/steam_launch_options.py --recolher-fora-da-arvore-viva"
    fi
    return 0
}

# UX-04: ACUSA (nunca recomenda) o veneno estático persistido nos
# localconfig.vdf — a assinatura `SDL_GAMECONTROLLER_IGNORE_DEVICES=
# 0x054c/0x0ce6` colada por jogo esconde físico E vpad quando o vpad degrada.
#
# T-08 (ONDA0-Z7, 24/08/2026): esta é UMA de TRÊS listas de raízes de Steam
# neste arquivo (as outras duas: check_proton_pin, _steam_input_do_appid) —
# as três têm de andar juntas, e são a versão em bash de
# `steam_launch_options.RAIZES_STEAM_RELATIVAS` (a lista única do lado
# Python). `test_a_lista_de_raizes_e_uma_so` (T-10) reprova se alguma
# divergir.
check_vdf_poison() {
    shopt -s nullglob
    local vdfs=(
        "${HOME}/.steam/steam/userdata/"*/config/localconfig.vdf
        "${HOME}/.local/share/Steam/userdata/"*/config/localconfig.vdf
        "${HOME}/.var/app/com.valvesoftware.Steam/.steam/steam/userdata/"*/config/localconfig.vdf
        "${HOME}/snap/steam/common/.steam/steam/userdata/"*/config/localconfig.vdf
    )
    shopt -u nullglob
    if [[ "${#vdfs[@]}" -eq 0 ]]; then
        info "nenhum localconfig.vdf da Steam encontrado — nada a acusar"
        return
    fi
    local vdf poisoned=0
    for vdf in "${vdfs[@]}"; do
        [[ -f "${vdf}" ]] || continue
        if grep -q 'SDL_GAMECONTROLLER_IGNORE_DEVICES=0x054c/0x0ce6' "${vdf}" 2>/dev/null; then
            poisoned=1
            warn "veneno estático persistido em ${vdf} — se o Hefesto cair/degradar, esse jogo abre com ZERO controles"
        fi
    done
    if [[ "${poisoned}" -eq 1 ]]; then
        info "cura (com a Steam fechada): botão 'Aplicar aos jogos da Steam' na GUI, ou:"
        info "  python3 ${ROOT_DIR}/src/hefesto_dualsense4unix/integrations/steam_launch_options.py --migrate"
    else
        pass "nenhuma Launch Option com o veneno estático nos localconfig.vdf"
    fi
}

# DEDUP-06: o guard anti-veneno consultado do MESMO jeito que o wrapper
# consulta o daemon — via IPC no socket de produção (nunca inspeção de
# processo). Reporta o `dedup_ok` agregado POR JOGADOR (P1 + co-op) e o aviso
# BT+Nativo (o SDL pode não enxergar o físico BT — fora do alcance do wrapper).
check_dedup_ipc() {
    local sock; sock="$(runtime_socket)"
    if [[ ! -S "${sock}" ]]; then
        info "daemon parado — sem estado de dedup a consultar (suba o daemon e rode de novo)"
        return
    fi
    if ! command -v python3 >/dev/null 2>&1; then
        warn "python3 ausente — não dá para consultar o dedup via IPC"
        return
    fi
    local out
    if ! out="$(python3 - "${sock}" <<'PYEOF' 2>/dev/null
import json
import socket
import sys

s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.settimeout(2.0)
s.connect(sys.argv[1])
s.sendall(
    json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": "daemon.state_full", "params": {}}
    ).encode("utf-8")
    + b"\n"
)
buf = b""
while not buf.endswith(b"\n"):
    chunk = s.recv(65536)
    if not chunk:
        raise SystemExit(1)
    buf += chunk
data = json.loads(buf.decode("utf-8"))
res = data.get("result") or {}
ge = res.get("gamepad_emulation") or {}
print(f"enabled={ge.get('enabled')}")
print(f"dedup_ok={ge.get('dedup_ok')}")
print(f"dedup_motivo={ge.get('dedup_motivo') or ''}")
print(f"native_bt={res.get('native_bt_fragil')}")
# MESA-CHEIA-11/E1: QUAIS controles estão frágeis (a flag acima virou "algum").
# Lista vazia = daemon antigo, ou mesa desconhecida — o aviso sai sem nomes.
frageis = res.get("native_bt_fragil_controles")
nums = (
    [n for n in frageis if isinstance(n, int) and not isinstance(n, bool)]
    if isinstance(frageis, list)
    else []
)
# CONSERTO 1.7: "2, 3 e 4", a MESMA grafia da janela (`juntar_rotulos`) — a
# mesma mesa não pode sair escrita de dois jeitos em duas telas da mesma casa.
if len(nums) > 1:
    quais = ", ".join(str(n) for n in nums[:-1]) + " e " + str(nums[-1])
else:
    quais = "".join(str(n) for n in nums)
print("native_bt_quais=" + quais)
# ...e QUANTOS, porque o shell não sabe contar uma frase: com UM frágil o texto
# dizia "com os Controles 3 ... esses controles" (plural para um), e a janela,
# no mesmo estado, acertava. O número é que escolhe o molde.
print(f"native_bt_quantos={len(nums)}")
PYEOF
)"; then
        warn "IPC não respondeu — estado de dedup indisponível (daemon travado?)"
        return
    fi
    local enabled dedup_ok motivo native_bt native_bt_quais native_bt_quantos
    enabled="$(sed -n 's/^enabled=//p' <<<"${out}")"
    dedup_ok="$(sed -n 's/^dedup_ok=//p' <<<"${out}")"
    motivo="$(sed -n 's/^dedup_motivo=//p' <<<"${out}")"
    native_bt="$(sed -n 's/^native_bt=//p' <<<"${out}")"
    native_bt_quais="$(sed -n 's/^native_bt_quais=//p' <<<"${out}")"
    native_bt_quantos="$(sed -n 's/^native_bt_quantos=//p' <<<"${out}")"
    if [[ "${native_bt}" == "True" ]]; then
        # MESA-CHEIA-11/E1: com quatro na mesa a pergunta seguinte é "quais?" —
        # e a resposta agora vem do daemon, que olha CADA controle em vez de só
        # o primário (com o Controle 1 no cabo, este aviso calava para os três
        # no rádio).
        #
        # CONSERTO 1.7: e são DOIS moldes, como na janela. Quem tem um controle
        # só no rádio — exatamente quem este aviso nasceu para socorrer — lia
        # "com os Controles 3 ... se o jogo não vir esses controles".
        if [[ "${native_bt_quantos}" == "1" && -n "${native_bt_quais}" ]]; then
            warn "Modo Nativo com o Controle ${native_bt_quais} em BLUETOOTH — o SDL pode não enxergar o físico BT (limite do HIDAPI); se o jogo não vir esse controle, use cabo USB ou a emulação"
        elif [[ -n "${native_bt_quais}" ]]; then
            warn "Modo Nativo com os Controles ${native_bt_quais} em BLUETOOTH — o SDL pode não enxergar o físico BT (limite do HIDAPI); se o jogo não vir esses controles, use cabo USB ou a emulação"
        else
            warn "Modo Nativo com o controle em BLUETOOTH — o SDL pode não enxergar o físico BT (limite do HIDAPI); se o jogo não vir o controle, use cabo USB ou a emulação"
        fi
    fi
    if [[ "${enabled}" != "True" ]]; then
        info "emulação de gamepad desligada — dedup por vpad não se aplica agora"
    elif [[ "${dedup_ok}" == "True" ]]; then
        pass "dedup POR JOGADOR ok (todos os vpads Edge/uhid, ou máscara Xbox)"
    elif [[ "${dedup_ok}" == "False" ]]; then
        warn "dedup QUEBRADA (${motivo:-sem motivo}) — jogo aberto com o IGNORE congelado pode deixar esse jogador com ZERO controles; reinicie o Hefesto na aba Sistema"
    else
        info "daemon não reporta dedup_ok (versão antiga do daemon?)"
    fi
}

# NUMA-05: diagnóstico da AUTORIDADE DE EXIBIÇÃO ('game'|'daemon'|'unknown',
# NUMA-01) — a causa-raiz do incidente de 14:42 era "não existe autoridade de
# exibição": sessão uhid do cliente Steam virava "jogo" aos olhos do daemon.
# Reporta o sinal ATUAL + a CAUSA quando ele está preso em 'unknown' (o
# comportamento degradado é sempre igual ao de hoje — nunca pior — mas
# escondido sem esta seção a mantenedora não teria como saber POR QUE). O
# posse-por-controle (`player_slot`/`lightbar_source`/`lightbar_rgb`, já no
# `state_full` desde STATUS-01/EXT-04) é listado junto — é o mesmo par
# get_players()/get_rgb() vs. autoridade que o `defend_display` compara.
check_display_authority() {
    local sock; sock="$(runtime_socket)"
    if [[ ! -S "${sock}" ]]; then
        info "daemon parado — sem sinal de autoridade de exibição a consultar (suba o daemon e rode de novo)"
        return
    fi
    if ! command -v python3 >/dev/null 2>&1; then
        warn "python3 ausente — não dá para consultar a autoridade de exibição via IPC"
        return
    fi
    local out
    if ! out="$(python3 - "${sock}" <<'PYEOF' 2>/dev/null
import json
import socket
import sys

s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.settimeout(2.0)
s.connect(sys.argv[1])
s.sendall(
    json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": "daemon.state_full", "params": {}}
    ).encode("utf-8")
    + b"\n"
)
buf = b""
while not buf.endswith(b"\n"):
    chunk = s.recv(65536)
    if not chunk:
        raise SystemExit(1)
    buf += chunk
data = json.loads(buf.decode("utf-8"))
res = data.get("result") or {}
gs = res.get("game_signal")
if not isinstance(gs, dict):
    print("sem_sinal=1")
else:
    print("sem_sinal=0")
    print(f"authority={gs.get('authority')}")
    print(f"evidencia={gs.get('evidencia') or ''}")
    print(f"motivo={gs.get('motivo') or ''}")
    print(f"degradado={gs.get('degradado')}")
for c in res.get("controllers") or []:
    if not isinstance(c, dict):
        continue
    slot = c.get("player_slot")
    fonte = c.get("lightbar_source")
    rgb = c.get("lightbar_rgb")
    print(f"posse|{slot}|{fonte}|{rgb}")
PYEOF
)"; then
        warn "IPC não respondeu — autoridade de exibição indisponível (daemon travado?)"
        return
    fi
    local sem_sinal authority evidencia motivo degradado
    sem_sinal="$(sed -n 's/^sem_sinal=//p' <<<"${out}")"
    if [[ "${sem_sinal}" == "1" ]]; then
        info "daemon não reporta o sinal de autoridade de exibição (versão antiga, sem NUMA-05)"
        return
    fi
    authority="$(sed -n 's/^authority=//p' <<<"${out}")"
    evidencia="$(sed -n 's/^evidencia=//p' <<<"${out}")"
    motivo="$(sed -n 's/^motivo=//p' <<<"${out}")"
    degradado="$(sed -n 's/^degradado=//p' <<<"${out}")"
    case "${authority}" in
        game)
            pass "autoridade de exibição: JOGO (evidência: ${evidencia:-desconhecida}) — DualSense mostram o número do jogo, externos sem disputa"
            ;;
        daemon)
            pass "autoridade de exibição: DAEMON — numeração/cor do co-op valendo, defesa contra escritor estrangeiro ativa"
            ;;
        unknown)
            if [[ "${degradado}" == "True" ]]; then
                warn "autoridade de exibição UNKNOWN (causa: ${motivo:-sem motivo reportado}) — degrada para o comportamento de hoje (réplica passa, jogo vence, daemon NÃO repinta); nunca pior, mas sem a defesa do NUMA-03"
            else
                info "autoridade de exibição unknown sem causa reportada — comportamento atual"
            fi
            ;;
        *)
            info "autoridade de exibição não reconhecida (${authority:-vazia}) — versão inconsistente do daemon?"
            ;;
    esac
    while IFS='|' read -r tag slot fonte rgb; do
        [[ "${tag}" == "posse" ]] || continue
        info "controle player_slot=${slot:-—} lightbar_source=${fonte:-desconhecida} lightbar_rgb=${rgb:-None}"
    done <<<"${out}"
}

# FEAT-WINDOW-DETECT-DIAG-01: diagnóstico do detector de janela do autoswitch
# (perfil-por-jogo). Quando a detecção falha, o autoswitch fica silenciosamente
# cego e o perfil-por-jogo vira letra morta — esta seção torna o estado visível.
# Cobre: DISPLAY/WAYLAND_DISPLAY do shell atual E do systemd --user (o daemon
# importa de lá quando sobe sem display — _ensure_display_env), o backend xlib
# (X11/XWayland: inclui jogos Proton/Steam), o portal XDG (GetActiveWindow), o
# wlrctl e o zcosmic_toplevel_info_v1. Veredito: OK / DEGRADADO / CEGO.
#
# A FRASE QUE CAIU — 02/09/2026. Esta seção dizia, no veredito DEGRADADO, que
# apps Wayland nativos aparecerem como 'unknown' era "limitação do compositor
# (COSMIC exigiria zcosmic_toplevel_info_v1), não do hefesto". A desculpa
# nomeava a cura: medido com `wayland-info`, dos 58 globais do cosmic-comp 0.1
# desta máquina o `zcosmic_toplevel_info_v1` ESTÁ publicado (versão 3) — quem
# não o usava era o produto. Usa agora, pelo `window_backends/cosmic_toplevel.py`,
# e este bloco pergunta ao MESMO código, em vez de reescrever o protocolo aqui.
# O que continua verdade sobre o COSMIC é o outro protocolo: o
# `zwlr_foreign_toplevel_manager_v1` não está entre os 58, e é por isso que o
# wlrctl responde "Foreign Toplevel Management interface not found".
check_window_detect() {
    local env_display="${DISPLAY:-}" env_wayland="${WAYLAND_DISPLAY:-}"
    local sysd_env="" sysd_display="" sysd_wayland=""
    if command -v systemctl >/dev/null 2>&1; then
        sysd_env="$(systemctl --user show-environment 2>/dev/null || true)"
        sysd_display="$(printf '%s\n' "${sysd_env}" | sed -n 's/^DISPLAY=//p' | head -1)"
        sysd_wayland="$(printf '%s\n' "${sysd_env}" | sed -n 's/^WAYLAND_DISPLAY=//p' | head -1)"
    fi
    info "shell atual:    DISPLAY=${env_display:-<vazio>}  WAYLAND_DISPLAY=${env_wayland:-<vazio>}"
    info "systemd --user: DISPLAY=${sysd_display:-<vazio>}  WAYLAND_DISPLAY=${sysd_wayland:-<vazio>}"

    # Valores efetivos: espelha o daemon (usa o env; se faltar, importa do
    # systemd --user via _ensure_display_env no boot do autoswitch).
    local eff_display="${env_display:-${sysd_display}}"
    local eff_wayland="${env_wayland:-${sysd_wayland}}"
    if [[ -z "${env_display}" && -n "${sysd_display}" ]]; then
        info "DISPLAY só existe no systemd --user — o daemon importa sozinho no boot do autoswitch"
    fi

    # Backend xlib (X11/XWayland). xprop prova que o servidor X responde;
    # python-xlib (o que o daemon usa de fato) fica como probe secundário
    # porque o python3 do PATH pode não ser o venv do daemon.
    local xlib_ok=0
    if [[ -n "${eff_display}" ]]; then
        if command -v xprop >/dev/null 2>&1 \
           && DISPLAY="${eff_display}" timeout 3 xprop -root _NET_ACTIVE_WINDOW >/dev/null 2>&1; then
            xlib_ok=1
            pass "servidor X responde em DISPLAY=${eff_display} (xprop) — backend xlib viável"
        elif DISPLAY="${eff_display}" timeout 3 python3 -c \
             'from Xlib import display; display.Display().close()' >/dev/null 2>&1; then
            xlib_ok=1
            pass "python-xlib conecta em DISPLAY=${eff_display} — backend xlib viável"
        else
            warn "DISPLAY=${eff_display} setado, mas nem xprop nem python-xlib falam com o X — backend xlib fora"
        fi
    else
        info "sem DISPLAY — backend xlib indisponível (jogos XWayland/Proton NÃO detectáveis)"
    fi

    # Portal XDG: interface Window com o método GetActiveWindow de verdade
    # (busctl com filtro de interface SEMPRE sai 0 — o grep é o teste real).
    local portal_ok=0
    if command -v busctl >/dev/null 2>&1; then
        if busctl --user --timeout=3 introspect org.freedesktop.portal.Desktop \
             /org/freedesktop/portal/desktop org.freedesktop.portal.Window 2>/dev/null \
             | grep -q 'GetActiveWindow'; then
            portal_ok=1
            pass "portal XDG expõe org.freedesktop.portal.Window::GetActiveWindow"
        else
            info "portal XDG sem GetActiveWindow (esperado no COSMIC atual) — backend portal fora"
        fi
    fi

    # zcosmic_toplevel_info_v1 — o caminho do COSMIC. Perguntado ao PRÓPRIO
    # backend do produto (mesmo código que o daemon roda); se o pacote
    # instalado for velho demais para tê-lo, cai no `wayland-info`, que
    # responde a mesma pergunta com outra régua.
    local cosmic_ok=0 cosmic_linha="" py_produto=""
    py_produto="$(_python_do_produto)"
    if [[ -z "${eff_wayland}" ]]; then
        info "sem WAYLAND_DISPLAY — não há compositor Wayland a quem perguntar"
    else
        if [[ -n "${py_produto}" ]]; then
            cosmic_linha="$(WAYLAND_DISPLAY="${eff_wayland}" timeout 5 "${py_produto}" -m \
                hefesto_dualsense4unix.integrations.window_backends.cosmic_toplevel \
                2>/dev/null || true)"
        fi
        if [[ "${cosmic_linha}" == protocolo=sim* ]]; then
            cosmic_ok=1
            pass "compositor responde zcosmic_toplevel_info_v1 — apps Wayland nativos detectáveis (${cosmic_linha})"
        elif [[ "${cosmic_linha}" == protocolo=nao* ]]; then
            info "compositor sem zcosmic_toplevel_info_v1 (não é COSMIC) — backend cosmic fora"
        elif command -v wayland-info >/dev/null 2>&1; then
            # O pacote instalado não tem o backend (instalação anterior a
            # 02/09/2026). A pergunta continua respondível.
            if WAYLAND_DISPLAY="${eff_wayland}" timeout 3 wayland-info 2>/dev/null \
                 | grep -q 'zcosmic_toplevel_info_v1'; then
                warn "o compositor PUBLICA zcosmic_toplevel_info_v1, mas o hefesto instalado não sabe usá-lo — atualize: $(conselho_de_instalacao)"
            else
                info "compositor sem zcosmic_toplevel_info_v1 (wayland-info) — backend cosmic fora"
            fi
        else
            info "não deu para perguntar pelo zcosmic_toplevel_info_v1 (sem python do produto e sem wayland-info)"
        fi
    fi

    # wlrctl (wlr-foreign-toplevel-management), que cobre o bloco wlroots.
    local wlrctl_ok=0 wlrctl_out="" wlrctl_rc=0
    if ! command -v wlrctl >/dev/null 2>&1; then
        info "wlrctl não instalado — backend wlrctl indisponível (irrelevante se o veredito abaixo for OK)"
    elif [[ -z "${eff_wayland}" ]]; then
        info "wlrctl instalado, mas sem WAYLAND_DISPLAY — nada a testar"
    else
        wlrctl_out="$(WAYLAND_DISPLAY="${eff_wayland}" timeout 3 wlrctl toplevel list 2>&1)"
        wlrctl_rc=$?
        if printf '%s' "${wlrctl_out}" | grep -qi 'toplevel management interface not found'; then
            info "compositor SEM wlr-foreign-toplevel-management (caso do cosmic-comp) — wlrctl instalado não ajuda aqui; quem cobre o COSMIC é o zcosmic_toplevel_info_v1, conferido acima"
        elif [[ "${wlrctl_rc}" -eq 0 ]]; then
            wlrctl_ok=1
            pass "wlrctl responde (wlr-foreign-toplevel-management OK)"
        else
            warn "wlrctl falhou (rc=${wlrctl_rc}): $(printf '%s' "${wlrctl_out}" | head -1)"
        fi
    fi

    # Veredito. O backend Wayland é qualquer um dos três: cosmic, portal ou wlrctl.
    local wayland_ok=0
    if [[ "${cosmic_ok}" -eq 1 || "${portal_ok}" -eq 1 || "${wlrctl_ok}" -eq 1 ]]; then
        wayland_ok=1
    fi
    if [[ "${xlib_ok}" -eq 1 && -z "${eff_wayland}" ]]; then
        pass "veredito: OK via xlib (sessão X11 pura — todas as janelas detectáveis)"
    elif [[ "${xlib_ok}" -eq 1 && "${wayland_ok}" -eq 1 ]]; then
        pass "veredito: OK via xlib + backend Wayland (cobertura total: jogos XWayland/Proton pelo xlib, apps Wayland nativos pelo compositor)"
    elif [[ "${xlib_ok}" -eq 1 ]]; then
        warn "veredito: DEGRADADO — só XWayland: jogos Proton/Steam e apps X11 são detectados (xlib), mas apps Wayland nativos aparecem como 'unknown'. Este compositor não publica nenhum dos três caminhos Wayland (zcosmic_toplevel_info_v1, portal XDG, wlr-foreign-toplevel-management)."
    elif [[ "${wayland_ok}" -eq 1 ]]; then
        pass "veredito: OK via backend Wayland (sessão Wayland pura — sem o nome do processo, que só o xlib resolve)"
    elif [[ -z "${eff_display}" && -z "${eff_wayland}" ]]; then
        fail "veredito: CEGO — sem DISPLAY e sem WAYLAND_DISPLAY (nem no systemd --user). Se o daemon subiu antes do login gráfico, reinicie: systemctl --user restart ${APP_ID}.service"
    else
        fail "veredito: CEGO — há display no ambiente mas nenhum backend funciona (X inacessível, compositor sem zcosmic_toplevel_info_v1, portal sem GetActiveWindow, wlrctl sem protocolo); o autoswitch ficará no fallback e perfil-por-jogo não muda sozinho"
    fi
}

# Caminho dos perfis. É o mesmo que `utils.xdg_paths.profiles_dir` resolve
# (platformdirs = XDG_CONFIG_HOME, com ~/.config de default) — lido do DISCO
# de propósito: o diagnóstico dos perfis tem de funcionar com o daemon parado,
# que é justamente quando a mantenedora vai olhar por que um perfil não entra.
profiles_dir_path() {
    printf '%s/%s/profiles' "${XDG_CONFIG_HOME:-${HOME}/.config}" "${APP_ID}"
}

# R-12 item 3 (débito da auditoria 23/07): classifica cada perfil do diretório
# em uma linha `estado<TAB>arquivo<TAB>nome`. Função PURA (recebe o diretório,
# só imprime) para ser exercitada por teste com um diretório sintético.
#
# Estados:
#   inalcancavel — `criteria` com os TRÊS campos vazios. `MatchCriteria.matches`
#                  devolve False sem condição alguma, então o autoswitch NUNCA
#                  escolhe esse perfil. Foi assim que o preset `coop_local` de
#                  fábrica passou meses sem nunca ativar, sem erro nenhum.
#   manual       — sentinel `{"type": "manual"}`: a MESMA inércia, só que
#                  declarada. Não é defeito, e por isso sai como informação.
#   ilegivel     — JSON quebrado (o daemon já pula com WARN no boot; aqui é
#                  para o item não sumir do relatório em silêncio).
# Perfil `any` e `criteria` com alvo não saem: são os casos sãos.
_perfis_inalcancaveis() {
    local dir="${1:-}"
    [[ -n "${dir}" ]] || dir="$(profiles_dir_path)"
    [[ -d "${dir}" ]] || return 0
    command -v python3 >/dev/null 2>&1 || return 0
    python3 - "${dir}" <<'PYEOF' 2>/dev/null
import json
import sys
from pathlib import Path

for path in sorted(Path(sys.argv[1]).glob("*.json")):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"ilegivel\t{path.name}\t{type(exc).__name__}")
        continue
    if not isinstance(data, dict):
        print(f"ilegivel\t{path.name}\tjson não é um objeto")
        continue
    nome = str(data.get("name") or path.stem)
    match = data.get("match")
    tipo = match.get("type") if isinstance(match, dict) else None
    if tipo == "manual":
        print(f"manual\t{path.name}\t{nome}")
    elif tipo == "criteria" and not (
        match.get("window_class")
        or match.get("window_title_regex")
        or match.get("process_name")
    ):
        print(f"inalcancavel\t{path.name}\t{nome}")
PYEOF
}

# R-12 item 3: o relatório de linha de comando do que a GUI já mostra na coluna
# "Quando usar" ("Só manual (nunca ativa sozinho)"). Um perfil sem alvo não
# falha, não loga e não aparece em lugar nenhum — ele simplesmente nunca entra,
# e a leitura de quem está do lado de cá é "o autoswitch está quebrado".
check_perfis_inalcancaveis() {
    local dir; dir="$(profiles_dir_path)"
    if [[ ! -d "${dir}" ]]; then
        info "sem diretório de perfis ainda (${dir}) — os presets nascem no primeiro boot do daemon"
        return
    fi
    if ! command -v python3 >/dev/null 2>&1; then
        warn "python3 ausente — não dá para ler os perfis"
        return
    fi
    local linhas total mortos="" manuais="" ilegiveis=""
    total="$(find "${dir}" -maxdepth 1 -name '*.json' -type f 2>/dev/null | wc -l)"
    linhas="$(_perfis_inalcancaveis "${dir}")"
    local estado arquivo nome
    while IFS=$'\t' read -r estado arquivo nome; do
        [[ -n "${estado}" ]] || continue
        case "${estado}" in
            inalcancavel) mortos+=" ${nome} (${arquivo})" ;;
            manual)       manuais+=" ${nome}" ;;
            ilegivel)     ilegiveis+=" ${arquivo} [${nome}]" ;;
        esac
    done <<< "${linhas}"

    if [[ -n "${ilegiveis}" ]]; then
        warn "perfil ilegível (o daemon pula com WARN no boot):${ilegiveis}"
    fi
    if [[ -n "${mortos}" ]]; then
        warn "perfil INALCANÇÁVEL pelo autoswitch — nenhum critério de janela:${mortos}. Ele só entra se você ativar na mão. Cura: abra a aba Perfis e dê um alvo (programa, jogo da Steam ou título), ou declare de propósito com \"match\": {\"type\": \"manual\"} no JSON"
    fi
    if [[ -n "${manuais}" ]]; then
        info "perfil só-manual por declaração (nunca ativa sozinho, e está certo assim):${manuais}"
    fi
    if [[ -z "${mortos}" && -z "${ilegiveis}" ]]; then
        pass "perfis alcançáveis pelo autoswitch (${total} no disco, nenhum sem alvo por acidente)"
    fi
}

# ============================================================================
# Energia USB e rádio (onda PLATAFORMA 2026-07-18) — tudo READ-ONLY.
# Estudos: 2026-07-18-estudo-kernel-hardening.md + 2026-07-18-estudo-bt-maximo.md.
# ============================================================================

# PLAT-03 item 1: nenhum device USB pode estar em economia de energia — um
# controle/adaptador dormindo é queda na certa (a regra 81 mantém tudo 'on').
check_usb_power_devices() {
    local dev ctl vid nome bad=0 total=0 exemplos=""
    for dev in /sys/bus/usb/devices/*; do
        [[ -r "${dev}/power/control" && -r "${dev}/idVendor" ]] || continue
        total=$((total + 1))
        ctl="$(cat "${dev}/power/control" 2>/dev/null)"
        if [[ "${ctl}" == "auto" ]]; then
            bad=$((bad + 1))
            vid="$(cat "${dev}/idVendor" 2>/dev/null)"
            nome="$(cat "${dev}/product" 2>/dev/null || true)"
            exemplos+=" $(basename "${dev}") (${vid} ${nome:-?})"
        fi
    done
    if [[ "${total}" -eq 0 ]]; then
        info "sem devices USB legíveis no sysfs — pulo o check de energia dos devices"
    elif [[ "${bad}" -eq 0 ]]; then
        pass "nenhum device USB em economia de energia (power/control=on em ${total}/${total})"
    else
        warn "economia de energia ATIVA em ${bad} device(s) USB:${exemplos} — a regra 81 deveria mantê-los 'on': sudo bash scripts/install_udev.sh (e replugue)"
    fi
}

# PLAT-03 item 3: o HOST xHCI em economia suspende o controlador PCI inteiro —
# num wake mal suportado o barramento TODO cai (teclado+mouse+controle juntos,
# visto em maio/2026). A regra 81-host mantém os hosts em 'on'.
check_usb_power_hosts() {
    local pci cls ctl found=0 bad=""
    for pci in /sys/bus/pci/devices/*; do
        cls="$(cat "${pci}/class" 2>/dev/null)" || continue
        [[ "${cls}" == 0x0c03* ]] || continue
        found=1
        ctl="$(cat "${pci}/power/control" 2>/dev/null)"
        [[ "${ctl}" != "on" ]] && bad+=" $(basename "${pci}")=${ctl:-?}"
    done
    if [[ "${found}" -eq 0 ]]; then
        info "nenhum host USB (classe PCI 0x0c03*) legível — pulo o check dos hosts"
    elif [[ -z "${bad}" ]]; then
        pass "hosts USB (xHCI) com power/control=on — o barramento inteiro não dorme"
    else
        warn "host(s) USB em economia:${bad} — a suspensão do CONTROLADOR derruba teclado, mouse e controle juntos; a regra 81-host corrige: sudo bash scripts/install_udev.sh"
    fi
}

# ASPM: a FONTE é o /proc/cmdline. ARMADILHA PROVADA (estudo 2026-07-18 §3):
# com pcie_aspm=off a policy do sysfs continua mostrando "[default]" — ela
# MENTE. NUNCA usar a policy sysfs como prova do off; quem confirma de verdade
# é o LnkCtl do lspci (exige sudo — fora do doctor).
check_pcie_aspm() {
    local tok policy
    tok="$(grep -o 'pcie_aspm=[^ ]*' /proc/cmdline 2>/dev/null | head -1)"
    if [[ -n "${tok}" ]]; then
        pass "ASPM definido no boot (${tok}) — lido do /proc/cmdline (a policy do sysfs mente com pcie_aspm=off; nunca a use como prova)"
        return
    fi
    policy="$(cat /sys/module/pcie_aspm/parameters/policy 2>/dev/null || true)"
    if [[ "${policy}" == *"[powersave]"* || "${policy}" == *"[powersupersave]"* ]]; then
        warn "sem pcie_aspm= no cmdline e policy de economia ativa (${policy}) — pode somar latência/instabilidade aos hosts USB; mudar é decisão do dono (ex.: pcie_aspm=off via kernelstub)"
    else
        info "sem pcie_aspm= no cmdline; policy ativa: ${policy:-ilegível} (informativo — a política é decisão do dono da máquina)"
    fi
}

# PLAT-03 item 4: caça a sabotadores de energia — ferramentas que RELIGAM o
# USB autosuspend por cima do udev. Nada é desinstalado; só instrução de exceção.
check_power_saboteurs() {
    local achados="" p
    if command -v dpkg-query >/dev/null 2>&1; then
        for p in tlp powertop tuned; do
            dpkg-query -W "$p" >/dev/null 2>&1 && achados+=" ${p}"
        done
    fi
    if [[ -n "${achados}" ]]; then
        warn "ferramenta(s) de economia presentes:${achados} — podem religar o USB autosuspend por cima do udev. Exceções: TLP → USB_DENYLIST=\"054c:0ce6 054c:0df2\"; powertop → NÃO use --auto-tune; tuned → evite perfis powersave (nada foi desinstalado)"
    else
        pass "sem TLP/powertop/tuned instalados (nenhum religador de economia USB)"
    fi
    # system76-power (Pop!_OS/COSMIC): não é inimigo dos controles (a regra 81
    # re-assert em 'change' defende o USB), mas o perfil importa em jogo — o
    # wrapper hefesto-launch pede Performance no launch e restaura no exit.
    if command -v systemctl >/dev/null 2>&1 \
       && systemctl is-active --quiet com.system76.PowerDaemon.service 2>/dev/null; then
        local prof=""
        command -v system76-power >/dev/null 2>&1 \
            && prof="$(timeout 3 system76-power profile 2>/dev/null | head -1 || true)"
        info "system76-power ativo (${prof:-perfil ilegível}) — o wrapper pede Performance durante o jogo e restaura o perfil ao sair"
    fi
    # Assinatura provada do system76-power no storage: link PM med_power_with_dipm.
    local h val achou=0
    for h in /sys/class/scsi_host/host*/link_power_management_policy; do
        [[ -r "${h}" ]] || continue
        val="$(cat "${h}" 2>/dev/null)"
        [[ "${val}" == med_power* ]] && achou=1
    done
    if [[ "${achou}" -eq 1 ]]; then
        info "storage com link PM em economia (med_power_with_dipm — assinatura do system76-power); não derruba os controles (USB defendido pela regra 81), mas mostra um agente de economia vivo"
    fi
}

# PLAT-04 item 1: o btusb liga o autosuspend do adaptador BT no probe (default
# do módulo). O conf do hefesto corta na raiz; esperado N pós-boot.
check_btusb_autosuspend() {
    local conf=/etc/modprobe.d/hefesto-btusb-no-autosuspend.conf
    local param=/sys/module/btusb/parameters/enable_autosuspend
    local val=""
    [[ -r "${param}" ]] && val="$(cat "${param}" 2>/dev/null)"
    if [[ "${val}" == "N" || "${val}" == "0" ]]; then
        pass "btusb sem autosuspend (enable_autosuspend=N) — o rádio dos controles não dorme"
    elif [[ -f "${conf}" ]]; then
        if [[ -z "${val}" ]]; then
            info "modprobe.d do btusb instalado; módulo btusb não carregado agora (sem adaptador BT?)"
        else
            info "modprobe.d do btusb instalado, mas o módulo ainda está com enable_autosuspend=${val} — vale no próximo probe (replug do adaptador BT ou reboot); o runtime já é coberto pela regra 81"
        fi
    else
        warn "btusb com autosuspend LIGADO (enable_autosuspend=${val:-?}) e sem o conf do hefesto — em máquina sem usbcore.autosuspend=-1 global o rádio dos controles dorme; $(conselho_de_instalacao)$(so_no_checkout "(o conf entra por default)")"
    fi
}

# PLAT-04 item 3: FastConnectable = reconexão entrante mais rápida (botão PS).
#
# RADIO-ABERTO-01/E1-bis (06/08/2026): esta função só conhecia a sentinela
# LEGADA `# >>> hefesto FastConnectable >>>`, que o bloco unificado (escrito
# por todo install desde 21/07) NÃO tem. Reproduzi a cadeia de ramos na máquina
# dela: caía no ramo do grep genérico e imprimia "FastConnectable já
# configurado por TERCEIRO no main.conf" — o doctor atribuía a um terceiro o
# bloco que este projeto tinha acabado de escrever. O alternador cobre as três
# sentinelas e o doctor volta a saber de quem é o bloco.
check_bluez_fastconnectable() {
    local dropin=/etc/bluetooth/main.conf.d/hefesto-fastconnectable.conf
    if [[ -f "${dropin}" ]]; then
        pass "FastConnectable do BlueZ instalado (drop-in main.conf.d) — botão PS reconecta mais rápido (vale desde o último start do bluetoothd)"
    elif grep -qsE '^# >>> hefesto (bluetooth|FastConnectable) >>>' /etc/bluetooth/main.conf 2>/dev/null; then
        pass "FastConnectable do BlueZ instalado (bloco marcado hefesto no main.conf) — vale desde o último start do bluetoothd"
    elif grep -qsE '^[[:space:]]*FastConnectable[[:space:]]*=[[:space:]]*true' /etc/bluetooth/main.conf 2>/dev/null; then
        pass "FastConnectable já configurado por terceiro no main.conf"
    elif [[ ! -e /etc/bluetooth/main.conf ]]; then
        info "sem /etc/bluetooth/main.conf (BlueZ ausente?) — pulo o check de FastConnectable"
    else
        warn "reconexão rápida BT (FastConnectable) não configurada — $(conselho_de_instalacao)$(so_no_checkout "(entra por default, SEM restart do bluetoothd)")"
    fi
}

# RADIO-ABERTO-01/E1-bis (06/08/2026) — O DETECTOR QUE NÃO EXISTIA.
#
# Até hoje o `doctor.sh` mencionava `JustWorksRepairing` ZERO vezes (grep fecha
# a conta). Foi essa cegueira, somada ao check acima que mentia sobre a
# autoria do bloco, que deixou `JustWorksRepairing=always` viver quatro dias em
# /etc/bluetooth/main.conf DEPOIS de a sprint declarar a E1 "FEITA": o valor
# seguro estava no repositório e ninguém tinha como ver que não estava no disco.
#
# `always` remove a ÚLTIMA recusa do BlueZ ao re-pareamento por Just Works de
# quem já tem bond. Com o agente NoInputNoOutput e o FastConnectable, quem
# clonar o BD_ADDR de um controle bondado sobrescreve a LinkKey sem interação
# humana — e o device que sobe escolhe o próprio descritor HID, que pode ser um
# TECLADO. Por isso o veredito aqui é `fail`, não `warn`.
#
# O segundo ramo é a contrapartida honesta da cura: `confirm` aceita SÓ se
# houver agente registrado, enquanto `always` aceitava sem depender de ninguém.
# A troca transfere peso para o `hefesto-bt-agent.service`, uma unit que já
# falhou duas vezes em 04/08 (BT-AGENT-TRAVA-O-RESTART-01 e
# BT-AGENT-MORTO-FICA-MORTO-01). Com o agente morto, o re-pareamento legítimo
# dela para de funcionar — e é o doctor que tem de dizer isso antes que ela
# descubra pelo controle que não conecta.
#
# QUEM LÊ O VALOR (06/08/2026): `scripts/bluez_config.sh verificar`, e só ele.
# A primeira versão desta função REIMPLEMENTAVA aqui o mesmo `sed` do dono da
# config — duas fontes para a mesma regra, que é exatamente a classe de defeito
# que esta leva veio fechar (a lógica morava dentro do install.sh, ninguém
# conseguia exercitá-la, e o `always` viveu quatro dias). O `verificar` é modo
# de leitura pura, e aqui roda com `HEFESTO_BT_SUDO=""` de propósito: um
# diagnóstico não pede senha. Se o arquivo estiver ilegível, ele diz
# `ilegível` — e nós dizemos também, em vez de inventar "não declarado".
#
# POR QUE A RAIZ É VARIÁVEL AQUI (06/08/2026): a raiz vinha literal
# (`/etc/bluetooth/main.conf`), e era isso que tornava esta função INTESTÁVEL —
# nenhuma bancada pode exercitá-la contra o /etc de verdade, e por isso os dois
# únicos testes que existiam eram grep de TEXTO no doctor.sh. MEDIDO: trocar o
# `fail` do ramo `always` por `pass` deixava a suíte INTEIRA verde (138 passed),
# e apagar a CHAMADA em `main()` também — o detector de segurança podia ser
# invertido ou desligado sem uma linha vermelha. Com a raiz saindo de
# `HEFESTO_BT_ETC` (o mesmo override que o dono único já usa; em produção fica
# no padrão), `tests/unit/test_doctor_justworks_comportamento.py` roda os cinco
# ramos DE VERDADE contra uma raiz falsa, e as duas mutações ficam vermelhas.
check_bluez_justworks_repairing() {
    local dono="${ROOT_DIR}/scripts/bluez_config.sh" valor state
    local etc_bt="${HEFESTO_BT_ETC:-/etc/bluetooth}"
    # "NÃO EXISTE" e "NÃO CONSIGO VER" são respostas diferentes, e o doctor
    # dizia a primeira nos dois casos (achado de 06/08/2026).
    #
    # Dentro de um Flatpak sem `--filesystem=host` — que é o caso do nosso
    # manifesto — `/etc/bluetooth` simplesmente NÃO EXISTE no sandbox: o /etc do
    # host não é alcançável. O ramo abaixo caía no `info ... pulo o check`, que
    # não é WARN nem FAIL, numa máquina cujo HOST tem `JustWorksRepairing=always`
    # ativo. Pior que o caso do .deb, que ao menos avisava com WARN. Silêncio
    # sobre injeção de teclas é o defeito que abriu esta sprint, de costas.
    #
    # O marcador é `/.flatpak-info`, que o próprio flatpak monta em todo
    # sandbox; `FLATPAK_ID`, `SNAP` e `/run/.containerenv` cobrem os vizinhos.
    # Os dois caminhos saem de variável para a bancada poder exercitá-los sem
    # container nenhum — mesma escola do `HEFESTO_BT_ETC`.
    local marca_flatpak="${HEFESTO_MARCA_SANDBOX:-/.flatpak-info}"
    local marca_container="${HEFESTO_MARCA_CONTAINER:-/run/.containerenv}"
    local em_sandbox=0
    if [[ -e "${marca_flatpak}" || -e "${marca_container}" \
          || -n "${FLATPAK_ID:-}" || -n "${SNAP:-}" ]]; then
        em_sandbox=1
    fi
    if [[ ! -e "${etc_bt}/main.conf" && "${em_sandbox}" -eq 1 ]]; then
        warn "NÃO SEI o valor de JustWorksRepairing nesta máquina: estou num sandbox (Flatpak/Snap/container) e o /etc do host não é alcançável daqui — ${etc_bt}/main.conf não existe DENTRO do sandbox, o que não diz nada sobre o host. Rode o doctor FORA do pacote: bash scripts/doctor.sh, ou sudo bash scripts/bluez_config.sh verificar"
        return
    fi
    if [[ ! -e "${etc_bt}/main.conf" ]]; then
        info "sem ${etc_bt}/main.conf (BlueZ ausente?) — pulo o check de JustWorksRepairing"
        return
    fi
    if [[ ! -f "${dono}" ]]; then
        warn "scripts/bluez_config.sh ausente — o dono único da config do BlueZ não está aqui, e não leio JustWorksRepairing por fora dele"
        return
    fi
    valor="$(HEFESTO_BT_SUDO="" bash "${dono}" verificar 2>/dev/null \
        | sed -n 's/^JustWorksRepairing: //p' || true)"
    case "${valor}" in
        confirm)
            pass "JustWorksRepairing=confirm no main.conf — re-pareamento de quem já tem bond passa pelo agente (RADIO-ABERTO-01)"
            # SELO-VERDE-CEDO-DEMAIS-01 (06/08/2026, achado de verificação
            # adversarial): dizer só "confirm no main.conf" carimbava VERDE um
            # rádio ainda ABERTO. O `bluez_config.sh` grava e NÃO reinicia o
            # bluetoothd de propósito (derrubaria os controles conectados), e diz
            # isso por escrito: "VALEM NO PRÓXIMO BOOT". Entre a cura e o próximo
            # start, o daemon VIVO segue com `always` — e quem lesse este `[ OK ]`
            # fecharia o terminal achando que a janela de Just Works fechou.
            #
            # Em vez de só ressalvar, MEDIMOS: se o main.conf é mais novo que o
            # start do bluetoothd, o disco ainda não é o que o daemon carregou.
            # O irmão FastConnectable já dizia "vale desde o último start" — a
            # ressalva existia no arquivo e faltava logo na chave de segurança.
            _t_conf="$(stat -c %Y "${etc_bt}/main.conf" 2>/dev/null || echo 0)"
            # `HEFESTO_BT_ATIVO_DESDE` existe para a bancada morder os DOIS
            # ramos (o `systemctl` de mentira dela não tem relógio). Em produção
            # nunca vem definida, e o valor sai do systemd logo abaixo.
            _t_bluez="${HEFESTO_BT_ATIVO_DESDE:-}"
            if [[ -z "${_t_bluez}" ]]; then
                _ts_bluez="$(systemctl show bluetooth.service \
                    -p ActiveEnterTimestamp --value 2>/dev/null || true)"
                # `date -d ""` NÃO falha: o GNU date devolve MEIA-NOITE DE HOJE
                # (medido em 06/08/2026). Sem esta guarda, toda máquina em que o
                # `bluetooth.service` não reporta — inativo, mascarado, container
                # sem systemd — comparava o `main.conf` contra meia-noite, e o
                # aviso saía em falso para qualquer arquivo tocado no dia. O
                # `|| echo 0` original não protegia nada, porque não havia erro.
                if [[ -n "${_ts_bluez//[[:space:]]/}" ]]; then
                    _t_bluez="$(date -d "${_ts_bluez}" +%s 2>/dev/null || echo 0)"
                else
                    _t_bluez=0
                fi
            fi
            if [[ "${_t_conf}" -gt 0 && "${_t_bluez}" -gt 0 \
                  && "${_t_conf}" -gt "${_t_bluez}" ]]; then
                warn "o main.conf mudou DEPOIS do último start do bluetoothd — o daemon VIVO ainda roda com o valor anterior, e o rádio só fecha no próximo boot (ou com 'sudo systemctl restart bluetooth', que derruba os controles conectados agora)"
            fi
            state="$(systemctl is-active hefesto-bt-agent.service 2>/dev/null || true)"
            if [[ "${state}" != "active" ]]; then
                # BG-06 (25/08/2026) — O GRAU ESTAVA ERRADO, E O CUSTO ERA
                # CONCRETO. Esta cena saía `warn`, e um aviso no meio de
                # centenas de linhas SOME. Mas o que ela descreve não é um
                # risco à espreita: é o produto parado na coisa principal.
                # `confirm` só aceita o Just Works repairing se um agente
                # registrado confirmar; sem agente não há quem confirme, e o
                # BlueZ recusa. O par (`confirm` + agente morto) é o ÚNICO
                # lugar do exame que conhece os dois fatos ao mesmo tempo —
                # `check_bt_agent_service` vê só o agente, e por isso segue
                # avisando sobre o bond meio-salvo em vez de reprovar aqui de
                # novo (duas réguas para o mesmo veredito é a duplicação que
                # esta casa persegue).
                #
                # DECLARADO COMO INFERÊNCIA: não há DualSense nesta bancada
                # (25/08/2026, os quatro hidraw são teclado e mouse). O
                # veredito vem do contrato do BlueZ e do histórico desta unit
                # (BT-AGENT-TRAVA-O-RESTART-01 e BT-AGENT-MORTO-FICA-MORTO-01,
                # 04/08), não de um pareamento medido com o agente morto. A
                # frase diz o que o BlueZ FAZ, não o que o controle dela fez.
                fail "pareamento por rádio PARADO: JustWorksRepairing=confirm só aceita com um agente registrado para confirmar, e o hefesto-bt-agent.service está ${state:-ausente} — sem ele o BlueZ RECUSA o re-pareamento ('Refusing connection from ...') e nenhum controle volta a entrar por Bluetooth. Ligue: sudo systemctl enable --now hefesto-bt-agent.service"
            fi
            ;;
        always)
            fail "JustWorksRepairing=always ATIVO no ${etc_bt}/main.conf — remove a última recusa do BlueZ ao re-pareamento por Just Works de quem já tem bond; com o agente NoInputNoOutput isso termina em injeção de teclas (RADIO-ABERTO-01). Cura, em qualquer formato: sudo bash ${dono} aplicar — corrige o bloco antigo do hefesto SEM reiniciar o bluetoothd$(so_no_checkout "— o ./install.sh SEM --no-udev faz o mesmo (a flag pula este passo inteiro)")"
            ;;
        ausente|"")
            warn "JustWorksRepairing não está declarado no main.conf — o BlueZ cai no default da distro, que não é decisão desta casa; cura em qualquer formato: sudo bash ${dono} aplicar$(so_no_checkout "— o ./install.sh também aplica, por default, mas NÃO com --no-udev, que pula este passo")"
            ;;
        ilegível)
            warn "não consigo LER ${etc_bt}/main.conf — sem leitura não sei o valor de JustWorksRepairing; rode: sudo bash ${dono} verificar"
            ;;
        recusado)
            # Achado de 06/08/2026: uma linha malformada em QUALQUER ponto do
            # arquivo faz o GKeyFile abortar a carga, e o bluetoothd fica sem
            # config nenhuma — nem a nossa. Antes, o dono lia a chave normal e o
            # doctor dava selo verde a um arquivo que o BlueZ descarta inteiro.
            fail "${etc_bt}/main.conf tem uma linha que o parser do bluetoothd (GKeyFile) RECUSA, e uma linha recusada invalida o ARQUIVO INTEIRO: o BlueZ fica sem config nenhuma — nem JustWorksRepairing, nem FastConnectable, nem o que já era dela. Veja qual linha é e conserte-a à mão: bash ${dono} verificar"
            ;;
        never)
            # A PROMESSA AQUI ERA FALSA NA METADE DOS CASOS (06/08/2026): dizia
            # sem ressalva que "a sua linha é neutralizada, e 'remover' a
            # devolve". Só vale FORA do bloco hefesto. DENTRO do bloco — que é
            # onde quem lê este aviso vai escrever, porque é onde a chave já
            # está — a faixa inteira é reescrita, nenhuma marca é gravada e o
            # `remover` entrega o arquivo SEM a chave. O `aplicar` sabe dizer
            # qual dos dois casos é o dela (ele lê a posição da linha que vence);
            # o doctor não precisa saber, precisa é não prometer o que não pode.
            warn "JustWorksRepairing=never no main.conf — é MAIS restritivo que o 'confirm' desta casa (recusa todo re-pareamento de quem já tem bond). Se foi escolha sua, NÃO deixe esta casa reescrever o valor: 'sudo bash ${dono} aplicar' rebaixa para 'confirm'$(so_no_checkout "— e o ./install.sh também"). E confira ONDE a sua linha está: FORA das sentinelas do hefesto ela é neutralizada e o 'bluez_config.sh remover' a devolve inteira; DENTRO do bloco ela é reescrita junto com o bloco e não volta (só o backup guarda)"
            ;;
        *)
            warn "JustWorksRepairing=${valor} no main.conf — esta casa instala 'confirm'; se o valor não foi escolha sua, $(conselho_de_instalacao)"
            ;;
    esac
}

# O "clone DS4" 054C:05C4 que stormou o rádio com 211 mil erros de CRC numa
# noite (estudo 2026-07-18 §2.1). Pelo OUI no cache do adaptador, é quase
# certamente um 8BitDo em modo D-input — o conselho é TROCAR O MODO/cabo, não
# jogar fora. (054C:05C4 também é o PID do DS4 v1 legítimo; o journal
# desempata: hw_version=0x00000000 denuncia o firmware clone.)
# WATCHDOG-FP-01 (22/07): consultas de estado BT saem do D-Bus — o
# bluetoothctl 5.86 one-shot é mudo (COMPAT BLUEZ-586-CTL-01) e `timeout N
# bluetoothctl ...` invoca o BINÁRIO, pulando a função-sombra acima; foi
# assim que a caça ao clone e o check de rádio ficaram cegos (4 controles
# Trusted=false e nenhum aviso).
_dbus_bt_device_paths() {
    busctl tree org.bluez --list 2>/dev/null \
        | grep -oE '/org/bluez/hci[0-9]+/dev_[0-9A-Fa-f_]+$' | sort -u || true
}
_dbus_bt_prop() {
    # $1=path  $2=interface  $3=propriedade → valor cru sem aspas (vazio se n/d)
    busctl get-property org.bluez "$1" "$2" "$3" 2>/dev/null \
        | sed -e 's/^[a-z]* //' -e 's/^"//' -e 's/"$//' || true
}

# MIGRACAO-BLUEZ-DEPRECIADOS-01 (19/08/2026) — `hciconfig`, `hcitool` e
# `sdptool` foram DEPRECIADOS pela upstream do BlueZ, e cada família de distro
# os mudou de pacote (`bluez-deprecated`, `bluez-deprecated-tools`). Em quem não
# os tem, o `command -v` falhava e o check inteiro SUMIA da saída: a conferência
# saía verde sem ter medido nada. Mentir por omissão é pior que não medir.
#
# A ordem, daqui em diante, é sempre a mesma:
#   1. fonte VIVA  — sysfs (kernel) e D-Bus do BlueZ (a regra do WATCHDOG-FP-01
#      já mandava consulta de estado BT sair do D-Bus, porque o `bluetoothctl`
#      one-shot do 5.86 é mudo nesta casa — COMPAT BLUEZ-586-CTL-01);
#   2. `btmgmt`    — a ferramenta que a upstream indica no lugar das três;
#   3. depreciada  — plano B, para não perder leitura em quem AINDA a tem;
#   4. e quando NENHUMA responde, o doctor DIZ que não sabe.
#
# O que NÃO tem sucessor vivo (conferido nos `--help` do bluez 5.86 desta casa,
# 19/08/2026 — nem `btmgmt` nem `bluetoothctl` têm comando equivalente):
#   - contadores RX/TX errors do adaptador (só o ioctl HCIGETDEVINFO os entrega,
#     e só o `hciconfig` o chama);
#   - link policy, do adaptador (`hciconfig lp`) e da conexão (`hcitool lp`);
#   - browse SDP sob demanda num device (`sdptool browse`).
# Onde essas três aparecem, o código diz "não sei" em vez de inventar.

# Adaptadores HCI, um por linha ("hci0"). Fonte viva: /sys/class/bluetooth, que
# é o kernel e não depende de pacote nenhum. O filtro `^hci[0-9]+$` existe
# porque ali também nascem as entradas de CONEXÃO, no formato "hci0:256".
#
# HEFESTO_BT_SYSFS_ROOT (opcional, env var) — raiz do sysfs, default
# /sys/class/bluetooth. Não é parâmetro posicional porque quem chama esta
# função em produção (`check_bt_resilience`, `check_bt_radio`) não recebe
# root nenhum para repassar; env var atravessa a cadeia de chamada sem
# precisar editar todo mundo no meio. Achado em 24/08/2026: sem isto, um
# teste que só troca o PATH (`sandbox_sem_velhas`) não consegue esconder
# Bluetooth físico de verdade — `tests/unit/test_migracao_bluez_depreciados.py`
# vermelho numa bancada com adaptadores reais plugados, porque esta função
# lia o sysfs REAL por baixo do sandbox de PATH do teste.
_bt_adaptadores() {
    local raiz="${HEFESTO_BT_SYSFS_ROOT:-/sys/class/bluetooth}"
    local p nome achou=0 lista
    for p in "${raiz}"/hci*; do
        [[ -e "${p}" ]] || continue
        nome="${p##*/}"
        [[ "${nome}" =~ ^hci[0-9]+$ ]] || continue
        printf '%s\n' "${nome}"
        achou=1
    done
    [[ "${achou}" -eq 1 ]] && return 0
    if command -v busctl >/dev/null 2>&1; then
        lista="$(busctl tree org.bluez --list 2>/dev/null \
            | grep -oE '/org/bluez/hci[0-9]+' | sed 's#.*/##' | sort -u || true)"
        if [[ -n "${lista}" ]]; then
            printf '%s\n' "${lista}"
            return 0
        fi
    fi
    command -v hciconfig >/dev/null 2>&1 || return 0
    hciconfig 2>/dev/null | awk -F: '/^hci/{print $1}' || true
}

# Este adaptador hospeda um controle da linhagem Nintendo? (N-IGUAL-A-UM-01)
#
# É a MESMA pergunta que o `bt_active_mode.sh` faz para decidir onde pôr o
# prefixo, e por isso o exame só pode cobrar o prefixo de quem ela responde SIM.
# As duas fontes são as mesmas de lá, e a ordem importa:
#
#   1. o D-Bus, que sabe do controle CONECTADO agora;
#   2. os BONDS em disco, que sabem do controle pareado e DESLIGADO — e é essa
#      metade que faz a proteção valer ANTES do link subir, que é justamente
#      quando o Pro precisa dela.
#
# A régua de "é da linhagem" é do produto, não deste arquivo:
# `core/linhagem_nintendo.py` é o dono, e o portão de paridade entre os dois é
# `tests/unit/test_o_no_sniff_alcanca_todo_pro.py`.
#
# ATÉ 25/08/2026 A FRASE ACIMA ERA FALSA, e é por isso que ela ganhou o nome do
# arquivo: o comentário afirmava o portão, portão nenhum lia estas listas, e elas
# JÁ TINHAM DERIVADO — havia aqui um `98:B6:E9:*` escrito à mão que não existe em
# lugar nenhum do produto. Um comentário que promete um portão inexistente é pior
# que nenhum comentário: ele desencoraja a conferência que teria achado a
# divergência. A faixa saiu (um Pro dela entra pelo NOME, como qualquer Pro de
# safra que esta bancada nunca viu) e as listas viraram cópia pinada.
#
# Sem privilégio: o D-Bus responde a uid 1000, e o `/var/lib/bluetooth` é lido
# best-effort — quando ele não abre, sobra a primeira fonte e o exame diz o que
# sabe em vez de inventar.
#
# CÓPIA PINADA, e o motivo de existir cópia: o doctor roda como usuário comum,
# em máquina que pode não ter o venv da casa de pé — é o exame que a pessoa roda
# JUSTAMENTE quando algo não está de pé.
OUIS_CLONE=("e4:17:d8")
OUIS_NINTENDO_VISTAS=("e0:f6:b5")
NOMES_PRO=("pro controller")
NOMES_LINHAGEM=("pro controller" "nintendo" "8bitdo")

# Genuíno OU clone — os dois leem o nome Bluetooth do host, e é essa a pergunta
# que decide se um adaptador precisa do prefixo.
_bt_e_da_linhagem() {  # $1 = MAC · $2 = nome
    local mac="${1,,}" nome="${2,,}" marca
    for marca in "${OUIS_NINTENDO_VISTAS[@]}" "${OUIS_CLONE[@]}"; do
        [[ "${mac}" == "${marca}"* ]] && return 0
    done
    for marca in "${NOMES_LINHAGEM[@]}"; do
        [[ "${nome}" == *"${marca}"* ]] && return 0
    done
    return 1
}

# SÓ o genuíno — a pergunta do NO-SNIFF, por NEGATIVA. Mesma ordem do
# `bt_nosniff_now.sh` e do `bt_active_mode.sh`: clone recusa, faixa já vista
# aplica sem nome, nome com cara de Pro aplica.
_bt_e_pro_genuino() {  # $1 = MAC · $2 = nome
    local mac="${1,,}" nome="${2,,}" marca
    for marca in "${OUIS_CLONE[@]}"; do
        [[ "${mac}" == "${marca}"* ]] && return 1
    done
    for marca in "${OUIS_NINTENDO_VISTAS[@]}"; do
        [[ "${mac}" == "${marca}"* ]] && return 0
    done
    for marca in "${NOMES_PRO[@]}"; do
        [[ "${nome}" == *"${marca}"* ]] && return 0
    done
    return 1
}

# O nome deste controle, para quem só tem o endereço. Vazio quando não há de
# onde tirar — e vazio NÃO é "não é um Pro".
_bt_nome_do_controle() {  # $1 = MAC -> nome, ou vazio
    local mac="${1^^}" caminho nome
    if command -v busctl >/dev/null 2>&1; then
        caminho="$(busctl tree org.bluez --list 2>/dev/null \
            | grep -oE "/org/bluez/hci[0-9]+/dev_${mac//:/_}$" | head -1 || true)"
        if [[ -n "${caminho}" ]]; then
            nome="$(busctl get-property org.bluez "${caminho}" org.bluez.Device1 Alias 2>/dev/null \
                | sed -E 's/^s "?//; s/"?$//' || true)"
            [[ -n "${nome}" ]] && { printf '%s\n' "${nome}"; return 0; }
        fi
    fi
    sed -n 's/^Name=//p' /var/lib/bluetooth/*/"${mac}"/info 2>/dev/null | head -1 || true
}

_bt_hospeda_linhagem() {
    local alvo="$1" caminho mac nome dir end
    [[ -n "${alvo}" ]] || return 1
    if command -v busctl >/dev/null 2>&1; then
        while IFS= read -r caminho; do
            [[ -n "${caminho}" ]] || continue
            [[ "${caminho}" == "/org/bluez/${alvo}/dev_"* ]] || continue
            mac="${caminho##*/dev_}"; mac="${mac//_/:}"
            nome="$(busctl get-property org.bluez "${caminho}" org.bluez.Device1 Alias 2>/dev/null \
                | sed -E 's/^s "?//; s/"?$//' || true)"
            _bt_e_da_linhagem "${mac}" "${nome}" && return 0
        done <<<"$(busctl tree org.bluez --list 2>/dev/null \
            | grep -oE "/org/bluez/${alvo}/dev_[0-9A-Fa-f_]+$" | sort -u || true)"
    fi
    end="$(cat "/sys/class/bluetooth/${alvo}/address" 2>/dev/null | tr 'a-f' 'A-F' || true)"
    [[ -n "${end}" ]] || return 1
    dir="/var/lib/bluetooth/${end}"
    [[ -d "${dir}" ]] || return 1
    for caminho in "${dir}"/*/info; do
        [[ -e "${caminho}" ]] || continue
        mac="${caminho%/info}"; mac="${mac##*/}"
        nome="$(grep -m1 '^Name=' "${caminho}" 2>/dev/null | cut -d= -f2- || true)"
        _bt_e_da_linhagem "${mac}" "${nome}" && return 0
    done
    return 1
}

# MACs com ACL de pé, um por linha, MAIÚSCULAS com ':'. Substitui o `hcitool
# con`. Fonte viva: o D-Bus do BlueZ (Device1.Connected). Plano B: `btmgmt con`
# (precisa de CAP_NET_ADMIN — daqui, sem root, costuma vir vazio). Plano C: o
# `hcitool con` depreciado, que ainda responde mesmo com o bluetoothd parado.
_bt_macs_conectados() {
    local p mac saida="" achou=0
    if command -v busctl >/dev/null 2>&1; then
        while IFS= read -r p; do
            [[ -z "${p}" ]] && continue
            [[ "$(_dbus_bt_prop "${p}" org.bluez.Device1 Connected)" == "true" ]] || continue
            mac="${p##*/dev_}"
            printf '%s\n' "${mac//_/:}"
            achou=1
        done <<<"$(_dbus_bt_device_paths)"
        [[ "${achou}" -eq 1 ]] && return 0
    fi
    if command -v btmgmt >/dev/null 2>&1; then
        saida="$(timeout 5 btmgmt con 2>/dev/null \
            | grep -oE '([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}' || true)"
        if [[ -n "${saida}" ]]; then
            printf '%s\n' "${saida^^}"
            return 0
        fi
    fi
    command -v hcitool >/dev/null 2>&1 || return 0
    saida="$(hcitool con 2>/dev/null \
        | grep -oE '([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}' || true)"
    [[ -n "${saida}" ]] && printf '%s\n' "${saida^^}"
    return 0
}

check_bt_clone_ds4() {
    command -v busctl >/dev/null 2>&1 || { info "busctl ausente — pulo a caça ao clone DS4"; return; }
    local paths p mac modalias clone=0
    paths="$(_dbus_bt_device_paths)"
    if [[ -z "${paths}" ]]; then
        info "nenhum dispositivo Bluetooth pareado — sem clone DS4 possível"
        return
    fi
    while IFS= read -r p; do
        [[ -z "${p}" ]] && continue
        mac="${p##*dev_}"; mac="${mac//_/:}"
        modalias="$(_dbus_bt_prop "${p}" org.bluez.Device1 Modalias)"
        if printf '%s' "${modalias}" | grep -q 'usb:v054Cp05C4'; then
            clone=1
            # NOTA DATADA — 23/08/2026. Este aviso tinha TRÊS afirmações e duas
            # caíram com medição da própria casa:
            #
            # 1. a que dizia que o clone degradava o rádio dos OUTROS
            #    controles — REFUTADA por
            #    controle negativo em 04/08 (RADIO-BOMBARDEADO-01): na janela de
            #    23:51 a 23:58 o clone despejou 26.884 erros de CRC e produziu
            #    ZERO frames L2CAP corrompidos. A LUGAR-À-MESA-01 registrou a
            #    refutação em 06/08 e o texto aqui não mudou por 17 dias.
            # 2. "troque o modo (Switch)" — para um aparelho PAREADO, que é o
            #    caso deste laço, o conselho manda para o modo que a casa mediu
            #    como PIOR: Switch por rádio é "PROVADO instável" e
            #    DirectInput/PS4 (que é justamente este 054C:05C4) é o
            #    RECOMENDADO por rádio (docs/usage/troubleshooting-8bitdo.md:35-37).
            #
            # O que sobrou é verdadeiro e medido: o firmware não calcula a
            # verificação de integridade e enche o diário do kernel de erros.
            # Isso atrapalha quem lê o diário, não o rádio de quem joga.
            warn "controle 'tipo DualShock 4' (054C:05C4) pareado (${mac}) — esse firmware não calcula a verificação de integridade e enche o diário do kernel de erros de CRC"
            info "  provavelmente é um 8BitDo em modo DirectInput/PS4, que é o modo RECOMENDADO por rádio — não troque para Switch sem o cabo, que por rádio é instável"
            info "  o barulho fica no diário: 26.884 erros de CRC mediram ZERO frames corrompidos (RADIO-BOMBARDEADO-01, 04/08)"
            info "  para desparear: bluetoothctl remove ${mac}  (se for um DS4 v1 legítimo, o journal desempata: 'hw_version=0x00000000' = clone)"
        fi
    done <<<"${paths}"
    [[ "${clone}" -eq 0 ]] && pass "nenhum clone DS4 (054C:05C4) pareado"
}

# O RÁDIO DESLIGADO POR SOFTWARE (O-QUE-E-DO-HEFESTO-SAI-DO-ZSH-01, 23/09/2026).
# Morava no self-heal do zsh dela (`audit_bluetooth_rfkill`), uma linha por hora
# num log que ninguém lê, e olhava só o primeiro adaptador. Veio para cá porque é
# a resposta à pergunta que ninguém faz: com o adaptador soft-blocked, o
# `bluetoothctl devices` vem vazio e tudo parece «sem adaptador» — o controle não
# conecta e nada diz por quê. O `systemd-rfkill` lembra o bloqueio POR PORTA USB
# (uma entrada por caminho em /var/lib/systemd/rfkill), então plugar o dongle na
# porta errada o traz desligado.
#
# LÊ ARQUIVO, não roda `rfkill` (a regra do doctor, no cabeçalho), e olha TODO
# adaptador. NUNCA desbloqueia: o botão de Bluetooth do painel faz exatamente
# este soft block, e desfazê-lo tiraria da pessoa o controle do próprio rádio.
check_bt_rfkill() {
    local raiz="${HEFESTO_BT_SYSFS_ROOT:-/sys/class/bluetooth}"
    local hci rf soft hard lido bloqueados=0 _hcis=() _lidos=() _sem_leitura=()
    mapfile -t _hcis < <(_bt_adaptadores)
    if [[ "${#_hcis[@]}" -eq 0 ]]; then
        info "nenhum adaptador Bluetooth presente — os controles só conectam pelo cabo (o dongle está na porta?)"
        return 0
    fi
    # A contagem é POR ADAPTADOR, e só conta o que foi LIDO: um adaptador sem
    # rfkill legível não é «ligado» — é «não sei». Somar os não lidos ao «ligado
    # em N» afirmaria o estado de um rádio que ninguém olhou.
    for hci in "${_hcis[@]}"; do
        lido=0
        for rf in "${raiz}/${hci}"/rfkill*; do
            [[ -r "${rf}/soft" && -r "${rf}/hard" ]] || continue
            soft="$(cat "${rf}/soft" 2>/dev/null)"
            hard="$(cat "${rf}/hard" 2>/dev/null)"
            [[ "${soft}" =~ ^[01]$ && "${hard}" =~ ^[01]$ ]] || continue
            lido=1
            if [[ "${hard}" == "1" ]]; then
                bloqueados=$((bloqueados + 1))
                warn "${hci} bloqueado pela chave física ou pela BIOS (rfkill hard) — nenhum controle conecta por ele até a chave voltar"
            elif [[ "${soft}" == "1" ]]; then
                bloqueados=$((bloqueados + 1))
                warn "${hci} desligado por software (rfkill soft) — parece «sem adaptador»: o controle não conecta e nada diz por quê. Ligue pelo botão de Bluetooth do painel ou: rfkill unblock bluetooth"
            fi
        done
        if [[ "${lido}" -eq 1 ]]; then
            _lidos+=("${hci}")
        else
            _sem_leitura+=("${hci}")
        fi
    done
    if [[ "${#_sem_leitura[@]}" -gt 0 ]]; then
        info "não consegui ler o rfkill de ${_sem_leitura[*]} — não sei dizer se esse rádio está bloqueado"
    fi
    if [[ "${#_lidos[@]}" -gt 0 && "${bloqueados}" -eq 0 ]]; then
        pass "rádio Bluetooth ligado em ${#_lidos[@]} adaptador(es) (rfkill sem bloqueio)"
    fi
}

# Saúde do rádio 2.4 GHz: RSSI, Trusted, Discovering, contadores do adaptador
# e IdleTimeout — os 5 checks do estudo BT §5/§6, todos read-only.
check_bt_radio() {
    command -v busctl >/dev/null 2>&1 || return 0
    local paths p mac alias connected trusted rssi disc gamepad_conectado=0
    # N-IGUAL-A-UM-01 (22/08/2026): os adaptadores que HOSPEDAM controle agora,
    # um por linha. Não é o "primeiro adaptador": nesta bancada de três, o
    # primeiro (hci0) hospeda um DualSense e o Pro mora no segundo — perguntar
    # ao primeiro é perguntar a quem não tem a resposta.
    local adps_com_controle="" adp
    paths="$(_dbus_bt_device_paths)"
    while IFS= read -r p; do
        [[ -z "${p}" ]] && continue
        mac="${p##*dev_}"; mac="${mac//_/:}"
        alias="$(_dbus_bt_prop "${p}" org.bluez.Device1 Alias)"
        printf '%s' "${alias}" | grep -qiE 'dualsense|wireless controller|pro controller|8bitdo|joy-con|xbox' || continue
        connected="$(_dbus_bt_prop "${p}" org.bluez.Device1 Connected)"
        if [[ "${connected}" == "true" ]]; then
            gamepad_conectado=1
            adps_com_controle+="${p%/*}"$'\n'
            # RSSI via D-Bus só existe durante discovery — mesmo limite do
            # `bluetoothctl info` antigo; sem valor, sem veredito.
            rssi="$(_dbus_bt_prop "${p}" org.bluez.Device1 RSSI)"
            if [[ -n "${rssi}" ]] && (( rssi < -70 )); then
                warn "sinal fraco do ${alias:-controle} (${mac}): RSSI ${rssi} dBm (bom é > -60) — ponha o adaptador BT num extensor USB curto, fora da sombra do gabinete e a 20 cm ou mais dos receivers 2.4G"
            elif [[ -n "${rssi}" ]]; then
                pass "sinal do ${alias:-controle}: RSSI ${rssi} dBm"
            fi
        fi
        trusted="$(_dbus_bt_prop "${p}" org.bluez.Device1 Trusted)"
        if [[ "${trusted}" == "false" ]]; then
            warn "${alias:-controle} (${mac}) pareado mas SEM confiança (Trusted: no) — a reconexão pelo botão PS pode depender de autorização; o watchdog corrige no próximo tick; na mão: busctl set-property org.bluez ${p} org.bluez.Device1 Trusted b true"
        fi
        # BT-SDP-VAZIO-01 (02/08): bond SEM registro de serviços SDP. O
        # `profiles/input/server.c` do BlueZ recusa conexão ENTRANTE de quem
        # não tem o perfil HID (0x1124) registrado — "Refusing connection:
        # unknown device" — e o device entra num laço: o rádio sobe, o perfil
        # não, o link cai. Nenhum dos checks acima enxergava isso: Paired,
        # Bonded e Trusted ficam todos `true` o tempo todo.
        #
        # Sem este aviso o defeito se parece com regressão do Hefesto, e foi
        # exatamente assim que ele chegou (a queixa dela: "conecta sozinho e
        # algo apaga a conexão"). Vale para device pareado, conectado ou não.
        if [[ "$(_dbus_bt_prop "${p}" org.bluez.Device1 Paired)" == "true" ]] \
                && ! _dbus_bt_prop "${p}" org.bluez.Device1 UUIDs \
                    | grep -q '00001124-0000-1000-8000-00805f9b34fb'; then
            fail "${alias:-controle} (${mac}) tem bond mas NENHUM perfil HID registrado (SDP vazio) — o BlueZ recusa a reconexão dele como 'unknown device' e o link cai sozinho. Cura (apaga o pareamento): busctl call org.bluez ${p%/*} org.bluez.Adapter1 RemoveDevice o ${p} && sudo rm -f /var/lib/bluetooth/*/cache/${mac} — e pareie de novo. O cache TEM de sair junto (SDP-CACHE-01), senão o pareamento novo nasce igual"
        fi
    done <<<"${paths}"
    # Inquiry contínuo rouba banda dos links dos controles (provado ao vivo:
    # a tela de Bluetooth do cosmic-settings aberta mantém Discovering=yes).
    #
    # N-IGUAL-A-UM-01 (22/08/2026): a pergunta é por adaptador, e o adaptador
    # certo é o que hospeda o controle — a busca só rouba banda DO RÁDIO EM QUE
    # ela acontece. O `/org/bluez/hci0` literal que morava aqui era a mesma
    # cicatriz do WATCHDOG-HCI-HARDCODE-01 (bt_health_watchdog.sh:158), que
    # está escrita vinte linhas acima e não tinha sido generalizada: MEDIDO
    # nesta bancada de três adaptadores, hci1 e hci2 hospedam quatro dos cinco
    # controles e nenhum deles era olhado. Numa máquina com um adaptador só que
    # tenha enumerado como hci1, o aviso era no-op MUDO.
    #
    # RESERVA-DO-RADIO-01 (20/09/2026): o aviso já estava no lugar certo e
    # dizia só o ESTADO — "a busca rouba banda do rádio". Quanto? Ninguém
    # sabia, e um aviso sem tamanho se lê como zelo e se ignora. Agora ele diz
    # o CUSTO MEDIDO: duas corridas de 19/09 com um DualSense no rádio do
    # adaptador que varria derrubaram 32,5% e 43,4% dos pacotes, medidos pelo
    # evdev de MOVIMENTO (a IMU publica ~500 pacotes/s com o controle parado).
    # As três corridas CRUZADAS — varrendo num adaptador, medindo em outro —
    # deram ruído (+5,1%, -4,2%, -3,5%), e é por isso que este aviso é por
    # adaptador e não pela mesa.
    #
    # O DONO DESSES DOIS NÚMEROS é
    # `src/hefesto_dualsense4unix/integrations/varredura_do_radio.py`
    # (QUEDA_MINIMA_MEDIDA / QUEDA_MAXIMA_MEDIDA), e
    # `tests/unit/test_a_varredura_do_radio_se_le_e_custa.py` reprova se esta
    # frase divergir dele. Dois donos do mesmo número divergem na primeira
    # remedição.
    #
    # E A CAUDA É PARTE DO AVISO: medido em 20/09, o adaptador continuou
    # varrendo por 21 SEGUNDOS depois de a janela fechar. "Já fechei" não é
    # "já parou", e sem esta linha a pessoa fecha a tela, testa na hora e
    # conclui que o aviso mente.
    if [[ "${gamepad_conectado}" -eq 1 ]]; then
        while IFS= read -r adp; do
            [[ -z "${adp}" ]] && continue
            disc="$(_dbus_bt_prop "${adp}" org.bluez.Adapter1 Discovering)"
            if [[ "${disc}" == "true" ]]; then
                warn "adaptador ${adp##*/} em modo de busca (Discovering: yes) com controle BT conectado nele — MEDIDO: a busca derruba de 32,5% a 43,4% dos pacotes do controle que está NESTE adaptador (19/09/2026, duas corridas). Feche a tela de Bluetooth do cosmic-settings (a busca é do adaptador em que você ENTROU, não da lista) e espere ~21 s: ela continua varrendo depois de a janela fechar"
            fi
        done <<<"$(printf '%s' "${adps_com_controle}" | sort -u)"
    fi
    # Contadores do adaptador (proxy não-intrusivo de rádio sujo — sem btmon).
    #
    # LEITURA SEM SUCESSOR VIVO (MIGRACAO-BLUEZ-DEPRECIADOS-01, 19/08/2026):
    # esses números são o `hci_dev_stats` do kernel, e o kernel só os entrega
    # pelo ioctl HCIGETDEVINFO — que é exatamente o que o `hciconfig` faz. Nem
    # `btmgmt` nem `bluetoothctl` do 5.86 têm comando que devolva contador de
    # erro (conferido nos dois `--help` em 19/08/2026). Onde a ferramenta
    # depreciada não existe, esta medida SE PERDE — e o doctor tem de dizer
    # isso. Antes ele calava, e a seção inteira sumia da saída: quem lia via uma
    # conferência sem avisos e concluía "rádio limpo".
    #
    # O adaptador também deixou de ser 'hci0' na unha (WATCHDOG-HCI-HARDCODE-01:
    # hci1 já aconteceu nesta máquina, e ali o check virava no-op mudo).
    # N-IGUAL-A-UM-01 (22/08/2026): o `head -1` daqui era a MESMA doença que o
    # comentário acima descreve, uma linha abaixo de onde ele a descreve. Trocar
    # `hci0` por "o primeiro que aparecer" não cura nada numa mesa de três: nesta
    # bancada hci1 e hci2 hospedam quatro dos cinco controles, e o rádio sujo
    # deles nunca era lido. Agora TODOS respondem, e o aviso NOMEIA qual.
    local _adp _adps_erro=()
    mapfile -t _adps_erro < <(_bt_adaptadores)
    if [[ "${#_adps_erro[@]}" -eq 0 ]]; then
        info "nenhum adaptador Bluetooth no sistema — sem contadores de rádio para ler"
    elif command -v hciconfig >/dev/null 2>&1; then
        local errs _algum_erro=0 _algum_lido=0
        for _adp in "${_adps_erro[@]}"; do
            errs="$(hciconfig "${_adp}" 2>/dev/null | grep -oE 'errors:[0-9]+' | grep -oE '[0-9]+' | paste -sd/ -)"
            [[ -n "${errs}" ]] && _algum_lido=1
            if [[ -n "${errs}" && "${errs}" != "0/0" ]]; then
                _algum_erro=1
                warn "adaptador ${_adp} com erros acumulados (RX/TX: ${errs}) — rádio sujo; veja as linhas [BT-ERR] no kernel.log e os conselhos de posicionamento acima"
            fi
        done
        errs=""
        [[ "${_algum_lido}" -eq 1 ]] && errs="0/0"
        if [[ "${_algum_erro}" -eq 1 ]]; then
            :
        elif [[ -n "${errs}" ]]; then
            pass "adaptador BT sem erros de RX/TX (0/0)"
        fi
    else
        # O NOME dos adaptadores vem do array, não de `${_adp}` — ele só é
        # preenchido DENTRO do laço acima, que neste ramo nem roda. Medido em
        # 22/08: a frase saía com "em " e o endereço vazio. Aqui ela nomeia os
        # três, que é a informação que faltava quando o texto dizia "hci0".
        info "NÃO SEI se o rádio acumulou erros de RX/TX em ${_adps_erro[*]}: esses contadores só saem do 'hciconfig' (ioctl HCIGETDEVINFO), que o BlueZ depreciou e sua distribuição moveu de pacote — instale bluez-deprecated (ou bluez-deprecated-tools) se quiser esta medida de volta. Nem btmgmt nem bluetoothctl a substituem, e as linhas [BT-ERR] do kernel-watch dependem da mesma fonte"
    fi
    # IdleTimeout do input.conf: default 0 = nunca desconecta por ociosidade
    # (já é o máximo). Valor > 0 = regressão de terceiro.
    local idle
    idle="$(grep -sE '^[[:space:]]*IdleTimeout[[:space:]]*=' /etc/bluetooth/input.conf 2>/dev/null | head -1 | sed 's/.*=[[:space:]]*//')"
    if [[ -n "${idle}" && "${idle}" != "0" ]]; then
        warn "desconexão por ociosidade LIGADA no BlueZ (input.conf IdleTimeout=${idle}) — controles BT vão cair sozinhos; o default 0 (nunca) é o certo: remova a linha de /etc/bluetooth/input.conf"
    else
        pass "sem desconexão por ociosidade no BlueZ (IdleTimeout no default 0)"
    fi
}

# Termômetro do rádio: 'input CRC's check failed' no boot atual. Fundo
# aceitável medido: 2–39; o storm do clone foi 211 mil (20/s).
check_bt_crc_counters() {
    command -v journalctl >/dev/null 2>&1 || return 0
    local nds nds4
    nds="$(journalctl -b -k --no-pager 2>/dev/null | grep -c "DualSense input CRC" || true)"
    nds4="$(journalctl -b -k --no-pager 2>/dev/null | grep -c "DualShock4 input CRC" || true)"
    nds="${nds:-0}"; nds4="${nds4:-0}"
    if [[ "${nds4}" -gt 100 ]]; then
        warn "DualShock4 com ${nds4} erros de CRC neste boot — assinatura do clone DS4 conectado bombardeando o rádio (troque o modo/cabo ou despareie; ver o aviso do clone acima)"
    fi
    if [[ "${nds}" -gt 100 ]]; then
        warn "DualSense com ${nds} erros de CRC neste boot — rádio sujo (interferência 2.4 GHz); afaste o dongle dos receivers (extensor USB) e evite Wi-Fi USB 2.4G durante o jogo"
    elif [[ "${nds4}" -le 100 ]]; then
        pass "integridade dos pacotes BT ok neste boot (DualSense: ${nds}, DualShock4: ${nds4} erros de CRC — fundo aceitável)"
    fi
}

# STORM-USB-01 (20/09/2026) — O ENDEREÇO DO -71, e não só a contagem.
#
# O aviso do `check_kernel_watch` diz *"33 vez(es) nos últimos 7 dias"* e manda
# "conferir a seção USB/dropout abaixo". Aquela seção (`check_usb_dropout`)
# correlaciona de verdade — mas só sobre `journalctl -b -k`, o BOOT ATUAL. A
# queda de terça-feira não está lá, e é justamente a que a pessoa quer
# explicar; o `kernel-watch` guarda meses e ninguém cruzava o log dele com o
# `/sys`.
#
# A porta está gravada em CADA linha `[USB-71]` desde que a vigia nasceu. Quem
# a lê e a cruza com a topologia é `integrations/exame_da_mesa.py --storm-usb`,
# e a direção é essa — não um `doctor.sh --json` — pela razão de sempre: o
# módulo viaja nos pacotes e este script não (`check_exame_da_mesa`, acima).
#
# `HEFESTO_DOCTOR_RAIZ_USB` troca a raiz do `/sys`. Serve para endereçar o -71
# contra um retrato de barramento de OUTRA máquina — a de quem pediu ajuda —, e
# é por onde a régua injeta uma bancada em vez de medir a topologia de quem
# roda o teste.
_o_endereco_do_storm() {
    local log="${1}" dias="${2}"
    local py arquivo raiz_usb
    py="$(_python_do_produto)"
    arquivo="${ROOT_DIR:-}/src/hefesto_dualsense4unix/integrations/exame_da_mesa.py"
    if [[ -z "${py}" || ! -f "${arquivo}" ]]; then
        info "NÃO SEI em qual porta esses -71 aconteceram: o exame_da_mesa.py não está ao alcance deste doctor (instalação por pacote sem o módulo, ou python ausente)"
        return
    fi
    raiz_usb="${HEFESTO_DOCTOR_RAIZ_USB:-/sys/bus/usb/devices}"
    local laudo
    # O FORMATO É O DO DONO: o `porque` de cada porta e de cada hub sai do
    # módulo, que é quem mediu. O que se escreve AQUI é a CURA — o que fazer
    # com o achado —, porque cura de terminal fala de cabo e de hub e a frase
    # do módulo tem de continuar servindo a quem só quer o laudo.
    laudo="$("${py}" "${arquivo}" --storm-usb --log "${log}" --dias "${dias}" \
             --raiz-usb "${raiz_usb}" 2>/dev/null | "${py}" -c '
import json
import sys

d = json.load(sys.stdin)
if d.get("porque_nao"):
    print("naosei\t" + str(d["porque_nao"]))
for p in d.get("portas") or []:
    texto = str(p.get("porque") or "").strip()
    if texto:
        print("porta\t" + texto)
for h in d.get("hubs_em_comum") or []:
    texto = str(h.get("porque") or "").strip()
    if texto:
        print("hub\t" + texto)
sobra = int(d.get("sem_endereco") or 0)
if sobra > 0:
    # AUSÊNCIA É RESPOSTA: a soma das portas acima é MENOR que o total contado,
    # e quem lê tem de saber disso. Engolir a diferença deixaria uma forma de
    # linha nova do kernel invisível para sempre.
    print("naosei\t" + str(sobra) + " evento(s) [USB-71] da janela ficaram SEM endereço — o kernel usou uma forma de linha que este doctor ainda não sabe ler; a soma das portas acima é menor que o total")
' 2>/dev/null)"
    # LAUDO VAZIO SÓ ACONTECE COM O MÓDULO MUDO, e isso é medido: esta função
    # só roda com pelo menos um `[USB-71]` na janela, e o módulo conta a MESMA
    # janela sobre o MESMO arquivo — logo ele devolve ao menos uma porta ou ao
    # menos um evento sem endereço, e qualquer um dos dois imprime linha.
    # (Uma sentinela "sempre imprima algo" chegou a ser escrita aqui e saiu:
    # nenhuma entrada a alcançava, e código que régua nenhuma pode morder é
    # verbosidade com cara de cuidado.)
    if [[ -z "${laudo}" ]]; then
        info "NÃO SEI em qual porta esses -71 aconteceram: o cruzamento com a topologia do /sys não devolveu nada — o módulo não respondeu"
        return
    fi
    local marca texto
    while IFS=$'\t' read -r marca texto; do
        [[ -n "${texto}" ]] || continue
        case "${marca}" in
            porta) info "  -71 em ${texto}" ;;
            hub) warn "${texto}. É o suspeito a trocar primeiro: tire um dos aparelhos desse hub e ligue direto numa entrada do computador, ou troque o hub (de preferência um com fonte própria)" ;;
            naosei) info "${texto}" ;;
        esac
    done <<<"${laudo}"
}

# kernel-watch (PLAT-06 item 4): resume o log dedicado pro leigo. Lê o
# kernel.log novo (fallback: storm.log antigo) e conta ocorrências por tag.
check_kernel_watch() {
    local unit="hefesto-dualsense4unix-storm-watch.service"
    if command -v systemctl >/dev/null 2>&1; then
        if systemctl --user is-active --quiet "${unit}" 2>/dev/null; then
            pass "kernel-watch ativo (${unit})"
        elif systemctl --user cat "${unit}" >/dev/null 2>&1; then
            warn "kernel-watch instalado mas parado — ligue: systemctl --user enable --now ${unit}"
        else
            warn "kernel-watch não instalado — $(conselho_de_instalacao)$(so_no_checkout "(entra por default; --no-kernel-watch é o opt-out)")"
        fi
    fi
    local log="${HOME}/.local/state/hefesto-dualsense4unix/kernel.log"
    [[ -f "${log}" ]] || log="${HOME}/.local/state/hefesto-dualsense4unix/storm.log"
    if [[ ! -f "${log}" ]]; then
        info "sem log do kernel-watch ainda (nasce no primeiro start/evento)"
        return
    fi
    # A JANELA, e ela é o commit inteiro — 03/09/2026, achado POR ELA.
    #
    # ELE CONTAVA O ARQUIVO INTEIRO E ESCREVIA NO PRESENTE. `grep -c "[JOYCON]"`
    # sobre um log que começa em 20/07 devolvia 9, e a frase saía *"o kernel deu
    # rate-limit no 8BitDo 9 vezes"* — com o 8BitDo desligado e os nove eventos
    # em 11/08 e 26/08. A palavra dela: *"nem o 8bitdo tá conectado nem o usb
    # pareceu ter dado pau. acho que essas 4 mensagens tão erradas não?"*.
    #
    # ESTAVAM. E o defeito não é o número — é o TEMPO VERBAL. Um aviso que
    # afirma com confiança um estado que não é o de agora é pior que aviso
    # nenhum: manda procurar defeito onde não há.
    #
    # A CURA TEM DUAS METADES: só é AVISO o que aconteceu dentro da janela, e
    # todo número vem com a DATA do último evento. Fora da janela vira `info`,
    # com o histórico dito como histórico.
    local dias_da_janela="${HEFESTO_DOCTOR_JANELA_DIAS:-7}"
    local corte
    corte="$(date -d "${dias_da_janela} days ago" +%Y-%m-%d 2>/dev/null || echo 0000-00-00)"

    # As linhas do kernel-watch abrem com `YYYY-MM-DD`, e data ISO compara como
    # texto — nenhuma aritmética por linha, nenhum `date` por evento.
    _quantos_desde() {  # <tag> <corte>
        awk -v tag="[$1]" -v corte="$2" \
            'index($0, tag) && substr($0,1,10) >= corte { n++ } END { print n+0 }' \
            "${log}" 2>/dev/null || echo 0
    }
    _quando_o_ultimo() {  # <tag> — devolve DD/MM ou vazio
        grep -F "[$1]" "${log}" 2>/dev/null | tail -1 |
            awk '{ d=substr($0,1,10); if (d ~ /^[0-9]{4}-/) printf "%s/%s", substr(d,9,2), substr(d,6,2) }'
    }
    #: A FRASE DE UM CONTADOR, e ela nunca mente sobre o tempo.
    #: `$1` tag · `$2` total · `$3` recentes · `$4` último · `$5` o que dizer.
    _relata() {
        if [[ "${3:-0}" -gt 0 ]]; then
            warn "$5 — ${3} vez(es) nos últimos ${dias_da_janela} dias (a última em ${4:-?}); ${2} no log inteiro"
        elif [[ "${2:-0}" -gt 0 ]]; then
            info "[$1] não aconteceu nos últimos ${dias_da_janela} dias. O log guarda ${2} do passado, a última em ${4:-?} — histórico, não o estado de agora"
        fi
    }

    local tag n resumo="" n_joycon=0 n_joycon_probe=0 n_usb71=0 n_bterr=0
    for tag in USB-71 JOYCON JOYCON-PROBE BT-HCI XHCI BT-ERR; do
        n="$(grep -cF "[${tag}]" "${log}" 2>/dev/null || true)"; n="${n:-0}"
        resumo+=" ${tag}=${n}"
        case "${tag}" in
            JOYCON) n_joycon="${n}" ;;
            JOYCON-PROBE) n_joycon_probe="${n}" ;;
            USB-71) n_usb71="${n}" ;;
            BT-ERR) n_bterr="${n}" ;;
        esac
    done
    info "kernel-watch (${log##*/}), o log INTEIRO desde $(head -1 "${log}" 2>/dev/null | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}' | head -1):${resumo}"

    _relata JOYCON "${n_joycon}" "$(_quantos_desde JOYCON "${corte}")" \
        "$(_quando_o_ultimo JOYCON)" \
        "o kernel deu rate-limit no controle Nintendo/8BitDo [JOYCON] — é a morte do 8BitDo em Bluetooth (muro do hid-nintendo); a configuração estável é NO CABO. Onda T: o patch DKMS (ver seção abaixo) reduz a chance do link cair, mas não elimina a degradação de rádio"
    _relata JOYCON-PROBE "${n_joycon_probe}" "$(_quantos_desde JOYCON-PROBE "${corte}")" \
        "$(_quando_o_ultimo JOYCON-PROBE)" \
        "o hid-nintendo falhou no PROBE [JOYCON-PROBE] — morte 'invisível' (o device nem chega a registrar; sem cascata [JOYCON]); ver a seção DKMS hid-nintendo abaixo"
    local recentes_usb71
    recentes_usb71="$(_quantos_desde USB-71 "${corte}")"
    _relata USB-71 "${n_usb71}" "${recentes_usb71}" \
        "$(_quando_o_ultimo USB-71)" \
        "storm USB (-71) registrado no kernel-watch [USB-71] — a PORTA e o APARELHO de cada um saem logo abaixo; as alavancas (quirk, regra 75) estão na seção USB/dropout"
    # STORM-USB-01: o número sozinho não manda ninguém a lugar nenhum.
    #
    # ESTA GUARDA É ECONOMIA, NÃO COMPORTAMENTO, e medir isso custou uma
    # mordida: quem CORTA a janela é o `--dias` do módulo, e arrancar o `-gt 0`
    # daqui não faz um evento de agosto aparecer — ele volta a ser dois
    # `python3` gastos para receber uma lista vazia. As duas travas ficam de
    # propósito, e a régua `test_evento_velho_nao_ganha_endereco` exige as
    # DUAS: só arrancando ambas é que o passado volta a ser contado no
    # presente, que é o defeito que ela pegou em 03/09.
    if [[ "${recentes_usb71:-0}" -gt 0 ]]; then
        _o_endereco_do_storm "${log}" "${dias_da_janela}"
    fi
    _relata BT-ERR "${n_bterr}" "$(_quantos_desde BT-ERR "${corte}")" \
        "$(_quando_o_ultimo BT-ERR)" \
        "o rádio BT acumulou erros [BT-ERR] — rádio sujo; ver os conselhos de posicionamento acima"
    # MIGRACAO-BLUEZ-DEPRECIADOS-01 (19/08/2026): [BT-ERR] só nasce se o
    # kernel-watch conseguiu LER os contadores, e a única fonte deles é o
    # `hciconfig` depreciado. Sem ele o log fica sem [BT-ERR] para sempre — e
    # zero [BT-ERR] é indistinguível de "rádio limpo". O kernel-watch passou a
    # marcar isso com [BT-SEM-CONTADOR]; aqui a marca vira frase.
    local n_semcontador
    n_semcontador="$(grep -cF '[BT-SEM-CONTADOR]' "${log}" 2>/dev/null || true)"
    if [[ "${n_semcontador:-0}" -gt 0 ]]; then
        info "o kernel-watch NÃO está medindo os erros do rádio ([BT-SEM-CONTADOR]) — o 'hciconfig' foi depreciado pelo BlueZ e não está aqui, e nenhuma ferramenta viva devolve esses contadores. Não leia 'BT-ERR=0' acima como rádio limpo: é ausência de medida, não medida de ausência. Para recuperá-la, instale bluez-deprecated (ou bluez-deprecated-tools)"
    fi
}

# AS FAMÍLIAS DO RÁDIO no kernel-watch (O-DIARIO-DO-RADIO-01; resumidas pelo
# doctor desde a INSTALL-E-UNINSTALL-DO-RADIO-01, 23/09/2026). O kernel-watch
# marca o rádio com tags próprias — [BT-SOCKET], [FILA-CHEIA], [ENLACE-PARADO],
# [BT-TRAVADO], [CRC] — e grava uma rajada como borda + resumo; o log de antes
# delas só se lê reclassificando o [BT-HCI] pelo conteúdo. Quem sabe as duas
# coisas é o `storm_doctor.classificar_o_historico`, e o doctor PERGUNTA a ele:
# não redigita padrão nenhum. A janela é a do `check_kernel_watch` (aviso só
# dentro dela; fora, histórico). Família que nenhuma volta da vigia procurou é
# «não olhei», e zero ali não é zero. O -71 (família 1) já sai no
# `check_kernel_watch`, com a porta.
check_familias_do_radio() {
    local log="${HOME}/.local/state/hefesto-dualsense4unix/kernel.log"
    local dias="${HEFESTO_DOCTOR_JANELA_DIAS:-7}" corte py saida
    [[ -f "${log}" ]] || return 0
    corte="$(date -d "${dias} days ago" +%Y-%m-%d 2>/dev/null || echo 0000-00-00)"
    py="$(_python_do_produto)"
    [[ -n "${py}" ]] || { info "sem python para ler as famílias do rádio no kernel-watch"; return; }
    saida="$(HEFESTO_SRC="${ROOT_DIR}/src" "${py}" - "${log}" "${corte}" <<'PY' 2>/dev/null
import os
import sys

src = os.environ.get("HEFESTO_SRC", "")
if src and os.path.isdir(src):
    sys.path.insert(0, src)
try:
    from hefesto_dualsense4unix.integrations.storm_doctor import (
        FAMILIAS_DO_RADIO,
        classificar_o_historico,
    )
except Exception:  # noqa: BLE001 - qualquer falha de import é "não sei"
    print("sem-produto")
    raise SystemExit(0)
with open(sys.argv[1], encoding="utf-8", errors="ignore") as fh:
    linhas = fh.read().splitlines()
tudo = classificar_o_historico(linhas)
janela = classificar_o_historico(
    [linha for linha in linhas if linha.startswith("#") or linha[:10] >= sys.argv[2]]
)
for tag, (familia, nome) in FAMILIAS_DO_RADIO.items():
    if familia == "1":
        continue
    conta = tudo.get(familia)
    if conta is None:
        print(f"naoolhei\t{tag}\t{nome}")
        continue
    recente = janela.get(familia)
    dia = conta.ultima[:10]
    ultima = f"{dia[8:10]}/{dia[5:7]}" if len(dia) == 10 else "?"
    print(
        f"familia\t{tag}\t{nome}\t{conta.rajadas}\t{recente.rajadas if recente else 0}\t{ultima}"
    )
PY
)" || saida=""
    if [[ -z "${saida}" || "${saida}" == "sem-produto" ]]; then
        info "NÃO SEI ler as famílias do rádio no kernel-watch: o storm_doctor não está ao alcance do python ${py}"
        return
    fi
    local marca tag nome total recentes ultima cura naoolhei=()
    while IFS=$'\t' read -r marca tag nome total recentes ultima; do
        if [[ "${marca}" == "naoolhei" ]]; then
            naoolhei+=("${nome} ${tag}")
            continue
        fi
        case "${tag}" in
            "[BT-SOCKET]") cura="É o que derruba os controles por Bluetooth: o bluetoothd com o hefesto-0002 (o backport do passo 3f) segura a sessão" ;;
            "[FILA-CHEIA]") cura="A fila de saída de um controle encheu: o uhid com contrapressão segura$(so_no_checkout "(./install.sh --uhid-contrapressao)")" ;;
            "[ENLACE-PARADO]") cura="O enlace de um controle parou de andar: distância ou interferência — aproxime o controle do adaptador" ;;
            "[BT-TRAVADO]") cura="Um adaptador travou: o watchdog o reinicia sozinho, até três vezes seguidas; se não voltar, tire e ponha o adaptador" ;;
            "[CRC]") cura="Pacotes corrompidos: interferência de 2.4 GHz — afaste o adaptador dos receivers e do Wi-Fi USB" ;;
            *) cura="" ;;
        esac
        if [[ "${recentes:-0}" -gt 0 ]]; then
            warn "rádio: ${nome} ${tag} — ${recentes} vez(es) nos últimos ${dias} dias (a última em ${ultima}); ${total} no log inteiro. ${cura}"
        elif [[ "${total:-0}" -gt 0 ]]; then
            info "rádio: ${nome} ${tag} não aconteceu nos últimos ${dias} dias. O log guarda ${total}, a última em ${ultima} — histórico, não o estado de agora"
        fi
    done <<<"${saida}"
    if [[ "${#naoolhei[@]}" -gt 0 ]]; then
        local lista
        lista="$(printf '%s, ' "${naoolhei[@]}")"
        info "o kernel-watch deste log ainda não procurava: ${lista%, } — zero aqui é «não olhei»; a vigia nova, que o install reinicia, passa a procurar"
    fi
}

# PLAT-03 item 2: os params do hefesto no cmdline — comparação /proc/cmdline
# (boot ATUAL) × configuration do kernelstub/grub (PRÓXIMO boot) = "aplicado"
# vs "pendente de reboot". A policy sysfs NUNCA entra aqui (ela mente).
check_cmdline_platform() {
    local owners="${HOME}/.local/state/hefesto-dualsense4unix/cmdline-owners.conf"
    local tok ativo agendado
    for tok in "usbcore.autosuspend=-1" "054c:0ce6:gn" "054c:0df2:gn"; do
        ativo=0; agendado=0
        grep -qF "${tok}" /proc/cmdline 2>/dev/null && ativo=1
        { [[ -r /etc/kernelstub/configuration ]] && grep -qF "${tok}" /etc/kernelstub/configuration 2>/dev/null; } && agendado=1
        { [[ -r /etc/default/grub ]] && grep -qF "${tok}" /etc/default/grub 2>/dev/null; } && agendado=1
        if [[ "${ativo}" -eq 1 ]]; then
            pass "cmdline: ${tok} APLICADO neste boot"
        elif [[ "${agendado}" -eq 1 ]]; then
            warn "cmdline: ${tok} agendado mas NÃO ativo — pendente de reboot"
        else
            warn "cmdline: ${tok} ausente — $(conselho_de_instalacao)$(so_no_checkout "(o passo 3e aplica com MERGE no token único e registro de dono)")"
        fi
    done
    # O kernel respeita SÓ UM token usbcore.quirks= — mais de um é bug de merge.
    local n_tokens
    n_tokens="$(grep -o 'usbcore\.quirks=' /proc/cmdline 2>/dev/null | wc -l || true)"
    if [[ "${n_tokens:-0}" -gt 1 ]]; then
        warn "MAIS DE UM token usbcore.quirks= no cmdline (${n_tokens}) — o kernel respeita só um; $(conselho_de_instalacao)$(so_no_checkout "(o passo 3e funde num token único)")"
    fi
    if [[ -f "${owners}" ]]; then
        info "donos registrados: $(tr '\n' ' ' < "${owners}")"
    fi
}

# ============================================================================
# G2 — doctor: "Rádio e pareamento" (sprint 2026-07-19-sprint-onda-g-gyro02-
# doctor.md). Tudo READ-ONLY; fecha o ciclo do que a Onda R instala (backport
# bluez 5.85 + hefesto-bt-agent.service) com visibilidade pro leigo. A causa
# medida do bond "meio-salvo" (Paired: yes / Bonded: no) é "No agent available
# for request type 2" (estudo receita-backport-bluez.md §4):
# nenhum agente D-Bus respondeu no momento do pareamento. O check 6 do sprint
# ("autoridade de exibição unknown presa") JÁ existe (NUMA-05/
# check_display_authority, mais abaixo) — não duplicado aqui.
# ============================================================================

# A faixa de bluez que esta casa aceita tem DOIS limites, não um.
#
# PISO 5.79 — abaixo dele, crashes crônicos de input/HIDP (estudo da Onda R,
#   receita-backport-bluez.md).
#
# TETO 5.87 — a MENOR versão REJEITADA conhecida. Motivo medido (estudo
#   docs/process/estudos/2026-08-07-o-defeito-do-bluez-que-ela-lembrou-e-os-
#   outros-cinco.md §D, GRAU MEDIDO pela topologia do git): o commit `5d836f1`
#   introduziu um uso-depois-de-liberado (UAF) em `dev_disconnected`
#   (`src/adapter.c`) — `device_is_connected()` chamado DEPOIS de
#   `adapter_remove_connection()`, que pode ter liberado o device. `5d836f1` é
#   ancestral da tag 5.87 (dentro); a correção `5bc6aa79` está UM commit depois
#   do 5.87 e NENHUM lançamento a carrega ainda. Por isso o alvo do backport é
#   o 5.86 (install.sh, passo 3f) e o 5.87 foi recusado em 22/07 e de novo em
#   07/08 — com número.
#
# Por que o teto é WARN e não FAIL: numa máquina que já veio com bluez ≥ 5.87
# (o caso do PC novo), nada disto é escolha dela, e o primeiro lançamento pós-
# 5.87 que carregue o `5bc6aa79` (previsivelmente o 5.88) sai desta faixa por
# mérito próprio. O dever do doctor aqui é NOMEAR o motivo, não decidir por
# ela. Quando o 5.88 sair com a correção, este teto sobe — e o estudo §D é o
# lugar onde se confere isso antes de mexer.
readonly _BZ_PISO="5.79"
readonly _BZ_TETO="5.87"

# Compara a versão do bluez instalada com a faixa [_BZ_PISO, _BZ_TETO).
# Função PURA — só `dpkg --compare-versions`, sem tocar em pacote nenhum.
_bluez_version_verdict() {
    local ver="$1"
    if [[ -z "${ver}" ]]; then
        printf 'unknown\n'
        return
    fi
    if ! dpkg --compare-versions "${ver}" ge "${_BZ_PISO}" 2>/dev/null; then
        printf 'old\n'
    elif dpkg --compare-versions "${ver}" ge "${_BZ_TETO}" 2>/dev/null; then
        printf 'nova\n'
    else
        printf 'ok\n'
    fi
}

# Versão do bluetoothd que o systemd REALMENTE executa, lida pelo ExecStart da
# unit (que o drop-in pode ter reapontado) — não precisa de privilégio.
#
# Quem cura o crash é o daemon em execução, não o que o dpkg empacotou. Em
# 18/08/2026, nesta casa, o backport saiu pelo tarball upstream porque o .deb do
# resolute exige noble (glib 2.80, libell 0.64, json-c 0.17, debhelper 13.14) e
# o jammy tem 2.72 / 0.49 / 0.15 / 13.6 — mas o configure.ac do 5.86 pede
# dbus>=1.10, libudev>=196, json-c>=0.13 e ell>=0.39, todos satisfeitos ali. O
# dpkg seguiu dizendo 5.64 com o rádio rodando 5.86, e este portão reprovava a
# cura que já estava de pé.
_bluez_binario_vivo() {
    local caminho
    caminho="$(systemctl show bluetooth.service -p ExecStart --value 2>/dev/null \
        | grep -oE 'path=[^ ]+' | head -1 | cut -d= -f2)"
    [[ -n "${caminho}" && -x "${caminho}" ]] || return 1
    printf '%s\n' "${caminho}"
}

_bluez_versao_do_daemon_vivo() {
    local caminho
    caminho="$(_bluez_binario_vivo)" || return 1
    "${caminho}" --version 2>/dev/null | tr -d '[:space:]'
}

# AS CURAS DO BACKPORT, perguntadas ao BINÁRIO (INSTALL-E-UNINSTALL-DO-RADIO-01,
# 23/09/2026). A faixa de versão acima diz «5.86» para o .3 e para o .4 — e o
# .4 é o do hefesto-0002, em que o EAGAIN do rádio cheio deixa de derrubar a
# sessão HID dos controles (BLUETOOTHD-NAO-DERRUBA-01). Um 5.86 oficial também
# passaria. A mesma pergunta do passo 3f do install: cada patch deixa uma marca
# no binário, e quem diz qual é o `MARCA_hefesto-NNNN` do
# `assets/bluez-backport/BASELINE` — o doctor lê, não digita. Sem o BASELINE (o
# pacote não o leva), diz que não sabe.
check_bluez_curas_do_backport() {
    local vivo baseline="${HEFESTO_DOCTOR_BLUEZ_BASELINE:-${ROOT_DIR}/assets/bluez-backport/BASELINE}"
    local nome marca faltam=() tem=()
    vivo="${HEFESTO_DOCTOR_BLUETOOTHD:-$(_bluez_binario_vivo || true)}"
    if [[ ! -r "${baseline}" ]]; then
        info "não sei conferir as curas do backport do BlueZ nesta instalação (sem o assets/bluez-backport/BASELINE)"
        return
    fi
    if [[ -z "${vivo}" || ! -r "${vivo}" ]]; then
        info "não achei o bluetoothd que o systemd executa — pulo a conferência das curas do backport"
        return
    fi
    # O BACKPORT DESTA CASA É .deb (conferência da INSTALL-E-UNINSTALL-DO-
    # RADIO-01): o passo 3f só existe onde há dpkg. Numa distro sem ele, o
    # aviso de baixo mandaria rodar um install que não entrega nada ali.
    if ! command -v "${HEFESTO_DOCTOR_DPKG:-dpkg}" >/dev/null 2>&1; then
        info "sem dpkg nesta distro — o backport do BlueZ desta casa é .deb (Debian/Ubuntu), e não há o que conferir aqui"
        return
    fi
    while IFS=$'\t' read -r nome marca; do
        [[ -n "${marca}" ]] || continue
        if grep -a -q -F -- "${marca}" "${vivo}" 2>/dev/null; then
            tem+=("${nome}")
        else
            faltam+=("${nome}")
        fi
    done < <(sed -n 's/^MARCA_\([^=]*\)=\(.*\)$/\1\t\2/p' "${baseline}" 2>/dev/null)
    if [[ "${#faltam[@]}" -eq 0 && "${#tem[@]}" -gt 0 ]]; then
        pass "o bluetoothd em execução traz as curas do backport desta casa (${tem[*]})"
    elif [[ "${#faltam[@]}" -gt 0 ]]; then
        warn "o bluetoothd em execução (${vivo}) não traz ${faltam[*]} — sem o hefesto-0002, o rádio cheio (EAGAIN) derruba a sessão dos controles por Bluetooth: $(conselho_de_instalacao)$(so_no_checkout "(o passo 3f instala o backport que estiver no cache; sem ele: scripts/construir_bluez_backport.sh)")"
    else
        # Nenhuma linha MARCA_ no BASELINE: não houve pergunta, e o silêncio
        # daqui se leria como «nada a dizer». É «não sei».
        info "não sei conferir as curas do backport do BlueZ: ${baseline} não traz nenhuma linha MARCA_"
    fi
}

check_bluez_backport_version() {
    if ! command -v dpkg >/dev/null 2>&1; then
        info "dpkg ausente (sistema não-Debian?) — pulo o check de versão do bluez"
        return
    fi
    local ver veredito origem
    ver="$(_bluez_versao_do_daemon_vivo || true)"
    if [[ -n "${ver}" ]]; then
        origem=" (daemon em execução)"
    elif command -v dpkg-query >/dev/null 2>&1; then
        ver="$(dpkg-query -W -f='${Version}' bluez 2>/dev/null || true)"
        origem=" (pacote dpkg — daemon parado)"
    else
        origem=""
    fi
    veredito="$(_bluez_version_verdict "${ver}")"
    case "${veredito}" in
        ok)
            pass "bluez ${ver}${origem} >= ${_BZ_PISO} e < ${_BZ_TETO} (sem os crashes crônicos de input/HIDP do 5.72, e sem o UAF do 5.87)"
            ;;
        nova)
            warn "bluez ${ver}${origem} >= ${_BZ_TETO} — o 5.87 carrega um uso-depois-de-liberado em dev_disconnected (src/adapter.c: device_is_connected() chamado depois de adapter_remove_connection() liberar o device; commit 5d836f1). A correção 5bc6aa79 está um commit DEPOIS do 5.87 e nenhum lançamento a carregava até 07/08/2026 — se esta versão é o 5.88 ou mais nova, confira se ela já traz o 5bc6aa79 e suba o teto (_BZ_TETO) no doctor.sh. O alvo desta casa é o backport 5.86$(so_no_checkout "(./install.sh, passo 3f)"); o porquê está em docs/process/estudos/2026-08-07-o-defeito-do-bluez-que-ela-lembrou-e-os-outros-cinco.md §D"
            ;;
        old)
            fail "bluez ${ver}${origem} < 5.79 — crashes crônicos de input/HIDP (heap corruption, 6x/5 dias medidos) documentados; aplique o backport: $(conselho_de_instalacao)$(so_no_checkout "(passo ONDA-R aplica sozinho se os .debs estiverem em ~/.cache/hefesto-dualsense4unix/bluez-backport/; senão, gere-os com scripts/construir_bluez_backport.sh)")"
            ;;
        *)
            info "bluez não encontrado (nem daemon em execução, nem pacote) — pulo o check de versão"
            ;;
    esac
}

# hefesto-bt-agent.service (Onda R): agente NoInputNoOutput persistente que
# responde o D-Bus na hora do pareamento — sem ele, um pareamento disparado
# fora da GUI/daemon (bluetoothctl manual, Blueman, re-pair em massa pós-
# migração do backport) fica "meio-salvo". É unit de SISTEMA (WantedBy=multi-
# user.target, /etc/systemd/system/) — por isso `systemctl` sem --user, ao
# contrário de check_service.
check_bt_agent_service() {
    command -v systemctl >/dev/null 2>&1 || { info "systemctl ausente — não checo o agente de pareamento"; return; }
    local state
    state="$(systemctl is-active hefesto-bt-agent.service 2>/dev/null || true)"
    if [[ "${state}" == "active" ]]; then
        pass "hefesto-bt-agent.service ativo — pareamento fora da GUI/daemon tem agente D-Bus para responder"
    elif systemctl cat hefesto-bt-agent.service >/dev/null 2>&1; then
        warn "hefesto-bt-agent.service instalado mas ${state:-inativo} — bond meio-salvo à espreita (Paired sem Bonded); ligue: sudo systemctl enable --now hefesto-bt-agent.service"
    else
        warn "hefesto-bt-agent.service não instalado — pareamento fora da GUI/daemon pode ficar meio-salvo (Paired sem Bonded, 'No agent available for request type 2'); $(conselho_de_instalacao)$(so_no_checkout "(ONDA-R aplica por default)")"
    fi
}

# A TRAVA COMUM DO RÁDIO (O-DIARIO-DO-RADIO-01; instalada pelo passo 3e-trava
# desde a INSTALL-E-UNINSTALL-DO-RADIO-01, 23/09/2026). O watchdog do Bluetooth
# (root), o `bt_active_mode.sh` (root, no start do bluetoothd) e o daemon (a
# sessão) pegam um `flock` antes de mexer no rádio — e a trava só é comum se os
# dois lados abrirem o MESMO arquivo. As quatro perguntas, na ordem em que uma
# resposta errada torna as seguintes inúteis:
#   1. o `tmpfiles.d` está instalado? (sem ele não há trava depois do boot);
#   2. a pasta existe, e NÃO é gravável pela sessão? (gravável é FALHA: o root
#      abre o arquivo ali, e a pasta deixaria trocá-lo por um link);
#   3. o arquivo é arquivo, 0660, grupo `hefesto`?
#   4. a sessão consegue escrever nele? (sem o grupo nos processos dela — quem
#      acabou de entrar no grupo —, a trava funciona só para ler).
# Os ganchos `HEFESTO_DOCTOR_TRAVA_*` existem para a régua não depender do /run
# de quem a roda.
check_trava_do_radio() {
    local conf="${HEFESTO_DOCTOR_TRAVA_CONF:-/etc/tmpfiles.d/hefesto-dualsense4unix-radio.conf}"
    local pasta="${HEFESTO_DOCTOR_TRAVA_DIR:-/run/hefesto-dualsense4unix}"
    local trava="${pasta}/radio.lock"
    local modo grupo
    if [[ ! -f "${conf}" ]]; then
        warn "a trava comum do rádio não está instalada — o watchdog do Bluetooth (root) e o daemon mexem no rádio sem se enxergar: $(conselho_de_instalacao)$(so_no_checkout "(o passo 3e-trava a cria)")"
        return
    fi
    if [[ ! -d "${pasta}" ]]; then
        warn "a trava comum do rádio está instalada mas ${pasta} não existe — ela nasce no boot; para agora: sudo systemd-tmpfiles --create ${conf}"
        return
    fi
    if [[ -w "${pasta}" ]]; then
        fail "${pasta} é GRAVÁVEL pela sua sessão — o root abre a trava ali, e uma pasta gravável deixaria trocá-la por um link; corrija: sudo systemd-tmpfiles --create ${conf}"
        return
    fi
    if [[ -L "${trava}" || ! -f "${trava}" ]]; then
        warn "a trava ${trava} falta (ou é um link) — sudo systemd-tmpfiles --create ${conf}"
        return
    fi
    read -r modo grupo <<<"$(stat -c '%a %G' "${trava}" 2>/dev/null || echo '? ?')"
    if [[ "${modo}" != "660" || "${grupo}" != "hefesto" ]]; then
        warn "a trava ${trava} está ${modo}, grupo ${grupo} (o certo é 660, grupo hefesto) — sudo systemd-tmpfiles --create ${conf}"
        return
    fi
    if [[ -w "${trava}" ]]; then
        pass "trava comum do rádio de pé (${trava}, 660, grupo hefesto) — o watchdog e o daemon disputam o mesmo arquivo"
    else
        warn "a trava comum do rádio está de pé, mas esta sessão ainda não está no grupo hefesto — o daemon a usa só para ler (a fila funciona) até você sair e entrar na sessão"
    fi
}

# ONDA-R2 (sprint 2026-07-21 BlueZ, camada 2): resiliência do bluetoothd —
# timers de snapshot de bonds + watchdog de saúde ativos e drop-in presente.
check_bt_resilience() {
    command -v systemctl >/dev/null 2>&1 || { info "systemctl ausente — não checo a resiliência do bluetoothd"; return; }
    local t1 t2
    t1="$(systemctl is-active hefesto-bt-bonds-snapshot.timer 2>/dev/null || true)"
    t2="$(systemctl is-active hefesto-bt-health-watchdog.timer 2>/dev/null || true)"
    if [[ "${t1}" == "active" && "${t2}" == "active" ]]; then
        pass "resiliência do bluetoothd ativa (snapshot de bonds 15min + watchdog de saúde 2min)"
    elif systemctl cat hefesto-bt-bonds-snapshot.timer >/dev/null 2>&1; then
        warn "timers de resiliência do bluetoothd instalados mas não ativos (snapshot=${t1:-?}, watchdog=${t2:-?}); ligue: sudo systemctl enable --now hefesto-bt-bonds-snapshot.timer hefesto-bt-health-watchdog.timer"
    else
        # A FRASE ANTIGA MANDAVA REPETIR O QUE JÁ TINHA SIDO FEITO (22/08/2026).
        # Ela dizia "rode ./install.sh (passo ONDA-R2 aplica por default)" — e
        # quem chegava aqui em geral tinha rodado: até 22/08 o passo 3e-bis
        # ficava DEPOIS do `exit 0` do ramo dos formatos, então `--flatpak`,
        # `--appimage` e `--deb` saíam sem a camada. Mandar repetir o comando
        # que não entrega é pior que não dizer nada: gasta o tempo da pessoa e
        # ainda a convence de que o problema é ela. Hoje o `install.sh` aplica
        # nos dois lados da cerca, e quem instalou por pacote sem checkout tem
        # o caminho próprio — o mesmo par de endereços que os checks de DKMS
        # já usam.
        warn "resiliência do bluetoothd não instalada (crash do bluetoothd destrói bonds sem backup): $(conselho_de_instalacao "" "/usr/share/hefesto-dualsense4unix/scripts/install-host-udev.sh" "— atenção: ele traz os alvos das regras 82/83, mas NÃO os timers")$(so_no_checkout "— em QUALQUER formato, inclusive --flatpak/--appimage/--deb")"
    fi
    if [[ ! -f /etc/systemd/system/bluetooth.service.d/10-hefesto-resilience.conf ]]; then
        warn "drop-in 10-hefesto-resilience.conf ausente — sem o desarme do watchdog do systemd (BLUETOOTHD-MORTO-POR-NOS-01) e sem snapshot na parada do serviço"
    fi
    # BT-NINTENDO-ACTIVE-01 + BT-SNIFF-PER-OUI-01 (23/07): o modo ativo é o nome
    # "Nintendo*" (do ADAPTADOR, vale para todos) + no-sniff SÓ no Pro genuíno
    # (POR CONEXÃO, não no adaptador). O A/B de 23/07 provou que no-sniff no
    # adaptador quebra a probe do 8BitDo (clone) — então o default do adaptador
    # DEVE manter o SNIFF. O que se verifica agora:
    #   - o alias começa com "Nintendo";
    #   - o adaptador MANTÉM o SNIFF (o clone precisa dele);
    #   - o Pro genuíno conectado, se houver, está com no-sniff na SUA conexão.
    #
    # LEITURA SEM SUCESSOR VIVO (MIGRACAO-BLUEZ-DEPRECIADOS-01, 19/08/2026): a
    # link policy — a do adaptador (`hciconfig lp`) e a da conexão (`hcitool
    # lp`) — não tem equivalente nas ferramentas vivas. A mgmt API do BlueZ não
    # expõe link policy, e por isso nem `btmgmt` nem `bluetoothctl` do 5.86 têm
    # comando para lê-la (conferido nos dois `--help` em 19/08/2026). O que
    # migrou aqui foi o resto da pergunta: QUAL é o adaptador (sysfs) e QUEM
    # está conectado (D-Bus). O SNIFF, sem as depreciadas, o doctor diz que não
    # sabe — antes ele calava e a linha inteira sumia da conferência.
    # N-IGUAL-A-UM-01 (22/08/2026): idem — a cura BT-NINTENDO-ACTIVE-01 passou a
    # valer em TODO adaptador que hospeda a linhagem, e um exame que olha um só
    # daria `[ OK ]` verde sobre os outros dois. O laço confere cada um.
    local _hci _lp _alias _mac _pro_mac _pro_lp _hcis=()
    mapfile -t _hcis < <(_bt_adaptadores)
    for _hci in "${_hcis[@]}"; do
    # E SÓ OS QUE HOSPEDAM A LINHAGEM, que é a outra metade da mesma cura.
    # Medido em 22/08 ao rodar o doctor na mesa de três logo depois de alargar o
    # laço: ele passou a reclamar dos adaptadores #2 e #3 — *"modo ativo p/
    # Nintendo incompleto"* — e nenhum dos dois hospeda Nintendo nenhum. O
    # `bt_active_mode.sh` do mesmo dia deixou de prefixar quem não hospeda (pôr
    # a palavra onde não precisa a torna parte permanente do nome dela, porque
    # o `apelido_do_dongle` nunca subtrai), então cobrar o prefixo de todos era
    # o exame reprovando a cura por ela ter ficado certa.
    #
    # Trocar um `head -1` por um laço cego é trocar o no-op mudo por barulho —
    # e barulho em exame é o que ensina a ignorar exame.
    if [[ -n "${_hci}" ]] && _bt_hospeda_linhagem "${_hci}"; then
        _alias="$(busctl get-property org.bluez "/org/bluez/${_hci}" org.bluez.Adapter1 Alias 2>/dev/null | sed -E 's/^s "?//; s/"?$//' || true)"
        if command -v hciconfig >/dev/null 2>&1; then
            _lp="$(hciconfig "${_hci}" lp 2>/dev/null | grep -o 'SNIFF' || true)"
        else
            _lp="?"
        fi
        # Pro genuíno conectado — se houver, checa a policy DELE (deve ser sem
        # SNIFF). Quem está conectado agora sai do D-Bus; só a POLICY dele ainda
        # depende do `hcitool`.
        #
        # QUEM É "GENUÍNO" DEIXOU DE SER UMA FAIXA (25/08/2026,
        # UMA-FAIXA-NÃO-É-UM-FABRICANTE-01 / A1). Até esta data a linha aqui era
        # um `grep -oiE` da faixa do Pro DESTA bancada, e o preço era um FALSO
        # VERDE, reproduzido em bancada de mentira: com um Pro de outra safra
        # conectado e COM sniff — a cura furada, que é o defeito — o grep não o
        # achava, `_pro_lp` ficava "ausente", e o exame imprimia
        # `[ OK ] ... no-sniff só no Pro genuíno` sem ter olhado controle nenhum.
        # Um exame que aprova a cura ausente é pior que exame nenhum.
        #
        # BASTA UM COM SNIFF para a cura estar furada: numa mesa com dois Pros o
        # laço para no primeiro que estiver errado, porque é ele que a pessoa
        # precisa consertar.
        _pro_lp="ausente"
        _pro_mac=""
        while IFS= read -r _mac; do
            [[ -n "${_mac}" ]] || continue
            _bt_e_pro_genuino "${_mac}" "$(_bt_nome_do_controle "${_mac}")" || continue
            _pro_mac="${_mac}"
            if ! command -v hcitool >/dev/null 2>&1; then
                _pro_lp="?"
                break
            fi
            if hcitool lp "${_mac}" 2>/dev/null | grep -q 'SNIFF'; then
                _pro_lp="SNIFF"
                break
            fi
            _pro_lp="sem-sniff"
        done <<<"$(_bt_macs_conectados)"
        if [[ "${_lp}" == "?" || "${_pro_lp}" == "?" ]]; then
            if [[ "${_alias}" == Nintendo* ]]; then
                warn "modo ativo p/ Nintendo pela METADE do que dá para conferir: o nome do adaptador está certo ('${_alias}'), mas NÃO SEI dizer o estado do SNIFF (nem do adaptador, nem do Pro genuíno) — a link policy só sai de 'hciconfig lp'/'hcitool lp', que o BlueZ depreciou e não estão nesta máquina, e a mgmt API (btmgmt/bluetoothctl) não a expõe. Instale bluez-deprecated (ou bluez-deprecated-tools) para esta conferência voltar"
            else
                warn "modo ativo p/ Nintendo incompleto (alias='${_alias:-?}') e SEM COMO conferir o SNIFF nesta máquina (hciconfig/hcitool depreciados e ausentes; btmgmt/bluetoothctl não leem link policy) — reaplique: sudo /usr/local/lib/hefesto-dualsense4unix/bt_active_mode.sh"
            fi
        elif [[ -n "${_lp}" && "${_alias}" == Nintendo* ]]; then
            if [[ "${_pro_lp}" == "SNIFF" ]]; then
                warn "modo ativo p/ Nintendo: alias e SNIFF do adaptador OK, mas o Pro genuíno conectado está COM sniff (deveria ser sem). Reaplique: sudo /usr/local/lib/hefesto-dualsense4unix/bt_active_mode.sh"
            else
                pass "modo ativo p/ Nintendo (nome '${_alias}' + SNIFF no adaptador p/ o 8BitDo probar + no-sniff só no Pro genuíno — BT-SNIFF-PER-OUI-01)"
            fi
        else
            warn "modo ativo p/ Nintendo incompleto (alias='${_alias:-?}', SNIFF-adaptador=${_lp:-AUSENTE}); o adaptador deve MANTER o SNIFF (o 8BitDo precisa) — reaplique: sudo /usr/local/lib/hefesto-dualsense4unix/bt_active_mode.sh"
        fi
    fi
    done
}

# ONDA-R2: bonds em disco vs cache — a assinatura medida em 22/07 do estado
# "pareamentos que evaporam" é cache/ populado com ZERO diretórios de bond
# (<MAC>/info) em /var/lib/bluetooth. Leitura exige root (árvore 700) —
# best-effort: sem sudo -n, só informa como conferir.
check_bt_bonds_persistidos() {
    if ! sudo -n true 2>/dev/null; then
        info "sem sudo sem senha — não leio /var/lib/bluetooth (confira à mão: sudo find /var/lib/bluetooth -name info)"
        return
    fi
    local n_info n_cache
    n_info="$(sudo -n find /var/lib/bluetooth -mindepth 3 -maxdepth 3 -type f -name info 2>/dev/null | wc -l)"
    n_cache="$(sudo -n find /var/lib/bluetooth -mindepth 3 -maxdepth 3 -type f -path '*/cache/*' 2>/dev/null | wc -l)"
    if [[ "${n_info}" -gt 0 ]]; then
        pass "bonds BT persistidos em disco: ${n_info} (cache com ${n_cache} devices vistos)"
    elif [[ "${n_cache}" -gt 0 ]]; then
        fail "ZERO bonds em disco com cache de ${n_cache} devices — pareamentos vivendo só em memória (evaporam no disconnect) ou destruídos por crash; re-pareie com Pair() explícito (bluetoothctl pair <MAC>) e confira Bonded: yes; se houver snapshot: sudo /usr/local/lib/hefesto-dualsense4unix/bt_bonds_restore.sh --list"
    else
        info "nenhum bond nem cache em /var/lib/bluetooth — adaptador nunca pareou nada (ou árvore em outro lugar)"
    fi
}

# SDP-CACHE-01 (23/07, medido ao vivo): o registro SDP do perfil HID mora em
# /var/lib/bluetooth/<adapter>/cache/<MAC>, seção [ServiceRecords], e é dele que
# o BlueZ tira o descritor HID (profiles/input/device.c:hidp_add_connection).
# Uma entrada SEM essa seção acompanha o controle ZUMBI: bond íntegro, ACL
# AUTH+ENCRYPT vivo, "Conectado" na GUI — e zero hidraw, zero input.
#
# Medido: 46 bytes (só [General] Name=) no controle quebrado, contra 1124..1433
# bytes COM [ServiceRecords] nos três sãos.
#
# Este check aponta o SINTOMA, que tem duas causas possíveis (o próprio check
# não as distingue; a mensagem cobre as duas):
#   (a) só a direção da conexão — o controle reconecta ENTRANTE (PS/SYNC) e esse
#       caminho não dispara SDP browse; um Connect() iniciado pelo HOST resolve
#       (o watchdog faz isso sozinho, e o BlueZ coopera: sem [ServiceRecords] ele
#       marca svc_resolved=false, src/device.c:4415);
#   (b) o controle parou de responder SDP — aí o cache truncado é consequência,
#       não causa, e nem Connect() nem re-pareamento resolvem. Confirme com
#       `sudo sdptool browse <MAC>`: controle são responde em <1 s; travado
#       estoura o timeout. Cura: reset de hardware do controle.
check_bt_sdp_cache_envenenado() {
    if ! sudo -n true 2>/dev/null; then
        info "sem sudo sem senha — não leio o cache SDP (confira: sudo grep -L ServiceRecords /var/lib/bluetooth/*/cache/*)"
        return
    fi
    local achou=0 info_f devdir mac adpdir cache
    while IFS= read -r info_f; do
        [[ -z "${info_f}" ]] && continue
        devdir="$(dirname "${info_f}")"
        mac="$(basename "${devdir}")"
        adpdir="$(dirname "${devdir}")"
        cache="${adpdir}/cache/${mac}"
        # Só device de perfil HID (0x1124 = HumanInterfaceDevice).
        sudo -n grep -qi '^Services=.*00001124-0000-1000-8000-00805f9b34fb' "${info_f}" 2>/dev/null || continue
        # Cache ausente é SÃO: o BlueZ refaz o browse na próxima conexão.
        sudo -n test -f "${cache}" 2>/dev/null || continue
        sudo -n grep -q '^\[ServiceRecords\]' "${cache}" 2>/dev/null && continue
        achou=1
        # LEITURA SEM SUCESSOR VIVO (MIGRACAO-BLUEZ-DEPRECIADOS-01, 19/08/2026):
        # o `sdptool browse` é o único jeito de perguntar SDP DIRETO ao controle
        # sob demanda; `btmgmt`/`bluetoothctl` do 5.86 não têm equivalente
        # (`btmgmt find-service` é varredura por UUID, não browse de um device
        # já conectado). Sem ele o conselho muda: em vez de mandar a humana
        # rodar um comando que não existe na máquina dela, o doctor assume o
        # que não sabe e dá o caminho barato primeiro.
        local _como_distinguir
        if command -v sdptool >/dev/null 2>&1; then
            _como_distinguir="Primeiro confira QUAL das duas causas é: 'sudo sdptool browse ${mac}' — se responder em <1 s, é só a direção da conexão e o watchdog cura sozinho no próximo tick (Connect() pelo host, sem desparear); se ESTOURAR o timeout, o stack do controle travou e nem re-parear resolve: reset de hardware do controle (furinho atrás, ~5 s com um clipe)"
        else
            _como_distinguir="NÃO DÁ para distinguir as duas causas nesta máquina: o browse SDP sob demanda só existia no 'sdptool', que o BlueZ depreciou e não está instalado aqui (pacote bluez-deprecated / bluez-deprecated-tools), e btmgmt/bluetoothctl não o substituem. Faça o barato primeiro: o watchdog tenta Connect() a cada 2 min — se em dois ticks o [ServiceRecords] não aparecer, trate como stack do controle travado (nem re-parear resolve): reset de hardware do controle (furinho atrás, ~5 s com um clipe)"
        fi
        fail "cache SDP de ${mac} SEM [ServiceRecords] — o perfil HID não sobe (controle 'Conectado' e sem input). ${_como_distinguir}"
    done < <(sudo -n find /var/lib/bluetooth -mindepth 3 -maxdepth 3 -type f -name info 2>/dev/null | sort)
    [[ "${achou}" -eq 0 ]] && pass "cache SDP íntegro em todos os controles com bond (todos têm [ServiceRecords])"
}

# Normaliza um MAC para minúsculo sem ':' — mesma forma usada para comparar
# HID_UNIQ (sysfs) com o MAC do bluetoothctl (formatos diferem em caixa).
_mac_norm() {
    local m="${1,,}"
    printf '%s\n' "${m//:/}"
}

# HID_UNIQ de cada hidraw vivo, normalizado (um por linha). Existe em USB E
# BT (mesma fonte de sysfs_leds._read_mac); raiz parametrizada p/ teste.
_hidraw_uniqs() {
    local root="${1:-/sys/class/hidraw}"
    local f uniq
    for f in "${root}"/*/device/uevent; do
        [[ -r "${f}" ]] || continue
        uniq="$(sed -n 's/^HID_UNIQ=//p' "${f}" | head -1)"
        [[ -z "${uniq}" ]] && continue
        _mac_norm "${uniq}"
    done
}

# Sintetiza um "bloco info" mínimo via D-Bus com as linhas que as funções
# puras abaixo consomem (Device/Icon/Connected/Paired/Bonded) — as puras e
# seus testes ficam intactos enquanto a FONTE deixa de ser o bluetoothctl
# 5.86 mudo (WATCHDOG-FP-01: "nenhum dispositivo pareado" com 4 em disco).
_dbus_bt_info_bloco() {
    local p="$1" mac icon conn paired bonded
    mac="${p##*dev_}"; mac="${mac//_/:}"
    icon="$(_dbus_bt_prop "${p}" org.bluez.Device1 Icon)"
    conn="$(_dbus_bt_prop "${p}" org.bluez.Device1 Connected)"
    paired="$(_dbus_bt_prop "${p}" org.bluez.Device1 Paired)"
    bonded="$(_dbus_bt_prop "${p}" org.bluez.Device1 Bonded)"
    printf 'Device %s (public)\n' "${mac}"
    if [[ -n "${icon}" ]]; then printf '\tIcon: %s\n' "${icon}"; fi
    printf '\tConnected: %s\n' "$([[ "${conn}" == "true" ]] && echo yes || echo no)"
    printf '\tPaired: %s\n' "$([[ "${paired}" == "true" ]] && echo yes || echo no)"
    # Bonded ausente na API (BlueZ < 5.65) fica FORA do bloco — igual ao
    # bluetoothctl antigo, para a pura não acusar "meio-salvo" por engano.
    if [[ -n "${bonded}" ]]; then
        printf '\tBonded: %s\n' "$([[ "${bonded}" == "true" ]] && echo yes || echo no)"
    fi
}

# Dado UM bloco de `bluetoothctl info <mac>` + a lista de HID_UNIQ vivos,
# imprime o MAC quando o device é gamepad (Icon: input-gaming), está
# Connected: yes, E nenhum hidraw bate com ele — senão nada (silencioso).
# Função PURA: só parsing de texto, sem chamar bluetoothctl/sysfs.
_bt_gamepad_missing_hidraw() {
    local info="$1" hidraw_list="$2" mac
    mac="$(printf '%s\n' "${info}" | awk '/^Device /{print $2; exit}')"
    [[ -z "${mac}" ]] && return 0
    printf '%s\n' "${info}" | grep -q '^[[:space:]]*Icon: input-gaming' || return 0
    printf '%s\n' "${info}" | grep -q '^[[:space:]]*Connected: yes' || return 0
    if printf '%s\n' "${hidraw_list}" | grep -qxF "$(_mac_norm "${mac}")"; then
        return 0
    fi
    printf '%s\n' "${mac}"
}

check_bt_connected_sem_hidraw() {
    command -v busctl >/dev/null 2>&1 || { info "busctl ausente — pulo o check de pareamento meio-salvo"; return; }
    local paths p inf hidraw_list resultado achou=0
    paths="$(_dbus_bt_device_paths)"
    if [[ -z "${paths}" ]]; then
        info "nenhum dispositivo Bluetooth pareado — sem 'Connected sem hidraw' possível"
        return
    fi
    hidraw_list="$(_hidraw_uniqs)"
    while IFS= read -r p; do
        [[ -z "${p}" ]] && continue
        inf="$(_dbus_bt_info_bloco "${p}")"
        resultado="$(_bt_gamepad_missing_hidraw "${inf}" "${hidraw_list}")"
        if [[ -n "${resultado}" ]]; then
            achou=1
            fail "controle BT ${resultado} CONECTADO mas SEM hidraw correspondente (HID_UNIQ) — controle ZUMBI; veja o check de cache SDP logo abaixo ANTES de desparear (na maioria dos casos a causa é cache SDP envenenado e o bond não precisa ser destruído)"
        fi
    done <<<"${paths}"
    [[ "${achou}" -eq 0 ]] && pass "todo device BT conectado (gamepad) tem hidraw correspondente"
}

# Dado UM bloco de `bluetoothctl info <mac>`, imprime o MAC quando o bond
# está "meio-salvo" (Paired: yes / Bonded: no) — senão nada. Função PURA,
# mesmo padrão de _bt_gamepad_missing_hidraw.
_bt_paired_sem_bonded() {
    local info="$1" mac
    mac="$(printf '%s\n' "${info}" | awk '/^Device /{print $2; exit}')"
    [[ -z "${mac}" ]] && return 0
    printf '%s\n' "${info}" | grep -q '^[[:space:]]*Paired: yes' || return 0
    printf '%s\n' "${info}" | grep -q '^[[:space:]]*Bonded: no' || return 0
    printf '%s\n' "${mac}"
}

check_bt_paired_sem_bonded() {
    command -v busctl >/dev/null 2>&1 || { info "busctl ausente — pulo o check de bond meio-salvo"; return; }
    local paths p inf resultado achou=0
    paths="$(_dbus_bt_device_paths)"
    if [[ -z "${paths}" ]]; then
        info "nenhum dispositivo Bluetooth pareado — sem bond meio-salvo possível"
        return
    fi
    while IFS= read -r p; do
        [[ -z "${p}" ]] && continue
        inf="$(_dbus_bt_info_bloco "${p}")"
        resultado="$(_bt_paired_sem_bonded "${inf}")"
        if [[ -n "${resultado}" ]]; then
            achou=1
            fail "${resultado} Paired mas NÃO Bonded — bond meio-salvo ('No agent available for request type 2'); cura: bluetoothctl remove ${resultado} && repareie (PS no controle); confira o hefesto-bt-agent.service ativo acima"
        fi
    done <<<"${paths}"
    [[ "${achou}" -eq 0 ]] && pass "nenhum device BT com bond meio-salvo (Paired sem Bonded)"
}

# BOND-DOBRADO-01 (19/09/2026) — o mesmo controle com chave em DOIS adaptadores.
#
# ACHADO NA MESA DELA, e ninguém via: quatro DualSense, SEIS bonds. Dois
# controles com chave de pareamento em dois adaptadores ao mesmo tempo — uma
# migração feita pela metade, em que o bond do adaptador de ORIGEM ficou.
# O `§6.3` do `GUIA-RADIO-DA-SALA` manda apagá-lo justamente para isso.
#
# POR QUE É DEFEITO, e não sujeira: o DualSense guarda UM host de cada vez.
# Com bond vivo em dois adaptadores o host tem duas verdades e o controle tem
# uma — na reconexão o adaptador "errado" pode ganhar a corrida, e a fita de
# ocupação conta o mesmo controle duas vezes.
#
# E O SALVA-VIDAS PIORA: por 24 h depois de uma migração, um crash do
# `bluetoothd` DEVOLVE o bond e o cache velhos ao adaptador de origem
# (`bt_bonds_autorestore.sh:95-98`) — ele não distingue "perdi por crash" de
# "removi de propósito".
#
# ELE SÓ ACUSA. Apagar bond é destruir pareamento, e QUAL dos dois fica depende
# de onde ela quer o controle sentado — é escolha dela, não deste script.
_bond_dobrado_por_controle() {
    # Imprime `<MAC> <hciA> <hciB> …` para cada controle sob mais de um
    # adaptador. A chave é o endereço do CONTROLE, e o valor, os adaptadores.
    local paths p mac hci
    paths="$(_dbus_bt_device_paths)"
    [[ -z "${paths}" ]] && return 0
    while IFS= read -r p; do
        [[ -z "${p}" ]] && continue
        # /org/bluez/hci1/dev_AA_BB_CC_DD_EE_FF → "hci1 AA:BB:CC:DD:EE:FF"
        hci="${p#/org/bluez/}"; hci="${hci%%/*}"
        mac="${p##*/dev_}"; mac="${mac//_/:}"
        [[ -z "${mac}" || -z "${hci}" ]] && continue
        printf '%s\t%s\n' "${mac}" "${hci}"
    done <<<"${paths}" | sort -u | awk -F'\t' '
        { onde[$1] = onde[$1] " " $2; n[$1]++ }
        END { for (m in n) if (n[m] > 1) print m onde[m] }
    '
}

check_bond_dobrado() {
    command -v busctl >/dev/null 2>&1 || { info "busctl ausente — pulo o check de bond dobrado"; return; }
    local linha mac adps achou=0
    while IFS= read -r linha; do
        [[ -z "${linha}" ]] && continue
        achou=1
        mac="${linha%% *}"
        adps="${linha#* }"
        # O RECADO DIZ O GESTO — regra desta casa: quem acusa diz o comando.
        # `esquecer` da ponte apaga o bond E o cache SDP na mesma execução; o
        # cache sozinho envenena o pareamento seguinte (SDP-CACHE-01).
        warn "o controle ${mac} tem chave de pareamento em MAIS DE UM adaptador (${adps# }) — migração feita pela metade: o bond do adaptador de ORIGEM ficou. Na reconexão o adaptador errado pode ganhar a corrida, e a conta de ocupação do rádio soma o mesmo controle duas vezes. Escolha em QUAL ele deve ficar e apague o outro: sudo /usr/local/lib/hefesto-dualsense4unix/bt_ponte_privilegiada.sh esquecer <adaptador-que-sai> ${mac}"
    done < <(_bond_dobrado_por_controle)
    [[ "${achou}" -eq 0 ]] && pass "nenhum controle com bond em mais de um adaptador"
}

# CONFIG-09 (22/08/2026): a MESMA leitura que a aba Conexões mostra (seção Check-up).
#
# Por que uma linha a mais, se as cinco conferências do exame já têm linha
# própria aqui em cima (btusb autosuspend, energia dos devices USB,
# hid_playstation, bond meio-salvo). Porque a partir de hoje existe uma SEGUNDA
# superfície dizendo se dá para jogar — a aba —, e ela lê por um módulo Python
# dentro do wheel, não por este arquivo. Duas leituras do mesmo fato se afastam
# na primeira mudança, e a que ninguém roda no terminal se afasta calada: esta
# linha é o único lugar em que o módulo da aba roda numa máquina de verdade e
# publica o que concluiu, lado a lado com as checagens de onde ele veio.
#
# O módulo é que viaja nos pacotes, não este script (`install.sh:3256-3268` só
# copia o `storm_watch.sh`) — por isso a direção é esta, e não um
# `doctor.sh --json` que a aba consumiria.
#
# `_python_do_produto` e não `python3` cru: a linha da vizinhança das portas
# importa o `mesa_de_radio`, que só existe dentro do produto instalado. Com o
# python do sistema ela degrada para "não deu para conferir" — honesto, mas
# diferente do que a pessoa vê na aba, e é a aba que este check espelha.
check_exame_da_mesa() {
    local py arquivo
    py="$(_python_do_produto)"
    arquivo="${ROOT_DIR}/src/hefesto_dualsense4unix/integrations/exame_da_mesa.py"
    if [[ -z "${py}" || ! -f "${arquivo}" ]]; then
        return
    fi
    local resumo
    # O ACHADO, E NÃO A ETIQUETA — 19/09/2026, `EXAME-DA-MESA-03`.
    #
    # Até aqui este bloco juntava `i["rotulo"]`, e TODA ordem de serviço nasce
    # com o mesmo rótulo constante (`ordens_da_mesa.ROTULO_DA_ORDEM`,
    # "Mudança recomendada"). Três ordens abertas viravam
    # `"Mudança recomendada; Mudança recomendada; Mudança recomendada"` —
    # o terminal dizendo três vezes a mesma palavra e nenhum endereço.
    #
    # **PROVADO POR MORDIDA:** trocar o `porque` de uma ordem deixava esta
    # linha BYTE-IDÊNTICA. O instrumento não lia o achado.
    #
    # A TELA JÁ TINHA SIDO CURADA EM 02/09 (a aba publica `porque` como
    # `achado`), e o doctor é o SEGUNDO CHAMADOR que aquela cura não cobriu —
    # a assinatura desta casa: *quando a cura conhece a causa, ela cobre TODOS
    # os chamadores*.
    #
    # O FORMATO É O DO DONO (`exame_da_mesa._imprimir_relatorio`): uma linha
    # por item, com TAB entre os campos. O `veredito` continua saindo do
    # módulo — nada é recalculado aqui, que é a cicatriz do `6c86e295`.
    resumo="$("${py}" "${arquivo}" --censo 2>/dev/null | "${py}" -c '
import json
import sys

d = json.load(sys.stdin)
itens = d.get("itens") or []
print("veredito=" + str(d.get("veredito") or ""))
for i in itens:
    estado = str(i.get("estado") or "")
    if estado == "certo":
        continue
    rotulo = str(i.get("rotulo") or "").strip()
    porque = str(i.get("porque") or "").strip()
    # O RÓTULO FICA NA FRENTE quando ele acrescenta — ele nomeia a CLASSE do
    # achado. Quando o `porque` está vazio (nunca visto, mas o dono permite),
    # o rótulo sozinho ainda é melhor que uma linha muda.
    texto = (rotulo + ": " + porque) if (rotulo and porque) else (porque or rotulo)
    if texto:
        print("item\t" + estado + "\t" + texto)
' 2>/dev/null)"
    if [[ -z "${resumo}" ]]; then
        info "exame da mesa indisponível — rode: ${py} ${arquivo} --relatorio"
        return
    fi
    local veredito
    veredito="$(sed -n 's/^veredito=//p' <<<"${resumo}")"

    # O veredito NÃO é recalculado aqui. Ele sai de `exame_da_mesa.veredito()`,
    # que é a resposta escrita ao `6c86e295` — um segundo lugar decidindo a cor
    # do topo é exatamente como o verde volta a conviver com o vermelho.
    #
    # E O ENDEREÇO NA TELA É A ABA **CONEXÕES**, seção Check-up. Estas linhas
    # diziam "aba Configurações", que NÃO EXISTE em lugar nenhum do produto —
    # nem entre as dez abas, nem nos mockups. Quem lesse o terminal procuraria
    # uma aba que não está lá.
    local achou_algum=0
    while IFS=$'\t' read -r marca estado texto; do
        [[ "${marca}" == "item" ]] || continue
        [[ -n "${texto}" ]] || continue
        achou_algum=1
        case "${estado}" in
            problema)
                fail "exame da mesa: ${texto} (aba Conexões, seção Check-up)" ;;
            atencao)  # (noqa-acento): valor do JSON, ASCII por contrato
                warn "exame da mesa: ${texto} (aba Conexões, seção Check-up)" ;;
            *)
                info "exame da mesa: ${texto} (aba Conexões, seção Check-up)" ;;
        esac
    done <<<"${resumo}"

    if [[ "${achou_algum}" -eq 0 ]]; then
        if [[ "${veredito}" == "certo" ]]; then
            pass "exame da mesa: as conferências da aba Conexões passaram"
        else
            info "exame da mesa: nem tudo deu para conferir sem senha"
        fi
    fi
}

# PLAT-01: relatório read-only do Proton pinado (proton_pin.py --report).
#
# CONSELHO-QUE-NAO-CURA-01 (02/09/2026) — DOIS destes avisos mandavam fazer
# algo que não resolve, e conselho que não funciona é pior que aviso nenhum:
# ele gasta a confiança de quem o segue.
#
# 1. *"o manifesto do hefesto não bate — rode ./install.sh"*. Medido na máquina
#    dela: o `GE-Proton10-34` foi instalado por FORA (ProtonUp, 03/04), não tem
#    o `.hefesto-proton-pin.json` dentro, e o `ensure_pinned_proton` devolve
#    `already ("instalação pré-existente sem manifesto (mantida)")` — ele
#    MANTÉM de propósito o que a dona da máquina instalou. O install rodou com
#    rc=0 e o aviso voltou igual, porque não havia o que curar.
#    A confusão era de UMA palavra: "não bate" descreve manifesto DIVERGENTE
#    (esse o install re-extrai e cura de verdade); manifesto AUSENTE é outra
#    coisa — é não termos como atestar o SHA256 de algo que não extraímos.
#    Os dois viraram ramos separados, com o gesto que serve a cada um.
#
# 2. *"1 jogo(s) fora do Proton pinado"*, sem nome e sem razão. O jogo é o
#    DON'T SCREAM, e ele está fora PORQUE O PRODUTO RESPEITOU A ESCOLHA DELA:
#    em 14/08/2026 a trava o arrastou de `proton_11` para o pinado e o
#    microfone do jogo — que é a mecânica inteira dele — morreu. Desde 19/08 o
#    `build_compat_tool_mapping` preserva escolha por jogo e registra
#    `action="preservado"` no `proton-pin-lock.json`. Esse registro é lido
#    aqui: escolha respeitada é INFO com o nome do jogo, não WARN sem nome.
#
#    NOTA DATADA, 18/09/2026: a ordem dela de 17/09 (`--lock --todos`) revogou
#    a guarda `preservado` para jogo que roda por Proton, e o DON'T SCREAM foi
#    junto para o pino a pedido dela. Escolha, agora, é só o que tem prova —
#    o `jogos_fora_do_pino.txt` e a ferramenta que não é Proton —, e o resto
#    volta a ser WARN, com o `--fix` que trava.
check_proton_pin() {
    local py="${ROOT_DIR}/src/hefesto_dualsense4unix/integrations/proton_pin.py"
    local conf="${ROOT_DIR}/assets/proton-pin.conf"
    if [[ ! -f "${py}" || ! -f "${conf}" ]] || ! command -v python3 >/dev/null 2>&1; then
        info "proton_pin.py/proton-pin.conf ausentes ou sem python3 — pulo o check do Proton pinado"
        return
    fi
    # A RAIZ ENVENENADA — 18/09/2026, INSTALL-UNIVERSAL. O `--ensure` de antes
    # da cura, rodado numa máquina SEM Steam, deixava `~/.steam/steam` como
    # diretório real só com o nosso Proton dentro. O lançador Debian lê isso
    # como o layout histórico e adota `~/.steam` como casa da Steam — e aí o
    # pino, o Steam Input, o wrapper e o vigia miram uma raiz que ela não usa.
    # Até aqui o doctor dizia só "Steam não detectada" e calava. A régua
    # (`raiz_envenenada`) é estreita: só reprova quando TUDO lá dentro é nosso.
    local envenenada
    envenenada="$(HEFESTO_PP="${py}" python3 - <<'PY' 2>/dev/null
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(os.environ.get("HEFESTO_PP", "")).parent))
try:
    import proton_pin as pp
except Exception:  # noqa: BLE001 - sem o módulo, a checagem some e o resto segue
    sys.exit(0)
alvo = getattr(pp, "raiz_envenenada", lambda: None)()
if alvo is not None:
    print(alvo)
PY
)"
    if [[ -n "${envenenada}" ]]; then
        fail "${envenenada} é uma pasta que um instalador antigo do Hefesto criou antes de existir Steam aqui (só tem o Proton pinado dentro): com ela no caminho, a Steam adota ${HOME}/.steam como casa e o Hefesto deixa de achá-la. Com a Steam FECHADA, rode: mv \"${envenenada}\" \"${envenenada}.sobra-do-hefesto\" — na próxima abertura a Steam recria o atalho, e o vigia da Steam reextrai o Proton pinado do cache"
        return
    fi
    # T-08 (ONDA0-Z7): os quatro layouts de check_vdf_poison — antes só os
    # dois nativos, e a Steam Flatpak/Snap passava por "não detectada".
    if [[ ! -f "${HOME}/.steam/steam/config/config.vdf" \
          && ! -f "${HOME}/.local/share/Steam/config/config.vdf" \
          && ! -f "${HOME}/.var/app/com.valvesoftware.Steam/.steam/steam/config/config.vdf" \
          && ! -f "${HOME}/snap/steam/common/.steam/steam/config/config.vdf" ]]; then
        info "Steam não detectada (sem config.vdf) — pulo o check do Proton pinado"
        return
    fi
    local resumo
    resumo="$(python3 "${py}" --report 2>/dev/null | python3 -c '
import json
import sys

d = json.load(sys.stdin)
print("name=" + str(d.get("pinned_name", "")))
print("present=" + ("1" if d.get("pinned_present") else "0"))
print("manifest=" + ("1" if d.get("pinned_manifest_ok") else "0"))
print("global=" + ("1" if d.get("global_is_pinned") else "0"))
off = d.get("games_off_pin") or []
print("off=" + str(len(off)))
print("offids=" + " ".join(str(a) for a in off))
leaky = d.get("games_leaky_proton") or []
print("leaky=" + " ".join(f"{a}:{t}" for a, t in leaky))
' 2>/dev/null)"
    if [[ -z "${resumo}" ]]; then
        warn "relatório do Proton pinado indisponível — rode: python3 ${py} --report"
        return
    fi
    local nome present manifest glob off offids leaky
    nome="$(sed -n 's/^name=//p' <<<"${resumo}")"
    present="$(sed -n 's/^present=//p' <<<"${resumo}")"
    manifest="$(sed -n 's/^manifest=//p' <<<"${resumo}")"
    glob="$(sed -n 's/^global=//p' <<<"${resumo}")"
    off="$(sed -n 's/^off=//p' <<<"${resumo}")"
    offids="$(sed -n 's/^offids=//p' <<<"${resumo}")"
    leaky="$(sed -n 's/^leaky=//p' <<<"${resumo}")"

    # O `--report` é PURO de propósito (a docstring do módulo diz: "quem lê
    # arquivos é a lane de wiring"), e o doctor é a lane de wiring. É aqui que
    # se abre o manifesto e o registro do lock — os dois dados que separam um
    # conselho que cura de um que só se repete.
    local detalhe
    detalhe="$(HEFESTO_PP="${py}" HEFESTO_CONF="${conf}" HEFESTO_OFF="${offids}" \
        python3 - <<'PY' 2>/dev/null
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(os.environ.get("HEFESTO_PP", "")).parent))
try:  # o MESMO modo standalone do CLI (o uninstall roda sem venv)
    import proton_pin as pp
except Exception:  # noqa: BLE001 - sem o módulo o detalhe some, o resto segue
    sys.exit(0)
try:
    conf = pp.parse_pin_conf(
        Path(os.environ["HEFESTO_CONF"]).read_text(encoding="utf-8")
    )
except (OSError, ValueError, KeyError):
    sys.exit(0)

raiz = pp.default_compat_dir() / conf["name"]
print("compat=" + str(raiz))

alvo = raiz / pp.MANIFEST_BASENAME
if not alvo.is_file():
    estado = "ausente"
else:
    try:
        sha = json.loads(alvo.read_text(encoding="utf-8")).get("sha256")
    except (OSError, ValueError):
        sha = None
    if not isinstance(sha, str):
        estado = "corrompido"
    elif sha.lower() == conf["sha256"].lower():
        estado = "ok"
    else:
        estado = "divergente"
print("manifesto=" + estado)

try:
    registro = json.loads(
        pp.default_lock_state_path().read_text(encoding="utf-8")
    ).get("changes") or {}
except (OSError, ValueError, AttributeError):
    registro = {}
try:
    from steam_launch_options import rotulo_do_jogo
except Exception:  # noqa: BLE001 - sem rótulo o appid ainda nomeia o jogo
    def rotulo_do_jogo(appid, home=None):
        return f"appid {appid}"

# TRÊS BALDES, e o que separa é a ORDEM DELA de 17/09/2026 (*"ele e todo o
# resto de agora em diante"*), não o registro `preservado` de antes dela:
#   - NOMEADO: está no `jogos_fora_do_pino.txt` — a exceção que ela escreveu;
#   - NATIVO: a ferramenta dele não é Proton (steamlinuxruntime e afins) — a
#     escolha de rodar nativo, que o `--todos` não troca desde 18/09/2026;
#   - FORA: está num OUTRO Proton — o que a ordem manda travar.
try:
    nomeados = set(pp.ler_jogos_fora_do_pino())
    arquivo = pp.fora_do_pino_path()
except AttributeError:  # módulo de antes de 18/09
    nomeados, arquivo = set(), None
try:
    mapa = pp.extract_compat_tool_mapping(
        pp.default_config_vdf().read_text(encoding="utf-8")
    )
except (OSError, ValueError):
    mapa = {}
da_familia = getattr(pp, "e_da_familia_proton", lambda n: "proton" in n.lower())
nomeado, nativo, fora = [], [], []
for appid in (os.environ.get("HEFESTO_OFF") or "").split():
    atual = mapa.get(appid) or mapa.get("0") or (
        (registro.get(appid) or {}).get("previous_name") or "?"
    )
    if appid in nomeados:
        nomeado.append(rotulo_do_jogo(appid))
    elif atual != "?" and not da_familia(atual):
        nativo.append(f"{rotulo_do_jogo(appid)} em {atual}")
    else:
        fora.append(f"{rotulo_do_jogo(appid)} em {atual}")
print("nomeados=" + "; ".join(nomeado))
print("nativos=" + "; ".join(nativo))
print("fora=" + "; ".join(fora))
if nomeado and arquivo is not None:
    import time

    try:
        quando = time.strftime("%d/%m/%Y", time.localtime(arquivo.stat().st_mtime))
    except OSError:
        quando = "?"
    print(f"arquivo_nomeados={arquivo} (alterado em {quando})")
PY
)"
    local raiz_do_pin manifesto nomeados nativos fora arquivo_nomeados
    raiz_do_pin="$(sed -n 's/^compat=//p' <<<"${detalhe}")"
    manifesto="$(sed -n 's/^manifesto=//p' <<<"${detalhe}")"
    nomeados="$(sed -n 's/^nomeados=//p' <<<"${detalhe}")"
    nativos="$(sed -n 's/^nativos=//p' <<<"${detalhe}")"
    fora="$(sed -n 's/^fora=//p' <<<"${detalhe}")"
    arquivo_nomeados="$(sed -n 's/^arquivo_nomeados=//p' <<<"${detalhe}")"

    if [[ "${present}" == "1" && "${manifest}" == "1" ]]; then
        pass "Proton pinado presente e íntegro (${nome})"
    elif [[ "${present}" == "1" && "${manifesto}" == "divergente" ]]; then
        warn "Proton pinado presente (${nome}) e o manifesto do hefesto aponta OUTRO sha256 — $(conselho_de_instalacao)$(so_no_checkout "(re-extrai do cache e re-verifica o SHA256)")"
    elif [[ "${present}" == "1" && "${manifesto}" == "ausente" ]]; then
        info "Proton pinado presente (${nome}), instalado por FORA do hefesto (ProtonUp ou à mão): mantemos de propósito o que você instalou, e por isso NÃO dá para conferir aqui o SHA256 do release — rodar o instalador de novo não muda isto. Para ficar com a cópia que nós verificamos, tire ${raiz_do_pin:-o diretório dele} do caminho e $(conselho_de_instalacao)"
    elif [[ "${present}" == "1" && "${manifesto}" == "corrompido" ]]; then
        warn "Proton pinado presente (${nome}) e o manifesto do hefesto está ilegível — o instalador trata isso como 'sem manifesto' e MANTÉM o diretório, então rodá-lo de novo não muda nada. Para refazer verificado, tire ${raiz_do_pin:-o diretório dele} do caminho e $(conselho_de_instalacao)"
    elif [[ "${present}" == "1" ]]; then
        warn "Proton pinado presente (${nome}) mas não consegui ler o manifesto do hefesto — rode: python3 ${py} --report"
    else
        warn "Proton pinado AUSENTE (${nome}) — $(conselho_de_instalacao)$(so_no_checkout "(baixa, verifica o SHA256 e extrai por default)")"
    fi
    if [[ "${glob}" == "1" && "${off:-0}" -eq 0 ]]; then
        pass "todos os jogos travados no Proton pinado (default global + por jogo)"
    else
        [[ "${glob}" != "1" ]] && warn "default global da Steam NÃO aponta pro Proton pinado — $(_gesto_da_trava_do_pino "${present}"); ou, para refazer tudo, $(conselho_de_instalacao)"
        # FATO QUE CAIU, SUBSTITUÍDO — 18/09/2026. Aqui se dizia *"fora do
        # Proton pinado por ESCOLHA SUA (…) Não há o que consertar"* sobre todo
        # jogo com `preservado` no registro. A ordem dela de 17/09 revogou essa
        # guarda para jogo que roda por Proton, e a frase passou a dizer o
        # contrário do que ela mandou. Sobram como escolha só as duas que têm
        # prova: a exceção que ela NOMEOU, e a ferramenta que não é Proton.
        [[ -n "${nomeados}" ]] && info "fora do Proton pinado por exceção que você nomeou em ${arquivo_nomeados:-jogos_fora_do_pino.txt}: ${nomeados} — o install, o vigia da Steam e o botão não tocam nestes; para devolver um: python3 ${py} --de-volta-ao-pino APPID"
        [[ -n "${nativos}" ]] && info "rodando por uma ferramenta que não é Proton, a escolha de rodar nativo, que o produto não troca: ${nativos} — o pino existe por causa do Wine, e estes não passam por ele"
        [[ -n "${fora}" ]] && warn "jogo(s) fora do Proton pinado, em outro Proton: ${fora} — a ordem de 17/09/2026 é todo jogo que roda por Proton no pino, e um upgrade de Proton pode trazer de volta o controle duplicado neles; $(_gesto_da_trava_do_pino "${present}"). Para deixar um de fora: python3 ${py} --fora-do-pino APPID"
        if [[ "${off:-0}" -gt 0 && -z "${nomeados}" && -z "${nativos}" && -z "${fora}" ]]; then
            warn "${off} jogo(s) fora do Proton pinado — um upgrade de Proton pode reintroduzir o controle duplicado nesses jogos; $(_gesto_da_trava_do_pino "${present}")"
        fi
    fi
    if [[ -n "${leaky}" ]]; then
        warn "jogo(s) em Proton <= 9: ${leaky} — nessa família o PROTON_DISABLE_HIDRAW não existe e o controle físico VAZA duplicado no jogo; trave no Proton pinado"
    fi
}

# ---------------------------------------------------------------------------
# ESCONDE-SÓ-O-HIDRAW-01 (23/08/2026) — as TRÊS superfícies do MESMO controle.
# ---------------------------------------------------------------------------
# O `hide` do broker age em UMA superfície: `/dev/hidraw*`. O mesmo controle
# aparece em TRÊS — `hidraw`, `evdev` (`/dev/input/event*`) e `joydev`
# (`/dev/input/js*`) — e as duas de baixo continuam com a ACL da sessão dela;
# o `jsN` ainda com o bit de leitura de `other`, legível pelo mundo inteiro.
# Medido nesta bancada em 25/08/2026, um DualSense no cabo, o hidraw escondido:
#
#   /dev/hidraw4        crw-------   root root       <- escondido (0600, sem ACL)
#   /dev/input/event21  crw-rw----+  user:<ela>:rw-  <- qualquer processo dela
#   /dev/input/js0      crw-rw-r--+  other::r--      <- e mais o mundo inteiro
#
# Até 25/08/2026 este check respondia a essa cena com `pass` e o texto "o jogo
# só vê o vpad" — contagem de nós hidraw lida como resposta a uma pergunta
# sobre três superfícies. É a família O-PORTAO-QUE-NAO-MEDE-O-QUE-PROMETE no
# pior lugar possível: quem investiga "por que o Steam mostra controle
# dobrado" — o terceiro controle dela — começava lendo um verde.
#
# CONFERE E NÃO CURA, e aqui a regra é dura: nenhuma destas funções escreve
# permissão nenhuma. QUAL das três saídas o produto vai tomar (EVIOCGRAB no
# evdev, estender o `hide` a evdev/joydev, ou seguir só na env do wrapper) é
# decisão DELA — a E2 da sprint, com o preço de cada caminho na mesa. O
# instrumento só para de mentir.

#: Os nós de `/dev/input` (evdev e joydev) do MESMO device HID de um nó hidraw.
#: Um basename por linha; NADA se o sysfs não souber responder — e "nada" é
#: resposta legítima (nó recém-sumido, replug no meio da leitura), nunca
#: "está tudo fechado".
_nos_de_entrada_do_hidraw() {
    local no="$1" base hid alvo
    base="$(basename "${no}")"
    hid="$(readlink -f "/sys/class/hidraw/${base}/device" 2>/dev/null || true)"
    [[ -n "${hid}" && -d "${hid}" ]] || return 0
    for alvo in "${hid}"/input/input*/event* "${hid}"/input/input*/js*; do
        [[ -e "${alvo}" ]] || continue
        basename "${alvo}"
    done
}

#: rc=0 se um processo DELA consegue `open(2)` o nó — que é a pergunta que o
#: jogo faz. NÃO se usa `[[ -r ]]` sozinho: rodando como root ele responde
#: "sim" para tudo e o instrumento viraria outro falso verde. As três formas
#: de o nó estar alcançável, cada uma medida nesta casa:
#:   1. bit de leitura de `other` — o estado de fábrica do `jsN`;
#:   2. ACL nomeada (`user:<alguém>:r`) — a que o `uaccess` dá no login;
#:   3. grupo do nó com leitura E a sessão nesse grupo — o acidente do grupo
#:      `input`, medido na OQ-6 (funciona aqui e não numa máquina limpa).
_entrada_alcancavel_pelo_jogo() {
    local no="$1" modo grupo_no g
    [[ -e "${no}" ]] || return 1
    modo="$(stat -c '%04a' "${no}" 2>/dev/null || true)"
    [[ -n "${modo}" ]] || return 1
    case "${modo: -1}" in
        [4567]) return 0 ;;
    esac
    if command -v getfacl >/dev/null 2>&1 \
       && getfacl -p "${no}" 2>/dev/null | grep -Eq '^user:[^:]+:r'; then
        return 0
    fi
    case "${modo: -2:1}" in
        [4567])
            grupo_no="$(stat -c '%G' "${no}" 2>/dev/null || true)"
            if [[ -n "${grupo_no}" ]]; then
                for g in $(id -nG 2>/dev/null); do
                    [[ "${g}" == "${grupo_no}" ]] && return 0
                done
            fi
            ;;
    esac
    return 1
}

#: O veredito POR CONTROLE (E3 da sprint): não "quantos nós hidraw estão 0600",
#: e sim "este controle está escondido DO JOGO?".
#:
#: ESTA FUNÇÃO É METADE DA E3, e a outra metade mora no `_veredito_do_hide`.
#: O item 3.1 do O-QUE-FICOU-ABERTO-01 pede o veredito por comparação com o
#: CENSO DE FÍSICOS — "o `pass` só é honesto quando `escondidos == físicos`"
#: (2026-08-16-O-QUE-FICOU-ABERTO-01:288-291). Aqui o denominador continua
#: sendo "o que o broker escondeu", de propósito: quem compara com a MESA é o
#: bloco do censo no `_veredito_do_hide`, que roda ANTES desta medição e
#: devolve `warn` sem chegar aqui quando os dois conjuntos divergem
#: (26/08/2026 — antes disso a cena de 16/08, dois físicos e um escondido,
#: saía verde).
#:
#: Preenche CINCO globais porque bash não devolve lista (esta lista dizia
#: quatro e o código escrevia cinco — o `TRES_SUP_N_ABERTOS` sai na tela dentro
#: do `warn` e não estava aqui):
#:   TRES_SUP_CONTROLES  quantos nós hidraw escondidos ENTRARAM na varredura.
#:                       Inclui os sem mapa, logo NÃO é o número de medidos
#:   TRES_SUP_ESCONDIDOS quantos deles têm as três superfícies fechadas
#:   TRES_SUP_ABERTOS    os nós de entrada alcançáveis, por nome
#:   TRES_SUP_N_ABERTOS  quantos são esses nós
#:   TRES_SUP_SEM_MAPA   quantos o sysfs não soube mapear (não contam como bons)
#:
#: `CONTROLES - SEM_MAPA` é o que foi de fato medido, e é esse — e só esse — o
#: número que uma frase de veredito pode afirmar.
_tres_superficies_medir() {
    TRES_SUP_CONTROLES=0
    TRES_SUP_ESCONDIDOS=0
    TRES_SUP_ABERTOS=""
    TRES_SUP_N_ABERTOS=0
    TRES_SUP_SEM_MAPA=0
    local no base entradas aberto_deste
    for no in "$@"; do
        [[ -n "${no}" ]] || continue
        TRES_SUP_CONTROLES=$((TRES_SUP_CONTROLES + 1))
        entradas="$(_nos_de_entrada_do_hidraw "${no}")"
        if [[ -z "${entradas}" ]]; then
            TRES_SUP_SEM_MAPA=$((TRES_SUP_SEM_MAPA + 1))
            continue
        fi
        aberto_deste=0
        for base in ${entradas}; do
            if _entrada_alcancavel_pelo_jogo "/dev/input/${base}"; then
                aberto_deste=1
                TRES_SUP_ABERTOS="${TRES_SUP_ABERTOS} ${base}"
                TRES_SUP_N_ABERTOS=$((TRES_SUP_N_ABERTOS + 1))
            fi
        done
        [[ "${aberto_deste}" -eq 0 ]] && TRES_SUP_ESCONDIDOS=$((TRES_SUP_ESCONDIDOS + 1))
    done
    TRES_SUP_ABERTOS="${TRES_SUP_ABERTOS# }"
}

#: O CENSO DE FÍSICOS — o denominador que faltava (3.1 do O-QUE-FICOU-ABERTO-01,
#: aberto desde 16/08/2026, fechado em 26/08).
#:
#: Nunca reimplementa o critério: chama `physical_nodes_exposure`, que é o
#: MESMO validador que o broker usa para decidir o que é um DualSense físico
#: (e que recusa o vpad uhid). Duas réguas para a mesma pergunta é como esta
#: casa já produziu alarme convincente e falso.
#:
#: Só leitura, e cala em vez de falhar: sem o pacote alcançável a saída é
#: vazia, e o veredito trata "censo vazio" como "não sei", nunca como zero.
_censo_de_fisicos() {
    local py; py="$(_python_do_produto)"
    [[ -n "${py}" ]] || return 0
    HEFESTO_SRC="${ROOT_DIR}/src" "${py}" - <<'PY' 2>/dev/null || true
import os
import sys

sys.path.insert(0, os.environ.get("HEFESTO_SRC", ""))
try:
    from hefesto_dualsense4unix.broker.hidraw_broker import physical_nodes_exposure
except Exception:  # noqa: BLE001 - sem o pacote o censo simplesmente cala
    sys.exit(0)
print(" ".join(sorted(physical_nodes_exposure(os.getuid()))), end="")
PY
}

#: O veredito do hide, separado do `check_hidraw_broker` para ser TESTÁVEL sem
#: systemd, sem socket e sem aparelho — a régua que mentia nunca teve teste
#: justamente porque vivia soldada dentro de uma função de 220 linhas.
#: $1 = nós hidraw escondidos (contagem do broker); $2 = 1 se o daemon responde
#: IPC; $3 = native_mode como o IPC o devolve; $4 = o CENSO DE FÍSICOS (nós
#: separados por espaço, vazio = não sei); $5.. = os nós escondidos.
_veredito_do_hide() {
    local hidden_count="$1" daemon_vivo="$2" native_mode="$3" censo="$4"
    shift 4
    if [[ "${hidden_count}" -le 0 ]]; then
        info "broker sem nós escondidos no momento (emulação desligada ou nenhum grab ativo)"
        return
    fi
    if [[ "${daemon_vivo}" != "1" ]]; then
        fail "broker com ${hidden_count} nó(s) escondido(s) e o daemon PARADO — invariante quebrada (belts falharam); cura: sudo systemctl restart hefesto-hidraw-broker.service"
        return
    fi
    if [[ "${native_mode}" == "True" ]]; then
        warn "broker com ${hidden_count} nó(s) escondido(s) em Modo Nativo — o físico deveria estar exposto ao jogo"
        return
    fi
    # O DENOMINADOR, e por que ele vem ANTES de medir superfície nenhuma.
    #
    # Até 26/08/2026 tudo abaixo desta linha olhava SÓ os nós que o broker
    # escondeu — o veredito perguntava "o que eu escondi está fechado?" e
    # respondia "o jogo só vê o vpad", que é uma afirmação sobre a MESA
    # inteira. Um DualSense físico que o broker nunca escondeu era invisível
    # para a régua, e a cena exata de 16/08 (dois físicos, um escondido)
    # continuava saindo verde — com o controle dobrado dentro do jogo. O
    # comentário do `_tres_superficies_medir`, logo acima, já confessava isto
    # por escrito desde 25/08; o que faltava era o censo, e o produto já sabia
    # levantá-lo (`broker/hidraw_broker.py:physical_nodes_exposure`).
    #
    # Censo VAZIO é "não sei" (sem o pacote alcançável, ou sysfs ilegível) e
    # não vira zero: ausência de dado não é prova de cura.
    local _fisico _escondido _visto fora=""
    for _fisico in ${censo}; do
        _visto=0
        for _escondido in "$@"; do
            [[ "${_escondido}" == "${_fisico}" ]] && { _visto=1; break; }
        done
        [[ "${_visto}" -eq 0 ]] && fora="${fora} ${_fisico}"
    done
    fora="${fora# }"
    if [[ -n "${fora}" ]]; then
        # PROVISÓRIO — decisão dela: texto novo de tela (LEVA-1-D, 26/08/2026).
        warn "o hide não cobre a mesa inteira: ${hidden_count} nó(s) escondido(s), mas o censo do produto vê DualSense físico FORA do hide (${fora}) — o jogo enxerga esse(s) controle(s) direto, e quem enumerar /dev/input ou hidraw acha o controle dobrado; este check NÃO afirma que o jogo só vê o vpad"
        info "  confira se a emulação está ligada para ele na aba Emulação; se estiver, o broker não pegou o nó: sudo systemctl restart hefesto-hidraw-broker.service"
        return
    fi
    _tres_superficies_medir "$@"
    if [[ "${TRES_SUP_CONTROLES}" -eq 0 || "${TRES_SUP_SEM_MAPA}" -eq "${TRES_SUP_CONTROLES}" ]]; then
        pass "broker escondendo ${hidden_count} nó(s) hidraw físico(s) (giroscópio sobrevive via fd-injection)"
        info "as superfícies evdev/joydev desses nós não estão legíveis no sysfs agora — este check NÃO afirma que o jogo só vê o vpad"
        return
    fi
    [[ "${TRES_SUP_SEM_MAPA}" -gt 0 ]] && info "${TRES_SUP_SEM_MAPA} nó(s) escondido(s) sem mapa no sysfs — ficaram fora do veredito abaixo"
    if [[ -n "${TRES_SUP_ABERTOS}" ]]; then
        warn "o hide cobre SÓ o hidraw: ${TRES_SUP_ESCONDIDOS} de ${TRES_SUP_CONTROLES} controle(s) escondido(s) do jogo — o FÍSICO segue alcançável em ${TRES_SUP_N_ABERTOS} nó(s) de entrada (${TRES_SUP_ABERTOS}), e quem enumerar /dev/input em vez de hidraw acha o controle dobrado. O que separa os dois hoje é a env do wrapper (SDL_GAMECONTROLLER_IGNORE_DEVICES/PROTON_DISABLE_HIDRAW) — veja o check do wrapper de launch acima; estender o hide a evdev/joydev é decisão em aberto (ESCONDE-SÓ-O-HIDRAW-01, E2)"
        return
    fi
    # A conta é sobre o que foi MEDIDO, não sobre o que entrou na varredura.
    # `TRES_SUP_CONTROLES` inclui os nós sem mapa (é incrementado antes do
    # `continue` lá em cima), e usá-lo aqui fazia o `pass` afirmar as três
    # superfícies fechadas de controles que a linha `info` acima acabara de
    # declarar FORA do veredito. Achado pela conferência da frente C4 em
    # 25/08/2026 — é a mesma família do defeito que este bloco inteiro veio
    # curar: a régua mentindo sobre a própria cura.
    local medidos=$((TRES_SUP_CONTROLES - TRES_SUP_SEM_MAPA))
    if [[ "${TRES_SUP_SEM_MAPA}" -gt 0 ]]; then
        pass "broker escondendo ${hidden_count} nó(s) físico(s), e as TRÊS superfícies dos ${medidos} controle(s) MEDIDO(S) fechadas (hidraw + evdev + joydev). NÃO afirmo nada sobre ${TRES_SUP_SEM_MAPA} outro(s), que o sysfs não soube mapear (giroscópio sobrevive via fd-injection)"
        return
    fi
    pass "broker escondendo ${hidden_count} nó(s) físico(s), e as TRÊS superfícies dos ${medidos} controle(s) fechadas (hidraw + evdev + joydev) — o jogo só vê o vpad (giroscópio sobrevive via fd-injection)"
}

# BROKER-01 (Onda S — fd-injection): o broker root que esconde o hidraw
# FÍSICO do DualSense do JOGO (cura de raiz do duplicado, complementar ao
# wrapper de launch acima). Verifica a unit de SISTEMA (não --user), o ping
# autenticado por SO_PEERCRED, a coerência do que está escondido (com o
# daemon ativo e o Modo Nativo) e — best-effort — a recusa a outro uid.
# Desenho: docs/process/estudos/2026-07-20-desenho-onda-s-broker-fd-injection.md §7.3.
check_hidraw_broker() {
    command -v systemctl >/dev/null 2>&1 || { info "systemctl ausente — não checo o broker hide-hidraw"; return; }
    if ! systemctl cat hefesto-hidraw-broker.socket >/dev/null 2>&1; then
        info "broker hide-hidraw não instalado ($(conselho_de_instalacao)$(so_no_checkout "— BROKER-01 é DEFAULT, sem flag"))"
        return
    fi
    local sock_state
    sock_state="$(systemctl is-active hefesto-hidraw-broker.socket 2>/dev/null || true)"
    if [[ "${sock_state}" != "active" ]]; then
        warn "hefesto-hidraw-broker.socket instalado mas ${sock_state:-inativo} — o físico NÃO é escondido do jogo (P2 duplicado volta); ligue: sudo systemctl enable --now hefesto-hidraw-broker.socket"
        return
    fi
    pass "hefesto-hidraw-broker.socket ativo"

    if ! command -v python3 >/dev/null 2>&1; then
        warn "python3 ausente — não dá para pingar o broker"
        return
    fi
    local ping_out
    if ! ping_out="$(python3 - <<'PYEOF' 2>/dev/null
import glob
import json
import os
import socket
import struct

s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.settimeout(2.0)
s.connect("/run/hefesto-hidraw-broker/broker.sock")
s.sendall(json.dumps({"cmd": "ping"}).encode("utf-8") + b"\n")
buf = b""
while not buf.endswith(b"\n"):
    chunk = s.recv(4096)
    if not chunk:
        raise SystemExit(1)
    buf += chunk
resp = json.loads(buf.decode("utf-8"))
print(f"ok={resp.get('ok')}")
print(f"peer_uid={resp.get('peer_uid')}")

s.sendall(json.dumps({"cmd": "status"}).encode("utf-8") + b"\n")
buf = b""
while not buf.endswith(b"\n"):
    chunk = s.recv(65536)
    if not chunk:
        raise SystemExit(1)
    buf += chunk
resp = json.loads(buf.decode("utf-8"))
hidden = resp.get("hidden") or []
print(f"hidden_count={len(hidden)}")
# ESCONDE-SÓ-O-HIDRAW-01: a contagem não responde "o jogo está vendo o
# físico?" — o veredito precisa dos NOMES para achar, no sysfs, as outras
# duas superfícies (evdev/joydev) do MESMO device HID.
print("hidden_nodes=" + " ".join(hidden))

# Onda S (achado #9): teste FUNCIONAL do cmd `open` — a rede de segurança que
# a tabela de riscos do desenho (§9) promete para DeviceAllow=char-hidraw e
# CapabilityBoundingSet. ping/status/hide NÃO exercitam o open(2) real sob o
# device cgroup (DevicePolicy=closed): só o `open` prova que o fd-injection
# (giroscópio sobrevivendo ao hide) está vivo. Candidatos: nós já escondidos
# (status acima) + hidraw de Sony no sysfs; o validador do broker decide o
# que é físico (vpad uhid vira reject_not_physical_dualsense = pulado).
candidatos = list(hidden)
for uevent in sorted(glob.glob("/sys/class/hidraw/hidraw*/device/uevent")):
    try:
        with open(uevent, encoding="utf-8", errors="replace") as fh:
            texto = fh.read()
    except OSError:
        continue
    if "054C" not in texto.upper():
        continue
    node = "/dev/" + uevent.split("/")[4]
    if node not in candidatos:
        candidatos.append(node)

resultado = "skip"
detalhe = ""
tam_fd = struct.calcsize("i")
espaco = socket.CMSG_SPACE(2 * tam_fd)
for node in candidatos:
    s.sendall(json.dumps({"cmd": "open", "node": node}).encode("utf-8") + b"\n")
    buf = b""
    fds = []
    while not buf.endswith(b"\n"):
        chunk, anc, _flags, _addr = s.recvmsg(65536, espaco)
        for nivel, tipo, dados in anc:
            if nivel == socket.SOL_SOCKET and tipo == socket.SCM_RIGHTS:
                n = len(dados) // tam_fd
                fds.extend(struct.unpack(f"{n}i", dados[: n * tam_fd]))
        if not chunk:
            raise SystemExit(1)
        buf += chunk
    resp = json.loads(buf.decode("utf-8"))
    for fd in fds:
        try:
            os.close(fd)  # o doctor só PROVA o open; nunca segura o fd
        except OSError:
            pass
    if resp.get("ok") and fds:
        resultado = "ok"
        detalhe = node
        break
    erro = resp.get("error") or ""
    if erro == "reject_not_physical_dualsense":
        continue  # vpad/uhid: nem falha nem sucesso — segue para o próximo
    resultado = "fail"
    detalhe = f"{node} erro={erro} errno={resp.get('errno')}"
    break
print(f"open={resultado}")
print(f"open_detalhe={detalhe}")
PYEOF
)"; then
        warn "broker não respondeu no socket (/run/hefesto-hidraw-broker/broker.sock) — verifique: systemctl status hefesto-hidraw-broker.service"
        return
    fi

    local ok peer_uid hidden_count hidden_nodes
    ok="$(sed -n 's/^ok=//p' <<<"${ping_out}")"
    peer_uid="$(sed -n 's/^peer_uid=//p' <<<"${ping_out}")"
    hidden_count="$(sed -n 's/^hidden_count=//p' <<<"${ping_out}")"
    hidden_count="${hidden_count:-0}"
    hidden_nodes="$(sed -n 's/^hidden_nodes=//p' <<<"${ping_out}")"

    if [[ "${ok}" != "True" ]]; then
        warn "broker recusou o ping (autorização por SO_PEERCRED/uid falhou)"
        return
    fi
    if [[ "${peer_uid}" != "$(id -u)" ]]; then
        warn "broker ecoou peer_uid=${peer_uid}, esperado $(id -u) — SO_PEERCRED inconsistente"
    else
        pass "ping ok — peer_uid=${peer_uid} confere (SO_PEERCRED)"
    fi

    # Onda S (achado #9): veredito do teste funcional do cmd `open` (feito no
    # python acima, na MESMA lease). Com o open quebrado — DeviceAllow com
    # 'r' em vez de 'rw', CapabilityBoundingSet sem CAP_DAC_OVERRIDE, hidraw
    # como módulo não carregado — ping/status/hide continuam verdes (não
    # dependem do device cgroup) e o gyro morre em silêncio sob o hide.
    local open_res open_det
    open_res="$(sed -n 's/^open=//p' <<<"${ping_out}")"
    open_det="$(sed -n 's/^open_detalhe=//p' <<<"${ping_out}")"
    case "${open_res}" in
        ok)
            pass "cmd open serviu fd real via SCM_RIGHTS (${open_det}) — fd-injection do giroscópio operante"
            # A PORTA, DECLARADA (A-PORTA-QUE-A-CASA-CONSTRUIU-01, 15/08/2026).
            # Este diagnóstico NUNCA abre /dev/hidraw* por conta própria: ele
            # pede o fd ao broker, que é a porta que a casa construiu para o nó
            # escondido. Dizer isso na tela importa porque quem lê o doctor
            # decide, a seguir, por onde o PRÓXIMO instrumento vai medir — e a
            # sessão de 15/08 se perdeu justamente batendo na porta errada.
            info "porta: broker (SCM_RIGHTS) via /run/hefesto-hidraw-broker/broker.sock — nenhum open() direto de /dev/hidraw* neste diagnóstico"
            ;;
        fail)
            fail "cmd open do broker FALHOU (${open_det}) — o giroscópio morre sob o hide; confira DeviceAllow=char-hidraw rw e CapabilityBoundingSet (CAP_DAC_OVERRIDE) em /etc/systemd/system/hefesto-hidraw-broker.service e rode: sudo systemctl restart hefesto-hidraw-broker.service"
            ;;
        *)
            info "cmd open não testado (nenhum hidraw físico de DualSense visível agora)"
            ;;
    esac

    # Coerência escondidos x daemon ativo x Modo Nativo — só cruza se o
    # daemon responde IPC (sem ele não há campo native_mode pra cruzar).
    local sock native_mode=""
    sock="$(runtime_socket)"
    if [[ -S "${sock}" ]]; then
        native_mode="$(python3 - "${sock}" <<'PYEOF' 2>/dev/null
import json
import socket
import sys

s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.settimeout(2.0)
s.connect(sys.argv[1])
s.sendall(
    json.dumps({"jsonrpc": "2.0", "id": 1, "method": "daemon.state_full", "params": {}}).encode("utf-8")
    + b"\n"
)
buf = b""
while not buf.endswith(b"\n"):
    chunk = s.recv(65536)
    if not chunk:
        raise SystemExit(1)
    buf += chunk
data = json.loads(buf.decode("utf-8"))
res = data.get("result") or {}
print(res.get("native_mode"))
PYEOF
)"
    fi

    local daemon_vivo=0
    [[ -S "${sock}" ]] && daemon_vivo=1
    # O CENSO DE FÍSICOS é o denominador do veredito (ESCONDE-SÓ-O-HIDRAW-01,
    # item 3.1): sem ele a régua mede só o que ela mesma escondeu.
    local censo_fisicos
    censo_fisicos="$(_censo_de_fisicos)"
    # shellcheck disable=SC2086  # a lista de nós é gerada aqui e não tem espaço no nome
    _veredito_do_hide "${hidden_count}" "${daemon_vivo}" "${native_mode}" "${censo_fisicos}" ${hidden_nodes}

    # Recusa a outro uid — best-effort (só roda com sudo -n disponível e o
    # usuário nobody presente); nunca falha o doctor por esta checagem.
    if sudo -n true 2>/dev/null && id nobody >/dev/null 2>&1; then
        if sudo -n -u nobody python3 - <<'PYEOF' >/dev/null 2>&1
import json
import socket
import sys

s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.settimeout(2.0)
s.connect("/run/hefesto-hidraw-broker/broker.sock")
s.sendall(json.dumps({"cmd": "ping"}).encode("utf-8") + b"\n")
buf = s.recv(4096)
sys.exit(0 if buf else 1)
PYEOF
        then
            warn "broker respondeu ping para outro uid (nobody) — recusa por SO_PEERCRED/DAC NÃO está funcionando"
        else
            pass "broker recusa outro uid (nobody) — DAC do socket + SO_PEERCRED ok"
        fi
    else
        info "validação de recusa a outro uid pulada (sem sudo -n ou usuário nobody ausente)"
    fi
}

# ---------------------------------------------------------------------------
# TECLADO-QUE-NAO-DIGITA-01 — o teclado na tela que o L3 do controle abre.
# ---------------------------------------------------------------------------
# ESTE CHECK CONFERE E NÃO CURA. É regra desta casa, e aqui ela tem dente
# próprio: instalar pacote de sistema é decisão com senha de root, e o doctor
# roda no meio de um diagnóstico — quem instala é o install.sh (passo 4f e o
# bloco dos formatos de pacote), quem confere é este. Nem o `--fix` toca nisto.
#
# O CONTRATO DE NOMES é o mesmo do `scripts/install_osk.sh` e o mesmo do
# `daemon/subsystems/keyboard.py`, e o `scripts/check_packaging_parity.sh`
# cobra a coincidência dos três: instalador, conferidor e daemon têm de estar
# falando do MESMO binário para a MESMA sessão, senão o produto instala um e
# procura outro — e ninguém percebe, porque cada um dos três passa sozinho.
#
# A ARMADILHA QUE ESTE CHECK EXISTE PARA NÃO REPETIR (commit 108b711):
# "install.sh ARMA, uninstall.sh DESARMA, doctor.sh lê a AUSÊNCIA como escolha
# dela — máquina curada e máquina quebrada são o MESMO estado para o portão".
# Aqui a ausência tem QUATRO histórias possíveis, e o binário faltando é
# idêntico nas quatro:
#
#   1. o install nunca passou por aqui (produto anterior a esta cura, ou
#      install nunca rodado nesta máquina);
#   2. ela pediu para pular (`--no-osk`);
#   3. o install TENTOU e não conseguiu (sem sudo, sem rede, distro sem o
#      pacote);
#   4. o pacote foi instalado e alguém o removeu depois — não fomos nós: o
#      uninstall do Hefesto NUNCA remove pacote de sistema.
#
# O que as distingue é a sentinela que o install grava
# (~/.local/state/hefesto-dualsense4unix/teclado-na-tela.conf). Sem ela, este
# check só poderia dizer "não tem" — que é exatamente a resposta que fez a
# máquina dela ficar quatro dias quebrada em agosto. O caso (2) é o único que
# NÃO é FAIL: é escolha dela, registrada e datada.
readonly OSK_BIN_WAYLAND="wvkbd-mobintl"
readonly OSK_BIN_X11="onboard"
readonly OSK_PKG_WAYLAND="wvkbd"
readonly OSK_PKG_X11="onboard"
# `${HOME:-}` e não `${HOME}`: este `readonly` roda no SOURCE do arquivo, e o
# doctor.sh é sourceado por testes de unidade das funções de parse com um
# ambiente mínimo, sem HOME (ver o rodapé deste arquivo). Sob `set -u`, um
# `${HOME}` aqui derruba o source inteiro com "unbound variable" — e o que
# quebra não é o teclado na tela, é toda a suíte que source este arquivo.
readonly OSK_SENTINELA="${HOME:-}/.local/state/hefesto-dualsense4unix/teclado-na-tela.conf"

# `WAYLAND_DISPLAY` primeiro, `DISPLAY` só depois: numa sessão Wayland com
# XWayland os DOIS estão setados (nesta máquina, `WAYLAND_DISPLAY=wayland-1` e
# `DISPLAY=:1`), então olhar `DISPLAY` antes diria "X11" para toda sessão
# Wayland moderna — e o veredito sairia invertido.
_osk_sessao() {
    if [[ -n "${WAYLAND_DISPLAY:-}" ]] || [[ "${XDG_SESSION_TYPE:-}" == "wayland" ]]; then
        printf 'wayland\n'
    elif [[ -n "${DISPLAY:-}" ]] || [[ "${XDG_SESSION_TYPE:-}" == "x11" ]]; then
        printf 'x11\n'
    else
        printf 'desconhecida\n'
    fi
}

_osk_sentinela() {
    local chave="$1"
    [[ -r "${OSK_SENTINELA}" ]] || return 1
    sed -n "s/^${chave}=//p" "${OSK_SENTINELA}" | head -1
}

check_teclado_na_tela() {
    local sessao esperado pacote gestor comando instalado outro
    sessao="$(_osk_sessao)"
    if [[ "${sessao}" == "x11" ]]; then
        esperado="${OSK_BIN_X11}";     pacote="${OSK_PKG_X11}"
        outro="${OSK_BIN_WAYLAND}"
    else
        esperado="${OSK_BIN_WAYLAND}"; pacote="${OSK_PKG_WAYLAND}"
        outro="${OSK_BIN_X11}"
    fi
    gestor="sua distribuição"
    comando="instale o pacote ${pacote} pela ${gestor}"
    if command -v apt-get >/dev/null 2>&1; then
        comando="sudo apt install ${pacote}"
    elif command -v dnf >/dev/null 2>&1; then
        comando="sudo dnf install ${pacote}"
    elif command -v pacman >/dev/null 2>&1; then
        comando="sudo pacman -S ${pacote}"
    fi

    if command -v "${esperado}" >/dev/null 2>&1; then
        pass "teclado na tela: ${esperado} instalado (sessão ${sessao}) — o L3 do controle abre"
        return
    fi

    # O caso que mais engana: o binário do OUTRO mundo está instalado. "Tem
    # teclado na tela" seria verdade e resposta errada — o onboard numa sessão
    # Wayland ABRE (via XWayland) e as teclas só chegam a clientes XWayland; o
    # wvkbd numa sessão X11 nem abre, porque é cliente Wayland puro.
    if command -v "${outro}" >/dev/null 2>&1; then
        if [[ "${sessao}" == "x11" ]]; then
            warn "teclado na tela: só ${outro} instalado, e esta sessão é X11 — ele é cliente Wayland puro e não abre aqui"
        else
            warn "teclado na tela: só ${outro} instalado, e esta sessão é Wayland — ele digita por XTEST e as teclas só chegam a janelas XWayland (abre e não digita)"
        fi
        info "quem digita nesta sessão é ${esperado}: ${comando}"
        info "o Hefesto NÃO remove o ${outro} — pacote de sistema é seu, não nosso"
        return
    fi

    # Daqui para baixo: nenhum dos dois no disco. Qual das quatro histórias?
    local resultado motivo data pacote_gravado
    resultado="$(_osk_sentinela resultado || true)"
    motivo="$(_osk_sentinela motivo || true)"
    data="$(_osk_sentinela data || true)"
    pacote_gravado="$(_osk_sentinela pacote || true)"

    case "${resultado}" in
        pulado)
            # ESCOLHA DELA — e é por isso que não é FAIL. Sem a sentinela esta
            # linha seria indistinguível do FAIL de baixo, que é o defeito de
            # 04/08 (108b711) inteiro em uma frase.
            info "teclado na tela: PULADO a pedido (${motivo:-"--no-osk"}, em ${data:-data não registrada})"
            info "o L3 do controle avisa na tela que não tem o que abrir, em vez de abrir"
            info "para ter: ${comando} (ou reinstale sem --no-osk)"
            ;;
        instalado|ja-instalado)
            fail "teclado na tela: o install registrou ${pacote_gravado:-${pacote}} instalado em ${data:-data não registrada}, e ele NÃO está mais na máquina"
            info "não fomos nós: o uninstall do Hefesto nunca remove pacote de sistema"
            info "para devolver: ${comando}"
            ;;
        falhou|dry-run)
            fail "teclado na tela: o install TENTOU instalar ${pacote_gravado:-${pacote}} e não conseguiu (motivo: ${motivo:-não registrado}, em ${data:-data não registrada})"
            info "rode: ${comando}"
            ;;
        *)
            fail "teclado na tela AUSENTE (${esperado}) e o install nunca passou por aqui — sem sentinela em ${OSK_SENTINELA}"
            info "é o ÚNICO caminho de fábrica para ESCREVER TEXTO com o controle:"
            info "nenhum dos nove atalhos padrão digita letra (Super, PrintScreen,"
            info "Alt+Tab, Alt+Shift+Tab, Enter, Delete, Backspace e os dois de OSK)"
            info "rode: ${comando}    — ou $(conselho_de_instalacao)"
            ;;
    esac
}

# GYRO-03: o giroscópio está chegando ao jogo? ------------------------------
# O vpad uhid (máscara DualSense Edge) expõe um nó evdev próprio de motion
# ("Hefesto Virtual DualSense PN Motion Sensors"). Com o espelho de motion do
# daemon vivo (PhysicalReportReader), esse nó AMOSTRA continuamente — o gyro
# de um DualSense real nunca fica em silêncio absoluto (ruído do sensor).
# Silêncio de ~1s = o gyro NÃO está fluindo pro jogo. READ-ONLY: leitura
# O_RDONLY sem grab, o mesmo probe validado à mão em 2026-07-19.

# Nós eventN dos Motion Sensors DOS VPADS (nunca os do físico — o nome do
# físico começa com "Sony..."/"DualSense..."; só o vpad tem o prefixo
# "Hefesto Virtual"). Fonte parametrizada p/ teste hermético.
_vpad_motion_event_nodes() {
    local src="${1:-/proc/bus/input/devices}"
    [[ -r "${src}" ]] || return 0
    awk '
        /^N: Name=/ {
            alvo = ($0 ~ /Hefesto Virtual DualSense P[0-9]+ Motion Sensors/)
        }
        alvo && /^H: Handlers=/ {
            for (i = 2; i <= NF; i++) {
                t = $i
                sub(/^Handlers=/, "", t)
                if (t ~ /^event[0-9]+$/) print t
            }
        }
    ' "${src}" 2>/dev/null
}

# Amostra ~1s de UM nó evdev (só leitura, sem grab) e imprime "vivo" quando
# chega pelo menos um evento EV_ABS de eixo de gyro/accel, ou "silencio".
# GYRO-03-FIX: o hid_playstation emite EV_MSC/MSC_TIMESTAMP neste nó a CADA
# report 0x01 do vpad, mesmo com a janela de motion NEUTRA (espelho morto) —
# stick/botão durante a amostra virava falso "vivo". Só EV_ABS (type=3) com
# code de gyro/accel (ABS_X..ABS_RZ = 0..5) prova gyro fluindo: espelho vivo
# = ruído do sensor mudando valor sempre; janela neutra = o input core
# suprime ABS repetido e NADA de EV_ABS sai (mesma lógica do probe manual de
# 2026-07-19). struct input_event (64-bit) = 24 B: 16 de timestamp + u16
# type + u16 code + s32 value → com `od -tu2 -w24`, type é o 9º campo e
# code o 10º.
_motion_node_sample() {
    local node="$1" dur="${2:-1}"
    local veredito
    veredito="$(timeout "${dur}" dd if="${node}" bs=24 2>/dev/null \
        | od -An -v -tu2 -w24 \
        | awk '$9 == 3 && $10 <= 5 { print "vivo"; exit }')"
    printf '%s\n' "${veredito:-silencio}"
}

check_vpad_motion() {
    local nodes
    nodes="$(_vpad_motion_event_nodes)"
    if [[ -z "${nodes}" ]]; then
        info "nenhum nó Motion de vpad agora (emulação desligada, backend uinput ou máscara xbox) — giroscópio via vpad não se aplica"
        return
    fi
    local ev node veredito
    for ev in ${nodes}; do
        node="/dev/input/${ev}"
        if [[ ! -r "${node}" ]]; then
            warn "sem permissão de leitura em ${node} — não deu para amostrar o giroscópio do vpad (regra udev/uaccess? rode como o usuário da sessão)"
            continue
        fi
        veredito="$(_motion_node_sample "${node}")"
        if [[ "${veredito}" == "vivo" ]]; then
            pass "giroscópio chegando ao jogo: SIM (${ev} amostrando)"
        else
            warn "giroscópio chegando ao jogo: NÃO (${ev} em silêncio por ~1s) — o espelho de motion do daemon não está alimentando este vpad; veja motion_streaming/motion_hz abaixo e o journal do daemon"
        fi
    done
    # Telemetria do daemon (motion_streaming/motion_hz por vpad) — contexto
    # extra quando o IPC responde; a amostragem acima já deu o veredito.
    local sock; sock="$(runtime_socket)"
    [[ -S "${sock}" ]] || return 0
    command -v python3 >/dev/null 2>&1 || return 0
    local out
    out="$(python3 - "${sock}" <<'PYEOF' 2>/dev/null
import json
import socket
import sys

s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.settimeout(2.0)
s.connect(sys.argv[1])
s.sendall(
    json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": "daemon.state_full", "params": {}}
    ).encode("utf-8")
    + b"\n"
)
buf = b""
while not buf.endswith(b"\n"):
    chunk = s.recv(65536)
    if not chunk:
        raise SystemExit(1)
    buf += chunk
data = json.loads(buf.decode("utf-8"))
res = data.get("result") or {}
for item in (res.get("rumble_ff") or {}).get("per_vpad") or []:
    streaming = "sim" if item.get("motion_streaming") else "não"
    hz = item.get("motion_hz") or 0.0
    print(
        f"vpad do jogador {item.get('player')}: espelho de motion "
        f"{'ATIVO' if streaming == 'sim' else 'inativo'} ({hz:.0f} Hz)"
    )
PYEOF
)" || return 0
    if [[ -n "${out}" ]]; then
        while IFS= read -r linha; do info "${linha}"; done <<<"${out}"
    fi
}

check_steam_input() {
    local script="${ROOT_DIR}/scripts/disable_steam_input.sh"
    if [[ ! -x "$script" ]]; then
        info "scripts/disable_steam_input.sh ausente — skip"
        return
    fi
    # Reusa o --status do próprio script (cobre deb/flatpak/snap, todos os users).
    local out
    out="$(bash "$script" --status 2>&1)"
    if printf '%s\n' "$out" | grep -q 'tudo limpo'; then
        pass "Steam Input PSSupport desligado em todos os localconfig.vdf"
    elif printf '%s\n' "$out" | grep -q 'ação sugerida'; then
        fail "Steam Input ATIVO (PSSupport=2 ou UseSteamControllerConfig=2) — conflita com o daemon; rode: scripts/doctor.sh --fix"
    elif printf '%s\n' "$out" | grep -q 'nenhum localconfig.vdf encontrado'; then
        info "Steam não detectada (sem localconfig.vdf)"
    else
        info "Steam Input status:"
        printf '%s\n' "$out" | sed 's/^/         /'
    fi
}

# R-06 (auditoria 23/07): a allowlist per-app do Steam Input
# (`steam_input_apps.txt`) era INERTE fora do guard de VDF — nada no caminho de
# lançamento a consultava e o broker escondia o hidraw do físico do mesmo jeito,
# então o jogo cujo DualSense vem PELA Steam (medido: Mullet Mad Jack, 2111190)
# não achava controle nenhum.
#
# FATO SUBSTITUÍDO — 16/08/2026 (a regra dela de 11/08: número errado não vira
# nota de rodapé, sai). Este check reprovava com [FAIL] quando o
# `steam_app_<appid>.env` de um jogo da allowlist trazia
# `SDL_GAMECONTROLLER_IGNORE_DEVICES`/`PROTON_DISABLE_HIDRAW` ("a exceção NÃO
# vale"). **Isso deixou de ser verdade em 09/08**, com a decisão dela
# ESCONDER-EM-VEZ-DE-SAIR-01: a marca passou a significar "esconda o controle
# FÍSICO neste jogo", e a JOGO-01 escreveu o invariante que voltou a valer —
# *"a allowlist muda QUAL dispositivo o jogo vê, nunca QUANTOS"*. O obituário
# do ramo está no cabeçalho de `daemon/launch_env.py`: **o jogo marcado recebe
# exatamente a mesma env de qualquer outro jogo**, dedup incluído. A nota datada
# de `tests/unit/test_r06_allowlist_steam_input.py` diz o mesmo com outras
# palavras: *"a env sem dedup virou a AUSÊNCIA de ramo"*.
#
# Ou seja: o [FAIL] passou 7 dias exigindo o estado que a decisão dela matou de
# propósito, e o `.env` que ele acusava era o CERTO. Medido em 16/08 05h: os
# dois jogos da allowlist com `.env` (Pragmata e Sackboy) reprovavam, e o
# install termina imprimindo os [FAIL] do doctor — todo install dela acabava em
# vermelho por causa de uma doutrina morta. O ramo sai; o que se observa
# continua na tela, como `info`.
#
# O que este check pergunta HOJE, e por quê:
#   1. QUAIS jogos estão na lista (nome, não appid) — nomear é o conserto do
#      defeito nº 2 desta noite;
#   2. o Steam Input está mesmo LIGADO na Steam para cada um? Entrar na lista
#      não liga nada: o arquivo só IMPEDE o guard de desligar. Uma entrada
#      posta depois de o guard já ter zerado o jogo é inerte para sempre.
check_steam_input_allowlist() {
    local arquivo="${XDG_CONFIG_HOME:-$HOME/.config}/hefesto-dualsense4unix/steam_input_apps.txt"
    if [[ ! -f "${arquivo}" ]]; then
        info "sem allowlist per-app do Steam Input (${arquivo} ausente) — nenhum jogo pediu exceção"
        return
    fi
    local appids
    # `[:blank:]` (espaço e tab), NUNCA `[:space:]`. O `tr -d '[:space:]'` que
    # estava aqui apagava também as QUEBRAS DE LINHA, e o `tr` trabalha sobre o
    # fluxo inteiro: a allowlist de três appids virava UM appid de 21 dígitos
    # ("211119033576501599660"), que nunca tem `.env`, e o check avisava
    # "1/1 appid(s) sem .env materializado" para sempre — desde 23/07.
    #
    # O defeito sobreviveu 24 dias porque a mensagem CONTAVA em vez de NOMEAR:
    # "1/1" é plausível, e ninguém desconfia de um número. Na primeira execução
    # em que o check diz o NOME, o appid-monstro aparece na tela e o defeito
    # dura um minuto. É a mesma lição do Pragmata, medida de novo em 16/08 —
    # e é a razão de este arquivo ter passado a nomear em toda parte.
    appids="$(sed 's/#.*$//' "${arquivo}" 2>/dev/null | tr -d '[:blank:]' | grep -E '^[0-9]+$' || true)"
    if [[ -z "${appids}" ]]; then
        info "allowlist per-app do Steam Input vazia (${arquivo})"
        return
    fi
    local appid rotulo valor nomes="" desligado="" ausente=""
    for appid in ${appids}; do
        [[ -n "${appid}" ]] || continue
        # NOMEAR-EM-VEZ-DE-CONTAR-01 (16/08/2026): até hoje este check dizia
        # "1/3 appid(s) sem .env" e nunca QUAL — a mesma cegueira que deixou o
        # Pragmata quebrado a noite toda enquanto o contador do wrapper passava
        # em verde. "1/3" não diz em que jogo ela vai esbarrar, e é justamente
        # isso que ela precisa saber para decidir se abre o jogo hoje.
        rotulo="$(_rotulo_do_appid "${appid}")"
        nomes+="${nomes:+; }${rotulo}"
        # Entrar na allowlist NÃO liga o Steam Input de jogo nenhum:
        # `add_appid_to_steam_input_allowlist` escreve UMA linha no nosso `.txt`
        # e nada mais. A única coisa que o arquivo faz é impedir o guard
        # (`disable_steam_input.sh`) de ZERAR um `UseSteamControllerConfig` que
        # JÁ estava em 1|2. Se o guard passou por ali antes de o appid entrar na
        # lista, o valor foi a zero e não volta sozinho — a entrada fica lá para
        # sempre, inerte, e a casa acha que cumpriu o pedido dela.
        # Medido em 16/08: o Sackboy (1599660) está na allowlist com
        # `UseSteamControllerConfig "0"` no vdf, marcado por ela no editor de
        # perfil e desligado na Steam.
        valor="$(_steam_input_do_appid "${appid}")"
        case "${valor}" in
            0) desligado+="${desligado:+; }${rotulo}" ;;
            "") ausente+="${ausente:+; }${rotulo}" ;;
        esac
    done
    pass "allowlist do Steam Input (o Hefesto não desliga o Steam Input destes): ${nomes}"
    [[ -n "${desligado}" ]] && warn "jogo(s) na allowlist com o Steam Input DESLIGADO na Steam (UseSteamControllerConfig=0): ${desligado} — entrar na allowlist só IMPEDE o Hefesto de desligar, nunca LIGA; ligue na Steam (Propriedades → Controle → 'Ativar Entrada Steam'), ou tire o jogo da lista se a intenção mudou"
    [[ -n "${ausente}" ]] && info "jogo(s) na allowlist sem a chave UseSteamControllerConfig no vdf (a Steam nunca gravou nada para eles): ${ausente} — vale o default da Steam, que esta casa não mediu; abrir Propriedades → Controle uma vez faz a Steam escrever a chave"
    return 0
}

# O nome do jogo a partir do appid, para os checks que precisam NOMEAR. Sem o
# pacote (python3 ausente, repo incompleto) cai no "appid N", que ainda é
# melhor que um número solto no meio de uma frase.
_rotulo_do_appid() {
    local appid="$1"
    if ! command -v python3 >/dev/null 2>&1; then
        printf 'appid %s' "${appid}"
        return 0
    fi
    HEFESTO_SRC="${ROOT_DIR}/src" HEFESTO_APPID="${appid}" python3 - <<'PY' 2>/dev/null || printf 'appid %s' "${appid}"
import os
import sys

sys.path.insert(0, os.environ.get("HEFESTO_SRC", ""))
appid = os.environ.get("HEFESTO_APPID", "")
try:
    from hefesto_dualsense4unix.integrations.steam_launch_options import rotulo_do_jogo
except Exception:  # noqa: BLE001
    print("appid %s" % appid, end="")
else:
    print(rotulo_do_jogo(appid), end="")
PY
}

# `UseSteamControllerConfig` do appid nos localconfig.vdf: "2"/"1" (ligado),
# "0" (desligado) ou vazio (a chave não existe — a Steam nunca escreveu nada
# para este jogo, e aí o que vale é o default dela, que não medimos).
#
# A chave NÃO mora na mesma árvore que o `LaunchOptions`: no vdf dela ela está
# em `UserLocalConfigStore/apps/<appid>`, enquanto o `LaunchOptions` vivo está
# em `UserLocalConfigStore/Software/Valve/Steam/apps/<appid>`. Por isso aqui a
# busca é pelo BLOCO do appid, em qualquer árvore — é o mesmo critério do
# `disable_steam_input.sh`, que é quem escreve esta chave.
_steam_input_do_appid() {
    local appid="$1" vdf linha
    shopt -s nullglob
    # T-08 (ONDA0-Z7): os quatro layouts de check_vdf_poison — a lista antiga
    # cobria só dois nativos mais um terceiro caminho não-canônico
    # ("debian-installation", fora de RAIZES_STEAM_RELATIVAS).
    for vdf in "${HOME}/.steam/steam/userdata/"*/config/localconfig.vdf \
               "${HOME}/.local/share/Steam/userdata/"*/config/localconfig.vdf \
               "${HOME}/.var/app/com.valvesoftware.Steam/.steam/steam/userdata/"*/config/localconfig.vdf \
               "${HOME}/snap/steam/common/.steam/steam/userdata/"*/config/localconfig.vdf; do
        [[ -f "${vdf}" ]] || continue
        linha="$(awk -v alvo="${appid}" '
            /^[[:space:]]*"[^"]*"[[:space:]]*$/ { nome = $0; gsub(/^[[:space:]]*"|"[[:space:]]*$/, "", nome); pend = nome; next }
            /^[[:space:]]*\{[[:space:]]*$/ { depth++; stack[depth] = pend; pend = ""; next }
            /^[[:space:]]*\}[[:space:]]*$/ { if (depth > 0) { delete stack[depth]; depth-- } next }
            /"UseSteamControllerConfig"/ {
                if (depth > 0 && stack[depth] == alvo) {
                    if (match($0, /"UseSteamControllerConfig"[^"]*"[^"]*"/)) {
                        v = substr($0, RSTART, RLENGTH)
                        sub(/.*"UseSteamControllerConfig"[^"]*"/, "", v)
                        sub(/"$/, "", v)
                        print v
                    }
                }
            }
        ' "${vdf}" 2>/dev/null | head -1)"
        if [[ -n "${linha}" ]]; then
            shopt -u nullglob
            printf '%s' "${linha}"
            return 0
        fi
    done
    shopt -u nullglob
    return 0
}

check_controller() {
    # As duas linhas abaixo LISTAM nós, e nunca abrem nenhum: `[[ -e ]]` e `ls`
    # não fazem `open(2)`. É a exceção declarada no portão da porta
    # (tests/unit/test_a_porta_que_a_casa_construiu_01.py) — quem precisa de um
    # fd de hidraw neste arquivo pede ao broker, em `check_hidraw_broker`.
    local h hidraw=0
    for h in /dev/hidraw*; do [[ -e "$h" ]] && hidraw=1; done
    [[ "${hidraw}" -eq 1 ]] && info "nós hidraw: $(ls /dev/hidraw* 2>/dev/null | tr '\n' ' ')"
    if command -v lsusb >/dev/null 2>&1 && lsusb 2>/dev/null | grep -qiE '054c'; then
        pass "DualSense conectado via USB (vendor 054c)"
    elif command -v bluetoothctl >/dev/null 2>&1 && timeout 4 bluetoothctl devices 2>/dev/null | grep -qi 'DualSense'; then
        pass "DualSense pareado via Bluetooth (conecte para usar)"
    else
        warn "controle não detectado agora — conecte o DualSense para testar"
    fi
}

# PURA: varre regras udev e imprime `arquivo:linha:conteúdo` de toda regra que
# abre TODO nó hidraw para quem não é dono nem do grupo. Nenhum privilégio é
# necessário — `/etc/udev/rules.d` e `/usr/lib/udev/rules.d` são legíveis por
# qualquer usuário. Sem argumento, varre esses dois, nessa ordem.
#
# ACUSA-O-CULPADO-01 (medido nesta máquina em 06/08/2026). O aviso antigo dizia
# "provável ajuste manual" para cada nó 0666 — e o ajuste manual não existia. A
# causa era UMA linha, `KERNEL=="hidraw*", MODE="0666"`, num arquivo de terceiro
# (`60-openrgb.rules`), que abria os SEIS nós que ninguém reivindicava — entre
# eles os receptores do teclado e do mouse dela. A mensagem acusava a única
# pessoa que não tinha feito aquilo, e mandava procurar onde não estava.
#
# Os três critérios, e por que cada um:
#
#  1. a linha tem de casar `hidraw` (`KERNEL=="hidraw*"` ou `SUBSYSTEM=="hidraw"`);
#  2. o MODE tem de dar algum bit para OUTROS (último octeto != 0). O check
#     antigo casava só o literal `666` e deixava passar `664`, `662` e `646` —
#     e é o bit de LEITURA (4) que vaza o que é digitado, não só o de escrita;
#  3. a regra NÃO pode estreitar por aparelho. `ATTRS{idVendor}`, `KERNELS==` e
#     companhia são o que separa "abriu o gamepad dele" de "abriu a máquina
#     inteira". CONTROLE POSITIVO vivo nesta máquina:
#     `/usr/lib/udev/rules.d/71-pdp-controllers.rules` tem `MODE="0666"` com
#     `ATTRS{idVendor}=="0e6f"` — é regra de distro, mira UM controle, e NÃO
#     pode aparecer aqui.
#
# SOMBRA: arquivo de mesmo nome em `/etc` anula o de `/usr/lib` (é assim que o
# udev resolve), então o primeiro diretório em que o nome aparece é o que vale.
#
# RESTAURO-SO-COM-SINTOMA-01 (07/08/2026): a varredura ganhou uma SEGUNDA vista,
# e o corpo virou `_udev_hidraw_scan <manta|estreita>` para as duas nascerem do
# MESMO awk. O motivo é a lição da RECEITA-ERRADA-01: enquanto o critério for
# escrito duas vezes, ele diverge — e o pior lugar para a divergência aparecer é
# a tela, porque é ali que ela vira instrução.
#
#   manta    = a regra abre TODO hidraw (a de ACUSA-O-CULPADO-01, acima);
#   estreita = a regra abre hidraw MAS estreita por aparelho. Essa NUNCA é
#              acusada — e agora precisa ser ENUMERADA, porque é ela que
#              distingue "nó aberto por decisão de terceiro" (mexer é atropelo,
#              e o próximo evento de udev desfaz) de "nó aberto sem explicação"
#              (é aí, e só aí, que o restauro vale). CONTROLE POSITIVO vivo
#              nesta máquina em 07/08: `71-pdp-controllers.rules:8` abre um
#              controle PDP com MODE="0666" estreitando por idVendor 0e6f.
#
# Na vista `estreita` a saída ganha um campo: `arquivo:linha:ids:conteúdo`, onde
# `ids` são os identificadores de 4 hex citados pela regra (minúsculos, com
# vírgula no fim de cada um). O casamento com o nó é DELIBERADAMENTE frouxo — um
# id em comum basta — porque todo erro dele tem de cair para o lado de NÃO agir.
_udev_hidraw_scan() {
    local vista="$1"; shift
    local dirs=("$@")
    [[ ${#dirs[@]} -gt 0 ]] || dirs=(/etc/udev/rules.d /usr/lib/udev/rules.d)
    local d f base v sombreado vistos=()
    for d in "${dirs[@]}"; do
        [[ -d "${d}" ]] || continue
        for f in "${d}"/*.rules; do
            [[ -f "${f}" ]] || continue
            base="${f##*/}"
            sombreado=0
            for v in ${vistos[@]+"${vistos[@]}"}; do
                [[ "${v}" == "${base}" ]] && sombreado=1
            done
            vistos+=("${base}")
            [[ "${sombreado}" -eq 1 ]] && continue
            awk -v arq="${f}" -v vista="${vista}" '
                {
                    linha = $0
                    sub(/^[[:space:]]+/, "", linha)
                    sub(/[[:space:]]+$/, "", linha)
                }
                linha == "" || linha ~ /^#/ { next }
                linha !~ /KERNEL=="hidraw/ && linha !~ /SUBSYSTEM=="hidraw"/ { next }
                {
                    if (match(linha, /MODE[[:space:]]*:?=[[:space:]]*"[0-7]+"/) == 0) next
                    modo = substr(linha, RSTART, RLENGTH)
                    # O valor do MODE sai do texto ANTES da colheita de ids:
                    # "0666" é quatro dígitos hexadecimais válidos e viraria um
                    # identificador fantasma em toda regra estreitada.
                    resto = substr(linha, 1, RSTART - 1) substr(linha, RSTART + RLENGTH)
                    gsub(/[^0-7]/, "", modo)
                    if (modo == "") next
                    outros = substr(modo, length(modo), 1)
                    if (outros == "0") next

                    # Estreitamento por aparelho: a regra é de quem a escreveu.
                    estreita = 0
                    if (linha ~ /ATTRS?\{id(Vendor|Product)\}/) estreita = 1
                    if (linha ~ /KERNELS[[:space:]]*==/)        estreita = 1
                    if (linha ~ /ENV\{ID_(VENDOR|MODEL)_ID\}/)  estreita = 1

                    if (vista == "manta"    && estreita == 1) next
                    if (vista == "estreita" && estreita == 0) next
                    if (vista != "estreita") { print arq ":" FNR ":" linha; next }

                    # Colhe todo bloco de exatamente 4 hex delimitado por
                    # não-hex. Pega `ATTRS{idVendor}=="0e6f"` e também o
                    # `KERNELS=="*045e:02ea*"` das regras de distro, que embutem
                    # vendor:produto dentro de um curinga.
                    ids = ""
                    tmp = resto
                    while (match(tmp, /[0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F]/)) {
                        tok    = substr(tmp, RSTART, 4)
                        antes  = (RSTART == 1) ? "" : substr(tmp, RSTART - 1, 1)
                        depois = substr(tmp, RSTART + 4, 1)
                        tmp    = substr(tmp, RSTART + 4)
                        if (antes ~ /[0-9a-fA-F]/ || depois ~ /[0-9a-fA-F]/) continue
                        ids = ids tolower(tok) ","
                    }
                    print arq ":" FNR ":" ids ":" linha
                }
            ' "${f}"
        done
    done
}

# A vista de ACUSA-O-CULPADO-01, intocada no nome, na assinatura e na saída:
# `arquivo:linha:conteúdo` de toda regra que abre TODO nó hidraw.
_udev_hidraw_rw_global() { _udev_hidraw_scan manta "$@"; }

# A vista nova: `arquivo:linha:ids:conteúdo` de toda regra que abre hidraw
# ESTREITANDO por aparelho. Não é acusação — é o inventário de decisões alheias
# que o restauro tem de respeitar.
_udev_hidraw_rw_estreitas() { _udev_hidraw_scan estreita "$@"; }

# Os identificadores 4-hex do aparelho por trás do nó, como `vendor,produto`
# minúsculos, lidos do uevent do sysfs:
#
#   HID_ID=0003:0000054C:00000CE6  ->  054c,0ce6
#
# Sem uevent legível devolve VAZIO — e quem chama trata "não sei" como "não
# mexo", nunca como "está livre".
_hidraw_ids_do_no() {
    local no="${1##*/}" sysroot="${2:-/sys/class/hidraw}" ue hid vend prod
    for ue in "${sysroot}/${no}/device/uevent" "${sysroot}/${no}/uevent"; do
        [[ -r "${ue}" ]] || continue
        hid="$(sed -n 's/^HID_ID=//p' "${ue}" 2>/dev/null | head -n1)"
        [[ -n "${hid}" ]] || continue
        prod="${hid##*:}"
        vend="${hid%:*}"; vend="${vend##*:}"
        [[ ${#vend} -ge 4 ]] && vend="${vend: -4}"
        [[ ${#prod} -ge 4 ]] && prod="${prod: -4}"
        printf '%s,%s' "${vend,,}" "${prod,,}"
        return 0
    done
    return 0
}

# O CRITÉRIO DE "HÁ SINTOMA", num lugar só — RESTAURO-SO-COM-SINTOMA-01.
#
# É esta função que o CHECK consulta para decidir se OFERECE o conserto, e é a
# mesma que a CURA consulta para decidir em que tocar. Um cano só, porque dois
# critérios com o mesmo nome divergem (RECEITA-ERRADA-01) e a tela passa a
# prometer o que a cura não faz.
#
# Imprime uma linha por nó ABERTO A OUTROS (os fechados não são sintoma nenhum):
#
#   alvo <nó> <modo>                 -> nenhuma regra udev explica: restaurar VALE
#   pulo <nó> manta    <arq:linha>   -> uma regra abre TODO hidraw
#   pulo <nó> estreita <arq:linha>   -> uma regra abre ESTE aparelho, de propósito
#   pulo <nó> incerta  <arq:linha>   -> abre hidraw estreitando por chave que não
#                                       sei avaliar, ou o nó não tem ids legíveis
#
# Por que os três `pulo` são recusa, e não preguiça — as DUAS metades importam:
#
#   1. ATROPELO: quem escreveu a regra escolheu abrir aquilo. Um projeto de
#      gamepad reescrevendo permissão de aparelho alheio é invasão de
#      configuração, mesmo com a intenção certa;
#   2. INUTILIDADE: a regra continua lá. No próximo evento de udev (add/change)
#      ela reabre o nó, e o conserto nem dura até o replug.
#
# Uma das duas já bastaria para não agir. As duas juntas fazem do `pulo` a única
# resposta honesta — e é por isso que o texto diz as duas.
_hidraw_alvos_do_restauro() {
    local devdir="${1:-/dev}" sysroot="${2:-/sys/class/hidraw}"
    [[ $# -gt 0 ]] && shift
    [[ $# -gt 0 ]] && shift
    local dirs=("$@")
    local mantas estreitas h mode ids linha end idlista casou incerta id
    mantas="$(_udev_hidraw_rw_global ${dirs[@]+"${dirs[@]}"})"
    estreitas="$(_udev_hidraw_rw_estreitas ${dirs[@]+"${dirs[@]}"})"
    for h in "${devdir}"/hidraw*; do
        [[ -e "${h}" ]] || continue
        mode="$(stat -c '%a' "${h}" 2>/dev/null || echo '?')"
        # Mesmo teste do check_perms_soft: último octeto != 0 = algum bit para
        # "outros". 4 (leitura) já basta — é a leitura que vaza a tecla.
        [[ "${mode}" =~ ^[0-7]*[1-7]$ ]] || continue
        if [[ -n "${mantas}" ]]; then
            printf 'pulo %s manta %s\n' "${h}" \
                   "$(printf '%s\n' "${mantas}" | head -n1 | cut -d: -f1,2)"
            continue
        fi
        ids="$(_hidraw_ids_do_no "${h}" "${sysroot}")"
        casou=""; incerta=""
        while IFS= read -r linha; do
            [[ -n "${linha}" ]] || continue
            end="$(printf '%s' "${linha}" | cut -d: -f1,2)"
            idlista="$(printf '%s' "${linha}" | cut -d: -f3)"
            if [[ -z "${idlista}" || -z "${ids}" ]]; then
                [[ -n "${incerta}" ]] || incerta="incerta ${end}"
                continue
            fi
            for id in ${ids//,/ }; do
                [[ -n "${id}" ]] || continue
                case ",${idlista}" in
                    *",${id},"*) casou="estreita ${end}" ;;
                esac
            done
            [[ -n "${casou}" ]] && break
        done <<< "${estreitas}"
        if [[ -n "${casou}" ]]; then
            printf 'pulo %s %s\n' "${h}" "${casou}"
        elif [[ -n "${incerta}" ]]; then
            printf 'pulo %s %s\n' "${h}" "${incerta}"
        else
            printf 'alvo %s %s\n' "${h}" "${mode}"
        fi
    done
}

# O que o nó hidraw É, em palavra humana — para o aviso poder dizer o que está
# aberto em vez de só o caminho. Sem udevadm, devolve vazio (e o aviso degrada
# para o nome do nó, que é melhor que nada).
_hidraw_classe_humana() {
    local no="${1##*/}" sys="${2:-/sys/class/hidraw}/${1##*/}/device" nome="" props="" classe=""
    command -v udevadm >/dev/null 2>&1 || return 0
    [[ -d "${sys}" ]] || return 0
    nome="$(udevadm info -q property -p "${sys}" 2>/dev/null \
            | sed -n 's/^HID_NAME=//p' | head -n1)"
    local i
    for i in "${sys}"/input/input*; do
        [[ -d "${i}" ]] || continue
        props+="$(udevadm info -q property -p "${i}" 2>/dev/null \
                  | grep -E '^ID_INPUT_(KEYBOARD|MOUSE)=1' || true)"$'\n'
    done
    [[ "${props}" == *ID_INPUT_KEYBOARD=1* ]] && classe="teclado"
    if [[ "${props}" == *ID_INPUT_MOUSE=1* ]]; then
        classe="${classe:+${classe}+}mouse"
    fi
    printf '%s' "${classe:+${classe} }${nome:-${no}}"
}

# ACUSA-O-CULPADO-01: UM aviso por CAUSA, não um por nó. Uma linha de regra
# produziu quatro avisos idênticos em 06/08 — quatro vezes a mesma notícia, e
# nenhuma vez o endereço.
#
# O grau continua [WARN] DE PROPÓSITO, e isso foi decidido, não esquecido: só o
# `fail` alimenta o `FAILS` que é o código de saída do doctor. Fazer a
# configuração de um programa de TERCEIRO reprovar o portão de saúde do Hefesto
# seria dizer "estou doente" por algo que não é nosso, e empurrar quem usa a
# desinstalar o vizinho para o nosso relatório ficar verde. A gravidade vai no
# TEXTO, que é onde ela sempre deveria ter estado.
check_perms_soft() {
    local devdir="${1:-/dev}" sysroot="${2:-/sys/class/hidraw}"
    [[ $# -gt 0 ]] && shift
    [[ $# -gt 0 ]] && shift
    local dirs=("$@")
    local h mode abertos=() classes="" causas="" plano="" tipo no campo3 campo4
    local alvos=() pulo_no=() pulo_motivo=() pulo_end=()
    for h in "${devdir}"/hidraw*; do
        [[ -e "$h" ]] || continue
        mode="$(stat -c '%a' "$h" 2>/dev/null || echo '?')"
        # Último octeto != 0 = algum bit para "outros". 4 (leitura) já basta:
        # hidraw entrega os relatórios de entrada CRUS, em paralelo ao evdev —
        # quem lê o nó do receptor do teclado lê o que está sendo digitado.
        [[ "${mode}" =~ ^[0-7]*[1-7]$ ]] || continue
        abertos+=("${h}")
        classes+="  ${h} (${mode}): $(_hidraw_classe_humana "${h}" "${sysroot}")"$'\n'
    done
    [[ ${#abertos[@]} -eq 0 ]] && return 0
    causas="$(_udev_hidraw_rw_global ${dirs[@]+"${dirs[@]}"})"
    # O MESMO cano que a cura usa. Se o check calculasse por conta própria, a
    # tela ofereceria o que a cura recusaria — foi exatamente esse o defeito da
    # RECEITA-ERRADA-01, e é o único jeito de ele não voltar.
    plano="$(_hidraw_alvos_do_restauro "${devdir}" "${sysroot}" ${dirs[@]+"${dirs[@]}"})"
    while read -r tipo no campo3 campo4; do
        case "${tipo}" in
            alvo) alvos+=("${no}") ;;
            pulo) pulo_no+=("${no}"); pulo_motivo+=("${campo3}"); pulo_end+=("${campo4}") ;;
        esac
    done <<< "${plano}"
    if [[ -n "${causas}" ]]; then
        warn "${#abertos[@]} nó(s) hidraw abertos a qualquer usuário local — QUALQUER processo, sem privilégio, lê o que esses aparelhos reportam"
    elif [[ ${#alvos[@]} -gt 0 ]]; then
        warn "${#abertos[@]} nó(s) hidraw abertos a qualquer usuário local, e NENHUMA regra udev explica — aí sim, ajuste manual é hipótese (esperado é 0660+uaccess)"
    else
        # RESTAURO-SO-COM-SINTOMA-01, nota datada de 07/08/2026: até aqui esta
        # linha era a de cima, e ela AFIRMAVA "NENHUMA regra udev explica" sempre
        # que a varredura de manta voltava vazia. Isso é falso quando a regra
        # estreita por aparelho — que é justamente o caso que a varredura de
        # manta se recusa a acusar, por decisão medida de ACUSA-O-CULPADO-01.
        # CONTROLE POSITIVO vivo nesta máquina em 07/08:
        # `/usr/lib/udev/rules.d/71-pdp-controllers.rules:8` abre um controle PDP
        # com MODE="0666" estreitando por `ATTRS{idVendor}=="0e6f"`. Com esse
        # controle no cabo, o doctor dizia "ninguém explica" sobre um nó que a
        # distribuição abriu de propósito.
        warn "${#abertos[@]} nó(s) hidraw abertos a qualquer usuário local, e uma regra udev ESTREITADA por aparelho explica cada um — é decisão de quem escreveu a regra, não defeito do Hefesto"
    fi
    printf '%s' "${classes}"
    if [[ -n "${causas}" ]]; then
        info "  CAUSA (regra udev que abre TODO hidraw, sem estreitar por aparelho):"
        printf '%s\n' "${causas}" | while IFS= read -r linha; do
            [[ -n "${linha}" ]] && info "    ${linha}"
        done
        info "  este arquivo NÃO é do Hefesto — a decisão de mantê-lo é de quem o instalou."
        # AFIRMACAO-SO-NO-ESTADO-DELA-01 (06/08/2026, achado de verificação
        # adversarial): esta linha afirmava, sem condição, que "os aparelhos do
        # Hefesto não são afetados". É verdade só quando o culpado está numerado
        # ABAIXO das nossas regras — que é o estado desta bancada (culpado em 60,
        # nós em 70+). É FALSA em três estados plausíveis, e um deles é o mais
        # provável de todos: a receita de internet mais copiada para hidraw é
        # `99-hidraw-permissions.rules`, que roda DEPOIS de nós e vence. Os
        # outros dois: `MODE:=` (atribuição final, que ninguém desfaz) e a
        # máquina sem as nossas regras instaladas — que é justamente quando se
        # roda o doctor.
        #
        # Então a frase passa a ser MEDIDA em vez de afirmada: só sai quando o
        # menor número de regra nossa é maior que o do culpado, e nenhum culpado
        # usa `:=`.
        # `causas` vem como "arquivo:linha:conteúdo", uma por linha.
        _rules_nossas="$(ls /etc/udev/rules.d/7*-ps5-controller.rules 2>/dev/null | head -1)"
        _culpado_tardio=0
        while IFS= read -r _entrada; do
            [[ -z "${_entrada}" ]] && continue
            _arq="${_entrada%%:*}"
            _num="$(basename "${_arq}" | sed -n 's/^\([0-9]\{1,3\}\).*/\1/p')"
            if [[ -n "${_num}" ]] && [[ "${_num}" -ge 70 ]]; then
                _culpado_tardio=1
            fi
            case "${_entrada}" in
                *MODE\ :=*|*MODE:=*) _culpado_tardio=1 ;;
            esac
        done <<< "${causas}"
        if [[ -z "${_rules_nossas}" ]]; then
            info "  as regras do Hefesto NÃO estão instaladas aqui — então nada devolve esses nós ao esperado; $(conselho_de_instalacao "" "/usr/share/hefesto-dualsense4unix/scripts/install-host-udev.sh")."
        elif [[ "${_culpado_tardio}" -eq 1 ]]; then
            info "  ATENÇÃO: a regra acima roda DEPOIS das do Hefesto (ou usa 'MODE:='), então ela vence — os nós dos controles também ficam abertos."
        else
            info "  os aparelhos do Hefesto não são afetados: a regra deles roda depois e os devolve a 0660+uaccess."
        fi
    fi
    # A OFERTA — decisão dela de 07/08/2026, resposta 16 do painel: o restauro
    # mora no doctor e só aparece quando há sintoma. O diagnóstico NÃO age: ele
    # diz que o conserto existe, o que ele vai fazer antes de fazer, e o que ele
    # não resolve. Diagnóstico que conserta sozinho é o oposto de diagnóstico.
    if [[ ${#alvos[@]} -gt 0 ]]; then
        info "  o conserto EXISTE e não roda sozinho: scripts/doctor.sh --restaurar-hidraw-uaccess"
        info "  o que ele VAI fazer, e nada além disso: tirar o bit de OUTROS de ${#alvos[@]} nó(s) — ${alvos[*]}"
        info "  o que ele NÃO faz: não cria regra udev, não escreve em /etc, não concede acesso a ninguém e não toca em nó que alguma regra explique."
        info "  o que ele NÃO resolve: ele não IMPEDE o nó de reabrir. Se o nó voltar a abrir depois, existe regra que este diagnóstico não lê (ENV{...}, GOTO, ou programa fora do udev) — e aí o conserto não dura."
    elif [[ ${#pulo_no[@]} -gt 0 ]]; then
        # RECEITA-ERRADA-01: citar o comando para dizer que ele NÃO serve é
        # honestidade; mandar rodá-lo é que era o defeito.
        info "  o --restaurar-hidraw-uaccess NÃO resolve este caso, e por isso ele não é oferecido aqui:"
        local i
        for i in "${!pulo_no[@]}"; do
            case "${pulo_motivo[$i]}" in
                manta)
                    info "    ${pulo_no[$i]}: a regra ${pulo_end[$i]} abre TODO hidraw — fechar agora desfaria o que esse arquivo manda de propósito, e o nó reabriria no próximo evento de udev"
                    ;;
                estreita)
                    info "    ${pulo_no[$i]}: a regra ${pulo_end[$i]} abre ESTE aparelho, estreitando por ele — a decisão é de quem escreveu a regra, e o nó reabriria no próximo evento de udev"
                    ;;
                *)
                    info "    ${pulo_no[$i]}: a regra ${pulo_end[$i]} abre hidraw estreitando por chave que não sei avaliar — não mexo no que não consigo provar que está órfão"
                    ;;
            esac
        done
    fi
}

# A CURA de RESTAURO-SO-COM-SINTOMA-01 — decisão dela, 07/08/2026, resposta 16
# do painel: *"o `--restaurar-hidraw-uaccess`: só no `doctor`, quando houver
# sintoma"*.
#
# POR QUE NÃO ENTRA NO INSTALL, na palavra dela: o install roda SEMPRE, e
# reescreveria permissão que outro programa pôs de propósito. O caso concreto
# desta casa é o OpenRGB (ACUSA-O-CULPADO-01). Pelo mesmo motivo isto NÃO entra
# no `--fix`: o `--fix` é o laço que roda tudo de uma vez, e roda ANTES dos
# checks — agiria sem sintoma nenhum. Há teste que cobra as duas ausências.
#
# O QUE ELE FAZ, por inteiro: `chmod o=` nos nós que o critério aprovou. Só
# isso. Não instala regra, não escreve em /etc, não concede acesso a ninguém.
#
# Por que o mecanismo é `chmod o=` e não `chmod 0660` nem `setfacl`:
#
#   - `chmod o=` tira SÓ o bit de outros: mexe na entrada `other::` e não toca
#     no `mask::` nem nas entradas nomeadas. `chmod 0660` escreveria a classe de
#     GRUPO, que num nó com ACL é a MÁSCARA — e o efeito medido não é fechar, é
#     ABRIR. MEDIDO nesta bancada em 07/08/2026, num nó com
#     `user:nobody:rwx` sob `mask::r--`:
#
#         chmod 0660  ->  mask::rw-   e nobody sai de #effective:r-- para rw-
#         chmod o=    ->  mask::r--   intacta, nobody continua em r--
#
#     Ou seja: o `chmod 0660` CONCEDE, no meio de uma operação que se chama
#     restauro, uma escrita que alguém tinha mascarado de propósito. GRAU:
#     MEDIDO (o teste `test_a_cura_nao_alarga_a_mascara_da_acl` reprova com a
#     troca feita — e a primeira versão dele NÃO reprovava, porque olhava um nó
#     cuja máscara já era `rw-`: nesse nó os dois comandos dão no mesmo);
#   - CONCEDER acesso não é RESTAURAR. Um `setfacl` nosso num nó alheio daria à
#     sessão acesso que ela não tinha — que é precisamente o que a casa recusou
#     por escrito (2026-08-06-RECOMENDACAO-A-ELA, "o que o Hefesto NÃO vai
#     fazer"): projeto de gamepad não legisla a política de segurança da máquina
#     inteira. Quem CONCEDE o uaccess aos nós do Hefesto é a regra udev — o
#     `./install.sh` e o `scripts/doctor.sh --fix`, que a reaplicam.
#
# O nome da opção é o DELA (resposta 16) e não foi trocado; a metade "uaccess"
# do nome descreve o estado a que os nós do Hefesto voltam, não uma concessão
# que este comando faça.
restaurar_hidraw_uaccess() {
    local devdir="${1:-/dev}" sysroot="${2:-/sys/class/hidraw}"
    [[ $# -gt 0 ]] && shift
    [[ $# -gt 0 ]] && shift
    local dirs=("$@")
    local plano tipo no campo3 campo4 i alvo modo depois
    local alvos=() modos=() pulo_no=() pulo_motivo=() pulo_end=()

    # AGIR CALADO É O QUE NÃO PODE ACONTECER. O `--quiet` existe para o
    # diagnóstico caber numa linha de log; aqui ele apagaria justamente o texto
    # que diz o que vai ser feito ANTES de ser feito. Neste modo ele não vale.
    QUIET=0

    plano="$(_hidraw_alvos_do_restauro "${devdir}" "${sysroot}" ${dirs[@]+"${dirs[@]}"})"
    while read -r tipo no campo3 campo4; do
        case "${tipo}" in
            alvo) alvos+=("${no}"); modos+=("${campo3}") ;;
            pulo) pulo_no+=("${no}"); pulo_motivo+=("${campo3}"); pulo_end+=("${campo4}") ;;
        esac
    done <<< "${plano}"

    if [[ ${#alvos[@]} -eq 0 ]]; then
        if [[ ${#pulo_no[@]} -eq 0 ]]; then
            pass "nenhum nó hidraw aberto a outros — não há o que restaurar (é este o estado esperado)"
            return 0
        fi
        info "não vou tocar em nada, e o motivo é este — em cada caso, mexer seria ao mesmo tempo atropelo e inútil:"
        for i in "${!pulo_no[@]}"; do
            case "${pulo_motivo[$i]}" in
                manta)
                    info "  ${pulo_no[$i]}: a regra ${pulo_end[$i]} abre TODO hidraw — fechar agora desfaria o que esse arquivo manda de propósito, e o nó reabriria no próximo evento de udev"
                    ;;
                estreita)
                    info "  ${pulo_no[$i]}: a regra ${pulo_end[$i]} abre ESTE aparelho, estreitando por ele — a decisão é de quem escreveu a regra, e o nó reabriria no próximo evento de udev"
                    ;;
                *)
                    info "  ${pulo_no[$i]}: a regra ${pulo_end[$i]} abre hidraw estreitando por chave que não sei avaliar — não mexo no que não consigo provar que está órfão"
                    ;;
            esac
        done
        info "se a permissão desse arquivo estiver errada, o conserto é no arquivo, não no nó: edite a regra e rode 'sudo udevadm control --reload-rules'."
        return 0
    fi

    # O TEXTO ANTES DA AÇÃO (RECEITA-ERRADA-01): quem lê tem de saber o que vai
    # acontecer enquanto ainda dá para desistir.
    info "vou tirar o bit de OUTROS destes ${#alvos[@]} nó(s), e nada além disso:"
    for i in "${!alvos[@]}"; do
        info "  ${alvos[$i]}: ${modos[$i]} -> ${modos[$i]%?}0   ($(_hidraw_classe_humana "${alvos[$i]}" "${sysroot}"))"
    done
    info "nenhuma regra udev é criada, nada é escrito em /etc, e nenhum acesso é concedido a ninguém."
    info "o que isto NÃO resolve: não IMPEDE o nó de reabrir. Se ele voltar a abrir, existe regra que este diagnóstico não lê (ENV{...}, GOTO, ou programa fora do udev) — e aí o conserto não dura."
    info "quem CONCEDE o uaccess aos nós do Hefesto é a regra udev, não este comando: $(conselho_de_instalacao "" "/usr/share/hefesto-dualsense4unix/scripts/install-host-udev.sh"), ou scripts/doctor.sh --fix."

    for i in "${!alvos[@]}"; do
        alvo="${alvos[$i]}"
        # Sem sudo primeiro: quem já pode (root, ou dono do nó) não gasta
        # elevação, e a suíte exercita a cura DE VERDADE sem privilégio nenhum.
        if ! chmod o= "${alvo}" 2>/dev/null; then
            if command -v sudo >/dev/null 2>&1; then
                sudo chmod o= "${alvo}" 2>/dev/null || true
            fi
        fi
        depois="$(stat -c '%a' "${alvo}" 2>/dev/null || echo '?')"
        modo="${modos[$i]}"
        if [[ "${depois}" =~ ^[0-7]*[1-7]$ ]]; then
            fail "${alvo} continua aberto a outros (${modo} -> ${depois}) — o chmod não pegou; confira quem é o dono do nó (ls -l ${alvo})"
        else
            pass "${alvo} restaurado (${modo} -> ${depois})"
        fi
    done
}

# 8BIT-03: assinatura de morte por Bluetooth do 8BitDo SN30 Pro (firmware
# clone) em modo Switch — o hid-nintendo desiste do controle e o input morre
# com o link BT ainda de pé. PROVADO ao vivo (2026-07-16, journal desta
# máquina) que o gate tem de ser a CASCATA, nunca a linha isolada:
#   - morte real (0005:057E:2009.0014, 13:23:47->13:24:00): dezenas de
#     "timeout waiting for input report" culminando em
#     "joycon_enforce_subcmd_rate: exceeded max attempts";
#   - NÃO-terminal medido (.0008 às 12:38:46: 3x exceeded com UM timeout;
#     o controle viveu mais ~8 min): "exceeded" isolado NÃO pode disparar.
# O hefesto está fora da cadeia causal (o daemon só abre DualSense — filtro
# Sony 054c — e é incapaz de tocar um device 057e); a morte aconteceu até SEM
# Steam rodando, então "feche o Steam" não é cura. A coabitação Steam×hidraw
# NUNCA vira warning aqui: o Steam segura o hidraw de TODO controle
# suportado, inclusive dos DualSense saudáveis.
#
# Função PURA e testável: lê linhas do journal do kernel no stdin e imprime
# "instância N" (uma por linha, N = timeouts acumulados até o último
# "exceeded max attempts" qualificado) só para instâncias hid com a cascata:
# >= $1 timeouts (default 10) acumulados ANTES de um "exceeded" na MESMA
# instância. Journal limpo ou só linhas isoladas => saída vazia.
_hid_nintendo_cascade_scan() {
    local min="${1:-10}"
    sed -nE \
        -e 's/^.*([0-9A-Fa-f]{4}:[0-9A-Fa-f]{4}:[0-9A-Fa-f]{4}\.[0-9A-Fa-f]{4}).*timeout waiting for input report.*$/\1 timeout/p' \
        -e 's/^.*([0-9A-Fa-f]{4}:[0-9A-Fa-f]{4}:[0-9A-Fa-f]{4}\.[0-9A-Fa-f]{4}).*joycon_enforce_subcmd_rate: exceeded max attempts.*$/\1 exceeded/p' \
      | awk -v min="${min}" '
            $2 == "timeout"                    { t[$1]++ }
            $2 == "exceeded" && t[$1] >= min   { casc[$1] = t[$1] }
            END { for (i in casc) printf "%s %d\n", i, casc[i] }
        ' | sort
}

# Check INFORMATIVO (warn no positivo; exit code inalterado; nada muda no
# sistema; nenhuma flag nova). Silencioso quando o boot atual não tem a
# cascata — o 8BitDo não é gerenciado pelo hefesto e um "OK" aqui só faria
# barulho. Usa `journalctl -b -k` SEM sudo (grupo adm; o dmesg cru é
# restrito por kernel.dmesg_restrict=1) — mesmo padrão dos outros checks.
check_hid_nintendo_bt_cascade() {
    command -v journalctl >/dev/null 2>&1 || return 0
    local hits
    hits="$(journalctl -b -k --no-pager 2>/dev/null | _hid_nintendo_cascade_scan)"
    [[ -z "${hits}" ]] && return 0
    local inst n
    while read -r inst n; do
        [[ -z "${inst}" ]] && continue
        warn "o driver desistiu do controle (instância ${inst}, neste boot): ${n}x 'timeout waiting for input report' culminando em 'joycon_enforce_subcmd_rate: exceeded max attempts' — por Bluetooth o firmware 8BitDo em modo Switch engasga com o hid-nintendo"
    done <<<"${hits}"
    info "a configuração provadamente estável é cabo em modo Switch; X-input por cabo vira Xbox 360 real (sem gyro); X-input por Bluetooth é experimento"
    info "não é o hefesto: o daemon só abre DualSense (filtro Sony 054c) e é incapaz de tocar um device Nintendo (057e)"
    info "guia: docs/usage/troubleshooting-8bitdo.md"
}

# ---------------------------------------------------------------------------
# Onda T — patch DKMS do hid-nintendo (probe BT resiliente + module params).
# Desenho: docs/process/estudos/2026-07-20-desenho-onda-t-patch-dkms.md.
# ---------------------------------------------------------------------------
# Nomes fixos (mesmos do assets/dkms/hid-nintendo/dkms.conf) — mudar de
# versão exige atualizar os dois lados.
readonly HEFESTO_DKMS_HID_NINTENDO_PKG="hefesto-hid-nintendo"
readonly HEFESTO_DKMS_HID_NINTENDO_VER="1.0.0"

# T-2/PKG-1 (auditoria 21/07): kernel contra o qual os patches T e W foram
# escritos/testados. Num upgrade de kernel em que o .c ainda COMPILE, o DKMS de
# safra antiga mascara para sempre o in-tree mais novo (fixes/devices novos) e o
# doctor daria pass.
readonly HEFESTO_DKMS_KERNEL_TESTED="7.0.11-76070011-generic"

# A LISTA INTEIRA, LIDA DA BASELINE — 01/09/2026, e a constante acima deixou de
# ser a resposta sozinha.
#
# O QUE ELE DIZIA E ERA FALSO: com o `rtw88-usb` revalidado para o
# 7.1.5-76070105 no mesmo dia, o doctor continuava comparando com o
# `KERNEL_TESTED` (o primeiro) e avisava *"kernel atual != kernel testado (…) o
# módulo do hefesto pode estar MASCARANDO um in-tree mais novo"* — sobre um
# módulo medido contra ESTE kernel. Pior que o alarme: o conselho era `sudo dkms
# remove`, isto é, arrancar uma cura válida.
#
# É A FORMA QUE ESTA CASA JÁ NOMEOU: a régua DIGITAVA o que devia LER. Agora ela
# lê `KERNELS_VALIDADOS` do `patch/BASELINE`, que é o dono do fato — e o dono é
# o mesmo que o `dkms.conf` usa no `BUILD_EXCLUSIVE_KERNEL`.
#
# O `KERNEL_TESTED` fica como piso: numa árvore instalada sem os assets (pacote
# que não leva `patch/`), a leitura devolve vazio e o comportamento é o de antes.
_dkms_kernels_validados() {
    local baseline lista=""
    for baseline in \
        "${ROOT_DIR}/assets/dkms/rtw88-usb/patch/BASELINE" \
        "/usr/share/hefesto-dualsense4unix/dkms/rtw88-usb/patch/BASELINE" \
    ; do
        [[ -r "${baseline}" ]] || continue
        lista="$(sed -n 's/^KERNELS_VALIDADOS=//p' "${baseline}" | head -1)"
        [[ -n "${lista}" ]] && break
    done
    printf '%s\n' "${lista}"
}

# Guard idempotente do aviso de Secure Boot (PKG-1): as duas seções DKMS
# chamam o helper, mas o aviso sai UMA vez por execução do doctor.
_DKMS_SB_WARNED=0

# T-2: WARN (não fail) quando o kernel atual difere do KERNEL_TESTED — o
# módulo patchado de safra antiga pode estar mascarando um in-tree mais novo.
_check_dkms_kernel_drift() {
    local kver validados build
    kver="$(uname -r)"
    [[ "${kver}" == "${HEFESTO_DKMS_KERNEL_TESTED}" ]] && return

    # `7.1.5-76070105-generic` -> `7.1.5-76070105`: a BASELINE lista o BUILD, e
    # o sufixo de sabor (-generic, -lowlatency) não muda ABI nenhuma.
    validados="$(_dkms_kernels_validados)"
    for build in ${validados}; do
        if [[ "${kver%-*}" == "${build}" ]]; then
            pass "kernel atual (${kver}) está entre os kernels validados na BASELINE do DKMS"
            return
        fi
    done

    warn "kernel atual (${kver}) não está entre os kernels validados dos patches DKMS (${validados:-${HEFESTO_DKMS_KERNEL_TESTED}}) — se o build passou, o módulo do hefesto pode estar MASCARANDO um in-tree mais novo (fixes/suporte a devices); confira o rebase do BASELINE antes de confiar na cura, ou 'sudo dkms remove' para voltar ao in-tree"
}

# PKG-1: com Secure Boot enforcing e MOK não enrolado, o load do .ko de
# updates/dkms FALHA e NÃO há fallback automático ao in-tree (modules.dep
# aponta um caminho só) — a máquina ficaria sem hid-nintendo E/OU WiFi no
# boot seguinte. Só avisa se mokutil existe, SB está ON e há .ko do hefesto.
_check_dkms_secureboot() {
    [[ "${_DKMS_SB_WARNED}" -eq 1 ]] && return
    command -v mokutil >/dev/null 2>&1 || return
    mokutil --sb-state 2>/dev/null | grep -qi 'SecureBoot enabled' || return
    local kver; kver="$(uname -r)"
    if compgen -G "/lib/modules/${kver}/updates/dkms/*.ko*" >/dev/null 2>&1; then
        _DKMS_SB_WARNED=1
        warn "Secure Boot ATIVO + módulos DKMS em updates/dkms — se a chave MOK do DKMS não estiver enrolada, o kernel RECUSA o .ko no boot e NÃO cai no in-tree (máquina sem hid-nintendo/WiFi): enrole a chave (sudo mokutil --import /var/lib/dkms/mok.pub) ou assine os módulos; nvidia-DKMS funcionando é bom sinal de que já está resolvido"
    fi
}

# Onda T (assinatura complementar à cascata de check_hid_nintendo_bt_cascade
# acima): "exceeded max attempts" DENSO mas SEM a cascata de timeouts que o
# gate `_hid_nintendo_cascade_scan` exige (>=10) aponta para OUTRA coisa —
# jitter/contenda de rádio (BT degradado mas NÃO morto), não a queda
# terminal. Função PURA (mesma leitura de journal, stdin → stdout): gate
# PRÓPRIO (exceeded >= $1, default 5, E timeouts < exceeded na MESMA
# instância hid). Journal limpo ou só a cascata terminal => saída vazia.
_hid_nintendo_dense_exceeded_scan() {
    local min="${1:-5}"
    sed -nE \
        -e 's/^.*([0-9A-Fa-f]{4}:[0-9A-Fa-f]{4}:[0-9A-Fa-f]{4}\.[0-9A-Fa-f]{4}).*timeout waiting for input report.*$/\1 timeout/p' \
        -e 's/^.*([0-9A-Fa-f]{4}:[0-9A-Fa-f]{4}:[0-9A-Fa-f]{4}\.[0-9A-Fa-f]{4}).*joycon_enforce_subcmd_rate: exceeded max attempts.*$/\1 exceeded/p' \
      | awk -v min="${min}" '
            $2 == "timeout"  { t[$1]++ }
            $2 == "exceeded" { e[$1]++ }
            END {
                for (i in e) {
                    to = (i in t ? t[i] : 0)
                    if (e[i] >= min && to < e[i]) printf "%s %d %d\n", i, e[i], to
                }
            }
        ' | sort
}

# Assinaturas do estudo de premissas (LER: docs/process/estudos/2026-07-20-
# estudo-premissas-onda-t-hid-nintendo.md, premissa 7) que HOJE não têm check
# dedicado: a morte por PROBE (o driver falha ANTES de registrar o device —
# "exceeded max attempts" nem entra na cadeia, então check_hid_nintendo_bt_
# cascade não vê nada) e o "exceeded" denso sem cascata (acima). Usa
# `_TRANSPORT=kernel` — NUNCA `journalctl -k` sozinho para checks novos (a
# armadilha "-k implica -b" documentada no sprint T0 já confundiu um
# diagnóstico desta onda); `-b` aqui é explícito e proposital (histórico
# deste boot, mesmo escopo do check_hid_nintendo_bt_cascade acima).
_check_hid_nintendo_probe_death_signature() {
    command -v journalctl >/dev/null 2>&1 || return 0
    local jlog info_fail probe_fail retry_hits
    jlog="$(journalctl -b _TRANSPORT=kernel --no-pager 2>/dev/null)"
    [[ -z "${jlog}" ]] && return 0
    info_fail="$(printf '%s\n' "${jlog}" | grep -ciE 'Failed to get joycon info; ret=-[0-9]+' || true)"
    probe_fail="$(printf '%s\n' "${jlog}" | grep -ciE 'probe - fail = -[0-9]+' || true)"
    retry_hits="$(printf '%s\n' "${jlog}" | grep -ciE 'init over bluetooth failed.*retrying' || true)"
    info_fail="${info_fail:-0}"; probe_fail="${probe_fail:-0}"; retry_hits="${retry_hits:-0}"
    if [[ "${info_fail}" -gt 0 && "${probe_fail}" -gt 0 ]]; then
        warn "morte por PROBE do hid-nintendo neste boot: ${info_fail}x 'Failed to get joycon info' + ${probe_fail}x 'probe - fail' — o driver falhou ANTES de registrar o device e o in-tree NÃO re-proba sozinho; sem o patch DKMS, replug/power-cycle é a única saída"
        if [[ "${retry_hits}" -gt 0 ]]; then
            info "o retry do patch DKMS está agindo (${retry_hits}x 'init over bluetooth failed; retrying') — se o probe passou depois, a cura funcionou"
        else
            info "sem sinal do retry do patch neste boot — confira acima se o módulo CARREGADO é o patchado"
        fi
    fi
}

_check_hid_nintendo_exceeded_dense_signature() {
    command -v journalctl >/dev/null 2>&1 || return 0
    local hits
    hits="$(journalctl -b _TRANSPORT=kernel --no-pager 2>/dev/null | _hid_nintendo_dense_exceeded_scan)"
    [[ -z "${hits}" ]] && return 0
    local inst n_exc n_to
    while read -r inst n_exc n_to; do
        [[ -z "${inst}" ]] && continue
        warn "interferência/contenda BT no controle Nintendo/8BitDo (instância ${inst}, neste boot): ${n_exc}x 'exceeded max attempts' com só ${n_to}x timeout — rádio degradado SEM a cascata de morte terminal (gate >=10 timeouts do check acima); o link não caiu, mas está sob contenda"
    done <<<"${hits}"
}

# Check principal da Onda T: o patch DKMS está instalado/ativo? Read-only —
# NUNCA chama modprobe/rmmod/dkms install aqui (isso é do install.sh).
check_hefesto_hid_nintendo_dkms() {
    if ! command -v dkms >/dev/null 2>&1; then
        info "dkms ausente — patch DKMS do hid-nintendo (Onda T) não instalado (opcional: sudo apt install dkms$(so_no_checkout "— ou ./install.sh, que o instala por default"))"
        return
    fi
    local kver status
    kver="$(uname -r)"
    status="$(dkms status "${HEFESTO_DKMS_HID_NINTENDO_PKG}/${HEFESTO_DKMS_HID_NINTENDO_VER}" 2>/dev/null)"
    if [[ -z "${status}" ]]; then
        info "patch DKMS do hid-nintendo (Onda T) não instalado — driver in-tree em uso (cura de raiz do probe BT: $(conselho_de_instalacao "" "/usr/share/hefesto-dualsense4unix/scripts/install-host-udev.sh")$(so_no_checkout "— opt-out: --no-dkms"))"
        return
    fi
    if printf '%s\n' "${status}" | grep -qF ", ${kver}"; then
        pass "DKMS ${HEFESTO_DKMS_HID_NINTENDO_PKG}/${HEFESTO_DKMS_HID_NINTENDO_VER} construído p/ o kernel atual (${kver})"
        _check_dkms_kernel_drift
    else
        warn "DKMS ${HEFESTO_DKMS_HID_NINTENDO_PKG} instalado mas NÃO p/ o kernel atual (${kver}) — rebase pendente, in-tree em uso; status: ${status}"
    fi
    _check_dkms_secureboot

    # Próximo carregamento: NUNCA usar srcversion (armadilha do estudo — não
    # distingue in-tree de DKMS); modinfo -F filename aponta o caminho real.
    local modpath
    modpath="$(modinfo -F filename hid_nintendo 2>/dev/null)"
    if [[ "${modpath}" == */updates/dkms/* ]]; then
        info "próximo carregamento resolve para o módulo patchado (${modpath})"
    elif [[ -n "${modpath}" ]]; then
        info "próximo carregamento ainda resolve para o in-tree (${modpath}) — confira /etc/depmod.d ou rode: sudo depmod -a"
    fi

    # Módulo CARREGADO agora: só o patchado expõe parameters/ (0 params no
    # in-tree — confirmado byte a byte no estudo de premissas).
    if [[ -d /sys/module/hid_nintendo/parameters ]]; then
        local retries skiptx regleds
        retries="$(cat /sys/module/hid_nintendo/parameters/bt_probe_retries 2>/dev/null || echo '?')"
        skiptx="$(cat /sys/module/hid_nintendo/parameters/skip_tx_on_rate_exceeded 2>/dev/null || echo '?')"
        regleds="$(cat /sys/module/hid_nintendo/parameters/register_leds_on_set_failure 2>/dev/null || echo '?')"
        pass "módulo hid_nintendo CARREGADO é o patchado (bt_probe_retries=${retries}, skip_tx_on_rate_exceeded=${skiptx}, register_leds_on_set_failure=${regleds}; esperados 3/Y/Y via /etc/modprobe.d/hefesto-hid-nintendo.conf — regleds '?' = módulo anterior ao fix 21/07, reinstale)"
    elif [[ -d /sys/module/hid_nintendo ]]; then
        warn "módulo hid_nintendo carregado é o in-tree (sem parameters/) — o patchado vale SÓ no próximo boot (replug NÃO troca módulo carregado: re-liga no driver residente; substituir módulo em uso derrubaria Pro Controller/8BitDo conectados)"
    else
        info "hid_nintendo não está carregado agora (sem controle Nintendo/8BitDo plugado?)"
    fi

    _check_hid_nintendo_probe_death_signature
    _check_hid_nintendo_exceeded_dense_signature
}

# ---------------------------------------------------------------------------
# Onda W — patch DKMS do rtw88_usb (device-gone + queue de port reset — cura
# do fantasma USB do dongle WiFi). Desenho:
# docs/process/estudos/2026-07-20-desenho-onda-w-patch-dkms.md.
# ---------------------------------------------------------------------------
# Nomes fixos (mesmos do assets/dkms/rtw88-usb/dkms.conf) — mudar de versão
# exige atualizar os dois lados.
readonly HEFESTO_DKMS_RTW88_PKG="hefesto-rtw88-usb"
readonly HEFESTO_DKMS_RTW88_VER="1.0.0"

# Check principal da Onda W: o patch DKMS está instalado/ativo? Read-only —
# NUNCA chama modprobe/rmmod/dkms install aqui (isso é do install.sh).
check_hefesto_rtw88_usb_dkms() {
    if ! command -v dkms >/dev/null 2>&1; then
        info "dkms ausente — patch DKMS do rtw88_usb (Onda W) não instalado (opcional: sudo apt install dkms$(so_no_checkout "— ou ./install.sh, que o instala por default"))"
        return
    fi
    local kver status
    kver="$(uname -r)"
    status="$(dkms status "${HEFESTO_DKMS_RTW88_PKG}/${HEFESTO_DKMS_RTW88_VER}" 2>/dev/null)"
    if [[ -z "${status}" ]]; then
        info "patch DKMS do rtw88_usb (Onda W) não instalado — driver in-tree em uso (cura de raiz do fantasma USB do dongle WiFi: $(conselho_de_instalacao "" "/usr/share/hefesto-dualsense4unix/scripts/install-host-udev.sh")$(so_no_checkout "— opt-out: --no-dkms"))"
        return
    fi
    if printf '%s\n' "${status}" | grep -qF ", ${kver}"; then
        pass "DKMS ${HEFESTO_DKMS_RTW88_PKG}/${HEFESTO_DKMS_RTW88_VER} construído p/ o kernel atual (${kver})"
        _check_dkms_kernel_drift
    else
        warn "DKMS ${HEFESTO_DKMS_RTW88_PKG} instalado mas NÃO p/ o kernel atual (${kver}) — rebase pendente OU kernel fora do pino BUILD_EXCLUSIVE_KERNEL (7.0.y é EOL, série nova precisa de rebase do BASELINE), in-tree em uso; status: ${status}"
    fi
    _check_dkms_secureboot

    # Próximo carregamento: NUNCA usar srcversion (mesma armadilha do estudo
    # da Onda T — não distingue in-tree de DKMS); modinfo -F filename aponta
    # o caminho real.
    local modpath
    modpath="$(modinfo -F filename rtw88_usb 2>/dev/null)"
    if [[ "${modpath}" == */updates/dkms/* ]]; then
        info "próximo carregamento resolve para o módulo patchado (${modpath})"
    elif [[ -n "${modpath}" ]]; then
        info "próximo carregamento ainda resolve para o in-tree (${modpath}) — confira /etc/depmod.d ou rode: sudo depmod -a"
    fi

    # Módulo CARREGADO agora: diferente do hid_nintendo (0 params no
    # in-tree), o rtw88_usb in-tree JÁ expõe parameters/ (switch_usb_mode) —
    # o marcador exclusivo do patchado é o PARÂMETRO NOVO hang_reset.
    if [[ -e /sys/module/rtw88_usb/parameters/hang_reset ]]; then
        local hang
        hang="$(cat /sys/module/rtw88_usb/parameters/hang_reset 2>/dev/null || echo '?')"
        pass "módulo rtw88_usb CARREGADO é o patchado (hang_reset=${hang}; Y = usb_queue_reset_device ativo em device-gone, N = só detecção/silenciamento)"
    elif [[ -d /sys/module/rtw88_usb ]]; then
        warn "módulo rtw88_usb carregado é o in-tree (sem hang_reset) — o patchado vale SÓ no próximo boot (replug NÃO troca módulo carregado: o dongle re-liga no driver residente; substituir módulo em uso derrubaria o WiFi)"
    else
        info "rtw88_usb não está carregado agora (dongle WiFi desconectado?)"
    fi
}

# Assinatura do fantasma USB (W1, medido 20/07: 13h de device retido após um
# port-status-change perdido no xHCI). Read-only, três ângulos independentes
# — cada um vira warn com a cura; journal do BOOT ATUAL só (mesma disciplina
# do check_usb_dropout acima).
check_usb_fantasma() {
    local d driver idv idp key any=0
    local -A _seen=()

    # (a) DUPLICATA: mais de um device em /sys/bus/usb/devices/* com o mesmo
    # idVendor:idProduct AINDA vinculado ao driver rtw88_usb — a assinatura
    # real do incidente (fantasma + device vivo re-enumerado, mesmos IDs, um
    # único dongle físico).
    for d in /sys/bus/usb/devices/*; do
        [[ -r "$d/idVendor" && -r "$d/idProduct" ]] || continue
        driver="$(basename "$(readlink -f "$d/driver" 2>/dev/null || true)" 2>/dev/null)"
        [[ "${driver}" == "rtw88_usb" ]] || continue
        idv="$(cat "$d/idVendor" 2>/dev/null)"
        idp="$(cat "$d/idProduct" 2>/dev/null)"
        key="${idv}:${idp}"
        if [[ -n "${_seen[$key]:-}" ]]; then
            any=1
            warn "device USB fantasma: $(basename "$d") E ${_seen[$key]} vinculados ao MESMO driver rtw88_usb com idVendor:idProduct=${key} — só existe um dongle físico; um 'USB disconnect' não foi processado. Cura: sudo sh -c 'echo ${_seen[$key]} > /sys/bus/usb/drivers/rtw88_usb/unbind' (confira o endereço exato) ou reboot"
        else
            _seen["${key}"]="$(basename "$d")"
        fi
    done

    # (b) journal do boot com colisão de rename do udev — o dano concreto do
    # fantasma (a interface nova não consegue assumir o nome wlx... que o
    # device fantasma ainda segura). NÃO restrito a _TRANSPORT=kernel: quem
    # renomeia é o systemd-udevd (userspace).
    if command -v journalctl >/dev/null 2>&1; then
        local rename_n
        rename_n="$(journalctl -b --no-pager 2>/dev/null \
            | grep -ciE 'wlx[0-9a-f]+.*(File exists|Arquivo existe)' || true)"
        rename_n="${rename_n:-0}"
        if [[ "${rename_n}" -gt 0 ]]; then
            any=1
            warn "colisão de rename do udev neste boot: ${rename_n}x 'wlx... File exists/Arquivo existe' — sintoma do fantasma (a interface nova não consegue assumir o nome que o device fantasma ainda segura)"
        fi
    fi

    # (c) device com driver rtw88_usb em sysfs SEM filho net/ (nunca virou
    # interface de rede, ou a perdeu) + -71 recente no kernel log deste
    # device — o padrão do firmware wedged/disconnect perdido medido 20/07.
    if command -v journalctl >/dev/null 2>&1; then
        local jlog
        jlog="$(journalctl -b -k --no-pager 2>/dev/null)"
        for d in /sys/bus/usb/devices/*; do
            [[ -r "$d/idVendor" ]] || continue
            driver="$(basename "$(readlink -f "$d/driver" 2>/dev/null || true)" 2>/dev/null)"
            [[ "${driver}" == "rtw88_usb" ]] || continue
            if find "$d" -maxdepth 2 -type d -name net 2>/dev/null | grep -q .; then
                continue
            fi
            local devname eproto_n
            devname="$(basename "$d")"
            eproto_n="$(printf '%s\n' "${jlog}" | grep -c "usb ${devname}:.*error -71" || true)"
            eproto_n="${eproto_n:-0}"
            if [[ "${eproto_n}" -gt 0 ]]; then
                any=1
                warn "device USB ${devname} (driver rtw88_usb) SEM interface de rede (net/) e com ${eproto_n}x '-71' neste boot — assinatura de device-gone (firmware wedged ou disconnect perdido). Cura: sudo sh -c 'echo ${devname} > /sys/bus/usb/drivers/rtw88_usb/unbind' ou reboot"
            fi
        done
    fi

    [[ "${any}" -eq 0 ]] && pass "sem sinal de device USB fantasma (rtw88_usb) neste boot"
}

# Powersave EFETIVO do WiFi (W2 — vilão ATIVO é o LPS RASO via mac80211,
# ligado hoje por wifi.powersave=3 do NetworkManager; disable_lps_deep é
# NO-OP em USB, não é medido/julgado aqui). Leitura SÓ de arquivo (conf.d) —
# NUNCA invoca nmcli/rfkill (regra da casa: doctor é read-only e não toca
# NetworkManager). Sem julgamento até scripts/medir_w2_lps.sh medir A/B.
check_wifi_powersave() {
    local -a files=(/etc/NetworkManager/NetworkManager.conf)
    if [[ -d /etc/NetworkManager/conf.d ]]; then
        local f
        while IFS= read -r -d '' f; do
            files+=("${f}")
        done < <(find /etc/NetworkManager/conf.d -maxdepth 1 -name '*.conf' -print0 2>/dev/null | sort -z)
    fi
    local val="" src="" f hit
    for f in "${files[@]}"; do
        [[ -r "${f}" ]] || continue
        hit="$(sed -n 's/^[[:space:]]*wifi\.powersave[[:space:]]*=[[:space:]]*\([0-9]\+\).*/\1/p' "${f}" 2>/dev/null | tail -1)"
        [[ -n "${hit}" ]] && { val="${hit}"; src="${f}"; }
    done
    if [[ -z "${val}" ]]; then
        info "NetworkManager sem wifi.powersave configurado (default do driver/firmware vale) — não medido ainda: scripts/medir_w2_lps.sh"
    elif [[ "${val}" == "3" ]]; then
        info "wifi.powersave=3 (LIGA o power save do firmware) via ${src} — histórico de instabilidade em dongles Realtek USB (rtw88); meça antes de mudar: scripts/medir_w2_lps.sh"
    elif [[ "${val}" == "2" && "${src}" == "/etc/NetworkManager/conf.d/hefesto-wifi-powersave.conf" ]]; then
        pass "wifi.powersave=2 (desliga) via o conf.d do hefesto — opt-in aplicado após medição W2 confirmar ganho"
    else
        info "wifi.powersave=${val} via ${src}"
    fi

    if command -v journalctl >/dev/null 2>&1; then
        local n
        n="$(journalctl -b -k --no-pager 2>/dev/null | grep -ciE 'failed to leave lps state' || true)"
        n="${n:-0}"
        if [[ "${n}" -gt 0 ]]; then
            warn "${n}x 'failed to leave lps state' neste boot — assinatura do LPS raso (mac80211 emperrando ao sair do power save); reforça o histórico de instabilidade citado acima"
        fi
    fi
}

# O VIGIA DO DONGLE WI-FI USB (O-QUE-E-DO-HEFESTO-SAI-DO-ZSH-01, 23/09/2026).
# Morava no self-heal do zsh dela; agora é do install, e esta é a pergunta
# "está de pé?". Quem responde "há Wi-Fi USB?" e "divide hub com o Bluetooth?"
# é o próprio `wifi_usb.sh` — o dono único da pergunta; o doctor só lê a
# resposta. Sem root o `wpa_cli` recusa (o socket do wpa_supplicant é de root),
# então o estado do scan de fundo NÃO se lê daqui: o `--status` diz isso na
# própria linha, e o que o doctor confere é o que se lê sem privilégio — o
# timer, o dispatcher (root e 755, senão o NetworkManager o recusa) e o que o
# vigia disse no journal deste boot.
#
# Ganchos de teste: `HEFESTO_WIFI_INSTALADO` (o script instalado) e
# `HEFESTO_WIFI_DISPATCHER` (o dispatcher) — o `wifi_usb.sh` lê os dele
# (`HEFESTO_WIFI_SYSFS`…) pelo ambiente herdado.
check_wifi_usb() {
    local instalado="${HEFESTO_WIFI_INSTALADO:-/usr/local/lib/hefesto-dualsense4unix/wifi_usb.sh}"
    local dispatcher="${HEFESTO_WIFI_DISPATCHER:-/etc/NetworkManager/dispatcher.d/90-hefesto-wifi-usb}"
    local script="" lista="" linha st_timer="" dono_modo="" diario="" n_reset=0 problema=0
    local ultimo_estado="" onde_o_dispatcher="sem NetworkManager nesta máquina, sem dispatcher"
    # Do checkout quando há; senão o instalado. O doctor viaja em pacote sem o
    # script, e aí a pergunta fica sem quem responda — diz isso em vez de
    # adivinhar.
    if [[ -x "${ROOT_DIR}/scripts/wifi_usb.sh" ]]; then
        script="${ROOT_DIR}/scripts/wifi_usb.sh"
    elif [[ -x "${instalado}" ]]; then
        script="${instalado}"
    fi
    if [[ -z "${script}" ]]; then
        info "vigia do Wi-Fi USB: o wifi_usb.sh não está nesta instalação — não sei dizer se há dongle Wi-Fi USB"
        return 0
    fi
    lista="$(bash "${script}" --lista 2>/dev/null || true)"
    if command -v systemctl >/dev/null 2>&1; then
        st_timer="$(systemctl is-active hefesto-wifi-usb-vigia.timer 2>/dev/null || true)"
    fi
    if [[ -z "${lista}" ]]; then
        if [[ "${st_timer}" == "active" ]]; then
            pass "nenhum Wi-Fi USB agora — o vigia está armado e não faz nada"
        else
            info "nenhum Wi-Fi USB agora (o vigia do dongle não está ativo; só faz falta a quem tiver um)"
        fi
        return 0
    fi
    lista="$(printf '%s' "${lista}" | tr '\n' ' ' | sed 's/ $//')"
    if [[ ! -x "${instalado}" ]]; then
        # O PACOTE NÃO O LIGA, por decisão (P-15 da INSTALL-E-UNINSTALL-DO-
        # RADIO-01, a razão está no `install-host-udev.sh`): mandar quem
        # instalou por pacote «atualizar» seria mandar repetir o que não
        # entrega. O gesto que liga é o instalador do repositório.
        if esta_instalacao_e_um_checkout; then
            warn "há Wi-Fi USB (${lista}) e o vigia do dongle não está instalado — o scan de fundo pode derrubá-lo de 5 em 5 min e um travamento mudo fica sem cura: $(conselho_de_instalacao)"
        else
            warn "há Wi-Fi USB (${lista}) e o vigia do dongle não está ligado — o scan de fundo pode derrubá-lo de 5 em 5 min e um travamento mudo fica sem cura. O pacote não o liga (é um serviço de root que reinicia porta USB); quem o liga é o instalador do repositório do Hefesto, rodado de um clone dele, em qualquer formato"
        fi
        problema=1
    elif [[ "${st_timer}" != "active" ]]; then
        warn "o vigia do Wi-Fi USB está instalado e o timer não está ativo (${st_timer:-?}) — ligue: sudo systemctl enable --now hefesto-wifi-usb-vigia.timer"
        problema=1
    fi
    if [[ -d "$(dirname "$(dirname "${dispatcher}")")" ]]; then
        onde_o_dispatcher="dispatcher do NetworkManager no lugar"
        if [[ ! -e "${dispatcher}" ]]; then
            if [[ -x "${instalado}" ]]; then
                warn "o dispatcher ${dispatcher} não existe — cada associação nova nasce com o scan de fundo ligado até o próximo tique do vigia"
                problema=1
            fi
        else
            dono_modo="$(stat -c '%U %a' "${dispatcher}" 2>/dev/null || true)"
            if [[ "${dono_modo}" != "root 755" ]]; then
                warn "o dispatcher ${dispatcher} está '${dono_modo:-?}' e o NetworkManager só roda script de root, 755 — ele é ignorado. Reinstale: $(conselho_de_instalacao)"
                problema=1
            fi
        fi
    fi
    # A linha do --status: porta, velocidade e o hub. Dividir hub com um
    # adaptador Bluetooth é a pergunta que é do rádio dos controles.
    while IFS= read -r linha; do
        [[ -n "${linha}" ]] || continue
        if [[ "${linha}" == *"AVISO: mesmo hub que o Bluetooth"* ]]; then
            warn "Wi-Fi USB e Bluetooth no mesmo hub: ${linha} — afaste o dongle dos adaptadores (outra porta, outro hub)"
            problema=1
        else
            info "wifi: ${linha}"
        fi
    done < <(bash "${script}" --status 2>/dev/null || true)
    # O que o vigia disse neste boot. `-t` é o SyslogIdentifier da unit e o
    # `logger` do dispatcher; legível por quem está no grupo adm ou
    # systemd-journal.
    #
    # O «parei» vale pelo que veio DEPOIS dele: o vigia o repete a cada tique
    # enquanto o rádio segue mudo, e para quando o roteador volta («o roteador
    # voltou a responder», «curado depois de…» — o dongle que ela tirou e pôs de
    # volta). Um «parei» de manhã seguido de uma cura à tarde não é defeito de
    # agora; quem decide é a ÚLTIMA dessas linhas, não a existência de uma.
    if command -v journalctl >/dev/null 2>&1; then
        diario="$(journalctl -b -q --no-pager -t hefesto-wifi-usb 2>/dev/null || true)"
        n_reset="$(printf '%s\n' "${diario}" | grep -c 'reiniciada (' || true)"
        ultimo_estado="$(printf '%s\n' "${diario}" \
            | grep -E 'parei\. Tire e ponha o dongle|o roteador voltou a responder|curado depois de' \
            | tail -n 1 || true)"
        if [[ "${ultimo_estado}" == *"parei. Tire e ponha o dongle"* ]]; then
            warn "o vigia do Wi-Fi USB reiniciou a porta 3 vezes sem cura e PAROU neste boot — tire e ponha o dongle (de preferência noutra porta)"
            problema=1
        elif [[ "${n_reset:-0}" -gt 0 && -n "${ultimo_estado}" ]]; then
            info "o vigia reiniciou a porta do dongle ${n_reset}x neste boot, e o roteador voltou a responder depois"
        elif [[ "${n_reset:-0}" -gt 0 ]]; then
            info "o vigia reiniciou a porta do dongle ${n_reset}x neste boot"
        fi
    fi
    [[ "${problema}" -eq 0 ]] && pass "vigia do Wi-Fi USB de pé (${lista}): timer ativo, ${onde_o_dispatcher}"
    return 0
}

# FEAT-DOCTOR-USB-DROPOUT-DIAGNOSTIC-01.
# Resolve o controlador PCI (xHCI) onde um device USB (sysfs path) está pendurado:
# o último 0000:XX:YY.Z na cadeia antes do /usbN é o controlador.
usb_pci_controller() {
    local devpath="$1" real
    real="$(readlink -f "${devpath}" 2>/dev/null || true)"
    printf '%s\n' "${real}" | grep -oE '0000:[0-9a-f]{2}:[0-9a-f]{2}\.[0-9a-f]' | tail -1
}

pci_label() {
    case "$1" in
        *0c:00.3) echo "CPU/Ryzen (0c:00.3)" ;;      # controlador USB integrado do Ryzen
        *02:00.0) echo "chipset (02:00.0)" ;;        # controlador USB do southbridge
        "")       echo "desconhecido" ;;
        *)        echo "$1" ;;
    esac
}

# Mapeia um número de bus USB para o rótulo do controlador PCI do seu root hub.
bus_to_label() {
    pci_label "$(usb_pci_controller "/sys/bus/usb/devices/usb${1}" 2>/dev/null)"
}

# Conta sintomas de dropout -71 (EPROTO) e ATRIBUI corretamente a fonte.
check_usb_dropout() {
    command -v journalctl >/dev/null 2>&1 || { info "journalctl ausente — pulo o check de dropout"; return; }

    # Localização: em qual controlador o DualSense (vendor 054c) está agora.
    local d ds_dev="" ds_pci="" ds_devname=""
    for d in /sys/bus/usb/devices/*; do
        [[ -r "$d/idVendor" ]] || continue
        [[ "$(cat "$d/idVendor" 2>/dev/null)" == "054c" ]] && ds_dev="$d"
    done
    if [[ -n "$ds_dev" ]]; then
        ds_pci="$(usb_pci_controller "$ds_dev")"
        ds_devname="$(basename "$ds_dev")"
        info "DualSense no controlador $(pci_label "$ds_pci"), Bus $(cat "$ds_dev/busnum" 2>/dev/null), power/control=$(cat "$ds_dev/power/control" 2>/dev/null)"
    else
        info "DualSense não conectado via USB agora (pode estar via Bluetooth) — pulo a localização de barramento"
    fi

    # Sintomas de -71 no boot atual (read-only).
    local lines n
    lines="$(journalctl -b -k --no-pager 2>/dev/null \
              | grep -iE 'error -71|device descriptor read/64, error|not accepting address|unable to enumerate USB device' || true)"
    n="$(printf '%s' "$lines" | grep -c . || true)"; n="${n:-0}"
    if [[ "${n}" -eq 0 ]]; then
        pass "sem dropout -71 neste boot"
        return
    fi
    warn "dropout USB: ${n} sintoma(s) -71/enum neste boot"

    # ATRIBUIÇÃO HONESTA (corrige a heurística antiga que culpava o controlador
    # do Ryzen só por o dsx estar lá): extrai QUAIS devices 'usb X-Y' geraram o
    # -71 e mapeia o bus -> controlador. O -71 de boot costuma ser OUTRO device
    # (ex: webcam no chipset), não o DualSense.
    local devs dev busnum hits dsx_hits=0 other_count=0
    devs="$(printf '%s\n' "$lines" | grep -oE 'usb [0-9]+-[0-9.]+' | awk '{print $2}' | sort -u)"
    [[ -n "$devs" ]] && info "fonte(s) do -71 neste boot:"
    for dev in $devs; do
        busnum="${dev%%-*}"
        hits="$(printf '%s\n' "$lines" | grep -c "usb ${dev}:" || true)"
        if [[ -n "$ds_devname" && "$dev" == "$ds_devname" ]]; then
            dsx_hits="$hits"
            info "  - usb ${dev} = DualSense (Bus ${busnum} = $(bus_to_label "$busnum")) -- ${hits}x"
        else
            other_count=$((other_count + 1))
            info "  - usb ${dev} = outro device (Bus ${busnum} = $(bus_to_label "$busnum")) -- ${hits}x"
        fi
    done

    if [[ "${dsx_hits:-0}" -gt 0 ]]; then
        info "o -71 ATINGE o DualSense -- storm port-independente; fix: quirk usbcore.quirks=...gn,gn (alavanca A, preserva áudio) OU regra 75 authorized=0 (alavanca B). Cheque: scripts/install_usb_quirk.sh --check"
    else
        info "o -71 deste boot NÃO é do DualSense -- provável outro device (ex: webcam). Valide o dsx abrindo a Steam com --watch-dropout."
    fi

    # O watcher de auto-recuperação por authorized-toggle saiu do projeto: a
    # auditoria do storm de 26/06 mediu que re-enumerar por software realimenta
    # o próprio storm, e a cura de raiz é o quirk acima.
    info "ver em tempo real: scripts/doctor.sh --watch-dropout"
}

# --suggest-port: diz em qual controlador USB o DualSense está. DIAGNÓSTICO
# NEUTRO -- o storm -71 é port-independente (A/B comprovado: cai em qualquer
# porta sob carga de GPU/Steam quando o snd-usb-audio enumera as 3 interfaces
# de áudio do controle). A localização do controlador NÃO é o fix; o fix é o
# quirk (alavanca A) OU a regra 75 (alavanca B). Esta função só ajuda a mapear
# topologia (ex: o dongle WiFi no mesmo controlador, que o rebind por software
# derrubaria).
suggest_port() {
    local d ds_dev=""
    for d in /sys/bus/usb/devices/*; do
        [[ -r "$d/idVendor" ]] || continue
        [[ "$(cat "$d/idVendor" 2>/dev/null)" == "054c" ]] && ds_dev="$d"
    done
    if [[ -z "$ds_dev" ]]; then
        if command -v bluetoothctl >/dev/null 2>&1 && timeout 4 bluetoothctl devices 2>/dev/null | grep -qi 'DualSense'; then
            info "DualSense via Bluetooth (sem caminho USB) -- sem snd-usb-audio, logo sem storm pelo controle"
        else
            info "DualSense não conectado via USB nem Bluetooth -- conecte para avaliar"
        fi
        return
    fi
    local ds_pci bus
    ds_pci="$(usb_pci_controller "$ds_dev")"
    bus="$(cat "$ds_dev/busnum" 2>/dev/null)"
    info "DualSense em Bus ${bus}, controlador $(pci_label "$ds_pci")"
    info "  topologia apenas (diagnóstico neutro). O storm -71 é port-independente:"
    info "  o fix é o quirk usbcore.quirks=...gn,gn (alavanca A, preserva áudio)"
    info "  OU a regra 75 authorized=0 (alavanca B). Cheque: scripts/install_usb_quirk.sh --check"
}

# Modo --watch-dropout: bloqueia até o primeiro sintoma de dropout e sai.
watch_dropout() {
    printf 'vigiando o journal do kernel por dropout -71 (Ctrl-C para sair)...\n'
    journalctl -kf -o cat --since now 2>/dev/null \
      | grep -m1 -iE 'error -71|device descriptor read/64, error|not accepting address|device not responding' \
      && printf '\n[WATCH] primeiro sinal de dropout capturado acima.\n'
}

# IRMAO-SEM-CARONA-01 (12/08/2026) — quem reaplica as regras udev depende do
# layout em que ESTE doctor está rodando, e até aqui só um dos dois existia no
# código.
#
# MEDIDO: `scripts/build_deb.sh:216` leva o `doctor.sh` para dentro do pacote
# (`/usr/share/hefesto-dualsense4unix/scripts/`), e o `ROOT_DIR` deste arquivo
# é derivado do lugar dele (:60) — no .deb, portanto,
# `${ROOT_DIR}/scripts/install_udev.sh` NÃO EXISTE: aquele laço leva cinco
# scripts, e o `install_udev.sh` não é um deles. O que o pacote leva, e leva de
# propósito para este exato serviço, é o `install-host-udev.sh` (a forma 3 do
# cabeçalho dele: "Direto de um .deb instalado"). O resultado na máquina de
# quem instalou pelo pacote era `hefesto-dualsense4unix doctor --fix` dizendo
# "falha ao reaplicar udev" — cura prometida, caminho inexistente.
#
# A escolha é por EXISTÊNCIA, não por adivinhar o layout: o checkout tem os
# dois e o `install_udev.sh` vem primeiro porque é o dono nativo (conjunto
# canônico das regras); o pacote tem só o `install-host-udev.sh`, que resolve
# as regras em `/usr/share/hefesto-dualsense4unix/udev-rules/`. Se nenhum dos
# dois estiver aqui, o recado diz qual arquivo faltou — em vez do "falha ao
# reaplicar" mudo, que não distingue script ausente de script que reprovou.
#
# Portão: a seção "irmão sem carona" de `scripts/check_packaging_parity.sh`, e
# `tests/unit/test_portao_reprova_irmao_sem_carona.py`.
_dono_das_regras_udev() {
    if [[ -f "${ROOT_DIR}/scripts/install_udev.sh" ]]; then
        printf '%s' "${ROOT_DIR}/scripts/install_udev.sh"
        return 0
    fi
    if [[ -f "${ROOT_DIR}/scripts/install-host-udev.sh" ]]; then
        printf '%s' "${ROOT_DIR}/scripts/install-host-udev.sh"
        return 0
    fi
    return 1
}

# A FILA DE NUMERAÇÃO, LIMPA DE ENDEREÇO DE FIXTURE — 18/09/2026.
#
# MEDIDO na mesa dela: quatro endereços `aa:bb:cc:00:00:0{1..4}` moravam no
# `controllers.json` desde 22/08, ocupando os postos 4 a 7 da fila e
# empurrando um DualSense REAL para o oitavo. A causa (a suíte escrevendo no
# `~/.config` real) foi fechada em 25/08 pelo lar de mentira de sessão; a
# SUJEIRA ficou, e nada a limpava: o `check_faixa_sintetica.py` acusava desde
# 24/08 e não tinha como curar.
#
# AQUI E NÃO NO PRODUTO, e a razão é medida: a primeira cura descartava a
# faixa dentro do `identity.order_entries` e foi recuada no mesmo dia — duas
# dezenas de réguas desta casa usam `aa:bb:cc` como endereço de controle de
# verdade. Expurgar no produto é regra sobre a nossa suíte, não sobre o
# aparelho. O `--fix` é onde esta casa conserta MÁQUINA, e é um gesto que a
# pessoa pede — que é o que a mensagem do portão exige: "a decisão sobre o que
# já está gravado é de quem é dono da máquina".
#
# TRÊS FUROS FECHADOS (INSTALL-UNIVERSAL, 18/09/2026), todos de máquina alheia:
#
#   1. O PYTHON. Rodava o `python3` do sistema com o erro jogado fora, e o
#      `--casa` importa `platformdirs`, que só a venv do produto garante — na
#      bancada dela ele existia por acaso (o pacote do pipx). Sem ele o script
#      morria no import e esta linha dizia "sem endereço de fixture" sem ter
#      lido o arquivo. Agora é o `_python_do_produto`, e o veredito sai da
#      primeira palavra da resposta: `OK:` passa, `LIMPO:` segue, qualquer
#      outra coisa (vazio, traceback) é AVISO com a última linha.
#   2. O DAEMON DE PÉ REGRAVAVA A FILA. O `load` põe a fila do disco na
#      memória uma vez só, e o `_save_locked` a regrava inteira quando um
#      controle chega ou muda de número — por cima do que se acabou de tirar.
#      Só quando houve limpeza, o serviço é reiniciado (`try-restart`: nada
#      acontece se ele não estiver rodando). Um daemon aberto fora do systemd
#      não é alcançável daqui, e isso é dito.
#   3. A FAIXA DE ENDEREÇO UNIVERSAL. Com o furo 2 fechado, a remoção passa a
#      ficar — e o `e_endereco_sintetico` respondia sim para `e8:47:3a`, uma
#      faixa sem o bit de administração local: espaço que a IEEE atribui a
#      fabricante. A cura é no dono (`core/faixa_sintetica.py`): só faixa de
#      endereço LOCAL é lixo por construção. Os dois furos entram juntos.
fix_fila_sem_fixture() {
    [[ -f "${ROOT_DIR}/scripts/check_faixa_sintetica.py" ]] || return 0
    local py saida fecho estado
    py="$(_python_do_produto)"
    if [[ -z "${py}" ]]; then
        warn "limpeza da fila não rodou: sem python para o check_faixa_sintetica.py"
        return
    fi
    saida="$("${py}" "${ROOT_DIR}/scripts/check_faixa_sintetica.py" --casa --limpar 2>&1)" || true
    if [[ $'\n'"${saida}" == *$'\n'"OK:"* ]]; then
        pass "fila de numeração: sem endereço de fixture"
        return
    fi
    if [[ $'\n'"${saida}" != *$'\n'"LIMPO:"* ]]; then
        fecho="${saida##*$'\n'}"
        warn "limpeza da fila não rodou: ${fecho:-o check_faixa_sintetica.py não respondeu} (python: ${py})"
        return
    fi
    pass "fila de numeração: endereços de fixture retirados"
    if ! command -v systemctl >/dev/null 2>&1; then
        [[ -S "$(runtime_socket)" ]] && warn "sem systemctl para reiniciar o daemon: ele guarda a fila antiga na memória e a regrava quando um controle chegar — feche-o e rode --fix de novo"
        return
    fi
    systemctl --user try-restart "${APP_ID}.service" >/dev/null 2>&1 || true
    estado="$(systemctl --user is-active "${APP_ID}.service" 2>/dev/null || true)"
    if [[ "${estado}" == "active" ]]; then
        pass "daemon reiniciado para ler a fila limpa (${APP_ID}.service)"
    elif [[ -S "$(runtime_socket)" ]]; then
        warn "o socket do daemon está de pé sem o ${APP_ID}.service: um daemon aberto fora do systemd guarda a fila antiga na memória e a regrava quando um controle chegar — feche-o e rode --fix de novo"
    fi
}

# HAPTICA-NATIVA-01 — o gancho UCM do DualSense no cabo (INSTALL-UNIVERSAL,
# 18/09/2026). Sai um gancho por controlador USB PRESENTE na hora; um
# controlador que chega depois (uma dock, uma placa USB) ficava sem, e o doctor
# só acusava. O roteiro é idempotente e pede sudo por dentro.
#
# O VEREDITO VEM DA RESPOSTA, não do código de saída — mesmo furo que o
# `fix_fila_sem_fixture` fechou. O roteiro sai 0 também quando NÃO grava: sem
# `ucm.conf`, com um `ucm.conf` que não lê `conf.d/`, com o /usr só de leitura
# e sem controlador que caiba no corte. Com a saída em /dev/null, o `--fix`
# dizia "[ OK ] conferido" justamente nesses quatro casos. Só a linha
# "N gancho(s) em …" prova que o gancho está no disco; sem ela, a última linha
# da resposta diz o porquê. HEFESTO_RAIZ_UCM (a mesma do
# `check_ucm_do_dualsense`) e HEFESTO_SYSFS existem para os testes.
#
# O caminho do roteiro vai POR EXTENSO na guarda e na chamada, e não numa
# variável: o portão do irmão sem carona (`check_packaging_parity.sh`) lê o
# nome literal, e o que não está escrito ele não vê.
fix_ucm_do_dualsense() {
    [[ -f "${ROOT_DIR}/scripts/install_ucm_dualsense.sh" ]] || return 0
    local saida fecho rc=0
    saida="$(bash "${ROOT_DIR}/scripts/install_ucm_dualsense.sh" \
        --raiz-ucm "${HEFESTO_RAIZ_UCM:-/usr/share/alsa/ucm2}" \
        --sysfs "${HEFESTO_SYSFS:-/sys}" 2>&1)" || rc=$?
    fecho="${saida##*$'\n'}"
    fecho="${fecho#\[ucm\] }"
    fecho="${fecho#aviso: }"
    if [[ "${rc}" -ne 0 ]]; then
        warn "install_ucm_dualsense.sh falhou (código ${rc}): ${fecho:-sem resposta} — rode: bash scripts/install_ucm_dualsense.sh"
    elif [[ $'\n'"${saida}" == *$'\n'"[ucm] "[0-9]*" gancho(s) em "* ]]; then
        pass "perfil UCM do DualSense conferido (um gancho por controlador USB)"
    else
        info "perfil UCM do DualSense não gravado: ${fecho:-o install_ucm_dualsense.sh não respondeu}"
    fi
}

# O rastro de quem disse não ao pino — 18/09/2026. O `--no-proton-pin` do
# install tira a linha do `--manter` da unidade do vigia; um install anterior a
# 18/09 deixa a mesma unidade sem ela. Sai 0 quando a unidade EXISTE e não tem
# a linha. Sem unidade não há rastro, e o `--fix` trava.
#
# UM PREDICADO SÓ, para o conselho e para o gesto: o `_gesto_da_trava_do_pino`
# mandava rodar o `--fix`, e o `fix_proton_pinado` lia o rastro e recusava — o
# conselho não curava, e a pessoa só chegava à cura no segundo salto.
_o_vigia_recusou_o_pino() {
    local unidade="${HOME}/.config/systemd/user/hefesto-steam-input-guard.service"
    [[ -f "${unidade}" ]] && ! grep -qE '^ExecStart=.*--manter' "${unidade}" 2>/dev/null
}

# O gesto que o `check_proton_pin` aconselha para a trava — 18/09/2026. Com o
# pino instalado, é o `--fix`, a não ser que o vigia tenha sido instalado sem o
# passo do pino: aí o `--fix` recusa, e o gesto é reinstalar. Sem o pino, o
# `--fix` não tem em que travar: o gesto é o do aviso de "Proton pinado
# AUSENTE", logo acima na mesma saída.
_gesto_da_trava_do_pino() {
    if [[ "${1:-0}" != "1" ]]; then
        printf '%s' "a trava espera o Proton pinado ficar instalado (ver o aviso de AUSENTE acima)"
    elif _o_vigia_recusou_o_pino; then
        printf '%s' "o vigia da Steam foi instalado sem o passo do pino (--no-proton-pin, ou um instalador anterior a 18/09/2026); para travar, $(conselho_de_instalacao)"
    else
        printf '%s' "rode: scripts/doctor.sh --fix (trava com a Steam fechada; o vigia da Steam também trava sozinho quando ela sai)"
    fi
}

# A trava do Proton pinado, pela linha que o próprio doctor aconselha — 18/09.
#
# O check dizia "Não há o que consertar" sobre o jogo fora do pino, e o `--fix`
# não tinha o que fazer por ele. Agora ele roda o MESMO passo do vigia da
# Steam, o `--manter`, e não o `--lock --todos`: o `--manter` repõe o pino do
# cache sem rede e só trava com ele instalado. O `--lock --todos` daqui, numa
# máquina sem o pino (install sem rede, ou feito antes de existir Steam),
# apontava cada jogo para uma ferramenta que não existe — e o doctor dizia
# PASS. O portão é o mesmo: com a Steam ou um jogo abertos ele ADIA (rc 3) e
# nunca fecha nada. Sem Steam nativa com `config.vdf`, o passo cala.
#
# QUEM DISSE NÃO AO PINO FICA SEM ELE. O `--no-proton-pin` do install tira a
# linha do `--manter` da unidade do vigia, e é esse o rastro que se lê aqui
# (`_o_vigia_recusou_o_pino`). Um install anterior a 18/09/2026 deixa o
# mesmo rastro, e aí o `--fix` também não trava — a frase diz os dois casos.
fix_proton_pinado() {
    local py="${ROOT_DIR}/src/hefesto_dualsense4unix/integrations/proton_pin.py"
    [[ -f "${py}" && -f "${ROOT_DIR}/assets/proton-pin.conf" ]] || return 0
    command -v python3 >/dev/null 2>&1 || return 0
    if [[ ! -f "${HOME}/.steam/steam/config/config.vdf" \
          && ! -f "${HOME}/.local/share/Steam/config/config.vdf" ]]; then
        return 0
    fi
    if _o_vigia_recusou_o_pino; then
        info "Proton pinado: o vigia da Steam desta máquina foi instalado sem o passo do pino (--no-proton-pin, ou um instalador anterior a 18/09/2026) — o --fix não trava por cima disso; para travar, $(conselho_de_instalacao)"
        return 0
    fi
    local rc=0
    python3 "${py}" --manter >/dev/null 2>&1 || rc=$?
    case "${rc}" in
        0) pass "Proton pinado conferido e jogos travados nele (--manter)" ;;
        2) warn "trava do Proton pinado ESPERA o pino: ele não está instalado e o tarball não está no cache (o --fix não baixa nada) — $(conselho_de_instalacao)" ;;
        3) warn "trava do Proton pinado ADIADA — a Steam (ou um jogo) está aberta; feche e rode de novo: scripts/doctor.sh --fix" ;;
        5) warn "o Proton pinado bateu com o SHA256 e a EXTRAÇÃO falhou — veja o espaço livre em disco e rode de novo: scripts/doctor.sh --fix" ;;
        *) warn "trava do Proton pinado falhou (rc=${rc}) — rode: python3 ${py} --manter" ;;
    esac
}

apply_fixes() {
    hdr "aplicando correções (--fix)"
    local _udev_dono=""
    _udev_dono="$(_dono_das_regras_udev || true)"
    if [[ -z "${_udev_dono}" ]]; then
        warn "nem install_udev.sh nem install-host-udev.sh estão em ${ROOT_DIR}/scripts — não reapliquei udev"
    elif command -v sudo >/dev/null 2>&1; then
        if sudo bash "${_udev_dono}" >/dev/null 2>&1; then
            pass "regras udev reaplicadas ($(basename "${_udev_dono}"))"
        else
            warn "falha ao reaplicar udev ($(basename "${_udev_dono}"))"
        fi
    else
        warn "sudo ausente — não reapliquei udev"
    fi
    # O gancho UCM do DualSense no cabo ANTES do fix do WirePlumber logo
    # abaixo, de propósito: o `--install` dele reinicia o WirePlumber, e é esse
    # restart que reabre a placa pelo gancho — outro `systemctl` aqui seria o
    # mesmo gesto duas vezes.
    fix_ucm_do_dualsense
    if bash "${ROOT_DIR}/scripts/fix_wireplumber_default_source.sh" --install >/dev/null 2>&1; then
        pass "fix de áudio do WirePlumber aplicado"
    else
        warn "fix de áudio do WirePlumber falhou"
    fi
    if [[ -x "${ROOT_DIR}/scripts/disable_steam_input.sh" ]]; then
        if bash "${ROOT_DIR}/scripts/disable_steam_input.sh" --apply >/dev/null 2>&1; then
            pass "Steam Input PSSupport desligado (todos os localconfig.vdf)"
        else
            warn "disable_steam_input.sh falhou"
        fi
    fi
    # MIC-USB-01: camadas 1 e 2 do microfone mudo. Depois do fix de áudio acima,
    # que pode reinstalar o drop-in e reiniciar o WirePlumber — o perfil da placa
    # e o mute da source precisam ser conferidos com o serviço já de pé.
    fix_mic_dualsense
    fix_proton_pinado
    fix_fila_sem_fixture
    # AUSÊNCIA DELIBERADA — RESTAURO-SO-COM-SINTOMA-01, decisão dela de
    # 07/08/2026: `restaurar_hidraw_uaccess` NÃO é chamado aqui. O `--fix` roda
    # tudo de uma vez e roda ANTES dos checks, então chamá-lo daqui seria agir
    # sem sintoma — exatamente o motivo pelo qual ela recusou pôr isto no
    # install. O restauro só existe atrás da opção própria. Há teste que cobra
    # esta ausência, porque uma linha a mais aqui a desfaz em silêncio.
}

main() {
    [[ "${WATCH_DROPOUT}" -eq 1 ]] && { watch_dropout; exit 0; }
    [[ "${SUGGEST_PORT}" -eq 1 ]] && { suggest_port; exit 0; }
    # RESTAURO-SO-COM-SINTOMA-01 (decisão dela, 07/08/2026): rota própria, pedida
    # a dedo. Ela não é alcançável por nenhum outro modo do doctor — nem pelo
    # --fix, nem pelo install.
    if [[ "${RESTAURAR_HIDRAW}" -eq 1 ]]; then
        hdr "restauro de permissão dos nós hidraw (--restaurar-hidraw-uaccess)"
        restaurar_hidraw_uaccess
        [[ "${FAILS}" -eq 0 ]]
        exit $?
    fi
    # MIC-USB-01: rota curta para quem só quer o microfone de volta agora —
    # cura as camadas 1 e 2, mostra o veredito das duas e sai. É também o que o
    # `fix_wireplumber_default_source.sh --promote-source` chama, para a cura
    # das camadas ter UM dono só e não virar dois códigos que divergem.
    if [[ "${FIX_MIC}" -eq 1 ]]; then
        hdr "microfone do DualSense (MIC-USB-01 — camadas 1 e 2)"
        fix_mic_dualsense
        check_mic_mute_persistido
        check_mic_perfil_sem_sinal
        check_default_source_monitor
        info "camada 3 (mudo no firmware do controle): hefesto-dualsense4unix mic unmute"
        [[ "${FAILS}" -eq 0 ]]
        exit $?
    fi
    [[ "${DO_FIX}" -eq 1 ]] && apply_fixes
    hdr "daemon"
    check_daemon_installed
    check_service
    check_socket
    # VERDE-MENTIROSO-01: as duas obrigatórias que o doctor não cobrava. Ficam
    # ao lado do CLI de propósito — são a mesma pergunta ("o produto consegue
    # fazer o que promete?"), e as duas reprovam por AUSÊNCIA de biblioteca, não
    # por defeito de configuração.
    check_libhidapi
    check_loader_svg
    hdr "kernel / udev"
    check_udev
    check_usb_audio_off
    check_usb_quirk
    check_usb_storm_config_conflict
    check_uinput
    check_uhid
    check_uhid_contrapressao
    check_hid_playstation
    check_hid_playstation_probe_abortado
    check_led_sysfs_gravavel
    # OQ-6: logo depois do check da 77 (nó de LED gravável) porque é a mesma
    # pergunta — "a regra desta casa chegou a valer no nó vivo?" — só que para
    # os nós de ENTRADA do touchpad e dos sensores de movimento.
    check_input_uaccess
    hdr "energia USB e rádio"
    check_usb_power_devices
    check_usb_power_hosts
    check_pcie_aspm
    check_power_saboteurs
    check_btusb_autosuspend
    check_bluez_fastconnectable
    check_bluez_justworks_repairing
    check_bt_clone_ds4
    check_bt_rfkill
    check_bt_radio
    check_bt_crc_counters
    check_kernel_watch
    check_familias_do_radio
    check_cmdline_platform
    hdr "rádio e pareamento (G2)"
    check_bluez_backport_version
    check_bluez_curas_do_backport
    check_bt_agent_service
    check_bt_resilience
    check_trava_do_radio
    check_bt_bonds_persistidos
    check_bt_connected_sem_hidraw
    check_bt_sdp_cache_envenenado
    check_bt_paired_sem_bonded
    check_bond_dobrado
    check_exame_da_mesa
    hdr "a bandeja do sistema (tray)"
    check_bandeja
    hdr "detector de janela (autoswitch / perfil-por-jogo)"
    check_window_detect
    check_perfis_inalcancaveis
    hdr "áudio (microfone)"
    check_wireplumber_source
    check_dropin_do_mic_armado
    check_default_source_monitor
    check_dualsense_sink_disabled
    check_dropin_do_alto_falante_acordado
    check_ucm_do_dualsense
    check_ancoras_da_haptica_por_radio
    check_audio_sink_muted
    check_mic_mute_persistido
    check_mic_perfil_sem_sinal
    check_mic_ganho_de_captura
    hdr "Steam Input"
    check_steam_input
    check_steam_input_allowlist
    hdr "controle no jogo (duplicação / wrapper de launch)"
    check_launch_wrapper
    check_copias_do_wrapper
    check_ultimo_device_ks
    check_vdf_poison
    check_dedup_ipc
    check_display_authority
    check_proton_pin
    hdr "broker hide-hidraw (BROKER-01 — cura de raiz do duplicado)"
    check_hidraw_broker
    hdr "giroscópio no jogo (vpad Motion)"
    check_vpad_motion
    hdr "teclado na tela (o que o L3 do controle abre)"
    check_teclado_na_tela
    hdr "controle"
    check_controller
    check_perms_soft
    check_hid_nintendo_bt_cascade
    hdr "DKMS hid-nintendo (Onda T — cura de raiz do probe BT)"
    check_hefesto_hid_nintendo_dkms
    hdr "DKMS rtw88_usb / WiFi (Onda W — fantasma USB + powersave)"
    check_hefesto_rtw88_usb_dkms
    check_usb_fantasma
    check_wifi_powersave
    check_wifi_usb
    hdr "USB / dropout"
    check_usb_dropout

    printf '\n─────────────────────────────────────────\n'
    if [[ "${FAILS}" -eq 0 ]]; then
        printf ' Diagnóstico: tudo OK (%d aviso(s))\n' "${WARNS}"
    else
        printf ' Diagnóstico: %d FALHA(s), %d aviso(s)\n' "${FAILS}" "${WARNS}"
    fi
    printf '─────────────────────────────────────────\n'
    [[ "${FAILS}" -eq 0 ]]
}

# `source scripts/doctor.sh` (testes de unidade das funções de parse, ex.
# _hid_nintendo_cascade_scan) carrega as funções SEM executar o diagnóstico;
# a execução direta segue idêntica.
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main
fi
