#!/usr/bin/env bash
# bt_ponte_privilegiada.sh — a ponte privilegiada do Bluetooth.
#
# As ÚNICAS operações de root que a janela precisa para mover um controle de um
# adaptador para outro. Cada verbo tem a entrada validada ANTES de tocar em
# qualquer coisa, e NÃO EXISTE verbo que execute comando arbitrário.
#
# POR QUE EXISTE (decisão, 22/08/2026)
#
#   "a ideia é que usemos o sudo só na hora do install e isso vai valer sempre
#    no nosso app. não tem como não usar se tratando de bt. zero problemas."
#
# O gesto de migrar um controle está no docs/usage/bluetooth-varios-adaptadores.md
# §3.3. Tirar o pareamento é `Adapter1.RemoveDevice`, que o usuário comum faz pelo
# D-Bus; o que exige root é só a sobra em disco quando o dongle está FORA da mesa
# (o BlueZ não está lá para apagar a própria pasta).
#
# O `rm` do cache SDP de todos os adaptadores, que este cabeçalho já defendeu como
# SDP-CACHE-01, SAIU em 07/10/2026 (O-BLUEZ-SO-PELA-PORTA-OFICIAL-01). Lido no fonte
# do BlueZ 5.86, `device_remove_stored` (device.c:5402-5456) apaga a pasta do bond e
# tira do `cache/<MAC>` os grupos ServiceRecords, Attributes e Endpoints; sem
# ServiceRecords, `device.c:4441-4444` marca o serviço como não resolvido e o
# BlueZ refaz o SDP na conexão seguinte. Um cache com só o nome não faz o pareamento
# novo nascer com SDP vazio, então apagar o cache do destino não curava nada.
#
# COMO A JANELA CHAMA SEM PEDIR SENHA — e por que `sudoers.d`
#
# O `install.sh` grava `/etc/sudoers.d/49-hefesto-bt-ponte` com NOPASSWD
# restrito a ESTE caminho absoluto e aos verbos nomeados um a um, sem
# argumento de aparelho (o verbo `regra-sudo` abaixo é o dono único desse
# texto — verbo novo entra na regra sozinho, e é impossível a regra ficar mais
# larga que a lista de verbos).
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
#   1. O ENDEREÇO E O NOME NOVO VÊM PELO STDIN, NUNCA POR ARGV. A linha de
#      comando de um `sudo` é registro por desenho: o sudo a escreve no
#      journal (e no `auth.log`), o journal a põe na unidade de quem chamou, e
#      o `/proc/<pid>/cmdline` a mostra a qualquer conta enquanto o processo
#      vive. No argv vão só o verbo e os segundos do `descobrir`, que não
#      identificam ninguém: o sudo registra `COMMAND=<ponte> esquecer`, quem,
#      quando e qual verbo, e nenhum aparelho. E a linha de comando permitida
#      pelo sudoers fica COMPLETAMENTE fechada — nenhum argumento livre para
#      casar;
#   2. A FORMA É CONFERIDA AQUI, ANTES DE QUALQUER EFEITO. O preço da
#      contenção 1: o sudoers deixou de conferir a forma do endereço (até
#      29/09/2026 ele a casava em classes de caractere). Quem confere é este
#      script — `_mac`, uma regex ancorada de MAC, no despacho, antes do
#      verbo —, e linha que falta, linha a mais e o endereço no argv (a forma
#      velha) são recusa;
#   3. OS GANCHOS DE TESTE MORREM SOB SUDO. `HEFESTO_BT_LIB`,
#      `HEFESTO_PONTE_DRY_RUN` e `HEFESTO_BT_LOG_DEST` são apagados quando
#      `SUDO_UID` está no ambiente. O `Defaults env_reset` do sudo já faria
#      isso, mas quem o desligou não pode ganhar de brinde um `rm` como root em
#      raiz escolhida por ele.
#
# OS VERBOS (a lista é curta de propósito). O stdin traz uma linha por dado, na
# ordem da coluna do meio, e fecha depois dela:
#
#   verbo e argv       stdin                  o que faz
#   adaptadores        —                      lista MAC, alias, ligado e hciN
#   bonds              adaptador              lista os controles pareados naquele
#   renomear           adaptador, nome novo   escreve o alias novo
#   esquecer           adaptador, controle    remove o bond e o cache da origem
#   descobrir <SEG>    adaptador              janela de busca (BLOQUEIA <SEG>) e,
#                                             enquanto ela vive, os candidatos
#   parear             adaptador, controle    Pair() + Trusted=true
#   desconectar        adaptador, controle    derruba o LINK (o controle zumbi)
#   reiniciar-travado  —                      reinicia o adaptador que o KERNEL
#                                             diz estar travado em laço (família
#                                             3) — sem dado nenhum: quem escolhe
#                                             a porta é o journal do kernel,
#                                             nunca quem chama
#   religar-orfaos     —                      religa NA HORA o controle que
#                                             perdeu a probe — o do cabo no -71,
#                                             o do rádio na contenção
#                                             (STORM-USB-02). Sem dado: quem
#                                             escolhe é o /sys, pelas guardas do
#                                             bt_rebind_orphans.sh
#   regra-sudo <USUARIA>  —                   imprime o /etc/sudoers.d (não
#                                             instala)
#
# Os verbos sem dado não leem o stdin: quem os chama (o watchdog, o
# storm_watch, o install) não fecha o stdin, e um verbo que o esperasse ficaria
# parado 10 s por nada.
#
# A TRAVA DO RÁDIO É DE QUEM CHAMA (O-DIARIO-DO-RADIO-01). Os motores que mexem
# no rádio passam por um `flock` em /run/hefesto-dualsense4unix/radio.lock
# (`integrations/diario_do_radio.py`). Esta ponte NUNCA o pede: quem a chama já
# o segura — o watchdog root e a central do daemon —, e um segundo `flock` aqui,
# num processo filho, esperaria pelo próprio pai até o prazo.
#
# O DIÁRIO DO ROOT. O que esta ponte faz sozinha vai para
# /var/lib/hefesto-dualsense4unix/radio-diario.jsonl, no MESMO formato do
# diário dela: o leitor (`diario_do_radio.ler`) junta os dois pela hora. Root não
# escreve no lar dela — um link simbólico ali levaria esta escrita a qualquer
# arquivo da máquina.
#
# SAÍDA: dado em TSV no stdout, uma linha por item; erro no stderr.
#   adaptadores -> MAC \t ALIAS \t ligado|desligado \t hciN
#   bonds       -> MAC \t NOME \t com-chave|sem-chave
#   descobrir   -> MAC \t NOME \t novo|pareado \t CLASSE
#   reiniciar-travado -> reiniciado|recusado|segurado \t PORTA \t hciN \t DETALHE
#   religar-orfaos -> as frases do bt_rebind_orphans.sh, uma por controle que ele
#                  tocou (as mesmas do journal); nada quando não havia órfão
# A CLASSE é o `Class` do BlueZ em decimal (a *class of device* do
# Bluetooth), e sai crua de propósito: quem decide se um candidato é
# controle é quem chama, não esta ponte. Vazia quando o BlueZ não a
# publica — um aparelho só-LE não tem classe, e inventar uma seria pior
# que a coluna vazia. Medido na bancada em 20/09/2026: os seis objetos
# de DualSense do BlueZ respondem `u 9480` (0x2508).
# Alias e nome são higienizados (controle/tab/quebra viram espaço) porque vêm
# do BlueZ, não de nós.
#
# CÓDIGOS DE SAÍDA: 0 sucesso · 1 falha operacional · 2 uso/entrada inválida.
#
# O ALIAS É ESCRITO LITERALMENTE, e isso é decisão de produto (#5 de 22/08/2026: "o
# nome do dongle é do usuário; o prefixo funcional é do produto"). O prefixo
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
#                           medível sem abrir varredura no rádio do usuário.
#   HEFESTO_BT_LAPIDES      a lista de lápides (default: a do acervo de bonds,
#                           só com a árvore REAL; com raiz de teste e sem este
#                           gancho, nenhuma lápide é escrita)
#   HEFESTO_RADIO_DIARIO_ROOT  o diário do root (mesma regra)
#   HEFESTO_SYSFS_RAIZ      raiz do /sys que o `reiniciar-travado` lê e escreve
#   HEFESTO_SYSFS_BLUETOOTH raiz dos adaptadores que o `adaptadores` lê no degrau
#                           do sysfs (default /sys/class/bluetooth)
#   HEFESTO_BT_JOURNAL      arquivo lido no lugar do journal do kernel, na
#                           forma do `journalctl -o short-unix` (epoch primeiro)
#   HEFESTO_PONTE_STAMPS    onde mora o carimbo do último reinício por porta
#   HEFESTO_USB_PAUSA_S     a pausa entre desautorizar e autorizar a porta
#   HEFESTO_USB_ESPERA_S    quanto esperar o adaptador voltar
#   HEFESTO_HID_DEVICES_DIR / HEFESTO_USB_DEVICES_DIR  as raízes do
#                           `bt_rebind_orphans.sh` (que o `religar-orfaos` roda):
#                           com uma delas desviada o verbo roda sem root, contra
#                           a mesa de mentira da régua
set -euo pipefail

#: Sob sudo os ganchos não existem. O `env_reset` do sudo já os apagaria; esta
#: linha é o cinto para a máquina que o desligou (contenção 3 do cabeçalho).
if [[ -n "${SUDO_UID:-}" || -n "${SUDO_USER:-}" ]]; then
    unset HEFESTO_BT_LIB HEFESTO_PONTE_DRY_RUN HEFESTO_BT_LOG_DEST HEFESTO_BT_BIN \
        HEFESTO_BT_LAPIDES HEFESTO_RADIO_DIARIO_ROOT HEFESTO_SYSFS_RAIZ \
        HEFESTO_BT_JOURNAL HEFESTO_PONTE_STAMPS HEFESTO_USB_PAUSA_S \
        HEFESTO_USB_ESPERA_S HEFESTO_SYSFS_BLUETOOTH \
        HEFESTO_HID_DEVICES_DIR HEFESTO_USB_DEVICES_DIR
fi

#: `%/` normaliza a barra final: sem isso, uma raiz de teste terminada em
#: `/` faria a guarda de forma de `_apagar` recusar todo caminho legítimo.
LIB="${HEFESTO_BT_LIB:-/var/lib/bluetooth}"
LIB="${LIB%/}"
LIB_REAL="/var/lib/bluetooth"
ALVO_INSTALADO="/usr/local/lib/hefesto-dualsense4unix/bt_ponte_privilegiada.sh"
SECOS="${HEFESTO_PONTE_DRY_RUN:-0}"

#: A raiz do /sys do `reiniciar-travado`. Com ela desviada, nada do kernel é
#: lido nem escrito — é a mesa de mentira da régua.
SYSFS="${HEFESTO_SYSFS_RAIZ:-/sys}"
SYSFS="${SYSFS%/}"
SYSFS_REAL="/sys"

#: As lápides e o diário moram na pasta do root do produto. Só a árvore REAL
#: escreve neles sem gancho: uma régua com a raiz desviada que esquecesse de
#: desviá-los escreveria no disco do usuário.
LAPIDES_REAIS="/var/lib/hefesto-dualsense4unix/bt-bonds/.lapides"
DIARIO_REAL="/var/lib/hefesto-dualsense4unix/radio-diario.jsonl"

#: BARRAMENTO DE MENTIRA. Com esta pasta na frente do PATH, o `busctl` e o
#: `bluetoothctl` que este script chama são os DO USUÁRIO — os da pasta —, e não os
#: do sistema. Existe por uma razão só: a lista de candidatos do `descobrir`
#: só se mede abrindo uma varredura, e abrir varredura na máquina do usuário custa
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
# sem isto grava, no journal da máquina do usuário, linhas que descrevem eventos que
# nunca aconteceram.
LOG_TAG=hefesto-bt-ponte
LOG_DEST="${HEFESTO_BT_LOG_DEST:-}"
#: O REGISTRO NÃO LEVA ENDEREÇO (O-SUDO-NAO-GRAVA-O-ENDERECO-NO-DIARIO-01,
#: 29/09/2026). A linha vai ao journal do sistema, que toda conta do grupo `adm`
#: lê: ela diz o verbo e o `hciN`, e o adaptador fora da mesa sai como «um
#: adaptador fora da mesa». O endereço fica no diário do root (`_diario`),
#: que é dado com leitor (`diario_do_radio.ler` junta os dois diários por ele).
#: E não se mascara aqui: este script não importa o dono da máscara nem faz
#: `source` de nada (ver «DUAS CÓPIAS, UMA FORMA» abaixo), e uma máscara
#: escrita em bash seria uma cópia dela.
_registrar() {
    case "${LOG_DEST}" in
        "")   logger -t "${LOG_TAG}" "$*" 2>/dev/null || true ;;
        none) : ;;
        *)    printf '%s %s: %s\n' "$(date -Is 2>/dev/null || true)" "${LOG_TAG}" "$*" \
                  2>/dev/null >>"${LOG_DEST}" || true ;;
    esac
}

_erro() { printf '%s: %s\n' "${0##*/}" "$*" >&2; }

# --- o diário do root (O-DIARIO-DO-RADIO-01) -------------------------------
#
# DUAS CÓPIAS, UMA FORMA: estas duas funções existem byte a byte iguais aqui e
# no `bt_health_watchdog.sh`, os dois escritores root do diário. Não é um
# `source` de propósito: um script root que lê outro arquivo em tempo de
# execução herda o risco de quem pode escrever nele. A régua
# `tests/unit/test_o_diario_do_radio.py` confere que as duas cópias são a
# mesma, e que o leitor Python entende a linha que elas escrevem.

#: Texto -> string JSON. Barra e aspas escapadas; controle vira espaço.
_json_texto() {
    local s="${1:-}"
    s="${s//\\/\\\\}"
    s="${s//\"/\\\"}"
    s="$(printf '%s' "${s}" | tr '\000-\037' ' ')"
    printf '"%s"' "${s}"
}

#: Uma ação no diário do root. $1 destino (vazio = não registra) · $2 quem ·
#: $3 o quê · $4 por quê · $5 antes (JSON) · $6 depois (JSON) · $7 campos a
#: mais, já em JSON (`"porta": "3-4.1.4"`). Nunca falha: a ação já aconteceu.
_diario_escrever() {
    local alvo="${1:-}" linha tamanho
    [[ -n "${alvo}" ]] || return 0
    [[ -L "${alvo}" ]] && return 0
    linha="{\"quando\": $(_json_texto "$(date -Iseconds 2>/dev/null || true)"), \"carimbo\": $(date +%s), \"quem\": $(_json_texto "$2"), \"o_que\": $(_json_texto "$3"), \"por_que\": $(_json_texto "$4"), \"antes\": ${5:-null}, \"depois\": ${6:-null}${7:+, $7}}"
    install -d -m 0755 "${alvo%/*}" 2>/dev/null || true
    tamanho="$(stat -c %s "${alvo}" 2>/dev/null || echo 0)"
    if [[ "${tamanho}" -gt 524288 ]]; then
        mv -f -- "${alvo}" "${alvo}.1" 2>/dev/null || true
    fi
    printf '%s\n' "${linha}" >>"${alvo}" 2>/dev/null || true
    return 0
}

#: Onde ESTA execução registra: o gancho, ou o diário real quando a árvore e o
#: /sys são os de verdade; com raiz de teste e sem gancho, em lugar nenhum.
_diario_alvo() {
    if [[ -n "${HEFESTO_RADIO_DIARIO_ROOT:-}" ]]; then
        printf '%s\n' "${HEFESTO_RADIO_DIARIO_ROOT}"
    elif [[ "${LIB}" == "${LIB_REAL}" && "${SYSFS}" == "${SYSFS_REAL}" ]]; then
        printf '%s\n' "${DIARIO_REAL}"
    fi
}

_diario() { _diario_escrever "$(_diario_alvo)" "$@"; }

#: Uso/entrada inválida sai com 2 — código distinto de falha operacional, para
#: a janela saber que o problema é dela e não do rádio.
_recusar() { _erro "$*"; exit 2; }

_uso() {
    cat >&2 <<'FIM'
uso: bt_ponte_privilegiada.sh <verbo> [segundos]   (os dados vêm pelo STDIN)

  verbo              o STDIN, uma linha por dado, nesta ordem
  adaptadores        —
  bonds              MAC do adaptador
  renomear           MAC do adaptador, nome novo
  esquecer           MAC do adaptador, MAC do controle
  descobrir <SEG>    MAC do adaptador
  parear             MAC do adaptador, MAC do controle
  desconectar        MAC do adaptador, MAC do controle
  reiniciar-travado  —
  religar-orfaos     —
  regra-sudo <USUARIA>

  exemplo: printf '%s\n%s\n' <adaptador> <controle> | sudo bt_ponte_privilegiada.sh esquecer

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

#: O endereço de um aparelho, pela próxima linha do stdin (contenção 1). As
#: regras são as do `_nome_do_stdin`: o prazo de 10 s, a recusa com código 2
#: no shell principal (a devolução pela global `VALIDADO`) e a forma do `_mac`,
#: que é a mesma de quando o endereço vinha no argv.
_mac_do_stdin() {
    local papel="$1" linha
    IFS= read -r -t 10 linha || _recusar "${papel} não veio pelo stdin (o endereço vem pelo stdin, uma linha por dado)"
    _mac "${linha}" "${papel}"
}

#: Depois das linhas que o verbo pede, o stdin tem de FECHAR. Linha a mais é
#: recusa: um chamador que monta o pedido errado tem de falhar alto, e não ter
#: metade dele lida. E um stdin que não fecha em 10 s também — root parado
#: esperando é falha de disponibilidade com privilégio.
_fim_do_stdin() {
    local sobra="" rc=0
    IFS= read -r -t 10 sobra || rc=$?
    #: `read` devolve 0 com a linha inteira, 1 no fim do arquivo (com o resto
    #: sem quebra de linha em `sobra`, se houver) e mais de 128 no prazo.
    (( rc <= 128 )) || _recusar "o stdin não fechou em 10 s depois dos dados do verbo"
    [[ "${rc}" -ne 0 && -z "${sobra}" ]] \
        || _recusar "o stdin trouxe uma linha a mais do que o verbo lê"
}

#: O endereço no argv é a forma de antes de 29/09/2026 — e é recusa com a
#: frase certa, não com a contagem: quem chamar pelo jeito antigo tem de saber
#: por quê, e nada acontece. A regra do sudoers nova também não a deixa passar
#: sem senha.
_sem_dado_no_argv() {
    local verbo="$1"; shift
    [[ $# -eq 0 ]] || _recusar "${verbo}: o endereço vem pelo stdin, uma linha por dado, e não no argv"
}

#: O nome novo do adaptador — o único dado de forma livre, e ele vem pelo
#: stdin como o endereço (contenção 1). A régua é ALLOWLIST, e é feita por
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

#: De onde, para o registro: o `hciN`, ou «um adaptador fora da mesa» quando o
#: adaptador não está plugado — nunca o endereço (ver `_registrar`).
_onde() {
    if [[ -n "${1:-}" ]]; then
        printf 'do adaptador %s' "$1"
    else
        printf 'de um adaptador fora da mesa'
    fi
}

#: MAC do adaptador -> hciN. Vazio (e retorno 1) quando o dongle não está
#: plugado — e isso é caso NORMAL: migrar um controle de um dongle que saiu da
#: mesa é exatamente o que o verbo `esquecer` precisa saber fazer.
_hci_do_mac() {
    local alvo="$1" caminho hci endereco
    #: RAIZ DE TESTE NÃO FALA COM O BARRAMENTO REAL. A suíte roda estes scripts
    #: DE VERDADE, na máquina do usuário, com quatro DualSense e um Pro no rádio — e
    #: `renomear`/`descobrir`/`parear` MEXEM no adaptador. Sem esta linha,
    #: bastaria um MAC de teste coincidir com um adaptador vivo para um portão
    #: derrubar a bancada. Mesma razão do gancho de raiz do bt_bonds_snapshot.
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

#: O nome já vem validado do despacho (o `_nome_do_stdin`, depois do endereço).
verbo_renomear() {
    local adaptador="$1" nome="$2" hci
    hci="$(_hci_do_mac "${adaptador}" || true)"
    [[ -n "${hci}" ]] || { _erro "adaptador ${adaptador} não está na mesa (plugado e ligado?)"; exit 1; }
    if _seco; then
        _dizer_seco "busctl set-property org.bluez /org/bluez/${hci} org.bluez.Adapter1 Alias s <${nome}>"
        return 0
    fi
    if busctl set-property org.bluez "/org/bluez/${hci}" org.bluez.Adapter1 Alias s "${nome}" 2>/dev/null; then
        _registrar "o adaptador ${hci} foi renomeado"
        return 0
    fi
    _erro "não consegui escrever o alias de ${adaptador} (${hci})"
    exit 1
}

#: O verbo que paga o script. Tira o bond (pelo D-Bus, e pelo disco quando o
#: dongle está fora da mesa), o cache da ORIGEM e deixa a lápide.
verbo_esquecer() {
    local adaptador="$1" controle="$2" hci no pasta_bond
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
    #: O cache da ORIGEM só sai porque, sem o BlueZ para limpá-lo, o
    #: `[ServiceRecords]` ficaria órfão do bond que acabou de sair. Nos outros
    #: adaptadores o cache NÃO se toca: o BlueZ não precisa disso (ver o cabeçalho).
    _apagar "${LIB}/${adaptador}/cache/${controle}" "cache SDP da origem"
    _enterrar "${adaptador}" "${controle}"
    if ! _seco; then
        _registrar "um controle esquecido $(_onde "${hci}") (bond + cache da origem + lápide)"
        _diario "bt-ponte" "esqueceu o controle" "pedido à ponte privilegiada" \
            "{\"bond\": $(_json_texto "no adaptador")}" \
            "{\"bond\": null, \"lapide\": true}" \
            "\"adaptador\": $(_json_texto "${adaptador}"), \"controle\": $(_json_texto "${controle}"), \"pedido_por\": $(_json_texto "${SUDO_USER:-}")"
    fi
    return 0
}

#: A LÁPIDE (O-DIARIO-DO-RADIO-01). Quem esquece um bond de propósito escreve
#: aqui, e o `bt_bonds_autorestore.sh` não o ressuscita de um snapshot de antes
#: disso — sem ela, um crash do bluetoothd nas 24 h seguintes devolveria o bond
#: velho, e o controle movido voltaria a ter casa em dois adaptadores. UMA
#: linha, UM controle num adaptador: o verbo já só aceita um par, e a R6 dela é
#: que nada se apaga em lote.
_lapides_alvo() {
    if [[ -n "${HEFESTO_BT_LAPIDES:-}" ]]; then
        printf '%s\n' "${HEFESTO_BT_LAPIDES}"
    elif [[ "${LIB}" == "${LIB_REAL}" ]]; then
        printf '%s\n' "${LAPIDES_REAIS}"
    fi
}

_enterrar() {
    local adaptador="$1" controle="$2" alvo
    alvo="$(_lapides_alvo)"
    [[ -n "${alvo}" ]] || return 0
    if _seco; then
        _dizer_seco "gravaria a lápide de ${controle} em ${adaptador}: ${alvo}"
        return 0
    fi
    if [[ -L "${alvo}" ]]; then
        _erro "recusando a lápide: ${alvo} é link simbólico"
        return 0
    fi
    install -d -m 700 "${alvo%/*}" 2>/dev/null || true
    printf '%s %s %s\n' "$(date +%s)" "${adaptador}" "${controle}" >>"${alvo}"
    chmod 600 "${alvo}" 2>/dev/null || true
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
#: adaptador do usuário por até <segundos> — e varredura no próprio adaptador custa de
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
    _registrar "janela de busca de ${segundos}s aberta no adaptador ${hci}"
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
    _registrar "janela de busca fechada no adaptador ${hci}: ${quantos} candidato(s)"
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
    _registrar "um controle pareado e confiado no adaptador ${hci}"
    return 0
}

#: CONEXAO-ZUMBI-01 (18/09/2026) — derruba o LINK de um controle que conectou e
#: NÃO virou controle. O caso, medido na bancada às 11h55: ACL de pé, nenhum
#: `hidraw`, nenhum nó de LED, nenhuma bateria — e o controle parado no padrão
#: de fábrica, barra azul e jogador 1. Derrubar o link faz o controle procurar
#: de novo, e achar o adaptador onde o bond dele está.
#:
#: O ALVO É O LINK, NÃO O DEVICE — e é por isso que o `Disconnect()` do
#: `org.bluez.Device1` NÃO serve aqui: o zumbi não tem objeto no BlueZ para
#: receber a chamada. É exatamente o que o distingue do "conectado sem hidraw"
#: que o `doctor.sh` já pega (`check_bt_connected_sem_hidraw`), cuja cura é
#: outra (RemoveDevice e parear de novo) e cujo device o BlueZ conhece.
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
            _registrar "o link de um controle derrubado no adaptador ${hci} por hcitool dc"
            return 0
        fi
    fi
    if command -v btmgmt >/dev/null 2>&1; then
        if timeout 10 btmgmt --index "${indice}" disconnect "${controle}" >/dev/null 2>&1; then
            _registrar "o link de um controle derrubado no adaptador ${hci} por btmgmt disconnect"
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

# --- FAMÍLIA 3: o adaptador travado em laço (O-DIARIO-DO-RADIO-01) ----------
#
# Em 13/09/2026 um controlador Realtek travou das 01:13 às 18:29: 24.998 vezes
# «command 0xfc61 tx timeout», uma a cada ~2,5 s, e nada se recuperou sozinho —
# acabou quando alguém tirou o dongle da porta. Este verbo é esse gesto feito
# por software: desautoriza e reautoriza a PORTA USB do adaptador (o
# `authorized` 0 → 1 do sysfs), que desliga o driver e enumera o aparelho de
# novo.
#
# SEM ARGUMENTO, DE PROPÓSITO. Quem decide QUAL adaptador está travado é o
# journal do KERNEL (`journalctl -k`), que processo nenhum de usuária consegue
# escrever — o /dev/kmsg é do root. Então a regra do sudoers não tem argumento
# a casar, e ninguém consegue, por este verbo, reiniciar um adaptador são.
#
# AS TRÊS GUARDAS, e a ordem importa:
#   1. o LAÇO: pelo menos LIMIAR_DO_LACO «command 0x.... tx timeout» do mesmo
#      hciN na janela — uma ocorrência solta acontece em adaptador são;
#   2. a PORTA, nunca o hciN: o hciN muda de número entre boots e entre
#      replugs. Ele só serve para achar a porta NESTE instante; dali em diante
#      quem manda é o caminho do barramento (`3-4.1.4`). O que amarra o hciN
#      do journal ao aparelho de AGORA é o laço estar VIVO (LACO_VIVO_S): um
#      adaptador que saiu da porta para de repetir, e o número que ele deixou
#      pode já ser de outro aparelho. Conferir que o hciN sai da porta que ele
#      mesmo indicou não prova nada disso — é a mesma leitura duas vezes;
#   3. NINGUÉM CONECTADO: com qualquer conexão de pé no adaptador (os nós
#      `hciN:<handle>` do kernel), o verbo recusa. Um adaptador em laço não tem
#      controle vivo — se tem, a leitura está errada, e errar aqui derruba a
#      bancada.
# E o freio: uma porta só é reiniciada uma vez a cada INTERVALO_ENTRE_RESETS_S.
# Se o laço voltar dentro dele, o verbo não insiste — o que resta é a mão
# dela, e o diário diz qual porta, UMA vez por reinício.
#
# O TIQUE SEGUINTE AO REINÍCIO (conferência de 23/09). A janela de 150 s
# alcança o tique seguinte do watchdog (2 min), e as linhas de ANTES do
# reinício ainda estão nela: sem contar só o que veio DEPOIS do carimbo da
# porta, o adaptador que voltou são era acusado de ter travado de novo — «Tire
# e ponha ele» no sino, sobre um aparelho bom.
#
# E O FREIO QUE PARA (GOVERNADOR-DO-RADIO-01, 23/09/2026). O intervalo de
# 15 min só espaçava os reinícios: um adaptador que volta a travar depois de
# cada um era reiniciado quatro vezes por hora, para sempre — e cada reinício
# é o dongle sumindo e voltando na porta dela. Depois de MAX_REINICIOS_SEGUIDOS
# reinícios sem cura (o laço voltou antes de JANELA_DA_CURA_S), o verbo PARA,
# diz no diário UMA vez, e o sino fica com a frase de pôr a mão. Ele só volta
# a reiniciar aquela porta depois que o laço sumir do journal — a mão do usuário
# (tirar e pôr) ou o adaptador que se curou.
LIMIAR_DO_LACO=5
JANELA_DO_LACO_S=150
#: Medido no kernel.log de 13/09: 24.990 intervalos entre timeouts, mediana
#: 2 s, p99 3 s, o maior 25 s. Quinze segundos são cinco voltas do laço.
LACO_VIVO_S=15
INTERVALO_ENTRE_RESETS_S=900
#: Quantos reinícios seguidos sem cura antes de parar.
MAX_REINICIOS_SEGUIDOS=3
#: Um reinício CUROU se o laço não voltou dentro disto. Quatro intervalos: o
#: laço que volta em menos de uma hora não foi curado pelo reinício.
JANELA_DA_CURA_S=3600
_PORTA_FORMA='^[0-9]{1,3}-[0-9]{1,3}(\.[0-9]{1,3}){0,6}$'

#: As linhas do kernel na janela, com o epoch na frente (`-o short-unix`). O
#: `-k` é o transporte do kernel: é isso que impede alguém de fabricar um laço
#: com `logger`.
_linhas_do_kernel() {
    if [[ -n "${HEFESTO_BT_JOURNAL:-}" ]]; then
        cat -- "${HEFESTO_BT_JOURNAL}" 2>/dev/null || true
        return 0
    fi
    command -v journalctl >/dev/null 2>&1 || return 0
    journalctl -k -b --since "-${JANELA_DO_LACO_S}s" -o short-unix -q --no-pager 2>/dev/null || true
}

#: `hciN QUANTOS ÚLTIMO` por hciN: quantos «command 0x.... tx timeout» com
#: epoch MAIOR que $1 (0 = a janela inteira), e o epoch do mais novo. Sem
#: limiar: quem decide é o verbo.
_timeouts_por_hci() {
    local desde="${1:-0}"
    _linhas_do_kernel \
        | grep -iE '^[0-9]+(\.[0-9]+)? .*hci[0-9]+: command 0x[0-9a-f]{4} tx timeout' \
        | awk -v desde="${desde}" '
            {
                quando = int($1)
                if (quando <= desde) next
                texto = tolower($0)
                if (!match(texto, /hci[0-9]+: command 0x/)) next
                hci = substr(texto, RSTART, RLENGTH)
                sub(/: command 0x$/, "", hci)
                n[hci]++
                if (!(hci in mais_novo) || quando > mais_novo[hci]) mais_novo[hci] = quando
            }
            END { for (h in n) print h, n[h], mais_novo[h] }' \
        | sort || true
}

#: `hciN QUANTOS ÚLTIMO` de quem passou do limiar, um por linha.
_hcis_em_laco() {
    _timeouts_por_hci 0 | awk -v limiar="${LIMIAR_DO_LACO}" '$2 >= limiar' || true
}

#: Quantos timeouts o `hciN` teve DEPOIS do epoch `$2`.
_timeouts_desde() {
    local hci="$1" desde="$2" h n _u
    while read -r h n _u; do
        [[ "${h}" == "${hci}" ]] && { printf '%s\n' "${n}"; return 0; }
    done < <(_timeouts_por_hci "${desde}")
    printf '0\n'
}

#: hciN -> o caminho USB do adaptador (`3-4.1.4`). Falha se não for USB, ou se
#: o caminho não tiver a forma de porta.
_porta_do_hci() {
    local hci="$1" real interface aparelho porta
    real="$(readlink -f -- "${SYSFS}/class/bluetooth/${hci}" 2>/dev/null)" || return 1
    [[ "${real}" == */bluetooth/"${hci}" ]] || return 1
    interface="${real%/bluetooth/*}"
    aparelho="${interface%/*}"
    porta="${aparelho##*/}"
    [[ "${porta}" =~ ${_PORTA_FORMA} ]] || return 1
    [[ "${interface##*/}" == "${porta}:"* ]] || return 1
    printf '%s\n' "${porta}"
}

#: O hciN que mora AGORA na porta — lido a partir da porta, não do nome.
_hci_da_porta() {
    local porta="$1" achado
    for achado in "${SYSFS}/bus/usb/devices/${porta}/${porta}":*/bluetooth/hci*; do
        [[ -e "${achado}" ]] || continue
        [[ "${achado##*/}" =~ ^hci[0-9]+$ ]] || continue
        printf '%s\n' "${achado##*/}"
        return 0
    done
    return 1
}

_ha_conexao() {
    local hci="$1" porta="$2" no
    for no in "${SYSFS}/class/bluetooth/${hci}":* \
              "${SYSFS}/bus/usb/devices/${porta}/${porta}":*/bluetooth/"${hci}/${hci}":*; do
        [[ -e "${no}" ]] && return 0
    done
    return 1
}

_estampas() { printf '%s\n' "${HEFESTO_PONTE_STAMPS:-/run/hefesto-bt-ponte}"; }

#: O FREIO SOLTA quando o laço some: para cada porta em que o verbo parou de
#: reiniciar, se o adaptador que mora nela AGORA não tem um único «command tx
#: timeout» na janela do journal (ou a porta está vazia), a mão do usuário curou — o
#: freio e a contagem de reinícios seguidos saem, e o diário diz O QUE MEDIU:
#: a porta vazia é o adaptador fora dela, e não «voltou» (conferência de
#: 23/09/2026 — o diário dizia «voltou» sobre uma porta sem aparelho).
_soltar_o_freio_curado() {
    local marca porta hci h n _u curado por_que
    for marca in "$(_estampas)"/reset-*.desistiu; do
        [[ -e "${marca}" ]] || continue
        porta="${marca##*/reset-}"
        porta="${porta%.desistiu}"
        [[ "${porta}" =~ ${_PORTA_FORMA} ]] || continue
        curado=1
        hci="$(_hci_da_porta "${porta}" || true)"
        if [[ -n "${hci}" ]]; then
            while read -r h n _u; do
                [[ "${h}" == "${hci}" && "${n}" =~ ^[0-9]+$ && "${n}" -gt 0 ]] && curado=0
            done < <(_timeouts_por_hci 0)
        fi
        [[ "${curado}" -eq 1 ]] || continue
        _seco && { _dizer_seco "soltaria o freio da porta ${porta}: o laço sumiu"; continue; }
        rm -f -- "${marca}" "${marca%.desistiu}.seguidos" 2>/dev/null || true
        if [[ -n "${hci}" ]]; then
            por_que="o laço sumiu do journal: nenhum «command tx timeout» do ${hci} da porta ${porta} em ${JANELA_DO_LACO_S} s"
        else
            por_que="a porta ${porta} ficou sem adaptador: o laço saiu com ele"
        fi
        _diario "bt-ponte" "soltou o freio do reinício" \
            "${por_que}" \
            null "{\"hci\": $(_json_texto "${hci}")}" \
            "\"porta\": $(_json_texto "${porta}"), \"familia\": \"3\""
    done
}

verbo_reiniciar_travado() {
    local hci quantos mais_novo porta agora_hci carimbo anterior agora pausa espera
    local recusou=0 achou=0 volta frase seguidos
    if [[ "${SYSFS}" == "${SYSFS_REAL}" && "$(id -u)" -ne 0 ]]; then
        _erro "'reiniciar-travado' requer root (é a ponte privilegiada)"
        exit 1
    fi
    agora="$(date +%s)"
    _soltar_o_freio_curado
    while read -r hci quantos mais_novo; do
        [[ "${hci}" =~ ^hci[0-9]+$ ]] || continue
        [[ "${quantos}" =~ ^[0-9]+$ && "${mais_novo}" =~ ^[0-9]+$ ]] || continue
        #: O laço PAROU — ou o adaptador saiu da porta e o hciN do journal já
        #: pode ser outro aparelho. Silêncio: não há o que fazer agora.
        (( agora - mais_novo <= LACO_VIVO_S )) || continue
        achou=1
        if ! porta="$(_porta_do_hci "${hci}")"; then
            printf 'recusado\t-\t%s\tsem porta USB\n' "${hci}"
            _diario "bt-ponte" "recusou reiniciar o adaptador" \
                "${quantos} «command tx timeout» seguidos, mas o ${hci} não tem porta USB legível" \
                "{\"hci\": $(_json_texto "${hci}"), \"timeouts\": ${quantos}}" null \
                "\"familia\": \"3\""
            recusou=1
            continue
        fi
        agora_hci="$(_hci_da_porta "${porta}" || true)"
        if [[ "${agora_hci}" != "${hci}" ]]; then
            printf 'recusado\t%s\t%s\to hci da porta agora é %s\n' "${porta}" "${hci}" "${agora_hci:-nenhum}"
            recusou=1
            continue
        fi
        carimbo="$(_estampas)/reset-${porta}"
        anterior="$(cat -- "${carimbo}" 2>/dev/null || echo 0)"
        [[ "${anterior}" =~ ^[0-9]+$ ]] || anterior=0
        #: Depois de um reinício desta porta, só conta o que veio DEPOIS dele.
        if (( anterior > 0 )); then
            quantos="$(_timeouts_desde "${hci}" "${anterior}")"
            (( quantos >= LIMIAR_DO_LACO )) || continue
        fi
        if _ha_conexao "${hci}" "${porta}"; then
            printf 'recusado\t%s\t%s\thá conexão de pé\n' "${porta}" "${hci}"
            _diario "bt-ponte" "recusou reiniciar o adaptador" \
                "o kernel acusa laço, mas há conexão de pé nele — reiniciar derrubaria quem está ligado" \
                "{\"hci\": $(_json_texto "${hci}"), \"timeouts\": ${quantos}}" null \
                "\"porta\": $(_json_texto "${porta}"), \"familia\": \"3\""
            recusou=1
            continue
        fi
        #: O FREIO QUE PARA: esta porta já levou MAX_REINICIOS_SEGUIDOS sem cura.
        #: Segura calado — o diário já disse, uma vez, no tique em que parou.
        if [[ -e "${carimbo}.desistiu" ]]; then
            printf 'segurado\t%s\t%s\tparou depois de %s reinícios\n' \
                "${porta}" "${hci}" "${MAX_REINICIOS_SEGUIDOS}"
            continue
        fi
        if (( agora - anterior < INTERVALO_ENTRE_RESETS_S )); then
            printf 'segurado\t%s\t%s\treiniciado há %ss\n' "${porta}" "${hci}" "$((agora - anterior))"
            #: UMA entrada por reinício: o watchdog pergunta a cada 2 min, e
            #: o sino não pode repetir a mesma frase sete vezes.
            if [[ "$(cat -- "${carimbo}.dito" 2>/dev/null || true)" != "${anterior}" ]]; then
                _diario "bt-ponte" "não insistiu no reinício" \
                    "o adaptador voltou a travar depois de reiniciado há $(( (agora - anterior) / 60 )) min — tire e ponha o adaptador da porta ${porta}" \
                    "{\"hci\": $(_json_texto "${hci}"), \"timeouts\": ${quantos}}" null \
                    "\"porta\": $(_json_texto "${porta}"), \"familia\": \"3\", \"frase\": $(_json_texto "O adaptador da porta ${porta} travou de novo. Tire e ponha ele.")"
                _seco || printf '%s\n' "${anterior}" >"${carimbo}.dito" 2>/dev/null || true
            fi
            continue
        fi
        #: Os reinícios SEGUIDOS: o anterior não curou se o laço voltou antes
        #: de JANELA_DA_CURA_S. Longe disso, a conta recomeça.
        seguidos="$(cat -- "${carimbo}.seguidos" 2>/dev/null || echo 0)"
        [[ "${seguidos}" =~ ^[0-9]+$ ]] || seguidos=0
        if (( anterior <= 0 || agora - anterior > JANELA_DA_CURA_S )); then
            seguidos=0
        fi
        if (( seguidos >= MAX_REINICIOS_SEGUIDOS )); then
            printf 'segurado\t%s\t%s\tparou depois de %s reinícios\n' \
                "${porta}" "${hci}" "${seguidos}"
            if _seco; then
                _dizer_seco "pararia de reiniciar a porta ${porta}: ${seguidos} reinícios sem cura"
                continue
            fi
            printf '%s\n' "${anterior}" >"${carimbo}.desistiu" 2>/dev/null || true
            _diario "bt-ponte" "parou de reiniciar o adaptador" \
                "${seguidos} reinícios seguidos e o laço voltou depois de cada um — reiniciar de novo só faria o adaptador sumir e voltar na porta" \
                "{\"hci\": $(_json_texto "${hci}"), \"timeouts\": ${quantos}, \"reinicios\": ${seguidos}}" null \
                "\"porta\": $(_json_texto "${porta}"), \"familia\": \"3\", \"frase\": $(_json_texto "O adaptador da porta ${porta} não se cura sozinho. Tire e ponha ele.")"
            continue
        fi
        if _seco; then
            _dizer_seco "reiniciaria a porta ${porta} (${hci}, ${quantos} timeouts): authorized 0 -> 1"
            continue
        fi
        pausa="${HEFESTO_USB_PAUSA_S:-2}"
        [[ "${pausa}" =~ ^[0-9]+$ ]] || pausa=2
        if ! printf '0' >"${SYSFS}/bus/usb/devices/${porta}/authorized" 2>/dev/null; then
            printf 'recusado\t%s\t%s\to kernel não aceitou desautorizar\n' "${porta}" "${hci}"
            recusou=1
            continue
        fi
        sleep "${pausa}"
        printf '1' >"${SYSFS}/bus/usb/devices/${porta}/authorized" 2>/dev/null || true
        install -d -m 700 "$(_estampas)" 2>/dev/null || true
        #: O carimbo é a hora DEPOIS de reautorizar: toda linha do laço velho
        #: é anterior a ele, e o tique seguinte só conta o que vier depois.
        printf '%s\n' "$(date +%s)" >"${carimbo}" 2>/dev/null || true
        printf '%s\n' "$((seguidos + 1))" >"${carimbo}.seguidos" 2>/dev/null || true
        #: A volta: o adaptador reaparece na MESMA porta, possivelmente com
        #: outro hciN. Esperar é o que separa «reiniciei» de «reiniciei e ele
        #: voltou».
        espera="${HEFESTO_USB_ESPERA_S:-30}"
        [[ "${espera}" =~ ^[0-9]+$ ]] || espera=30
        volta=""
        while :; do
            volta="$(_hci_da_porta "${porta}" || true)"
            [[ -n "${volta}" || "${espera}" -le 0 ]] && break
            sleep 1
            espera=$((espera - 1))
        done
        printf 'reiniciado\t%s\t%s\t%s\n' "${porta}" "${hci}" "${quantos}"
        _registrar "adaptador da porta ${porta} (${hci}) reiniciado: ${quantos} «command tx timeout» seguidos"
        #: A frase diz o que a espera mediu: «foi reiniciado» só quando o
        #: adaptador VOLTOU à porta. Sem ele, o que resta é a mão do usuário.
        if [[ -n "${volta}" ]]; then
            frase="O adaptador da porta ${porta} travou e foi reiniciado."
        else
            frase="O adaptador da porta ${porta} travou e não voltou. Tire e ponha ele."
        fi
        _diario "bt-ponte" "reiniciou o adaptador" \
            "${quantos} «command tx timeout» seguidos no ${hci}: o controlador travou em laço" \
            "{\"hci\": $(_json_texto "${hci}"), \"timeouts\": ${quantos}}" \
            "{\"hci\": $(_json_texto "${volta}"), \"voltou\": $([[ -n "${volta}" ]] && echo true || echo false)}" \
            "\"porta\": $(_json_texto "${porta}"), \"familia\": \"3\", \"frase\": $(_json_texto "${frase}")"
    done < <(_hcis_em_laco)
    [[ "${achou}" -eq 1 ]] || return 0
    [[ "${recusou}" -eq 0 ]] || exit 1
    return 0
}

# --- O RELIGAR NA HORA (STORM-USB-02, 24/09/2026) ---------------------------
#
# A palavra de 23/09 é «nomear e religar»: o controle que cai por -71 volta
# sozinho, COM O MESMO NÚMERO. O religar existia (o `bt_rebind_orphans.sh`, no
# tique de 2 min do watchdog), mas o lugar guardado de quem saiu vale 30 s — e
# no tique o controle voltava fora do prazo em mais de 3 de cada 4 quedas. Este
# verbo é o mesmo religar chamado pelo kernel-watch NA HORA do aviso do kernel.
#
# SEM ARGUMENTO, como o `reiniciar-travado`: quem escolhe O QUE religar é o /sys,
# pelas guardas do `bt_rebind_orphans.sh` (a HID de um Sony sem driver, no cabo;
# o device HID de um Sony no barramento do rádio, sem driver). A regra do
# sudoers não tem argumento a casar, e o pior que alguém consegue por aqui é
# pedir, antes da hora, o que o watchdog faria sozinho no tique seguinte — com
# o teto de três por controle, que é do script e não de quem chama.
#
# O RELIGAR NÃO MORA AQUI, E É DE PROPÓSITO. A regra de quem é órfão tem um dono
# (o `bt_rebind_orphans.sh`, que o doctor espelha e a régua cruza); uma segunda
# cópia nesta ponte divergiria no primeiro conserto. Rodar o irmão instalado ao
# lado é o que o watchdog root já faz a cada tique, com o mesmo arquivo — e por
# isso a guarda abaixo: como root, o irmão tem de ser do root e não gravável
# por mais ninguém, ou o verbo recusa.
#
# A TRAVA DO RÁDIO NÃO É PEDIDA, e não por esquecimento: religar não mexe no
# rádio (não pareia, não conecta, não reinicia nada) — ele pede ao driver que
# refaça a probe de um aparelho que JÁ está ligado.

#: O `bt_rebind_orphans.sh` ao lado desta ponte — o instalado ao lado do
#: instalado, o da árvore ao lado do da árvore. Vazio (e retorno 1) quando ele
#: não está lá ou, como root, quando não é só do root.
_o_religar() {
    local aqui alvo modo
    aqui="$(readlink -f -- "${BASH_SOURCE[0]}" 2>/dev/null)" || return 1
    alvo="${aqui%/*}/bt_rebind_orphans.sh"
    [[ -f "${alvo}" && ! -L "${alvo}" ]] || return 1
    if [[ "$(id -u)" -eq 0 ]]; then
        [[ "$(stat -c %u -- "${alvo}" 2>/dev/null)" == "0" ]] || return 1
        modo="$(stat -c %a -- "${alvo}" 2>/dev/null)" || return 1
        [[ "${modo}" =~ ^[0-7]{3,4}$ ]] || return 1
        (( (8#${modo} & 8#022) == 0 )) || return 1
    fi
    printf '%s\n' "${alvo}"
}

verbo_religar_orfaos() {
    local religar
    #: Root só é exigido contra o /sys de verdade: com a raiz de teste desviada
    #: (os ganchos do próprio religar, que morrem sob sudo), root não acrescenta
    #: nada — e exigi-lo tornaria o verbo intestável. O mesmo idioma do
    #: `_exige_root` e do `reiniciar-travado`.
    if [[ -z "${HEFESTO_HID_DEVICES_DIR:-}" && -z "${HEFESTO_USB_DEVICES_DIR:-}" \
          && "$(id -u)" -ne 0 ]]; then
        _erro "'religar-orfaos' requer root (é a ponte privilegiada)"
        exit 1
    fi
    if ! religar="$(_o_religar)"; then
        _erro "o religar (bt_rebind_orphans.sh) não está ao lado desta ponte, ou não é só do root — nada foi feito"
        exit 1
    fi
    if _seco; then
        bash "${religar}" --dry-run --evento --quiet
        return 0
    fi
    bash "${religar}" --evento --quiet
}

#: DONO ÚNICO da regra do sudoers. O `install.sh` só canaliza a saída daqui
#: para o `visudo -c`. Verbo novo no `case` lá embaixo tem de aparecer aqui, ou
#: a janela não consegue chamá-lo — que é o sentido certo da falha.
verbo_regra_sudo() {
    local usuaria="$1"
    #: NENHUM argumento de aparelho, e nenhum `*`: o endereço e o nome novo vêm
    #: pelo stdin (contenção 1), e a linha de comando que o sudo permite é o
    #: verbo e nada mais. Um verbo com argumento na regra casa SÓ aquele
    #: argumento — `<ponte> esquecer` não casa `<ponte> esquecer <um> <outro>`,
    #: e a forma velha pede senha. Os segundos do `descobrir` são o único
    #: argumento, em classes de caractere, uma linha por largura: `*` no
    #: sudoers casa espaço em branco, e casar espaço em argumento é como
    #: NOPASSWD estreito vira NOPASSWD largo.
    cat <<FIM
# /etc/sudoers.d/49-hefesto-bt-ponte — gerado por
# ${ALVO_INSTALADO} regra-sudo ${usuaria}
#
# A ponte privilegiada do Bluetooth: o sudo é do install e vale para o app
# inteiro. NÃO editar à mão: o install regrava.
#
# A regra é estreita de propósito — caminho absoluto, verbos nomeados um a um e
# NENHUM curinga. O endereço e o nome novo entram pelo STDIN, não por argv:
# assim não sobra argumento livre a casar aqui, e o registro do sudo diz o
# verbo e nenhum aparelho.
Cmnd_Alias HEFESTO_BT_PONTE = \\
    ${ALVO_INSTALADO} adaptadores, \\
    ${ALVO_INSTALADO} bonds, \\
    ${ALVO_INSTALADO} renomear, \\
    ${ALVO_INSTALADO} esquecer, \\
    ${ALVO_INSTALADO} parear, \\
    ${ALVO_INSTALADO} desconectar, \\
    ${ALVO_INSTALADO} reiniciar-travado, \\
    ${ALVO_INSTALADO} religar-orfaos, \\
    ${ALVO_INSTALADO} descobrir [0-9], \\
    ${ALVO_INSTALADO} descobrir [0-9][0-9], \\
    ${ALVO_INSTALADO} descobrir [0-9][0-9][0-9]

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
        _sem_dado_no_argv bonds "$@"
        _mac_do_stdin 'MAC do adaptador'; ARG_ADAPTADOR="${VALIDADO}"
        _fim_do_stdin
        verbo_bonds "${ARG_ADAPTADOR}"
        ;;
    renomear)
        _sem_dado_no_argv renomear "$@"
        _mac_do_stdin 'MAC do adaptador'; ARG_ADAPTADOR="${VALIDADO}"
        #: A recusa do nome tem de matar o PROCESSO, não uma subshell — por
        #: isso a função devolve pela global (ver o comentário de `VALIDADO`).
        _nome_do_stdin;                    ARG_NOME="${VALIDADO}"
        _fim_do_stdin
        verbo_renomear "${ARG_ADAPTADOR}" "${ARG_NOME}"
        ;;
    esquecer)
        _sem_dado_no_argv esquecer "$@"
        _mac_do_stdin 'MAC do adaptador'; ARG_ADAPTADOR="${VALIDADO}"
        _mac_do_stdin 'MAC do controle';  ARG_CONTROLE="${VALIDADO}"
        _fim_do_stdin
        verbo_esquecer "${ARG_ADAPTADOR}" "${ARG_CONTROLE}"
        ;;
    descobrir)
        [[ $# -eq 1 ]] || _recusar "descobrir recebe só os segundos no argv; o endereço vem pelo stdin, uma linha por dado"
        _segundos "${1}";                  ARG_SEGUNDOS="${VALIDADO}"
        _mac_do_stdin 'MAC do adaptador'; ARG_ADAPTADOR="${VALIDADO}"
        _fim_do_stdin
        verbo_descobrir "${ARG_ADAPTADOR}" "${ARG_SEGUNDOS}"
        ;;
    parear)
        _sem_dado_no_argv parear "$@"
        _mac_do_stdin 'MAC do adaptador'; ARG_ADAPTADOR="${VALIDADO}"
        _mac_do_stdin 'MAC do controle';  ARG_CONTROLE="${VALIDADO}"
        _fim_do_stdin
        verbo_parear "${ARG_ADAPTADOR}" "${ARG_CONTROLE}"
        ;;
    desconectar)
        _sem_dado_no_argv desconectar "$@"
        _mac_do_stdin 'MAC do adaptador'; ARG_ADAPTADOR="${VALIDADO}"
        _mac_do_stdin 'MAC do controle';  ARG_CONTROLE="${VALIDADO}"
        _fim_do_stdin
        verbo_desconectar "${ARG_ADAPTADOR}" "${ARG_CONTROLE}"
        ;;
    reiniciar-travado)
        [[ $# -eq 0 ]] || _recusar "reiniciar-travado não recebe argumento (quem escolhe a porta é o kernel)"
        verbo_reiniciar_travado
        ;;
    religar-orfaos)
        [[ $# -eq 0 ]] || _recusar "religar-orfaos não recebe argumento (quem escolhe o controle é o /sys)"
        verbo_religar_orfaos
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
