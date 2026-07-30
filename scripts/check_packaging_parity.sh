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
#      (install_udev.sh, install-host-udev.sh, build_deb.sh, PKGBUILD, spec) e
#      pelo uninstall.sh — regra nova não pode sumir de um instalador sem
#      ninguém notar; e no build_deb.sh a regra tem de chegar aos DOIS destinos
#      (diretório vivo E espelho /usr/share/.../udev-rules, que o
#      install-host-udev.sh prefere e exige completo).
#   4b) o .desktop do aplicativo pedir um Icon= que nenhum/algum formato não
#      instala com esse nome (lançador sem ícone).
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

# PACKAGING-ICON-NAME-MISMATCH-01: o bloco acima cobre SÓ applet COSMIC — o
# `grep -q '^X-CosmicApplet=true' || continue` PULAVA justamente o .desktop do
# aplicativo principal, e era ali que estava o furo: ele pede `Icon=hefesto` e
# três dos cinco formatos (PKGBUILD, spec, package.nix) instalavam o PNG como
# hefesto-dualsense4unix.png, deixando o lançador sem ícone. O contrato aqui é
# outro: o ícone do app NÃO vive versionado ao lado do .desktop (nasce de
# assets/appimage/), então o gate cobra o NOME do arquivo que cada formato
# instala em icons/hicolor/*/apps/.
echo "== Icon dos .desktop de aplicativo (packaging/) × nome instalado =="
ICON_INSTALLERS=(
    scripts/build_deb.sh
    packaging/arch/PKGBUILD
    packaging/fedora/hefesto-dualsense4unix.spec
    packaging/nix/package.nix
)
while IFS= read -r desk; do
    # Applet COSMIC tem contrato próprio (ícone versionado ao lado) — já cobrado.
    grep -q '^X-CosmicApplet=true' "${desk}" 2>/dev/null && continue
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

# PACKAGING-ICON-NAME-MISMATCH-01, segunda metade — a que o primeiro passe desta
# leva ESQUECEU e que só apareceu na verificação independente. Alinhar tudo em
# `hefesto.png` consertou o lançador e QUEBROU a janela e a bandeja, porque há um
# SEGUNDO consumidor, em código e não em .desktop:
#   src/hefesto_dualsense4unix/app/main.py  -> Gtk.Window.set_default_icon_name(...)
#   src/hefesto_dualsense4unix/app/tray.py  -> TRAY_ICON_NAME, via theme.has_icon()
# Sem esse nome no tema, a bandeja cai no fallback "input-gaming" (joystick
# genérico). Não havia ganho líquido: trocava um ícone quebrado por outro, e o que
# quebrava era justamente o que ela vê rodando. Então os DOIS nomes são contrato,
# e o gate cobra os dois.
echo "== Icon pedido pelo CÓDIGO (janela + bandeja) × nome instalado =="
CODE_ICON_SOURCES=(
    src/hefesto_dualsense4unix/app/main.py
    src/hefesto_dualsense4unix/app/tray.py
)
code_icons=()
for src in "${CODE_ICON_SOURCES[@]}"; do
    [[ -f "${src}" ]] || continue
    while IFS= read -r nome; do
        [[ -n "${nome}" ]] && code_icons+=("${nome}")
    done < <(grep -hoE '(set_default_icon_name\(|TRAY_ICON_NAME[[:space:]]*=[[:space:]]*)"[^"]+"' "${src}" 2>/dev/null \
        | grep -oE '"[^"]+"' | tr -d '"')
done
if [[ "${#code_icons[@]}" -eq 0 ]]; then
    echo "[WARN] não achei nome de ícone pedido pelo código — o padrão de busca envelheceu?"
else
    # Ordena e deduplica sem depender de associative array (bash 4.0+ basta).
    while IFS= read -r icon; do
        [[ -n "${icon}" ]] || continue
        missing=()
        for inst in "${ICON_INSTALLERS[@]}"; do
            [[ -f "${inst}" ]] || continue
            grep -qF "apps/${icon}.png" "${inst}" 2>/dev/null || missing+=("${inst}")
        done
        if [[ "${#missing[@]}" -eq 0 ]]; then
            echo "[ OK ] código pede ${icon} e todos os formatos instalam apps/${icon}.png"
        else
            echo "[FAIL] código pede ${icon} e falta apps/${icon}.png em: ${missing[*]}"
            echo "       a JANELA e a BANDEJA caem no fallback genérico nesses formatos."
            echo "       Instale os DOIS nomes (o do .desktop e o do código)."
            rc=1
        fi
    done < <(printf '%s\n' "${code_icons[@]}" | sort -u)
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

# BUG-DEB-MIRROR-RULES-INCOMPLETO-01: o build_deb.sh manda as regras para DOIS
# destinos — o diretório VIVO (/usr/lib/udev/rules.d) e o ESPELHO
# (/usr/share/.../udev-rules), que o install-host-udev.sh PREFERE como origem e
# exige COMPLETO num pre-flight com exit 1. O gate antigo só perguntava se a
# string "assets/NN-*.rules" aparecia em ALGUM lugar do build_deb.sh: o glob do
# diretório vivo satisfazia e o espelho defasado (parava na 81) ficava
# invisível — a ativação inteira do .deb abortava e o gate passava verde. Agora
# o build_deb.sh tem UMA lista (UDEV_RULES_GLOBS) e o gate cobra que ela
# contenha a regra E que os DOIS destinos consumam essa mesma lista.
DEB_RULES_LIST="$(sed -n '/^UDEV_RULES_GLOBS=(/,/^)/p' scripts/build_deb.sh 2>/dev/null)"
DEB_RULES_LIST_USES="$(grep -c 'UDEV_RULES_GLOBS\[@\]' scripts/build_deb.sh 2>/dev/null || true)"

# Só cobra se o checkout realmente tem regras udev para espelhar (fixtures
# mínimas de outros testes não têm assets/NN-*.rules) — mesmo critério de
# "gateado pelo asset" dos blocos de broker/DKMS abaixo.
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

    # uninstall.sh remove TODA regra pelo nome (inclusive descontinuada/opt-in).
    grep -qF "${rules_name}" uninstall.sh 2>/dev/null \
        || missing+=("uninstall.sh")

    if ! is_install_optional_rule "${rules_name}"; then
        grep -qF "${rules_name}" scripts/install_udev.sh 2>/dev/null \
            || missing+=("scripts/install_udev.sh")
        grep -qF "${rules_name}" scripts/install-host-udev.sh 2>/dev/null \
            || missing+=("scripts/install-host-udev.sh")
        # build_deb.sh cobre por glob (assets/NN-*.rules) ou por nome literal,
        # mas SÓ dentro da lista única UDEV_RULES_GLOBS — é ela que alimenta os
        # DOIS destinos (rules.d vivo + espelho udev-rules). Fora dela, a regra
        # chegava só ao diretório vivo e o helper abortava (ver bloco acima).
        if [[ -n "${DEB_RULES_LIST}" ]]; then
            if ! grep -qF "assets/${rules_prefix}-*.rules" <<<"${DEB_RULES_LIST}" \
               && ! grep -qF "${rules_name}" <<<"${DEB_RULES_LIST}"; then
                missing+=("scripts/build_deb.sh")
            fi
        elif ! grep -qF "assets/${rules_prefix}-*.rules" scripts/build_deb.sh 2>/dev/null \
           && ! grep -qF "${rules_name}" scripts/build_deb.sh 2>/dev/null; then
            missing+=("scripts/build_deb.sh")
        fi
        # Onda de restauro 2026-07-29: Arch e Fedora ficavam FORA deste bloco —
        # e é exatamente por isso que a ausência das 82/83/84 no PKGBUILD e no
        # spec nunca reprovou. O bloco de modprobe.d logo abaixo já cobria os
        # dois; aqui é a mesma simetria (e o mesmo pre-flight do
        # install-host-udev.sh, que os dois formatos documentam no pós-install).
        grep -qF "${rules_name}" packaging/arch/PKGBUILD 2>/dev/null \
            || missing+=("packaging/arch/PKGBUILD")
        grep -qF "${rules_name}" packaging/fedora/hefesto-dualsense4unix.spec 2>/dev/null \
            || missing+=("packaging/fedora/hefesto-dualsense4unix.spec")
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
    # Onda T (corretor, achado #10): o .spec do Fedora ficava FORA deste gate
    # — remover um install -Dm644 de conf lá passava verde e o RPM saía sem a
    # cura. Agora o .spec está sob o mesmo contrato dos demais instaladores.
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

# Onda T (corretor, achado #9): a cura de RAIZ do probe BT é o MÓDULO DKMS —
# a conf modprobe.d acima é inerte sem ele. Todo formato empacotado precisa
# carregar as fontes (dkms/hid-nintendo) + a lib (dkms_lib.sh), e o
# install-host-udev.sh (o passo pós-instalação que deb/rpm/arch documentam)
# precisa RODAR o dkms_install_patched_module. Sem este gate, o furo "só a
# conf viaja, o módulo nunca chega ao usuário de pacote" passava verde.
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
    # Corretor final (interação T×W): a REMOÇÃO era gateada só para o irmão
    # rtw88-usb — apagar o `dkms remove` do hid-nintendo de um hook de pacote
    # passava verde (falso-verde reproduzido) e o purge deixava o módulo
    # `hefesto-hid-nintendo` órfão registrado no DKMS para sempre. Mesmo
    # contrato do bloco rtw88-usb abaixo: remoção desregistra em TODO formato.
    for hook in packaging/debian/prerm packaging/debian/postrm \
                packaging/arch/hefesto-dualsense4unix.install \
                packaging/fedora/hefesto-dualsense4unix.spec; do
        { grep -qF "dkms remove" "${hook}" 2>/dev/null \
            && grep -qF "hefesto-hid-nintendo" "${hook}" 2>/dev/null; } \
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

# Onda W: a cura de raiz do fantasma USB do dongle WiFi é o módulo DKMS
# rtw88_usb — mesma lição do hid-nintendo (achado #9): as fontes precisam
# viajar em TODO formato E o install-host-udev.sh precisa RODAR o DKMS.
# E a lição do broker (#2/#8) vale dobrada aqui: a REMOÇÃO de pacote
# (prerm/postrm/.install/%preun) precisa DESREGISTRAR o módulo, senão o
# patchado vence o in-tree para sempre numa máquina que removeu o app.
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
        { grep -qF "dkms remove" "${hook}" 2>/dev/null \
            && grep -qF "hefesto-rtw88-usb" "${hook}" 2>/dev/null; } \
            || missing+=("${hook}(remoção)")
    done
    grep -qF "hefesto-rtw88-usb" uninstall.sh 2>/dev/null \
        || missing+=("uninstall.sh")
    # Paridade de MENSAGEM: o texto pós-instalação de TODO formato tem de citar
    # o rtw88_usb (o postinst do .deb ficava só com o hid-nintendo — assimetria
    # que nenhum gate pegava porque o postinst fica isolado dos blocos de cópia).
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

# Contenção BT (2026-07-25): o TERCEIRO módulo DKMS (hid-playstation, retry de
# feature report na probe) ganhou os dois blocos irmãos acima mas NUNCA ganhou o
# seu — e o furo era o pior dos três: o dkms.conf dele tem AUTOINSTALL="yes",
# então sobrevivia ao `apt remove`/`pacman -R` REGISTRADO, se reconstruía a cada
# kernel novo e vencia o in-tree para sempre numa máquina que removeu o app.
# Só o %preun do Fedora desregistrava. Mesmo contrato dos irmãos.
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
    # Padrão COMBINADO, não dois greps independentes: os hooks já citam
    # "dkms remove" (pelos dois módulos irmãos) e já citam
    # "hefesto-hid-playstation" (pela conf de modprobe.d), então dois greps
    # soltos davam falso-verde com ZERO remoção deste módulo — reproduzido ao
    # vivo arrancando a cura.
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
