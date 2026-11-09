#!/usr/bin/env bash
set -u

ALVO_INSTALADO=/usr/local/lib/hefesto-dualsense4unix/atualizador-raiz
SUFIXOS_INSTALADOS=/usr/local/lib/hefesto-dualsense4unix/sufixos-da-casa
RECEITAS_INSTALADAS=/usr/local/lib/hefesto-dualsense4unix/receitas
REPO_DO_MANGOHUD=flightlessmango/MangoHud
GRUPOS="nvidia kernel sistema"
GRUPOS_DA_REINSTALACAO="nvidia kernel"
BACKPORTS="bluez pipewire portal"
TETO_DO_BAIXADO=$((512 * 1024 * 1024))

if [[ "$(id -u)" -eq 0 ]]; then
    export PATH=/usr/sbin:/usr/bin:/sbin:/bin
    export DEBIAN_FRONTEND=noninteractive
    CACHE=/var/cache/hefesto-dualsense4unix
    SRC=/usr/src
    MODULOS=/lib/modules
    ENTRADAS=/boot/efi/loader/entries
    ESP=/boot/efi
    BOOT=/boot
    ESTADO=/var/lib/hefesto-dualsense4unix/atualizador
    SUFIXOS="${SUFIXOS_INSTALADOS}"
    RECEITAS="${RECEITAS_INSTALADAS}"
    CASA_DA_USUARIA=""
    DONO=root
    API="https://api.github.com/repos/${REPO_DO_MANGOHUD}/releases/latest"
else
    CACHE="${HEFESTO_ATUALIZADOR_CACHE:-}"
    SRC="${HEFESTO_ATUALIZADOR_SRC:-/usr/src}"
    MODULOS="${HEFESTO_ATUALIZADOR_MODULOS:-/lib/modules}"
    ENTRADAS="${HEFESTO_ATUALIZADOR_ENTRADAS:-/boot/efi/loader/entries}"
    ESP="${HEFESTO_ATUALIZADOR_ESP:-/boot/efi}"
    BOOT="${HEFESTO_ATUALIZADOR_BOOT:-/boot}"
    ESTADO="${HEFESTO_ATUALIZADOR_ESTADO:-}"
    SUFIXOS="${HEFESTO_ATUALIZADOR_SUFIXOS:-${SUFIXOS_INSTALADOS}}"
    RECEITAS="${HEFESTO_ATUALIZADOR_RECEITAS:-}"
    CASA_DA_USUARIA="${HEFESTO_ATUALIZADOR_CASA:-}"
    DONO="${HEFESTO_ATUALIZADOR_DONO:-root}"
    API="${HEFESTO_ATUALIZADOR_API:-}"
fi

umask 077

_erro() { printf '%s: %s\n' "${0##*/}" "$*" >&2; }
_recusar() { _erro "$*"; exit 2; }

_exige_raiz() {
    [[ -n "${CACHE}" ]] || { _erro "'$1' requer root"; exit 1; }
}

_apt() {
    apt-get -y -o APT::Status-Fd=1 \
        -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold "$@"
}

APT_SO_ASSINADO=(-o APT::Get::AllowUnauthenticated=false -o Acquire::AllowInsecureRepositories=false
    -o Acquire::AllowDowngradeToInsecureRepositories=false)
APT_SO_A_PECA=(--no-remove -o APT::Get::allow-downgrades=false -o APT::Get::allow-remove-essential=false
    -o APT::Get::allow-change-held-packages=false)

_instalados() {
    dpkg-query -W -f '${Package}\t${db:Status-Abbrev}\t${Version}\n' 2>/dev/null
}

_instalados_que_casam() {
    _instalados | awk -F'\t' -v re="$1" '$2 ~ /^ii/ && $1 ~ re { print $1 }'
}

_e_so_do_dono() {
    local alvo="$1" fora
    [[ -e "${alvo}" ]] || return 1
    fora="$(find "${alvo}" \( ! -user "${DONO}" -o -perm /022 \) -print -quit 2>/dev/null)"
    [[ -z "${fora}" ]]
}

SEGURADOS=()

_soltar_os_da_casa() {
    [[ "${#SEGURADOS[@]}" -gt 0 ]] || return 0
    apt-mark unhold "${SEGURADOS[@]}" >/dev/null || _erro "não soltei: ${SEGURADOS[*]}"
    SEGURADOS=()
}

_segurar_os_da_casa() {
    _e_so_do_dono "${SUFIXOS}" || _recusar "sem a lista dos sufixos da casa só do root (${SUFIXOS}): rode o install"
    local -a sufixos da_casa ja
    mapfile -t sufixos < <(grep -E '^[A-Za-z0-9.+~:-]+$' "${SUFIXOS}")
    [[ "${#sufixos[@]}" -gt 0 ]] || _recusar "a lista dos sufixos da casa está vazia"
    mapfile -t da_casa < <(_instalados | awk -F'\t' -v lista="$(printf '%s\n' "${sufixos[@]}")" '
        BEGIN { n = split(lista, s, "\n") }
        $2 ~ /^ii/ { for (i = 1; i <= n; i++) if (s[i] != "" && index($3, s[i])) { print $1; break } }')
    [[ "${#da_casa[@]}" -gt 0 ]] || return 0
    local segurados_antes
    segurados_antes="$(apt-mark showhold 2>/dev/null)" \
        || _recusar "não li os pacotes já segurados: nada sobe sem saber o que não se solta"
    mapfile -t ja <<<"${segurados_antes}"
    local p j
    for p in "${da_casa[@]}"; do
        for j in "${ja[@]}"; do
            [[ "${p}" == "${j}" ]] && continue 2
        done
        SEGURADOS+=("${p}")
    done
    [[ "${#SEGURADOS[@]}" -gt 0 ]] || return 0
    trap _soltar_os_da_casa EXIT
    trap 'exit 130' INT TERM HUP
    apt-mark hold "${SEGURADOS[@]}" >/dev/null || _recusar "não segurei os pacotes da casa: ${SEGURADOS[*]}"
    printf 'fora da subida (da casa): %s\n' "${SEGURADOS[*]}"
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
    _segurar_os_da_casa
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

_grupo_da_reinstalacao() {
    local g
    for g in ${GRUPOS_DA_REINSTALACAO}; do
        [[ "$1" == "${g}" ]] && return 0
    done
    _recusar "grupo sem reinstalação: '$1' (${GRUPOS_DA_REINSTALACAO// / | })"
}

_pacotes_da_reinstalacao() {
    local grupo="$1" rodando="$2"
    _instalados | awk -F'\t' -v grupo="${grupo}" -v k="-${rodando}" '
        $2 !~ /^ii/ { next }
        grupo == "nvidia" && $1 ~ /^(nvidia-|libnvidia-|xserver-xorg-video-nvidia)/ { print $1 "=" $3 }
        grupo == "kernel" && $1 ~ /^linux-/ && length($1) > length(k) \
            && substr($1, length($1) - length(k) + 1) == k { print $1 "=" $3 }' | sort -u
}

_apt_reinstalar_do_grupo() {
    local grupo="$1" rodando="" p
    shift
    _grupo_da_reinstalacao "${grupo}"
    if [[ "${grupo}" == "kernel" ]]; then
        rodando="$(uname -r)"
        [[ "${rodando}" =~ ^[A-Za-z0-9._+-]+$ ]] || _recusar "o kernel em uso tem um nome estranho: '${rodando}'"
    fi
    _segurar_os_da_casa
    local -a pacotes
    mapfile -t pacotes < <(_pacotes_da_reinstalacao "${grupo}" "${rodando}")
    [[ "${#pacotes[@]}" -gt 0 ]] || _recusar "nada instalado no grupo ${grupo} para reinstalar"
    for p in "${pacotes[@]}"; do
        [[ "${p}" =~ ^[a-z0-9][a-z0-9.+-]*=[A-Za-z0-9.+:~-]+$ ]] || _recusar "pacote estranho: '${p}'"
    done
    _apt "${APT_SO_ASSINADO[@]}" "${APT_SO_A_PECA[@]}" "$@" install --reinstall --no-install-recommends \
        "${pacotes[@]}"
}

verbo_apt_baixar_de_novo() { _exige_raiz apt-baixar-de-novo; _apt_reinstalar_do_grupo "${1:-}" -d; }
verbo_apt_reinstalar() { _exige_raiz apt-reinstalar; _apt_reinstalar_do_grupo "${1:-}"; }

verbo_apt_consertar() {
    _exige_raiz apt-consertar
    local rc=0
    _segurar_os_da_casa
    dpkg --force-confdef --force-confold --configure -a || rc=1
    _apt "${APT_SO_ASSINADO[@]}" "${APT_SO_A_PECA[@]}" --no-install-recommends -f install || rc=1
    return "${rc}"
}
_kernels_instalados() {
    local k
    for k in "${MODULOS}"/*; do
        [[ -d "${k}" ]] && printf '%s\n' "${k##*/}"
    done
}

_pasta_do_estado() {
    [[ -n "${ESTADO}" ]] || _recusar "sem a pasta do estado do ajudante"
    install -d -m 700 "${ESTADO}" || _recusar "não criei ${ESTADO}"
    _e_so_do_dono "${ESTADO}" || _recusar "a pasta ${ESTADO} não é só do root"
}

verbo_apt_instalar() {
    _exige_raiz apt-instalar
    local grupo="${1:-}" antes depois rodando
    if [[ "${grupo}" != "kernel" ]]; then
        _apt_do_grupo "${grupo}"
        return
    fi
    _pasta_do_estado
    antes="$(_kernels_instalados)"
    rodando="$(uname -r)"
    _apt_do_grupo kernel || return 1
    depois="$(_kernels_instalados)"
    if [[ "${depois}" != "${antes}" && "${rodando}" =~ ^[A-Za-z0-9._+-]+$ ]]; then
        printf '%s\n' "${rodando}" > "${ESTADO}/kernel-anterior"
        chmod 600 "${ESTADO}/kernel-anterior"
        printf 'a volta possível: %s\n' "${rodando}"
    fi
}
verbo_apt_limpar() { _exige_raiz apt-limpar; _segurar_os_da_casa; _apt autoremove --purge; }

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

_dkms_compilar() {
    local nome="$1" ver="$2" kernel="$3" forcar="$4"
    if [[ "${forcar}" -eq 0 ]]; then
        dkms install -m "${nome}" -v "${ver}" -k "${kernel}"
        return
    fi
    dkms build --force -m "${nome}" -v "${ver}" -k "${kernel}" \
        && dkms install --force -m "${nome}" -v "${ver}" -k "${kernel}"
}

_dkms_por_fonte() {
    local forcar="$1" pasta nome ver kernel mudou=0 falhou=0
    command -v dkms >/dev/null 2>&1 || _recusar "dkms ausente"
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
            if [[ "${forcar}" -eq 0 ]] \
                && dkms status -m "${nome}" -v "${ver}" -k "${kernel}" 2>/dev/null | grep -q ': installed'; then
                continue
            fi
            printf 'refazendo %s %s para %s\n' "${nome}" "${ver}" "${kernel}"
            if _dkms_compilar "${nome}" "${ver}" "${kernel}" "${forcar}"; then
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

verbo_dkms_refazer() { _exige_raiz dkms-refazer; _dkms_por_fonte 0; }
verbo_dkms_reinstalar() { _exige_raiz dkms-reinstalar; _dkms_por_fonte 1; }

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

_uid_da_usuaria() {
    if [[ -n "${CASA_DA_USUARIA}" ]]; then
        id -u
        return
    fi
    id -u -- "${SUDO_USER}"
}

_copiar_o_baixado() {
    python3 -I - "$1" "$2" "$3" "${TETO_DO_BAIXADO}" <<'COPIA'
import os, stat, sys
origem, destino, dono, teto = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
try:
    fd = os.open(origem, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
except OSError as erro:
    sys.exit(f"não abri {origem}: {erro.strerror}")
st = os.fstat(fd)
if not stat.S_ISREG(st.st_mode):
    sys.exit(f"{origem} não é um arquivo comum")
if (dono >= 0 and st.st_uid != dono) or st.st_nlink != 1:
    sys.exit(f"{origem} não é de quem baixou")
if st.st_size > teto:
    sys.exit(f"{origem} passa do teto")
lidos = 0
with os.fdopen(fd, "rb") as entrada, open(destino, "wb") as saida:
    while bloco := entrada.read(1024 * 1024):
        lidos += len(bloco)
        if lidos > teto:
            sys.exit(f"{origem} passa do teto")
        saida.write(bloco)
COPIA
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
    _e_so_do_dono "${CACHE}/mangohud" || _recusar "a pasta ${CACHE}/mangohud não é só do root"
    rm -f "${CACHE}/mangohud/novo.tar.gz"
    _copiar_o_baixado "${origem}" "${CACHE}/mangohud/novo.tar.gz" "$(_uid_da_usuaria)" \
        || { rm -f "${CACHE}/mangohud/novo.tar.gz"; _recusar "não li ${origem}"; }
    esperado="$(_digest_publicado "${nome}")"
    [[ "${esperado}" =~ ^[0-9a-f]{64}$ ]] || { rm -f "${CACHE}/mangohud/novo.tar.gz"; _recusar "a soma publicada de ${nome} não veio"; }
    obtido="$(sha256sum "${CACHE}/mangohud/novo.tar.gz" | cut -d' ' -f1)"
    if [[ "${obtido}" != "${esperado}" ]]; then
        rm -f "${CACHE}/mangohud/novo.tar.gz"
        _recusar "o sha256 de ${nome} não é o publicado"
    fi
    _instalar_o_tar_do_mangohud "${CACHE}/mangohud/novo.tar.gz" || exit 1
    if [[ -f "${CACHE}/mangohud/atual.tar.gz" ]]; then
        mv -f "${CACHE}/mangohud/atual.tar.gz" "${CACHE}/mangohud/anterior.tar.gz"
        if [[ -f "${CACHE}/mangohud/atual.nome" ]]; then
            mv -f "${CACHE}/mangohud/atual.nome" "${CACHE}/mangohud/anterior.nome"
        else
            rm -f "${CACHE}/mangohud/anterior.nome"
        fi
    fi
    mv -f "${CACHE}/mangohud/novo.tar.gz" "${CACHE}/mangohud/atual.tar.gz"
    printf '%s\n' "${nome}" >"${CACHE}/mangohud/atual.nome"
    printf 'MangoHud instalado: %s\n' "${nome}"
}

_mangohud_de_agora() {
    local pasta="${CACHE}/mangohud" nome
    [[ -d "${pasta}" && ! -L "${pasta}" ]] && _e_so_do_dono "${pasta}" \
        && [[ -f "${pasta}/atual.tar.gz" && ! -L "${pasta}/atual.tar.gz" ]] \
        && [[ -f "${pasta}/atual.nome" && ! -L "${pasta}/atual.nome" ]] \
        || _recusar "sem o MangoHud que este ajudante instalou: a reinstalação vem depois da primeira subida pela janela"
    nome="$(head -n 1 "${pasta}/atual.nome")"
    [[ "${nome}" =~ ^MangoHud-[A-Za-z0-9._-]+\.tar\.gz$ ]] || _recusar "o nome do MangoHud de agora está estragado"
    printf '%s\n' "${nome}"
}

verbo_mangohud_reinstalavel() {
    _exige_raiz mangohud-reinstalavel
    local nome
    nome="$(_mangohud_de_agora)" || exit 2
    printf 'reinstala: %s\n' "${nome}"
}

verbo_mangohud_reinstalar() {
    _exige_raiz mangohud-reinstalar
    local nome
    nome="$(_mangohud_de_agora)" || exit 2
    _instalar_o_tar_do_mangohud "${CACHE}/mangohud/atual.tar.gz" || exit 1
    printf 'MangoHud reinstalado: %s\n' "${nome}"
}

verbo_mangohud_voltar() {
    _exige_raiz mangohud-voltar
    _e_so_do_dono "${CACHE}/mangohud" || _recusar "a pasta ${CACHE}/mangohud não é só do root"
    [[ -f "${CACHE}/mangohud/anterior.tar.gz" ]] || _recusar "sem versão anterior do MangoHud trocada por este ajudante"
    _instalar_o_tar_do_mangohud "${CACHE}/mangohud/anterior.tar.gz" || exit 1
    mv -f "${CACHE}/mangohud/anterior.tar.gz" "${CACHE}/mangohud/atual.tar.gz"
    if [[ -f "${CACHE}/mangohud/anterior.nome" ]]; then
        mv -f "${CACHE}/mangohud/anterior.nome" "${CACHE}/mangohud/atual.nome"
    else
        rm -f "${CACHE}/mangohud/atual.nome"
    fi
    printf 'MangoHud de volta à versão anterior\n'
}

_imagem_da_entrada() {
    local caminho
    caminho="$(awk 'tolower($1) == "linux" { print $2; exit }' "$1" 2>/dev/null)"
    [[ "${caminho}" =~ ^/[A-Za-z0-9._/-]+$ && "${caminho}" != *..* ]] || return 1
    printf '%s%s\n' "${ESP}" "${caminho}"
}

_entrada_do_kernel() {
    local ver="$1" e velha imagem
    for e in "${ENTRADAS}"/*.conf; do
        [[ -f "${e}" ]] || continue
        if [[ "${e##*/}" == *"${ver}"* ]] || grep -qF -- "${ver}" "${e}"; then
            printf '%s\n' "${e##*/}"
            return 0
        fi
    done
    velha="$(find "${ENTRADAS}" -maxdepth 1 -name '*oldkern.conf' -printf '%f\n' 2>/dev/null | head -n 1)"
    [[ -n "${velha}" ]] || return 0
    imagem="$(_imagem_da_entrada "${ENTRADAS}/${velha}")" || return 3
    [[ -f "${imagem}" && -f "${BOOT}/vmlinuz-${ver}" ]] || return 3
    cmp -s -- "${imagem}" "${BOOT}/vmlinuz-${ver}" || return 3
    printf '%s\n' "${velha}"
}

verbo_kernel_anterior() {
    _exige_raiz kernel-anterior
    _pasta_do_estado
    local registro="${ESTADO}/kernel-anterior" ver entrada
    _e_so_do_dono "${registro}" || _recusar "nenhuma subida de kernel deste ajudante a desfazer"
    ver="$(head -n 1 "${registro}")"
    [[ "${ver}" =~ ^[A-Za-z0-9._+-]+$ ]] || _recusar "o registro do kernel anterior está estragado"
    [[ -d "${MODULOS}/${ver}" ]] || _recusar "o kernel ${ver} não está mais instalado"
    entrada="$(_entrada_do_kernel "${ver}")" \
        || _recusar "a entrada «oldkern» do carregador não é o kernel ${ver}: nada muda"
    [[ -n "${entrada}" ]] || _recusar "sem a entrada do kernel ${ver} no carregador"
    command -v bootctl >/dev/null 2>&1 || _recusar "bootctl ausente"
    bootctl set-default "${entrada}" || exit 1
    rm -f "${registro}"
    printf 'o próximo início usa %s (%s)\n' "${entrada}" "${ver}"
}

_backport_valido() {
    local b
    for b in ${BACKPORTS}; do
        [[ "$1" == "${b}" ]] && return 0
    done
    _recusar "peça da casa desconhecida: '$1' (${BACKPORTS// / | })"
}

_versao_do_portal_no_apt() {
    local v melhor=""
    while IFS= read -r v; do
        [[ "${v}" =~ ^[0-9A-Za-z.+:~-]+$ && "${v}" != *~hefesto* ]] || continue
        if [[ -z "${melhor}" ]] || dpkg --compare-versions "${v}" gt "${melhor}"; then
            melhor="${v}"
        fi
    done < <(apt-cache madison xdg-desktop-portal-cosmic 2>/dev/null \
        | awk -F'|' '{ gsub(/ /, "", $2); print $2 }')
    printf '%s' "${melhor}"
}

_obra_da_caixa() {
    if [[ "$(id -u)" -eq 0 ]]; then
        printf '/var/cache/hefesto-backport-%s' "$1"
    else
        printf '%s/backports/%s/obra' "${CACHE}" "$1"
    fi
}

_construir_na_caixa() {
    local peca="$1" ver="$2"
    local -a receita=(python3 -I "${RECEITAS}/scripts/hefesto_receita_nova.py" construir
        --peca "${peca}" --receitas "${RECEITAS}" --portal-do-apt "${ver}"
        --obra "$(_obra_da_caixa "${peca}")")
    if [[ "$(id -u)" -ne 0 ]]; then
        "${receita[@]}" </dev/null
        return
    fi
    command -v systemd-run >/dev/null 2>&1 || _recusar "systemd-run ausente: a casa não constrói como root"
    systemd-run --quiet --wait --pipe --collect \
        -p DynamicUser=yes -p "CacheDirectory=hefesto-backport-${peca}" \
        -p ProtectHome=yes -p PrivateTmp=yes -p NoNewPrivileges=yes -p RuntimeMaxSec=4h \
        -p "WorkingDirectory=/var/cache/hefesto-backport-${peca}" \
        "${receita[@]}" </dev/null
}

_limpar_a_caixa() {
    [[ "$(id -u)" -eq 0 ]] || return 0
    rm -rf --one-file-system -- "/var/cache/private/hefesto-backport-$1"
}

_conferir_a_entrega() {
    local pasta="$1" deb nome
    [[ -f "${pasta}/SHA256SUMS" ]] || return 1
    compgen -G "${pasta}/*.deb" >/dev/null || return 1
    for deb in "${pasta}"/*.deb; do
        nome="${deb##*/}"
        awk -v n="${nome}" '$2 == n || $2 == "*" n { achou = 1 } END { exit !achou }' \
            "${pasta}/SHA256SUMS" || return 1
    done
    (cd "${pasta}" && sha256sum --quiet --strict -c SHA256SUMS) >/dev/null 2>&1
}

_fontes_da_peca() {
    case "$1" in
        bluez) printf 'bluez\n' ;;
        pipewire) printf 'pipewire\nwireplumber\n' ;;
        portal) printf 'xdg-desktop-portal-cosmic\n' ;;
    esac
}

_debs_da_casa() {
    local pasta="$1" peca="$2" deb pacote ver fonte s da_casa
    local -a sufixos
    _e_so_do_dono "${SUFIXOS}" || { _erro "sem a lista dos sufixos da casa só do root (${SUFIXOS})"; return 1; }
    mapfile -t sufixos < <(grep -E '^[A-Za-z0-9.+~:-]+$' "${SUFIXOS}")
    for deb in "${pasta}"/*.deb; do
        pacote="$(dpkg-deb -f "${deb}" Package 2>/dev/null)"
        ver="$(dpkg-deb -f "${deb}" Version 2>/dev/null)"
        [[ "${pacote}" =~ ^[a-z0-9][a-z0-9.+-]*$ ]] || { _erro "${deb##*/} sem nome de pacote"; return 1; }
        da_casa=0
        for s in "${sufixos[@]}"; do
            [[ -n "${s}" && "${ver}" == *"${s}"* ]] && da_casa=1
        done
        [[ "${da_casa}" -eq 1 ]] || { _erro "${deb##*/} não é um pacote da casa (${ver})"; return 1; }
        fonte="$(dpkg-deb -f "${deb}" Source 2>/dev/null)"
        fonte="${fonte%% *}"
        fonte="${fonte:-${pacote}}"
        _fontes_da_peca "${peca}" | grep -qxF -- "${fonte}" \
            || { _erro "${deb##*/} vem do fonte ${fonte}, não do de ${peca}"; return 1; }
        _instalados | awk -F'\t' -v p="${pacote}" '$1 == p && $2 ~ /^ii/ { achou = 1 } END { exit !achou }' \
            && printf '%s\n' "${deb}"
    done
    return 0
}

_instalar_da_pasta() {
    local pasta="$1" peca="$2" lista
    shift 2
    _conferir_a_entrega "${pasta}" || _recusar "a soma dos pacotes em ${pasta} não confere"
    lista="$(_debs_da_casa "${pasta}" "${peca}")" || _recusar "os pacotes em ${pasta} não são da casa"
    [[ -n "${lista}" ]] || _recusar "nenhum dos pacotes em ${pasta} está instalado nesta máquina"
    local -a debs
    mapfile -t debs <<<"${lista}"
    _apt "$@" install --no-install-recommends "${debs[@]}"
}

verbo_backport_construir() {
    _exige_raiz backport-construir
    local peca="$1" ver="" obra arquivo nome rc=0 base
    _backport_valido "${peca}"
    [[ -n "${RECEITAS}" ]] && _e_so_do_dono "${RECEITAS}" \
        || _recusar "sem as receitas da casa só do root (${RECEITAS}): rode o install"
    base="${CACHE}/backports/${peca}"
    install -d -m 700 "${CACHE}/backports" "${base}" || _recusar "não criei ${base}"
    _e_so_do_dono "${CACHE}/backports" || _recusar "a pasta ${CACHE}/backports não é só do root"
    if [[ "${peca}" == "portal" ]]; then
        ver="$(_versao_do_portal_no_apt)"
        [[ -n "${ver}" ]] || _recusar "o apt não diz a versão do portal"
    fi
    obra="$(_obra_da_caixa "${peca}")"
    _construir_na_caixa "${peca}" "${ver}" || rc=$?
    if [[ "${rc}" -ne 0 ]]; then
        _limpar_a_caixa "${peca}"
        exit "${rc}"
    fi
    rm -rf -- "${base}/novo"
    if [[ -L "${obra}/entrega" || ! -d "${obra}/entrega" ]]; then
        _limpar_a_caixa "${peca}"
        _recusar "a entrega de ${peca} não é uma pasta da caixa"
    fi
    install -d -m 700 "${base}/novo"
    for arquivo in "${obra}/entrega"/*.deb "${obra}/entrega/SHA256SUMS"; do
        [[ -e "${arquivo}" || -L "${arquivo}" ]] || continue
        nome="${arquivo##*/}"
        if [[ ! "${nome}" =~ ^[A-Za-z0-9._+~-]+$ ]] \
            || ! _copiar_o_baixado "${arquivo}" "${base}/novo/${nome}" -1; then
            rm -rf -- "${base}/novo"
            _limpar_a_caixa "${peca}"
            _recusar "a entrega de ${peca} traz o que não se copia: ${nome}"
        fi
    done
    _limpar_a_caixa "${peca}"
    if ! _conferir_a_entrega "${base}/novo"; then
        rm -rf -- "${base}/novo"
        _recusar "a entrega de ${peca} não confere com a própria SHA256SUMS"
    fi
    printf 'pronto para instalar: %s\n' "${peca}"
}

verbo_backport_instalar() {
    _exige_raiz backport-instalar
    local peca="$1" base
    _backport_valido "${peca}"
    base="${CACHE}/backports/${peca}"
    _e_so_do_dono "${base}/novo" || _recusar "nada construído para ${peca}: a construção vem antes"
    _instalar_da_pasta "${base}/novo" "${peca}" || exit 1
    rm -rf -- "${base}/anterior"
    [[ -d "${base}/atual" ]] && mv -f -- "${base}/atual" "${base}/anterior"
    mv -f -- "${base}/novo" "${base}/atual"
    printf 'instalado: %s\n' "${peca}"
}

_entrega_da_reinstalacao() {
    local peca="$1" base lista deb pacote ver instalada
    _backport_valido "${peca}"
    base="${CACHE}/backports/${peca}"
    [[ -d "${base}/atual" && ! -L "${base}/atual" ]] && _e_so_do_dono "${base}/atual" \
        || _recusar "sem a entrega de ${peca} que este ajudante instalou: a reinstalação vem depois da primeira subida pela janela"
    _conferir_a_entrega "${base}/atual" || _recusar "a soma dos pacotes de ${peca} não confere"
    lista="$(_debs_da_casa "${base}/atual" "${peca}")" || _recusar "os pacotes de ${peca} não são da casa"
    [[ -n "${lista}" ]] || _recusar "nenhum dos pacotes de ${peca} está instalado nesta máquina"
    while IFS= read -r deb; do
        pacote="$(dpkg-deb -f "${deb}" Package 2>/dev/null)"
        ver="$(dpkg-deb -f "${deb}" Version 2>/dev/null)"
        instalada="$(_instalados | awk -F'\t' -v p="${pacote}" '$1 == p && $2 ~ /^ii/ { print $3; exit }')"
        [[ -n "${ver}" && "${ver}" == "${instalada}" ]] \
            || _recusar "a entrega de ${peca} traz ${pacote} ${ver}, e a máquina tem ${instalada:-nada}: não é a versão de agora"
    done <<<"${lista}"
    printf '%s\n' "${lista}"
}

verbo_backport_reinstalavel() {
    _exige_raiz backport-reinstalavel
    _entrega_da_reinstalacao "$1" >/dev/null || exit 2
    printf 'reinstala: %s\n' "$1"
}

verbo_backport_reinstalar() {
    _exige_raiz backport-reinstalar
    local lista
    lista="$(_entrega_da_reinstalacao "$1")" || exit 2
    local -a debs
    mapfile -t debs <<<"${lista}"
    _apt "${APT_SO_ASSINADO[@]}" "${APT_SO_A_PECA[@]}" install --reinstall --no-install-recommends \
        "${debs[@]}" || exit 1
    printf 'reinstalado: %s\n' "$1"
}

verbo_backport_voltar() {
    _exige_raiz backport-voltar
    local peca="$1" base
    _backport_valido "${peca}"
    base="${CACHE}/backports/${peca}"
    _e_so_do_dono "${base}/anterior" || _recusar "sem versão anterior de ${peca} trocada por este ajudante"
    _instalar_da_pasta "${base}/anterior" "${peca}" --allow-downgrades || exit 1
    rm -rf -- "${base}/atual"
    mv -f -- "${base}/anterior" "${base}/atual"
    printf '%s de volta à versão anterior\n' "${peca}"
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
    for g in ${GRUPOS_DA_REINSTALACAO}; do
        printf '    %s apt-baixar-de-novo %s, \\\n' "${ALVO_INSTALADO}" "${g}"
        printf '    %s apt-reinstalar %s, \\\n' "${ALVO_INSTALADO}" "${g}"
    done
    printf '    %s apt-consertar, \\\n' "${ALVO_INSTALADO}"
    printf '    %s apt-limpar, \\\n' "${ALVO_INSTALADO}"
    printf '    %s dkms-refazer, \\\n' "${ALVO_INSTALADO}"
    printf '    %s dkms-reinstalar, \\\n' "${ALVO_INSTALADO}"
    printf '    %s mangohud-instalar, \\\n' "${ALVO_INSTALADO}"
    printf '    %s mangohud-reinstalavel, \\\n' "${ALVO_INSTALADO}"
    printf '    %s mangohud-reinstalar, \\\n' "${ALVO_INSTALADO}"
    printf '    %s mangohud-voltar, \\\n' "${ALVO_INSTALADO}"
    for g in ${BACKPORTS}; do
        printf '    %s backport-construir %s, \\\n' "${ALVO_INSTALADO}" "${g}"
        printf '    %s backport-instalar %s, \\\n' "${ALVO_INSTALADO}" "${g}"
        printf '    %s backport-reinstalavel %s, \\\n' "${ALVO_INSTALADO}" "${g}"
        printf '    %s backport-reinstalar %s, \\\n' "${ALVO_INSTALADO}" "${g}"
        printf '    %s backport-voltar %s, \\\n' "${ALVO_INSTALADO}" "${g}"
    done
    printf '    %s kernel-anterior\n' "${ALVO_INSTALADO}"
    printf '%s ALL=(root) NOPASSWD: HEFESTO_ATUALIZADOR\n' "${usuaria}"
}

[[ $# -le 2 ]] || _recusar "argumentos demais"

case "${1:-}" in
    apt-lista) [[ $# -eq 1 ]] || _recusar "apt-lista não leva argumento"; verbo_apt_lista ;;
    apt-baixar) [[ $# -eq 2 ]] || _recusar "apt-baixar <grupo>"; verbo_apt_baixar "$2" ;;
    apt-instalar) [[ $# -eq 2 ]] || _recusar "apt-instalar <grupo>"; verbo_apt_instalar "$2" ;;
    apt-baixar-de-novo) [[ $# -eq 2 ]] || _recusar "apt-baixar-de-novo <grupo>"; verbo_apt_baixar_de_novo "$2" ;;
    apt-reinstalar) [[ $# -eq 2 ]] || _recusar "apt-reinstalar <grupo>"; verbo_apt_reinstalar "$2" ;;
    apt-consertar) [[ $# -eq 1 ]] || _recusar "apt-consertar não leva argumento"; verbo_apt_consertar ;;
    apt-limpar) [[ $# -eq 1 ]] || _recusar "apt-limpar não leva argumento"; verbo_apt_limpar ;;
    dkms-refazer) [[ $# -eq 1 ]] || _recusar "dkms-refazer não leva argumento"; verbo_dkms_refazer ;;
    dkms-reinstalar) [[ $# -eq 1 ]] || _recusar "dkms-reinstalar não leva argumento"; verbo_dkms_reinstalar ;;
    mangohud-instalar) [[ $# -eq 1 ]] || _recusar "mangohud-instalar não leva argumento"; verbo_mangohud_instalar ;;
    mangohud-reinstalavel) [[ $# -eq 1 ]] || _recusar "mangohud-reinstalavel não leva argumento"; verbo_mangohud_reinstalavel ;;
    mangohud-reinstalar) [[ $# -eq 1 ]] || _recusar "mangohud-reinstalar não leva argumento"; verbo_mangohud_reinstalar ;;
    mangohud-voltar) [[ $# -eq 1 ]] || _recusar "mangohud-voltar não leva argumento"; verbo_mangohud_voltar ;;
    kernel-anterior) [[ $# -eq 1 ]] || _recusar "kernel-anterior não leva argumento"; verbo_kernel_anterior ;;
    backport-construir) [[ $# -eq 2 ]] || _recusar "backport-construir <peça>"; verbo_backport_construir "$2" ;;
    backport-instalar) [[ $# -eq 2 ]] || _recusar "backport-instalar <peça>"; verbo_backport_instalar "$2" ;;
    backport-reinstalavel) [[ $# -eq 2 ]] || _recusar "backport-reinstalavel <peça>"; verbo_backport_reinstalavel "$2" ;;
    backport-reinstalar) [[ $# -eq 2 ]] || _recusar "backport-reinstalar <peça>"; verbo_backport_reinstalar "$2" ;;
    backport-voltar) [[ $# -eq 2 ]] || _recusar "backport-voltar <peça>"; verbo_backport_voltar "$2" ;;
    regra-sudo) verbo_regra_sudo "${2:-}" ;;
    *) _recusar "verbo desconhecido: '${1:-}' (apt-lista | apt-baixar|apt-instalar <grupo> | apt-baixar-de-novo|apt-reinstalar <grupo> | apt-consertar | apt-limpar | dkms-refazer | dkms-reinstalar | mangohud-instalar | mangohud-reinstalavel | mangohud-reinstalar | mangohud-voltar | kernel-anterior | backport-construir|backport-instalar|backport-reinstalavel|backport-reinstalar|backport-voltar <peça> | regra-sudo <usuária>)" ;;
esac
