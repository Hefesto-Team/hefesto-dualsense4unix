#!/usr/bin/env bash
# reproduzir.sh — o `wpctl` pendurado pelo metadata, num PipeWire privado.
#
# A receita de docs/protocol/o-wpctl-pendurado-pelo-metadata.md, em script: um
# servidor com XDG_RUNTIME_DIR próprio, o WirePlumber só com o metadata
# sm-settings, e então, a cada rodada, o WirePlumber congelado (SIGSTOP) recebe
# os binds de N `wpctl settings` e morre (SIGKILL) sem responder ao ping. Com o
# metadata.c sem a cura (até a 1.6.8), todo `wpctl` daquela janela fica preso.
#
# NÃO TOCA O SOM DA SESSÃO: o runtime, a configuração e o estado são de um
# diretório temporário, o D-Bus aponta para um socket que não existe, e nem o
# servidor nem o WirePlumber da prova carregam ALSA, Bluetooth ou câmera. Os
# processos que ele mata são só os que ele mesmo lançou, pelo PID.
#
# Uso:
#   reproduzir.sh PREFIXO_DO_PIPEWIRE [RODADAS] [POR_RODADA]
#       PREFIXO_DO_PIPEWIRE tem bin/pipewire e lib/<multiarch>/ (um `meson
#       install` num diretório, ou um .deb desempacotado com `dpkg-deb -x`, cujo
#       prefixo é <dir>/usr). O WirePlumber e o wpctl vêm do PATH.
#
# Imprime `lancados=N pendurados=M`. Sai 0 com M=0, 1 com M>0, 2 no uso e 3 se
# a prova não subiu.
set -euo pipefail

prefixo="${1:-}"
rodadas="${2:-5}"
por_rodada="${3:-4}"
[[ -x "${prefixo}/bin/pipewire" ]] || { echo "uso: $0 PREFIXO_DO_PIPEWIRE [RODADAS] [POR_RODADA]" >&2; exit 2; }
if ! command -v wireplumber >/dev/null || ! command -v wpctl >/dev/null; then
    echo "faltam o wireplumber e o wpctl no PATH" >&2
    exit 2
fi

multiarch="$(gcc -dumpmachine 2>/dev/null || echo x86_64-linux-gnu)"
base="$(mktemp -d "${TMPDIR:-/tmp}/hefesto-metadata.XXXXXX")"
mkdir -p "${base}/run" "${base}/pipewire" "${base}/wireplumber/wireplumber.conf.d"
chmod 700 "${base}/run"
cat > "${base}/pipewire/pipewire.conf" <<'CONF'
# O servidor da prova: só o que o bind no metadata precisa, sem ALSA, sem
# Bluetooth, sem D-Bus. Nenhum aparelho da máquina é aberto.
context.properties = {
    core.daemon = true
    core.name   = pipewire-0
    support.dbus = false
}
context.spa-libs = {
    support.* = support/libspa-support
}
context.modules = [
    { name = libpipewire-module-protocol-native }
    { name = libpipewire-module-metadata }
    { name = libpipewire-module-client-node }
    { name = libpipewire-module-adapter }
    { name = libpipewire-module-access }
    { name = libpipewire-module-session-manager }
]
CONF
for conf in "${prefixo}/share/pipewire/client.conf" /usr/share/pipewire/client.conf; do
    [[ -r "${conf}" ]] && { cp "${conf}" "${base}/pipewire/client.conf"; break; }
done
wp_conf="$(dirname "$(command -v wireplumber)")/../share/wireplumber/wireplumber.conf"
[[ -r "${wp_conf}" ]] || wp_conf=/usr/share/wireplumber/wireplumber.conf
cp "${wp_conf}" "${base}/wireplumber/wireplumber.conf"
cat > "${base}/wireplumber/wireplumber.conf.d/90-prova.conf" <<'CONF'
# O perfil da prova: o WirePlumber só exporta o metadata sm-settings (o que o
# `wpctl settings` da Steam lê). Nenhum monitor de ALSA, Bluetooth ou câmera.
wireplumber.profiles = {
  prova = {
    metadata.sm-settings = required
    support.settings = required
  }
}
CONF

export XDG_RUNTIME_DIR="${base}/run" PIPEWIRE_RUNTIME_DIR="${base}/run"
export XDG_CONFIG_HOME="${base}/config" XDG_STATE_HOME="${base}/state" XDG_DATA_HOME="${base}/data"
export PIPEWIRE_CONFIG_DIR="${base}/pipewire" WIREPLUMBER_CONFIG_DIR="${base}/wireplumber"
export DBUS_SESSION_BUS_ADDRESS="unix:path=${base}/sem-dbus" PULSE_SERVER=none
unset PIPEWIRE_REMOTE DISPLAY WAYLAND_DISPLAY

PW="" WP="" pids=()
limpar() {
    local p
    # Só o PID que ainda é um dos três que a prova lançou: um PID que já saiu
    # pode ter sido reusado por outro processo da sessão.
    for p in "${pids[@]}" "${WP}" "${PW}"; do
        [[ -n "${p}" ]] || continue
        case "$(cat "/proc/${p}/comm" 2>/dev/null)" in
            wpctl | wireplumber | pipewire) kill -KILL "${p}" 2>/dev/null || true ;;
        esac
    done
    { wait; } 2>/dev/null || true
    rm -rf "${base}"
}
trap limpar EXIT

LD_LIBRARY_PATH="${prefixo}/lib/${multiarch}${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}" \
    "${prefixo}/bin/pipewire" > "${base}/pipewire.log" 2>&1 &
PW=$!
for _ in $(seq 50); do [[ -S "${base}/run/pipewire-0" ]] && break; sleep 0.1; done
[[ -S "${base}/run/pipewire-0" ]] || { tail -n 5 "${base}/pipewire.log" >&2; exit 3; }

subir_o_wireplumber() {
    wireplumber -p prova >> "${base}/wireplumber.log" 2>&1 &
    WP=$!
    for _ in $(seq 50); do
        timeout 1 wpctl settings monitor.alsa.enable-external-volume-control >/dev/null 2>&1 && return 0
        sleep 0.1
    done
    return 1
}
subir_o_wireplumber || { tail -n 5 "${base}/wireplumber.log" >&2; exit 3; }

for _ in $(seq "${rodadas}"); do
    kill -STOP "${WP}"
    for _ in $(seq "${por_rodada}"); do
        wpctl settings monitor.alsa.enable-external-volume-control >/dev/null 2>&1 &
        pids+=($!)
    done
    sleep 1
    kill -KILL "${WP}"
    wait "${WP}" 2>/dev/null || true
    subir_o_wireplumber || { tail -n 5 "${base}/wireplumber.log" >&2; exit 3; }
done
# Um `wpctl` são responde em milissegundos; o preso fica em poll para sempre.
sleep 10
pendurados=0
for p in "${pids[@]}"; do
    kill -0 "${p}" 2>/dev/null && pendurados=$((pendurados + 1))
done
echo "lancados=${#pids[@]} pendurados=${pendurados}"
[[ "${pendurados}" -eq 0 ]]
