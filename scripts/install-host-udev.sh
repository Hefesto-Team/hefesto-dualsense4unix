#!/usr/bin/env bash
# install-host-udev.sh — Instala regras udev + modules-load (uinput, uhid) do
# Hefesto - Dualsense4Unix no sistema hospedeiro.
#
# Pode ser executado de 3 formas (todas idempotentes):
#
#   1. Dentro do Flatpak (caminho oficial pós-install):
#        flatpak run --command=install-host-udev.sh br.andrefarias.Hefesto
#      Resolve as regras em /app/share/hefesto-dualsense4unix/udev-rules/.
#
#   2. Direto do repositório clonado (instalação via fonte):
#        sudo bash scripts/install-host-udev.sh
#      Resolve as regras em ../assets/ relativo ao script.
#
#   3. Direto de um .deb instalado:
#        sudo /usr/share/hefesto-dualsense4unix/scripts/install-host-udev.sh
#      Resolve as regras em /usr/share/hefesto-dualsense4unix/udev-rules/.
#
# As regras concedem acesso ao DualSense via hidraw sem necessidade de root
# a cada execução, ativam emulação Xbox360 via uinput, evitam autosuspend
# USB que derruba a conexão e disparam hotplug-GUI (USB + BT).
#
# Requer pkexec (polkit) ou execução com sudo. Script suporta ambos.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Resolve origem das regras conforme contexto de execução.
# v3.3.1+: cobre Flatpak (/app/share), .deb (/usr/share) e source (../assets).
RULES_SRC=""
MODLOAD_SRC=""
for candidate in \
    "/app/share/hefesto-dualsense4unix/udev-rules" \
    "/usr/share/hefesto-dualsense4unix/udev-rules" \
    "${SCRIPT_DIR}/../assets" \
; do
    if [[ -f "${candidate}/70-ps5-controller.rules" ]]; then
        RULES_SRC="${candidate}"
        break
    fi
done

for candidate in \
    "/app/share/hefesto-dualsense4unix/modules-load" \
    "/usr/share/hefesto-dualsense4unix/modules-load" \
    "${SCRIPT_DIR}/../assets" \
; do
    if [[ -f "${candidate}/hefesto-dualsense4unix.conf" ]]; then
        MODLOAD_SRC="${candidate}"
        break
    fi
done

# SPRINT-GAME-RUMBLE-01: cura de RAIZ do storm -71 (quirk do snd_usb_audio).
# Quem instala por .deb/Flatpak também precisa dela — o install.sh nativo a
# aplica no step 3c, e este helper é o caminho equivalente para os pacotes.
# PRESERVA mic+fone (não é a regra 75, que é áudio-off e segue opt-in).
SNDQUIRK_SRC=""
for candidate in \
    "/app/share/hefesto-dualsense4unix/modprobe" \
    "/usr/share/hefesto-dualsense4unix/modprobe" \
    "/app/share/hefesto-dualsense4unix/assets/modprobe" \
    "/usr/share/hefesto-dualsense4unix/assets/modprobe" \
    "${SCRIPT_DIR}/../assets/modprobe" \
; do
    if [[ -f "${candidate}/hefesto-dualsense-storm.conf" ]]; then
        SNDQUIRK_SRC="${candidate}"
        break
    fi
done
SNDQUIRK_DEST="/etc/modprobe.d"

# PLAT-04 item 1: btusb sem autosuspend (o btusb LIGA o autosuspend do
# adaptador BT no probe; o conf corta na raiz, inclusive p/ adaptadores
# composite classe ef que escapam da regra 81 por classe e0).
BTUSB_SRC=""
for candidate in \
    "/app/share/hefesto-dualsense4unix/modprobe.d" \
    "/usr/share/hefesto-dualsense4unix/modprobe.d" \
    "${SCRIPT_DIR}/../assets/modprobe.d" \
; do
    if [[ -f "${candidate}/hefesto-btusb-no-autosuspend.conf" ]]; then
        BTUSB_SRC="${candidate}"
        break
    fi
done

if [[ -z "${RULES_SRC}" ]]; then
    echo "ERRO: regras udev não encontradas em nenhum dos paths esperados." >&2
    echo "      Verifique a instalação." >&2
    exit 1
fi

RULES_DEST="/etc/udev/rules.d"
MODLOAD_DEST="/etc/modules-load.d"

# Regras canônicas: hidraw/uinput/autosuspend.
# Sincronizado com scripts/install_udev.sh.
# 73/74 (GUI auto-spawn no hotplug) REMOVIDAS 2026-06-23 — abriam o controle a
# cada ACTION=="add" e amplificavam a re-enumeração do storm -71. Causa-raiz
# real: porta USB ruim (full-speed/-71 na 3-1). Ver docs/process/discoveries.
RULES=(
    "70-ps5-controller.rules"
    # 71-uhid: /dev/uhid — o gamepad virtual vira um DualSense de verdade, o que faz
    # a vibração funcionar também com a máscara DualSense. SPRINT-UHID-VPAD-01.
    # O número TEM de ser < 73 (a 73-seat-late.rules é quem vira a TAG uaccess em ACL).
    "71-uhid.rules"
    "71-uinput.rules"
    "72-ps5-controller-autosuspend.rules"
    "76-dualsense-touchpad-libinput-ignore.rules"
    "77-dualsense-leds.rules"
    "78-dualsense-motion-not-joystick.rules"
    # 79: LEDs de player dos Nintendo/8BitDo graváveis p/ o daemon numerar o
    # co-op misto (continua a contagem dos DualSense; só LED, nunca input). 8BIT-02.
    "79-external-controller-leds.rules"
    # 80: jsN legados dos Motion Sensors (físico E vpad) em MODE 0000 — a API js
    # legada para de enumerar "joysticks" fantasmas. KERNEL-07.
    "80-motion-joydev-hide.rules"
    # 81 (devices): controles e adaptadores BT nunca dormem (power/control=on +
    # autosuspend_delay_ms=-1). PLAT-03 item 1.
    "81-hefesto-usb-power.rules"
    # 81 (hosts): controladores USB PCI (classe 0x0c03*) em power/control=on —
    # a economia no HOST derruba o barramento inteiro. PLAT-03 item 3.
    "81-hefesto-usb-host-power.rules"
)

# Verificar se TODAS as rules existem na origem.
echo "Hefesto - Dualsense4Unix — instalação de regras udev"
echo ""
echo "Origem das regras:    ${RULES_SRC}"
if [[ -n "${MODLOAD_SRC}" ]]; then
    echo "Origem modules-load:  ${MODLOAD_SRC}"
fi
echo "Destino udev:         ${RULES_DEST}"
echo "Destino modules-load: ${MODLOAD_DEST}"
echo ""

for regra in "${RULES[@]}"; do
    if [[ ! -f "${RULES_SRC}/${regra}" ]]; then
        echo "ERRO: arquivo não encontrado: ${RULES_SRC}/${regra}" >&2
        exit 1
    fi
done

echo "As seguintes regras serão instaladas:"
for regra in "${RULES[@]}"; do
    echo "  - ${regra}"
done
if [[ -n "${MODLOAD_SRC}" ]]; then
    echo "  - hefesto-dualsense4unix.conf (modules-load: uinput, uhid)"
fi
if [[ -n "${SNDQUIRK_SRC}" ]]; then
    echo "  - hefesto-dualsense-storm.conf (cura do travamento do USB; preserva mic+fone)"
fi
if [[ -n "${BTUSB_SRC}" ]]; then
    echo "  - hefesto-btusb-no-autosuspend.conf (adaptador Bluetooth nunca dorme)"
fi
echo ""

# Comando núcleo executado com privilégios elevados (pkexec ou sudo).
# Define como string para reuso em ambos os caminhos sem duplicar lógica.
_build_install_cmd() {
    local cmd=""
    for regra in "${RULES[@]}"; do
        cmd+="install -Dm644 '${RULES_SRC}/${regra}' '${RULES_DEST}/${regra}'; "
    done
    if [[ -n "${MODLOAD_SRC}" ]]; then
        cmd+="install -Dm644 '${MODLOAD_SRC}/hefesto-dualsense4unix.conf' "
        cmd+="'${MODLOAD_DEST}/hefesto-dualsense4unix.conf'; "
        # Carrega uinput agora para não esperar reboot.
        cmd+="modprobe uinput 2>/dev/null || true; "
        # uhid: o gamepad virtual vira um DualSense de verdade (vibração também na
        # máscara DualSense). Sem o módulo o daemon cai no uinput sozinho — por isso
        # é best-effort, como o uinput. SPRINT-UHID-VPAD-01.
        cmd+="modprobe uhid 2>/dev/null || true; "
    fi
    # Cura de raiz do storm (paridade com o step 3c do install.sh nativo).
    # Também escreve o quirk_flags a quente — vale no próximo replug do controle,
    # sem reboot. Best-effort: se o sysfs não existir, segue.
    if [[ -n "${SNDQUIRK_SRC}" ]]; then
        cmd+="install -Dm644 '${SNDQUIRK_SRC}/hefesto-dualsense-storm.conf' "
        cmd+="'${SNDQUIRK_DEST}/hefesto-dualsense-storm.conf'; "
        cmd+="printf '%s' '054c:0ce6:ignore_ctl_error|ctl_msg_delay_1m,054c:0df2:ignore_ctl_error|ctl_msg_delay_1m' "
        cmd+="> /sys/module/snd_usb_audio/parameters/quirk_flags 2>/dev/null || true; "
    fi
    # btusb sem autosuspend (PLAT-04): conf persistente + runtime p/ probes
    # futuros (best-effort; o adaptador já plugado é coberto pela regra 81).
    if [[ -n "${BTUSB_SRC}" ]]; then
        cmd+="install -Dm644 '${BTUSB_SRC}/hefesto-btusb-no-autosuspend.conf' "
        cmd+="'${SNDQUIRK_DEST}/hefesto-btusb-no-autosuspend.conf'; "
        cmd+="printf '0' > /sys/module/btusb/parameters/enable_autosuspend 2>/dev/null || true; "
    fi
    # Recarrega udev e re-dispara eventos para dispositivos PS5 já presentes,
    # cobrindo BT (subsystem=hidraw) + USB (subsystem=usb).
    cmd+="udevadm control --reload-rules; "
    cmd+="udevadm trigger --subsystem-match=hidraw --attr-match=idVendor=054c 2>/dev/null || true; "
    cmd+="udevadm trigger --subsystem-match=usb --attr-match=idVendor=054c 2>/dev/null || true; "
    cmd+="udevadm trigger --subsystem-match=leds --action=add 2>/dev/null || true; "
    # input: reavalia 76 (touchpad-ignore), 78 (ID_INPUT_*) e 80 (js de Motion
    # Sensors em MODE 0000) sem exigir replug do controle.
    cmd+="udevadm trigger --action=change --subsystem-match=input 2>/dev/null || true; "
    # misc: /dev/uinput e /dev/uhid. Sem este trigger as regras 71-* só valeriam no
    # próximo boot (o nó já existia quando elas chegaram) — e sem elas não há vpad.
    cmd+="udevadm trigger --subsystem-match=misc --action=add 2>/dev/null || true; "
    # pci: aplica a 81-host (power/control=on nos xHCI) sem reboot. PLAT-03.
    cmd+="udevadm trigger --action=change --subsystem-match=pci 2>/dev/null || true; "
    cmd+="udevadm trigger 2>/dev/null || true; "
    cmd+="echo 'Regras instaladas com sucesso.'"
    printf '%s' "${cmd}"
}

INSTALL_CMD="$(_build_install_cmd)"

# Decidir como elevar privilégios.
if [[ "$(id -u)" -eq 0 ]]; then
    # Já rodando como root (ex: sudo bash install-host-udev.sh)
    bash -c "${INSTALL_CMD}"
elif command -v pkexec &>/dev/null; then
    # Dentro do Flatpak ou sistema com polkit — pkexec é o caminho canônico
    echo "Esta operação requer senha de administrador (polkit)."
    echo ""
    pkexec bash -c "${INSTALL_CMD}"
elif command -v sudo &>/dev/null; then
    # Fallback para sudo (fora do Flatpak em sistemas sem polkit)
    # INSTALL-UDEV-SUDO-CHECK-01 (v3.3.0): se o sudo cache expirou (ou
    # nunca rodou nessa sessão), o `sudo bash -c` mostra prompt em stdin.
    # Em sessão automatizada (CI sem TTY ou helper headless), trava.
    # Pre-check `sudo -n true` detecta isso e avisa antes — usuário sabe
    # que vai precisar digitar senha em ambiente real.
    if ! sudo -n true 2>/dev/null; then
        echo "AVISO: sudo requer senha para instalar regras udev em ${RULES_DEST}." >&2
        echo "       Se você está rodando sem TTY (CI, headless), cancele com Ctrl+C" >&2
        echo "       e use 'sudo bash $0' diretamente." >&2
        echo "" >&2
    fi
    sudo bash -c "${INSTALL_CMD}"
else
    echo "ERRO: nenhum método de elevação de privilégio encontrado (pkexec ou sudo)." >&2
    echo "" >&2
    echo "Execute manualmente como root:" >&2
    for regra in "${RULES[@]}"; do
        echo "  sudo install -Dm644 ${RULES_SRC}/${regra} ${RULES_DEST}/${regra}" >&2
    done
    if [[ -n "${MODLOAD_SRC}" ]]; then
        echo "  sudo install -Dm644 ${MODLOAD_SRC}/hefesto-dualsense4unix.conf \\" >&2
        echo "       ${MODLOAD_DEST}/hefesto-dualsense4unix.conf" >&2
        echo "  sudo modprobe uinput" >&2
    fi
    echo "  sudo udevadm control --reload-rules" >&2
    echo "  sudo udevadm trigger" >&2
    exit 1
fi

echo ""
echo "Desconecte e reconecte o controle DualSense para aplicar as permissões."
echo "Confira com: ls -l /dev/hidraw* /dev/uinput"
