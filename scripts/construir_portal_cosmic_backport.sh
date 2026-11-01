#!/usr/bin/env bash
set -euo pipefail
_ajuda() {
  cat <<'AJUDA'
construir_portal_cosmic_backport.sh — o portal de captura do COSMIC da casa:
o xdg-desktop-portal-cosmic que o dpkg diz, com o cosmic-protocols#92 pelo
[patch] do Cargo, construído do fonte do próprio apt e conferido a cada passo
(O-PORTAL-DE-CAPTURA-DO-COSMIC-NAO-CAI-NO-COMPARTILHAMENTO-01, 01/11/2026).

Uso:
  scripts/construir_portal_cosmic_backport.sh             # constrói
  scripts/construir_portal_cosmic_backport.sh --forcar    # reconstrói mesmo já pronto
  scripts/construir_portal_cosmic_backport.sh --preparar  # só monta a árvore, sem compilar
  scripts/construir_portal_cosmic_backport.sh --conferir-dispatch ARQ
      # o dispatch.rs do cosmic-client-toolkit destrói o frame antes do callback?
  scripts/construir_portal_cosmic_backport.sh --conferir-programa ARQ
      # o binário traz a MARCA_ do BASELINE?
  HEFESTO_PORTAL_CACHE=/outro scripts/construir_portal_cosmic_backport.sh
  HEFESTO_PORTAL_JOBS=4 scripts/construir_portal_cosmic_backport.sh

Códigos de saída: 0 certo · 2 uso · 3 falta dependência · 4 fonte · 5 patch ·
6 sem a cura · 7 build · 9 a versão de cima já traz a cura (nada a fazer).
AJUDA
}

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ASSETS="${RAIZ}/assets/portal-cosmic-backport"
BASELINE="${HEFESTO_PORTAL_BASELINE:-${ASSETS}/BASELINE}"
CACHE="${HEFESTO_PORTAL_CACHE:-${HOME}/.cache/hefesto-dualsense4unix}"
FONTES="${CACHE}/portal-cosmic-fontes"
OBRA="${CACHE}/portal-cosmic-obra"
SAIDA="${CACHE}/portal-cosmic-backport"
JOBS="${HEFESTO_PORTAL_JOBS:-$(nproc)}"
CURADAS="${SAIDA}/A-ORIGEM-JA-CURA.txt"

RC_USO=2
RC_DEPS=3
RC_FONTE=4
RC_PATCH=5
RC_CURA=6
RC_BUILD=7
RC_JA_CURADO=9

PATH_LIMPO="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

diga() { printf '[portal-cosmic-backport] %s\n' "$*"; }

morra() {
    local rc="$1"
    shift
    printf '[portal-cosmic-backport] ERRO: %s\n' "$*" >&2
    exit "${rc}"
}

ler() {
    local chave="$1" valor
    valor="$(awk -v c="${chave}" 'index($0, c "=") == 1 { print substr($0, length(c) + 2); exit }' "${BASELINE}")"
    [[ -n "${valor}" ]] || morra "${RC_USO}" "${BASELINE} não tem ${chave}"
    printf '%s' "${valor}"
}

sha_de() {
    local saida
    saida="$(sha256sum "$1")"
    printf '%s' "${saida%% *}"
}

marcas() {
    sed -n 's/^MARCA_\([^=]*\)=\(.*\)$/\1\t\2/p' "${BASELINE}"
}

tem_a_cura() {
    [[ -r "$1" ]] || return 2
    awk '
        /Event::Ready[[:space:]]*=>/ { braco = "ready"; next }
        /Event::Failed[[:space:]]*\{/ { braco = "failed"; next }
        /Event::[A-Za-z]+/ || /^[[:space:]]*_[[:space:]]*=>/ { braco = ""; next }
        braco == "" || (braco in primeiro) { next }
        /screencopy_frame\.destroy\(\);/ { primeiro[braco] = "destroy"; next }
        braco == "ready" && /app_data\.ready\(/ { primeiro[braco] = "callback"; next }
        braco == "failed" && /app_data\.failed\(/ { primeiro[braco] = "callback"; next }
        END {
            if (!("ready" in primeiro) || !("failed" in primeiro)) exit 2
            exit !(primeiro["ready"] == "destroy" && primeiro["failed"] == "destroy")
        }
    ' "$1"
}

conferir_dispatch() {
    local arquivo="$1" rc=0
    tem_a_cura "${arquivo}" || rc=$?
    case "${rc}" in
        0) diga "${arquivo##*/}: o frame se destrói antes do ready e do failed (a cura do cosmic-protocols#$(ler PROTOCOLOS_PR))" ;;
        1) morra "${RC_CURA}" "${arquivo}: o ready ou o failed roda antes do destroy do frame — sem a cura do cosmic-protocols#$(ler PROTOCOLOS_PR)" ;;
        *) morra "${RC_PATCH}" "${arquivo}: não reconheço os braços Ready e Failed do frame da captura" ;;
    esac
}

conferir_binario() {
    local arquivo="$1" nome marca faltam=() n=0
    [[ -r "${arquivo}" ]] || morra "${RC_USO}" "não consigo ler ${arquivo}"
    while IFS=$'\t' read -r nome marca; do
        n=$((n + 1))
        grep -a -q -F -- "${marca}" "${arquivo}" || faltam+=("${nome}")
    done < <(marcas)
    [[ "${n}" -gt 0 ]] || morra "${RC_USO}" "${BASELINE} não traz nenhuma linha MARCA_"
    [[ "${#faltam[@]}" -eq 0 ]] || morra "${RC_CURA}" "${arquivo} não traz ${faltam[*]}"
    diga "${arquivo} traz a cura (MARCA_ do BASELINE presente)"
}

versao_instalada() {
    dpkg-query -W -f='${db:Status-Abbrev}|${Version}\n' "$(ler PORTAL_PACOTE)" 2>/dev/null \
        | awk -F'|' '$1 ~ /^ii/ { print $2; exit }' || true
}

versao_de_cima() {
    local instalada="$1" sufixo
    sufixo="$(ler SUFIXO)"
    printf '%s' "${instalada%"${sufixo%%~hefesto*}"~hefesto*}"
}

origem() {
    printf 'portal=%s de cima %s\n' "${REVISAO}" "${VERSAO}"
    printf 'patch=%s %s cosmic-protocols#%s %s\n' "$(ler PATCH)" "$(sha_de "${ASSETS}/patches/$(ler PATCH)")" \
        "$(ler PROTOCOLOS_PR)" "$(ler PROTOCOLOS_PR_COMMIT)"
    printf 'marcas=%s\n' "$(marcas | tr '\t\n' '= ')"
    printf 'construido_por=scripts/construir_portal_cosmic_backport.sh\n'
}

ja_construido() {
    local linha linhas sha deb
    [[ -f "${SAIDA}/SHA256SUMS" && -f "${SAIDA}/ORIGEM.txt" ]] || return 1
    mapfile -t linhas < "${SAIDA}/SHA256SUMS"
    [[ "${#linhas[@]}" -gt 0 ]] || return 1
    for linha in "${linhas[@]}"; do
        read -r sha deb <<< "${linha}"
        [[ -f "${SAIDA}/${deb}" && "$(sha_de "${SAIDA}/${deb}")" == "${sha}" ]] || return 1
    done
    [[ "$(origem)" == "$(cat "${SAIDA}/ORIGEM.txt")" ]]
}

origem_ja_cura() {
    [[ -f "${CURADAS}" ]] && grep -q -x -F -- "${VERSAO}" "${CURADAS}"
}

registrar_origem_curada() {
    mkdir -p "${SAIDA}"
    origem_ja_cura || printf '%s\n' "${VERSAO}" >> "${CURADAS}"
    diga "a versão de cima ${VERSAO} já traz a cura do cosmic-protocols#$(ler PROTOCOLOS_PR) — nada a fazer"
    exit "${RC_JA_CURADO}"
}

campo_do_dsc() {
    awk -v alvo="$2" '
        /^Checksums-Sha256:/ { dentro = 1; next }
        dentro && /^[^ ]/ { exit }
        dentro && $3 == alvo { print $1; exit }
    ' "$1"
}

buscar_fonte() {
    local pacote dir dsc tar esperado
    pacote="$(ler PORTAL_PACOTE)"
    dir="${FONTES}/${VERSAO}"
    mkdir -p "${dir}"
    command -v apt-get >/dev/null || morra "${RC_DEPS}" "falta o apt-get"
    diga "buscando o fonte de ${pacote}=${VERSAO} pelo apt (conferido pelo índice assinado do repositório)"
    if ! (cd "${dir}" && LC_ALL=C apt-get source --download-only "${pacote}=${VERSAO}") \
            > "${dir}/baixar.log" 2>&1; then
        tail -n 5 "${dir}/baixar.log" >&2
        morra "${RC_FONTE}" "o apt não entregou o fonte de ${pacote}=${VERSAO}: o repositório que traz o portal precisa da linha deb-src (no Pop!_OS 24.04 a linha já vem ligada); o registro está em ${dir}/baixar.log"
    fi
    dsc="${dir}/${pacote}_${VERSAO#*:}.dsc"
    [[ -f "${dsc}" ]] || morra "${RC_FONTE}" "o apt não deixou ${dsc##*/} em ${dir}"
    tar="$(awk '/^Checksums-Sha256:/ { d = 1; next } d && /^[^ ]/ { exit } d && $3 ~ /\.tar\./ { print $3; exit }' "${dsc}")"
    [[ -n "${tar}" && -f "${dir}/${tar}" ]] || morra "${RC_FONTE}" "o ${dsc##*/} não aponta um tarball presente em ${dir}"
    esperado="$(campo_do_dsc "${dsc}" "${tar}")"
    [[ "$(sha_de "${dir}/${tar}")" == "${esperado}" ]] \
        || morra "${RC_FONTE}" "o SHA-256 de ${tar} não confere com o ${dsc##*/} — nada foi usado"
    TARBALL="${dir}/${tar}"
}

fonte_no_lock() {
    awk -v alvo="\"$2\"" '
        /^\[\[package\]\]/ { nome = "" }
        /^name = / { nome = $3 }
        /^source = / && nome == alvo { gsub(/"/, "", $3); print $3; exit }
    ' "$1"
}

chave_do_patch() {
    local fonte="$1" url
    case "${fonte}" in
        git+*)
            url="${fonte#git+}"
            url="${url%%#*}"
            printf '"%s"' "${url%%\?*}"
            ;;
        registry+https://github.com/rust-lang/crates.io-index | sparse+https://index.crates.io/)
            printf 'crates-io'
            ;;
        *) return 1 ;;
    esac
}

montar_arvore() {
    local achado
    [[ "${OBRA}" == */portal-cosmic-obra ]] || morra "${RC_USO}" "obra fora do lugar: ${OBRA}"
    rm -rf "${OBRA}"
    mkdir -p "${OBRA}/.tar"
    tar -xf "${TARBALL}" -C "${OBRA}/.tar"
    achado="$(find "${OBRA}/.tar" -mindepth 2 -maxdepth 3 -path '*/debian/changelog' -print -quit)"
    [[ -n "${achado}" ]] || morra "${RC_FONTE}" "o tarball não trouxe um debian/changelog"
    mv "${achado%/debian/changelog}" "${ARVORE}"
    rm -rf "${OBRA}/.tar"
    [[ "$(dpkg-parsechangelog -l "${ARVORE}/debian/changelog" -S Version)" == "${VERSAO}" ]] \
        || morra "${RC_FONTE}" "o debian/changelog do tarball não diz ${VERSAO}"
    [[ -f "${ARVORE}/Cargo.lock" && -f "${ARVORE}/Cargo.toml" ]] || morra "${RC_FONTE}" "o fonte não traz Cargo.toml e Cargo.lock"
    [[ -f "${ARVORE}/vendor.tar" ]] || morra "${RC_FONTE}" "o fonte não traz o vendor.tar: o [patch] precisa das crates de cima ao lado"
    tar -xf "${ARVORE}/vendor.tar" -C "${ARVORE}"
    [[ -d "${ARVORE}/vendor" && -f "${ARVORE}/.cargo/config.toml" ]] || morra "${RC_FONTE}" "o vendor.tar não trouxe vendor/ e .cargo/config.toml"
}

aplicar_o_pr() {
    local arvore_patch patch fonte_tk fonte_pr chave rc=0
    arvore_patch="${OBRA}/$(ler ARVORE_DO_PATCH)"
    patch="${ASSETS}/patches/$(ler PATCH)"
    fonte_tk="$(fonte_no_lock "${ARVORE}/Cargo.lock" cosmic-client-toolkit)"
    fonte_pr="$(fonte_no_lock "${ARVORE}/Cargo.lock" cosmic-protocols)"
    [[ -n "${fonte_tk}" ]] || morra "${RC_PATCH}" "o Cargo.lock não tem o cosmic-client-toolkit: a receita não vale para esta versão do portal"
    [[ "${fonte_tk}" == "${fonte_pr}" ]] \
        || morra "${RC_PATCH}" "o cosmic-client-toolkit e o cosmic-protocols vêm de fontes diferentes no Cargo.lock (${fonte_tk} e ${fonte_pr:-nenhuma})"
    chave="$(chave_do_patch "${fonte_tk}")" || morra "${RC_PATCH}" "não sei montar o [patch] para a fonte ${fonte_tk}"
    [[ -d "${ARVORE}/vendor/cosmic-client-toolkit" && -d "${ARVORE}/vendor/cosmic-protocols" ]] \
        || morra "${RC_PATCH}" "o vendor/ não traz o cosmic-client-toolkit e o cosmic-protocols"

    tem_a_cura "${ARVORE}/vendor/cosmic-client-toolkit/src/screencopy/dispatch.rs" || rc=$?
    case "${rc}" in
        0) registrar_origem_curada ;;
        1) ;;
        *) morra "${RC_PATCH}" "não reconheço o dispatch.rs do cosmic-client-toolkit desta versão: a receita precisa de revisão" ;;
    esac

    cp -a "${ARVORE}/vendor/cosmic-protocols" "${arvore_patch}"
    rm -rf "${arvore_patch}/client-toolkit"
    cp -a "${ARVORE}/vendor/cosmic-client-toolkit" "${arvore_patch}/client-toolkit"
    rm -f "${arvore_patch}/.cargo-checksum.json" "${arvore_patch}/client-toolkit/.cargo-checksum.json"
    [[ "$(sha_de "${patch}")" == "$(ler PATCH_SHA256)" ]] \
        || morra "${RC_PATCH}" "${patch##*/} não tem o SHA-256 do BASELINE"
    if ! patch -d "${arvore_patch}" -p1 -F0 -N -s < "${patch}" > "${OBRA}/patch.log" 2>&1; then
        cat "${OBRA}/patch.log" >&2
        morra "${RC_PATCH}" "${patch##*/} não aplica sem fuzz sobre o cosmic-protocols de ${fonte_tk}"
    fi
    conferir_dispatch "${arvore_patch}/client-toolkit/src/screencopy/dispatch.rs"

    grep -q -x -F "[patch.${chave}]" "${ARVORE}/Cargo.toml" \
        && morra "${RC_PATCH}" "o Cargo.toml de cima já tem um [patch.${chave}]"
    printf '\n[patch.%s]\ncosmic-protocols = { path = "../%s" }\ncosmic-client-toolkit = { path = "../%s/client-toolkit" }\n' \
        "${chave}" "${arvore_patch##*/}" "${arvore_patch##*/}" >> "${ARVORE}/Cargo.toml"
    LOCK_FONTE="${fonte_tk}"
    diga "aplicado: ${patch##*/} sobre ${fonte_tk##*#}, pelo [patch.${chave}] do Cargo.toml"
}

ambiente_de_build() {
    local cargo_dir gcc_include
    cargo_dir="$(dirname "$(command -v cargo)")"
    gcc_include="$(gcc -print-file-name=include)"
    AMBIENTE=(
        env -i
        "HOME=${HOME}"
        "PATH=${cargo_dir}:${PATH_LIMPO}"
        "LC_ALL=C.UTF-8"
        "TERM=dumb"
        "BINDGEN_EXTRA_CLANG_ARGS=-I${gcc_include}"
        "CARGO_BUILD_JOBS=${JOBS}"
        "DEB_BUILD_OPTIONS=noautodbgsym parallel=${JOBS}"
    )
    local v
    for v in CARGO_HOME RUSTUP_HOME RUSTUP_TOOLCHAIN LIBCLANG_PATH; do
        [[ -n "${!v:-}" ]] && AMBIENTE+=("${v}=${!v}")
    done
    return 0
}

atualizar_o_lock() {
    cp -a "${ARVORE}/Cargo.lock" "${OBRA}/Cargo.lock.de-cima"
    if ! (cd "${ARVORE}" && "${AMBIENTE[@]}" cargo metadata --offline --format-version 1) \
            > /dev/null 2> "${OBRA}/lock.log"; then
        cat "${OBRA}/lock.log" >&2
        morra "${RC_PATCH}" "o cargo não resolveu o [patch] com as crates do vendor.tar (registro em ${OBRA}/lock.log)"
    fi
    if ! grep -v -x -F "source = \"${LOCK_FONTE}\"" "${OBRA}/Cargo.lock.de-cima" | diff -q - "${ARVORE}/Cargo.lock" >/dev/null; then
        diff <(grep -v -x -F "source = \"${LOCK_FONTE}\"" "${OBRA}/Cargo.lock.de-cima") "${ARVORE}/Cargo.lock" | head -n 20 >&2 || true
        morra "${RC_PATCH}" "o Cargo.lock mudou além das duas crates do [patch]"
    fi
    rm -rf "${ARVORE}/vendor" "${ARVORE}/.cargo"
    diga "Cargo.lock: só o cosmic-protocols e o cosmic-client-toolkit trocam de fonte"
}

escrever_changelog() {
    local changelog="${ARVORE}/debian/changelog" dist data lock_commit
    dist="$(dpkg-parsechangelog -l "${changelog}" -S Distribution)"
    data="$(dpkg-parsechangelog -l "${changelog}" -S Date)"
    lock_commit="${LOCK_FONTE##*#}"
    {
        printf '%s (%s) %s; urgency=medium\n\n' "$(ler PORTAL_PACOTE)" "${REVISAO}" "${dist}"
        printf '  * O frame da captura se destrói antes do ready e do failed\n'
        printf '    (pop-os/cosmic-protocols#%s), pelo [patch] do Cargo: o\n' "$(ler PROTOCOLOS_PR)"
        printf '    compartilhamento de tela não cai mais com «create_frame sent\n'
        printf '    before the previous frame was destroyed».\n'
        printf '  * cosmic-protocols#%s: %s\n' "$(ler PROTOCOLOS_PR)" "$(ler PROTOCOLOS_PR_COMMIT)"
        printf '  * cosmic-protocols de cima: %s\n' "${lock_commit}"
        printf '  * Upstream: %s\n\n' "${VERSAO}"
        printf ' -- Hefesto DualSense4Unix Project <hefesto-dualsense4unix@users.noreply.github.com>  %s\n\n' "${data}"
        cat "${changelog}"
    } > "${changelog}.novo"
    mv -f "${changelog}.novo" "${changelog}"
    [[ "$(dpkg-parsechangelog -l "${changelog}" -S Version)" == "${REVISAO}" ]] \
        || morra "${RC_PATCH}" "o changelog montado não diz ${REVISAO}"
}

preparar() {
    command -v dpkg-parsechangelog >/dev/null || morra "${RC_DEPS}" "falta o dpkg-dev (dpkg-parsechangelog)"
    command -v patch >/dev/null || morra "${RC_DEPS}" "falta o patch"
    buscar_fonte
    montar_arvore
    aplicar_o_pr
}

versao_do_rust_pedida() {
    local pedida edicao
    pedida="$(sed -n 's/^rust-version[[:space:]]*=[[:space:]]*"\([0-9.]*\)".*/\1/p' "${ARVORE}/Cargo.toml" | head -n 1)"
    if [[ -z "${pedida}" ]]; then
        edicao="$(sed -n 's/^edition[[:space:]]*=[[:space:]]*"\([0-9]*\)".*/\1/p' "${ARVORE}/Cargo.toml" | head -n 1)"
        case "${edicao}" in
            2024) pedida=1.85 ;;
            2021) pedida=1.56 ;;
        esac
    fi
    printf '%s' "${pedida}"
}

tem_libclang() {
    [[ -n "${LIBCLANG_PATH:-}" ]] && compgen -G "${LIBCLANG_PATH}/libclang*.so*" >/dev/null && return 0
    { ldconfig -p 2>/dev/null || /sbin/ldconfig -p 2>/dev/null; } | grep -q -E '[[:space:]]libclang(-[0-9.]+)?\.so'
}

checar_dependencias() {
    local faltam=() saida nomes n rust pedida include
    command -v dpkg-buildpackage >/dev/null || faltam+=("o dpkg-dev (sudo apt install dpkg-dev)")
    if ! command -v cargo >/dev/null || ! command -v rustc >/dev/null; then
        faltam+=("o Rust, cargo e rustc (pelo rustup, https://rustup.rs, ou sudo apt install cargo rustc)")
    else
        rust="$(rustc --version 2>/dev/null | awk '{ print $2 }')"
        pedida="$(versao_do_rust_pedida)"
        if [[ -n "${pedida}" ]] && ! dpkg --compare-versions "${rust:-0}" ge "${pedida}" 2>/dev/null; then
            faltam+=("um Rust ${pedida} ou mais novo: o desta máquina é o ${rust:-desconhecido} (rustup update)")
        fi
    fi
    command -v just >/dev/null || faltam+=("o just (sudo apt install just)")
    tem_libclang || faltam+=("o libclang, que o bindgen carrega (sudo apt install libclang-dev)")
    if ! command -v gcc >/dev/null; then
        faltam+=("o gcc, de onde sai o stdbool.h do bindgen (sudo apt install gcc)")
    else
        include="$(gcc -print-file-name=include)"
        [[ -f "${include}/stdbool.h" ]] || faltam+=("o stdbool.h do gcc em ${include} (sudo apt install gcc)")
    fi
    if command -v dpkg-checkbuilddeps >/dev/null; then
        saida="$(cd "${ARVORE}" && LC_ALL=C dpkg-checkbuilddeps 2>&1)" || true
        nomes="$(sed -n 's/.*Unmet build dependencies: //p' <<<"${saida}" | sed -E 's/ \([^)]*\)//g; s/ \| [^ ]+//g')"
        for n in ${nomes}; do
            case "${n}" in
                cargo | rustc) command -v cargo >/dev/null && command -v rustc >/dev/null && continue ;;
                just) command -v just >/dev/null && continue ;;
                libclang-dev) tem_libclang && continue ;;
            esac
            faltam+=("${n} (sudo apt install ${n})")
        done
    fi
    if [[ "${#faltam[@]}" -gt 0 ]]; then
        printf '[portal-cosmic-backport] falta, para construir o portal da casa:\n' >&2
        printf '    - %s\n' "${faltam[@]}" >&2
        morra "${RC_DEPS}" "faltam dependências de build (acima)"
    fi
}

compilar() {
    diga "dpkg-buildpackage -b -us -uc em ${ARVORE##*/} (log em ${ARVORE}.build.log)"
    if ! (cd "${ARVORE}" && "${AMBIENTE[@]}" dpkg-buildpackage -b -us -uc -nc -d -j"${JOBS}") \
            > "${ARVORE}.build.log" 2>&1; then
        tail -n 40 "${ARVORE}.build.log" >&2
        morra "${RC_BUILD}" "o build de ${ARVORE##*/} falhou (log em ${ARVORE}.build.log)"
    fi
}

entregar() {
    local arch deb tmp programa
    arch="$(dpkg --print-architecture)"
    deb="${OBRA}/$(ler PORTAL_PACOTE)_${REVISAO#*:}_${arch}.deb"
    [[ -f "${deb}" ]] || morra "${RC_BUILD}" "o build não produziu ${deb##*/}"
    tmp="$(mktemp -d)"
    dpkg-deb -x "${deb}" "${tmp}" || morra "${RC_BUILD}" "não consegui abrir ${deb##*/}"
    programa="$(find "${tmp}" -type f -name "$(ler PORTAL_PACOTE)" -perm -u+x -print -quit)"
    if [[ -z "${programa}" ]]; then
        rm -rf "${tmp}"
        morra "${RC_BUILD}" "${deb##*/} não traz o binário do portal"
    fi
    (conferir_binario "${programa}") || {
        rm -rf "${tmp}"
        morra "${RC_CURA}" "o binário construído não traz a MARCA_ do BASELINE"
    }
    rm -rf "${tmp}"
    mkdir -p "${SAIDA}"
    rm -f "${SAIDA}"/*.deb
    cp -f "${deb}" "${SAIDA}/"
    (cd "${SAIDA}" && sha256sum -- *.deb > SHA256SUMS.novo)
    mv -f "${SAIDA}/SHA256SUMS.novo" "${SAIDA}/SHA256SUMS"
    origem > "${SAIDA}/ORIGEM.txt"
    rm -rf "${ARVORE}/target" "${ARVORE}/vendor" "${ARVORE}/vendor.tar"
    diga "entregue em ${SAIDA}: ${deb##*/}"
}

main() {
    local modo="construir" forcar=0 instalada
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --forcar) forcar=1 ;;
            --preparar) modo="preparar" ;;
            --conferir-dispatch)
                [[ $# -ge 2 ]] || morra "${RC_USO}" "--conferir-dispatch pede o caminho de um dispatch.rs"
                conferir_dispatch "$2"
                exit 0
                ;;
            --conferir-programa)
                [[ $# -ge 2 ]] || morra "${RC_USO}" "--conferir-programa pede o caminho de um binário"
                conferir_binario "$2"
                exit 0
                ;;
            -h | --help)
                _ajuda
                exit 0
                ;;
            *) morra "${RC_USO}" "argumento desconhecido: $1" ;;
        esac
        shift
    done

    [[ "${EUID}" -ne 0 ]] || morra "${RC_USO}" "não rode como root: o HOME vira /root"
    [[ -f "${BASELINE}" ]] || morra "${RC_USO}" "não achei ${BASELINE}"
    [[ "${JOBS}" =~ ^[1-9][0-9]*$ ]] || morra "${RC_USO}" "HEFESTO_PORTAL_JOBS inválido: ${JOBS} (um inteiro a partir de 1)"
    command -v dpkg-query >/dev/null || morra "${RC_USO}" "sem dpkg: o portal da casa é .deb"
    instalada="$(versao_instalada)"
    [[ -n "${instalada}" ]] || morra "${RC_USO}" "o $(ler PORTAL_PACOTE) não está instalado pelo dpkg"
    VERSAO="$(versao_de_cima "${instalada}")"
    REVISAO="${VERSAO}$(ler SUFIXO)"
    ARVORE="${OBRA}/$(ler PORTAL_PACOTE)-${VERSAO#*:}"

    origem_ja_cura && registrar_origem_curada
    if [[ "${modo}" == "construir" && "${forcar}" -eq 0 ]] && ja_construido; then
        diga "já construído em ${SAIDA}: SHA256SUMS e ORIGEM.txt conferem — nada a fazer (--forcar reconstrói)"
        exit 0
    fi

    preparar
    checar_dependencias
    ambiente_de_build
    atualizar_o_lock
    escrever_changelog
    diga "árvore pronta: ${ARVORE} (${REVISAO})"
    [[ "${modo}" == "preparar" ]] && exit 0
    compilar
    entregar
}

main "$@"
