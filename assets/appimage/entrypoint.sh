#!/bin/bash
# Entrypoint do AppImage Hefesto - Dualsense4Unix.
# $APPDIR é definido pelo AppRun do python-appimage.
#
# IMPORTANTE: este AppImage expõe APENAS a CLI. A GUI GTK3 requer
# PyGObject + GTK3 bundlados que python-appimage (ferramenta usada pra
# gerar o bundle) não inclui — só Python puro + deps Python puras.
# Para a GUI use .deb (apt install ./hefesto-dualsense4unix_*.deb) ou
# Flatpak (flatpak install Hefesto-Dualsense4Unix.flatpak).
#
# Sem args: imprime ajuda da CLI e sai. Com subcomando: roteia.

set -e

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

# Sem args, mostrar mensagem clara de uso CLI + ponteiros pra GUI.
if [[ $# -eq 0 ]]; then
    cat <<'BANNER' >&2
Hefesto - Dualsense4Unix v3.0.0 — AppImage (CLI only)

Para a GUI GTK3 use:
  - .deb       sudo apt install ./hefesto-dualsense4unix_3.0.0_amd64.deb
  - Flatpak    flatpak install --user Hefesto-Dualsense4Unix.flatpak

Subcomandos CLI disponíveis abaixo:
BANNER
    exec "$PYTHON" -m hefesto_dualsense4unix --help
fi

exec "$PYTHON" -m hefesto_dualsense4unix "$@"
