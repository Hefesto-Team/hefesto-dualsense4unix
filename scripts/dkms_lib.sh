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
#   dkms_mark_initramfs_stale <builtname>  # agenda o refresh (não roda ainda)
#   dkms_flush_initramfs                   # roda UMA vez, no fim do install

# Raízes parametrizáveis (defaults == sistema real). Existem como COSTURA DE
# TESTE: a suíte precisa exercitar o caminho feliz/idempotente/build-falho de
# ponta a ponta sem root (aponta as duas p/ diretórios temporários + stubs de
# sudo/dkms). Em produção NUNCA são definidas — os defaults valem.
_dkms_src_root() { printf '%s' "${HEFESTO_DKMS_SRC_ROOT:-/usr/src}"; }
_dkms_modules_root() { printf '%s' "${HEFESTO_DKMS_MODULES_ROOT:-/lib/modules}"; }
# Idem para o initramfs (INITRAMFS-01, abaixo): default == sistema real; a
# suíte aponta para um arquivo temporário.
_dkms_initramfs_path() {
    printf '%s' "${HEFESTO_INITRAMFS_PATH:-/boot/initrd.img-$(uname -r)}"
}

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
# `:=` e não `=`: o install.sh dá `source` NESTE arquivo DENTRO de cada função
# (uma vez por módulo DKMS). Com atribuição direta, cada source zeraria o
# marcador e o aviso sairia repetido — e, pior, o mesmo padrão zeraria a fila
# do initramfs abaixo, que existe justamente para coalescer.
: "${_DKMS_SB_WARNED:=0}"
dkms_warn_secureboot_once() {
    [[ "${_DKMS_SB_WARNED}" -eq 1 ]] && return 0
    command -v mokutil >/dev/null 2>&1 || return 0
    if mokutil --sb-state 2>/dev/null | grep -qi 'SecureBoot enabled'; then
        _DKMS_SB_WARNED=1
        _dkms_warn "Secure Boot ATIVO: o módulo DKMS só CARREGA se a chave MOK do dkms estiver enrolada (se não estiver, o kernel recusa o .ko no boot e NÃO volta ao in-tree sozinho). Se um controle Nintendo/WiFi sumir após o próximo boot, enrole a chave: sudo mokutil --import /var/lib/dkms/mok.pub (nvidia-DKMS funcionando indica que já está resolvido)."
    fi
    return 0
}

# ---------------------------------------------------------------------------
# INITRAMFS-01 (25/07) — o furo que fazia o boot carregar o módulo VELHO
# ---------------------------------------------------------------------------
# O initramfs carrega uma CÓPIA do .ko (o hid-nintendo entra nele porque é
# driver de teclado/gamepad USB, necessário para digitar a senha do LUKS).
# `dkms install` grava em /lib/modules/<kver>/updates/dkms e roda `depmod`,
# mas NÃO regenera o initramfs. Resultado medido nesta máquina em 25/07:
# initramfs de 23/07 x DKMS reconstruído em 25/07, e o boot subia o módulo
# antigo — provado comparando a identidade de fonte do .ko carregado
# (D83CA24F0AB553FD5643812) com a do .ko em disco (954EBD3EDBB7D0BBA07066F).
# Como os parâmetros do patch 0003 não existiam no módulo velho, o kernel
# DESCARTAVA o /etc/modprobe.d/hefesto-hid-nintendo.conf INTEIRO ("unknown
# parameter"), derrubando junto curas que já funcionavam (bt_probe_retries).
# (Aquela comparação é DIAGNÓSTICO pontual, feito à mão; NÃO é como esta lib
# valida nada — a validação aqui é sempre por CAMINHO, via
# `modinfo -F filename` resolvendo para updates/dkms.)
#
# Simetria (regra dura do projeto): o uninstall também precisa regenerar,
# senão o initramfs segue entregando o módulo do hefesto depois de removido.
#
# O comentário do scripts/install_snd_quirk.sh ("update-initramfs é
# desnecessário") vale SÓ para o caso dele (options de snd_usb_audio, que
# carrega tarde, já da raiz montada) — não vale para módulo de HID.
#
# Coalescência: `update-initramfs -u` custa dezenas de segundos e ~140 MB de
# escrita; com 3 módulos DKMS rodaria 3x. Por isso os chamadores MARCAM
# (dkms_mark_initramfs_stale) e um único dkms_flush_initramfs no fim executa.
: "${_DKMS_INITRAMFS_STALE:=0}"
: "${_DKMS_INITRAMFS_DONE:=0}"
: "${_DKMS_INITRAMFS_MODS:=}"

# Marca que o initramfs ficou defasado por causa de <builtname> (ex.:
# hid-nintendo). Não executa nada — quem executa é o flush.
dkms_mark_initramfs_stale() {
    _DKMS_INITRAMFS_STALE=1
    case " ${_DKMS_INITRAMFS_MODS} " in
        *" $1 "*) : ;;
        *) _DKMS_INITRAMFS_MODS="${_DKMS_INITRAMFS_MODS} $1" ;;
    esac
    return 0
}

# Qual gerador esta distro usa? Preenche o ARRAY _DKMS_INITRAMFS_ARGV (vazio
# se nenhum for encontrado). Ordem: Debian/Ubuntu/Pop (update-initramfs) →
# Fedora/RHEL/SUSE (dracut) → Arch (mkinitcpio). Todos regeneram o initramfs
# do kernel CORRENTE.
#
# Array e não string: `sudo ${_cmd}` depende de word splitting, que é o
# default do bash mas NÃO do zsh — a mesma linha vira "comando não encontrado"
# quando alguém dá source nesta lib de um shell interativo zsh (acontece:
# é assim que se depura o install). Array não tem essa dependência, nem
# precisa de `shellcheck disable=SC2086`, nem quebra com espaço no uname -r.
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

# Regenera o initramfs UMA vez, se alguém marcou. Fail-safe como o resto da
# lib: gerador ausente ou falha viram aviso + return 0 (o install nunca aborta
# — o pior caso é continuar valendo o módulo do boot anterior, que é
# exatamente o estado de hoje). Idempotente: só roda uma vez por execução.
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
    # Saída guardada em arquivo (não descartada): quando falha, o motivo é o
    # que importa — /boot cheio é a causa clássica, e um aviso sem a mensagem
    # do gerador manda a mantenedora repetir o comando à mão só para ler o
    # erro. `< /dev/null` porque este passo NUNCA pode virar prompt: o install
    # roda sem TTY (headless) e um gerador esperando resposta travaria tudo.
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

# BUG-INSTALL-INITRAMFS-REGENERA-SEMPRE-01 (25/07): o INITRAMFS-01 marcava o
# initramfs como defasado em TODA execução bem-sucedida do
# dkms_install_patched_module — inclusive quando os três módulos já estavam
# sincronizados e nada tinha sido reconstruído. Medido: um `install.sh --yes`
# reexecutado sem nenhuma mudança reescrevia 141 MB em /boot, exatamente o
# custo que o desenho do passo 3l dizia querer evitar.
#
# O juiz certo não é "o passo rodou", é MTIME: o initramfs só está defasado se
# o .ko que o modprobe resolve HOJE for mais NOVO que a imagem. Como bônus,
# este critério é auto-curativo — se um flush anterior falhou (/boot cheio), o
# .ko continua mais novo e a próxima execução tenta de novo, o que um simples
# "mudou nesta execução?" não faria. Na dúvida (modinfo mudo, .ko ou imagem
# ausentes) devolve 0 = defasado: regenerar à toa é caro, não regenerar quando
# era preciso é um boot com o módulo velho.
_dkms_initramfs_desatualizado() {
    local _ko _img
    _ko="$(modinfo -F filename "$1" 2>/dev/null)" || return 0
    _img="$(_dkms_initramfs_path)"
    [[ -f "${_ko}" && -f "${_img}" ]] || return 0
    [[ "${_ko}" -nt "${_img}" ]]
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
        # INITRAMFS-01: o .ko novo está em updates/dkms, mas o initramfs ainda
        # carrega a cópia da geração anterior. Marca aqui (dentro do ramo de
        # SUCESSO — nos ramos fail-safe nada mudou em disco, logo nada a
        # regenerar) e deixa o flush do chamador executar uma vez só.
        # BUG-INSTALL-INITRAMFS-REGENERA-SEMPRE-01: e só se o .ko for de fato
        # mais novo que a imagem — reinstalar por cima sem nada ter mudado não
        # justifica reescrever 141 MB em /boot.
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

# 3º argumento (<builtname>, ex.: hid-nintendo) é OPCIONAL só por
# compatibilidade com chamadas antigas: sem ele o initramfs não é marcado e a
# cópia do módulo removido continuaria no initramfs (assimetria). Passe sempre.
dkms_remove_patched_module() {
    local _pkg="$1" _ver="$2" _built="${3:-}" _srcdst
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
    # INITRAMFS-01 (simetria): o depmod acima conserta /lib/modules, mas o
    # initramfs guarda uma CÓPIA do .ko removido e continuaria entregando o
    # módulo do hefesto no boot — desinstalado no disco, vivo no boot. Marca
    # para o flush do uninstall regenerar.
    [[ -n "${_built}" ]] && dkms_mark_initramfs_stale "${_built}"
    _dkms_log "${_pkg} removido — o módulo in-tree volta a valer no próximo boot"
    return 0
}
