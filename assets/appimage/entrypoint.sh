#!/bin/bash
# Entrypoint do AppImage Hefesto - Dualsense4Unix.
# $APPDIR é definido pelo AppRun do python-appimage.
#
# Roteamento:
#   - Sem args (clique duplo, atalho do menu): abre GUI GTK3.
#   - Com subcomando da CLI (status, profile, led, daemon, etc) ou flag (--help,
#     --version): roteia para CLI Typer.

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

CLI_SUBCOMMANDS=(status battery led profile test daemon emulate mouse tui tray version plugin)

route_to_cli() {
    local first="${1:-}"
    [[ -z "$first" ]] && return 1
    [[ "$first" == -* ]] && return 0
    for c in "${CLI_SUBCOMMANDS[@]}"; do
        [[ "$first" == "$c" ]] && return 0
    done
    return 1
}

if route_to_cli "$@"; then
    exec "$PYTHON" -m hefesto_dualsense4unix "$@"
else
    exec "$PYTHON" -m hefesto_dualsense4unix.app.main "$@"
fi
