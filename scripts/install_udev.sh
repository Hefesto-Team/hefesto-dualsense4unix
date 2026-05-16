#!/usr/bin/env bash
# install_udev.sh — Instala udev rules + modules-load uinput (caminho source).
#
# Conjunto canônico (v3.3.1+): 5 regras .rules + 1 .conf modules-load.
# Sincronizado com scripts/install-host-udev.sh (caminho Flatpak/.deb) —
# ambos usam o mesmo conjunto de assets/.
#
# Requer sudo. Idempotente: re-executar é seguro (sobrescreve com mesma
# fonte + recarrega udev + dispara eventos).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ASSETS="$HERE/assets"

# Falha cedo se algum arquivo esperado estiver ausente.
for f in \
    "$ASSETS/70-ps5-controller.rules" \
    "$ASSETS/71-uinput.rules" \
    "$ASSETS/72-ps5-controller-autosuspend.rules" \
    "$ASSETS/73-ps5-controller-hotplug.rules" \
    "$ASSETS/74-ps5-controller-hotplug-bt.rules" \
    "$ASSETS/hefesto-dualsense4unix.conf" \
; do
    [[ -f "$f" ]] || { echo "ERRO: asset ausente: $f" >&2; exit 1; }
done

echo "[1/3] copiando udev rules para /etc/udev/rules.d/..."
sudo install -Dm644 "$ASSETS/70-ps5-controller.rules"             /etc/udev/rules.d/70-ps5-controller.rules
sudo install -Dm644 "$ASSETS/71-uinput.rules"                     /etc/udev/rules.d/71-uinput.rules
sudo install -Dm644 "$ASSETS/72-ps5-controller-autosuspend.rules" /etc/udev/rules.d/72-ps5-controller-autosuspend.rules
sudo install -Dm644 "$ASSETS/73-ps5-controller-hotplug.rules"     /etc/udev/rules.d/73-ps5-controller-hotplug.rules
sudo install -Dm644 "$ASSETS/74-ps5-controller-hotplug-bt.rules"  /etc/udev/rules.d/74-ps5-controller-hotplug-bt.rules

echo "[2/3] copiando modules-load uinput..."
sudo install -Dm644 "$ASSETS/hefesto-dualsense4unix.conf" /etc/modules-load.d/hefesto-dualsense4unix.conf

echo "[3/3] carregando uinput + reload udev + trigger..."
sudo modprobe uinput 2>/dev/null || echo "  aviso: modprobe uinput falhou (kernel sem suporte CONFIG_INPUT_UINPUT?)"
sudo udevadm control --reload-rules
# Trigger seletivo para PS5 (vendor 054c). O trigger global no fim cobre
# devices que estavam quietos antes do reload (ex: BT pareado e idle).
sudo udevadm trigger --subsystem-match=hidraw --attr-match=idVendor=054c 2>/dev/null || true
sudo udevadm trigger --subsystem-match=usb    --attr-match=idVendor=054c 2>/dev/null || true
sudo udevadm trigger --action=change --subsystem-match=usb 2>/dev/null || true

cat <<'EOF'

Instalação concluída.
  - Desconecte e reconecte o DualSense (USB) ou reemparelhe (BT).
  - Para conferir permissão: ls -l /dev/hidraw*
  - Para conferir uinput:    ls -l /dev/uinput

Se estiver em distro sem systemd-logind (Alpine/Void/Gentoo OpenRC):
este setup não funciona. Ver docs/adr/009-systemd-logind-scope.md.

EOF

# "A forja prova o ferro. A paciência prova o homem." — Eclesiástico 31:26
