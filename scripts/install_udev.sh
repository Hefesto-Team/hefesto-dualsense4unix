#!/usr/bin/env bash
# install_udev.sh — Instala udev rules + modules-load uinput (caminho source).
#
# Conjunto canônico (v3.3.1+): regras .rules + 1 .conf modules-load.
# Sincronizado com scripts/install-host-udev.sh (caminho Flatpak/.deb) —
# ambos usam o mesmo conjunto de assets/.
#
# Requer sudo. Idempotente: re-executar é seguro (sobrescreve com mesma
# fonte + recarrega udev + dispara eventos).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ASSETS="$HERE/assets"

# Opt-in: 75-...-disable-usb-audio (DualSense pure-HID no nível USB). Escalada do
# storm -71 — desliga o áudio USB inteiro do controle (sem mic NEM fone do jack).
# FEAT-DSX-DEFINITIVE-FIX-01 §7.5.
DISABLE_USB_AUDIO=0
for arg in "$@"; do
    case "$arg" in
        --disable-usb-audio) DISABLE_USB_AUDIO=1 ;;
        *) echo "aviso: argumento desconhecido: $arg" >&2 ;;
    esac
done

# Falha cedo se algum arquivo esperado estiver ausente.
for f in \
    "$ASSETS/70-ps5-controller.rules" \
    "$ASSETS/71-uhid.rules" \
    "$ASSETS/71-uinput.rules" \
    "$ASSETS/72-ps5-controller-autosuspend.rules" \
    "$ASSETS/76-dualsense-touchpad-libinput-ignore.rules" \
    "$ASSETS/77-dualsense-leds.rules" \
    "$ASSETS/78-dualsense-motion-not-joystick.rules" \
    "$ASSETS/79-external-controller-leds.rules" \
    "$ASSETS/80-motion-joydev-hide.rules" \
    "$ASSETS/81-hefesto-usb-power.rules" \
    "$ASSETS/81-hefesto-usb-host-power.rules" \
    "$ASSETS/hefesto-dualsense4unix.conf" \
; do
    [[ -f "$f" ]] || { echo "ERRO: asset ausente: $f" >&2; exit 1; }
done

# VPAD-09 (2026-07-21): grupo dedicado dono de /dev/uhid e /dev/uinput. A ACL
# do uaccess é aplicada pelo systemd-logind NO LOGIN — mesmo instante em que o
# daemon de sessão sobe: corrida real (perdida ao vivo em 21/07: EACCES nos
# dois nós no boot → vpad nenhum → Sony some da GUI e o jogo vê o físico cru).
# O GROUP= das regras 71-* é aplicado pelo udev na CRIAÇÃO do nó, antes de
# qualquer login — determinístico. O grupo entra nos processos da usuária no
# PRÓXIMO login; até lá o uaccess cobre (e o daemon tem o revive VPAD-09).
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
sudo install -Dm644 "$ASSETS/70-ps5-controller.rules"             /etc/udev/rules.d/70-ps5-controller.rules
sudo install -Dm644 "$ASSETS/71-uinput.rules"                     /etc/udev/rules.d/71-uinput.rules
# 71-uhid: /dev/uhid acessível ao usuário — o gamepad virtual vira um DualSense de
# verdade (hidraw + lightbar + LEDs + sensores), o que faz a vibração funcionar
# também com a máscara DualSense. SPRINT-UHID-VPAD-01.
# O número TEM de ser < 73: quem transforma a TAG uaccess em ACL é a
# /usr/lib/udev/rules.d/73-seat-late.rules. Numerada 79, a regra rodava DEPOIS
# dela e o /dev/uhid ficava root-only (MODE aplicado, ACL não) — medido ao vivo.
sudo install -Dm644 "$ASSETS/71-uhid.rules"                       /etc/udev/rules.d/71-uhid.rules
sudo install -Dm644 "$ASSETS/72-ps5-controller-autosuspend.rules" /etc/udev/rules.d/72-ps5-controller-autosuspend.rules
# 76: touchpad do DualSense ignorado como ponteiro libinput (para de brigar com a
# emulação analógica do hefesto). FEAT-DUALSENSE-TOUCHPAD-IGNORE-01. Não-destrutivo
# e reversível (remover o arquivo). Só vale após re-add do device (replug/relogin).
sudo install -Dm644 "$ASSETS/76-dualsense-touchpad-libinput-ignore.rules" /etc/udev/rules.d/76-dualsense-touchpad-libinput-ignore.rules
# 77: torna graváveis os nós de LED do kernel (lightbar + player) p/ o daemon
# (usuário) controlar a COR via sysfs — funciona em USB E BT. FEAT-DSX-LIGHTBAR-SYSFS-01.
sudo install -Dm644 "$ASSETS/77-dualsense-leds.rules" /etc/udev/rules.d/77-dualsense-leds.rules
# 78: os Motion Sensors do DualSense deixam de enumerar como JOYSTICK (SDL/jogos
# ignoram; para de poluir a lista de gamepads e de jorrar eventos de acelerômetro
# no jogo). FEAT-DSX-CONTROLLER-IDENTITY-01. Reversível (remover o arquivo).
sudo install -Dm644 "$ASSETS/78-dualsense-motion-not-joystick.rules" /etc/udev/rules.d/78-dualsense-motion-not-joystick.rules
# 79: torna graváveis os LEDs de player dos controles Nintendo/8BitDo p/ o daemon
# numerar o CO-OP MISTO (continua a contagem dos DualSense; só LED, nunca input).
# 8BIT-02. Sem ela, o número do LED do 8BitDo cai no default do kernel.
sudo install -Dm644 "$ASSETS/79-external-controller-leds.rules" /etc/udev/rules.d/79-external-controller-leds.rules
# 80: os nós js legados dos Motion Sensors (joydev cria jsN para CADA
# acelerômetro — físico E vpad) viram MODE 0000: a API js legada para de
# enumerar "joysticks" fantasmas (js2/js4/js6/js8 ao vivo). KERNEL-07.
sudo install -Dm644 "$ASSETS/80-motion-joydev-hide.rules" /etc/udev/rules.d/80-motion-joydev-hide.rules
# 81 (devices): controles (Sony/Nintendo/8BitDo/Microsoft) e adaptadores BT
# (classe e0) com power/control=on + autosuspend_delay_ms=-1 — USB nunca dorme.
# PLAT-03 item 1 (estudo 2026-07-18-estudo-kernel-hardening.md §2).
sudo install -Dm644 "$ASSETS/81-hefesto-usb-power.rules" /etc/udev/rules.d/81-hefesto-usb-power.rules
# 81 (hosts): controladores USB PCI (classe 0x0c03*) sempre em power/control=on
# — a economia no HOST derruba o barramento inteiro (teclado+mouse+controle
# juntos, visto em maio/2026). PLAT-03 item 3.
sudo install -Dm644 "$ASSETS/81-hefesto-usb-host-power.rules" /etc/udev/rules.d/81-hefesto-usb-host-power.rules
# 73/74 (GUI auto-spawn no hotplug) DESCONTINUADAS 2026-06-23 (abriam o controle
# via hidraw a cada ACTION=="add", amplificando a re-enumeração do storm -71) e
# REMOVIDAS do repo em 2026-07-18. O rm compensatório fica por 1 release para
# limpar instalações antigas — depois pode sair junto com este comentário:
sudo rm -f /etc/udev/rules.d/73-ps5-controller-hotplug.rules \
           /etc/udev/rules.d/74-ps5-controller-hotplug-bt.rules 2>/dev/null || true

if [[ "${DISABLE_USB_AUDIO}" -eq 1 ]]; then
    echo "[1b/3] (opt-in) instalando 75-...-disable-usb-audio (DualSense pure-HID)..."
    sudo install -Dm644 "$ASSETS/75-ps5-controller-disable-usb-audio.rules" /etc/udev/rules.d/75-ps5-controller-disable-usb-audio.rules
else
    # Se a regra opt-in já existe de uma instalação anterior, preserva (não a
    # removemos aqui — quem remove é o uninstall.sh ou rodar sem a flag não a apaga).
    [[ -e /etc/udev/rules.d/75-ps5-controller-disable-usb-audio.rules ]] && \
        echo "[1b/3] 75-...-disable-usb-audio já presente (mantido)"
fi

echo "[2/3] copiando modules-load uinput..."
sudo install -Dm644 "$ASSETS/hefesto-dualsense4unix.conf" /etc/modules-load.d/hefesto-dualsense4unix.conf

echo "[3/3] carregando uinput + uhid + reload udev + trigger..."
sudo modprobe uinput 2>/dev/null || echo "  aviso: modprobe uinput falhou (kernel sem suporte CONFIG_INPUT_UINPUT?)"
# uhid: gamepad virtual como DualSense de verdade (SPRINT-UHID-VPAD-01). Sem ele
# o daemon cai no uinput (sem vibração na máscara DualSense), então é aviso, não erro.
sudo modprobe uhid 2>/dev/null || echo "  aviso: modprobe uhid falhou (kernel sem CONFIG_UHID?)"
sudo udevadm control --reload-rules
# Trigger seletivo para PS5 (vendor 054c). O trigger global no fim cobre
# devices que estavam quietos antes do reload (ex: BT pareado e idle).
sudo udevadm trigger --subsystem-match=hidraw --attr-match=idVendor=054c 2>/dev/null || true
sudo udevadm trigger --subsystem-match=usb    --attr-match=idVendor=054c 2>/dev/null || true
sudo udevadm trigger --action=change --subsystem-match=usb 2>/dev/null || true
# input: faz a 76 (LIBINPUT_IGNORE_DEVICE no touchpad), a 78 (ID_INPUT_*) e a 80
# (MODE 0000 nos js de Motion Sensors) serem reavaliadas sem replug. libinput só
# relê a flag ao re-add do device, então replug/relogin do controle ainda é o garantido.
sudo udevadm trigger --action=change --subsystem-match=input 2>/dev/null || true
# leds: aplica a 77 (chmod/uaccess nos nós de LED) sem exigir replug do controle.
sudo udevadm trigger --subsystem-match=leds --action=add 2>/dev/null || true
# misc: /dev/uinput e /dev/uhid vivem aqui. Sem este trigger as regras 71-* só
# valiam no próximo boot (o nó já existia quando as regras chegaram) — e sem elas
# o daemon não cria vpad nenhum: co-op de 4 jogadores morto até reiniciar.
sudo udevadm trigger --subsystem-match=misc --action=add 2>/dev/null || true
# pci: aplica a 81-host (power/control=on nos controladores xHCI) sem reboot —
# os hosts já existiam quando a regra chegou. PLAT-03 item 3.
sudo udevadm trigger --action=change --subsystem-match=pci 2>/dev/null || true

cat <<'EOF'

Instalação concluída.
  - Desconecte e reconecte o DualSense (USB) ou reemparelhe (BT).
  - Para conferir permissão: ls -l /dev/hidraw*
  - Para conferir uinput:    ls -l /dev/uinput

Se estiver em distro sem systemd-logind (Alpine/Void/Gentoo OpenRC):
este setup não funciona. Ver docs/adr/009-systemd-logind-scope.md.

EOF

# "A forja prova o ferro. A paciência prova o homem." — Eclesiástico 31:26
