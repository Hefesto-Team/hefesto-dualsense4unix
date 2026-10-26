#!/usr/bin/env bash

set -uo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

rc=0

GREP_EXCLUDES=(--exclude-dir=target --exclude-dir=.flatpak-builder --exclude-dir=build)

_pkg_scripts_copiados_de() {
    local _arq="$1" _codigo _copias _var _lista
    [[ -f "${_arq}" ]] || return 0
    _codigo="$(sed -e :a -e '/\\$/N; s/\\\n[[:space:]]*/ /; ta' "${_arq}" 2>/dev/null \
        | grep -vE '^[[:space:]]*#' || true)"
    _copias="$(grep -E '(install[[:space:]]+-D|(^|[[:space:]])cp([[:space:]]|$))' <<<"${_codigo}" || true)"
    grep -oE 'scripts/[A-Za-z0-9_.-]+\.(sh|py)' <<<"${_copias}" | sed 's|^scripts/||' || true
    while IFS= read -r _var; do
        [[ -n "${_var}" ]] || continue
        grep -qE "scripts/\\\$\\{?${_var}\\}?" <<<"${_copias}" || continue
        _lista="$(grep -oE "for[[:space:]]+${_var}[[:space:]]+in[[:space:]][^;]*" <<<"${_codigo}" \
            | sed -E "s/^for[[:space:]]+${_var}[[:space:]]+in[[:space:]]//" || true)"
        tr ' \t' '\n\n' <<<"${_lista}"
    done < <(grep -oE 'for[[:space:]]+[A-Za-z_][A-Za-z0-9_]*[[:space:]]+in' <<<"${_codigo}" 2>/dev/null \
        | awk '{print $2}' | sort -u)
}

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
    _icone_achado="$(find "${dir}" -path "*apps/${icon}.*" 2>/dev/null || true)"
    if grep -q . <<< "${_icone_achado}"; then
        echo "[ OK ] $(basename "${desk}"): Icon=${icon} tem arquivo versionado"
    else
        echo "[FAIL] $(basename "${desk}"): Icon=${icon} sem arquivo de ícone em ${dir}"
        rc=1
    fi
done < <(grep -rl "${GREP_EXCLUDES[@]}" 'X-CosmicApplet' --include='*.desktop' packaging/ 2>/dev/null)

echo "== Icon dos .desktop de aplicativo (packaging/) × nome instalado =="
ICON_INSTALLERS=(
    scripts/build_deb.sh
    packaging/arch/PKGBUILD
    packaging/fedora/hefesto-dualsense4unix.spec
    packaging/nix/package.nix
)
while IFS= read -r desk; do
    grep -q '^X-CosmicApplet=true' "${desk}" 2>/dev/null && continue
    if grep -q '^X-HefestoNaoEmpacotado=true' "${desk}" 2>/dev/null; then
        echo "[ -- ] ${desk}: fora dos empacotamentos por declaração própria"
        continue
    fi
    icon="$(sed -n 's/^Icon=//p' "${desk}" | head -1)"
    if [[ -z "${icon}" ]]; then
        echo "[WARN] ${desk}: sem linha Icon="
        continue
    fi
    missing=()
    for inst in "${ICON_INSTALLERS[@]}"; do
        [[ -f "${inst}" ]] || continue
        grep -qF "apps/${icon}.png" "${inst}" 2>/dev/null || missing+=("${inst}")
    done
    if [[ "${#missing[@]}" -eq 0 ]]; then
        echo "[ OK ] $(basename "${desk}"): Icon=${icon} casa o PNG de todos os formatos"
    else
        echo "[FAIL] $(basename "${desk}"): Icon=${icon} sem apps/${icon}.png em: ${missing[*]}"
        echo "       o lançador fica SEM ÍCONE nesses formatos — alinhe o nome do"
        echo "       arquivo instalado (ou o Icon= do .desktop compartilhado)."
        rc=1
    fi
done < <(find packaging -name '*.desktop' \
    -not -path '*/target/*' -not -path '*/.flatpak-builder/*' \
    -not -path '*/flatpak-repo/*' 2>/dev/null)

echo "== Icon pedido pelo CÓDIGO (janela + bandeja) × nome instalado =="
echo "       (o nome vem de utils/identidade.py:HEFESTO — ver o comentário aqui)"
if [[ ! -d src/hefesto_dualsense4unix ]]; then
    echo "[ OK ] ícone pedido pelo código: sem src/ neste checkout — nada a checar"
else
    IDENTIDADE_PY=src/hefesto_dualsense4unix/utils/identidade.py
    code_icons=()
    if [[ -f "${IDENTIDADE_PY}" ]]; then
        icone_do_app="$(awk '/^HEFESTO = Identidade\(/,/^\)/' "${IDENTIDADE_PY}" \
            | sed -n 's/^[[:space:]]*icone="\([^"]*\)".*/\1/p' | head -1)"
        if [[ -n "${icone_do_app}" ]]; then
            code_icons+=("${icone_do_app}")
            if grep -q 'TRAY_ICON_NAME[[:space:]]*=.*-symbolic' \
                src/hefesto_dualsense4unix/app/tray.py 2>/dev/null; then
                code_icons+=("${icone_do_app}-symbolic")
            else
                echo "[FAIL] app/tray.py não constrói mais um nome terminado em -symbolic"
                echo "       APPLET-MONOCROMÁTICO-01: sem o sufixo, o painel não recolore"
                echo "       e o ícone dela volta a ser o único cromático da barra."
                rc=1
            fi
        fi
    fi
    LANCADOR_PY=src/hefesto_dualsense4unix/interface/abrir.py
    if [[ ! -f "${LANCADOR_PY}" ]]; then
        echo "[FAIL] ${LANCADOR_PY} sumiu — ninguém veste o ícone no processo"
        echo "       e a janela dela nasce com o ícone genérico do sistema."
        rc=1
    elif ! grep -q 'set_default_icon_name(' "${LANCADOR_PY}" \
         || ! grep -q '\.icone' "${LANCADOR_PY}"; then
        echo "[FAIL] ${LANCADOR_PY} não pede mais o ícone por identidade.icone"
        echo "       o nome do ícone voltou a estar cravado, e um literal que"
        echo "       diverge do resto do produto some do menu sem avisar."
        rc=1
    elif grep -qE 'set_default_icon_name\(["'"'"']' "${LANCADOR_PY}"; then
        echo "[FAIL] ${LANCADOR_PY} passa um LITERAL a set_default_icon_name"
        echo "       o nome tem de vir de utils/identidade.py, que é o dono."
        rc=1
    fi
    if [[ "${#code_icons[@]}" -eq 0 ]]; then
        echo "[FAIL] não achei nome de ícone em ${IDENTIDADE_PY} (bloco HEFESTO)"
        echo "       sem isso a JANELA e a BANDEJA caem no ícone genérico e"
        echo "       ninguém é avisado — por isso é FAIL, e não mais WARN."
        rc=1
    else
        while IFS= read -r icon; do
            [[ -n "${icon}" ]] || continue
            if [[ "${icon}" == *-symbolic ]]; then
                esperado="symbolic/apps/${icon}.svg"
            else
                esperado="apps/${icon}.png"
            fi
            missing=()
            for inst in "${ICON_INSTALLERS[@]}"; do
                [[ -f "${inst}" ]] || continue
                grep -qF "${esperado}" "${inst}" 2>/dev/null || missing+=("${inst}")
            done
            if [[ "${#missing[@]}" -eq 0 ]]; then
                echo "[ OK ] código pede ${icon} e todos os formatos instalam ${esperado}"
            else
                echo "[FAIL] código pede ${icon} e falta ${esperado} em: ${missing[*]}"
                echo "       a JANELA e a BANDEJA caem no fallback genérico nesses formatos."
                echo "       Instale os DOIS nomes (o do .desktop e o do código)."
                rc=1
            fi
        done < <(printf '%s\n' "${code_icons[@]}" | sort -u)
    fi
fi

echo "== simbólico da bandeja × simbólico do applet (mesmo desenho) =="
SIMB_CANONICO="assets/simbolico/hefesto-dualsense4unix-symbolic.svg"
SIMB_APPLET="packaging/cosmic-applet/data/icons/hicolor/symbolic/apps/com.vitoriamaria.HefestoDualsense4Unix-symbolic.svg"
if [[ ! -f "${SIMB_CANONICO}" ]]; then
    echo "[FAIL] ${SIMB_CANONICO} não existe — a bandeja cai no ícone colorido"
    rc=1
elif [[ ! -f "${SIMB_APPLET}" ]]; then
    echo "[FAIL] ${SIMB_APPLET} não existe — o applet fica sem glifo simbólico"
    rc=1
elif cmp -s "${SIMB_CANONICO}" "${SIMB_APPLET}"; then
    echo "[ OK ] bandeja e applet servem o mesmo desenho simbólico"
else
    echo "[FAIL] o simbólico da bandeja e o do applet DIVERGIRAM"
    echo "       ${SIMB_CANONICO}"
    echo "       ${SIMB_APPLET}"
    echo "       copie um sobre o outro — o desenho é um só."
    rc=1
fi

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

DEB_RULES_LIST="$(sed -n '/^UDEV_RULES_GLOBS=(/,/^)/p' scripts/build_deb.sh 2>/dev/null)"
DEB_RULES_LIST_USES="$(grep -c 'UDEV_RULES_GLOBS\[@\]' scripts/build_deb.sh 2>/dev/null || true)"

HAS_UDEV_RULES=0
for _r in assets/[0-9][0-9]-*.rules; do
    [[ -f "${_r}" ]] && HAS_UDEV_RULES=1 && break
done

echo "== dois destinos das regras udev no build_deb.sh =="
if [[ ! -f scripts/build_deb.sh || "${HAS_UDEV_RULES}" -eq 0 ]]; then
    echo "[ OK ] sem scripts/build_deb.sh ou sem assets/NN-*.rules — nada a checar"
elif [[ -z "${DEB_RULES_LIST}" ]]; then
    echo "[FAIL] scripts/build_deb.sh: sem a lista única UDEV_RULES_GLOBS=(...)"
    echo "       os dois destinos (rules.d vivo + espelho udev-rules) têm de sair"
    echo "       da MESMA lista, senão um deles fica defasado em silêncio."
    rc=1
elif [[ "${DEB_RULES_LIST_USES}" -lt 2 ]]; then
    echo "[FAIL] scripts/build_deb.sh: UDEV_RULES_GLOBS usada ${DEB_RULES_LIST_USES}x"
    echo "       (esperado >= 2: um laço para /usr/lib/udev/rules.d e um para o"
    echo "       espelho /usr/share/hefesto-dualsense4unix/udev-rules)."
    rc=1
elif ! grep -qF 'usr/share/hefesto-dualsense4unix/udev-rules' scripts/build_deb.sh; then
    echo "[FAIL] scripts/build_deb.sh: espelho udev-rules ausente"
    echo "       o pre-flight do install-host-udev.sh aborta sem ele."
    rc=1
else
    echo "[ OK ] build_deb.sh: rules.d vivo e espelho udev-rules saem da mesma lista"
fi

echo "== paridade das regras udev (assets/ × instaladores) =="
for rules_path in assets/[0-9][0-9]-*.rules; do
    [[ -f "${rules_path}" ]] || continue
    rules_name="$(basename "${rules_path}")"
    rules_prefix="${rules_name%%-*}"
    missing=()

    grep -qF "${rules_name}" uninstall.sh 2>/dev/null \
        || missing+=("uninstall.sh")

    if ! is_install_optional_rule "${rules_name}"; then
        grep -qF "${rules_name}" scripts/install_udev.sh 2>/dev/null \
            || missing+=("scripts/install_udev.sh")
        grep -qF "${rules_name}" scripts/install-host-udev.sh 2>/dev/null \
            || missing+=("scripts/install-host-udev.sh")
        if [[ -n "${DEB_RULES_LIST}" ]]; then
            if ! grep -qF "assets/${rules_prefix}-*.rules" <<<"${DEB_RULES_LIST}" \
               && ! grep -qF "${rules_name}" <<<"${DEB_RULES_LIST}"; then
                missing+=("scripts/build_deb.sh")
            fi
        elif ! grep -qF "assets/${rules_prefix}-*.rules" scripts/build_deb.sh 2>/dev/null \
           && ! grep -qF "${rules_name}" scripts/build_deb.sh 2>/dev/null; then
            missing+=("scripts/build_deb.sh")
        fi
        grep -qF "${rules_name}" packaging/arch/PKGBUILD 2>/dev/null \
            || missing+=("packaging/arch/PKGBUILD")
        grep -qF "${rules_name}" packaging/fedora/hefesto-dualsense4unix.spec 2>/dev/null \
            || missing+=("packaging/fedora/hefesto-dualsense4unix.spec")
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

echo "== acesso da sessão aos nós de ENTRADA (touchpad + sensores de movimento) =="
if [[ "${HAS_UDEV_RULES}" -eq 0 ]]; then
    echo "[ OK ] sem assets/NN-*.rules neste checkout — nada a checar"
else
    _in_motion=""
    _in_touch=""
    _in_tarde=()
    for _in_path in assets/[0-9][0-9]-*.rules; do
        [[ -f "${_in_path}" ]] || continue
        _in_nome="$(basename "${_in_path}")"
        _in_num="$(( 10#${_in_nome:0:2} ))"
        while IFS= read -r _in_linha; do
            [[ "${_in_linha}" == *'SUBSYSTEM=="input"'* ]] || continue
            [[ "${_in_linha}" == *'KERNEL=="event*"'*   ]] || continue
            [[ "${_in_linha}" == *'TAG+="uaccess"'*     ]] || continue
            if [[ "${_in_num}" -ge 73 ]]; then
                [[ " ${_in_tarde[*]-} " == *" ${_in_nome} "* ]] \
                    || _in_tarde+=("${_in_nome}")
                continue
            fi
            case "${_in_linha}" in
                *"Motion Sensors"*|*"IMU"*) _in_motion="${_in_nome}" ;;
            esac
            case "${_in_linha}" in
                *Touchpad*) _in_touch="${_in_nome}" ;;
            esac
        done < <(grep -v '^[[:space:]]*#' "${_in_path}" 2>/dev/null)
    done
    _in_falhas=()
    if [[ "${#_in_tarde[@]}" -gt 0 ]]; then
        _in_falhas+=("TAG uaccess em event* num arquivo >= 73 (${_in_tarde[*]}): a 73-seat-late.rules já passou, a TAG NUNCA vira ACL — renumere para < 73")
    fi
    [[ -n "${_in_motion}" ]] \
        || _in_falhas+=("nenhuma regra dá uaccess ao nó dos SENSORES DE MOVIMENTO (giroscópio): ele é ID_INPUT_ACCELEROMETER, não ID_INPUT_JOYSTICK, então a 70-uaccess.rules do sistema não o cobre")
    [[ -n "${_in_touch}" ]] \
        || _in_falhas+=("nenhuma regra dá uaccess ao nó do TOUCHPAD: ele é ID_INPUT_TOUCHPAD, não ID_INPUT_JOYSTICK, então a 70-uaccess.rules do sistema não o cobre")
    for _in_inst in scripts/install_udev.sh scripts/install-host-udev.sh; do
        [[ -f "${_in_inst}" ]] || continue
        grep -qF 'subsystem-match=input' "${_in_inst}" 2>/dev/null \
            || _in_falhas+=("${_in_inst} não dispara 'udevadm trigger --subsystem-match=input' — a regra de acesso só valeria no próximo replug")
    done
    if [[ "${#_in_falhas[@]}" -eq 0 ]]; then
        echo "[ OK ] touchpad (${_in_touch}) e movimento (${_in_motion}) com uaccess em regra < 73, e o trigger de input nos dois instaladores"
    else
        for _in_f in "${_in_falhas[@]}"; do
            echo "[FAIL] ${_in_f}"
        done
        echo "       sem isso o touchpad e o giroscópio dependem de a usuária estar"
        echo "       no grupo 'input' por fora do produto — que é como estavam até"
        echo "       09/08/2026, e que numa máquina nova simplesmente não acontece."
        rc=1
    fi
fi

echo "== trigger de hidraw dos instaladores (tem de casar dispositivo de verdade) =="
_hidraw_falhas=()
for _hid_inst in scripts/install_udev.sh scripts/install-host-udev.sh; do
    [[ -f "${_hid_inst}" ]] || continue
    _hid_linhas="$(grep -h 'udevadm trigger' "${_hid_inst}" 2>/dev/null \
        | grep -F 'subsystem-match=hidraw' || true)"
    [[ -n "${_hid_linhas}" ]] || continue
    if grep -qF 'attr-match' <<<"${_hid_linhas}"; then
        _hidraw_falhas+=("${_hid_inst}: trigger de hidraw filtrado por --attr-match — um nó hidraw NÃO tem sysattr próprio (idVendor mora no pai USB, e no Bluetooth não há pai USB): o filtro casa ZERO dispositivos, sempre")
    fi
done
if [[ "${#_hidraw_falhas[@]}" -eq 0 ]]; then
    echo "[ OK ] os dois instaladores redisparam hidraw sem filtro impossível"
else
    for _hid_f in "${_hidraw_falhas[@]}"; do
        echo "[FAIL] ${_hid_f}"
    done
    echo "       o certo é 'udevadm trigger --action=change --subsystem-match=hidraw':"
    echo "       reaplica MODE/OWNER e faz a 73-seat-late.rules virar a TAG uaccess"
    echo "       em ACL, sem re-executar os RUN+= presos a ACTION==\"add\"."
    rc=1
fi

echo "== paridade da cura de raiz (assets/modprobe{,.d}/*.conf × instaladores) =="
for conf_path in assets/modprobe/*.conf assets/modprobe.d/*.conf; do
    [[ -f "${conf_path}" ]] || continue
    conf_name="$(basename "${conf_path}")"
    if grep -q '^# X-HefestoNaoEmpacotado:' "${conf_path}" 2>/dev/null; then
        _porque="$(sed -n 's/^# X-HefestoNaoEmpacotado: *//p' "${conf_path}" | head -1)"
        if grep -qF "${conf_name}" uninstall.sh 2>/dev/null; then
            echo "[ -- ] ${conf_name}: fora dos empacotamentos por declaração própria (${_porque}); uninstall.sh a desfaz"
        else
            echo "[FAIL] ${conf_name}: dispensada dos empacotamentos, mas o uninstall.sh NÃO a desfaz"
            rc=1
        fi
        continue
    fi
    missing=()
    grep -qF "${conf_name}" scripts/build_deb.sh 2>/dev/null \
        || missing+=("scripts/build_deb.sh")
    grep -qF "${conf_name}" flatpak/*.yml 2>/dev/null \
        || missing+=("flatpak/*.yml")
    grep -qF "${conf_name}" scripts/install-host-udev.sh 2>/dev/null \
        || missing+=("scripts/install-host-udev.sh")
    grep -qF "${conf_name}" packaging/arch/PKGBUILD 2>/dev/null \
        || missing+=("packaging/arch/PKGBUILD")
    grep -qF "${conf_name}" packaging/fedora/hefesto-dualsense4unix.spec 2>/dev/null \
        || missing+=("packaging/fedora/hefesto-dualsense4unix.spec")
    grep -qF "${conf_name}" uninstall.sh 2>/dev/null \
        || missing+=("uninstall.sh")
    if [[ "${#missing[@]}" -eq 0 ]]; then
        echo "[ OK ] ${conf_name}: coberta em todos os instaladores"
    else
        echo "[FAIL] ${conf_name}: FALTANDO em: ${missing[*]}"
        rc=1
    fi
done

echo "== paridade da cura DKMS (assets/dkms/hid-nintendo × instaladores) =="
if [[ -f assets/dkms/hid-nintendo/dkms.conf ]]; then
    missing=()
    for inst in scripts/build_deb.sh packaging/arch/PKGBUILD \
                packaging/fedora/hefesto-dualsense4unix.spec; do
        { grep -qF "dkms/hid-nintendo" "${inst}" 2>/dev/null \
            && grep -qF "dkms_lib.sh" "${inst}" 2>/dev/null; } \
            || missing+=("${inst}")
    done
    { grep -qF "dkms/hid-nintendo" flatpak/*.yml 2>/dev/null \
        && grep -qF "dkms_lib.sh" flatpak/*.yml 2>/dev/null; } \
        || missing+=("flatpak/*.yml")
    grep -qF "dkms_install_patched_module" scripts/install-host-udev.sh 2>/dev/null \
        || missing+=("scripts/install-host-udev.sh(não roda o DKMS)")
    for hook in packaging/debian/prerm packaging/debian/postrm \
                packaging/arch/hefesto-dualsense4unix.install \
                packaging/fedora/hefesto-dualsense4unix.spec; do
        grep -qF 'dkms remove "hefesto-hid-nintendo/' "${hook}" 2>/dev/null \
            || missing+=("${hook}(remoção)")
    done
    grep -qF "hefesto-hid-nintendo" uninstall.sh 2>/dev/null \
        || missing+=("uninstall.sh")
    if [[ "${#missing[@]}" -eq 0 ]]; then
        echo "[ OK ] dkms hid-nintendo: fontes+lib em todos os formatos, o helper roda o DKMS e a remoção desregistra"
    else
        echo "[FAIL] dkms hid-nintendo: FALTANDO em: ${missing[*]}"
        rc=1
    fi
fi

echo "== paridade da cura DKMS (assets/dkms/rtw88-usb × instaladores) =="
if [[ -f assets/dkms/rtw88-usb/dkms.conf ]]; then
    missing=()
    for inst in scripts/build_deb.sh packaging/arch/PKGBUILD \
                packaging/fedora/hefesto-dualsense4unix.spec; do
        { grep -qF "dkms/rtw88-usb" "${inst}" 2>/dev/null \
            && grep -qF "dkms_lib.sh" "${inst}" 2>/dev/null; } \
            || missing+=("${inst}")
    done
    { grep -qF "dkms/rtw88-usb" flatpak/*.yml 2>/dev/null \
        && grep -qF "dkms_lib.sh" flatpak/*.yml 2>/dev/null; } \
        || missing+=("flatpak/*.yml")
    grep -qF "dkms_install_patched_module hefesto-rtw88-usb" \
        scripts/install-host-udev.sh 2>/dev/null \
        || missing+=("scripts/install-host-udev.sh(não roda o DKMS)")
    for hook in packaging/debian/prerm packaging/debian/postrm \
                packaging/arch/hefesto-dualsense4unix.install \
                packaging/fedora/hefesto-dualsense4unix.spec; do
        grep -qF 'dkms remove "hefesto-rtw88-usb/' "${hook}" 2>/dev/null \
            || missing+=("${hook}(remoção)")
    done
    grep -qF "hefesto-rtw88-usb" uninstall.sh 2>/dev/null \
        || missing+=("uninstall.sh")
    for msg in packaging/debian/postinst \
               packaging/arch/hefesto-dualsense4unix.install \
               packaging/fedora/hefesto-dualsense4unix.spec; do
        grep -qiE "rtw88[_-]usb" "${msg}" 2>/dev/null \
            || missing+=("${msg}(mensagem sem rtw88_usb)")
    done
    if [[ "${#missing[@]}" -eq 0 ]]; then
        echo "[ OK ] dkms rtw88-usb: fontes+lib em todos os formatos, o helper roda o DKMS e a remoção desregistra"
    else
        echo "[FAIL] dkms rtw88-usb: FALTANDO em: ${missing[*]}"
        rc=1
    fi
else
    echo "[ OK ] dkms rtw88-usb: assets/dkms/rtw88-usb/dkms.conf ausente — nada a checar"
fi

echo "== vigia do Wi-Fi USB e o drop-in do watchdog (install × uninstall × doctor) =="
if [[ -f assets/systemd/hefesto-wifi-usb-vigia.service ]]; then
    missing=()
    _wifi_lib="$(sed -e :a -e '/\\$/N; s/\\\n[[:space:]]*/ /; ta' scripts/lib/camada_de_maquina.sh 2>/dev/null \
        | grep -v '^[[:space:]]*#' \
        | grep -vE '^[[:space:]]*(log|echo|printf|warn|info)[[:space:]]' || true)"
    _wifi_lib_inst="$(grep -E '(^|[[:space:]])install[[:space:]]+-D' <<<"${_wifi_lib}" || true)"
    _wifi_un_acao="$(sed -e :a -e '/\\$/N; s/\\\n[[:space:]]*/ /; ta' uninstall.sh 2>/dev/null \
        | grep -v '^[[:space:]]*#' \
        | grep -vE '^[[:space:]]*(log|echo|printf|warn|info)[[:space:]]' || true)"
    _wifi_un_rm="$(grep -E '(^|[[:space:]])rm[[:space:]]+-f' <<<"${_wifi_un_acao}" || true)"
    _wifi_inst="$(grep -v '^[[:space:]]*#' install.sh 2>/dev/null || true)"
    _wifi_doc="$(grep -v '^[[:space:]]*#' scripts/doctor.sh 2>/dev/null || true)"
    for _wifi_dest in /usr/local/lib/hefesto-dualsense4unix/wifi_usb.sh \
                      /etc/NetworkManager/dispatcher.d/90-hefesto-wifi-usb \
                      hefesto-wifi-usb-vigia.service hefesto-wifi-usb-vigia.timer; do
        case "${_wifi_dest}" in
            /*) _wifi_onde="${_wifi_lib_inst}" ;;
            *)  _wifi_onde="${_wifi_lib}" ;;
        esac
        grep -qF -- "${_wifi_dest}" <<<"${_wifi_onde}" \
            || missing+=("scripts/lib/camada_de_maquina.sh(não instala ${_wifi_dest})")
        grep -qF -- "${_wifi_dest}" <<<"${_wifi_un_rm}" \
            || missing+=("uninstall.sh(não remove ${_wifi_dest})")
    done
    grep -qF 'enable --now hefesto-wifi-usb-vigia.timer' <<<"${_wifi_lib}" \
        || missing+=("scripts/lib/camada_de_maquina.sh(não habilita o timer)")
    grep -qF 'disable --now hefesto-wifi-usb-vigia.timer' <<<"${_wifi_un_acao}" \
        || missing+=("uninstall.sh(não desabilita o timer)")
    grep -qE '^[[:space:]]*install_wifi_usb_host[[:space:]]*$' <<<"${_wifi_inst}" \
        || missing+=("install.sh(não chama install_wifi_usb_host)")
    grep -qE '^check_wifi_usb\(\)' <<<"${_wifi_doc}" \
        || missing+=("scripts/doctor.sh(sem check_wifi_usb)")
    grep -qE '^[[:space:]]+check_wifi_usb[[:space:]]*$' <<<"${_wifi_doc}" \
        || missing+=("scripts/doctor.sh(o main não chama check_wifi_usb)")
    grep -qE '^check_bt_rfkill\(\)' <<<"${_wifi_doc}" \
        || missing+=("scripts/doctor.sh(sem check_bt_rfkill)")
    grep -qE '^[[:space:]]+check_bt_rfkill[[:space:]]*$' <<<"${_wifi_doc}" \
        || missing+=("scripts/doctor.sh(o main não chama check_bt_rfkill)")
    grep -qF 'hefesto-bt-health-watchdog.service.d/10-hefesto-maquina.conf' <<<"${_wifi_lib_inst}" \
        || missing+=("scripts/lib/camada_de_maquina.sh(não escreve o drop-in do watchdog)")
    grep -qF 'hefesto-bt-health-watchdog.service.d/10-hefesto-maquina.conf' <<<"${_wifi_un_rm}" \
        || missing+=("uninstall.sh(não remove o drop-in do watchdog)")
    if [[ -f scripts/install-host-udev.sh ]]; then
        _wifi_ihu="$(grep -v '^[[:space:]]*#' scripts/install-host-udev.sh 2>/dev/null || true)"
        for _wifi_dest in hefesto-wifi-usb-vigia 90-hefesto-wifi-usb 10-hefesto-maquina.conf; do
            if grep -qF -- "${_wifi_dest}" <<<"${_wifi_ihu}"; then
                missing+=("scripts/install-host-udev.sh(põe ${_wifi_dest}, e a decisão é que o pacote não o liga)")
            fi
        done
    fi
    if [[ "${#missing[@]}" -eq 0 ]]; then
        echo "[ OK ] vigia do Wi-Fi USB: o install põe os quatro destinos, o uninstall tira os quatro, o doctor pergunta (e pergunta pelo rfkill); o drop-in do watchdog entra e sai; o pacote não liga o vigia"
    else
        echo "[FAIL] vigia do Wi-Fi USB: FALTANDO em: ${missing[*]}"
        echo "       Peça que o install põe e o uninstall não tira é o defeito que tirou"
        echo "       esta família do zsh dela: desinstalar deixava tudo de pé."
        rc=1
    fi
else
    echo "[ OK ] vigia do Wi-Fi USB: assets/systemd/hefesto-wifi-usb-vigia.service ausente — nada a checar"
fi

echo "== a trava comum do rádio (install × uninstall × doctor) =="
if [[ -f assets/tmpfiles.d/hefesto-dualsense4unix-radio.conf ]]; then
    missing=()
    _trava_lib="$(sed -e :a -e '/\\$/N; s/\\\n[[:space:]]*/ /; ta' scripts/lib/camada_de_maquina.sh 2>/dev/null \
        | grep -v '^[[:space:]]*#' \
        | grep -vE '^[[:space:]]*(log|echo|printf|warn|info)[[:space:]]' || true)"
    _trava_lib_inst="$(grep -E '(^|[[:space:]])install[[:space:]]+-D' <<<"${_trava_lib}" || true)"
    _trava_un="$(sed -e :a -e '/\\$/N; s/\\\n[[:space:]]*/ /; ta' uninstall.sh 2>/dev/null \
        | grep -v '^[[:space:]]*#' \
        | grep -vE '^[[:space:]]*(log|echo|printf|warn|info)[[:space:]]' || true)"
    _trava_un_rm="$(grep -E '(^|[[:space:]])rm[[:space:]]+-f' <<<"${_trava_un}" || true)"
    _trava_inst="$(grep -v '^[[:space:]]*#' install.sh 2>/dev/null || true)"
    _trava_doc="$(grep -v '^[[:space:]]*#' scripts/doctor.sh 2>/dev/null || true)"
    grep -qF '/etc/tmpfiles.d/hefesto-dualsense4unix-radio.conf' <<<"${_trava_lib_inst}" \
        || missing+=("scripts/lib/camada_de_maquina.sh(não instala o tmpfiles.d)")
    grep -qF 'assets/tmpfiles.d/hefesto-dualsense4unix-radio.conf' <<<"${_trava_lib}" \
        || missing+=("scripts/lib/camada_de_maquina.sh(não lê o asset)")
    grep -qF 'systemd-tmpfiles --create /etc/tmpfiles.d/hefesto-dualsense4unix-radio.conf' <<<"${_trava_lib}" \
        || missing+=("scripts/lib/camada_de_maquina.sh(não aplica o tmpfiles.d na hora)")
    grep -qE '^[[:space:]]*install_trava_do_radio_host[[:space:]]*$' <<<"${_trava_inst}" \
        || missing+=("install.sh(não chama install_trava_do_radio_host)")
    for _trava_dest in /etc/tmpfiles.d/hefesto-dualsense4unix-radio.conf \
                       /run/hefesto-dualsense4unix/radio.lock; do
        grep -qF -- "${_trava_dest}" <<<"${_trava_un_rm}" \
            || missing+=("uninstall.sh(não remove ${_trava_dest})")
    done
    grep -qF 'rmdir /run/hefesto-dualsense4unix' <<<"${_trava_un}" \
        || missing+=("uninstall.sh(não tira a pasta /run/hefesto-dualsense4unix)")
    grep -qE '^check_trava_do_radio\(\)' <<<"${_trava_doc}" \
        || missing+=("scripts/doctor.sh(sem check_trava_do_radio)")
    grep -qE '^[[:space:]]+check_trava_do_radio[[:space:]]*$' <<<"${_trava_doc}" \
        || missing+=("scripts/doctor.sh(o main não chama check_trava_do_radio)")
    if [[ -f scripts/install-host-udev.sh ]]; then
        _trava_ihu="$(grep -v '^[[:space:]]*#' scripts/install-host-udev.sh 2>/dev/null || true)"
        if grep -qF 'hefesto-dualsense4unix-radio.conf' <<<"${_trava_ihu}"; then
            missing+=("scripts/install-host-udev.sh(põe a trava, e a decisão é que o pacote não a põe)")
        fi
    fi
    if [[ "${#missing[@]}" -eq 0 ]]; then
        echo "[ OK ] trava comum do rádio: o install a cria e aplica, o uninstall a tira, o doctor pergunta; o pacote não a põe"
    else
        echo "[FAIL] trava comum do rádio: FALTANDO em: ${missing[*]}"
        echo "       Trava que o install cria e o uninstall não tira fica em /etc para sempre;"
        echo "       trava que ninguém cria deixa o watchdog e o daemon sem se enxergar."
        rc=1
    fi
else
    echo "[ OK ] trava comum do rádio: assets/tmpfiles.d/hefesto-dualsense4unix-radio.conf ausente — nada a checar"
fi

echo "== paridade da cura DKMS (assets/dkms/hid-playstation × instaladores) =="
if [[ -f assets/dkms/hid-playstation/dkms.conf ]]; then
    missing=()
    for inst in scripts/build_deb.sh packaging/arch/PKGBUILD \
                packaging/fedora/hefesto-dualsense4unix.spec; do
        { grep -qF "dkms/hid-playstation" "${inst}" 2>/dev/null \
            && grep -qF "dkms_lib.sh" "${inst}" 2>/dev/null; } \
            || missing+=("${inst}")
    done
    { grep -qF "dkms/hid-playstation" flatpak/*.yml 2>/dev/null \
        && grep -qF "dkms_lib.sh" flatpak/*.yml 2>/dev/null; } \
        || missing+=("flatpak/*.yml")
    grep -qF "dkms_install_patched_module hefesto-hid-playstation" \
        scripts/install-host-udev.sh 2>/dev/null \
        || missing+=("scripts/install-host-udev.sh(não roda o DKMS)")
    for hook in packaging/debian/prerm packaging/debian/postrm \
                packaging/arch/hefesto-dualsense4unix.install \
                packaging/fedora/hefesto-dualsense4unix.spec; do
        grep -qF 'dkms remove "hefesto-hid-playstation/' "${hook}" 2>/dev/null \
            || missing+=("${hook}(remoção)")
    done
    grep -qF "hefesto-hid-playstation" uninstall.sh 2>/dev/null \
        || missing+=("uninstall.sh")
    if [[ "${#missing[@]}" -eq 0 ]]; then
        echo "[ OK ] dkms hid-playstation: fontes+lib em todos os formatos, o helper roda o DKMS e a remoção desregistra"
    else
        echo "[FAIL] dkms hid-playstation: FALTANDO em: ${missing[*]}"
        echo "       o dkms.conf tem AUTOINSTALL=yes: sem a remoção em TODO hook de"
        echo "       pacote, o patchado se reconstrói a cada kernel para sempre."
        rc=1
    fi
else
    echo "[ OK ] dkms hid-playstation: assets/dkms/hid-playstation/dkms.conf ausente — nada a checar"
fi

echo "== paridade da cura DKMS (assets/dkms/usb-f-hid × instaladores) =="
if [[ -f assets/dkms/usb-f-hid/dkms.conf ]]; then
    missing=()
    for inst in scripts/build_deb.sh packaging/arch/PKGBUILD \
                packaging/fedora/hefesto-dualsense4unix.spec; do
        { grep -qF "dkms/usb-f-hid" "${inst}" 2>/dev/null \
            && grep -qF "dkms_lib.sh" "${inst}" 2>/dev/null; } \
            || missing+=("${inst}")
    done
    grep -qF "%{_datadir}/%{app_id}/dkms/usb-f-hid/" \
        packaging/fedora/hefesto-dualsense4unix.spec 2>/dev/null \
        || missing+=("packaging/fedora/hefesto-dualsense4unix.spec(%files)")
    grep -qF "assets/dkms/usb-f-hid" flatpak/*.yml 2>/dev/null \
        || missing+=("flatpak/*.yml")
    grep -qF "dkms_install_patched_module hefesto-usb-f-hid" \
        scripts/install-host-udev.sh 2>/dev/null \
        || missing+=("scripts/install-host-udev.sh(não roda o DKMS)")
    for hook in packaging/debian/prerm packaging/debian/postrm \
                packaging/arch/hefesto-dualsense4unix.install \
                packaging/fedora/hefesto-dualsense4unix.spec; do
        grep -qF 'dkms remove "hefesto-usb-f-hid/' "${hook}" 2>/dev/null \
            || missing+=("${hook}(remoção)")
    done
    grep -qF "dkms_remove_patched_module hefesto-usb-f-hid" uninstall.sh 2>/dev/null \
        || missing+=("uninstall.sh")
    grep -qF "usb-f-hid" packaging/nix/README.md 2>/dev/null \
        || missing+=("packaging/nix/README.md(a lacuna escrita)")
    if [[ "${#missing[@]}" -eq 0 ]]; then
        echo "[ OK ] dkms usb-f-hid: fontes+lib em todos os formatos, o helper roda o DKMS e a remoção desregistra"
    else
        echo "[FAIL] dkms usb-f-hid: FALTANDO em: ${missing[*]}"
        echo "       o dkms.conf tem AUTOINSTALL=yes: sem a remoção em TODO hook de"
        echo "       pacote, o patchado se reconstrói a cada kernel para sempre."
        rc=1
    fi
else
    echo "[ OK ] dkms usb-f-hid: assets/dkms/usb-f-hid/dkms.conf ausente — nada a checar"
fi

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
    grep -qF "hefesto-hidraw-broker" packaging/debian/prerm 2>/dev/null \
        || missing+=("packaging/debian/prerm")
    grep -qF "hefesto-hidraw-broker" packaging/debian/postrm 2>/dev/null \
        || missing+=("packaging/debian/postrm")
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

echo "== paridade da config do BlueZ (assets/bluetooth × bluez_config.sh) =="
if [[ -f assets/bluetooth/hefesto-bt.block ]]; then
    missing=()
    grep -qF 'scripts/bluez_config.sh" aplicar' install.sh 2>/dev/null \
        || missing+=("install.sh não chama bluez_config.sh aplicar")
    grep -qF 'scripts/bluez_config.sh" remover' uninstall.sh 2>/dev/null \
        || missing+=("uninstall.sh não chama bluez_config.sh remover")
    for _bt_asset in hefesto-bt.block hefesto-fastconnectable.conf hefesto-justworks.conf; do
        grep -qF "${_bt_asset}" scripts/bluez_config.sh 2>/dev/null \
            || missing+=("scripts/bluez_config.sh não cita ${_bt_asset}")
    done
    for _bt_sent in '>>>' '<<<'; do
        grep -qF "hefesto (bluetooth|FastConnectable|JustWorksRepairing) ${_bt_sent}" \
            scripts/bluez_config.sh 2>/dev/null \
            || missing+=("scripts/bluez_config.sh não reconhece as sentinelas legadas (${_bt_sent})")
    done
    _bt_raiz="$(mktemp -d)"
    mkdir -p "${_bt_raiz}/bluetooth"
    printf '[General]\nName = BlueZ\n' > "${_bt_raiz}/bluetooth/main.conf"
    for _bt_i in 1 2 3 4 5 6 7 8 9 10 11 12; do
        printf '[General]\n' \
            > "${_bt_raiz}/bluetooth/main.conf.bak.hefesto-17860000${_bt_i}"
        touch -d "@$(( 1786000000 + _bt_i * 60 ))" \
            "${_bt_raiz}/bluetooth/main.conf.bak.hefesto-17860000${_bt_i}" 2>/dev/null || true
    done
    _bt_antes="$(find "${_bt_raiz}/bluetooth" -maxdepth 1 -type f \
                      -name 'main.conf.bak.hefesto-*' | wc -l)"
    HEFESTO_BT_ETC="${_bt_raiz}/bluetooth" \
    HEFESTO_BT_ASSETS="${PWD}/assets/bluetooth" \
    HEFESTO_BT_SUDO="" \
    HEFESTO_BT_BACKUPS_MANTER=1 \
        bash scripts/bluez_config.sh aplicar >/dev/null 2>&1 || true
    _bt_depois="$(find "${_bt_raiz}/bluetooth" -maxdepth 1 -type f \
                       -name 'main.conf.bak.hefesto-*' | wc -l)"
    _bt_sumidos=()
    for _bt_i in 1 2 3 4 5 6 7 8 9 10 11 12; do
        [[ -f "${_bt_raiz}/bluetooth/main.conf.bak.hefesto-17860000${_bt_i}" ]] \
            || _bt_sumidos+=("main.conf.bak.hefesto-17860000${_bt_i}")
    done
    if [[ "${#_bt_sumidos[@]}" -gt 0 ]]; then
        missing+=("bluez_config.sh aplicar APAGOU ${#_bt_sumidos[@]} backup(s) sem ninguém pedir — a poda automática voltou (havia ${_bt_antes}, ficaram ${_bt_depois}; sumiram: ${_bt_sumidos[*]})")
    fi
    rm -rf "${_bt_raiz}"
    grep -qF 'podar)' scripts/bluez_config.sh 2>/dev/null \
        || missing+=("scripts/bluez_config.sh perdeu o subcomando explícito 'podar'")
    grep -qF "JustWorksRepairing" scripts/doctor.sh 2>/dev/null \
        || missing+=("scripts/doctor.sh não checa JustWorksRepairing")
    grep -qE '(bluez_config\.sh|\$\{dono\})" verificar([[:space:]]|$)' \
        scripts/doctor.sh 2>/dev/null \
        || missing+=("scripts/doctor.sh não consome bluez_config.sh verificar")
    _corpo_main="$(awk '/^main\(\) \{$/ { dentro = 1 } dentro { print } dentro && /^\}$/ { exit }' \
        scripts/doctor.sh 2>/dev/null || true)"
    grep -qE '^[[:space:]]*check_bluez_justworks_repairing[[:space:]]*$' <<< "${_corpo_main}" \
        || missing+=("scripts/doctor.sh define check_bluez_justworks_repairing e NÃO a chama em main()")
    _bt_olhados=(); _bt_pulados=()
    for _bt_pkg in scripts/build_deb.sh flatpak/io.github.hefesto_team.hefesto_dualsense4unix.yml \
                   scripts/build_appimage.sh scripts/build_appimage_gui.sh \
                   packaging/fedora/hefesto-dualsense4unix.spec \
                   packaging/arch/PKGBUILD packaging/nix/package.nix; do
        [[ -f "${_bt_pkg}" ]] || continue
        _bt_codigo="$(grep -v '^[[:space:]]*#' "${_bt_pkg}" 2>/dev/null || true)"
        if ! grep -qF 'doctor.sh' <<< "${_bt_codigo}"; then
            _bt_pulados+=("$(basename "${_bt_pkg}")")
            continue
        fi
        _bt_olhados+=("$(basename "${_bt_pkg}")")
        grep -qF 'bluez_config.sh' <<< "${_bt_codigo}" \
            || missing+=("${_bt_pkg} empacota doctor.sh e deixa bluez_config.sh para trás (detector CEGO no pacote: cai em 'o dono único da config do BlueZ não está aqui')")
    done
    if [[ "${#missing[@]}" -eq 0 ]]; then
        echo "[ OK ] config do BlueZ: dono único, chamado nos dois lados, detector CHAMADO em main(), e a poda provada não-automática"
        echo "       PAR doctor+bluez conferido em ${#_bt_olhados[@]} de $(( ${#_bt_olhados[@]} + ${#_bt_pulados[@]} )) empacotadores: ${_bt_olhados[*]:-nenhum}"
        if [[ "${#_bt_pulados[@]}" -gt 0 ]]; then
            echo "       NÃO conferidos (não levam o doctor.sh, logo a regra de par não se aplica): ${_bt_pulados[*]}"
        fi
    else
        echo "[FAIL] config do BlueZ: ${missing[*]}"
        echo "       JustWorksRepairing=always sem detector foi o defeito de 06/08/2026:"
        echo "       a cura estava no repositório e não chegava ao disco dela."
        rc=1
    fi
else
    echo "[ OK ] config do BlueZ: assets/bluetooth/hefesto-bt.block ausente — nada a checar"
fi

echo "== teclado na tela do L3 (instalador × empacotamentos × doctor × daemon) =="
_osk_promessa="src/hefesto_dualsense4unix/core/keyboard_mappings.py"
if [[ ! -f "${_osk_promessa}" ]] || ! grep -q '_OSK__' "${_osk_promessa}" 2>/dev/null; then
    echo "[ OK ] teclado na tela: o mapa de fábrica não promete teclado na tela neste checkout — nada a checar"
elif [[ ! -f scripts/install_osk.sh ]]; then
    echo "[FAIL] o mapa de fábrica promete teclado na tela num botão e scripts/install_osk.sh não existe"
    echo "       o teclado na tela ficou sem dono: o produto oferece o gesto e não instala nada."
    rc=1
else
    missing=()

    _osk_install_codigo="$(grep -v '^[[:space:]]*#' install.sh 2>/dev/null || true)"
    _osk_bloco_formatos="$(printf '%s\n' "${_osk_install_codigo}" | awk '
        /^if \[\[ "\$\{FORMAT\}" != "native" \]\]; then$/ { dentro = 1 }
        dentro { print }
        dentro && /^[[:space:]]+exit 0$/ { exit }')"
    _osk_bloco_native="$(printf '%s\n' "${_osk_install_codigo}" | awk '
        /^if \[\[ "\$\{FORMAT\}" != "native" \]\]; then$/ { dentro = 1 }
        dentro && /^fi$/ { depois = 1; next }
        depois { print }')"
    grep -qE '^[[:space:]]*install_osk_host[[:space:]]*$' <<< "${_osk_bloco_formatos}" \
        || missing+=("install.sh NÃO instala o teclado na tela nos formatos de pacote (flatpak/appimage/deb saem pelo 'exit 0' sem ele)")
    grep -qE '^[[:space:]]*install_osk_host[[:space:]]*$' <<< "${_osk_bloco_native}" \
        || missing+=("install.sh NÃO instala o teclado na tela no fluxo native")

    _osk_declaram=(
        "packaging/debian/control:^(Depends|Recommends|Suggests):.*wvkbd"
        "packaging/fedora/hefesto-dualsense4unix.spec:^(Requires|Recommends|Suggests):[[:space:]]*wvkbd"
        "packaging/arch/PKGBUILD:^[[:space:]]*'wvkbd:"
        "packaging/nix/package.nix:makeBinPath.*wvkbd"
        "flatpak/io.github.hefesto_team.hefesto_dualsense4unix.yml:^[[:space:]]*-[[:space:]]*name:[[:space:]]*wvkbd[[:space:]]*$"
    )
    for _osk_item in "${_osk_declaram[@]}"; do
        _osk_decl="${_osk_item%%:*}"
        _osk_padrao="${_osk_item#*:}"
        [[ -f "${_osk_decl}" ]] || continue
        _osk_decl_codigo="$(grep -v '^[[:space:]]*#' "${_osk_decl}" 2>/dev/null || true)"
        grep -qE "${_osk_padrao}" <<< "${_osk_decl_codigo}" \
            || missing+=("${_osk_decl} não DECLARA o teclado na tela no campo que o gerenciador lê (padrão: ${_osk_padrao})")
    done

    grep -qE '^check_teclado_na_tela\(\) \{' scripts/doctor.sh 2>/dev/null \
        || missing+=("scripts/doctor.sh não define check_teclado_na_tela")
    _corpo_main="$(awk '/^main\(\) \{$/ { dentro = 1 } dentro { print } dentro && /^\}$/ { exit }' \
        scripts/doctor.sh 2>/dev/null || true)"
    grep -qE '^[[:space:]]*check_teclado_na_tela[[:space:]]*$' <<< "${_corpo_main}" \
        || missing+=("scripts/doctor.sh define check_teclado_na_tela e NÃO a chama em main()")

    _osk_apply_fixes="$(awk '/^apply_fixes\(\) \{$/ { dentro = 1 } dentro { print } dentro && /^\}$/ { exit }' \
        scripts/doctor.sh 2>/dev/null || true)"
    grep -qE 'apt|dnf|pacman|install_osk' <<< "${_osk_apply_fixes}" \
        && missing+=("scripts/doctor.sh CURA o teclado na tela dentro de apply_fixes — o doctor confere e não cura")

    _osk_uninstall_codigo="$(grep -v '^[[:space:]]*#' uninstall.sh 2>/dev/null || true)"
    grep -qE '(apt-get|apt|dnf|pacman|rpm)[^|]*(remove|purge|erase|-R)[^|]*(wvkbd|onboard)' \
        <<< "${_osk_uninstall_codigo}" \
        && missing+=("uninstall.sh REMOVE o pacote do teclado na tela — pacote de sistema não é nosso para desinstalar")
    grep -qF 'teclado-na-tela.conf' <<< "${_osk_uninstall_codigo}" \
        || missing+=("uninstall.sh não apaga a sentinela teclado-na-tela.conf (o doctor passaria a acusar remoção de um produto que já saiu)")

    _osk_keyboard="src/hefesto_dualsense4unix/daemon/subsystems/keyboard.py"
    for _osk_dono in scripts/install_osk.sh scripts/doctor.sh "${_osk_keyboard}"; do
        [[ -f "${_osk_dono}" ]] || { missing+=("${_osk_dono} ausente"); continue; }
        grep -qE '(OSK_BIN_WAYLAND|_OSK_BIN_WAYLAND)[ =]+"wvkbd-mobintl"' "${_osk_dono}" 2>/dev/null \
            || missing+=("${_osk_dono} não casa Wayland com wvkbd-mobintl")
        grep -qE '(OSK_BIN_X11|_OSK_BIN_X11)[ =]+"onboard"' "${_osk_dono}" 2>/dev/null \
            || missing+=("${_osk_dono} não casa X11 com onboard")
    done

    _osk_tmp="$(mktemp -d)"
    for _osk_par in "wayland:wvkbd" "x11:onboard"; do
        _osk_sessao="${_osk_par%%:*}"
        _osk_esperado="${_osk_par##*:}"
        HEFESTO_OSK_STATE="${_osk_tmp}/${_osk_sessao}.conf" \
        HEFESTO_OSK_SESSAO="${_osk_sessao}" \
        HEFESTO_OSK_GERENCIADOR="apt" \
        HEFESTO_OSK_DRY_RUN=1 \
            bash scripts/install_osk.sh >/dev/null 2>&1 || true
        _osk_gravado="$(sed -n 's/^pacote=//p' "${_osk_tmp}/${_osk_sessao}.conf" 2>/dev/null | head -1)"
        [[ "${_osk_gravado}" == "${_osk_esperado}" ]] \
            || missing+=("install_osk.sh em sessão ${_osk_sessao} escolheria '${_osk_gravado:-nada}' e o certo é '${_osk_esperado}'")
    done
    rm -rf "${_osk_tmp}"

    if [[ "${#missing[@]}" -eq 0 ]]; then
        echo "[ OK ] teclado na tela: instalado em TODO formato, declarado nos 5 empacotamentos, conferido (e não curado) pelo doctor, preservado pelo uninstall, e o par sessão↔programa provado por execução"
    else
        echo "[FAIL] teclado na tela: ${missing[*]}"
        echo "       sem ele, NENHUM atalho de fábrica digita uma letra — 'o teclado"
        echo "       emulado não digita' volta a ser literalmente verdade."
        rc=1
    fi
fi

echo "== artefato de sistema sem dono (assets/ × os caminhos de instalação) =="
if [[ ! -f install.sh ]]; then
    echo "[ OK ] artefatos de sistema: sem install.sh neste checkout — nada a checar"
else
    _dono_arquivos=()
    for _dono_cand in install.sh scripts/lib/camada_de_maquina.sh \
                      scripts/install_udev.sh scripts/install-host-udev.sh \
                      scripts/build_deb.sh \
                      scripts/build_appimage.sh scripts/build_appimage_gui.sh \
                      packaging/arch/PKGBUILD \
                      packaging/fedora/hefesto-dualsense4unix.spec \
                      packaging/nix/package.nix \
                      flatpak/*.yml; do
        [[ -f "${_dono_cand}" ]] && _dono_arquivos+=("${_dono_cand}")
    done

    _dono_codigo=""
    if [[ "${#_dono_arquivos[@]}" -gt 0 ]]; then
        _dono_codigo="$(grep -hv '^[[:space:]]*#' "${_dono_arquivos[@]}" 2>/dev/null \
            | grep -vE '^[[:space:]]*(_faria|_faria_root|_nao_faria|log|echo|printf|warn|info|step)[[:space:]]' \
            || true)"
    fi

    _helper_codigo=""
    while IFS= read -r _helper; do
        [[ -f "${_helper}" ]] || continue
        grep -qF -- "$(basename "${_helper}")" <<<"${_dono_codigo}" || continue
        _helper_codigo+="$(grep -v '^[[:space:]]*#' "${_helper}" 2>/dev/null \
            | grep -vE '^[[:space:]]*(_faria|_faria_root|_nao_faria|log|echo|printf|warn|info|step)[[:space:]]' \
            || true)"$'\n'
    done < <(find scripts -maxdepth 1 -name '*.sh' -type f 2>/dev/null | sort)

    _cobertos=""
    _dono_tokens="$(printf '%s\n%s\n' "${_dono_codigo}" "${_helper_codigo}" \
        | sed -e 's/\${[^}]*}/ /g' -e 's/\$[A-Za-z_][A-Za-z0-9_]*/ /g' -e "s/[\"']//g" \
        | grep -oE 'assets/[]A-Za-z0-9_./*?[-]*' \
        | sort -u || true)"
    while IFS= read -r _tok; do
        [[ -n "${_tok}" ]] || continue
        [[ "${_tok}" == */ ]] && continue
        if [[ -d "${_tok}" ]]; then
            _cobertos+="$(find "${_tok}" -type f 2>/dev/null || true)"$'\n'
            continue
        fi
        # shellcheck disable=SC2086
        _cobertos+="$(shopt -s nullglob; printf '%s\n' ${_tok})"$'\n'
    done <<<"${_dono_tokens}"

    _ARTEFATO_SEM_DONO_HOJE=()

    _art_orfaos=()
    _art_contados=0
    _art_delegados=0
    while IFS= read -r _art; do
        [[ -n "${_art}" ]] || continue
        _art_nome="$(basename "${_art}")"

        case "${_art}" in
            assets/[0-9][0-9]-*.rules|assets/modprobe/*.conf|assets/modprobe.d/*.conf)
                _art_delegados=$(( _art_delegados + 1 ))
                continue
                ;;
        esac

        _art_contados=$(( _art_contados + 1 ))
        grep -qF -- "${_art_nome}" <<<"${_dono_codigo}" && continue
        grep -qxF -- "${_art}" <<<"${_cobertos}" && continue
        grep -qF -- "${_art_nome}" <<<"${_helper_codigo}" && continue
        _art_orfaos+=("${_art}")
    done < <(find assets -type f \
        \( -name '*.rules' -o -name '*.service' -o -name '*.timer' -o -name '*.path' \
           -o -name '*.socket' -o -name '*.conf' -o -name '*.desktop' -o -name '*.policy' \) \
        2>/dev/null | sort)

    _art_lacunas_mortas=()
    for _art_lac in ${_ARTEFATO_SEM_DONO_HOJE[@]+"${_ARTEFATO_SEM_DONO_HOJE[@]}"}; do
        _art_lac_arq="${_art_lac%%:*}"
        if [[ ! -f "${_art_lac_arq}" ]]; then
            [[ "${#_art_orfaos[@]}" -eq 0 && "${_art_contados}" -eq 0 ]] && continue
            _art_lacunas_mortas+=("${_art_lac_arq} (não existe mais na árvore)")
            continue
        fi
        _art_ainda_orfao=0
        for _art_o in ${_art_orfaos[@]+"${_art_orfaos[@]}"}; do
            [[ "${_art_o}" == "${_art_lac_arq}" ]] && _art_ainda_orfao=1
        done
        [[ "${_art_ainda_orfao}" -eq 1 ]] \
            || _art_lacunas_mortas+=("${_art_lac_arq} (ganhou dono — a dívida foi paga)")
    done

    _art_restantes=()
    for _art_o in ${_art_orfaos[@]+"${_art_orfaos[@]}"}; do
        _art_declarado=0
        for _art_lac in ${_ARTEFATO_SEM_DONO_HOJE[@]+"${_ARTEFATO_SEM_DONO_HOJE[@]}"}; do
            [[ "${_art_o}" == "${_art_lac%%:*}" ]] && _art_declarado=1
        done
        [[ "${_art_declarado}" -eq 1 ]] || _art_restantes+=("${_art_o}")
    done

    if [[ "${#_art_restantes[@]}" -gt 0 ]]; then
        for _art_o in "${_art_restantes[@]}"; do
            echo "[FAIL] ${_art_o}: artefato de sistema que nenhum caminho de instalação alcança"
        done
        echo "       ESCREVA a instalação dele em UM caminho de produção: cite o arquivo"
        echo "       em install.sh (ou no build_deb.sh/PKGBUILD/spec/package.nix/flatpak),"
        echo "       copie o DIRETÓRIO que o contém, ou chame de lá o helper de scripts/"
        echo "       que o instala. Se ele é resto de uma cura que outro caminho já"
        echo "       substituiu, APAGUE o arquivo — artefato versionado que ninguém"
        echo "       instala é promessa que a máquina dela nunca recebe."
        echo "       Se ainda não é hora, declare em _ARTEFATO_SEM_DONO_HOJE deste"
        echo "       script, com a data e o endereço de onde o caminho se perde."
        rc=1
    fi
    if [[ "${#_art_lacunas_mortas[@]}" -gt 0 ]]; then
        for _art_m in "${_art_lacunas_mortas[@]}"; do
            echo "[FAIL] lacuna declarada que já não vale: ${_art_m}"
        done
        echo "       APAGUE a entrada de _ARTEFATO_SEM_DONO_HOJE. Lacuna que sobrevive"
        echo "       ao próprio defeito vira paisagem, e a próxima pessoa lê a lista"
        echo "       como se fosse a dívida de hoje."
        rc=1
    fi
    if [[ "${#_art_restantes[@]}" -eq 0 && "${#_art_lacunas_mortas[@]}" -eq 0 ]]; then
        echo "[ OK ] artefatos de sistema: ${_art_contados} com dono (+${_art_delegados} nos laços de udev/modprobe acima, ${#_ARTEFATO_SEM_DONO_HOJE[@]} lacuna(s) declarada(s))"
    fi
fi

echo "== irmão sem carona (script distribuído × o irmão que ele chama) =="
_carona_instaladores=()
for _carona_cand in install.sh \
                    scripts/build_deb.sh \
                    scripts/build_appimage.sh scripts/build_appimage_gui.sh \
                    packaging/arch/PKGBUILD \
                    packaging/fedora/hefesto-dualsense4unix.spec \
                    packaging/nix/package.nix \
                    flatpak/*.yml; do
    [[ -f "${_carona_cand}" ]] && _carona_instaladores+=("${_carona_cand}")
done

if [[ "${#_carona_instaladores[@]}" -eq 0 || ! -d scripts ]]; then
    echo "[ OK ] irmão sem carona: sem instalador (ou sem scripts/) neste checkout — nada a checar"
else
    _carona_existentes="$(find scripts -maxdepth 1 -type f \( -name '*.sh' -o -name '*.py' \) \
        -printf '%f\n' 2>/dev/null | sort)"

    _carona_chamados_de() {
        local _s="scripts/$1" _codigo
        [[ -f "${_s}" ]] || return 0
        if [[ "$1" == *.py ]]; then
            grep -E '^[[:space:]]*import[[:space:]]+[A-Za-z_][A-Za-z0-9_]*[[:space:]]*(#|$)' "${_s}" \
                | awk '{print $2 ".py"}' || true
            return 0
        fi
        _codigo="$(grep -vE '^[[:space:]]*#' "${_s}" 2>/dev/null \
            | grep -vE '^[[:space:]]*(sudo[[:space:]]+)?(fail|warn|info|pass|note|hdr|step|die|echo|printf)[[:space:]]' || true)"
        grep -oE '(^|[;&|(){}]|&&|\||then|do|if|else|exec)[[:space:]]*(sudo[[:space:]]+(-n[[:space:]]+)?)?(bash|sh|source|\.)[[:space:]]+("?[^"[:space:]]*/)?[A-Za-z0-9_.-]+\.(sh|py)' \
            <<<"${_codigo}" | grep -oE '[A-Za-z0-9_.-]+\.(sh|py)$' || true
        grep -oE '/usr/(local/lib|share)/hefesto-dualsense4unix/(scripts/)?[A-Za-z0-9_.-]+\.(sh|py)' \
            <<<"${_codigo}" | grep -oE '[A-Za-z0-9_.-]+\.(sh|py)$' || true
    }

    _carona_tem_guarda() {
        grep -qE "\[\[?[^]]*-(x|f|e|r)[[:space:]][^]]*$(sed 's/[.[\*^$]/\\&/g' <<<"$2")" "scripts/$1"
    }

    _carona_faltas=()
    _carona_pares=0
    for _carona_inst in "${_carona_instaladores[@]}"; do
        _carona_set="$(_pkg_scripts_copiados_de "${_carona_inst}" | sort -u)"
        [[ -n "${_carona_set}" ]] || continue
        while IFS= read -r _carona_s; do
            [[ -n "${_carona_s}" ]] || continue
            grep -qxF -- "${_carona_s}" <<<"${_carona_existentes}" || continue
            while IFS= read -r _carona_irmao; do
                [[ -n "${_carona_irmao}" ]] || continue
                [[ "${_carona_irmao}" == "${_carona_s}" ]] && continue
                grep -qxF -- "${_carona_irmao}" <<<"${_carona_existentes}" || continue
                _carona_pares=$(( _carona_pares + 1 ))
                grep -qxF -- "${_carona_irmao}" <<<"${_carona_set}" && continue
                _carona_tem_guarda "${_carona_s}" "${_carona_irmao}" && continue
                _carona_faltas+=("${_carona_inst} leva ${_carona_s}, que chama ${_carona_irmao} sem levar")
            done < <(_carona_chamados_de "${_carona_s}" | sort -u)
        done <<<"${_carona_set}"
    done

    if [[ "${#_carona_faltas[@]}" -gt 0 ]]; then
        for _carona_f in "${_carona_faltas[@]}"; do
            echo "[FAIL] ${_carona_f}"
        done
        echo "       Na máquina de quem instalou por esse caminho, a chamada aponta"
        echo "       para um arquivo que não está lá — e a cura prometida vira um"
        echo "       aviso de falha. Três saídas, e QUALQUER UMA basta: copie o irmão"
        echo "       no mesmo instalador; chame o irmão que aquele layout JÁ tem; ou"
        echo "       escreva a guarda de existência (\`[[ -x .../nome ]]\`, com o NOME"
        echo "       literal) e trate a ausência."
        rc=1
    else
        echo "[ OK ] irmão sem carona: ${_carona_pares} chamada(s) de irmão em script distribuído, todas com carona ou guarda"
    fi
fi

echo "== scripts do produto (o que a janela e o doctor EXECUTAM) × os empacotamentos =="
if [[ ! -d src/hefesto_dualsense4unix || ! -d scripts ]]; then
    echo "[ OK ] scripts do produto: sem src/ (ou sem scripts/) neste checkout — nada a checar"
else
    _prod_faltas=()

    _PRODSCRIPTS=(
        doctor.sh
        bluez_config.sh
        disable_steam_input.sh
        fix_wireplumber_default_source.sh
        install_snd_quirk.sh
    )

    _prod_censo_chamada="$(grep -rhoE '_(find_repo_file|find_doctor_sh|run_script)\([[:space:]]*"scripts/[A-Za-z0-9_.-]+\.sh"' \
        src/hefesto_dualsense4unix 2>/dev/null || true)"
    _prod_censo_abs="$(grep -rhoE '/usr/(local/)?share/hefesto-dualsense4unix/scripts/[A-Za-z0-9_.-]+\.sh' \
        src/hefesto_dualsense4unix 2>/dev/null || true)"
    _prod_censo="$(printf '%s\n%s\n' "${_prod_censo_chamada}" "${_prod_censo_abs}" \
        | grep -oE '[A-Za-z0-9_.-]+\.sh' | sort -u || true)"

    while IFS= read -r _prod_c; do
        [[ -n "${_prod_c}" ]] || continue
        _prod_na_lista=0
        for _prod_s in "${_PRODSCRIPTS[@]}"; do
            [[ "${_prod_s}" == "${_prod_c}" ]] && _prod_na_lista=1
        done
        [[ "${_prod_na_lista}" -eq 1 ]] \
            || _prod_faltas+=("o código EXECUTA scripts/${_prod_c} e ele não está em _PRODSCRIPTS deste portão — ou ele entra na lista (e em todo formato), ou o consumidor some")
    done <<<"${_prod_censo}"

    for _prod_s in "${_PRODSCRIPTS[@]}"; do
        [[ -f "scripts/${_prod_s}" ]] \
            || _prod_faltas+=("scripts/${_prod_s} está em _PRODSCRIPTS e não existe mais no disco — APAGUE-o da lista e dos empacotadores")
    done

    _PRODPKGS=(
        "scripts/build_deb.sh|.deb|share/hefesto-dualsense4unix/scripts"
        "flatpak/io.github.hefesto_team.hefesto_dualsense4unix.yml|Flatpak|/app/share/hefesto-dualsense4unix/scripts"
        "scripts/build_appimage.sh|AppImage (CLI)|share/hefesto-dualsense4unix/scripts"
        "scripts/build_appimage_gui.sh|AppImage (GUI)|share/hefesto-dualsense4unix/scripts"
        "packaging/arch/PKGBUILD|Arch|share/hefesto-dualsense4unix/scripts"
        "packaging/fedora/hefesto-dualsense4unix.spec|Fedora|%{app_id}/scripts"
        "packaging/nix/package.nix|Nix|share/hefesto-dualsense4unix/scripts"
    )

    _prod_conferidos=()
    for _prod_pkg in "${_PRODPKGS[@]}"; do
        _prod_arq="${_prod_pkg%%|*}"
        _prod_resto="${_prod_pkg#*|}"
        _prod_forma="${_prod_resto%%|*}"
        _prod_dest="${_prod_resto##*|}"
        if [[ ! -f "${_prod_arq}" ]]; then
            _prod_faltas+=("${_prod_forma}: ${_prod_arq} não existe neste checkout — o formato sumiu ou mudou de nome; ACERTE _PRODPKGS")
            continue
        fi
        _prod_conferidos+=("${_prod_forma}")
        _prod_leva="$(_pkg_scripts_copiados_de "${_prod_arq}" | sort -u)"
        for _prod_s in "${_PRODSCRIPTS[@]}"; do
            grep -qxF -- "${_prod_s}" <<<"${_prod_leva}" \
                || _prod_faltas+=("${_prod_forma} (${_prod_arq}) NÃO leva scripts/${_prod_s}")
        done
        _prod_codigo="$(sed -e :a -e '/\\$/N; s/\\\n[[:space:]]*/ /; ta' "${_prod_arq}" 2>/dev/null \
            | grep -vE '^[[:space:]]*#' || true)"
        grep -qF -- "${_prod_dest}" <<<"${_prod_codigo}" \
            || _prod_faltas+=("${_prod_forma} (${_prod_arq}) não cita o destino ${_prod_dest}/ — pôr os arquivos em OUTRO diretório é o mesmo que não levá-los, porque BASES_DE_INSTALACAO não olha para lá")

        if [[ "${_prod_arq}" == *.spec ]]; then
            _prod_files="$(sed -n '/^%files/,/^%changelog/p' "${_prod_arq}" 2>/dev/null || true)"
            for _prod_s in "${_PRODSCRIPTS[@]}"; do
                grep -qF -- "/scripts/${_prod_s}" <<<"${_prod_files}" \
                    || _prod_faltas+=("${_prod_forma}: ${_prod_s} é instalado no %install e não aparece no %files — o rpmbuild aborta o pacote inteiro")
            done
        fi
    done

    _PRODSCRIPT_LACUNAS_HOJE=(
        "25/08/2026 — LEVAR NÃO É ACHAR. BASES_DE_INSTALACAO (app/actions/daemon_actions.py) conhece quatro bases: a raiz do checkout, /app/share (Flatpak), /usr/share e /usr/local/share. O Nix instala em \$out/share e as duas receitas de AppImage em \$APPDIR/usr/share, e nenhuma das duas é uma delas — nesses três formatos os arquivos agora VIAJAM e o consumidor ainda não olha para onde caíram. A cura é uma base derivada de sys.prefix, num arquivo que a frente BG-04 não possui."
    )

    _prod_consumidor="src/hefesto_dualsense4unix/app/actions/daemon_actions.py"
    if [[ "${#_PRODSCRIPT_LACUNAS_HOJE[@]}" -gt 0 && -f "${_prod_consumidor}" ]]; then
        _prod_bases="$(sed -n '/^BASES_DE_INSTALACAO/,/^)/p' "${_prod_consumidor}" 2>/dev/null || true)"
        if grep -qF 'sys.prefix' <<<"${_prod_bases}"; then
            _prod_faltas+=("lacuna declarada que já não vale: BASES_DE_INSTALACAO já deriva de sys.prefix — APAGUE a entrada de _PRODSCRIPT_LACUNAS_HOJE")
        fi
    fi

    if [[ "${#_prod_faltas[@]}" -eq 0 ]]; then
        echo "[ OK ] scripts do produto: os ${#_PRODSCRIPTS[@]} viajam nos ${#_prod_conferidos[@]} formatos (${_prod_conferidos[*]}), no destino que o consumidor procura — ${#_PRODSCRIPT_LACUNAS_HOJE[@]} lacuna(s) declarada(s)"
    else
        for _prod_f in "${_prod_faltas[@]}"; do
            echo "[FAIL] scripts do produto: ${_prod_f}"
        done
        echo "       Na máquina de quem instalou por esse formato, \"Deixar tudo"
        echo "       pronto\" e o botão do microfone respondem \"não encontrado\" e"
        echo "       mandam rodar um ./install.sh que não está lá — quem não clonou"
        echo "       o repositório não tem checkout nenhum. O destino não é escolha"
        echo "       livre: é o que BASES_DE_INSTALACAO procura."
        rc=1
    fi
fi

_SVG_PROMESSA="src/hefesto_dualsense4unix/app/tray.py"
echo "== loader SVG do gdk-pixbuf (o que desenha) × o que cada formato declara =="
if [[ ! -f "${_SVG_PROMESSA}" ]] \
   || ! grep -q 'set_icon_theme_path' "${_SVG_PROMESSA}" 2>/dev/null; then
    echo "[ OK ] loader SVG: o produto não carrega SVG em execução neste checkout — nada a checar"
else
    missing=()

    _svg_declaram=(
        "packaging/fedora/hefesto-dualsense4unix.spec:^(Requires|Recommends):[[:space:]]*librsvg2([[:space:]]|$)"
        "packaging/arch/PKGBUILD:^[[:space:]]*'librsvg'"
        "packaging/nix/package.nix:^[[:space:]]*librsvg[[:space:]]*$"
    )
    for _svg_item in "${_svg_declaram[@]}"; do
        _svg_arq="${_svg_item%%:*}"
        _svg_padrao="${_svg_item#*:}"
        [[ -f "${_svg_arq}" ]] || continue
        _svg_codigo="$(grep -v '^[[:space:]]*#' "${_svg_arq}" 2>/dev/null || true)"
        grep -qE "${_svg_padrao}" <<< "${_svg_codigo}" \
            || missing+=("${_svg_arq} não declara o loader SVG no campo que o gerenciador lê (padrão: ${_svg_padrao})")
    done

    if [[ -f packaging/debian/control ]]; then
        _svg_campo_deb="$(awk '
            /^(Depends|Recommends|Pre-Depends):/ { dentro = 1; print; next }
            dentro && /^[[:space:]]/ { print; next }
            dentro { dentro = 0 }
        ' packaging/debian/control 2>/dev/null || true)"
        grep -qE '(^|[[:space:],])librsvg2-common([[:space:],]|$)' <<< "${_svg_campo_deb}" \
            || missing+=("packaging/debian/control: librsvg2-common não está em Depends/Recommends (a menção na Description NÃO instala nada)")
    fi

    if [[ -f install.sh ]]; then
        _svg_censo="$(grep -v '^[[:space:]]*#' install.sh 2>/dev/null || true)"
        grep -qE '"svg-loader\|obrigatoria\|svg\|' <<< "${_svg_censo}" \
            || missing+=("install.sh: o censo _DEPS_DE_SISTEMA não cobra o svg-loader como obrigatória pela checagem de EFEITO (svg)")
        for _svg_fam in 'librsvg2-common' 'librsvg2"' "librsvg\""; do
            grep -qF -- "${_svg_fam}" <<< "${_svg_censo}" \
                || missing+=("install.sh: _pkg_nome perdeu o nome do loader para uma família (procurado: ${_svg_fam})")
        done
    fi

    if [[ -f flatpak/io.github.hefesto_team.hefesto_dualsense4unix.yml ]]; then
        _svg_runtime="$(sed -n 's/^runtime:[[:space:]]*//p' flatpak/io.github.hefesto_team.hefesto_dualsense4unix.yml | head -1)"
        if [[ "${_svg_runtime}" != "org.gnome.Platform" ]]; then
            grep -qi 'rsvg' flatpak/io.github.hefesto_team.hefesto_dualsense4unix.yml 2>/dev/null \
                || missing+=("flatpak: runtime '${_svg_runtime}' não é o org.gnome.Platform que garantia o loader SVG, e o manifesto não bundla nenhum — a isenção caducou")
        fi
    fi

    _SVG_LACUNAS_HOJE=(
        "scripts/build_appimage_gui.sh:19/08/2026 — o AppImage GUI BUNDLA os loaders do gdk-pixbuf (ele mesmo aponta GDK_PIXBUF_MODULE_FILE para o loaders.cache de dentro do pacote, :134), então quem decide se o SVG desenha é o que estava na MÁQUINA DE BUILD. E a lista de pré-requisitos do cabeçalho (:14-15) pede python3-gi, gir1.2-gtk-3.0 e o appindicator, e NÃO pede o librsvg2-common: buildar num host sem ele produz um AppImage com a bandeja vazia e nenhum erro no log. A cura é do dono do build (pedir o pacote no cabeçalho e ABORTAR quando o loader não estiver no host antes de bundlar), não deste portão."
    )
    for _svg_lac in ${_SVG_LACUNAS_HOJE[@]+"${_SVG_LACUNAS_HOJE[@]}"}; do
        _svg_lac_arq="${_svg_lac%%:*}"
        [[ -f "${_svg_lac_arq}" ]] && continue
        missing+=("lacuna declarada que já não vale: ${_svg_lac_arq} não existe mais — APAGUE a entrada de _SVG_LACUNAS_HOJE")
    done

    if [[ "${#missing[@]}" -eq 0 ]]; then
        echo "[ OK ] loader SVG: declarado no .deb, no .spec, no PKGBUILD, no package.nix e no censo do install.sh (por EFEITO), com o flatpak coberto pelo runtime — ${#_SVG_LACUNAS_HOJE[@]} lacuna(s) declarada(s)"
    else
        for _svg_m in "${missing[@]}"; do
            echo "[FAIL] loader SVG: ${_svg_m}"
        done
        echo "       Sem o loader, GdkPixbuf.Pixbuf.new_from_file_at_scale devolve None"
        echo "       EM SILÊNCIO: o ícone some da bandeja, sem UMA linha de erro no"
        echo "       log. Quem instalar por esse formato fica sem o ícone e sem nada"
        echo "       que explique o sumiço."
        echo "       ARMADILHA DE NOME: quem desenha é librsvg2-common (Debian),"
        echo "       librsvg2 (Fedora) e librsvg (Arch/Nix). O librsvg2-bin e o"
        echo "       librsvg2-tools são o rsvg-convert, ferramenta de BUILD — errados."
        rc=1
    fi
fi

_RENDERIZADOR="src/hefesto_dualsense4unix/utils/units_de_usuario.py"
if [[ -f "${_RENDERIZADOR}" ]] && command -v python3 >/dev/null 2>&1; then
    missing=()
    _un_tmp="$(mktemp -d)"
    for _un_forma in "deb|/usr/bin|/opt/hefesto-dualsense4unix/venv/bin/python" \
                     "arch|/usr/bin|/usr/bin/python3" \
                     "fedora|/usr/bin|/usr/bin/python3" \
                     "nix|/nix/store/aaaa-hefesto/bin|/nix/store/bbbb-python3/bin/python3"; do
        IFS='|' read -r _un_nome _un_bin _un_py <<<"${_un_forma}"
        if ! _un_saida="$(python3 "${_RENDERIZADOR}" --assets assets --out "${_un_tmp}/${_un_nome}" \
                --bin-dir "${_un_bin}" --python "${_un_py}" 2>&1)"; then
            missing+=("${_un_nome}: o renderizador recusou as units — ${_un_saida}")
            continue
        fi
        for _un_arq in "${_un_tmp}/${_un_nome}"/*.service; do
            [[ -f "${_un_arq}" ]] || continue
            _un_corpo="$(grep -v '^[[:space:]]*#' "${_un_arq}")"
            if [[ "${_un_corpo}" =~ __[A-Z][A-Z_]*__ ]] || [[ "${_un_corpo}" == *"%h/.local/"* ]]; then
                missing+=("${_un_nome}: $(basename "${_un_arq}") sai com marcador ou caminho do install nativo")
            fi
            while IFS= read -r _un_alvo; do
                [[ -n "${_un_alvo}" ]] || continue
                [[ -f "${_un_tmp}/${_un_nome}/${_un_alvo}" ]] \
                    || missing+=("${_un_nome}: $(basename "${_un_arq}") chama ${_un_alvo}, que o pacote não leva")
            done < <(sed -n -E 's/^(OnFailure|Requires|Wants)=([^[:space:]]+\.service).*/\2/p' <<<"${_un_corpo}")
        done
    done
    rm -rf "${_un_tmp}"

    for _un_pac in scripts/build_deb.sh packaging/arch/PKGBUILD \
                   packaging/fedora/hefesto-dualsense4unix.spec packaging/nix/package.nix; do
        [[ -f "${_un_pac}" ]] || continue
        _un_texto="$(<"${_un_pac}")"
        [[ "${_un_texto}" == *"utils/units_de_usuario.py"* ]] \
            || missing+=("${_un_pac}: não chama o renderizador das units de usuário")
        if [[ "${_un_texto}" == *'for unit in assets/*.service'* ]] || [[ "${_un_texto}" == *'cp "$service_file"'* ]]; then
            missing+=("${_un_pac}: copia as units de assets/ às cegas (chegam com %h/.local/bin e __PYTHON__)")
        fi
    done

    if [[ "${#missing[@]}" -eq 0 ]]; then
        echo "[ OK ] units de usuário: renderizadas para .deb, Arch, Fedora e Nix sem marcador sobrando, e os quatro empacotadores passam pelo renderizador"
    else
        for _un_m in "${missing[@]}"; do
            echo "[FAIL] units de usuário: ${_un_m}"
        done
        echo "       A unit que chega com %h/.local/bin/ ou __PYTHON__ aponta para um"
        echo "       caminho que só o install.sh nativo cria: o daemon não sobe e o"
        echo "       systemd só diz 203/EXEC. O dono é utils/units_de_usuario.py."
        rc=1
    fi
fi

echo "─────────────────────────────────────────"
if [[ "${rc}" -eq 0 ]]; then
    echo "paridade de empacotamento OK"
else
    echo "paridade de empacotamento FALHOU"
fi
exit "${rc}"
