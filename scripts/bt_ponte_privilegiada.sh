#!/usr/bin/env bash
# bt_ponte_privilegiada.sh — a ponte privilegiada do Bluetooth.
#
# As ÚNICAS operações de root que a janela precisa para mover um controle de um
# adaptador para outro. Cada verbo tem a entrada validada ANTES de tocar em
# qualquer coisa, e NÃO EXISTE verbo que execute comando arbitrário.
#
# POR QUE EXISTE (decisão dela, 22/08/2026)
#
#   "a ideia é que usemos o sudo só na hora do install e isso vai valer sempre
#    no nosso app. não tem como não usar se tratando de bt. zero problemas."
#
# O gesto de migrar um controle está no GUIA-RADIO-DA-SALA.md §6.3, e uma das
# suas cinco linhas exige root:
#
#     rm -f /var/lib/bluetooth/*/cache/<MAC_CONTROLE>
#
# Esse `rm` NÃO é zelo: é o SDP-CACHE-01 que o `scripts/doctor.sh` documenta.
# Sem apagar, o pareamento novo nasce com o registro SDP vazio, o BlueZ recusa a
# reconexão como *unknown device*, o link cai sozinho e parece defeito do
# controle. Um botão de "mover controle" que não apaga o cache entrega um
# controle quebrado — por isso o cache entra no MESMO verbo do esquecimento, e
# não como passo separado que alguém pode pular.
#
# COMO A JANELA CHAMA SEM PEDIR SENHA — e por que `sudoers.d`
#
# O `install.sh` grava `/etc/sudoers.d/49-hefesto-bt-ponte` com NOPASSWD
# restrito a ESTE caminho absoluto e a FORMAS DE ARGUMENTO fixas (o verbo
# `regra-sudo` abaixo é o dono único desse texto — verbo novo entra na regra
# sozinho, e é impossível a regra ficar mais larga que a lista de verbos).
#
# O preço de cada alternativa, medido contra o que este projeto já tem:
#
#   - polkit/pkexec — precisa de um AGENTE de autorização vivo na sessão.
#     `install-host-udev.sh` já usa pkexec, mas em tempo de INSTALAÇÃO, onde
#     pedir senha é aceitável. Em tempo de USO seria preciso
#     `<allow_active>yes</allow_active>`, que concede a QUALQUER sessão local
#     ativa — mais largo que uma usuária nomeada — e ainda assim quebra em
#     sessão sem agente (gamescope, tty, WM mínimo), que é público real deste
#     projeto. A superfície de argumento seria exatamente a mesma;
#   - unit systemd + `systemctl start` — o `systemctl start` de usuária comum
#     passa por polkit de qualquer jeito (mesma dependência), unit não recebe
#     argumento livre (seria unit template com o MAC no nome da instância, e
#     escape de `:` em nome de unit) e a saída não volta para quem chamou;
#   - daemon privilegiado com socket (molde do `hefesto-hidraw-broker`) — é o
#     desenho mais robusto e o único que não depende de pilha de terceiros, mas
#     é um serviço root VIVO O TEMPO TODO e um protocolo de IPC novo. Para
#     seis verbos, o custo não se paga HOJE. Se a lista crescer, é para cá que
#     ela deve migrar;
#   - `sudoers.d` estreito — sem daemon novo, sem polkit, funciona em toda
#     sessão (inclusive tty), e o próprio `install.sh` valida o arquivo com
#     `visudo -c` antes de gravá-lo (sudoers inválido derruba o sudo da máquina
#     inteira). O preço honesto: é uma concessão REAL de root para aquelas
#     linhas de comando. As três contenções que a pagam estão abaixo.
#
# AS TRÊS CONTENÇÕES (não relaxar)
#
#   1. FORMA DE ARGUMENTO EM DOIS LUGARES. A regra do sudoers só casa MAC com
#      classes de caractere explícitas (`[0-9A-Fa-f][0-9A-Fa-f]\:...`), sem
#      nenhum `*`; e este script revalida tudo com regex. Uma das duas falhando
#      ainda deixa a outra de pé;
#   2. NOME NOVO VEM PELO STDIN, NUNCA POR ARGV. É o único dado de forma livre
#      do produto. Pelo stdin, a linha de comando permitida pelo sudoers fica
#      COMPLETAMENTE fechada — nenhum argumento livre para casar;
#   3. OS GANCHOS DE TESTE MORREM SOB SUDO. `HEFESTO_BT_LIB`,
#      `HEFESTO_PONTE_DRY_RUN` e `HEFESTO_BT_LOG_DEST` são apagados quando
#      `SUDO_UID` está no ambiente. O `Defaults env_reset` do sudo já faria
#      isso, mas quem o desligou não pode ganhar de brinde um `rm` como root em
#      raiz escolhida por ele.
#
# OS VERBOS (a lista é curta de propósito)
#
#   adaptadores                          lista MAC, alias, ligado e hciN
#   bonds      <MAC_ADAPTADOR>           lista os controles pareados naquele
#   renomear   <MAC_ADAPTADOR>           alias novo pelo STDIN (1 linha)
#   esquecer   <MAC_ADAPTADOR> <MAC_CTRL>  remove o bond E o cache SDP
#   descobrir  <MAC_ADAPTADOR> <SEG>     janela de busca (BLOQUEIA <SEG>) e,
#                                        enquanto ela vive, os candidatos
#   parear     <MAC_ADAPTADOR> <MAC_CTRL>  Pair() + Trusted=true
#   desconectar <MAC_ADAPTADOR> <MAC_CTRL> derruba o LINK (o controle zumbi)
#   regra-sudo <USUARIA>                 imprime o /etc/sudoers.d (não instala)
#
# SAÍDA: dado em TSV no stdout, uma linha por item; erro no stderr.
#   adaptadores -> MAC \t ALIAS \t ligado|desligado \t hciN
#   bonds       -> MAC \t NOME \t com-chave|sem-chave
#   descobrir   -> MAC \t NOME \t novo|pareado \t CLASSE
# A CLASSE é o `Class` do BlueZ em decimal (a *class of device* do
# Bluetooth), e sai crua de propósito: quem decide se um candidato é
# controle é quem chama, não esta ponte. Vazia quando o BlueZ não a
# publica — um aparelho só-LE não tem classe, e inventar uma seria pior
# que a coluna vazia. Medido na mesa dela em 20/09/2026: os seis objetos
# de DualSense do BlueZ respondem `u 9480` (0x2508).
# Alias e nome são higienizados (controle/tab/quebra viram espaço) porque vêm
# do BlueZ, não de nós.
#
# CÓDIGOS DE SAÍDA: 0 sucesso · 1 falha operacional · 2 uso/entrada inválida.
#
# O ALIAS É ESCRITO LITERALMENTE, e isso é decisão dela (#5 de 22/08/2026: "o
# nome do dongle é dela; o prefixo funcional é do produto"). O prefixo
# "Nintendo " é posto pelo `bt_active_mode.sh` a cada tick do watchdog, nos
# adaptadores que HOSPEDAM a linhagem Nintendo — era "no PRIMEIRO adaptador"
# até 22/08/2026, e essa é a cura N-IGUAL-A-UM-01/E2. Quem desenha a tela
# mostra o nome SEM o prefixo, e não tenta impedi-lo aqui.
#
# GANCHOS DE TESTE (inertes sob sudo, ver contenção 3):
#   HEFESTO_BT_LIB          raiz da árvore do BlueZ (default /var/lib/bluetooth)
#   HEFESTO_PONTE_DRY_RUN=1 não muda nada; imprime o que faria (= --dry-run)
#   HEFESTO_BT_LOG_DEST     vazio = journal · caminho = arquivo · none = nada
#   HEFESTO_BT_BIN          pasta posta NA FRENTE do PATH: `busctl`,
#                           `bluetoothctl` e `hcitool` saem dela, não do
#                           sistema. É o que torna a lista de candidatos
#                           medível sem abrir varredura no rádio dela.
set -euo pipefail

#: Sob sudo os ganchos não existem. O `env_reset` do sudo já os apagaria; esta
#: linha é o cinto para a máquina que o desligou (contenção 3 do cabeçalho).
if [[ -n "${SUDO_UID:-}" || -n "${SUDO_USER:-}" ]]; then
    unset HEFESTO_BT_LIB HEFESTO_PONTE_DRY_RUN HEFESTO_BT_LOG_DEST HEFESTO_BT_BIN
fi

#: `%/` normaliza a barra final: sem isso, uma raiz de teste terminada em
#: `/` faria a guarda de forma de `_apagar` recusar todo caminho legítimo.
LIB="${HEFESTO_BT_LIB:-/var/lib/bluetooth}"
LIB="${LIB%/}"
LIB_REAL="/var/lib/bluetooth"
ALVO_INSTALADO="/usr/local/lib/hefesto-dualsense4unix/bt_ponte_privilegiada.sh"
SECOS="${HEFESTO_PONTE_DRY_RUN:-0}"

#: BARRAMENTO DE MENTIRA. Com esta pasta na frente do PATH, o `busctl` e o
#: `bluetoothctl` que este script chama são os DELA — os da pasta —, e não os
#: do sistema. Existe por uma razão só: a lista de candidatos do `descobrir`
#: só se mede abrindo uma varredura, e abrir varredura na máquina dela custa
#: 32-43% dos pacotes do adaptador com quatro controles de pé. Inerte sob
#: sudo, como os outros três ganchos (contenção 3 do cabeçalho).
BIN_DE_TESTE="${HEFESTO_BT_BIN:-}"
if [[ -n "${BIN_DE_TESTE}" ]]; then
    PATH="${BIN_DE_TESTE}:${PATH}"
    export PATH
fi

#: Teto da janela de busca. Existe porque o processo BLOQUEIA por esse tempo com
#: privilégio de root — janela sem teto é root parado para sempre.
SEGUNDOS_MAX=120

# DIÁRIO-QUE-NAO-MENTE-01 (15/08/2026): vazio = journal (produção); caminho =
# arquivo; `none` = nada. Existe porque a suíte roda estes scripts DE VERDADE e
# sem isto grava, no journal da máquina dela, linhas que descrevem eventos que
# nunca aconteceram.
LOG_TAG=hefesto-bt-ponte
LOG_DEST="${HEFESTO_BT_LOG_DEST:-}"
_registrar() {
    case "${LOG_DEST}" in
        "")   logger -t "${LOG_TAG}" "$*" 2>/dev/null || true ;;
        none) : ;;
        *)    printf '%s %s: %s\n' "$(date -Is 2>/dev/null || true)" "${LOG_TAG}" "$*" \
                  2>/dev/null >>"${LOG_DEST}" || true ;;
    esac
}

_erro() { printf '%s: %s\n' "${0##*/}" "$*" >&2; }

#: Uso/entrada inválida sai com 2 — código distinto de falha operacional, para
#: a janela saber que o problema é dela e não do rádio.
_recusar() { _erro "$*"; exit 2; }

_uso() {
    cat >&2 <<'FIM'
uso: bt_ponte_privilegiada.sh <verbo> [argumentos]

  adaptadores
  bonds      <MAC_ADAPTADOR>
  renomear   <MAC_ADAPTADOR>            (o nome novo vem pelo STDIN, 1 linha)
  esquecer   <MAC_ADAPTADOR> <MAC_CONTROLE>
  descobrir  <MAC_ADAPTADOR> <SEGUNDOS>
  parear     <MAC_ADAPTADOR> <MAC_CONTROLE>
  desconectar <MAC_ADAPTADOR> <MAC_CONTROLE>
  regra-sudo <USUARIA>

  --dry-run como PRIMEIRO argumento: não muda nada, imprime o que faria.
FIM
    exit 2
}

# --- validação de entrada ---------------------------------------------------
#
# Toda a segurança deste script mora nestas três funções. Elas rodam ANTES de
# qualquer efeito, e nenhum caminho de execução as pula.

#: AS VALIDAÇÕES DEVOLVEM PELA GLOBAL `VALIDADO`, NÃO PELO STDOUT — e isso é o
#: contrário do idioma normal da casa, de propósito. `x="$(_mac "$1")"` roda a
#: função numa SUBSHELL, e o `exit 2` da recusa mataria só a subshell: o script
#: seguiria com a variável VAZIA e a entrada suja apenas... sumida. Um portão
#: que recusa dentro de `$( )` não é portão. Escrito assim, a recusa acontece no
#: shell principal e o processo morre de verdade.
VALIDADO=""

#: MAC e nada mais. Note que a forma exclui, por construção, `..`, `/`, `;`,
#: `$(`, espaço e byte de controle — não há denylist a manter atualizada.
_MAC_FORMA='^[0-9A-Fa-f]{2}(:[0-9A-Fa-f]{2}){5}$'

_mac() {
    local valor="${1:-}" papel="${2:-MAC}"
    [[ -n "${valor}" ]] || _recusar "${papel} ausente"
    [[ "${valor}" =~ ${_MAC_FORMA} ]] \
        || _recusar "${papel} inválido: esperava aa:bb:cc:dd:ee:ff, recebi '${valor}'"
    VALIDADO="${valor^^}"
}

_segundos() {
    local valor="${1:-}"
    [[ "${valor}" =~ ^[0-9]{1,3}$ ]] \
        || _recusar "segundos inválido: esperava 1 a ${SEGUNDOS_MAX}, recebi '${valor}'"
    #: 10#: sem isto, "08" seria octal e o teste de faixa explodiria.
    (( 10#${valor} >= 1 && 10#${valor} <= SEGUNDOS_MAX )) \
        || _recusar "segundos fora da faixa: 1 a ${SEGUNDOS_MAX}, recebi '${valor}'"
    VALIDADO="$((10#${valor}))"
}

_usuaria() {
    local valor="${1:-}"
    #: Faixa portável de nome de usuária POSIX. Maiúscula e ponto entram
    #: porque existem em distro real; `/`, espaço, `;` e `=` NÃO, que é o
    #: que impediria alguém de contrabandear uma segunda regra para dentro
    #: do arquivo do sudoers.
    [[ "${valor}" =~ ^[A-Za-z_][A-Za-z0-9._-]{0,31}$ ]] \
        || _recusar "nome de usuária inválido: '${valor}'"
    #: `ALL` PASSA na forma acima e NÃO é um nome: é a palavra reservada do
    #: sudoers para "todo mundo". `regra-sudo ALL` escreveria
    #: `ALL ALL=(root) NOPASSWD: ...` e entregaria a ponte à máquina inteira,
    #: com o arquivo ainda passando limpo no `visudo -c`. Achado desta suíte.
    [[ "${valor}" != "ALL" ]] \
        || _recusar "'ALL' é palavra reservada do sudoers (concederia a TODO MUNDO), não um nome de usuária"
    VALIDADO="${valor}"
}

#: O nome novo do adaptador — o ÚNICO dado de forma livre, e por isso o único
#: que vem pelo stdin (contenção 2). A régua é ALLOWLIST, e é feita por
#: subtração para não depender de locale: tira os permitidos ASCII, tira os
#: bytes >= 0x80 (acentuação em UTF-8, que ela usa), e o que sobrar reprova.
#: Uma allowlist com `[[:alnum:]]` mudaria de significado entre LC_ALL=C e
#: pt_BR.UTF-8 — e sob sudo o locale é justamente o que o env_reset apaga.
_nome_do_stdin() {
    local nome resto
    #: -t: root parado para sempre esperando stdin que não vem é falha de
    #: disponibilidade com privilégio; 10 s é folga de sobra para um pipe.
    IFS= read -r -t 10 nome || _recusar "nome novo não veio pelo stdin"
    [[ -n "${nome}" ]] || _recusar "nome novo vazio"
    (( ${#nome} <= 64 )) || _recusar "nome novo longo demais (máximo 64)"
    [[ "${nome}" != " "* && "${nome}" != *" " ]] \
        || _recusar "nome novo não pode começar nem terminar com espaço"
    if [[ "${nome}" =~ [[:cntrl:]] ]]; then
        _recusar "nome novo tem caractere de controle"
    fi
    resto="${nome//[A-Za-z0-9 ._#+()-]/}"
    resto="$(LC_ALL=C printf '%s' "${resto}" | tr -d '\200-\377')"
    [[ -z "${resto}" ]] \
        || _recusar "nome novo tem caractere proibido: '${resto}'"
    VALIDADO="${nome}"
}

# --- utilidades -------------------------------------------------------------

#: Tudo o que vem do BlueZ passa por aqui antes de virar linha de TSV: alias e
#: nome de dispositivo são texto de terceiro, e um `\t` neles quebraria o
#: contrato de saída de quem nos lê.
_higienizar() {
    printf '%s' "${1:-}" | tr '\t\n\r' '   ' | tr -d '\000-\037\177'
}

_exige_root() {
    #: Root só é exigido contra a árvore REAL (700 do root). Com a raiz de
    #: teste apontando para outro lugar, root não acrescenta nada — e exigi-lo
    #: tornaria a lógica não-testável. Mesmo idioma do bt_bonds_snapshot.sh.
    [[ "${LIB}" == "${LIB_REAL}" ]] || return 0
    [[ "$(id -u)" -eq 0 ]] || { _erro "'$1' requer root (é a ponte privilegiada)"; exit 1; }
}

_seco() { [[ "${SECOS}" == "1" ]]; }

_dizer_seco() { printf '[dry-run] %s\n' "$*"; }

#: `dev_AA_BB_...` — a forma que o BlueZ usa no caminho de objeto D-Bus.
_no_do_dispositivo() { printf 'dev_%s\n' "${1//:/_}"; }

#: MAC do adaptador -> hciN. Vazio (e retorno 1) quando o dongle não está
#: plugado — e isso é caso NORMAL: migrar um controle de um dongle que saiu da
#: mesa é exatamente o que o verbo `esquecer` precisa saber fazer.
_hci_do_mac() {
    local alvo="$1" caminho hci endereco
    #: RAIZ DE TESTE NÃO FALA COM O BARRAMENTO REAL. A suíte roda estes scripts
    #: DE VERDADE, na máquina dela, com quatro DualSense e um Pro no rádio — e
    #: `renomear`/`descobrir`/`parear` MEXEM no adaptador. Sem esta linha,
    #: bastaria um MAC de teste coincidir com um adaptador vivo para um portão
    #: derrubar a mesa dela. Mesma razão do gancho de raiz do bt_bonds_snapshot.
    #: E `HEFESTO_BT_BIN` abre a exceção, que é segura POR CONSTRUÇÃO: com ele
    #: o `busctl` da linha seguinte é o da pasta de teste, então o barramento
    #: que responde não é o dela. Sem ele, a guarda acima continua inteira.
    [[ "${LIB}" == "${LIB_REAL}" || -n "${BIN_DE_TESTE}" ]] || return 1
    command -v busctl >/dev/null 2>&1 || return 1
    while read -r caminho; do
        [[ -n "${caminho}" ]] || continue
        hci="${caminho##*/}"
        endereco="$(busctl get-property org.bluez "${caminho}" org.bluez.Adapter1 Address 2>/dev/null \
            | sed -E 's/^s "?//; s/"?$//' || true)"
        if [[ "${endereco^^}" == "${alvo}" ]]; then
            printf '%s\n' "${hci}"
            return 0
        fi
    done <<<"$(busctl tree org.bluez --list 2>/dev/null \
        | grep -oE '^/org/bluez/hci[0-9]+$' | sort -u || true)"
    return 1
}

# --- verbos -----------------------------------------------------------------

verbo_adaptadores() {
    local caminho hci endereco apelido ligado achou=0
    if command -v busctl >/dev/null 2>&1; then
        while read -r caminho; do
            [[ -n "${caminho}" ]] || continue
            hci="${caminho##*/}"
            endereco="$(busctl get-property org.bluez "${caminho}" org.bluez.Adapter1 Address 2>/dev/null \
                | sed -E 's/^s "?//; s/"?$//' || true)"
            [[ -n "${endereco}" ]] || continue
            apelido="$(busctl get-property org.bluez "${caminho}" org.bluez.Adapter1 Alias 2>/dev/null \
                | sed -E 's/^s "?//; s/"?$//' || true)"
            ligado="$(busctl get-property org.bluez "${caminho}" org.bluez.Adapter1 Powered 2>/dev/null \
                | sed -E 's/^b //' || true)"
            printf '%s\t%s\t%s\t%s\n' "${endereco^^}" "$(_higienizar "${apelido}")" \
                "$([[ "${ligado}" == "true" ]] && printf 'ligado' || printf 'desligado')" "${hci}"
            achou=1
        done <<<"$(busctl tree org.bluez --list 2>/dev/null \
            | grep -oE '^/org/bluez/hci[0-9]+$' | sort -u || true)"
    fi
    [[ "${achou}" -eq 1 ]] && return 0
    #: Degrau do meio: sysfs é kernel puro, não precisa de pacote nem de
    #: privilégio, e responde mesmo com o bluetoothd fora do ar. Sem D-Bus não
    #: existe Alias — a coluna sai vazia, que é honesto.
    for caminho in "${HEFESTO_SYSFS_BLUETOOTH:-/sys/class/bluetooth}"/hci*; do
        [[ -e "${caminho}" ]] || continue
        hci="${caminho##*/}"
        [[ "${hci}" =~ ^hci[0-9]+$ ]] || continue
        endereco="$(cat "${caminho}/address" 2>/dev/null || true)"
        [[ -n "${endereco}" ]] || continue
        printf '%s\t\t%s\t%s\n' "${endereco^^}" "desconhecido" "${hci}"
        achou=1
    done
    [[ "${achou}" -eq 1 ]] && return 0
    #: DEGRAU DE BAIXO, E ELE NÃO É REDUNDANTE — o do meio NÃO RESPONDE NESTE
    #: KERNEL. Medido em 20/09/2026, kernel 7.1.5: `/sys/class/bluetooth/hci0/`
    #: tem `device`, `power`, `reset`, `rfkill0`, `subsystem` e `uevent`, e
    #: **nenhum `address`**. Sem este degrau, uma máquina sem D-Bus responderia
    #: "nenhum adaptador" com três dongles plugados.
    if command -v hcitool >/dev/null 2>&1; then
        while read -r hci endereco; do
            [[ "${hci}" =~ ^hci[0-9]+$ ]] || continue
            [[ "${endereco}" =~ ${_MAC_FORMA} ]] || continue
            printf '%s\t\t%s\t%s\n' "${endereco^^}" "desconhecido" "${hci}"
        done <<<"$(LC_ALL=C hcitool dev 2>/dev/null | tail -n +2 || true)"
    fi
    return 0
}

verbo_bonds() {
    local adaptador="$1" pasta alvo nome chave
    _exige_root bonds
    pasta="${LIB}/${adaptador}"
    [[ -d "${pasta}" ]] || { _erro "adaptador ${adaptador} não tem árvore em ${LIB}"; exit 1; }
    for alvo in "${pasta}"/*; do
        [[ -d "${alvo}" ]] || continue
        [[ "${alvo##*/}" =~ ${_MAC_FORMA} ]] || continue
        [[ -f "${alvo}/info" ]] || continue
        nome="$(sed -n 's/^Name=//p' "${alvo}/info" 2>/dev/null | head -1 || true)"
        chave='sem-chave'
        grep -q '^\[LinkKey\]' "${alvo}/info" 2>/dev/null && chave='com-chave'
        printf '%s\t%s\t%s\n' "${alvo##*/}" "$(_higienizar "${nome}")" "${chave}"
    done
    return 0
}

verbo_renomear() {
    local adaptador="$1" nome hci
    #: A recusa do nome tem de matar o PROCESSO, não uma subshell — por isso a
    #: função devolve pela global (ver o comentário de `VALIDADO`).
    _nome_do_stdin
    nome="${VALIDADO}"
    hci="$(_hci_do_mac "${adaptador}" || true)"
    [[ -n "${hci}" ]] || { _erro "adaptador ${adaptador} não está na mesa (plugado e ligado?)"; exit 1; }
    if _seco; then
        _dizer_seco "busctl set-property org.bluez /org/bluez/${hci} org.bluez.Adapter1 Alias s <${nome}>"
        return 0
    fi
    if busctl set-property org.bluez "/org/bluez/${hci}" org.bluez.Adapter1 Alias s "${nome}" 2>/dev/null; then
        _registrar "adaptador ${adaptador} (${hci}) renomeado"
        return 0
    fi
    _erro "não consegui escrever o alias de ${adaptador} (${hci})"
    exit 1
}

#: O verbo que paga o script. Faz o §6.3 do guia inteiro do lado de SAÍDA: tira
#: o bond E o cache SDP, na mesma execução, para que ninguém possa fazer meio
#: gesto e culpar o controle depois (SDP-CACHE-01).
verbo_esquecer() {
    local adaptador="$1" controle="$2" hci no pasta_bond pasta_adap
    _exige_root esquecer
    hci="$(_hci_do_mac "${adaptador}" || true)"
    no="$(_no_do_dispositivo "${controle}")"
    if [[ -n "${hci}" ]]; then
        if _seco; then
            _dizer_seco "busctl call org.bluez /org/bluez/${hci} org.bluez.Adapter1 RemoveDevice o /org/bluez/${hci}/${no}"
        else
            busctl call org.bluez "/org/bluez/${hci}" org.bluez.Adapter1 \
                RemoveDevice o "/org/bluez/${hci}/${no}" >/dev/null 2>&1 || true
        fi
    fi
    #: O RemoveDevice acima já apaga a pasta do bond — mas SÓ quando o dongle
    #: está plugado. Com o dongle fora da mesa (o caso de quem está justamente
    #: reorganizando o rack) o bond em disco sobrevive, e o controle voltaria a
    #: reconectar nele no próximo plug. Daí a remoção em disco também.
    pasta_bond="${LIB}/${adaptador}/${controle}"
    _apagar "${pasta_bond}" "bond"
    #: O cache SDP sai de TODOS os adaptadores, como no §6.3 do guia: o dongue
    #: de DESTINO também pode ter uma entrada velha desse controle, de um scan
    #: anterior, e é ela que faria o pareamento novo nascer com SDP vazio.
    for pasta_adap in "${LIB}"/*; do
        [[ -d "${pasta_adap}" ]] || continue
        [[ "${pasta_adap##*/}" =~ ${_MAC_FORMA} ]] || continue
        _apagar "${pasta_adap}/cache/${controle}" "cache SDP"
    done
    _seco || _registrar "controle ${controle} esquecido do adaptador ${adaptador} (bond + cache SDP)"
    return 0
}

#: Guarda de forma para TODA remoção: só apaga caminho que é EXATAMENTE
#: <LIB>/<MAC>/<MAC> ou <LIB>/<MAC>/cache/<MAC>. As duas pontas já vieram
#: validadas por `_mac`, então esta função é redundante de propósito — é a
#: segunda tranca, para o dia em que alguém acrescentar um caminho novo aqui
#: sem passar pela validação.
_apagar() {
    local caminho="$1" rotulo="$2" relativo
    [[ -e "${caminho}" ]] || return 0
    relativo="${caminho#"${LIB}/"}"
    if [[ ! "${relativo}" =~ ^[0-9A-Fa-f]{2}(:[0-9A-Fa-f]{2}){5}/(cache/)?[0-9A-Fa-f]{2}(:[0-9A-Fa-f]{2}){5}$ ]]; then
        _erro "recusando apagar caminho fora da forma esperada: ${caminho}"
        exit 1
    fi
    if _seco; then
        _dizer_seco "apagaria ${rotulo}: ${caminho}"
        return 0
    fi
    rm -rf -- "${caminho}"
}

#: FECHAR A JANELA É PARTE DO GESTO, e não higiene. Se este processo morrer sem
#: derrubar o `bluetoothctl` que está atrás, a varredura continua de pé no
#: adaptador DELA por até <segundos> — e varredura no próprio adaptador custa de
#: 32% a 43% dos pacotes, com quatro controles em cima. Quem fecha a tela tem de
#: fechar o rádio junto, inclusive quando quem fecha é um sinal.
#:
#: Os três moram em global porque um `trap` não enxerga `local` de função.
BUSCA_PID=""
BUSCA_ROTEIRO=""
BUSCA_JAVISTOS=""

_fechar_a_busca() {
    if [[ -n "${BUSCA_PID}" ]]; then
        kill "${BUSCA_PID}" 2>/dev/null || true
        BUSCA_PID=""
    fi
    [[ -n "${BUSCA_ROTEIRO}" ]] && rm -f -- "${BUSCA_ROTEIRO}"
    [[ -n "${BUSCA_JAVISTOS}" ]] && rm -f -- "${BUSCA_JAVISTOS}"
    return 0
}

#: OS CANDIDATOS QUE AINDA NÃO SAÍRAM — uma linha de TSV por aparelho novo.
#:
#: PONTE-SEM-CHAMADOR-01 (20/09/2026). Até hoje o `descobrir` abria a janela e
#: **não devolvia nada**: quem chamasse ficava com um adaptador varrendo e
#: nenhuma lista para escolher. Sem a lista, o `parear` só serve a quem já sabe
#: o endereço de cor — que é exatamente a pessoa que não precisa de botão.
#:
#: O ARQUIVO DE JÁ-VISTOS É O QUE FAZ A SAÍDA SER UM FLUXO, e é isso que
#: resolve o segundo risco da sprint: o `parear` tem de correr DENTRO da janela
#: que este verbo abriu, e só há como chamá-lo dentro dela se o endereço sair
#: ANTES de a janela fechar. Uma lista impressa no fim mandaria quem chama
#: parear contra um objeto que o BlueZ já pode ter recolhido.
_candidatos_novos() {
    local hci="$1" javistos="$2" caminho endereco nome pareado classe
    while read -r caminho; do
        [[ -n "${caminho}" ]] || continue
        grep -qxF -- "${caminho}" "${javistos}" 2>/dev/null && continue
        endereco="$(busctl get-property org.bluez "${caminho}" org.bluez.Device1 Address 2>/dev/null \
            | sed -E 's/^s "?//; s/"?$//' || true)"
        #: Sem endereço não há candidato — e o caminho NÃO entra em já-vistos,
        #: porque a propriedade pode aparecer na volta seguinte.
        [[ "${endereco}" =~ ${_MAC_FORMA} ]] || continue
        nome="$(busctl get-property org.bluez "${caminho}" org.bluez.Device1 Alias 2>/dev/null \
            | sed -E 's/^s "?//; s/"?$//' || true)"
        pareado="$(busctl get-property org.bluez "${caminho}" org.bluez.Device1 Paired 2>/dev/null \
            | sed -E 's/^b //' || true)"
        classe="$(busctl get-property org.bluez "${caminho}" org.bluez.Device1 Class 2>/dev/null \
            | sed -E 's/^u //' || true)"
        [[ "${classe}" =~ ^[0-9]+$ ]] || classe=""
        printf '%s\t%s\t%s\t%s\n' "${endereco^^}" "$(_higienizar "${nome}")" \
            "$([[ "${pareado}" == "true" ]] && printf 'pareado' || printf 'novo')" "${classe}"
        printf '%s\n' "${caminho}" >>"${javistos}"
    done <<<"$(busctl tree org.bluez --list 2>/dev/null \
        | grep -oE "^/org/bluez/${hci}/dev_[0-9A-Fa-f_]+$" | sort -u || true)"
}

#: BLOQUEIA por <SEGUNDOS> — é uma janela de busca, não um interruptor. O
#: `--init-script` é o único jeito de dar mais de um comando a uma sessão só do
#: bluetoothctl, e a sessão precisa ser uma só: `select` não sobrevive entre
#: invocações (cada `bluetoothctl` é um cliente D-Bus novo), e a descoberta
#: morre junto com o cliente que a pediu.
verbo_descobrir() {
    local adaptador="$1" segundos="$2" hci fim quantos
    hci="$(_hci_do_mac "${adaptador}" || true)"
    [[ -n "${hci}" ]] || { _erro "adaptador ${adaptador} não está na mesa (plugado e ligado?)"; exit 1; }
    command -v bluetoothctl >/dev/null 2>&1 \
        || { _erro "bluetoothctl ausente — sem ele não há janela de busca"; exit 1; }
    if _seco; then
        _dizer_seco "bluetoothctl --timeout ${segundos} (select ${adaptador}; power on; pairable on; scan on)"
        _dizer_seco "e, a cada segundo da janela, uma linha por candidato novo de ${hci}: MAC \\t NOME \\t novo|pareado \\t CLASSE"
        return 0
    fi
    BUSCA_ROTEIRO="$(mktemp)" || { _erro "não consegui criar o roteiro temporário"; exit 1; }
    BUSCA_JAVISTOS="$(mktemp)" || { _erro "não consegui criar a lista de já-vistos"; exit 1; }
    chmod 600 "${BUSCA_ROTEIRO}" "${BUSCA_JAVISTOS}"
    #: O `trap` de EXIT cobre o SIGTERM, e isso é MEDIDO (20/09/2026): o bash
    #: corre o trap de saída também quando morre por sinal, então um `trap`
    #: separado de TERM/INT foi escrito, medido com a cura arrancada, e não
    #: reprovou nada — era linha a mais dizendo o que esta já diz.
    trap _fechar_a_busca EXIT
    printf 'select %s\npower on\npairable on\nscan on\n' "${adaptador}" >"${BUSCA_ROTEIRO}"
    _registrar "janela de busca de ${segundos}s aberta em ${adaptador} (${hci})"
    #: O teto de tempo externo é cinto: se o bluetoothctl ignorar o --timeout,
    #: quem fica preso é um processo ROOT.
    #:
    #: E A JANELA VAI PARA O FUNDO, que é a mudança. Presa em primeiro plano
    #: ela não deixava ninguém olhar o barramento enquanto varria — e o que
    #: interessa a quem chama acontece justamente DURANTE a varredura.
    timeout "$((segundos + 10))" bluetoothctl --timeout "${segundos}" \
        --init-script "${BUSCA_ROTEIRO}" >/dev/null 2>&1 &
    BUSCA_PID=$!
    fim=$(( $(date +%s) + segundos ))
    while kill -0 "${BUSCA_PID}" 2>/dev/null && (( $(date +%s) < fim )); do
        _candidatos_novos "${hci}" "${BUSCA_JAVISTOS}"
        sleep 1
    done
    #: Uma última passada com a janela já fechando: o aparelho que apareceu no
    #: último segundo é candidato como qualquer outro, e perdê-lo obrigaria a
    #: pessoa a repetir o gesto de PS + Create inteiro.
    _candidatos_novos "${hci}" "${BUSCA_JAVISTOS}"
    wait "${BUSCA_PID}" 2>/dev/null || true
    BUSCA_PID=""
    quantos="$(wc -l <"${BUSCA_JAVISTOS}" 2>/dev/null || printf '0')"
    #: O DIÁRIO CONTA, NÃO NOMEIA. Uma varredura vê o celular do vizinho, e o
    #: journal desta máquina não é lugar para o endereço de quem passou na rua.
    _registrar "janela de busca fechada em ${adaptador} (${hci}): ${quantos} candidato(s)"
    return 0
}

#: Pair() precisa de agente registrado — o projeto já instala o
#: `hefesto-bt-agent.service` (NoInputNoOutput) exatamente para o bond nascer
#: "Bonded" e não só "Paired". Sem ele o BlueZ responde
#: "No agent available for request type 2" e este verbo falha com motivo.
verbo_parear() {
    local adaptador="$1" controle="$2" hci no caminho
    hci="$(_hci_do_mac "${adaptador}" || true)"
    [[ -n "${hci}" ]] || { _erro "adaptador ${adaptador} não está na mesa (plugado e ligado?)"; exit 1; }
    no="$(_no_do_dispositivo "${controle}")"
    caminho="/org/bluez/${hci}/${no}"
    if _seco; then
        _dizer_seco "busctl call org.bluez ${caminho} org.bluez.Device1 Pair"
        _dizer_seco "busctl set-property org.bluez ${caminho} org.bluez.Device1 Trusted b true"
        return 0
    fi
    #: 45 s cobre o pareamento mais lento medido; sem teto, um controle que
    #: sumiu no meio do gesto deixaria root pendurado até o fim da sessão.
    if ! timeout 45 busctl call org.bluez "${caminho}" org.bluez.Device1 Pair >/dev/null 2>&1; then
        _erro "Pair() falhou em ${controle} via ${adaptador} — o controle está em modo de pareamento (PS + Create) e dentro da janela de busca?"
        exit 1
    fi
    busctl set-property org.bluez "${caminho}" org.bluez.Device1 Trusted b true >/dev/null 2>&1 || true
    _registrar "controle ${controle} pareado e confiado em ${adaptador} (${hci})"
    return 0
}

#: CONEXAO-ZUMBI-01 (18/09/2026) — derruba o LINK de um controle que conectou e
#: NÃO virou controle. O caso, medido na mesa dela às 11h55: ACL de pé, nenhum
#: `hidraw`, nenhum nó de LED, nenhuma bateria — e o controle parado no padrão
#: de fábrica, barra azul e jogador 1. Derrubar o link faz o controle procurar
#: de novo, e achar o adaptador onde o bond dele está.
#:
#: O ALVO É O LINK, NÃO O DEVICE — e é por isso que o `Disconnect()` do
#: `org.bluez.Device1` NÃO serve aqui: o zumbi não tem objeto no BlueZ para
#: receber a chamada. É exatamente o que o distingue do "conectado sem hidraw"
#: que o `doctor.sh` já pega (`check_bt_connected_sem_hidraw`), cuja cura é
#: outra (o cache SDP) e cujo device o BlueZ conhece.
#:
#: A ESCADA, E A ORDEM É POR MEDIÇÃO:
#:   1. `hcitool dc` — o único caminho MEDIDO (derrubou o zumbi de 18/09). Foi
#:      DEPRECIADO pelo BlueZ, então a ausência dele é caso normal, não bug;
#:   2. `btmgmt disconnect` — a mgmt API, que é a ferramenta que a upstream
#:      indica, e que também fala com a camada de link (não depende de objeto
#:      no bluetoothd). Plano B porque esta casa ainda NÃO a mediu neste gesto.
#: Sem nenhum dos dois, o verbo FALHA COM MOTIVO — ausência é resposta, nunca
#: ação às cegas.
verbo_desconectar() {
    local adaptador="$1" controle="$2" hci indice
    hci="$(_hci_do_mac "${adaptador}" || true)"
    [[ -n "${hci}" ]] || { _erro "adaptador ${adaptador} não está na mesa (plugado e ligado?)"; exit 1; }
    #: O `-i`/`--index` NÃO é zelo: o rádio é POR ADAPTADOR, e `hcitool dc` sem
    #: `-i` cai no primeiro adaptador que o kernel rotear. Numa malha de três
    #: dongles isso derrubaria o link de OUTRO adaptador — quem estava jogando.
    indice="${hci#hci}"
    if _seco; then
        _dizer_seco "hcitool -i ${hci} dc ${controle}   (plano B: btmgmt --index ${indice} disconnect ${controle})"
        return 0
    fi
    if command -v hcitool >/dev/null 2>&1; then
        if timeout 10 hcitool -i "${hci}" dc "${controle}" >/dev/null 2>&1; then
            _registrar "link de ${controle} derrubado em ${adaptador} (${hci}) por hcitool dc"
            return 0
        fi
    fi
    if command -v btmgmt >/dev/null 2>&1; then
        if timeout 10 btmgmt --index "${indice}" disconnect "${controle}" >/dev/null 2>&1; then
            _registrar "link de ${controle} derrubado em ${adaptador} (${hci}) por btmgmt disconnect"
            return 0
        fi
    fi
    if ! command -v hcitool >/dev/null 2>&1 && ! command -v btmgmt >/dev/null 2>&1; then
        _erro "não há como derrubar o link de ${controle}: nem 'hcitool' (depreciado pelo BlueZ, pacote bluez-deprecated / bluez-deprecated-tools) nem 'btmgmt' estão nesta máquina"
        exit 1
    fi
    _erro "não consegui derrubar o link de ${controle} em ${adaptador} (${hci}) — o link ainda estava de pé quando tentei?"
    exit 1
}

#: DONO ÚNICO da regra do sudoers. O `install.sh` só canaliza a saída daqui
#: para o `visudo -c`. Verbo novo no `case` lá embaixo tem de aparecer aqui, ou
#: a janela não consegue chamá-lo — que é o sentido certo da falha.
verbo_regra_sudo() {
    local usuaria="$1" m
    #: MAC em classes de caractere EXPLÍCITAS, sem um `*` sequer: `*` no
    #: sudoers casa espaço em branco, e casar espaço em argumento é como
    #: NOPASSWD estreito vira NOPASSWD largo. O `\:` é obrigatório — `:` é
    #: metacaractere do sudoers.
    m='[0-9A-Fa-f][0-9A-Fa-f]\:[0-9A-Fa-f][0-9A-Fa-f]\:[0-9A-Fa-f][0-9A-Fa-f]'
    m="${m}\\:[0-9A-Fa-f][0-9A-Fa-f]\\:[0-9A-Fa-f][0-9A-Fa-f]\\:[0-9A-Fa-f][0-9A-Fa-f]"
    cat <<FIM
# /etc/sudoers.d/49-hefesto-bt-ponte — gerado por
# ${ALVO_INSTALADO} regra-sudo ${usuaria}
#
# A ponte privilegiada do Bluetooth (decisão dela, 22/08/2026: o sudo é do
# install e vale para o app inteiro). NÃO editar à mão: o install regrava.
#
# A regra é estreita de propósito — caminho absoluto, verbos nomeados um a um,
# MAC em classes de caractere explícitas e NENHUM curinga. O nome novo do
# adaptador entra pelo STDIN, não por argv, justamente para que não sobre
# argumento livre a casar aqui.
Cmnd_Alias HEFESTO_BT_PONTE = \\
    ${ALVO_INSTALADO} adaptadores, \\
    ${ALVO_INSTALADO} bonds ${m}, \\
    ${ALVO_INSTALADO} renomear ${m}, \\
    ${ALVO_INSTALADO} esquecer ${m} ${m}, \\
    ${ALVO_INSTALADO} parear ${m} ${m}, \\
    ${ALVO_INSTALADO} desconectar ${m} ${m}, \\
    ${ALVO_INSTALADO} descobrir ${m} [0-9], \\
    ${ALVO_INSTALADO} descobrir ${m} [0-9][0-9], \\
    ${ALVO_INSTALADO} descobrir ${m} [0-9][0-9][0-9]

${usuaria} ALL=(root) NOPASSWD: HEFESTO_BT_PONTE
FIM
}

# --- despacho ---------------------------------------------------------------

if [[ "${1:-}" == "--dry-run" ]]; then
    SECOS=1
    shift
fi

VERBO="${1:-}"
[[ -n "${VERBO}" ]] || _uso
shift || true

case "${VERBO}" in
    adaptadores)
        [[ $# -eq 0 ]] || _recusar "adaptadores não recebe argumento"
        verbo_adaptadores
        ;;
    bonds)
        [[ $# -eq 1 ]] || _recusar "bonds recebe exatamente 1 argumento (MAC do adaptador)"
        _mac "${1}" 'MAC do adaptador'; ARG_ADAPTADOR="${VALIDADO}"
        verbo_bonds "${ARG_ADAPTADOR}"
        ;;
    renomear)
        [[ $# -eq 1 ]] || _recusar "renomear recebe exatamente 1 argumento (MAC do adaptador); o nome vem pelo stdin"
        _mac "${1}" 'MAC do adaptador'; ARG_ADAPTADOR="${VALIDADO}"
        verbo_renomear "${ARG_ADAPTADOR}"
        ;;
    esquecer)
        [[ $# -eq 2 ]] || _recusar "esquecer recebe exatamente 2 argumentos (MAC do adaptador, MAC do controle)"
        _mac "${1}" 'MAC do adaptador'; ARG_ADAPTADOR="${VALIDADO}"
        _mac "${2}" 'MAC do controle';  ARG_CONTROLE="${VALIDADO}"
        verbo_esquecer "${ARG_ADAPTADOR}" "${ARG_CONTROLE}"
        ;;
    descobrir)
        [[ $# -eq 2 ]] || _recusar "descobrir recebe exatamente 2 argumentos (MAC do adaptador, segundos)"
        _mac "${1}" 'MAC do adaptador'; ARG_ADAPTADOR="${VALIDADO}"
        _segundos "${2}";               ARG_SEGUNDOS="${VALIDADO}"
        verbo_descobrir "${ARG_ADAPTADOR}" "${ARG_SEGUNDOS}"
        ;;
    parear)
        [[ $# -eq 2 ]] || _recusar "parear recebe exatamente 2 argumentos (MAC do adaptador, MAC do controle)"
        _mac "${1}" 'MAC do adaptador'; ARG_ADAPTADOR="${VALIDADO}"
        _mac "${2}" 'MAC do controle';  ARG_CONTROLE="${VALIDADO}"
        verbo_parear "${ARG_ADAPTADOR}" "${ARG_CONTROLE}"
        ;;
    desconectar)
        [[ $# -eq 2 ]] || _recusar "desconectar recebe exatamente 2 argumentos (MAC do adaptador, MAC do controle)"
        _mac "${1}" 'MAC do adaptador'; ARG_ADAPTADOR="${VALIDADO}"
        _mac "${2}" 'MAC do controle';  ARG_CONTROLE="${VALIDADO}"
        verbo_desconectar "${ARG_ADAPTADOR}" "${ARG_CONTROLE}"
        ;;
    regra-sudo)
        [[ $# -eq 1 ]] || _recusar "regra-sudo recebe exatamente 1 argumento (nome da usuária)"
        _usuaria "${1}"; ARG_USUARIA="${VALIDADO}"
        verbo_regra_sudo "${ARG_USUARIA}"
        ;;
    ajuda|--help|-h)
        _uso
        ;;
    *)
        _recusar "verbo desconhecido: '${VERBO}'"
        ;;
esac
