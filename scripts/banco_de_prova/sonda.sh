#!/usr/bin/env bash

set -u
set -o pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PASTA="${SONDA_PASTA:-${PWD}/sonda-saida}"
SAIDA="${PASTA}/sonda.txt"
PLASTICO="${RAIZ}/scripts/banco_de_prova/sonda_plastico.py"
SYS="${SONDA_SYS:-/sys}"
DEV="${SONDA_DEV:-/dev}"
FERRAMENTAS_DO_KERNEL="${SONDA_LINUX_TOOLS:-/usr/lib/linux-tools}"
PY="$(command -v python3 || true)"
MAC_DO_RADIO="aa:bb:cc:00:00:01"
MAC_DO_CABO="aa:bb:cc:00:00:02"

mkdir -p "${PASTA}"
: >"${SAIDA}"

reg() { printf '%s=%s\n' "$1" "$2" | tee -a "${SAIDA}"; }

valor() { grep "^$1=" "${SAIDA}" | tail -n 1 | cut -d= -f2-; }

absorver() {
    local arquivo="$1" prefixo="$2"
    if [[ -s "${arquivo}" ]]; then
        sed "s/^/${prefixo}/" "${arquivo}" | tee -a "${SAIDA}"
    else
        reg "${prefixo}veredito" "não-mediu: ${arquivo##*/} vazio (o verbo não escreveu)"
    fi
}

sudo_ok() { sudo -n true 2>/dev/null; }

carregar() {
    local m
    for m in "$@"; do sudo -n modprobe "${m}" >>"${PASTA}/modprobe.log" 2>&1 || true; done
}

modulo_no_kernel() {
    local nome="${1//-/_}"
    if [[ -d "${SYS}/module/${nome}" ]]; then echo "carregado"
    elif sudo -n modinfo -n "$1" >/dev/null 2>&1; then echo "existe-não-carregou"
    else echo "ausente"; fi
}

reg kernel "$(uname -r)"
reg virtualizacao "$(systemd-detect-virt --vm 2>/dev/null || echo nenhuma)"
reg sudo_sem_senha "$(sudo_ok && echo sim || echo não)"
reg python "${PY:-ausente}"

if ! sudo_ok || [[ -z "${PY}" ]]; then
    reg casa_radio "so_na_vm"
    reg casa_cabo "so_da_mao"
    reg motivo "não-mediu: sem sudo sem senha ou sem python3 no runner"
    exit 1
fi

carregar uhid uinput hid_playstation
if [[ ! -d "${SYS}/module/uhid" && ! -e "${DEV}/uhid" ]] || [[ ! -d "${SYS}/module/hid_playstation" ]]; then
    reg extra_tentado "linux-modules-extra-$(uname -r)"
    sudo -n apt-get install -y "linux-modules-extra-$(uname -r)" >"${PASTA}/apt-extra.log" 2>&1
    reg extra_rc "$?"
    carregar uhid uinput hid_playstation
fi
for m in uhid uinput hid_playstation; do reg "modulo_${m}" "$(modulo_no_kernel "${m}")"; done
reg dev_uhid "$([[ -e "${DEV}/uhid" ]] && echo sim || echo não)"

timeout 60 sudo -n "${PY}" "${PLASTICO}" radio --saida "${PASTA}/radio.txt" \
    --mac "${MAC_DO_RADIO}" --segundos 10 --sys "${SYS}" >"${PASTA}/radio.log" 2>&1
reg radio_rc "$?"
absorver "${PASTA}/radio.txt" "radio_"
sudo -n dmesg 2>&1 | tail -n 80 >"${PASTA}/dmesg-radio.log"
reg radio_dmesg_playstation "$(grep -ci 'playstation\|dualsense' "${PASTA}/dmesg-radio.log")"

GADGET="${SYS}/kernel/config/usb_gadget/sonda"
USBIPD_PID=""

limpar_o_cabo() {
    sudo -n bash -c "
        [[ -d '${GADGET}' ]] || exit 0
        echo '' >'${GADGET}/UDC' 2>/dev/null
        rm -f '${GADGET}/configs/c.1/hid.usb0'
        rmdir '${GADGET}/configs/c.1/strings/0x409' '${GADGET}/configs/c.1' 2>/dev/null
        rmdir '${GADGET}/functions/hid.usb0' '${GADGET}/strings/0x409' '${GADGET}' 2>/dev/null
        exit 0" >/dev/null 2>&1
    if [[ -n "${USBIPD_PID}" ]] && kill -0 "${USBIPD_PID}" 2>/dev/null; then
        sudo -n kill -TERM "${USBIPD_PID}" 2>/dev/null
    fi
}

o_cabo() {
    local m faltam=""
    for m in libcomposite usb_f_hid usbip-vudc vhci-hcd; do
        carregar "${m}"
        local estado
        estado="$(modulo_no_kernel "${m}")"
        reg "cabo_modulo_${m//-/_}" "${estado}"
        [[ "${estado}" == "carregado" ]] || faltam="${faltam} ${m}"
    done
    if [[ -n "${faltam}" ]]; then
        reg cabo_veredito "sem-modulo:${faltam}"
        return 0
    fi

    sudo -n mountpoint -q "${SYS}/kernel/config" || sudo -n mount -t configfs none "${SYS}/kernel/config"
    local udc
    udc="$(basename "$(compgen -G "${SYS}/class/udc/usbip-vudc*" | head -n 1)" 2>/dev/null)"
    [[ "${udc}" == "." || "${udc}" == "usbip-vudc*" ]] && udc=""
    reg cabo_udc "${udc:-nenhum}"
    if [[ -z "${udc}" ]]; then
        reg cabo_veredito "sem-udc: o usbip-vudc carregou e não criou o controlador"
        return 0
    fi

    sudo -n env GADGET="${GADGET}" DESCRITOR="${RAIZ}/tests/fixtures/hid/dualsense_usb_descriptor_054c0ce6.bin" \
        bash -s >"${PASTA}/gadget.log" 2>&1 <<'CONFIGFS'
set -e
mkdir -p "${GADGET}"
echo 0x054c >"${GADGET}/idVendor"
echo 0x0ce6 >"${GADGET}/idProduct"
echo 0x0200 >"${GADGET}/bcdUSB"
mkdir -p "${GADGET}/strings/0x409"
echo "aa:bb:cc:00:00:02" >"${GADGET}/strings/0x409/serialnumber"
echo "Sonda" >"${GADGET}/strings/0x409/manufacturer"
echo "DualSense Sonda" >"${GADGET}/strings/0x409/product"
mkdir -p "${GADGET}/configs/c.1/strings/0x409"
echo "hid" >"${GADGET}/configs/c.1/strings/0x409/configuration"
mkdir -p "${GADGET}/functions/hid.usb0"
echo 0 >"${GADGET}/functions/hid.usb0/protocol"
echo 0 >"${GADGET}/functions/hid.usb0/subclass"
echo 64 >"${GADGET}/functions/hid.usb0/report_length"
cat "${DESCRITOR}" >"${GADGET}/functions/hid.usb0/report_desc"
ln -s "${GADGET}/functions/hid.usb0" "${GADGET}/configs/c.1/"
CONFIGFS
    reg cabo_gadget_rc "$?"
    if [[ ! -d "${GADGET}/functions/hid.usb0" ]]; then
        reg cabo_veredito "não-mediu: o gadget não foi montado no configfs (ver gadget.log)"
        return 0
    fi

    sudo -n bash -c "echo '${udc}' >'${GADGET}/UDC'" >>"${PASTA}/gadget.log" 2>&1
    reg cabo_udc_amarrado_rc "$?"
    local i
    for i in 1 2 3 4 5 6 7 8 9 10; do [[ -e "${DEV}/hidg0" ]] && break; sleep 0.5; done
    reg cabo_hidg0 "$([[ -e "${DEV}/hidg0" ]] && echo sim || echo não)"
    if [[ ! -e "${DEV}/hidg0" ]]; then
        reg cabo_veredito "sem-hidg: o gadget amarrou e o /dev/hidg0 não nasceu"
        return 0
    fi
    sudo -n "${PY}" "${PLASTICO}" cabo-features --saida "${PASTA}/cabo-features.txt" \
        --mac "${MAC_DO_CABO}" --hidg "${DEV}/hidg0" >"${PASTA}/cabo-features.log" 2>&1
    absorver "${PASTA}/cabo-features.txt" "cabo_"

    local usbip usbipd
    usbip="$(compgen -G "${FERRAMENTAS_DO_KERNEL}/*/usbip" | tail -n 1)"
    usbipd="$(compgen -G "${FERRAMENTAS_DO_KERNEL}/*/usbipd" | tail -n 1)"
    if [[ -z "${usbip}" || -z "${usbipd}" ]]; then
        sudo -n apt-get install -y linux-tools-generic hwdata >"${PASTA}/apt-usbip.log" 2>&1
        reg cabo_apt_usbip_rc "$?"
        usbip="$(compgen -G "${FERRAMENTAS_DO_KERNEL}/*/usbip" | tail -n 1)"
        usbipd="$(compgen -G "${FERRAMENTAS_DO_KERNEL}/*/usbipd" | tail -n 1)"
    fi
    if [[ -z "${usbip}" || -z "${usbipd}" ]]; then
        reg cabo_veredito "não-mediu: sem o usbip/usbipd (linux-tools) neste runner"
        return 0
    fi
    sudo -n "${usbipd}" >"${PASTA}/usbipd.log" 2>&1 &
    USBIPD_PID="$!"
    sleep 1
    timeout 30 sudo -n "${usbip}" attach -r 127.0.0.1 -b "${udc}" >"${PASTA}/usbip-attach.log" 2>&1
    reg cabo_attach_rc "$?"
    for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16; do
        compgen -G "${SYS}/bus/hid/drivers/playstation/0003:054C:0CE6.*" >/dev/null && break
        sleep 0.5
    done
    if compgen -G "${SYS}/bus/hid/drivers/playstation/0003:054C:0CE6.*" >/dev/null; then
        reg cabo_registrou sim
        reg cabo_veredito "o usb_f_hid respondeu o GET_REPORT de feature e o hid_playstation registrou o gadget"
    else
        reg cabo_registrou não
        reg cabo_veredito "o gadget enumerou e o hid_playstation não registrou (ver dmesg-cabo.log)"
    fi
    sudo -n dmesg 2>&1 | tail -n 120 >"${PASTA}/dmesg-cabo.log"
}
o_cabo
limpar_o_cabo

DAEMON_PID=""
PLASTICO_PID=""

limpar_o_hefesto() {
    if [[ -n "${PLASTICO_PID}" ]] && kill -0 "${PLASTICO_PID}" 2>/dev/null; then
        sudo -n kill -TERM "${PLASTICO_PID}" 2>/dev/null
    fi
    if [[ -n "${DAEMON_PID}" ]] && kill -0 "${DAEMON_PID}" 2>/dev/null; then
        kill -TERM "${DAEMON_PID}" 2>/dev/null
    fi
}

o_hefesto() {
    (cd "${RAIZ}" && timeout 1500 ./install.sh --yes --no-proton-pin) >"${PASTA}/install.log" 2>&1
    reg install_rc "$?"
    reg broker_socket "$(systemctl is-active hefesto-hidraw-broker.socket 2>&1 | head -n 1)"
    reg regra_udev_73 "$(compgen -G '/etc/udev/rules.d/*hefesto*' >/dev/null \
        || compgen -G '/usr/lib/udev/rules.d/*hefesto*' >/dev/null && echo sim || echo não)"

    local bin
    bin="$(command -v hefesto-dualsense4unix 2>/dev/null || true)"
    [[ -x "${bin}" ]] || bin="${HOME}/.local/bin/hefesto-dualsense4unix"
    if [[ ! -x "${bin}" ]]; then
        reg acl_veredito "não-mediu: o install não deixou o binário do produto (ver install.log)"
        return 0
    fi
    "${bin}" daemon start --foreground >"${PASTA}/daemon.log" 2>&1 &
    DAEMON_PID="$!"
    sleep 6
    reg daemon_vivo "$(kill -0 "${DAEMON_PID}" 2>/dev/null && echo sim || echo não)"

    sudo -n "${PY}" "${PLASTICO}" radio --saida "${PASTA}/radio-fica.txt" --mac "${MAC_DO_RADIO}" \
        --segundos 15 --sys "${SYS}" --fica >"${PASTA}/radio-fica.log" 2>&1 &
    PLASTICO_PID="$!"
    local i
    for i in $(seq 1 30); do
        [[ -s "${PASTA}/radio-fica.txt" ]] && break
        sleep 1
    done
    absorver "${PASTA}/radio-fica.txt" "radio_com_hefesto_"

    for i in $(seq 1 20); do
        "${PY}" "${PLASTICO}" acl --saida "${PASTA}/acl.txt" --sys "${SYS}" >/dev/null 2>&1
        grep -q '^acl_hidraw_nos=.\+' "${PASTA}/acl.txt" 2>/dev/null && break
        sleep 1
    done
    absorver "${PASTA}/acl.txt" ""
    { ls -l /dev/hidraw* /dev/input/event* 2>&1; id; } >"${PASTA}/nos-e-usuario.log"
    if command -v getfacl >/dev/null 2>&1; then
        getfacl -p /dev/hidraw* /dev/input/event* >>"${PASTA}/nos-e-usuario.log" 2>&1
    fi
    sudo -n dmesg 2>&1 | tail -n 120 >"${PASTA}/dmesg-hefesto.log"
}
o_hefesto
limpar_o_hefesto

casa_radio="so_na_vm"
if [[ "$(valor radio_registrou)" == "sim" && "$(valor acl_hidraw)" == "sim" \
      && "$(valor acl_evdev)" == "sim" ]]; then
    casa_radio="no_runner"
fi
casa_cabo="so_da_mao"
if [[ "$(valor cabo_registrou)" == "sim" ]]; then
    casa_cabo="no_runner"
fi
reg casa_radio "${casa_radio}"
reg casa_cabo "${casa_cabo}"

nao_mediu="$(grep -c 'não-mediu\|não-achou' "${SAIDA}")"
reg medidas_que_nao_se_fizeram "${nao_mediu}"

if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then
    {
        echo "## A sonda do banco de prova"
        echo
        echo "| decisão | resultado |"
        echo "| --- | --- |"
        echo "| rádio (uhid + hid_playstation + ACL do pad) | \`${casa_radio}\` |"
        echo "| cabo (usb_f_hid responde o GET_REPORT) | \`${casa_cabo}\` |"
        echo "| medidas que não se fizeram | ${nao_mediu} |"
        echo
        echo '```'
        cat "${SAIDA}"
        echo '```'
    } >>"${GITHUB_STEP_SUMMARY}"
fi

[[ -n "$(valor casa_radio)" && -n "$(valor casa_cabo)" ]]
