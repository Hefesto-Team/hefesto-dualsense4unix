#!/usr/bin/env bash

set -euo pipefail
_ajuda() {
  cat <<'AJUDA'
install_snd_quirk.sh — cura de RAIZ do storm -71 do DualSense na camada de ÁUDIO.

Uso:
  scripts/install_snd_quirk.sh            instala o drop-in (default; requer root)
  scripts/install_snd_quirk.sh --remove   remove o drop-in (requer root)
  scripts/install_snd_quirk.sh --status   read-only: ativo/agendado (sem sudo)
  scripts/install_snd_quirk.sh --check     alias de --status
  scripts/install_snd_quirk.sh --runtime  escreve no sysfs (best-effort; vale só
                                           na próxima reenumeração/replug). Requer root.
AJUDA
}

readonly QUIRK_VALUE="054c:0ce6:ignore_ctl_error|ctl_msg_delay_1m,054c:0df2:ignore_ctl_error|ctl_msg_delay_1m"
readonly MARKER="054c:0ce6:ignore_ctl_error"
readonly CONF="/etc/modprobe.d/hefesto-dualsense-storm.conf"
readonly SYSFS="/sys/module/snd_usb_audio/parameters/quirk_flags"

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

do_remove() {
    if [[ ! -f "$CONF" ]]; then
        info "no-op: ${CONF} ausente"
    else
        info "removendo ${CONF}"
        as_root rm -f "$CONF"
    fi
    if [[ -w "$SYSFS" ]] || [[ "${EUID:-$(id -u)}" -eq 0 ]] || command -v sudo >/dev/null 2>&1; then
        printf '' | as_root tee "$SYSFS" >/dev/null 2>&1 || true
    fi
}

do_status() {
    info "cura alvo: quirk_flags=${QUIRK_VALUE}"
    if [[ -r "$SYSFS" ]] && grep -q "$MARKER" "$SYSFS" 2>/dev/null; then
        info "[ativo nesta sessão]        sim — presente em ${SYSFS} (pega no próximo replug)"
    else
        info "[ativo nesta sessão]        não — ${SYSFS} sem a cura"
    fi
    if [[ -r "$CONF" ]] && grep -q "$MARKER" "$CONF" 2>/dev/null; then
        info "[persistente / próximo boot] sim — em ${CONF}"
    else
        info "[persistente / próximo boot] não — ${CONF} ausente"
    fi
    info "lembrete: PRESERVA mic+fone. É ALTERNATIVA à regra 75 (áudio-off) — use uma OU outra."
}

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
        help)    _ajuda ;;
    esac
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
