#!/usr/bin/env bash
# build_appimage_gui.sh — Gera AppImage com GUI GTK3 bundlada via appimagetool +
# linuxdeploy-plugin-gtk. Alternativa ao build_appimage.sh (CLI-only).
#
# FEAT-APPIMAGE-GUI-WITH-GTK-01 (#33) — v3.1.0+. A versão CLI-only do
# build_appimage.sh continua valida e mais leve (~30 MB). Esta versão GUI
# bundlada gera AppImage de ~150-200 MB que roda em qualquer distro sem
# precisar instalar GTK3/PyGObject via apt.
#
# Pré-requisitos:
#   - tools baixadas em build/appimage-gui-tools/ (appimagetool, linuxdeploy,
#     linuxdeploy-plugin-gtk.sh)
#   - python3.12 disponível
#   - python3-gi + gir1.2-gtk-3.0 + gir1.2-ayatanaappindicator3-0.1 instalados
#     no host (necessários para bundlar as libs e typelibs corretamente)
#
# Uso:
#   bash scripts/build_appimage_gui.sh
#
# Saída: dist/appimage/Hefesto-Dualsense4Unix-<version>-gui-x86_64.AppImage

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HERE"

TOOLS_DIR="$HERE/build/appimage-gui-tools"
APPDIR="$HERE/build/appimage-gui/AppDir"
OUT_DIR="$HERE/dist/appimage"

VERSION=$(python3 - <<'EOF'
import tomllib
print(tomllib.load(open("pyproject.toml", "rb"))["project"]["version"])
EOF
)

# Valida ferramentas
for tool in appimagetool linuxdeploy linuxdeploy-plugin-gtk.sh; do
    if [[ ! -x "$TOOLS_DIR/$tool" ]]; then
        echo "erro: $tool ausente em $TOOLS_DIR"
        echo "Baixe via:"
        echo "  mkdir -p build/appimage-gui-tools && cd build/appimage-gui-tools"
        echo "  wget https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage -O appimagetool && chmod +x appimagetool"
        echo "  wget https://github.com/linuxdeploy/linuxdeploy/releases/download/continuous/linuxdeploy-x86_64.AppImage -O linuxdeploy && chmod +x linuxdeploy"
        echo "  wget https://raw.githubusercontent.com/linuxdeploy/linuxdeploy-plugin-gtk/master/linuxdeploy-plugin-gtk.sh && chmod +x linuxdeploy-plugin-gtk.sh"
        exit 2
    fi
done

# FEAT-I18N-CATALOGS-01 (v3.4.0): compila .mo antes do pip install -e .
# para que o package locale/ seja embarcado via candidate path #5.
if [[ ! -d "$HERE/src/hefesto_dualsense4unix/locale" ]] \
        || [[ -z "$(ls "$HERE/src/hefesto_dualsense4unix/locale" 2>/dev/null)" ]]; then
    echo "[i18n] catalogos .mo ausentes — compilando do po/..."
    bash "$HERE/scripts/i18n_compile.sh"
fi

echo "[1/6] Limpando build anterior..."
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin"
mkdir -p "$APPDIR/usr/share/applications"
mkdir -p "$APPDIR/usr/share/icons/hicolor/256x256/apps"
mkdir -p "$APPDIR/usr/share/locale"
mkdir -p "$APPDIR/usr/share/metainfo"
mkdir -p "$OUT_DIR"

echo "[2/6] Copiando .desktop + icon..."
cp "$HERE/assets/appimage/Hefesto-Dualsense4Unix.png" \
   "$APPDIR/usr/share/icons/hicolor/256x256/apps/hefesto-dualsense4unix.png"
cp "$HERE/assets/appimage/Hefesto-Dualsense4Unix.png" "$APPDIR/hefesto-dualsense4unix.png"

cat > "$APPDIR/usr/share/applications/hefesto-dualsense4unix.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Hefesto - Dualsense4Unix
GenericName=DualSense Controller
Comment=Daemon de gatilhos adaptativos para DualSense no Linux
Exec=hefesto-dualsense4unix-gui
Icon=hefesto-dualsense4unix
Categories=Settings;HardwareSettings;
Terminal=false
StartupNotify=true
StartupWMClass=Hefesto-Dualsense4Unix
DESKTOP
cp "$APPDIR/usr/share/applications/hefesto-dualsense4unix.desktop" "$APPDIR/hefesto-dualsense4unix.desktop"

echo "[3/6] Criando venv embarcada no AppDir (com system-site-packages para gi)..."
python3.12 -m venv --system-site-packages "$APPDIR/usr"
"$APPDIR/usr/bin/python3" -m pip install --quiet --upgrade pip
"$APPDIR/usr/bin/pip" install --quiet "$HERE[emulation,cosmic,tray]"

# Copia catalogos .mo para AppDir/usr/share/locale/ — gettext acha via
# XDG_DATA_DIRS exportado no AppRun (candidate path #3 do utils/i18n.py).
# Redundante com candidate #5 (package locale) mas barato e explicito.
if [[ -d "$HERE/locale" ]]; then
    cp -r "$HERE/locale"/. "$APPDIR/usr/share/locale/"
fi

echo "[4/6] Criando AppRun (entrypoint da GUI)..."
cat > "$APPDIR/AppRun" <<'APPRUN'
#!/bin/bash
# AppRun do Hefesto - Dualsense4Unix GUI AppImage.
# Resolve paths relativos ao próprio bundle e exporta as envs que GTK/PyGObject
# precisam para encontrar typelibs, gdk-pixbuf loaders, etc.

HERE="$(dirname "$(readlink -f "${0}")")"

# Python bundlado + pacote Hefesto
export PATH="${HERE}/usr/bin:${PATH}"

# GTK + GdkPixbuf + GObject Introspection paths
export GI_TYPELIB_PATH="${HERE}/usr/lib/girepository-1.0:${HERE}/usr/lib/x86_64-linux-gnu/girepository-1.0:${GI_TYPELIB_PATH:-}"
export GDK_PIXBUF_MODULE_FILE="${HERE}/usr/lib/x86_64-linux-gnu/gdk-pixbuf-2.0/2.10.0/loaders.cache"
export GDK_PIXBUF_MODULEDIR="${HERE}/usr/lib/x86_64-linux-gnu/gdk-pixbuf-2.0/2.10.0/loaders"
export XDG_DATA_DIRS="${HERE}/usr/share:${XDG_DATA_DIRS:-/usr/local/share:/usr/share}"

# Detect CLI-only vs GUI args
if [[ $# -eq 0 ]] || [[ "$1" == "--gui" ]]; then
    [[ "${1:-}" == "--gui" ]] && shift
    exec "${HERE}/usr/bin/hefesto-dualsense4unix-gui" "$@"
fi

# Subcomando CLI direto
exec "${HERE}/usr/bin/hefesto-dualsense4unix" "$@"
APPRUN
chmod +x "$APPDIR/AppRun"

echo "[5/6] Bundling GTK3 + dependências via linuxdeploy-plugin-gtk..."
export DEPLOY_GTK_VERSION=3
"$TOOLS_DIR/linuxdeploy" --appdir "$APPDIR" \
    --plugin gtk \
    --desktop-file "$APPDIR/usr/share/applications/hefesto-dualsense4unix.desktop" \
    --icon-file "$APPDIR/usr/share/icons/hicolor/256x256/apps/hefesto-dualsense4unix.png" \
    || { echo "erro: linuxdeploy falhou"; exit 3; }

echo "[6/6] Gerando AppImage final via appimagetool..."
ARCH=x86_64 "$TOOLS_DIR/appimagetool" --no-appstream \
    "$APPDIR" \
    "$OUT_DIR/Hefesto-Dualsense4Unix-${VERSION}-gui-x86_64.AppImage" \
    || { echo "erro: appimagetool falhou"; exit 4; }

echo ""
echo "AppImage GUI gerado:"
ls -lh "$OUT_DIR/Hefesto-Dualsense4Unix-${VERSION}-gui-x86_64.AppImage"
echo ""
echo "Teste com:"
echo "  $OUT_DIR/Hefesto-Dualsense4Unix-${VERSION}-gui-x86_64.AppImage --gui"
echo "Ou versão (CLI):"
echo "  $OUT_DIR/Hefesto-Dualsense4Unix-${VERSION}-gui-x86_64.AppImage version"
