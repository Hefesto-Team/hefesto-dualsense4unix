# shellcheck shell=bash

_dkms_src_root() { printf '%s' "${HEFESTO_DKMS_SRC_ROOT:-/usr/src}"; }
_dkms_modules_root() { printf '%s' "${HEFESTO_DKMS_MODULES_ROOT:-/lib/modules}"; }
_dkms_initramfs_path() {
    printf '%s' "${HEFESTO_INITRAMFS_PATH:-/boot/initrd.img-$(uname -r)}"
}

_dkms_licenses_dir() {
    if [[ -n "${HEFESTO_DKMS_LICENSES_DIR:-}" ]]; then
        printf '%s' "${HEFESTO_DKMS_LICENSES_DIR}"
        return 0
    fi
    local _libdir _cand
    _libdir="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)" || return 0
    for _cand in \
        "${_libdir}/../LICENSES" \
        "/usr/share/hefesto-dualsense4unix/dkms/LICENSES" \
        "/app/share/hefesto-dualsense4unix/dkms/LICENSES" \
    ; do
        if [[ -d "${_cand}" ]]; then
            (cd "${_cand}" && pwd)
            return 0
        fi
    done
    return 0
}

_dkms_log() { printf '      %s\n' "$*"; }

_dkms_warn() {
    if [[ "$(type -t warn 2>/dev/null)" == "function" ]]; then
        warn "$*"
    else
        printf '      aviso: %s\n' "$*"
    fi
}

_dkms_efivars_root() { printf '%s' "${HEFESTO_EFIVARS_ROOT:-/sys/firmware/efi/efivars}"; }

_dkms_familia_da_distro() {
    local _os="${HEFESTO_OS_RELEASE:-/etc/os-release}"
    [[ -r "${_os}" ]] || return 0
    (
        ID="" ID_LIKE=""
        # shellcheck disable=SC1090
        . "${_os}" >/dev/null 2>&1 || true
        if [[ "${ID}" == "ubuntu" ]]; then
            printf '%s' "${ID}"
        elif [[ -n "${ID_LIKE}" ]]; then
            printf '%s' "${ID_LIKE}"
        else
            printf '%s' "${ID}"
        fi
    )
}

_dkms_mok_pub() {
    if [[ -n "${HEFESTO_DKMS_MOK_PUB:-}" ]]; then
        printf '%s' "${HEFESTO_DKMS_MOK_PUB}"
        return 0
    fi
    local _conf _linha _chave="" _cert=""
    # shellcheck disable=SC2086
    for _conf in ${HEFESTO_DKMS_FRAMEWORK_CONFS:-/etc/dkms/framework.conf /etc/dkms/framework.conf.d/*.conf}; do
        [[ -r "${_conf}" ]] || continue
        while IFS= read -r _linha || [[ -n "${_linha}" ]]; do
            _linha="${_linha#"${_linha%%[![:space:]]*}"}"
            case "${_linha}" in
                mok_signing_key=*) _chave="${_linha#mok_signing_key=}" ;;
                mok_certificate=*) _cert="${_linha#mok_certificate=}" ;;
            esac
        done < "${_conf}"
    done
    _chave="${_chave//[\"\']/}"
    _cert="${_cert//[\"\']/}"
    if [[ -z "${_chave}" && "$(_dkms_familia_da_distro)" == ubuntu* ]]; then
        printf '%s' "/var/lib/shim-signed/mok/MOK.der"
        return 0
    fi
    printf '%s' "${_cert:-/var/lib/dkms/mok.pub}"
}
_dkms_mok_listas() {
    local _l
    # shellcheck disable=SC2086
    for _l in ${HEFESTO_MOK_LISTAS:-/sys/firmware/efi/mok-variables/MokListRT /sys/firmware/efi/efivars/MokListRT-605dab50-e046-4300-abb6-3dd810dd8b23}; do
        printf '%s\n' "${_l}"
    done
}

dkms_secure_boot_ligado() {
    local _var _ultimo
    for _var in "$(_dkms_efivars_root)"/SecureBoot-*; do
        [[ -r "${_var}" ]] || continue
        _ultimo="$(od -An -tu1 "${_var}" 2>/dev/null | awk 'NF { v = $NF } END { print v }')"
        [[ "${_ultimo}" == "1" ]]
        return
    done
    return 1
}

dkms_chave_mok_inscrita() {
    local _pub _lista _resposta
    _pub="$(_dkms_mok_pub)"
    [[ -r "${_pub}" && -s "${_pub}" ]] || return 1
    if command -v mokutil >/dev/null 2>&1; then
        _resposta="$(mokutil --test-key "${_pub}" 2>&1 || true)"
        [[ "${_resposta}" == *"already enrolled"* ]] && return 0
    fi
    while IFS= read -r _lista; do
        [[ -r "${_lista}" ]] || continue
        python3 - "${_pub}" "${_lista}" <<'PYEOF' && return 0
import sys
chave = open(sys.argv[1], "rb").read()
lista = open(sys.argv[2], "rb").read()
raise SystemExit(0 if chave and chave in lista else 1)
PYEOF
    done < <(_dkms_mok_listas)
    return 1
}

dkms_passo_da_mok() {
    local _pub; _pub="$(_dkms_mok_pub)"
    if [[ ! -s "${_pub}" && "${_pub}" == /var/lib/shim-signed/* ]]; then
        printf 'gere a chave (sudo update-secureboot-policy --new-key), '
    elif [[ ! -s "${_pub}" ]]; then
        printf 'gere a chave (sudo dkms generate_mok), '
    fi
    printf 'inscreva-a com sudo mokutil --import %s (ele pede uma senha), reinicie, escolha «Enroll MOK» na tela azul que aparece antes do sistema, digite a mesma senha, e rode ./install.sh de novo' "${_pub}"
}

: "${_DKMS_SB_WARNED:=0}"
dkms_warn_secureboot_once() {
    [[ "${_DKMS_SB_WARNED}" -eq 1 ]] && return 0
    dkms_secure_boot_ligado || return 0
    dkms_chave_mok_inscrita && return 0
    _DKMS_SB_WARNED=1
    _dkms_warn "Secure Boot ligado e a chave do DKMS não está inscrita: os módulos desta casa NÃO vão ser instalados, porque o kernel os recusaria no boot e o DualSense (e o controle Nintendo, e o Wi-Fi USB) ficaria sem driver nenhum. Os drivers de fábrica ficam: o DualSense funciona, sem as curas, e o microfone pelo rádio fica desligado. Para ganhar as curas: $(dkms_passo_da_mok)."
    return 0
}

: "${_DKMS_INITRAMFS_STALE:=0}"
: "${_DKMS_INITRAMFS_DONE:=0}"
: "${_DKMS_INITRAMFS_MODS:=}"

dkms_mark_initramfs_stale() {
    _DKMS_INITRAMFS_STALE=1
    case " ${_DKMS_INITRAMFS_MODS} " in
        *" $1 "*) : ;;
        *) _DKMS_INITRAMFS_MODS="${_DKMS_INITRAMFS_MODS} $1" ;;
    esac
    return 0
}

_DKMS_INITRAMFS_ARGV=()
_dkms_initramfs_detect() {
    _DKMS_INITRAMFS_ARGV=()
    if command -v update-initramfs >/dev/null 2>&1; then
        _DKMS_INITRAMFS_ARGV=(update-initramfs -u -k "$(uname -r)")
    elif command -v dracut >/dev/null 2>&1; then
        _DKMS_INITRAMFS_ARGV=(dracut --force --kver "$(uname -r)")
    elif command -v mkinitcpio >/dev/null 2>&1; then
        _DKMS_INITRAMFS_ARGV=(mkinitcpio -P)
    fi
}

dkms_flush_initramfs() {
    local _cmd _log_file
    [[ "${_DKMS_INITRAMFS_STALE}" -eq 1 ]] || return 0
    [[ "${_DKMS_INITRAMFS_DONE}" -eq 1 ]] && return 0
    _DKMS_INITRAMFS_DONE=1

    _dkms_initramfs_detect
    if [[ "${#_DKMS_INITRAMFS_ARGV[@]}" -eq 0 ]]; then
        _dkms_warn "nenhum gerador de initramfs encontrado (update-initramfs/dracut/mkinitcpio) — o initramfs NÃO foi regenerado; se ele contiver uma cópia de${_DKMS_INITRAMFS_MODS}, o boot seguirá carregando a versão antiga. Regenere pela ferramenta da sua distro."
        return 0
    fi
    _cmd="${_DKMS_INITRAMFS_ARGV[*]}"

    _dkms_log "regenerando o initramfs (${_cmd}) — sem isto o boot carrega a cópia antiga de${_DKMS_INITRAMFS_MODS}"
    _log_file="$(mktemp -t hefesto-initramfs-XXXXXX.log 2>/dev/null)" || _log_file=""
    if sudo "${_DKMS_INITRAMFS_ARGV[@]}" </dev/null >"${_log_file:-/dev/null}" 2>&1; then
        [[ -n "${_log_file}" ]] && rm -f "${_log_file}"
        _dkms_log "initramfs regenerado ($(_dkms_initramfs_path))"
        return 0
    fi
    _dkms_warn "'${_cmd}' FALHOU — o initramfs continua com a cópia antiga de${_DKMS_INITRAMFS_MODS} e o próximo boot carregará o módulo velho (os module params do hefesto ficam invisíveis e o kernel descarta a conf de options inteira). Rode à mão: sudo ${_cmd}"
    if [[ -n "${_log_file}" && -s "${_log_file}" ]]; then
        _dkms_warn "últimas linhas do gerador: $(tail -n 3 "${_log_file}" | tr '\n' ' | ')"
        rm -f "${_log_file}"
    fi
    return 0
}

dkms_pkg_version() {
    local _src="$1" _fallback="${2:-1.0.0}" _ver=""
    if [[ -f "${_src}/dkms.conf" ]]; then
        _ver="$(sed -n 's/^PACKAGE_VERSION="\(.*\)"$/\1/p' "${_src}/dkms.conf")"
    fi
    printf '%s' "${_ver:-${_fallback}}"
}

dkms_module_from_updates() {
    local _path
    _path="$(modinfo -F filename "$1" 2>/dev/null)" || return 1
    [[ "${_path}" == */updates/dkms/* ]]
}

dkms_module_loaded() {
    [[ -d "/sys/module/${1//-/_}" ]]
}

_dkms_initramfs_desatualizado() {
    local _ko _img
    _ko="$(modinfo -F filename "$1" 2>/dev/null)" || return 0
    _img="$(_dkms_initramfs_path)"
    [[ -f "${_ko}" && -f "${_img}" ]] || return 0
    [[ "${_ko}" -nt "${_img}" ]]
}

_dkms_status_texto() {
    sudo dkms status "$@" 2>/dev/null || true
}

dkms_install_patched_module() {
    local _pkg="$1" _ver="$2" _src="$3" _built="$4"
    local _kver _srcdst _dkms_lic
    _kver="$(uname -r)"
    _srcdst="$(_dkms_src_root)/${_pkg}-${_ver}"

    if ! command -v dkms >/dev/null 2>&1; then
        _dkms_warn "dkms ausente — pulando ${_pkg} (módulo in-tree continua); cure com: sudo apt install dkms"
        return 0
    fi
    if [[ ! -e "$(_dkms_modules_root)/${_kver}/build" ]]; then
        _dkms_warn "headers do kernel ${_kver} ausentes — pulando ${_pkg} (módulo in-tree continua); cure com: sudo apt install linux-headers-${_kver}"
        return 0
    fi
    if [[ ! -f "${_src}/dkms.conf" ]]; then
        _dkms_warn "source DKMS incompleto em ${_src} (sem dkms.conf) — pulando ${_pkg}"
        return 0
    fi
    if dkms_secure_boot_ligado && ! dkms_chave_mok_inscrita; then
        dkms_warn_secureboot_once
        _dkms_log "${_pkg} pulado: Secure Boot sem a chave do DKMS inscrita — o driver de fábrica continua"
        return 0
    fi

    if [[ -d "${_srcdst}" ]] && sudo diff -rq -x patch -x LICENSES "${_src}" "${_srcdst}" >/dev/null 2>&1; then
        _dkms_log "source ${_pkg}-${_ver} já sincronizado em ${_srcdst}"
    else
        sudo dkms remove "${_pkg}/${_ver}" --all >/dev/null 2>&1 || true
        if ! sudo rm -rf "${_srcdst}"; then
            _dkms_warn "não consegui limpar ${_srcdst} — pulando ${_pkg} (in-tree continua)"
            return 0
        fi
        if ! sudo install -d "${_srcdst}" || ! sudo cp -a "${_src}/." "${_srcdst}/"; then
            _dkms_warn "falha copiando source p/ ${_srcdst} — pulando ${_pkg} (in-tree continua)"
            return 0
        fi
        sudo rm -rf "${_srcdst}/patch" || true
    fi

    _dkms_lic="$(_dkms_licenses_dir)"
    if [[ -n "${_dkms_lic}" && -d "${_srcdst}" ]]; then
        if sudo diff -rq "${_dkms_lic}" "${_srcdst}/LICENSES" >/dev/null 2>&1; then
            :
        elif sudo install -d "${_srcdst}/LICENSES" 2>/dev/null \
            && sudo cp -a "${_dkms_lic}/." "${_srcdst}/LICENSES/" 2>/dev/null; then
            _dkms_log "licenças de terceiros copiadas p/ ${_srcdst}/LICENSES"
        else
            _dkms_log "não consegui copiar LICENSES p/ ${_srcdst} (o módulo segue)"
        fi
    fi

    if [[ -z "$(_dkms_status_texto "${_pkg}/${_ver}")" ]]; then
        if ! sudo dkms add "${_pkg}/${_ver}"; then
            _dkms_warn "dkms add falhou p/ ${_pkg}/${_ver} — in-tree continua"
            return 0
        fi
    fi

    if [[ ! "$(_dkms_status_texto "${_pkg}/${_ver}" -k "${_kver}")" =~ (built|installed) ]]; then
        local _rc_build=0
        sudo dkms build "${_pkg}/${_ver}" -k "${_kver}" || _rc_build=$?
        if [[ "${_rc_build}" -eq 77 ]]; then
            _dkms_log "${_pkg} não é para o kernel ${_kver} (BUILD_EXCLUSIVE_KERNEL do dkms.conf) — o in-tree assume, como o pino manda"
            return 0
        fi
        if [[ "${_rc_build}" -ne 0 ]]; then
            _dkms_warn "dkms build FALHOU p/ ${_pkg}/${_ver} no kernel ${_kver} — módulo in-tree continua (fail-safe); log: /var/lib/dkms/${_pkg}/${_ver}/${_kver}/${_arch:-x86_64}/log/make.log"
            return 0
        fi
    fi

    if [[ "$(_dkms_status_texto "${_pkg}/${_ver}" -k "${_kver}")" != *installed* ]]; then
        if ! sudo dkms install "${_pkg}/${_ver}" -k "${_kver}"; then
            _dkms_warn "dkms install falhou p/ ${_pkg}/${_ver} — in-tree continua"
            return 0
        fi
    fi

    if dkms_module_from_updates "${_built}"; then
        _dkms_log "ok: modinfo resolve ${_built} p/ updates/dkms (vence o in-tree no próximo carregamento)"
        if _dkms_initramfs_desatualizado "${_built}"; then
            dkms_mark_initramfs_stale "${_built}"
        else
            _dkms_log "initramfs já mais novo que o ${_built} de updates/dkms — sem regeneração"
        fi
    else
        _dkms_warn "modinfo NÃO aponta ${_built} p/ updates/dkms — confira /etc/depmod.d e rode: sudo depmod -a"
    fi
    return 0
}

dkms_remove_patched_module() {
    local _pkg="$1" _ver="$2" _built="${3:-}" _srcdst
    _srcdst="$(_dkms_src_root)/${_pkg}-${_ver}"
    if command -v dkms >/dev/null 2>&1 &&
        [[ -n "$(_dkms_status_texto "${_pkg}/${_ver}")" ]]; then
        if ! sudo dkms remove "${_pkg}/${_ver}" --all; then
            _dkms_warn "dkms remove falhou p/ ${_pkg}/${_ver} — registro DKMS e ${_srcdst} PRESERVADOS; remova à mão: sudo dkms remove ${_pkg}/${_ver} --all && sudo rm -rf ${_srcdst}"
            return 0
        fi
    fi
    if ! sudo rm -rf "${_srcdst}"; then
        _dkms_warn "não consegui apagar ${_srcdst} — remova à mão: sudo rm -rf ${_srcdst}"
    fi
    sudo depmod -a >/dev/null 2>&1 || true
    [[ -n "${_built}" ]] && dkms_mark_initramfs_stale "${_built}"
    _dkms_log "${_pkg} removido — o módulo in-tree volta a valer no próximo boot"
    return 0
}
