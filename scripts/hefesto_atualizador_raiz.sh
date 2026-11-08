#!/usr/bin/env bash
set -u

ALVO_INSTALADO=/usr/local/lib/hefesto-dualsense4unix/atualizador-raiz
REPO_DO_MANGOHUD=flightlessmango/MangoHud
GRUPOS="nvidia kernel sistema"

if [[ "$(id -u)" -eq 0 ]]; then
    export PATH=/usr/sbin:/usr/bin:/sbin:/bin
    export DEBIAN_FRONTEND=noninteractive
    CACHE=/var/cache/hefesto-dualsense4unix
    SRC=/usr/src
    MODULOS=/lib/modules
    ENTRADAS=/boot/efi/loader/entries
    CASA_DA_USUARIA=""
    DONO=root
    API="https://api.github.com/repos/${REPO_DO_MANGOHUD}/releases/latest"
else
    CACHE="${HEFESTO_ATUALIZADOR_CACHE:-}"
    SRC="${HEFESTO_ATUALIZADOR_SRC:-/usr/src}"
    MODULOS="${HEFESTO_ATUALIZADOR_MODULOS:-/lib/modules}"
    ENTRADAS="${HEFESTO_ATUALIZADOR_ENTRADAS:-/boot/efi/loader/entries}"
    CASA_DA_USUARIA="${HEFESTO_ATUALIZADOR_CASA:-}"
    DONO="${HEFESTO_ATUALIZADOR_DONO:-root}"
    API="${HEFESTO_ATUALIZADOR_API:-}"
fi

_erro() { printf '%s: %s\n' "${0##*/}" "$*" >&2; }
_recusar() { _erro "$*"; exit 2; }

_exige_raiz() {
    [[ -n "${CACHE}" ]] || { _erro "'$1' requer root"; exit 1; }
}

_apt() {
    apt-get -y -o APT::Status-Fd=1 \
        -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold "$@"
}

_instalados_que_casam() {
    dpkg-query -W -f '${Package}\t${db:Status-Abbrev}\n' 2>/dev/null \
        | awk -F'\t' -v re="$1" '$2 ~ /^ii/ && $1 ~ re { print $1 }'
}

_pacotes_do_grupo() {
    case "$1" in
        nvidia) _instalados_que_casam '^(nvidia-|libnvidia-|xserver-xorg-video-nvidia)' ;;
        kernel) _instalados_que_casam '^(linux-system76|linux-generic|linux-image-generic|linux-headers-generic)$' ;;
    esac
}

_grupo_valido() {
    local g
    for g in ${GRUPOS}; do
        [[ "$1" == "${g}" ]] && return 0
    done
    _recusar "grupo desconhecido: '$1' (${GRUPOS// / | })"
}

verbo_apt_lista() {
    _exige_raiz apt-lista
    apt-get -q -o APT::Status-Fd=1 update
}

_apt_do_grupo() {
    local grupo="$1"; shift
    _grupo_valido "${grupo}"
    if [[ "${grupo}" == "sistema" ]]; then
        _apt "$@" full-upgrade
        return
    fi
    local -a pacotes
    mapfile -t pacotes < <(_pacotes_do_grupo "${grupo}")
    if [[ "${#pacotes[@]}" -eq 0 ]]; then
        printf 'nada instalado no grupo %s\n' "${grupo}"
        return 0
    fi
    _apt "$@" install --only-upgrade "${pacotes[@]}"
}

verbo_apt_baixar() { _exige_raiz apt-baixar; _apt_do_grupo "${1:-}" -d; }
verbo_apt_instalar() { _exige_raiz apt-instalar; _apt_do_grupo "${1:-}"; }
verbo_apt_limpar() { _exige_raiz apt-limpar; _apt autoremove --purge; }

_fonte_e_do_root() {
    local pasta="$1" fora
    fora="$(find "${pasta}" \( ! -user "${DONO}" -o -perm /022 \) -print -quit 2>/dev/null)"
    [[ -z "${fora}" ]]
}

_kernels_com_build() {
    local k
    for k in "${MODULOS}"/*; do
        [[ -e "${k}/build" ]] && printf '%s\n' "${k##*/}"
    done
}

verbo_dkms_refazer() {
    _exige_raiz dkms-refazer
    command -v dkms >/dev/null 2>&1 || _recusar "dkms ausente"
    local pasta nome ver kernel mudou=0 falhou=0
    for pasta in "${SRC}"/hefesto-*-*; do
        [[ -d "${pasta}" && -f "${pasta}/dkms.conf" ]] || continue
        if ! _fonte_e_do_root "${pasta}"; then
            _erro "o fonte em ${pasta} não é só do root: rode o install"
            falhou=1
            continue
        fi
        nome="${pasta##*/}"
        ver="${nome##*-}"
        nome="${nome%-*}"
        while IFS= read -r kernel; do
            [[ -n "${kernel}" ]] || continue
            if dkms status -m "${nome}" -v "${ver}" -k "${kernel}" 2>/dev/null | grep -q ': installed'; then
                continue
            fi
            printf 'refazendo %s %s para %s\n' "${nome}" "${ver}" "${kernel}"
            if dkms install -m "${nome}" -v "${ver}" -k "${kernel}"; then
                mudou=1
            else
                _erro "${nome} não compilou para ${kernel}"
                falhou=1
            fi
        done < <(_kernels_com_build)
    done
    if [[ "${mudou}" -eq 1 ]] && command -v update-initramfs >/dev/null 2>&1; then
        update-initramfs -u -k all >/dev/null 2>&1 || _erro "o initramfs não se refez"
    fi
    [[ "${falhou}" -eq 0 ]]
}

_casa_da_usuaria() {
    if [[ -n "${CASA_DA_USUARIA}" ]]; then
        printf '%s' "${CASA_DA_USUARIA}"
        return
    fi
    local usuaria="${SUDO_USER:-}"
    [[ "${usuaria}" =~ ^[A-Za-z_][A-Za-z0-9._-]{0,31}$ && "${usuaria}" != "root" ]] \
        || _recusar "não sei de quem é o download (SUDO_USER: '${usuaria}')"
    getent passwd "${usuaria}" | cut -d: -f6
}

_digest_publicado() {
    local nome="$1"
    curl -fsSL --max-time 30 -H 'Accept: application/vnd.github+json' "${API}" \
        | python3 -I -c '
import json, sys
nome = sys.argv[1]
for ativo in json.load(sys.stdin).get("assets", []):
    if ativo.get("name") == nome and str(ativo.get("digest", "")).startswith("sha256:"):
        print(ativo["digest"].split(":", 1)[1])
        break
' "${nome}"
}

_instalar_o_tar_do_mangohud() {
    local tar="$1" pasta setup
    pasta="$(mktemp -d "${CACHE}/mangohud/.instalar.XXXXXX")" || return 1
    if ! tar -C "${pasta}" --no-same-owner -xzf "${tar}"; then
        rm -rf "${pasta}"
        _erro "o pacote do MangoHud não abriu"
        return 1
    fi
    setup="$(find "${pasta}" -maxdepth 2 -name mangohud-setup.sh -type f -print -quit)"
    if [[ -z "${setup}" ]]; then
        rm -rf "${pasta}"
        _erro "o pacote do MangoHud não traz o mangohud-setup.sh"
        return 1
    fi
    (cd "${setup%/*}" && bash ./mangohud-setup.sh install) </dev/null
    local rc=$?
    rm -rf "${pasta}"
    return "${rc}"
}

verbo_mangohud_instalar() {
    _exige_raiz mangohud-instalar
    local casa origem nome esperado obtido
    casa="$(_casa_da_usuaria)"
    [[ -n "${casa}" && -d "${casa}" ]] || _recusar "a casa de quem baixou não existe"
    local -a achados
    mapfile -t achados < <(find "${casa}/.cache/hefesto-dualsense4unix/atualizador/mangohud" \
        -maxdepth 1 -type f -name 'MangoHud-*.tar.gz' 2>/dev/null)
    [[ "${#achados[@]}" -eq 1 ]] || _recusar "esperava um MangoHud baixado, achei ${#achados[@]}"
    origem="${achados[0]}"
    nome="${origem##*/}"
    [[ "${nome}" =~ ^MangoHud-[A-Za-z0-9._-]+\.tar\.gz$ ]] || _recusar "nome estranho: ${nome}"
    install -d -m 700 "${CACHE}/mangohud"
    cat <"${origem}" >"${CACHE}/mangohud/novo.tar.gz" || _recusar "não li ${origem}"
    esperado="$(_digest_publicado "${nome}")"
    [[ "${esperado}" =~ ^[0-9a-f]{64}$ ]] || { rm -f "${CACHE}/mangohud/novo.tar.gz"; _recusar "a soma publicada de ${nome} não veio"; }
    obtido="$(sha256sum "${CACHE}/mangohud/novo.tar.gz" | cut -d' ' -f1)"
    if [[ "${obtido}" != "${esperado}" ]]; then
        rm -f "${CACHE}/mangohud/novo.tar.gz"
        _recusar "o sha256 de ${nome} não é o publicado"
    fi
    _instalar_o_tar_do_mangohud "${CACHE}/mangohud/novo.tar.gz" || exit 1
    [[ -f "${CACHE}/mangohud/atual.tar.gz" ]] && mv -f "${CACHE}/mangohud/atual.tar.gz" "${CACHE}/mangohud/anterior.tar.gz"
    mv -f "${CACHE}/mangohud/novo.tar.gz" "${CACHE}/mangohud/atual.tar.gz"
    printf 'MangoHud instalado: %s\n' "${nome}"
}

verbo_mangohud_voltar() {
    _exige_raiz mangohud-voltar
    [[ -f "${CACHE}/mangohud/anterior.tar.gz" ]] || _recusar "sem versão anterior do MangoHud"
    _instalar_o_tar_do_mangohud "${CACHE}/mangohud/anterior.tar.gz" || exit 1
    mv -f "${CACHE}/mangohud/anterior.tar.gz" "${CACHE}/mangohud/volta.tar.gz"
    [[ -f "${CACHE}/mangohud/atual.tar.gz" ]] && mv -f "${CACHE}/mangohud/atual.tar.gz" "${CACHE}/mangohud/anterior.tar.gz"
    mv -f "${CACHE}/mangohud/volta.tar.gz" "${CACHE}/mangohud/atual.tar.gz"
    printf 'MangoHud de volta à versão anterior\n'
}

verbo_kernel_anterior() {
    _exige_raiz kernel-anterior
    local entrada
    entrada="$(find "${ENTRADAS}" -maxdepth 1 -name '*oldkern.conf' -printf '%f\n' 2>/dev/null | head -n 1)"
    [[ -n "${entrada}" ]] || _recusar "sem a entrada do kernel anterior no carregador"
    command -v bootctl >/dev/null 2>&1 || _recusar "bootctl ausente"
    bootctl set-default "${entrada}" && printf 'o próximo início usa %s\n' "${entrada}"
}

verbo_regra_sudo() {
    local usuaria="${1:-}" g
    [[ "${usuaria}" =~ ^[A-Za-z_][A-Za-z0-9._-]{0,31}$ ]] \
        || _recusar "nome de usuária inválido: '${usuaria}'"
    [[ "${usuaria}" != "ALL" && "${usuaria}" != "root" ]] \
        || _recusar "'${usuaria}' não é um nome de usuária para a regra"
    printf '# /etc/sudoers.d/49-hefesto-atualizador — gerado por\n'
    printf '# %s regra-sudo %s\n' "${ALVO_INSTALADO}" "${usuaria}"
    printf '#\n# O atualizador do Hefesto sem pedir senha. NÃO editar à mão: o install regrava.\n'
    printf '# Caminho absoluto, cada verbo com o argumento exato e NENHUM curinga.\n'
    printf 'Cmnd_Alias HEFESTO_ATUALIZADOR = \\\n'
    printf '    %s apt-lista, \\\n' "${ALVO_INSTALADO}"
    for g in ${GRUPOS}; do
        printf '    %s apt-baixar %s, \\\n' "${ALVO_INSTALADO}" "${g}"
        printf '    %s apt-instalar %s, \\\n' "${ALVO_INSTALADO}" "${g}"
    done
    printf '    %s apt-limpar, \\\n' "${ALVO_INSTALADO}"
    printf '    %s dkms-refazer, \\\n' "${ALVO_INSTALADO}"
    printf '    %s mangohud-instalar, \\\n' "${ALVO_INSTALADO}"
    printf '    %s mangohud-voltar, \\\n' "${ALVO_INSTALADO}"
    printf '    %s kernel-anterior\n' "${ALVO_INSTALADO}"
    printf '%s ALL=(root) NOPASSWD: HEFESTO_ATUALIZADOR\n' "${usuaria}"
}

[[ $# -le 2 ]] || _recusar "argumentos demais"

case "${1:-}" in
    apt-lista) [[ $# -eq 1 ]] || _recusar "apt-lista não leva argumento"; verbo_apt_lista ;;
    apt-baixar) [[ $# -eq 2 ]] || _recusar "apt-baixar <grupo>"; verbo_apt_baixar "$2" ;;
    apt-instalar) [[ $# -eq 2 ]] || _recusar "apt-instalar <grupo>"; verbo_apt_instalar "$2" ;;
    apt-limpar) [[ $# -eq 1 ]] || _recusar "apt-limpar não leva argumento"; verbo_apt_limpar ;;
    dkms-refazer) [[ $# -eq 1 ]] || _recusar "dkms-refazer não leva argumento"; verbo_dkms_refazer ;;
    mangohud-instalar) [[ $# -eq 1 ]] || _recusar "mangohud-instalar não leva argumento"; verbo_mangohud_instalar ;;
    mangohud-voltar) [[ $# -eq 1 ]] || _recusar "mangohud-voltar não leva argumento"; verbo_mangohud_voltar ;;
    kernel-anterior) [[ $# -eq 1 ]] || _recusar "kernel-anterior não leva argumento"; verbo_kernel_anterior ;;
    regra-sudo) verbo_regra_sudo "${2:-}" ;;
    *) _recusar "verbo desconhecido: '${1:-}' (apt-lista | apt-baixar <grupo> | apt-instalar <grupo> | apt-limpar | dkms-refazer | mangohud-instalar | mangohud-voltar | kernel-anterior | regra-sudo <usuária>)" ;;
esac
