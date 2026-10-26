#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HERE"

DOMAIN="hefesto-dualsense4unix"

if ! command -v msgfmt >/dev/null 2>&1; then
    echo "ERRO: msgfmt ausente. Instale: sudo apt install gettext" >&2
    exit 1
fi

PKG_LOCALE="src/hefesto_dualsense4unix/locale"
rm -rf locale "$PKG_LOCALE"
mkdir -p locale "$PKG_LOCALE"

count=0
for po in po/*.po; do
    [[ -f "$po" ]] || continue
    lang="$(basename "$po" .po)"
    target_dir="locale/${lang}/LC_MESSAGES"
    mkdir -p "$target_dir"
    target="${target_dir}/${DOMAIN}.mo"
    msgfmt --check --statistics --output-file="$target" "$po" 2>&1 \
        | sed "s|^|  [${lang}] |"
    pkg_target_dir="${PKG_LOCALE}/${lang}/LC_MESSAGES"
    mkdir -p "$pkg_target_dir"
    cp -f "$target" "${pkg_target_dir}/${DOMAIN}.mo"
    count=$((count + 1))
done

echo ""
echo "Compilados $count idiomas em locale/ + $PKG_LOCALE/"
echo "Idiomas: $(ls locale/ | tr '\n' ' ')"
echo ""
echo "Próximo passo: bundling via build_deb.sh / build_appimage*.sh /"
echo "               build_flatpak.sh / install.sh"
