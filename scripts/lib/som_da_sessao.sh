#!/usr/bin/env bash
# som_da_sessao.sh — o reinício do som da sessão, num ponto só.
#
# O-SOM-REINICIADO-NAO-CEGA-O-PAINEL-DO-COSMIC-01 (15/10/2026). Sourceado pelo
# `install.sh` (passo 3f-bis, ao instalar o PipeWire da casa) e pelo
# `uninstall.sh` (ao devolver o PipeWire de antes): os dois reiniciam o som por
# `reiniciar_o_som_da_sessao`, e só por ela.
#
# O QUE SE MEDIU: no COSMIC 1.10, quem lê o PipeWire é o `cosmic-settings-daemon`;
# o applet de som do painel e o OSD do volume falam com ele, nunca com o
# PipeWire. Depois do `systemctl --user restart pipewire pipewire-pulse
# wireplumber` das 04h20, ele seguiu vivo e FORA do `pw-cli ls Client` por dez
# horas, e o applet dizia «Nenhum dispositivo selecionado» com o som tocando.
# O `cosmic-session` não o ressuscita. Subi-lo de novo pelo `systemd-run --user`,
# com o ambiente da sessão, o devolveu ao PipeWire em 4 s.
#
# O reinício só do `wireplumber` (os do `uninstall.sh` que tiram um drop-in) não
# passa por aqui: o `wireplumber.service` tem `BindsTo=pipewire.service`, que
# propaga a parada do PipeWire para o WirePlumber e nunca o contrário. Medido no
# diário: nove reinícios só do WirePlumber entre 12 e 14/10, e o servidor do
# PipeWire com o mesmo processo de 12/10 10h31 até as 04h20 de 15/10.
#
# Fora do COSMIC nada muda: sem `cosmic-session` da pessoa, ou sem um
# `cosmic-settings-daemon` dela no ar, o reinício é só o `systemctl`.
#
# O QUE SAI DAQUI, para quem chama dizer na língua dele:
#   rc 1                     — o `systemctl` não reiniciou o som;
#   SOM_PAINEL_DO_COSMIC     — "" (fora do COSMIC), "voltou" ou "nao-voltou";
#   SOM_CURA_DO_PAINEL       — o comando que a pessoa roda quando não voltou.

# shellcheck disable=SC2034  # as duas saídas são lidas por quem sourceia
SOM_PAINEL_DO_COSMIC=""
SOM_CURA_DO_PAINEL=""

#: Os PIDs dos `cosmic-settings-daemon` de quem roda. O `pgrep -x` compara com o
#: `comm`, que o kernel corta em 15 caracteres: `cosmic-settings` casa o daemon
#: E a janela das Configurações. Quem separa é o argv0 da cmdline. O `pgrep -f`
#: casaria o próprio shell que tem o nome na linha de comando.
_som_pids_do_cosmic_settings_daemon() {
    local p argv0
    for p in $(pgrep -u "$(id -u)" -x cosmic-settings 2>/dev/null || true); do
        argv0=""
        IFS= read -r -d '' argv0 < "/proc/${p}/cmdline" 2>/dev/null || true
        if [[ "${argv0##*/}" == cosmic-settings-daemon ]]; then
            printf '%s\n' "${p}"
        fi
    done
}

#: O `cosmic-settings-daemon` está entre os clientes do PipeWire? Só lê.
#: Para uma variável, e não `| grep -q`: sob `pipefail` o cano devolve 141 quando ACHA.
_som_cosmic_settings_daemon_e_cliente() {
    local clientes
    clientes="$(timeout 5 pw-cli ls Client 2>/dev/null)" || return 1
    [[ "${clientes}" == *'application.name = "cosmic-settings-daemon"'* ]]
}

#: O ambiente da sessão gráfica, lido do `cosmic-panel` vivo (o mesmo que o
#: `cosmic-session` deu ao daemon), em `-E NOME=valor` para o `systemd-run`.
#: Sem painel, vale o do próprio daemon que vai sair (`$1`).
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

#: Religa o `cosmic-settings-daemon` ao PipeWire recém-reiniciado.
_som_devolve_o_painel_do_cosmic() {
    local pids p argv0 programa i vivos
    SOM_PAINEL_DO_COSMIC=""
    SOM_CURA_DO_PAINEL=""
    pgrep -u "$(id -u)" -x cosmic-session >/dev/null 2>&1 || return 0
    pids="$(_som_pids_do_cosmic_settings_daemon)"
    [[ -n "${pids}" ]] || return 0
    argv0=""
    IFS= read -r -d '' argv0 < "/proc/${pids%%$'\n'*}/cmdline" 2>/dev/null || true
    if [[ "${argv0}" == /* && -x "${argv0}" ]]; then
        programa="${argv0}"
    else
        programa="$(command -v cosmic-settings-daemon 2>/dev/null || printf '/usr/bin/cosmic-settings-daemon')"
    fi
    SOM_CURA_DO_PAINEL="systemd-run --user --collect ${programa}"
    if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
        if declare -F _faria >/dev/null; then
            _faria "religar o cosmic-settings-daemon ao som (PID $(tr '\n' ' ' <<<"${pids}")pelo ${SOM_CURA_DO_PAINEL})"
        fi
        return 0
    fi
    _som_ambiente_da_sessao "${pids%%$'\n'*}" || true
    # Morto pelo PID, e o PID conferido de novo na hora: se ele saiu e o número
    # voltou para outro processo, ninguém morre por engano.
    for p in ${pids}; do
        argv0=""
        IFS= read -r -d '' argv0 < "/proc/${p}/cmdline" 2>/dev/null || true
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
    # Se a sessão o ressuscitar sozinha (outra versão do COSMIC), não sobe um segundo.
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

#: O reinício do som da sessão (pipewire, pipewire-pulse e wireplumber) e, no
#: COSMIC, a volta do painel ao som. rc 1 só quando o `systemctl` falha.
reiniciar_o_som_da_sessao() {
    SOM_PAINEL_DO_COSMIC=""
    SOM_CURA_DO_PAINEL=""
    systemctl --user restart pipewire pipewire-pulse wireplumber >/dev/null 2>&1 || return 1
    _som_devolve_o_painel_do_cosmic
    return 0
}
