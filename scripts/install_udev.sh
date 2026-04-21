#!/usr/bin/env bash
# Instala udev rules e modules-load pra hidraw e uinput.
# Requer sudo. Seguro pra re-executar (idempotente).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ASSETS="$HERE/assets"

echo "[1/3] copiando udev rules para /etc/udev/rules.d/..."
sudo cp -v "$ASSETS/70-ps5-controller.rules"             /etc/udev/rules.d/
sudo cp -v "$ASSETS/71-uinput.rules"                     /etc/udev/rules.d/
sudo cp -v "$ASSETS/72-ps5-controller-autosuspend.rules" /etc/udev/rules.d/

echo "[2/3] copiando modules-load config..."
sudo cp -v "$ASSETS/hefesto.conf" /etc/modules-load.d/hefesto.conf

echo "[3/3] aplicando configuracao..."
sudo modprobe uinput
sudo udevadm control --reload-rules
sudo udevadm trigger --action=change --subsystem-match=usb
sudo udevadm trigger

cat <<'EOF'

Instalacao concluida.
  - Desconecte e reconecte o DualSense (USB) ou reemparelhe (BT).
  - Para conferir permissao: ls -l /dev/hidraw*
  - Para conferir uinput:    ls -l /dev/uinput

Se estiver em distro sem systemd-logind (Alpine/Void/Gentoo OpenRC):
este setup nao funciona. Ver docs/adr/009-systemd-logind-scope.md.

EOF

# "A forja prova o ferro. A paciencia prova o homem." — Eclesiastico 31:26
