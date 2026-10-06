#!/usr/bin/env bash
# desempenho.sh — dono ÚNICO dos ajustes do modo desempenho.
#
#   desempenho.sh aplicar [id...]   grava os ajustes (install.sh, o passo desempenho)
#   desempenho.sh remover           desfaz TODOS os arquivos (uninstall.sh)
#   desempenho.sh ids               imprime os ids que este roteiro conhece
#
# O QUE É (decisão, 02/10/2026): o install pergunta se o computador deve ser
# usado no modo desempenho para jogar, e cada ajuste é um ARQUIVO PERMANENTE na
# forma que o install já usa para o USB e o Bluetooth (modprobe.d, tmpfiles.d,
# unit de sistema) — nunca um comando que some no reboot. Quem decide a pergunta
# e o padrão (sim no desktop, não no notebook com bateria) é a
# `install_desempenho_host`, em scripts/lib/camada_de_maquina.sh; este roteiro é
# só o mecanismo.
#
# OS AJUSTES
#   perfil   o perfil de energia em Performance, a cada boot (unit de sistema que
#            fala com o system76-power ou com o power-profiles-daemon). É
#            DECISÃO DE PRODUTO: entra sempre que o pedido é sim.
#   nvidia   NVreg_DynamicPowerManagement=0 (modprobe.d)          — a provar
#   audio    snd_hda_intel power_save=0 (modprobe.d)              — a provar
#   aspm     política ASPM do PCIe em performance (tmpfiles.d)    — a provar
#
# «A PROVAR» é literal: só entra no install o que a medida no aparelho mostrou.
# A lista dos provados mora no install.sh (`DESEMPENHO_PROVADOS`, vazia hoje) e
# chega aqui por HEFESTO_DESEMPENHO_PROVADOS; a prova liga um ajuste acrescentando
# o id àquela variável. Pedido EXPLÍCITO (`aplicar nvidia`) vale sempre — é como
# se grava o ajuste para provar na bancada, e `remover` o desfaz.
#
# O QUE A MÁQUINA NÃO TEM É PULADO E DITO, nunca erro: sem system76-power nem
# power-profiles-daemon não há perfil de energia; sem o módulo nvidia carregado a
# placa é outra (AMD, Intel) ou está sem driver; sem snd_hda_intel o áudio é
# outro; sem pcie_aspm no kernel não há política a escrever.
#
# NADA aqui reinicia nada nem escreve no sysfs: os arquivos valem no próximo
# boot (o `perfil`, além disso, é pedido ao gerenciador agora, pela unit).
#
# Overrides de bancada (em produção ficam todos no padrão):
#   HEFESTO_DESEMPENHO_RAIZ       prefixo de mentira para /etc (vazio = a máquina;
#                                 com ele não há sudo nem systemctl)
#   HEFESTO_DESEMPENHO_SYS        o /sys           (padrão /sys)
#   HEFESTO_DESEMPENHO_PROC       o /proc          (padrão /proc)
#   HEFESTO_DESEMPENHO_BIN        pasta onde procurar system76-power e
#                                 powerprofilesctl (padrão: o PATH)
#   HEFESTO_DESEMPENHO_ASSETS     assets/desempenho (padrão ../assets/desempenho)
#   HEFESTO_DESEMPENHO_PROVADOS   os ids provados, separados por espaço
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

# Roda como root na máquina; direto sob prefixo de mentira.
_como_root() { "${SUDO[@]}" "$@"; }

# Procura um binário: na pasta de bancada, se houver, senão no PATH.
_achar() {
    if [[ -n "${HEFESTO_DESEMPENHO_BIN:-}" ]]; then
        [[ -x "${HEFESTO_DESEMPENHO_BIN}/$1" ]] && printf '%s' "${HEFESTO_DESEMPENHO_BIN}/$1"
        return 0
    fi
    command -v "$1" 2>/dev/null || true
}

# O gerenciador de energia desta máquina: system76-power, power-profiles-daemon
# ou nada. O system76-power vem primeiro (no Pop!_OS é ele o dono do perfil).
_gerenciador() {
    if [[ -n "$(_achar system76-power)" ]]; then
        printf 'system76-power'
    elif [[ -n "$(_achar powerprofilesctl)" ]]; then
        printf 'power-profiles-daemon'
    fi
}

# O power-profiles-daemon só oferece «performance» quando um driver da máquina
# o sustenta (platform_profile, ou o pstate da CPU); sem ele a unit pediria um
# perfil que não existe e falharia a cada boot. Sem resposta do daemon não se
# sabe, e não se pula: a unit é o lado reversível.
_ppd_sem_performance() {
    local lista
    lista="$(timeout 5 "$(_achar powerprofilesctl)" list 2>/dev/null)" || return 1
    ! grep -Eq '^[[:space:]*]*performance:' <<<"${lista}"
}

# Diz se a máquina tem o que o ajuste mexe. Imprime o MOTIVO quando não tem.
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
    # O sucesso da unit é o ESTADO, não o código de saída do pedido: o
    # system76-power sai 1 quando uma peça do perfil falha (a política de link
    # de uma porta SATA que não a aceita, medido na máquina do usuário em 03/10) mesmo
    # com o perfil aplicado, e a unit ficaria falhada a cada boot. Pede, e
    # confere lendo o perfil de volta; o Restart= só volta a pedir se não pegou.
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
    # A guarda pós-render, como a das units do broker: nunca gravar unit com
    # marcador literal.
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
