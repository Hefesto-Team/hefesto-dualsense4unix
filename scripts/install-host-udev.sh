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

# Onda T (2026-07-20): opções do hid-nintendo patchado (bt_probe_retries=3 —
# cura da morte por probe BT). O parâmetro só existe no módulo DKMS do hefesto;
# com o in-tree o kernel loga "unknown parameter ignored" e sobe normal
# (fail-safe do desenho da Onda T) — instalar a conf é sempre seguro.
HIDNINTENDO_SRC=""
for candidate in \
    "/app/share/hefesto-dualsense4unix/modprobe.d" \
    "/usr/share/hefesto-dualsense4unix/modprobe.d" \
    "${SCRIPT_DIR}/../assets/modprobe.d" \
; do
    if [[ -f "${candidate}/hefesto-hid-nintendo.conf" ]]; then
        HIDNINTENDO_SRC="${candidate}"
        break
    fi
done

# BROKER-01 (Onda S — fd-injection): broker root que esconde o hidraw FÍSICO
# do DualSense do JOGO e serve fd O_RDWR ao daemon via SCM_RIGHTS (cmd
# `open`) para o giroscópio nunca morrer, mesmo com o nó escondido. Resolve o
# binário standalone (stdlib pura, roda no python3 do sistema) e as units-
# template nos mesmos 3 contextos acima. PRIMEIRO serviço de SISTEMA
# (systemd system, socket-activated) do projeto. Desenho completo:
# docs/process/estudos/2026-07-20-desenho-onda-s-broker-fd-injection.md §7.4.
BROKER_BIN_SRC=""
for candidate in \
    "/app/share/hefesto-dualsense4unix/broker" \
    "/usr/share/hefesto-dualsense4unix/broker" \
    "${SCRIPT_DIR}/../src/hefesto_dualsense4unix/broker" \
; do
    if [[ -f "${candidate}/hidraw_broker.py" ]]; then
        BROKER_BIN_SRC="${candidate}"
        break
    fi
done

BROKER_UNITS_SRC=""
for candidate in \
    "/app/share/hefesto-dualsense4unix/systemd" \
    "/usr/share/hefesto-dualsense4unix/systemd" \
    "${SCRIPT_DIR}/../assets/systemd" \
; do
    if [[ -f "${candidate}/hefesto-hidraw-broker.service" ]]; then
        BROKER_UNITS_SRC="${candidate}"
        break
    fi
done

# uid/grupo da SESSÃO (lição 6: NUNCA root) — capturado AQUI, antes de
# qualquer elevação (pkexec/sudo troca o ambiente da linha abaixo pra
# frente). Nos 3 contextos de uso deste script, `id -u`/`SUDO_UID` neste
# ponto ainda refletem quem CHAMOU o script, nunca o alvo da elevação.
BROKER_SESSION_UID="${SUDO_UID:-$(id -u)}"
BROKER_SESSION_GROUP=""
if [[ "${BROKER_SESSION_UID}" != "0" ]]; then
    BROKER_SESSION_GROUP="$(id -gn -- "${BROKER_SESSION_UID}" 2>/dev/null || true)"
fi
BROKER_INSTALL_OK=0
if [[ -n "${BROKER_BIN_SRC}" && -n "${BROKER_UNITS_SRC}" \
        && "${BROKER_SESSION_UID}" != "0" && -n "${BROKER_SESSION_GROUP}" ]]; then
    BROKER_INSTALL_OK=1
fi

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
if [[ -n "${HIDNINTENDO_SRC}" ]]; then
    echo "  - hefesto-hid-nintendo.conf (probe BT resiliente do hid-nintendo patchado)"
fi
if [[ "${BROKER_INSTALL_OK}" -eq 1 ]]; then
    echo "  - hefesto-hidraw-broker (broker root hide-hidraw, BROKER-01; uid ${BROKER_SESSION_UID}, grupo ${BROKER_SESSION_GROUP})"
elif [[ -n "${BROKER_BIN_SRC}" && -n "${BROKER_UNITS_SRC}" ]]; then
    echo "  - hefesto-hidraw-broker NÃO instalado (SESSION_UID resolveu 0/root — rode este script a partir da sessão da usuária)"
fi
echo ""

# Comando núcleo executado com privilégios elevados (pkexec ou sudo).
# Define como string para reuso em ambos os caminhos sem duplicar lógica.
_build_install_cmd() {
    local cmd=""
    # VPAD-09: grupo dedicado dono dos nós 71-* (racional na 71-uhid.rules) —
    # criado ANTES de copiar as regras, senão o GROUP= cai no fallback
    # uaccess-only (udev ignora grupo inexistente). A usuária entra no grupo
    # a partir do PRÓXIMO login; até lá o uaccess cobre a sessão atual.
    cmd+="groupadd -f -r hefesto; "
    if [[ "${BROKER_SESSION_UID}" != "0" ]]; then
        local _vpad_user
        _vpad_user="$(id -un -- "${BROKER_SESSION_UID}" 2>/dev/null || true)"
        if [[ -n "${_vpad_user}" && "${_vpad_user}" != "root" ]]; then
            cmd+="usermod -aG hefesto '${_vpad_user}'; "
        fi
    fi
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
    # Onda T: conf persistente do hid-nintendo patchado + parâmetro a quente
    # (só existe se o módulo DKMS estiver carregado — best-effort; vale já no
    # próximo probe BT, sem reload de módulo nem replug dos controles em uso).
    if [[ -n "${HIDNINTENDO_SRC}" ]]; then
        cmd+="install -Dm644 '${HIDNINTENDO_SRC}/hefesto-hid-nintendo.conf' "
        cmd+="'${SNDQUIRK_DEST}/hefesto-hid-nintendo.conf'; "
        cmd+="printf '3' > /sys/module/hid_nintendo/parameters/bt_probe_retries 2>/dev/null || true; "
        cmd+="printf '1' > /sys/module/hid_nintendo/parameters/skip_tx_on_rate_exceeded 2>/dev/null || true; "
    fi
    # BROKER-01 (Onda S — fd-injection): binário + units-template renderizadas
    # (__SESSION_UID__/__SESSION_GROUP__) + enable --now do .socket (só ele —
    # o .service sobe na 1ª conexão do daemon, ativação por socket). Guarda
    # pós-render (lição 6): placeholder __SESSION_* sobrando ABORTA só o
    # broker (nunca as regras udev já instaladas acima).
    # S-1 (auditoria 21/07): o render acontece num mktemp -d PRIVADO criado
    # DENTRO do comando elevado (0700 de root) — caminho fixo em /tmp era
    # pré-criável por outro usuário local: com fs.protected_regular o sed de
    # root falhava em silêncio e o root instalava a unit DO ATACANTE.
    if [[ "${BROKER_INSTALL_OK}" -eq 1 ]]; then
        cmd+="install -Dm755 '${BROKER_BIN_SRC}/hidraw_broker.py' "
        cmd+="/usr/local/lib/hefesto-dualsense4unix/hefesto-hidraw-broker; "
        cmd+="_hbr=\$(mktemp -d /tmp/hefesto-broker-render.XXXXXXXX) "
        cmd+="&& sed 's/__SESSION_UID__/${BROKER_SESSION_UID}/' "
        cmd+="'${BROKER_UNITS_SRC}/hefesto-hidraw-broker.service' "
        cmd+="> \"\${_hbr}/hefesto-hidraw-broker.service\" "
        cmd+="&& sed 's/__SESSION_GROUP__/${BROKER_SESSION_GROUP}/' "
        cmd+="'${BROKER_UNITS_SRC}/hefesto-hidraw-broker.socket' "
        cmd+="> \"\${_hbr}/hefesto-hidraw-broker.socket\" "
        cmd+="|| { echo 'ERRO: render do broker falhou — broker NAO instalado' >&2; "
        cmd+="[ -n \"\${_hbr:-}\" ] && rm -rf \"\${_hbr}\"; _hbr=; }; "
        cmd+="if [ -n \"\${_hbr:-}\" ]; then "
        cmd+="if grep -q '__SESSION_' \"\${_hbr}/hefesto-hidraw-broker.service\" "
        cmd+="\"\${_hbr}/hefesto-hidraw-broker.socket\" 2>/dev/null; then "
        cmd+="echo 'ERRO: render do broker deixou placeholder __SESSION_* — broker NAO instalado' >&2; "
        cmd+="else "
        cmd+="install -Dm644 \"\${_hbr}/hefesto-hidraw-broker.service\" "
        cmd+="/etc/systemd/system/hefesto-hidraw-broker.service; "
        cmd+="install -Dm644 \"\${_hbr}/hefesto-hidraw-broker.socket\" "
        cmd+="/etc/systemd/system/hefesto-hidraw-broker.socket; "
        cmd+="systemctl daemon-reload; "
        cmd+="systemctl enable --now hefesto-hidraw-broker.socket; "
        cmd+="fi; "
        cmd+="rm -rf \"\${_hbr}\"; "
        cmd+="fi; "
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

# -----------------------------------------------------------------------------
# Onda T — cura de RAIZ do probe BT: módulo DKMS hid-nintendo patchado.
# A conf modprobe.d instalada acima é INERTE sem o módulo (o in-tree só loga
# "unknown parameter ignored"). Este bloco é o caminho OFICIAL dos formatos
# empacotados (.deb/rpm/arch instruem rodar este script no pós-instalação):
# sem ele, usuário de pacote nunca ganharia o módulo — a cura ficava
# reservada a quem roda ./install.sh de um checkout git.
# Fail-safe TOTAL (contrato do dkms_lib.sh): dkms/headers ausentes ou build
# falho = aviso honesto + segue; as regras udev já instaladas acima nunca são
# afetadas; NUNCA recarrega módulo (controles em uso não podem cair).
# -----------------------------------------------------------------------------
DKMS_SRC=""
for candidate in \
    "/app/share/hefesto-dualsense4unix/dkms/hid-nintendo" \
    "/usr/share/hefesto-dualsense4unix/dkms/hid-nintendo" \
    "${SCRIPT_DIR}/../assets/dkms/hid-nintendo" \
; do
    if [[ -f "${candidate}/dkms.conf" ]]; then
        DKMS_SRC="${candidate}"
        break
    fi
done
DKMS_LIB_SH=""
for candidate in \
    "/app/share/hefesto-dualsense4unix/scripts/dkms_lib.sh" \
    "/usr/share/hefesto-dualsense4unix/scripts/dkms_lib.sh" \
    "${SCRIPT_DIR}/dkms_lib.sh" \
; do
    if [[ -f "${candidate}" ]]; then
        DKMS_LIB_SH="${candidate}"
        break
    fi
done
if [[ -n "${DKMS_SRC}" && -n "${DKMS_LIB_SH}" ]]; then
    # A versão vem do dkms.conf (fonte da verdade) — nunca hardcoded aqui.
    DKMS_VER="$(sed -n 's/^PACKAGE_VERSION="\(.*\)"$/\1/p' "${DKMS_SRC}/dkms.conf")"
    if [[ -n "${DKMS_VER}" ]]; then
        # Rodando já como root (sudo bash …, o caminho documentado nos
        # pacotes) o dkms_lib.sh ainda prefixa sudo — shim inócuo quando o
        # binário sudo não existe no sistema.
        if [[ "$(id -u)" -eq 0 ]] && ! command -v sudo >/dev/null 2>&1; then
            sudo() { "$@"; }
        fi
        echo ""
        echo "Cura de raiz do probe BT (Onda T): módulo DKMS hid-nintendo patchado ..."
        # shellcheck source=dkms_lib.sh
        source "${DKMS_LIB_SH}"
        dkms_install_patched_module hefesto-hid-nintendo "${DKMS_VER}" \
            "${DKMS_SRC}" hid-nintendo
        if dkms_module_from_updates hid-nintendo; then
            echo "  módulo patchado staged (vence o in-tree no próximo boot/carregamento)"
        else
            echo "  módulo patchado NÃO staged (avisos acima) — driver in-tree continua (fail-safe)"
        fi
    fi
else
    echo ""
    echo "AVISO: fontes DKMS do hid-nintendo não encontradas neste formato — a conf"
    echo "       hefesto-hid-nintendo.conf fica inerte sem o módulo patchado (in-tree segue)."
fi

# -----------------------------------------------------------------------------
# Onda W — cura de RAIZ do fantasma USB do dongle WiFi: módulo DKMS rtw88_usb
# patchado (device-gone + usb_queue_reset_device, gate hang_reset). Mesmo
# caminho OFICIAL dos formatos empacotados da Onda T acima: sem este bloco,
# usuário de pacote nunca ganharia o módulo. Fail-safe TOTAL (contrato do
# dkms_lib.sh): dkms/headers ausentes ou build falho = aviso honesto + segue
# (in-tree continua); NUNCA recarrega módulo — o WiFi em uso não pode cair,
# a troca vale no próximo boot (replug NÃO troca módulo carregado).
# -----------------------------------------------------------------------------
RTW88_DKMS_SRC=""
for candidate in \
    "/app/share/hefesto-dualsense4unix/dkms/rtw88-usb" \
    "/usr/share/hefesto-dualsense4unix/dkms/rtw88-usb" \
    "${SCRIPT_DIR}/../assets/dkms/rtw88-usb" \
; do
    if [[ -f "${candidate}/dkms.conf" ]]; then
        RTW88_DKMS_SRC="${candidate}"
        break
    fi
done
if [[ -n "${RTW88_DKMS_SRC}" && -n "${DKMS_LIB_SH}" ]]; then
    # A versão vem do dkms.conf (fonte da verdade) — nunca hardcoded aqui.
    RTW88_DKMS_VER="$(sed -n 's/^PACKAGE_VERSION="\(.*\)"$/\1/p' "${RTW88_DKMS_SRC}/dkms.conf")"
    if [[ -n "${RTW88_DKMS_VER}" ]]; then
        # Mesmo shim do bloco acima: rodando já como root sem o binário sudo.
        if [[ "$(id -u)" -eq 0 ]] && ! command -v sudo >/dev/null 2>&1; then
            sudo() { "$@"; }
        fi
        echo ""
        echo "Cura de raiz do fantasma USB do dongle WiFi (Onda W): módulo DKMS rtw88_usb patchado ..."
        # shellcheck source=dkms_lib.sh
        source "${DKMS_LIB_SH}"
        dkms_install_patched_module hefesto-rtw88-usb "${RTW88_DKMS_VER}" \
            "${RTW88_DKMS_SRC}" rtw88_usb
        if dkms_module_from_updates rtw88_usb; then
            echo "  módulo patchado staged (vence o in-tree no próximo boot — NUNCA recarregamos com WiFi em uso)"
        else
            echo "  módulo patchado NÃO staged (avisos acima) — driver in-tree continua (fail-safe)"
        fi
    fi
else
    echo ""
    echo "AVISO: fontes DKMS do rtw88-usb não encontradas neste formato — sem o módulo"
    echo "       patchado o fantasma USB do dongle WiFi segue possível (in-tree continua)."
fi

echo ""
echo "Desconecte e reconecte o controle DualSense para aplicar as permissões."
echo "Confira com: ls -l /dev/hidraw* /dev/uinput"
