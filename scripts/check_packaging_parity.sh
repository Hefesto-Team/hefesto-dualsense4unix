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

# CORRIDA-DO-PIPEFAIL-01 (13/08/2026) — cuidado com `produtor | grep -q`:
#
# `grep -q` SAI no primeiro casamento. O produtor a montante (awk, printf,
# find) morre então com SIGPIPE, status 141, e o `pipefail` desta linha faz o
# PIPE INTEIRO devolver 141 — mesmo tendo o grep achado o que procurava. O
# `|| missing+=(...)` dispara e o portão acusa um defeito que NÃO existe.
#
# É CORRIDA, e por isso enganou por dois dias: quem produz pouco costuma
# terminar antes de o grep sair, e a máquina dela ganhou 200 vezes em 200. O
# runner do CI, mais lento, perdeu — e o `ci.yml` acusou "doctor.sh define
# check_teclado_na_tela e NÃO a chama em main()" com a chamada VIVA na linha
# 4493, deixando no log a assinatura do crime: `printf: write error: Broken
# pipe`.
#
# A cura é não construir o pipe: o produtor entra numa variável e o `grep` lê
# dela por here-string. As duas travessias de `main()` do doctor foram as
# primeiras curadas assim; as outras NOVE ocorrências de `| grep -q` deste
# arquivo foram curadas do mesmo jeito em 13/08/2026, e o arquivo passou a ter
# ZERO. É essa contagem que
# tests/unit/test_check_packaging_parity.py::test_nenhum_produtor_entra_num_pipe_com_grep_q
# fixa: `| grep -q` novo neste arquivo reprova a suíte.
#
# A direção do erro depende do que está pendurado no status, e MEDIR isso em
# 13/08/2026 desmentiu a leitura fácil de que "com `||` sempre dá alarme":
#   - `|| missing+=(...)` ACUSA um defeito que não existe — o caso do CI acima;
#   - `|| continue` (linha do `doctor.sh` na seção do BlueZ) PULA o item, e a
#     checagem seguinte nunca roda: silêncio, não alarme;
#   - `&& missing+=(...)` CALA sobre um defeito que existe — havia duas assim
#     (o doctor que cura, e o uninstall que remove o pacote).
# Duas das três direções erram para o lado de APROVAR.
#
# Fica de fora, de propósito, um caso que PARECE o mesmo e não é: o
# `printf ... | awk '... exit'` que recorta os blocos do `install.sh`. O awk
# também sai cedo, mas ninguém lê o status daquela substituição, e o texto que
# ele já escreveu é o texto completo do bloco. Sem veredito pendurado no
# código de saída, não há defeito a curar.
cd "$(dirname "${BASH_SOURCE[0]}")/.."

rc=0

# Diretórios de BUILD dentro de packaging/ (target/ do Rust chega a dezenas
# de GB): fora de todo grep recursivo — senão o check leva minutos e trava a
# suíte que o executa por subprocess (test_check_packaging_parity.py).
GREP_EXCLUDES=(--exclude-dir=target --exclude-dir=.flatpak-builder --exclude-dir=build)

#: O QUE UM EMPACOTADOR COPIA DE `scripts/` PARA FORA DO CHECKOUT.
#:
#: DONO ÚNICO da pergunta, e é por isso que ele mora aqui em cima, fora de toda
#: seção: duas seções perguntam a mesma coisa — "irmão sem carona" (o que este
#: script instalado chama, e foi junto?) e "scripts do produto" (os cinco que a
#: janela e o doctor executam chegaram a todo formato?). Copiar a função para a
#: segunda seção era o caminho fácil, e é o defeito que esta casa pagou mais
#: caro em 25/08/2026: uma função copiada em dois lugares que divergiram.
#:
#: DUAS FORMAS DE CITAÇÃO, porque as duas existem na árvore: o nome literal na
#: linha de cópia (`build_deb.sh:196`) e o laço com variável
#: (`build_deb.sh:234`), que o grep literal não vê. O laço só conta quando a
#: MESMA variável aparece numa linha de cópia — senão qualquer `for x in ...`
#: do arquivo daria carona de graça.
#:
#: A DOBRA DAS CONTINUAÇÕES VEM PRIMEIRO, e não é enfeite — MEDIDO em
#: 25/08/2026: sem ela, a forma `install -Dm755 -t DIR \` com um nome por linha
#: some INTEIRA, porque só a primeira linha casa com `install -D` e os nomes
#: estão nas outras. O portão via `dkms_lib.sh install-host-udev.sh` no
#: PKGBUILD e no `.spec` e NÃO via os sete `bt_*.sh` que os dois levam desde
#: 22/08 — quinze scripts distribuídos que nenhuma das duas seções auditava.
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
    # CORRIDA-DO-PIPEFAIL-01: era `find ... | grep -q .`. Um diretório de
    # ícones grande faz o `find` ainda estar escrevendo quando o `grep -q` sai
    # no primeiro nome — e aí o ícone EXISTE e o portão diz que falta.
    _icone_achado="$(find "${dir}" -path "*apps/${icon}.*" 2>/dev/null || true)"
    if grep -q . <<< "${_icone_achado}"; then
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
    # AS DUAS CASAS (29/08/2026): o app de DESENVOLVIMENTO não entra em
    # .deb/.rpm/Arch/Nix — ele é instalado só por `install-dev.sh`, na máquina
    # de quem desenvolve. Cobrar o PNG dele desses quatro formatos seria o gate
    # exigindo um arquivo que NÃO se deve empacotar. A dispensa mora no próprio
    # `.desktop` (a chave `X-HefestoNaoEmpacotado`), do mesmo jeito que a do
    # applet acima: quem criar um `.desktop` novo sem a chave é cobrado, e quem
    # a puser tem de escrevê-la à mão, de propósito. E o gate DIZ que pulou —
    # dispensa calada é como uma lápide envelhece sem ninguém ver.
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

# PACKAGING-ICON-NAME-MISMATCH-01, segunda metade — a que o primeiro passe desta
# leva ESQUECEU e que só apareceu na verificação independente. Alinhar tudo em
# `hefesto.png` consertou o lançador e QUEBROU a janela e a bandeja, porque há um
# SEGUNDO consumidor, em código e não em .desktop:
#   scripts/abrir_interface.py              -> Gtk.Window.set_default_icon_name(...)
#   src/hefesto_dualsense4unix/app/tray.py  -> TRAY_ICON_NAME, via theme.has_icon()
# ENDEREÇO CORRIGIDO em 06/09/2026 (`GTK-3`): o primeiro consumidor era
# `app/main.py`, o entry point da janela GTK, apagado com ela
# (`D-0609-GTK-LEVA-INTEIRA`). Quem veste o ícone no processo hoje é o
# `scripts/abrir_interface.py`, que é o que o `.desktop` dela abre pelo
# `interface.sh` -> `run.sh --gui`.
# Sem esse nome no tema, a bandeja cai no fallback "input-gaming" (joystick
# genérico). Não havia ganho líquido: trocava um ícone quebrado por outro, e o que
# quebrava era justamente o que ela vê rodando. Então os DOIS nomes são contrato,
# e o gate cobra os dois.
echo "== Icon pedido pelo CÓDIGO (janela + bandeja) × nome instalado =="
#
# ONDE O NOME MORA, e por que esta régua mudou de lugar em 29/08/2026.
# --------------------------------------------------------------------
# Ela procurava o literal dentro do lançador e de `app/tray.py`:
#     set_default_icon_name("hefesto-dualsense4unix")
#     TRAY_ICON_NAME = "hefesto-dualsense4unix-symbolic"
# Com AS DUAS CASAS (o app dela e o de desenvolvimento), esses dois pontos
# passaram a DERIVAR o nome de `utils/identidade.py`, e os literais saíram de
# lá. A régua não achou mais nada e desligou sozinha, com um `[WARN]` —
# exatamente o defeito que esta casa já pagou onze vezes: *a régua reprova a
# melhora em vez do defeito, porque digitava o que devia LER*.
#
# Agora ela lê o literal de onde ele passou a viver, e continua sendo texto
# puro (sem depender do venv, que este script não tem).
echo "       (o nome vem de utils/identidade.py:HEFESTO — ver o comentário aqui)"
# TOLERÂNCIA DE CHECKOUT — a convenção deste script, que ESTA seção tinha
# quebrado (curado em 03/09/2026). Toda irmã aqui se cala quando o arquivo que
# ela lê não existe (`— nada a checar`); esta reprovava. O efeito medido: os 24
# testes que montam um repositório MÍNIMO em /tmp para exercitar as OUTRAS
# seções levavam [FAIL] de ícone e reprovavam sem ter nada a ver com ícone.
# O defeito que a seção nasceu para pegar continua pego: com `src/` na árvore,
# nome de ícone sumido ou literal cravado reprova igual.
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
            # A BANDEJA pede o mesmo nome com `-symbolic` (app/tray.py:
            # TRAY_ICON_NAME). O sufixo é contrato — APPLET-MONOCROMÁTICO-01 —,
            # então a régua só o deriva se o código ainda o construir assim.
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
    # A TELA tem de pedir o ícone pelo nome da identidade, não por um literal.
    #
    # 06/09/2026: o alvo mudou de `app/main.py` (apagado com a janela GTK) para
    # `scripts/abrir_interface.py`, e a régua mudou de forma junto: lá a chamada
    # era `set_default_icon_name(casa.icone)`, numa linha; aqui o nome passa por
    # uma variável, porque há um SEGUNDO caminho (`set_default_icon_from_file`,
    # para quem ainda não rodou o `install.sh`). Cobrar a forma de uma linha
    # reprovaria a melhora — o defeito que este arquivo já pagou onze vezes.
    # A régua passa a cobrar o EFEITO: o nome sai da identidade, e não há
    # literal dentro da chamada.
    LANCADOR_PY=scripts/abrir_interface.py
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
    _corpo_main="$(awk '/^main\(\) \{$/ { dentro = 1 } dentro { print } dentro && /^\}$/ { exit }' \
        scripts/doctor.sh 2>/dev/null || true)"
    grep -qE '^[[:space:]]*check_bluez_justworks_repairing[[:space:]]*$' <<< "${_corpo_main}" \
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
    # `flatpak/io.github.hefesto_team.hefesto_dualsense4unix.yml`, que não estava em lista nenhuma.
    # Resultado: pôr o `doctor.sh` no manifesto SEM o `bluez_config.sh` passava
    # VERDE aqui e na bancada — o invólucro não cita `doctor.sh`, então o
    # `continue` disparava e a regra de PAR nunca era aplicada ao Flatpak.
    # O manifesto é YAML e comenta com `#`, então o descarte de comentários
    # acima continua valendo letra por letra.
    _bt_olhados=(); _bt_pulados=()
    for _bt_pkg in scripts/build_deb.sh flatpak/io.github.hefesto_team.hefesto_dualsense4unix.yml \
                   scripts/build_appimage.sh scripts/build_appimage_gui.sh \
                   packaging/fedora/hefesto-dualsense4unix.spec \
                   packaging/arch/PKGBUILD packaging/nix/package.nix; do
        [[ -f "${_bt_pkg}" ]] || continue
        _bt_codigo="$(grep -v '^[[:space:]]*#' "${_bt_pkg}" 2>/dev/null || true)"
        # CORRIDA-DO-PIPEFAIL-01: here-string, nunca `printf | grep -q`. Este
        # `|| continue` era o mais traiçoeiro dos nove — sob SIGPIPE ele PULA o
        # empacotador em silêncio, e a regra de PAR da linha seguinte nunca é
        # aplicada. Medido em 13/08/2026: com o pipe de volta, um build_deb.sh
        # que leva o doctor.sh e ESQUECE o bluez_config.sh passa [ OK ].
        if ! grep -qF 'doctor.sh' <<< "${_bt_codigo}"; then
            _bt_pulados+=("$(basename "${_bt_pkg}")")
            continue
        fi
        _bt_olhados+=("$(basename "${_bt_pkg}")")
        grep -qF 'bluez_config.sh' <<< "${_bt_codigo}" \
            || missing+=("${_bt_pkg} empacota doctor.sh e deixa bluez_config.sh para trás (detector CEGO no pacote: cai em 'o dono único da config do BlueZ não está aqui')")
    done
    if [[ "${#missing[@]}" -eq 0 ]]; then
        # A CONTA APARECE, e não é enfeite (achado do braço C do teste de viés,
        # 24/08/2026). A regra de PAR só se aplica a quem leva o `doctor.sh`, e
        # medido nesta árvore isso é UM de sete empacotadores — os outros seis
        # caem na pré-condição acima. O `[ OK ]` afirmava "dono empacotado com o
        # doctor" como se valesse para todos, e valia para um.
        #
        # A regra NÃO mudou: se o `bluez_config.sh` deve viajar em todo pacote é
        # decisão dela, não deste script. O que mudou é o portão parar de
        # afirmar mais do que mediu — a mesma doutrina que fez o medidor de
        # rádio dizer "Não sei" em vez de "Folgada".
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
# Então o gate é o que CRIA a promessa: um token de OSK no mapa de fábrica.
# Enquanto o produto oferecer teclado na tela num botão, ele tem de instalar,
# declarar e conferir o que isso precisa. Se um dia a promessa sair do mapa, a
# seção fica quieta por direito — e é isso que também mantém esta seção
# silenciosa nos checkouts sintéticos dos testes do próprio portão, que trazem
# só `scripts/` e `assets/`.
#
# A ÂNCORA É `_OSK__`, E NÃO `__OPEN_OSK__` — corrigido em 02/09/2026, no dia em
# que o L3 virou alternador. O mapa passou a ter TRÊS tokens
# (`__TOGGLE_OSK__`, `__OPEN_OSK__`, `__CLOSE_OSK__`), e uma âncora presa ao
# nome de UM deles emudeceria a seção inteira no dia em que alguém aposentasse
# justamente esse — sem que a promessa tivesse saído do produto. É a armadilha
# que o parágrafo acima descreve, escrita dentro da própria cura.
_osk_promessa="src/hefesto_dualsense4unix/core/keyboard_mappings.py"
if [[ ! -f "${_osk_promessa}" ]] || ! grep -q '_OSK__' "${_osk_promessa}" 2>/dev/null; then
    echo "[ OK ] teclado na tela: o mapa de fábrica não promete teclado na tela neste checkout — nada a checar"
elif [[ ! -f scripts/install_osk.sh ]]; then
    echo "[FAIL] o mapa de fábrica promete teclado na tela num botão e scripts/install_osk.sh não existe"
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
    # CORRIDA-DO-PIPEFAIL-01: here-string. O `install.sh` é o maior produtor
    # desta seção — é aqui que a corrida tem mais chance de ser perdida, e o
    # veredito seria "o install não chama install_osk_host" com a chamada viva.
    grep -qE '^[[:space:]]*install_osk_host[[:space:]]*$' <<< "${_osk_bloco_formatos}" \
        || missing+=("install.sh NÃO instala o teclado na tela nos formatos de pacote (flatpak/appimage/deb saem pelo 'exit 0' sem ele)")
    grep -qE '^[[:space:]]*install_osk_host[[:space:]]*$' <<< "${_osk_bloco_native}" \
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
        "flatpak/io.github.hefesto_team.hefesto_dualsense4unix.yml:^[[:space:]]*-[[:space:]]*name:[[:space:]]*wvkbd[[:space:]]*$"
    )
    for _osk_item in "${_osk_declaram[@]}"; do
        _osk_decl="${_osk_item%%:*}"
        _osk_padrao="${_osk_item#*:}"
        [[ -f "${_osk_decl}" ]] || continue
        # CORRIDA-DO-PIPEFAIL-01: o produtor lê um ARQUIVO, e o casamento de
        # todos estes padrões está no começo dele — o `grep -qE` sai enquanto o
        # `grep -v` ainda tem o resto do arquivo para escrever. Este é o mais
        # exposto dos nove, porque o tamanho do produtor não é escolha nossa.
        _osk_decl_codigo="$(grep -v '^[[:space:]]*#' "${_osk_decl}" 2>/dev/null || true)"
        grep -qE "${_osk_padrao}" <<< "${_osk_decl_codigo}" \
            || missing+=("${_osk_decl} não DECLARA o teclado na tela no campo que o gerenciador lê (padrão: ${_osk_padrao})")
    done

    # 3) O doctor CONFERE — e a chamada, não só a função. Definir
    #    `check_teclado_na_tela` e não chamá-la em `main()` deixaria a suíte
    #    verde e o portão OK com a conferência morta: é o
    #    ENTREGA-QUE-NAO-LIGOU-01 literal, o mesmo recorte de `main()` que a
    #    seção do BlueZ já faz por este motivo.
    grep -qE '^check_teclado_na_tela\(\) \{' scripts/doctor.sh 2>/dev/null \
        || missing+=("scripts/doctor.sh não define check_teclado_na_tela")
    _corpo_main="$(awk '/^main\(\) \{$/ { dentro = 1 } dentro { print } dentro && /^\}$/ { exit }' \
        scripts/doctor.sh 2>/dev/null || true)"
    grep -qE '^[[:space:]]*check_teclado_na_tela[[:space:]]*$' <<< "${_corpo_main}" \
        || missing+=("scripts/doctor.sh define check_teclado_na_tela e NÃO a chama em main()")

    # 4) O doctor CONFERE E NÃO CURA (regra da casa). Nenhuma das rotas de cura
    #    pode instalar pacote: `apply_fixes` e `fix_mic_dualsense` rodam sem ela
    #    pedir, e instalar software de sistema por baixo de um diagnóstico é
    #    exatamente o tipo de surpresa que esta casa não entrega.
    #    CORRIDA-DO-PIPEFAIL-01, e aqui ela erra para o lado de APROVAR: o
    #    veredito está num `&&`, então o 141 do pipe faz o `missing+=` NÃO
    #    disparar. O doctor curaria o teclado na tela e o portão diria [ OK ].
    _osk_apply_fixes="$(awk '/^apply_fixes\(\) \{$/ { dentro = 1 } dentro { print } dentro && /^\}$/ { exit }' \
        scripts/doctor.sh 2>/dev/null || true)"
    grep -qE 'apt|dnf|pacman|install_osk' <<< "${_osk_apply_fixes}" \
        && missing+=("scripts/doctor.sh CURA o teclado na tela dentro de apply_fixes — o doctor confere e não cura")

    # 5) O uninstall NÃO remove o pacote (é do sistema, e pode servir a outra
    #    coisa — mesma decisão do libopus0 da ponte de mic), e REMOVE a
    #    sentinela (essa é nossa). Sem apagar a sentinela, o doctor leria uma
    #    máquina já desinstalada como "o pacote sumiu depois do install".
    _osk_uninstall_codigo="$(grep -v '^[[:space:]]*#' uninstall.sh 2>/dev/null || true)"
    # CORRIDA-DO-PIPEFAIL-01 nas duas: here-string. O `uninstall.sh` tem mais
    # de mil linhas, e a sentinela é citada perto do começo.
    grep -qE '(apt-get|apt|dnf|pacman|rpm)[^|]*(remove|purge|erase|-R)[^|]*(wvkbd|onboard)' \
        <<< "${_osk_uninstall_codigo}" \
        && missing+=("uninstall.sh REMOVE o pacote do teclado na tela — pacote de sistema não é nosso para desinstalar")
    grep -qF 'teclado-na-tela.conf' <<< "${_osk_uninstall_codigo}" \
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

# ---------------------------------------------------------------------------
# A-CASA-SABE-E-O-PRODUTO-NAO-FAZ-01 / ARTEFATO SEM DONO (12/08/2026)
#
# MEDIDO antes desta seção existir: das dezessete seções deste portão, só DUAS
# são genéricas — o laço das regras udev (:266) e o das confs de modprobe
# (:464). As outras quinze são blocos escritos à mão, um por cura já paga. A
# consequência é o furo que esta seção fecha: as TREZE unidades systemd de
# `assets/` e `assets/systemd/` não tinham laço nenhum — só o broker era citado,
# à mão, em duas linhas (:647 e :684). Uma unit nova entrava na árvore e
# instalador nenhum era cobrado por ela. Mesmo furo em `assets/wireplumber/`,
# `assets/NetworkManager/`, `assets/bluetooth/` e `assets/appimage/`.
#
# A ÂNCORA É O ARTEFATO, e aqui isso é o certo (ao contrário da seção do teclado
# na tela, onde a âncora tem de ser a promessa): o arquivo versionado em
# `assets/` É a promessa — o produto promete pôr isto na máquina dela. Se ele
# sair da árvore, não há promessa, e o silêncio é justo.
#
# O QUE CONTA COMO ARTEFATO DE SISTEMA, e a régua para quem acrescentar um tipo
# novo amanhã: é artefato de sistema o arquivo que o produto INSTALA num lugar
# do sistema ou da sessão dela e que um programa de fora do Hefesto lê —
# `.rules` (udev), `.service .timer .path .socket` (systemd), `.conf` (modprobe,
# wireplumber, NetworkManager, BlueZ, DKMS), `.desktop` (lançador) e `.policy`
# (polkit). NÃO são: `.svg`/`.png` (arte — o portão de ícones acima já os cobra
# pelo NOME que cada formato instala), `.patch`/`.c`/`.h`/`Makefile`/`BASELINE`
# (fonte de DKMS, que chega pela cópia do diretório e é cobrada pelos três
# blocos de DKMS), os `.json` de `assets/profiles_default/` (dado que viaja
# dentro do pacote, sem lugar no sistema) e os `.sh` (código executável: o dono
# de um `.sh` é quem o CHAMA — unit, install ou outro script —, pergunta
# diferente da desta seção, e misturar as duas daria uma resposta fraca às duas).
#
# O ALCANCE CONTA TRÊS CAMINHOS, porque MEDIDO: contar só o nome no `install.sh`
# produziria ruído garantido — `assets/wireplumber/5{1,2,3}-*.conf` quem instala
# é `scripts/fix_wireplumber_default_source.sh` (chamado em install.sh:1139 e
# :1143), e as fontes de `assets/dkms/*/` chegam por cópia de DIRETÓRIO.
#
# E A REMOÇÃO NÃO É COBRADA AQUI, contra o primeiro desenho desta seção: cobrar
# `uninstall.sh` pelo NOME do asset dá DOIS falsos, medidos —
# `bluetooth-dropin-10-hefesto-resilience.conf` é removido pelo nome de DESTINO
# (`/etc/systemd/system/bluetooth.service.d/10-hefesto-resilience.conf`,
# uninstall.sh:675) e o `proton-pin.conf` é desfeito pelo `proton_pin.py
# --unlock` (uninstall.sh:1367), que não cita arquivo nenhum. O nome no disco
# dela não é o nome no repositório, e um portão que finge o contrário reprova
# quem está certo. A remoção continua cobrada por família, onde o nome de
# destino é conhecido (udev, modprobe, DKMS, broker, BlueZ, teclado na tela).
# O CHECKOUT TEM DE TER UM INSTALADOR para ser julgado por esta régua. Mesmo
# critério de "gateado pelo asset" das seções acima (:246, :647, :712), do lado
# do dono em vez do lado do artefato: os repositórios sintéticos dos testes deste
# próprio portão trazem só `assets/` e `scripts/`, e cobrar deles a instalação de
# um asset de mentira seria o portão acusando o instrumento, não o produto.
echo "== artefato de sistema sem dono (assets/ × os caminhos de instalação) =="
if [[ ! -f install.sh ]]; then
    echo "[ OK ] artefatos de sistema: sem install.sh neste checkout — nada a checar"
else
    #: Os arquivos de produção que podem SER dono. Qualquer UM basta: a pergunta
    #: desta seção é "alguém instala isto?", não "todo formato instala isto?" —
    #: essa é a pergunta das seções de paridade, e cada família que a merece já tem
    #: a sua. Aqui é o piso: artefato que NINGUÉM instala.
    _dono_arquivos=()
    for _dono_cand in install.sh \
                      scripts/install_udev.sh scripts/install-host-udev.sh \
                      scripts/build_deb.sh \
                      scripts/build_appimage.sh scripts/build_appimage_gui.sh \
                      packaging/arch/PKGBUILD \
                      packaging/fedora/hefesto-dualsense4unix.spec \
                      packaging/nix/package.nix \
                      flatpak/*.yml; do
        [[ -f "${_dono_cand}" ]] && _dono_arquivos+=("${_dono_cand}")
    done

    # Só linha de CÓDIGO conta. É a mesma armadilha do bloco do BlueZ (:812) e do
    # teclado na tela (:892): um comentário — ou a prosa de um `Description:` —
    # citando o arquivo satisfaria um grep ingênuo, e o portão viraria decoração
    # exatamente no dia em que a instalação fosse arrancada e o comentário ficasse.
    _dono_codigo=""
    if [[ "${#_dono_arquivos[@]}" -gt 0 ]]; then
        _dono_codigo="$(grep -hv '^[[:space:]]*#' "${_dono_arquivos[@]}" 2>/dev/null || true)"
    fi

    # Caminho 3, montado antes do laço: helper de `scripts/` que algum dono CHAMA.
    # Uma indireção só — é a que o produto usa (install.sh -> helper -> asset), e
    # duas já seriam alcance por parentesco distante, que não instala nada.
    _helper_codigo=""
    while IFS= read -r _helper; do
        [[ -f "${_helper}" ]] || continue
        grep -qF -- "$(basename "${_helper}")" <<<"${_dono_codigo}" || continue
        _helper_codigo+="$(grep -v '^[[:space:]]*#' "${_helper}" 2>/dev/null || true)"$'\n'
    done < <(find scripts -maxdepth 1 -name '*.sh' -type f 2>/dev/null | sort)

    # Caminho 2 — cópia de DIRETÓRIO e GLOB, resolvidos de verdade contra o disco.
    # Não basta procurar o nome do diretório: `assets/` aparece no install como raiz
    # (install.sh:193) e `assets/systemd/${_btres_u}` aparece com o nome vindo de uma
    # variável — os dois casariam um `grep` de prefixo e dariam alcance de graça a
    # TODO arquivo daquele diretório, que é o vácuo que esta seção não pode ter.
    # Então: as expansões de variável são apagadas (o token que sobra terminado em
    # `/` é DESCARTADO, porque o que dizia qual arquivo era a variável), e o que
    # resta é resolvido como caminho — diretório existente cobre o que está sob ele,
    # e glob cobre o que ele casa.
    #
    # A ASPA É APAGADA, não trocada por espaço, e isto foi MEDIDO: o install escreve
    # o glob das regras como `"${ROOT_DIR}/assets/"[0-9][0-9]-*.rules` (:1329), com a
    # aspa NO MEIO do caminho. Trocá-la por espaço partia o token em `assets/` (que o
    # descarte acima come, e ainda bem) mais um resto sem prefixo — e o laço por glob
    # não cobria nada, silenciosamente.
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
        # Glob resolvido pelo shell, em subshell para não vazar o `nullglob`.
        # O `${_tok}` SEM aspas é o mecanismo, não descuido: é a expansão do
        # glob que responde "quais arquivos este laço do install cobre?". Com
        # aspas, `assets/systemd/*.service` viraria um nome literal, casaria
        # zero, e o caminho 2 do alcance calaria inteiro — o portão passaria a
        # acusar quem está instalado por laço.
        # shellcheck disable=SC2086
        _cobertos+="$(shopt -s nullglob; printf '%s\n' ${_tok})"$'\n'
    done <<<"${_dono_tokens}"

    #: A DÍVIDA DECLARADA — `arquivo:razão com data`. Molde de
    #: `INSTALL_OPTIONAL_RULES` acima e de `_SEM_ESCRITOR_HOJE`
    #: (tests/unit/test_perfil_salva_tudo_cobertura_das_secoes.py:129): declarar é
    #: honesto, e este portão não castiga honestidade — só não deixa a lápide
    #: envelhecer calada (a conferência está logo abaixo do laço, e uma entrada que
    #: já ganhou dono REPROVA até alguém apagá-la).
    #:
    #: VAZIA em 12/08/2026, e não por sorte: os 46 artefatos de sistema desta árvore
    #: têm dono, medidos um a um com a régua dos três caminhos. Esta seção não cobra
    #: dívida velha — ela impede a próxima.
    _ARTEFATO_SEM_DONO_HOJE=()

    _art_orfaos=()
    _art_contados=0
    _art_delegados=0
    while IFS= read -r _art; do
        [[ -n "${_art}" ]] || continue
        _art_nome="$(basename "${_art}")"

        # Sem contar duas vezes: os dois laços GENÉRICOS que já existem neste
        # arquivo cobrem estas duas famílias arquivo por arquivo, e com uma régua
        # mais dura (paridade em TODO instalador, não "alguém instala"). Repeti-las
        # aqui daria duas linhas de saída para o mesmo arquivo e — pior — dois
        # veredictos diferentes sobre ele: a `75-*.rules` é opt-in por decisão
        # registrada (INSTALL_OPTIONAL_RULES, :211) e aqui apareceria como coberta,
        # o que ensinaria a ler o portão errado.
        case "${_art}" in
            assets/[0-9][0-9]-*.rules|assets/modprobe/*.conf|assets/modprobe.d/*.conf)
                _art_delegados=$(( _art_delegados + 1 ))
                continue
                ;;
        esac

        _art_contados=$(( _art_contados + 1 ))
        # 1) pelo nome, no código de algum dono.
        grep -qF -- "${_art_nome}" <<<"${_dono_codigo}" && continue
        # 2) por diretório copiado inteiro ou por glob resolvido acima.
        grep -qxF -- "${_art}" <<<"${_cobertos}" && continue
        # 3) por helper de `scripts/` que algum dono chama.
        grep -qF -- "${_art_nome}" <<<"${_helper_codigo}" && continue
        _art_orfaos+=("${_art}")
    done < <(find assets -type f \
        \( -name '*.rules' -o -name '*.service' -o -name '*.timer' -o -name '*.path' \
           -o -name '*.socket' -o -name '*.conf' -o -name '*.desktop' -o -name '*.policy' \) \
        2>/dev/null | sort)

    # A lápide não envelhece calada: entrada declarada que já não vale REPROVA, para
    # que a lista encolha sozinha quando alguém pagar a dívida ou apagar o resto.
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

# ---------------------------------------------------------------------------
# IRMAO-SEM-CARONA-01 (12/08/2026) — a outra metade da seção acima
#
# A seção "artefato de sistema sem dono" recusa explicitamente os `.sh`, e com
# razão declarada ali mesmo: *"o dono de um `.sh` é quem o CHAMA — unit, install
# ou outro script —, pergunta diferente da desta seção"*. Esta é aquela outra
# pergunta, e ela é o inverso da primeira: não "quem instala este arquivo?", mas
# **"o que este arquivo instalado chama, e isso foi junto?"**.
#
# O DEFEITO QUE A FEZ EXISTIR, MEDIDO em 12/08/2026: `scripts/build_deb.sh:216`
# levava cinco scripts para dentro do pacote — `doctor.sh`, `bluez_config.sh`,
# `disable_steam_input.sh`, `fix_wireplumber_default_source.sh` e
# `dsx_recover.sh`, este último RETIRADO do laço em 26/08/2026 por não ter
# consumidor em lugar nenhum (LEVA-4-E; hoje o laço leva quatro)
# — e o `doctor.sh` chamava, em `apply_fixes`, um SEXTO que ninguém levou:
# `sudo bash "${ROOT_DIR}/scripts/install_udev.sh"`. Como o `ROOT_DIR` do doctor
# é derivado do lugar do próprio arquivo (`scripts/doctor.sh:60`), no layout do
# .deb aquilo apontava para `/usr/share/hefesto-dualsense4unix/scripts/
# install_udev.sh`, que não existe — e `hefesto-dualsense4unix doctor --fix`
# (que ACHA o doctor no .deb, `cli/cmd_doctor.py:26`) respondia "falha ao
# reaplicar udev" na máquina de quem instalou pelo pacote. O irmão certo para
# aquele layout já viajava no mesmo pacote: `install-host-udev.sh`, cuja forma 3
# no cabeçalho é literalmente "Direto de um .deb instalado".
#
# A ÂNCORA É A CHAMADA, não o arquivo: só é cobrado o script que algum
# instalador COPIA para fora do checkout. Script que só roda do repositório
# clonado tem todos os irmãos ao lado por construção, e cobrá-lo seria inventar
# defeito — é por isso que `scripts/eliminacao.py` e `scripts/identidade_do_vpad.py`
# não aparecem aqui: quem os importa (`gerar-mapa.py`, os três ensaios de
# bancada) é instrumento de bancada, e instrumento de bancada nenhum instalador
# distribui. No dia em que um deles for distribuído, esta seção cobra o módulo
# junto — que é exatamente a resposta à pergunta "o `identidade_do_vpad.py` é
# instalado?": não, e o portão passa a cobrar se a premissa mudar.
#
# O QUE CONTA COMO CHAMADA, e por que a régua é estreita de propósito: só
# posição de COMANDO com nome literal (`bash "${ROOT_DIR}/scripts/X"`) e o
# caminho absoluto de runtime (`/usr/local/lib/hefesto-dualsense4unix/X`, que só
# existe porque o install o cria). Linha de recado é descartada pelo PRIMEIRO
# comando dela (`fail`/`warn`/`info`/`echo`/`printf`/...), e isto foi MEDIDO:
# sem esse descarte, `doctor.sh:461` — um `info` que ENSINA a rodar o rebind à
# mão — virava chamada, e o portão acusava seis falsos só no doctor. Recado
# pode citar script ausente; é o ofício dele.
#
# A GUARDA DE EXISTÊNCIA É A SAÍDA DECLARADA, e ela já era o idioma da casa
# antes desta seção: `doctor.sh:4343` testa `[[ -x "${ROOT_DIR}/scripts/
# disable_steam_input.sh" ]]` antes de chamar, e `bt_health_watchdog.sh:215`
# testa `[[ -x "${_ACTIVE}" ]]`. Quem escreve a guarda está dizendo "sei que
# pode não estar aqui, e tratei" — e o portão acredita. Quem chama sem guarda
# está prometendo que o arquivo existe naquele layout, e essa promessa é o que
# se cobra.
#
# O LIMITE, dito de frente: chamada por variável (`bash "${_dono}"`) não é
# vista, porque o nome não está na linha. Não é buraco por descuido — é a mesma
# escolha da guarda: quem monta o caminho em variável está escolhendo o alvo em
# tempo de execução, e o portão não adivinha shell. O que ele impede é a
# regressão silenciosa: o nome literal de um irmão que ficou para trás.
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
    #: Os nomes que existem em `scripts/`. Um nome citado que NÃO está aqui não é
    #: irmão — é comando do sistema ou arquivo de outro projeto, e cobrar por ele
    #: seria o portão inventando parentesco.
    _carona_existentes="$(find scripts -maxdepth 1 -type f \( -name '*.sh' -o -name '*.py' \) \
        -printf '%f\n' 2>/dev/null | sort)"

    #: O que UM script chama. Ver a régua estreita explicada no cabeçalho: posição
    #: de comando com nome literal, mais o caminho absoluto de runtime; linha de
    #: recado fora. Em Python a pergunta é o `import` de módulo irmão — e ali não
    #: existe guarda: import é incondicional, e é justo que seja cobrado sempre.
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

    #: A guarda de existência, procurada pelo NOME literal numa linha de teste de
    #: arquivo. É por isso que `scripts/doctor.sh::_dono_das_regras_udev` escreve
    #: os dois nomes por extenso, um `[[ -f ]]` cada, em vez de varrer uma lista
    #: numa variável: o que não está escrito, portão nenhum lê.
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

# ---------------------------------------------------------------------------
# SCRIPTS DO PRODUTO × OS FORMATOS (25/08/2026, BG-04)
#
# O DEFEITO, do lado de quem usa: quem instalou por Flatpak, AppImage, Arch,
# Fedora ou Nix apertava "Deixar tudo pronto" ou o botão do microfone e recebia
# "Script do WirePlumber não encontrado" — e o único conselho que a tela dava
# era rodar um `./install.sh` que não existe na máquina de quem não clonou o
# repositório. Medido em 24/08 (SISTEMA-O-VIGIA-VIVO-01, §2.2): UM formato
# levava os scripts, cinco não.
#
# E NENHUM PORTÃO VIA, porque este arquivo declara por escrito que não olha
# para `scripts/` (:8) — a exceção foi escrita para UM nome de unit do hotplug
# e virou cegueira para o diretório inteiro. A seção "irmão sem carona" acima
# responde a pergunta VIZINHA ("o que este script distribuído chama foi
# junto?") e não esta: um script que NENHUM formato distribui não tem irmão a
# cobrar, e some das duas contas.
#
# A ÂNCORA É O CONSUMIDOR, e é isso que impede a lista de envelhecer: quem
# manda aqui é o `src/`, não uma lista escrita à mão neste arquivo. O censo
# abaixo lê do CÓDIGO quem executa script de `scripts/` em runtime — pela
# chamada nomeada (`_find_repo_file("scripts/X.sh")`, `_run_script(...)`) e
# pelo caminho absoluto de instalação — e exige que tudo que ele achar esteja
# na lista. Consumidor novo com script novo reprova até alguém decidir o que
# fazer com ele.
#
# O LIMITE, dito de frente: caminho montado em variável não é visto
# (`cli/cmd_mic.py:93` é `Path(".../scripts") / _SCRIPT_NAME`). É o mesmo
# limite que a seção "irmão sem carona" declara, e pela mesma razão — portão
# não adivinha o valor de uma variável. Aqui ele não abre buraco: o mesmo
# script aparece por nome literal em `emulation_actions.py:1201`. Duas réguas
# independentes é o que revela.
echo "== scripts do produto (o que a janela e o doctor EXECUTAM) × os empacotamentos =="
if [[ ! -d src/hefesto_dualsense4unix || ! -d scripts ]]; then
    echo "[ OK ] scripts do produto: sem src/ (ou sem scripts/) neste checkout — nada a checar"
else
    _prod_faltas=()

    #: A LISTA. Quatro nomes saem do censo do `src/` logo abaixo; o quinto —
    #: `bluez_config.sh` — entra pela REGRA DE PAR que a seção "config do
    #: BlueZ" já cobra: o `doctor.sh` lê a config do BlueZ EXCLUSIVAMENTE por
    #: ele (`doctor.sh:2484`), e pacote que leva o doctor sem ele fica com o
    #: detector CEGO. Está aqui para a falha nomear os cinco de uma vez, não
    #: para inventar regra nova.
    _PRODSCRIPTS=(
        doctor.sh
        bluez_config.sh
        disable_steam_input.sh
        fix_wireplumber_default_source.sh
        install_snd_quirk.sh
    )

    #: O CENSO INDEPENDENTE, lido do `src/` e não desta lista. Duas formas,
    #: porque as duas existem no código: a chamada nomeada e o caminho absoluto
    #: de instalação.
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

    #: A régua ao contrário: nome na lista que já não existe no disco vira
    #: exigência-fantasma, e todo formato passaria a carregar um arquivo morto.
    for _prod_s in "${_PRODSCRIPTS[@]}"; do
        [[ -f "scripts/${_prod_s}" ]] \
            || _prod_faltas+=("scripts/${_prod_s} está em _PRODSCRIPTS e não existe mais no disco — APAGUE-o da lista e dos empacotadores")
    done

    #: `arquivo|o nome do formato na boca de quem usa|o destino que o
    #: consumidor PROCURA`. O destino é conferido uma vez por formato, e não
    #: por arquivo, porque a forma `install -t DIR a.sh b.sh` escreve o
    #: diretório uma vez só.
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

        #: O `.spec` tem uma exigência A MAIS, e ela é do rpmbuild e não deste
        #: portão: arquivo instalado e ausente do `%files` ABORTA o build
        #: inteiro com "Installed (but unpackaged) file(s) found" — a cicatriz
        #: que as fontes do hid-playstation deixaram escrita ali.
        if [[ "${_prod_arq}" == *.spec ]]; then
            _prod_files="$(sed -n '/^%files/,/^%changelog/p' "${_prod_arq}" 2>/dev/null || true)"
            for _prod_s in "${_PRODSCRIPTS[@]}"; do
                grep -qF -- "/scripts/${_prod_s}" <<<"${_prod_files}" \
                    || _prod_faltas+=("${_prod_forma}: ${_prod_s} é instalado no %install e não aparece no %files — o rpmbuild aborta o pacote inteiro")
            done
        fi
    done

    #: A LACUNA DECLARADA — o que esta seção NÃO resolve, escrito para não
    #: virar paisagem. Mesmo molde de `_ARTEFATO_SEM_DONO_HOJE` e de
    #: `_SVG_LACUNAS_HOJE`: declarar é honesto, e o portão não castiga
    #: honestidade — só não deixa a lápide envelhecer calada.
    _PRODSCRIPT_LACUNAS_HOJE=(
        "25/08/2026 — LEVAR NÃO É ACHAR. BASES_DE_INSTALACAO (app/actions/daemon_actions.py) conhece quatro bases: a raiz do checkout, /app/share (Flatpak), /usr/share e /usr/local/share. O Nix instala em \$out/share e as duas receitas de AppImage em \$APPDIR/usr/share, e nenhuma das duas é uma delas — nesses três formatos os arquivos agora VIAJAM e o consumidor ainda não olha para onde caíram. A cura é uma base derivada de sys.prefix, num arquivo que a frente BG-04 não possui."
    )

    #: E a lápide sabe morrer: no dia em que o consumidor derivar uma base de
    #: `sys.prefix`, esta entrada vira mentira e o portão manda apagá-la. Se o
    #: bloco mudar de arquivo (a BG-05 fala em `utils/repo_files.py`), o
    #: `-f` abaixo cala e a lacuna sobrevive um dia a mais — erra para o lado
    #: de guardar, que é o lado certo para uma dívida.
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

# LOADER-SVG-01 (19/08/2026) — o loader SVG do gdk-pixbuf em TODA forma de
# empacotamento.
#
# POR QUE ESTA SEÇÃO NASCEU: a leva de 19/08 pôs o loader nos empacotamentos e a
# conferência foi "rode o check_packaging_parity.sh e veja se os três concordam".
# O portão respondeu VERDE — e estava CEGO: não havia uma linha sobre `librsvg`
# neste arquivo. Verde por silêncio é a pior resposta que um portão dá, porque
# quem perguntou vai embora achando que mediu.
#
# E O SINTOMA NÃO APONTA PARA A CAUSA, que é o motivo de isto virar portão em vez
# de nota: sem o loader, `GdkPixbuf.Pixbuf.new_from_file_at_scale` devolve None
# EM SILÊNCIO — o ícone some da bandeja e os 38 glifos da interface caem junto,
# sem uma linha de erro no log (BUG-TRAY-ICONE-INVISIVEL-01, descrito em
# app/arranque.py). Ninguém liga a tela vazia ao pacote que faltou.
#
# A ÂNCORA É A PROMESSA, não o pacote — mesma disciplina da seção do teclado na
# tela: enquanto o produto DESENHAR SVG em execução, ele tem de declarar o
# loader em todo formato. Se um dia o desenho sair do produto, a seção cala por
# direito (e é isso que a mantém quieta nos checkouts sintéticos dos testes deste
# próprio portão, que trazem só `assets/` e `scripts/`).
_SVG_PROMESSA="src/hefesto_dualsense4unix/gui/widgets/button_glyph.py"
echo "== loader SVG do gdk-pixbuf (o que desenha) × o que cada formato declara =="
if [[ ! -f "${_SVG_PROMESSA}" ]] \
   || ! grep -q 'new_from_file_at_scale' "${_SVG_PROMESSA}" 2>/dev/null; then
    echo "[ OK ] loader SVG: o produto não carrega SVG em execução neste checkout — nada a checar"
else
    missing=()

    #: Formato -> padrão que só o CAMPO LIDO PELO GERENCIADOR satisfaz.
    #:
    #: A LIÇÃO DA SEÇÃO DO TECLADO NA TELA, aplicada de novo: procurar a palavra
    #: `librsvg` no arquivo inteiro passaria VERDE com a dependência arrancada,
    #: porque os quatro arquivos EXPLICAM a armadilha de nome em prosa — e a
    #: `Description:` do debian/control não é comentário, então nem o filtro de
    #: `#` a remove. Cada padrão abaixo mira o campo, e só ele.
    #:
    #: OS NOMES DIVERGEM DE PROPÓSITO, e a divergência é a armadilha: quem
    #: desenha é `librsvg2-common` (Debian), `librsvg2` (Fedora) e `librsvg`
    #: (Arch/Nix). O `librsvg2-bin`/`librsvg2-tools` é o `rsvg-convert`,
    #: ferramenta de BUILD — o errado em todos eles.
    _svg_declaram=(
        "packaging/fedora/hefesto-dualsense4unix.spec:^(Requires|Recommends):[[:space:]]*librsvg2([[:space:]]|$)"
        "packaging/arch/PKGBUILD:^[[:space:]]*'librsvg'"
        "packaging/nix/package.nix:^[[:space:]]*librsvg[[:space:]]*$"
    )
    for _svg_item in "${_svg_declaram[@]}"; do
        _svg_arq="${_svg_item%%:*}"
        _svg_padrao="${_svg_item#*:}"
        [[ -f "${_svg_arq}" ]] || continue
        # CORRIDA-DO-PIPEFAIL-01: here-string, nunca `produtor | grep -q`.
        _svg_codigo="$(grep -v '^[[:space:]]*#' "${_svg_arq}" 2>/dev/null || true)"
        grep -qE "${_svg_padrao}" <<< "${_svg_codigo}" \
            || missing+=("${_svg_arq} não declara o loader SVG no campo que o gerenciador lê (padrão: ${_svg_padrao})")
    done

    # O .deb tem contrato PRÓPRIO, e o motivo é medido: `Depends:` é um campo de
    # CONTINUAÇÃO — o nome do pacote mora numa linha que começa com espaço, e um
    # `^Depends:.*librsvg2-common` nunca casaria. Pior: a palavra também vive na
    # `Description`, cujas linhas TAMBÉM começam com espaço. Então o campo é
    # recortado de verdade (cabeçalho + continuações, até a próxima linha que
    # começa em coluna 0), e é dentro DELE que se procura.
    if [[ -f packaging/debian/control ]]; then
        _svg_campo_deb="$(awk '
            /^(Depends|Recommends|Pre-Depends):/ { dentro = 1; print; next }
            dentro && /^[[:space:]]/ { print; next }
            dentro { dentro = 0 }
        ' packaging/debian/control 2>/dev/null || true)"
        grep -qE '(^|[[:space:],])librsvg2-common([[:space:],]|$)' <<< "${_svg_campo_deb}" \
            || missing+=("packaging/debian/control: librsvg2-common não está em Depends/Recommends (a menção na Description NÃO instala nada)")
    fi

    # O install.sh nativo: o loader tem de estar no CENSO com criticidade
    # `obrigatoria` — e a checagem tem de ser a do EFEITO (`svg`: o gdk-pixbuf lê
    # SVG?), nunca o nome de um pacote. É o que faz a mesma régua valer nas três
    # famílias, e é o que impede a volta do `librsvg2-bin` pelo nome.
    if [[ -f install.sh ]]; then
        _svg_censo="$(grep -v '^[[:space:]]*#' install.sh 2>/dev/null || true)"
        grep -qE '"svg-loader\|obrigatoria\|svg\|' <<< "${_svg_censo}" \
            || missing+=("install.sh: o censo _DEPS_DE_SISTEMA não cobra o svg-loader como obrigatória pela checagem de EFEITO (svg)")
        for _svg_fam in 'librsvg2-common' 'librsvg2"' "librsvg\""; do
            grep -qF -- "${_svg_fam}" <<< "${_svg_censo}" \
                || missing+=("install.sh: _pkg_nome perdeu o nome do loader para uma família (procurado: ${_svg_fam})")
        done
    fi

    # O FLATPAK NÃO DECLARA, e está certo: ele roda sobre `org.gnome.Platform`,
    # que já traz o loader SVG dentro do runtime — é assim que qualquer app GTK
    # desenha ícone simbólico ali, e o próprio manifesto registra que as deps
    # deste tipo "já estão dentro do runtime". O que o portão cobra, então, é a
    # PREMISSA: se um dia o manifesto trocar para um runtime que não a garante
    # (`org.freedesktop.Platform`, por exemplo), a isenção morre junto e alguém
    # tem de declarar o módulo à mão.
    if [[ -f flatpak/io.github.hefesto_team.hefesto_dualsense4unix.yml ]]; then
        _svg_runtime="$(sed -n 's/^runtime:[[:space:]]*//p' flatpak/io.github.hefesto_team.hefesto_dualsense4unix.yml | head -1)"
        if [[ "${_svg_runtime}" != "org.gnome.Platform" ]]; then
            grep -qi 'rsvg' flatpak/io.github.hefesto_team.hefesto_dualsense4unix.yml 2>/dev/null \
                || missing+=("flatpak: runtime '${_svg_runtime}' não é o org.gnome.Platform que garantia o loader SVG, e o manifesto não bundla nenhum — a isenção caducou")
        fi
    fi

    #: A DÍVIDA DECLARADA — `arquivo:razão com data`. Mesmo molde de
    #: `_ARTEFATO_SEM_DONO_HOJE` acima: declarar é honesto, e o portão não
    #: castiga honestidade — só não deixa a lápide envelhecer calada.
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
        echo "       EM SILÊNCIO: o ícone some da bandeja e os 38 glifos da interface"
        echo "       caem junto, sem UMA linha de erro no log. Quem instalar por esse"
        echo "       formato vai ver uma interface quebrada sem nada que a explique."
        echo "       ARMADILHA DE NOME: quem desenha é librsvg2-common (Debian),"
        echo "       librsvg2 (Fedora) e librsvg (Arch/Nix). O librsvg2-bin e o"
        echo "       librsvg2-tools são o rsvg-convert, ferramenta de BUILD — errados."
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
