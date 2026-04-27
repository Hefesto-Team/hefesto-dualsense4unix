#!/bin/bash
# Entrypoint do AppImage Hefesto - Dualsense4Unix.
# $APPDIR é definido pelo AppRun do python-appimage.
#
# Chamamos `python -m hefesto_dualsense4unix` porque o bin `hefesto` gerado pelo pip
# tem shebang com path do build (/tmp/python-appimage-.../AppDir/AppRun)
# que não existe em runtime. `-m hefesto_dualsense4unix` usa o Python embutido direto.

set -e

for candidate in "$APPDIR"/opt/python*/bin/python3.*; do
    if [[ -x "$candidate" ]]; then
        exec "$candidate" -m hefesto_dualsense4unix "$@"
    fi
done

echo "python embutido não encontrado no AppImage" >&2
exit 1
