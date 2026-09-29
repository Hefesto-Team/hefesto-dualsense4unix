#!/usr/bin/env bash
# CI-INSTALL-USUARIA-01 — executa o `install.sh` DE VERDADE, dentro do
# contêiner da distro, COMO USUÁRIA COMUM.
#
# POR QUE ISTO EXISTE, e a data importa: em 19/08/2026 a leva que tornou o
# `install.sh` universal (apt/dnf/pacman) trouxe junto um BLOQUEANTE que teria
# quebrado o Debian 12 para toda pessoa que instala sem ser root. A régua de
# biblioteca perguntava ao `ldconfig`, que mora em `/usr/sbin` — fora do PATH
# de usuária comum no Debian 12, dentro do PATH do root em qualquer distro.
# Medido na bancada, com o PATH de login de uma pessoa real:
#
#     libhidapi-hidraw.so.0: AUSENTE (falso!)
#     libopus.so.0:          AUSENTE (falso!)
#
# NENHUM PORTÃO VIU, por três razões que este arquivo conserta de uma vez:
#   1. o `smoke-multi-distro` instala o WHEEL e nunca toca no `install.sh`;
#   2. os contêineres dele rodam como ROOT, e o PATH do root tem `sbin`;
#   3. o único portão que olhava para o `install.sh` era o `shellcheck`, que é
#      análise estática e não executa uma linha.
#
# O QUE ESTE SCRIPT GARANTE, e cada garantia é a resposta a um desses buracos:
#   - roda como usuária SEM privilégio, com `sudo` sem senha (o instalador
#     chama `sudo` por dentro; ele NUNCA é chamado COM `sudo`, senão o `HOME`
#     viraria `/root`);
#   - com o PATH de LOGIN dessa usuária — não o herdado do root. Há sentinela
#     que reprova se o ambiente do CI vazar para dentro da sessão;
#   - reprova quando o instalador reprova (código de saída), e também quando
#     ele DIZ que vai instalar algo que já está presente no contêiner — que era
#     exatamente o sintoma do bloqueante.
#
# Uso (dentro do contêiner, como root):
#     scripts/ci/instalar_como_usuaria.sh --presente hidapi
#     scripts/ci/instalar_como_usuaria.sh --fontes pop --so-fontes
#     scripts/ci/instalar_como_usuaria.sh --so-dkms
#
#   --fontes pop  antes de tudo, põe o repositório do Pop!_OS sobre o
#                 ubuntu:24.04, com a chave conferida pela impressão digital:
#                 é o Pop sem a parte gráfica, a distro onde o produto é medido
#   --so-fontes   só prepara as fontes e sai (o smoke do wheel usa)
#   --so-dkms     não instala nada do produto: instala o dkms e os headers mais
#                 novos da distro e roda o `dkms build -k` de cada módulo de
#                 assets/dkms/. Código 77 é o BUILD_EXCLUSIVE_KERNEL recusando
#                 um kernel fora do pino, de propósito; qualquer outro código
#                 diferente de 0 reprova
#
# Variáveis:
#     HEFESTO_CI_USUARIA   nome da usuária criada (default: jogadora)
#     HEFESTO_CI_LOG       caminho do log (default: /tmp/install-como-usuaria.log)
#     HEFESTO_CI_FLAGS     flags EXTRAS para o install.sh, além do `--yes`. Existe
#                          por CUSTO, não por conveniência: o passo `11c` baixa
#                          492 MB de Proton em cada contêiner (medido em
#                          19/08/2026), e `--no-proton-pin` corta isso. Nada de
#                          `--no-*` para calar um passo que reprova — aí o
#                          portão vira decoração.

set -euo pipefail

USUARIA="${HEFESTO_CI_USUARIA:-jogadora}"
LOG="${HEFESTO_CI_LOG:-/tmp/install-como-usuaria.log}"
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# Nomes canônicos do censo (`_DEPS_DE_SISTEMA`, em install.sh) que o contêiner
# JÁ instalou antes desta chamada. Se o instalador disser que falta um deles, a
# régua dele está cega — é o bloqueante voltando.
PRESENTES=()
FONTES=""
SO_FONTES=0
SO_DKMS=0

# A chave que assina o repositório do Pop!_OS (Pop OS ISO Signing Key). A
# impressão digital é a da chave instalada num Pop!_OS 24.04, conferida em
# 28/09/2026; a chave baixada que não bater com ela reprova.
POP_CHAVE="63C46DF0140D738961429F4E204DD8AEC33A7AFF"

# Sentinela do vazamento de ambiente: se esta variável aparecer dentro da
# sessão de login, o `su -` deixou de trocar o ambiente e o PATH que medimos é
# o do CI, não o de uma pessoa real. O portão volta a ser cego, e cego é pior
# que ausente — por isso reprova em vez de avisar.
export HEFESTO_CI_SENTINELA_DE_AMBIENTE="vazou-do-ci"

while (( $# )); do
    case "$1" in
        --presente)  PRESENTES+=("$2"); shift 2 ;;
        --presente=*) PRESENTES+=("${1#*=}"); shift ;;
        --fontes)    FONTES="$2"; shift 2 ;;
        --so-fontes) SO_FONTES=1; shift ;;
        --so-dkms)   SO_DKMS=1; shift ;;
        -h|--help)   sed -n '2,53p' "${BASH_SOURCE[0]}"; exit 0 ;;
        *) printf 'ERRO: argumento desconhecido: %s\n' "$1" >&2; exit 2 ;;
    esac
done

titulo() { printf '\n=== %s ===\n' "$*"; }
falha()  { printf '\nREPROVADO: %s\n' "$*" >&2; exit 1; }

[[ "$(id -u)" -eq 0 ]] || falha "este script prepara o contêiner e precisa começar como root (ele é quem CRIA a usuária comum; o install.sh é que roda sem privilégio)"

# ---------------------------------------------------------------------------
# 1. Família de pacotes — a mesma pergunta que o install.sh faz, pelo os-release
# ---------------------------------------------------------------------------
familia="nenhum"
if [[ -r /etc/os-release ]]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    case " ${ID:-} ${ID_LIKE:-} " in
        *" debian "*|*" ubuntu "*) familia="apt" ;;
        *" fedora "*|*" rhel "*)   familia="dnf" ;;
        *" arch "*)                familia="pacman" ;;
    esac
fi
[[ "${familia}" != "nenhum" ]] || falha "não reconheço o gerenciador de pacotes desta imagem (ID=${ID:-?})"

titulo "contêiner: ${PRETTY_NAME:-?} (família ${familia})"

# ---------------------------------------------------------------------------
# 1b. As fontes do Pop!_OS, quando pedidas
#
# O repositório `release` do Pop por cima do ubuntu:24.04: traz o kernel, os
# headers e os pacotes que o Pop troca. A chave vem do servidor de chaves do
# Ubuntu e só vale se a impressão digital for a de POP_CHAVE.
# ---------------------------------------------------------------------------
preparar_fontes_do_pop() {
    [[ "${familia}" == apt && "${ID:-}" == ubuntu ]] \
        || falha "--fontes pop só vale sobre uma imagem do Ubuntu (ID=${ID:-?})"
    titulo "fontes do Pop!_OS sobre o ${PRETTY_NAME:-?}"
    apt-get update -qq && apt-get install -y -qq ca-certificates curl gnupg >/dev/null
    local chave=/usr/share/keyrings/pop-os-release.gpg
    curl -fsSL --retry 3 \
        "https://keyserver.ubuntu.com/pks/lookup?op=get&options=mr&search=0x${POP_CHAVE}" \
        | gpg --dearmor > "${chave}"
    gpg --show-keys --with-colons "${chave}" | grep -q "^fpr:::::::::${POP_CHAVE}:" \
        || falha "a chave baixada não tem a impressão digital do Pop (${POP_CHAVE})"
    cat > /etc/apt/sources.list.d/pop-os-release.sources <<FONTES
Types: deb
URIs: http://apt.pop-os.org/release
Suites: ${VERSION_CODENAME:-noble}
Components: main
Signed-By: ${chave}
FONTES
    apt-get update -qq
    printf 'repositório do Pop ligado (chave %s)\n' "${POP_CHAVE}"
}

case "${FONTES}" in
    "") ;;
    pop) preparar_fontes_do_pop ;;
    *) falha "--fontes só conhece «pop» (pediram «${FONTES}»)" ;;
esac
(( SO_FONTES == 0 )) || exit 0

# ---------------------------------------------------------------------------
# 1c. O `dkms build -k` de cada módulo contra os headers desta distro
#
# Responde a uma pergunta que o install no contêiner não alcança: o fonte de
# cada módulo compila contra o kernel desta distro, e o pino de kernel recusa o
# que não foi conferido? O kernel é o dos headers mais novos que a distro
# oferece (o do contêiner é o do runner, que não interessa).
# ---------------------------------------------------------------------------
dkms_contra_os_headers() {
    titulo "o dkms build -k de cada módulo contra os headers da distro"
    case "${familia}" in
        apt)
            apt-get update -qq
            local pacote=linux-headers-amd64
            if [[ "${ID:-}" != debian ]]; then
                pacote="$(apt-cache search --names-only '^linux-headers-[0-9].*-generic$' \
                    | awk '{print $1}' | sort -V | tail -1)"
            fi
            [[ -n "${pacote}" ]] || falha "a distro não oferece headers de kernel"
            apt-get install -y -qq dkms build-essential "${pacote}" >/dev/null ;;
        dnf)
            dnf install -y -q dkms kernel-devel make gcc elfutils-libelf-devel >/dev/null ;;
        pacman)
            pacman -Sy --noconfirm --needed dkms linux-headers base-devel >/dev/null ;;
    esac
    local k=""
    if [[ -d /usr/src/kernels ]]; then
        # O kernel-devel do Fedora não traz o /lib/modules/<k>/build: é o
        # kernel-core que o traz, e ele não entra num contêiner.
        k="$(ls /usr/src/kernels | sort -V | tail -1)"
        [[ -n "${k}" ]] && mkdir -p "/lib/modules/${k}" \
            && ln -sfn "/usr/src/kernels/${k}" "/lib/modules/${k}/build"
    else
        k="$(ls /lib/modules | sort -V | tail -1)"
    fi
    [[ -n "${k}" && -e "/lib/modules/${k}/build/Makefile" ]] \
        || falha "os headers instalados não deixaram um /lib/modules/<k>/build"
    printf 'kernel dos headers: %s\n' "${k}"
    local conf dir nome ver rc reprovados=()
    for conf in "${RAIZ}"/assets/dkms/*/dkms.conf; do
        dir="$(dirname "${conf}")"
        nome="$(sed -n 's/^PACKAGE_NAME="\{0,1\}\([^"]*\)"\{0,1\}$/\1/p' "${conf}")"
        ver="$(sed -n 's/^PACKAGE_VERSION="\{0,1\}\([^"]*\)"\{0,1\}$/\1/p' "${conf}")"
        rm -rf "/usr/src/${nome}-${ver}"
        cp -a "${dir}" "/usr/src/${nome}-${ver}"
        dkms add -m "${nome}" -v "${ver}" >/dev/null 2>&1 || true
        set +e
        dkms build -m "${nome}" -v "${ver}" -k "${k}" > "/tmp/dkms-${nome}.log" 2>&1
        rc=$?
        set -e
        case "${rc}" in
            0)  printf '  %-26s compila (rc 0)\n' "${nome}" ;;
            77) printf '  %-26s fora do pino de kernel, de propósito (rc 77)\n' "${nome}" ;;
            *)  printf '  %-26s NÃO compila (rc %s); o fim do log:\n' "${nome}" "${rc}"
                tail -15 "/tmp/dkms-${nome}.log" | sed 's/^/      /'
                reprovados+=("${nome}") ;;
        esac
        if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then
            printf -- '- `%s` contra `%s`: rc %s\n' "${nome}" "${k}" "${rc}" >> "${GITHUB_STEP_SUMMARY}"
        fi
    done
    (( ${#reprovados[@]} == 0 )) \
        || falha "módulo(s) que não compilam contra ${k}: ${reprovados[*]}"
    titulo "APROVADO: todo módulo compila ou é recusado pelo pino em ${k}"
}

if (( SO_DKMS )); then
    dkms_contra_os_headers
    exit 0
fi

# ---------------------------------------------------------------------------
# 2. O mínimo para EXISTIR uma usuária comum com sudo
#
# Só isto — nada do censo do produto. O que o install.sh tem de instalar é
# trabalho DELE, e é justamente o que este job mede.
# ---------------------------------------------------------------------------
titulo "preparando a usuária comum"
case "${familia}" in
    apt)    apt-get update -qq && apt-get install -y -qq sudo passwd >/dev/null ;;
    dnf)    dnf install -y -q sudo shadow-utils >/dev/null ;;
    pacman) pacman -Sy --noconfirm --needed sudo shadow >/dev/null ;;
esac

id -u "${USUARIA}" >/dev/null 2>&1 || useradd --create-home --shell /bin/bash "${USUARIA}"
printf '%s ALL=(ALL) NOPASSWD: ALL\n' "${USUARIA}" > "/etc/sudoers.d/99-${USUARIA}-ci"
chmod 0440 "/etc/sudoers.d/99-${USUARIA}-ci"

# A árvore veio do checkout como root. Uma pessoa real é dona do próprio clone.
chown -R "${USUARIA}:${USUARIA}" "${RAIZ}"

# ---------------------------------------------------------------------------
# 3. O PATH que uma pessoa real teria — e a prova de que é ele mesmo
# ---------------------------------------------------------------------------
titulo "ambiente de login da usuária"
printf 'PATH do root nesta sessão:\n  %s\n' "${PATH}"

path_login="$(su - "${USUARIA}" -s /bin/bash -c 'printf "%s" "${PATH}"')"
printf 'PATH de login de %s:\n  %s\n' "${USUARIA}" "${path_login}"

vazou="$(su - "${USUARIA}" -s /bin/bash -c 'printf "%s" "${HEFESTO_CI_SENTINELA_DE_AMBIENTE:-}"')"
[[ -z "${vazou}" ]] || falha "o ambiente do CI vazou para a sessão de login (HEFESTO_CI_SENTINELA_DE_AMBIENTE=${vazou}) — o PATH medido não é o de uma pessoa real, e o portão ficaria cego"

if su - "${USUARIA}" -s /bin/bash -c 'command -v ldconfig' >/dev/null 2>&1; then
    printf 'ldconfig ALCANÇÁVEL no PATH de login (nesta distro `sbin` é visível para todo mundo)\n'
else
    printf 'ldconfig FORA do PATH de login — é exatamente a condição do bloqueante de 19/08/2026\n'
fi

# ---------------------------------------------------------------------------
# 4. O install.sh, de verdade
#
# `--yes` porque não há TTY. NUNCA com `sudo` na frente: o `HOME` viraria
# `/root` e o instalador escreveria a casa da pessoa no lugar errado.
# Sem `|| true` em lugar nenhum: o código de saída é o portão.
# ---------------------------------------------------------------------------
titulo "executando ./install.sh --yes como ${USUARIA}"
inicio="${SECONDS}"
# `| tee` e não `> >(tee ...)`: a substituição de processo é assíncrona e o log
# podia ser lido pela metade logo abaixo. Com o cano, o código que interessa é
# o do `su`, não o do `tee` — daí o `PIPESTATUS[0]`.
set +e
su - "${USUARIA}" -s /bin/bash -c "cd '${RAIZ}' && ./install.sh --yes ${HEFESTO_CI_FLAGS:-}" 2>&1 | tee "${LOG}"
retorno="${PIPESTATUS[0]}"
set -e
duracao=$(( SECONDS - inicio ))
printf '\ninstall.sh terminou com código %d em %ds\n' "${retorno}" "${duracao}"

motivos=()
if (( retorno != 0 )); then
    printf '\n--- últimas 40 linhas do log ---\n'
    tail -40 "${LOG}" || true
    motivos+=("o install.sh saiu com código ${retorno}")
fi

# ---------------------------------------------------------------------------
# 5. A régua que pega o bloqueante SEM depender do código de saída
#
# O sintoma dele não era morrer: era o instalador ANUNCIAR que falta o que já
# está lá — e pedir sudo para instalar de novo. A linha do install.sh é
#     `      falta <canônico> — sem ele, <razão>`
# Só conferimos os nomes que ESTE contêiner comprovadamente instalou antes de
# chamar o instalador; nada é inferido.
#
# Roda mesmo quando o código de saída já reprovou, de propósito: as duas réguas
# olham para coisas diferentes, e o relatório de uma corrida vermelha tem de
# dizer as DUAS respostas — senão a segunda só aparece na corrida seguinte.
# ---------------------------------------------------------------------------
if (( ${#PRESENTES[@]} )); then
    titulo "conferindo que o instalador não pediu o que já estava instalado"
    cegueira=()
    for canon in "${PRESENTES[@]}"; do
        if grep -qE "^[[:space:]]*falta ${canon} " "${LOG}"; then
            printf 'CEGO: o instalador declarou "falta %s" — e o contêiner instalou isso antes de chamá-lo\n' "${canon}"
            grep -nE "^[[:space:]]*falta ${canon} " "${LOG}" || true
            cegueira+=("${canon}")
        else
            printf 'ok: o instalador não pediu %s (já presente, e ele enxergou)\n' "${canon}"
        fi
    done
    (( ${#cegueira[@]} == 0 )) || motivos+=("a régua de presença do install.sh está cega para: ${cegueira[*]}")
fi

if (( ${#motivos[@]} )); then
    printf '\n'
    for motivo in "${motivos[@]}"; do
        printf '  - %s\n' "${motivo}"
    done
    falha "o install.sh não passa como usuária comum em ${PRETTY_NAME:-esta distro}"
fi

titulo "APROVADO: o install.sh rodou como usuária comum em ${PRETTY_NAME:-esta distro}"
