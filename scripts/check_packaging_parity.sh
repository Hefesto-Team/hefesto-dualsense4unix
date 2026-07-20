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
#   4) alguma regra udev de assets/ não estiver coberta pelos instaladores
#      (install_udev.sh, install-host-udev.sh, build_deb.sh) e pelo uninstall.sh
#      — regra nova não pode sumir de um instalador sem ninguém notar.
#   5) BROKER-01 (Onda S): o broker root hide-hidraw (fd-injection) não estiver
#      referenciado em TODAS as formas de empacotamento (build_deb.sh,
#      PKGBUILD, spec, flatpak, install-host-udev.sh) E no uninstall.sh —
#      purge/remoção não pode deixar a unit ROOT órfã habilitada (achado #21).
#
# Rodável local e em CI. CHORE-PACKAGING-PARITY-ALL-FORMS-01.

set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

rc=0

# Diretórios de BUILD dentro de packaging/ (target/ do Rust chega a dezenas
# de GB): fora de todo grep recursivo — senão o check leva minutos e trava a
# suíte que o executa por subprocess (test_check_packaging_parity.py).
GREP_EXCLUDES=(--exclude-dir=target --exclude-dir=.flatpak-builder --exclude-dir=build)

echo "== nome de unit do hotplug (assets/packaging/flatpak) =="
if grep -rn "${GREP_EXCLUDES[@]}" 'hefesto-gui-hotplug' assets/ packaging/ flatpak/ 2>/dev/null \
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
done < <(grep -rl "${GREP_EXCLUDES[@]}" 'X-CosmicApplet' --include='*.desktop' packaging/ 2>/dev/null)

echo "== X-HostWaylandDisplay nos .desktop de applet COSMIC (packaging/) =="
while IFS= read -r desk; do
    grep -q '^X-CosmicApplet=true' "${desk}" 2>/dev/null || continue
    if grep -q '^X-HostWaylandDisplay=true' "${desk}" 2>/dev/null; then
        echo "[ OK ] $(basename "${desk}"): X-HostWaylandDisplay=true"
    else
        echo "[FAIL] $(basename "${desk}"): falta X-HostWaylandDisplay=true"
        rc=1
    fi
done < <(grep -rl "${GREP_EXCLUDES[@]}" 'X-CosmicApplet' --include='*.desktop' packaging/ 2>/dev/null)

# FIX-PACKAGING-SEED-PARITY-01: paridade das regras udev entre assets/ e os
# instaladores. A 78 (motion-not-joystick) nasceu só no caminho nativo — sem
# esta guarda, a próxima regra some de um instalador sem ninguém notar.
#
# Exceções conscientes (dispensadas da cobertura de INSTALAÇÃO; o uninstall.sh
# continua obrigatório para todas, pois precisa limpar instalações antigas):
#   73/74: hotplug-GUI descontinuadas (alimentavam o storm -71) — só remoção.
#   75:    disable-usb-audio é opt-in (install_udev.sh --disable-usb-audio).
INSTALL_OPTIONAL_RULES=(
    "73-ps5-controller-hotplug.rules"
    "74-ps5-controller-hotplug-bt.rules"
    "75-ps5-controller-disable-usb-audio.rules"
)

is_install_optional_rule() {
    local name="$1" opt
    for opt in "${INSTALL_OPTIONAL_RULES[@]}"; do
        [[ "${name}" == "${opt}" ]] && return 0
    done
    return 1
}

echo "== paridade das regras udev (assets/ × instaladores) =="
for rules_path in assets/[0-9][0-9]-*.rules; do
    [[ -f "${rules_path}" ]] || continue
    rules_name="$(basename "${rules_path}")"
    rules_prefix="${rules_name%%-*}"
    missing=()

    # uninstall.sh remove TODA regra pelo nome (inclusive descontinuada/opt-in).
    grep -qF "${rules_name}" uninstall.sh 2>/dev/null \
        || missing+=("uninstall.sh")

    if ! is_install_optional_rule "${rules_name}"; then
        grep -qF "${rules_name}" scripts/install_udev.sh 2>/dev/null \
            || missing+=("scripts/install_udev.sh")
        grep -qF "${rules_name}" scripts/install-host-udev.sh 2>/dev/null \
            || missing+=("scripts/install-host-udev.sh")
        # build_deb.sh cobre por glob (assets/NN-*.rules) ou por nome literal.
        if ! grep -qF "assets/${rules_prefix}-*.rules" scripts/build_deb.sh 2>/dev/null \
           && ! grep -qF "${rules_name}" scripts/build_deb.sh 2>/dev/null; then
            missing+=("scripts/build_deb.sh")
        fi
        # FIX-FLATPAK-UDEV-PARITY-01: o manifesto Flatpak precisa bundlar TODA
        # regra obrigatória — o install-host-udev.sh (que vai no bundle) tem
        # pre-flight que ABORTA se qualquer uma faltar em /app/share.
        if ! grep -qF "${rules_name}" flatpak/*.yml 2>/dev/null; then
            missing+=("flatpak/*.yml")
        fi
    fi

    if [[ "${#missing[@]}" -eq 0 ]]; then
        echo "[ OK ] ${rules_name}: coberta em todos os instaladores"
    else
        echo "[FAIL] ${rules_name}: FALTANDO em: ${missing[*]}"
        echo "       adicione a regra ao(s) instalador(es) furado(s) acima — ou,"
        echo "       se ela for opt-in/descontinuada de propósito, à lista"
        echo "       INSTALL_OPTIONAL_RULES deste script (com justificativa)."
        rc=1
    fi
done

# M11 (auditoria): a cura de RAIZ do storm (assets/modprobe/*.conf) precisa ser
# empacotada por TODOS os caminhos, senão o install-host-udev.sh pula a cura em
# silêncio (SNDQUIRK_SRC=""). O glob de regras acima só pega *.rules — este bloco
# cobre o .conf. Antes ausente: removê-lo do build_deb/flatpak passava despercebido.
# Onda PLATAFORMA 2026-07-18: assets/modprobe.d/ (novo, distinto do legado
# assets/modprobe/) entra no MESMO contrato de paridade — o btusb-no-autosuspend
# não pode sumir de um instalador sem ninguém notar.
echo "== paridade da cura de raiz (assets/modprobe{,.d}/*.conf × instaladores) =="
for conf_path in assets/modprobe/*.conf assets/modprobe.d/*.conf; do
    [[ -f "${conf_path}" ]] || continue
    conf_name="$(basename "${conf_path}")"
    missing=()
    grep -qF "${conf_name}" scripts/build_deb.sh 2>/dev/null \
        || missing+=("scripts/build_deb.sh")
    grep -qF "${conf_name}" flatpak/*.yml 2>/dev/null \
        || missing+=("flatpak/*.yml")
    grep -qF "${conf_name}" scripts/install-host-udev.sh 2>/dev/null \
        || missing+=("scripts/install-host-udev.sh")
    grep -qF "${conf_name}" packaging/arch/PKGBUILD 2>/dev/null \
        || missing+=("packaging/arch/PKGBUILD")
    grep -qF "${conf_name}" uninstall.sh 2>/dev/null \
        || missing+=("uninstall.sh")
    if [[ "${#missing[@]}" -eq 0 ]]; then
        echo "[ OK ] ${conf_name}: coberta em todos os instaladores"
    else
        echo "[FAIL] ${conf_name}: FALTANDO em: ${missing[*]}"
        rc=1
    fi
done

# BROKER-01 (Onda S — fd-injection, achado #21 da auditoria): purge/remoção
# não pode deixar a unit ROOT do broker órfã habilitada em NENHUMA forma de
# empacotamento. Gate: só cobra paridade SE o repo realmente tem o broker
# (asset canônico presente) — um checkout sem a onda S (ex.: fixture mínima
# de outros testes) fica silencioso, igual ao bloco de modprobe acima.
echo "== paridade do broker hide-hidraw (hefesto-hidraw-broker) =="
if [[ -f assets/systemd/hefesto-hidraw-broker.service ]]; then
    missing=()
    grep -qF "hefesto-hidraw-broker" scripts/build_deb.sh 2>/dev/null \
        || missing+=("scripts/build_deb.sh")
    grep -qF "hefesto-hidraw-broker" packaging/arch/PKGBUILD 2>/dev/null \
        || missing+=("packaging/arch/PKGBUILD")
    grep -qF "hefesto-hidraw-broker" packaging/fedora/hefesto-dualsense4unix.spec 2>/dev/null \
        || missing+=("packaging/fedora/hefesto-dualsense4unix.spec")
    grep -qF "hefesto-hidraw-broker" flatpak/*.yml 2>/dev/null \
        || missing+=("flatpak/*.yml")
    grep -qF "hefesto-hidraw-broker" scripts/install-host-udev.sh 2>/dev/null \
        || missing+=("scripts/install-host-udev.sh")
    # Achados Onda S #2/#8: o caminho Debian tem DOIS lados — o build
    # (build_deb.sh EMPACOTA o broker; o grep acima cobre) e a REMOÇÃO
    # (prerm/postrm, que o dpkg executa no apt remove/purge). Só o grep do
    # build dava falso-verde: um purge sem broker nos maintainer scripts
    # deixava a unit ROOT órfã habilitada. prerm E postrm precisam do
    # caminho de remoção (disable + restore-all + rm das units).
    grep -qF "hefesto-hidraw-broker" packaging/debian/prerm 2>/dev/null \
        || missing+=("packaging/debian/prerm")
    grep -qF "hefesto-hidraw-broker" packaging/debian/postrm 2>/dev/null \
        || missing+=("packaging/debian/postrm")
    # uninstall.sh é obrigatório em TODO checkout (o caminho nativo sempre
    # precisa poder desfazer) — não é gateado pela existência do asset acima
    # de propósito redundante: se o asset sumiu mas o texto ficou, ok; se o
    # texto sumiu, falha aqui igual aos demais.
    grep -qF "hefesto-hidraw-broker" uninstall.sh 2>/dev/null \
        || missing+=("uninstall.sh")
    if [[ "${#missing[@]}" -eq 0 ]]; then
        echo "[ OK ] hefesto-hidraw-broker: coberto em todas as formas + remoção (uninstall.sh)"
    else
        echo "[FAIL] hefesto-hidraw-broker: FALTANDO em: ${missing[*]}"
        echo "       purge/remoção pode deixar a unit ROOT órfã habilitada — cubra o binário"
        echo "       + as units-template + o caminho de remoção no(s) instalador(es) furado(s)."
        rc=1
    fi
else
    echo "[ OK ] hefesto-hidraw-broker: assets/systemd/hefesto-hidraw-broker.service ausente — nada a checar"
fi

echo "─────────────────────────────────────────"
if [[ "${rc}" -eq 0 ]]; then
    echo "paridade de empacotamento OK"
else
    echo "paridade de empacotamento FALHOU"
fi
exit "${rc}"
