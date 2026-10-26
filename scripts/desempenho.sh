#!/usr/bin/env bash
set -euo pipefail

_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

RAIZ="${HEFESTO_DESEMPENHO_RAIZ:-}"
SYS="${HEFESTO_DESEMPENHO_SYS:-/sys}"
PROC="${HEFESTO_DESEMPENHO_PROC:-/proc}"
ASSETS="${HEFESTO_DESEMPENHO_ASSETS:-${_SCRIPT_DIR}/../assets/desempenho}"
PROVADOS="${HEFESTO_DESEMPENHO_PROVADOS-}"

IDS_DECIDIDOS="perfil"
IDS_TODOS="perfil nvidia audio aspm"

ARQ_UNIT="${RAIZ}/etc/systemd/system/hefesto-desempenho.service"
ARQ_WANTS="${RAIZ}/etc/systemd/system/multi-user.target.wants/hefesto-desempenho.service"
ARQ_NVIDIA="${RAIZ}/etc/modprobe.d/hefesto-desempenho-nvidia.conf"
ARQ_AUDIO="${RAIZ}/etc/modprobe.d/hefesto-desempenho-audio.conf"
ARQ_ASPM="${RAIZ}/etc/tmpfiles.d/hefesto-desempenho-aspm.conf"

if [[ -n "${RAIZ}" ]]; then
    SUDO=()
else
    SUDO=(sudo)
fi

_dizer() { printf '      %s\n' "$*"; }

_como_root() { "${SUDO[@]}" "$@"; }

_achar() {
    if [[ -n "${HEFESTO_DESEMPENHO_BIN:-}" ]]; then
        [[ -x "${HEFESTO_DESEMPENHO_BIN}/$1" ]] && printf '%s' "${HEFESTO_DESEMPENHO_BIN}/$1"
        return 0
    fi
    command -v "$1" 2>/dev/null || true
}

_gerenciador() {
    if [[ -n "$(_achar system76-power)" ]]; then
        printf 'system76-power'
    elif [[ -n "$(_achar powerprofilesctl)" ]]; then
        printf 'power-profiles-daemon'
    fi
}

_ppd_sem_performance() {
    local lista
    lista="$(timeout 5 "$(_achar powerprofilesctl)" list 2>/dev/null)" || return 1
    ! grep -Eq '^[[:space:]*]*performance:' <<<"${lista}"
}

_falta_na_maquina() {
    case "$1" in
        perfil)
            if [[ -z "$(_gerenciador)" ]]; then
                printf 'sem system76-power nem power-profiles-daemon, não há perfil de energia a pedir'
            elif [[ "$(_gerenciador)" == "power-profiles-daemon" ]] && _ppd_sem_performance; then
                printf 'o power-profiles-daemon desta máquina não oferece o perfil performance'
            fi
            ;;
        nvidia)
            [[ -d "${SYS}/module/nvidia" || -r "${PROC}/driver/nvidia/params" ]] \
                || printf 'sem o driver NVIDIA carregado (a placa é outra, ou está sem driver)'
            ;;
        audio)
            [[ -d "${SYS}/module/snd_hda_intel" ]] \
                || printf 'sem snd_hda_intel carregado (o áudio desta máquina é outro)'
            ;;
        aspm)
            [[ -e "${SYS}/module/pcie_aspm/parameters/policy" ]] \
                || printf 'este kernel não expõe a política de ASPM do PCIe'
            ;;
    esac
}

_instalar_asset() {
    local asset="$1" destino="$2"
    [[ -f "${ASSETS}/${asset}" ]] || { _dizer "aviso: falta ${ASSETS}/${asset}"; return 1; }
    _como_root install -Dm644 "${ASSETS}/${asset}" "${destino}"
}

_aplicar_perfil() {
    local gerenciador comando unidade tmp
    gerenciador="$(_gerenciador)"
    if [[ "${gerenciador}" == "system76-power" ]]; then
        comando="/bin/sh -c 'system76-power profile performance; system76-power profile | grep -q \"^Power Profile: Performance\"'"
        unidade="com.system76.PowerDaemon.service"
    else
        comando="/bin/sh -c 'powerprofilesctl set performance; powerprofilesctl get | grep -qx performance'"
        unidade="power-profiles-daemon.service"
    fi
    tmp="$(mktemp)"
    sed -e "s#__SERVICO_DO_GERENCIADOR__#${unidade}#g" -e "s#__COMANDO__#${comando}#g" \
        "${ASSETS}/hefesto-desempenho.service" >"${tmp}"
    if grep -q '__[A-Z_]*__' "${tmp}"; then
        rm -f "${tmp}"
        _dizer "aviso: o modelo da unit do perfil ficou com marcador sem trocar — nada gravado"
        return 1
    fi
    _como_root install -Dm644 "${tmp}" "${ARQ_UNIT}" || { rm -f "${tmp}"; return 1; }
    rm -f "${tmp}"
    if [[ -z "${RAIZ}" ]]; then
        sudo systemctl daemon-reload >/dev/null 2>&1 || true
        sudo systemctl reset-failed hefesto-desempenho.service >/dev/null 2>&1 || true
        if sudo systemctl enable --now hefesto-desempenho.service >/dev/null 2>&1; then
            _dizer "perfil: aplicado (${gerenciador}; a unit hefesto-desempenho.service pede Performance a cada boot)"
        else
            _dizer "aviso: perfil: a unit foi gravada e o enable falhou — habilite: sudo systemctl enable --now hefesto-desempenho.service"
        fi
    else
        _como_root mkdir -p "$(dirname "${ARQ_WANTS}")"
        _como_root ln -sf ../hefesto-desempenho.service "${ARQ_WANTS}"
        _dizer "perfil: aplicado (${gerenciador}; a unit hefesto-desempenho.service pede Performance a cada boot)"
    fi
}

_aplicar_um() {
    local id="$1" motivo
    motivo="$(_falta_na_maquina "${id}")"
    if [[ -n "${motivo}" ]]; then
        _dizer "${id}: pulado, ${motivo}"
        return 0
    fi
    case "${id}" in
        perfil)
            _aplicar_perfil || _dizer "aviso: perfil: não consegui gravar a unit"
            ;;
        nvidia)
            if _instalar_asset hefesto-desempenho-nvidia.conf "${ARQ_NVIDIA}"; then
                _dizer "nvidia: aplicado (modprobe.d: NVreg_DynamicPowerManagement=0; vale no próximo boot)"
            fi
            ;;
        audio)
            if _instalar_asset hefesto-desempenho-audio.conf "${ARQ_AUDIO}"; then
                _dizer "audio: aplicado (modprobe.d: snd_hda_intel power_save=0; vale no próximo boot)"
            fi
            ;;
        aspm)
            if _instalar_asset hefesto-desempenho-aspm.conf "${ARQ_ASPM}"; then
                _dizer "aspm: aplicado (tmpfiles.d: política performance a cada boot)"
            fi
            ;;
    esac
}

_conhecido() {
    local x
    for x in ${IDS_TODOS}; do
        [[ "$1" == "${x}" ]] && return 0
    done
    return 1
}

cmd_aplicar() {
    local ids=("$@") id
    if [[ "${#ids[@]}" -eq 0 ]]; then
        # shellcheck disable=SC2206
        ids=(${IDS_DECIDIDOS} ${PROVADOS})
        for id in ${IDS_TODOS}; do
            case " ${IDS_DECIDIDOS} ${PROVADOS} " in
                *" ${id} "*) ;;
                *) _dizer "${id}: não aplicado, a provar na bancada (ainda não está na lista dos provados do install)" ;;
            esac
        done
    fi
    for id in "${ids[@]}"; do
        if ! _conhecido "${id}"; then
            _dizer "aviso: ajuste desconhecido: ${id} (conheço: ${IDS_TODOS})"
            continue
        fi
        _aplicar_um "${id}"
    done
}

cmd_remover() {
    local achou=0 f
    if [[ -e "${ARQ_UNIT}" || -L "${ARQ_WANTS}" ]]; then
        achou=1
        if [[ -z "${RAIZ}" ]]; then
            sudo systemctl disable --now hefesto-desempenho.service >/dev/null 2>&1 || true
        else
            _como_root rm -f "${ARQ_WANTS}"
        fi
        _como_root rm -f "${ARQ_UNIT}" "${ARQ_WANTS}"
        if [[ -z "${RAIZ}" ]]; then
            sudo systemctl daemon-reload >/dev/null 2>&1 || true
            sudo systemctl reset-failed hefesto-desempenho.service >/dev/null 2>&1 || true
        fi
        _dizer "perfil: a unit saiu (o perfil de energia de agora fica como está; para mudar: system76-power profile balanced, ou powerprofilesctl set balanced)"
    fi
    for f in "${ARQ_NVIDIA}" "${ARQ_AUDIO}" "${ARQ_ASPM}"; do
        if [[ -e "${f}" ]]; then
            achou=1
            _como_root rm -f "${f}"
            _dizer "saiu ${f#"${RAIZ}"} (os valores de fábrica voltam no próximo boot)"
        fi
    done
    [[ "${achou}" -eq 1 ]] || _dizer "nenhum ajuste do modo desempenho estava instalado"
}

case "${1:-}" in
    aplicar) shift; cmd_aplicar "$@" ;;
    remover) cmd_remover ;;
    ids)     printf '%s\n' ${IDS_TODOS} ;;
    *)
        printf 'uso: desempenho.sh aplicar [id...] | remover | ids\n' >&2
        exit 2
        ;;
esac
