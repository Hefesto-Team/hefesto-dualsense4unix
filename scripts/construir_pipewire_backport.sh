#!/usr/bin/env bash
# construir_pipewire_backport.sh — o PipeWire e o WirePlumber da casa,
# construídos do zero e conferidos a cada passo
# (O-PIPEWIRE-DA-CASA-LEVA-A-CURA-DO-METADATA-01, 15/10/2026).
#
# POR QUE EXISTE: até a 1.6.8 (a do Pop!_OS 24.04), o cliente que faz bind num
# metadata enquanto o WirePlumber sai fica preso para sempre, e a Steam, que
# roda `wpctl settings`, não fecha (docs/protocol/o-wpctl-pendurado-pelo-metadata.md).
# O upstream curou na 1.6.9. A casa leva a estável mais nova dos dois, sem
# esperar a distro: cada entrada está fixada por SHA-256 em
# assets/pipewire-backport/BASELINE.
#
# O QUE FAZ, na ordem:
#   1. baixa os tarballs das tags do upstream e os do Pop (o debian/ vem dentro
#      deles) e confere os quatro hashes — nada é usado sem conferir;
#   2. monta as duas árvores: o fonte do upstream, o debian/ do Pop, os ajustes
#      de empacotamento, os patches (cada um conferido pelo hash) e a entrada
#      do changelog;
#   3. confere que o metadata.c da árvore é o do BASELINE e que o global_unbind
#      dele chama o remove_pending (a cura);
#   4. confere as dependências de build — se faltar, LISTA e sai (código 3),
#      sem sudo nenhum;
#   5. dpkg-buildpackage -b -us -uc das duas;
#   6. entrega os .deb + SHA256SUMS + ORIGEM.txt em
#      ~/.cache/hefesto-dualsense4unix/pipewire-backport/.
#
# NÃO INSTALA NADA. Trocar o PipeWire reinicia o som da sessão; a instalação é
# à mão, com a Steam fechada, pela receita
# (docs/usage/receita-backport-pipewire.md).
#
# Uso:
#   scripts/construir_pipewire_backport.sh               # constrói os dois
#   scripts/construir_pipewire_backport.sh --forcar      # reconstrói mesmo já pronto
#   scripts/construir_pipewire_backport.sh --preparar    # só os passos 1 a 3
#   scripts/construir_pipewire_backport.sh --prova       # passos 1 a 3, e a prova sem dependência de build:
#       compila só o servidor da árvore (meson mínimo, sem ALSA nem Bluetooth) com e sem a cura,
#       e roda assets/pipewire-backport/prova/reproduzir.sh nos dois. Com a cura, 0 pendurados;
#       sem ela, todos. Precisa de meson, ninja e gcc, e do wireplumber e do wpctl no PATH.
#   scripts/construir_pipewire_backport.sh --conferir-metadata ARQ
#       # só a pergunta do passo 3, sobre ARQ
#   HEFESTO_PIPEWIRE_CACHE=/outro scripts/construir_pipewire_backport.sh
#   HEFESTO_PIPEWIRE_JOBS=4 scripts/construir_pipewire_backport.sh
#
# Idempotente: com os .deb já no cache, o SHA256SUMS batendo e o ORIGEM.txt
# dizendo as mesmas fontes e os mesmos patches, sai 0 sem baixar nem compilar.
#
# Códigos de saída: 0 ok · 2 uso · 3 falta dependência · 4 fonte não confere
# · 5 patch ou ajuste não aplica · 6 sem a cura · 7 build · 8 a prova falhou.
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ASSETS="${RAIZ}/assets/pipewire-backport"
BASELINE="${HEFESTO_PIPEWIRE_BASELINE:-${ASSETS}/BASELINE}"
CACHE="${HEFESTO_PIPEWIRE_CACHE:-${HOME}/.cache/hefesto-dualsense4unix}"
FONTES="${CACHE}/pipewire-fontes"
OBRA="${CACHE}/pipewire-obra"
SAIDA="${CACHE}/pipewire-backport"
JOBS="${HEFESTO_PIPEWIRE_JOBS:-$(nproc)}"

RC_USO=2
RC_DEPS=3
RC_FONTE=4
RC_PATCH=5
RC_CURA=6
RC_BUILD=7
RC_PROVA=8

# O ambiente do build é LIMPO: um PYTHONPATH ou uma venv herdados mudam o
# python do meson, e o build deixa de ser o mesmo em outra casa.
AMBIENTE_LIMPO=(
    env -i
    "HOME=${HOME}"
    "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
    "LC_ALL=C.UTF-8"
    "TERM=dumb"
)

diga() { printf '[pipewire-backport] %s\n' "$*"; }

morra() {
    local rc="$1"
    shift
    printf '[pipewire-backport] ERRO: %s\n' "$*" >&2
    exit "${rc}"
}

# A chave casa por texto, não por regex: os nomes dos patches têm ponto.
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

conferir_sha() {
    local arquivo="$1" esperado="$2" nome="$3" rc="${4:-${RC_PATCH}}" obtido
    obtido="$(sha_de "${arquivo}")"
    [[ "${obtido}" == "${esperado}" ]] \
        || morra "${rc}" "${nome} tem SHA-256 ${obtido}, o BASELINE diz ${esperado}"
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
    # Com teto de tempo: sem ele o curl fica parado para sempre numa conexão
    # que aceitou e não manda nada (medido em 23/09 no backport do BlueZ).
    curl -fsSL --retry 3 --retry-delay 5 --connect-timeout 20 --max-time 600 \
            --speed-limit 1024 --speed-time 60 -o "${parcial}" "${url}" \
        || morra "${RC_FONTE}" "não consegui baixar ${url}"
    if [[ "$(sha_de "${parcial}")" != "${esperado}" ]]; then
        rm -f "${parcial}"
        morra "${RC_FONTE}" "o SHA-256 de ${url} não confere com o BASELINE — nada foi usado"
    fi
    mv -f "${parcial}" "${destino}"
}

# A cura do #5445 (o 06de0ed): o global_unbind chama o remove_pending. Lido
# pelo corpo da função, e não pela linha, para servir a qualquer versão.
tem_a_cura() {
    awk '
        /^static void global_unbind\(void \*data\)/ { dentro = 1; next }
        dentro && /^}/ { exit }
        dentro && /remove_pending\(d\);/ { achou = 1 }
        END { exit !achou }
    ' "$1"
}

conferir_metadata() {
    local arquivo="$1"
    [[ -r "${arquivo}" ]] || morra "${RC_USO}" "não consigo ler ${arquivo}"
    tem_a_cura "${arquivo}" \
        || morra "${RC_CURA}" "o global_unbind de ${arquivo} não chama o remove_pending: sem a cura do metadata (#5445)"
    diga "o global_unbind de ${arquivo##*/} chama o remove_pending (a cura do #5445)"
}

# Monta <obra>/<nome>-<versão>: o tarball da tag e, por cima, o debian/ do
# tarball nativo do Pop.
montar() {
    local prefixo="$1" nome="$2" url_up sha_up url_emp sha_emp tar_up tar_emp tmp
    url_up="$(ler "${prefixo}_FONTE_URL")"
    sha_up="$(ler "${prefixo}_FONTE_SHA256")"
    url_emp="$(ler "${prefixo}_EMPACOTAMENTO_URL")"
    sha_emp="$(ler "${prefixo}_EMPACOTAMENTO_SHA256")"
    tar_up="${FONTES}/${url_up##*/}"
    tar_emp="${FONTES}/${url_emp##*/}"
    baixar "${url_up}" "${sha_up}" "${tar_up}"
    baixar "${url_emp}" "${sha_emp}" "${tar_emp}"

    tar -xf "${tar_up}" -C "${OBRA}"
    [[ -d "${OBRA}/${nome}" ]] || morra "${RC_FONTE}" "o tarball não trouxe ${nome}/"
    tmp="${OBRA}/.emp-${prefixo}"
    mkdir -p "${tmp}"
    tar -xf "${tar_emp}" -C "${tmp}"
    [[ -d "${tmp}/archive/debian" ]] || morra "${RC_FONTE}" "o tarball do Pop não trouxe archive/debian/"
    cp -a "${tmp}/archive/debian" "${OBRA}/${nome}/debian"
    rm -rf "${tmp}"
}

aplicar() {
    local arvore="$1" patch="$2" nome="${2##*/}"
    if ! patch -d "${arvore}" -p1 -F0 -N -s < "${patch}" > "${OBRA}/${nome}.log" 2>&1; then
        cat "${OBRA}/${nome}.log" >&2
        morra "${RC_PATCH}" "${nome} não aplica sem fuzz em ${arvore##*/}"
    fi
    diga "aplicado: ${nome}"
}

# Prepende a entrada da casa e confere que o changelog montado diz a revisão
# do BASELINE.
escrever_changelog() {
    local arvore="$1" entrada="$2" alvo="$3" changelog="$1/debian/changelog" lida
    cat "${entrada}" "${changelog}" > "${changelog}.novo"
    mv -f "${changelog}.novo" "${changelog}"
    lida="$(dpkg-parsechangelog -l "${changelog}" -S Version)"
    [[ "${lida}" == "${alvo}" ]] || morra "${RC_PATCH}" "o changelog montado diz ${lida}, o BASELINE diz ${alvo}"
}

# Os ajustes que a 1.6.9 pede ao debian/ da 1.6.8 do Pop (medidos em
# 15/10/2026). Cada um confere que achou o alvo, senão para: um ajuste que não
# acha o alvo é sinal de que o empacotamento mudou por baixo.
ajustar_pipewire() {
    local arvore="$1" d="$1/debian"
    # 1. a 1.6.9 pede libcamera >= 0.6.0 (spa/meson.build), e o noble tem a 0.2.0:
    #    o plugin sai do build e os dois pacotes dele saem do control.
    # shellcheck disable=SC2016  # é o texto do debian/rules: o $ é do make
    grep -q -F -- '-Dlibcamera=$(LIBCAMERA)' "${d}/rules" \
        || morra "${RC_PATCH}" "o debian/rules do Pop não passa -Dlibcamera=\$(LIBCAMERA)"
    # shellcheck disable=SC2016  # idem
    sed -i 's/-Dlibcamera=\$(LIBCAMERA)/-Dlibcamera=disabled/' "${d}/rules"
    grep -q -E '^[[:space:]]+libcamera-dev ' "${d}/control" \
        || morra "${RC_PATCH}" "o debian/control do Pop não pede o libcamera-dev"
    sed -i -E '/^[[:space:]]+libcamera-dev /d' "${d}/control"
    grep -qx 'Package: libspa-0.2-libcamera' "${d}/control" \
        || morra "${RC_PATCH}" "o debian/control do Pop não traz o libspa-0.2-libcamera"
    awk 'BEGIN { RS = ""; ORS = "\n\n" } !/^Package: (libspa-0\.2-libcamera|pipewire-libcamera)\n/' \
        "${d}/control" > "${d}/control.novo"
    mv -f "${d}/control.novo" "${d}/control"
    rm -f "${d}/libspa-0.2-libcamera."* "${d}/pipewire-libcamera."*
}

ajustar_wireplumber() {
    local arvore="$1" d="$1/debian" p simbolos novos
    # 1. o Pop é formato nativo: o patch dele está no fonte da 0.5.12, e não no
    #    da 0.5.18. A série do debian/patches se aplica aqui, à mão.
    if [[ -f "${d}/patches/series" ]]; then
        while read -r p; do
            [[ -n "${p}" && "${p}" != \#* ]] || continue
            aplicar "${arvore}" "${d}/patches/${p}"
        done < "${d}/patches/series"
    fi
    # 2. o dh_makeshlibs do Pop roda com -c4: os 38 símbolos novos da 0.5.13 à
    #    0.5.16 entram no arquivo de símbolos.
    simbolos="${d}/libwireplumber-0.5-0.symbols"
    novos="${ASSETS}/debian/libwireplumber-0.5-0.symbols.novos"
    conferir_sha "${novos}" "$(ler WP_SIMBOLOS_NOVOS_SHA256)" "${novos##*/}"
    [[ "$(grep -c '^[^ *]' "${simbolos}")" -eq 1 ]] \
        || morra "${RC_PATCH}" "${simbolos##*/} não tem uma biblioteca só: o acréscimo no fim não vale"
    cat "${novos}" >> "${simbolos}"
    # 3. a 0.5.18 instala o completar do wpctl no bash (src/tools/meson.build), e
    #    o dh_missing do compat 13 reprova arquivo instalado sem pacote.
    if grep -q 'bash-completion/completions' "${arvore}/src/tools/meson.build"; then
        printf 'usr/share/bash-completion/completions/wpctl\n' >> "${d}/wireplumber.install"
    fi
    # 4. o control do Pop pede o meson-1.5, o do pipewire pede o meson-1.7, e os
    #    dois pacotes do noble conflitam: não há casa que tenha as duas build-deps.
    #    A 0.5.18 pede meson >= 0.59.0, e o build das duas sai com o 1.7.
    grep -q -E '^[[:space:]]+meson-1\.5,$' "${d}/control" \
        || morra "${RC_PATCH}" "o debian/control do Pop não pede o meson-1.5"
    sed -i -E 's/^([[:space:]]+)meson-1\.5,$/\1meson-1.7,/' "${d}/control"
}

preparar() {
    local p sha
    command -v dpkg-parsechangelog >/dev/null || morra "${RC_DEPS}" "falta o dpkg-dev (dpkg-parsechangelog)"
    command -v patch >/dev/null || morra "${RC_DEPS}" "falta o patch"
    # A obra é refeita do zero: é isso que faz duas corridas darem a mesma árvore.
    [[ "${OBRA}" == */pipewire-obra ]] || morra "${RC_USO}" "obra fora do lugar: ${OBRA}"
    rm -rf "${OBRA}"
    mkdir -p "${OBRA}"

    montar PW "pipewire-${PW_VERSAO}"
    conferir_sha "${PW_ARVORE}/src/modules/module-metadata/metadata.c" \
        "$(ler PW_SHA256_METADATA_C)" "o metadata.c do tarball" "${RC_FONTE}"
    ajustar_pipewire "${PW_ARVORE}"
    for p in $(ler PW_PATCHES); do
        [[ -f "${ASSETS}/patches/${p}" ]] || morra "${RC_PATCH}" "falta assets/pipewire-backport/patches/${p}"
        sha="$(ler "PATCH_${p}")"
        conferir_sha "${ASSETS}/patches/${p}" "${sha}" "${p}"
        aplicar "${PW_ARVORE}" "${ASSETS}/patches/${p}"
    done
    escrever_changelog "${PW_ARVORE}" "${ASSETS}/debian/changelog.pipewire.hefesto" "$(ler PW_REVISAO)"
    conferir_metadata "${PW_ARVORE}/src/modules/module-metadata/metadata.c"

    montar WP "wireplumber-${WP_VERSAO}"
    ajustar_wireplumber "${WP_ARVORE}"
    escrever_changelog "${WP_ARVORE}" "${ASSETS}/debian/changelog.wireplumber.hefesto" "$(ler WP_REVISAO)"
    diga "árvores prontas: ${PW_ARVORE} ($(ler PW_REVISAO)) e ${WP_ARVORE} ($(ler WP_REVISAO))"
}

# O servidor da árvore, compilado no mínimo (sem ALSA, Bluetooth, câmera nem
# documentação), num prefixo dentro da obra. Só precisa de meson, ninja e gcc.
compilar_o_servidor() {
    local fonte="$1" destino="$2"
    if ! meson setup --prefix="${destino}" -Dauto_features=disabled '-Dsession-managers=[]' \
            -Dexamples=disabled -Dtests=disabled -Ddocs=disabled -Dman=disabled \
            -Dspa-plugins=enabled -Dsupport=enabled -Daudioconvert=enabled \
            -Dpipewire-alsa=disabled -Dpipewire-jack=disabled -Dpipewire-v4l2=disabled \
            "${destino}.build" "${fonte}" > "${destino}.log" 2>&1 \
        || ! ninja -C "${destino}.build" -j"${JOBS}" >> "${destino}.log" 2>&1 \
        || ! meson install -C "${destino}.build" >> "${destino}.log" 2>&1; then
        tail -n 20 "${destino}.log" >&2
        morra "${RC_BUILD}" "o servidor da prova não compilou (log em ${destino}.log)"
    fi
}

provar() {
    local sem_cura="${OBRA}/prova-sem-cura" metadata saida rc p
    for p in meson ninja gcc wireplumber wpctl; do
        command -v "${p}" >/dev/null || morra "${RC_DEPS}" "a prova precisa do ${p} no PATH"
    done
    diga "compilando o servidor da árvore (log em ${OBRA}/prova-com-cura.log)"
    compilar_o_servidor "${PW_ARVORE}" "${OBRA}/prova-com-cura"
    # A mordida: a mesma árvore, sem a linha da cura. Se esta não pendura, a
    # prova não mede nada.
    rm -rf "${sem_cura}.fonte"
    cp -a "${PW_ARVORE}" "${sem_cura}.fonte"
    metadata="${sem_cura}.fonte/src/modules/module-metadata/metadata.c"
    awk '
        /^static void global_unbind\(void \*data\)/ { dentro = 1 }
        dentro && /^}/ { dentro = 0 }
        dentro && /^[[:space:]]*remove_pending\(d\);[[:space:]]*$/ { next }
        { print }
    ' "${metadata}" > "${metadata}.novo"
    mv -f "${metadata}.novo" "${metadata}"
    ! tem_a_cura "${metadata}" || morra "${RC_PROVA}" "a mordida não tirou a cura do metadata.c"
    diga "compilando o mesmo servidor sem a cura (log em ${sem_cura}.log)"
    compilar_o_servidor "${sem_cura}.fonte" "${sem_cura}"

    rc=0
    saida="$(bash "${ASSETS}/prova/reproduzir.sh" "${OBRA}/prova-com-cura" 2>/dev/null)" || rc=$?
    diga "com a cura: ${saida:-sem saída} (rc=${rc})"
    [[ "${rc}" -eq 0 ]] || morra "${RC_PROVA}" "com a cura, a prova não deu 0 pendurados"
    rc=0
    saida="$(bash "${ASSETS}/prova/reproduzir.sh" "${sem_cura}" 2>/dev/null)" || rc=$?
    diga "sem a cura: ${saida:-sem saída} (rc=${rc})"
    [[ "${rc}" -eq 1 ]] || morra "${RC_PROVA}" "sem a cura, a prova não pendurou: ela não mede nada"
}

checar_dependencias() {
    local arvore falta faltou=0
    command -v dpkg-buildpackage >/dev/null || morra "${RC_DEPS}" "falta o dpkg-dev (dpkg-buildpackage)"
    for arvore in "${PW_ARVORE}" "${WP_ARVORE}"; do
        if ! falta="$(cd "${arvore}" && dpkg-checkbuilddeps 2>&1)"; then
            printf '%s: %s\n' "${arvore##*/}" "${falta}" >&2
            printf '[pipewire-backport] quem tem sudo instala e roda de novo:\n' >&2
            printf '    cd %s && sudo mk-build-deps -ir debian/control\n' "${arvore}" >&2
            faltou=1
        fi
    done
    [[ "${faltou}" -eq 0 ]] || morra "${RC_DEPS}" "faltam dependências de build (acima)"
}

compilar() {
    local arvore
    for arvore in "${PW_ARVORE}" "${WP_ARVORE}"; do
        diga "dpkg-buildpackage -b -us -uc em ${arvore##*/} (log em ${arvore}.build.log)"
        if ! (cd "${arvore}" && "${AMBIENTE_LIMPO[@]}" dpkg-buildpackage -b -us -uc -j"${JOBS}") \
                > "${arvore}.build.log" 2>&1; then
            tail -n 40 "${arvore}.build.log" >&2
            morra "${RC_BUILD}" "o build de ${arvore##*/} falhou (log em ${arvore}.build.log)"
        fi
    done
}

origem() {
    local p
    printf 'pipewire=%s upstream %s %s empacotamento %s\n' "$(ler PW_REVISAO)" \
        "$(ler PW_VERSAO_UPSTREAM)" "$(ler PW_FONTE_SHA256)" "$(ler PW_EMPACOTAMENTO_VERSAO)"
    for p in $(ler PW_PATCHES); do
        printf 'patch=%s %s\n' "${p}" "$(sha_de "${ASSETS}/patches/${p}")"
    done
    printf 'wireplumber=%s upstream %s %s empacotamento %s\n' "$(ler WP_REVISAO)" \
        "$(ler WP_VERSAO_UPSTREAM)" "$(ler WP_FONTE_SHA256)" "$(ler WP_EMPACOTAMENTO_VERSAO)"
    printf 'changelogs=%s %s\n' "$(sha_de "${ASSETS}/debian/changelog.pipewire.hefesto")" \
        "$(sha_de "${ASSETS}/debian/changelog.wireplumber.hefesto")"
    printf 'construido_por=scripts/construir_pipewire_backport.sh\n'
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

entregar() {
    local deb tmp so_do_metadata n=0
    mkdir -p "${SAIDA}"
    rm -f "${SAIDA}"/*.deb
    for deb in "${OBRA}"/*_"$(ler PW_REVISAO)"_*.deb "${OBRA}"/*_"$(ler WP_REVISAO)"_*.deb; do
        [[ -f "${deb}" ]] || continue
        cp -f "${deb}" "${SAIDA}/"
        n=$((n + 1))
    done
    [[ "${n}" -gt 0 ]] || morra "${RC_BUILD}" "o build não produziu .deb nenhum"
    # A cura tem de estar no módulo que vai para o cache: o metadata.c da obra
    # foi conferido, e o .so que saiu dele tem de existir no pacote.
    tmp="$(mktemp -d)"
    dpkg-deb -x "${SAIDA}/libpipewire-0.3-modules_$(ler PW_REVISAO)_$(dpkg --print-architecture).deb" "${tmp}" \
        || morra "${RC_BUILD}" "não achei o libpipewire-0.3-modules construído"
    so_do_metadata="$(find "${tmp}" -name 'libpipewire-module-metadata.so' -print -quit)"
    rm -rf "${tmp}"
    [[ -n "${so_do_metadata}" ]] || morra "${RC_BUILD}" "o libpipewire-0.3-modules construído não traz o módulo de metadata"
    (cd "${SAIDA}" && sha256sum -- *.deb > SHA256SUMS.novo)
    mv -f "${SAIDA}/SHA256SUMS.novo" "${SAIDA}/SHA256SUMS"
    origem > "${SAIDA}/ORIGEM.txt"
    diga "entregue em ${SAIDA}: ${n} pacotes"
}

main() {
    local modo="construir" forcar=0
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --forcar) forcar=1 ;;
            --preparar) modo="preparar" ;;
            --prova) modo="prova" ;;
            --conferir-metadata)
                [[ $# -ge 2 ]] || morra "${RC_USO}" "--conferir-metadata pede o caminho de um metadata.c"
                conferir_metadata "$2"
                exit 0
                ;;
            -h | --help)
                sed -n '2,/^set -euo/p' "${BASH_SOURCE[0]}" | sed '$d'
                exit 0
                ;;
            *) morra "${RC_USO}" "argumento desconhecido: $1" ;;
        esac
        shift
    done

    [[ "${EUID}" -ne 0 ]] || morra "${RC_USO}" "não rode como root: o HOME vira /root"
    [[ -f "${BASELINE}" ]] || morra "${RC_USO}" "não achei ${BASELINE}"
    [[ "${JOBS}" =~ ^[1-9][0-9]*$ ]] || morra "${RC_USO}" "HEFESTO_PIPEWIRE_JOBS inválido: ${JOBS} (um inteiro a partir de 1)"
    PW_VERSAO="$(ler PW_VERSAO_UPSTREAM)"
    WP_VERSAO="$(ler WP_VERSAO_UPSTREAM)"
    PW_ARVORE="${OBRA}/pipewire-${PW_VERSAO}"
    WP_ARVORE="${OBRA}/wireplumber-${WP_VERSAO}"

    if [[ "${modo}" == "construir" && "${forcar}" -eq 0 ]] && ja_construido; then
        diga "já construído em ${SAIDA}: SHA256SUMS e ORIGEM.txt conferem — nada a fazer (--forcar reconstrói)"
        exit 0
    fi

    preparar
    case "${modo}" in
        preparar) exit 0 ;;
        prova)
            provar
            exit 0
            ;;
    esac
    checar_dependencias
    compilar
    entregar
}

main "$@"
