#!/usr/bin/env bash
# install-dev.sh — instala o Hefesto de DESENVOLVIMENTO como OUTRO app.
#
# Pedido dela, 29/08/2026: *"Vamos migrar o desenvolvimento inteiro pra outra
# pasta dev e lá vamos implementar as features e ficar validando tudo. Se
# tivermos que criar um install separado pra ele. OK. Sem problemas. Ele é
# instalado como OUTRO APP com a logo alterada em dev."*
#
# ============================================================================
# LEIA ISTO ANTES: POR QUE ESTE ARQUIVO EXISTE, E POR QUE `install.sh` NÃO SERVE
# ============================================================================
# `install.sh:192` declara `readonly APP_ID="hefesto-dualsense4unix"`. Rodá-lo
# na árvore de dev NÃO cria um app novo: SEQUESTRA o dela. Ele reescreve o
# `.desktop` dela (`install.sh:3070`) com `Exec=` apontando para a árvore de
# dev, repontua o symlink `~/.local/bin/hefesto-dualsense4unix`
# (`install.sh:3236`) — que é o binário que a unit DELA executa
# (`assets/hefesto-dualsense4unix.service:22`) — e reescreve as units
# (`install.sh:3369`). O produto que ela usa todo dia passaria a rodar código
# de desenvolvimento, sem trocar o nome de nada.
#
# Este instalador é a alternativa: tudo com `dev` NO MEIO do nome, nada em
# `/etc`, nada em `/usr`, zero `sudo`.
#
# O QUE ELE INSTALA (tudo reversível por `--desfazer`)
# ----------------------------------------------------
#   ~/.local/share/applications/hefesto-dev-dualsense4unix.desktop
#   ~/.local/share/icons/hicolor/*/apps/hefesto-dev-dualsense4unix.png
#   ~/.local/bin/hefesto-dev-dualsense4unix       -> .venv de dev
#   ~/.local/bin/hefesto-dev-dualsense4unix-gui   (lançador)
#   ~/.local/bin/hefesto-chave                    (a chave liga/desliga)
#   ~/.config/systemd/user/hefesto-dev-dualsense4unix.service
#
# A CAMADA DE MÁQUINA — `--camada-de-maquina`, e ela NÃO vem de graça
# --------------------------------------------------------------------
# Regras udev, o grupo `hefesto`, o broker hidraw, a resiliência do bluetoothd,
# a ponte privilegiada, os módulos DKMS e o que mora em `/usr/local/lib`. Essa
# camada é da MÁQUINA, não do app — e por isso ela só entra quando PEDIDA:
#
#     ./install-dev.sh --camada-de-maquina
#
# A instalação normal (sem a flag) continua não tocando em nada disso, pela
# razão de sempre: dois instaladores escrevendo por cima de
# `/etc/udev/rules.d/70-ps5-controller.rules` fariam o app de um rodar sob a
# regra do outro sem uma linha dizendo isso, e o `--desfazer` de um levaria a
# regra do outro junto. Pior: as regras 82 e 83 executam script de
# `/usr/local/lib/hefesto-dualsense4unix/` como root na borda do hotplug
# (`assets/82-nintendo-pro-nosniff.rules:96`).
#
# O QUE MUDOU EM 31/08/2026, e por que a flag nasceu: *"eu desinstalei a versão
# antiga e vamos deixar só a dev"*. Até esse dia este arquivo dizia, aqui, que
# "o app de dev DEPENDE do Hefesto estável para essa camada" — e dependia
# mesmo. Sem o estável, ninguém instalava a camada, e o app de dev parou de
# funcionar sem UM erro sequer: `/dev/uhid` nascia `crw------- root root`, o
# daemon caía para uinput calado (`vpad_degradado motivo=uhid_indisponivel`) e
# o teclado virtual não abria (`uinput_keyboard_create_failed [Errno 13]`).
# O sintoma foi o de sempre nesta casa — a AUSÊNCIA de dado.
#
# A FONTE É UMA SÓ: `scripts/lib/camada_de_maquina.sh`, sourceada por este
# arquivo e pelo `install.sh`. Este script NUNCA executa o `install.sh` —
# fazê-lo reescreveria o `.desktop`, o symlink e as units do app ESTÁVEL
# apontando para código de desenvolvimento, que é o sequestro descrito acima.
#
# Convivência, quando os dois apps existem: o broker foi desenhado para ela —
# `broker/hidraw_broker.py:507-518` diz, literal, que "dois daemons em takeover
# convivem", cada um com sua lease. Um broker, dois daemons.
#
# ELE SE RECUSA A RODAR SE FOR COLIDIR, e diz o que colide. Ver `conferir()`.
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ID="hefesto-dev-dualsense4unix"
VARIANTE="dev"

BIN="${HOME}/.local/bin"
APLICATIVOS="${HOME}/.local/share/applications"
HICOLOR="${HOME}/.local/share/icons/hicolor"
UNITS="${HOME}/.config/systemd/user"

DESKTOP="${APLICATIVOS}/${APP_ID}.desktop"
UNIT="${UNITS}/${APP_ID}.service"
TAMANHOS="16 22 24 32 48 64 96 128 192 256 512"

# Os nomes do app ESTÁVEL — nenhum deles pode ser alvo de escrita aqui.
ESTAVEL_DESKTOP="${APLICATIVOS}/hefesto-dualsense4unix.desktop"
ESTAVEL_BIN="${BIN}/hefesto-dualsense4unix"
ESTAVEL_BIN_GUI="${BIN}/hefesto-dualsense4unix-gui"
ESTAVEL_UNIT="${UNITS}/hefesto-dualsense4unix.service"

SIM=0
SO_CONFERIR=0
DESFAZER=0
CAMADA=0
for arg in "$@"; do
    case "$arg" in
        --yes|-y)     SIM=1 ;;
        --conferir)   SO_CONFERIR=1 ;;
        --desfazer)   DESFAZER=1 ;;
        --camada-de-maquina) CAMADA=1 ;;
        -h|--help)
            sed -n '2,50p' "$0" | sed 's/^# \{0,1\}//'
            exit 0 ;;
        *) echo "argumento desconhecido: $arg" >&2; exit 2 ;;
    esac
done

vermelho() { printf '\033[31m%s\033[0m\n' "$*"; }
verde()    { printf '\033[32m%s\033[0m\n' "$*"; }
passo()    { printf '\n\033[1m%s\033[0m\n' "$*"; }

# ============================================================================
# A RECUSA — roda ANTES de escrever o primeiro byte
# ============================================================================
conferir() {
    local problemas=0

    passo "conferindo se algo vai colidir"

    # 1. Nenhum alvo pode ser um arquivo do estável. Esta é a checagem que
    #    impede o sequestro descrito no cabeçalho.
    local alvo
    for alvo in "$DESKTOP" "$UNIT" "${BIN}/${APP_ID}" "${BIN}/${APP_ID}-gui"; do
        case "$alvo" in
            "$ESTAVEL_DESKTOP"|"$ESTAVEL_UNIT"|"$ESTAVEL_BIN"|"$ESTAVEL_BIN_GUI")
                vermelho "  RECUSO: '$alvo' é do Hefesto ESTÁVEL."
                problemas=1 ;;
        esac
    done
    # E por forma, não só por lista: um nome sem `-dev-` no meio é, por
    # construção, um nome que pode alcançar o estável.
    if [[ "$APP_ID" != *"-dev-"* ]]; then
        vermelho "  RECUSO: APP_ID='${APP_ID}' não tem 'dev' no MEIO do nome."
        vermelho "          O 'dev' no FIM faria o pgrep -f da GUI dela"
        vermelho "          (app/main.py) matar este app — casamento por substring."
        problemas=1
    fi

    # 2. A árvore tem de ser a de dev, não a dela.
    if [[ "$RAIZ" == "/mnt/Apate/Desenvolvimento/hefesto-dualsense4unix" ]]; then
        vermelho "  RECUSO: esta é a ÁRVORE ESTÁVEL dela (branch dev)."
        vermelho "          O app de desenvolvimento sai da árvore -dev."
        problemas=1
    fi

    # 3. Precisa de .venv próprio — senão o app de dev rodaria o código dela.
    if [[ ! -x "${RAIZ}/.venv/bin/python" ]]; then
        vermelho "  RECUSO: ${RAIZ}/.venv não existe."
        vermelho "          Sem venv próprio, o binário de dev apontaria para o"
        vermelho "          .venv do estável e os dois rodariam o MESMO código."
        vermelho "          Rode antes: ${RAIZ}/scripts/dev_bootstrap.sh"
        problemas=1
    fi

    # 4. A logo de dev tem de existir e tem de RENDERIZAR no librsvg — que é o
    #    motor do pipeline de ícone. Medido em 29/08: a logo nova usa
    #    `transform-box`/`transform-origin`, que o librsvg IGNORA, e o anel e o
    #    martelo somem do PNG. Um ícone mutilado na dock é justamente o oposto
    #    do que ela pediu, então isto é recusa, não aviso.
    if [[ ! -f "${RAIZ}/assets/hefesto-dev-logo.svg" ]]; then
        vermelho "  RECUSO: assets/hefesto-dev-logo.svg ausente."
        problemas=1
    elif grep -q 'transform-origin\|transform-box' "${RAIZ}/assets/hefesto-dev-logo.svg" \
         && [[ ! -f "${RAIZ}/scripts/assar_transforms_svg.py" ]]; then
        # A RECUSA VIROU CONDICIONAL em 30/08/2026. Ela dizia "asse os
        # transforms antes" — e ela mesma decidiu o contrário: *"o nosso install
        # sempre deve corrigir ele"*. Com o assador presente, não há o que
        # recusar; sem ele, a recusa continua valendo, porque o ícone sairia
        # mutilado e ninguém saberia por quê.
        vermelho "  RECUSO: a logo tem transform-origin/transform-box e o assador"
        vermelho "          (scripts/assar_transforms_svg.py) não está aqui."
        problemas=1
    fi

    command -v rsvg-convert >/dev/null 2>&1 || {
        vermelho "  RECUSO: rsvg-convert ausente (sudo apt install librsvg2-bin)"
        problemas=1; }

    # 5. O WM_CLASS que o código publica tem de casar o StartupWMClass do
    #    .desktop. São dois arquivos que ninguém obriga a concordar — e foi por
    #    não haver régua assim que duas janelas do produto nasceram com app_id
    #    errado. Aqui a régua roda ANTES de instalar.
    local wm_do_codigo wm_do_desktop
    wm_do_codigo="$("${RAIZ}/.venv/bin/python" -c \
        'import sys; sys.path.insert(0,"'"${RAIZ}"'/src");
from hefesto_dualsense4unix.utils import identidade
print(identidade.DEV.wm_class)' 2>/dev/null || echo "")"
    wm_do_desktop="$(sed -n 's/^StartupWMClass=//p' \
        "${RAIZ}/packaging/${APP_ID}.desktop" 2>/dev/null || echo "")"
    if [[ -z "$wm_do_codigo" || "$wm_do_codigo" != "$wm_do_desktop" ]]; then
        vermelho "  RECUSO: o WM_CLASS do código e o do .desktop divergem."
        vermelho "          código  : '${wm_do_codigo}'  (utils/identidade.py:DEV)"
        vermelho "          .desktop: '${wm_do_desktop}'  (packaging/${APP_ID}.desktop)"
        vermelho "          Com eles diferentes a dock não acha o ícone."
        problemas=1
    else
        verde "  WM_CLASS do código == StartupWMClass do .desktop ('${wm_do_codigo}')"
    fi

    # 6. Avisos — não impedem, mas ela tem de saber ANTES.
    # 31/08/2026: este aviso mandava esperar pelo estável, e a espera virou
    # beco quando ela o desinstalou. Agora ele aponta a saída — e só aparece
    # se a camada de fato NÃO estiver na máquina. A régua é o grupo `hefesto`,
    # que só existe se `scripts/install_udev.sh` já correu: é o dono de
    # /dev/uhid e /dev/uinput, e sem ele o daemon cai para uinput em silêncio.
    if ! getent group hefesto >/dev/null 2>&1; then
        printf '  aviso: a CAMADA DE MÁQUINA não está instalada (não há grupo `hefesto`).\n'
        printf '         Sem ela o daemon não abre /dev/uhid nem /dev/uinput e\n'
        printf '         degrada CALADO — vira aviso no log, não erro na tela.\n'
        printf '         Instale depois deste install:\n'
        printf '             ./install-dev.sh --camada-de-maquina\n'
        printf '         A interface (./interface) funciona mesmo assim: ela só LÊ.\n'
    fi
    if systemctl --user is-active --quiet hefesto-dualsense4unix.service 2>/dev/null; then
        printf '  aviso: o daemon ESTÁVEL está no ar agora.\n'
        printf '         Dois daemons disputam o aparelho (dois vpads, entrada\n'
        printf '         dobrada). Antes de usar o de dev:\n'
        printf '             hefesto-chave estavel off\n'
    fi

    if [[ $problemas -eq 1 ]]; then
        vermelho ""
        vermelho "NADA FOI ESCRITO. Conserte o que está acima e rode de novo."
        return 1
    fi
    verde "  nenhuma colisão."
    return 0
}

# ============================================================================
# DESFAZER
# ============================================================================
if [[ $DESFAZER -eq 1 ]]; then
    passo "desfazendo a instalação de desenvolvimento"
    systemctl --user disable --now "${APP_ID}.service" >/dev/null 2>&1 || true
    systemctl --user unmask "${APP_ID}.service" >/dev/null 2>&1 || true
    rm -f "$UNIT"
    systemctl --user daemon-reload >/dev/null 2>&1 || true
    rm -f "$DESKTOP" "${BIN}/${APP_ID}" "${BIN}/${APP_ID}-gui" "${BIN}/hefesto-chave"
    for t in ${TAMANHOS}; do rm -f "${HICOLOR}/${t}x${t}/apps/${APP_ID}.png"; done
    rm -f "${HICOLOR}/symbolic/apps/${APP_ID}-symbolic.svg"
    rm -f "${HOME}/.local/share/pixmaps/${APP_ID}.png"
    command -v gtk-update-icon-cache >/dev/null 2>&1 &&
        gtk-update-icon-cache -q -f "$HICOLOR" 2>/dev/null || true
    command -v update-desktop-database >/dev/null 2>&1 &&
        update-desktop-database -q "$APLICATIVOS" 2>/dev/null || true
    verde "pronto. O Hefesto estável não foi tocado."
    printf 'A config de dev (~/.config/%s) NÃO foi apagada — é dado, e apagar\n' "$APP_ID"
    printf 'dado não é trabalho de desinstalador. Tire à mão se quiser.\n'
    exit 0
fi

# ============================================================================
# A CAMADA DE MÁQUINA — `--camada-de-maquina` (31/08/2026)
# ============================================================================
# Ela desinstalou o Hefesto estável e ficou só com o de desenvolvimento:
# *"eu desinstalei a versão antiga e vamos deixar só a dev"*. Com isso caiu a
# premissa em que este arquivo nasceu — a de que o estável provia a camada de
# máquina —, e o app de dev parou de funcionar sem dar um erro sequer: o
# sintoma foi a AUSÊNCIA de dado. `/dev/uhid` nascia `crw------- root root`,
# ninguém o abria, e o daemon caía para uinput em silêncio
# (`vpad_degradado motivo=uhid_indisponivel`); `/dev/uinput` sem o grupo
# `hefesto` derrubava o teclado virtual (`uinput_keyboard_create_failed
# [Errno 13]`). Nada disso era erro — era aviso, no meio do log.
#
# ESTE MODO NÃO INSTALA APP NENHUM. Não escreve `.desktop`, symlink, unit de
# usuário nem ícone: só a camada da MÁQUINA, a mesma que o `install.sh`
# instala, lida da MESMA fonte (`scripts/lib/camada_de_maquina.sh`). Por isso
# ele roda ANTES do `conferir()` — não há alvo de app para colidir.
#
# E ele NÃO executa o `install.sh`. Sourcear a lib é o que permite isso, e a
# regra do `CLAUDE.md` ("nunca rode `install.sh` na árvore de dev") continua
# valendo, literal: rodá-lo aqui reescreveria o `.desktop`, o symlink e as
# units do app ESTÁVEL apontando para código de desenvolvimento.
if [[ $CAMADA -eq 1 ]]; then
    passo "instalando a CAMADA DE MÁQUINA a partir de ${RAIZ}"
    printf 'Isto muda o SISTEMA, não o app: regras udev em /etc/udev/rules.d,\n'
    printf 'o grupo `hefesto`, scripts em /usr/local/lib, units de sistema e\n'
    printf 'os módulos DKMS. Nenhum .desktop, symlink ou unit de usuário é\n'
    printf 'tocado — nem os do app estável, nem os do de dev.\n'

    if [[ $SIM -eq 0 ]]; then
        printf '\nSeguir? [s/N] '
        read -r resposta
        [[ "$resposta" =~ ^[sS] ]] || { echo "nada feito."; exit 0; }
    fi

    # A credencial UMA vez. Sem isto cada função pediria a senha por conta
    # própria e as que testam `sudo -n true` desistiriam caladas — o mesmo
    # defeito que o `acquire_sudo` do `install.sh` existe para matar
    # (BUG-INSTALL-SUDO-NONINTERACTIVE-01).
    if ! sudo -v; then
        vermelho "RECUSO: sem sudo não há camada de máquina — ela mora em /etc e /usr/local."
        exit 1
    fi

    # A lib espera `ROOT_DIR` (o léxico do `install.sh`); aqui a raiz chama `RAIZ`.
    ROOT_DIR="$RAIZ"
    export ROOT_DIR
    # shellcheck source=scripts/lib/camada_de_maquina.sh
    source "${RAIZ}/scripts/lib/camada_de_maquina.sh"
    instalar_camada_de_maquina

    passo "pronto."
    printf 'O grupo `hefesto` só vale a partir do PRÓXIMO LOGIN — até lá quem\n'
    printf 'dá acesso a /dev/uhid e /dev/uinput é a ACL do uaccess, que o\n'
    printf 'trigger do udev já reaplicou. Reinicie o daemon para ele pegar:\n'
    printf '    systemctl --user restart %s.service\n' "$APP_ID"
    exit 0
fi

# ============================================================================
conferir || exit 1
[[ $SO_CONFERIR -eq 1 ]] && { verde "só conferi; nada instalado."; exit 0; }

if [[ $SIM -eq 0 ]]; then
    printf '\nInstalar o Hefesto (dev) a partir de %s? [s/N] ' "$RAIZ"
    read -r resposta
    [[ "$resposta" =~ ^[sS] ]] || { echo "nada feito."; exit 0; }
fi

# --- 1. ícones ---------------------------------------------------------------
    # O SVG QUE VAI PARA O RASTERIZADOR NÃO É O ARQUIVO DELA — é uma cópia com
    # os transforms ASSADOS. Decisão dela, 30/08/2026: *"então o nosso install
    # sempre deve corrigir ele pra ter o mesmo SVG em qualquer versão, PNG ou
    # afins."*
    #
    # O editor dela escreve rotação e espelho com `transform-box` e
    # `transform-origin`, que o navegador honra e o `librsvg` IGNORA. Sem assar,
    # o anel e o martelo saem da arte e o ícone da dock não é o desenho dela —
    # aconteceu TRÊS vezes em 29 e 30/08, e ela apontou as três.
    #
    # O arquivo dela não é tocado: o assado vive num temporário.
    LOGO_DEV="${RAIZ}/assets/hefesto-dev-logo.svg"
    if grep -q 'transform-box\|transform-origin' "$LOGO_DEV" 2>/dev/null; then
        _PY="${RAIZ}/.venv/bin/python"; [ -x "$_PY" ] || _PY=python3
        _ASSADA="$(mktemp -t hefesto-dev-logo-assada-XXXXXX.svg)"
        if "$_PY" "${RAIZ}/scripts/assar_transforms_svg.py" "$LOGO_DEV" "$_ASSADA" >/dev/null 2>&1; then
            verde "  transforms assados (o librsvg os ignora; o navegador não)"
            LOGO_DEV="$_ASSADA"
        else
            vermelho "  AVISO: não consegui assar — o ícone pode sair torto"
        fi
    fi

passo "1/5  ícones (a logo de dev que ela desenhou)"
for t in ${TAMANHOS}; do
    mkdir -p "${HICOLOR}/${t}x${t}/apps"
    rsvg-convert -w "$t" -h "$t" "$LOGO_DEV" \
        -o "${HICOLOR}/${t}x${t}/apps/${APP_ID}.png"
done
mkdir -p "${HOME}/.local/share/pixmaps"
cp -f "${HICOLOR}/256x256/apps/${APP_ID}.png" \
    "${HOME}/.local/share/pixmaps/${APP_ID}.png"
if [[ -f "${RAIZ}/assets/simbolico/hefesto-dualsense4unix-symbolic.svg" ]]; then
    mkdir -p "${HICOLOR}/symbolic/apps"
    cp -f "${RAIZ}/assets/simbolico/hefesto-dualsense4unix-symbolic.svg" \
        "${HICOLOR}/symbolic/apps/${APP_ID}-symbolic.svg"
fi
command -v gtk-update-icon-cache >/dev/null 2>&1 &&
    gtk-update-icon-cache -q -f "$HICOLOR" 2>/dev/null || true
verde "  ${TAMANHOS// /, } px + simbólico"

# --- 2. binários -------------------------------------------------------------
passo "2/5  binários em ~/.local/bin (todos com 'dev' no meio)"
mkdir -p "$BIN"
ln -sfn "${RAIZ}/.venv/bin/hefesto-dualsense4unix" "${BIN}/${APP_ID}"
cat > "${BIN}/${APP_ID}-gui" <<LANCA
#!/usr/bin/env bash
# Gerado por install-dev.sh. HEFESTO_VARIANTE=dev é o que dá a este processo
# casa própria: config, socket, unit, WM_CLASS e ícone (utils/identidade.py).
export HEFESTO_VARIANTE=${VARIANTE}
setsid nohup env GDK_BACKEND=x11 "${RAIZ}/run.sh" "\$@" </dev/null >/dev/null 2>&1 &
disown 2>/dev/null || true
LANCA
chmod +x "${BIN}/${APP_ID}-gui"
install -m 755 "${RAIZ}/scripts/hefesto-chave.sh" "${BIN}/hefesto-chave"
verde "  ${APP_ID}, ${APP_ID}-gui, hefesto-chave"

# --- 3. .desktop -------------------------------------------------------------
passo "3/5  atalho"
mkdir -p "$APLICATIVOS"
sed "s|@RAIZ@|${RAIZ}|g" "${RAIZ}/packaging/${APP_ID}.desktop" > "$DESKTOP"
command -v desktop-file-validate >/dev/null 2>&1 &&
    desktop-file-validate "$DESKTOP" >/dev/null 2>&1 || true
command -v update-desktop-database >/dev/null 2>&1 &&
    update-desktop-database -q "$APLICATIVOS" 2>/dev/null || true
verde "  $DESKTOP"

# --- 4. unit ----------------------------------------------------------------
passo "4/5  unit systemd --user (instalada, NÃO habilitada)"
mkdir -p "$UNITS"
cat > "$UNIT" <<UNITFIM
[Unit]
Description=Hefesto (dev) - Dualsense4Unix: daemon do app de desenvolvimento
After=graphical-session.target default.target
StartLimitIntervalSec=30
StartLimitBurst=3

[Service]
Type=simple
Environment=HEFESTO_VARIANTE=${VARIANTE}
Environment=PYTHONUNBUFFERED=1
ExecStartPre=-/usr/bin/systemctl --user import-environment WAYLAND_DISPLAY DISPLAY
ExecStart=%h/.local/bin/${APP_ID} daemon start --foreground
Restart=on-failure
RestartSec=2
SuccessExitStatus=143 SIGTERM

[Install]
WantedBy=default.target
UNITFIM
systemctl --user daemon-reload >/dev/null 2>&1 || true
verde "  $UNIT"
printf '  NÃO habilitada de propósito: dois daemons disputam o aparelho.\n'
printf '  Quando quiser o de dev no boot:\n'
printf '      hefesto-chave estavel off\n'
printf '      systemctl --user enable --now %s.service\n' "$APP_ID"

# --- 5. o retrato ------------------------------------------------------------
passo "5/5  como está a máquina agora"
"${BIN}/hefesto-chave" estado || true

cat <<FIM

pronto.

  abrir a interface nova : ${RAIZ}/interface
  abrir o app completo   : ${APP_ID}-gui
  desligar o estável     : hefesto-chave estavel off
  religar o estável      : hefesto-chave estavel on
  tirar tudo isto        : ${RAIZ}/install-dev.sh --desfazer

Nada do Hefesto estável foi tocado por este script.
FIM
