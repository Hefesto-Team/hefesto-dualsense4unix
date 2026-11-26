#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

MODO="instalar"
for argumento in "$@"; do
    case "${argumento}" in
        --remover) MODO="remover" ;;
        *)
            echo "uso: install-host-udev.sh [--remover]" >&2
            exit 2
            ;;
    esac
done

if [[ -e "${HEFESTO_MARCA_SANDBOX:-/.flatpak-info}" ]]; then
    _opcao=""
    [[ "${MODO}" == "remover" ]] && _opcao=" --remover"
    echo "Este ajudante grava no sistema, e de dentro do Flatpak o sistema não é alcançável."
    echo "Rode este comando num terminal do sistema (fora do Flatpak):"
    echo ""
    echo "  sudo bash \"\$(flatpak info --show-location ${FLATPAK_ID:-io.github.hefesto_team.hefesto_dualsense4unix})/files/bin/install-host-udev.sh\"${_opcao}"
    exit 1
fi

_elevar() {
    local cmd="$1" sem_elevacao="$2"
    if [[ "$(id -u)" -eq 0 ]]; then
        bash -c "${cmd}"
    elif command -v pkexec &>/dev/null; then
        echo "Esta operação requer senha de administrador (polkit)."
        echo ""
        pkexec bash -c "${cmd}"
    elif command -v sudo &>/dev/null; then
        if ! sudo -n true 2>/dev/null; then
            echo "AVISO: sudo requer senha para gravar em ${RULES_DEST}." >&2
            echo "       Se você está rodando sem TTY (CI, headless), cancele com Ctrl+C" >&2
            echo "       e use 'sudo bash $0' diretamente." >&2
            echo "" >&2
        fi
        sudo bash -c "${cmd}"
    else
        echo "ERRO: nenhum método de elevação de privilégio encontrado (pkexec ou sudo)." >&2
        echo "" >&2
        "${sem_elevacao}"
        exit 1
    fi
}

RULES_SRC=""
MODLOAD_SRC=""
for candidate in \
    "/app/share/hefesto-dualsense4unix/udev-rules" \
    "${SCRIPT_DIR}/../share/hefesto-dualsense4unix/udev-rules" \
    "/usr/share/hefesto-dualsense4unix/udev-rules" \
    "${SCRIPT_DIR}/../assets" \
; do
    if [[ -f "${candidate}/73-hefesto-ps5-controller.rules" ]]; then
        RULES_SRC="${candidate}"
        break
    fi
done

for candidate in \
    "/app/share/hefesto-dualsense4unix/modules-load" \
    "${SCRIPT_DIR}/../share/hefesto-dualsense4unix/modules-load" \
    "/usr/share/hefesto-dualsense4unix/modules-load" \
    "${SCRIPT_DIR}/../assets" \
; do
    if [[ -f "${candidate}/hefesto-dualsense4unix.conf" ]]; then
        MODLOAD_SRC="${candidate}"
        break
    fi
done

SNDQUIRK_SRC=""
for candidate in \
    "/app/share/hefesto-dualsense4unix/modprobe" \
    "${SCRIPT_DIR}/../share/hefesto-dualsense4unix/modprobe" \
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

BTUSB_SRC=""
for candidate in \
    "/app/share/hefesto-dualsense4unix/modprobe.d" \
    "${SCRIPT_DIR}/../share/hefesto-dualsense4unix/modprobe.d" \
    "/usr/share/hefesto-dualsense4unix/modprobe.d" \
    "${SCRIPT_DIR}/../assets/modprobe.d" \
; do
    if [[ -f "${candidate}/hefesto-btusb-no-autosuspend.conf" ]]; then
        BTUSB_SRC="${candidate}"
        break
    fi
done

HIDNINTENDO_SRC=""
for candidate in \
    "/app/share/hefesto-dualsense4unix/modprobe.d" \
    "${SCRIPT_DIR}/../share/hefesto-dualsense4unix/modprobe.d" \
    "/usr/share/hefesto-dualsense4unix/modprobe.d" \
    "${SCRIPT_DIR}/../assets/modprobe.d" \
; do
    if [[ -f "${candidate}/hefesto-hid-nintendo.conf" ]]; then
        HIDNINTENDO_SRC="${candidate}"
        break
    fi
done

HIDPLAYSTATION_SRC=""
for candidate in \
    "/app/share/hefesto-dualsense4unix/modprobe.d" \
    "${SCRIPT_DIR}/../share/hefesto-dualsense4unix/modprobe.d" \
    "/usr/share/hefesto-dualsense4unix/modprobe.d" \
    "${SCRIPT_DIR}/../assets/modprobe.d" \
; do
    if [[ -f "${candidate}/hefesto-hid-playstation.conf" ]]; then
        HIDPLAYSTATION_SRC="${candidate}"
        break
    fi
done

BROKER_BIN_SRC=""
for candidate in \
    "/app/share/hefesto-dualsense4unix/broker" \
    "${SCRIPT_DIR}/../share/hefesto-dualsense4unix/broker" \
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
    "${SCRIPT_DIR}/../share/hefesto-dualsense4unix/systemd" \
    "/usr/share/hefesto-dualsense4unix/systemd" \
    "${SCRIPT_DIR}/../assets/systemd" \
; do
    if [[ -f "${candidate}/hefesto-hidraw-broker.service" ]]; then
        BROKER_UNITS_SRC="${candidate}"
        break
    fi
done

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

BTRES_SCRIPTS_SRC=""
for candidate in \
    "/app/share/hefesto-dualsense4unix/scripts" \
    "${SCRIPT_DIR}/../share/hefesto-dualsense4unix/scripts" \
    "/usr/share/hefesto-dualsense4unix/scripts" \
    "${SCRIPT_DIR}" \
; do
    if [[ -f "${candidate}/bt_nosniff_now.sh" && -f "${candidate}/bt_bonds_snapshot.sh" ]]; then
        BTRES_SCRIPTS_SRC="${candidate}"
        break
    fi
done

BTRES_UNIT_SRC=""
for candidate in \
    "/app/share/hefesto-dualsense4unix/systemd" \
    "${SCRIPT_DIR}/../share/hefesto-dualsense4unix/systemd" \
    "/usr/share/hefesto-dualsense4unix/systemd" \
    "${SCRIPT_DIR}/../assets/systemd" \
; do
    if [[ -f "${candidate}/hefesto-bt-bonds-snapshot.service" ]]; then
        BTRES_UNIT_SRC="${candidate}"
        break
    fi
done

BTRES_INSTALL_OK=0
if [[ -n "${BTRES_SCRIPTS_SRC}" && -n "${BTRES_UNIT_SRC}" ]]; then
    BTRES_INSTALL_OK=1
fi

REGRA_ABERTA_SH=""
for candidate in \
    "/app/share/hefesto-dualsense4unix/scripts" \
    "${SCRIPT_DIR}/../share/hefesto-dualsense4unix/scripts" \
    "/usr/share/hefesto-dualsense4unix/scripts" \
    "${SCRIPT_DIR}" \
; do
    if [[ -f "${candidate}/regra_do_no_aberta.sh" ]]; then
        REGRA_ABERTA_SH="${candidate}/regra_do_no_aberta.sh"
        break
    fi
done

DISPARO_SH=""
for candidate in \
    "/app/share/hefesto-dualsense4unix/scripts" \
    "${SCRIPT_DIR}/../share/hefesto-dualsense4unix/scripts" \
    "/usr/share/hefesto-dualsense4unix/scripts" \
    "${SCRIPT_DIR}" \
; do
    if [[ -f "${candidate}/disparo_do_udev.sh" ]]; then
        DISPARO_SH="${candidate}/disparo_do_udev.sh"
        break
    fi
done

DKMS_LIB_SH=""
for candidate in \
    "/app/share/hefesto-dualsense4unix/scripts/dkms_lib.sh" \
    "${SCRIPT_DIR}/../share/hefesto-dualsense4unix/scripts/dkms_lib.sh" \
    "/usr/share/hefesto-dualsense4unix/scripts/dkms_lib.sh" \
    "${SCRIPT_DIR}/dkms_lib.sh" \
; do
    if [[ -f "${candidate}" ]]; then
        DKMS_LIB_SH="${candidate}"
        break
    fi
done
DKMS_DIR=""
for candidate in \
    "/app/share/hefesto-dualsense4unix/dkms" \
    "${SCRIPT_DIR}/../share/hefesto-dualsense4unix/dkms" \
    "/usr/share/hefesto-dualsense4unix/dkms" \
    "${SCRIPT_DIR}/../assets/dkms" \
; do
    if compgen -G "${candidate}/*/dkms.conf" >/dev/null; then
        DKMS_DIR="${candidate}"
        break
    fi
done

if [[ "${MODO}" == "instalar" && -z "${RULES_SRC}" ]]; then
    echo "ERRO: regras udev não encontradas em nenhum dos paths esperados." >&2
    echo "      Verifique a instalação." >&2
    exit 1
fi

if [[ "${MODO}" == "instalar" && -z "${DISPARO_SH}" ]]; then
    echo "ERRO: disparo_do_udev.sh não encontrado em nenhum dos paths esperados." >&2
    echo "      Verifique a instalação." >&2
    exit 1
fi

RULES_DEST="/etc/udev/rules.d"
MODLOAD_DEST="/etc/modules-load.d"

RULES=(
    "73-hefesto-ps5-controller.rules"
    "71-uhid.rules"
    "71-uinput.rules"
    "72-ps5-controller-autosuspend.rules"
    "72-hefesto-touchpad-motion-uaccess.rules"
    "76-dualsense-touchpad-libinput-ignore.rules"
    "77-dualsense-leds.rules"
    "78-dualsense-motion-not-joystick.rules"
    "79-external-controller-leds.rules"
    "80-motion-joydev-hide.rules"
    "81-hefesto-usb-power.rules"
    "81-hefesto-usb-host-power.rules"
    "82-nintendo-pro-nosniff.rules"
    "83-hefesto-bond-snapshot.rules"
    "84-nintendo-pro-variant.rules"
    "85-hefesto-o-cabo-assume.rules"
)

if [[ "${MODO}" == "remover" ]]; then
    REGRA_DO_NO_VELHA="70-ps5-controller.rules"
    LIB_DEST="/usr/local/lib/hefesto-dualsense4unix"
    UNIT_DEST="/etc/systemd/system"
    BONDS_DEST="/var/lib/hefesto-dualsense4unix"
    CONFS_DO_MODPROBE=(
        "hefesto-dualsense-storm.conf"
        "hefesto-btusb-no-autosuspend.conf"
        "hefesto-hid-nintendo.conf"
        "hefesto-hid-playstation.conf"
    )
    ARQUIVOS_DA_LIB=(
        "hefesto-hidraw-broker"
        "bt_nosniff_now.sh"
        "bt_bonds_snapshot.sh"
        "bt_active_mode.sh"
        "bt_ponte_privilegiada.sh"
    )
    UNIDADES=(
        "hefesto-hidraw-broker.service"
        "hefesto-hidraw-broker.socket"
        "hefesto-bt-bonds-snapshot.service"
    )

    _build_remove_cmd() {
        local cmd="" regra conf arquivo unidade
        cmd+="if command -v systemctl >/dev/null 2>&1; then "
        cmd+="systemctl disable --now hefesto-hidraw-broker.socket hefesto-hidraw-broker.service "
        cmd+="2>/dev/null || true; fi; "
        cmd+="if [ -x '${LIB_DEST}/hefesto-hidraw-broker' ]; then "
        cmd+="'${LIB_DEST}/hefesto-hidraw-broker' --restore-all-and-exit 2>/dev/null || true; fi; "
        for regra in "${RULES[@]}" "${REGRA_DO_NO_VELHA}"; do
            cmd+="rm -f '${RULES_DEST}/${regra}'; "
        done
        cmd+="rm -f '${MODLOAD_DEST}/hefesto-dualsense4unix.conf'; "
        for conf in "${CONFS_DO_MODPROBE[@]}"; do
            cmd+="rm -f '${SNDQUIRK_DEST}/${conf}'; "
        done
        for unidade in "${UNIDADES[@]}"; do
            cmd+="rm -f '${UNIT_DEST}/${unidade}'; "
        done
        for arquivo in "${ARQUIVOS_DA_LIB[@]}"; do
            cmd+="rm -f '${LIB_DEST}/${arquivo}'; "
        done
        cmd+="rmdir '${LIB_DEST}' 2>/dev/null || true; "
        cmd+="rmdir '${BONDS_DEST}/bt-bonds' 2>/dev/null || true; "
        cmd+="rmdir '${BONDS_DEST}' 2>/dev/null || true; "
        cmd+="systemctl daemon-reload 2>/dev/null || true; "
        cmd+="udevadm control --reload-rules; "
        if [[ -n "${DISPARO_SH}" ]]; then
            cmd+="bash '${DISPARO_SH}'; "
        fi
        cmd+="echo 'Regras e arquivos removidos.'"
        printf '%s' "${cmd}"
    }

    _manual_da_volta() {
        echo "Execute manualmente como root:" >&2
        echo "  sudo systemctl disable --now hefesto-hidraw-broker.socket hefesto-hidraw-broker.service" >&2
        echo "  sudo rm -f ${RULES_DEST}/${REGRA_DO_NO_VELHA} \\" >&2
        for regra in "${RULES[@]}"; do
            echo "       ${RULES_DEST}/${regra} \\" >&2
        done
        echo "       ${MODLOAD_DEST}/hefesto-dualsense4unix.conf" >&2
        for conf in "${CONFS_DO_MODPROBE[@]}"; do
            echo "  sudo rm -f ${SNDQUIRK_DEST}/${conf}" >&2
        done
        for conf in "${UNIDADES[@]}"; do
            echo "  sudo rm -f ${UNIT_DEST}/${conf}" >&2
        done
        echo "  sudo rm -rf ${LIB_DEST}" >&2
        echo "  sudo systemctl daemon-reload" >&2
        echo "  sudo udevadm control --reload-rules" >&2
    }

    _dkms_da_volta() {
        local conf fonte pacote ko ver
        for conf in "${DKMS_DIR}"/*/dkms.conf; do
            [[ -f "${conf}" ]] || continue
            fonte="${conf%/dkms.conf}"
            pacote="$(sed -n 's/^PACKAGE_NAME="\(.*\)"$/\1/p' "${conf}")"
            ko="$(sed -n 's/^BUILT_MODULE_NAME\[0\]="\(.*\)"$/\1/p' "${conf}")"
            ver="$(sed -n 's/^PACKAGE_VERSION="\(.*\)"$/\1/p' "${conf}")"
            [[ -n "${pacote}" && -n "${ko}" && -n "${ver}" ]] || continue
            if [[ -z "$(_dkms_status_texto "${pacote}/${ver}")" \
                  && ! -d "$(_dkms_src_root)/${pacote}-${ver}" ]]; then
                continue
            fi
            echo ""
            echo "Módulo DKMS patchado ${ko} (${pacote}) ..."
            dkms_remove_patched_module "${pacote}" "${ver}" "${ko}"
        done
    }

    echo "Hefesto - DualSense4Unix — remoção do que o ajudante gravou no sistema"
    echo ""
    _elevar "$(_build_remove_cmd)" _manual_da_volta

    if [[ -n "${DKMS_LIB_SH}" && -n "${DKMS_DIR}" ]]; then
        if [[ "$(id -u)" -eq 0 ]] && ! command -v sudo >/dev/null 2>&1; then
            sudo() { "$@"; }
        fi
        # shellcheck source=dkms_lib.sh
        source "${DKMS_LIB_SH}"
        _dkms_da_volta
        dkms_flush_initramfs
    fi

    echo ""
    echo "Feito. O grupo 'hefesto' e as cópias dos pareamentos em /var/lib/hefesto-dualsense4unix/bt-bonds/ ficam."
    echo "Os módulos do kernel de fábrica voltam a valer no próximo boot."
    exit 0
fi

echo "Hefesto - DualSense4Unix — instalação de regras udev"
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

REGRA_DO_NO="73-hefesto-ps5-controller.rules"
REGRA_DO_NO_VELHA="70-ps5-controller.rules"
REGRA_DO_NO_SRC="${RULES_SRC}/${REGRA_DO_NO}"
REGRA_DO_NO_TMPDIR=""
if [[ "${BROKER_INSTALL_OK}" -ne 1 ]]; then
    if [[ -n "${REGRA_ABERTA_SH}" ]]; then
        REGRA_DO_NO_TMPDIR="$(mktemp -d)"
        trap 'rm -rf "${REGRA_DO_NO_TMPDIR}"' EXIT
        if bash "${REGRA_ABERTA_SH}" "${RULES_SRC}/${REGRA_DO_NO}" \
                "${REGRA_DO_NO_TMPDIR}/${REGRA_DO_NO}"; then
            REGRA_DO_NO_SRC="${REGRA_DO_NO_TMPDIR}/${REGRA_DO_NO}"
            echo "AVISO: o broker NÃO será instalado — a ${REGRA_DO_NO} vai ABERTA."
            echo "       O nó do DualSense só nasce fechado quando existe quem o abra."
        else
            REGRA_DO_NO_SRC=""
            echo "AVISO: não foi possível gerar a variante aberta da ${REGRA_DO_NO};" >&2
            echo "       a variante NÃO será instalada (fechá-la sem broker travaria o controle)." >&2
        fi
    else
        REGRA_DO_NO_SRC=""
        echo "AVISO: sem broker e sem regra_do_no_aberta.sh — a ${REGRA_DO_NO} NÃO será instalada." >&2
        echo "       Fechá-la sem quem a abra deixaria o DualSense inutilizável." >&2
    fi
fi
if [[ -z "${REGRA_DO_NO_SRC}" ]]; then
    _restantes=()
    for regra in "${RULES[@]}"; do
        [[ "${regra}" == "${REGRA_DO_NO}" ]] || _restantes+=("${regra}")
    done
    RULES=("${_restantes[@]}")
fi

_unit_do_pacote_correta() {
    local dir unit_servico socket exec_do_broker
    for dir in "$@"; do
        unit_servico="${dir}/hefesto-hidraw-broker.service"
        socket="${dir}/hefesto-hidraw-broker.socket"
        [[ -f "${unit_servico}" && -f "${socket}" ]] || continue
        if grep -q '__[A-Z_]*__' "${unit_servico}" "${socket}"; then
            continue
        fi
        grep -q '^Environment=HEFESTO_BROKER_NO_NASCE_FECHADO=1$' "${unit_servico}" || continue
        exec_do_broker="$(sed -n 's/^ExecStart=\([^ ]*\).*/\1/p' "${unit_servico}" | head -n 1)"
        [[ -n "${exec_do_broker}" && -x "${exec_do_broker}" ]] || continue
        printf '%s' "${dir}"
        return 0
    done
    return 1
}

RENDER_DO_BROKER=""
if [[ -n "${DKMS_LIB_SH}" ]]; then
    # shellcheck source=dkms_lib.sh
    source "${DKMS_LIB_SH}"
    RENDER_DO_BROKER="$(declare -f _render_broker_units)"
fi
UNIT_DO_PACOTE=""
if [[ "${BROKER_INSTALL_OK}" -eq 1 ]]; then
    UNIT_DO_PACOTE="$(_unit_do_pacote_correta /usr/lib/systemd/system /lib/systemd/system || true)"
fi
NO_NASCE_FECHADO=0
if [[ -n "${REGRA_DO_NO_SRC}" && "${REGRA_DO_NO_SRC}" == "${RULES_SRC}/${REGRA_DO_NO}" ]]; then
    NO_NASCE_FECHADO=1
fi

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
if [[ -n "${HIDPLAYSTATION_SRC}" ]]; then
    echo "  - hefesto-hid-playstation.conf (retry de feature report do hid-playstation patchado)"
fi
if [[ -f /etc/modprobe.d/hefesto-uhid.conf ]]; then
    echo "  - contrapressão do uhid rearmada a quente (o pedido --uhid-contrapressao já está em /etc/modprobe.d)"
fi
if [[ "${BROKER_INSTALL_OK}" -eq 1 && -n "${UNIT_DO_PACOTE}" ]]; then
    echo "  - hefesto-hidraw-broker (a unit do pacote em ${UNIT_DO_PACOTE} é a que vale: só se liga, nada vai para /etc/systemd/system)"
elif [[ "${BROKER_INSTALL_OK}" -eq 1 ]]; then
    echo "  - hefesto-hidraw-broker (broker root hide-hidraw, BROKER-01; uid ${BROKER_SESSION_UID}, grupo ${BROKER_SESSION_GROUP})"
elif [[ -n "${BROKER_BIN_SRC}" && -n "${BROKER_UNITS_SRC}" ]]; then
    echo "  - hefesto-hidraw-broker NÃO instalado (SESSION_UID resolveu 0/root — rode este script a partir da sessão da usuária)"
fi
if [[ "${BTRES_INSTALL_OK}" -eq 1 ]]; then
    echo "  - bt_nosniff_now.sh + bt_bonds_snapshot.sh + hefesto-bt-bonds-snapshot.service"
    echo "    (os alvos do RUN+= das regras 82 e 83 — sem eles as duas regras são enfeite)"
fi
echo ""
if [[ "${BTRES_INSTALL_OK}" -eq 0 ]]; then
    echo "AVISO: este formato não traz os alvos do RUN+= das regras 82 e 83."
    echo "       As duas regras vão para o disco e ficam INERTES (o seu TEST== não acha"
    echo "       o alvo): o Pro Controller genuíno não perde o sniff na borda da conexão,"
    echo "       e o snapshot de bonds não é disparado quando um controle Bluetooth chega."
    echo "       Para ganhar as duas curas: clone o repositório e rode ./install.sh (sem"
    echo "       sudo — ele pede a senha por dentro)."
    echo ""
fi

_opcao_do_modprobe() {
    awk -v p="$2" '
        $1 == "options" {
            for (i = 3; i <= NF; i++) {
                n = index($i, "=")
                if (n > 1 && substr($i, 1, n - 1) == p) v = substr($i, n + 1)
            }
        }
        END { if (v !~ /^[A-Za-z0-9_.,:-]+$/) exit 1; print v }
    ' "$1" 2>/dev/null
}

_build_install_cmd() {
    local cmd="" _v
    cmd+="groupadd -f -r hefesto; "
    if [[ "${BROKER_SESSION_UID}" != "0" ]]; then
        local _vpad_user
        _vpad_user="$(id -un -- "${BROKER_SESSION_UID}" 2>/dev/null || true)"
        if [[ -n "${_vpad_user}" && "${_vpad_user}" != "root" ]]; then
            cmd+="usermod -aG hefesto '${_vpad_user}'; "
        fi
    fi
    for regra in "${RULES[@]}"; do
        local _origem="${RULES_SRC}/${regra}"
        if [[ "${regra}" == "${REGRA_DO_NO}" ]]; then
            _origem="${REGRA_DO_NO_SRC}"
        fi
        cmd+="install -Dm644 '${_origem}' '${RULES_DEST}/${regra}'; "
    done
    cmd+="rm -f '${RULES_DEST}/${REGRA_DO_NO_VELHA}'; "
    if [[ -n "${MODLOAD_SRC}" ]]; then
        cmd+="install -Dm644 '${MODLOAD_SRC}/hefesto-dualsense4unix.conf' "
        cmd+="'${MODLOAD_DEST}/hefesto-dualsense4unix.conf'; "
        cmd+="modprobe uinput 2>/dev/null || true; "
        cmd+="modprobe uhid 2>/dev/null || true; "
    fi
    if [[ -n "${SNDQUIRK_SRC}" ]]; then
        cmd+="install -Dm644 '${SNDQUIRK_SRC}/hefesto-dualsense-storm.conf' "
        cmd+="'${SNDQUIRK_DEST}/hefesto-dualsense-storm.conf'; "
        cmd+="printf '%s' '054c:0ce6:ignore_ctl_error|ctl_msg_delay_1m,054c:0df2:ignore_ctl_error|ctl_msg_delay_1m' "
        cmd+="> /sys/module/snd_usb_audio/parameters/quirk_flags 2>/dev/null || true; "
    fi
    if [[ -n "${BTUSB_SRC}" ]]; then
        cmd+="install -Dm644 '${BTUSB_SRC}/hefesto-btusb-no-autosuspend.conf' "
        cmd+="'${SNDQUIRK_DEST}/hefesto-btusb-no-autosuspend.conf'; "
        _v="$(_opcao_do_modprobe "${BTUSB_SRC}/hefesto-btusb-no-autosuspend.conf" enable_autosuspend)" \
            && cmd+="printf '${_v}' > /sys/module/btusb/parameters/enable_autosuspend 2>/dev/null || true; "
    fi
    if [[ -n "${HIDNINTENDO_SRC}" ]]; then
        cmd+="install -Dm644 '${HIDNINTENDO_SRC}/hefesto-hid-nintendo.conf' "
        cmd+="'${SNDQUIRK_DEST}/hefesto-hid-nintendo.conf'; "
        _v="$(_opcao_do_modprobe "${HIDNINTENDO_SRC}/hefesto-hid-nintendo.conf" bt_probe_retries)" \
            && cmd+="printf '${_v}' > /sys/module/hid_nintendo/parameters/bt_probe_retries 2>/dev/null || true; "
        _v="$(_opcao_do_modprobe "${HIDNINTENDO_SRC}/hefesto-hid-nintendo.conf" skip_tx_on_rate_exceeded)" \
            && cmd+="printf '${_v}' > /sys/module/hid_nintendo/parameters/skip_tx_on_rate_exceeded 2>/dev/null || true; "
        _v="$(_opcao_do_modprobe "${HIDNINTENDO_SRC}/hefesto-hid-nintendo.conf" usb_cmd_pad_to_report)" \
            && cmd+="printf '${_v}' > /sys/module/hid_nintendo/parameters/usb_cmd_pad_to_report 2>/dev/null || true; "
        _v="$(_opcao_do_modprobe "${HIDNINTENDO_SRC}/hefesto-hid-nintendo.conf" usb_send_conn_status)" \
            && cmd+="printf '${_v}' > /sys/module/hid_nintendo/parameters/usb_send_conn_status 2>/dev/null || true; "
        _v="$(_opcao_do_modprobe "${HIDNINTENDO_SRC}/hefesto-hid-nintendo.conf" usb_probe_degrade)" \
            && cmd+="printf '${_v}' > /sys/module/hid_nintendo/parameters/usb_probe_degrade 2>/dev/null || true; "
    fi
    if [[ -n "${HIDPLAYSTATION_SRC}" ]]; then
        cmd+="install -Dm644 '${HIDPLAYSTATION_SRC}/hefesto-hid-playstation.conf' "
        cmd+="'${SNDQUIRK_DEST}/hefesto-hid-playstation.conf'; "
        _v="$(_opcao_do_modprobe "${HIDPLAYSTATION_SRC}/hefesto-hid-playstation.conf" feature_retries)" \
            && cmd+="printf '${_v}' > /sys/module/hid_playstation/parameters/feature_retries 2>/dev/null || true; "
        _v="$(_opcao_do_modprobe "${HIDPLAYSTATION_SRC}/hefesto-hid-playstation.conf" ds4_short_pairing_info)" \
            && cmd+="printf '${_v}' > /sys/module/hid_playstation/parameters/ds4_short_pairing_info 2>/dev/null || true; "
        _v="$(_opcao_do_modprobe "${HIDPLAYSTATION_SRC}/hefesto-hid-playstation.conf" ds4_synthetic_mac)" \
            && cmd+="printf '${_v}' > /sys/module/hid_playstation/parameters/ds4_synthetic_mac 2>/dev/null || true; "
    fi
    if [[ -f /etc/modprobe.d/hefesto-uhid.conf ]]; then
        _v="$(_opcao_do_modprobe /etc/modprobe.d/hefesto-uhid.conf backpressure)" \
            && cmd+="printf '${_v}' > /sys/module/uhid/parameters/backpressure 2>/dev/null || true; "
    fi
    if [[ "${BROKER_INSTALL_OK}" -eq 1 && -n "${UNIT_DO_PACOTE:-}" ]]; then
        cmd+="rm -f /etc/systemd/system/hefesto-hidraw-broker.service "
        cmd+="/etc/systemd/system/hefesto-hidraw-broker.socket; "
        cmd+="systemctl daemon-reload; "
        cmd+="systemctl enable --now hefesto-hidraw-broker.socket; "
    elif [[ "${BROKER_INSTALL_OK}" -eq 1 ]]; then
        cmd+="install -Dm755 '${BROKER_BIN_SRC}/hidraw_broker.py' "
        cmd+="/usr/local/lib/hefesto-dualsense4unix/hefesto-hidraw-broker; "
        cmd+="${RENDER_DO_BROKER:-}"$'\n'
        cmd+="_hbr=\$(mktemp -d /tmp/hefesto-broker-render.XXXXXXXX) "
        cmd+="&& _render_broker_units '${BROKER_UNITS_SRC}/hefesto-hidraw-broker.service' "
        cmd+="'${BROKER_UNITS_SRC}/hefesto-hidraw-broker.socket' \"\${_hbr}\" '${NO_NASCE_FECHADO:-1}' "
        cmd+="|| { echo 'ERRO: render do broker falhou ou deixou marcador cru — broker NAO instalado' >&2; "
        cmd+="[ -n \"\${_hbr:-}\" ] && rm -rf \"\${_hbr}\"; _hbr=; }; "
        cmd+="if [ -n \"\${_hbr:-}\" ]; then "
        cmd+="install -Dm644 \"\${_hbr}/hefesto-hidraw-broker.service\" "
        cmd+="/etc/systemd/system/hefesto-hidraw-broker.service; "
        cmd+="install -Dm644 \"\${_hbr}/hefesto-hidraw-broker.socket\" "
        cmd+="/etc/systemd/system/hefesto-hidraw-broker.socket; "
        cmd+="systemctl daemon-reload; "
        cmd+="systemctl enable --now hefesto-hidraw-broker.socket; "
        cmd+="rm -rf \"\${_hbr}\"; "
        cmd+="fi; "
    fi
    if [[ "${BTRES_INSTALL_OK}" -eq 1 ]]; then
        cmd+="install -Dm755 '${BTRES_SCRIPTS_SRC}/bt_nosniff_now.sh' "
        cmd+="/usr/local/lib/hefesto-dualsense4unix/bt_nosniff_now.sh; "
        cmd+="install -Dm755 '${BTRES_SCRIPTS_SRC}/bt_bonds_snapshot.sh' "
        cmd+="/usr/local/lib/hefesto-dualsense4unix/bt_bonds_snapshot.sh; "
        cmd+="[ -f '${BTRES_SCRIPTS_SRC}/bt_active_mode.sh' ] && install -Dm755 "
        cmd+="'${BTRES_SCRIPTS_SRC}/bt_active_mode.sh' "
        cmd+="/usr/local/lib/hefesto-dualsense4unix/bt_active_mode.sh; "
        cmd+="[ -f '${BTRES_SCRIPTS_SRC}/bt_ponte_privilegiada.sh' ] && install -Dm755 "
        cmd+="'${BTRES_SCRIPTS_SRC}/bt_ponte_privilegiada.sh' "
        cmd+="/usr/local/lib/hefesto-dualsense4unix/bt_ponte_privilegiada.sh; "
        cmd+="install -Dm644 '${BTRES_UNIT_SRC}/hefesto-bt-bonds-snapshot.service' "
        cmd+="/etc/systemd/system/hefesto-bt-bonds-snapshot.service; "
        cmd+="install -d -m700 /var/lib/hefesto-dualsense4unix/bt-bonds; "
        cmd+="systemctl daemon-reload 2>/dev/null || true; "
    fi
    cmd+="udevadm control --reload-rules; "
    cmd+="bash '${DISPARO_SH}'; "
    cmd+="echo 'Regras instaladas com sucesso.'"
    printf '%s' "${cmd}"
}

INSTALL_CMD="$(_build_install_cmd)"

_manual_da_ida() {
    echo "Execute manualmente como root:" >&2
    for regra in "${RULES[@]}"; do
        if [[ "${regra}" == "${REGRA_DO_NO}" ]]; then
            echo "  sudo install -Dm644 ${REGRA_DO_NO_SRC} ${RULES_DEST}/${regra}" >&2
        else
            echo "  sudo install -Dm644 ${RULES_SRC}/${regra} ${RULES_DEST}/${regra}" >&2
        fi
    done
    echo "  sudo rm -f ${RULES_DEST}/${REGRA_DO_NO_VELHA}" >&2
    if [[ "${BTRES_INSTALL_OK}" -eq 1 ]]; then
        echo "  sudo install -Dm755 ${BTRES_SCRIPTS_SRC}/bt_nosniff_now.sh \\" >&2
        echo "       /usr/local/lib/hefesto-dualsense4unix/bt_nosniff_now.sh" >&2
        echo "  sudo install -Dm755 ${BTRES_SCRIPTS_SRC}/bt_bonds_snapshot.sh \\" >&2
        echo "       /usr/local/lib/hefesto-dualsense4unix/bt_bonds_snapshot.sh" >&2
        echo "  sudo install -Dm644 ${BTRES_UNIT_SRC}/hefesto-bt-bonds-snapshot.service \\" >&2
        echo "       /etc/systemd/system/hefesto-bt-bonds-snapshot.service" >&2
        echo "  sudo install -d -m700 /var/lib/hefesto-dualsense4unix/bt-bonds" >&2
    fi
    if [[ -n "${MODLOAD_SRC}" ]]; then
        echo "  sudo install -Dm644 ${MODLOAD_SRC}/hefesto-dualsense4unix.conf \\" >&2
        echo "       ${MODLOAD_DEST}/hefesto-dualsense4unix.conf" >&2
        echo "  sudo modprobe uinput" >&2
    fi
    echo "  sudo udevadm control --reload-rules" >&2
    echo "  sudo bash ${DISPARO_SH}" >&2
}

_elevar "${INSTALL_CMD}" _manual_da_ida

_depois_do_usb_f_hid() {
    if ! dkms_modulo_da_casa usb_f_hid; then
        echo "  módulo patchado NÃO staged (avisos acima) — o de fábrica continua: o jogo no Proton espera 5 s por pedido de feature"
    elif [[ ! -d /sys/module/usb_f_hid || -z "$(dkms_usb_f_hid_marcas_que_faltam /sys/module)" ]]; then
        echo "  módulo patchado staged (o curado já está carregado, ou entra no próximo carregamento)"
    elif [[ "$(cat /sys/module/usb_f_hid/refcnt 2>/dev/null)" == "0" ]] \
         && sudo modprobe -r usb_f_hid 2>/dev/null && sudo modprobe usb_f_hid 2>/dev/null; then
        echo "  usb_f_hid trocado a quente (nenhum pad no ar)"
    else
        echo "  módulo patchado staged — com pads USB virtuais no ar, vale no próximo boot (ou rode ./install.sh, que solta os pads e troca)"
    fi
}

_depois_do_modulo() {
    local ko="$1"
    if [[ "${ko}" == "rtw88_usb" && -e /sys/module/rtw88_usb/parameters/hang_reset ]]; then
        printf 'Y' | sudo tee /sys/module/rtw88_usb/parameters/hang_reset >/dev/null 2>&1 || true
        echo "  hang_reset rearmado a quente (vale já; sem reload, sem reboot)"
    fi
    if dkms_modulo_da_casa "${ko}"; then
        echo "  módulo patchado staged (vence o in-tree no próximo boot/carregamento — NUNCA recarregamos com o aparelho em uso)"
    else
        echo "  módulo patchado NÃO staged (avisos acima) — o driver de fábrica continua (fail-safe)"
    fi
}

_dkms_do_dono() {
    local conf fonte pacote ko ver
    for conf in "${DKMS_DIR}"/*/dkms.conf; do
        [[ -f "${conf}" ]] || continue
        fonte="${conf%/dkms.conf}"
        pacote="$(sed -n 's/^PACKAGE_NAME="\(.*\)"$/\1/p' "${conf}")"
        ko="$(sed -n 's/^BUILT_MODULE_NAME\[0\]="\(.*\)"$/\1/p' "${conf}")"
        ver="$(sed -n 's/^PACKAGE_VERSION="\(.*\)"$/\1/p' "${conf}")"
        [[ -n "${pacote}" && -n "${ko}" && -n "${ver}" ]] || continue
        if [[ "${ko}" == "uhid" && "${COM_UHID_CONTRAPRESSAO:-0}" -ne 1 \
              && ! -f "${HEFESTO_UHID_CONF:-/etc/modprobe.d/hefesto-uhid.conf}" ]]; then
            echo ""
            echo "uhid com contrapressão: pulado (opt-in: ./install.sh --uhid-contrapressao); o de fábrica segue"
            continue
        fi
        echo ""
        echo "Módulo DKMS patchado ${ko} (${pacote}) ..."
        dkms_install_patched_module "${pacote}" "${ver}" "${fonte}" "${ko}"
        case "${ko}" in
            usb_f_hid) _depois_do_usb_f_hid ;;
            *) _depois_do_modulo "${ko}" ;;
        esac
    done
}

if [[ -n "${DKMS_DIR}" && -n "${DKMS_LIB_SH}" ]]; then
    if [[ "$(id -u)" -eq 0 ]] && ! command -v sudo >/dev/null 2>&1; then
        sudo() { "$@"; }
    fi
    # shellcheck source=dkms_lib.sh
    source "${DKMS_LIB_SH}"
    _dkms_do_dono
else
    echo ""
    echo "AVISO: fontes DKMS não encontradas neste formato — sem os módulos patchados, a"
    echo "       contenção BT, o microfone pelo rádio, o GET_REPORT dos pads virtuais e o"
    echo "       fantasma USB do dongle WiFi seguem possíveis (os drivers de fábrica continuam)."
fi

if [[ -n "${DKMS_LIB_SH}" ]]; then
    # shellcheck source=dkms_lib.sh
    source "${DKMS_LIB_SH}"
    dkms_fontes_so_do_root || true
    dkms_flush_initramfs
fi

echo ""
echo "Desconecte e reconecte o controle DualSense para aplicar as permissões."
echo "Confira com: ls -l /dev/hidraw* /dev/uinput"
