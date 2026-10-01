#!/usr/bin/env bash
# hefesto_placa_acordada.sh — a placa de vídeo acordada enquanto um jogo vive.
#
# O-JOGO-LEVE-ACORDA-A-PLACA-01 (01/10/2026). Medido no Pro Jank Footy: com
# carga leve e constante, a NVIDIA desce sozinha de 2.505 para 210 MHz em ~5 s
# e leva ~0,5 s para subir de novo, e o quadro que aperta passa do vsync. Com o
# piso de clock travado, 116 quadros acima de 20 ms viraram 24, e 6 trancos
# acima de 50 ms viraram 0. O `system76-power` em Performance não mexe nisso.
#
# O QUE FAZ, por marca (lida no `vendor` de cada `/sys/class/drm/card*`):
#   - NVIDIA: `nvidia-smi -lgc <piso>,<máximo>`, com o piso em 2/3 do máximo
#     (2.070 MHz numa RTX 4060, perto dos 2.010 medidos); devolve com `-rgc`;
#   - AMD: `power_dpm_force_performance_level` em `high`; devolve o de antes;
#   - Intel (i915 e xe): o mínimo de frequência em 2/3 do RP0; devolve o de antes.
# Só o piso sobe: o teto fica o da placa.
#
# A CONTAGEM É POR JOGO. Cada lançamento pede `acordar` com o PID do jogo e,
# quando ele sai, `devolver`. A placa só volta quando nenhum PID pedido está
# vivo, e um PID morto (o jogo que caiu, o restaurador que foi morto junto com
# o grupo) sai da conta na chamada seguinte. O estado mora em /run, que o boot
# limpa junto com o clock travado.
#
# O ROOT VEM DO SUDO, e a regra é estreita como a da ponte do Bluetooth
# (`bt_ponte_privilegiada.sh`): caminho absoluto, os três verbos nomeados, e
# NENHUM curinga. O PID entra pelo STDIN, não por argv: `*` no sudoers casa
# espaço, e casar argumento livre é como NOPASSWD estreito vira largo.
#
# Uso:
#   acordar               — PID do jogo na primeira linha do stdin
#   devolver              — idem
#   estado                — imprime se a placa está acordada e os PIDs vivos
#   regra-sudo <USUARIA>  — imprime o /etc/sudoers.d (não precisa de root)
#
# Fora do root (só as réguas): HEFESTO_PLACA_ESTADO, HEFESTO_PLACA_SYS e
# HEFESTO_PLACA_NVSMI apontam para um lar de mentira. Como root eles são
# ignorados: o sudo já os tira do ambiente, e o script não confia nisso.
set -u

ALVO_INSTALADO=/usr/local/lib/hefesto-dualsense4unix/hefesto_placa_acordada.sh

if [[ "$(id -u)" -eq 0 ]]; then
    ESTADO=/run/hefesto-dualsense4unix/placa
    SYS=/sys
    NVSMI="nvidia-smi"
    export PATH=/usr/sbin:/usr/bin:/sbin:/bin
else
    ESTADO="${HEFESTO_PLACA_ESTADO:-}"
    SYS="${HEFESTO_PLACA_SYS:-/sys}"
    NVSMI="${HEFESTO_PLACA_NVSMI:-nvidia-smi}"
fi

_erro() { printf '%s: %s\n' "${0##*/}" "$*" >&2; }
_recusar() { _erro "$*"; exit 2; }

_exige_estado() {
    [[ -n "${ESTADO}" ]] || { _erro "'$1' requer root"; exit 1; }
    mkdir -p "${ESTADO}/pedidos" 2>/dev/null || { _erro "não consegui criar ${ESTADO}"; exit 1; }
    chmod 700 "${ESTADO}" 2>/dev/null || true
}

#: O PID do jogo, pela primeira linha do stdin. Só dígitos, e só um processo
#: que existe agora.
_pid_do_stdin() {
    local linha=""
    IFS= read -r -t 5 linha || true
    [[ "${linha}" =~ ^[0-9]{1,9}$ ]] || _recusar "PID inválido no stdin: '${linha}'"
    PID="$((10#${linha}))"
}

_vivo() { [[ -d "/proc/$1" ]]; }

_podar() {
    local f
    for f in "${ESTADO}"/pedidos/*; do
        [[ -e "${f}" ]] || continue
        _vivo "${f##*/}" || rm -f "${f}"
    done
}

_ha_pedido() {
    local f
    for f in "${ESTADO}"/pedidos/*; do
        [[ -e "${f}" ]] && return 0
    done
    return 1
}

#: As placas da máquina: «cartão<TAB>vendor». Só os `card<N>` (os conectores
#: `card<N>-DP-1` são do mesmo aparelho).
_placas() {
    local c v
    for c in "${SYS}"/class/drm/card*; do
        [[ "${c##*/}" =~ ^card[0-9]+$ ]] || continue
        v="$(cat "${c}/device/vendor" 2>/dev/null)" || continue
        printf '%s\t%s\n' "${c}" "${v}"
    done
}

_dois_tercos() { printf '%s\n' "$(( $1 * 2 / 3 ))"; }

_acordar_nvidia() {
    command -v "${NVSMI}" >/dev/null 2>&1 || return 0
    local idx maximo
    while IFS=', ' read -r idx maximo; do
        [[ "${idx}" =~ ^[0-9]+$ && "${maximo}" =~ ^[0-9]+$ ]] || continue
        "${NVSMI}" -i "${idx}" -lgc "$(_dois_tercos "${maximo}"),${maximo}" >/dev/null 2>&1 \
            && printf 'nvidia\t%s\n' "${idx}" >>"${ESTADO}/devolver"
    done < <("${NVSMI}" --query-gpu=index,clocks.max.graphics --format=csv,noheader,nounits 2>/dev/null)
}

_acordar_amd() {
    local arq="$1/device/power_dpm_force_performance_level" antes
    [[ -w "${arq}" ]] || return 0
    antes="$(cat "${arq}" 2>/dev/null)" || return 0
    [[ "${antes}" =~ ^[a-z_]+$ ]] || return 0
    printf 'high\n' >"${arq}" 2>/dev/null \
        && printf 'arquivo\t%s\t%s\n' "${arq}" "${antes}" >>"${ESTADO}/devolver"
}

_acordar_intel() {
    local c="$1" minimo rp0 antes alvo
    for minimo in "${c}/gt_min_freq_mhz" "${c}"/device/tile*/gt*/freq0/min_freq; do
        [[ -w "${minimo}" ]] || continue
        rp0="${minimo%min_freq_mhz}RP0_freq_mhz"
        [[ "${minimo}" == */min_freq ]] && rp0="${minimo%min_freq}rp0_freq"
        antes="$(cat "${minimo}" 2>/dev/null)" || continue
        alvo="$(cat "${rp0}" 2>/dev/null)" || continue
        [[ "${antes}" =~ ^[0-9]+$ && "${alvo}" =~ ^[0-9]+$ ]] || continue
        alvo="$(_dois_tercos "${alvo}")"
        (( alvo > antes )) || continue
        printf '%s\n' "${alvo}" >"${minimo}" 2>/dev/null \
            && printf 'arquivo\t%s\t%s\n' "${minimo}" "${antes}" >>"${ESTADO}/devolver"
    done
}

_acordar_a_placa() {
    : >"${ESTADO}/devolver"
    local c v nvidia=0
    while IFS=$'\t' read -r c v; do
        case "${v}" in
            0x10de) nvidia=1 ;;
            0x1002) _acordar_amd "${c}" ;;
            0x8086) _acordar_intel "${c}" ;;
        esac
    done < <(_placas)
    [[ "${nvidia}" -eq 1 ]] && _acordar_nvidia
    : >"${ESTADO}/acordada"
}

_devolver_a_placa() {
    local tipo a b
    while IFS=$'\t' read -r tipo a b; do
        case "${tipo}" in
            nvidia) "${NVSMI}" -i "${a}" -rgc >/dev/null 2>&1 || true ;;
            arquivo)
                case "${a}" in
                    *..*) ;;
                    "${SYS}"/class/drm/card*) printf '%s\n' "${b}" >"${a}" 2>/dev/null || true ;;
                esac
                ;;
        esac
    done <"${ESTADO}/devolver"
    rm -f "${ESTADO}/devolver" "${ESTADO}/acordada"
}

verbo_acordar() {
    _exige_estado acordar
    _pid_do_stdin
    _vivo "${PID}" || _recusar "o processo ${PID} não existe"
    _podar
    : >"${ESTADO}/pedidos/${PID}"
    [[ -e "${ESTADO}/acordada" ]] || _acordar_a_placa
}

verbo_devolver() {
    _exige_estado devolver
    _pid_do_stdin
    rm -f "${ESTADO}/pedidos/${PID}"
    _podar
    _ha_pedido && return 0
    [[ -e "${ESTADO}/acordada" ]] && _devolver_a_placa
    return 0
}

verbo_estado() {
    _exige_estado estado
    _podar
    if [[ -e "${ESTADO}/acordada" ]]; then printf 'acordada'; else printf 'livre'; fi
    local f
    for f in "${ESTADO}"/pedidos/*; do
        [[ -e "${f}" ]] && printf ' %s' "${f##*/}"
    done
    printf '\n'
}

verbo_regra_sudo() {
    local usuaria="${1:-}"
    [[ "${usuaria}" =~ ^[A-Za-z_][A-Za-z0-9._-]{0,31}$ ]] \
        || _recusar "nome de usuária inválido: '${usuaria}'"
    [[ "${usuaria}" != "ALL" ]] \
        || _recusar "'ALL' é palavra reservada do sudoers (concederia a TODO MUNDO), não um nome de usuária"
    cat <<FIM
# /etc/sudoers.d/49-hefesto-placa — gerado por
# ${ALVO_INSTALADO} regra-sudo ${usuaria}
#
# A placa de vídeo acordada enquanto um jogo vive. O sudo é do install e vale
# para o lançador. NÃO editar à mão: o install regrava.
#
# Caminho absoluto, os três verbos nomeados e NENHUM curinga: o PID do jogo
# entra pelo STDIN.
Cmnd_Alias HEFESTO_PLACA = \\
    ${ALVO_INSTALADO} acordar, \\
    ${ALVO_INSTALADO} devolver, \\
    ${ALVO_INSTALADO} estado
${usuaria} ALL=(root) NOPASSWD: HEFESTO_PLACA
FIM
}

case "${1:-}" in
    acordar) verbo_acordar ;;
    devolver) verbo_devolver ;;
    estado) verbo_estado ;;
    regra-sudo) verbo_regra_sudo "${2:-}" ;;
    *) _recusar "verbo desconhecido: '${1:-}' (acordar | devolver | estado | regra-sudo <usuária>)" ;;
esac
