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
# O QUE ELE NÃO INSTALA, E ISSO É DECISÃO, NÃO ESQUECIMENTO
# ----------------------------------------------------------
# Regras udev, o broker hidraw, `hefesto-bt-agent`, `bt-health-watchdog`, nada
# em `/usr/local/lib`. Essa camada é da MÁQUINA, não do app: um segundo
# instalador escrevendo por cima de `/etc/udev/rules.d/70-ps5-controller.rules`
# faria o app dela passar a rodar sob regra de dev sem uma linha dizendo isso,
# e o `--desfazer` de um levaria a regra do outro junto. Pior: as regras 82 e 83
# executam script de `/usr/local/lib/hefesto-dualsense4unix/` como root na borda
# do hotplug (`assets/82-nintendo-pro-nosniff.rules:96`).
#
# O app de dev DEPENDE do Hefesto estável para essa camada — e o broker foi
# desenhado para isso: `broker/hidraw_broker.py:507-518` diz, literal, que
# "dois daemons em takeover convivem", cada um com sua lease. Um broker, dois
# daemons. Se o estável não estiver instalado, este script AVISA e continua:
# a interface nova (`./interface`) só LÊ o daemon e funciona mesmo assim.
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
for arg in "$@"; do
    case "$arg" in
        --yes|-y)     SIM=1 ;;
        --conferir)   SO_CONFERIR=1 ;;
        --desfazer)   DESFAZER=1 ;;
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
    elif grep -q 'transform-origin\|transform-box' "${RAIZ}/assets/hefesto-dev-logo.svg"; then
        vermelho "  RECUSO: a logo de dev ainda tem transform-origin/transform-box."
        vermelho "          O librsvg os IGNORA e o ícone sai mutilado na dock."
        vermelho "          Asse os transforms na matriz antes (ver o cabeçalho"
        vermelho "          de assets/hefesto-dev-logo.svg)."
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
    if [[ ! -f "$ESTAVEL_DESKTOP" ]]; then
        printf '  aviso: o Hefesto estável não parece instalado.\n'
        printf '         O app de dev NÃO instala udev nem o broker (é da\n'
        printf '         máquina, não do app) — sem o estável, o daemon de dev\n'
        printf '         pode não enxergar o aparelho. A interface (./interface)\n'
        printf '         funciona mesmo assim: ela só LÊ.\n'
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
conferir || exit 1
[[ $SO_CONFERIR -eq 1 ]] && { verde "só conferi; nada instalado."; exit 0; }

if [[ $SIM -eq 0 ]]; then
    printf '\nInstalar o Hefesto (dev) a partir de %s? [s/N] ' "$RAIZ"
    read -r resposta
    [[ "$resposta" =~ ^[sS] ]] || { echo "nada feito."; exit 0; }
fi

# --- 1. ícones ---------------------------------------------------------------
passo "1/5  ícones (logo de dev, âmbar)"
for t in ${TAMANHOS}; do
    mkdir -p "${HICOLOR}/${t}x${t}/apps"
    rsvg-convert -w "$t" -h "$t" "${RAIZ}/assets/hefesto-dev-logo.svg" \
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
