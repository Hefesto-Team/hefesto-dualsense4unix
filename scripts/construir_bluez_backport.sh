#!/usr/bin/env bash
# construir_bluez_backport.sh — o backport do BlueZ que o install.sh instala,
# construído do zero e conferido a cada passo (BLUETOOTHD-NAO-DERRUBA-01).
#
# POR QUE EXISTE: até 23/09/2026 o 5.86-0ubuntu0.1~hefesto24.04.3 que roda na
# máquina dela não tinha fonte, patch nem receita em lugar nenhum — o install
# só consumia .deb prontos de um cache que já não existia. Este script é a
# receita inteira, e cada entrada dele está fixada por SHA-256 em
# assets/bluez-backport/BASELINE.
#
# O QUE FAZ, na ordem:
#   1. baixa o upstream (kernel.org) e o empacotamento do resolute
#      (Launchpad), e confere os dois hashes — nada é usado sem conferir;
#   2. monta a árvore: tarball + debian/, os três ajustes de empacotamento, os
#      patches hefesto-NNNN da revisão e as entradas do changelog;
#   3. aplica a série (dpkg-source) e confere o hash do device.c resultante;
#   4. MORDE: roda assets/bluez-backport/prova/eagain.c contra o device.c
#      vanilla (tem de destruir o aparelho no EAGAIN) e contra o patchado
#      (tem de ficar);
#   5. confere as dependências de build — se faltar, LISTA e sai (código 3),
#      sem sudo nenhum;
#   6. dpkg-buildpackage -b -us -uc, e depois o `make check` do próprio BlueZ;
#   7. entrega libbluetooth3, bluez e bluez-cups + SHA256SUMS em
#      ~/.cache/hefesto-dualsense4unix/bluez-backport/, onde o install procura,
#      e confere no bluetoothd a marca de cada patch.
#
# NÃO INSTALA NADA. O postinst do pacote bluez reinicia o bluetoothd e derruba
# todo HID por rádio; instalar é do install.sh, com ela avisada.
#
# Uso:
#   scripts/construir_bluez_backport.sh              # constrói a última revisão
#   scripts/construir_bluez_backport.sh --forcar     # reconstrói mesmo já pronto
#   scripts/construir_bluez_backport.sh --sem-unit   # pula o make check
#   scripts/construir_bluez_backport.sh --preparar   # só os passos 1 a 4
#   scripts/construir_bluez_backport.sh --mordida ARQ  # só o passo 4, sobre ARQ
#   HEFESTO_BLUEZ_CACHE=/outro scripts/construir_bluez_backport.sh --revisao 3
#       # reconstrói uma revisão antiga para provar a receita; exige um cache
#       # que NÃO seja o que o install lê
#   HEFESTO_BLUEZ_JOBS=4 scripts/construir_bluez_backport.sh
#       # compila com 4 processos em vez de um por núcleo
#
# Idempotente: com os três .deb da versão alvo já no cache, o SHA256SUMS
# batendo e o ORIGEM.txt dizendo as mesmas fontes e os mesmos patches, sai 0
# sem baixar nem compilar. A árvore de obra é refeita do zero
# a cada preparo, então duas corridas dão a mesma árvore.
#
# Códigos de saída: 0 ok · 2 uso · 3 falta dependência · 4 fonte não confere
# · 5 série não aplica · 6 a mordida não morde · 7 build · 8 unit do BlueZ.
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ASSETS="${RAIZ}/assets/bluez-backport"
BASELINE="${HEFESTO_BLUEZ_BASELINE:-${ASSETS}/BASELINE}"
CACHE="${HEFESTO_BLUEZ_CACHE:-${HOME}/.cache/hefesto-dualsense4unix}"
FONTES="${CACHE}/bluez-fontes"
OBRA="${CACHE}/bluez-obra"
SAIDA="${CACHE}/bluez-backport"
# Onde o install.sh (passo 3f) procura os .deb — fixo, sem HEFESTO_BLUEZ_CACHE.
SAIDA_DO_INSTALL="${HOME}/.cache/hefesto-dualsense4unix/bluez-backport"
# Paralelismo do build e do make check. O padrão é um núcleo por processador;
# numa máquina em uso, com pouca memória livre, peça menos.
JOBS="${HEFESTO_BLUEZ_JOBS:-$(nproc)}"

RC_USO=2
RC_DEPS=3
RC_FONTE=4
RC_PATCH=5
RC_MORDIDA=6
RC_BUILD=7
RC_UNIT=8

# O ambiente do build é LIMPO: um PYTHONPATH ou uma venv herdados mudam o
# python que gera as man pages, e o build deixa de ser o mesmo em outra casa.
AMBIENTE_LIMPO=(
    env -i
    "HOME=${HOME}"
    "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
    "LC_ALL=C.UTF-8"
    "TERM=dumb"
)

# O recorte que a mordida compila: a struct input_device (e o enum que ela
# cita), toda função hidp_send_* e os #define HIDP_SEND_* do patch. Casa pelo
# NOME, não pela linha, então serve ao vanilla e ao patchado.
# shellcheck disable=SC2016  # é um programa awk: o $ é do awk, não do shell
RECORTE_AWK='
!dentro && /^#define HIDP_SEND_/ { print; next }
!dentro && /^(enum reconnect_mode_t|struct input_device) \{/ { dentro = 1; fim = "^};"; print; next }
!dentro && /^static [^(]*[ *]hidp_send_[a-z0-9_]+\(/ && !/\);[[:space:]]*$/ { dentro = 1; fim = "^}"; print; next }
dentro { print; if ($0 ~ fim) { dentro = 0; print "" } }
'

diga() { printf '[bluez-backport] %s\n' "$*"; }

morra() {
    local rc="$1"
    shift
    printf '[bluez-backport] ERRO: %s\n' "$*" >&2
    exit "${rc}"
}

ler() {
    local chave="$1" linha
    linha="$(grep -m1 -E "^${chave}=" "${BASELINE}" || true)"
    [[ -n "${linha}" ]] || morra "${RC_USO}" "${BASELINE} não tem ${chave}"
    printf '%s' "${linha#*=}"
}

sha_de() {
    local saida
    saida="$(sha256sum "$1")"
    printf '%s' "${saida%% *}"
}

conferir_sha() {
    local arquivo="$1" esperado="$2" nome="$3" obtido
    obtido="$(sha_de "${arquivo}")"
    [[ "${obtido}" == "${esperado}" ]] \
        || morra "${RC_PATCH}" "${nome} tem SHA-256 ${obtido}, o BASELINE diz ${esperado}"
}

baixar() {
    local url="$1" esperado="$2" destino="$3" parcial
    if [[ -f "${destino}" && "$(sha_de "${destino}")" == "${esperado}" ]]; then
        diga "já baixado e conferido: ${destino##*/}"
        return 0
    fi
    command -v curl >/dev/null || morra "${RC_DEPS}" "falta o curl"
    mkdir -p "${destino%/*}"
    parcial="${destino}.parcial"
    diga "baixando ${url}"
    # Sem teto de tempo o curl fica PARADO para sempre numa conexão que aceitou
    # e não manda nada — medido em 23/09 no redirecionamento do Launchpad, com
    # o mesmo arquivo chegando em 16 s por outro curl. Cada tentativa tem teto,
    # uma transferência abaixo de 1 KB/s por 60 s é abandonada, e o --retry
    # tenta de novo.
    curl -fsSL --retry 3 --retry-delay 5 --connect-timeout 20 --max-time 300 \
            --speed-limit 1024 --speed-time 60 -o "${parcial}" "${url}" \
        || morra "${RC_FONTE}" "não consegui baixar ${url}"
    if [[ "$(sha_de "${parcial}")" != "${esperado}" ]]; then
        rm -f "${parcial}"
        morra "${RC_FONTE}" "o SHA-256 de ${url} não confere com o BASELINE — nada foi usado"
    fi
    mv -f "${parcial}" "${destino}"
}

# Os três ajustes que o 5.86 pede ao empacotamento do 5.85 (medidos no build
# de 22/07/2026). Cada um confere que achou o que devia, senão para: um ajuste
# que não acha o alvo é sinal de que o empacotamento mudou por baixo.
ajustar_empacotamento() {
    local series="${ARVORE}/debian/patches/series"
    local manpages="${ARVORE}/debian/bluez.manpages"
    local p0013="0013-transport-Fix-set-volume-failure-with-invalid-device.patch"
    local man_btmgmt="usr/share/man/man1/btmgmt.1"
    local nova

    # 1. o 0013 do resolute não liga no 5.86: a API de volume foi refeita
    #    (media_transport_get_device_volume não existe mais).
    grep -qxF "${p0013}" "${series}" \
        || morra "${RC_PATCH}" "a series do resolute não lista ${p0013}"
    grep -vxF "${p0013}" "${series}" > "${series}.novo" || true
    mv -f "${series}.novo" "${series}"

    # 2. o 5.86 não gera mais a man page do btmgmt; a cópia de debian/manpages
    #    continua instalada.
    grep -qxF "${man_btmgmt}" "${manpages}" \
        || morra "${RC_PATCH}" "debian/bluez.manpages não lista ${man_btmgmt}"
    grep -vxF "${man_btmgmt}" "${manpages}" > "${manpages}.novo" || true
    mv -f "${manpages}.novo" "${manpages}"

    # 3. seis man pages novas do 5.86, sem as quais o dh_missing aborta.
    for nova in \
        usr/share/man/man1/bluetoothctl-telephony.1 \
        usr/share/man/man5/org.bluez.Call.5 \
        usr/share/man/man5/org.bluez.Telephony.5 \
        usr/share/man/man5/org.bluez.Thermometer.5 \
        usr/share/man/man5/org.bluez.ThermometerManager.5 \
        usr/share/man/man5/org.bluez.ThermometerWatcher.5; do
        grep -qxF "${nova}" "${manpages}" || printf '%s\n' "${nova}" >> "${manpages}"
    done
}

# As entradas hefesto do changelog até a revisão pedida, por cima do do resolute.
escrever_changelog() {
    local rev="$1" changelog="${ARVORE}/debian/changelog" versao_lida
    {
        awk -v rev="${rev}" '
            /^bluez \(/ { n = $2; sub(/.*~hefesto24\.04\./, "", n); sub(/\).*/, "", n); manter = (n + 0 <= rev + 0) }
            manter { print }
        ' "${ASSETS}/debian/changelog.hefesto"
        cat "${changelog}"
    } > "${changelog}.novo"
    mv -f "${changelog}.novo" "${changelog}"
    versao_lida="$(dpkg-parsechangelog -l "${changelog}" -S Version)"
    [[ "${versao_lida}" == "${ALVO}" ]] \
        || morra "${RC_PATCH}" "o changelog montado diz ${versao_lida}, o alvo é ${ALVO}"
}

preparar() {
    local url_up sha_up url_emp sha_emp sha_vanilla sha_serie tar_up tar_emp p
    command -v dpkg-source >/dev/null || morra "${RC_DEPS}" "falta o dpkg-dev (dpkg-source)"

    # Lido em atribuição, e não dentro de argumento: assim um BASELINE sem a
    # chave para o script aqui, em vez de seguir com o valor vazio.
    url_up="$(ler FONTE_UPSTREAM_URL)"
    sha_up="$(ler FONTE_UPSTREAM_SHA256)"
    url_emp="$(ler EMPACOTAMENTO_URL)"
    sha_emp="$(ler EMPACOTAMENTO_SHA256)"
    sha_vanilla="$(ler SHA256_DEVICE_C_VANILLA)"
    sha_serie="$(ler "SHA256_DEVICE_C_R${REVISAO}")"
    tar_up="${FONTES}/${url_up##*/}"
    tar_emp="${FONTES}/${url_emp##*/}"
    baixar "${url_up}" "${sha_up}" "${tar_up}"
    baixar "${url_emp}" "${sha_emp}" "${tar_emp}"

    # A obra é refeita do zero: é isso que faz duas corridas darem a mesma árvore.
    [[ "${OBRA}" == */bluez-obra ]] || morra "${RC_USO}" "obra fora do lugar: ${OBRA}"
    rm -rf "${OBRA}"
    mkdir -p "${OBRA}"
    tar -xf "${tar_up}" -C "${OBRA}"
    [[ -d "${ARVORE}" ]] || morra "${RC_FONTE}" "o tarball não trouxe ${ARVORE##*/}/"
    tar -xf "${tar_emp}" -C "${ARVORE}"

    conferir_sha "${ARVORE}/profiles/input/device.c" "${sha_vanilla}" "o device.c do tarball"
    cp -f "${ARVORE}/profiles/input/device.c" "${OBRA}/device.c.vanilla"

    ajustar_empacotamento
    for p in ${PATCHES}; do
        [[ -f "${ASSETS}/patches/${p}" ]] || morra "${RC_PATCH}" "falta assets/bluez-backport/patches/${p}"
        cp -f "${ASSETS}/patches/${p}" "${ARVORE}/debian/patches/${p}"
        printf '%s\n' "${p}" >> "${ARVORE}/debian/patches/series"
    done
    escrever_changelog "${REVISAO}"

    if ! (cd "${ARVORE}" && dpkg-source --before-build .) > "${OBRA}/serie.log" 2>&1; then
        cat "${OBRA}/serie.log" >&2
        morra "${RC_PATCH}" "a série não aplicou (log em ${OBRA}/serie.log)"
    fi
    # Sem isto o dpkg-buildpackage DESFAZ a série ao terminar, e o make check
    # recompilaria o bluetoothd sem os patches.
    rm -f "${ARVORE}/.pc/.dpkg-source-unapply"

    conferir_sha "${ARVORE}/profiles/input/device.c" "${sha_serie}" "o device.c depois da série"
    diga "árvore pronta: ${ARVORE} (${ALVO})"
}

mordida() {
    local alvo="$1" tmp
    command -v gcc >/dev/null || morra "${RC_DEPS}" "falta o gcc (build-essential)"
    [[ -f /usr/include/linux/uhid.h ]] || morra "${RC_DEPS}" "falta linux/uhid.h (linux-libc-dev)"
    [[ -f "${alvo}" ]] || morra "${RC_USO}" "não achei ${alvo}"
    tmp="$(mktemp -d)"
    awk "${RECORTE_AWK}" "${alvo}" > "${tmp}/recorte.inc"
    if ! gcc -std=gnu11 -O0 -Wall -Wno-unused-function -I "${tmp}" \
            -o "${tmp}/eagain" "${ASSETS}/prova/eagain.c" 2> "${tmp}/gcc.log"; then
        cat "${tmp}/gcc.log" >&2
        rm -rf "${tmp}"
        morra "${RC_MORDIDA}" "o recorte de ${alvo} não compilou"
    fi
    "${tmp}/eagain"
    rm -rf "${tmp}"
}

destruido_em() {
    local saida="$1" cenario="$2" re
    re="cenario=${cenario} destruido=([0-9]+)"
    [[ "${saida}" =~ ${re} ]] || morra "${RC_MORDIDA}" "a mordida não relatou o cenário ${cenario}"
    printf '%s' "${BASH_REMATCH[1]}"
}

# A régua do patch, sobre o fonte BAIXADO: o vanilla tem de destruir o
# aparelho no EAGAIN e o patchado não. Só vale para revisão com o 0002.
provar_a_mordida() {
    local vanilla patchado n_vanilla n_eagain n_epipe
    case " ${PATCHES} " in
        *" hefesto-0002-"*) ;;
        *) diga "revisão ${REVISAO} não tem o hefesto-0002 — sem mordida a provar"; return 0 ;;
    esac
    vanilla="$(mordida "${OBRA}/device.c.vanilla")"
    patchado="$(mordida "${ARVORE}/profiles/input/device.c")"
    n_vanilla="$(destruido_em "${vanilla}" eagain)"
    n_eagain="$(destruido_em "${patchado}" eagain)"
    n_epipe="$(destruido_em "${patchado}" epipe)"
    [[ "${n_vanilla}" -gt 0 ]] \
        || morra "${RC_MORDIDA}" "o vanilla NÃO destruiu no EAGAIN — a régua não mede o defeito"
    [[ "${n_eagain}" -eq 0 ]] \
        || morra "${RC_MORDIDA}" "o patchado destruiu no EAGAIN — o hefesto-0002 não pegou"
    [[ "${n_epipe}" -gt 0 ]] \
        || morra "${RC_MORDIDA}" "o patchado não destruiu no EPIPE — erro terminal tem de derrubar"
    diga "mordida: o vanilla destrói no EAGAIN, o patchado fica, o EPIPE derruba nos dois"
}

checar_dependencias() {
    local falta
    command -v dpkg-buildpackage >/dev/null || morra "${RC_DEPS}" "falta o dpkg-dev (dpkg-buildpackage)"
    if ! falta="$(cd "${ARVORE}" && dpkg-checkbuilddeps 2>&1)"; then
        printf '%s\n' "${falta}" >&2
        printf '[bluez-backport] quem tem sudo instala e roda de novo:\n' >&2
        printf '    cd %s && sudo mk-build-deps -ir debian/control\n' "${ARVORE}" >&2
        morra "${RC_DEPS}" "faltam dependências de build (acima)"
    fi
}

compilar() {
    diga "dpkg-buildpackage -b -us -uc (log em ${OBRA}/build.log)"
    if ! (cd "${ARVORE}" && "${AMBIENTE_LIMPO[@]}" dpkg-buildpackage -b -us -uc -j"${JOBS}") \
            > "${OBRA}/build.log" 2>&1; then
        tail -n 40 "${OBRA}/build.log" >&2
        morra "${RC_BUILD}" "o build falhou (log em ${OBRA}/build.log)"
    fi
}

# O AES-CCM do kernel pela AF_ALG, que o unit/test-mesh-crypto usa (pela ell).
# Há máquina que o desliga de propósito: a dela tem
# /etc/modprobe.d/disable-algif_aead.conf (CVE-2026-31431), e ali o bind
# devolve ENOENT. Só leitura: nada é carregado nem escrito.
aead_do_kernel_disponivel() {
    python3 -c 'import socket
s = socket.socket(socket.AF_ALG, socket.SOCK_SEQPACKET, 0)
s.bind(("aead", "ccm(aes)"))' >/dev/null 2>&1
}

# Um FAIL do unit/ que a MÁQUINA explica, e não o código: o teste só é
# perdoado quando a pré-condição dele é medida ausente AGORA. Medido em
# 23/09/2026: o unit/test-mesh-crypto liga só o próprio .o e a -lell — nada de
# profiles/input —, e reprova em «Crypto packet encrypt» com o algif_aead
# desligado. Qualquer outro FAIL, ou este com o AEAD disponível, reprova.
falha_explicada_pela_maquina() {
    case "$1" in
        unit/test-mesh-crypto) ! aead_do_kernel_disponivel ;;
        *) return 1 ;;
    esac
}

unit_do_bluez() {
    local log="${ARVORE}/test-suite.log" linha tipo teste
    diga "make check, o unit/ do próprio BlueZ (log em ${OBRA}/unit.log)"
    if ! (cd "${ARVORE}" && "${AMBIENTE_LIMPO[@]}" make -j"${JOBS}" check) \
            > "${OBRA}/unit.log" 2>&1; then
        # Sem o test-suite.log o make check nem chegou a rodar os testes. O
        # XPASS também reprova o make check (automake), então entra na conta:
        # sem ele, um XPASS ao lado do mesh-crypto perdoado passava calado.
        if [[ ! -f "${log}" ]] || ! grep -qE '^(FAIL|ERROR|XPASS): ' "${log}"; then
            tail -n 40 "${OBRA}/unit.log" >&2
            morra "${RC_UNIT}" "o make check falhou antes de rodar os testes (log em ${OBRA}/unit.log)"
        fi
        while read -r linha; do
            tipo="${linha%%:*}"
            teste="${linha#*: }"
            if [[ "${tipo}" == "FAIL" ]] && falha_explicada_pela_maquina "${teste}"; then
                diga "NÃO MEDIDO nesta máquina: ${teste} — o AES-CCM do kernel (AF_ALG aead) está desligado aqui, e o teste não liga nada de profiles/input"
                continue
            fi
            printf '%s\n' "${linha}" >&2
            morra "${RC_UNIT}" "o unit/ do BlueZ reprovou (log em ${OBRA}/unit.log)"
        done < <(grep -E '^(FAIL|ERROR|XPASS): ' "${log}")
    fi
    grep -E '^# (TOTAL|PASS|SKIP|XFAIL|FAIL|XPASS|ERROR):' "${log}" || true
}

debs_alvo() {
    local pkg
    for pkg in libbluetooth3 bluez bluez-cups; do
        printf '%s\n' "${pkg}_${ALVO}_${ARCH}.deb"
    done
}

# O que entrou no build: as fontes e o hash de cada patch da revisão. É a
# chave do cache — o mesmo texto que vai para o ORIGEM.txt.
origem() {
    local p
    printf 'versao=%s\n' "${ALVO}"
    printf 'upstream=%s %s\n' "$(ler FONTE_UPSTREAM_URL)" "$(ler FONTE_UPSTREAM_SHA256)"
    printf 'empacotamento=%s %s\n' "$(ler EMPACOTAMENTO_URL)" "$(ler EMPACOTAMENTO_SHA256)"
    for p in ${PATCHES}; do
        printf 'patch=%s %s\n' "${p}" "$(sha_de "${ASSETS}/patches/${p}")"
    done
    printf 'construido_por=scripts/construir_bluez_backport.sh\n'
}

# O atalho só vale quando os .deb conferem E foram feitos com o que está na
# árvore agora. Sem a segunda pergunta, um hefesto-0002 mudado sem subir a
# revisão respondia «já construído» e o install levava o .deb velho.
ja_construido() {
    local deb
    [[ -f "${SAIDA}/SHA256SUMS" && -f "${SAIDA}/ORIGEM.txt" ]] || return 1
    while read -r deb; do
        [[ -f "${SAIDA}/${deb}" ]] || return 1
        grep -qxF "$(sha_de "${SAIDA}/${deb}")  ${deb}" "${SAIDA}/SHA256SUMS" || return 1
    done < <(debs_alvo)
    [[ "$(origem)" == "$(cat "${SAIDA}/ORIGEM.txt")" ]]
}

entregar() {
    local deb p a b _ chave marca tmp achou
    mkdir -p "${SAIDA}"
    while read -r deb; do
        [[ -f "${OBRA}/${deb}" ]] || morra "${RC_BUILD}" "o build não produziu ${deb}"
        cp -f "${OBRA}/${deb}" "${SAIDA}/${deb}"
    done < <(debs_alvo)

    # A marca de cada patch tem de estar no binário que vai para o cache.
    tmp="$(mktemp -d)"
    dpkg-deb -x "${SAIDA}/bluez_${ALVO}_${ARCH}.deb" "${tmp}"
    for p in ${PATCHES}; do
        IFS=- read -r a b _ <<< "${p}"
        chave="MARCA_${a}-${b}"
        marca="$(ler "${chave}")"
        achou="$(grep -a -c -F "${marca}" "${tmp}/usr/libexec/bluetooth/bluetoothd" || true)"
        if [[ "${achou}" -eq 0 ]]; then
            rm -rf "${tmp}"
            morra "${RC_BUILD}" "o bluetoothd construído não tem a marca do ${a}-${b}: ${marca}"
        fi
        diga "marca do ${a}-${b} no bluetoothd: ${marca}"
    done
    rm -rf "${tmp}"

    # SHA256SUMS só dos três de agora, por basename — é como o install lê.
    (cd "${SAIDA}" && debs_alvo | xargs sha256sum > SHA256SUMS.novo)
    mv -f "${SAIDA}/SHA256SUMS.novo" "${SAIDA}/SHA256SUMS"
    origem > "${SAIDA}/ORIGEM.txt"
    diga "entregue em ${SAIDA}:"
    cat "${SAIDA}/SHA256SUMS"
}

main() {
    local modo="construir" forcar=0 sem_unit=0 alvo_mordida="" revisao_ultima
    REVISAO=""
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --forcar) forcar=1 ;;
            --sem-unit) sem_unit=1 ;;
            --preparar) modo="preparar" ;;
            --mordida)
                modo="mordida"
                [[ $# -ge 2 ]] || morra "${RC_USO}" "--mordida pede o caminho de um device.c"
                alvo_mordida="$2"
                shift
                ;;
            --revisao)
                [[ $# -ge 2 ]] || morra "${RC_USO}" "--revisao pede um número"
                REVISAO="$2"
                shift
                ;;
            -h | --help)
                sed -n '2,/^set -euo/p' "${BASH_SOURCE[0]}" | sed '$d'
                exit 0
                ;;
            *) morra "${RC_USO}" "argumento desconhecido: $1" ;;
        esac
        shift
    done

    if [[ "${modo}" == "mordida" ]]; then
        mordida "${alvo_mordida}"
        exit 0
    fi

    [[ "${EUID}" -ne 0 ]] || morra "${RC_USO}" "não rode como root: o HOME vira /root e o install não acha o cache"
    [[ -f "${BASELINE}" ]] || morra "${RC_USO}" "não achei ${BASELINE}"
    revisao_ultima="$(ler REVISAO_ULTIMA)"
    REVISAO="${REVISAO:-${revisao_ultima}}"
    [[ "${REVISAO}" =~ ^[0-9]+$ ]] || morra "${RC_USO}" "revisão inválida: ${REVISAO}"
    # A pergunta é pelo LUGAR, não pela variável: HEFESTO_BLUEZ_CACHE escrito
    # com o próprio caminho do install (ou um link para ele) passava, e o .3
    # sobrescrevia o SHA256SUMS que o install lê.
    if [[ "${REVISAO}" != "${revisao_ultima}" ]] \
            && [[ "$(realpath -m "${SAIDA}")" == "$(realpath -m "${SAIDA_DO_INSTALL}")" ]]; then
        morra "${RC_USO}" "a revisão ${REVISAO} não é a última (${revisao_ultima}); ela só se reconstrói com HEFESTO_BLUEZ_CACHE apontando para FORA do cache que o install lê (${SAIDA_DO_INSTALL})"
    fi
    PATCHES="$(ler "PATCHES_R${REVISAO}")"
    ALVO="$(ler VERSAO_BASE)~hefesto24.04.${REVISAO}"
    ARVORE="${OBRA}/bluez-$(ler VERSAO_UPSTREAM)"
    ARCH="$(dpkg --print-architecture)"

    if [[ "${modo}" == "construir" && "${forcar}" -eq 0 ]] && ja_construido; then
        diga "já construído: ${ALVO} em ${SAIDA}, SHA256SUMS e ORIGEM.txt conferem — nada a fazer (--forcar reconstrói)"
        exit 0
    fi

    preparar
    provar_a_mordida
    [[ "${modo}" == "preparar" ]] && exit 0

    checar_dependencias
    compilar
    if [[ "${sem_unit}" -eq 0 ]]; then
        unit_do_bluez
    fi
    entregar
}

main "$@"
