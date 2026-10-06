#!/usr/bin/env bash
# p4-vm.sh — o degrau P4 da escada da máquina limpa: o SISTEMA INTEIRO, numa
# VM KVM sem janela, dirigida pelo QMP. Muda o sistema; depois, um aparelho
# por vez (o cabo, o rádio).
#
# O-PRODUTO-EM-QUALQUER-MAQUINA-01 (28/09/2026), a Parte A. É o único degrau
# que alcança o que nenhum outro alcança: o COSMIC do pacote, o DKMS
# carregando depois do reinício, o Secure Boot, o `uaccess` sem o grupo
# `input`, o pareamento do zero e a `.venv` com o que o pip entrega — e o
# aparelho de verdade, passado pelo cabo e pelo rádio. O usuário liberou a VM nesta
# máquina em 28/09 (*«pode usar o Pc atual como VM»*); o `qemu-system-x86`, o
# `qemu-utils` e o `ovmf` são o pedido 1 dela, e sem eles este script diz isso
# e sai.
#
# AS TRAVAS, e nenhuma é opcional:
#   - a VM roda SEM JANELA (`-display none`): cada tela vem por `screendump`
#     para um PNG que se lê com calma. Nada nasce na tela do usuário, e não existe
#     flag que abra uma janela;
#   - o QMP é um socket na pasta da VM, e é por ele que tudo se dirige;
#   - passar um aparelho TIRA o aparelho do daemon do usuário até a devolução. O
#     `passar` recusa sem o `--sei-que-tira`, e o `devolver` é o caminho de
#     volta (depois dele, o controle volta pelo «Mover» da aba Conexões);
#   - o que sai de dentro da VM com endereço de aparelho passa pelo mascarador
#     antes de ir para o disco (`HEFESTO_MASCARA_SED`); sem ele, o `guardar`
#     recusa.
#
# Uso:
#   p4-vm.sh criar  [--disco 60G]               o disco e as variáveis da UEFI
#   p4-vm.sh ligar  --iso ARQ [--secboot]       sobe a VM (P4c: --secboot)
#   p4-vm.sh ligar                              sobe do disco
#   p4-vm.sh foto   ARQ.png                     a tela da VM, sem janela
#   p4-vm.sh digitar TEXTO                      teclas pelo QMP (ASCII)
#   p4-vm.sh tecla  NOME [NOME...]              uma combinação (ex.: ret, ctrl alt t)
#   p4-vm.sh passar HOSTBUS HOSTADDR ID --sei-que-tira
#   p4-vm.sh devolver ID                        tira o aparelho da VM
#   p4-vm.sh guardar ORIGEM DESTINO             copia um relato, mascarado
#   p4-vm.sh desligar                           pede o desligamento à VM
#   p4-vm.sh estado                             a VM está de pé?
#
# A pasta da VM é `HEFESTO_VM_DIR` (padrão: ~/vm-hefesto). A ISO é a do
# Pop!_OS 24.04 sem NVIDIA, baixada do site oficial e conferida pelo sha256
# publicado. As medidas de cada volta (P4a cabo, P4b rádio, P4c Secure Boot,
# P4d a Steam instalada depois) estão em `LEIA.md`, ao lado.

set -euo pipefail

VM="${HEFESTO_VM_DIR:-${HOME}/vm-hefesto}"
QMP="${VM}/qmp.sock"
PID="${VM}/qemu.pid"
OVMF_CODE="${HEFESTO_OVMF_CODE:-/usr/share/OVMF/OVMF_CODE_4M.fd}"
OVMF_VARS="${HEFESTO_OVMF_VARS:-/usr/share/OVMF/OVMF_VARS_4M.fd}"
OVMF_CODE_SB="${HEFESTO_OVMF_CODE_SB:-/usr/share/OVMF/OVMF_CODE_4M.secboot.fd}"
OVMF_VARS_SB="${HEFESTO_OVMF_VARS_SB:-/usr/share/OVMF/OVMF_VARS_4M.ms.fd}"

_precisa() {
    local falta=()
    command -v qemu-system-x86_64 >/dev/null 2>&1 || falta+=(qemu-system-x86)
    command -v qemu-img >/dev/null 2>&1 || falta+=(qemu-utils)
    [[ -r "${OVMF_CODE}" ]] || falta+=(ovmf)
    if (( ${#falta[@]} )); then
        printf 'faltam %s nesta máquina — é o pedido 1 da sprint (quem instala é ela)\n' "${falta[*]}" >&2
        exit 3
    fi
}

_de_pe() { [[ -r "${PID}" ]] && kill -0 "$(cat "${PID}")" 2>/dev/null; }

# Fala com o QMP: negocia as capacidades e manda UM comando em JSON.
_qmp() {
    _de_pe || { echo "a VM não está de pé" >&2; exit 1; }
    python3 - "${QMP}" "$1" <<'PYEOF'
import json, socket, sys
s = socket.socket(socket.AF_UNIX)
s.connect(sys.argv[1])
f = s.makefile("rw")
json.loads(f.readline())
for comando in ({"execute": "qmp_capabilities"}, json.loads(sys.argv[2])):
    f.write(json.dumps(comando) + "\n"); f.flush()
    while True:
        resposta = json.loads(f.readline())
        if "event" not in resposta:
            break
    if "error" in resposta:
        print(resposta["error"].get("desc", resposta), file=sys.stderr)
        raise SystemExit(1)
print(json.dumps(resposta.get("return", {})))
PYEOF
}

acao="${1:-}"; shift || true
case "${acao}" in
    criar)
        _precisa
        tam="60G"; [[ "${1:-}" == "--disco" ]] && tam="$2"
        mkdir -p "${VM}"
        [[ -e "${VM}/disco.qcow2" ]] || qemu-img create -q -f qcow2 "${VM}/disco.qcow2" "${tam}"
        [[ -e "${VM}/vars.fd" ]] || cp "${OVMF_VARS}" "${VM}/vars.fd"
        [[ -e "${VM}/vars-sb.fd" || ! -r "${OVMF_VARS_SB}" ]] || cp "${OVMF_VARS_SB}" "${VM}/vars-sb.fd"
        echo "VM criada em ${VM}"
        ;;
    ligar)
        _precisa
        _de_pe && { echo "a VM já está de pé (pid $(cat "${PID}"))"; exit 0; }
        iso=""; codigo="${OVMF_CODE}"; vars="${VM}/vars.fd"
        while (( $# )); do
            case "$1" in
                --iso) iso="$2"; shift 2 ;;
                --secboot) codigo="${OVMF_CODE_SB}"; vars="${VM}/vars-sb.fd"; shift ;;
                *) echo "argumento desconhecido: $1" >&2; exit 2 ;;
            esac
        done
        [[ -r "${VM}/disco.qcow2" ]] || { echo "rode «criar» antes" >&2; exit 2; }
        extra=()
        [[ -n "${iso}" ]] && extra+=(-cdrom "${iso}")
        qemu-system-x86_64 -enable-kvm -machine q35 -m 6G -smp 4 \
            -drive "if=pflash,format=raw,readonly=on,file=${codigo}" \
            -drive "if=pflash,format=raw,file=${vars}" \
            -drive "file=${VM}/disco.qcow2,if=virtio" "${extra[@]}" \
            -device qemu-xhci,id=xhci -vga virtio -display none \
            -qmp "unix:${QMP},server,nowait" -nic user \
            -daemonize -pidfile "${PID}"
        echo "VM de pé, sem janela (pid $(cat "${PID}")); a tela: p4-vm.sh foto tela.png"
        ;;
    foto)
        alvo="$(readlink -f "${1:?diga o arquivo .png}")"
        _qmp "{\"execute\": \"screendump\", \"arguments\": {\"filename\": \"${alvo}\", \"format\": \"png\"}}" >/dev/null
        echo "${alvo}"
        ;;
    digitar)
        texto="${1:?diga o texto}"
        python3 - "${texto}" <<'PYEOF' | while IFS= read -r cmd; do _qmp "${cmd}" >/dev/null; done
import json, sys
especiais = {" ": "spc", "\n": "ret", "-": "minus", ".": "dot", "/": "slash", "_": ("shift", "minus"),
             ":": ("shift", "semicolon"), "=": "equal", ",": "comma", ";": "semicolon"}
for c in sys.argv[1]:
    if c.isalnum() and c.isascii():
        teclas = ("shift", c.lower()) if c.isupper() else (c,)
    else:
        nome = especiais.get(c)
        if nome is None:
            raise SystemExit(f"caractere sem tecla: {c!r}")
        teclas = nome if isinstance(nome, tuple) else (nome,)
    print(json.dumps({"execute": "send-key", "arguments": {"keys": [{"type": "qcode", "data": t} for t in teclas]}}))
PYEOF
        ;;
    tecla)
        (( $# )) || { echo "diga a tecla" >&2; exit 2; }
        teclas="$(printf '{"type": "qcode", "data": "%s"},' "$@")"
        _qmp "{\"execute\": \"send-key\", \"arguments\": {\"keys\": [${teclas%,}]}}" >/dev/null
        ;;
    passar)
        bus="${1:?hostbus}"; addr="${2:?hostaddr}"; id="${3:?um id para devolver depois}"
        [[ "${4:-}" == "--sei-que-tira" ]] || {
            echo "passar um aparelho o TIRA do daemon dela até a devolução; repita com --sei-que-tira" >&2
            exit 2; }
        _qmp "{\"execute\": \"device_add\", \"arguments\": {\"driver\": \"usb-host\", \"bus\": \"xhci.0\", \"hostbus\": ${bus}, \"hostaddr\": ${addr}, \"id\": \"${id}\"}}" >/dev/null
        echo "aparelho ${bus}:${addr} na VM como «${id}» — devolva com: p4-vm.sh devolver ${id}"
        ;;
    devolver)
        id="${1:?o id do passar}"
        _qmp "{\"execute\": \"device_del\", \"arguments\": {\"id\": \"${id}\"}}" >/dev/null
        echo "«${id}» saiu da VM; o controle volta pelo «Mover» da aba Conexões"
        ;;
    guardar)
        origem="${1:?o relato}"; destino="${2:?onde guardar}"
        mascara="${HEFESTO_MASCARA_SED:-}"
        [[ -n "${mascara}" && -r "${mascara}" ]] || {
            echo "sem HEFESTO_MASCARA_SED legível: um relato com aparelho não vai ao disco sem máscara" >&2
            exit 2; }
        sed -E -f "${mascara}" "${origem}" > "${destino}"
        echo "${destino}"
        ;;
    desligar)
        _qmp '{"execute": "system_powerdown"}' >/dev/null
        echo "desligamento pedido à VM"
        ;;
    estado)
        if _de_pe; then echo "de pé (pid $(cat "${PID}"))"; else echo "desligada"; fi
        ;;
    *)
        sed -n '2,45p' "${BASH_SOURCE[0]}"
        [[ -z "${acao}" || "${acao}" == -h || "${acao}" == --help ]] || exit 2
        ;;
esac
