# shellcheck shell=bash

_dkms_src_root() { printf '%s' "${HEFESTO_DKMS_SRC_ROOT:-/usr/src}"; }
_dkms_modules_root() { printf '%s' "${HEFESTO_DKMS_MODULES_ROOT:-/lib/modules}"; }
_dkms_tree_root() { printf '%s' "${HEFESTO_DKMS_TREE:-/var/lib/dkms}"; }
_dkms_boot_root() { printf '%s' "${HEFESTO_DKMS_BOOT_ROOT:-/boot}"; }
_dkms_kernel_alvo() { printf '%s' "${HEFESTO_DKMS_KERNEL:-$(uname -r)}"; }
_dkms_initramfs_path() {
    printf '%s' "${HEFESTO_INITRAMFS_PATH:-/boot/initrd.img-$(_dkms_kernel_alvo)}"
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

cabecalhos_do_kernel_no_pacman() {
    local _kver="${1:-$(_dkms_kernel_alvo)}" _dono=""
    _dono="$(pacman -Qqo "/usr/lib/modules/${_kver}/vmlinuz" 2>/dev/null | head -n 1)"
    printf '%s-headers\n' "${_dono:-linux}"
}

_dkms_como_instalar() {
    local _o_que="$1" _kver="${2:-$(_dkms_kernel_alvo)}"
    if command -v apt-get >/dev/null 2>&1; then
        if [[ "${_o_que}" == "dkms" ]]; then printf 'sudo apt install dkms'
        else printf 'sudo apt install linux-headers-%s' "${_kver}"; fi
    elif command -v dnf >/dev/null 2>&1; then
        if [[ "${_o_que}" == "dkms" ]]; then printf 'sudo dnf install dkms'
        else printf 'sudo dnf install kernel-devel-%s' "${_kver}"; fi
    elif command -v pacman >/dev/null 2>&1; then
        if [[ "${_o_que}" == "dkms" ]]; then printf 'sudo pacman -S --needed dkms'
        else printf 'sudo pacman -S --needed %s' "$(cabecalhos_do_kernel_no_pacman "${_kver}")"; fi
    else
        if [[ "${_o_que}" == "dkms" ]]; then printf 'instale o dkms pela sua distribuição'
        else printf 'instale os cabeçalhos do kernel %s pela sua distribuição' "${_kver}"; fi
    fi
}

_dkms_efivars_root() {
    if [[ "${EUID}" -ne 0 && -n "${HEFESTO_EFIVARS_ROOT:-}" ]]; then
        printf '%s' "${HEFESTO_EFIVARS_ROOT}"
    else
        printf '%s' /sys/firmware/efi/efivars
    fi
}

_dkms_sys_module() {
    if [[ "${EUID}" -ne 0 && -n "${HEFESTO_SYS_MODULE:-}" ]]; then
        printf '%s' "${HEFESTO_SYS_MODULE}"
    else
        printf '%s' /sys/module
    fi
}

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

_dkms_valor_no_framework() {
    local _campo="$1" _conf _linha _valor=""
    # shellcheck disable=SC2086
    for _conf in ${HEFESTO_DKMS_FRAMEWORK_CONFS:-/etc/dkms/framework.conf /etc/dkms/framework.conf.d/*.conf}; do
        [[ -r "${_conf}" ]] || continue
        while IFS= read -r _linha || [[ -n "${_linha}" ]]; do
            _linha="${_linha#"${_linha%%[![:space:]]*}"}"
            [[ "${_linha}" == "${_campo}="* ]] && _valor="${_linha#"${_campo}"=}"
        done < "${_conf}"
    done
    printf '%s' "${_valor//[\"\']/}"
}

_dkms_mok_pub() {
    if [[ -n "${HEFESTO_DKMS_MOK_PUB:-}" ]]; then
        printf '%s' "${HEFESTO_DKMS_MOK_PUB}"
        return 0
    fi
    local _chave _cert
    _chave="$(_dkms_valor_no_framework mok_signing_key)"
    _cert="$(_dkms_valor_no_framework mok_certificate)"
    if [[ -z "${_chave}" && "$(_dkms_familia_da_distro)" == ubuntu* ]]; then
        printf '%s' "/var/lib/shim-signed/mok/MOK.der"
        return 0
    fi
    printf '%s' "${_cert:-/var/lib/dkms/mok.pub}"
}

_dkms_mok_chave_privada() {
    local _chave
    _chave="$(_dkms_valor_no_framework mok_signing_key)"
    if [[ -z "${_chave}" && "$(_dkms_familia_da_distro)" == ubuntu* ]]; then
        printf '%s' "/var/lib/shim-signed/mok/MOK.priv"
        return 0
    fi
    printf '%s' "${_chave:-/var/lib/dkms/mok.key}"
}

_dkms_leitura_da_chave_privada() {
    local _chave _pasta _lido=""
    _chave="$(_dkms_mok_chave_privada)"
    if [[ "${_chave}" == pkcs11:* || -s "${_chave}" ]]; then
        printf 'presente'
        return 0
    fi
    _pasta="${_chave}"
    while [[ "${_pasta}" == /?* ]]; do
        _pasta="${_pasta%/*}"
        [[ -n "${_pasta}" ]] || _pasta="/"
        if [[ -e "${_pasta}" ]]; then
            if [[ -d "${_pasta}" && -x "${_pasta}" ]]; then
                printf 'falta'
                return 0
            fi
            break
        fi
    done
    _lido="$(sudo -n sh -c 'if [ -s "$1" ]; then echo presente; else echo falta; fi' sh "${_chave}" 2>/dev/null)" || true
    case "${_lido}" in
        presente | falta) printf '%s' "${_lido}" ;;
        *) printf 'nao-sei' ;;
    esac
}

dkms_kernel_assina_modulo() {
    local _k="${1:-$(_dkms_kernel_alvo)}" _config _rc
    for _config in "$(_dkms_modules_root)/${_k}/build/.config" "$(_dkms_boot_root)/config-${_k}"; do
        [[ -r "${_config}" ]] || continue
        _rc=0
        grep -q '^CONFIG_MODULE_SIG_HASH=' "${_config}" 2>/dev/null || _rc=$?
        [[ "${_rc}" -eq 0 ]] && return 0
        [[ "${_rc}" -eq 1 ]] && return 1
    done
    return 2
}

dkms_estado_da_chave_privada() {
    local _assina=0
    if dkms_secure_boot_ligado; then
        dkms_kernel_assina_modulo "${1:-}" || _assina=$?
    else
        _assina=1
    fi
    if [[ "${_assina}" -eq 1 ]]; then
        printf 'dispensada'
    else
        _dkms_leitura_da_chave_privada
    fi
}

dkms_sem_a_chave_privada() { [[ "$(dkms_estado_da_chave_privada "${1:-}")" == "falta" ]]; }
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

_dkms_srcversion_do_modulo() {
    modinfo -F srcversion "$1" 2>/dev/null || true
}

_dkms_carregado_e_da_casa() {
    local _nome="$1" _carregado _arquivo
    [[ -n "${_nome}" ]] || return 1
    _carregado="$(cat "$(_dkms_sys_module)/${_nome//-/_}/srcversion" 2>/dev/null || true)"
    [[ -n "${_carregado}" ]] || return 1
    _arquivo="$(modinfo -F filename "${_nome}" 2>/dev/null)" || return 1
    dkms_ko_da_casa "${_arquivo}" || return 1
    [[ "$(_dkms_srcversion_do_modulo "${_arquivo}")" == "${_carregado}" ]]
}

_dkms_arquivo_traz_a_chave() {
    python3 - "$1" "$2" <<'PYEOF'
import sys
try:
    chave = open(sys.argv[1], "rb").read()
    lista = open(sys.argv[2], "rb").read()
except OSError:
    raise SystemExit(2)
raise SystemExit(0 if chave and chave in lista else 1)
PYEOF
}

_dkms_mok_pedido() {
    printf '%s' "$(_dkms_efivars_root)/MokNew-605dab50-e046-4300-abb6-3dd810dd8b23"
}

_dkms_leitura_da_chave() {
    local _pub _lista _resposta _leu=0 _rc _pedida=0
    _pub="$(_dkms_mok_pub)"
    if [[ ! -r "${_pub}" || ! -s "${_pub}" ]]; then
        printf 'nao-lida'
        return 0
    fi
    if command -v mokutil >/dev/null 2>&1; then
        _resposta="$(mokutil --test-key "${_pub}" 2>&1 || true)"
        if [[ "${_resposta}" == *"already enrolled"* ]]; then
            printf 'inscrita'
            return 0
        fi
        [[ "${_resposta}" == *"enrollment request"* ]] && _pedida=1
        [[ "${_resposta}" == *"is not enrolled"* ]] && _leu=1
    fi
    while IFS= read -r _lista; do
        [[ -r "${_lista}" ]] || continue
        _rc=0
        _dkms_arquivo_traz_a_chave "${_pub}" "${_lista}" || _rc=$?
        if [[ "${_rc}" -eq 0 ]]; then
            printf 'inscrita'
            return 0
        fi
        [[ "${_rc}" -eq 1 ]] && _leu=1
    done < <(_dkms_mok_listas)
    if [[ "${_pedida}" -eq 0 && -r "$(_dkms_mok_pedido)" ]]; then
        _dkms_arquivo_traz_a_chave "${_pub}" "$(_dkms_mok_pedido)" && _pedida=1
    fi
    if [[ "${_pedida}" -eq 1 ]]; then
        printf 'pedida'
    elif [[ "${_leu}" -eq 1 ]]; then
        printf 'lida-fora'
    else
        printf 'nao-lida'
    fi
    return 0
}

_dkms_leitura_lida() {
    if [[ -n "${_DKMS_LEITURA:-}" ]]; then
        printf '%s' "${_DKMS_LEITURA}"
    else
        _dkms_leitura_da_chave
    fi
}

dkms_ler_a_chave() {
    [[ -n "${_DKMS_LEITURA:-}" ]] || _DKMS_LEITURA="$(_dkms_leitura_da_chave)"
    DKMS_ESTADO="$(dkms_estado_da_chave "${1:-}")"
}

dkms_estado_da_chave() {
    local _leitura
    _leitura="$(_dkms_leitura_lida)"
    case "${_leitura}" in
        lida-fora)
            if _dkms_carregado_e_da_casa "${1:-}"; then printf 'nao-sei'; else printf 'fora'; fi
            ;;
        nao-lida) printf 'nao-sei' ;;
        *) printf '%s' "${_leitura}" ;;
    esac
    return 0
}

DKMS_MODULOS_DA_CASA="hid-nintendo uhid hid-playstation usb_f_hid rtw88_usb"

dkms_ler_a_chave_da_casa() {
    local _m _primeiro=""
    DKMS_ESTADO="" DKMS_MODULO=""
    for _m in ${DKMS_MODULOS_DA_CASA}; do
        dkms_ler_a_chave "${_m}"
        [[ -n "${_primeiro}" ]] || _primeiro="${_m}"
        if [[ "${DKMS_ESTADO}" != "nao-sei" ]]; then
            DKMS_MODULO="${_m}"
            return 0
        fi
    done
    DKMS_MODULO="${_primeiro}"
    return 0
}

dkms_chave_mok_inscrita() { [[ "$(dkms_estado_da_chave "${1:-}")" == "inscrita" ]]; }

dkms_chave_mok_fora() { [[ "$(dkms_estado_da_chave "${1:-}")" == "fora" ]]; }

dkms_sem_a_chave_garantida() {
    dkms_secure_boot_ligado || return 1
    ! dkms_chave_mok_inscrita "${1:-}"
}

_dkms_passo_que_gera_a_chave() {
    if [[ "$(_dkms_mok_pub)" == /var/lib/shim-signed/* ]]; then
        printf 'gere a chave (sudo update-secureboot-policy --new-key), '
    else
        printf 'gere a chave (sudo dkms generate_mok), '
    fi
}

dkms_passo_da_mok() {
    local _pub; _pub="$(_dkms_mok_pub)"
    [[ -s "${_pub}" ]] || _dkms_passo_que_gera_a_chave
    printf 'inscreva-a com sudo mokutil --import %s (ele pede uma senha), reinicie, escolha «Enroll MOK» na tela azul que aparece antes do sistema, digite a mesma senha, e rode ./install.sh de novo' "${_pub}"
}

dkms_passo_da_chave_privada() {
    local _pub; _pub="$(_dkms_mok_pub)"
    printf 'devolva a chave privada a %s e rode ./install.sh de novo; se a chave privada se perdeu, tire a pública %s do lugar, %sinscreva a nova com sudo mokutil --import %s, reinicie, escolha «Enroll MOK» na tela azul que aparece antes do sistema, digite a mesma senha, e rode ./install.sh de novo' \
        "$(_dkms_mok_chave_privada)" "${_pub}" "$(_dkms_passo_que_gera_a_chave)" "${_pub}"
}

dkms_texto_da_chave_privada() {
    printf 'Secure Boot ligado e a chave do DKMS está inscrita, mas falta a chave privada do DKMS (%s) para assinar: sem a privada o DKMS geraria uma chave nova, fora da MOK, e o kernel recusaria o módulo no boot. Os módulos do Hefesto não são instalados nem trocados, e o que já estava instalado continua como estava. Para seguir: %s' \
        "$(_dkms_mok_chave_privada)" "$(dkms_passo_da_chave_privada)"
}

dkms_passo_da_inscricao_pedida() {
    printf 'reinicie o computador, escolha «Enroll MOK» na tela azul que aparece antes do sistema, digite a senha que você deu ao pedir a inscrição, e rode ./install.sh de novo'
}

dkms_efeito_sem_a_chave() {
    printf 'o DualSense e o controle Nintendo funcionam, sem as curas, os nós de movimento e do touchpad e as luzes; o microfone pelo rádio fica desligado; o pad virtual cai para a reserva; o dongle Wi-Fi USB da Realtek fica sem driver, porque o kernel não traz um'
}

_dkms_como_instalar_o_mokutil() {
    if command -v apt-get >/dev/null 2>&1; then printf 'sudo apt install mokutil'
    elif command -v dnf >/dev/null 2>&1; then printf 'sudo dnf install mokutil'
    elif command -v pacman >/dev/null 2>&1; then printf 'sudo pacman -S --needed mokutil'
    else printf 'pelo gerenciador de pacotes da sua distribuição'; fi
}

_dkms_alguma_lista_se_le() {
    local _lista
    while IFS= read -r _lista; do
        [[ -r "${_lista}" ]] && return 0
    done < <(_dkms_mok_listas)
    return 1
}

dkms_passo_para_ler_a_chave() {
    local _pub; _pub="$(_dkms_mok_pub)"
    if [[ ! -e "${_pub}" || ( -r "${_pub}" && ! -s "${_pub}" ) ]]; then
        dkms_passo_da_mok
    elif [[ ! -r "${_pub}" ]]; then
        printf 'deixe a chave %s legível para quem roda o install (a chave é pública) e rode ./install.sh de novo' "${_pub}"
    elif ! command -v mokutil >/dev/null 2>&1 && ! _dkms_alguma_lista_se_le; then
        printf 'instale o mokutil (%s) e rode ./install.sh de novo' "$(_dkms_como_instalar_o_mokutil)"
    else
        local _antes=""
        command -v mokutil >/dev/null 2>&1 || _antes="$(printf 'instale o mokutil (%s) e ' "$(_dkms_como_instalar_o_mokutil)")"
        printf '%sconfira se a chave está inscrita com mokutil --test-key %s («already enrolled» é inscrita, «is not enrolled» é fora) e rode ./install.sh de novo; só com a chave fora o install diz o passo da inscrição' "${_antes}" "${_pub}"
    fi
}

dkms_chave_e_o_passo() {
    local _estado; _estado="$(dkms_estado_da_chave "${1:-}")"
    if [[ "${_estado}" == "pedida" ]]; then
        printf 'Secure Boot ligado, e a inscrição da chave do DKMS espera o reinício para ser confirmada: o driver do Hefesto não se instala nem se troca até lá. Para confirmar: %s' "$(dkms_passo_da_inscricao_pedida)"
    elif [[ "${_estado}" == "fora" ]]; then
        printf 'Secure Boot ligado e a chave do DKMS não está inscrita, e sem a chave o driver do Hefesto não se instala: %s' "$(dkms_passo_da_mok)"
    else
        printf 'Secure Boot ligado, e não consegui ler a chave do DKMS: sem saber se está inscrita, o driver do Hefesto não se instala nem se troca. Para ler a chave: %s' "$(dkms_passo_para_ler_a_chave)"
    fi
}

dkms_titulo_da_chave() {
    local _estado; _estado="$(dkms_estado_da_chave "${1:-}")"
    if [[ "${_estado}" == "pedida" ]]; then
        printf 'Secure Boot ligado, e a inscrição da chave do DKMS espera o reinício para ser confirmada'
    elif [[ "${_estado}" == "fora" ]]; then
        printf 'Secure Boot ligado, e a chave do DKMS não está inscrita'
    else
        printf 'Secure Boot ligado, e não consegui ler a chave do DKMS para saber se está inscrita'
    fi
}

_dkms_frase_do_carregado() {
    local _m _nomes=() _n
    for _m in "${1:-}" ${DKMS_MODULOS_DA_CASA}; do
        [[ -n "${_m}" ]] || continue
        [[ " ${_nomes[*]:-} " == *" ${_m} "* ]] && continue
        _dkms_carregado_e_da_casa "${_m}" && _nomes+=("${_m}")
    done
    _n="${#_nomes[@]}"
    if [[ "${_n}" -eq 1 ]]; then
        printf ' O módulo %s do Hefesto carregado agora segue como está.' "${_nomes[0]}"
    elif [[ "${_n}" -gt 1 ]]; then
        printf ' Os módulos %s do Hefesto carregados agora seguem como estão.' "${_nomes[*]}"
    fi
    return 0
}

dkms_modulos_sem_a_chave() {
    local _estado; _estado="$(dkms_estado_da_chave "${1:-}")"
    if [[ "${_estado}" == "pedida" ]]; then
        printf 'Até a inscrição se confirmar, os módulos do Hefesto não são instalados nem trocados.'
    elif [[ "${_estado}" == "fora" ]]; then
        printf 'Os módulos do Hefesto não vão ser instalados, porque o kernel os recusaria no boot. Os que já estavam instalados saem e o driver de fábrica volta.%s' "$(_dkms_frase_do_carregado "${1:-}")"
    else
        printf 'Sem saber, os módulos do Hefesto não são instalados nem trocados.%s' "$(_dkms_frase_do_carregado "${1:-}")"
    fi
}

dkms_passo_se_a_chave_falta() {
    dkms_secure_boot_ligado || return 0
    dkms_ler_a_chave "${1:-}"
    if [[ "${DKMS_ESTADO}" == "inscrita" ]]; then
        dkms_sem_a_chave_privada || return 0
        dkms_texto_da_chave_privada
        return 0
    fi
    dkms_chave_e_o_passo "${1:-}"
}

dkms_aviso_do_doctor() {
    dkms_secure_boot_ligado || return 0
    dkms_ler_a_chave_da_casa
    case "${DKMS_ESTADO}" in
        inscrita) return 0 ;;
        pedida)
            printf 'Secure Boot ligado, e a inscrição da chave do DKMS espera o reinício para ser confirmada, e há módulos do Hefesto instalados neste kernel — a atualização não os tira nem os troca. Para confirmar: %s' "$(dkms_passo_da_inscricao_pedida)"
            ;;
        fora)
            printf 'Secure Boot ligado, a chave do DKMS não está inscrita, e há módulos do Hefesto instalados neste kernel — o kernel os RECUSA no boot e o driver de fábrica vale no lugar (a atualização tira esses módulos): %s.%s Para ganhar as curas: %s' "$(dkms_efeito_sem_a_chave)" "$(_dkms_frase_do_carregado)" "$(dkms_passo_da_mok)"
            ;;
        *)
            printf 'Secure Boot ligado, e não consegui ler a chave do DKMS para saber se está inscrita, e há módulos do Hefesto instalados neste kernel — a atualização não os tira nem os troca.%s Para ler a chave: %s' "$(_dkms_frase_do_carregado)" "$(dkms_passo_para_ler_a_chave)"
            ;;
    esac
}

dkms_efeito_do_estado() {
    if [[ "$(dkms_estado_da_chave "${1:-}")" == "fora" ]]; then
        printf 'Sem as curas: %s.' "$(dkms_efeito_sem_a_chave)"
    else
        printf 'O que já estava instalado continua como estava.'
    fi
}

dkms_passo_da_chave() {
    local _estado; _estado="$(dkms_estado_da_chave "${1:-}")"
    if [[ "${_estado}" == "pedida" ]]; then
        printf 'Para confirmar a inscrição: %s.' "$(dkms_passo_da_inscricao_pedida)"
    elif [[ "${_estado}" == "fora" ]]; then
        printf 'Para ganhar as curas: %s.' "$(dkms_passo_da_mok)"
    else
        printf 'Para ler a chave: %s.' "$(dkms_passo_para_ler_a_chave)"
    fi
}

: "${_DKMS_SB_WARNED:=0}"
dkms_aviso_da_chave_dito() { _DKMS_SB_WARNED=1; }

: "${_DKMS_PRIVADA_WARNED:=0}"

dkms_avisa_a_chave_privada_uma_vez() {
    [[ "${_DKMS_PRIVADA_WARNED}" -eq 1 ]] && return 0
    _DKMS_PRIVADA_WARNED=1
    _dkms_warn "$(dkms_texto_da_chave_privada)"
}

dkms_warn_secureboot_once() {
    [[ "${_DKMS_SB_WARNED}" -eq 1 ]] && return 0
    dkms_secure_boot_ligado || return 0
    dkms_ler_a_chave "${1:-}"
    [[ "${DKMS_ESTADO}" == "inscrita" ]] && return 0
    dkms_aviso_da_chave_dito
    _dkms_warn "$(dkms_titulo_da_chave "${1:-}"). $(dkms_modulos_sem_a_chave "${1:-}") $(dkms_efeito_do_estado "${1:-}") $(dkms_passo_da_chave "${1:-}")"
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
        _DKMS_INITRAMFS_ARGV=(update-initramfs -u -k "$(_dkms_kernel_alvo)")
    elif command -v dracut >/dev/null 2>&1; then
        _DKMS_INITRAMFS_ARGV=(dracut --force --kver "$(_dkms_kernel_alvo)")
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

dkms_arquivo_do_veredito() {
    printf '%s/%s/%s/fonte-%s.txt' "$(_dkms_tree_root)" "$1" "$2" "$3"
}

dkms_veredito_do_fonte() {
    local _arquivo _estado _frase
    _arquivo="$(dkms_arquivo_do_veredito "$1" "$2" "$3")"
    [[ -r "${_arquivo}" ]] || return 0
    { IFS= read -r _estado && IFS= read -r _frase; } < "${_arquivo}" || true
    [[ -n "${_estado:-}" ]] && printf '%s\t%s\n' "${_estado}" "${_frase:-}"
    return 0
}

_dkms_esquecer_o_veredito_que_falhou() {
    local _arquivo _veredito
    _veredito="$(dkms_veredito_do_fonte "$1" "$2" "$3")"
    case "${_veredito%%$'\t'*}" in
        "" | cache | fabrica) return 0 ;;
    esac
    _arquivo="$(dkms_arquivo_do_veredito "$1" "$2" "$3")"
    sudo rm -f "${_arquivo}" "${_arquivo%.txt}.tar" || true
}

_dkms_arquivo_do_modulo() {
    if [[ -n "${HEFESTO_DKMS_KERNEL:-}" ]]; then
        modinfo -k "${HEFESTO_DKMS_KERNEL}" -F filename "$1" 2>/dev/null
    else
        modinfo -F filename "$1" 2>/dev/null
    fi
}

dkms_ko_da_casa() {
    local _ko="$1" _link
    [[ -f "${_ko}" ]] || return 1
    for _link in "$(_dkms_tree_root)"/hefesto-*/kernel-*; do
        cmp -s "${_link}/module/${_ko##*/}" "${_ko}" && return 0
    done
    return 1
}

dkms_modulo_da_casa() {
    local _path
    _path="$(_dkms_arquivo_do_modulo "$1")" || return 1
    dkms_ko_da_casa "${_path}"
}

_dkms_marca_de_assinatura() {
    python3 - "$1" <<'PYEOF'
import sys

MARCA = b"~Module signature appended~\n"
caminho = sys.argv[1]
try:
    with open(caminho, "rb") as arquivo:
        dados = arquivo.read()
    if caminho.endswith(".xz"):
        import lzma
        dados = lzma.decompress(dados)
    elif caminho.endswith(".gz"):
        import gzip
        dados = gzip.decompress(dados)
    elif caminho.endswith(".zst"):
        import shutil
        import subprocess
        zstd = shutil.which("zstd")
        if not zstd:
            raise SystemExit(2)
        dados = subprocess.run(
            [zstd, "-dc", caminho], capture_output=True, check=True, timeout=60
        ).stdout
except BaseException:
    raise SystemExit(2)
raise SystemExit(0 if dados.endswith(MARCA) else 3)
PYEOF
}

dkms_modulo_da_casa_sem_assinatura() {
    local _path _rc=0
    _path="$(_dkms_arquivo_do_modulo "$1")" || return 1
    dkms_ko_da_casa "${_path}" || return 1
    _dkms_marca_de_assinatura "${_path}" || _rc=$?
    [[ "${_rc}" -eq 3 ]]
}

_dkms_serie_da_chave_publica() {
    python3 - "$(_dkms_mok_pub)" <<'PYEOF'
import base64
import re
import sys


def corpo(dados, i):
    tag = dados[i]
    tamanho = dados[i + 1]
    i += 2
    if tamanho & 0x80:
        n = tamanho & 0x7F
        tamanho = int.from_bytes(dados[i:i + n], "big")
        i += n
    if tamanho <= 0 or i + tamanho > len(dados):
        raise ValueError("tamanho fora do arquivo")
    return tag, i, tamanho


try:
    with open(sys.argv[1], "rb") as arquivo:
        dados = arquivo.read()
    if dados.lstrip().startswith(b"-----BEGIN"):
        achado = re.search(rb"-----BEGIN [^-]+-----(.*?)-----END", dados, re.S)
        dados = base64.b64decode(achado.group(1))
    tag, i, _ = corpo(dados, 0)
    if tag != 0x30:
        raise ValueError("não é um certificado")
    tag, i, _ = corpo(dados, i)
    if tag != 0x30:
        raise ValueError("sem o corpo do certificado")
    tag, inicio, tamanho = corpo(dados, i)
    if tag == 0xA0:
        tag, inicio, tamanho = corpo(dados, inicio + tamanho)
    if tag != 0x02:
        raise ValueError("sem o número de série")
    print(dados[inicio:inicio + tamanho].hex())
except BaseException:
    raise SystemExit(2)
PYEOF
}

_dkms_serie_normalizada() {
    local _s="${1//:/}"
    _s="${_s,,}"
    while [[ "${_s}" == 00* ]]; do _s="${_s:2}"; done
    printf '%s' "${_s}"
}

dkms_modulo_da_casa_de_outra_chave() {
    local _path _do_modulo _da_chave
    _path="$(_dkms_arquivo_do_modulo "$1")" || return 1
    dkms_ko_da_casa "${_path}" || return 1
    _dkms_marca_de_assinatura "${_path}" || return 1
    _do_modulo="$(modinfo -F sig_key "${_path}" 2>/dev/null | head -n 1)" || return 1
    _da_chave="$(_dkms_serie_da_chave_publica 2>/dev/null)" || return 1
    _do_modulo="$(_dkms_serie_normalizada "${_do_modulo}")"
    _da_chave="$(_dkms_serie_normalizada "${_da_chave}")"
    [[ "${_do_modulo}" =~ ^[0-9a-f]+$ && "${_da_chave}" =~ ^[0-9a-f]+$ ]] || return 1
    [[ "${_do_modulo}" != "${_da_chave}" ]]
}

DKMS_MARCAS_DO_USB_F_HID=(get_report_sized get_report_refuses)

dkms_usb_f_hid_marcas_que_faltam() {
    local _pasta="${1:-/sys/module}/usb_f_hid/parameters" _marca _valor _faltam=()
    for _marca in "${DKMS_MARCAS_DO_USB_F_HID[@]}"; do
        _valor="$(cat "${_pasta}/${_marca}" 2>/dev/null || true)"
        [[ "${_valor}" == "Y" || "${_valor}" == "1" ]] || _faltam+=("${_marca}")
    done
    printf '%s\n' "${_faltam[*]}"
}

dkms_module_loaded() {
    [[ -d "/sys/module/${1//-/_}" ]]
}

_dkms_initramfs_desatualizado() {
    local _ko _img
    _ko="$(_dkms_arquivo_do_modulo "$1")" || return 0
    _img="$(_dkms_initramfs_path)"
    [[ -f "${_ko}" && -f "${_img}" ]] || return 0
    [[ "${_ko}" -nt "${_img}" ]]
}

_dkms_status_texto() {
    sudo dkms status "$@" 2>/dev/null || true
}

dkms_fontes_so_do_root() {
    local _raiz _pasta _falhou=0
    _raiz="$(_dkms_src_root)"
    for _pasta in "${_raiz}"/hefesto-*; do
        [[ -d "${_pasta}" && ! -L "${_pasta}" ]] || continue
        if ! sudo chown -R root:root "${_pasta}" || ! sudo chmod -R go-w "${_pasta}"; then
            _dkms_warn "o fonte em ${_pasta} não ficou só do root — o kernel novo compilaria código que outro escreve"
            _falhou=1
        fi
    done
    return "${_falhou}"
}

_dkms_kernels_com_o_modulo() {
    local _status _linha
    _status="$(_dkms_status_texto "$1/$2")"
    while IFS= read -r _linha; do
        [[ "${_linha}" =~ :\ (installed|built) ]] || continue
        _linha="${_linha%%: ${BASH_REMATCH[1]}*}"
        _linha="${_linha%, *}"
        printf '%s\n' "${_linha##*, }"
    done <<< "${_status}"
}

dkms_devolver_o_driver_de_fabrica() {
    local _pkg="$1" _ver="$2" _built="${3:-}" _kver _tirou=0
    while IFS= read -r _kver; do
        [[ -n "${_kver}" ]] || continue
        if sudo dkms remove "${_pkg}/${_ver}" -k "${_kver}" >/dev/null 2>&1; then
            sudo depmod -a "${_kver}" >/dev/null 2>&1 || true
            _dkms_log "${_pkg} tirado do kernel ${_kver}: o driver de fábrica volta no próximo carregamento"
            _tirou=1
            [[ -n "${_built}" && "${_kver}" == "$(_dkms_kernel_alvo)" ]] \
                && dkms_mark_initramfs_stale "${_built}"
        else
            _dkms_warn "dkms remove falhou p/ ${_pkg}/${_ver} no kernel ${_kver} — o módulo da casa segue nesse kernel e o kernel o recusa no boot; rode: sudo dkms remove ${_pkg}/${_ver} -k ${_kver}"
        fi
    done < <(_dkms_kernels_com_o_modulo "${_pkg}" "${_ver}")
    [[ "${_tirou}" -eq 1 ]] || _dkms_log "${_pkg} pulado: Secure Boot sem a chave do DKMS inscrita — o driver de fábrica continua"
    return 0
}

dkms_install_patched_module() {
    local _pkg="$1" _ver="$2" _src="$3" _built="$4"
    local _kver _srcdst _dkms_lic _refazer=0
    _kver="${HEFESTO_DKMS_KERNEL:-$(uname -r)}"
    _srcdst="$(_dkms_src_root)/${_pkg}-${_ver}"

    if ! command -v dkms >/dev/null 2>&1; then
        _dkms_warn "dkms ausente — pulando ${_pkg} (módulo in-tree continua); cure com: $(_dkms_como_instalar dkms)"
        return 0
    fi
    if dkms_secure_boot_ligado; then
        dkms_ler_a_chave "${_built}"
        if [[ "${DKMS_ESTADO}" != "inscrita" ]]; then
            dkms_warn_secureboot_once "${_built}"
            case "${DKMS_ESTADO}" in
                fora) dkms_devolver_o_driver_de_fabrica "${_pkg}" "${_ver}" "${_built}" ;;
                pedida) _dkms_log "${_pkg} pulado: a inscrição da chave do DKMS espera o reinício, então nada se instala nem se tira" ;;
                *) _dkms_log "${_pkg} pulado: não li a chave do DKMS, então nada se instala nem se tira" ;;
            esac
            return 0
        fi
        case "$(dkms_estado_da_chave_privada "${_kver}")" in
            falta)
                dkms_avisa_a_chave_privada_uma_vez
                _dkms_log "${_pkg} pulado: falta a chave privada do DKMS, então nada se instala nem se tira"
                return 0
                ;;
            nao-sei)
                _dkms_log "${_pkg} pulado: não li a chave privada do DKMS ($(_dkms_mok_chave_privada)), então nada se instala nem se tira"
                return 0
                ;;
        esac
    fi
    if dkms_secure_boot_ligado && dkms_kernel_assina_modulo "${_kver}"; then
        if dkms_modulo_da_casa_sem_assinatura "${_built}"; then
            _refazer=1
            _dkms_log "${_pkg}: o módulo instalado está sem assinatura e a chave do DKMS está inscrita; refazendo para o kernel aceitá-lo"
        elif dkms_modulo_da_casa_de_outra_chave "${_built}"; then
            _refazer=1
            _dkms_log "${_pkg}: o módulo instalado foi assinado por outra chave que não a do DKMS de agora; refazendo para o kernel aceitá-lo"
        fi
    fi
    if [[ ! -e "$(_dkms_modules_root)/${_kver}/build" ]]; then
        _dkms_warn "headers do kernel ${_kver} ausentes — pulando ${_pkg} (módulo in-tree continua); cure com: $(_dkms_como_instalar cabecalhos "${_kver}")"
        return 0
    fi
    if [[ ! -f "${_src}/dkms.conf" ]]; then
        _dkms_warn "source DKMS incompleto em ${_src} (sem dkms.conf) — pulando ${_pkg}"
        return 0
    fi

    if [[ -d "${_srcdst}" ]] && sudo diff -rq -x LICENSES "${_src}" "${_srcdst}" >/dev/null 2>&1; then
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

    if ! sudo chown -R root:root "${_srcdst}" || ! sudo chmod -R go-w "${_srcdst}"; then
        _dkms_warn "o source em ${_srcdst} não ficou só do root — pulando ${_pkg} (in-tree continua)"
        return 0
    fi

    if [[ -z "$(_dkms_status_texto "${_pkg}/${_ver}")" ]]; then
        if ! sudo dkms add "${_pkg}/${_ver}"; then
            _dkms_warn "dkms add falhou p/ ${_pkg}/${_ver} — in-tree continua"
            return 0
        fi
    fi

    if [[ "${_refazer}" -eq 1 ]] || [[ ! "$(_dkms_status_texto "${_pkg}/${_ver}" -k "${_kver}")" =~ (built|installed) ]]; then
        local _rc_build=0 _veredito _forca=()
        [[ "${_refazer}" -eq 1 ]] && _forca=(--force)
        _dkms_esquecer_o_veredito_que_falhou "${_pkg}" "${_ver}" "${_kver}"
        sudo dkms build "${_pkg}/${_ver}" -k "${_kver}" ${_forca[@]+"${_forca[@]}"} || _rc_build=$?
        if [[ "${_rc_build}" -ne 0 ]]; then
            _veredito="$(dkms_veredito_do_fonte "${_pkg}" "${_ver}" "${_kver}")"
            case "${_veredito%%$'\t'*}" in
                "" | cache | fabrica)
                    _dkms_warn "dkms build FALHOU p/ ${_pkg}/${_ver} no kernel ${_kver} — módulo in-tree continua (fail-safe); log: $(_dkms_tree_root)/${_pkg}/${_ver}/build/make.log"
                    ;;
                *)
                    _dkms_warn "${_veredito#*$'\t'}"
                    ;;
            esac
            return 0
        fi
    fi

    if [[ "${_refazer}" -eq 1 ]] \
        || [[ "$(_dkms_status_texto "${_pkg}/${_ver}" -k "${_kver}")" != *installed* ]] \
        || [[ "$(_dkms_status_texto "${_pkg}/${_ver}" -k "${_kver}")" == *"between built and installed"* ]]; then
        if ! sudo dkms install "${_pkg}/${_ver}" -k "${_kver}" --force; then
            _dkms_warn "dkms install falhou p/ ${_pkg}/${_ver} — in-tree continua"
            return 0
        fi
    fi

    if dkms_modulo_da_casa "${_built}"; then
        _dkms_log "ok: modinfo resolve ${_built} p/ o que o DKMS instalou (vence o in-tree no próximo carregamento)"
        if [[ -n "${HEFESTO_DKMS_KERNEL:-}" && ! -f "$(_dkms_initramfs_path)" ]]; then
            _dkms_log "o initramfs de ${_kver} ainda não nasceu: ele já nasce com o ${_built}"
        elif _dkms_initramfs_desatualizado "${_built}"; then
            dkms_mark_initramfs_stale "${_built}"
        else
            _dkms_log "initramfs já mais novo que o ${_built} do DKMS — sem regeneração"
        fi
    else
        _dkms_warn "modinfo NÃO aponta ${_built} p/ o que o DKMS instalou — confira /etc/depmod.d e rode: sudo depmod -a"
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
