# shellcheck shell=bash
# scripts/dkms_lib.sh — infra DKMS genérica do hefesto-dualsense4unix (Onda T).
#
# Reuso previsto: hid-nintendo (Onda T) e rtw88 (Onda W). É uma BIBLIOTECA
# (source, não executável): quem chama é o install.sh/uninstall.sh, que já
# têm sudo adquirido (acquire_sudo) e as funções warn/ok — se ausentes, há
# fallback local.
#
# Contrato (regras invioláveis embutidas):
#   - FAIL-SAFE: qualquer falha vira aviso + return 0 — o módulo in-tree
#     continua e o install NUNCA aborta por causa do DKMS;
#   - NUNCA carrega/descarrega módulo (modprobe/rmmod PROIBIDOS aqui):
#     ativação é responsabilidade do chamador e a mensagem é sempre
#     "vale no próximo boot" (substituir módulo carregado derrubaria os
#     controles em uso);
#   - IDEMPOTENTE: re-rodar não quebra, não duplica, e re-sincroniza o
#     source se os assets mudaram (bump de PACKAGE_VERSION ou patch novo).
#
# API:
#   dkms_install_patched_module <pkg> <versão> <src_dir> <builtname>
#       ex.: dkms_install_patched_module hefesto-hid-nintendo 1.0.0 \
#                "${ROOT_DIR}/assets/dkms/hid-nintendo" hid-nintendo
#   dkms_remove_patched_module <pkg> <versão>
#   dkms_module_from_updates <builtname>   # 0 sse modinfo resolve p/ updates/dkms
#   dkms_module_loaded <sysname>           # 0 sse /sys/module/<sysname> existe

# Raízes parametrizáveis (defaults == sistema real). Existem como COSTURA DE
# TESTE: a suíte precisa exercitar o caminho feliz/idempotente/build-falho de
# ponta a ponta sem root (aponta as duas p/ diretórios temporários + stubs de
# sudo/dkms). Em produção NUNCA são definidas — os defaults valem.
_dkms_src_root() { printf '%s' "${HEFESTO_DKMS_SRC_ROOT:-/usr/src}"; }
_dkms_modules_root() { printf '%s' "${HEFESTO_DKMS_MODULES_ROOT:-/lib/modules}"; }

_dkms_log() { printf '      %s\n' "$*"; }

_dkms_warn() {
    if [[ "$(type -t warn 2>/dev/null)" == "function" ]]; then
        warn "$*"
    else
        printf '      aviso: %s\n' "$*"
    fi
}

# PKG-1 (auditoria 21/07): com Secure Boot enforcing e a chave MOK do DKMS
# não enrolada, o kernel RECUSA o .ko de updates/dkms no boot e NÃO cai no
# in-tree (modules.dep aponta um caminho só) — a máquina ficaria sem
# hid-nintendo/WiFi. Best-effort, idempotente (avisa 1x por execução), NUNCA
# aborta o install. Só fala se mokutil existe e reporta SB habilitado.
_DKMS_SB_WARNED=0
dkms_warn_secureboot_once() {
    [[ "${_DKMS_SB_WARNED}" -eq 1 ]] && return 0
    command -v mokutil >/dev/null 2>&1 || return 0
    if mokutil --sb-state 2>/dev/null | grep -qi 'SecureBoot enabled'; then
        _DKMS_SB_WARNED=1
        _dkms_warn "Secure Boot ATIVO: o módulo DKMS só CARREGA se a chave MOK do dkms estiver enrolada (se não estiver, o kernel recusa o .ko no boot e NÃO volta ao in-tree sozinho). Se um controle Nintendo/WiFi sumir após o próximo boot, enrole a chave: sudo mokutil --import /var/lib/dkms/mok.pub (nvidia-DKMS funcionando indica que já está resolvido)."
    fi
    return 0
}

# PKG-3 (auditoria 21/07): a versão do pacote é o PACKAGE_VERSION do dkms.conf
# (fonte da verdade — o install-host-udev.sh já parseava assim). Fallback ao
# literal recebido para NUNCA quebrar o caminho (dkms.conf ilegível/ausente).
dkms_pkg_version() {
    local _src="$1" _fallback="${2:-1.0.0}" _ver=""
    if [[ -f "${_src}/dkms.conf" ]]; then
        _ver="$(sed -n 's/^PACKAGE_VERSION="\(.*\)"$/\1/p' "${_src}/dkms.conf")"
    fi
    printf '%s' "${_ver:-${_fallback}}"
}

# O módulo que o modprobe resolveria HOJE vem de updates/dkms (vence o in-tree)?
dkms_module_from_updates() {
    local _path
    _path="$(modinfo -F filename "$1" 2>/dev/null)" || return 1
    [[ "${_path}" == */updates/dkms/* ]]
}

# O módulo está CARREGADO agora? (usado p/ decidir a mensagem de ativação)
dkms_module_loaded() {
    [[ -d "/sys/module/${1//-/_}" ]]
}

dkms_install_patched_module() {
    local _pkg="$1" _ver="$2" _src="$3" _built="$4"
    local _kver _srcdst
    _kver="$(uname -r)"
    _srcdst="$(_dkms_src_root)/${_pkg}-${_ver}"

    # Pré-requisitos — warn honesto + fail-safe (in-tree continua).
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

    # 1) Sincroniza o source em /usr/src (idempotente). Se os assets mudaram,
    #    remove a registração antiga ANTES de recopiar (rebuild limpo).
    if [[ -d "${_srcdst}" ]] && sudo diff -rq -x patch "${_src}" "${_srcdst}" >/dev/null 2>&1; then
        _dkms_log "source ${_pkg}-${_ver} já sincronizado em ${_srcdst}"
    else
        sudo dkms remove "${_pkg}/${_ver}" --all >/dev/null 2>&1 || true
        # rm/cp/install guardados um a um: o chamador roda com set -e e o
        # contrato é fail-safe — nenhuma falha aqui pode abortar o install.
        if ! sudo rm -rf "${_srcdst}"; then
            _dkms_warn "não consegui limpar ${_srcdst} — pulando ${_pkg} (in-tree continua)"
            return 0
        fi
        if ! sudo install -d "${_srcdst}" || ! sudo cp -a "${_src}/." "${_srcdst}/"; then
            _dkms_warn "falha copiando source p/ ${_srcdst} — pulando ${_pkg} (in-tree continua)"
            return 0
        fi
        # patch/ é referência de rebase/upstream, não entra no build
        sudo rm -rf "${_srcdst}/patch" || true
    fi

    # 2) add (tolerante a "já adicionado")
    if ! sudo dkms status "${_pkg}/${_ver}" 2>/dev/null | grep -q .; then
        if ! sudo dkms add "${_pkg}/${_ver}"; then
            _dkms_warn "dkms add falhou p/ ${_pkg}/${_ver} — in-tree continua"
            return 0
        fi
    fi

    # 3) build p/ o kernel atual (o AUTOINSTALL cobre kernels futuros)
    if ! sudo dkms status "${_pkg}/${_ver}" -k "${_kver}" 2>/dev/null | grep -qE 'built|installed'; then
        if ! sudo dkms build "${_pkg}/${_ver}" -k "${_kver}"; then
            _dkms_warn "dkms build FALHOU p/ ${_pkg}/${_ver} no kernel ${_kver} — módulo in-tree continua (fail-safe); log: /var/lib/dkms/${_pkg}/${_ver}/build/make.log"
            return 0
        fi
    fi

    # 4) install → /lib/modules/<kver>/updates/dkms (+ depmod pelo dkms)
    if ! sudo dkms status "${_pkg}/${_ver}" -k "${_kver}" 2>/dev/null | grep -q 'installed'; then
        if ! sudo dkms install "${_pkg}/${_ver}" -k "${_kver}"; then
            _dkms_warn "dkms install falhou p/ ${_pkg}/${_ver} — in-tree continua"
            return 0
        fi
    fi

    # 5) validação: o PRÓXIMO carregamento resolve p/ updates/dkms?
    if dkms_module_from_updates "${_built}"; then
        _dkms_log "ok: modinfo resolve ${_built} p/ updates/dkms (vence o in-tree no próximo carregamento)"
    else
        _dkms_warn "modinfo NÃO aponta ${_built} p/ updates/dkms — confira /etc/depmod.d e rode: sudo depmod -a"
    fi
    return 0
}

dkms_remove_patched_module() {
    local _pkg="$1" _ver="$2" _srcdst
    _srcdst="$(_dkms_src_root)/${_pkg}-${_ver}"
    if command -v dkms >/dev/null 2>&1 &&
        sudo dkms status "${_pkg}/${_ver}" 2>/dev/null | grep -q .; then
        if ! sudo dkms remove "${_pkg}/${_ver}" --all; then
            # Registro DKMS continua de pé: NÃO apagar o source (o dkms ainda
            # precisa dele p/ convergir) e NUNCA anunciar sucesso — re-rodar o
            # uninstall tenta de novo até convergir. Fail-safe: return 0 (o
            # resto do uninstall segue; o chamador roda com set -e).
            _dkms_warn "dkms remove falhou p/ ${_pkg}/${_ver} — registro DKMS e ${_srcdst} PRESERVADOS; remova à mão: sudo dkms remove ${_pkg}/${_ver} --all && sudo rm -rf ${_srcdst}"
            return 0
        fi
    fi
    # Guardado: o uninstall roda com set -euo pipefail e uma falha aqui (fs
    # read-only, sudoers restrito…) NÃO pode abortar os passos seguintes.
    if ! sudo rm -rf "${_srcdst}"; then
        _dkms_warn "não consegui apagar ${_srcdst} — remova à mão: sudo rm -rf ${_srcdst}"
    fi
    sudo depmod -a >/dev/null 2>&1 || true
    _dkms_log "${_pkg} removido — o módulo in-tree volta a valer no próximo boot"
    return 0
}
