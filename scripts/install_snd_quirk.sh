#!/usr/bin/env bash
# install_snd_quirk.sh — cura de RAIZ do storm -71 do DualSense na camada de ÁUDIO.
#
# CONTEXTO: o storm -71 (EPROTO) é disparado pela enumeração das interfaces de
# ÁUDIO USB do DualSense — o snd-usb-audio sonda o mixer UAC e MARTELA o EP0
# ("cannot get min/max values for control"), colidindo com o `usbhid` que anexa a
# interface HID → "can't add hid device: -71" → USB disconnect em loop.
#
# ESTE script instala um drop-in de modprobe.d que aplica o parâmetro por-device
# `quirk_flags` do snd_usb_audio para 054c:0ce6/0df2:
#   ignore_ctl_error  — tolera o erro do mixer (card sobe com defaults).
#   ctl_msg_delay_1m  — espaça os control-transfers no EP0 (~1-2 ms).
# PRESERVA mic + fone do DualSense (NÃO desliga áudio). É a ALTERNATIVA que mantém
# os dois áudios — oposto da regra 75 (áudio-off total, opt-in agressivo).
#
# Diferente do install_usb_quirk.sh (que mexe em CMDLINE do kernel, sensível ao
# bootloader), aqui é só um arquivo em /etc/modprobe.d — por isso é DEFAULT no
# install (preserva mic+fone, não é boot-crítico). Ortogonal ao usbcore.quirks=gn.
#
# Idempotente (rodar 2x = no-op). Reversível (--remove). O módulo snd_usb_audio
# carrega tarde (do root real, quando o áudio do controle é detectado) — NÃO está
# no initramfs, então update-initramfs é desnecessário.
#
# Uso:
#   scripts/install_snd_quirk.sh            instala o drop-in (default; requer root)
#   scripts/install_snd_quirk.sh --remove   remove o drop-in (requer root)
#   scripts/install_snd_quirk.sh --status   read-only: ativo/agendado (sem sudo)
#   scripts/install_snd_quirk.sh --check     alias de --status
#   scripts/install_snd_quirk.sh --runtime  escreve no sysfs (best-effort; vale só
#                                            na próxima reenumeração/replug). Requer root.
#
# SPRINT-GAME-RUMBLE-01 / incidente Sackboy 2026-07-14. Pesquisa e descritores em
# docs/process/sprints/2026-07-14-plano-raiz-anti-storm.md.

set -euo pipefail

# Valor do parâmetro (nomes das flags; o kernel resolve o bit em qualquer versão).
readonly QUIRK_VALUE="054c:0ce6:ignore_ctl_error|ctl_msg_delay_1m,054c:0df2:ignore_ctl_error|ctl_msg_delay_1m"
# Marcador estável para idempotência.
readonly MARKER="054c:0ce6:ignore_ctl_error"
readonly CONF="/etc/modprobe.d/hefesto-dualsense-storm.conf"
readonly SYSFS="/sys/module/snd_usb_audio/parameters/quirk_flags"

# Fonte do .conf: ao lado deste script (repo) ou no share do pacote instalado.
_here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ASSET_CONF=""
for cand in \
    "${_here}/../assets/modprobe/hefesto-dualsense-storm.conf" \
    "/usr/share/hefesto-dualsense4unix/modprobe/hefesto-dualsense-storm.conf" \
    "/usr/local/share/hefesto-dualsense4unix/modprobe/hefesto-dualsense-storm.conf"; do
    [[ -f "$cand" ]] && { ASSET_CONF="$cand"; break; }
done

info() { printf '[snd-quirk] %s\n' "$*"; }
warn() { printf '[snd-quirk] aviso: %s\n' "$*" >&2; }
die()  { printf '[snd-quirk] ERRO: %s\n' "$*" >&2; exit 1; }

as_root() {
    if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
        "$@"
    elif command -v sudo >/dev/null 2>&1; then
        sudo "$@"
    else
        die "precisa de root e 'sudo' está ausente — rode como root"
    fi
}

# ---------------------------------------------------------------------------
# APLICAR
# ---------------------------------------------------------------------------
do_apply() {
    if [[ -f "$CONF" ]] && grep -q "$MARKER" "$CONF" 2>/dev/null; then
        info "no-op: cura já presente em ${CONF}"
        return 0
    fi
    [[ -n "$ASSET_CONF" ]] || die "asset não encontrado (assets/modprobe/hefesto-dualsense-storm.conf)"
    info "instalando ${CONF} (cura de raiz do storm — preserva mic+fone)"
    as_root install -D -o root -g root -m 0644 "$ASSET_CONF" "$CONF"
    info "feito — vale no próximo load do snd_usb_audio (replug do controle ou reboot)."
    info "para valer AGORA sem reboot: ${BASH_SOURCE[0]} --runtime  e replugue o controle."
}

# ---------------------------------------------------------------------------
# REMOVER
# ---------------------------------------------------------------------------
do_remove() {
    if [[ ! -f "$CONF" ]]; then
        info "no-op: ${CONF} ausente"
    else
        info "removendo ${CONF}"
        as_root rm -f "$CONF"
    fi
    # Best-effort: limpa o sysfs runtime também (vale no próximo replug).
    if [[ -w "$SYSFS" ]] || [[ "${EUID:-$(id -u)}" -eq 0 ]] || command -v sudo >/dev/null 2>&1; then
        printf '' | as_root tee "$SYSFS" >/dev/null 2>&1 || true
    fi
}

# ---------------------------------------------------------------------------
# STATUS (read-only, sem sudo)
# ---------------------------------------------------------------------------
do_status() {
    info "cura alvo: quirk_flags=${QUIRK_VALUE}"
    # Ativo na sessão atual (sysfs).
    if [[ -r "$SYSFS" ]] && grep -q "$MARKER" "$SYSFS" 2>/dev/null; then
        info "[ativo nesta sessão]        sim — presente em ${SYSFS} (pega no próximo replug)"
    else
        info "[ativo nesta sessão]        não — ${SYSFS} sem a cura"
    fi
    # Agendado (drop-in persistente).
    if [[ -r "$CONF" ]] && grep -q "$MARKER" "$CONF" 2>/dev/null; then
        info "[persistente / próximo boot] sim — em ${CONF}"
    else
        info "[persistente / próximo boot] não — ${CONF} ausente"
    fi
    info "lembrete: PRESERVA mic+fone. É ALTERNATIVA à regra 75 (áudio-off) — use uma OU outra."
}

# ---------------------------------------------------------------------------
# RUNTIME (best-effort; vale na próxima reenumeração/replug)
# ---------------------------------------------------------------------------
do_runtime() {
    [[ -e "$SYSFS" ]] || die "sysfs ausente: ${SYSFS} (snd_usb_audio não carregado?)"
    if [[ -r "$SYSFS" ]] && grep -q "$MARKER" "$SYSFS" 2>/dev/null; then
        info "no-op: cura já presente em ${SYSFS}"
        return 0
    fi
    info "escrevendo a cura em ${SYSFS} (best-effort runtime)"
    if printf '%s' "$QUIRK_VALUE" | as_root tee "$SYSFS" >/dev/null; then
        info "OK — vale na PRÓXIMA reenumeração/replug do controle. Desconecte e reconecte o DualSense."
        info "para persistir entre boots, rode sem --runtime (instala o ${CONF})."
    else
        die "falha ao escrever em ${SYSFS}"
    fi
}

# ---------------------------------------------------------------------------
# Dispatch (mesma guarda de segurança do install_usb_quirk.sh)
# ---------------------------------------------------------------------------
main() {
    local mode="" arg want
    for arg in "$@"; do
        case "$arg" in
            --remove|--delete) want="remove" ;;
            --status|--check)  want="status" ;;
            --runtime)         want="runtime" ;;
            -h|--help)         want="help" ;;
            *) die "argumento desconhecido: ${arg} (use: --remove | --status | --runtime | --help; sem args = aplica)" ;;
        esac
        if [[ -n "$mode" && "$mode" != "$want" ]]; then
            die "modos conflitantes: --${mode} e --${want} (passe só um)"
        fi
        mode="$want"
    done
    mode="${mode:-apply}"

    case "$mode" in
        apply)   do_apply ;;
        remove)  do_remove ;;
        status)  do_status ;;
        runtime) do_runtime ;;
        help)    sed -n '2,40p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//' ;;
    esac
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
