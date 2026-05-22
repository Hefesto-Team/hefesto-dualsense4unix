#!/usr/bin/env bash
# check_packaging_parity.sh — guarda anti-regressão de paridade entre as formas
# de empacotamento (nativo, .deb, Arch, flatpak, AppImage, applet COSMIC).
#
# Falha (exit 1) se:
#   1) o nome de unit ERRADO do hotplug (hefesto-gui-hotplug.service) reaparecer
#      em assets/, packaging/ ou flatpak/ — a unit real é
#      hefesto-dualsense4unix-gui-hotplug.service. (scripts/ é ignorado de
#      propósito: doctor.sh cita o nome errado para DETECTÁ-lo.)
#   2) algum .desktop de applet COSMIC tiver Icon= sem o arquivo de ícone
#      correspondente versionado ao lado (mismatch de sufixo -symbolic).
#   3) algum .desktop de applet COSMIC não tiver X-HostWaylandDisplay=true
#      (sem ele o applet roda isolado e não enxerga o sistema no painel COSMIC).
#
# Rodável local e em CI. CHORE-PACKAGING-PARITY-ALL-FORMS-01.

set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

rc=0

echo "== nome de unit do hotplug (assets/packaging/flatpak) =="
if grep -rn 'hefesto-gui-hotplug' assets/ packaging/ flatpak/ 2>/dev/null \
        | grep -v 'hefesto-dualsense4unix-gui-hotplug'; then
    echo "[FAIL] nome de unit ERRADO 'hefesto-gui-hotplug.service' acima"
    echo "       use 'hefesto-dualsense4unix-gui-hotplug.service'"
    rc=1
else
    echo "[ OK ] nenhuma referência ao nome de unit errado"
fi

echo "== Icon dos .desktop de applet COSMIC (packaging/) =="
while IFS= read -r desk; do
    grep -q '^X-CosmicApplet=true' "${desk}" 2>/dev/null || continue
    icon="$(sed -n 's/^Icon=//p' "${desk}" | head -1)"
    if [[ -z "${icon}" ]]; then
        echo "[WARN] ${desk}: sem linha Icon="
        continue
    fi
    dir="$(dirname "${desk}")"
    if find "${dir}" -path "*apps/${icon}.*" 2>/dev/null | grep -q .; then
        echo "[ OK ] $(basename "${desk}"): Icon=${icon} tem arquivo versionado"
    else
        echo "[FAIL] $(basename "${desk}"): Icon=${icon} sem arquivo de ícone em ${dir}"
        rc=1
    fi
done < <(grep -rl 'X-CosmicApplet' --include='*.desktop' packaging/ 2>/dev/null)

echo "== X-HostWaylandDisplay nos .desktop de applet COSMIC (packaging/) =="
while IFS= read -r desk; do
    grep -q '^X-CosmicApplet=true' "${desk}" 2>/dev/null || continue
    if grep -q '^X-HostWaylandDisplay=true' "${desk}" 2>/dev/null; then
        echo "[ OK ] $(basename "${desk}"): X-HostWaylandDisplay=true"
    else
        echo "[FAIL] $(basename "${desk}"): falta X-HostWaylandDisplay=true"
        rc=1
    fi
done < <(grep -rl 'X-CosmicApplet' --include='*.desktop' packaging/ 2>/dev/null)

echo "─────────────────────────────────────────"
if [[ "${rc}" -eq 0 ]]; then
    echo "paridade de empacotamento OK"
else
    echo "paridade de empacotamento FALHOU"
fi
exit "${rc}"
