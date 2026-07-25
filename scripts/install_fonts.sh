#!/usr/bin/env bash
# install_fonts.sh — instala as duas fontes da identidade visual do Hefesto.
#
# POR QUE ISTO EXISTE
# ------------------
# O `gui/theme.css` pede "Space Grotesk" na interface e "JetBrains Mono" nos
# valores/logs — os nomes que o guia de identidade (`novo-layout/`) define. Numa
# máquina limpa NENHUMA das duas existe: aqui, com 797 fontes instaladas, o
# `fc-match` caía em Noto Sans para as DUAS. Ou seja, a interface nunca era a do
# design e nada indicava isso: fontconfig substitui em silêncio.
#
# Nada QUEBRA sem as fontes (a cadeia do CSS tem fallback). O que muda é a
# interface ficar igual ao mockup — e o monoespaçado dos valores/log virar um
# monoespaçado de verdade em vez do que a distribuição tiver sorteado.
#
# ORDEM DE PREFERÊNCIA (a decisão de projeto)
# -------------------------------------------
#   1. PACOTE DA DISTRIBUIÇÃO. É o caminho preferido: vem assinado pelo
#      repositório, entra no gerenciador de pacotes e sai por ele. As duas
#      fontes estão empacotadas no Debian/Ubuntu (logo, Pop!_OS):
#      `fonts-space-grotesk-ttf` e `fonts-jetbrains-mono`.
#   2. DOWNLOAD DIRETO, só se (1) não der. Os arquivos vêm do repositório
#      oficial do Google Fonts, sob OFL 1.1, PINADOS num commit específico e
#      conferidos por SHA-256 — commit pinado + checksum é o que transforma um
#      "baixar da internet no install" em algo auditável: o byte que chega é o
#      byte revisado aqui. Instala em ~/.local/share/fonts (usuário, sem root).
#
# Por que NÃO vendorizar os .ttf no repositório: caberia (são 3 arquivos
# variáveis, ~0,5 MB no total — 133 KB do Space Grotesk + 183 KB do JetBrains
# Mono + 187 KB do itálico), e a OFL 1.1 permite redistribuir. Mas colocar
# binário de terceiro no git significa carregar a licença, o aviso de
# copyright e o dever de atualizar a fonte junto com o upstream para sempre,
# num repositório que hoje não tem NENHUM binário. Como a distribuição já
# empacota as duas, vendorizar seria assumir esse custo permanente para cobrir
# só o caso raro de máquina sem pacote e sem rede — e nesse caso o fallback do
# CSS já resolve. Se um dia a decisão mudar, o custo é este: ~0,5 MB e dois
# OFL.txt em assets/fonts/.
#
# USO
#   scripts/install_fonts.sh              # instala (pacote da distro, senão baixa)
#   scripts/install_fonts.sh --status     # só relata o que está instalado
#   scripts/install_fonts.sh --uninstall  # remove o que ESTE script instalou
#   scripts/install_fonts.sh --no-download# nunca sai para a rede (CI, offline)
#   scripts/install_fonts.sh --yes        # não pergunta nada (headless)
#
# SAÍDA: 0 mesmo quando não consegue instalar. Fonte é acabamento, não
# requisito — fazer o install.sh inteiro falhar por causa disso seria trocar um
# problema cosmético por um problema real.

set -euo pipefail

readonly DEST_DIR="${HOME}/.local/share/fonts/hefesto-dualsense4unix"
readonly PIN_COMMIT="7ff85c87f93ea6cca5f41c69f2e4edcb90240f26"
readonly RAW_BASE="https://raw.githubusercontent.com/google/fonts/${PIN_COMMIT}"

# arquivo|caminho no google/fonts|sha256
readonly FONTES=(
  "SpaceGrotesk[wght].ttf|ofl/spacegrotesk/SpaceGrotesk%5Bwght%5D.ttf|acad6de1fc93436f5c0f1f4137751ef04f1aea3063e7036535970ffcfbd79f72"
  "JetBrainsMono[wght].ttf|ofl/jetbrainsmono/JetBrainsMono%5Bwght%5D.ttf|48715a42ec242c21e9f02692891e147d022299a52e48d5e413e1a942193ffeda"
  "JetBrainsMono-Italic[wght].ttf|ofl/jetbrainsmono/JetBrainsMono-Italic%5Bwght%5D.ttf|85ae2a5cd3f56baf1ce1c21a851322c58e3d8fbe8e8ad4a4d090a820dd7fe558"
)
readonly LICENCAS=(
  "OFL-SpaceGrotesk.txt|ofl/spacegrotesk/OFL.txt"
  "OFL-JetBrainsMono.txt|ofl/jetbrainsmono/OFL.txt"
)

# Famílias como o fontconfig as enxerga — é por este nome que o theme.css pede.
readonly FAMILIA_UI="Space Grotesk"
readonly FAMILIA_MONO="JetBrains Mono"

MODO="instalar"
PERMITE_DOWNLOAD=1
ASSUME_SIM=0

info()  { printf '  %s\n' "$*"; }
ok()    { printf '  [ OK ] %s\n' "$*"; }
warn()  { printf '  [aviso] %s\n' "$*" >&2; }

uso() {
    sed -n '2,50p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --status)      MODO="status" ;;
        --uninstall|--remove) MODO="remover" ;;
        --no-download) PERMITE_DOWNLOAD=0 ;;
        --yes|-y)      ASSUME_SIM=1 ;;
        -h|--help)     uso; exit 0 ;;
        *) warn "opção desconhecida: $1"; uso; exit 0 ;;
    esac
    shift
done

# ---------------------------------------------------------------------------
# Detecção. `fc-list` é a única verdade: pouco importa QUEM instalou a fonte
# (pacote, este script, ou a usuária na mão) — se o fontconfig acha a família,
# o GTK vai achar também.
# ---------------------------------------------------------------------------
# ARMADILHA: `grep -q` NÃO pode fechar este pipe. O script roda com
# `pipefail`, e o `-q` sai no primeiro casamento => SIGPIPE no `fc-list`/`tr`
# => a pipeline inteira devolve 141 e a função dizia "fonte ausente" para uma
# fonte que ESTAVA instalada. Sem `-q` o grep consome tudo e o status é o dele.
tem_familia() {
    local familia="$1"
    command -v fc-list >/dev/null 2>&1 || return 1
    fc-list : family 2>/dev/null | tr ',' '\n' | grep -ixF "${familia}" >/dev/null
}

relatar() {
    local faltando=0
    for f in "${FAMILIA_UI}" "${FAMILIA_MONO}"; do
        if tem_familia "${f}"; then
            ok "${f} disponível"
        else
            warn "${f} AUSENTE — a interface cai para a fonte padrão do sistema"
            faltando=1
        fi
    done
    return "${faltando}"
}

# ---------------------------------------------------------------------------
# Caminho 1: pacote da distribuição.
# ---------------------------------------------------------------------------
sudo_disponivel() {
    command -v sudo >/dev/null 2>&1 || return 1
    # Sem TTY, só serve se já houver ticket ou NOPASSWD (o install.sh headless
    # depende disso; pedir senha aqui travaria o script para sempre).
    if [[ "${ASSUME_SIM}" == "1" ]] || [[ ! -t 0 ]]; then
        sudo -n true 2>/dev/null
        return $?
    fi
    return 0
}

instalar_por_pacote() {
    local pacotes=()
    if command -v apt-get >/dev/null 2>&1; then
        tem_familia "${FAMILIA_UI}"   || pacotes+=("fonts-space-grotesk-ttf")
        tem_familia "${FAMILIA_MONO}" || pacotes+=("fonts-jetbrains-mono")
        [[ ${#pacotes[@]} -eq 0 ]] && return 0
        sudo_disponivel || { warn "sem sudo não-interativo — pulando o pacote da distro"; return 1; }
        info "instalando pelo apt: ${pacotes[*]}"
        sudo -n apt-get install -y "${pacotes[@]}" >/dev/null 2>&1 || return 1
        return 0
    fi
    if command -v dnf >/dev/null 2>&1; then
        tem_familia "${FAMILIA_MONO}" || pacotes+=("jetbrains-mono-fonts")
        # O Fedora não empacota Space Grotesk: essa fica para o download.
        [[ ${#pacotes[@]} -eq 0 ]] && return 1
        sudo_disponivel || return 1
        info "instalando pelo dnf: ${pacotes[*]}"
        sudo -n dnf install -y "${pacotes[@]}" >/dev/null 2>&1 || return 1
        return 1   # Space Grotesk continua faltando -> segue para o download
    fi
    if command -v pacman >/dev/null 2>&1; then
        tem_familia "${FAMILIA_MONO}" || pacotes+=("ttf-jetbrains-mono")
        # Space Grotesk só existe no AUR — não usamos AUR em script de install.
        [[ ${#pacotes[@]} -eq 0 ]] && return 1
        sudo_disponivel || return 1
        info "instalando pelo pacman: ${pacotes[*]}"
        sudo -n pacman -S --noconfirm --needed "${pacotes[@]}" >/dev/null 2>&1 || return 1
        return 1
    fi
    return 1
}

# ---------------------------------------------------------------------------
# Caminho 2: download pinado + SHA-256.
# ---------------------------------------------------------------------------
baixar() {
    local url="$1" destino="$2"
    if command -v curl >/dev/null 2>&1; then
        curl -sSL --fail --max-time 60 -o "${destino}" "${url}"
    elif command -v wget >/dev/null 2>&1; then
        wget -q --timeout=60 -O "${destino}" "${url}"
    else
        return 1
    fi
}

instalar_por_download() {
    [[ "${PERMITE_DOWNLOAD}" == "1" ]] || { info "--no-download: pulando o download"; return 1; }
    command -v sha256sum >/dev/null 2>&1 || { warn "sha256sum ausente — não baixo sem poder conferir"; return 1; }

    mkdir -p "${DEST_DIR}"
    local falhou=0
    for entrada in "${FONTES[@]}"; do
        IFS='|' read -r nome caminho soma <<< "${entrada}"
        local destino="${DEST_DIR}/${nome}"
        # Idempotente: já lá e com a soma certa => não toca na rede.
        if [[ -f "${destino}" ]] && printf '%s  %s\n' "${soma}" "${destino}" | sha256sum -c --status 2>/dev/null; then
            ok "${nome} já instalado e íntegro"
            continue
        fi
        local tmp
        tmp="$(mktemp "${TMPDIR:-/tmp}/hefesto-fonte-XXXXXX")"
        if ! baixar "${RAW_BASE}/${caminho}" "${tmp}"; then
            warn "download falhou: ${nome}"
            rm -f "${tmp}"; falhou=1; continue
        fi
        # A soma é a barreira: arquivo trocado no meio do caminho (proxy,
        # espelho, commit reescrito) não entra em ~/.local/share/fonts.
        if ! printf '%s  %s\n' "${soma}" "${tmp}" | sha256sum -c --status 2>/dev/null; then
            warn "SHA-256 NÃO confere para ${nome} — descartado"
            rm -f "${tmp}"; falhou=1; continue
        fi
        install -m 0644 "${tmp}" "${destino}"
        rm -f "${tmp}"
        ok "${nome} instalado"
    done

    # A OFL 1.1 obriga a distribuir a licença junto com a fonte.
    for entrada in "${LICENCAS[@]}"; do
        IFS='|' read -r nome caminho <<< "${entrada}"
        [[ -f "${DEST_DIR}/${nome}" ]] && continue
        baixar "${RAW_BASE}/${caminho}" "${DEST_DIR}/${nome}" || true
    done

    return "${falhou}"
}

# Cache do fontconfig. É `-f` GERAL de propósito, não só do nosso diretório: o
# pacote da distribuição escreve em /usr/share/fonts e, com o cache só do
# ~/.local, o `fc-list` logo abaixo continuava dizendo "AUSENTE" para uma fonte
# que ACABARA de ser instalada — o script mentia sobre o próprio resultado.
atualizar_cache() {
    command -v fc-cache >/dev/null 2>&1 || { warn "fc-cache ausente — reinicie a sessão para as fontes valerem"; return 0; }
    fc-cache -f >/dev/null 2>&1 || true
}

remover() {
    if [[ -d "${DEST_DIR}" ]]; then
        # Só o NOSSO diretório. Fonte instalada por pacote da distro sai pelo
        # gerenciador de pacotes, nunca por aqui: outra coisa pode depender
        # dela, e desinstalar o que não fomos nós instalar é o tipo de
        # assimetria que o uninstall deste projeto não faz.
        rm -rf "${DEST_DIR}"
        ok "removido ${DEST_DIR}"
        atualizar_cache
    else
        info "nada a remover (${DEST_DIR} não existe)"
    fi
    if tem_familia "${FAMILIA_UI}" || tem_familia "${FAMILIA_MONO}"; then
        info "as famílias continuam disponíveis pelo pacote da distribuição —"
        info "para tirá-las: sudo apt remove fonts-space-grotesk-ttf fonts-jetbrains-mono"
    fi
}

# ---------------------------------------------------------------------------
main() {
    case "${MODO}" in
        status)  relatar || true; exit 0 ;;
        remover) remover; exit 0 ;;
    esac

    printf '  Fontes da identidade visual (Space Grotesk + JetBrains Mono)\n'
    if relatar >/dev/null 2>&1; then
        ok "as duas famílias já estão disponíveis — nada a fazer"
        exit 0
    fi

    if instalar_por_pacote; then
        atualizar_cache
    fi
    # Reconsulta o fontconfig: o apt pode ter resolvido uma das duas.
    if ! relatar >/dev/null 2>&1; then
        instalar_por_download || true
        atualizar_cache
    fi

    relatar || warn "seguindo sem as fontes do design — a interface usa o fallback do CSS e funciona igual"
    exit 0
}

main
