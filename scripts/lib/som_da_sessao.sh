#!/usr/bin/env bash

# shellcheck disable=SC2034
SOM_PAINEL_DO_COSMIC=""
SOM_CURA_DO_PAINEL=""

_som_pids_do_cosmic_settings_daemon() {
    local p argv0
    for p in $(pgrep -u "$(id -u)" -x cosmic-settings 2>/dev/null || true); do
        argv0=""
        IFS= read -r -d '' argv0 2>/dev/null < "/proc/${p}/cmdline" || true
        if [[ "${argv0##*/}" == cosmic-settings-daemon ]]; then
            printf '%s\n' "${p}"
        fi
    done
}

_som_cosmic_settings_daemon_e_cliente() {
    local clientes
    clientes="$(timeout 5 pw-cli ls Client 2>/dev/null)" || return 1
    [[ "${clientes}" == *'application.name = "cosmic-settings-daemon"'* ]]
}

_som_programa_le_o_pipewire() {
    LC_ALL=C grep -qa 'libpipewire-0\.3\.so' "$1" 2>/dev/null
}

_SOM_AMBIENTE=()
_som_ambiente_da_sessao() {
    local p var
    local -a fontes=()
    _SOM_AMBIENTE=()
    for p in $(pgrep -u "$(id -u)" -x cosmic-panel 2>/dev/null || true); do
        fontes+=("${p}")
    done
    [[ -n "${1:-}" ]] && fontes+=("$1")
    for p in "${fontes[@]}"; do
        [[ -r "/proc/${p}/environ" ]] || continue
        while IFS= read -r -d '' var; do
            case "${var%%=*}" in
                WAYLAND_DISPLAY|DISPLAY|XDG_*|DBUS_SESSION_BUS_ADDRESS|COSMIC_*|LANG|HOME|PATH)
                    _SOM_AMBIENTE+=(-E "${var}") ;;
            esac
        done < "/proc/${p}/environ"
        [[ "${#_SOM_AMBIENTE[@]}" -gt 0 ]] && return 0
    done
    return 1
}

_som_devolve_o_painel_do_cosmic() {
    local pids p argv0 programa i vivos
    SOM_PAINEL_DO_COSMIC=""
    SOM_CURA_DO_PAINEL=""
    pgrep -u "$(id -u)" -x cosmic-session >/dev/null 2>&1 || return 0
    pids="$(_som_pids_do_cosmic_settings_daemon)"
    [[ -n "${pids}" ]] || return 0
    argv0=""
    IFS= read -r -d '' argv0 2>/dev/null < "/proc/${pids%%$'\n'*}/cmdline" || true
    if [[ "${argv0}" == /* && -x "${argv0}" ]]; then
        programa="${argv0}"
    else
        programa="$(command -v cosmic-settings-daemon 2>/dev/null || printf '/usr/bin/cosmic-settings-daemon')"
    fi
    _som_programa_le_o_pipewire "${programa}" || return 0
    SOM_CURA_DO_PAINEL="systemd-run --user --collect ${programa}"
    if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
        if declare -F _faria >/dev/null; then
            _faria "religar o cosmic-settings-daemon ao som (PID $(tr '\n' ' ' <<<"${pids}")pelo ${SOM_CURA_DO_PAINEL})"
        fi
        return 0
    fi
    _som_ambiente_da_sessao "${pids%%$'\n'*}" || true
    for p in ${pids}; do
        argv0=""
        IFS= read -r -d '' argv0 2>/dev/null < "/proc/${p}/cmdline" || true
        if [[ "${argv0##*/}" == cosmic-settings-daemon ]]; then
            kill -TERM "${p}" 2>/dev/null || true
        fi
    done
    for (( i = 0; i < 30; i++ )); do
        vivos=0
        for p in ${pids}; do
            if kill -0 "${p}" 2>/dev/null; then vivos=1; fi
        done
        [[ "${vivos}" -eq 0 ]] && break
        sleep 0.1
    done
    if [[ "${vivos}" -eq 1 ]]; then
        SOM_PAINEL_DO_COSMIC="nao-voltou"
        SOM_CURA_DO_PAINEL="kill $(tr '\n' ' ' <<<"${pids}")&& ${SOM_CURA_DO_PAINEL}"
        return 0
    fi
    sleep 1
    if [[ -z "$(_som_pids_do_cosmic_settings_daemon)" ]]; then
        systemd-run --user --collect --quiet \
            --unit="hefesto-cosmic-settings-daemon-$(date +%s)" \
            --description="cosmic-settings-daemon, religado ao som pelo Hefesto" \
            "${_SOM_AMBIENTE[@]}" "${programa}" >/dev/null 2>&1 || true
    fi
    for (( i = 0; i < 20; i++ )); do
        if _som_cosmic_settings_daemon_e_cliente; then
            SOM_PAINEL_DO_COSMIC="voltou"
            return 0
        fi
        sleep 0.5
    done
    SOM_PAINEL_DO_COSMIC="nao-voltou"
    pids="$(_som_pids_do_cosmic_settings_daemon)"
    if [[ -n "${pids}" ]]; then
        SOM_CURA_DO_PAINEL="kill $(tr '\n' ' ' <<<"${pids}")&& ${SOM_CURA_DO_PAINEL}"
    fi
    return 0
}

reiniciar_o_som_da_sessao() {
    SOM_PAINEL_DO_COSMIC=""
    SOM_CURA_DO_PAINEL=""
    systemctl --user restart pipewire pipewire-pulse wireplumber >/dev/null 2>&1 || return 1
    _som_devolve_o_painel_do_cosmic
    return 0
}
