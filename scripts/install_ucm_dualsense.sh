#!/usr/bin/env bash
# install_ucm_dualsense.sh — o perfil UCM do DualSense no cabo (HAPTICA-NATIVA-01).
#
# O caminho de háptica do GE-Proton procura um sink cujo nome tenha
# `Speaker__sink`, e esse nome só existe quando o PipeWire abre a placa do
# controle por UCM. O `alsa-ucm-conf` do Ubuntu 24.04 não conhece o DualSense:
#
#     UCM is not supported for this USB device (… @ USB054c:0ce6)
#
# e editar o `USB-Audio.conf` do pacote é trabalho que o próximo `apt upgrade`
# apaga.
#
# O GANCHO, medido em 18/09/2026 com o pacote intacto (`dpkg -V` limpo): o
# `ucm.conf` procura `conf.d/USB-Audio/<nome longo da placa>.conf` ANTES do
# `USB-Audio.conf`. O nome longo sai do kernel cortado em 79 caracteres, e o
# corte cai dentro do endereço do controlador USB:
#
#     DualSense       "Sony … DualSense Wireless Controller at usb-0000:0c:00."
#     DualSense Edge  "Sony … DualSense Edge Wireless Controller at usb-0000:0"
#
# então UM arquivo por controlador USB da máquina vale para toda porta dele.
# Com o gancho, `alsaucm -c hw:N list _verbs` responde `HiFi`; sem ele, o erro
# acima.
#
# Uso:
#   scripts/install_ucm_dualsense.sh            grava o verbo e os ganchos (root)
#   scripts/install_ucm_dualsense.sh --remover  tira tudo o que este roteiro gravou
#   scripts/install_ucm_dualsense.sh --status   só lê: 0 se todo gancho esperado existe
#
# Vale no próximo replug do controle, ou quando o WirePlumber reinicia.
# Controlador USB ligado depois (uma dock) pede uma nova execução; o doctor
# acusa o DualSense no cabo sem gancho.

set -euo pipefail

RAIZ_UCM="/usr/share/alsa/ucm2"
SYSFS="/sys"
ACAO="aplicar"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --remover) ACAO="remover" ;;
        --status)  ACAO="status" ;;
        # Para os testes: a árvore UCM e o sysfs de mentira.
        --raiz-ucm) RAIZ_UCM="$2"; shift ;;
        --sysfs)    SYSFS="$2"; shift ;;
        *) printf '[ucm] opção desconhecida: %s\n' "$1" >&2; exit 2 ;;
    esac
    shift
done

readonly MARCADOR="hefesto-ucm-dualsense"
readonly FABRICANTE="Sony Interactive Entertainment"
readonly MODELOS=("DualSense Wireless Controller" "DualSense Edge Wireless Controller")
# O `longname` da placa é um char[80] no kernel (sound/core): 79 e o NUL.
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

# O nome do controlador USB de cada barramento: o pai do root hub no sysfs
# (`0000:0c:00.3` num PCI, `vhci_hcd.0` no usbip). É o que o kernel escreve
# depois de `at usb-` no nome longo da placa.
controladores() {
    local rh
    for rh in "${SYSFS}"/bus/usb/devices/usb*; do
        [[ -e "${rh}" ]] || continue
        basename "$(dirname "$(readlink -f "${rh}")")"
    done | sort -u
}

# Um nome de arquivo por linha. O kernel monta `usb-<controlador>-<porta>`
# (usb_make_path), e o corte tem de cair antes da porta: se o controlador tiver
# nome curto, o nome longo continua com a porta e a velocidade, que só existem
# na hora do plugue — esse controlador fica de fora, e o roteiro diz qual.
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

# A pergunta é ao `findmnt`, pelo ponto de montagem que CONTÉM a árvore UCM:
# `-w` não serve, porque sem root o diretório nunca é gravável e é o sudo
# que escreve. Sem `findmnt` (util-linux), a resposta é "não sei", e o roteiro
# segue como antes.
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
    # DISTRO IMUTÁVEL (Silverblue, Kinoite, Bazzite, SteamOS): o /usr é só de
    # leitura, o `install -D` falha, e o install mandava rodar de novo um
    # roteiro que ali nunca vai funcionar. O que vale nessas distros é o UCM
    # que ela mesma traz — dizer isso e sair limpo é a resposta honesta.
    if usr_so_leitura; then
        info "${RAIZ_UCM} está num sistema de arquivos só de leitura (distro imutável) — nada gravado; vale o perfil UCM que a própria distro traz"
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
    # O gancho de um controlador que saiu da máquina não serve a ninguém.
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
