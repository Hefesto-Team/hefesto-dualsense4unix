#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ASSETS="$HERE/assets"

DISABLE_USB_AUDIO=0

ABRIR_O_NO=0

uso() {
    cat <<'FIM'
Uso: scripts/install_udev.sh [opções]

Instala as regras udev + o modules-load do uinput (caminho source). Requer
sudo. Idempotente: reexecutar é seguro.

Opções:
  --disable-usb-audio   instala também a regra 75 (opt-in): desliga o áudio USB
                        do DualSense inteiro — sem microfone NEM fone do jack
  --no-fechar-o-no      OPT-OUT: o hidraw do DualSense físico volta a nascer
                        ABERTO para a sessão. Por default ele nasce 0600 root e
                        quem o abre é o broker, sob pedido — é o que impede a
                        Steam de pegá-lo no instante da conexão pelo rádio. Se
                        usar aqui, use também no ./install.sh: o broker precisa
                        ser renderizado sabendo disso
  --help, -h            mostra esta ajuda e sai

Nada é instalado enquanto esta ajuda estiver sendo exibida.
FIM
}

for arg in "$@"; do
    case "$arg" in
        --disable-usb-audio) DISABLE_USB_AUDIO=1 ;;
        --no-fechar-o-no)    ABRIR_O_NO=1 ;;
        --help|-h)           uso; exit 0 ;;
        *)
            echo "argumento desconhecido: $arg" >&2
            echo "nada foi instalado. Use --help para ver as opções." >&2
            exit 2
            ;;
    esac
done

for f in \
    "$ASSETS/73-hefesto-ps5-controller.rules" \
    "$ASSETS/71-uhid.rules" \
    "$ASSETS/71-uinput.rules" \
    "$ASSETS/72-ps5-controller-autosuspend.rules" \
    "$ASSETS/72-hefesto-touchpad-motion-uaccess.rules" \
    "$ASSETS/76-dualsense-touchpad-libinput-ignore.rules" \
    "$ASSETS/77-dualsense-leds.rules" \
    "$ASSETS/78-dualsense-motion-not-joystick.rules" \
    "$ASSETS/79-external-controller-leds.rules" \
    "$ASSETS/80-motion-joydev-hide.rules" \
    "$ASSETS/81-hefesto-usb-power.rules" \
    "$ASSETS/81-hefesto-usb-host-power.rules" \
    "$ASSETS/82-nintendo-pro-nosniff.rules" \
    "$ASSETS/83-hefesto-bond-snapshot.rules" \
    "$ASSETS/84-nintendo-pro-variant.rules" \
    "$ASSETS/85-hefesto-o-cabo-assume.rules" \
    "$ASSETS/hefesto-dualsense4unix.conf" \
    "$HERE/scripts/bt_nosniff_now.sh" \
    "$HERE/scripts/bt_bonds_snapshot.sh" \
    "$HERE/scripts/regra_do_no_aberta.sh" \
    "$ASSETS/systemd/hefesto-bt-bonds-snapshot.service" \
; do
    [[ -f "$f" ]] || { echo "ERRO: asset ausente: $f" >&2; exit 1; }
done

echo "[0/3] grupo dedicado 'hefesto' (dono de /dev/uhid e /dev/uinput)..."
sudo groupadd -f -r hefesto
_HEFESTO_USER="${SUDO_USER:-$(id -un)}"
if [[ "${_HEFESTO_USER}" != "root" ]]; then
    if id -nG -- "${_HEFESTO_USER}" | tr ' ' '\n' | grep -qx hefesto; then
        echo "  ${_HEFESTO_USER} já pertence ao grupo hefesto"
    else
        sudo usermod -aG hefesto "${_HEFESTO_USER}"
        echo "  ${_HEFESTO_USER} adicionada ao grupo hefesto (vale a partir do PRÓXIMO login)"
    fi
else
    echo "  aviso: usuário da sessão resolveu root — adicione manualmente: sudo usermod -aG hefesto SEU_USUARIO"
fi

echo "[1/3] copiando udev rules para /etc/udev/rules.d/..."
if [[ "$ABRIR_O_NO" -eq 1 ]]; then
    _regra_aberta="$(mktemp)"
    if ! bash "$HERE/scripts/regra_do_no_aberta.sh" \
            "$ASSETS/73-hefesto-ps5-controller.rules" "$_regra_aberta"; then
        rm -f "$_regra_aberta"
        echo "ERRO: --no-fechar-o-no não conseguiu reabrir todas as linhas do asset." >&2
        echo "nada foi instalado. Confira assets/73-hefesto-ps5-controller.rules." >&2
        exit 1
    fi
    sudo install -Dm644 "$_regra_aberta"                          /etc/udev/rules.d/73-hefesto-ps5-controller.rules
    rm -f "$_regra_aberta"
    echo "  AVISO: --no-fechar-o-no — o hidraw do DualSense nasce ABERTO; a Steam pode pegá-lo antes do broker"
else
    sudo install -Dm644 "$ASSETS/73-hefesto-ps5-controller.rules" /etc/udev/rules.d/73-hefesto-ps5-controller.rules
fi
sudo rm -f /etc/udev/rules.d/70-ps5-controller.rules
sudo install -Dm644 "$ASSETS/71-uinput.rules"                     /etc/udev/rules.d/71-uinput.rules
sudo install -Dm644 "$ASSETS/71-uhid.rules"                       /etc/udev/rules.d/71-uhid.rules
sudo install -Dm644 "$ASSETS/72-ps5-controller-autosuspend.rules" /etc/udev/rules.d/72-ps5-controller-autosuspend.rules
if [[ "$ABRIR_O_NO" -eq 1 ]]; then
    _regra_72_aberta="$(mktemp)"
    if ! bash "$HERE/scripts/regra_do_no_aberta.sh" \
            "$ASSETS/72-hefesto-touchpad-motion-uaccess.rules" "$_regra_72_aberta"; then
        rm -f "$_regra_72_aberta"
        echo "ERRO: --no-fechar-o-no não conseguiu reabrir as entradas da 72." >&2
        exit 1
    fi
    sudo install -Dm644 "$_regra_72_aberta" /etc/udev/rules.d/72-hefesto-touchpad-motion-uaccess.rules
    rm -f "$_regra_72_aberta"
else
    sudo install -Dm644 "$ASSETS/72-hefesto-touchpad-motion-uaccess.rules" /etc/udev/rules.d/72-hefesto-touchpad-motion-uaccess.rules
fi
sudo install -Dm644 "$ASSETS/76-dualsense-touchpad-libinput-ignore.rules" /etc/udev/rules.d/76-dualsense-touchpad-libinput-ignore.rules
sudo install -Dm644 "$ASSETS/77-dualsense-leds.rules" /etc/udev/rules.d/77-dualsense-leds.rules
sudo install -Dm644 "$ASSETS/78-dualsense-motion-not-joystick.rules" /etc/udev/rules.d/78-dualsense-motion-not-joystick.rules
sudo install -Dm644 "$ASSETS/79-external-controller-leds.rules" /etc/udev/rules.d/79-external-controller-leds.rules
sudo install -Dm644 "$ASSETS/80-motion-joydev-hide.rules" /etc/udev/rules.d/80-motion-joydev-hide.rules
sudo install -Dm644 "$ASSETS/81-hefesto-usb-power.rules" /etc/udev/rules.d/81-hefesto-usb-power.rules
sudo install -Dm644 "$ASSETS/81-hefesto-usb-host-power.rules" /etc/udev/rules.d/81-hefesto-usb-host-power.rules
sudo install -Dm644 "$ASSETS/82-nintendo-pro-nosniff.rules" /etc/udev/rules.d/82-nintendo-pro-nosniff.rules
sudo install -Dm644 "$ASSETS/83-hefesto-bond-snapshot.rules" /etc/udev/rules.d/83-hefesto-bond-snapshot.rules
sudo install -Dm644 "$ASSETS/84-nintendo-pro-variant.rules" /etc/udev/rules.d/84-nintendo-pro-variant.rules
sudo install -Dm644 "$ASSETS/85-hefesto-o-cabo-assume.rules" /etc/udev/rules.d/85-hefesto-o-cabo-assume.rules
sudo rm -f /etc/udev/rules.d/73-ps5-controller-hotplug.rules \
           /etc/udev/rules.d/74-ps5-controller-hotplug-bt.rules 2>/dev/null || true

if [[ "${DISABLE_USB_AUDIO}" -eq 1 ]]; then
    echo "[1b/3] (opt-in) instalando 75-...-disable-usb-audio (DualSense pure-HID)..."
    sudo install -Dm644 "$ASSETS/75-ps5-controller-disable-usb-audio.rules" /etc/udev/rules.d/75-ps5-controller-disable-usb-audio.rules
else
    [[ -e /etc/udev/rules.d/75-ps5-controller-disable-usb-audio.rules ]] && \
        echo "[1b/3] 75-...-disable-usb-audio já presente (mantido)"
fi

echo "[1c/3] alvos do RUN+= das regras 82 e 83 (sem eles as regras ficam inertes)..."
sudo install -Dm755 "$HERE/scripts/bt_nosniff_now.sh" \
    /usr/local/lib/hefesto-dualsense4unix/bt_nosniff_now.sh
sudo install -Dm755 "$HERE/scripts/bt_bonds_snapshot.sh" \
    /usr/local/lib/hefesto-dualsense4unix/bt_bonds_snapshot.sh
sudo install -Dm644 "$ASSETS/systemd/hefesto-bt-bonds-snapshot.service" \
    /etc/systemd/system/hefesto-bt-bonds-snapshot.service
sudo install -d -m700 /var/lib/hefesto-dualsense4unix/bt-bonds
if command -v systemctl >/dev/null 2>&1; then
    sudo systemctl daemon-reload >/dev/null 2>&1 || true
fi

echo "[2/3] copiando modules-load uinput..."
sudo install -Dm644 "$ASSETS/hefesto-dualsense4unix.conf" /etc/modules-load.d/hefesto-dualsense4unix.conf

echo "[3/3] carregando uinput + uhid + reload udev + trigger..."
sudo modprobe uinput 2>/dev/null || echo "  aviso: modprobe uinput falhou (kernel sem suporte CONFIG_INPUT_UINPUT?)"
sudo modprobe uhid 2>/dev/null || echo "  aviso: modprobe uhid falhou (kernel sem CONFIG_UHID?)"
sudo udevadm control --reload-rules
if python3 -I "$HERE/src/hefesto_dualsense4unix/integrations/quem_o_jogo_le.py" \
        --ha-jogo --proc "${HEFESTO_RAIZ_PROC:-/proc}" >/dev/null 2>&1; then
    echo "  com um jogo aberto, o controle não é reenumerado: as regras novas valem no próximo plugue"
else
    sudo udevadm trigger --action=change --subsystem-match=hidraw 2>/dev/null || true
    sudo udevadm trigger --subsystem-match=usb    --attr-match=idVendor=054c 2>/dev/null || true
    sudo udevadm trigger --action=change --subsystem-match=usb 2>/dev/null || true
    sudo udevadm trigger --action=change --subsystem-match=input 2>/dev/null || true
fi
sudo udevadm trigger --subsystem-match=leds --action=add 2>/dev/null || true
sudo udevadm trigger --subsystem-match=misc --action=add 2>/dev/null || true
sudo udevadm trigger --action=change --subsystem-match=pci 2>/dev/null || true

cat <<'EOF'

Instalação concluída.
  - Desconecte e reconecte o DualSense (USB) ou reemparelhe (BT).
  - Para conferir permissão: ls -l /dev/hidraw*
  - Para conferir uinput:    ls -l /dev/uinput

Se estiver em distro sem systemd-logind (Alpine/Void/Gentoo OpenRC):
este setup não funciona. Ver docs/adr/009-systemd-logind-scope.md.

EOF
