#!/usr/bin/env bash
# install_osk.sh — instala o TECLADO NA TELA que o L3 do controle abre.
#
# POR QUE ISTO EXISTE
# -------------------
# O mapa de fábrica do teclado emulado (`core/keyboard_mappings.py`) dá ao L3 o
# token `__OPEN_OSK__`, e o daemon (`daemon/subsystems/keyboard.py`) o cumpre
# abrindo um teclado na tela DO SISTEMA. Medido na máquina dela em 09/08/2026:
#
#     command -v onboard wvkbd-mobintl   ->  NENHUM DOS DOIS
#     grep -c onboard install.sh         ->  0
#     grep -c onboard packaging/debian/control -> 0
#
# Zero. O produto prometia um gesto e não instalava, não declarava e não
# conferia o que ele precisa. E o preço é maior do que parece: nenhum dos nove
# atalhos de fábrica digita uma LETRA (são Super, PrintScreen, Alt+Tab,
# Alt+Shift+Tab, Enter, Delete, Backspace e os dois tokens de OSK), então sem o
# teclado na tela "o teclado emulado não digita" é literalmente verdade.
#
# QUAL PACOTE, E POR QUÊ — o critério é MEDIDO, não preferido
# ----------------------------------------------------------
# Há dois candidatos, e quem decide qual dos dois FUNCIONA é a sessão gráfica:
#
#   wvkbd (binário `wvkbd-mobintl`) — para WAYLAND.
#     Cliente Wayland puro. `Depends` do pacote Debian: libc6, libcairo2,
#     libpango-1.0-0, libpangocairo-1.0-0, libwayland-client0 — e mais nada.
#     Aparece na tela pelo `zwlr_layer_shell_v1` e DIGITA pelo
#     `zwp_virtual_keyboard_manager_v1`; os dois .xml viajam dentro do próprio
#     tarball, em `proto/`, então ele não depende de wayland-protocols do host.
#
#   onboard — para X11.
#     GTK3, e `Depends: libx11-6, libxi6, libxkbfile1, libxtst6`. O `libxtst6`
#     é o XTEST, que é COMO ele digita: injeta no servidor X. Numa sessão
#     Wayland ele até ABRE (via XWayland), e as teclas só chegam a clientes
#     XWayland — a janela nativa em foco não recebe nada. Abrir e não digitar é
#     PIOR que não abrir, porque parece que funcionou.
#
# A MEDIÇÃO QUE FECHA O CRITÉRIO (10/08/2026, máquina dela — Pop!_OS 24.04,
# COSMIC/Wayland, `XDG_SESSION_TYPE=wayland`):
#
#     wayland-info | grep -E 'layer_shell|virtual_keyboard'
#       interface: 'zwp_virtual_keyboard_manager_v1',  version: 1
#       interface: 'zwlr_layer_shell_v1',              version: 5
#
# O cosmic-comp expõe EXATAMENTE os dois protocolos de que o wvkbd precisa —
# ele não é wlroots, mas implementa as duas extensões wlr que o wvkbd usa. Por
# isso, em Wayland, o pacote é o `wvkbd`. Não por ser mais novo nem mais leve
# (embora seja: 800 KB de binário contra onboard + onboard-common +
# onboard-data + hunspell + python3-dbus), mas porque é o que DIGITA.
#
# A SENTINELA, E POR QUE ELA EXISTE
# ---------------------------------
# O commit 108b711 registrou a armadilha desta casa: "install.sh ARMA,
# uninstall.sh DESARMA, doctor.sh lê a AUSÊNCIA como escolha dela — máquina
# curada e máquina quebrada são o MESMO estado para o portão". Aqui o uninstall
# NÃO desarma (pacote de sistema não é nosso para remover — mesma decisão do
# `libopus0` da ponte de mic), mas a ausência continua ambígua: pode ser que o
# install nunca tenha passado por aqui, que ele tenha TENTADO e falhado (sem
# sudo, sem rede, distro sem o pacote), que ela tenha pedido para pular, ou que
# ela tenha removido o pacote depois. São quatro histórias diferentes com o
# mesmo `command -v` vazio.
#
# Por isso este script GRAVA o que fez em
# `~/.local/state/hefesto-dualsense4unix/teclado-na-tela.conf`, e o
# `scripts/doctor.sh` lê a sentinela junto com o disco para dizer QUAL das
# quatro é. O uninstall apaga a sentinela (é estado NOSSO) e não toca no pacote.
#
# USO
#   scripts/install_osk.sh              # instala o certo para esta sessão
#   scripts/install_osk.sh --status     # só relata (saída legível por máquina)
#   scripts/install_osk.sh --yes        # não pergunta nada (headless)
#   scripts/install_osk.sh --dry-run    # decide e grava, sem instalar nada
#
# SAÍDA: 0 sempre no modo instalar. Teclado na tela é o caminho de TEXTO, não o
# produto inteiro — derrubar o install por causa dele trocaria um problema
# grande por um problema maior. No `--status`, 0 se há teclado utilizável nesta
# sessão e 1 se não há.
#
# GANCHOS DE TESTE (é assim que o portão de paridade roda isto sem sudo e sem
# tocar na máquina): HEFESTO_OSK_STATE (caminho da sentinela),
# HEFESTO_OSK_SESSAO (força wayland|x11|desconhecida), HEFESTO_OSK_GERENCIADOR
# (força apt|dnf|pacman|nenhum), HEFESTO_OSK_DRY_RUN=1 (nunca chama o
# gerenciador de pacotes).

set -uo pipefail

# ---------------------------------------------------------------------------
# O contrato de nomes. Estas quatro linhas são o que o portão de paridade
# compara contra `scripts/doctor.sh` e contra `daemon/subsystems/keyboard.py`:
# instalador, conferidor e daemon têm de estar falando do MESMO binário para a
# MESMA sessão, senão o produto instala um e procura outro.
# ---------------------------------------------------------------------------
readonly OSK_BIN_WAYLAND="wvkbd-mobintl"
readonly OSK_BIN_X11="onboard"
readonly OSK_PKG_WAYLAND="wvkbd"
readonly OSK_PKG_X11="onboard"

readonly SENTINELA_PADRAO="${HOME}/.local/state/hefesto-dualsense4unix/teclado-na-tela.conf"
SENTINELA="${HEFESTO_OSK_STATE:-${SENTINELA_PADRAO}}"

MODO="instalar"
ASSUME_SIM=0
DRY_RUN="${HEFESTO_OSK_DRY_RUN:-0}"

info() { printf '  %s\n' "$*"; }
ok()   { printf '  [ OK ] %s\n' "$*"; }
warn() { printf '  [aviso] %s\n' "$*" >&2; }

uso() {
    awk 'NR == 1 { next } /^#/ { sub(/^# ?/, ""); print; next } { exit }' \
        "${BASH_SOURCE[0]}"
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --status)   MODO="status" ;;
        --dry-run)  DRY_RUN=1 ;;
        --yes|-y)   ASSUME_SIM=1 ;;
        -h|--help)  uso; exit 0 ;;
        *) warn "opção desconhecida: $1"; uso; exit 0 ;;
    esac
    shift
done

# ---------------------------------------------------------------------------
# Sessão gráfica. `WAYLAND_DISPLAY` é a evidência mais forte (é a variável que
# o próprio cliente Wayland usa para conectar), e é a que o daemon enxerga: a
# unit faz `systemctl --user import-environment WAYLAND_DISPLAY DISPLAY` no
# ExecStartPre, e o processo vivo desta máquina traz `WAYLAND_DISPLAY=wayland-1`
# — medido em 10/08/2026 lendo /proc/<pid>/environ. Sem isso o wvkbd nasceria
# sem compositor para conectar, e a escolha aqui seria acadêmica.
#
# Note a ordem: `DISPLAY` sozinho NÃO decide, porque numa sessão Wayland com
# XWayland ele também está setado (`DISPLAY=:1` nesta máquina). Só depois de
# descartar Wayland é que `DISPLAY` significa X11.
# ---------------------------------------------------------------------------
sessao_grafica() {
    if [[ -n "${HEFESTO_OSK_SESSAO:-}" ]]; then
        printf '%s\n' "${HEFESTO_OSK_SESSAO}"
        return 0
    fi
    if [[ -n "${WAYLAND_DISPLAY:-}" ]] || [[ "${XDG_SESSION_TYPE:-}" == "wayland" ]]; then
        printf 'wayland\n'
        return 0
    fi
    if [[ -n "${DISPLAY:-}" ]] || [[ "${XDG_SESSION_TYPE:-}" == "x11" ]]; then
        printf 'x11\n'
        return 0
    fi
    printf 'desconhecida\n'
}

# Binário que FUNCIONA nesta sessão. Em "desconhecida" (install headless, por
# ssh, CI) a aposta é declarada e não escondida: vale o de Wayland, que é o
# padrão de todo desktop atual — e o doctor, que roda DENTRO da sessão dela,
# corrige o veredito depois se a máquina for X11.
binario_da_sessao() {
    case "$(sessao_grafica)" in
        x11) printf '%s\n' "${OSK_BIN_X11}" ;;
        *)   printf '%s\n' "${OSK_BIN_WAYLAND}" ;;
    esac
}

pacote_do_binario() {
    case "$1" in
        "${OSK_BIN_X11}") printf '%s\n' "${OSK_PKG_X11}" ;;
        *)                printf '%s\n' "${OSK_PKG_WAYLAND}" ;;
    esac
}

# Qualquer um dos dois que esteja no PATH — inclusive o "errado" para esta
# sessão. Quem julga se serve é quem chama.
binario_instalado() {
    local b
    for b in "${OSK_BIN_WAYLAND}" "${OSK_BIN_X11}"; do
        if command -v "${b}" >/dev/null 2>&1; then
            printf '%s\n' "${b}"
            return 0
        fi
    done
    return 1
}

gerenciador() {
    if [[ -n "${HEFESTO_OSK_GERENCIADOR:-}" ]]; then
        printf '%s\n' "${HEFESTO_OSK_GERENCIADOR}"
        return 0
    fi
    command -v apt-get >/dev/null 2>&1 && { printf 'apt\n'; return 0; }
    command -v dnf     >/dev/null 2>&1 && { printf 'dnf\n'; return 0; }
    command -v pacman  >/dev/null 2>&1 && { printf 'pacman\n'; return 0; }
    printf 'nenhum\n'
}

# O comando exato que ela roda se nós não conseguirmos — impresso, nunca
# escondido. É a mesma string que o doctor imprime, e é por isso que ela mora
# aqui, num lugar só.
comando_manual() {
    local pacote="$1"
    case "$(gerenciador)" in
        apt)    printf 'sudo apt install %s\n' "${pacote}" ;;
        dnf)    printf 'sudo dnf install %s\n' "${pacote}" ;;
        pacman) printf 'sudo pacman -S %s\n' "${pacote}" ;;
        *)      printf 'instale o pacote %s pela sua distribuição\n' "${pacote}" ;;
    esac
}

sudo_utilizavel() {
    command -v sudo >/dev/null 2>&1 || return 1
    sudo -n true 2>/dev/null && return 0
    # Só vale insistir com senha se há terminal E ela não pediu modo silencioso.
    [[ "${ASSUME_SIM}" -eq 1 ]] && return 1
    [[ -t 0 ]] || return 1
    return 0
}

sudo_rodar() {
    if sudo -n true 2>/dev/null; then
        sudo -n "$@"
    else
        sudo "$@"
    fi
}

gravar_sentinela() {
    local resultado="$1" pacote="$2" binario="$3" motivo="${4:-}"
    local dir
    dir="$(dirname "${SENTINELA}")"
    mkdir -p "${dir}" 2>/dev/null || return 0
    {
        printf '# gravado por scripts/install_osk.sh — NÃO editar à mão.\n'
        printf '# É o que distingue "o install não instalou" de "ela removeu depois".\n'
        printf 'resultado=%s\n' "${resultado}"
        printf 'pacote=%s\n'    "${pacote}"
        printf 'binario=%s\n'   "${binario}"
        printf 'sessao=%s\n'    "$(sessao_grafica)"
        printf 'gerenciador=%s\n' "$(gerenciador)"
        printf 'motivo=%s\n'    "${motivo}"
        printf 'data=%s\n'      "$(date -Is 2>/dev/null || date)"
    } > "${SENTINELA}.tmp" 2>/dev/null && mv "${SENTINELA}.tmp" "${SENTINELA}" 2>/dev/null
    return 0
}

ler_sentinela() {
    local chave="$1"
    [[ -r "${SENTINELA}" ]] || return 1
    sed -n "s/^${chave}=//p" "${SENTINELA}" | head -1
}

# ---------------------------------------------------------------------------
# --status: saída legível por máquina (o doctor consome estas chaves) seguida
# do veredito humano. Sai 0 se há teclado UTILIZÁVEL nesta sessão.
# ---------------------------------------------------------------------------
relatar() {
    local sessao esperado atual caminho casa sentinela
    sessao="$(sessao_grafica)"
    esperado="$(binario_da_sessao)"
    atual="$(binario_instalado || true)"
    caminho=""
    [[ -n "${atual}" ]] && caminho="$(command -v "${atual}" 2>/dev/null || true)"
    # (noqa-acento): "sim"/"nao" sao VALORES de chave legivel por maquina, na
    # mesma linguagem ASCII do resto do bloco `--status` que o doctor consome.
    if [[ "${atual}" == "${esperado}" ]]; then casa="sim"; else casa="nao"; fi  # (noqa-acento)
    [[ -z "${atual}" ]] && casa="nao"  # (noqa-acento)
    sentinela="$(ler_sentinela resultado || true)"
    printf 'sessao=%s\n'     "${sessao}"
    printf 'esperado=%s\n'   "${esperado}"
    printf 'pacote=%s\n'     "$(pacote_do_binario "${esperado}")"
    printf 'instalado=%s\n'  "${atual}"
    printf 'caminho=%s\n'    "${caminho}"
    printf 'casa=%s\n'       "${casa}"
    printf 'sentinela=%s\n'  "${sentinela:-ausente}"
    printf 'comando=%s\n'    "$(comando_manual "$(pacote_do_binario "${esperado}")")"
    [[ "${casa}" == "sim" ]]
}

if [[ "${MODO}" == "status" ]]; then
    relatar
    exit $?
fi

# ---------------------------------------------------------------------------
# Instalar.
# ---------------------------------------------------------------------------
SESSAO="$(sessao_grafica)"
ESPERADO="$(binario_da_sessao)"
PACOTE="$(pacote_do_binario "${ESPERADO}")"
ATUAL="$(binario_instalado || true)"

if [[ "${ATUAL}" == "${ESPERADO}" ]]; then
    ok "teclado na tela já instalado: ${ESPERADO} (sessão ${SESSAO})"
    gravar_sentinela "ja-instalado" "${PACOTE}" "${ESPERADO}"
    exit 0
fi

if [[ -n "${ATUAL}" ]]; then
    # O caso que mais engana: `onboard` presente numa sessão Wayland. Ele abre e
    # não digita fora do XWayland, então "tem teclado instalado" seria uma
    # resposta falsa. Instalamos o certo POR CIMA — sem remover o outro, que não
    # é nosso.
    info "há ${ATUAL} instalado, mas a sessão é ${SESSAO} — quem digita aqui é ${ESPERADO}"
fi

GERENCIADOR="$(gerenciador)"
if [[ "${GERENCIADOR}" == "nenhum" ]]; then
    warn "sem apt/dnf/pacman — não sei instalar ${PACOTE} nesta distribuição"
    info "instale à mão: $(comando_manual "${PACOTE}")"
    gravar_sentinela "falhou" "${PACOTE}" "${ESPERADO}" "sem-gerenciador"
    exit 0
fi

if [[ "${DRY_RUN}" -eq 1 ]]; then
    info "dry-run: instalaria ${PACOTE} (${ESPERADO}) via ${GERENCIADOR}"
    gravar_sentinela "dry-run" "${PACOTE}" "${ESPERADO}" "dry-run"
    exit 0
fi

if ! sudo_utilizavel; then
    warn "sem sudo utilizável — o teclado na tela fica de fora"
    info "rode: $(comando_manual "${PACOTE}")"
    gravar_sentinela "falhou" "${PACOTE}" "${ESPERADO}" "sem-sudo"
    exit 0
fi

info "instalando o teclado na tela pelo ${GERENCIADOR}: ${PACOTE}"
_saida="$(mktemp 2>/dev/null || printf '/tmp/hefesto-osk.log')"
_rc=0
case "${GERENCIADOR}" in
    apt)    sudo_rodar apt-get install -y -qq "${PACOTE}" > "${_saida}" 2>&1 || _rc=$? ;;
    dnf)    sudo_rodar dnf install -y "${PACOTE}"         > "${_saida}" 2>&1 || _rc=$? ;;
    pacman) sudo_rodar pacman -S --noconfirm --needed "${PACOTE}" > "${_saida}" 2>&1 || _rc=$? ;;
esac

if [[ "${_rc}" -eq 0 ]] && command -v "${ESPERADO}" >/dev/null 2>&1; then
    ok "teclado na tela instalado: ${ESPERADO} — o L3 do controle já abre"
    gravar_sentinela "instalado" "${PACOTE}" "${ESPERADO}"
    rm -f "${_saida}"
    exit 0
fi

warn "não consegui instalar ${PACOTE} (o L3 vai avisar na tela em vez de abrir)"
[[ -s "${_saida}" ]] && tail -3 "${_saida}" >&2
info "rode: $(comando_manual "${PACOTE}")"
gravar_sentinela "falhou" "${PACOTE}" "${ESPERADO}" "gerenciador-falhou"
rm -f "${_saida}"
exit 0

# "A natureza nada faz em vão." — Aristóteles
