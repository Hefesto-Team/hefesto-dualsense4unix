#!/usr/bin/env bash
# Bootstrap de ambiente de desenvolvimento.
# Uso: ./scripts/dev_bootstrap.sh [--with-tray]
set -euo pipefail

WITH_TRAY=0
for arg in "$@"; do
    case "$arg" in
        --with-tray) WITH_TRAY=1 ;;
        *) echo "aviso: argumento desconhecido ignorado: $arg" ;;
    esac
done

echo "[1/4] instalando deps do sistema..."
sudo apt-get update
sudo apt-get install -y libhidapi-dev libhidapi-hidraw0 libudev-dev libxi-dev

if [[ "$WITH_TRAY" == "1" ]]; then
    echo "[1.5/4] instalando deps opcionais de tray..."
    sudo apt-get install -y libgirepository1.0-dev libcairo2-dev pkg-config python3-dev
fi

echo "[2/4] criando virtualenv..."
python3 -m venv .venv
# shellcheck disable=SC1091
. .venv/bin/activate

echo "[3/4] instalando Hefesto em modo dev..."
EXTRAS="dev,emulation"
[[ "$WITH_TRAY" == "1" ]] && EXTRAS="$EXTRAS,tray"
pip install --upgrade pip
pip install -e ".[$EXTRAS]"

echo "[4/4] próximo passo: rodar ./scripts/install_udev.sh para configurar udev rules."
echo "Bootstrap concluido."

# "Ama a sabedoria com perseverança, e ela te elevará." — Provérbios 4:8
