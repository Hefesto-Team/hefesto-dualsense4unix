#!/bin/bash
# Entrypoint do AppImage Hefesto.
# $APPDIR é definido pelo AppRun do python-appimage.
#
# Chamamos `python -m hefesto` porque o bin `hefesto` gerado pelo pip
# tem shebang com path do build (/tmp/python-appimage-.../AppDir/AppRun)
# que não existe em runtime. `-m hefesto` usa o Python embutido direto.

set -e

for candidate in "$APPDIR"/opt/python*/bin/python3.*; do
    if [[ -x "$candidate" ]]; then
        exec "$candidate" -m hefesto "$@"
    fi
done

echo "python embutido não encontrado no AppImage" >&2
exit 1
