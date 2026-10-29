#!/bin/bash

set -e

HEFESTO_VERSION_FALLBACK="0.9.5.1"

PYTHON=""
for candidate in "$APPDIR"/opt/python*/bin/python3.*; do
    if [[ -x "$candidate" ]]; then
        PYTHON="$candidate"
        break
    fi
done

if [[ -z "$PYTHON" ]]; then
    echo "python embutido não encontrado no AppImage" >&2
    exit 1
fi

if [[ $# -eq 0 ]]; then
    HEFESTO_VERSION="$("$PYTHON" -c 'from importlib.metadata import version
print(version("hefesto-dualsense4unix"))' 2>/dev/null || true)"
    if [[ -z "$HEFESTO_VERSION" ]]; then
        HEFESTO_VERSION="$HEFESTO_VERSION_FALLBACK"
    fi
    cat <<BANNER >&2
Hefesto - DualSense4Unix v${HEFESTO_VERSION} — AppImage (CLI only)

Para a GUI GTK3 use:
  - .deb       sudo apt install ./hefesto-dualsense4unix_${HEFESTO_VERSION}_amd64_py*.deb
  - Flatpak    flatpak install --user Hefesto-Dualsense4Unix.flatpak

Subcomandos CLI disponíveis abaixo:
BANNER
    exec "$PYTHON" -m hefesto_dualsense4unix --help
fi

exec "$PYTHON" -m hefesto_dualsense4unix "$@"
