#!/usr/bin/env bash
# instalar_atalho_da_interface.sh — põe a logo de dev na dock, e só isso.
#
# Pedido dela, 29/08/2026: *"o nosso lançador.sh precisa ter a logo do app na
# dock"*.
#
# O QUE ESTE SCRIPT FAZ, E O QUE ELE DELIBERADAMENTE NÃO FAZ
# ----------------------------------------------------------
# FAZ: escreve UM `.desktop` (`hefesto-dev-dualsense4unix.desktop`) e os PNGs
# do ícone de dev no tema `hicolor` do HOME. Onze arquivos, todos com `dev` no
# nome, todos dentro de `~/.local/share`.
#
# NÃO FAZ: nada de `sudo`, nada em `/etc` ou `/usr`, nenhuma regra udev, nenhum
# `systemctl`, nenhum `pip`. Não encosta em NADA do Hefesto estável — nem no
# `.desktop` dela, nem nos ícones dela, nem no daemon dela. É por isso que ele
# é separado do `install-dev.sh`: este aqui é reversível com um `rm`, e ela
# pode rodá-lo sem pensar duas vezes.
#
# `--desfazer` apaga exatamente o que ele escreveu, nada mais.
#
# POR QUE O ÍCONE NÃO É O DA LOGO NOVA DIRETO (medido em 29/08/2026)
# -------------------------------------------------------------------
# `assets/hefesto-logo.svg` usa `transform-box` e `transform-origin`, que o
# **librsvg IGNORA** (medido com rsvg-convert 2.58.0). O anel e o martelo somem
# do PNG — a logo apareceria mutilada na dock e inteira dentro do app.
# `assets/hefesto-dev-logo.svg` já nasce com esses transforms ASSADOS na
# matriz: o Chrome renderiza o antes e o depois byte-idênticos, e o librsvg
# passa a mostrar o desenho inteiro. Detalhe no cabeçalho daquele arquivo.
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

APP_ID="hefesto-dev-dualsense4unix"
SVG="${RAIZ}/assets/hefesto-dev-logo.svg"
SIMBOLICO="${RAIZ}/assets/simbolico/hefesto-dualsense4unix-symbolic.svg"
MODELO="${RAIZ}/packaging/${APP_ID}.desktop"

APLICATIVOS="${HOME}/.local/share/applications"
HICOLOR="${HOME}/.local/share/icons/hicolor"
DESKTOP="${APLICATIVOS}/${APP_ID}.desktop"
TAMANHOS="16 22 24 32 48 64 96 128 192 256 512"

atualizar_caches() {
    command -v gtk-update-icon-cache >/dev/null 2>&1 &&
        gtk-update-icon-cache -q -f "${HICOLOR}" 2>/dev/null || true
    command -v update-desktop-database >/dev/null 2>&1 &&
        update-desktop-database -q "${APLICATIVOS}" 2>/dev/null || true
}

if [[ "${1:-}" == "--desfazer" ]]; then
    rm -f "${DESKTOP}"
    for t in ${TAMANHOS}; do
        rm -f "${HICOLOR}/${t}x${t}/apps/${APP_ID}.png"
    done
    rm -f "${HICOLOR}/symbolic/apps/${APP_ID}-symbolic.svg"
    rm -f "${HOME}/.local/share/pixmaps/${APP_ID}.png"
    atualizar_caches
    echo "desfeito: o atalho e os ícones de dev saíram. O Hefesto estável não foi tocado."
    exit 0
fi

# --- as recusas, ANTES de escrever o primeiro byte ---------------------------
[[ -f "${SVG}" ]] || { echo "erro: não achei ${SVG}" >&2; exit 1; }
[[ -f "${MODELO}" ]] || { echo "erro: não achei ${MODELO}" >&2; exit 1; }
[[ -x "${RAIZ}/interface" ]] || {
    echo "erro: ${RAIZ}/interface não existe ou não é executável" >&2; exit 1; }
command -v rsvg-convert >/dev/null 2>&1 || {
    echo "erro: rsvg-convert ausente. Instale: sudo apt install librsvg2-bin" >&2
    exit 1; }

# A recusa que importa: se este `.desktop` ou este ícone tivesse o nome do
# estável, escrevê-lo SEQUESTRARIA o app dela — o `.desktop` dela é
# `hefesto-dualsense4unix.desktop`, e o `Exec=` dele aponta para a árvore dela.
# Aqui isso é impossível por construção (o APP_ID tem `dev` no meio), e a
# checagem existe para que continue impossível se alguém editar o APP_ID.
if [[ "${APP_ID}" != *"-dev-"* ]]; then
    echo "erro: APP_ID sem 'dev' no meio — isto sobrescreveria o app estável" >&2
    exit 1
fi

echo "Hefesto (dev) — atalho e ícone"
echo "  árvore : ${RAIZ}"
echo "  app_id : ${APP_ID}"
echo

# --- ícones ------------------------------------------------------------------
for t in ${TAMANHOS}; do
    mkdir -p "${HICOLOR}/${t}x${t}/apps"
    rsvg-convert -w "${t}" -h "${t}" "${SVG}" \
        -o "${HICOLOR}/${t}x${t}/apps/${APP_ID}.png"
done
mkdir -p "${HOME}/.local/share/pixmaps"
cp -f "${HICOLOR}/256x256/apps/${APP_ID}.png" \
    "${HOME}/.local/share/pixmaps/${APP_ID}.png"
echo "  ícones : ${TAMANHOS// /, } px em hicolor/*/apps/${APP_ID}.png"

# O simbólico da bandeja é o MESMO desenho do estável, e isso é decisão
# registrada, não descuido: a grade de 16 px do simbólico não tem folga para
# uma marca a mais (o cabeçalho de `assets/simbolico/...-symbolic.svg` mede por
# que — as contas do aro já alcançam 7,80 de 8,00). Quem distingue os dois na
# bandeja é o ícone colorido do degrau de queda, que É diferente.
if [[ -f "${SIMBOLICO}" ]]; then
    mkdir -p "${HICOLOR}/symbolic/apps"
    cp -f "${SIMBOLICO}" "${HICOLOR}/symbolic/apps/${APP_ID}-symbolic.svg"
fi

# --- .desktop ----------------------------------------------------------------
mkdir -p "${APLICATIVOS}"
sed "s|@RAIZ@|${RAIZ}|g" "${MODELO}" > "${DESKTOP}"
command -v desktop-file-validate >/dev/null 2>&1 &&
    desktop-file-validate "${DESKTOP}" >/dev/null 2>&1 || true
echo "  atalho : ${DESKTOP}"

atualizar_caches

echo
echo "pronto. 'Hefesto (dev)' está no menu, com a logo âmbar."
echo "Para tirar tudo: $0 --desfazer"
