#!/usr/bin/env bash

set -euo pipefail

RAIZ_UCM="/usr/share/alsa/ucm2"
SYSFS="/sys"
ACAO="aplicar"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --remover) ACAO="remover" ;;
        --status)  ACAO="status" ;;
        --raiz-ucm) RAIZ_UCM="$2"; shift ;;
        --sysfs)    SYSFS="$2"; shift ;;
        *) printf '[ucm] opção desconhecida: %s\n' "$1" >&2; exit 2 ;;
    esac
    shift
done

readonly MARCADOR="hefesto-ucm-dualsense"
readonly FABRICANTE="Sony Interactive Entertainment"
readonly MODELOS=("DualSense Wireless Controller" "DualSense Edge Wireless Controller")
readonly CORTE=79
readonly VERBO="${RAIZ_UCM}/USB-Audio/Hefesto/DualSense-HiFi.conf"
readonly GANCHOS="${RAIZ_UCM}/conf.d/USB-Audio"

_aqui="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ASSETS=""
for cand in \
    "${_aqui}/../assets/ucm" \
    "/usr/share/hefesto-dualsense4unix/ucm" \
    "/usr/local/share/hefesto-dualsense4unix/ucm"; do
    [[ -f "${cand}/DualSense-gancho.conf" ]] && { ASSETS="${cand}"; break; }
done

info() { printf '[ucm] %s\n' "$*"; }
warn() { printf '[ucm] aviso: %s\n' "$*" >&2; }
die()  { printf '[ucm] ERRO: %s\n' "$*" >&2; exit 1; }

as_root() {
    if [[ "${EUID:-$(id -u)}" -eq 0 || -w "${RAIZ_UCM}" ]]; then
        "$@"
    elif command -v sudo >/dev/null 2>&1; then
        sudo "$@"
    else
        die "precisa de root e 'sudo' está ausente — rode como root"
    fi
}

controladores() {
    local rh
    for rh in "${SYSFS}"/bus/usb/devices/usb*; do
        [[ -e "${rh}" ]] || continue
        basename "$(dirname "$(readlink -f "${rh}")")"
    done | sort -u
}

ganchos_esperados() {
    local ctrl modelo base
    while IFS= read -r ctrl; do
        [[ -n "${ctrl}" ]] || continue
        for modelo in "${MODELOS[@]}"; do
            base="${FABRICANTE} ${modelo} at usb-${ctrl}-"
            if (( ${#base} < CORTE )); then
                warn "controlador ${ctrl}: o nome longo passa da porta — sem gancho para ${modelo}"
                continue
            fi
            printf '%s.conf\n' "${base:0:${CORTE}}"
        done
    done < <(controladores) | sort -u
}

usr_so_leitura() {
    command -v findmnt >/dev/null 2>&1 || return 1
    local opcoes
    opcoes="$(findmnt -n -o OPTIONS --target "${RAIZ_UCM}" 2>/dev/null)" || return 1
    [[ ",${opcoes}," == *",ro,"* ]]
}

nossos_no_disco() {
    [[ -d "${GANCHOS}" ]] || return 0
    grep -l -F -- "${MARCADOR}" "${GANCHOS}"/*.conf 2>/dev/null | while IFS= read -r f; do
        basename "${f}"
    done
}

do_aplicar() {
    [[ -n "${ASSETS}" ]] || die "assets/ucm/ não encontrado"
    if [[ ! -f "${RAIZ_UCM}/ucm.conf" ]]; then
        warn "${RAIZ_UCM}/ucm.conf ausente (sem alsa-ucm-conf) — nada a fazer"
        return 0
    fi
    if ! grep -q 'conf\.d' "${RAIZ_UCM}/ucm.conf"; then
        warn "o ucm.conf desta distro não procura conf.d/ — o gancho não seria lido"
        return 0
    fi
    if usr_so_leitura; then
        info "${RAIZ_UCM} está num sistema de arquivos só de leitura (distro imutável) — nada gravado; efeito: a vibração dos jogos da Sony pelo cabo só chega se o perfil UCM da própria imagem do sistema já conhecer o DualSense"
        return 0
    fi
    local -a esperados=()
    mapfile -t esperados < <(ganchos_esperados)
    if [[ ${#esperados[@]} -eq 0 ]]; then
        warn "nenhum controlador USB com nome que caiba no corte — nada gravado"
        return 0
    fi
    if ! cmp -s "${ASSETS}/DualSense-HiFi.conf" "${VERBO}"; then
        as_root install -D -m 0644 "${ASSETS}/DualSense-HiFi.conf" "${VERBO}"
        info "verbo HiFi em ${VERBO}"
    fi
    local nome gravados=0
    for nome in "${esperados[@]}"; do
        if ! cmp -s "${ASSETS}/DualSense-gancho.conf" "${GANCHOS}/${nome}"; then
            as_root install -D -m 0644 "${ASSETS}/DualSense-gancho.conf" "${GANCHOS}/${nome}"
            gravados=$((gravados + 1))
        fi
    done
    local velho achou
    while IFS= read -r velho; do
        [[ -n "${velho}" ]] || continue
        achou=0
        for nome in "${esperados[@]}"; do
            [[ "${nome}" == "${velho}" ]] && { achou=1; break; }
        done
        [[ "${achou}" -eq 1 ]] || as_root rm -f "${GANCHOS}/${velho}"
    done < <(nossos_no_disco)
    info "${#esperados[@]} gancho(s) em ${GANCHOS}/ (${gravados} novo(s)) — vale no próximo replug do controle"
}

do_remover() {
    local velho n=0
    if usr_so_leitura; then
        info "${RAIZ_UCM} está num sistema de arquivos só de leitura (distro imutável) — nada removido"
        return 0
    fi
    while IFS= read -r velho; do
        [[ -n "${velho}" ]] || continue
        as_root rm -f "${GANCHOS}/${velho}"
        n=$((n + 1))
    done < <(nossos_no_disco)
    if [[ -e "${VERBO}" ]]; then
        as_root rm -f "${VERBO}"
        as_root rmdir "$(dirname "${VERBO}")" 2>/dev/null || true
    fi
    info "${n} gancho(s) removido(s)"
}

do_status() {
    local nome faltam=0
    while IFS= read -r nome; do
        [[ -n "${nome}" ]] || continue
        if [[ -f "${GANCHOS}/${nome}" ]]; then
            info "ok       ${nome}"
        else
            info "FALTA    ${nome}"
            faltam=$((faltam + 1))
        fi
    done < <(ganchos_esperados 2>/dev/null)
    [[ -f "${VERBO}" ]] || { info "FALTA    ${VERBO}"; faltam=$((faltam + 1)); }
    [[ "${faltam}" -eq 0 ]]
}

case "${ACAO}" in
    aplicar) do_aplicar ;;
    remover) do_remover ;;
    status)  do_status ;;
esac
