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
    #
    # A EXCEÇÃO DO `-symbolic` — APPLET-MONOCROMÁTICO-01, 07/08/2026.
    # Nome terminado em `-symbolic` NÃO se satisfaz com PNG, e cobrar
    # `apps/<nome>.png` dele seria o gate exigindo exatamente o arquivo que não
    # se deve criar: PNG nunca é recolorido pelo tema (o desvio do libcosmic
    # manda `Data::Image` por um caminho sem cor), e foi por isso que o ícone
    # dela era o único cromático da barra. Para esses nomes o contrato é outro
    # arquivo, não nenhum arquivo: `symbolic/apps/<nome>.svg`.
    # O caso que este gate nasceu para pegar continua pego — nome pedido pelo
    # código sem arquivo instalado reprova igual, só muda QUAL arquivo se cobra.
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

# APPLET-MONOCROMÁTICO-01: o simbólico pedido pelo código tem de EXISTIR nesta
# árvore, e ser o mesmo desenho que o applet COSMIC instala. São dois arquivos
# com nomes diferentes (a bandeja pede `hefesto-dualsense4unix-symbolic`, o
# applet pede `com.vitoriamaria.HefestoDualsense4Unix-symbolic`) e um desenho
# só: se um mudar sem o outro, a barra fica com dois ícones diferentes para o
# mesmo aplicativo conforme a superfície — que é a família de defeito desta
# sprint inteira.
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

# OQ-6 (09/08/2026): o bloco acima cobra que cada regra que
# EXISTE viaje em todo instalador — e passava verde com a regra que NÃO existia.
# Nenhuma linha desta casa dava acesso aos nós de ENTRADA (`/dev/input/event*`)
# do touchpad e dos sensores de movimento, e ninguém percebeu porque a usuária
# desta máquina está no grupo `input` POR FORA do produto (`id` devolve
# `995(input)`; instalador nenhum daqui toca esse grupo). MEDIDO em 09/08 com
# `udevadm info -q property` nos nós vivos:
#
#   event6  "DualSense Wireless Controller"                 TAGS=:uaccess:seat:
#   event7  "DualSense Wireless Controller Motion Sensors"  TAGS=:systemd:
#   event8  "DualSense Wireless Controller Touchpad"        TAGS=(vazio)
#
# Numa máquina nova, touchpad e giroscópio não funcionam — e o sintoma é a
# AUSÊNCIA de dado, que não acusa ninguém. Este portão cobra a EXISTÊNCIA da
# regra, não a paridade dela (dessa o bloco acima já cuida).
#
# TRÊS COISAS SÃO COBRADAS, e a segunda é a que tem dente:
#   1. existe linha de CÓDIGO (comentário não conta) que case `SUBSYSTEM=="input"`
#      + `KERNEL=="event*"` e dê `TAG+="uaccess"`;
#   2. o arquivo que a contém é numerado **< 73**. Quem transforma a TAG em ACL
#      é a `/usr/lib/udev/rules.d/73-seat-late.rules`; numerada >= 73 a regra
#      instala, o `udevadm verify` aprova, o portão de paridade fica verde — e
#      a TAG nunca vira ACL. Já aconteceu duas vezes nesta casa (a `71-uhid`
#      nasceu 79; a `79-external-controller-leds` tinha uma TAG morta que o
#      bloco ONDA-R foi remover). Sem esta cobrança, renomear o arquivo para 79
#      é uma regressão silenciosa e completa;
#   3. os DOIS nós estão cobertos — o de movimento (giroscópio) e o de touchpad.
#      Cobrir um só é meia cura, e foi meia cura que ela pediu para não ter.
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
                # Um arquivo com três linhas mortas é UM arquivo morto: a
                # mensagem nomeia o arquivo uma vez, não uma vez por linha.
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
    # Sem o trigger de `input` a regra só vale no próximo replug do controle —
    # "funciona por default" viraria "funciona depois que você desplugar".
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

# GATILHO-DA-COR-INSTALA-01 (12/08/2026): o trigger de `hidraw` dos instaladores
# tem de poder CASAR alguma coisa.
#
# Os dois instaladores traziam
# `udevadm trigger --subsystem-match=hidraw --attr-match=idVendor=054c`, que
# casa ZERO dispositivos em toda máquina: o `--attr-match` só olha os sysattrs
# do PRÓPRIO nó, e um `hidraw` não tem `idVendor` — ele mora no pai USB, e no
# Bluetooth não existe pai USB (o BlueZ cria o HID por `uhid`). Medido na
# máquina dela em 12/08: 8 dispositivos sem o filtro, 0 com ele.
#
# O que isso custava: numa instalação limpa com o DualSense já conectado no
# rádio, a regra 70 (MODE 0660 + TAG uaccess) não era reaplicada ao nó que já
# existia. O daemon subia sem poder ESCREVER no hidraw daquele controle, e a
# lightbar por Bluetooth — inclusive o gatilho da cor de
# `core/lightbar_gatilho.py` — nascia morta até alguém reconectar o controle
# à mão. É a regra da casa de 08/08 ("nada à mão, nada opt-in") furada por uma
# linha que parecia certa.
#
# Este portão é cego a QUAL trigger se usa: ele cobra só que nenhum trigger de
# hidraw venha casado com um `--attr-match`. A PRESENÇA do trigger é cobrada do
# lado do pytest (tests/unit/test_install_curas_de_12_08_lightbar_por_bluetooth.py),
# que roda contra os arquivos REAIS — aqui o repo pode ser o fixture mínimo dos
# testes deste próprio portão, que não tem controle nenhum a redisparar.
# Mordida: devolver a linha antiga reprova aqui.
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
    #
    # FALSO-VERDE-GATE-DKMS-REMOVE-01 (30/07): este loop nasceu com DOIS greps
    # INDEPENDENTES ("dkms remove" em algum lugar do arquivo E o nome do módulo
    # em algum lugar do arquivo) e por isso NÃO gateava nada — cada hook cita
    # `dkms remove` pelos módulos IRMÃOS e cita `hefesto-hid-nintendo` pela conf
    # de modprobe.d, então os dois greps casavam com ZERO remoção deste módulo.
    # Foi reproduzido ao vivo na onda 1 (a mutação que arrancava o `dkms remove`
    # do hid-playstation passou verde na primeira tentativa por este padrão).
    # Agora é o padrão COMBINADO — o comando E o módulo na MESMA linha — igual
    # ao bloco do hid-playstation, que nasceu certo.
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
    # FALSO-VERDE-GATE-DKMS-REMOVE-01 (30/07): mesma cura do bloco do
    # hid-nintendo acima — dois greps independentes davam falso-verde porque
    # cada hook já cita `dkms remove` (pelos módulos irmãos) e já cita
    # `hefesto-rtw88-usb` (pela mensagem pós-instalação cobrada abaixo). Padrão
    # COMBINADO: o comando E o módulo na MESMA linha.
    for hook in packaging/debian/prerm packaging/debian/postrm \
                packaging/arch/hefesto-dualsense4unix.install \
                packaging/fedora/hefesto-dualsense4unix.spec; do
        grep -qF 'dkms remove "hefesto-rtw88-usb/' "${hook}" 2>/dev/null \
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

# RADIO-ABERTO-01/E1-bis (06/08/2026): assets/bluetooth/ NUNCA esteve sob gate
# nenhum aqui (`grep -n bluetooth` neste arquivo dava ZERO antes desta seção), e
# é por isso que passou despercebido que o `.deb`/`.rpm`/`PKGBUILD`/flatpak não
# levam a configuração do BlueZ.
#
# A DÍVIDA FOI PARTIDA EM DUAS (06/08/2026, correção de decisão gravada). O
# curador anterior escreveu aqui que a lacuna inteira era "dívida registrada,
# exige postinst próprio, e é entrega à parte". Isso é verdade para APLICAR a
# config — reescrever `/etc/bluetooth/main.conf`, que é conffile do dpkg, de
# dentro de um pacote, exige postinst e é mesmo outra entrega. É FALSO para o
# DETECTOR: `check_bluez_justworks_repairing` é LEITURA PURA e lê exclusivamente
# pelo dono único em `${ROOT_DIR}/scripts/bluez_config.sh`. Como o `.deb` copiava
# o `doctor.sh` e não o dono, no layout empacotado a função caía no ramo "o dono
# único da config do BlueZ não está aqui" e NÃO VIA NADA — MEDIDO contra o /etc
# real desta máquina, que tem `JustWorksRepairing=always`. Isto está curado
# (`scripts/build_deb.sh`) e travado abaixo pela REGRA DE PAR: quem empacota o
# `doctor.sh` empacota o `bluez_config.sh`.
#
# O resto desta seção trava o que já era verdade e não pode regredir: existe um
# dono único da config (scripts/bluez_config.sh), install e uninstall o chamam
# pelos dois lados, e o dono conhece cada asset de assets/bluetooth/ — inclusive
# os dois blocos legados, que só existem para o `remover` limpar instalação
# antiga. Sem isto, um asset podia ficar órfão (ninguém aplica, ninguém remove)
# exatamente como o `always` ficou órfão no disco dela por quatro dias.
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
    # Os .block legados não são mais APLICADOS; o contrato é que o removedor
    # ainda saiba limpá-los pelas sentinelas de instalações anteriores a 21/07.
    #
    # ERA VÁCUO ATÉ 06/08/2026: o teste era `grep -qF FastConnectable`, e a
    # palavra aparece na regex de NEUTRALIZAÇÃO — o portão passava com o
    # tratamento legado inteiramente arrancado. Uma linha que LIA como proteção
    # e não protegia. O que se exige agora é a ALTERNÂNCIA das três sentinelas,
    # que é o mecanismo de verdade e não sobrevive a arrancá-lo.
    for _bt_sent in '>>>' '<<<'; do
        grep -qF "hefesto (bluetooth|FastConnectable|JustWorksRepairing) ${_bt_sent}" \
            scripts/bluez_config.sh 2>/dev/null \
            || missing+=("scripts/bluez_config.sh não reconhece as sentinelas legadas (${_bt_sent})")
    done
    # A poda de backup NÃO pode voltar a ser automática: apagaria a evidência
    # medida do colapso 404 -> 3 linhas na primeira execução do install
    # (decisão de 06/08/2026, registrada na sprint RADIO-ABERTO-01).
    #
    # ERA CHECAGEM DE GRAFIA ATÉ 06/08/2026: o teste era `grep -qF
    # '_podar_backups'`, o NOME LITERAL da função que fora removida. Renomear a
    # função e devolver a chamada passava batido — MEDIDO por mutação. Hoje o
    # portão RODA o `aplicar` contra uma raiz falsa em `mktemp -d`, com o
    # diretório povoado de backups, e confere no disco que nenhum sumiu. Nada
    # em /etc é tocado (HEFESTO_BT_ETC + HEFESTO_BT_SUDO vazio), e o mecanismo
    # não tem grafia de que fugir.
    #
    # O CONTEÚDO DOS 12 É IDÊNTICO DE PROPÓSITO. Com conteúdos diferentes a
    # regra "conteúdo ÚNICO nunca sai" protegeria todos, o `_podar` não teria
    # candidato nenhum e o portão passaria verde mesmo com a poda automática de
    # volta — foi exatamente o que aconteceu no primeiro desenho deste bloco, e
    # é a armadilha do teste que não morde. Iguais, os 12 são candidatos
    # legítimos: só a proteção do MAIS ANTIGO e a retenção seguram dois deles, e
    # uma poda automática levaria os outros dez.
    _bt_raiz="$(mktemp -d)"
    mkdir -p "${_bt_raiz}/bluetooth"
    printf '[General]\nName = BlueZ\n' > "${_bt_raiz}/bluetooth/main.conf"
    for _bt_i in 1 2 3 4 5 6 7 8 9 10 11 12; do
        printf '[General]\n' \
            > "${_bt_raiz}/bluetooth/main.conf.bak.hefesto-17860000${_bt_i}"
        # mtimes distintos e crescentes: a ordem "do mais novo para o mais
        # velho" é o que define quem a retenção pouparia.
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
    # O `aplicar` mudou o arquivo, então nasce UM backup novo. O que não pode é
    # QUALQUER um dos 12 anteriores ter sumido.
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
    # O doctor é o único que enxerga o disco entre um install e o próximo — e
    # tem de LER pelo dono único, não reimplementar o parser.
    grep -qF "JustWorksRepairing" scripts/doctor.sh 2>/dev/null \
        || missing+=("scripts/doctor.sh não checa JustWorksRepairing")
    # `-E` com fronteira de palavra de propósito: `-qF ... verificar` casaria
    # com `verificar-qualquer-coisa` e o portão voltaria a ser decorativo.
    grep -qE '(bluez_config\.sh|\$\{dono\})" verificar([[:space:]]|$)' \
        scripts/doctor.sh 2>/dev/null \
        || missing+=("scripts/doctor.sh não consome bluez_config.sh verificar")
    # A CHAMADA, não só a função. MEDIDO em 06/08/2026: apagar a linha
    # `check_bluez_justworks_repairing` de `main()` deixava a suíte inteira
    # verde E este portão OK — porque tudo o que ele procurava continuava vivo
    # DENTRO da função morta. ENTREGA-QUE-NAO-LIGOU-01 literal. O `awk` recorta
    # o CORPO de `main()` (a definição da função fica de fora por construção) e
    # exige a chamada lá dentro.
    awk '/^main\(\) \{$/ { dentro = 1 } dentro { print } dentro && /^\}$/ { exit }' \
        scripts/doctor.sh 2>/dev/null \
        | grep -qE '^[[:space:]]*check_bluez_justworks_repairing[[:space:]]*$' \
        || missing+=("scripts/doctor.sh define check_bluez_justworks_repairing e NÃO a chama em main()")
    # A REGRA DE PAR do empacotamento: quem leva o doctor.sh leva o dono único.
    # Sem ela o detector empacotado é CEGO (cai no ramo "o dono único da config
    # do BlueZ não está aqui") e o portão imprimia "com detector no doctor" sem
    # nunca conferir que o dono viaja junto — o mesmo vácuo que esta leva veio
    # fechar duas seções acima.
    #
    # OS COMENTÁRIOS SÃO DESCARTADOS ANTES DO GREP, e isso não é detalhe: o
    # primeiro desenho deste bloco procurava a palavra no arquivo inteiro, e o
    # próprio comentário que EXPLICA a regra a satisfazia — arrancar o
    # `bluez_config.sh` da linha de cópia do `build_deb.sh` passava verde
    # (MEDIDO por mutação, 06/08/2026). Era a mesma classe de vácuo que o
    # `grep -qF FastConnectable` de duas seções acima tinha, e que esta leva
    # veio fechar. Só linha de CÓDIGO conta.
    #
    # E O FLATPAK ESTAVA NA LISTA PELO ARQUIVO ERRADO (achado de 06/08/2026,
    # MEDIDO): a lista trazia `scripts/build_flatpak.sh`, que é um INVÓLUCRO de
    # 120 linhas — ele chama o `flatpak-builder` e não lista arquivo nenhum.
    # Quem declara o conteúdo do pacote é o MANIFESTO
    # `flatpak/br.andrefarias.Hefesto.yml`, que não estava em lista nenhuma.
    # Resultado: pôr o `doctor.sh` no manifesto SEM o `bluez_config.sh` passava
    # VERDE aqui e na bancada — o invólucro não cita `doctor.sh`, então o
    # `continue` disparava e a regra de PAR nunca era aplicada ao Flatpak.
    # O manifesto é YAML e comenta com `#`, então o descarte de comentários
    # acima continua valendo letra por letra.
    for _bt_pkg in scripts/build_deb.sh flatpak/br.andrefarias.Hefesto.yml \
                   scripts/build_appimage.sh scripts/build_appimage_gui.sh \
                   packaging/fedora/hefesto-dualsense4unix.spec \
                   packaging/arch/PKGBUILD packaging/nix/package.nix; do
        [[ -f "${_bt_pkg}" ]] || continue
        _bt_codigo="$(grep -v '^[[:space:]]*#' "${_bt_pkg}" 2>/dev/null || true)"
        printf '%s\n' "${_bt_codigo}" | grep -qF 'doctor.sh' || continue
        printf '%s\n' "${_bt_codigo}" | grep -qF 'bluez_config.sh' \
            || missing+=("${_bt_pkg} empacota doctor.sh e deixa bluez_config.sh para trás (detector CEGO no pacote: cai em 'o dono único da config do BlueZ não está aqui')")
    done
    if [[ "${#missing[@]}" -eq 0 ]]; then
        echo "[ OK ] config do BlueZ: dono único, chamado nos dois lados, detector CHAMADO em main(), dono empacotado com o doctor, e a poda provada não-automática"
    else
        echo "[FAIL] config do BlueZ: ${missing[*]}"
        echo "       JustWorksRepairing=always sem detector foi o defeito de 06/08/2026:"
        echo "       a cura estava no repositório e não chegava ao disco dela."
        rc=1
    fi
else
    echo "[ OK ] config do BlueZ: assets/bluetooth/hefesto-bt.block ausente — nada a checar"
fi

# TECLADO-QUE-NAO-DIGITA-01 (10/08/2026): o teclado na tela que o L3 do controle
# abre não estava em instalador NENHUM. Medido antes desta seção existir:
#
#     command -v onboard wvkbd-mobintl        ->  NENHUM DOS DOIS
#     grep -c onboard install.sh              ->  0
#     grep -c onboard packaging/debian/control ->  0
#
# O produto oferecia "Abrir teclado na tela" no botão L3, e como nenhum dos nove
# atalhos de fábrica digita uma LETRA (Super, PrintScreen, Alt+Tab,
# Alt+Shift+Tab, Enter, Delete, Backspace e os dois tokens de OSK), o único
# caminho para ESCREVER TEXTO com o controle simplesmente não existia na
# máquina. Esta seção é o que impede isso de voltar por qualquer um dos flancos.
echo "== teclado na tela do L3 (instalador × empacotamentos × doctor × daemon) =="
# A ÂNCORA DESTA SEÇÃO É A PROMESSA, NÃO A CURA. O molde das seções acima é
# gatear pelo asset (`assets/systemd/hefesto-hidraw-broker.service`,
# `assets/bluetooth/hefesto-bt.block`), e aqui isso seria um erro sutil:
# gatear por `scripts/install_osk.sh` faria a seção EMUDECER exatamente quando
# alguém apagasse o instalador — o portão calaria justo no defeito que ele
# existe para acusar.
#
# Então o gate é o que CRIA a promessa: o token `__OPEN_OSK__` no mapa de
# fábrica. Enquanto o produto oferecer "abrir teclado na tela" no L3, ele tem
# de instalar, declarar e conferir o que isso precisa. Se um dia a promessa
# sair do mapa, a seção fica quieta por direito — e é isso que também mantém
# esta seção silenciosa nos checkouts sintéticos dos testes do próprio portão,
# que trazem só `scripts/` e `assets/`.
_osk_promessa="src/hefesto_dualsense4unix/core/keyboard_mappings.py"
if [[ ! -f "${_osk_promessa}" ]] || ! grep -q '__OPEN_OSK__' "${_osk_promessa}" 2>/dev/null; then
    echo "[ OK ] teclado na tela: o mapa de fábrica não promete __OPEN_OSK__ neste checkout — nada a checar"
elif [[ ! -f scripts/install_osk.sh ]]; then
    echo "[FAIL] o mapa de fábrica promete __OPEN_OSK__ no L3 e scripts/install_osk.sh não existe"
    echo "       o teclado na tela ficou sem dono: o produto oferece o gesto e não instala nada."
    rc=1
else
    missing=()

    # 1) O install chama o dono dos DOIS lados da cerca. O `exit 0` do bloco de
    #    formatos deixa doze passos de cura para trás, e um passo escrito só no
    #    fluxo native cairia do lado errado — foi exatamente o achado #7 da Onda
    #    S (o broker) numa camada nova. Comentários fora: um comentário citando
    #    a função satisfaria um grep ingênuo e o portão viraria decoração.
    _osk_install_codigo="$(grep -v '^[[:space:]]*#' install.sh 2>/dev/null || true)"
    _osk_bloco_formatos="$(printf '%s\n' "${_osk_install_codigo}" | awk '
        /^if \[\[ "\$\{FORMAT\}" != "native" \]\]; then$/ { dentro = 1 }
        dentro { print }
        dentro && /^[[:space:]]+exit 0$/ { exit }')"
    _osk_bloco_native="$(printf '%s\n' "${_osk_install_codigo}" | awk '
        /^if \[\[ "\$\{FORMAT\}" != "native" \]\]; then$/ { dentro = 1 }
        dentro && /^fi$/ { depois = 1; next }
        depois { print }')"
    printf '%s\n' "${_osk_bloco_formatos}" | grep -qE '^[[:space:]]*install_osk_host[[:space:]]*$' \
        || missing+=("install.sh NÃO instala o teclado na tela nos formatos de pacote (flatpak/appimage/deb saem pelo 'exit 0' sem ele)")
    printf '%s\n' "${_osk_bloco_native}" | grep -qE '^[[:space:]]*install_osk_host[[:space:]]*$' \
        || missing+=("install.sh NÃO instala o teclado na tela no fluxo native")

    # 2) Todo empacotamento DECLARA o teclado na tela. O .deb/.rpm/PKGBUILD
    #    declaram como dependência fraca (o gerenciador instala por padrão e
    #    ela pode remover sem desinstalar o Hefesto); o Flatpak BUNDLA, porque
    #    dentro do sandbox um pacote do host é invisível — sem o módulo, o
    #    `shutil.which` do daemon devolve None para sempre, por construção.
    #
    #    CADA UM COM O PADRÃO DO SEU CAMPO, e isto foi MEDIDO por mutação em
    #    10/08/2026: o primeiro desenho desta parte procurava a palavra "wvkbd"
    #    no arquivo inteiro, sem comentários. Arrancar `wvkbd | onboard` do
    #    `Recommends:` do debian/control passava VERDE — porque a palavra
    #    continuava viva na PROSA da `Description`, que não é comentário e por
    #    isso sobrevivia ao filtro. É a mesma armadilha do `grep -qF
    #    FastConnectable` da seção do BlueZ com outra roupa: um texto que
    #    EXPLICA a regra satisfazendo a regra. Só o campo que o gerenciador de
    #    pacotes de fato lê conta.
    _osk_declaram=(
        "packaging/debian/control:^(Depends|Recommends|Suggests):.*wvkbd"
        "packaging/fedora/hefesto-dualsense4unix.spec:^(Requires|Recommends|Suggests):[[:space:]]*wvkbd"
        "packaging/arch/PKGBUILD:^[[:space:]]*'wvkbd:"
        "packaging/nix/package.nix:makeBinPath.*wvkbd"
        "flatpak/br.andrefarias.Hefesto.yml:^[[:space:]]*-[[:space:]]*name:[[:space:]]*wvkbd[[:space:]]*$"
    )
    for _osk_item in "${_osk_declaram[@]}"; do
        _osk_decl="${_osk_item%%:*}"
        _osk_padrao="${_osk_item#*:}"
        [[ -f "${_osk_decl}" ]] || continue
        grep -v '^[[:space:]]*#' "${_osk_decl}" 2>/dev/null \
            | grep -qE "${_osk_padrao}" \
            || missing+=("${_osk_decl} não DECLARA o teclado na tela no campo que o gerenciador lê (padrão: ${_osk_padrao})")
    done

    # 3) O doctor CONFERE — e a chamada, não só a função. Definir
    #    `check_teclado_na_tela` e não chamá-la em `main()` deixaria a suíte
    #    verde e o portão OK com a conferência morta: é o
    #    ENTREGA-QUE-NAO-LIGOU-01 literal, o mesmo recorte de `main()` que a
    #    seção do BlueZ já faz por este motivo.
    grep -qE '^check_teclado_na_tela\(\) \{' scripts/doctor.sh 2>/dev/null \
        || missing+=("scripts/doctor.sh não define check_teclado_na_tela")
    awk '/^main\(\) \{$/ { dentro = 1 } dentro { print } dentro && /^\}$/ { exit }' \
        scripts/doctor.sh 2>/dev/null \
        | grep -qE '^[[:space:]]*check_teclado_na_tela[[:space:]]*$' \
        || missing+=("scripts/doctor.sh define check_teclado_na_tela e NÃO a chama em main()")

    # 4) O doctor CONFERE E NÃO CURA (regra da casa). Nenhuma das rotas de cura
    #    pode instalar pacote: `apply_fixes` e `fix_mic_dualsense` rodam sem ela
    #    pedir, e instalar software de sistema por baixo de um diagnóstico é
    #    exatamente o tipo de surpresa que esta casa não entrega.
    awk '/^apply_fixes\(\) \{$/ { dentro = 1 } dentro { print } dentro && /^\}$/ { exit }' \
        scripts/doctor.sh 2>/dev/null \
        | grep -qE 'apt|dnf|pacman|install_osk' \
        && missing+=("scripts/doctor.sh CURA o teclado na tela dentro de apply_fixes — o doctor confere e não cura")

    # 5) O uninstall NÃO remove o pacote (é do sistema, e pode servir a outra
    #    coisa — mesma decisão do libopus0 da ponte de mic), e REMOVE a
    #    sentinela (essa é nossa). Sem apagar a sentinela, o doctor leria uma
    #    máquina já desinstalada como "o pacote sumiu depois do install".
    _osk_uninstall_codigo="$(grep -v '^[[:space:]]*#' uninstall.sh 2>/dev/null || true)"
    printf '%s\n' "${_osk_uninstall_codigo}" \
        | grep -qE '(apt-get|apt|dnf|pacman|rpm)[^|]*(remove|purge|erase|-R)[^|]*(wvkbd|onboard)' \
        && missing+=("uninstall.sh REMOVE o pacote do teclado na tela — pacote de sistema não é nosso para desinstalar")
    printf '%s\n' "${_osk_uninstall_codigo}" | grep -qF 'teclado-na-tela.conf' \
        || missing+=("uninstall.sh não apaga a sentinela teclado-na-tela.conf (o doctor passaria a acusar remoção de um produto que já saiu)")

    # 6) O CONTRATO DE NOMES entre os três que precisam concordar: quem instala
    #    (scripts/install_osk.sh), quem confere (scripts/doctor.sh) e quem
    #    executa (daemon/subsystems/keyboard.py). Se um deles trocar de binário
    #    ou inverter o par sessão↔programa, os três continuam coerentes CONSIGO
    #    MESMOS e o produto instala um e procura outro.
    _osk_keyboard="src/hefesto_dualsense4unix/daemon/subsystems/keyboard.py"
    for _osk_dono in scripts/install_osk.sh scripts/doctor.sh "${_osk_keyboard}"; do
        [[ -f "${_osk_dono}" ]] || { missing+=("${_osk_dono} ausente"); continue; }
        grep -qE '(OSK_BIN_WAYLAND|_OSK_BIN_WAYLAND)[ =]+"wvkbd-mobintl"' "${_osk_dono}" 2>/dev/null \
            || missing+=("${_osk_dono} não casa Wayland com wvkbd-mobintl")
        grep -qE '(OSK_BIN_X11|_OSK_BIN_X11)[ =]+"onboard"' "${_osk_dono}" 2>/dev/null \
            || missing+=("${_osk_dono} não casa X11 com onboard")
    done

    # 7) O MECANISMO, rodado de verdade — a parte de que nenhum comentário pode
    #    fugir. O dono é executado em dry-run contra uma sentinela em mktemp,
    #    com a sessão forçada nos dois sentidos: nada é instalado, nada da
    #    máquina é tocado, e o que se cobra é a DECISÃO gravada no disco. Se
    #    alguém inverter o par sessão↔pacote, esta parte reprova sozinha,
    #    mesmo com todo o texto acima intacto.
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

echo "─────────────────────────────────────────"
if [[ "${rc}" -eq 0 ]]; then
    echo "paridade de empacotamento OK"
else
    echo "paridade de empacotamento FALHOU"
fi
exit "${rc}"
