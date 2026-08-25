#!/usr/bin/env bash
# bt_active_mode.sh — deixa o rádio BR/EDR amigável aos controles da linhagem
# Nintendo (Switch Pro genuíno / 8BitDo modo Switch), curando na RAIZ a
# desconexão sob carga (BT-NINTENDO-ACTIVE-01, 22/07). Root. Idempotente.
# Reversível.
#
# DUAS medidas com ESCOPOS DIFERENTES (BT-SNIFF-PER-OUI-01, 23/07):
#   (1) o NOME é do ADAPTADOR — e serve aos DOIS controles da linhagem: o A/B de
#       23/07 provou que o alias não atrapalha o clone. Vai nos adaptadores que
#       hospedam a linhagem, não em todos (a razão está na seção 1);
#   (2) o NO-SNIFF é POR DISPOSITIVO — só o Pro genuíno. Aplicá-lo como default
#       do adaptador quebrava a probe do 8BitDo (regressão medida; §2).
#
# As duas entraram juntas em fb5e3ad e por isso ficaram acopladas até 23/07.
#
# E as duas valiam para UM adaptador só até 22/08 (N-IGUAL-A-UM-01): ver
# `_adaptadores` e a seção 1.
#
# Pesquisa original
# (docs/process/estudos/2026-07-22-pesquisa-pro-controller-bt-e-lightbar-keepalive.md):
#
# 1) NOME do host prefixado "Nintendo": o Pro Controller LÊ o nome Bluetooth do
#    host e, se não for "Nintendo*", cai num sniff mode frágil que não manda
#    keepalive — sob rumble+IMU os reports enfileiram e o controle desconecta.
#    3 fontes independentes (Fyra Labs, bluez#1797, ArchWiki): renomear o
#    adaptador com prefixo "Nintendo" tira o controle desse modo. Aplicado via
#    Alias do BlueZ (persiste em /var/lib/bluetooth/<adapter>/settings).
#
# 2) LINK POLICY sem SNIFF: complementa o nome no nível HCI — o LM local passa a
#    RECUSAR LMP_sniff_req, forçando modo ativo. Provado ao vivo 22/07: os
#    DualSense seguem conectados normalmente sem sniff.
#     ESCOPO CORRIGIDO em 23/07 (BT-SNIFF-PER-OUI-01): era default do
#    ADAPTADOR e por isso atingia TODO mundo — inclusive o 8BitDo, cuja probe
#    morre sem sniff. Agora é aplicada SÓ por-conexão, no Pro genuíno. Detalhes
#    e o A/B que mediu isso estão na seção 2 do corpo.
#
# Reverter: `hciconfig <hciN> lp rswitch,hold,sniff,park` (VÍRGULA — com
# espaços o hciconfig lê só o primeiro token e a reversão é no-op
# silencioso; medido 23/07) e Alias de volta ao
# hostname (o uninstall faz). Vale a partir do próximo start do bluetoothd/boot;
# este script NUNCA reinicia o serviço.
set -euo pipefail

# GANCHOS DE TESTE — a suíte precisa de uma bancada de mentira com três
# adaptadores, e nenhum teste desta casa pode ler o barramento vivo dela:
#   HEFESTO_SYS_BLUETOOTH   raiz dos adaptadores (default /sys/class/bluetooth)
#   HEFESTO_BT_LIB          raiz da árvore de bonds (default /var/lib/bluetooth)
#   HEFESTO_BT_LOG_DEST     vazio = journal · caminho = arquivo · none = nada
#
# Os dois de CAMINHO morrem sob sudo (mesma contenção do
# `bt_ponte_privilegiada.sh`): o `env_reset` já os apagaria, e esta linha é o
# cinto para a máquina que o desligou. O de LOG fica — ele não muda nada do que
# o script DECIDE, só onde ele escreve o diário, e o uninstall depende dele.
if [[ -n "${SUDO_UID:-}" || -n "${SUDO_USER:-}" ]]; then
    unset HEFESTO_SYS_BLUETOOTH HEFESTO_BT_LIB
fi
SYS_BLUETOOTH="${HEFESTO_SYS_BLUETOOTH:-/sys/class/bluetooth}"
SYS_BLUETOOTH="${SYS_BLUETOOTH%/}"
LIB="${HEFESTO_BT_LIB:-/var/lib/bluetooth}"
LIB="${LIB%/}"

LOG_TAG=hefesto-bt-active
# DIÁRIO-QUE-NAO-MENTE-01 (15/08/2026): vazio = journal (produção); caminho =
# arquivo; `none` = nada. Existe porque a suíte roda estes scripts DE VERDADE e
# sem isto grava, no journal da máquina dela, linhas que descrevem eventos que
# nunca aconteceram. Motivo completo no cabeçalho do bt_bonds_autorestore.sh.
LOG_DEST="${HEFESTO_BT_LOG_DEST:-}"
_registrar() {
    case "${LOG_DEST}" in
        "")   logger -t "${LOG_TAG}" "$*" 2>/dev/null || true ;;
        none) : ;;
        *)    printf '%s %s: %s\n' "$(date -Is 2>/dev/null || true)" "${LOG_TAG}" "$*" \
                  2>/dev/null >>"${LOG_DEST}" || true ;;
    esac
}
log() { _registrar "$*"; [[ "${QUIET:-0}" -eq 1 ]] || printf '%s\n' "$*"; }

if [[ "$(id -u)" -ne 0 ]]; then
    printf 'bt_active_mode.sh: requer root\n' >&2
    exit 1
fi

QUIET=0
[[ "${1:-}" == "--quiet" ]] && QUIET=1

# MIGRACAO-BLUEZ-DEPRECIADOS-01 (19/08/2026): este script SAÍA AQUI quando o
# `hciconfig` não existia — e com isso perdia também a medida (1), o alias
# "Nintendo*", que é a que NÃO precisa dele (sai pelo D-Bus). Numa distro que
# moveu as depreciadas para `bluez-deprecated`, a cura inteira virava no-op com
# um log de uma linha. Agora cada medida é guardada pela ferramenta que ELA usa.
#
# N-IGUAL-A-UM-01 (22/08/2026): esta função devolvia UM adaptador — o primeiro
# do glob, com `return 0` na primeira volta — e o script inteiro respondia pelo
# rádio inteiro a partir dele. Com um dongle isso sempre acertou, e é por isso
# que nunca apareceu. Com os TRÊS desta bancada, MEDIDO: o alias "Nintendo*"
# ficava no `hci0`, que não hospeda Nintendo nenhum, enquanto o Pro vivia no
# `hci1` sem proteção — e a vigia de 2 min reafirmava a escolha errada para
# sempre. Agora é PLURAL, e quem decide o que fazer em cada adaptador é a
# OPERAÇÃO, não a ordem de enumeração (as três razões estão na seção 1).
#
# Fontes, em ordem: sysfs (kernel puro, sem pacote e sem privilégio; o filtro
# `^hci[0-9]+$` descarta as entradas de conexão, que ali nascem como
# "hci0:256"), a árvore do BlueZ no D-Bus — que é de onde sai o objeto usado
# logo abaixo para o Alias —, `btmgmt info` em seguida, e o `hciconfig` como
# plano B. Nenhuma delas corta no primeiro.
_adaptadores() {
    local p nome achou=0
    for p in "${SYS_BLUETOOTH}"/hci*; do
        [[ -e "${p}" ]] || continue
        nome="${p##*/}"
        [[ "${nome}" =~ ^hci[0-9]+$ ]] || continue
        printf '%s\n' "${nome}"
        achou=1
    done
    [[ "${achou}" -eq 1 ]] && return 0
    if command -v busctl >/dev/null 2>&1; then
        nome="$(busctl tree org.bluez --list 2>/dev/null \
            | grep -oE '/org/bluez/hci[0-9]+' | sed 's#.*/##' | sort -u || true)"
        if [[ -n "${nome}" ]]; then printf '%s\n' "${nome}"; return 0; fi
    fi
# BTMGMT-QUE-NAO-VOLTA-01 (19/08/2026): `btmgmt` fala com o kernel pelo socket
# de MANAGEMENT, e sem adaptador ele fica esperando uma resposta que nunca vem —
# não devolve erro, não devolve vazio, não devolve NADA. Medido: o job do Arch
# ficou preso exatamente aqui e só morreu no teto de 30 min do CI, e o mesmo
# aconteceria na máquina de quem instala sem Bluetooth: o install trava para
# sempre, no passo 8 de 11, sem uma linha dizendo por quê.
# O `2>/dev/null` não ajuda (não há erro) e o `|| true` não ajuda (não há saída).
# Só o teto de tempo resolve. Cinco segundos é vinte vezes o que ele leva numa
# máquina sadia — medido: responde em menos de 0,25 s com adaptador de pé.
    if command -v btmgmt >/dev/null 2>&1; then
        nome="$(timeout 5 btmgmt info 2>/dev/null | grep -oE '^hci[0-9]+' | sort -u || true)"
        if [[ -n "${nome}" ]]; then printf '%s\n' "${nome}"; return 0; fi
    fi
    command -v hciconfig >/dev/null 2>&1 || return 0
    hciconfig 2>/dev/null | awk -F: '/^hci/{print $1}' || true
}

# MACs com ACL de pé, MAIÚSCULAS com ':'. Substitui o `hcitool con`: o D-Bus do
# BlueZ responde a mesma pergunta e está vivo; `btmgmt con` é o plano B (a
# ferramenta que a upstream indica), e o `hcitool con` o plano C — ele ainda
# responde com o bluetoothd parado, então não se joga fora quem o tem.
_macs_conectados() {
    local p mac saida="" achou=0
    if command -v busctl >/dev/null 2>&1; then
        while IFS= read -r p; do
            [[ -z "${p}" ]] && continue
            [[ "$(busctl get-property org.bluez "${p}" org.bluez.Device1 Connected 2>/dev/null \
                | tr -d '[:space:]')" == "btrue" ]] || continue
            mac="${p##*/dev_}"
            printf '%s\n' "${mac//_/:}"
            achou=1
        done <<<"$(busctl tree org.bluez --list 2>/dev/null \
            | grep -oE '/org/bluez/hci[0-9]+/dev_[0-9A-Fa-f_]+$' | sort -u || true)"
        [[ "${achou}" -eq 1 ]] && return 0
    fi
    if command -v btmgmt >/dev/null 2>&1; then
        saida="$(timeout 5 btmgmt con 2>/dev/null | grep -oE '([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}' || true)"
        if [[ -n "${saida}" ]]; then printf '%s\n' "${saida^^}"; return 0; fi
    fi
    command -v hcitool >/dev/null 2>&1 || return 0
    saida="$(hcitool con 2>/dev/null | grep -oE '([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}' || true)"
    [[ -n "${saida}" ]] && printf '%s\n' "${saida^^}"
    return 0
}

# A REGRA de "quem faz um adaptador precisar do prefixo" tem UM DONO:
# `src/hefesto_dualsense4unix/core/linhagem_nintendo.py` — `OUIS_CLONE`,
# `OUIS_NINTENDO_VISTAS`, `NOMES_LINHAGEM` e `e_da_linhagem_nintendo`. As duas
# listas abaixo são a MESMA regra escrita em shell, e existem porque este script
# roda no `ExecStartPost` do bluetoothd, como root, antes de qualquer venv da
# casa existir: importar Python aqui é depender de coisa que pode não estar de
# pé no instante em que o Pro conecta.
#
# Cópia PINADA não é cópia solta:
# `tests/unit/test_o_prefixo_vai_no_adaptador_que_hospeda_nintendo.py` lê os dois
# lados e reprova se eles se separarem — inclusive quando o `linhagem_nintendo`
# ganhar uma faixa nova e esta cópia não.
OUIS_LINHAGEM=("e0:f6:b5" "e4:17:d8")
NOMES_LINHAGEM=("pro controller" "nintendo")

# E A OUTRA PERGUNTA, que NÃO é esta: "quem é um PRO GENUÍNO?"
#
# São duas perguntas com duas respostas diferentes para o MESMO aparelho, e
# misturá-las troca o tratamento dos dois controles:
#
#   - LINHAGEM (acima) -> genuíno E clone respondem SIM. É quem lê o nome
#     Bluetooth do host, e por isso decide o PREFIXO do adaptador. O A/B de
#     23/07/2026 mediu que o nome não atrapalha o clone.
#   - PRO GENUÍNO (aqui) -> só o genuíno. É quem recebe o NO-SNIFF, que para o
#     clone é veneno: sem sniff a probe dele morre em `ret=-110`, mesmo A/B.
#
# A resposta vai por NEGATIVA, e é a de `core/linhagem_nintendo.e_pro_genuino`:
# `e4:17:d8` é clone; qualquer outra faixa com cara de Pro é genuíno. A 8BitDo
# tem UMA faixa MA-L registrada e a Nintendo tem 82 (medido contra
# `/usr/share/ieee-data/oui.csv` em 22/08/2026), então a lista fechada que
# funciona é a do clone.
#
# AS LISTAS SE REPETEM NESTE ARQUIVO de propósito, e há portão para isso: a
# `OUIS_LINHAGEM` acima é a UNIÃO das duas de baixo, e
# `tests/unit/test_o_no_sniff_alcanca_todo_pro.py` reprova se elas se separarem
# — aqui dentro ou do dono em `core/linhagem_nintendo.py`. Escrever a união como
# derivação (`("${OUIS_NINTENDO_VISTAS[@]}" ...)`) esconderia os literais do
# portão que já vigia a `OUIS_LINHAGEM`, e um portão cego é pior que uma cópia
# vigiada.
OUIS_CLONE=("e4:17:d8")
OUIS_NINTENDO_VISTAS=("e0:f6:b5")
NOMES_PRO=("pro controller")

#: Teto do alias em BYTES UTF-8, MEDIDO em 22/08/2026 no BlueZ 5.86 desta
#: bancada — o mesmo `TETO_DE_BYTES` de `integrations/apelido_do_dongle.py`.
TETO_DE_BYTES=247

#: Endereço do adaptador (MAIÚSCULO) -> `hciN`. Preenchido pelo D-Bus, porque o
#: sysfs NÃO publica o endereço: `/sys/class/bluetooth/hciN/address` não existe
#: (conferido em 22/08/2026). É o que deixa a árvore de bonds, que fala em
#: endereço, apontar para um adaptador.
declare -A HCI_DE=()

# Este controle lê o nome Bluetooth do host? Genuíno e clone respondem SIM — o
# A/B de 23/07 mediu que o nome não atrapalha o clone; o que atrapalha o clone é
# o no-sniff, que é a outra metade e continua só para o genuíno.
_e_linhagem_nintendo() {  # $1 = MAC do controle · $2 = nome do controle
    local mac="${1,,}" nome="${2,,}" marca
    for marca in "${OUIS_LINHAGEM[@]}"; do
        [[ "${mac}" == "${marca}"* ]] && return 0
    done
    for marca in "${NOMES_LINHAGEM[@]}"; do
        [[ "${nome}" == *"${marca}"* ]] && return 0
    done
    return 1
}

# O nome deste controle, para quem só tem o endereço na mão. Vazio quando não
# há de onde tirar — e vazio NÃO é "não é um Pro": ver `_e_pro_genuino`.
_nome_do_controle() {  # $1 = MAC do controle -> nome, ou vazio
    local mac="${1^^}" alvo caminho nome
    alvo="dev_${mac//:/_}"
    if command -v busctl >/dev/null 2>&1; then
        caminho="$(busctl tree org.bluez --list 2>/dev/null \
            | grep -oE "/org/bluez/hci[0-9]+/${alvo}$" | head -1 || true)"
        if [[ -n "${caminho}" ]]; then
            nome="$(busctl get-property org.bluez "${caminho}" org.bluez.Device1 Alias 2>/dev/null \
                | sed -E 's/^s "?//; s/"?$//' || true)"
            [[ -n "${nome}" ]] && { printf '%s\n' "${nome}"; return 0; }
        fi
    fi
    # Plano B: a árvore de bonds em disco, que é onde o nome fica GRAVADO — o
    # mesmo lugar de onde `_hci_com_nintendo` já o lê quando o bluetoothd ainda
    # está povoando o D-Bus.
    sed -n 's/^Name=//p' "${LIB}"/*/"${mac}"/info 2>/dev/null | head -1 || true
}

# Este controle é um Pro GENUÍNO — o único que recebe o no-sniff? Por NEGATIVA.
#
# A ordem é a mesma do `bt_nosniff_now.sh`, e cada degrau responde uma pergunta
# distinta: faixa de clone conhecida recusa (a recusa É a cura dele); faixa que
# esta casa já viu num aparelho aplica sem consultar nome nenhum (nada que já
# funcionava passa a depender de um dado novo); nome com cara de Pro aplica, e é
# por AQUI que o Pro de outra safra entra.
_e_pro_genuino() {  # $1 = MAC do controle · $2 = nome do controle
    local mac="${1,,}" nome="${2,,}" marca
    for marca in "${OUIS_CLONE[@]}"; do
        [[ "${mac}" == "${marca}"* ]] && return 1
    done
    for marca in "${OUIS_NINTENDO_VISTAS[@]}"; do
        [[ "${mac}" == "${marca}"* ]] && return 0
    done
    for marca in "${NOMES_PRO[@]}"; do
        [[ "${nome}" == *"${marca}"* ]] && return 0
    done
    return 1
}

_prop_adaptador() {  # $1 = hciN · $2 = propriedade de org.bluez.Adapter1
    busctl get-property org.bluez "/org/bluez/$1" org.bluez.Adapter1 "$2" 2>/dev/null \
        | sed -E 's/^s "?//; s/"?$//' || true
}

# Os `hciN` que hospedam a linhagem, um por linha e com repetição — quem chama
# passa por `sort -u`.
_hci_com_nintendo() {
    local caminho mac nome info dir end
    if command -v busctl >/dev/null 2>&1; then
        while IFS= read -r caminho; do
            [[ -n "${caminho}" ]] || continue
            mac="${caminho##*/dev_}"
            mac="${mac//_/:}"
            nome="$(busctl get-property org.bluez "${caminho}" org.bluez.Device1 Alias 2>/dev/null \
                | sed -E 's/^s "?//; s/"?$//' || true)"
            _e_linhagem_nintendo "${mac}" "${nome}" || continue
            caminho="${caminho%/dev_*}"
            printf '%s\n' "${caminho##*/}"
        done <<<"$(busctl tree org.bluez --list 2>/dev/null \
            | grep -oE '/org/bluez/hci[0-9]+/dev_[0-9A-Fa-f_]+$' | sort -u || true)"
    fi
    while IFS= read -r info; do
        [[ -n "${info}" ]] || continue
        dir="${info%/info}"
        mac="${dir##*/}"
        nome="$(sed -n 's/^Name=//p' "${info}" 2>/dev/null | head -1 || true)"
        _e_linhagem_nintendo "${mac}" "${nome}" || continue
        end="${dir%/*}"
        end="${end##*/}"
        [[ -n "${HCI_DE[${end^^}]:-}" ]] && printf '%s\n' "${HCI_DE[${end^^}]}"
    done <<<"$(find "${LIB}" -mindepth 3 -maxdepth 3 -type f -name info 2>/dev/null || true)"
}

mapfile -t ADAPTADORES < <(_adaptadores)
[[ "${#ADAPTADORES[@]}" -eq 0 ]] && { log "nenhum adaptador HCI — nada a fazer"; exit 0; }

# --- 1) NOME "Nintendo*" via Alias do BlueZ (idempotente) --------------------
#
# QUAL OPERAÇÃO VALE PARA QUEM (N-IGUAL-A-UM-01, 22/08/2026). São TRÊS respostas
# diferentes, e cada uma tem a razão dela:
#
#   (1) o alias "Nintendo*" -> SÓ nos adaptadores que hospedam a linhagem. Pôr
#       em todos seria mais simples, e o A/B de 23/07 diz que o nome não
#       atrapalha o clone — mas `integrations/apelido_do_dongle.py` só ESCONDE
#       o prefixo na tela em adaptador COM Nintendo, e nunca subtrai. Num dongle
#       sem Nintendo a palavra vira parte permanente do nome que ela escreveu:
#       "Nintendo Sala", para sempre. Pôr onde não precisa custa mais que não
#       pôr.
#   (2) o SNIFF default -> em TODOS (ver a seção 2). É a devolução do default do
#       kernel, e não existe adaptador para o qual "sniff permitido" seja errado.
#   (3) o no-sniff por-conexão -> já é multi-adaptador de graça: `hcitool lp
#       <MAC>` acha o adaptador da conexão sozinho (`hci_for_each_dev`). MEDIDO
#       em 22/08/2026, com o Pro no `hci1` e o script mirando o `hci0`.
#
# QUEM HOSPEDA O QUÊ — duas fontes unidas, cada uma respondendo o que a outra
# não responde:
#
#   * a árvore do BlueZ no D-Bus dá o `hciN` DIRETO e responde ANTES do link.
#     MEDIDO em 22/08/2026: com o Pro DESLIGADO, o objeto
#     `/org/bluez/hci1/dev_E0_F6_B5_*` continua lá. É o que importa — o Pro lê o
#     nome do host no MOMENTO do link, e prefixo aplicado depois chega tarde;
#   * a árvore de bonds em disco responde com o `bluetoothd` ainda povoando a
#     árvore de objetos, que é exatamente o instante do `ExecStartPost`.
#
# O sysfs vivo (`/sys/class/hidraw/*/device/uevent`), que é a fonte do
# `apelido_do_dongle` na GUI, NÃO entra aqui: tudo o que ele enxerga — controle
# CONECTADO — a árvore do D-Bus já enxerga, e sem um segundo laço. Lá ele é a
# fonte certa porque a GUI não tem root; aqui seria repetição. É a resposta "cada
# um com a sua fonte" da decisão D2 da sprint.
if command -v busctl >/dev/null 2>&1; then
    for HCI in "${ADAPTADORES[@]}"; do
        END="$(_prop_adaptador "${HCI}" Address)"
        [[ -n "${END}" ]] && HCI_DE["${END^^}"]="${HCI}"
    done
    mapfile -t COM_NINTENDO < <(_hci_com_nintendo | sort -u)
    for HCI in ${COM_NINTENDO[@]+"${COM_NINTENDO[@]}"}; do
        ADAPTER_OBJ="/org/bluez/${HCI}"
        ALIAS_ATUAL="$(_prop_adaptador "${HCI}" Alias)"
        [[ -n "${ALIAS_ATUAL}" && "${ALIAS_ATUAL}" != Nintendo* ]] || continue
        NOVO="Nintendo ${ALIAS_ATUAL}"
        # O BlueZ recusa a chamada inteira quando o corte cai no meio de um
        # caractere multibyte (medido; ver `apelido_do_dongle`), e o shell não
        # tem como cortar UTF-8 em fronteira de caractere sem depender de
        # ferramenta que pode não existir no boot. Então aqui não se corta: se
        # não cabe, DIZ que não coube.
        if [[ "$(printf '%s' "${NOVO}" | LC_ALL=C wc -c)" -gt "${TETO_DE_BYTES}" ]]; then
            log "NÃO prefixei o alias de ${HCI}: 'Nintendo ' mais o nome de hoje passa de ${TETO_DE_BYTES} bytes, o teto do BlueZ — encurte o nome do adaptador pela aba do produto e o Pro volta a ficar protegido"
            continue
        fi
        if busctl set-property org.bluez "${ADAPTER_OBJ}" org.bluez.Adapter1 Alias s "${NOVO}" 2>/dev/null; then
            log "alias do adaptador ${HCI} -> '${NOVO}' (tira o Pro do sniff frágil)"
        else
            log "falha ao setar alias de ${HCI} (adaptador não pronto?) — o watchdog re-tenta"
        fi
    done
fi

# --- 2) LINK POLICY sem SNIFF — POR DISPOSITIVO (BT-SNIFF-PER-OUI-01) --------
#
#  Esta medida É por-dispositivo. Aplicá-la como default do ADAPTADOR foi uma
# regressão medida (23/07) — ver o A/B abaixo.
#
# Os dois controles da linhagem Nintendo têm requisitos de firmware
# INCOMPATÍVEIS entre si, e nenhum ajuste global satisfaz os dois:
#
#                        | Pro genuíno (e0:f6:b5) | 8BitDo clone (e4:17:d8)
#   ---------------------|------------------------|------------------------
#   SNIFF permitido      | cai sob carga          | FUNCIONA
#   SNIFF recusado       | ESTÁVEL                | probe morre (-110)
#
# A/B de 23/07 (watchdog parado para não contaminar): com no-sniff global, o
# 8BitDo acumulou 4 probes falhadas e 0 sucessos, sempre em
# `Failed to get joycon info; ret=-110` — o LM local recusa `LMP_sniff_req`, e
# o firmware clone trata a recusa como erro e não completa o handshake de
# subcomando. Devolvido o SNIFF ao adaptador, ele probou em 54 s na primeira
# tentativa e ficou de pé. No mesmo teste o alias "Nintendo" seguiu aplicado —
# ou seja, o NOME não atrapalha o clone; só o no-sniff atrapalha. As duas
# medidas do BT-NINTENDO-ACTIVE-01, que entraram juntas em fb5e3ad e nunca
# tinham sido separadas, ficam separadas aqui.
#
# Por que aplicar DEPOIS do connect basta para o Pro: ele proba bem com sniff
# (era o comportamento antes do fb5e3ad); o que ele não aguenta é a operação
# SUSTENTADA sob carga. O 8BitDo, ao contrário, precisa do sniff justamente na
# janela da probe. O default do adaptador fica então COM sniff (o que o clone
# precisa) e o Pro recebe o tratamento no handle dele, já conectado.
#
# "Só o nome" NÃO é alternativa: medido em 22/07 — com o alias sozinho o Pro
# durou muito mais, "mas sob carga pesada ele ainda caiu. Não é cura completa
# sozinho" (docs/process/estudos/2026-07-22-pesquisa-pro-controller-bt-*).

# SEM SUCESSOR VIVO (MIGRACAO-BLUEZ-DEPRECIADOS-01, 19/08/2026): link policy —
# ler ou escrever, no adaptador ou na conexão — NÃO existe na mgmt API do BlueZ,
# e por isso não existe em `btmgmt` nem em `bluetoothctl` (conferido nos dois
# `--help` do 5.86 desta casa em 19/08/2026). Aqui não há o que migrar: o
# `hciconfig lp` / `hcitool lp` seguem sendo o ÚNICO caminho, e a resposta certa
# quando eles faltam é DIZER que a medida não foi aplicada — não sair calado.

# Default do adaptador: SNIFF PERMITIDO. Se uma versão anterior deixou o
# adaptador sem SNIFF, isto o devolve — é o que destrava o clone.
# ATENÇÃO: a lista vai separada por VÍRGULA; com espaços o hciconfig lê só o
# primeiro token e o comando vira no-op silencioso (medido 23/07).
#
# EM TODOS OS ADAPTADORES, e a razão é diferente da do alias (N-IGUAL-A-UM-01,
# 22/08/2026): isto não escolhe favorecido nenhum, devolve o default do kernel.
# Só age em quem está SEM sniff — e quem ficou sem foi uma versão anterior deste
# script, que mexia em qualquer adaptador que calhasse de ser o primeiro naquele
# boot. O 8BitDo pareia em qualquer um dos três e a probe dele morre em qualquer
# um deles; consertar só o primeiro deixaria o reparo automático sem chegar
# nunca ao adaptador estragado. Não existe adaptador para o qual "sniff
# permitido" seja a resposta errada — o no-sniff é POR CONTROLE desde 23/07.
if ! command -v hciconfig >/dev/null 2>&1; then
    log "NÃO apliquei o SNIFF default de ${ADAPTADORES[*]}: o 'hciconfig' foi depreciado pelo BlueZ e não está nesta máquina, e nenhuma ferramenta viva escreve link policy — instale bluez-deprecated (ou bluez-deprecated-tools). O alias 'Nintendo*' acima segue valendo; o 8BitDo pode não completar a probe se o adaptador estiver sem SNIFF"
else
    for HCI in "${ADAPTADORES[@]}"; do
        if ! hciconfig "${HCI}" lp 2>/dev/null | grep -q 'SNIFF'; then
            hciconfig "${HCI}" lp rswitch,hold,sniff,park 2>/dev/null \
                && log "link policy default de ${HCI} -> RSWITCH,HOLD,SNIFF,PARK (o clone 8BitDo precisa do SNIFF para probar)" \
                || log "falha ao devolver o SNIFF ao default de ${HCI} (adaptador não pronto?)"
        fi
    done
fi

# Por-conexão: no-sniff SÓ no Pro genuíno. Reaplicado a cada tick da vigia 0
# (2 min), o que cobre reconexão sem precisar caçar a borda. Quem está
# conectado sai do D-Bus (`_macs_conectados`); só o ATO de mudar a policy
# depende do `hcitool`.
#
# QUEM É "O PRO GENUÍNO" DEIXOU DE SER UMA FAIXA (UMA-FAIXA-NÃO-É-UM-FABRICANTE-01
# / E1, 25/08/2026). Até esta data a linha aqui era
# `[[ "${MAC^^}" != "${OUI_NINTENDO_REAL}"* ]] && continue`, e aquela constante
# guardava a faixa do Pro DESTA bancada, promovida a definição de "Pro". Quem tem
# um Pro de outra safra ficava com o link caindo sob carga a cada sessão de
# quatro jogadores, e o `doctor` aprovando a cura.
#
# A FAIXA NÃO SE ESCREVE AQUI, nem como exemplo: um portão desta casa procurava
# a declaração dela por regex, e o comentário que a citasse por inteiro faria o
# portão passar verde lendo um COMENTÁRIO — que é a cicatriz
# "o portão pode olhar para o lugar errado" (16/08/2026), aplicada a si mesma.
#
# FATO ERRADO, SUBSTITUÍDO: o comentário daquela constante dizia ser a "mesma
# fonte da verdade" do `NINTENDO_REAL_OUI` do `external_identity.py`. Aquele
# módulo parou de decidir por ela em 22/08 (passou a chamar `e_pro_genuino`), e a
# frase ficou descrevendo uma comunhão que não existia mais.
#
# ESTE LAÇO É SILENCIOSO QUANDO RECUSA, e isso é decisão, não descuido: ele roda
# a cada 2 minutos, e uma linha de journal por recusa seriam ~720 por dia por
# controle. Quem DIZ o motivo, uma vez por connect, é o `bt_nosniff_now.sh` na
# borda — o lugar onde a informação é nova.
while read -r MAC; do
    [[ -z "${MAC}" ]] && continue
    _e_pro_genuino "${MAC}" "$(_nome_do_controle "${MAC}")" || continue
    if ! command -v hcitool >/dev/null 2>&1; then
        log "Pro genuíno ${MAC} conectado e NÃO consegui tirá-lo do SNIFF: o 'hcitool' foi depreciado pelo BlueZ e não está nesta máquina (pacote bluez-deprecated / bluez-deprecated-tools), e a mgmt API não escreve link policy. Ele vai cair sob carga até isso ser resolvido"
        continue
    fi
    hcitool lp "${MAC}" RSWITCH >/dev/null 2>&1 \
        && log "link policy de ${MAC} -> RSWITCH (sem SNIFF; Pro genuíno)" || true
done <<<"$(_macs_conectados)"

exit 0
