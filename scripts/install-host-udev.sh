#!/usr/bin/env bash
# install-host-udev.sh — Instala regras udev + modules-load uinput do
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

if [[ -z "${RULES_SRC}" ]]; then
    echo "ERRO: regras udev não encontradas em nenhum dos paths esperados." >&2
    echo "      Verifique a instalação." >&2
    exit 1
fi

RULES_DEST="/etc/udev/rules.d"
MODLOAD_DEST="/etc/modules-load.d"

# Regras canônicas (v3.3.1+): 5 hidraw/uinput/autosuspend/hotplug.
# Sincronizado com scripts/install_udev.sh.
RULES=(
    "70-ps5-controller.rules"
    "71-uinput.rules"
    "72-ps5-controller-autosuspend.rules"
    "73-ps5-controller-hotplug.rules"
    "74-ps5-controller-hotplug-bt.rules"
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
    echo "  - hefesto-dualsense4unix.conf (modules-load: uinput)"
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
    fi
    # Recarrega udev e re-dispara eventos para dispositivos PS5 já presentes,
    # cobrindo BT (subsystem=hidraw) + USB (subsystem=usb).
    cmd+="udevadm control --reload-rules; "
    cmd+="udevadm trigger --subsystem-match=hidraw --attr-match=idVendor=054c 2>/dev/null || true; "
    cmd+="udevadm trigger --subsystem-match=usb --attr-match=idVendor=054c 2>/dev/null || true; "
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
