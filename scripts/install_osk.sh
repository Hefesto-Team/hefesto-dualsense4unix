#!/usr/bin/env bash

set -uo pipefail
_ajuda() {
  cat <<'AJUDA'
install_osk.sh — instala o TECLADO NA TELA que o L3 do controle abre.

USO
  scripts/install_osk.sh              # instala o certo para esta sessão
  scripts/install_osk.sh --status     # só relata (saída legível por máquina)
  scripts/install_osk.sh --yes        # não pergunta nada (headless)
  scripts/install_osk.sh --dry-run    # decide e grava, sem instalar nada
AJUDA
}

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
    _ajuda
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

binario_instalado() {
    local b
    if [[ -n "${HEFESTO_OSK_INSTALADO:-}" ]]; then
        [[ "${HEFESTO_OSK_INSTALADO}" == "nenhum" ]] && return 1
        printf '%s\n' "${HEFESTO_OSK_INSTALADO}"
        return 0
    fi
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

relatar() {
    local sessao esperado atual caminho casa sentinela
    sessao="$(sessao_grafica)"
    esperado="$(binario_da_sessao)"
    atual="$(binario_instalado || true)"
    caminho=""
    [[ -n "${atual}" ]] && caminho="$(command -v "${atual}" 2>/dev/null || true)"
    if [[ "${atual}" == "${esperado}" ]]; then casa="sim"; else casa="nao"; fi
    [[ -z "${atual}" ]] && casa="nao"
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
